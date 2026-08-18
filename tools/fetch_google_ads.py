"""
fetch_google_ads.py — Extrai relatórios de uma conta Google Ads via GAQL.

Foco: contas de GERAÇÃO DE LEAD (lead / cadastro / mensagem), não e-commerce.
Puxa campanhas, grupos de anúncios, palavras-chave, TERMOS DE BUSCA (onde vaza
verba), quebra por conversão e por dispositivo, e salva tudo em CSV para análise.

Pré-requisitos:
    pip install google-ads
    python autenticar_google_ads.py        # gera token_google_ads.json
    .env com GOOGLE_ADS_DEVELOPER_TOKEN (e opcional GOOGLE_ADS_LOGIN_CUSTOMER_ID)

Uso:
    python tools/fetch_google_ads.py --customer_id 123-456-7890 --last_days 30
    python tools/fetch_google_ads.py --customer_id 1234567890 \
        --date_start 2026-07-01 --date_end 2026-07-31

Saída: output/google_ads/<customer_id>/<periodo>/*.csv  + resumo no console.
"""

import argparse
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

try:
    from google.ads.googleads.client import GoogleAdsClient
    from google.ads.googleads.errors import GoogleAdsException
except ImportError:
    print("ERRO: biblioteca google-ads não instalada. Rode: pip install google-ads")
    raise SystemExit(1)

ROOT       = Path(__file__).resolve().parent.parent
CREDS_FILE = ROOT / "credentials.json"
TOKEN_FILE = ROOT / "token_google_ads.json"

load_dotenv(ROOT / ".env")


def digits(cid: str) -> str:
    """Normaliza customer_id: remove traços/espaços, deixa só dígitos."""
    return "".join(ch for ch in str(cid) if ch.isdigit())


def build_client(login_cid=None) -> GoogleAdsClient:
    """Monta o GoogleAdsClient a partir de credentials.json + token_google_ads.json + .env.

    login_cid: ID da MCC (para contas dentro dela). Passe None para contas de
    acesso direto, fora da MCC (ex.: Dr. Vinicius).
    """
    if not CREDS_FILE.exists():
        print("ERRO: credentials.json não encontrado.")
        raise SystemExit(1)
    if not TOKEN_FILE.exists():
        print("ERRO: token_google_ads.json não encontrado. Rode: python autenticar_google_ads.py")
        raise SystemExit(1)

    cfg   = json.loads(CREDS_FILE.read_text())
    oauth = cfg.get("web") or cfg.get("installed") or {}
    token = json.loads(TOKEN_FILE.read_text())

    dev_token = os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN")
    if not dev_token:
        print("ERRO: GOOGLE_ADS_DEVELOPER_TOKEN não definido no .env.")
        raise SystemExit(1)

    refresh_token = token.get("refresh_token")
    if not refresh_token:
        print("ERRO: refresh_token ausente em token_google_ads.json. Rode a autenticação de novo.")
        raise SystemExit(1)

    config = {
        "developer_token": dev_token,
        "client_id":       oauth["client_id"],
        "client_secret":   oauth["client_secret"],
        "refresh_token":   refresh_token,
        "use_proto_plus":  True,
    }
    # login_customer_id: só para contas acessadas VIA MCC. Para contas de acesso
    # direto (fora da MCC), passar login_cid=None omite o header — senão o Google
    # retorna erro de permissão.
    if login_cid:
        config["login_customer_id"] = digits(login_cid)

    return GoogleAdsClient.load_from_dict(config)


def micros(v) -> float:
    return round((v or 0) / 1_000_000, 2)


def run_query(client, customer_id, query, mapper):
    """Executa GAQL via search_stream e devolve DataFrame. Nunca derruba o script inteiro."""
    ga = client.get_service("GoogleAdsService")
    rows = []
    try:
        for batch in ga.search_stream(customer_id=customer_id, query=query):
            for row in batch.results:
                rows.append(mapper(row))
    except GoogleAdsException as ex:
        msgs = "; ".join(e.message for e in ex.failure.errors)
        print(f"  [aviso] consulta falhou: {msgs}")
    return pd.DataFrame(rows)


# ── Mapeadores: 1 por relatório ───────────────────────────────────────────────
def _rate(conv, clicks):
    return round((conv / clicks) * 100, 2) if clicks else 0.0


