import numpy as np

from app.core.bruss_xr import aplicar_bruss_xr, indice_parada_otima_bruss, soma_odds_acumulada
from app.models import Parada, ParametrosAtivoBruss


def test_soma_odds():
    assert np.allclose(soma_odds_acumulada(np.array([0.4, 0.4, 0.4])), [1.2, 0.8, 0.4])
    assert indice_parada_otima_bruss(np.array([0.4, 0.4, 0.4])) == 0


def test_bruss_produz_ranking():
    paradas = [Parada(id=i, inicio=i * 10, duracao=4) for i in range(1, 5)]
    p = ParametrosAtivoBruss(
        ativo_id="A1",
        idade_atual=100,
        weibull_beta=1.5,
        weibull_eta=200,
        mttr=5,
        sigma_t=2,
    )
    r = aplicar_bruss_xr(paradas, p, 0.3)
    ranks = [a.rank for a in r.avaliacoes if a.rank is not None]
    assert sorted(ranks) == [1, 2, 3, 4]
    assert all(0 <= a.p <= 1 for a in r.avaliacoes)
    assert all(0 <= a.R <= 1 for a in r.avaliacoes)


def test_idade_atual_reduz_p_para_weibull_com_hazard_crescente():
    paradas = [Parada(id=1, inicio=100, duracao=5)]
    jovem = ParametrosAtivoBruss(
        ativo_id="A1",
        idade_atual=0,
        weibull_beta=2.0,
        weibull_eta=600,
        mttr=5,
        sigma_t=2,
    )
    velho = ParametrosAtivoBruss(
        ativo_id="A1",
        idade_atual=500,
        weibull_beta=2.0,
        weibull_eta=600,
        mttr=5,
        sigma_t=2,
    )

    r_jovem = aplicar_bruss_xr(paradas, jovem, 0.0).avaliacoes[0]
    r_velho = aplicar_bruss_xr(paradas, velho, 0.0).avaliacoes[0]

    assert r_velho.R < r_jovem.R
    assert r_velho.p < r_jovem.p
