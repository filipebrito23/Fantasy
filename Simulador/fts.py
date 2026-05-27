import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

st.set_page_config(page_title="Fantasy NBA Dashboard", layout="wide")

SOURCE_FILE = "base.xlsx"
STAT_COLS = ["pts", "trb", "ast", "stl", "blk", "three_p", "tov"]
AVG_COLS = ["pts_avg", "trb_avg", "ast_avg", "stl_avg", "blk_avg", "three_p_avg", "tov_avg"]


def norm_cols(df):
    if df.empty:
        return df
    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]
    return df


def first_col(df, options):
    for c in options:
        if c in df.columns:
            return c
    return None


def load_sheet(xls, name):
    return pd.read_excel(xls, name) if name in xls.sheet_names else pd.DataFrame()


def load_data():
    xls = pd.ExcelFile(SOURCE_FILE)
    sheets = {s.lower(): s for s in xls.sheet_names}
    return (
        SOURCE_FILE,
        load_sheet(xls, sheets.get("players", "")),
        load_sheet(xls, sheets.get("teams", "")),
        load_sheet(xls, sheets.get("lineup_active", "")),
        load_sheet(xls, sheets.get("bench", "")),
        load_sheet(xls, sheets.get("scenarios", "")),
        load_sheet(xls, sheets.get("scenario_lineup_active", "")),
        load_sheet(xls, sheets.get("scenario_bench", "")),
        load_sheet(xls, sheets.get("scenario_moves", "")),
    )


def compute_fantasy_value(df):
    if df.empty:
        return df
    df = df.copy()
    for c in STAT_COLS:
        if c not in df.columns:
            df[c] = np.nan
    df["fantasy_value"] = (
        df["pts"].fillna(0)
        + df["trb"].fillna(0)
        + df["ast"].fillna(0)
        + df["stl"].fillna(0) * 1.5
        + df["blk"].fillna(0) * 1.5
        + df["three_p"].fillna(0)
        - df["tov"].fillna(0)
    )
    return df


def team_stats(roster):
    return {f"{c}_avg": float(roster[c].sum()) if c in roster.columns and not roster.empty else np.nan for c in STAT_COLS}


def matchup_score(a, b):
    wins = 0
    for c in AVG_COLS:
        if pd.isna(a.get(c, np.nan)) or pd.isna(b.get(c, np.nan)):
            continue
        wins += int(a[c] < b[c]) if c == "tov_avg" else int(a[c] > b[c])
    return wins


def update_teams(teams, lineup, players):
    teams = teams.copy()
    team_id_col = first_col(teams, ["team_id", "teamid"])
    lineup_team_col = first_col(lineup, ["team_id", "teamid"])
    lineup_player_col = first_col(lineup, ["player_id", "playerid"])
    lineup_active_col = first_col(lineup, ["is_active", "isactive"])
    player_id_col = first_col(players, ["player_id", "playerid"])
    if not team_id_col or not lineup_team_col or not lineup_player_col or not player_id_col:
        return teams
    lineup = lineup.copy(); players = players.copy()
    lineup[lineup_team_col] = pd.to_numeric(lineup[lineup_team_col], errors="coerce")
    lineup[lineup_player_col] = pd.to_numeric(lineup[lineup_player_col], errors="coerce")
    if lineup_active_col and lineup_active_col in lineup.columns:
        lineup[lineup_active_col] = pd.to_numeric(lineup[lineup_active_col], errors="coerce")
    players[player_id_col] = pd.to_numeric(players[player_id_col], errors="coerce")
    for idx, row in teams.iterrows():
        tid = pd.to_numeric(pd.Series([row[team_id_col]]), errors="coerce").iloc[0]
        if pd.isna(tid) or int(tid) == 15:
            continue
        mask = lineup[lineup[lineup_team_col] == tid].copy()
        if lineup_active_col and lineup_active_col in mask.columns:
            mask = mask[mask[lineup_active_col].fillna(1).astype(int) == 1]
        active_ids = pd.to_numeric(mask[lineup_player_col], errors="coerce").dropna().astype(int).unique().tolist()
        if len(active_ids) != 6:
            for c in AVG_COLS:
                teams.loc[idx, c] = np.nan
            continue
        roster = players[players[player_id_col].isin(active_ids)]
        stats = team_stats(roster)
        for c in AVG_COLS:
            teams.loc[idx, c] = stats[c]
    if team_id_col in teams.columns:
        def calc_mw(r):
            tid = pd.to_numeric(pd.Series([r[team_id_col]]), errors="coerce").iloc[0]
            if pd.isna(tid) or int(tid) == 15 or any(pd.isna(r[c]) for c in AVG_COLS):
                return np.nan
            others = teams[(teams[team_id_col] != r[team_id_col]) & (teams[team_id_col] != 15)].dropna(subset=AVG_COLS)
            if others.empty:
                return np.nan
            return float(np.mean([matchup_score(r, o) for _, o in others.iterrows()]))
        teams["matchup_win_avg"] = teams.apply(calc_mw, axis=1)
    return teams


