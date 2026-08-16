from cryptography.fernet import Fernet
from app.config import settings
def cipher():
    k=settings().ENCRYPTION_KEY
    if not k: raise RuntimeError("ENCRYPTION_KEY required")
    return Fernet(k.encode())
def encrypt(v): return cipher().encrypt(v.encode()).decode()
def decrypt(v): return cipher().decrypt(v.encode()).decode()
