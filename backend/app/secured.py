import json
import re
import time
from collections import defaultdict
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from starlette.middleware.base import BaseHTTPMiddleware
from app.main import app
from app.db import Session
from app.models import Project, User, Organization, Membership, SessionToken, AuditLog
from app.auth import create_user, authenticate, issue_session, get_identity, ROLE_LEVEL
from app.config import settings
from app.security import hash_token

PUBLIC_EXACT = {"/", "/health", "/api/status", "/api/auth/signup", "/api/auth/login", "/api/auth/logout"}
PUBLIC_PREFIX = ("/api/google/oauth/callback", "/api/github/oauth/callback", "/api/vercel/oauth/callback", "/api/vercel/webhook", "/api/vercel/configure", "/docs", "/openapi.json", "/redoc")
RATE_BUCKET = defaultdict(list)

class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if request.method == "OPTIONS": return await call_next(request)
        origin = request.headers.get("origin", "")
        if origin and origin.rstrip("/") not in settings().cors_origins:
            return JSONResponse({"detail":"origin_not_allowed"}, status_code=403)
        if path in PUBLIC_EXACT or any(path.startswith(p) for p in PUBLIC_PREFIX):
            return await call_next(request)
        # Fixed-window limiter. Production deployments should share this state via Redis.
        if path.startswith("/api/"):
            key = f"{request.client.host if request.client else 'unknown'}:{path.split('/')[2] if len(path.split('/'))>2 else 'api'}"
            now = time.time(); RATE_BUCKET[key] = [t for t in RATE_BUCKET[key] if now-t < 60]
            if len(RATE_BUCKET[key]) >= settings().RATE_LIMIT_PER_MINUTE: return JSONResponse({"detail":"rate_limit_exceeded"}, status_code=429)
            RATE_BUCKET[key].append(now)
        token = request.cookies.get("awc_session")
        async with Session() as s:
            identity = await get_identity(s, token)
            if not identity: return JSONResponse({"detail":"authentication_required"}, status_code=401)
            user, memberships = identity
            request.state.user = user
            request.state.memberships = memberships
            match = re.match(r"/api/projects/(\d+)(?:/|$)", path)
            if match:
                pid = int(match.group(1))
                project = await s.scalar(select(Project).where(Project.id == pid))
                membership = next((m for m in memberships if project and m.organization_id == project.organization_id), None)
                if not project or not membership: return JSONResponse({"detail":"project_forbidden"}, status_code=403)
                if request.method in {"POST","PUT","PATCH","DELETE"} and ROLE_LEVEL.get(membership.role,0) < ROLE_LEVEL["Member"]:
                    return JSONResponse({"detail":"insufficient_role"}, status_code=403)
            response = await call_next(request)
            return response

app.add_middleware(SecurityMiddleware)

@app.post("/api/auth/signup")
async def signup(payload: dict, request: Request):
    async with Session() as s:
        try:
            user_count = await s.scalar(select(User.id).limit(1))
            user, org = await create_user(s, payload.get("email",""), payload.get("password",""), payload.get("name", ""))
            # One-time bootstrap: migrate pre-auth projects to the first owner's organization.
            if user_count is None:
                for project in (await s.execute(select(Project).where(Project.organization_id.is_(None)))).scalars(): project.organization_id = org.id
            token = await issue_session(s, user.id, settings().SESSION_TTL_HOURS)
            s.add(AuditLog(user_id=user.id, actor="user", action="auth.signup", details={"organization_id":org.id}))
            await s.commit()
        except ValueError as exc:
            await s.rollback(); raise HTTPException(400, str(exc))
    response = JSONResponse({"id":user.id,"email":user.email,"organization_id":org.id,"role":"Owner"})
    response.set_cookie("awc_session", token, httponly=True, secure=settings().COOKIE_SECURE, samesite="lax", max_age=settings().SESSION_TTL_HOURS*3600, path="/")
    return response

@app.post("/api/auth/login")
async def login(payload: dict):
    async with Session() as s:
        user = await authenticate(s, payload.get("email",""), payload.get("password",""))
        if not user: raise HTTPException(401, "invalid_credentials")
        token = await issue_session(s, user.id, settings().SESSION_TTL_HOURS)
        s.add(AuditLog(user_id=user.id, actor="user", action="auth.login", details={"ip":"redacted"})); await s.commit()
    response = JSONResponse({"id":user.id,"email":user.email,"name":user.name})
    response.set_cookie("awc_session", token, httponly=True, secure=settings().COOKIE_SECURE, samesite="lax", max_age=settings().SESSION_TTL_HOURS*3600, path="/")
    return response

@app.post("/api/auth/logout")
async def logout(request: Request):
    token=request.cookies.get("awc_session")
    async with Session() as s:
        if token:
            row=await s.scalar(select(SessionToken).where(SessionToken.token_hash==hash_token(token), SessionToken.revoked_at.is_(None)))
            if row: row.revoked_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc)
            await s.commit()
    response=JSONResponse({"status":"logged_out"}); response.delete_cookie("awc_session", path="/"); return response

@app.get("/api/auth/me")
async def me(request: Request):
    user=getattr(request.state,"user",None)
    if not user: raise HTTPException(401,"authentication_required")
    return {"id":user.id,"email":user.email,"name":user.name}

# Replace the unsafe unscoped project list with an organization-scoped endpoint.
@app.get("/api/me/projects")
async def my_projects(request: Request):
    user=request.state.user
    async with Session() as s:
        org_ids=[m.organization_id for m in (await s.execute(select(Membership).where(Membership.user_id==user.id))).scalars().all()]
        rows=(await s.execute(select(Project).where(Project.organization_id.in_(org_ids)).order_by(Project.id.desc()))).scalars().all() if org_ids else []
        return [{"id":x.id,"name":x.name,"domain":x.domain,"repo":x.repo,"branch":x.branch,"goal":x.goal,"language":x.language,"dry_run":x.dry_run,"active":x.active} for x in rows]

# Ensure production refuses to start with an unsafe encryption setup.
@app.on_event("startup")
async def validate_security_configuration():
    s=settings()
    if not s.ENCRYPTION_KEY: raise RuntimeError("ENCRYPTION_KEY is required in production")
    if s.COOKIE_SECURE is False and s.DASHBOARD_URL.startswith("https://"): raise RuntimeError("COOKIE_SECURE cannot be disabled for HTTPS production")