def lineup_view(team_id, lineup, players):
    lineup_team_col = first_col(lineup, ["team_id", "teamid"])
    lineup_player_col = first_col(lineup, ["player_id", "playerid"])
    lineup_active_col = first_col(lineup, ["is_active", "isactive"])
    player_id_col = first_col(players, ["player_id", "playerid"])
    if lineup.empty or not lineup_team_col or not lineup_player_col:
        return pd.DataFrame()
    active = lineup.copy()
    active[lineup_team_col] = pd.to_numeric(active[lineup_team_col], errors="coerce")
    active[lineup_player_col] = pd.to_numeric(active[lineup_player_col], errors="coerce")
    if lineup_active_col and lineup_active_col in active.columns:
        active[lineup_active_col] = pd.to_numeric(active[lineup_active_col], errors="coerce")
    active = active[active[lineup_team_col] == team_id]
    if lineup_active_col and lineup_active_col in active.columns:
        active = active[active[lineup_active_col].fillna(1).astype(int) == 1]
    return active.merge(players, left_on=lineup_player_col, right_on=player_id_col, how="left")


def bench_view(team_id, bench, players):
    bench_team_col = first_col(bench, ["team_id", "teamid"])
    bench_player_col = first_col(bench, ["player_id", "playerid"])
    player_id_col = first_col(players, ["player_id", "playerid"])
    if bench.empty or not bench_team_col or not bench_player_col:
        return pd.DataFrame()
    b = bench.copy()
    b[bench_team_col] = pd.to_numeric(b[bench_team_col], errors="coerce")
    b[bench_player_col] = pd.to_numeric(b[bench_player_col], errors="coerce")
    b = b[b[bench_team_col] == team_id]
    return b.merge(players, left_on=bench_player_col, right_on=player_id_col, how="left")


def scenario_views(scenarios, scen_lineup, scen_bench, scen_moves):
    return scenarios, scen_lineup, scen_bench, scen_moves


def scenario_roster_for_team(scenario_id, team_id, scen_lineup, scen_bench, players):
    lineup_team_col = first_col(scen_lineup, ["team_id", "teamid"])
    lineup_pid_col = first_col(scen_lineup, ["player_id", "playerid"])
    bench_team_col = first_col(scen_bench, ["team_id", "teamid"])
    bench_pid_col = first_col(scen_bench, ["player_id", "playerid"])
    player_id_col = first_col(players, ["player_id", "playerid"])
    if lineup_team_col is None or lineup_pid_col is None:
        return pd.DataFrame(), pd.DataFrame()
    sl = scen_lineup.copy()
    sb = scen_bench.copy()
    sl[lineup_team_col] = pd.to_numeric(sl[lineup_team_col], errors="coerce")
    sb[bench_team_col] = pd.to_numeric(sb[bench_team_col], errors="coerce")
    sl[lineup_pid_col] = pd.to_numeric(sl[lineup_pid_col], errors="coerce")
    sb[bench_pid_col] = pd.to_numeric(sb[bench_pid_col], errors="coerce")
    if "scenario_id" in sl.columns:
        sl["scenario_id"] = pd.to_numeric(sl["scenario_id"], errors="coerce")
        sl = sl[(sl["scenario_id"] == scenario_id) | (sl["scenario_id"].isna())]
    if "scenario_id" in sb.columns:
        sb["scenario_id"] = pd.to_numeric(sb["scenario_id"], errors="coerce")
        sb = sb[(sb["scenario_id"] == scenario_id) | (sb["scenario_id"].isna())]
    sl = sl[sl[lineup_team_col] == team_id]
    sb = sb[sb[bench_team_col] == team_id]
    return (
        sl.merge(players, left_on=lineup_pid_col, right_on=player_id_col, how="left"),
        sb.merge(players, left_on=bench_pid_col, right_on=player_id_col, how="left"),
    )


path, players, teams, lineup, bench, scenarios, scen_lineup, scen_bench, scen_moves = load_data()
players = compute_fantasy_value(norm_cols(players))
teams = norm_cols(teams)
lineup = norm_cols(lineup)
bench = norm_cols(bench)
scenarios = norm_cols(scenarios)
scen_lineup = norm_cols(scen_lineup)
scen_bench = norm_cols(scen_bench)
scen_moves = norm_cols(scen_moves)
teams = update_teams(teams, lineup, players)
team_name_col = first_col(teams, ["team_name", "teamname"])
team_id_col = first_col(teams, ["team_id", "teamid"])
scenario_id_col = first_col(scenarios, ["scenario_id", "scenarioid"])
scenario_name_col = first_col(scenarios, ["scenario_name", "scenarioname"])
scenario_team_col = first_col(scenarios, ["team_id", "teamid"])

