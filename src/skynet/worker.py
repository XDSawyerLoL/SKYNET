from __future__ import annotations

import threading
import time
from pathlib import Path

from .runtime import Runtime


def main() -> None:
    runtime = Runtime.create(Path.cwd(), session_id="autonomy-worker")
    poll = max(10, runtime.config.autonomy_poll_seconds)
    print(f"SKYNET autonomy worker started. Poll={poll}s. Ctrl+C to stop.")
    stop_heartbeat = threading.Event()

    def heartbeat_loop() -> None:
        while not stop_heartbeat.is_set():
            try:
                runtime.heartbeats.beat("worker", "alive")
            except Exception:
                pass
            stop_heartbeat.wait(5)

    heartbeat_thread = threading.Thread(target=heartbeat_loop, daemon=True, name="skynet-heartbeat")
    heartbeat_thread.start()

    try:
        while True:
            if runtime.control.engaged():
                runtime.heartbeats.beat("worker", "stopped-by-kill-switch")
                print("SKYNET worker stopped: global kill-switch engaged.")
                return
            results = runtime.autonomy.run_due()
            for routine, status, reply in results:
                one_line = " ".join(reply.splitlines())[:240]
                print(f"[{status}] {routine.name}: {one_line}")
            time.sleep(poll)
    except KeyboardInterrupt:
        runtime.heartbeats.beat("worker", "stopped")
        print("\nSKYNET autonomy worker stopped.")
    except Exception:
        runtime.heartbeats.beat("worker", "crashed")
        raise
    finally:
        stop_heartbeat.set()
        heartbeat_thread.join(timeout=2)
        runtime.close()


if __name__ == "__main__":
    main()
