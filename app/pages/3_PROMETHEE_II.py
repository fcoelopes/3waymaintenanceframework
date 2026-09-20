import numpy as np
import pandas as pd
import streamlit as st

from app.core.promethee import calcular_ranking
from app.models import ResultadoPROMETHEE

st.title("3 · PROMETHEE II — Quais ativos?")
st.caption("Ranking estratégico. A ordem representa prioridade, não uma ordem obrigatória de execução.")

criterios = st.session_state.get("criterios_config")
pesos = st.session_state.get("pesos_fucom")
ativos = st.session_state.get("ativos_df")
if not criterios or pesos is None or ativos is None:
    st.warning("Conclua as páginas 1 e 2.")
    st.stop()

names = [c["nome"] for c in criterios]
try:
    matriz = ativos[names].astype(float).to_numpy()
    qs = np.asarray([c["q"] for c in criterios], dtype=float)
    ps = np.asarray([c["p"] for c in criterios], dtype=float)
    dirs = np.asarray([1 if c["direcao"] == "max" else -1 for c in criterios])
    plus, minus, net, ranks = calcular_ranking(matriz, np.asarray(pesos), qs, ps, dirs)
    result = ResultadoPROMETHEE(
        ids=ativos["id"].astype(str).tolist(),
        phi_plus=plus.tolist(),
        phi_minus=minus.tolist(),
        phi_net=net.tolist(),
        ranks=ranks.tolist(),
    )
    st.session_state.resultado_promethee = result
    st.session_state.nomes_ativos = dict(zip(ativos["id"].astype(str), ativos["nome"].astype(str)))
    out = pd.DataFrame({
        "rank": ranks,
        "id": result.ids,
        "ativo": ativos["nome"].astype(str),
        "phi+": plus,
        "phi-": minus,
        "phi": net,
    }).sort_values(["rank", "phi"], ascending=[True, False])
    st.dataframe(out, hide_index=True, use_container_width=True)
    st.bar_chart(out.set_index("ativo")["phi"])
    st.success("Ranking calculado. Agora configure as oportunidades temporais.")
except Exception as exc:
    st.error(f"Não foi possível calcular o ranking: {exc}")
