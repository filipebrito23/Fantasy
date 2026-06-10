import pandas as pd
from data_loader import SALARY_COLS, OPTION_COLS


def get_team_options(teams: pd.DataFrame) -> pd.DataFrame:
    cols = [c for c in ["team_id", "team_name"] if c in teams.columns]
    return teams[cols].drop_duplicates().sort_values("team_name").reset_index(drop=True)


def build_roster_view(roster_df: pd.DataFrame, players_df: pd.DataFrame, team_id: int, roster_type: str) -> pd.DataFrame:
    df = roster_df.loc[roster_df["team_id"] == team_id].copy()
    player_cols = [c for c in ["player_id", "player_name", "position", "nba_team"] if c in players_df.columns]
    df = df.merge(players_df[player_cols], on="player_id", how="left")

    order_col = "pos_order" if "pos_order" in df.columns else "order"
    if order_col in df.columns:
        df = df.sort_values(order_col, na_position="last")

    visible_cols = [
        order_col,
        "player_id",
        "player_name",
        "position",
        *[c for c in SALARY_COLS if c in df.columns],
        *[c for c in OPTION_COLS if c in df.columns],
    ]
    visible_cols = [c for c in visible_cols if c in df.columns]
    df = df[visible_cols].copy()
    df.insert(0, "roster_type", roster_type)
    return df.reset_index(drop=True)
