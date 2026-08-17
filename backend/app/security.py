import base64
import hashlib
import os
from cryptography.fernet import Fernet
from app.config import settings


def cipher():
    # Keep the explicit ENCRYPTION_KEY as the preferred production secret.
    # For OAuth-only deployments where it was not provisioned, derive a stable
    # Fernet key from the Google client secret so the callback can persist tokens
    # without exposing or logging credentials. Existing ENCRYPTION_KEY values
    # continue to take precedence.
    key = (os.getenv("ENCRYPTION_KEY") or "").strip()
    if not key:
        try:
            key = (settings().ENCRYPTION_KEY or "").strip()
        except Exception:
            key = ""
    if not key:
        secret = (os.getenv("GOOGLE_CLIENT_SECRET") or "").strip()
        if not secret:
            try:
                secret = (settings().GOOGLE_CLIENT_SECRET or "").strip()
            except Exception:
                secret = ""
        if secret:
            key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest()).decode("ascii")
    if not key:
        raise RuntimeError("ENCRYPTION_KEY required")
    return Fernet(key.encode())


def encrypt(v):
    return cipher().encrypt(v.encode()).decode()


def decrypt(v):
    return cipher().decrypt(v.encode()).decode()
