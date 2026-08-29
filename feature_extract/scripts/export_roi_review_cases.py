# -*- coding: utf-8 -*-
"""Select paired-reader QC cases and export original-image ROI screenshots.

Selection rule
--------------
1. Four cases in which R1 and R2 used inconsistent image series.
2. Among the remaining series-consistent cases, the two lowest and two
   highest 3-D tumour Dice scores.

The R2 tumour mask is resampled to the original R1 mask grid with nearest-
neighbour interpolation before Dice calculation. Screenshots are made from
the original NRRD images and multilabel masks, not from preprocessed images.
"""
from __future__ import annotations

import argparse
import csv
import math
import os
import re
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import SimpleITK as sitk  # noqa: E402


# Keep the invocation path instead of resolving the radiomics26 junction back
# to its Chinese target; SimpleITK 2.2.1 on this Windows environment cannot
# reliably open NRRD files through the Chinese path.
FEATURE_ROOT = Path(os.path.abspath(__file__)).parents[1]
DEFAULT_MANIFEST = FEATURE_ROOT / "output" / "manifest.csv"
DEFAULT_OUT = FEATURE_ROOT / "output" / "roi_review_cases"

TISSUES = {
    "t": {"label": "肿瘤", "color": "#ff3b30"},
    "f": {"label": "脂肪", "color": "#ffd60a"},
    "m": {"label": "肌肉", "color": "#00d5ff"},
}
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


def resolve_project_path(value: str) -> Path:
    """Resolve a manifest path (stored relative to feature_extract)."""
    return FEATURE_ROOT / Path(str(value).replace("\\", os.sep))


def display_sequence_name(value: str) -> str:
    return Path(str(value).replace("\\", "/")).stem


def sequence_key(value: str) -> str:
    """Remove file-copy suffixes such as _1 without erasing series numbers."""
    name = display_sequence_name(value)
    name = re.sub(r"_\d+$", "", name)
    name = re.sub(r"\s+", " ", name).strip().lower()
    return name


def close_tuple(a: Iterable[float], b: Iterable[float], atol: float = 1e-3) -> bool:
    return bool(np.allclose(tuple(a), tuple(b), rtol=0.0, atol=atol))


def geometry_same(a: sitk.Image, b: sitk.Image) -> bool:
    return (
        a.GetSize() == b.GetSize()
        and close_tuple(a.GetSpacing(), b.GetSpacing())
        and close_tuple(a.GetOrigin(), b.GetOrigin())
        and close_tuple(a.GetDirection(), b.GetDirection())
    )


def image_agreement(a: sitk.Image, b: sitk.Image) -> Tuple[float, float]:
    """Return Pearson correlation and normalized MAE when grids match."""
    if not geometry_same(a, b):
        return float("nan"), float("nan")
    x = sitk.GetArrayViewFromImage(a).astype(np.float64).ravel()
    y = sitk.GetArrayViewFromImage(b).astype(np.float64).ravel()
    finite = np.isfinite(x) & np.isfinite(y)
    if finite.sum() < 2:
        return float("nan"), float("nan")
    x, y = x[finite], y[finite]
    sx, sy = float(x.std()), float(y.std())
    corr = float(np.corrcoef(x, y)[0, 1]) if sx > 0 and sy > 0 else float("nan")
    scale = max(float(np.percentile(x, 99) - np.percentile(x, 1)), 1e-12)
    nmae = float(np.mean(np.abs(x - y)) / scale)
    return corr, nmae


def dice_on_r1_grid(mask1: sitk.Image, mask2: sitk.Image) -> Tuple[float, int, int, int]:
    r2_on_r1 = sitk.Resample(
        sitk.Cast(mask2 == 1, sitk.sitkUInt8),
        mask1,
        sitk.Transform(),
        sitk.sitkNearestNeighbor,
        0,
        sitk.sitkUInt8,
    )
    a = sitk.GetArrayViewFromImage(mask1) == 1
    b = sitk.GetArrayViewFromImage(r2_on_r1) == 1
    n1, n2 = int(a.sum()), int(b.sum())
    inter = int(np.logical_and(a, b).sum())
    denom = n1 + n2
    return (2.0 * inter / denom if denom else float("nan"), n1, n2, inter)


