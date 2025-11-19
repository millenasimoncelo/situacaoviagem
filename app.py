# ====================================================================================
# PAINEL DE CATEGORIZAÇÃO DE VIAGENS — versão Streamlit com UPLOAD + ABAS + RANKINGS
# ====================================================================================

import os
import pandas as pd
import numpy as np
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import textwrap

# ------------------------------------------------------------------------------------
# ⚙️ CONFIGURAÇÃO INICIAL DO STREAMLIT
# ------------------------------------------------------------------------------------

st.set_page_config(
    page_title="Painel de Categorização de Viagens",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("Painel de Categorização de Viagens")

# ------------------------------------------------------------------------------------
# 📌 Carregar dados enviados pelo usuário
# ------------------------------------------------------------------------------------

@st.cache_data
def carregar_dados_upload(arquivos):
    dfs = []
    for arquivo in arquivos:
        nome = arquivo.name.lower()

        if nome.endswith(".csv"):
            df_arq = pd.read_csv(
                arquivo,
                sep=";",
                encoding="utf-8-sig",
                low_memory=False
            )
        elif nome.endswith(".xlsx"):
            df_arq = pd.read_excel(arquivo)
        else:
            st.error("Formato não suportado. Envie arquivos .csv ou .xlsx.")
            st.stop()

        dfs.append(df_arq)

    if not dfs:
        st.error("Nenhum arquivo válido enviado.")
        st.stop()

    return pd.concat(dfs, ignore_index=True)

# ------------------------------------------------------------------------------------
# 📂 UPLOAD DO ARQUIVO
# ------------------------------------------------------------------------------------

with st.sidebar:
    st.header("Carregar dados")
    uploaded_files = st.file_uploader(
        "Envie seus arquivos .xlsx ou .csv",
        type=["xlsx", "csv"],
        accept_multiple_files=True
    )

if not uploaded_files:
    st.warning("Por favor, envie um arquivo para começar.")
    st.stop()

df = carregar_dados_upload(uploaded_files)

df = df.rename(columns=lambda x: str(x).strip().replace(" ", "_"))

# ------------------------------------------------------------------------------------
# Função para classificar tipo de dia
# ------------------------------------------------------------------------------------

def classificar_tipo_dia(ts):
    if pd.isna(ts):
        return "Desconhecido"
    wd = ts.weekday()
    if wd <= 4:
        return "Dia útil"
    elif wd == 5:
        return "Sábado"
    else:
        return "Domingo"

# ====================================================================================
# Tratamento das colunas básicas
# ====================================================================================

colunas_necessarias = [
    "Horário_agendado",
    "Horário_realizado",
    "Situação_viagem",
    "Situação_categoria",
]

for c in colunas_necessarias:
    if c not in df.columns:
        st.error(f"A coluna obrigatória '{c}' não existe na base!")
        st.stop()

df["Horário_agendado"] = pd.to_datetime(df["Horário_agendado"], errors="coerce")
df["Data_Agendada"] = df["Horário_agendado"].dt.normalize()
df["Horário_realizado"] = pd.to_datetime(df["Horário_realizado"], errors="coerce")

df["Tipo_Dia"] = df["Data_Agendada"].apply(classificar_tipo_dia)

# ====================================================================================
# Faixa Horária
# ====================================================================================

df["Hora_Agendada"] = df["Horário_agendado"].dt.hour
df["Faixa_Horaria"] = df["Hora_Agendada"].apply(
    lambda h: f"{int(h):02d}:00–{int(h):02d}:59" if pd.notnull(h) else "Sem horário"
)

# ====================================================================================
# Adiantamento
# ====================================================================================

df["Adiantamento_min"] = (
    df["Horário_realizado"] - df["Horário_agendado"]
).dt.total_seconds() / 60

df["Adianta_3"] = df["Adiantamento_min"] > 3
df["Adianta_5"] = df["Adiantamento_min"] > 5
df["Adianta_10"] = df["Adiantamento_min"] > 10

# ====================================================================================
# Filtros
# ====================================================================================

st.sidebar.header("Filtros")

if "Empresa" in df.columns:
    empresas = sorted(df["Empresa"].dropna().unique())
    empresas_sel = st.sidebar.multiselect("Empresa", empresas, default=empresas)
else:
    empresas_sel = []

if "Linha" in df.columns:
    linhas = sorted(df["Linha"].dropna().unique())
    linhas_sel = st.sidebar.multiselect("Linha", linhas, default=linhas)
else:
    linhas_sel = []

faixas = sorted(df["Faixa_Horaria"].dropna().unique())
faixas_sel = st.sidebar.multiselect("Faixa Horária", faixas, default=faixas)

mask = pd.Series(True, index=df.index)

if empresas_sel:
    mask &= df["Empresa"].isin(empresas_sel)
if linhas_sel:
    mask &= df["Linha"].isin(linhas_sel)
mask &= df["Faixa_Horaria"].isin(faixas_sel)

df_filtro = df[mask].copy()

if df_filtro.empty:
    st.warning("Nenhum dado encontrado com os filtros selecionados.")
    st.stop()

# ====================================================================================
# Comparação por tipo de dia
# ====================================================================================

df_filtro["Data_Agendada"] = pd.to_datetime(df_filtro["Data_Agendada"])

ultimo_dia = df_filtro["Data_Agendada"].max()
df_dia = df_filtro[df_filtro["Data_Agendada"] == ultimo_dia]

tipo_dia_ult = df_dia["Tipo_Dia"].iloc[0]

# DOMINGO
if tipo_dia_ult == "Domingo":
    domingos = df_filtro[(df_filtro["Tipo_Dia"] == "Domingo") &
                         (df_filtro["Data_Agendada"] < ultimo_dia)]
    domingos = domingos.sort_values("Data_Agendada", ascending=False)

    if domingos.empty:
        st.error("Não há domingo anterior para comparação.")
        st.stop()

    ref = domingos["Data_Agendada"].iloc[0]
    df_tipo = domingos[domingos["Data_Agendada"] == ref]

# SÁBADO
elif tipo_dia_ult == "Sábado":
    sabados = df_filtro[(df_filtro["Tipo_Dia"] == "Sábado") &
                        (df_filtro["Data_Agendada"] < ultimo_dia)]
    sabados = sabados.sort_values("Data_Agendada", ascending=False)

    if sabados.empty:
        st.error("Não há sábado anterior para comparação.")
        st.stop()

    ref = sabados["Data_Agendada"].iloc[0]
    df_tipo = sabados[sabados["Data_Agendada"] == ref]

# DIA ÚTIL
elif tipo_dia_ult == "Dia útil":
    uteis = df_filtro[(df_filtro["Tipo_Dia"] == "Dia útil") &
                      (df_filtro["Data_Agendada"] < ultimo_dia)]
    uteis = uteis.sort_values("Data_Agendada", ascending=False)

    if uteis.empty:
        st.error("Não há dias úteis anteriores.")
        st.stop()

    datas_ref = uteis["Data_Agendada"].unique()[:5]
    df_tipo = uteis[uteis["Data_Agendada"].isin(datas_ref)]

else:
    st.error("Tipo de dia desconhecido.")
    st.stop()

# ====================================================================================
# Função auxiliar
# ====================================================================================

def calcula_adiantamento(df_base, df_dia, limite):
    if df_base.empty or df_dia.empty:
        return 0, 0, 0, 0

    qtd_dia = (df_dia["Adiantamento_min"] > limite).sum()
    pct_dia = qtd_dia / len(df_dia) * 100

    qtd_media = (df_base["Adiantamento_min"] > limite).sum()
    pct_media = qtd_media / len(df_base) * 100

    return qtd_dia, pct_dia, pct_media, pct_media

# ====================================================================================
# Abas
# ====================================================================================

tab_resumo, tab_sit_viagem, tab_sit_cat, tab_rankings = st.tabs(
    ["Resumo (velocímetros)", "Situação da viagem", "Situação categoria",
     "Rankings por empresa"]
)

# ====================================================================================
# TAB 1 — RESUMO / VELOCÍMETROS
# ====================================================================================

with tab_resumo:

    st.header("Adiantamento — Último Dia vs Referência (dia equivalente anterior)")

    limites = [3, 5, 10]
    colunas = st.columns(3)

    if tipo_dia_ult == "Domingo":
        tipo_janela = "domingo anterior"
    elif tipo_dia_ult == "Sábado":
        tipo_janela = "sábado anterior"
    else:
        tipo_janela = "média dos 5 dias úteis anteriores"

    resumo_exec = []

    for idx, LIM in enumerate(limites):

        qtd_dia, pct_dia, qtd_media, pct_media = calcula_adiantamento(df_tipo, df_dia, LIM)

        desvio = pct_dia - pct_media

        resumo_exec.append({
            "limite": LIM,
            "qtd_dia": qtd_dia,
            "pct_dia": pct_dia,
            "qtd_media": qtd_media,
            "pct_media": pct_media,
            "desvio": desvio,
            "tipo_janela": tipo_janela
        })

        with colunas[idx]:

            fig_gauge = go.Figure(
                go.Indicator(
                    mode="gauge+number+delta",
                    value=pct_dia,
                    delta={
                        "reference": pct_media,
                        "valueformat": ".2f",
                        "increasing.color": "green",
                        "decreasing.color": "red",
                    },
                    number={"suffix": "%"},
                    gauge={
                        "axis": {"range": [0, max(10, pct_dia * 3, pct_media * 3)]},
                        "bar": {"color": "#4CAF50"},
                    }
                )
            )

            fig_gauge.update_layout(
                title=f"Adiantadas > {LIM} min",
                height=300
            )

            st.plotly_chart(fig_gauge, use_container_width=True)

    # ====================================================================================
    # RESUMO EXECUTIVO — CAIXAS (VERSÃO FINAL)
    # ====================================================================================
    
    st.subheader("Resumo Executivo dos Adiantamentos")
    
    col1, col2, col3 = st.columns(3)
    colunas_exec = [col1, col2, col3]
    
    for col, dados in zip(colunas_exec, resumo_exec):
    
        LIM = dados["limite"]
        qtd_dia = dados["qtd_dia"]
        pct_dia = dados["pct_dia"]
        qtd_media = dados["qtd_media"]
        pct_media = dados["pct_media"]
        desvio = dados["desvio"]
        tipo_janela = dados["tipo_janela"]
    
        cor_desvio = "green" if desvio >= 0 else "red"
    
        html_card = f"""
        <div style="background:#ffffff; border-radius:12px; padding:18px;
                    box-shadow:0 3px 8px rgba(0,0,0,0.12); font-family:Arial;">
    
            <h3 style="margin-top:0; margin-bottom:10px;">
                ▶ {LIM} min
            </h3>
    
            <div style="font-size:26px; font-weight:600; margin-bottom:6px;">
                {qtd_dia} viagens
            </div>
    
            <div style="font-size:18px; color:#444;">
                📊 Último dia: <b>{pct_dia:.2f}%</b>
            </div>
    
            <div style="font-size:16px; color:#666; margin-top:4px;">
                📅 Referência: <b>{pct_media:.2f}%</b><br/>
                <i>{tipo_janela}</i>
            </div>
    
            <div style="font-size:18px; color:{cor_desvio}; margin-top:10px;">
                <b>{desvio:+.2f} p.p.</b>
            </div>
        </div>
        """
    
        col.markdown(html_card, unsafe_allow_html=True)


# ====================================================================================
# AS DEMAIS ABAS (Viagem / Categoria / Rankings)
# ====================================================================================

# (todo o seu código das outras abas permanece como estava — não precisa alterar)

