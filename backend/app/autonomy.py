from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class AgentRole(str, Enum):
    CEO = "ceo"
    RESEARCH = "research"
    SEO = "seo"
    CONTENT = "content"
    DEVELOPER = "developer"
    QA = "qa"
    ANALYST = "analytics"
    MARKETING = "marketing"
    REVENUE = "revenue"
    SECURITY = "security"
    SUPPORT = "support"


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
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


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
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class CompanyLoop:
    def __init__(self, goals: list[BusinessGoal] | None = None):
        self.goals = goals or [
            BusinessGoal("Organic traffic growth", "organic_clicks"),
            BusinessGoal("Search visibility", "impressions"),
            BusinessGoal("Commercial performance", "revenue"),
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
            reason,
            action,
            expected_metric,
            expected_direction,
            max(0, min(1, confidence)),
            tasks,
        )
        self.history.append(decision)
        return decision

    @staticmethod
    def can_deploy(qa: dict[str, Any]) -> bool:
        return bool(qa.get("passed")) and not bool(qa.get("errors"))

    @staticmethod
    def evaluate_change(
        before: dict[str, float],
        after: dict[str, float],
        metric: str,
        direction: str,
    ) -> str:
        if metric not in before or metric not in after:
            return "insufficient_data"
        if after[metric] == before[metric]:
            return "no_change"
        improved = (
            after[metric] > before[metric]
            if direction == "increase"
            else after[metric] < before[metric]
        )
        return "improved" if improved else "regressed"
