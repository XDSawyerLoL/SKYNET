import tempfile
import unittest
from pathlib import Path

from skynet.windows import WindowsController, WindowsError


class WindowsControllerTests(unittest.TestCase):
    def test_windows_controller_uses_injected_runner(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            calls = []

            def fake(script: str, timeout: int) -> str:
                calls.append((script, timeout))
                return '[{"Id":1,"ProcessName":"demo","MainWindowTitle":"Demo"}]'

            controller = WindowsController(Path(tmp), runner=fake)
            result = controller.list_windows()
            self.assertIn("Demo", result)
            self.assertTrue(calls)

    def test_screenshot_cannot_escape_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            controller = WindowsController(Path(tmp), runner=lambda script, timeout: "ok")
            with self.assertRaises(WindowsError):
                controller.screenshot("../outside.png")


if __name__ == "__main__":
    unittest.main()
