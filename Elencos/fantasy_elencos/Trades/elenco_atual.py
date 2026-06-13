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
    calculate_dev_totals,
)

st.set_page_config(page_title="Elencos Fantasy NBA", layout="wide")

st.title("Elencos Fantasy NBA")
st.caption("Etapa 4_3 v4.3: TO vira marcador visual no salário; totais do principal filtrados por time.")

DEFAULT_FILE = Path("roster.xlsx")

@st.cache_data
def cached_load(file_path: str):
    return load_workbook_data(file_path)


def currency(v: float) -> str:
    if pd.isna(v):
        return "-"
    return f"US$ {v:,.2f}"


def display_table(df: pd.DataFrame):
    st.dataframe(df, use_container_width=True, hide_index=True)


def build_red_flags(df: pd.DataFrame, visible_seasons: list[str]) -> pd.DataFrame:
    out = df.copy()
    for season in visible_seasons:
        sal_col = SEASON_LABELS[season]
        opt_col = f"TO_{season}"
        if sal_col not in out.columns or opt_col not in out.columns:
            continue
        flag_col = f"{sal_col}__red"
        out[flag_col] = out[opt_col].astype(str).str.strip().str.lower().eq("sim")
        out = out.drop(columns=[opt_col])
    return out


def render_red_table(df: pd.DataFrame, visible_seasons: list[str]) -> str:
    out = df.copy()
    drop_cols = [c for c in out.columns if str(c).startswith("TO_")]
    if drop_cols:
        out = out.drop(columns=drop_cols)
    for season in visible_seasons:
        sal_col = SEASON_LABELS[season]
        flag_col = f"{sal_col}__red"
        if sal_col in out.columns and flag_col in out.columns:
            out[sal_col] = out[sal_col].apply(lambda x: f"<span style='color:red'>{x}</span>" if pd.notna(x) else "")
            out = out.drop(columns=[flag_col])
    return out.to_html(escape=False, index=False)

if not DEFAULT_FILE.exists():
    st.error("Arquivo roster.xlsx não encontrado na pasta do projeto.")
    st.stop()

data = cached_load(str(DEFAULT_FILE))
teams = get_team_options(data["teams"])

c1, c2 = st.columns([2, 1])
with c1:
    selected_team_name = st.selectbox("Selecione o time", teams["team_name"].tolist())
with c2:
    selected_start_season = st.selectbox("Temporada inicial", SEASONS, format_func=lambda x: SEASON_LABELS[x])

selected_team_id = int(teams.loc[teams["team_name"] == selected_team_name, "team_id"].iloc[0])
visible_seasons = get_visible_seasons(selected_start_season)

main_roster_raw = build_roster_view(data["roster"], data["players"], selected_team_id, "MAIN", visible_seasons)
main_roster = format_roster_for_display(main_roster_raw, visible_seasons)
main_team_df = data["roster"].loc[data["roster"]["team_id"] == selected_team_id].copy()
main_totals = calculate_main_totals(main_team_df, data["fines"], selected_team_id, visible_seasons)

dev_team_df = data["development"].loc[data["development"]["team_id"] == selected_team_id].copy()
dev_roster_raw = build_roster_view(data["development"], data["players"], selected_team_id, "DEV", visible_seasons)
dev_roster = format_roster_for_display(dev_roster_raw, visible_seasons)
dev_totals = calculate_dev_totals(dev_team_df, visible_seasons)

with st.expander("Diagnóstico de carregamento", expanded=False):
    st.json({
        "players": len(data["players"]),
        "teams": len(data["teams"]),
        "roster": len(data["roster"]),
        "development": len(data["development"]),
        "picks": len(data["picks"]),
        "fines": len(data["fines"]),
        "time_selecionado": selected_team_name,
        "temporadas_visiveis": [SEASON_LABELS[s] for s in visible_seasons],
    })

st.subheader("Elenco principal")
display_main = build_red_flags(main_roster, visible_seasons)
red_cols_main = [f"{SEASON_LABELS[s]}__red" for s in visible_seasons if f"{SEASON_LABELS[s]}__red" in display_main.columns]
for season in visible_seasons:
    label = SEASON_LABELS[season]
    if label in display_main.columns:
        display_main[label] = display_main[label].apply(currency)
for c in red_cols_main:
    base_col = c.replace("__red", "")
    display_main[base_col] = display_main[base_col].astype(str)
    display_main.loc[display_main[c].fillna(False), base_col] = display_main.loc[display_main[c].fillna(False), base_col].map(lambda x: f"<span style='color:red'>{x}</span>")
    display_main = display_main.drop(columns=[c])
st.markdown(render_red_table(display_main, visible_seasons), unsafe_allow_html=True)

st.subheader("Totalizadores do elenco principal")
main_totals_display = main_totals.copy()
for col in ["Salários", "Multas", "Cap restante"]:
    if col in main_totals_display.columns:
        main_totals_display[col] = main_totals_display[col].apply(currency)
st.dataframe(main_totals_display, use_container_width=True, hide_index=True)

st.subheader("Liga de desenvolvimento")
display_dev = build_red_flags(dev_roster, visible_seasons)
red_cols_dev = [f"{SEASON_LABELS[s]}__red" for s in visible_seasons if f"{SEASON_LABELS[s]}__red" in display_dev.columns]
for season in visible_seasons:
    label = SEASON_LABELS[season]
    if label in display_dev.columns:
        display_dev[label] = display_dev[label].apply(currency)
for c in red_cols_dev:
    base_col = c.replace("__red", "")
    display_dev[base_col] = display_dev[base_col].astype(str)
    display_dev.loc[display_dev[c].fillna(False), base_col] = display_dev.loc[display_dev[c].fillna(False), base_col].map(lambda x: f"<span style='color:red'>{x}</span>")
    display_dev = display_dev.drop(columns=[c])
st.markdown(render_red_table(display_dev, visible_seasons), unsafe_allow_html=True)

st.subheader("Totalizadores da development")
dev_totals_display = dev_totals.copy()
for col in ["Salários", "Cap restante"]:
    if col in dev_totals_display.columns:
        dev_totals_display[col] = dev_totals_display[col].apply(currency)
st.dataframe(dev_totals_display, use_container_width=True, hide_index=True)
