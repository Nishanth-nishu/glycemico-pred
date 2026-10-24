"""Stage 7: classical baselines (section 32, baselines 0-6).

Hyper-parameter search (PLSR components, SVR C/gamma) runs on an inner
GroupKFold over training subjects, so tuning never sees the outer test fold.
"""

from __future__ import annotations

from sklearn.cross_decomposition import PLSRegression
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression, RidgeCV
from sklearn.model_selection import GridSearchCV, GroupKFold
from sklearn.svm import SVR

CLASSICAL_MODELS = ["linear", "ridge", "plsr", "svr", "rf", "xgboost", "catboost"]


class _PLS(PLSRegression):
    """PLSRegression that clips n_components to the data and returns 1-D predictions."""

    def fit(self, X, y):
        self._requested = self.n_components
        self.n_components = min(self.n_components, X.shape[1], X.shape[0] - 1)
        super().fit(X, y)
        self.n_components = self._requested
        return self

    def predict(self, X, copy=True):
        return super().predict(X, copy=copy).ravel()


def _grouped_search(est, grid, n_jobs):
    return GridSearchCV(est, grid, cv=GroupKFold(3), scoring="neg_mean_absolute_error", n_jobs=n_jobs)


def build_classical(name: str, n_jobs: int = 4, seed: int = 0):
    if name == "mean":
        return DummyRegressor(strategy="mean")
    if name == "linear":
        return LinearRegression()
    if name == "ridge":
        return RidgeCV(alphas=[1e-3, 1e-2, 1e-1, 1, 10, 100])
    if name == "plsr":
        return _grouped_search(_PLS(scale=False), {"n_components": [1, 2, 3, 4, 5, 6, 8, 10, 15]}, n_jobs)
    if name == "svr":
        return _grouped_search(SVR(kernel="rbf"), {"C": [1, 10, 100, 1000], "gamma": ["scale", 0.01, 0.1]}, n_jobs)
    if name == "rf":
        return RandomForestRegressor(n_estimators=400, min_samples_leaf=3, max_features=0.5,
                                     n_jobs=n_jobs, random_state=seed)
    if name == "xgboost":
        from xgboost import XGBRegressor
        return XGBRegressor(n_estimators=600, learning_rate=0.03, max_depth=4, subsample=0.8,
                            colsample_bytree=0.8, min_child_weight=3, reg_lambda=1.0,
                            n_jobs=n_jobs, random_state=seed)
    if name == "catboost":
        from catboost import CatBoostRegressor
        return CatBoostRegressor(iterations=800, learning_rate=0.03, depth=6, l2_leaf_reg=3,
                                 loss_function="MAE", thread_count=n_jobs, random_seed=seed, verbose=False,
                                 allow_writing_files=False)
    raise KeyError(f"unknown model '{name}'")


def needs_groups(name: str) -> bool:
    return name in ("plsr", "svr")
