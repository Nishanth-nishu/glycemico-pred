"""Synthetic earlobe NIR dataset following the mixture model

    x = s_glucose + s_tissue + s_water + s_hb + s_scatter + s_motion + s_sensor + eps

This exists so the whole pipeline (QC, preprocessing ablations, wavelength
selection, subject-independent CV, calibration) can be built and tested before
real EarSpectro recordings exist. It is NOT a physical forward model: band
positions follow the usual NIR assignments (water 1450/1200/970 nm, glucose
C-H/O-H overtones ~1530-1690 nm and ~1130 nm, lipid ~1210 nm) and water values
are rough literature magnitudes, but glucose band strengths are scaled by
``glucose_gain`` so the signal is weak-but-learnable. Results on this data say
nothing about real-world accuracy.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

EAR5 = [1050, 1200, 1450, 1550, 1650]
DENSE = list(range(1000, 1701, 5))

# Approximate water absorption coefficient (cm^-1), interpolated in log space.
_WATER_TABLE = np.array([
    [950, 0.40], [970, 0.45], [1000, 0.36], [1050, 0.15], [1100, 0.18],
    [1150, 0.90], [1200, 1.05], [1250, 0.95], [1300, 1.20], [1350, 3.0],
    [1400, 12.0], [1450, 28.0], [1500, 20.0], [1550, 10.0], [1600, 6.5],
    [1650, 5.5], [1700, 6.0],
])


def _gauss(wl, centre, width, height):
    return height * np.exp(-0.5 * ((wl - centre) / width) ** 2)


def water_abs(wl, shift_nm=0.0):
    w = np.asarray(wl, float) - shift_nm
    return np.exp(np.interp(w, _WATER_TABLE[:, 0], np.log(_WATER_TABLE[:, 1])))


def glucose_abs(wl):
    """Relative glucose band shape (peak ~1)."""
    wl = np.asarray(wl, float)
    return (_gauss(wl, 1590, 35, 1.0) + _gauss(wl, 1536, 25, 0.6)
            + _gauss(wl, 1690, 25, 0.7) + _gauss(wl, 1130, 40, 0.18)
            + _gauss(wl, 1060, 30, 0.05))


def lipid_abs(wl):
    wl = np.asarray(wl, float)
    return _gauss(wl, 1210, 25, 1.0) + _gauss(wl, 1040, 30, 0.2) + _gauss(wl, 1690, 30, 0.5)


def protein_abs(wl):
    wl = np.asarray(wl, float)
    return _gauss(wl, 1180, 50, 0.3) + _gauss(wl, 1500, 60, 0.6)


def hb_abs(wl):
    wl = np.asarray(wl, float)
    return np.exp(-(wl - 1000.0) / 150.0)


@dataclass
class SynthConfig:
    n_subjects: int = 40
    sessions_per_subject: int = 2
    timepoints_per_session: int = 16      # OGTT-like, every ~10 min
    repeats: int = 3                      # spectra per timepoint
    wavelengths: list = field(default_factory=lambda: list(EAR5))
    glucose_gain: float = 2.0e-5          # OD per (mg/dL) at the 1590 nm peak
    noise_od: float = 1.5e-3              # white sensor noise per wavelength
    confound_strength: float = 1.0        # session-time-locked perfusion/temperature drift
    diabetic_fraction: float = 0.3
    artifact_rate: float = 0.03           # motion / ambient-light / saturation events
    ref_cv: float = 0.05                  # reference glucometer error (CV)
    seed: int = 0


def _ogtt_curve(t_min, g0, rise, t_peak, decay):
    """Fasting baseline + gamma-like post-load excursion (mg/dL)."""
    t = np.maximum(t_min, 0.0)
    shape = (t / t_peak) ** 2 * np.exp(2 * (1 - t / t_peak))
    shape = shape ** (1.0 / decay)
    return g0 + rise * shape


def generate(cfg: SynthConfig) -> pd.DataFrame:
    rng = np.random.default_rng(cfg.seed)
    wl = np.asarray(cfg.wavelengths, float)
    e_w0 = water_abs(wl)
    e_g = glucose_abs(wl)
    e_l, e_p, e_h = lipid_abs(wl), protein_abs(wl), hb_abs(wl)
    rows = []
    t0 = pd.Timestamp("2026-01-05 08:00")

    for s in range(cfg.n_subjects):
        diabetic = rng.random() < cfg.diabetic_fraction
        subj = dict(
            subject_id=f"S{s + 1:03d}",
            age=int(rng.integers(20, 70)),
            sex=rng.choice(["F", "M"]),
            skin_tone=int(rng.integers(1, 7)),        # Fitzpatrick I-VI
            diabetic=int(diabetic),
        )
        # Subject-level tissue / anatomy (the dominant, glucose-unrelated variance).
        path_cm = rng.normal(0.08, 0.012)            # effective optical path
        water_frac = rng.normal(0.70, 0.04)
        lipid = rng.normal(0.25, 0.08)
        protein = rng.normal(0.30, 0.06)
        hb = rng.normal(0.15, 0.04) * (1 + 0.05 * (subj["skin_tone"] - 3.5))
        scat_a, scat_b = rng.normal(0.35, 0.08), rng.normal(1.2, 0.2)
        g_scale = rng.normal(1.0, 0.15)              # subject-specific glucose path response

        for sess in range(cfg.sessions_per_subject):
            day = t0 + pd.Timedelta(days=int(7 * sess + rng.integers(0, 3)), hours=float(rng.normal(0, 1)))
            g0 = rng.normal(140, 25) if diabetic else rng.normal(92, 9)
            rise = rng.normal(110, 30) if diabetic else rng.normal(55, 18)
            t_peak = rng.normal(70, 12) if diabetic else rng.normal(45, 8)
            decay = rng.uniform(0.8, 1.4)
            # Session-level placement/sensor state.
            gain_od = rng.normal(0, 0.03)                 # LED/detector gain -> additive OD
            tilt = rng.normal(0, 0.02)                    # placement -> baseline slope
            path_sess = path_cm * rng.normal(1.0, 0.04)
            temp0 = rng.normal(0, 0.5)                    # skin temperature offset, deg C

            for tp in range(cfg.timepoints_per_session):
                t_min = tp * 10.0 - 10.0                   # one fasting point before load
                g_true = max(_ogtt_curve(t_min, g0, rise, t_peak, decay), 45.0)
                # Time-locked confounder: perfusion / temperature drift after the
                # glucose load, correlated with glucose but not caused by it.
                drift = cfg.confound_strength * np.tanh(max(t_min, 0) / 60.0)
                temp = temp0 + 0.6 * drift
                g_ref = g_true * (1 + rng.normal(0, cfg.ref_cv))
                ts = day + pd.Timedelta(minutes=t_min + 10)

                for rep in range(cfg.repeats):
                    e_w = water_abs(wl, shift_nm=-0.5 * temp) * (1 - 0.003 * temp)
                    mu = (water_frac * (1 - 6e-7 * g_true) * e_w   # glucose displaces water (~0.6 mL per g)
                          + lipid * 0.4 * e_l + protein * 0.5 * e_p
                          + hb * (1 + 0.05 * drift) * e_h)
                    A = path_sess * mu
                    A = A + cfg.glucose_gain * g_scale * g_true * e_g
                    A = A + scat_a * (wl / 1000.0) ** (-scat_b)
                    A = A + gain_od + tilt * (wl - wl.mean()) / 500.0
                    A = A + rng.normal(0, cfg.noise_od, wl.size)
                    artifact = "none"
                    u = rng.random()
                    if u < cfg.artifact_rate:
                        kind = rng.choice(["motion", "ambient", "saturation", "dropout"])
                        artifact = str(kind)
                        if kind == "motion":
                            A = A + rng.normal(0, 0.08) + rng.normal(0, 0.04, wl.size)
                        elif kind == "ambient":
                            A = A - np.abs(rng.normal(0.15, 0.05)) * np.linspace(1, 0.5, wl.size)
                        elif kind == "saturation":
                            A = np.maximum(A, np.quantile(A, 0.6))
                        else:
                            A = A.copy()
                            A[rng.integers(0, wl.size)] = np.nan
                    rows.append({
                        **subj,
                        "session_id": f"{subj['subject_id']}_D{sess + 1}",
                        "session_idx": sess,
                        "timepoint": tp,
                        "repeat": rep,
                        "timestamp": ts + pd.Timedelta(seconds=20 * rep),
                        "minutes_since_load": t_min,
                        "skin_temp_offset": temp,
                        "artifact": artifact,
                        "glucose_true": g_true,
                        "glucose_ref": g_ref,
                        **{f"A_{int(w)}": a for w, a in zip(wl, A)},
                    })
    return pd.DataFrame(rows)
