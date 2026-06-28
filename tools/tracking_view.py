"""
Aba de Rastreamento de Anúncios para o dashboard interno.
Lê dados do Supabase e mostra: Anúncio → Leads → Agendamentos → Taxa de conversão.
"""
import os
import requests
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent.parent / ".env")


def _sb_headers():
    key = os.getenv("SUPABASE_SECRET_KEY") or st.secrets.get("SUPABASE_SECRET_KEY", "")
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def _get_clientes():
    url = os.getenv("SUPABASE_URL") or st.secrets.get("SUPABASE_URL", "")
    r = requests.get(f"{url}/rest/v1/clientes", headers=_sb_headers(),
                     params={"ativo": "eq.true", "select": "id,nome,etapa_conversao"})
    return r.json() if r.ok else []


def _get_leads(cliente_id: int):
    url = os.getenv("SUPABASE_URL") or st.secrets.get("SUPABASE_URL", "")
    r = requests.get(f"{url}/rest/v1/leads", headers=_sb_headers(),
                     params={"cliente_id": f"eq.{cliente_id}",
                             "select": "anuncio_tag,etapa_atual,converteu,evento_capi_enviado,criado_em"})
    return r.json() if r.ok else []


def render_tracking_tab():
    st.subheader("Rastreamento de Anúncios")

    clientes = _get_clientes()
    if not clientes:
        st.warning("Nenhum cliente cadastrado no sistema de tracking.")
        return

    nomes = [c["nome"] for c in clientes]
    cliente_nome = st.selectbox("Cliente", nomes, key="tracking_cliente")
    cliente = next(c for c in clientes if c["nome"] == cliente_nome)

    leads_raw = _get_leads(cliente["id"])
    if not leads_raw:
        st.info("Nenhum lead rastreado ainda para este cliente.")
        return

    df = pd.DataFrame(leads_raw)
    df["criado_em"] = pd.to_datetime(df["criado_em"], utc=True)

    # Filtro de período
    col1, col2 = st.columns(2)
    with col1:
        data_ini = st.date_input("De", value=df["criado_em"].min().date(), key="t_ini")
    with col2:
        data_fim = st.date_input("Até", value=df["criado_em"].max().date(), key="t_fim")

    df = df[(df["criado_em"].dt.date >= data_ini) & (df["criado_em"].dt.date <= data_fim)]

    etapa_conv = cliente.get("etapa_conversao", "CONSULTA AGENDADA")

    # ── Métricas gerais ─────────────────────────────────────────────────────────
    total_leads = len(df)
    total_agend = int(df["evento_capi_enviado"].sum())
    taxa_geral  = total_agend / total_leads * 100 if total_leads else 0

    m1, m2, m3 = st.columns(3)
    m1.metric("Total de Leads", total_leads)
    m2.metric(f"Agendamentos ({etapa_conv})", total_agend)
    m3.metric("Taxa de Conversão", f"{taxa_geral:.1f}%")

    st.markdown("---")

    # ── Tabela por anúncio ──────────────────────────────────────────────────────
    st.markdown("#### Por Anúncio")

    df_tag = df.copy()
    df_tag["anuncio_tag"] = df_tag["anuncio_tag"].fillna("(sem tag)")

    resumo = (
        df_tag.groupby("anuncio_tag")
        .agg(
            Leads=("anuncio_tag", "count"),
            Agendamentos=("evento_capi_enviado", "sum"),
        )
        .reset_index()
        .rename(columns={"anuncio_tag": "Anúncio"})
    )
    resumo["Agendamentos"] = resumo["Agendamentos"].astype(int)
    resumo["Taxa"] = (resumo["Agendamentos"] / resumo["Leads"] * 100).round(1).astype(str) + "%"
    resumo = resumo.sort_values("Leads", ascending=False).reset_index(drop=True)

    st.dataframe(resumo, use_container_width=True, hide_index=True)

    # ── Leads sem tag ────────────────────────────────────────────────────────────
    sem_tag = int((df["anuncio_tag"].isna() | (df["anuncio_tag"] == "")).sum())
    if sem_tag:
        st.caption(f"⚠️ {sem_tag} lead(s) sem tag de anúncio — configure a mensagem pré-preenchida no Meta Ads.")
