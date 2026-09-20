"""PROMETHEE II com função de preferência tipo V."""
import numpy as np


def preferencia_v(diff: np.ndarray, q: float, p: float) -> np.ndarray:
    if q < 0 or p <= q:
        raise ValueError("É necessário 0 <= q < p")
    d = np.asarray(diff, dtype=float)
    return np.where(d <= q, 0.0, np.where(d >= p, 1.0, (d - q) / (p - q)))


def calcular_ranking(
    matriz_desempenho: np.ndarray,
    pesos: np.ndarray,
    qs: np.ndarray,
    ps: np.ndarray,
    direcoes: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    x = np.asarray(matriz_desempenho, dtype=float)
    w = np.asarray(pesos, dtype=float)
    q = np.asarray(qs, dtype=float)
    p = np.asarray(ps, dtype=float)
    d = np.asarray(direcoes, dtype=float)

    if x.ndim != 2:
        raise ValueError("matriz_desempenho deve ser 2D")
    n_alt, n_crit = x.shape
    if n_alt < 2:
        raise ValueError("PROMETHEE requer pelo menos duas alternativas")
    if any(len(v) != n_crit for v in (w, q, p, d)):
        raise ValueError("Dimensões de pesos/limiares/direções incompatíveis")
    if np.any(q < 0) or np.any(p <= q):
        raise ValueError("Cada critério deve respeitar 0 <= q < p")
    if np.any(~np.isin(d, [-1, 1])):
        raise ValueError("direcoes deve conter apenas +1 (max) ou -1 (min)")
    if np.any(w < 0) or w.sum() <= 0:
        raise ValueError("pesos inválidos")
    w = w / w.sum()

    agg = np.zeros((n_alt, n_alt), dtype=float)
    for j in range(n_crit):
        diff = d[j] * (x[:, j][:, None] - x[:, j][None, :])
        agg += w[j] * preferencia_v(diff, float(q[j]), float(p[j]))

    np.fill_diagonal(agg, 0.0)
    denom = n_alt - 1
    phi_plus = agg.sum(axis=1) / denom
    phi_minus = agg.sum(axis=0) / denom
    phi_net = phi_plus - phi_minus

    order = np.argsort(-phi_net, kind="stable")
    ranks = np.empty(n_alt, dtype=int)
    rank = 1
    for pos, idx in enumerate(order):
        if pos > 0 and not np.isclose(phi_net[idx], phi_net[order[pos - 1]], atol=1e-12):
            rank = pos + 1
        ranks[idx] = rank
    return phi_plus, phi_minus, phi_net, ranks


def ordenar_por_rank(ids: list[str], phi_net: np.ndarray, ranks: np.ndarray) -> list[tuple[int, str, float]]:
    if not (len(ids) == len(phi_net) == len(ranks)):
        raise ValueError("Dimensões incompatíveis")
    return sorted(
        [(int(r), str(i), float(phi)) for i, phi, r in zip(ids, phi_net, ranks)],
        key=lambda item: (item[0], -item[2], item[1]),
    )
