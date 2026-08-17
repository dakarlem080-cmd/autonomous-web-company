from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Employee,AIModel
from app.tool_registry import ToolRegistry

class AgentRuntime:
    def __init__(self,registry:ToolRegistry):self.registry=registry
    async def load(self,s:AsyncSession,project_id:int)->list[dict]:
        rows=(await s.execute(select(Employee,AIModel).outerjoin(AIModel,Employee.model_id==AIModel.id).where(Employee.project_id==project_id,Employee.active==True))).all()
        return [{"id":e.id,"name":e.name,"agent":e.agent,"role":e.role,"instructions":e.instructions,"objectives":e.objectives or [],"tools":e.tools or [],"permissions":e.permissions or [],"autonomy_level":e.autonomy_level,"budget_cents":e.budget_cents,"model":{"provider":m.provider,"model":m.model,"purpose":m.purpose} if m else None,"allowed_tools":[t.name for t in self.registry.list_allowed(e.permissions or [])]} for e,m in rows]
    def authorize(self,agent:dict,tool:str):
        if tool not in set(agent.get("allowed_tools",[])):raise PermissionError(f"tool_forbidden:{tool}")
        return self.registry.get(tool)
