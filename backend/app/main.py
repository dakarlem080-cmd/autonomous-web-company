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
from app.github_oauth import authorization_url as github_authorization_url,exchange_code as github_exchange_code,read_state as github_read_state,profile as github_profile,repositories as github_repositories
from app.vercel_oauth import authorization_url as vercel_authorization_url,exchange_code as vercel_exchange_code,read_state as vercel_read_state,current_user as vercel_current_user,list_projects as vercel_list_projects,list_deployments as vercel_list_deployments
from app.adsense import AdSense
import json
app=FastAPI(title="Autonomous Web Company",version="5.6")
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_credentials=False,allow_methods=["*"],allow_headers=["*"])
engine=Engine()
class ProjectIn(BaseModel):name:str;domain:str;repo:str="";branch:str="main";goal:str="organic_traffic";language:str="en";dry_run:bool=True
class ProjectPatch(BaseModel):name:str|None=None;domain:str|None=None;repo:str|None=None;branch:str|None=None;goal:str|None=None;language:str|None=None;dry_run:bool|None=None;active:bool|None=None
class SecretIn(BaseModel):provider:str;value:str
class EmployeeIn(BaseModel):name:str;role:str;agent:str="";instructions:str="";objectives:list[str]=[];tools:list[str]=[];permissions:list[str]=[];model_id:int|None=None;autonomy_level:str="execute"
class EmployeePatch(BaseModel):name:str|None=None;role:str|None=None;agent:str|None=None;instructions:str|None=None;objectives:list[str]|None=None;tools:list[str]|None=None;permissions:list[str]|None=None;model_id:int|None=None;autonomy_level:str|None=None;active:bool|None=None
class ModelIn(BaseModel):provider:str;model:str;purpose:str="general"
class ModelPatch(BaseModel):provider:str|None=None;model:str|None=None;purpose:str|None=None;active:bool|None=None
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
 s=settings();return {"status":"online","dry_run":s.AUTONOMY_DRY_RUN,"provisioning_enabled":s.PROVISIONING_ENABLED,"integrations":{"gsc":bool(s.GOOGLE_APPLICATION_CREDENTIALS and s.GSC_SITE_URL),"ga4":bool(s.GA4_PROPERTY_ID),"github":bool(s.GITHUB_TOKEN and s.GITHUB_OWNER),"vercel":False,"domain_binding":bool((s.VERCEL_TOKEN or s.VERCEL_CLIENT_ID) and s.ALLOW_DOMAIN_BINDING)},"scheduler_hours":s.SCHEDULER_HOURS}
@app.post("/api/projects")
async def create(p:ProjectIn,s:AsyncSession=Depends(db)):
 x=Project(**p.model_dump());s.add(x);await s.commit();await s.refresh(x);return {"id":x.id,"name":x.name,"domain":x.domain,"dry_run":x.dry_run,"active":x.active}
@app.get("/api/projects")
async def projects(s:AsyncSession=Depends(db)):
 r=await s.execute(select(Project).order_by(Project.id.desc()));return [{"id":x.id,"name":x.name,"domain":x.domain,"repo":x.repo,"branch":x.branch,"goal":x.goal,"language":x.language,"dry_run":x.dry_run,"active":x.active} for x in r.scalars()]
@app.patch("/api/projects/{pid}")
async def update_project(pid:int,p:ProjectPatch,s:AsyncSession=Depends(db)):
 x=await s.scalar(select(Project).where(Project.id==pid))
 if not x:raise HTTPException(404,"project_not_found")
 for k,v in p.model_dump(exclude_unset=True).items():setattr(x,k,v)
 await s.commit();await s.refresh(x);return {"id":x.id,"name":x.name,"domain":x.domain,"repo":x.repo,"branch":x.branch,"goal":x.goal,"language":x.language,"dry_run":x.dry_run,"active":x.active}
