#!/usr/bin/env python3
"""Portable library DB inside _FutaMass/.futa-db — icons, notes, import meta.

Keyed by pack name + payload filename (not absolute path), so the folder can move.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

DB_DIRNAME = ".futa-db"
INDEX_NAME = "index.json"

META_KEEP = (
    "verified",
    "notes",
    "userNote",
    "sourceUrl",
    "homepage",
    "downloadUrl",
    "silentHint",
    "group",
    "wingetId",
    "updateUrl",
    "updateHint",
    "kind",
    "publisher",
    "versionKnown",
    "engine",
    "name",
)


def db_dir(root: Path) -> Path:
    return Path(root) / DB_DIRNAME


def icons_dir(root: Path) -> Path:
    return db_dir(root) / "icons"


def unit_stable_id(unit: dict) -> str:
    pack = str(unit.get("id") or Path(unit.get("folder") or "").name or unit.get("name") or "").strip().lower()
    payload = str(Path(unit.get("filePath") or "").name or unit.get("file") or "").strip().lower()
    raw = pack + "|" + payload
    return hashlib.sha1(raw.encode("utf-8", "replace")).hexdigest()[:20]


def load_index(root: Path) -> dict:
    path = db_dir(root) / INDEX_NAME
    if not path.is_file():
        return {"v": 1, "units": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"v": 1, "units": {}}
    data.setdefault("v", 1)
    data.setdefault("units", {})
    return data


def save_index(root: Path, data: dict) -> None:
    folder = db_dir(root)
    folder.mkdir(parents=True, exist_ok=True)
    data["v"] = 1
    data["updated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    (folder / INDEX_NAME).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def bind_icons(root: Path, cats: list[dict]) -> int:
    """Attach already-extracted PNGs onto units. No harvest."""
    icond = icons_dir(root)
    files: dict[str, Path] = {}
    try:
        if icond.is_dir():
            for p in icond.glob("*.png"):
                files[p.stem.lower()] = p
    except OSError:
        pass
    idx = load_index(root).get("units") or {}
    by_alt: dict[str, Path] = {}
    by_payload: dict[str, list[Path]] = {}
    for rec in idx.values():
        if not isinstance(rec, dict):
            continue
        icon = rec.get("icon") or ""
        p = db_dir(root) / icon if icon else None
        if p is None or not p.is_file():
            uid = str(rec.get("id") or "")
            p = files.get(uid.lower()) if uid else None
        if p is None or not p.is_file():
            continue
        alt = (str(rec.get("pack") or "") + "|" + str(rec.get("payload") or "")).lower()
        if alt.strip("|"):
            by_alt[alt] = p
        pay = str(rec.get("payload") or "").lower()
        if pay:
            by_payload.setdefault(pay, []).append(p)
    n = 0
    for cat in cats:
        for unit in cat.get("units") or []:
            uid = unit_stable_id(unit)
            p = files.get(uid.lower())
            if p is None:
                alt = (
                    str(unit.get("id") or Path(unit.get("folder") or "").name or "")
                    + "|"
                    + str(Path(unit.get("filePath") or "").name or unit.get("file") or "")
                ).lower()
                p = by_alt.get(alt)
            if p is None:
                pay = str(Path(unit.get("filePath") or "").name or unit.get("file") or "").lower()
                hits = by_payload.get(pay) or []
                if len(hits) == 1:
                    p = hits[0]
            if p is None or not p.is_file():
                continue
            unit["iconPath"] = str(p)
            n += 1
    return n


def apply(root: Path, cats: list[dict]) -> None:
    idx = load_index(root).get("units") or {}
    by_alt: dict[str, dict] = {}
    for rec in idx.values():
        if not isinstance(rec, dict):
            continue
        alt = (str(rec.get("pack") or "") + "|" + str(rec.get("payload") or "")).lower()
        if alt.strip("|"):
            by_alt[alt] = rec
    icond = icons_dir(root)
    for cat in cats:
        for unit in cat.get("units") or []:
            uid = unit_stable_id(unit)
            rec = idx.get(uid)
            if not isinstance(rec, dict):
                alt = (str(unit.get("id") or Path(unit.get("folder") or "").name or "") + "|" + str(Path(unit.get("filePath") or "").name or unit.get("file") or "")).lower()
                rec = by_alt.get(alt)
            if isinstance(rec, dict):
                for field in META_KEEP:
                    val = rec.get(field)
                    if val not in (None, ""):
                        unit[field] = val
            icon = icond / (uid + ".png")
            if icon.is_file():
                unit["iconPath"] = str(icon)
            elif isinstance(rec, dict) and rec.get("icon"):
                p = db_dir(root) / rec["icon"]
                if p.is_file():
                    unit["iconPath"] = str(p)


def persist(root: Path, cats: list[dict]) -> None:
    data = load_index(root)
    units = data.setdefault("units", {})
    icond = icons_dir(root)
    for cat in cats:
        for unit in cat.get("units") or []:
            uid = unit_stable_id(unit)
            rec = units.get(uid) if isinstance(units.get(uid), dict) else {}
            rec["id"] = uid
            rec["pack"] = str(unit.get("id") or Path(unit.get("folder") or "").name or "")
            rec["payload"] = str(Path(unit.get("filePath") or "").name or unit.get("file") or "")
            rec["rel"] = str(unit.get("payloadRel") or "")
            for field in META_KEEP:
                if unit.get(field) not in (None, ""):
                    rec[field] = unit.get(field)
            icon = icond / (uid + ".png")
            if icon.is_file():
                rec["icon"] = "icons/" + uid + ".png"
            units[uid] = rec
    save_index(root, data)


def upsert_note(root: Path, unit: dict, text: str) -> None:
    data = load_index(root)
    uid = unit_stable_id(unit)
    rec = data.setdefault("units", {}).setdefault(uid, {"id": uid})
    rec["userNote"] = text
    rec["pack"] = str(unit.get("id") or Path(unit.get("folder") or "").name or "")
    rec["payload"] = str(Path(unit.get("filePath") or "").name or unit.get("file") or "")
    unit["userNote"] = text
    save_index(root, data)


def icon_path_for(root: Path, unit: dict) -> Path:
    icons_dir(root).mkdir(parents=True, exist_ok=True)
    return icons_dir(root) / (unit_stable_id(unit) + ".png")


def extract_shell_icon(src: Path, dest: Path) -> bool:
    if os.name != "nt" or not src.is_file():
        return False
    try:
        import ctypes
        from ctypes import wintypes
        from PIL import Image
    except ImportError:
        return False
    SHGFI_ICON = 0x00000100
    SHGFI_LARGEICON = 0x00000000
    DI_NORMAL = 0x0003

    class SHFILEINFOW(ctypes.Structure):
        _fields_ = [
            ("hIcon", ctypes.c_void_p),
            ("iIcon", ctypes.c_int),
            ("dwAttributes", wintypes.DWORD),
            ("szDisplayName", wintypes.WCHAR * 260),
            ("szTypeName", wintypes.WCHAR * 80),
        ]

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ("biSize", wintypes.DWORD),
            ("biWidth", wintypes.LONG),
            ("biHeight", wintypes.LONG),
            ("biPlanes", wintypes.WORD),
            ("biBitCount", wintypes.WORD),
            ("biCompression", wintypes.DWORD),
            ("biSizeImage", wintypes.DWORD),
            ("biXPelsPerMeter", wintypes.LONG),
            ("biYPelsPerMeter", wintypes.LONG),
            ("biClrUsed", wintypes.DWORD),
            ("biClrImportant", wintypes.DWORD),
        ]

    class BITMAPINFO(ctypes.Structure):
        _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]

    shell32 = ctypes.windll.shell32
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    shell32.SHGetFileInfoW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_void_p, wintypes.UINT, wintypes.UINT]
    shell32.SHGetFileInfoW.restype = ctypes.c_void_p
    info = SHFILEINFOW()
    r = shell32.SHGetFileInfoW(str(src), 0, ctypes.byref(info), ctypes.sizeof(info), SHGFI_ICON | SHGFI_LARGEICON)
    if not r or not info.hIcon:
        return False
    w = h = 128
    bmi = BITMAPINFO()
    bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth = w
    bmi.bmiHeader.biHeight = -h
    bmi.bmiHeader.biPlanes = 1
    bmi.bmiHeader.biBitCount = 32
    bits = ctypes.c_void_p()
    hdc = user32.GetDC(None)
    hbmp = gdi32.CreateDIBSection(hdc, ctypes.byref(bmi), 0, ctypes.byref(bits), None, 0)
    mem = gdi32.CreateCompatibleDC(hdc)
    old = gdi32.SelectObject(mem, hbmp)
    user32.DrawIconEx(mem, 0, 0, info.hIcon, w, h, 0, None, DI_NORMAL)
    buf = ctypes.string_at(bits, w * h * 4)
    gdi32.SelectObject(mem, old)
    gdi32.DeleteDC(mem)
    gdi32.DeleteObject(hbmp)
    user32.ReleaseDC(None, hdc)
    user32.DestroyIcon(info.hIcon)
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        img = Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1).copy()
        img.save(dest, "PNG")
        return dest.is_file() and dest.stat().st_size > 32
    except OSError:
        return False


def extract_unit_icon(src: Path, dest: Path) -> bool:
    """One file, one icon. Never batch."""
    try:
        if dest.is_file() and dest.stat().st_size > 32:
            return True
    except OSError:
        pass
    if src is None or not Path(src).is_file():
        return False
    src = Path(src)
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.suffix.lower() in {".png", ".ico", ".jpg", ".jpeg", ".bmp", ".webp", ".gif"}:
        try:
            from PIL import Image
            Image.open(src).convert("RGBA").resize((128, 128)).save(dest, "PNG")
            if dest.is_file() and dest.stat().st_size > 32:
                return True
        except (OSError, ImportError):
            pass
    if extract_shell_icon(src, dest):
        return True
    harvest_ps1([(src, dest)])
    try:
        return dest.is_file() and dest.stat().st_size > 32
    except OSError:
        return False


def harvest_ps1(jobs: list[tuple[Path, Path]]) -> None:
    if os.name != "nt" or not jobs:
        return
    lines = ["Add-Type -AssemblyName System.Drawing"]
    for src, dest in jobs:
        s = str(src).replace("'", "''")
        d = str(dest).replace("'", "''")
        dest.parent.mkdir(parents=True, exist_ok=True)
        lines.append(
            "try { $i = [System.Drawing.Icon]::ExtractAssociatedIcon('"
            + s
            + "'); if ($i -ne $null) { $i.ToBitmap().Save('"
            + d
            + "', [System.Drawing.Imaging.ImageFormat]::Png) } } catch {}"
        )
    ps1 = Path(tempfile.gettempdir()) / "aw_futa_icons.ps1"
    ps1.write_text("\n".join(lines), encoding="utf-8-sig")
    flags = 0x08000000
    try:
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        subprocess.run(
            ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-ExecutionPolicy", "Bypass", "-File", str(ps1)],
            capture_output=True,
            timeout=min(40, 8 + len(jobs) * 2),
            startupinfo=si,
            creationflags=flags,
        )
    except (OSError, subprocess.TimeoutExpired):
        pass
