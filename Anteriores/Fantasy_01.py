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
MAIN_DEBUG = False


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
    pontos = str(row.get("Pontos", "")).strip()
    return pontos != ""


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


def processar_todas_as_abas():
    spreadsheet = conectar_gsheets()
    worksheets = spreadsheet.worksheets()
    log(f"Abas encontradas: {[ws.title for ws in worksheets]}")

    for ws in worksheets:
        log(f"\n=== PROCESSANDO ABA: {ws.title} ===")

        all_values = ws.get_all_values()
        if not all_values:
            log("Aba vazia; pulando.")
            continue

        header = all_values[0]
        rows = all_values[1:]

        idx_stats = {}
        for col in COLUNAS_STATS:
            try:
                idx_stats[col] = header.index(col) + 1
            except ValueError:
                idx_stats[col] = None

        try:
            idx_jogadores = header.index("Jogadores")
            idx_gameid = header.index("GameID")
        except ValueError as exc:
            log(f"[{ws.title}] Cabeçalhos obrigatórios não encontrados: {exc}")
            continue

        df = pd.DataFrame(rows, columns=header)

        linhas_preenchidas = 0

        for i, row in df.iterrows():
            jogador = str(row.get("Jogadores", "")).strip()
            game_id_cell = str(row.get("GameID", "")).strip()

            if not jogador or not game_id_cell:
                continue

            if stats_ja_preenchidas(row):
                log(f"[{ws.title}] Linha {i+2}: já preenchida; pulando.")
                continue

            log(f"[{ws.title}] Linha {i+2}: processando '{jogador}' (GameID: {game_id_cell})")

            stats = buscar_stats_com_cache(game_id_cell, jogador)

            updates = []
            for stat_col in COLUNAS_STATS:
                if idx_stats.get(stat_col) is None:
                    continue
                val = str(stats.get(stat_col, ""))
                cell_a1 = f"{a1_col(idx_stats[stat_col])}{i+2}"
                updates.append({"range": cell_a1, "values": [[val]]})

            if updates:
                try:
                    ws.batch_update(updates)
                    log(f"[{ws.title}] Linha {i+2}: escrita concluída.")
                except Exception as exc:
                    log(f"[{ws.title}] Erro em batch_update na linha {i+2}: {exc}")

            if any(str(v).strip() for v in stats.values()):
                linhas_preenchidas += 1

            time.sleep(0.25)

        log(f"[{ws.title}] Aba concluída: {linhas_preenchidas} linhas preenchidas.")

    log("\nPROCESSAMENTO DE TODAS AS ABAS CONCLUÍDO.")


if __name__ == "__main__":
    processar_todas_as_abas()