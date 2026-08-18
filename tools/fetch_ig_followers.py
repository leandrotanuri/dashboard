"""
Busca novos seguidores do Instagram via API (instagram_manage_insights).
Usa endpoint /insights?metric=follower_count para dados diarios oficiais.
Fallback: delta de snapshots locais caso a permissao nao esteja disponivel.
"""

import os
import json
import requests
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

IG_ID = os.getenv("META_IG_ID", "17841448465661091")
ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN")
SNAPSHOT_FILE = Path("output/ig_followers_snapshot.json")


def fetch_daily_gains_api(date_start: str, date_end: str, ig_id: str = None) -> dict:
    """
    Busca novos seguidores por dia via API oficial (instagram_manage_insights).
    Retorna {data_str: novos_seguidores} ou None se sem permissao.
    """
    ig = ig_id or IG_ID
    # until precisa ser +1 dia para incluir o ultimo dia
    dt_end = datetime.strptime(date_end, "%Y-%m-%d") + timedelta(days=1)
    r = requests.get(
        f"https://graph.facebook.com/v19.0/{ig}/insights",
        params={
            "access_token": ACCESS_TOKEN,
            "metric": "follower_count",
            "period": "day",
            "since": date_start,
            "until": dt_end.strftime("%Y-%m-%d"),
        },
    )
    data = r.json()
    if "error" in data:
        return None  # sem permissao, usar fallback

    result = {}
    for item in data.get("data", []):
        for v in item.get("values", []):
            date = v["end_time"][:10]
            result[date] = int(v["value"])
    return result


def get_daily_gains(date_start: str, date_end: str, ig_id: str = None) -> dict:
    """
    Retorna {data_str: novos_seguidores} para o intervalo.
    Tenta API primeiro; fallback para delta de snapshots.
    """
    # Tenta via API
    gains = fetch_daily_gains_api(date_start, date_end, ig_id)
    if gains is not None:
        return gains

    # Fallback: delta de snapshots locais
    snapshots = load_snapshots()
    result = {}
    dt = datetime.strptime(date_start, "%Y-%m-%d")
    end = datetime.strptime(date_end, "%Y-%m-%d")
    while dt <= end:
        date_str = dt.strftime("%Y-%m-%d")
        prev_str = (dt - timedelta(days=1)).strftime("%Y-%m-%d")
        if date_str in snapshots and prev_str in snapshots:
            result[date_str] = max(snapshots[date_str] - snapshots[prev_str], 0)
        else:
            result[date_str] = None
        dt += timedelta(days=1)
    return result


def fetch_current_followers(ig_id: str = None) -> int:
    ig = ig_id or IG_ID
    r = requests.get(
        f"https://graph.facebook.com/v19.0/{ig}",
        params={"access_token": ACCESS_TOKEN, "fields": "followers_count"},
    )
    r.raise_for_status()
    return int(r.json()["followers_count"])


def load_snapshots() -> dict:
    if SNAPSHOT_FILE.exists():
        return json.loads(SNAPSHOT_FILE.read_text(encoding="utf-8"))
    return {}


def save_snapshots(snapshots: dict):
    SNAPSHOT_FILE.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_FILE.write_text(json.dumps(snapshots, indent=2, ensure_ascii=False), encoding="utf-8")


def record_today(ig_id: str = None):
    today = datetime.now().strftime("%Y-%m-%d")
    snapshots = load_snapshots()
    if today in snapshots:
        print(f"Snapshot de {today} ja existe: {snapshots[today]} seguidores")
        return snapshots[today]
    total = fetch_current_followers(ig_id)
    snapshots[today] = total
    save_snapshots(snapshots)
    print(f"Snapshot salvo: {today} = {total} seguidores")
    return total


def main():
    parser = argparse.ArgumentParser(description="Seguidores Instagram via API ou delta")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("record", help="Salva snapshot de hoje (fallback)")

    p_gains = subparsers.add_parser("gains", help="Mostra ganho de seguidores por dia")
    p_gains.add_argument("--date_start", required=True)
    p_gains.add_argument("--date_end", required=True)
    p_gains.add_argument("--ig_id", default=None)

    p_backfill = subparsers.add_parser("backfill", help="Insere snapshots manualmente")
    p_backfill.add_argument("--data", required=True)

    subparsers.add_parser("show", help="Exibe snapshots salvos")

    args = parser.parse_args()

    if args.command == "record":
        record_today()

    elif args.command == "gains":
        gains = get_daily_gains(args.date_start, args.date_end, args.ig_id)
        print(f"\nNovos seguidores ({args.date_start} a {args.date_end}):")
        for date, val in sorted(gains.items()):
            print(f"  {date}: {val if val is not None else 'sem dados'}")

    elif args.command == "backfill":
        snapshots = load_snapshots()
        for date, total in json.loads(args.data).items():
            snapshots[date] = total
            print(f"  {date} = {total}")
        save_snapshots(snapshots)

    elif args.command == "show":
        snapshots = load_snapshots()
        for date in sorted(snapshots):
            print(f"  {date}: {snapshots[date]}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
