"""
Cadastra um cliente no sistema de tracking.
Execute: python tools/setup_cliente_tracking.py
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SECRET_KEY")

SB_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

# --- Configuração do cliente ---
CLIENTES = [
    {
        "nome": "Dr. Vinicius Mello",
        "kommo_subdomain": "crm01scaleag",
        "kommo_token": os.getenv("KOMMO_LONG_TOKEN"),
        "meta_pixel_id": "1601913367590883",
        "meta_token": os.getenv("META_ACCESS_TOKEN"),
        "etapa_conversao": "CONSULTA AGENDADA",
        "ativo": True
    }
]

for cliente in CLIENTES:
    r = requests.post(
        f"{SUPABASE_URL}/rest/v1/clientes",
        headers=SB_HEADERS,
        json=cliente
    )
    if r.status_code in (200, 201):
        print(f"[OK] Cliente '{cliente['nome']}' cadastrado com sucesso!")
    elif r.status_code == 409:
        print(f"[AViso] Cliente '{cliente['nome']}' ja existe.")
    else:
        print(f"[ERRO] Erro ao cadastrar '{cliente['nome']}': {r.status_code} - {r.text}")
