"""Build outcome-blind A-set manifests and audit their identity."""
from __future__ import annotations

import argparse
import json
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
HAB = os.path.dirname(HERE)
ROOT = os.path.dirname(HAB)
FEAT = os.path.join(ROOT, "feature_extract")
MANIFEST = os.path.join(FEAT, "output", "manifest.csv")
SCANNER = os.path.join(FEAT, "output", "scanner_map.csv")
SCREEN = os.path.join(HAB, "output", "high_signal_eligibility_audit")
LENIENT = os.path.join(SCREEN, "lenient_screening_decisions.csv")
STRICT = os.path.join(SCREEN, "recommended_screening_decisions.csv")
OUT = os.path.join(HAB, "output", "technical_cohort_manifest")
OLD_A = os.path.join(HAB, "output", "feasibility_A_patient_balanced_post_slic_fix",
                     "case_diagnostics.csv")

sys.path.insert(0, HERE)
from freeze_lock import atomic_write_json, file_sha256, id_hash, utc_now  # noqa: E402
FEATURE_SCRIPTS = os.path.join(FEAT, "scripts")
if FEATURE_SCRIPTS not in sys.path:
    sys.path.insert(0, FEATURE_SCRIPTS)
from data_split_guard import resolve_cohort_membership  # noqa: E402


def normalized_ids(frame, column):
    if column not in frame.columns:
        raise AssertionError("missing identifier column: %s" % column)
    values = frame[column].astype(str).str.strip()
    if values.eq("").any() or values.duplicated().any():
        raise AssertionError("identifier column must be nonempty and unique: %s" % column)
    return values


def merge_manifest_scanner(manifest, scanner):
    return resolve_cohort_membership(manifest, scanner)


def selected_ids(path, pass_column):
    frame = pd.read_csv(path, encoding="utf-8-sig", dtype=str)
    frame["patient_id"] = normalized_ids(frame, "patient_id")
    if pass_column not in frame.columns:
        raise AssertionError("screening file missing %s" % pass_column)
    return set(frame.loc[pd.to_numeric(frame[pass_column], errors="coerce").eq(1),
                         "patient_id"])


def build_tables(manifest_path=MANIFEST, scanner_path=SCANNER,
                 lenient_path=LENIENT, strict_path=STRICT):
    manifest = pd.read_csv(manifest_path, encoding="utf-8-sig", dtype=str)
    scanner = pd.read_csv(scanner_path, encoding="utf-8-sig", dtype=str)
    merged = merge_manifest_scanner(manifest, scanner)
    if "排除" in merged:
        merged = merged[merged["排除"].fillna("0").astype(str) != "1"].copy()
    lenient_ids = selected_ids(lenient_path, "lenient_pass")
    strict_ids = selected_ids(strict_path, "recommended_pass")
    columns = ["影像号", "split", "R1厂商", "R1机型", "R1场强"]
    lenient = merged[(merged["split"] == "A") & merged["影像号"].isin(lenient_ids)][columns].copy()
    strict = merged[(merged["split"] == "A") & merged["影像号"].isin(strict_ids)][columns].copy()
    lenient["screening_rule"] = "lenient"
    strict["screening_rule"] = "strict"
    lenient = lenient.sort_values("影像号").reset_index(drop=True)
    strict = strict.sort_values("影像号").reset_index(drop=True)
    if not set(strict["影像号"]).issubset(set(lenient["影像号"])):
        raise AssertionError("strict A cohort is not a subset of lenient A cohort")
    return lenient, strict


