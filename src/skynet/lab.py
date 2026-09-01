from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import os
import shutil
import subprocess
import time


@dataclass(frozen=True, slots=True)
class IsolationBackend:
    name: str
    available: bool
    security_boundary: bool
    reason: str


@dataclass(frozen=True, slots=True)
class LabJob:
    job_id: str
    candidate: str
    backend: str
    created_at: float
    directory: str
    status: str


class AdaptiveLab:
    """Prepares candidate evaluation jobs for genuine isolation backends.

    Windows Sandbox is treated as a security boundary when the executable is
    available. WSL2 is useful for compatibility/testing but is explicitly not
    labelled as an equivalent Windows security boundary here.
    """

    def __init__(self, root: Path, candidate_root: Path) -> None:
        self.root = root.resolve()
        self.candidate_root = candidate_root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _command_exists(name: str) -> bool:
        return shutil.which(name) is not None

    def backends(self) -> list[IsolationBackend]:
        sandbox = self._command_exists("WindowsSandbox.exe") if os.name == "nt" else False
        wsl = self._command_exists("wsl.exe") if os.name == "nt" else self._command_exists("wsl")
        return [
            IsolationBackend(
                "windows-sandbox",
                sandbox,
                True,
                "Windows Sandbox executable detected" if sandbox else "Windows Sandbox not available/enabled",
            ),
            IsolationBackend(
                "wsl2",
                wsl,
                False,
                "WSL available for compatibility tests; not treated as the same isolation boundary" if wsl else "WSL not available",
            ),
            IsolationBackend(
                "static-only",
                True,
                False,
                "Always available; performs preparation/static validation only and never executes candidate code",
            ),
        ]

    def choose(self) -> IsolationBackend:
        for backend in self.backends():
            if backend.name == "windows-sandbox" and backend.available:
                return backend
        for backend in self.backends():
            if backend.name == "wsl2" and backend.available:
                return backend
        return self.backends()[-1]

    @staticmethod
    def _wsl_path(path: Path) -> str:
        executable = shutil.which("wsl.exe") or shutil.which("wsl")
        if not executable:
            raise RuntimeError("WSL is not available")
        completed = subprocess.run(
            [executable, "wslpath", "-a", str(path)],
            capture_output=True,
            text=True,
            timeout=5,
            shell=False,
        )
        if completed.returncode != 0 or not completed.stdout.strip():
            raise RuntimeError((completed.stderr or "wslpath failed").strip())
        return completed.stdout.strip()

    def prepare(self, candidate: str, backend: str | None = None) -> LabJob:
        candidate_dir = (self.candidate_root / candidate).resolve()
        candidate_dir.relative_to(self.candidate_root)
        if not candidate_dir.is_dir():
            raise FileNotFoundError(f"unknown candidate: {candidate}")
        choices = {item.name: item for item in self.backends()}
        selected = choices.get(backend or self.choose().name)
        if selected is None:
            raise ValueError("unknown isolation backend")
        if not selected.available:
            raise RuntimeError(selected.reason)

        job_id = f"{int(time.time())}-{candidate}"
        job_dir = (self.root / job_id).resolve()
        job_dir.relative_to(self.root)
        job_dir.mkdir(parents=True, exist_ok=False)
        manifest = {
            "job_id": job_id,
            "candidate": candidate,
            "candidate_dir": str(candidate_dir),
            "backend": selected.name,
            "security_boundary": selected.security_boundary,
            "created_at": time.time(),
            "status": "prepared",
        }
        (job_dir / "job.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        if selected.name == "windows-sandbox":
            output_dir = job_dir / "output"
            output_dir.mkdir()
            command = (
                "powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "
                "\"Get-ChildItem C:\\Candidate -Recurse | Select-Object FullName,Length | "
                "ConvertTo-Json | Set-Content C:\\Output\\inventory.json; "
                "'sandbox-complete' | Set-Content C:\\Output\\status.txt\""
            )
            config = f"""<Configuration>
  <Networking>Disable</Networking>
  <ClipboardRedirection>Disable</ClipboardRedirection>
  <PrinterRedirection>Disable</PrinterRedirection>
  <MappedFolders>
    <MappedFolder><HostFolder>{candidate_dir}</HostFolder><SandboxFolder>C:\\Candidate</SandboxFolder><ReadOnly>true</ReadOnly></MappedFolder>
    <MappedFolder><HostFolder>{output_dir}</HostFolder><SandboxFolder>C:\\Output</SandboxFolder><ReadOnly>false</ReadOnly></MappedFolder>
  </MappedFolders>
  <LogonCommand><Command>{command}</Command></LogonCommand>
</Configuration>"""
            (job_dir / "job.wsb").write_text(config, encoding="utf-8")

        return LabJob(job_id, candidate, selected.name, manifest["created_at"], str(job_dir), "prepared")

    def launch(self, job_id: str) -> str:
        job_dir = (self.root / job_id).resolve()
        job_dir.relative_to(self.root)
        data = json.loads((job_dir / "job.json").read_text(encoding="utf-8"))
        backend = data["backend"]
        candidate_dir = Path(data["candidate_dir"])

        if backend == "windows-sandbox":
            executable = shutil.which("WindowsSandbox.exe")
            if not executable:
                raise RuntimeError("Windows Sandbox is no longer available")
            subprocess.Popen([executable, str(job_dir / "job.wsb")], shell=False)
            return "Windows Sandbox launched. Candidate folder is mapped read-only and networking is disabled."

        if backend == "wsl2":
            executable = shutil.which("wsl.exe") or shutil.which("wsl")
            if not executable:
                raise RuntimeError("WSL is no longer available")
            candidate_wsl = self._wsl_path(candidate_dir)
            output_wsl = self._wsl_path(job_dir / "inventory.txt")
            command = f"find '{candidate_wsl}' -maxdepth 3 -type f -print > '{output_wsl}'"
            completed = subprocess.run(
                [executable, "sh", "-lc", command],
                capture_output=True,
                text=True,
                timeout=30,
                shell=False,
            )
            return f"wsl exit_code={completed.returncode}\n{(completed.stdout or '')}{(completed.stderr or '')}".strip()

        return "Static-only job prepared; no candidate code was executed."

    def list(self) -> list[LabJob]:
        output: list[LabJob] = []
        for path in sorted(self.root.glob("*/job.json"), reverse=True):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                output.append(LabJob(
                    data["job_id"], data["candidate"], data["backend"], data["created_at"],
                    str(path.parent), data.get("status", "prepared"),
                ))
            except Exception:
                continue
        return output
