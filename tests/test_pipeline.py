"""Fast checks for the leakage guarantees and the building blocks."""

import numpy as np
import pandas as pd
import pytest

from earspectro.calibration import calibration_curve
from earspectro.data.synthetic import SynthConfig, generate
from earspectro.metrics import clarke_zones, regression_metrics
from earspectro.pipeline import RunSpec, cross_validate
from earspectro.preprocessing import MSC, PREPROCESSING, SNV, build_preprocessor
from earspectro.qc import QualityControl, repeat_groups
from earspectro.splits import check_no_subject_leak, make_splits


@pytest.fixture(scope="module")
def df():
    return generate(SynthConfig(n_subjects=10, sessions_per_subject=2, timepoints_per_session=8,
                                repeats=2, artifact_rate=0.05, seed=1))


def test_subject_split_has_no_leak(df):
    splits = make_splits(df, "subject", 5)
    check_no_subject_leak(df, splits)
    assert sum(len(te) for _, te in splits) == len(df)


def test_session_split_tests_last_session_only(df):
    (tr, te), = make_splits(df, "session")
    assert set(df.session_idx.iloc[te]) == {1} and set(df.session_idx.iloc[tr]) == {0}


def test_random_split_does_leak(df):
    with pytest.raises(AssertionError):
        check_no_subject_leak(df, make_splits(df, "random", 5))


def test_snv_rows_standardised():
    X = np.random.default_rng(0).normal(size=(4, 7)) * 3 + 2
    Z = SNV().transform(X)
    assert np.allclose(Z.mean(1), 0) and np.allclose(Z.std(1), 1)


def test_msc_removes_multiplicative_scatter():
    base = np.linspace(1, 2, 20)
    X = np.vstack([a + b * base for a, b in [(0.1, 1.0), (-0.2, 1.3), (0.05, 0.8)]])
    Z = MSC().fit(X).transform(X)
    assert np.allclose(Z, Z[0], atol=1e-8)


@pytest.mark.parametrize("name", PREPROCESSING)
def test_preprocessing_shapes_on_sparse_grid(name):
    wl = [1050, 1200, 1450, 1550, 1650]
    X = np.random.default_rng(0).normal(1, 0.1, size=(6, 5))
    p = build_preprocessor(name, wl)
    out = p.fit(X).transform(X)
    assert out.shape == X.shape and np.isfinite(out).all()


def test_qc_flags_injected_artifacts(df):
    from earspectro.data import spectral_columns
    X = df[spectral_columns(df)].to_numpy(float)
    s = QualityControl().fit(X).score(X, repeat_groups(df))
    clean = df.artifact.to_numpy() == "none"
    # A bad repeat can drag its clean partner's repeat score down, hence the slack.
    assert (~s.qc_pass[clean]).mean() < 0.10
    for kind in ("dropout", "saturation"):
        m = df.artifact.to_numpy() == kind
        if m.any():
            assert (~s.qc_pass[m]).all(), kind


def test_metrics_and_clarke():
    y = np.array([100.0, 150, 60, 250])
    m = regression_metrics(y, y)
    assert m["MAE"] == 0 and m["R2"] == 1
    assert list(clarke_zones(y, y)) == ["A"] * 4
    assert clarke_zones([250.0], [60.0])[0] == "E"


def test_cross_validate_runs_and_beats_nothing_crazy(df):
    res, oof = cross_validate(df, RunSpec(model="ridge"), "subject", 5)
    assert len(oof) > 0.8 * len(df)
    assert np.isfinite(res["MAE"])
    check_no_subject_leak(oof.assign(), [(np.where(oof.fold != f)[0], np.where(oof.fold == f)[0])
                                         for f in oof.fold.unique()])


def test_calibration_offset_fixes_constant_bias():
    rng = np.random.default_rng(0)
    rows = []
    for s in range(6):
        for tp in range(10):
            y = 100 + 5 * tp
            rows.append({"session_id": f"s{s}", "subject_id": f"s{s}", "timepoint": tp,
                         "y": y, "pred": y + 20 * (s - 2.5) + rng.normal(0, 1)})
    c = calibration_curve(pd.DataFrame(rows), ks=(0, 1), methods=("offset",))
    assert c.set_index("k_cal").MAE[1] < 0.2 * c.set_index("k_cal").MAE[0]
