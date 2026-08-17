import re
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select
from app.db import Session
from app.models import Project
from app.auth import get_identity,ROLE_LEVEL
class SensitiveRBACMiddleware(BaseHTTPMiddleware):
    async def dispatch(self,request,call_next):
        path=request.url.path
        if request.method in {"POST","PUT","PATCH","DELETE"} and path.startswith("/api/projects/"):
            m=re.match(r"/api/projects/(\d+)(?:/|$)",path)
            if m:
                pid=int(m.group(1))
                async with Session() as s:
                    identity=await get_identity(s,request.cookies.get("awc_session"))
                    if not identity:return JSONResponse({"detail":"authentication_required"},status_code=401)
                    user,memberships=identity;project=await s.scalar(select(Project).where(Project.id==pid));membership=next((x for x in memberships if project and x.organization_id==project.organization_id),None)
                    if not membership:return JSONResponse({"detail":"project_forbidden"},status_code=403)
                    required="Admin" if any(x in path for x in ("/secrets","/provision","/deploy","/rollback")) else "Member"
                    if ROLE_LEVEL.get(membership.role,0)<ROLE_LEVEL[required]:return JSONResponse({"detail":"insufficient_role"},status_code=403)
        return await call_next(request)
def install(app):app.add_middleware(SensitiveRBACMiddleware)
