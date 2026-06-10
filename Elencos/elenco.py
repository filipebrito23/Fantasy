from pathlib import Path
import streamlit as st
from data_loader import load_workbook_data
from transforms import get_team_options, build_roster_view

st.set_page_config(page_title="Elencos Fantasy NBA", layout="wide")

st.title("Elencos Fantasy NBA")
st.caption("Etapa 1: leitura da planilha, seletor de time e pré-visualização dos elencos.")

DEFAULT_FILE = Path("roster.xlsx")

@st.cache_data
def cached_load(file_path: str):
    return load_workbook_data(file_path)

if not DEFAULT_FILE.exists():
    st.error("Arquivo roster.xlsx não encontrado na pasta do projeto.")
    st.stop()

data = cached_load(str(DEFAULT_FILE))
teams = get_team_options(data["teams"])

selected_team_name = st.selectbox("Selecione o time", teams["team_name"].tolist())
selected_team_id = int(teams.loc[teams["team_name"] == selected_team_name, "team_id"].iloc[0])

with st.expander("Diagnóstico de carregamento", expanded=False):
    diag = {
        "players": len(data["players"]),
        "teams": len(data["teams"]),
        "roster": len(data["roster"]),
        "development": len(data["development"]),
        "picks": len(data["picks"]),
        "fines": len(data["fines"]),
    }
    st.json(diag)

main_roster = build_roster_view(data["roster"], data["players"], selected_team_id, "MAIN")
dev_roster = build_roster_view(data["development"], data["players"], selected_team_id, "DEV")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Elenco principal")
    st.dataframe(main_roster, use_container_width=True, hide_index=True)

with col2:
    st.subheader("Liga de desenvolvimento")
    st.dataframe(dev_roster, use_container_width=True, hide_index=True)
