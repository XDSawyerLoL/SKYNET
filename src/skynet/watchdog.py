from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import time

from .resilience import CrashLoopGuard, KillSwitch


def main() -> None:
    root = Path.cwd()
    data = root / ".skynet"
    kill = KillSwitch(data / "KILL_SWITCH.json")
    guard = CrashLoopGuard(data / "watchdog-restarts.json", max_restarts=4, window_seconds=300)
    heartbeat = data / "worker-heartbeat.txt"
    data.mkdir(parents=True, exist_ok=True)
    print("SKYNET watchdog started. Ctrl+C to stop.")
    try:
        while True:
            if kill.active():
                print("Kill-switch active. Worker will not be started.")
                return
            state = guard.state()
            if state.blocked:
                print(f"Crash-loop detected: {state.restart_count} restarts in {state.window_seconds}s. Supervisor halted.")
                return
            proc = subprocess.Popen([sys.executable, "-m", "skynet.worker"], cwd=root)
            started = time.time()
            while proc.poll() is None:
                if kill.active():
                    proc.terminate()
                    try:
                        proc.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                    print("Kill-switch activated. Worker terminated.")
                    return
                time.sleep(2)
            runtime = time.time() - started
            code = int(proc.returncode or 0)
            if code == 0:
                print("Worker exited cleanly. Watchdog stopping.")
                return
            state = guard.record_restart()
            print(f"Worker crashed with exit code {code} after {runtime:.1f}s. Restart {state.restart_count}/{state.max_restarts}.")
            if state.blocked:
                print("Crash-loop threshold exceeded. Watchdog halted.")
                return
            time.sleep(min(30, 2 ** max(0, state.restart_count - 1)))
    except KeyboardInterrupt:
        print("\nSKYNET watchdog stopped.")


if __name__ == "__main__":
    main()
