#!/usr/bin/env python3
"""B F Futa — Bug Finder Futa.

Drop this file next to any Tk app. Same lime-on-black look as AW_FutaDepot.

    import bf_futa
    bf = bf_futa.install(root)
    bf.attach_checkbox(settings_frame)   # dummy checkbox at end of settings
    bf.log("info", "scan", "SCAN START", "walking _FutaMass", "who=scan_all")

Secret: click the checkbox туда-сюда 3 times (6 clicks) within 5 seconds.
A single click does nothing. One click while the overlay is open closes it.
Re-open needs the 3 round-trips again.
"""

from __future__ import annotations

import time
import tkinter as tk
from datetime import datetime, timezone

LIME = "#99e550"
BG = "#061108"
FILL = "#0d1a10"
LINE = "#1f3d24"
TEXT = "#e8e4d8"
DIM = "#8a9a88"
ERR = "#ff4d4d"
WARN = "#f5c542"
INFO = "#e8e4d8"
SYS = "#9aa89a"

LEVEL_FG = {"error": ERR, "warn": WARN, "info": INFO, "sys": SYS}
MAX_LOGS = 800
SECRET_CLICKS = 6
SECRET_WINDOW = 5.0

_bus = None


def install(root: tk.Tk, app_name: str = "app"):
    global _bus
    if _bus is None:
        _bus = BFFuta(root, app_name)
    else:
        _bus.root = root
        _bus.app_name = app_name
    return _bus


def get():
    return _bus


def log(level: str, who: str, title: str, what: str = "", note: str = "", **extra) -> None:
    if _bus is None:
        return
    _bus.log(level, who, title, what, note, **extra)


