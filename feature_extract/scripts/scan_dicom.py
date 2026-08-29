# -*- coding: utf-8 -*-
"""扫描原始 DICOM 源，为 manifest 每个病例建立「影像号 → 厂商/机型/场强」映射。

匹配策略：
1. NRRD 文件名形如 "<系列号> <描述>.nrrd"，取前导数字与 DICOM 系列目录 S_<系列号> 匹配；
2. 几何验证：行/列数相等、面内间距相对差 <5%、层数差 <=3；
3. 无前导数字的序列名（如 t2_fse_otra）退化为纯几何匹配；
4. R2 图像同样尝试匹配（可能位于同一影像号下不同检查号/系列）。

输出：output/scanner_map.csv（utf-8-sig）+ 控制台汇总。
用法：python scripts/scan_dicom.py [--dicom-root 路径] [--manifest output/manifest.csv]
"""
from __future__ import annotations

import argparse
import glob
import math
import os
import re

import pandas as pd
import SimpleITK as sitk

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DICOM_ROOT = r"J:\张无忌   20260421"


def nrrd_geometry(path: str) -> tuple[list[int] | None, list[float] | None]:
    """仅读 NRRD 文本头（不读体数据），返回尺寸与三个方向向量的模长（即体素间距）。"""
    with open(path, "rb") as f:
        head = f.read(8192).decode("ascii", errors="ignore")
    m_size = re.search(r"sizes:\s*([^\n]+)", head)
    m_sp = re.search(r"space directions:\s*([^\n]+)", head)
    size = [int(x) for x in m_size.group(1).split()] if m_size else None
    sp = None
    if m_sp:
        toks = re.findall(r"\(([^)]*)\)", m_sp.group(1))
        try:
            vecs = [[float(x) for x in t.split(",")] for t in toks[:3]]
            sp = [math.sqrt(sum(v[i] ** 2 for i in range(3))) for v in vecs]
        except ValueError:
            sp = None
    return size, sp


def read_dicom_tags(first_file: str) -> dict:
    img = sitk.ReadImage(first_file)
    def md(k):
        try:
            return img.GetMetaData(k)
        except Exception:
            return ""
    return {
        "厂商": md("0008|0070").strip(),
        "机型": md("0008|1090").strip(),
        "场强": md("0018|0087").strip(),
        "系列号": md("0020|0011").strip(),
        "行": int(md("0028|0010") or 0),
        "列": int(md("0028|0011") or 0),
        "面内间距": md("0028|0030").strip(),
        "层厚": md("0018|0050").strip(),
        "层数": len(glob.glob(os.path.join(os.path.dirname(first_file), "*"))),
    }


def series_dirs(exam_dir: str) -> list[str]:
    out = []
    for d in os.listdir(exam_dir):
        p = os.path.join(exam_dir, d)
        if os.path.isdir(p) and re.match(r"^S_\d+$", d):
            out.append(p)
    return out


