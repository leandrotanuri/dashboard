"""
Dashboard de Campanhas Meta Ads
Seguidores (E1-DIST) e Mensagens (E2-CAP)
"""

import ast
import os
import sys
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st
from dotenv import load_dotenv


load_dotenv(Path(__file__).parent.parent / ".env")

# Streamlit Cloud: carrega secrets como variáveis de ambiente
try:
    import streamlit as _st
    for _k, _v in _st.secrets.items():
        if isinstance(_v, str) and not os.getenv(_k):
            os.environ[_k] = _v
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent))

ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN")
API_VERSION = "v19.0"
BASE_URL = f"https://graph.facebook.com/{API_VERSION}"

FOLLOWER_KEYWORD = "E1-DIST"
MESSAGING_KEYWORD = "E2-CAP"
FIELDS_CAMPAIGN = "campaign_name,impressions,clicks,spend,reach,ctr,cpm,actions"

# ── config por cliente ─────────────────────────────────────────────────────────
MONTH_TAB = {
    1:"📈 Jan",2:"📈 Fev",3:"📈 Mar",4:"📈 Abr",
    5:"📈 Mai",6:"📈 Jun",7:"📈 Jul",8:"📈 Ago",
    9:"📈 Set",10:"📈 Out",11:"📈 Nov",12:"📈 Dez",
}

CLIENTS = {
    "Dr. Vinicius": {
        "account_id": "act_10205578707965893",
        "spreadsheet_id": "1hajaZpK-2cGY4TEpVGTfM7DljZk0M9fiLO6qylC29Gw",
    },
}

DEFAULT_CLIENT = "Dr. Vinicius"

# ── helpers de formatação ──────────────────────────────────────────────────────

def fmt_brl(value: float) -> str:
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def fmt_num(value: float) -> str:
    return f"{int(value):,}".replace(",", ".")

def fmt_pct(value: float) -> str:
    return f"{value:.2f}%"

def extract_action(raw, action_type: str) -> int:
    if not raw or (isinstance(raw, float) and pd.isna(raw)):
        return 0
    try:
        actions = ast.literal_eval(raw) if isinstance(raw, str) else raw
        for a in actions:
            if a.get("action_type") == action_type:
                return int(a.get("value", 0))
    except Exception:
        pass
    return 0

# ── busca de dados ─────────────────────────────────────────────────────────────

