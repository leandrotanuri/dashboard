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
FIELDS_CAMPAIGN = "campaign_name,impressions,clicks,inline_link_clicks,spend,reach,ctr,cpm,actions"

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
        "agendamentos_id": "1cOD2Sa9fp8TPJrBia7RY3br_Htg5pCJc5squzmLY4Dk",
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
    for col in ["impressions", "clicks", "inline_link_clicks", "spend", "reach", "ctr", "cpm"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    actions_col = df.get("actions", pd.Series(dtype=object))
    df["messaging_contacts"] = actions_col.apply(
        lambda x: extract_action(x, "onsite_conversion.messaging_first_reply")
    )
    df["date_start"] = pd.to_datetime(df["date_start"])
    return df


GWS_CMD   = r"C:\Users\leand\AppData\Roaming\npm\gws.cmd"
NODE_PATH = r"C:\Program Files\nodejs"

def _read_sheets_range(spreadsheet_id: str, range_: str) -> list:
    """Lê range via gws (local) ou sheets_client (cloud)."""
    import json, subprocess
    if os.path.exists(GWS_CMD):
        env = os.environ.copy()
        env["PATH"] = NODE_PATH + os.pathsep + env.get("PATH", "")
        result = subprocess.run(
            [GWS_CMD, "sheets", "spreadsheets", "values", "get",
             "--params", json.dumps({"spreadsheetId": spreadsheet_id, "range": range_})],
            capture_output=True, text=True, env=env, shell=True,
        )
        return json.loads(result.stdout).get("values", [])
    else:
        from sheets_client import read_range
        return read_range(spreadsheet_id, range_)

@st.cache_data(ttl=7200)
def fetch_sheets_seguidores(spreadsheet_id: str, month: int) -> pd.DataFrame:
    """Lê colunas M (investido E1-DIST) e N (seguidores)."""
    tab = MONTH_TAB[month]
    range_ = f"'{tab}'!M5:N35"
    try:
        rows = _read_sheets_range(spreadsheet_id, range_)
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
    div[data-testid="metric-container"] label {
        font-size: 0.75rem !important;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    div[data-testid="metric-container"] [data-testid="stMetricValue"] > div {
        font-size: 1.15rem !important;
        white-space: nowrap;
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
agendamentos_id = client_cfg.get("agendamentos_id")

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

@st.cache_data(ttl=7200)
def fetch_agendamentos(spreadsheet_id: str, date_start: str, date_end: str) -> pd.DataFrame:
    """Lê planilha de agendamentos filtrando pelo período selecionado."""
    try:
        rows = _read_sheets_range(spreadsheet_id, "'Planilha agendamento'!A2:G400")
    except Exception as e:
        st.error(f"Erro ao ler agendamentos: {e}")
        return pd.DataFrame(columns=["data","consultas","valor_consulta","total_consultas","cirurgias","valor_cirurgia","total_cirurgias"])

    records = []
    for row in rows:
        if not row or not row[0]:
            continue
        def parse_brl(val):
            if not val or val in ("", None):
                return 0.0
            return float(str(val).replace("R$","").replace(".","").replace(",",".").strip() or 0)
        def parse_num(val):
            if not val or val in ("", None):
                return 0
            return int(float(str(val).replace(",",".")))
        records.append({
            "data":           row[0] if len(row) > 0 else "",
            "consultas":      parse_num(row[1]) if len(row) > 1 else 0,
            "valor_consulta": parse_brl(row[2]) if len(row) > 2 else 0.0,
            "total_consultas":parse_brl(row[3]) if len(row) > 3 else 0.0,
            "cirurgias":      parse_num(row[4]) if len(row) > 4 else 0,
            "valor_cirurgia": parse_brl(row[5]) if len(row) > 5 else 0.0,
            "total_cirurgias":parse_brl(row[6]) if len(row) > 6 else 0.0,
        })

    df = pd.DataFrame(records)
    if df.empty:
        return df

    # Filtra pelo período selecionado (formato dd/mm na planilha)
    ds = pd.to_datetime(date_start)
    de = pd.to_datetime(date_end)
    current_year = ds.year
    df["dt"] = pd.to_datetime(df["data"] + f"/{current_year}", format="%d/%m/%Y", errors="coerce")
    df = df.dropna(subset=["dt"])
    df = df[(df["dt"] >= ds) & (df["dt"] <= de)]
    return df

with st.spinner("Buscando dados..."):
    df = fetch_campaign_insights(str(date_start), str(date_end), account_id)
    df_sheets = fetch_sheets_seguidores(spreadsheet_id, date_start.month)
    df_agend = fetch_agendamentos(agendamentos_id, str(date_start), str(date_end)) if agendamentos_id else pd.DataFrame()

st.caption(f"Última atualização: {datetime.now().strftime('%d/%m/%Y às %H:%M')} · Cache renova a cada 2h")

if df.empty:
    st.warning("Nenhum dado encontrado para o período selecionado.")
    st.stop()

# ── filtra por tipo de campanha ────────────────────────────────────────────────

df_seg = df[df["campaign_name"].str.contains(FOLLOWER_KEYWORD, case=False, na=False)].copy()
df_msg = df[df["campaign_name"].str.contains(MESSAGING_KEYWORD, case=False, na=False)].copy()


TAX_MULTIPLIER = 1.1385

tab1, tab2, tab3 = st.tabs(["💬 Mensagens · E2-CAP", "👥 Seguidores · E1-DIST", "📊 Funil Completo"])

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

        total_link_clicks_m = df_msg["inline_link_clicks"].sum() if "inline_link_clicks" in df_msg.columns else total_clicks_m
        avg_cpc_m = (total_spend_m / total_link_clicks_m) if total_link_clicks_m > 0 else None

        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("Valor Total Investido + Impostos", fmt_brl(total_investido_impostos_m))
        c2.metric("Novos Contatos (MSG)", fmt_num(total_contacts) if total_contacts > 0 else "—")
        c3.metric("Custo por Contato + Impostos", fmt_brl(custo_contato) if custo_contato is not None else "—")
        c4.metric("CPM", fmt_brl(avg_cpm_m))
        c5.metric("CTR", fmt_pct(avg_ctr_m))
        c6.metric("CPC", fmt_brl(avg_cpc_m) if avg_cpc_m is not None else "—")

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
                LinkCliques=("inline_link_clicks", "sum"),
                Contatos=("messaging_contacts", "sum"),
            )
            .reset_index()
        )
        camp_msg["CPM"]           = camp_msg["Investido"] / camp_msg["Impressões"] * 1000
        camp_msg["CTR"]           = camp_msg["Cliques"] / camp_msg["Impressões"] * 100
        camp_msg["CPC"]           = camp_msg.apply(lambda r: r["Investido"] / r["LinkCliques"] if r["LinkCliques"] > 0 else None, axis=1)
        camp_msg["Custo/Contato"] = camp_msg.apply(lambda r: r["Investido"] / r["Contatos"] if r["Contatos"] > 0 else None, axis=1)
        camp_msg = camp_msg.rename(columns={"campaign_name": "Campanha"})
        # Formata e reordena colunas
        camp_out = camp_msg[["Campanha"]].copy()
        camp_out["Investido"]      = camp_msg["Investido"].apply(fmt_brl)
        camp_out["Contatos"]       = camp_msg["Contatos"].apply(fmt_num)
        camp_out["Custo/Contato"]  = camp_msg["Custo/Contato"].apply(lambda v: fmt_brl(v) if v is not None else "—")
        camp_out["Impressões"]     = camp_msg["Impressões"].apply(fmt_num)
        camp_out["CPM"]            = camp_msg["CPM"].apply(fmt_brl)
        camp_out["CTR"]            = camp_msg["CTR"].apply(fmt_pct)
        camp_out["CPC"]            = camp_msg["CPC"].apply(lambda v: fmt_brl(v) if v is not None else "—")
        st.dataframe(camp_out.set_index("Campanha"), use_container_width=True)

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

        total_link_clicks = df_seg["inline_link_clicks"].sum() if "inline_link_clicks" in df_seg.columns else total_clicks
        avg_cpc = (total_spend_api / total_link_clicks) if total_link_clicks > 0 else None

        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("Valor Total Investido + Impostos", fmt_brl(total_investido_impostos))
        c2.metric("Seguidores Ganhos", fmt_num(total_follows) if total_follows > 0 else "—")
        c3.metric("Custo por Seguidor + Impostos", fmt_brl(custo_seg) if custo_seg else "—")
        c4.metric("CPM", fmt_brl(avg_cpm))
        c5.metric("CTR", fmt_pct(avg_ctr))
        c6.metric("CPC", fmt_brl(avg_cpc) if avg_cpc is not None else "—")

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

# ══ TAB 3 — FUNIL COMPLETO ════════════════════════════════════════════════════

with tab3:
    if df_agend is None or df_agend.empty:
        st.info("Nenhum dado de agendamentos encontrado para o período.")
    else:
        # Totais da planilha de agendamentos
        total_consultas   = int(df_agend["consultas"].sum())
        total_cirurgias   = int(df_agend["cirurgias"].sum())
        fat_consultas     = df_agend["total_consultas"].sum()
        fat_cirurgias     = df_agend["total_cirurgias"].sum()
        fat_total         = fat_consultas + fat_cirurgias

        ticket_consulta   = (fat_consultas / total_consultas) if total_consultas > 0 else 0
        ticket_cirurgia   = (fat_cirurgias / total_cirurgias) if total_cirurgias > 0 else 0

        # Totais das campanhas de mensagem (E2-CAP)
        invest_liq        = df_msg["spend"].sum() if not df_msg.empty else 0
        invest_imp        = invest_liq * TAX_MULTIPLIER
        total_msgs        = int(df_msg["messaging_contacts"].sum()) if not df_msg.empty else 0
        total_cliques     = int(df_msg["clicks"].sum()) if not df_msg.empty else 0
        total_impressoes  = int(df_msg["impressions"].sum()) if not df_msg.empty else 0
        reach_total_f     = int(df_msg["reach"].sum()) if not df_msg.empty and "reach" in df_msg.columns else 0

        # ROAS
        roas              = (fat_total / invest_liq) if invest_liq > 0 else 0
        roas_imp          = (fat_total / invest_imp) if invest_imp > 0 else 0

        # Taxas
        tx_passagem       = (total_msgs / total_cliques * 100) if total_cliques > 0 else 0
        tx_agend          = (total_consultas / total_msgs * 100) if total_msgs > 0 else 0
        tx_fech           = (total_cirurgias / total_consultas * 100) if total_consultas > 0 else 0
        tx_conv           = (total_cirurgias / total_cliques * 100) if total_cliques > 0 else 0

        # Custos
        cpm_f             = (invest_liq / total_impressoes * 1000) if total_impressoes > 0 else 0
        ctr_f             = (total_cliques / total_impressoes * 100) if total_impressoes > 0 else 0
        cpc_f             = (invest_liq / total_cliques) if total_cliques > 0 else 0
        cpl_f             = (invest_liq / total_msgs) if total_msgs > 0 else 0
        custo_consulta    = (invest_imp / total_consultas) if total_consultas > 0 else 0
        custo_cirurgia    = (invest_imp / total_cirurgias) if total_cirurgias > 0 else 0

        # ── Linha 1: Investimento + ROAS ──────────────────────────────────────
        st.subheader("Visão Geral")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Investimento Líquido", fmt_brl(invest_liq))
        c2.metric("Investimento + Impostos", fmt_brl(invest_imp))
        c3.metric("ROAS", f"{roas:.1f}x")
        c4.metric("ROAS c/ Impostos", f"{roas_imp:.1f}x")

        st.divider()

        # ── Linha 2: Funil ────────────────────────────────────────────────────
        col_funil, col_metricas = st.columns([1, 1])

        with col_funil:
            st.markdown("**Funil de Captação**")
            funil_labels_f = ["Impressões", "Cliques", "Mensagens", "Consultas", "Cirurgias"]
            funil_values_f = [total_impressoes, total_cliques, total_msgs, total_consultas, total_cirurgias]
            funil_colors_f = ["#5B4FCF", "#6A5ACD", "#4C9BE8", "#FFA726", "#43A047"]

            funil_svg_f = build_funnel_svg(funil_labels_f, funil_values_f, funil_colors_f)
            st.markdown(funil_svg_f, unsafe_allow_html=True)

        with col_metricas:
            st.markdown("**Taxas de Conversão**")
            m1, m2 = st.columns(2)
            m1.metric("Tx. Passagem (CLI→MSG)", fmt_pct(tx_passagem))
            m2.metric("Tx. Agendamento (MSG→CON)", fmt_pct(tx_agend))
            m1.metric("Tx. Fechamento (CON→CIR)", fmt_pct(tx_fech))
            m2.metric("Tx. Conversão (CLI→CIR)", fmt_pct(tx_conv))

            st.markdown("**Custos**")
            m1.metric("CPM", fmt_brl(cpm_f))
            m2.metric("CTR", fmt_pct(ctr_f))
            m1.metric("CPC", fmt_brl(cpc_f))
            m2.metric("CPL (por MSG)", fmt_brl(cpl_f))
            m1.metric("Custo por Consulta", fmt_brl(custo_consulta))
            m2.metric("Custo por Cirurgia", fmt_brl(custo_cirurgia))

        st.divider()

        # ── Linha 3: Faturamento ──────────────────────────────────────────────
        st.subheader("Faturamento")
        f1, f2, f3, f4, f5 = st.columns(5)
        f1.metric("Consultas", fmt_num(total_consultas))
        f2.metric("Ticket Médio Consulta", fmt_brl(ticket_consulta))
        f3.metric("Faturamento Consultas", fmt_brl(fat_consultas))
        f4.metric("Cirurgias", fmt_num(total_cirurgias))
        f5.metric("Ticket Médio Cirurgia", fmt_brl(ticket_cirurgia))

        st.metric("Faturamento Total", fmt_brl(fat_total))

