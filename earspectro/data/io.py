"""Dataset schema and loading.

One row = one ear spectrum. Required columns:

    subject_id, session_id, timestamp, glucose_ref, A_<wavelength_nm> ...

Spectral columns are named ``A_<nm>`` (absorbance, -log10(I/I0)) so the
wavelength axis can be recovered from the header. Everything else is metadata
kept for confounding / subgroup analysis and is NOT fed to models by default.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

TARGET_COL = "glucose_ref"
META_COLS = ["subject_id", "session_id", "timestamp", "timepoint", "repeat"]
_SPEC_RE = re.compile(r"^A_(\d+(?:\.\d+)?)$")


def spectral_columns(df: pd.DataFrame) -> list[str]:
    cols = [c for c in df.columns if _SPEC_RE.match(c)]
    return sorted(cols, key=lambda c: float(_SPEC_RE.match(c).group(1)))


def wavelengths_of(cols: list[str]) -> np.ndarray:
    return np.array([float(_SPEC_RE.match(c).group(1)) for c in cols])


def load_dataset(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if path.suffix == ".parquet":
        df = pd.read_parquet(path)
    else:
        df = pd.read_csv(path)
    missing = {"subject_id", "session_id", TARGET_COL} - set(df.columns)
    if missing:
        raise ValueError(f"{path}: missing required columns {sorted(missing)}")
    if not spectral_columns(df):
        raise ValueError(f"{path}: no spectral columns named A_<nm>")
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


def synchronise_reference(
    spectra: pd.DataFrame,
    reference: pd.DataFrame,
    tolerance: str = "5min",
    by: str = "subject_id",
) -> pd.DataFrame:
    """Pair each spectrum with the nearest reference glucose X(t) <-> G(t).

    ``reference`` needs [by, timestamp, glucose_ref]. Spectra with no reference
    within ``tolerance`` are dropped; the time offset is kept as ``ref_lag_s``
    so its effect on error can be analysed later.
    """
    s = spectra.sort_values("timestamp").copy()
    r = reference.sort_values("timestamp")[[by, "timestamp", TARGET_COL]].copy()
    r["ref_time"] = r["timestamp"]
    out = pd.merge_asof(
        s.drop(columns=[TARGET_COL], errors="ignore"),
        r,
        on="timestamp",
        by=by,
        direction="nearest",
        tolerance=pd.Timedelta(tolerance),
    )
    out["ref_lag_s"] = (out["timestamp"] - out["ref_time"]).dt.total_seconds()
    return out.dropna(subset=[TARGET_COL]).drop(columns=["ref_time"]).reset_index(drop=True)
