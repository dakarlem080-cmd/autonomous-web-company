from __future__ import annotations
import os
import httpx
from google.oauth2.credentials import Credentials
from app.config import settings

BASE="https://adsense.googleapis.com/v2"
SCOPE="https://www.googleapis.com/auth/adsense.readonly"

def _cfg(name:str)->str:
    value=(os.environ.get(name) or "").strip()
    if value:return value
    try:return str(getattr(settings(),name,"") or "").strip()
    except Exception:return ""

def credentials(oauth:dict)->Credentials:
    return Credentials(token=oauth.get("access_token"),refresh_token=oauth.get("refresh_token"),token_uri="https://oauth2.googleapis.com/token",client_id=_cfg("GOOGLE_CLIENT_ID"),client_secret=_cfg("GOOGLE_CLIENT_SECRET"),scopes=[SCOPE])

class AdSense:
    def __init__(self,oauth:dict|None=None): self.oauth=oauth or {}
    def ready(self): return bool(self.oauth.get("access_token"))
    def _headers(self):
        c=credentials(self.oauth)
        if c.expired and c.refresh_token: c.refresh(request=None)
        return {"Authorization":f"Bearer {c.token}","Content-Type":"application/json"}
    async def accounts(self):
        if not self.ready(): return {"connected":False,"reason":"google_oauth_not_configured"}
        async with httpx.AsyncClient(timeout=30) as client:
            r=await client.get(f"{BASE}/accounts",headers=self._headers())
            if r.status_code>=400:return {"connected":False,"status_code":r.status_code,"error":r.text[:500]}
            return {"connected":True,"accounts":r.json().get("accounts",[])}
    async def sites(self,account:str):
        if not self.ready(): return {"connected":False,"reason":"google_oauth_not_configured"}
        account=account.split("/")[-1]
        async with httpx.AsyncClient(timeout=30) as client:
            r=await client.get(f"{BASE}/accounts/{account}/sites",headers=self._headers())
            if r.status_code>=400:return {"connected":False,"status_code":r.status_code,"error":r.text[:500]}
            return {"connected":True,"sites":r.json().get("sites",[])}
    async def report(self,account:str,days:int=28):
        if not self.ready(): return {"connected":False,"reason":"google_oauth_not_configured"}
        account=account.split("/")[-1]
        body={"startDate":{"year":2026,"month":1,"day":1},"endDate":{"year":2026,"month":12,"day":31},"metrics":["ESTIMATED_EARNINGS","IMPRESSIONS","CLICKS","PAGE_VIEWS_RPM","COST_PER_CLICK","PAGE_VIEWS"],"dimensions":["DATE"]}
        from datetime import date,timedelta
        end=date.today();start=end-timedelta(days=max(1,days))
        body["startDate"]={"year":start.year,"month":start.month,"day":start.day};body["endDate"]={"year":end.year,"month":end.month,"day":end.day}
        async with httpx.AsyncClient(timeout=60) as client:
            r=await client.post(f"{BASE}/accounts/{account}/reports:generate",headers=self._headers(),json=body)
            if r.status_code>=400:return {"connected":False,"status_code":r.status_code,"error":r.text[:500]}
            return {"connected":True,"report":r.json()}
