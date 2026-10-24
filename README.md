# glycemico-pred — EarSpectro non-invasive glucose prediction

ML/DL framework for predicting blood glucose from multi-wavelength near-infrared
(NIR) spectra measured at the earlobe. It implements the staged plan from the
EarSpectro literature survey:

```
Raw ear NIR → QC → preprocessing → representation → feature/wavelength selection
  → PLSR / SVR / RF / XGBoost / CatBoost → FFNN → 1-D CNN
  → subject-independent validation → calibration → explainability
```

The project treats this as a **generalisation** problem, not a curve-fitting one:
the main result is always error on **subjects the model never saw**.

## Status

No real EarSpectro recordings exist yet. Until they do, everything runs on a
**synthetic** dataset (`earspectro/data/synthetic.py`) built on the mixture
model from the survey:

```
x = s_glucose + s_tissue + s_water + s_hb + s_scatter + s_motion + s_sensor + ε
```

The generator includes per-subject anatomy (optical path, water/lipid/protein/Hb, scatter),
per-session sensor placement and gain, a skin-temperature confounder that drifts after the
glucose load (it correlates with glucose but isn't caused by it), OGTT-shaped glucose
curves for normoglycaemic and diabetic subjects, reference-meter error, and motion, ambient-light,
saturation and dropout artifacts.
Band positions follow standard NIR assignments, but the glucose band strength
(`--glucose_gain`) is a free parameter. **Synthetic results check that the pipeline
works and is leakage-free. They are not evidence of device accuracy.**

## Layout

| Path | Stage (survey §) |
|---|---|
| `earspectro/data/io.py` | dataset schema, reference-glucose synchronisation (§11) |
| `earspectro/data/synthetic.py` | synthetic ear-NIR generator |
| `earspectro/qc.py` | quality score Q, rejection (§12) |
| `earspectro/preprocessing.py` | detrend, SG, SNV, MSC, derivatives, combos (§13–14) |
| `earspectro/features.py` | wavelength subsets, engineered ratio/difference/slope features (§15–16) |
| `earspectro/selection.py` | correlation filter, mRMR, RFE — fitted on training folds only (§17) |
| `earspectro/models/` | mean, linear, ridge, PLSR, SVR, RF, XGBoost, CatBoost, FFNN, 1-D CNN (§18–20, §32) |
| `earspectro/splits.py` | random / subject / session scenarios, leak check (§22–23) |
| `earspectro/pipeline.py` | leakage-safe pipeline + cross-validation |
| `earspectro/calibration.py` | 0/1/2/3/5-point per-session calibration (§24–25) |
| `earspectro/explain.py` | permutation + SHAP wavelength importance with fold stability (§27) |
| `earspectro/metrics.py` | MAE, RMSE, R², MARD, Clarke grid, Bland–Altman, subgroup MAE (§28, §31) |
| `experiments/run.py` | one sub-command per study |
| `slurm/run_all.sh` | full suite on gnode118 |

## Data format

One row per spectrum (CSV or parquet):

| column | meaning |
|---|---|
| `subject_id`, `session_id`, `timestamp` | required identifiers |
| `glucose_ref` | reference glucose, mg/dL |
| `A_<nm>` | absorbance at each wavelength, e.g. `A_1050 … A_1650` |
| `timepoint`, `repeat`, `session_idx` | repeated-measurement structure (used by QC, calibration, session split) |
| anything else | metadata kept for subgroup analysis, never fed to models |

`earspectro.data.synchronise_reference` pairs raw spectra with the nearest
reference reading within a tolerance and records the lag.

## Leakage rules enforced in code

- Subject split: `check_no_subject_leak` asserts no subject is in both train and test.
- Preprocessing, MSC reference, scalers, QC thresholds and feature selectors are fitted inside each training fold.
- PLSR/SVR hyper-parameters are tuned with an inner GroupKFold over training subjects. NN early stopping holds out training subjects.
- Wavelength-count curve uses **nested** selection: the best subset of size k is picked on inner folds, then scored on the outer held-out subjects. The all-subsets table is descriptive only.

## Running (Ada, gnode118)

```bash
cd /scratch/nishanth.r/glycemico-pred
source venv/bin/activate
pytest -q
python experiments/run.py generate --grid ear5        # data/synthetic_ear5.csv
python experiments/run.py scenarios --prep snv
python experiments/run.py report
```

Full suite as a batch job:

```bash
sbatch slurm/run_all.sh
DATA=data/real_ear.csv OUT=outputs_real sbatch slurm/run_all.sh
```

Results land in `outputs/<study>/` and are summarised in `outputs/REPORT.md`.

## Hypotheses → experiments

| | Hypothesis | Command |
|---|---|---|
| H1 | preprocessing beats raw | `matrix` |
| H2 | a wavelength subset is as good as all five | `wavelengths` |
| H3 | nonlinear > linear/PLSR | `matrix`, `scenarios` |
| H4 | 1-D CNN helps with enough data | `matrix` (`--grid dense` data for a real spectral axis) |
| H5 | unseen-subject error > random-split error | `scenarios` |
| H6 | few-point calibration helps | `calibration` |
| H7 | interference-robust training generalises | planned: transfer learning once a pretraining corpus is chosen |

## Findings so far (synthetic data, 2026-10-24)

Three datasets, 40 subjects × 2 OGTT sessions × 16 timepoints × 3 repeats:
`ear5` (the 5-LED layout at default realism), `dense` (1000–1700 nm every 5 nm, same physiology),
and `control_ear5` (5 LEDs, 5× stronger glucose band, no temperature confounder).
Full tables: `outputs/<dataset>/REPORT.md`. Errors are on **unseen subjects** unless stated.

1. **The pipeline finds signal when it exists.** On the positive control, ridge/PLSR/SVR reach
   R² ≈ 0.51–0.54 (MAE ≈ 29 mg/dL) on unseen subjects. The mean predictor gives MAE 43.
2. **Five LEDs are under-determined at realistic glucose strength.** On `ear5`, no model
   beats predicting the mean on unseen subjects (best MAE 41.6 vs 43.1; all R² < 0). With the same
   physiology on a dense spectrum, linear/PLSR models reach R² ≈ 0.32–0.38 (MAE ≈ 32–34).
   Five channels cannot separate glucose from ~8 nuisance factors (path length, water, lipid,
   protein, Hb, scatter, gain/tilt, temperature). This argues for more wavelengths or a reference
   channel, a hypothesis to test on real data.
3. **Random splits overstate accuracy, as the survey warned (H5).** FFNN on dense:
   R² +0.60 on a random split, −0.09 on unseen subjects. CatBoost on ear5: +0.31 vs −0.28.
4. **Nonlinear models do not beat linear ones here (H3/H4).** With 40 subjects, tree models and
   the CNN fit subject identity. On the dense grid, PLSR/linear plus detrend or d1+SNV are at the top.
   Permutation importance for CatBoost on held-out subjects is *negative* at every wavelength,
   so what it learned hurts on new people.
5. **Preprocessing matters little for linear models and a lot for nonlinear ones (H1).** Across the
   preprocessing variants, MAE spreads by 2–4 mg/dL for linear/PLSR but 7–16 mg/dL for RF,
   XGBoost, CatBoost and the CNN. Detrend and d1+SNV give the best dense-grid results. For the
   tree models, d1+SNV is what makes them competitive at all (CatBoost dense: 32.6 with d1+SNV).
6. **Calibration gains are mostly the reference level (H6).** A spectra-free `ref_only` control
   (predict the mean calibration reading) matches every calibrated model on `ear5`. On `dense`,
   PLSR + 5-point linear calibration reaches MAE 25.5 vs 29.7 for `ref_only`. That ~4 mg/dL is the
   part the optical model actually adds.
7. **QC works on the injected artifacts.** 96–100% of motion, ambient, saturation and dropout spectra
   are rejected, and 0.05% of clean spectra.

## Not done yet

- Transfer learning (§21): waiting for a relevant pretraining spectral dataset.
- Multi-task (glucose + quality + category) head (§26).
- Uncertainty output U (conformal intervals) for the final (Ĝ, Q, U) model.
- Surveillance Error Grid (needs the SEG risk table).
