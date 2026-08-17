import asyncio,json,re,time
from collections import defaultdict
from datetime import datetime,timezone
from fastapi import HTTPException,Request
from fastapi.responses import JSONResponse,Response
from sqlalchemy import select
from starlette.middleware.base import BaseHTTPMiddleware
from app.main import app,secret_map,google_site_for_project
from app.db import Session
from app.models import Project,User,Membership,SessionToken,AuditLog,Run,Opportunity,Decision,Task,ToolCall
from app.auth import create_user,authenticate,issue_session,get_identity,ROLE_LEVEL
from app.config import settings
from app.security import hash_token
from app.engine import Engine
from app.agent_runtime import AgentRuntime
from app.tool_registry import default_registry

PUBLIC_EXACT={"/","/health","/api/status","/api/auth/signup","/api/auth/login","/api/auth/logout"}
PUBLIC_PREFIX=("/api/google/oauth/callback","/api/github/oauth/callback","/api/vercel/oauth/callback","/api/vercel/webhook","/api/vercel/configure","/docs","/openapi.json","/redoc")
RATE_BUCKET=defaultdict(list);RUN_LOCKS:dict[int,asyncio.Lock]={};ENGINE=Engine();RUNTIME=AgentRuntime(default_registry())

def cors(response,origin):
    if origin and origin.rstrip("/") in settings().cors_origins:response.headers.update({"Access-Control-Allow-Origin":origin,"Access-Control-Allow-Credentials":"true","Vary":"Origin"})
    return response

async def execute_run(pid:int,user_id:int):
    lock=RUN_LOCKS.setdefault(pid,asyncio.Lock())
    if lock.locked():return JSONResponse({"detail":"project_run_already_active"},status_code=409)
    async with lock:
        async with Session() as s:
            p=await s.scalar(select(Project).where(Project.id==pid))
            if not p:raise HTTPException(404,"project_not_found")
            active=await s.scalar(select(Run).where(Run.project_id==pid,Run.status=="running").limit(1))
            if active:return JSONResponse({"detail":"project_run_already_active"},status_code=409)
            run=Run(project_id=pid,status="running",state={"stages":[]});s.add(run);await s.commit();await s.refresh(run)
            stored=secret_map(pid,s);oauth=stored.get("google_oauth") if isinstance(stored.get("google_oauth"),dict) else {}
            site=google_site_for_project(p,settings().GSC_SITE_URL);agents=await RUNTIME.load(s,pid)
        try:
            result=await asyncio.to_thread(ENGINE.cycle,p,oauth,site,None,agents)
            async with Session() as s:
                run=await s.scalar(select(Run).where(Run.id==run.id));run.state=result;run.status="cycle_complete";run.finished_at=datetime.now(timezone.utc)
                for item in result.get("autonomy",{}).get("decision",{}).get("evidence",[])[:50]:
                    s.add(Opportunity(project_id=pid,kind=item.get("kind","search"),title=item.get("title","opportunity"),evidence=item,score=float(item.get("score",0))))
                decision=result.get("autonomy",{}).get("decision")
                if decision:s.add(Decision(project_id=pid,agent="ceo",decision=json.dumps(decision,ensure_ascii=False),evidence={"run_id":run.id}))
                for i,t in enumerate(result.get("autonomy",{}).get("tasks",[])):
                    s.add(Task(project_id=pid,run_id=run.id,agent=t.get("agent", "unknown"),title=t.get("title",f"task-{i}"),payload=t,status="queued",priority=50))
                s.add(AuditLog(project_id=pid,user_id=user_id,actor="user",action="run.completed",details={"run_id":run.id,"status":"cycle_complete"}));await s.commit();return result
        except Exception as exc:
            async with Session() as s:
                run=await s.scalar(select(Run).where(Run.id==run.id));run.status="failed";run.error=str(exc)[:4000];run.finished_at=datetime.now(timezone.utc);run.state={"error":str(exc)[:4000]};await s.commit()
            raise

