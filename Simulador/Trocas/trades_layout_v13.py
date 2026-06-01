import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

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
        k: load_sheet(xls, sheets.get(k if k != 'lineup' else 'lineup_active', ''))
        for k in ['players', 'teams', 'lineup', 'bench', 'scenarios', 'scenario_lineup', 'scenario_bench', 'scenario_moves']
    }


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


def team_cols(df):
    return {
        "team_id": first_col(df, ["team_id", "teamid"]),
        "team_name": first_col(df, ["team_name", "teamname"]),
        "player_id": first_col(df, ["player_id", "playerid"]),
        "player_name": first_col(df, ["player_name", "name"]),
        "slot": first_col(df, ["slot"]),
        "bench_order": first_col(df, ["bench_order", "benchorder"]),
        "is_active": first_col(df, ["is_active", "isactive"]),
    }


def calc_team_table(players, teams, lineup):
    tc, lc, pc = team_cols(teams), team_cols(lineup), team_cols(players)
    t = teams.copy()
    for c in STAT_COLS:
        if c not in t.columns:
            t[c] = np.nan
    if tc["team_id"] is None or tc["team_name"] is None or lc["team_id"] is None or lc["player_id"] is None or pc["player_id"] is None:
        return t
    t["team_id"] = pd.to_numeric(t[tc["team_id"]], errors="coerce")
    l = lineup.copy()
    p = players.copy()
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


def matchup_score(a, b, cols=STAT_COLS):
    score = 0
    for c in cols:
        av, bv = a.get(c, np.nan), b.get(c, np.nan)
        if pd.isna(av) or pd.isna(bv):
            continue
        score += int(av < bv) if c == "tov" else int(av > bv)
    return score


def matchup_detail(a, b, cols=STAT_COLS):
    rows = []
    for c in cols:
        av, bv = a.get(c, np.nan), b.get(c, np.nan)
        if pd.isna(av) or pd.isna(bv):
            result = "NA"
        elif c == "tov":
            result = "W" if av < bv else "L" if av > bv else "T"
        else:
            result = "W" if av > bv else "L" if av < bv else "T"
        rows.append({"Categoria": STAT_LABELS[c], "Time A": av, "Time B": bv, "Resultado": result})
    return pd.DataFrame(rows)


def matchup_matrix(teams_calc):
    valid = teams_calc[teams_calc["team_id"] != 15].dropna(subset=STAT_COLS).copy()
    if valid.empty:
        return pd.DataFrame()
    valid = valid.set_index("team_name")
    mat = pd.DataFrame(index=valid.index, columns=valid.index, dtype=float)
    for a in valid.index:
        for b in valid.index:
            if a == b:
                mat.loc[a, b] = np.nan
            else:
                mat.loc[a, b] = matchup_score(valid.loc[a], valid.loc[b])
    return mat


def matchup_ranking(teams_calc):
    valid = teams_calc[teams_calc["team_id"] != 15].dropna(subset=STAT_COLS).copy()
    if valid.empty:
        return pd.DataFrame()
    rows = []
    for _, a in valid.iterrows():
        wins = losses = ties = 0
        for _, b in valid.iterrows():
            if a["team_id"] == b["team_id"]:
                continue
            score = matchup_score(a, b)
            if score > len(STAT_COLS) / 2:
                wins += 1
            elif score < len(STAT_COLS) / 2:
                losses += 1
            else:
                ties += 1
        points = wins + ties * 0.5
        total = max(len(valid) - 1, 1)
        rows.append({"team_id": a["team_id"], "team_name": a["team_name"], "wins": wins, "losses": losses, "ties": ties, "strength": points / total})
    return pd.DataFrame(rows).sort_values(["strength", "wins"], ascending=[False, False]).reset_index(drop=True)


def matchup_strengths(teams_calc):
    valid = teams_calc[teams_calc["team_id"] != 15].dropna(subset=STAT_COLS)
    if valid.empty:
        return pd.DataFrame()
    out = []
    for _, a in valid.iterrows():
        score = 0
        for _, b in valid.iterrows():
            if a["team_id"] == b["team_id"]:
                continue
            score += matchup_score(a, b)
        out.append({"team_id": a["team_id"], "strength": score / max(len(valid) - 1, 1)})
    return pd.DataFrame(out)


