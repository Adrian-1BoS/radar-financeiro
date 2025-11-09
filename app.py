import streamlit as st
#import numpy as np
from statistics import median
from core.news import buscar_noticias_combinadas
from core.dados import carregar_ativos, extrair_palavras_chave, carregar_keywords, carregar_keywords_setoriais
from core.analise import analisar_sentimento_em_lote, analisar_tendencia
from core.grafico import (
    carregar_dados_preco,
    exibir_metricas_preco,
    plotar_grafico_linha,
    plotar_grafico_velas,
    exibir_tabela_precos
)
import os, logging
from logging.handlers import RotatingFileHandler

#config do logging para salvar erros no arquivo .log
os.makedirs("logs", exist_ok=True)

# Configura rotação: 1 MB por arquivo, até 5 arquivos antigos
handler = RotatingFileHandler("logs/bugs.log", maxBytes=1_000_000, backupCount=5)

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        handler,
        logging.StreamHandler()
    ]
)

# 🔹 Interface principal
st.set_page_config(page_title="Radar Financeiro", layout="wide")
# 🔹 Titulo para o usuario
st.title("📊 Radar Financeiro Julios Invest 🔎💵")
# 🔹 Informação importante
st.write("Análise de notícias, tendencia e preços de ativos. **A análise é experimental e contém erros no calculo de 'sentimentos'.**")

ativos_df = carregar_ativos()
# 🔹 Lista de seleção com os ativos no DB
ativo = ["Selecione um ativo..."] + [f"{row['ticker']} - {row['nome']}" for _, row in ativos_df.iterrows()]

with st.sidebar:
    st.header("Seleção")
    if "ativo_selecionado" not in st.session_state:
        st.session_state.ativo_selecionado = None

    entrada = st.selectbox("Selecione o ativo", ativo)
    if entrada != "Selecione um ativo...":
        st.session_state.ativo_selecionado = entrada

    periodo = st.radio("📅 Selecione o período do gráfico", ("5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "max"),
        index=3,
        horizontal=True
    )
    tipo_grafico = st.radio("Tipo de gráfico", ["Gráfico de Linha", "Gráfico de Velas"], index=1)

    if st.button("Analisar") and st.session_state.ativo_selecionado:
        st.session_state.analise_ativa = True
        st.session_state.resultados = None
        st.rerun()

    if st.button("🔄 Limpar"):
        st.session_state.pop("analise_ativa", None)
        st.session_state.pop("ativo_selecionado", None)
        st.rerun()

# 🔹 Função para limpeza (para remover de materias '~' e '\c') sugerido pelo gemini
def limpar_texto_exibicao(texto):
    return (
        texto
        .replace("~", "")
        .replace("\\c", "")
        .replace("\\x03", "")
        .replace("\r\n", " ")
        .strip()
    )

# 🔹 Execução da análise
if "analise_ativa" in st.session_state and st.session_state.analise_ativa and st.session_state.ativo_selecionado:
    ticker, nome = st.session_state.ativo_selecionado.split(" - ")
    termo_busca = nome
    ativo_info = ativos_df.query("ticker == @ticker").iloc[0]
    ativo = ativo_info.to_dict() if not ativo_info.empty else None

    try:
        dicionario_geral = carregar_keywords()
        dicionario_setorial = carregar_keywords_setoriais()
    except Exception as e:
        st.error(f"Erro ao carregar arquivos JSON de dicionários: {e}.")
        dicionario_geral, dicionario_setorial = {}, {}

    dados = carregar_dados_preco(ticker, periodo)
    st.subheader(f"🔍 Análise de Notícias sobre {termo_busca}")
    noticias = buscar_noticias_combinadas(termo_busca)

    if ativo:
        palavras_chave = [p.lower() for p in extrair_palavras_chave(ativo)]
    else:
        palavras_chave = []

        # A linha de filtragem usa a lista de palavras-chave gerada
    noticias_relevantes = [n for n in noticias if
                           any(p in f"{n['titulo']} {n['resumo']}".lower() for p in palavras_chave)]

    tendencia = analisar_tendencia(dados)
    st.subheader("📊 Análise de Tendência")
    st.info(tendencia)

    if noticias_relevantes:
        resultados = analisar_sentimento_em_lote(noticias_relevantes, ativos_df, dicionario_geral, dicionario_setorial)
        st.session_state.resultados = resultados

        pontuacoes_validas = [r["intensidade"] for r in resultados if r["intensidade"] != 0.0]
        pontuacao_media = median(pontuacoes_validas) if pontuacoes_validas else 0
        col1, col2 = st.columns([1, 2])
        with col1:
            cor_sentimento = (
                "<span style='color:green; font-weight:bold;'>Positivo</span>" if pontuacao_media > 0.1 else
                "<span style='color:red; font-weight:bold;'>Negativo</span>" if pontuacao_media < -0.1 else
                "<span style='color:gray; font-weight:bold;'>Neutro</span>"
            )
            st.markdown(f"**Sentimento Médio:** {cor_sentimento} ({pontuacao_media:.2f})", unsafe_allow_html=True)

        with col2:
            st.info(f"Análise baseada em {len(noticias_relevantes)} notícias filtradas.")

        st.markdown("### 📰 Destaques")
        destaques = sorted(resultados, key=lambda x: abs(x["intensidade"]), reverse=True)[:5]
        for r in destaques:
            texto_limpo_display = limpar_texto_exibicao(r['texto_original'][:100])

            cor = "🟢" if r['intensidade'] > 0.1 else "🔴" if r['intensidade'] < -0.1 else "⚪"

            with st.expander(f"{cor} `{r['intensidade']:.2f}` — {texto_limpo_display}..."):
                st.markdown(f"**Original:** {limpar_texto_exibicao(r['texto_original'])}")
                st.markdown(f"**Sentimento:** **{r['sentimento']}**")

        with st.expander("Ver todas as notícias analisadas", expanded=False):
            for r in resultados:
                texto_limpo_display = limpar_texto_exibicao(r['texto_original'])

                cor = "🟢" if r['intensidade'] > 0.1 else "🔴" if r['intensidade'] < -0.1 else "⚪"
                st.write(f"{cor} `{r['intensidade']:.2f}` — {texto_limpo_display}")
    else:
        st.warning("Nenhuma notícia relevante foi encontrada para este ativo.")

    st.subheader("📈 Histórico de Preço")
    st.write("Ticker:", ticker)

    exibir_metricas_preco(dados)

    if tipo_grafico == "Gráfico de Velas":
        plotar_grafico_velas(dados)
    else:

        plotar_grafico_linha(dados)

    exibir_tabela_precos(dados)