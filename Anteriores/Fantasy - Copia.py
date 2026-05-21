import re
import time
from datetime import datetime
import json
from pathlib import Path

import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from nba_api.stats.endpoints import boxscoretraditionalv3

SPREADSHEET_ID = "1IiJb0iJW4Vnqyh5CFs8jZOSSZqlmdBGbWJCPFoNO4ao"
SERVICE_ACCOUNT_FILE = Path(__file__).resolve().parent / "service_account.json"
CACHE_FILE = Path(__file__).resolve().parent / "nba_boxscore_cache.json"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

COLUNAS_STATS = ["Pontos", "Rebotes", "Assistências", "Roubos", "Tocos", "Bolas de 3", "Turnovers"]


def log(msg):
    print(msg)


def stats_vazias():
    return {col: "" for col in COLUNAS_STATS}


def cache_load():
    if not CACHE_FILE.exists():
        return {}
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def cache_save(cache_dict):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache_dict, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


CACHE = cache_load()


def conectar_gsheets():
    log(f"Credencial: {SERVICE_ACCOUNT_FILE}")
    if not SERVICE_ACCOUNT_FILE.exists():
        raise FileNotFoundError(f"Credencial não encontrada: {SERVICE_ACCOUNT_FILE}")
    creds = Credentials.from_service_account_file(str(SERVICE_ACCOUNT_FILE), scopes=SCOPES)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    log(f"Planilha: {spreadsheet.title}")
    return spreadsheet


def listar_abas():
    spreadsheet = conectar_gsheets()
    return [ws.title for ws in spreadsheet.worksheets()]


def normalizar_nome(nome):
    if nome is None:
        return ""
    nome = str(nome).strip().lower()
    nome = re.sub(r"[*\\.]", "", nome)
    return re.sub(r"\s+", " ", nome)


def a1_col(col_num):
    result = ""
    while col_num > 0:
        col_num, remainder = divmod(col_num - 1, 26)
        result = chr(65 + remainder) + result
    return result


def stats_ja_preenchidas(row):
    return str(row.get("Pontos", "")).strip() != ""


def buscar_stats_com_cache(game_id: str, player_name: str) -> dict:
    if game_id in CACHE and "stats" in CACHE[game_id]:
        raw_stats = CACHE[game_id]["stats"]
        if isinstance(raw_stats, list) and all(isinstance(r, dict) for r in raw_stats):
            log(f"CACHE HIT: {game_id}")
            df_data = raw_stats
        else:
            log(f"CACHE FORMATO ERRADO para {game_id}; ignorando cache.")
            df_data = None
    else:
        df_data = None

    if df_data is None:
        log(f"CACHE MISS: {game_id}; buscando via NBA API...")
        bx = boxscoretraditionalv3.BoxScoreTraditionalV3(
            game_id=game_id,
            start_period=0,
            end_period=14,
            start_range=0,
            end_range=2147483647,
            range_type=0,
            timeout=20,
        )
        df = bx.get_data_frames()[0]
        df_data = df.to_dict("records")

        if isinstance(df_data, list) and all(isinstance(r, dict) for r in df_data):
            CACHE[game_id] = {"stats": df_data, "ts": datetime.now().isoformat()}
            cache_save(CACHE)

    if not isinstance(df_data, list) or not all(isinstance(r, dict) for r in df_data):
        log(f"Cache/API devolveu formato inválido para {game_id}; pulando.")
        return stats_vazias()

    alvo = normalizar_nome(player_name)

    for row in df_data:
        first = str(row.get("firstName", "")).strip()
        last = str(row.get("familyName", "")).strip()
        if not first and not last:
            continue
        nome_api = normalizar_nome(f"{first} {last}")
        if alvo == nome_api:
            return {
                "Pontos": str(row.get("points", "")),
                "Rebotes": str(row.get("reboundsTotal", "")),
                "Assistências": str(row.get("assists", "")),
                "Roubos": str(row.get("steals", "")),
                "Tocos": str(row.get("blocks", "")),
                "Bolas de 3": str(row.get("threePointersMade", "")),
                "Turnovers": str(row.get("turnovers", "")),
            }

    log(f"Jogador não encontrado no boxscore (cache): {player_name} (GameID: {game_id})")
    return stats_vazias()


def processar_aba(nome_aba, somente_vazias=True, callback=None):
    spreadsheet = conectar_gsheets()
    ws = spreadsheet.worksheet(nome_aba)

    all_values = ws.get_all_values()
    if not all_values:
        return {
            "aba": nome_aba,
            "linhas_total": 0,
            "linhas_preenchidas": 0,
            "linhas_puladas": 0,
            "cache_hits": 0,
            "cache_misses": 0,
        }

    header = all_values[0]
    rows = all_values[1:]
    df = pd.DataFrame(rows, columns=header)

    try:
        idx_stats = {col: header.index(col) + 1 for col in COLUNAS_STATS}
    except ValueError as exc:
        raise ValueError(f"Coluna ausente na aba {nome_aba}: {exc}")

    total = len(df)
    preenchidas = 0
    puladas = 0
    cache_hits = 0
    cache_misses = 0

    for i, row in df.iterrows():
        jogador = str(row.get("Jogadores", "")).strip()
        game_id_cell = str(row.get("GameID", "")).strip()

        if not jogador or not game_id_cell:
            puladas += 1
            continue

        if somente_vazias and stats_ja_preenchidas(row):
            puladas += 1
            if callback:
                callback("skip", nome_aba, i + 2, jogador, game_id_cell, None)
            continue

        if game_id_cell in CACHE and "stats" in CACHE[game_id_cell]:
            raw_stats = CACHE[game_id_cell]["stats"]
            if isinstance(raw_stats, list) and all(isinstance(r, dict) for r in raw_stats):
                cache_hits += 1
            else:
                cache_misses += 1
        else:
            cache_misses += 1

        if callback:
            callback("row_start", nome_aba, i + 2, jogador, game_id_cell, None)

        stats = buscar_stats_com_cache(game_id_cell, jogador)

        updates = []
        for stat_col in COLUNAS_STATS:
            val = str(stats.get(stat_col, ""))
            cell_a1 = f"{a1_col(idx_stats[stat_col])}{i+2}"
            updates.append({"range": cell_a1, "values": [[val]]})

        if updates:
            try:
                ws.batch_update(updates)
                if any(str(v).strip() for v in stats.values()):
                    preenchidas += 1
            except Exception as exc:
                log(f"[{nome_aba}] Erro em batch_update na linha {i+2}: {exc}")

        if callback:
            callback("row_end", nome_aba, i + 2, jogador, game_id_cell, stats)

        time.sleep(0.15)

    return {
        "aba": nome_aba,
        "linhas_total": total,
        "linhas_preenchidas": preenchidas,
        "linhas_puladas": puladas,
        "cache_hits": cache_hits,
        "cache_misses": cache_misses,
    }


def processar_todas_as_abas(somente_vazias=True, callback=None):
    spreadsheet = conectar_gsheets()
    worksheets = spreadsheet.worksheets()

    resumo = []
    for ws in worksheets:
        r = processar_aba(ws.title, somente_vazias=somente_vazias, callback=callback)
        resumo.append(r)
        if callback:
            callback("sheet_end", ws.title, None, None, None, r)

    return resumo


if __name__ == "__main__":
    processar_todas_as_abas()