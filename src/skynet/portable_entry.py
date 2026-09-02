from __future__ import annotations

import os
from pathlib import Path
import sys


def portable_root() -> Path:
    """Return the persistent root used by the portable build.

    In a PyInstaller one-file executable, sys.executable points to the actual
    EXE on the USB drive while __file__ points inside PyInstaller's temporary
    extraction directory. Persistent state must therefore follow the EXE.
    """

    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path.cwd().resolve()


def prepare_portable_environment() -> Path:
    root = portable_root()
    root.mkdir(parents=True, exist_ok=True)
    os.chdir(root)
    os.environ.setdefault("SKYNET_PORTABLE", "1")
    os.environ.setdefault("SKYNET_DATA_DIR", ".skynet")
    os.environ.setdefault("SKYNET_WORKSPACE", "workspace")
    os.environ.setdefault("SKYNET_MCP_CONFIG", ".skynet/mcp.json")
    return root


def main() -> None:
    prepare_portable_environment()
    from .desktop_chat_launch import main as desktop_main

    desktop_main()


if __name__ == "__main__":
    main()
