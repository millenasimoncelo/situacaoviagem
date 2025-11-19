# ====================================================================================
# PAINEL DE CATEGORIZAÇÃO DE VIAGENS — versão com filtros e janela 7 dias (19/11/2025)
# ====================================================================================

import os
import pandas as pd
import numpy as np
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px

# ------------------------------------------------------------------------------------
# ⚙️ CONFIGURAÇÃO INICIAL DO STREAMLIT
# ------------------------------------------------------------------------------------

st.set_page_config(
    page_title="Painel de Categorização de Viagens",
    layout="wide",
    initial_sidebar_state="expanded"
)

# TÍTULO DO PAINEL
st.title("Painel de Categorização de Viagens")

# Remove header do Streamlit
st.markdown("""
    <style>
        header {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------------------------
# 📌 UPLOAD DOS ARQUIVOS (FUNCIONA LOCAL E NA NUVEM)
# ------------------------------------------------------------------------------------

st.sidebar.header("Carregar dados")

uploaded_files = st.sidebar.file_uploader(
    "Envie seus arquivos .xlsx da categorização",
    type=["xlsx"],
    accept_multiple_files=True
)

if not uploaded_files:
    st.warning("Envie pelo menos um arquivo .xlsx para iniciar o painel.")
    st.stop()

# Função que concatena todos os arquivos enviados
@st.cache_data
def carregar_dados_upload(arquivos):
    dfs = []
    for arquivo in arquivos:
        df = pd.read_excel(arquivo)
        dfs.append(df)
    df_final = pd.concat(dfs, ignore_index=True)
    return df_final

df = carregar_dados_upload(uploaded_files)

# ------------------------------------------------------------------------------------
# 📌 TRATAMENTO DAS COLUNAS BÁSICAS
# ------------------------------------------------------------------------------------

df = df.rename(columns=lambda x: x.strip().replace(" ", "_"))

# Verificações básicas
colunas_necessarias = ["Horário_agendado", "Horário_realizado", "Situação_viagem", "Situação_categoria"]
for c in colunas_necessarias:
    if c not in df.columns:
        st.error(f"A coluna obrigatória '{c}' não existe na base!")
        st.stop()

df["Horário_agendado"] = pd.to_datetime(df["Horário_agendado"])
df["Data_Agendada"] = df["Horário_agendado"].dt.date
df["Horário_realizado"] = pd.to_datetime(df["Horário_realizado"], errors="coerce")

# ------------------------------------------------------------------------------------
# 📌 Classificação do tipo de dia
# ------------------------------------------------------------------------------------

def classificar_tipo_dia(data):
    if data.weekday() <= 4:
        return "Dia útil"
    elif data.weekday() == 5:
        return "Sábado"
    elif data.weekday() == 6:
        return "Domingo"
    else:
        return "Outro"

df["Tipo_Dia"] = pd.to_datetime(df["Data_Agendada"]).apply(classificar_tipo_dia)

# ====================================================================================
# 📌 CRIAR FAIXA HORÁRIA
# ====================================================================================

df["Hora_Agendada"] = df["Horário_agendado"].dt.hour
df["Faixa_Horaria"] = df["Hora_Agendada"].apply(
    lambda h: f"{int(h):02d}:00–{int(h):02d}:59" if pd.notnull(h) else "Sem horário"
)

# ====================================================================================
# 📌 Cálculo do Adiantamento
# ====================================================================================

df["Adiantamento_min"] = (
    df["Horário_realizado"] - df["Horário_agendado"]
).dt.total_seconds() / 60

df["Adianta_3"] = df["Adiantamento_min"] > 3
df["Adianta_5"] = df["Adiantamento_min"] > 5
df["Adianta_10"] = df["Adiantamento_min"] > 10

# ====================================================================================
# 🎚️ FILTROS NA SIDEBAR
# ====================================================================================

st.sidebar.header("Filtros")

# Empresa
if "Empresa" in df.columns:
    empresas = sorted(df["Empresa"].dropna().unique())
    empresas_sel = st.sidebar.multiselect("Empresa", options=empresas, default=empresas)
else:
    empresas_sel = []

# Linha
if "Linha" in df.columns:
    linhas = sorted(df["Linha"].dropna().unique())
    linhas_sel = st.sidebar.multiselect("Linha", options=linhas, default=linhas)
else:
    linhas_sel = []

# Faixa Horária
faixas = sorted(df["Faixa_Horaria"].dropna().unique())
faixas_sel = st.sidebar.multiselect("Faixa horária (Horário agendado)", options=faixas, default=faixas)

# Aplicar filtros
mask = pd.Series([True] * len(df))

if empresas_sel and "Empresa" in df.columns:
    mask &= df["Empresa"].isin(empresas_sel)

if linhas_sel and "Linha" in df.columns:
    mask &= df["Linha"].isin(linhas_sel)

if faixas_sel:
    mask &= df["Faixa_Horaria"].isin(faixas_sel)

df_filtro = df[mask].copy()

if df_filtro.empty:
    st.warning("Nenhum dado encontrado com os filtros selecionados.")
    st.stop()

# ====================================================================================
# 📌 Preparação: Último dia e janela de 7 dias
# ====================================================================================

ultimo_dia = df_filtro["Data_Agendada"].max()
tipo_dia_ult = df_filtro.loc[df_filtro["Data_Agendada"] == ultimo_dia, "Tipo_Dia"].iloc[0]

df_dia = df_filtro[df_filtro["Data_Agendada"] == ultimo_dia]

JANELA_DIAS = 7
limite_data = ultimo_dia - pd.Timedelta(days=JANELA_DIAS)

df_janela = df_filtro[df_filtro["Data_Agendada"] >= limite_data]
df_tipo = df_janela[df_janela["Tipo_Dia"] == tipo_dia_ult]

# ====================================================================================
# 🔢 Funções auxiliares de cálculo
# ====================================================================================

def calcula_adiantamento(df_base, df_dia, limite):
    qtd_dia = (df_dia["Adiantamento_min"] > limite).sum()
    pct_dia = qtd_dia / len(df_dia) * 100 if len(df_dia) else 0

    qtd_media = (df_base["Adiantamento_min"] > limite).sum()
    pct_media = qtd_media / len(df_base) * 100 if len(df_base) else 0

    return qtd_dia, pct_dia, qtd_media, pct_media

# ====================================================================================
# ⏱️ SEÇÃO 1 — VELOCÍMETROS DE ADIANTAMENTO
# ====================================================================================

st.header(f"Adiantamento das Viagens — Último Dia vs Média ({JANELA_DIAS} dias, mesmo tipo de dia)")

colunas = st.columns(3)
limites = [3, 5, 10]

for idx, LIM in enumerate(limites):

    qtd_dia, pct_dia, _, pct_media = calcula_adiantamento(df_tipo, df_dia, LIM)
    desvio = pct_dia - pct_media

    with colunas[idx]:

        fig_gauge = go.Figure(
            go.Indicator(
                mode="gauge+number+delta",
                value=pct_dia,
                delta={
                    "reference": pct_media,
                    "valueformat": ".2f",
                    "increasing.color": "green",
                    "decreasing.color": "red"
                },
                number={"suffix": "%", "font": {"size": 48}},
                gauge={
                    "axis": {"range": [0, max(10, pct_dia * 3)], "tickwidth": 1},
                    "bar": {"color": "#4CAF50"},
                    "borderwidth": 2,
                    "bgcolor": "white",
                },
            )
        )

        fig_gauge.update_layout(
            title=f"Adiantadas > {LIM} min",
            height=360,
            margin=dict(l=10, r=10, t=70, b=10)
        )

        st.plotly_chart(fig_gauge, use_container_width=True)

        st.markdown(
            f"""
            <div style="text-align:center; font-size:18px; margin-top:-12px;">
            Último dia: <b>{qtd_dia}</b> viagens ({pct_dia:.2f}%) • 
            Média {tipo_dia_ult.lower()} (últimos {JANELA_DIAS} dias): <b>{pct_media:.2f}%</b> 
            ({'+' if desvio>=0 else ''}{desvio:.2f} p.p.)
            </div>
            """,
            unsafe_allow_html=True
        )

# ====================================================================================
# 📌 SEÇÃO 2 — SITUAÇÃO DA VIAGEM
# ====================================================================================

st.header(f"Situação da Viagem — Último Dia vs Média ({JANELA_DIAS} dias)")

df_ult = df_dia
df_tipo_dia = df_tipo

tab_ult = df_ult.groupby("Situação_viagem").size().reset_index(name="Qtd Último Dia")
tab_tipo = df_tipo_dia.groupby("Situação_viagem").size().reset_index(name="Qtd Média TipoDia (7d)")

tabela_vg = tab_ult.merge(tab_tipo, on="Situação_viagem", how="outer").fillna(0)

tabela_vg["% Último Dia"] = tabela_vg["Qtd Último Dia"] / tabela_vg["Qtd Último Dia"].sum() * 100
tabela_vg["% Média TipoDia (7d)"] = tabela_vg["Qtd Média TipoDia (7d)"] / tabela_vg["Qtd Média TipoDia (7d)"].sum() * 100
tabela_vg["Desvio (p.p.)"] = tabela_vg["% Último Dia"] - tabela_vg["% Média TipoDia (7d)"]

st.subheader("Tabela — Situação da Viagem (inclui 'Viagem concluída')")
st.dataframe(tabela_vg, use_container_width=True)

grafico_vg = tabela_vg[tabela_vg["Situação_viagem"] != "Viagem concluída"]

fig_vg = px.bar(
    grafico_vg,
    x="Situação_viagem",
    y=["% Média TipoDia (7d)", "% Último Dia"],
    barmode="group",
    labels={"value": "% das viagens", "Situação_viagem": "Situação"},
    height=450
)

fig_vg.update_layout(title="Situação da Viagem — Comparação (sem 'Viagem concluída')")
st.plotly_chart(fig_vg, use_container_width=True)

# ====================================================================================
# 📌 SEÇÃO 3 — SITUAÇÃO CATEGORIA
# ====================================================================================

st.header(f"Situação Categoria — Último Dia vs Média ({JANELA_DIAS} dias)")

tab_cat_ult = df_ult.groupby("Situação_categoria").size().reset_index(name="Qtd Último Dia")
tab_cat_tipo = df_tipo_dia.groupby("Situação_categoria").size().reset_index(name="Qtd Média TipoDia (7d)")

tabela_cat = tab_cat_ult.merge(tab_cat_tipo, on="Situação_categoria", how="outer").fillna(0)

tabela_cat["% Último Dia"] = tabela_cat["Qtd Último Dia"] / tabela_cat["Qtd Último Dia"].sum() * 100
tabela_cat["% Média TipoDia (7d)"] = tabela_cat["Qtd Média TipoDia (7d)"] / tabela_cat["Qtd Média TipoDia (7d)"].sum() * 100
tabela_cat["Desvio (p.p.)"] = tabela_cat["% Último Dia"] - tabela_cat["% Média TipoDia (7d)"]

fig_cat = px.bar(
    tabela_cat,
    x="Situação_categoria",
    y=["% Média TipoDia (7d)", "% Último Dia"],
    barmode="group",
    labels={"value": "% das viagens", "Situação_categoria": "Categoria"},
    height=450
)

fig_cat.update_layout(title="Situação Categoria — Comparação")
st.plotly_chart(fig_cat, use_container_width=True)

st.subheader("Tabela — Situação Categoria")
st.dataframe(tabela_cat, use_container_width=True)