class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self,request:Request,call_next):
        path=request.url.path;origin=request.headers.get("origin","")
        if origin and origin.rstrip("/") not in settings().cors_origins:return JSONResponse({"detail":"origin_not_allowed"},status_code=403)
        if request.method=="OPTIONS":
            if not origin:return JSONResponse({"detail":"origin_required"},status_code=400)
            return cors(Response(status_code=204,headers={"Access-Control-Allow-Methods":"GET,POST,PATCH,PUT,DELETE,OPTIONS","Access-Control-Allow-Headers":"Content-Type,Authorization","Access-Control-Max-Age":"600"}),origin)
        if path in PUBLIC_EXACT or any(path.startswith(p) for p in PUBLIC_PREFIX):return cors(await call_next(request),origin)
        if path.startswith("/api/"):
            key=f"{request.client.host if request.client else 'unknown'}:{path.split('/')[2] if len(path.split('/'))>2 else 'api'}";now=time.time();RATE_BUCKET[key]=[t for t in RATE_BUCKET[key] if now-t<60]
            if len(RATE_BUCKET[key])>=settings().RATE_LIMIT_PER_MINUTE:return cors(JSONResponse({"detail":"rate_limit_exceeded"},status_code=429),origin)
            RATE_BUCKET[key].append(now)
        async with Session() as s:
            identity=await get_identity(s,request.cookies.get("awc_session"))
            if not identity:return cors(JSONResponse({"detail":"authentication_required"},status_code=401),origin)
            user,memberships=identity;request.state.user=user;request.state.memberships=memberships;org_ids=[m.organization_id for m in memberships]
            if path=="/api/projects" and request.method=="GET":
                rows=(await s.execute(select(Project).where(Project.organization_id.in_(org_ids)).order_by(Project.id.desc()))).scalars().all() if org_ids else []
                return cors(JSONResponse([{"id":x.id,"name":x.name,"domain":x.domain,"repo":x.repo,"branch":x.branch,"goal":x.goal,"language":x.language,"dry_run":x.dry_run,"active":x.active} for x in rows]),origin)
            match=re.match(r"/api/projects/(\d+)(?:/|$)",path)
            if match:
                pid=int(match.group(1));project=await s.scalar(select(Project).where(Project.id==pid));membership=next((m for m in memberships if project and m.organization_id==project.organization_id),None)
                if not project or not membership:return cors(JSONResponse({"detail":"project_forbidden"},status_code=403),origin)
                if request.method in {"POST","PUT","PATCH","DELETE"} and ROLE_LEVEL.get(membership.role,0)<ROLE_LEVEL["Member"]:return cors(JSONResponse({"detail":"insufficient_role"},status_code=403),origin)
                if path==f"/api/projects/{pid}/run" and request.method=="POST":
                    try:return cors(await execute_run(pid,user.id),origin)
                    except HTTPException as exc:return cors(JSONResponse({"detail":exc.detail},status_code=exc.status_code),origin)
                    except Exception as exc:return cors(JSONResponse({"detail":"run_failed","error":str(exc)[:500]},status_code=500),origin)
            response=await call_next(request)
            if path=="/api/projects" and request.method=="POST" and 200<=response.status_code<300:
                body=b"".join([chunk async for chunk in response.body_iterator])
                try:
                    data=json.loads(body);project=await s.scalar(select(Project).where(Project.id==int(data["id"])))
                    if project and project.organization_id is None:project.organization_id=memberships[0].organization_id if memberships else None;await s.commit()
                except Exception:await s.rollback()
                response=Response(content=body,status_code=response.status_code,headers=dict(response.headers),media_type=response.media_type)
            return cors(response,origin)

app.add_middleware(SecurityMiddleware)

@app.post("/api/auth/signup")
async def signup(payload:dict):
    async with Session() as s:
        try:
            user_count=await s.scalar(select(User.id).limit(1));user,org=await create_user(s,payload.get("email",""),payload.get("password",""),payload.get("name",""))
            if user_count is None:
                for project in (await s.execute(select(Project).where(Project.organization_id.is_(None)))).scalars():project.organization_id=org.id
            token=await issue_session(s,user.id,settings().SESSION_TTL_HOURS);s.add(AuditLog(user_id=user.id,actor="user",action="auth.signup",details={"organization_id":org.id}));await s.commit()
        except ValueError as exc:await s.rollback();raise HTTPException(400,str(exc))
    response=JSONResponse({"id":user.id,"email":user.email,"organization_id":org.id,"role":"Owner"});response.set_cookie("awc_session",token,httponly=True,secure=settings().COOKIE_SECURE,samesite="lax",max_age=settings().SESSION_TTL_HOURS*3600,path="/");return response

@app.post("/api/auth/login")
async def login(payload:dict):
    async with Session() as s:
        user=await authenticate(s,payload.get("email",""),payload.get("password",""))
        if not user:raise HTTPException(401,"invalid_credentials")
        token=await issue_session(s,user.id,settings().SESSION_TTL_HOURS);s.add(AuditLog(user_id=user.id,actor="user",action="auth.login",details={}));await s.commit()
    response=JSONResponse({"id":user.id,"email":user.email,"name":user.name});response.set_cookie("awc_session",token,httponly=True,secure=settings().COOKIE_SECURE,samesite="lax",max_age=settings().SESSION_TTL_HOURS*3600,path="/");return response

@app.post("/api/auth/logout")
async def logout(request:Request):
    token=request.cookies.get("awc_session")
    if token:
        async with Session() as s:
            row=await s.scalar(select(SessionToken).where(SessionToken.token_hash==hash_token(token),SessionToken.revoked_at.is_(None)))
            if row:row.revoked_at=datetime.now(timezone.utc);await s.commit()
    response=JSONResponse({"status":"logged_out"});response.delete_cookie("awc_session",path="/");return response

@app.get("/api/auth/me")
async def me(request:Request):
    user=request.state.user;memberships=getattr(request.state,"memberships",[]);return {"id":user.id,"email":user.email,"name":user.name,"memberships":[{"organization_id":m.organization_id,"role":m.role} for m in memberships]}

@app.get("/api/me/projects")
async def my_projects(request:Request):
    async with Session() as s:
        org_ids=[m.organization_id for m in (await s.execute(select(Membership).where(Membership.user_id==request.state.user.id))).scalars().all()]
        rows=(await s.execute(select(Project).where(Project.organization_id.in_(org_ids)).order_by(Project.id.desc()))).scalars().all() if org_ids else []
        return [{"id":x.id,"name":x.name,"domain":x.domain,"repo":x.repo,"branch":x.branch,"goal":x.goal,"language":x.language,"dry_run":x.dry_run,"active":x.active} for x in rows]

@app.on_event("startup")
async def validate_security_configuration():
    if not settings().ENCRYPTION_KEY:raise RuntimeError("ENCRYPTION_KEY is required in production")
