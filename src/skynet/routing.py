from __future__ import annotations

from dataclasses import dataclass
import hashlib

from .ollama import OllamaClient, OllamaError


@dataclass(slots=True)
class RouteDecision:
    model: str
    reason: str


class ModelRouter:
    """Local model router with measurable canary/promotion support."""

    def __init__(self, base_url: str, default_model: str, candidates: list[str] | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        ordered = [default_model] + [m for m in (candidates or []) if m and m != default_model]
        self.candidates = list(dict.fromkeys(ordered))
        self.preferred_model: str | None = None
        self.canary_model: str | None = None
        self.canary_ratio = 0.20
        self.last_route = RouteDecision(default_model, "default")
        self._clients: dict[str, OllamaClient] = {}

    def configure_deployment(self, model: str | None, status: str | None, canary_ratio: float = 0.20) -> None:
        self.preferred_model = None
        self.canary_model = None
        self.canary_ratio = max(0.0, min(float(canary_ratio), 0.5))
        if not model or model not in self.candidates:
            return
        if status == "canary":
            self.canary_model = model
        elif status in {"active", "rolled_back"}:
            self.preferred_model = model

    def _client(self, model: str) -> OllamaClient:
        if model not in self._clients:
            self._clients[model] = OllamaClient(self.base_url, model)
        return self._clients[model]

    def list_models(self) -> list[str]:
        return self._client(self.default_model).list_models()

    @staticmethod
    def _last_user_text(messages: list[dict]) -> str:
        for message in reversed(messages):
            if message.get("role") == "user":
                return str(message.get("content", ""))
        return ""

    def _in_canary_bucket(self, text: str) -> bool:
        if not self.canary_model or self.canary_ratio <= 0:
            return False
        digest = hashlib.sha256(text.encode("utf-8", errors="ignore")).digest()
        bucket = int.from_bytes(digest[:4], "big") / 0xFFFFFFFF
        return bucket < self.canary_ratio

    def decide(self, text: str, installed: list[str] | None = None) -> RouteDecision:
        available = set(installed or self.candidates)
        choices = [m for m in self.candidates if m in available]
        if not choices:
            return RouteDecision(self.default_model, "fallback: configured default")

        if self.canary_model in available and self._in_canary_bucket(text):
            return RouteDecision(str(self.canary_model), f"evolution canary {self.canary_ratio:.0%}")

        lower = text.lower()
        coding = any(k in lower for k in ("code", "python", "javascript", "typescript", "bug", "compile", "github", "powershell", "fonction", "script"))
        reasoning = any(k in lower for k in ("analyse", "raisonne", "compare", "architecture", "plan", "diagnostic", "pourquoi"))

        scored: list[tuple[int, str, str]] = []
        for model in choices:
            name = model.lower()
            score = 100 if model == self.default_model else 0
            reasons: list[str] = []
            if model == self.preferred_model:
                score += 130
                reasons.append("measured preferred")
            if coding and any(k in name for k in ("coder", "code", "dev")):
                score += 180
                reasons.append("coding specialist")
            if reasoning and any(k in name for k in ("qwen3", "reason", "r1", "deepseek")):
                score += 50
                reasons.append("reasoning fit")
            if model == self.default_model:
                reasons.append("default")
            scored.append((score, model, ", ".join(reasons) or "candidate"))
        scored.sort(key=lambda item: (-item[0], self.candidates.index(item[1])))
        best = scored[0]
        return RouteDecision(best[1], best[2])

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        text = self._last_user_text(messages)
        try:
            installed = self.list_models()
        except OllamaError:
            installed = self.candidates
        decision = self.decide(text, installed)
        self.last_route = decision
        try:
            return self._client(decision.model).chat(messages, tools=tools)
        except OllamaError:
            if decision.model == self.default_model:
                raise
            self.last_route = RouteDecision(self.default_model, f"fallback after {decision.model} failure")
            return self._client(self.default_model).chat(messages, tools=tools)