def team_correlation_matrix(team_players):
    cols = [c for c in STAT_COLS if c in team_players.columns]
    if len(cols) < 2:
        return pd.DataFrame()
    return team_players[cols].corr(method="pearson")


def display_table(df, cols):
    return df[[c for c in cols if c in df.columns]].copy() if not df.empty else pd.DataFrame()


def roster_needs(team_players, teams_df):
    if team_players.empty:
        return pd.DataFrame()
    stat_cols = [c for c in STAT_COLS if c in teams_df.columns]
    if not stat_cols:
        return pd.DataFrame()
    team_sums = {}
    for c in stat_cols:
        team_sums[c] = pd.to_numeric(team_players[c], errors='coerce').sum() if c in team_players.columns else np.nan
    rows = []
    valid = teams_df.dropna(subset=stat_cols).copy()
    for c in stat_cols:
        val = team_sums.get(c, np.nan)
        series = pd.to_numeric(valid[c], errors='coerce').dropna() if c in valid.columns else pd.Series(dtype=float)
        if pd.isna(val) or series.empty:
            rows.append({'Categoria': c.upper().replace('THREE_P', '3PT'), 'Valor': val, 'Games': 0, 'Wins': 0, 'Losses': 0, 'relative_strength': np.nan, 'need': np.nan})
            continue
        if c == 'tov':
            wins = int((series > val).sum())
            losses = int((series < val).sum())
        else:
            wins = int((series < val).sum())
            losses = int((series > val).sum())
        games = int(len(series))
        denom = max(games - 1, 1)
        relative_strength = (wins / denom) * 100
        need = 100 - relative_strength
        rows.append({'Categoria': c.upper().replace('THREE_P', '3PT'), 'Valor': val, 'Games': games, 'Wins': wins, 'Losses': losses, 'relative_strength': relative_strength, 'need': need})
    return pd.DataFrame(rows).sort_values('need', ascending=False)


def player_pool(df, exclude_team=None):
    if df.empty:
        return df
    if "team_id" not in df.columns or exclude_team is None:
        return df
    return df[(df["team_id"].isna()) | (df["team_id"] != exclude_team)]


def trade_package_summary(out_rows, in_rows):
    out_sum = {c: pd.to_numeric(out_rows[c], errors="coerce").fillna(0).sum() if c in out_rows.columns else 0 for c in STAT_COLS}
    in_sum = {c: pd.to_numeric(in_rows[c], errors="coerce").fillna(0).sum() if c in in_rows.columns else 0 for c in STAT_COLS}
    return out_sum, in_sum


def apply_trade_totals(current, out_rows, in_rows, n):
    out_sum, in_sum = trade_package_summary(out_rows, in_rows)
    return {
        "pts": current["pts"] + (in_sum["pts"] - out_sum["pts"]) / n,
        "trb": current["trb"] + (in_sum["trb"] - out_sum["trb"]) / n,
        "ast": current["ast"] + (in_sum["ast"] - out_sum["ast"]) / n,
        "stl": current["stl"] + (in_sum["stl"] - out_sum["stl"]) / n,
        "blk": current["blk"] + (in_sum["blk"] - out_sum["blk"]) / n,
        "three_p": current["three_p"] + (in_sum["three_p"] - out_sum["three_p"]) / n,
        "tov": current["tov"] + (in_sum["tov"] - out_sum["tov"]) / n,
    }


def compare_trade_teams(current, new):
    rows = []
    for c in STAT_COLS:
        rows.append({
            "Categoria": STAT_LABELS[c],
            "Antes": current.get(c, np.nan),
            "Depois": new.get(c, np.nan),
            "Delta": new.get(c, np.nan) - current.get(c, np.nan) if pd.notna(current.get(c, np.nan)) and pd.notna(new.get(c, np.nan)) else np.nan,
        })
    return pd.DataFrame(rows)


def compare_players(out_rows, in_rows):
    out_sum, in_sum = trade_package_summary(out_rows, in_rows)
    fig = go.Figure()
    fig.add_trace(go.Bar(name="Saindo", x=[STAT_LABELS[c] for c in STAT_COLS], y=[out_sum[c] for c in STAT_COLS], marker_color="#E45756"))
    fig.add_trace(go.Bar(name="Entrando", x=[STAT_LABELS[c] for c in STAT_COLS], y=[in_sum[c] for c in STAT_COLS], marker_color="#72B7B2"))
    fig.update_layout(barmode="group", title="Pacote saindo vs entrando", height=400)
    return fig


