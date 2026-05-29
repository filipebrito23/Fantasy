import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Fantasy NBA Dashboard", layout="wide")

DATA_CANDIDATES = ["dash_filled_with_na.xlsx", "dash.xlsx", "sportsref_download.xlsx"]

@st.cache_data
def load_data():
    last_error = None
    for path in DATA_CANDIDATES:
        try:
            xls = pd.ExcelFile(path)
            sheets = set(xls.sheet_names)
            players = pd.read_excel(xls, "players") if "players" in sheets else pd.DataFrame()
            teams = pd.read_excel(xls, "teams") if "teams" in sheets else pd.DataFrame()
            lineup = pd.read_excel(xls, "lineup_active") if "lineup_active" in sheets else pd.DataFrame()
            bench = pd.read_excel(xls, "bench") if "bench" in sheets else pd.DataFrame()
            scenarios = pd.read_excel(xls, "scenarios") if "scenarios" in sheets else pd.DataFrame()
            return path, players, teams, lineup, bench, scenarios
        except Exception as e:
            last_error = e
    raise RuntimeError(f"Não foi possível abrir nenhuma base: {DATA_CANDIDATES}. Erro final: {last_error}")

def normalize_columns(df):
    if df.empty:
        return df
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    return df

def safe_num(v):
    return float(v) if pd.notna(v) else np.nan

def team_stats(df):
    src = {
        "pts_avg": "pts",
        "trb_avg": "trb",
        "ast_avg": "ast",
        "stl_avg": "stl",
        "blk_avg": "blk",
        "three_p_avg": "three_p",
        "tov_avg": "tov",
    }
    out = {}
    for k, c in src.items():
        out[k] = safe_num(df[c].mean()) if c in df.columns and not df.empty else np.nan
    return out

def matchup_score(row_a, row_b):
    cats = ["pts_avg", "trb_avg", "ast_avg", "stl_avg", "blk_avg", "three_p_avg", "tov_avg"]
    wins = 0
    for c in cats:
        a = row_a.get(c, np.nan)
        b = row_b.get(c, np.nan)
        if pd.isna(a) or pd.isna(b):
            continue
        if c == "tov_avg":
            wins += int(a < b)
        else:
            wins += int(a > b)
    return wins

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
        wins.append(matchup_score(team_row, opp))
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
    fig.add_trace(go.Bar(name="Antes", x=[labels[c] for c in categories], y=[current.get(c, np.nan) for c in categories], marker_color="#4C78A8"))
    fig.add_trace(go.Bar(name="Depois", x=[labels[c] for c in categories], y=[new.get(c, np.nan) for c in categories], marker_color="#F58518"))
    fig.update_layout(barmode="group", title="Antes vs Depois", height=430)
    return fig

def compare_players(out_rows, in_rows):
    cols = ["pts", "trb", "ast", "stl", "blk", "three_p", "tov"]
    labels = {"pts":"PTS","trb":"TRB","ast":"AST","stl":"STL","blk":"BLK","three_p":"3PT","tov":"TOV"}
    out_sum = {c: sum(safe_num(v) for v in out_rows[c].fillna(0)) for c in cols}
    in_sum = {c: sum(safe_num(v) for v in in_rows[c].fillna(0)) for c in cols}
    fig = go.Figure()
    fig.add_trace(go.Bar(name="Saindo", x=[labels[c] for c in cols], y=[out_sum[c] for c in cols], marker_color="#E45756"))
    fig.add_trace(go.Bar(name="Entrando", x=[labels[c] for c in cols], y=[in_sum[c] for c in cols], marker_color="#72B7B2"))
    fig.update_layout(barmode="group", title="Pacote saindo vs entrando", height=400)
    return fig

