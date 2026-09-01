from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from pathlib import Path

from .runtime import Runtime


class DesktopApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("SKYNET V0.9 — Sovereign Local AI")
        self.root.geometry("1180x760")
        self.runtime = Runtime.create(Path.cwd(), session_id="desktop")
        self.events: queue.Queue[tuple[str, str]] = queue.Queue()
        self.busy = False
        self.autonomy_busy = False
        self.session_display_to_id: dict[str, str] = {}
        self._build()
        self._refresh_sessions(select_id="desktop")
        self._refresh_status()
        self._refresh_routines()
        self.root.after(100, self._drain_events)
        self.root.after(1000, self._autonomy_tick)
        self.root.protocol("WM_DELETE_WINDOW", self._close)

    def _build(self) -> None:
        outer = ttk.Frame(self.root, padding=10)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=3)
        outer.columnconfigure(1, weight=1)
        outer.rowconfigure(1, weight=1)

        title = ttk.Label(outer, text="SKYNET V0.9 — Product Convergence", font=("Segoe UI", 18, "bold"))
        title.grid(row=0, column=0, sticky="w")
        self.status = ttk.Label(outer, text="")
        self.status.grid(row=0, column=1, sticky="e")

        chat_frame = ttk.Frame(outer)
        chat_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 10), pady=(10, 0))
        chat_frame.rowconfigure(1, weight=1)
        chat_frame.columnconfigure(0, weight=1)

        session_bar = ttk.Frame(chat_frame)
        session_bar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        session_bar.columnconfigure(0, weight=1)
        self.session_combo = ttk.Combobox(session_bar, state="readonly")
        self.session_combo.grid(row=0, column=0, sticky="ew")
        self.session_combo.bind("<<ComboboxSelected>>", lambda _event: self._switch_session())
        ttk.Button(session_bar, text="Nouvelle", command=self._new_session).grid(row=0, column=1, padx=(6, 0))
        ttk.Button(session_bar, text="Fork", command=self._fork_session).grid(row=0, column=2, padx=(6, 0))
        ttk.Button(session_bar, text="Rechercher", command=self._search_sessions).grid(row=0, column=3, padx=(6, 0))

        self.chat = tk.Text(chat_frame, wrap="word", state="disabled", font=("Segoe UI", 10))
        self.chat.grid(row=1, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(chat_frame, orient="vertical", command=self.chat.yview)
        scroll.grid(row=1, column=1, sticky="ns")
        self.chat.configure(yscrollcommand=scroll.set)

        input_row = ttk.Frame(chat_frame)
        input_row.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        input_row.columnconfigure(0, weight=1)
        self.entry = ttk.Entry(input_row)
        self.entry.grid(row=0, column=0, sticky="ew")
        self.entry.bind("<Return>", lambda _event: self._send())
        ttk.Button(input_row, text="Envoyer", command=self._send).grid(row=0, column=1, padx=(8, 0))

        side = ttk.LabelFrame(outer, text="Autonomie, produit & confiance", padding=8)
        side.grid(row=1, column=1, sticky="nsew", pady=(10, 0))
        side.rowconfigure(1, weight=1)
        side.columnconfigure(0, weight=1)

        ttk.Label(side, text="Routines").grid(row=0, column=0, sticky="w")
        self.routines = tk.Listbox(side, height=10)
        self.routines.grid(row=1, column=0, sticky="nsew", pady=(4, 8))

        form = ttk.Frame(side)
        form.grid(row=2, column=0, sticky="ew")
        form.columnconfigure(1, weight=1)
        ttk.Label(form, text="Nom").grid(row=0, column=0, sticky="w")
        self.routine_name = ttk.Entry(form)
        self.routine_name.grid(row=0, column=1, sticky="ew", padx=(6, 0))
        ttk.Label(form, text="Toutes les (min)").grid(row=1, column=0, sticky="w")
        self.routine_minutes = ttk.Entry(form)
        self.routine_minutes.insert(0, "60")
        self.routine_minutes.grid(row=1, column=1, sticky="ew", padx=(6, 0))
        ttk.Label(form, text="Instruction").grid(row=2, column=0, sticky="nw")
        self.routine_prompt = tk.Text(form, height=4, wrap="word")
        self.routine_prompt.grid(row=2, column=1, sticky="ew", padx=(6, 0))
        ttk.Button(form, text="Ajouter à cette session", command=self._add_routine).grid(row=3, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Button(form, text="Exécuter les routines dues", command=self._run_due_manual).grid(row=4, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        ttk.Button(form, text="État produit / évolution", command=self._show_evolution).grid(row=5, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        ttk.Separator(form, orient="horizontal").grid(row=6, column=0, columnspan=2, sticky="ew", pady=8)
        ttk.Button(form, text="ARRÊT GLOBAL", command=self._emergency_stop).grid(row=7, column=0, columnspan=2, sticky="ew")
        ttk.Button(form, text="Réarmer SKYNET", command=self._rearm).grid(row=8, column=0, columnspan=2, sticky="ew", pady=(6, 0))

        self._append("SYSTEM", "SKYNET V0.9 démarré. Sessions, skills progressifs, browser local, intégrations, channels et multi-agent hiérarchique complètent Trust & Resilience.")

    def _append(self, who: str, text: str) -> None:
        self.chat.configure(state="normal")
        self.chat.insert("end", f"\n{who} > {text}\n")
        self.chat.configure(state="disabled")
        self.chat.see("end")

    def _clear_chat(self) -> None:
        self.chat.configure(state="normal")
        self.chat.delete("1.0", "end")
        self.chat.configure(state="disabled")

    def _refresh_sessions(self, select_id: str | None = None) -> None:
        sessions = self.runtime.sessions.list(limit=100)
        self.session_display_to_id.clear()
        values: list[str] = []
        selected_display = None
        for item in sessions:
            project = f" [{item.project}]" if item.project else ""
            display = f"{item.title}{project} · {item.session_id}"
            values.append(display)
            self.session_display_to_id[display] = item.session_id
            if item.session_id == (select_id or self.runtime.agent.session_id):
                selected_display = display
        self.session_combo["values"] = values
        if selected_display:
            self.session_combo.set(selected_display)

    def _load_session_history(self, session_id: str) -> None:
        self._clear_chat()
        for message in self.runtime.memory.recent_messages(session_id, limit=100):
            role = str(message.get("role", "message")).upper()
            self._append("YOU" if role == "USER" else "SKYNET" if role == "ASSISTANT" else role, str(message.get("content", "")))

    def _switch_session(self) -> None:
        selected = self.session_combo.get()
        session_id = self.session_display_to_id.get(selected)
        if not session_id or self.busy:
            return
        self.runtime.agent.session_id = session_id
        self._load_session_history(session_id)
        self._refresh_status()

    def _new_session(self) -> None:
        title = simpledialog.askstring("Nouvelle session", "Titre de la session :", parent=self.root)
        if title is None:
            return
        title = title.strip() or "Nouvelle session"
        item = self.runtime.sessions.create(title, channel="desktop")
        self.runtime.agent.session_id = item.session_id
        self._refresh_sessions(select_id=item.session_id)
        self._clear_chat()
        self._append("SYSTEM", f"Nouvelle session : {item.title}")
        self._refresh_status()

    def _fork_session(self) -> None:
        current = self.runtime.agent.session_id
        try:
            item = self.runtime.sessions.fork(current)
        except Exception as exc:
            messagebox.showerror("Fork session", str(exc)); return
        self.runtime.agent.session_id = item.session_id
        self._refresh_sessions(select_id=item.session_id)
        self._load_session_history(item.session_id)
        self._append("SYSTEM", "Session forkée : l'historique a été copié, la suite évolue indépendamment.")
        self._refresh_status()

    def _search_sessions(self) -> None:
        query = simpledialog.askstring("Recherche historique", "Texte à rechercher dans les conversations :", parent=self.root)
        if not query:
            return
        hits = self.runtime.sessions.search(query, limit=30)
        if not hits:
            self._append("HISTORY", "Aucun résultat."); return
        lines = [f"{hit['title']} [{hit['session_id']}] · {hit['role']}: {' '.join(str(hit['content']).split())[:220]}" for hit in hits]
        self._append("HISTORY", "\n".join(lines))

    def _confirm(self, message: str) -> bool:
        done = threading.Event()
        result = {"value": False}

        def ask() -> None:
            result["value"] = messagebox.askyesno("Autorisation SKYNET", message, parent=self.root)
            done.set()

        self.root.after(0, ask)
        done.wait()
        return bool(result["value"])

    def _emergency_stop(self) -> None:
        if not messagebox.askyesno("Arrêt global SKYNET", "Bloquer immédiatement tous les appels d'outils et l'autonomie jusqu'à réarmement explicite ?"):
            return
        self.runtime.control.engage("desktop emergency stop")
        self._append("CONTROL", "ARRÊT GLOBAL ENGAGÉ. Les appels d'outils sont bloqués sous le LLM.")
        self._refresh_status()

    def _rearm(self) -> None:
        if not messagebox.askyesno("Réarmer SKYNET", "Retirer le kill-switch global ? Les permissions normales resteront actives."):
            return
        self.runtime.control.release()
        self._append("CONTROL", "Kill-switch retiré explicitement. Les mandats et permissions normales restent applicables.")
        self._refresh_status()

    def _show_evolution(self) -> None:
        deployed = self.runtime.deployments.get("reasoning-model")
        deployment = "baseline" if deployed is None else f"{deployed.active} [{deployed.status}]"
        hardware = self.runtime.profiler.snapshot()
        lab = self.runtime.lab.choose()
        text = (
            f"Deployment: {deployment}\n"
            f"Sessions: {len(self.runtime.sessions.list(include_archived=True, limit=500))}\n"
            f"Intégrations actives: {len(self.runtime.integrations.list(enabled_only=True))}/{len(self.runtime.integrations.list())}\n"
            f"Outils exposés: {len(self.runtime.tools.schemas())}\n"
            f"Skills approuvés: {len(self.runtime.skills.list_skills())}\n"
            f"Swarm runs: {len(self.runtime.swarm.recent(100))}\n"
            f"Browser: {self.runtime.browser.state().mode}\n"
            f"Telemetry: {len(self.runtime.telemetry.recent(20))} recent\n"
            f"Validation reports: {len(self.runtime.reports.recent(20))} recent\n"
            f"Historical regressions: {len(self.runtime.regression.build(100))}\n"
            f"Lab backend: {lab.name} — {lab.reason}\n"
            f"RAM available: {hardware.ram_available_mb or '?'} MB\n"
            f"GPU: {hardware.gpu_name or 'not detected'}"
        )
        self._append("PRODUCT", text)

    def _send(self) -> None:
        if self.busy:
            return
        text = self.entry.get().strip()
        if not text:
            return
        self.entry.delete(0, "end")
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

        threading.Thread(target=work, daemon=True).start()

    def _add_routine(self) -> None:
        name = self.routine_name.get().strip()
        prompt = self.routine_prompt.get("1.0", "end").strip()
        try:
            minutes = int(self.routine_minutes.get().strip())
            if minutes < 1:
                raise ValueError
        except ValueError:
            messagebox.showerror("Routine", "L’intervalle doit être un nombre entier d’au moins 1 minute."); return
        if not name or not prompt:
            messagebox.showerror("Routine", "Nom et instruction sont obligatoires."); return
        if not messagebox.askyesno("Routine", f"Créer la routine locale '{name}' toutes les {minutes} minutes dans cette session ?"):
            return
        try:
            self.runtime.routines.create(name, prompt, minutes * 60, start_in_seconds=minutes * 60, session_id=self.runtime.agent.session_id)
            self.routine_name.delete(0, "end")
            self.routine_prompt.delete("1.0", "end")
            self._refresh_routines()
        except Exception as exc:
            messagebox.showerror("Routine", str(exc))

    def _run_due_manual(self) -> None:
        if self.autonomy_busy or self.runtime.control.engaged():
            if self.runtime.control.engaged():
                self._append("CONTROL", "Routine non lancée : arrêt global engagé.")
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

        threading.Thread(target=work, daemon=True).start()

    def _autonomy_tick(self) -> None:
        if not self.runtime.control.engaged() and not self.autonomy_busy and self.runtime.routines.due():
            self._start_autonomy()
        self.root.after(max(10, self.runtime.config.autonomy_poll_seconds) * 1000, self._autonomy_tick)

    def _drain_events(self) -> None:
        try:
            while True:
                kind, text = self.events.get_nowait()
                if kind == "reply":
                    self._append("SKYNET", text)
                    self._refresh_sessions(select_id=self.runtime.agent.session_id)
                elif kind == "routine":
                    self._append("ROUTINE", text); self._refresh_routines()
                elif kind == "system":
                    self._append("SYSTEM", text)
                elif kind == "error":
                    self._append("ERROR", text)
                elif kind == "idle":
                    self.busy = False; self._refresh_status()
                elif kind == "autonomy_idle":
                    self.autonomy_busy = False; self._refresh_status(); self._refresh_routines()
        except queue.Empty:
            pass
        self.root.after(100, self._drain_events)

    def _refresh_status(self) -> None:
        route = self.runtime.router.last_route.model
        deployed = self.runtime.deployments.get("reasoning-model")
        mode = deployed.status if deployed else "baseline"
        session = self.runtime.agent.session_id[:16]
        if self.runtime.control.engaged():
            self.status.configure(text=f"{route} • {mode} • {session} • STOP GLOBAL"); return
        flags = []
        if self.busy:
            flags.append("chat")
        if self.autonomy_busy:
            flags.append("routine")
        activity = ", ".join(flags) if flags else "idle"
        self.status.configure(text=f"{route} • {mode} • {session} • {activity}")

    def _refresh_routines(self) -> None:
        self.routines.delete(0, "end")
        for item in self.runtime.routines.list():
            self.routines.insert("end", self.runtime.routines.render(item))

    def _close(self) -> None:
        if self.busy or self.autonomy_busy:
            if not messagebox.askyesno("Quitter SKYNET", "Une tâche est active. Quitter quand même ?"):
                return
        self.runtime.close()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    DesktopApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
