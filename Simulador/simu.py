import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Fantasy NBA Dashboard", layout="wide")

@st.cache_data
def load_data(path="dash_filled_with_na.xlsx"):
    xls = pd.ExcelFile(path)
    players = pd.read_excel(xls, "players")
    teams = pd.read_excel(xls, "teams")
    lineup = pd.read_excel(xls, "lineup_active")
    bench = pd.read_excel(xls, "bench")
    scenarios = pd.read_excel(xls, "scenarios")
    return players, teams, lineup, bench, scenarios

def team_stats(df):
    return {
        "pts_avg": df["pts"].mean(),
        "trb_avg": df["trb"].mean(),
        "ast_avg": df["ast"].mean(),
        "stl_avg": df["stl"].mean(),
        "blk_avg": df["blk"].mean(),
        "three_p_avg": df["three_p"].mean(),
        "tov_avg": df["tov"].mean(),
    }

def matchup_win(team_row, teams_df):
    cols = ["pts_avg", "trb_avg", "ast_avg", "stl_avg", "blk_avg", "three_p_avg", "tov_avg"]
    wins = []
    for _, opp in teams_df.dropna(subset=cols).iterrows():
        if opp["team_id"] == team_row["team_id"]:
            continue
        w = 0
        for c in cols:
            if c == "tov_avg":
                w += team_row[c] < opp[c]
            else:
                w += team_row[c] > opp[c]
        wins.append(w)
    return float(np.mean(wins)) if wins else np.nan

players, teams, lineup, bench, scenarios = load_data()

team_names = teams["team_name"].fillna("NA").tolist()
team_sel = st.sidebar.selectbox("Time", team_names)
view = st.sidebar.radio("Visão", ["Visão geral", "Elenco", "Matchups", "Simulador"])

team_row = teams[teams["team_name"].fillna("NA") == team_sel].iloc[0]
team_id = int(team_row["team_id"])
team_players = players[players["team_id"] == team_id].copy()

st.title("Fantasy NBA Dashboard v4.1")

if view == "Visão geral":
    cols = st.columns(7)
    metrics = [
        ("PTS", "pts_avg"),
        ("TRB", "trb_avg"),
        ("AST", "ast_avg"),
        ("STL", "stl_avg"),
        ("BLK", "blk_avg"),
        ("3PT", "three_p_avg"),
        ("TOV", "tov_avg"),
    ]
    for c, (label, col) in zip(cols, metrics):
        val = team_row[col]
        c.metric(label, f"{val:.2f}" if pd.notna(val) else "NA")

    st.metric(
        "Matchup win médio",
        f"{team_row['matchup_win_avg']:.2f}" if pd.notna(team_row["matchup_win_avg"]) else "NA",
    )

    left, right = st.columns(2)

    with left:
        ranking = teams[teams["team_name"].notna()].sort_values("matchup_win_avg", ascending=False)
        fig = px.bar(ranking, x="team_name", y="matchup_win_avg", title="Matchup win médio")
        fig.update_layout(height=420)
        st.plotly_chart(fig, use_container_width=True)

    with right:
        corr = team_players[["pts", "trb", "ast", "stl", "blk", "three_p", "tov"]].corr()
        fig = px.imshow(
            corr,
            text_auto=True,
            aspect="auto",
            color_continuous_scale="Viridis",
            title="Correlação interna",
        )
        fig.update_layout(height=420)
        st.plotly_chart(fig, use_container_width=True)

elif view == "Elenco":
    st.dataframe(
        team_players[["player_name", "position", "pts", "trb", "ast", "stl", "blk", "three_p", "tov"]]
        .sort_values("pts", ascending=False),
        use_container_width=True,
    )

    fig = px.bar(
        team_players.sort_values("pts", ascending=False).head(10),
        x="player_name",
        y="pts",
        title="Top 10 por pontos",
    )
    fig.update_layout(height=450)
    st.plotly_chart(fig, use_container_width=True)

