# ====================================================================================
# PAINEL DE CATEGORIZAÇÃO DE VIAGENS — VERSÃO COM UPLOAD, ABAS, RANKING E HEATMAP
# ====================================================================================

import os
import pandas as pd
import numpy as np
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px

# ------------------------------------------------------------------------------------
# BLOCO 1 — CONFIGURAÇÃO INICIAL DO STREAMLIT
# ------------------------------------------------------------------------------------

st.set_page_config(
    page_title="Painel de Categorização de Viagens",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("Painel de Categorização de Viagens")

# ------------------------------------------------------------------------------------
# BLOCO 2 — FUNÇÃO PARA CARREGAR DADOS VIA UPLOAD (.CSV ; E .XLSX)
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

    df_final = pd.concat(dfs, ignore_index=True)
    return df_final


# ------------------------------------------------------------------------------------
# BLOCO 3 — UPLOAD DOS ARQUIVOS
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
# BLOCO 4 — FUNÇÃO PARA CLASSIFICAR TIPO DE DIA
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
# BLOCO 5 — TRATAMENTO DAS COLUNAS BÁSICAS
# ------------------------------------------------------------------------------------

colunas_necessarias = [
    "Horário_agendado",
    "Horário_realizado",
    "Situação_viagem",
    "Situação_categoria"
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

# ------------------------------------------------------------------------------------
# BLOCO 6 — CRIAÇÃO DA FAIXA HORÁRIA
# ------------------------------------------------------------------------------------

df["Hora_Agendada"] = df["Horário_agendado"].dt.hour
df["Faixa_Horaria"] = df["Hora_Agendada"].apply(
    lambda h: f"{int(h):02d}:00–{int(h):02d}:59" if pd.notnull(h) else "Sem horário"
)

# ------------------------------------------------------------------------------------
# BLOCO 7 — CÁLCULO DO ADIANTAMENTO
# ------------------------------------------------------------------------------------

df["Adiantamento_min"] = (
    df["Horário_realizado"] - df["Horário_agendado"]
).dt.total_seconds() / 60

df["Adianta_3"] = df["Adiantamento_min"] > 3
df["Adianta_5"] = df["Adiantamento_min"] > 5
df["Adianta_10"] = df["Adiantamento_min"] > 10

# ------------------------------------------------------------------------------------
# BLOCO 8 — FILTROS GLOBAIS (SIDEBAR)
# ------------------------------------------------------------------------------------

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
faixas_sel = st.sidebar.multiselect("Faixa Horária (Horário agendado)", faixas, default=faixas)

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

# ------------------------------------------------------------------------------------
# BLOCO 9 — PREPARAÇÃO: ÚLTIMO DIA E JANELA DE 7 DIAS (REGRA ESPECIAL)
# ------------------------------------------------------------------------------------

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

# ------------------------------------------------------------------------------------
# BLOCO 10 — FUNÇÕES AUXILIARES (ADIANTAMENTO, SEMÁFORO, ETC.)
# ------------------------------------------------------------------------------------

def calcula_adiantamento(df_base, df_dia, limite):
    """Retorna: qtd_dia, pct_dia, qtd_media, pct_media."""
    if len(df_dia) == 0 or len(df_base) == 0:
        return 0, 0.0, 0.0, 0.0

    qtd_dia = (df_dia["Adiantamento_min"] > limite).sum()
    pct_dia = qtd_dia / len(df_dia) * 100

    qtd_media = (df_base["Adiantamento_min"] > limite).sum()
    pct_media = qtd_media / len(df_base) * 100

    return qtd_dia, pct_dia, qtd_media, pct_media


def tabela_semáforo(df_tab, colunas_pct, titulo=None):
    """Mostra DataFrame com gradiente em vermelho nas colunas de percentual."""
    if titulo:
        st.subheader(titulo)
    if df_tab.empty:
        st.info("Sem dados para exibir nesta tabela.")
        return
    fmt = {col: "{:.2f}%" for col in colunas_pct}
    styler = (
        df_tab.style
        .format(fmt)
        .background_gradient(cmap="Reds", subset=colunas_pct)
    )
    st.dataframe(styler, use_container_width=True)


# ====================================================================================
# BLOCO 11 — ABAS
# ====================================================================================

aba1, aba2, aba3, aba4 = st.tabs(
    [
        "Adiantamento (Velocímetros)",
        "Situação da Viagem",
        "Situação Categoria",
        "Ranking & Heatmap de Empresas",
    ]
)

# ====================================================================================
# BLOCO 12 — ABA 1: ADIANTAMENTO (VELOCÍMETROS)
# ====================================================================================

with aba1:
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
# BLOCO 13 — ABA 2: SITUAÇÃO DA VIAGEM (GRÁFICO + TABELA)
# ====================================================================================

with aba2:
    st.header(f"Situação da Viagem — Último Dia vs Média ({JANELA_DIAS} dias)")

    # Tabelas base
    tab_ult = df_dia.groupby("Situação_viagem").size().reset_index(name="Qtd Último Dia")
    tab_tipo = df_tipo.groupby("Situação_viagem").size().reset_index(name="Qtd Média TipoDia")

    tabela_vg = tab_ult.merge(tab_tipo, on="Situação_viagem", how="outer").fillna(0)

    soma_ult = tabela_vg["Qtd Último Dia"].sum()
    soma_tipo = tabela_vg["Qtd Média TipoDia"].sum()

    tabela_vg["% Último Dia"] = (
        tabela_vg["Qtd Último Dia"] / soma_ult * 100 if soma_ult > 0 else 0
    )
    tabela_vg["% Média TipoDia"] = (
        tabela_vg["Qtd Média TipoDia"] / soma_tipo * 100 if soma_tipo > 0 else 0
    )
    tabela_vg["Desvio (p.p.)"] = tabela_vg["% Último Dia"] - tabela_vg["% Média TipoDia"]

    # Gráfico SEM "Viagem concluída"
    grafico_vg = tabela_vg[tabela_vg["Situação_viagem"] != "Viagem concluída"]

    fig_vg = px.bar(
        grafico_vg,
        x="Situação_viagem",
        y=["% Média TipoDia", "% Último Dia"],
        barmode="group",
        labels={"value": "% das viagens", "Situação_viagem": "Situação"},
        height=450
    )
    fig_vg.update_layout(title="Situação da Viagem — Comparação (sem 'Viagem concluída')")

    st.plotly_chart(fig_vg, use_container_width=True)

    # Tabela completa
    st.subheader("Tabela — Situação da Viagem (inclui 'Viagem concluída')")
    st.dataframe(tabela_vg, use_container_width=True)

# ====================================================================================
# BLOCO 14 — ABA 3: SITUAÇÃO CATEGORIA (GRÁFICO + TABELA)
# ====================================================================================

with aba3:
    st.header(f"Situação Categoria — Último Dia vs Média ({JANELA_DIAS} dias)")

    tab_cat_ult = df_dia.groupby("Situação_categoria").size().reset_index(name="Qtd Último Dia")
    tab_cat_tipo = df_tipo.groupby("Situação_categoria").size().reset_index(name="Qtd Média TipoDia")

    tabela_cat = tab_cat_ult.merge(tab_cat_tipo, on="Situação_categoria", how="outer").fillna(0)

    soma_cat_ult = tabela_cat["Qtd Último Dia"].sum()
    soma_cat_tipo = tabela_cat["Qtd Média TipoDia"].sum()

    tabela_cat["% Último Dia"] = (
        tabela_cat["Qtd Último Dia"] / soma_cat_ult * 100 if soma_cat_ult > 0 else 0
    )
    tabela_cat["% Média TipoDia"] = (
        tabela_cat["Qtd Média TipoDia"] / soma_cat_tipo * 100 if soma_cat_tipo > 0 else 0
    )
    tabela_cat["Desvio (p.p.)"] = tabela_cat["% Último Dia"] - tabela_cat["% Média TipoDia"]

    # Gráfico primeiro
    fig_cat = px.bar(
        tabela_cat,
        x="Situação_categoria",
        y=["% Média TipoDia", "% Último Dia"],
        barmode="group",
        labels={"value": "% das viagens", "Situação_categoria": "Categoria"},
        height=450
    )
    fig_cat.update_layout(title="Situação Categoria — Comparação")
    st.plotly_chart(fig_cat, use_container_width=True)

    # Tabela abaixo
    st.subheader("Tabela — Situação Categoria")
    st.dataframe(tabela_cat, use_container_width=True)

# ====================================================================================
# BLOCO 15 — ABA 4: RANKING DE EMPRESAS + HEATMAP
# ====================================================================================

with aba4:
    st.header(f"Ranking de Empresas — Últimos {JANELA_DIAS} dias (filtros aplicados)")

    if "Empresa" not in df_filtro.columns:
        st.info("A coluna 'Empresa' não existe na base. Ranking e heatmap não podem ser gerados.")
    else:
        df_rank = df_janela.copy()
        if df_rank.empty:
            st.info("Não há dados na janela de 7 dias para os filtros selecionados.")
        else:
            # ------------------- RANKING 1 — ADIANTAMENTO -------------------
            st.markdown("### Ranking 1 — Adiantamento (>3, >5, >10 minutos)")

            grp = df_rank.groupby("Empresa")
            resumo1 = grp.agg(
                Total=("Empresa", "size"),
                Adianta3=("Adianta_3", "sum"),
                Adianta5=("Adianta_5", "sum"),
                Adianta10=("Adianta_10", "sum"),
            ).reset_index()

            resumo1["% >3 min"] = resumo1["Adianta3"] / resumo1["Total"] * 100
            resumo1["% >5 min"] = resumo1["Adianta5"] / resumo1["Total"] * 100
            resumo1["% >10 min"] = resumo1["Adianta10"] / resumo1["Total"] * 100

            resumo1 = resumo1.sort_values("% >10 min", ascending=False)

            tabela_semáforo(
                resumo1[["Empresa", "Total", "% >3 min", "% >5 min", "% >10 min"]],
                colunas_pct=["% >3 min", "% >5 min", "% >10 min"],
                titulo="Empresas com maiores percentuais de viagens adiantadas",
            )

            # ------------------- RANKING 2 — SITUAÇÃO DA VIAGEM -------------------
            st.markdown("### Ranking 2 — Situação da Viagem")

            s = df_rank["Situação_viagem"].fillna("").str.lower()

            df_rank["Flg_Cancelada"] = s.str.contains("cancelad")
            df_rank["Flg_NaoMonit"] = s.str.contains("não monitorada") | s.str.contains("nao monitorada")
            df_rank["Flg_Cumprida"] = s.str.contains("concluída") | s.str.contains("concluida")
            df_rank["Flg_ProbHorario"] = (
                s.str.contains("tempo limite") | s.str.contains("horário") | s.str.contains("horario")
            )

            grp2 = df_rank.groupby("Empresa")
            resumo2 = grp2.agg(
                Total=("Empresa", "size"),
                Canceladas=("Flg_Cancelada", "sum"),
                NaoMonit=("Flg_NaoMonit", "sum"),
                Cumpridas=("Flg_Cumprida", "sum"),
                ProbHorario=("Flg_ProbHorario", "sum"),
            ).reset_index()

            resumo2["% Canceladas"] = resumo2["Canceladas"] / resumo2["Total"] * 100
            resumo2["% Não Monit."] = resumo2["NaoMonit"] / resumo2["Total"] * 100
            resumo2["% Cumpridas"] = resumo2["Cumpridas"] / resumo2["Total"] * 100
            resumo2["% Prob. Horário"] = resumo2["ProbHorario"] / resumo2["Total"] * 100

            resumo2 = resumo2.sort_values(["% Não Monit.", "% Canceladas"], ascending=False)

            tabela_semáforo(
                resumo2[
                    [
                        "Empresa",
                        "Total",
                        "% Canceladas",
                        "% Não Monit.",
                        "% Cumpridas",
                        "% Prob. Horário",
                    ]
                ],
                colunas_pct=["% Canceladas", "% Não Monit.", "% Cumpridas", "% Prob. Horário"],
                titulo="Empresas por situação da viagem (semáforo por percentual)",
            )

            # ------------------- RANKING 3 — SITUAÇÃO CATEGORIA -------------------
            st.markdown("### Ranking 3 — Situação Categoria (distribuição por empresa)")

            categorias = ["ACI", "AVL", "CII", "EXT", "IAC", "IEP", "MRI", "OK", "QUE", "SIS", "TRI", "VNR"]

            df_cat = df_rank.copy()
            df_cat["Situação_categoria"] = df_cat["Situação_categoria"].fillna("")

            total_emp = df_cat.groupby("Empresa")["Situação_categoria"].size().rename("TotalEmp")
            dist = (
                df_cat.groupby(["Empresa", "Situação_categoria"])
                .size()
                .rename("Qtd")
                .reset_index()
            )

            dist = dist.merge(total_emp, on="Empresa", how="left")
            dist["% Categoria"] = dist["Qtd"] / dist["TotalEmp"] * 100

            tabela_cat_emp = dist.pivot_table(
                index="Empresa",
                columns="Situação_categoria",
                values="% Categoria",
                fill_value=0,
            )

            for c in categorias:
                if c not in tabela_cat_emp.columns:
                    tabela_cat_emp[c] = 0

            tabela_cat_emp = tabela_cat_emp[categorias].reset_index()

            tabela_semáforo(
                tabela_cat_emp,
                colunas_pct=categorias,
                titulo="Distribuição de Situação Categoria por Empresa (% dentro da empresa)",
            )

            # ------------------- HEATMAP Empresa × Situação da Viagem -------------------
            st.markdown("### Heatmap — Empresa × Situação da Viagem (últimos 7 dias)")

            dist_sv = (
                df_rank.groupby(["Empresa", "Situação_viagem"])
                .size()
                .rename("Qtd")
                .reset_index()
            )

            tot_emp_sv = dist_sv.groupby("Empresa")["Qtd"].sum().rename("TotalEmp")
            dist_sv = dist_sv.merge(tot_emp_sv, on="Empresa", how="left")
            dist_sv["%"] = dist_sv["Qtd"] / dist_sv["TotalEmp"] * 100

            heat = dist_sv.pivot_table(
                index="Empresa",
                columns="Situação_viagem",
                values="%",
                fill_value=0
            )

            if not heat.empty:
                fig_heat = px.imshow(
                    heat,
                    aspect="auto",
                    color_continuous_scale="Reds",
                    labels=dict(color="% das viagens"),
                    height=500
                )
                fig_heat.update_layout(
                    title="Heatmap Empresa × Situação da Viagem (% dentro da empresa)",
                    xaxis_title="Situação da Viagem",
                    yaxis_title="Empresa",
                )
                st.plotly_chart(fig_heat, use_container_width=True)
            else:
                st.info("Não há dados suficientes para o heatmap.")
