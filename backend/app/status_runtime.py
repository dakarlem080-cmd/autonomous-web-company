from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.db import Session


class RuntimeStatusMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.url.path != "/api/status":
            return await call_next(request)

        s = settings()
        db_ok = False
        try:
            async with Session() as db:
                await db.execute(text("SELECT 1"))
                db_ok = True
        except Exception:
            pass

        return JSONResponse(
            {
                "status": "online" if db_ok else "degraded",
                "database": db_ok,
                "dry_run": s.AUTONOMY_DRY_RUN,
                "provisioning_enabled": s.PROVISIONING_ENABLED,
                "scheduler_hours": s.SCHEDULER_HOURS,
                "max_projects_per_run": s.AUTONOMY_MAX_PROJECTS_PER_RUN,
                "integrations": {
                    "gsc": bool(s.GOOGLE_CLIENT_ID and s.GOOGLE_CLIENT_SECRET),
                    "ga4": bool(s.GOOGLE_CLIENT_ID and s.GOOGLE_CLIENT_SECRET),
                    "github": bool(s.GITHUB_CLIENT_ID and s.GITHUB_CLIENT_SECRET),
                    "vercel": bool(s.VERCEL_CLIENT_ID and s.VERCEL_CLIENT_SECRET),
                },
            }
        )


def install(app):
    app.add_middleware(RuntimeStatusMiddleware)
