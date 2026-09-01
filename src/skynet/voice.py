from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
import tempfile
import threading
from typing import Callable


@dataclass(frozen=True, slots=True)
class VoiceStatus:
    provider: str
    ready: bool
    voice: str
    detail: str
    last_error: str = ""


class VoiceEngine:
    """Local-first TTS with Kokoro neural speech and Windows SAPI fallback.

    The engine deliberately keeps speech outside the agent authority boundary:
    it can render assistant text, but it cannot execute commands. Kokoro is
    optional and is discovered at runtime; Windows SAPI remains the fallback.
    """

    def __init__(self, data_dir: Path, on_state: Callable[[str], None] | None = None) -> None:
        self.data_dir = Path(data_dir)
        self.voice_dir = self.data_dir / "voice"
        self.voice_dir.mkdir(parents=True, exist_ok=True)
        self.model_path = self.voice_dir / "kokoro-v1.0.onnx"
        self.voices_path = self.voice_dir / "voices-v1.0.bin"
        self.on_state = on_state
        self._thread: threading.Thread | None = None
        self._process: subprocess.Popen | None = None
        self._stop_lock = threading.RLock()
        self._kokoro = None
        self._last_error = ""
        self._provider = self._detect_provider()

    @property
    def last_error(self) -> str:
        return self._last_error

    def _detect_provider(self) -> str:
        if self.model_path.exists() and self.voices_path.exists():
            try:
                import kokoro_onnx  # noqa: F401
                import sounddevice  # noqa: F401
                import soundfile  # noqa: F401
                from misaki import espeak  # noqa: F401
                from misaki.espeak import EspeakG2P  # noqa: F401
                return "kokoro-local"
            except Exception as exc:
                self._last_error = f"Kokoro runtime unavailable: {type(exc).__name__}: {exc}"
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
        if self._provider == "kokoro-local":
            return VoiceStatus(
                provider="Kokoro 82M local",
                ready=True,
                voice="ff_siwis",
                detail="Neural local voice · French · no cloud API",
                last_error=self._last_error,
            )
        if self._powershell_ready():
            return VoiceStatus(
                provider="Windows SAPI",
                ready=True,
                voice="best available French voice",
                detail="Offline fallback. Run install-voice.ps1 for neural Kokoro.",
                last_error=self._last_error,
            )
        return VoiceStatus("none", False, "", "No local TTS provider available", self._last_error)

    def refresh(self) -> VoiceStatus:
        self._last_error = ""
        self._provider = self._detect_provider()
        return self.status()

    def diagnostics(self) -> dict:
        devices: list[str] = []
        default_device = "unknown"
        try:
            import sounddevice as sd
            raw = sd.query_devices()
            devices = [f"{i}: {item['name']} (out={item['max_output_channels']})" for i, item in enumerate(raw)]
            default_device = str(sd.default.device)
        except Exception as exc:
            devices = [f"sounddevice unavailable: {type(exc).__name__}: {exc}"]
        status = self.status()
        return {
            "provider": status.provider,
            "ready": status.ready,
            "voice": status.voice,
            "detail": status.detail,
            "last_error": self._last_error,
            "model_exists": self.model_path.exists(),
            "voices_exists": self.voices_path.exists(),
            "default_audio_device": default_device,
            "audio_devices": devices,
        }

    def speak(self, text: str) -> None:
        clean = " ".join(str(text).split()).strip()
        if not clean:
            return
        self.stop()
        self._thread = threading.Thread(target=self._speak_worker, args=(clean,), daemon=True, name="skynet-voice")
        self._thread.start()

    def speak_blocking(self, text: str) -> None:
        clean = " ".join(str(text).split()).strip()
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
        try:
            if self._provider == "kokoro-local":
                self._speak_kokoro(text)
            else:
                self._speak_windows(text)
        except Exception as neural_exc:
            self._last_error = f"{type(neural_exc).__name__}: {neural_exc}"
            if self._provider == "kokoro-local":
                self._emit(f"fallback:{self._last_error}")
                try:
                    self._speak_windows(text)
                except Exception as sapi_exc:
                    self._last_error += f" | SAPI fallback: {type(sapi_exc).__name__}: {sapi_exc}"
                    self._emit(f"error:{self._last_error}")
                    return
            else:
                self._emit(f"error:{self._last_error}")
                return
        self._emit("idle")

    def _speak_kokoro(self, text: str) -> None:
        import sounddevice as sd
        from kokoro_onnx import Kokoro
        from misaki import espeak
        from misaki.espeak import EspeakG2P

        # This mirrors kokoro-onnx's official French example. Initialising the
        # fallback explicitly matters on systems where phonemizer discovery is
        # not automatic.
        _fallback = espeak.EspeakFallback(british=False)
        g2p = EspeakG2P(language="fr-fr")
        phonemes, _ = g2p(text)
        if not phonemes:
            raise RuntimeError("French phonemizer returned no phonemes")

        if self._kokoro is None:
            self._kokoro = Kokoro(str(self.model_path), str(self.voices_path))
        samples, sample_rate = self._kokoro.create(
            phonemes,
            voice="ff_siwis",
            speed=1.02,
            is_phonemes=True,
        )
        if samples is None or len(samples) == 0:
            raise RuntimeError("Kokoro returned an empty audio buffer")
        sd.play(samples, samplerate=sample_rate)
        sd.wait()

    def _speak_windows(self, text: str) -> None:
        # Pass text through a UTF-8 temporary file to avoid command-line quoting
        # issues and never execute assistant text as PowerShell source.
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
                "if (-not $v) {throw 'No Windows speech voice is installed'}; "
                "$s.SelectVoice($v.Name); $s.Rate = 0; $s.Volume = 100; "
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
                raise RuntimeError("Windows SAPI speech timed out") from exc
            if process.returncode != 0:
                detail = (stderr or "").strip()
                raise RuntimeError(detail or f"Windows SAPI exited with code {process.returncode}")
        finally:
            try:
                Path(tmp.name).unlink(missing_ok=True)
            except Exception:
                pass


__all__ = ["VoiceEngine", "VoiceStatus"]
