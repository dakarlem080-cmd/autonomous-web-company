import base64,hmac,hashlib,json,secrets
from urllib.parse import urlencode
import httpx
from app.config import settings

SCOPES=("https://www.googleapis.com/auth/webmasters.readonly "
        "https://www.googleapis.com/auth/analytics.readonly")

def _key():
    key=settings().ENCRYPTION_KEY.encode()
    if not key: raise RuntimeError("ENCRYPTION_KEY is required")
    return key

def make_state(project_id:int):
    payload={"pid":project_id,"nonce":secrets.token_urlsafe(18)}
    raw=base64.urlsafe_b64encode(json.dumps(payload,separators=(",",":" )).encode()).decode().rstrip("=")
    sig=hmac.new(_key(),raw.encode(),hashlib.sha256).hexdigest()
    return f"{raw}.{sig}"

def read_state(state:str):
    try:
        raw,sig=state.rsplit(".",1)
        expected=hmac.new(_key(),raw.encode(),hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig,expected): raise ValueError("invalid_state")
        raw += "=" * (-len(raw)%4)
        return json.loads(base64.urlsafe_b64decode(raw))
    except Exception as e: raise ValueError("invalid_state") from e

def authorization_url(project_id:int):
    s=settings()
    if not s.GOOGLE_CLIENT_ID or not s.GOOGLE_OAUTH_REDIRECT_URI:
        raise RuntimeError("GOOGLE_CLIENT_ID and GOOGLE_OAUTH_REDIRECT_URI are required")
    state=make_state(project_id)
    params={"client_id":s.GOOGLE_CLIENT_ID,"redirect_uri":s.GOOGLE_OAUTH_REDIRECT_URI,"response_type":"code","scope":SCOPES,"access_type":"offline","include_granted_scopes":"true","prompt":"consent","state":state}
    return "https://accounts.google.com/o/oauth2/v2/auth?"+urlencode(params)

async def exchange_code(code:str):
    s=settings()
    if not s.GOOGLE_CLIENT_ID or not s.GOOGLE_CLIENT_SECRET or not s.GOOGLE_OAUTH_REDIRECT_URI:
        raise RuntimeError("Google OAuth environment is incomplete")
    async with httpx.AsyncClient(timeout=30) as client:
        r=await client.post("https://oauth2.googleapis.com/token",data={"code":code,"client_id":s.GOOGLE_CLIENT_ID,"client_secret":s.GOOGLE_CLIENT_SECRET,"redirect_uri":s.GOOGLE_OAUTH_REDIRECT_URI,"grant_type":"authorization_code"})
        r.raise_for_status();return r.json()
