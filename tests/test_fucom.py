import numpy as np
import pytest

from app.core.fucom import (
    calcular_pesos,
    consistencia_chi,
    resolver_fucom,
    status_consistencia,
)


def test_fucom_resolve_modelo_de_otimizacao():
    phis = [1.0, 1.3, 1.2, 1.4, 1.5]
    resultado = resolver_fucom(phis)

    assert resultado.sucesso
    assert np.isclose(resultado.pesos.sum(), 1.0)
    assert np.all(resultado.pesos > 0)
    assert resultado.chi < 1e-8
    assert status_consistencia(resultado.chi) == "Plena"

    # Relações consecutivas e transitivas precisam ser respeitadas.
    w = resultado.pesos
    for k in range(len(w) - 1):
        assert np.isclose(w[k] / w[k + 1], phis[k + 1], atol=1e-7)
    for k in range(len(w) - 2):
        assert np.isclose(
            w[k] / w[k + 2],
            phis[k + 1] * phis[k + 2],
            atol=1e-7,
        )


def test_api_calcular_pesos_permanece_compativel():
    phis = [1.0, 1.3, 1.2]
    w = calcular_pesos(phis)
    assert np.isclose(w.sum(), 1.0)
    assert consistencia_chi(w, phis) < 1e-8


def test_phi_invalido():
    with pytest.raises(ValueError):
        calcular_pesos([1.0, 0.9])
