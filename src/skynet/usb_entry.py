from __future__ import annotations

import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib import error, request

from .portable_entry import portable_root
from .usb_proxy import USBProxy, USB_MODEL


MODEL_FILE = "Qwen3-4B-Q4_K_M.gguf"
ENGINE_PORT_HOST = "127.0.0.1"


def usb_layout(root: Path) -> dict[str, Path]:
    root = Path(root).resolve()
    return {
        "root": root,
        "model": root / "models" / MODEL_FILE,
        "vulkan": root / "engine" / "vulkan",
        "cpu": root / "engine" / "cpu",
        "data": root / ".skynet",
        "workspace": root / "workspace",
        "logs": root / ".skynet" / "logs",
    }


def find_llama_server(folder: Path) -> Path | None:
    if not folder.exists():
        return None
    direct = folder / "llama-server.exe"
    if direct.exists():
        return direct
    matches = list(folder.rglob("llama-server.exe"))
    return matches[0] if matches else None


def find_free_port(host: str = ENGINE_PORT_HOST) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def configure_usb_environment(root: Path, proxy_port: int) -> None:
    os.chdir(root)
    os.environ["SKYNET_PORTABLE"] = "1"
    os.environ["SKYNET_USB"] = "1"
    os.environ["SKYNET_DATA_DIR"] = ".skynet"
    os.environ["SKYNET_WORKSPACE"] = "workspace"
    os.environ["SKYNET_MCP_CONFIG"] = ".skynet/mcp.json"
    os.environ["SKYNET_MODEL"] = USB_MODEL
    os.environ["SKYNET_MODELS"] = USB_MODEL
    os.environ["SKYNET_OLLAMA_URL"] = f"http://127.0.0.1:{proxy_port}"
    os.environ["SKYNET_EMBED_MODEL"] = ""
    os.environ["SKYNET_VISION_MODEL"] = ""


def _http_ready(url: str, timeout: float = 1.0) -> bool:
    try:
        with request.urlopen(url, timeout=timeout) as response:
            return 200 <= int(response.status) < 300
    except Exception:
        return False


def _process_flags() -> int:
    return int(getattr(subprocess, "CREATE_NO_WINDOW", 0)) if os.name == "nt" else 0


class BundledLlama:
    def __init__(self, root: Path, model_path: Path, log_path: Path) -> None:
        self.root = Path(root)
        self.model_path = Path(model_path)
        self.log_path = Path(log_path)
        self.process: subprocess.Popen | None = None
        self.log_handle = None
        self.port: int | None = None
        self.mode = ""

    def _launch(self, executable: Path, mode: str, port: int) -> subprocess.Popen:
        args = [
            str(executable),
            "--model", str(self.model_path),
            "--host", ENGINE_PORT_HOST,
            "--port", str(port),
            "--ctx-size", "8192",
            "--alias", USB_MODEL,
            "--jinja",
        ]
        args += ["--n-gpu-layers", "99" if mode == "vulkan" else "0"]

        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_handle = self.log_path.open("a", encoding="utf-8", errors="replace")
        self.log_handle.write(f"\n--- SKYNET USB engine start: {mode} ---\n")
        self.log_handle.flush()
        return subprocess.Popen(
            args,
            cwd=str(executable.parent),
            stdin=subprocess.DEVNULL,
            stdout=self.log_handle,
            stderr=subprocess.STDOUT,
            creationflags=_process_flags(),
            shell=False,
        )

    def _wait_ready(self, process: subprocess.Popen, port: int, timeout_s: float, progress=None) -> bool:
        deadline = time.monotonic() + timeout_s
        started = time.monotonic()
        while time.monotonic() < deadline:
            if process.poll() is not None:
                return False
            elapsed = int(time.monotonic() - started)
            if progress is not None:
                progress(f"Chargement du modèle local… {elapsed} s")
            if _http_ready(f"http://{ENGINE_PORT_HOST}:{port}/health", timeout=1.0):
                return True
            if _http_ready(f"http://{ENGINE_PORT_HOST}:{port}/v1/models", timeout=1.0):
                return True
            time.sleep(0.35)
        return False

    def start(self, vulkan_dir: Path, cpu_dir: Path, progress=None, *, allow_vulkan: bool = True) -> tuple[str, int]:
        attempts: list[tuple[str, Path | None, float]] = []
        if allow_vulkan:
            attempts.append(("vulkan", find_llama_server(vulkan_dir), 90.0))
        attempts.append(("cpu", find_llama_server(cpu_dir), 150.0))
        missing: list[str] = []
        for mode, executable, timeout_s in attempts:
            if executable is None:
                missing.append(mode)
                continue
            if progress is not None:
                label = "accélération graphique Vulkan" if mode == "vulkan" else "mode processeur universel"
                progress(f"Initialisation du moteur local · {label}")
            port = find_free_port()
            process = self._launch(executable, mode, port)
            if self._wait_ready(process, port, timeout_s, progress=progress):
                self.process = process
                self.port = port
                self.mode = mode
                return mode, port
            try:
                process.terminate()
                process.wait(timeout=4)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass
            if self.log_handle is not None:
                self.log_handle.close()
                self.log_handle = None
        raise RuntimeError(
            "Impossible de démarrer le moteur llama.cpp embarqué. "
            + (f"Moteur(s) absent(s): {', '.join(missing)}. " if missing else "")
            + f"Consultez {self.log_path}."
        )

    def close(self) -> None:
        process = self.process
        self.process = None
        if process is not None and process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=5)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass
        if self.log_handle is not None:
            try:
                self.log_handle.close()
            except Exception:
                pass
            self.log_handle = None