@app.get("/api/projects/{pid}/settings")
async def project_settings(pid:int,s:AsyncSession=Depends(db)):
 p=await s.scalar(select(Project).where(Project.id==pid))
 if not p:raise HTTPException(404,"project_not_found")
 providers=await secret_providers(pid,s)
 employees=(await s.execute(select(Employee).where(Employee.project_id==pid).order_by(Employee.id))).scalars().all()
 models=(await s.execute(select(AIModel).where(AIModel.project_id==pid).order_by(AIModel.id))).scalars().all()
 from app.config import settings
 cfg=settings();google_connected="google_oauth" in providers;github_connected="github_oauth" in providers;vercel_connected="vercel_oauth" in providers
 return {"project":{"id":p.id,"name":p.name,"domain":p.domain,"repo":p.repo,"branch":p.branch,"goal":p.goal,"language":p.language,"dry_run":p.dry_run,"active":p.active},"connections":{"google":{"connected":google_connected,"search_console":google_connected,"analytics":google_connected,"adsense":google_connected},"google_oauth":google_connected,"gsc":google_connected,"ga4":google_connected,"adsense":google_connected,"github":github_connected,"vercel":vercel_connected},"employees":[{"id":x.id,"name":x.name,"role":x.role,"agent":x.agent,"instructions":x.instructions,"objectives":x.objectives or [],"tools":x.tools or [],"permissions":x.permissions or [],"model_id":x.model_id,"autonomy_level":x.autonomy_level,"active":x.active} for x in employees],"models":[{"id":x.id,"provider":x.provider,"model":x.model,"purpose":x.purpose,"active":x.active} for x in models]}
@app.post("/api/projects/{pid}/secrets")
async def secret(pid:int,p:SecretIn,s:AsyncSession=Depends(db)):
 if not await s.scalar(select(Project).where(Project.id==pid)):raise HTTPException(404,"project_not_found")
 old=await s.scalar(select(Secret).where(Secret.project_id==pid,Secret.provider==p.provider))
 if old:old.ciphertext=encrypt(p.value)
 else:s.add(Secret(project_id=pid,provider=p.provider,ciphertext=encrypt(p.value)))
 await s.commit();return {"status":"stored","provider":p.provider}
@app.get("/api/projects/{pid}/employees")
async def employees(pid:int,s:AsyncSession=Depends(db)):
 r=await s.execute(select(Employee).where(Employee.project_id==pid).order_by(Employee.id));return [{"id":x.id,"name":x.name,"role":x.role,"agent":x.agent,"instructions":x.instructions,"objectives":x.objectives or [],"tools":x.tools or [],"permissions":x.permissions or [],"model_id":x.model_id,"autonomy_level":x.autonomy_level,"active":x.active} for x in r.scalars()]
@app.post("/api/projects/{pid}/employees")
async def add_employee(pid:int,p:EmployeeIn,s:AsyncSession=Depends(db)):
 if not await s.scalar(select(Project).where(Project.id==pid)):raise HTTPException(404,"project_not_found")
 if p.model_id and not await s.scalar(select(AIModel).where(AIModel.id==p.model_id,AIModel.project_id==pid)):raise HTTPException(400,"model_not_found")
 x=Employee(project_id=pid,**p.model_dump());s.add(x);await s.commit();await s.refresh(x);return {"id":x.id,"name":x.name,"role":x.role,"agent":x.agent,"model_id":x.model_id,"active":x.active}
@app.patch("/api/projects/{pid}/employees/{eid}")
async def update_employee(pid:int,eid:int,p:EmployeePatch,s:AsyncSession=Depends(db)):
 x=await s.scalar(select(Employee).where(Employee.id==eid,Employee.project_id==pid))
 if not x:raise HTTPException(404,"employee_not_found")
 data=p.model_dump(exclude_unset=True)
 if "model_id" in data and data["model_id"] and not await s.scalar(select(AIModel).where(AIModel.id==data["model_id"],AIModel.project_id==pid)):raise HTTPException(400,"model_not_found")
 for k,v in data.items():setattr(x,k,v)
 await s.commit();await s.refresh(x);return {"id":x.id,"name":x.name,"role":x.role,"agent":x.agent,"instructions":x.instructions,"objectives":x.objectives or [],"tools":x.tools or [],"permissions":x.permissions or [],"model_id":x.model_id,"autonomy_level":x.autonomy_level,"active":x.active}
