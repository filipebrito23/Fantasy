from nba_api.stats.endpoints import scheduleleaguev2
import pandas as pd

season = "2026-27"

schedule = scheduleleaguev2.ScheduleLeagueV2(league_id="00", season=season)
df = schedule.get_data_frames()[0]

jogos = df[[
    "gameId",
    "gameDateEst",
    "awayTeam_teamTricode",
    "awayTeam_teamName",
    "homeTeam_teamTricode",
    "homeTeam_teamName",
]].copy()

jogos = jogos.rename(columns={
    "gameId": "GAME_ID",
    "gameDateEst": "GAME_DATE",
    "awayTeam_teamTricode": "AWAY_TEAM_ABBR",
    "awayTeam_teamName": "AWAY_TEAM_NAME",
    "homeTeam_teamTricode": "HOME_TEAM_ABBR",
    "homeTeam_teamName": "HOME_TEAM_NAME",
})

jogos["SEASON"] = season

jogos = (
    jogos
    .sort_values(["GAME_DATE", "GAME_ID"])
    .drop_duplicates(subset=["GAME_ID"])
    .reset_index(drop=True)
)

jogos = jogos[[
    "SEASON",
    "GAME_DATE",
    "GAME_ID",
    "AWAY_TEAM_ABBR",
    "AWAY_TEAM_NAME",
    "HOME_TEAM_ABBR",
    "HOME_TEAM_NAME",
]]

jogos.to_csv("nba_2026_27_calendario_completo.csv", index=False, encoding="utf-8-sig")
print(f"Calendário exportado com {len(jogos)} jogos.")