def rank_targets(team_players, pool, team_id, teams_df, top_n=15):
    current = team_stats(team_players)
    base_row = pd.Series({"team_id": team_id, **current})
    old_m = matchup_win(base_row, teams_df)
    n = max(len(team_players), 1)
    rows = []
    for _, in_row in pool.iterrows():
        for _, out_row in team_players.iterrows():
            new = {
                "pts_avg": current["pts_avg"] + (safe_num(in_row.get("pts", 0)) - safe_num(out_row.get("pts", 0))) / n,
                "trb_avg": current["trb_avg"] + (safe_num(in_row.get("trb", 0)) - safe_num(out_row.get("trb", 0))) / n,
                "ast_avg": current["ast_avg"] + (safe_num(in_row.get("ast", 0)) - safe_num(out_row.get("ast", 0))) / n,
                "stl_avg": current["stl_avg"] + (safe_num(in_row.get("stl", 0)) - safe_num(out_row.get("stl", 0))) / n,
                "blk_avg": current["blk_avg"] + (safe_num(in_row.get("blk", 0)) - safe_num(out_row.get("blk", 0))) / n,
                "three_p_avg": current["three_p_avg"] + (safe_num(in_row.get("three_p", 0)) - safe_num(out_row.get("three_p", 0))) / n,
                "tov_avg": current["tov_avg"] + (safe_num(in_row.get("tov", 0)) - safe_num(out_row.get("tov", 0))) / n,
            }
            temp_team_row = pd.Series({"team_id": team_id, **new})
            new_m = matchup_win(temp_team_row, teams_df)
            rows.append({
                "jogador_saindo": out_row.get("player_name", "NA"),
                "jogador_entrando": in_row.get("player_name", "NA"),
                "pos_out": out_row.get("position", "NA"),
                "pos_in": in_row.get("position", "NA"),
                "antes": old_m,
                "depois": new_m,
                "delta": new_m - old_m if pd.notna(old_m) and pd.notna(new_m) else np.nan,
                "delta_pts": new["pts_avg"] - current["pts_avg"],
                "delta_trb": new["trb_avg"] - current["trb_avg"],
                "delta_ast": new["ast_avg"] - current["ast_avg"],
                "delta_stl": new["stl_avg"] - current["stl_avg"],
                "delta_blk": new["blk_avg"] - current["blk_avg"],
                "delta_3pt": new["three_p_avg"] - current["three_p_avg"],
                "delta_tov": new["tov_avg"] - current["tov_avg"],
            })
    res = pd.DataFrame(rows)
    if res.empty:
        return res
    return res.sort_values(["delta", "depois"], ascending=[False, False]).head(top_n)

source_file, players, teams, lineup, bench, scenarios = load_data()
players = normalize_columns(players)
teams = normalize_columns(teams)
lineup = normalize_columns(lineup)
bench = normalize_columns(bench)
scenarios = normalize_columns(scenarios)

if players.empty or teams.empty:
    st.error(f"Base carregada sem as abas necessárias. Arquivo detectado: {source_file}")
    st.stop()

team_names = teams["team_name"].fillna("NA").tolist()
team_sel = st.sidebar.selectbox("Time", team_names)
view = st.sidebar.radio("Visão", ["Visão geral", "Elenco", "Matchups", "Simulador", "Trade Finder"])

team_row = teams[teams["team_name"].fillna("NA") == team_sel].iloc[0]
team_id = int(team_row["team_id"])
team_players = players[players["team_id"] == team_id].copy()

st.title("Fantasy NBA Dashboard v4.3")
st.caption(f"Base detectada: {source_file}")

