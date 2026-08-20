from nba_api.stats.endpoints import scheduleleaguev2
import pandas as pd

season = "2026-27"

schedule = scheduleleaguev2.ScheduleLeagueV2(league_id="00", season=season)
df = schedule.get_data_frames()[0]

# Inspecionar colunas disponíveis
print("Colunas disponíveis:")
print(df.columns.tolist())
print(f"\nTotal de jogos: {len(df)}")