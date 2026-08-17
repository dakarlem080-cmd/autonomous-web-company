from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker,AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import select,text
from app.config import settings
class Base(DeclarativeBase): pass

def async_url(url:str)->str:
    if url.startswith("postgres://"): return "postgresql+asyncpg://"+url[len("postgres://"):]
    if url.startswith("postgresql://"): return "postgresql+asyncpg://"+url[len("postgresql://"):]
    return url
engine=create_async_engine(async_url(settings().DATABASE_URL),pool_pre_ping=True)
Session=async_sessionmaker(engine,expire_on_commit=False,class_=AsyncSession)
DEFAULT_EMPLOYEES=(
 {"name":"General Manager","role":"Company Operations Manager","agent":"manager","instructions":"Manage the company toward its goals. Delegate work, review evidence, coordinate employees, and never claim success without evidence.","objectives":["grow organic traffic","increase revenue"],"tools":["analytics","search_console","employee_registry"],"permissions":["read","analyze","delegate","review"],"autonomy_level":"execute"},
 {"name":"SEO Strategist","role":"SEO & Keyword Intelligence","agent":"seo","instructions":"Find and execute evidence-backed opportunities in organic search. Analyze queries, intent, competitors and technical SEO. Escalate code changes to the manager when outside your permissions.","objectives":["increase organic clicks","improve rankings"],"tools":["search_console","browser","search"],"permissions":["read","analyze","create_tasks"],"autonomy_level":"execute"},
 {"name":"Growth Analyst","role":"Traffic, Analytics & Revenue","agent":"analyst","instructions":"Measure traffic, search visibility, engagement and commercial outcomes. Compare before and after changes and report evidence to the manager.","objectives":["increase qualified traffic","increase conversions"],"tools":["analytics","search_console"],"permissions":["read","analyze","create_tasks"],"autonomy_level":"execute"},
 {"name":"Autonomous Developer","role":"Code, UX, Performance & Deployment","agent":"developer","instructions":"Implement manager-approved changes directly in the website. Test builds, fix regressions and provide evidence before deployment.","objectives":["improve website","ship safe changes"],"tools":["github","vercel","browser","code_execution"],"permissions":["read","write","build","test","deploy","rollback"],"autonomy_level":"execute"},
)
async def init_db():
 from app.models import Project,Secret,Metric,Opportunity,Decision,Run,Experiment,AuditLog,Deployment,Employee
 async with engine.begin() as c:
  await c.run_sync(Base.metadata.create_all)
  # Lightweight upgrade for existing PostgreSQL databases created before employee configuration existed.
  if "postgresql" in str(engine.url):
   for sql in ("ALTER TABLE employees ADD COLUMN IF NOT EXISTS instructions TEXT DEFAULT ''","ALTER TABLE employees ADD COLUMN IF NOT EXISTS objectives JSON DEFAULT '[]'","ALTER TABLE employees ADD COLUMN IF NOT EXISTS tools JSON DEFAULT '[]'","ALTER TABLE employees ADD COLUMN IF NOT EXISTS permissions JSON DEFAULT '[]'","ALTER TABLE employees ADD COLUMN IF NOT EXISTS model_id INTEGER","ALTER TABLE employees ADD COLUMN IF NOT EXISTS autonomy_level VARCHAR(40) DEFAULT 'execute'"):
    await c.execute(text(sql))
 async with Session() as s:
  projects=(await s.execute(select(Project).where(Project.active==True))).scalars().all()
  for project in projects:
   existing=(await s.execute(select(Employee).where(Employee.project_id==project.id))).scalars().all();agents={x.agent for x in existing}
   for item in DEFAULT_EMPLOYEES:
    if item["agent"] not in agents:s.add(Employee(project_id=project.id,**item))
  await s.commit()
