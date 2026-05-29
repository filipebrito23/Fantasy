
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

def team_stats(df):
    return {
        'pts_avg': df['pts'].mean(), 'trb_avg': df['trb'].mean(), 'ast_avg': df['ast'].mean(),
        'stl_avg': df['stl'].mean(), 'blk_avg': df['blk'].mean(), 'three_p_avg': df['three_p'].mean(),
        'tov_avg': df['tov'].mean(),
    }

def matchup_win(team_row, teams_df):
    cols=['pts_avg','trb_avg','ast_avg','stl_avg','blk_avg','three_p_avg','tov_avg']
    wins=[]
    for _,o in teams_df.dropna(subset=cols).iterrows():
        if o['team_id']==team_row['team_id']:
            continue
        w=0
        for c in cols:
            w += (team_row[c] < o[c]) if c=='tov_avg' else (team_row[c] > o[c])
        wins.append(w)
    return float(np.mean(wins)) if wins else np.nan

players, teams, lineup, bench, scenarios = load_data()
team_names = teams['team_name'].fillna('NA').tolist()
team_sel = st.sidebar.selectbox('Time', team_names)
view = st.sidebar.radio('Visão', ['Visão geral', 'Elenco', 'Matchups', 'Simulador'])
team_row = teams[teams['team_name'].fillna('NA') == team_sel].iloc[0]
team_id = int(team_row['team_id'])
team_players = players[players['team_id'] == team_id].copy()

st.title('Fantasy NBA Dashboard v3')

if view == 'Visão geral':
    cols = st.columns(7)
    for c,(label,col) in zip(cols, [('PTS','pts_avg'),('TRB','trb_avg'),('AST','ast_avg'),('STL','stl_avg'),('BLK','blk_avg'),('3PT','three_p_avg'),('TOV','tov_avg')]):
        val = team_row[col]
        c.metric(label, f'{val:.2f}' if pd.notna(val) else 'NA')
    st.metric('Matchup win médio', f"{team_row['matchup_win_avg']:.2f}" if pd.notna(team_row['matchup_win_avg']) else 'NA')
    left, right = st.columns(2)
    with left:
        ranking = teams[teams['team_name'].notna()].sort_values('matchup_win_avg', ascending=False)
        st.plotly_chart(px.bar(ranking, x='team_name', y='matchup_win_avg', title='Matchup win médio'), use_container_width=True)
    with right:
        corr = team_players[['pts','trb','ast','stl','blk','three_p','tov']].corr()
        st.plotly_chart(px.imshow(corr, text_auto=True, aspect='auto', color_continuous_scale='Viridis', title='Correlação interna'), use_container_width=True)

elif view == 'Elenco':
    st.dataframe(team_players[['player_name','position','pts','trb','ast','stl','blk','three_p','tov']].sort_values('pts', ascending=False), use_container_width=True)
    st.plotly_chart(px.bar(team_players.sort_values('pts', ascending=False).head(10), x='player_name', y='pts', title='Top 10 por pontos'), use_container_width=True)

elif view == 'Matchups':
    tm = teams[teams['team_name'].notna()].copy().set_index('team_name')
    cols = ['pts_avg','trb_avg','ast_avg','stl_avg','blk_avg','three_p_avg','tov_avg']
    mat = pd.DataFrame(index=tm.index, columns=tm.index)
    for a in tm.index:
        for b in tm.index:
            if a == b:
                mat.loc[a,b] = np.nan
            else:
                w = 0
                for c in cols:
                    w += (tm.loc[a,c] < tm.loc[b,c]) if c=='tov_avg' else (tm.loc[a,c] > tm.loc[b,c])
                mat.loc[a,b] = w
    st.dataframe(mat)
    st.plotly_chart(px.imshow(mat.astype(float), text_auto=True, aspect='auto', color_continuous_scale='Blues', title='Matriz de confrontos'), use_container_width=True)

else:
    st.subheader('Simulador de troca')
    active = lineup[lineup['team_id'] == team_id].copy() if 'team_id' in lineup.columns else pd.DataFrame()
    bench_team = bench[bench['team_id'] == team_id].copy() if 'team_id' in bench.columns else pd.DataFrame()
    out_name = st.selectbox('Saindo', team_players['player_name'].tolist())
    pool = pd.concat([players[players['team_id'] != team_id], bench_team.merge(players, on='player_id', how='left')], ignore_index=True)
    pool = pool.dropna(subset=['player_name'])
    in_name = st.selectbox('Entrando', pool['player_name'].drop_duplicates().tolist())
    out_row = team_players[team_players['player_name'] == out_name].iloc[0]
    in_row = pool[pool['player_name'] == in_name].iloc[0]
    current = team_stats(team_players)
    n = max(len(team_players), 1)
    new = {k: current[k] + (in_row[c]-out_row[c])/n for k,c in [('pts_avg','pts'),('trb_avg','trb'),('ast_avg','ast'),('stl_avg','stl'),('blk_avg','blk'),('three_p_avg','three_p'),('tov_avg','tov')]}
    old_row = pd.Series({'team_id': team_id, **current})
    new_row = pd.Series({'team_id': team_id, **new})
    old_m = matchup_win(old_row, teams)
    temp_teams = teams.copy()
    for k,v in new.items():
        temp_teams.loc[temp_teams['team_id']==team_id, k] = v
    temp_teams.loc[temp_teams['team_id']==team_id, 'matchup_win_avg'] = matchup_win(temp_teams[temp_teams['team_id']==team_id].iloc[0], temp_teams)
    new_m = float(temp_teams.loc[temp_teams['team_id']==team_id, 'matchup_win_avg'].iloc[0])
    c1,c2,c3 = st.columns(3)
    c1.metric('Antes', f'{old_m:.2f}' if pd.notna(old_m) else 'NA')
    c2.metric('Depois', f'{new_m:.2f}' if pd.notna(new_m) else 'NA')
    c3.metric('Delta', f'{(new_m-old_m):+.2f}' if pd.notna(old_m) and pd.notna(new_m) else 'NA')
    comp = pd.DataFrame([{'cenario':'Antes', **current}, {'cenario':'Depois', **new}])
    melted = comp.melt(id_vars='cenario', var_name='categoria', value_name='valor')
    fig = go.Figure()
    for s in melted['cenario'].dropna().unique():
        d = melted[melted['cenario'] == s]
        fig.add_trace(go.Bar(name=str(s), x=d['categoria'], y=d['valor']))
    fig.update_layout(barmode='group', title='Antes vs Depois')
    st.plotly_chart(fig, use_container_width=True)
