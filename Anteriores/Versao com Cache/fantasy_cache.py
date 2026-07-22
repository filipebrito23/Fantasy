import re
import time
from datetime import datetime
import json
from pathlib import Path

import gspread
import pandas as pd
from google.oauth2.service_account import Credentials

# ---------
# nba_api
# ---------
from nba_api.stats.endpoints import boxscoretraditionalv3

# ---------

# ---------- CONFIGURAÇÃO -------------------------------------
SPREADSHEET_ID = "1IiJb0iJW4Vnqyh5CFs8jZOSSZqlmdBGbWJCPFoNO4ao"
SERVICE_ACCOUNT_FILE = Path(__file__).resolve().parent / "service_account.json"
CACHE_FILE = Path(__file__).resolve().parent / "nba_boxscore_cache.json"  # cache local por GameID

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

COLUNAS_PLANILHA = ["Jogadores", "Time Mandante", "Data", "GameID"]
COLUNAS_STATS = ["Pontos", "Rebotes", "Assistências", "Roubos", "Tocos", "Bolas de 3", "Turnovers"]

MAIN_DEBUG = False
MAX_ERROS_SEQUENCIAIS = 5  # parar após 5 erros seguidos na mesma aba

# ---------------------------------------------------------------------------

def log(msg):
    print(msg)

def stats_vazias():
    return {col: "" for col in COLUNAS_STATS}

# --- CACHE LOCAL (por GameID) ---
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

CACHE = cache_load()  # cache em memória

# 1. Conectar ao Google Sheets
def conectar_gsheets():
    log(f"Credencial: {SERVICE_ACCOUNT_FILE}")
    if not SERVICE_ACCOUNT_FILE.exists():
        raise FileNotFoundError(f"Credencial não encontrada: {SERVICE_ACCOUNT_FILE}")
    creds = Credentials.from_service_account_file(str(SERVICE_ACCOUNT_FILE), scopes=SCOPES)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    log(f"Planilha: {spreadsheet.title}")
    log(f"URL: https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit")
    return spreadsheet

# 2. Normalizar nome do jogador
def normalizar_nome(nome):
    if nome is None:
        return ""
    nome = str(nome).strip().lower()
    nome = re.sub(r"[*\\.]", "", nome)
    return re.sub(r"\\s+", " ", nome)

# 3. Conversão de data (só para uso futuro/log)
def parse_data(data_str):
    try:
        dt = datetime.strptime(str(data_str).strip(), "%d/%m/%y")
        return dt.strftime("%Y%m%d")
    except:
        return None

# 4. Converter índice de coluna para A1
def a1_col(col_num):
    result = ""
    while col_num > 0:
        col_num, remainder = divmod(col_num - 1, 26)
        result = chr(65 + remainder) + result
    return result

# 5. Buscar stats de um jogador (com cache por GameID)
def buscar_stats_com_cache(game_id: str, player_name: str) -> dict:
    if game_id in CACHE and "stats" in CACHE[game_id]:
        # Garantir que seja lista de dicts
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

        # Salva o boxscore completo do jogo no cache
        if isinstance(df_data, list) and all(isinstance(r, dict) for r in df_data):
            CACHE[game_id] = {"stats": df_data, "ts": datetime.now().isoformat()}
            cache_save(CACHE)
        else:
            log(f"ERRO: boxscore não é lista de dicts; formato inválido para cache.")

    # Se DF_DATA não é lista de dicts, retorna vazias
    if not isinstance(df_data, list) or not all(isinstance(r, dict) for r in df_data):
        log(f"Cache/API devolveu formato inválido para {game_id}; pulando.")
        return stats_vazias()

    # Extração de stats do jogador dentro do cache
    first_name_col = "firstName"
    last_name_col = "familyName"
    pts_col = "points"
    reb_col = "reboundsTotal"
    ast_col = "assists"
    stl_col = "steals"
    blk_col = "blocks"
    thr_col = "threePointersMade"
    tov_col = "turnovers"

    alvo = normalizar_nome(player_name)

    for row in df_data:
        # row é dict, garantido pelo check acima
        first = str(row.get(first_name_col, "")).strip()
        last = str(row.get(last_name_col, "")).strip()
        if not first and not last:
            continue
        nome_api = normalizar_nome(f"{first} {last}")
        if alvo == nome_api:
            return {
                "Pontos": str(row.get(pts_col, "")),
                "Rebotes": str(row.get(reb_col, "")),
                "Assistências": str(row.get(ast_col, "")),
                "Roubos": str(row.get(stl_col, "")),
                "Tocos": str(row.get(blk_col, "")),
                "Bolas de 3": str(row.get(thr_col, "")),
                "Turnovers": str(row.get(tov_col, "")),
            }

    log(f"Jogador não encontrado no boxscore (cache): {player_name} (GameID: {game_id})")
    return stats_vazias()

# 6. Processar TODAS AS ABAS da planilha
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

        # Índices das colunas de stats
        idx_stats = {}
        for col in COLUNAS_STATS:
            try:
                idx_stats[col] = header.index(col) + 1
            except ValueError:
                idx_stats[col] = None
        log(f"Colunas de stats: {idx_stats}")

        df = pd.DataFrame(rows, columns=header)

        linhas_preenchidas = 0
        erros_sequenciais = 0

        for i, row in df.iterrows():
            jogador = str(row.get("Jogadores", "")).strip()
            game_id_cell = str(row.get("GameID", "")).strip()

            if not jogador:
                log(f"[{ws.title}] Linha {i+2}: jogador vazio; pulando.")
                continue
            if not game_id_cell:
                log(f"[{ws.title}] Linha {i+2}: GameID vazio para {jogador}; pulando.")
                continue

            log(f"[{ws.title}] Linha {i+2}: processando jogador '{jogador}' (GameID: {game_id_cell})")

            stats = buscar_stats_com_cache(game_id_cell, jogador)

            # Agrupar escritas por linha (batch_update)
            updates = []
            todas_vazias = True
            for stat_col in COLUNAS_STATS:
                if stat_col not in idx_stats or idx_stats[stat_col] is None:
                    continue
                val = str(stats.get(stat_col, ""))
                if val.strip():
                    todas_vazias = False
                col_idx = idx_stats[stat_col]
                cell_a1 = f"{a1_col(col_idx)}{i+2}"
                log(f"[{ws.title}] Enfileirar escrita: {cell_a1} = {val!r}")
                updates.append({
                    "range": cell_a1,
                    "values": [[val]]
                })

            if updates:
                try:
                    ws.batch_update(updates)
                    log(f"[{ws.title}] Linha {i+2}: escrita em lote realizada.")
                    if MAIN_DEBUG:
                        time.sleep(0.5)
                except Exception as exc:
                    log(f"[{ws.title}] Erro em batch_update para linha {i+2}: {exc}")

            if not todas_vazias:
                linhas_preenchidas += 1
            else:
                erros_sequenciais += 1
                if erros_sequenciais >= MAX_ERROS_SEQUENCIAIS:
                    log(f"[{ws.title}] Parando após {erros_sequenciais} erros sequenciais.")
                    break

            time.sleep(0.25)  # para respeitar quota de writes/min

        log(f"[{ws.title}] Aba concluída: {linhas_preenchidas} linhas preenchidas.")

    log("\nPROCESSAMENTO DE TODAS AS ABAS CONCLUÍDO.")

# 7. Entrypoint
if __name__ == "__main__":
    processar_todas_as_abas()