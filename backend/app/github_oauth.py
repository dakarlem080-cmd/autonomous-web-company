import base64
import hashlib
import hmac
import json
import time
from urllib.parse import urlencode
import httpx
from app.config import settings

AUTH_URL="https://github.com/login/oauth/authorize"
TOKEN_URL="https://github.com/login/oauth/access_token"
API_URL="https://api.github.com"
SCOPES="read:user user:email repo read:org workflow"

def _secret():
    s=settings()
    return (s.GITHUB_OAUTH_STATE_SECRET or s.ENCRYPTION_KEY or s.GITHUB_CLIENT_SECRET or "github-state").encode()

def redirect_uri():
    s=settings()
    if s.GITHUB_OAUTH_REDIRECT_URI:
        return s.GITHUB_OAUTH_REDIRECT_URI.rstrip("/")
    return f"{s.DASHBOARD_URL.rstrip('/')}/api/github/oauth/callback"

def make_state(project_id:int):
    payload={"pid":project_id,"iat":int(time.time()),"nonce":hashlib.sha256(f"{project_id}:{time.time_ns()}".encode()).hexdigest()[:24]}
    raw=base64.urlsafe_b64encode(json.dumps(payload,separators=(",",":"),sort_keys=True).encode()).decode().rstrip("=")
    sig=hmac.new(_secret(),raw.encode(),hashlib.sha256).hexdigest()
    return f"{raw}.{sig}"

def read_state(state:str,max_age=600):
    raw,sig=state.rsplit(".",1)
    expected=hmac.new(_secret(),raw.encode(),hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig,expected): raise ValueError("invalid_github_oauth_state")
    payload=json.loads(base64.urlsafe_b64decode(raw+"="*((4-len(raw)%4)%4)).decode())
    if int(time.time())-int(payload["iat"])>max_age: raise ValueError("expired_github_oauth_state")
    return payload

def authorization_url(project_id:int):
    s=settings()
    if not s.GITHUB_CLIENT_ID: raise ValueError("github_client_id_not_configured")
    return AUTH_URL+"?"+urlencode({"client_id":s.GITHUB_CLIENT_ID,"redirect_uri":redirect_uri(),"scope":SCOPES,"state":make_state(project_id),"allow_signup":"true"})

async def exchange_code(code:str):
    s=settings()
    if not s.GITHUB_CLIENT_ID or not s.GITHUB_CLIENT_SECRET: raise ValueError("github_oauth_credentials_not_configured")
    async with httpx.AsyncClient(timeout=30) as c:
        r=await c.post(TOKEN_URL,data={"client_id":s.GITHUB_CLIENT_ID,"client_secret":s.GITHUB_CLIENT_SECRET,"code":code,"redirect_uri":redirect_uri()},headers={"Accept":"application/json"})
        r.raise_for_status();data=r.json()
    if data.get("error"):raise ValueError(data.get("error_description") or data["error"])
    return data

async def github_get(token:str,path:str,params=None):
    async with httpx.AsyncClient(timeout=30) as c:
        r=await c.get(f"{API_URL}{path}",headers={"Authorization":f"Bearer {token}","Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28"},params=params or {})
        r.raise_for_status();return r.json()

async def profile(token:str): return await github_get(token,"/user")
async def repositories(token:str,per_page=100): return await github_get(token,"/user/repos",{"per_page":per_page,"sort":"updated","affiliation":"owner,collaborator,organization_member"})
