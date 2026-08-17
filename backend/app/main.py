from datetime import datetime,timezone
from fastapi import FastAPI,Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db import init_db,Session
from app.models import Project,Secret,Run,Opportunity
from app.security import encrypt
from app.engine import Engine
from app.integrations import GSC,GA4

app=FastAPI(title="Autonomous Web Company",version="5.2")
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_credentials=False,allow_methods=["*"],allow_headers=["*"])
engine=Engine()
class ProjectIn(BaseModel):name:str;domain:str;repo:str="";branch:str="main";goal:str="organic_traffic";language:str="en";dry_run:bool=True
class SecretIn(BaseModel):provider:str;value:str

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
 s=settings()
 return {"status":"online","dry_run":s.AUTONOMY_DRY_RUN,"integrations":{"gsc":bool(s.GOOGLE_APPLICATION_CREDENTIALS and s.GSC_SITE_URL),"ga4":bool(s.GA4_PROPERTY_ID),"github":bool(s.GITHUB_TOKEN and s.GITHUB_OWNER and s.GITHUB_REPO),"vercel":bool(s.VERCEL_TOKEN)},"scheduler_hours":s.SCHEDULER_HOURS}

@app.post("/api/projects")
async def create(p:ProjectIn,s:AsyncSession=Depends(db)):
 x=Project(**p.model_dump());s.add(x);await s.commit();await s.refresh(x);return {"id":x.id,"name":x.name,"domain":x.domain,"dry_run":x.dry_run}

@app.get("/api/projects")
async def projects(s:AsyncSession=Depends(db)):
 r=await s.execute(select(Project).order_by(Project.id.desc()));return [{"id":x.id,"name":x.name,"domain":x.domain,"dry_run":x.dry_run,"active":x.active} for x in r.scalars()]

@app.post("/api/projects/{pid}/secrets")
async def secret(pid:int,p:SecretIn,s:AsyncSession=Depends(db)):
 s.add(Secret(project_id=pid,provider=p.provider,ciphertext=encrypt(p.value)));await s.commit();return {"status":"stored"}

@app.post("/api/projects/{pid}/run")
async def run(pid:int,s:AsyncSession=Depends(db)):
 r=await s.execute(select(Project).where(Project.id==pid));p=r.scalar_one_or_none()
 if not p:return {"error":"project_not_found"}
 x=Run(project_id=pid,status="running");s.add(x);await s.commit()
 try:x.state=engine.cycle(p);x.status=x.state.get("status","complete")
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
 gsc_rows=GSC().query(["query","page"])
 impressions=clicks=0.0
 opportunities=[]
 for row in gsc_rows:
  imp=float(row.get("impressions",0));clk=float(row.get("clicks",0));impressions+=imp;clicks+=clk
  keys=row.get("keys",[])
  if imp>0: opportunities.append({"query":keys[0] if keys else "","page":keys[1] if len(keys)>1 else "","clicks":clk,"impressions":imp,"ctr":float(row.get("ctr",0))*100,"position":float(row.get("position",0))})
 opportunities.sort(key=lambda x:(x["impressions"],-x["position"]),reverse=True)
 ga4_rows=GA4().report()
 users=sessions=0.0;engagement_weight=0.0
 for row in ga4_rows:
  vals=[float(v.value or 0) for v in row.metric_values]
  u=vals[0] if len(vals)>0 else 0;sess=vals[1] if len(vals)>1 else 0;eng=vals[2] if len(vals)>2 else 0
  users+=u;sessions+=sess;engagement_weight+=eng*sess
 engagement=(engagement_weight/sessions*100) if sessions else 0
 return {"project":{"id":p.id,"name":p.name,"domain":p.domain},"gsc":{"configured":bool(GSC().service),"clicks":round(clicks),"impressions":round(impressions),"ctr":round(clicks/impressions*100,2) if impressions else 0,"opportunities":opportunities[:20]},"ga4":{"configured":bool(GA4().client),"users":round(users),"sessions":round(sessions),"engagement_rate":round(engagement,2)},"period_days":28}
