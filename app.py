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
# 📌 Função para carregar DADOS enviados via upload (CSV ; ou XLSX)
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
# 📌 Classificação do tipo de dia
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

# ------------------------------------------------------------------------------------
# 📌 TRATAMENTO DAS COLUNAS BÁSICAS
# ------------------------------------------------------------------------------------

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

df["Hora_Agendada"] = df["Horário_agendado"].dt.hour
df["Faixa_Horaria"] = df["Hora_Agendada"].apply(
    lambda h: f"{int(h):02d}:00–{int(h):02d}:59" if pd.notnull(h) else "Sem horário"
)

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

empresas_sel = st.sidebar.multiselect(
    "Empresa",
    sorted(df["Empresa"].dropna().unique()) if "Empresa" in df.columns else [],
    default=sorted(df["Empresa"].dropna().unique()) if "Empresa" in df.columns else []
)

linhas_sel = st.sidebar.multiselect(
    "Linha",
    sorted(df["Linha"].dropna().unique()) if "Linha" in df.columns else [],
    default=sorted(df["Linha"].dropna().unique()) if "Linha" in df.columns else []
)

faixas_sel = st.sidebar.multiselect(
    "Faixa Horária",
    sorted(df["Faixa_Horaria"].dropna().unique()),
    default=sorted(df["Faixa_Horaria"].dropna().unique())
)

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
# 📌 Definição da janela de comparação (dia equivalente)
# ====================================================================================

df_filtro["Data_Agendada"] = pd.to_datetime(df_filtro["Data_Agendada"], errors="coerce")
ultimo_dia = df_filtro["Data_Agendada"].max()
df_dia = df_filtro[df_filtro["Data_Agendada"] == ultimo_dia].copy()
tipo_dia_ult = df_dia["Tipo_Dia"].iloc[0]

if tipo_dia_ult == "Domingo":
    anteriores = df_filtro[(df_filtro["Tipo_Dia"] == "Domingo") & (df_filtro["Data_Agendada"] < ultimo_dia)]
    data_ref = anteriores["Data_Agendada"].max()
    df_tipo = df_filtro[df_filtro["Data_Agendada"] == data_ref]
    tipo_janela = "domingo anterior"

elif tipo_dia_ult == "Sábado":
    anteriores = df_filtro[(df_filtro["Tipo_Dia"] == "Sábado") & (df_filtro["Data_Agendada"] < ultimo_dia)]
    data_ref = anteriores["Data_Agendada"].max()
    df_tipo = df_filtro[df_filtro["Data_Agendada"] == data_ref]
    tipo_janela = "sábado anterior"

else:
    dias_uteis = df_filtro[(df_filtro["Tipo_Dia"] == "Dia útil") & (df_filtro["Data_Agendada"] < ultimo_dia)]
    datas_ref = dias_uteis["Data_Agendada"].unique()[:5]
    df_tipo = df_filtro[df_filtro["Data_Agendada"].isin(datas_ref)]
    tipo_janela = "média dos 5 dias úteis anteriores"

# ====================================================================================
# 🔢 Função auxiliar de adiantamento
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
# 🧩 ABAS
# ====================================================================================

tab_resumo, tab_sit_viagem, tab_sit_cat, tab_rankings = st.tabs(
    ["Resumo (velocímetros)", "Situação da viagem", "Situação categoria", "Rankings por empresa"]
)

# ====================================================================================
# TAB 1 — RESUMO / VELOCÍMETROS + RESUMO EXECUTIVO
# ====================================================================================

