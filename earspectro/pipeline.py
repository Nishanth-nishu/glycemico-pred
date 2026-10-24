"""Composes the stages into one leakage-safe sklearn Pipeline and runs CV.

    [wavelength subset] -> preprocessing -> [engineered features] ->
    [feature selection] -> [scaler] -> model

Quality control is fitted on the training fold and applied to both folds;
test spectra that fail QC are excluded from scoring (a device would refuse to
report them) and the rejection rate is recorded.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .data import TARGET_COL, spectral_columns, wavelengths_of
from .features import SpectralFeatures, WavelengthSubset
from .metrics import full_report
from .models import build_model
from .models.classical import needs_groups
from .preprocessing import build_preprocessor
from .qc import QualityControl, repeat_groups
from .selection import build_selector
from .splits import check_no_subject_leak, make_splits

_SCALED = {"linear", "ridge", "plsr", "svr"}


@dataclass
class RunSpec:
    model: str = "plsr"
    preprocessing: str = "raw"
    representation: str = "spectrum"      # "spectrum" (track A) | "features" (track B)
    wavelengths: tuple | None = None      # subset to keep; None = all
    selector: str | None = None           # None | corr | mrmr | rfe
    k_features: int = 20
    qc: bool = True
    aggregate_repeats: bool = False       # average QC-passed repeats per timepoint
    seed: int = 0
    n_jobs: int = 4

    def tag(self) -> str:
        wl = "all" if self.wavelengths is None else "-".join(str(int(w)) for w in self.wavelengths)
        sel = self.selector or "none"
        return f"{self.model}|{self.preprocessing}|{self.representation}|wl={wl}|sel={sel}"


def build_pipeline(spec: RunSpec, all_wavelengths) -> Pipeline:
    all_wl = np.asarray(all_wavelengths, float)
    subset = WavelengthSubset(all_wl, spec.wavelengths)
    wl = all_wl if spec.wavelengths is None else all_wl[subset.fit(np.zeros((1, all_wl.size))).idx_]
    steps = [("subset", subset), ("prep", build_preprocessor(spec.preprocessing, wl))]
    if spec.representation == "features":
        steps.append(("features", SpectralFeatures(wl)))
    sel = build_selector(spec.selector, spec.k_features)
    if sel is not None:
        steps.append(("select", sel))
    if spec.model in _SCALED:
        steps.append(("scale", StandardScaler()))
    steps.append(("model", build_model(spec.model, n_jobs=spec.n_jobs, seed=spec.seed)))
    return Pipeline(steps)


def _fit_params(spec: RunSpec, groups):
    if needs_groups(spec.model) or spec.model in ("ffnn", "cnn1d"):
        return {"model__groups": groups}
    return {}


def _aggregate(df: pd.DataFrame, X: np.ndarray):
    key = repeat_groups(df)
    g = pd.Series(np.arange(len(df))).groupby(key, sort=False)
    first = g.first().to_numpy()
    Xa = np.vstack([X[idx].mean(axis=0) for idx in g.apply(list)])
    return df.iloc[first].reset_index(drop=True), Xa


_KEEP = ("subject_id", "session_id", "session_idx", "timepoint", "repeat", "skin_tone",
         "diabetic", "sex", "age", "minutes_since_load", "artifact")


def fit_predict(dtr: pd.DataFrame, dte: pd.DataFrame, spec: RunSpec):
    """Fit QC + pipeline on ``dtr`` and predict ``dte``. Returns (pred frame, n_rejected, pipeline)."""
    cols = spectral_columns(dtr)
    wl = wavelengths_of(cols)
    dtr, dte = dtr.reset_index(drop=True), dte.reset_index(drop=True)
    Xtr, Xte = dtr[cols].to_numpy(float), dte[cols].to_numpy(float)
    n_rejected = 0
    if spec.qc:
        qc = QualityControl().fit(Xtr)
        ktr = qc.score(Xtr, repeat_groups(dtr))["qc_pass"].to_numpy()
        ste = qc.score(Xte, repeat_groups(dte))
        kte = ste["qc_pass"].to_numpy()
        n_rejected = int((~kte).sum())
        dtr, Xtr = dtr[ktr].reset_index(drop=True), Xtr[ktr]
        dte, Xte = dte[kte].reset_index(drop=True).assign(_Q=ste["Q"].to_numpy()[kte]), Xte[kte]
    else:
        fill = np.nanmean(Xtr)
        Xtr, Xte = np.nan_to_num(Xtr, nan=fill), np.nan_to_num(Xte, nan=fill)
        dte = dte.assign(_Q=1.0)
    if spec.aggregate_repeats:
        dtr, Xtr = _aggregate(dtr, Xtr)
        dte, Xte = _aggregate(dte, Xte)
    ytr, yte = dtr[TARGET_COL].to_numpy(float), dte[TARGET_COL].to_numpy(float)

    pipe = build_pipeline(spec, wl)
    pipe.fit(Xtr, ytr, **_fit_params(spec, dtr["subject_id"].to_numpy()))
    keep = [c for c in _KEEP if c in dte.columns]
    out = dte[keep].assign(y=yte, pred=pipe.predict(Xte), Q=dte["_Q"].to_numpy())
    return out, n_rejected, pipe


def cross_validate(df: pd.DataFrame, spec: RunSpec, scenario: str = "subject", n_splits: int = 5,
                   return_models: bool = False):
    """Out-of-fold predictions + metrics for one configuration under one scenario."""
    splits = make_splits(df, scenario, n_splits=n_splits, seed=spec.seed)
    if scenario == "subject":   # the session scenario reuses subjects on purpose (later days)
        check_no_subject_leak(df, splits)

    oof, models, n_rejected, n_test = [], [], 0, 0
    t0 = time.time()
    for fold, (tr, te) in enumerate(splits):
        pred, rej, pipe = fit_predict(df.iloc[tr], df.iloc[te], spec)
        oof.append(pred.assign(fold=fold))
        n_rejected += rej
        n_test += len(te)
        if return_models:
            models.append(pipe)

    oof = pd.concat(oof, ignore_index=True)
    res = {"scenario": scenario, "tag": spec.tag(), **asdict(spec), **full_report(oof["y"], oof["pred"]),
           "qc_reject_rate": n_rejected / max(n_test, 1), "seconds": time.time() - t0}
    res["wavelengths"] = "all" if spec.wavelengths is None else "-".join(str(int(w)) for w in spec.wavelengths)
    # Per-subject MAE spread: a model that only works for some subjects is not general.
    subj = oof.assign(ae=(oof["pred"] - oof["y"]).abs()).groupby("subject_id")["ae"].mean()
    res["subject_MAE_median"], res["subject_MAE_p90"] = float(subj.median()), float(subj.quantile(0.9))
    return (res, oof, models) if return_models else (res, oof)
