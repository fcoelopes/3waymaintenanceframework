import numpy as np
from app.core.monte_carlo import perturbar_pesos, simular


def test_perturbar_pesos_normaliza():
    rng = np.random.default_rng(1)
    w = perturbar_pesos(np.array([0.6, 0.4]), 0.2, rng)
    assert np.isclose(w.sum(), 1.0)
    assert np.all(w > 0)


def test_simular_shapes():
    x = np.array([[10, 10], [5, 5], [1, 1]], dtype=float)
    out = simular(
        x, np.array([0.5, 0.5]), np.array([0, 0]), np.array([1, 1]), np.array([1, 1]),
        n_iter=50, n_top=2, seed=1,
    )
    assert out["rank_samples"].shape == (50, 3)
    assert out["prob_top_n"].shape == (3,)
