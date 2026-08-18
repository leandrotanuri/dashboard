"""
Cria planilha de Agendamentos do Dr Vinicius com tudo em uma única aba.
Meses emendados um abaixo do outro, com cabeçalho de mês antes de cada bloco.
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


def create_spreadsheet(title: str, tab_name: str, token: str) -> str:
    body = {
        "properties": {"title": title},
        "sheets": [{"properties": {"title": tab_name}}]
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


def build_all_rows(year: int, start_month: int = 4) -> tuple:
    """Constrói todas as linhas e retorna junto com metadados de formatação."""
    all_rows = [HEADER]  # Linha 1: cabeçalho fixo

    format_info = []
    format_info.append((0, "header"))  # cabeçalho principal

    current_row = 1  # começa na linha 2 (índice 1)

    for month in range(start_month, 13):
        num_days = calendar.monthrange(year, month)[1]

        # Linhas dos dias — sem cabeçalho de mês e sem total
        for day in range(1, num_days + 1):
            date_str = f"{day:02d}/{month:02d}"
            sheet_row = current_row + 1  # +1 porque sheets é 1-indexed

            valor_total_consulta = f"=B{sheet_row}*C{sheet_row}"
            valor_total_cirurgia = f"=E{sheet_row}*F{sheet_row}"

            all_rows.append([
                date_str,
                "",
                "",
                valor_total_consulta,
                "",
                "",
                valor_total_cirurgia
            ])
            current_row += 1

    return all_rows, format_info


def format_sheet(spreadsheet_id: str, sheet_id: int, format_info: list, token: str):
    requests_list = []

    # Congelar cabeçalho
    requests_list.append({
        "updateSheetProperties": {
            "properties": {
                "sheetId": sheet_id,
                "gridProperties": {"frozenRowCount": 1}
            },
            "fields": "gridProperties.frozenRowCount"
        }
    })

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

    for row_idx, tipo in format_info:
        if tipo == "header":
            # Azul escuro
            bg = {"red": 0.13, "green": 0.27, "blue": 0.53}
            fg = {"red": 1.0, "green": 1.0, "blue": 1.0}
            bold = True
        elif tipo == "month":
            # Azul médio
            bg = {"red": 0.27, "green": 0.45, "blue": 0.72}
            fg = {"red": 1.0, "green": 1.0, "blue": 1.0}
            bold = True
        elif tipo == "total":
            # Cinza
            bg = {"red": 0.83, "green": 0.83, "blue": 0.83}
            fg = {"red": 0.0, "green": 0.0, "blue": 0.0}
            bold = True
        else:
            continue  # linhas de data não precisam de formatação especial

        requests_list.append({
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": row_idx,
                    "endRowIndex": row_idx + 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": 7
                },
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": bg,
                        "textFormat": {
                            "foregroundColor": fg,
                            "bold": bold,
                            "fontSize": 10
                        },
                        "horizontalAlignment": "CENTER"
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)"
            }
        })

    url = f"{SHEETS_URL}/{spreadsheet_id}:batchUpdate"
    r = requests.post(url, json={"requests": requests_list}, headers={"Authorization": f"Bearer {token}"})
    r.raise_for_status()


def main():
    year = 2026
    start_month = 4  # Começa em Abril
    tab_name = "Agendamentos"

    print("🔑 Autenticando...")
    token = _get_access_token()

    print("📊 Criando planilha: Agendamentos — Dr Vinicius")
    spreadsheet_id = create_spreadsheet("Agendamentos — Dr Vinicius", tab_name, token)

    print("📝 Construindo dados...")
    all_rows, format_info = build_all_rows(year, start_month)

    print("💾 Salvando dados...")
    write_data(spreadsheet_id, tab_name, all_rows, token)

    print("🎨 Formatando...")
    sheet_ids = get_sheet_ids(spreadsheet_id, token)
    sheet_id = sheet_ids[tab_name]
    format_sheet(spreadsheet_id, sheet_id, format_info, token)

    link = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"
    print(f"\n✅ Planilha criada com sucesso!")
    print(f"🔗 Link: {link}")


if __name__ == "__main__":
    main()
