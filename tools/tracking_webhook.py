"""
Webhook receiver para eventos do Kommo.
Recebe notificações de mudança de etapa e envia eventos pro Meta CAPI.

Deploy: Render
Run local: uvicorn tools.tracking_webhook:app --port 8001
"""
import os
import hashlib
import hmac
import time
import logging
import requests
from fastapi import FastAPI, Request, HTTPException
from urllib.parse import parse_qs
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("tracking")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SECRET_KEY")

app = FastAPI()

SB_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}


_stage_cache: dict = {}

def get_lead_details(token: str, lead_id: str, subdomain: str = "") -> dict:
    """Busca nome e telefone do lead via API Kommo."""
    base = f"https://{subdomain}.amocrm.com/api/v4" if subdomain else "https://api-g.kommo.com/api/v4"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        r = requests.get(f"{base}/leads/{lead_id}", headers=headers, params={"with": "contacts"})
        log.info(f"KOMMO LEAD API status={r.status_code} body={r.text[:300]}")
        lead = r.json()
        nome = lead.get("name", "")
        telefone = ""
        contacts = lead.get("_embedded", {}).get("contacts", [])
        if contacts:
            contact_id = contacts[0].get("id")
            rc = requests.get(f"{base}/contacts/{contact_id}", headers=headers)
            log.info(f"KOMMO CONTACT API status={rc.status_code} body={rc.text[:300]}")
            contact_data = rc.json()
            nome = contact_data.get("name", "") or nome  # nome real do contato
            cf = contact_data.get("custom_fields_values", []) or []
            for field in cf:
                if field.get("field_code") in ("PHONE", "phone") or field.get("field_type") == "multitext":
                    vals = field.get("values", [])
                    if vals:
                        telefone = vals[0].get("value", "")
                        break
        return {"nome": nome, "telefone": telefone}
    except Exception as e:
        log.warning(f"Erro ao buscar lead {lead_id} no Kommo: {e}")
        return {"nome": "", "telefone": ""}


def get_first_message(token: str, lead_id: str, subdomain: str = "") -> str:
    """Busca a primeira mensagem do lead via API Kommo para extrair tag do anúncio."""
    import time
    base = f"https://{subdomain}.amocrm.com/api/v4" if subdomain else "https://api-g.kommo.com/api/v4"
    headers = {"Authorization": f"Bearer {token}"}

    # Aguarda 3s para o Kommo indexar a mensagem antes de buscar
    time.sleep(3)

    try:
        # Tenta 1: eventos do lead
        r = requests.get(
            f"{base}/events",
            headers=headers,
            params={"filter[entity_type]": "lead", "filter[entity_id][]": lead_id, "limit": 20}
        )
        log.info(f"KOMMO EVENTS status={r.status_code} body={r.text[:600]}")
        events = r.json().get("_embedded", {}).get("events", [])
        for event in events:
            etype = event.get("type", "")
            log.info(f"EVENT TYPE={etype}")
            value_after = event.get("value_after", [])
            if isinstance(value_after, list):
                for v in value_after:
                    msg = v.get("message", {}).get("text", "") or v.get("text", "")
                    if msg:
                        log.info(f"MSG ENCONTRADA via events: {msg[:100]}")
                        return msg

        # Tenta 2: notas do lead
        r2 = requests.get(
            f"{base}/leads/{lead_id}/notes",
            headers=headers,
            params={"limit": 10}
        )
        log.info(f"KOMMO NOTES status={r2.status_code} body={r2.text[:400]}")
        notes = r2.json().get("_embedded", {}).get("notes", [])
        for note in notes:
            text = note.get("params", {}).get("text", "") or note.get("text", "")
            if text:
                log.info(f"MSG ENCONTRADA via notes: {text[:100]}")
                return text

        return ""
    except Exception as e:
        log.warning(f"Erro ao buscar mensagens lead {lead_id}: {e}")
        return ""


