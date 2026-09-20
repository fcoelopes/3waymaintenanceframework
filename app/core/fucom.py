"""FUCOM simplificado em forma fechada para razões entre critérios consecutivos."""
import numpy as np


def calcular_pesos(phis: list[float]) -> np.ndarray:
    if len(phis) < 2:
        raise ValueError("Informe pelo menos dois critérios")
    arr = np.asarray(phis, dtype=float)
    if not np.isclose(arr[0], 1.0):
        raise ValueError("Por convenção, phi_1 deve ser 1")
    if np.any(arr < 1.0):
        raise ValueError("Todos os valores phi devem ser >= 1")

    rel = np.ones(len(arr), dtype=float)
    for k in range(1, len(arr)):
        rel[k] = rel[k - 1] / arr[k]
    return rel / rel.sum()


def consistencia_chi(pesos: np.ndarray, phis: list[float]) -> float:
    w = np.asarray(pesos, dtype=float)
    p = np.asarray(phis, dtype=float)
    if len(w) != len(p):
        raise ValueError("pesos e phis devem ter o mesmo tamanho")
    if len(w) < 3:
        return 0.0
    desvios = []
    for k in range(len(w) - 2):
        esperado = p[k + 1] * p[k + 2]
        observado = w[k] / w[k + 2]
        desvios.append(abs(observado - esperado))
    return float(max(desvios, default=0.0))


def status_consistencia(chi: float, limiar: float = 0.1) -> str:
    if chi < limiar / 10:
        return "Excelente"
    if chi < limiar:
        return "Aceitável"
    return "Revisar"
