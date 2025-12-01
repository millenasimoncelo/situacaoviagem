# ====================================================================================
# PAINEL DE CATEGORIZAÇÃO DE VIAGENS — VERSÃO COM UPLOAD, ABAS, SISTEMA E RANKINGS
# ====================================================================================

import os
import pandas as pd
import numpy as np
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px

# janela usada APENAS para ranking (últimos N dias)
JANELA_RANK_DIAS = 7

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
# BLOCO 4 — FUNÇÕES AUXILIARES
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


def formato_br_num(v, casas=0):
    """Formata número no padrão PT-BR."""
    if pd.isna(v):
        return ""
    if casas == 0:
        s = f"{v:,.0f}"
    else:
        s = f"{v:,.{casas}f}"
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return s


def tabela_semáforo(df_tab, colunas_pct, titulo=None):
    """
    Mostra DataFrame com gradiente em vermelho nas colunas de percentual
    e formatação de números no padrão BR.
    (Requer matplotlib instalado no ambiente por causa do background_gradient.)
    """
    if titulo:
        st.subheader(titulo)
    if df_tab.empty:
        st.info("Sem dados para exibir nesta tabela.")
        return

    fmt_funcs = {}

    # Percentuais com 2 casas
    for c in colunas_pct:
        def fmt_pct(v, col=c):
            if pd.isna(v):
                return ""
            return formato_br_num(v, casas=2) + " %"
        fmt_funcs[c] = fmt_pct

    # Se existir coluna 'Total', formatar com milhar
    if "Total" in df_tab.columns:
        def fmt_total(v):
            return formato_br_num(v, casas=0)
        fmt_funcs["Total"] = fmt_total

    styler = (
        df_tab.style
        .format(fmt_funcs)
        .background_gradient(cmap="Reds", subset=colunas_pct)
    )

    st.dataframe(styler, use_container_width=True)


def calcula_adiantamento_equiv(df_base, df_dia, limite):
    """
    Cálculo do adiantamento para:
    - df_dia  : último dia
    - df_base : dias equivalentes anteriores
    """
    if len(df_dia) == 0 or len(df_base) == 0:
        return 0, 0.0, 0.0

    qtd_dia = (df_dia["Adiantamento_min"] > limite).sum()
    pct_dia = qtd_dia / len(df_dia) * 100 if len(df_dia) > 0 else 0.0

    qtd_base = (df_base["Adiantamento_min"] > limite).sum()
    pct_base = qtd_base / len(df_base) * 100 if len(df_base) > 0 else 0.0

    return qtd_dia, pct_dia, pct_base


# ------------------------------------------------------------------------------------
# BLOCO 5 — TRATAMENTO DAS COLUNAS BÁSICAS
# ------------------------------------------------------------------------------------

