from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AIModel, Employee
from app.tool_registry import ToolRegistry


class AgentRuntime:
    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    async def load(self, s: AsyncSession, project_id: int) -> list[dict]:
        rows = (
            await s.execute(
                select(Employee, AIModel)
                .outerjoin(AIModel, Employee.model_id == AIModel.id)
                .where(Employee.project_id == project_id, Employee.active)
            )
        ).all()
        return [
            {
                "id": employee.id,
                "name": employee.name,
                "agent": employee.agent,
                "role": employee.role,
                "instructions": employee.instructions,
                "objectives": employee.objectives or [],
                "tools": employee.tools or [],
                "permissions": employee.permissions or [],
                "autonomy_level": employee.autonomy_level,
                "budget_cents": employee.budget_cents,
                "model": (
                    {
                        "provider": model.provider,
                        "model": model.model,
                        "purpose": model.purpose,
                    }
                    if model
                    else None
                ),
                "allowed_tools": [
                    tool.name
                    for tool in self.registry.list_allowed(employee.permissions or [])
                ],
            }
            for employee, model in rows
        ]

    def authorize(self, agent: dict, tool: str):
        if tool not in set(agent.get("allowed_tools", [])):
            raise PermissionError(f"tool_forbidden:{tool}")
        return self.registry.get(tool)
