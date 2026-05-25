
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

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
team_names = teams['team_name'].fillna('NA').tolist()
team_sel = st.sidebar.selectbox('Time', team_names)
view = st.sidebar.radio('Visualização', ['Visão geral', 'Jogadores', 'Matchups', 'Cenários'])
team_row = teams[teams['team_name'].fillna('NA') == team_sel].iloc[0]
team_id = team_row['team_id']
team_players = players[players['team_id'] == team_id].copy()

st.title('Fantasy NBA Dashboard')

if view == 'Visão geral':
    st.subheader(f'Resumo: {team_sel}')
    cols = st.columns(7)
    labels = [('PTS','pts_avg'),('TRB','trb_avg'),('AST','ast_avg'),('STL','stl_avg'),('BLK','blk_avg'),('3PT','three_p_avg'),('TOV','tov_avg')]
    for c,(label,col) in zip(cols, labels):
        val = team_row[col]
        c.metric(label, f'{val:.2f}' if pd.notna(val) else 'NA')
    st.metric('Matchup win médio', f"{team_row['matchup_win_avg']:.2f}" if pd.notna(team_row['matchup_win_avg']) else 'NA')
    left, right = st.columns([1,1])
    with left:
        ranking = teams[teams['team_name'].notna()].sort_values('matchup_win_avg', ascending=False)
        fig = px.bar(ranking, x='team_name', y='matchup_win_avg', title='Matchup win médio por time')
        fig.update_layout(height=420)
        st.plotly_chart(fig, use_container_width=True)
    with right:
        metric_cols = ['pts_avg','trb_avg','ast_avg','stl_avg','blk_avg','three_p_avg','tov_avg']
        fig2 = go.Figure(data=go.Heatmap(z=team_players[['pts','trb','ast','stl','blk','three_p','tov']].corr().values,
                                         x=['PTS','TRB','AST','STL','BLK','3PT','TOV'],
                                         y=['PTS','TRB','AST','STL','BLK','3PT','TOV'],
                                         colorscale='Viridis'))
        fig2.update_layout(title='Correlação interna do elenco', height=420)
        st.plotly_chart(fig2, use_container_width=True)

elif view == 'Jogadores':
    st.subheader(f'Elenco: {team_sel}')
    show_cols = ['player_name','position','pts','trb','ast','stl','blk','three_p','tov']
    st.dataframe(team_players[show_cols].sort_values('pts', ascending=False), use_container_width=True)
    fig = px.bar(team_players.sort_values('pts', ascending=False).head(10), x='player_name', y='pts', title='Top 10 por pontos')
    fig.update_layout(height=450)
    st.plotly_chart(fig, use_container_width=True)

elif view == 'Matchups':
    st.subheader('Matriz de matchups')
    metric_cols = ['pts_avg','trb_avg','ast_avg','stl_avg','blk_avg','three_p_avg','tov_avg']
    tm = teams[teams['team_name'].notna()].copy().set_index('team_name')
    matchup = pd.DataFrame(index=tm.index, columns=tm.index)
    for a in tm.index:
        for b in tm.index:
            if a == b:
                matchup.loc[a,b] = np.nan
            else:
                w = 0
                for col in metric_cols:
                    if col == 'tov_avg':
                        w += tm.loc[a,col] < tm.loc[b,col]
                    else:
                        w += tm.loc[a,col] > tm.loc[b,col]
                matchup.loc[a,b] = w
    st.dataframe(matchup)
    fig = px.imshow(matchup.astype(float), text_auto=True, aspect='auto', color_continuous_scale='Blues', title='Heatmap de confrontos')
    fig.update_layout(height=700)
    st.plotly_chart(fig, use_container_width=True)

else:
    st.subheader(f'Cenários: {team_sel}')
    st.dataframe(scenarios[scenarios['team_id'] == team_id] if 'team_id' in scenarios.columns else scenarios, use_container_width=True)
    st.info('Nesta versão, a aba de cenários é apenas leitura. Na próxima, vamos habilitar simulação interativa.')
