"""Stages 8-9: FFNN baseline and 1-D CNN, wrapped as sklearn regressors.

Early stopping uses a held-out slice of the *training* subjects (when groups
are passed), so it never peeks at the outer test fold.
"""

from __future__ import annotations

import copy
import os

import numpy as np
import torch
from sklearn.base import BaseEstimator, RegressorMixin
from sklearn.model_selection import GroupShuffleSplit, ShuffleSplit
from torch import nn


class FFNN(nn.Module):
    def __init__(self, n_in: int, hidden=(128, 64, 32), dropout: float = 0.2):
        super().__init__()
        layers, d = [], n_in
        for i, h in enumerate(hidden):
            layers += [nn.Linear(d, h), nn.ReLU()]
            if i == 0:
                layers.append(nn.Dropout(dropout))
            d = h
        layers.append(nn.Linear(d, 1))
        self.net = nn.Sequential(*layers)

    def forward(self, x):
        return self.net(x).squeeze(-1)


class CNN1D(nn.Module):
    """Spectrum -> Conv-BN-ReLU -> Conv -> Pool -> Conv -> GlobalPool -> Dense -> glucose."""

    def __init__(self, n_in: int, channels=(32, 64, 64), dropout: float = 0.2):
        super().__init__()
        k1 = 7 if n_in >= 15 else 3
        c1, c2, c3 = channels

        def block(ci, co, k):
            return nn.Sequential(nn.Conv1d(ci, co, k, padding=k // 2), nn.BatchNorm1d(co), nn.ReLU())

        self.features = nn.Sequential(
            block(1, c1, k1),
            block(c1, c2, 3),
            nn.MaxPool1d(2) if n_in >= 8 else nn.Identity(),
            block(c2, c3, 3),
        )
        self.head = nn.Sequential(nn.Linear(2 * c3, 64), nn.ReLU(), nn.Dropout(dropout), nn.Linear(64, 1))

    def forward(self, x):
        h = self.features(x.unsqueeze(1))
        h = torch.cat([h.mean(-1), h.amax(-1)], dim=1)
        return self.head(h).squeeze(-1)


class SpectraNet(BaseEstimator, RegressorMixin):
    def __init__(self, arch: str = "ffnn", epochs: int = 400, batch_size: int = 64, lr: float = 1e-3,
                 weight_decay: float = 1e-4, dropout: float = 0.2, patience: int = 40,
                 val_fraction: float = 0.15, random_state: int = 0, device: str | None = None):
        self.arch, self.epochs, self.batch_size, self.lr = arch, epochs, batch_size, lr
        self.weight_decay, self.dropout, self.patience = weight_decay, dropout, patience
        self.val_fraction, self.random_state, self.device = val_fraction, random_state, device

    def _dev(self):
        return torch.device(self.device or ("cuda" if torch.cuda.is_available() else "cpu"))

    def _build(self, n_in):
        if self.arch == "ffnn":
            return FFNN(n_in, dropout=self.dropout)
        if self.arch == "cnn1d":
            return CNN1D(n_in, dropout=self.dropout)
        raise KeyError(self.arch)

    def fit(self, X, y, groups=None):
        torch.manual_seed(self.random_state)
        torch.set_num_threads(int(os.environ.get("SLURM_CPUS_PER_TASK", 4)))
        rng = np.random.default_rng(self.random_state)
        X, y = np.asarray(X, np.float32), np.asarray(y, np.float32)
        self.x_mu_, self.x_sd_ = X.mean(0), X.std(0) + 1e-6
        self.y_mu_, self.y_sd_ = float(y.mean()), float(y.std() + 1e-6)
        Xs, ys = (X - self.x_mu_) / self.x_sd_, (y - self.y_mu_) / self.y_sd_

        if groups is not None and len(np.unique(groups)) > 3:
            tr, va = next(GroupShuffleSplit(1, test_size=self.val_fraction, random_state=self.random_state)
                          .split(Xs, ys, groups))
        else:
            tr, va = next(ShuffleSplit(1, test_size=self.val_fraction, random_state=self.random_state).split(Xs))

        dev = self._dev()
        model = self._build(X.shape[1]).to(dev)
        opt = torch.optim.AdamW(model.parameters(), lr=self.lr, weight_decay=self.weight_decay)
        sched = torch.optim.lr_scheduler.ReduceLROnPlateau(opt, factor=0.5, patience=self.patience // 3)
        Xt, yt = torch.tensor(Xs[tr], device=dev), torch.tensor(ys[tr], device=dev)
        Xv, yv = torch.tensor(Xs[va], device=dev), torch.tensor(ys[va], device=dev)
        loss_fn = nn.SmoothL1Loss(beta=0.5)

        best, best_state, wait = np.inf, None, 0
        self.history_ = []
        for epoch in range(self.epochs):
            model.train()
            perm = torch.tensor(rng.permutation(len(tr)), device=dev)
            for i in range(0, len(tr), self.batch_size):
                b = perm[i:i + self.batch_size]
                if b.numel() < 2:
                    continue
                opt.zero_grad()
                loss = loss_fn(model(Xt[b]), yt[b])
                loss.backward()
                opt.step()
            model.eval()
            with torch.no_grad():
                v = float(torch.mean(torch.abs(model(Xv) - yv)))
            sched.step(v)
            self.history_.append(v)
            if v < best - 1e-4:
                best, best_state, wait = v, copy.deepcopy(model.state_dict()), 0
            else:
                wait += 1
                if wait >= self.patience:
                    break
        model.load_state_dict(best_state)
        self.model_, self.best_epoch_ = model.eval(), int(np.argmin(self.history_))
        return self

    def predict(self, X):
        Xs = (np.asarray(X, np.float32) - self.x_mu_) / self.x_sd_
        with torch.no_grad():
            out = self.model_(torch.tensor(Xs, device=next(self.model_.parameters()).device))
        return out.cpu().numpy() * self.y_sd_ + self.y_mu_
