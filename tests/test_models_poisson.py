import numpy as np
import pytest

from statinvest.models.poisson import PoissonModel


def test_poisson_recovers_rate():
    rng = np.random.default_rng(0)
    X = rng.normal(size=(800, 1))
    mu = np.exp(0.5 + 0.8 * X[:, 0])
    y = rng.poisson(mu)
    res = PoissonModel().fit(X, y)
    assert res.converged
    assert res.params[0] == pytest.approx(0.5, abs=0.15)
    assert res.params[1] == pytest.approx(0.8, abs=0.15)


def test_poisson_rejects_non_integer():
    X = np.random.default_rng(1).normal(size=(20, 1))
    y = np.array([0.5] * 20)
    with pytest.raises(ValueError):
        PoissonModel().fit(X, y)


def test_poisson_rejects_negative():
    X = np.random.default_rng(2).normal(size=(20, 1))
    y = np.array([-1] + [1] * 19)
    with pytest.raises(ValueError):
        PoissonModel().fit(X, y)


def test_poisson_offset_supported():
    rng = np.random.default_rng(3)
    X = rng.normal(size=(400, 1))
    exposure = rng.uniform(1, 5, size=400)
    mu = exposure * np.exp(0.2 + 0.5 * X[:, 0])
    y = rng.poisson(mu)
    res = PoissonModel().fit(X, y, exposure=exposure)
    assert res.converged
    assert res.params[1] == pytest.approx(0.5, abs=0.2)


def test_poisson_offset_requires_positive():
    X = np.random.default_rng(4).normal(size=(10, 1))
    y = np.random.default_rng(4).poisson(2, size=10)
    with pytest.raises(ValueError):
        PoissonModel().fit(X, y, exposure=np.zeros(10))


def test_poisson_overdispersion_warns():
    rng = np.random.default_rng(5)
    X = rng.normal(size=(500, 1))
    # Negative-binomial-like overdispersed counts.
    mu = np.exp(1.0 + 0.5 * X[:, 0])
    y = rng.negative_binomial(2, 2 / (2 + mu))
    res = PoissonModel().fit(X, y)
    assert any("overdispersion" in w.lower() for w in res.warnings)


def test_poisson_excess_zeros_warns():
    rng = np.random.default_rng(6)
    X = rng.normal(size=(300, 1))
    y = np.zeros(300, dtype=int)
    y[:60] = rng.poisson(3, size=60)  # 80% zeros
    res = PoissonModel().fit(X, y)
    assert any("excess zeros" in w.lower() for w in res.warnings)
