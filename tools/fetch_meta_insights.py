"""
Ferramenta: fetch_meta_insights.py
Busca insights de campanhas/conjuntos/anúncios via API do Meta Ads.
"""

import os
import csv
import argparse
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import requests

load_dotenv()

ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN")
AD_ACCOUNT_ID = os.getenv("META_AD_ACCOUNT_ID")
API_VERSION = "v19.0"
BASE_URL = f"https://graph.facebook.com/{API_VERSION}"

DEFAULT_FIELDS = "campaign_name,adset_name,ad_name,impressions,clicks,spend,reach,ctr,cpc,cpm"


def fetch_insights(date_start: str, date_end: str, level: str, fields: str) -> list[dict]:
    url = f"{BASE_URL}/{AD_ACCOUNT_ID}/insights"
    params = {
        "access_token": ACCESS_TOKEN,
        "level": level,
        "fields": fields,
        "time_range": f'{{"since":"{date_start}","until":"{date_end}"}}',
        "time_increment": 1,
        "limit": 500,
    }

    results = []
    while url:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        results.extend(data.get("data", []))

        # Paginação
        paging = data.get("paging", {})
        next_url = paging.get("next")
        url = next_url if next_url else None
        params = {}  # Próxima página já tem os params na URL

    return results


def save_to_csv(rows: list[dict], output_path: Path):
    if not rows:
        print("Nenhum dado retornado.")
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Salvo: {output_path} ({len(rows)} linhas)")


def main():
    parser = argparse.ArgumentParser(description="Busca insights do Meta Ads")
    parser.add_argument("--date_start", required=True, help="Data início YYYY-MM-DD")
    parser.add_argument("--date_end", required=True, help="Data fim YYYY-MM-DD")
    parser.add_argument("--level", default="campaign", choices=["campaign", "adset", "ad"])
    parser.add_argument("--fields", default=DEFAULT_FIELDS)
    parser.add_argument("--account_id", default=None, help="Override do AD_ACCOUNT_ID (ex: act_123)")
    parser.add_argument("--output_dir", default="output")
    args = parser.parse_args()

    global AD_ACCOUNT_ID
    account_id = args.account_id or AD_ACCOUNT_ID
    if not ACCESS_TOKEN or not account_id:
        raise EnvironmentError("META_ACCESS_TOKEN e META_AD_ACCOUNT_ID precisam estar no .env")
    AD_ACCOUNT_ID = account_id

    print(f"Conta: {account_id}")
    print(f"Buscando insights: {args.level} | {args.date_start} -> {args.date_end}")
    rows = fetch_insights(args.date_start, args.date_end, args.level, args.fields)

    output_file = Path(args.output_dir) / f"meta_insights_{args.level}_{args.date_start}_{args.date_end}.csv"
    save_to_csv(rows, output_file)


if __name__ == "__main__":
    main()
