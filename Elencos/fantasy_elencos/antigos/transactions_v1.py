from pathlib import Path
import pandas as pd
import streamlit as st
from data_loader import load_workbook_data

st.set_page_config(page_title="Elencos Fantasy NBA", layout="wide")
st.title("Transactions")
st.caption("Transações com impacto no roster e no development.")

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
players = data.get("players", pd.DataFrame())
roster = data.get("roster", pd.DataFrame())
development = data.get("development", pd.DataFrame())
picks = data.get("picks", pd.DataFrame())
fines = data.get("fines", pd.DataFrame())

team_map = teams[["team_id", "team_name"]].drop_duplicates() if not teams.empty else pd.DataFrame(columns=["team_id", "team_name"])
team_lookup = dict(zip(team_map["team_id"], team_map["team_name"])) if not team_map.empty else {}
player_lookup = dict(zip(players["player_id"], players["player_name"])) if not players.empty else {}

st.subheader("Resumo do impacto")
cols = st.columns(4)
cols[0].metric("Transações", 0 if transactions.empty else len(transactions))
cols[1].metric("Itens movidos", 0 if transaction_times.empty else len(transaction_times))
cols[2].metric("Picks ativos", 0 if picks.empty else len(picks))
cols[3].metric("Débitos/fines", 0 if fines.empty else len(fines))

st.divider()

if transactions.empty:
    st.info("Não há transações cadastradas ainda.")
else:
    df = transactions.copy()
    df["from_team"] = df["from_team_id"].map(team_lookup)
    df["to_team"] = df["to_team_id"].map(team_lookup)
    cols1 = [c for c in ["transaction_id", "transaction_type", "transaction_date", "season", "from_team", "to_team", "initiated_by", "status", "notes"] if c in df.columns]
    st.subheader("Transações")
    st.dataframe(df[cols1], use_container_width=True, hide_index=True)

st.subheader("Itens por transação")
if transaction_times.empty:
    st.info("Nenhum item vinculado às transações ainda.")
else:
    tdf = transaction_times.copy()
    tdf["from_team"] = tdf["from_team_id"].map(team_lookup)
    tdf["to_team"] = tdf["to_team_id"].map(team_lookup)
    tdf["asset_name"] = tdf["asset_id"].map(player_lookup).fillna(tdf["asset_id"].astype(str))
    cols2 = [c for c in ["transaction_id", "item_id", "item_type", "asset_name", "from_team", "to_team", "from_roster_type", "to_roster_type", "effective_season", "item_notes"] if c in tdf.columns]
    st.dataframe(tdf[cols2], use_container_width=True, hide_index=True)

st.subheader("Impacto no roster")
if roster.empty:
    st.info("Sem dados de roster.")
else:
    rdf = roster.copy()
    rdf["team_name"] = rdf["team_id"].map(team_lookup)
    rdf["player_name"] = rdf["player_id"].map(player_lookup).fillna(rdf.get("Jogador", pd.Series(index=rdf.index, dtype=str)))
    cols3 = [c for c in ["team_name", "player_name", "pos_order", "salarie_26_27", "option_26_27", "salarie_27_28", "option_27_28", "salarie_28_29", "option_28_29", "salarie_29_30", "option_29_30"] if c in rdf.columns]
    st.dataframe(rdf[cols3], use_container_width=True, hide_index=True)

st.subheader("Impacto no development")
if development.empty:
    st.info("Sem dados de development.")
else:
    ddf = development.copy()
    ddf["team_name"] = ddf["team_id"].map(team_lookup)
    ddf["player_name"] = ddf["player_id"].map(player_lookup)
    cols4 = [c for c in ["team_name", "player_name", "order", "salarie_26_27", "option_26_27", "salarie_27_28", "option_27_28", "salarie_28_29", "option_28_29", "salarie_29_30", "option_29_30"] if c in ddf.columns]
    st.dataframe(ddf[cols4], use_container_width=True, hide_index=True)
