"""Orquestração das três camadas do framework de apoio à decisão.

A intenção é manter os motores independentes e conectar somente seus contratos:
PROMETHEE -> prioridade do ativo;
Bruss X·R -> oportunidade temporal;
Selective Maintenance -> ação/portfólio dentro da janela.
"""
from __future__ import annotations

from collections import defaultdict

from app.models import DecisaoIntegrada, ResultadoBrussAtivo, ResultadoPROMETHEE


def construir_decisoes_integradas(
    resultado_promethee: ResultadoPROMETHEE,
    resultado_bruss: dict[str, ResultadoBrussAtivo],
    nomes_ativos: dict[str, str] | None = None,
) -> list[DecisaoIntegrada]:
    """Consolida QUEM + QUANDO sem misturar os scores na função objetivo operacional."""
    nomes_ativos = nomes_ativos or {}
    linhas: list[DecisaoIntegrada] = []
    for aid, rank in sorted(zip(resultado_promethee.ids, resultado_promethee.ranks), key=lambda x: x[1]):
        br = resultado_bruss.get(aid)
        if br is None:
            continue
        recomendada = next(
            (a for a in br.avaliacoes if a.parada_id == br.parada_otima_id),
            None,
        )
        if recomendada is None:
            linhas.append(DecisaoIntegrada(
                rank_promethee=int(rank),
                ativo_id=aid,
                ativo_nome=nomes_ativos.get(aid, br.ativo_nome),
                parada_recomendada_id=None,
                instante_parada=None,
                duracao_parada=None,
                p_sucesso=None,
                tipo_decisao="degradada",
                threshold_usado=br.threshold_aplicado,
                observacao="Sem oportunidade recomendada no horizonte.",
            ))
            continue
        obs = {
            "otima": "Oportunidade aceita pelo threshold.",
            "otima_threshold_alto": "Bruss aponta a oportunidade, mas p está abaixo do threshold.",
            "degradada": "Decisão degradada: soma de odds insuficiente.",
            "eliminada": "Oportunidade eliminada.",
        }[recomendada.tipo_decisao]
        linhas.append(DecisaoIntegrada(
            rank_promethee=int(rank),
            ativo_id=aid,
            ativo_nome=nomes_ativos.get(aid, br.ativo_nome),
            parada_recomendada_id=recomendada.parada_id,
            instante_parada=recomendada.inicio,
            duracao_parada=recomendada.duracao,
            p_sucesso=recomendada.p,
            tipo_decisao=recomendada.tipo_decisao,
            threshold_usado=br.threshold_aplicado,
            observacao=obs,
        ))
    return linhas


def agrupar_candidatos_por_parada(
    decisoes: list[DecisaoIntegrada],
) -> dict[int, list[str]]:
    """Retorna {parada_id: [ativo_id,...]} para alimentar a camada Selective."""
    grupos: dict[int, list[str]] = defaultdict(list)
    for d in decisoes:
        if d.parada_recomendada_id is not None:
            grupos[d.parada_recomendada_id].append(d.ativo_id)
    return dict(grupos)


def proxima_oportunidade(
    resultado: ResultadoBrussAtivo,
    parada_atual_id: int,
) -> int | None:
    """Fallback simples: próxima oportunidade ranqueada após a rejeitada pelo Selective."""
    ranked = [a for a in resultado.avaliacoes if a.rank is not None]
    ranked.sort(key=lambda a: a.rank or 10**9)
    pos = next((i for i, a in enumerate(ranked) if a.parada_id == parada_atual_id), None)
    if pos is None:
        return None
    for a in ranked[pos + 1:]:
        if a.tipo_decisao != "eliminada":
            return a.parada_id
    return None
