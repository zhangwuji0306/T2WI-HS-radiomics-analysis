"""Central cohort split and fail-closed data-access helpers.

The three public readers deliberately separate technical A, A outcome, and B
validation access.  Default CSV/XLSX reads are row-streamed and filtered by an
already-authorized identifier allow-list before a pandas frame is created.
"""
from __future__ import annotations

import csv
import os
import sys
from typing import Iterable, Optional, Set

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
FEATURE_ROOT = os.path.dirname(HERE)
PROJECT_ROOT = os.path.dirname(FEATURE_ROOT)
HABITAT_ROOT = os.path.join(PROJECT_ROOT, "habitat_analysis")
HABITAT_SCRIPTS = os.path.join(HABITAT_ROOT, "scripts")
if HABITAT_SCRIPTS not in sys.path:
    sys.path.insert(0, HABITAT_SCRIPTS)
from freeze_lock import validate_freeze_lock  # noqa: E402

PROGNOSIS_ROOT = os.path.join(PROJECT_ROOT, "prognosis_analysis")
PROGNOSIS_SCRIPTS = os.path.join(PROGNOSIS_ROOT, "scripts")
if PROGNOSIS_SCRIPTS not in sys.path:
    sys.path.insert(0, PROGNOSIS_SCRIPTS)
from model_freeze_lock import validate_model_freeze_lock  # noqa: E402

FREEZE_LOCK = os.path.join(HABITAT_ROOT, "freeze_lock.json")
# Kept as a compatibility name for callers that patch the old setting.  It is
# deliberately not consulted for authorization.
B_UNLOCK_LOCK = os.path.join(HABITAT_ROOT, "b_validation_unlock.json")
MODEL_FREEZE_LOCK = os.path.join(PROGNOSIS_ROOT, "model_freeze_lock.json")


def resolve_cohort_membership(manifest, scanner):
    """Assign A/B using the single project-wide scanner rule."""
    manifest = manifest.copy()
    scanner = scanner.copy()
    manifest["影像号"] = manifest["影像号"].astype(str).str.strip()
    scanner["影像号"] = scanner["影像号"].astype(str).str.strip()
    if manifest["影像号"].eq("").any() or scanner["影像号"].eq("").any():
        raise AssertionError("manifest/scanner identifiers must be nonempty")
    if manifest["影像号"].duplicated().any() or scanner["影像号"].duplicated().any():
        raise AssertionError("manifest/scanner identifiers must be unique")
    fields = ["影像号", "R1厂商", "R1机型", "R1场强"]
    merged = manifest.merge(scanner[fields], on="影像号", how="left",
                            validate="one_to_one", indicator=True)
    target = merged["排除"].fillna("0").ne("1") if "排除" in merged else pd.Series(True, index=merged.index)
    missing = merged.loc[target & merged["_merge"].ne("both"), "影像号"].tolist()
    if missing:
        raise AssertionError("target cases missing scanner mapping: %s" % missing[:5])
    field = pd.to_numeric(merged["R1场强"], errors="coerce")
    is_a = ((merged["R1厂商"] == "GE MEDICAL SYSTEMS") &
            (merged["R1机型"] == "DISCOVERY MR750") &
            (field.round(1) == 3.0))
    merged["split"] = "B"
    merged.loc[is_a, "split"] = "A"
    return merged.drop(columns=["_merge"])


def add_split(manifest, scanner):
    return resolve_cohort_membership(manifest, scanner)


def require_b_unlock():
    """Require both locks; the legacy B unlock file has no authority."""
    validate_freeze_lock(FREEZE_LOCK)
    return validate_model_freeze_lock(MODEL_FREEZE_LOCK)


def require_a_outcome_unlock():
    """Require the first-stage technical lock before A clinical/outcome reads."""
    return validate_freeze_lock(FREEZE_LOCK)


def _normalize_allowlist(allowed_ids: Optional[Iterable]) -> Optional[Set[str]]:
    if allowed_ids is None:
        return None
    if isinstance(allowed_ids, str):
        values = [allowed_ids]
    else:
        values = list(allowed_ids)
    normalized = {str(value).strip() for value in values}
    if "" in normalized:
        raise ValueError("allowed_ids must not contain an empty identifier")
    return normalized


def _apply_dtype(frame: pd.DataFrame, dtype) -> pd.DataFrame:
    if dtype is None:
        return frame
    if isinstance(dtype, dict):
        for column, target in dtype.items():
            if column in frame.columns:
                frame[column] = frame[column].astype(target)
        return frame
    return frame.astype(dtype)


def _stream_csv(path, allowed_ids: Set[str], id_column: str, *args, **kwargs):
    encoding = kwargs.pop("encoding", "utf-8-sig")
    dtype = kwargs.pop("dtype", None)
    usecols = kwargs.pop("usecols", None)
    delimiter = kwargs.pop("delimiter", ",")
    if args or kwargs:
        raise ValueError("unsupported options for authorized CSV reader: %s" %
                         sorted(kwargs))
    rows = []
    with open(path, "r", newline="", encoding=encoding) as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        if not reader.fieldnames or id_column not in reader.fieldnames:
            raise ValueError("%s lacks identifier column %s" % (path, id_column))
        columns = list(reader.fieldnames)
        if usecols is not None:
            columns = [column for column in columns if column in set(usecols)]
            if id_column not in columns:
                columns.insert(0, id_column)
        for row in reader:
            identifier = str(row.get(id_column, "")).strip()
            if identifier in allowed_ids:
                rows.append({column: row.get(column) for column in columns})
    return _apply_dtype(pd.DataFrame(rows, columns=columns), dtype)