@st.cache_data(ttl=7200)
def fetch_campaign_insights(date_start: str, date_end: str, account_id: str) -> pd.DataFrame:
    url = f"{BASE_URL}/{account_id}/insights"
    params = {
        "access_token": ACCESS_TOKEN,
        "level": "campaign",
        "fields": FIELDS_CAMPAIGN,
        "time_range": f'{{"since":"{date_start}","until":"{date_end}"}}',
        "time_increment": 1,
        "limit": 500,
    }
    rows = []
    while url:
        r = requests.get(url, params=params)
        r.raise_for_status()
        data = r.json()
        rows.extend(data.get("data", []))
        url = data.get("paging", {}).get("next")
        params = {}

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    for col in ["impressions", "clicks", "spend", "reach", "ctr", "cpm"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    actions_col = df.get("actions", pd.Series(dtype=object))
    df["messaging_contacts"] = actions_col.apply(
        lambda x: extract_action(x, "onsite_conversion.messaging_first_reply")
    )
    df["date_start"] = pd.to_datetime(df["date_start"])
    return df


@st.cache_data(ttl=7200)
def fetch_sheets_seguidores(spreadsheet_id: str, month: int) -> pd.DataFrame:
    """Lê colunas M (investido E1-DIST) e N (seguidores) via sheets_client."""
    from sheets_client import read_range
    tab = MONTH_TAB[month]
    range_ = f"'{tab}'!M5:N35"
    try:
        rows = read_range(spreadsheet_id, range_)
    except Exception:
        return pd.DataFrame(columns=["dia", "investido_seg", "seguidores"])

    records = []
    for i, row in enumerate(rows):
        dia = i + 1
        investido = float(str(row[0]).replace(",", ".").replace("R$", "").strip()) if len(row) > 0 and row[0] not in ("", None) else 0.0
        seguidores = int(float(str(row[1]).replace(",", "."))) if len(row) > 1 and row[1] not in ("", None) else 0
        records.append({"dia": dia, "investido_seg": investido, "seguidores": seguidores})

    return pd.DataFrame(records) if records else pd.DataFrame(columns=["dia", "investido_seg", "seguidores"])


# ── layout ─────────────────────────────────────────────────────────────────────

st.set_page_config(page_title="Dashboard de Campanhas", page_icon="📊", layout="wide")

st.markdown("""
<style>
    .metric-card {
        background: #f8f9fa;
        border-radius: 10px;
        padding: 16px 20px;
        border-left: 4px solid #4C9BE8;
    }
    div[data-testid="metric-container"] {
        background: #f8f9fa;
        border-radius: 10px;
        padding: 12px 16px;
    }
</style>
""", unsafe_allow_html=True)

st.title("📊 Dashboard de Campanhas")

# ── sidebar — seleção de cliente ───────────────────────────────────────────────

with st.sidebar:
    st.header("Configurações")
    client_name = st.selectbox("Cliente", list(CLIENTS.keys()), index=list(CLIENTS.keys()).index(DEFAULT_CLIENT))

client_cfg = CLIENTS[client_name]
account_id = client_cfg["account_id"]
spreadsheet_id = client_cfg["spreadsheet_id"]

# ── filtros de data ────────────────────────────────────────────────────────────

col_a, col_b, col_c = st.columns([1, 1, 4])
today = date.today()
first_day = today.replace(day=1)

with col_a:
    date_start = st.date_input("De", value=first_day, max_value=today)
with col_b:
    date_end = st.date_input("Até", value=today, max_value=today)

if date_start > date_end:
    st.error("A data inicial deve ser anterior à data final.")
    st.stop()

# ── carrega dados ──────────────────────────────────────────────────────────────

with st.spinner("Buscando dados..."):
    df = fetch_campaign_insights(str(date_start), str(date_end), account_id)
    df_sheets = fetch_sheets_seguidores(spreadsheet_id, date_start.month)

st.caption(f"Última atualização: {datetime.now().strftime('%d/%m/%Y às %H:%M')} · Cache renova a cada 2h")

if df.empty:
    st.warning("Nenhum dado encontrado para o período selecionado.")
    st.stop()

# ── filtra por tipo de campanha ────────────────────────────────────────────────

df_seg = df[df["campaign_name"].str.contains(FOLLOWER_KEYWORD, case=False, na=False)].copy()
df_msg = df[df["campaign_name"].str.contains(MESSAGING_KEYWORD, case=False, na=False)].copy()


TAX_MULTIPLIER = 1.1385

tab1, tab2 = st.tabs(["💬 Mensagens · E2-CAP", "👥 Seguidores · E1-DIST"])

# ══ TAB 1 — MENSAGENS ═════════════════════════════════════════════════════════

with tab1:
    if df_msg.empty:
        st.info("Nenhuma campanha com E2-CAP encontrada no período.")
    else:
        total_spend_m = df_msg["spend"].sum()
        total_impressions_m = df_msg["impressions"].sum()
        total_clicks_m = df_msg["clicks"].sum()
        total_contacts = df_msg["messaging_contacts"].sum()

        total_investido_impostos_m = total_spend_m * TAX_MULTIPLIER
        avg_cpm_m = (total_spend_m / total_impressions_m * 1000) if total_impressions_m > 0 else 0
        avg_ctr_m = (total_clicks_m / total_impressions_m * 100) if total_impressions_m > 0 else 0
        custo_contato = (total_spend_m * TAX_MULTIPLIER / total_contacts) if total_contacts > 0 else None

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Valor Total Investido + Impostos", fmt_brl(total_investido_impostos_m))
        c2.metric("Novos Contatos (MSG)", fmt_num(total_contacts) if total_contacts > 0 else "—")
        c3.metric("Custo por Contato + Impostos", fmt_brl(custo_contato) if custo_contato is not None else "—")
        c4.metric("CPM", fmt_brl(avg_cpm_m))
        c5.metric("CTR", fmt_pct(avg_ctr_m))

        st.divider()

        # Inputs manuais para o funil
        col_inp1, col_inp2, _ = st.columns([1, 1, 3])
        with col_inp1:
            consultas = st.number_input("Consultas agendadas", min_value=0, value=0, step=1)
        with col_inp2:
            cirurgias = st.number_input("Cirurgias realizadas", min_value=0, value=0, step=1)

        # Dados diários
        daily_msg = (
            df_msg.groupby("date_start")
            .agg(
                spend=("spend", "sum"),
                impressions=("impressions", "sum"),
                clicks=("clicks", "sum"),
                Contatos=("messaging_contacts", "sum"),
            )
            .reset_index()
        )
        daily_msg["Custo/Contato"] = daily_msg.apply(
            lambda r: r["spend"] * TAX_MULTIPLIER / r["Contatos"] if r["Contatos"] > 0 else None, axis=1
        )

        # Funil SVG customizado
        reach_total = int(df_msg["reach"].sum()) if "reach" in df_msg.columns else 0
        funnel_labels = ["Alcance", "Impressões", "Cliques", "Mensagens", "Consultas", "Cirurgias"]
        funnel_values = [reach_total, int(total_impressions_m), int(total_clicks_m), int(total_contacts), consultas, cirurgias]
        funnel_colors = ["#5B4FCF", "#6A5ACD", "#7B68EE", "#4C9BE8", "#FFA726", "#43A047"]

        def build_funnel_svg(labels, values, colors):
            W, H_stage, GAP = 300, 55, 3
            n = len(labels)
            # Taper from full width to ~15% — pronounced funnel shape
            stage_widths = [W * (1.0 - 0.85 * i / (n - 1)) for i in range(n)]
            total_h = n * H_stage + (n - 1) * GAP
            parts = [f'<svg viewBox="0 0 {W} {total_h}" xmlns="http://www.w3.org/2000/svg" style="height:450px;width:auto;display:block;margin:30px auto 0">']
            for i, (label, val, color) in enumerate(zip(labels, values, colors)):
                y = i * (H_stage + GAP)
                top_w = stage_widths[i - 1] if i > 0 else W
                bot_w = stage_widths[i]
                xl_t, xr_t = (W - top_w) / 2, (W + top_w) / 2
                xl_b, xr_b = (W - bot_w) / 2, (W + bot_w) / 2
                pts = f"{xl_t:.1f},{y} {xr_t:.1f},{y} {xr_b:.1f},{y+H_stage} {xl_b:.1f},{y+H_stage}"
                parts.append(f'<polygon points="{pts}" fill="{color}"/>')
                cy = y + H_stage / 2
                parts.append(f'<text x="{W/2}" y="{cy-9}" text-anchor="middle" fill="white" font-family="sans-serif" font-size="10" font-weight="bold">{label}</text>')
                val_str = f"{val:,}".replace(",", ".")
                parts.append(f'<text x="{W/2}" y="{cy+11}" text-anchor="middle" fill="white" font-family="sans-serif" font-size="15" font-weight="bold">{val_str}</text>')
            parts.append('</svg>')
            return "".join(parts)

        funnel_svg = build_funnel_svg(funnel_labels, funnel_values, funnel_colors)

        # Gráfico contatos por dia
        fig_contatos = px.bar(
            daily_msg, x="date_start", y="Contatos",
            title="Novos Contatos por Dia",
            labels={"date_start": "Data"},
            color_discrete_sequence=["#4CAF50"],
        )
        fig_contatos.update_layout(showlegend=False, xaxis_title="", yaxis_title="Contatos")

        # Gráfico custo por contato por dia
        fig_custo = px.line(
            daily_msg.dropna(subset=["Custo/Contato"]),
            x="date_start", y="Custo/Contato",
            title="Custo por Contato + Impostos por Dia (R$)",
            labels={"date_start": "Data", "Custo/Contato": "R$"},
            color_discrete_sequence=["#FF6B6B"],
        )
        fig_custo.update_layout(xaxis_title="", yaxis_title="R$")

        col_g1, col_g2 = st.columns(2)
        with col_g1:
            st.markdown("**Funil de Conversão**")
            st.markdown(funnel_svg, unsafe_allow_html=True)
        with col_g2:
            st.plotly_chart(fig_contatos, use_container_width=True)
            st.plotly_chart(fig_custo, use_container_width=True)

        # Tabela por campanha
        st.subheader("Por Campanha")
        camp_msg = (
            df_msg.groupby("campaign_name")
            .agg(
                Investido=("spend", "sum"),
                Impressões=("impressions", "sum"),
                Cliques=("clicks", "sum"),
                Contatos=("messaging_contacts", "sum"),
            )
            .reset_index()
        )
        camp_msg["CPM"] = camp_msg["Investido"] / camp_msg["Impressões"] * 1000
        camp_msg["CTR"] = camp_msg["Cliques"] / camp_msg["Impressões"] * 100
        camp_msg["Custo/Contato"] = camp_msg.apply(
            lambda r: fmt_brl(r["Investido"] / r["Contatos"]) if r["Contatos"] > 0 else "—", axis=1
        )
        camp_msg = camp_msg.rename(columns={"campaign_name": "Campanha"})
        camp_msg["Investido"] = camp_msg["Investido"].apply(fmt_brl)
        camp_msg["CPM"] = camp_msg["CPM"].apply(fmt_brl)
        camp_msg["CTR"] = camp_msg["CTR"].apply(fmt_pct)
        st.dataframe(camp_msg.set_index("Campanha"), use_container_width=True)

# ══ TAB 2 — SEGUIDORES ════════════════════════════════════════════════════════

with tab2:
    if df_seg.empty:
        st.info("Nenhuma campanha com E1-DIST encontrada no período.")
    else:
        # Métricas da API Meta
        total_spend_api = df_seg["spend"].sum()
        total_impressions = df_seg["impressions"].sum()
        total_clicks = df_seg["clicks"].sum()
        total_investido_impostos = total_spend_api * TAX_MULTIPLIER
        avg_cpm = (total_spend_api / total_impressions * 1000) if total_impressions > 0 else 0
        avg_ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0

        # Métricas da planilha (seguidores e custo por seguidor)
        sheets_period = df_sheets[
            (df_sheets["dia"] >= date_start.day) & (df_sheets["dia"] <= date_end.day)
        ] if date_start.month == date_end.month else df_sheets
        total_investido_seg = sheets_period["investido_seg"].sum()
        total_follows = int(sheets_period["seguidores"].sum())
        custo_seg = (total_investido_seg * TAX_MULTIPLIER / total_follows) if total_follows > 0 else None

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Valor Total Investido + Impostos", fmt_brl(total_investido_impostos))
        c2.metric("Seguidores Ganhos", fmt_num(total_follows) if total_follows > 0 else "—")
        c3.metric("Custo por Seguidor + Impostos", fmt_brl(custo_seg) if custo_seg else "—")
        c4.metric("CPM", fmt_brl(avg_cpm))
        c5.metric("CTR", fmt_pct(avg_ctr))

        st.divider()

        # Gráfico diário — cruza API Meta com Sheets
        daily_seg = (
            df_seg.groupby("date_start")
            .agg(spend=("spend", "sum"), impressions=("impressions", "sum"), clicks=("clicks", "sum"))
            .reset_index()
        )
        daily_seg["dia"] = daily_seg["date_start"].dt.day
        daily_seg["CPM"] = daily_seg["spend"] / daily_seg["impressions"] * 1000
        daily_seg = daily_seg.merge(
            df_sheets[["dia", "seguidores"]].rename(columns={"seguidores": "Seguidores"}),
            on="dia", how="left"
        )
        daily_seg["Seguidores"] = daily_seg["Seguidores"].fillna(0)

        col_g1, col_g2 = st.columns(2)
        with col_g1:
            fig1 = px.bar(
                daily_seg, x="date_start", y="Seguidores",
                title="Seguidores por Dia",
                labels={"date_start": "Data"},
                color_discrete_sequence=["#4C9BE8"],
            )
            fig1.update_layout(showlegend=False, xaxis_title="", yaxis_title="Seguidores")
            st.plotly_chart(fig1, use_container_width=True)

        with col_g2:
            fig2 = px.line(
                daily_seg, x="date_start", y="CPM",
                title="CPM por Dia (R$)",
                labels={"date_start": "Data", "CPM": "CPM (R$)"},
                color_discrete_sequence=["#FF6B6B"],
            )
            fig2.update_layout(xaxis_title="", yaxis_title="CPM (R$)")
            st.plotly_chart(fig2, use_container_width=True)

        # Tabela por campanha
        st.subheader("Por Campanha")
        camp_seg = (
            df_seg.groupby("campaign_name")
            .agg(Investido=("spend", "sum"), Impressões=("impressions", "sum"), Cliques=("clicks", "sum"))
            .reset_index()
        )
        camp_seg["CPM"] = camp_seg["Investido"] / camp_seg["Impressões"] * 1000
        camp_seg["CTR"] = camp_seg["Cliques"] / camp_seg["Impressões"] * 100
        camp_seg = camp_seg.rename(columns={"campaign_name": "Campanha"})
        camp_seg["Investido"] = camp_seg["Investido"].apply(fmt_brl)
        camp_seg["CPM"] = camp_seg["CPM"].apply(fmt_brl)
        camp_seg["CTR"] = camp_seg["CTR"].apply(fmt_pct)
        st.dataframe(camp_seg.set_index("Campanha"), use_container_width=True)

