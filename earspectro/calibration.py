"""Stages 11-12: per-subject calibration on top of a subject-independent model.

Given out-of-fold predictions from the subject-independent scenario, each test
subject donates its first k timepoints (chronologically, as a device would at
setup) as calibration points; error is then measured on that subject's
remaining points only, and compared with zero calibration on the *same*
remaining points.

    k = 0      universal model
    k = 1      offset:  G' = G_hat + mean(G_ref - G_hat)
    k >= 2     offset, or shrunk linear  G' = a*G_hat + b  (a pulled toward 1)
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .metrics import regression_metrics


def _calibrate(p_cal, y_cal, p_eval, method: str, shrink: float):
    if len(p_cal) == 0 or method == "none":
        return p_eval
    if method == "offset" or len(np.unique(p_cal)) < 2:
        return p_eval + np.mean(y_cal - p_cal)
    # Ridge-to-identity slope: minimise sum (y - a p - b)^2 + shrink * n * (a - 1)^2 in centred form.
    pc, yc = p_cal - p_cal.mean(), y_cal - y_cal.mean()
    n = len(p_cal)
    a = (np.dot(pc, yc) + shrink * n) / (np.dot(pc, pc) + shrink * n)
    b = y_cal.mean() - a * p_cal.mean()
    return a * p_eval + b


def calibration_curve(oof: pd.DataFrame, ks=(0, 1, 2, 3, 5), methods=("offset", "linear"),
                      shrink: float = 50.0, per_session: bool = True) -> pd.DataFrame:
    """MAE vs number of calibration timepoints. Calibration is per session when
    ``per_session`` (sensor re-placed each day) else per subject."""
    unit = "session_id" if per_session else "subject_id"
    kmax = max(ks)
    rows = []
    for method in methods:
        for k in ks:
            ys, ps, base = [], [], []
            for _, g in oof.groupby(unit):
                tps = np.sort(g["timepoint"].unique())
                if len(tps) <= kmax:
                    continue
                cal_tp, eval_mask = tps[:k], g["timepoint"].isin(tps[kmax:]).to_numpy()
                cal = g[g["timepoint"].isin(cal_tp)]
                # Average repeats at each calibration timepoint: one reference per timepoint.
                cal = cal.groupby("timepoint")[["y", "pred"]].mean()
                ev = g[eval_mask]
                ps.append(_calibrate(cal["pred"].to_numpy(), cal["y"].to_numpy(), ev["pred"].to_numpy(),
                                     "none" if k == 0 else method, shrink))
                ys.append(ev["y"].to_numpy())
            y, p = np.concatenate(ys), np.concatenate(ps)
            rows.append({"method": method, "k_cal": k, **regression_metrics(y, p)})
    out = pd.DataFrame(rows)
    zero = out[out.k_cal == 0].groupby("method")["MAE"].first()
    out["delta_MAE"] = out["MAE"] - out["method"].map(zero)
    return out
