import numpy as np
import pytest

from statinvest.models.logistic import (
    LogisticModel,
    pr_auc,
    roc_auc,
    stable_sigmoid,
)


def test_stable_sigmoid_no_overflow():
    z = np.array([-1000.0, 0.0, 1000.0])
    p = stable_sigmoid(z)
    assert np.all(np.isfinite(p))
    assert p[0] == pytest.approx(0.0, abs=1e-12)
    assert p[1] == pytest.approx(0.5)
    assert p[2] == pytest.approx(1.0, abs=1e-12)


def test_logistic_recovers_signs_and_converges():
    rng = np.random.default_rng(0)
    X = rng.normal(size=(600, 2))
    z = 0.3 + 1.5 * X[:, 0] - 1.0 * X[:, 1]
    y = (rng.uniform(size=600) < 1 / (1 + np.exp(-z))).astype(int)
    model = LogisticModel()
    res = model.fit(X, y)
    assert res.converged
    assert res.params[1] > 0 and res.params[2] < 0


def test_logistic_rejects_non_binary():
    X = np.random.default_rng(1).normal(size=(50, 1))
    y = np.array([0, 1, 2] * 17)[:50]
    with pytest.raises(ValueError):
        LogisticModel().fit(X, y)


def test_logistic_separation_warns():
    X = np.linspace(-3, 3, 40).reshape(-1, 1)
    y = (X.ravel() > 0).astype(int)  # perfectly separable
    res = LogisticModel().fit(X, y, max_iter=50)
    assert any("separation" in w.lower() or "did not converge" in w.lower()
               for w in res.warnings)


def test_logistic_class_imbalance_warns():
    rng = np.random.default_rng(2)
    X = rng.normal(size=(500, 1))
    y = np.zeros(500, dtype=int)
    y[:10] = 1  # 2% positives
    res = LogisticModel().fit(X, y)
    assert any("imbalance" in w.lower() for w in res.warnings)


def test_roc_auc_perfect_and_random():
    y = np.array([0, 0, 1, 1])
    assert roc_auc(y, np.array([0.1, 0.2, 0.8, 0.9])) == pytest.approx(1.0)
    assert roc_auc(y, np.array([0.5, 0.5, 0.5, 0.5])) == pytest.approx(0.5)


def test_classification_metrics_shape():
    rng = np.random.default_rng(3)
    X = rng.normal(size=(200, 2))
    y = (X[:, 0] + rng.normal(scale=0.5, size=200) > 0).astype(int)
    model = LogisticModel()
    model.fit(X, y)
    m = model.classification_metrics(X, y)
    assert set(m["confusion_matrix"]) == {"tp", "tn", "fp", "fn"}
    assert 0 <= m["accuracy"] <= 1
    assert 0 <= m["pr_auc"] <= 1 or np.isnan(m["pr_auc"])
