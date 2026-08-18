"""
Faz upload do Dr_Vinicius_Apresentacao.pptx para o Google Drive
e converte automaticamente para Google Slides.
Imprime o link direto para edição.
"""

import io
import json
import time
import sys
import os
from pathlib import Path
import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

TOKEN_FILE = Path(__file__).parent.parent / "token.json"
_default   = Path(__file__).parent.parent / "output" / "Dr_Vinicius_Apresentacao.pptx"
PPTX_FILE  = Path(sys.argv[1]) if len(sys.argv) > 1 else _default

DRIVE_UPLOAD_URL = "https://www.googleapis.com/upload/drive/v3/files"
DRIVE_FILES_URL  = "https://www.googleapis.com/drive/v3/files"


def get_access_token():
    if not TOKEN_FILE.exists():
        print("ERRO: token.json não encontrado. Execute autenticar_google.py primeiro.")
        sys.exit(1)
    token = json.loads(TOKEN_FILE.read_text())
    if time.time() >= token.get("expires_at", 0) - 300:
        r = requests.post(token["token_uri"], data={
            "client_id":     token["client_id"],
            "client_secret": token["client_secret"],
            "refresh_token": token["refresh_token"],
            "grant_type":    "refresh_token",
        })
        r.raise_for_status()
        new = r.json()
        token["access_token"] = new["access_token"]
        token["expires_at"]   = time.time() + new.get("expires_in", 3600)
        TOKEN_FILE.write_text(json.dumps(token, indent=2))
    return token["access_token"]


def upload_and_convert(token, pptx_path):
    """Faz upload do .pptx e converte para Google Slides em uma etapa."""
    metadata = json.dumps({
        "name":     "Dr. Vinicius — Resultados & Estratégia 2025–2026",
        "mimeType": "application/vnd.google-apps.presentation",
    }).encode("utf-8")

    boundary = "==boundary=="
    body = (
        f"--{boundary}\r\n"
        f"Content-Type: application/json; charset=UTF-8\r\n\r\n"
    ).encode() + metadata + (
        f"\r\n--{boundary}\r\n"
        "Content-Type: application/vnd.openxmlformats-officedocument.presentationml.presentation\r\n\r\n"
    ).encode() + pptx_path.read_bytes() + f"\r\n--{boundary}--".encode()

    r = requests.post(
        f"{DRIVE_UPLOAD_URL}?uploadType=multipart",
        headers={
            "Authorization":  f"Bearer {token}",
            "Content-Type":   f"multipart/related; boundary={boundary}",
            "Content-Length": str(len(body)),
        },
        data=body,
    )
    r.raise_for_status()
    return r.json()["id"]


def main():
    if not PPTX_FILE.exists():
        print(f"ERRO: arquivo não encontrado: {PPTX_FILE}")
        sys.exit(1)

    print("Autenticando com Google...")
    token = get_access_token()

    # Verificar se o scope drive.file está disponível
    # (só saberemos na hora do upload — se falhar, orientar re-autenticação)

    print(f"Fazendo upload de {PPTX_FILE.name} ({PPTX_FILE.stat().st_size // 1024} KB)...")
    try:
        file_id = upload_and_convert(token, PPTX_FILE)
    except requests.HTTPError as e:
        if e.response.status_code in (401, 403):
            print("\n⚠️  Permissão negada. Você precisa re-autenticar com o novo escopo.")
            print("Execute: python autenticar_google.py")
            sys.exit(1)
        raise

    link = f"https://docs.google.com/presentation/d/{file_id}/edit"
    print(f"\n✅ Apresentação criada no Google Slides!")
    print(f"🔗 Link: {link}")
    print(f"\nCompartilhe este link com o Dr. Vinicius ou abra no navegador.")


if __name__ == "__main__":
    main()
