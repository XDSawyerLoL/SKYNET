from __future__ import annotations

from dataclasses import dataclass
import math
import tkinter as tk


@dataclass(frozen=True, slots=True)
class Palette:
    bg: str = "#070B10"
    sidebar: str = "#090E14"
    panel: str = "#0C131B"
    panel_alt: str = "#101A24"
    border: str = "#172737"
    border_hot: str = "#1D4963"
    text: str = "#E7F0F7"
    muted: str = "#7890A1"
    faint: str = "#445866"
    cyan: str = "#21C8FF"
    cyan_soft: str = "#0E7FA8"
    green: str = "#35D69A"
    amber: str = "#F2B84B"
    red: str = "#FF5D68"


PALETTE = Palette()


def orb_mode(*, busy: bool, autonomy_busy: bool, stopped: bool) -> str:
    if stopped:
        return "stopped"
    if busy:
        return "thinking"
    if autonomy_busy:
        return "acting"
    return "idle"


class StatusOrb(tk.Canvas):
    """Small, dependency-free animated identity element.

    The animation is intentionally restrained: it communicates state without
    turning the product into a permanently moving HUD.
    """

    def __init__(self, master, size: int = 76, **kwargs) -> None:
        super().__init__(
            master,
            width=size,
            height=size,
            bg=kwargs.pop("bg", PALETTE.bg),
            highlightthickness=0,
            bd=0,
            **kwargs,
        )
        self.size = size
        self.mode = "idle"
        self.phase = 0.0
        self._alive = True
        self.after(80, self._tick)

    def set_mode(self, mode: str) -> None:
        self.mode = mode

    def destroy(self) -> None:
        self._alive = False
        super().destroy()

    def _tick(self) -> None:
        if not self._alive:
            return
        self.phase = (self.phase + 0.13) % (math.pi * 2)
        self._draw()
        self.after(80, self._tick)

    def _draw(self) -> None:
        self.delete("all")
        s = self.size
        c = s / 2
        if self.mode == "stopped":
            accent = PALETTE.red
            pulse = 0.5
        elif self.mode == "acting":
            accent = PALETTE.amber
            pulse = 0.5 + 0.25 * math.sin(self.phase * 1.4)
        elif self.mode == "thinking":
            accent = PALETTE.cyan
            pulse = 0.55 + 0.35 * math.sin(self.phase * 2.0)
        else:
            accent = PALETTE.cyan
            pulse = 0.45 + 0.12 * math.sin(self.phase)

        r_outer = s * (0.36 + 0.02 * pulse)
        r_mid = s * 0.28
        r_core = s * (0.10 + 0.015 * pulse)
        self.create_oval(c-r_outer, c-r_outer, c+r_outer, c+r_outer, outline=PALETTE.border_hot, width=1)
        self.create_oval(c-r_mid, c-r_mid, c+r_mid, c+r_mid, outline=accent, width=2)
        self.create_oval(c-r_core, c-r_core, c+r_core, c+r_core, fill=accent, outline="")

        # Only four moving markers: enough life, little visual noise.
        marker_r = s * 0.31
        for index in range(4):
            angle = self.phase * (0.55 if index % 2 == 0 else -0.35) + index * (math.pi / 2)
            x = c + math.cos(angle) * marker_r
            y = c + math.sin(angle) * marker_r
            rr = 1.4 if self.mode == "idle" else 2.0
            self.create_oval(x-rr, y-rr, x+rr, y+rr, fill=accent, outline="")


__all__ = ["PALETTE", "Palette", "StatusOrb", "orb_mode"]
