import base64
import hashlib
import hmac
import json
import secrets
from urllib.parse import urlencode

import httpx

from app.config import settings


def _secret() -> bytes:
    s = settings()
    value = s.VERCEL_OAUTH_STATE_SECRET or s.ENCRYPTION_KEY
    if not value:
        raise ValueError("vercel_oauth_state_secret_not_configured")
    return value.encode()


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def make_state(project_id: int) -> str:
    payload = {"pid": project_id, "nonce": secrets.token_urlsafe(18)}
    raw = _b64(json.dumps(payload, separators=(",", ":")).encode())
    signature = _b64(hmac.new(_secret(), raw.encode(), hashlib.sha256).digest())
    return f"{raw}.{signature}"


def read_state(state: str) -> dict:
    try:
        raw, signature = state.split(".", 1)
        expected = hmac.new(_secret(), raw.encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(_unb64(signature), expected):
            raise ValueError("vercel_oauth_state_invalid")
        payload = json.loads(_unb64(raw).decode())
        pid = int(payload["pid"])
        if pid <= 0:
            raise ValueError("vercel_oauth_state_invalid")
        return payload
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("vercel_oauth_state_invalid") from exc


def authorization_url(project_id: int) -> str:
    s = settings()
    if not s.VERCEL_CLIENT_ID:
        raise ValueError("vercel_oauth_not_configured")
    if not s.VERCEL_OAUTH_REDIRECT_URI:
        raise ValueError("vercel_oauth_redirect_not_configured")
    slug = s.VERCEL_INTEGRATION_SLUG.strip() or "autonomous-web-company"
    state = make_state(project_id)
    params = {
        "source": "external",
        "state": state,
    }
    return f"https://vercel.com/integrations/{slug}/new?{urlencode(params)}"


async def exchange_code(code: str) -> dict:
    s = settings()
    if not s.VERCEL_CLIENT_ID or not s.VERCEL_CLIENT_SECRET:
        raise ValueError("vercel_oauth_not_configured")
    if not s.VERCEL_OAUTH_REDIRECT_URI:
        raise ValueError("vercel_oauth_redirect_not_configured")
    response = await httpx.AsyncClient(timeout=30).post(
        "https://api.vercel.com/v2/oauth/access_token",
        data={
            "client_id": s.VERCEL_CLIENT_ID,
            "client_secret": s.VERCEL_CLIENT_SECRET,
            "code": code,
            "redirect_uri": s.VERCEL_OAUTH_REDIRECT_URI,
        },
        headers={"Accept": "application/json"},
    )
    response.raise_for_status()
    data = response.json()
    if not data.get("access_token"):
        raise ValueError("vercel_access_token_missing")
    return data


async def current_user(access_token: str) -> dict:
    response = await httpx.AsyncClient(timeout=30).get(
        "https://api.vercel.com/v2/user",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    response.raise_for_status()
    return response.json()


async def list_projects(access_token: str, team_id: str | None = None) -> list:
    params = {"limit": 100}
    if team_id:
        params["teamId"] = team_id
    response = await httpx.AsyncClient(timeout=30).get(
        "https://api.vercel.com/v9/projects",
        params=params,
        headers={"Authorization": f"Bearer {access_token}"},
    )
    response.raise_for_status()
    return response.json().get("projects", [])