elif view == "Matchups":
    tm = teams[teams["team_name"].notna()].copy().set_index("team_name")
    cols = ["pts_avg", "trb_avg", "ast_avg", "stl_avg", "blk_avg", "three_p_avg", "tov_avg"]

    mat = pd.DataFrame(index=tm.index, columns=tm.index)
    for a in tm.index:
        for b in tm.index:
            if a == b:
                mat.loc[a, b] = np.nan
            else:
                w = 0
                for c in cols:
                    if c == "tov_avg":
                        w += tm.loc[a, c] < tm.loc[b, c]
                    else:
                        w += tm.loc[a, c] > tm.loc[b, c]
                mat.loc[a, b] = w

    st.dataframe(mat)
    fig = px.imshow(
        mat.astype(float),
        text_auto=True,
        aspect="auto",
        color_continuous_scale="Blues",
        title="Matriz de confrontos",
    )
    fig.update_layout(height=700)
    st.plotly_chart(fig, use_container_width=True)

else:
    st.subheader("Simulador de troca")

    out_name = st.selectbox("Saindo", team_players["player_name"].tolist())

    pool = players[players["team_id"] != team_id].copy()
    in_name = st.selectbox("Entrando", pool["player_name"].drop_duplicates().tolist())

    out_row = team_players[team_players["player_name"] == out_name].iloc[0]
    in_row = pool[pool["player_name"] == in_name].iloc[0]

    current = team_stats(team_players)
    n = max(len(team_players), 1)

    new = {
        "pts_avg": current["pts_avg"] + (in_row["pts"] - out_row["pts"]) / n,
        "trb_avg": current["trb_avg"] + (in_row["trb"] - out_row["trb"]) / n,
        "ast_avg": current["ast_avg"] + (in_row["ast"] - out_row["ast"]) / n,
        "stl_avg": current["stl_avg"] + (in_row["stl"] - out_row["stl"]) / n,
        "blk_avg": current["blk_avg"] + (in_row["blk"] - out_row["blk"]) / n,
        "three_p_avg": current["three_p_avg"] + (in_row["three_p"] - out_row["three_p"]) / n,
        "tov_avg": current["tov_avg"] + (in_row["tov"] - out_row["tov"]) / n,
    }

    old_row = pd.Series({"team_id": team_id, **current})
    new_row = pd.Series({"team_id": team_id, **new})

    old_m = matchup_win(old_row, teams)

    temp_teams = teams.copy()
    for k, v in new.items():
        temp_teams.loc[temp_teams["team_id"] == team_id, k] = v

    temp_teams.loc[temp_teams["team_id"] == team_id, "matchup_win_avg"] = matchup_win(
        temp_teams[temp_teams["team_id"] == team_id].iloc[0],
        temp_teams,
    )
    new_m = float(temp_teams.loc[temp_teams["team_id"] == team_id, "matchup_win_avg"].iloc[0])

    c1, c2, c3 = st.columns(3)
    c1.metric("Antes", f"{old_m:.2f}" if pd.notna(old_m) else "NA")
    c2.metric("Depois", f"{new_m:.2f}" if pd.notna(new_m) else "NA")
    c3.metric("Delta", f"{(new_m - old_m):+.2f}" if pd.notna(old_m) and pd.notna(new_m) else "NA")

    comp = pd.DataFrame(
        [
            {"cenario": "Antes", **current},
            {"cenario": "Depois", **new},
        ]
    )

    melted = comp.melt(id_vars="cenario", var_name="categoria", value_name="valor")
    fig = go.Figure()
    for s in melted["cenario"].dropna().unique():
        d = melted[melted["cenario"] == s]
        fig.add_trace(go.Bar(name=str(s), x=d["categoria"], y=d["valor"]))
    fig.update_layout(barmode="group", title="Antes vs Depois")
    st.plotly_chart(fig, use_container_width=True)