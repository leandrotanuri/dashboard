"""
App de Rastreamento de Anúncios — uso interno apenas.
Mostra: Anúncio → Leads → Agendamentos → Taxa de conversão
"""
import os
import requests
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Rastreamento de Anúncios", page_icon="🎯", layout="wide")

# ── credenciais ────────────────────────────────────────────────────────────────
def _get_env(key: str) -> str:
    try:
        return st.secrets.get(key, "") or os.getenv(key, "")
    except Exception:
        return os.getenv(key, "")

# ── login simples ──────────────────────────────────────────────────────────────
def _check_login():
    if st.session_state.get("logged_in"):
        return
    st.title("🎯 Rastreamento de Anúncios")
    st.markdown("---")
    col = st.columns([1, 2, 1])[1]
    with col:
        senha = st.text_input("Senha", type="password")
        if st.button("Entrar", use_container_width=True):
            senha_correta = _get_env("TRACKING_PASSWORD")
            if senha == senha_correta:
                st.session_state.logged_in = True
                st.rerun()
            else:
                st.error("Senha incorreta.")
    st.stop()

_check_login()

# ── Supabase helpers ───────────────────────────────────────────────────────────
def _sb_headers():
    key = _get_env("SUPABASE_SECRET_KEY")
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }

def _sb_get(path: str, params: dict = None):
    url = _get_env("SUPABASE_URL")
    r = requests.get(f"{url}/rest/v1/{path}", headers=_sb_headers(), params=params)
    return r.json() if r.ok else []

# ── Layout principal ───────────────────────────────────────────────────────────
st.title("🎯 Rastreamento de Anúncios")

clientes = _sb_get("clientes", {"ativo": "eq.true", "select": "id,nome,etapa_conversao"})
if not clientes:
    st.warning("Nenhum cliente cadastrado.")
    st.stop()

# Seletor de cliente na sidebar
with st.sidebar:
    st.markdown("### Cliente")
    cliente_nome = st.selectbox("", [c["nome"] for c in clientes], label_visibility="collapsed")
    cliente = next(c for c in clientes if c["nome"] == cliente_nome)

    st.markdown("---")
    if st.button("Sair"):
        st.session_state.logged_in = False
        st.rerun()

# ── Dados ──────────────────────────────────────────────────────────────────────
leads_raw = _sb_get("leads", {
    "cliente_id": f"eq.{cliente['id']}",
    "select": "anuncio_tag,etapa_atual,converteu,evento_capi_enviado,criado_em"
})

if not leads_raw:
    st.info("Nenhum lead rastreado ainda para este cliente.")
    st.stop()

df = pd.DataFrame(leads_raw)
df["criado_em"] = pd.to_datetime(df["criado_em"], utc=True)

# ── Filtro de período ──────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Período")
    data_ini = st.date_input("De", value=df["criado_em"].min().date())
    data_fim = st.date_input("Até", value=df["criado_em"].max().date())

df = df[(df["criado_em"].dt.date >= data_ini) & (df["criado_em"].dt.date <= data_fim)]

etapa_conv = cliente.get("etapa_conversao", "CONSULTA AGENDADA")

# ── Métricas gerais ────────────────────────────────────────────────────────────
total_leads = len(df)
total_agend = int(df["evento_capi_enviado"].sum())
taxa_geral  = total_agend / total_leads * 100 if total_leads else 0

m1, m2, m3 = st.columns(3)
m1.metric("Total de Leads", total_leads)
m2.metric("Agendamentos", total_agend)
m3.metric("Taxa de Conversão", f"{taxa_geral:.1f}%")

st.markdown("---")

# ── Tabela por anúncio ─────────────────────────────────────────────────────────
st.markdown("### Por Anúncio")

df["anuncio_tag"] = df["anuncio_tag"].fillna("(sem tag)")

resumo = (
    df.groupby("anuncio_tag")
    .agg(Leads=("anuncio_tag", "count"), Agendamentos=("evento_capi_enviado", "sum"))
    .reset_index()
    .rename(columns={"anuncio_tag": "Anúncio"})
)
resumo["Agendamentos"] = resumo["Agendamentos"].astype(int)
resumo["Taxa"] = (resumo["Agendamentos"] / resumo["Leads"] * 100).round(1).astype(str) + "%"
resumo = resumo.sort_values("Leads", ascending=False).reset_index(drop=True)

st.dataframe(resumo, use_container_width=True, hide_index=True)

# ── Aviso leads sem tag ────────────────────────────────────────────────────────
sem_tag = int((df["anuncio_tag"] == "(sem tag)").sum())
if sem_tag:
    st.caption(f"⚠️ {sem_tag} lead(s) sem tag — configure a mensagem pré-preenchida no Meta Ads.")
