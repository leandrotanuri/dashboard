"""
Adiciona colunas WhatsApp PCTE Modelo (Invest / Leads / CPL)
antes da coluna de Seguidores nas abas 📈 do Instituto Master Beauty.

Estrutura final:
  D-F   META — WhatsApp Alunos   (invest / leads / CPL)
  G-I   META — Lead Ads          (invest / leads / CPL)
  J-K   ocultas (LP)
  L-N   META — WhatsApp PCTE Modelo  (invest / leads / CPL)  ← NOVO
  O     Seguidores Ganhos         (manual)
  P     Total Invest              (=D+G+L)
  Q     Total Leads               (=E+H+M)
"""

import io, sys, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(__file__))
from sheets_client import _get_access_token
import requests

SHEET_ID   = "1frBnGLtYljtV1xQ-qufog3gHxplAYPTTWO-oIT5Kv1I"
SHEETS_URL = "https://sheets.googleapis.com/v4/spreadsheets"
MESES      = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"]

TRAFEGO_IDS = {
    "Jan": 241373107,  "Fev": 2058612474, "Mar": 640866637,  "Abr": 1774656171,
    "Mai": 1713917476, "Jun": 324483132,  "Jul": 1819205739, "Ago": 580767448,
    "Set": 1811114875, "Out": 2049680820, "Nov": 1659052681, "Dez": 532698598,
}


def values_batch(token, data):
    url  = f"{SHEETS_URL}/{SHEET_ID}/values:batchUpdate"
    body = {"data": data, "valueInputOption": "USER_ENTERED"}
    r = requests.post(url, json=body, headers={"Authorization": f"Bearer {token}"})
    r.raise_for_status()


def sheets_batch(token, reqs):
    url  = f"{SHEETS_URL}/{SHEET_ID}:batchUpdate"
    body = {"requests": reqs}
    r = requests.post(url, json=body, headers={"Authorization": f"Bearer {token}"})
    r.raise_for_status()


def insert_cols(sheet_id, col_index, count=3):
    """Insere `count` colunas em branco a partir de col_index (0-based)."""
    return {"insertDimension": {
        "range": {
            "sheetId":    sheet_id,
            "dimension":  "COLUMNS",
            "startIndex": col_index,
            "endIndex":   col_index + count,
        },
        "inheritFromBefore": True,
    }}


