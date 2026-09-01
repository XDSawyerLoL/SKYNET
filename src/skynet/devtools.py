from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
import json
import os
import shutil
import subprocess
import sys


class DeveloperToolError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class DoctorReport:
    python: str
    git: bool
    ollama: bool
    playwright: bool
    tests_dir: bool
    git_repo: bool


class DeveloperTools:
    """Local developer operations with explicit bounded commands.

    Read-only inspection is separated from code execution. The ToolBus keeps
    test execution permission-gated because project tests execute local code.
    """

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def doctor(self) -> str:
        try:
            import playwright  # type: ignore  # noqa: F401
            has_playwright = True
        except Exception:
            has_playwright = False
        report = DoctorReport(
            python=sys.version.split()[0],
            git=shutil.which("git") is not None,
            ollama=shutil.which("ollama") is not None,
            playwright=has_playwright,
            tests_dir=(self.root / "tests").is_dir(),
            git_repo=(self.root / ".git").exists(),
        )
        return json.dumps(asdict(report), ensure_ascii=False)

    def _git(self, *args: str, timeout: int = 30) -> str:
        if shutil.which("git") is None:
            raise DeveloperToolError("git is not installed")
        completed = subprocess.run(
            ["git", *args], cwd=self.root, capture_output=True, text=True,
            timeout=max(1, min(timeout, 120)), shell=False,
        )
        output = ((completed.stdout or "") + (completed.stderr or "")).strip()
        if completed.returncode != 0:
            raise DeveloperToolError(f"git {' '.join(args)} failed: {output[:4000]}")
        return output[:50_000]

    def git_status(self) -> str:
        return self._git("status", "--short", "--branch")

    def git_diff(self, staged: bool = False) -> str:
        args = ["diff", "--stat", "--patch", "--minimal"]
        if staged:
            args.insert(1, "--cached")
        return self._git(*args, timeout=60)

    def recent_commits(self, limit: int = 20) -> str:
        safe_limit = max(1, min(int(limit), 100))
        return self._git("log", f"-{safe_limit}", "--oneline", "--decorate")

    def project_tree(self, max_files: int = 500) -> str:
        ignored = {".git", ".venv", "__pycache__", ".skynet", "node_modules", "dist", "build"}
        items: list[str] = []
        for path in sorted(self.root.rglob("*"), key=lambda p: p.as_posix().casefold()):
            try:
                rel = path.relative_to(self.root)
            except ValueError:
                continue
            if any(part in ignored for part in rel.parts):
                continue
            if path.is_file():
                items.append(rel.as_posix())
                if len(items) >= max(1, min(max_files, 3000)):
                    break
        return "\n".join(items)

    def search_code(self, query: str, max_results: int = 100) -> str:
        needle = query.strip().casefold()
        if not needle:
            return ""
        binary_suffixes = {".png", ".jpg", ".jpeg", ".gif", ".zip", ".exe", ".dll", ".db", ".sqlite", ".pyc"}
        ignored = {".git", ".venv", "__pycache__", ".skynet", "node_modules"}
        results: list[str] = []
        for path in self.root.rglob("*"):
            if not path.is_file() or path.suffix.lower() in binary_suffixes:
                continue
            rel = path.relative_to(self.root)
            if any(part in ignored for part in rel.parts):
                continue
            try:
                if path.stat().st_size > 1_000_000:
                    continue
                for number, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                    if needle in line.casefold():
                        results.append(f"{rel.as_posix()}:{number}: {line[:500]}")
                        if len(results) >= max(1, min(max_results, 500)):
                            return "\n".join(results)
            except OSError:
                continue
        return "\n".join(results)

    def run_tests(self, timeout: int = 180) -> str:
        tests = self.root / "tests"
        if not tests.is_dir():
            raise DeveloperToolError("No tests directory found")
        completed = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
            cwd=self.root, capture_output=True, text=True,
            timeout=max(10, min(int(timeout), 900)), shell=False,
            env=dict(os.environ),
        )
        output = ((completed.stdout or "") + (completed.stderr or "")).strip()
        return f"exit_code={completed.returncode}\n{output[-100_000:]}"
