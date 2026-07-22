from pathlib import Path
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
)

st.set_page_config(page_title="Elencos Fantasy NBA", layout="wide")

st.title("Elencos Fantasy NBA")
st.caption("Etapa 2 v2: seletor de temporada, visão salarial do elenco principal e totalizadores.")

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


if not DEFAULT_FILE.exists():
    st.error("Arquivo roster.xlsx não encontrado na pasta do projeto.")
    st.stop()

data = cached_load(str(DEFAULT_FILE))
teams = get_team_options(data["teams"])

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

main_roster_raw = build_roster_view(data["roster"], data["players"], selected_team_id, "MAIN", visible_seasons)
main_roster = format_roster_for_display(main_roster_raw, visible_seasons)
main_totals = calculate_main_totals(data["roster"], data["fines"], selected_team_id, visible_seasons)

with st.expander("Diagnóstico de carregamento", expanded=False):
    diag = {
        "players": len(data["players"]),
        "teams": len(data["teams"]),
        "roster": len(data["roster"]),
        "development": len(data["development"]),
        "picks": len(data["picks"]),
        "fines": len(data["fines"]),
        "time_selecionado": selected_team_name,
        "temporadas_visiveis": [SEASON_LABELS[s] for s in visible_seasons],
    }
    st.json(diag)

st.subheader("Elenco principal")
display_main = main_roster.copy()
for season in visible_seasons:
    label = SEASON_LABELS[season]
    if label in display_main.columns:
        display_main[label] = display_main[label].apply(currency)

if any(str(c).startswith("TO ") for c in display_main.columns):
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

st.info("Na próxima etapa entraremos com a tabela da liga de desenvolvimento usando a mesma lógica de temporadas e totalizadores.")
