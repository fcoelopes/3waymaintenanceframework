import numpy as np
import pandas as pd
import streamlit as st

from app.core.monte_carlo import classificar_estabilidade, simular

st.title("4 · Robustez Monte Carlo — opcional")
st.caption("Perturba pesos e desempenhos para testar a estabilidade do ranking PROMETHEE.")

prom = st.session_state.get("resultado_promethee")
ativos = st.session_state.get("ativos_df")
criterios = st.session_state.get("criterios_config")
pesos = st.session_state.get("pesos_fucom")
if prom is None or ativos is None or not criterios or pesos is None:
    st.warning("Calcule o PROMETHEE II primeiro.")
    st.stop()

c1, c2, c3, c4 = st.columns(4)
with c1:
    n_iter = st.number_input("Iterações", 100, 10000, 1000, 100)
with c2:
    dp = st.slider("Perturbação pesos", 0.0, 0.5, 0.20, 0.01)
with c3:
    dx = st.slider("Perturbação desempenhos", 0.0, 0.5, 0.15, 0.01)
with c4:
    n_top = st.number_input("Top-N", 1, len(prom.ids), min(5, len(prom.ids)), 1)

if st.button("▶ Simular robustez", type="primary"):
    names = [c["nome"] for c in criterios]
    res = simular(
        ativos[names].astype(float).to_numpy(),
        np.asarray(pesos, dtype=float),
        np.asarray([c["q"] for c in criterios], dtype=float),
        np.asarray([c["p"] for c in criterios], dtype=float),
        np.asarray([1 if c["direcao"] == "max" else -1 for c in criterios]),
        n_iter=int(n_iter), delta_pesos=float(dp), delta_desempenho=float(dx),
        n_top=int(n_top), seed=42,
    )
    st.session_state.resultado_mc = res

res = st.session_state.get("resultado_mc")
if res:
    nomes = st.session_state.get("nomes_ativos", {})
    rows = []
    for j, aid in enumerate(prom.ids):
        rows.append({
            "id": aid, "ativo": nomes.get(aid, aid),
            "rank nominal": int(res["rank_nominal"][j]),
            "rank modal": int(res["rank_modal"][j]),
            "rank médio": float(res["rank_medio"][j]),
            "P5": float(res["rank_p5"][j]), "P95": float(res["rank_p95"][j]),
            "P(top-N) %": float(res["prob_top_n"][j]),
            "estabilidade": classificar_estabilidade(
                res["prob_top_n"][j], res["rank_modal"][j], res["rank_nominal"][j]
            ),
        })
    st.dataframe(pd.DataFrame(rows).sort_values("rank nominal"), hide_index=True, use_container_width=True)
