from __future__ import annotations

from pathlib import Path
import re


_SAFE_NAME = re.compile(r"^[a-zA-Z0-9_.-]+$")


class SkillStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _normalize(name: str) -> str:
        clean = name[:-3] if name.endswith(".md") else name
        if not _SAFE_NAME.fullmatch(clean):
            raise ValueError("Invalid skill name")
        return clean

    def list_skills(self) -> list[str]:
        return sorted(p.stem for p in self.path.glob("*.md") if p.is_file())

    def read_skill(self, name: str) -> str:
        clean = self._normalize(name)
        path = self.path / f"{clean}.md"
        if not path.exists():
            raise FileNotFoundError(f"Unknown skill: {name}")
        return path.read_text(encoding="utf-8")

    def save_skill(self, name: str, content: str) -> str:
        clean = self._normalize(name)
        body = content.strip()
        if not body:
            raise ValueError("Skill content cannot be empty")
        if len(body) > 50_000:
            raise ValueError("Skill exceeds 50 KB")
        path = self.path / f"{clean}.md"
        temp = path.with_suffix(".tmp")
        temp.write_text(body + "\n", encoding="utf-8")
        temp.replace(path)
        return f"Saved skill: {clean}"
