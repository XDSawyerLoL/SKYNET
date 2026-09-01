from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RiskAssessment:
    score: int
    level: str
    reasons: tuple[str, ...]
    requires_human: bool


class RiskBudgetEngine:
    """Deterministic plan-level risk scoring independent from the LLM."""

    RULES = {
        "delete": 25, "remove": 20, "supprimer": 25, "registry": 30, "registre": 30,
        "admin": 25, "elevat": 25, "credential": 40, "password": 40, "secret": 35,
        "payment": 45, "wallet": 45, "purchase": 40, "acheter": 40, "send": 15,
        "email": 12, "publish": 20, "post": 15, "install": 20, "powershell": 12,
        "network": 10, "internet": 10, "upload": 25, "share": 20,
    }

    def __init__(self, budget: int = 50) -> None:
        self.budget = max(0, min(int(budget), 100))

    def assess(self, goal: str, steps: list[str]) -> RiskAssessment:
        text = (goal + "\n" + "\n".join(steps)).casefold()
        score = 0
        reasons: list[str] = []
        for needle, weight in self.RULES.items():
            if needle in text:
                score += weight
                reasons.append(f"{needle}:{weight}")
        score = min(score, 100)
        if score >= 70:
            level = "critical"
        elif score >= 45:
            level = "high"
        elif score >= 20:
            level = "medium"
        else:
            level = "low"
        return RiskAssessment(score, level, tuple(reasons), score > self.budget)
