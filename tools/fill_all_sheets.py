"""
Preenche as planilhas de todos os clientes com dados do Meta Ads.
Atualiza apenas D,E | G,H | J,K | M,N — nunca toca nas fórmulas.
"""

import os
import ast
import sys
import io
from collections import defaultdict
from datetime import datetime, date
from dotenv import load_dotenv
import requests
import urllib.parse
sys.path.insert(0, os.path.dirname(__file__))
from sheets_client import batch_update

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
load_dotenv()


def _refresh_meta_token():
    """
    Se o token do Meta estiver próximo de vencer (ou já venceu),
    troca por um novo token de 60 dias e salva no .env automaticamente.
    """
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    env_path = os.path.normpath(env_path)

    token     = os.getenv("META_ACCESS_TOKEN")
    app_id    = os.getenv("META_APP_ID")
    app_secret= os.getenv("META_APP_SECRET")

    if not all([token, app_id, app_secret]):
        return token  # não tem credenciais para renovar

    # Verifica validade do token
    r = requests.get(
        f"https://graph.facebook.com/debug_token",
        params={"input_token": token, "access_token": f"{app_id}|{app_secret}"},
    )
    if r.status_code != 200:
        print("  Aviso: não foi possível verificar token Meta.")
        return token

    info       = r.json().get("data", {})
    expires_at = info.get("expires_at", 0)
    is_valid   = info.get("is_valid", False)

    # Renova se inválido ou expira em menos de 7 dias
    import time
    if not is_valid or (expires_at and expires_at - time.time() < 7 * 86400):
        print("  Token Meta próximo do vencimento — renovando automaticamente...")
        r2 = requests.get(
            "https://graph.facebook.com/v19.0/oauth/access_token",
            params={
                "grant_type":        "fb_exchange_token",
                "client_id":         app_id,
                "client_secret":     app_secret,
                "fb_exchange_token": token,
            },
        )
        if r2.status_code == 200:
            new_token = r2.json()["access_token"]
            # Salva no .env
            env_text = open(env_path, encoding="utf-8").read()
            env_text = env_text.replace(
                f"META_ACCESS_TOKEN={token}",
                f"META_ACCESS_TOKEN={new_token}",
            )
            open(env_path, "w", encoding="utf-8").write(env_text)
            os.environ["META_ACCESS_TOKEN"] = new_token
            print("  Token Meta renovado por mais 60 dias. ✓")
            return new_token
        else:
            print(f"  Aviso: falha ao renovar token Meta: {r2.text}")

    return os.getenv("META_ACCESS_TOKEN")


CLIENTS = [
    {"name": "Clínica PRC",         "account_id": "act_546529263459917",   "spreadsheet_id": "1BZBBwaAN1wBy6bzDxeEN51CkMJ82He-ckhhOzYifrpY"},
    {"name": "Qpharma",             "account_id": "act_2255286214998670",   "spreadsheet_id": "1smTMj2S-GUxYA_CG4Rr3sKaUERSu96_ClFtNhEI_Ao4"},
    {"name": "Arquitetando Paladar","account_id": "act_2315650968737562",   "spreadsheet_id": "17bXplk_19RHR-wdBLwxJJhCoaY74pjHzQZSGYNLOf9Q"},
    {"name": "Dr Vinicius",         "account_id": "act_10205578707965893",  "spreadsheet_id": "1hajaZpK-2cGY4TEpVGTfM7DljZk0M9fiLO6qylC29Gw"},
    {"name": "Elisa Lobo",          "account_id": "act_995746376256993",    "spreadsheet_id": "1S6FUTqK7kDG9ZOgmuakLdxRCSrMxRbegKIEdwCJjS68"},
    {"name": "Dra Mariana Torres", "account_id": "act_888239859802098",    "spreadsheet_id": None},  # preencher quando planilha for criada
]

ACCESS_TOKEN = None  # definido em main() após renovação automática
API_VERSION  = "v19.0"
BASE_URL     = f"https://graph.facebook.com/{API_VERSION}"

MONTH_TAB = {
    1: "📈 Jan", 2: "📈 Fev", 3: "📈 Mar", 4: "📈 Abr",
    5: "📈 Mai", 6: "📈 Jun", 7: "📈 Jul", 8: "📈 Ago",
    9: "📈 Set", 10: "📈 Out", 11: "📈 Nov", 12: "📈 Dez",
}

