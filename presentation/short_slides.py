
# ════════════════════════════════════════════════════════════════════════════
# Condensed 6-slide version. Appended after the helper/data section of build_deck.py.

# 1. Title + question
s = new_slide(dark=True, notes="EarSpectro: predicting blood glucose from multi-wavelength earlobe NIR spectra. "
                               "All results so far come from synthetic data.")
tb(s, 0.9, 0.8, 11, 0.4, "NON-INVASIVE GLUCOSE · NEAR-INFRARED SPECTROSCOPY", 14, AMBER, bold=True)
tb(s, 0.9, 1.35, 11.6, 1.7, "EarSpectro: predicting blood glucose from earlobe NIR spectra", 40, WHITE,
   bold=True, font=HEAD)
tb(s, 0.9, 3.2, 11.4, 1.1, "Can multi-wavelength ear spectra predict glucose in people the model has never seen, and "
                           "which preprocessing, wavelengths, model and calibration make that work?", 18, LAV,
   italic=True)
for i, (lab, col) in enumerate([("1050", LAV), ("1200", LAV), ("1450", AMBER), ("1550", RED), ("1650", RED)]):
    badge(s, 0.9 + i * 1.05, 4.75, 0.8, lab, fill=col, color=INK if col in (LAV, AMBER) else WHITE, pt=13)
tb(s, 6.3, 4.9, 6.2, 0.5, "nm · the five EarSpectro LED wavelengths", 14, LAV, anchor=MSO_ANCHOR.MIDDLE)
tb(s, 0.9, 6.3, 11.5, 0.4, "github.com/Nishanth-nishu/glycemico-pred  ·  October 2026", 13, LAV)

# 2. Pipeline architecture
s = new_slide(kicker="Architecture", title="End-to-end pipeline: raw ear spectrum to glucose, quality and uncertainty",
              notes="Each box is a module of the earspectro package. Everything after the split is fitted on training "
                    "subjects only.")
stages = [("Ear NIR + glucose sync", "nearest reading within 5 min"),
          ("Quality control", "score Q, reject Q < 0.5"),
          ("Preprocessing", "SG · SNV · MSC · d1 · detrend"),
          ("Representation", "spectrum, or 45 engineered features"),
          ("Selection", "corr · mRMR · RFE · nested λ subsets"),
          ("Models", "PLSR · SVR · RF · XGB · CatBoost · FFNN · 1-D CNN"),
          ("Validation", "random · unseen-subject · unseen-session"),
          ("Calibration", "0–5 reference points per session"),
          ("Explain + output", "permutation · SHAP → (Ĝ, Q)")]
bw, bh, gx = 3.75, 1.3, 0.425
for i, (t, sub) in enumerate(stages):
    row, col = divmod(i, 3)
    if row == 1:
        col = 2 - col                       # snake layout
    x = 0.6 + col * (bw + gx)
    y = 1.7 + row * 1.75
    dark = i in (1, 6, 7)
    box(s, x, y, bw, bh, fill=INK if dark else TINT)
    badge(s, x + 0.18, y + 0.36, 0.55, str(i + 1), fill=RED, pt=13)
    tb(s, x + 0.95, y + 0.17, bw - 1.1, 0.45, t, 14, WHITE if dark else INK, bold=True)
    tb(s, x + 0.95, y + 0.65, bw - 1.1, 0.55, sub, 12, LAV if dark else GREY)
    if i < 8:
        if i in (2, 5):
            arrow(s, x + bw / 2, y + bh + 0.03, x + bw / 2, y + 1.75 - 0.03)
        elif row == 1:
            arrow(s, x - 0.03, y + bh / 2, x - gx + 0.03, y + bh / 2)
        else:
            arrow(s, x + bw + 0.03, y + bh / 2, x + bw + gx - 0.03, y + bh / 2)
tb(s, 0.6, 6.6, 12.1, 0.35, "Dark boxes decide whether results generalise: the quality gate, subject-level validation "
                            "and calibration.", 12, GREY)

# 3. Signal model + data
s = new_slide(kicker="Signal model and data", title="Glucose is a tiny part of a mixed spectrum; data is synthetic for now",
              notes="Glucose adds about 0.002 OD per 100 mg/dL at its strongest band, against about 0.1 OD of "
                    "between-subject tissue variation.")
