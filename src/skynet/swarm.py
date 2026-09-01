from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import json

from .ollama import OllamaClient
from .routing import ModelRouter


@dataclass(frozen=True, slots=True)
class SpecialistResult:
    role: str
    model: str
    output: str


DEFAULT_ROLES = {
    "planner": "Decompose the problem, identify dependencies and propose the shortest robust plan.",
    "analyst": "Analyze facts, constraints, failure modes and trade-offs. Avoid unsupported claims.",
    "critic": "Attack the proposed approach, find hidden assumptions, contradictions and likely failures.",
    "security": "Review permissions, data exposure, prompt injection, supply-chain and execution risks.",
    "verifier": "Define objective checks and evidence needed before declaring success.",
    "innovator": "Look for non-obvious approaches that improve capability without adding fragile dependencies.",
}


class SwarmEngine:
    """Small, parallel, local-first specialist swarm.

    SKYNET intentionally starts with a bounded swarm instead of spawning dozens
    of agents. Quality, diversity and verification are measured before scale.
    """

    def __init__(self, router: ModelRouter, max_workers: int = 4) -> None:
        self.router = router
        self.max_workers = max(1, min(max_workers, 8))

    def _model_for(self, role: str) -> str:
        hint = "code architecture analysis" if role in {"planner", "analyst", "security", "verifier"} else "creative analysis"
        return self.router.decide(hint, self.router.candidates).model

    def _run_role(self, role: str, goal: str) -> SpecialistResult:
        instruction = DEFAULT_ROLES.get(role, f"Act as an independent specialist for role: {role}.")
        model = self._model_for(role)
        client = OllamaClient(self.router.base_url, model)
        message = client.chat([
            {"role": "system", "content": "You are one bounded SKYNET specialist. Do not use tools. Return concise evidence-oriented analysis."},
            {"role": "user", "content": f"ROLE: {role}\nMISSION: {instruction}\nGOAL: {goal}"},
        ])
        return SpecialistResult(role, model, str(message.get("content", "")).strip())

    def run(self, goal: str, roles: list[str] | None = None) -> str:
        selected = [r.strip().lower() for r in (roles or ["planner", "analyst", "critic", "security", "verifier"]) if r.strip()]
        selected = list(dict.fromkeys(selected))[:8]
        if not selected:
            raise ValueError("at least one swarm role is required")

        results: list[SpecialistResult] = []
        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(selected))) as pool:
            futures = {pool.submit(self._run_role, role, goal): role for role in selected}
            for future in as_completed(futures):
                role = futures[future]
                try:
                    results.append(future.result())
                except Exception as exc:
                    results.append(SpecialistResult(role, "error", f"{type(exc).__name__}: {exc}"))

        evidence = "\n\n".join(f"[{r.role} via {r.model}]\n{r.output}" for r in results)
        synthesis = self.router.chat([
            {"role": "system", "content": "Synthesize independent specialist reports. Resolve disagreements, preserve uncertainty, and give a concrete recommendation. Do not invent evidence."},
            {"role": "user", "content": f"GOAL:\n{goal}\n\nSPECIALIST REPORTS:\n{evidence}"},
        ])
        payload = {
            "goal": goal,
            "specialists": [{"role": r.role, "model": r.model, "output": r.output} for r in results],
            "synthesis": str(synthesis.get("content", "")).strip(),
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)
