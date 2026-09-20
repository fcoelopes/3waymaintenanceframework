import pandas as pd
import streamlit as st

from app.core.fucom import calcular_pesos, consistencia_chi, status_consistencia

st.title("1 · Critérios e Pesos — FUCOM")
st.caption("Camada 1/3: preferências do decisor para responder quais ativos merecem prioridade.")

DEFAULT = pd.DataFrame([
    {"posicao": 1, "nome": "Criticidade", "direcao": "max", "q": 0.5, "p": 2.0, "phi": 1.0},
    {"posicao": 2, "nome": "Condição", "direcao": "max", "q": 0.5, "p": 2.0, "phi": 1.2},
    {"posicao": 3, "nome": "Impacto produção", "direcao": "max", "q": 0.5, "p": 2.0, "phi": 1.2},
    {"posicao": 4, "nome": "Custo", "direcao": "min", "q": 1.0, "p": 4.0, "phi": 1.15},
])

if "criterios_fucom_df" not in st.session_state:
    st.session_state.criterios_fucom_df = DEFAULT

edited = st.data_editor(
    st.session_state.criterios_fucom_df,
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "direcao": st.column_config.SelectboxColumn(options=["max", "min"]),
        "posicao": st.column_config.NumberColumn(min_value=1, step=1),
        "phi": st.column_config.NumberColumn(min_value=1.0, step=0.05),
    },
)
st.session_state.criterios_fucom_df = edited

try:
    df = edited.sort_values("posicao").reset_index(drop=True)
    if len(df) < 2:
        raise ValueError("Informe pelo menos dois critérios")
    if df["nome"].duplicated().any():
        raise ValueError("Nomes de critérios devem ser únicos")
    if (df["p"] <= df["q"]).any():
        raise ValueError("Cada critério deve respeitar p > q")
    phis = df["phi"].astype(float).tolist()
    phis[0] = 1.0
    pesos = calcular_pesos(phis)
    chi = consistencia_chi(pesos, phis)
    df["peso"] = pesos
    st.dataframe(df[["posicao", "nome", "direcao", "q", "p", "phi", "peso"]], hide_index=True, use_container_width=True)
    c1, c2 = st.columns(2)
    c1.metric("χ de consistência", f"{chi:.4f}")
    c2.metric("Status", status_consistencia(chi))
    st.session_state.criterios_config = df.to_dict("records")
    st.session_state.pesos_fucom = pesos.tolist()
    st.success("Critérios e pesos prontos.")
except Exception as exc:
    st.error(str(exc))
