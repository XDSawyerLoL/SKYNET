from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from pathlib import Path

from .runtime import Runtime
from .ui import PALETTE, StatusOrb, orb_mode


class DesktopApp:
    """Minimal premium desktop shell for SKYNET.

    The default surface stays intentionally quiet: sessions on the left,
    conversation in the center, and an optional context drawer on the right.
    Advanced product/security information is available on demand instead of
    permanently occupying the main workspace.
    """

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("SKYNET V0.10 — Sovereign Local AI")
        self.root.geometry("1240x800")
        self.root.minsize(980, 640)
        self.root.configure(bg=PALETTE.bg)

        self.runtime = Runtime.create(Path.cwd(), session_id="desktop")
        self.events: queue.Queue[tuple[str, str]] = queue.Queue()
        self.busy = False
        self.autonomy_busy = False
        self.context_visible = False
        self.session_ids: list[str] = []
        self.nav_buttons: dict[str, tk.Button] = {}

        self._configure_style()
        self._build()
        self._refresh_sessions(select_id="desktop")
        self._load_session_history("desktop")
        self._refresh_status()
        self._refresh_routines()
        self._show_context("SKYNET", self._overview_lines(), reveal=False)

        self.root.after(100, self._drain_events)
        self.root.after(1000, self._autonomy_tick)
        self.root.protocol("WM_DELETE_WINDOW", self._close)

    # ---------- visual shell ----------

    def _configure_style(self) -> None:
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

    def _build(self) -> None:
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_workspace()
        self._build_context_drawer()

    def _build_sidebar(self) -> None:
        side = tk.Frame(self.root, bg=PALETTE.sidebar, width=232, highlightthickness=1, highlightbackground=PALETTE.border)
        side.grid(row=0, column=0, sticky="nsw")
        side.grid_propagate(False)
        side.grid_rowconfigure(8, weight=1)
        side.grid_columnconfigure(0, weight=1)
        self.sidebar = side

        brand = tk.Frame(side, bg=PALETTE.sidebar)
        brand.grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 14))
        brand.grid_columnconfigure(1, weight=1)
        self.sidebar_orb = StatusOrb(brand, size=42, bg=PALETTE.sidebar)
        self.sidebar_orb.grid(row=0, column=0, rowspan=2, padx=(0, 10))
        tk.Label(brand, text="SKYNET", bg=PALETTE.sidebar, fg=PALETTE.text, font=("Segoe UI", 14, "bold")).grid(row=0, column=1, sticky="sw")
        tk.Label(brand, text="LOCAL AI", bg=PALETTE.sidebar, fg=PALETTE.muted, font=("Segoe UI", 8)).grid(row=1, column=1, sticky="nw")

        self.new_button = tk.Button(
            side,
            text="＋  Nouvelle conversation",
            command=self._new_session,
            bg=PALETTE.cyan,
            fg="#031018",
            activebackground="#55D8FF",
            activeforeground="#031018",
            relief="flat",
            bd=0,
            font=("Segoe UI", 10, "bold"),
            cursor="hand2",
            padx=12,
            pady=10,
        )
        self.new_button.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 14))

        nav = tk.Frame(side, bg=PALETTE.sidebar)
        nav.grid(row=2, column=0, sticky="ew", padx=10)
        for key, label in (
            ("chat", "Chat"),
            ("memory", "Mémoire"),
            ("automations", "Automatisations"),
            ("tools", "Outils"),
            ("settings", "Réglages"),
        ):
            button = tk.Button(
                nav,
                text=label,
                anchor="w",
                command=lambda item=key: self._navigate(item),
                bg=PALETTE.sidebar,
                fg=PALETTE.muted,
                activebackground=PALETTE.panel_alt,
                activeforeground=PALETTE.text,
                relief="flat",
                bd=0,
                cursor="hand2",
                font=("Segoe UI", 10),
                padx=12,
                pady=8,
            )
            button.pack(fill="x", pady=1)
            self.nav_buttons[key] = button
        self._set_nav_active("chat")

        tk.Frame(side, bg=PALETTE.border, height=1).grid(row=3, column=0, sticky="ew", padx=18, pady=14)
        tk.Label(side, text="SESSIONS", bg=PALETTE.sidebar, fg=PALETTE.faint, font=("Segoe UI", 8, "bold")).grid(row=4, column=0, sticky="w", padx=20)

        session_holder = tk.Frame(side, bg=PALETTE.sidebar)
        session_holder.grid(row=5, column=0, sticky="nsew", padx=10, pady=(6, 0))
        session_holder.grid_rowconfigure(0, weight=1)
        session_holder.grid_columnconfigure(0, weight=1)
        self.session_list = tk.Listbox(
            session_holder,
            bg=PALETTE.sidebar,
            fg=PALETTE.muted,
            selectbackground=PALETTE.panel_alt,
            selectforeground=PALETTE.text,
            activestyle="none",
            highlightthickness=0,
            bd=0,
            exportselection=False,
            font=("Segoe UI", 9),
        )
        self.session_list.grid(row=0, column=0, sticky="nsew")
        self.session_list.bind("<<ListboxSelect>>", lambda _event: self._switch_session_from_list())
        scroll = ttk.Scrollbar(session_holder, orient="vertical", command=self.session_list.yview, style="Sky.Vertical.TScrollbar")
        scroll.grid(row=0, column=1, sticky="ns")
        self.session_list.configure(yscrollcommand=scroll.set)

        session_actions = tk.Frame(side, bg=PALETTE.sidebar)
        session_actions.grid(row=6, column=0, sticky="ew", padx=14, pady=8)
        for text, cmd in (("Fork", self._fork_session), ("Rechercher", self._search_sessions)):
            tk.Button(
                session_actions,
                text=text,
                command=cmd,
                bg=PALETTE.panel,
                fg=PALETTE.muted,
                activebackground=PALETTE.panel_alt,
                activeforeground=PALETTE.text,
                relief="flat",
                bd=0,
                cursor="hand2",
                font=("Segoe UI", 8),
                padx=8,
                pady=6,
            ).pack(side="left", expand=True, fill="x", padx=2)

        self.sidebar_status = tk.Label(side, text="●  Local · Prêt", bg=PALETTE.sidebar, fg=PALETTE.green, font=("Segoe UI", 9))
        self.sidebar_status.grid(row=9, column=0, sticky="w", padx=20, pady=(8, 18))

    def _build_workspace(self) -> None:
        main = tk.Frame(self.root, bg=PALETTE.bg)
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_rowconfigure(1, weight=1)
        main.grid_columnconfigure(0, weight=1)
        self.main = main

        top = tk.Frame(main, bg=PALETTE.bg, height=64)
        top.grid(row=0, column=0, sticky="ew", padx=24, pady=(12, 0))
        top.grid_columnconfigure(1, weight=1)
        self.main_orb = StatusOrb(top, size=48, bg=PALETTE.bg)
        self.main_orb.grid(row=0, column=0, rowspan=2, padx=(0, 10))
        self.session_title = tk.Label(top, text="SKYNET", bg=PALETTE.bg, fg=PALETTE.text, font=("Segoe UI", 13, "bold"))
        self.session_title.grid(row=0, column=1, sticky="sw")
        self.session_subtitle = tk.Label(top, text="Compagnon IA souverain", bg=PALETTE.bg, fg=PALETTE.muted, font=("Segoe UI", 8))
        self.session_subtitle.grid(row=1, column=1, sticky="nw")

        self.status = tk.Label(top, text="", bg=PALETTE.panel, fg=PALETTE.green, font=("Segoe UI", 9), padx=10, pady=6)
        self.status.grid(row=0, column=2, rowspan=2, padx=(8, 6))
        self.context_button = tk.Button(
            top,
            text="Contexte  ›",
            command=self._toggle_context,
            bg=PALETTE.bg,
            fg=PALETTE.muted,
            activebackground=PALETTE.panel,
            activeforeground=PALETTE.text,
            relief="flat",
            bd=0,
            cursor="hand2",
            font=("Segoe UI", 9),
            padx=8,
            pady=6,
        )
        self.context_button.grid(row=0, column=3, rowspan=2)

        conversation = tk.Frame(main, bg=PALETTE.bg)
        conversation.grid(row=1, column=0, sticky="nsew", padx=24, pady=(8, 0))
        conversation.grid_rowconfigure(0, weight=1)
        conversation.grid_columnconfigure(0, weight=1)

        self.chat = tk.Text(
            conversation,
            wrap="word",
            state="disabled",
            bg=PALETTE.bg,
            fg=PALETTE.text,
            insertbackground=PALETTE.text,
            selectbackground=PALETTE.cyan_soft,
            highlightthickness=0,
            bd=0,
            padx=34,
            pady=22,
            font=("Segoe UI", 10),
            spacing1=2,
            spacing3=8,
        )
        self.chat.grid(row=0, column=0, sticky="nsew")
        chat_scroll = ttk.Scrollbar(conversation, orient="vertical", command=self.chat.yview, style="Sky.Vertical.TScrollbar")
        chat_scroll.grid(row=0, column=1, sticky="ns")
        self.chat.configure(yscrollcommand=chat_scroll.set)
        self.chat.tag_configure("who_user", foreground=PALETTE.muted, font=("Segoe UI", 8, "bold"), spacing1=14)
        self.chat.tag_configure("who_skynet", foreground=PALETTE.cyan, font=("Segoe UI", 8, "bold"), spacing1=14)
        self.chat.tag_configure("who_system", foreground=PALETTE.faint, font=("Segoe UI", 8, "bold"), spacing1=12)
        self.chat.tag_configure("body_user", foreground=PALETTE.text, lmargin1=18, lmargin2=18, rmargin=46)
        self.chat.tag_configure("body_skynet", foreground="#CFE0EA", lmargin1=18, lmargin2=18, rmargin=46)
        self.chat.tag_configure("body_system", foreground=PALETTE.muted, lmargin1=18, lmargin2=18, rmargin=46)

        composer = tk.Frame(main, bg=PALETTE.bg)
        composer.grid(row=2, column=0, sticky="ew", padx=32, pady=(12, 24))
        composer.grid_columnconfigure(0, weight=1)
        input_shell = tk.Frame(composer, bg=PALETTE.panel, highlightthickness=1, highlightbackground=PALETTE.border)
        input_shell.grid(row=0, column=0, sticky="ew")
        input_shell.grid_columnconfigure(0, weight=1)
        self.entry = tk.Text(
            input_shell,
            height=3,
            wrap="word",
            bg=PALETTE.panel,
            fg=PALETTE.text,
            insertbackground=PALETTE.cyan,
            selectbackground=PALETTE.cyan_soft,
            relief="flat",
            bd=0,
            highlightthickness=0,
            font=("Segoe UI", 10),
            padx=14,
            pady=12,
        )
        self.entry.grid(row=0, column=0, sticky="ew")
        self.entry.bind("<Return>", self._entry_return)
        self.send_button = tk.Button(
            input_shell,
            text="Envoyer  ↗",
            command=self._send,
            bg=PALETTE.cyan,
            fg="#031018",
            activebackground="#55D8FF",
            activeforeground="#031018",
            relief="flat",
            bd=0,
            cursor="hand2",
            font=("Segoe UI", 9, "bold"),
            padx=12,
            pady=9,
        )
        self.send_button.grid(row=0, column=1, padx=(8, 10), pady=10, sticky="s")
        tk.Label(composer, text="Entrée pour envoyer · Maj+Entrée pour une nouvelle ligne", bg=PALETTE.bg, fg=PALETTE.faint, font=("Segoe UI", 7)).grid(row=1, column=0, sticky="w", padx=4, pady=(5, 0))

    def _build_context_drawer(self) -> None:
        drawer = tk.Frame(self.root, bg=PALETTE.sidebar, width=310, highlightthickness=1, highlightbackground=PALETTE.border)
        drawer.grid_rowconfigure(2, weight=1)
        drawer.grid_columnconfigure(0, weight=1)
        drawer.grid_propagate(False)
        self.context_drawer = drawer

        header = tk.Frame(drawer, bg=PALETTE.sidebar)
        header.grid(row=0, column=0, sticky="ew", padx=18, pady=(20, 10))
        header.grid_columnconfigure(0, weight=1)
        self.context_title = tk.Label(header, text="Contexte", bg=PALETTE.sidebar, fg=PALETTE.text, font=("Segoe UI", 12, "bold"))
        self.context_title.grid(row=0, column=0, sticky="w")
        tk.Button(header, text="×", command=self._toggle_context, bg=PALETTE.sidebar, fg=PALETTE.muted, activebackground=PALETTE.panel, activeforeground=PALETTE.text, relief="flat", bd=0, cursor="hand2", font=("Segoe UI", 12)).grid(row=0, column=1)

        self.context_state = tk.Label(drawer, text="", bg=PALETTE.sidebar, fg=PALETTE.green, font=("Segoe UI", 9), anchor="w")
        self.context_state.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 10))

        self.context_detail = tk.Text(
            drawer,
            wrap="word",
            state="disabled",
            bg=PALETTE.sidebar,
            fg=PALETTE.muted,
            highlightthickness=0,
            bd=0,
            font=("Segoe UI", 9),
            padx=18,
            pady=8,
            spacing3=5,
        )
        self.context_detail.grid(row=2, column=0, sticky="nsew")

        controls = tk.Frame(drawer, bg=PALETTE.sidebar)
        controls.grid(row=3, column=0, sticky="ew", padx=14, pady=14)
        for text, cmd in (
            ("Nouvelle routine", self._new_routine),
            ("Exécuter les routines dues", self._run_due_manual),
            ("État avancé", self._show_evolution),
        ):
            tk.Button(controls, text=text, command=cmd, bg=PALETTE.panel, fg=PALETTE.muted, activebackground=PALETTE.panel_alt, activeforeground=PALETTE.text, relief="flat", bd=0, cursor="hand2", font=("Segoe UI", 9), padx=10, pady=8).pack(fill="x", pady=2)

        self.stop_button = tk.Button(controls, text="Arrêt global", command=self._emergency_stop, bg="#241013", fg=PALETTE.red, activebackground="#35171B", activeforeground="#FF8890", relief="flat", bd=0, cursor="hand2", font=("Segoe UI", 9, "bold"), padx=10, pady=8)
        self.stop_button.pack(fill="x", pady=(10, 2))
        self.rearm_button = tk.Button(controls, text="Réarmer SKYNET", command=self._rearm, bg=PALETTE.panel, fg=PALETTE.green, activebackground=PALETTE.panel_alt, activeforeground=PALETTE.green, relief="flat", bd=0, cursor="hand2", font=("Segoe UI", 9), padx=10, pady=8)
        self.rearm_button.pack(fill="x", pady=2)

    def _set_nav_active(self, key: str) -> None:
        for name, button in self.nav_buttons.items():
            if name == key:
                button.configure(bg=PALETTE.panel_alt, fg=PALETTE.text)
            else:
                button.configure(bg=PALETTE.sidebar, fg=PALETTE.muted)

    def _toggle_context(self) -> None:
        self.context_visible = not self.context_visible
        if self.context_visible:
            self.context_drawer.grid(row=0, column=2, sticky="nse", padx=0)
            self.context_button.configure(text="Contexte  ‹")
        else:
            self.context_drawer.grid_forget()
            self.context_button.configure(text="Contexte  ›")

    def _show_context(self, title: str, lines: list[str], *, reveal: bool = True) -> None:
        self.context_title.configure(text=title)
        self.context_detail.configure(state="normal")
        self.context_detail.delete("1.0", "end")
        self.context_detail.insert("1.0", "\n\n".join(lines))
        self.context_detail.configure(state="disabled")
        if reveal and not self.context_visible:
            self._toggle_context()

    # ---------- navigation ----------

    def _navigate(self, key: str) -> None:
        self._set_nav_active(key)
        if key == "chat":
            if self.context_visible:
                self._toggle_context()
            self.entry.focus_set()
            return
        if key == "memory":
            memories = self.runtime.memory.list_memories(limit=12)
            lines = [f"Mémoire durable · {len(memories)} éléments récents"]
            lines.extend(f"• {item}" for item in memories[:10])
            if not memories:
                lines.append("Aucune mémoire durable enregistrée.")
            self._show_context("Mémoire", lines)
            return
        if key == "automations":
            routines = self.runtime.routines.list()
            lines = [f"{len(routines)} routine(s) configurée(s)"]
            lines.extend(f"• {self.runtime.routines.render(item)}" for item in routines[:12])
            if not routines:
                lines.append("Aucune automatisation. Utilise « Nouvelle routine » pour en créer une.")
            self._show_context("Automatisations", lines)
            return
        if key == "tools":
            integrations = self.runtime.integrations.list(enabled_only=True)
            lines = [
                f"{len(self.runtime.tools.schemas())} outils exposés",
                f"{len(integrations)} intégration(s) active(s)",
                f"Browser · {self.runtime.browser.state().mode}",
                f"Skills approuvés · {len(self.runtime.skills.list_skills())}",
                "Les actions sensibles restent soumises au Mandate + Policy + PermissionGate.",
            ]
            self._show_context("Outils", lines)
            return
        if key == "settings":
            route = self.runtime.router.last_route.model
            lines = [
                f"Modèle actif · {route}",
                f"Workspace · {self.runtime.config.workspace}",
                f"Données locales · {self.runtime.config.data_dir}",
                f"Autonomie · toutes les {self.runtime.config.autonomy_poll_seconds}s",
                f"Kill-switch · {'ENGAGÉ' if self.runtime.control.engaged() else 'désengagé'}",
                "Les réglages avancés restent disponibles dans les consoles skynet-admin / skynet-trust / skynet-evolve.",
            ]
            self._show_context("Réglages", lines)

    # ---------- conversation ----------

    def _append(self, who: str, text: str) -> None:
        key = who.strip().lower()
        if key in {"you", "user", "toi"}:
            who_tag, body_tag, label = "who_user", "body_user", "VOUS"
        elif key == "skynet":
            who_tag, body_tag, label = "who_skynet", "body_skynet", "SKYNET"
        else:
            who_tag, body_tag, label = "who_system", "body_system", who.upper()
        self.chat.configure(state="normal")
        self.chat.insert("end", f"{label}\n", who_tag)
        self.chat.insert("end", f"{text.strip()}\n", body_tag)
        self.chat.configure(state="disabled")
        self.chat.see("end")

    def _clear_chat(self) -> None:
        self.chat.configure(state="normal")
        self.chat.delete("1.0", "end")
        self.chat.configure(state="disabled")

    def _entry_return(self, event) -> str | None:
        if event.state & 0x0001:  # Shift+Enter
            return None
        self._send()
        return "break"

    def _send(self) -> None:
        if self.busy:
            return
        text = self.entry.get("1.0", "end").strip()
        if not text:
            return
        self.entry.delete("1.0", "end")
        self._append("YOU", text)
        self.busy = True
        self._refresh_status()

        def work() -> None:
            try:
                reply = self.runtime.agent.ask(text, self._confirm)
                self.events.put(("reply", reply))
            except Exception as exc:
                self.events.put(("error", f"{type(exc).__name__}: {exc}"))
            finally:
                self.events.put(("idle", ""))

        threading.Thread(target=work, daemon=True, name="skynet-desktop-chat").start()

    # ---------- sessions ----------

    def _refresh_sessions(self, select_id: str | None = None) -> None:
        sessions = self.runtime.sessions.list(limit=100)
        wanted = select_id or self.runtime.agent.session_id
        self.session_ids = []
        self.session_list.delete(0, "end")
        selected_index = None
        for index, item in enumerate(sessions):
            self.session_ids.append(item.session_id)
            self.session_list.insert("end", item.title)
            if item.session_id == wanted:
                selected_index = index
        if selected_index is not None:
            self.session_list.selection_clear(0, "end")
            self.session_list.selection_set(selected_index)
            self.session_list.see(selected_index)
        self._update_session_heading()

    def _update_session_heading(self) -> None:
        current = self.runtime.agent.session_id
        title = "SKYNET"
        for item in self.runtime.sessions.list(limit=100):
            if item.session_id == current:
                title = item.title
                break
        self.session_title.configure(text=title)
        self.session_subtitle.configure(text="Compagnon IA souverain · session locale")

    def _load_session_history(self, session_id: str) -> None:
        self._clear_chat()
        messages = self.runtime.memory.recent_messages(session_id, limit=100)
        if not messages:
            self._append("SKYNET", "Comment puis-je t’aider ?")
            return
        for message in messages:
            role = str(message.get("role", "message")).upper()
            self._append("YOU" if role == "USER" else "SKYNET" if role == "ASSISTANT" else role, str(message.get("content", "")))

    def _switch_session_from_list(self) -> None:
        selection = self.session_list.curselection()
        if not selection or self.busy:
            return
        index = int(selection[0])
        if index >= len(self.session_ids):
            return
        session_id = self.session_ids[index]
        if session_id == self.runtime.agent.session_id:
            return
        self.runtime.agent.session_id = session_id
        self._load_session_history(session_id)
        self._update_session_heading()
        self._refresh_status()
        self._set_nav_active("chat")

    def _new_session(self) -> None:
        title = simpledialog.askstring("Nouvelle conversation", "Nom de la conversation :", parent=self.root)
        if title is None:
            return
        item = self.runtime.sessions.create(title.strip() or "Nouvelle conversation", channel="desktop")
        self.runtime.agent.session_id = item.session_id
        self._refresh_sessions(select_id=item.session_id)
        self._load_session_history(item.session_id)
        self._set_nav_active("chat")
        if self.context_visible:
            self._toggle_context()
        self.entry.focus_set()
        self._refresh_status()

    def _fork_session(self) -> None:
        current = self.runtime.agent.session_id
        try:
            item = self.runtime.sessions.fork(current)
        except Exception as exc:
            messagebox.showerror("Fork session", str(exc), parent=self.root)
            return
        self.runtime.agent.session_id = item.session_id
        self._refresh_sessions(select_id=item.session_id)
        self._load_session_history(item.session_id)
        self._append("SYSTEM", "Branche indépendante créée depuis cette conversation.")
        self._refresh_status()

    def _search_sessions(self) -> None:
        query = simpledialog.askstring("Recherche", "Rechercher dans les conversations :", parent=self.root)
        if not query:
            return
        hits = self.runtime.sessions.search(query, limit=30)
        if not hits:
            self._show_context("Recherche", ["Aucun résultat."])
            return
        lines = [f"{hit['title']}\n{hit['role']} · {' '.join(str(hit['content']).split())[:240]}" for hit in hits]
        self._show_context(f"Recherche · {query}", lines)

    # ---------- permissions, automation, trust ----------

    def _confirm(self, message: str) -> bool:
        done = threading.Event()
        result = {"value": False}

        def ask() -> None:
            result["value"] = messagebox.askyesno("Autorisation SKYNET", message, parent=self.root)
            done.set()

        self.root.after(0, ask)
        done.wait()
        return bool(result["value"])

    def _new_routine(self) -> None:
        name = simpledialog.askstring("Nouvelle routine", "Nom :", parent=self.root)
        if not name:
            return
        minutes = simpledialog.askinteger("Nouvelle routine", "Toutes les combien de minutes ?", parent=self.root, minvalue=1, initialvalue=60)
        if minutes is None:
            return
        prompt = simpledialog.askstring("Nouvelle routine", "Instruction :", parent=self.root)
        if not prompt:
            return
        if not messagebox.askyesno("Nouvelle routine", f"Créer « {name.strip()} » toutes les {minutes} minutes pour cette session ?", parent=self.root):
            return
        try:
            self.runtime.routines.create(name.strip(), prompt.strip(), minutes * 60, start_in_seconds=minutes * 60, session_id=self.runtime.agent.session_id)
            self._refresh_routines()
            self._navigate("automations")
        except Exception as exc:
            messagebox.showerror("Routine", str(exc), parent=self.root)

    def _run_due_manual(self) -> None:
        if self.autonomy_busy or self.runtime.control.engaged():
            if self.runtime.control.engaged():
                self._show_context("Contrôle", ["Routine non lancée : arrêt global engagé."])
            return
        self._start_autonomy()

    def _start_autonomy(self) -> None:
        self.autonomy_busy = True
        self._refresh_status()

        def work() -> None:
            try:
                results = self.runtime.autonomy.run_due()
                if not results:
                    self.events.put(("system", "Aucune routine due."))
                for routine, status, reply in results:
                    self.events.put(("routine", f"{routine.name} [{status}]\n{reply}"))
            except Exception as exc:
                self.events.put(("error", f"Autonomie: {type(exc).__name__}: {exc}"))
            finally:
                self.events.put(("autonomy_idle", ""))

        threading.Thread(target=work, daemon=True, name="skynet-desktop-autonomy").start()

    def _autonomy_tick(self) -> None:
        if not self.runtime.control.engaged() and not self.autonomy_busy and self.runtime.routines.due():
            self._start_autonomy()
        self.root.after(max(10, self.runtime.config.autonomy_poll_seconds) * 1000, self._autonomy_tick)

    def _refresh_routines(self) -> None:
        if self.context_title.cget("text") == "Automatisations":
            self._navigate("automations")

    def _overview_lines(self) -> list[str]:
        route = self.runtime.router.last_route.model
        return [
            f"Modèle · {route}",
            f"Session · {self.runtime.agent.session_id}",
            f"Autonomie · {'active' if not self.runtime.control.engaged() else 'bloquée'}",
            "Les détails apparaissent ici uniquement lorsqu’ils sont utiles.",
        ]

    def _show_evolution(self) -> None:
        deployed = self.runtime.deployments.get("reasoning-model")
        deployment = "baseline" if deployed is None else f"{deployed.active} [{deployed.status}]"
        hardware = self.runtime.profiler.snapshot()
        lab = self.runtime.lab.choose()
        lines = [
            f"Deployment · {deployment}",
            f"Sessions · {len(self.runtime.sessions.list(include_archived=True, limit=500))}",
            f"Intégrations · {len(self.runtime.integrations.list(enabled_only=True))}/{len(self.runtime.integrations.list())}",
            f"Outils · {len(self.runtime.tools.schemas())}",
            f"Skills · {len(self.runtime.skills.list_skills())}",
            f"Swarm runs · {len(self.runtime.swarm.recent(100))}",
            f"Browser · {self.runtime.browser.state().mode}",
            f"Lab · {lab.name} — {lab.reason}",
            f"RAM disponible · {hardware.ram_available_mb or '?'} MB",
            f"GPU · {hardware.gpu_name or 'non détecté'}",
        ]
        self._show_context("État avancé", lines)

    def _emergency_stop(self) -> None:
        if not messagebox.askyesno("Arrêt global SKYNET", "Bloquer immédiatement tous les appels d’outils et l’autonomie jusqu’au réarmement explicite ?", parent=self.root):
            return
        self.runtime.control.engage("desktop emergency stop")
        self._show_context("Contrôle", ["ARRÊT GLOBAL ENGAGÉ", "Les appels d’outils sont bloqués sous le LLM."])
        self._refresh_status()

    def _rearm(self) -> None:
        if not messagebox.askyesno("Réarmer SKYNET", "Retirer le kill-switch global ? Les mandats et permissions normales resteront actifs.", parent=self.root):
            return
        self.runtime.control.release()
        self._show_context("Contrôle", ["SKYNET réarmé.", "Mandats, politiques et permissions normales restent applicables."])
        self._refresh_status()

    # ---------- event loop ----------

    def _drain_events(self) -> None:
        try:
            while True:
                kind, text = self.events.get_nowait()
                if kind == "reply":
                    self._append("SKYNET", text)
                    self._refresh_sessions(select_id=self.runtime.agent.session_id)
                elif kind == "routine":
                    self._append("ROUTINE", text)
                elif kind == "system":
                    self._append("SYSTEM", text)
                elif kind == "error":
                    self._append("ERROR", text)
                elif kind == "idle":
                    self.busy = False
                    self._refresh_status()
                elif kind == "autonomy_idle":
                    self.autonomy_busy = False
                    self._refresh_status()
                    self._refresh_routines()
        except queue.Empty:
            pass
        self.root.after(100, self._drain_events)

    def _refresh_status(self) -> None:
        stopped = self.runtime.control.engaged()
        mode = orb_mode(busy=self.busy, autonomy_busy=self.autonomy_busy, stopped=stopped)
        self.main_orb.set_mode(mode)
        self.sidebar_orb.set_mode(mode)

        if stopped:
            text, color = "●  Arrêt global", PALETTE.red
            side_text = "●  Bloqué"
        elif self.busy:
            text, color = "●  Réflexion", PALETTE.cyan
            side_text = "●  Réflexion"
        elif self.autonomy_busy:
            text, color = "●  Action", PALETTE.amber
            side_text = "●  Action"
        else:
            text, color = "●  Local · Prêt", PALETTE.green
            side_text = "●  Local · Prêt"
        self.status.configure(text=text, fg=color)
        self.sidebar_status.configure(text=side_text, fg=color)
        self.context_state.configure(text=text, fg=color)
        self.send_button.configure(state="disabled" if self.busy else "normal")
        self.stop_button.configure(state="disabled" if stopped else "normal")
        self.rearm_button.configure(state="normal" if stopped else "disabled")

    def _close(self) -> None:
        if self.busy or self.autonomy_busy:
            if not messagebox.askyesno("Quitter SKYNET", "Une tâche est active. Quitter quand même ?", parent=self.root):
                return
        self.runtime.close()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    DesktopApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
