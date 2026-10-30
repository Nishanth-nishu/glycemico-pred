# glycemico-pred — EarSpectro non-invasive glucose prediction

> **Also in this repo:** the penny-stocks talent pipeline run on Ada with local Ollama.
> Start at [PENNY_README.md](PENNY_README.md) (handover: what was done, how to run, open items),
> then [PENNY_RESULTS.md](PENNY_RESULTS.md) (numbers) and the site in `docs/`.

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

## Real data: NTNU aqueous glucose NIR (2026-10-28)

Fuglerud et al., *J Biophotonics* 2021 (doi:10.1002/jbio.202000450); data doi:10.18710/NSHFAK (CC0).
393 transmission spectra (Metrohm XDS, 400–2500 nm) of 91 aqueous mixtures at ~37 °C, with
glucose 0–50 mM (0–900 mg/dL) plus lactate, acetaminophen, caffeine and ethanol as interferents.
**This is in-vitro: no skin, blood or physiology.** It tests whether the pipeline can pull glucose
out of overlapping NIR absorbers, not whether an ear sensor works.

```
python experiments/run.py import_ntnu --raw data/ntnu_raw --grid {ear5,dense,nir} --output data/ntnu_<grid>.csv
sbatch slurm/run_ntnu.sh
```

Mapping: subject = mixture, session = one cuvette fill (the `session` split uses the day: days 2–4
calibration, day 5 validation), `holdout` = the authors' own calibration → validation split. Grids: `nir` (1100–1880 + 2050–2350 nm, 542 bands),
`dense` (1000–1700 nm every 5 nm, 141 bands), `ear5` (the five EarSpectro LED wavelengths).

Two validation mixtures, VAL012 and VAL015, are labelled 50 mM glucose but read as ~25 mM. Every
one of their 6 spectra does, across two cuvettes, while lactate, ethanol, acetaminophen and caffeine
in the same spectra are predicted at their labels (VAL015: ethanol 70.8 vs 69, lactate 15.4 vs 15).
A diluted sample would shift every analyte, so a glucose prep or labelling error is the likely cause.
They are flagged in `label_suspect` (rule: `SUSPECT_LABELS` in `earspectro/data/ntnu.py`) and
`slurm/run_ntnu.sh` reports each grid with them (`outputs/ntnu_<grid>`) and without them
(`outputs/ntnu_<grid>_clean`, `import_ntnu --drop_suspect`).

PLSR MAE in mg/dL (÷18 for mM). Without / with the two suspect mixtures; the mean predictor scores 220–275:

| grid | unseen mixtures | day-5 holdout | best nonlinear, unseen mixtures |
|:--|--:|--:|--:|
| nir (542 bands) | **20.4** (1.1 mM), R² 0.988 / 32.1 | **15.7** (0.9 mM), R² 0.994 / 34.5 | FFNN 34.4 |
| dense (141 bands) | **17.8** (1.0 mM), R² 0.990 / 30.7 | **13.3** (0.7 mM), R² 0.995 / 35.2 | FFNN 35.7 |
| ear5 (5 LEDs) | **94.6** (5.3 mM), R² 0.85 / 100.4 | **75.7** (4.2 mM), R² 0.86 / 97.2 | FFNN 98.0 |

1. **Real NIR spectra carry recoverable glucose.** PLSR reaches R² ≈ 0.99 and ~1 mM error on mixtures
   it never saw and on the separately mixed day-5 set, despite four interferents.
2. **Five LEDs are about 5× worse than a dense spectrum (H2).** Nested selection on ear5: 1–2
   wavelengths are near the mean predictor (R² ≤ 0.18); 1200/1550/1650 nm gives R² 0.80, and adding
   the other two LEDs adds almost nothing. This matches synthetic finding 2.
3. **Linear wins again (H3/H4).** PLSR is best in every grid and scenario; on ear5 FFNN is closest (98 vs 95 on unseen mixtures).
   The CNN is the weakest model after the mean predictor on nir. CatBoost permutation importance on
   held-out mixtures is negative at 20–33% of wavelengths, PLSR's at 0–2%.
4. **Day-to-day drift hurts nonlinear models most (H5).** In the `session` split (train on a mixture's
   earlier day, test its later day; only 94 training spectra) PLSR on nir goes from 20 to 34 mg/dL,
   FFNN from 34 to 83 and CatBoost from 61 to 88. Part of that gap is the smaller training set.
5. **The suspect labels dominate the headline error.** With them, day-5 PLSR RMSE is ~97 vs MAE ~35;
   without them RMSE ~20 vs MAE ~16.

QC on this data rejects 0–2.5% of spectra. Two QC bugs surfaced on the way, both fixed and covered
by tests: the amplitude check treated a 3% baseline offset of cuvette 3 as an outlier (it rejected
every cuvette-3 spectrum on the nir grid), and the repeat check grouped by `session_id` without
`subject_id`, so all mixtures from one day were treated as repeats of each other. Neither changes
synthetic results (synthetic `session_id` already contains the subject; amplitude spread there is
above the new floor).

Not run on NTNU: `calibration` (there are no per-subject calibration readings in vitro).

## Not done yet

- Transfer learning (§21): waiting for a relevant pretraining spectral dataset.
- Multi-task (glucose + quality + category) head (§26).
- Uncertainty output U (conformal intervals) for the final (Ĝ, Q, U) model.
- Surveillance Error Grid (needs the SEG risk table).
