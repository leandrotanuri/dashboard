"""
Cria planilha de Agendamentos do Dr Vinicius com:
- 12 abas (uma por mês)
- Estrutura diária com colunas de agendamentos e cirurgias
- Fórmulas de valor total e linha de TOTAL
"""

import sys
import io
import json
import time
import datetime
import calendar
import requests
import urllib.parse
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

TOKEN_FILE = Path(__file__).parent.parent / "token.json"
SHEETS_URL = "https://sheets.googleapis.com/v4/spreadsheets"

MESES_PT = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
]

HEADER = [
    "Data",
    "Agendamentos Confirmados",
    "Valor da Consulta",
    "Valor Total Consulta",
    "Cirurgias Confirmadas",
    "Valor da Cirurgia",
    "Valor Total Cirurgias"
]

HEADER_COLORS = {
    "bg": {"red": 0.13, "green": 0.27, "blue": 0.53},
    "fg": {"red": 1.0, "green": 1.0, "blue": 1.0}
}

TOTAL_ROW_COLOR = {"red": 0.85, "green": 0.85, "blue": 0.85}


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


def create_spreadsheet(title: str, first_tab: str, token: str) -> str:
    body = {
        "properties": {"title": title},
        "sheets": [{"properties": {"title": first_tab}}]
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
    range_ = urllib.parse.quote(f"{tab_name}!A1", safe="")
    url = f"{SHEETS_URL}/{spreadsheet_id}/values/{range_}?valueInputOption=USER_ENTERED"
    r = requests.put(url, json={"values": rows}, headers={"Authorization": f"Bearer {token}"})
    r.raise_for_status()


def get_sheet_ids(spreadsheet_id: str, token: str) -> dict:
    url = f"{SHEETS_URL}/{spreadsheet_id}?fields=sheets.properties"
    r = requests.get(url, headers={"Authorization": f"Bearer {token}"})
    r.raise_for_status()
    return {s["properties"]["title"]: s["properties"]["sheetId"] for s in r.json()["sheets"]}


def format_sheet(spreadsheet_id: str, sheet_id: int, num_days: int, token: str):
    total_row = num_days + 2  # header + days + total

    requests_list = [
        # Cabeçalho azul
        {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 0,
                    "endRowIndex": 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": 7
                },
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": HEADER_COLORS["bg"],
                        "textFormat": {
                            "foregroundColor": HEADER_COLORS["fg"],
                            "bold": True,
                            "fontSize": 10
                        },
                        "horizontalAlignment": "CENTER"
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)"
            }
        },
        # Linha TOTAL cinza
        {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": total_row - 1,
                    "endRowIndex": total_row,
                    "startColumnIndex": 0,
                    "endColumnIndex": 7
                },
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": TOTAL_ROW_COLOR,
                        "textFormat": {"bold": True},
                        "horizontalAlignment": "CENTER"
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)"
            }
        },
        # Centralizar coluna de data e números
        {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 1,
                    "endRowIndex": total_row,
                    "startColumnIndex": 0,
                    "endColumnIndex": 7
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
    col_widths = [90, 200, 150, 180, 180, 150, 180]
    for i, width in enumerate(col_widths):
        requests_list.append({
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
    r = requests.post(url, json={"requests": requests_list}, headers={"Authorization": f"Bearer {token}"})
    r.raise_for_status()


def build_month_rows(year: int, month: int) -> list:
    month_name = f"{MESES_PT[month-1]} {year}"
    num_days = calendar.monthrange(year, month)[1]

    rows = [HEADER]

    for day in range(1, num_days + 1):
        date_str = f"{day:02d}/{month:02d}"
        row_num = day + 1  # +1 por causa do header

        # D = Agendamentos, C = Valor Consulta, E = Cirurgias, F = Valor Cirurgia
        valor_total_consulta = f"=B{row_num}*C{row_num}"
        valor_total_cirurgia = f"=E{row_num}*F{row_num}"

        rows.append([
            date_str,
            "",                      # Agendamentos Confirmados
            "",                      # Valor da Consulta
            valor_total_consulta,    # Valor Total Consulta
            "",                      # Cirurgias Confirmadas
            "",                      # Valor da Cirurgia
            valor_total_cirurgia     # Valor Total Cirurgias
        ])

    # Linha TOTAL
    last_data_row = num_days + 1
    rows.append([
        "TOTAL",
        f"=SUM(B2:B{last_data_row})",
        "",
        f"=SUM(D2:D{last_data_row})",
        f"=SUM(E2:E{last_data_row})",
        "",
        f"=SUM(G2:G{last_data_row})"
    ])

    return rows, num_days


def main():
    year = 2026
    print("🔑 Autenticando...")
    token = _get_access_token()

    first_tab = f"{MESES_PT[0]} {year}"
    print(f"📊 Criando planilha: Agendamentos — Dr Vinicius")
    spreadsheet_id = create_spreadsheet(
        f"Agendamentos — Dr Vinicius",
        first_tab,
        token
    )

    # Janeiro (já criado com a planilha)
    rows, num_days = build_month_rows(year, 1)
    write_data(spreadsheet_id, first_tab, rows, token)
    print(f"   ✅ {first_tab}")

    # Fevereiro a Dezembro
    for month in range(2, 13):
        tab_name = f"{MESES_PT[month-1]} {year}"
        add_sheet(spreadsheet_id, tab_name, token)
        rows, num_days = build_month_rows(year, month)
        write_data(spreadsheet_id, tab_name, rows, token)
        print(f"   ✅ {tab_name}")

    # Formatar todas as abas
    print("🎨 Formatando...")
    sheet_ids = get_sheet_ids(spreadsheet_id, token)
    for month in range(1, 13):
        tab_name = f"{MESES_PT[month-1]} {year}"
        sid = sheet_ids.get(tab_name)
        if sid is not None:
            num_days = calendar.monthrange(year, month)[1]
            format_sheet(spreadsheet_id, sid, num_days, token)

    link = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"
    print(f"\n✅ Planilha criada com sucesso!")
    print(f"🔗 Link: {link}")


if __name__ == "__main__":
    main()