def map_campaign(r):
    m = r.metrics
    return {
        "campanha": r.campaign.name,
        "status": r.campaign.status.name,
        "canal": r.campaign.advertising_channel_type.name,
        "impressoes": m.impressions,
        "cliques": m.clicks,
        "custo": micros(m.cost_micros),
        "conversoes": round(m.conversions, 2),
        "cpa": micros(m.cost_per_conversion),
        "ctr_%": round(m.ctr * 100, 2),
        "cpc_medio": micros(m.average_cpc),
        "tx_conv_%": round(m.conversions_from_interactions_rate * 100, 2),
        "is_busca_%": round(m.search_impression_share * 100, 2) if m.search_impression_share else None,
        "is_perdida_orcamento_%": round(m.search_budget_lost_impression_share * 100, 2) if m.search_budget_lost_impression_share else None,
        "is_perdida_rank_%": round(m.search_rank_lost_impression_share * 100, 2) if m.search_rank_lost_impression_share else None,
    }


def map_adgroup(r):
    m = r.metrics
    return {
        "campanha": r.campaign.name,
        "grupo": r.ad_group.name,
        "status": r.ad_group.status.name,
        "impressoes": m.impressions,
        "cliques": m.clicks,
        "custo": micros(m.cost_micros),
        "conversoes": round(m.conversions, 2),
        "cpa": micros(m.cost_per_conversion),
        "ctr_%": round(m.ctr * 100, 2),
    }


def map_keyword(r):
    m = r.metrics
    return {
        "campanha": r.campaign.name,
        "grupo": r.ad_group.name,
        "palavra_chave": r.ad_group_criterion.keyword.text,
        "correspondencia": r.ad_group_criterion.keyword.match_type.name,
        "status": r.ad_group_criterion.status.name,
        "quality_score": r.ad_group_criterion.quality_info.quality_score or None,
        "impressoes": m.impressions,
        "cliques": m.clicks,
        "custo": micros(m.cost_micros),
        "conversoes": round(m.conversions, 2),
        "cpa": micros(m.cost_per_conversion),
    }


def map_search_term(r):
    m = r.metrics
    return {
        "termo_buscado": r.search_term_view.search_term,
        "campanha": r.campaign.name,
        "grupo": r.ad_group.name,
        "impressoes": m.impressions,
        "cliques": m.clicks,
        "custo": micros(m.cost_micros),
        "conversoes": round(m.conversions, 2),
        "cpa": micros(m.cost_per_conversion),
    }


def map_conversion(r):
    m = r.metrics
    return {
        "acao_conversao": r.segments.conversion_action_name,
        "conversoes": round(m.conversions, 2),
        "valor_conv": round(m.conversions_value, 2),
        "cpa": micros(m.cost_per_conversion),
    }


def map_device(r):
    m = r.metrics
    return {
        "dispositivo": r.segments.device.name,
        "impressoes": m.impressions,
        "cliques": m.clicks,
        "custo": micros(m.cost_micros),
        "conversoes": round(m.conversions, 2),
        "cpa": micros(m.cost_per_conversion),
        "ctr_%": round(m.ctr * 100, 2),
    }


def build_reports(d1, d2):
    period = f"segments.date BETWEEN '{d1}' AND '{d2}'"
    return {
        "campanhas": (map_campaign, f"""
            SELECT campaign.name, campaign.status, campaign.advertising_channel_type,
                   metrics.impressions, metrics.clicks, metrics.cost_micros,
                   metrics.conversions, metrics.cost_per_conversion, metrics.ctr,
                   metrics.average_cpc, metrics.conversions_from_interactions_rate,
                   metrics.search_impression_share,
                   metrics.search_budget_lost_impression_share,
                   metrics.search_rank_lost_impression_share
            FROM campaign
            WHERE {period} AND campaign.status != 'REMOVED'
            ORDER BY metrics.cost_micros DESC"""),
        "grupos": (map_adgroup, f"""
            SELECT campaign.name, ad_group.name, ad_group.status,
                   metrics.impressions, metrics.clicks, metrics.cost_micros,
                   metrics.conversions, metrics.cost_per_conversion, metrics.ctr
            FROM ad_group
            WHERE {period} AND ad_group.status != 'REMOVED'
            ORDER BY metrics.cost_micros DESC"""),
        "palavras_chave": (map_keyword, f"""
            SELECT campaign.name, ad_group.name, ad_group_criterion.keyword.text,
                   ad_group_criterion.keyword.match_type, ad_group_criterion.status,
                   ad_group_criterion.quality_info.quality_score,
                   metrics.impressions, metrics.clicks, metrics.cost_micros,
                   metrics.conversions, metrics.cost_per_conversion
            FROM keyword_view
            WHERE {period} AND ad_group_criterion.status != 'REMOVED'
            ORDER BY metrics.cost_micros DESC"""),
        "termos_de_busca": (map_search_term, f"""
            SELECT search_term_view.search_term, campaign.name, ad_group.name,
                   metrics.impressions, metrics.clicks, metrics.cost_micros,
                   metrics.conversions, metrics.cost_per_conversion
            FROM search_term_view
            WHERE {period}
            ORDER BY metrics.cost_micros DESC"""),
        "conversoes": (map_conversion, f"""
            SELECT segments.conversion_action_name, metrics.conversions,
                   metrics.conversions_value, metrics.cost_per_conversion
            FROM campaign
            WHERE {period}
            ORDER BY metrics.conversions DESC"""),
        "dispositivos": (map_device, f"""
            SELECT segments.device, metrics.impressions, metrics.clicks,
                   metrics.cost_micros, metrics.conversions,
                   metrics.cost_per_conversion, metrics.ctr
            FROM campaign
            WHERE {period}"""),
    }