st.title("Fantasy NBA Dashboard - fts")

if team_name_col is None or team_id_col is None:
    st.error("A aba teams precisa ter team_id e team_name.")
    st.stop()

team_sel = st.sidebar.selectbox("Time", teams[team_name_col].fillna("NA").tolist())
view = st.sidebar.radio("Visão", ["Visão geral", "Lineup ativo", "Banco", "Cenários", "Sugestão de troca"])
team_row = teams[teams[team_name_col].fillna("NA") == team_sel].iloc[0]
team_id = int(team_row[team_id_col]) if pd.notna(team_row[team_id_col]) else None

if view == "Visão geral":
    if any(pd.isna(team_row.get(c, np.nan)) for c in AVG_COLS):
        st.warning("Este time ainda não tem 6 titulares válidos ou o lineup ativo não foi reconhecido.")
    cols = st.columns(7)
    for c, label, col in zip(cols, ["PTS", "TRB", "AST", "STL", "BLK", "3PT", "TOV"], AVG_COLS):
        val = team_row[col] if col in team_row.index else np.nan
        c.metric(label, f"{val:.2f}" if pd.notna(val) else "NA")
    st.metric("Matchup win médio", f"{team_row['matchup_win_avg']:.2f}" if pd.notna(team_row.get("matchup_win_avg", np.nan)) else "NA")

elif view == "Lineup ativo":
    lv = lineup_view(team_id, lineup, players)
    if lv.empty:
        st.info("Lineup não reconhecido para este time.")
    else:
        display_cols = [c for c in ["player_name", "position", "slot", "pts", "trb", "ast", "stl", "blk", "three_p", "tov", "fantasy_value"] if c in lv.columns]
        st.dataframe(lv[display_cols], use_container_width=True)

elif view == "Banco":
    bv = bench_view(team_id, bench, players)
    if bv.empty:
        st.info("Sem banco cadastrado ou aba ausente.")
    else:
        display_cols = [c for c in ["player_name", "position", "bench_order", "pts", "trb", "ast", "stl", "blk", "three_p", "tov", "fantasy_value"] if c in bv.columns]
        st.dataframe(bv[display_cols], use_container_width=True)

elif view == "Cenários":
    st.subheader("Cenários")
    if not scenarios.empty:
        cols = [c for c in [scenario_id_col, scenario_name_col, scenario_team_col, "move_type", "description", "created_at", "is_active"] if c in scenarios.columns]
        st.dataframe(scenarios[cols], use_container_width=True)
    else:
        st.info("Nenhum cenário cadastrado ainda.")
    if not scen_lineup.empty:
        st.markdown("### scenario_lineup_active")
        st.dataframe(scen_lineup, use_container_width=True)
    if not scen_bench.empty:
        st.markdown("### scenario_bench")
        st.dataframe(scen_bench, use_container_width=True)
    if not scen_moves.empty:
        st.markdown("### scenario_moves")
        st.dataframe(scen_moves, use_container_width=True)

else:
    st.subheader("Sugestão de troca")
    lv = lineup_view(team_id, lineup, players)
    bv = bench_view(team_id, bench, players)
    if lv.empty or bv.empty:
        st.info("Precisa de lineup e banco preenchidos para gerar sugestão.")
    else:
        suggestions = []
        for _, out_row in lv.iterrows():
            candidates = bv.copy()
            if "position" in candidates.columns and "position" in out_row.index:
                same_pos = candidates[candidates["position"] == out_row.get("position")]
                if not same_pos.empty:
                    candidates = same_pos
            candidates = candidates.assign(delta=candidates["fantasy_value"].fillna(0) - float(out_row.get("fantasy_value", 0)))
            candidates["abs_delta"] = candidates["delta"].abs()
            best = candidates.sort_values(["abs_delta", "delta"], ascending=[True, False]).head(1)
            if not best.empty:
                br = best.iloc[0]
                suggestions.append({"out": out_row.get("player_name", ""), "in": br.get("player_name", ""), "delta": br.get("delta", np.nan), "out_pos": out_row.get("position", ""), "in_pos": br.get("position", "")})
        sug = pd.DataFrame(suggestions)
        if sug.empty:
            st.info("Nenhuma sugestão encontrada.")
        else:
            st.dataframe(sug, use_container_width=True)
            st.plotly_chart(px.bar(sug, x="out", y="delta", color="delta", title="Impacto estimado da melhor troca por titular"), use_container_width=True)
