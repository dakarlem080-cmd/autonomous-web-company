from datetime import datetime,timezone
from fastapi import FastAPI,Depends,HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db import init_db,Session
from app.models import Project,Secret,Run,Opportunity,Employee,AIModel
from app.security import encrypt,decrypt
from app.engine import Engine
from app.integrations import GSC,GA4,GitHub,Vercel
from app.google_oauth import authorization_url,exchange_code,read_state
import json

app=FastAPI(title="Autonomous Web Company",version="5.6")
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_credentials=False,allow_methods=["*"],allow_headers=["*"])
engine=Engine()
class ProjectIn(BaseModel):name:str;domain:str;repo:str="";branch:str="main";goal:str="organic_traffic";language:str="en";dry_run:bool=True
class SecretIn(BaseModel):provider:str;value:str
class EmployeeIn(BaseModel):name:str;role:str;agent:str=""
class ModelIn(BaseModel):provider:str;model:str;purpose:str="general"

@app.on_event("startup")
async def startup():await init_db()
async def db():
 async with Session() as s:yield s
@app.get("/health")
async def health():return {"status":"ok","service":"brain-api"}
@app.get("/")
async def root():return {"service":"Autonomous Web Company Brain","status":"online","health":"/health"}
@app.get("/api/status")
async def status():
 from app.config import settings
 s=settings();return {"status":"online","dry_run":s.AUTONOMY_DRY_RUN,"provisioning_enabled":s.PROVISIONING_ENABLED,"integrations":{"gsc":bool(s.GOOGLE_APPLICATION_CREDENTIALS and s.GSC_SITE_URL),"ga4":bool(s.GA4_PROPERTY_ID),"github":bool(s.GITHUB_TOKEN and s.GITHUB_OWNER),"vercel":bool(s.VERCEL_TOKEN),"domain_binding":bool(s.VERCEL_TOKEN and s.ALLOW_DOMAIN_BINDING)},"scheduler_hours":s.SCHEDULER_HOURS}
@app.post("/api/projects")
async def create(p:ProjectIn,s:AsyncSession=Depends(db)):
 x=Project(**p.model_dump());s.add(x);await s.commit();await s.refresh(x);return {"id":x.id,"name":x.name,"domain":x.domain,"dry_run":x.dry_run}
@app.get("/api/projects")
async def projects(s:AsyncSession=Depends(db)):
 r=await s.execute(select(Project).order_by(Project.id.desc()));return [{"id":x.id,"name":x.name,"domain":x.domain,"dry_run":x.dry_run,"active":x.active} for x in r.scalars()]
@app.post("/api/projects/{pid}/secrets")
async def secret(pid:int,p:SecretIn,s:AsyncSession=Depends(db)):
 r=await s.execute(select(Project).where(Project.id==pid))
 if not r.scalar_one_or_none():raise HTTPException(404,"project_not_found")
 old=await s.scalar(select(Secret).where(Secret.project_id==pid,Secret.provider==p.provider))
 if old:old.ciphertext=encrypt(p.value)
 else:s.add(Secret(project_id=pid,provider=p.provider,ciphertext=encrypt(p.value)))
 await s.commit();return {"status":"stored","provider":p.provider}

async def secret_map(pid:int,s:AsyncSession):
 r=await s.execute(select(Secret).where(Secret.project_id==pid));out={}
 for x in r.scalars():
  try:out[x.provider]=decrypt(x.ciphertext)
  except Exception:out[x.provider]=""
 return out

@app.get("/api/projects/{pid}/google/oauth/start")
async def google_oauth_start(pid:int,s:AsyncSession=Depends(db)):
 if not await s.scalar(select(Project).where(Project.id==pid)):raise HTTPException(404,"project_not_found")
 try:return RedirectResponse(authorization_url(pid),status_code=302)
 except RuntimeError as e:raise HTTPException(503,str(e))