def mask_aligned_image(preferred_path: Path, mask: sitk.Image) -> Tuple[Path, sitk.Image, bool]:
    """Use the manifest image unless another image is the mask's actual grid.

    A paired-reader folder can contain more than one series, while the
    current manifest points to the image that is not referenced by the saved
    labelmap. For clinical ROI review, the screenshot must use the image on
    which the ROI was actually drawn; the discrepancy remains in the audit.
    """
    preferred = sitk.ReadImage(str(preferred_path))
    if geometry_same(preferred, mask):
        return preferred_path, preferred, False
    candidates = []
    for path in sorted(preferred_path.parent.glob("*.nrrd")):
        if "label" in path.name.lower() or path == preferred_path:
            continue
        image = sitk.ReadImage(str(path))
        if geometry_same(image, mask):
            candidates.append((path, image))
    if len(candidates) != 1:
        raise RuntimeError(
            f"{preferred_path.parent}: preferred image does not match mask and "
            f"found {len(candidates)} alternative grid matches"
        )
    return candidates[0][0], candidates[0][1], True


def assess_pair(row: pd.Series) -> Dict[str, object]:
    r1_image_path = resolve_project_path(row["图像文件"])
    r2_image_path = resolve_project_path(row["R2图像文件"])
    r1_mask_path = resolve_project_path(row["掩膜文件"])
    r2_mask_path = resolve_project_path(row["R2掩膜文件"])
    mask1 = sitk.ReadImage(str(r1_mask_path))
    mask2 = sitk.ReadImage(str(r2_mask_path))
    img1 = sitk.ReadImage(str(r1_image_path))
    img2 = sitk.ReadImage(str(r2_image_path))
    shot1_path, _, shot1_replaced = mask_aligned_image(r1_image_path, mask1)
    shot2_path, _, shot2_replaced = mask_aligned_image(r2_image_path, mask2)

    geom_equal = geometry_same(img1, img2)
    corr, nmae = image_agreement(img1, img2)
    r1_seq = display_sequence_name(row["图像文件"])
    r2_seq = display_sequence_name(row["R2图像文件"])
    key_equal = sequence_key(row["图像文件"]) == sequence_key(row["R2图像文件"])

    # A copied NRRD of the same source series should have the same normalized
    # name and grid, and effectively identical pixel values. This avoids
    # treating Slicer copy suffixes (_1, _2, ...) as different acquisitions.
    pixel_equal = bool(math.isfinite(corr) and corr >= 0.999999 and nmae <= 1e-6)
    series_consistent = bool(key_equal and geom_equal and pixel_equal)
    reasons: List[str] = []
    if not key_equal:
        reasons.append("标准化序列名不同")
    if not geom_equal:
        reasons.append("图像网格不同")
    if geom_equal and not pixel_equal:
        reasons.append("同网格但像素内容不同")
    if not reasons:
        reasons.append("同一序列")

    dice, n1, n2, inter = dice_on_r1_grid(mask1, mask2)
    return {
        "影像号": str(row["影像号"]),
        "R1序列": r1_seq,
        "R2序列": r2_seq,
        "标准化序列名一致": int(key_equal),
        "原始图像网格一致": int(geom_equal),
        "原始图像像素相关": corr,
        "原始图像归一化MAE": nmae,
        "序列一致": int(series_consistent),
        "判定依据": "；".join(reasons),
        "肿瘤Dice": dice,
        "R1肿瘤体素": n1,
        "R2映射至R1网格肿瘤体素": n2,
        "交集体素": inter,
        "R1图像路径": str(r1_image_path),
        "R2图像路径": str(r2_image_path),
        "R1截图图像路径": str(shot1_path),
        "R2截图图像路径": str(shot2_path),
        "R1截图序列": display_sequence_name(str(shot1_path)),
        "R2截图序列": display_sequence_name(str(shot2_path)),
        "R1截图改用掩膜匹配图像": int(shot1_replaced),
        "R2截图改用掩膜匹配图像": int(shot2_replaced),
        "R1掩膜路径": str(r1_mask_path),
        "R2掩膜路径": str(r2_mask_path),
        "R2肌肉标签": int(float(row["R2肌肉标签"])),
    }