@app.delete("/api/projects/{pid}/employees/{eid}")
async def remove_employee(pid:int,eid:int,s:AsyncSession=Depends(db)):
 x=await s.scalar(select(Employee).where(Employee.id==eid,Employee.project_id==pid))
 if not x:raise HTTPException(404,"employee_not_found")
 await s.delete(x);await s.commit();return {"status":"removed"}
@app.get("/api/projects/{pid}/models")
async def models(pid:int,s:AsyncSession=Depends(db)):
 r=await s.execute(select(AIModel).where(AIModel.project_id==pid).order_by(AIModel.id));return [{"id":x.id,"provider":x.provider,"model":x.model,"purpose":x.purpose,"active":x.active} for x in r.scalars()]
@app.post("/api/projects/{pid}/models")
async def add_model(pid:int,p:ModelIn,s:AsyncSession=Depends(db)):
 if not await s.scalar(select(Project).where(Project.id==pid)):raise HTTPException(404,"project_not_found")
 x=AIModel(project_id=pid,**p.model_dump());s.add(x);await s.commit();await s.refresh(x);return {"id":x.id,"provider":x.provider,"model":x.model,"purpose":x.purpose,"active":x.active}
@app.patch("/api/projects/{pid}/models/{mid}")
async def update_model(pid:int,mid:int,p:ModelPatch,s:AsyncSession=Depends(db)):
 x=await s.scalar(select(AIModel).where(AIModel.id==mid,AIModel.project_id==pid))
 if not x:raise HTTPException(404,"model_not_found")
 for k,v in p.model_dump(exclude_unset=True).items():setattr(x,k,v)
 await s.commit();await s.refresh(x);return {"id":x.id,"provider":x.provider,"model":x.model,"purpose":x.purpose,"active":x.active}
@app.delete("/api/projects/{pid}/models/{mid}")
async def remove_model(pid:int,mid:int,s:AsyncSession=Depends(db)):
 x=await s.scalar(select(AIModel).where(AIModel.id==mid,AIModel.project_id==pid))
 if not x:raise HTTPException(404,"model_not_found")
 await s.delete(x);await s.commit();return {"status":"removed"}
@app.get("/api/projects/{pid}/autonomy")
async def autonomy(pid:int,s:AsyncSession=Depends(db)):
 if not await s.scalar(select(Project).where(Project.id==pid)):raise HTTPException(404,"project_not_found")
 run=await s.scalar(select(Run).where(Run.project_id==pid).order_by(Run.id.desc()).limit(1));emps=(await s.execute(select(Employee).where(Employee.project_id==pid,Employee.active==True))).scalars().all()
 return {"employees":[{"id":x.id,"name":x.name,"role":x.role,"agent":x.agent,"model_id":x.model_id,"autonomy_level":x.autonomy_level} for x in emps],"latest_run":{"id":run.id,"status":run.status,"state":run.state} if run else None}
@app.get("/api/projects/{pid}/google/oauth/start")
async def google_oauth_start(pid:int,s:AsyncSession=Depends(db)):
 if not await s.scalar(select(Project).where(Project.id==pid)):raise HTTPException(404,"project_not_found")
 try:return RedirectResponse(authorization_url(pid),status_code=302)
 except Exception as e:raise HTTPException(503,str(e))
