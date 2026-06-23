"""
Gera análise semanal de performance por cliente e escreve
na planilha consolidada de insights.
"""

import os
import ast
import sys
import io
from collections import defaultdict
from datetime import datetime, date, timedelta
from dotenv import load_dotenv
import requests
sys.path.insert(0, os.path.dirname(__file__))
from sheets_client import write_tab as sheets_write_tab

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
load_dotenv()

# ─── Planilha consolidada de insights ─────────────────────────────────────────
INSIGHTS_SPREADSHEET_ID = "13En74sLC9cQvKFXSpiiytEaqsqff9-mKfHzvbgdmEQE"

# ─── Clientes e metas de CPL ──────────────────────────────────────────────────
CLIENTS = [
    {
        "name": "Clínica PRC",
        "tab":  "PRC",
        "account_id": "act_546529263459917",
        "cpl_targets": {"whatsapp": 20.0, "seguidores": 3.0},
    },
    {
        "name": "Qpharma",
        "tab":  "Qpharma",
        "account_id": "act_2255286214998670",
        "cpl_targets": {"whatsapp": 6.0, "seguidores": 3.0},
    },
    {
        "name": "Arquitetando Paladar",
        "tab":  "Arq. Paladar",
        "account_id": "act_2315650968737562",
        "cpl_targets": {"whatsapp": 15.0, "seguidores": 3.0},
    },
    {
        "name": "Dr Vinicius",
        "tab":  "Dr Vinicius",
        "account_id": "act_10205578707965893",
        "cpl_targets": {"whatsapp": 30.0, "lead_ads": None, "seguidores": 3.0},
    },
    {
        "name": "Elisa Lobo",
        "tab":  "Elisa Lobo",
        "account_id": "act_995746376256993",
        "cpl_targets": {"whatsapp": None, "seguidores": 3.0},
    },
]

# ─── Config ───────────────────────────────────────────────────────────────────
ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN")
API_VERSION  = "v19.0"
BASE_URL     = f"https://graph.facebook.com/{API_VERSION}"

CAMPAIGN_MAP = {
    "whatsapp":          "whatsapp",
    "wpp":               "whatsapp",
    "mensagem":          "whatsapp",
    "mensagens":         "whatsapp",
    "lead ads":          "lead_ads",
    "lead_ads":          "lead_ads",
    "formulário":        "lead_ads",
    "formulario":        "lead_ads",
    "e2-cap":            "whatsapp",
    "e1-dist":           "seguidores",
    "seguidor":          "seguidores",
    "tráfego":           "seguidores",
    "trafego":           "seguidores",
    "trfg":              "seguidores",
    "perfil":            "seguidores",
    "engj":              "seguidores",
    "engajamento":       "seguidores",
    "alcance":           "seguidores",
    "landing":           "landing_page",
    "padrão":            "whatsapp",
    "padrao":            "whatsapp",
    "[campanha de msg]": "whatsapp",
    "fevereiro":         "whatsapp",
    "visitas ao perfil": "seguidores",
}

CANAL_LABEL = {
    "whatsapp":     "WhatsApp",
    "lead_ads":     "Lead Ads",
    "landing_page": "Landing Page",
    "seguidores":   "Seguidores",
}

DIAS_PT = {0: "Segunda", 1: "Terça", 2: "Quarta", 3: "Quinta", 4: "Sexta", 5: "Sábado", 6: "Domingo"}


# ─── Meta API ─────────────────────────────────────────────────────────────────
def fetch_insights(account_id, date_start, date_end):
    url = f"{BASE_URL}/{account_id}/insights"
    params = {
        "access_token": ACCESS_TOKEN,
        "level": "campaign",
        "fields": "campaign_name,spend,impressions,clicks,reach,ctr,cpm,actions",
        "time_range": f'{{"since":"{date_start}","until":"{date_end}"}}',
        "time_increment": 1,
        "limit": 500,
    }
    results = []
    while url:
        r = requests.get(url, params=params)
        r.raise_for_status()
        data = r.json()
        results.extend(data.get("data", []))
        url = data.get("paging", {}).get("next")
        params = {}
    return results


