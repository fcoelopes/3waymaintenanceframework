import math

import pytest

from app.core.rbd import confiabilidade_rbd, validar_referencias
from app.models import NoRBD


def C(cid: str) -> NoRBD:
    return NoRBD(tipo="component", componente_id=cid)


def test_rbd_series():
    topo = NoRBD(tipo="series", filhos=[C("A"), C("B")])
    r = confiabilidade_rbd(topo, {"A": 0.9, "B": 0.8})
    assert math.isclose(r, 0.72)


def test_rbd_parallel():
    topo = NoRBD(tipo="parallel", filhos=[C("A"), C("B")])
    r = confiabilidade_rbd(topo, {"A": 0.9, "B": 0.8})
    assert math.isclose(r, 0.98)


def test_rbd_nested():
    topo = NoRBD(
        tipo="series",
        filhos=[C("A"), NoRBD(tipo="parallel", filhos=[C("B"), C("C")])],
    )
    r = confiabilidade_rbd(topo, {"A": 0.9, "B": 0.8, "C": 0.7})
    assert math.isclose(r, 0.9 * (1 - 0.2 * 0.3))


def test_validacao_pode_exigir_rbd_completo():
    topo = C("A")
    validar_referencias(topo, {"A", "B"})

    with pytest.raises(ValueError, match="RBD incompleto"):
        validar_referencias(topo, {"A", "B"}, exigir_todos=True)