def get_team_lineup(team_id, lineup, players):
    lc, pc = team_cols(lineup), team_cols(players)
    if lineup.empty or lc["team_id"] is None or lc["player_id"] is None or pc["player_id"] is None:
        return pd.DataFrame()
    active = lineup.copy()
    active[lc["team_id"]] = pd.to_numeric(active[lc["team_id"]], errors="coerce")
    active[lc["player_id"]] = pd.to_numeric(active[lc["player_id"]], errors="coerce")
    if lc["is_active"] and lc["is_active"] in active.columns:
        active = active[pd.to_numeric(active[lc["is_active"]], errors="coerce").fillna(1).astype(int) == 1]
    return active[active[lc["team_id"]] == team_id].merge(players, left_on=lc["player_id"], right_on=pc["player_id"], how="left")


def get_team_bench(team_id, bench, players):
    bc, pc = team_cols(bench), team_cols(players)
    if bench.empty or bc["team_id"] is None or bc["player_id"] is None or pc["player_id"] is None:
        return pd.DataFrame()
    b = bench.copy()
    b[bc["team_id"]] = pd.to_numeric(b[bc["team_id"]], errors="coerce")
    b[bc["player_id"]] = pd.to_numeric(b[bc["player_id"]], errors="coerce")
    return b[b[bc["team_id"]] == team_id].merge(players, left_on=bc["player_id"], right_on=pc["player_id"], how="left")


def get_top_need_categories(need_df, top_k=3):
    if need_df.empty or 'Categoria' not in need_df.columns:
        return []
    return need_df.sort_values('need', ascending=False)['Categoria'].astype(str).head(top_k).tolist()


def level_similarity_ok(out_row, in_row, enabled):
    if not enabled:
        return True
    tier_cols = [c for c in ["tier_valor", "tiervalor", "tier"] if c in out_row.index and c in in_row.index]
    if tier_cols:
        col = tier_cols[0]
        out_tier = str(out_row.get(col, "")).strip()
        in_tier = str(in_row.get(col, "")).strip()
        if out_tier and in_tier:
            return out_tier == in_tier
    out_fv = pd.to_numeric(pd.Series([out_row.get("fantasy_value", np.nan)]), errors="coerce").iloc[0]
    in_fv = pd.to_numeric(pd.Series([in_row.get("fantasy_value", np.nan)]), errors="coerce").iloc[0]
    if pd.isna(out_fv) or pd.isna(in_fv):
        return True
    threshold = max(3.0, abs(out_fv) * 0.15)
    return abs(in_fv - out_fv) <= threshold


