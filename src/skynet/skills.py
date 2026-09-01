from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import re
import sqlite3
import threading
import time

from .skill_validation import SkillValidation, SkillValidator

_SAFE_NAME = re.compile(r"^[a-zA-Z0-9_.-]+$")
_WORD = re.compile(r"[a-zA-ZÀ-ÿ0-9_-]{3,}")


@dataclass(frozen=True, slots=True)
class SkillMatch:
    name: str
    score: float
    source: str
    preview: str
    uses: int


class SkillStore:
    """Progressive-disclosure local skill library with thread-safe usage evidence."""

    def __init__(self, path: Path, external_paths: list[Path] | None = None) -> None:
        self.path = path
        self.candidates_path = path.parent / "skill_candidates"
        self.path.mkdir(parents=True, exist_ok=True)
        self.candidates_path.mkdir(parents=True, exist_ok=True)
        self.validator = SkillValidator()
        env_paths = [Path(x) for x in os.getenv("SKYNET_SKILL_DIRS", "").split(os.pathsep) if x.strip()]
        self.external_paths = [p.expanduser().resolve() for p in (external_paths or env_paths) if p.expanduser().exists()]
        self.lock = threading.RLock()
        self.stats = sqlite3.connect(path.parent / "skill-usage.db", timeout=10, check_same_thread=False)
        with self.lock:
            self.stats.execute(
                """
                CREATE TABLE IF NOT EXISTS skill_usage (
                    name TEXT PRIMARY KEY,
                    uses INTEGER NOT NULL DEFAULT 0,
                    successes INTEGER NOT NULL DEFAULT 0,
                    last_used REAL
                )
                """
            )
            self.stats.commit()

    @staticmethod
    def _normalize(name: str) -> str:
        clean = name[:-3] if name.endswith(".md") else name
        if not _SAFE_NAME.fullmatch(clean):
            raise ValueError("Invalid skill name")
        return clean

    def _internal_files(self) -> dict[str, Path]:
        return {p.stem: p for p in self.path.glob("*.md") if p.is_file()}

    def _external_files(self) -> dict[str, Path]:
        output: dict[str, Path] = {}
        for root in self.external_paths:
            try:
                direct = root / "SKILL.md"
                if direct.is_file(): output.setdefault(root.name, direct)
                for file in root.glob("*/SKILL.md"): output.setdefault(file.parent.name, file)
                for file in root.glob("*.md"): output.setdefault(file.stem, file)
            except OSError:
                continue
        return output

    def _all_files(self) -> dict[str, tuple[Path, str]]:
        output = {name: (path, "internal") for name, path in self._internal_files().items()}
        for name, path in self._external_files().items():
            output.setdefault(name, (path, f"external:{path.parent}"))
        return output

    def list_skills(self) -> list[str]: return sorted(self._all_files())
    def list_candidates(self) -> list[str]: return sorted(p.stem for p in self.candidates_path.glob("*.md") if p.is_file())

    def read_skill(self, name: str) -> str:
        clean = self._normalize(name); found = self._all_files().get(clean)
        if found is None: raise FileNotFoundError(f"Unknown skill: {name}")
        path, _source = found
        if path.stat().st_size > 200_000: raise ValueError("Skill exceeds 200 KB read limit")
        return path.read_text(encoding="utf-8", errors="replace")

    def read_candidate(self, name: str) -> str:
        clean = self._normalize(name); path = self.candidates_path / f"{clean}.md"
        if not path.exists(): raise FileNotFoundError(f"Unknown skill candidate: {name}")
        return path.read_text(encoding="utf-8")

    def propose_skill(self, name: str, content: str) -> str:
        clean = self._normalize(name); body = content.strip()
        if not body: raise ValueError("Skill content cannot be empty")
        if len(body) > 50_000: raise ValueError("Skill exceeds 50 KB")
        path = self.candidates_path / f"{clean}.md"; temp = path.with_suffix(".tmp")
        temp.write_text(body + "\n", encoding="utf-8"); temp.replace(path)
        return f"Saved skill candidate: {clean}. Validate and promote it before use."

    def validate_candidate(self, name: str) -> SkillValidation: return self.validator.validate(self.read_candidate(name))

    def promote(self, name: str) -> str:
        clean = self._normalize(name); body = self.read_candidate(clean); result = self.validator.validate(body)
        if not result.valid: raise ValueError("Skill validation failed: " + "; ".join(result.errors))
        target = self.path / f"{clean}.md"; temp = target.with_suffix(".tmp")
        temp.write_text(body.rstrip() + "\n", encoding="utf-8"); temp.replace(target)
        (self.candidates_path / f"{clean}.md").unlink(missing_ok=True)
        return f"Promoted validated skill: {clean}"

    def save_skill(self, name: str, content: str) -> str: return self.propose_skill(name, content)

    @staticmethod
    def _tokens(text: str) -> set[str]: return {word.casefold() for word in _WORD.findall(text)}

    def _usage(self, name: str) -> tuple[int, int]:
        with self.lock:
            row = self.stats.execute("SELECT uses,successes FROM skill_usage WHERE name=?", (name,)).fetchone()
        return (0, 0) if row is None else (int(row[0]), int(row[1]))

    def search(self, query: str, limit: int = 5) -> list[SkillMatch]:
        q = self._tokens(query)
        if not q: return []
        results: list[SkillMatch] = []
        for name, (path, source) in self._all_files().items():
            try: text = path.read_text(encoding="utf-8", errors="replace")[:30_000]
            except OSError: continue
            tokens = self._tokens(name + " " + text[:8000]); overlap = len(q & tokens)
            if not overlap: continue
            uses, successes = self._usage(name); reliability = (successes / uses) if uses else 0.5
            score = (overlap / max(1, len(q))) + min(0.20, uses * 0.005) + reliability * 0.10
            results.append(SkillMatch(name, score, source, " ".join(text.split())[:500], uses))
        return sorted(results, key=lambda x: (-x.score, -x.uses, x.name))[:max(1, min(limit, 10))]

    def mark_used(self, name: str, success: bool | None = None) -> None:
        clean = self._normalize(name)
        with self.lock:
            row = self.stats.execute("SELECT uses,successes FROM skill_usage WHERE name=?", (clean,)).fetchone()
            uses, successes = (0, 0) if row is None else (int(row[0]), int(row[1]))
            self.stats.execute(
                "INSERT OR REPLACE INTO skill_usage(name,uses,successes,last_used) VALUES(?,?,?,?)",
                (clean, uses + 1, successes + (1 if success is True else 0), time.time()),
            )
            self.stats.commit()

    def context_for(self, query: str, limit: int = 3, max_chars: int = 12_000) -> list[tuple[str, str]]:
        output: list[tuple[str, str]] = []; remaining = max(1000, max_chars)
        for match in self.search(query, limit=limit):
            body = self.read_skill(match.name); chunk = body[:remaining]
            if not chunk: break
            output.append((match.name, chunk)); self.mark_used(match.name); remaining -= len(chunk)
            if remaining <= 0: break
        return output

    def usage(self, limit: int = 50) -> list[dict]:
        with self.lock:
            rows = self.stats.execute(
                "SELECT name,uses,successes,last_used FROM skill_usage ORDER BY uses DESC,last_used DESC LIMIT ?",
                (max(1, min(limit, 500)),),
            ).fetchall()
        return [{"name": str(r[0]), "uses": int(r[1]), "successes": int(r[2]), "last_used": r[3]} for r in rows]

    def close(self) -> None:
        with self.lock: self.stats.close()
