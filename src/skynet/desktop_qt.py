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
BORDER = "#253445"
TEXT = "#eef5fb"
MUTED = "#8da1b4"
FAINT = "#5d7286"
ACCENT = "#4cc9f0"
ACCENT_2 = "#7ae3ff"
GREEN = "#54d6a1"
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
QLabel#title {{ color: {TEXT}; font-size: 29px; font-weight: 700; }}
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
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(45)

    def set_mode(self, mode: str) -> None:
        self.mode = mode
        self.update()

    def _tick(self) -> None:
        self.phase = (self.phase + 1.3) % 360.0
        self.update()

    def paintEvent(self, _event) -> None:
        import math

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        size = min(w, h)
        accent = QColor(RED if self.mode == "stopped" else ACCENT)
        soft = QColor(44, 91, 119, 180)

        for ratio, width, alpha in ((0.44, 1, 120), (0.35, 2, 180), (0.26, 1, 160)):
            r = size * ratio
            color = QColor(accent)
            color.setAlpha(alpha)
            p.setPen(QPen(color, width))
            p.drawEllipse(int(cx-r), int(cy-r), int(2*r), int(2*r))

        p.setPen(QPen(soft, 5))
        r = size * 0.39
        p.drawArc(int(cx-r), int(cy-r), int(2*r), int(2*r), int((90-self.phase)*16), int(88*16))
        p.setPen(QPen(accent, 2))
        r2 = size * 0.31
        p.drawArc(int(cx-r2), int(cy-r2), int(2*r2), int(2*r2), int((self.phase+30)*16), int(130*16))

        p.setBrush(accent)
        p.setPen(Qt.NoPen)
        for i in range(6):
            angle = (self.phase * (1 if i % 2 == 0 else -0.55) + i * 60) * math.pi / 180
            radius = size * (0.40 if i % 2 == 0 else 0.33)
            x = cx + math.cos(angle) * radius
            y = cy + math.sin(angle) * radius
            p.drawEllipse(int(x-3), int(y-3), 6, 6)

        p.setPen(QColor(TEXT))
        font = QFont("Segoe UI Variable", max(14, int(size * 0.075)), QFont.DemiBold)
        p.setFont(font)
        p.drawText(self.rect(), Qt.AlignCenter, "SKYNET")
        p.setPen(QColor(GREEN if self.mode != "stopped" else RED))
        font.setPointSize(max(8, int(size * 0.034)))
        p.setFont(font)
        label = "● EN LIGNE" if self.mode != "stopped" else "● MODE SÛR"
        p.drawText(0, int(cy + size*0.11), w, 30, Qt.AlignHCenter, label)


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
        self.setWindowTitle("Palette de commandes")
        self.setModal(True)
        self.resize(620, 440)
        self.setStyleSheet(APP_STYLE)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Rechercher une capacité, une page ou une commande…")
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
            if query and query not in f"{label} {detail}".casefold():
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
        self.setWindowTitle("SKYNET — Intelligence souveraine")
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

        self.setStyleSheet(APP_STYLE)
        self._connect_bridge()
        self._build()
        self._install_shortcuts()
        self.navigate("home")
        self._trace("Noyau", "Runtime souverain chargé")
        self._trace("Mémoire", "Contexte persistant connecté")
        self._trace("Sécurité", "Mandat · politique · permission · reçu actifs")
        self._trace("Modèle", self.runtime.router.last_route.model)

        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._refresh_dynamic)
        self.refresh_timer.start(2500)
        self._refresh_dynamic()
        QTimer.singleShot(900, self._announce_startup)

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
            ("memory", "Mémoire", "Contexte persistant, continuité des sessions et connaissances retenues par SKYNET."),
            ("skills", "Compétences", "Procédures réutilisables qui transforment les réussites répétées en capacités fiables."),
            ("automations", "Automatisations", "Routines, actions planifiées et travail autonome lié au bon contexte."),
            ("browser", "Recherche", "Navigation locale, collecte de preuves, extraction et interaction gouvernée."),
            ("integrations", "Intégrations", "Outils MCP, adaptateurs internes et ponts de capacités externes."),
            ("devices", "Appareils", "Contrôle Windows, ressources matérielles, UI Automation, captures et vision."),
            ("sessions", "Sessions", "Rechercher, reprendre et bifurquer des conversations et projets durables."),
            ("system", "Système & sécurité", "Identité, politiques, permissions, reçus, risque et arrêt global."),
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
        sub = QLabel("IA SOUVERAINE")
        sub.setObjectName("eyebrow")
        sub.setStyleSheet(f"color: {ACCENT}; padding: 0 9px 18px 9px;")
        layout.addWidget(sub)

        items = (
            ("home", "⌂", "Vue d’ensemble"),
            ("chat", "◫", "Centre de mission"),
            ("memory", "◇", "Mémoire"),
            ("skills", "✦", "Compétences"),
            ("automations", "◴", "Automatisations"),
            ("browser", "◎", "Recherche"),
            ("integrations", "⌘", "Intégrations"),
            ("devices", "▱", "Appareils"),
            ("sessions", "☷", "Sessions"),
            ("system", "⚙", "Système"),
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
        local = QLabel("● LOCAL · SOUVERAIN")
        local.setObjectName("statusGood")
        layout.addWidget(local)
        return side

    def _build_topbar(self) -> QWidget:
        bar = QFrame()
        bar.setFixedHeight(70)
        bar.setStyleSheet(f"background: {BG}; border-bottom: 1px solid {BORDER};")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(28, 12, 24, 12)
        self.breadcrumb = QLabel("SKYNET / VUE D’ENSEMBLE")
        self.breadcrumb.setObjectName("eyebrow")
        layout.addWidget(self.breadcrumb)
        layout.addStretch(1)
        self.status_label = QLabel("● SYSTÈMES OPÉRATIONNELS")
        self.status_label.setObjectName("statusGood")
        layout.addWidget(self.status_label)
        model = QLabel(f"MODÈLE LOCAL · {self.runtime.router.last_route.model}")
        model.setObjectName("subtitle")
        model.setStyleSheet(f"background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 11px; padding: 8px 12px;")
        layout.addWidget(model)
        voice = QPushButton("◉ Voix")
        voice.setObjectName("secondary")
        voice.clicked.connect(self._toggle_voice)
        layout.addWidget(voice)
        palette = QPushButton("⌘K")
        palette.setObjectName("secondary")
        palette.clicked.connect(self.open_palette)
        layout.addWidget(palette)
        return bar

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
        eyebrow = QLabel("COUCHE DE COMMANDE SOUVERAINE")
        eyebrow.setObjectName("eyebrow")
        copy.addWidget(eyebrow)
        title = QLabel("Donnez l’objectif. SKYNET s’occupe du reste.")
        title.setObjectName("title")
        copy.addWidget(title)
        intro = QLabel(
            "SKYNET n’est pas un simple chatbot. Il peut raisonner, utiliser des outils gouvernés, agir sur Windows, "
            "naviguer, mémoriser, automatiser et coordonner plusieurs spécialistes tout en laissant une trace vérifiable."
        )
        intro.setWordWrap(True)
        intro.setObjectName("subtitle")
        intro.setMaximumWidth(760)
        copy.addWidget(intro)
        actions = QHBoxLayout()
        mission = QPushButton("Démarrer une mission")
        mission.setObjectName("primary")
        mission.clicked.connect(lambda: self._start_prompt("Je veux te confier une mission. Clarifie l’objectif, construis un plan, exécute-le avec les outils disponibles et vérifie le résultat."))
        actions.addWidget(mission)
        capabilities = QPushButton("Que peux-tu faire ?")
        capabilities.setObjectName("secondary")
        capabilities.clicked.connect(lambda: self._start_prompt("Montre-moi concrètement ce que tu peux faire sur ce PC, avec des exemples d’actions réellement disponibles et leurs niveaux d’autorisation."))
        actions.addWidget(capabilities)
        actions.addStretch(1)
        copy.addLayout(actions)
        hero_layout.addLayout(copy, 1)
        root.addWidget(hero)

        stats = QHBoxLayout()
        self.metric_tools = self._metric_card("OUTILS", "—", "capacités gouvernées")
        self.metric_integrations = self._metric_card("INTÉGRATIONS", "—", "ponts actifs")
        self.metric_sessions = self._metric_card("SESSIONS", "—", "contextes durables")
        self.metric_skills = self._metric_card("COMPÉTENCES", "—", "procédures approuvées")
        for card in (self.metric_tools, self.metric_integrations, self.metric_sessions, self.metric_skills):
            stats.addWidget(card)
        root.addLayout(stats)

        section = QLabel("Ce que SKYNET peut réellement faire")
        section.setStyleSheet(f"font-size: 18px; font-weight: 700; color: {TEXT}; padding-top: 6px;")
        root.addWidget(section)
        capabilities_data = (
            ("▱  Piloter Windows", "Inspecter l’interface, cibler une application, saisir, cliquer, capturer l’écran et utiliser la vision en secours.", "Aide-moi à piloter Windows de façon vérifiable et sans risque inutile."),
            ("◎  Rechercher sur le web", "Naviguer, collecter des preuves, comparer des sources et conserver la trace de ce qui a été utilisé.", "Lance une recherche approfondie sur un sujet que je vais te donner, avec preuves et vérification."),
            ("</>  Fichiers & code", "Lire et écrire dans l’espace de travail, inspecter Git, rechercher dans le code, lancer des tests et utiliser PowerShell sous contrôle.", "Analyse ce projet, trouve les problèmes prioritaires et propose un plan de correction vérifiable."),
            ("◴  Automatiser", "Créer des routines, les rattacher à une session et travailler de manière autonome dans les limites de risque définies.", "Aide-moi à créer une automatisation utile sur ce PC et explique exactement ce qu’elle fera."),
            ("◇  Se souvenir", "Mémoire persistante, rappel sémantique, recherche de sessions, bifurcations et continuité des projets.", "Montre ce que tu sais retenir, retrouver et réutiliser d’une session à l’autre."),
            ("✦  Mobiliser plusieurs agents", "Planificateur, chercheur, analyste, codeur, critique, sécurité et vérificateur coordonnés.", "Utilise le swarm pour analyser un problème complexe et montre la valeur ajoutée des spécialistes."),
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
            root.addLayout(row)

        lower = QHBoxLayout()
        lower.setSpacing(14)
        activity = Card("Activité en direct")
        self.home_trace = QTextBrowser()
        self.home_trace.setFrameShape(QFrame.NoFrame)
        self.home_trace.setMaximumHeight(190)
        activity.box.addWidget(self.home_trace)
        lower.addWidget(activity, 2)
        system = Card("État du système")
        self.home_system = QLabel()
        self.home_system.setWordWrap(True)
        self.home_system.setObjectName("subtitle")
        system.box.addWidget(self.home_system)
        open_system = QPushButton("Ouvrir sécurité & système")
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

    def _build_chat(self) -> QWidget:
        host = QWidget()
        root = QHBoxLayout(host)
        root.setContentsMargins(28, 24, 28, 26)
        root.setSpacing(14)

        conversation = Card("Centre de mission")
        self.chat = QTextBrowser()
        self.chat.setFrameShape(QFrame.NoFrame)
        self.chat.setStyleSheet("QTextBrowser { background: transparent; border: 0; padding: 6px; }")
        conversation.box.addWidget(self.chat, 1)
        composer = QHBoxLayout()
        self.entry = QTextEdit()
        self.entry.setPlaceholderText("Donnez un objectif à SKYNET…  Ctrl+Entrée pour envoyer")
        self.entry.setFixedHeight(86)
        composer.addWidget(self.entry, 1)
        send = QPushButton("Envoyer  ↗")
        send.setObjectName("primary")
        send.setFixedWidth(116)
        send.clicked.connect(self.send_message)
        composer.addWidget(send)
        conversation.box.addLayout(composer)
        quick = QHBoxLayout()
        for label, prompt in (
            ("Planifier", "Transforme mon objectif en plan d’exécution avec critères de réussite."),
            ("Recherche approfondie", "Passe en recherche approfondie et construis une réponse vérifiée avec sources."),
            ("Multi-agent", "Utilise plusieurs spécialistes pour traiter ce problème et synthétise leurs conclusions."),
            ("Inspecter le PC", "Fais un état des capacités Windows accessibles et propose une démonstration sans risque."),
        ):
            button = QPushButton(label)
            button.setObjectName("secondary")
            button.clicked.connect(lambda _checked=False, p=prompt: self._fill_prompt(p))
            quick.addWidget(button)
        quick.addStretch(1)
        conversation.box.addLayout(quick)
        root.addWidget(conversation, 3)

        rail = QVBoxLayout()
        state = Card("Mission actuelle")
        self.mission_state = QLabel("En attente\n\nDonnez un objectif. SKYNET peut planifier, agir avec ses outils gouvernés et vérifier le résultat.")
        self.mission_state.setWordWrap(True)
        self.mission_state.setObjectName("subtitle")
        state.box.addWidget(self.mission_state)
        rail.addWidget(state)
        trace_card = Card("Trace d’exécution")
        self.chat_trace = QTextBrowser()
        self.chat_trace.setFrameShape(QFrame.NoFrame)
        trace_card.box.addWidget(self.chat_trace, 1)
        rail.addWidget(trace_card, 1)
        root.addLayout(rail, 1)
        self._load_history()
        return host

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
            ("home", "Vue d’ensemble"), ("chat", "Centre de mission"), ("memory", "Mémoire"),
            ("skills", "Compétences"), ("automations", "Automatisations"), ("browser", "Recherche"),
            ("integrations", "Intégrations"), ("devices", "Appareils"), ("sessions", "Sessions"), ("system", "Système"),
        ):
            actions.append((f"Ouvrir {label}", "Naviguer dans SKYNET", lambda page=key: self.navigate(page)))
        actions.extend([
            ("Piloter Windows", "Démarrer une mission de contrôle Windows gouvernée", lambda: self._start_prompt("Aide-moi à accomplir une tâche sur Windows avec UI Automation, vérification et permissions.")),
            ("Recherche approfondie", "Navigateur, preuves et synthèse", lambda: self._start_prompt("Je veux lancer une recherche approfondie. Demande-moi le sujet puis exécute une démarche sourcée et vérifiable.")),
            ("Analyse multi-agent", "Planificateur + spécialistes + vérificateur", lambda: self._start_prompt("Passe en analyse multi-agent sur le problème que je vais te donner.")),
            ("Créer une automatisation", "Construire une routine liée au bon contexte", lambda: self._start_prompt("Aide-moi à créer une automatisation locale utile, avec limites, critères de réussite et possibilité d’arrêt.")),
            ("Tester la voix", "Faire parler le moteur vocal actuel", self._test_voice),
            ("Arrêt global", "Passer immédiatement en mode sûr", self._kill_switch),
        ])
        CommandPalette(actions, self).exec()

    def navigate(self, page: str) -> None:
        if page not in self.pages:
            return
        self.current_page = page
        self.stack.setCurrentWidget(self.pages[page])
        for key, button in self.nav.items():
            button.setChecked(key == page)
        titles = {
            "home": "VUE D’ENSEMBLE", "chat": "CENTRE DE MISSION", "memory": "MÉMOIRE",
            "skills": "COMPÉTENCES", "automations": "AUTOMATISATIONS", "browser": "RECHERCHE",
            "integrations": "INTÉGRATIONS", "devices": "APPAREILS", "sessions": "SESSIONS", "system": "SYSTÈME",
        }
        self.breadcrumb.setText(f"SKYNET / {titles.get(page, page.upper())}")
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
        self._append_message("VOUS", text)
        self.status_label.setText("● MISSION EN COURS")
        self.orb.set_mode("thinking")
        self.mission_state.setText("En cours…\n\nSKYNET raisonne, sélectionne ses outils et maintient la frontière d’exécution.")
        self._trace("Mission", "Objectif utilisateur accepté")
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
            self._append_message("SKYNET", "Systèmes opérationnels. Donnez-moi un objectif : je peux planifier, agir avec mes outils et vérifier le résultat.")
            return
        for message in messages:
            role = str(message.get("role", "")).lower()
            who = "VOUS" if role == "user" else "SKYNET" if role == "assistant" else role.upper()
            self._append_message(who, str(message.get("content", "")))

    def _refresh_data_page(self, key: str, page: DataPage) -> None:
        try:
            if key == "memory":
                sessions = self.runtime.sessions.list(limit=20)
                memories = self.runtime.memory.list_memories(limit=20)
                body = self._cards_html("Mémoire persistante", [
                    ("Souvenirs durables", str(len(memories)), "entrées récentes"),
                    ("Sessions", str(len(sessions)), "recherchables et bifurcables"),
                    ("Mémoire sémantique", "ACTIVE", "rappel du contexte pertinent"),
                ]) + "<h3>Souvenirs récents</h3>" + self._items_html(memories)
            elif key == "skills":
                skills = self.runtime.skills.list_skills()
                body = self._cards_html("Système de compétences", [
                    ("Approuvées", str(len(skills)), "disponibles pour l’agent"),
                    ("Chargement progressif", "ACTIF", "seules les compétences pertinentes entrent en contexte"),
                    ("Pipeline candidat", "GOUVERNÉ", "validation avant promotion"),
                ]) + "<h3>Compétences approuvées</h3>" + self._items_html(skills[:30])
            elif key == "automations":
                routines = self.runtime.routines.list()
                body = self._cards_html("Autonomie", [
                    ("Routines", str(len(routines)), "intervalle / unique / budget d’exécutions"),
                    ("Liées aux sessions", "OUI", "le bon contexte est conservé"),
                    ("Sécurité sans surveillance", "ACTIVE", "les actions sensibles ne s’auto-approuvent pas"),
                ]) + "<h3>Routines configurées</h3>" + self._items_html([self.runtime.routines.render(x) for x in routines])
            elif key == "browser":
                state = self.runtime.browser.state()
                body = self._cards_html("Pile de recherche", [
                    ("Mode navigateur", str(state.mode), "local en priorité"),
                    ("Lecture HTTP", "ACTIVE", "extraction du texte et des liens"),
                    ("Navigateur interactif", "OPTIONNEL", "Playwright local si installé"),
                ]) + "<h3>Ce que cela permet</h3>" + self._items_html([
                    "Collecte de preuves et comparaison de sources",
                    "Navigation, clic, saisie et capture sous gouvernance",
                    "Sessions de recherche avec audit et vérification",
                ])
            elif key == "integrations":
                integrations = self.runtime.integrations.list(enabled_only=True)
                body = self._cards_html("Tissu de capacités", [
                    ("Intégrations actives", str(len(integrations)), "internes + MCP"),
                    ("Outils exposés", str(len(self.runtime.tools.schemas())), "tous gouvernés"),
                    ("MCP dynamique", "ACTIF", "les outils configurés deviennent natifs"),
                ]) + "<h3>Intégrations actives</h3>" + self._items_html([str(getattr(x, "name", x)) for x in integrations])
            elif key == "devices":
                snap = self.runtime.profiler.snapshot()
                body = self._cards_html("Machine locale", [
                    ("CPU", f"{snap.cpu_count} cœurs", "exécution locale"),
                    ("RAM", self._ram_text(snap), "disponible / total"),
                    ("GPU", snap.gpu_name or "Non détecté", self._gpu_text(snap)),
                ]) + "<h3>Contrôle Windows</h3>" + self._items_html([
                    "Accessibilité et UI Automation en priorité",
                    "Capture d’écran et vision en secours",
                    "PowerShell derrière permission et politique",
                ])
            elif key == "sessions":
                sessions = self.runtime.sessions.list(limit=100)
                body = self._cards_html("Continuité", [
                    ("Sessions", str(len(sessions)), "état conversationnel durable"),
                    ("Recherche", "ACTIVE", "retrouver le contexte précédent"),
                    ("Bifurcation", "ACTIVE", "ouvrir une investigation sans perdre l’original"),
                ]) + "<h3>Sessions récentes</h3>" + self._items_html([f"{x.title} · {x.session_id}" for x in sessions[:40]])
            elif key == "system":
                voice = self.voice.status()
                body = self._cards_html("Gouvernance", [
                    ("Arrêt global", "ENGAGÉ" if self.runtime.control.engaged() else "ARMÉ", "contrôle général"),
                    ("Reçus", "SIGNÉS", "les actions laissent une preuve vérifiable"),
                    ("Permissions", "APPLIQUÉES", "les outils inconnus sont bloqués"),
                ]) + self._cards_html("Présence vocale", [
                    ("Moteur", voice.provider, voice.detail),
                    ("Voix", voice.voice or "—", "français par défaut"),
                    ("État", "PRÊTE" if voice.ready else "INDISPONIBLE", voice.last_error or "aucune erreur"),
                ]) + "<h3>Frontière d’exécution</h3>" + self._items_html([
                    "Mandat → politique → permission → exécution → reçu",
                    "Budget de risque et classification des actions irréversibles",
                    "Évolution en bac à sable, canari et retour arrière",
                    "Accélérateur de réalité synthétique et rejeu des régressions",
                ])
            else:
                body = ""
            page.set_html(body)
        except Exception as exc:
            page.set_html(f"<p style='color:{RED}'>Impossible d’actualiser la page : {html.escape(str(exc))}</p>")

    @staticmethod
    def _items_html(items) -> str:
        values = list(items)
        if not values:
            return f"<p style='color:{MUTED}'>Rien d’enregistré pour le moment.</p>"
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
            return "Inconnue"
        return f"{snap.ram_available_mb/1024:.1f} / {snap.ram_total_mb/1024:.1f} Go"

    @staticmethod
    def _gpu_text(snap) -> str:
        if snap.gpu_memory_total_mb is None:
            return "Télémétrie VRAM indisponible"
        used = snap.gpu_memory_used_mb or 0
        return f"{used/1024:.1f} / {snap.gpu_memory_total_mb/1024:.1f} Go VRAM"

    def _refresh_dynamic(self) -> None:
        try:
            self.metric_tools.value_widget.setText(str(len(self.runtime.tools.schemas())))  # type: ignore[attr-defined]
            self.metric_integrations.value_widget.setText(str(len(self.runtime.integrations.list(enabled_only=True))))  # type: ignore[attr-defined]
            self.metric_sessions.value_widget.setText(str(len(self.runtime.sessions.list(limit=500))))  # type: ignore[attr-defined]
            self.metric_skills.value_widget.setText(str(len(self.runtime.skills.list_skills())))  # type: ignore[attr-defined]
            voice = self.voice.status()
            self.side_voice.setText(f"VOIX\n{voice.provider}\n{voice.detail}")
            snap = self.runtime.profiler.snapshot()
            posture = (
                f"<b>Modèle</b> · {html.escape(self.runtime.router.last_route.model)}<br>"
                f"<b>RAM</b> · {html.escape(self._ram_text(snap))}<br>"
                f"<b>GPU</b> · {html.escape(snap.gpu_name or 'non détecté')}<br>"
                f"<b>Navigateur</b> · {html.escape(str(self.runtime.browser.state().mode))}<br>"
                f"<b>Arrêt global</b> · {'ENGAGÉ' if self.runtime.control.engaged() else 'prêt'}"
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

    def _announce_startup(self) -> None:
        if not self.voice_enabled:
            return
        hour = time.localtime().tm_hour
        salutation = "Bonjour" if 5 <= hour < 18 else "Bonsoir"
        model = self.runtime.router.last_route.model.replace(":", " ")
        text = (
            f"Initialisation de SKYNET. Noyau souverain chargé. Mémoire persistante en ligne. "
            f"Gouvernance et contrôle des permissions actifs. Modèle local {model} prêt. "
            f"{salutation}. Tous les systèmes sont opérationnels."
        )
        self._trace("Présence", f"Annonce de démarrage · {self.voice.status().provider}")
        self.voice.speak(text)

    def _test_voice(self) -> None:
        self.voice.refresh()
        status = self.voice.status()
        self._trace("Voix", f"Test · {status.provider}")
        self.voice.speak("Test vocal. SKYNET est en ligne. La présence vocale française est opérationnelle.")

    def _toggle_voice(self) -> None:
        self.voice_enabled = not self.voice_enabled
        if not self.voice_enabled:
            self.voice.stop()
            self._trace("Voix", "Synthèse vocale désactivée")
        else:
            self.voice.refresh()
            self._trace("Voix", f"Synthèse vocale activée · {self.voice.status().provider}")
            self._test_voice()

    def _kill_switch(self) -> None:
        answer = QMessageBox.warning(
            self,
            "Arrêt global SKYNET",
            "Passer SKYNET en mode sûr et arrêter l’exécution autonome ?",
            QMessageBox.Yes | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )
        if answer != QMessageBox.Yes:
            return
        try:
            self.runtime.control.engage("arrêt global manuel depuis l’interface")
            self.orb.set_mode("stopped")
            self.status_label.setText("● MODE SÛR")
            self.status_label.setStyleSheet(f"color:{RED};font-weight:700")
            self._trace("Sécurité", "Arrêt global engagé")
        except Exception as exc:
            QMessageBox.critical(self, "Arrêt global", str(exc))

    def _connect_bridge(self) -> None:
        self.bridge.reply.connect(self._on_reply)
        self.bridge.error.connect(self._on_error)
        self.bridge.busy.connect(self._on_busy)
        self.bridge.confirm.connect(self._on_confirm)
        self.bridge.trace.connect(self._trace)
        self.bridge.voice_state.connect(self._on_voice_state)

    def _on_reply(self, reply: str) -> None:
        self._append_message("SKYNET", reply)
        self.mission_state.setText("Terminée\n\nLa réponse vient du Runtime gouverné. La trace permet d’inspecter le chemin d’exécution.")
        self._trace("Sortie", "Réponse de mission terminée")
        if self.voice_enabled:
            self.voice.speak(reply)

    def _on_error(self, message: str) -> None:
        self._append_message("SYSTÈME", message)
        self.mission_state.setText(f"Bloquée / échouée\n\n{message}")
        self._trace("Erreur", message[:120])

    def _on_busy(self, busy: bool) -> None:
        if busy:
            self.status_label.setText("● MISSION EN COURS")
            self.orb.set_mode("thinking")
        else:
            self.status_label.setText("● SYSTÈMES OPÉRATIONNELS")
            self.orb.set_mode("idle" if not self.runtime.control.engaged() else "stopped")

    def _on_confirm(self, message: str, packet: object) -> None:
        data = packet
        answer = QMessageBox.question(
            self,
            "Demande d’autorisation SKYNET",
            message,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        data["result"] = answer == QMessageBox.Yes  # type: ignore[index]
        data["event"].set()  # type: ignore[index]
        self._trace("Permission", "Approuvée" if data["result"] else "Refusée")  # type: ignore[index]

    def _on_voice_state(self, state: str) -> None:
        if state == "speaking":
            self._trace("Voix", f"Parle · {self.voice.status().provider}")
        elif state.startswith("loading:"):
            self._trace("Voix", state.split(":", 1)[1])
        elif state.startswith("fallback:"):
            self._trace("Voix", "Bascule moteur · " + state.split(":", 1)[1][:100])
        elif state.startswith("error:"):
            self._trace("Voix", "Échec · " + state.split(":", 1)[1][:120])

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