def build_trade_finder_results(team_id, team_name, teams_calc, lineup_df, bench_df, players, include_bench=False, same_position=True, level_similar=True, limit=10, pos_filter="Todas"):
    roster_frames = [lineup_df]
    if include_bench and not bench_df.empty:
        roster_frames.append(bench_df)
    roster = pd.concat([df for df in roster_frames if not df.empty], ignore_index=True) if roster_frames else pd.DataFrame()
    if roster.empty:
        return pd.DataFrame(), pd.DataFrame()

    roster = roster.copy().drop_duplicates(subset=[c for c in ["player_id", "player_name"] if c in roster.columns])
    if pos_filter != "Todas" and "position" in roster.columns:
        roster = roster[roster["position"].astype(str) == str(pos_filter)]
    if roster.empty:
        return pd.DataFrame(), pd.DataFrame()

    pool = player_pool(players, team_id).copy()
    pool = pool[pool["team_id"] != 15] if "team_id" in pool.columns else pool
    if pos_filter != "Todas" and "position" in pool.columns:
        pool = pool[pool["position"].astype(str) == str(pos_filter)]
    if pool.empty:
        return pd.DataFrame(), pd.DataFrame()

    current = {c: pd.to_numeric(pd.Series([teams_calc.loc[teams_calc["team_id"] == team_id, c].iloc[0] if not teams_calc.loc[teams_calc["team_id"] == team_id].empty else np.nan]), errors="coerce").iloc[0] for c in STAT_COLS}
    opps = teams_calc[(teams_calc["team_id"] != team_id) & (teams_calc["team_id"] != 15)].dropna(subset=STAT_COLS).copy()
    old_m = float(np.mean([matchup_score(pd.Series(current), opp) for _, opp in opps.iterrows()])) if not opps.empty else np.nan
    need_df = roster_needs(get_team_lineup(team_id, lineup, players), teams_calc)
    top_needs = get_top_need_categories(need_df, top_k=3)
    n = max(len(get_team_lineup(team_id, lineup, players)), 1)

    rows = []
    for _, out_row in roster.iterrows():
        out_name = out_row.get("player_name", "NA")
        out_pos = str(out_row.get("position", "NA"))
        source = "Banco" if (not bench_df.empty and "player_id" in out_row.index and "player_id" in bench_df.columns and int(pd.to_numeric(pd.Series([out_row.get('player_id', np.nan)]), errors='coerce').fillna(-1).iloc[0]) in set(pd.to_numeric(bench_df['player_id'], errors='coerce').dropna().astype(int).tolist())) else "Lineup"
        for _, in_row in pool.iterrows():
            if same_position and "position" in out_row.index and "position" in in_row.index:
                if str(out_row.get("position", "")) != str(in_row.get("position", "")):
                    continue
            if not level_similarity_ok(out_row, in_row, level_similar):
                continue
            partner_team_id = in_row.get("team_id", np.nan)
            partner_team_name = "NA"
            if "team_id" in teams_calc.columns and "team_name" in teams_calc.columns and pd.notna(partner_team_id):
                match = teams_calc[teams_calc["team_id"] == partner_team_id]
                if not match.empty:
                    partner_team_name = match.iloc[0]["team_name"]
            out_rows = pd.DataFrame([out_row])
            in_rows = pd.DataFrame([in_row])
            new = apply_trade_totals(current, out_rows, in_rows, n)
            new_m = float(np.mean([matchup_score(pd.Series(new), opp) for _, opp in opps.iterrows()])) if not opps.empty else np.nan
            impact_df = compare_trade_teams(current, new)
            improved = impact_df.copy()
            improved["Impacto_positivo"] = improved.apply(lambda r: (r["Delta"] < 0) if r["Categoria"] == "TOV" else (r["Delta"] > 0), axis=1)
            improved_cats = improved[improved["Impacto_positivo"]]["Categoria"].astype(str).tolist()
            need_gain = sum(1 for c in improved_cats if c in top_needs)
            rows.append({
                "jogador_saindo": out_name,
                "origem_saida": source,
                "jogador_entrando": in_row.get("player_name", "NA"),
                "time_parceiro": partner_team_name,
                "pos_out": out_pos,
                "pos_in": in_row.get("position", "NA"),
                "fantasy_out": pd.to_numeric(pd.Series([out_row.get("fantasy_value", np.nan)]), errors="coerce").iloc[0],
                "fantasy_in": pd.to_numeric(pd.Series([in_row.get("fantasy_value", np.nan)]), errors="coerce").iloc[0],
                "antes": old_m,
                "depois": new_m,
                "delta_matchup": new_m - old_m if pd.notna(old_m) and pd.notna(new_m) else np.nan,
                "ganhos_categorias": len(improved_cats),
                "ganhos_need": need_gain,
                "categorias_melhoradas": ", ".join(improved_cats),
                "delta_pts": float(impact_df.loc[impact_df["Categoria"] == "PTS", "Delta"].iloc[0]) if not impact_df.loc[impact_df["Categoria"] == "PTS"].empty else np.nan,
                "delta_reb": float(impact_df.loc[impact_df["Categoria"] == "REB", "Delta"].iloc[0]) if not impact_df.loc[impact_df["Categoria"] == "REB"].empty else np.nan,
                "delta_ast": float(impact_df.loc[impact_df["Categoria"] == "AST", "Delta"].iloc[0]) if not impact_df.loc[impact_df["Categoria"] == "AST"].empty else np.nan,
                "delta_stl": float(impact_df.loc[impact_df["Categoria"] == "STL", "Delta"].iloc[0]) if not impact_df.loc[impact_df["Categoria"] == "STL"].empty else np.nan,
                "delta_blk": float(impact_df.loc[impact_df["Categoria"] == "BLK", "Delta"].iloc[0]) if not impact_df.loc[impact_df["Categoria"] == "BLK"].empty else np.nan,
                "delta_3pt": float(impact_df.loc[impact_df["Categoria"] == "3PT", "Delta"].iloc[0]) if not impact_df.loc[impact_df["Categoria"] == "3PT"].empty else np.nan,
                "delta_tov": float(impact_df.loc[impact_df["Categoria"] == "TOV", "Delta"].iloc[0]) if not impact_df.loc[impact_df["Categoria"] == "TOV"].empty else np.nan,
            })
    ranked = pd.DataFrame(rows)
    if ranked.empty:
        return ranked, need_df
    ranked = ranked.sort_values(["delta_matchup", "ganhos_need", "ganhos_categorias", "depois"], ascending=[False, False, False, False]).reset_index(drop=True)
    ranked = ranked.drop_duplicates(subset=["jogador_saindo", "jogador_entrando"]).head(limit)
    return ranked, need_df


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

