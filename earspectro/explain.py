"""Stage 14: which wavelengths does the model use, and is that stable across folds?

Importance is measured on each fold's *held-out* subjects, then summarised as
mean, std and rank stability across folds. A wavelength that is important in
one fold but not others is a warning sign, not a finding.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.inspection import permutation_importance

from .data import TARGET_COL, spectral_columns, wavelengths_of
from .pipeline import RunSpec, build_pipeline, _fit_params
from .qc import QualityControl, repeat_groups
from .splits import make_splits


def wavelength_importance(df: pd.DataFrame, spec: RunSpec, scenario: str = "subject", n_splits: int = 5,
                          n_repeats: int = 10, use_shap: bool = True) -> pd.DataFrame:
    cols = spectral_columns(df)
    wl = wavelengths_of(cols)
    X, y = df[cols].to_numpy(float), df[TARGET_COL].to_numpy(float)
    rows = []
    for fold, (tr, te) in enumerate(make_splits(df, scenario, n_splits, spec.seed)):
        qc = QualityControl().fit(X[tr])
        ktr = qc.score(X[tr], repeat_groups(df.iloc[tr]))["qc_pass"].to_numpy()
        kte = qc.score(X[te], repeat_groups(df.iloc[te]))["qc_pass"].to_numpy()
        tr, te = tr[ktr], te[kte]
        pipe = build_pipeline(spec, wl)
        pipe.fit(X[tr], y[tr], **_fit_params(spec, df["subject_id"].to_numpy()[tr]))
        # Permutation importance on raw input wavelengths: model-agnostic, includes preprocessing.
        pi = permutation_importance(pipe, X[te], y[te], scoring="neg_mean_absolute_error",
                                    n_repeats=n_repeats, random_state=spec.seed, n_jobs=1)
        for w, m in zip(wl, pi.importances_mean):
            rows.append({"fold": fold, "wavelength": w, "method": "permutation_dMAE", "importance": m})
        if use_shap and spec.model in ("catboost", "xgboost", "rf") and spec.representation == "spectrum" \
                and spec.preprocessing == "raw" and spec.wavelengths is None:
            import shap
            expl = shap.TreeExplainer(pipe.named_steps["model"])
            sv = expl.shap_values(pipe[:-1].transform(X[te]))
            for w, m in zip(wl, np.abs(sv).mean(axis=0)):
                rows.append({"fold": fold, "wavelength": w, "method": "mean_abs_shap", "importance": m})
    imp = pd.DataFrame(rows)
    imp["rank"] = imp.groupby(["fold", "method"])["importance"].rank(ascending=False)
    return imp


def summarise_importance(imp: pd.DataFrame) -> pd.DataFrame:
    return (imp.groupby(["method", "wavelength"])
            .agg(mean=("importance", "mean"), std=("importance", "std"),
                 mean_rank=("rank", "mean"), rank_std=("rank", "std"))
            .reset_index().sort_values(["method", "mean_rank"]))
