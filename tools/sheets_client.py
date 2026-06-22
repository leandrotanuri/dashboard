"""
Cliente Google Sheets sem DLLs — usa apenas requests.
Lê/renova token.json automaticamente.
"""

import json
import time
import urllib.parse
from pathlib import Path
import requests as req

TOKEN_FILE = Path(__file__).parent.parent / "token.json"
SHEETS_URL = "https://sheets.googleapis.com/v4/spreadsheets"


_SECRETS_TOML = Path(__file__).parent.parent / ".streamlit" / "secrets.toml"

# Fonte do token: "file" (token.json local) ou "streamlit" (st.secrets)
_token_source = "file"


def _load_token() -> dict:
    global _token_source
    # Prefere token.json local (mais atualizado e tem refresh_token válido)
    if TOKEN_FILE.exists():
        _token_source = "file"
        return json.loads(TOKEN_FILE.read_text())
    # Fallback: Streamlit Cloud (TOKEN_FILE não existe no ambiente cloud)
    try:
        import streamlit as st
        if "google_token" in st.secrets:
            _token_source = "streamlit"
            token = dict(st.secrets["google_token"])
            # No Cloud não dá pra salvar de volta → força refresh a cada sessão
            token["expires_at"] = 0
            return token
    except Exception:
        pass
    raise FileNotFoundError(
        "token.json não encontrado. Execute autenticar_google.py primeiro."
    )


def _do_refresh(token: dict) -> dict:
    """Troca refresh_token por um novo access_token e persiste onde possível."""
    r = req.post(token["token_uri"], data={
        "client_id":     token["client_id"],
        "client_secret": token["client_secret"],
        "refresh_token": token["refresh_token"],
        "grant_type":    "refresh_token",
    })
    r.raise_for_status()
    new = r.json()
    token["access_token"] = new["access_token"]
    token["expires_at"]   = time.time() + new.get("expires_in", 3600)

    # Só persiste quando rodando localmente (Cloud tem filesystem read-only)
    if _token_source == "file":
        if TOKEN_FILE.exists():
            TOKEN_FILE.write_text(json.dumps(token, indent=2))
        if _SECRETS_TOML.exists():
            _update_secrets_toml(token)

    return token


def _update_secrets_toml(token: dict):
    """Atualiza access_token e expires_at no secrets.toml local sem mexer no resto."""
    text = _SECRETS_TOML.read_text(encoding="utf-8")
    lines = text.splitlines()
    new_lines = []
    for line in lines:
        if line.startswith("access_token"):
            new_lines.append(f'access_token = "{token["access_token"]}"')
        elif line.startswith("expires_at"):
            new_lines.append(f'expires_at = {token["expires_at"]}')
        else:
            new_lines.append(line)
    # Garante que access_token existe na seção google_token
    result = "\n".join(new_lines)
    if "access_token" not in result.split("[google_token]", 1)[-1]:
        result = result.replace(
            "[google_token]",
            f'[google_token]\naccess_token = "{token["access_token"]}"',
        )
    _SECRETS_TOML.write_text(result + "\n", encoding="utf-8")


def _get_access_token() -> str:
    # Tenta usar token cacheado na sessão Streamlit (evita refresh a cada widget)
    try:
        import streamlit as st
        cached = st.session_state.get("_google_access_token")
        exp    = st.session_state.get("_google_token_exp", 0)
        if cached and time.time() < exp - 300:
            return cached
    except Exception:
        pass

    token = _load_token()

    # Renova se expirado ou vem do Streamlit (expires_at forçado a 0)
    if time.time() >= token.get("expires_at", 0) - 300:
        token = _do_refresh(token)

    # Salva na sessão Streamlit para reutilizar durante a mesma sessão
    try:
        import streamlit as st
        st.session_state["_google_access_token"] = token["access_token"]
        st.session_state["_google_token_exp"]    = token["expires_at"]
    except Exception:
        pass

    return token["access_token"]


def batch_update(spreadsheet_id: str, data: list) -> None:
    """
    data = lista de dicts com 'range', 'majorDimension', 'values'
    Nunca toca colunas de fórmula — só os ranges passados.
    """
    token = _get_access_token()
    url   = f"{SHEETS_URL}/{spreadsheet_id}/values:batchUpdate"
    body  = {"data": data, "valueInputOption": "USER_ENTERED"}
    r = req.post(url, json=body, headers={"Authorization": f"Bearer {token}"})
    r.raise_for_status()


def update_range(spreadsheet_id: str, range_: str, values: list) -> None:
    token = _get_access_token()
    url   = f"{SHEETS_URL}/{spreadsheet_id}/values/{urllib.parse.quote(range_, safe='')}?valueInputOption=USER_ENTERED"
    r = req.put(url, json={"values": values}, headers={"Authorization": f"Bearer {token}"})
    r.raise_for_status()


def clear_range(spreadsheet_id: str, range_: str) -> None:
    token = _get_access_token()
    url   = f"{SHEETS_URL}/{spreadsheet_id}/values/{urllib.parse.quote(range_, safe='')}:clear"
    r = req.post(url, headers={"Authorization": f"Bearer {token}"})
    r.raise_for_status()


def read_range(spreadsheet_id: str, range_: str) -> list:
    """Retorna lista de linhas [[v1, v2, ...], ...] para o range informado."""
    token = _get_access_token()
    url = f"{SHEETS_URL}/{spreadsheet_id}/values/{urllib.parse.quote(range_, safe='')}"
    r = req.get(url, headers={"Authorization": f"Bearer {token}"})
    r.raise_for_status()
    return r.json().get("values", [])


def get_sheet_titles(spreadsheet_id: str) -> list:
    token = _get_access_token()
    url   = f"{SHEETS_URL}/{spreadsheet_id}?fields=sheets.properties.title"
    r = req.get(url, headers={"Authorization": f"Bearer {token}"})
    r.raise_for_status()
    return [s["properties"]["title"] for s in r.json().get("sheets", [])]


def ensure_tab(spreadsheet_id: str, tab_name: str) -> None:
    titles = get_sheet_titles(spreadsheet_id)
    if tab_name not in titles:
        token = _get_access_token()
        url   = f"{SHEETS_URL}/{spreadsheet_id}:batchUpdate"
        body  = {"requests": [{"addSheet": {"properties": {"title": tab_name}}}]}
        r = req.post(url, json=body, headers={"Authorization": f"Bearer {token}"})
        r.raise_for_status()


def write_tab(spreadsheet_id: str, tab_name: str, rows: list) -> None:
    """Sobrescreve uma aba inteira com os dados passados."""
    ensure_tab(spreadsheet_id, tab_name)
    clear_range(spreadsheet_id, tab_name)
    token = _get_access_token()
    range_ = urllib.parse.quote(f"{tab_name}!A1", safe="")
    url    = f"{SHEETS_URL}/{spreadsheet_id}/values/{range_}?valueInputOption=USER_ENTERED"
    r = req.put(url, json={"values": rows}, headers={"Authorization": f"Bearer {token}"})
    r.raise_for_status()
