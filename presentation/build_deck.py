"""Build the EarSpectro deck (python-pptx, native charts, formula images)."""
import json
import sys
from pathlib import Path

import pandas as pd
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml import parse_xml
from pptx.util import Emu, Inches, Pt

REPO = Path(sys.argv[1])
FORM = Path(sys.argv[2])
OUT = Path(sys.argv[3])
FMETA = json.loads((FORM / "meta.json").read_text())

# ── Palette: NIR-optics ─────────────────────────────────────────────────────
INK = RGBColor(0x1A, 0x1D, 0x3A)      # dominant dark
RED = RGBColor(0xD7, 0x26, 0x3D)      # NIR accent / warnings
TEAL = RGBColor(0x1B, 0x99, 0x8B)     # "works" / linear
AMBER = RGBColor(0xF4, 0xA2, 0x59)
GREY = RGBColor(0x5B, 0x61, 0x70)
TINT = RGBColor(0xF2, 0xF4, 0xF8)
TINT2 = RGBColor(0xE4, 0xE8, 0xF1)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
LAV = RGBColor(0xC9, 0xCE, 0xEA)
HEAD, BODY = "Cambria", "Calibri"

prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
BLANK = prs.slide_layouts[6]
TEXTS = []          # (slide_no, text, font, pt, bold, w_in, h_in) for the fit check
N = [0]


def _hex(c):
    return str(c)


def new_slide(dark=False, kicker=None, title=None, notes=None):
    s = prs.slides.add_slide(BLANK)
    N[0] += 1
    bg = s.background.fill
    bg.solid()
    bg.fore_color.rgb = INK if dark else WHITE
    if title:
        if kicker:
            tb(s, 0.6, 0.32, 12.1, 0.3, kicker.upper(), 12, RED if not dark else AMBER, bold=True)
        tb(s, 0.6, 0.58, 12.1, 0.95, title, 28, WHITE if dark else INK, bold=True, font=HEAD)
    if not dark:
        tb(s, 0.6, 7.05, 8, 0.25, "EarSpectro · glycemico-pred · synthetic-data study", 10, GREY)
        tb(s, 11.9, 7.05, 0.83, 0.25, str(N[0]), 10, GREY, align=PP_ALIGN.RIGHT)
    if notes:
        s.notes_slide.notes_text_frame.text = notes
    return s


def tb(s, x, y, w, h, text, pt, color=INK, bold=False, font=BODY, align=PP_ALIGN.LEFT,
       anchor=MSO_ANCHOR.TOP, italic=False, name=None):
    """Text box. ``text`` may be a str or a list of paragraphs; a paragraph may be a
    str or a list of (text, {bold, color, italic, pt}) runs. A paragraph starting with
    '• ' becomes a real bullet."""
    shp = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    if name:
        shp.name = name
    tf = shp.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    paras = text if isinstance(text, list) else [text]
    for i, para in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        runs = para if isinstance(para, list) else [(para, {})]
        bullet = isinstance(runs[0][0], str) and runs[0][0].startswith("• ")
        if bullet:
            runs = [(runs[0][0][2:], runs[0][1])] + runs[1:]
            pPr = p._p.get_or_add_pPr()
            pPr.set("marL", str(Emu(Inches(0.22))))
            pPr.set("indent", str(-Emu(Inches(0.22))))
            pPr.append(parse_xml('<a:buChar xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" char="&#8226;"/>'))
        if len(paras) > 1:
            p.space_after = Pt(pt * 0.45)
        full = ""
        for t, o in runs:
            r = p.add_run()
            r.text = t
            full += t
            f = r.font
            f.name = o.get("font", font)
            f.size = Pt(o.get("pt", pt))
            f.bold = o.get("bold", bold)
            f.italic = o.get("italic", italic)
            f.color.rgb = o.get("color", color)
    # one aggregate entry per box is what matters for height; keep per-para entries tagged
    TEXTS.append((N[0], None, font, pt, bold, w, h, len(paras), [
        ("    " if (isinstance(pp, str) and pp.startswith("• ")) else "") +
        ("".join(t for t, _ in pp) if isinstance(pp, list) else pp) for pp in paras]))
    return shp


def box(s, x, y, w, h, fill=TINT, line=None, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.08, name=None):
    shp = s.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    shp.shadow.inherit = False
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        shp.adjustments[0] = radius
    if fill is None:
        shp.fill.background()
    else:
        shp.fill.solid()
        shp.fill.fore_color.rgb = fill
    if line is None:
        shp.line.fill.background()
    else:
        shp.line.color.rgb = line
        shp.line.width = Pt(1.25)
    if name:
        shp.name = name
    shp.text_frame.text = ""
    return shp


def label_box(s, x, y, w, h, title, sub=None, fill=TINT, tcolor=INK, scolor=GREY, tpt=14, spt=11,
              align=PP_ALIGN.CENTER, line=None):
    box(s, x, y, w, h, fill=fill, line=line)
    pad = 0.12
    if sub:
        tb(s, x + pad, y + 0.1, w - 2 * pad, h * 0.5 - 0.05, title, tpt, tcolor, bold=True, align=align,
           anchor=MSO_ANCHOR.BOTTOM)
        tb(s, x + pad, y + h * 0.5 + 0.04, w - 2 * pad, h * 0.5 - 0.12, sub, spt, scolor, align=align)
    else:
        tb(s, x + pad, y, w - 2 * pad, h, title, tpt, tcolor, bold=True, align=align, anchor=MSO_ANCHOR.MIDDLE)


