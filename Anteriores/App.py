import json
from pathlib import Path

import streamlit as st
import pandas as pd

import Fantasy as backend

APP_DIR = Path(__file__).resolve().parent
CACHE_FILE = APP_DIR / "nba_boxscore_cache.json"

st.set_page_config(
    page_title="Fantasy NBA Stats",
    page_icon="🏀",
    layout="wide",
)

st.title("🏀 Fantasy NBA Stats")
st.caption("Preenchimento de estatísticas da NBA com cache local, filtros e painel de status.")

def ler_cache():
    if not CACHE_FILE.exists():
        return {}
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def reset_estado():
    st.session_state.logs = []
    st.session_state.resumos = []
    st.session_state.ultima_execucao = None
    st.session_state.metricas = {
        "linhas_total": 0,
        "linhas_processadas": 0,
        "linhas_preenchidas": 0,
        "linhas_puladas": 0,
        "cache_hits": 0,
        "cache_misses": 0,
        "aba_atual": "",
        "linha_atual": "",
        "status_texto": "Aguardando execução",
    }

if "logs" not in st.session_state:
    reset_estado()

cache = ler_cache()

with st.sidebar:
    st.header("Configurações")

    try:
        abas_disponiveis = backend.listar_abas()
    except Exception as exc:
        abas_disponiveis = []
        st.error(f"Erro ao listar abas: {exc}")

    modo_execucao = st.radio(
        "Escopo",
        ["Todas as abas", "Apenas uma aba"],
        index=0
    )

    if modo_execucao == "Apenas uma aba" and abas_disponiveis:
        aba_escolhida = st.selectbox("Selecione a aba", abas_disponiveis)
    else:
        aba_escolhida = None

    somente_vazias = st.checkbox("Pular linhas já preenchidas", value=True)
    mostrar_logs = st.checkbox("Mostrar logs detalhados", value=True)

    st.divider()
    st.subheader("Cache")
    st.write(f"Jogos salvos: **{len(cache)}**")
    st.caption(str(CACHE_FILE))

top1, top2, top3, top4, top5, top6 = st.columns(6)
m = st.session_state.metricas
top1.metric("Linhas total", m["linhas_total"])
top2.metric("Processadas", m["linhas_processadas"])
top3.metric("Preenchidas", m["linhas_preenchidas"])
top4.metric("Puladas", m["linhas_puladas"])
top5.metric("Cache hits", m["cache_hits"])
top6.metric("Cache misses", m["cache_misses"])

status_box = st.empty()
progress_total = st.progress(0, text=m["status_texto"])
progress_aba = st.progress(0, text="Aguardando aba...")
resumo_box = st.empty()
logs_box = st.empty()

def atualizar_tela():
    m = st.session_state.metricas
    status_box.info(
        f"Aba atual: {m['aba_atual'] or '-'} | "
        f"Linha atual: {m['linha_atual'] or '-'} | "
        f"Status: {m['status_texto']}"
    )

    total = m["linhas_total"] if m["linhas_total"] > 0 else 1
    pct_aba = int((m["linhas_processadas"] / total) * 100)
    pct_aba = max(0, min(100, pct_aba))
    progress_aba.progress(pct_aba, text=f"Progresso da aba: {pct_aba}%")

    if mostrar_logs:
        logs_box.text_area(
            "Logs",
            "\n".join(st.session_state.logs[-300:]),
            height=320
        )
    else:
        logs_box.info("Logs ocultos.")

    if st.session_state.resumos:
        df = pd.DataFrame(st.session_state.resumos)
        resumo_box.dataframe(df, use_container_width=True)

def callback(evento):
    ev = evento.get("evento")

    if ev == "aba_inicio":
        st.session_state.metricas["aba_atual"] = evento.get("aba", "")
        st.session_state.metricas["linhas_total"] = evento.get("linhas_total", 0)
        st.session_state.metricas["linhas_processadas"] = 0
        st.session_state.metricas["status_texto"] = f"Iniciando aba {evento.get('aba', '')}"
        st.session_state.logs.append(f"[{evento.get('aba', '')}] Iniciando aba.")

    elif ev == "linha_pulada":
        st.session_state.metricas["linhas_puladas"] += 1
        st.session_state.logs.append(
            f"[{evento.get('aba', '')}] Linha {evento.get('linha', '')}: pulada ({evento.get('motivo', '')})"
        )

    elif ev == "linha_inicio":
        st.session_state.metricas["aba_atual"] = evento.get("aba", "")
        st.session_state.metricas["linha_atual"] = evento.get("linha", "")
        st.session_state.metricas["status_texto"] = (
            f"Processando {evento.get('jogador', '')} - GameID {evento.get('game_id', '')}"
        )
        st.session_state.logs.append(
            f"[{evento.get('aba', '')}] Linha {evento.get('linha', '')}: processando {evento.get('jogador', '')}"
        )

    elif ev == "linha_fim":
        st.session_state.metricas["linhas_processadas"] = evento.get("linhas_processadas", 0)
        st.session_state.metricas["linhas_preenchidas"] = evento.get("linhas_preenchidas", 0)
        st.session_state.metricas["linhas_puladas"] = evento.get("linhas_puladas", 0)
        st.session_state.metricas["cache_hits"] = evento.get("cache_hits", 0)
        st.session_state.metricas["cache_misses"] = evento.get("cache_misses", 0)
        st.session_state.logs.append(
            f"[{evento.get('aba', '')}] Linha {evento.get('linha', '')}: concluída ({evento.get('cache_status', '')})"
        )

    elif ev == "aba_fim":
        resumo = evento.get("resumo", {})
        st.session_state.resumos.append(resumo)
        st.session_state.metricas["status_texto"] = f"Aba concluída: {resumo.get('aba', '')}"
        st.session_state.logs.append(f"[{resumo.get('aba', '')}] Aba concluída.")

    atualizar_tela()

col_a, col_b = st.columns([1, 1])

with col_a:
    executar = st.button("▶️ Executar", type="primary", use_container_width=True)

with col_b:
    limpar = st.button("🧹 Limpar painel", use_container_width=True)

if limpar:
    reset_estado()
    atualizar_tela()

if executar:
    reset_estado()
    atualizar_tela()

    try:
        if modo_execucao == "Apenas uma aba" and aba_escolhida:
            progress_total.progress(10, text=f"Processando aba {aba_escolhida}...")
            resultado = backend.processar_aba(
                aba_escolhida,
                somente_vazias=somente_vazias,
                callback=callback
            )
            st.session_state.ultima_execucao = [resultado]
            progress_total.progress(100, text="Execução concluída.")
        else:
            abas = backend.listar_abas()
            total_abas = len(abas) if abas else 1
            resultados = []

            for i, aba in enumerate(abas, start=1):
                pct = int(((i - 1) / total_abas) * 100)
                progress_total.progress(pct, text=f"Processando aba {aba}...")
                resultado = backend.processar_aba(
                    aba,
                    somente_vazias=somente_vazias,
                    callback=callback
                )
                resultados.append(resultado)

            st.session_state.ultima_execucao = resultados
            progress_total.progress(100, text="Execução concluída.")

        st.success("Processamento finalizado com sucesso.")

    except Exception as exc:
        st.error(f"Erro durante a execução: {exc}")
        st.session_state.logs.append(f"ERRO: {exc}")
        atualizar_tela()

atualizar_tela()