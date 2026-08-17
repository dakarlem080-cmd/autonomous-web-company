import httpx
from app.config import settings

class DeploymentManager:
    def __init__(self):
        self.base="https://api.vercel.com";self.headers={"Authorization":f"Bearer {settings().VERCEL_TOKEN}"}
    def _check(self):
        if not settings().VERCEL_TOKEN:raise RuntimeError("VERCEL_TOKEN_not_configured")
    async def status(self,deployment_id:str):
        self._check()
        async with httpx.AsyncClient(timeout=30) as c:
            r=await c.get(f"{self.base}/v13/deployments/{deployment_id}",headers=self.headers);r.raise_for_status();return r.json()
    async def promote(self,project_id:str,deployment_id:str):
        self._check()
        async with httpx.AsyncClient(timeout=30) as c:
            r=await c.post(f"{self.base}/v10/projects/{project_id}/promote/{deployment_id}",headers=self.headers);r.raise_for_status();return r.json()
    async def rollback(self,project_id:str,deployment_id:str):
        result=await self.promote(project_id,deployment_id)
        return {"status":"rolled_back","deployment_id":deployment_id,"result":result}
