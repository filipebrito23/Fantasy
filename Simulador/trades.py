import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

st.set_page_config(page_title="Fantasy NBA Dashboard", layout="wide")

SOURCE_FILE = "base.xlsx"
STAT_COLS = ["pts", "trb", "ast", "stl", "blk", "three_p", "tov"]
STAT_LABELS = {"pts": "PTS", "trb": "REB", "ast": "AST", "stl": "STL", "blk": "BLK", "three_p": "3PT", "tov": "TOV"}


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
    return {
        "players": load_sheet(xls, sheets.get("players", "")),
        "teams": load_sheet(xls, sheets.get("teams", "")),
        "lineup": load_sheet(xls, sheets.get("lineup_active", "")),
        "bench": load_sheet(xls, sheets.get("bench", "")),
        "scenarios": load_sheet(xls, sheets.get("scenarios", "")),
        "scenario_lineup": load_sheet(xls, sheets.get("scenario_lineup_active", "")),
        "scenario_bench": load_sheet(xls, sheets.get("scenario_bench", "")),
        "scenario_moves": load_sheet(xls, sheets.get("scenario_moves", "")),
    }


def compute_fantasy_value(df):
    if df.empty:
        return df
    df = df.copy()
    for c in STAT_COLS:
        if c not in df.columns:
            df[c] = np.nan
    df["fantasy_value"] = df["pts"].fillna(0) + df["trb"].fillna(0) + df["ast"].fillna(0) + df["stl"].fillna(0) * 1.5 + df["blk"].fillna(0) * 1.5 + df["three_p"].fillna(0) - df["tov"].fillna(0)
    return df


def team_cols(df):
    return {"team_id": first_col(df, ["team_id", "teamid"]), "team_name": first_col(df, ["team_name", "teamname"]), "player_id": first_col(df, ["player_id", "playerid"]), "player_name": first_col(df, ["player_name", "name"]), "slot": first_col(df, ["slot"]), "bench_order": first_col(df, ["bench_order"]), "is_active": first_col(df, ["is_active", "isactive"])}


def calc_team_table(players, teams, lineup):
    tc, lc, pc = team_cols(teams), team_cols(lineup), team_cols(players)
    t = teams.copy()
    for c in STAT_COLS:
        if c not in t.columns:
            t[c] = np.nan
    if tc["team_id"] is None or tc["team_name"] is None or lc["team_id"] is None or lc["player_id"] is None or pc["player_id"] is None:
        return t
    t["team_id"] = pd.to_numeric(t[tc["team_id"]], errors="coerce")
    l = lineup.copy(); p = players.copy()
    l[lc["team_id"]] = pd.to_numeric(l[lc["team_id"]], errors="coerce")
    l[lc["player_id"]] = pd.to_numeric(l[lc["player_id"]], errors="coerce")
    if lc["is_active"] and lc["is_active"] in l.columns:
        l[lc["is_active"]] = pd.to_numeric(l[lc["is_active"]], errors="coerce")
    p[pc["player_id"]] = pd.to_numeric(p[pc["player_id"]], errors="coerce")
    for idx, row in t.iterrows():
        tid = row["team_id"]
        if pd.isna(tid) or int(tid) == 15:
            continue
        cur = l[l[lc["team_id"]] == tid].copy()
        if lc["is_active"] and lc["is_active"] in cur.columns:
            cur = cur[cur[lc["is_active"]].fillna(1).astype(int) == 1]
        ids = cur[lc["player_id"]].dropna().astype(int).tolist()
        roster = p[p[pc["player_id"]].isin(ids)]
        for c in STAT_COLS:
            t.loc[idx, c] = roster[c].sum() if c in roster.columns and not roster.empty else np.nan
    return t


def team_rankings(teams_calc):
    valid = teams_calc[teams_calc["team_id"] != 15].dropna(subset=STAT_COLS)
    rows = []
    for c in STAT_COLS:
        asc = c == "tov"
        order = valid[["team_id", c]].sort_values(c, ascending=asc).reset_index(drop=True)
        order["rank"] = np.arange(1, len(order) + 1)
        order["stat"] = c
        rows.append(order)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def matchup_strengths(teams_calc):
    valid = teams_calc[teams_calc["team_id"] != 15].dropna(subset=STAT_COLS)
    out = []
    for _, a in valid.iterrows():
        score = 0
        for _, b in valid.iterrows():
            if a["team_id"] == b["team_id"]:
                continue
            wins = sum([(a[c] > b[c]) if c != "tov" else (a[c] < b[c]) for c in STAT_COLS])
            score += wins
        out.append({"team_id": a["team_id"], "strength": score / max(len(valid) - 1, 1)})
    return pd.DataFrame(out)


def display_table(df, cols):
    return df[[c for c in cols if c in df.columns]].copy() if not df.empty else pd.DataFrame()


def player_pool(df, exclude_team=None):
    if df.empty:
        return df
    if "team_id" not in df.columns or exclude_team is None:
        return df
    return df[(df["team_id"].isna()) | (df["team_id"] != exclude_team)]


def scenario_views(data):
    return {k: v for k, v in data.items() if k in ["scenarios", "scenario_lineup", "scenario_bench", "scenario_moves"]}


raw = load_data()
players = compute_fantasy_value(norm_cols(raw["players"]))
teams = norm_cols(raw["teams"])
lineup = norm_cols(raw["lineup"])
bench = norm_cols(raw["bench"])
scenarios = norm_cols(raw["scenarios"])
scenario_lineup = norm_cols(raw["scenario_lineup"])
scenario_bench = norm_cols(raw["scenario_bench"])
scenario_moves = norm_cols(raw["scenario_moves"])
teams_calc = calc_team_table(players, teams, lineup)
teamc = team_cols(teams_calc)

