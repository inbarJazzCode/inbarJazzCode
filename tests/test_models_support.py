import numpy as np
import pytest

from statinvest.models._util import add_intercept
from statinvest.models.evaluation import (
    chronological_split,
    walk_forward_splits,
)
from statinvest.models.optim import (
    gradient_check,
    logistic_objective,
    mse_objective,
    run_optimizer,
)
from statinvest.models.serialize import deserialize_run, serialize_run
from statinvest.models.transforms import (
    Specification,
    TransformError,
    build_design,
    safe_log,
)


def test_gradient_check_mse_and_logistic():
    rng = np.random.default_rng(0)
    X = add_intercept(rng.normal(size=(50, 2)))
    y = rng.normal(size=50)
    beta = rng.normal(size=3)
    assert gradient_check(mse_objective, beta, X, y) < 1e-5
    yb = (rng.uniform(size=50) < 0.5).astype(float)
    assert gradient_check(logistic_objective, beta, X, yb) < 1e-5


def test_optimizer_reproducible():
    rng = np.random.default_rng(1)
    X = add_intercept(rng.normal(size=(100, 2)))
    y = X @ np.array([1.0, 2.0, -1.0]) + rng.normal(scale=0.1, size=100)
    a = run_optimizer(X, y, optimizer="sgd", lr=0.05, epochs=200, seed=7)
    b = run_optimizer(X, y, optimizer="sgd", lr=0.05, epochs=200, seed=7)
    assert np.allclose(a.params, b.params)


def test_optimizer_matches_reference():
    rng = np.random.default_rng(2)
    X = add_intercept(rng.normal(size=(200, 2)))
    y = X @ np.array([0.5, 1.0, -2.0]) + rng.normal(scale=0.1, size=200)
    res = run_optimizer(X, y, optimizer="adam", lr=0.05, epochs=1000)
    assert res.max_coef_diff < 0.05


def test_optimizer_nonconvergence_flagged():
    rng = np.random.default_rng(3)
    X = add_intercept(rng.normal(size=(100, 2)))
    y = rng.normal(size=100)
    res = run_optimizer(X, y, optimizer="sgd", lr=1e6, epochs=5, patience=999)
    assert (not res.converged) or any("diverg" in w.lower() or "did not" in w.lower()
                                      for w in res.warnings)


def test_chronological_split_no_leakage():
    sp = chronological_split(100, 0.7, 0.15)
    assert sp.train_idx.max() < sp.val_idx.min()
    assert sp.val_idx.max() < sp.test_idx.min()
    assert len(set(sp.train_idx) & set(sp.test_idx)) == 0


def test_walk_forward_windows_increasing():
    splits = walk_forward_splits(100, n_folds=4)
    assert len(splits) >= 1
    for train_idx, test_idx in splits:
        assert train_idx.max() < test_idx.min()


def test_safe_log_rejects_nonpositive():
    with pytest.raises(TransformError):
        safe_log(np.array([1.0, 0.0, 2.0]))


def test_build_design_drops_missing_and_records_formula():
    data = {
        "y": np.array([1.0, 2.0, np.nan, 4.0]),
        "x": np.array([1.0, 2.0, 3.0, 4.0]),
    }
    spec = Specification(family="ols", target="y", features=["x"],
                         target_transform="level")
    y, X, names, resolved = build_design(data, spec)
    assert resolved.n_dropped == 1
    assert resolved.n_observations == 3
    assert "y ~" in resolved.formula


def test_serialize_run_no_secrets():
    doc = serialize_run(
        spec={"family": "ols"},
        result={"r2": np.float64(0.9), "params": np.array([1.0, 2.0])},
        provenance={"symbol": "AAPL"},
        seed=1,
    )
    parsed = deserialize_run(doc)
    assert parsed["result"]["r2"] == 0.9
    with pytest.raises(ValueError):
        serialize_run(spec={"api_key": "x"}, result={})