formula(s, "mixture", 0.6, 1.65, pt=22, max_w=12.1)
formula(s, "absorb", 0.6, 2.35, pt=16, max_w=12.1)
tb(s, 0.6, 2.95, 12.1, 0.35, "Simulates: subject anatomy · sensor placement and gain · OGTT glucose curves · "
                             "temperature confounder · artifacts · 5% meter error", 12, GREY)
variants = [("ear5", "5 LEDs, realistic glucose strength", INK),
            ("dense", "1000–1700 nm every 5 nm, same physiology", TEAL),
            ("control", "5 LEDs, 5× stronger glucose, no confounder", RED)]
for i, (n, d, col) in enumerate(variants):
    x = 0.6 + i * 4.1
    box(s, x, 3.6, 3.85, 1.35, fill=TINT)
    tb(s, x + 0.25, 3.72, 3.4, 0.45, n, 18, col, bold=True, font=HEAD)
    tb(s, x + 0.25, 4.2, 3.4, 0.7, d, 13, INK)
tb(s, 0.6, 5.2, 12.1, 0.35, "Each dataset: 40 subjects × 2 sessions × 16 timepoints × 3 repeats = 3,840 spectra",
   14, INK, bold=True)
tb(s, 0.6, 5.75, 12.1, 1.1, ["• Glucose band positions: Amerov, Chen & Arnold (2004), Applied Spectroscopy, "
                             "doi:10.1366/0003702042336136",
                             "• No real EarSpectro recordings yet; real data plugs into the same CSV format"], 12, GREY)

# 4. Key formulas
s = new_slide(kicker="Methods", title="Key formulas: quality, preprocessing, features, evaluation and calibration",
              notes="Every transform, selector and tuning step is fitted inside training folds only.")
cells = [("Quality score", "qprod"), ("SNV", "snv"), ("MSC", "msc"),
         ("Feature ratio", "ratio"), ("mRMR selection", "mrmr"), ("1-D convolution", "conv"),
         ("Leak-free split", "split"), ("Accuracy", "mae"), ("Fit", "r2"),
         ("Clinical relative error", "mard"), ("Offset calibration", "cal_off"), ("Control: ignore spectra", "cal_ref")]
for i, (lab, f) in enumerate(cells):
    row, col = divmod(i, 3)
    x, y = 0.6 + col * 4.1, 1.62 + row * 1.33
    box(s, x, y, 3.85, 1.2, fill=TINT)
    tb(s, x + 0.2, y + 0.1, 3.45, 0.3, lab, 12, RED if f == "cal_ref" else GREY, bold=True)
    formula(s, f, x + 0.2, y + 0.42, pt=15, max_w=3.45)

# 5. Results: generalisation
s = new_slide(kicker="Results", title="Random splits flatter models; 5 LEDs can't untangle glucose",
              notes="Left: dense spectrum, R² by split type. Right: R² on unseen subjects across datasets.")
models = ["plsr", "svr", "catboost", "ffnn"]
names = ["PLSR", "SVR", "CatBoost", "FFNN"]
add_chart(s, XL_CHART_TYPE.COLUMN_CLUSTERED, 0.6, 1.6, 6.0, 4.5, names,
          [("Random split", [round(r2("dense", m, "random"), 2) for m in models]),
           ("Unseen subjects", [round(r2("dense", m, "subject"), 2) for m in models])],
          [LAV, INK], title="R² by split type (dense spectrum)", val_min=-0.6, val_max=0.8, label_pt=10, gap=50)
add_chart(s, XL_CHART_TYPE.COLUMN_CLUSTERED, 6.7, 1.6, 6.0, 4.5, names,
          [("5 LEDs", [round(r2("ear5", m, "subject"), 2) for m in models]),
           ("Dense", [round(r2("dense", m, "subject"), 2) for m in models]),
           ("Control (5× signal)", [round(r2("control_ear5", m, "subject"), 2) for m in models])],
          [RED, TEAL, INK], title="R² on unseen subjects by dataset", val_min=-0.6, val_max=0.7, label_pt=9, gap=40)
