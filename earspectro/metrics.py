"""Section 31: regression metrics plus clinical / agreement analyses.

Glucose is in mg/dL throughout.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def regression_metrics(y, p) -> dict:
    y, p = np.asarray(y, float), np.asarray(p, float)
    err = p - y
    ss_res = np.sum(err ** 2)
    ss_tot = np.sum((y - y.mean()) ** 2)
    return {
        "n": int(y.size),
        "MAE": float(np.mean(np.abs(err))),
        "RMSE": float(np.sqrt(np.mean(err ** 2))),
        "R2": float(1 - ss_res / ss_tot) if ss_tot > 0 else float("nan"),
        "MARD": float(100 * np.mean(np.abs(err) / y)),
        "bias": float(err.mean()),
        "pearson_r": float(np.corrcoef(y, p)[0, 1]) if y.size > 1 and p.std() > 0 else float("nan"),
    }


def clarke_zones(y, p) -> np.ndarray:
    """Clarke Error Grid zone (A-E) per point; y = reference, p = prediction."""
    y, p = np.asarray(y, float), np.asarray(p, float)
    z = np.full(y.size, "B", dtype="<U1")
    for i, (r, e) in enumerate(zip(y, p)):
        if (r <= 70 and e <= 70) or (0.8 * r <= e <= 1.2 * r):
            z[i] = "A"
        elif (r >= 180 and e <= 70) or (r <= 70 and e >= 180):
            z[i] = "E"
        elif (70 <= r <= 290 and e >= r + 110) or (130 <= r <= 180 and e <= (7 / 5) * r - 182):
            z[i] = "C"
        elif (r >= 240 and 70 <= e <= 180) or (r <= 175 / 3 and 70 <= e <= 180) or \
             (175 / 3 <= r <= 70 and e >= (6 / 5) * r):
            z[i] = "D"
    return z


def clarke_summary(y, p) -> dict:
    z = clarke_zones(y, p)
    return {f"clarke_{k}": float(np.mean(z == k) * 100) for k in "ABCDE"}


def bland_altman(y, p) -> dict:
    d = np.asarray(p, float) - np.asarray(y, float)
    m, s = d.mean(), d.std(ddof=1)
    return {"ba_bias": float(m), "ba_loa_low": float(m - 1.96 * s), "ba_loa_high": float(m + 1.96 * s)}


GLUCOSE_BINS = [0, 70, 180, 250, np.inf]
GLUCOSE_LABELS = ["<70", "70-180", "180-250", ">250"]


def subgroup_mae(df: pd.DataFrame, by: str, y: str = "y", p: str = "pred") -> pd.DataFrame:
    """MAE_k per subgroup (section 28)."""
    g = df.assign(abs_err=(df[p] - df[y]).abs()).groupby(by, observed=True)
    return g.agg(n=("abs_err", "size"), MAE=("abs_err", "mean")).reset_index()


def full_report(y, p) -> dict:
    out = regression_metrics(y, p)
    out.update(clarke_summary(y, p))
    out.update(bland_altman(y, p))
    return out
