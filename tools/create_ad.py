"""
Ferramenta: create_ad.py
Cria campanha + conjunto de anúncios + criativo + anúncio no Meta Ads via Marketing API.

Todos os objetos são sempre criados com status=PAUSED, sem exceção.
Sem a flag --confirm, o script roda em modo simulação (dry-run) e não faz
nenhuma chamada de escrita à API — apenas imprime o resumo do que seria criado.
"""

import os
import json
import argparse
from pathlib import Path
from dotenv import load_dotenv
import requests

load_dotenv()

ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN")
AD_ACCOUNT_ID = os.getenv("META_AD_ACCOUNT_ID")
API_VERSION = "v19.0"
BASE_URL = f"https://graph.facebook.com/{API_VERSION}"


def api_post(path: str, payload: dict) -> dict:
    url = f"{BASE_URL}/{path}"
    payload = {**payload, "access_token": ACCESS_TOKEN}
    response = requests.post(url, data=payload)
    if response.status_code >= 400:
        print(f"Erro na chamada POST {path}:")
        print(response.text)
        response.raise_for_status()
    return response.json()


def upload_image(account_id: str, image_path: str) -> str:
    url = f"{BASE_URL}/{account_id}/adimages"
    with open(image_path, "rb") as f:
        files = {Path(image_path).name: f}
        response = requests.post(url, data={"access_token": ACCESS_TOKEN}, files=files)
    response.raise_for_status()
    images = response.json().get("images", {})
    first = next(iter(images.values()))
    return first["hash"]


def create_campaign(account_id: str, cfg: dict) -> str:
    payload = {
        "name": cfg["name"],
        "objective": cfg["objective"],
        "status": "PAUSED",
        "special_ad_categories": json.dumps(cfg.get("special_ad_categories", [])),
    }
    result = api_post(f"{account_id}/campaigns", payload)
    return result["id"]


def create_adset(account_id: str, campaign_id: str, cfg: dict) -> str:
    payload = {
        "name": cfg["name"],
        "campaign_id": campaign_id,
        "status": "PAUSED",
        "billing_event": cfg["billing_event"],
        "optimization_goal": cfg["optimization_goal"],
        "targeting": json.dumps(cfg["targeting"]),
    }
    if "daily_budget" in cfg:
        payload["daily_budget"] = int(cfg["daily_budget"])
    if "lifetime_budget" in cfg:
        payload["lifetime_budget"] = int(cfg["lifetime_budget"])
        if "end_time" in cfg:
            payload["end_time"] = cfg["end_time"]
    if "bid_amount" in cfg:
        payload["bid_amount"] = int(cfg["bid_amount"])
    if "start_time" in cfg:
        payload["start_time"] = cfg["start_time"]
    result = api_post(f"{account_id}/adsets", payload)
    return result["id"]


def create_creative(account_id: str, cfg: dict) -> str:
    link_data = {
        "message": cfg["message"],
        "link": cfg["link"],
    }
    if cfg.get("description"):
        link_data["description"] = cfg["description"]
    if cfg.get("call_to_action_type"):
        link_data["call_to_action"] = {
            "type": cfg["call_to_action_type"],
            "value": {"link": cfg["link"]},
        }
    if cfg.get("image_path"):
        link_data["image_hash"] = upload_image(account_id, cfg["image_path"])
    elif cfg.get("picture"):
        link_data["picture"] = cfg["picture"]

    payload = {
        "name": cfg["name"],
        "object_story_spec": json.dumps({
            "page_id": cfg["page_id"],
            "link_data": link_data,
        }),
    }
    result = api_post(f"{account_id}/adcreatives", payload)
    return result["id"]


def create_ad(account_id: str, adset_id: str, creative_id: str, cfg: dict) -> str:
    payload = {
        "name": cfg["name"],
        "adset_id": adset_id,
        "creative": json.dumps({"creative_id": creative_id}),
        "status": "PAUSED",
    }
    result = api_post(f"{account_id}/ads", payload)
    return result["id"]


def print_summary(cfg: dict, account_id: str):
    campaign = cfg["campaign"]
    adset = cfg["adset"]
    creative = cfg["creative"]
    ad = cfg["ad"]

    print("=" * 60)
    print("RESUMO DO ANÚNCIO A SER CRIADO")
    print("=" * 60)
    print(f"Conta: {account_id}")
    print(f"\nCampanha: {campaign['name']}")
    print(f"  Objetivo: {campaign['objective']}")
    print(f"  Categoria especial: {campaign.get('special_ad_categories', [])}")
    print(f"\nConjunto de anúncios: {adset['name']}")
    if "daily_budget" in adset:
        print(f"  Orçamento diário: R$ {int(adset['daily_budget']) / 100:.2f}")
    if "lifetime_budget" in adset:
        print(f"  Orçamento total: R$ {int(adset['lifetime_budget']) / 100:.2f}")
    print(f"  Evento de cobrança: {adset['billing_event']}")
    print(f"  Meta de otimização: {adset['optimization_goal']}")
    print(f"  Segmentação: {json.dumps(adset['targeting'], ensure_ascii=False)}")
    print(f"\nCriativo: {creative['name']}")
    print(f"  Página: {creative['page_id']}")
    print(f"  Texto: {creative['message'][:100]}")
    print(f"  Link: {creative['link']}")
    print(f"\nAnúncio: {ad['name']}")
    print("\nStatus de todos os objetos: PAUSED (ativação manual necessária no Ads Manager)")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Cria campanha/conjunto/criativo/anúncio no Meta Ads (sempre PAUSED)"
    )
    parser.add_argument("--config", required=True, help="Caminho para o JSON de configuração")
    parser.add_argument("--account_id", default=None, help="Override do AD_ACCOUNT_ID (ex: act_123)")
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Executa de fato as chamadas de criação. Sem essa flag, roda em modo simulação (dry-run)",
    )
    args = parser.parse_args()

    account_id = args.account_id or AD_ACCOUNT_ID
    if not ACCESS_TOKEN or not account_id:
        raise EnvironmentError("META_ACCESS_TOKEN e META_AD_ACCOUNT_ID precisam estar no .env")

    with open(args.config, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    print_summary(cfg, account_id)

    if not args.confirm:
        print("\nModo simulação (dry-run). Nenhuma chamada de criação foi feita.")
        print("Revise os dados acima e rode novamente com --confirm para criar de fato (sempre em PAUSED).")
        return

    print("\nCriando objetos no Meta Ads (todos em PAUSED)...")
    campaign_id = create_campaign(account_id, cfg["campaign"])
    print(f"Campanha criada: {campaign_id}")

    adset_id = create_adset(account_id, campaign_id, cfg["adset"])
    print(f"Conjunto de anúncios criado: {adset_id}")

    creative_id = create_creative(account_id, cfg["creative"])
    print(f"Criativo criado: {creative_id}")

    ad_id = create_ad(account_id, adset_id, creative_id, cfg["ad"])
    print(f"Anúncio criado: {ad_id}")

    print("\nTudo criado com status PAUSED. Revise no Ads Manager e ative manualmente quando estiver pronto.")

    result_path = Path("output") / f"ad_created_{campaign_id}.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(
            {"campaign_id": campaign_id, "adset_id": adset_id, "creative_id": creative_id, "ad_id": ad_id},
            f,
            indent=2,
        )
    print(f"IDs salvos em {result_path}")


if __name__ == "__main__":
    main()
