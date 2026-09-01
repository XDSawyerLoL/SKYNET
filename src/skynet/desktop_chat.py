from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import html
import time
import uuid

from PySide6.QtCore import Qt, QTimer, Signal, QObject
from PySide6.QtGui import QAction, QFont, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .runtime import Runtime
from .voice import VoiceEngine


BG = "#212121"
SIDEBAR = "#171717"
SURFACE = "#2f2f2f"
SURFACE_HOVER = "#383838"
TEXT = "#ececec"
MUTED = "#a9a9a9"
FAINT = "#747474"
BORDER = "#3d3d3d"
ACCENT = "#ffffff"
GREEN = "#35c48d"
RED = "#f16f6f"


STYLE = f"""
QWidget {{ background:{BG}; color:{TEXT}; font-family:'Segoe UI Variable','Segoe UI',sans-serif; font-size:14px; }}
QMainWindow {{ background:{BG}; }}
QFrame#sidebar {{ background:{SIDEBAR}; border-right:1px solid #242424; }}
QFrame#topbar {{ background:{BG}; border-bottom:1px solid #2a2a2a; }}
QFrame#composer {{ background:{SURFACE}; border:1px solid #4a4a4a; border-radius:24px; }}
QFrame#userBubble {{ background:{SURFACE}; border:0; border-radius:18px; }}
QFrame#suggestion {{ background:#292929; border:1px solid {BORDER}; border-radius:16px; }}
QFrame#suggestion:hover {{ background:{SURFACE_HOVER}; }}
QPushButton {{ background:transparent; border:0; border-radius:10px; color:{TEXT}; padding:9px 11px; text-align:left; }}
QPushButton:hover {{ background:{SURFACE_HOVER}; }}
QPushButton#newChat {{ background:#242424; border:1px solid #333333; border-radius:12px; font-weight:600; }}
QPushButton#newChat:hover {{ background:#303030; }}
QPushButton#send {{ background:{ACCENT}; color:#111111; border-radius:18px; min-width:36px; max-width:36px; min-height:36px; max-height:36px; padding:0; text-align:center; font-weight:800; }}
QPushButton#chip {{ background:#292929; border:1px solid {BORDER}; border-radius:14px; color:{MUTED}; padding:6px 10px; }}
QPushButton#chip:checked {{ color:{TEXT}; border:1px solid #777777; background:#3a3a3a; }}
QTextEdit {{ background:transparent; border:0; color:{TEXT}; padding:8px 4px; selection-background-color:#555555; }}
QListWidget {{ background:transparent; border:0; outline:0; }}
QListWidget::item {{ color:{MUTED}; padding:9px 8px; border-radius:8px; }}
QListWidget::item:hover {{ background:#252525; color:{TEXT}; }}
QListWidget::item:selected {{ background:#2d2d2d; color:{TEXT}; }}
QScrollArea {{ border:0; background:transparent; }}
QScrollBar:vertical {{ background:transparent; width:10px; }}
QScrollBar::handle:vertical {{ background:#454545; min-height:30px; border-radius:5px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
"""


class Bridge(QObject):
    token = Signal(str)
    final = Signal(str)
    error = Signal(str)
    busy = Signal(bool)
    confirm = Signal(str, object)
    warmed = Signal(str)
    warm_error = Signal(str)
    voice_state = Signal(str)


class MessageWidget(QWidget):
    def __init__(self, role: str, text: str = "", parent=None) -> None:
        super().__init__(parent)
        self.role = role
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 8, 0, 8)
        row.setSpacing(10)

        if role == "user":
            row.addStretch(1)
            bubble = QFrame()
            bubble.setObjectName("userBubble")
            bubble.setMaximumWidth(720)
            box = QVBoxLayout(bubble)
            box.setContentsMargins(16, 11, 16, 11)
            self.label = QLabel()
            self.label.setWordWrap(True)
            self.label.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse)
            box.addWidget(self.label)
            row.addWidget(bubble)
        else:
            avatar = QLabel("S")
            avatar.setFixedSize(28, 28)
            avatar.setAlignment(Qt.AlignCenter)
            avatar.setStyleSheet("background:#f0f0f0;color:#1b1b1b;border-radius:14px;font-weight:800;")
            row.addWidget(avatar, 0, Qt.AlignTop)
            self.label = QLabel()
            self.label.setMaximumWidth(780)
            self.label.setWordWrap(True)
            self.label.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse)
            self.label.setStyleSheet(f"color:{TEXT}; line-height:1.45;")
            row.addWidget(self.label, 1, Qt.AlignTop)
            row.addStretch(1)
        self.set_text(text)

    def set_text(self, text: str) -> None:
        value = str(text or "")
        if self.role == "assistant":
            self.label.setTextFormat(Qt.MarkdownText)
            self.label.setText(value)
        else:
            self.label.setTextFormat(Qt.PlainText)
            self.label.setText(value)


