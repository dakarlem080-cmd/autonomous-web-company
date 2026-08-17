from __future__ import annotations
import os
import httpx
from google.oauth2.credentials import Credentials
from app.config import settings

API_VERSION="v25"
BASE=f"https://googleads.googleapis.com/{API_VERSION}"
SCOPE="https://www.googleapis.com/auth/adwords"

def _cfg(name:str)->str:
    value=(os.environ.get(name) or "").strip()
    if value:return value
    return str(getattr(settings(),name,"") or "").strip()

def credentials(oauth:dict)->Credentials:
    return Credentials(
        token=oauth.get("access_token"),
        refresh_token=oauth.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=_cfg("GOOGLE_CLIENT_ID"),
        client_secret=_cfg("GOOGLE_CLIENT_SECRET"),
        scopes=[SCOPE],
    )

class GoogleAds:
    def __init__(self,oauth:dict|None=None,customer_id:str|None=None):
        self.oauth=oauth or {}
        self.customer_id=(customer_id or _cfg("GOOGLE_ADS_CUSTOMER_ID")).replace("-","")
        self.login_customer_id=_cfg("GOOGLE_ADS_LOGIN_CUSTOMER_ID").replace("-","")
        self.developer_token=_cfg("GOOGLE_ADS_DEVELOPER_TOKEN")
    def ready(self):
        return bool(self.oauth.get("access_token") and self.developer_token)
    def _headers(self):
        c=credentials(self.oauth)
        if c.expired and c.refresh_token:c.refresh(request=None)
        access=c.token
        headers={"Authorization":f"Bearer {access}","developer-token":self.developer_token,"Content-Type":"application/json"}
        if self.login_customer_id:headers["login-customer-id"]=self.login_customer_id
        return headers
    async def accessible_customers(self):
        if not self.ready():return {"connected":False,"reason":"oauth_or_developer_token_not_configured"}
        async with httpx.AsyncClient(timeout=30) as client:
            r=await client.get(f"{BASE}/customers:listAccessibleCustomers",headers=self._headers())
            if r.status_code>=400:return {"connected":False,"status_code":r.status_code,"error":r.text[:500]}
            names=r.json().get("resourceNames",[])
            return {"connected":True,"customer_ids":[x.rsplit("/",1)[-1] for x in names]}
    async def campaign_metrics(self,customer_id:str|None=None,days:int=30):
        cid=(customer_id or self.customer_id).replace("-","")
        if not cid:return {"connected":False,"reason":"customer_id_not_configured"}
        if not self.ready():return {"connected":False,"reason":"oauth_or_developer_token_not_configured"}
        query=("SELECT campaign.id, campaign.name, campaign.status, metrics.impressions, "
               "metrics.clicks, metrics.cost_micros, metrics.conversions "
               "FROM campaign WHERE segments.date DURING LAST_30_DAYS "
               "ORDER BY metrics.impressions DESC")
        async with httpx.AsyncClient(timeout=60) as client:
            r=await client.post(f"{BASE}/customers/{cid}/googleAds:searchStream",headers=self._headers(),json={"query":query})
            if r.status_code>=400:return {"connected":False,"status_code":r.status_code,"error":r.text[:500]}
            rows=[]
            for batch in r.json():
                for row in batch.get("results",[]):
                    campaign=row.get("campaign",{});metrics=row.get("metrics",{})
                    rows.append({"id":campaign.get("id"),"name":campaign.get("name"),"status":campaign.get("status"),"impressions":int(metrics.get("impressions",0)),"clicks":int(metrics.get("clicks",0)),"cost":float(metrics.get("costMicros",0))/1_000_000,"conversions":float(metrics.get("conversions",0))})
            return {"connected":True,"customer_id":cid,"campaigns":rows}
