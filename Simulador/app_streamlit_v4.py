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

def safe_num(v):
    return float(v) if pd.notna(v) else np.nan

def team_stats(df):
    cols = ["pts", "trb", "ast", "stl", "blk", "three_p", "tov"]
    base = {}
    for c in cols:
        base[f"{c}_avg"] = safe_num(df[c].mean()) if c in df.columns else np.nan
    return base

def matchup_win(team_row, teams_df):
    cols = ["pts_avg", "trb_avg", "ast_avg", "stl_avg", "blk_avg", "three_p_avg", "tov_avg"]
    valid = teams_df.dropna(subset=cols).copy()
    if valid.empty:
        return np.nan

    wins = []
    team_id = team_row.get("team_id", None)
    for _, opp in valid.iterrows():
        if team_id is not None and opp.get("team_id", None) == team_id:
            continue
        w = 0
        for c in cols:
            a = team_row.get(c, np.nan)
            b = opp.get(c, np.nan)
            if pd.isna(a) or pd.isna(b):
                continue
            if c == "tov_avg":
                w += int(a < b)
            else:
                w += int(a > b)
        wins.append(w)
    return float(np.mean(wins)) if wins else np.nan

def build_comp_chart(current, new):
    categories = ["pts_avg", "trb_avg", "ast_avg", "stl_avg", "blk_avg", "three_p_avg", "tov_avg"]
    labels = {
        "pts_avg": "PTS",
        "trb_avg": "TRB",
        "ast_avg": "AST",
        "stl_avg": "STL",
        "blk_avg": "BLK",
        "three_p_avg": "3PT",
        "tov_avg": "TOV",
    }

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Antes",
        x=[labels[c] for c in categories],
        y=[current.get(c, np.nan) for c in categories],
        marker_color="#4C78A8"
    ))
    fig.add_trace(go.Bar(
        name="Depois",
        x=[labels[c] for c in categories],
        y=[new.get(c, np.nan) for c in categories],
        marker_color="#F58518"
    ))
    fig.update_layout(barmode="group", title="Antes vs Depois", height=460)
    return fig

def compare_players(out_row, in_row):
    cols = ["pts", "trb", "ast", "stl", "blk", "three_p", "tov"]
    labels = {
        "pts": "PTS",
        "trb": "TRB",
        "ast": "AST",
        "stl": "STL",
        "blk": "BLK",
        "three_p": "3PT",
        "tov": "TOV",
    }
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name=str(out_row.get("player_name", "Saindo")),
        x=[labels[c] for c in cols],
        y=[safe_num(out_row.get(c, np.nan)) for c in cols],
        marker_color="#E45756"
    ))
    fig.add_trace(go.Bar(
        name=str(in_row.get("player_name", "Entrando")),
        x=[labels[c] for c in cols],
        y=[safe_num(in_row.get(c, np.nan)) for c in cols],
        marker_color="#72B7B2"
    ))
    fig.update_layout(barmode="group", title="Comparação dos jogadores", height=420)
    return fig

players, teams, lineup, bench, scenarios = load_data()

for df in [players, teams, lineup, bench, scenarios]:
    df.columns = [str(c).strip() for c in df.columns]

team_names = teams["team_name"].fillna("NA").tolist()
team_sel = st.sidebar.selectbox("Time", team_names)
view = st.sidebar.radio("Visão", ["Visão geral", "Elenco", "Matchups", "Simulador"])

team_row = teams[teams["team_name"].fillna("NA") == team_sel].iloc[0]
team_id = int(team_row["team_id"])
team_players = players[players["team_id"] == team_id].copy()

st.title("Fantasy NBA Dashboard v4.2")
st.caption("Versão limpa com simulador mais estável e melhor experiência de uso.")

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
        val = team_row[col] if col in team_row.index else np.nan
        c.metric(label, f"{val:.2f}" if pd.notna(val) else "NA")

    matchup_val = team_row["matchup_win_avg"] if "matchup_win_avg" in team_row.index else np.nan
    st.metric("Matchup win médio", f"{matchup_val:.2f}" if pd.notna(matchup_val) else "NA")

    left, right = st.columns(2)

    with left:
        ranking = teams[teams["team_name"].notna()].sort_values("matchup_win_avg", ascending=False)
        fig = px.bar(ranking, x="team_name", y="matchup_win_avg", title="Matchup win médio")
        fig.update_layout(height=420, xaxis_title="Time", yaxis_title="Média")
        st.plotly_chart(fig, use_container_width=True)

    with right:
        corr_cols = [c for c in ["pts", "trb", "ast", "stl", "blk", "three_p", "tov"] if c in team_players.columns]
        if corr_cols:
            corr = team_players[corr_cols].corr(numeric_only=True)
            fig = px.imshow(
                corr,
                text_auto=True,
                aspect="auto",
                color_continuous_scale="Viridis",
                title="Correlação interna",
            )
            fig.update_layout(height=420)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Sem colunas suficientes para calcular correlação.")

