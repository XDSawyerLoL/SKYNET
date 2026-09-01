from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import Config
from .voice import VoiceEngine


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="skynet-voice", description="Diagnostic de la voix locale SKYNET")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="Afficher le moteur vocal et les périphériques audio détectés")
    test = sub.add_parser("test", help="Prononcer une phrase de test en français")
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
        print(f"Moteur : {status.provider}")
        print(f"Voix : {status.voice}")
        print("Lecture de la phrase de test...")
        engine.speak_blocking(args.text)
        if engine.last_error:
            raise SystemExit(f"ERREUR VOCALE : {engine.last_error}")
        print("Test vocal terminé.")
        if states:
            print("États : " + " -> ".join(states))


if __name__ == "__main__":
    main()
