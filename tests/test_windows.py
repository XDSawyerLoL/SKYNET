from pathlib import Path

import pytest

from skynet.windows import WindowsController, WindowsError


def test_windows_controller_uses_injected_runner(tmp_path: Path) -> None:
    calls = []

    def fake(script: str, timeout: int) -> str:
        calls.append((script, timeout))
        return '[{"Id":1,"ProcessName":"demo","MainWindowTitle":"Demo"}]'

    controller = WindowsController(tmp_path, runner=fake)
    result = controller.list_windows()
    assert "Demo" in result
    assert calls


def test_screenshot_cannot_escape_workspace(tmp_path: Path) -> None:
    controller = WindowsController(tmp_path, runner=lambda script, timeout: "ok")
    with pytest.raises(WindowsError):
        controller.screenshot("../outside.png")
