import numpy as np
from app.core.promethee import preferencia_v, calcular_ranking


def test_preferencia_v():
    d = np.array([0.0, 1.5, 3.0])
    p = preferencia_v(d, 1.0, 2.0)
    assert p[0] == 0
    assert p[1] == 0.5
    assert p[2] == 1


def test_dominante_primeiro():
    x = np.array([[10, 10], [5, 5], [1, 1]], dtype=float)
    plus, minus, net, ranks = calcular_ranking(
        x, np.array([0.5, 0.5]), np.array([0.0, 0.0]), np.array([1.0, 1.0]), np.array([1, 1])
    )
    assert ranks[0] == 1
    assert np.allclose(net, plus - minus)
