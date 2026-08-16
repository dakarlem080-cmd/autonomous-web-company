from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker,AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.config import settings
class Base(DeclarativeBase): pass

def async_url(url:str)->str:
    if url.startswith("postgres://"): return "postgresql+asyncpg://"+url[len("postgres://"):]
    if url.startswith("postgresql://"): return "postgresql+asyncpg://"+url[len("postgresql://"):]
    return url

engine=create_async_engine(async_url(settings().DATABASE_URL),pool_pre_ping=True)
Session=async_sessionmaker(engine,expire_on_commit=False,class_=AsyncSession)
async def init_db():
    from app.models import Project,Secret,Metric,Opportunity,Decision,Run,Experiment,AuditLog,Deployment
    async with engine.begin() as c: await c.run_sync(Base.metadata.create_all)