def summarize(dfs):
    """Imprime um resumo objetivo pra dar contexto rápido antes da análise."""
    print("\n" + "=" * 60)
    print("RESUMO")
    print("=" * 60)

    camp = dfs.get("campanhas")
    if camp is not None and not camp.empty:
        custo = camp["custo"].sum()
        conv = camp["conversoes"].sum()
        cpa = round(custo / conv, 2) if conv else 0
        print(f"Investimento total: R$ {custo:,.2f}")
        print(f"Conversões totais:  {conv:,.1f}")
        print(f"CPA médio:          R$ {cpa:,.2f}")

    st = dfs.get("termos_de_busca")
    if st is not None and not st.empty:
        waste = st[(st["conversoes"] == 0) & (st["custo"] > 0)].sort_values("custo", ascending=False)
        if not waste.empty:
            gasto = waste["custo"].sum()
            print(f"\n⚠️  Termos com custo e ZERO conversão: {len(waste)} termos, R$ {gasto:,.2f} sem retorno")
            for _, row in waste.head(10).iterrows():
                print(f"    R$ {row['custo']:>8,.2f}  |  {row['termo_buscado']}")
    print("=" * 60)


def main():
    ap = argparse.ArgumentParser(description="Extrai relatórios de uma conta Google Ads.")
    ap.add_argument("--customer_id", required=True, help="ID da conta (com ou sem traços)")
    ap.add_argument("--last_days", type=int, default=30, help="Janela em dias (default 30)")
    ap.add_argument("--date_start", help="AAAA-MM-DD (sobrescreve --last_days)")
    ap.add_argument("--date_end", help="AAAA-MM-DD (sobrescreve --last_days)")
    ap.add_argument("--direct", action="store_true",
                    help="Conta de acesso DIRETO, fora da MCC (ex.: Dr. Vinicius). "
                         "Omite o login_customer_id.")
    ap.add_argument("--login_customer_id",
                    help="Sobrescreve o ID da MCC do .env (contas dentro de outra MCC).")
    args = ap.parse_args()

    if args.date_start and args.date_end:
        d1, d2 = args.date_start, args.date_end
    else:
        end = date.today() - timedelta(days=1)
        start = end - timedelta(days=args.last_days - 1)
        d1, d2 = start.isoformat(), end.isoformat()

    # Decide o login_customer_id: --direct omite; --login_customer_id sobrescreve;
    # senão usa o .env (MCC padrão).
    if args.direct:
        login_cid = None
    elif args.login_customer_id:
        login_cid = args.login_customer_id
    else:
        login_cid = os.getenv("GOOGLE_ADS_LOGIN_CUSTOMER_ID")

    cid = digits(args.customer_id)
    via = "acesso direto (sem MCC)" if not login_cid else f"via MCC {digits(login_cid)}"
    print(f"Conta: {cid}  |  Período: {d1} a {d2}  |  {via}")

    client = build_client(login_cid)
    reports = build_reports(d1, d2)

    out_dir = ROOT / "output" / "google_ads" / cid / f"{d1}_a_{d2}"
    out_dir.mkdir(parents=True, exist_ok=True)

    dfs = {}
    for name, (mapper, query) in reports.items():
        print(f"→ {name} ...")
        df = run_query(client, cid, query, mapper)
        dfs[name] = df
        if not df.empty:
            path = out_dir / f"{name}.csv"
            df.to_csv(path, index=False, encoding="utf-8-sig")
            print(f"  {len(df)} linhas → {path.relative_to(ROOT)}")
        else:
            print("  (sem dados)")

    summarize(dfs)
    print(f"\nCSVs em: {out_dir.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
