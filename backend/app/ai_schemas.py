from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DecisionSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str = Field(min_length=1, max_length=300)
    target: str = Field(default="", max_length=1000)
    reason: str = Field(min_length=1, max_length=4000)
    evidence: list[dict] = Field(default_factory=list)
    expected_impact: float = Field(ge=-1, le=1)
    confidence: float = Field(ge=0, le=1)
    risk: Literal["low", "medium", "high"]
    reversible: bool
    approval_required: bool


class QAResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    passed: bool
    checks: dict[str, bool | float | int | str] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    executed_checks: list[str] = Field(default_factory=list)


class ToolRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool: str
    arguments: dict = Field(default_factory=dict)
