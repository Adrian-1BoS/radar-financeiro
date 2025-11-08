import torch
import numpy as np
import streamlit as st
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from core.dados import (
    expressao_ironi,
    expressao_neut
)


# 🔹 Carregamento dos modelos com cache de recursos
@st.cache_resource
def carregar_modelos():
    # Carrega o modelo de IA (FinBERT-PT-BR). Sua função é agir como um sinal inicial.
    try:
        tokenizer_sentimento = AutoTokenizer.from_pretrained("lucas-leme/FinBERT-PT-BR")
        model_sentimento = AutoModelForSequenceClassification.from_pretrained("lucas-leme/FinBERT-PT-BR")
        st.success("✅ Modelo de IA especializado carregado com sucesso!")
        return tokenizer_sentimento, model_sentimento
    except Exception as e:
        st.error(f"❌ Erro ao carregar o modelo de IA. A análise de sentimento não funcionará. Erro: {e}")
        return None, None


# 🔹 Função de análise com ajuste hierárquico
@st.cache_data
def analisar_sentimento_em_lote(noticias_relevantes, ativos_df, dicionario_geral, dicionario_setorial):
    """
    Analisa o sentimento de uma lista de notícias em lote, ajustando o resultado da IA
    com base em uma lógica hierárquica de keywords e filtros anuladores.
    """
    tokenizer_sentimento, model_sentimento = carregar_modelos()
    resultados_analise = []

    if not noticias_relevantes:
        return []

    with st.spinner("Analisando sentimento..."):
        for n in noticias_relevantes:
            titulo = n['titulo']
            resumo = n['resumo']
            ticker = n.get("ticker", "")

            # Limpeza de texto para corrigir problemas de codificação e exibição
            texto_sujo = f"{titulo} {resumo}"
            # Remove caracteres de codificação problemáticos (ex: 'R$401,9bilho~es', '\c a')
            texto_pt = (
                texto_sujo.lower()
                .replace("~", "")
                .replace("\\c", "")
                .replace("\\x03", "")
                .replace("\r\n", " ")
                .strip()
            )

            # Busca as informações do ativo para obter Setor e Subsetor
            ativo = ativos_df.query("cod == @ticker").iloc[0].to_dict() if not ativos_df.query(
                "cod == @ticker").empty else None
            setor = ativo.get("SETOR", "") if ativo else ""
            subsetor = ativo.get("SUBSETOR", "") if ativo else ""

            # PASSO 1: Análise inicial com o modelo FinBERT-PT-BR (Base)
            if not model_sentimento or not tokenizer_sentimento:
                continue

            inputs = tokenizer_sentimento(texto_pt, return_tensors="pt", truncation=True, max_length=512)
            with torch.no_grad():
                logits = model_sentimento(**inputs).logits
            scores = torch.nn.functional.softmax(logits, dim=1).numpy()[0]
            labels_map = {0: -1, 1: 0, 2: 1}  # Mapeamento: Negativo(0)->-1, Neutro(1)->0, Positivo(2)->1
            sentimento_finbert = labels_map.get(np.argmax(scores), 0)
            confianca_finbert = scores[np.argmax(scores)]
            pontuacao_finbert = sentimento_finbert * confianca_finbert

            # PASSO 2: Cálculo dos pontos de ajuste hierárquicos (Keywords)

            # Acumula os pesos das keywords encontradas no texto_pt (limpo)
            pontos_ajuste_concretos = 0.0
            for tipo in ["concretas"]:
                for polaridade in ["positivas", "negativas"]:
                    termos = dicionario_geral.get(tipo, {}).get(polaridade, {})
                    for palavra, peso in termos.items():
                        if palavra in texto_pt:
                            pontos_ajuste_concretos += peso

            pontos_ajuste_qualitativos = 0.0
            for tipo in ["qualitativas"]:
                for polaridade in ["positivas", "negativas"]:
                    termos = dicionario_geral.get(tipo, {}).get(polaridade, {})
                    for palavra, peso in termos.items():
                        if palavra in texto_pt:
                            pontos_ajuste_qualitativos += peso

            pontos_setoriais = 0.0
            for polaridade in ["positivas", "negativas"]:
                termos = dicionario_setorial.get(setor, {}).get(subsetor, {}).get(polaridade, {})
                for palavra, peso in termos.items():
                    if palavra in texto_pt:
                        pontos_setoriais += peso

            # PASSO 3: Ponderação Final da Pontuação
            pontuacao_final = (
                    pontuacao_finbert * 0.20 +
                    pontos_setoriais * 0.35 +
                    pontos_ajuste_concretos * 0.35 +
                    pontos_ajuste_qualitativos * 0.10
            )

            # PASSO 4: Aplicação dos Filtros Anuladores (Neutralização e Ironia)
            is_neutra = expressao_neut(texto_pt, dicionario_geral)
            is_ironica = expressao_ironi(texto_pt, dicionario_geral)

            if is_neutra:
                # Se for neutra/macro, o sentimento é puxado fortemente para zero (redução de 90%)
                pontuacao_final *= 0.1
            elif is_ironica:
                # Se for irônica, a intensidade é reduzida pela metade (atenuação)
                pontuacao_final *= 0.5

            # Garante que a pontuacao_final fique entre -1.0 e 1.0
            pontuacao_final = np.clip(pontuacao_final, -1.0, 1.0)

            # PASSO 5: Classificação Final
            if pontuacao_final > 0.1:
                sentimento_final_str = "Positivo"
            elif pontuacao_final < -0.1:
                sentimento_final_str = "Negativo"
            else:
                sentimento_final_str = "Neutro"

            resultados_analise.append({
                # Usa o texto original para manter a formatação, mas garante que o cálculo foi no texto limpo
                "texto_original": f"{n['titulo']} {n['resumo']}",
                "texto_traduzido": "Não aplicável",
                "sentimento": sentimento_final_str,
                "intensidade": pontuacao_final
            })

    return resultados_analise


def analisar_tendencia(dados):
    """ Analisa a tendência do ativo comparando o preço atual com a média móvel. """
    if dados.empty or "Close" not in dados.columns or "Média Móvel" not in dados.columns:
        return "Dados insuficientes para análise de tendência."

    ultimos = dados.tail(5)
    preco_atual = ultimos["Close"].iloc[-1]
    media_atual = ultimos["Média Móvel"].iloc[-1]
    inclinacao = ultimos["Média Móvel"].diff().mean()

    if preco_atual > media_atual and inclinacao > 0:
        return "📈 Tendência de alta"
    elif preco_atual < media_atual and inclinacao < 0:
        return "📉 Tendência de baixa"
    else:
        return "⏸️ Tendência lateral ou indefinida"