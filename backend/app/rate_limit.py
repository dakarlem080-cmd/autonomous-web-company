import time
from collections import defaultdict
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse
from app.config import settings
_BUCKET=defaultdict(list)
class PublicRateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self,request,call_next):
        if request.url.path.startswith("/api/"):
            scope="oauth" if any(x in request.url.path for x in ("/oauth/","/vercel/","/google/","/github/")) else "api"
            key=f"{scope}:{request.client.host if request.client else 'unknown'}";now=time.time();_BUCKET[key]=[t for t in _BUCKET[key] if now-t<60]
            limit=max(10,settings().RATE_LIMIT_PER_MINUTE//2) if scope=="oauth" else settings().RATE_LIMIT_PER_MINUTE
            if len(_BUCKET[key])>=limit:return JSONResponse({"detail":"rate_limit_exceeded"},status_code=429)
            _BUCKET[key].append(now)
        return await call_next(request)
def install(app):app.add_middleware(PublicRateLimitMiddleware)
