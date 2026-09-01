from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from pathlib import Path

from .runtime import Runtime


class DesktopApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("SKYNET V0.5 — Sovereign Local AI")
        self.root.geometry("1080x720")
        self.runtime = Runtime.create(Path.cwd(), session_id="desktop")
        self.events: queue.Queue[tuple[str, str]] = queue.Queue()
        self.busy = False
        self.autonomy_busy = False
        self._build()
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

        title = ttk.Label(outer, text="SKYNET V0.5 — Measured Evolution", font=("Segoe UI", 18, "bold"))
        title.grid(row=0, column=0, sticky="w")
        self.status = ttk.Label(outer, text="")
        self.status.grid(row=0, column=1, sticky="e")

        chat_frame = ttk.Frame(outer)
        chat_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 10), pady=(10, 0))
        chat_frame.rowconfigure(0, weight=1)
        chat_frame.columnconfigure(0, weight=1)

        self.chat = tk.Text(chat_frame, wrap="word", state="disabled", font=("Segoe UI", 10))
        self.chat.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(chat_frame, orient="vertical", command=self.chat.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.chat.configure(yscrollcommand=scroll.set)

        input_row = ttk.Frame(chat_frame)
        input_row.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        input_row.columnconfigure(0, weight=1)
        self.entry = ttk.Entry(input_row)
        self.entry.grid(row=0, column=0, sticky="ew")
        self.entry.bind("<Return>", lambda _event: self._send())
        ttk.Button(input_row, text="Envoyer", command=self._send).grid(row=0, column=1, padx=(8, 0))

        side = ttk.LabelFrame(outer, text="Autonomie locale & évolution", padding=8)
        side.grid(row=1, column=1, sticky="nsew", pady=(10, 0))
        side.rowconfigure(1, weight=1)
        side.columnconfigure(0, weight=1)

        ttk.Label(side, text="Routines").grid(row=0, column=0, sticky="w")
        self.routines = tk.Listbox(side, height=12)
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
        self.routine_prompt = tk.Text(form, height=5, wrap="word")
        self.routine_prompt.grid(row=2, column=1, sticky="ew", padx=(6, 0))
        ttk.Button(form, text="Ajouter la routine", command=self._add_routine).grid(row=3, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Button(form, text="Exécuter les routines dues", command=self._run_due_manual).grid(row=4, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        ttk.Button(form, text="État évolution", command=self._show_evolution).grid(row=5, column=0, columnspan=2, sticky="ew", pady=(6, 0))

        self._append("SYSTEM", "SKYNET V0.5 démarré. Mandats, évolution mesurée, mémoire, routines et outils restent locaux par défaut.")

    def _append(self, who: str, text: str) -> None:
        self.chat.configure(state="normal")
        self.chat.insert("end", f"\n{who} > {text}\n")
        self.chat.configure(state="disabled")
        self.chat.see("end")

    def _confirm(self, message: str) -> bool:
        done = threading.Event()
        result = {"value": False}

        def ask() -> None:
            result["value"] = messagebox.askyesno("Autorisation SKYNET", message, parent=self.root)
            done.set()

        self.root.after(0, ask)
        done.wait()
        return bool(result["value"])

    def _show_evolution(self) -> None:
        deployed = self.runtime.deployments.get("reasoning-model")
        deployment = "baseline" if deployed is None else f"{deployed.active} [{deployed.status}]"
        scores = self.runtime.scores.recent(5)
        proposals = self.runtime.trajectory_miner.proposals()
        text = f"Deployment: {deployment}\nScorecards: {len(scores)} recent\nLearning proposals: {len(proposals)}\n"
        text += "Use the CLI :tournament command for explicit model benchmarking and canary promotion."
        self._append("EVOLUTION", text)

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
            messagebox.showerror("Routine", "L’intervalle doit être un nombre entier d’au moins 1 minute.")
            return
        if not name or not prompt:
            messagebox.showerror("Routine", "Nom et instruction sont obligatoires.")
            return
        if not messagebox.askyesno("Routine", f"Créer la routine locale '{name}' toutes les {minutes} minutes ?"):
            return
        try:
            self.runtime.routines.create(name, prompt, minutes * 60, start_in_seconds=minutes * 60)
            self.routine_name.delete(0, "end")
            self.routine_prompt.delete("1.0", "end")
            self._refresh_routines()
        except Exception as exc:
            messagebox.showerror("Routine", str(exc))

    def _run_due_manual(self) -> None:
        if self.autonomy_busy:
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
        if not self.autonomy_busy and self.runtime.routines.due():
            self._start_autonomy()
        self.root.after(max(10, self.runtime.config.autonomy_poll_seconds) * 1000, self._autonomy_tick)

    def _drain_events(self) -> None:
        try:
            while True:
                kind, text = self.events.get_nowait()
                if kind == "reply":
                    self._append("SKYNET", text)
                elif kind == "routine":
                    self._append("ROUTINE", text)
                    self._refresh_routines()
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
        route = self.runtime.router.last_route.model
        deployed = self.runtime.deployments.get("reasoning-model")
        mode = deployed.status if deployed else "baseline"
        flags = []
        if self.busy:
            flags.append("chat")
        if self.autonomy_busy:
            flags.append("routine")
        activity = ", ".join(flags) if flags else "idle"
        self.status.configure(text=f"{route} • {mode} • {activity}")

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
