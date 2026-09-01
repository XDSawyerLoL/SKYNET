from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from skynet.voice import VoiceEngine, prepare_spoken_text
from skynet.voice_worker import _split_for_prosody


class VoiceIsolationV0121Tests(unittest.TestCase):
    def test_spoken_text_removes_visual_noise(self) -> None:
        text = "## Résultat 🚀\n- **Prêt** ✅\nVoir https://example.com puis `code`."
        spoken = prepare_spoken_text(text)
        self.assertNotIn("🚀", spoken)
        self.assertNotIn("✅", spoken)
        self.assertNotIn("https://", spoken)
        self.assertNotIn("**", spoken)
        self.assertIn("Résultat", spoken)
        self.assertIn("Prêt", spoken)

    def test_prosody_split_prefers_sentence_boundaries(self) -> None:
        chunks = _split_for_prosody(
            "Première phrase assez courte. Deuxième phrase avec une question ? Troisième phrase finale.",
            max_chars=48,
        )
        self.assertGreaterEqual(len(chunks), 2)
        self.assertTrue(all(len(chunk) <= 80 for chunk in chunks))
        self.assertTrue(chunks[0].endswith("."))

    def test_premium_detection_requires_isolated_venv_and_female_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / ".skynet"
            voice = data / "voice"
            python = voice / "venv" / "Scripts" / "python.exe"
            python.parent.mkdir(parents=True, exist_ok=True)
            python.write_bytes(b"")
            (voice / "chatterbox.enabled").write_text("female-reference-validated", encoding="ascii")

            engine = VoiceEngine(data)
            try:
                self.assertNotEqual(engine.status().provider, "Chatterbox Multilingual V3")
                self.assertFalse(engine.diagnostics()["female_reference_valid"])

                (voice / "reference.wav").write_bytes(b"R" * 25000)
                status = engine.refresh()
                self.assertEqual(status.provider, "Chatterbox Multilingual V3")
                self.assertIn("féminine", status.voice)
                self.assertTrue(engine.diagnostics()["premium_python_exists"])
                self.assertTrue(engine.diagnostics()["female_reference_valid"])
            finally:
                engine.close()


if __name__ == "__main__":
    unittest.main()
