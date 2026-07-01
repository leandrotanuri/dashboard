"""
App de Rastreamento de Anúncios — uso interno apenas.
Mostra: Anúncio → Leads → Agendamentos → Taxa de conversão
"""
import os
import requests
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Rastreamento de Anúncios", page_icon="🎯", layout="wide")


def _get_env(key: str) -> str:
    try:
        return st.secrets.get(key, "") or os.getenv(key, "")
    except Exception:
        return os.getenv(key, "")


def _check_login():
    if st.session_state.get("logged_in"):
        return
    st.title("🎯 Rastreamento de Anúncios")
    st.markdown("---")
    col = st.columns([1, 2, 1])[1]
    with col:
        senha = st.text_input("Senha", type="password")
        if st.button("Entrar", use_container_width=True):
            if senha == _get_env("TRACKING_PASSWORD"):
                st.session_state.logged_in = True
                st.rerun()
            else:
                st.error("Senha incorreta.")
    st.stop()


_check_login()


def _sb_headers():
    key = _get_env("SUPABASE_SECRET_KEY")
    return {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def _sb_get(path: str, params: dict = None):
    url = _get_env("SUPABASE_URL")
    r = requests.get(f"{url}/rest/v1/{path}", headers=_sb_headers(), params=params)
    return r.json() if r.ok else []


# ── Layout ─────────────────────────────────────────────────────────────────────
st.title("🎯 Rastreamento de Anúncios")

clientes = _sb_get("clientes", {"ativo": "eq.true", "select": "id,nome,etapa_conversao"})
if not clientes:
    st.warning("Nenhum cliente cadastrado.")
    st.stop()

with st.sidebar:
    st.markdown("### Cliente")
    cliente_nome = st.selectbox("", [c["nome"] for c in clientes], label_visibility="collapsed")
    cliente = next(c for c in clientes if c["nome"] == cliente_nome)
    st.markdown("---")
    if st.button("Sair"):
        st.session_state.logged_in = False
        st.rerun()

leads_raw = _sb_get("leads", {
    "cliente_id": f"eq.{cliente['id']}",
    "select": "nome,telefone,anuncio_tag,etapa_atual,converteu,evento_capi_enviado,primeira_mensagem,criado_em",
    "order": "criado_em.desc"
})

if not leads_raw:
    st.info("Nenhum lead rastreado ainda para este cliente.")
    st.stop()

df = pd.DataFrame(leads_raw)
df["criado_em"] = pd.to_datetime(df["criado_em"], utc=True)

# ── Filtros na sidebar ─────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Período")
    data_ini = st.date_input("De", value=df["criado_em"].min().date())
    data_fim = st.date_input("Até", value=df["criado_em"].max().date())

    st.markdown("### Buscar por nome")
    filtro_nome = st.text_input("Nome do lead", placeholder="Ex: Ana, João...")

    st.markdown("### Filtrar por mensagem")
    filtro_msg = st.text_input("Palavra-chave na mensagem", placeholder="Ex: ADF01, botox...")

    st.markdown("### Filtrar por etapa")
    etapas_disponiveis = ["Todas"] + sorted(df["etapa_atual"].dropna().unique().tolist())
    filtro_etapa = st.selectbox("Etapa", etapas_disponiveis)

df = df[(df["criado_em"].dt.date >= data_ini) & (df["criado_em"].dt.date <= data_fim)]

if filtro_nome:
    df = df[df["nome"].fillna("").str.contains(filtro_nome, case=False, na=False)]

if filtro_msg:
    df = df[df["primeira_mensagem"].fillna("").str.contains(filtro_msg, case=False, na=False)]

if filtro_etapa != "Todas":
    df = df[df["etapa_atual"] == filtro_etapa]

# ── Métricas ───────────────────────────────────────────────────────────────────
total_leads = len(df)
total_agend = int(df["evento_capi_enviado"].sum())
taxa = total_agend / total_leads * 100 if total_leads else 0

m1, m2, m3 = st.columns(3)
m1.metric("Total de Leads", total_leads)
m2.metric("Agendamentos", total_agend)
m3.metric("Taxa de Conversão", f"{taxa:.1f}%")

st.markdown("---")

# ── Abas ───────────────────────────────────────────────────────────────────────
tab1, tab2 = st.tabs(["👤 Leads", "📊 Por Anúncio"])

with tab1:
    def _formata(subset):
        t = subset[["nome", "telefone", "primeira_mensagem", "anuncio_tag", "etapa_atual", "criado_em"]].copy()
        t.columns = ["Nome", "Telefone", "Primeira Mensagem", "Tag Anúncio", "Etapa", "Data"]
        t["Data"] = t["Data"].dt.strftime("%d/%m %H:%M")
        t["Primeira Mensagem"] = t["Primeira Mensagem"].fillna("—")
        t["Tag Anúncio"] = t["Tag Anúncio"].fillna("(sem tag)")
        return t

    ETAPA_ENTRADA  = "ETAPA LEADS DE ENTRADA"
    ETAPA_AGENDADA = cliente.get("etapa_conversao", "CONSULTA AGENDADA")

    entrada     = df[df["etapa_atual"].str.upper().str.strip() == ETAPA_ENTRADA.upper()]
    agendaram   = df[df["evento_capi_enviado"] == True]
    nao_agendaram = df[
        (df["evento_capi_enviado"] == False) &
        (df["etapa_atual"].str.upper().str.strip() != ETAPA_ENTRADA.upper())
    ]

    st.markdown(f"#### Leads de Entrada ({len(entrada)})")
    if entrada.empty:
        st.info("Nenhum lead em entrada no período.")
    else:
        st.dataframe(_formata(entrada), use_container_width=True, hide_index=True)

    st.markdown(f"#### Agendaram ({len(agendaram)})")
    if agendaram.empty:
        st.info("Nenhum lead agendou ainda.")
    else:
        st.dataframe(_formata(agendaram), use_container_width=True, hide_index=True)

    st.markdown(f"#### Não Agendaram ({len(nao_agendaram)})")
    if nao_agendaram.empty:
        st.info("Nenhum lead sem agendamento.")
    else:
        st.dataframe(_formata(nao_agendaram), use_container_width=True, hide_index=True)

with tab2:
    st.markdown("#### Por Anúncio")
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

    sem_tag = int((df["anuncio_tag"] == "(sem tag)").sum())
    if sem_tag:
        st.caption(f"⚠️ {sem_tag} lead(s) sem tag — use o filtro por mensagem para identificar o anúncio.")
