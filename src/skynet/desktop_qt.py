from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import html
import threading
import time
from typing import Callable

from PySide6.QtCore import Qt, QTimer, Signal, QObject, QSize
from PySide6.QtGui import QAction, QColor, QFont, QKeySequence, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QStackedWidget,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .runtime import Runtime
from .voice import VoiceEngine


BG = "#0b0f14"
SURFACE = "#111821"
SURFACE_2 = "#151e28"
SURFACE_3 = "#1b2632"
BORDER = "#253445"
TEXT = "#eef5fb"
MUTED = "#8da1b4"
FAINT = "#5d7286"
ACCENT = "#4cc9f0"
ACCENT_2 = "#7ae3ff"
GREEN = "#54d6a1"
AMBER = "#f2be63"
RED = "#ff6f7d"


APP_STYLE = f"""
QWidget {{
    background: {BG}; color: {TEXT}; font-family: 'Segoe UI Variable', 'Segoe UI', sans-serif;
    font-size: 13px;
}}
QMainWindow {{ background: {BG}; }}
QFrame#sidebar {{ background: #0d131a; border-right: 1px solid {BORDER}; }}
QFrame#card {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 18px; }}
QFrame#cardSoft {{ background: {SURFACE_2}; border: 1px solid {BORDER}; border-radius: 16px; }}
QFrame#hero {{ background: #101923; border: 1px solid #29465c; border-radius: 24px; }}
QLabel#eyebrow {{ color: {ACCENT}; font-size: 11px; font-weight: 700; letter-spacing: 1px; }}
QLabel#title {{ color: {TEXT}; font-size: 28px; font-weight: 700; }}
QLabel#subtitle {{ color: {MUTED}; font-size: 13px; }}
QLabel#metric {{ color: {TEXT}; font-size: 24px; font-weight: 650; }}
QLabel#metricLabel {{ color: {MUTED}; font-size: 11px; }}
QLabel#statusGood {{ color: {GREEN}; font-size: 11px; font-weight: 700; }}
QPushButton {{
    background: transparent; border: 1px solid transparent; border-radius: 12px;
    color: {MUTED}; padding: 10px 13px; text-align: left;
}}
QPushButton:hover {{ background: {SURFACE_2}; color: {TEXT}; }}
QPushButton:checked {{ background: #142431; border: 1px solid #2b536d; color: {TEXT}; }}
QPushButton#primary {{ background: {ACCENT}; color: #061017; border: 0; font-weight: 700; padding: 11px 16px; text-align: center; }}
QPushButton#primary:hover {{ background: {ACCENT_2}; }}
QPushButton#secondary {{ background: {SURFACE_2}; color: {TEXT}; border: 1px solid {BORDER}; padding: 10px 14px; text-align: center; }}
QPushButton#danger {{ background: #24151a; color: {RED}; border: 1px solid #5b2730; padding: 10px 14px; text-align: center; }}
QPushButton#capability {{
    background: {SURFACE_2}; color: {TEXT}; border: 1px solid {BORDER}; border-radius: 16px;
    padding: 14px; text-align: left; font-size: 14px; font-weight: 650;
}}
QPushButton#capability:hover {{ background: #182634; border: 1px solid #35607b; }}
QTextEdit, QTextBrowser, QLineEdit, QListWidget {{
    background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 14px;
    color: {TEXT}; selection-background-color: #24536c; padding: 10px;
}}
QTextEdit:focus, QLineEdit:focus {{ border: 1px solid #3a789a; }}
QScrollArea {{ border: 0; background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 4px; }}
QScrollBar::handle:vertical {{ background: #2d4154; min-height: 32px; border-radius: 5px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
"""


class Bridge(QObject):
    reply = Signal(str)
    error = Signal(str)
    busy = Signal(bool)
    confirm = Signal(str, object)
    trace = Signal(str, str)
    voice_state = Signal(str)