# ─── Helpers ──────────────────────────────────────────────────────────────────
def get_action_value(actions, action_type):
    if not actions:
        return 0
    if isinstance(actions, str):
        try:
            actions = ast.literal_eval(actions)
        except Exception:
            return 0
    for a in actions:
        if a.get("action_type") == action_type:
            return int(float(a.get("value", 0)))
    return 0


def classify_campaign(name, actions):
    name_lower = name.lower()
    for keyword, canal in CAMPAIGN_MAP.items():
        if keyword in name_lower:
            return canal
    if get_action_value(actions, "onsite_conversion.messaging_conversation_started_7d") > 0:
        return "whatsapp"
    if get_action_value(actions, "onsite_conversion.lead_grouped") > 0:
        return "lead_ads"
    return "landing_page"


def get_leads(canal, actions):
    if canal == "whatsapp":
        return get_action_value(actions, "onsite_conversion.messaging_conversation_started_7d")
    elif canal == "lead_ads":
        return (get_action_value(actions, "offsite_complete_registration_add_meta_leads")
                or get_action_value(actions, "lead")
                or get_action_value(actions, "onsite_conversion.lead_grouped"))
    return 0


def aggregate(rows):
    """Agrega métricas por data e canal."""
    by_date = defaultdict(lambda: defaultdict(lambda: {
        "spend": 0.0, "leads": 0, "impressions": 0, "clicks": 0, "reach": 0
    }))
    for row in rows:
        dt      = row["date_start"]
        name    = row.get("campaign_name", "")
        actions = row.get("actions", [])
        canal   = classify_campaign(name, actions)
        d       = by_date[dt][canal]
        d["spend"]       += float(row.get("spend", 0) or 0)
        d["leads"]       += get_leads(canal, actions)
        d["impressions"] += int(row.get("impressions", 0) or 0)
        d["clicks"]      += int(row.get("clicks", 0) or 0)
        d["reach"]       += int(row.get("reach", 0) or 0)
    return by_date


def sum_period(by_date, date_start, date_end):
    """Soma métricas de um período."""
    totals = defaultdict(lambda: {"spend": 0.0, "leads": 0, "impressions": 0, "clicks": 0, "reach": 0})
    start = datetime.strptime(date_start, "%Y-%m-%d").date()
    end   = datetime.strptime(date_end,   "%Y-%m-%d").date()
    for dt_str, canais in by_date.items():
        dt = datetime.strptime(dt_str, "%Y-%m-%d").date()
        if start <= dt <= end:
            for canal, m in canais.items():
                for k, v in m.items():
                    totals[canal][k] += v
    return totals


def cpl(spend, leads):
    return spend / leads if leads > 0 else None


def fmt_brl(v):
    return f"R$ {v:.2f}".replace(".", ",") if v is not None else "—"


def fmt_pct(v):
    return f"{v:.1f}%" if v is not None else "—"


def status_icon(val, target):
    if target is None or val is None:
        return "—"
    if val <= target:
        return "✅ OK"
    if val <= target * 1.2:
        return "⚠️ ATENÇÃO"
    return "🔴 ACIMA"


# ─── Google Sheets ────────────────────────────────────────────────────────────
def write_tab(tab_name, rows):
    sheets_write_tab(INSIGHTS_SPREADSHEET_ID, tab_name, rows)
    return True


