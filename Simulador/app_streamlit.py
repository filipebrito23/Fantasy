
import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title='Fantasy NBA Dashboard', layout='wide')

@st.cache_data
def load_data(path='dash_filled_with_na.xlsx'):
    xls = pd.ExcelFile(path)
    players = pd.read_excel(xls, 'players')
    teams = pd.read_excel(xls, 'teams')
    lineup = pd.read_excel(xls, 'lineup_active')
    bench = pd.read_excel(xls, 'bench')
    scenarios = pd.read_excel(xls, 'scenarios')
    return players, teams, lineup, bench, scenarios

players, teams, lineup, bench, scenarios = load_data()

st.title('Fantasy NBA Dashboard')

team_sel = st.sidebar.selectbox('Team', teams['team_name'].fillna('NA').tolist())
view = st.sidebar.radio('View', ['Team overview', 'Players', 'Scenarios'])

if view == 'Team overview':
    t = teams[teams['team_name'].fillna('NA') == team_sel].iloc[0]
    cols = st.columns(7)
    metrics = ['pts_avg','trb_avg','ast_avg','stl_avg','blk_avg','three_p_avg','tov_avg']
    labels = ['PTS','TRB','AST','STL','BLK','3PT','TOV']
    for c,l,m in zip(cols, labels, metrics):
        c.metric(l, round(t[m],2) if pd.notna(t[m]) else None)
    fig = px.bar(teams[teams['team_name'].notna()].sort_values('matchup_win_avg', ascending=False), x='team_name', y='matchup_win_avg')
    st.plotly_chart(fig, use_container_width=True)

elif view == 'Players':
    df = players[players['team_id'] == teams.loc[teams['team_name'].fillna('NA') == team_sel, 'team_id'].iloc[0]].copy()
    st.dataframe(df)

else:
    st.dataframe(scenarios)
