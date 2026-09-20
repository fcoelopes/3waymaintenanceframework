"""Import/export de dados do aplicativo."""
from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]


def carregar_carteira_template() -> pd.DataFrame:
    path = ROOT / "data" / "exemplo_carteira.xlsx"
    if path.exists():
        return pd.read_excel(path)
    return pd.DataFrame()


def carregar_caso_thomas2008() -> dict:
    path = ROOT / "data" / "exemplo_thomas2008.json"
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def upload_carteira_widget() -> pd.DataFrame | None:
    arquivo = st.file_uploader("Carteira em Excel", type=["xlsx", "xls"])
    if arquivo is None:
        return None
    return pd.read_excel(arquivo)


def exportar_decisao_integrada(
    df_promethee: pd.DataFrame,
    df_paradas: pd.DataFrame,
    df_decisoes: pd.DataFrame,
    nome_arquivo: str = "decisao_integrada.xlsx",
) -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df_promethee.to_excel(writer, sheet_name="PROMETHEE", index=False)
        df_paradas.to_excel(writer, sheet_name="Paradas", index=False)
        df_decisoes.to_excel(writer, sheet_name="Decisoes", index=False)
    return buffer.getvalue()
