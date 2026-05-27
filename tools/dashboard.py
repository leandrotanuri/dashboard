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

# ── autenticação ───────────────────────────────────────────────────────────────
def _load_passwords() -> dict:
    """Retorna {senha: cliente} lendo de st.secrets ou .env."""
    try:
        pw = st.secrets.get("passwords", {})
        return {v: k for k, v in pw.items()}  # inverte: senha → nome_chave
    except Exception:
        return {}

def _check_auth():
    """Gerencia login. Retorna (cliente_forçado_ou_None, is_admin)."""
    passwords_raw = {}
    try:
        passwords_raw = dict(st.secrets.get("passwords", {}))
    except Exception:
        pass

    admin_pass   = passwords_raw.pop("admin", None)
    # cliente_key → senha  (ex: "Dr. Vinicius" → "abc123")
    client_passes = {v: k for k, v in passwords_raw.items()}  # senha → client_key

    if "auth_client" not in st.session_state:
        st.session_state.auth_client = None
        st.session_state.auth_admin  = False

    if st.session_state.auth_client or st.session_state.auth_admin:
        return st.session_state.auth_client, st.session_state.auth_admin

    # Tela de login
    st.set_page_config(page_title="Dashboard de Campanhas", page_icon="📊", layout="wide")
    st.title("📊 Dashboard de Campanhas")
    st.markdown("---")
    col = st.columns([1, 2, 1])[1]
    with col:
        st.subheader("Acesso restrito")
        senha = st.text_input("Senha", type="password")
        if st.button("Entrar", use_container_width=True):
            if admin_pass and senha == admin_pass:
                st.session_state.auth_admin  = True
                st.session_state.auth_client = None
                st.rerun()
            elif senha in client_passes:
                st.session_state.auth_client = client_passes[senha]
                st.session_state.auth_admin  = False
                st.rerun()
            else:
                st.error("Senha incorreta.")
    st.stop()

_forced_client, _is_admin = _check_auth()
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
        "meta_consultas": 40,
        "meta_cirurgias": 16,
        "tipo": "clinica_geral",
    },
    "Clínica PRC": {
        "account_id": "act_546529263459917",
        "spreadsheet_id": "1BZBBwaAN1wBy6bzDxeEN51CkMJ82He-ckhhOzYifrpY",
        "agendamentos_id": "1JGL8vElaWn-dCtYSPZEPkZMk0-02xLvAaLN2cxtjKd8",
        "meta_pacientes": 20,
        "tipo": "tricologia",
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
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800;900&display=swap');

/* ── Base ── */
html, body,
[data-testid="stAppViewContainer"],
[data-testid="stMain"], .main,
[data-testid="block-container"] {
    background-color: #0b0d17 !important;
    color: #e0e4f0 !important;
    font-family: 'Inter', sans-serif !important;
}
[data-testid="stHeader"] {
    background: #0b0d17 !important;
    border-bottom: 1px solid #1e2235 !important;
}
[data-testid="stToolbar"] { background: #0b0d17 !important; }

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0f1120 0%, #0b0d17 100%) !important;
    border-right: 1px solid #1e2235 !important;
}
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] span {
    color: #b0b8d0 !important;
}
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {
    color: #e0e4f0 !important;
}
[data-testid="stSidebar"] .stButton > button {
    background: #161829 !important;
    color: #b0b8d0 !important;
    border: 1px solid #1e2235 !important;
    border-radius: 8px !important;
    transition: all .15s !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: #1e2235 !important;
    border-color: #00d4ff !important;
    color: #00d4ff !important;
}
[data-testid="stSidebar"] div[data-baseweb="select"] > div {
    background: #161829 !important;
    color: #c8cce8 !important;
    border: 1px solid #1e2235 !important;
    border-radius: 8px !important;
}

