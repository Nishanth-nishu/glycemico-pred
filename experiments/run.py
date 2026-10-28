#!/usr/bin/env python
"""EarSpectro experiment runner — one sub-command per study in the framework.

    generate     synthetic dataset (until real ear recordings exist)
    import_ntnu  real in-vitro NIR glucose spectra (NTNU, doi:10.18710/NSHFAK) -> EarSpectro CSV
    qc           QC detection vs known artifacts (synthetic only) + rejection stats
    matrix       representation x preprocessing x model  (section 30, H1/H3/H4)
    scenarios    random vs subject vs session split       (section 23, H5)
    wavelengths  single / pairs / increasing sets, nested selection (section 15, H2)
    selection    feature-selection methods on engineered features (section 17)
    calibration  0/1/2/3/5-point per-session calibration   (section 25, H6)
    explain      wavelength importance stability          (section 27)
    report       collect everything into outputs/REPORT.md

Every study writes CSVs and PNGs under --out/<study>/.
"""

from __future__ import annotations

import argparse
import json
import sys
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from earspectro import plots  # noqa: E402
from earspectro.calibration import calibration_curve  # noqa: E402
from earspectro.data import TARGET_COL, load_dataset, spectral_columns, wavelengths_of  # noqa: E402
from earspectro.data.ntnu import GRIDS, load_ntnu  # noqa: E402
from earspectro.data.synthetic import DENSE, EAR5, PHYSICAL_GLUCOSE_GAIN, SynthConfig, generate  # noqa: E402
from earspectro.explain import summarise_importance, wavelength_importance  # noqa: E402
from earspectro.metrics import regression_metrics  # noqa: E402
from earspectro.pipeline import RunSpec, cross_validate, fit_predict  # noqa: E402
from earspectro.qc import QualityControl, repeat_groups  # noqa: E402
from earspectro.splits import make_splits  # noqa: E402


def log(*a):
    print(*a, flush=True)


