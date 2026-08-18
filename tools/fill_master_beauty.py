"""
Preenche a planilha do Instituto Master Beauty com dados do Meta Ads.
Separação de campanhas:
  - [PCTE MODELO] no nome  → whatsapp_pcte  (colunas L, M, N)
  - FORMULÁRIO              → lead_ads       (colunas G, H, I)
  - MSG sem PCTE MODELO     → whatsapp       (colunas D, E, F)
Nunca toca nas fórmulas (CPL calculado automaticamente).
"""

import os, ast, sys, io
from collections import defaultdict
from datetime import datetime, date, timedelta
from dotenv import load_dotenv
import requests
sys.path.insert(0, os.path.dirname(__file__))
from sheets_client import batch_update

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
load_dotenv()

ACCOUNT_ID     = "act_400205609739120"
SPREADSHEET_ID = "1frBnGLtYljtV1xQ-qufog3gHxplAYPTTWO-oIT5Kv1I"

ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN")
API_VERSION  = "v19.0"
BASE_URL     = f"https://graph.facebook.com/{API_VERSION}"

MONTH_TAB = {
    1: "📈 Jan", 2: "📈 Fev", 3: "📈 Mar", 4: "📈 Abr",
    5: "📈 Mai", 6: "📈 Jun", 7: "📈 Jul", 8: "📈 Ago",
    9: "📈 Set", 10: "📈 Out", 11: "📈 Nov", 12: "📈 Dez",
}


def fetch_insights(date_start, date_end, time_increment=1):
    url    = f"{BASE_URL}/{ACCOUNT_ID}/insights"
    params = {
        "access_token":  ACCESS_TOKEN,
        "level":         "campaign",
        "fields":        "campaign_name,spend,actions",
        "time_range":    f'{{"since":"{date_start}","until":"{date_end}"}}',
        "limit":         500,
    }
    if time_increment:
        params["time_increment"] = time_increment
    results = []
    while url:
        r = requests.get(url, params=params)
        r.raise_for_status()
        data = r.json()
        results.extend(data.get("data", []))
        url    = data.get("paging", {}).get("next")
        params = {}
    return results


def fetch_lead_ads_totals(date_start, date_end):
    """
    Busca total de leads de Lead Ads SEM time_increment (deduplicado,
    igual ao Gerenciador de Anúncios) retorna dict {campaign_name: leads}
    """
    rows = fetch_insights(date_start, date_end, time_increment=None)
    totals = {}
    for row in rows:
        name = row.get("campaign_name", "")
        if classify_campaign(name, []) != "lead_ads":
            continue
        leads = (get_action_value(row.get("actions", []), "offsite_complete_registration_add_meta_leads")
                 or get_action_value(row.get("actions", []), "lead")
                 or get_action_value(row.get("actions", []), "onsite_conversion.lead_grouped"))
        totals[name] = totals.get(name, 0) + leads
    return totals


def get_action_value(actions, action_type):
    if not actions:
        return 0
    if isinstance(actions, str):
        try:
            actions = ast.literal_eval(actions)
        except Exception:
            return 0
    for a in actions:
        if a.get("action_type") == action_type:
            return int(float(a.get("value", 0)))
    return 0


def classify_campaign(name, actions):
    name_lower = name.lower()
    if "pcte modelo" in name_lower:
        return "whatsapp_pcte"
    if "formulário" in name_lower or "formulario" in name_lower or "formul" in name_lower:
        return "lead_ads"
    if "msg" in name_lower or "mensagem" in name_lower or "whatsapp" in name_lower:
        return "whatsapp"
    # fallback por action type
    if get_action_value(actions, "onsite_conversion.messaging_conversation_started_7d") > 0:
        return "whatsapp"
    if get_action_value(actions, "onsite_conversion.lead_grouped") > 0:
        return "lead_ads"
    return "whatsapp"  # default para instituto


