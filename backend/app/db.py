from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    pass


def async_url(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url[len("postgresql://") :]
    return url


engine = create_async_engine(async_url(settings().DATABASE_URL), pool_pre_ping=True)
Session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

DEFAULT_EMPLOYEES = (
    {
        "name": "CEO / Strategy",
        "role": "Company Strategy",
        "agent": "ceo",
        "instructions": "Read persistent evidence and metrics, prioritize opportunities, create tasks, set risk and approval requirements, and never claim success without evidence.",
        "objectives": ["grow qualified traffic", "increase revenue"],
        "tools": ["analytics", "search_console", "planning"],
        "permissions": ["read", "analyze", "delegate", "review"],
        "autonomy_level": "execute",
    },
    {
        "name": "Research Agent",
        "role": "Research & Evidence",
        "agent": "research",
        "instructions": "Perform real web research, competitor analysis and source validation. Persist evidence and cite important claims.",
        "objectives": ["discover opportunities", "validate sources"],
        "tools": ["search_web", "crawl_page"],
        "permissions": ["read", "research", "create_tasks"],
        "autonomy_level": "execute",
    },
    {
        "name": "SEO Agent",
        "role": "SEO & Keyword Intelligence",
        "agent": "seo",
        "instructions": "Use Search Console and site evidence to find ranking, CTR, content-gap and internal-link opportunities. Persist every opportunity.",
        "objectives": ["increase organic clicks", "improve rankings"],
        "tools": ["search_console", "analytics", "crawl_page"],
        "permissions": ["read", "analyze", "create_tasks"],
        "autonomy_level": "execute",
    },
    {
        "name": "Content Agent",
        "role": "Evidence-backed Content",
        "agent": "content",
        "instructions": "Research, outline, draft, fact-check, optimize and prepare content. Important claims must have sources.",
        "objectives": ["publish useful content", "increase topical coverage"],
        "tools": ["search_web", "read_github", "publish_content"],
        "permissions": ["read", "write_content", "publish"],
        "autonomy_level": "execute",
    },
    {
        "name": "Developer Agent",
        "role": "Code & Deployment",
        "agent": "developer",
        "instructions": "Implement bounded changes, run tests/build/security checks, create a branch and PR, and deploy only after QA passes.",
        "objectives": ["ship safe changes", "improve site"],
        "tools": [
            "read_github",
            "write_github",
            "run_tests",
            "run_build",
            "create_pr",
            "deploy_vercel",
            "rollback_deployment",
        ],
        "permissions": ["read", "write", "build", "test", "deploy", "rollback"],
        "autonomy_level": "execute",
    },
    {
        "name": "QA Agent",
        "role": "Quality & Security",
        "agent": "qa",
        "instructions": "Never report passed without executing checks. Validate build, links, metadata, canonical, robots, sitemap, JSON-LD, security and deployment smoke tests.",
        "objectives": ["prevent regressions", "block unsafe releases"],
        "tools": [
            "run_tests",
            "run_build",
            "run_lighthouse",
            "security_scan",
            "check_deployment",
        ],
        "permissions": ["read", "test", "block_release"],
        "autonomy_level": "execute",
    },
    {
        "name": "Analytics Agent",
        "role": "Measurement & Learning",
        "agent": "analytics",
        "instructions": "Persist metrics with source and timestamp, compare baselines and outcomes, and feed evidence into the next autonomous cycle.",
        "objectives": ["measure impact", "learn from experiments"],
        "tools": ["search_console", "get_ga4", "analytics"],
        "permissions": ["read", "analyze", "measure"],
        "autonomy_level": "execute",
    },
)


async def init_db():
    # Schema is managed exclusively by Alembic before the application starts.
    async with Session() as session:
        from app.models import Employee, Project

        projects = (
            (await session.execute(select(Project).where(Project.active)))
            .scalars()
            .all()
        )
        for project in projects:
            existing = (
                (
                    await session.execute(
                        select(Employee).where(Employee.project_id == project.id)
                    )
                )
                .scalars()
                .all()
            )
            agents = {employee.agent for employee in existing}
            for item in DEFAULT_EMPLOYEES:
                if item["agent"] not in agents:
                    session.add(Employee(project_id=project.id, **item))
        await session.commit()
