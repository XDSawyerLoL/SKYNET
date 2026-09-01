from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .agent import Agent
from .audit import AuditLog
from .autonomy import AutonomyRunner
from .checkpoints import CheckpointStore
from .config import Config
from .mcp import MCPHub
from .memory import MemoryStore
from .permissions import PermissionGate
from .planning import PlanStore
from .routing import ModelRouter
from .scheduler import RoutineStore
from .skills import SkillStore
from .tools import ToolBus
from .vision import OllamaVisionClient
from .windows import WindowsController


@dataclass(slots=True)
class Runtime:
    config: Config
    memory: MemoryStore
    audit: AuditLog
    skills: SkillStore
    plans: PlanStore
    permissions: PermissionGate
    router: ModelRouter
    vision: OllamaVisionClient
    windows: WindowsController
    mcp: MCPHub
    checkpoints: CheckpointStore
    routines: RoutineStore
    tools: ToolBus
    agent: Agent
    autonomy: AutonomyRunner

    @classmethod
    def create(cls, root: Path | None = None, session_id: str = "default") -> "Runtime":
        config = Config.load(root or Path.cwd())
        memory = MemoryStore(config.data_dir / "memory.db")
        audit = AuditLog(config.data_dir / "audit.jsonl")
        skills = SkillStore(config.data_dir / "skills")
        plans = PlanStore(config.data_dir / "plans")
        permissions = PermissionGate()
        router = ModelRouter(config.ollama_url, config.model, config.models)
        vision = OllamaVisionClient(config.ollama_url, config.vision_model)
        windows = WindowsController(config.workspace)
        mcp = MCPHub(config.mcp_config)
        checkpoints = CheckpointStore(config.data_dir / "checkpoints.db")
        routines = RoutineStore(config.data_dir / "routines.db")
        tools = ToolBus(
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
        agent = Agent(router, memory, skills, tools, config.max_tool_rounds, session_id=session_id)
        autonomy = AutonomyRunner(routines, checkpoints, agent)
        return cls(
            config, memory, audit, skills, plans, permissions, router, vision, windows, mcp,
            checkpoints, routines, tools, agent, autonomy,
        )

    def close(self) -> None:
        self.mcp.close()
        self.routines.close()
        self.checkpoints.close()
        self.memory.close()
