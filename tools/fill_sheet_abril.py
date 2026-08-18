"""
Preenche a aba '📈 Abr' da planilha com dados do Meta Ads.
Atualiza apenas colunas D, E, G, H, J, K, M, N — nunca toca nas formulas (F, I, L, O).

Mapeamento de campanhas para colunas:
  - MSG / WhatsApp  -> META WhatsApp   (D=Invest, E=Leads)
  - Lead Ads        -> META Lead Ads   (G=Invest, H=Leads)
  - Landing Page    -> META Landing Page (J=Invest, K=Leads)
  - Trafego/Perfil  -> META Seguidores (M=Invest, N=Seguid.)
"""

import os
import ast
import csv
import json
import subprocess
import sys
import io
from collections import defaultdict
from datetime import datetime
import argparse
from dotenv import load_dotenv

# Importa rastreador de seguidores do mesmo pacote
sys.path.insert(0, os.path.dirname(__file__))
from fetch_ig_followers import get_daily_gains, record_today

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

load_dotenv()

SPREADSHEET_ID = os.getenv("GOOGLE_SPREADSHEET_ID")
SHEET_NAME = "📈 Abr"
GWS_CMD = r"C:\Users\leand\AppData\Roaming\npm\gws.cmd"
NODE_PATH = r"C:\Program Files\nodejs"

# Mapeamento de campanhas conhecidas -> canal
CAMPAIGN_MAP = {
    "padrão": "whatsapp",
    "padrao": "whatsapp",
    "fevereiro": "whatsapp",
    "[campanha de msg]": "whatsapp",
    "whatsapp": "whatsapp",
    "wpp": "whatsapp",
    "lead ads": "lead_ads",
    "lead_ads": "lead_ads",
    "visitas ao perfil": "seguidores",
    "seguidor": "seguidores",
    "trafego": "seguidores",
    "tráfego": "seguidores",
    "landing": "landing_page",
}


def get_action_value(actions_str, action_type):
    if not actions_str:
        return 0
    try:
        actions = ast.literal_eval(actions_str)
        for a in actions:
            if a.get("action_type") == action_type:
                return int(float(a.get("value", 0)))
    except Exception:
        pass
    return 0


def classify_campaign(name: str, actions_str: str) -> str:
    name_lower = name.lower()
    for keyword, canal in CAMPAIGN_MAP.items():
        if keyword in name_lower:
            return canal
    # Fallback por action: se tem mensagens iniciadas → whatsapp
    if get_action_value(actions_str, "onsite_conversion.messaging_conversation_started_7d") > 0:
        return "whatsapp"
    return "landing_page"