@app.get("/api/google/oauth/callback")
async def google_oauth_callback(code:str|None=None,state:str|None=None,error:str|None=None,s:AsyncSession=Depends(db)):
 from app.config import settings
 dashboard=settings().DASHBOARD_URL.rstrip("/") if getattr(settings(),"DASHBOARD_URL","") else "https://autonomous-web-company.vercel.app"
 if error:return RedirectResponse(f"{dashboard}/settings?tab=google&google=denied",status_code=302)
 if not code or not state:return RedirectResponse(f"{dashboard}/settings?tab=google&google=error",status_code=302)
 try:
  payload=read_state(state);pid=int(payload.get("pid"))
  if not await s.scalar(select(Project).where(Project.id==pid)):raise ValueError("project_not_found")
  token=await exchange_code(code)
  if not token.get("access_token"):raise ValueError("google_access_token_missing")
  old=await s.scalar(select(Secret).where(Secret.project_id==pid,Secret.provider=="google_oauth"))
  value=json.dumps(token,separators=(",",":"))
  if old:old.ciphertext=encrypt(value)
  else:s.add(Secret(project_id=pid,provider="google_oauth",ciphertext=encrypt(value)))
  await s.commit()
  return RedirectResponse(f"{dashboard}/settings?tab=google&google=connected",status_code=302)
 except Exception:
  await s.rollback()
  return RedirectResponse(f"{dashboard}/settings?tab=google&google=error",status_code=302)
@app.get("/api/projects/{pid}/github/oauth/start")
async def github_oauth_start(pid:int,s:AsyncSession=Depends(db)):
 if not await s.scalar(select(Project).where(Project.id==pid)):raise HTTPException(404,"project_not_found")
 try:return RedirectResponse(github_authorization_url(pid),status_code=302)
 except ValueError as e:raise HTTPException(503,detail=str(e))
 except Exception as e:raise HTTPException(500,detail=f"github_oauth_start_failed:{e}")
@app.get("/api/github/oauth/callback")
async def github_oauth_callback(code:str|None=None,state:str|None=None,error:str|None=None,s:AsyncSession=Depends(db)):
 from app.config import settings
 dashboard=settings().DASHBOARD_URL.rstrip("/")
 if error:return RedirectResponse(f"{dashboard}/settings?tab=github&github=denied",status_code=302)
 if not code or not state:return RedirectResponse(f"{dashboard}/settings?tab=github&github=error",status_code=302)
 try:
  payload=github_read_state(state);pid=int(payload.get("pid"))
  if not await s.scalar(select(Project).where(Project.id==pid)):raise ValueError("project_not_found")
  token=await github_exchange_code(code);access=token.get("access_token")
  if not access:raise ValueError("github_access_token_missing")
  me=await github_profile(access)
  value=json.dumps({"token":token,"profile":me},separators=(",",":"))
  old=await s.scalar(select(Secret).where(Secret.project_id==pid,Secret.provider=="github_oauth"))
  if old:old.ciphertext=encrypt(value)
  else:s.add(Secret(project_id=pid,provider="github_oauth",ciphertext=encrypt(value)))
  await s.commit()
  return RedirectResponse(f"{dashboard}/settings?tab=github&github=connected",status_code=302)
 except Exception:
  await s.rollback()
  return RedirectResponse(f"{dashboard}/settings?tab=github&github=error",status_code=302)
@app.get("/api/projects/{pid}/github")
async def github_connection(pid:int,s:AsyncSession=Depends(db)):
 if not await s.scalar(select(Project).where(Project.id==pid)):raise HTTPException(404,"project_not_found")
 stored=await secret_map(pid,s);data=stored.get("github_oauth") or {}
 token=data.get("token",{}).get("access_token") if isinstance(data,dict) else None
 if not token:return {"connected":False}
 me=data.get("profile",{}) if isinstance(data,dict) else {}
 try:repos=await github_repositories(token,100)
 except Exception as e:return {"connected":True,"profile":me,"repositories":[],"error":str(e)[:300]}
 return {"connected":True,"profile":me,"repositories":repos if isinstance(repos,list) else []}
@app.delete("/api/projects/{pid}/github")
async def github_disconnect(pid:int,s:AsyncSession=Depends(db)):
 x=await s.scalar(select(Secret).where(Secret.project_id==pid,Secret.provider=="github_oauth"))
 if x:await s.delete(x);await s.commit()
 return {"connected":False}
