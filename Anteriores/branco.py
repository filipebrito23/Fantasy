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

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Colunas que você tem (não mudar nomes)
COLUNAS_PLANILHA = ["Jogadores", "Time Mandante", "Data", "GameID"]
COLUNAS_STATS = ["Pontos", "Rebotes", "Assistências", "Roubos", "Tocos", "Bolas de 3", "Turnovers"]

# Aba de teste (altere para o nome real)
ABA_TESTE = "CHA x KDG"  # exemplo
MAIN_DEBUG = False

# ---------------------------------------------------------------------------

def log(msg):
    print(msg)

def stats_vazias():
    return {col: "" for col in COLUNAS_STATS}

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

# 3. Conversão de data (DD/MM/YY -> YYYYMMDD; só para log por enquanto)
def parse_data(data_str):
    try:
        dt = datetime.strptime(str(data_str).strip(), "%d/%m/%y")
        return dt.strftime("%Y%m%d")
    except:
        return None

# 4. A1 de coluna
def a1_col(col_num):
    result = ""
    while col_num > 0:
        col_num, remainder = divmod(col_num - 1, 26)
        result = chr(65 + remainder) + result
    return result

# 5. Função principal: buscar stats via nba_api pelo GameID e nome do jogador
def buscar_stats_jogador(game_id: str, player_name: str) -> dict:
    try:
        log(f"Buscando boxscore pela NBA API para GameID {game_id} (jogador: {player_name})...")
        bx = boxscoretraditionalv3.BoxScoreTraditionalV3(
            game_id=game_id,
            start_period=0,
            end_period=14,
            start_range=0,
            end_range=2147483647,
            range_type=0,
            timeout=20,
        )
        df = bx.get_data_frames()[0]  # dataset 0 = stats de jogadores
        log(f"Total de linhas no boxscore: {len(df)}")

        # ------------------------------------------------
        # DEBUG: imprimir colunas e exemplo de nomes
        # Remova depois, se quiser
        print("COLUMNS:", df.columns.tolist())
        if "firstName" in df.columns and "familyName" in df.columns:
            print("Primeiras 3 linhas (firstName/familyName):")
            print(df.head(3)[["firstName", "familyName"]])
        # ------------------------------------------------

        # Suponha:
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

        for _, row in df.iterrows():
            first = str(row.get(first_name_col, "")).strip()
            last = str(row.get(last_name_col, "")).strip()
            if not first and not last:
                continue
            nome_api = normalizar_nome(f"{first} {last}")
            # DEBUG de match (remova depois):
            print(f"API: '{nome_api}' | Planilha: '{alvo}'")
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
        log(f"Jogador não encontrado no boxscore: {player_name}")
        return stats_vazias()
    except Exception as exc:
        log(f"Erro na API da NBA: {exc}")
        return stats_vazias()

# 6. Função de teste: ler planilha, pegar a primeira linha válida e preencher
def testar_primeira_linha():
    spreadsheet = conectar_gsheets()
    worksheet = spreadsheet.worksheet(ABA_TESTE)
    log(f"=== ABA DE TESTE: {worksheet.title} ===")

    # Read all values
    all_values = worksheet.get_all_values()
    if not all_values:
        log("Aba vazia; nada a fazer.")
        return

    header = all_values[0]
    rows = all_values[1:]

    # Encontrar índice das colunas de stats
    idx_stats = {}
    for col in COLUNAS_STATS:
        try:
            idx_stats[col] = header.index(col) + 1  # A1 column number
        except ValueError:
            # Coluna não existe; cria?
            idx_stats[col] = None

    log(f"Colunas de stats: {idx_stats}")

    df = pd.DataFrame(rows, columns=header)

    linha_feita = False
    for i, row in df.iterrows():
        jogador = str(row.get("Jogadores", "")).strip()
        game_id_cell = str(row.get("GameID", "")).strip()

        if not jogador:
            log(f"Linha {i+2}: jogador vazio; pulando.")
            continue
        if not game_id_cell:
            log(f"Linha {i+2}: GameID vazio para {jogador}; pulando.")
            continue

        log(f"+++ TESTE PARA JOGADOR: {jogador} (GameID: {game_id_cell}) +++")

        stats = buscar_stats_jogador(game_id_cell, jogador)

        for stat_col in COLUNAS_STATS:
            if stat_col not in idx_stats or idx_stats[stat_col] is None:
                log(f"Coluna {stat_col} não encontrada; pulando.")
                continue
            val = str(stats.get(stat_col, ""))
            cell_a1 = f"{a1_col(idx_stats[stat_col])}{i+2}"
            log(f"Escrever: {worksheet.title}!{cell_a1} = {val!r}")

            worksheet.update_acell(cell_a1, val)

            if MAIN_DEBUG:
                time.sleep(0.5)
                v2 = worksheet.acell(cell_a1).value
                log(f"Verificação: {worksheet.title}!{cell_a1} => {v2!r}")

        linha_feita = True
        break  # ROMPE após a primeira linha válida

    if linha_feita:
        log(">>> Teste concluído: primeira linha processada.")
    else:
        log("Nenhuma linha elegível encontrada na aba.")

# 7. Entry point
if __name__ == "__main__":
    testar_primeira_linha()