import pandas as pd
import streamlit as st

st.title("2 · Ativos")
st.caption("Matriz de desempenho usada pelo PROMETHEE II.")

criterios = st.session_state.get("criterios_config")
if not criterios:
    st.warning("Configure primeiro os critérios na página 1.")
    st.stop()

names = [c["nome"] for c in criterios]
if "ativos_df" not in st.session_state:
    rows = []
    for i in range(1, 7):
        row = {"id": f"A{i}", "nome": f"Ativo {i}"}
        for j, nome in enumerate(names):
            row[nome] = float(5 + ((i * (j + 2)) % 6))
        rows.append(row)
    st.session_state.ativos_df = pd.DataFrame(rows)

# Garante colunas quando critérios forem alterados.
df = st.session_state.ativos_df.copy()
for nome in names:
    if nome not in df.columns:
        df[nome] = 5.0
cols = ["id", "nome"] + names
edited = st.data_editor(df[cols], num_rows="dynamic", use_container_width=True)
st.session_state.ativos_df = edited

if edited["id"].duplicated().any():
    st.error("IDs dos ativos devem ser únicos.")
elif len(edited) < 2:
    st.error("Informe pelo menos dois ativos.")
else:
    st.subheader("Discriminação por critério")
    stats = edited[names].astype(float).agg(["min", "max", "std"]).T
    stats["range"] = stats["max"] - stats["min"]
    st.dataframe(stats, use_container_width=True)
    st.success("Carteira pronta para o PROMETHEE II.")