@app.get("/api/projects/{pid}/vercel/oauth/start")
async def vercel_oauth_start(pid:int,s:AsyncSession=Depends(db)):
 if not await s.scalar(select(Project).where(Project.id==pid)):raise HTTPException(404,"project_not_found")
 try:return RedirectResponse(vercel_authorization_url(pid),status_code=302)
 except ValueError as e:raise HTTPException(503,detail=str(e))
 except Exception as e:raise HTTPException(500,detail=f"vercel_oauth_start_failed:{e}")
@app.get("/api/vercel/oauth/callback")
async def vercel_oauth_callback(code:str|None=None,state:str|None=None,error:str|None=None,teamId:str|None=None,configurationId:str|None=None,next:str|None=None,s:AsyncSession=Depends(db)):
 from app.config import settings
 dashboard=settings().DASHBOARD_URL.rstrip("/")
 if error:return RedirectResponse(f"{dashboard}/settings?tab=vercel&vercel=denied",status_code=302)
 if not code or not state:return RedirectResponse(f"{dashboard}/settings?tab=vercel&vercel=error",status_code=302)
 try:
  payload=vercel_read_state(state);pid=int(payload.get("pid"))
  if not await s.scalar(select(Project).where(Project.id==pid)):raise ValueError("project_not_found")
  if not configurationId:raise ValueError("vercel_configuration_id_missing")
  token=await vercel_exchange_code(code,configurationId)
  access=token.get("access_token")
  if not access:raise ValueError("vercel_access_token_missing")
  profile=await vercel_current_user(access)
  resolved_team=token.get("team_id") or teamId
  resolved_configuration=configurationId or token.get("configuration_id")
  if not resolved_configuration:raise ValueError("vercel_configuration_id_missing")
  value=json.dumps({"access_token":access,"token":token,"profile":profile,"team_id":resolved_team,"configuration_id":resolved_configuration},separators=(",",":"))
  old=await s.scalar(select(Secret).where(Secret.project_id==pid,Secret.provider=="vercel_oauth"))
  if old:old.ciphertext=encrypt(value)
  else:s.add(Secret(project_id=pid,provider="vercel_oauth",ciphertext=encrypt(value)))
  await s.commit()
  completion=next if next and next.startswith("https://vercel.com/") else f"{dashboard}/settings?tab=vercel&vercel=connected"
  return RedirectResponse(completion,status_code=302)
 except Exception:
  await s.rollback()
  return RedirectResponse(f"{dashboard}/settings?tab=vercel&vercel=error",status_code=302)
@app.get("/api/projects/{pid}/vercel")
async def vercel_connection(pid:int,s:AsyncSession=Depends(db)):
 if not await s.scalar(select(Project).where(Project.id==pid)):raise HTTPException(404,"project_not_found")
 stored=await secret_map(pid,s);data=stored.get("vercel_oauth") or {}
 token=data.get("access_token") if isinstance(data,dict) else None
 if not token:return {"connected":False}
 profile=data.get("profile",{}) if isinstance(data,dict) else {}
 team_id=data.get("team_id") if isinstance(data,dict) else None
 configuration_id=data.get("configuration_id") if isinstance(data,dict) else None
 try:projects=await vercel_list_projects(token,team_id)
 except Exception as e:return {"connected":True,"profile":profile,"team_id":team_id,"configuration_id":configuration_id,"projects":[],"error":str(e)[:300]}
 return {"connected":True,"profile":profile,"team_id":team_id,"configuration_id":configuration_id,"projects":[{"id":x.get("id"),"name":x.get("name"),"framework":x.get("framework"),"url":x.get("targets",{}).get("production",{}).get("url") if isinstance(x.get("targets"),dict) else None} for x in projects]}