def aggregate_by_date(rows, la_totals_dedup):
    """
    la_totals_dedup: dict {campaign_name: total_leads_deduplicado}
    Para Lead Ads, distribui os leads deduplicados proporcionalmente
    ao investimento diário (evita dupla contagem do time_increment).
    """
    # Pre-calcular investimento total por campanha de Lead Ads
    la_spend_total = defaultdict(float)
    for row in rows:
        name  = row.get("campaign_name", "")
        spend = float(row.get("spend", 0) or 0)
        if classify_campaign(name, []) == "lead_ads":
            la_spend_total[name] += spend

    result = defaultdict(lambda: {
        "whatsapp":      {"spend": 0.0, "leads": 0},
        "whatsapp_pcte": {"spend": 0.0, "leads": 0},
        "lead_ads":      {"spend": 0.0, "leads": 0},
    })
    # Acumular leads de LA por dia proporcional ao spend
    la_leads_assigned = defaultdict(lambda: defaultdict(int))  # {campaign: {date: leads}}

    for row in rows:
        dt      = row["date_start"]
        name    = row.get("campaign_name", "")
        spend   = float(row.get("spend", 0) or 0)
        actions = row.get("actions", [])
        canal   = classify_campaign(name, actions)

        if canal == "whatsapp" or canal == "whatsapp_pcte":
            leads = get_action_value(actions, "onsite_conversion.messaging_conversation_started_7d")
        elif canal == "lead_ads":
            # Distribuir leads deduplicados proporcionalmente ao spend do dia
            total_dedup  = la_totals_dedup.get(name, 0)
            total_spend  = la_spend_total.get(name, 0)
            if total_spend > 0 and spend > 0:
                leads = round(total_dedup * (spend / total_spend))
            else:
                leads = 0
        else:
            leads = 0

        result[dt][canal]["spend"] += spend
        result[dt][canal]["leads"] += leads
    return result


def date_to_row(date_str):
    return 4 + datetime.strptime(date_str, "%Y-%m-%d").day


def fill_sheet(sheet_name, by_date):
    value_ranges = []
    for dt in sorted(by_date.keys()):
        row = date_to_row(dt)
        d   = by_date[dt]
        value_ranges += [
            # D:E  WhatsApp Alunos (invest, leads) — CPL F calculado
            {"range": f"'{sheet_name}'!D{row}:E{row}", "majorDimension": "ROWS",
             "values": [[round(d["whatsapp"]["spend"], 2), d["whatsapp"]["leads"]]]},
            # G:H  Lead Ads (invest, leads) — CPL I calculado
            {"range": f"'{sheet_name}'!G{row}:H{row}", "majorDimension": "ROWS",
             "values": [[round(d["lead_ads"]["spend"], 2), d["lead_ads"]["leads"]]]},
            # L:M  WhatsApp PCTE Modelo (invest, leads) — CPL N calculado
            {"range": f"'{sheet_name}'!L{row}:M{row}", "majorDimension": "ROWS",
             "values": [[round(d["whatsapp_pcte"]["spend"], 2), d["whatsapp_pcte"]["leads"]]]},
        ]
    batch_update(SPREADSHEET_ID, value_ranges)
    return True


def main():
    today      = date.today()
    date_start = today.replace(day=1).strftime("%Y-%m-%d")
    date_end   = (today - timedelta(days=1)).strftime("%Y-%m-%d")
    sheet_name = MONTH_TAB[today.month]

    print(f"=== Instituto Master Beauty ===")
    print(f"Período: {date_start} → {date_end}  |  Aba: {sheet_name}\n")

    rows = fetch_insights(date_start, date_end)
    print(f"Meta: {len(rows)} registros (diário)")

    if not rows:
        print("Sem dados no período.")
        return

    # Buscar totais deduplicados de Lead Ads (igual ao Gerenciador)
    la_totals = fetch_lead_ads_totals(date_start, date_end)
    print(f"Lead Ads deduplicado: {sum(la_totals.values())} leads")
    for name, v in la_totals.items():
        print(f"  {v:3}  {name}")

    by_date = aggregate_by_date(rows, la_totals)
    ok = fill_sheet(sheet_name, by_date)

    if ok:
        print(f"\nPlanilha: {len(by_date)} dias atualizados ✓")

        # Resumo por canal
        total_wp     = sum(v["whatsapp"]["leads"]      for v in by_date.values())
        total_la     = sum(v["lead_ads"]["leads"]       for v in by_date.values())
        total_pcte   = sum(v["whatsapp_pcte"]["leads"]  for v in by_date.values())
        spend_wp     = sum(v["whatsapp"]["spend"]       for v in by_date.values())
        spend_la     = sum(v["lead_ads"]["spend"]       for v in by_date.values())
        spend_pcte   = sum(v["whatsapp_pcte"]["spend"]  for v in by_date.values())
        print(f"\n  WP Alunos   : {total_wp:3} leads  |  R$ {spend_wp:,.2f}")
        print(f"  Lead Ads    : {total_la:3} leads  |  R$ {spend_la:,.2f}")
        print(f"  WP PCTE Mod.: {total_pcte:3} leads  |  R$ {spend_pcte:,.2f}")


if __name__ == "__main__":
    main()
