import re
import time
from datetime import datetime
from io import StringIO
from pathlib import Path

import gspread
import pandas as pd
import requests
from bs4 import BeautifulSoup
from google.oauth2.service_account import Credentials

SPREADSHEET_ID = "1IiJb0iJW4Vnqyh5CFs8jZOSSZqlmdBGbWJCPFoNO4ao"
SERVICE_ACCOUNT_FILE = Path(__file__).resolve().parent / "service_account.json"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

COLUNAS_OBRIGATORIAS = ["Jogadores", "Time Mandante", "Data"]
COLUNAS_STATS = ["Pontos", "Rebotes", "Assistências", "Roubos", "Tocos", "Bolas de 3", "Turnovers"]

ABA_TESTE = "CHA x KDG"
APENAS_TESTE_ESCRITA = True
PROCESSAR_APENAS_PRIMEIRA_LINHA = True
CELULA_TESTE = "E2"
VALOR_TESTE = "999"

NBA_TEAMS = {
    "Atlanta Hawks": "ATL", "Boston Celtics": "BOS", "Brooklyn Nets": "BRK",
    "Charlotte Hornets": "CHO", "Chicago Bulls": "CHI", "Cleveland Cavaliers": "CLE",
    "Dallas Mavericks": "DAL", "Denver Nuggets": "DEN", "Detroit Pistons": "DET",
    "Golden State Warriors": "GSW", "Houston Rockets": "HOU", "Indiana Pacers": "IND",
    "Los Angeles Clippers": "LAC", "Los Angeles Lakers": "LAL", "Memphis Grizzlies": "MEM",
    "Miami Heat": "MIA", "Milwaukee Bucks": "MIL", "Minnesota Timberwolves": "MIN",
    "New Orleans Pelicans": "NOP", "New York Knicks": "NYK", "Oklahoma City Thunder": "OKC",
    "Orlando Magic": "ORL", "Philadelphia 76ers": "PHI", "Phoenix Suns": "PHX",
    "Portland Trail Blazers": "POR", "Sacramento Kings": "SAC", "San Antonio Spurs": "SAS",
    "Toronto Raptors": "TOR", "Utah Jazz": "UTA", "Washington Wizards": "WAS",
}


def log(msg):
    print(msg)


def conectar_gsheets():
    log(f"Credencial esperada em: {SERVICE_ACCOUNT_FILE}")
    if not SERVICE_ACCOUNT_FILE.exists():
        raise FileNotFoundError(f"Arquivo de credencial não encontrado: {SERVICE_ACCOUNT_FILE}")

    creds = Credentials.from_service_account_file(str(SERVICE_ACCOUNT_FILE), scopes=SCOPES)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    log(f"Planilha conectada: {spreadsheet.title}")
    log(f"URL esperada: https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit")
    return spreadsheet


def parse_data(data_str):
    try:
        dt = datetime.strptime(str(data_str).strip(), "%d/%m/%y")
        return dt.strftime("%Y%m%d")
    except Exception:
        return None


def normalizar_nome(nome):
    nome = "" if nome is None else str(nome)
    nome = nome.strip().lower()
    nome = re.sub(r"[*\.]", "", nome)
    nome = re.sub(r"\s+", " ", nome)
    return nome


def encontrar_jogador(df_box, player_name):
    if df_box is None or df_box.empty:
        return None

    if getattr(df_box.columns, "nlevels", 1) > 1:
        df_box.columns = df_box.columns.droplevel()

    player_col = df_box.columns[0]
    df_box[player_col] = df_box[player_col].astype(str).str.strip()
    alvo = normalizar_nome(player_name)

    for idx, player in df_box[player_col].items():
        atual = normalizar_nome(player)
        if atual == alvo or alvo in atual or atual in alvo:
            return idx, df_box

    return None


def stats_vazias():
    return {col: "" for col in COLUNAS_STATS}


def find_player_stats(team_abbr, game_date, player_name):
    game_id = f"{game_date}0{team_abbr}"
    url = f"https://www.basketball-reference.com/boxscores/{game_id}.html"
    log(f"URL boxscore: {url}")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,pt-BR;q=0.8",
        "Referer": "https://www.basketball-reference.com/",
        "Connection": "keep-alive",
    }

    try:
        response = requests.get(url, headers=headers, timeout=20)
        log(f"Status HTTP: {response.status_code}")
        if response.status_code != 200:
            return stats_vazias()

        html = response.text.replace("<!--", "").replace("-->", "")
        soup = BeautifulSoup(html, "html.parser")
        tables = soup.find_all("table", id=re.compile(r"box-.+-game-basic"))
        log(f"Tabelas boxscore encontradas: {len(tables)}")

        for table in tables:
            try:
                df_box = pd.read_html(StringIO(str(table)))[0]
            except Exception as exc:
                log(f"Erro lendo tabela: {exc}")
                continue

            encontrado = encontrar_jogador(df_box, player_name)
            if not encontrado:
                continue

            idx, df_box = encontrado
            stats = {
                "Pontos": df_box.loc[idx, "PTS"] if "PTS" in df_box.columns else "",
                "Rebotes": df_box.loc[idx, "TRB"] if "TRB" in df_box.columns else "",
                "Assistências": df_box.loc[idx, "AST"] if "AST" in df_box.columns else "",
                "Roubos": df_box.loc[idx, "STL"] if "STL" in df_box.columns else "",
                "Tocos": df_box.loc[idx, "BLK"] if "BLK" in df_box.columns else "",
                "Bolas de 3": df_box.loc[idx, "3P"] if "3P" in df_box.columns else "",
                "Turnovers": df_box.loc[idx, "TOV"] if "TOV" in df_box.columns else "",
            }
            log(f"Stats encontradas para {player_name}: {stats}")
            return stats

        log(f"Jogador não encontrado no boxscore: {player_name}")
        return stats_vazias()
    except Exception as exc:
        log(f"Erro em find_player_stats: {exc}")
        return stats_vazias()


