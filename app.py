# ====================================================================================
# PAINEL DE CATEGORIZAÇÃO DE VIAGENS — versão Streamlit com UPLOAD DE ARQUIVOS
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

st.title("Painel de Categorização de Viagens")

# ------------------------------------------------------------------------------------
# 📌 Função para carregar DADOS enviados via upload (CSV ; ou XLSX)
# ------------------------------------------------------------------------------------

@st.cache_data
def carregar_dados_upload(arquivos):
    dfs = []
    for arquivo in arquivos:
        nome = arquivo.name.lower()

        if nome.endswith(".csv"):
            # seu CSV real: separador ; e UTF-8 com BOM
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

    df_final = pd.concat(dfs, ignore_index=True)
    return df_final


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

# limpar nomes de colunas (tira espaços e troca por _)
df = df.rename(columns=lambda x: str(x).strip().replace(" ", "_"))

# ------------------------------------------------------------------------------------
# 📌 Função para classificar tipo de dia
# ------------------------------------------------------------------------------------

def classificar_tipo_dia(ts):
    # ts é um Timestamp (datetime64)
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
# 📌 TRATAMENTO DAS COLUNAS BÁSICAS
# ====================================================================================

colunas_necessarias = ["Horário_agendado", "Horário_realizado",
                       "Situação_viagem", "Situação_categoria"]

for c in colunas_necessarias:
    if c not in df.columns:
        st.error(f"A coluna obrigatória '{c}' não existe na base!")
        st.stop()

# Horário_agendado como datetime
df["Horário_agendado"] = pd.to_datetime(df["Horário_agendado"], errors="coerce")

# Data_Agendada como datetime normalizado (meia-noite)
df["Data_Agendada"] = df["Horário_agendado"].dt.normalize()

# Horário_realizado como datetime
df["Horário_realizado"] = pd.to_datetime(df["Horário_realizado"], errors="coerce")

# Tipo de dia
df["Tipo_Dia"] = df["Data_Agendada"].apply(classificar_tipo_dia)

# ====================================================================================
# 📌 CRIAÇÃO DA FAIXA HORÁRIA
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
# 🎚️ FILTROS
# ====================================================================================

st.sidebar.header("Filtros")

# Empresa
if "Empresa" in df.columns:
    empresas = sorted(df["Empresa"].dropna().unique())
    empresas_sel = st.sidebar.multiselect("Empresa", empresas, default=empresas)
else:
    empresas_sel = []

# Linha
if "Linha" in df.columns:
    linhas = sorted(df["Linha"].dropna().unique())
    linhas_sel = st.sidebar.multiselect("Linha", linhas, default=linhas)
else:
    linhas_sel = []

# Faixa horária
faixas = sorted(df["Faixa_Horaria"].dropna().unique())
faixas_sel = st.sidebar.multiselect("Faixa Horária", faixas, default=faixas)

mask = pd.Series(True, index=df.index)

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
# 📌 Preparação: Último dia e janela de 7 dias (robusto)
# ====================================================================================

# garante que Data_Agendada é datetime
df_filtro["Data_Agendada"] = pd.to_datetime(df_filtro["Data_Agendada"], errors="coerce")

if df_filtro["Data_Agendada"].notna().sum() == 0:
    st.error("Não foi possível identificar datas válidas em Data_Agendada.")
    st.stop()

ultimo_dia = df_filtro["Data_Agendada"].max()

df_dia = df_filtro[df_filtro["Data_Agendada"] == ultimo_dia]

JANELA_DIAS = 7
limite_data = ultimo_dia - pd.Timedelta(days=JANELA_DIAS)

df_janela = df_filtro[df_filtro["Data_Agendada"] >= limite_data]

tipo_dia_ult = df_dia["Tipo_Dia"].iloc[0]
df_tipo = df_janela[df_janela["Tipo_Dia"] == tipo_dia_ult]

# ====================================================================================
# 🔢 Função auxiliar
# ====================================================================================

