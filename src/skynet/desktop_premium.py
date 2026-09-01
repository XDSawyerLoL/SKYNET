from __future__ import annotations

import queue
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk
from typing import Any

from .runtime import Runtime
from .ui_premium import PALETTE, CommandCore, HudCard, NeonButton, Pill, RingGauge, Sparkline, Waveform


NAV_ITEMS = (
    ("home", "⌂", "Home"),
    ("chat", "◫", "Chat"),
    ("memory", "▣", "Memory"),
    ("skills", "✧", "Skills"),
    ("automations", "◉", "Automations"),
    ("browser", "◎", "Browser"),
    ("integrations", "⌘", "Integrations"),
    ("devices", "▱", "Devices"),
    ("sessions", "☷", "Sessions"),
    ("system", "⚙", "System"),
)


def _field(item: Any, name: str, default: Any = "") -> Any:
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


class PremiumDesktopApp:
    """SKYNET premium command center.

    The interface is intentionally implemented with the Python standard library
    so the sovereign/local-first install remains dependency-light. It uses the
    real Runtime stores and the real governed Agent; dashboard values are derived
    from local state rather than invented demo telemetry.
    """

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("SKYNET — Sovereign Command Center")
        self.root.geometry("1600x940")
        self.root.minsize(1180, 720)
        self.root.configure(bg=PALETTE.bg)
        try:
            self.root.state("zoomed")
        except tk.TclError:
            pass

        self.runtime = Runtime.create(Path.cwd(), session_id="desktop")
        self.events: queue.Queue[tuple[str, Any]] = queue.Queue()
        self.busy = False
        self.resource_busy = False
        self.page = "home"
        self.nav_buttons: dict[str, tk.Button] = {}
        self.chat_widget: tk.Text | None = None
        self.entry_widget: tk.Text | None = None
        self.trace_widget: tk.Text | None = None
        self.core: CommandCore | None = None
        self.waveform: Waveform | None = None
        self.session_ids: list[str] = []
        self.resource_snapshot = None
        self.resource_labels: dict[str, tk.Label] = {}
        self.resource_sparks: dict[str, Sparkline] = {}
        self._last_response_started = 0.0

        self._configure_ttk()
        self._build_shell()
        self._navigate("home")
        self._trace("Runtime", "Sovereign core initialized")
        self._trace("Policy", "Mandate + PermissionGate active")
        self._trace("Model", self._model_name())

        self.root.after(80, self._drain_events)
        self.root.after(400, self._request_resource_snapshot)
        self.root.protocol("WM_DELETE_WINDOW", self._close)

    # ------------------------------------------------------------------ shell

    def _configure_ttk(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(
            "Sky.Vertical.TScrollbar",
            background=PALETTE.panel_alt,
            troughcolor=PALETTE.bg,
            bordercolor=PALETTE.bg,
            arrowcolor=PALETTE.muted,
            lightcolor=PALETTE.panel_alt,
            darkcolor=PALETTE.panel_alt,
        )

    def _build_shell(self) -> None:
        self.root.grid_columnconfigure(0, weight=0)
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)
        self._build_sidebar()

        shell = tk.Frame(self.root, bg=PALETTE.bg)
        shell.grid(row=0, column=1, sticky="nsew")
        shell.grid_columnconfigure(0, weight=1)
        shell.grid_rowconfigure(1, weight=1)
        self.shell = shell

        self._build_topbar(shell)
        self.page_host = tk.Frame(shell, bg=PALETTE.bg)
        self.page_host.grid(row=1, column=0, sticky="nsew", padx=12, pady=(4, 8))
        self._build_footer(shell)

    def _build_sidebar(self) -> None:
        side = tk.Frame(
            self.root,
            width=248,
            bg=PALETTE.sidebar,
            highlightthickness=1,
            highlightbackground=PALETTE.border,
        )
        side.grid(row=0, column=0, sticky="nsw", padx=(10, 0), pady=10)
        side.grid_propagate(False)
        side.grid_columnconfigure(0, weight=1)
        side.grid_rowconfigure(3, weight=1)
        self.sidebar = side

        brand = tk.Frame(side, bg=PALETTE.sidebar)
        brand.grid(row=0, column=0, sticky="ew", padx=16, pady=(18, 14))
        brand.grid_columnconfigure(1, weight=1)
        logo = CommandCore(brand, size=56, bg=PALETTE.sidebar)
        logo.grid(row=0, column=0, rowspan=2, padx=(0, 10))
        logo.set_label("")
        tk.Label(brand, text="SKYNET", bg=PALETTE.sidebar, fg=PALETTE.text, font=("Segoe UI Semibold", 16)).grid(row=0, column=1, sticky="sw")
        tk.Label(brand, text="COMMAND CENTER", bg=PALETTE.sidebar, fg=PALETTE.muted, font=("Segoe UI", 7)).grid(row=1, column=1, sticky="nw")

        nav = tk.Frame(side, bg=PALETTE.sidebar)
        nav.grid(row=1, column=0, sticky="new", padx=8)
        for key, icon, label in NAV_ITEMS:
            button = tk.Button(
                nav,
                text=f" {icon}    {label}",
                anchor="w",
                command=lambda target=key: self._navigate(target),
                bg=PALETTE.sidebar,
                fg=PALETTE.text_soft,
                activebackground=PALETTE.panel_hot,
                activeforeground=PALETTE.text,
                relief="flat",
                bd=0,
                highlightthickness=0,
                cursor="hand2",
                font=("Segoe UI", 10),
                padx=12,
                pady=9,
            )
            button.pack(fill="x", pady=1)
            self.nav_buttons[key] = button

        status = HudCard(side, title="System Status")
        status.grid(row=2, column=0, sticky="ew", padx=12, pady=(14, 10))
        self.side_state = tk.Label(status.header, text="● OPTIMAL", bg=PALETTE.panel, fg=PALETTE.green, font=("Segoe UI Semibold", 8))
        self.side_state.grid(row=0, column=1, sticky="e")
        for row, key in enumerate(("CPU", "GPU", "RAM", "POWER")):
            tk.Label(status.body, text=key, bg=PALETTE.panel, fg=PALETTE.muted, font=("Segoe UI", 8)).grid(row=row, column=0, sticky="w", pady=3)
            label = tk.Label(status.body, text="—", bg=PALETTE.panel, fg=PALETTE.text_soft, font=("Segoe UI Semibold", 8))
            label.grid(row=row, column=1, sticky="e", pady=3)
            status.body.grid_columnconfigure(1, weight=1)
            self.resource_labels[f"side_{key.lower()}"] = label

        self.sidebar_mode = tk.Label(side, text="◈  LOCAL · SOVEREIGN", bg=PALETTE.sidebar, fg=PALETTE.cyan, font=("Segoe UI Semibold", 8))
        self.sidebar_mode.grid(row=4, column=0, sticky="w", padx=18, pady=(6, 2))
        tk.Label(side, text="No mandatory cloud API", bg=PALETTE.sidebar, fg=PALETTE.faint, font=("Segoe UI", 7)).grid(row=5, column=0, sticky="w", padx=18, pady=(0, 16))

    def _build_topbar(self, master: tk.Frame) -> None:
        top = tk.Frame(master, bg=PALETTE.bg_alt, height=58, highlightthickness=1, highlightbackground=PALETTE.border)
        top.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 4))
        top.grid_propagate(False)
        top.grid_columnconfigure(1, weight=1)
        self.breadcrumb = tk.Label(top, text="SKYNET  //  HOME · COMMAND CENTER", bg=PALETTE.bg_alt, fg=PALETTE.cyan, font=("Segoe UI Semibold", 9))
        self.breadcrumb.grid(row=0, column=0, padx=18, sticky="w")

        center = tk.Frame(top, bg=PALETTE.bg_alt)
        center.grid(row=0, column=1)
        self.top_activity = Pill(center, "●  SYSTEMS NOMINAL", fg=PALETTE.green, bg=PALETTE.bg_alt)
        self.top_activity.pack(side="left", padx=5)
        self.top_session = Pill(center, "SESSION: DESKTOP", fg=PALETTE.muted, bg=PALETTE.bg_alt)
        self.top_session.pack(side="left", padx=5)

        model = tk.Frame(top, bg=PALETTE.panel, highlightthickness=1, highlightbackground=PALETTE.border)
        model.grid(row=0, column=2, padx=12, pady=9, sticky="e")
        tk.Label(model, text="LOCAL MODEL", bg=PALETTE.panel, fg=PALETTE.green, font=("Segoe UI", 7)).pack(anchor="w", padx=12, pady=(4, 0))
        self.model_label = tk.Label(model, text=self._model_name(), bg=PALETTE.panel, fg=PALETTE.text, font=("Segoe UI Semibold", 9))
        self.model_label.pack(anchor="w", padx=12, pady=(0, 4))

    def _build_footer(self, master: tk.Frame) -> None:
        footer = tk.Frame(master, bg=PALETTE.bg_alt, height=62, highlightthickness=1, highlightbackground=PALETTE.border)
        footer.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 10))
        footer.grid_propagate(False)
        footer.grid_columnconfigure(1, weight=1)
        quick = tk.Frame(footer, bg=PALETTE.bg_alt)
        quick.grid(row=0, column=0, padx=14)
        tk.Label(quick, text="QUICK LAUNCH", bg=PALETTE.bg_alt, fg=PALETTE.faint, font=("Segoe UI Semibold", 7)).pack(anchor="w")
        row = tk.Frame(quick, bg=PALETTE.bg_alt)
        row.pack()
        for text, target in ((">_", "system"), ("</>", "skills"), ("◫", "sessions"), ("◎", "browser")):
            tk.Button(row, text=text, command=lambda t=target: self._navigate(t), bg=PALETTE.panel, fg=PALETTE.cyan, activebackground=PALETTE.panel_hot, activeforeground=PALETTE.text, relief="flat", bd=0, cursor="hand2", font=("Consolas", 9), width=4).pack(side="left", padx=2)

        self.footer_status = tk.Label(footer, text="Ready", bg=PALETTE.bg_alt, fg=PALETTE.muted, font=("Segoe UI", 8))
        self.footer_status.grid(row=0, column=1)
        self.footer_time = tk.Label(footer, text="", bg=PALETTE.bg_alt, fg=PALETTE.faint, font=("Consolas", 8))
        self.footer_time.grid(row=0, column=2, padx=16)
        self._tick_clock()

    def _tick_clock(self) -> None:
        self.footer_time.configure(text=time.strftime("%H:%M:%S"))
        self.root.after(1000, self._tick_clock)

    # --------------------------------------------------------------- navigation

    def _navigate(self, key: str) -> None:
        self.page = key
        for name, button in self.nav_buttons.items():
            active = name == key
            button.configure(
                bg=PALETTE.panel_hot if active else PALETTE.sidebar,
                fg=PALETTE.cyan if active else PALETTE.text_soft,
                highlightthickness=1 if active else 0,
                highlightbackground=PALETTE.border_hot,
            )
        for child in self.page_host.winfo_children():
            child.destroy()
        self.chat_widget = None
        self.entry_widget = None
        self.trace_widget = None
        self.core = None
        self.waveform = None

        title = dict((k, label) for k, _i, label in NAV_ITEMS).get(key, key.title())
        self.breadcrumb.configure(text=f"SKYNET  //  {title.upper()}")
        renderer = getattr(self, f"_render_{key}", self._render_home)
        renderer()

    # ------------------------------------------------------------------- home

    def _render_home(self) -> None:
        host = self.page_host
        host.grid_columnconfigure(0, weight=5, uniform="home")
        host.grid_columnconfigure(1, weight=6, uniform="home")
        host.grid_columnconfigure(2, weight=4, uniform="home")
        host.grid_rowconfigure(0, weight=1)
        host.grid_rowconfigure(1, weight=0)

        left = tk.Frame(host, bg=PALETTE.bg)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(0, weight=1)

        core_card = HudCard(left, title="System Core", accent=PALETTE.cyan)
        core_card.grid(row=0, column=0, sticky="nsew", pady=(0, 5))
        self.core = CommandCore(core_card.body, size=410, bg=PALETTE.panel)
        self.core.pack(fill="both", expand=True)
        self.core.set_mode("stopped" if self.runtime.control.engaged() else "thinking" if self.busy else "idle")

        metrics = HudCard(left, title="Core Metrics")
        metrics.grid(row=1, column=0, sticky="ew", pady=5)
        metrics.body.grid_columnconfigure((0, 1), weight=1)
        pairs = (
            ("MODEL", self._model_name()),
            ("TOOLS", str(len(self.runtime.tools.schemas()))),
            ("SESSIONS", str(len(self.runtime.sessions.list(limit=1000)))),
            ("SKILLS", str(len(self.runtime.skills.list_skills()))),
        )
        for i, (name, value) in enumerate(pairs):
            box = tk.Frame(metrics.body, bg=PALETTE.panel_alt, highlightthickness=1, highlightbackground=PALETTE.border)
            box.grid(row=i//2, column=i%2, sticky="ew", padx=3, pady=3)
            tk.Label(box, text=name, bg=PALETTE.panel_alt, fg=PALETTE.faint, font=("Segoe UI", 7)).pack(anchor="w", padx=9, pady=(6, 0))
            tk.Label(box, text=value[:26], bg=PALETTE.panel_alt, fg=PALETTE.text, font=("Segoe UI Semibold", 10)).pack(anchor="w", padx=9, pady=(0, 6))

        voice = HudCard(left, title="Voice Interface")
        voice.grid(row=2, column=0, sticky="ew", pady=(5, 0))
        voice.body.grid_columnconfigure(0, weight=1)
        self.waveform = Waveform(voice.body, height=54, bg=PALETTE.panel)
        self.waveform.grid(row=0, column=0, sticky="ew")
        tk.Label(voice.body, text="VOICE MODULE · not enabled yet", bg=PALETTE.panel, fg=PALETTE.faint, font=("Segoe UI", 7)).grid(row=1, column=0, sticky="w", pady=(2, 0))

        center = HudCard(host, title="Command Console", accent=PALETTE.cyan2)
        center.grid(row=0, column=1, sticky="nsew", padx=5)
        self._build_console(center.body, compact=True)

        right = tk.Frame(host, bg=PALETTE.bg)
        right.grid(row=0, column=2, sticky="nsew", padx=(5, 0))
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(2, weight=1)
        self._build_companion_card(right)
        self._build_memory_snapshot(right)
        self._build_trace_card(right)
        self._build_security_card(right)

        bottom = tk.Frame(host, bg=PALETTE.bg)
        bottom.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        bottom.grid_columnconfigure(0, weight=5)
        bottom.grid_columnconfigure(1, weight=3)
        bottom.grid_columnconfigure(2, weight=4)
        self._build_sessions_strip(bottom)
        self._build_automation_strip(bottom)
        self._build_resource_strip(bottom)

    def _build_console(self, master: tk.Frame, *, compact: bool = False) -> None:
        master.grid_columnconfigure(0, weight=1)
        master.grid_rowconfigure(0, weight=1)
        conversation = tk.Frame(master, bg=PALETTE.panel)
        conversation.grid(row=0, column=0, sticky="nsew")
        conversation.grid_columnconfigure(0, weight=1)
        conversation.grid_rowconfigure(0, weight=1)
        self.chat_widget = tk.Text(
            conversation,
            wrap="word",
            state="disabled",
            bg=PALETTE.panel,
            fg=PALETTE.text_soft,
            insertbackground=PALETTE.cyan,
            selectbackground=PALETTE.border_hot,
            highlightthickness=0,
            bd=0,
            font=("Segoe UI", 9 if compact else 10),
            padx=12,
            pady=8,
            spacing3=7,
        )
        self.chat_widget.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(conversation, orient="vertical", command=self.chat_widget.yview, style="Sky.Vertical.TScrollbar")
        scroll.grid(row=0, column=1, sticky="ns")
        self.chat_widget.configure(yscrollcommand=scroll.set)
        self.chat_widget.tag_configure("user_label", foreground=PALETTE.muted, font=("Segoe UI Semibold", 8), spacing1=10)
        self.chat_widget.tag_configure("ai_label", foreground=PALETTE.cyan, font=("Segoe UI Semibold", 8), spacing1=10)
        self.chat_widget.tag_configure("system_label", foreground=PALETTE.amber, font=("Segoe UI Semibold", 8), spacing1=10)
        self.chat_widget.tag_configure("body", foreground=PALETTE.text_soft, lmargin1=12, lmargin2=12, rmargin=14)
        self._load_session_history()

        composer = tk.Frame(master, bg=PALETTE.panel_alt, highlightthickness=1, highlightbackground=PALETTE.border_hot)
        composer.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        composer.grid_columnconfigure(0, weight=1)
        self.entry_widget = tk.Text(composer, height=2 if compact else 3, wrap="word", bg=PALETTE.panel_alt, fg=PALETTE.text, insertbackground=PALETTE.cyan, relief="flat", bd=0, highlightthickness=0, font=("Segoe UI", 9), padx=10, pady=9)
        self.entry_widget.grid(row=0, column=0, sticky="ew")
        self.entry_widget.bind("<Return>", self._entry_return)
        NeonButton(composer, "SEND  ➤", self._send, primary=True).grid(row=0, column=1, padx=8, pady=7)

        actions = tk.Frame(master, bg=PALETTE.panel)
        actions.grid(row=2, column=0, sticky="ew", pady=(7, 0))
        for label, prompt in (
            ("Summarize", "Résume la situation actuelle en quelques points utiles."),
            ("Create Task", "Aide-moi à transformer mon objectif en plan d'action concret."),
            ("Run Trace", "Explique les étapes de haut niveau prévues pour cette tâche sans révéler de raisonnement privé."),
            ("Deep Research", "Prépare une recherche approfondie et vérifiable sur mon prochain sujet."),
        ):
            NeonButton(actions, label, lambda p=prompt: self._prefill(p)).pack(side="left", padx=(0, 5))

    def _build_companion_card(self, master: tk.Frame) -> None:
        card = HudCard(master, title="Companion")
        card.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        body = card.body
        body.grid_columnconfigure(1, weight=1)
        gauge = RingGauge(body, value=100 if not self.runtime.control.engaged() else 0, label="ONLINE" if not self.runtime.control.engaged() else "SAFE", size=78, bg=PALETTE.panel)
        gauge.grid(row=0, column=0, rowspan=3, padx=(0, 10))
        tk.Label(body, text="SKYNET", bg=PALETTE.panel, fg=PALETTE.text, font=("Segoe UI Semibold", 12)).grid(row=0, column=1, sticky="sw")
        tk.Label(body, text="Sovereign local AI companion", bg=PALETTE.panel, fg=PALETTE.muted, font=("Segoe UI", 8)).grid(row=1, column=1, sticky="nw")
        tk.Label(body, text="● ONLINE" if not self.runtime.control.engaged() else "● SAFE MODE", bg=PALETTE.panel, fg=PALETTE.green if not self.runtime.control.engaged() else PALETTE.red, font=("Segoe UI Semibold", 8)).grid(row=2, column=1, sticky="nw")

    def _build_memory_snapshot(self, master: tk.Frame) -> None:
        card = HudCard(master, title="Memory Snapshot")
        card.grid(row=1, column=0, sticky="ew", pady=5)
        facts = len(self.runtime.memory.list_memories(limit=1000))
        sessions = len(self.runtime.sessions.list(limit=1000))
        skills = len(self.runtime.skills.list_skills())
        for row, (name, value) in enumerate((("Durable memories", facts), ("Sessions", sessions), ("Approved skills", skills))):
            tk.Label(card.body, text=name.upper(), bg=PALETTE.panel, fg=PALETTE.faint, font=("Segoe UI", 7)).grid(row=row, column=0, sticky="w", pady=3)
            tk.Label(card.body, text=str(value), bg=PALETTE.panel, fg=PALETTE.text, font=("Segoe UI Semibold", 9)).grid(row=row, column=1, sticky="e", pady=3)
        card.body.grid_columnconfigure(1, weight=1)

    def _build_trace_card(self, master: tk.Frame) -> None:
        card = HudCard(master, title="Live Activity Trace")
        card.grid(row=2, column=0, sticky="nsew", pady=5)
        card.body.grid_rowconfigure(0, weight=1)
        card.body.grid_columnconfigure(0, weight=1)
        self.trace_widget = tk.Text(card.body, state="disabled", wrap="word", bg=PALETTE.panel, fg=PALETTE.muted, highlightthickness=0, bd=0, font=("Consolas", 7), padx=2, pady=2)
        self.trace_widget.grid(row=0, column=0, sticky="nsew")
        for line in (
            "Runtime   Local stores connected",
            "Memory    Context available",
            "Policy    Governance boundary active",
            f"Model     {self._model_name()}",
        ):
            self._trace("", line, write_queue=False)

    def _build_security_card(self, master: tk.Frame) -> None:
        card = HudCard(master, title="Security Governance", accent=PALETTE.red if self.runtime.control.engaged() else PALETTE.green)
        card.grid(row=3, column=0, sticky="ew", pady=(5, 0))
        state = "KILL SWITCH ENGAGED" if self.runtime.control.engaged() else "GOVERNED EXECUTION ACTIVE"
        tk.Label(card.body, text=state, bg=PALETTE.panel, fg=PALETTE.red if self.runtime.control.engaged() else PALETTE.green, font=("Segoe UI Semibold", 8)).pack(anchor="w")
        tk.Label(card.body, text="Mandate → Policy → Permission → Receipt", bg=PALETTE.panel, fg=PALETTE.muted, font=("Segoe UI", 7)).pack(anchor="w", pady=(3, 6))
        NeonButton(card.body, "Open Security", lambda: self._navigate("system")).pack(fill="x")

    def _build_sessions_strip(self, master: tk.Frame) -> None:
        card = HudCard(master, title="Sessions")
        card.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        sessions = self.runtime.sessions.list(limit=4)
        for item in sessions:
            title = str(_field(item, "title", _field(item, "session_id", "Session")))[:25]
            sid = str(_field(item, "session_id", ""))
            NeonButton(card.body, title, lambda s=sid: self._switch_session(s)).pack(side="left", padx=(0, 4))
        NeonButton(card.body, "+", self._new_session).pack(side="left")

    def _build_automation_strip(self, master: tk.Frame) -> None:
        card = HudCard(master, title="Automations")
        card.grid(row=0, column=1, sticky="ew", padx=5)
        routines = self.runtime.routines.list()
        enabled = sum(1 for item in routines if bool(_field(item, "enabled", True)))
        tk.Label(card.body, text=str(enabled), bg=PALETTE.panel, fg=PALETTE.cyan, font=("Segoe UI Semibold", 18)).pack(side="left", padx=(0, 8))
        tk.Label(card.body, text=f"ACTIVE\n{len(routines)} CONFIGURED", justify="left", bg=PALETTE.panel, fg=PALETTE.muted, font=("Segoe UI", 7)).pack(side="left")
        NeonButton(card.body, "VIEW", lambda: self._navigate("automations")).pack(side="right")

    def _build_resource_strip(self, master: tk.Frame) -> None:
        card = HudCard(master, title="Resource Monitors")
        card.grid(row=0, column=2, sticky="ew", padx=(5, 0))
        card.body.grid_columnconfigure((0, 1, 2), weight=1)
        for col, (key, color) in enumerate((("RAM", PALETTE.cyan), ("GPU", PALETTE.green), ("POWER", PALETTE.purple))):
            box = tk.Frame(card.body, bg=PALETTE.panel)
            box.grid(row=0, column=col, sticky="ew", padx=3)
            value = tk.Label(box, text="—", bg=PALETTE.panel, fg=PALETTE.text, font=("Segoe UI Semibold", 8))
            value.pack(anchor="w")
            self.resource_labels[f"home_{key.lower()}"] = value
            spark = Sparkline(box, color=color, height=28, bg=PALETTE.panel)
            spark.pack(fill="x")
            self.resource_sparks[key.lower()] = spark
            tk.Label(box, text=key, bg=PALETTE.panel, fg=PALETTE.faint, font=("Segoe UI", 7)).pack(anchor="w")

    # ---------------------------------------------------------- dedicated pages

    def _render_chat(self) -> None:
        host = self.page_host
        host.grid_columnconfigure(0, weight=7)
        host.grid_columnconfigure(1, weight=3)
        host.grid_rowconfigure(0, weight=1)
        center = HudCard(host, title="Mission Control / Conversation", accent=PALETTE.cyan2)
        center.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        self._build_console(center.body, compact=False)
        right = tk.Frame(host, bg=PALETTE.bg)
        right.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=1)
        self._build_memory_snapshot(right)
        self._build_trace_card(right)
        self._build_security_card(right)

    def _render_memory(self) -> None:
        host = self._page_frame("Memory / Sessions", "Persistent local continuity, searchable sessions and durable facts")
        top = tk.Frame(host, bg=PALETTE.bg)
        top.pack(fill="x", pady=(0, 8))
        metrics = (
            ("SESSIONS", len(self.runtime.sessions.list(limit=5000)), PALETTE.cyan),
            ("DURABLE FACTS", len(self.runtime.memory.list_memories(limit=5000)), PALETTE.green),
            ("SKILLS", len(self.runtime.skills.list_skills()), PALETTE.purple),
        )
        for name, value, color in metrics:
            card = HudCard(top, title=name, accent=color)
            card.pack(side="left", fill="x", expand=True, padx=4)
            tk.Label(card.body, text=str(value), bg=PALETTE.panel, fg=PALETTE.text, font=("Segoe UI Semibold", 22)).pack(anchor="w")

        body = tk.Frame(host, bg=PALETTE.bg)
        body.pack(fill="both", expand=True)
        body.grid_columnconfigure(0, weight=6)
        body.grid_columnconfigure(1, weight=4)
        body.grid_rowconfigure(0, weight=1)
        sessions_card = HudCard(body, title="Session History")
        sessions_card.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        listbox = tk.Listbox(sessions_card.body, bg=PALETTE.panel, fg=PALETTE.text_soft, selectbackground=PALETTE.panel_hot, selectforeground=PALETTE.cyan, bd=0, highlightthickness=0, font=("Segoe UI", 9))
        listbox.pack(fill="both", expand=True)
        for item in self.runtime.sessions.list(limit=200):
            listbox.insert("end", f"{_field(item, 'title', 'Session')}   ·   {_field(item, 'channel', 'local')}")
        actions = tk.Frame(sessions_card.body, bg=PALETTE.panel)
        actions.pack(fill="x", pady=(8, 0))
        NeonButton(actions, "New Session", self._new_session).pack(side="left", padx=(0, 4))
        NeonButton(actions, "Search", self._search_sessions).pack(side="left")

        mem_card = HudCard(body, title="Durable Memory")
        mem_card.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        text = self._readonly_text(mem_card.body)
        memories = self.runtime.memory.list_memories(limit=100)
        self._set_text(text, "\n\n".join(f"◈ {m}" for m in memories) if memories else "No durable memory stored yet.")

    def _render_skills(self) -> None:
        host = self._page_frame("Skills", "Approved reusable procedures and candidate lifecycle")
        body = tk.Frame(host, bg=PALETTE.bg)
        body.pack(fill="both", expand=True)
        body.grid_columnconfigure(0, weight=6)
        body.grid_columnconfigure(1, weight=4)
        body.grid_rowconfigure(0, weight=1)
        approved = HudCard(body, title=f"Approved Skills · {len(self.runtime.skills.list_skills())}")
        approved.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        at = self._readonly_text(approved.body)
        skills = self.runtime.skills.list_skills()
        self._set_text(at, "\n".join(f"●  {name}" for name in skills) if skills else "No approved skills yet.")
        candidate_names = self.runtime.skills.list_candidates()
        candidates = HudCard(body, title=f"Candidate Skills · {len(candidate_names)}", accent=PALETTE.amber)
        candidates.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        ct = self._readonly_text(candidates.body)
        self._set_text(ct, "\n".join(f"◇  {name}" for name in candidate_names) if candidate_names else "No candidates awaiting validation.")
        tk.Label(candidates.body, text="Candidates never become active automatically.", bg=PALETTE.panel, fg=PALETTE.muted, font=("Segoe UI", 8)).pack(anchor="w", pady=(8, 0))

    def _render_automations(self) -> None:
        host = self._page_frame("Automations", "Persistent routines with session-bound context and governed unattended execution")
        card = HudCard(host, title="Configured Automations")
        card.pack(fill="both", expand=True)
        text = self._readonly_text(card.body)
        routines = self.runtime.routines.list()
        lines = [self.runtime.routines.render(item) for item in routines]
        self._set_text(text, "\n\n".join(lines) if lines else "No automation configured.")
        controls = tk.Frame(card.body, bg=PALETTE.panel)
        controls.pack(fill="x", pady=(8, 0))
        NeonButton(controls, "New Routine", self._new_routine, primary=True).pack(side="left", padx=(0, 5))
        NeonButton(controls, "Run Due Now", self._run_due).pack(side="left")

    def _render_browser(self) -> None:
        state = self.runtime.browser.state()
        host = self._page_frame("Browser / Deep Research", "Local web harness with read-only HTTP and optional Playwright interaction")
        body = tk.Frame(host, bg=PALETTE.bg)
        body.pack(fill="both", expand=True)
        body.grid_columnconfigure(0, weight=6)
        body.grid_columnconfigure(1, weight=4)
        browser = HudCard(body, title="Browser Harness")
        browser.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        tk.Label(browser.body, text=str(_field(state, "mode", "unknown")).upper(), bg=PALETTE.panel, fg=PALETTE.cyan, font=("Segoe UI Semibold", 26)).pack(anchor="w", pady=(8, 4))
        tk.Label(browser.body, text="Webpage content remains untrusted input. Interactive actions stay permission-gated.", wraplength=600, justify="left", bg=PALETTE.panel, fg=PALETTE.muted, font=("Segoe UI", 9)).pack(anchor="w")
        NeonButton(browser.body, "Open Chat Mission Control", lambda: self._navigate("chat"), primary=True).pack(anchor="w", pady=(16, 0))
        research = HudCard(body, title="Research Capabilities")
        research.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        capabilities = ["HTTP read-only navigation", "Source extraction", "Playwright when installed", "Screenshots permission-gated", "Memory + session integration", "MCP tools remain governed"]
        for line in capabilities:
            tk.Label(research.body, text=f"◈  {line}", bg=PALETTE.panel, fg=PALETTE.text_soft, font=("Segoe UI", 9)).pack(anchor="w", pady=4)

    def _render_integrations(self) -> None:
        host = self._page_frame("Integrations", "Replaceable local adapters, MCP discovery and channel infrastructure")
        card = HudCard(host, title="Enabled Integrations")
        card.pack(fill="both", expand=True)
        text = self._readonly_text(card.body)
        items = self.runtime.integrations.list(enabled_only=True)
        lines: list[str] = []
        for item in items:
            name = str(_field(item, "name", _field(item, "integration_id", item)))
            capabilities = _field(item, "capabilities", [])
            if isinstance(capabilities, (list, tuple, set)):
                cap = ", ".join(str(x) for x in capabilities)
            else:
                cap = str(capabilities)
            lines.append(f"● {name}\n   {cap}")
        self._set_text(text, "\n\n".join(lines) if lines else "No integration registry entries.")

    def _render_devices(self) -> None:
        host = self._page_frame("Devices", "Local hardware and Windows execution surface")
        body = tk.Frame(host, bg=PALETTE.bg)
        body.pack(fill="both", expand=True)
        body.grid_columnconfigure((0, 1), weight=1)
        hardware = HudCard(body, title="Hardware")
        hardware.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        snap = self.resource_snapshot or self.runtime.profiler.snapshot()
        rows = [
            ("CPU logical cores", snap.cpu_count),
            ("RAM total", self._mb(snap.ram_total_mb)),
            ("RAM available", self._mb(snap.ram_available_mb)),
            ("GPU", snap.gpu_name or "Not detected by nvidia-smi"),
            ("GPU VRAM", self._gpu_text(snap)),
            ("GPU power", f"{snap.gpu_power_w:.1f} W" if snap.gpu_power_w is not None else "Unavailable"),
        ]
        for name, value in rows:
            line = tk.Frame(hardware.body, bg=PALETTE.panel)
            line.pack(fill="x", pady=4)
            tk.Label(line, text=name.upper(), bg=PALETTE.panel, fg=PALETTE.faint, font=("Segoe UI", 7)).pack(side="left")
            tk.Label(line, text=str(value), bg=PALETTE.panel, fg=PALETTE.text, font=("Segoe UI Semibold", 9)).pack(side="right")
        windows = HudCard(body, title="Windows Control")
        windows.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        tk.Label(windows.body, text="UI Automation + accessibility-first control", bg=PALETTE.panel, fg=PALETTE.cyan, font=("Segoe UI Semibold", 10)).pack(anchor="w")
        tk.Label(windows.body, text="Visual fallback, screenshots, focus, invoke and typing remain behind permissions.", wraplength=480, justify="left", bg=PALETTE.panel, fg=PALETTE.muted, font=("Segoe UI", 9)).pack(anchor="w", pady=(8, 14))
        NeonButton(windows.body, "Inspect Visible Windows", self._scan_windows).pack(anchor="w")

    def _render_sessions(self) -> None:
        host = self._page_frame("Sessions", "Search, resume and fork persistent conversations")
        card = HudCard(host, title="Session Registry")
        card.pack(fill="both", expand=True)
        self.session_list = tk.Listbox(card.body, bg=PALETTE.panel, fg=PALETTE.text_soft, selectbackground=PALETTE.panel_hot, selectforeground=PALETTE.cyan, bd=0, highlightthickness=0, font=("Segoe UI", 10))
        self.session_list.pack(fill="both", expand=True)
        self.session_ids = []
        for item in self.runtime.sessions.list(limit=500):
            sid = str(_field(item, "session_id", ""))
            self.session_ids.append(sid)
            self.session_list.insert("end", f"{_field(item, 'title', sid)}     [{_field(item, 'channel', 'local')}]")
        self.session_list.bind("<Double-Button-1>", lambda _e: self._open_selected_session())
        controls = tk.Frame(card.body, bg=PALETTE.panel)
        controls.pack(fill="x", pady=(8, 0))
        NeonButton(controls, "Open", self._open_selected_session, primary=True).pack(side="left", padx=(0, 4))
        NeonButton(controls, "New", self._new_session).pack(side="left", padx=4)
        NeonButton(controls, "Fork Current", self._fork_session).pack(side="left", padx=4)
        NeonButton(controls, "Search", self._search_sessions).pack(side="left", padx=4)

    def _render_system(self) -> None:
        host = self._page_frame("Security / System", "Identity, policy boundary, kill switch and local configuration")
        body = tk.Frame(host, bg=PALETTE.bg)
        body.pack(fill="both", expand=True)
        body.grid_columnconfigure((0, 1, 2), weight=1)
        identity = HudCard(body, title="Sovereign Identity")
        identity.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        agent_id = str(self.runtime.identity.identity.agent_id)
        tk.Label(identity.body, text="VERIFIED LOCAL IDENTITY", bg=PALETTE.panel, fg=PALETTE.green, font=("Segoe UI Semibold", 10)).pack(anchor="w")
        tk.Label(identity.body, text=agent_id, wraplength=420, justify="left", bg=PALETTE.panel, fg=PALETTE.muted, font=("Consolas", 8)).pack(anchor="w", pady=(8, 0))

        governance = HudCard(body, title="Governance")
        governance.grid(row=0, column=1, sticky="nsew", padx=5)
        for line in ("Canonical Mandate", "Deterministic Policy Engine", "PermissionGate", "Signed action receipts", "Capability leases", "Audit chain"):
            tk.Label(governance.body, text=f"●  {line}", bg=PALETTE.panel, fg=PALETTE.text_soft, font=("Segoe UI", 9)).pack(anchor="w", pady=3)

        kill = HudCard(body, title="Kill Switch", accent=PALETTE.red)
        kill.grid(row=0, column=2, sticky="nsew", padx=(5, 0))
        self.kill_state = tk.Label(kill.body, text="ENGAGED" if self.runtime.control.engaged() else "ARMED · NOT ENGAGED", bg=PALETTE.panel, fg=PALETTE.red if self.runtime.control.engaged() else PALETTE.green, font=("Segoe UI Semibold", 14))
        self.kill_state.pack(anchor="w", pady=(8, 12))
        NeonButton(kill.body, "ENGAGE SAFE MODE", self._emergency_stop, danger=True).pack(fill="x", pady=3)
        NeonButton(kill.body, "REARM SKYNET", self._rearm).pack(fill="x", pady=3)

        config = HudCard(body, title="Local Configuration")
        config.grid(row=1, column=0, columnspan=3, sticky="nsew", pady=(10, 0))
        values = [
            f"Model pool: {', '.join(self.runtime.config.models)}",
            f"Ollama: {self.runtime.config.ollama_url}",
            f"Workspace: {self.runtime.config.workspace}",
            f"Data: {self.runtime.config.data_dir}",
            f"Browser: {self.runtime.browser.state().mode}",
            f"MCP config: {self.runtime.config.mcp_config}",
        ]
        tk.Label(config.body, text="\n".join(values), justify="left", bg=PALETTE.panel, fg=PALETTE.muted, font=("Consolas", 8)).pack(anchor="w")

    # --------------------------------------------------------------- page utils

    def _page_frame(self, title: str, subtitle: str) -> tk.Frame:
        wrapper = tk.Frame(self.page_host, bg=PALETTE.bg)
        wrapper.pack(fill="both", expand=True)
        header = tk.Frame(wrapper, bg=PALETTE.bg)
        header.pack(fill="x", pady=(4, 12))
        tk.Label(header, text=title.upper(), bg=PALETTE.bg, fg=PALETTE.text, font=("Segoe UI Semibold", 18)).pack(anchor="w")
        tk.Label(header, text=subtitle, bg=PALETTE.bg, fg=PALETTE.muted, font=("Segoe UI", 9)).pack(anchor="w", pady=(2, 0))
        return wrapper

    def _readonly_text(self, master: tk.Frame) -> tk.Text:
        text = tk.Text(master, state="disabled", wrap="word", bg=PALETTE.panel, fg=PALETTE.text_soft, bd=0, highlightthickness=0, font=("Segoe UI", 9), padx=6, pady=6, spacing3=5)
        text.pack(fill="both", expand=True)
        return text

    @staticmethod
    def _set_text(widget: tk.Text, value: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", value)
        widget.configure(state="disabled")

    # ------------------------------------------------------------- conversation

    def _append_chat(self, who: str, text: str) -> None:
        if self.chat_widget is None or not self.chat_widget.winfo_exists():
            return
        key = who.casefold()
        if key in {"you", "user", "vous", "toi"}:
            tag, label = "user_label", "YOU"
        elif key == "skynet":
            tag, label = "ai_label", "SKYNET"
        else:
            tag, label = "system_label", who.upper()
        self.chat_widget.configure(state="normal")
        self.chat_widget.insert("end", f"{label}  ·  {time.strftime('%H:%M')}\n", tag)
        self.chat_widget.insert("end", text.strip() + "\n", "body")
        self.chat_widget.configure(state="disabled")
        self.chat_widget.see("end")

    def _load_session_history(self) -> None:
        if self.chat_widget is None:
            return
        self.chat_widget.configure(state="normal")
        self.chat_widget.delete("1.0", "end")
        self.chat_widget.configure(state="disabled")
        messages = self.runtime.memory.recent_messages(self.runtime.agent.session_id, limit=80)
        if not messages:
            self._append_chat("SKYNET", "Systems nominal. How can I assist you?")
            return
        for message in messages:
            role = str(message.get("role", "system"))
            self._append_chat("YOU" if role == "user" else "SKYNET" if role == "assistant" else "SYSTEM", str(message.get("content", "")))

    def _entry_return(self, event) -> str | None:
        if event.state & 0x0001:
            return None
        self._send()
        return "break"

    def _prefill(self, text: str) -> None:
        if self.entry_widget is None:
            self._navigate("chat")
        if self.entry_widget is not None:
            self.entry_widget.delete("1.0", "end")
            self.entry_widget.insert("1.0", text)
            self.entry_widget.focus_set()

    def _send(self) -> None:
        if self.busy or self.entry_widget is None:
            return
        text = self.entry_widget.get("1.0", "end").strip()
        if not text:
            return
        self.entry_widget.delete("1.0", "end")
        self._append_chat("YOU", text)
        self.busy = True
        self._last_response_started = time.time()
        self._set_busy_state(True)
        self._trace("Mission", "User command accepted")

        def work() -> None:
            try:
                reply = self.runtime.agent.ask(text, self._confirm)
                self.events.put(("reply", reply))
            except Exception as exc:
                self.events.put(("error", f"{type(exc).__name__}: {exc}"))
            finally:
                self.events.put(("idle", None))

        threading.Thread(target=work, daemon=True, name="skynet-premium-chat").start()

    def _confirm(self, prompt: str) -> bool:
        done = threading.Event()
        result = {"value": False}

        def ask() -> None:
            result["value"] = messagebox.askyesno("SKYNET · Permission required", prompt, parent=self.root)
            done.set()

        self.root.after(0, ask)
        done.wait()
        return bool(result["value"])

    def _set_busy_state(self, busy: bool) -> None:
        self.busy = busy
        self.top_activity.configure(text="●  EXECUTING" if busy else "●  SYSTEMS NOMINAL", fg=PALETTE.amber if busy else PALETTE.green)
        self.footer_status.configure(text="Mission running…" if busy else "Ready")
        if self.core is not None:
            self.core.set_mode("stopped" if self.runtime.control.engaged() else "thinking" if busy else "idle")
        if self.waveform is not None:
            self.waveform.set_active(busy)

    # ---------------------------------------------------------------- sessions

    def _switch_session(self, session_id: str) -> None:
        if not session_id or self.busy:
            return
        self.runtime.agent.session_id = session_id
        self.top_session.configure(text=f"SESSION: {session_id[:22].upper()}")
        self._trace("Session", f"Switched to {session_id[:24]}")
        if self.page not in {"home", "chat"}:
            self._navigate("chat")
        else:
            self._load_session_history()

    def _new_session(self) -> None:
        title = simpledialog.askstring("New Session", "Session title:", parent=self.root)
        if title is None:
            return
        item = self.runtime.sessions.create(title.strip() or "New Session", channel="desktop")
        self._switch_session(str(_field(item, "session_id", "")))

    def _fork_session(self) -> None:
        try:
            item = self.runtime.sessions.fork(self.runtime.agent.session_id)
        except Exception as exc:
            messagebox.showerror("Fork Session", str(exc), parent=self.root)
            return
        self._switch_session(str(_field(item, "session_id", "")))

    def _search_sessions(self) -> None:
        query = simpledialog.askstring("Search Sessions", "Search text:", parent=self.root)
        if not query:
            return
        hits = self.runtime.sessions.search(query, limit=25)
        if not hits:
            messagebox.showinfo("Search Sessions", "No result.", parent=self.root)
            return
        preview = "\n\n".join(f"{hit.get('title', 'Session')}\n{str(hit.get('content', ''))[:220]}" for hit in hits)
        self._show_modal_text("Session Search", preview)

    def _open_selected_session(self) -> None:
        selection = getattr(self, "session_list", None)
        if selection is None:
            return
        indexes = selection.curselection()
        if not indexes:
            return
        index = int(indexes[0])
        if index < len(self.session_ids):
            self._switch_session(self.session_ids[index])

    # ------------------------------------------------------------- automations

    def _new_routine(self) -> None:
        name = simpledialog.askstring("New Routine", "Routine name:", parent=self.root)
        if not name:
            return
        prompt = simpledialog.askstring("New Routine", "Instruction:", parent=self.root)
        if not prompt:
            return
        minutes = simpledialog.askinteger("New Routine", "Interval in minutes (minimum 1):", parent=self.root, minvalue=1, initialvalue=60)
        if minutes is None:
            return
        try:
            self.runtime.routines.create(name, prompt, interval_seconds=max(60, minutes * 60), start_in_seconds=max(60, minutes * 60))
            self._trace("Automation", f"Created: {name}")
            self._navigate("automations")
        except Exception as exc:
            messagebox.showerror("New Routine", str(exc), parent=self.root)

    def _run_due(self) -> None:
        if self.busy:
            return
        self.footer_status.configure(text="Checking due automations…")

        def work() -> None:
            try:
                results = self.runtime.autonomy.run_due()
                self.events.put(("automation", results))
            except Exception as exc:
                self.events.put(("error", f"{type(exc).__name__}: {exc}"))

        threading.Thread(target=work, daemon=True, name="skynet-premium-autonomy").start()

    # --------------------------------------------------------------- windows

    def _scan_windows(self) -> None:
        self.footer_status.configure(text="Inspecting visible Windows applications…")

        def work() -> None:
            try:
                result = self.runtime.windows.list_windows()
                self.events.put(("windows", result))
            except Exception as exc:
                self.events.put(("error", f"{type(exc).__name__}: {exc}"))

        threading.Thread(target=work, daemon=True, name="skynet-premium-windows-scan").start()

    # --------------------------------------------------------------- security

    def _emergency_stop(self) -> None:
        if not messagebox.askyesno("SKYNET · Safe Mode", "Engage the global kill switch and stop consequential tool execution?", parent=self.root):
            return
        self.runtime.control.engage("desktop-user")
        self._trace("Security", "GLOBAL KILL SWITCH ENGAGED")
        self._set_busy_state(False)
        self._navigate("system")

    def _rearm(self) -> None:
        if not messagebox.askyesno("SKYNET · Rearm", "Re-enable governed execution?", parent=self.root):
            return
        self.runtime.control.rearm("desktop-user")
        self._trace("Security", "Governed execution re-armed")
        self._navigate("system")

    # -------------------------------------------------------------- resources

    def _request_resource_snapshot(self) -> None:
        if not self.resource_busy:
            self.resource_busy = True

            def work() -> None:
                try:
                    self.events.put(("resources", self.runtime.profiler.snapshot()))
                finally:
                    self.events.put(("resource_idle", None))

            threading.Thread(target=work, daemon=True, name="skynet-premium-resource-sampler").start()
        self.root.after(5000, self._request_resource_snapshot)

    def _apply_resource_snapshot(self, snap) -> None:
        self.resource_snapshot = snap
        ram_pct = None
        if snap.ram_total_mb and snap.ram_available_mb is not None:
            ram_pct = max(0.0, min(100.0, (snap.ram_total_mb - snap.ram_available_mb) / snap.ram_total_mb * 100))
        gpu_pct = None
        if snap.gpu_memory_total_mb and snap.gpu_memory_used_mb is not None:
            gpu_pct = max(0.0, min(100.0, snap.gpu_memory_used_mb / snap.gpu_memory_total_mb * 100))
        values = {
            "side_cpu": f"{snap.cpu_count} cores",
            "side_ram": f"{ram_pct:.0f}%" if ram_pct is not None else "—",
            "side_gpu": f"{gpu_pct:.0f}%" if gpu_pct is not None else (snap.gpu_name or "—")[:15],
            "side_power": f"{snap.gpu_power_w:.0f} W" if snap.gpu_power_w is not None else "—",
            "home_ram": f"RAM {ram_pct:.0f}%" if ram_pct is not None else "RAM —",
            "home_gpu": f"GPU {gpu_pct:.0f}%" if gpu_pct is not None else "GPU —",
            "home_power": f"PWR {snap.gpu_power_w:.0f}W" if snap.gpu_power_w is not None else "PWR —",
        }
        for key, text in values.items():
            label = self.resource_labels.get(key)
            if label is not None and label.winfo_exists():
                label.configure(text=text)
        if ram_pct is not None and "ram" in self.resource_sparks:
            self.resource_sparks["ram"].push(ram_pct)
        if gpu_pct is not None and "gpu" in self.resource_sparks:
            self.resource_sparks["gpu"].push(gpu_pct)
        if snap.gpu_power_w is not None and "power" in self.resource_sparks:
            self.resource_sparks["power"].push(snap.gpu_power_w)

    # ----------------------------------------------------------------- events

    def _trace(self, source: str, message: str, *, write_queue: bool = True) -> None:
        if write_queue and threading.current_thread() is not threading.main_thread():
            self.events.put(("trace", (source, message)))
            return
        if self.trace_widget is None or not self.trace_widget.winfo_exists():
            return
        prefix = f"{time.strftime('%H:%M:%S')}  "
        if source:
            prefix += f"{source:<10} "
        self.trace_widget.configure(state="normal")
        self.trace_widget.insert("end", prefix + message + "\n")
        lines = int(float(self.trace_widget.index("end-1c").split(".")[0]))
        if lines > 60:
            self.trace_widget.delete("1.0", "12.0")
        self.trace_widget.configure(state="disabled")
        self.trace_widget.see("end")

    def _drain_events(self) -> None:
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "reply":
                    self._append_chat("SKYNET", str(payload))
                    elapsed = time.time() - self._last_response_started if self._last_response_started else 0
                    self._trace("Output", f"Response completed in {elapsed:.1f}s")
                elif kind == "error":
                    self._append_chat("SYSTEM", str(payload))
                    self._trace("Error", str(payload)[:120])
                    self.footer_status.configure(text="Error · see conversation")
                elif kind == "idle":
                    self._set_busy_state(False)
                elif kind == "resources":
                    self._apply_resource_snapshot(payload)
                elif kind == "resource_idle":
                    self.resource_busy = False
                elif kind == "trace":
                    source, message = payload
                    self._trace(str(source), str(message), write_queue=False)
                elif kind == "automation":
                    results = payload or []
                    self._trace("Automation", f"{len(results)} due routine(s) processed")
                    self.footer_status.configure(text=f"Automations · {len(results)} processed")
                    if self.page == "automations":
                        self._navigate("automations")
                elif kind == "windows":
                    self._show_modal_text("Visible Windows", str(payload))
                    self.footer_status.configure(text="Window inspection complete")
        except queue.Empty:
            pass
        self.root.after(80, self._drain_events)

    # ---------------------------------------------------------------- helpers

    def _model_name(self) -> str:
        try:
            return str(self.runtime.router.last_route.model or self.runtime.config.model)
        except Exception:
            return str(self.runtime.config.model)

    @staticmethod
    def _mb(value: int | None) -> str:
        if value is None:
            return "Unavailable"
        if value >= 1024:
            return f"{value / 1024:.1f} GB"
        return f"{value} MB"

    @staticmethod
    def _gpu_text(snap) -> str:
        if snap.gpu_memory_total_mb is None:
            return "Unavailable"
        used = snap.gpu_memory_used_mb or 0
        return f"{used} / {snap.gpu_memory_total_mb} MB"

    def _show_modal_text(self, title: str, body: str) -> None:
        win = tk.Toplevel(self.root)
        win.title(f"SKYNET · {title}")
        win.geometry("820x560")
        win.configure(bg=PALETTE.bg)
        card = HudCard(win, title=title)
        card.pack(fill="both", expand=True, padx=12, pady=12)
        text = self._readonly_text(card.body)
        self._set_text(text, body)
        NeonButton(card.body, "Close", win.destroy).pack(anchor="e", pady=(8, 0))

    def _close(self) -> None:
        try:
            self.runtime.close()
        finally:
            self.root.destroy()


def main() -> None:
    root = tk.Tk()
    PremiumDesktopApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
