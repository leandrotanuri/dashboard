"""
Ferramenta: analyze_dr_vinicius_creatives.py
Agrega insights de anúncios (nível ad) por criativo e compara dois períodos,
destacando os melhores/piores criativos e o que mudou entre os meses.
"""

import ast
import csv
import argparse
from collections import defaultdict
from pathlib import Path

RESULT_ACTION_TYPES = [
    "onsite_conversion.messaging_conversation_started_7d",
    "onsite_conversion.lead",
    "lead",
]


def parse_actions(raw):
    if not raw:
        return {}
    try:
        actions = ast.literal_eval(raw)
    except Exception:
        return {}
    out = {}
    for a in actions:
        out[a["action_type"]] = float(a.get("value", 0))
    return out


def load_and_aggregate(csv_path: Path):
    agg = defaultdict(lambda: {
        "campaign_name": set(), "adset_name": set(),
        "impressions": 0.0, "clicks": 0.0, "spend": 0.0, "reach": 0.0,
        "conversas": 0.0, "leads": 0.0,
    })
    with open(csv_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            ad = row["ad_name"]
            a = agg[ad]
            a["campaign_name"].add(row["campaign_name"])
            a["adset_name"].add(row["adset_name"])
            a["impressions"] += float(row["impressions"] or 0)
            a["clicks"] += float(row["clicks"] or 0)
            a["spend"] += float(row["spend"] or 0)
            a["reach"] = max(a["reach"], float(row["reach"] or 0))
            acts = parse_actions(row["actions"])
            a["conversas"] += acts.get("onsite_conversion.messaging_conversation_started_7d", 0)
            a["leads"] += acts.get("onsite_conversion.lead", 0) + acts.get("lead", 0)
    return agg


def summarize(agg):
    rows = []
    total_spend = total_conv = total_leads = total_impr = total_clicks = 0.0
    for ad, a in agg.items():
        ctr = (a["clicks"] / a["impressions"] * 100) if a["impressions"] else 0
        cpm = (a["spend"] / a["impressions"] * 1000) if a["impressions"] else 0
        cpc = (a["spend"] / a["clicks"]) if a["clicks"] else None
        cost_per_conv = (a["spend"] / a["conversas"]) if a["conversas"] else None
        rows.append({
            "ad_name": ad,
            "campaign_name": " / ".join(sorted(a["campaign_name"]))[:80],
            "spend": a["spend"], "impressions": a["impressions"], "clicks": a["clicks"],
            "ctr": ctr, "cpm": cpm, "cpc": cpc,
            "conversas": a["conversas"], "leads": a["leads"],
            "cost_per_conv": cost_per_conv,
        })
        total_spend += a["spend"]
        total_conv += a["conversas"]
        total_leads += a["leads"]
        total_impr += a["impressions"]
        total_clicks += a["clicks"]
    totals = {
        "spend": total_spend, "conversas": total_conv, "leads": total_leads,
        "impressions": total_impr, "clicks": total_clicks,
        "ctr": (total_clicks / total_impr * 100) if total_impr else 0,
        "cost_per_conv": (total_spend / total_conv) if total_conv else None,
    }
    return rows, totals


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--may_csv", required=True)
    p.add_argument("--june_csv", required=True)
    p.add_argument("--output", default="output/dr_vinicius/relatorio_maio_junho.md")
    args = p.parse_args()

    may_agg = load_and_aggregate(Path(args.may_csv))
    jun_agg = load_and_aggregate(Path(args.june_csv))
    may_rows, may_tot = summarize(may_agg)
    jun_rows, jun_tot = summarize(jun_agg)

    may_rows.sort(key=lambda r: (r["cost_per_conv"] is None, r["cost_per_conv"] or 0))
    jun_rows.sort(key=lambda r: (r["cost_per_conv"] is None, r["cost_per_conv"] or 0))

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    lines.append("# Dr. Vinicius — Criativos Maio x Junho 2026\n")

    lines.append("## Totais do período\n")
    lines.append("| Métrica | Maio | Junho | Variação |")
    lines.append("|---|---|---|---|")
    def var(a, b):
        if a == 0:
            return "-"
        return f"{(b-a)/a*100:+.1f}%"
    lines.append(f"| Investimento | R$ {may_tot['spend']:.2f} | R$ {jun_tot['spend']:.2f} | {var(may_tot['spend'], jun_tot['spend'])} |")
    lines.append(f"| Impressões | {may_tot['impressions']:.0f} | {jun_tot['impressions']:.0f} | {var(may_tot['impressions'], jun_tot['impressions'])} |")
    lines.append(f"| Cliques | {may_tot['clicks']:.0f} | {jun_tot['clicks']:.0f} | {var(may_tot['clicks'], jun_tot['clicks'])} |")
    lines.append(f"| CTR médio | {may_tot['ctr']:.2f}% | {jun_tot['ctr']:.2f}% | {var(may_tot['ctr'], jun_tot['ctr'])} |")
    lines.append(f"| Conversas iniciadas (WPP) | {may_tot['conversas']:.0f} | {jun_tot['conversas']:.0f} | {var(may_tot['conversas'], jun_tot['conversas'])} |")
    lines.append(f"| Leads | {may_tot['leads']:.0f} | {jun_tot['leads']:.0f} | {var(may_tot['leads'], jun_tot['leads'])} |")
    mcpc = may_tot['cost_per_conv'] or 0
    jcpc = jun_tot['cost_per_conv'] or 0
    lines.append(f"| Custo por conversa | R$ {mcpc:.2f} | R$ {jcpc:.2f} | {var(mcpc, jcpc)} |")
    lines.append("")

    for label, rows in [("Maio", may_rows), ("Junho", jun_rows)]:
        lines.append(f"## Ranking de criativos — {label} (por custo/conversa, menor = melhor)\n")
        lines.append("| Criativo | Campanha | Invest. | Impr. | CTR | Conversas | Leads | Custo/Conversa |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for r in rows:
            cpc_str = f"R$ {r['cost_per_conv']:.2f}" if r["cost_per_conv"] else "-"
            lines.append(
                f"| {r['ad_name']} | {r['campaign_name']} | R$ {r['spend']:.2f} | {r['impressions']:.0f} | "
                f"{r['ctr']:.2f}% | {r['conversas']:.0f} | {r['leads']:.0f} | {cpc_str} |"
            )
        lines.append("")

    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"Relatório salvo em: {out}")


if __name__ == "__main__":
    main()
