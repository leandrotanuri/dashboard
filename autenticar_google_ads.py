"""
Autenticação Google Ads API via OAuth — gera o refresh_token com escopo adwords.
Usa apenas requests + módulos nativos do Python (mesmo padrão do autenticar_google.py).

Execute UMA VEZ, logando com o e-mail Google que tem acesso às contas de anúncio:
    python autenticar_google_ads.py

Gera token_google_ads.json com o refresh_token usado por tools/fetch_google_ads.py.
"""

import json
import time
import webbrowser
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
import requests

CREDS_FILE = Path(__file__).parent / "credentials.json"
TOKEN_FILE = Path(__file__).parent / "token_google_ads.json"
SCOPE      = "https://www.googleapis.com/auth/adwords"
REDIRECT   = "http://localhost:8765"

if not CREDS_FILE.exists():
    print("ERRO: credentials.json não encontrado.")
    raise SystemExit(1)

creds = json.loads(CREDS_FILE.read_text())
cfg   = creds.get("web") or creds.get("installed") or {}
CLIENT_ID     = cfg["client_id"]
CLIENT_SECRET = cfg["client_secret"]
AUTH_URI      = cfg.get("auth_uri",  "https://accounts.google.com/o/oauth2/auth")
TOKEN_URI     = cfg.get("token_uri", "https://oauth2.googleapis.com/token")

# ── Captura o código de autorização via servidor local ────────────────────────
auth_code = None


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        auth_code = params.get("code", [None])[0]
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"<h2>Autenticado! Pode fechar esta aba.</h2>")

    def log_message(self, *args):
        pass


# ── Abre o navegador com a URL de auth ────────────────────────────────────────
params = urllib.parse.urlencode({
    "client_id":     CLIENT_ID,
    "redirect_uri":  REDIRECT,
    "response_type": "code",
    "scope":         SCOPE,
    "access_type":   "offline",
    "prompt":        "consent",
})
url = f"{AUTH_URI}?{params}"
print("Abrindo navegador para autenticação Google Ads...")
print("IMPORTANTE: logue com o e-mail que tem acesso às contas de anúncio.")
webbrowser.open(url)

# ── Aguarda o redirecionamento ────────────────────────────────────────────────
server = HTTPServer(("localhost", 8765), Handler)
server.handle_request()

if not auth_code:
    print("ERRO: código de autorização não recebido.")
    raise SystemExit(1)

# ── Troca o código por tokens ─────────────────────────────────────────────────
r = requests.post(TOKEN_URI, data={
    "code":          auth_code,
    "client_id":     CLIENT_ID,
    "client_secret": CLIENT_SECRET,
    "redirect_uri":  REDIRECT,
    "grant_type":    "authorization_code",
})
r.raise_for_status()
token_data = r.json()
token_data["client_id"]     = CLIENT_ID
token_data["client_secret"] = CLIENT_SECRET
token_data["token_uri"]     = TOKEN_URI
token_data["expires_at"]    = time.time() + token_data.get("expires_in", 3600)

TOKEN_FILE.write_text(json.dumps(token_data, indent=2))
print("\nAutenticado com sucesso!")
print(f"Token salvo em: {TOKEN_FILE}")
if "refresh_token" not in token_data:
    print("AVISO: refresh_token não veio. Revogue o acesso do app na conta Google e rode de novo.")
