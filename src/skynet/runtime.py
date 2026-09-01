from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .agent import Agent
from .audit import AuditLog
from .autonomy import AutonomyRunner
from .checkpoints import CheckpointStore
from .config import Config
from .delegation import CapabilityLeaseStore
from .deployment import DeploymentRegistry
from .evolution import EvalSuite, ModelTournament, ScoreStore, TrajectoryMiner
from .governance import GovernedToolBus
from .identity import LocalIdentityStore
from .interop import AgentCard, AgentRegistry
from .mcp import MCPHub
from .memory import MemoryStore
from .permissions import PermissionGate
from .planning import PlanStore
from .policy import MandateStore, PolicyEngine, ReceiptStore
from .routing import ModelRouter
from .scheduler import RoutineStore
from .semantic import SemanticMemory
from .skills import SkillStore
from .swarm import SwarmEngine
from .tools import ToolBus
from .trajectories import TrajectoryStore
from .vision import OllamaVisionClient
from .windows import WindowsController


@dataclass(slots=True)
class Runtime:
    config: Config
    memory: MemoryStore
    semantic: SemanticMemory
    trajectories: TrajectoryStore
    trajectory_miner: TrajectoryMiner
    audit: AuditLog
    identity: LocalIdentityStore
    mandates: MandateStore
    receipts: ReceiptStore
    policy: PolicyEngine
    leases: CapabilityLeaseStore
    deployments: DeploymentRegistry
    eval_suite: EvalSuite
    scores: ScoreStore
    tournament: ModelTournament
    skills: SkillStore
    plans: PlanStore
    permissions: PermissionGate
    router: ModelRouter
    swarm: SwarmEngine
    agents: AgentRegistry
    vision: OllamaVisionClient
    windows: WindowsController
    mcp: MCPHub
    checkpoints: CheckpointStore
    routines: RoutineStore
    raw_tools: ToolBus
    tools: GovernedToolBus
    agent: Agent
    autonomy: AutonomyRunner

    @classmethod
    def create(cls, root: Path | None = None, session_id: str = "default") -> "Runtime":
        config = Config.load(root or Path.cwd())
        memory = MemoryStore(config.data_dir / "memory.db")
        semantic = SemanticMemory(config.data_dir / "semantic.db", config.ollama_url, config.embed_model)
        trajectories = TrajectoryStore(config.data_dir / "trajectories.db")
        trajectory_miner = TrajectoryMiner(trajectories)
        audit = AuditLog(config.data_dir / "audit.jsonl")
        identity = LocalIdentityStore(config.data_dir / "identity.key")
        receipts = ReceiptStore(config.data_dir / "receipts.db", identity)
        mandates = MandateStore(config.data_dir / "mandate.json", identity.identity.agent_id)
        policy = PolicyEngine(receipts)
        leases = CapabilityLeaseStore(config.data_dir / "leases.json", identity)
        deployments = DeploymentRegistry(config.data_dir / "deployments.json")
        eval_suite = EvalSuite(config.data_dir / "eval-suite.json")
        scores = ScoreStore(config.data_dir / "scorecards.db")
        skills = SkillStore(config.data_dir / "skills")
        plans = PlanStore(config.data_dir / "plans")
        permissions = PermissionGate()
        router = ModelRouter(config.ollama_url, config.model, config.models)
        tournament = ModelTournament(router, eval_suite, scores, max_workers=min(config.swarm_workers, 3))
        swarm = SwarmEngine(router, config.swarm_workers)
        agents = AgentRegistry(config.data_dir / "agents.json")
        agents.register(AgentCard(
            name="SKYNET local core",
            agent_id=identity.identity.agent_id,
            capabilities=[
                "planning", "memory", "windows", "mcp", "swarm", "policy-enforcement",
                "trajectory-learning", "objective-evaluation", "capability-delegation",
            ],
            protocols=["skynet-local", "mcp-client", "a2a-ready"],
            trust="owner-local",
        ))
        vision = OllamaVisionClient(config.ollama_url, config.vision_model)
        windows = WindowsController(config.workspace)
        mcp = MCPHub(config.mcp_config)
        checkpoints = CheckpointStore(config.data_dir / "checkpoints.db")
        routines = RoutineStore(config.data_dir / "routines.db")
        raw_tools = ToolBus(
            config.workspace,
            memory,
            skills,
            audit,
            permissions,
            plans=plans,
            windows=windows,
            mcp=mcp,
            vision=vision,
        )
        tools = GovernedToolBus(
            raw_tools, mandates, policy, receipts, identity.identity.agent_id,
            semantic=semantic, swarm=swarm,
        )
        agent = Agent(
            router, memory, skills, tools, config.max_tool_rounds,
            session_id=session_id, semantic=semantic, trajectories=trajectories,
        )
        autonomy = AutonomyRunner(routines, checkpoints, agent)
        return cls(
            config=config,
            memory=memory,
            semantic=semantic,
            trajectories=trajectories,
            trajectory_miner=trajectory_miner,
            audit=audit,
            identity=identity,
            mandates=mandates,
            receipts=receipts,
            policy=policy,
            leases=leases,
            deployments=deployments,
            eval_suite=eval_suite,
            scores=scores,
            tournament=tournament,
            skills=skills,
            plans=plans,
            permissions=permissions,
            router=router,
            swarm=swarm,
            agents=agents,
            vision=vision,
            windows=windows,
            mcp=mcp,
            checkpoints=checkpoints,
            routines=routines,
            raw_tools=raw_tools,
            tools=tools,
            agent=agent,
            autonomy=autonomy,
        )

    def close(self) -> None:
        self.mcp.close()
        self.routines.close()
        self.checkpoints.close()
        self.scores.close()
        self.receipts.close()
        self.trajectories.close()
        self.semantic.close()
        self.memory.close()