@app.get("/api/google/oauth/callback")
async def google_oauth_callback(code:str|None=None,state:str|None=None,error:str|None=None,s:AsyncSession=Depends(db)):
 from app.config import settings
 if error:return RedirectResponse(f"{settings().DASHBOARD_URL}/settings?tab=google&google=denied")
 if not code or not state:raise HTTPException(400,"missing_oauth_response")
 try:payload=read_state(state);pid=int(payload["pid"])
 except Exception:raise HTTPException(400,"invalid_oauth_state")
 if not await s.scalar(select(Project).where(Project.id==pid)):raise HTTPException(404,"project_not_found")
 try:tokens=await exchange_code(code)
 except Exception as e:return RedirectResponse(f"{settings().DASHBOARD_URL}/settings?tab=google&google=error&detail={str(e)[:80]}")
 bundle={"access_token":tokens.get("access_token",""),"refresh_token":tokens.get("refresh_token",""),"expires_in":tokens.get("expires_in",0),"scope":tokens.get("scope","")}
 old=await s.scalar(select(Secret).where(Secret.project_id==pid,Secret.provider=="google_oauth"))
 value=json.dumps(bundle)
 if old:old.ciphertext=encrypt(value)
 else:s.add(Secret(project_id=pid,provider="google_oauth",ciphertext=encrypt(value)))
 await s.commit()
 return RedirectResponse(f"{settings().DASHBOARD_URL}/settings?tab=google&google=connected")

@app.post("/api/projects/{pid}/connections/test")
async def test_connection(pid:int,p:SecretIn,s:AsyncSession=Depends(db)):
 if not await s.scalar(select(Project).where(Project.id==pid)):raise HTTPException(404,"project_not_found")
 value=p.value.strip()
 try:
  if p.provider=="github_token":
   from github import Github
   user=Github(value).get_user();return {"provider":"github","connected":True,"account":user.login}
  if p.provider=="vercel_token":
   import httpx
   r=httpx.get("https://api.vercel.com/v2/user",headers={"Authorization":f"Bearer {value}"},timeout=20);r.raise_for_status();return {"provider":"vercel","connected":True,"account":r.json().get("user",{}).get("username")}
  if p.provider in {"gsc_service_account","ga4_service_account"}:
   from google.oauth2 import service_account
   scopes=["https://www.googleapis.com/auth/webmasters.readonly"] if p.provider=="gsc_service_account" else ["https://www.googleapis.com/auth/analytics.readonly"]
   info=json.loads(value);creds=service_account.Credentials.from_service_account_info(info,scopes=scopes)
   return {"provider":p.provider,"connected":True,"account":creds.service_account_email}
  raise HTTPException(400,"unsupported_provider")
 except HTTPException:raise
 except Exception as e:return {"provider":p.provider,"connected":False,"error":str(e)[:300]}

@app.post("/api/projects/{pid}/connections/save-and-test")
async def save_and_test_connection(pid:int,p:SecretIn,s:AsyncSession=Depends(db)):
 result=await test_connection(pid,p,s)
 if result.get("connected"):await secret(pid,p,s)
 return result

@app.get("/api/projects/{pid}/settings")
async def project_settings(pid:int,s:AsyncSession=Depends(db)):
 r=await s.execute(select(Project).where(Project.id==pid));p=r.scalar_one_or_none()
 if not p:raise HTTPException(404,"project_not_found")
 er=await s.execute(select(Employee).where(Employee.project_id==pid));mr=await s.execute(select(AIModel).where(AIModel.project_id==pid));sr=await s.execute(select(Secret).where(Secret.project_id==pid))
 from app.config import settings
 cfg=settings();providers=[x.provider for x in sr.scalars()]
 return {"project":{"id":p.id,"name":p.name,"domain":p.domain,"dry_run":p.dry_run},"employees":[{"id":x.id,"name":x.name,"role":x.role,"agent":x.agent,"active":x.active} for x in er.scalars()],"models":[{"id":x.id,"provider":x.provider,"model":x.model,"purpose":x.purpose,"active":x.active} for x in mr.scalars()],"connections":{"github":bool(cfg.GITHUB_TOKEN and cfg.GITHUB_OWNER),"vercel":bool(cfg.VERCEL_TOKEN),"gsc":bool(cfg.GOOGLE_APPLICATION_CREDENTIALS and cfg.GSC_SITE_URL) or "google_oauth" in providers,"ga4":bool(cfg.GA4_PROPERTY_ID) or "google_oauth" in providers,"google_oauth":"google_oauth" in providers,"secrets":providers}}

@app.post("/api/projects/{pid}/employees")
async def add_employee(pid:int,p:EmployeeIn,s:AsyncSession=Depends(db)):
 if not await s.scalar(select(Project).where(Project.id==pid)):raise HTTPException(404,"project_not_found")
 x=Employee(project_id=pid,**p.model_dump());s.add(x);await s.commit();await s.refresh(x);return {"id":x.id,"name":x.name,"role":x.role,"agent":x.agent,"active":x.active}
@app.delete("/api/projects/{pid}/employees/{eid}")
async def remove_employee(pid:int,eid:int,s:AsyncSession=Depends(db)):
 x=await s.scalar(select(Employee).where(Employee.id==eid,Employee.project_id==pid))
 if not x:raise HTTPException(404,"employee_not_found")
 await s.delete(x);await s.commit();return {"status":"removed"}
