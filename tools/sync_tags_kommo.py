"""
Sincroniza as tags do Kommo para todos os leads no Supabase.
Roda uma vez para atualizar leads que já existiam antes do sistema de tags.
Execute: python tools/sync_tags_kommo.py
"""
import os
import re
import requests
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SECRET_KEY")
KOMMO_TOKEN  = os.getenv("KOMMO_LONG_TOKEN")
KOMMO_SUB    = os.getenv("KOMMO_SUBDOMAIN")

SB = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

BASE = f"https://{KOMMO_SUB}.amocrm.com/api/v4"
KH   = {"Authorization": f"Bearer {KOMMO_TOKEN}"}

# Busca todos os leads do Supabase
r = requests.get(f"{SUPABASE_URL}/rest/v1/leads", headers=SB,
                 params={"select": "id,kommo_lead_id,anuncio_tag", "order": "id.asc"})
leads = r.json()
print(f"[INFO] {len(leads)} leads encontrados no Supabase")

atualizados = 0
for lead in leads:
    lead_id = lead["kommo_lead_id"]
    sb_id   = lead["id"]

    try:
        rk = requests.get(f"{BASE}/leads/{lead_id}", headers=KH,
                          params={"with": "tags"})
        if rk.status_code != 200:
            print(f"[SKIP] lead {lead_id} status={rk.status_code}")
            continue

        data = rk.json()
        tags = data.get("_embedded", {}).get("tags", [])

        if not tags:
            print(f"[SEM TAG] lead {lead_id}")
            continue

        # Prioriza tag com padrão AD, senão pega a primeira
        tag_name = None
        for t in tags:
            if re.search(r'AD', t.get("name", ""), re.IGNORECASE):
                tag_name = t["name"]
                break
        if not tag_name:
            tag_name = tags[0]["name"]

        # Atualiza no Supabase
        requests.patch(
            f"{SUPABASE_URL}/rest/v1/leads",
            headers=SB,
            params={"id": f"eq.{sb_id}"},
            json={"anuncio_tag": tag_name}
        )
        print(f"[OK] lead {lead_id} -> tag={tag_name}")
        atualizados += 1

    except Exception as e:
        print(f"[ERRO] lead {lead_id}: {e}")

print(f"\n[DONE] {atualizados}/{len(leads)} leads atualizados com tag")
