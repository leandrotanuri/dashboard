"""
Atualização diária automática — Todos os clientes
Busca insights do mês atual via Meta Ads API e salva em CSV por cliente.
"""

import os
import ast
import csv
import sys
import io
import argparse
from collections import defaultdict
from datetime import datetime, date, timedelta
from pathlib import Path
from dotenv import load_dotenv
import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
load_dotenv()

# ─── Clientes ─────────────────────────────────────────────────────────────────
CLIENTS = [
    {"name": "Clinica PRC",         "account_id": "act_546529263459917"},
    {"name": "Qpharma",             "account_id": "act_2255286214998670"},
    {"name": "Arquitetando Paladar","account_id": "act_2315650968737562"},
    {"name": "Dr Vinicius",         "account_id": "act_10205578707965893"},
    {"name": "Elisa Lobo",          "account_id": "act_995746376256993"},
]

# ─── Config ───────────────────────────────────────────────────────────────────
ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN")
API_VERSION  = "v19.0"
BASE_URL     = f"https://graph.facebook.com/{API_VERSION}"
OUTPUT_DIR   = Path(__file__).parent.parent / "output"

CAMPAIGN_MAP = {
    "whatsapp":          "whatsapp",
    "wpp":               "whatsapp",
    "mensagem":          "whatsapp",
    "mensagens":         "whatsapp",
    "lead ads":          "lead_ads",
    "lead_ads":          "lead_ads",
    "formulário":        "lead_ads",
    "formulario":        "lead_ads",
    "seguidor":          "seguidores",
    "tráfego":           "seguidores",
    "trafego":           "seguidores",
    "trfg":              "seguidores",
    "perfil":            "seguidores",
    "landing":           "landing_page",
    "padrão":            "whatsapp",
    "padrao":            "whatsapp",
    "[campanha de msg]": "whatsapp",
    "fevereiro":         "whatsapp",
    "visitas ao perfil": "seguidores",
}


# ─── Meta API ─────────────────────────────────────────────────────────────────
def fetch_insights(account_id: str, date_start: str, date_end: str) -> list[dict]:
    url = f"{BASE_URL}/{account_id}/insights"
    params = {
        "access_token": ACCESS_TOKEN,
        "level": "campaign",
        "fields": "campaign_name,spend,actions",
        "time_range": f'{{"since":"{date_start}","until":"{date_end}"}}',
        "time_increment": 1,
        "limit": 500,
    }
    results = []
    while url:
        r = requests.get(url, params=params)
        r.raise_for_status()
        data = r.json()
        results.extend(data.get("data", []))
        url = data.get("paging", {}).get("next")
        params = {}
    return results


# ─── Helpers ──────────────────────────────────────────────────────────────────
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


def classify_campaign(name: str, actions) -> str:
    name_lower = name.lower()
    for keyword, canal in CAMPAIGN_MAP.items():
        if keyword in name_lower:
            return canal
    if get_action_value(actions, "onsite_conversion.messaging_conversation_started_7d") > 0:
        return "whatsapp"
    if get_action_value(actions, "onsite_conversion.lead_grouped") > 0:
        return "lead_ads"
    return "landing_page"


def aggregate_by_date(rows: list[dict]) -> dict:
    result = defaultdict(lambda: {
        "whatsapp":     {"spend": 0.0, "leads": 0},
        "lead_ads":     {"spend": 0.0, "leads": 0},
        "landing_page": {"spend": 0.0, "leads": 0},
        "seguidores":   {"spend": 0.0, "leads": 0},
    })
    for row in rows:
        dt      = row["date_start"]
        name    = row.get("campaign_name", "")
        spend   = float(row.get("spend", 0) or 0)
        actions = row.get("actions", [])
        canal   = classify_campaign(name, actions)

        if canal == "whatsapp":
            leads = get_action_value(actions, "onsite_conversion.messaging_conversation_started_7d")
        elif canal == "lead_ads":
            leads = (get_action_value(actions, "offsite_complete_registration_add_meta_leads")
                     or get_action_value(actions, "lead")
                     or get_action_value(actions, "onsite_conversion.lead_grouped"))
        else:
            leads = 0

        result[dt][canal]["spend"] += spend
        result[dt][canal]["leads"] += leads
    return result


def save_csv(client_name: str, by_date: dict):
    OUTPUT_DIR.mkdir(exist_ok=True)
    slug = client_name.lower().replace(" ", "_")
    path = OUTPUT_DIR / f"{slug}_abril.csv"

    fieldnames = ["data", "wp_invest", "wp_leads", "la_invest", "la_leads",
                  "lp_invest", "lp_leads", "seg_invest", "seg_leads"]

    # Lê dados existentes para merge
    existing = {}
    if path.exists():
        with open(path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                existing[row["data"]] = row

    # Sobrescreve com novos dados
    for dt, d in by_date.items():
        existing[dt] = {
            "data":       dt,
            "wp_invest":  round(d["whatsapp"]["spend"], 2),
            "wp_leads":   d["whatsapp"]["leads"],
            "la_invest":  round(d["lead_ads"]["spend"], 2),
            "la_leads":   d["lead_ads"]["leads"],
            "lp_invest":  round(d["landing_page"]["spend"], 2),
            "lp_leads":   d["landing_page"]["leads"],
            "seg_invest": round(d["seguidores"]["spend"], 2),
            "seg_leads":  d["seguidores"]["leads"],
        }

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for dt in sorted(existing.keys()):
            writer.writerow(existing[dt])

    return path


def process_client(client: dict, date_start: str, date_end: str):
    name       = client["name"]
    account_id = client["account_id"]

    print(f"\n{'='*55}")
    print(f"  {name}  |  {account_id}")
    print(f"{'='*55}")

    try:
        rows = fetch_insights(account_id, date_start, date_end)
        print(f"  {len(rows)} registros da API")
    except Exception as e:
        print(f"  ERRO ao buscar insights: {e}")
        return

    if not rows:
        print("  Sem dados para este período.")
        return

    by_date = aggregate_by_date(rows)

    print(f"  {'Data':<12} {'WP Invest':>10} {'WP Leads':>9} {'LA Invest':>10} {'LA Leads':>9} {'Seg Invest':>10}")
    for dt in sorted(by_date.keys()):
        d = by_date[dt]
        print(f"  {dt}  {d['whatsapp']['spend']:>10.2f} {d['whatsapp']['leads']:>9} "
              f"{d['lead_ads']['spend']:>10.2f} {d['lead_ads']['leads']:>9} "
              f"{d['seguidores']['spend']:>10.2f}")

    path = save_csv(name, by_date)
    print(f"  Salvo: {path.name}")


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date_start", default=None, help="Data início YYYY-MM-DD (padrão: 1º do mês)")
    parser.add_argument("--date_end",   default=None, help="Data fim YYYY-MM-DD (padrão: hoje)")
    args = parser.parse_args()

    if not ACCESS_TOKEN:
        raise EnvironmentError("META_ACCESS_TOKEN não encontrado no .env")

    today      = date.today()
    date_start = args.date_start or today.replace(day=1).strftime("%Y-%m-%d")
    date_end   = args.date_end   or today.strftime("%Y-%m-%d")

    print(f"=== Atualização — Todos os clientes ===")
    print(f"Período: {date_start} → {date_end}")

    for client in CLIENTS:
        process_client(client, date_start, date_end)

    print(f"\n{'='*55}")
    print(f"Concluído. CSVs salvos em: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