def _missing_message(layout: dict[str, Path]) -> str | None:
    missing: list[str] = []
    if not layout["model"].exists():
        missing.append(str(layout["model"]))
    if find_llama_server(layout["vulkan"]) is None and find_llama_server(layout["cpu"]) is None:
        missing.append(str(layout["root"] / "engine" / "..." / "llama-server.exe"))
    if not missing:
        return None
    return "SKYNET USB est incomplet. Fichier(s) manquant(s) :\n\n" + "\n".join(missing)


def main() -> None:
    root = portable_root()
    layout = usb_layout(root)
    layout["data"].mkdir(parents=True, exist_ok=True)
    layout["workspace"].mkdir(parents=True, exist_ok=True)
    layout["logs"].mkdir(parents=True, exist_ok=True)

    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication, QLabel, QMessageBox, QVBoxLayout, QWidget

    app = QApplication([])
    app.setApplicationName("SKYNET USB")
    app.setOrganizationName("SKYNET Project")
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI Variable", 10))

    missing = _missing_message(layout)
    if missing:
        QMessageBox.critical(None, "SKYNET USB", missing + "\n\nUtilisez PREPARER-SKYNET-USB.cmd pour reconstruire la clé.")
        return

    splash = QWidget()
    splash.setWindowTitle("SKYNET USB")
    splash.setFixedSize(520, 220)
    splash.setStyleSheet("QWidget{background:#212121;color:#ececec;} QLabel{color:#ececec;}")
    box = QVBoxLayout(splash)
    title = QLabel("SKYNET")
    title.setAlignment(Qt.AlignCenter)
    title.setStyleSheet("font-size:30px;font-weight:700;")
    state = QLabel("Initialisation de l'intelligence locale…")
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

    engine = BundledLlama(root, layout["model"], layout["logs"] / "llama-server.log")
    proxy: USBProxy | None = None
    try:
        mode, engine_port = engine.start(layout["vulkan"], layout["cpu"], progress=progress)
        progress("Connexion du noyau SKYNET au modèle local…")
        proxy_port = find_free_port()
        proxy = USBProxy("127.0.0.1", proxy_port, f"http://127.0.0.1:{engine_port}", USB_MODEL)
        proxy.start()
        configure_usb_environment(root, proxy_port)

        deadline = time.monotonic() + 8.0
        while time.monotonic() < deadline and not _http_ready(f"http://127.0.0.1:{proxy_port}/api/tags"):
            app.processEvents()
            time.sleep(0.1)
        if not _http_ready(f"http://127.0.0.1:{proxy_port}/api/tags"):
            raise RuntimeError("Le pont d'inférence local n'a pas démarré.")

        progress("Mémoire et outils locaux en cours d'initialisation…")
        from .desktop_chat import ChatWindow
        from .desktop_chat_launch import ComposerSubmitFilter

        window = ChatWindow()
        submit_filter = ComposerSubmitFilter(window)
        window.entry.installEventFilter(submit_filter)
        window._composer_submit_filter = submit_filter
        window.local_status.setText(
            "● USB autonome · " + ("Vulkan" if mode == "vulkan" else "CPU") + " · Qwen3 4B"
        )
        splash.close()
        window.showMaximized()
        app.exec()
    except Exception as exc:
        splash.close()
        QMessageBox.critical(
            None,
            "SKYNET USB — démarrage impossible",
            f"{type(exc).__name__}: {exc}\n\nJournal : {layout['logs'] / 'llama-server.log'}",
        )
    finally:
        if proxy is not None:
            proxy.close()
        engine.close()


if __name__ == "__main__":
    main()
