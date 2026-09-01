from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import Config
from .voice import VoiceEngine


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="skynet-voice", description="SKYNET local voice diagnostics")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="Show detected voice provider and audio devices")
    test = sub.add_parser("test", help="Speak a deterministic French test sentence")
    test.add_argument("--text", default="SKYNET en ligne. Tous les systèmes sont opérationnels.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config = Config.load(Path.cwd())
    states: list[str] = []
    engine = VoiceEngine(config.data_dir, on_state=states.append)
    if args.command == "status":
        print(json.dumps(engine.diagnostics(), ensure_ascii=False, indent=2))
        return
    if args.command == "test":
        status = engine.refresh()
        print(f"Provider: {status.provider}")
        print(f"Voice: {status.voice}")
        print("Speaking test sentence...")
        engine.speak_blocking(args.text)
        if engine.last_error:
            raise SystemExit(f"VOICE ERROR: {engine.last_error}")
        print("Voice test completed.")
        if states:
            print("States: " + " -> ".join(states))


if __name__ == "__main__":
    main()