st.title("Fantasy NBA Dashboard v13")

if teams_calc.empty or teamc["team_name"] is None:
    st.error("Não foi possível carregar os times.")
    st.stop()

team_list = teams_calc.loc[teams_calc["team_id"] != 15, teamc["team_name"]].fillna("NA").tolist()
sel_team = st.sidebar.selectbox("Time", team_list)
sel_row = teams_calc[teams_calc[teamc["team_name"]].fillna("NA") == sel_team].iloc[0]
team_id = int(sel_row["team_id"])
view = st.sidebar.radio("Visão", ["Resumo", "Ranking", "Elenco", "Cenários", "Matchups", "Simulador", "Trade Finder"])

team_lineup = get_team_lineup(team_id, lineup, players)
team_bench = get_team_bench(team_id, bench, players)

if view == "Resumo":
    cols = st.columns(7)
    for col, stat in zip(cols, STAT_COLS):
        col.metric(STAT_LABELS[stat], f"{sel_row[stat]:.2f}" if pd.notna(sel_row[stat]) else "NA")
    ms = matchup_strengths(teams_calc)
    left, right = st.columns(2)
    with left:
        if not ms.empty and sel_row["team_id"] in ms.set_index("team_id").index:
            ms_plot = ms.merge(teams_calc[["team_id", teamc["team_name"]]], on="team_id", how="left").rename(columns={teamc["team_name"]: "team"}).sort_values("strength", ascending=False)
            st.plotly_chart(px.bar(ms_plot, x="team", y="strength", color="strength", title="Matchup win médio entre todos os times"), use_container_width=True)
    with right:
        corr = team_correlation_matrix(team_lineup)
        if not corr.empty:
            st.plotly_chart(px.imshow(corr.round(2), text_auto=True, color_continuous_scale="RdBu", zmin=-1, zmax=1, title=f"Correlação interna - {sel_team}"), use_container_width=True)

elif view == "Ranking":
    rk = []
    valid = teams_calc[teams_calc["team_id"] != 15].dropna(subset=STAT_COLS)
    for c in STAT_COLS:
        asc = c == "tov"
        order = valid[["team_id", c]].sort_values(c, ascending=asc).reset_index(drop=True)
        order["rank"] = np.arange(1, len(order) + 1)
        order["stat"] = c
        rk.append(order)
    rk = pd.concat(rk, ignore_index=True) if rk else pd.DataFrame()
    if rk.empty:
        st.info("Sem ranking disponível.")
    else:
        cat = st.selectbox("Categoria", [STAT_LABELS[c] for c in STAT_COLS])
        stat_key = {v: k for k, v in STAT_LABELS.items()}[cat]
        subset = rk[rk["stat"] == stat_key].merge(teams_calc[["team_id", teamc["team_name"]]], on="team_id", how="left")
        subset = subset.rename(columns={teamc["team_name"]: "team"})
        st.plotly_chart(px.bar(subset.sort_values("rank"), x="team", y=stat_key, color="rank", title=f"Ranking - {cat}"), use_container_width=True)

