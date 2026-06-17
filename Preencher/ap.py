import json
from pathlib import Path

import pandas as pd
import streamlit as st

import Fantasy as backend

APP_DIR = Path(__file__).resolve().parent
CACHE_FILE = APP_DIR / "nba_boxscore_cache.json"

st.set_page_config(
    page_title="Fantasy NBA Stats",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .block-container {
        padding-top: 1.2rem;
        padding-bottom: 1.2rem;
        max-width: 1400px;
    }
    .hero {
        background: linear-gradient(135deg, rgba(18,18,18,1) 0%, rgba(34,40,49,1) 55%, rgba(43,86,78,1) 100%);
        padding: 1.4rem 1.5rem;
        border-radius: 20px;
        color: white;
        border: 1px solid rgba(255,255,255,0.08);
        box-shadow: 0 12px 30px rgba(0,0,0,0.18);
        margin-bottom: 1rem;
    }
    .hero h1 {
        margin: 0;
        font-size: 2rem;
        line-height: 1.05;
    }
    .hero p {
        margin: 0.45rem 0 0 0;
        color: rgba(255,255,255,0.86);
        max-width: 820px;
    }
    .subtle-card {
        background: rgba(255,255,255,0.02);
        border: 1px solid rgba(128,128,128,0.18);
        border-radius: 18px;
        padding: 1rem 1rem;
        box-shadow: 0 6px 18px rgba(0,0,0,0.05);
    }
    .section-title {
        font-size: 1rem;
        font-weight: 700;
        margin-bottom: 0.6rem;
    }
    .metric-label {
        font-size: 0.85rem;
        opacity: 0.8;
    }
    .status-strip {
        padding: 0.9rem 1rem;
        border-radius: 16px;
        background: linear-gradient(90deg, rgba(0,104,84,0.12), rgba(0,104,84,0.04));
        border: 1px solid rgba(0,104,84,0.20);
        margin-bottom: 0.8rem;
    }
    .mini-note {
        font-size: 0.84rem;
        opacity: 0.8;
    }
    div[data-testid="stMetric"] {
        background: rgba(255,255,255,0.02);
        border: 1px solid rgba(128,128,128,0.18);
        padding: 0.75rem 0.85rem;
        border-radius: 16px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


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

st.markdown(
    """
    <div class="hero">
        <h1>Fantasy NBA Stats</h1>
        <p>Preenchimento das planilhas de jogos.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Configurações")

    try:
        abas_disponiveis = backend.listar_abas()
    except Exception as exc:
        abas_disponiveis = []
        st.error(f"Erro ao listar abas: {exc}")

    modo_execucao = st.radio(
        "Escopo da execução",
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
    st.subheader("Cache local")
    st.metric("Jogos salvos", len(cache))
    st.caption(str(CACHE_FILE))

    st.divider()
    st.markdown("<div class='mini-note'>Fluxo: Google Sheets → NBA API → cache local → escrita na planilha.</div>", unsafe_allow_html=True)

m = st.session_state.metricas

st.markdown("<div class='section-title'>Visão geral</div>", unsafe_allow_html=True)
mc1, mc2, mc3, mc4, mc5, mc6 = st.columns(6)
mc1.metric("Linhas totais", m["linhas_total"])
mc2.metric("Processadas", m["linhas_processadas"])
mc3.metric("Preenchidas", m["linhas_preenchidas"])
mc4.metric("Puladas", m["linhas_puladas"])
mc5.metric("Cache hits", m["cache_hits"])
mc6.metric("Cache misses", m["cache_misses"])

left, right = st.columns([1.2, 0.8])

with left:
    st.markdown("<div class='subtle-card'>", unsafe_allow_html=True)
    st.markdown("<div class='section-title'>Status e progresso</div>", unsafe_allow_html=True)
    status_box = st.empty()
    progress_total = st.progress(0, text=m["status_texto"])
    progress_aba = st.progress(0, text="Aguardando aba...")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div style='height: 0.8rem'></div>", unsafe_allow_html=True)
    st.markdown("<div class='subtle-card'>", unsafe_allow_html=True)
    st.markdown("<div class='section-title'>Resumo por aba</div>", unsafe_allow_html=True)
    resumo_box = st.empty()
    st.markdown("</div>", unsafe_allow_html=True)

with right:
    st.markdown("<div class='subtle-card'>", unsafe_allow_html=True)
    st.markdown("<div class='section-title'>Ações</div>", unsafe_allow_html=True)
    col_a, col_b = st.columns(2)
    with col_a:
        executar = st.button("▶️ Executar", type="primary", use_container_width=True)
    with col_b:
        limpar = st.button("🧹 Limpar", use_container_width=True)

    st.markdown("<div class='status-strip'><strong>Status atual:</strong><br/>Use os filtros na lateral para escolher a aba e o modo de execução. O painel mostra o avanço geral e o comportamento do cache.</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div style='height: 0.8rem'></div>", unsafe_allow_html=True)
    st.markdown("<div class='subtle-card'>", unsafe_allow_html=True)
    st.markdown("<div class='section-title'>Logs</div>", unsafe_allow_html=True)
    logs_box = st.empty()
    st.markdown("</div>", unsafe_allow_html=True)


def atualizar_tela():
    m = st.session_state.metricas
    status_box.markdown(
        f"""
        <div class="status-strip">
            <strong>Aba atual:</strong> {m['aba_atual'] or '-'} &nbsp;|&nbsp;
            <strong>Linha atual:</strong> {m['linha_atual'] or '-'} &nbsp;|&nbsp;
            <strong>Status:</strong> {m['status_texto']}
        </div>
        """,
        unsafe_allow_html=True,
    )

    total = m["linhas_total"] if m["linhas_total"] > 0 else 1
    pct_aba = int((m["linhas_processadas"] / total) * 100)
    pct_aba = max(0, min(100, pct_aba))
    progress_aba.progress(pct_aba, text=f"Progresso da aba: {pct_aba}%")

    if mostrar_logs:
        logs_box.text_area("Logs do processamento", "\n".join(st.session_state.logs[-300:]), height=420)
    else:
        logs_box.info("Logs ocultos.")

    if st.session_state.resumos:
        df = pd.DataFrame(st.session_state.resumos)
        resumo_box.dataframe(df, use_container_width=True, height=260)
    else:
        resumo_box.info("Nenhuma execução realizada ainda.")


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


if limpar:
    reset_estado()
    progress_total.progress(0, text="Aguardando execução")
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
