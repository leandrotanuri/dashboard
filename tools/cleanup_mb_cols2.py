"""
Remove colunas desnecessárias do Instituto Master Beauty nas abas 📈:
  - Deleta: L (CPL LP), M (Seg invest), O (CPS), P/Q/R (Google)
  - Mantém: N → vira coluna L (seguidores ganhos, sem fórmula)
  - Total invest (S→M) e Total leads (T→N) ficam só com WP+LA
  - Painel Mensal: INDIRECT strings atualizados para novos endereços
"""

import io, sys, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(__file__))
from sheets_client import _get_access_token
import requests

SHEET_ID   = "1frBnGLtYljtV1xQ-qufog3gHxplAYPTTWO-oIT5Kv1I"
SHEETS_URL = "https://sheets.googleapis.com/v4/spreadsheets"

MESES = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"]

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

def delete_col(sheet_id, col_index):
    return {"deleteDimension": {"range": {
        "sheetId": sheet_id, "dimension": "COLUMNS",
        "startIndex": col_index, "endIndex": col_index + 1,
    }}}


def main():
    token = _get_access_token()

    # ── ETAPA 1: Corrigir S e T antes de deletar P e Q ──────────────
    print("1. Corrigindo fórmulas de Total Invest e Total Leads (S e T)...")
    pre_data = []
    for mes in MESES:
        aba = f"📈 {mes}"
        # S5:S35 = D+G (apenas WP + Lead Ads; J=0, P vai ser deletado)
        s_vals = [[f"=D{r}+G{r}"] for r in range(5, 36)]
        pre_data.append({"range": f"'{aba}'!S5:S35", "majorDimension": "ROWS", "values": s_vals})
        # T5:T35 = E+H
        t_vals = [[f"=E{r}+H{r}"] for r in range(5, 36)]
        pre_data.append({"range": f"'{aba}'!T5:T35", "majorDimension": "ROWS", "values": t_vals})

    values_batch(token, pre_data)
    print("   S e T corrigidos em 12 abas ✓")

    # ── ETAPA 2: Deletar colunas (ordem inversa para preservar índices) ─
    # Colunas 0-based: L=11, M=12, O=14, P=15, Q=16, R=17
    # Deletar em ordem reversa: R(17), Q(16), P(15), O(14), M(12), L(11)
    print("2. Deletando colunas L, M, O, P, Q, R de todas as abas 📈...")
    cols_reverse = [17, 16, 15, 14, 12, 11]
    reqs = []
    for mes, sheet_id in TRAFEGO_IDS.items():
        for col in cols_reverse:
            reqs.append(delete_col(sheet_id, col))

    # Enviar em lotes de 100
    for i in range(0, len(reqs), 100):
        sheets_batch(token, reqs[i:i+100])
    print("   12 abas 📈 limpas ✓")

    # ── ETAPA 3: Atualizar cabeçalhos das abas 📈 ───────────────────
    # Após deleção a estrutura ficou:
    #   B=Data C=Obs D=WP Invest E=WP Leads F=WP CPL
    #   G=LA Invest H=LA Leads I=LA CPL
    #   J=hidden K=hidden
    #   L=Seg Ganhos (era N)
    #   M=Total Invest (era S)  N=Total Leads (era T)
    print("3. Atualizando cabeçalhos das abas 📈...")
    header_data = []
    for mes in MESES:
        aba = f"📈 {mes}"
        # Linha 3: seções
        header_data.append({"range": f"'{aba}'!A3:N3", "majorDimension": "ROWS", "values": [[
            "", "IDENTIFICAÇÃO", "", "META — WhatsApp", "", "", "META — Lead Ads", "", "", "", "", "SEG.", "TOTAIS", "",
        ]]})
        # Linha 4: sub-cabeçalhos
        header_data.append({"range": f"'{aba}'!A4:N4", "majorDimension": "ROWS", "values": [[
            "", "Data", "Obs.", "Invest.\n(R$)", "Leads", "CPL\n(R$)",
            "Invest.\n(R$)", "Leads", "CPL\n(R$)",
            "", "",  # J e K ocultos
            "Seg.\nGanhos", "Total\nInvest.(R$)", "Total\nLeads",
        ]]})

    values_batch(token, header_data)
    print("   Cabeçalhos atualizados ✓")

    # ── ETAPA 4: Corrigir Painel Mensal (INDIRECT strings) ──────────
    # Após deleção:
    #   old N36 → new L36 (seg ganhos)
    #   old S36 → new M36 (total invest)
    #   old T36 → new N36 (total leads)
    print("4. Corrigindo Painel Mensal...")
    painel_data = [
        # Linha 10 LP — não usada: zerar
        {"range": "'📊 Painel Mensal'!C10:E10", "majorDimension": "ROWS",
         "values": [["0", "0", "—"]]},
        # Linha 11 Seguidores — invest=0, count=L36 (sem custo)
        {"range": "'📊 Painel Mensal'!C11:E11", "majorDimension": "ROWS",
         "values": [[
             "0",
             '=IFERROR(INDIRECT("\'📈 "&C4&"\'!L36");0)',
             "—",
         ]]},
        # Linha 12 Google — não usada: zerar
        {"range": "'📊 Painel Mensal'!C12:E12", "majorDimension": "ROWS",
         "values": [["0", "0", "—"]]},
        # Linha 13 TOTAL — invest=M36, leads=N36
        {"range": "'📊 Painel Mensal'!C13:E13", "majorDimension": "ROWS",
         "values": [[
             '=IFERROR(INDIRECT("\'📈 "&C4&"\'!M36");0)',
             '=IFERROR(INDIRECT("\'📈 "&C4&"\'!N36");0)',
             '=IFERROR(C13/D13;0)',
         ]]},
        # Linha 17 Leads Gerados — total leads = N36
        {"range": "'📊 Painel Mensal'!C17", "majorDimension": "ROWS",
         "values": [['=IFERROR(INDIRECT("\'📈 "&C4&"\'!N36");0)']]},
    ]
    values_batch(token, painel_data)
    print("   Painel Mensal corrigido ✓")

    print("\n✅ Concluído! Estrutura final das abas 📈:")
    print("   D-F  WhatsApp (invest / leads / CPL)")
    print("   G-I  Lead Ads (invest / leads / CPL)")
    print("   J-K  (ocultas — LP, sempre zero)")
    print("   L    Seguidores ganhos (preenchimento manual)")
    print("   M    Total Invest (=D+G)")
    print("   N    Total Leads (=E+H)")


if __name__ == "__main__":
    main()
