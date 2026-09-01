from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import hashlib
import time

from .ollama import OllamaClient, OllamaError
from .resources import ResourceProfiler, ResourceSnapshot
from .telemetry import ModelTelemetryStore


@dataclass(slots=True)
class RouteDecision:
    model: str
    reason: str


class ModelRouter:
    """Local model router with measured quality, efficiency and canary support."""

    def __init__(
        self,
        base_url: str,
        default_model: str,
        candidates: list[str] | None = None,
        telemetry: ModelTelemetryStore | None = None,
        profiler: ResourceProfiler | None = None,
        quality_lookup: Callable[[str], dict | None] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        ordered = [default_model] + [m for m in (candidates or []) if m and m != default_model]
        self.candidates = list(dict.fromkeys(ordered))
        self.telemetry = telemetry
        self.profiler = profiler
        self.quality_lookup = quality_lookup
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

    @staticmethod
    def task_class(text: str) -> str:
        lower = text.casefold()
        if any(k in lower for k in ("code", "python", "javascript", "typescript", "bug", "compile", "github", "powershell", "fonction", "script")):
            return "coding"
        if any(k in lower for k in ("analyse", "raisonne", "compare", "architecture", "plan", "diagnostic", "pourquoi")):
            return "reasoning"
        if any(k in lower for k in ("image", "photo", "capture", "vision", "écran", "screen")):
            return "vision"
        return "general"

    def _in_canary_bucket(self, text: str) -> bool:
        if not self.canary_model or self.canary_ratio <= 0:
            return False
        digest = hashlib.sha256(text.encode("utf-8", errors="ignore")).digest()
        bucket = int.from_bytes(digest[:4], "big") / 0xFFFFFFFF
        return bucket < self.canary_ratio

    def _resource_snapshot(self) -> ResourceSnapshot | None:
        if self.profiler is None:
            return None
        try:
            return self.profiler.snapshot()
        except Exception:
            return None

    def decide(self, text: str, installed: list[str] | None = None) -> RouteDecision:
        available = set(installed or self.candidates)
        choices = [m for m in self.candidates if m in available]
        if not choices:
            return RouteDecision(self.default_model, "fallback: configured default")

        if self.canary_model in available and self._in_canary_bucket(text):
            return RouteDecision(str(self.canary_model), f"evolution canary {self.canary_ratio:.0%}")

        task = self.task_class(text)
        snapshot = self._resource_snapshot()
        scored: list[tuple[float, str, str]] = []
        for model in choices:
            name = model.lower()
            score = 100.0 if model == self.default_model else 0.0
            reasons: list[str] = []

            if model == self.preferred_model:
                score += 130.0
                reasons.append("measured preferred")
            if task == "coding" and any(k in name for k in ("coder", "code", "dev")):
                score += 180.0
                reasons.append("coding specialist")
            if task == "reasoning" and any(k in name for k in ("qwen3", "reason", "r1", "deepseek")):
                score += 50.0
                reasons.append("reasoning fit")

            if self.quality_lookup is not None:
                try:
                    quality = self.quality_lookup(model)
                except Exception:
                    quality = None
                if quality:
                    mean_score = float(quality.get("mean_score", 0.0))
                    pass_rate = float(quality.get("pass_rate", 0.0))
                    safety_failures = int(quality.get("safety_failures", 0))
                    score += mean_score * 140.0 + pass_rate * 60.0
                    if safety_failures:
                        score -= 300.0
                    reasons.append(f"quality={mean_score:.2f}/{pass_rate:.0%}")

            stats = self.telemetry.stats(model, task) if self.telemetry is not None else None
            if stats is None and self.telemetry is not None:
                stats = self.telemetry.stats(model)
            if stats is not None:
                score -= min(70.0, stats.avg_latency_s * 4.0)
                reasons.append(f"lat={stats.avg_latency_s:.1f}s")
                if stats.avg_energy_wh is not None:
                    score -= min(40.0, stats.avg_energy_wh * 200.0)
                    reasons.append(f"energy={stats.avg_energy_wh:.3f}Wh")
                if snapshot and snapshot.gpu_memory_total_mb and stats.avg_gpu_memory_mb is not None:
                    pressure = stats.avg_gpu_memory_mb / max(1.0, float(snapshot.gpu_memory_total_mb))
                    if pressure > 0.85:
                        score -= 80.0
                    elif pressure > 0.70:
                        score -= 35.0
                    reasons.append(f"vram={pressure:.0%}")
                if snapshot and snapshot.ram_available_mb and stats.avg_ram_delta_mb is not None:
                    pressure = stats.avg_ram_delta_mb / max(1.0, float(snapshot.ram_available_mb))
                    if pressure > 1.0:
                        score -= 120.0
                    elif pressure > 0.70:
                        score -= 50.0
                    reasons.append(f"ram-pressure={pressure:.0%}")

            if model == self.default_model:
                reasons.append("default")
            scored.append((score, model, ", ".join(reasons) or "candidate"))

        scored.sort(key=lambda item: (-item[0], self.candidates.index(item[1])))
        best = scored[0]
        return RouteDecision(best[1], best[2])

    def _record_run(self, model: str, text: str, started: float, before: ResourceSnapshot | None, success: bool) -> None:
        if self.telemetry is None:
            return
        elapsed = max(0.0, time.perf_counter() - started)
        after = self._resource_snapshot()
        energy = None
        gpu_memory = None
        ram_delta = None
        if before is not None and after is not None:
            energy = ResourceProfiler.estimate_energy_wh(before, after, elapsed)
            values = [x for x in (before.gpu_memory_used_mb, after.gpu_memory_used_mb) if x is not None]
            gpu_memory = max(values) if values else None
            if before.ram_available_mb is not None and after.ram_available_mb is not None:
                ram_delta = max(0.0, float(before.ram_available_mb - after.ram_available_mb))
        try:
            self.telemetry.record(
                model=model,
                task_class=self.task_class(text),
                latency_s=elapsed,
                energy_wh=energy,
                gpu_memory_mb=gpu_memory,
                ram_delta_mb=ram_delta,
                success=success,
            )
        except Exception:
            pass

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        text = self._last_user_text(messages)
        try:
            installed = self.list_models()
        except OllamaError:
            installed = self.candidates
        decision = self.decide(text, installed)
        self.last_route = decision
        before = self._resource_snapshot()
        started = time.perf_counter()
        try:
            result = self._client(decision.model).chat(messages, tools=tools)
            self._record_run(decision.model, text, started, before, True)
            return result
        except OllamaError:
            self._record_run(decision.model, text, started, before, False)
            if decision.model == self.default_model:
                raise
            self.last_route = RouteDecision(self.default_model, f"fallback after {decision.model} failure")
            before = self._resource_snapshot()
            started = time.perf_counter()
            try:
                result = self._client(self.default_model).chat(messages, tools=tools)
                self._record_run(self.default_model, text, started, before, True)
                return result
            except OllamaError:
                self._record_run(self.default_model, text, started, before, False)
                raise