def choose_cases(audit: pd.DataFrame) -> pd.DataFrame:
    mismatch = audit[audit["序列一致"] == 0].copy()
    if len(mismatch) < 4:
        raise RuntimeError(f"仅识别到 {len(mismatch)} 例序列不一致病例，少于预设 4 例")
    if len(mismatch) > 4:
        # Prefer explicit name differences, then geometry differences, then
        # lower pixel agreement; patient ID is the deterministic tie breaker.
        mismatch["_name_diff"] = 1 - mismatch["标准化序列名一致"].astype(int)
        mismatch["_geom_diff"] = 1 - mismatch["原始图像网格一致"].astype(int)
        mismatch["_corr_rank"] = mismatch["原始图像像素相关"].fillna(-1.0)
        mismatch = mismatch.sort_values(
            ["_name_diff", "_geom_diff", "_corr_rank", "影像号"],
            ascending=[False, False, True, True],
        ).head(4)
    mismatch = mismatch.copy()
    mismatch["选例类别"] = "R1/R2序列不一致"

    same = audit[audit["序列一致"] == 1].sort_values(["肿瘤Dice", "影像号"])
    if len(same) < 4:
        raise RuntimeError(f"仅识别到 {len(same)} 例序列一致病例，无法选择高低各 2 例")
    low = same.head(2).copy()
    high = same.tail(2).sort_values(["肿瘤Dice", "影像号"], ascending=[False, True]).copy()
    low["选例类别"] = "同序列肿瘤Dice最低"
    high["选例类别"] = "同序列肿瘤Dice最高"
    selected = pd.concat([mismatch, low, high], ignore_index=True)
    if selected["影像号"].duplicated().any() or len(selected) != 8:
        raise RuntimeError("选例结果不是 8 个互不重复病例")
    return selected


def robust_window(image_array: np.ndarray) -> Tuple[float, float]:
    finite = image_array[np.isfinite(image_array)]
    if finite.size == 0:
        return 0.0, 1.0
    nonzero = finite[finite != 0]
    sample = nonzero if nonzero.size >= 100 else finite
    lo, hi = np.percentile(sample, [1.0, 99.5])
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        lo, hi = float(sample.min()), float(sample.max())
    if hi <= lo:
        hi = lo + 1.0
    return float(lo), float(hi)


def largest_slice(mask_array: np.ndarray, label: int) -> Tuple[int, int]:
    areas = (mask_array == label).sum(axis=(1, 2))
    if int(areas.max()) == 0:
        raise ValueError(f"标签 {label} 无体素")
    z = int(np.argmax(areas))
    return z, int(areas[z])


def export_reader(
    pid: str,
    reader: str,
    image_path: str,
    mask_path: str,
    mappings: Dict[str, int],
    sequence: str,
    out_dir: Path,
) -> List[Dict[str, object]]:
    """Export one image per unique maximum-area slice for this reader.

    If t/f/m maxima occur on one, two, or three unique slices, this function
    exports exactly one, two, or three screenshots, respectively. Every
    screenshot overlays all ROI classes present on that slice. The filename
    suffix records only the class(es) whose maximum occurs on that slice.
    """
    image = sitk.ReadImage(image_path)
    mask = sitk.ReadImage(mask_path)
    if not geometry_same(image, mask):
        mask = sitk.Resample(mask, image, sitk.Transform(), sitk.sitkNearestNeighbor, 0, mask.GetPixelID())
    a = sitk.GetArrayFromImage(image).astype(np.float32)
    m = sitk.GetArrayFromImage(mask)
    lo, hi = robust_window(a)
    spacing = image.GetSpacing()

    maxima: Dict[str, Tuple[int, int]] = {}
    by_slice: Dict[int, List[str]] = {}
    for tissue in ("t", "f", "m"):
        z, area_px = largest_slice(m, mappings[tissue])
        maxima[tissue] = (z, area_px)
        by_slice.setdefault(z, []).append(tissue)

    rows: List[Dict[str, object]] = []
    tissue_order = {"t": 0, "f": 1, "m": 2}
    grouped = sorted(by_slice.items(), key=lambda item: min(tissue_order[x] for x in item[1]))
    for z, max_tissues in grouped:
        max_tissues = sorted(max_tissues, key=lambda x: tissue_order[x])
        suffix = "_".join(max_tissues)
        visible: List[str] = []
        slice_areas: Dict[str, int] = {}

        fig, ax = plt.subplots(figsize=(8, 8), dpi=150)
        ax.imshow(a[z], cmap="gray", vmin=lo, vmax=hi, interpolation="nearest")
        for tissue in ("t", "f", "m"):
            roi = m[z] == mappings[tissue]
            area = int(roi.sum())
            slice_areas[tissue] = area
            if area > 0:
                visible.append(tissue)
                ax.contour(
                    roi.astype(np.uint8),
                    levels=[0.5],
                    colors=[TISSUES[tissue]["color"]],
                    linewidths=1.8,
                )
        legend = [
            Line2D([0], [0], color=TISSUES[t]["color"], lw=2, label=f"{t}: {TISSUES[t]['label']}")
            for t in visible
        ]
        if legend:
            ax.legend(
                handles=legend,
                loc="lower right",
                framealpha=0.65,
                facecolor="black",
                edgecolor="white",
                labelcolor="white",
                fontsize=8,
            )
        ax.set_title(
            f"{pid} | {reader} | maximum: {suffix} | slice {z + 1}/{a.shape[0]}\n{sequence}",
            fontsize=10,
            color="white",
            pad=8,
        )
        ax.set_axis_off()
        fig.patch.set_facecolor("black")
        fig.tight_layout(pad=0.25)
        out_path = out_dir / f"{pid}_{reader}_{suffix}.png"
        fig.savefig(str(out_path), dpi=150, facecolor="black", bbox_inches="tight", pad_inches=0.03)
        plt.close(fig)
        px_to_mm2 = float(spacing[0]) * float(spacing[1])
        rows.append(
            {
                "影像号": pid,
                "读者": reader,
                "最大组织代码": suffix,
                "最大组织": "、".join(TISSUES[t]["label"] for t in max_tissues),
                "截图层面_从1计数": z + 1,
                "总层数": int(a.shape[0]),
                "该层可见ROI代码": "_".join(visible),
                "该层肿瘤像素": slice_areas["t"],
                "该层脂肪像素": slice_areas["f"],
                "该层肌肉像素": slice_areas["m"],
                "该层肿瘤面积mm2": slice_areas["t"] * px_to_mm2,
                "该层脂肪面积mm2": slice_areas["f"] * px_to_mm2,
                "该层肌肉面积mm2": slice_areas["m"] * px_to_mm2,
                "窗宽显示下限_p1": lo,
                "窗宽显示上限_p99.5": hi,
                "PNG": out_path.name,
            }
        )
    return rows


