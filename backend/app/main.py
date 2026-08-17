from datetime import datetime,timezone
from fastapi import FastAPI,Depends,HTTPException
from fastapi.middleware.cors import CORSMiddleware
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
 s=settings();return {"status":"online","dry_run":s.AUTONOMY_DRY_RUN,"provisioning_enabled":s.PROVISIONING_ENABLED,"integrations":{"gsc":bool(s.GOOGLE_APPLICATION_CREDENTIALS and s.GSC_SITE_URL),"ga4":bool(s.GA4_PROPERTY_ID),"github":bool(s.GITHUB_TOKEN and s.GITHUB_OWNER),"vercel":bool(s.VERCEL_TOKEN),"domain_binding":bool(s.VERCEL_TOKEN and s.ALLOW_DOMAIN_BINDING)},"scheduler_hours":s.SCHEDULER_HOURS}
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
 secrets=(await s.execute(select(Secret).where(Secret.project_id==pid))).scalars().all()
 providers={x.provider for x in secrets}
 employees=(await s.execute(select(Employee).where(Employee.project_id==pid).order_by(Employee.id))).scalars().all()
 models=(await s.execute(select(AIModel).where(AIModel.project_id==pid).order_by(AIModel.id))).scalars().all()
 from app.config import settings
 cfg=settings()
 return {"project":{"id":p.id,"name":p.name,"domain":p.domain,"repo":p.repo,"branch":p.branch,"goal":p.goal,"language":p.language,"dry_run":p.dry_run,"active":p.active},"connections":{"google":{"connected":"google_oauth" in providers,"search_console":"google_oauth" in providers,"analytics":"google_oauth" in providers},"github":{"connected":bool(cfg.GITHUB_TOKEN and cfg.GITHUB_OWNER)},"vercel":{"connected":bool(cfg.VERCEL_TOKEN),"domain_binding":bool(cfg.VERCEL_TOKEN and cfg.ALLOW_DOMAIN_BINDING)}},"employees":[{"id":x.id,"name":x.name,"role":x.role,"agent":x.agent,"instructions":x.instructions,"objectives":x.objectives or [],"tools":x.tools or [],"permissions":x.permissions or [],"model_id":x.model_id,"autonomy_level":x.autonomy_level,"active":x.active} for x in employees],"models":[{"id":x.id,"provider":x.provider,"model":x.model,"purpose":x.purpose,"active":x.active} for x in models]}
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
 run=await s.scalar(select(Run).where(Run.project_id==pid).order_by(Run.id.desc()).limit(1));emps=(await s.execute(select(Employee).where(Employee.project_id==pid,Employee.active==True))).scalars().all()
 return {"employees":[{"id":x.id,"name":x.name,"role":x.role,"agent":x.agent,"model_id":x.model_id,"autonomy_level":x.autonomy_level} for x in emps],"latest_run":{"id":run.id,"status":run.status,"state":run.state} if run else None}
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
 p=await s.scalar(select(Project).where(Project.id==pid))
 if not p:return {"error":"project_not_found"}
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