class CoreOrb(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.phase = 0.0
        self.mode = "idle"
        self.setMinimumSize(230, 230)
        self.setMaximumSize(300, 300)
        timer = QTimer(self)
        timer.timeout.connect(self._tick)
        timer.start(45)
        self._timer = timer

    def set_mode(self, mode: str) -> None:
        self.mode = mode
        self.update()

    def _tick(self) -> None:
        self.phase = (self.phase + 1.3) % 360.0
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        c_x, c_y = w / 2, h / 2
        size = min(w, h)
        accent = QColor(RED if self.mode == "stopped" else ACCENT)
        soft = QColor(44, 91, 119, 180)

        for ratio, width, alpha in ((0.44, 1, 120), (0.35, 2, 180), (0.26, 1, 160)):
            r = size * ratio
            color = QColor(accent)
            color.setAlpha(alpha)
            p.setPen(QPen(color, width))
            p.drawEllipse(int(c_x-r), int(c_y-r), int(2*r), int(2*r))

        p.setPen(QPen(soft, 5))
        r = size * 0.39
        start = int((90 - self.phase) * 16)
        p.drawArc(int(c_x-r), int(c_y-r), int(2*r), int(2*r), start, int(88 * 16))
        p.setPen(QPen(accent, 2))
        r2 = size * 0.31
        p.drawArc(int(c_x-r2), int(c_y-r2), int(2*r2), int(2*r2), int((self.phase+30)*16), int(130*16))

        p.setBrush(QColor(ACCENT if self.mode != "stopped" else RED))
        p.setPen(Qt.NoPen)
        for i in range(6):
            import math
            angle = (self.phase * (1 if i % 2 == 0 else -0.55) + i * 60) * 3.14159265 / 180
            radius = size * (0.40 if i % 2 == 0 else 0.33)
            x = c_x + math.cos(angle) * radius
            y = c_y + math.sin(angle) * radius
            p.drawEllipse(int(x-3), int(y-3), 6, 6)

        p.setPen(QColor(TEXT))
        font = QFont("Segoe UI Variable", max(14, int(size * 0.075)), QFont.DemiBold)
        p.setFont(font)
        p.drawText(self.rect(), Qt.AlignCenter, "SKYNET")
        p.setPen(QColor(GREEN if self.mode != "stopped" else RED))
        font.setPointSize(max(8, int(size * 0.034)))
        p.setFont(font)
        p.drawText(0, int(c_y + size*0.11), w, 30, Qt.AlignHCenter, "● ONLINE" if self.mode != "stopped" else "● SAFE MODE")


class Card(QFrame):
    def __init__(self, title: str | None = None, parent=None, *, soft: bool = False) -> None:
        super().__init__(parent)
        self.setObjectName("cardSoft" if soft else "card")
        self.box = QVBoxLayout(self)
        self.box.setContentsMargins(18, 16, 18, 16)
        self.box.setSpacing(10)
        if title:
            label = QLabel(title.upper())
            label.setObjectName("eyebrow")
            self.box.addWidget(label)


class DataPage(QWidget):
    def __init__(self, title: str, subtitle: str, parent=None) -> None:
        super().__init__(parent)
        self.title_text = title
        self.subtitle_text = subtitle
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 26)
        layout.setSpacing(18)
        title_label = QLabel(title)
        title_label.setObjectName("title")
        layout.addWidget(title_label)
        sub = QLabel(subtitle)
        sub.setWordWrap(True)
        sub.setObjectName("subtitle")
        layout.addWidget(sub)
        self.card = Card()
        layout.addWidget(self.card, 1)
        self.body = QTextBrowser()
        self.body.setOpenExternalLinks(False)
        self.body.setFrameShape(QFrame.NoFrame)
        self.card.box.addWidget(self.body, 1)

    def set_html(self, content: str) -> None:
        self.body.setHtml(content)


class CommandPalette(QDialog):
    def __init__(self, actions: list[tuple[str, str, Callable[[], None]]], parent=None) -> None:
        super().__init__(parent)
        self.actions = actions
        self.setWindowTitle("Command Palette")
        self.setModal(True)
        self.resize(620, 440)
        self.setStyleSheet(APP_STYLE)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Type a capability, page or command…")
        self.list = QListWidget()
        layout.addWidget(self.search)
        layout.addWidget(self.list, 1)
        self.search.textChanged.connect(self._refresh)
        self.search.returnPressed.connect(self._activate)
        self.list.itemActivated.connect(lambda _item: self._activate())
        self._refresh()
        self.search.setFocus()

    def _refresh(self) -> None:
        query = self.search.text().casefold().strip()
        self.list.clear()
        for index, (label, detail, _callback) in enumerate(self.actions):
            hay = f"{label} {detail}".casefold()
            if query and query not in hay:
                continue
            item = QListWidgetItem(f"{label}\n{detail}")
            item.setData(Qt.UserRole, index)
            item.setSizeHint(QSize(0, 54))
            self.list.addItem(item)
        if self.list.count():
            self.list.setCurrentRow(0)

    def _activate(self) -> None:
        item = self.list.currentItem()
        if item is None:
            return
        index = int(item.data(Qt.UserRole))
        self.accept()
        self.actions[index][2]()


class SkynetWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("SKYNET — Sovereign AI")
        self.resize(1540, 940)
        self.setMinimumSize(1120, 720)
        self.runtime = Runtime.create(Path.cwd(), session_id="desktop")
        self.bridge = Bridge()
        self.pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix="skynet-ui")
        self.voice = VoiceEngine(self.runtime.config.data_dir, on_state=lambda state: self.bridge.voice_state.emit(state))
        self.voice_enabled = True
        self.current_page = "home"
        self.nav: dict[str, QPushButton] = {}
        self.pages: dict[str, QWidget] = {}
        self.trace_lines: list[str] = []
        self.started_at = time.perf_counter()

        self.setStyleSheet(APP_STYLE)
        self._connect_bridge()
        self._build()
        self._install_shortcuts()
        self.navigate("home")
        self._trace("Core", "Sovereign runtime ready")
        self._trace("Governance", "Mandate · Policy · Permission · Receipt active")
        self._trace("Model", self.runtime.router.last_route.model)

        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._refresh_dynamic)
        self.refresh_timer.start(2500)
        self._refresh_dynamic()

    # --------------------------------------------------------------- structure
    def _build(self) -> None:
        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self._build_sidebar())

        shell = QWidget()
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)
        shell_layout.addWidget(self._build_topbar())
        self.stack = QStackedWidget()
        shell_layout.addWidget(self.stack, 1)
        root_layout.addWidget(shell, 1)
        self.setCentralWidget(root)

        self.pages["home"] = self._build_home()
        self.pages["chat"] = self._build_chat()
        for key, title, subtitle in (
            ("memory", "Memory", "Persistent context, session continuity and what SKYNET has learned."),
            ("skills", "Skills", "Reusable procedures that reduce repeated work and turn successful workflows into capabilities."),
            ("automations", "Automations", "Long-running routines, scheduled actions and session-bound autonomous work."),
            ("browser", "Browser", "Local browser harness, research, evidence extraction and governed interaction."),
            ("integrations", "Integrations", "MCP tools, built-in adapters and external capability bridges."),
            ("devices", "Devices", "Windows control, hardware resources, UI Automation, screenshots and vision fallback."),
            ("sessions", "Sessions", "Search, fork and resume durable conversations and projects."),
            ("system", "System & Security", "Identity, policy, permissions, receipts, risk and the global kill switch."),
        ):
            self.pages[key] = DataPage(title, subtitle)
        for page in self.pages.values():
            self.stack.addWidget(page)

    def _build_sidebar(self) -> QWidget:
        side = QFrame()
        side.setObjectName("sidebar")
        side.setFixedWidth(228)
        layout = QVBoxLayout(side)
        layout.setContentsMargins(16, 22, 16, 18)
        layout.setSpacing(5)

        brand = QLabel("◉  SKYNET")
        brand.setStyleSheet(f"font-size: 20px; font-weight: 750; color: {TEXT}; padding: 4px 8px;")
        layout.addWidget(brand)
        sub = QLabel("SOVEREIGN AI")
        sub.setObjectName("eyebrow")
        sub.setStyleSheet(f"color: {ACCENT}; padding: 0 9px 18px 9px;")
        layout.addWidget(sub)

        items = (
            ("home", "⌂", "Overview"),
            ("chat", "◫", "Mission Control"),
            ("memory", "◇", "Memory"),
            ("skills", "✦", "Skills"),
            ("automations", "◴", "Automations"),
            ("browser", "◎", "Research"),
            ("integrations", "⌘", "Integrations"),
            ("devices", "▱", "Devices"),
            ("sessions", "☷", "Sessions"),
            ("system", "⚙", "System"),
        )
        for key, icon, label in items:
            button = QPushButton(f"{icon}   {label}")
            button.setCheckable(True)
            button.clicked.connect(lambda _checked=False, name=key: self.navigate(name))
            layout.addWidget(button)
            self.nav[key] = button
        layout.addItem(QSpacerItem(10, 20, QSizePolicy.Minimum, QSizePolicy.Expanding))

        self.side_voice = QLabel()
        self.side_voice.setObjectName("subtitle")
        self.side_voice.setWordWrap(True)
        layout.addWidget(self.side_voice)
        local = QLabel("● LOCAL · SOVEREIGN")
        local.setObjectName("statusGood")
        layout.addWidget(local)
        return side

    def _build_topbar(self) -> QWidget:
        bar = QFrame()
        bar.setFixedHeight(70)
        bar.setStyleSheet(f"background: {BG}; border-bottom: 1px solid {BORDER};")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(28, 12, 24, 12)
        self.breadcrumb = QLabel("SKYNET / OVERVIEW")
        self.breadcrumb.setObjectName("eyebrow")
        layout.addWidget(self.breadcrumb)
        layout.addStretch(1)
        self.status_label = QLabel("● SYSTEMS NOMINAL")
        self.status_label.setObjectName("statusGood")
        layout.addWidget(self.status_label)
        model = QLabel(f"LOCAL MODEL  ·  {self.runtime.router.last_route.model}")
        model.setObjectName("subtitle")
        model.setStyleSheet(f"background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 11px; padding: 8px 12px;")
        layout.addWidget(model)
        voice = QPushButton("◉ Voice")
        voice.setObjectName("secondary")
        voice.clicked.connect(self._toggle_voice)
        layout.addWidget(voice)
        palette = QPushButton("⌘K")
        palette.setObjectName("secondary")
        palette.clicked.connect(self.open_palette)
        layout.addWidget(palette)
        return bar

    # ------------------------------------------------------------------- home
    def _build_home(self) -> QWidget:
        outer = QScrollArea()
        outer.setWidgetResizable(True)
        host = QWidget()
        root = QVBoxLayout(host)
        root.setContentsMargins(28, 26, 28, 28)
        root.setSpacing(18)

        hero = QFrame()
        hero.setObjectName("hero")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(26, 22, 26, 22)
        hero_layout.setSpacing(26)
        self.orb = CoreOrb()
        hero_layout.addWidget(self.orb)

        copy = QVBoxLayout()
        eyebrow = QLabel("SOVEREIGN COMMAND LAYER")
        eyebrow.setObjectName("eyebrow")
        copy.addWidget(eyebrow)
        title = QLabel("Ask once. Let SKYNET operate.")
        title.setObjectName("title")
        copy.addWidget(title)
        intro = QLabel(
            "SKYNET is not just a chatbot. It can reason, use governed tools, work across Windows, browse, "
            "remember context, automate routines and coordinate specialist agents — while every consequential action remains auditable."
        )
        intro.setWordWrap(True)
        intro.setObjectName("subtitle")
        intro.setMaximumWidth(760)
        copy.addWidget(intro)
        actions = QHBoxLayout()
        mission = QPushButton("Start a mission")
        mission.setObjectName("primary")
        mission.clicked.connect(lambda: self._start_prompt("Je veux te confier une mission. Commence par clarifier l’objectif, puis construis et exécute un plan vérifiable."))
        actions.addWidget(mission)
        capabilities = QPushButton("What can you do?")
        capabilities.setObjectName("secondary")
        capabilities.clicked.connect(lambda: self._start_prompt("Montre-moi concrètement ce que tu peux faire sur ce PC, avec des exemples d’actions réellement disponibles et leurs niveaux d’autorisation."))
        actions.addWidget(capabilities)
        actions.addStretch(1)
        copy.addLayout(actions)
        hero_layout.addLayout(copy, 1)
        root.addWidget(hero)

        stats = QHBoxLayout()
        self.metric_tools = self._metric_card("TOOLS", "—", "governed capabilities")
        self.metric_integrations = self._metric_card("INTEGRATIONS", "—", "active bridges")
        self.metric_sessions = self._metric_card("SESSIONS", "—", "durable contexts")
        self.metric_skills = self._metric_card("SKILLS", "—", "approved procedures")
        for card in (self.metric_tools, self.metric_integrations, self.metric_sessions, self.metric_skills):
            stats.addWidget(card)
        root.addLayout(stats)

        section = QLabel("What SKYNET can actually do")
        section.setStyleSheet(f"font-size: 18px; font-weight: 700; color: {TEXT}; padding-top: 6px;")
        root.addWidget(section)
        grid_rows = QVBoxLayout()
        capabilities_data = (
            ("▱  Operate Windows", "Inspect UI Automation, focus apps, type, click, take screenshots and use vision fallback.", "Ouvre le mode Mission Control et aide-moi à piloter Windows de façon vérifiable."),
            ("◎  Research & browse", "Navigate the web, collect evidence, compare sources and keep a trace of what was used.", "Lance une recherche web approfondie sur un sujet que je vais te donner, avec preuves et vérification."),
            ("</>  Files & code", "Read/write workspace files, inspect Git, search source code, run tests and use PowerShell under policy.", "Analyse ce projet, trouve les problèmes prioritaires et propose un plan de correction vérifiable."),
            ("◴  Automate", "Create routines, bind them to sessions, run unattended work within permission and risk limits.", "Aide-moi à créer une automatisation utile sur ce PC et explique exactement ce qu’elle fera."),
            ("◇  Remember", "Persistent memory, semantic recall, searchable sessions, forks and project continuity.", "Montre ce que tu sais retenir, retrouver et réutiliser d’une session à l’autre."),
            ("✦  Multi-agent", "Planner, researcher, analyst, coder, critic, security and verifier roles coordinated as a DAG.", "Utilise le swarm pour analyser un problème complexe et montre la valeur ajoutée des spécialistes."),
        )
        for row_start in range(0, len(capabilities_data), 3):
            row = QHBoxLayout()
            row.setSpacing(12)
            for title_text, detail, prompt in capabilities_data[row_start:row_start+3]:
                card = Card(soft=True)
                button = QPushButton(title_text)
                button.setObjectName("capability")
                button.clicked.connect(lambda _checked=False, p=prompt: self._start_prompt(p))
                card.box.addWidget(button)
                detail_label = QLabel(detail)
                detail_label.setWordWrap(True)
                detail_label.setObjectName("subtitle")
                card.box.addWidget(detail_label)
                row.addWidget(card, 1)
            grid_rows.addLayout(row)
        root.addLayout(grid_rows)

        lower = QHBoxLayout()
        lower.setSpacing(14)
        activity = Card("Live activity")
        self.home_trace = QTextBrowser()
        self.home_trace.setFrameShape(QFrame.NoFrame)
        self.home_trace.setMaximumHeight(190)
        activity.box.addWidget(self.home_trace)
        lower.addWidget(activity, 2)
        system = Card("System posture")
        self.home_system = QLabel()
        self.home_system.setWordWrap(True)
        self.home_system.setObjectName("subtitle")
        system.box.addWidget(self.home_system)
        open_system = QPushButton("Open security & system")
        open_system.setObjectName("secondary")
        open_system.clicked.connect(lambda: self.navigate("system"))
        system.box.addWidget(open_system)
        lower.addWidget(system, 1)
        root.addLayout(lower)
        root.addStretch(1)
        outer.setWidget(host)
        return outer

    def _metric_card(self, label: str, value: str, detail: str) -> Card:
        card = Card()
        label_widget = QLabel(label)
        label_widget.setObjectName("metricLabel")
        value_widget = QLabel(value)
        value_widget.setObjectName("metric")
        detail_widget = QLabel(detail)
        detail_widget.setObjectName("subtitle")
        card.box.addWidget(label_widget)
        card.box.addWidget(value_widget)
        card.box.addWidget(detail_widget)
        card.value_widget = value_widget  # type: ignore[attr-defined]
        return card

    # ------------------------------------------------------------------- chat
    def _build_chat(self) -> QWidget:
        host = QWidget()
        root = QHBoxLayout(host)
        root.setContentsMargins(28, 24, 28, 26)
        root.setSpacing(14)

        conversation = Card("Mission control")
        conv_box = conversation.box
        self.chat = QTextBrowser()
        self.chat.setFrameShape(QFrame.NoFrame)
        self.chat.setStyleSheet(f"QTextBrowser {{ background: transparent; border: 0; padding: 6px; }}")
        conv_box.addWidget(self.chat, 1)
        composer = QHBoxLayout()
        self.entry = QTextEdit()
        self.entry.setPlaceholderText("Give SKYNET an objective…  Ctrl+Enter to send")
        self.entry.setFixedHeight(86)
        composer.addWidget(self.entry, 1)
        send = QPushButton("Send  ↗")
        send.setObjectName("primary")
        send.setFixedWidth(116)
        send.clicked.connect(self.send_message)
        composer.addWidget(send)
        conv_box.addLayout(composer)
        quick = QHBoxLayout()
        for label, prompt in (
            ("Plan", "Transforme mon objectif en plan d’exécution avec critères de réussite."),
            ("Deep research", "Passe en recherche approfondie et construis une réponse vérifiée avec sources."),
            ("Use swarm", "Utilise plusieurs spécialistes pour traiter ce problème et synthétise leurs conclusions."),
            ("Inspect PC", "Fais un état des capacités Windows actuellement accessibles et propose une démonstration sans risque."),
        ):
            button = QPushButton(label)
            button.setObjectName("secondary")
            button.clicked.connect(lambda _checked=False, p=prompt: self._fill_prompt(p))
            quick.addWidget(button)
        quick.addStretch(1)
        conv_box.addLayout(quick)
        root.addWidget(conversation, 3)

        rail = QVBoxLayout()
        state = Card("Current mission")
        self.mission_state = QLabel("Idle\n\nGive SKYNET an objective. It will plan, act through governed tools and verify outcomes.")
        self.mission_state.setWordWrap(True)
        self.mission_state.setObjectName("subtitle")
        state.box.addWidget(self.mission_state)
        rail.addWidget(state)
        trace_card = Card("Execution trace")
        self.chat_trace = QTextBrowser()
        self.chat_trace.setFrameShape(QFrame.NoFrame)
        trace_card.box.addWidget(self.chat_trace, 1)
        rail.addWidget(trace_card, 1)
        root.addLayout(rail, 1)
        self._load_history()
        return host

    # --------------------------------------------------------------- commands
    def _install_shortcuts(self) -> None:
        action = QAction(self)
        action.setShortcut(QKeySequence("Ctrl+K"))
        action.triggered.connect(self.open_palette)
        self.addAction(action)
        send = QAction(self)
        send.setShortcut(QKeySequence("Ctrl+Return"))
        send.triggered.connect(self.send_message)
        self.addAction(send)

    def open_palette(self) -> None:
        actions: list[tuple[str, str, Callable[[], None]]] = []
        for key, label in (
            ("home", "Overview"), ("chat", "Mission Control"), ("memory", "Memory"),
            ("skills", "Skills"), ("automations", "Automations"), ("browser", "Research"),
            ("integrations", "Integrations"), ("devices", "Devices"), ("sessions", "Sessions"), ("system", "System"),
        ):
            actions.append((f"Open {label}", "Navigate inside SKYNET", lambda page=key: self.navigate(page)))
        actions.extend([
            ("Operate Windows", "Start a governed Windows-control mission", lambda: self._start_prompt("Aide-moi à accomplir une tâche sur Windows avec UI Automation, vérification et permissions.")),
            ("Deep Research", "Use browser, evidence and synthesis", lambda: self._start_prompt("Je veux lancer une recherche approfondie. Demande-moi le sujet puis exécute une démarche sourcée et vérifiable.")),
            ("Run multi-agent analysis", "Planner + specialists + verifier", lambda: self._start_prompt("Passe en analyse multi-agent sur le problème que je vais te donner.")),
            ("Create automation", "Build a session-bound routine", lambda: self._start_prompt("Aide-moi à créer une automatisation locale utile, avec limites, critères de réussite et possibilité d’arrêt.")),
            ("Global kill switch", "Immediately enter safe mode", self._kill_switch),
        ])
        CommandPalette(actions, self).exec()

    def navigate(self, page: str) -> None:
        if page not in self.pages:
            return
        self.current_page = page
        self.stack.setCurrentWidget(self.pages[page])
        for key, button in self.nav.items():
            button.setChecked(key == page)
        self.breadcrumb.setText(f"SKYNET / {page.upper()}")
        if isinstance(self.pages[page], DataPage):
            self._refresh_data_page(page, self.pages[page])
        if page == "chat":
            self._load_history()

    def _start_prompt(self, prompt: str) -> None:
        self.navigate("chat")
        self._fill_prompt(prompt)
        self.entry.setFocus()

    def _fill_prompt(self, prompt: str) -> None:
        self.entry.setPlainText(prompt)
        cursor = self.entry.textCursor()
        cursor.movePosition(cursor.End)
        self.entry.setTextCursor(cursor)

    def send_message(self) -> None:
        if self.current_page != "chat":
            self.navigate("chat")
        text = self.entry.toPlainText().strip()
        if not text:
            return
        self.entry.clear()
        self._append_message("YOU", text)
        self.status_label.setText("● MISSION ACTIVE")
        self.orb.set_mode("thinking")
        self.mission_state.setText("Working…\n\nSKYNET is reasoning, selecting tools and preserving the execution boundary.")
        self._trace("Mission", "User objective accepted")
        self.bridge.busy.emit(True)

        def work() -> None:
            try:
                reply = self.runtime.agent.ask(text, self._confirm_from_worker)
                self.bridge.reply.emit(reply)
            except Exception as exc:
                self.bridge.error.emit(f"{type(exc).__name__}: {exc}")
            finally:
                self.bridge.busy.emit(False)

        self.pool.submit(work)

    def _confirm_from_worker(self, message: str) -> bool:
        packet = {"event": threading.Event(), "result": False}
        self.bridge.confirm.emit(message, packet)
        packet["event"].wait()
        return bool(packet["result"])

    # --------------------------------------------------------------- messages
    def _append_message(self, who: str, text: str) -> None:
        color = ACCENT if who == "SKYNET" else TEXT
        safe = html.escape(text).replace("\n", "<br>")
        self.chat.append(
            f"<div style='margin:12px 0 3px 0;color:{color};font-size:11px;font-weight:700'>{html.escape(who)}</div>"
            f"<div style='margin:0 0 14px 0;color:{TEXT};line-height:1.55'>{safe}</div>"
        )

    def _load_history(self) -> None:
        if not hasattr(self, "chat"):
            return
        self.chat.clear()
        messages = self.runtime.memory.recent_messages(self.runtime.agent.session_id, limit=80)
        if not messages:
            self._append_message("SKYNET", "Systems nominal. Give me an objective, not just a question — I can plan and act through my governed tools.")
            return
        for message in messages:
            role = str(message.get("role", "")).lower()
            who = "YOU" if role == "user" else "SKYNET" if role == "assistant" else role.upper()
            self._append_message(who, str(message.get("content", "")))

    # --------------------------------------------------------------- data views
    def _refresh_data_page(self, key: str, page: DataPage) -> None:
        try:
            if key == "memory":
                sessions = self.runtime.sessions.list(limit=20)
                memories = self.runtime.memory.list_memories(limit=20)
                body = self._cards_html("Persistent memory", [
                    ("Durable memories", str(len(memories)), "recent entries loaded"),
                    ("Sessions", str(len(sessions)), "searchable & forkable"),
                    ("Semantic memory", "ACTIVE", "related context is retrieved automatically"),
                ]) + "<h3>Recent memories</h3>" + self._items_html(memories)
            elif key == "skills":
                skills = self.runtime.skills.list_skills()
                usage = self.runtime.skills.usage()[:20]
                body = self._cards_html("Skill system", [
                    ("Approved", str(len(skills)), "available to the agent"),
                    ("Progressive loading", "ACTIVE", "only relevant skills enter context"),
                    ("Candidate pipeline", "GOVERNED", "validate before promotion"),
                ]) + "<h3>Approved skills</h3>" + self._items_html(skills[:30])
                if usage:
                    body += "<h3>Usage</h3>" + self._items_html([str(x) for x in usage])
            elif key == "automations":
                routines = self.runtime.routines.list()
                body = self._cards_html("Autonomy", [
                    ("Routines", str(len(routines)), "interval / once / run budgets"),
                    ("Session-bound", "YES", "automation keeps the right context"),
                    ("Unattended safety", "ACTIVE", "sensitive actions cannot self-approve"),
                ]) + "<h3>Configured routines</h3>" + self._items_html([self.runtime.routines.render(x) for x in routines])
            elif key == "browser":
                state = self.runtime.browser.state()
                body = self._cards_html("Research stack", [
                    ("Browser mode", str(state.mode), "local-first harness"),
                    ("HTTP read", "ACTIVE", "extract text and links"),
                    ("Interactive browser", "OPTIONAL", "Playwright local when installed"),
                ]) + "<h3>What this enables</h3>" + self._items_html([
                    "Evidence collection and source comparison",
                    "Governed navigation, click, typing and screenshot",
                    "Research sessions with audit and verification",
                ])
            elif key == "integrations":
                integrations = self.runtime.integrations.list(enabled_only=True)
                body = self._cards_html("Capability fabric", [
                    ("Active integrations", str(len(integrations)), "built-ins + MCP"),
                    ("Exposed tools", str(len(self.runtime.tools.schemas())), "all governed"),
                    ("Dynamic MCP", "ACTIVE", "configured server tools become native SKYNET tools"),
                ]) + "<h3>Active integrations</h3>" + self._items_html([str(getattr(x, "name", x)) for x in integrations])
            elif key == "devices":
                snap = self.runtime.profiler.snapshot()
                body = self._cards_html("Local machine", [
                    ("CPU", f"{snap.cpu_count} cores", "local execution"),
                    ("RAM", self._ram_text(snap), "available / total"),
                    ("GPU", snap.gpu_name or "Not detected", self._gpu_text(snap)),
                ]) + "<h3>Windows control</h3>" + self._items_html([
                    "Accessibility / UI Automation first",
                    "Screenshot and vision fallback",
                    "PowerShell through permission + policy boundary",
                ])
            elif key == "sessions":
                sessions = self.runtime.sessions.list(limit=100)
                body = self._cards_html("Continuity", [
                    ("Sessions", str(len(sessions)), "durable conversation state"),
                    ("Search", "ACTIVE", "find earlier context"),
                    ("Fork", "ACTIVE", "branch investigations safely"),
                ]) + "<h3>Recent sessions</h3>" + self._items_html([f"{x.title} · {x.session_id}" for x in sessions[:40]])
            elif key == "system":
                body = self._cards_html("Governance", [
                    ("Kill switch", "ENGAGED" if self.runtime.control.engaged() else "ARMED", "global control"),
                    ("Receipts", "SIGNED", "actions leave verifiable evidence"),
                    ("Permissions", "ENFORCED", "unknown tools are blocked"),
                ]) + "<h3>Execution boundary</h3>" + self._items_html([
                    "Mandate → Policy → Permission → Execution → Receipt",
                    "Risk budget and non-reversible action classification",
                    "Sandboxed candidate evolution, canary promotion and rollback",
                    "Synthetic reality accelerator + regression replay",
                ])
            else:
                body = ""
            page.set_html(body)
        except Exception as exc:
            page.set_html(f"<p style='color:{RED}'>Unable to refresh page: {html.escape(str(exc))}</p>")

    @staticmethod
    def _items_html(items) -> str:
        values = list(items)
        if not values:
            return f"<p style='color:{MUTED}'>Nothing recorded yet.</p>"
        return "<ul style='line-height:1.7'>" + "".join(f"<li>{html.escape(str(x))}</li>" for x in values) + "</ul>"

    @staticmethod
    def _cards_html(title: str, cards: list[tuple[str, str, str]]) -> str:
        cells = "".join(
            f"<td style='padding:14px;border:1px solid {BORDER};border-radius:12px'>"
            f"<div style='color:{MUTED};font-size:10px'>{html.escape(a)}</div>"
            f"<div style='color:{TEXT};font-size:22px;font-weight:700;margin-top:4px'>{html.escape(b)}</div>"
            f"<div style='color:{FAINT};font-size:10px;margin-top:4px'>{html.escape(c)}</div></td>"
            for a, b, c in cards
        )
        return f"<h2>{html.escape(title)}</h2><table width='100%' cellspacing='8'><tr>{cells}</tr></table>"

    @staticmethod
    def _ram_text(snap) -> str:
        if snap.ram_total_mb is None or snap.ram_available_mb is None:
            return "Unknown"
        return f"{snap.ram_available_mb/1024:.1f} / {snap.ram_total_mb/1024:.1f} GB"

    @staticmethod
    def _gpu_text(snap) -> str:
        if snap.gpu_memory_total_mb is None:
            return "VRAM telemetry unavailable"
        used = snap.gpu_memory_used_mb or 0
        return f"{used/1024:.1f} / {snap.gpu_memory_total_mb/1024:.1f} GB VRAM"

    # --------------------------------------------------------------- dynamic
    def _refresh_dynamic(self) -> None:
        try:
            tool_count = len(self.runtime.tools.schemas())
            integration_count = len(self.runtime.integrations.list(enabled_only=True))
            session_count = len(self.runtime.sessions.list(limit=500))
            skill_count = len(self.runtime.skills.list_skills())
            self.metric_tools.value_widget.setText(str(tool_count))  # type: ignore[attr-defined]
            self.metric_integrations.value_widget.setText(str(integration_count))  # type: ignore[attr-defined]
            self.metric_sessions.value_widget.setText(str(session_count))  # type: ignore[attr-defined]
            self.metric_skills.value_widget.setText(str(skill_count))  # type: ignore[attr-defined]
            voice = self.voice.status()
            self.side_voice.setText(f"VOICE\n{voice.provider}\n{voice.detail}")
            snap = self.runtime.profiler.snapshot()
            ram = self._ram_text(snap)
            gpu = snap.gpu_name or "GPU not detected"
            posture = (
                f"<b>Model</b> · {html.escape(self.runtime.router.last_route.model)}<br>"
                f"<b>RAM</b> · {html.escape(ram)}<br>"
                f"<b>GPU</b> · {html.escape(gpu)}<br>"
                f"<b>Browser</b> · {html.escape(str(self.runtime.browser.state().mode))}<br>"
                f"<b>Kill switch</b> · {'ENGAGED' if self.runtime.control.engaged() else 'ready'}"
            )
            self.home_system.setText(posture)
        except Exception:
            pass
        self._refresh_trace_widgets()

    def _trace(self, source: str, message: str) -> None:
        stamp = time.strftime("%H:%M:%S")
        self.trace_lines.append(f"{stamp}  {source:<12} {message}")
        self.trace_lines = self.trace_lines[-80:]
        self._refresh_trace_widgets()

    def _refresh_trace_widgets(self) -> None:
        text = "\n".join(self.trace_lines[-14:])
        if hasattr(self, "home_trace"):
            self.home_trace.setPlainText(text)
        if hasattr(self, "chat_trace"):
            self.chat_trace.setPlainText("\n".join(self.trace_lines[-24:]))

    # --------------------------------------------------------------- voice/safe
    def _toggle_voice(self) -> None:
        self.voice_enabled = not self.voice_enabled
        if not self.voice_enabled:
            self.voice.stop()
            self._trace("Voice", "Speech disabled")
        else:
            self.voice.refresh()
            self._trace("Voice", f"Speech enabled · {self.voice.status().provider}")

    def _kill_switch(self) -> None:
        answer = QMessageBox.warning(
            self,
            "Global kill switch",
            "Engage SKYNET safe mode and stop autonomous execution?",
            QMessageBox.Yes | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )
        if answer != QMessageBox.Yes:
            return
        try:
            self.runtime.control.engage("manual UI kill switch")
            self.orb.set_mode("stopped")
            self.status_label.setText("● SAFE MODE")
            self.status_label.setStyleSheet(f"color:{RED};font-weight:700")
            self._trace("Security", "Global kill switch engaged")
        except Exception as exc:
            QMessageBox.critical(self, "Kill switch", str(exc))

    # --------------------------------------------------------------- bridge
    def _connect_bridge(self) -> None:
        self.bridge.reply.connect(self._on_reply)
        self.bridge.error.connect(self._on_error)
        self.bridge.busy.connect(self._on_busy)
        self.bridge.confirm.connect(self._on_confirm)
        self.bridge.trace.connect(self._trace)
        self.bridge.voice_state.connect(self._on_voice_state)

    def _on_reply(self, reply: str) -> None:
        self._append_message("SKYNET", reply)
        self.mission_state.setText("Completed\n\nThe latest response was produced through the governed runtime. Use the trace to inspect the execution path.")
        self._trace("Output", "Mission response completed")
        if self.voice_enabled:
            self.voice.speak(reply)

    def _on_error(self, message: str) -> None:
        self._append_message("SYSTEM", message)
        self.mission_state.setText(f"Blocked / failed\n\n{message}")
        self._trace("Error", message[:120])

    def _on_busy(self, busy: bool) -> None:
        if busy:
            self.status_label.setText("● MISSION ACTIVE")
            self.orb.set_mode("thinking")
        else:
            self.status_label.setText("● SYSTEMS NOMINAL")
            self.orb.set_mode("idle" if not self.runtime.control.engaged() else "stopped")

    def _on_confirm(self, message: str, packet: object) -> None:
        data = packet
        answer = QMessageBox.question(
            self,
            "SKYNET permission request",
            message,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        data["result"] = answer == QMessageBox.Yes  # type: ignore[index]
        data["event"].set()  # type: ignore[index]
        self._trace("Permission", "Approved" if data["result"] else "Denied")  # type: ignore[index]

    def _on_voice_state(self, state: str) -> None:
        if state == "speaking":
            self._trace("Voice", f"Speaking · {self.voice.status().provider}")
        elif state == "error":
            self._trace("Voice", "Speech provider failed")

    # --------------------------------------------------------------- lifecycle
    def closeEvent(self, event) -> None:
        self.voice.stop()
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
    window = SkynetWindow()
    window.showMaximized()
    app.exec()


if __name__ == "__main__":
    main()
