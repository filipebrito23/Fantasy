import time
import json
from pathlib import Path

import streamlit as st

import Fantasy as backend

APP_DIR = Path(__file__).resolve().parent
CACHE_FILE = APP_DIR / "nba_boxscore_cache.json"

st.set_page_config(page_title="Fantasy NBA Stats", page_icon="🏀", layout="wide")
st.title("📊 Fantasy NBA Stats")

st.caption("Interface para preencher estatísticas da NBA com cache local, filtros e progresso.")

def ler_cache():
    if not CACHE_FILE.exists():
        return {}
    try:
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}

def fmt_num(v):
    try:
        return f"{int(v)}"
    except Exception:
        return "0"

if "logs" not in st.session_state:
    st.session_state.logs = []
if "resumo" not in st.session_state:
    st.session_state.resumo = []
if "executando" not in st.session_state:
    st.session_state.executando = False

with st.sidebar:
    st.header("Filtros")
    cache = ler_cache()
    abas = []
    try:
        abas = backend.listar_abas()
    except Exception as exc:
        st.error(f"Erro ao listar abas: {exc}")

    aba_escolhida = st.selectbox("Aba", ["Todas"] + abas if abas else ["Todas"])
    somente_vazias = st.checkbox("Pular linhas já preenchidas", value=True)
    mostrar_debug = st.checkbox("Mostrar logs detalhados", value=True)

    st.divider()
    st.subheader("Cache local")
    st.write(f"Jogos no cache: **{len(cache)}**")
    st.code(str(CACHE_FILE), language="text")

col1, col2, col3, col4 = st.columns(4)

painel_status = st.container()
barra = st.progress(0, text="Aguardando execução...")
log_box = st.empty()
resumo_box = st.empty()

def callback(evento, aba, linha, jogador, game_id, payload):
    if evento == "skip":
        msg = f"[{aba}] linha {linha}: pulada (já preenchida)"
    elif evento == "row_start":
        msg = f"[{aba}] linha {linha}: processando {jogador} ({game_id})"
    elif evento == "row_end":
        if payload:
            msg = f"[{aba}] linha {linha}: concluída"
        else:
            msg = f"[{aba}] linha {linha}: concluída sem stats"
    elif evento == "sheet_end":
        msg = f"[{aba}] aba finalizada"
    else:
        msg = str(evento)

    st.session_state.logs.append(msg)
    if len(st.session_state.logs) > 200:
        st.session_state.logs = st.session_state.logs[-200:]

def render_logs():
    if mostrar_debug:
        log_box.text_area("Logs", "\n".join(st.session_state.logs), height=360)
    else:
        log_box.info("Logs ocultos. Marque 'Mostrar logs detalhados' para exibir.")

def render_resumo(resumo_lista):
    if not resumo_lista:
        resumo_box.info("Nenhuma execução ainda.")
        return

    total_linhas = sum(r["linhas_total"] for r in resumo_lista)
    total_preenchidas = sum(r["linhas_preenchidas"] for r in resumo_lista)
    total_puladas = sum(r["linhas_puladas"] for r in resumo_lista)
    total_hits = sum(r["cache_hits"] for r in resumo_lista)
    total_misses = sum(r["cache_misses"] for r in resumo_lista)

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Linhas", fmt_num(total_linhas))
    c2.metric("Preenchidas", fmt_num(total_preenchidas))
    c3.metric("Puladas", fmt_num(total_puladas))
    c4.metric("Cache hits", fmt_num(total_hits))
    c5.metric("Cache misses", fmt_num(total_misses))

    st.dataframe(resumo_lista, use_container_width=True)

if st.button("▶️ Executar", type="primary", disabled=st.session_state.executando):
    st.session_state.executando = True
    st.session_state.logs = []
    st.session_state.resumo = []
    barra.progress(0, text="Iniciando...")

    with painel_status:
        st.status("Executando processamento...", expanded=True)

    try:
        if aba_escolhida == "Todas":
            abas_exec = abas
        else:
            abas_exec = [aba_escolhida]

        total_abas = max(len(abas_exec), 1)

        for idx, aba in enumerate(abas_exec, start=1):
            barra.progress(int((idx - 1) * 100 / total_abas), text=f"Processando aba {aba}...")
            st.session_state.logs.append(f"Iniciando aba: {aba}")
            render_logs()

            resultado = backend.processar_aba(
                aba,
                somente_vazias=somente_vazias,
                callback=callback
            )
            st.session_state.resumo.append(resultado)

            barra.progress(int(idx * 100 / total_abas), text=f"Aba {aba} concluída")
            render_logs()
            render_resumo(st.session_state.resumo)

        barra.progress(100, text="Processamento concluído.")
        st.success("Processamento finalizado com sucesso.")

    except Exception as exc:
        st.error(f"Erro durante a execução: {exc}")

    finally:
        st.session_state.executando = False

render_logs()
render_resumo(st.session_state.resumo)

st.divider()
st.caption("Fluxo: Google Sheets → NBA API → cache local → escrita na planilha.")