with tab_resumo:

    st.header("Adiantamento — Último Dia vs Referência (dia equivalente anterior)")

    limites = [3, 5, 10]
    colunas = st.columns(3)

    resumo_exec = []

    # ------------------------ GAUGES ------------------------
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
            fig = go.Figure(
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
            fig.update_layout(
                title=f"Adiantadas > {LIM} min",
                height=320,
                margin=dict(l=10, r=10, t=70, b=10),
            )
            st.plotly_chart(fig, use_container_width=True)

    # ------------------------ RESUMO EXECUTIVO ------------------------

    st.subheader("Resumo Executivo dos Adiantamentos")

    col1, col2, col3 = st.columns(3)
    colunas_exec = [col1, col2, col3]

    for col, dados in zip(colunas_exec, resumo_exec):

        cor = "green" if dados["desvio"] >= 0 else "red"

        html = f"""
        <div style="background:#ffffff; border-radius:12px; padding:18px;
                    box-shadow:0 3px 8px rgba(0,0,0,0.12); font-family:Arial;">
            <h3 style="margin-top:0; margin-bottom:10px;">▶ {dados['limite']} min</h3>

            <div style="font-size:26px; font-weight:600;">
                {dados['qtd_dia']} viagens
            </div>

            <p style="font-size:18px;">
                📊 Último dia: <b>{dados['pct_dia']:.2f}%</b>
            </p>

            <p style="font-size:16px; color:#555;">
                📅 Referência: <b>{dados['pct_media']:.2f}%</b><br>
                <i>({dados['tipo_janela']})</i>
            </p>

            <p style="color:{cor}; font-size:20px; margin-top:10px;">
                <b>{dados['desvio']:+.2f} p.p.</b>
            </p>
        </div>
        """

        col.markdown(html, unsafe_allow_html=True)

# ====================================================================================
# TAB 2 — SITUAÇÃO DA VIAGEM
# ====================================================================================

with tab_sit_viagem:
    st.header("Situação da Viagem — Último Dia vs Referência")

    tab_ult = df_dia.groupby("Situação_viagem").size().reset_index(name="Qtd Último Dia")
    tab_tipo = df_tipo.groupby("Situação_viagem").size().reset_index(name="Qtd Média TipoDia")

    tabela = tab_ult.merge(tab_tipo, on="Situação_viagem", how="outer").fillna(0)

    tabela["% Último Dia"] = tabela["Qtd Último Dia"] / tabela["Qtd Último Dia"].sum() * 100
    tabela["% Média TipoDia"] = tabela["Qtd Média TipoDia"] / tabela["Qtd Média TipoDia"].sum() * 100
    tabela["Desvio (p.p.)"] = tabela["% Último Dia"] - tabela["% Média TipoDia"]

    c1, c2 = st.columns([2, 3])

    with c1:
        st.subheader("Tabela")
        st.dataframe(tabela, use_container_width=True)

    with c2:
        st.subheader("Gráfico")
        graf = tabela[tabela["Situação_viagem"] != "Viagem concluída"]
        if not graf.empty:
            fig = px.bar(
                graf,
                x="Situação_viagem",
                y=["% Média TipoDia", "% Último Dia"],
                barmode="group",
                labels={"value": "% das viagens"},
                height=420,
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Não há dados para exibir.")

# ====================================================================================
# TAB 3 — SITUAÇÃO CATEGORIA
# ====================================================================================

with tab_sit_cat:
    st.header("Situação categoria — Último Dia vs Referência")

    tab_ult = df_dia.groupby("Situação_categoria").size().reset_index(name="Qtd Último Dia")
    tab_tipo = df_tipo.groupby("Situação_categoria").size().reset_index(name="Qtd Média TipoDia")

    tabela = tab_ult.merge(tab_tipo, on="Situação_categoria", how="outer").fillna(0)

    tabela["% Último Dia"] = tabela["Qtd Último Dia"] / tabela["Qtd Último Dia"].sum() * 100
    tabela["% Média TipoDia"] = tabela["Qtd Média TipoDia"] / tabela["Qtd Média TipoDia"].sum() * 100
    tabela["Desvio (p.p.)"] = tabela["% Último Dia"] - tabela["% Média TipoDia"]

    c1, c2 = st.columns([2, 3])

    with c1:
        st.dataframe(tabela, use_container_width=True)

    with c2:
        if not tabela.empty:
            fig = px.bar(
                tabela,
                x="Situação_categoria",
                y=["% Média TipoDia", "% Último Dia"],
                barmode="group",
                labels={"value": "% das viagens"},
                height=420,
            )
            st.plotly_chart(fig, use_container_width=True)

# ====================================================================================
# TAB 4 — RANKINGS
# ====================================================================================

with tab_rankings:
    st.header("Rankings por empresa")

    if "Empresa" not in df_filtro.columns:
        st.warning("Não é possível montar rankings: Coluna 'Empresa' ausente.")
    else:

        base = df_filtro.copy()
        base["Cancelada_flag"] = base["Situação_viagem"].eq("Viagem cancelada")

        agg = base.groupby("Empresa").agg(
            Total=("Adiantamento_min", "size"),
            Adianta3=("Adianta_3", "sum"),
            Adianta5=("Adianta_5", "sum"),
            Adianta10=("Adianta_10", "sum"),
            Canceladas=("Cancelada_flag", "sum"),
        ).reset_index()

        agg = agg[agg["Total"] > 0]

        agg["%_3min"] = agg["Adianta3"] / agg["Total"] * 100
        agg["%_5min"] = agg["Adianta5"] / agg["Total"] * 100
        agg["%_10min"] = agg["Adianta10"] / agg["Total"] * 100
        agg["%_Cancel"] = agg["Canceladas"] / agg["Total"] * 100

        st.subheader("> Adiantamento >3, >5 e >10 min")
        c1, c2, c3 = st.columns(3)

        with c1:
            st.dataframe(agg[["Empresa", "%_3min", "Total"]].sort_values("%_3min", ascending=False))

        with c2:
            st.dataframe(agg[["Empresa", "%_5min", "Total"]].sort_values("%_5min", ascending=False))

        with c3:
            st.dataframe(agg[["Empresa", "%_10min", "Total"]].sort_values("%_10min", ascending=False))

        st.markdown("---")

        st.subheader("Viagens Canceladas")
        st.dataframe(
            agg[["Empresa", "%_Cancel", "Total"]].sort_values("%_Cancel", ascending=False),
            use_container_width=True
        )

        st.markdown("---")

        categorias_r3 = ["ACI", "AVL", "CII", "EXT", "IAC", "IEP", "MRI", "OK", "QUE", "SIS", "TRI", "VNR"]
        base_cat = df_filtro[df_filtro["Situação_categoria"].isin(categorias_r3)]

        if base_cat.empty:
            st.info("Não há registros nas categorias especiais.")
        else:
            rank_cat = (
                base_cat.groupby("Empresa")
                .size()
                .reset_index(name="Qtd_ocorrências")
                .sort_values("Qtd_ocorrências", ascending=False)
            )
            st.dataframe(rank_cat.head(15), use_container_width=True)


