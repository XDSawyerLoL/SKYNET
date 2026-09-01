from __future__ import annotations

import time
from pathlib import Path

from .runtime import Runtime


def main() -> None:
    runtime = Runtime.create(Path.cwd(), session_id="autonomy-worker")
    poll = max(10, runtime.config.autonomy_poll_seconds)
    print(f"SKYNET autonomy worker started. Poll={poll}s. Ctrl+C to stop.")
    runtime.heartbeats.beat("worker", "started")
    try:
        while True:
            if runtime.control.engaged():
                runtime.heartbeats.beat("worker", "stopped-by-kill-switch")
                print("SKYNET worker stopped: global kill-switch engaged.")
                return
            runtime.heartbeats.beat("worker", "running")
            results = runtime.autonomy.run_due()
            for routine, status, reply in results:
                one_line = " ".join(reply.splitlines())[:240]
                print(f"[{status}] {routine.name}: {one_line}")
            runtime.heartbeats.beat("worker", "idle")
            time.sleep(poll)
    except KeyboardInterrupt:
        runtime.heartbeats.beat("worker", "stopped")
        print("\nSKYNET autonomy worker stopped.")
    except Exception:
        runtime.heartbeats.beat("worker", "crashed")
        raise
    finally:
        runtime.close()


if __name__ == "__main__":
    main()
