"""
Ferramenta: run_report.py
Orquestra o pipeline completo: busca → processa → envia para Google Sheets.

IMPORTANTE: sempre executar a partir da raiz do projeto.

Uso:
    python tools/run_report.py --date_start 2026-03-01 --date_end 2026-03-31
    python tools/run_report.py --date_start 2026-03-01 --date_end 2026-03-31 --level adset
"""

import sys
import os
import argparse
import traceback
from pathlib import Path

# Garante que a raiz do projeto esteja no path ao rodar como script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests
from dotenv import load_dotenv

from tools.fetch_meta_insights import fetch_insights, save_to_csv, DEFAULT_FIELDS
from tools.process_insights import load_and_clean, build_resumo, build_campanhas, build_diario, save_outputs
from tools.upload_to_sheets import upload_folder

load_dotenv()


def run_report(
    date_start: str,
    date_end: str,
    level: str = "campaign",
    spreadsheet_id: str | None = None,
    output_dir: Path = Path("output"),
    fields: str = DEFAULT_FIELDS,
) -> None:
    if not spreadsheet_id:
        spreadsheet_id = os.getenv("GOOGLE_SPREADSHEET_ID")
    if not spreadsheet_id:
        raise EnvironmentError("GOOGLE_SPREADSHEET_ID precisa estar no .env ou passado como --spreadsheet_id")

    # ── ETAPA 1: Buscar dados ──────────────────────────────────────────────────
    print(f"\n=== ETAPA 1/3: Buscando insights do Meta Ads ===")
    print(f"  Nível: {level} | Período: {date_start} → {date_end}")

    rows = fetch_insights(date_start, date_end, level, fields)

    if not rows:
        print("Aviso: nenhum dado retornado pela API para o período informado. Encerrando.")
        sys.exit(0)

    raw_csv = output_dir / f"meta_insights_{level}_{date_start}_{date_end}.csv"
    save_to_csv(rows, raw_csv)

    # ── ETAPA 2: Processar dados ───────────────────────────────────────────────
    print(f"\n=== ETAPA 2/3: Processando dados ===")

    df = load_and_clean(raw_csv)
    print(f"  {len(df)} linhas carregadas.")

    resumo = build_resumo(df)
    campanhas = build_campanhas(df)
    diario = build_diario(df)
    save_outputs(resumo, campanhas, diario, output_dir)

    # ── ETAPA 3: Enviar para Google Sheets ────────────────────────────────────
    print(f"\n=== ETAPA 3/3: Enviando para Google Sheets ===")
    print(f"  Planilha ID: {spreadsheet_id}")

    upload_folder(output_dir, spreadsheet_id)

    print(f"\nRelatório concluído. Abas atualizadas: Resumo, Campanhas, Diário")


def main():
    parser = argparse.ArgumentParser(description="Pipeline completo Meta Ads → Google Sheets")
    parser.add_argument("--date_start", required=True, help="Data início YYYY-MM-DD")
    parser.add_argument("--date_end", required=True, help="Data fim YYYY-MM-DD")
    parser.add_argument("--level", default="campaign", choices=["campaign", "adset", "ad"])
    parser.add_argument("--spreadsheet_id", default=None, help="ID da planilha (padrão: .env)")
    parser.add_argument("--fields", default=DEFAULT_FIELDS)
    parser.add_argument("--output_dir", default="output")
    args = parser.parse_args()

    try:
        run_report(
            date_start=args.date_start,
            date_end=args.date_end,
            level=args.level,
            spreadsheet_id=args.spreadsheet_id,
            output_dir=Path(args.output_dir),
            fields=args.fields,
        )
    except requests.HTTPError as e:
        print(f"\nErro na API do Meta: {e.response.status_code} — {e.response.text}")
        sys.exit(1)
    except EnvironmentError as e:
        print(f"\nCredencial ausente: {e}")
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"\nArquivo não encontrado: {e}")
        sys.exit(1)
    except Exception:
        print("\nErro inesperado:")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