if view == "Visão geral":
    cols = st.columns(7)
    metrics = [("PTS","pts_avg"),("TRB","trb_avg"),("AST","ast_avg"),("STL","stl_avg"),("BLK","blk_avg"),("3PT","three_p_avg"),("TOV","tov_avg")]
    for c, (label, col) in zip(cols, metrics):
        val = team_row[col] if col in team_row.index else np.nan
        c.metric(label, f"{val:.2f}" if pd.notna(val) else "NA")
    matchup_val = team_row["matchup_win_avg"] if "matchup_win_avg" in team_row.index else np.nan
    st.metric("Matchup win médio", f"{matchup_val:.2f}" if pd.notna(matchup_val) else "NA")

    left, right = st.columns(2)
    with left:
        ranking = teams[teams["team_name"].notna()].sort_values("matchup_win_avg", ascending=False)
        fig = px.bar(ranking, x="team_name", y="matchup_win_avg", title="Matchup win médio")
        fig.update_layout(height=420)
        st.plotly_chart(fig, use_container_width=True)
    with right:
        corr_cols = [c for c in ["pts","trb","ast","stl","blk","three_p","tov"] if c in team_players.columns]
        if corr_cols:
            corr = team_players[corr_cols].corr(numeric_only=True)
            fig = px.imshow(corr, text_auto=True, aspect="auto", color_continuous_scale="Viridis", title="Correlação interna")
            fig.update_layout(height=420)
            st.plotly_chart(fig, use_container_width=True)

elif view == "Elenco":
    display_cols = [c for c in ["player_name","position","pts","trb","ast","stl","blk","three_p","tov"] if c in team_players.columns]
    base_df = team_players[display_cols].copy()
    if "pts" in base_df.columns:
        base_df = base_df.sort_values("pts", ascending=False)
    st.dataframe(base_df, use_container_width=True)

elif view == "Matchups":
    tm = teams[teams["team_name"].notna()].copy().set_index("team_name")
    cols = ["pts_avg", "trb_avg", "ast_avg", "stl_avg", "blk_avg", "three_p_avg", "tov_avg"]
    mat = pd.DataFrame(index=tm.index, columns=tm.index)
    for a in tm.index:
        for b in tm.index:
            if a == b:
                mat.loc[a, b] = np.nan
            else:
                mat.loc[a, b] = matchup_score(tm.loc[a], tm.loc[b])
    st.dataframe(mat, use_container_width=True)
    fig = px.imshow(mat.astype(float), text_auto=True, aspect="auto", color_continuous_scale="Blues", title="Matriz de confrontos")
    fig.update_layout(height=700)
    st.plotly_chart(fig, use_container_width=True)

