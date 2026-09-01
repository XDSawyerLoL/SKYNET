from __future__ import annotations

import math
import tkinter as tk
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CommandPalette:
    bg: str = "#03070B"
    bg_alt: str = "#050B11"
    sidebar: str = "#060C12"
    panel: str = "#07121B"
    panel_alt: str = "#091A26"
    panel_hot: str = "#0B2130"
    border: str = "#123348"
    border_hot: str = "#0B77A4"
    cyan: str = "#08C8FF"
    cyan2: str = "#2EE6FF"
    blue: str = "#1976FF"
    green: str = "#20E6A2"
    amber: str = "#FFBD45"
    red: str = "#FF4E62"
    purple: str = "#9A6CFF"
    text: str = "#E8F5FC"
    text_soft: str = "#B7D0DE"
    muted: str = "#6E91A5"
    faint: str = "#315268"


PALETTE = CommandPalette()


class HudCard(tk.Frame):
    def __init__(self, master, *, title: str = "", accent: str | None = None, **kwargs) -> None:
        super().__init__(
            master,
            bg=kwargs.pop("bg", PALETTE.panel),
            highlightthickness=1,
            highlightbackground=accent or PALETTE.border,
            bd=0,
            **kwargs,
        )
        self.accent = accent or PALETTE.cyan
        self.grid_columnconfigure(0, weight=1)
        self.header = tk.Frame(self, bg=self["bg"])
        self.header.grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 6))
        self.header.grid_columnconfigure(0, weight=1)
        self.title = tk.Label(
            self.header,
            text=title.upper(),
            bg=self["bg"],
            fg=self.accent,
            font=("Segoe UI Semibold", 9),
        )
        self.title.grid(row=0, column=0, sticky="w")
        self.body = tk.Frame(self, bg=self["bg"])
        self.body.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 12))
        self.grid_rowconfigure(1, weight=1)


class Pill(tk.Label):
    def __init__(self, master, text: str, *, fg: str = PALETTE.cyan, bg: str = PALETTE.panel_alt, **kwargs) -> None:
        super().__init__(master, text=text, fg=fg, bg=bg, font=("Segoe UI Semibold", 8), padx=9, pady=4, **kwargs)


class NeonButton(tk.Button):
    def __init__(self, master, text: str, command=None, *, danger: bool = False, primary: bool = False, **kwargs) -> None:
        if danger:
            bg, fg, active = "#2A0B10", PALETTE.red, "#401017"
        elif primary:
            bg, fg, active = PALETTE.cyan, "#001018", "#45D8FF"
        else:
            bg, fg, active = PALETTE.panel_alt, PALETTE.text_soft, PALETTE.panel_hot
        super().__init__(
            master,
            text=text,
            command=command,
            bg=bg,
            fg=fg,
            activebackground=active,
            activeforeground=fg,
            relief="flat",
            bd=0,
            highlightthickness=1 if not primary else 0,
            highlightbackground=PALETTE.border,
            cursor="hand2",
            font=("Segoe UI Semibold", 9),
            padx=12,
            pady=8,
            **kwargs,
        )


class CommandCore(tk.Canvas):
    """Animated command-core HUD. Pure Tk, no external assets required."""

    def __init__(self, master, size: int = 420, **kwargs) -> None:
        super().__init__(master, width=size, height=size, bg=kwargs.pop("bg", PALETTE.bg_alt), highlightthickness=0, bd=0, **kwargs)
        self.size = size
        self.phase = 0.0
        self.mode = "idle"
        self.label = "SKYNET"
        self._alive = True
        self.after(50, self._tick)

    def set_mode(self, mode: str) -> None:
        self.mode = mode

    def set_label(self, label: str) -> None:
        self.label = label[:24].upper()

    def destroy(self) -> None:
        self._alive = False
        super().destroy()

    def _tick(self) -> None:
        if not self._alive:
            return
        self.phase = (self.phase + 0.032) % (math.pi * 2)
        self._draw()
        self.after(50, self._tick)

    def _draw_arc(self, c: float, r: float, start: float, extent: float, color: str, width: int = 2) -> None:
        self.create_arc(c-r, c-r, c+r, c+r, start=start, extent=extent, style="arc", outline=color, width=width)

    def _draw(self) -> None:
        self.delete("all")
        s = min(max(self.winfo_width(), 1), max(self.winfo_height(), 1))
        if s < 60:
            s = self.size
        c = s / 2
        accent = PALETTE.red if self.mode == "stopped" else PALETTE.amber if self.mode == "acting" else PALETTE.cyan

        # atmospheric grid crosshair
        self.create_line(c, s * .06, c, s * .94, fill="#082638", width=1)
        self.create_line(s * .06, c, s * .94, c, fill="#082638", width=1)

        for ratio, color, width in (
            (.44, "#092C42", 1),
            (.39, PALETTE.border_hot, 1),
            (.33, "#0D4F70", 1),
            (.27, accent, 2),
            (.19, "#0C678A", 1),
        ):
            r = s * ratio
            self.create_oval(c-r, c-r, c+r, c+r, outline=color, width=width)

        # rotating segmented rings
        for i in range(18):
            start = math.degrees(self.phase * (1 if i % 2 == 0 else -0.65)) + i * 20
            extent = 6 + (i % 4) * 3
            radius = s * (.35 if i % 2 == 0 else .30)
            self._draw_arc(c, radius, start, extent, PALETTE.cyan if i % 3 else PALETTE.blue, 2 if i % 5 == 0 else 1)

        for i in range(48):
            angle = (i / 48) * math.tau + self.phase * .2
            inner = s * (.405 if i % 4 else .395)
            outer = inner + (7 if i % 4 == 0 else 3)
            x1, y1 = c + math.cos(angle) * inner, c + math.sin(angle) * inner
            x2, y2 = c + math.cos(angle) * outer, c + math.sin(angle) * outer
            self.create_line(x1, y1, x2, y2, fill="#0D6F94", width=1)

        # orbiting nodes
        for i in range(6):
            angle = self.phase * (1.1 if i % 2 else -.7) + i * math.tau / 6
            rr = s * (.37 if i % 2 else .32)
            x, y = c + math.cos(angle) * rr, c + math.sin(angle) * rr
            self.create_oval(x-3, y-3, x+3, y+3, fill=accent, outline="#8DEAFF")

        pulse = .5 + .5 * math.sin(self.phase * 4)
        core_r = s * (.105 + .006 * pulse)
        self.create_oval(c-core_r, c-core_r, c+core_r, c+core_r, outline=accent, width=2)
        self.create_text(c, c-7, text=self.label, fill=PALETTE.text, font=("Segoe UI Semibold", max(12, int(s*.045))))
        self.create_text(c, c+19, text="●  ONLINE" if self.mode != "stopped" else "●  SAFE MODE", fill=PALETTE.green if self.mode != "stopped" else PALETTE.red, font=("Segoe UI Semibold", max(7, int(s*.018))))


