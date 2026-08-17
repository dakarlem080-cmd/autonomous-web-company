"""Google OAuth helpers for Search Console, Analytics 4, and Google Ads."""
from __future__ import annotations
import base64,hashlib,hmac,json,os,secrets,time
from urllib.parse import urlencode
import httpx
from app.config import settings
GOOGLE_AUTH_URL="https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL="https://oauth2.googleapis.com/token"
SCOPES="https://www.googleapis.com/auth/webmasters.readonly https://www.googleapis.com/auth/analytics.readonly https://www.googleapis.com/auth/adwords"
def _env(name:str)->str:
 value=(os.environ.get(name) or "").strip()
 if value:return value
 try:return str(getattr(settings(),name,"") or "").strip()
 except Exception:return ""
def _state_key()->bytes:
 value=_env("GOOGLE_OAUTH_STATE_SECRET") or _env("ENCRYPTION_KEY") or _env("GOOGLE_CLIENT_SECRET")
 if not value:raise RuntimeError("Google OAuth state secret is not configured")
 return value.encode()
def make_state(project_id:int)->str:
 payload={"pid":project_id,"nonce":secrets.token_urlsafe(18),"exp":int(time.time())+600}
 raw=base64.urlsafe_b64encode(json.dumps(payload,separators=(",",":")).encode()).decode().rstrip("=")
 sig=hmac.new(_state_key(),raw.encode(),hashlib.sha256).hexdigest();return f"{raw}.{sig}"
def read_state(state:str):
 try:
  raw,sig=state.rsplit(".",1);expected=hmac.new(_state_key(),raw.encode(),hashlib.sha256).hexdigest()
  if not hmac.compare_digest(sig,expected):raise ValueError("invalid_state")
  payload=json.loads(base64.urlsafe_b64decode(raw+"="*(-len(raw)%4)))
  if int(payload.get("exp",0))<int(time.time()):raise ValueError("expired_state")
  return payload
 except Exception as exc:raise ValueError("invalid_state") from exc
def authorization_url(project_id:int):
 client_id=_env("GOOGLE_CLIENT_ID");redirect_uri=_env("GOOGLE_OAUTH_REDIRECT_URI");client_secret=_env("GOOGLE_CLIENT_SECRET")
 missing=[k for k,v in (("GOOGLE_CLIENT_ID",client_id),("GOOGLE_OAUTH_REDIRECT_URI",redirect_uri),("GOOGLE_CLIENT_SECRET",client_secret)) if not v]
 if missing:raise RuntimeError("Google OAuth is not configured: "+", ".join(missing))
 params={"client_id":client_id,"redirect_uri":redirect_uri,"response_type":"code","scope":SCOPES,"access_type":"offline","include_granted_scopes":"true","prompt":"consent","state":make_state(project_id)}
 return GOOGLE_AUTH_URL+"?"+urlencode(params)
async def exchange_code(code:str):
 client_id=_env("GOOGLE_CLIENT_ID");client_secret=_env("GOOGLE_CLIENT_SECRET");redirect_uri=_env("GOOGLE_OAUTH_REDIRECT_URI")
 missing=[k for k,v in (("GOOGLE_CLIENT_ID",client_id),("GOOGLE_CLIENT_SECRET",client_secret),("GOOGLE_OAUTH_REDIRECT_URI",redirect_uri)) if not v]
 if missing:raise RuntimeError("Google OAuth is not configured: "+", ".join(missing))
 async with httpx.AsyncClient(timeout=30) as client:
  response=await client.post(GOOGLE_TOKEN_URL,data={"code":code,"client_id":client_id,"client_secret":client_secret,"redirect_uri":redirect_uri,"grant_type":"authorization_code"})
  response.raise_for_status();return response.json()
