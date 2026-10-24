"""Figures for the report. All functions save a PNG and return its path."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from .metrics import clarke_zones  # noqa: E402

_ZONE_COLOURS = {"A": "#2a9d8f", "B": "#e9c46a", "C": "#f4a261", "D": "#e76f51", "E": "#9b2226"}


def _save(fig, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return path


def clarke_grid(y, p, path, title=""):
    y, p = np.asarray(y), np.asarray(p)
    z = clarke_zones(y, p)
    fig, ax = plt.subplots(figsize=(5.5, 5.5))
    for k, c in _ZONE_COLOURS.items():
        m = z == k
        ax.scatter(y[m], p[m], s=6, alpha=0.5, c=c, label=f"{k}: {m.mean() * 100:.1f}%")
    lim = 400
    ax.plot([0, lim], [0, lim], "k:", lw=0.8)
    for xs, ys in [([0, 175 / 3], [70, 70]), ([175 / 3, 400 / 1.2], [70, 400]), ([70, 70], [84, 400]),
                   ([0, 70], [180, 180]), ([70, 290], [180, 400]), ([70, 70], [0, 56]),
                   ([70, 400], [56, 320]), ([180, 180], [0, 70]), ([180, 400], [70, 70]),
                   ([240, 240], [70, 180]), ([240, 400], [180, 180]), ([130, 180], [0, 70])]:
        ax.plot(xs, ys, "k-", lw=0.6)
    ax.set(xlim=(0, lim), ylim=(0, lim), xlabel="Reference glucose (mg/dL)",
           ylabel="Predicted glucose (mg/dL)", title=title or "Clarke error grid")
    ax.legend(loc="upper left", fontsize=8, markerscale=2)
    return _save(fig, path)


def bland_altman_plot(y, p, path, title=""):
    y, p = np.asarray(y), np.asarray(p)
    mean, diff = (y + p) / 2, p - y
    m, s = diff.mean(), diff.std(ddof=1)
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.scatter(mean, diff, s=5, alpha=0.4)
    for v, ls in [(m, "-"), (m + 1.96 * s, "--"), (m - 1.96 * s, "--")]:
        ax.axhline(v, color="k", ls=ls, lw=0.8)
    ax.set(xlabel="Mean of reference and prediction (mg/dL)", ylabel="Prediction - reference (mg/dL)",
           title=title or f"Bland-Altman (bias {m:.1f}, LoA ±{1.96 * s:.1f})")
    return _save(fig, path)


def error_vs_glucose(y, p, path, title=""):
    y, p = np.asarray(y), np.asarray(p)
    bins = np.arange(40, 320, 20)
    idx = np.digitize(y, bins)
    centres, maes = [], []
    for i in np.unique(idx):
        m = idx == i
        if m.sum() >= 10:
            centres.append(y[m].mean())
            maes.append(np.abs(p[m] - y[m]).mean())
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(centres, maes, "o-")
    ax.set(xlabel="Reference glucose (mg/dL)", ylabel="MAE (mg/dL)", title=title or "Error vs glucose level")
    return _save(fig, path)


def scenario_bars(res: pd.DataFrame, path, metric="MAE"):
    piv = res.pivot_table(index="model", columns="scenario", values=metric)
    order = [c for c in ("random", "subject", "session") if c in piv.columns]
    piv = piv[order].sort_values(order[-1] if "subject" not in order else "subject")
    fig, ax = plt.subplots(figsize=(7, 4))
    piv.plot.bar(ax=ax)
    ax.set(ylabel=f"{metric} (mg/dL)", title=f"{metric} by evaluation scenario")
    return _save(fig, path)


def heatmap(piv: pd.DataFrame, path, title, fmt="{:.1f}", cmap="viridis_r"):
    fig, ax = plt.subplots(figsize=(1.1 * piv.shape[1] + 2.5, 0.45 * piv.shape[0] + 1.5))
    im = ax.imshow(piv.to_numpy(float), cmap=cmap, aspect="auto")
    ax.set_xticks(range(piv.shape[1]), piv.columns, rotation=40, ha="right")
    ax.set_yticks(range(piv.shape[0]), piv.index)
    for i in range(piv.shape[0]):
        for j in range(piv.shape[1]):
            v = piv.iat[i, j]
            if np.isfinite(v):
                ax.text(j, i, fmt.format(v), ha="center", va="center", fontsize=7, color="w")
    fig.colorbar(im, ax=ax, shrink=0.8)
    ax.set_title(title)
    return _save(fig, path)


def line(df: pd.DataFrame, x, y, hue, path, title, ylabel=None):
    fig, ax = plt.subplots(figsize=(6, 4))
    for name, g in df.groupby(hue):
        g = g.sort_values(x)
        ax.plot(g[x], g[y], "o-", label=str(name))
    ax.set(xlabel=x, ylabel=ylabel or y, title=title)
    ax.legend(fontsize=8)
    return _save(fig, path)


def importance_plot(summary: pd.DataFrame, path, title="Wavelength importance (held-out subjects)"):
    fig, ax = plt.subplots(figsize=(7, 4))
    for method, g in summary.groupby("method"):
        g = g.sort_values("wavelength")
        scale = g["mean"].abs().max() or 1.0
        ax.errorbar(g["wavelength"], g["mean"] / scale, yerr=g["std"] / scale, fmt="o-", capsize=3, label=method)
    ax.set(xlabel="Wavelength (nm)", ylabel="Importance (normalised)", title=title)
    ax.legend(fontsize=8)
    return _save(fig, path)


def example_spectra(df: pd.DataFrame, cols, wl, path):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    for sid, g in list(df.groupby("subject_id"))[:6]:
        axes[0].plot(wl, g[cols].median().to_numpy(), "o-", ms=3, label=sid)
    axes[0].set(xlabel="Wavelength (nm)", ylabel="Absorbance", title="Median spectrum per subject")
    axes[0].legend(fontsize=7)
    sess = df[df["session_id"] == df["session_id"].iloc[0]]
    base = sess[sess["timepoint"] == sess["timepoint"].min()][cols].mean().to_numpy()
    cmap = plt.get_cmap("viridis")
    for tp, g in sess.groupby("timepoint"):
        axes[1].plot(wl, g[cols].mean().to_numpy() - base, color=cmap(tp / sess["timepoint"].max()),
                     label=f"{g['glucose_ref'].mean():.0f} mg/dL" if tp % 4 == 0 else None)
    axes[1].set(xlabel="Wavelength (nm)", ylabel="ΔA vs fasting", title="One session: change over the OGTT")
    axes[1].legend(fontsize=7)
    return _save(fig, path)