def badge(s, x, y, d, text, fill=RED, color=WHITE, pt=13):
    c = box(s, x, y, d, d, fill=fill, shape=MSO_SHAPE.OVAL)
    tb(s, x, y, d, d, text, pt, color, bold=True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    return c


def arrow(s, x1, y1, x2, y2, color=GREY, width=1.75):
    c = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    c.line.color.rgb = color
    c.line.width = Pt(width)
    ln = c.line._get_or_add_ln()
    ln.append(parse_xml('<a:tailEnd xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
                        'type="triangle" w="med" len="med"/>'))
    return c


def formula(s, name, x, y, pt=20, max_w=None, alt=None):
    m = FMETA[name]
    w = m["w_px"] / 300 * pt / 26
    h = m["h_px"] / 300 * pt / 26
    if max_w and w > max_w:
        h, w = h * max_w / w, max_w
    pic = s.shapes.add_picture(str(FORM / f"{name}.png"), Inches(x), Inches(y), Inches(w), Inches(h))
    pic._element.nvPicPr.cNvPr.set("descr", alt or f"Formula: {name}")
    return w, h


def image(s, path, x, y, w=None, h=None, alt=""):
    pic = s.shapes.add_picture(str(path), Inches(x), Inches(y), Inches(w) if w else None, Inches(h) if h else None)
    pic._element.nvPicPr.cNvPr.set("descr", alt)
    return pic


def style_chart(ch, colors, legend=True, labels=True, numfmt='0.00', label_pt=11, axis_title=None,
                val_min=None, val_max=None, gap=60):
    ch.font.name = BODY
    ch.font.size = Pt(12)
    ch.font.color.rgb = GREY
    ch.has_legend = legend
    if legend:
        ch.legend.position = XL_LEGEND_POSITION.BOTTOM
        ch.legend.include_in_layout = False
        ch.legend.font.size = Pt(12)
    plot = ch.plots[0]
    if hasattr(plot, "gap_width"):
        plot.gap_width = gap
        plot.overlap = -10 if len(colors) > 1 else 0
    for ser, col in zip(plot.series, colors):
        fmt = ser.format
        if ch.chart_type in (XL_CHART_TYPE.LINE_MARKERS, XL_CHART_TYPE.LINE):
            fmt.line.color.rgb = col
            fmt.line.width = Pt(2.5)
            ser.smooth = False
            if ch.chart_type == XL_CHART_TYPE.LINE_MARKERS:
                ser.marker.format.fill.solid()
                ser.marker.format.fill.fore_color.rgb = col
                ser.marker.format.line.color.rgb = col
                ser.marker.size = 7
        else:
            fmt.fill.solid()
            fmt.fill.fore_color.rgb = col
    if labels:
        plot.has_data_labels = True
        dl = plot.data_labels
        dl.number_format = numfmt
        dl.number_format_is_linked = False
        dl.font.size = Pt(label_pt)
        dl.font.color.rgb = INK
        try:
            dl.position = XL_LABEL_POSITION.OUTSIDE_END
        except Exception:
            pass
    va = ch.value_axis
    va.has_major_gridlines = True
    va.major_gridlines.format.line.color.rgb = TINT2
    va.format.line.fill.background()
    va.tick_labels.font.size = Pt(12)
    if val_min is not None:
        va.minimum_scale = val_min
    if val_max is not None:
        va.maximum_scale = val_max
    if axis_title:
        va.has_title = True
        va.axis_title.text_frame.text = axis_title
        r = va.axis_title.text_frame.paragraphs[0].runs[0]
        r.font.size, r.font.bold, r.font.color.rgb = Pt(12), False, GREY
    ca = ch.category_axis
    ca.tick_labels.font.size = Pt(12)
    ca.format.line.color.rgb = TINT2
    ca.has_major_gridlines = False


def add_chart(s, kind, x, y, w, h, cats, series, colors, title=None, **kw):
    cd = CategoryChartData()
    cd.categories = cats
    for name, vals in series:
        cd.add_series(name, vals)
    gf = s.shapes.add_chart(kind, Inches(x), Inches(y), Inches(w), Inches(h), cd)
    ch = gf.chart
    if title:
        ch.has_title = True
        ch.chart_title.text_frame.text = title
        r = ch.chart_title.text_frame.paragraphs[0].runs[0]
        r.font.size, r.font.bold, r.font.color.rgb, r.font.name = Pt(14), True, INK, BODY
    else:
        ch.has_title = False
    style_chart(ch, colors, **kw)
    return ch


def table(s, x, y, w, rows, col_w, pt=12, header_fill=INK, row_h=0.36):
    t = s.shapes.add_table(len(rows), len(rows[0]), Inches(x), Inches(y), Inches(w),
                           Inches(row_h * len(rows))).table
    for j, cw in enumerate(col_w):
        t.columns[j].width = Inches(cw)
    for i, row in enumerate(rows):
        t.rows[i].height = Inches(row_h)
        for j, val in enumerate(row):
            c = t.cell(i, j)
            c.margin_left = c.margin_right = Inches(0.08)
            c.margin_top = c.margin_bottom = Inches(0.03)
            c.vertical_anchor = MSO_ANCHOR.MIDDLE
            c.fill.solid()
            c.fill.fore_color.rgb = header_fill if i == 0 else (TINT if i % 2 else WHITE)
            tf = c.text_frame
            tf.word_wrap = True
            tf.text = str(val)
            for p in tf.paragraphs:
                for r in p.runs:
                    r.font.size = Pt(pt)
                    r.font.name = BODY
                    r.font.bold = i == 0
                    r.font.color.rgb = WHITE if i == 0 else INK
            TEXTS.append((N[0], str(val), BODY, pt, i == 0, col_w[j] - 0.16, row_h - 0.06))
    return t


def section(num, title, sub):
    s = new_slide(dark=True)
    tb(s, 0.9, 1.95, 3.0, 1.7, num, 96, AMBER, bold=True, font=HEAD)
    tb(s, 0.9, 3.75, 11.5, 0.9, title, 40, WHITE, bold=True, font=HEAD)
    tb(s, 0.9, 4.7, 11.0, 0.9, sub, 18, LAV)
    return s


# ── Data ────────────────────────────────────────────────────────────────────
def scen(d):
    return pd.read_csv(REPO / f"outputs/{d}/scenarios/scenarios.csv").pivot_table(
        index="model", columns="scenario", values=["R2", "MAE", "clarke_A"])


SC = {d: scen(d) for d in ("ear5", "dense", "control_ear5")}
MX = {d: pd.read_csv(REPO / f"outputs/{d}/matrix/matrix_subject.csv") for d in ("ear5", "dense")}
NEST = pd.read_csv(REPO / "outputs/ear5/wavelengths/nested_size_curve.csv")
ALLW = pd.read_csv(REPO / "outputs/ear5/wavelengths/all_subsets.csv")
CAL = {d: pd.read_csv(REPO / f"outputs/{d}/calibration/calibration_curve.csv") for d in ("ear5", "dense")}
IMP = {d: pd.read_csv(REPO / f"outputs/{d}/explain/importance_summary.csv") for d in ("ear5", "dense")}
QC = pd.read_csv(REPO / "outputs/ear5/qc/qc_by_artifact.csv")
r2 = lambda d, m, sc: float(SC[d]["R2"][sc][m])  # noqa: E731

# ════════════════════════════════════════════════════════════════════════════
# 1. Title
s = new_slide(dark=True, notes="Overview deck of the EarSpectro glucose-prediction framework: formulas, architecture, "
                               "pipeline, data and first results. All results come from synthetic data.")
tb(s, 0.9, 1.0, 11, 0.4, "NON-INVASIVE GLUCOSE · NEAR-INFRARED SPECTROSCOPY", 14, AMBER, bold=True)
tb(s, 0.9, 1.6, 11.6, 2.0, "EarSpectro: predicting blood glucose from earlobe NIR spectra", 44, WHITE,
   bold=True, font=HEAD)
tb(s, 0.9, 3.75, 11, 0.9, "ML / DL framework, end-to-end pipeline, formulas, architectures and first results "
                          "on synthetic data", 20, LAV)
for i, (lab, col) in enumerate([("1050", LAV), ("1200", LAV), ("1450", AMBER), ("1550", RED), ("1650", RED)]):
    badge(s, 0.9 + i * 1.05, 5.25, 0.8, lab, fill=col, color=INK if col in (LAV, AMBER) else WHITE, pt=13)
tb(s, 6.3, 5.4, 6, 0.5, "nm · the five EarSpectro LED wavelengths", 14, LAV, anchor=MSO_ANCHOR.MIDDLE)
tb(s, 0.9, 6.55, 11.5, 0.4, "github.com/Nishanth-nishu/glycemico-pred  ·  October 2026", 13, LAV)

# 2. Research question
s = new_slide(kicker="Problem", title="Can earlobe NIR spectra predict glucose in people the model never saw?",
              notes="The task is framed as spectral disentanglement and generalisation, not plain regression.")
box(s, 0.6, 1.65, 12.1, 1.55, fill=TINT)
tb(s, 0.95, 1.85, 11.4, 1.2,
   "Do multi-wavelength NIR measurements from the earlobe carry reproducible glucose information for "
   "subject-independent prediction, and which preprocessing, wavelength set, model and calibration give "
   "the most robust mapping from ear spectra to reference glucose?", 18, INK, italic=True)
tb(s, 0.6, 3.55, 5.8, 0.35, "Regression formulation", 16, RED, bold=True)
formula(s, "problem", 0.6, 4.0, pt=22)
tb(s, 0.6, 4.75, 5.8, 1.6, ["• x: absorbance at p wavelengths (5 LEDs: 1050, 1200, 1450, 1550, 1650 nm)",
                            "• y: reference blood glucose (mg/dL)",
                            "• Glucose changes absorbance by ~0.1% of the total signal"], 14)
tb(s, 6.9, 3.55, 5.8, 0.35, "What the model should really learn", 16, RED, bold=True)
formula(s, "fxqc", 6.9, 4.0, pt=22)
tb(s, 6.9, 4.75, 5.8, 1.6, ["• x: the spectrum",
                            "• q: signal-quality information (QC score Q)",
                            "• c: calibration / subject information",
                            "• Output target: (Ĝ, Q, U), the prediction, quality and uncertainty"], 14)

# 3. Findings at a glance
s = new_slide(kicker="Summary", title="Five findings so far, on synthetic data",
              notes="Synthetic results validate the pipeline and probe design questions. They are not device accuracy.")
stats = [
    (f"{r2('control_ear5', 'svr', 'subject'):.2f}", "R² on unseen subjects (positive control)",
     "The pipeline finds glucose when the signal is there", TEAL),
    ("< 0", "R² with 5 LEDs at realistic glucose strength", "No model beats predicting the mean", RED),
    (f"{MX['dense'].R2.max():.2f}", "R² with a dense 1000–1700 nm spectrum", "Same physiology, many more channels",
     TEAL),
    (f"{r2('dense', 'ffnn', 'subject'):.2f}", "FFNN R² on unseen subjects",
     f"Same model scores {r2('dense', 'ffnn', 'random'):.2f} on a random split: random splits overstate accuracy", RED),
]
for i, (big, lab, sub, col) in enumerate(stats):
    x = 0.6 + i * 3.075
    box(s, x, 1.7, 2.85, 3.3, fill=TINT)
    tb(s, x + 0.2, 1.9, 2.45, 1.0, big, 40, col, bold=True, font=HEAD)
    tb(s, x + 0.2, 3.0, 2.45, 0.8, lab, 14, INK, bold=True)
    tb(s, x + 0.2, 3.95, 2.45, 0.9, sub, 13, GREY)
box(s, 0.6, 5.3, 12.1, 1.45, fill=None, line=TINT2)
badge(s, 0.85, 5.6, 0.55, "5", fill=AMBER, color=INK, pt=16)
tb(s, 1.6, 5.45, 10.9, 1.2, [[("Calibration gain is mostly the reference level. ", {"bold": True}),
                              ("A spectra-free control (mean of the calibration readings) matches every calibrated "
                               "model on 5 LEDs. On the dense spectrum the optical model adds ~4 mg/dL on top.", {})]],
   15, anchor=MSO_ANCHOR.MIDDLE)

# 4. Section divider
section("01", "Pipeline, data and methods", "Signal model · dataset · QC · preprocessing · features · models · "
                                            "evaluation · calibration")

# 5. End-to-end pipeline
s = new_slide(kicker="Architecture", title="End-to-end pipeline: from raw ear spectrum to (Ĝ, Q, U)",
              notes="Each box is a module in the earspectro package. Everything after the split is fitted on training "
                    "subjects only.")
stages = [
    ("Ear NIR acquisition", "5 LEDs · repeats", "data/io.py"),
    ("Reference sync", "nearest G within 5 min", "data/io.py"),
    ("Quality control", "Q score · reject < 0.5", "qc.py"),
    ("Preprocessing", "SG · SNV · MSC · d1/d2", "preprocessing.py"),
    ("Representation", "Track A spectrum · B features", "features.py"),
    ("Feature / λ selection", "corr · mRMR · RFE · nested", "selection.py"),
    ("Classical ML", "PLSR · SVR · RF · XGB · CatBoost", "models/classical.py"),
    ("Neural nets", "FFNN · 1-D CNN", "models/nets.py"),
    ("Subject-level validation", "random · subject · session", "splits.py"),
    ("Calibration", "0 / 1 / 2 / 3 / 5 points", "calibration.py"),
    ("Explainability", "permutation · SHAP", "explain.py"),
    ("Output", "Ĝ + Q (+ U planned)", "metrics.py · plots.py"),
]
bw, bh, gx = 1.78, 1.55, 0.284
for i, (t, sub, mod) in enumerate(stages):
    row, col = divmod(i, 6)
    if row == 1:
        col = 5 - col                       # snake: second row runs right-to-left
    x = 0.6 + col * (bw + gx)
    y = 1.75 + row * 2.45
    fill = INK if i in (2, 8, 9) else TINT
    tc, sc = (WHITE, LAV) if fill == INK else (INK, GREY)
    box(s, x, y, bw, bh, fill=fill)
    badge(s, x + 0.12, y + 0.12, 0.38, str(i + 1), fill=RED, pt=11)
    tb(s, x + 0.14, y + 0.58, bw - 0.28, 0.5, t, 12, tc, bold=True)
    tb(s, x + 0.14, y + 1.07, bw - 0.28, 0.45, sub, 11, sc)
    tb(s, x, y + bh + 0.06, bw, 0.25, mod, 10, GREY, align=PP_ALIGN.CENTER, italic=True)
    if i < 11:
        if i == 5:
            arrow(s, x + bw / 2, y + bh + 0.35, x + bw / 2, y + 2.45 - 0.05)
        elif row == 0:
            arrow(s, x + bw + 0.03, y + bh / 2, x + bw + gx - 0.03, y + bh / 2)
        else:
            arrow(s, x - 0.03, y + bh / 2, x - gx + 0.03, y + bh / 2)
tb(s, 0.6, 6.6, 12.1, 0.35, "Dark boxes: the stages that most affect whether results generalise "
                            "(quality gate, subject-level validation, calibration).", 12, GREY)

# 6. Signal model
s = new_slide(kicker="Signal model", title="The measured spectrum is a mixture; glucose is a tiny part of it",
              notes="Glucose adds roughly 0.002 OD per 100 mg/dL at its strongest band, against ~0.1 OD of "
                    "between-subject tissue variation.")
formula(s, "mixture", 0.6, 1.6, pt=24)
terms = [("s_glucose", "C–H/O–H overtones ~1530–1690 nm, ~1130 nm", RED),
         ("s_water", "dominant; 1450 nm band, shifts with temperature", INK),
         ("s_tissue", "lipid ~1210 nm, protein ~1180/1500 nm", INK),
         ("s_Hb", "falls off smoothly above 1000 nm", INK),
         ("s_scatter", "a·(λ/1000)^-b, varies per subject", INK),
         ("s_motion / s_sensor", "offsets, gain, tilt, ambient light", INK)]
for i, (t, d, col) in enumerate(terms):
    y = 2.55 + i * 0.68
    box(s, 0.6, y, 5.5, 0.58, fill=TINT)
    tb(s, 0.8, y + 0.04, 1.8, 0.5, t, 14, col, bold=True, anchor=MSO_ANCHOR.MIDDLE)
    tb(s, 2.65, y + 0.04, 3.35, 0.5, d, 12, GREY, anchor=MSO_ANCHOR.MIDDLE)
image(s, REPO / "data/synthetic_dense.spectra.png", 6.45, 2.5, w=6.3,
      alt="Left: median absorbance spectrum per subject. Right: change in absorbance over one OGTT session.")
tb(s, 6.45, 5.45, 6.3, 0.8, "Left: subjects differ by far more than glucose ever moves the spectrum. "
                            "Right: change in one session over the glucose test, mostly water/temperature.", 12, GREY)

# 7. Synthetic generator
s = new_slide(kicker="Dataset", title="Synthetic ear-NIR generator (stand-in until real recordings exist)",
              notes="Modified Beer–Lambert style absorbance with subject, session and timepoint effects. "
                    "Glucose band strength gamma is a free parameter.")
formula(s, "absorb", 0.6, 1.62, pt=18, max_w=12.1)
tb(s, 0.6, 2.2, 12.1, 0.5, "L_s path length · w, l, p, h tissue fractions · δT skin-temperature shift · γ glucose band "
                           "strength · g_s subject response · a, b scatter · o, τ gain and tilt · ε sensor noise", 12, GREY)
tb(s, 0.6, 2.9, 5.6, 0.35, "Glucose trajectory: OGTT-shaped", 16, RED, bold=True)
formula(s, "ogtt", 0.6, 3.35, pt=20)
tb(s, 0.6, 4.35, 5.6, 2.3, ["• Normoglycaemic: G₀ ≈ 92, ΔG ≈ 55, peak ≈ 45 min",
                            "• Diabetic (30%): G₀ ≈ 140, ΔG ≈ 110, peak ≈ 70 min",
                            "• Reference meter error: 5% CV",
                            "• Confounder: skin temperature drifts after the glucose load"], 14)
rows = [["Level", "What varies"],
        ["Subject (40)", "path length, tissue, Hb, scatter, glucose response, age, sex, skin tone"],
        ["Session (2 per subject)", "LED gain, placement tilt, temperature offset, glucose curve"],
        ["Timepoint (16 × 10 min)", "glucose, temperature drift"],
        ["Repeat (3 per timepoint)", "sensor noise; 3% motion / ambient / saturation / dropout"]]
table(s, 6.6, 2.95, 6.1, rows, [1.95, 4.15], pt=12, row_h=0.62)
tb(s, 6.6, 6.2, 6.1, 0.5, "40 × 2 × 16 × 3 = 3,840 spectra per dataset", 14, INK, bold=True)

# 8. Dataset variants + references
s = new_slide(kicker="Dataset", title="Three dataset variants, each answering a different question",
              notes="Band positions follow published NIR assignments; values are approximations, not measured spectra.")
variants = [("ear5", "The device as designed", ["5 LEDs: 1050–1650 nm", "γ = 2×10⁻⁵ OD per mg/dL", "noise 1.5×10⁻³ OD",
                                                 "temperature confounder on"], INK),
            ("dense", "What a spectrometer would see", ["141 points, 1000–1700 nm, 5 nm step", "same physiology and γ",
                                                        "same confounder"], TEAL),
            ("control_ear5", "Positive control", ["5 LEDs", "γ = 1×10⁻⁴ (5× stronger)", "confounder off",
                                                  "proves the pipeline can find signal"], RED)]
for i, (name, q, items, col) in enumerate(variants):
    x = 0.6 + i * 4.1
    box(s, x, 1.65, 3.85, 2.75, fill=TINT)
    tb(s, x + 0.25, 1.82, 3.4, 0.45, name, 20, col, bold=True, font=HEAD)
    tb(s, x + 0.25, 2.3, 3.4, 0.35, q, 13, GREY, italic=True)
    tb(s, x + 0.25, 2.75, 3.4, 1.6, ["• " + it for it in items], 13)
tb(s, 0.6, 4.65, 12.1, 0.35, "Where the numbers come from", 16, RED, bold=True)
tb(s, 0.6, 5.05, 12.1, 1.8, [
    "• Glucose NIR band positions: Amerov, Chen & Arnold (2004), Applied Spectroscopy 58(10) — molar absorptivities of glucose, first overtone and combination regions",
    "• Water absorption magnitudes: rough literature values (e.g. Hale & Querry, 1973; citation not auto-verified)",
    "• Lipid, protein, Hb, scatter terms: generic NIR tissue-optics shapes, deliberately approximate",
    "• No real EarSpectro recordings yet. Real data plugs in through the same CSV schema (next slide)"], 13)

# 9. Schema + sync
s = new_slide(kicker="Data contract", title="One row per spectrum, paired with its reference glucose",
              notes="Metadata is retained for confounding and subgroup analysis and is never fed to the models.")
rows = [["Column", "Meaning"], ["subject_id, session_id", "identifiers (required)"],
        ["timestamp", "acquisition time (required for sync)"], ["glucose_ref", "reference glucose, mg/dL (target)"],
        ["A_1050 … A_1650", "absorbance per wavelength, −log₁₀(I/I₀)"],
        ["timepoint, repeat", "repeated-measurement structure"],
        ["age, sex, skin_tone, …", "metadata for subgroup analysis only"]]
table(s, 0.6, 1.7, 6.4, rows, [2.4, 4.0], pt=13, row_h=0.55)
tb(s, 7.4, 1.7, 5.3, 0.35, "Reference synchronisation", 16, RED, bold=True)
formula(s, "sync", 7.4, 2.2, pt=18, max_w=5.3)
tb(s, 7.4, 3.0, 5.3, 1.4, ["• Pair X(t) with G(t), never X(t₁) with G(t₂)",
                           "• Spectra with no reading within 5 min are dropped",
                           "• The lag is kept as ref_lag_s for error analysis"], 14)
box(s, 7.4, 4.7, 5.3, 1.55, fill=TINT)
tb(s, 7.6, 4.85, 4.9, 1.3, [[("Same format for real data: ", {"bold": True}),
                             ("DATA=real.csv sbatch slurm/run_all.sh reruns every experiment on it.", {})]], 14)

# 10. QC
s = new_slide(kicker="Stage 2 · Quality control", title="A quality score Q gates every spectrum before modelling",
              notes="All checks are unsupervised and fitted on the training fold. One bad property is enough to "
                    "reject a spectrum because Q is a product.")
formula(s, "robustz", 0.6, 1.65, pt=20)
formula(s, "qsoft", 0.6, 2.55, pt=20)
formula(s, "qprod", 0.6, 3.45, pt=20)
checks = ["missing wavelengths", "absorbance out of range", "saturation (clipped values)",
          "abnormal amplitude", "spectral discontinuity", "disagreeing repeats"]
for i, c in enumerate(checks):
    row, col = divmod(i, 2)
    x, y = 0.6 + col * 2.95, 4.35 + row * 0.75
    box(s, x, y, 2.8, 0.6, fill=TINT)
    tb(s, x + 0.15, y, 2.5, 0.6, c, 13, INK, anchor=MSO_ANCHOR.MIDDLE)
q = QC.set_index("artifact")
cats = ["dropout", "saturation", "ambient", "motion", "none"]
add_chart(s, XL_CHART_TYPE.COLUMN_CLUSTERED, 6.75, 1.6, 5.95, 4.8, ["dropout", "saturation", "ambient", "motion",
                                                                     "clean"],
          [("Rejected (%)", [round(float(q.loc[c, "rejected"]), 1) for c in cats])], [RED],
          title="Spectra rejected by QC, by injected artifact (ear5)", legend=False, numfmt='0.0"%"',
          val_min=0, val_max=110)
tb(s, 6.75, 6.45, 5.95, 0.4, "Clean spectra rejected: 0.05% (2 of 3,732).", 12, GREY)

# 11. Preprocessing
s = new_slide(kicker="Stage 3 · Preprocessing", title="Ten preprocessing variants, compared rather than assumed",
              notes="All transforms run inside the sklearn Pipeline, so anything with state (MSC reference) is fitted "
                    "on training subjects only.")
cards = [("SNV", "snv", "removes per-spectrum offset and scale (Barnes et al., 1989)"),
         ("MSC", "msc", "regress each spectrum on the training mean (Geladi et al., 1985)"),
         ("Savitzky–Golay", "sg", "local polynomial smoothing (Savitzky & Golay, 1964)"),
         ("Derivatives", "deriv", "remove broad baselines, sharpen bands; amplify noise"),
         ("Detrend", "detrend", "remove a linear baseline in λ per spectrum"),
         ]
for i, (t, f, d) in enumerate(cards):
    row, col = divmod(i, 3)
    x, y = 0.6 + col * 4.1, 1.65 + row * 2.45
    box(s, x, y, 3.85, 2.2, fill=TINT)
    tb(s, x + 0.25, y + 0.15, 3.4, 0.4, t, 16, RED, bold=True)
    formula(s, f, x + 0.25, y + 0.65, pt=18, max_w=3.35)
    tb(s, x + 0.25, y + 1.5, 3.4, 0.65, d, 12, GREY)
x, y = 0.6 + 2 * 4.1, 1.65 + 2.45
box(s, x, y, 3.85, 2.2, fill=INK)
tb(s, x + 0.25, y + 0.15, 3.4, 0.4, "Variants tested", 16, AMBER, bold=True)
tb(s, x + 0.25, y + 0.6, 3.4, 1.5, "raw · detrend · sg · snv · msc · d1 · d2 · sg+snv · sg+msc · d1+snv", 14, WHITE)
tb(s, 0.6, 6.5, 12.1, 0.4, "On the sparse 5-LED grid, SG windows shrink to the available points and derivatives use "
                           "finite differences on the true wavelength spacing.", 12, GREY)

# 12. Representations
s = new_slide(kicker="Stage 4 · Representation", title="Two tracks: learn from the spectrum, or from engineered features",
              notes="For 5 wavelengths Track B gives 45 features: 5 raw, 30 pairwise, 4 slopes, 3 curvatures, "
                    "area, mean and std.")
box(s, 0.6, 1.65, 4.2, 4.95, fill=TINT)
tb(s, 0.85, 1.85, 3.7, 0.4, "Track A · full spectrum", 18, INK, bold=True, font=HEAD)
tb(s, 0.85, 2.4, 3.7, 1.0, "X = [A₁₀₅₀, A₁₂₀₀, A₁₄₅₀, A₁₅₅₀, A₁₆₅₀] or 141 dense points", 14)
tb(s, 0.85, 3.4, 3.7, 3.0, ["• Used by every model, including the 1-D CNN",
                            "• Keeps spectral order for convolution",
                            "• Preprocessing applied first"], 14)
box(s, 5.1, 1.65, 7.6, 4.95, fill=TINT)
tb(s, 5.35, 1.85, 7.1, 0.4, "Track B · engineered features (45 for 5 λ)", 18, INK, bold=True, font=HEAD)
feats = [("ratio", "ratio"), ("diff", "difference"), ("ndiff", "normalised difference"), ("slope", "local slope"),
         ("curv", "local curvature")]
for i, (f, lab) in enumerate(feats):
    row, col = divmod(i, 2)
    x, y = 5.35 + col * 3.6, 2.45 + row * 1.25
    tb(s, x, y, 3.4, 0.3, lab, 12, GREY)
    formula(s, f, x, y + 0.3, pt=17, max_w=3.4)
tb(s, 8.95, 4.95, 3.5, 0.9, "+ band area, mean, std; dense spectra are first averaged into 8 bands", 12, GREY)

# 13. Selection
s = new_slide(kicker="Stages 5–6 · Selection", title="Feature and wavelength selection always happen inside training folds",
              notes="The all-subsets table is descriptive only. Picking its best row would be selection on the test folds.")
tb(s, 0.6, 1.6, 6, 0.35, "Feature selection methods", 16, RED, bold=True)
tb(s, 0.6, 2.0, 6, 0.3, "Correlation filter: keep top-k by", 13, GREY)
formula(s, "corr", 0.6, 2.35, pt=17, max_w=5.8)
tb(s, 0.6, 3.25, 6, 0.3, "mRMR (greedy): relevance minus redundancy", 13, GREY)
formula(s, "mrmr", 0.6, 3.6, pt=17, max_w=5.8)
tb(s, 0.6, 4.6, 6, 0.6, "RFE: drop the weakest 20% by extra-trees importance, refit, repeat", 13, GREY)
tb(s, 7.0, 1.6, 5.7, 0.35, "Wavelength experiments (5 LEDs)", 16, RED, bold=True)
exps = [("A", "Single wavelength", "5 models: 1050 → G, …, 1650 → G"),
        ("B", "Pairs", "10 models: (λᵢ, λⱼ) → G"),
        ("C", "Growing sets", "all 31 subsets, sizes 1 → 5")]
for i, (k, t, d) in enumerate(exps):
    y = 2.05 + i * 0.85
    badge(s, 7.0, y + 0.08, 0.5, k, fill=INK, pt=14)
    tb(s, 7.7, y, 5.0, 0.35, t, 14, INK, bold=True)
    tb(s, 7.7, y + 0.35, 5.0, 0.35, d, 12, GREY)
box(s, 7.0, 4.75, 5.7, 1.85, fill=TINT)
tb(s, 7.2, 4.85, 5.3, 0.35, "Nested selection (honest curve)", 14, INK, bold=True)
steps = ["outer fold: hold out subjects", "inner 3-fold CV picks best subset of size k", "score it on held-out subjects"]
for i, st in enumerate(steps):
    x = 7.2 + i * 1.8
    box(s, x, 5.3, 1.6, 1.1, fill=WHITE)
    tb(s, x + 0.1, 5.3, 1.4, 1.1, st, 11, INK, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    if i < 2:
        arrow(s, x + 1.62, 5.85, x + 1.78, 5.85)

# 14. Model ladder
s = new_slide(kicker="Stages 7–9 · Models", title="A model ladder: each rung asks whether extra complexity pays off",
              notes="Hyper-parameters for PLSR (components) and SVR (C, gamma) are tuned with inner GroupKFold over "
                    "training subjects.")
ladder = [("Mean", "reference: Ĝ = mean(G)", None),
          ("Linear / Ridge", "is the relation roughly linear?", "ridge"),
          ("PLSR", "linear, built for correlated spectra (Wold et al., 2001)", "pls"),
          ("SVR (RBF)", "does a nonlinear kernel help?", "svr"),
          ("RF · XGBoost · CatBoost", "do feature interactions help?", "boost"),
          ("FFNN", "does a learned representation beat engineering?", None),
          ("1-D CNN", "can local spectral shape be learned directly?", "conv")]
for i, (t, q, f) in enumerate(ladder):
    y = 1.62 + i * 0.68
    x = 0.6 + i * 0.35
    box(s, x, y, 3.2, 0.56, fill=INK if i >= 5 else TINT)
    tb(s, x + 0.15, y, 2.9, 0.56, t, 14, WHITE if i >= 5 else INK, bold=True, anchor=MSO_ANCHOR.MIDDLE)
    tb(s, x + 3.35, y, 3.5, 0.56, q, 12, GREY, anchor=MSO_ANCHOR.MIDDLE)
    if f:
        formula(s, f, 9.4, y + 0.06, pt=15, max_w=3.3)
tb(s, 0.6, 6.55, 12.1, 0.35, "Transfer learning (rung 8) is planned once a relevant pretraining spectral corpus is "
                                    "chosen.", 12, GREY)

# 15. Neural architectures
s = new_slide(kicker="Stages 8–9 · Neural networks", title="FFNN and 1-D CNN architectures",
              notes="Both are wrapped as sklearn regressors. Inputs and targets are standardised inside fit.")
tb(s, 0.6, 1.55, 6, 0.35, "FFNN (baseline network)", 16, RED, bold=True)
ff = [("Input", "p"), ("Dense 128", "ReLU + Dropout 0.2"), ("Dense 64", "ReLU"), ("Dense 32", "ReLU"), ("Output", "Ĝ")]
for i, (t, sub) in enumerate(ff):
    x = 0.6 + i * 1.62
    label_box(s, x, 2.0, 1.38, 1.15, t, sub, fill=INK if t in ("Input", "Output") else TINT,
              tcolor=WHITE if t in ("Input", "Output") else INK, scolor=LAV if t in ("Input", "Output") else GREY,
              tpt=13, spt=10)
    if i < 4:
        arrow(s, x + 1.4, 2.575, x + 1.6, 2.575)
tb(s, 0.6, 3.5, 6, 0.35, "1-D CNN (main deep model)", 16, RED, bold=True)
cnn = [("Spectrum", "1 × p"), ("Conv 32", "k=7 (3 if p<15) BN ReLU"), ("Conv 64", "k=3 BN ReLU"),
       ("MaxPool 2", "if p ≥ 8"), ("Conv 64", "k=3 BN ReLU"), ("Global pool", "mean ‖ max"), ("Dense 64", "ReLU, Drop 0.2"),
       ("Output", "Ĝ")]
for i, (t, sub) in enumerate(cnn):
    x = 0.6 + i * 1.55
    dark = t in ("Spectrum", "Output")
    label_box(s, x, 3.95, 1.35, 1.25, t, sub, fill=INK if dark else TINT, tcolor=WHITE if dark else INK,
              scolor=LAV if dark else GREY, tpt=12, spt=10)
    if i < 7:
        arrow(s, x + 1.37, 4.575, x + 1.53, 4.575)
formula(s, "conv", 0.6, 5.55, pt=18)
box(s, 5.0, 5.45, 7.7, 1.4, fill=TINT)
tb(s, 5.2, 5.55, 7.3, 1.25, [[("Training: ", {"bold": True}),
                              ("AdamW (lr 1e-3, wd 1e-4), SmoothL1 loss (β = 0.5) on standardised glucose, batch 64, "
                               "≤ 400 epochs, ReduceLROnPlateau, early stopping (patience 40) on a held-out 15% of the "
                               "training subjects.", {})]], 13)

# 16. Evaluation design
s = new_slide(kicker="Stages 10 · Validation", title="Three evaluation scenarios; unseen subjects is the primary result",
              notes="Squares stand for subjects. Random splits put the same person in train and test, so a model can "
                    "memorise the person instead of glucose.")
scen_rows = [("A · Random split", "measurements shuffled; same subject in train and test", "sanity check only", RED),
             ("B · Subject split", "GroupKFold on subject_id; test people never seen", "primary result", TEAL),
             ("C · Session split", "train on day 1, test on day 2 of the same people", "wearable reality", AMBER)]
for i, (t, d, tag, col) in enumerate(scen_rows):
    y = 1.65 + i * 1.3
    tb(s, 0.6, y, 3.3, 0.4, t, 16, INK, bold=True)
    tb(s, 0.6, y + 0.42, 3.3, 0.75, d, 12, GREY)
    for j in range(10):
        if i == 0:
            fill = TEAL if (j * 7) % 10 < 8 else RED
            fill2 = RED if j in (2, 6) else TEAL
        elif i == 1:
            fill = fill2 = TEAL if j < 8 else RED
        else:
            fill, fill2 = TEAL, RED
        box(s, 4.15 + j * 0.52, y + 0.12, 0.42, 0.42, fill=fill, radius=0.2)
        box(s, 4.15 + j * 0.52, y + 0.6, 0.42, 0.42, fill=fill2, radius=0.2)
    tb(s, 9.5, y + 0.3, 1.8, 0.5, tag, 13, col, bold=True, anchor=MSO_ANCHOR.MIDDLE)
tb(s, 4.15, 5.55, 7.0, 0.3, [[("■ ", {"color": TEAL}), ("train   ", {}), ("■ ", {"color": RED}), ("test   ", {}),
                              ("top row: session 1 · bottom row: session 2 · 10 example subjects", {})]], 11, GREY)
formula(s, "split", 0.6, 5.95, pt=20)
tb(s, 4.15, 5.95, 8.55, 0.95, ["• Leak check aborts the run if any subject is in both train and test",
                               "• Preprocessing, QC, scalers, selectors and tuning are all fitted inside each training fold"],
   13)

# 17. Metrics
s = new_slide(kicker="Metrics", title="Accuracy, agreement and clinical-risk metrics",
              notes="R² alone can hide clinically unacceptable errors, so every result also reports Clarke zones and "
                    "per-subject error.")
mets = [("mae", "Mean absolute error"), ("rmse", "Root mean squared error"), ("r2", "Coefficient of determination"),
        ("mard", "Mean absolute relative difference"), ("loa", "Bland–Altman agreement"),
        ("mae_k", "Subgroup MAE")]
for i, (f, lab) in enumerate(mets):
    row, col = divmod(i, 3)
    x, y = 0.6 + col * 4.1, 1.6 + row * 2.15
    box(s, x, y, 3.85, 1.95, fill=TINT)
    tb(s, x + 0.2, y + 0.15, 3.45, 0.35, lab, 13, GREY, bold=True)
    formula(s, f, x + 0.2, y + 0.65, pt=18, max_w=3.45)
box(s, 0.6, 5.95, 12.1, 0.9, fill=INK)
tb(s, 0.85, 5.95, 11.6, 0.9, [[("Clarke error grid (Clarke et al., 1987): ", {"bold": True, "color": AMBER}),
                              ("zone A within ±20% (or both < 70 mg/dL) · B benign · C–E would lead to wrong treatment. "
                               "Per-subject MAE (median, 90th percentile) is reported too.", {"color": WHITE})]],
   14, anchor=MSO_ANCHOR.MIDDLE)

# 18. Calibration
s = new_slide(kicker="Stage 11 · Calibration", title="Per-session calibration, with a control that ignores the spectra",
              notes="Every k is scored on the same evaluation timepoints (index 5 onward), so the curves are comparable.")
items = [("Offset (k ≥ 1)", "cal_off"), ("Shrunk linear (k ≥ 2), λ = 50", "cal_lin"), ("ref_only control", "cal_ref")]
for i, (t, f) in enumerate(items):
    y = 1.6 + i * 1.35
    tb(s, 0.6, y, 6, 0.35, t, 15, RED if i == 2 else INK, bold=True)
    formula(s, f, 0.6, y + 0.4, pt=18, max_w=6.2)
tb(s, 0.6, 5.7, 6.2, 1.0, "If a calibrated model doesn't beat ref_only at the same k, the gain came from knowing the "
                          "recent glucose level, not from the optics.", 14, INK, italic=True)
tb(s, 7.2, 1.6, 5.5, 0.35, "Protocol on one OGTT session", 15, INK, bold=True)
for j in range(16):
    x = 7.2 + j * 0.34
    fill = AMBER if j < 5 else (TEAL if j >= 5 else TINT)
    box(s, x, 2.2, 0.27, 0.9, fill=fill, radius=0.25)
tb(s, 7.2, 3.2, 1.7, 0.6, "first k used to calibrate", 11, GREY)
tb(s, 8.95, 3.2, 3.7, 0.6, "timepoints 5–15: scored for every k", 11, GREY)
tb(s, 7.2, 4.1, 5.5, 2.4, ["• k ∈ {0, 1, 2, 3, 5} reference readings per session",
                           "• Repeats at a timepoint are averaged into one calibration point",
                           "• Sensor is re-placed each day, so calibration is per session",
                           "• The question is the calibration burden, not the lowest error"], 13)

# 19. Section divider
section("02", "Results (synthetic data)", "Validation scenarios · signal strength · preprocessing · wavelengths · "
                                         "calibration · explainability · clinical view")

# 20. H5: random vs subject
s = new_slide(kicker="H5 · Evaluation scenario", title="Random splits flatter models; unseen subjects tell the truth",
              notes="Dense-spectrum dataset. Positive R² on a random split turns negative for most models on unseen "
                    "subjects.")
models = ["plsr", "svr", "catboost", "ffnn", "cnn1d"]
names = ["PLSR", "SVR", "CatBoost", "FFNN", "1-D CNN"]
add_chart(s, XL_CHART_TYPE.COLUMN_CLUSTERED, 0.6, 1.55, 8.3, 5.3, names,
          [("Random split", [round(r2("dense", m, "random"), 2) for m in models]),
           ("Unseen session", [round(r2("dense", m, "session"), 2) for m in models]),
           ("Unseen subjects", [round(r2("dense", m, "subject"), 2) for m in models])],
          [LAV, AMBER, INK], title="R² by evaluation scenario (dense spectrum, SNV)", val_min=-0.8, val_max=0.8,
          label_pt=10, gap=40)
box(s, 9.2, 1.7, 3.5, 5.0, fill=TINT)
tb(s, 9.45, 1.9, 3.0, 0.9, f"{r2('dense', 'ffnn', 'random'):.2f} → {r2('dense', 'ffnn', 'subject'):.2f}", 28, RED,
   bold=True, font=HEAD)
tb(s, 9.45, 2.8, 3.0, 0.6, "FFNN R², random → unseen subjects", 13, INK, bold=True)
tb(s, 9.45, 3.55, 3.0, 3.0, ["• CatBoost: 0.51 → −0.43",
                             "• Only PLSR stays positive on new people (0.23)",
                             "• A random split rewards memorising the person"], 13)

# 21. Signal strength / channels
s = new_slide(kicker="H2 · Signal and channels", title="Five LEDs can't untangle glucose; a dense spectrum partly can",
              notes="Unseen-subject R² for the same models across the three datasets. Mean predictor shown as zero line.")
models = ["plsr", "svr", "catboost", "ffnn"]
names = ["PLSR", "SVR", "CatBoost", "FFNN"]
add_chart(s, XL_CHART_TYPE.COLUMN_CLUSTERED, 0.6, 1.55, 8.3, 5.3, names,
          [("5 LEDs (ear5)", [round(r2("ear5", m, "subject"), 2) for m in models]),
           ("Dense spectrum", [round(r2("dense", m, "subject"), 2) for m in models]),
           ("5 LEDs, 5× signal (control)", [round(r2("control_ear5", m, "subject"), 2) for m in models])],
          [RED, TEAL, INK], title="R² on unseen subjects", val_min=-0.6, val_max=0.7, label_pt=10, gap=40)
box(s, 9.2, 1.7, 3.5, 5.0, fill=TINT)
tb(s, 9.45, 1.9, 3.0, 4.7, [[("Control works: ", {"bold": True}), ("linear models and SVR reach R² ≈ 0.5, so the "
                                                                    "pipeline does find signal.", {})],
                            [("ear5 fails: ", {"bold": True}), ("5 channels vs ~8 nuisance factors leaves glucose "
                                                                "unidentifiable at realistic strength.", {})],
                            [("Dense helps: ", {"bold": True}), (f"best R² {MX['dense'].R2.max():.2f} "
                                                                 "(linear, detrend). Design lever: more wavelengths "
                                                                 "or a reference channel.", {})]], 13)

# 22. Preprocessing results
s = new_slide(kicker="H1 · Preprocessing", title="Preprocessing barely moves linear models but makes or breaks trees",
              notes="Spread = worst minus best MAE across the 10 preprocessing variants, unseen subjects, dense spectrum.")
m = MX["dense"]
m = m[m.representation == "spectrum"]
sp = m.groupby("model").MAE.agg(lambda v: v.max() - v.min())
order = ["linear", "plsr", "svr", "cnn1d", "ffnn", "rf", "xgboost", "catboost"]
lab = {"linear": "Linear", "plsr": "PLSR", "svr": "SVR", "cnn1d": "1-D CNN", "ffnn": "FFNN", "rf": "RF",
       "xgboost": "XGBoost", "catboost": "CatBoost"}
raw = m[m.preprocessing == "raw"].set_index("model").MAE
best = m.groupby("model").MAE.min()
add_chart(s, XL_CHART_TYPE.COLUMN_CLUSTERED, 0.6, 1.55, 7.0, 4.4, [lab[o] for o in order],
          [("Raw spectrum", [round(float(raw[o]), 1) for o in order]),
           ("Best preprocessing", [round(float(best[o]), 1) for o in order])], [LAV, TEAL],
          title="MAE on unseen subjects (dense spectrum)", numfmt="0.0", label_pt=9, val_min=25, val_max=50, gap=50)
add_chart(s, XL_CHART_TYPE.BAR_CLUSTERED, 7.85, 1.55, 4.85, 4.4, [lab[o] for o in order],
          [("MAE spread", [round(float(sp[o]), 1) for o in order])], [INK],
          title="MAE spread across variants (mg/dL)", legend=False, numfmt="0.0", gap=50)
tb(s, 0.6, 6.05, 12.1, 0.6, "Best dense results use detrend or d1+SNV. d1+SNV is what makes the tree models "
                              "competitive at all (CatBoost 48.2 → 32.6).", 12, GREY)

# 23. Wavelengths
s = new_slide(kicker="H2 · Wavelength count", title="With 5 LEDs, more wavelengths don't help at realistic signal",
              notes="Nested curve: the best subset of each size is chosen on inner folds of training subjects, then "
                    "scored on held-out subjects. Dashed level: mean predictor (MAE 43.1).")
nst = NEST.pivot_table(index="n_wavelengths", columns="model", values="MAE")
add_chart(s, XL_CHART_TYPE.LINE_MARKERS, 0.6, 1.55, 6.2, 5.0, [str(k) for k in nst.index],
          [("PLSR", [round(v, 1) for v in nst["plsr"]]), ("CatBoost", [round(v, 1) for v in nst["catboost"]]),
           ("Mean predictor", [43.1] * len(nst))], [TEAL, RED, GREY],
          title="Nested: MAE vs number of wavelengths", numfmt="0.0", label_pt=10,
          val_min=40, val_max=56, axis_title="MAE (mg/dL)")
single = ALLW[(ALLW.n_wavelengths == 1) & (ALLW.model == "plsr")].sort_values("wavelengths")
add_chart(s, XL_CHART_TYPE.COLUMN_CLUSTERED, 7.1, 1.55, 5.6, 5.0, [f"{int(w)} nm" for w in single.wavelengths],
          [("PLSR, single wavelength", [round(v, 1) for v in single.MAE])], [INK],
          title="Single-wavelength PLSR MAE (mg/dL)", legend=False, numfmt="0.0", val_min=40, val_max=46)
tb(s, 0.6, 6.6, 12.1, 0.35, "Every subset stays at or above the mean predictor; the nested picks change fold to fold, "
                            "a sign there is no stable informative subset.", 12, GREY)

# 24. Calibration results
s = new_slide(kicker="H6 · Calibration", title="Calibration gains: mostly the reference level, a little optics",
              notes="PLSR, unseen subjects. ref_only predicts the mean of the calibration readings and ignores spectra.")
for i, d in enumerate(("ear5", "dense")):
    c = CAL[d][CAL[d].model == "plsr"].pivot_table(index="k_cal", columns="method", values="MAE")
    add_chart(s, XL_CHART_TYPE.LINE_MARKERS, 0.6 + i * 6.15, 1.55, 5.95, 4.6, [str(k) for k in c.index],
              [("Offset", [round(v, 1) for v in c["offset"]]), ("Shrunk linear", [round(v, 1) for v in c["linear"]]),
               ("ref_only (no spectra)", [round(v, 1) for v in c["ref_only"]])], [TEAL, INK, RED],
              title=("5 LEDs (ear5)" if d == "ear5" else "Dense spectrum") + ": PLSR MAE vs calibration points",
              numfmt="0.0", label_pt=9, val_min=20, val_max=55, axis_title="MAE (mg/dL)")
tb(s, 0.6, 6.25, 12.1, 0.65, "ear5: ref_only (32.8) matches calibrated PLSR (33.6) at k = 5, so the gain is the "
                             "reference level. Dense: calibrated PLSR reaches 25.5 vs 29.7 for ref_only, about 4 mg/dL "
                             "from the optics.", 13, INK)

# 25. Explainability
s = new_slide(kicker="Explainability", title="What the models lean on: water-band flank more than glucose bands",
              notes="Permutation importance on held-out subjects, averaged over 5 folds. Dense PLSR peaks at "
                    "1440–1500 nm, the flank of the water band where the temperature confounder acts.")
imp = IMP["dense"]
pl = imp[(imp.model == "plsr") & (imp.method == "permutation_dMAE")].sort_values("wavelength")
add_chart(s, XL_CHART_TYPE.LINE, 0.6, 1.55, 7.6, 4.6, [str(int(w)) for w in pl.wavelength],
          [("ΔMAE when permuted", [round(v, 1) for v in pl["mean"]])], [INK],
          title="Dense PLSR: permutation importance by wavelength (nm)", legend=False, labels=False,
          axis_title="ΔMAE (mg/dL)")
cax = s.shapes[-1].chart.category_axis._element
skip = parse_xml('<c:tickLblSkip xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart" val="20"/>')
nm = cax.find("{http://schemas.openxmlformats.org/drawingml/2006/chart}noMultiLvlLbl")
nm.addprevious(skip) if nm is not None else cax.append(skip)
tb(s, 0.6, 6.2, 7.6, 0.7, "Peak at 1440–1500 nm (water band flank, temperature-sensitive) rather than the 1590 nm "
                          "glucose band: part of the signal is the confounder.", 12, GREY)
e5 = IMP["ear5"]
cb = e5[(e5.model == "catboost")].pivot_table(index="wavelength", columns="method", values="mean")
add_chart(s, XL_CHART_TYPE.COLUMN_CLUSTERED, 8.5, 1.55, 4.2, 4.6, [str(int(w)) for w in cb.index],
          [("mean |SHAP|", [round(v, 1) for v in cb["mean_abs_shap"]]),
           ("ΔMAE permuted", [round(v, 1) for v in cb["permutation_dMAE"]])], [AMBER, RED],
          title="ear5 CatBoost", numfmt="0.0", label_pt=9, gap=40)
tb(s, 8.5, 6.2, 4.2, 0.7, "SHAP says 1450 nm matters, yet permuting any wavelength improves MAE on new people.",
   12, GREY)

# 26. Clinical view
s = new_slide(kicker="Clinical view", title="Clarke error grid on unseen subjects",
              notes="Zone A: clinically accurate; B: benign; C–E: would lead to wrong treatment decisions.")
for i, (d, mdl, cap) in enumerate([("dense", "plsr", "Dense spectrum · PLSR (SNV)"),
                                   ("control_ear5", "svr", "Positive control · SVR (MSC)")]):
    x = 0.6 + i * 6.25
    image(s, REPO / f"outputs/{d}/scenarios/clarke_{mdl}_subject.png", x + 0.5, 1.55, h=4.65,
          alt=f"Clarke error grid, {cap}, unseen subjects.")
    za = float(SC[d]["clarke_A"]["subject"][mdl])
    tb(s, x, 6.3, 5.85, 0.6, [[(f"{cap}: ", {"bold": True}), (f"{za:.0f}% in zone A", {})]], 14,
       align=PP_ALIGN.CENTER)

# 27. Hypotheses scorecard
s = new_slide(kicker="Scorecard", title="Hypotheses H1–H7: where the evidence stands",
              notes="Synthetic evidence only; every row must be re-tested on real EarSpectro recordings.")
rows = [["", "Hypothesis", "Synthetic evidence", "Status"],
        ["H1", "Preprocessing beats raw", "Small for linear (2–4 mg/dL), large for trees (7–16)", "Partly"],
        ["H2", "A wavelength subset is as good as all 5", "Nothing beats the mean on ear5; dense spectrum helps", "Open"],
        ["H3", "Nonlinear beats linear / PLSR", "Not with 40 subjects; trees fit identity", "Not supported"],
        ["H4", "1-D CNN helps with enough data", "CNN R² −0.28 on dense, below PLSR", "Not yet"],
        ["H5", "Unseen subjects score worse than random split", "FFNN 0.60 → −0.09, CatBoost 0.51 → −0.43", "Supported"],
        ["H6", "A little calibration helps", "Mostly the reference level; ~4 mg/dL optical gain on dense", "Partly"],
        ["H7", "Interference-robust training generalises", "Transfer learning not run yet", "Not tested"]]
t = table(s, 0.6, 1.6, 12.1, rows, [0.6, 4.0, 5.6, 1.9], pt=13, row_h=0.6)
colors = {"Supported": TEAL, "Partly": AMBER, "Open": GREY, "Not supported": RED, "Not yet": RED, "Not tested": GREY}
for i in range(1, len(rows)):
    c = t.cell(i, 3)
    for r in c.text_frame.paragraphs[0].runs:
        r.font.bold = True
        r.font.color.rgb = colors[rows[i][3]]

# 28. Next steps
s = new_slide(dark=True, title="Next steps", kicker="Plan")
steps = [("Collect real ear spectra", "subject ID, timestamp, reference glucose; run the same suite unchanged"),
         ("Test more channels on hardware", "add wavelengths or a temperature / reference channel"),
         ("Measure skin temperature", "use it as a model input; it is the largest confounder in the simulation"),
         ("Uncertainty output U", "conformal intervals on subject-level residuals"),
         ("Transfer learning (H7)", "pretrain the 1-D CNN on a public NIR corpus, fine-tune on ear data"),
         ("GPU runs", "install CUDA torch on gnode118 for larger CNN sweeps")]
for i, (t_, d_) in enumerate(steps):
    row, col = divmod(i, 2)
    x, y = 0.6 + col * 6.15, 1.7 + row * 1.65
    badge(s, x, y + 0.1, 0.6, str(i + 1), fill=AMBER, color=INK, pt=16)
    tb(s, x + 0.85, y, 5.1, 0.45, t_, 17, WHITE, bold=True)
    tb(s, x + 0.85, y + 0.5, 5.1, 0.9, d_, 14, LAV)

# 29. References
s = new_slide(kicker="References", title="References and sources",
              notes="Methods references verified against OpenAlex except Hale & Querry (not found by the lookup). "
                    "Survey papers are cited as named in the EarSpectro literature survey.")
refs = [
    "Amerov, A. K., Chen, J., & Arnold, M. A. (2004). Molar absorptivities of glucose and other biological molecules in "
    "aqueous solutions over the first overtone and combination regions of the NIR spectrum. Applied Spectroscopy. "
    "doi:10.1366/0003702042336136",
    "Barnes, R. J., Dhanoa, M. S., & Lister, S. J. (1989). Standard normal variate transformation and de-trending of "
    "NIR diffuse reflectance spectra. Applied Spectroscopy. doi:10.1366/0003702894202201",
    "Clarke, W. L., et al. (1987). Evaluating clinical accuracy of systems for self-monitoring of blood glucose. "
    "Diabetes Care. doi:10.2337/diacare.10.5.622",
    "Geladi, P., MacDougall, D., & Martens, H. (1985). Linearization and scatter-correction for NIR reflectance spectra "
    "of meat. Applied Spectroscopy. doi:10.1366/0003702854248656",
    "Lundberg, S. M., & Lee, S.-I. (2017). A unified approach to interpreting model predictions. NeurIPS. arXiv:1705.07874",
    "Prokhorenkova, L., et al. (2018). CatBoost: unbiased boosting with categorical features. NeurIPS. arXiv:1706.09516",
    "Savitzky, A., & Golay, M. J. E. (1964). Smoothing and differentiation of data by simplified least squares "
    "procedures. Analytical Chemistry. doi:10.1021/ac60214a047",
    "Wold, S., Sjöström, M., & Eriksson, L. (2001). PLS-regression: a basic tool of chemometrics. Chemometrics and "
    "Intelligent Laboratory Systems. doi:10.1016/S0169-7439(01)00155-1",
    "Hale, G. M., & Querry, M. R. (1973). Optical constants of water in the 200-nm to 200-µm wavelength region. "
    "Applied Optics (not auto-verified)",
]
tb(s, 0.6, 1.5, 12.1, 4.4, ["• " + r for r in refs], 11)
box(s, 0.6, 6.0, 12.1, 0.85, fill=TINT)
tb(s, 0.8, 6.0, 11.7, 0.85, [[("From the EarSpectro survey (cited as named there): ", {"bold": True}),
                              ("Gusev et al.; Susana et al.; Satter et al.; Adigüzel et al.; Naresh et al.; "
                               "Habibullah et al.; Liao, Lo & Yang.", {})]], 12, anchor=MSO_ANCHOR.MIDDLE)

prs.save(OUT)
(OUT.with_suffix(".texts.json")).write_text(json.dumps(TEXTS, default=str))
print("slides:", len(prs.slides), "->", OUT)
