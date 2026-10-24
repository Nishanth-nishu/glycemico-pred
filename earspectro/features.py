"""Stage 5: representations.

Track A uses the (preprocessed) spectrum directly. Track B builds engineered
features: per-wavelength intensities, pairwise ratios / differences /
normalised differences, local slopes and curvature, and band areas.
"""

from __future__ import annotations

from itertools import combinations

import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin


class WavelengthSubset(BaseEstimator, TransformerMixin):
    """Keep only the given wavelengths (by value, nearest match)."""

    def __init__(self, wavelengths, keep=None):
        self.wavelengths, self.keep = wavelengths, keep

    def fit(self, X, y=None):
        wl = np.asarray(self.wavelengths, float)
        if self.keep is None:
            self.idx_ = np.arange(wl.size)
        else:
            self.idx_ = np.array(sorted({int(np.argmin(np.abs(wl - k))) for k in self.keep}))
        return self

    def transform(self, X):
        return np.asarray(X, float)[:, self.idx_]


class SpectralFeatures(BaseEstimator, TransformerMixin):
    """Track-B engineered features from a (sparse or dense) spectrum.

    For dense spectra, pairwise terms are built on ``n_bands`` band means so
    the feature count stays manageable.
    """

    def __init__(self, wavelengths, n_bands: int = 8, include_raw: bool = True):
        self.wavelengths, self.n_bands, self.include_raw = wavelengths, n_bands, include_raw

    def fit(self, X, y=None):
        wl = np.asarray(self.wavelengths, float)
        n = np.asarray(X).shape[1]
        if n <= self.n_bands:
            self.bands_ = [np.array([i]) for i in range(n)]
            self.band_centres_ = wl[:n]
        else:
            self.bands_ = np.array_split(np.arange(n), self.n_bands)
            self.band_centres_ = np.array([wl[b].mean() for b in self.bands_])
        self.names_ = self._names()
        return self

    def _names(self):
        c = [f"{x:.0f}" for x in self.band_centres_]
        names = [f"A{x}" for x in c] if self.include_raw else []
        for i, j in combinations(range(len(c)), 2):
            names += [f"R{c[i]}/{c[j]}", f"D{c[i]}-{c[j]}", f"ND{c[i]},{c[j]}"]
        names += [f"slope{c[i]}-{c[i + 1]}" for i in range(len(c) - 1)]
        names += [f"curv@{c[i]}" for i in range(1, len(c) - 1)]
        names += ["area", "mean", "std"]
        return names

    def get_feature_names_out(self, input_features=None):
        return np.array(self.names_)

    def transform(self, X):
        X = np.asarray(X, float)
        B = np.column_stack([X[:, b].mean(axis=1) for b in self.bands_])
        wc = self.band_centres_
        eps = 1e-6
        feats = [B] if self.include_raw else []
        pair = []
        for i, j in combinations(range(B.shape[1]), 2):
            a, b = B[:, i], B[:, j]
            safe_b = np.where(np.abs(b) < eps, eps, b)
            pair += [a / safe_b, a - b, (a - b) / (np.abs(a) + np.abs(b) + eps)]
        if pair:
            feats.append(np.column_stack(pair))
        if B.shape[1] > 1:
            feats.append(np.diff(B, axis=1) / np.diff(wc))
        if B.shape[1] > 2:
            slopes = np.diff(B, axis=1) / np.diff(wc)
            feats.append(np.diff(slopes, axis=1) / (0.5 * (wc[2:] - wc[:-2])))
        area = np.trapz(X, np.asarray(self.wavelengths, float)[: X.shape[1]], axis=1) if X.shape[1] > 1 else X[:, 0]
        feats.append(np.column_stack([area, X.mean(axis=1), X.std(axis=1)]))
        return np.column_stack(feats)
