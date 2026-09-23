"""FUCOM (Full Consistency Method) para obtenção de pesos de critérios.

A implementação resolve explicitamente o problema de otimização descrito por
Pamučar, Stević & Sremac (2018):

    min chi

sujeito às relações entre critérios consecutivos, à transitividade matemática,
à normalização dos pesos e à não negatividade.

Convenção deste projeto:
- phis[0] = 1.0;
- phis[k] (k >= 1) representa a prioridade comparativa
  w[k-1] / w[k] entre critérios consecutivos, já ordenados por importância.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import minimize


@dataclass(frozen=True, slots=True)
class ResultadoFUCOM:
    pesos: np.ndarray
    chi: float
    sucesso: bool
    mensagem: str


def _validar_phis(phis: list[float] | np.ndarray) -> np.ndarray:
    arr = np.asarray(phis, dtype=float)
    if arr.ndim != 1 or len(arr) < 2:
        raise ValueError("Informe pelo menos dois critérios")
    if not np.isclose(arr[0], 1.0):
        raise ValueError("Por convenção, phi_1 deve ser 1")
    if np.any(~np.isfinite(arr)):
        raise ValueError("Todos os valores phi devem ser finitos")
    if np.any(arr < 1.0):
        raise ValueError("Todos os valores phi devem ser >= 1")
    return arr


def _pesos_consistentes_iniciais(phis: np.ndarray) -> np.ndarray:
    """Ponto inicial factível quando as comparações são plenamente consistentes."""
    rel = np.ones(len(phis), dtype=float)
    for k in range(1, len(phis)):
        rel[k] = rel[k - 1] / phis[k]
    return rel / rel.sum()


def resolver_fucom(phis: list[float] | np.ndarray) -> ResultadoFUCOM:
    """Resolve o modelo FUCOM e retorna pesos + DFC (chi).

    O vetor de decisão é [w_1, ..., w_n, chi]. As restrições de módulo são
    decompostas em duas desigualdades para cada relação.
    """
    p = _validar_phis(phis)
    n = len(p)
    w0 = _pesos_consistentes_iniciais(p)
    x0 = np.concatenate([w0, np.array([1e-10])])

    constraints: list[dict] = [
        {"type": "eq", "fun": lambda x: float(np.sum(x[:-1]) - 1.0)}
    ]

    def adicionar_restricao_ratio(i: int, j: int, alvo: float) -> None:
        # chi >= ratio - alvo
        constraints.append({
            "type": "ineq",
            "fun": lambda x, i=i, j=j, alvo=alvo: float(
                x[-1] - (x[i] / x[j] - alvo)
            ),
        })
        # chi >= -(ratio - alvo)
        constraints.append({
            "type": "ineq",
            "fun": lambda x, i=i, j=j, alvo=alvo: float(
                x[-1] + (x[i] / x[j] - alvo)
            ),
        })

    # Condição 1: relações entre critérios consecutivos.
    for k in range(n - 1):
        adicionar_restricao_ratio(k, k + 1, float(p[k + 1]))

    # Condição 2: transitividade w_k/w_(k+2) = phi_k,k+1 * phi_k+1,k+2.
    for k in range(n - 2):
        alvo = float(p[k + 1] * p[k + 2])
        adicionar_restricao_ratio(k, k + 2, alvo)

    result = minimize(
        fun=lambda x: float(x[-1]),
        x0=x0,
        method="SLSQP",
        bounds=[(1e-12, 1.0)] * n + [(0.0, None)],
        constraints=constraints,
        options={"ftol": 1e-12, "maxiter": 2000},
    )

    if not result.success:
        raise RuntimeError(f"FUCOM não convergiu: {result.message}")

    pesos = np.asarray(result.x[:-1], dtype=float)
    pesos = pesos / pesos.sum()
    chi = max(0.0, float(result.x[-1]))

    # Recalcula o desvio efetivo após normalização para evitar mascarar ruído.
    chi = max(chi, consistencia_chi(pesos, p.tolist()))

    return ResultadoFUCOM(
        pesos=pesos,
        chi=chi,
        sucesso=True,
        mensagem=str(result.message),
    )


def calcular_pesos(phis: list[float] | np.ndarray) -> np.ndarray:
    """Compatibilidade com a API anterior: retorna somente os pesos otimizados."""
    return resolver_fucom(phis).pesos


def consistencia_chi(pesos: np.ndarray, phis: list[float] | np.ndarray) -> float:
    """Calcula a DFC máxima efetiva das duas famílias de restrições FUCOM."""
    w = np.asarray(pesos, dtype=float)
    p = _validar_phis(phis)
    if len(w) != len(p):
        raise ValueError("pesos e phis devem ter o mesmo tamanho")
    if np.any(w <= 0) or not np.isclose(w.sum(), 1.0, atol=1e-8):
        raise ValueError("pesos devem ser positivos e somar 1")

    desvios: list[float] = []
    for k in range(len(w) - 1):
        desvios.append(abs(w[k] / w[k + 1] - p[k + 1]))
    for k in range(len(w) - 2):
        esperado = p[k + 1] * p[k + 2]
        desvios.append(abs(w[k] / w[k + 2] - esperado))
    return float(max(desvios, default=0.0))


def status_consistencia(chi: float, limiar: float = 0.025) -> str:
    """Classificação operacional da DFC.

    chi ~= 0 representa consistência plena; valores até 0.025 são tratados
    como próximos da consistência plena para fins de diagnóstico da interface.
    """
    if chi < 0:
        raise ValueError("chi deve ser >= 0")
    if chi <= 1e-8:
        return "Plena"
    if chi <= limiar:
        return "Aceitável"
    return "Revisar"
