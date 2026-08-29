"""预处理流水线：R2 对齐至 R1 网格 → 重采样 1×1×2 mm（图像 BSpline、掩膜最近邻）
→ 肿瘤包围盒外扩 5 体素裁剪 → 跨图像强度标准化（主分析：肌肉均值线性缩放 / 敏感性：
肿瘤 ROI Z-score）→ 保存 NRRD。

N4 偏置场校正暂缓（n4_enabled=false，归一化质控后决策是否重启）；启用时仅前景掩膜
全图校正（降采样估计偏置场，n4_downsample_factor）。
逐例 try/except；流水线版本戳与输出并存，版本一致且产物齐全的病例自动跳过（断点续跑）；
计时写入 output/qc/logs/preprocess_timing.csv，归一化指标写入 preprocess_metrics.csv，
告警写入 output/qc/qc_report.csv（--metrics-csv/--timing-csv/--qc-report 可隔离输出路径，
供 N4 试点等对照运行使用）。

用法:
  python scripts/preprocess.py [--ids ID1,ID2,...] [--force] [--normalize muscle|zscore]
                               [--n4] [--n4-factor 2.0]
                               [--metrics-csv ...] [--timing-csv ...] [--qc-report ...]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import time

import numpy as np
import pandas as pd
import SimpleITK as sitk

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "output")
PREP = os.path.join(OUT, "preprocessed")
PREP_DIR = PREP  # 输出目录（--prep-dir 覆盖；z-score 敏感性臂用 output/preprocessed_zscore）
QC_DIR = os.path.join(OUT, "qc")
QC_LOG = os.path.join(QC_DIR, "logs")
QC_REPORT = os.path.join(QC_DIR, "qc_report.csv")
TIMING_CSV = os.path.join(QC_LOG, "preprocess_timing.csv")
METRICS_CSV = os.path.join(QC_LOG, "preprocess_metrics.csv")
CONFIG = os.path.join(ROOT, "configs", "radiomics_params.yaml")

DEFAULTS = {
    "target_spacing": [1.0, 1.0, 2.0],
    "resample_interpolator": "sitkBSpline",
    "mask_interpolator": "sitkNearestNeighbor",
    "n4_enabled": False,
    "n4_mask": "foreground",
    "n4_downsample_factor": 2.0,
    "normalization": "muscle",
    "erode_radius_R1": [1, 1, 0],
    "erode_radius_R2": [2, 2, 0],
    "crop_padding": 5,
    "geometry_tolerance": 1e-3,
    "min_tumor_voxels": 10,
}
INTERP = {"sitkBSpline": sitk.sitkBSpline, "sitkNearestNeighbor": sitk.sitkNearestNeighbor}
TIMING_COLS = ["影像号", "读者", "read", "n4", "resample", "align", "crop", "zscore", "save", "total"]
METRICS_COLS = ["影像号", "读者", "normalization", "muscle_label", "muscle_mean",
                "muscle_voxels", "eroded_voxels", "erode_radius", "muscle_cv",
                "muscle_p10", "muscle_p50", "muscle_p90", "grad", "fallback"]
PIPELINE_VERSION = "v4"


def pipeline_stamp(cfg: dict) -> str:
    """流水线版本戳：脚本版本 + 预处理关键参数哈希（断点续跑版本判定）。"""
    payload = {"v": PIPELINE_VERSION,
               **{k: cfg[k] for k in ("target_spacing", "resample_interpolator",
                                      "mask_interpolator", "n4_enabled", "n4_mask",
                                      "normalization", "erode_radius_R1", "erode_radius_R2",
                                      "crop_padding", "geometry_tolerance")}}
    return hashlib.md5(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def load_config() -> dict:
    cfg = dict(DEFAULTS)
    if os.path.exists(CONFIG):
        try:
            import yaml
            p = yaml.safe_load(open(CONFIG, encoding="utf-8")) or {}
            for k, v in (p.get("preprocessing") or {}).items():
                cfg[k] = v
        except Exception as e:  # noqa: BLE001
            print(f"[warn] 配置解析失败，使用默认参数: {e}")
    return cfg


def mask_image(mask_arr: np.ndarray, ref: sitk.Image, label: int) -> sitk.Image:
    img = sitk.GetImageFromArray((mask_arr == label).astype(np.uint8))
    img.CopyInformation(ref)
    return img


def foreground_mask(img: sitk.Image) -> sitk.Image:
    """前景掩膜：Otsu 阈值 + 最大连通域（排除空气背景）。"""
    f = sitk.Cast(img, sitk.sitkFloat32)
    thr = sitk.OtsuThresholdImageFilter()
    thr.SetOutsideValue(0)
    thr.SetInsideValue(1)
    m = thr.Execute(f)
    cc = sitk.ConnectedComponent(m > 0)
    rel = sitk.RelabelComponent(cc)
    out = rel == 1
    out.CopyInformation(img)
    return out


def muscle_stats(img: sitk.Image, mask_arr: np.ndarray, label: int,
                 erode_radius: list[int]) -> dict:
    """肌肉掩膜统计（仅以肌肉为参照组织）：面内腐蚀去除部分容积效应，腐蚀后体素不足
    50 时逐级减半径退回。

    返回 dict（肌肉为空时返回 {}）：
      mean/total/eroded/cv/p10/p50/p90、erode_radius（实际使用半径）、
      grad（肌肉内面内强度梯度斜率，%/mm）。
    """
    m = (mask_arr == label).astype(np.uint8)
    total = int(m.sum())
    if total == 0:
        return {}
    mimg = sitk.GetImageFromArray(m)
    mimg.CopyInformation(img)
    radius_used = [int(r) for r in erode_radius]
    ea = sitk.GetArrayFromImage(sitk.BinaryErode(
        mimg, kernelRadius=radius_used, kernelType=sitk.sitkBox))
    n_ero = int(ea.sum())
    while n_ero < 50 and any(r > 0 for r in radius_used):
        radius_used = [max(r - 1, 0) for r in radius_used]
        ea = sitk.GetArrayFromImage(sitk.BinaryErode(
            mimg, kernelRadius=radius_used, kernelType=sitk.sitkBox))
        n_ero = int(ea.sum())
    if n_ero == 0:
        ea, n_ero = m, total
        radius_used = [0, 0, 0]
    arr = sitk.GetArrayFromImage(img).astype(np.float64)
    vals = arr[ea == 1]
    mu = float(vals.mean())
    sd = float(vals.std())
    cv = float(sd / mu) if mu > 0 else float("nan")
    p10, p50, p90 = (float(np.percentile(vals, q)) for q in (10, 50, 90))
    zs, ys, xs = np.where(ea == 1)
    if vals.size > 20000:
        step = int(np.ceil(vals.size / 20000.0))
        sel = np.arange(0, vals.size, step)
        xs_s, ys_s, vals_s = xs[sel], ys[sel], vals[sel]
    else:
        xs_s, ys_s, vals_s = xs, ys, vals
    A = np.column_stack([xs_s, ys_s, np.ones_like(xs_s)])
    try:
        coef, *_ = np.linalg.lstsq(A, vals_s, rcond=None)
        grad = float(np.hypot(coef[0], coef[1]) / mu * 100.0) if mu > 0 else float("nan")
        grad = grad / min(img.GetSpacing()[0], img.GetSpacing()[1])  # %/mm
    except Exception:  # noqa: BLE001
        grad = float("nan")
    return {"mean": mu, "total": total, "eroded": n_ero, "cv": cv,
            "p10": p10, "p50": p50, "p90": p90,
            "grad": grad, "erode_radius": radius_used}


def mus_metrics(mus: dict | None, fallback: bool, mlab: str) -> dict:
    """归一化指标 dict → 记录行字段。"""
    if not mus:
        return {"muscle_label": mlab, "fallback": fallback}
    return {"muscle_label": mlab,
            "muscle_mean": mus["mean"], "muscle_voxels": mus["total"],
            "eroded_voxels": mus["eroded"],
            "erode_radius": ",".join(map(str, mus["erode_radius"])),
            "muscle_cv": mus["cv"], "muscle_p10": mus["p10"],
            "muscle_p50": mus["p50"], "muscle_p90": mus["p90"],
            "grad": mus["grad"], "fallback": fallback}


def n4_correct(image: sitk.Image, mask: sitk.Image | None, factor: float = 1.0) -> sitk.Image:
    """N4 偏置场校正（仅前景掩膜全图校正）。

    factor > 1 时采用降采样策略：图像与掩膜重采样至 factor× 间距的粗网格，
    在粗网格上估计偏置场，再以原始图像网格为参考重采样回全分辨率后施加校正
    （校正耗时随掩膜体素数近似线性下降）。
    """
    filt = sitk.N4BiasFieldCorrectionImageFilter()
    img = sitk.Cast(image, sitk.sitkFloat32)
    if mask is None or factor <= 1.0:
        return filt.Execute(img, mask) if mask is not None else filt.Execute(img)
    sp = list(img.GetSpacing())
    coarse_sp = [s * factor for s in sp]
    img_c = resample_to(img, spacing=coarse_sp, interp=sitk.sitkBSpline)
    m_c = resample_to(mask, spacing=coarse_sp, interp=sitk.sitkNearestNeighbor,
                      pixel=sitk.sitkUInt8)
    filt.Execute(img_c, m_c)
    logbias = filt.GetLogBiasFieldAsImage(img)
    out = img / sitk.Exp(logbias)
    out.CopyInformation(img)
    return out


def resample_to(img: sitk.Image, spacing=None, grid=None, interp=sitk.sitkBSpline,
                pixel=None, default=0.0) -> sitk.Image:
    """重采样：spacing 给定目标间距（保留原点/方向），或 grid 给定完整目标网格。"""
    if grid is not None:
        size, origin, sp, dr = grid
    else:
        size = [int(math.ceil(img.GetSize()[i] * img.GetSpacing()[i] / spacing[i])) for i in range(3)]
        origin, sp, dr = img.GetOrigin(), list(spacing), img.GetDirection()
    return sitk.Resample(img, size, sitk.Transform(), interp, origin, sp, dr,
                         default, pixel if pixel is not None else img.GetPixelIDValue())


def crop_bbox(image: sitk.Image, mask_arr: np.ndarray, pad: int) -> sitk.Image:
    zs, ys, xs = np.where(mask_arr)
    z0, z1 = max(int(zs.min()) - pad, 0), min(int(zs.max()) + pad + 1, mask_arr.shape[0])
    y0, y1 = max(int(ys.min()) - pad, 0), min(int(ys.max()) + pad + 1, mask_arr.shape[1])
    x0, x1 = max(int(xs.min()) - pad, 0), min(int(xs.max()) + pad + 1, mask_arr.shape[2])
    arr = sitk.GetArrayFromImage(image)[z0:z1, y0:y1, x0:x1]
    out = sitk.GetImageFromArray(arr)
    out.SetSpacing(image.GetSpacing())
    out.SetOrigin(image.TransformIndexToPhysicalPoint((int(x0), int(y0), int(z0))))
    out.SetDirection(image.GetDirection())
    return out


def zscore_roi(image: sitk.Image, mask_arr: np.ndarray) -> tuple[sitk.Image, float, float]:
    arr = sitk.GetArrayFromImage(image).astype(np.float32)
    roi = arr[mask_arr == 1]
    mu, sd = float(roi.mean()), float(roi.std())
    if sd > 1e-12:
        arr = (arr - mu) / sd
    out = sitk.GetImageFromArray(arr)
    out.CopyInformation(image)
    return out, mu, sd


def geom_consistent(a: sitk.Image, b: sitk.Image, tol: float) -> bool:
    if list(a.GetSize()) != list(b.GetSize()):
        return False
    return all(abs(x - y) <= tol for x, y in zip(
        list(a.GetSpacing()) + list(a.GetOrigin()) + list(a.GetDirection()),
        list(b.GetSpacing()) + list(b.GetOrigin()) + list(b.GetDirection())))


def save_qc(qc: dict) -> None:
    """质控告警追加式写入（按 影像号+阶段+代码+说明 去重），避免多模式运行相互覆盖。"""
    rows = []
    if os.path.exists(QC_REPORT):
        try:
            rows = pd.read_csv(QC_REPORT, dtype=str).to_dict("records")
        except Exception:
            rows = []
    for pid in qc:
        rows.extend(qc[pid])
    seen: set[tuple] = set()
    out = []
    for r in rows:
        key = (r.get("影像号"), r.get("阶段"), r.get("代码"), r.get("说明"))
        if key not in seen:
            seen.add(key)
            out.append(r)
    os.makedirs(QC_DIR, exist_ok=True)
    pd.DataFrame(out).to_csv(QC_REPORT, index=False, encoding="utf-8-sig")


def process(pid: str, row: pd.Series, cfg: dict, qc: dict, force: bool) -> tuple[str, dict, dict | None, dict]:
    rel = lambda p: os.path.join(ROOT, p)  # noqa: E731
    outdir = os.path.join(PREP_DIR, pid)
    os.makedirs(outdir, exist_ok=True)
    r1_files = [os.path.join(outdir, "R1_image.nrrd"), os.path.join(outdir, "R1_mask.nrrd")]
    has_r2 = str(row.get("是否双读者", "")) == "1" and not pd.isna(row.get("R2图像文件"))
    r2_files = [os.path.join(outdir, "R2_image.nrrd"), os.path.join(outdir, "R2_mask.nrrd")] if has_r2 else []
    stamp_path = os.path.join(outdir, ".pipeline_stamp")
    if not force and all(os.path.exists(f) for f in r1_files + r2_files):
        if os.path.exists(stamp_path) and \
                open(stamp_path, encoding="ascii").read().strip() == pipeline_stamp(cfg):
            return "skipped", {}, {}, {}
    qc[pid] = []
    mtr: dict = {}

    def warn(code: str, msg: str, level: str = "WARN") -> None:
        qc[pid].append({"影像号": pid, "阶段": "preprocess", "级别": level, "代码": code, "说明": msg})

    st1 = {"read": 0.0, "n4": 0.0, "resample": 0.0, "align": 0.0, "crop": 0.0, "zscore": 0.0, "save": 0.0, "total": 0.0}
    st2 = dict(st1) if has_r2 else None

    # ---- R1
    t = time.perf_counter()
    i1 = sitk.ReadImage(rel(row["图像文件"]))
    m1 = sitk.ReadImage(rel(row["掩膜文件"]))
    st1["read"] = time.perf_counter() - t
    if not geom_consistent(i1, m1, cfg["geometry_tolerance"]):
        warn("GEOM_MISMATCH", "R1 图像与掩膜几何不一致")
    a1 = sitk.GetArrayFromImage(m1)
    n1 = int((a1 == 1).sum())
    if n1 == 0:
        warn("NO_TUMOR", "无肿瘤勾画，剔除", "ERROR")
        save_qc(qc)
        return "excluded", st1, st2, mtr
    if n1 < cfg["min_tumor_voxels"]:
        warn("SMALL_TUMOR", f"肿瘤体素 {n1} < {cfg['min_tumor_voxels']}（记录评估）")

    # N4 偏置场校正（暂缓：n4_enabled=False 时跳过；启用时仅前景掩膜全图校正，降采样估计偏置场）
    n4_on = bool(cfg.get("n4_enabled"))
    n4_f = float(cfg.get("n4_downsample_factor", 1.0))
    n4_mask1 = foreground_mask(i1) if (n4_on and cfg["n4_mask"] == "foreground") else None
    t = time.perf_counter()
    corr1 = n4_correct(i1, n4_mask1, factor=n4_f) if n4_on else sitk.Cast(i1, sitk.sitkFloat32)
    st1["n4"] = time.perf_counter() - t

    # 归一化参数（主分析：肌肉均值线性缩放；敏感性：Z-score）
    norm_mode = cfg["normalization"]
    mus1 = None
    if norm_mode == "muscle":
        mus1 = muscle_stats(corr1, a1, 3, erode_radius=cfg["erode_radius_R1"])
        if not mus1:
            warn("NO_MUSCLE", "R1 无标签3（肌肉），退回 Z-score 标准化（敏感性方案）")
            norm_mode = "zscore_fallback"

    # 重采样至 1×1×2 mm（保留原点与方向）
    t = time.perf_counter()
    sp = list(cfg["target_spacing"])
    r1 = resample_to(corr1, spacing=sp, interp=INTERP[cfg["resample_interpolator"]])
    rm1 = resample_to(mask_image(a1, i1, 1), spacing=sp,
                      interp=INTERP[cfg["mask_interpolator"]], pixel=sitk.sitkUInt8)
    st1["resample"] = time.perf_counter() - t
    if not geom_consistent(r1, rm1, cfg["geometry_tolerance"]):
        warn("GEOM_MISMATCH", "重采样后 R1 图像与掩膜几何不一致")
    a_rm1 = sitk.GetArrayFromImage(rm1) == 1

    # ---- R2（双读者）
    if st2 is not None:
        t = time.perf_counter()
        i2 = sitk.ReadImage(rel(row["R2图像文件"]))
        m2 = sitk.ReadImage(rel(row["R2掩膜文件"]))
        st2["read"] = time.perf_counter() - t
        if not geom_consistent(i2, m2, cfg["geometry_tolerance"]):
            warn("GEOM_MISMATCH", "R2 图像与掩膜几何不一致")
        a2 = sitk.GetArrayFromImage(m2)
        n2 = int((a2 == 1).sum())
        if n2 == 0:
            warn("R2_NO_TUMOR", "R2 无肿瘤勾画，跳过 R2", "ERROR")
            st2 = None
        else:
            # 覆盖校验：R1 肿瘤包围盒角点须落在 R2 物理范围内
            zs, ys, xs = np.where(a1 == 1)
            idx = np.array([[x, y, z] for z in (zs.min(), zs.max())
                            for y in (ys.min(), ys.max())
                            for x in (xs.min(), xs.max())], float)
            d1 = np.array(i1.GetDirection()).reshape(3, 3)
            sp1 = np.array(i1.GetSpacing())
            pts = np.array(i1.GetOrigin()) + (d1 @ (sp1[:, None] * idx.T)).T
            sz2 = np.array(i2.GetSize())
            d2m = np.array(i2.GetDirection()).reshape(3, 3)
            sp2 = np.array(i2.GetSpacing())
            cidx = np.array([[x, y, z] for z in (0, sz2[2] - 1)
                             for y in (0, sz2[1] - 1) for x in (0, sz2[0] - 1)], float)
            corners2 = np.array(i2.GetOrigin()) + (d2m @ (sp2[:, None] * cidx.T)).T
            mn, mx = corners2.min(axis=0), corners2.max(axis=0)
            tol = cfg["geometry_tolerance"]
            if not (np.all(pts >= mn - tol) and np.all(pts <= mx + tol)):
                warn("R2_FOV_NOT_COVERED", "R2 空间范围未覆盖 R1 肿瘤，跳过 R2（人工复核）", "ERROR")
                st2 = None

    if st2 is not None:
        # R2 N4（暂缓；启用时仅前景掩膜全图校正）
        n4_mask2 = foreground_mask(i2) if (n4_on and cfg["n4_mask"] == "foreground") else None
        t = time.perf_counter()
        corr2 = n4_correct(i2, n4_mask2, factor=n4_f) if n4_on else sitk.Cast(i2, sitk.sitkFloat32)
        st2["n4"] = time.perf_counter() - t

        # R2 归一化参数：肌肉标签（2 或 3）按同图内标签2/3平均灰度判别，采用 R2 自身肌肉
        mus2 = None
        mlab = ""
        if norm_mode == "muscle":
            mlab = str(row.get("R2肌肉标签", ""))
            if mlab in ("2", "3"):
                mus2 = muscle_stats(corr2, a2, int(mlab),
                                    erode_radius=cfg["erode_radius_R2"])
                if not mus2:
                    warn("NO_MUSCLE", f"R2 肌肉标签{mlab}为空，R1/R2 同步退回 Z-score 标准化")
                    norm_mode, mus1 = "zscore_fallback", None
                elif mlab == "2":
                    warn("R2_MUSCLE_LABEL2", "R2 标签2为肌肉（标签3为脂肪），以标签2计算 μ_muscle")
            else:
                warn("NO_MUSCLE", "R2 无肌肉标签（标签2/3均缺），R1/R2 同步退回 Z-score 标准化")
                norm_mode, mus1 = "zscore_fallback", None
        mtr["R2"] = {"normalization": norm_mode,
                     **mus_metrics(mus2, norm_mode == "zscore_fallback", mlab)}

        # R2 对齐：重采样至 R1 重采样网格（方向/原点取 R1，间距 1×1×2）
        t = time.perf_counter()
        grid = (list(r1.GetSize()), r1.GetOrigin(), list(r1.GetSpacing()), r1.GetDirection())
        r2 = resample_to(corr2, grid=grid, interp=INTERP[cfg["resample_interpolator"]])
        rm2 = resample_to(mask_image(a2, i2, 1), grid=grid,
                          interp=INTERP[cfg["mask_interpolator"]], pixel=sitk.sitkUInt8)
        st2["align"] = time.perf_counter() - t
        if list(r2.GetSize()) != list(r1.GetSize()):
            warn("R2_GRID_MISMATCH", "R2 重采样网格与 R1 不一致", "ERROR")

        # 裁剪（双读者共用 R1∪R2 肿瘤并集框，保证同网格）
        t = time.perf_counter()
        a_rm2 = sitk.GetArrayFromImage(rm2) == 1
        box_mask = a_rm1 | a_rm2
        c2 = crop_bbox(r2, box_mask, cfg["crop_padding"])
        c2m = crop_bbox(rm2, box_mask, cfg["crop_padding"])
        st2["crop"] = time.perf_counter() - t
        t = time.perf_counter()
        if mus2:
            z2 = sitk.Cast(c2 / mus2["mean"], sitk.sitkFloat32)
        else:
            z2, _, sd2 = zscore_roi(c2, sitk.GetArrayFromImage(c2m) == 1)
            if sd2 <= 1e-12:
                warn("ZSCORE_SD_ZERO", "R2 肿瘤 ROI 灰度标准差为 0，未标准化")
        st2["zscore"] = time.perf_counter() - t
        c2m.CopyInformation(c2)  # 掩膜几何以图像为基准（消除浮点舍入差异）
        t = time.perf_counter()
        sitk.WriteImage(z2, r2_files[0])
        sitk.WriteImage(c2m, r2_files[1])
        st2["save"] = time.perf_counter() - t
        st2["total"] = sum(st2.values())

    mtr["R1"] = {"normalization": norm_mode,
                 **mus_metrics(mus1, norm_mode == "zscore_fallback", "3" if mus1 else "")}

    # R1 裁剪 + 标准化（双读者共用并集框，保证与 R2 同网格）
    t = time.perf_counter()
    box = a_rm1 if st2 is None else box_mask
    c1 = crop_bbox(r1, box, cfg["crop_padding"])
    c1m = crop_bbox(rm1, box, cfg["crop_padding"])
    st1["crop"] = time.perf_counter() - t
    t = time.perf_counter()
    if mus1:
        z1 = sitk.Cast(c1 / mus1["mean"], sitk.sitkFloat32)
    else:
        z1, _, sd1 = zscore_roi(c1, sitk.GetArrayFromImage(c1m) == 1)
        if sd1 <= 1e-12:
            warn("ZSCORE_SD_ZERO", "R1 肿瘤 ROI 灰度标准差为 0，未标准化")
    st1["zscore"] = time.perf_counter() - t
    c1m.CopyInformation(c1)  # 掩膜几何以图像为基准（消除浮点舍入差异）
    t = time.perf_counter()
    sitk.WriteImage(z1, r1_files[0])
    sitk.WriteImage(c1m, r1_files[1])
    st1["save"] = time.perf_counter() - t
    st1["total"] = sum(st1.values())

    with open(stamp_path, "w", encoding="ascii") as f:
        f.write(pipeline_stamp(cfg))
    save_qc(qc)
    return "done", st1, st2, mtr


def main() -> None:
    ap = argparse.ArgumentParser(description="预处理流水线")
    ap.add_argument("--manifest", default=os.path.join(OUT, "manifest.csv"))
    ap.add_argument("--ids", help="逗号分隔的影像号（缺省处理清单全部病例）")
    ap.add_argument("--force", action="store_true", help="忽略已存在输出，重新处理")
    ap.add_argument("--normalize", choices=["muscle", "zscore"], help="覆盖跨图像标准化配置")
    ap.add_argument("--prep-dir", default="output/preprocessed",
                    help="预处理输出目录（相对项目根；z-score 臂建议 output/preprocessed_zscore）")
    ap.add_argument("--n4", action="store_true", help="启用 N4（仅前景掩膜全图校正，降采样估计偏置场）")
    ap.add_argument("--n4-factor", type=float, help="N4 降采样因子（覆盖配置值）")
    ap.add_argument("--metrics-csv", help="归一化指标表路径（缺省共享 preprocess_metrics.csv）")
    ap.add_argument("--timing-csv", help="计时表路径（缺省共享 preprocess_timing.csv）")
    ap.add_argument("--qc-report", help="质控告警表路径（缺省共享 qc_report.csv）")
    args = ap.parse_args()

    cfg = load_config()
    if args.normalize:
        cfg["normalization"] = args.normalize
    if args.n4:
        cfg["n4_enabled"] = True
    if args.n4_factor:
        cfg["n4_downsample_factor"] = args.n4_factor
    global PREP_DIR, METRICS_CSV, TIMING_CSV, QC_REPORT
    PREP_DIR = os.path.join(ROOT, args.prep_dir)

    def _path(p: str) -> str:
        return os.path.join(ROOT, p) if p and not os.path.isabs(p) else p

    if args.metrics_csv:
        METRICS_CSV = _path(args.metrics_csv)
    if args.timing_csv:
        TIMING_CSV = _path(args.timing_csv)
    if args.qc_report:
        QC_REPORT = _path(args.qc_report)
    if cfg["n4_enabled"]:
        print(f"[N4] 已启用：前景掩膜全图校正，降采样因子 {cfg['n4_downsample_factor']:g}")
    if os.path.exists(CONFIG):
        os.makedirs(os.path.join(OUT, "configs"), exist_ok=True)
        shutil.copy2(CONFIG, os.path.join(OUT, "configs", "radiomics_params.yaml"))

    df = pd.read_csv(args.manifest, encoding="utf-8-sig", dtype=str)
    if args.ids:
        ids = [x.strip() for x in args.ids.split(",") if x.strip()]
        df = df[df["影像号"].isin(ids)]
    os.makedirs(QC_LOG, exist_ok=True)
    write_header = not os.path.exists(TIMING_CSV)

    t_rows: list[dict] = []
    m_rows: list[dict] = []
    qc: dict = {}
    status: dict = {}
    for _, row in df.iterrows():
        pid = row["影像号"]
        if str(row.get("排除", "")) == "1":
            status["excluded"] = status.get("excluded", 0) + 1
            continue
        try:
            st, st1, st2, mtr = process(pid, row, cfg, qc, args.force)
            status[st] = status.get(st, 0) + 1
            if st1.get("total"):
                t_rows.append({"影像号": pid, "读者": "R1", **{k: round(v, 3) for k, v in st1.items()}})
            if st2 and st2.get("total"):
                t_rows.append({"影像号": pid, "读者": "R2", **{k: round(v, 3) for k, v in st2.items()}})
            for reader in ("R1", "R2"):
                if reader in mtr:
                    m_rows.append({"影像号": pid, "读者": reader, **mtr[reader]})
        except Exception as e:  # noqa: BLE001
            qc[pid] = [{"影像号": pid, "阶段": "preprocess", "级别": "ERROR",
                        "代码": "EXCEPTION", "说明": f"{type(e).__name__}: {e}"}]
            status["error"] = status.get("error", 0) + 1
    save_qc(qc)

    if m_rows:
        mdf = pd.DataFrame(m_rows, columns=METRICS_COLS)
        if os.path.exists(METRICS_CSV):
            try:
                old = pd.read_csv(METRICS_CSV, dtype=str)
                mdf = pd.concat([old, mdf], ignore_index=True).drop_duplicates(
                    subset=["影像号", "读者", "normalization"], keep="last")
            except pd.errors.EmptyDataError:
                pass
        mdf.to_csv(METRICS_CSV, index=False, encoding="utf-8-sig")

    if t_rows:
        tdf = pd.DataFrame(t_rows, columns=TIMING_COLS)
        tdf.to_csv(TIMING_CSV, mode="a", header=write_header, index=False, encoding="utf-8-sig")
        r1, r2 = tdf[tdf["读者"] == "R1"], tdf[tdf["读者"] == "R2"]
        print("\n===== 计时汇总 (秒) =====")
        for name, d in (("R1", r1), ("R2", r2)):
            if len(d):
                print(f"[{name}] n={len(d)}  mean={d['total'].mean():.1f}  median={d['total'].median():.1f}  max={d['total'].max():.1f}")
                for c in ("read", "n4", "resample", "align", "crop", "zscore", "save"):
                    print(f"    {c}: mean={d[c].mean():.2f}")
        n_all = len(df)
        n_r2 = int((df["是否双读者"] == "1").sum()) if "是否双读者" in df.columns else 0
        if len(r1):
            est = r1["total"].mean() * n_all + r2["total"].mean() * n_r2
            print(f"全队列预估: R1 {n_all} 例 × {r1['total'].mean():.1f}s + R2 {n_r2} 例 × {r2['total'].mean():.1f}s"
                  f" ≈ {est / 60:.1f} 分钟（{est / 3600:.2f} 小时）")
    print("状态统计:", status)


if __name__ == "__main__":
    main()
