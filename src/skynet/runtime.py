from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .adaptation import AdaptationPipeline
from .agent import Agent
from .audit import AuditLog
from .autonomy import AutonomyRunner
from .backup import BackupManager
from .browser import BrowserHarness
from .candidates import CandidateGenerator
from .channels import ChannelHub
from .checkpoints import CheckpointStore
from .config import Config
from .delegation import CapabilityLeaseStore
from .deployment import DeploymentRegistry
from .devtools import DeveloperTools
from .evolution import EvalSuite, ModelTournament, ScoreStore, TrajectoryMiner
from .governance import GovernedToolBus
from .health import GlobalControl, HeartbeatStore
from .identity import LocalIdentityStore
from .integrations import IntegrationRegistry
from .interop import AgentCard, AgentRegistry
from .lab import AdaptiveLab
from .mcp import MCPHub
from .memory import MemoryStore
from .permissions import PermissionGate
from .planning import PlanStore
from .policy import MandateStore, PolicyEngine, ReceiptStore
from .product_tools import ProductToolBus
from .redteam import RedTeamSuite
from .regression import FailureRegressionSuite
from .resources import ResourceProfiler
from .risk import RiskBudgetEngine
from .routing import ModelRouter
from .sandbox import CandidateSandbox
from .scheduler import RoutineStore
from .semantic import SemanticMemory
from .sessions import SessionStore
from .skills import SkillStore
from .swarm import SwarmEngine
from .telemetry import ModelTelemetryStore
from .trajectories import TrajectoryStore
from .trust import ValidationReportStore
from .vision import OllamaVisionClient
from .windows import WindowsController