elif view == "Elenco":
    display_cols = [c for c in ["player_name", "position", "pts", "trb", "ast", "stl", "blk", "three_p", "tov"] if c in team_players.columns]
    st.dataframe(
        team_players[display_cols].sort_values("pts", ascending=False) if "pts" in team_players.columns else team_players[display_cols],
        use_container_width=True,
    )

    if "pts" in team_players.columns and "player_name" in team_players.columns:
        fig = px.bar(
            team_players.sort_values("pts", ascending=False).head(10),
            x="player_name",
            y="pts",
            title="Top 10 por pontos",
        )
        fig.update_layout(height=450, xaxis_title="Jogador", yaxis_title="PTS")
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
                    if pd.isna(tm.loc[a, c]) or pd.isna(tm.loc[b, c]):
                        continue
                    if c == "tov_avg":
                        w += int(tm.loc[a, c] < tm.loc[b, c])
                    else:
                        w += int(tm.loc[a, c] > tm.loc[b, c])
                mat.loc[a, b] = w

    st.dataframe(mat, use_container_width=True)
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

    team_positions = sorted(team_players["position"].dropna().astype(str).unique().tolist()) if "position" in team_players.columns else []
    pos_choice = st.selectbox("Filtro de posição", ["Todas"] + team_positions)

    eligible_out = team_players.copy()
    if pos_choice != "Todas" and "position" in eligible_out.columns:
        eligible_out = eligible_out[eligible_out["position"].astype(str) == pos_choice]

    if eligible_out.empty:
        st.warning("Nenhum jogador disponível para a posição selecionada.")
        st.stop()

    out_name = st.selectbox("Saindo", eligible_out["player_name"].tolist())
    out_row = eligible_out[eligible_out["player_name"] == out_name].iloc[0]

    pool = players[players["team_id"] != team_id].copy()
    if pos_choice != "Todas" and "position" in pool.columns:
        pool = pool[pool["position"].astype(str) == pos_choice]

    if pool.empty:
        st.warning("Nenhum jogador elegível encontrado no pool externo para esse filtro.")
        st.stop()

    in_name = st.selectbox("Entrando", pool["player_name"].drop_duplicates().tolist())
    in_row = pool[pool["player_name"] == in_name].iloc[0]

    info1, info2 = st.columns(2)
    with info1:
        st.markdown("### Jogador saindo")
        st.write({
            "Jogador": out_row.get("player_name", "NA"),
            "Posição": out_row.get("position", "NA"),
            "PTS": safe_num(out_row.get("pts", np.nan)),
            "TRB": safe_num(out_row.get("trb", np.nan)),
            "AST": safe_num(out_row.get("ast", np.nan)),
            "STL": safe_num(out_row.get("stl", np.nan)),
            "BLK": safe_num(out_row.get("blk", np.nan)),
            "3PT": safe_num(out_row.get("three_p", np.nan)),
            "TOV": safe_num(out_row.get("tov", np.nan)),
        })
    with info2:
        st.markdown("### Jogador entrando")
        st.write({
            "Jogador": in_row.get("player_name", "NA"),
            "Posição": in_row.get("position", "NA"),
            "PTS": safe_num(in_row.get("pts", np.nan)),
            "TRB": safe_num(in_row.get("trb", np.nan)),
            "AST": safe_num(in_row.get("ast", np.nan)),
            "STL": safe_num(in_row.get("stl", np.nan)),
            "BLK": safe_num(in_row.get("blk", np.nan)),
            "3PT": safe_num(in_row.get("three_p", np.nan)),
            "TOV": safe_num(in_row.get("tov", np.nan)),
        })

    st.plotly_chart(compare_players(out_row, in_row), use_container_width=True)

    valid_trade = True
    invalid_reason = None
    if pos_choice != "Todas" and "position" in out_row.index and "position" in in_row.index:
        if str(out_row.get("position")) != str(in_row.get("position")):
            valid_trade = False
            invalid_reason = "Troca inválida: as posições não batem com o filtro aplicado."

    if not valid_trade:
        st.error(invalid_reason)
        st.stop()

    current = team_stats(team_players)
    n = max(len(team_players), 1)
    new = {
        "pts_avg": current["pts_avg"] + (safe_num(in_row.get("pts", 0)) - safe_num(out_row.get("pts", 0))) / n,
        "trb_avg": current["trb_avg"] + (safe_num(in_row.get("trb", 0)) - safe_num(out_row.get("trb", 0))) / n,
        "ast_avg": current["ast_avg"] + (safe_num(in_row.get("ast", 0)) - safe_num(out_row.get("ast", 0))) / n,
        "stl_avg": current["stl_avg"] + (safe_num(in_row.get("stl", 0)) - safe_num(out_row.get("stl", 0))) / n,
        "blk_avg": current["blk_avg"] + (safe_num(in_row.get("blk", 0)) - safe_num(out_row.get("blk", 0))) / n,
        "three_p_avg": current["three_p_avg"] + (safe_num(in_row.get("three_p", 0)) - safe_num(out_row.get("three_p", 0))) / n,
        "tov_avg": current["tov_avg"] + (safe_num(in_row.get("tov", 0)) - safe_num(out_row.get("tov", 0))) / n,
    }

    old_row = pd.Series({"team_id": team_id, **current})
    old_m = matchup_win(old_row, teams)

    temp_teams = teams.copy()
    for k, v in new.items():
        temp_teams.loc[temp_teams["team_id"] == team_id, k] = v

    temp_team_row = temp_teams[temp_teams["team_id"] == team_id].iloc[0]
    new_m = matchup_win(temp_team_row, temp_teams)

    c1, c2, c3 = st.columns(3)
    c1.metric("Antes", f"{old_m:.2f}" if pd.notna(old_m) else "NA")
    c2.metric("Depois", f"{new_m:.2f}" if pd.notna(new_m) else "NA")
    c3.metric("Delta", f"{(new_m - old_m):+.2f}" if pd.notna(old_m) and pd.notna(new_m) else "NA")

    st.plotly_chart(build_comp_chart(current, new), use_container_width=True)
