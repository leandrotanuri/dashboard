"""
Ferramenta: upload_to_sheets.py
Envia um CSV (ou pasta de CSVs) para o Google Sheets via Google Workspace CLI (gws).

Pré-requisito: gws instalado e autenticado (`gws auth login`).
  npm install -g @googleworkspace/cli
  gws auth login   # faz o fluxo OAuth

Uso — arquivo único:
    python tools/upload_to_sheets.py --input output/resumo.csv --sheet_name Resumo

Uso — batch (pasta completa):
    python tools/upload_to_sheets.py --folder output/
"""

import os
import csv
import json
import argparse
import subprocess
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BATCH_NAME_MAP = {
    "resumo": "Resumo",
    "campanhas": "Campanhas",
    "diario": "Diário",
}


def _run_gws(*args: str, body: dict | None = None) -> dict:
    """
    Executa um comando gws e retorna o JSON parseado da saída.
    Usa shell=True para compatibilidade com Windows (.cmd wrapper do npm).
    """
    parts = ["gws"] + list(args)
    if body is not None:
        parts += ["--json", json.dumps(body, ensure_ascii=False)]

    # No Windows o gws é um .cmd — shell=True é necessário para resolvê-lo
    cmd_str = " ".join(json.dumps(p) for p in parts)

    result = subprocess.run(
        cmd_str,
        capture_output=True,
        shell=True,
    )

    stdout = result.stdout.decode("utf-8", errors="replace")
    stderr = result.stderr.decode("utf-8", errors="replace")

    if result.returncode != 0:
        # Ignora linhas de status do keyring no stderr antes de reportar erro
        error_lines = [l for l in stderr.splitlines() if "keyring" not in l.lower()]
        raise RuntimeError(
            f"gws falhou (exit {result.returncode}):\n" + "\n".join(error_lines)
        )

    # Remove linhas de status do keyring do stdout antes de parsear
    clean = "\n".join(l for l in stdout.splitlines() if "keyring" not in l.lower())
    return json.loads(clean) if clean.strip() else {}


def _list_sheet_titles(spreadsheet_id: str) -> set[str]:
    """Retorna os títulos de todas as abas existentes na planilha."""
    data = _run_gws(
        "sheets", "spreadsheets", "get",
        "--params", json.dumps({
            "spreadsheetId": spreadsheet_id,
            "fields": "sheets.properties.title",
        }),
    )
    return {s["properties"]["title"] for s in data.get("sheets", [])}


def _ensure_sheet_exists(spreadsheet_id: str, sheet_name: str, existing: set[str]) -> None:
    """Cria a aba se ela ainda não existir."""
    if sheet_name not in existing:
        _run_gws(
            "sheets", "spreadsheets", "batchUpdate",
            "--params", json.dumps({"spreadsheetId": spreadsheet_id}),
            body={"requests": [{"addSheet": {"properties": {"title": sheet_name}}}]},
        )
        print(f"  Aba '{sheet_name}' criada.")


def upload_csv(input_path: Path, spreadsheet_id: str, sheet_name: str) -> None:
    """Envia um CSV para uma aba do Google Sheets, substituindo o conteúdo existente."""
    with open(input_path, "r", encoding="utf-8") as f:
        rows = list(csv.reader(f))

    if not rows:
        print(f"Aviso: arquivo vazio, ignorando: {input_path}")
        return

    existing = _list_sheet_titles(spreadsheet_id)
    _ensure_sheet_exists(spreadsheet_id, sheet_name, existing)

    # Limpa o conteúdo atual da aba
    _run_gws(
        "sheets", "spreadsheets", "values", "clear",
        "--params", json.dumps({"spreadsheetId": spreadsheet_id, "range": sheet_name}),
    )

    # Escreve os novos valores
    _run_gws(
        "sheets", "spreadsheets", "values", "update",
        "--params", json.dumps({
            "spreadsheetId": spreadsheet_id,
            "range": f"{sheet_name}!A1",
            "valueInputOption": "RAW",
        }),
        body={"values": rows},
    )

    print(f"Planilha atualizada: aba '{sheet_name}' com {len(rows) - 1} linha(s) de dados")


def upload_folder(
    folder_path: Path,
    spreadsheet_id: str,
    name_map: dict | None = None,
) -> None:
    """Envia vários CSVs de uma pasta para abas correspondentes no Google Sheets."""
    if name_map is None:
        name_map = BATCH_NAME_MAP

    for filename_stem, sheet_name in name_map.items():
        csv_path = folder_path / f"{filename_stem}.csv"
        if not csv_path.exists():
            print(f"Aviso: arquivo não encontrado, ignorando: {csv_path}")
            continue
        upload_csv(csv_path, spreadsheet_id, sheet_name)


def main():
    parser = argparse.ArgumentParser(description="Upload CSV(s) para Google Sheets via gws CLI")

    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--input", help="Caminho de um único CSV")
    mode.add_argument("--folder", help="Pasta com CSVs para upload em batch")

    parser.add_argument("--sheet_name", help="Nome da aba destino (necessário com --input)")
    parser.add_argument(
        "--spreadsheet_id",
        default=os.getenv("GOOGLE_SPREADSHEET_ID"),
        help="ID da planilha (padrão: GOOGLE_SPREADSHEET_ID do .env)",
    )
    args = parser.parse_args()

    if not args.spreadsheet_id:
        raise EnvironmentError(
            "GOOGLE_SPREADSHEET_ID precisa estar no .env ou passado como --spreadsheet_id"
        )

    if args.folder:
        upload_folder(Path(args.folder), args.spreadsheet_id)
    else:
        if not args.sheet_name:
            parser.error("--sheet_name é obrigatório quando usando --input")
        upload_csv(Path(args.input), args.spreadsheet_id, args.sheet_name)


if __name__ == "__main__":
    main()
