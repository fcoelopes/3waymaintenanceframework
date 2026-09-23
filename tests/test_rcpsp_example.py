import json
from pathlib import Path

from app.core.rcpsp import RCPSPScheduler
from app.rcpsp_models import InstanciaRCPSP


def test_exemplo_turnaround_rcpsp_e_viavel():
    dados = json.loads(
        Path("data/exemplo_rcpsp_turnaround.json").read_text(encoding="utf-8")
    )
    instancia = InstanciaRCPSP.model_validate(dados)
    resultado = RCPSPScheduler(instancia).solve()

    assert resultado.status in {"optimal", "feasible"}
    assert resultado.makespan_h is not None
    assert resultado.makespan_h <= instancia.janela_h
    assert len(resultado.atividades) == len(instancia.atividades)
