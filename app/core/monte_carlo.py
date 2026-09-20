"""Robustez do ranking PROMETHEE II via Monte Carlo."""
from __future__ import annotations

import numpy as np

from app.core.promethee import calcular_ranking


def perturbar_pesos(pesos_nominais: np.ndarray, delta: float, rng: np.random.Generator) -> np.ndarray:
    if not 0 <= delta <= 1:
        raise ValueError("delta deve estar em [0,1]")
    w = np.asarray(pesos_nominais, dtype=float)
    if np.any(w < 0) or w.sum() <= 0:
        raise ValueError("pesos inválidos")
    lo, hi = w * (1 - delta), w * (1 + delta)
    sampled = rng.uniform(lo, hi)
    sampled = np.clip(sampled, 1e-12, None)
    return sampled / sampled.sum()


def perturbar_desempenhos(
    matriz: np.ndarray,
    delta: float,
    rng: np.random.Generator,
    limites: dict[int, tuple[float, float]] | None = None,
) -> np.ndarray:
    if delta < 0:
        raise ValueError("delta deve ser >= 0")
    x = np.asarray(matriz, dtype=float)
    noise = rng.triangular(-delta, 0.0, delta, size=x.shape)
    out = x * (1.0 + noise)
    if limites:
        for j, (lo, hi) in limites.items():
            out[:, j] = np.clip(out[:, j], lo, hi)
    return out


def simular(
    matriz_desempenho: np.ndarray,
    pesos: np.ndarray,
    qs: np.ndarray,
    ps: np.ndarray,
    direcoes: np.ndarray,
    n_iter: int = 1000,
    delta_pesos: float = 0.20,
    delta_desempenho: float = 0.15,
    n_top: int = 10,
    limites_criterios: dict[int, tuple[float, float]] | None = None,
    seed: int | None = None,
) -> dict[str, np.ndarray]:
    if n_iter <= 0:
        raise ValueError("n_iter deve ser > 0")
    x = np.asarray(matriz_desempenho, dtype=float)
    n_alt = x.shape[0]
    n_top = max(1, min(int(n_top), n_alt))
    rng = np.random.default_rng(seed)
    _, _, _, nominal = calcular_ranking(x, pesos, qs, ps, direcoes)
    rank_samples = np.empty((n_iter, n_alt), dtype=int)

    for i in range(n_iter):
        w = perturbar_pesos(pesos, delta_pesos, rng)
        xx = perturbar_desempenhos(x, delta_desempenho, rng, limites_criterios)
        _, _, _, ranks = calcular_ranking(xx, w, qs, ps, direcoes)
        rank_samples[i] = ranks

    rank_modal = np.array([
        np.bincount(rank_samples[:, j], minlength=n_alt + 1)[1:].argmax() + 1
        for j in range(n_alt)
    ])
    return {
        "rank_nominal": nominal,
        "rank_modal": rank_modal,
        "rank_medio": rank_samples.mean(axis=0),
        "rank_p5": np.quantile(rank_samples, 0.05, axis=0),
        "rank_p95": np.quantile(rank_samples, 0.95, axis=0),
        "prob_top_n": 100.0 * np.mean(rank_samples <= n_top, axis=0),
        "rank_samples": rank_samples,
    }


def classificar_estabilidade(
    prob_top_n: float,
    rank_modal: int,
    rank_nominal: int,
    limiar_robusto: float = 80.0,
    limiar_moderado: float = 50.0,
    delta_modal: int = 2,
) -> str:
    desloc = abs(int(rank_modal) - int(rank_nominal))
    if prob_top_n >= limiar_robusto and desloc <= delta_modal:
        return "Robusto"
    if prob_top_n >= limiar_moderado and desloc <= 2 * delta_modal:
        return "Moderado"
    return "Frágil"
