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
            self.assertIn(status.provider, {"Kokoro 82M local", "Windows SAPI", "none"})
            self.assertIsInstance(status.ready, bool)
            engine.stop()

    def test_presence_home_exposes_capability_first_language(self):
        import inspect
        import skynet.desktop_qt as desktop_qt
        source = inspect.getsource(desktop_qt.SkynetWindow._build_home)
        self.assertIn("What SKYNET can actually do", source)
        self.assertIn("Operate Windows", source)
        self.assertIn("Research & browse", source)
        self.assertIn("Multi-agent", source)


if __name__ == "__main__":
    unittest.main()
