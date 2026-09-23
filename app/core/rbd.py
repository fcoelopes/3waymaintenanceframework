"""Cálculo de confiabilidade para RBDs série/paralelo.

A primeira versão é deliberadamente limitada a estruturas decomponíveis em série
ou paralelo, exatamente a classe estrutural usada pelo modelo de manutenção
seletiva de Lust, Roux & Riane (2009).
"""
from __future__ import annotations

from app.models import NoRBD


def componentes_rbd(topologia: NoRBD) -> list[str]:
    """Lista os componentes referenciados pelo RBD na ordem de travessia."""
    refs: list[str] = []

    def walk(no: NoRBD) -> None:
        if no.tipo == "component":
            assert no.componente_id is not None
            refs.append(no.componente_id)
            return
        for filho in no.filhos:
            walk(filho)

    walk(topologia)
    return refs


def validar_referencias(
    topologia: NoRBD,
    componentes_ids: set[str],
    *,
    exigir_todos: bool = False,
) -> None:
    """Valida referências e, opcionalmente, exige o RBD completo do sistema."""
    refs = componentes_rbd(topologia)
    refs_set = set(refs)

    faltantes = sorted(refs_set - componentes_ids)
    if faltantes:
        raise ValueError(f"RBD referencia componentes inexistentes: {faltantes}")

    duplicados = sorted({ref for ref in refs if refs.count(ref) > 1})
    if duplicados:
        raise ValueError(
            "Cada componente deve aparecer uma única vez no RBD desta versão: "
            f"{duplicados}"
        )

    if exigir_todos:
        ausentes_do_rbd = sorted(componentes_ids - refs_set)
        if ausentes_do_rbd:
            raise ValueError(
                "RBD incompleto: componentes do sistema ausentes da topologia: "
                f"{ausentes_do_rbd}"
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
