"""Confiabilidade e mantenabilidade usadas pelo framework integrado.

A camada Bruss usa p_i = M(d_i) * R(a_i).  A camada Selective Maintenance
reutiliza a mesma modelagem de duração por MTTR + sigma_T, agora por ação.
"""
from typing import Literal

import numpy as np
from scipy.stats import norm

TipoMantenabilidade = Literal["lognormal", "exponencial"]


def _return_scalar_if_scalar(value, original):
    arr = np.asarray(value, dtype=float)
    if np.isscalar(original):
        return float(arr)
    return arr


def parametros_lognormal(mttr: float, sigma_t: float) -> tuple[float, float]:
    """Converte média/desvio reais para parâmetros logarítmicos (mu, sigma)."""
    if mttr <= 0:
        raise ValueError("mttr deve ser > 0")
    if sigma_t <= 0:
        raise ValueError("sigma_t deve ser > 0")
    sigma_log_sq = float(np.log1p((sigma_t / mttr) ** 2))
    sigma_log = float(np.sqrt(sigma_log_sq))
    mu_log = float(np.log(mttr) - sigma_log_sq / 2.0)
    return mu_log, sigma_log


def maintainability_lognormal(
    duracao: float | np.ndarray,
    mttr: float,
    sigma_t: float,
) -> float | np.ndarray:
    """M(d)=P(T<=d) para T lognormal parametrizado por MTTR e sigma_T."""
    mu_log, sigma_log = parametros_lognormal(mttr, sigma_t)
    d = np.asarray(duracao, dtype=float)
    if np.any(d < 0):
        raise ValueError("duracao deve ser >= 0")
    out = np.zeros_like(d, dtype=float)
    mask = d > 0
    out[mask] = norm.cdf((np.log(d[mask]) - mu_log) / sigma_log)
    return _return_scalar_if_scalar(out, duracao)


def maintainability_exponential(
    duracao: float | np.ndarray,
    mttr: float,
) -> float | np.ndarray:
    """M(d)=1-exp(-d/MTTR), compatibilidade com Thomas et al. (2008)."""
    if mttr <= 0:
        raise ValueError("mttr deve ser > 0")
    d = np.asarray(duracao, dtype=float)
    if np.any(d < 0):
        raise ValueError("duracao deve ser >= 0")
    out = 1.0 - np.exp(-d / mttr)
    return _return_scalar_if_scalar(out, duracao)


def maintainability(
    duracao: float | np.ndarray,
    mttr: float,
    sigma_t: float | None = None,
    tipo: TipoMantenabilidade = "lognormal",
) -> float | np.ndarray:
    if tipo == "lognormal":
        if sigma_t is None:
            raise ValueError("sigma_t é obrigatório para mantenabilidade lognormal")
        return maintainability_lognormal(duracao, mttr, sigma_t)
    if tipo == "exponencial":
        return maintainability_exponential(duracao, mttr)
    raise ValueError(f"tipo de mantenabilidade desconhecido: {tipo}")


def reliability_weibull(
    instante: float | np.ndarray,
    beta: float,
    eta: float,
    gamma: float = 0.0,
) -> float | np.ndarray:
    """R(t)=exp(-((t-gamma)/eta)^beta), com R=1 antes de gamma."""
    if beta <= 0:
        raise ValueError("beta deve ser > 0")
    if eta <= 0:
        raise ValueError("eta deve ser > 0")
    if gamma < 0:
        raise ValueError("gamma deve ser >= 0")
    t = np.asarray(instante, dtype=float)
    if np.any(t < 0):
        raise ValueError("instante deve ser >= 0")
    rel = np.maximum(0.0, t - gamma)
    out = np.exp(-((rel / eta) ** beta))
    return _return_scalar_if_scalar(out, instante)


def p_success_combined(
    instante: float,
    duracao: float,
    weibull_beta: float,
    weibull_eta: float,
    weibull_gamma: float,
    mttr: float,
    sigma_t: float | None = None,
    tipo_mantenabilidade: TipoMantenabilidade = "lognormal",
) -> float:
    """Função-sucesso combinada do estágio temporal: p=M(d)*R(t)."""
    m = float(maintainability(duracao, mttr, sigma_t, tipo_mantenabilidade))
    r = float(reliability_weibull(instante, weibull_beta, weibull_eta, weibull_gamma))
    return float(np.clip(m * r, 0.0, 1.0))


def amostrar_lognormal_por_media_desvio(
    mttr: float,
    sigma_t: float,
    size: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Amostra tempos positivos a partir de MTTR + sigma_T reais."""
    if size <= 0:
        raise ValueError("size deve ser > 0")
    mu, sigma = parametros_lognormal(mttr, sigma_t)
    return rng.lognormal(mean=mu, sigma=sigma, size=size)
