import sys, json, time, requests
sys.stdout.reconfigure(encoding='utf-8')

PPTX_PATH = r"C:\Users\leand\Downloads\MetaAds Relatórios\output\Dr_Vinicius_Reuniao_Jun2026.pptx"

# Token
with open(r"C:\Users\leand\Downloads\MetaAds Relatórios\token.json") as f:
    t = json.load(f)

r = requests.post(t['token_uri'], data={
    'client_id': t['client_id'], 'client_secret': t['client_secret'],
    'refresh_token': t['refresh_token'], 'grant_type': 'refresh_token',
})
r.raise_for_status()
token = r.json()['access_token']

# Upload para Drive convertendo para Google Slides
print("Fazendo upload para Google Slides...")
with open(PPTX_PATH, 'rb') as f:
    data = f.read()

metadata = {
    "name": "Dr. Vinicius — Reunião Junho 2026",
    "mimeType": "application/vnd.google-apps.presentation",
}

resp = requests.post(
    "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart",
    headers={"Authorization": f"Bearer {token}"},
    files={
        "metadata": (None, json.dumps(metadata), "application/json; charset=UTF-8"),
        "file": ("presentation.pptx", data, "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
    }
)
resp.raise_for_status()
file_id = resp.json()["id"]
link = f"https://docs.google.com/presentation/d/{file_id}/edit"
print(f"\nLink: {link}")
