import math
import numpy as np
import pytest

from app.core.reliability import (
    maintainability,
    maintainability_exponential,
    maintainability_lognormal,
    p_success_combined,
    reliability_weibull,
    survival_rul_weibull,
)


def test_lognormal_zero_e_monotona():
    assert maintainability_lognormal(0.0, 5.0, 2.0) == 0.0
    ds = np.array([1.0, 3.0, 5.0, 10.0])
    ms = maintainability_lognormal(ds, 5.0, 2.0)
    assert np.all(np.diff(ms) > 0)


def test_lognormal_mediana():
    varlog = math.log(1 + (2 / 5) ** 2)
    med = math.exp(math.log(5) - varlog / 2)
    assert abs(maintainability_lognormal(med, 5, 2) - 0.5) < 1e-9


def test_exponencial_no_mttr():
    assert abs(maintainability_exponential(5, 5) - (1 - 1 / math.e)) < 1e-12


def test_dispatcher_requer_sigma():
    with pytest.raises(ValueError):
        maintainability(5, 5)


def test_weibull_no_eta():
    for beta in [0.5, 1.0, 2.0]:
        assert abs(reliability_weibull(600, beta, 600) - 1 / math.e) < 1e-12


def test_sobrevivencia_rul_condicional():
    beta, eta = 2.0, 600.0
    idade, horizonte = 300.0, 100.0

    esperado = (
        reliability_weibull(idade + horizonte, beta, eta)
        / reliability_weibull(idade, beta, eta)
    )
    obtido = survival_rul_weibull(horizonte, idade, beta, eta)

    assert math.isclose(obtido, esperado, rel_tol=1e-12)
    assert math.isclose(
        survival_rul_weibull(horizonte, 0.0, beta, eta),
        reliability_weibull(horizonte, beta, eta),
        rel_tol=1e-12,
    )


def test_ativo_mais_velho_tem_menor_sobrevivencia_residual_para_beta_maior_que_um():
    jovem = survival_rul_weibull(100, 0, 2.0, 600)
    velho = survival_rul_weibull(100, 500, 2.0, 600)
    assert velho < jovem


def test_p_combinada_intervalo_e_idade():
    p_jovem = p_success_combined(300, 5, 1.5, 600, 0, 5, 2, idade_atual=0)
    p_velho = p_success_combined(300, 5, 1.5, 600, 0, 5, 2, idade_atual=500)
    assert 0 < p_velho < p_jovem < 1
