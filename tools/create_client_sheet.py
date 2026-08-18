"""
Cria planilha de acompanhamento individual por cliente.
Colunas: Semana | Agendamentos | Cirurgias Agendadas | Observações
"""

import sys
import io
import json
import time
import datetime
import requests
import urllib.parse
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

TOKEN_FILE = Path(__file__).parent.parent / "token.json"
SHEETS_URL = "https://sheets.googleapis.com/v4/spreadsheets"


def get_weeks_of_year(year=None):
    if year is None:
        year = datetime.date.today().year
    weeks = []
    d = datetime.date(year, 1, 1)
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
    body = {
        "properties": {"title": title},
        "sheets": [{"properties": {"title": "Agendamentos"}}]
    }
    r = requests.post(SHEETS_URL, json=body, headers={"Authorization": f"Bearer {token}"})
    r.raise_for_status()
    return r.json()["spreadsheetId"]


def write_data(spreadsheet_id: str, tab_name: str, rows: list, token: str):
    range_ = urllib.parse.quote(f"{tab_name}!A1", safe="")
    url = f"{SHEETS_URL}/{spreadsheet_id}/values/{range_}?valueInputOption=USER_ENTERED"
    r = requests.put(url, json={"values": rows}, headers={"Authorization": f"Bearer {token}"})
    r.raise_for_status()


def get_sheet_ids(spreadsheet_id: str, token: str) -> dict:
    url = f"{SHEETS_URL}/{spreadsheet_id}?fields=sheets.properties"
    r = requests.get(url, headers={"Authorization": f"Bearer {token}"})
    r.raise_for_status()
    return {s["properties"]["title"]: s["properties"]["sheetId"] for s in r.json()["sheets"]}


def format_sheet(spreadsheet_id: str, sheet_id: int, num_cols: int, token: str):
    col_widths = [160, 160, 180, 220]  # Semana, Agendamentos, Cirurgias, Observações

    requests_body = [
        # Cabeçalho azul escuro, negrito, branco, centralizado
        {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 0,
                    "endRowIndex": 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": num_cols
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
        # Linhas de dados centralizadas
        {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": num_cols - 1  # tudo menos Observações
                },
                "cell": {
                    "userEnteredFormat": {
                        "horizontalAlignment": "CENTER"
                    }
                },
                "fields": "userEnteredFormat(horizontalAlignment)"
            }
        },
        # Congelar cabeçalho
        {
            "updateSheetProperties": {
                "properties": {
                    "sheetId": sheet_id,
                    "gridProperties": {"frozenRowCount": 1}
                },
                "fields": "gridProperties.frozenRowCount"
            }
        }
    ]

    # Largura das colunas
    for i, width in enumerate(col_widths[:num_cols]):
        requests_body.append({
            "updateDimensionProperties": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "COLUMNS",
                    "startIndex": i,
                    "endIndex": i + 1
                },
                "properties": {"pixelSize": width},
                "fields": "pixelSize"
            }
        })

    url = f"{SHEETS_URL}/{spreadsheet_id}:batchUpdate"
    r = requests.post(url, json={"requests": requests_body}, headers={"Authorization": f"Bearer {token}"})
    r.raise_for_status()


def create_client_sheet(client_name: str, has_cirurgias: bool = False):
    print(f"🔑 Autenticando...")
    token = _get_access_token()

    title = f"Agendamentos — {client_name}"
    print(f"📊 Criando planilha: {title}")
    spreadsheet_id = create_spreadsheet(title, token)

    weeks = get_weeks_of_year()

    if has_cirurgias:
        header = ["Semana", "Agendamentos", "Cirurgias Agendadas", "Observações"]
    else:
        header = ["Semana", "Agendamentos", "Observações"]

    rows = [header] + [[w] + [""] * (len(header) - 1) for w in weeks]
    write_data(spreadsheet_id, "Agendamentos", rows, token)

    sheet_ids = get_sheet_ids(spreadsheet_id, token)
    sheet_id = sheet_ids["Agendamentos"]

    print("🎨 Formatando...")
    format_sheet(spreadsheet_id, sheet_id, len(header), token)

    link = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"
    print(f"\n✅ Planilha criada com sucesso!")
    print(f"🔗 Link: {link}")
    return spreadsheet_id


if __name__ == "__main__":
    create_client_sheet("Dr Vinicius", has_cirurgias=True)