def get_stage_name(subdomain: str, token: str, status_id: str) -> str:
    """Busca o nome da etapa no Kommo pelo status_id (com cache)."""
    cache_key = f"{subdomain}:{status_id}"
    if cache_key in _stage_cache:
        return _stage_cache[cache_key]
    try:
        base = f"https://{subdomain}.amocrm.com/api/v4" if subdomain else "https://api-g.kommo.com/api/v4"
        r = requests.get(
            f"{base}/leads/pipelines",
            headers={"Authorization": f"Bearer {token}"},
            params={"with": "statuses"}
        )
        log.info(f"KOMMO PIPELINE API status={r.status_code} body={r.text[:200]}")
        pipelines = r.json().get("_embedded", {}).get("pipelines", [])
        for pipeline in pipelines:
            for status in pipeline.get("_embedded", {}).get("statuses", []):
                key = f"{subdomain}:{status['id']}"
                _stage_cache[key] = status["name"]
        return _stage_cache.get(cache_key, status_id)
    except Exception as e:
        log.warning(f"Erro ao buscar etapas Kommo: {e}")
        return status_id


def get_cliente_by_subdomain(subdomain: str):
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/clientes",
        headers=SB_HEADERS,
        params={"kommo_subdomain": f"eq.{subdomain}", "ativo": "eq.true"}
    )
    data = r.json()
    return data[0] if data else None


def upsert_lead(cliente_id: int, kommo_lead_id: str, nome: str, telefone: str, anuncio_tag: str, etapa: str, primeira_mensagem: str = None):
    payload = {
        "cliente_id": cliente_id,
        "kommo_lead_id": kommo_lead_id,
        "nome": nome,
        "telefone": telefone,
        "anuncio_tag": anuncio_tag,
        "etapa_atual": etapa,
        "atualizado_em": "now()"
    }
    if primeira_mensagem:
        payload["primeira_mensagem"] = primeira_mensagem
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


def parse_kommo_body(raw: bytes) -> dict:
    """
    Kommo envia PHP-style nested form params:
      leads[add][0][id]=123&leads[add][0][name]=Fulano
    Este parser converte para dict aninhado Python.
    """
    flat = parse_qs(raw.decode("utf-8", errors="replace"))
    result = {}
    import re
    for key, values in flat.items():
        value = values[0] if len(values) == 1 else values
        # Extrai partes: leads, add, 0, id
        parts = re.findall(r'([^\[\]]+)', key)
        node = result
        for part in parts[:-1]:
            if part not in node:
                node[part] = {}
            node = node[part]
        node[parts[-1]] = value
    return result


def get_list(obj, *keys):
    """Navega dict aninhado e garante lista."""
    node = obj
    for k in keys:
        if not isinstance(node, dict):
            return []
        node = node.get(k, {})
    if not node:
        return []
    if isinstance(node, dict):
        return list(node.values())
    return node


