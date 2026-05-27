import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime, timezone

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


def scenario_id_name_map(scenarios):
    sid = first_col(scenarios, ["scenario_id", "scenarioid"])
    sname = first_col(scenarios, ["scenario_name", "scenarioname"])
    if sid and sname and not scenarios.empty:
        return dict(zip(pd.to_numeric(scenarios[sid], errors="coerce"), scenarios[sname].astype(str)))
    return {}


def scenario_roster_for_team(scenario_id, team_id, scen_lineup, scen_bench, players):
    lineup_team_col = first_col(scen_lineup, ["team_id", "teamid"])
    lineup_pid_col = first_col(scen_lineup, ["player_id", "playerid"])
    bench_team_col = first_col(scen_bench, ["team_id", "teamid"])
    bench_pid_col = first_col(scen_bench, ["player_id", "playerid"])
    player_id_col = first_col(players, ["player_id", "playerid"])
    if lineup_team_col is None or lineup_pid_col is None:
        return pd.DataFrame(), pd.DataFrame()
    sl = scen_lineup.copy(); sb = scen_bench.copy()
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


def scenario_summary_line(sid, sname, team_name, lineup_df, bench_df, players):
    lineup_ids = pd.to_numeric(lineup_df["player_id"], errors="coerce").dropna().astype(int).tolist() if not lineup_df.empty and "player_id" in lineup_df.columns else []
    bench_ids = pd.to_numeric(bench_df["player_id"], errors="coerce").dropna().astype(int).tolist() if not bench_df.empty and "player_id" in bench_df.columns else []
    lineup_stats = team_stats(players[players["player_id"].isin(lineup_ids)]) if lineup_ids else {f"{c}_avg": np.nan for c in STAT_COLS}
    bench_stats = team_stats(players[players["player_id"].isin(bench_ids)]) if bench_ids else {f"{c}_avg": np.nan for c in STAT_COLS}
    return {"scenario_id": sid, "scenario_name": sname, "team_name": team_name, **lineup_stats, **{f"bench_{k}": v for k, v in bench_stats.items()}}


def scenario_vs_current(lineup_current, bench_current, scenario_lineup, scenario_bench, players):
    cur_lineup_ids = pd.to_numeric(lineup_current["player_id"], errors="coerce").dropna().astype(int).tolist() if not lineup_current.empty and "player_id" in lineup_current.columns else []
    scen_lineup_ids = pd.to_numeric(scenario_lineup["player_id"], errors="coerce").dropna().astype(int).tolist() if not scenario_lineup.empty and "player_id" in scenario_lineup.columns else []
    cur_roster = players[players["player_id"].isin(cur_lineup_ids)]
    scen_roster = players[players["player_id"].isin(scen_lineup_ids)]
    cur_stats = team_stats(cur_roster)
    scen_stats = team_stats(scen_roster)
    return pd.DataFrame([{"metric": k.replace("_avg", ""), "current": cur_stats[k], "scenario": scen_stats[k], "delta": scen_stats[k] - cur_stats[k] if pd.notna(cur_stats[k]) and pd.notna(scen_stats[k]) else np.nan} for k in AVG_COLS])


def generate_move_suggestions(lineup_df, bench_df):
    if lineup_df.empty or bench_df.empty or "fantasy_value" not in lineup_df.columns or "fantasy_value" not in bench_df.columns:
        return pd.DataFrame()
    suggestions = []
    for _, out_row in lineup_df.iterrows():
        candidates = bench_df.copy()
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
    return pd.DataFrame(suggestions)


