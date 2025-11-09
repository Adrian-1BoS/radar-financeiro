import json, sqlite3, logging
import pandas as pd
import streamlit as st
import os
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

# Dicionário de chaves geral/ampla
def carregar_keywords(caminho="data/chave.json"):
    with open(caminho, "r", encoding="utf-8") as f:
        return json.load(f)

# Pega o peso no dicionario == chave.json
# Sendo polaridade == positivo negativo... tipo == concreta, qualitativas
def buscar_peso(palavra, tipo, polaridade, dicionario):
    return dicionario.get(tipo, {}).get(polaridade, {}).get(palavra.lower(), 0.0)

# Filtros para ver se não tem uma palavra presente nas noticias que seja == neutras e/ou ironico
def expressao_neut(texto, dicionario):
    texto_lower = texto.lower()
    return any(expr in texto_lower for expr in dicionario.get("neutras", []))
def expressao_ironi(texto, dicionario):
    texto_lower = texto.lower()
    return any(expr in texto_lower for expr in dicionario.get("ironico", []))

# Dicionário por setor (esse é mais preciso, usando como base as chaves por setor)
def carregar_keywords_setoriais(caminho="data/chave_setor.json"):
    with open(caminho, "r", encoding="utf-8") as f:
        return json.load(f)

# Busca o peso por setor e subsetor presentes no chave_setor.json, como a função anterior
def buscar_peso_setorial(palavra, setor, subsetor, polaridade, dicionario):
    return dicionario.get(setor, {}).get(subsetor, {}).get(polaridade, {}).get(palavra.lower(), 0.0)

# Carregamento do DB
@st.cache_resource
def carregar_ativos():
    try:
        conn = sqlite3.connect("data/ativos.db")
        df = pd.read_sql("SELECT * FROM ativos", conn)
        return df
    except Exception as e:
        st.error(f"Erro ao carregar o banco de dados.")
        logging.critical(f"Erro ao carregar o DB {e}", exc_info=True)
        return pd.DataFrame()

# Com base nos dados do ativo (vindos do DB), coleta campos relevantes para gerar palavras-chave de busca para o todo
def extrair_palavras_chave(ativo):
    try:
        campos = [
            ativo.get("cod", ""),
            ativo.get("cod_base", ""),
            ativo.get("nome", ""),
            ativo.get("ticker", ""),
            ativo.get("SETOR", ""),
            ativo.get("SUBSETOR", ""),
            ativo.get("SEGMENTO", "")
        ]
        palavras_fixas = ["ações", "lucro", "balanço", "mercado", "investidores", "dividendos", "CVM", "B3"]
        return [str(c).strip() for c in campos + palavras_fixas if c]
    except Exception as e:
        logging.critical(f"Erro na extração de palavra chave do ativo {ativo.get('ticker', 'N/A')}: {e}", exc_info=True)