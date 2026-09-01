from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(slots=True)
class Config:
    ollama_url: str
    model: str
    models: list[str]
    vision_model: str | None
    data_dir: Path
    workspace: Path
    mcp_config: Path
    max_tool_rounds: int = 10
    autonomy_poll_seconds: int = 30

    @classmethod
    def load(cls, root: Path | None = None) -> "Config":
        root = (root or Path.cwd()).resolve()
        _load_dotenv(root / ".env")
        data_dir = (root / os.getenv("SKYNET_DATA_DIR", ".skynet")).resolve()
        workspace = (root / os.getenv("SKYNET_WORKSPACE", "workspace")).resolve()
        mcp_config = (root / os.getenv("SKYNET_MCP_CONFIG", ".skynet/mcp.json")).resolve()
        data_dir.mkdir(parents=True, exist_ok=True)
        workspace.mkdir(parents=True, exist_ok=True)
        vision = os.getenv("SKYNET_VISION_MODEL", "").strip() or None
        default_model = os.getenv("SKYNET_MODEL", "qwen3:8b").strip()
        models = _csv(os.getenv("SKYNET_MODELS", default_model))
        if default_model not in models:
            models.insert(0, default_model)
        return cls(
            ollama_url=os.getenv("SKYNET_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/"),
            model=default_model,
            models=models,
            vision_model=vision,
            data_dir=data_dir,
            workspace=workspace,
            mcp_config=mcp_config,
            max_tool_rounds=max(1, int(os.getenv("SKYNET_MAX_TOOL_ROUNDS", "10"))),
            autonomy_poll_seconds=max(10, int(os.getenv("SKYNET_AUTONOMY_POLL_SECONDS", "30"))),
        )
