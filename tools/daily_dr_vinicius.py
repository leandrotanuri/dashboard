"""
Atualização diária automática — Dr. Vinicius
Busca insights do mês atual e preenche a aba correta da planilha.
Preenche até o dia ANTERIOR ao de execução (dia fechado).
Coluna N (seguidores) é preenchida manualmente — este script não toca nela.
"""

import os
import ast
import sys
import io
from collections import defaultdict
from datetime import datetime, date, timedelta
from dotenv import load_dotenv
import requests
sys.path.insert(0, os.path.dirname(__file__))
from sheets_client import batch_update

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
load_dotenv()

# ─── Config do cliente ────────────────────────────────────────────────────────
ACCOUNT_ID     = "act_10205578707965893"
SPREADSHEET_ID = "1hajaZpK-2cGY4TEpVGTfM7DljZk0M9fiLO6qylC29Gw"
ACCESS_TOKEN   = os.getenv("META_ACCESS_TOKEN")
API_VERSION    = "v19.0"
BASE_URL       = f"https://graph.facebook.com/{API_VERSION}"

MONTH_TAB = {
    1: "📈 Jan", 2: "📈 Fev", 3: "📈 Mar", 4: "📈 Abr",
    5: "📈 Mai", 6: "📈 Jun", 7: "📈 Jul", 8: "📈 Ago",
    9: "📈 Set", 10: "📈 Out", 11: "📈 Nov", 12: "📈 Dez",
}

CAMPAIGN_MAP = {
    "e2-cap":   "whatsapp",
    "e1-dist":  "seguidores",
    "whatsapp": "whatsapp",
    "wpp":      "whatsapp",
    "mensagem": "whatsapp",
    "mensagens":"whatsapp",
    "lead ads": "lead_ads",
    "lead_ads": "lead_ads",
    "seguidor": "seguidores",
    "trafego":  "seguidores",
    "tráfego":  "seguidores",
    "trfg":     "seguidores",
    "landing":  "landing_page",
}


# ─── Meta API ─────────────────────────────────────────────────────────────────
def fetch_insights(date_start: str, date_end: str) -> list:
    url = f"{BASE_URL}/{ACCOUNT_ID}/insights"
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
    if get_action_value(actions, "onsite_conversion.messaging_first_reply") > 0:
        return "whatsapp"
    if get_action_value(actions, "onsite_conversion.lead_grouped") > 0:
        return "lead_ads"
    return "landing_page"


def aggregate_by_date(rows: list) -> dict:
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
            leads = get_action_value(actions, "onsite_conversion.messaging_first_reply")
        elif canal == "lead_ads":
            leads = (get_action_value(actions, "offsite_complete_registration_add_meta_leads")
                     or get_action_value(actions, "lead")
                     or get_action_value(actions, "onsite_conversion.lead_grouped"))
        else:
            leads = 0

        result[dt][canal]["spend"] += spend
        result[dt][canal]["leads"] += leads
    return result


def date_to_row(date_str: str) -> int:
    """Linha 5 = dia 01, linha 6 = dia 02, etc."""
    return 4 + datetime.strptime(date_str, "%Y-%m-%d").day


def fill_sheet(sheet_name: str, by_date: dict) -> bool:
    value_ranges = []
    for dt in sorted(by_date.keys()):
        row = date_to_row(dt)
        d   = by_date[dt]
        value_ranges += [
            {"range": f"'{sheet_name}'!D{row}:E{row}", "majorDimension": "ROWS",
             "values": [[round(d["whatsapp"]["spend"], 2), d["whatsapp"]["leads"]]]},
            {"range": f"'{sheet_name}'!G{row}:H{row}", "majorDimension": "ROWS",
             "values": [[round(d["lead_ads"]["spend"], 2), d["lead_ads"]["leads"]]]},
            {"range": f"'{sheet_name}'!J{row}:K{row}", "majorDimension": "ROWS",
             "values": [[round(d["landing_page"]["spend"], 2), d["landing_page"]["leads"]]]},
            # Coluna M = investimento E1-DIST | Coluna N = seguidores (preenchida manualmente)
            {"range": f"'{sheet_name}'!M{row}", "majorDimension": "ROWS",
             "values": [[round(d["seguidores"]["spend"], 2)]]},
        ]
    batch_update(SPREADSHEET_ID, value_ranges)
    return True


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    today      = date.today()
    yesterday  = today - timedelta(days=1)
    date_start = yesterday.replace(day=1).strftime("%Y-%m-%d")
    date_end   = yesterday.strftime("%Y-%m-%d")
    sheet_name = MONTH_TAB[yesterday.month]

    print(f"=== Atualização diária — Dr. Vinicius ===")
    print(f"Hoje: {today}  |  Preenchendo até: {date_end} (dia fechado)")
    print(f"Aba: {sheet_name}  |  Planilha: {SPREADSHEET_ID}\n")

    if not ACCESS_TOKEN:
        raise EnvironmentError("META_ACCESS_TOKEN não encontrado no .env")

    print("Buscando insights Meta Ads...")
    rows = fetch_insights(date_start, date_end)
    print(f"  {len(rows)} registros retornados")

    if not rows:
        print("Nenhum dado encontrado. Encerrando.")
        return

    by_date = aggregate_by_date(rows)

    print("\n--- Resumo ---")
    for dt in sorted(by_date.keys()):
        d = by_date[dt]
        print(f"  {dt}  WP={d['whatsapp']['spend']:.2f}/{d['whatsapp']['leads']}  "
              f"LA={d['lead_ads']['spend']:.2f}/{d['lead_ads']['leads']}  "
              f"Seg={d['seguidores']['spend']:.2f}")

    print("\nAtualizando planilha...")
    ok = fill_sheet(sheet_name, by_date)
    if ok:
        print(f"\nConcluído: {len(by_date)} dias atualizados em '{sheet_name}'")
    else:
        print("\nERRO ao atualizar a planilha.")


if __name__ == "__main__":
    main()
