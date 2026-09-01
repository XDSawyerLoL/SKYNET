import unittest
from pathlib import Path
import tempfile


class PresenceV011Tests(unittest.TestCase):
    def test_qt_desktop_module_imports(self):
        import skynet.desktop_qt as desktop_qt
        self.assertTrue(callable(desktop_qt.main))
        self.assertTrue(hasattr(desktop_qt, "SkynetWindow"))

    def test_voice_engine_has_offline_fallback_contract(self):
        from skynet.voice import VoiceEngine
        with tempfile.TemporaryDirectory() as tmp:
            engine = VoiceEngine(Path(tmp))
            status = engine.status()
            self.assertIn(status.provider, {"Chatterbox Multilingual V3", "Kokoro 82M local", "Windows SAPI", "aucun"})
            self.assertIsInstance(status.ready, bool)
            engine.stop()

    def test_presence_home_exposes_capability_first_french_language(self):
        import inspect
        import skynet.desktop_qt as desktop_qt
        source = inspect.getsource(desktop_qt.SkynetWindow._build_home)
        self.assertIn("Ce que SKYNET peut réellement faire", source)
        self.assertIn("Piloter Windows", source)
        self.assertIn("Rechercher sur le web", source)
        self.assertIn("Mobiliser plusieurs agents", source)

    def test_voice_text_normalizer_strips_emoji_markdown_and_urls(self):
        from skynet.voice import prepare_spoken_text
        spoken = prepare_spoken_text("## Bonjour 👋 **test** https://example.com\n- Tout va bien ✅")
        self.assertIn("Bonjour", spoken)
        self.assertIn("Tout va bien", spoken)
        self.assertNotIn("👋", spoken)
        self.assertNotIn("✅", spoken)
        self.assertNotIn("**", spoken)
        self.assertNotIn("https", spoken)


if __name__ == "__main__":
    unittest.main()
