import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

from app_streamlit_v7 import compare_players

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
    return {k: load_sheet(xls, sheets.get(k if k != 'lineup' else 'lineup_active', '')) for k in ['players','teams','lineup','bench','scenarios','scenario_lineup','scenario_bench','scenario_moves']}


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
    valid = teams_calc[teams_calc["team_id"] != 15].copy()
    if valid.empty or "team_name" not in valid.columns:
        return pd.DataFrame()
    valid = valid.set_index("team_name")
    for c in STAT_COLS:
        if c not in valid.columns:
            valid[c] = np.nan
    valid = valid[STAT_COLS].apply(pd.to_numeric, errors="coerce").fillna(0)
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
        src = c.replace('_avg', '')
        team_sums[c] = pd.to_numeric(team_players[src], errors='coerce').sum() if src in team_players.columns else np.nan 
    rows = []
    valid = teams_df.dropna(subset=stat_cols).copy()
    for c in stat_cols:
        val = team_sums.get(c, np.nan)
        series = pd.to_numeric(valid[c], errors='coerce').dropna() if c in valid.columns else pd.Series(dtype=float)
        if pd.isna(val) or series.empty:
            rows.append({'Categoria': c.replace('_avg','').upper(), 'Valor': val, 'Games': 0, 'Wins': 0, 'Losses': 0, 'relative_strength': np.nan, 'need': np.nan})
            continue
        if c == 'tov_avg':
            wins = int((series > val).sum())
            losses = int((series < val).sum())
        else:
            wins = int((series < val).sum())
            losses = int((series > val).sum())
        games = int(len(series))
        denom = max(games - 1, 1)
        relative_strength = (wins / denom) * 100
        need = 100 - relative_strength
        rows.append({'Categoria': c.replace('_avg','').upper(), 'Valor': val, 'Games': games, 'Wins': wins, 'Losses': losses, 'relative_strength': relative_strength, 'need': need})
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
        rows.append({"Categoria": STAT_LABELS[c], "Antes": current.get(c, np.nan), "Depois": new.get(c, np.nan), "Delta": new.get(c, np.nan) - current.get(c, np.nan) if pd.notna(current.get(c, np.nan)) and pd.notna(new.get(c, np.nan)) else np.nan})
    return pd.DataFrame(rows)


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
view = st.sidebar.radio("Visão", ["Resumo", "Ranking", "Elenco", "Banco", "Cenários", "Matchups", "Simulador", "Sugestão de troca"])

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
        lc, pc = team_cols(lineup), team_cols(players)
        team_players = pd.DataFrame()
        if not lineup.empty and lc["team_id"] and lc["player_id"]:
            active = lineup.copy()
            active[lc["team_id"]] = pd.to_numeric(active[lc["team_id"]], errors="coerce")
            active[lc["player_id"]] = pd.to_numeric(active[lc["player_id"]], errors="coerce")
            if lc["is_active"] and lc["is_active"] in active.columns:
                active = active[pd.to_numeric(active[lc["is_active"]], errors="coerce").fillna(1).astype(int) == 1]
            team_players = active[active[lc["team_id"]] == sel_row["team_id"]].merge(players, left_on=lc["player_id"], right_on=pc["player_id"], how="left")
        corr = team_correlation_matrix(team_players)
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
    st.subheader("Elenco")
    st.dataframe(display_table(team_players, cols), use_container_width=True)
    st.subheader("Necessidades do elenco")
    need_df = roster_needs(team_players, teams_calc)
    if need_df.empty:
        st.info("Não foi possível calcular necessidades do elenco.")
    else:
        st.dataframe(need_df, use_container_width=True)
        st.plotly_chart(px.bar(need_df, x="Categoria", y="need", color="relative_strength", title=f"Necessidades do elenco - {sel_team}"), use_container_width=True)

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
        from plotly.colors import n_colors
        

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

    tc, lc, pc = team_cols(teams_calc), team_cols(lineup), team_cols(players)
    active = lineup.copy()
    if not active.empty and lc["team_id"] and lc["player_id"]:
        active[lc["team_id"]] = pd.to_numeric(active[lc["team_id"]], errors="coerce")
        active[lc["player_id"]] = pd.to_numeric(active[lc["player_id"]], errors="coerce")
        if lc["is_active"] and lc["is_active"] in active.columns:
            active = active[pd.to_numeric(active[lc["is_active"]], errors="coerce").fillna(1).astype(int) == 1]
        team_active = active[active[lc["team_id"]] == sel_row["team_id"]].copy()
        team_players = team_active.merge(players, left_on=lc["player_id"], right_on=pc["player_id"], how="left")
    else:
        team_active = pd.DataFrame()
        team_players = pd.DataFrame()

    lineup_ids = team_active[lc["player_id"]].dropna().astype(int).tolist() if not team_active.empty else []
    pool = players[~players[pc["player_id"]].isin(lineup_ids)].copy() if pc["player_id"] and pc["player_id"] in players.columns else players.copy()

    team_positions = sorted(team_players["position"].dropna().astype(str).unique().tolist()) if not team_players.empty and "position" in team_players.columns else []
    pos_choice = st.selectbox("Filtro de posição", ["Todas"] + team_positions)

    eligible_out = team_players.copy()
    if pos_choice != "Todas" and "position" in eligible_out.columns:
        eligible_out = eligible_out[eligible_out["position"].astype(str) == pos_choice]
        if "position" in pool.columns:
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

    out_sum, in_sum = trade_package_summary(out_rows, in_rows)
    current = {c: pd.to_numeric(sel_row[c], errors="coerce") if c in sel_row.index else np.nan for c in STAT_COLS}
    n = max(len(team_players), 1)
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
        st.dataframe(out_rows[[c for c in ["player_name","position","fantasy_value","tier_valor"] + STAT_COLS if c in out_rows.columns]], use_container_width=True)
    with c_right:
        st.markdown("### Pacote entrando")
        st.dataframe(in_rows[[c for c in ["player_name","position","fantasy_value","tier_valor"] + STAT_COLS if c in in_rows.columns]], use_container_width=True)

   # current = stat_cols(team_players)
   # n = max(len(team_players), 1)
   # new = apply_trade(current, out_rows, in_rows, n)

    old_row = pd.Series({**current})
    new_row = pd.Series({**new})
    opps = teams_calc[(teams_calc["team_id"] != sel_row["team_id"]) & (teams_calc["team_id"] != 15)].dropna(subset=STAT_COLS).copy() if not teams_calc.empty else pd.DataFrame()
    old_m = float(np.mean([matchup_score(old_row, opp) for _, opp in opps.iterrows()])) if not opps.empty else np.nan
    new_m = float(np.mean([matchup_score(new_row, opp) for _, opp in opps.iterrows()])) if not opps.empty else np.nan
    st.caption("Impacto médio da troca contra todos os outros times")
    m1, m2, m3 = st.columns(3)
    m1.metric("Matchup médio antes", f"{old_m:.2f}" if pd.notna(old_m) else "NA")
    m2.metric("Matchup médio depois", f"{new_m:.2f}" if pd.notna(new_m) else "NA")
    m3.metric("Delta", f"{new_m - old_m:.2f}" if pd.notna(old_m) and pd.notna(new_m) else "NA")

else:
    st.subheader("Sugestão de troca")
    pool = player_pool(players, sel_row["team_id"])
    st.info("A próxima etapa pode refinar a sugestão de troca sem mexer nas abas de cenário.")
    st.dataframe(display_table(pool, [c for c in ["player_name", "team_id", "position", "fantasy_value"] if c in pool.columns]).sort_values("fantasy_value", ascending=False).head(20), use_container_width=True)
