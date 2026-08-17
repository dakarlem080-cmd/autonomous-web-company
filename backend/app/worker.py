import asyncio
from datetime import datetime,timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from app.config import settings
from app.db import init_db,Session
from app.models import Project,Run
from app.engine import Engine
from app.main import secret_map,google_site_for_project
from app.agent_runtime import AgentRuntime
from app.tool_registry import default_registry
from app.queue import reserve,retry

async def execute_project(p,run_id:int,e:Engine,runtime:AgentRuntime):
    async with Session() as db:
        stored=secret_map(p.id,db);oauth=stored.get("google_oauth") if isinstance(stored.get("google_oauth"),dict) else {};site=google_site_for_project(p,settings().GSC_SITE_URL);agents=await runtime.load(db,p.id)
    state=await asyncio.to_thread(e.cycle,p,oauth,site,None,agents)
    async with Session() as db:
        run=await db.scalar(select(Run).where(Run.id==run_id));run.state=state;run.status="cycle_complete";run.finished_at=datetime.now(timezone.utc);await db.commit()

async def tick():
    e=Engine();runtime=AgentRuntime(default_registry());limit=max(1,settings().AUTONOMY_MAX_PROJECTS_PER_RUN)
    async with Session() as db:projects=(await db.execute(select(Project).where(Project.active==True).order_by(Project.id))).scalars().all()[:limit]
    for p in projects:
        async with Session() as db:
            if await db.scalar(select(Run.id).where(Run.project_id==p.id,Run.status=="running").limit(1)):continue
            run=Run(project_id=p.id,status="running",state={"trigger":"scheduler"});db.add(run);await db.commit();await db.refresh(run);rid=run.id
        try:await execute_project(p,rid,e,runtime)
        except Exception as exc:
            async with Session() as db:
                run=await db.scalar(select(Run).where(Run.id==rid));run.status="failed";run.error=str(exc)[:4000];run.finished_at=datetime.now(timezone.utc);await db.commit()

async def consume():
    e=Engine();runtime=AgentRuntime(default_registry())
    while True:
        job=await reserve(10)
        if not job:continue
        try:
            if job.get("kind")!="project_run":raise RuntimeError("unknown_job_kind")
            pid=int(job["payload"]["project_id"])
            async with Session() as db:
                p=await db.scalar(select(Project).where(Project.id==pid,Project.active==True))
                if not p:raise RuntimeError("project_not_found")
                if await db.scalar(select(Run.id).where(Run.project_id==pid,Run.status=="running").limit(1)):continue
                run=Run(project_id=pid,status="running",state={"trigger":"queue","job_id":job["id"]});db.add(run);await db.commit();await db.refresh(run);rid=run.id
            await execute_project(p,rid,e,runtime)
        except Exception as exc:await retry(job,str(exc))

async def main():
    await init_db();scheduler=AsyncIOScheduler();scheduler.add_job(tick,"interval",hours=settings().SCHEDULER_HOURS,max_instances=1,coalesce=True);scheduler.start();await tick();await consume()
if __name__=="__main__":asyncio.run(main())
