from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import re
import subprocess
import tempfile
import threading
import unicodedata
from typing import Callable


@dataclass(frozen=True, slots=True)
class VoiceStatus:
    provider: str
    ready: bool
    voice: str
    detail: str
    last_error: str = ""


_URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
_CODE_BLOCK_RE = re.compile(r"```.*?```", re.DOTALL)
_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\([^\)]+\)")
_HTML_RE = re.compile(r"<[^>]+>")
_MULTI_SPACE_RE = re.compile(r"\s+")


def prepare_spoken_text(text: str, max_chars: int = 1800) -> str:
    """Turn rich assistant output into natural speech.

    The UI may contain markdown, links, code, bullets and emoji. Those are useful
    visually but sound cheap when a TTS engine reads them literally. This
    function keeps the semantic prose while removing presentation noise.
    """

    value = str(text or "")
    value = _CODE_BLOCK_RE.sub(" ", value)
    value = _MD_LINK_RE.sub(r"\1", value)
    value = _URL_RE.sub(" ", value)
    value = _HTML_RE.sub(" ", value)
    value = value.replace("→", ", puis ").replace("=>", ", puis ")
    value = value.replace("&", " et ")
    value = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", value)
    value = re.sub(r"(?m)^\s*[-*•]\s+", "", value)
    value = re.sub(r"(?m)^\s*\d+[.)]\s+", "", value)
    value = value.replace("`", "").replace("*", "").replace("_", "").replace("~", "")

    cleaned: list[str] = []
    for char in value:
        category = unicodedata.category(char)
        if category in {"Cf", "Cs"}:
            continue
        if category.startswith("So") or category.startswith("Sk"):
            continue
        cleaned.append(char)
    value = "".join(cleaned)
    value = _MULTI_SPACE_RE.sub(" ", value).strip()

    if len(value) > max_chars:
        cut = value[:max_chars]
        boundary = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "), cut.rfind("; "))
        value = (cut[: boundary + 1] if boundary > int(max_chars * 0.55) else cut).strip()
    return value


