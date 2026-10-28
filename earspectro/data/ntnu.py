"""Real in-vitro NIR glucose spectra from NTNU (Fuglerud et al., J. Biophotonics 2021).

    Dataset: "Aqueous glucose measured by NIR spectroscopy", doi:10.18710/NSHFAK (CC0)
    Paper:   doi:10.1002/jbio.202000450

Glucose, lactate, acetaminophen, caffeine and ethanol mixed in PBS, measured on a
Metrohm XDS spectrometer at ~37 C, 400-2499.5 nm every 0.5 nm, absorbance -log(I/I0).
CalibrationData.txt covers days 2-4; ValidationData.txt was mixed separately and
measured on day 5. Files are UTF-16, tab separated, with trailing empty columns.

Mapping onto the EarSpectro schema (one row = one spectrum):

    subject_id   one mixture (identical composition, same file). Repeat spectra of a
                 mixture never straddle train/test under the "subject" split.
    session_id   measurement day; session_idx = day - 2
    split        "cal" or "val" (the authors' own separate-day validation set)
    glucose_ref  glucose in mg/dL (mM x 18.016), exact by construction
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .synthetic import DENSE, EAR5

MG_DL_PER_MM = 18.016
_META = {
    "Glucose (mM)": "glucose_mM", "Lactate (mM)": "lactate_mM",
    "Acetaminophen (mM)": "acetaminophen_mM", "Caffeine (mM)": "caffeine_mM",
    "Ethanol (mM)": "ethanol_mM", "Temperature (C)": "temperature_C",
    "Kuvette": "cuvette", "Day": "day", "Run": "run",
}
_ANALYTES = ["glucose_mM", "lactate_mM", "acetaminophen_mM", "caffeine_mM", "ethanol_mM"]

# Resampling grids: (centres, half-width of the averaging window in nm).
# "nir" skips 1880-2050 nm, where water absorbance passes ~3 and the detector saturates.
GRIDS = {
    "nir": (np.r_[np.arange(1100, 1881, 2), np.arange(2050, 2351, 2)], 1.0),
    "dense": (np.asarray(DENSE, float), 2.5),     # same axis as the synthetic dense grid
    "ear5": (np.asarray(EAR5, float), 10.0),      # LED-like bands around the 5 EarSpectro LEDs
}


def _read(path: Path) -> pd.DataFrame:
    d = pd.read_csv(path, sep="\t", encoding="utf-16")
    d.columns = [str(c).strip() for c in d.columns]
    return d.loc[:, ~d.columns.str.startswith("Column")].rename(columns=_META)


def load_ntnu(raw_dir: str | Path, grid: str = "nir") -> pd.DataFrame:
    raw_dir = Path(raw_dir)
    parts = []
    for split, fname in (("cal", "CalibrationData.txt"), ("val", "ValidationData.txt")):
        d = _read(raw_dir / fname)
        d["split"] = split
        mix = d.groupby(_ANALYTES, sort=False).ngroup()
        d["subject_id"] = [f"{split.upper()}{m + 1:03d}" for m in mix]
        parts.append(d)
    d = pd.concat(parts, ignore_index=True)

    wl_cols = [c for c in d.columns if c.replace(".", "", 1).isdigit()]
    wl = np.array(wl_cols, float)
    X = d[wl_cols].to_numpy(float)
    centres, half = GRIDS[grid]
    spec = {}
    for c in centres:
        m = np.abs(wl - c) <= half + 1e-9
        spec[f"A_{c:g}"] = X[:, m].mean(axis=1)

    meta = d.drop(columns=wl_cols)
    meta["session_idx"] = meta["day"] - 2
    meta["session_id"] = "day" + meta["day"].astype(str)
    meta["repeat"] = meta.groupby(["subject_id", "day"]).cumcount()
    meta["timepoint"] = 0
    meta["glucose_true"] = meta["glucose_mM"] * MG_DL_PER_MM
    meta["glucose_ref"] = meta["glucose_true"]
    return pd.concat([meta, pd.DataFrame(spec)], axis=1)
