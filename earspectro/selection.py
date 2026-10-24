"""Stage 6: feature selection, always fitted inside the training fold.

Each selector is an sklearn transformer, so placing it in the Pipeline
guarantees the test fold never influences which features are kept.
"""

from __future__ import annotations

import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.feature_selection import RFE, mutual_info_regression
from sklearn.ensemble import ExtraTreesRegressor


class CorrelationFilter(BaseEstimator, TransformerMixin):
    """Keep the k features with highest |Pearson r| to the target."""

    def __init__(self, k: int = 20):
        self.k = k

    def fit(self, X, y):
        X, y = np.asarray(X, float), np.asarray(y, float)
        Xc, yc = X - X.mean(0), y - y.mean()
        r = (Xc * yc[:, None]).sum(0) / (np.sqrt((Xc ** 2).sum(0) * (yc ** 2).sum()) + 1e-12)
        self.scores_ = np.abs(r)
        self.idx_ = np.sort(np.argsort(-self.scores_)[: min(self.k, X.shape[1])])
        return self

    def transform(self, X):
        return np.asarray(X, float)[:, self.idx_]


class MRMR(BaseEstimator, TransformerMixin):
    """Greedy minimum-redundancy maximum-relevance (MI relevance, |r| redundancy)."""

    def __init__(self, k: int = 20, random_state: int = 0):
        self.k, self.random_state = k, random_state

    def fit(self, X, y):
        X = np.asarray(X, float)
        k = min(self.k, X.shape[1])
        rel = mutual_info_regression(X, y, random_state=self.random_state)
        corr = np.abs(np.nan_to_num(np.corrcoef(X, rowvar=False)))
        chosen = [int(np.argmax(rel))]
        while len(chosen) < k:
            red = corr[:, chosen].mean(axis=1)
            score = rel - red
            score[chosen] = -np.inf
            chosen.append(int(np.argmax(score)))
        self.idx_ = np.sort(chosen)
        return self

    def transform(self, X):
        return np.asarray(X, float)[:, self.idx_]


class TreeRFE(BaseEstimator, TransformerMixin):
    """Recursive feature elimination driven by extra-trees importance."""

    def __init__(self, k: int = 20, random_state: int = 0):
        self.k, self.random_state = k, random_state

    def fit(self, X, y):
        X = np.asarray(X, float)
        est = ExtraTreesRegressor(n_estimators=200, min_samples_leaf=3, n_jobs=-1, random_state=self.random_state)
        self.rfe_ = RFE(est, n_features_to_select=min(self.k, X.shape[1]), step=0.2).fit(X, y)
        self.idx_ = np.flatnonzero(self.rfe_.support_)
        return self

    def transform(self, X):
        return np.asarray(X, float)[:, self.idx_]


def build_selector(name: str | None, k: int = 20):
    if name in (None, "none"):
        return None
    return {"corr": CorrelationFilter, "mrmr": MRMR, "rfe": TreeRFE}[name](k=k)
