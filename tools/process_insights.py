"""
Ferramenta: process_insights.py
Processa o CSV bruto do Meta Ads e gera 3 saídas: Resumo, Campanhas, Diário.

Uso:
    python tools/process_insights.py --input output/meta_insights_campaign_2026-03-01_2026-03-31.csv
"""

import argparse
from pathlib import Path

import pandas as pd


def load_and_clean(input_path: Path) -> pd.DataFrame:
    """Lê o CSV bruto e retorna um DataFrame com tipos corretos."""
    if not input_path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {input_path}")

    df = pd.read_csv(input_path)

    if df.empty:
        raise ValueError(f"O arquivo está vazio: {input_path}")

    # Tipos numéricos
    for col in ["impressions", "clicks", "reach"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

    for col in ["spend", "ctr", "cpc", "cpm"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    # Datas
    for col in ["date_start", "date_end"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.date

    # Strings
    for col in ["campaign_name", "adset_name", "ad_name"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    return df


def _agg_metrics(df: pd.DataFrame) -> dict:
    """Calcula métricas agregadas recalculando CTR/CPC/CPM dos totais."""
    total_spend = df["spend"].sum() if "spend" in df.columns else 0.0
    total_impressions = df["impressions"].sum() if "impressions" in df.columns else 0
    total_clicks = df["clicks"].sum() if "clicks" in df.columns else 0
    total_reach = df["reach"].sum() if "reach" in df.columns else 0

    ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0.0
    cpc = (total_spend / total_clicks) if total_clicks > 0 else 0.0
    cpm = (total_spend / total_impressions * 1000) if total_impressions > 0 else 0.0

    return {
        "spend": round(total_spend, 2),
        "impressions": int(total_impressions),
        "clicks": int(total_clicks),
        "reach": int(total_reach),
        "ctr": round(ctr, 4),
        "cpc": round(cpc, 4),
        "cpm": round(cpm, 4),
    }


def build_resumo(df: pd.DataFrame) -> pd.DataFrame:
    """Retorna 1 linha com totais do período."""
    metrics = _agg_metrics(df)

    date_start = df["date_start"].min() if "date_start" in df.columns else None
    date_end = df["date_end"].max() if "date_end" in df.columns else None

    row = {"date_start": date_start, "date_end": date_end, **metrics}
    return pd.DataFrame([row])


def build_campanhas(df: pd.DataFrame) -> pd.DataFrame:
    """Performance agrupada por campanha, ordenada por spend desc."""
    if "campaign_name" not in df.columns:
        raise ValueError("Coluna 'campaign_name' não encontrada. Verifique o --level usado na extração.")

    groups = df.groupby("campaign_name", sort=False)
    rows = []
    for name, group in groups:
        metrics = _agg_metrics(group)
        rows.append({"campaign_name": name, **metrics})

    result = pd.DataFrame(rows)
    return result.sort_values("spend", ascending=False).reset_index(drop=True)


def build_diario(df: pd.DataFrame) -> pd.DataFrame:
    """Performance agrupada por dia, ordenada por data asc."""
    if "date_start" not in df.columns:
        raise ValueError("Coluna 'date_start' não encontrada no CSV.")

    groups = df.groupby("date_start", sort=False)
    rows = []
    for date, group in groups:
        metrics = _agg_metrics(group)
        rows.append({"date_start": date, **metrics})

    result = pd.DataFrame(rows)
    return result.sort_values("date_start", ascending=True).reset_index(drop=True)


def save_outputs(
    resumo: pd.DataFrame,
    campanhas: pd.DataFrame,
    diario: pd.DataFrame,
    output_dir: Path,
) -> dict:
    """Salva os 3 DataFrames como CSV e retorna mapa de nomes → paths."""
    output_dir.mkdir(parents=True, exist_ok=True)

    paths = {
        "resumo": output_dir / "resumo.csv",
        "campanhas": output_dir / "campanhas.csv",
        "diario": output_dir / "diario.csv",
    }

    resumo.to_csv(paths["resumo"], index=False, encoding="utf-8")
    campanhas.to_csv(paths["campanhas"], index=False, encoding="utf-8")
    diario.to_csv(paths["diario"], index=False, encoding="utf-8")

    for name, path in paths.items():
        rows = len(pd.read_csv(path))
        print(f"Salvo: {path} ({rows} linha(s))")

    return paths


def main():
    parser = argparse.ArgumentParser(description="Processa CSV bruto do Meta Ads")
    parser.add_argument("--input", required=True, help="Caminho do CSV bruto gerado por fetch_meta_insights.py")
    parser.add_argument("--output_dir", default="output", help="Diretório de saída (padrão: output/)")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output_dir)

    print(f"Carregando: {input_path}")
    df = load_and_clean(input_path)
    print(f"  {len(df)} linhas carregadas.")

    resumo = build_resumo(df)
    campanhas = build_campanhas(df)
    diario = build_diario(df)

    save_outputs(resumo, campanhas, diario, output_dir)


if __name__ == "__main__":
    main()
