import altair as alt
import streamlit as st
import yfinance as yf
import pandas as pd
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

# 🔹 Mapeamento do periodo para a média móvel conforme boas praticas de mercado
def obter_janela_media(periodo):
    mapeamento_dias = {
        "5d": 3, "1mo": 10, "3mo": 20, "6mo": 30,
        "1y": 50, "2y": 100, "5y": 200, "max": 300
    }
    return mapeamento_dias.get(periodo, 20)

# 🔹 Mapeia os periodos do grafico para dar um return de intervalo condicente com o periodo, não ficando muito pesado principalmente em periodos longos
def obter_intervalo(periodo):
    if periodo in ["5d", "1mo", "3mo"]:
        return "1d"
    elif periodo in ["6mo", "1y"]:
        return "1wk"
    elif periodo in ["2y", "5y", "max"]:
        return "1mo"
    else:
        return "1d"

# 🔹 Busca dados de preço no yfinance, trata os dados e calcula média móvel
def carregar_dados_preco(ticker, periodo):
    try:

        intervalo = obter_intervalo(periodo)
        dados = yf.download(ticker, period=periodo, interval=intervalo, progress=False)

        # 🔹 Corrige nomes de coluna antes de qualquer verificação
        if isinstance(dados.columns, pd.MultiIndex):
            dados.columns = [col[0].strip() for col in dados.columns.values]
        else:
            dados.columns = dados.columns.str.strip()

        # 🔹 Verifica se os dados estão válidos
        if not dados.empty and "Close" in dados.columns:
            # Reseta o índice e garante coerção de tipos para robustez
            dados.reset_index(inplace=True)
            colunas_preco = ["Open", "High", "Low", "Close", "Volume"]
            for col in colunas_preco:
                if col in dados.columns:
                    dados[col] = pd.to_numeric(dados[col], errors='coerce')
            dados.dropna(subset=["Close"], inplace=True)
            if 'Date' in dados.columns:
                dados['Date'] = pd.to_datetime(dados['Date'])

            janela = obter_janela_media(periodo)
            dados["Média Móvel"] = dados["Close"].rolling(window=janela, min_periods=1).mean()
            return dados
        else:
            st.warning("⚠️ Dados vazios ou coluna 'Close' ausente.")
            return pd.DataFrame(columns=["Date", "Close", "Média Móvel", "Open", "High", "Low", "Volume"])
    except Exception as e:
        st.error(f"❌ Erro ao buscar dados de preço: {e}")
        return pd.DataFrame(columns=["Date", "Close", "Média Móvel", "Open", "High", "Low", "Volume"])

# 🔹 Exibe métrica de preço atual e variação
def exibir_metricas_preco(dados):
    if not dados.empty and "Close" in dados.columns and len(dados) >= 1:
        preco_atual = dados["Close"].iloc[-1]
        preco_anterior = dados["Close"].iloc[-2] if len(dados) > 1 else preco_atual
        variacao = ((preco_atual - preco_anterior) / preco_anterior) * 100

        st.metric(
            label="💰 Preço atual",
            value=f"R$ {float(preco_atual):.2f}",
            delta=f"{float(variacao):.2f}%"
        )


# 🔹 Função formatar_balao (Compacta, em uma linha)
def formatar_balao(row):
    partes = []

    try:
        data_str = row['Date'].strftime('%d/%m/%Y') if isinstance(row['Date'], pd.Timestamp) else str(row['Date'])
        partes.append(f"Data: {data_str}")
    except Exception:
        partes.append("Data: -")

    if 'Close' in row and isinstance(row['Close'], (float, int)) and not pd.isna(row['Close']):
        partes.append(f"Fechamento: R$ {row['Close']:.2f}")

    if 'Média Móvel' in row and isinstance(row['Média Móvel'], (float, int)) and not pd.isna(row['Média Móvel']):
        partes.append(f"Média Móvel: R$ {row['Média Móvel']:.2f}")

    if 'Open' in row and 'High' in row and 'Low' in row:
        try:
            partes.append(f"Abertura: R$ {row['Open']:.2f}")
            partes.append(f"Máxima: R$ {row['High']:.2f}")
            partes.append(f"Mínima: R$ {row['Low']:.2f}")
            if 'Volume' in row:
                partes.append(f"Volume: {row['Volume']:,.0f}")
        except Exception:
            pass

    # Juntar todas as partes com separador | para garantir uma linha compacta
    return ' | '.join(partes)


