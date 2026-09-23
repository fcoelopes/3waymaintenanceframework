import math

import pytest

from app.core.rcpsp import RCPSPScheduler
from app.rcpsp_models import (
    AtividadeRCPSP,
    BloqueioRecursoRCPSP,
    InstanciaRCPSP,
    RecursoRCPSP,
    RequisitoRecursoRCPSP,
)


def req(rid: str, q: int = 1) -> list[RequisitoRecursoRCPSP]:
    return [RequisitoRecursoRCPSP(recurso_id=rid, quantidade=q)]


def test_precedencia_define_makespan():
    instancia = InstanciaRCPSP(
        janela_h=8,
        time_unit_minutes=60,
        recursos=[],
        atividades=[
            AtividadeRCPSP(
                id="A",
                nome="A",
                work_package_id="WP1",
                duracao_h=2,
            ),
            AtividadeRCPSP(
                id="B",
                nome="B",
                work_package_id="WP1",
                duracao_h=3,
                predecessores=["A"],
            ),
        ],
    )

    r = RCPSPScheduler(instancia).solve()
    assert r.status == "optimal"
    assert math.isclose(r.makespan_h, 5.0)
    by_id = {a.id: a for a in r.atividades}
    assert by_id["B"].inicio_h >= by_id["A"].fim_h


def test_recurso_capacidade_um_serializa_atividades():
    recurso = RecursoRCPSP(id="MEC", nome="Mecânicos", capacidade=1)
    instancia = InstanciaRCPSP(
        janela_h=8,
        time_unit_minutes=60,
        recursos=[recurso],
        atividades=[
            AtividadeRCPSP(
                id="A",
                nome="A",
                work_package_id="WP1",
                duracao_h=3,
                recursos=req("MEC"),
            ),
            AtividadeRCPSP(
                id="B",
                nome="B",
                work_package_id="WP2",
                duracao_h=3,
                recursos=req("MEC"),
            ),
        ],
    )

    r = RCPSPScheduler(instancia).solve()
    assert r.status == "optimal"
    assert math.isclose(r.makespan_h, 6.0)


def test_recurso_capacidade_dois_permite_paralelismo():
    recurso = RecursoRCPSP(id="MEC", nome="Mecânicos", capacidade=2)
    instancia = InstanciaRCPSP(
        janela_h=8,
        time_unit_minutes=60,
        recursos=[recurso],
        atividades=[
            AtividadeRCPSP(
                id="A",
                nome="A",
                work_package_id="WP1",
                duracao_h=3,
                recursos=req("MEC"),
            ),
            AtividadeRCPSP(
                id="B",
                nome="B",
                work_package_id="WP2",
                duracao_h=3,
                recursos=req("MEC"),
            ),
        ],
    )

    r = RCPSPScheduler(instancia).solve()
    assert r.status == "optimal"
    assert math.isclose(r.makespan_h, 3.0)


def test_recurso_exclusivo_respeita_bloqueio():
    guindaste = RecursoRCPSP(
        id="G",
        nome="Guindaste",
        capacidade=1,
        exclusivo=True,
    )
    instancia = InstanciaRCPSP(
        janela_h=8,
        time_unit_minutes=60,
        recursos=[guindaste],
        bloqueios_recursos=[
            BloqueioRecursoRCPSP(
                recurso_id="G",
                inicio_h=0,
                fim_h=3,
                reducao_capacidade=1,
                motivo="indisponível",
            )
        ],
        atividades=[
            AtividadeRCPSP(
                id="ICAR",
                nome="Içamento",
                work_package_id="WP1",
                duracao_h=4,
                recursos=req("G"),
            )
        ],
    )

    r = RCPSPScheduler(instancia).solve()
    assert r.status == "optimal"
    assert math.isclose(r.makespan_h, 7.0)
    assert r.atividades[0].inicio_h >= 3.0


def test_detecta_inviabilidade_por_caminho_critico():
    instancia = InstanciaRCPSP(
        janela_h=7,
        time_unit_minutes=60,
        atividades=[
            AtividadeRCPSP(
                id="A",
                nome="A",
                work_package_id="WP1",
                duracao_h=4,
            ),
            AtividadeRCPSP(
                id="B",
                nome="B",
                work_package_id="WP1",
                duracao_h=4,
                predecessores=["A"],
            ),
        ],
    )

    r = RCPSPScheduler(instancia).solve()
    assert r.status == "infeasible"
    assert any("Caminho crítico" in d for d in r.diagnosticos)


def test_discretizacao_e_conservadora():
    instancia = InstanciaRCPSP(
        janela_h=3,
        time_unit_minutes=15,
        atividades=[
            AtividadeRCPSP(
                id="A",
                nome="A",
                work_package_id="WP1",
                duracao_h=2.1,
            )
        ],
    )

    r = RCPSPScheduler(instancia).solve()
    assert r.status == "optimal"
    # 2.1 h -> 2.25 h em ticks de 15 min; nunca arredonda para baixo.
    assert math.isclose(r.makespan_h, 2.25)


def test_rejeita_ciclo_de_precedencias():
    instancia = InstanciaRCPSP(
        janela_h=10,
        atividades=[
            AtividadeRCPSP(
                id="A",
                nome="A",
                work_package_id="WP",
                duracao_h=1,
                predecessores=["B"],
            ),
            AtividadeRCPSP(
                id="B",
                nome="B",
                work_package_id="WP",
                duracao_h=1,
                predecessores=["A"],
            ),
        ],
    )

    with pytest.raises(ValueError, match="ciclo"):
        RCPSPScheduler(instancia)
