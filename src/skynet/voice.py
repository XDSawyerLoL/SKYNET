from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import os
import re
import subprocess
import tempfile
import threading
import unicodedata
import uuid
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
    """Transform rich assistant output into prose suitable for speech."""

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
    """French local TTS with an isolated premium runtime.

    Provider priority:
      Chatterbox Multilingual V3 worker -> Kokoro 82M -> Windows SAPI.

    Chatterbox deliberately lives in `.skynet/voice/venv`. Its pinned numpy,
    torch and transformers versions therefore cannot mutate SKYNET's core venv.
    The worker remains alive after loading the model so subsequent utterances do
    not pay model startup cost again.
    """

    def __init__(self, data_dir: Path, on_state: Callable[[str], None] | None = None) -> None:
        self.data_dir = Path(data_dir)
        self.voice_dir = self.data_dir / "voice"
        self.voice_dir.mkdir(parents=True, exist_ok=True)
        self.model_path = self.voice_dir / "kokoro-v1.0.onnx"
        self.voices_path = self.voice_dir / "voices-v1.0.bin"
        self.chatterbox_marker = self.voice_dir / "chatterbox.enabled"
        self.reference_path = self.voice_dir / "reference.wav"
        self.worker_script = Path(__file__).with_name("voice_worker.py").resolve()
        self.on_state = on_state
        self._thread: threading.Thread | None = None
        self._process: subprocess.Popen | None = None
        self._premium_process: subprocess.Popen | None = None
        self._premium_log_handle = None
        self._stop_lock = threading.RLock()
        self._premium_lock = threading.RLock()
        self._kokoro = None
        self._last_error = ""
        self._provider = self._detect_provider()

    @property
    def last_error(self) -> str:
        return self._last_error

    def _premium_python(self) -> Path:
        windows = self.voice_dir / "venv" / "Scripts" / "python.exe"
        if windows.exists():
            return windows
        return self.voice_dir / "venv" / "bin" / "python"

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
        python = self._premium_python()
        return self.chatterbox_marker.exists() and python.exists() and self.worker_script.exists()

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
            detail = "Voix premium locale · français · moteur isolé et persistant"
            if self._premium_process is not None and self._premium_process.poll() is None:
                detail += " · modèle chaud"
            return VoiceStatus("Chatterbox Multilingual V3", True, reference, detail, self._last_error)
        if self._provider == "kokoro-local":
            return VoiceStatus(
                "Kokoro 82M local",
                True,
                "ff_siwis",
                "Voix neuronale locale · français · mode rapide",
                self._last_error,
            )
        if self._powershell_ready():
            return VoiceStatus(
                "Windows SAPI",
                True,
                "meilleure voix française disponible",
                "Mode de secours hors ligne",
                self._last_error,
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
        premium_python = self._premium_python()
        return {
            "provider": status.provider,
            "ready": status.ready,
            "voice": status.voice,
            "detail": status.detail,
            "last_error": self._last_error,
            "kokoro_model_exists": self.model_path.exists(),
            "kokoro_voices_exists": self.voices_path.exists(),
            "chatterbox_enabled": self.chatterbox_marker.exists(),
            "premium_python_exists": premium_python.exists(),
            "premium_worker_alive": self._premium_process is not None and self._premium_process.poll() is None,
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
        """Stop current playback without unloading the premium model."""
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

    def close(self) -> None:
        self.stop()
        with self._premium_lock:
            process = self._premium_process
            self._premium_process = None
            if process is not None and process.poll() is None:
                try:
                    if process.stdin is not None:
                        process.stdin.write(json.dumps({"cmd": "shutdown", "id": uuid.uuid4().hex}) + "\n")
                        process.stdin.flush()
                    process.wait(timeout=3)
                except Exception:
                    try:
                        process.terminate()
                    except Exception:
                        pass
            if self._premium_log_handle is not None:
                try:
                    self._premium_log_handle.close()
                except Exception:
                    pass
                self._premium_log_handle = None

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

    def _premium_log_tail(self) -> str:
        path = self.voice_dir / "chatterbox-worker.log"
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            return " | ".join(lines[-6:])[-1200:]
        except Exception:
            return ""

    def _ensure_premium_worker(self) -> subprocess.Popen:
        with self._premium_lock:
            if self._premium_process is not None and self._premium_process.poll() is None:
                return self._premium_process

            python = self._premium_python()
            if not python.exists():
                raise RuntimeError("environnement vocal premium absent; relancez install-voice-premium.ps1")
            if not self.worker_script.exists():
                raise RuntimeError("voice_worker.py est introuvable")

            log_path = self.voice_dir / "chatterbox-worker.log"
            if self._premium_log_handle is not None:
                try:
                    self._premium_log_handle.close()
                except Exception:
                    pass
            self._premium_log_handle = log_path.open("a", encoding="utf-8")
            env = dict(os.environ)
            env["PYTHONUTF8"] = "1"
            self._emit("loading:Chatterbox")
            process = subprocess.Popen(
                [str(python), "-u", str(self.worker_script)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=self._premium_log_handle,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                shell=False,
                env=env,
            )
            self._premium_process = process
            if process.stdout is None:
                raise RuntimeError("sortie du moteur premium indisponible")
            line = process.stdout.readline().strip()
            if not line:
                raise RuntimeError("le moteur premium s'est arrêté au chargement: " + self._premium_log_tail())
            try:
                ready = json.loads(line)
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"réponse de démarrage vocal invalide: {line[:300]}") from exc
            if not ready.get("ok"):
                raise RuntimeError(str(ready.get("error") or "échec du chargement Chatterbox"))
            self._emit(f"ready:Chatterbox {ready.get('variant', '')} {ready.get('device', '')}".strip())
            return process

    def _speak_chatterbox(self, text: str) -> None:
        import sounddevice as sd
        import soundfile as sf

        with self._premium_lock:
            process = self._ensure_premium_worker()
            if process.stdin is None or process.stdout is None:
                raise RuntimeError("canal du moteur premium indisponible")
            request_id = uuid.uuid4().hex
            cache = self.voice_dir / "cache"
            cache.mkdir(parents=True, exist_ok=True)
            output = cache / f"{request_id}.wav"
            payload = {
                "cmd": "synth",
                "id": request_id,
                "text": text,
                "output": str(output.resolve()),
                "reference": str(self.reference_path.resolve()) if self.reference_path.exists() else None,
            }
            try:
                process.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
                process.stdin.flush()
                line = process.stdout.readline().strip()
                if not line:
                    raise RuntimeError("le moteur premium s'est interrompu: " + self._premium_log_tail())
                response = json.loads(line)
                if response.get("id") != request_id:
                    raise RuntimeError("réponse vocale désynchronisée")
                if not response.get("ok"):
                    raise RuntimeError(str(response.get("error") or "échec de synthèse Chatterbox"))
                samples, sample_rate = sf.read(output, dtype="float32", always_2d=False)
                if getattr(samples, "size", len(samples)) == 0:
                    raise RuntimeError("fichier audio premium vide")
                sd.play(samples, samplerate=int(sample_rate))
                sd.wait()
            finally:
                try:
                    output.unlink(missing_ok=True)
                except Exception:
                    pass

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
