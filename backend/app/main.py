from datetime import datetime,timezone
from fastapi import FastAPI,Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db import init_db,Session
from app.models import Project,Secret,Run,Opportunity
from app.security import encrypt
from app.engine import Engine
app=FastAPI(title="Autonomous Web Company",version="5.0");engine=Engine()
class ProjectIn(BaseModel):name:str;domain:str;repo:str="";branch:str="main";goal:str="organic_traffic";language:str="en";dry_run:bool=True
class SecretIn(BaseModel):provider:str;value:str
@app.on_event("startup")
async def startup():await init_db()
async def db():
 async with Session() as s:yield s
@app.get("/health")
async def health():return {"status":"ok"}
@app.post("/api/projects")
async def create(p:ProjectIn,s:AsyncSession=Depends(db)):
 x=Project(**p.model_dump());s.add(x);await s.commit();await s.refresh(x);return {"id":x.id,"name":x.name,"domain":x.domain}
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
 r=await s.execute(select(Run).where(Run.project_id==pid).order_by(Run.id.desc()).limit(50));return [{"id":x.id,"status":x.status,"error":x.error} for x in r.scalars()]
@app.get("/api/projects/{pid}/opportunities")
async def ops(pid:int,s:AsyncSession=Depends(db)):
 r=await s.execute(select(Opportunity).where(Opportunity.project_id==pid).order_by(Opportunity.score.desc()));return [{"id":x.id,"title":x.title,"score":x.score,"status":x.status} for x in r.scalars()]
