"""Stage 3: spectral preprocessing as sklearn transformers.

All transforms live inside the model Pipeline, so anything with fitted state
(MSC reference spectrum, scalers) is fitted on the training fold only.

On the 5-LED EarSpectro layout the wavelengths are irregular and sparse, so
Savitzky-Golay windows shrink to the number of available points and
derivatives fall back to finite differences on the true wavelength spacing.
These variants are still worth testing, but they mean less than on a dense
spectrometer grid.
"""

from __future__ import annotations

import numpy as np
from scipy.signal import savgol_filter
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import FunctionTransformer


class _Stateless(BaseEstimator, TransformerMixin):
    def fit(self, X, y=None):
        self.n_features_in_ = np.asarray(X).shape[1]   # marks the step as fitted for sklearn
        return self


def _odd_window(window: int, n: int) -> int:
    w = min(window, n if n % 2 else n - 1)
    return max(w, 3)


class SavGol(_Stateless):
    def __init__(self, window: int = 11, polyorder: int = 2, deriv: int = 0, wavelengths=None):
        self.window, self.polyorder, self.deriv, self.wavelengths = window, polyorder, deriv, wavelengths

    def transform(self, X):
        X = np.asarray(X, float)
        n = X.shape[1]
        if n < 3:
            return X
        w = _odd_window(self.window, n)
        p = min(self.polyorder, w - 1)
        uniform = self.wavelengths is None or np.allclose(np.diff(self.wavelengths), np.diff(self.wavelengths)[0])
        if self.deriv and not uniform:
            # Irregular grid: smooth (if possible) then differentiate on the real axis.
            Xs = savgol_filter(X, w, min(p, w - 2), axis=1) if w < n else X
            for _ in range(self.deriv):
                Xs = np.gradient(Xs, np.asarray(self.wavelengths, float), axis=1)
            return Xs
        delta = float(np.diff(self.wavelengths)[0]) if self.wavelengths is not None else 1.0
        return savgol_filter(X, w, max(p, self.deriv), deriv=self.deriv, delta=delta, axis=1)


class SNV(_Stateless):
    def transform(self, X):
        X = np.asarray(X, float)
        return (X - X.mean(axis=1, keepdims=True)) / (X.std(axis=1, keepdims=True) + 1e-12)


class MSC(BaseEstimator, TransformerMixin):
    """Multiplicative scatter correction against the training-mean spectrum."""

    def fit(self, X, y=None):
        self.reference_ = np.asarray(X, float).mean(axis=0)
        return self

    def transform(self, X):
        X = np.asarray(X, float)
        ref = self.reference_ - self.reference_.mean()
        out = np.empty_like(X)
        for i, x in enumerate(X):
            b = np.dot(ref, x - x.mean()) / (np.dot(ref, ref) + 1e-12)
            a = x.mean() - b * self.reference_.mean()
            out[i] = (x - a) / (b if abs(b) > 1e-12 else 1.0)
        return out


class Detrend(_Stateless):
    """Baseline correction: remove a per-spectrum polynomial in wavelength."""

    def __init__(self, order: int = 1, wavelengths=None):
        self.order, self.wavelengths = order, wavelengths

    def transform(self, X):
        X = np.asarray(X, float)
        wl = np.arange(X.shape[1], dtype=float) if self.wavelengths is None else np.asarray(self.wavelengths, float)
        t = (wl - wl.mean()) / (wl.std() + 1e-12)
        V = np.vander(t, self.order + 1)
        coef, *_ = np.linalg.lstsq(V, X.T, rcond=None)
        return X - (V @ coef).T


class VectorNorm(_Stateless):
    def transform(self, X):
        X = np.asarray(X, float)
        return X / (np.linalg.norm(X, axis=1, keepdims=True) + 1e-12)


def identity():
    return FunctionTransformer(validate=False)


def build_preprocessor(name: str, wavelengths) -> object:
    """Named preprocessing variants for the Stage-3 ablation (section 14)."""
    wl = np.asarray(wavelengths, float)
    sg = lambda d=0: SavGol(window=11, polyorder=2, deriv=d, wavelengths=wl)  # noqa: E731
    variants = {
        "raw": lambda: identity(),
        "detrend": lambda: Detrend(1, wl),
        "sg": lambda: sg(),
        "snv": lambda: SNV(),
        "msc": lambda: MSC(),
        "vnorm": lambda: VectorNorm(),
        "d1": lambda: sg(1),
        "d2": lambda: sg(2),
        "sg+snv": lambda: make_pipeline(sg(), SNV()),
        "sg+msc": lambda: make_pipeline(sg(), MSC()),
        "d1+snv": lambda: make_pipeline(sg(1), SNV()),
        "snv+detrend": lambda: make_pipeline(SNV(), Detrend(1, wl)),
    }
    if name not in variants:
        raise KeyError(f"unknown preprocessing '{name}'; choose from {sorted(variants)}")
    return variants[name]()


PREPROCESSING = ["raw", "detrend", "sg", "snv", "msc", "d1", "d2", "sg+snv", "sg+msc", "d1+snv"]