def _stream_excel(path, allowed_ids: Set[str], id_column: str, *args, **kwargs):
    try:
        from openpyxl import load_workbook
    except ImportError as exc:
        raise RuntimeError("openpyxl is required for authorized XLSX reads") from exc
    if args:
        raise ValueError("positional options are unsupported for authorized XLSX reader")
    dtype = kwargs.pop("dtype", None)
    sheet_name = kwargs.pop("sheet_name", 0)
    if kwargs:
        raise ValueError("unsupported options for authorized XLSX reader: %s" %
                         sorted(kwargs))
    if isinstance(sheet_name, (list, tuple)):
        raise ValueError("authorized XLSX reader accepts one sheet only")
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        if isinstance(sheet_name, int):
            worksheet = workbook.worksheets[sheet_name]
        else:
            worksheet = workbook[sheet_name]
        rows = worksheet.iter_rows(values_only=True)
        try:
            header = [str(value).strip() if value is not None else ""
                      for value in next(rows)]
        except StopIteration:
            raise ValueError("authorized XLSX sheet is empty: %s" % path)
        if id_column not in header:
            raise ValueError("%s lacks identifier column %s" % (path, id_column))
        output = []
        for values in rows:
            row = dict(zip(header, values))
            identifier = str(row.get(id_column, "")).strip()
            if identifier in allowed_ids:
                output.append(row)
        return _apply_dtype(pd.DataFrame(output, columns=header), dtype)
    finally:
        workbook.close()


def _authorized_read(path, reader, allowed_ids, id_column, allow_full,
                     *args, **kwargs):
    allowlist = _normalize_allowlist(allowed_ids)
    if reader is not None:
        # Injectable readers are retained for tests and connector adapters.
        # Production callers use the default streaming path below so the
        # allow-list is applied before any patient row enters pandas.
        return reader(path, *args, **kwargs)
    if allowlist is None:
        if not allow_full:
            raise RuntimeError("authorized read requires an identifier allow-list")
        suffix = os.path.splitext(str(path))[1].lower()
        if suffix == ".csv":
            return pd.read_csv(path, *args, **kwargs)
        if suffix in (".xlsx", ".xlsm"):
            return pd.read_excel(path, *args, **kwargs)
        raise ValueError("unsupported declared technical format: %s" % suffix)
    suffix = os.path.splitext(str(path))[1].lower()
    if suffix in (".csv", ".tsv"):
        if suffix == ".tsv" and "delimiter" not in kwargs:
            kwargs["delimiter"] = "\t"
        return _stream_csv(path, allowlist, id_column, *args, **kwargs)
    if suffix in (".xlsx", ".xlsm"):
        return _stream_excel(path, allowlist, id_column, *args, **kwargs)
    raise ValueError("unsupported authorized data format: %s" % suffix)


def read_technical_A(path, reader=None, allowed_ids=None, id_column="影像号",
                     allow_full=False, *args, **kwargs):
    """Read outcome-blind technical A data without a lock.

    ``allowed_ids`` is required for a raw source that may contain A and B.
    A declared A-only technical artifact may be read through an injected
    reader or an explicit allow-list.
    """
    return _authorized_read(path, reader, allowed_ids, id_column, allow_full,
                            *args, **kwargs)


def read_A_outcomes(path, reader=None, allowed_ids=None, id_column="影像号",
                    *args, **kwargs):
    """Validate the first lock, then read only authorized A clinical/outcome rows."""
    require_a_outcome_unlock()
    return _authorized_read(path, reader, allowed_ids, id_column, False,
                            *args, **kwargs)


def read_B_validation(path, reader=None, allowed_ids=None, id_column="影像号",
                      *args, **kwargs):
    """Validate the model freeze, then read only authorized B validation rows."""
    require_b_unlock()
    return _authorized_read(path, reader, allowed_ids, id_column, False,
                            *args, **kwargs)


# Compatibility aliases are intentionally non-authorizing; callers should use
# the explicit three-reader API above.
read_technical_data = read_technical_A


def read_a_outcome(path, reader, *args, **kwargs):
    return read_A_outcomes(path, reader=reader, *args, **kwargs)


def read_b_data(path, reader, *args, **kwargs):
    return read_B_validation(path, reader=reader, *args, **kwargs)


def read_b_csv(path, *args, **kwargs):
    reader = kwargs.pop("reader", None)
    return read_B_validation(path, reader=reader, *args, **kwargs)


def read_b_excel(path, *args, **kwargs):
    reader = kwargs.pop("reader", None)
    return read_B_validation(path, reader=reader, *args, **kwargs)


def select_split(frame, split):
    if split not in ("A", "B", "all"):
        raise ValueError("split must be A, B, or all")
    if split in ("B", "all"):
        require_b_unlock()
    return frame.copy() if split == "all" else frame[frame["split"] == split].copy()