def load_csv(filepath: str) -> list[dict]:
    with open(filepath, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def aggregate_by_date(rows: list[dict]) -> dict:
    result = defaultdict(lambda: {
        "whatsapp":     {"spend": 0.0, "leads": 0},
        "lead_ads":     {"spend": 0.0, "leads": 0},
        "landing_page": {"spend": 0.0, "leads": 0},
        "seguidores":   {"spend": 0.0, "leads": 0},
    })

    for row in rows:
        date = row["date_start"]
        name = row.get("campaign_name", "")
        spend = float(row.get("spend", 0) or 0)
        actions_str = row.get("actions", "")
        canal = classify_campaign(name, actions_str)

        if canal == "whatsapp":
            leads = get_action_value(actions_str, "onsite_conversion.messaging_conversation_started_7d")
        elif canal == "lead_ads":
            leads = (get_action_value(actions_str, "leadgen.other")
                     or get_action_value(actions_str, "lead")
                     or get_action_value(actions_str, "offsite_complete_registration_add_meta_leads")
                     or get_action_value(actions_str, "onsite_conversion.lead_grouped"))
        elif canal == "landing_page":
            leads = get_action_value(actions_str, "offsite_conversion.fb_pixel_lead")
        elif canal == "seguidores":
            # Seguidores: sem metrica direta de novos seguidores na API — deixa 0
            leads = 0
        else:
            leads = 0

        result[date][canal]["spend"] += spend
        result[date][canal]["leads"] += leads

    return result


def date_to_row(date_str: str) -> int:
    """Linha 5 = dia 01, linha 6 = dia 02, etc."""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return 4 + dt.day


def batch_update_day(row: int, day_data: dict, env: dict) -> bool:
    """
    Atualiza D:E, G:H, J:K, M:N em uma unica chamada batchUpdate.
    Nunca toca nas colunas de formula (F, I, L, O).
    """
    wp = day_data["whatsapp"]
    la = day_data["lead_ads"]
    lp = day_data["landing_page"]
    sg = day_data["seguidores"]

    sn = SHEET_NAME

    value_ranges = [
        {"range": f"'{sn}'!D{row}:E{row}", "majorDimension": "ROWS",
         "values": [[round(wp["spend"], 2), wp["leads"]]]},
        {"range": f"'{sn}'!G{row}:H{row}", "majorDimension": "ROWS",
         "values": [[round(la["spend"], 2), la["leads"]]]},
        {"range": f"'{sn}'!J{row}:K{row}", "majorDimension": "ROWS",
         "values": [[round(lp["spend"], 2), lp["leads"]]]},
        {"range": f"'{sn}'!M{row}:N{row}", "majorDimension": "ROWS",
         "values": [[round(sg["spend"], 2), sg["leads"]]]},
    ]

    params = {"spreadsheetId": SPREADSHEET_ID}
    body = {"data": value_ranges, "valueInputOption": "USER_ENTERED"}

    result = subprocess.run(
        [GWS_CMD, "sheets", "spreadsheets", "values", "batchUpdate",
         "--params", json.dumps(params),
         "--json", json.dumps(body)],
        capture_output=True, text=True, env=env, shell=True
    )

    if result.returncode != 0:
        print(f"  ERRO linha {row}: {result.stderr or result.stdout}")
        return False

    return True


def main():
    parser = argparse.ArgumentParser(description="Preenche aba Abr da planilha com dados Meta Ads")
    parser.add_argument("csv_path", help="CSV com insights de campanha")
    parser.add_argument("--spreadsheet_id", default=None, help="Override do GOOGLE_SPREADSHEET_ID")
    args = parser.parse_args()

    if args.spreadsheet_id:
        global SPREADSHEET_ID
        SPREADSHEET_ID = args.spreadsheet_id

    csv_path = args.csv_path
    rows = load_csv(csv_path)
    print(f"Carregados {len(rows)} registros")

    by_date = aggregate_by_date(rows)

    print("\n--- Resumo por data ---")
    print(f"{'Data':<12} {'WP Spend':>10} {'WP Leads':>9} {'LA Spend':>10} {'LA Leads':>9} {'LP Spend':>10} {'LP Leads':>9} {'Seg Spend':>10}")
    print("-" * 82)
    for date in sorted(by_date.keys()):
        d = by_date[date]
        print(f"{date:<12} {d['whatsapp']['spend']:>10.2f} {d['whatsapp']['leads']:>9} "
              f"{d['lead_ads']['spend']:>10.2f} {d['lead_ads']['leads']:>9} "
              f"{d['landing_page']['spend']:>10.2f} {d['landing_page']['leads']:>9} "
              f"{d['seguidores']['spend']:>10.2f}")

    # Salva snapshot de hoje e busca ganhos de seguidores
    print("\n--- Buscando seguidores Instagram ---")
    try:
        record_today()
        dates = sorted(by_date.keys())
        gains = get_daily_gains(dates[0], dates[-1])
        for date, gain in gains.items():
            if gain is not None:
                by_date[date]["seguidores"]["leads"] = gain
                print(f"  {date}: +{gain} seguidores")
            else:
                print(f"  {date}: sem snapshot anterior (N = 0)")
    except Exception as e:
        print(f"  Aviso: nao foi possivel buscar seguidores - {e}")

    env = os.environ.copy()
    env["PATH"] = NODE_PATH + os.pathsep + env.get("PATH", "")

    print("\n--- Atualizando planilha (D,E | G,H | J,K | M,N) ---")
    updated = 0
    for date in sorted(by_date.keys()):
        row_num = date_to_row(date)
        if batch_update_day(row_num, by_date[date], env):
            print(f"  OK {date} -> linha {row_num}")
            updated += 1
        else:
            print(f"  FALHA {date}")

    print(f"\nConcluido: {updated}/{len(by_date)} dias atualizados na aba '{SHEET_NAME}'")


if __name__ == "__main__":
    main()
