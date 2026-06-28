"""
Webhook receiver para eventos do Kommo.
Recebe notificações de mudança de etapa e envia eventos pro Meta CAPI.

Deploy: Railway
Run local: uvicorn tools.tracking_webhook:app --port 8001
"""
import os
import hashlib
import hmac
import time
import requests
from fastapi import FastAPI, Request, HTTPException
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SECRET_KEY")

app = FastAPI()

SB_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}


def get_cliente_by_subdomain(subdomain: str):
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/clientes",
        headers=SB_HEADERS,
        params={"kommo_subdomain": f"eq.{subdomain}", "ativo": "eq.true"}
    )
    data = r.json()
    return data[0] if data else None


def upsert_lead(cliente_id: int, kommo_lead_id: str, nome: str, telefone: str, anuncio_tag: str, etapa: str):
    payload = {
        "cliente_id": cliente_id,
        "kommo_lead_id": kommo_lead_id,
        "nome": nome,
        "telefone": telefone,
        "anuncio_tag": anuncio_tag,
        "etapa_atual": etapa,
        "atualizado_em": "now()"
    }
    r = requests.post(
        f"{SUPABASE_URL}/rest/v1/leads",
        headers={**SB_HEADERS, "Prefer": "resolution=merge-duplicates,return=representation"},
        json=payload
    )
    return r.json()


def registrar_evento(lead_id: int, etapa_anterior: str, etapa_nova: str):
    requests.post(
        f"{SUPABASE_URL}/rest/v1/eventos_lead",
        headers=SB_HEADERS,
        json={"lead_id": lead_id, "etapa_anterior": etapa_anterior, "etapa_nova": etapa_nova}
    )


def enviar_capi_schedule(pixel_id: str, token: str, telefone: str, nome: str):
    telefone_limpo = "".join(filter(str.isdigit, telefone or ""))
    if not telefone_limpo:
        return False

    phone_hash = hashlib.sha256(telefone_limpo.encode()).hexdigest()

    nome_parts = (nome or "").strip().split(" ", 1)
    fn_hash = hashlib.sha256(nome_parts[0].lower().encode()).hexdigest() if nome_parts else None
    ln_hash = hashlib.sha256(nome_parts[1].lower().encode()).hexdigest() if len(nome_parts) > 1 else None

    user_data = {"ph": [phone_hash]}
    if fn_hash:
        user_data["fn"] = [fn_hash]
    if ln_hash:
        user_data["ln"] = [ln_hash]

    payload = {
        "data": [{
            "event_name": "Schedule",
            "event_time": int(time.time()),
            "action_source": "other",
            "user_data": user_data
        }]
    }

    r = requests.post(
        f"https://graph.facebook.com/v19.0/{pixel_id}/events",
        params={"access_token": token},
        json=payload
    )
    return r.status_code == 200


def marcar_capi_enviado(lead_id: int):
    requests.patch(
        f"{SUPABASE_URL}/rest/v1/leads",
        headers=SB_HEADERS,
        params={"id": f"eq.{lead_id}"},
        json={"evento_capi_enviado": True, "converteu": True}
    )


def extrair_tag_anuncio(primeira_msg: str) -> str:
    """Extrai tag do anúncio da primeira mensagem. Ex: [C1], #ADV-A, etc."""
    import re
    if not primeira_msg:
        return None
    match = re.search(r'\[([A-Z0-9\-_]+)\]|#([A-Z0-9\-_]+)', primeira_msg, re.IGNORECASE)
    if match:
        return match.group(1) or match.group(2)
    return None


@app.get("/")
def health():
    return {"status": "ok", "service": "tracking-agency"}


@app.post("/webhook/kommo")
async def kommo_webhook(request: Request):
    """Recebe eventos do Kommo via webhook."""
    try:
        body = await request.json()
    except Exception:
        body = {}

    # Kommo envia dados como form ou JSON dependendo da versão
    if not body:
        form = await request.form()
        body = dict(form)

    # Identifica o subdomínio pelo header ou query param
    subdomain = request.query_params.get("account") or request.headers.get("X-Kommo-Domain", "")

    if not subdomain:
        # Tenta extrair do body
        subdomain = body.get("account_subdomain", "")

    cliente = get_cliente_by_subdomain(subdomain) if subdomain else None

    # Processa mudança de etapa (leads)
    leads_updated = body.get("leads", {}).get("status", []) or []
    if isinstance(leads_updated, dict):
        leads_updated = [leads_updated]

    for lead_data in leads_updated:
        kommo_lead_id = str(lead_data.get("id", ""))
        etapa_nova = lead_data.get("pipeline", {}).get("status", {}).get("name", "")
        nome = lead_data.get("name", "")

        # Busca contato para pegar telefone
        telefone = ""
        contacts = lead_data.get("contacts", {}).get("links", [])
        if contacts:
            telefone = contacts[0].get("phone", "")

        # Busca lead existente no Supabase
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/leads",
            headers=SB_HEADERS,
            params={"kommo_lead_id": f"eq.{kommo_lead_id}"}
        )
        lead_existente = r.json()[0] if r.json() else None
        etapa_anterior = lead_existente.get("etapa_atual") if lead_existente else None

        if cliente:
            lead_result = upsert_lead(
                cliente_id=cliente["id"],
                kommo_lead_id=kommo_lead_id,
                nome=nome,
                telefone=telefone,
                anuncio_tag=lead_existente.get("anuncio_tag") if lead_existente else None,
                etapa=etapa_nova
            )

            lead_id = lead_result[0]["id"] if lead_result else (lead_existente.get("id") if lead_existente else None)

            if lead_id and etapa_anterior != etapa_nova:
                registrar_evento(lead_id, etapa_anterior, etapa_nova)

            # Verifica se chegou na etapa de conversão
            if (etapa_nova == cliente["etapa_conversao"]
                    and not (lead_existente or {}).get("evento_capi_enviado")):
                enviado = enviar_capi_schedule(
                    pixel_id=cliente["meta_pixel_id"],
                    token=cliente["meta_token"],
                    telefone=telefone,
                    nome=nome
                )
                if enviado and lead_id:
                    marcar_capi_enviado(lead_id)

    # Processa novo lead (primeira mensagem = tag do anúncio)
    leads_novos = body.get("leads", {}).get("add", [])
    if isinstance(leads_novos, dict):
        leads_novos = [leads_novos]

    for lead_data in leads_novos:
        kommo_lead_id = str(lead_data.get("id", ""))
        nome = lead_data.get("name", "")
        primeira_msg = lead_data.get("first_message", "") or lead_data.get("message", "")
        anuncio_tag = extrair_tag_anuncio(primeira_msg)
        etapa = lead_data.get("pipeline", {}).get("status", {}).get("name", "Primeiro Atendimento")

        telefone = ""
        contacts = lead_data.get("contacts", {}).get("links", [])
        if contacts:
            telefone = contacts[0].get("phone", "")

        if cliente:
            upsert_lead(
                cliente_id=cliente["id"],
                kommo_lead_id=kommo_lead_id,
                nome=nome,
                telefone=telefone,
                anuncio_tag=anuncio_tag,
                etapa=etapa
            )

    return {"ok": True}
