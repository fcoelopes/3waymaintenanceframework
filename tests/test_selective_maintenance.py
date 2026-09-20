from app.core.selective_maintenance import SelectiveMaintenanceProblem
from app.models import ComponenteSelective, NoRBD


def C(cid):
    return NoRBD(tipo="component", componente_id=cid)


def elementary_problem(mode="deterministic"):
    componentes = [
        ComponenteSelective(ativo_id="3", nome="C3", operacional=True, idade=30, weibull_beta=3, weibull_eta=120, tempo_reparo_minimo=3, tempo_substituicao_falhado=5, tempo_substituicao_operacional=1),
        ComponenteSelective(ativo_id="4", nome="C4", operacional=False, idade=60, weibull_beta=4, weibull_eta=150, tempo_reparo_minimo=2, tempo_substituicao_falhado=4, tempo_substituicao_operacional=2),
        ComponenteSelective(ativo_id="5", nome="C5", operacional=True, idade=28, weibull_beta=2.5, weibull_eta=130, tempo_reparo_minimo=1, tempo_substituicao_falhado=3, tempo_substituicao_operacional=2),
        ComponenteSelective(ativo_id="6", nome="C6", operacional=False, idade=56, weibull_beta=4, weibull_eta=180, tempo_reparo_minimo=2, tempo_substituicao_falhado=6, tempo_substituicao_operacional=3),
    ]
    topo = NoRBD(tipo="series", filhos=[C("3"), NoRBD(tipo="parallel", filhos=[C("4"), C("5")]), C("6")])
    return SelectiveMaintenanceProblem(componentes, topo, 40, 6, modo_tempo=mode, alpha_conclusao=0.9, n_simulacoes=3000, seed=1)


def test_reproduz_artigo_no_modo_deterministico():
    r = elementary_problem("deterministic").solve_exact()
    assert abs(r.confiabilidade_final - 0.874198) < 1e-5
    assert r.tempo_esperado <= 6


def test_estocastico_respeita_chance_constraint():
    r = elementary_problem("stochastic").solve_heuristic()
    assert r.probabilidade_conclusao >= r.alpha_conclusao - 1e-12
    assert r.tempo_p95 >= r.tempo_p50