elif view == "Simulador":
    st.subheader("Simulador de troca")
    multi_trade = st.toggle("Troca múltipla (2 por 2)", value=False)

    team_positions = sorted(team_players["position"].dropna().astype(str).unique().tolist()) if "position" in team_players.columns else []
    pos_choice = st.selectbox("Filtro de posição", ["Todas"] + team_positions)

    eligible_out = team_players.copy()
    pool = players[players["team_id"] != team_id].copy()
    if pos_choice != "Todas" and "position" in eligible_out.columns:
        eligible_out = eligible_out[eligible_out["position"].astype(str) == pos_choice]
        pool = pool[pool["position"].astype(str) == pos_choice]

    if eligible_out.empty or pool.empty:
        st.warning("Sem jogadores suficientes com o filtro aplicado.")
        st.stop()

    if not multi_trade:
        out_names = [st.selectbox("Saindo", eligible_out["player_name"].drop_duplicates().tolist(), key="out1")]
        in_names = [st.selectbox("Entrando", pool["player_name"].drop_duplicates().tolist(), key="in1")]
    else:
        c1, c2 = st.columns(2)
        with c1:
            out_names = st.multiselect("Saindo (escolha 2)", eligible_out["player_name"].drop_duplicates().tolist(), max_selections=2)
        with c2:
            in_names = st.multiselect("Entrando (escolha 2)", pool["player_name"].drop_duplicates().tolist(), max_selections=2)
        if len(out_names) != 2 or len(in_names) != 2:
            st.info("Selecione exatamente 2 jogadores saindo e 2 entrando.")
            st.stop()

    out_rows = eligible_out[eligible_out["player_name"].isin(out_names)].drop_duplicates(subset=["player_name"])
    in_rows = pool[pool["player_name"].isin(in_names)].drop_duplicates(subset=["player_name"])

    st.plotly_chart(compare_players(out_rows, in_rows), use_container_width=True)

    stats_cols = ["pts","trb","ast","stl","blk","three_p","tov"]
    c_left, c_right = st.columns(2)
    with c_left:
        st.markdown("### Pacote saindo")
        st.dataframe(out_rows[[c for c in ["player_name","position"] + stats_cols if c in out_rows.columns]], use_container_width=True)
    with c_right:
        st.markdown("### Pacote entrando")
        st.dataframe(in_rows[[c for c in ["player_name","position"] + stats_cols if c in in_rows.columns]], use_container_width=True)

    current = team_stats(team_players)
    n = max(len(team_players), 1)

    out_sum = {c: sum(safe_num(v) for v in out_rows[c].fillna(0)) for c in stats_cols}
    in_sum = {c: sum(safe_num(v) for v in in_rows[c].fillna(0)) for c in stats_cols}
    new = {
        "pts_avg": current["pts_avg"] + (in_sum["pts"] - out_sum["pts"]) / n,
        "trb_avg": current["trb_avg"] + (in_sum["trb"] - out_sum["trb"]) / n,
        "ast_avg": current["ast_avg"] + (in_sum["ast"] - out_sum["ast"]) / n,
        "stl_avg": current["stl_avg"] + (in_sum["stl"] - out_sum["stl"]) / n,
        "blk_avg": current["blk_avg"] + (in_sum["blk"] - out_sum["blk"]) / n,
        "three_p_avg": current["three_p_avg"] + (in_sum["three_p"] - out_sum["three_p"]) / n,
        "tov_avg": current["tov_avg"] + (in_sum["tov"] - out_sum["tov"]) / n,
    }

    old_row = pd.Series({"team_id": team_id, **current})
    new_row = pd.Series({"team_id": team_id, **new})
    old_m = matchup_win(old_row, teams)
    new_m = matchup_win(new_row, teams)

    c1, c2, c3 = st.columns(3)
    c1.metric("Antes", f"{old_m:.2f}" if pd.notna(old_m) else "NA")
    c2.metric("Depois", f"{new_m:.2f}" if pd.notna(new_m) else "NA")
    c3.metric("Delta", f"{(new_m - old_m):+.2f}" if pd.notna(old_m) and pd.notna(new_m) else "NA")

    impact_df = pd.DataFrame({
        "Categoria": ["PTS","TRB","AST","STL","BLK","3PT","TOV"],
        "Antes": [current["pts_avg"], current["trb_avg"], current["ast_avg"], current["stl_avg"], current["blk_avg"], current["three_p_avg"], current["tov_avg"]],
        "Depois": [new["pts_avg"], new["trb_avg"], new["ast_avg"], new["stl_avg"], new["blk_avg"], new["three_p_avg"], new["tov_avg"]],
    })
    impact_df["Delta"] = impact_df["Depois"] - impact_df["Antes"]
    st.markdown("### Impacto por categoria")
    st.dataframe(impact_df, use_container_width=True)
    st.plotly_chart(build_comp_chart(current, new), use_container_width=True)

else:
    st.subheader("Trade Finder")
    same_position = st.checkbox("Apenas mesma posição", value=True)
    top_n = st.slider("Quantidade de sugestões", min_value=5, max_value=30, value=15, step=5)

    pool = players[players["team_id"] != team_id].copy()
    if same_position and "position" in team_players.columns and "position" in pool.columns:
        valid_positions = set(team_players["position"].dropna().astype(str).unique())
        pool = pool[pool["position"].astype(str).isin(valid_positions)]

    ranked = rank_targets(team_players, pool.drop_duplicates(subset=["player_name"]), team_id, teams, top_n=top_n)
    if ranked.empty:
        st.warning("Não foi possível gerar sugestões com os filtros atuais.")
        st.stop()

    st.dataframe(ranked, use_container_width=True)

    fig = px.bar(
        ranked.head(10),
        x="jogador_entrando",
        y="delta",
        color="jogador_saindo",
        title="Top ganhos de matchup win",
        barmode="group"
    )
    fig.update_layout(height=500, xaxis_title="Alvo", yaxis_title="Delta")
    st.plotly_chart(fig, use_container_width=True)
