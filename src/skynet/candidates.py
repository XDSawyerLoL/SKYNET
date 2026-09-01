from __future__ import annotations

from dataclasses import asdict, dataclass
import json

from .evolution import TrajectoryMiner
from .ollama import OllamaClient
from .sandbox import CandidateArtifact, CandidateSandbox
from .trajectories import TrajectoryStore


@dataclass(frozen=True, slots=True)
class CandidateProposal:
    signature: str
    sample_count: int
    model: str
    artifact: CandidateArtifact


class CandidateGenerator:
    """Creates *proposals* from repeated successful trajectories.

    Generated candidates are staged only. They do not become active skills,
    policies or core code until independent validation/promotion occurs.
    """

    def __init__(
        self,
        base_url: str,
        model: str,
        trajectories: TrajectoryStore,
        miner: TrajectoryMiner,
        sandbox: CandidateSandbox,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.trajectories = trajectories
        self.miner = miner
        self.sandbox = sandbox

    def generate(self, signature: str | None = None) -> CandidateProposal:
        proposals = self.miner.proposals(min_samples=2, min_reward=0.75, limit=200)
        if signature:
            proposals = [item for item in proposals if item.signature == signature]
        if not proposals:
            raise RuntimeError("no repeated successful trajectory pattern is ready for candidate generation")
        proposal = proposals[0]
        evidence = []
        wanted = set(proposal.trajectory_ids)
        for item in self.trajectories.recent(200):
            if int(item["id"]) in wanted:
                evidence.append({
                    "trajectory_id": item["id"],
                    "goal": item["goal"],
                    "reward": item["reward"],
                    "evidence": str(item["evidence"])[:6000],
                })
        client = OllamaClient(self.base_url, self.model)
        response = client.chat([
            {
                "role": "system",
                "content": (
                    "You generate a candidate reusable SKYNET skill from successful trajectory evidence. "
                    "Output Markdown only. Include Purpose, Preconditions, Procedure, Verification, Failure recovery, "
                    "and Safety boundaries. Never add permissions that were not present in the evidence. "
                    "Never include secrets. This is a proposal only, not trusted executable core code."
                ),
            },
            {
                "role": "user",
                "content": "PATTERN: " + proposal.signature + "\nEVIDENCE:\n" + json.dumps(evidence, ensure_ascii=False, indent=2),
            },
        ])
        content = str(response.get("content", "")).strip()
        if len(content) < 80:
            raise RuntimeError("generated candidate was too small to evaluate")
        safe_name = "auto-" + "-".join(x for x in proposal.signature.replace("+", "-").split("-") if x)[:60]
        artifact = self.sandbox.stage(safe_name, "skill", content)
        return CandidateProposal(proposal.signature, proposal.sample_count, self.model, artifact)
