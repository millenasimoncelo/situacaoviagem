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
            # CSV real: separador ; e UTF-8 com BOM
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
# 🎚️ FILTROS (SIDEBAR)
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
# 📌 Preparação: Lógica correta para comparação por tipo de dia
# ====================================================================================

# Garante formato datetime
df_filtro["Data_Agendada"] = pd.to_datetime(df_filtro["Data_Agendada"], errors="coerce")

# Último dia (dia atual da base filtrada)
ultimo_dia = df_filtro["Data_Agendada"].max()

# Registros do dia atual
df_dia = df_filtro[df_filtro["Data_Agendada"] == ultimo_dia].copy()

# Tipo do dia atual
tipo_dia_ult = df_dia["Tipo_Dia"].iloc[0]  # Dia útil, Sábado, Domingo

# -------------------------------------------------------------------------
# 1) DOMINGO → comparar com o domingo anterior
# -------------------------------------------------------------------------
if tipo_dia_ult == "Domingo":
    domingos_anteriores = (
        df_filtro[
            (df_filtro["Tipo_Dia"] == "Domingo")
            & (df_filtro["Data_Agendada"] < ultimo_dia)
        ]
        .sort_values("Data_Agendada", ascending=False)
    )

    if len(domingos_anteriores) == 0:
        st.error("Não há domingo anterior para comparação.")
        st.stop()

    data_ref = domingos_anteriores["Data_Agendada"].iloc[0]
    df_tipo = domingos_anteriores[domingos_anteriores["Data_Agendada"] == data_ref]

# -------------------------------------------------------------------------
# 2) SÁBADO → comparar com o sábado anterior
# -------------------------------------------------------------------------
elif tipo_dia_ult == "Sábado":
    sabados_anteriores = (
        df_filtro[
            (df_filtro["Tipo_Dia"] == "Sábado")
            & (df_filtro["Data_Agendada"] < ultimo_dia)
        ]
        .sort_values("Data_Agendada", ascending=False)
    )

    if len(sabados_anteriores) == 0:
        st.error("Não há sábado anterior para comparação.")
        st.stop()

    data_ref = sabados_anteriores["Data_Agendada"].iloc[0]
    df_tipo = sabados_anteriores[sabados_anteriores["Data_Agendada"] == data_ref]

# -------------------------------------------------------------------------
# 3) DIA ÚTIL → média dos últimos 5 dias úteis anteriores
# -------------------------------------------------------------------------
elif tipo_dia_ult == "Dia útil":
    dias_uteis_anteriores = (
        df_filtro[
            (df_filtro["Tipo_Dia"] == "Dia útil")
            & (df_filtro["Data_Agendada"] < ultimo_dia)
        ]
        .sort_values("Data_Agendada", ascending=False)
    )

    if len(dias_uteis_anteriores) == 0:
        st.error("Não há dias úteis anteriores suficientes.")
        st.stop()

    datas_ref = dias_uteis_anteriores["Data_Agendada"].unique()[:5]
    df_tipo = dias_uteis_anteriores[
        dias_uteis_anteriores["Data_Agendada"].isin(datas_ref)
    ]

# -------------------------------------------------------------------------
# OUTROS CASOS (não deve acontecer)
# -------------------------------------------------------------------------
else:
    st.error(f"Tipo de dia '{tipo_dia_ult}' não reconhecido.")
    st.stop()


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
# 🧩 ABAS PRINCIPAIS
# ====================================================================================

tab_resumo, tab_sit_viagem, tab_sit_cat, tab_rankings = st.tabs(
    ["Resumo (velocímetros)", "Situação da viagem", "Situação categoria", "Rankings por empresa"]
)

# ====================================================================================
# TAB 1 — RESUMO / VELOCÍMETROS
# ====================================================================================

