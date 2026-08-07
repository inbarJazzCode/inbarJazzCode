import numpy as np
import pytest

from statinvest.models.linear import OLSModel


def test_ols_coefficient_recovery():
    rng = np.random.default_rng(0)
    X = rng.normal(size=(500, 3))
    beta = np.array([1.5, -2.0, 0.7])
    y = 4.0 + X @ beta + rng.normal(scale=0.2, size=500)
    res = OLSModel().fit(X, y)
    assert np.allclose(res.params[0], 4.0, atol=0.1)
    assert np.allclose(res.params[1:], beta, atol=0.1)
    assert 0.9 < res.r_squared <= 1.0


def test_ols_singular_design_warns():
    rng = np.random.default_rng(1)
    x = rng.normal(size=200)
    X = np.column_stack([x, x])  # perfectly collinear
    y = 2 * x + rng.normal(scale=0.1, size=200)
    res = OLSModel().fit(X, y)
    assert any("Rank-deficient" in w or "multicollinear" in w.lower()
               for w in res.warnings)


def test_ols_constant_column_detected():
    rng = np.random.default_rng(2)
    x = rng.normal(size=100)
    const = np.ones(100)
    X = np.column_stack([x, const])
    y = x + rng.normal(scale=0.1, size=100)
    res = OLSModel().fit(X, y)
    assert any("constant" in w.lower() for w in res.warnings)


def test_ols_tiny_sample_warns():
    X = np.array([[1.0], [2.0]])
    y = np.array([1.0, 2.0])
    res = OLSModel().fit(X, y)
    assert any("Tiny sample" in w for w in res.warnings)


def test_ols_robust_se_differs_under_heteroskedasticity():
    rng = np.random.default_rng(3)
    x = rng.uniform(1, 5, size=400)
    y = 1 + 2 * x + rng.normal(scale=x, size=400)  # variance grows with x
    m1 = OLSModel().fit(x, y, se_type="classical")
    m2 = OLSModel().fit(x, y, se_type="hc3")
    assert not np.allclose(m1.se, m2.se)


def test_ols_vif_and_cooks():
    rng = np.random.default_rng(4)
    X = rng.normal(size=(200, 2))
    y = X[:, 0] + rng.normal(scale=0.3, size=200)
    model = OLSModel()
    model.fit(X, y)
    vifs = model.variance_inflation_factors()
    assert set(vifs) == {"x1", "x2"}
    assert len(model.cooks_distance()) == 200


def test_ols_uses_stable_solver_not_inverse():
    # ill-conditioned but full rank; lstsq should still solve.
    rng = np.random.default_rng(5)
    x = rng.normal(size=300)
    X = np.column_stack([x, x + 1e-6 * rng.normal(size=300)])
    y = x + rng.normal(scale=0.1, size=300)
    res = OLSModel().fit(X, y)
    assert np.isfinite(res.params).all()
