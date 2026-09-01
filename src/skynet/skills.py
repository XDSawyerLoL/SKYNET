from __future__ import annotations

from pathlib import Path
import re


_SAFE_NAME = re.compile(r"^[a-zA-Z0-9_.-]+$")


class SkillStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.mkdir(parents=True, exist_ok=True)

    def list_skills(self) -> list[str]:
        return sorted(p.stem for p in self.path.glob("*.md") if p.is_file())

    def read_skill(self, name: str) -> str:
        if not _SAFE_NAME.fullmatch(name):
            raise ValueError("Invalid skill name")
        path = self.path / (name if name.endswith(".md") else f"{name}.md")
        if not path.exists():
            raise FileNotFoundError(f"Unknown skill: {name}")
        return path.read_text(encoding="utf-8")