/* ── Metric cards ── */
div[data-testid="metric-container"] {
    background: #0f1120 !important;
    border: 1px solid #1e2235 !important;
    border-radius: 10px !important;
    padding: 16px 20px !important;
}
div[data-testid="metric-container"] label,
div[data-testid="metric-container"] [data-testid="stMetricLabel"] p {
    color: #3d4466 !important;
    font-size: 0.72rem !important;
    font-weight: 700 !important;
    text-transform: uppercase !important;
    letter-spacing: 1px !important;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
div[data-testid="metric-container"] [data-testid="stMetricValue"] > div {
    color: #00d4ff !important;
    font-size: 1.4rem !important;
    font-weight: 900 !important;
    letter-spacing: -0.5px !important;
    white-space: nowrap;
}

/* ── Tabs ── */
[data-testid="stTabs"] [data-baseweb="tab-list"] {
    gap: 4px;
    background: transparent !important;
    border-bottom: 1px solid #1e2235 !important;
}
[data-testid="stTabs"] button[data-baseweb="tab"] {
    background: transparent !important;
    color: #5a607a !important;
    border: none !important;
    border-bottom: 2px solid transparent !important;
    padding: 8px 16px !important;
    font-size: 0.82rem !important;
    font-weight: 600 !important;
}
[data-testid="stTabs"] button[aria-selected="true"] {
    color: #00d4ff !important;
    border-bottom: 2px solid #00d4ff !important;
    background: transparent !important;
}
[data-testid="stTabs"] [data-baseweb="tab-panel"] {
    background: transparent !important;
    padding-top: 16px !important;
}

/* ── Dividers ── */
hr { border-color: #1e2235 !important; }

/* ── Headings & text ── */
h1, h2, h3, h4 { color: #e0e4f0 !important; font-family: 'Inter', sans-serif !important; }
p { color: #c8cfe0 !important; }

/* ── Date inputs ── */
[data-testid="stDateInput"] input {
    background: #0f1120 !important;
    color: #e0e4f0 !important;
    border: 1px solid #1e2235 !important;
    border-radius: 8px !important;
}
[data-testid="stDateInput"] label { color: #3d4466 !important; font-size: 0.72rem !important; font-weight: 700 !important; text-transform: uppercase !important; letter-spacing: 1px !important; }

/* ── Selectbox ── */
[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
    background: #0f1120 !important;
    color: #e0e4f0 !important;
    border: 1px solid #1e2235 !important;
    border-radius: 8px !important;
}
[data-testid="stSelectbox"] label { color: #3d4466 !important; font-size: 0.72rem !important; font-weight: 700 !important; text-transform: uppercase !important; letter-spacing: 1px !important; }

/* ── Dataframes ── */
[data-testid="stDataFrame"] {
    background: #0f1120 !important;
    border: 1px solid #1e2235 !important;
    border-radius: 10px !important;
}
[data-testid="stDataFrame"] * { color: #c8cfe0 !important; }

/* ── Buttons ── */
.stButton > button {
    background: #161829 !important;
    color: #b0b8d0 !important;
    border: 1px solid #1e2235 !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    transition: all .15s !important;
}
.stButton > button:hover {
    background: #1e2235 !important;
    border-color: #00d4ff !important;
    color: #00d4ff !important;
}

/* ── Progress bar ── */
[data-testid="stProgress"] > div {
    background: #161829 !important;
    border-radius: 4px !important;
}
[data-testid="stProgress"] > div > div {
    background: linear-gradient(90deg, #00d4ff, #00e676) !important;
    border-radius: 4px !important;
}

/* ── Alerts ── */
[data-testid="stAlert"] {
    background: #0f1120 !important;
    border: 1px solid #1e2235 !important;
}
[data-testid="stAlert"] p { color: #c8cfe0 !important; }

/* ── Caption ── */
[data-testid="stCaptionContainer"] p { color: #3d4466 !important; font-size: 0.75rem !important; }

/* ── Spinner ── */
[data-testid="stSpinner"] * { color: #00d4ff !important; }

/* ── Oculta UI padrão Streamlit ── */
#MainMenu { visibility: hidden; }
footer    { visibility: hidden; }
[data-testid="stDecoration"] { display:none; }
[data-testid="stStatusWidget"] { display:none; }
[data-testid="collapsedControl"] { display:none; }

/* ── Tabela customizada ── */
.tbl-wrap { overflow-x:auto; margin-top:4px; }
.tbl-wrap table { width:100%; border-collapse:collapse; font-size:12px; }
.tbl-wrap th {
    color:#3d4466; font-weight:700; font-size:10px; text-transform:uppercase;
    letter-spacing:.8px; padding:9px 12px; text-align:left;
    border-bottom:1px solid #1e2235; white-space:nowrap;
}
.tbl-wrap td { padding:10px 12px; border-bottom:1px solid #161829; color:#8892b0; white-space:nowrap; }
.tbl-wrap tr:hover td { background:#161829; }
.tbl-wrap td.bold { color:#fff; font-weight:700; }
.tbl-wrap td.green { color:#00e676; font-weight:700; }

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: #0b0d17; }
::-webkit-scrollbar-thumb { background: #1e2235; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #2a2f4a; }

/* ── KPI Cards customizados ── */
.kpi-grid { display:grid; gap:12px; margin-bottom:8px; }
.kpi-card {
    background:#0f1120; border:1px solid #1e2235; border-radius:12px;
    padding:18px 20px; display:flex; flex-direction:column; gap:8px;
    transition:.2s; overflow:hidden;
}
.kpi-card:hover { border-color:#2a2f50; transform:translateY(-1px); }
.kpi-label { font-size:10px; font-weight:700; color:#3d4466; text-transform:uppercase; letter-spacing:1.2px; }
.kpi-value { font-size:30px; font-weight:900; line-height:1; letter-spacing:-1px; }
.kpi-sub { font-size:11px; color:#3d4466; display:flex; align-items:center; gap:6px; flex-wrap:wrap; }
.kpi-bar { height:2px; border-radius:2px; margin-top:2px; }
.badge { padding:2px 8px; border-radius:99px; font-size:10px; font-weight:700; }
.badge.ok   { background:#00d4ff22; color:#00d4ff; }
.badge.up   { background:#00e67622; color:#00e676; }
.badge.down { background:#ff444422; color:#ff4444; }
.badge.warn { background:#ffd60022; color:#ffd600; }

/* ── Metric rows customizados ── */
.metrics-col { display:flex; flex-direction:column; gap:7px; }
.metric-row {
    background:#161829; border-radius:8px; padding:12px 14px;
    display:flex; justify-content:space-between; align-items:center;
    border:1px solid #1e2235;
}
.metric-row .ml { font-size:10px; color:#3d4466; font-weight:700; text-transform:uppercase; letter-spacing:.8px; }
.metric-row .mv { font-size:16px; font-weight:800; }

/* ── Roas / visão geral cards ── */
.vg-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin-bottom:4px; }
.vg-card {
    background:#0f1120; border:1px solid #1e2235; border-radius:10px;
    padding:14px 18px; display:flex; flex-direction:column; gap:4px;
}
.vg-label { font-size:10px; font-weight:700; color:#3d4466; text-transform:uppercase; letter-spacing:1px; }
.vg-value { font-size:22px; font-weight:900; color:#e0e4f0; }
</style>
""", unsafe_allow_html=True)

# template base para todos os gráficos Plotly
_PD = dict(
    paper_bgcolor="#0b0d17",
    plot_bgcolor="#0f1120",
    font=dict(color="#c8cfe0", family="Inter, sans-serif"),
    xaxis=dict(gridcolor="#1e2235", linecolor="#1e2235", tickfont=dict(color="#5a607a")),
    yaxis=dict(gridcolor="#1e2235", linecolor="#1e2235", tickfont=dict(color="#5a607a")),
    title_font=dict(color="#c8cce8", size=13),
    margin=dict(t=36, l=8, r=8, b=8),
)

_COL = {"cyan":"#00d4ff","green":"#00e676","yellow":"#ffd600","white":"#ffffff","red":"#ff4444","purple":"#a78bfa"}
_BAR = {
    "cyan":   "linear-gradient(90deg,#00d4ff,#7B6CF6)",
    "green":  "linear-gradient(90deg,#00e676,#00b248)",
    "yellow": "linear-gradient(90deg,#ffd600,#ff8f00)",
    "white":  "linear-gradient(90deg,#7B6CF6,#a855f7)",
    "red":    "linear-gradient(90deg,#ff4444,#c62828)",
    "purple": "linear-gradient(90deg,#a78bfa,#7B6CF6)",
}

def _kpi_html(cards: list, cols: int = 0) -> str:
    """Renderiza linha de KPI cards com visual idêntico ao preview."""
    n = cols if cols > 0 else len(cards)
    items = []
    for c in cards:
        col    = c.get("color", "cyan")
        badge  = c.get("badge", "")
        bcls   = c.get("badge_cls", "ok")
        sub    = c.get("sub", "")
        badge_html = f'<span class="badge {bcls}">{badge}</span>' if badge else ""
        items.append(f"""
        <div class="kpi-card">
          <div class="kpi-label">{c['label']}</div>
          <div class="kpi-value" style="color:{_COL.get(col,col)}">{c['value']}</div>
          <div class="kpi-sub">{badge_html}{sub}</div>
          <div class="kpi-bar" style="background:{_BAR.get(col,'')}"></div>
        </div>""")
    return (f'<div class="kpi-grid" style="grid-template-columns:repeat({n},1fr)">'
            + "".join(items) + "</div>")

def _metric_rows_html(rows: list) -> str:
    """Renderiza coluna de métricas de performance como linhas escuras."""
    items = []
    for r in rows:
        col = _COL.get(r.get("color","white"), r.get("color","#fff"))
        items.append(
            f'<div class="metric-row">'
            f'<div class="ml">{r["label"]}</div>'
            f'<div class="mv" style="color:{col}">{r["value"]}</div>'
            f'</div>'
        )
    return '<div class="metrics-col">' + "".join(items) + "</div>"

def _pill(val_str: str) -> str:
    """Converte 'XX.XX%' num pill colorido (verde/amarelo/vermelho)."""
    try:
        v = float(val_str.replace("%", "").replace(",", "."))
        cls = "ok" if v >= 50 else ("warn" if v >= 35 else "bad")
    except Exception:
        cls = "ok"
    return f'<span class="pill {cls}">{val_str}</span>'

def _tabela_html(dt_out: pd.DataFrame, tipo_cli: str) -> str:
    """Renderiza tabela Por Dia como HTML customizado com pills e dark style."""
    base_cols  = ["Dia", "Invest. c/ Imposto", "CPM", "CPC", "CTR", "Tx Passagem", "Leads", "CPL", "Consultas", "Custo por Consulta"]
    extra_cols = ["Cirurgias Confirmadas", "Custo por Cirurgia"] if tipo_cli == "clinica_geral" else []
    headers_lbl = ["DIA", "INVEST.", "CPM", "CPC", "CTR", "TX. PASSAGEM", "LEADS", "CPL", "CONSULTAS", "CUSTO/CONS."]
    if tipo_cli == "clinica_geral":
        headers_lbl += ["CIRURGIAS", "CUSTO/CIR."]
    all_cols = base_cols + extra_cols

    thead = "".join(f"<th>{h}</th>" for h in headers_lbl)
    rows  = []
    for _, row in dt_out.iterrows():
        cells = []
        for col in all_cols:
            val = str(row.get(col, "—"))
            if col == "Tx Passagem":
                cells.append(f"<td>{_pill(val)}</td>")
            elif col == "Leads":
                cells.append(f'<td class="bold">{val}</td>')
            elif col in ("Consultas", "Cirurgias Confirmadas") and val not in ("—", "0"):
                cells.append(f'<td class="green">{val}</td>')
            elif col == "Dia":
                cells.append(f'<td style="color:#c8cfe0;font-weight:600">{val}</td>')
            else:
                cells.append(f"<td>{val}</td>")
        rows.append(f"<tr>{''.join(cells)}</tr>")

    return (
        '<div class="tbl-wrap">'
        f'<table><thead><tr>{thead}</tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table></div>'
    )

def _tabela_campanha_html(camp_out: pd.DataFrame) -> str:
    """Renderiza tabela Por Campanha como HTML customizado."""
    cols = list(camp_out.columns)
    thead = "".join(f"<th>{c.upper()}</th>" for c in ["CAMPANHA"] + cols)
    rows  = []
    for idx, row in camp_out.iterrows():
        name_cell = f'<td style="color:#c8cfe0;font-weight:600;max-width:320px;overflow:hidden;text-overflow:ellipsis">{idx}</td>'
        cells = [name_cell] + [f"<td>{row[c]}</td>" for c in cols]
        rows.append(f"<tr>{''.join(cells)}</tr>")
    return (
        '<div class="tbl-wrap">'
        f'<table><thead><tr>{thead}</tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table></div>'
    )

def build_funnel_html(labels, values, colors, pcts=None) -> str:
    """Funil com blocos retangulares de bordas arredondadas e borda esquerda colorida."""
    items = []
    for i, (label, val, color) in enumerate(zip(labels, values, colors)):
        pct_str = f"{pcts[i]:.1f}%" if pcts and i < len(pcts) and pcts[i] is not None else ""
        val_str = f"{val:,}".replace(",", ".")
        items.append(
            f'<div style="background:{color}11;border:1px solid #1e2235;border-left:3px solid {color};'
            f'border-radius:8px;padding:14px 20px;display:flex;align-items:center;justify-content:space-between">'
            f'<div>'
            f'<div style="font-size:10px;font-weight:700;color:{color};text-transform:uppercase;letter-spacing:1px">{label}</div>'
            f'<div style="font-size:10px;color:#3d4466;margin-top:3px">{pct_str}</div>'
            f'</div>'
            f'<div style="font-size:24px;font-weight:900;color:#fff">{val_str}</div>'
            f'</div>'
        )
    return '<div style="display:flex;flex-direction:column;gap:6px;padding:4px 0">' + "".join(items) + "</div>"

def _vg_html(cards: list) -> str:
    """Renderiza cards de visão geral (ROAS, investimento)."""
    items = []
    for c in cards:
        col = _COL.get(c.get("color","white"), c.get("color","#e0e4f0"))
        items.append(
            f'<div class="vg-card">'
            f'<div class="vg-label">{c["label"]}</div>'
            f'<div class="vg-value" style="color:{col}">{c["value"]}</div>'
            f'</div>'
        )
    return '<div class="vg-grid">' + "".join(items) + "</div>"

st.title("📊 Dashboard de Campanhas")

# ── sidebar — seleção de cliente ───────────────────────────────────────────────

with st.sidebar:
    st.header("Configurações")
    if _is_admin:
        client_name = st.selectbox("Cliente", list(CLIENTS.keys()), index=list(CLIENTS.keys()).index(DEFAULT_CLIENT))
    else:
        client_name = _forced_client
        st.markdown(f"**{client_name}**")
    if st.button("Sair", use_container_width=True):
        st.session_state.auth_client = None
        st.session_state.auth_admin  = False
        st.rerun()

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
            try:
                return float(str(val).replace("R$","").replace(".","").replace(",",".").strip() or 0)
            except (ValueError, TypeError):
                return 0.0
        def parse_num(val):
            if not val or val in ("", None):
                return 0
            try:
                return int(float(str(val).replace(",",".")))
            except (ValueError, TypeError):
                return 0
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

tab1, tab2, tab3, tab4 = st.tabs(["💬 Mensagens · E2-CAP", "👥 Seguidores · E1-DIST", "📊 Funil Completo", "🎯 Metas"])

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

        st.markdown(_kpi_html([
            {"label": "Investimento c/ Impostos", "value": fmt_brl(total_investido_impostos_m),
             "color": "cyan",   "badge": "E2-CAP", "badge_cls": "ok"},
            {"label": "Novos Contatos",            "value": fmt_num(total_contacts) if total_contacts > 0 else "—",
             "color": "green"},
            {"label": "CPL Real",                  "value": fmt_brl(custo_contato) if custo_contato else "—",
             "color": "yellow"},
            {"label": "CPM",  "value": fmt_brl(avg_cpm_m),  "color": "white"},
            {"label": "CTR",  "value": fmt_pct(avg_ctr_m),  "color": "white"},
            {"label": "CPC",  "value": fmt_brl(avg_cpc_m) if avg_cpc_m else "—", "color": "white"},
        ], cols=6), unsafe_allow_html=True)

        st.divider()

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

        # Funil SVG customizado (removido da tab1 — mantido só no Funil Completo)

        # (build_funnel_svg movida para módulo — não usada aqui)

        # Gráficos
        fig_contatos = px.bar(
            daily_msg, x="date_start", y="Contatos",
            labels={"date_start": ""},
            color_discrete_sequence=["#00e676"],
        )
        fig_contatos.update_layout(showlegend=False, xaxis_title="", yaxis_title="", **_PD)

        fig_custo = px.line(
            daily_msg.dropna(subset=["Custo/Contato"]),
            x="date_start", y="Custo/Contato",
            labels={"date_start": "", "Custo/Contato": ""},
            color_discrete_sequence=["#ffd600"],
        )
        fig_custo.update_layout(xaxis_title="", yaxis_title="", **_PD)

        col_g1, col_g2 = st.columns(2)
        with col_g1:
            st.markdown("""
            <div style="background:#0f1120;border:1px solid #1e2235;border-radius:12px;padding:18px 20px 4px">
            <div style="font-size:13px;font-weight:700;color:#c8cce8">Novos Contatos por Dia</div>
            <div style="font-size:11px;color:#3d4466;margin-top:2px;margin-bottom:8px">Mensagens iniciadas no período</div>
            """, unsafe_allow_html=True)
            st.plotly_chart(fig_contatos, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)
        with col_g2:
            st.markdown("""
            <div style="background:#0f1120;border:1px solid #1e2235;border-radius:12px;padding:18px 20px 4px">
            <div style="font-size:13px;font-weight:700;color:#c8cce8">CPL por Dia (R$)</div>
            <div style="font-size:11px;color:#3d4466;margin-top:2px;margin-bottom:8px">Custo por contato com imposto</div>
            """, unsafe_allow_html=True)
            st.plotly_chart(fig_custo, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

        # Tabela por campanha
        st.markdown('<div style="font-size:18px;font-weight:800;color:#e0e4f0;margin:16px 0 8px">Por Campanha</div>', unsafe_allow_html=True)
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
        st.markdown(_tabela_campanha_html(camp_out.set_index("Campanha")), unsafe_allow_html=True)

        # ── Tabela por dia ────────────────────────────────────────────────────
        st.markdown("""
        <div style="font-size:18px;font-weight:800;color:#e0e4f0;margin:20px 0 2px">Por Dia</div>
        <div style="font-size:11px;color:#3d4466;margin-bottom:10px">Detalhamento diário</div>
        """, unsafe_allow_html=True)

        daily_tab = (
            df_msg.groupby("date_start")
            .agg(
                spend=("spend", "sum"),
                impressions=("impressions", "sum"),
                link_clicks=("inline_link_clicks", "sum"),
                leads=("messaging_contacts", "sum"),
            )
            .reset_index()
        )
        daily_tab["invest_imp"] = daily_tab["spend"] * TAX_MULTIPLIER
        daily_tab["CPM"]        = daily_tab.apply(lambda r: r["spend"] / r["impressions"] * 1000 if r["impressions"] > 0 else None, axis=1)
        daily_tab["CPC"]        = daily_tab.apply(lambda r: r["spend"] / r["link_clicks"] if r["link_clicks"] > 0 else None, axis=1)
        daily_tab["CTR"]        = daily_tab.apply(lambda r: r["link_clicks"] / r["impressions"] * 100 if r["impressions"] > 0 else None, axis=1)
        daily_tab["CPL"]        = daily_tab.apply(lambda r: r["invest_imp"] / r["leads"] if r["leads"] > 0 else None, axis=1)
        daily_tab["Tx Passagem"]= daily_tab.apply(lambda r: r["leads"] / r["link_clicks"] * 100 if r["link_clicks"] > 0 else None, axis=1)

        # Cruza com agendamentos por dia
        if not df_agend.empty and "dt" in df_agend.columns:
            agend_day = (
                df_agend.groupby("dt")
                .agg(consultas=("consultas","sum"), cirurgias=("cirurgias","sum"),
                     fat_consultas=("total_consultas","sum"), fat_cirurgias=("total_cirurgias","sum"))
                .reset_index()
            )
            agend_day = agend_day.rename(columns={"dt": "date_start"})
            daily_tab = daily_tab.merge(agend_day, on="date_start", how="left")
        else:
            daily_tab["consultas"]     = None
            daily_tab["cirurgias"]     = None
            daily_tab["fat_consultas"] = None
            daily_tab["fat_cirurgias"] = None

        daily_tab["custo_consulta"] = daily_tab.apply(
            lambda r: r["invest_imp"] / r["consultas"] if pd.notna(r.get("consultas")) and r.get("consultas", 0) > 0 else None, axis=1)
        daily_tab["custo_cirurgia"] = daily_tab.apply(
            lambda r: r["invest_imp"] / r["cirurgias"] if pd.notna(r.get("cirurgias")) and r.get("cirurgias", 0) > 0 else None, axis=1)

        # Monta tabela formatada
        tipo_cli = client_cfg.get("tipo", "clinica_geral")
        dt_out = pd.DataFrame()
        dt_out["Dia"]                  = daily_tab["date_start"].dt.strftime("%d/%m/%Y")
        dt_out["Invest. c/ Imposto"]   = daily_tab["invest_imp"].apply(fmt_brl)
        dt_out["CPM"]                  = daily_tab["CPM"].apply(lambda v: fmt_brl(v) if v is not None else "—")
        dt_out["CPC"]                  = daily_tab["CPC"].apply(lambda v: fmt_brl(v) if v is not None else "—")
        dt_out["CTR"]                  = daily_tab["CTR"].apply(lambda v: fmt_pct(v) if v is not None else "—")
        dt_out["Tx Passagem"]          = daily_tab["Tx Passagem"].apply(lambda v: fmt_pct(v) if v is not None else "—")
        dt_out["Leads"]                = daily_tab["leads"].apply(fmt_num)
        dt_out["CPL"]                  = daily_tab["CPL"].apply(lambda v: fmt_brl(v) if v is not None else "—")
        dt_out["Consultas"]            = daily_tab["consultas"].apply(lambda v: fmt_num(v) if pd.notna(v) else "—")
        dt_out["Custo por Consulta"]   = daily_tab["custo_consulta"].apply(lambda v: fmt_brl(v) if pd.notna(v) else "—")
        if tipo_cli == "clinica_geral":
            dt_out["Cirurgias Confirmadas"] = daily_tab["cirurgias"].apply(lambda v: fmt_num(v) if pd.notna(v) else "—")
            dt_out["Custo por Cirurgia"]    = daily_tab["custo_cirurgia"].apply(lambda v: fmt_brl(v) if pd.notna(v) else "—")

        st.markdown(_tabela_html(dt_out, tipo_cli), unsafe_allow_html=True)

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

        st.markdown(_kpi_html([
            {"label": "Investimento c/ Impostos", "value": fmt_brl(total_investido_impostos),
             "color": "cyan", "badge": "E1-DIST", "badge_cls": "ok"},
            {"label": "Seguidores Ganhos", "value": fmt_num(total_follows) if total_follows > 0 else "—",
             "color": "green"},
            {"label": "Custo por Seguidor",       "value": fmt_brl(custo_seg) if custo_seg else "—",
             "color": "yellow"},
            {"label": "CPM", "value": fmt_brl(avg_cpm),  "color": "white"},
            {"label": "CTR", "value": fmt_pct(avg_ctr),  "color": "white"},
            {"label": "CPC", "value": fmt_brl(avg_cpc) if avg_cpc else "—", "color": "white"},
        ], cols=6), unsafe_allow_html=True)

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

        fig1 = px.bar(daily_seg, x="date_start", y="Seguidores",
                      labels={"date_start": ""}, color_discrete_sequence=["#00d4ff"])
        fig1.update_layout(showlegend=False, xaxis_title="", yaxis_title="", **_PD)

        fig2 = px.line(daily_seg, x="date_start", y="CPM",
                       labels={"date_start": "", "CPM": ""}, color_discrete_sequence=["#a78bfa"])
        fig2.update_layout(xaxis_title="", yaxis_title="", **_PD)

        col_g1, col_g2 = st.columns(2)
        with col_g1:
            st.markdown("""
            <div style="background:#0f1120;border:1px solid #1e2235;border-radius:12px;padding:18px 20px 4px">
            <div style="font-size:13px;font-weight:700;color:#c8cce8">Seguidores por Dia</div>
            <div style="font-size:11px;color:#3d4466;margin-top:2px;margin-bottom:8px">Novos seguidores no período</div>
            """, unsafe_allow_html=True)
            st.plotly_chart(fig1, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)
        with col_g2:
            st.markdown("""
            <div style="background:#0f1120;border:1px solid #1e2235;border-radius:12px;padding:18px 20px 4px">
            <div style="font-size:13px;font-weight:700;color:#c8cce8">CPM por Dia (R$)</div>
            <div style="font-size:11px;color:#3d4466;margin-top:2px;margin-bottom:8px">Custo por mil impressões</div>
            """, unsafe_allow_html=True)
            st.plotly_chart(fig2, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

        # Tabela por campanha
        st.markdown('<div style="font-size:18px;font-weight:800;color:#e0e4f0;margin:16px 0 8px">Por Campanha</div>', unsafe_allow_html=True)
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
        st.markdown(_tabela_campanha_html(camp_seg.set_index("Campanha")), unsafe_allow_html=True)

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

        # Totais das campanhas — E2-CAP + E1-DIST
        invest_liq        = (df_msg["spend"].sum() if not df_msg.empty else 0) + \
                            (df_seg["spend"].sum() if not df_seg.empty else 0)
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
        st.markdown(_kpi_html([
            {"label": "Investimento Líquido",    "value": fmt_brl(invest_liq),  "color": "cyan"},
            {"label": "Investimento + Impostos", "value": fmt_brl(invest_imp),  "color": "cyan"},
            {"label": "ROAS",                    "value": f"{roas:.1f}x",       "color": "green"},
            {"label": "ROAS c/ Impostos",        "value": f"{roas_imp:.1f}x",   "color": "green"},
        ]), unsafe_allow_html=True)

        st.divider()

        # ── Linha 2: Funil ────────────────────────────────────────────────────
        tipo_funil = client_cfg.get("tipo", "clinica_geral")
        col_funil, col_metricas = st.columns([1, 1])

        with col_funil:
            st.markdown('<div style="font-size:13px;font-weight:700;color:#c8cce8;margin-bottom:4px">Funil de Captação</div>', unsafe_allow_html=True)
            if tipo_funil == "tricologia":
                funil_labels_f = ["Impressões", "Cliques", "Mensagens", "Consultas"]
                funil_values_f = [total_impressoes, total_cliques, total_msgs, total_consultas]
                funil_colors_f = ["#00d4ff", "#7B6CF6", "#00e676", "#ffd600"]
                funil_pcts_f   = [100.0,
                                  ctr_f,
                                  tx_passagem,
                                  tx_agend]
            else:
                funil_labels_f = ["Impressões", "Cliques", "Mensagens", "Consultas", "Cirurgias"]
                funil_values_f = [total_impressoes, total_cliques, total_msgs, total_consultas, total_cirurgias]
                funil_colors_f = ["#00d4ff", "#7B6CF6", "#00e676", "#ffd600", "#ff6b6b"]
                funil_pcts_f   = [100.0, ctr_f, tx_passagem, tx_agend, tx_fech]

            st.markdown(build_funnel_html(funil_labels_f, funil_values_f, funil_colors_f, funil_pcts_f),
                        unsafe_allow_html=True)

        with col_metricas:
            _rows_metricas = [
                {"label": "CPM",             "value": fmt_brl(cpm_f),        "color": "cyan"},
                {"label": "CTR",             "value": fmt_pct(ctr_f),        "color": "green"},
                {"label": "CPC",             "value": fmt_brl(cpc_f),        "color": "white"},
                {"label": "CPL (por MSG)",   "value": fmt_brl(cpl_f),        "color": "yellow"},
                {"label": "Tx. Passagem",    "value": fmt_pct(tx_passagem),  "color": "green"},
                {"label": "Tx. Agendamento", "value": fmt_pct(tx_agend),     "color": "green"},
                {"label": "Custo/Consulta",  "value": fmt_brl(custo_consulta),"color": "yellow"},
            ]
            if tipo_funil == "clinica_geral":
                _rows_metricas += [
                    {"label": "Tx. Fechamento",   "value": fmt_pct(tx_fech),       "color": "green"},
                    {"label": "Tx. Conversão",    "value": fmt_pct(tx_conv),       "color": "green"},
                    {"label": "Custo/Cirurgia",   "value": fmt_brl(custo_cirurgia),"color": "yellow"},
                ]
            st.markdown(_metric_rows_html(_rows_metricas), unsafe_allow_html=True)

        st.divider()

        # ── Linha 3: Faturamento ──────────────────────────────────────────────
        st.subheader("Faturamento")
        if tipo_funil == "tricologia":
            st.markdown(_kpi_html([
                {"label": "Consultas",             "value": fmt_num(total_consultas),  "color": "white"},
                {"label": "Ticket Médio Consulta", "value": fmt_brl(ticket_consulta),  "color": "yellow"},
                {"label": "Faturamento Total",     "value": fmt_brl(fat_consultas),    "color": "green"},
            ]), unsafe_allow_html=True)
        else:
            st.markdown(_kpi_html([
                {"label": "Consultas",              "value": fmt_num(total_consultas),  "color": "white"},
                {"label": "Ticket Médio Consulta",  "value": fmt_brl(ticket_consulta),  "color": "yellow"},
                {"label": "Fat. Consultas",         "value": fmt_brl(fat_consultas),    "color": "green"},
                {"label": "Cirurgias",              "value": fmt_num(total_cirurgias),  "color": "white"},
                {"label": "Ticket Médio Cirurgia",  "value": fmt_brl(ticket_cirurgia),  "color": "yellow"},
                {"label": "Faturamento Total",      "value": fmt_brl(fat_total),        "color": "green"},
            ]), unsafe_allow_html=True)

# ══ TAB 4 — METAS ════════════════════════════════════════════════════════════

with tab4:
    import calendar
    from datetime import date as _date

    hoje           = _date.today()
    primeiro_dia   = hoje.replace(day=1).strftime("%Y-%m-%d")
    ultimo_dia     = hoje.replace(day=calendar.monthrange(hoje.year, hoje.month)[1]).strftime("%Y-%m-%d")
    dias_no_mes    = calendar.monthrange(hoje.year, hoje.month)[1]
    dias_passados  = hoje.day
    dias_restantes = dias_no_mes - dias_passados

    tipo_cliente = client_cfg.get("tipo", "clinica_geral")

    df_metas = fetch_agendamentos(agendamentos_id, primeiro_dia, ultimo_dia) if agendamentos_id else pd.DataFrame()

    st.markdown(
        f'<div style="font-size:20px;font-weight:900;color:#e0e4f0;margin-bottom:2px">'
        f'Metas de {hoje.strftime("%B de %Y").capitalize()}</div>'
        f'<div style="font-size:11px;color:#3d4466;margin-bottom:16px">'
        f'Dia {dias_passados} de {dias_no_mes} · {dias_restantes} dias restantes</div>',
        unsafe_allow_html=True
    )

    def _meta_block(titulo, atual, meta, ritmo, proj, dias_rest, unidade="pacientes"):
        faltam  = max(meta - atual, 0)
        pct     = min(atual / meta * 100, 100) if meta > 0 else 0
        nec     = faltam / dias_rest if dias_rest > 0 else 0
        bater   = proj >= meta
        cor_txt = "#00e676" if bater else "#ffd600"
        status  = (f"✅ No ritmo atual ({ritmo:.1f}/dia) vai bater a meta — projeção: <b>{proj}</b> {unidade}."
                   if bater else
                   f"⚠️ Projeção: <b>{proj}</b> {unidade}. Precisa de <b>{nec:.1f}/dia</b> para bater a meta.")
        pct_bar = round(pct)
        col1, col2 = st.columns([2, 1])
        with col1:
            st.markdown(
                f'<div style="background:#0f1120;border:1px solid #1e2235;border-radius:12px;padding:20px 24px">'
                f'<div style="font-size:12px;font-weight:700;color:#3d4466;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">{titulo}</div>'
                f'<div style="font-size:28px;font-weight:900;color:#e0e4f0;margin-bottom:4px">{atual} <span style="font-size:16px;color:#5a607a">/ {meta}</span></div>'
                f'<div style="font-size:11px;color:#3d4466;margin-bottom:12px">faltam <b style="color:{cor_txt}">{faltam}</b> {unidade}</div>'
                f'<div style="background:#161829;border-radius:4px;height:6px;margin-bottom:12px">'
                f'<div style="background:linear-gradient(90deg,#00d4ff,#00e676);height:100%;border-radius:4px;width:{pct_bar}%"></div></div>'
                f'<div style="font-size:12px;color:#8892b0">{status}</div>'
                f'</div>',
                unsafe_allow_html=True
            )
        with col2:
            st.markdown(_kpi_html([
                {"label": "Realizado",          "value": f"{atual}/{meta}",    "color": "cyan"},
                {"label": "Projeção no mês",    "value": str(proj),            "color": "green" if bater else "yellow"},
                {"label": "Ritmo atual",        "value": f"{ritmo:.1f}/dia",   "color": "white"},
            ], cols=1), unsafe_allow_html=True)

    if tipo_cliente == "tricologia":
        META_PACIENTES = client_cfg.get("meta_pacientes", 20)

        if df_metas is None or df_metas.empty:
            total_msgs_m = int(df_msg["messaging_contacts"].sum()) if not df_msg.empty else 0
            ritmo = total_msgs_m / dias_passados if dias_passados > 0 else 0
            proj  = round(ritmo * dias_no_mes)
            _meta_block("👤 Pacientes (Novos Contatos)", total_msgs_m, META_PACIENTES, ritmo, proj, dias_restantes, "pacientes")
        else:
            pacientes_atual = int(df_metas["consultas"].sum())
            ritmo = pacientes_atual / dias_passados if dias_passados > 0 else 0
            proj  = round(ritmo * dias_no_mes)
            _meta_block("👤 Pacientes Atendidos", pacientes_atual, META_PACIENTES, ritmo, proj, dias_restantes, "pacientes")

    else:
        META_CONSULTAS = client_cfg.get("meta_consultas", 40)
        META_CIRURGIAS = client_cfg.get("meta_cirurgias", 16)

        if df_metas is None or df_metas.empty:
            st.info("Nenhum dado de agendamentos encontrado para este mês.")
        else:
            consultas_atual = int(df_metas["consultas"].sum())
            cirurgias_atual = int(df_metas["cirurgias"].sum())

            ritmo_consultas = consultas_atual / dias_passados if dias_passados > 0 else 0
            ritmo_cirurgias = cirurgias_atual / dias_passados if dias_passados > 0 else 0
            proj_consultas  = round(ritmo_consultas * dias_no_mes)
            proj_cirurgias  = round(ritmo_cirurgias * dias_no_mes)

            _meta_block("📅 Agendamentos (Consultas)", consultas_atual, META_CONSULTAS,
                        ritmo_consultas, proj_consultas, dias_restantes, "consultas")
            st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
            _meta_block("🔬 Cirurgias", cirurgias_atual, META_CIRURGIAS,
                        ritmo_cirurgias, proj_cirurgias, dias_restantes, "cirurgias")
