from nba_api.stats.endpoints import leaguegamefinder
import pandas as pd

season = "2026-27"

finder = leaguegamefinder.LeagueGameFinder(season_nullable=season)
df = finder.get_data_frames()[0]

# leaguegamefinder retorna uma linha por time/jogo
base = df[["GAME_ID", "GAME_DATE", "MATCHUP", "TEAM_ABBREVIATION", "TEAM_NAME"]].copy()

home = base[base["MATCHUP"].str.contains("vs\\.", na=False)].copy()
away = base[base["MATCHUP"].str.contains("@", na=False)].copy()

home = home.rename(columns={
    "TEAM_ABBREVIATION": "HOME_TEAM_ABBR",
    "TEAM_NAME": "HOME_TEAM_NAME",
})

away = away.rename(columns={
    "TEAM_ABBREVIATION": "AWAY_TEAM_ABBR",
    "TEAM_NAME": "AWAY_TEAM_NAME",
})

jogos = pd.merge(
    home[["GAME_ID", "GAME_DATE", "HOME_TEAM_ABBR", "HOME_TEAM_NAME"]],
    away[["GAME_ID", "GAME_DATE", "AWAY_TEAM_ABBR", "AWAY_TEAM_NAME"]],
    on=["GAME_ID", "GAME_DATE"],
    how="outer"
)

jogos = (
    jogos
    .sort_values(["GAME_DATE", "GAME_ID"])
    .drop_duplicates(subset=["GAME_ID"])
    .reset_index(drop=True)
)

jogos["SEASON"] = season
jogos = jogos[[
    "SEASON",
    "GAME_DATE",
    "GAME_ID",
    "AWAY_TEAM_ABBR",
    "AWAY_TEAM_NAME",
    "HOME_TEAM_ABBR",
    "HOME_TEAM_NAME",
]]

jogos.to_csv("nba_2026_27_jogos_gameid.csv", index=False, encoding="utf-8-sig")
print(f"Arquivo gerado com {len(jogos)} jogos.")