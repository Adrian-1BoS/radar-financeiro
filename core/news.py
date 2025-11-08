import requests
import streamlit as st
from dotenv import load_dotenv
import os

load_dotenv()
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")
CURRENTS_KEY = os.getenv("CURRENTS_KEY")

# 🔹 Busca via NewsAPI
@st.cache_data(ttl=3600)
def buscar_noticias_news(termo):
    url = f"https://newsapi.org/v2/everything?q={termo}&language=pt&sortBy=publishedAt&apiKey={NEWSAPI_KEY}"
    try:
        resposta = requests.get(url, timeout=10)
        resposta.raise_for_status()
        dados = resposta.json()
        return [
            {"titulo": artigo["title"], "resumo": artigo.get("description", "")}
            for artigo in dados.get("articles", [])
            if artigo.get("title")
        ]
    except requests.exceptions.RequestException as e:
        print(f"❌ Erro ao conectar com o NewsAPI: {e}")
        return []

# 🔹 Busca via Currents API
@st.cache_data(ttl=3600)
def buscar_noticias_currents(termo):
    url = "https://api.currentsapi.services/v1/search"
    params = {
        "keywords": termo,
        "language": "pt",
        "apiKey": CURRENTS_KEY
    }

    try:
        resposta = requests.get(url, params=params, timeout=10)
        resposta.raise_for_status()
        dados = resposta.json()
        return [
            {
                "titulo": n["title"],
                "resumo": n.get("description", ""),
                "fonte": n.get("source", ""),
                "url": n["url"]
            }
            for n in dados.get("news", [])
        ]
    except requests.exceptions.RequestException as e:
        print(f"❌ Erro ao conectar com Currents API: {e}")
        return []

# 🔹 Combina ambas as fontes
def buscar_noticias_combinadas(termo):
    noticias_newsapi = buscar_noticias_news(termo)
    noticias_currents = buscar_noticias_currents(termo)
    return noticias_newsapi + noticias_currents