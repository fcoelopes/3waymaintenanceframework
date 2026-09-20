"""Cálculo de confiabilidade para RBDs série/paralelo.

A primeira versão é deliberadamente limitada a estruturas decomponíveis em série
ou paralelo, exatamente a classe estrutural usada pelo modelo de manutenção
seletiva de Lust, Roux & Riane (2009).
"""
from __future__ import annotations

from app.models import NoRBD


def validar_referencias(topologia: NoRBD, componentes_ids: set[str]) -> None:
    """Valida se todos os blocos do RBD referenciam componentes existentes."""
    refs: list[str] = []

    def walk(no: NoRBD) -> None:
        if no.tipo == "component":
            assert no.componente_id is not None
            refs.append(no.componente_id)
            return
        for filho in no.filhos:
            walk(filho)

    walk(topologia)

    faltantes = sorted(set(refs) - componentes_ids)
    if faltantes:
        raise ValueError(f"RBD referencia componentes inexistentes: {faltantes}")

    duplicados = sorted({ref for ref in refs if refs.count(ref) > 1})
    if duplicados:
        raise ValueError(
            "Cada componente deve aparecer uma única vez no RBD desta versão: "
            f"{duplicados}"
        )


def confiabilidade_rbd(topologia: NoRBD, confiabilidades: dict[str, float]) -> float:
    """Calcula R_sys recursivamente para nós component, series e parallel."""
    if topologia.tipo == "component":
        cid = topologia.componente_id
        assert cid is not None
        if cid not in confiabilidades:
            raise KeyError(f"Confiabilidade não fornecida para {cid}")
        r = float(confiabilidades[cid])
        if not 0.0 <= r <= 1.0:
            raise ValueError(f"Confiabilidade de {cid} fora de [0,1]: {r}")
        return r

    valores = [confiabilidade_rbd(filho, confiabilidades) for filho in topologia.filhos]

    if topologia.tipo == "series":
        r = 1.0
        for valor in valores:
            r *= valor
        return r

    if topologia.tipo == "parallel":
        falha_conjunta = 1.0
        for valor in valores:
            falha_conjunta *= 1.0 - valor
        return 1.0 - falha_conjunta

    raise ValueError(f"Tipo de nó RBD não suportado: {topologia.tipo}")