def write_report(selected: pd.DataFrame, shots: pd.DataFrame, out_dir: Path) -> Path:
    report = out_dir / "典型病例原图与ROI质量审阅.md"
    lines = [
        "# 典型病例原始图像与 ROI 质量审阅",
        "",
        "> 用途：供临床导师审阅原始 T2WI 序列选择及 R1/R2 ROI 勾画质量。截图均来自原始 NRRD 图像，未使用重采样、归一化、裁剪或 N4 处理后的图像。彩色线为相应 ROI 边界。",
        "",
        "## 1. 选例与计算口径",
        "",
        "- 先选 4 例 R1/R2 图像序列不一致病例；再在序列一致病例中分别选择肿瘤三维 Dice 最低 2 例和最高 2 例，三组互不重复。",
        "- 序列一致性综合标准化序列名、原始图像网格和像素内容判定；文件复制后缀（如 `_1`）不视为不同序列。",
        "- 肿瘤 Dice：将 R2 标签 1 掩膜按物理坐标用最近邻插值映射至 R1 原始掩膜网格后计算 `2|R1∩R2|/(|R1|+|R2|)`；未进行图像配准。",
        "- 对每位读者分别求肿瘤、脂肪、肌肉 ROI 的最大面积层面，再按唯一层号合并：三类最大层面若完全相同则导出 1 张，部分相同则导出 2 张，均不相同则导出 3 张。文件名后缀（如 `_t_f`）表示该层同时是哪些 ROI 的最大层面。",
        "- 每张截图均叠加该层面实际存在的全部三类 ROI：肿瘤红色、脂肪黄色、肌肉青色；文件名未列出的 ROI 只要在该层存在也会显示。R1 标签固定为 1=肿瘤、2=脂肪、3=肌肉；R2 的脂肪/肌肉标签依据项目清单中的逐例判别结果映射。",
        "- 显示窗仅用于 PNG 可视化：按该三维原图非零有限体素的第 1–99.5 百分位显示，不改变源数据。",
        "",
        "## 2. 入选病例总览",
        "",
        "| 类别 | 影像号 | R1 序列 | R2 序列 | 肿瘤 Dice | 序列判定依据 |",
        "|---|---:|---|---|---:|---|",
    ]
    for _, r in selected.iterrows():
        lines.append(
            f"| {r['选例类别']} | {r['影像号']} | {r['R1序列']} | {r['R2序列']} | "
            f"{float(r['肿瘤Dice']):.4f} | {r['判定依据']} |"
        )

    lines += ["", "## 3. 逐例截图", ""]
    for _, r in selected.iterrows():
        pid = str(r["影像号"])
        lines += [
            f"### {pid}（{r['选例类别']}）",
            "",
            f"- R1 序列：`{r['R1序列']}`",
            f"- R2 序列：`{r['R2序列']}`",
            f"- 肿瘤 Dice：**{float(r['肿瘤Dice']):.4f}**",
            f"- 序列判定：{r['判定依据']}",
            "",
        ]
        if int(r["R1截图改用掩膜匹配图像"]) or int(r["R2截图改用掩膜匹配图像"]):
            lines += [
                "> **图像—ROI 关联异常：** 当前清单指向的 R2 图像与 R2 掩膜网格不一致。为显示实际 ROI，R2 截图改用目录内与掩膜网格唯一匹配的 "
                f"`{r['R2截图序列']}`；该替代仅用于质控展示，不修订当前分析清单。",
                "",
            ]
        for reader in ("R1", "R2"):
            sub = shots[(shots["影像号"].astype(str) == pid) & (shots["读者"] == reader)]
            lines += [f"#### {reader}", "", "| 最大项 | 层面 | 截图（含该层全部 ROI） |", "|---|---:|---|"]
            for _, shot in sub.iterrows():
                lines.append(
                    f"| `{shot['最大组织代码']}`（{shot['最大组织']}） | "
                    f"{int(shot['截图层面_从1计数'])}/{int(shot['总层数'])} | "
                    f"![{pid} {reader} {shot['最大组织代码']}]({shot['PNG']}) |"
                )
            lines.append("")

    lines += [
        "## 4. 审阅时建议记录",
        "",
        "请导师逐例记录：（1）R1/R2 序列是否为目标 T2WI 斜轴位；（2）肿瘤边界是否包含腔内容物、正常肠壁或瘤周组织；（3）脂肪与肌肉 ROI 是否受部分容积、血管、骨、皮下组织或伪影污染；（4）是否需要重新选序列或重新勾画。",
        "",
        "## 5. 可复算附件",
        "",
        "- `paired_reader_dice_audit.csv`：全部双读者病例的序列判定、图像一致性与 Dice。",
        "- `selected_cases.csv`：本次 8 例入选清单。",
        f"- `screenshot_metadata.csv`：本次 {len(shots)} 张截图的共享最大项、层号、该层三类 ROI 面积和显示窗。",
        "",
    ]
    report.write_text("\n".join(lines), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="选择双读者典型病例并导出原图 ROI 截图")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT))
    parser.add_argument("--audit-only", action="store_true", help="仅计算全体配对审计表，不选例或截图")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = pd.read_csv(args.manifest, dtype=str, encoding="utf-8-sig")
    pairs = manifest[manifest["是否双读者"] == "1"].copy()
    audit_rows = [assess_pair(row) for _, row in pairs.iterrows()]
    audit = pd.DataFrame(audit_rows).sort_values("影像号")
    audit_path = out_dir / "paired_reader_dice_audit.csv"
    audit.to_csv(audit_path, index=False, encoding="utf-8-sig", float_format="%.8g")
    print(audit[["影像号", "R1序列", "R2序列", "序列一致", "判定依据", "肿瘤Dice"]].to_string(index=False))
    print(f"\n序列不一致: {int((audit['序列一致'] == 0).sum())} / {len(audit)}")
    print("审计表:", audit_path)
    if args.audit_only:
        return

    selected = choose_cases(audit)
    selected_path = out_dir / "selected_cases.csv"
    selected.to_csv(selected_path, index=False, encoding="utf-8-sig", float_format="%.8g")

    shot_rows: List[Dict[str, object]] = []
    for _, r in selected.iterrows():
        pid = str(r["影像号"])
        r2_muscle = int(r["R2肌肉标签"])
        r2_fat = 3 if r2_muscle == 2 else 2
        mappings = {
            "R1": {"t": 1, "f": 2, "m": 3},
            "R2": {"t": 1, "f": r2_fat, "m": r2_muscle},
        }
        for reader in ("R1", "R2"):
            image_path = str(r[f"{reader}截图图像路径"])
            mask_path = str(r[f"{reader}掩膜路径"])
            sequence = str(r[f"{reader}截图序列"])
            shot_rows.extend(
                export_reader(
                    pid,
                    reader,
                    image_path,
                    mask_path,
                    mappings[reader],
                    sequence,
                    out_dir,
                )
            )
    shots = pd.DataFrame(shot_rows)
    shots.to_csv(out_dir / "screenshot_metadata.csv", index=False, encoding="utf-8-sig", float_format="%.8g")
    report = write_report(selected, shots, out_dir)
    print("\n入选病例:")
    print(selected[["选例类别", "影像号", "R1序列", "R2序列", "肿瘤Dice"]].to_string(index=False))
    print(f"PNG: {len(shots)} 张")
    print("报告:", report)


if __name__ == "__main__":
    main()
