import asyncio
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from app.agent_runtime import AgentRuntime
from app.config import settings
from app.db import Session, init_db
from app.engine import Engine
from app.main import google_site_for_project, secret_map
from app.models import Project, Run
from app.queue import reserve, retry
from app.tool_registry import default_registry


async def execute_project(p, run_id: int, e: Engine, runtime: AgentRuntime):
    async with Session() as db:
        stored = await secret_map(p.id, db)
        oauth = (
            stored.get("google_oauth")
            if isinstance(stored.get("google_oauth"), dict)
            else {}
        )
        site = google_site_for_project(p, settings().GSC_SITE_URL)
        agents = await runtime.load(db, p.id)

    state = await asyncio.to_thread(e.cycle, p, oauth, site, None, agents, stored)
    async with Session() as db:
        run = await db.scalar(select(Run).where(Run.id == run_id))
        run.state = state
        run.status = "cycle_complete"
        run.finished_at = datetime.now(timezone.utc)
        await db.commit()


async def tick():
    engine = Engine()
    runtime = AgentRuntime(default_registry())
    limit = max(1, settings().AUTONOMY_MAX_PROJECTS_PER_RUN)
    async with Session() as db:
        projects = (
            (
                await db.execute(
                    select(Project).where(Project.active).order_by(Project.id)
                )
            )
            .scalars()
            .all()[:limit]
        )

    for project in projects:
        async with Session() as db:
            if await db.scalar(
                select(Run.id)
                .where(Run.project_id == project.id, Run.status == "running")
                .limit(1)
            ):
                continue
            run = Run(
                project_id=project.id,
                status="running",
                state={"trigger": "scheduler"},
            )
            db.add(run)
            await db.commit()
            await db.refresh(run)
            run_id = run.id
        try:
            await execute_project(project, run_id, engine, runtime)
        except Exception as exc:
            async with Session() as db:
                run = await db.scalar(select(Run).where(Run.id == run_id))
                run.status = "failed"
                run.error = str(exc)[:4000]
                run.finished_at = datetime.now(timezone.utc)
                await db.commit()


async def consume():
    engine = Engine()
    runtime = AgentRuntime(default_registry())
    while True:
        job = await reserve(10)
        if not job:
            continue
        try:
            if job.get("kind") != "project_run":
                raise RuntimeError("unknown_job_kind")
            project_id = int(job["payload"]["project_id"])
            async with Session() as db:
                project = await db.scalar(
                    select(Project).where(Project.id == project_id, Project.active)
                )
                if not project:
                    raise RuntimeError("project_not_found")
                if await db.scalar(
                    select(Run.id)
                    .where(Run.project_id == project_id, Run.status == "running")
                    .limit(1)
                ):
                    continue
                run = Run(
                    project_id=project_id,
                    status="running",
                    state={"trigger": "queue", "job_id": job["id"]},
                )
                db.add(run)
                await db.commit()
                await db.refresh(run)
                run_id = run.id
            await execute_project(project, run_id, engine, runtime)
        except Exception as exc:
            await retry(job, str(exc))


async def main():
    await init_db()
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        tick,
        "interval",
        hours=settings().SCHEDULER_HOURS,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    await tick()
    await consume()


if __name__ == "__main__":
    asyncio.run(main())
