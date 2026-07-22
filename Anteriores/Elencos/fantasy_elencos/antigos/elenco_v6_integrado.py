cfrom pathlib import Path
import pandas as pd
import streamlit as st
from data_loader import load_workbook_data, SEASONS
from transforms import (
    SEASON_LABELS,
    get_team_options,
    get_visible_seasons,
    build_roster_view,
    format_roster_for_display,
    calculate_main_totals,
    calculate_dev_totals,
)

st.set_page_config(page_title="Elencos Fantasy NBA", layout="wide")
st.title("Elencos Fantasy NBA")
st.caption("Versão integrada com transações, roster e development.")

DEFAULT_FILE = Path("roster.xlsx")

@st.cache_data
def cached_load(file_path: str):
    return load_workbook_data(file_path)

def currency(v: float) -> str:
    if pd.isna(v):
        return "-"
    return f"US$ {v:,.2f}"

def display_table(df: pd.DataFrame):
    try:
        st.dataframe(df.style, use_container_width=True, hide_index=True)
    except Exception:
        st.dataframe(df, use_container_width=True, hide_index=True)

def apply_transaction_labels(df, player_lookup, team_lookup):
    if df.empty:
        return df
    out = df.copy()
    if "from_team_id" in out.columns:
        out["from_team"] = out["from_team_id"].map(team_lookup)
    if "to_team_id" in out.columns:
        out["to_team"] = out["to_team_id"].map(team_lookup)
    if "asset_id" in out.columns:
        out["asset_name"] = out["asset_id"].map(player_lookup).fillna(out["asset_id"].astype(str))
    return out

if not DEFAULT_FILE.exists():
    st.error("Arquivo roster.xlsx não encontrado na pasta do projeto.")
    st.stop()

data = cached_load(str(DEFAULT_FILE))
teams = get_team_options(data["teams"])
team_map = data["teams"][ ["team_id", "team_name"] ].drop_duplicates() if not data["teams"].empty else pd.DataFrame(columns=["team_id", "team_name"])
team_lookup = dict(zip(team_map["team_id"], team_map["team_name"])) if not team_map.empty else {}
player_lookup = dict(zip(data["players"]["player_id"], data["players"]["player_name"])) if not data["players"].empty else {}

c1, c2 = st.columns([2, 1])
with c1:
    selected_team_name = st.selectbox("Selecione o time", teams["team_name"].tolist())
with c2:
    selected_start_season = st.selectbox(
        "Temporada inicial",
        SEASONS,
        format_func=lambda x: SEASON_LABELS[x],
    )

selected_team_id = int(teams.loc[teams["team_name"] == selected_team_name, "team_id"].iloc[0])
visible_seasons = get_visible_seasons(selected_start_season)

transactions = data.get("transactions", pd.DataFrame())
transaction_times = data.get("transaction_times", pd.DataFrame())
transactions_view = apply_transaction_labels(transactions, player_lookup, team_lookup)
transaction_times_view = apply_transaction_labels(transaction_times, player_lookup, team_lookup)

st.subheader("Resumo integrado")
cols = st.columns(5)
cols[0].metric("Transações", 0 if transactions.empty else len(transactions))
cols[1].metric("Itens movidos", 0 if transaction_times.empty else len(transaction_times))
cols[2].metric("Picks", 0 if data.get("picks", pd.DataFrame()).empty else len(data.get("picks", pd.DataFrame())))
cols[3].metric("Fines", 0 if data.get("fines", pd.DataFrame()).empty else len(data.get("fines", pd.DataFrame())))
cols[4].metric("Temporadas visíveis", len(visible_seasons))

with st.expander("Diagnóstico de carregamento", expanded=False):
    st.json({
        "players": len(data["players"]),
        "teams": len(data["teams"]),
        "roster": len(data["roster"]),
        "development": len(data["development"]),
        "picks": len(data["picks"]),
        "fines": len(data["fines"]),
        "transactions": len(transactions),
        "transaction_times": len(transaction_times),
        "time_selecionado": selected_team_name,
        "temporadas_visiveis": [SEASON_LABELS[s] for s in visible_seasons],
    })

