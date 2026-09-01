from __future__ import annotations

from pathlib import Path

from .config import Config
from .health import WorkerSupervisor


def main() -> None:
    root = Path.cwd().resolve()
    config = Config.load(root)
    code = WorkerSupervisor(root, config.data_dir).run()
    raise SystemExit(code)


if __name__ == "__main__":
    main()