class SuggestionCard(QFrame):
    clicked = Signal(str)

    def __init__(self, title: str, detail: str, prompt: str, parent=None) -> None:
        super().__init__(parent)
        self.prompt = prompt
        self.setObjectName("suggestion")
        self.setCursor(Qt.PointingHandCursor)
        box = QVBoxLayout(self)
        box.setContentsMargins(15, 13, 15, 13)
        box.setSpacing(5)
        title_label = QLabel(title)
        title_label.setStyleSheet(f"font-weight:650;color:{TEXT};")
        detail_label = QLabel(detail)
        detail_label.setWordWrap(True)
        detail_label.setStyleSheet(f"color:{MUTED};font-size:12px;")
        box.addWidget(title_label)
        box.addWidget(detail_label)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.prompt)
        super().mousePressEvent(event)


class ChatWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("SKYNET")
        self.resize(1440, 900)
        self.setMinimumSize(980, 680)
        self.setStyleSheet(STYLE)

        self.runtime = Runtime.create(Path.cwd(), session_id="desktop")
        self.bridge = Bridge()
        self.pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix="skynet-chat")
        self.voice = VoiceEngine(self.runtime.config.data_dir, on_state=lambda state: self.bridge.voice_state.emit(state))
        self.voice_enabled = True
        self.force_agent = False
        self.current_assistant: MessageWidget | None = None
        self.current_text = ""
        self.busy = False
        self.welcome: QWidget | None = None

        self._connect_bridge()
        self._build()
        self._install_shortcuts()
        self._load_session(self.runtime.agent.session_id)
        self._refresh_sessions()

        QTimer.singleShot(120, self._warm_model)
        QTimer.singleShot(900, self._announce_startup)

    def _connect_bridge(self) -> None:
        self.bridge.token.connect(self._on_token)
        self.bridge.final.connect(self._on_final)
        self.bridge.error.connect(self._on_error)
        self.bridge.busy.connect(self._set_busy)
        self.bridge.confirm.connect(self._on_confirm)
        self.bridge.warmed.connect(self._on_warmed)
        self.bridge.warm_error.connect(self._on_warm_error)

    def _build(self) -> None:
        root = QWidget()
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_sidebar())
        layout.addWidget(self._build_main(), 1)
        self.setCentralWidget(root)

    def _build_sidebar(self) -> QWidget:
        side = QFrame()
        side.setObjectName("sidebar")
        side.setFixedWidth(252)
        box = QVBoxLayout(side)
        box.setContentsMargins(12, 14, 12, 14)
        box.setSpacing(8)

        brand = QLabel("SKYNET")
        brand.setStyleSheet("font-size:18px;font-weight:750;padding:5px 7px 8px 7px;")
        box.addWidget(brand)

        new_chat = QPushButton("＋  Nouvelle conversation")
        new_chat.setObjectName("newChat")
        new_chat.clicked.connect(self.new_chat)
        box.addWidget(new_chat)

        section = QLabel("RÉCENT")
        section.setStyleSheet(f"color:{FAINT};font-size:10px;font-weight:700;padding:10px 8px 0 8px;")
        box.addWidget(section)

        self.sessions_list = QListWidget()
        self.sessions_list.itemClicked.connect(self._session_clicked)
        box.addWidget(self.sessions_list, 1)

        capabilities = QPushButton("◇  Ce que SKYNET peut faire")
        capabilities.clicked.connect(self._show_capabilities)
        box.addWidget(capabilities)

        self.local_status = QLabel("● Local · préparation…")
        self.local_status.setStyleSheet(f"color:{MUTED};font-size:11px;padding:6px 8px;")
        box.addWidget(self.local_status)
        return side

    def _build_main(self) -> QWidget:
        host = QWidget()
        box = QVBoxLayout(host)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(0)

        top = QFrame()
        top.setObjectName("topbar")
        top.setFixedHeight(58)
        top_box = QHBoxLayout(top)
        top_box.setContentsMargins(22, 8, 18, 8)
        title = QLabel("SKYNET")
        title.setStyleSheet("font-size:16px;font-weight:650;")
        top_box.addWidget(title)
        model = QLabel(self.runtime.router.last_route.model)
        model.setStyleSheet(f"color:{MUTED};font-size:12px;")
        self.model_label = model
        top_box.addWidget(model)
        top_box.addStretch(1)
        self.mode_label = QLabel("Auto")
        self.mode_label.setStyleSheet(f"color:{MUTED};font-size:12px;")
        top_box.addWidget(self.mode_label)
        box.addWidget(top)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll_host = QWidget()
        self.messages = QVBoxLayout(self.scroll_host)
        self.messages.setContentsMargins(0, 18, 0, 20)
        self.messages.setSpacing(1)
        self.messages.addStretch(1)
        self.scroll.setWidget(self.scroll_host)
        box.addWidget(self.scroll, 1)

        composer_wrap = QWidget()
        composer_outer = QVBoxLayout(composer_wrap)
        composer_outer.setContentsMargins(24, 10, 24, 20)
        composer_outer.setSpacing(6)

        center = QHBoxLayout()
        center.addStretch(1)
        composer = QFrame()
        composer.setObjectName("composer")
        composer.setMaximumWidth(900)
        composer.setMinimumWidth(560)
        cbox = QVBoxLayout(composer)
        cbox.setContentsMargins(14, 8, 10, 8)
        cbox.setSpacing(5)

        self.entry = QTextEdit()
        self.entry.setPlaceholderText("Message à SKYNET")
        self.entry.setFixedHeight(64)
        cbox.addWidget(self.entry)

        controls = QHBoxLayout()
        controls.setSpacing(7)
        plus = QPushButton("＋")
        plus.setObjectName("chip")
        plus.setToolTip("Capacités")
        plus.clicked.connect(self._show_capabilities)
        controls.addWidget(plus)

        self.agent_button = QPushButton("Mode agent")
        self.agent_button.setObjectName("chip")
        self.agent_button.setCheckable(True)
        self.agent_button.setToolTip("Force l'utilisation du moteur agentique complet et des outils")
        self.agent_button.toggled.connect(self._toggle_agent)
        controls.addWidget(self.agent_button)

        self.voice_button = QPushButton("Voix")
        self.voice_button.setObjectName("chip")
        self.voice_button.setCheckable(True)
        self.voice_button.setChecked(True)
        self.voice_button.toggled.connect(self._toggle_voice)
        controls.addWidget(self.voice_button)
        controls.addStretch(1)

        self.send_button = QPushButton("↑")
        self.send_button.setObjectName("send")
        self.send_button.clicked.connect(self.send_message)
        controls.addWidget(self.send_button)
        cbox.addLayout(controls)
        center.addWidget(composer, 1)
        center.addStretch(1)
        composer_outer.addLayout(center)

        hint = QLabel("Entrée pour envoyer · Maj+Entrée pour une nouvelle ligne · le mode agent s'active automatiquement pour les actions")
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet(f"color:{FAINT};font-size:10px;")
        composer_outer.addWidget(hint)
        box.addWidget(composer_wrap)
        return host

    def _install_shortcuts(self) -> None:
        send = QAction(self)
        send.setShortcut(QKeySequence("Ctrl+Return"))
        send.triggered.connect(self.send_message)
        self.addAction(send)

    def _show_welcome(self) -> None:
        if self.welcome is not None:
            return
        welcome = QWidget()
        welcome.setMaximumWidth(850)
        box = QVBoxLayout(welcome)
        box.setContentsMargins(30, 70, 30, 30)
        box.setSpacing(16)
        title = QLabel("Comment puis-je vous aider ?")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size:30px;font-weight:650;")
        box.addWidget(title)
        subtitle = QLabel("Discutez naturellement, ou confiez une action à SKYNET. Le mode agentique s'active quand des outils sont nécessaires.")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(f"color:{MUTED};font-size:13px;")
        box.addWidget(subtitle)

        cards = (
            ("Piloter mon PC", "Windows, applications et écran", "Inspecte ce PC et propose une démonstration simple et sûre de ce que tu peux réellement contrôler."),
            ("Rechercher", "Web, preuves et synthèse", "Fais une recherche approfondie sur un sujet que je vais te donner et vérifie les informations."),
            ("Coder", "Projet, diagnostic et tests", "Analyse un projet de code que je vais t'indiquer, trouve les problèmes prioritaires et propose des corrections vérifiables."),
            ("Automatiser", "Routines et tâches récurrentes", "Aide-moi à automatiser une tâche répétitive sur ce PC en gardant les actions sensibles sous contrôle."),
        )
        for i in range(0, len(cards), 2):
            row = QHBoxLayout()
            row.setSpacing(10)
            for title_text, detail, prompt in cards[i:i+2]:
                card = SuggestionCard(title_text, detail, prompt)
                card.clicked.connect(self._fill_prompt)
                row.addWidget(card, 1)
            box.addLayout(row)
        self.welcome = welcome
        self.messages.insertWidget(self.messages.count() - 1, welcome, 0, Qt.AlignHCenter)

    def _remove_welcome(self) -> None:
        if self.welcome is None:
            return
        self.messages.removeWidget(self.welcome)
        self.welcome.deleteLater()
        self.welcome = None

    def _add_message(self, role: str, text: str = "") -> MessageWidget:
        self._remove_welcome()
        holder = QWidget()
        holder.setMaximumWidth(920)
        hbox = QHBoxLayout(holder)
        hbox.setContentsMargins(24, 0, 24, 0)
        message = MessageWidget(role, text)
        hbox.addWidget(message, 1)
        self.messages.insertWidget(self.messages.count() - 1, holder, 0, Qt.AlignHCenter)
        QTimer.singleShot(0, self._scroll_bottom)
        return message

    def _scroll_bottom(self) -> None:
        bar = self.scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _fill_prompt(self, prompt: str) -> None:
        self.entry.setPlainText(prompt)
        self.entry.setFocus()

    def send_message(self) -> None:
        if self.busy:
            return
        text = self.entry.toPlainText().strip()
        if not text:
            return
        self.entry.clear()
        self._add_message("user", text)
        self.current_assistant = self._add_message("assistant", "…")
        self.current_text = ""
        force_agent = self.agent_button.isChecked()
        auto_agent = self.runtime.agent.requires_agentic_mode(text)
        self.mode_label.setText("Agent" if force_agent or auto_agent else "Chat rapide")
        self.bridge.busy.emit(True)

        def run() -> None:
            try:
                reply = self.runtime.agent.ask_stream(
                    text,
                    self._confirm_from_worker,
                    on_token=lambda token: self.bridge.token.emit(token),
                    force_agent=force_agent,
                )
                self.bridge.final.emit(reply)
            except Exception as exc:
                self.bridge.error.emit(f"{type(exc).__name__}: {exc}")
            finally:
                self.bridge.busy.emit(False)

        self.pool.submit(run)

    def _confirm_from_worker(self, message: str) -> bool:
        packet = {"event": __import__("threading").Event(), "result": False}
        self.bridge.confirm.emit(message, packet)
        packet["event"].wait()
        return bool(packet["result"])

    def _on_confirm(self, message: str, packet: object) -> None:
        answer = QMessageBox.question(self, "Autorisation SKYNET", message, QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        packet["result"] = answer == QMessageBox.Yes  # type: ignore[index]
        packet["event"].set()  # type: ignore[index]

    def _on_token(self, token: str) -> None:
        if self.current_assistant is None:
            return
        if self.current_text == "" and self.current_assistant.label.text() == "…":
            self.current_assistant.set_text("")
        self.current_text += token
        self.current_assistant.set_text(self.current_text)
        self._scroll_bottom()

    def _on_final(self, reply: str) -> None:
        if self.current_assistant is not None:
            self.current_text = reply
            self.current_assistant.set_text(reply)
        self.current_assistant = None
        self.model_label.setText(self.runtime.router.last_route.model)
        self._refresh_sessions()
        if self.voice_enabled:
            self.voice.speak(reply)

    def _on_error(self, message: str) -> None:
        if self.current_assistant is not None:
            self.current_assistant.set_text(f"Erreur locale : {message}")
        else:
            self._add_message("assistant", f"Erreur locale : {message}")
        self.current_assistant = None
        self.current_text = ""

    def _set_busy(self, busy: bool) -> None:
        self.busy = busy
        self.send_button.setEnabled(not busy)
        self.entry.setReadOnly(busy)
        if not busy:
            self.entry.setFocus()

    def _toggle_agent(self, checked: bool) -> None:
        self.force_agent = checked
        self.mode_label.setText("Agent forcé" if checked else "Auto")

    def _toggle_voice(self, checked: bool) -> None:
        self.voice_enabled = checked
        if not checked:
            self.voice.stop()

    def _warm_model(self) -> None:
        def run() -> None:
            try:
                model = self.runtime.router.warm()
                self.bridge.warmed.emit(model)
            except Exception as exc:
                self.bridge.warm_error.emit(str(exc))
        self.pool.submit(run)

    def _on_warmed(self, model: str) -> None:
        self.model_label.setText(model)
        self.local_status.setText(f"● Local · {model} prêt")
        self.local_status.setStyleSheet(f"color:{GREEN};font-size:11px;padding:6px 8px;")

    def _on_warm_error(self, message: str) -> None:
        self.local_status.setText("● Ollama à vérifier")
        self.local_status.setToolTip(message)
        self.local_status.setStyleSheet(f"color:{RED};font-size:11px;padding:6px 8px;")

    def _announce_startup(self) -> None:
        if not self.voice_enabled:
            return
        hour = time.localtime().tm_hour
        hello = "Bonjour" if 5 <= hour < 18 else "Bonsoir"
        self.voice.speak(f"{hello}. SKYNET est en ligne. Je suis prête.")

    def _show_capabilities(self) -> None:
        QMessageBox.information(
            self,
            "Capacités de SKYNET",
            "SKYNET peut discuter rapidement, puis basculer automatiquement vers son moteur agentique pour :\n\n"
            "• piloter Windows et inspecter l'écran ;\n"
            "• naviguer et rechercher sur le web ;\n"
            "• travailler sur des fichiers, du code et PowerShell ;\n"
            "• utiliser des intégrations et outils MCP ;\n"
            "• mémoriser les sessions et procédures utiles ;\n"
            "• créer des routines et automatisations ;\n"
            "• mobiliser plusieurs spécialistes sur les tâches complexes.\n\n"
            "Les actions sensibles restent gouvernées par les permissions et les reçus d'exécution.",
        )

    def _refresh_sessions(self) -> None:
        try:
            sessions = self.runtime.sessions.list(limit=40)
        except Exception:
            sessions = []
        current = self.runtime.agent.session_id
        self.sessions_list.clear()
        for session in sessions:
            title = str(getattr(session, "title", getattr(session, "session_id", "Conversation")))
            sid = str(getattr(session, "session_id", ""))
            item = QListWidgetItem(title or "Conversation")
            item.setData(Qt.UserRole, sid)
            self.sessions_list.addItem(item)
            if sid == current:
                self.sessions_list.setCurrentItem(item)

    def _session_clicked(self, item: QListWidgetItem) -> None:
        sid = str(item.data(Qt.UserRole) or "")
        if sid and not self.busy:
            self._load_session(sid)

    def _clear_messages(self) -> None:
        while self.messages.count() > 1:
            item = self.messages.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.welcome = None

    def _load_session(self, session_id: str) -> None:
        self.runtime.agent.session_id = session_id
        self._clear_messages()
        rows = self.runtime.memory.recent_messages(session_id, limit=80)
        if not rows:
            self._show_welcome()
            return
        for message in rows:
            role = str(message.get("role", "")).lower()
            if role in {"user", "assistant"}:
                self._add_message(role, str(message.get("content", "")))
        self._scroll_bottom()

    def new_chat(self) -> None:
        if self.busy:
            return
        sid = f"chat-{uuid.uuid4().hex[:12]}"
        self.runtime.sessions.ensure(sid, title="Nouvelle conversation", channel="local")
        self.runtime.agent.session_id = sid
        self._clear_messages()
        self._show_welcome()
        self._refresh_sessions()
        self.entry.setFocus()

    def closeEvent(self, event) -> None:
        try:
            self.voice.close()
        except Exception:
            pass
        self.pool.shutdown(wait=False, cancel_futures=True)
        try:
            self.runtime.close()
        finally:
            event.accept()


def main() -> None:
    app = QApplication([])
    app.setApplicationName("SKYNET")
    app.setOrganizationName("SKYNET Project")
    app.setStyle("Fusion")
    font = QFont("Segoe UI Variable", 10)
    app.setFont(font)
    window = ChatWindow()
    window.showMaximized()
    app.exec()


if __name__ == "__main__":
    main()
