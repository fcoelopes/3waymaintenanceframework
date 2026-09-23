import pandas as pd
import streamlit as st

from app.components.data_io import carregar_caso_thomas2008
from app.models import AgendaParadasPlanta, ConfigBruss, ParametrosAtivoBruss, Parada

st.title("5 · Paradas e Parâmetros — Quando?")
st.caption(
    "Agenda da planta + idade atual + sobrevivência condicional da RUL Weibull "
    "+ mantenabilidade MTTR/σT."
)

prom = st.session_state.get("resultado_promethee")
if prom is None:
    st.warning("Calcule o PROMETHEE II primeiro.")
    st.stop()

ordered = sorted(zip(prom.ids, prom.ranks), key=lambda x: x[1])
max_n = len(ordered)
top_n = st.slider("Ativos levados à camada tática", 1, max_n, min(5, max_n))
top_ids = [aid for aid, _ in ordered[:top_n]]
st.session_state.top_ids = top_ids
nomes = st.session_state.get("nomes_ativos", {})

st.subheader("A · Agenda de paradas")
if "agenda_df" not in st.session_state:
    caso = carregar_caso_thomas2008()
    st.session_state.agenda_df = pd.DataFrame(caso["paradas"])
    st.session_state.horizonte_T = float(caso["horizonte_T"])

c1, c2 = st.columns([1, 3])
with c1:
    horizonte = st.number_input("Horizonte T (h)", min_value=1.0, value=float(st.session_state.horizonte_T))
with c2:
    if st.button("Recarregar agenda Thomas 2008"):
        caso = carregar_caso_thomas2008()
        st.session_state.agenda_df = pd.DataFrame(caso["paradas"])
        st.rerun()
agenda_df = st.data_editor(st.session_state.agenda_df, num_rows="dynamic", use_container_width=True)
st.session_state.agenda_df = agenda_df

st.subheader("B · Parâmetros por ativo")
if "parametros_bruss_df" not in st.session_state:
    rows = []
    for aid in top_ids:
        rows.append({
            "ativo_id": aid, "nome": nomes.get(aid, aid), "idade_atual": 0.0,
            "weibull_beta": 1.5,
            "weibull_eta": 600.0, "weibull_gamma": 0.0, "mttr": 5.0,
            "sigma_t": 2.0, "threshold_override": None,
        })
    st.session_state.parametros_bruss_df = pd.DataFrame(rows)
else:
    old = st.session_state.parametros_bruss_df
    byid = {str(r["ativo_id"]): r for r in old.to_dict("records")}
    rows = []
    for aid in top_ids:
        row = dict(byid.get(aid, {
            "ativo_id": aid, "nome": nomes.get(aid, aid), "idade_atual": 0.0,
            "weibull_beta": 1.5, "weibull_eta": 600.0, "weibull_gamma": 0.0,
            "mttr": 5.0, "sigma_t": 2.0, "threshold_override": None,
        }))
        row.setdefault("idade_atual", 0.0)
        rows.append(row)
    st.session_state.parametros_bruss_df = pd.DataFrame(rows)
params_df = st.data_editor(st.session_state.parametros_bruss_df, use_container_width=True)
st.session_state.parametros_bruss_df = params_df

st.subheader("C · Configuração")
c1, c2 = st.columns(2)
with c1:
    tipo = st.selectbox("Mantenabilidade", ["lognormal", "exponencial"], format_func=lambda x: "Lognormal — MTTR + σT" if x == "lognormal" else "Exponencial — compatibilidade Thomas")
with c2:
    threshold = st.slider("Threshold global", 0.0, 1.0, 0.35, 0.01)

try:
    agenda = AgendaParadasPlanta(
        horizonte_T=float(horizonte),
        paradas=[Parada(**r) for r in agenda_df.to_dict("records")],
    )
    params = {}
    for row in params_df.to_dict("records"):
        row = dict(row)
        row.pop("nome", None)
        # Pandas converte vazio para NaN; Pydantic espera None.
        if pd.isna(row.get("threshold_override")):
            row["threshold_override"] = None
        params[str(row["ativo_id"])] = ParametrosAtivoBruss(**row)
    st.session_state.agenda_planta = agenda
    st.session_state.parametros_bruss = params
    st.session_state.config_bruss = ConfigBruss(threshold_global=threshold, tipo_mantenabilidade=tipo)
    st.success("Configuração tática válida.")
except Exception as exc:
    st.error(str(exc))