CAMPAIGN_MAP = {
    "whatsapp":          "whatsapp",
    "wpp":               "whatsapp",
    "mensagem":          "whatsapp",
    "mensagens":         "whatsapp",
    "lead ads":          "lead_ads",
    "lead_ads":          "lead_ads",
    "formulário":        "lead_ads",
    "formulario":        "lead_ads",
    "e2-cap":            "whatsapp",
    "e1-dist":           "seguidores",
    "seguidor":          "seguidores",
    "tráfego":           "seguidores",
    "trafego":           "seguidores",
    "trfg":              "seguidores",
    "perfil":            "seguidores",
    "engj":              "seguidores",
    "engajamento":       "seguidores",
    "alcance":           "seguidores",
    "landing":           "landing_page",
    "padrão":            "whatsapp",
    "padrao":            "whatsapp",
    "[campanha de msg]": "whatsapp",
    "fevereiro":         "whatsapp",
    "visitas ao perfil": "seguidores",
}


def fetch_insights(account_id, date_start, date_end):
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
    for keyword, canal in CAMPAIGN_MAP.items():
        if keyword in name_lower:
            return canal
    if get_action_value(actions, "onsite_conversion.messaging_conversation_started_7d") > 0:
        return "whatsapp"
    if get_action_value(actions, "onsite_conversion.lead_grouped") > 0:
        return "lead_ads"
    return "landing_page"


def aggregate_by_date(rows):
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


def date_to_row(date_str):
    return 4 + datetime.strptime(date_str, "%Y-%m-%d").day


def fill_sheet(spreadsheet_id, sheet_name, by_date):
    value_ranges = []
    for dt in sorted(by_date.keys()):
        row = date_to_row(dt)
        d   = by_date[dt]
        value_ranges += [
            {"range": f"'{sheet_name}'!D{row}:E{row}", "majorDimension": "ROWS", "values": [[round(d["whatsapp"]["spend"], 2),     d["whatsapp"]["leads"]]]},
            {"range": f"'{sheet_name}'!G{row}:H{row}", "majorDimension": "ROWS", "values": [[round(d["lead_ads"]["spend"], 2),      d["lead_ads"]["leads"]]]},
            {"range": f"'{sheet_name}'!J{row}:K{row}", "majorDimension": "ROWS", "values": [[round(d["landing_page"]["spend"], 2),  d["landing_page"]["leads"]]]},
            {"range": f"'{sheet_name}'!M{row}",        "majorDimension": "ROWS", "values": [[round(d["seguidores"]["spend"], 2)]]},
        ]
    batch_update(spreadsheet_id, value_ranges)
    return True


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--date_start", default=None)
    parser.add_argument("--date_end",   default=None)
    args = parser.parse_args()

    global ACCESS_TOKEN
    ACCESS_TOKEN = _refresh_meta_token()

    today      = date.today()
    date_start = args.date_start or today.replace(day=1).strftime("%Y-%m-%d")
    date_end   = args.date_end   or (today - __import__("datetime").timedelta(days=1)).strftime("%Y-%m-%d")
    ref_date   = datetime.strptime(date_start, "%Y-%m-%d").date()
    sheet_name = MONTH_TAB[ref_date.month]

    print(f"=== Preenchendo planilhas — Todos os clientes ===")
    print(f"Período: {date_start} → {date_end}  |  Aba: {sheet_name}\n")

    for client in CLIENTS:
        name           = client["name"]
        account_id     = client["account_id"]
        spreadsheet_id = client["spreadsheet_id"]

        print(f"{'='*50}")
        print(f"  {name}")

        try:
            rows = fetch_insights(account_id, date_start, date_end)
            print(f"  Meta: {len(rows)} registros")
        except Exception as e:
            print(f"  ERRO Meta: {e}")
            continue

        if not rows:
            print("  Sem dados no período.")
            continue

        by_date = aggregate_by_date(rows)

        if not spreadsheet_id:
            print("  Planilha: não configurada — pulando.")
            continue

        ok = fill_sheet(spreadsheet_id, sheet_name, by_date)
        if ok:
            print(f"  Planilha: {len(by_date)} dias atualizados ✓")
        else:
            print(f"  Planilha: ERRO ao atualizar")

    print(f"\n{'='*50}")
    print("Concluído.")


if __name__ == "__main__":
    main()