@app.post("/webhook/kommo")
async def kommo_webhook(request: Request):
    """Recebe eventos do Kommo via webhook."""
    raw = await request.body()
    content_type = request.headers.get("content-type", "")
    log.info(f"KOMMO IN | ct={content_type} | raw={raw[:300]}")

    body = parse_kommo_body(raw)
    log.info(f"KOMMO PARSED | {str(body)[:400]}")

    subdomain = (
        request.query_params.get("account")
        or request.headers.get("X-Kommo-Domain", "")
        or body.get("account_subdomain", "")
    )
    log.info(f"SUBDOMAIN={subdomain}")

    cliente = get_cliente_by_subdomain(subdomain) if subdomain else None
    if not cliente:
        log.warning(f"Cliente nao encontrado para subdomain={subdomain}")

    # --- Novo lead criado ---
    for lead_data in get_list(body, "leads", "add"):
        kommo_lead_id = str(lead_data.get("id", ""))
        nome = lead_data.get("name", "")
        # Tenta pegar tag do payload do webhook primeiro
        primeira_msg = lead_data.get("message", "") or lead_data.get("first_message", "")
        anuncio_tag = extrair_tag_anuncio(primeira_msg)
        etapa = lead_data.get("status_name", "") or "Primeiro Atendimento"
        telefone = lead_data.get("phone", "") or ""

        # Busca dados completos via API do Kommo (mensagem + etapa real + telefone)
        msg_api = ""
        if cliente and kommo_lead_id:
            detalhes = get_lead_details(cliente["kommo_token"], kommo_lead_id, subdomain)
            nome = nome or detalhes["nome"]
            telefone = telefone or detalhes["telefone"]

            # Busca etapa real pelo status_id do lead
            status_id = str(lead_data.get("status_id", ""))
            if status_id:
                etapa = get_stage_name(subdomain, cliente["kommo_token"], status_id) or etapa

            msg_api = get_first_message(cliente["kommo_token"], kommo_lead_id, subdomain)
            if not anuncio_tag:
                anuncio_tag = extrair_tag_anuncio(msg_api)
            log.info(f"TAG VIA API: msg={msg_api[:100]} tag={anuncio_tag}")

        log.info(f"NOVO LEAD id={kommo_lead_id} nome={nome} tag={anuncio_tag} etapa={etapa} tel={telefone}")

        if cliente and kommo_lead_id:
            upsert_lead(
                cliente_id=cliente["id"],
                kommo_lead_id=kommo_lead_id,
                nome=nome,
                telefone=telefone,
                anuncio_tag=anuncio_tag,
                etapa=etapa,
                primeira_mensagem=msg_api or primeira_msg or None
            )

    # --- Mudança de etapa ---
    for lead_data in get_list(body, "leads", "status"):
        kommo_lead_id = str(lead_data.get("id", ""))
        status_id = str(lead_data.get("status_id", ""))
        # Kommo envia status_id (número), precisa resolver para nome
        etapa_nova = ""
        if status_id and cliente:
            etapa_nova = get_stage_name(subdomain, cliente["kommo_token"], status_id)
        nome = lead_data.get("name", "")
        telefone = lead_data.get("phone", "") or ""

        log.info(f"STATUS LEAD id={kommo_lead_id} etapa={etapa_nova}")

        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/leads",
            headers=SB_HEADERS,
            params={"kommo_lead_id": f"eq.{kommo_lead_id}"}
        )
        lead_existente = r.json()[0] if r.json() else None
        etapa_anterior = lead_existente.get("etapa_atual") if lead_existente else None

        # Busca dados completos do lead via API Kommo
        if cliente and (not telefone or not nome):
            detalhes = get_lead_details(cliente["kommo_token"], kommo_lead_id, subdomain)
            nome = nome or detalhes["nome"]
            telefone = telefone or detalhes["telefone"]
            log.info(f"KOMMO API lead={kommo_lead_id} nome={nome} tel={telefone}")

        if cliente and kommo_lead_id:
            lead_result = upsert_lead(
                cliente_id=cliente["id"],
                kommo_lead_id=kommo_lead_id,
                nome=nome or (lead_existente.get("nome") if lead_existente else ""),
                telefone=telefone,
                anuncio_tag=lead_existente.get("anuncio_tag") if lead_existente else None,
                etapa=etapa_nova
            )

            lead_id = None
            if isinstance(lead_result, list) and lead_result:
                lead_id = lead_result[0].get("id")
            if not lead_id and lead_existente:
                lead_id = lead_existente.get("id")
            log.info(f"UPSERT lead_id={lead_id} result={str(lead_result)[:100]}")

            if lead_id and etapa_anterior != etapa_nova:
                registrar_evento(lead_id, etapa_anterior, etapa_nova)

            if (etapa_nova.strip().upper() == cliente["etapa_conversao"].strip().upper()
                    and not (lead_existente or {}).get("evento_capi_enviado")):
                log.info(f"CAPI SCHEDULE -> lead={kommo_lead_id} tel={telefone}")
                enviado = enviar_capi_schedule(
                    pixel_id=cliente["meta_pixel_id"],
                    token=cliente["meta_token"],
                    telefone=telefone,
                    nome=nome
                )
                log.info(f"CAPI enviado={enviado}")
                if enviado and lead_id:
                    marcar_capi_enviado(lead_id)

    return {"ok": True}
