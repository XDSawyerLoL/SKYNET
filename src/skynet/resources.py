from __future__ import annotations

from dataclasses import asdict, dataclass
import ctypes
import os
import shutil
import subprocess
import time


@dataclass(frozen=True, slots=True)
class ResourceSnapshot:
    ts: float
    cpu_count: int
    ram_total_mb: int | None
    ram_available_mb: int | None
    gpu_name: str | None
    gpu_memory_total_mb: int | None
    gpu_memory_used_mb: int | None
    gpu_power_w: float | None

    def as_dict(self) -> dict:
        return asdict(self)


class _MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


class ResourceProfiler:
    """Dependency-free local hardware sampler.

    RAM uses the Windows API when available. NVIDIA telemetry is optional and
    queried through nvidia-smi when present. Missing metrics remain None rather
    than being guessed.
    """

    def _ram(self) -> tuple[int | None, int | None]:
        if os.name == "nt":
            try:
                status = _MEMORYSTATUSEX()
                status.dwLength = ctypes.sizeof(_MEMORYSTATUSEX)
                if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                    mb = 1024 * 1024
                    return int(status.ullTotalPhys // mb), int(status.ullAvailPhys // mb)
            except Exception:
                pass
        try:
            pages = os.sysconf("SC_PHYS_PAGES")
            page_size = os.sysconf("SC_PAGE_SIZE")
            avail = os.sysconf("SC_AVPHYS_PAGES")
            mb = 1024 * 1024
            return int(pages * page_size // mb), int(avail * page_size // mb)
        except Exception:
            return None, None

    @staticmethod
    def _nvidia() -> tuple[str | None, int | None, int | None, float | None]:
        exe = shutil.which("nvidia-smi")
        if not exe:
            return None, None, None, None
        try:
            completed = subprocess.run(
                [
                    exe,
                    "--query-gpu=name,memory.total,memory.used,power.draw",
                    "--format=csv,noheader,nounits",
                    "-i", "0",
                ],
                capture_output=True,
                text=True,
                timeout=3,
                shell=False,
            )
            if completed.returncode != 0 or not completed.stdout.strip():
                return None, None, None, None
            row = [x.strip() for x in completed.stdout.splitlines()[0].split(",")]
            if len(row) < 4:
                return None, None, None, None
            name = row[0] or None
            total = int(float(row[1])) if row[1] not in {"", "N/A"} else None
            used = int(float(row[2])) if row[2] not in {"", "N/A"} else None
            power = float(row[3]) if row[3] not in {"", "N/A"} else None
            return name, total, used, power
        except Exception:
            return None, None, None, None

    def snapshot(self) -> ResourceSnapshot:
        total, available = self._ram()
        gpu_name, gpu_total, gpu_used, gpu_power = self._nvidia()
        return ResourceSnapshot(
            ts=time.time(),
            cpu_count=os.cpu_count() or 1,
            ram_total_mb=total,
            ram_available_mb=available,
            gpu_name=gpu_name,
            gpu_memory_total_mb=gpu_total,
            gpu_memory_used_mb=gpu_used,
            gpu_power_w=gpu_power,
        )

    @staticmethod
    def estimate_energy_wh(before: ResourceSnapshot, after: ResourceSnapshot, elapsed_s: float) -> float | None:
        values = [x for x in (before.gpu_power_w, after.gpu_power_w) if x is not None]
        if not values or elapsed_s <= 0:
            return None
        mean_w = sum(values) / len(values)
        return mean_w * elapsed_s / 3600.0