elif view == "Elenco":
    tab1, tab2, tab3 = st.tabs(["Titulares", "Banco", "Needs"])
    with tab1:
        cols = [c for c in ["player_name", "position", "slot", "pts", "trb", "ast", "stl", "blk", "three_p", "tov", "fantasy_value"] if c in team_lineup.columns]
        st.dataframe(display_table(team_lineup, cols), use_container_width=True)
    with tab2:
        cols = [c for c in ["player_name", "position", "bench_order", "pts", "trb", "ast", "stl", "blk", "three_p", "tov", "fantasy_value"] if c in team_bench.columns]
        st.dataframe(display_table(team_bench, cols), use_container_width=True)
    with tab3:
        need_df = roster_needs(team_lineup, teams_calc)
        if need_df.empty:
            st.info("Não foi possível calcular necessidades do elenco.")
        else:
            st.dataframe(need_df, use_container_width=True)
            st.plotly_chart(px.bar(need_df, x="Categoria", y="need", color="relative_strength", title=f"Necessidades do elenco - {sel_team}"), use_container_width=True)

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

elif view == "Matchups":
    st.subheader("Matchups")
    matrix = matchup_matrix(teams_calc)


    tm = teams_calc[teams_calc["team_name"].notna()].copy().set_index("team_name")
    mat = pd.DataFrame(index=tm.index, columns=tm.index)
    for a in tm.index:
        for b in tm.index:
            if a == b:
                mat.loc[a, b] = np.nan
            else:
                mat.loc[a, b] = matchup_score(tm.loc[a], tm.loc[b])
    
    fig = px.imshow(mat.astype(float), text_auto=True, aspect="auto", color_continuous_scale="Blues", title="Matriz de confrontos")
    fig.update_layout(height=700)
    st.plotly_chart(fig, use_container_width=True)

    if matrix.empty:
        st.info("Sem dados suficientes para montar a matriz.")
    else:
        teams_sel = teams_calc[teams_calc["team_id"] != 15].dropna(subset=["team_name"]).copy()
        rank = matchup_ranking(teams_calc)
        if not rank.empty:
            st.markdown("### Ranking de força")
            fig_rank = px.bar(rank.sort_values("strength", ascending=True), x="strength", y="team_name", orientation="h", color="strength", color_continuous_scale="Viridis", title="Força de matchup por time")
            fig_rank.update_layout(height=max(420, 28 * len(rank) + 120), yaxis_title="", xaxis_title="Força")
            st.plotly_chart(fig_rank, use_container_width=True)
            
        team_opts = teams_sel["team_name"].tolist()
        team_a_name = st.selectbox("Time A", team_opts, index=team_opts.index(sel_team) if sel_team in team_opts else 0)
        team_b_opts = [t for t in team_opts if t != team_a_name]
        team_b_name = st.selectbox("Time B", team_b_opts)
        row_a = teams_sel[teams_sel["team_name"] == team_a_name].iloc[0]
        row_b = teams_sel[teams_sel["team_name"] == team_b_name].iloc[0]
        detail = matchup_detail(row_a, row_b)
        st.markdown("### Detalhe por categoria")
        c1, c2, c3 = st.columns(3)
        c1.metric("Vitórias Time A", int((detail["Resultado"] == "W").sum()))
        c2.metric("Vitórias Time B", int((detail["Resultado"] == "L").sum()))
        c3.metric("Empates", int((detail["Resultado"] == "T").sum()))
        st.dataframe(detail, use_container_width=True)

