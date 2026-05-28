import os
import shutil
import tempfile

import pandas as pd
import streamlit as st

from planilha import ler_configuracao, ler_times, salvar_resultados, validar_times
from regras import gerar_jogos_grupos, registrar_resultado, calcular_classificacao_grupos, calcular_classificacao_terceiros

ARQUIVO_PADRAO = "copa_2026.xlsx"
st.set_page_config(page_title="Simulador Copa 2026", page_icon="⚽", layout="wide")

BANDEIRAS = {
    "África do Sul": "za", "Alemanha": "de", "Arábia Saudita": "sa", "Argentina": "ar", "Argélia": "dz",
    "Austrália": "au", "Áustria": "at", "Bélgica": "be", "Bosnia": "ba", "Brasil": "br",
    "Cabo Verde": "cv", "Canadá": "ca", "Catar": "qa", "Colômbia": "co", "Coreia do Sul": "kr",
    "Croácia": "hr", "Curaçao": "cw", "Costa do Marfim": "ci", "Egito": "eg", "Equador": "ec",
    "Escócia": "gb-sct", "Espanha": "es", "Estados Unidos": "us", "França": "fr", "Gana": "gh",
    "Haiti": "ht", "Holanda": "nl", "Inglaterra": "gb-eng", "Irã": "ir", "Iraque": "iq",
    "Japão": "jp", "Jordânia": "jo", "Marrocos": "ma", "México": "mx", "Noruega": "no",
    "Nova Zelândia": "nz", "Panamá": "pa", "Paraguai": "py", "Portugal": "pt", "RD Congo": "cd",
    "Senegal": "sn", "Suécia": "se", "Suíça": "ch", "Tchéquia": "cz", "Tunísia": "tn",
    "Turquia": "tr", "Uruguai": "uy", "Uzbequistão": "uz"
}


def limpar_texto(valor, padrao=""):
    if valor is None:
        return padrao
    try:
        if pd.isna(valor):
            return padrao
    except Exception:
        pass
    texto = str(valor).strip()
    if texto.lower() == "nan":
        return padrao
    return texto if texto else padrao