def _csv(df: pd.DataFrame, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    log(f"  -> {path}")


def _short(res: dict) -> str:
    return (f"MAE {res['MAE']:6.2f}  RMSE {res['RMSE']:6.2f}  R2 {res['R2']:+.3f}  "
            f"MARD {res['MARD']:5.1f}%  ClarkeA {res['clarke_A']:5.1f}%")


# ── generate ────────────────────────────────────────────────────────────────
def cmd_generate(a):
    cfg = SynthConfig(n_subjects=a.subjects, sessions_per_subject=a.sessions, seed=a.seed,
                      wavelengths=EAR5 if a.grid == "ear5" else DENSE,
                      glucose_gain=a.glucose_gain, noise_od=a.noise_od,
                      confound_strength=a.confound)
    df = generate(cfg)
    out = Path(a.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    (out.with_suffix(".config.json")).write_text(json.dumps(cfg.__dict__, indent=2))
    cols = spectral_columns(df)
    plots.example_spectra(df, cols, wavelengths_of(cols), out.with_suffix(".spectra.png"))
    log(f"{len(df)} spectra, {df.subject_id.nunique()} subjects, {len(cols)} wavelengths -> {out}")
    log(f"glucose_ref: mean {df[TARGET_COL].mean():.1f}, range {df[TARGET_COL].min():.0f}-{df[TARGET_COL].max():.0f}")


def cmd_import_ntnu(a):
    df = load_ntnu(a.raw, a.grid)
    out = Path(a.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    cols = spectral_columns(df)
    plots.example_spectra(df, cols, wavelengths_of(cols), out.with_suffix(".spectra.png"))
    log(f"{len(df)} spectra, {df.subject_id.nunique()} mixtures, {len(cols)} wavelengths -> {out}")
    log(f"glucose_ref: mean {df[TARGET_COL].mean():.1f}, range {df[TARGET_COL].min():.0f}-{df[TARGET_COL].max():.0f}")


# ── qc ──────────────────────────────────────────────────────────────────────
def cmd_qc(a):
    df = load_dataset(a.data)
    cols = spectral_columns(df)
    X = df[cols].to_numpy(float)
    s = QualityControl().fit(X).score(X, repeat_groups(df))
    out = Path(a.out) / "qc"
    res = pd.concat([df[["subject_id", "session_id", "timepoint"]], s], axis=1)
    if "artifact" in df.columns:
        res["artifact"] = df["artifact"].to_numpy()
        tab = res.groupby("artifact").agg(n=("Q", "size"), rejected=("qc_pass", lambda v: 100 * (~v).mean()),
                                          median_Q=("Q", "median")).reset_index()
        _csv(tab, out / "qc_by_artifact.csv")
        log(tab.to_string(index=False))
    log(f"overall rejection rate {100 * (~s['qc_pass']).mean():.2f}%")
    _csv(res, out / "qc_scores.csv")


# ── matrix ──────────────────────────────────────────────────────────────────
def cmd_matrix(a):
    df = load_dataset(a.data)
    rows = []
    for rep in a.representations:
        for prep in a.preprocessing:
            for model in a.models:
                if rep == "features" and model == "cnn1d":
                    continue        # engineered features have no spectral ordering
                spec = RunSpec(model=model, preprocessing=prep, representation=rep, seed=a.seed,
                               n_jobs=a.n_jobs, aggregate_repeats=a.aggregate)
                res, _ = cross_validate(df, spec, a.scenario, a.folds)
                rows.append(res)
                log(f"{rep:9s} {prep:8s} {model:9s} {_short(res)}  ({res['seconds']:.0f}s)")
                _csv(pd.DataFrame(rows), Path(a.out) / "matrix" / f"matrix_{a.scenario}.csv")
    res = pd.DataFrame(rows)
    for rep, g in res.groupby("representation"):
        piv = g.pivot_table(index="preprocessing", columns="model", values="MAE")
        plots.heatmap(piv, Path(a.out) / "matrix" / f"matrix_{a.scenario}_{rep}_MAE.png",
                      f"MAE (mg/dL), {rep}, {a.scenario}-independent CV")


# ── scenarios ───────────────────────────────────────────────────────────────
def cmd_scenarios(a):
    df = load_dataset(a.data)
    rows, out = [], Path(a.out) / "scenarios"
    for model in a.models:
        for scen in ("random", "subject", "session") + (("holdout",) if "split" in df else ()):
            spec = RunSpec(model=model, preprocessing=a.prep, seed=a.seed, n_jobs=a.n_jobs)
            res, oof = cross_validate(df, spec, scen, a.folds)
            rows.append(res)
            log(f"{model:9s} {scen:8s} {_short(res)}")
            if scen == "subject":
                _csv(oof, out / f"oof_{model}_subject.csv")
                plots.clarke_grid(oof.y, oof.pred, out / f"clarke_{model}_subject.png",
                                  f"{model}, {a.prep}, unseen subjects")
                plots.bland_altman_plot(oof.y, oof.pred, out / f"bland_altman_{model}_subject.png")
                plots.error_vs_glucose(oof.y, oof.pred, out / f"error_vs_glucose_{model}_subject.png")
    res = pd.DataFrame(rows)
    _csv(res, out / "scenarios.csv")
    plots.scenario_bars(res, out / "scenarios_MAE.png")


# ── wavelengths ─────────────────────────────────────────────────────────────
def cmd_wavelengths(a):
    df = load_dataset(a.data)
    wl = wavelengths_of(spectral_columns(df))
    if wl.size > 8:
        log(f"skipping: subset enumeration is for sparse LED layouts (<= 8 wavelengths), got {wl.size}")
        return
    out = Path(a.out) / "wavelengths"
    subsets = [tuple(c) for k in range(1, wl.size + 1) for c in combinations(wl, k)]

    # (1) Descriptive table: every subset under subject-independent CV.
    #     Picking the best row from this table would be selection on the test folds,
    #     so it is reported, never used to choose.
    rows = []
    for model in a.models:
        for sub in subsets:
            spec = RunSpec(model=model, preprocessing=a.prep, wavelengths=sub, seed=a.seed, n_jobs=a.n_jobs)
            res, _ = cross_validate(df, spec, "subject", a.folds)
            rows.append({**res, "n_wavelengths": len(sub)})
            log(f"{model:9s} {res['wavelengths']:28s} {_short(res)}")
        _csv(pd.DataFrame(rows), out / "all_subsets.csv")

    # (2) Honest curve: for each size k, choose the subset on inner folds of the
    #     training subjects only, then score it on the outer held-out subjects.
    curve = []
    for model in a.models:
        for k in range(1, wl.size + 1):
            cands = [s for s in subsets if len(s) == k]
            oofs, picks = [], []
            for fold, (tr, te) in enumerate(make_splits(df, "subject", a.folds, a.seed)):
                dtr = df.iloc[tr]
                if len(cands) > 1:
                    inner = [(s, cross_validate(dtr, RunSpec(model=model, preprocessing=a.prep, wavelengths=s,
                                                             seed=a.seed, n_jobs=a.n_jobs), "subject", 3)[0]["MAE"])
                             for s in cands]
                    best = min(inner, key=lambda t: t[1])[0]
                else:
                    best = cands[0]
                picks.append("-".join(str(int(w)) for w in best))
                pred, _, _ = fit_predict(dtr, df.iloc[te], RunSpec(model=model, preprocessing=a.prep,
                                                                   wavelengths=best, seed=a.seed, n_jobs=a.n_jobs))
                oofs.append(pred)
            o = pd.concat(oofs)
            m = regression_metrics(o.y, o.pred)
            curve.append({"model": model, "n_wavelengths": k, **m, "chosen_per_fold": ";".join(picks)})
            log(f"nested {model:9s} k={k}  MAE {m['MAE']:.2f}  picks {picks}")
            _csv(pd.DataFrame(curve), out / "nested_size_curve.csv")
    plots.line(pd.DataFrame(curve), "n_wavelengths", "MAE", "model", out / "nested_size_curve.png",
               "Wavelengths needed (subset chosen inside training folds)", "MAE on unseen subjects (mg/dL)")


# ── selection ───────────────────────────────────────────────────────────────
def cmd_selection(a):
    df = load_dataset(a.data)
    rows = []
    for model in a.models:
        for sel in ("none", "corr", "mrmr", "rfe"):
            for k in (a.k if sel != "none" else [0]):
                spec = RunSpec(model=model, preprocessing=a.prep, representation="features",
                               selector=None if sel == "none" else sel, k_features=k or 20,
                               seed=a.seed, n_jobs=a.n_jobs)
                res, _ = cross_validate(df, spec, "subject", a.folds)
                rows.append(res)
                log(f"{model:9s} {sel:5s} k={k:3d} {_short(res)}")
    _csv(pd.DataFrame(rows), Path(a.out) / "selection" / "selection.csv")


# ── calibration ─────────────────────────────────────────────────────────────
def cmd_calibration(a):
    df = load_dataset(a.data)
    out, curves = Path(a.out) / "calibration", []
    for model in a.models:
        spec = RunSpec(model=model, preprocessing=a.prep, seed=a.seed, n_jobs=a.n_jobs)
        _, oof = cross_validate(df, spec, "subject", a.folds)
        c = calibration_curve(oof).assign(model=model)
        curves.append(c)
        log(c[["model", "method", "k_cal", "MAE", "delta_MAE", "R2"]].to_string(index=False))
    c = pd.concat(curves)
    _csv(c, out / "calibration_curve.csv")
    plots.line(c.assign(series=c.model + "/" + c.method), "k_cal", "MAE", "series",
               out / "calibration_curve.png", "Per-session calibration on unseen subjects", "MAE (mg/dL)")


# ── explain ─────────────────────────────────────────────────────────────────
def cmd_explain(a):
    df = load_dataset(a.data)
    out, sums = Path(a.out) / "explain", []
    for model in a.models:
        spec = RunSpec(model=model, preprocessing=a.prep, seed=a.seed, n_jobs=a.n_jobs)
        imp = wavelength_importance(df, spec, "subject", a.folds)
        s = summarise_importance(imp).assign(model=model)
        sums.append(s)
        log(s.to_string(index=False))
        plots.importance_plot(s, out / f"importance_{model}.png", f"Wavelength importance — {model}, {a.prep}")
    _csv(pd.concat(sums), out / "importance_summary.csv")


# ── report ──────────────────────────────────────────────────────────────────
def _md(df: pd.DataFrame, cols, n=None, floatfmt=".2f"):
    d = df[cols].head(n) if n else df[cols]
    return d.to_markdown(index=False, floatfmt=floatfmt)


def cmd_report(a):
    o = Path(a.out)
    note = ("> NTNU in-vitro data: aqueous mixtures in a cuvette, no tissue. 'Subject' = mixture, "
            "'session' = measurement day. Clarke zones are not clinically meaningful here."
            if "ntnu" in Path(a.data).name else
            "> Synthetic data: these numbers validate the pipeline, not the device. "
            "See README for what the generator does and does not model.")
    lines = ["# EarSpectro experiment report", "", f"Data: `{a.data}`", "", note, ""]
    f = o / "scenarios" / "scenarios.csv"
    if f.exists():
        d = pd.read_csv(f)
        lines += ["## Evaluation scenarios (H5)", "",
                  _md(d.sort_values(["model", "scenario"]),
                      ["model", "scenario", "MAE", "RMSE", "R2", "MARD", "clarke_A", "subject_MAE_p90"]), "",
                  "![](scenarios/scenarios_MAE.png)", ""]
    for f in sorted((o / "matrix").glob("matrix_*.csv")):
        d = pd.read_csv(f).sort_values("MAE")
        lines += [f"## Model x preprocessing matrix — `{f.stem}` (H1, H3, H4)", "", "Top 15 by MAE:", "",
                  _md(d, ["representation", "preprocessing", "model", "MAE", "RMSE", "R2", "clarke_A"], 15), ""]
        lines += [f"![]({p.relative_to(o)})" for p in sorted((o / "matrix").glob(f"{f.stem}_*.png"))] + [""]
    f = o / "wavelengths" / "nested_size_curve.csv"
    if f.exists():
        d = pd.read_csv(f)
        lines += ["## How many wavelengths? (H2, nested selection)", "",
                  _md(d, ["model", "n_wavelengths", "MAE", "R2", "chosen_per_fold"]), "",
                  "![](wavelengths/nested_size_curve.png)", ""]
        d = pd.read_csv(o / "wavelengths" / "all_subsets.csv")
        single = d[d.n_wavelengths == 1]
        lines += ["Single-wavelength models (descriptive):", "",
                  _md(single, ["model", "wavelengths", "MAE", "R2"]), ""]
    f = o / "selection" / "selection.csv"
    if f.exists():
        d = pd.read_csv(f).fillna({"selector": "none"})
        lines += ["## Feature selection on engineered features", "",
                  _md(d, ["model", "selector", "k_features", "MAE", "R2"]), ""]
    f = o / "calibration" / "calibration_curve.csv"
    if f.exists():
        d = pd.read_csv(f)
        lines += ["## Calibration burden (H6)", "",
                  "`ref_only` ignores the spectra (predicts the mean calibration reference); "
                  "a model is only adding information where it beats `ref_only` at the same k.", "",
                  _md(d, ["model", "method", "k_cal", "MAE", "delta_MAE", "R2", "n"]), "",
                  "![](calibration/calibration_curve.png)", ""]
    f = o / "explain" / "importance_summary.csv"
    if f.exists():
        d = pd.read_csv(f)
        lines += ["## Wavelength importance on held-out subjects", "",
                  _md(d, ["model", "method", "wavelength", "mean", "std", "mean_rank", "rank_std"],
                      floatfmt=".3g"), ""]
        lines += [f"![]({p.relative_to(o)})" for p in sorted((o / "explain").glob("*.png"))] + [""]
    f = o / "qc" / "qc_by_artifact.csv"
    if f.exists():
        lines += ["## Quality control vs injected artifacts", "", _md(pd.read_csv(f), ["artifact", "n", "rejected",
                                                                                        "median_Q"]), ""]
    (o / "REPORT.md").write_text("\n".join(lines))
    log(f"  -> {o / 'REPORT.md'}")


def _glucose_gain(v):
    return PHYSICAL_GLUCOSE_GAIN if v == "physical" else float(v)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate")
    g.add_argument("--output", default="data/synthetic_ear5.csv")
    g.add_argument("--grid", choices=["ear5", "dense"], default="ear5")
    g.add_argument("--subjects", type=int, default=40)
    g.add_argument("--sessions", type=int, default=2)
    g.add_argument("--glucose_gain", type=_glucose_gain, default=2.0e-5,
                   help="OD per mg/dL at 1590 nm, or 'physical' for the literature strength")
    g.add_argument("--noise_od", type=float, default=1.5e-3)
    g.add_argument("--confound", type=float, default=1.0)
    g.add_argument("--seed", type=int, default=0)

    def common(sp, models, prep="raw"):
        sp.add_argument("--data", default="data/synthetic_ear5.csv")
        sp.add_argument("--out", default="outputs")
        sp.add_argument("--models", nargs="+", default=models)
        sp.add_argument("--prep", default=prep)
        sp.add_argument("--folds", type=int, default=5)
        sp.add_argument("--seed", type=int, default=0)
        sp.add_argument("--n_jobs", type=int, default=8)

    n = sub.add_parser("import_ntnu", help="convert the NTNU NIR glucose files (doi:10.18710/NSHFAK)")
    n.add_argument("--raw", required=True, help="folder with CalibrationData.txt and ValidationData.txt")
    n.add_argument("--grid", choices=sorted(GRIDS), default="nir")
    n.add_argument("--output", required=True)

    common(sub.add_parser("qc"), [])
    m = sub.add_parser("matrix")
    common(m, ["mean", "linear", "plsr", "svr", "rf", "xgboost", "catboost", "ffnn", "cnn1d"])
    m.add_argument("--preprocessing", nargs="+",
                   default=["raw", "detrend", "sg", "snv", "msc", "d1", "sg+snv", "sg+msc", "d1+snv"])
    m.add_argument("--representations", nargs="+", default=["spectrum", "features"])
    m.add_argument("--scenario", default="subject")
    m.add_argument("--aggregate", action="store_true", help="average QC-passed repeats per timepoint")
    common(sub.add_parser("scenarios"), ["mean", "plsr", "svr", "catboost", "ffnn", "cnn1d"])
    common(sub.add_parser("wavelengths"), ["plsr", "catboost"])
    s = sub.add_parser("selection")
    common(s, ["svr", "catboost"])
    s.add_argument("--k", nargs="+", type=int, default=[5, 10, 20])
    common(sub.add_parser("calibration"), ["plsr", "catboost", "cnn1d"])
    common(sub.add_parser("explain"), ["plsr", "catboost"])
    common(sub.add_parser("report"), [])

    a = p.parse_args()
    globals()[f"cmd_{a.cmd}"](a)


if __name__ == "__main__":
    main()
