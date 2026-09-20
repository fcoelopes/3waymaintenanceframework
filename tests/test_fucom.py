import numpy as np
import pytest
from app.core.fucom import calcular_pesos, consistencia_chi


def test_pesos_fucom():
    phis = [1.0, 1.3, 1.2, 1.4, 1.5]
    w = calcular_pesos(phis)
    assert np.isclose(w.sum(), 1.0)
    assert np.all(np.diff(w) < 0)
    assert consistencia_chi(w, phis) < 1e-12


def test_phi_invalido():
    with pytest.raises(ValueError):
        calcular_pesos([1.0, 0.9])