def identity_audit(new_ids, old_path=OLD_A):
    if not os.path.exists(old_path):
        raise FileNotFoundError("post-SLIC A393 baseline is missing: %s" % old_path)
    old = pd.read_csv(old_path, encoding="utf-8-sig", dtype=str,
                      usecols=["影像号"])
    old_ids = set(old["影像号"].astype(str).str.strip())
    new_ids = set(str(value).strip() for value in new_ids)
    universe = sorted(old_ids | new_ids)
    detail = pd.DataFrame({"影像号": universe})
    detail["in_old_A393"] = detail["影像号"].isin(old_ids).astype(int)
    detail["in_new_A393"] = detail["影像号"].isin(new_ids).astype(int)
    detail["status"] = "intersection"
    detail.loc[(detail["in_old_A393"] == 1) & (detail["in_new_A393"] == 0), "status"] = "old_only"
    detail.loc[(detail["in_old_A393"] == 0) & (detail["in_new_A393"] == 1), "status"] = "new_only"
    summary = {
        "old_A393_n": len(old_ids), "new_A393_n": len(new_ids),
        "intersection_n": len(old_ids & new_ids),
        "old_only_n": len(old_ids - new_ids),
        "new_only_n": len(new_ids - old_ids),
        "symmetric_difference_n": len(old_ids ^ new_ids),
        "identity_audit_pass": int(len(old_ids ^ new_ids) == 0),
        "old_A393_id_hash": id_hash(old_ids), "new_A393_id_hash": id_hash(new_ids),
    }
    return detail, summary


def main():
    parser = argparse.ArgumentParser(description="构建纯技术A集清单并审计A393身份")
    parser.add_argument("--skip-identity-audit", action="store_true")
    args = parser.parse_args()
    os.makedirs(OUT, exist_ok=True)
    lenient, strict = build_tables()
    if len(lenient) != 393 or lenient["影像号"].nunique() != 393:
        raise RuntimeError("technical A lenient must contain exactly 393 unique cases")
    if len(strict) != 137 or strict["影像号"].nunique() != 137:
        raise RuntimeError("technical A strict must contain exactly 137 unique cases")
    lenient.to_csv(os.path.join(OUT, "cohort_A_lenient.csv"), index=False,
                   encoding="utf-8-sig")
    strict.to_csv(os.path.join(OUT, "cohort_A_strict.csv"), index=False,
                  encoding="utf-8-sig")
    summary = {
        "A_lenient_n": len(lenient), "A_strict_n": len(strict),
        "A137_subset_A393": int(set(strict["影像号"]).issubset(set(lenient["影像号"]))),
        "A393_id_hash": id_hash(lenient["影像号"]),
        "A137_id_hash": id_hash(strict["影像号"]),
        "outcome_columns_read": False, "B_data_read": False,
    }
    if not args.skip_identity_audit:
        detail, audit = identity_audit(lenient["影像号"])
        detail.to_csv(os.path.join(OUT, "A393_identity_audit.csv"), index=False,
                      encoding="utf-8-sig")
        summary.update(audit)
        lines = [
            "# A393身份一致性审计", "",
            "- old A393：%d；new A393：%d；intersection：%d。" %
            (audit["old_A393_n"], audit["new_A393_n"], audit["intersection_n"]),
            "- old-only：%d；new-only：%d；symmetric difference：%d。" %
            (audit["old_only_n"], audit["new_only_n"], audit["symmetric_difference_n"]),
            "- 判定：%s。" % ("PASS" if audit["identity_audit_pass"] else "FAIL；停止后续bootstrap"),
            "- outcome_columns_read=false；B_data_read=false。", "",
        ]
        with open(os.path.join(OUT, "A393_identity_audit.md"), "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines))
    atomic_write_json(os.path.join(OUT, "cohort_summary.json"), summary)
    provenance = {
        "created_at": utc_now(), "outcome_columns_read": False, "B_data_read": False,
        "inputs": {os.path.basename(path): {"path": os.path.relpath(path, ROOT),
                                             "sha256": file_sha256(path)}
                   for path in [MANIFEST, SCANNER, LENIENT, STRICT]},
    }
    atomic_write_json(os.path.join(OUT, "provenance.json"), provenance)
    if summary.get("identity_audit_pass", 1) != 1:
        raise SystemExit("A393 identity audit failed; post-SLIC results must be regenerated")
    print("technical A lenient=393; strict=137; identity audit=%s" %
          ("PASS" if summary.get("identity_audit_pass", 1) else "FAIL"))


if __name__ == "__main__":
    main()
