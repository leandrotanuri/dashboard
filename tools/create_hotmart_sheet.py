"""
Cria a planilha de Vendas Hotmart (Elisa) com as colunas certas para o
webhook da Hotmart (PURCHASE_APPROVED e demais eventos) via Make.
Usa a autenticação Google existente (token.json).
"""

import sys
from pathlib import Path

import requests as req

sys.path.insert(0, str(Path(__file__).parent))
from sheets_client import _get_access_token, update_range  # noqa: E402

SHEETS_URL = "https://sheets.googleapis.com/v4/spreadsheets"

TITULO = "Vendas Hotmart - Elisa (MM40+)"
ABA = "Vendas"

# Cabeçalhos — alinhados ao payload do webhook Hotmart 2.0.0
HEADERS = [
    "Data/Hora",       # creation_date (convertido no Make)
    "Evento",          # PURCHASE_APPROVED, CANCELED, etc.
    "Transação",       # data.purchase.transaction
    "Produto",         # data.product.name
    "Comprador",       # data.buyer.name
    "E-mail",          # data.buyer.email
    "Telefone",        # data.buyer.checkout_phone
    "Valor (R$)",      # data.purchase.price.value
    "Pagamento",       # data.purchase.payment.type
    "Parcelas",        # data.purchase.payment.installments_number
    "Oferta",          # data.purchase.offer.code
    "Afiliado",        # data.affiliations[].name
    "Origem (src)",    # data.purchase.origin.src / tracking
    "Recebido em",     # now() do Make
]


def main():
    token = _get_access_token()
    body = {
        "properties": {"title": TITULO},
        "sheets": [{"properties": {"title": ABA}}],
    }
    r = req.post(SHEETS_URL, json=body,
                 headers={"Authorization": f"Bearer {token}"})
    r.raise_for_status()
    data = r.json()
    sid = data["spreadsheetId"]
    url = data["spreadsheetUrl"]

    update_range(sid, f"{ABA}!A1", [HEADERS])

    print("PLANILHA CRIADA")
    print("ID:", sid)
    print("URL:", url)


if __name__ == "__main__":
    main()