def calcula_adiantamento(df_base, df_dia, limite):
    if len(df_dia) == 0 or len(df_base) == 0:
        return 0, 0.0, 0.0, 0.0

    qtd_dia = (df_dia["Adiantamento_min"] > limite).sum()
    pct_dia = qtd_dia / len(df_dia) * 100

    qtd_media = (df_base["Adiantamento_min"] > limite).sum()
    pct_media = qtd_media / len(df_base) * 100

    return qtd_dia, pct_dia, qtd_media, pct_media

# ====================================================================================
# SEÇÃO 1 — VELOCÍMETROS
# ====================================================================================

st.header(f"Adiantamento das Viagens — Último Dia vs Média ({JANELA_DIAS} dias)")

colunas = st.columns(3)
limites = [3, 5, 10]

for idx, LIM in enumerate(limites):
    qtd_dia, pct_dia, qtd_media, pct_media = calcula_adiantamento(df_tipo, df_dia, LIM)
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
                    "decreasing.color": "red",
                },
                number={"suffix": "%", "font": {"size": 40}},
                gauge={
                    "axis": {"range": [0, max(10, pct_dia * 3, pct_media * 3)], "tickwidth": 1},
                    "bar": {"color": "#4CAF50"},
                    "borderwidth": 2,
                    "bgcolor": "white",
                },
            )
        )

        fig_gauge.update_layout(
            title=f"Adiantadas > {LIM} min",
            height=320,
            margin=dict(l=10, r=10, t=70, b=10)
        )

        st.plotly_chart(fig_gauge, use_container_width=True)

        st.markdown(
            f"""
            <div style="text-align:center; font-size:16px; margin-top:-12px;">
            Último dia: <b>{qtd_dia}</b> viagens ({pct_dia:.2f}%) • 
            Média {tipo_dia_ult.lower()} (últimos {JANELA_DIAS} dias): <b>{pct_media:.2f}%</b> 
            ({'+' if desvio>=0 else ''}{desvio:.2f} p.p.)
            </div>
            """,
            unsafe_allow_html=True
        )

# ====================================================================================
# SEÇÃO 2 — SITUAÇÃO DA VIAGEM
# ====================================================================================

st.header(f"Situação da Viagem — Último Dia vs Média ({JANELA_DIAS} dias)")

tab_ult = df_dia.groupby("Situação_viagem").size().reset_index(name="Qtd Último Dia")
tab_tipo = df_tipo.groupby("Situação_viagem").size().reset_index(name="Qtd Média TipoDia")

tabela_vg = tab_ult.merge(tab_tipo, on="Situação_viagem", how="outer").fillna(0)

tabela_vg["% Último Dia"] = tabela_vg["Qtd Último Dia"] / tabela_vg["Qtd Último Dia"].sum() * 100
tabela_vg["% Média TipoDia"] = tabela_vg["Qtd Média TipoDia"] / tabela_vg["Qtd Média TipoDia"].sum() * 100
tabela_vg["Desvio (p.p.)"] = tabela_vg["% Último Dia"] - tabela_vg["% Média TipoDia"]

st.subheader("Tabela — Situação da Viagem")
st.dataframe(tabela_vg, use_container_width=True)

# ====================================================================================
# SEÇÃO 3 — SITUAÇÃO CATEGORIA
# ====================================================================================

st.header(f"Situação Categoria — Último Dia vs Média ({JANELA_DIAS} dias)")

tab_cat_ult = df_dia.groupby("Situação_categoria").size().reset_index(name="Qtd Último Dia")
tab_cat_tipo = df_tipo.groupby("Situação_categoria").size().reset_index(name="Qtd Média TipoDia")

tabela_cat = tab_cat_ult.merge(tab_cat_tipo, on="Situação_categoria", how="outer").fillna(0)

tabela_cat["% Último Dia"] = tabela_cat["Qtd Último Dia"] / tabela_cat["Qtd Último Dia"].sum() * 100
tabela_cat["% Média TipoDia"] = tabela_cat["Qtd Média TipoDia"] / tabela_cat["Qtd Média TipoDia"].sum() * 100
tabela_cat["Desvio (p.p.)"] = tabela_cat["% Último Dia"] - tabela_cat["% Média TipoDia"]

st.subheader("Tabela — Situação Categoria")
st.dataframe(tabela_cat, use_container_width=True)


