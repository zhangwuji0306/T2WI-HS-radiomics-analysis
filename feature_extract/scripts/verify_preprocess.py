"""校验预处理输出：间距/网格、掩膜有效性、标准化统计与 R2 对齐结果。

标准化模式由图像统计自推断（z-score 图像肿瘤 ROI 均值≈0、标准差≈1 为构造性特征；
muscle 模式肿瘤 ROI 均值≈肿瘤/肌肉信号比，无固定目标），不依赖共享指标 CSV。

用法: python scripts/verify_preprocess.py --ids ID1,ID2,... [--prep-dir 输出目录]
"""
from __future__ import annotations

import argparse
import os

import numpy as np
import SimpleITK as sitk

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = [1.0, 1.0, 2.0]
EPS = 1e-6


def geom(img: sitk.Image) -> dict:
    return {"size": list(img.GetSize()), "spacing": list(img.GetSpacing()),
            "origin": list(img.GetOrigin()), "direction": list(img.GetDirection())}


def infer_mode(mu: float, sd: float) -> str:
    return "zscore" if (abs(mu) < 1e-3 and abs(sd - 1.0) < 1e-2) else "muscle"


def main() -> None:
    ap = argparse.ArgumentParser(description="校验预处理输出")
    ap.add_argument("--ids", required=True, help="逗号分隔的影像号")
    ap.add_argument("--prep-dir", default="output/preprocessed",
                    help="预处理输出目录（相对项目根）")
    args = ap.parse_args()
    ids = [x.strip() for x in args.ids.split(",") if x.strip()]
    prep = os.path.join(ROOT, args.prep_dir)

    fails: list[str] = []
    for pid in ids:
        d = os.path.join(prep, pid)
        lines = [f"== {pid} =="]
        img1 = sitk.ReadImage(os.path.join(d, "R1_image.nrrd"))
        g1 = geom(img1)
        sp1 = all(abs(a - b) < EPS for a, b in zip(g1["spacing"], TARGET))
        f32_1 = img1.GetPixelID() == sitk.sitkFloat32
        a1 = sitk.GetArrayFromImage(sitk.ReadImage(os.path.join(d, "R1_mask.nrrd")))
        n1 = int((a1 == 1).sum())
        z1 = sitk.GetArrayFromImage(img1)
        mu1, sd1 = float(z1[a1 == 1].mean()), float(z1[a1 == 1].std())
        mode1 = infer_mode(mu1, sd1)
        lines.append(f"R1: 间距={['%.3f' % s for s in g1['spacing']]} 网格OK={sp1} float32={f32_1} "
                     f"肿瘤体素={n1} 标准化={mode1}")
        lines.append(f"    肿瘤ROI均值={mu1:.4f} 标准差={sd1:.4f}"
                     f"（muscle 模式均值≈肿瘤/肌肉信号比，无固定目标）")
        lines.append(f"    方向={['%.4f' % x for x in g1['direction']]} 原点={['%.2f' % x for x in g1['origin']]}")
        ok1 = sp1 and f32_1 and n1 > 0
        if mode1 == "zscore":
            ok1 = ok1 and abs(mu1) < 1e-3 and abs(sd1 - 1.0) < 1e-2
        else:
            ok1 = ok1 and sd1 > 0 and np.isfinite(mu1) and np.isfinite(sd1) and abs(mu1) < 1e6
        if not ok1:
            fails.append(pid + " R1")
        r2p = os.path.join(d, "R2_image.nrrd")
        if os.path.exists(r2p):
            img2 = sitk.ReadImage(r2p)
            g2 = geom(img2)
            sp2 = all(abs(a - b) < EPS for a, b in zip(g2["spacing"], TARGET))
            f32_2 = img2.GetPixelID() == sitk.sitkFloat32
            a2 = sitk.GetArrayFromImage(sitk.ReadImage(os.path.join(d, "R2_mask.nrrd")))
            n2 = int((a2 == 1).sum())
            same = (g2["size"] == g1["size"]
                    and all(abs(a - b) < EPS for a, b in zip(g2["spacing"], g1["spacing"]))
                    and all(abs(a - b) < EPS for a, b in zip(g2["origin"], g1["origin"]))
                    and all(abs(a - b) < EPS for a, b in zip(g2["direction"], g1["direction"])))
            z2 = sitk.GetArrayFromImage(img2)
            mu2, sd2 = float(z2[a2 == 1].mean()), float(z2[a2 == 1].std())
            mode2 = infer_mode(mu2, sd2)
            ok2 = same and n2 > 0
            if mode2 == "zscore":
                ok2 = ok2 and abs(mu2) < 1e-3 and abs(sd2 - 1.0) < 1e-2
            else:
                ok2 = ok2 and sd2 > 0 and np.isfinite(mu2) and np.isfinite(sd2)
            lines.append(f"R2: 与R1网格一致={same} 间距OK={sp2} float32={f32_2} 肿瘤体素={n2} 标准化={mode2}")
            if not ok2:
                fails.append(pid + " R2")
        else:
            lines.append("R2: 无（单读者病例）")
        print("\n".join(lines))
    print("\n" + ("全部通过" if not fails else "失败项: " + ", ".join(fails)))


if __name__ == "__main__":
    main()