elif view == "Simulador":
    st.subheader("Simulador de troca")
    multi_trade = st.toggle("Troca múltipla (2 por 2)", value=False)
    same_position = st.checkbox("Exigir mesma posição", value=True)
    include_bench_sim = st.checkbox("Incluir banco", value=False)

    roster_frames = [team_lineup]
    if include_bench_sim and not team_bench.empty:
        roster_frames.append(team_bench)
    eligible_out = pd.concat([df for df in roster_frames if not df.empty], ignore_index=True) if roster_frames else pd.DataFrame()

    pool = player_pool(players, team_id).copy()
    pool = pool[pool["team_id"] != 15] if "team_id" in pool.columns else pool

    team_positions = sorted(eligible_out["position"].dropna().astype(str).unique().tolist()) if not eligible_out.empty and "position" in eligible_out.columns else []
    pos_choice = st.selectbox("Filtro de posição", ["Todas"] + team_positions)

    if pos_choice != "Todas" and "position" in eligible_out.columns:
        eligible_out = eligible_out[eligible_out["position"].astype(str) == pos_choice]
    if pos_choice != "Todas" and "position" in pool.columns:
        pool = pool[pool["position"].astype(str) == pos_choice]

    if eligible_out.empty or pool.empty:
        st.warning("Sem jogadores suficientes com o filtro aplicado.")
        st.stop()

    if not multi_trade:
        out_name = st.selectbox("Saindo", eligible_out["player_name"].drop_duplicates().tolist(), key="out1")
        out_rows = eligible_out[eligible_out["player_name"] == out_name].drop_duplicates(subset=["player_name"])
        if same_position and "position" in eligible_out.columns and "position" in pool.columns:
            out_pos = out_rows["position"].iloc[0]
            pool_view = pool[pool["position"].astype(str) == str(out_pos)]
        else:
            pool_view = pool
        in_name = st.selectbox("Entrando", pool_view["player_name"].drop_duplicates().tolist(), key="in1")
        in_rows = pool_view[pool_view["player_name"] == in_name].drop_duplicates(subset=["player_name"])
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

    if same_position and "position" in out_rows.columns and "position" in in_rows.columns and len(out_rows) == len(in_rows):
        if sorted(out_rows["position"].astype(str).tolist()) != sorted(in_rows["position"].astype(str).tolist()):
            st.error("Troca inválida: as posições do pacote entrando não batem com as do pacote saindo.")
            st.stop()

    current = {c: pd.to_numeric(sel_row[c], errors="coerce") if c in sel_row.index else np.nan for c in STAT_COLS}
    n = max(len(team_lineup), 1)
    new = apply_trade_totals(current, out_rows, in_rows, n)
    impact_df = compare_trade_teams(current, new)

    st.plotly_chart(compare_players(out_rows, in_rows), use_container_width=True)
    st.markdown("### Impacto por categoria")
    st.dataframe(impact_df, use_container_width=True)
    st.plotly_chart(px.bar(impact_df, x="Categoria", y="Delta", color="Delta", title="Impacto total da troca"), use_container_width=True)

    st.markdown("### Pacote saindo vs entrando")
    c_left, c_right = st.columns(2)
    with c_left:
        st.markdown("### Pacote saindo")
        st.dataframe(out_rows[[c for c in ["player_name", "position", "fantasy_value", "tier_valor", "tiervalor"] + STAT_COLS if c in out_rows.columns]], use_container_width=True)
    with c_right:
        st.markdown("### Pacote entrando")
        st.dataframe(in_rows[[c for c in ["player_name", "position", "fantasy_value", "tier_valor", "tiervalor"] + STAT_COLS if c in in_rows.columns]], use_container_width=True)

    old_row = pd.Series({**current})
    new_row = pd.Series({**new})
    opps = teams_calc[(teams_calc["team_id"] != team_id) & (teams_calc["team_id"] != 15)].dropna(subset=STAT_COLS).copy() if not teams_calc.empty else pd.DataFrame()
    old_m = float(np.mean([matchup_score(old_row, opp) for _, opp in opps.iterrows()])) if not opps.empty else np.nan
    new_m = float(np.mean([matchup_score(new_row, opp) for _, opp in opps.iterrows()])) if not opps.empty else np.nan
    st.caption("Impacto médio da troca contra todos os outros times")
    m1, m2, m3 = st.columns(3)
    m1.metric("Matchup médio antes", f"{old_m:.2f}" if pd.notna(old_m) else "NA")
    m2.metric("Matchup médio depois", f"{new_m:.2f}" if pd.notna(new_m) else "NA")
    m3.metric("Delta", f"{new_m - old_m:.2f}" if pd.notna(old_m) and pd.notna(new_m) else "NA")