@dataclass(slots=True)
class Runtime:
    config: Config
    memory: MemoryStore
    sessions: SessionStore
    semantic: SemanticMemory
    trajectories: TrajectoryStore
    trajectory_miner: TrajectoryMiner
    adaptation: AdaptationPipeline
    sandbox: CandidateSandbox
    lab: AdaptiveLab
    candidate_generator: CandidateGenerator
    redteam: RedTeamSuite
    regression: FailureRegressionSuite
    risk: RiskBudgetEngine
    profiler: ResourceProfiler
    telemetry: ModelTelemetryStore
    audit: AuditLog
    identity: LocalIdentityStore
    reports: ValidationReportStore
    backups: BackupManager
    control: GlobalControl
    heartbeats: HeartbeatStore
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
    browser: BrowserHarness
    developer: DeveloperTools
    integrations: IntegrationRegistry
    channels: ChannelHub
    vision: OllamaVisionClient
    windows: WindowsController
    mcp: MCPHub
    checkpoints: CheckpointStore
    routines: RoutineStore
    raw_tools: ProductToolBus
    tools: GovernedToolBus
    agent: Agent
    autonomy: AutonomyRunner

    @classmethod
    def create(cls, root: Path | None = None, session_id: str = "default") -> "Runtime":
        config = Config.load(root or Path.cwd())
        memory_path = config.data_dir / "memory.db"
        memory = MemoryStore(memory_path)
        sessions = SessionStore(memory_path)
        sessions.ensure(session_id, title=session_id, channel="local")
        semantic = SemanticMemory(config.data_dir / "semantic.db", config.ollama_url, config.embed_model)
        trajectories = TrajectoryStore(config.data_dir / "trajectories.db")
        trajectory_miner = TrajectoryMiner(trajectories)
        adaptation = AdaptationPipeline(config.data_dir / "adaptation", trajectories)
        sandbox = CandidateSandbox(config.data_dir / "candidate-sandbox")
        lab = AdaptiveLab(config.data_dir / "adaptive-lab", config.data_dir / "candidate-sandbox")
        redteam = RedTeamSuite(config.ollama_url)
        regression = FailureRegressionSuite(config.data_dir / "regression", trajectories, config.ollama_url)
        risk = RiskBudgetEngine(50)
        profiler = ResourceProfiler()
        telemetry = ModelTelemetryStore(config.data_dir / "model-telemetry.db")
        audit = AuditLog(config.data_dir / "audit.jsonl")
        identity = LocalIdentityStore(config.data_dir / "identity.key")
        reports = ValidationReportStore(config.data_dir / "validation-reports", identity)
        backups = BackupManager(config.data_dir, config.data_dir / "backups")
        control = GlobalControl(config.data_dir / "kill-switch.json")
        heartbeats = HeartbeatStore(config.data_dir / "heartbeats")
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
        router = ModelRouter(
            config.ollama_url,
            config.model,
            config.models,
            telemetry=telemetry,
            profiler=profiler,
            quality_lookup=scores.latest_for,
        )
        deployed_model = deployments.get("reasoning-model")
        if deployed_model is not None:
            router.configure_deployment(deployed_model.active, deployed_model.status)
        candidate_generator = CandidateGenerator(
            config.ollama_url,
            router.preferred_model or config.model,
            trajectories,
            trajectory_miner,
            sandbox,
        )
        tournament = ModelTournament(router, eval_suite, scores, max_workers=min(config.swarm_workers, 3))
        swarm = SwarmEngine(router, config.swarm_workers, store_path=config.data_dir / "swarm-runs.db")
        agents = AgentRegistry(config.data_dir / "agents.json")
        agents.register(AgentCard(
            name="SKYNET local core",
            agent_id=identity.identity.agent_id,
            capabilities=[
                "planning", "memory", "session-search", "windows", "mcp", "browser", "swarm-graph",
                "channels", "integration-registry", "developer-tooling", "policy-enforcement",
                "trajectory-learning", "objective-evaluation", "capability-delegation",
                "canary-promotion", "rollback", "red-team-evaluation", "risk-budgeting",
                "candidate-sandbox", "local-adaptation-prep", "adaptive-lab",
                "resource-aware-routing", "trajectory-candidate-generation",
                "signed-validation", "failure-regression", "global-kill-switch", "resilience-backup",
            ],
            protocols=["skynet-local", "mcp-client", "a2a-ready", "channel-bus-v1"],
            trust="owner-local",
        ))
        browser = BrowserHarness(config.workspace)
        developer = DeveloperTools(config.workspace if (config.workspace / ".git").exists() else config.data_dir.parent)
        integrations = IntegrationRegistry(config.data_dir / "integrations.json")
        channels = ChannelHub(config.data_dir / "channels.db")
        vision = OllamaVisionClient(config.ollama_url, config.vision_model)
        windows = WindowsController(config.workspace)
        mcp = MCPHub(config.mcp_config)
        integrations.seed_builtin("core:ollama", ["local-inference", "model-routing"])
        integrations.seed_builtin("core:windows", ["desktop-control", "accessibility", "screenshots"])
        integrations.seed_builtin("core:filesystem", ["files-read", "files-write"])
        integrations.seed_builtin("core:powershell", ["shell"])
        integrations.seed_builtin("core:browser", ["web-read", "browser-automation", browser.state().mode])
        integrations.seed_builtin("core:git", ["git-status", "git-diff", "code-search", "tests"])
        integrations.seed_builtin("core:channels", ["inbox", "outbox", "session-binding"])
        integrations.discover_mcp(mcp.list_servers())
        checkpoints = CheckpointStore(config.data_dir / "checkpoints.db")
        routines = RoutineStore(config.data_dir / "routines.db")
        raw_tools = ProductToolBus(
            config.workspace, memory, skills, audit, permissions,
            plans=plans, windows=windows, mcp=mcp, vision=vision,
            browser=browser, developer=developer, sessions=sessions, integrations=integrations,
        )
        tools = GovernedToolBus(
            raw_tools, mandates, policy, receipts, identity.identity.agent_id,
            semantic=semantic, swarm=swarm, control=control,
        )
        agent = Agent(
            router, memory, skills, tools, config.max_tool_rounds,
            session_id=session_id, semantic=semantic, trajectories=trajectories, sessions=sessions,
        )
        autonomy = AutonomyRunner(routines, checkpoints, agent)
        return cls(
            config=config, memory=memory, sessions=sessions, semantic=semantic, trajectories=trajectories,
            trajectory_miner=trajectory_miner, adaptation=adaptation, sandbox=sandbox,
            lab=lab, candidate_generator=candidate_generator, redteam=redteam, regression=regression,
            risk=risk, profiler=profiler, telemetry=telemetry, audit=audit, identity=identity,
            reports=reports, backups=backups, control=control, heartbeats=heartbeats,
            mandates=mandates, receipts=receipts, policy=policy, leases=leases,
            deployments=deployments, eval_suite=eval_suite, scores=scores,
            tournament=tournament, skills=skills, plans=plans, permissions=permissions,
            router=router, swarm=swarm, agents=agents, browser=browser, developer=developer,
            integrations=integrations, channels=channels, vision=vision, windows=windows,
            mcp=mcp, checkpoints=checkpoints, routines=routines, raw_tools=raw_tools,
            tools=tools, agent=agent, autonomy=autonomy,
        )

    def close(self) -> None:
        self.browser.close()
        self.mcp.close()
        self.routines.close()
        self.checkpoints.close()
        self.channels.close()
        self.swarm.close()
        self.skills.close()
        self.sessions.close()
        self.telemetry.close()
        self.scores.close()
        self.receipts.close()
        self.trajectories.close()
        self.semantic.close()
        self.memory.close()
