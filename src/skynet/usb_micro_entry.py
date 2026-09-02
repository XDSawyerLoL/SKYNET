from __future__ import annotations

import time
from pathlib import Path

from .portable_entry import portable_root
from .usb_proxy import USBProxy
from . import usb_entry as base


MICRO_MODEL_FILE = "SmolLM2-360M-Instruct-Q3_K_M.gguf"
MICRO_MODEL_ID = "smollm2:360m-usb-micro"


def _layout(root: Path) -> dict[str, Path]:
    root = Path(root).resolve()
    return {
        "root": root,
        "model": root / "models" / MICRO_MODEL_FILE,
        "vulkan": root / "engine" / "vulkan",
        "cpu": root / "engine" / "cpu",
        "data": root / ".skynet",
        "workspace": root / "workspace",
        "logs": root / ".skynet" / "logs",
    }


def main() -> None:
    root = portable_root()
    layout = _layout(root)
    for key in ("data", "workspace", "logs"):
        layout[key].mkdir(parents=True, exist_ok=True)

    base.USB_MODEL = MICRO_MODEL_ID

    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication, QLabel, QMessageBox, QVBoxLayout, QWidget

    app = QApplication([])
    app.setApplicationName("SKYNET USB Micro")
    app.setOrganizationName("SKYNET Project")
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI Variable", 10))

    missing: list[str] = []
    if not layout["model"].exists():
        missing.append(str(layout["model"]))
    if base.find_llama_server(layout["cpu"]) is None:
        missing.append(str(root / "engine" / "cpu" / "llama-server.exe"))
    if missing:
        QMessageBox.critical(None, "SKYNET USB Micro", "Package incomplet :\n\n" + "\n".join(missing))
        return

    splash = QWidget()
    splash.setWindowTitle("SKYNET USB Micro")
    splash.setFixedSize(520, 220)
    splash.setStyleSheet("QWidget{background:#212121;color:#ececec;} QLabel{color:#ececec;}")
    box = QVBoxLayout(splash)
    title = QLabel("SKYNET")
    title.setAlignment(Qt.AlignCenter)
    title.setStyleSheet("font-size:30px;font-weight:700;")
    state = QLabel("Initialisation locale…")
    state.setAlignment(Qt.AlignCenter)
    state.setWordWrap(True)
    state.setStyleSheet("font-size:13px;color:#b5b5b5;")
    box.addStretch(1)
    box.addWidget(title)
    box.addWidget(state)
    box.addStretch(1)
    splash.show()
    app.processEvents()

    def progress(text: str) -> None:
        state.setText(text)
        app.processEvents()

    engine = base.BundledLlama(root, layout["model"], layout["logs"] / "llama-server.log")
    proxy: USBProxy | None = None
    try:
        # CPU-only package: pass the same CPU folder for both attempts so no Vulkan files are required.
        mode, engine_port = engine.start(layout["cpu"], layout["cpu"], progress=progress)
        progress("Connexion du noyau SKYNET au modèle local…")
        proxy_port = base.find_free_port()
        proxy = USBProxy("127.0.0.1", proxy_port, f"http://127.0.0.1:{engine_port}", MICRO_MODEL_ID)
        proxy.start()
        base.configure_usb_environment(root, proxy_port)

        deadline = time.monotonic() + 8.0
        while time.monotonic() < deadline and not base._http_ready(f"http://127.0.0.1:{proxy_port}/api/tags"):
            app.processEvents()
            time.sleep(0.1)
        if not base._http_ready(f"http://127.0.0.1:{proxy_port}/api/tags"):
            raise RuntimeError("Le pont d'inférence local n'a pas démarré.")

        progress("Mémoire et interface en cours d'initialisation…")
        from .desktop_chat import ChatWindow
        from .desktop_chat_launch import ComposerSubmitFilter

        window = ChatWindow()
        submit_filter = ComposerSubmitFilter(window)
        window.entry.installEventFilter(submit_filter)
        window._composer_submit_filter = submit_filter
        window.local_status.setText("● USB autonome Micro · CPU · SmolLM2 360M")
        splash.close()
        window.showMaximized()
        app.exec()
    except Exception as exc:
        splash.close()
        QMessageBox.critical(
            None,
            "SKYNET USB Micro — démarrage impossible",
            f"{type(exc).__name__}: {exc}\n\nJournal : {layout['logs'] / 'llama-server.log'}",
        )
    finally:
        if proxy is not None:
            proxy.close()
        engine.close()


if __name__ == "__main__":
    main()
