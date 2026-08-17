import pytest
from cryptography.fernet import Fernet


def test_encryption_key_is_independent(monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("ENCRYPTION_KEY", key)
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "different")
    from app.security import decrypt, encrypt

    value = "oauth-token"
    assert decrypt(encrypt(value)) == value


def test_encryption_requires_key(monkeypatch):
    monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
    from app.security import cipher

    with pytest.raises(RuntimeError):
        cipher()


def test_decision_schema_rejects_invalid_confidence():
    from app.ai_schemas import DecisionSchema

    with pytest.raises(Exception):
        DecisionSchema(
            action="x",
            reason="r",
            confidence=2,
            expected_impact=0,
            risk="low",
            reversible=True,
            approval_required=False,
        )