def to_iso_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def save_scenario(scenarios_df, scen_lineup_df, scen_bench_df, scen_moves_df, team_id, move_type, description, lineup_df, bench_df, selected_scenario_id=None, player_out_id=None, player_in_id=None, notes=""):
    scenarios_df = scenarios_df.copy()
    scen_lineup_df = scen_lineup_df.copy()
    scen_bench_df = scen_bench_df.copy()
    scen_moves_df = scen_moves_df.copy()
    sid_col = first_col(scenarios_df, ["scenario_id", "scenarioid"]) or "scenario_id"
    sc_team_col = first_col(scenarios_df, ["team_id", "teamid"]) or "team_id"
    sc_move_col = first_col(scenarios_df, ["move_type", "movetype"]) or "move_type"
    sc_desc_col = first_col(scenarios_df, ["description"] ) or "description"
    sc_created_col = first_col(scenarios_df, ["created_at", "createdat"]) or "created_at"
    sc_active_col = first_col(scenarios_df, ["is_active", "isactive"]) or "is_active"

    if selected_scenario_id is None:
        next_id = int(pd.to_numeric(scenarios_df[sid_col], errors="coerce").max() + 1) if not scenarios_df.empty and sid_col in scenarios_df.columns else 1
        selected_scenario_id = next_id
        new_row = {sid_col: selected_scenario_id, sc_team_col: team_id, sc_move_col: move_type, sc_desc_col: description, sc_created_col: to_iso_now(), sc_active_col: 1}
        scenarios_df = pd.concat([scenarios_df, pd.DataFrame([new_row])], ignore_index=True)
    else:
        if sc_team_col in scenarios_df.columns:
            scenarios_df.loc[pd.to_numeric(scenarios_df[sid_col], errors="coerce") == selected_scenario_id, sc_team_col] = team_id
        if sc_move_col in scenarios_df.columns:
            scenarios_df.loc[pd.to_numeric(scenarios_df[sid_col], errors="coerce") == selected_scenario_id, sc_move_col] = move_type
        if sc_desc_col in scenarios_df.columns:
            scenarios_df.loc[pd.to_numeric(scenarios_df[sid_col], errors="coerce") == selected_scenario_id, sc_desc_col] = description
        if sc_active_col in scenarios_df.columns:
            scenarios_df.loc[pd.to_numeric(scenarios_df[sid_col], errors="coerce") == selected_scenario_id, sc_active_col] = 1

    sl_team_col = first_col(scen_lineup_df, ["team_id", "teamid"]) or "team_id"
    sl_sid_col = first_col(scen_lineup_df, ["scenario_id", "scenarioid"]) or "scenario_id"
    sb_team_col = first_col(scen_bench_df, ["team_id", "teamid"]) or "team_id"
    sb_sid_col = first_col(scen_bench_df, ["scenario_id", "scenarioid"]) or "scenario_id"
    scen_lineup_df = scen_lineup_df[~((pd.to_numeric(scen_lineup_df.get(sl_sid_col, pd.Series(dtype=float)), errors="coerce") == selected_scenario_id) & (pd.to_numeric(scen_lineup_df.get(sl_team_col, pd.Series(dtype=float)), errors="coerce") == team_id))].copy() if not scen_lineup_df.empty else scen_lineup_df
    scen_bench_df = scen_bench_df[~((pd.to_numeric(scen_bench_df.get(sb_sid_col, pd.Series(dtype=float)), errors="coerce") == selected_scenario_id) & (pd.to_numeric(scen_bench_df.get(sb_team_col, pd.Series(dtype=float)), errors="coerce") == team_id))].copy() if not scen_bench_df.empty else scen_bench_df

    lineup_save = lineup_df.copy()
    bench_save = bench_df.copy()
    lineup_save.insert(0, sl_sid_col, selected_scenario_id)
    lineup_save.insert(1, sl_team_col, team_id)
    bench_save.insert(0, sb_sid_col, selected_scenario_id)
    bench_save.insert(1, sb_team_col, team_id)
    scen_lineup_df = pd.concat([scen_lineup_df, lineup_save], ignore_index=True)
    scen_bench_df = pd.concat([scen_bench_df, bench_save], ignore_index=True)

    move_cols = [c for c in ["scenario_id", "move_id", "move_type", "player_out_id", "player_in_id", "timestamp", "notes"] if c in scen_moves_df.columns] or ["scenario_id", "move_id", "move_type", "player_out_id", "player_in_id", "timestamp", "notes"]
    next_move_id = int(pd.to_numeric(scen_moves_df.get("move_id", pd.Series(dtype=float)), errors="coerce").max() + 1) if not scen_moves_df.empty and "move_id" in scen_moves_df.columns else 1
    scen_moves_df = pd.concat([scen_moves_df, pd.DataFrame([{"scenario_id": selected_scenario_id, "move_id": next_move_id, "move_type": move_type, "player_out_id": player_out_id, "player_in_id": player_in_id, "timestamp": to_iso_now(), "notes": notes}])], ignore_index=True)
    return scenarios_df, scen_lineup_df, scen_bench_df, scen_moves_df, selected_scenario_id


