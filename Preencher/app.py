import json
from io import BytesIO
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
        padding-top: 1.1rem;
        padding-bottom: 1.2rem;
        max-width: 1420px;
    }
    .hero {
        background: linear-gradient(135deg, #101215 0%, #1f2833 52%, #1f5c51 100%);
        padding: 1.4rem 1.5rem;
        border-radius: 22px;
        color: white;
        border: 1px solid rgba(255,255,255,0.08);
        box-shadow: 0 14px 34px rgba(0,0,0,0.18);
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
        max-width: 900px;
    }
    .panel-card {
        background: rgba(255,255,255,0.02);
        border: 1px solid rgba(128,128,128,0.18);
        border-radius: 18px;
        padding: 1rem;
        box-shadow: 0 6px 18px rgba(0,0,0,0.05);
    }
    .section-title {
        font-size: 1rem;
        font-weight: 700;
        margin-bottom: 0.65rem;
    }
    .status-strip {
        padding: 0.95rem 1rem;
        border-radius: 15px;
        background: linear-gradient(90deg, rgba(0,104,84,0.12), rgba(0,104,84,0.04));
        border: 1px solid rgba(0,104,84,0.2);
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
    button[kind="primary"] {
        border-radius: 12px;
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


def resumo_df():
    if not st.session_state.resumos:
        return pd.DataFrame(columns=[
            "aba", "linhas_total", "linhas_processadas", "linhas_preenchidas",
            "linhas_puladas", "cache_hits", "cache_misses"
        ])
    return pd.DataFrame(st.session_state.resumos)


def resumo_csv_bytes(df):
    return df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")


def resumo_excel_bytes(df):
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="resumo", index=False)
    return buffer.getvalue()


if "logs" not in st.session_state:
    reset_estado()

cache = ler_cache()

st.markdown(
    """
    <div class="hero">
        <h1>Fantasy NBA Stats</h1>
        <p>Painel para preencher estatísticas da NBA no Google Sheets com cache local, filtros de execução, progresso por aba e visão consolidada dos resultados.</p>
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

    modo_execucao = st.radio("Escopo da execução", ["Todas as abas", "Apenas uma aba"], index=0)

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
    st.markdown("<div class='mini-note'>Fluxo: Google Sheets → NBA API → cache local → escrita na planilha.</div>", unsafe_allow_html=True)

m = st.session_state.metricas
c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Linhas totais", m["linhas_total"])
c2.metric("Processadas", m["linhas_processadas"])
c3.metric("Preenchidas", m["linhas_preenchidas"])
c4.metric("Puladas", m["linhas_puladas"])
c5.metric("Cache hits", m["cache_hits"])
c6.metric("Cache misses", m["cache_misses"])

tab_exec, tab_resumo, tab_logs = st.tabs(["Execução", "Resumo", "Logs"])

with tab_exec:
    left, right = st.columns([1.25, 0.75])
    with left:
        st.markdown("<div class='panel-card'>", unsafe_allow_html=True)
        st.markdown("<div class='section-title'>Status e progresso</div>", unsafe_allow_html=True)
        status_box = st.empty()
        progress_total = st.progress(0, text=m["status_texto"])
        progress_aba = st.progress(0, text="Aguardando aba...")
        st.markdown("</div>", unsafe_allow_html=True)
    with right:
        st.markdown("<div class='panel-card'>", unsafe_allow_html=True)
        st.markdown("<div class='section-title'>Ações</div>", unsafe_allow_html=True)
        col_a, col_b = st.columns(2)
        with col_a:
            executar = st.button("▶️ Executar", type="primary", use_container_width=True)
        with col_b:
            limpar = st.button("🧹 Limpar", use_container_width=True)
        st.markdown(
            "<div class='status-strip'><strong>Status atual:</strong><br/>Escolha o escopo na lateral, execute o processo e acompanhe o avanço geral e o progresso da aba em andamento.</div>",
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

with tab_resumo:
    st.markdown("<div class='panel-card'>", unsafe_allow_html=True)
    st.markdown("<div class='section-title'>Resumo por aba</div>", unsafe_allow_html=True)
    resumo_toolbar = st.columns([1, 1, 3])
    resumo_box = st.empty()
    st.markdown("</div>", unsafe_allow_html=True)

with tab_logs:
    st.markdown("<div class='panel-card'>", unsafe_allow_html=True)
    st.markdown("<div class='section-title'>Logs do processamento</div>", unsafe_allow_html=True)
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
        logs_box.text_area("Logs", "\n".join(st.session_state.logs[-400:]), height=430)
    else:
        logs_box.info("Logs ocultos.")

    df = resumo_df()
    if df.empty:
        resumo_box.info("Nenhuma execução realizada ainda.")
    else:
        resumo_box.dataframe(
            df,
            use_container_width=True,
            height=320,
            column_config={
                "aba": st.column_config.TextColumn("Aba", width="medium"),
                "linhas_total": st.column_config.NumberColumn("Linhas", format="%d"),
                "linhas_processadas": st.column_config.NumberColumn("Processadas", format="%d"),
                "linhas_preenchidas": st.column_config.NumberColumn("Preenchidas", format="%d"),
                "linhas_puladas": st.column_config.NumberColumn("Puladas", format="%d"),
                "cache_hits": st.column_config.NumberColumn("Cache hits", format="%d"),
                "cache_misses": st.column_config.NumberColumn("Cache misses", format="%d"),
            },
        )


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
        st.session_state.metricas["status_texto"] = f"Processando {evento.get('jogador', '')} - GameID {evento.get('game_id', '')}"
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
                callback=callback,
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
                    callback=callback,
                )
                resultados.append(resultado)

            st.session_state.ultima_execucao = resultados
            progress_total.progress(100, text="Execução concluída.")

        st.success("Processamento finalizado com sucesso.")

    except Exception as exc:
        st.error(f"Erro durante a execução: {exc}")
        st.session_state.logs.append(f"ERRO: {exc}")
        atualizar_tela()

with tab_resumo:
    df_resumo = resumo_df()
    with resumo_toolbar[0]:
        st.download_button(
            "⬇️ CSV",
            data=df_resumo.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig"),
            file_name="fantasy_resumo_execucao.csv",
            mime="text/csv",
            use_container_width=True,
            disabled=df_resumo.empty,
        )
    with resumo_toolbar[1]:
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df_resumo.to_excel(writer, sheet_name="resumo", index=False)
        st.download_button(
            "⬇️ Excel",
            data=buffer.getvalue(),
            file_name="fantasy_resumo_execucao.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            disabled=df_resumo.empty,
        )

atualizar_tela()