# ─── Geração de insights por cliente ──────────────────────────────────────────
def build_client_report(client, today):
    name     = client["name"]
    targets  = client["cpl_targets"]

    # Períodos
    week_end   = today - timedelta(days=1)              # ontem
    week_start = week_end - timedelta(days=6)           # 7 dias atrás
    prev_end   = week_start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=6)
    month_start = today.replace(day=1)

    # Busca dados (mês todo para ter histórico de dias)
    rows_all = fetch_insights(
        client["account_id"],
        month_start.strftime("%Y-%m-%d"),
        today.strftime("%Y-%m-%d"),
    )

    by_date   = aggregate(rows_all)
    curr_week = sum_period(by_date, week_start.strftime("%Y-%m-%d"), week_end.strftime("%Y-%m-%d"))
    prev_week = sum_period(by_date, prev_start.strftime("%Y-%m-%d"), prev_end.strftime("%Y-%m-%d"))

    # ── Monta linhas da planilha ──────────────────────────────────────────────
    out = []
    out.append([f"💡 Insights — {name}",  f"Gerado em {today.strftime('%d/%m/%Y')}"])
    out.append([""])

    # ── Performance da semana ─────────────────────────────────────────────────
    out.append(["📊 PERFORMANCE DA SEMANA",
                f"{week_start.strftime('%d/%m')} a {week_end.strftime('%d/%m')}"])
    out.append(["Canal", "Invest.", "Leads/Seguid.", "CPL/CPS",
                "Meta", "Status", "vs Semana Anterior"])

    canais_ativos = [c for c in curr_week if curr_week[c]["spend"] > 0]
    if not canais_ativos:
        out.append(["Sem dados na semana", "", "", "", "", "", ""])
    else:
        for canal in ["whatsapp", "lead_ads", "seguidores", "landing_page"]:
            m = curr_week.get(canal)
            if not m or m["spend"] == 0:
                continue
            p        = prev_week.get(canal, {"spend": 0, "leads": 0})
            cpl_curr = cpl(m["spend"], m["leads"])
            cpl_prev = cpl(p["spend"], p["leads"])
            target   = targets.get(canal)
            label    = CANAL_LABEL.get(canal, canal)

            # Variação semana anterior
            if cpl_curr is not None and cpl_prev is not None and cpl_prev > 0:
                var = ((cpl_curr - cpl_prev) / cpl_prev) * 100
                var_txt = f"{'▲' if var > 0 else '▼'} {abs(var):.1f}%"
            else:
                var_txt = "—"

            out.append([
                label,
                fmt_brl(m["spend"]),
                str(m["leads"]),
                fmt_brl(cpl_curr),
                fmt_brl(target) if target else "Média",
                status_icon(cpl_curr, target),
                var_txt,
            ])

    out.append([""])

    # ── Alertas ───────────────────────────────────────────────────────────────
    alertas = []
    for canal in ["whatsapp", "lead_ads", "seguidores"]:
        m      = curr_week.get(canal, {"spend": 0, "leads": 0})
        target = targets.get(canal)
        if m["spend"] == 0:
            continue
        cpl_v = cpl(m["spend"], m["leads"])
        label = CANAL_LABEL.get(canal, canal)
        if cpl_v is not None and target is not None and cpl_v > target * 1.2:
            alertas.append([f"🔴 CPL {label} em {fmt_brl(cpl_v)} — meta é {fmt_brl(target)}. Revisar segmentação ou criativo."])
        elif cpl_v is not None and target is not None and cpl_v > target:
            alertas.append([f"⚠️ CPL {label} em {fmt_brl(cpl_v)} — ligeiramente acima da meta ({fmt_brl(target)}). Monitorar."])
        if m["leads"] == 0 and m["spend"] > 0:
            alertas.append([f"🔴 {label} com gasto de {fmt_brl(m['spend'])} e zero conversões na semana. Verificar urgente."])

    # CTR baixo (abaixo de 1%)
    total_impressions = sum(curr_week.get(c, {}).get("impressions", 0) for c in curr_week)
    total_clicks      = sum(curr_week.get(c, {}).get("clicks", 0) for c in curr_week)
    if total_impressions > 0:
        ctr_overall = (total_clicks / total_impressions) * 100
        if ctr_overall < 1.0:
            alertas.append([f"⚠️ CTR geral em {ctr_overall:.2f}% (abaixo de 1%). Criativos podem estar cansados."])

    out.append(["⚠️ ALERTAS"])
    if alertas:
        out.extend(alertas)
    else:
        out.append(["✅ Nenhum alerta — tudo dentro das metas!"])

    out.append([""])

    # ── Melhor e pior dia da semana ───────────────────────────────────────────
    out.append(["📅 MELHOR E PIOR DIA (últimos 7 dias)"])
    out.append(["Dia", "Invest. Total", "Leads Total", "CPL Médio"])

    dias = []
    for dt_str, canais in by_date.items():
        dt = datetime.strptime(dt_str, "%Y-%m-%d").date()
        if week_start <= dt <= week_end:
            total_spend = sum(canais[c]["spend"] for c in canais)
            total_leads = sum(canais[c]["leads"] for c in canais if c != "seguidores")
            dias.append((dt, total_spend, total_leads))

    dias.sort(key=lambda x: x[0])
    if dias:
        for dt, spend, leads in dias:
            out.append([
                DIAS_PT[dt.weekday()],
                fmt_brl(spend),
                str(leads),
                fmt_brl(cpl(spend, leads)),
            ])

        melhor = min(dias, key=lambda x: cpl(x[1], x[2]) or 9999)
        pior   = max(dias, key=lambda x: cpl(x[1], x[2]) or 0)
        out.append([""])
        out.append([f"🏆 Melhor dia: {DIAS_PT[melhor[0].weekday()]} — CPL {fmt_brl(cpl(melhor[1], melhor[2]))}"])
        out.append([f"📉 Pior dia:   {DIAS_PT[pior[0].weekday()]} — CPL {fmt_brl(cpl(pior[1], pior[2]))}"])

    out.append([""])

    # ── Sugestões ─────────────────────────────────────────────────────────────
    sugestoes = []
    for canal in ["whatsapp", "lead_ads", "seguidores"]:
        m      = curr_week.get(canal, {"spend": 0, "leads": 0})
        p      = prev_week.get(canal, {"spend": 0, "leads": 0})
        target = targets.get(canal)
        label  = CANAL_LABEL.get(canal, canal)
        if m["spend"] == 0:
            continue
        cpl_c = cpl(m["spend"], m["leads"])
        cpl_p = cpl(p["spend"], p["leads"])

        # CPL caindo e abaixo da meta → escalar
        if cpl_c and target and cpl_c <= target * 0.8 and cpl_p and cpl_c < cpl_p:
            sugestoes.append([f"💡 {label} com CPL baixo e melhorando. Bom momento para aumentar o orçamento."])
        # CPL subindo acima da meta → revisar
        if cpl_c and target and cpl_c > target and cpl_p and cpl_c > cpl_p:
            sugestoes.append([f"💡 {label} com CPL subindo. Testar novo criativo ou revisar público-alvo."])
        # Zero leads com gasto
        if m["leads"] == 0 and m["spend"] > 10:
            sugestoes.append([f"💡 {label} sem conversões. Verificar se o botão/formulário está funcionando."])

    if total_impressions > 0 and ctr_overall < 1.0:
        sugestoes.append(["💡 CTR baixo no geral. Considere renovar os criativos (imagens/vídeos) das campanhas."])

    out.append(["💡 SUGESTÕES"])
    if sugestoes:
        out.extend(sugestoes)
    else:
        out.append(["✅ Campanhas estáveis. Acompanhe a frequência e renove criativos preventivamente."])

    out.append([""])
    out.append([f"📈 ACUMULADO DO MÊS ({month_start.strftime('%d/%m')} a {today.strftime('%d/%m')})"])
    month_data = sum_period(by_date, month_start.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d"))
    out.append(["Canal", "Invest. Total", "Leads Total", "CPL Médio"])
    for canal in ["whatsapp", "lead_ads", "seguidores"]:
        m = month_data.get(canal)
        if not m or m["spend"] == 0:
            continue
        out.append([CANAL_LABEL.get(canal, canal), fmt_brl(m["spend"]), str(m["leads"]), fmt_brl(cpl(m["spend"], m["leads"]))])

    return out


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    if not ACCESS_TOKEN:
        raise EnvironmentError("META_ACCESS_TOKEN não encontrado no .env")

    today = date.today()
    print(f"=== Gerando Insights — {today.strftime('%d/%m/%Y')} ===\n")

    for client in CLIENTS:
        name = client["name"]
        tab  = client["tab"]
        print(f"  Processando {name}...", end=" ")
        try:
            rows = build_client_report(client, today)
            ok   = write_tab(tab, rows)
            print("✓" if ok else "ERRO ao escrever na planilha")
        except Exception as e:
            print(f"ERRO: {e}")

    print(f"\nConcluído! Planilha: https://docs.google.com/spreadsheets/d/{INSIGHTS_SPREADSHEET_ID}")


if __name__ == "__main__":
    main()