class RingGauge(tk.Canvas):
    def __init__(self, master, *, value: float = 0.0, label: str = "", size: int = 96, color: str = PALETTE.cyan, **kwargs) -> None:
        super().__init__(master, width=size, height=size, bg=kwargs.pop("bg", PALETTE.panel), highlightthickness=0, bd=0, **kwargs)
        self.size = size
        self.value = max(0.0, min(100.0, value))
        self.label = label
        self.color = color
        self.bind("<Configure>", lambda _e: self._draw())
        self._draw()

    def set(self, value: float, label: str | None = None) -> None:
        self.value = max(0.0, min(100.0, value))
        if label is not None:
            self.label = label
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        s = self.size
        pad = 9
        self.create_oval(pad, pad, s-pad, s-pad, outline=PALETTE.border, width=5)
        extent = -3.6 * self.value
        self.create_arc(pad, pad, s-pad, s-pad, start=90, extent=extent, style="arc", outline=self.color, width=5)
        self.create_text(s/2, s/2-5, text=f"{self.value:.0f}%", fill=PALETTE.text, font=("Segoe UI Semibold", 13))
        if self.label:
            self.create_text(s/2, s/2+16, text=self.label, fill=PALETTE.muted, font=("Segoe UI", 7))


class Sparkline(tk.Canvas):
    def __init__(self, master, *, color: str = PALETTE.cyan, height: int = 34, **kwargs) -> None:
        super().__init__(master, height=height, bg=kwargs.pop("bg", PALETTE.panel), highlightthickness=0, bd=0, **kwargs)
        self.color = color
        self.values: list[float] = []
        self.bind("<Configure>", lambda _e: self._draw())

    def push(self, value: float) -> None:
        self.values.append(float(value))
        self.values = self.values[-40:]
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        if len(self.values) < 2:
            return
        w = max(10, self.winfo_width())
        h = max(10, self.winfo_height())
        lo, hi = min(self.values), max(self.values)
        span = max(1.0, hi-lo)
        pts: list[float] = []
        for i, value in enumerate(self.values):
            x = i * (w-2) / max(1, len(self.values)-1) + 1
            y = h-3 - ((value-lo)/span) * (h-7)
            pts.extend((x, y))
        self.create_line(*pts, fill=self.color, width=1.4, smooth=True)


class Waveform(tk.Canvas):
    def __init__(self, master, *, height: int = 72, **kwargs) -> None:
        super().__init__(master, height=height, bg=kwargs.pop("bg", PALETTE.panel), highlightthickness=0, bd=0, **kwargs)
        self.phase = 0.0
        self.active = False
        self._alive = True
        self.after(70, self._tick)

    def set_active(self, active: bool) -> None:
        self.active = active

    def destroy(self) -> None:
        self._alive = False
        super().destroy()

    def _tick(self) -> None:
        if not self._alive:
            return
        self.phase += .16
        self._draw()
        self.after(70, self._tick)

    def _draw(self) -> None:
        self.delete("all")
        w, h = max(20, self.winfo_width()), max(20, self.winfo_height())
        mid = h/2
        amp = 13 if self.active else 4
        pts: list[float] = []
        for i in range(80):
            x = i * w / 79
            envelope = .35 + .65 * math.sin(i/79 * math.pi) ** 2
            wave = math.sin(i*.72 + self.phase) + .45*math.sin(i*.21-self.phase*1.7)
            y = mid + wave * amp * envelope
            pts.extend((x, y))
        self.create_line(*pts, fill=PALETTE.cyan, width=1.2, smooth=True)
        self.create_line(0, mid, w, mid, fill="#0B3144", width=1)


__all__ = ["PALETTE", "CommandPalette", "HudCard", "Pill", "NeonButton", "CommandCore", "RingGauge", "Sparkline", "Waveform"]
