"""Bruss X·R para seleção temporal de oportunidades de manutenção.

O estágio recebe a agenda de paradas e, para cada ativo, calcula
p_i = M(d_i) * R(a_i). As odds r_i=p_i/(1-p_i) alimentam a regra de Bruss.
A aplicação recursiva produz uma ordenação das oportunidades.
"""
from __future__ import annotations

import numpy as np

from app.core.reliability import p_success_combined, maintainability, reliability_weibull
from app.models import (
    AgendaParadasPlanta,
    AvaliacaoParada,
    ParametrosAtivoBruss,
    ResultadoBrussAtivo,
)


def soma_odds_acumulada(odds: np.ndarray) -> np.ndarray:
    arr = np.asarray(odds, dtype=float)
    if arr.ndim != 1:
        raise ValueError("odds deve ser vetor 1D")
    if np.any(arr < 0):
        raise ValueError("odds não podem ser negativas")
    return np.cumsum(arr[::-1])[::-1]


def indice_parada_otima_bruss(odds: np.ndarray) -> int:
    arr = np.asarray(odds, dtype=float)
    if arr.ndim != 1 or len(arr) == 0:
        raise ValueError("Informe ao menos uma odd")
    s = soma_odds_acumulada(arr)
    valid = np.flatnonzero(s >= 1.0)
    return int(valid[-1]) if len(valid) else 0


def aplicar_bruss_xr(
    paradas,
    parametros: ParametrosAtivoBruss,
    threshold: float,
    tipo_mantenabilidade: str = "lognormal",
    ativo_nome: str | None = None,
) -> ResultadoBrussAtivo:
    if not 0 <= threshold <= 1:
        raise ValueError("threshold deve estar em [0,1]")
    if not paradas:
        raise ValueError("Informe ao menos uma parada")
    paradas = sorted(paradas, key=lambda p: (p.inicio, p.id))
    if len({p.id for p in paradas}) != len(paradas):
        raise ValueError("IDs de parada devem ser únicos")

    base: dict[int, dict] = {}
    for p in paradas:
        prob = p_success_combined(
            instante=p.inicio,
            duracao=p.duracao,
            weibull_beta=parametros.weibull_beta,
            weibull_eta=parametros.weibull_eta,
            weibull_gamma=parametros.weibull_gamma,
            mttr=parametros.mttr,
            sigma_t=parametros.sigma_t,
            tipo_mantenabilidade=tipo_mantenabilidade,  # type: ignore[arg-type]
        )
        x = float(maintainability(
            p.duracao,
            parametros.mttr,
            parametros.sigma_t,
            tipo_mantenabilidade,  # type: ignore[arg-type]
        ))
        r = float(reliability_weibull(
            p.inicio,
            parametros.weibull_beta,
            parametros.weibull_eta,
            parametros.weibull_gamma,
        ))
        odd = float("inf") if prob >= 1.0 else prob / max(1e-15, 1.0 - prob)
        base[p.id] = {"parada": p, "p": prob, "X": x, "R": r, "odd": odd}

    # p==0 não carrega informação útil para a regra de parada.
    disponiveis = [p.id for p in paradas if base[p.id]["p"] > 0.0]
    eliminadas = [p.id for p in paradas if base[p.id]["p"] <= 0.0]
    ranked: list[AvaliacaoParada] = []
    rank = 1

    while disponiveis:
        odds = np.asarray([base[pid]["odd"] for pid in disponiveis], dtype=float)
        sums = soma_odds_acumulada(odds)
        k = indice_parada_otima_bruss(odds)
        pid = disponiveis[k]
        item = base[pid]
        soma = float(sums[k])
        prob = float(item["p"])

        if soma < 1.0:
            tipo = "degradada"
        elif prob >= threshold:
            tipo = "otima"
        else:
            tipo = "otima_threshold_alto"

        p = item["parada"]
        ranked.append(AvaliacaoParada(
            parada_id=p.id,
            inicio=p.inicio,
            duracao=p.duracao,
            X=item["X"],
            R=item["R"],
            p=prob,
            odd=item["odd"],
            rank=rank,
            tipo_decisao=tipo,
            soma_odds_acumulada=soma,
        ))
        disponiveis.pop(k)
        rank += 1

    for pid in eliminadas:
        item = base[pid]
        p = item["parada"]
        ranked.append(AvaliacaoParada(
            parada_id=p.id,
            inicio=p.inicio,
            duracao=p.duracao,
            X=item["X"],
            R=item["R"],
            p=item["p"],
            odd=item["odd"],
            rank=None,
            tipo_decisao="eliminada",
            soma_odds_acumulada=None,
        ))

    ranked.sort(key=lambda a: (a.rank is None, a.rank if a.rank is not None else 10**9, a.parada_id))
    recomendada = next((a.parada_id for a in ranked if a.tipo_decisao == "otima"), None)
    if recomendada is None:
        recomendada = next(
            (a.parada_id for a in ranked if a.tipo_decisao == "otima_threshold_alto"),
            None,
        )

    return ResultadoBrussAtivo(
        ativo_id=parametros.ativo_id,
        ativo_nome=ativo_nome or parametros.ativo_id,
        threshold_aplicado=threshold,
        avaliacoes=ranked,
        parada_otima_id=recomendada,
        n_otimas=sum(a.tipo_decisao == "otima" for a in ranked),
        n_degradadas=sum(a.tipo_decisao == "degradada" for a in ranked),
        n_eliminadas=sum(a.tipo_decisao == "eliminada" for a in ranked),
    )