class BFFuta:
    def __init__(self, root: tk.Tk, app_name: str = "app") -> None:
        self.root = root
        self.app_name = app_name
        self.rows: list[dict] = []
        self.win: tk.Toplevel | None = None
        self.list_box: tk.Frame | None = None
        self.alpha = 0.88
        self._clicks: list[float] = []
        self._var = tk.BooleanVar(value=False)
        self._busy = False
        self._boot()

    def _boot(self) -> None:
        self.log("sys", "bf_futa", "INIT", "B F Futa attached", "secret: 6 clicks / 5s on the dummy checkbox")

    def attach_checkbox(self, parent: tk.Widget, text: str = "B F Futa") -> tk.Checkbutton:
        box = tk.Checkbutton(
            parent,
            text=text,
            variable=self._var,
            command=self._on_dummy,
            fg=DIM,
            bg=parent.cget("bg") if "bg" in parent.keys() else BG,
            selectcolor=FILL,
            activebackground=parent.cget("bg") if "bg" in parent.keys() else BG,
            activeforeground=DIM,
            font=("Consolas", 10),
            highlightthickness=0,
            bd=0,
        )
        box.pack(anchor="w", pady=(16, 4))
        return box

    def _on_dummy(self) -> None:
        if self._busy:
            return
        now = time.monotonic()
        self._clicks = [t for t in self._clicks if now - t <= SECRET_WINDOW]
        self._clicks.append(now)
        open_win = self.win is not None
        try:
            open_win = open_win and bool(self.win.winfo_exists())
        except tk.TclError:
            open_win = False
        self._busy = True
        try:
            if open_win:
                self.hide()
                self._clicks.clear()
                self.log("sys", "bf_futa", "CLOSE", "overlay closed by one toggle")
                return
            if len(self._clicks) >= SECRET_CLICKS:
                self._clicks.clear()
                self._var.set(False)
                self.show()
                self.log("info", "bf_futa", "UNLOCK", "secret 3× round-trip accepted", "overlay open")
                return
            self._var.set(False)
        finally:
            self._busy = False

    def log(self, level: str, who: str, title: str, what: str = "", note: str = "", **extra) -> None:
        level = (level or "info").lower()
        if level not in LEVEL_FG:
            level = "info"
        row = {
            "t": datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3],
            "iso": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "level": level,
            "who": who or "?",
            "title": title or "",
            "what": what or "",
            "note": note or "",
            "extra": extra or {},
        }
        self.rows.append(row)
        if len(self.rows) > MAX_LOGS:
            self.rows = self.rows[-MAX_LOGS:]
        if self.win is not None:
            try:
                if self.win.winfo_exists():
                    self.root.after(0, lambda r=row: self._paint_row(r))
            except tk.TclError:
                pass

    def show(self) -> None:
        if self.win is not None:
            try:
                if self.win.winfo_exists():
                    self.win.deiconify()
                    self.win.lift()
                    return
            except tk.TclError:
                self.win = None
        w = tk.Toplevel(self.root)
        self.win = w
        w.title("B F Futa")
        w.configure(bg=BG)
        w.geometry("520x640+24+80")
        w.minsize(360, 280)
        w.attributes("-topmost", True)
        try:
            w.attributes("-alpha", self.alpha)
        except tk.TclError:
            pass
        w.protocol("WM_DELETE_WINDOW", self.hide)

        head = tk.Frame(w, bg=FILL)
        head.pack(fill="x")
        tk.Label(head, text="B F Futa", fg=LIME, bg=FILL, font=("Consolas", 16, "bold")).pack(side="left", padx=12, pady=8)
        tk.Label(head, text=self.app_name, fg=DIM, bg=FILL, font=("Consolas", 10)).pack(side="left")
        tk.Button(head, text="×", command=self.hide, bg=FILL, fg=LIME, relief="flat", bd=0, cursor="hand2", font=("Consolas", 14)).pack(side="right", padx=8)

        slide = tk.Frame(w, bg=BG)
        slide.pack(fill="x", padx=12, pady=4)
        tk.Label(slide, text="bg alpha", fg=LIME, bg=BG, font=("Consolas", 9)).pack(side="left")
        self._alpha_var = tk.DoubleVar(value=self.alpha)

        def on_alpha(_=None):
            self.alpha = float(self._alpha_var.get())
            try:
                w.attributes("-alpha", self.alpha)
            except tk.TclError:
                pass

        sc = tk.Scale(
            slide,
            from_=0.35,
            to=1.0,
            resolution=0.01,
            orient="horizontal",
            variable=self._alpha_var,
            command=on_alpha,
            bg=BG,
            fg=LIME,
            troughcolor=FILL,
            highlightthickness=0,
            showvalue=0,
            sliderrelief="flat",
            length=220,
        )
        sc.pack(side="left", fill="x", expand=True, padx=8)

        wrap = tk.Frame(w, bg=BG)
        wrap.pack(fill="both", expand=True, padx=8, pady=8)
        canvas = tk.Canvas(wrap, bg=BG, highlightthickness=0, bd=0)
        sb = tk.Scrollbar(wrap, orient="vertical", command=canvas.yview, bg=FILL, troughcolor=BG, activebackground=LIME, highlightthickness=0)
        inner = tk.Frame(canvas, bg=BG)
        self._log_win = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(self._log_win, width=e.width))
        self.list_box = inner
        self._canvas = canvas
        for row in self.rows:
            self._paint_row(row)
        self.root.after(50, lambda: canvas.yview_moveto(1.0))

        def wheel(ev):
            canvas.yview_scroll(-1 if getattr(ev, "delta", 0) > 0 or getattr(ev, "num", 0) == 4 else 1, "units")

        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", wheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

    def hide(self) -> None:
        if self.win is None:
            return
        try:
            self.win.destroy()
        except tk.TclError:
            pass
        self.win = None
        self.list_box = None
        self._var.set(False)

    def _paint_row(self, row: dict) -> None:
        if self.list_box is None:
            return
        fg = LEVEL_FG.get(row["level"], INFO)
        line = f"{row['t']}  [{row['level']}]  {row['who']}  ·  {row['title']}"
        fr = tk.Frame(self.list_box, bg=BG, cursor="hand2")
        fr.pack(fill="x", pady=1)
        lab = tk.Label(fr, text=line, fg=fg, bg=BG, anchor="w", font=("Consolas", 9), justify="left")
        lab.pack(fill="x")
        fr.bind("<Button-1>", lambda e, r=row: self._detail(r))
        lab.bind("<Button-1>", lambda e, r=row: self._detail(r))
        try:
            self._canvas.yview_moveto(1.0)
        except Exception:
            pass

    def _detail(self, row: dict) -> None:
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        side = max(280, int((sw * sh / 6) ** 0.5))
        x = (sw - side) // 2
        y = (sh - side) // 2
        box = tk.Toplevel(self.root)
        box.title(row.get("title") or "log")
        box.configure(bg=BG)
        box.geometry(f"{side}x{side}+{x}+{y}")
        box.attributes("-topmost", True)
        tk.Label(box, text=row.get("title") or "LOG", fg=LIME, bg=BG, font=("Consolas", 14, "bold")).pack(anchor="w", padx=12, pady=(10, 2))
        meta = f"{row.get('iso')}   {row.get('level')}   who={row.get('who')}"
        tk.Label(box, text=meta, fg=DIM, bg=BG, font=("Consolas", 9)).pack(anchor="w", padx=12)
        body = (
            f"TITLE: {row.get('title')}\n"
            f"WHO:   {row.get('who')}\n"
            f"LEVEL: {row.get('level')}\n"
            f"WHEN:  {row.get('iso')}\n"
            f"WHAT:  {row.get('what')}\n"
            f"NOTE:  {row.get('note')}\n"
        )
        extra = row.get("extra") or {}
        if extra:
            body += "DATA:\n" + "\n".join(f"  {k}={v}" for k, v in extra.items())
        txt = tk.Text(box, bg=FILL, fg=TEXT, insertbackground=LIME, relief="flat", wrap="word", font=("Consolas", 10), highlightthickness=1, highlightbackground=LIME)
        txt.pack(fill="both", expand=True, padx=12, pady=8)
        txt.insert("1.0", body)
        txt.focus_set()
        bar = tk.Frame(box, bg=BG)
        bar.pack(fill="x", padx=12, pady=(0, 12))

        def copy_it():
            box.clipboard_clear()
            box.clipboard_append(txt.get("1.0", "end-1c"))
            bf_note = tk.Label(bar, text="copied", fg=LIME, bg=BG, font=("Consolas", 9))
            bf_note.pack(side="left", padx=8)
            box.after(1200, bf_note.destroy)

        copy_btn = tk.Canvas(bar, width=36, height=36, bg="#000000", highlightthickness=1, highlightbackground=LIME, cursor="hand2")
        copy_btn.pack(side="left")
        copy_btn.create_rectangle(10, 8, 24, 22, outline=LIME, width=2)
        copy_btn.create_rectangle(16, 14, 30, 28, outline=LIME, width=2, fill="#000000")
        copy_btn.bind("<Button-1>", lambda e: copy_it())
        tk.Button(bar, text="OK", command=box.destroy, bg=LIME, fg="#000000", relief="flat", padx=18, pady=8, font=("Consolas", 11, "bold"), cursor="hand2").pack(side="right")
