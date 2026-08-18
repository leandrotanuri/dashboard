"""
Cria a planilha de Agendamentos Manuais no Google Sheets.
Uma aba por cliente, com colunas: Semana, Agendamentos, Observações.
"""

import sys
import io
import json
import time
import requests
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

TOKEN_FILE = Path(__file__).parent.parent / "token.json"
SHEETS_URL = "https://sheets.googleapis.com/v4/spreadsheets"

CLIENTS = [
    "Clinica PRC",
    "Qpharma",
    "Dr Giovanni",
    "Dr Bruno",
    "Arquitetando Paladar",
    "Dr Vinicius",
]

# Semanas do ano (simplificado — ajuste conforme necessário)
import datetime

def get_weeks_of_year(year=None):
    if year is None:
        year = datetime.date.today().year
    weeks = []
    d = datetime.date(year, 1, 1)
    # Começa na primeira segunda-feira
    while d.weekday() != 0:
        d += datetime.timedelta(days=1)
    while d.year == year:
        end = d + datetime.timedelta(days=6)
        weeks.append(f"{d.strftime('%d/%m')} - {end.strftime('%d/%m/%Y')}")
        d += datetime.timedelta(weeks=1)
    return weeks


def _load_token():
    return json.loads(TOKEN_FILE.read_text())


def _get_access_token():
    token = _load_token()
    if time.time() >= token.get("expires_at", 0) - 300:
        r = requests.post(token["token_uri"], data={
            "client_id":     token["client_id"],
            "client_secret": token["client_secret"],
            "refresh_token": token["refresh_token"],
            "grant_type":    "refresh_token",
        })
        r.raise_for_status()
        new = r.json()
        token["access_token"] = new["access_token"]
        token["expires_at"]   = time.time() + new.get("expires_in", 3600)
        TOKEN_FILE.write_text(json.dumps(token, indent=2))
    return token["access_token"]


def create_spreadsheet(title: str, token: str) -> str:
    """Cria uma nova planilha e retorna o ID."""
    body = {
        "properties": {"title": title},
        "sheets": [{"properties": {"title": CLIENTS[0]}}]  # primeira aba
    }
    r = requests.post(SHEETS_URL, json=body, headers={"Authorization": f"Bearer {token}"})
    r.raise_for_status()
    return r.json()["spreadsheetId"]


def add_sheet(spreadsheet_id: str, tab_name: str, token: str):
    url = f"{SHEETS_URL}/{spreadsheet_id}:batchUpdate"
    body = {"requests": [{"addSheet": {"properties": {"title": tab_name}}}]}
    r = requests.post(url, json=body, headers={"Authorization": f"Bearer {token}"})
    r.raise_for_status()


def write_data(spreadsheet_id: str, tab_name: str, rows: list, token: str):
    import urllib.parse
    range_ = urllib.parse.quote(f"{tab_name}!A1", safe="")
    url = f"{SHEETS_URL}/{spreadsheet_id}/values/{range_}?valueInputOption=USER_ENTERED"
    r = requests.put(url, json={"values": rows}, headers={"Authorization": f"Bearer {token}"})
    r.raise_for_status()


def format_header(spreadsheet_id: str, sheet_id: int, token: str):
    """Deixa o cabeçalho em negrito e com fundo azul escuro."""
    url = f"{SHEETS_URL}/{spreadsheet_id}:batchUpdate"
    body = {"requests": [
        {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 0,
                    "endRowIndex": 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": 3
                },
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": {"red": 0.13, "green": 0.27, "blue": 0.53},
                        "textFormat": {
                            "foregroundColor": {"red": 1, "green": 1, "blue": 1},
                            "bold": True,
                            "fontSize": 11
                        },
                        "horizontalAlignment": "CENTER"
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)"
            }
        },
        {
            "updateDimensionProperties": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "COLUMNS",
                    "startIndex": 0,
                    "endIndex": 3
                },
                "properties": {"pixelSize": 200},
                "fields": "pixelSize"
            }
        }
    ]}
    r = requests.post(url, json=body, headers={"Authorization": f"Bearer {token}"})
    r.raise_for_status()


def get_sheet_ids(spreadsheet_id: str, token: str) -> dict:
    url = f"{SHEETS_URL}/{spreadsheet_id}?fields=sheets.properties"
    r = requests.get(url, headers={"Authorization": f"Bearer {token}"})
    r.raise_for_status()
    return {s["properties"]["title"]: s["properties"]["sheetId"] for s in r.json()["sheets"]}


def main():
    print("🔑 Autenticando...")
    token = _get_access_token()

    print("📊 Criando planilha...")
    spreadsheet_id = create_spreadsheet("Agendamentos — Clientes", token)
    print(f"   Planilha criada: https://docs.google.com/spreadsheets/d/{spreadsheet_id}")

    weeks = get_weeks_of_year()
    header = ["Semana", "Agendamentos", "Observações"]

    # Primeira aba já criada com o spreadsheet
    first_client = CLIENTS[0]
    rows = [header] + [[w, "", ""] for w in weeks]
    write_data(spreadsheet_id, first_client, rows, token)

    # Demais abas
    for client in CLIENTS[1:]:
        print(f"   Adicionando aba: {client}")
        add_sheet(spreadsheet_id, client, token)
        rows = [header] + [[w, "", ""] for w in weeks]
        write_data(spreadsheet_id, client, rows, token)

    # Formatar cabeçalhos
    print("🎨 Formatando cabeçalhos...")
    sheet_ids = get_sheet_ids(spreadsheet_id, token)
    for client in CLIENTS:
        sid = sheet_ids.get(client)
        if sid is not None:
            format_header(spreadsheet_id, sid, token)

    print("\n✅ Planilha criada com sucesso!")
    print(f"🔗 Link: https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit")


if __name__ == "__main__":
    main()
