"""Ponte mínima entre Selective Maintenance e RCPSP.

O Selective decide o portfólio de ações. O RCPSP precisa de uma WBS detalhada.
Esta função gera apenas um *rascunho* de work packages: uma atividade por ação
selecionada. Antes de usar o cronograma operacionalmente, essas atividades devem
ser decompostas em isolamento, desmontagem, inspeção, içamento, montagem, testes,
etc., com precedências e recursos reais.
"""
from __future__ import annotations

from app.models import ResultadoSelective
from app.rcpsp_models import (
    AtividadeRCPSP,
    InstanciaRCPSP,
    RecursoRCPSP,
    RequisitoRecursoRCPSP,
)


def rascunho_rcpsp_do_selective(
    resultado: ResultadoSelective,
    *,
    janela_h: float,
    capacidade_equipe_geral: int = 1,
    time_unit_minutes: int = 15,
) -> InstanciaRCPSP:
    if capacidade_equipe_geral <= 0:
        raise ValueError("capacidade_equipe_geral deve ser > 0")

    recurso = RecursoRCPSP(
        id="equipe_geral",
        nome="Equipe geral — rascunho",
        capacidade=capacidade_equipe_geral,
    )
    atividades = []
    for item in resultado.itens:
        if item.acao == "none":
            continue
        atividades.append(
            AtividadeRCPSP(
                id=f"{item.ativo_id}:{item.acao}",
                nome=f"{item.ativo_nome} — {item.acao}",
                work_package_id=f"WP-{item.ativo_id}",
                ativo_id=item.ativo_id,
                acao_origem=item.acao,
                duracao_h=max(item.mttr_acao, time_unit_minutes / 60.0),
                recursos=[
                    RequisitoRecursoRCPSP(
                        recurso_id=recurso.id,
                        quantidade=1,
                    )
                ],
            )
        )

    if not atividades:
        raise ValueError("resultado Selective não contém ações selecionadas")

    return InstanciaRCPSP(
        janela_h=janela_h,
        atividades=atividades,
        recursos=[recurso],
        time_unit_minutes=time_unit_minutes,
    )