class VoiceEngine:
    """Local-first French TTS with layered quality fallbacks.

    Priority when installed:
      Chatterbox Multilingual V3 -> Kokoro 82M -> Windows SAPI.

    Speech is output-only: this component never executes assistant text as code.
    Premium Chatterbox is opt-in through `.skynet/voice/chatterbox.enabled` so a
    lightweight SKYNET install never downloads multi-gigabyte models silently.
    """

    def __init__(self, data_dir: Path, on_state: Callable[[str], None] | None = None) -> None:
        self.data_dir = Path(data_dir)
        self.voice_dir = self.data_dir / "voice"
        self.voice_dir.mkdir(parents=True, exist_ok=True)
        self.model_path = self.voice_dir / "kokoro-v1.0.onnx"
        self.voices_path = self.voice_dir / "voices-v1.0.bin"
        self.chatterbox_marker = self.voice_dir / "chatterbox.enabled"
        self.reference_path = self.voice_dir / "reference.wav"
        self.on_state = on_state
        self._thread: threading.Thread | None = None
        self._process: subprocess.Popen | None = None
        self._stop_lock = threading.RLock()
        self._kokoro = None
        self._chatterbox = None
        self._chatterbox_device = ""
        self._last_error = ""
        self._provider = self._detect_provider()

    @property
    def last_error(self) -> str:
        return self._last_error

    def _kokoro_available(self) -> bool:
        if not (self.model_path.exists() and self.voices_path.exists()):
            return False
        try:
            import kokoro_onnx  # noqa: F401
            import sounddevice  # noqa: F401
            from misaki import espeak  # noqa: F401
            from misaki.espeak import EspeakG2P  # noqa: F401
            return True
        except Exception:
            return False

    def _chatterbox_available(self) -> bool:
        if not self.chatterbox_marker.exists():
            return False
        try:
            import torch  # noqa: F401
            import sounddevice  # noqa: F401
            from chatterbox.mtl_tts import ChatterboxMultilingualTTS  # noqa: F401
            return True
        except Exception as exc:
            self._last_error = f"Chatterbox indisponible: {type(exc).__name__}: {exc}"
            return False

    def _detect_provider(self) -> str:
        if self._chatterbox_available():
            return "chatterbox-local"
        if self._kokoro_available():
            return "kokoro-local"
        return "windows-sapi"

    @staticmethod
    def _powershell_ready() -> bool:
        try:
            return subprocess.run(
                ["powershell", "-NoProfile", "-Command", "$PSVersionTable.PSVersion.Major"],
                capture_output=True,
                text=True,
                timeout=3,
                shell=False,
            ).returncode == 0
        except Exception:
            return False

    def status(self) -> VoiceStatus:
        if self._provider == "chatterbox-local":
            reference = "référence personnalisée" if self.reference_path.exists() else "voix intégrée"
            return VoiceStatus(
                provider="Chatterbox Multilingual V3",
                ready=True,
                voice=reference,
                detail="Voix premium locale · français · expressivité naturelle",
                last_error=self._last_error,
            )
        if self._provider == "kokoro-local":
            return VoiceStatus(
                provider="Kokoro 82M local",
                ready=True,
                voice="ff_siwis",
                detail="Voix neuronale locale · français · mode rapide",
                last_error=self._last_error,
            )
        if self._powershell_ready():
            return VoiceStatus(
                provider="Windows SAPI",
                ready=True,
                voice="meilleure voix française disponible",
                detail="Mode de secours hors ligne",
                last_error=self._last_error,
            )
        return VoiceStatus("aucun", False, "", "Aucun moteur vocal local disponible", self._last_error)

    def refresh(self) -> VoiceStatus:
        self._last_error = ""
        self._provider = self._detect_provider()
        return self.status()

    def diagnostics(self) -> dict:
        devices: list[str] = []
        default_device = "inconnu"
        try:
            import sounddevice as sd
            raw = sd.query_devices()
            devices = [f"{i}: {item['name']} (sorties={item['max_output_channels']})" for i, item in enumerate(raw)]
            default_device = str(sd.default.device)
        except Exception as exc:
            devices = [f"sounddevice indisponible: {type(exc).__name__}: {exc}"]
        status = self.status()
        return {
            "provider": status.provider,
            "ready": status.ready,
            "voice": status.voice,
            "detail": status.detail,
            "last_error": self._last_error,
            "kokoro_model_exists": self.model_path.exists(),
            "kokoro_voices_exists": self.voices_path.exists(),
            "chatterbox_enabled": self.chatterbox_marker.exists(),
            "reference_voice_exists": self.reference_path.exists(),
            "default_audio_device": default_device,
            "audio_devices": devices,
        }

    def speak(self, text: str) -> None:
        clean = prepare_spoken_text(text)
        if not clean:
            return
        self.stop()
        self._thread = threading.Thread(target=self._speak_worker, args=(clean,), daemon=True, name="skynet-voice")
        self._thread.start()

    def speak_blocking(self, text: str) -> None:
        clean = prepare_spoken_text(text)
        if not clean:
            return
        self.stop()
        self._speak_worker(clean)

    def stop(self) -> None:
        with self._stop_lock:
            try:
                import sounddevice as sd
                sd.stop()
            except Exception:
                pass
            process = self._process
            self._process = None
            if process is not None and process.poll() is None:
                try:
                    process.terminate()
                except Exception:
                    pass

    def _emit(self, state: str) -> None:
        if self.on_state is not None:
            try:
                self.on_state(state)
            except Exception:
                pass

    def _speak_worker(self, text: str) -> None:
        self._last_error = ""
        self._emit("speaking")
        errors: list[str] = []

        candidates: list[str] = [self._provider]
        if self._provider == "chatterbox-local" and self._kokoro_available():
            candidates.append("kokoro-local")
        if "windows-sapi" not in candidates:
            candidates.append("windows-sapi")

        for provider in candidates:
            try:
                if provider == "chatterbox-local":
                    self._speak_chatterbox(text)
                elif provider == "kokoro-local":
                    self._speak_kokoro(text)
                else:
                    self._speak_windows(text)
                self._provider = provider
                self._last_error = " | ".join(errors)
                self._emit("idle")
                return
            except Exception as exc:
                detail = f"{provider}: {type(exc).__name__}: {exc}"
                errors.append(detail)
                self._emit(f"fallback:{detail}")

        self._last_error = " | ".join(errors)
        self._emit(f"error:{self._last_error}")

    @staticmethod
    def _choose_chatterbox_device() -> str:
        forced = os.getenv("SKYNET_VOICE_DEVICE", "auto").strip().lower()
        if forced in {"cpu", "cuda"}:
            return forced
        try:
            import torch
            if torch.cuda.is_available():
                free_bytes, _total_bytes = torch.cuda.mem_get_info()
                if free_bytes >= 4_500_000_000:
                    return "cuda"
        except Exception:
            pass
        return "cpu"

    def _speak_chatterbox(self, text: str) -> None:
        import sounddevice as sd
        from chatterbox.mtl_tts import ChatterboxMultilingualTTS

        device = self._choose_chatterbox_device()
        if self._chatterbox is None or self._chatterbox_device != device:
            self._emit(f"loading:Chatterbox {device}")
            self._chatterbox = ChatterboxMultilingualTTS.from_pretrained(device=device, t3_model="v3")
            self._chatterbox_device = device

        kwargs = {
            "language_id": "fr",
            "exaggeration": 0.38,
            "cfg_weight": 0.35,
            "temperature": 0.72,
        }
        if self.reference_path.exists():
            kwargs["audio_prompt_path"] = str(self.reference_path)
        wav = self._chatterbox.generate(text, **kwargs)
        samples = wav.squeeze().detach().cpu().numpy()
        if samples.size == 0:
            raise RuntimeError("Chatterbox a renvoyé un tampon audio vide")
        sd.play(samples, samplerate=self._chatterbox.sr)
        sd.wait()

    def _speak_kokoro(self, text: str) -> None:
        import sounddevice as sd
        from kokoro_onnx import Kokoro
        from misaki import espeak
        from misaki.espeak import EspeakG2P

        _fallback = espeak.EspeakFallback(british=False)
        g2p = EspeakG2P(language="fr-fr")
        phonemes, _ = g2p(text)
        if not phonemes:
            raise RuntimeError("Le phonémiseur français n'a produit aucun phonème")

        if self._kokoro is None:
            self._kokoro = Kokoro(str(self.model_path), str(self.voices_path))
        samples, sample_rate = self._kokoro.create(
            phonemes,
            voice="ff_siwis",
            speed=0.96,
            is_phonemes=True,
        )
        if samples is None or len(samples) == 0:
            raise RuntimeError("Kokoro a renvoyé un tampon audio vide")
        sd.play(samples, samplerate=sample_rate)
        sd.wait()

    def _speak_windows(self, text: str) -> None:
        tmp = tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".txt", delete=False, dir=self.voice_dir)
        try:
            tmp.write(text)
            tmp.close()
            path = str(Path(tmp.name).resolve()).replace("'", "''")
            script = (
                "Add-Type -AssemblyName System.Speech; "
                "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                "$voices = $s.GetInstalledVoices() | ForEach-Object {$_.VoiceInfo}; "
                "$v = $voices | Where-Object {$_.Culture.Name -like 'fr-*' -and $_.Gender -eq 'Female'} | Select-Object -First 1; "
                "if (-not $v) {$v = $voices | Where-Object {$_.Culture.Name -like 'fr-*'} | Select-Object -First 1}; "
                "if (-not $v) {$v = $voices | Select-Object -First 1}; "
                "if (-not $v) {throw 'Aucune voix Windows installée'}; "
                "$s.SelectVoice($v.Name); $s.Rate = -1; $s.Volume = 100; "
                f"$t = Get-Content -Raw -Encoding UTF8 '{path}'; $s.Speak($t)"
            )
            with self._stop_lock:
                self._process = subprocess.Popen(
                    ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    shell=False,
                )
                process = self._process
            try:
                _stdout, stderr = process.communicate(timeout=240)
            except subprocess.TimeoutExpired as exc:
                process.terminate()
                raise RuntimeError("La synthèse vocale Windows a dépassé le délai") from exc
            if process.returncode != 0:
                detail = (stderr or "").strip()
                raise RuntimeError(detail or f"Windows SAPI a quitté avec le code {process.returncode}")
        finally:
            try:
                Path(tmp.name).unlink(missing_ok=True)
            except Exception:
                pass


__all__ = ["VoiceEngine", "VoiceStatus", "prepare_spoken_text"]
