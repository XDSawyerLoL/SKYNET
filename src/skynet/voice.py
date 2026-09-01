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


class VoiceEngine:
    """Local-first TTS with a Kokoro neural path and Windows SAPI fallback.

    Kokoro is optional and discovered at runtime. The base SKYNET install stays
    usable without the large voice model; `install-voice.ps1` enables the
    neural provider. Runtime speech never requires a paid API.
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
        self._provider = self._detect_provider()

    def _detect_provider(self) -> str:
        if self.model_path.exists() and self.voices_path.exists():
            try:
                import kokoro_onnx  # noqa: F401
                import sounddevice  # noqa: F401
                import soundfile  # noqa: F401
                from misaki.espeak import EspeakG2P  # noqa: F401
                return "kokoro-local"
            except Exception:
                pass
        return "windows-sapi"

    def status(self) -> VoiceStatus:
        if self._provider == "kokoro-local":
            return VoiceStatus(
                provider="Kokoro 82M local",
                ready=True,
                voice="ff_siwis",
                detail="Neural local voice · French · no cloud API",
            )
        if subprocess.run(
            ["powershell", "-NoProfile", "-Command", "$PSVersionTable.PSVersion.Major"],
            capture_output=True,
            text=True,
            timeout=3,
            shell=False,
        ).returncode == 0:
            return VoiceStatus(
                provider="Windows SAPI",
                ready=True,
                voice="best available French voice",
                detail="Offline fallback. Run install-voice.ps1 for neural Kokoro.",
            )
        return VoiceStatus("none", False, "", "No local TTS provider available")

    def refresh(self) -> VoiceStatus:
        self._provider = self._detect_provider()
        return self.status()

    def speak(self, text: str) -> None:
        clean = " ".join(str(text).split()).strip()
        if not clean:
            return
        self.stop()
        self._thread = threading.Thread(target=self._speak_worker, args=(clean,), daemon=True, name="skynet-voice")
        self._thread.start()

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
        self._emit("speaking")
        try:
            if self._provider == "kokoro-local":
                self._speak_kokoro(text)
            else:
                self._speak_windows(text)
        except Exception:
            # Neural path can fail because of missing runtime DLLs/espeak even
            # after assets were downloaded. Fall back rather than losing voice.
            try:
                self._speak_windows(text)
            except Exception:
                self._emit("error")
                return
        self._emit("idle")

    def _speak_kokoro(self, text: str) -> None:
        import sounddevice as sd
        from kokoro_onnx import Kokoro
        from misaki.espeak import EspeakG2P

        if self._kokoro is None:
            self._kokoro = Kokoro(str(self.model_path), str(self.voices_path))
        g2p = EspeakG2P(language="fr-fr")
        phonemes, _ = g2p(text)
        samples, sample_rate = self._kokoro.create(phonemes, "ff_siwis", is_phonemes=True, speed=1.02)
        sd.play(samples, sample_rate)
        sd.wait()

    def _speak_windows(self, text: str) -> None:
        # Pass text through a UTF-8 temporary file to avoid command-line quoting
        # issues and never execute user text as PowerShell source.
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
                "if ($v) {$s.SelectVoice($v.Name)}; "
                "$s.Rate = 0; $s.Volume = 100; "
                f"$t = Get-Content -Raw -Encoding UTF8 '{path}'; $s.Speak($t)"
            )
            with self._stop_lock:
                self._process = subprocess.Popen(
                    ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    shell=False,
                )
                process = self._process
            process.wait(timeout=240)
        finally:
            try:
                Path(tmp.name).unlink(missing_ok=True)
            except Exception:
                pass


__all__ = ["VoiceEngine", "VoiceStatus"]
