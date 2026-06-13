from pathlib import Path
import pandas as pd
import streamlit as st
from data_loader import load_workbook_data

st.set_page_config(page_title="Elencos Fantasy NBA", layout="wide")
st.title("Transactions")
st.caption("Primeira tela de transações e itens relacionados.")

DEFAULT_FILE = Path("roster.xlsx")

@st.cache_data
def cached_load(file_path: str):
    return load_workbook_data(file_path)

if not DEFAULT_FILE.exists():
    st.error("Arquivo roster.xlsx não encontrado na pasta do projeto.")
    st.stop()

data = cached_load(str(DEFAULT_FILE))

transactions = data.get("transactions", pd.DataFrame())
transaction_times = data.get("transaction_times", pd.DataFrame())
teams = data.get("teams", pd.DataFrame())

team_map = teams[["team_id", "team_name"]].drop_duplicates() if not teams.empty else pd.DataFrame(columns=["team_id", "team_name"])
team_lookup = dict(zip(team_map["team_id"], team_map["team_name"])) if not team_map.empty else {}

if transactions.empty:
    st.info("Não há transações cadastradas ainda.")
else:
    df = transactions.copy()
    df["from_team"] = df["from_team_id"].map(team_lookup)
    df["to_team"] = df["to_team_id"].map(team_lookup)
    cols = [c for c in ["transaction_id", "transaction_type", "transaction_date", "season", "from_team", "to_team", "initiated_by", "status", "notes"] if c in df.columns]
    st.subheader("Transações")
    st.dataframe(df[cols], use_container_width=True, hide_index=True)

    st.subheader("Itens por transação")
    if transaction_times.empty:
        st.info("Nenhum item vinculado às transações ainda.")
    else:
        tdf = transaction_times.copy()
        tdf["from_team"] = tdf["from_team_id"].map(team_lookup)
        tdf["to_team"] = tdf["to_team_id"].map(team_lookup)
        cols2 = [c for c in ["transaction_id", "item_id", "item_type", "asset_id", "from_team", "to_team", "from_roster_type", "to_roster_type", "effective_season", "item_notes"] if c in tdf.columns]
        st.dataframe(tdf[cols2], use_container_width=True, hide_index=True)