# 🔹 Gráfico de linha com média móvel (Com balão customizado e correção de renderização)
def plotar_grafico_linha(dados):
    if dados.empty:
        st.info("Dados de preço indisponíveis para plotar o gráfico de linha.")
        return

    dados["balão"] = dados.apply(formatar_balao, axis=1)

    # 🔹 Seleção invisível que segue o eixo X
    nearest = alt.selection_point(on="mouseover", fields=["Date"], nearest=True)

    # 🔹 Base do gráfico
    base = alt.Chart(dados).encode(x=alt.X("Date:T", title="Data"))

    # 🔹 Linha de fechamento
    linha = base.mark_line(color="steelblue").encode(
        y=alt.Y("Close:Q", title="Preço de Fechamento, Média Móvel")
    )

    # 🔹 Linha de média móvel
    media = base.mark_line(color="orange").encode(
        y=alt.Y("Média Móvel:Q", title="Preço de Fechamento, Média Móvel")
    )

    # 💡 Camada de ponto para ativar a seleção e o tooltip customizado
    pontos_selecao = base.mark_point(opacity=0).encode(
        y=alt.Y("Close:Q"),  # Usamos Close como referência para a seleção
        tooltip=alt.Tooltip("balão:N", title="")  # Tooltip é o texto formatado
    ).add_params(nearest)

    # 🔹 Fundo do balão (Mark Rect)
    fundo = alt.Chart(dados).mark_rect(
        fill='white',
        stroke='gray',
        strokeWidth=1,
        opacity=0.3
    ).encode(
        x="Date:T",
        y="Close:Q"
    ).transform_filter(nearest)

    # 🔹 Linha vertical de guia
    linha_guia = alt.Chart(dados).mark_rule(color="gray").encode(
        x="Date:T"
    ).transform_filter(nearest)

    # 🔹 Texto com valor do ponto mais próximo (Para forçar a renderização do balão)
    texto = alt.Chart(dados).mark_text(
        align="left",
        dx=5,
        dy=-5,
        fontSize=0,
        fontWeight="bold",
        color="black"
    ).encode(
        x="Date:T",
        y="Close:Q",
        text="balão:N"
    ).transform_filter(nearest)

    grafico_final = alt.layer(
        linha, media, linha_guia, fundo, texto, pontos_selecao
    ).properties(width=700, height=400)  # Adicionando .interactive() de volta

    st.altair_chart(grafico_final, use_container_width=True)


# 🔹 Gráfico de velas com média móvel (Restaurado com balão customizado)
def plotar_grafico_velas(dados):
    if dados.empty:
        st.info("Dados de preço indisponíveis para plotar o gráfico de velas.")
        return

    dados["balão"] = dados.apply(formatar_balao, axis=1)  # Usa a função corrigida

    # 🔹 Seleção invisível que segue o eixo X (Usando alt.selection_point)
    nearest = alt.selection_point(on="mouseover", fields=["Date"], nearest=True)

    # 🔹 Base do gráfico
    base = alt.Chart(dados).encode(x=alt.X("Date:T", title="Data"))

    # 🔹 Gráfico de velas (pavilhos)
    high_low = base.mark_rule().encode(
        y=alt.Y("Low:Q", title="Preço de Fechamento, Média Móvel"),
        y2="High:Q"
    )

    # 🔹 Corpos das velas. Tooltip nativo removido para usar o customizado.
    candle = base.mark_bar().encode(
        y=alt.Y("Open:Q"),
        y2="Close:Q",
        color=alt.condition(
            "datum.Open > datum.Close",
            alt.value("#EF5350"),  # Vermelho
            alt.value("#26A69A")  # Verde
        )
    )

    # 🔹 Linha de média móvel
    media = base.mark_line(color="orange").encode(
        y=alt.Y("Média Móvel:Q", title="Preço de Fechamento, Média Móvel")
    )

    # 💡 Camada de ponto para ativar a seleção e o tooltip customizado
    pontos_selecao = base.mark_point(opacity=0).encode(
        y=alt.Y("Close:Q"),  # Usamos Close como referência para a seleção
        tooltip=alt.Tooltip("balão:N", title="")  # Tooltip é o texto formatado
    ).add_params(nearest)

    # 🔹 Fundo do balão (Mark Rect)
    fundo = alt.Chart(dados).mark_rect(
        fill='white',
        stroke='gray',
        strokeWidth=1,
        opacity=0.3
    ).encode(
        x="Date:T",
        y="Close:Q"
    ).transform_filter(nearest)

    # 🔹 Linha vertical de guia
    linha_guia = alt.Chart(dados).mark_rule(color="gray").encode(
        x="Date:T"
    ).transform_filter(nearest)

    # 🔹 Texto com valor do ponto mais próximo (Para forçar a renderização do balão)
    texto = alt.Chart(dados).mark_text(
        align="left",
        dx=5,
        dy=-5,
        fontSize=0,
        fontWeight="bold",
        color="black"
    ).encode(
        x="Date:T",
        y="Close:Q",
        text="balão:N"
    ).transform_filter(nearest)

    grafico_final = alt.layer(
        high_low, candle, media, linha_guia, fundo, texto, pontos_selecao
    ).properties(width=700, height=400) #.interactive()

    st.altair_chart(grafico_final, use_container_width=True)


# 🔹 Tabela de últimos preços
def exibir_tabela_precos(dados):
    if not dados.empty:
        st.subheader("📊 Últimos Preços")
        st.dataframe(dados[["Close", "Volume"]].tail(10))