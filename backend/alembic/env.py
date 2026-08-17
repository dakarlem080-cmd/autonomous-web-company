from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context
from app.config import settings
from app.db import Base
import app.models  # noqa: F401

config=context.config
if config.config_file_name:fileConfig(config.config_file_name)
target_metadata=Base.metadata

def run_migrations_offline():
    context.configure(url=settings().DATABASE_URL, target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle":"named"})
    with context.begin_transaction(): context.run_migrations()

async def run_async_migrations():
    connectable=async_engine_from_config({"sqlalchemy.url": settings().DATABASE_URL.replace("postgresql://","postgresql+asyncpg://").replace("postgres://","postgresql+asyncpg://")}, prefix="sqlalchemy.", poolclass=pool.NullPool)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()

def do_run_migrations(connection: Connection):
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction(): context.run_migrations()

if context.is_offline_mode(): run_migrations_offline()
else:
    import asyncio
    asyncio.run(run_async_migrations())
