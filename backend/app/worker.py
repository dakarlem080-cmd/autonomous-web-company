import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from app.config import settings
from app.db import init_db,Session
from app.models import Project,Run
from app.engine import Engine
async def tick():
 e=Engine()
 async with Session() as db:
  r=await db.execute(select(Project).where(Project.active==True))
  for p in r.scalars().all():
   run=Run(project_id=p.id,status="running");db.add(run);await db.commit()
   try:run.state=e.cycle(p);run.status=run.state.get("status","complete")
   except Exception as ex:run.status="failed";run.error=str(ex)
   await db.commit()
async def main():
 await init_db();s=AsyncIOScheduler();s.add_job(tick,"interval",hours=settings().SCHEDULER_HOURS,max_instances=1);s.start();await tick();await asyncio.Event().wait()
if __name__=="__main__":asyncio.run(main())
