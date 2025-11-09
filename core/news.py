import requests, logging
import streamlit as st
from dotenv import load_dotenv
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

load_dotenv()
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")
CURRENTS_KEY = os.getenv("CURRENTS_KEY")

# Busca via NewsAPI com cache ele não precisa fazer outra busca em um periodo de 1 hora.
@st.cache_data(ttl=3600)
def buscar_noticias_news(termo):
    url = f"https://newsapi.org/v2/everything?q={termo}&language=pt&sortBy=publishedAt&apiKey={NEWSAPI_KEY}"
    try:
        # Traz uma resposta em um periodo de até 10 segundos.
        resposta = requests.get(url, timeout=10)
        # Verifica se a trouxe algo valido, caso contrario == erro
        resposta.raise_for_status()
        # Converte o arquivo de noticias de .json para .py
        dados = resposta.json()

        # Em caso de algum erro no processo
        if dados.get("status") != "ok":
            logging.warning(f"Resposta inesperada da NewsAPI: {dados}")
            return []

        # Extrai título e resumo dos artigos retornados
        return [
            {"titulo": artigo["title"], "resumo": artigo.get("description", "")}
            for artigo in dados.get("articles", [])
            if artigo.get("title")
        ]

    except Exception as e:
        logging.error(f"Erro na busca usando a NewsAPI: {e}", exc_info=True)
        return []

# Busca notícias via Currents API e armazena em cache por 1 hora
@st.cache_data(ttl=3600)
def buscar_noticias_currents(termo):
    url = "https://api.currentsapi.services/v1/search"
    # Monta os parâmetros da requisição
    params = {
        "keywords": termo,
        "language": "pt",
        "apiKey": CURRENTS_KEY
    }

    try:
        # Realiza a requisição com tempo limite de 10 segundos
        resposta = requests.get(url, params=params, timeout=10)
        # Lança exceção se a resposta HTTP for inválida
        resposta.raise_for_status()
        # Converte o conteúdo JSON da resposta para dicionário Python
        dados = resposta.json()

        if not isinstance(dados.get("news"), list):
            logging.warning(f"Resposta inesperada da Currents API: {dados}")
            return []

        # Extrai título, resumo, fonte e URL de cada notícia
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
        logging.error(f"Erro ao conectar com Currents API: {e}", exc_info=True)
        return []

# Agrega notícias de múltiplas fontes para ampliar cobertura e reduzir viés (Não é muito funcional)
def buscar_noticias_combinadas(termo):
    noticias_newsapi = buscar_noticias_news(termo)
    noticias_currents = buscar_noticias_currents(termo)

    todas = noticias_newsapi + noticias_currents

    # Remove duplicatas com base no título
    titulos_vistos = set()
    unicas = []
    for noticia in todas:
        if noticia["titulo"] not in titulos_vistos:
            titulos_vistos.add(noticia["titulo"])
            unicas.append(noticia)

    return unicas