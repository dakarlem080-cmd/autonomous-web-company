from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker,AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import select
from app.config import settings
class Base(DeclarativeBase): pass

def async_url(url:str)->str:
    if url.startswith("postgres://"): return "postgresql+asyncpg://"+url[len("postgres://"):]
    if url.startswith("postgresql://"): return "postgresql+asyncpg://"+url[len("postgresql://"):]
    return url

engine=create_async_engine(async_url(settings().DATABASE_URL),pool_pre_ping=True)
Session=async_sessionmaker(engine,expire_on_commit=False,class_=AsyncSession)

DEFAULT_EMPLOYEES=(
    {"name":"SEO Strategist","role":"SEO & Keyword Intelligence","agent":"seo"},
    {"name":"Growth Analyst","role":"Traffic, Analytics & Revenue","agent":"analyst"},
    {"name":"Autonomous Developer","role":"Code, UX, Performance & Deployment","agent":"developer"},
)

async def init_db():
    from app.models import Project,Secret,Metric,Opportunity,Decision,Run,Experiment,AuditLog,Deployment,Employee
    async with engine.begin() as c: await c.run_sync(Base.metadata.create_all)
    async with Session() as s:
        projects=(await s.execute(select(Project).where(Project.active==True))).scalars().all()
        for project in projects:
            existing=(await s.execute(select(Employee).where(Employee.project_id==project.id))).scalars().all()
            agents={x.agent for x in existing}
            for item in DEFAULT_EMPLOYEES:
                if item["agent"] not in agents:
                    s.add(Employee(project_id=project.id,**item))
        await s.commit()