st.subheader("Transações")
if transactions_view.empty:
    st.info("Não há transações cadastradas ainda.")
else:
    cols_tx = [c for c in ["transaction_id", "transaction_type", "transaction_date", "season", "from_team", "to_team", "initiated_by", "status", "notes"] if c in transactions_view.columns]
    display_table(transactions_view[cols_tx])

st.subheader("Itens por transação")
if transaction_times_view.empty:
    st.info("Nenhum item vinculado às transações ainda.")
else:
    cols_ti = [c for c in ["transaction_id", "item_id", "item_type", "asset_name", "from_team", "to_team", "from_roster_type", "to_roster_type", "effective_season", "item_notes"] if c in transaction_times_view.columns]
    display_table(transaction_times_view[cols_ti])

main_roster_raw = build_roster_view(data["roster"], data["players"], selected_team_id, "MAIN", visible_seasons)
main_roster = format_roster_for_display(main_roster_raw, visible_seasons)
main_totals = calculate_main_totals(data["roster"], data["fines"], selected_team_id, visible_seasons)

dev_roster_raw = build_roster_view(data["development"], data["players"], selected_team_id, "DEV", visible_seasons)
dev_roster = format_roster_for_display(dev_roster_raw, visible_seasons)
dev_totals = calculate_dev_totals(data["development"], visible_seasons)

st.subheader("Elenco principal")
display_main = main_roster.copy()
for season in visible_seasons:
    label = SEASON_LABELS[season]
    if label in display_main.columns:
        display_main[label] = display_main[label].apply(currency)
option_cols = [c for c in display_main.columns if str(c).startswith("TO ")]
for col in option_cols:
    salary_col = col.replace("TO ", "")
    if salary_col in display_main.columns:
        mask = display_main[col].astype(str).str.strip().str.lower().eq("sim")
        display_main.loc[mask, salary_col] = display_main.loc[mask, salary_col].map(lambda x: f"🔴 {x}")
        display_main.loc[mask, col] = display_main.loc[mask, col].map(lambda x: f"🔴 {x}")

display_table(display_main)

st.subheader("Totalizadores do elenco principal")
main_totals_display = main_totals.copy()
for col in ["Salários", "Multas", "Cap restante"]:
    if col in main_totals_display.columns:
        main_totals_display[col] = main_totals_display[col].apply(currency)
st.dataframe(main_totals_display, use_container_width=True, hide_index=True)

st.subheader("Liga de desenvolvimento")
display_dev = dev_roster.copy()
for season in visible_seasons:
    label = SEASON_LABELS[season]
    if label in display_dev.columns:
        display_dev[label] = display_dev[label].apply(currency)
option_cols_dev = [c for c in display_dev.columns if str(c).startswith("TO ")]
for col in option_cols_dev:
    salary_col = col.replace("TO ", "")
    if salary_col in display_dev.columns:
        mask = display_dev[col].astype(str).str.strip().str.lower().eq("sim")
        display_dev.loc[mask, salary_col] = display_dev.loc[mask, salary_col].map(lambda x: f"🔴 {x}")
        display_dev.loc[mask, col] = display_dev.loc[mask, col].map(lambda x: f"🔴 {x}")

display_table(display_dev)

st.subheader("Totalizadores da development")
dev_totals_display = dev_totals.copy()
for col in ["Salários", "Cap restante"]:
    if col in dev_totals_display.columns:
        dev_totals_display[col] = dev_totals_display[col].apply(currency)
st.dataframe(dev_totals_display, use_container_width=True, hide_index=True)

st.info("Próximo passo: aplicar as transferências de forma efetiva no pipeline do roster e da development.")
