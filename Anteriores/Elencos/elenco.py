from pathlib import Path
import pandas as pd
import streamlit as st
import jinja2
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
st.caption("Etapa 2: seletor de temporada, visão salarial do elenco principal e totalizadores.")

DEFAULT_FILE = Path("roster.xlsx")

@st.cache_data
def cached_load(file_path: str):
    return load_workbook_data(file_path)


def currency(v: float) -> str:
    if pd.isna(v):
        return "-"
    return f"US$ {v:,.2f}"


def highlight_team_options(df: pd.DataFrame):
    styles = pd.DataFrame("", index=df.index, columns=df.columns)
    for col in df.columns:
        if str(col).startswith("TO "):
            salary_col = col.replace("TO ", "")
            if salary_col in df.columns:
                mask = df[col].astype(str).str.strip().str.lower().eq("sim")
                styles.loc[mask, salary_col] = "color: red; font-weight: 700;"
                styles.loc[mask, col] = "color: red; font-weight: 700;"
    return styles


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
styled_main = main_roster.style.apply(highlight_team_options, axis=None)
for season in visible_seasons:
    label = SEASON_LABELS[season]
    if label in main_roster.columns:
        styled_main = styled_main.format({label: currency})

st.dataframe(styled_main, use_container_width=True, hide_index=True)

st.subheader("Totalizadores do elenco principal")
st.dataframe(
    main_totals.style.format(
        {
            "Salários": currency,
            "Multas": currency,
            "Cap restante": currency,
        }
    ),
    use_container_width=True,
    hide_index=True,
)

st.info("Na próxima etapa entraremos com a tabela da liga de desenvolvimento usando a mesma lógica de temporadas e totalizadores.")
