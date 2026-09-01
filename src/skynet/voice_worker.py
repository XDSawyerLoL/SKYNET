from __future__ import annotations

import argparse
import contextlib
import inspect
import json
import os
from pathlib import Path
import re
import sys
import traceback
import uuid


def _choose_device() -> str:
    forced = os.getenv("SKYNET_VOICE_DEVICE", "auto").strip().lower()
    if forced in {"cpu", "cuda"}:
        return forced
    import torch
    if torch.cuda.is_available():
        try:
            free_bytes, _total = torch.cuda.mem_get_info()
            if free_bytes >= 5_000_000_000:
                return "cuda"
        except Exception:
            pass
    return "cpu"


def _load_model():
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS

    device = _choose_device()
    kwargs = {"device": device}
    signature = inspect.signature(ChatterboxMultilingualTTS.from_pretrained)
    if "t3_model" in signature.parameters:
        kwargs["t3_model"] = "v3"
    with contextlib.redirect_stdout(sys.stderr):
        model = ChatterboxMultilingualTTS.from_pretrained(**kwargs)
    variant = "v3" if "t3_model" in signature.parameters else "package-default"
    return model, device, variant


def _split_for_prosody(text: str, max_chars: int = 320) -> list[str]:
    value = " ".join(str(text).split()).strip()
    if not value:
        return []
    sentences = re.split(r"(?<=[.!?])\s+", value)
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        if len(sentence) > max_chars:
            parts = re.split(r"(?<=[,;:])\s+", sentence)
        else:
            parts = [sentence]
        for part in parts:
            part = part.strip()
            if not part:
                continue
            candidate = f"{current} {part}".strip() if current else part
            if current and len(candidate) > max_chars:
                chunks.append(current)
                current = part
            else:
                current = candidate
    if current:
        chunks.append(current)
    return chunks


def _generate_to_file(model, text: str, output_path: Path, reference: str | None) -> dict:
    import numpy as np
    import soundfile as sf

    chunks = _split_for_prosody(text)
    if not chunks:
        raise ValueError("texte vocal vide")

    generated: list[np.ndarray] = []
    sr = int(model.sr)
    silence = np.zeros(int(sr * 0.13), dtype=np.float32)
    for index, chunk in enumerate(chunks):
        kwargs = {
            "language_id": "fr",
            "exaggeration": 0.62,
            "cfg_weight": 0.30,
            "temperature": 0.78,
            "repetition_penalty": 1.2,
            "min_p": 0.05,
            "top_p": 0.95,
        }
        if reference:
            kwargs["audio_prompt_path"] = reference
        with contextlib.redirect_stdout(sys.stderr):
            wav = model.generate(chunk, **kwargs)
        samples = wav.squeeze().detach().cpu().numpy().astype(np.float32, copy=False)
        if samples.size == 0:
            raise RuntimeError("Chatterbox a renvoye un tampon audio vide")
        generated.append(samples)
        if index < len(chunks) - 1:
            generated.append(silence)

    audio = np.concatenate(generated)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(output_path, audio, sr, subtype="PCM_16")
    return {"sample_rate": sr, "chunks": len(chunks), "seconds": round(len(audio) / sr, 3)}


def _prewarm() -> int:
    try:
        model, device, variant = _load_model()
        print(json.dumps({"ok": True, "device": device, "variant": variant, "sample_rate": int(model.sr)}, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False))
        traceback.print_exc(file=sys.stderr)
        return 1


def _serve() -> int:
    try:
        model, device, variant = _load_model()
    except Exception as exc:
        print(json.dumps({"type": "ready", "ok": False, "error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False), flush=True)
        traceback.print_exc(file=sys.stderr)
        return 1

    print(json.dumps({"type": "ready", "ok": True, "device": device, "variant": variant, "sample_rate": int(model.sr)}, ensure_ascii=False), flush=True)
    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        try:
            request = json.loads(raw)
            command = str(request.get("cmd", ""))
            request_id = str(request.get("id") or uuid.uuid4().hex)
            if command == "shutdown":
                print(json.dumps({"type": "shutdown", "ok": True, "id": request_id}), flush=True)
                return 0
            if command != "synth":
                raise ValueError(f"commande inconnue: {command}")
            text = str(request.get("text", "")).strip()
            output = Path(str(request.get("output", ""))).resolve()
            reference_raw = request.get("reference")
            reference = str(Path(str(reference_raw)).resolve()) if reference_raw else None
            meta = _generate_to_file(model, text, output, reference)
            print(json.dumps({"type": "result", "ok": True, "id": request_id, "output": str(output), **meta}, ensure_ascii=False), flush=True)
        except Exception as exc:
            print(json.dumps({"type": "result", "ok": False, "id": request.get("id") if "request" in locals() else "", "error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False), flush=True)
            traceback.print_exc(file=sys.stderr)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prewarm", action="store_true")
    args = parser.parse_args()
    raise SystemExit(_prewarm() if args.prewarm else _serve())


if __name__ == "__main__":
    main()
