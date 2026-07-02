"""
Backfill: busca a primeira mensagem de cada lead via API de talks do Kommo
e salva no Supabase. Roda uma vez para leads existentes.

Execute: python tools/sync_primeira_mensagem.py
"""
import os
import re
import time
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
}
BASE = f"https://{KOMMO_SUB}.amocrm.com/api/v4"
KH   = {"Authorization": f"Bearer {KOMMO_TOKEN}"}


def get_primeira_mensagem(lead_id):
    try:
        r = requests.get(f"{BASE}/talks", headers=KH,
                         params={"filter[lead_id]": lead_id, "limit": 3}, timeout=10)
        if r.status_code != 200:
            return None
        talks = r.json().get("_embedded", {}).get("talks", [])
        for talk in talks:
            talk_id = talk.get("id")
            if not talk_id:
                continue
            rm = requests.get(f"{BASE}/talks/{talk_id}/messages", headers=KH,
                              params={"limit": 5, "order[created_at]": "asc"}, timeout=10)
            if rm.status_code != 200:
                continue
            messages = rm.json().get("_embedded", {}).get("messages", [])
            for msg in messages:
                text = msg.get("content", {}).get("text", "") or msg.get("text", "")
                if text:
                    return text
    except Exception as e:
        print(f"  ERRO talks: {e}")
    return None


def extrair_tag(msg):
    if not msg:
        return None
    # Código de anúncio Meta: [ADF01], [ADQ02], etc.
    m = re.search(r'(\[[A-Z0-9\-_]+\])', msg, re.IGNORECASE)
    if m:
        return m.group(1)
    # Google Ads (landing page)
    if re.search(r'vim do site', msg, re.IGNORECASE):
        return "[GOOGLE]"
    # Instagram bio
    if re.search(r'vim do instagram', msg, re.IGNORECASE):
        return "[INSTAGRAM-BIO]"
    return None


# Busca leads sem primeira_mensagem
r = requests.get(f"{SUPABASE_URL}/rest/v1/leads", headers=SB, params={
    "select": "id,kommo_lead_id,nome,anuncio_tag,primeira_mensagem",
    "primeira_mensagem": "is.null",
    "order": "id.asc"
})
leads = r.json()
print(f"{len(leads)} leads sem primeira_mensagem")

atualizados = 0
for i, lead in enumerate(leads):
    lead_id  = lead["kommo_lead_id"]
    sb_id    = lead["id"]
    nome     = lead.get("nome", "")

    msg = get_primeira_mensagem(lead_id)

    if msg:
        tag_na_msg = extrair_tag(msg)
        patch = {"primeira_mensagem": msg}
        # Se ainda não tem tag e a mensagem tem, aproveita para salvar
        if tag_na_msg and not lead.get("anuncio_tag"):
            patch["anuncio_tag"] = tag_na_msg

        requests.patch(f"{SUPABASE_URL}/rest/v1/leads", headers={**SB, "Prefer": "return=minimal"},
                       params={"id": f"eq.{sb_id}"}, json=patch)

        tag_info = f" | tag extraida={tag_na_msg}" if tag_na_msg else ""
        msg_preview = msg[:60].encode("ascii", errors="replace").decode()
        print(f"[OK] {i+1}/{len(leads)} lead={lead_id} | {msg_preview}{tag_info}")
        atualizados += 1
    else:
        print(f"[SEM MSG] {i+1}/{len(leads)} lead={lead_id} | {nome}")

    # Pausa para não sobrecarregar a API
    time.sleep(0.3)

print(f"\n[DONE] {atualizados}/{len(leads)} leads atualizados com primeira mensagem")