def aplicar_bruss_carteira(
    agenda: AgendaParadasPlanta,
    parametros_por_ativo: dict[str, ParametrosAtivoBruss],
    threshold_global: float,
    tipo_mantenabilidade: str = "lognormal",
    nomes_ativos: dict[str, str] | None = None,
) -> dict[str, ResultadoBrussAtivo]:
    out: dict[str, ResultadoBrussAtivo] = {}
    for aid, parametros in parametros_por_ativo.items():
        threshold = (
            parametros.threshold_override
            if parametros.threshold_override is not None
            else threshold_global
        )
        out[aid] = aplicar_bruss_xr(
            agenda.paradas,
            parametros,
            float(threshold),
            tipo_mantenabilidade,
            ativo_nome=(nomes_ativos or {}).get(aid, aid),
        )
    return out


def sensibilidade_threshold(
    paradas,
    parametros: ParametrosAtivoBruss,
    thresholds: np.ndarray,
    tipo_mantenabilidade: str = "lognormal",
) -> dict[str, np.ndarray]:
    th = np.asarray(thresholds, dtype=float)
    if np.any((th < 0) | (th > 1)):
        raise ValueError("thresholds devem estar em [0,1]")
    parada_otima = []
    n_eliminadas = []
    n_otimas = []
    ids = [p.id for p in sorted(paradas, key=lambda p: (p.inicio, p.id))]
    matriz = np.full((len(th), len(ids)), np.nan)
    id_to_col = {pid: i for i, pid in enumerate(ids)}

    for row, t in enumerate(th):
        r = aplicar_bruss_xr(paradas, parametros, float(t), tipo_mantenabilidade)
        parada_otima.append(np.nan if r.parada_otima_id is None else r.parada_otima_id)
        n_eliminadas.append(r.n_eliminadas)
        n_otimas.append(r.n_otimas)
        for a in r.avaliacoes:
            if a.rank is not None:
                matriz[row, id_to_col[a.parada_id]] = a.rank

    return {
        "thresholds": th,
        "parada_otima": np.asarray(parada_otima, dtype=float),
        "n_eliminadas": np.asarray(n_eliminadas, dtype=int),
        "n_otimas": np.asarray(n_otimas, dtype=int),
        "matriz_ranks": matriz,
    }
