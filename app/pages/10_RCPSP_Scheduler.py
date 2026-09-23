"""Camada HOW: programação RCPSP da parada com OR-Tools CP-SAT."""
import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app.core.rcpsp import RCPSPScheduler
from app.core.rcpsp_adapter import rascunho_rcpsp_do_selective
from app.rcpsp_models import InstanciaRCPSP

st.title("10 · RCPSP — Como executar?")
st.caption(
    "Programa o escopo selecionado respeitando precedências, capacidade de recursos, "
    "recursos exclusivos, indisponibilidades e a janela T0."
)

EXAMPLE_PATH = Path("data/exemplo_rcpsp_turnaround.json")

if "rcpsp_json" not in st.session_state:
    st.session_state.rcpsp_json = EXAMPLE_PATH.read_text(encoding="utf-8")

c1, c2 = st.columns(2)
with c1:
    if st.button("Carregar exemplo de turnaround"):
        st.session_state.rcpsp_json = EXAMPLE_PATH.read_text(encoding="utf-8")
        st.rerun()

with c2:
    estrategia = st.session_state.get("estrategia_final")
    if estrategia and st.button("Gerar rascunho do Selective"):
        try:
            resultado = estrategia["resultado"]
            agenda = st.session_state.get("agenda_planta")
            parada_id = estrategia["parada_id"]
            parada = (
                next(p for p in agenda.paradas if p.id == parada_id)
                if agenda is not None
                else None
            )
            janela = float(parada.duracao if parada is not None else resultado.janela_manutencao)
            instancia = rascunho_rcpsp_do_selective(
                resultado,
                janela_h=janela,
                capacidade_equipe_geral=1,
            )
            st.session_state.rcpsp_json = instancia.model_dump_json(indent=2)
            st.warning(
                "Rascunho gerado: uma atividade por ação Selective. Decomponha cada "
                "work package em WBS real e informe recursos/precedências antes de usar "
                "o cronograma operacionalmente."
            )
        except Exception as exc:
            st.error(f"Não foi possível gerar o rascunho: {exc}")

st.subheader("A · Instância RCPSP")
st.info(
    "O JSON usa horas decimais. O solver discretiza para ticks inteiros de forma "
    "conservadora conforme time_unit_minutes."
)
raw = st.text_area(
    "Recursos, bloqueios, atividades, precedências e janelas",
    value=st.session_state.rcpsp_json,
    height=520,
)
st.session_state.rcpsp_json = raw

instancia = None
try:
    instancia = InstanciaRCPSP.model_validate(json.loads(raw))
    st.success(
        f"Instância válida: {len(instancia.atividades)} atividades · "
        f"{len(instancia.recursos)} recursos · janela={instancia.janela_h:.2f} h."
    )
except Exception as exc:
    st.error(f"Instância inválida: {exc}")

if instancia is not None and st.button("▶ Programar parada", type="primary"):
    try:
        st.session_state.resultado_rcpsp = RCPSPScheduler(instancia).solve()
    except Exception as exc:
        st.error(f"Falha ao montar/solver o RCPSP: {exc}")

result = st.session_state.get("resultado_rcpsp")
if result:
    st.subheader("B · Resultado")
    c1, c2, c3 = st.columns(3)
    c1.metric("Status", result.status.upper())
    c2.metric(
        "Makespan",
        "—" if result.makespan_h is None else f"{result.makespan_h:.2f} h",
    )
    c3.metric("Janela T0", f"{result.janela_h:.2f} h")

    if result.diagnosticos:
        for diagnostic in result.diagnosticos:
            st.warning(diagnostic)

    if result.atividades:
        df = pd.DataFrame([a.model_dump() for a in result.atividades])
        st.dataframe(
            df[
                [
                    "id",
                    "work_package_id",
                    "nome",
                    "inicio_h",
                    "fim_h",
                    "duracao_h",
                    "ativo_id",
                    "acao_origem",
                ]
            ],
            hide_index=True,
            use_container_width=True,
        )

        st.subheader("C · Gantt")
        fig = go.Figure()
        for a in result.atividades:
            fig.add_trace(
                go.Bar(
                    y=[f"{a.work_package_id} · {a.id}"],
                    x=[a.duracao_h],
                    base=[a.inicio_h],
                    orientation="h",
                    name=a.id,
                    hovertemplate=(
                        f"{a.nome}<br>início={a.inicio_h:.2f} h"
                        f"<br>fim={a.fim_h:.2f} h<extra></extra>"
                    ),
                    showlegend=False,
                )
            )
        fig.update_layout(
            xaxis_title="Horas desde o início da parada",
            yaxis_title="Atividade",
            height=max(360, 38 * len(result.atividades)),
            barmode="overlay",
        )
        st.plotly_chart(fig, use_container_width=True)

    if result.utilizacao_recursos:
        st.subheader("D · Recursos")
        rdf = pd.DataFrame([r.model_dump() for r in result.utilizacao_recursos])
        rdf["utilizacao_media_%"] = 100.0 * rdf["utilizacao_media"]
        st.dataframe(
            rdf[
                [
                    "recurso_id",
                    "nome",
                    "capacidade",
                    "carga_h_equivalente",
                    "capacidade_h_total",
                    "utilizacao_media_%",
                    "pico_utilizado",
                ]
            ],
            hide_index=True,
            use_container_width=True,
        )

    st.caption(f"Tempo de solução CP-SAT: {result.wall_time_s:.3f} s")
