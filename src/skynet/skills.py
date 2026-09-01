from __future__ import annotations

from pathlib import Path
import re

from .skill_validation import SkillValidation, SkillValidator


_SAFE_NAME = re.compile(r"^[a-zA-Z0-9_.-]+$")


class SkillStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.candidates_path = path.parent / "skill_candidates"
        self.path.mkdir(parents=True, exist_ok=True)
        self.candidates_path.mkdir(parents=True, exist_ok=True)
        self.validator = SkillValidator()

    @staticmethod
    def _normalize(name: str) -> str:
        clean = name[:-3] if name.endswith(".md") else name
        if not _SAFE_NAME.fullmatch(clean):
            raise ValueError("Invalid skill name")
        return clean

    def list_skills(self) -> list[str]:
        return sorted(p.stem for p in self.path.glob("*.md") if p.is_file())

    def list_candidates(self) -> list[str]:
        return sorted(p.stem for p in self.candidates_path.glob("*.md") if p.is_file())

    def read_skill(self, name: str) -> str:
        clean = self._normalize(name)
        path = self.path / f"{clean}.md"
        if not path.exists():
            raise FileNotFoundError(f"Unknown skill: {name}")
        return path.read_text(encoding="utf-8")

    def read_candidate(self, name: str) -> str:
        clean = self._normalize(name)
        path = self.candidates_path / f"{clean}.md"
        if not path.exists():
            raise FileNotFoundError(f"Unknown skill candidate: {name}")
        return path.read_text(encoding="utf-8")

    def propose_skill(self, name: str, content: str) -> str:
        clean = self._normalize(name)
        body = content.strip()
        if not body:
            raise ValueError("Skill content cannot be empty")
        if len(body) > 50_000:
            raise ValueError("Skill exceeds 50 KB")
        path = self.candidates_path / f"{clean}.md"
        temp = path.with_suffix(".tmp")
        temp.write_text(body + "\n", encoding="utf-8")
        temp.replace(path)
        return f"Saved skill candidate: {clean}. Validate and promote it before use."

    def validate_candidate(self, name: str) -> SkillValidation:
        return self.validator.validate(self.read_candidate(name))

    def promote(self, name: str) -> str:
        clean = self._normalize(name)
        body = self.read_candidate(clean)
        result = self.validator.validate(body)
        if not result.valid:
            raise ValueError("Skill validation failed: " + "; ".join(result.errors))
        target = self.path / f"{clean}.md"
        temp = target.with_suffix(".tmp")
        temp.write_text(body.rstrip() + "\n", encoding="utf-8")
        temp.replace(target)
        (self.candidates_path / f"{clean}.md").unlink(missing_ok=True)
        return f"Promoted validated skill: {clean}"

    def save_skill(self, name: str, content: str) -> str:
        """Compatibility alias: V0.3 stores learned skills as candidates first."""
        return self.propose_skill(name, content)
