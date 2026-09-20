import numpy as np
import pandas as pd
import streamlit as st

from app.core.bruss_xr import sensibilidade_threshold

st.title("7 · Sensibilidade do Threshold — opcional")
st.caption("Mostra como a oportunidade recomendada muda quando o threshold do especialista varia.")

agenda = st.session_state.get("agenda_planta")
params = st.session_state.get("parametros_bruss")
config = st.session_state.get("config_bruss")
if agenda is None or params is None or config is None:
    st.warning("Configure a camada Bruss primeiro.")
    st.stop()

c1, c2, c3 = st.columns(3)
with c1:
    tmin = st.number_input("Threshold mínimo", 0.0, 1.0, 0.0, 0.05)
with c2:
    tmax = st.number_input("Threshold máximo", 0.0, 1.0, 1.0, 0.05)
with c3:
    step = st.number_input("Passo", 0.01, 0.5, 0.05, 0.01)

if tmax < tmin:
    st.error("Threshold máximo deve ser >= mínimo.")
    st.stop()
thresholds = np.arange(tmin, tmax + step/2, step)

aid = st.selectbox("Ativo", list(params), format_func=lambda x: st.session_state.get("nomes_ativos", {}).get(x, x))
if st.button("▶ Analisar sensibilidade", type="primary"):
    st.session_state.sens_threshold = sensibilidade_threshold(
        agenda.paradas, params[aid], thresholds, config.tipo_mantenabilidade
    )

res = st.session_state.get("sens_threshold")
if res:
    df = pd.DataFrame({
        "threshold": res["thresholds"],
        "parada recomendada": res["parada_otima"],
        "n ótimas": res["n_otimas"],
        "n eliminadas": res["n_eliminadas"],
    })
    st.dataframe(df, hide_index=True, use_container_width=True)
    st.line_chart(df.set_index("threshold")[["parada recomendada"]])