def main():
    token = _get_access_token()

    # ── 1. Inserir 3 colunas no índice 11 (antes de L = Seg Ganhos) ──
    print("1. Inserindo colunas PCTE Modelo em todas as abas 📈...")
    reqs = [insert_cols(sid, 11) for sid in TRAFEGO_IDS.values()]
    sheets_batch(token, reqs)
    print("   3 colunas inseridas em 12 abas ✓")

    # ── 2. Cabeçalhos, fórmulas e totais ─────────────────────────────
    # Nova estrutura (0-based → letra):
    #   L(11)=PCTE invest  M(12)=PCTE leads  N(13)=PCTE CPL
    #   O(14)=Seg Ganhos   P(15)=Total Invest  Q(16)=Total Leads
    print("2. Preenchendo cabeçalhos e fórmulas...")
    data = []
    for mes in MESES:
        aba = f"📈 {mes}"

        # Linha 3 — seções
        data.append({"range": f"'{aba}'!A3:Q3", "majorDimension": "ROWS", "values": [[
            "", "IDENTIFICAÇÃO", "",
            "META — WhatsApp Alunos", "", "",
            "META — Lead Ads", "", "",
            "", "",                           # J K ocultas
            "META — WhatsApp PCTE Modelo", "", "",
            "SEG.", "TOTAIS", "",
        ]]})

        # Linha 4 — sub-cabeçalhos
        data.append({"range": f"'{aba}'!A4:Q4", "majorDimension": "ROWS", "values": [[
            "", "Data", "Obs.",
            "Invest.\n(R$)", "Leads", "CPL\n(R$)",
            "Invest.\n(R$)", "Leads", "CPL\n(R$)",
            "", "",
            "Invest.\n(R$)", "Leads", "CPL\n(R$)",
            "Seg.\nGanhos",
            "Total\nInvest.(R$)", "Total\nLeads",
        ]]})

        # Linhas 5-35 — CPL PCTE Modelo (N) + Totais (P e Q)
        n_vals, p_vals, q_vals = [], [], []
        for row in range(5, 36):
            n_vals.append([f"=IFERROR(L{row}/M{row};0)"])
            p_vals.append([f"=D{row}+G{row}+L{row}"])
            q_vals.append([f"=E{row}+H{row}+M{row}"])
        data.append({"range": f"'{aba}'!N5:N35", "majorDimension": "ROWS", "values": n_vals})
        data.append({"range": f"'{aba}'!P5:P35", "majorDimension": "ROWS", "values": p_vals})
        data.append({"range": f"'{aba}'!Q5:Q35", "majorDimension": "ROWS", "values": q_vals})

        # Linha 36 — totais do mês
        data.append({"range": f"'{aba}'!L36:Q36", "majorDimension": "ROWS", "values": [[
            "=SUM(L5:L35)",          # L: PCTE invest
            "=SUM(M5:M35)",          # M: PCTE leads
            "=IFERROR(L36/M36;0)",   # N: PCTE CPL
            "=SUM(O5:O35)",          # O: Seg ganhos
            "=D36+G36+L36",          # P: Total invest
            "=E36+H36+M36",          # Q: Total leads
        ]]})

    values_batch(token, data)
    print("   Cabeçalhos e fórmulas preenchidos ✓")

    # ── 3. Corrigir Painel Mensal ─────────────────────────────────────
    # INDIRECT antigos → novos endereços:
    #   Total invest: M36 → P36
    #   Total leads:  N36 → Q36
    #   Seg ganhos:   L36 → O36
    print("3. Corrigindo Painel Mensal...")
    painel = [
        # Linha 8 WP — agora só Alunos (D, E, F)
        {"range": "'📊 Painel Mensal'!B8", "majorDimension": "ROWS",
         "values": [["Meta — WhatsApp Alunos"]]},
        # Nova linha para PCTE Modelo — inserir em linha 10 (antes de LP)
        # Vamos usar linha 10 (que era LP e está zerada)
        {"range": "'📊 Painel Mensal'!B10:E10", "majorDimension": "ROWS", "values": [[
            "Meta — WhatsApp PCTE Modelo",
            '=IFERROR(INDIRECT("\'📈 "&C4&"\'!L36");0)',
            '=IFERROR(INDIRECT("\'📈 "&C4&"\'!M36");0)',
            '=IFERROR(INDIRECT("\'📈 "&C4&"\'!N36");0)',
        ]]},
        # Linha 11 Seguidores — O36
        {"range": "'📊 Painel Mensal'!D11", "majorDimension": "ROWS",
         "values": [['=IFERROR(INDIRECT("\'📈 "&C4&"\'!O36");0)']]},
        # Linha 12 Google — zerar
        {"range": "'📊 Painel Mensal'!B12:E12", "majorDimension": "ROWS",
         "values": [["Google — LP", "0", "0", "—"]]},
        # Linha 13 TOTAL — P36, Q36
        {"range": "'📊 Painel Mensal'!C13:E13", "majorDimension": "ROWS",
         "values": [[
             '=IFERROR(INDIRECT("\'📈 "&C4&"\'!P36");0)',
             '=IFERROR(INDIRECT("\'📈 "&C4&"\'!Q36");0)',
             '=IFERROR(C13/D13;0)',
         ]]},
        # Linha 17 Leads Gerados — Q36
        {"range": "'📊 Painel Mensal'!C17", "majorDimension": "ROWS",
         "values": [['=IFERROR(INDIRECT("\'📈 "&C4&"\'!Q36");0)']]},
    ]
    values_batch(token, painel)
    print("   Painel Mensal corrigido ✓")

    print("\n✅ Concluído! Estrutura final das abas 📈:")
    print("   D-F  META — WhatsApp Alunos    (invest / leads / CPL)")
    print("   G-I  META — Lead Ads           (invest / leads / CPL)")
    print("   J-K  ocultas (LP)")
    print("   L-N  META — WhatsApp PCTE Modelo (invest / leads / CPL)  ← NOVO")
    print("   O    Seguidores Ganhos          (manual)")
    print("   P    Total Invest               (=D+G+L)")
    print("   Q    Total Leads                (=E+H+M)")


if __name__ == "__main__":
    main()