@app.get("/api/projects/{pid}/vercel/deployments")
async def vercel_deployments(pid:int,project_id:str|None=None,s:AsyncSession=Depends(db)):
 if not await s.scalar(select(Project).where(Project.id==pid)):raise HTTPException(404,"project_not_found")
 stored=await secret_map(pid,s);data=stored.get("vercel_oauth") or {}
 token=data.get("access_token") if isinstance(data,dict) else None
 if not token:return {"connected":False,"deployments":[]}
 team_id=data.get("team_id") if isinstance(data,dict) else None
 if not project_id:return {"connected":True,"deployments":[],"error":"project_id_required"}
 try:deployments=await vercel_list_deployments(token,project_id,team_id)
 except Exception as e:return {"connected":True,"deployments":[],"error":str(e)[:300]}
 return {"connected":True,"project_id":project_id,"team_id":team_id,"deployments":[{"id":x.get("uid") or x.get("id"),"name":x.get("name"),"state":x.get("state"),"url":x.get("url"),"created":x.get("created"),"target":x.get("target"),"ready":x.get("ready")} for x in deployments]}
@app.delete("/api/projects/{pid}/vercel")
async def vercel_disconnect(pid:int,s:AsyncSession=Depends(db)):
 x=await s.scalar(select(Secret).where(Secret.project_id==pid,Secret.provider=="vercel_oauth"))
 if x:await s.delete(x);await s.commit()
 return {"connected":False}
@app.get("/api/projects/{pid}/adsense")
async def adsense(pid:int,s:AsyncSession=Depends(db)):
 if not await s.scalar(select(Project).where(Project.id==pid)):raise HTTPException(404,"project_not_found")
 stored=await secret_map(pid,s);oauth=parse_google_oauth(stored);api=AdSense(oauth);accounts=await api.accounts()
 if not accounts.get("connected"):
  return {"connected":False,"reason":accounts.get("reason") or accounts.get("error") or "adsense_unavailable","status_code":accounts.get("status_code")}
 account_rows=accounts.get("accounts",[]);enriched=[]
 for account in account_rows:
  name=account.get("name","");sites=await api.sites(name) if name else {"sites":[]}
  enriched.append({"account":account,"sites":sites.get("sites",[]) if sites.get("connected",True) else [],"sites_error":sites.get("error")})
 report=None
 if enriched:
  name=enriched[0]["account"].get("name","")
  if name:report=await api.report(name,28)
 return {"connected":True,"accounts":enriched,"report":report}
@app.post("/api/projects/{pid}/provision")
async def provision(pid:int,s:AsyncSession=Depends(db)):
 p=await s.scalar(select(Project).where(Project.id==pid))
 if not p:raise HTTPException(404,"project_not_found")
 from app.config import settings
 if settings().AUTONOMY_DRY_RUN:return {"status":"blocked","reason":"global_dry_run_enabled"}
 return engine.provision(p)
@app.post("/api/projects/{pid}/run")
async def run(pid:int,s:AsyncSession=Depends(db)):
 p=await s.scalar(select(Project).where(Project.id==pid))
 if not p:raise HTTPException(404,"project_not_found")
 x=Run(project_id=pid,status="running");s.add(x);await s.commit()
 try:x.state=engine.cycle(p);x.status="cycle_complete"
 except Exception as e:x.status="failed";x.error=str(e);x.state={"error":str(e)}
 x.finished_at=datetime.now(timezone.utc);await s.commit();return x.state
@app.get("/api/projects/{pid}/runs")
async def runs(pid:int,s:AsyncSession=Depends(db)):
 if not await s.scalar(select(Project).where(Project.id==pid)):raise HTTPException(404,"project_not_found")
 r=await s.execute(select(Run).where(Run.project_id==pid).order_by(Run.id.desc()).limit(50));return [{"id":x.id,"status":x.status,"error":x.error,"finished_at":x.finished_at.isoformat() if x.finished_at else None} for x in r.scalars()]
@app.get("/api/projects/{pid}/opportunities")
async def ops(pid:int,s:AsyncSession=Depends(db)):
 if not await s.scalar(select(Project).where(Project.id==pid)):raise HTTPException(404,"project_not_found")
 r=await s.execute(select(Opportunity).where(Opportunity.project_id==pid).order_by(Opportunity.score.desc()));return [{"id":x.id,"title":x.title,"score":x.score,"status":x.status} for x in r.scalars()]