def find_series(case_dir: str, nrrd_path: str, want_num: int | None,
                nrrd_size, nrrd_sp) -> list[dict]:
    """在影像号目录下所有检查号中找与 NRRD 匹配的系列。"""
    cands = []
    for exam in os.listdir(case_dir):
        ep = os.path.join(case_dir, exam)
        if not os.path.isdir(ep):
            continue
        for sd in series_dirs(ep):
            m = re.match(r"^S_(\d+)$", os.path.basename(sd))
            if not m:
                continue
            num = int(m.group(1))
            if want_num is not None and num != want_num:
                continue
            files = sorted(glob.glob(os.path.join(sd, "*")))
            if not files:
                continue
            tags = read_dicom_tags(files[0])
            # 几何验证
            ok = True
            reason = []
            if nrrd_size and tags["行"]:
                if tags["行"] != nrrd_size[0] or tags["列"] != nrrd_size[1]:
                    ok, reason = False, ["行列不符"]
            if ok and nrrd_sp and tags["面内间距"]:
                try:
                    xy = [float(x) for x in tags["面内间距"].split("\\")]
                    if abs(xy[0] - nrrd_sp[0]) / nrrd_sp[0] > 0.05 or \
                       abs(xy[1] - nrrd_sp[1]) / nrrd_sp[1] > 0.05:
                        ok, reason = False, ["面内间距不符"]
                except ValueError:
                    pass
            if ok and nrrd_size and tags["层数"]:
                if abs(tags["层数"] - nrrd_size[2]) > 3:
                    ok, reason = False, ["层数不符"]
            cands.append({"检查号": exam, "系列目录": os.path.basename(sd),
                          "几何一致": ok, "不匹配原因": ";".join(reason), **tags})
    return cands


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dicom-root", default=DEFAULT_DICOM_ROOT)
    ap.add_argument("--manifest", default=os.path.join(ROOT, "output", "manifest.csv"))
    args = ap.parse_args()

    df = pd.read_csv(args.manifest, encoding="utf-8-sig", dtype=str)
    rows = []
    for _, r in df.iterrows():
        pid = r["影像号"]
        case_dir = os.path.join(args.dicom_root, pid)
        if not os.path.isdir(case_dir):
            rows.append({"影像号": pid, "序列名": r["序列名"], "状态": "缺目录"})
            continue
        rec = {"影像号": pid, "序列名": r["序列名"]}
        for key, tag in (("图像文件", "R1"), ("R2图像文件", "R2")):
            p = r.get(key, "")
            if not isinstance(p, str) or not p or pd.isna(p):
                continue
            nrrd = os.path.join(ROOT, p)
            if not os.path.exists(nrrd):
                continue
            size, sp = nrrd_geometry(nrrd)
            stem = os.path.splitext(os.path.basename(p))[0]
            m = re.match(r"^(\d+)\s+", stem)
            want = int(m.group(1)) if m else None
            cands = find_series(case_dir, nrrd, want, size, sp)
            ok = [c for c in cands if c["几何一致"]]
            pool = ok or cands
            if len(pool) == 1:
                c = pool[0]
                rec[f"{tag}检查号"] = c["检查号"]
                rec[f"{tag}系列"] = c["系列目录"]
                rec[f"{tag}厂商"] = c["厂商"]
                rec[f"{tag}机型"] = c["机型"]
                rec[f"{tag}场强"] = c["场强"]
                rec[f"{tag}行"] = c["行"]
                rec[f"{tag}列"] = c["列"]
                rec[f"{tag}面内间距"] = c["面内间距"]
                rec[f"{tag}层厚"] = c["层厚"]
                rec[f"{tag}层数"] = c["层数"]
                rec[f"{tag}匹配"] = "系列号+几何" if want is not None else "纯几何"
                rec[f"{tag}几何一致"] = c["几何一致"]
            elif len(pool) == 0:
                rec[f"{tag}匹配"] = "无"
                rec[f"{tag}备注"] = ";".join(c["不匹配原因"] for c in cands[:3]) or "无候选系列"
            else:
                rec[f"{tag}匹配"] = "多候选"
                rec[f"{tag}备注"] = f"{len(pool)} 个候选系列"
        rows.append(rec)

    out = pd.DataFrame(rows)
    out_path = os.path.join(ROOT, "output", "scanner_map.csv")
    # Do not replace a valid mapping with a zero-mapping placeholder when the
    # raw DICOM volume is temporarily unavailable (for example, an unmounted
    # network drive).  The manifest and existing mapping remain usable for
    # NRRD-based processing and can be refreshed when the source is mounted.
    mapped = int(out["R1厂商"].notna().sum()) if "R1厂商" in out.columns else 0
    if mapped == 0 and os.path.exists(out_path):
        try:
            old = pd.read_csv(out_path, encoding="utf-8-sig", dtype=str)
            old_mapped = int(old["R1厂商"].notna().sum()) if "R1厂商" in old.columns else 0
            if old_mapped > 0:
                print(f"原始DICOM不可用，未覆盖已有 scanner_map.csv（保留 {old_mapped} 个R1映射）")
                return
        except Exception:
            pass
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    out.to_csv(out_path, index=False, encoding="utf-8-sig")

    # 汇总
    print(f"总病例 {len(out)}，映射成功 "
          f"{(out.get('R1厂商', pd.Series(dtype=str)).notna()).sum()}")
    if "R1厂商" in out:
        g = out.groupby(["R1厂商", "R1机型", "R1场强"]).size().reset_index(name="例数")
        print(g.to_string(index=False))
        if "R2厂商" in out:
            ok_r2 = out["R2厂商"].notna().sum()
            same = ((out["R2厂商"] == out["R1厂商"]) & out["R2厂商"].notna()).sum()
            print(f"R2 映射 {ok_r2} 例，其中与 R1 同厂商 {same} 例")
        no = out[out.get("R1厂商", pd.Series(dtype=str)).isna() if "R1厂商" in out else True]
        if len(no):
            print("--- 未映射病例 ---")
            print(no[["影像号", "序列名", "状态"] if "状态" in no else ["影像号", "序列名"]]
                  .head(20).to_string(index=False))
    print("输出:", out_path)


if __name__ == "__main__":
    main()