def export_excel(scenarios_df, scen_lineup_df, scen_bench_df, scen_moves_df):
    out_path = Path('/home/user/output/scenarios_export.xlsx')
    with pd.ExcelWriter(out_path, engine='openpyxl') as writer:
        scenarios_df.to_excel(writer, sheet_name='scenarios', index=False)
        scen_lineup_df.to_excel(writer, sheet_name='scenario_lineup_active', index=False)
        scen_bench_df.to_excel(writer, sheet_name='scenario_bench', index=False)
        scen_moves_df.to_excel(writer, sheet_name='scenario_moves', index=False)
    return out_path


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
scenario_map = scenario_id_name_map(scenarios)

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
    st.subheader("Criar ou abrir cenário")
    if scenarios.empty:
        st.info("Nenhum cenário cadastrado ainda.")
    else:
        sid_col = scenario_id_col or "scenario_id"
        sname_col = scenario_name_col or "scenario_name"
        display_cols = [c for c in [sid_col, sname_col, scenario_team_col, "move_type", "description", "created_at", "is_active"] if c in scenarios.columns]
        st.dataframe(scenarios[display_cols], use_container_width=True)
    valid_ids = [int(x) for x in pd.to_numeric(scenarios[scenario_id_col], errors='coerce').dropna().astype(int).tolist()] if scenario_id_col in scenarios.columns and not scenarios.empty else []
    mode = st.radio("Ação", ["Novo cenário", "Editar cenário existente"], horizontal=True)
    selected_sid = None
    if mode == "Editar cenário existente" and valid_ids:
        selected_sid = st.selectbox("Cenário", valid_ids, format_func=lambda x: scenario_map.get(x, str(x)))
    scenario_team = team_id
    base_lineup = lineup_view(team_id, lineup, players)
    base_bench = bench_view(team_id, bench, players)
    if mode == "Editar cenário existente" and selected_sid is not None and scenario_team_col in scenarios.columns:
        row = scenarios[pd.to_numeric(scenarios[scenario_id_col], errors='coerce') == selected_sid].iloc[0]
        scenario_team = int(row[scenario_team_col]) if pd.notna(row.get(scenario_team_col, np.nan)) else team_id
        base_lineup, base_bench = scenario_roster_for_team(selected_sid, scenario_team, scen_lineup, scen_bench, players)
    st.markdown("### Lineup atual do time")
    st.dataframe(base_lineup[[c for c in ["player_id", "player_name", "position", "slot", "fantasy_value"] if c in base_lineup.columns]], use_container_width=True)
    st.markdown("### Banco atual do time")
    st.dataframe(base_bench[[c for c in ["player_id", "player_name", "position", "bench_order", "fantasy_value"] if c in base_bench.columns]], use_container_width=True)
    out_options = base_lineup[[c for c in ["player_id", "player_name"] if c in base_lineup.columns]].dropna().copy() if not base_lineup.empty else pd.DataFrame()
    in_options = base_bench[[c for c in ["player_id", "player_name"] if c in base_bench.columns]].dropna().copy() if not base_bench.empty else pd.DataFrame()
    player_out_id = None
    player_in_id = None
    if not out_options.empty:
        out_label = st.selectbox("Sairá do lineup", out_options.index.tolist(), format_func=lambda i: f"{int(out_options.loc[i, 'player_id'])} - {out_options.loc[i, 'player_name']}")
        player_out_id = int(out_options.loc[out_label, 'player_id'])
    if not in_options.empty:
        in_label = st.selectbox("Entrará do banco", in_options.index.tolist(), format_func=lambda i: f"{int(in_options.loc[i, 'player_id'])} - {in_options.loc[i, 'player_name']}")
        player_in_id = int(in_options.loc[in_label, 'player_id'])
    move_type = st.selectbox("Tipo de movimento", ["swap", "injury", "rest", "projection", "manual"])
    description = st.text_input("Nome / descrição do cenário", value=f"Cenário {team_sel}")
    notes = st.text_area("Notas do movimento", value="")
    if st.button("Salvar cenário"):
        for df_name, df in [("lineup", base_lineup), ("bench", base_bench)]:
            if "player_id" not in df.columns:
                st.error(f"{df_name} precisa ter player_id.")
                st.stop()
        new_scenarios, new_sl, new_sb, new_sm, saved_sid = save_scenario(
            scenarios, scen_lineup, scen_bench, scen_moves, team_id, move_type, description, base_lineup, base_bench,
            selected_scenario_id=selected_sid, player_out_id=player_out_id, player_in_id=player_in_id, notes=notes
        )
        export_path = export_excel(new_scenarios, new_sl, new_sb, new_sm)
        st.success(f"Cenário salvo com ID {saved_sid}.")
        st.info(f"Arquivo exportado em {export_path}")
    if not scenarios.empty and valid_ids:
        open_sid = st.selectbox("Abrir comparação", valid_ids, key='open_compare', format_func=lambda x: scenario_map.get(x, str(x)))
        row = scenarios[pd.to_numeric(scenarios[scenario_id_col], errors='coerce') == open_sid].iloc[0]
        scenario_team = int(row[scenario_team_col]) if scenario_team_col in scenarios.columns and pd.notna(row.get(scenario_team_col, np.nan)) else team_id
        slv, sbv = scenario_roster_for_team(open_sid, scenario_team, scen_lineup, scen_bench, players)
        cmp_df = scenario_vs_current(lineup_view(scenario_team, lineup, players), bench_view(scenario_team, bench, players), slv, sbv, players)
        st.markdown("### Comparação cenário vs atual")
        st.dataframe(cmp_df, use_container_width=True)
        st.plotly_chart(px.bar(cmp_df, x="metric", y="delta", title="Diferença do cenário vs atual"), use_container_width=True)

else:
    st.subheader("Sugestão de troca")
    lv = lineup_view(team_id, lineup, players)
    bv = bench_view(team_id, bench, players)
    if lv.empty or bv.empty:
        st.info("Precisa de lineup e banco preenchidos para gerar sugestão.")
    else:
        sug = generate_move_suggestions(lv, bv)
        if sug.empty:
            st.info("Nenhuma sugestão encontrada.")
        else:
            st.dataframe(sug, use_container_width=True)
            st.plotly_chart(px.bar(sug, x="out", y="delta", color="delta", title="Impacto estimado da melhor troca por titular"), use_container_width=True)