with tab_resumo:
    st.header("Adiantamento — Último Dia vs Referência (dia equivalente anterior)")

    limites = [3, 5, 10]
    colunas = st.columns(len(limites))

    # Determina o texto da referência (janela de comparação)
    if tipo_dia_ult == "Domingo":
        tipo_janela = "domingo anterior"
    elif tipo_dia_ult == "Sábado":
        tipo_janela = "sábado anterior"
    else:
        tipo_janela = "média dos 5 dias úteis anteriores"

    # Lista que será usada no resumo executivo
    resumo_exec = []

    # ---------------------- GAUGES ----------------------
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
            "tipo_janela": tipo_janela,
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
                    number={"suffix": "%", "font": {"size": 40}},
                    gauge={
                        "axis": {
                            "range": [0, max(10, pct_dia * 3, pct_media * 3)],
                            "tickwidth": 1,
                        },
                        "bar": {"color": "#4CAF50"},
                        "borderwidth": 2,
                        "bgcolor": "white",
                    },
                )
            )

            fig_gauge.update_layout(
                title=f"Adiantadas > {LIM} min",
                height=320,
                margin=dict(l=10, r=10, t=70, b=10),
            )

            st.plotly_chart(fig_gauge, use_container_width=True)

    # ====================================================================================
    # RESUMO EXECUTIVO — CAIXAS
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

        # IMPORTANTE: usar textwrap.dedent pra remover a indentação
        html_card = textwrap.dedent(f"""
        <div style="background:#ffffff; border-radius:12px; padding:18px;
                    box-shadow:0 3px 8px rgba(0,0,0,0.12); font-family:Arial;">
            <h3 style="margin-top:0; margin-bottom:10px;">▶ {LIM} min</h3>

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
        """)

        col.markdown(html_card, unsafe_allow_html=True)


# ====================================================================================
# TAB 2 — SITUAÇÃO DA VIAGEM
# ====================================================================================

with tab_sit_viagem:
    st.header("Situação da Viagem — Último Dia vs Referência (dia equivalente anterior)")

    tab_ult = df_dia.groupby("Situação_viagem").size().reset_index(name="Qtd Último Dia")
    tab_tipo = df_tipo.groupby("Situação_viagem").size().reset_index(name="Qtd Média TipoDia")

    tabela_vg = tab_ult.merge(tab_tipo, on="Situação_viagem", how="outer").fillna(0)

    tabela_vg["% Último Dia"] = (
        tabela_vg["Qtd Último Dia"] / tabela_vg["Qtd Último Dia"].sum() * 100
        if tabela_vg["Qtd Último Dia"].sum() > 0
        else 0
    )
    tabela_vg["% Média TipoDia"] = (
        tabela_vg["Qtd Média TipoDia"] / tabela_vg["Qtd Média TipoDia"].sum() * 100
        if tabela_vg["Qtd Média TipoDia"].sum() > 0
        else 0
    )
    tabela_vg["Desvio (p.p.)"] = tabela_vg["% Último Dia"] - tabela_vg["% Média TipoDia"]

    col1, col2 = st.columns([2, 3])

    with col1:
        st.subheader("Tabela")
        st.dataframe(tabela_vg, use_container_width=True)

    with col2:
        st.subheader("Gráfico (sem 'Viagem concluída')")
        grafico_vg = tabela_vg[tabela_vg["Situação_viagem"] != "Viagem concluída"]
        if not grafico_vg.empty:
            fig_vg = px.bar(
                grafico_vg,
                x="Situação_viagem",
                y=["% Média TipoDia", "% Último Dia"],
                barmode="group",
                labels={"value": "% das viagens", "Situação_viagem": "Situação"},
                height=420,
            )
            fig_vg.update_layout(legend_title_text="")
            st.plotly_chart(fig_vg, use_container_width=True)
        else:
            st.info("Não há dados para exibir no gráfico.")

# ====================================================================================
# TAB 3 — SITUAÇÃO CATEGORIA
# ====================================================================================

with tab_sit_cat:
    st.header("Situação categoria — Último Dia vs Referência (dia equivalente anterior)")

    tab_cat_ult = df_dia.groupby("Situação_categoria").size().reset_index(name="Qtd Último Dia")
    tab_cat_tipo = df_tipo.groupby("Situação_categoria").size().reset_index(name="Qtd Média TipoDia")

    tabela_cat = tab_cat_ult.merge(tab_cat_tipo, on="Situação_categoria", how="outer").fillna(0)

    tabela_cat["% Último Dia"] = (
        tabela_cat["Qtd Último Dia"] / tabela_cat["Qtd Último Dia"].sum() * 100
        if tabela_cat["Qtd Último Dia"].sum() > 0
        else 0
    )
    tabela_cat["% Média TipoDia"] = (
        tabela_cat["Qtd Média TipoDia"] / tabela_cat["Qtd Média TipoDia"].sum() * 100
        if tabela_cat["Qtd Média TipoDia"].sum() > 0
        else 0
    )
    tabela_cat["Desvio (p.p.)"] = tabela_cat["% Último Dia"] - tabela_cat["% Média TipoDia"]

    col1, col2 = st.columns([2, 3])

    with col1:
        st.subheader("Tabela")
        st.dataframe(tabela_cat, use_container_width=True)

    with col2:
        st.subheader("Gráfico")
        if not tabela_cat.empty:
            fig_cat = px.bar(
                tabela_cat,
                x="Situação_categoria",
                y=["% Média TipoDia", "% Último Dia"],
                barmode="group",
                labels={"value": "% das viagens", "Situação_categoria": "Categoria"},
                height=420,
            )
            fig_cat.update_layout(legend_title_text="")
            st.plotly_chart(fig_cat, use_container_width=True)
        else:
            st.info("Não há dados para exibir no gráfico.")