else:
    st.subheader("Trade Finder")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        same_position = st.checkbox("Apenas mesma posição", value=True)
    with c2:
        level_similar = st.checkbox("Apenas nível parecido", value=True)
    with c3:
        include_bench = st.checkbox("Incluir banco", value=False)
    with c4:
        limit = st.selectbox("Quantidade de sugestões", [5, 10, 15], index=1)

    pos_options = ["Todas"] + (sorted(pd.concat([team_lineup[["position"]], team_bench[["position"]]], ignore_index=True)["position"].dropna().astype(str).unique().tolist()) if (not team_lineup.empty or not team_bench.empty) and "position" in pd.concat([team_lineup, team_bench], ignore_index=True).columns else [])
    pos_filter = st.selectbox("Filtro de posição", pos_options)

    ranked, need_df = build_trade_finder_results(team_id, sel_team, teams_calc, team_lineup, team_bench, players, include_bench=include_bench, same_position=same_position, level_similar=level_similar, limit=limit, pos_filter=pos_filter)
    if ranked.empty:
        st.warning("Não foi possível gerar sugestões com os filtros atuais.")
        st.stop()

    st.markdown("### Top ganhos de matchup win")
    st.dataframe(ranked[[c for c in ["jogador_saindo", "origem_saida", "jogador_entrando", "time_parceiro", "pos_out", "pos_in", "antes", "depois", "delta_matchup", "ganhos_categorias", "ganhos_need", "categorias_melhoradas"] if c in ranked.columns]], use_container_width=True)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=ranked["jogador_entrando"],
        y=ranked["delta_matchup"],
        text=ranked["jogador_saindo"],
        marker_color=np.where(ranked["delta_matchup"] >= 0, "#2E8B57", "#C44E52"),
        hovertemplate="Entrando: %{x}<br>Saindo: %{text}<br>Delta matchup: %{y:.2f}<extra></extra>",
    ))
    fig.update_layout(title="Top ganhos de matchup win", xaxis_title="Jogador entrando", yaxis_title="Delta matchup", height=450)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Leitura de needs do elenco")
    if not need_df.empty:
        st.dataframe(need_df, use_container_width=True)

    detail_idx = st.selectbox("Abrir sugestão", ranked.index, format_func=lambda i: f"{ranked.loc[i, 'jogador_saindo']} → {ranked.loc[i, 'jogador_entrando']} ({ranked.loc[i, 'delta_matchup']:+.2f})")
    selected = ranked.loc[detail_idx]

    roster_frames = [team_lineup]
    if include_bench and not team_bench.empty:
        roster_frames.append(team_bench)
    eligible_out = pd.concat([df for df in roster_frames if not df.empty], ignore_index=True)
    out_rows = eligible_out[eligible_out["player_name"] == selected["jogador_saindo"]].head(1)
    in_rows = players[players["player_name"] == selected["jogador_entrando"]].head(1)

    current = {c: pd.to_numeric(sel_row[c], errors="coerce") if c in sel_row.index else np.nan for c in STAT_COLS}
    n = max(len(team_lineup), 1)
    new = apply_trade_totals(current, out_rows, in_rows, n)
    impact_df = compare_trade_teams(current, new)

    st.plotly_chart(compare_players(out_rows, in_rows), use_container_width=True)
    m1, m2, m3 = st.columns(3)
    m1.metric("Matchup médio antes", f"{selected['antes']:.2f}" if pd.notna(selected['antes']) else "NA")
    m2.metric("Matchup médio depois", f"{selected['depois']:.2f}" if pd.notna(selected['depois']) else "NA")
    m3.metric("Delta", f"{selected['delta_matchup']:+.2f}" if pd.notna(selected['delta_matchup']) else "NA")

    st.markdown("### Impacto por categoria")
    st.dataframe(impact_df, use_container_width=True)
    st.plotly_chart(px.bar(impact_df, x="Categoria", y="Delta", color="Delta", title="Impacto total da sugestão"), use_container_width=True)

    c_left, c_right = st.columns(2)
    with c_left:
        st.markdown("### Pacote saindo")
        st.dataframe(out_rows[[c for c in ["player_name", "position", "fantasy_value", "tier_valor", "tiervalor"] + STAT_COLS if c in out_rows.columns]], use_container_width=True)
    with c_right:
        st.markdown("### Pacote entrando")
        st.dataframe(in_rows[[c for c in ["player_name", "position", "fantasy_value", "tier_valor", "tiervalor"] + STAT_COLS if c in in_rows.columns]], use_container_width=True)