@app.get("/api/projects/{pid}/analytics")
async def analytics(pid:int,s:AsyncSession=Depends(db)):
 p=await s.scalar(select(Project).where(Project.id==pid))
 if not p:raise HTTPException(404,"project_not_found")
 from app.config import settings
 cfg=settings();stored=await secret_map(pid,s);oauth=parse_google_oauth(stored);site=google_site_for_project(p,cfg.GSC_SITE_URL);gsc=GSC(oauth=oauth,site=site);gsc_rows=[];gsc_error="";gsc_connected=False
 try:gsc_rows=gsc.query(["query","page"]);gsc_connected=bool(gsc.service and gsc.site)
 except Exception as e:gsc_error=str(e)[:300]
 impressions=clicks=0.0;opportunities=[]
 for row in gsc_rows:
  imp=float(row.get("impressions",0));clk=float(row.get("clicks",0));impressions+=imp;clicks+=clk;keys=row.get("keys",[])
  if imp>0:opportunities.append({"query":keys[0] if keys else "","page":keys[1] if len(keys)>1 else "","clicks":clk,"impressions":imp,"ctr":float(row.get("ctr",0))*100,"position":float(row.get("position",0))})
 opportunities.sort(key=lambda x:(x["impressions"],-x["position"]),reverse=True)
 ga4=GA4(oauth=oauth);ga4_rows=[];ga4_error="";ga4_connected=False
 try:ga4_rows=ga4.report();ga4_connected=bool(ga4.client and ga4.pid)
 except Exception as e:ga4_error=str(e)[:300]
 users=sessions=engagement_weight=0.0
 for row in ga4_rows:
  vals=[float(v.value or 0) for v in row.metric_values];u=vals[0] if len(vals)>0 else 0;sess=vals[1] if len(vals)>1 else 0;eng=vals[2] if len(vals)>2 else 0;users+=u;sessions+=sess;engagement_weight+=eng*sess
 engagement=(engagement_weight/sessions*100) if sessions else 0
 return {"project":{"id":p.id,"name":p.name,"domain":p.domain},"google":{"oauth_connected":bool(oauth),"encrypted_storage":("google_oauth" in stored),"site":site,"ga4_property_configured":bool(cfg.GA4_PROPERTY_ID)},"gsc":{"configured":gsc_connected,"clicks":round(clicks),"impressions":round(impressions),"ctr":round(clicks/impressions*100,2) if impressions else 0,"opportunities":opportunities[:20],"error":gsc_error},"ga4":{"configured":ga4_connected,"users":round(users),"sessions":round(sessions),"engagement_rate":round(engagement,2),"error":ga4_error},"period_days":28}
def google_site_for_project(project,default_site):
 domain=(project.domain or "").strip().rstrip("/")
 if not domain:return default_site
 return domain if domain.startswith("sc-domain:") or domain.startswith("http://") or domain.startswith("https://") else "https://"+domain
async def secret_providers(pid,s):
 rows=(await s.execute(select(Secret).where(Secret.project_id==pid))).scalars().all();return {x.provider for x in rows}
async def secret_map(pid,s):
 rows=(await s.execute(select(Secret).where(Secret.project_id==pid))).scalars().all();out={}
 for x in rows:
  try:out[x.provider]=json.loads(decrypt(x.ciphertext))
  except Exception:out[x.provider]=None
 return out
def parse_google_oauth(stored):
 value=stored.get("google_oauth");return value if isinstance(value,dict) else {}

# Vercel Marketplace compatibility routes.
# Keep the existing OAuth implementation untouched; these routes only bridge
# Vercel's configured callback/configuration URLs to the existing application flow.
app.add_api_route("/api/vercel/webhook", vercel_oauth_callback, methods=["GET"], include_in_schema=False)

@app.get("/api/vercel/configure", include_in_schema=False)
async def vercel_configure(configurationId: str | None = None):
 from app.config import settings
 dashboard=settings().DASHBOARD_URL.rstrip("/")
 target=f"{dashboard}/settings?tab=vercel&configurationId={configurationId}" if configurationId else f"{dashboard}/settings?tab=vercel"
 return RedirectResponse(target, status_code=302)
