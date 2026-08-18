import sys, os, requests
from dotenv import load_dotenv
sys.stdout.reconfigure(encoding='utf-8')
load_dotenv()

TOKEN      = os.getenv("META_ACCESS_TOKEN")
ACCOUNT_ID = "act_10205578707965893"
API        = "https://graph.facebook.com/v19.0"

def fetch(date_start, date_end):
    url = f"{API}/{ACCOUNT_ID}/insights"
    params = {
        "access_token": TOKEN,
        "level": "campaign",
        "fields": "campaign_name,spend,actions",
        "time_range": f'{{"since":"{date_start}","until":"{date_end}"}}',
        "time_increment": 1,
        "limit": 500,
    }
    rows = []
    while url:
        r = requests.get(url, params=params)
        r.raise_for_status()
        d = r.json()
        rows.extend(d.get("data", []))
        url = d.get("paging", {}).get("next")
        params = {}
    return rows

def get_msgs(actions):
    if not actions:
        return 0
    for a in actions:
        if a.get("action_type") == "onsite_conversion.messaging_conversation_started_7d":
            return int(float(a.get("value", 0)))
    return 0

WPP_KW = ["whatsapp","wpp","mensagem","mensagens","padrão","padrao","[campanha de msg]","fevereiro"]

def is_wpp(name):
    n = name.lower()
    return any(k in n for k in WPP_KW)

for label, ds, de in [("ABRIL", "2026-04-01", "2026-04-30"), ("MAIO", "2026-05-01", "2026-05-31")]:
    rows = fetch(ds, de)
    wpp = [r for r in rows if is_wpp(r.get("campaign_name",""))]

    # agrupa por campanha
    by_camp = {}
    for r in wpp:
        name  = r.get("campaign_name","")
        spend = float(r.get("spend", 0) or 0)
        msgs  = get_msgs(r.get("actions"))
        if name not in by_camp:
            by_camp[name] = {"spend": 0, "leads": 0}
        by_camp[name]["spend"]  += spend
        by_camp[name]["leads"]  += msgs

    total_spend = sum(v["spend"] for v in by_camp.values())
    total_leads = sum(v["leads"] for v in by_camp.values())

    print(f"\n{'='*60}")
    print(f"  {label}  |  Total invest: R$ {total_spend:.2f}  |  Leads: {total_leads}")
    print(f"{'='*60}")
    for name, v in sorted(by_camp.items(), key=lambda x: -x[1]["spend"]):
        cpl = v["spend"]/v["leads"] if v["leads"] > 0 else 0
        cpl_str = f"CPL R${cpl:.2f}" if cpl else "sem leads"
        print(f"  {name[:55]:<55} | R${v['spend']:>8.2f} | {v['leads']:>4} leads | {cpl_str}")
