import pandas as pd
import streamlit as st

from app.core.framework import agrupar_candidatos_por_parada, construir_decisoes_integradas

st.title("8 · Decisão Integrada — Quais + Quando")
st.caption("Contrato entre a prioridade PROMETHEE e as oportunidades Bruss. A próxima página fecha 'o quê'.")

prom = st.session_state.get("resultado_promethee")
bruss = st.session_state.get("resultado_bruss")
if prom is None or not bruss:
    st.warning("Calcule PROMETHEE e Bruss antes de consolidar.")
    st.stop()

linhas = construir_decisoes_integradas(prom, bruss, st.session_state.get("nomes_ativos", {}))
st.session_state.decisoes_integradas = linhas
grupos = agrupar_candidatos_por_parada(linhas)
st.session_state.candidatos_por_parada = grupos

st.subheader("Ativo × oportunidade")
df = pd.DataFrame([x.model_dump() for x in linhas])
st.dataframe(df, hide_index=True, use_container_width=True)

st.subheader("Candidatos agrupados por parada")
if grupos:
    for pid, ids in sorted(grupos.items()):
        st.write(f"**Parada {pid}:** {', '.join(ids)}")
else:
    st.info("Nenhum ativo foi alocado a uma parada.")

st.success("O Selective Maintenance usará cada duração de parada como T0 e decidirá as ações.")
