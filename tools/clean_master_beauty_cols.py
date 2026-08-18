"""
Limpa colunas desnecessárias da planilha Instituto Master Beauty:
  📋 tabs : deleta C, D, G, J, K (em ordem reversa para não deslocar índices)
  📈 tabs : oculta J e K (Landing Page — não usado; ocultar preserva INDIRECT do Painel)
  Painel Mensal: corrige INDIRECT de E10 → C10 após deleção
"""

import io, sys, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(__file__))
from sheets_client import _get_access_token
import requests

SHEET_ID   = "1frBnGLtYljtV1xQ-qufog3gHxplAYPTTWO-oIT5Kv1I"
SHEETS_URL = "https://sheets.googleapis.com/v4/spreadsheets"

RESUMO_IDS = {   # 📋 tabs
    "Jan": 1748660919, "Fev": 1206569391, "Mar": 1695968661, "Abr": 757038641,
    "Mai": 956037642,  "Jun": 319589234,  "Jul": 463921140,  "Ago": 980107805,
    "Set": 1325810023, "Out": 1140482076, "Nov": 1184551744, "Dez": 798985451,
}

TRAFEGO_IDS = {  # 📈 tabs
    "Jan": 241373107,  "Fev": 2058612474, "Mar": 640866637,  "Abr": 1774656171,
    "Mai": 1713917476, "Jun": 324483132,  "Jul": 1819205739,  "Ago": 580767448,
    "Set": 1811114875, "Out": 2049680820, "Nov": 1659052681,  "Dez": 532698598,
}


def spreadsheet_batch_update(token, requests_list):
    url  = f"{SHEETS_URL}/{SHEET_ID}:batchUpdate"
    body = {"requests": requests_list}
    r = requests.post(url, json=body, headers={"Authorization": f"Bearer {token}"})
    r.raise_for_status()
    return r.json()


def values_batch_update(token, data):
    url  = f"{SHEETS_URL}/{SHEET_ID}/values:batchUpdate"
    body = {"data": data, "valueInputOption": "USER_ENTERED"}
    r = requests.post(url, json=body, headers={"Authorization": f"Bearer {token}"})
    r.raise_for_status()
    return r.json()


def delete_column(sheet_id, col_index):
    """Retorna request para deletar uma coluna (0-based index)."""
    return {
        "deleteDimension": {
            "range": {
                "sheetId":    sheet_id,
                "dimension":  "COLUMNS",
                "startIndex": col_index,
                "endIndex":   col_index + 1,
            }
        }
    }


def hide_columns(sheet_id, start_index, end_index):
    """Retorna request para ocultar colunas (0-based, end exclusive)."""
    return {
        "updateDimensionProperties": {
            "range": {
                "sheetId":    sheet_id,
                "dimension":  "COLUMNS",
                "startIndex": start_index,
                "endIndex":   end_index,
            },
            "properties": {"hiddenByUser": True},
            "fields": "hiddenByUser",
        }
    }


def main():
    token = _get_access_token()

    # ── 1. Deletar colunas das abas 📋 ──────────────────────────────
    # Colunas a deletar (0-based): C=2, D=3, G=6, J=9, K=10
    # IMPORTANTE: processar da maior para a menor para preservar índices
    cols_to_delete = [10, 9, 6, 3, 2]  # K, J, G, D, C

    print("1. Deletando colunas C, D, G, J, K das abas 📋...")
    reqs = []
    for mes, sheet_id in RESUMO_IDS.items():
        for col in cols_to_delete:
            reqs.append(delete_column(sheet_id, col))

    # Enviar em lotes de 100 (limite da API)
    for i in range(0, len(reqs), 100):
        spreadsheet_batch_update(token, reqs[i:i+100])
    print(f"   12 abas 📋 limpas ✓")

    # ── 2. Ocultar colunas J e K das abas 📈 ────────────────────────
    # J=9, K=10 (0-based), Landing Page — não usada
    print("2. Ocultando colunas J e K (Landing Page) das abas 📈...")
    reqs2 = []
    for mes, sheet_id in TRAFEGO_IDS.items():
        reqs2.append(hide_columns(sheet_id, 9, 11))  # J e K

    spreadsheet_batch_update(token, reqs2)
    print(f"   12 abas 📈 atualizadas ✓")

    # ── 3. Corrigir Painel Mensal ────────────────────────────────────
    # Após deletar C e D das 📋, a coluna Alunos Fechados
    # que era E passou a ser C → INDIRECT precisa usar C10
    print("3. Corrigindo fórmula do Painel Mensal (E10 → C10)...")
    values_batch_update(token, [
        {
            "range": "'📊 Painel Mensal'!C18",
            "majorDimension": "ROWS",
            "values": [['=IFERROR(INDIRECT("\'📋 "&C4&"\'!C10");0)']],
        }
    ])
    print("   Painel Mensal corrigido ✓")

    print("\n✅ Limpeza concluída!")


if __name__ == "__main__":
    main()
