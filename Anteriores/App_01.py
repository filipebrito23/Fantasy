# app.py
import streamlit as st
import time
import json
import sys
from io import StringIO
from pathlib import Path

# Importa o seu script principal de processamento de dados. Certifique-se de que Fantasy.py está na mesma pasta deste app.py
import Fantasy as preencher_stats

APP_DIR = Path(__file__).resolve().parent
CACHE_FILE = APP_DIR / "nba_boxscore_cache.json"

st.set_page_config(page_title="Fantasy NBA Stats", page_icon="🏀", layout="wide")
st.title("📊 Fantasy NBA Stats • Interface")

# --- Helpers ----------------------------------------------------------------
def ler_cache():
    if not CACHE_FILE.exists():
        return {}
    try:
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}

def rodar_com_captura(func, *args, **kwargs):
    buf = StringIO()
    old_stdout = sys.stdout
    sys.stdout = buf
    try:
        result = func(*args, **kwargs)
    except Exception as exc:
        # garante que o exception trace fique no buffer também
        import traceback
        traceback.print_exc(file=buf)
        result = None
    finally:
        sys.stdout = old_stdout
    return buf.getvalue(), result

# --- Sidebar / config -------------------------------------------------------
st.sidebar.header("Configuração")
dev_mode = st.sidebar.checkbox("Modo desenvolvedor (logs detalhados)", value=False)
selecionar_aba = st.sidebar.checkbox("Permitir selecionar aba (rodar apenas uma)", value=True)

st.sidebar.markdown("---")
st.sidebar.markdown("Arquivo de cache:")
st.sidebar.code(str(CACHE_FILE))

# --- Status de cache --------------------------------------------------------
cache = ler_cache()
st.markdown("### Cache local")
if cache:
    st.write(f"Jogos salvos no cache: **{len(cache)}**")
else:
    st.info("Cache vazio — será criado na primeira execução.")

# --- Ações ------------------------------------------------------------------
st.markdown("### Execução")
col1, col2 = st.columns([1, 3])

with col1:
    if selecionar_aba:
        # tenta listar abas disponíveis chamando conectar_gsheets()
        try:
            spreadsheet = preencher_stats.conectar_gsheets()
            ws_titles = [ws.title for ws in spreadsheet.worksheets()]
        except Exception as exc:
            ws_titles = []
            if dev_mode:
                st.sidebar.error(f"Erro ao listar abas: {exc}")

        aba_escolhida = st.selectbox("Aba para processar", ["Todas"] + ws_titles)
    else:
        aba_escolhida = "Todas"

    rodar_btn = st.button("▶️ Executar")

with col2:
    st.markdown("Clique em Executar para iniciar o processamento. Logs e progresso aparecerão abaixo.")

log_area = st.empty()
progress_area = st.empty()
summary_area = st.empty()

# --- Execução quando o botão for pressionado --------------------------------
if rodar_btn:
    log_area.info("Preparando execução...")
    time.sleep(0.2)

    # Preparação: mostrar info do cache
    cache = ler_cache()
    if cache:
        log_area.write(f"Cache local contém {len(cache)} jogos.")
    else:
        log_area.write("Cache local vazio.")

    # Se o módulo preencher_stats tiver suporte para processar uma aba específica,
    # tentamos chamá-lo com esse parâmetro; caso contrário, chamamos o processamento geral.
    # Este trecho assume que preencher_stats.processar_todas_as_abas() existe.
    # Se houver uma função específica para processar 1 aba, podemos adaptá-la mais adiante.
    start_t = time.time()

    # Captura stdout do processamento
    def wrapper():
        # If user selected a specific sheet name, try to call a function that supports it.
        # We'll try multiple strategies in order so the app is robust:
        # 1) if preencher_stats.processar_aba(nome) exists, call it
        # 2) if preencher_stats.processar_worksheet(nome) exists, call it
        # 3) else, call preencher_stats.processar_todas_as_abas()
        aba = aba_escolhida
        if aba != "Todas":
            # Strategy 1
            if hasattr(preencher_stats, "processar_aba"):
                return preencher_stats.processar_aba(aba)
            # Strategy 2: try to pass the worksheet name to an existing function if it accepts args
            if hasattr(preencher_stats, "processar_todas_as_abas"):
                try:
                    import inspect
                    sig = inspect.signature(preencher_stats.processar_todas_as_abas)
                    if len(sig.parameters) == 1:
                        return preencher_stats.processar_todas_as_abas(aba)
                except Exception:
                    pass
        # Fallback: process all
        return preencher_stats.processar_todas_as_abas()

    log_text, _ = rodar_com_captura(wrapper)

    elapsed = time.time() - start_t

    # Exibe logs com scrolling
    log_area.code(log_text if log_text else "Nenhum log gerado.", language="text")

    # Mostra resumo simples
    summary = {
        "tempo_segundos": round(elapsed, 1),
        "cache_jogos_antes": len(cache),
    }
    summary_area.markdown("### Resumo")
    summary_area.write(summary)

    # Atualiza cache info pós-execução
    cache_after = ler_cache()
    st.markdown("#### Cache após execução")
    st.write(f"Jogos no cache: **{len(cache_after)}**")

    if dev_mode:
        st.sidebar.markdown("---")
        st.sidebar.subheader("Debug")
        st.sidebar.text(f"Tempo total: {elapsed:.1f}s")

st.markdown("---")
st.markdown("### Observações")
st.markdown(
    "- Este app faz *wrapper* em torno do seu módulo principal (Fantasy.py). "
    "Ele captura stdout e exibe os logs. "
)
st.markdown(
    "- Se quiser que o app chame uma função específica para processar uma única aba, "
    "adicione em Fantasy.py uma função `processar_aba(nome_da_aba)` que processe apenas essa aba."
)