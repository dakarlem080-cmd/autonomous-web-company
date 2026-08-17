import hashlib
import os
import re
import secrets
from cryptography.fernet import Fernet
from app.config import settings

PROVIDER_RE = re.compile(r"^[a-zA-Z0-9_.:-]{2,80}$")

def cipher() -> Fernet:
    key = (settings().ENCRYPTION_KEY or "").strip()
    if not key:
        raise RuntimeError("ENCRYPTION_KEY is required; refusing to derive encryption keys from OAuth secrets")
    try:
        return Fernet(key.encode("ascii"))
    except Exception as exc:
        raise RuntimeError("ENCRYPTION_KEY must be a valid Fernet key") from exc

def encrypt(value: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("secret_value_required")
    return cipher().encrypt(value.encode("utf-8")).decode("ascii")

def decrypt(value: str) -> str:
    return cipher().decrypt(value.encode("ascii")).decode("utf-8")

def validate_provider(provider: str) -> str:
    provider = provider.strip()
    if not PROVIDER_RE.fullmatch(provider):
        raise ValueError("invalid_secret_provider")
    return provider

def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

def new_session_token() -> str:
    return secrets.token_urlsafe(48)