def aplicar_estilo():
    st.markdown(
        """
        <style>
        .stApp {background: linear-gradient(180deg, #f8fafc 0%, #eef2f7 100%);}
        .block-container {padding-top: 1.2rem; padding-bottom: 2rem; max-width: 1320px;}
        [data-testid="stSidebar"] {background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%); border-right: 1px solid rgba(255,255,255,0.08);}
        [data-testid="stSidebar"] * {color: #e2e8f0;}
        .hero-card {background: linear-gradient(135deg, #0f172a 0%, #1d4ed8 62%, #0f766e 100%); border-radius: 20px; padding: 1.25rem 1.4rem; color: white; box-shadow: 0 16px 38px rgba(15,23,42,0.18); margin-bottom: 1rem;}
        .hero-title {font-size: 1.9rem; font-weight: 800; margin-bottom: .2rem; color: white !important;}
        .hero-sub {opacity: .92; font-size: .98rem; color: rgba(255,255,255,.92) !important;}
        .section-label {font-size: .82rem; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; color: #1d4ed8; margin: .8rem 0 .6rem 0;}
        .game-card {background: #ffffff; border: 1px solid rgba(15,23,42,0.08); border-radius: 18px; padding: .95rem 1rem .85rem 1rem; box-shadow: 0 10px 24px rgba(15,23,42,0.06); margin: .45rem 0 .55rem 0;}
        .game-header {display:flex; justify-content:space-between; align-items:center; margin-bottom:.75rem; font-size:.9rem; color:#475569; font-weight:700;}
        .match-row {display:flex; align-items:center; justify-content:space-between; gap:1rem;}
        .team-box {display:flex; align-items:center; gap:.55rem; min-width:0; flex:1;}
        .team-box.right {justify-content:flex-end; text-align:right;}
        .team-name {font-weight:800; color:#0f172a; font-size:1rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;}
        .flag-img {width:34px; height:24px; border-radius:4px; object-fit:cover; border:1px solid rgba(15,23,42,.08); box-shadow:0 1px 4px rgba(0,0,0,.12);}
        .score-chip {background: linear-gradient(135deg, #0f172a 0%, #1d4ed8 100%); color:white; border-radius:14px; padding:.35rem .7rem; min-width:76px; text-align:center; font-weight:800; letter-spacing:.03em; font-size:.95rem;}
        .third-slot {display:flex; justify-content:center; align-items:center; min-height:42px;}
        .third-slot .stSelectbox {width: 100%;}
        div[data-testid="stMetric"] {background: rgba(255,255,255,0.95); border:1px solid rgba(15,23,42,0.08); border-radius:16px; padding:.35rem .55rem; box-shadow:0 6px 18px rgba(15,23,42,.05);}
        div[data-testid="stMetric"] label, div[data-testid="stMetric"] [data-testid="stMetricLabel"], div[data-testid="stMetric"] [data-testid="stMetricValue"] {color:#0f172a !important;}
        h1, h2, h3, h4, h5, h6, .stMarkdown p, .stSubheader, [data-testid="stHeader"] {color:#0f172a !important;}
        label[data-testid='stWidgetLabel'] p, .stSelectbox label p, .stNumberInput label p {color:#334155 !important; font-weight:700 !important;}
        [data-testid="stDataFrame"] * {color:#0f172a !important;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def flag_url(time):
    codigo = BANDEIRAS.get(limpar_texto(time), "")
    if not codigo:
        return ""
    return f"https://flagcdn.com/w80/{codigo}.png"


def team_label_html(time, align="left"):
    nome = limpar_texto(time, "A definir")
    url = flag_url(nome)
    if align == "right":
        if url:
            return f'<div class="team-box right"><div class="team-name">{nome}</div><img class="flag-img" src="{url}"></div>'
        return f'<div class="team-box right"><div class="team-name">{nome}</div></div>'
    if url:
        return f'<div class="team-box"><img class="flag-img" src="{url}"><div class="team-name">{nome}</div></div>'
    return f'<div class="team-box"><div class="team-name">{nome}</div></div>'


def placar_texto(row):
    if pd.isna(row.get("gols_casa")) or pd.isna(row.get("gols_fora")):
        return "vs"
    return f'{int(row.get("gols_casa"))} x {int(row.get("gols_fora"))}'


def mostrar_card_jogo(row, fase=''):
    rodada = limpar_texto(row.get('rodada', fase), fase)
    st.markdown(
        f"""
        <div class="game-card">
            <div class="game-header">
                <span>{limpar_texto(row.get('id_jogo',''))}</span>
                <span>{rodada}</span>
            </div>
            <div class="match-row">
                {team_label_html(row.get('time_A',''), 'left')}
                <div class="score-chip">{placar_texto(row)}</div>
                {team_label_html(row.get('time_B',''), 'right')}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def adicionar_bandeiras_df(df, col="time", nova_col="seleção"):
    base = df.copy()
    if col not in base.columns:
        return base
    base[nova_col] = base[col].apply(limpar_texto)
    return base


def formatar_time_com_bandeira(nome):
    nome_l = limpar_texto(nome)
    if not nome_l:
        return ""
    url = flag_url(nome_l)
    if url:
        return f"<span style=\"display:inline-flex;align-items:center;gap:8px;\"><img src=\"{url}\" style=\"width:22px;height:16px;border-radius:3px;object-fit:cover;border:1px solid rgba(15,23,42,.08);\"><span>{nome_l}</span></span>"
    return nome_l


def render_df_com_html(df, cols_html=None, cols_plain=None):
    if df is None or getattr(df, "empty", True):
        st.dataframe(df, use_container_width=True, hide_index=True)
        return
    display = df.copy()
    cols_html = cols_html or []
    cols_plain = cols_plain or []
    for col in cols_html:
        if col in display.columns:
            display[col] = display[col].apply(formatar_time_com_bandeira)
    for col in cols_plain:
        if col in display.columns:
            display[col] = display[col].apply(limpar_texto)
    st.markdown(display.to_html(escape=False, index=False), unsafe_allow_html=True)


def render_header():
    st.markdown(
        """
        <div class="hero-card">
            <div class="hero-title">⚽ Simulador Copa 2026</div>
            <div class="hero-sub">Painel de grupos, mata-mata e final com leitura mais limpa e confrontos com bandeiras.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def inicializar_estado():
    defaults = {"arquivo_base": ARQUIVO_PADRAO, "dados_carregados": False, "config": None, "df_times": None, "df_jogos": None, "df_classificacao": None, "df_terceiros": None, "df_jogos_16": None, "df_jogos_8": None, "df_jogos_4": None, "df_jogos_2": None, "df_final": None, "mensagem": ""}
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

@st.cache_data
def carregar_base(caminho_arquivo):
    config = ler_configuracao(caminho_arquivo)
    df_times = ler_times(caminho_arquivo)
    validar_times(df_times, config)
    df_jogos = gerar_jogos_grupos(df_times)
    return config, df_times, df_jogos


def recalcular_tabelas():
    st.session_state.df_classificacao = calcular_classificacao_grupos(st.session_state.df_times, st.session_state.df_jogos, st.session_state.config)
    st.session_state.df_terceiros = calcular_classificacao_terceiros(st.session_state.df_classificacao, st.session_state.config)
    try: st.session_state.df_jogos_16 = carregar_jogos_16(st.session_state.arquivo_base)
    except Exception: st.session_state.df_jogos_16 = pd.DataFrame()
    try: st.session_state.df_jogos_8 = carregar_jogos_8(st.session_state.arquivo_base)
    except Exception: st.session_state.df_jogos_8 = pd.DataFrame()
    try: st.session_state.df_jogos_4 = carregar_jogos_4(st.session_state.arquivo_base)
    except Exception: st.session_state.df_jogos_4 = pd.DataFrame()
    try: st.session_state.df_jogos_2 = carregar_jogos_2(st.session_state.arquivo_base)
    except Exception: st.session_state.df_jogos_2 = pd.DataFrame()
    try: st.session_state.df_final = carregar_final(st.session_state.arquivo_base)
    except Exception: st.session_state.df_final = pd.DataFrame()


def carregar_base_arquivo(caminho_arquivo):
    config, df_times, df_jogos = carregar_base(caminho_arquivo)
    st.session_state.config = config
    st.session_state.df_times = df_times
    st.session_state.df_jogos = df_jogos
    st.session_state.dados_carregados = True
    recalcular_tabelas()
    st.session_state.mensagem = "Base carregada com sucesso."


def jogos_para_edicao(df_jogos_grupo: pd.DataFrame) -> pd.DataFrame:
    df = df_jogos_grupo.copy()
    df["placar_atual"] = df.apply(lambda x: "-" if pd.isna(x["gols_casa"]) or pd.isna(x["gols_fora"]) else f"{int(x['gols_casa'])} x {int(x['gols_fora'])}", axis=1)
    return df[["id_jogo", "grupo", "rodada", "ordem_casa", "time_casa", "gols_casa", "gols_fora", "time_fora", "ordem_fora", "placar_atual"]].copy()


def aplicar_edicoes(df_editado: pd.DataFrame):
    df_base = st.session_state.df_jogos.copy()
    for _, linha in df_editado.iterrows():
        id_jogo = linha["id_jogo"]
        gols_casa = linha["gols_casa"]
        gols_fora = linha["gols_fora"]
        if pd.isna(gols_casa) and pd.isna(gols_fora):
            continue
        if pd.isna(gols_casa) != pd.isna(gols_fora):
            raise ValueError(f"Preencha ambos os gols no jogo {id_jogo}.")
        df_base = registrar_resultado(df_base, id_jogo, int(gols_casa), int(gols_fora))
    st.session_state.df_jogos = df_base
    recalcular_tabelas()


def salvar_arquivo():
    tmp_dir = tempfile.mkdtemp()
    caminho_saida = os.path.join(tmp_dir, "copa_2026_bolao_atualizada.xlsx")
    shutil.copyfile(st.session_state.arquivo_base, caminho_saida)
    salvar_resultados(caminho_saida, st.session_state.df_jogos, st.session_state.df_classificacao, st.session_state.df_terceiros)
    with pd.ExcelWriter(caminho_saida, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
        st.session_state.df_jogos_16.to_excel(writer, sheet_name="jogos_16", index=False)
        st.session_state.df_jogos_8.to_excel(writer, sheet_name="jogos_8", index=False)
        st.session_state.df_jogos_4.to_excel(writer, sheet_name="jogos_4", index=False)
        st.session_state.df_jogos_2.to_excel(writer, sheet_name="jogos_2", index=False)
        st.session_state.df_final.to_excel(writer, sheet_name="Final", index=False)
    return caminho_saida


def pagina_edicao():
    st.markdown('<div class="section-label">Fase de grupos</div>', unsafe_allow_html=True)
    grupos = sorted(st.session_state.df_times["grupo"].unique())
    grupo_escolhido = st.selectbox("Grupo", grupos, key="grupo_edicao")
    jogos_grupo = st.session_state.df_jogos[st.session_state.df_jogos["grupo"] == grupo_escolhido].copy().sort_values(["rodada", "id_jogo"])
    df_editor = jogos_para_edicao(jogos_grupo)
    with st.form(f"form_grupo_{grupo_escolhido}"):
        df_editado = st.data_editor(df_editor, hide_index=True, use_container_width=True, disabled=["id_jogo", "grupo", "rodada", "ordem_casa", "time_casa", "time_fora", "ordem_fora", "placar_atual"], column_config={"gols_casa": st.column_config.NumberColumn("Gols Casa", min_value=0, max_value=30, step=1), "gols_fora": st.column_config.NumberColumn("Gols Fora", min_value=0, max_value=30, step=1)}, key=f"editor_{grupo_escolhido}")
        c1, c2 = st.columns(2)
        aplicar = c1.form_submit_button("Aplicar", use_container_width=True)
        recalc = c2.form_submit_button("Recalcular", use_container_width=True)
    if aplicar:
        try:
            aplicar_edicoes(df_editado)
            st.session_state.mensagem = f"Placares do Grupo {grupo_escolhido} atualizados."
            st.rerun()
        except Exception as e:
            st.session_state.mensagem = f"Erro ao aplicar: {e}"
            st.rerun()
    if recalc:
        recalcular_tabelas()
        st.session_state.mensagem = "Tabelas recalculadas."
        st.rerun()
    st.subheader("Classificação do grupo")
    classificacao_grupo = st.session_state.df_classificacao[st.session_state.df_classificacao["grupo"] == grupo_escolhido].copy().sort_values("posicao")
    classificacao_grupo = classificacao_grupo[["posicao", "grupo", "time", "vitorias", "empates", "derrotas", "gols_pro", "gols_contra", "saldo_gols", "pontos", "status_classificacao"]].copy()
    render_df_com_html(classificacao_grupo, cols_html=["time"])


def dashboard():
    st.markdown('<div class="section-label">Dashboard geral</div>', unsafe_allow_html=True)
    total = len(st.session_state.df_jogos)
    preenchidos = len(st.session_state.df_jogos.dropna(subset=["gols_casa", "gols_fora"]))
    progresso = preenchidos / total if total else 0
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total de jogos", total)
    c2.metric("Jogos preenchidos", preenchidos)
    c3.metric("Progresso", f"{progresso:.1%}")
    c4.metric("Classificados", len(st.session_state.df_classificacao[st.session_state.df_classificacao["status_classificacao"] != "eliminado"]))
    st.progress(progresso)
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["Resumo", "Classificação", "Terceiros", "Grupos", "16-avos", "Playoff"])
    with tab1:
        resumo = st.session_state.df_classificacao.copy()
        resumo["faixa"] = resumo["status_classificacao"].map({"classificado": "Direto", "terceiro": "Terceiro", "eliminado": "Eliminado"})
        resumo = resumo[["grupo", "posicao", "time", "pontos", "saldo_gols", "gols_pro", "status_classificacao", "faixa"]].copy()
        render_df_com_html(resumo, cols_html=["time"])
    with tab2:
        classif = st.session_state.df_classificacao.copy()
        classif = classif[["grupo", "posicao", "time", "vitorias", "empates", "derrotas", "gols_pro", "gols_contra", "saldo_gols", "pontos", "status_classificacao"]].copy()
        render_df_com_html(classif, cols_html=["time"])
    with tab3:
        terceiros = st.session_state.df_terceiros.copy()
        terceiros["top_8"] = terceiros.index < int(st.session_state.config.get("classifica_melhores_terceiros", 8))
        render_df_com_html(terceiros, cols_html=["time"])
    with tab4:
        st.dataframe(st.session_state.df_jogos, use_container_width=True, hide_index=True)
    with tab5:
        st.dataframe(jogos16_para_edicao(st.session_state.df_jogos_16), use_container_width=True, hide_index=True)
    with tab6:
        st.caption("Visual rápido do mata-mata.")
        if st.session_state.df_final is not None and not getattr(st.session_state.df_final, 'empty', True):
            for _, row in final_para_edicao(st.session_state.df_final).iterrows():
                mostrar_card_jogo(row)


def carregar_jogos_8(caminho_arquivo):
    try:
        df = pd.read_excel(caminho_arquivo, sheet_name="jogos_8")
        for col in ["Simbolo_A", "Simbolo_B", "time_A", "time_B", "time_A_resolvido", "time_B_resolvido", "vencedor_penaltis"]:
            if col not in df.columns: df[col] = ""
        for col in ["Simbolo_A", "Simbolo_B", "time_A", "time_B", "time_A_resolvido", "time_B_resolvido", "vencedor_penaltis"]:
            df[col] = df[col].fillna("").astype(str)
        return df
    except Exception:
        return pd.DataFrame()


def carregar_jogos_4(caminho_arquivo):
    try:
        df = pd.read_excel(caminho_arquivo, sheet_name="jogos_4")
        for col in ["Simbolo_A", "Simbolo_B", "time_A", "time_B", "time_A_resolvido", "time_B_resolvido", "vencedor_penaltis"]:
            if col not in df.columns: df[col] = ""
        for col in ["Simbolo_A", "Simbolo_B", "time_A", "time_B", "time_A_resolvido", "time_B_resolvido", "vencedor_penaltis"]:
            df[col] = df[col].fillna("").astype(str)
        return df
    except Exception:
        return pd.DataFrame()


def carregar_jogos_2(caminho_arquivo):
    try:
        df = pd.read_excel(caminho_arquivo, sheet_name="jogos_2")
        for col in ["Simbolo_A", "Simbolo_B", "time_A", "time_B", "time_A_resolvido", "time_B_resolvido", "vencedor_penaltis"]:
            if col not in df.columns: df[col] = ""
        for col in ["Simbolo_A", "Simbolo_B", "time_A", "time_B", "time_A_resolvido", "time_B_resolvido", "vencedor_penaltis"]:
            df[col] = df[col].fillna("").astype(str)
        return df
    except Exception:
        return pd.DataFrame()


def carregar_final(caminho_arquivo):
    try:
        df = pd.read_excel(caminho_arquivo, sheet_name="Final")
        for col in ["Simbolo_A", "Simbolo_B", "time_A", "time_B", "time_A_resolvido", "time_B_resolvido", "vencedor_penaltis"]:
            if col not in df.columns: df[col] = ""
        for col in ["Simbolo_A", "Simbolo_B", "time_A", "time_B", "time_A_resolvido", "time_B_resolvido", "vencedor_penaltis"]:
            df[col] = df[col].fillna("").astype(str)
        return df
    except Exception:
        return pd.DataFrame()


def carregar_jogos_16(caminho_arquivo):
    df = pd.read_excel(caminho_arquivo, sheet_name="jogos_16")
    for col in ["Simbolo_A", "Simbolo_B", "time_A", "time_B", "time_A_resolvido", "time_B_resolvido", "selecao_terceiro_A", "selecao_terceiro_B", "vencedor_penaltis"]:
        if col not in df.columns: df[col] = ""
    for col in ["Simbolo_A", "Simbolo_B", "time_A", "time_B", "time_A_resolvido", "time_B_resolvido", "selecao_terceiro_A", "selecao_terceiro_B", "vencedor_penaltis"]:
        df[col] = df[col].fillna("").astype(str)
    if "placar_atual" not in df.columns:
        df["placar_atual"] = df.apply(lambda x: "-" if pd.isna(x.get("gols_casa")) or pd.isna(x.get("gols_fora")) else f"{int(x['gols_casa'])} x {int(x['gols_fora'])}", axis=1)
    return df


def resolver_jogos_16(df_jogos_16, df_classificacao, df_terceiros):
    df = df_jogos_16.copy()
    mapa = {f"{int(r['posicao'])}{r['grupo']}": r['time'] for _, r in df_classificacao.iterrows() if r['posicao'] in [1,2]}
    terceiros_validos = df_terceiros[df_terceiros["classifica_16avos"] == "sim"]["time"].tolist()
    for idx, row in df.iterrows():
        simb_a = str(row.get("Simbolo_A", "")).strip()
        simb_b = str(row.get("Simbolo_B", "")).strip()
        sel_a = str(row.get("selecao_terceiro_A", "")).strip()
        sel_b = str(row.get("selecao_terceiro_B", "")).strip()
        time_a = mapa.get(simb_a, "")
        time_b = mapa.get(simb_b, "")
        if simb_a.startswith("3") and sel_a in terceiros_validos: time_a = sel_a
        if simb_b.startswith("3") and sel_b in terceiros_validos: time_b = sel_b
        df.at[idx, "time_A"] = time_a
        df.at[idx, "time_B"] = time_b
        df.at[idx, "time_A_resolvido"] = time_a
        df.at[idx, "time_B_resolvido"] = time_b
    return df


def jogos16_para_edicao(df_jogos_16):
    return resolver_jogos_16(df_jogos_16, st.session_state.df_classificacao, st.session_state.df_terceiros)


def obter_vencedor_jogo(row):
    gols_casa = row.get("gols_casa")
    gols_fora = row.get("gols_fora")
    time_a = str(row.get("time_A_resolvido", row.get("time_A", ""))).strip()
    time_b = str(row.get("time_B_resolvido", row.get("time_B", ""))).strip()
    vencedor_pen = str(row.get("vencedor_penaltis", "")).strip()
    if pd.isna(gols_casa) or pd.isna(gols_fora): return ""
    if gols_casa > gols_fora: return time_a
    if gols_fora > gols_casa: return time_b
    return vencedor_pen if vencedor_pen in [time_a, time_b] else ""


def perdedor_jogo(row):
    gols_casa = row.get("gols_casa")
    gols_fora = row.get("gols_fora")
    time_a = str(row.get("time_A_resolvido", row.get("time_A", ""))).strip()
    time_b = str(row.get("time_B_resolvido", row.get("time_B", ""))).strip()
    vencedor = obter_vencedor_jogo(row)
    if pd.isna(gols_casa) or pd.isna(gols_fora) or not vencedor: return ""
    if vencedor == time_a: return time_b
    if vencedor == time_b: return time_a
    return ""


def resolver_jogos_8(df_jogos_8, df_jogos_16):
    df = df_jogos_8.copy()
    base16 = resolver_jogos_16(df_jogos_16, st.session_state.df_classificacao, st.session_state.df_terceiros)
    vencedores = {f"W{row['id_jogo']}": obter_vencedor_jogo(row) for _, row in base16.iterrows()}
    for idx, row in df.iterrows():
        simb_a = str(row.get("Simbolo_A", "")).strip()
        simb_b = str(row.get("Simbolo_B", "")).strip()
        time_a = vencedores.get(simb_a, "") if simb_a.startswith("W") else str(row.get("time_A", "")).strip()
        time_b = vencedores.get(simb_b, "") if simb_b.startswith("W") else str(row.get("time_B", "")).strip()
        df.at[idx, "time_A"] = time_a
        df.at[idx, "time_B"] = time_b
        if "time_A_resolvido" in df.columns: df.at[idx, "time_A_resolvido"] = time_a
        if "time_B_resolvido" in df.columns: df.at[idx, "time_B_resolvido"] = time_b
    return df


def jogos8_para_edicao(df_jogos_8):
    return resolver_jogos_8(df_jogos_8, st.session_state.df_jogos_16)


def resolver_jogos_4(df_jogos_4, df_jogos_8):
    df = df_jogos_4.copy()
    base8 = resolver_jogos_8(df_jogos_8, st.session_state.df_jogos_16)
    vencedores = {f"W{row['id_jogo']}": obter_vencedor_jogo(row) for _, row in base8.iterrows()}
    for idx, row in df.iterrows():
        simb_a = str(row.get("Simbolo_A", "")).strip()
        simb_b = str(row.get("Simbolo_B", "")).strip()
        time_a = vencedores.get(simb_a, "") if simb_a.startswith("W") else str(row.get("time_A", "")).strip()
        time_b = vencedores.get(simb_b, "") if simb_b.startswith("W") else str(row.get("time_B", "")).strip()
        df.at[idx, "time_A"] = time_a
        df.at[idx, "time_B"] = time_b
        if "time_A_resolvido" in df.columns: df.at[idx, "time_A_resolvido"] = time_a
        if "time_B_resolvido" in df.columns: df.at[idx, "time_B_resolvido"] = time_b
    return df


def jogos4_para_edicao(df_jogos_4):
    return resolver_jogos_4(df_jogos_4, st.session_state.df_jogos_8)


def resolver_jogos_2(df_jogos_2, df_jogos_4):
    df = df_jogos_2.copy()
    base4 = resolver_jogos_4(df_jogos_4, st.session_state.df_jogos_8)
    vencedores = {f"W{row['id_jogo']}": obter_vencedor_jogo(row) for _, row in base4.iterrows()}
    for idx, row in df.iterrows():
        simb_a = str(row.get("Simbolo_A", "")).strip()
        simb_b = str(row.get("Simbolo_B", "")).strip()
        time_a = vencedores.get(simb_a, "") if simb_a.startswith("W") else str(row.get("time_A", "")).strip()
        time_b = vencedores.get(simb_b, "") if simb_b.startswith("W") else str(row.get("time_B", "")).strip()
        df.at[idx, "time_A"] = time_a
        df.at[idx, "time_B"] = time_b
        if "time_A_resolvido" in df.columns: df.at[idx, "time_A_resolvido"] = time_a
        if "time_B_resolvido" in df.columns: df.at[idx, "time_B_resolvido"] = time_b
    return df


def jogos2_para_edicao(df_jogos_2):
    return resolver_jogos_2(df_jogos_2, st.session_state.df_jogos_4)


def resolver_final(df_final, df_jogos_2):
    if df_final is None: return pd.DataFrame()
    df = df_final.copy()
    base2 = resolver_jogos_2(df_jogos_2, st.session_state.df_jogos_4)
    vencedores = {f"W{row['id_jogo']}": obter_vencedor_jogo(row) for _, row in base2.iterrows()}
    perdedores = {f"L{row['id_jogo']}": perdedor_jogo(row) for _, row in base2.iterrows()}
    for idx, row in df.iterrows():
        simb_a = str(row.get("Simbolo_A", "")).strip()
        simb_b = str(row.get("Simbolo_B", "")).strip()
        if simb_a.startswith("W"): time_a = vencedores.get(simb_a, "")
        elif simb_a.startswith("L"): time_a = perdedores.get(simb_a, "")
        else: time_a = str(row.get("time_A", "")).strip()
        if simb_b.startswith("W"): time_b = vencedores.get(simb_b, "")
        elif simb_b.startswith("L"): time_b = perdedores.get(simb_b, "")
        else: time_b = str(row.get("time_B", "")).strip()
        df.at[idx, "time_A"] = time_a
        df.at[idx, "time_B"] = time_b
        if "time_A_resolvido" in df.columns: df.at[idx, "time_A_resolvido"] = time_a
        if "time_B_resolvido" in df.columns: df.at[idx, "time_B_resolvido"] = time_b
    return df


def final_para_edicao(df_final):
    return resolver_final(df_final, st.session_state.df_jogos_2)


def pagina_round32():
    st.markdown('<div class="section-label">16-avos de final</div>', unsafe_allow_html=True)
    if st.session_state.df_jogos_16 is None or getattr(st.session_state.df_jogos_16, "empty", True):
        st.info("A aba jogos_16 não foi carregada.")
        return
    df_view = jogos16_para_edicao(st.session_state.df_jogos_16).reset_index(drop=True)
    terceiros_opts = [""] + st.session_state.df_terceiros[st.session_state.df_terceiros["classifica_16avos"] == "sim"]["time"].tolist()
    with st.form("form_jogos_16"):
        edited_rows = []
        for i, row in df_view.iterrows():
            mostrar_card_jogo(row, "16-avos")
            linha_visual = st.columns([1.4, 1.0, 1.4])
            if str(row.get('Simbolo_A', '')).strip().startswith("3"):
                with linha_visual[0]:
                    terceiro_a = st.selectbox("Terceiro A", terceiros_opts, index=terceiros_opts.index(row.get("selecao_terceiro_A", "")) if row.get("selecao_terceiro_A", "") in terceiros_opts else 0, key=f"ta_{i}")
            else:
                terceiro_a = ""
                linha_visual[0].markdown(" ")
            linha_visual[1].markdown(" ")
            if str(row.get('Simbolo_B', '')).strip().startswith("3"):
                with linha_visual[2]:
                    terceiro_b = st.selectbox("Terceiro B", terceiros_opts, index=terceiros_opts.index(row.get("selecao_terceiro_B", "")) if row.get("selecao_terceiro_B", "") in terceiros_opts else 0, key=f"tb_{i}")
            else:
                terceiro_b = ""
                linha_visual[2].markdown(" ")
            bottom = st.columns([1.0, 1.0, 1.3])
            gols_casa = bottom[0].number_input("Casa", min_value=0, max_value=30, value=int(row["gols_casa"]) if pd.notna(row["gols_casa"]) else 0, step=1, key=f"gc_{i}")
            gols_fora = bottom[1].number_input("Fora", min_value=0, max_value=30, value=int(row["gols_fora"]) if pd.notna(row["gols_fora"]) else 0, step=1, key=f"gf_{i}")
            op_pen = ["", limpar_texto(row.get('time_A_resolvido', '')), limpar_texto(row.get('time_B_resolvido', ''))]
            vencedor_pen = ""
            if gols_casa == gols_fora and limpar_texto(row.get('time_A_resolvido', '')) and limpar_texto(row.get('time_B_resolvido', '')):
                vencedor_pen = bottom[2].selectbox("Penais", op_pen, index=0 if limpar_texto(row.get("vencedor_penaltis", "")) not in op_pen else op_pen.index(limpar_texto(row.get("vencedor_penaltis", ""))), key=f"vp_{i}")
            else:
                bottom[2].markdown(" ")
            edited_rows.append({"id_jogo": row["id_jogo"], "selecao_terceiro_A": terceiro_a, "selecao_terceiro_B": terceiro_b, "gols_casa": gols_casa, "gols_fora": gols_fora, "vencedor_penaltis": vencedor_pen})
        salvar = st.form_submit_button("Salvar 16-avos", use_container_width=True)
    if salvar:
        df_base = st.session_state.df_jogos_16.copy()
        for item in edited_rows:
            idx = df_base.index[df_base["id_jogo"] == item["id_jogo"]]
            if len(idx) == 0: continue
            j = idx[0]
            for k in ["selecao_terceiro_A", "selecao_terceiro_B", "vencedor_penaltis"]:
                if k in df_base.columns: df_base.loc[j, k] = item.get(k, "")
            df_base.loc[j, "gols_casa"] = item["gols_casa"]
            df_base.loc[j, "gols_fora"] = item["gols_fora"]
            df_base.loc[j, "placar_atual"] = f"{item['gols_casa']} x {item['gols_fora']}"
        st.session_state.df_jogos_16 = resolver_jogos_16(df_base, st.session_state.df_classificacao, st.session_state.df_terceiros)
        st.session_state.mensagem = "Round of 32 atualizado."
        st.rerun()


def pagina_oitavas():
    st.markdown('<div class="section-label">Playoff</div>', unsafe_allow_html=True)
    if st.session_state.df_jogos_8 is None or getattr(st.session_state.df_jogos_8, "empty", True):
        st.info("A aba jogos_8 não foi carregada.")
        return
    df_view = jogos8_para_edicao(st.session_state.df_jogos_8).reset_index(drop=True)
    with st.form("form_jogos_8"):
        edited_rows = []
        for i, row in df_view.iterrows():
            mostrar_card_jogo(row, "Oitavas")
            cols = st.columns([1.0, 1.0, 1.4])
            gols_casa = cols[0].number_input("Casa", min_value=0, max_value=30, value=int(row["gols_casa"]) if pd.notna(row["gols_casa"]) else 0, step=1, key=f"g8c_{i}")
            gols_fora = cols[1].number_input("Fora", min_value=0, max_value=30, value=int(row["gols_fora"]) if pd.notna(row["gols_fora"]) else 0, step=1, key=f"g8f_{i}")
            opcoes_penal = ["", limpar_texto(row.get('time_A', '')), limpar_texto(row.get('time_B', ''))]
            if gols_casa == gols_fora and limpar_texto(row.get('time_A', '')) and limpar_texto(row.get('time_B', '')):
                vencedor_pen = cols[2].selectbox("Penais", opcoes_penal, index=0 if limpar_texto(row.get("vencedor_penaltis", "")) not in opcoes_penal else opcoes_penal.index(limpar_texto(row.get("vencedor_penaltis", ""))), key=f"g8p_{i}")
            else:
                cols[2].markdown(" ")
                vencedor_pen = ""
            edited_rows.append({"id_jogo": row["id_jogo"], "gols_casa": gols_casa, "gols_fora": gols_fora, "vencedor_penaltis": vencedor_pen})
        salvar = st.form_submit_button("Salvar Oitavas", use_container_width=True)
    if salvar:
        df_base = st.session_state.df_jogos_8.copy()
        for item in edited_rows:
            idx = df_base.index[df_base["id_jogo"] == item["id_jogo"]]
            if len(idx) == 0: continue
            j = idx[0]
            df_base.loc[j, "gols_casa"] = item["gols_casa"]
            df_base.loc[j, "gols_fora"] = item["gols_fora"]
            if "vencedor_penaltis" in df_base.columns: df_base.loc[j, "vencedor_penaltis"] = item.get("vencedor_penaltis", "")
        st.session_state.df_jogos_8 = resolver_jogos_8(df_base, st.session_state.df_jogos_16)
        st.session_state.df_jogos_4 = resolver_jogos_4(st.session_state.df_jogos_4, st.session_state.df_jogos_8)
        st.session_state.mensagem = "Oitavas atualizadas."
        st.rerun()

    st.subheader("Quartas de Final")
    if st.session_state.df_jogos_4 is None or getattr(st.session_state.df_jogos_4, "empty", True):
        st.info("A aba jogos_4 não foi carregada.")
        return
    df_quartas = jogos4_para_edicao(st.session_state.df_jogos_4).reset_index(drop=True)
    with st.form("form_jogos_4"):
        edited_quartas = []
        for i, row in df_quartas.iterrows():
            mostrar_card_jogo(row, "Quartas")
            cols = st.columns([1.0, 1.0, 1.4])
            gols_casa = cols[0].number_input("Casa", min_value=0, max_value=30, value=int(row["gols_casa"]) if pd.notna(row["gols_casa"]) else 0, step=1, key=f"g4c_{i}")
            gols_fora = cols[1].number_input("Fora", min_value=0, max_value=30, value=int(row["gols_fora"]) if pd.notna(row["gols_fora"]) else 0, step=1, key=f"g4f_{i}")
            opcoes_penal = ["", limpar_texto(row.get('time_A', '')), limpar_texto(row.get('time_B', ''))]
            if gols_casa == gols_fora and limpar_texto(row.get('time_A', '')) and limpar_texto(row.get('time_B', '')):
                vencedor_pen = cols[2].selectbox("Penais", opcoes_penal, index=0 if limpar_texto(row.get("vencedor_penaltis", "")) not in opcoes_penal else opcoes_penal.index(limpar_texto(row.get("vencedor_penaltis", ""))), key=f"g4p_{i}")
            else:
                cols[2].markdown(" ")
                vencedor_pen = ""
            edited_quartas.append({"id_jogo": row["id_jogo"], "gols_casa": gols_casa, "gols_fora": gols_fora, "vencedor_penaltis": vencedor_pen})
        salvar_quartas = st.form_submit_button("Salvar Quartas", use_container_width=True)
    if salvar_quartas:
        df_base_4 = st.session_state.df_jogos_4.copy()
        for item in edited_quartas:
            idx = df_base_4.index[df_base_4["id_jogo"] == item["id_jogo"]]
            if len(idx) == 0: continue
            j = idx[0]
            df_base_4.loc[j, "gols_casa"] = item["gols_casa"]
            df_base_4.loc[j, "gols_fora"] = item["gols_fora"]
            if "vencedor_penaltis" in df_base_4.columns: df_base_4.loc[j, "vencedor_penaltis"] = item.get("vencedor_penaltis", "")
        st.session_state.df_jogos_4 = resolver_jogos_4(df_base_4, st.session_state.df_jogos_8)
        st.session_state.df_jogos_2 = resolver_jogos_2(st.session_state.df_jogos_2, st.session_state.df_jogos_4)
        st.session_state.mensagem = "Quartas atualizadas."
        st.rerun()

    st.subheader("Semi-Final")
    if st.session_state.df_jogos_2 is None or getattr(st.session_state.df_jogos_2, "empty", True):
        st.info("A aba jogos_2 não foi carregada.")
        return
    df_semis = jogos2_para_edicao(st.session_state.df_jogos_2).reset_index(drop=True)
    with st.form("form_jogos_2"):
        edited_semis = []
        for i, row in df_semis.iterrows():
            mostrar_card_jogo(row, "Semi-Final")
            cols = st.columns([1.0, 1.0, 1.4])
            gols_casa = cols[0].number_input("Casa", min_value=0, max_value=30, value=int(row["gols_casa"]) if pd.notna(row["gols_casa"]) else 0, step=1, key=f"g2c_{i}")
            gols_fora = cols[1].number_input("Fora", min_value=0, max_value=30, value=int(row["gols_fora"]) if pd.notna(row["gols_fora"]) else 0, step=1, key=f"g2f_{i}")
            opcoes_penal = ["", limpar_texto(row.get('time_A', '')), limpar_texto(row.get('time_B', ''))]
            if gols_casa == gols_fora and limpar_texto(row.get('time_A', '')) and limpar_texto(row.get('time_B', '')):
                vencedor_pen = cols[2].selectbox("Penais", opcoes_penal, index=0 if limpar_texto(row.get("vencedor_penaltis", "")) not in opcoes_penal else opcoes_penal.index(limpar_texto(row.get("vencedor_penaltis", ""))), key=f"g2p_{i}")
            else:
                cols[2].markdown(" ")
                vencedor_pen = ""
            edited_semis.append({"id_jogo": row["id_jogo"], "gols_casa": gols_casa, "gols_fora": gols_fora, "vencedor_penaltis": vencedor_pen})
        salvar_semis = st.form_submit_button("Salvar Semi-Final", use_container_width=True)
    if salvar_semis:
        df_base_2 = st.session_state.df_jogos_2.copy()
        for item in edited_semis:
            idx = df_base_2.index[df_base_2["id_jogo"] == item["id_jogo"]]
            if len(idx) == 0: continue
            j = idx[0]
            df_base_2.loc[j, "gols_casa"] = item["gols_casa"]
            df_base_2.loc[j, "gols_fora"] = item["gols_fora"]
            if "vencedor_penaltis" in df_base_2.columns: df_base_2.loc[j, "vencedor_penaltis"] = item.get("vencedor_penaltis", "")
        st.session_state.df_jogos_2 = resolver_jogos_2(df_base_2, st.session_state.df_jogos_4)
        if st.session_state.df_final is None:
            try: st.session_state.df_final = carregar_final(st.session_state.arquivo_base)
            except Exception: st.session_state.df_final = pd.DataFrame()
        st.session_state.df_final = resolver_final(st.session_state.df_final, st.session_state.df_jogos_2)
        st.session_state.mensagem = "Semi-final atualizada."
        st.rerun()

    st.subheader("Final e Terceiro Lugar")
    if st.session_state.df_final is None or getattr(st.session_state.df_final, "empty", True):
        st.info("A aba Final não foi carregada.")
        return
    df_final_view = final_para_edicao(st.session_state.df_final).reset_index(drop=True)
    with st.form("form_final"):
        edited_final = []
        for i, row in df_final_view.iterrows():
            mostrar_card_jogo(row, limpar_texto(row.get('rodada', 'Final'), 'Final'))
            cols = st.columns([1.0, 1.0, 1.4])
            gols_casa = cols[0].number_input("Casa", min_value=0, max_value=30, value=int(row["gols_casa"]) if pd.notna(row["gols_casa"]) else 0, step=1, key=f"gfinc_{i}")
            gols_fora = cols[1].number_input("Fora", min_value=0, max_value=30, value=int(row["gols_fora"]) if pd.notna(row["gols_fora"]) else 0, step=1, key=f"gfinf_{i}")
            opcoes_penal = ["", limpar_texto(row.get('time_A', '')), limpar_texto(row.get('time_B', ''))]
            if gols_casa == gols_fora and limpar_texto(row.get('time_A', '')) and limpar_texto(row.get('time_B', '')):
                vencedor_pen = cols[2].selectbox("Penais", opcoes_penal, index=0 if limpar_texto(row.get("vencedor_penaltis", "")) not in opcoes_penal else opcoes_penal.index(limpar_texto(row.get("vencedor_penaltis", ""))), key=f"gfinp_{i}")
            else:
                cols[2].markdown(" ")
                vencedor_pen = ""
            edited_final.append({"id_jogo": row["id_jogo"], "gols_casa": gols_casa, "gols_fora": gols_fora, "vencedor_penaltis": vencedor_pen})
        salvar_final = st.form_submit_button("Salvar Final e Terceiro Lugar", use_container_width=True)
    if salvar_final:
        df_base_final = st.session_state.df_final.copy()
        for item in edited_final:
            idx = df_base_final.index[df_base_final["id_jogo"] == item["id_jogo"]]
            if len(idx) == 0: continue
            j = idx[0]
            df_base_final.loc[j, "gols_casa"] = item["gols_casa"]
            df_base_final.loc[j, "gols_fora"] = item["gols_fora"]
            if "vencedor_penaltis" in df_base_final.columns: df_base_final.loc[j, "vencedor_penaltis"] = item.get("vencedor_penaltis", "")
        st.session_state.df_final = resolver_final(df_base_final, st.session_state.df_jogos_2)
        st.session_state.mensagem = "Final e terceiro lugar atualizados."
        st.rerun()


def main():
    inicializar_estado()
    aplicar_estilo()
    render_header()
    with st.sidebar:
        st.markdown("### Centro de Controle")
        arquivo = st.text_input("Caminho do Excel", value=st.session_state.arquivo_base)
        if st.button("Carregar base", use_container_width=True):
            try:
                st.session_state.arquivo_base = arquivo
                carregar_base_arquivo(arquivo)
            except Exception as e:
                st.session_state.mensagem = f"Erro ao carregar base: {e}"
        st.markdown("---")
        pagina = st.radio("Navegação", ["Editar Grupos", "Dashboard", "Round of 32", "Playoff"], index=0)
        if st.session_state.dados_carregados:
            st.success("Base carregada")
            st.write(f"Edição: {st.session_state.config.get('edicao_copa')}")
            st.write(f"Grupos: {st.session_state.config.get('qtd_grupos')}")
            st.write(f"Terceiros que avançam: {st.session_state.config.get('classifica_melhores_terceiros')}")
        else:
            st.info("Informe o arquivo e carregue a base")
    if st.session_state.mensagem:
        st.info(st.session_state.mensagem)
    if not st.session_state.dados_carregados:
        st.stop()
    if pagina == "Editar Grupos": pagina_edicao()
    elif pagina == "Dashboard": dashboard()
    elif pagina == "Round of 32": pagina_round32()
    elif pagina == "Playoff": pagina_oitavas()
    st.markdown("---")
    if st.button("Preparar download do Excel"):
        caminho_saida = salvar_arquivo()
        with open(caminho_saida, "rb") as f:
            st.download_button(label="Baixar arquivo atualizado", data=f.read(), file_name="copa_2026_bolao_atualizada.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

if __name__ == "__main__":
    main()