@app.post("/api/projects/{pid}/models")
async def add_model(pid:int,p:ModelIn,s:AsyncSession=Depends(db)):
 if not await s.scalar(select(Project).where(Project.id==pid)):raise HTTPException(404,"project_not_found")
 x=AIModel(project_id=pid,**p.model_dump());s.add(x);await s.commit();await s.refresh(x);return {"id":x.id,"provider":x.provider,"model":x.model,"purpose":x.purpose,"active":x.active}
@app.delete("/api/projects/{pid}/models/{mid}")
async def remove_model(pid:int,mid:int,s:AsyncSession=Depends(db)):
 x=await s.scalar(select(AIModel).where(AIModel.id==mid,AIModel.project_id==pid))
 if not x:raise HTTPException(404,"model_not_found")
 await s.delete(x);await s.commit();return {"status":"removed"}
@app.post("/api/projects/{pid}/provision")
async def provision(pid:int,s:AsyncSession=Depends(db)):
 r=await s.execute(select(Project).where(Project.id==pid));p=r.scalar_one_or_none()
 if not p:raise HTTPException(404,"project_not_found")
 from app.config import settings
 if settings().AUTONOMY_DRY_RUN:return {"status":"blocked","reason":"global_dry_run_enabled"}
 return engine.provision(p)
@app.post("/api/projects/{pid}/run")
async def run(pid:int,s:AsyncSession=Depends(db)):
 r=await s.execute(select(Project).where(Project.id==pid));p=r.scalar_one_or_none()
 if not p:return {"error":"project_not_found"}
 x=Run(project_id=pid,status="running");s.add(x);await s.commit()
 try:x.state=engine.cycle(p);x.status="cycle_complete"
 except Exception as e:x.status="failed";x.error=str(e);x.state={"error":str(e)}
 x.finished_at=datetime.now(timezone.utc);await s.commit();return x.state
@app.get("/api/projects/{pid}/runs")
async def runs(pid:int,s:AsyncSession=Depends(db)):
 r=await s.execute(select(Run).where(Run.project_id==pid).order_by(Run.id.desc()).limit(50));return [{"id":x.id,"status":x.status,"error":x.error,"finished_at":x.finished_at.isoformat() if x.finished_at else None} for x in r.scalars()]
@app.get("/api/projects/{pid}/opportunities")
async def ops(pid:int,s:AsyncSession=Depends(db)):
 r=await s.execute(select(Opportunity).where(Opportunity.project_id==pid).order_by(Opportunity.score.desc()));return [{"id":x.id,"title":x.title,"score":x.score,"status":x.status} for x in r.scalars()]
@app.get("/api/projects/{pid}/analytics")
async def analytics(pid:int,s:AsyncSession=Depends(db)):
 r=await s.execute(select(Project).where(Project.id==pid));p=r.scalar_one_or_none()
 if not p:return {"error":"project_not_found"}
 gsc=GSC();gsc_rows=gsc.query(["query","page"]);impressions=clicks=0.0;opportunities=[]
 for row in gsc_rows:
  imp=float(row.get("impressions",0));clk=float(row.get("clicks",0));impressions+=imp;clicks+=clk;keys=row.get("keys",[])
  if imp>0:opportunities.append({"query":keys[0] if keys else "","page":keys[1] if len(keys)>1 else "","clicks":clk,"impressions":imp,"ctr":float(row.get("ctr",0))*100,"position":float(row.get("position",0))})
 opportunities.sort(key=lambda x:(x["impressions"],-x["position"]),reverse=True)
 ga4=GA4();ga4_rows=ga4.report();users=sessions=engagement_weight=0.0
 for row in ga4_rows:
  vals=[float(v.value or 0) for v in row.metric_values];u=vals[0] if len(vals)>0 else 0;sess=vals[1] if len(vals)>1 else 0;eng=vals[2] if len(vals)>2 else 0;users+=u;sessions+=sess;engagement_weight+=eng*sess
 engagement=(engagement_weight/sessions*100) if sessions else 0
 return {"project":{"id":p.id,"name":p.name,"domain":p.domain},"gsc":{"configured":bool(gsc.service),"clicks":round(clicks),"impressions":round(impressions),"ctr":round(clicks/impressions*100,2) if impressions else 0,"opportunities":opportunities[:20]},"ga4":{"configured":bool(ga4.client),"users":round(users),"sessions":round(sessions),"engagement_rate":round(engagement,2)},"period_days":28}
