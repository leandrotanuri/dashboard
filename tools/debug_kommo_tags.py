"""
Debug: verifica o retorno real da API Kommo para um lead com tag.
Execute: python tools/debug_kommo_tags.py
"""
import os
import sys
import json
import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("KOMMO_LONG_TOKEN")
SUB   = os.getenv("KOMMO_SUBDOMAIN")
BASE  = f"https://{SUB}.amocrm.com/api/v4"
H     = {"Authorization": f"Bearer {TOKEN}"}

# Lead que sabemos ter tag [ADF01] (visível na UI)
LEAD_ID = 6966393

print(f"Buscando lead {LEAD_ID} em {BASE}...")

# Teste 1: with=tags
r1 = requests.get(f"{BASE}/leads/{LEAD_ID}", headers=H, params={"with": "contacts,tags"})
print(f"\n[TESTE 1] with=contacts,tags  status={r1.status_code}")
data1 = r1.json()
tags1 = data1.get("_embedded", {}).get("tags", [])
print(f"  tags encontradas: {tags1}")
print(f"  embedded keys: {list(data1.get('_embedded', {}).keys())}")
print(f"  top-level tag_id: {data1.get('tag', '')}")

# Teste 2: endpoint dedicado de tags
r2 = requests.get(f"{BASE}/leads/{LEAD_ID}/tags", headers=H)
print(f"\n[TESTE 2] /leads/{LEAD_ID}/tags  status={r2.status_code}")
if r2.status_code == 200:
    try:
        data2 = r2.json()
        print(f"  resposta: {json.dumps(data2, ensure_ascii=False)[:500]}")
    except Exception as e:
        print(f"  erro ao parsear: {e}")
        print(f"  body raw: {r2.text[:300]}")

# Teste 3: busca na lista de leads (com filtro por ID)
r3 = requests.get(f"{BASE}/leads", headers=H, params={"id[]": LEAD_ID, "with": "tags"})
print(f"\n[TESTE 3] /leads?id[]={LEAD_ID}&with=tags  status={r3.status_code}")
if r3.status_code == 200:
    leads_list = r3.json().get("_embedded", {}).get("leads", [])
    for l in leads_list:
        t = l.get("_embedded", {}).get("tags", [])
        print(f"  lead_id={l.get('id')} tags={t}")

# Mostra o JSON completo para inspeção
print(f"\n[FULL JSON] lead {LEAD_ID}:")
print(json.dumps(data1, ensure_ascii=False, indent=2)[:2000])
