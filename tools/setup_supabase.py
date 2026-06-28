"""
Cria as tabelas no Supabase para o sistema de tracking.
Execute uma vez: python tools/setup_supabase.py
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SECRET_KEY")

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

SQL = """
-- Clientes (um por cliente gerenciado)
CREATE TABLE IF NOT EXISTS clientes (
    id SERIAL PRIMARY KEY,
    nome TEXT NOT NULL,
    kommo_subdomain TEXT NOT NULL,
    kommo_token TEXT NOT NULL,
    meta_pixel_id TEXT NOT NULL,
    meta_token TEXT NOT NULL,
    etapa_conversao TEXT NOT NULL DEFAULT 'Agendamento Confirmado',
    ativo BOOLEAN DEFAULT true,
    criado_em TIMESTAMPTZ DEFAULT NOW()
);

-- Leads rastreados
CREATE TABLE IF NOT EXISTS leads (
    id SERIAL PRIMARY KEY,
    cliente_id INTEGER REFERENCES clientes(id),
    kommo_lead_id TEXT NOT NULL UNIQUE,
    telefone TEXT,
    nome TEXT,
    anuncio_tag TEXT,
    etapa_atual TEXT,
    converteu BOOLEAN DEFAULT false,
    evento_capi_enviado BOOLEAN DEFAULT false,
    criado_em TIMESTAMPTZ DEFAULT NOW(),
    atualizado_em TIMESTAMPTZ DEFAULT NOW()
);

-- Histórico de etapas
CREATE TABLE IF NOT EXISTS eventos_lead (
    id SERIAL PRIMARY KEY,
    lead_id INTEGER REFERENCES leads(id),
    etapa_anterior TEXT,
    etapa_nova TEXT,
    criado_em TIMESTAMPTZ DEFAULT NOW()
);
"""

resp = requests.post(
    f"{SUPABASE_URL}/rest/v1/rpc/exec_sql",
    headers=headers,
    json={"sql": SQL}
)

if resp.status_code in (200, 201):
    print("✅ Tabelas criadas com sucesso!")
else:
    # Tenta via query direta
    print(f"Tentando método alternativo...")
    # Verifica conexão
    r = requests.get(f"{SUPABASE_URL}/rest/v1/", headers=headers)
    print(f"Status conexão: {r.status_code}")
    print("Use o SQL Editor do Supabase para criar as tabelas.")
    print("\nSQL para copiar no Supabase SQL Editor:")
    print(SQL)
