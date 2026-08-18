"""
Adapta a planilha do Instituto Master Beauty:
- Painel Mensal: remove Consultas/Procedimentos, usa Alunos Fechados
- Abas 📋 (resumo semanal): renomeia e simplifica para contexto de cursos
- Config: atualiza nome do cliente
"""

import io, sys, json, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(__file__))
from sheets_client import _get_access_token
import requests

SHEET_ID  = "1frBnGLtYljtV1xQ-qufog3gHxplAYPTTWO-oIT5Kv1I"
SHEETS_URL = "https://sheets.googleapis.com/v4/spreadsheets"
MESES     = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"]


def batch_update_values(token, data):
    url  = f"{SHEETS_URL}/{SHEET_ID}/values:batchUpdate"
    body = {"data": data, "valueInputOption": "USER_ENTERED"}
    r = requests.post(url, json=body, headers={"Authorization": f"Bearer {token}"})
    r.raise_for_status()
    return r.json()


def main():
    token = _get_access_token()

    # ── 1. Painel Mensal ──────────────────────────────────────────────
    print("1. Atualizando Painel Mensal...")

    painel_data = [
        # Linha 18: Alunos Fechados (substituindo Leads Agendados)
        {
            "range": "'📊 Painel Mensal'!B18:G18",
            "majorDimension": "ROWS",
            "values": [[
                "Alunos Fechados",
                '=IFERROR(INDIRECT("\'📋 "&C4&"\'!E10");0)',
                "='⚙️ Config'!C15",
                "=IFERROR(C18/D18;0)",
                "=IFERROR(C13/C18;0)",
                '=IF(D18=0;"—";IF(C18/D18>=1;"✅ Meta atingida";IF(C18/D18>=0,7;"⚠️ Perto";"🔴 Abaixo")))',
            ]]
        },
        # Linha 19: limpar Consultas Realizadas
        {
            "range": "'📊 Painel Mensal'!B19:G19",
            "majorDimension": "ROWS",
            "values": [["—", "—", "—", "—", "—", "—"]]
        },
        # Linha 20: limpar Procedimentos Fechados
        {
            "range": "'📊 Painel Mensal'!B20:G20",
            "majorDimension": "ROWS",
            "values": [["—", "—", "—", "—", "—", "—"]]
        },
        # Linha 21: Faturamento = Alunos * Ticket Médio
        {
            "range": "'📊 Painel Mensal'!C21",
            "majorDimension": "ROWS",
            "values": [["=C18*'⚙️ Config'!C16"]]
        },
        # Linha 23: Ticket Médio fixo da Config
        {
            "range": "'📊 Painel Mensal'!C23:D23",
            "majorDimension": "ROWS",
            "values": [["='⚙️ Config'!C16", "='⚙️ Config'!C16"]]
        },
    ]
    batch_update_values(token, painel_data)
    print("   Painel Mensal atualizado ✓")

    # ── 2. Todas as abas 📋 ───────────────────────────────────────────
    print("2. Atualizando abas de resumo mensal (📋)...")

    resumo_data = []
    for mes in MESES:
        aba = f"📋 {mes}"

        # Cabeçalhos row 4
        resumo_data.append({
            "range": f"'{aba}'!B4:J4",
            "majorDimension": "ROWS",
            "values": [[
                "Semana\n(data início)",
                "—",
                "—",
                "Alunos\nFechados",
                "Faturamento\n(R$)",
                "",
                "Invest.\nda Semana (R$)",
                "Custo/\nAluno (R$)",
                "",
            ]]
        })

        # Limpar colunas C e D (não usadas para instituto)
        resumo_data.append({
            "range": f"'{aba}'!C5:D9",
            "majorDimension": "ROWS",
            "values": [["", ""], ["", ""], ["", ""], ["", ""], ["", ""]]
        })

        # F5:F9 = Alunos * Ticket Médio (faturamento automático)
        faturamento_rows = []
        for row in range(5, 10):
            faturamento_rows.append([f"=IF(E{row}=\"\";0;E{row}*'⚙️ Config'!C16)"])
        resumo_data.append({
            "range": f"'{aba}'!F5:F9",
            "majorDimension": "ROWS",
            "values": faturamento_rows
        })

        # F10 = total faturamento
        resumo_data.append({
            "range": f"'{aba}'!F10",
            "majorDimension": "ROWS",
            "values": [["=SUM(F5:F9)"]]
        })

        # I5:I9 = Custo por aluno (investimento / alunos)
        custo_rows = []
        for row in range(5, 10):
            custo_rows.append([f"=IFERROR(H{row}/E{row};0)"])
        resumo_data.append({
            "range": f"'{aba}'!I5:I9",
            "majorDimension": "ROWS",
            "values": custo_rows
        })

        # I10 = total custo/aluno
        resumo_data.append({
            "range": f"'{aba}'!I10",
            "majorDimension": "ROWS",
            "values": [["=IFERROR(H10/E10;0)"]]
        })

    batch_update_values(token, resumo_data)
    print(f"   {len(MESES)} abas de resumo atualizadas ✓")

    # ── 3. Config ────────────────────────────────────────────────────
    print("3. Atualizando Config...")
    config_data = [
        {
            "range": "'⚙️ Config'!C5",
            "majorDimension": "ROWS",
            "values": [["Instituto Master Beauty"]]
        },
    ]
    batch_update_values(token, config_data)
    print("   Config atualizado ✓")

    print("\n✅ Adaptação concluída!")
    print(f"   Planilha: https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit")


if __name__ == "__main__":
    main()
