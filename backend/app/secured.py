import asyncio
import json
import re
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from redis.asyncio import Redis
from sqlalchemy import select
from starlette.middleware.base import BaseHTTPMiddleware

from app.agent_runtime import AgentRuntime
from app.auth import ROLE_LEVEL, authenticate, create_user, get_identity, issue_session
from app.config import settings
from app.db import Session
from app.engine import Engine
from app.main import app, google_site_for_project, secret_map
from app.models import (
    AuditLog,
    Decision,
    Membership,
    Opportunity,
    Project,
    Run,
    SessionToken,
    Task,
    User,
)
from app.security import hash_token
from app.tool_registry import default_registry


app.user_middleware = [
    middleware for middleware in app.user_middleware if middleware.cls is not CORSMiddleware
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings().cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

PUBLIC_EXACT = {
    "/",
    "/health",
    "/api/status",
    "/api/auth/signup",
    "/api/auth/login",
    "/api/auth/logout",
}
PUBLIC_PREFIX = (
    "/api/google/oauth/callback",
    "/api/github/oauth/callback",
    "/api/vercel/oauth/callback",
    "/api/vercel/webhook",
    "/api/vercel/configure",
    "/docs",
    "/openapi.json",
    "/redoc",
)
RATE_BUCKET = defaultdict(list)
RUN_LOCKS: dict[int, asyncio.Lock] = {}
ENGINE = Engine()
RUNTIME = AgentRuntime(default_registry())


async def distributed_lock(key: str, ttl: int = 1800):
    if not settings().REDIS_URL:
        return None, None
    redis = Redis.from_url(settings().REDIS_URL, decode_responses=True)
    token = uuid.uuid4().hex
    ok = await redis.set(key, token, nx=True, ex=ttl)
    await redis.aclose()
    return (token if ok else None), redis


async def release_lock(key, token):
    if not token or not settings().REDIS_URL:
        return
    redis = Redis.from_url(settings().REDIS_URL, decode_responses=True)
    script = (
        "if redis.call('get',KEYS[1])==ARGV[1] then "
        "return redis.call('del',KEYS[1]) else return 0 end"
    )
    await redis.eval(script, 1, key, token)
    await redis.aclose()


def cors(response, origin):
    if origin and origin.rstrip("/") in settings().cors_origins:
        response.headers.update(
            {
                "Access-Control-Allow-Origin": origin,
                "Access-Control-Allow-Credentials": "true",
                "Vary": "Origin",
            }
        )
    return response


async def execute_run(pid: int, user_id: int):
    lock = RUN_LOCKS.setdefault(pid, asyncio.Lock())
    if lock.locked():
        return JSONResponse({"detail": "project_run_already_active"}, status_code=409)

    async with lock:
        redis_token, _ = await distributed_lock(f"awc:project:{pid}:run")
        if settings().REDIS_URL and not redis_token:
            return JSONResponse(
                {"detail": "project_run_already_active"}, status_code=409
            )
        try:
            async with Session() as session:
                project = await session.scalar(
                    select(Project).where(Project.id == pid)
                )
                if not project:
                    raise HTTPException(404, "project_not_found")
                active = await session.scalar(
                    select(Run.id)
                    .where(Run.project_id == pid, Run.status == "running")
                    .limit(1)
                )
                if active:
                    return JSONResponse(
                        {"detail": "project_run_already_active"}, status_code=409
                    )
                run = Run(
                    project_id=pid,
                    status="running",
                    state={"trigger": "api", "stages": []},
                )
                session.add(run)
                await session.commit()
                await session.refresh(run)
                stored = secret_map(pid, session)
                oauth = (
                    stored.get("google_oauth")
                    if isinstance(stored.get("google_oauth"), dict)
                    else {}
                )
                site = google_site_for_project(
                    project, settings().GSC_SITE_URL
                )
                agents = await RUNTIME.load(session, pid)

            try:
                result = await asyncio.to_thread(
                    ENGINE.cycle,
                    project,
                    oauth,
                    site,
                    None,
                    agents,
                    stored,
                )
                async with Session() as session:
                    run = await session.scalar(select(Run).where(Run.id == run.id))
                    run.state = result
                    run.status = "cycle_complete"
                    run.finished_at = datetime.now(timezone.utc)
                    for item in result.get("autonomy", {}).get("decision", {}).get(
                        "evidence", []
                    )[:50]:
                        session.add(
                            Opportunity(
                                project_id=pid,
                                kind=item.get("kind", "search"),
                                title=item.get("title", "opportunity"),
                                evidence=item,
                                score=float(item.get("score", 0)),
                            )
                        )
                    decision = result.get("autonomy", {}).get("decision")
                    if decision:
                        session.add(
                            Decision(
                                project_id=pid,
                                agent="ceo",
                                decision=json.dumps(decision, ensure_ascii=False),
                                evidence={"run_id": run.id},
                            )
                        )
                    for task in result.get("autonomy", {}).get("tasks", []):
                        session.add(
                            Task(
                                project_id=pid,
                                run_id=run.id,
                                agent=task.get("agent", "unknown"),
                                title=task.get("title", "task"),
                                payload=task,
                                status="queued",
                                priority=int(task.get("priority", 50)),
                            )
                        )
                    session.add(
                        AuditLog(
                            project_id=pid,
                            user_id=user_id,
                            actor="user",
                            action="run.completed",
                            details={
                                "run_id": run.id,
                                "status": "cycle_complete",
                            },
                        )
                    )
                    await session.commit()
                    return result
            except Exception as exc:
                async with Session() as session:
                    run = await session.scalar(select(Run).where(Run.id == run.id))
                    run.status = "failed"
                    run.error = str(exc)[:4000]
                    run.finished_at = datetime.now(timezone.utc)
                    run.state = {"error": str(exc)[:4000]}
                    await session.commit()
                raise
        finally:
            await release_lock(f"awc:project:{pid}:run", redis_token)


class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        origin = request.headers.get("origin", "")
        if origin and origin.rstrip("/") not in settings().cors_origins:
            return JSONResponse({"detail": "origin_not_allowed"}, status_code=403)
        if path in PUBLIC_EXACT or any(
            path.startswith(prefix) for prefix in PUBLIC_PREFIX
        ):
            return cors(await call_next(request), origin)
        if path.startswith("/api/"):
            scope = path.split("/")
            key = f"{request.client.host if request.client else 'unknown'}:{scope[2] if len(scope) > 2 else 'api'}"
            now = time.time()
            RATE_BUCKET[key] = [timestamp for timestamp in RATE_BUCKET[key] if now - timestamp < 60]
            if len(RATE_BUCKET[key]) >= settings().RATE_LIMIT_PER_MINUTE:
                return cors(
                    JSONResponse({"detail": "rate_limit_exceeded"}, status_code=429),
                    origin,
                )
            RATE_BUCKET[key].append(now)
        async with Session() as session:
            identity = await get_identity(
                session, request.cookies.get("awc_session")
            )
            if not identity:
                return cors(
                    JSONResponse(
                        {"detail": "authentication_required"}, status_code=401
                    ),
                    origin,
                )
            user, memberships = identity
            request.state.user = user
            request.state.memberships = memberships
            org_ids = [membership.organization_id for membership in memberships]
            if path == "/api/projects" and request.method == "GET":
                rows = (
                    (
                        await session.execute(
                            select(Project)
                            .where(Project.organization_id.in_(org_ids))
                            .order_by(Project.id.desc())
                        )
                    )
                    .scalars()
                    .all()
                    if org_ids
                    else []
                )
                return cors(
                    JSONResponse(
                        [
                            {
                                "id": project.id,
                                "name": project.name,
                                "domain": project.domain,
                                "repo": project.repo,
                                "branch": project.branch,
                                "goal": project.goal,
                                "language": project.language,
                                "dry_run": project.dry_run,
                                "active": project.active,
                            }
                            for project in rows
                        ]
                    ),
                    origin,
                )
            match = re.match(r"/api/projects/(\d+)(?:/|$)", path)
            if match:
                pid = int(match.group(1))
                project = await session.scalar(
                    select(Project).where(Project.id == pid)
                )
                membership = next(
                    (
                        member
                        for member in memberships
                        if project
                        and member.organization_id == project.organization_id
                    ),
                    None,
                )
                if not project or not membership:
                    return cors(
                        JSONResponse(
                            {"detail": "project_forbidden"}, status_code=403
                        ),
                        origin,
                    )
                if (
                    request.method in {"POST", "PUT", "PATCH", "DELETE"}
                    and ROLE_LEVEL.get(membership.role, 0) < ROLE_LEVEL["Member"]
                ):
                    return cors(
                        JSONResponse(
                            {"detail": "insufficient_role"}, status_code=403
                        ),
                        origin,
                    )
                if path == f"/api/projects/{pid}/run" and request.method == "POST":
                    try:
                        return cors(await execute_run(pid, user.id), origin)
                    except HTTPException as exc:
                        return cors(
                            JSONResponse(
                                {"detail": exc.detail}, status_code=exc.status_code
                            ),
                            origin,
                        )
                    except Exception as exc:
                        return cors(
                            JSONResponse(
                                {"detail": "run_failed", "error": str(exc)[:500]},
                                status_code=500,
                            ),
                            origin,
                        )
            response = await call_next(request)
            if path == "/api/projects" and request.method == "POST" and 200 <= response.status_code < 300:
                body = b"".join([chunk async for chunk in response.body_iterator])
                try:
                    data = json.loads(body)
                    project = await session.scalar(
                        select(Project).where(Project.id == int(data["id"]))
                    )
                    if project and project.organization_id is None:
                        project.organization_id = (
                            memberships[0].organization_id if memberships else None
                        )
                        await session.commit()
                except Exception:
                    await session.rollback()
                response = Response(
                    content=body,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    media_type=response.media_type,
                )
            return cors(response, origin)


app.add_middleware(SecurityMiddleware)


@app.post("/api/auth/signup")
async def signup(payload: dict):
    async with Session() as session:
        try:
            user_count = await session.scalar(select(User.id).limit(1))
            user, organization = await create_user(
                session,
                payload.get("email", ""),
                payload.get("password", ""),
                payload.get("name", ""),
            )
            if user_count is None:
                projects = (
                    await session.execute(
                        select(Project).where(Project.organization_id.is_(None))
                    )
                ).scalars()
                for project in projects:
                    project.organization_id = organization.id
            token = await issue_session(
                session, user.id, settings().SESSION_TTL_HOURS
            )
            session.add(
                AuditLog(
                    user_id=user.id,
                    actor="user",
                    action="auth.signup",
                    details={"organization_id": organization.id},
                )
            )
            await session.commit()
        except ValueError as exc:
            await session.rollback()
            raise HTTPException(400, str(exc)) from exc
    response = JSONResponse(
        {
            "id": user.id,
            "email": user.email,
            "organization_id": organization.id,
            "role": "Owner",
        }
    )
    response.set_cookie(
        "awc_session",
        token,
        httponly=True,
        secure=settings().COOKIE_SECURE,
        samesite="lax",
        max_age=settings().SESSION_TTL_HOURS * 3600,
        path="/",
    )
    return response


@app.post("/api/auth/login")
async def login(payload: dict):
    async with Session() as session:
        user = await authenticate(
            session,
            payload.get("email", ""),
            payload.get("password", ""),
        )
        if not user:
            raise HTTPException(401, "invalid_credentials")
        token = await issue_session(
            session, user.id, settings().SESSION_TTL_HOURS
        )
        session.add(
            AuditLog(user_id=user.id, actor="user", action="auth.login", details={})
        )
        await session.commit()
    response = JSONResponse(
        {"id": user.id, "email": user.email, "name": user.name}
    )
    response.set_cookie(
        "awc_session",
        token,
        httponly=True,
        secure=settings().COOKIE_SECURE,
        samesite="lax",
        max_age=settings().SESSION_TTL_HOURS * 3600,
        path="/",
    )
    return response


@app.post("/api/auth/logout")
async def logout(request: Request):
    token = request.cookies.get("awc_session")
    if token:
        async with Session() as session:
            row = await session.scalar(
                select(SessionToken).where(
                    SessionToken.token_hash == hash_token(token),
                    SessionToken.revoked_at.is_(None),
                )
            )
            if row:
                row.revoked_at = datetime.now(timezone.utc)
                await session.commit()
    response = JSONResponse({"status": "logged_out"})
    response.delete_cookie("awc_session", path="/")
    return response


@app.get("/api/auth/me")
async def me(request: Request):
    user = request.state.user
    memberships = getattr(request.state, "memberships", [])
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "memberships": [
            {"organization_id": membership.organization_id, "role": membership.role}
            for membership in memberships
        ],
    }


@app.get("/api/me/projects")
async def my_projects(request: Request):
    async with Session() as session:
        memberships = (
            await session.execute(
                select(Membership).where(Membership.user_id == request.state.user.id)
            )
        ).scalars().all()
        org_ids = [membership.organization_id for membership in memberships]
        rows = (
            (
                await session.execute(
                    select(Project)
                    .where(Project.organization_id.in_(org_ids))
                    .order_by(Project.id.desc())
                )
            )
            .scalars()
            .all()
            if org_ids
            else []
        )
        return [
            {
                "id": project.id,
                "name": project.name,
                "domain": project.domain,
                "repo": project.repo,
                "branch": project.branch,
                "goal": project.goal,
                "language": project.language,
                "dry_run": project.dry_run,
                "active": project.active,
            }
            for project in rows
        ]


@app.on_event("startup")
async def validate_security_configuration():
    if not settings().ENCRYPTION_KEY:
        raise RuntimeError("ENCRYPTION_KEY is required in production")
