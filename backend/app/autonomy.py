from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class AgentRole(str, Enum):
    CEO = "ceo"
    SEO = "seo"
    ANALYST = "analyst"
    DEVELOPER = "developer"


class GoalStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    ACHIEVED = "achieved"
    FAILED = "failed"


class TaskStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    BLOCKED = "blocked"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class BusinessGoal:
    name: str
    metric: str
    direction: str = "increase"
    target: float | None = None
    status: GoalStatus = GoalStatus.ACTIVE
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class AutonomousTask:
    title: str
    agent: AgentRole
    objective: str
    priority: int = 50
    depends_on: list[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.QUEUED
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class Decision:
    reason: str
    action: str
    expected_metric: str
    expected_direction: str
    confidence: float
    tasks: list[AutonomousTask]
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class CompanyLoop:
    """Deterministic orchestration contract for the autonomous operating loop.

    Agents return evidence and proposed actions; the CEO decides what is worth
    executing. Deployment must only happen after evidence-backed QA succeeds.
    """

    def __init__(self, goals: list[BusinessGoal] | None = None) -> None:
        self.goals = goals or [
            BusinessGoal("Organic traffic growth", "organic_clicks", "increase"),
            BusinessGoal("Search visibility", "impressions", "increase"),
            BusinessGoal("Commercial performance", "revenue", "increase"),
        ]
        self.history: list[Decision] = []

    def create_decision(
        self,
        reason: str,
        action: str,
        expected_metric: str,
        expected_direction: str,
        confidence: float,
        tasks: list[AutonomousTask],
    ) -> Decision:
        decision = Decision(
            reason=reason,
            action=action,
            expected_metric=expected_metric,
            expected_direction=expected_direction,
            confidence=max(0.0, min(1.0, confidence)),
            tasks=tasks,
        )
        self.history.append(decision)
        return decision

    @staticmethod
    def can_deploy(qa: dict[str, Any]) -> bool:
        """Deployment gate: never report success without real QA evidence."""
        return bool(qa.get("executed")) and bool(qa.get("passed")) and not bool(qa.get("blocking_errors"))

    @staticmethod
    def evaluate_change(before: dict[str, float], after: dict[str, float], metric: str, direction: str) -> str:
        if metric not in before or metric not in after:
            return "insufficient_data"
        if after[metric] == before[metric]:
            return "no_change"
        improved = after[metric] > before[metric] if direction == "increase" else after[metric] < before[metric]
        return "improved" if improved else "regressed"
