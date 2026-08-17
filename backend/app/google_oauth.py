"""Google OAuth helpers.

Environment values are read directly from the process as well as the Pydantic
settings object so Railway runtime variables are honored even when the settings
singleton was initialized before an environment refresh.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from urllib.parse import urlencode

import httpx
from app.config import settings

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPES = "https://www.googleapis.com/auth/webmasters.readonly https://www.googleapis.com/auth/analytics.readonly"


def _env(name: str) -> str:
    value = (os.environ.get(name) or "").strip()
    if value:
        return value
    try:
        return str(getattr(settings(), name, "") or "").strip()
    except Exception:
        return ""


def _state_key() -> bytes:
    value = _env("GOOGLE_OAUTH_STATE_SECRET") or _env("ENCRYPTION_KEY") or _env("GOOGLE_CLIENT_SECRET")
    if not value:
        raise RuntimeError("Google OAuth state secret is not configured")
    return value.encode("utf-8")


def make_state(project_id: int) -> str:
    payload = {
        "pid": project_id,
        "nonce": secrets.token_urlsafe(18),
        "exp": int(time.time()) + 600,
    }
    raw = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    ).decode().rstrip("=")
    sig = hmac.new(_state_key(), raw.encode(), hashlib.sha256).hexdigest()
    return f"{raw}.{sig}"


def read_state(state: str):
    try:
        raw, sig = state.rsplit(".", 1)
        expected = hmac.new(_state_key(), raw.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            raise ValueError("invalid_state")
        encoded = raw + "=" * (-len(raw) % 4)
        payload = json.loads(base64.urlsafe_b64decode(encoded))
        if int(payload.get("exp", 0)) < int(time.time()):
            raise ValueError("expired_state")
        return payload
    except Exception as exc:
        raise ValueError("invalid_state") from exc


def authorization_url(project_id: int):
    client_id = _env("GOOGLE_CLIENT_ID")
    redirect_uri = _env("GOOGLE_OAUTH_REDIRECT_URI")
    client_secret = _env("GOOGLE_CLIENT_SECRET")
    missing = []
    if not client_id:
        missing.append("GOOGLE_CLIENT_ID")
    if not redirect_uri:
        missing.append("GOOGLE_OAUTH_REDIRECT_URI")
    if not client_secret:
        missing.append("GOOGLE_CLIENT_SECRET")
    if missing:
        raise RuntimeError("Google OAuth is not configured: " + ", ".join(missing))

    state = make_state(project_id)
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": SCOPES,
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent",
        "state": state,
    }
    return GOOGLE_AUTH_URL + "?" + urlencode(params)


async def exchange_code(code: str):
    client_id = _env("GOOGLE_CLIENT_ID")
    client_secret = _env("GOOGLE_CLIENT_SECRET")
    redirect_uri = _env("GOOGLE_OAUTH_REDIRECT_URI")
    missing = []
    if not client_id:
        missing.append("GOOGLE_CLIENT_ID")
    if not client_secret:
        missing.append("GOOGLE_CLIENT_SECRET")
    if not redirect_uri:
        missing.append("GOOGLE_OAUTH_REDIRECT_URI")
    if missing:
        raise RuntimeError("Google OAuth is not configured: " + ", ".join(missing))

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        response.raise_for_status()
        return response.json()