colunas_necessarias = [
    "Horário_agendado",
    "Horário_realizado",
    "Situação_viagem",
    "Situação_categoria",
    "Empresa"
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

# CRIAÇÃO DO CAMPO SISTEMA (Transcol x Aquaviário)
df["Sistema"] = np.where(
    df["Empresa"].str.contains("VJB", case=False, na=False),
    "Aquaviário",
    "Transcol"
)

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

# Sistema (Transcol x Aquaviário)
sistema_sel = st.sidebar.radio("Sistema", ["Transcol", "Aquaviário"], index=0)

df_sistema = df[df["Sistema"] == sistema_sel].copy()

if df_sistema.empty:
    st.warning("Não há dados para o sistema selecionado.")
    st.stop()

# Empresa
if "Empresa" in df_sistema.columns:
    empresas = sorted(df_sistema["Empresa"].dropna().unique())
    empresas_sel = st.sidebar.multiselect("Empresa", empresas, default=empresas)
else:
    empresas_sel = []

# Linha (se existir)
if "Linha" in df_sistema.columns:
    linhas = sorted(df_sistema["Linha"].dropna().unique())
    linhas_sel = st.sidebar.multiselect("Linha", linhas, default=linhas)
else:
    linhas_sel = []

# Faixa horária
faixas = sorted(df_sistema["Faixa_Horaria"].dropna().unique())
faixas_sel = st.sidebar.multiselect(
    "Faixa Horária (Horário agendado)",
    faixas,
    default=faixas
)

mask = pd.Series(True, index=df_sistema.index)

if empresas_sel and "Empresa" in df_sistema.columns:
    mask &= df_sistema["Empresa"].isin(empresas_sel)

if linhas_sel and "Linha" in df_sistema.columns:
    mask &= df_sistema["Linha"].isin(linhas_sel)

if faixas_sel:
    mask &= df_sistema["Faixa_Horaria"].isin(faixas_sel)

df_filtro = df_sistema[mask].copy()

if df_filtro.empty:
    st.warning("Nenhum dado encontrado com os filtros selecionados.")
    st.stop()

# ------------------------------------------------------------------------------------
# BLOCO 9 — PREPARAÇÃO: ÚLTIMO DIA E DIAS EQUIVALENTES ANTERIORES
# ------------------------------------------------------------------------------------

df_filtro["Data_Agendada"] = pd.to_datetime(
    df_filtro["Data_Agendada"], errors="coerce"
).dt.normalize()

if df_filtro["Data_Agendada"].notna().sum() == 0:
    st.error("Não foi possível identificar datas válidas em Data_Agendada.")
    st.stop()

ultimo_dia = df_filtro["Data_Agendada"].max()
df_ultimo = df_filtro[df_filtro["Data_Agendada"] == ultimo_dia]

if df_ultimo.empty:
    st.error("Não há registros para o último dia encontrado.")
    st.stop()

tipo_dia_ult = df_ultimo["Tipo_Dia"].iloc[0]

# Histórico (apenas datas ANTES do último dia)
df_hist = df_filtro[df_filtro["Data_Agendada"] < ultimo_dia].copy()

if df_hist.empty:
    # caso limite: só há dados do último dia
    df_base_equiv = df_hist.iloc[0:0].copy()  # vazio com mesmas colunas
else:
    if tipo_dia_ult == "Domingo":
        n_dias = 1
    elif tipo_dia_ult == "Sábado":
        n_dias = 1
    else:  # Dia útil
        n_dias = 5

    datas_equiv = (
        df_hist.loc[df_hist["Tipo_Dia"] == tipo_dia_ult, "Data_Agendada"]
        .drop_duplicates()
        .sort_values(ascending=False)
        .head(n_dias)
    )

    df_base_equiv = df_filtro[df_filtro["Data_Agendada"].isin(datas_equiv)].copy()

# ------------------------------------------------------------------------------------
# BLOCO 10 — PREPARAÇÃO ESPECÍFICA PARA RANKING (ÚLTIMOS 7 DIAS)
# ------------------------------------------------------------------------------------

inicio_rank = ultimo_dia - pd.Timedelta(days=JANELA_RANK_DIAS - 1)
df_rank_janela = df_filtro[
    (df_filtro["Data_Agendada"] >= inicio_rank) & (df_filtro["Data_Agendada"] <= ultimo_dia)
].copy()

# ====================================================================================
# BLOCO 11 — ABAS
# ====================================================================================

aba1, aba2, aba3, aba4 = st.tabs(
    [
        "Adiantamento (Velocímetros)",
        "Situação da Viagem",
        "Situação Categoria",
        "Ranking de Empresas",
    ]
)

# ====================================================================================
# BLOCO 12 — ABA 1: ADIANTAMENTO (VELOCÍMETROS)
# ====================================================================================

with aba1:
    st.header("Adiantamento das Viagens — Último dia vs dias equivalentes anteriores")
    st.caption(f"Sistema selecionado: {sistema_sel}")

    colunas = st.columns(3)
    limites = [3, 5, 10]

    tipo_label = tipo_dia_ult.lower()

    for idx, LIM in enumerate(limites):
        qtd_dia, pct_dia, pct_base = calcula_adiantamento_equiv(df_base_equiv, df_ultimo, LIM)
        desvio = pct_dia - pct_base

        with colunas[idx]:
            fig_gauge = go.Figure(
                go.Indicator(
                    mode="gauge+number+delta",
                    value=pct_dia,
                    delta={
                        "reference": pct_base,
                        "valueformat": ".2f",
                        "increasing.color": "green",
                        "decreasing.color": "red",
                    },
                    number={"suffix": "%", "font": {"size": 40}},
                    gauge={
                        "axis": {
                            "range": [0, max(10, pct_dia * 3, pct_base * 3, 5)],
                            "tickwidth": 1
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
                margin=dict(l=10, r=10, t=70, b=10)
            )

            st.plotly_chart(fig_gauge, use_container_width=True)

            st.markdown(
                f"""
                <div style="text-align:center; font-size:16px; margin-top:-12px;">
                Último dia: <b>{qtd_dia}</b> viagens ({pct_dia:.2f}%) • 
                Média de dias equivalentes ({tipo_label}): <b>{pct_base:.2f}%</b> 
                ({'+' if desvio>=0 else ''}{desvio:.2f} p.p.)
                </div>
                """,
                unsafe_allow_html=True
            )

# ====================================================================================
# BLOCO 13 — ABA 2: SITUAÇÃO DA VIAGEM (GRÁFICO + TABELA)
# ====================================================================================

with aba2:
    st.header("Situação da Viagem — Último dia vs dias equivalentes anteriores")
    st.caption(f"Sistema selecionado: {sistema_sel}")

    # Tabelas base
    tab_ult = df_ultimo.groupby("Situação_viagem").size().reset_index(name="Qtd Último Dia")

    if df_base_equiv.empty:
        tab_base = tab_ult.copy()
        tab_base["Qtd Base Dias Equivalentes"] = 0
        tab_base = tab_base[["Situação_viagem", "Qtd Base Dias Equivalentes"]]
    else:
        tab_base = (
            df_base_equiv.groupby("Situação_viagem")
            .size()
            .reset_index(name="Qtd Base Dias Equivalentes")
        )

    tabela_vg = tab_ult.merge(tab_base, on="Situação_viagem", how="outer").fillna(0)

    soma_ult = tabela_vg["Qtd Último Dia"].sum()
    soma_base = tabela_vg["Qtd Base Dias Equivalentes"].sum()

    tabela_vg["% Último Dia"] = (
        tabela_vg["Qtd Último Dia"] / soma_ult * 100 if soma_ult > 0 else 0
    )
    tabela_vg["% Dias Equivalentes"] = (
        tabela_vg["Qtd Base Dias Equivalentes"] / soma_base * 100 if soma_base > 0 else 0
    )
    tabela_vg["Desvio (p.p.)"] = tabela_vg["% Último Dia"] - tabela_vg["% Dias Equivalentes"]

    # Gráfico SEM "Viagem concluída"
    grafico_vg = tabela_vg.copy()
    sv_norm = grafico_vg["Situação_viagem"].astype(str).str.strip().str.lower()
    grafico_vg = grafico_vg[~sv_norm.isin(["viagem concluída", "viagem concluida"])]

    fig_vg = px.bar(
        grafico_vg,
        x="Situação_viagem",
        y=["% Dias Equivalentes", "% Último Dia"],
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
    st.header("Situação Categoria — Último dia vs dias equivalentes anteriores")
    st.caption(f"Sistema selecionado: {sistema_sel}")

    tab_cat_ult = df_ultimo.groupby("Situação_categoria").size().reset_index(name="Qtd Último Dia")

    if df_base_equiv.empty:
        tab_cat_base = tab_cat_ult.copy()
        tab_cat_base["Qtd Base Dias Equivalentes"] = 0
        tab_cat_base = tab_cat_base[["Situação_categoria", "Qtd Base Dias Equivalentes"]]
    else:
        tab_cat_base = (
            df_base_equiv.groupby("Situação_categoria")
            .size()
            .reset_index(name="Qtd Base Dias Equivalentes")
        )

    tabela_cat = tab_cat_ult.merge(tab_cat_base, on="Situação_categoria", how="outer").fillna(0)

    soma_cat_ult = tabela_cat["Qtd Último Dia"].sum()
    soma_cat_base = tabela_cat["Qtd Base Dias Equivalentes"].sum()

    tabela_cat["% Último Dia"] = (
        tabela_cat["Qtd Último Dia"] / soma_cat_ult * 100 if soma_cat_ult > 0 else 0
    )
    tabela_cat["% Dias Equivalentes"] = (
        tabela_cat["Qtd Base Dias Equivalentes"] / soma_cat_base * 100 if soma_cat_base > 0 else 0
    )
    tabela_cat["Desvio (p.p.)"] = tabela_cat["% Último Dia"] - tabela_cat["% Dias Equivalentes"]

    # Gráfico primeiro
    fig_cat = px.bar(
        tabela_cat,
        x="Situação_categoria",
        y=["% Dias Equivalentes", "% Último Dia"],
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
# BLOCO 15 — ABA 4: RANKING DE EMPRESAS (ÚLTIMOS 7 DIAS)
# ====================================================================================

with aba4:
    st.header(f"Ranking de Empresas — Últimos {JANELA_RANK_DIAS} dias (filtros aplicados)")
    st.caption(f"Sistema selecionado: {sistema_sel}")

    if "Empresa" not in df_rank_janela.columns:
        st.info("A coluna 'Empresa' não existe na base. Ranking não pode ser gerado.")
    else:
        df_rank = df_rank_janela.copy()
        if df_rank.empty:
            st.info("Não há dados na janela de dias selecionada para os filtros atuais.")
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

            colunas_pct1 = ["% >3 min", "% >5 min", "% >10 min"]

            tabela_semáforo(
                resumo1[["Empresa", "Total"] + colunas_pct1],
                colunas_pct=colunas_pct1,
                titulo="Empresas com maiores percentuais de viagens adiantadas",
            )

            # ------------------- RANKING 2 — SITUAÇÃO DA VIAGEM (TODAS, EXCETO CONCLUÍDA) -------------------
            st.markdown("### Ranking 2 — Situação da Viagem (distribuição por empresa, exceto 'Viagem concluída')")

            df_sv = df_rank.copy()
            df_sv["Situação_viagem"] = df_sv["Situação_viagem"].fillna("")

            sv_norm = df_sv["Situação_viagem"].str.strip().str.lower()
            mask_concl = sv_norm.isin(["viagem concluída", "viagem concluida"])
            df_sv = df_sv[~mask_concl]

            if df_sv.empty:
                st.info("Não há dados de Situação da Viagem (exceto 'Viagem concluída') para esta janela.")
            else:
                total_emp_sv = df_sv.groupby("Empresa")["Situação_viagem"].size().rename("TotalEmp")
                dist_sv = (
                    df_sv.groupby(["Empresa", "Situação_viagem"])
                    .size()
                    .rename("Qtd")
                    .reset_index()
                )

                dist_sv = dist_sv.merge(total_emp_sv, on="Empresa", how="left")
                dist_sv["%"] = dist_sv["Qtd"] / dist_sv["TotalEmp"] * 100

                tabela_sv_emp = dist_sv.pivot_table(
                    index="Empresa",
                    columns="Situação_viagem",
                    values="%",
                    fill_value=0,
                ).reset_index()

                colunas_pct2 = [c for c in tabela_sv_emp.columns if c != "Empresa"]

                tabela_semáforo(
                    tabela_sv_emp,
                    colunas_pct=colunas_pct2,
                    titulo="Distribuição de Situação da Viagem por Empresa (% dentro da empresa)",
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

            # garantir todas as categorias em colunas (mesmo que 0)
            for c in categorias:
                if c not in tabela_cat_emp.columns:
                    tabela_cat_emp[c] = 0

            tabela_cat_emp = tabela_cat_emp[categorias].reset_index()

            tabela_semáforo(
                tabela_cat_emp,
                colunas_pct=categorias,
                titulo="Distribuição de Situação Categoria por Empresa (% dentro da empresa)",
            )