st.title("Fantasy NBA Dashboard")

if teams_calc.empty or teamc["team_name"] is None:
    st.error("Não foi possível carregar os times.")
    st.stop()

team_list = teams_calc.loc[teams_calc["team_id"] != 15, teamc["team_name"]].fillna("NA").tolist()
sel_team = st.sidebar.selectbox("Time", team_list)
sel_row = teams_calc[teams_calc[teamc["team_name"]].fillna("NA") == sel_team].iloc[0]
view = st.sidebar.radio("Visão", ["Resumo", "Ranking", "Elenco", "Banco", "Cenários", "Sugestão de troca"])

if view == "Resumo":
    cols = st.columns(7)
    for col, stat in zip(cols, STAT_COLS):
        col.metric(STAT_LABELS[stat], f"{sel_row[stat]:.2f}" if pd.notna(sel_row[stat]) else "NA")
    ms = matchup_strengths(teams_calc)
    strength = ms.set_index("team_id").loc[sel_row["team_id"], "strength"] if not ms.empty and sel_row["team_id"] in ms.set_index("team_id").index else np.nan
    st.metric("Força de confronto", f"{strength:.2f}" if pd.notna(strength) else "NA")

elif view == "Ranking":
    rk = team_rankings(teams_calc)
    if rk.empty:
        st.info("Sem ranking disponível.")
    else:
        cat = st.selectbox("Categoria", [STAT_LABELS[c] for c in STAT_COLS])
        stat_key = {v: k for k, v in STAT_LABELS.items()}[cat]
        subset = rk[rk["stat"] == stat_key].merge(teams_calc[["team_id", teamc["team_name"]]], on="team_id", how="left")
        subset = subset.rename(columns={teamc["team_name"]: "team"})
        st.dataframe(subset[["rank", "team", stat_key]].sort_values("rank"), use_container_width=True)
        st.plotly_chart(px.bar(subset.sort_values("rank"), x="team", y=stat_key, color="rank", title=f"Ranking - {cat}"), use_container_width=True)

elif view == "Elenco":
    lc, pc = team_cols(lineup), team_cols(players)
    active = lineup.copy()
    if not active.empty and lc["team_id"] and lc["player_id"]:
        active[lc["team_id"]] = pd.to_numeric(active[lc["team_id"]], errors="coerce")
        active[lc["player_id"]] = pd.to_numeric(active[lc["player_id"]], errors="coerce")
        if lc["is_active"] and lc["is_active"] in active.columns:
            active = active[pd.to_numeric(active[lc["is_active"]], errors="coerce").fillna(1).astype(int) == 1]
        team_players = active[active[lc["team_id"]] == sel_row["team_id"]].merge(players, left_on=lc["player_id"], right_on=pc["player_id"], how="left")
    else:
        team_players = pd.DataFrame()
    cols = [c for c in ["player_name", "position", "slot", "pts", "trb", "ast", "stl", "blk", "three_p", "tov", "fantasy_value"] if c in team_players.columns]
    st.dataframe(display_table(team_players, cols), use_container_width=True)

elif view == "Banco":
    bc, pc = team_cols(bench), team_cols(players)
    if not bench.empty and bc["team_id"] and bc["player_id"]:
        b = bench.copy()
        b[bc["team_id"]] = pd.to_numeric(b[bc["team_id"]], errors="coerce")
        b[bc["player_id"]] = pd.to_numeric(b[bc["player_id"]], errors="coerce")
        team_bench = b[b[bc["team_id"]] == sel_row["team_id"]].merge(players, left_on=bc["player_id"], right_on=pc["player_id"], how="left")
    else:
        team_bench = pd.DataFrame()
    cols = [c for c in ["player_name", "position", "bench_order", "pts", "trb", "ast", "stl", "blk", "three_p", "tov", "fantasy_value"] if c in team_bench.columns]
    st.dataframe(display_table(team_bench, cols), use_container_width=True)

elif view == "Cenários":
    st.subheader("Cenários")
    if scenarios.empty:
        st.info("Nenhum cenário cadastrado.")
    else:
        cols = [c for c in ["scenario_id", "scenario_name", "team_id", "move_type", "description", "created_at", "is_active"] if c in scenarios.columns]
        st.dataframe(scenarios[cols], use_container_width=True)
    if not scenario_lineup.empty:
        st.markdown("### scenario_lineup_active")
        st.dataframe(scenario_lineup, use_container_width=True)
    if not scenario_bench.empty:
        st.markdown("### scenario_bench")
        st.dataframe(scenario_bench, use_container_width=True)
    if not scenario_moves.empty:
        st.markdown("### scenario_moves")
        st.dataframe(scenario_moves, use_container_width=True)

else:
    st.subheader("Sugestão de troca")
    lv = display_table(lineup, [c for c in ["player_name", "position", "slot", "pts", "trb", "ast", "stl", "blk", "three_p", "tov", "fantasy_value"] if c in lineup.columns])
    bv = display_table(bench, [c for c in ["player_name", "position", "bench_order", "pts", "trb", "ast", "stl", "blk", "three_p", "tov", "fantasy_value"] if c in bench.columns])
    pool = player_pool(players, sel_row["team_id"])
    st.info("A próxima etapa pode refinar a sugestão de troca sem mexer nas abas de cenário.")
    st.dataframe(display_table(pool, [c for c in ["player_name", "team_id", "position", "fantasy_value"] if c in pool.columns]).sort_values("fantasy_value", ascending=False).head(20), use_container_width=True)
