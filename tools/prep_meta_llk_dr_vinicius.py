"""
Limpa a planilha de contatos do Dr. Vinicius e gera lista no padrao Meta
(Custom Audience / Lookalike - LLK).

- Le a aba original (Pagina1: coluna A = nome, coluna B = telefone)
- Remove linhas vazias e cabecalhos de secao ("Paciente", "Pacientes ... semana")
- Normaliza telefone p/ E.164 BR (+55DDDNNNNNNNNN), removendo espacos,
  tracos e caracteres invisiveis (LTR/RTL marks, nbsp)
- Deduplica por telefone
- Sinaliza numeros que precisam conferencia (10/12/9 digitos, internacionais)
- Escreve nova aba "Meta - Lista LLK" (nao mexe na original)
- Salva CSV pronto p/ upload em output/meta_llk_dr_vinicius.csv

Uso:
    python tools/prep_meta_llk_dr_vinicius.py            # dry-run (so mostra)
    python tools/prep_meta_llk_dr_vinicius.py --write    # grava aba + csv
"""
import sys
import re
import csv
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import sheets_client as sc

SID = "1GkqmPnd2_vLS5O23n7DXicTnXK5rN-P-Cj0ltGvd9tc"
SRC_RANGE = "A1:B1100"
DEST_TAB = "Meta - Lista LLK"
OUT_CSV = Path(__file__).parent.parent / "output" / "meta_llk_dr_vinicius.csv"

PARTICULAS = {"de", "da", "do", "das", "dos", "e", "di", "du", "del", "della", "van", "von"}

DDDS_BR = {"11","12","13","14","15","16","17","18","19","21","22","24","27","28",
           "31","32","33","34","35","37","38","41","42","43","44","45","46","47","48","49",
           "51","53","54","55","61","62","63","64","65","66","67","68","69",
           "71","73","74","75","77","79","81","82","83","84","85","86","87","88","89",
           "91","92","93","94","95","96","97","98","99"}

# Linhas de cabecalho/secao que nao sao contatos
HEADER_RE = re.compile(r"^\s*(paciente|pacientes\b)", re.IGNORECASE)


def title_br(nome: str) -> str:
    palavras = re.sub(r"\s+", " ", nome).strip().split(" ")
    out = []
    for i, p in enumerate(palavras):
        low = p.lower()
        if i > 0 and low in PARTICULAS:
            out.append(low)
        else:
            out.append(low.capitalize())
    return " ".join(out)


def split_nome(nome: str):
    partes = nome.split(" ")
    fn = partes[0]
    ln = partes[-1] if len(partes) > 1 else ""
    return fn, ln


def normaliza_tel(raw: str):
    """Retorna (e164, obs). e164=None se sem telefone. obs != '' = corrigido ou verificar."""
    d = re.sub(r"\D", "", raw or "")
    d = d.lstrip("0")  # tira trunk nacional
    if not d:
        return None, "sem telefone"

    n = len(d)

    # Numeros internacionais reais (nao mexer)
    if d.startswith("351") and n == 12 and d[3] == "9":       # celular Portugal
        return "+" + d, "internacional (Portugal)"
    if d.startswith("596"):                                    # Antilhas francesas
        return "+" + d, "internacional"

    if d.startswith("55") and n in (12, 13):
        return "+" + d, ""                                     # ja tem DDI BR
    if n == 11:
        return "+55" + d, ""                                   # celular BR ok
    if n == 10:
        if d[:2] in DDDS_BR:                                   # falta o 9 do celular
            return "+55" + d[:2] + "9" + d[2:], "corrigido: +9 apos DDD"
        return "+55" + d, "VERIFICAR: DDD inexistente"
    if n == 12:
        if d[:2] in DDDS_BR:                                   # digito extra na 3a posicao
            return "+55" + d[:2] + d[3:], "corrigido: removido digito extra"
        return "+" + d, "VERIFICAR: internacional?"
    if n == 9:                                                 # sem DDD -> nao da p/ inferir
        return "+55" + d, "VERIFICAR: falta DDD"
    if n >= 13:
        return "+" + d, "VERIFICAR: internacional?"
    return "+55" + d, f"VERIFICAR: so {n} digitos"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="grava aba no Sheets e CSV")
    args = ap.parse_args()

    rows = sc.read_range(SID, SRC_RANGE)

    limpos = []          # (e164, fn, ln, nome_limpo, obs, tel_orig)
    seen = set()
    sem_tel = 0
    dup = 0
    for r in rows:
        nome = (r[0] if len(r) > 0 else "").replace("\n", " ").strip()
        tel = (r[1] if len(r) > 1 else "").strip()
        if not nome or HEADER_RE.match(nome):
            continue
        e164, obs = normaliza_tel(tel)
        if e164 is None:
            sem_tel += 1
            continue
        if e164 in seen:
            dup += 1
            continue
        seen.add(e164)
        nome_limpo = title_br(nome)
        fn, ln = split_nome(nome_limpo)
        limpos.append((e164, fn, ln, nome_limpo, obs, tel))

    corrigidos = [x for x in limpos if x[4].startswith("corrigido")]
    verificar = [x for x in limpos if x[4].startswith("VERIFICAR")]

    print(f"linhas lidas:            {len(rows)}")
    print(f"contatos sem telefone:   {sem_tel} (descartados p/ Meta)")
    print(f"duplicados por telefone: {dup}")
    print(f"contatos unicos c/ tel:  {len(limpos)}")
    print(f"numeros CORRIGIDOS:      {len(corrigidos)}")
    print(f"ainda p/ VERIFICAR:      {len(verificar)}")
    print("\n--- corrigidos automaticamente ---")
    for e164, fn, ln, nome, obs, orig in corrigidos:
        print(f"  {orig!r:16} -> {e164:16} | {nome:32} | {obs}")
    print("\n--- ainda precisam olho humano ---")
    for e164, fn, ln, nome, obs, orig in verificar:
        print(f"  {orig!r:16} -> {e164:16} | {nome:32} | {obs}")

    if not args.write:
        print("\n(dry-run) rode com --write para gravar aba e CSV.")
        return

    # Aba completa (com obs) no Sheets
    sheet_rows = [["phone", "fn", "ln", "country", "nome_completo", "obs", "telefone_original"]]
    for e164, fn, ln, nome, obs, orig in limpos:
        # apostrofo forca o Sheets a guardar como texto e preservar o "+"
        sheet_rows.append(["'" + e164, fn, ln, "br", nome, obs, "'" + orig])
    sc.write_tab(SID, DEST_TAB, sheet_rows)
    print(f"\nOK: aba '{DEST_TAB}' gravada com {len(limpos)} contatos.")

    # CSV limpo p/ upload (so 9-digitos invalidos ficam de fora)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["phone", "fn", "ln", "country"])
        n = 0
        for e164, fn, ln, nome, obs, orig in limpos:
            if "falta DDD" in obs or "so " in obs:  # sem area = inutilizavel p/ Meta
                continue
            w.writerow([e164, fn, ln, "br"])
            n += 1
    print(f"OK: CSV salvo em {OUT_CSV} ({n} linhas).")


if __name__ == "__main__":
    main()