tb(s, 0.6, 6.2, 6.0, 0.7, f"FFNN drops from {r2('dense', 'ffnn', 'random'):.2f} to "
                          f"{r2('dense', 'ffnn', 'subject'):.2f} on new people. Only linear PLSR stays positive: "
                          "with 40 subjects, nonlinear models learn the person.", 13, INK)
tb(s, 6.7, 6.2, 6.0, 0.7, "The control proves the pipeline finds real signal (R² ≈ 0.5); 5 LEDs at realistic "
                          "strength find none.", 13, INK)

# 6. Remaining results + next step
s = new_slide(kicker="Results", title="Calibration, preprocessing, wavelengths, QC and explainability",
              notes="All panels: errors on unseen subjects. ref_only = mean of calibration readings, spectra ignored.")
c = CAL["dense"][CAL["dense"].model == "plsr"].pivot_table(index="k_cal", columns="method", values="MAE")
add_chart(s, XL_CHART_TYPE.LINE_MARKERS, 0.6, 1.6, 3.9, 3.3, [str(k) for k in c.index],
          [("PLSR calibrated", [round(v, 1) for v in c["linear"]]),
           ("ref_only", [round(v, 1) for v in c["ref_only"]])], [TEAL, RED],
          title="Calibration (dense): MAE vs points", numfmt="0", label_pt=9, val_min=20, val_max=50)
m = MX["dense"]
m = m[m.representation == "spectrum"]
raw = m[m.preprocessing == "raw"].set_index("model").MAE
best = m.groupby("model").MAE.min()
pm = ["linear", "plsr", "ffnn", "catboost"]
add_chart(s, XL_CHART_TYPE.COLUMN_CLUSTERED, 4.72, 1.6, 3.9, 3.3, ["Linear", "PLSR", "FFNN", "CatBoost"],
          [("Raw", [round(float(raw[o]), 1) for o in pm]), ("Best prep.", [round(float(best[o]), 1) for o in pm])],
          [LAV, TEAL], title="Preprocessing (dense): MAE", numfmt="0", label_pt=9, val_min=25, val_max=50, gap=50)
nst = NEST.pivot_table(index="n_wavelengths", columns="model", values="MAE")
add_chart(s, XL_CHART_TYPE.LINE_MARKERS, 8.84, 1.6, 3.86, 3.3, [str(k) for k in nst.index],
          [("PLSR (nested)", [round(v, 1) for v in nst["plsr"]]), ("Mean predictor", [43.1] * len(nst))],
          [INK, GREY], title="Wavelengths used (5 LEDs): MAE", numfmt="0", label_pt=9, val_min=40, val_max=50)
caps = ["At 5 points optics add ~4 mg/dL (25.5 vs 29.7); with 5 LEDs, none.",
        "Linear barely moves; d1+SNV rescues trees (CatBoost 48 → 33).",
        "No subset of the 5 LEDs beats predicting the mean."]
for i, cap in enumerate(caps):
    tb(s, 0.6 + i * 4.12, 4.98, 3.88, 0.55, cap, 11, GREY)
chips = [("QC", "96–100% of artifacts rejected; 0.05% of clean spectra", TEAL),
         ("Explainability", "PLSR leans on 1440–1500 nm (water band, temperature), not the 1590 nm glucose band", RED),
         ("Clinical", f"Clarke zone A on unseen subjects: {SC['dense']['clarke_A']['subject']['plsr']:.0f}% dense PLSR, "
                      f"{SC['control_ear5']['clarke_A']['subject']['svr']:.0f}% control SVR", AMBER),
         ("Next", "real ear data · more wavelengths · skin-temperature sensor · uncertainty U", INK)]
for i, (t, d, col) in enumerate(chips):
    x = 0.6 + i * 3.06
    box(s, x, 5.62, 2.9, 1.3, fill=INK if t == "Next" else TINT)
    tb(s, x + 0.18, 5.7, 2.6, 0.3, t, 13, AMBER if t == "Next" else col, bold=True)
    tb(s, x + 0.18, 6.02, 2.6, 0.85, d, 11, WHITE if t == "Next" else INK)

prs.save(OUT)
(OUT.with_suffix(".texts.json")).write_text(json.dumps(TEXTS, default=str))
print("slides:", len(prs.slides), "->", OUT)
