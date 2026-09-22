#!/usr/bin/env python3
"""AW_FutaDepot standalone window. No browser."""

from __future__ import annotations

import io
import locale
import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from pathlib import Path

# lib/ on sys.path before local imports
_ROOT = Path(__file__).resolve().parent
_LIB = _ROOT / "lib"
if _LIB.is_dir() and str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

import app as core
import win_cfg
import lib_opt
import bf_futa

try:
    from PIL import Image, ImageGrab, ImageTk
except ImportError:
    Image = ImageGrab = ImageTk = None

BG = "#0d0b12"
FILL = "#222034"
HOVER = "#2e2c42"
PRESS = "#99e550"
LIME = "#99e550"
CYAN = "#22d3ee"
BLUE = "#3b82f6"
ORANGE = "#f97316"
MUTED = "#6a8a4a"
TEXT = "#e8e4d8"
DIM = "#8a8678"
LINE = "#3a3848"
AUMID = "ArtWolf.AW_FutaDepot.1"


def apply_app_icon(root: tk.Tk) -> None:
    ico = core.APP_DIR / "icon.ico"
    png = core.APP_DIR / "icon128.png"
    if ico.exists():
        try:
            root.iconbitmap(str(ico))
        except tk.TclError:
            pass
    if png.exists():
        try:
            img = tk.PhotoImage(file=str(png))
            root.iconphoto(True, img)
            root._iconphoto_ref = img
        except tk.TclError:
            pass
    if os.name != "nt":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(AUMID)
        if not ico.exists():
            return
        IMAGE_ICON, LR_LOADFROMFILE, WM_SETICON = 1, 0x0010, 0x0080
        handle = ctypes.windll.user32.LoadImageW(None, str(ico), IMAGE_ICON, 0, 0, LR_LOADFROMFILE)
        if not handle:
            return
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id()) or root.winfo_id()
        ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, 0, handle)
        ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, 1, handle)
    except Exception:
        pass


class Tip:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.win = None
        self.lab = None

    def show(self, text: str, x: int, y: int, fg: str | None = None, bg: str | None = None, size: int = 9) -> None:
        fg = fg or TEXT
        bg = bg or FILL
        if self.win is None or not self.win.winfo_exists():
            self.win = tk.Toplevel(self.root)
            self.win.wm_overrideredirect(True)
            self.win.configure(bg=LIME)
            fr = tk.Frame(self.win, bg=bg, padx=10, pady=8)
            fr.pack(padx=1, pady=1)
            self.lab = tk.Label(fr, text=text, fg=fg, bg=bg, justify="left", font=("Consolas", size, "bold"), anchor="w", wraplength=720)
            self.lab.pack()
            self._fr = fr
        else:
            self._fr.configure(bg=bg)
            self.lab.configure(text=text, fg=fg, bg=bg, font=("Consolas", size, "bold"))
        self.win.geometry(f"+{x + 16}+{y + 16}")
        self.win.deiconify()

    def hide(self) -> None:
        if self.win is not None and self.win.winfo_exists():
            self.win.withdraw()

    def show_img(self, path: str, x: int, y: int, caption: str = "") -> None:
        self.hide()
        self.show((caption + "\n" if caption else "") + path, x, y)
        if Image is None or ImageTk is None:
            return
        p = Path(path)
        if not p.is_file():
            return
        try:
            im = Image.open(p)
            im.thumbnail((220, 220))
            photo = ImageTk.PhotoImage(im)
        except Exception:
            return
        if self.win is None or not self.win.winfo_exists():
            return
        lab = tk.Label(self.win, image=photo, bg=FILL)
        lab.image = photo
        lab.pack(padx=4, pady=4)



class DepotUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("AW_FutaDepot")
        self.root.minsize(1100, 720)
        self.root.configure(bg=BG)
        dpi = root.winfo_fpixels("1i")
        self.scale = max(1.0, min(2.0, dpi / 96.0))
        self.fs = int(11 * self.scale)
        self.fs_big = int(18 * self.scale)
        self.cfg = core.load_config()
        self.cats = []
        self.current = None
        self.filter_kind = None
        self.unit = None
        self.tab = "lib"
        self.hist = [{"tab": "lib", "cat": None}]
        self.hist_i = 0
        self.quiet = False
        self.page = 0
        self.store_page = 0
        self.tip = Tip(root)
        self.path_vars = {}
        self.icon_target = None
        self.photo_keep = {}
        self._grid_cols = 0
        self._sidebar_sig = None
        self._last_wh = (0, 0)
        self._relayout_job = None
        self._relayouting = False
        self._unit_cells = []
        self._units_sig = None
        self._scan_busy = False
        self.sort_kind = None
        self.bf = bf_futa.install(self.root, "AW_FutaDepot")
        core.unblock_app_dir()
        self._build()
        self.root.bind("<Control-v>", self.on_paste)
        self.root.bind("<Control-V>", self.on_paste)
        self.reload()
        self.root.after(50, self._regrid_units)
        self.root.after(200, self._regrid_units)
        self.root.after(250, self.ensure_library)
        self.root.after(400, self.apply_db_view)
        self.root.after(500, self.maybe_help)

    def px(self, n: int) -> int:
        return int(n * self.scale)

    def hoverize(self, w: tk.Widget, idle=FILL, over=HOVER, down=PRESS, idle_fg=TEXT, down_fg=BG) -> None:
        def enter(_=None):
            try:
                w.configure(bg=over)
            except tk.TclError:
                pass

        def leave(_=None):
            try:
                w.configure(bg=idle)
            except tk.TclError:
                pass

        def press(_=None):
            try:
                w.configure(bg=down, fg=down_fg)
            except tk.TclError:
                pass

        def release(_=None):
            try:
                w.configure(bg=over, fg=idle_fg)
            except tk.TclError:
                pass

        w.bind("<Enter>", enter)
        w.bind("<Leave>", leave)
        w.bind("<ButtonPress-1>", press)
        w.bind("<ButtonRelease-1>", release)

    def _btn(self, parent, text, cmd, primary=False, accent=None):
        if accent:
            bg, fg = accent, BG
        elif primary:
            bg, fg = LIME, BG
        else:
            bg, fg = FILL, TEXT
        b = tk.Button(
            parent,
            text=text,
            command=cmd,
            bg=bg,
            fg=fg,
            activebackground=PRESS,
            activeforeground=BG,
            relief="flat",
            highlightthickness=1,
            highlightbackground=accent or LIME,
            bd=0,
            padx=self.px(12),
            pady=self.px(8),
            font=("Consolas", self.fs),
            cursor="hand2",
        )
        if accent:
            self.hoverize(b, idle=accent, over="#67e8f9" if accent == CYAN else HOVER, down=PRESS, idle_fg=BG, down_fg=BG)
        elif primary:
            self.hoverize(b, idle=LIME, over="#b6f06a", down="#6a8a4a", idle_fg=BG, down_fg=BG)
        else:
            self.hoverize(b)
        return b

    def _init_styles(self) -> None:
        st = ttk.Style(self.root)
        try:
            st.theme_use("clam")
        except tk.TclError:
            pass
        st.configure("TPanedwindow", background=BG)
        st.configure("Sash", sashthickness=self.px(6), background="#2e2c42", gripcount=0)
        st.configure(
            "Depot.Vertical.TScrollbar",
            background="#2e2c42",
            troughcolor=BG,
            bordercolor=BG,
            arrowcolor=LIME,
            lightcolor="#2e2c42",
            darkcolor="#16141c",
            relief="flat",
        )
        st.map(
            "Depot.Vertical.TScrollbar",
            background=[("active", "#3a3848"), ("pressed", LIME)],
            arrowcolor=[("pressed", BG)],
        )

    def _build(self) -> None:
        self._init_styles()
        top = tk.Frame(self.root, bg=FILL, pady=self.px(6), padx=self.px(8))
        top.pack(fill="x")
        tk.Label(top, text="AW_FutaDepot", fg=LIME, bg=FILL, font=("Consolas", self.fs_big, "bold")).pack(side="left", padx=8)
        for name, key in (
            ("LIBRARY", "lib"),
            ("AUTOSORT", "sort"),
            ("INSTALLED", "inst"),
            ("NET INSTALL", "store"),
            ("PATHS", "paths"),
            ("SETTINGS", "set"),
            ("WIN CFG", "wincfg"),
            ("TOOLBOX", "box"),
        ):
            self._btn(top, name, lambda k=key: self.show_tab(k)).pack(side="left", padx=2)
        self.lbl_root = tk.Label(top, text="", fg=DIM, bg=FILL, font=("Consolas", max(8, self.fs - 2)))
        self.lbl_root.pack(side="right", padx=8)
        self._btn(top, "OPEN", self.open_root).pack(side="right", padx=2)
        self._btn(top, "COPY", self.copy_root).pack(side="right", padx=2)
        self._btn(top, "IMPORT", self.import_meta).pack(side="right", padx=2)
        self._btn(top, "SYNC", self.sync_net).pack(side="right", padx=2)
        self._btn(top, "REPORT", self.make_report).pack(side="right", padx=2)
        self._btn(top, "SCAN", self.scan).pack(side="right", padx=2)
        self._btn(top, "?", self.show_help).pack(side="right", padx=2)

        nav = tk.Frame(self.root, bg="#16141c", pady=self.px(6), padx=self.px(8))
        nav.pack(fill="x")
        self.btn_back = self._btn(nav, "←", self.nav_back)
        self.btn_fwd = self._btn(nav, "→", self.nav_fwd)
        self.btn_back.pack(side="left", padx=2)
        self.btn_fwd.pack(side="left", padx=2)
        self._btn(nav, "HOME", self.go_home).pack(side="left", padx=2)
        self._btn(nav, "REFRESH", self.refresh).pack(side="left", padx=2)
        self._btn(nav, "SELECT", self.select_library, accent=CYAN).pack(side="left", padx=8)
        self._btn(nav, "NEW PACK", self.new_pack, primary=True).pack(side="left", padx=2)
        self.lbl_where = tk.Label(nav, text="LIBRARY / HOME", fg=DIM, bg="#16141c", font=("Consolas", self.fs))
        self.lbl_where.pack(side="left", padx=12)

        self.body = tk.Frame(self.root, bg=BG)
        self.body.pack(fill="both", expand=True)
        self.foot = tk.Label(self.root, text="ready", fg=DIM, bg=BG, anchor="w", font=("Consolas", max(8, self.fs - 2)))
        self.foot.pack(fill="x", padx=8, pady=4)

        self.frames = {}
        self._lib_frame()
        self._sort_frame()
        self._store_frame()
        self._paths_frame()
        self._inst_frame()
        self._set_frame()
        self._wincfg_frame()
        self._box_frame()
        self.show_tab("lib")

    def status(self, text: str) -> None:
        self.foot.configure(text=text)
        bf_futa.log("sys", "ui", "STATUS", text)

    def _on_resize(self, ev) -> None:
        if ev.widget is not self.root:
            return
        self._schedule_grid()

    def _schedule_grid(self, _e=None) -> None:
        if self._relayout_job:
            try:
                self.root.after_cancel(self._relayout_job)
            except tk.TclError:
                pass
        self._relayout_job = self.root.after(20, self._regrid_units)

    def _relayout(self, wh=None) -> None:
        self._regrid_units()

    def _tile_size(self) -> int:
        return self.px(148)

    def _regrid_units(self) -> None:
        self._relayout_job = None
        if self.tab != "lib":
            return
        canvas = getattr(self, "units_canvas", None)
        if canvas is None:
            return
        w = canvas.winfo_width()
        if w < 60:
            self.root.after(40, self._regrid_units)
            return
        tile = self._tile_size()
        gap = self.px(12)
        cols = max(1, (w - gap) // (tile + gap))
        if cols == self._grid_cols and self._unit_cells:
            return
        self._grid_cols = cols
        for i, cell in enumerate(self._unit_cells):
            cell.grid(row=i // cols, column=i % cols, padx=gap // 2, pady=gap // 2, sticky="nw")
        inner = self.units_inner
        for c in range(cols + 1):
            inner.grid_columnconfigure(c, weight=0, minsize=0)

    def show_tab(self, name: str) -> None:
        self.tab = name
        bf_futa.log("sys", "nav", "TAB", name, "page switch")
        for key, fr in self.frames.items():
            fr.pack_forget()
        self.frames[name].pack(fill="both", expand=True)
        if name == "store":
            self.fill_store()
        if name == "paths":
            self.fill_paths()
        if name == "inst":
            self.fill_installed()
        if name == "sort":
            self.fill_sort()
        if name in {"set", "box"}:
            self.fill_settings()
        if name == "wincfg":
            self.fill_wincfg()
        if name == "lib":
            self.root.after(30, self._place_sashes)
        self.push_hist()
        self.paint_nav()

    def snap(self):
        return {"tab": self.tab, "cat": self.current}

    def push_hist(self) -> None:
        if self.quiet:
            return
        s = self.snap()
        last = self.hist[self.hist_i]
        if last["tab"] == s["tab"] and last["cat"] == s["cat"]:
            return
        self.hist = self.hist[: self.hist_i + 1]
        self.hist.append(s)
        self.hist_i = len(self.hist) - 1

    def apply_snap(self, s) -> None:
        self.quiet = True
        self.current = s["cat"]
        self.unit = None
        self.show_tab(s["tab"])
        if s["tab"] == "lib":
            self.render_lib()
        self.quiet = False
        self.paint_nav()

    def paint_nav(self) -> None:
        self.btn_back.configure(state="normal" if self.hist_i > 0 else "disabled")
        self.btn_fwd.configure(state="normal" if self.hist_i < len(self.hist) - 1 else "disabled")
        names = {"lib": "LIBRARY", "sort": "AUTOSORT", "inst": "INSTALLED", "store": "NET INSTALL", "paths": "PATHS", "set": "SETTINGS", "box": "TOOLBOX"}
        where = names.get(self.tab, self.tab)
        if self.tab == "lib":
            where += " / " + (self.current or "HOME")
        self.lbl_where.configure(text=where)

    def nav_back(self) -> None:
        if self.unit is not None:
            self.unit = None
            host = self.inspector_host()
            for w in host.winfo_children():
                w.destroy()
            self.status("ready")
            return
        if self.hist_i <= 0:
            return
        self.hist_i -= 1
        self.apply_snap(self.hist[self.hist_i])

    def nav_fwd(self) -> None:
        if self.hist_i >= len(self.hist) - 1:
            return
        self.hist_i += 1
        self.apply_snap(self.hist[self.hist_i])

    def go_home(self) -> None:
        self.current = None
        self.filter_kind = None
        self.unit = None
        self.page = 0
        if self.tab != "lib":
            self.show_tab("lib")
        else:
            self.render_lib()
            self.push_hist()
            self.paint_nav()

    def refresh(self) -> None:
        self.apply_db_view()

    def apply_db_view(self) -> None:
        if getattr(self, "_scan_busy", False):
            return
        core.overlay_import_meta(self.cats)
        core.overlay_futa_db(self.cfg, self.cats)
        n = core.apply_icons(self.cfg, self.cats)
        self.photo_keep.clear()
        self._units_sig = None
        self.render_lib()
        self.status("icons " + str(n))
        bf_futa.log("info", "ui", "APPLY ICONS", str(n) + " bound from .futa-db")

    def reload(self) -> None:
        self.cfg = core.load_config()
        self.cats = core.discover_library(self.cfg)
        core.overlay_import_meta(self.cats)
        core.overlay_futa_db(self.cfg, self.cats)
        self.lbl_root.configure(text=str(core.library_root(self.cfg)))
        self.render_lib()
        self.status("AW_FutaDepot " + core.VERSION)

    def scan(self) -> None:
        if getattr(self, "_scan_busy", False):
            return
        self._scan_busy = True
        bf_futa.log("info", "scan", "STEP 1", "discover")
        self.status("1/5 discover")
        self.cats = core.discover_library(self.cfg)
        self.render_lib()
        self.root.after(20, self._scan_step_meta)

    def _scan_step_meta(self) -> None:
        bf_futa.log("info", "scan", "STEP 2", "import overlay")
        self.status("2/5 import overlay")
        core.overlay_import_meta(self.cats)
        self.root.after(20, self._scan_step_db)

    def _scan_step_db(self) -> None:
        bf_futa.log("info", "scan", "STEP 3", "load .futa-db")
        self.status("3/5 local db")
        core.overlay_futa_db(self.cfg, self.cats)
        self.photo_keep.clear()
        self._units_sig = None
        self.render_lib()
        self.root.after(20, self._scan_step_unblock)

    def _scan_step_unblock(self) -> None:
        bf_futa.log("info", "scan", "STEP 4", "unblock payloads")
        self.status("4/5 unblock")
        core.unblock_payloads(self.cats)
        self.root.after(20, self._scan_step_icons)

    def _scan_step_icons(self) -> None:
        bf_futa.log("info", "scan", "STEP 5a", "icons one-by-one")
        self.status("5/5 icons…")
        cats = self.cats
        cfg = self.cfg

        def work():
            n = core.harvest_icons(cats, cfg)
            self.root.after(0, lambda: self._scan_step_save(n))

        threading.Thread(target=work, daemon=True).start()

    def _scan_step_save(self, n: int) -> None:
        bf_futa.log("info", "scan", "STEP 5b", "persist db", str(n) + " icons")
        core.persist_library(self.cfg, self.cats)
        self._scan_busy = False
        self.apply_db_view()
        self.status("scan done · icons " + str(n))

    def harvest_idle(self) -> None:
        self.scan()

    def make_report(self) -> None:
        r = core.write_report(self.cfg)
        if not r.get("ok"):
            self.status(r.get("error") or "report fail")
            return
        dump = r.get("json") or ""
        self.status("SEND THIS → " + dump)
        ru = self.lang() == "ru"
        text = (
            "В чат отправь только этот файл:\n\n"
            f"{dump}\n\n"
            "Это снимок библиотеки. MD — для чтения глазами, его слать не надо.\n"
            "Когда чат вернёт JSON с описаниями — нажми SYNC или IMPORT."
            if ru
            else
            "Send only this file to the chat:\n\n"
            f"{dump}\n\n"
            "That is the library dump. The MD file is for reading, do not send it.\n"
            "When the chat returns a JSON with descriptions, press SYNC or IMPORT."
        )
        messagebox.showinfo("REPORT", text)
        if dump:
            core.open_path(Path(dump))

    def sync_net(self) -> None:
        ru = self.lang() == "ru"
        self.status("SYNC…")

        def work() -> None:
            r = core.sync_channel(self.cfg)
            self.root.after(0, lambda: self._sync_done(r))

        threading.Thread(target=work, daemon=True).start()

    def _sync_done(self, r: dict) -> None:
        ru = self.lang() == "ru"
        if r.get("need_install") and (r.get("tool") or "gh") == "gh":
            cmd = r.get("command") or "winget install GitHub.cli"
            if ru:
                msg = "Нет GitHub CLI (gh).\n\nУстановить?\n\n" + cmd
            else:
                msg = "GitHub CLI (gh) is missing.\n\nInstall now?\n\n" + cmd
            if messagebox.askyesno("SYNC / gh", msg):
                self.status("ставим gh…" if ru else "installing gh…")
                inst = core.run_install_command(cmd)
                if not inst.get("ok"):
                    self.status(inst.get("error") or "gh install fail")
                    messagebox.showerror("SYNC / gh", inst.get("error") or "install failed")
                    return
                auth = core.gh_auth_status()
                if auth.get("missing"):
                    self.status("gh still missing after install")
                    return
                if not auth.get("ok"):
                    if ru:
                        hint = (
                            "gh установлен. Войди: gh auth login\n"
                            "(браузер / device flow). Токены в приложение не вставлять."
                        )
                    else:
                        hint = (
                            "gh installed. Sign in: gh auth login\n"
                            "(browser / device flow). Do not paste tokens into the app."
                        )
                    self.status("gh needs login")
                    messagebox.showinfo("SYNC / gh auth", hint)
                    return
                self.sync_net()
                return
            self.status(r.get("error") or "gh required")
            return
        if r.get("need_login"):
            hint = r.get("hint") or "gh auth login"
            messagebox.showinfo("SYNC / gh auth", hint)
            self.status("gh auth login needed")
            return
        if r.get("need_install") and r.get("tool") == "rclone":
            url = r.get("url") or "https://rclone.org/install/"
            if ru:
                msg = "rclone не найден. Открыть инструкцию?\n" + url
            else:
                msg = "rclone not found. Open install docs?\n" + url
            if messagebox.askyesno("SYNC / rclone", msg):
                import webbrowser
                webbrowser.open(url)
            self.status(r.get("error") or "rclone missing")
            return

        pull = r.get("pull") or {}
        push = r.get("push") or {}
        if pull.get("ok"):
            self.reload()
            core.persist_library(self.cfg, self.cats)
            merged = pull.get("merged")
            push_bit = ""
            if push.get("pushed"):
                push_bit = " · push ok"
            elif push.get("error"):
                push_bit = " · push: " + str(push.get("error"))[:80]
            self.status(
                ("sync ok · импорт " if ru else "sync ok · imported ")
                + str(merged)
                + push_bit
            )
            return

        err = r.get("error") or pull.get("error") or push.get("error") or "no meta yet"
        if push.get("pushed"):
            self.status("dump+push ok · pull: " + str(err))
        else:
            self.status(("dump сохранён · " if ru else "dump saved · ") + str(err))

    def import_meta(self) -> None:
        path = filedialog.askopenfilename(title="Import dump JSON", filetypes=[("JSON", "*.json"), ("All", "*.*")])
        if not path:
            return
        r = core.import_meta_file(path)
        if not r.get("ok"):
            bf_futa.log("error", "import", "IMPORT FAIL", r.get("error") or "fail", path=path)
            self.status(r.get("error") or "import fail")
            return
        self.reload()
        core.persist_library(self.cfg, self.cats)
        linked = 0
        for cat in self.cats:
            for unit in cat.get("units") or []:
                if unit.get("sourceUrl") or unit.get("updateUrl") or unit.get("wingetId") or unit.get("homepage"):
                    linked += 1
        self.status("imported " + str(r.get("merged")) + " · linked " + str(linked))

    def apply_library(self, path: str, create: bool = False) -> bool:
        r = core.set_library(self.cfg, path, create=create)
        if not r.get("ok"):
            self.status(r.get("error") or "library fail")
            bf_futa.log("error", "library", "LIB FAIL", r.get("error") or "", path=str(path))
            return False
        self.cfg = core.load_config()
        self.lbl_root.configure(text=str(core.library_root(self.cfg)))
        bf_futa.log("info", "library", "LIB SET", r.get("path") or str(path), "scan follows")
        self.scan()
        return True

    def select_library(self) -> None:
        path = filedialog.askdirectory(title="Library folder — anywhere")
        if not path:
            return
        self.apply_library(path, create=False)

    def new_pack(self) -> None:
        parent = filedialog.askdirectory(title="Where to create the new pack")
        if not parent:
            return
        dest = Path(parent) / core.MASS_NAME
        n = 1
        while dest.exists():
            try:
                if not any(dest.iterdir()):
                    break
            except OSError:
                break
            n += 1
            dest = Path(parent) / f"{core.MASS_NAME}_{n}"
        if not self.apply_library(dest, create=True):
            return
        core.open_path(dest)
        self.status("pack ready · drop files here → " + str(dest))

    def ensure_library(self) -> None:
        if not core.need_library_pick(self.cfg):
            return
        ru = self.lang() == "ru"
        box = tk.Toplevel(self.root)
        box.title("library")
        box.configure(bg=BG)
        box.transient(self.root)
        box.grab_set()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        w, h = 520, 240
        box.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")
        tk.Label(box, text="LIBRARY", fg=LIME, bg=BG, font=("Consolas", self.fs_big, "bold")).pack(anchor="w", padx=20, pady=(18, 6))
        msg = (
            "Путь не выбран. Папка может быть где угодно — диск, флешка, другой том.\nSELECT — взять существующую. NEW PACK — создать _FutaMass и открыть её."
            if ru
            else
            "No library path yet. It can live anywhere — disk, USB, another volume.\nSELECT an existing folder, or NEW PACK to create _FutaMass and open it."
        )
        tk.Label(box, text=msg, fg=TEXT, bg=BG, font=("Consolas", self.fs), justify="left", wraplength=480).pack(anchor="w", padx=20)
        row = tk.Frame(box, bg=BG)
        row.pack(pady=20)

        def do_sel():
            box.destroy()
            self.select_library()

        def do_new():
            box.destroy()
            self.new_pack()

        self._btn(row, "SELECT", do_sel, accent=CYAN).pack(side="left", padx=8)
        self._btn(row, "NEW PACK", do_new, primary=True).pack(side="left", padx=8)
        box.protocol("WM_DELETE_WINDOW", box.destroy)

    def open_root(self) -> None:
        core.open_path(core.library_root(self.cfg))

    def copy_root(self) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(str(core.library_root(self.cfg)))
        self.status("copied")

    def _lib_frame(self) -> None:
        fr = tk.Frame(self.body, bg=BG)
        self.frames["lib"] = fr
        pane = ttk.Panedwindow(fr, orient=tk.HORIZONTAL)
        pane.pack(fill="both", expand=True)
        side = tk.Frame(pane, bg="#16141c", width=self.px(220))
        mid = tk.Frame(pane, bg=BG)
        right = tk.Frame(pane, bg="#16141c", width=self.px(280))
        side.pack_propagate(False)
        right.pack_propagate(False)
        pane.add(side, weight=0)
        pane.add(mid, weight=1)
        pane.add(right, weight=0)
        self.lib_pane = pane
        self._btn(side, "HOME", self.go_home).pack(fill="x", padx=8, pady=8)
        tk.Label(side, text="FILTER", fg=LIME, bg="#16141c", font=("Consolas", self.fs)).pack(anchor="w", padx=8)
        self.cat_box = tk.Frame(side, bg="#16141c")
        self.cat_box.pack(fill="both", expand=True, padx=4, pady=4)
        self._btn(side, "+ ADD FOLDER", self.add_folder).pack(fill="x", padx=8, pady=8)
        bar = tk.Frame(mid, bg=BG)
        bar.pack(fill="x", padx=8, pady=6)
        self.lbl_crumb = tk.Label(bar, text="HOME", fg=TEXT, bg=BG, font=("Consolas", self.fs))
        self.lbl_crumb.pack(side="left")
        self._btn(bar, "OPEN FOLDER", self.open_cat_folder).pack(side="left", padx=4)
        self._btn(bar, "ADD FILE", self.add_file).pack(side="left", padx=4)
        self.units_box = tk.Frame(mid, bg=BG)
        self.units_box.pack(fill="both", expand=True)
        self.units_canvas = tk.Canvas(self.units_box, bg=BG, highlightthickness=0, bd=0)
        self.units_scroll = ttk.Scrollbar(self.units_box, orient="vertical", command=self.units_canvas.yview, style="Depot.Vertical.TScrollbar")
        self.units_inner = tk.Frame(self.units_canvas, bg=BG)
        self._units_win = self.units_canvas.create_window((0, 0), window=self.units_inner, anchor="nw")
        self.units_canvas.configure(yscrollcommand=self.units_scroll.set)
        self.units_canvas.pack(side="left", fill="both", expand=True)
        self.units_scroll.pack(side="right", fill="y")
        self.units_inner.bind("<Configure>", lambda e: self.units_canvas.configure(scrollregion=self.units_canvas.bbox("all")))

        def on_canvas_cfg(e):
            self.units_canvas.itemconfigure(self._units_win, width=max(e.width, 1))
            self._schedule_grid()

        self.units_canvas.bind("<Configure>", on_canvas_cfg)

        def wheel(ev):
            steps = -1 if getattr(ev, "delta", 0) > 0 or getattr(ev, "num", 0) == 4 else 1
            if getattr(ev, "delta", 0) and abs(ev.delta) > 120:
                steps = int(-ev.delta / 120)
            self.units_canvas.yview_scroll(steps, "units")

        self.units_canvas.bind("<Enter>", lambda e: self.units_canvas.bind_all("<MouseWheel>", wheel))
        self.units_canvas.bind("<Leave>", lambda e: self.units_canvas.unbind_all("<MouseWheel>"))
        self.units_canvas.bind("<Button-4>", wheel)
        self.units_canvas.bind("<Button-5>", wheel)
        pager = tk.Frame(mid, bg=BG)
        pager.pack(fill="x", pady=4)
        self.lbl_page = tk.Label(pager, text="", fg=DIM, bg=BG, font=("Consolas", self.fs))
        self.lbl_page.pack(side="left", padx=8)
        self.detail = right
        self.root.bind("<Configure>", self._on_resize)
        self.root.after(120, self._place_sashes)

    def _place_sashes(self) -> None:
        pane = getattr(self, "lib_pane", None)
        if pane is None:
            return
        try:
            w = pane.winfo_width()
            if w < 200:
                self.root.after(80, self._place_sashes)
                return
            pane.sashpos(0, self.px(220))
            pane.sashpos(1, max(self.px(500), w - self.px(280)))
        except tk.TclError:
            pass
        self._regrid_units()

    def _sort_frame(self) -> None:
        fr = tk.Frame(self.body, bg=BG)
        self.frames["sort"] = fr
        pane = ttk.Panedwindow(fr, orient=tk.HORIZONTAL)
        pane.pack(fill="both", expand=True)
        side = tk.Frame(pane, bg="#16141c", width=self.px(220))
        mid = tk.Frame(pane, bg=BG)
        right = tk.Frame(pane, bg="#16141c", width=self.px(300))
        side.pack_propagate(False)
        right.pack_propagate(False)
        pane.add(side, weight=0)
        pane.add(mid, weight=1)
        pane.add(right, weight=0)
        tk.Label(side, text="AUTOSORT", fg=LIME, bg="#16141c", font=("Consolas", self.fs_big)).pack(anchor="w", padx=8, pady=8)
        self.sort_btns = tk.Frame(side, bg="#16141c")
        self.sort_btns.pack(fill="both", expand=True, padx=6, pady=4)
        self.sort_box = tk.Frame(mid, bg=BG)
        self.sort_box.pack(fill="both", expand=True)
        self.sort_detail = right

    def _store_frame(self) -> None:
        fr = tk.Frame(self.body, bg=BG)
        self.frames["store"] = fr
        bar = tk.Frame(fr, bg=BG)
        bar.pack(fill="x", padx=8, pady=8)
        tk.Label(bar, text="NET INSTALL", fg=LIME, bg=BG, font=("Consolas", self.fs_big)).pack(side="left")
        self.store_q = tk.Entry(bar, bg=FILL, fg=TEXT, insertbackground=TEXT, relief="flat", font=("Consolas", self.fs))
        self.store_q.pack(side="left", padx=8, fill="x", expand=True, ipady=6)
        self.store_q.bind("<Return>", lambda e: self.fill_store())
        self._btn(bar, "SEARCH", self.fill_store, primary=True).pack(side="left")
        self.store_box = tk.Frame(fr, bg=BG)
        self.store_box.pack(fill="both", expand=True, padx=8)
        pager = tk.Frame(fr, bg=BG)
        pager.pack(fill="x", pady=4)
        self._btn(pager, "PREV", lambda: self.flip_store(-1)).pack(side="left", padx=8)
        self.lbl_store_page = tk.Label(pager, text="1 / 1", fg=DIM, bg=BG, font=("Consolas", self.fs))
        self.lbl_store_page.pack(side="left")
        self._btn(pager, "NEXT", lambda: self.flip_store(1)).pack(side="left", padx=8)

    def _paths_frame(self) -> None:
        fr = tk.Frame(self.body, bg=BG)
        self.frames["paths"] = fr
        tk.Label(fr, text="PATHS", fg=LIME, bg=BG, font=("Consolas", self.fs_big)).pack(anchor="w", padx=12, pady=8)
        self.paths_box = tk.Frame(fr, bg=BG)
        self.paths_box.pack(fill="both", expand=True, padx=12)
        self._btn(fr, "SAVE", self.save_paths, primary=True).pack(anchor="w", padx=12, pady=8)

    def _inst_frame(self) -> None:
        fr = tk.Frame(self.body, bg=BG)
        self.frames["inst"] = fr
        tk.Label(fr, text="INSTALLED BY THIS APP", fg=LIME, bg=BG, font=("Consolas", self.fs_big)).pack(anchor="w", padx=12, pady=8)
        self.inst_box = tk.Frame(fr, bg=BG)
        self.inst_box.pack(fill="both", expand=True, padx=12, pady=8)

    def _set_frame(self) -> None:
        fr = tk.Frame(self.body, bg=BG)
        self.frames["set"] = fr
        tk.Label(fr, text="SETTINGS", fg=LIME, bg=BG, font=("Consolas", self.fs_big)).pack(anchor="w", padx=12, pady=8)
        split = tk.Frame(fr, bg=BG)
        split.pack(fill="both", expand=True, padx=12)
        form = tk.Frame(split, bg=BG, width=self.px(520))
        form.pack(side="left", fill="y", padx=(0, 16))
        form.pack_propagate(False)
        right = tk.Frame(split, bg=BG)
        right.pack(side="left", fill="both", expand=True)
        tk.Label(form, text="library root  (relative = portable)", fg=DIM, bg=BG, font=("Consolas", self.fs)).pack(anchor="w")
        row = tk.Frame(form, bg=BG)
        row.pack(fill="x", pady=4)
        self.ent_root = tk.Entry(row, bg=FILL, fg=TEXT, insertbackground=TEXT, relief="flat", font=("Consolas", self.fs), width=42)
        self.ent_root.pack(side="left", ipady=6)
        self._btn(row, "BROWSE", self.browse_root).pack(side="left", padx=4)
        self.auto_var = tk.BooleanVar(value=False)
        tk.Checkbutton(form, text="autostart with Windows", variable=self.auto_var, fg=TEXT, bg=BG, selectcolor=FILL, activebackground=BG, font=("Consolas", self.fs)).pack(anchor="w", pady=4)
        self.quiet_var = tk.BooleanVar(value=True)
        tk.Checkbutton(form, text="quiet auto-update on start", variable=self.quiet_var, fg=TEXT, bg=BG, selectcolor=FILL, activebackground=BG, font=("Consolas", self.fs)).pack(anchor="w", pady=4)
        tk.Label(form, text="update channel URL", fg=DIM, bg=BG, font=("Consolas", self.fs)).pack(anchor="w")
        self.ent_ver = tk.Entry(form, bg=FILL, fg=TEXT, insertbackground=TEXT, relief="flat", font=("Consolas", self.fs), width=48)
        self.ent_ver.pack(anchor="w", pady=4, ipady=6)
        tk.Label(form, text="Drive meta URL", fg=DIM, bg=BG, font=("Consolas", self.fs)).pack(anchor="w")
        self.ent_meta = tk.Entry(form, bg=FILL, fg=TEXT, insertbackground=TEXT, relief="flat", font=("Consolas", self.fs), width=48)
        self.ent_meta.pack(anchor="w", pady=4, ipady=6)
        tk.Label(form, text="Drive folder", fg=DIM, bg=BG, font=("Consolas", self.fs)).pack(anchor="w")
        self.ent_folder = tk.Entry(form, bg=FILL, fg=TEXT, insertbackground=TEXT, relief="flat", font=("Consolas", self.fs), width=48)
        self.ent_folder.pack(anchor="w", pady=4, ipady=6)
        btns = tk.Frame(form, bg=BG)
        btns.pack(anchor="w", pady=10)
        self._btn(btns, "UPDATE", self.manual_update).pack(side="left", padx=4)
        self._btn(btns, "COMPRESS SIZE", self.do_compress, accent=ORANGE).pack(side="left", padx=4)
        self._btn(btns, "COPY TO…", self.do_copy_to, accent=CYAN).pack(side="left", padx=4)
        self._btn(btns, "? HELP", self.show_help).pack(side="left", padx=4)
        self._btn(btns, "SAVE", self.save_settings, primary=True).pack(side="left", padx=4)
        self.bf_box = tk.Frame(form, bg=BG)
        self.bf_box.pack(anchor="w", pady=(18, 4))
        bf = bf_futa.get()
        if bf:
            bf.attach_checkbox(self.bf_box, "B F Futa")
        tk.Label(right, text="copy FULL library onto a drive — does not format", fg=DIM, bg=BG, font=("Consolas", self.fs)).pack(anchor="w")
        self.drive_box = tk.Frame(right, bg=BG)
        self.drive_box.pack(fill="both", expand=True, pady=4)

    def _wincfg_frame(self) -> None:
        fr = tk.Frame(self.body, bg=BG)
        self.frames["wincfg"] = fr
        tk.Label(fr, text="WINDOWS SETTINGS SNAPSHOT", fg=LIME, bg=BG, font=("Consolas", self.fs_big)).pack(anchor="w", padx=12, pady=8)
        tk.Label(
            fr,
            text="Copies Explorer / theme / power / pins / wallpaper / profile picture / Wi-Fi profiles. Not passwords, not SAM.",
            fg=DIM,
            bg=BG,
            font=("Consolas", self.fs),
            wraplength=self.px(900),
            justify="left",
        ).pack(anchor="w", padx=12)
        row = tk.Frame(fr, bg=BG)
        row.pack(fill="x", padx=12, pady=8)
        self._btn(row, "SNAPSHOT NOW", self.do_win_snap, primary=True).pack(side="left", padx=4)
        self._btn(row, "APPLY SELECTED", self.do_win_apply, accent=CYAN).pack(side="left", padx=4)
        self._btn(row, "OPEN FOLDER", lambda: core.open_path(win_cfg.snap_dir(core.APP_DIR))).pack(side="left", padx=4)
        self.lbl_snap = tk.Label(fr, text="", fg=DIM, bg=BG, font=("Consolas", self.fs))
        self.lbl_snap.pack(anchor="w", padx=12)
        wrap = tk.Frame(fr, bg=BG)
        wrap.pack(fill="both", expand=True, padx=12, pady=8)
        self.wincfg_canvas = tk.Canvas(wrap, bg=BG, highlightthickness=0)
        sy = tk.Scrollbar(wrap, orient="vertical", command=self.wincfg_canvas.yview)
        self.wincfg_box = tk.Frame(self.wincfg_canvas, bg=BG)
        self.wincfg_box.bind("<Configure>", lambda e: self.wincfg_canvas.configure(scrollregion=self.wincfg_canvas.bbox("all")))
        self.wincfg_canvas.create_window((0, 0), window=self.wincfg_box, anchor="nw")
        self.wincfg_canvas.configure(yscrollcommand=sy.set)
        self.wincfg_canvas.pack(side="left", fill="both", expand=True)
        sy.pack(side="right", fill="y")
        self.win_vars = {}

    def fill_wincfg(self) -> None:
        for w in self.wincfg_box.winfo_children():
            w.destroy()
        self.win_vars = {}
        man = win_cfg.load_manifest(core.APP_DIR)
        at = man.get("at") or "no snapshot yet"
        machine = man.get("machine") or "—"
        user = man.get("user") or "—"
        self.lbl_snap.configure(text=f"{at}  ·  {machine}  ·  {user}")
        items = man.get("items") or []
        if not items:
            tk.Label(self.wincfg_box, text="Press SNAPSHOT NOW on this Windows PC.", fg=DIM, bg=BG, font=("Consolas", self.fs)).pack(anchor="w")
            return
        groups = []
        for it in items:
            g = it.get("group") or "Other"
            if g not in groups:
                groups.append(g)
        for g in groups:
            tk.Label(self.wincfg_box, text=g.upper(), fg=LIME, bg=BG, font=("Consolas", self.fs_big)).pack(anchor="w", pady=(10, 2))
            for it in items:
                if (it.get("group") or "Other") != g:
                    continue
                self._wincfg_row(it)

    def _wincfg_row(self, it: dict) -> None:
        var = tk.BooleanVar(value=True)
        self.win_vars[it.get("id") or it.get("title")] = var
        row = tk.Frame(self.wincfg_box, bg=FILL, highlightthickness=1, highlightbackground=LINE)
        row.pack(fill="x", pady=2, ipady=4)
        tk.Checkbutton(row, variable=var, bg=FILL, activebackground=FILL, selectcolor=FILL, fg=TEXT).pack(side="left", padx=6)
        col = tk.Frame(row, bg=FILL)
        col.pack(side="left", fill="x", expand=True)
        tk.Label(col, text=it.get("title") or it.get("id"), fg=TEXT, bg=FILL, anchor="w", font=("Consolas", self.fs)).pack(fill="x")
        tk.Label(col, text=str(it.get("value") or "—"), fg=DIM, bg=FILL, anchor="w", font=("Consolas", max(8, self.fs - 1))).pack(fill="x")
        preview = it.get("preview")
        if preview:
            img_path = win_cfg.snap_dir(core.APP_DIR) / preview

            def enter(e, p=str(img_path), cap=it.get("title") or ""):
                self.tip.show_img(p, e.x_root, e.y_root, cap)

            def leave(_=None):
                self.tip.hide()

            for w in (row, col, *col.winfo_children()):
                w.bind("<Enter>", enter)
                w.bind("<Leave>", leave)

    def do_win_snap(self) -> None:
        self.status("snapshot…")

        def work():
            r = win_cfg.snapshot(core.APP_DIR)
            def done():
                self.fill_wincfg()
                self.status("snapshot " + str(r.get("count")) + " items  " + (r.get("at") or "") if r.get("ok") else r.get("error") or "fail")
            self.root.after(0, done)

        threading.Thread(target=work, daemon=True).start()

    def do_win_apply(self) -> None:
        ids = [k for k, v in self.win_vars.items() if v.get()]
        if not ids:
            self.status("nothing selected")
            return
        if not messagebox.askokcancel("Apply Windows settings", "Apply " + str(len(ids)) + " selected items to THIS Windows profile?"):
            return
        r = win_cfg.apply_items(core.APP_DIR, ids)
        msg = "applied " + str(len(r.get("applied") or []))
        if r.get("errors"):
            msg += " · " + "; ".join(r["errors"][:4])
        self.status(msg)

    def _box_frame(self) -> None:
        fr = tk.Frame(self.body, bg=BG)
        self.frames["box"] = fr
        tk.Label(fr, text="TOOLBOX", fg=LIME, bg=BG, font=("Consolas", self.fs_big)).pack(anchor="w", padx=12, pady=8)
        row = tk.Frame(fr, bg=BG)
        row.pack(fill="x", padx=12, pady=4)
        self.ent_proxy = tk.Entry(row, bg=FILL, fg=TEXT, insertbackground=TEXT, relief="flat", font=("Consolas", self.fs))
        self.ent_proxy.pack(side="left", fill="x", expand=True, ipady=6)
        self.proxy_on = tk.BooleanVar(value=False)
        tk.Checkbutton(row, text="PROXY ON", variable=self.proxy_on, fg=TEXT, bg=BG, selectcolor=FILL, font=("Consolas", self.fs)).pack(
            side="left", padx=6
        )
        self._btn(row, "SAVE", self.save_proxy, primary=True).pack(side="left")
        grid = tk.Frame(fr, bg=BG)
        grid.pack(fill="both", expand=True, padx=12, pady=12)
        pages = [("DEFENDER", "defender"), ("ACTIVATION", "activation"), ("NETWORK", "network"), ("UPDATE", "update"), ("STARTUP", "startup")]
        for i, (label, page) in enumerate(pages):
            b = self._btn(grid, label, lambda p=page: self.win_page(p))
            b.grid(row=i // 3, column=i % 3, padx=8, pady=8, sticky="nsew")
            grid.grid_columnconfigure(i % 3, weight=1)
        self._btn(grid, "GHOST", lambda: self.status("Ghost Mode slot empty")).grid(row=1, column=2, padx=8, pady=8, sticky="nsew")

    def tile_metrics(self, box: tk.Frame, count: int):
        w = box.winfo_width()
        h = box.winfo_height()
        if w < 80:
            w = max(self.root.winfo_width() - self.px(80), 900)
        if h < 80:
            h = max(self.root.winfo_height() - self.px(180), 500)
        tw, th = self.px(132), self.px(96)
        cols = max(2, w // (tw + self.px(10)))
        rows = max(1, h // (th + self.px(10)))
        per = max(1, cols * rows)
        return cols, per, tw, th

    def flip(self, delta: int) -> None:
        self.page = max(0, self.page + delta)
        self.render_lib()

    def flip_store(self, delta: int) -> None:
        self.store_page = max(0, self.store_page + delta)
        self.fill_store(keep_page=True)

    def _mass(self):
        return next((c for c in self.cats if c["id"] == "MASS"), None)

    def _pool_and_items(self):
        mass = self._mass()
        pool = list((mass or {}).get("units") or [])
        labels = {
            "game": "Games",
            "save": "Saves",
            "script": "Scripts",
            "installer": "Installers",
            "portable": "Portable",
            "archive": "Archives",
            "doc": "Docs",
            "empty": "Unknown",
            "unknown": "Unknown",
        }
        if self.current and self.current != "MASS":
            cat = next((c for c in self.cats if c["id"] == self.current), None)
            return mass, pool, labels, (cat["units"] if cat else []), cat
        items = pool
        if self.filter_kind:
            items = [u for u in pool if (u.get("kind") or "unknown") == self.filter_kind]
        return mass, pool, labels, items, mass

    def _paint_sidebar(self) -> None:
        mass, pool, labels, items, _cat = self._pool_and_items()
        counts = {}
        for u in pool:
            k = u.get("kind") or "unknown"
            counts[k] = counts.get(k, 0) + 1
        sig = (self.current, self.filter_kind, tuple(sorted(counts.items())), tuple(c["id"] for c in self.cats))
        if sig == self._sidebar_sig and self.cat_box.winfo_children():
            return
        self._sidebar_sig = sig
        for w in self.cat_box.winfo_children():
            w.destroy()

        def side_row(title, color, selected, cmd, count=None):
            bg = HOVER if selected else FILL
            row = tk.Frame(self.cat_box, bg=bg, cursor="hand2", highlightthickness=1, highlightbackground=color)
            row.pack(fill="x", pady=3, ipady=8)
            tk.Frame(row, bg=color, width=self.px(8)).pack(side="left", fill="y")
            lab = tk.Label(row, text="  " + title + (" >" if selected else ""), fg=TEXT, bg=bg, anchor="w", font=("Consolas", self.fs), cursor="hand2")
            lab.pack(side="left", fill="x", expand=True)
            if count is not None:
                tk.Label(row, text=str(count) + "  ", fg=MUTED, bg=bg, cursor="hand2").pack(side="right")
            for w in (row, *row.winfo_children()):
                w.bind("<Button-1>", lambda e, fn=cmd: fn())

        side_row("HOME", LIME, self.current is None and not self.filter_kind, self.go_home, len(pool))
        for kind in ("game", "save", "script", "installer", "portable", "archive", "doc", "empty"):
            if counts.get(kind):
                side_row(
                    labels[kind],
                    core.KIND_COLOR.get(kind, LINE),
                    self.filter_kind == kind,
                    lambda k=kind: self.set_filter(k),
                    counts.get(kind, 0),
                )
        for cat in self.cats:
            if cat["id"] == "MASS":
                continue
            side_row(cat["id"], LINE, self.current == cat["id"], lambda c=cat["id"]: self.open_cat(c), len(cat["units"]))
        plus = tk.Frame(self.cat_box, bg=FILL, cursor="hand2", highlightthickness=1, highlightbackground=LIME)
        plus.pack(fill="x", pady=3, ipady=8)
        tk.Label(plus, text="  +  group", fg=LIME, bg=FILL, anchor="w", font=("Consolas", self.fs), cursor="hand2").pack(fill="x")
        plus.bind("<Button-1>", lambda e: self.add_group())
        plus.winfo_children()[0].bind("<Button-1>", lambda e: self.add_group())

    def _paint_grid(self, keep_detail: bool = False) -> None:
        mass, pool, labels, items, cat = self._pool_and_items()
        if self.current and self.current != "MASS":
            self.lbl_crumb.configure(text=self.current)
        elif self.filter_kind:
            self.lbl_crumb.configure(text=labels.get(self.filter_kind, self.filter_kind))
        else:
            self.lbl_crumb.configure(text="HOME")
        held = self.unit if keep_detail else None
        if not keep_detail:
            for w in self.detail.winfo_children():
                w.destroy()
        self._fill_unit_tiles(items, cat or mass)
        self.lbl_page.configure(text=str(len(items)) + " items")
        if held:
            self.open_unit(held)

    def _fill_unit_tiles(self, items, cat) -> None:
        sig = tuple((u.get("id"), u.get("filePath"), u.get("kind"), u.get("iconPath")) for u in items)
        if sig == self._units_sig and self._unit_cells:
            self._grid_cols = 0
            self._regrid_units()
            return
        self._units_sig = sig
        for w in self.units_inner.winfo_children():
            w.destroy()
        self._unit_cells = []
        tile = self._tile_size()
        for unit in items:
            cell = tk.Frame(self.units_inner, bg=BG, width=tile, height=tile)
            cell.grid_propagate(False)
            self.unit_tile(cell, cat or {}, unit, tile, tile)
            self._unit_cells.append(cell)
        self._grid_cols = 0
        self._regrid_units()


    def render_lib(self) -> None:
        self._sidebar_sig = None
        self._paint_sidebar()
        self._paint_grid(keep_detail=False)
        if self.unit:
            self.open_unit(self.unit)

    def lang(self) -> str:
        loc = ""
        try:
            loc = (locale.getdefaultlocale()[0] or "")
        except Exception:
            loc = ""
        return "ru" if loc.lower().startswith("ru") else "en"

    def maybe_help(self) -> None:
        if self.cfg.get("seenHelp"):
            return
        self.show_help()

    def dump_prompt(self) -> str:
        path = core.APP_DIR / "docs" / "CHAT_DUMP_PROMPT.md"
        if not path.is_file():
            path = core.APP_DIR / "CHAT_DUMP_PROMPT.md"
        if path.is_file():
            raw = path.read_text(encoding="utf-8")
            if "---" in raw:
                return raw.split("---", 1)[1].strip()
            return raw.strip()
        return "принято, жду данные"

    def copy_prompt(self) -> None:
        text = self.dump_prompt()
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update()
        self.status("prompt copied")

    def show_help(self) -> None:
        ru = self.lang() == "ru"
        text = (
            "1. Кидай файлы и папки в _FutaMass (кнопка OPEN).\n"
            "2. SCAN — список заполняется.\n"
            "3. Чёрный квадрат = тип неясен. Нужен REPORT.\n"
            "4. REPORT пишет dump с деревом каждой папки — его в чат.\n"
            "5. COPY PROMPT — промпт 0.1.46, старый не использовать.\n"
            "6. Первый ответ того чата: принято, жду данные.\n"
            "7. Кидаешь JSON. Когда вернёт мета — SYNC или IMPORT.\n"
            "8. Плюс слева — новая группа.\n"
            "9. Вкладка AUTOSORT — те же файлы по цветам, на диске не двигает. Слева цвет = фильтр списка."
            if ru
            else
            "1. Drop files into _FutaMass (OPEN).\n"
            "2. SCAN fills the list.\n"
            "3. Black square = unknown type. Make a REPORT.\n"
            "4. REPORT writes depot-dump-latest.json — send that to chat.\n"
            "5. COPY PROMPT copies the new-chat prompt.\n"
            "6. That chat first line: принято, жду данные.\n"
            "7. Drop the JSON. Then SYNC or IMPORT.\n"
            "8. Plus on the left adds a group."
        )
        win = tk.Toplevel(self.root)
        win.title("HELP" if not ru else "СПРАВКА")
        win.configure(bg=BG)
        win.geometry("560x420")
        tk.Label(win, text=text, fg=TEXT, bg=BG, justify="left", font=("Consolas", self.fs)).pack(anchor="w", padx=16, pady=12)
        self._btn(win, "COPY PROMPT", self.copy_prompt, primary=True).pack(anchor="w", padx=16, pady=8)
        self._btn(win, "CLOSE", win.destroy).pack(anchor="w", padx=16, pady=4)
        self.cfg["seenHelp"] = True
        core.save_config(self.cfg)

    def do_autosort(self) -> None:
        if not messagebox.askokcancel(
            "AUTOSORT",
            "Move items from MASS into Games / Saves / Scripts / Installers / Portable / Archives / Unknown?",
        ):
            return
        r = core.autosort_mass(self.cfg)
        self.scan()
        self.status("sorted " + str(r.get("moved") or 0))

    def add_group(self) -> None:
        name = simpledialog.askstring("group", "name")
        if not name:
            return
        path = filedialog.askdirectory(title="group folder")
        if not path:
            return
        extras = self.cfg.setdefault("addedCategories", [])
        extras.append({"id": name.strip(), "root": path, "target": ""})
        core.save_config(self.cfg)
        self.scan()

    def type_color(self, unit: dict) -> str:
        kind = (unit.get("kind") or "unknown").lower()
        if unit.get("hasSaves") and kind == "game":
            kind = "game"
        if kind == "save" or (unit.get("hasSaves") and kind not in {"game", "installer"}):
            kind = "save"
        return core.KIND_COLOR.get(kind, core.KIND_COLOR.get("unknown", "#6b7280"))

    def draw_list(self, box, items, cat) -> None:
        self.lbl_page.configure(text=str(len(items)) + " items")
        canvas = tk.Canvas(box, bg=BG, highlightthickness=0)
        bar = tk.Scrollbar(box, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=BG)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=bar.set)
        canvas.pack(side="left", fill="both", expand=True)
        bar.pack(side="right", fill="y")

        def wheel(ev):
            canvas.yview_scroll(-1 if ev.delta > 0 or ev.num == 4 else 1, "units")

        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", wheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
        canvas.bind("<Button-4>", wheel)
        canvas.bind("<Button-5>", wheel)
        tile = self.px(160)
        cols = max(1, (box.winfo_width() or self.px(640)) // (tile + self.px(16)))
        self._grid_cols = cols
        if not items:
            tk.Label(inner, text="empty · drop into _FutaMass · SCAN", fg=DIM, bg=BG, font=("Consolas", self.fs)).pack(anchor="w", padx=12, pady=16)
            return
        for i, unit in enumerate(items):
            cell = tk.Frame(inner, bg=BG, width=tile, height=tile)
            cell.grid(row=i // cols, column=i % cols, padx=6, pady=6)
            cell.grid_propagate(False)
            self.unit_tile(cell, cat or {}, unit, tile, tile)

    def list_row(self, parent, cat, unit) -> None:
        mark = self.type_color(unit)
        row = tk.Frame(parent, bg=FILL, highlightthickness=2, highlightbackground=mark, cursor="hand2")
        row.pack(fill="x", padx=8, pady=3, ipady=6)
        self.icon_slot(row, unit, self.px(36))
        sq = tk.Frame(row, bg=mark, width=self.px(16), height=self.px(16))
        sq.pack(side="left", padx=8)
        sq.pack_propagate(False)
        tk.Label(row, text=unit.get("name") or "?", fg=TEXT, bg=FILL, anchor="w", font=("Consolas", self.fs)).pack(side="left", fill="x", expand=True)
        tk.Label(row, text=unit.get("kind") or "", fg=DIM, bg=FILL, font=("Consolas", max(8, self.fs - 2))).pack(side="right", padx=8)
        tip = f"{unit.get('name')}\n{unit.get('file')}\n{unit.get('kind')} / {unit.get('engine')}\n{unit.get('filePath') or unit.get('folder')}"

        def open_it(_e=None, u=unit):
            self.open_unit(u)
            return "break"

        for w in (row, *row.winfo_children()):
            w.bind("<Button-1>", open_it)
            w.bind("<Enter>", lambda e, t=tip, r=row: (r.configure(bg=HOVER), self.tip.show(t, e.x_root, e.y_root)))
            w.bind("<Leave>", lambda e, r=row: (r.configure(bg=FILL), self.tip.hide()))

    def draw_tiles(self, box, items, page, factory, pager_lbl) -> None:
        cols, per, tw, th = self.tile_metrics(box, len(items))
        pages = max(1, (len(items) + per - 1) // per)
        page = min(page, pages - 1)
        if pager_lbl is self.lbl_page:
            self.page = page
        start = page * per
        chunk = items[start : start + per]
        pager_lbl.configure(text=f"{page + 1} / {pages}   ({len(items)})")
        grid = tk.Frame(box, bg=BG)
        grid.pack(anchor="nw", padx=8, pady=8)
        for i, item in enumerate(chunk):
            cell = tk.Frame(grid, bg=BG, width=tw, height=th)
            cell.grid(row=i // cols, column=i % cols, padx=6, pady=6)
            cell.grid_propagate(False)
            factory(cell, item, tw, th)

    def home_tile(self, parent, cat, tw, th) -> None:
        fr = tk.Frame(parent, bg=FILL, highlightbackground=LIME, highlightthickness=1, cursor="hand2")
        fr.place(relx=0, rely=0, relwidth=1, relheight=1)
        tk.Label(fr, text=cat["id"], fg=LIME, bg=FILL, font=("Consolas", self.fs_big)).pack(pady=(self.px(18), 4))
        tk.Label(fr, text=f"{len(cat['units'])} items", fg=DIM, bg=FILL, font=("Consolas", self.fs)).pack()
        tk.Label(fr, text=cat.get("target") or "path not set", fg=MUTED, bg=FILL, font=("Consolas", max(8, self.fs - 2))).pack(pady=6)
        tip = f"{cat['id']}\nfolder: {cat.get('path')}\ninstall to: {cat.get('target') or '-'}\nitems: {len(cat['units'])}"
        for w in (fr, *fr.winfo_children()):
            w.bind("<Button-1>", lambda e, c=cat["id"]: self.open_cat(c))
            w.bind("<Enter>", lambda e, t=tip: self.tip.show(t, e.x_root, e.y_root))
            w.bind("<Leave>", lambda e: self.tip.hide())
            self.hoverize(w)

    def unit_tile(self, parent, cat, unit, tw, th) -> None:
        mark = self.type_color(unit)
        fr = tk.Frame(parent, bg=FILL, highlightbackground=mark, highlightthickness=2, cursor="hand2")
        fr.place(relx=0, rely=0, relwidth=1, relheight=1)
        top = tk.Frame(fr, bg=FILL)
        top.pack(fill="x", padx=6, pady=6)
        self.icon_slot(top, unit, self.px(40))
        wrap = max(80, tw - self.px(56))
        name_lab = tk.Label(
            top,
            text=unit.get("name") or "?",
            fg=TEXT,
            bg=FILL,
            font=("Consolas", max(8, self.fs - 1)),
            anchor="w",
            justify="left",
            wraplength=wrap,
            cursor="hand2",
        )
        name_lab.pack(side="left", fill="x", expand=True, padx=4)
        size = self.file_size(unit)
        tk.Label(fr, text=f"{unit.get('kind') or '-'}  ·  {size}", fg=mark, bg=FILL, font=("Consolas", max(8, self.fs - 2))).pack()
        tk.Label(fr, text=unit.get("file") or "-", fg=MUTED, bg=FILL, font=("Consolas", max(8, self.fs - 2)), wraplength=tw - 16).pack(pady=2)
        tip = (
            f"{unit.get('name')}\n"
            f"file: {unit.get('file') or '-'}\n"
            f"size: {size}\n"
            f"kind: {unit.get('kind')}\n"
            f"engine: {unit.get('engine')}\n"
            f"silent: {'yes' if unit.get('silent') else 'no'}\n"
            f"source: {unit.get('filePath') or unit.get('folder')}\n"
            f"icon: click then Ctrl+V"
        )
        def open_only(e=None, u=unit):
            self.open_unit(u)
            return "break"
        fr.bind("<Button-1>", open_only)
        for w in (fr, top, *top.winfo_children(), *fr.winfo_children()):
            if w is name_lab:
                continue
            w.bind("<Button-1>", open_only)
        name_lab.bind("<Button-1>", lambda e, u=unit, lab=name_lab, p=top: (self.open_unit(u), self.begin_rename(u, lab, p)))
        fr.bind("<Enter>", lambda e, t=tip: self.tip.show(t, e.x_root, e.y_root))
        fr.bind("<Leave>", lambda e: self.tip.hide())

    def icon_photo(self, unit: dict, size: int):
        key = core.unit_key(unit) + ":" + str(size)
        cached = self.photo_keep.get(key)
        if cached is not None:
            return cached
        path = core.cached_icon(unit)
        if path is None or not path.is_file():
            return None
        photo = None
        if Image is not None and ImageTk is not None:
            try:
                img = Image.open(path).convert("RGBA").resize((size, size), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(img)
            except Exception:
                photo = None
        if photo is None:
            try:
                raw = tk.PhotoImage(file=str(path))
                if raw.width() > size > 0:
                    f = max(1, int(round(raw.width() / size)))
                    photo = raw.subsample(f, f)
                else:
                    photo = raw
            except tk.TclError:
                return None
        self.photo_keep[key] = photo
        return photo

    def icon_slot(self, parent, unit: dict, size: int) -> tk.Frame:
        selected = self.icon_target is not None and core.unit_key(self.icon_target) == core.unit_key(unit)
        border = LIME if selected else LINE
        box = tk.Frame(parent, bg=FILL, width=size + 6, height=size + 6, highlightthickness=2, highlightbackground=border, cursor="hand2")
        box.pack(side="left")
        box.pack_propagate(False)
        photo = self.icon_photo(unit, size)
        if photo:
            lab = tk.Label(box, image=photo, bg=FILL)
        else:
            lab = tk.Label(box, text="ICO", fg=MUTED, bg=FILL, font=("Consolas", max(8, self.fs - 2)))
        lab.place(relx=0.5, rely=0.5, anchor="center")

        def pick(e=None, u=unit):
            self.icon_target = u
            self.status("icon selected · Ctrl+V")
        box.bind("<Control-Button-1>", pick)
        lab.bind("<Control-Button-1>", pick)
        return box

    def clipboard_image(self):
        if ImageGrab is None:
            return None
        try:
            grabbed = ImageGrab.grabclipboard()
        except Exception:
            grabbed = None
        if isinstance(grabbed, Image.Image):
            return grabbed.convert("RGBA")
        if isinstance(grabbed, list) and grabbed:
            try:
                return Image.open(grabbed[0]).convert("RGBA")
            except OSError:
                pass
        return None

    def on_paste(self, _ev=None):
        if not self.icon_target:
            return
        self.paste_for(self.icon_target)

    def paste_for(self, unit: dict) -> None:
        if Image is None:
            self.status("pip install pillow")
            return
        self.icon_target = unit
        img = self.clipboard_image()
        if img is None:
            path = filedialog.askopenfilename(
                title="Image for icon",
                filetypes=[("Images", "*.png *.jpg *.jpeg *.webp *.ico *.bmp *.gif"), ("All", "*.*")],
            )
            if not path:
                self.status("clipboard empty")
                return
            try:
                img = Image.open(path).convert("RGBA")
            except OSError as exc:
                self.status(str(exc))
                return
        IconCrop(self, unit, img)

    def file_size(self, unit: dict) -> str:
        p = unit.get("filePath")
        if not p or not Path(p).is_file():
            return "-"
        n = Path(p).stat().st_size
        if n > 1_000_000_000:
            return f"{n/1e9:.2f} GB"
        if n > 1_000_000:
            return f"{n/1e6:.1f} MB"
        return f"{n/1024:.0f} KB"

    def set_filter(self, kind: str) -> None:
        self.filter_kind = kind
        self.current = None
        self.unit = None
        self.page = 0
        self.render_lib()
        self.paint_nav()

    def fill_sort(self) -> None:
        for w in self.sort_btns.winfo_children():
            w.destroy()
        for w in self.sort_box.winfo_children():
            w.destroy()
        mass = next((c for c in self.cats if c["id"] == "MASS"), None)
        pool = list((mass or {}).get("units") or [])
        order = ("game", "save", "script", "installer", "portable", "archive", "doc", "empty", "unknown")
        labels = {
            "game": "Games",
            "save": "Saves",
            "script": "Scripts",
            "installer": "Installers",
            "portable": "Portable",
            "archive": "Archives",
            "doc": "Docs",
            "empty": "Unknown",
            "unknown": "Unknown",
        }
        counts = {}
        for u in pool:
            k = u.get("kind") or "unknown"
            counts[k] = counts.get(k, 0) + 1
        if self.sort_kind is None:
            self.sort_kind = next((k for k in order if counts.get(k)), "game")
        for kind in order:
            n = counts.get(kind, 0)
            if not n:
                continue
            col = core.KIND_COLOR.get(kind, LINE)
            sel = self.sort_kind == kind
            b = tk.Button(
                self.sort_btns,
                text=f"{labels.get(kind, kind)}  {n}",
                command=lambda k=kind: self.set_sort_kind(k),
                bg=col if sel else FILL,
                fg=BG if sel else TEXT,
                activebackground=col,
                relief="flat",
                highlightthickness=2,
                highlightbackground=col,
                anchor="w",
                padx=10,
                pady=8,
                font=("Consolas", self.fs),
                cursor="hand2",
            )
            b.pack(fill="x", pady=3)

        chunk = [u for u in pool if (u.get("kind") or "unknown") == self.sort_kind]
        canvas = tk.Canvas(self.sort_box, bg=BG, highlightthickness=0)
        bar = ttk.Scrollbar(self.sort_box, orient="vertical", command=canvas.yview, style="Depot.Vertical.TScrollbar")
        inner = tk.Frame(canvas, bg=BG)
        win = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=bar.set)
        canvas.pack(side="left", fill="both", expand=True)
        bar.pack(side="right", fill="y")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        def on_cfg(e):
            canvas.itemconfigure(win, width=max(e.width, 1))

        canvas.bind("<Configure>", on_cfg)

        def wheel(ev):
            canvas.yview_scroll(-1 if getattr(ev, "delta", 0) > 0 or getattr(ev, "num", 0) == 4 else 1, "units")

        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", wheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
        inner.grid_columnconfigure(0, weight=1)
        inner.grid_columnconfigure(1, weight=1)
        if not chunk:
            tk.Label(inner, text="empty group", fg=DIM, bg=BG, font=("Consolas", self.fs)).grid(row=0, column=0, sticky="w", padx=12, pady=16)
            return
        for i, unit in enumerate(chunk):
            cell = tk.Frame(inner, bg=BG)
            cell.grid(row=i // 2, column=i % 2, sticky="ew", padx=6, pady=3)
            self.list_row(cell, mass, unit)

    def set_sort_kind(self, kind: str) -> None:
        self.sort_kind = kind
        self.unit = None
        for w in self.sort_detail.winfo_children():
            w.destroy()
        self.fill_sort()
        self.paint_nav()
    def open_cat(self, cid: str) -> None:
        self.current = cid
        self.filter_kind = None
        self.unit = None
        self.page = 0
        self.tip.hide()
        self.render_lib()
        self.push_hist()
        self.paint_nav()

    def inspector_host(self) -> tk.Frame:
        if self.tab == "sort":
            return self.sort_detail
        return self.detail

    def open_unit(self, unit: dict) -> None:
        self.unit = unit
        cat = next((c for c in self.cats if c["id"] == self.current), None)
        if cat is None:
            cat = self._mass() or {"id": "MASS", "units": []}
        self.draw_unit(cat, unit)
        self.status(unit.get("name") or "item")

    def begin_rename(self, unit: dict, label: tk.Label, parent: tk.Widget) -> None:
        old = unit.get("name") or ""
        ent = tk.Entry(parent, bg=FILL, fg=TEXT, insertbackground=TEXT, relief="flat", font=("Consolas", self.fs_big))
        ent.insert(0, old)
        try:
            label.pack_forget()
        except tk.TclError:
            pass
        ent.pack(side="left", fill="x", expand=True, padx=8)
        ent.focus_set()
        ent.select_range(0, "end")

        def commit(_e=None):
            name = ent.get().strip()
            try:
                ent.destroy()
            except tk.TclError:
                return
            if not name or name == old:
                self.open_unit(unit)
                return
            r = core.rename_unit(unit, name, self.cfg)
            lvl = "info" if r.get("ok") else "error"
            bf_futa.log(lvl, "rename", "RENAME", name, r.get("error") or r.get("path") or "", old=old)
            self.status("renamed" if r.get("ok") else r.get("error") or "rename fail")
            self.scan()
            if r.get("ok"):
                for cat in self.cats:
                    for u in cat.get("units") or []:
                        if u.get("name") == r.get("name") or str(u.get("folder") or "").endswith(r.get("name") or "___"):
                            self.open_unit(u)
                            return

        ent.bind("<Return>", commit)
        ent.bind("<Escape>", lambda e: (ent.destroy(), self.open_unit(unit)))

    def clip_txt(self, s: str, n: int = 32) -> str:
        s = str(s or "-")
        if len(s) <= n:
            return s
        if "\\" in s or "/" in s:
            keep = max(8, (n - 1) // 2)
            return s[:keep] + "…" + s[-(n - keep - 1):]
        return s[: n - 1] + "…"

    def hover_full(self, w: tk.Widget, full: str, shown: str) -> None:
        if not full or full == shown:
            return

        def enter(e):
            self.tip.show(full, e.x_root, e.y_root, fg="#c8ff00", bg="#050505", size=max(12, self.fs + 2))

        w.bind("<Enter>", enter)
        w.bind("<Leave>", lambda e: self.tip.hide())

    def draw_unit(self, cat: dict, unit: dict) -> None:
        host = self.inspector_host()
        for w in host.winfo_children():
            w.destroy()
        actions = tk.Frame(host, bg="#16141c")
        actions.pack(side="bottom", fill="x", pady=4)
        split = tk.Frame(host, bg="#16141c")
        split.pack(fill="both", expand=True)
        split.columnconfigure(0, weight=1, uniform="insp")
        split.columnconfigure(1, weight=1, uniform="insp")
        split.rowconfigure(0, weight=1)
        left = tk.Frame(split, bg="#16141c")
        right = tk.Frame(split, bg="#16141c")
        left.grid(row=0, column=0, sticky="nsew", padx=0, pady=6)
        right.grid(row=0, column=1, sticky="nsew", padx=0, pady=6)
        left.grid_propagate(False)
        right.grid_propagate(False)

        def lock_half(e):
            if e.widget is not split:
                return
            half = max(int(e.width / 2), 90)
            left.configure(width=half)
            right.configure(width=half)

        split.bind("<Configure>", lock_half)

        head = tk.Frame(left, bg="#16141c")
        head.pack(fill="x", padx=8)
        self.icon_slot(head, unit, self.px(52))
        name_full = unit.get("name") or "?"
        name_lab = tk.Label(
            head,
            text=self.clip_txt(name_full, 28),
            fg=LIME,
            bg="#16141c",
            font=("Consolas", self.fs_big, "bold"),
            justify="left",
            cursor="hand2",
            anchor="w",
        )
        name_lab.pack(side="left", padx=8, fill="x", expand=True)
        self.hover_full(name_lab, name_full, self.clip_txt(name_full, 28))
        name_lab.bind("<Button-1>", lambda e, u=unit, lab=name_lab, p=head: self.begin_rename(u, lab, p))

        table = tk.Frame(left, bg="#16141c")
        table.pack(fill="x", padx=8, pady=(10, 4))
        table.columnconfigure(1, weight=1)
        fp = unit.get("filePath") or unit.get("folder") or ""
        fname = unit.get("file") or Path(fp).name or "-"
        ext = Path(fname).suffix.lower() or (unit.get("format") or "-")
        src = unit.get("sourceUrl") or unit.get("homepage") or ""
        has_src = bool(src) or bool(unit.get("hasSource"))
        rows = [
            ("name", unit.get("name") or "-", False),
            ("ext", ext, False),
            ("type", str(unit.get("kind") or "-"), False),
            ("size", self.file_size(unit), False),
            ("path", fp or "-", False),
            ("group", str(unit.get("group") or "-"), False),
            ("verified", str(unit.get("verified") or "no"), False),
            ("Source", "YES" if has_src else "NO", True),
        ]
        fs_row = max(12, self.fs + 2)
        for i, (k, v, fat) in enumerate(rows):
            lim = 22 if k == "path" else 26
            shown = self.clip_txt(v, lim)
            tk.Label(table, text=k, fg=DIM, bg="#16141c", font=("Consolas", fs_row), anchor="w").grid(row=i, column=0, sticky="nw", padx=(0, 8), pady=2)
            fg = LIME if fat else TEXT
            font = ("Consolas", fs_row + (2 if fat else 0), "bold")
            lab = tk.Label(table, text=shown, fg=fg, bg="#16141c", font=font, anchor="w", justify="left")
            lab.grid(row=i, column=1, sticky="nw", pady=2)
            self.hover_full(lab, str(v), shown)

        extra = tk.Frame(left, bg="#16141c")
        opened = {"v": False}

        def toggle():
            opened["v"] = not opened["v"]
            if opened["v"]:
                extra.pack(fill="both", expand=True, pady=4)
                tog.configure(text="DETAILS  ▴")
            else:
                extra.pack_forget()
                tog.configure(text="DETAILS  ▾")

        tog = self._btn(left, "DETAILS  ▾", toggle)
        tog.pack(anchor="w", pady=(8, 2))

        if unit.get("tree") is None:
            core.attach_tree(unit)
        more = [
            f"file     {fname}",
            f"run      {unit.get('payloadRel') or fname}",
            f"format   {unit.get('format') or '-'}",
            f"engine   {unit.get('engine') or '-'}",
            f"inside   {unit.get('innerFile') or '-'}  ({unit.get('innerCount') or 0})",
            f"web      {src or '-'}",
            f"update   {unit.get('updateUrl') or unit.get('downloadUrl') or '-'}",
            f"winget   {unit.get('wingetId') or '-'}",
            f"publisher {unit.get('publisher') or '-'}",
            f"import   {unit.get('notes') or '-'}",
            f"flags    {', '.join(unit.get('treeFlags') or []) or '-'}",
        ]
        for line in more:
            shown = self.clip_txt(line, 40)
            lab = tk.Label(extra, text=shown, fg=DIM, bg="#16141c", anchor="w", justify="left", font=("Consolas", max(10, self.fs)))
            lab.pack(fill="x", pady=1)
            self.hover_full(lab, line, shown)
        tree = unit.get("tree") or []
        box = tk.Frame(extra, bg=FILL)
        box.pack(fill="x", pady=4)
        tk.Label(box, text="folder tree", fg=LIME, bg=FILL, anchor="w", font=("Consolas", max(8, self.fs - 1))).pack(fill="x")
        txt = tk.Text(box, height=7, bg=FILL, fg=TEXT, relief="flat", wrap="none", font=("Consolas", max(8, self.fs - 2)))
        txt.pack(fill="x")
        body = "\n".join(tree) if tree else "(empty)"
        if unit.get("treeTruncated"):
            body += "\n… truncated"
        txt.insert("1.0", body)
        txt.configure(state="disabled")
        self._btn(extra, "PASTE ICON", lambda: self.paste_for(unit)).pack(fill="x", pady=3)

        PURPLE = "#a855f7"
        ACID = "#c8ff00"
        ink = tk.Frame(right, bg=PURPLE, highlightthickness=0)
        ink.pack(fill="both", expand=True, padx=2, pady=2)
        inner_n = tk.Frame(ink, bg="#061108")
        inner_n.pack(fill="both", expand=True, padx=3, pady=3)
        note_fs = max(12, int(self.fs * 1.5))
        note = tk.Text(
            inner_n,
            bg="#061108",
            fg=ACID,
            insertbackground=ACID,
            relief="flat",
            wrap="word",
            font=("Consolas", note_fs, "bold"),
            highlightthickness=0,
            padx=8,
            pady=8,
            undo=True,
        )
        note.pack(fill="both", expand=True)
        note.insert("1.0", unit.get("userNote") or "")
        saved = tk.Label(right, text="", fg=LIME, bg="#16141c", font=("Consolas", max(8, self.fs - 2)))
        saved.pack(anchor="w", padx=4)

        def save_note(_e=None):
            text = note.get("1.0", "end-1c")
            core.save_user_note(unit, text)
            saved.configure(text="saved")
            self.status("note saved")
            self.root.after(1200, lambda: saved.configure(text=""))
            return "break"

        def on_ret(e):
            if int(getattr(e, "state", 0)) & 0x0001:
                return None
            return save_note()

        note.bind("<Return>", on_ret)
        note.bind("<FocusOut>", save_note)
        note.bind("<MouseWheel>", lambda e: "break")

        can_run = bool(fp) or bool(unit.get("innerFile")) or bool(unit.get("canLaunch"))
        can_silent = bool(unit.get("silent")) and bool(fp or unit.get("canLaunch"))
        upd = unit.get("updateUrl") or unit.get("downloadUrl") or unit.get("wingetId") or ""
        folder = unit.get("folder") or fp or ""
        self._btn(actions, "OPEN FOLDER", lambda: core.open_path(Path(folder))).pack(fill="x", padx=8, pady=2)
        self._act(actions, "RUN AS-IS", lambda: self.do_run(unit), on=can_run, accent=CYAN)
        self._btn(actions, "COPY TO…", lambda: self.do_copy_to()).pack(fill="x", padx=8, pady=2)
        self._act(actions, "SILENT INSTALL", lambda: self.do_silent(cat, unit), on=can_silent, primary=True)
        self._act(actions, "OPEN SOURCE", lambda: self.do_open_url(src), on=bool(src), accent=BLUE)
        self._act(actions, "GET UPDATE", lambda: self.do_get_update(unit), on=bool(upd), accent=ORANGE)
        groups = [c for c in self.cats if c["id"] != "MASS"]
        if cat and cat.get("id") == "MASS" and groups:
            for g in groups:
                self._btn(actions, "MOVE → " + g["id"], lambda gg=g: self.move_unit(unit, gg)).pack(fill="x", padx=8, pady=1)
        is_zip = (unit.get("format") == "zip") or str(unit.get("file") or "").lower().endswith(".zip")
        self._act(actions, "PACK TO ZIP", lambda: self.do_pack(unit), on=not is_zip)
        self._act(actions, "UNPACK ZIP", lambda: self.do_unpack(unit), on=is_zip)
        self._act(actions, "DELETE", lambda: self.do_delete(cat, unit), on=True, danger=True)

    def _act(self, parent, text, cmd, on=True, primary=False, danger=False, accent=None) -> None:
        if not on:
            tk.Label(parent, text=text + "  ·  off", fg=DIM, bg="#16141c", anchor="w", font=("Consolas", max(8, self.fs - 1))).pack(
                fill="x", padx=10, pady=3
            )
            return
        if danger:
            b = self._btn(parent, text, cmd)
        else:
            b = self._btn(parent, text, cmd, primary=primary, accent=accent)
        b.pack(fill="x", padx=10, pady=3)

    def do_open_url(self, url: str) -> None:
        url = (url or "").strip()
        if not url:
            self.status("no source url — import dump")
            return
        import webbrowser
        webbrowser.open(url)
        self.status("open " + url)

    def do_get_update(self, unit: dict) -> None:
        wid = (unit.get("wingetId") or "").strip()
        url = (unit.get("updateUrl") or unit.get("downloadUrl") or "").strip()
        if wid:
            if not messagebox.askokcancel("winget", "Install / upgrade via winget:\n" + wid):
                return
            self.status("winget " + wid)
            r = core.winget_install(wid)
            self.status("winget ok" if r.get("ok") else (r.get("error") or r.get("err") or "winget fail"))
            return
        self.do_open_url(url)

    def do_run(self, unit: dict) -> None:
        path = unit.get("filePath") or ""
        if path and Path(path).is_file():
            r = core.launch([path], cwd=unit.get("folder") or str(Path(path).parent))
            bf_futa.log("info" if r.get("ok") else "error", "run", "RUN AS-IS", path, r.get("error") or "ok", name=unit.get("name"))
            self.status("run" if r.get("ok") else r.get("error") or "fail")
            return
        if unit.get("innerFile"):
            self.do_unpack_run(unit)
            return
        folder = unit.get("folder")
        if folder and Path(folder).exists():
            core.open_path(Path(folder))
            self.status("opened folder")
            return
        self.status("not a Windows program")

    def do_pack(self, unit: dict) -> None:
        r = core.pack_store(unit)
        self.status("packed " + (r.get("zip") or "") if r.get("ok") else r.get("error") or "pack fail")
        if r.get("ok"):
            self.scan()

    def do_unpack(self, unit: dict) -> None:
        dest = filedialog.askdirectory(title="unpack here")
        if not dest:
            return
        r = core.unpack_store(unit, dest)
        self.status("unpacked" if r.get("ok") else r.get("error") or "unpack fail")
        if r.get("ok"):
            self.scan()

    def do_unpack_run(self, unit: dict) -> None:
        r = core.unpack_store(unit)
        if not r.get("ok"):
            self.status(r.get("error") or "unpack fail")
            return
        dest = Path(r.get("dest") or "")
        inner = dest / unit["innerFile"]
        if not inner.is_file():
            hits = list(dest.rglob(Path(unit["innerFile"]).name)) if dest.is_dir() else []
            inner = hits[0] if hits else inner
        if not inner.is_file():
            self.status("inner missing after unpack")
            return
        r2 = core.launch([str(inner)], cwd=str(inner.parent))
        self.status("run inner" if r2.get("ok") else r2.get("error") or "fail")

    def do_silent(self, cat: dict, unit: dict) -> None:
        if not unit.get("silent"):
            self.status("silent unknown")
            return
        target = (cat or {}).get("target") or ""
        if not target:
            picked = filedialog.askdirectory(title="install here")
            if not picked:
                self.status("no dest")
                return
            target = picked
        dest = Path(target) / unit["id"]
        dest.mkdir(parents=True, exist_ok=True)
        cmd = core.silent_command(unit, dest)
        if not cmd:
            self.status("cannot build silent command")
            return
        if not messagebox.askokcancel("silent install", "Install to:\n" + str(dest)):
            return
        r = core.launch(cmd, cwd=unit.get("folder"))
        if r.get("ok"):
            core.record_install(unit.get("name") or unit.get("id"), str(dest), unit.get("filePath") or "", unit.get("kind") or "")
        self.status("silent start" if r.get("ok") else r.get("error") or "fail")

    def move_unit(self, unit: dict, group: dict) -> None:
        r = core.move_unit(unit, group.get("path") or "")
        self.status("moved" if r.get("ok") else r.get("error") or "fail")
        self.unit = None
        self.scan()

    def do_delete(self, cat: dict, unit: dict) -> None:
        path = str(unit.get("filePath") or unit.get("folder") or "")
        ans = simpledialog.askstring("DELETE", "Type YES to delete from disk:\n" + path)
        if ans != "YES":
            self.status("delete cancelled")
            return
        r = core.delete_unit(cat, unit)
        self.status("deleted" if r.get("ok") else r.get("error") or "fail")
        self.unit = None
        self.reload()

    def do_copy_to(self) -> None:
        dest = filedialog.askdirectory(title="Copy FULL library here")
        if not dest:
            return
        self.status("copying…")
        def work():
            r = core.install_to(dest, self.cfg)
            def done():
                ok = r.get("ok")
                bf_futa.log("info" if ok else "error", "copy", "COPY TO", dest, r.get("error") or r.get("dest") or "")
                self.status("copied " + (r.get("dest") or "") if ok else r.get("error") or "copy fail")
            self.root.after(0, done)
        threading.Thread(target=work, daemon=True).start()

    def fill_installed(self) -> None:
        for w in self.inst_box.winfo_children():
            w.destroy()
        rows = core.load_installed()
        if not rows:
            tk.Label(self.inst_box, text="empty · installs from this app appear here", fg=DIM, bg=BG, font=("Consolas", self.fs)).pack(anchor="w")
            return
        for i, row in enumerate(rows):
            line = tk.Frame(self.inst_box, bg=FILL, highlightthickness=1, highlightbackground=LINE)
            line.pack(fill="x", pady=4, ipady=6)
            tk.Label(line, text=row.get("name") or "?", fg=TEXT, bg=FILL, anchor="w", font=("Consolas", self.fs)).pack(side="left", padx=8)
            tk.Label(line, text=row.get("dest") or "", fg=DIM, bg=FILL, font=("Consolas", max(8, self.fs - 2))).pack(side="left", padx=8)
            self._btn(line, "OPEN", lambda d=row.get("dest"): core.open_path(Path(d or ""))).pack(side="right", padx=4)
            self._btn(line, "REMOVE", lambda n=i: self.remove_install(n)).pack(side="right", padx=4)

    def remove_install(self, index: int) -> None:
        rows = core.load_installed()
        if index >= len(rows):
            return
        dest = rows[index].get("dest") or ""
        if not messagebox.askokcancel("remove install", "Delete remembered install folder?\n" + dest):
            return
        r = core.remove_installed(index)
        self.status("removed" if r.get("ok") else r.get("error") or "fail")
        self.fill_installed()

    def open_cat_folder(self) -> None:
        if not self.current:
            core.open_path(core.library_root(self.cfg))
            return
        cat = next((c for c in self.cats if c["id"] == self.current), None)
        if cat:
            core.open_path(Path(cat["path"]))

    def add_folder(self) -> None:
        path = filedialog.askdirectory(title="Category folder")
        if not path:
            return
        name = Path(path).name
        self.cfg.setdefault("addedCategories", []).append({"id": name, "root": path, "target": ""})
        core.save_config(self.cfg)
        self.reload()
        self.status("added " + name)

    def add_file(self) -> None:
        if not self.current:
            self.status("open a category first")
            return
        cat = next((c for c in self.cats if c["id"] == self.current), None)
        if not cat:
            return
        path = filedialog.askopenfilename(title="Add program")
        if not path:
            return
        r = core.add_file_to_category(cat, path)
        self.status("file added" if r.get("ok") else r.get("error") or "fail")
        self.reload()

    def fill_store(self, keep_page: bool = False) -> None:
        for w in self.store_box.winfo_children():
            w.destroy()
        if not keep_page:
            self.store_page = 0
        data = core.store_list(self.store_q.get().strip())
        items = data.get("items") or []
        self._store_items = items
        self.draw_tiles(self.store_box, items, self.store_page, self.store_tile, self.lbl_store_page)

    def store_tile(self, parent, item, tw, th) -> None:
        fr = tk.Frame(parent, bg=FILL, highlightbackground=LINE, highlightthickness=1, cursor="hand2")
        fr.place(relx=0, rely=0, relwidth=1, relheight=1)
        tk.Label(fr, text=item.get("tag") or "", fg=LIME, bg=FILL, font=("Consolas", max(8, self.fs - 2))).pack(pady=(self.px(6), 0))
        tk.Label(fr, text=item.get("name") or item.get("id"), fg=TEXT, bg=FILL, font=("Consolas", self.fs), wraplength=tw - 16).pack(pady=2)
        btn = self._btn(fr, "INSTALL", lambda i=item["id"]: self.install_pkg(i), primary=True)
        btn.pack(pady=4)
        tip = (
            f"{item.get('name')}\n"
            f"id: {item.get('id')}\n"
            f"source: {item.get('src') or 'winget'}\n"
            f"tag: {item.get('tag') or '-'}\n"
            f"install via winget on Windows"
        )
        for w in (fr, *fr.winfo_children()):
            if w is btn:
                continue
            w.bind("<Enter>", lambda e, t=tip: self.tip.show(t, e.x_root, e.y_root))
            w.bind("<Leave>", lambda e: self.tip.hide())

    def install_pkg(self, pkg_id: str) -> None:
        self.tip.hide()
        self.status("install " + pkg_id)
        r = core.winget_install(pkg_id)
        self.status("installed " + pkg_id if r.get("ok") else (r.get("error") or r.get("err") or "install fail"))

    def fill_paths(self) -> None:
        for w in self.paths_box.winfo_children():
            w.destroy()
        self.path_vars = {}
        for cat in self.cats:
            row = tk.Frame(self.paths_box, bg=BG)
            row.pack(fill="x", pady=4)
            tk.Label(row, text=cat["id"], fg=TEXT, bg=BG, width=16, anchor="w", font=("Consolas", self.fs)).pack(side="left")
            var = tk.StringVar(value=cat.get("target") or "")
            tk.Entry(row, textvariable=var, bg=FILL, fg=TEXT, insertbackground=TEXT, relief="flat", font=("Consolas", self.fs)).pack(
                side="left", fill="x", expand=True, ipady=6
            )
            self.path_vars[cat["id"]] = var

    def save_paths(self) -> None:
        self.cfg["paths"] = {k: v.get().strip() for k, v in self.path_vars.items()}
        core.save_config(self.cfg)
        self.reload()
        self.status("paths saved")

    def fill_settings(self) -> None:
        self.ent_root.delete(0, "end")
        self.ent_root.insert(0, self.cfg.get("libraryRoot") or "")
        self.auto_var.set(bool(self.cfg.get("autostart")))
        self.quiet_var.set(self.cfg.get("autoUpdate", True))
        self.ent_ver.delete(0, "end")
        self.ent_ver.insert(0, self.cfg.get("versionUrl") or "")
        self.ent_meta.delete(0, "end")
        self.ent_meta.insert(0, self.cfg.get("metaUrl") or "")
        self.ent_folder.delete(0, "end")
        self.ent_folder.insert(0, self.cfg.get("driveFolder") or "")
        self.ent_proxy.delete(0, "end")
        self.ent_proxy.insert(0, self.cfg.get("proxyHttp") or "")
        self.proxy_on.set(bool(self.cfg.get("proxyEnabled")))
        for w in self.drive_box.winfo_children():
            w.destroy()
        for drv in core.list_drives():
            row = tk.Frame(self.drive_box, bg=FILL, highlightthickness=1, highlightbackground=LINE)
            row.pack(fill="x", pady=4, ipady=6)
            flags = []
            if drv.get("system"):
                flags.append("SYSTEM")
            if drv.get("boot"):
                flags.append("BOOT")
            flags.append(str(drv.get("kind") or "fixed").upper())
            free_gb = (drv.get("free") or 0) / 1e9
            total_gb = (drv.get("total") or 0) / 1e9
            text = f"{drv['path']}   {free_gb:.1f} / {total_gb:.1f} GB free   {' '.join(flags)}"
            tk.Label(row, text=text, fg=TEXT, bg=FILL, anchor="w", font=("Consolas", self.fs)).pack(side="left", fill="x", expand=True, padx=8)
            self._btn(row, "COPY ALL HERE", lambda d=drv: self.confirm_pack(d)).pack(side="right", padx=8)

    def confirm_pack(self, drv: dict, need: int = 0) -> None:
        dest = Path(drv["path"]) / "AW_FutaDepot"
        self.status("counting library size…")

        def count():
            plan = core.copy_plan(self.cfg)
            self.root.after(0, lambda: self._confirm_copy(drv, dest, plan))

        threading.Thread(target=count, daemon=True).start()

    def _confirm_copy(self, drv: dict, dest: Path, plan: dict) -> None:
        need = int(plan.get("total") or 0)
        free = int(drv.get("free") or 0)
        lines = [
            f"Copy PROGRAM + FULL library into:\n{dest}",
            f"Program: {core.fmt_size(int(plan.get('appBytes') or 0))}",
            f"Library ({plan.get('libName') or '_FutaMass'}): {core.fmt_size(int(plan.get('libBytes') or 0))}",
            f"TOTAL: {core.fmt_size(need)}",
            f"Free on disk: {core.fmt_size(free)}",
            f"Disk kind: {drv.get('kind')}",
            "Does NOT format the disk.",
            "Does NOT delete other files on the disk.",
            "Uses robocopy (resume, skip already copied, 16 threads).",
            "Creates / updates only the AW_FutaDepot folder (app + whole _FutaMass).",
        ]
        fs = lib_opt.volume_fs(drv["path"])
        if fs:
            lines.append("Filesystem: " + fs)
        if str(fs).upper() in {"FAT32", "FAT"}:
            lines.append("FAT32: files over 4 GB will fail. Use NTFS/exFAT.")
        if drv.get("system") or drv.get("boot"):
            lines.append("\nThis is the Windows / boot drive.")
            if not messagebox.askokcancel("System drive", "\n".join(lines) + "\n\nCopy onto the system drive anyway?"):
                self.status("cancelled")
                return
        else:
            if not messagebox.askokcancel("Copy full library", "\n".join(lines)):
                self.status("cancelled")
                return
        if free < need + 200_000_000:
            messagebox.showerror("Not enough space", f"Need {core.fmt_size(need)}, free {core.fmt_size(free)}. Will not copy.")
            self.status("not enough space")
            return
        box = tk.Toplevel(self.root)
        box.title("copying library")
        box.configure(bg=BG)
        box.geometry("480x110")
        box.transient(self.root)
        tk.Label(box, text="copying " + core.fmt_size(need) + " → " + str(dest), fg=LIME, bg=BG).pack(pady=8)
        bar = ttk.Progressbar(box, length=420, mode="determinate", maximum=100)
        bar.pack(pady=8)
        done = {"n": 0}

        def prog(n, name):
            done["n"] += n
            def ui():
                bar["value"] = min(100, done["n"] * 100 / need) if need else 50
                self.status("copy " + str(name) + "  " + core.fmt_size(done["n"]))
            self.root.after(0, ui)

        def work():
            r = core.install_to(drv["path"], self.cfg, progress=prog)
            def finish():
                box.destroy()
                self.status("copied " + core.fmt_size(r.get("bytes") or done["n"]) + " -> " + r.get("dest", "") if r.get("ok") else (r.get("error") or "copy fail"))
            self.root.after(0, finish)

        threading.Thread(target=work, daemon=True).start()

    def do_compress(self) -> None:
        root = core.library_root(self.cfg)
        self.status("analyzing library size…")

        def work():
            info = lib_opt.analyze(root)
            self.root.after(0, lambda: self._compress_ask(root, info))

        threading.Thread(target=work, daemon=True).start()

    def _compress_ask(self, root: Path, info: dict) -> None:
        if not info.get("ok"):
            self.status(info.get("error") or "analyze fail")
            return
        msg = (
            f"Library: {core.fmt_size(info.get('bytes') or 0)}  ({info.get('files')} files)\n"
            f"Junk (Thumbs.db / tmp / .DS_Store): {info.get('junkCount')} files, {core.fmt_size(info.get('junkBytes') or 0)}\n"
            f"Already packed (zip/msi/video…): {core.fmt_size(info.get('skipBytes') or 0)} — leave as-is\n"
            f"Can compact in place (NTFS, files still run): {info.get('compactFiles')} files, {core.fmt_size(info.get('compactBytes') or 0)}\n\n"
            "This does NOT zip installers. compact.exe is transparent.\n"
            "Junk delete + compact XPRESS8K. Can take a long time on ~100 GB."
        )
        if not messagebox.askokcancel("COMPRESS SIZE", msg):
            self.status("compress cancelled")
            return
        box = tk.Toplevel(self.root)
        box.title("compress")
        box.configure(bg=BG)
        tk.Label(box, text="junk + compact… do not close", fg=LIME, bg=BG).pack(pady=12)

        def work():
            j = lib_opt.purge_junk(root)
            c = lib_opt.compact_tree(root)
            def done():
                box.destroy()
                self.status(
                    "junk -"
                    + str(j.get("removed") or 0)
                    + "  compact "
                    + ("ok" if c.get("ok") else str(c.get("error") or c.get("code")))
                )
            self.root.after(0, done)

        threading.Thread(target=work, daemon=True).start()

    def browse_root(self) -> None:
        path = filedialog.askdirectory(title="Library root")
        if path:
            self.ent_root.delete(0, "end")
            self.ent_root.insert(0, path)

    def auto_update(self) -> None:
        self._run_update(quiet=True)

    def manual_update(self) -> None:
        self._run_update(quiet=False)

    def _run_update(self, quiet: bool) -> None:
        self.status("checking update…")

        def work():
            info = core.check_update(self.cfg)
            def after_check():
                if not info.get("ok"):
                    if not quiet:
                        self.status(info.get("error") or "update check fail")
                    else:
                        self.status("AW_FutaDepot " + core.VERSION)
                    return
                if not info.get("newer"):
                    if not quiet:
                        self.status("already " + str(info.get("current") or core.VERSION) + "  remote " + str(info.get("remote") or "-"))
                    else:
                        self.status("AW_FutaDepot " + core.VERSION)
                    return
                zip_url = info.get("zip") or ""
                if not zip_url:
                    self.status("channel has version, no zip url")
                    return
                box = tk.Toplevel(self.root)
                box.title("update")
                box.configure(bg=BG)
                box.geometry("420x90")
                box.transient(self.root)
                tk.Label(box, text="updating to " + str(info.get("remote") or ""), fg=LIME, bg=BG).pack(pady=8)
                bar = ttk.Progressbar(box, length=360, mode="determinate", maximum=100)
                bar.pack(pady=8)
                def prog(n, total):
                    def ui():
                        bar["value"] = (n * 100 / total) if total else 50
                        self.status("update " + str(n))
                    self.root.after(0, ui)
                def dl():
                    r = core.apply_update(zip_url, progress=prog)
                    def done():
                        box.destroy()
                        if r.get("restart"):
                            self.status("ready")
                            self.root.after(200, self.root.destroy)
                            return
                        if r.get("ok"):
                            self.status("updated")
                            self.reload()
                        else:
                            self.status(r.get("error") or "update fail")
                    self.root.after(0, done)
                threading.Thread(target=dl, daemon=True).start()
            self.root.after(0, after_check)
        threading.Thread(target=work, daemon=True).start()

    def save_settings(self) -> None:
        self.cfg["libraryRoot"] = self.ent_root.get().strip()
        self.cfg["librarySet"] = bool(self.cfg["libraryRoot"])
        self.cfg["autostart"] = bool(self.auto_var.get())
        self.cfg["autoUpdate"] = bool(self.quiet_var.get())
        self.cfg["versionUrl"] = self.ent_ver.get().strip()
        self.cfg["metaUrl"] = self.ent_meta.get().strip()
        self.cfg["driveFolder"] = self.ent_folder.get().strip()
        core.save_config(self.cfg)
        r = core.set_autostart(self.cfg["autostart"])
        self.reload()
        self.status("settings saved" if r.get("ok") or not self.cfg["autostart"] else r.get("error") or "saved")

    def save_proxy(self) -> None:
        self.cfg["proxyEnabled"] = bool(self.proxy_on.get())
        self.cfg["proxyHttp"] = self.ent_proxy.get().strip()
        self.cfg["proxyHttps"] = self.cfg["proxyHttp"]
        core.save_config(self.cfg)
        self.status("proxy saved")

    def win_page(self, page: str) -> None:
        r = core.open_windows(page)
        self.status("open " + page if r.get("ok") else r.get("error") or "fail")


class IconCrop:
    def __init__(self, ui: DepotUI, unit: dict, image: Image.Image) -> None:
        self.ui = ui
        self.unit = unit
        self.src = image.convert("RGBA")
        self.win = tk.Toplevel(ui.root)
        self.win.title("icon 1:1")
        self.win.configure(bg=BG)
        self.win.geometry("520x620")
        self.scale = tk.DoubleVar(value=1.0)
        self.ox = 0
        self.oy = 0
        self.drag = None
        self.view = 360
        tk.Label(self.win, text="square crop · drag to pan · slider = scale", fg=DIM, bg=BG).pack(pady=6)
        self.canvas = tk.Canvas(self.win, width=self.view, height=self.view, bg="#111", highlightthickness=1, highlightbackground=LIME)
        self.canvas.pack()
        self.canvas.bind("<ButtonPress-1>", self._down)
        self.canvas.bind("<B1-Motion>", self._move)
        tk.Scale(
            self.win,
            from_=0.2,
            to=4.0,
            resolution=0.05,
            orient="horizontal",
            variable=self.scale,
            command=lambda _=None: self.redraw(),
            bg=BG,
            fg=TEXT,
            troughcolor=FILL,
            highlightthickness=0,
        ).pack(fill="x", padx=16, pady=8)
        row = tk.Frame(self.win, bg=BG)
        row.pack(pady=8)
        tk.Button(row, text="APPLY", command=self.apply, bg=LIME, fg=BG, relief="flat", padx=16, pady=8).pack(side="left", padx=6)
        tk.Button(row, text="CANCEL", command=self.win.destroy, bg=FILL, fg=TEXT, relief="flat", padx=16, pady=8).pack(side="left", padx=6)
        self.keep = None
        self.redraw()

    def _down(self, ev) -> None:
        self.drag = (ev.x, ev.y, self.ox, self.oy)

    def _move(self, ev) -> None:
        if not self.drag:
            return
        sx, sy, ox, oy = self.drag
        self.ox = ox + (ev.x - sx)
        self.oy = oy + (ev.y - sy)
        self.redraw()

    def composed(self) -> Image.Image:
        sc = float(self.scale.get())
        w = max(1, int(self.src.width * sc))
        h = max(1, int(self.src.height * sc))
        scaled = self.src.resize((w, h), Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", (self.view, self.view), (13, 11, 18, 255))
        canvas.paste(scaled, (self.ox + (self.view - w) // 2, self.oy + (self.view - h) // 2), scaled)
        return canvas

    def redraw(self) -> None:
        img = self.composed()
        self.keep = ImageTk.PhotoImage(img)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self.keep)
        pad = 8
        self.canvas.create_rectangle(pad, pad, self.view - pad, self.view - pad, outline=LIME, width=2)

    def apply(self) -> None:
        img = self.composed()
        pad = 8
        crop = img.crop((pad, pad, self.view - pad, self.view - pad)).resize((256, 256), Image.Resampling.LANCZOS)
        dest = core.custom_icon_path(self.unit)
        dest.parent.mkdir(parents=True, exist_ok=True)
        crop.save(dest, "PNG")
        self.ui.status("icon saved " + dest.name)
        self.win.destroy()
        self.ui.render_lib()


def main() -> None:
    if os.name == "nt":
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(AUMID)
        except Exception:
            pass
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        print("Tk window failed:", exc)
        sys.exit(1)
    apply_app_icon(root)
    root.after(200, lambda: apply_app_icon(root))
    DepotUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