def preparar_dataframe_worksheet(ws):
    values = ws.get_all_values()
    if not values:
        log(f"[{ws.title}] aba vazia")
        return None, None

    header = values[0]
    rows = values[1:]
    df = pd.DataFrame(rows, columns=header)
    log(f"[{ws.title}] cabeçalho detectado: {header}")

    if not all(col in df.columns for col in COLUNAS_OBRIGATORIAS):
        log(f"[{ws.title}] incompatível. Esperado: {COLUNAS_OBRIGATORIAS}")
        return None, None

    for col in COLUNAS_STATS:
        if col not in df.columns:
            df[col] = ""

    return df, header


def a1_col(col_num):
    result = ""
    while col_num > 0:
        col_num, remainder = divmod(col_num - 1, 26)
        result = chr(65 + remainder) + result
    return result


def testar_escrita(ws):
    valor_antes = ws.acell(CELULA_TESTE).value
    log(f"Teste escrita em {ws.title}!{CELULA_TESTE} | antes={valor_antes}")
    ws.update_acell(CELULA_TESTE, VALOR_TESTE)
    time.sleep(2)
    valor_depois = ws.acell(CELULA_TESTE).value
    log(f"Teste escrita em {ws.title}!{CELULA_TESTE} | depois={valor_depois}")


def processar_aba(ws):
    df, header = preparar_dataframe_worksheet(ws)
    if df is None:
        return

    log(f"\n=== Aba: {ws.title} ===")
    testar_escrita(ws)

    if APENAS_TESTE_ESCRITA:
        log("Modo atual: apenas teste de escrita. Encerrando após teste.")
        return

    stats_col_idx = {col: header.index(col) + 1 for col in COLUNAS_STATS if col in header}
    log(f"Mapeamento colunas stats: {stats_col_idx}")

    linhas_processadas = 0
    for i, row in df.iterrows():
        jogador = str(row.get("Jogadores", "")).strip()
        mandante = str(row.get("Time Mandante", "")).strip()
        data_txt = str(row.get("Data", "")).strip()
        pontos_atual = str(row.get("Pontos", "")).strip()

        if not jogador or not mandante or not data_txt:
            continue

        if pontos_atual:
            log(f"Linha {i+2}: já preenchida | {jogador}")
            continue

        game_date = parse_data(data_txt)
        team_abbr = NBA_TEAMS.get(mandante, mandante[:3].upper())
        log(f"Linha {i+2}: jogador={jogador} | mandante={mandante} | data={data_txt} | game_date={game_date} | team={team_abbr}")

        if not game_date:
            log("Data inválida, pulando")
            continue

        stats = find_player_stats(team_abbr, game_date, jogador)

        if all(str(stats.get(col, "")).strip() == "" for col in COLUNAS_STATS):
            log(f"Sem stats para {jogador}; pulando escrita para não apagar células.")
            continue

        sheet_row = i + 2
        for stat_col in COLUNAS_STATS:
            if stat_col not in stats_col_idx:
                continue
            cell_a1 = f"{a1_col(stats_col_idx[stat_col])}{sheet_row}"
            valor = str(stats.get(stat_col, ""))
            log(f"Escrevendo: {ws.title}!{cell_a1} = {valor!r}")
            ws.update_acell(cell_a1, valor)
            time.sleep(1)
            valor_lido = ws.acell(cell_a1).value
            log(f"Conferência pós-escrita: {ws.title}!{cell_a1} => {valor_lido!r}")

        linhas_processadas += 1
        if PROCESSAR_APENAS_PRIMEIRA_LINHA and linhas_processadas >= 1:
            log("Encerrando após a primeira linha elegível.")
            break


def processar_todas_as_abas():
    spreadsheet = conectar_gsheets()
    worksheets = spreadsheet.worksheets()
    log(f"Abas encontradas: {[ws.title for ws in worksheets]}")

    for ws in worksheets:
        if ABA_TESTE and ws.title != ABA_TESTE:
            continue
        processar_aba(ws)

    log("\nProcesso concluído.")


if __name__ == "__main__":
    processar_todas_as_abas()
