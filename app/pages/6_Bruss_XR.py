import pandas as pd
import streamlit as st

from app.core.bruss_xr import aplicar_bruss_carteira

st.title("6 · Bruss X·RUL — Quando intervir?")
st.caption(
    "Seleciona e ordena oportunidades usando mantenabilidade × sobrevivência "
    "residual condicional à idade atual do ativo."
)

agenda = st.session_state.get("agenda_planta")
params = st.session_state.get("parametros_bruss")
config = st.session_state.get("config_bruss")
if agenda is None or params is None or config is None:
    st.warning("Configure a página 5 primeiro.")
    st.stop()

if st.button("▶ Calcular oportunidades", type="primary"):
    try:
        st.session_state.resultado_bruss = aplicar_bruss_carteira(
            agenda,
            params,
            config.threshold_global,
            config.tipo_mantenabilidade,
            st.session_state.get("nomes_ativos", {}),
        )
    except Exception as exc:
        st.error(str(exc))

resultados = st.session_state.get("resultado_bruss")
if resultados:
    aid = st.selectbox("Ativo", list(resultados), format_func=lambda x: resultados[x].ativo_nome)
    r = resultados[aid]
    st.metric("Parada recomendada", "—" if r.parada_otima_id is None else str(r.parada_otima_id))
    df = pd.DataFrame([a.model_dump() for a in r.avaliacoes])
    st.dataframe(df, hide_index=True, use_container_width=True)

    rows = []
    for aid, rr in resultados.items():
        ev = next((a for a in rr.avaliacoes if a.parada_id == rr.parada_otima_id), None)
        rows.append({
            "ativo_id": aid,
            "ativo": rr.ativo_nome,
            "parada": rr.parada_otima_id,
            "inicio": None if ev is None else ev.inicio,
            "duracao": None if ev is None else ev.duracao,
            "p": None if ev is None else ev.p,
            "tipo": None if ev is None else ev.tipo_decisao,
        })
    st.subheader("Visão consolidada")
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
