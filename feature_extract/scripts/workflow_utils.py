"""Shared provenance, geometry, and atomic-output helpers for the radiomics workflow."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional, Sequence, Set, Tuple

import pandas as pd


def stable_json_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def file_sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def git_commit(root: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-c", "safe.directory=" + os.path.abspath(root),
             "-C", root, "rev-parse", "HEAD"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            universal_newlines=True, check=False,
        )
        value = result.stdout.strip()
        return value if result.returncode == 0 and value else "unknown"
    except (OSError, ValueError):
        return "unknown"


def atomic_write_text(path: str, text: str, encoding: str = "utf-8") -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="." + os.path.basename(path) + ".",
                               suffix=".tmp", dir=os.path.dirname(os.path.abspath(path)))
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def atomic_write_json(path: str, value: Dict[str, Any]) -> None:
    atomic_write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def read_json_or_empty(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as handle:
            value = json.load(handle)
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def update_stage_metadata(path: str, stage: str,
                          payload: Dict[str, Any]) -> None:
    current = read_json_or_empty(path)
    stages = current.get("stages")
    if not isinstance(stages, dict):
        stages = {}
    stages[stage] = payload
    atomic_write_json(path, {"stages": stages})


def atomic_write_csv(frame: pd.DataFrame, path: str,
                     columns: Optional[Sequence[str]] = None) -> None:
    if columns is not None:
        frame = frame.reindex(columns=list(columns))
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="." + os.path.basename(path) + ".",
                               suffix=".tmp", dir=os.path.dirname(os.path.abspath(path)))
    os.close(fd)
    try:
        frame.to_csv(tmp, index=False, encoding="utf-8-sig")
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def read_csv_or_empty(path: str, columns: Optional[Sequence[str]] = None) -> pd.DataFrame:
    if not os.path.exists(path):
        return pd.DataFrame(columns=list(columns or []))
    try:
        return pd.read_csv(path, dtype=str)
    except (pd.errors.EmptyDataError, OSError, ValueError):
        return pd.DataFrame(columns=list(columns or []))


def frame_keys(frame: pd.DataFrame, key_cols: Sequence[str]) -> Set[Tuple[str, ...]]:
    if frame.empty or any(col not in frame.columns for col in key_cols):
        return set()
    return set(tuple(str(v) for v in row)
               for row in frame[list(key_cols)].itertuples(index=False, name=None))


def drop_keys(frame: pd.DataFrame, key_cols: Sequence[str],
              keys: Iterable[Tuple[str, ...]]) -> pd.DataFrame:
    key_set = set(keys)
    if frame.empty or not key_set or any(col not in frame.columns for col in key_cols):
        return frame.copy()
    keep = [tuple(str(v) for v in row) not in key_set
            for row in frame[list(key_cols)].itertuples(index=False, name=None)]
    return frame.loc[keep].copy()


def merge_rows(base: pd.DataFrame, new_rows: pd.DataFrame,
               key_cols: Sequence[str]) -> pd.DataFrame:
    if new_rows.empty:
        return base.copy()
    new_keys = frame_keys(new_rows, key_cols)
    kept = drop_keys(base, key_cols, new_keys)
    return pd.concat([kept, new_rows], ignore_index=True, sort=False)


def physical_points_inside_image(image: Any, points: Iterable[Sequence[float]]) -> bool:
    """Return whether every physical point lies inside an image''s continuous-index FOV."""
    size = image.GetSize()
    for point in points:
        index = image.TransformPhysicalPointToContinuousIndex(
            tuple(float(value) for value in point))
        if any(index[d] < -0.5 or index[d] > size[d] - 0.5 for d in range(len(size))):
            return False
    return True
