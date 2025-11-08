import json
import sqlite3
import pandas as pd
import streamlit as st

# 🔹 Dicionário de chaves geral/ampla
def carregar_keywords(caminho="data/chave.json"):
    with open(caminho, "r", encoding="utf-8") as f:
        return json.load(f)

def buscar_peso(palavra, tipo, polaridade, dicionario):
    return dicionario.get(tipo, {}).get(polaridade, {}).get(palavra.lower(), 0.0)

def expressao_neut(texto, dicionario):
    texto_lower = texto.lower()
    return any(expr in texto_lower for expr in dicionario.get("neutralizadoras", []))

def expressao_ironi(texto, dicionario):
    texto_lower = texto.lower()
    return any(expr in texto_lower for expr in dicionario.get("ironico", []))

# 🔹 Dicionário por setor
def carregar_keywords_setoriais(caminho="data/chave_setor.json"):
    with open(caminho, "r", encoding="utf-8") as f:
        return json.load(f)

def buscar_peso_setorial(palavra, setor, subsetor, polaridade, dicionario):
    return dicionario.get(setor, {}).get(subsetor, {}).get(polaridade, {}).get(palavra.lower(), 0.0)

# 🔹 Carregamento dos ativos
@st.cache_resource
def carregar_ativos():
    try:
        conn = sqlite3.connect("data/ativos.db")
        df = pd.read_sql("SELECT * FROM ativos", conn)
        return df
    except Exception as e:
        st.error(f"❌ Erro ao carregar o banco de dados. Erro: {e}")
        return []

def extrair_palavras_chave(ativo):
    campos = [ativo.get("nome", ""), ativo.get("ticker", ""), ativo.get("SETOR", ""), ativo.get("SUBSETOR", ""), ativo.get("SEGMENTO", "")]
    cod_base = ativo.get("cod", ativo.get("ticker", "").split(".")[0])
    palavras_fixas = ["ações", "lucro", "balanço", "mercado", "investidores", "dividendos", "CVM", "B3"]
    return [str(c).strip() for c in campos + [cod_base] + palavras_fixas if c]