# ====================================================================================
# TAB 4 — RANKINGS POR EMPRESA
# ====================================================================================

with tab_rankings:
    st.header("Rankings por empresa")

    if "Empresa" not in df_filtro.columns:
        st.warning("A coluna 'Empresa' não existe na base. Não é possível montar rankings.")
    else:
        # base de agregação por empresa
        base_emp = df_filtro.copy()
        base_emp["Cancelada_flag"] = base_emp["Situação_viagem"].eq("Viagem cancelada")

        agg_emp = (
            base_emp.groupby("Empresa")
            .agg(
                Total_viagens=("Adiantamento_min", "size"),
                Adianta_3=("Adianta_3", "sum"),
                Adianta_5=("Adianta_5", "sum"),
                Adianta_10=("Adianta_10", "sum"),
                Canceladas=("Cancelada_flag", "sum"),
            )
            .reset_index()
        )

        # evita divisão por zero
        agg_emp = agg_emp[agg_emp["Total_viagens"] > 0]

        agg_emp["%_Adianta_3"] = agg_emp["Adianta_3"] / agg_emp["Total_viagens"] * 100
        agg_emp["%_Adianta_5"] = agg_emp["Adianta_5"] / agg_emp["Total_viagens"] * 100
        agg_emp["%_Adianta_10"] = agg_emp["Adianta_10"] / agg_emp["Total_viagens"] * 100
        agg_emp["%_Canceladas"] = agg_emp["Canceladas"] / agg_emp["Total_viagens"] * 100

        # ---------------- Ranking 1: adiantamento >3, >5, >10 ----------------
        st.subheader("Ranking 1 — Percentual de viagens adiantadas (>3, >5, >10 min)")

        c1, c2, c3 = st.columns(3)

        with c1:
            st.markdown("**> 3 minutos**")
            r3 = agg_emp.sort_values("%_Adianta_3", ascending=False)[
                ["Empresa", "%_Adianta_3", "Total_viagens"]
            ]
            r3["%_Adianta_3"] = r3["%_Adianta_3"].round(2)
            st.dataframe(r3.head(10), use_container_width=True)

        with c2:
            st.markdown("**> 5 minutos**")
            r5 = agg_emp.sort_values("%_Adianta_5", ascending=False)[
                ["Empresa", "%_Adianta_5", "Total_viagens"]
            ]
            r5["%_Adianta_5"] = r5["%_Adianta_5"].round(2)
            st.dataframe(r5.head(10), use_container_width=True)

        with c3:
            st.markdown("**> 10 minutos**")
            r10 = agg_emp.sort_values("%_Adianta_10", ascending=False)[
                ["Empresa", "%_Adianta_10", "Total_viagens"]
            ]
            r10["%_Adianta_10"] = r10["%_Adianta_10"].round(2)
            st.dataframe(r10.head(10), use_container_width=True)

        st.markdown("---")

        # ---------------- Ranking 2: percentual de viagens canceladas ----------------
        st.subheader("Ranking 2 — Percentual de viagens canceladas")

        r_cancel = agg_emp.sort_values("%_Canceladas", ascending=False)[
            ["Empresa", "%_Canceladas", "Total_viagens"]
        ]
        r_cancel["%_Canceladas"] = r_cancel["%_Canceladas"].round(2)
        st.dataframe(r_cancel.head(15), use_container_width=True)

        st.markdown("---")

        # ---------------- Ranking 3: categorias específicas ----------------
        st.subheader("Ranking 3 — Ocorrências por categorias especiais")

        categorias_r3 = ["ACI", "AVL", "CII", "EXT", "IAC", "IEP", "MRI",
                         "OK", "QUE", "SIS", "TRI", "VNR"]

        base_cat = df_filtro[df_filtro["Situação_categoria"].isin(categorias_r3)].copy()

        if base_cat.empty:
            st.info("Não há registros nas categorias ACI, AVL, CII, EXT, IAC, IEP, MRI, OK, QUE, SIS, TRI, VNR.")
        else:
            rank_cat = (
                base_cat.groupby("Empresa")
                .size()
                .reset_index(name="Qtd_ocorrências")
                .sort_values("Qtd_ocorrências", ascending=False)
            )
            st.dataframe(rank_cat.head(15), use_container_width=True)

















