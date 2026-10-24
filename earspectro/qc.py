"""Stage 2: spectral quality control.

Every check is unsupervised (never looks at glucose) and returns a per-spectrum
score in [0, 1]. The combined quality score Q is their product, so one bad
property is enough to pull Q down. Thresholds for the robust checks are fitted
on a reference set (the training fold) via ``QualityControl.fit``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


def _soft(excess: np.ndarray, scale: float) -> np.ndarray:
    """1 when excess <= 0, decaying smoothly as the excess grows."""
    return np.exp(-np.clip(excess, 0, None) / scale)


def _robust_z(v: np.ndarray, med: float, mad: float) -> np.ndarray:
    return (v - med) / (1.4826 * mad + 1e-12)


@dataclass
class QualityControl:
    a_min: float = 0.0           # absorbance below this -> too much light / ambient leak
    a_max: float = 4.0           # above this -> detector starved / clipped
    z_max: float = 4.0           # robust-z limit for amplitude, roughness, repeat deviation
    q_min: float = 0.5           # reject spectra with Q below this

    def fit(self, X: np.ndarray) -> "QualityControl":
        X = np.asarray(X, float)
        ok = ~np.isnan(X).any(axis=1)
        Xo = X[ok]
        level = Xo.mean(axis=1)
        rough = self._roughness(Xo)
        self.level_ = (np.median(level), np.median(np.abs(level - np.median(level))))
        self.rough_ = (np.median(rough), np.median(np.abs(rough - np.median(rough))))
        self.median_spectrum_ = np.median(Xo, axis=0)
        return self

    @staticmethod
    def _roughness(X: np.ndarray) -> np.ndarray:
        """Spectral discontinuity: largest |second difference| after removing the median shape."""
        if X.shape[1] < 3:
            return np.zeros(len(X))
        return np.abs(np.diff(X, n=2, axis=1)).max(axis=1)

    def score(self, X: np.ndarray, groups: np.ndarray | None = None) -> pd.DataFrame:
        """Per-check scores and combined Q. ``groups`` marks repeats of one timepoint."""
        X = np.asarray(X, float)
        n = len(X)
        missing = np.isnan(X).any(axis=1)
        Xf = np.where(np.isnan(X), np.nanmedian(X, axis=0), X)

        out_of_range = np.maximum(self.a_min - Xf.min(axis=1), Xf.max(axis=1) - self.a_max)
        # Saturation: two or more wavelengths pinned at exactly the same (clipped) value.
        flat = np.array([np.unique(np.round(r, 9)).size < r.size for r in Xf]) & ~missing
        z_level = np.abs(_robust_z(Xf.mean(axis=1), *self.level_))
        z_rough = np.abs(_robust_z(self._roughness(Xf), *self.rough_))

        z_rep = np.zeros(n)
        if groups is not None:
            g = pd.Series(np.asarray(groups))
            dev = np.zeros(n)
            for _, idx in g.groupby(g).groups.items():
                idx = np.asarray(list(idx))
                if len(idx) > 1:
                    med = np.median(Xf[idx], axis=0)
                    dev[idx] = np.abs(Xf[idx] - med).mean(axis=1)
            nz = dev[dev > 0]
            if nz.size:
                z_rep = np.abs(_robust_z(dev, np.median(nz), np.median(np.abs(nz - np.median(nz)))))

        s = pd.DataFrame({
            "q_missing": np.where(missing, 0.0, 1.0),
            "q_range": _soft(out_of_range, 0.1),
            "q_saturation": np.where(flat, 0.0, 1.0),
            "q_amplitude": _soft(z_level - self.z_max, 2.0),
            "q_discontinuity": _soft(z_rough - self.z_max, 2.0),
            "q_repeat": _soft(z_rep - self.z_max, 2.0),
        })
        s["Q"] = s.prod(axis=1)
        s["qc_pass"] = s["Q"] >= self.q_min
        return s


def repeat_groups(df: pd.DataFrame) -> np.ndarray:
    """Group key for repeated spectra of the same subject/session/timepoint."""
    cols = [c for c in ("session_id", "timepoint") if c in df.columns]
    if not cols:
        return None
    return df[cols].astype(str).agg("|".join, axis=1).to_numpy()
