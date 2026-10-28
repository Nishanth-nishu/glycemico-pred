"""Section 23: the three evaluation scenarios.

A  random      - measurements shuffled; subjects leak across folds (sanity check only)
B  subject     - GroupKFold on subject_id; test subjects never seen in training (primary)
C  session     - train on each subject's earlier session(s), test on the last one
D  holdout     - fixed external test set: train on split == "cal", test on split == "val"
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold, KFold


def make_splits(df: pd.DataFrame, scenario: str, n_splits: int = 5, seed: int = 0):
    idx = np.arange(len(df))
    if scenario == "random":
        return list(KFold(n_splits, shuffle=True, random_state=seed).split(idx))
    if scenario == "subject":
        # Shuffle subject order so GroupKFold folds are not tied to subject id order.
        subj = df["subject_id"].to_numpy()
        rng = np.random.default_rng(seed)
        perm = {s: i for i, s in enumerate(rng.permutation(np.unique(subj)))}
        groups = np.array([perm[s] for s in subj])
        return list(GroupKFold(n_splits).split(idx, groups=groups))
    if scenario == "session":
        order = df.groupby("subject_id")["session_idx"].transform("max")
        test = df["session_idx"].to_numpy() == order.to_numpy()
        multi = (df.groupby("subject_id")["session_idx"].transform("nunique") > 1).to_numpy()
        return [(idx[~test & multi], idx[test & multi])]
    if scenario == "holdout":
        val = df["split"].to_numpy() == "val"
        return [(idx[~val], idx[val])]
    raise ValueError(f"unknown scenario '{scenario}'")


def check_no_subject_leak(df: pd.DataFrame, splits) -> None:
    for tr, te in splits:
        overlap = set(df["subject_id"].iloc[tr]) & set(df["subject_id"].iloc[te])
        if overlap:
            raise AssertionError(f"subject leakage: {sorted(overlap)[:5]}")
