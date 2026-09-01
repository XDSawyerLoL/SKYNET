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


@dataclass(slots=True)
class Config:
    ollama_url: str
    model: str
    data_dir: Path
    workspace: Path
    max_tool_rounds: int = 8

    @classmethod
    def load(cls, root: Path | None = None) -> "Config":
        root = (root or Path.cwd()).resolve()
        _load_dotenv(root / ".env")
        data_dir = (root / os.getenv("SKYNET_DATA_DIR", ".skynet")).resolve()
        workspace = (root / os.getenv("SKYNET_WORKSPACE", "workspace")).resolve()
        data_dir.mkdir(parents=True, exist_ok=True)
        workspace.mkdir(parents=True, exist_ok=True)
        return cls(
            ollama_url=os.getenv("SKYNET_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/"),
            model=os.getenv("SKYNET_MODEL", "qwen3:8b"),
            data_dir=data_dir,
            workspace=workspace,
            max_tool_rounds=int(os.getenv("SKYNET_MAX_TOOL_ROUNDS", "8")),
        )
