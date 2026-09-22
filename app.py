#!/usr/bin/env python3
"""AW_FutaDepot 0.1.1 — local library launcher."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import urllib.error
import urllib.request
import zipfile
import base64
from pathlib import Path

# lib/ on sys.path before local imports
_APP_DIR_BOOT = Path(__file__).resolve().parent
_LIB = _APP_DIR_BOOT / "lib"
if _LIB.is_dir() and str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

import futa_db

VERSION = "0.1.46"
PORT = 17331
APP_DIR = Path(__file__).resolve().parent
CONFIG_PATH = APP_DIR / "config.json"
_CATALOG_CANDIDATES = [APP_DIR / "lib" / "catalog.json", APP_DIR / "catalog.json"]
CATALOG_PATH = next((c for c in _CATALOG_CANDIDATES if c.is_file()), _CATALOG_CANDIDATES[0])
META_PATH = APP_DIR / "depot-meta.json"
INSTALLED_PATH = APP_DIR / "installed.json"
HISTORY_PATH = APP_DIR / "search-history.json"
REPORTS_DIR = APP_DIR / "reports"
INBOX_DIR = APP_DIR / "_FutaMass"
MASS_NAME = "_FutaMass"
ICON_CACHE = APP_DIR / ".iconcache"
CUSTOM_ICON_DIR = APP_DIR / "icons-custom"


def run_hidden(cmd: list[str], **kw):
    if os.name == "nt" and cmd and "powershell" in cmd[0].lower():
        out = [cmd[0], "-NoProfile", "-WindowStyle", "Hidden"]
        i = 1
        while i < len(cmd):
            if cmd[i] in {"-NoProfile", "-WindowStyle", "Hidden"}:
                i += 1
                if i < len(cmd) and cmd[i - 1] == "-WindowStyle":
                    i += 1
                continue
            out.append(cmd[i])
            i += 1
        cmd = out
        kw["creationflags"] = kw.get("creationflags", 0) | 0x08000000
        kw["startupinfo"] = subprocess.STARTUPINFO()
        kw["startupinfo"].dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return subprocess.run(cmd, **kw)


def unit_key(unit: dict) -> str:
    raw = unit.get("filePath") or unit.get("folder") or unit.get("id") or unit.get("name") or "x"
    return hashlib.sha1(str(raw).encode("utf-8")).hexdigest()[:16]


def custom_icon_path(unit: dict) -> Path:
    try:
        root = library_root(load_config())
        if str(load_config().get("libraryRoot") or "").strip():
            return futa_db.icon_path_for(root, unit)
    except Exception:
        pass
    CUSTOM_ICON_DIR.mkdir(parents=True, exist_ok=True)
    return CUSTOM_ICON_DIR / (unit_key(unit) + ".png")

LEGEND = {
    "innosetup": {"label": "Inno Setup", "silent": "yes", "color": "#99e550", "note": "quiet /DIR="},
    "nsis": {"label": "NSIS", "silent": "yes-if-no-spaces", "color": "#c6e070", "note": "/S /D="},
    "msi": {"label": "MSI", "silent": "yes", "color": "#50c8e5", "note": "msiexec /qn"},
    "installshield": {"label": "InstallShield", "silent": "rare", "color": "#e5c050", "note": "run as-is"},
    "portable": {"label": "Portable", "silent": "n/a", "color": "#a080e5", "note": "run file"},
    "unknown": {"label": "Unknown exe", "silent": "unknown", "color": "#8a8678", "note": "sniff failed"},
    "empty": {"label": "No payload", "silent": "no", "color": "#444", "note": "folder only"},
}
SKIP_DIR_NAMES = {".git", "__pycache__", "node_modules", ".iconcache", ".futa-db"}
SAVE_DIR_HINTS = {"save", "saves", "savedata", "savegames", "savegame", "userdata", "user data", "profiles", "saveslots"}
SAVE_EXT = {".sav", ".save", ".sl2", ".ess", ".bak", ".dat"}
GAME_FILE_HINTS = {"game.exe", "game.bat", "start.bat", "play.bat", "data.win", "unityplayer.dll", "steam_api.dll", "steam_api64.dll", "unrealengine", "game.iso"}
SCAN_FILE_EXT = {
    ".exe", ".msi", ".bat", ".cmd", ".ps1", ".vbs", ".reg", ".inf", ".lnk", ".url",
    ".zip", ".7z", ".rar", ".iso", ".sav", ".save", ".sl2", ".ess",
    ".txt", ".md", ".json", ".ini", ".cfg", ".xml", ".log", ".nfo",
}
DOC_EXT = {".txt", ".md", ".json", ".ini", ".cfg", ".xml", ".log", ".nfo"}
INSTALLER_NAMES = {
    "setup.exe",
    "install.exe",
    "installer.exe",
    "setup.msi",
    "install.msi",
}
LAUNCH_EXT = {".exe", ".msi", ".bat", ".cmd"}
BIN_DIR_HINTS = {
    "x86", "x64", "x86_64", "bin", "app", "win", "win32", "win64",
    "program", "files", "binaries", "application", "32-bit", "64-bit",
    "32bit", "64bit",
}
SKIP_PAYLOAD_DIR = {
    "crack", "cracks", "keygen", "patch", "patches", "activator",
    "serial", "codec", "codecs", "unins",
}
SKIP_EXE_SUB = (
    "unins", "uninstall", "crashhandler", "vcredist", "dxsetup",
    "unitycrash", "easyanticheat", "crashrpt",
)
HEADER_JUNK = {"name", "id", "version", "source", "tag", "moniker", "query", "command"}
KIND_FOLDER = {
    "game": "Games",
    "save": "Saves",
    "script": "Scripts",
    "installer": "Installers",
    "portable": "Portable",
    "archive": "Archives",
    "empty": "Unknown",
}
KIND_COLOR = {
    "game": "#3b82f6",
    "save": "#f97316",
    "script": "#a855f7",
    "installer": "#99e550",
    "portable": "#22d3ee",
    "archive": "#eab308",
    "empty": "#111111",
    "unknown": "#6b7280",
    "doc": "#94a3b8",
}
SORT_FOLDERS = set(KIND_FOLDER.values())



def load_config() -> dict:
    if CONFIG_PATH.exists():
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    else:
        data = {}
    data.setdefault("libraryRoot", "")
    data.setdefault("librarySet", False)
    data.setdefault("seenHelp", False)
    data.setdefault("paths", {})
    data.setdefault("addedCategories", [])
    data.setdefault("autostart", False)
    data.setdefault("proxyEnabled", False)
    data.setdefault("proxyHttp", "")
    data.setdefault("proxyHttps", "")
    data.setdefault("toolboxModules", [])
    data.setdefault("channelId", "AW_FutaDepot_sync")
    data.setdefault("syncTarget", "github")
    data.setdefault("driveFolder", "https://drive.google.com/drive/folders/1Lqwt0iIrV3oDsrXR66lvNWqRJtAneoy_")
    data.setdefault(
        "dumpUrl",
        "https://raw.githubusercontent.com/2biteWolf/AW_FutaDepot/main/channel/depot-dump-latest.json",
    )
    data.setdefault(
        "metaUrl",
        "https://raw.githubusercontent.com/2biteWolf/AW_FutaDepot/main/channel/depot-meta.json",
    )
    data.setdefault("versionUrl", "https://raw.githubusercontent.com/2biteWolf/AW_FutaDepot/main/channel/version.json")
    data.setdefault("autoUpdate", False)
    return data


def save_config(data: dict) -> None:
    raw = data.get("libraryRoot")
    if raw:
        p = Path(raw).expanduser()
        if p.is_absolute():
            try:
                data["libraryRoot"] = str(p.resolve().relative_to(APP_DIR.resolve()))
            except ValueError:
                data["libraryRoot"] = str(p.resolve()) if p.exists() else str(p)
        else:
            data["libraryRoot"] = str(p)
    CONFIG_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_installed() -> list[dict]:
    if not INSTALLED_PATH.exists():
        return []
    try:
        data = json.loads(INSTALLED_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def save_installed(rows: list[dict]) -> None:
    INSTALLED_PATH.write_text(json.dumps(rows, indent=2), encoding="utf-8")


def record_install(name: str, dest: str, source: str = "", kind: str = "") -> None:
    rows = load_installed()
    rows.append(
        {
            "name": name,
            "dest": dest,
            "source": source,
            "kind": kind,
            "when": dt.datetime.now().isoformat(timespec="seconds"),
        }
    )
    save_installed(rows)


def remove_installed(index: int) -> dict:
    rows = load_installed()
    if index < 0 or index >= len(rows):
        return {"ok": False, "error": "missing"}
    row = rows.pop(index)
    dest = Path(row.get("dest") or "")
    if dest.exists():
        try:
            if dest.is_dir():
                shutil.rmtree(dest)
            else:
                dest.unlink()
        except OSError as exc:
            return {"ok": False, "error": str(exc)}
    save_installed(rows)
    return {"ok": True, "name": row.get("name")}


def unit_source_path(unit: dict, root: Path | None = None) -> Path:
    """Move the top-level folder, not the inner setup/exe. Loose files stay files."""
    payload = Path(unit.get("filePath") or "")
    folder = Path(unit.get("folder") or "")
    root_r = root.resolve() if root is not None and Path(root).exists() else None

    def _under_root(path: Path) -> bool:
        if root_r is None:
            return True
        try:
            path.resolve().relative_to(root_r)
            return True
        except ValueError:
            return False

    if folder.is_dir() and folder.name not in SORT_FOLDERS and _under_root(folder):
        parent = folder.parent
        at_mass = root_r is not None and parent.resolve() == root_r
        in_bucket = parent.name in SORT_FOLDERS
        if at_mass or in_bucket:
            if not payload.exists():
                return folder
            try:
                payload.resolve().relative_to(folder.resolve())
                return folder
            except ValueError:
                pass
    if payload.exists():
        return payload
    return folder


def move_unit(unit: dict, dest_dir: str) -> dict:
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    src = unit_source_path(unit)
    if not src.exists():
        return {"ok": False, "error": "source missing"}
    target = dest / src.name
    try:
        shutil.move(str(src), str(target))
    except OSError as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "dest": str(target)}


def autosort_mass(cfg: dict) -> dict:
    root = library_root(cfg)
    mass = scan_root(root, "MASS", "", skip_names=SORT_FOLDERS)
    moved = 0
    errors = []
    for unit in mass.get("units") or []:
        kind = unit.get("kind") or "empty"
        if unit.get("hasSaves") and kind == "game":
            dest_name = "Games"
        else:
            dest_name = KIND_FOLDER.get(kind, "Unknown")
        dest = root / dest_name
        dest.mkdir(parents=True, exist_ok=True)
        src = unit_source_path(unit, root)
        if not src.exists():
            continue
        if src.parent.resolve() == dest.resolve():
            continue
        target = dest / src.name
        if target.exists():
            errors.append(src.name + " exists")
            continue
        try:
            shutil.move(str(src), str(target))
            moved += 1
        except OSError as exc:
            errors.append(str(exc))
    return {"ok": True, "moved": moved, "errors": errors}


def load_catalog() -> list[dict]:
    if not CATALOG_PATH.exists():
        return []
    try:
        data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def library_root(cfg: dict) -> Path:
    raw = str(cfg.get("libraryRoot") or "").strip()
    if not raw:
        return APP_DIR / MASS_NAME
    p = Path(raw).expanduser()
    if not p.is_absolute():
        p = APP_DIR / p
    return p


def need_library_pick(cfg: dict) -> bool:
    raw = str(cfg.get("libraryRoot") or "").strip()
    if not raw:
        return True
    p = library_root(cfg)
    if not p.is_dir():
        return True
    if cfg.get("librarySet"):
        return False
    return False


def set_library(cfg: dict, path: str | Path, create: bool = False) -> dict:
    p = Path(path).expanduser()
    if create:
        try:
            p.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return {"ok": False, "error": str(exc)}
    if not p.is_dir():
        return {"ok": False, "error": "folder missing"}
    cfg["libraryRoot"] = str(p.resolve())
    cfg["librarySet"] = True
    save_config(cfg)
    return {"ok": True, "path": str(p.resolve())}


def rel_if_inside(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(APP_DIR.resolve()))
    except ValueError:
        return str(path)



def read_depot_json(folder: Path) -> dict:
    f = folder / "depot.json"
    if not f.is_file():
        return {}
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def is_pe(path: Path) -> bool:
    try:
        with path.open("rb") as fh:
            return fh.read(2) == b"MZ"
    except OSError:
        return False


def sniff_format(path: Path) -> str:
    ext = path.suffix.lower()
    try:
        with path.open("rb") as fh:
            head = fh.read(8)
    except OSError:
        return ext[1:] if ext else "unknown"
    if head.startswith(b"MZ"):
        return "pe"
    if head.startswith(b"PK"):
        return "zip"
    if head.startswith(b"7z\xbc\xaf"):
        return "7z"
    if head.startswith(b"Rar!"):
        return "rar"
    if ext == ".msi":
        return "msi"
    if ext == ".iso":
        return "iso"
    return ext[1:] if ext else "bin"


def pack_store(unit: dict) -> dict:
    src = Path(unit.get("filePath") or unit.get("folder") or "")
    if not src.exists():
        return {"ok": False, "error": "source missing"}
    dest = library_root(load_config()) / (src.stem + ".zip")
    try:
        with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            if src.is_file():
                zf.write(src, src.name)
            else:
                for item in src.rglob("*"):
                    if item.is_file():
                        zf.write(item, item.relative_to(src.parent).as_posix())
    except OSError as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "zip": str(dest), "bytes": dest.stat().st_size}


def unpack_store(unit: dict, dest_dir: str | None = None) -> dict:
    src = Path(unit.get("filePath") or "")
    if not src.is_file() or src.suffix.lower() != ".zip":
        return {"ok": False, "error": "zip only"}
    dest = Path(dest_dir) if dest_dir else (src.parent / src.stem)
    dest.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(src) as zf:
            zf.extractall(dest)
    except (OSError, zipfile.BadZipFile) as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "dest": str(dest)}


def can_launch(path: Path | None) -> bool:
    if path is None or not path.is_file():
        return False
    return path.suffix.lower() in {".exe", ".msi", ".bat", ".cmd", ".com", ".lnk", ".msc", ".ps1"}


def sniff_engine(path: Path) -> tuple[str, bool]:
    suffix = path.suffix.lower()
    if suffix == ".msi":
        return "msi", True
    if suffix not in {".exe", ".msi"}:
        return "none", False
    if not is_pe(path):
        return "none", False
    blob = b""
    try:
        size = path.stat().st_size
        with path.open("rb") as fh:
            blob = fh.read(min(size, 48_000))
            if size > 80_000:
                fh.seek(max(0, size - 12_000))
                blob += fh.read(12_000)
    except OSError:
        return "unknown", False
    low = blob.lower()
    if b"inno setup" in low or b"innosetup" in low:
        return "innosetup", True
    if b"nullsoft" in low or b"nsis" in low:
        return "nsis", True
    if b"installshield" in low:
        return "installshield", False
    if b"wise installation" in low:
        return "wise", False
    if b"wix" in low:
        return "wix", True
    if b"7-zip" in low:
        return "7zsfx", False
    return "unknown", False


def peek_archive(path: Path) -> dict:
    out: dict = {"inner": [], "innerCount": 0, "innerFile": None, "kindHint": None}
    fmt = sniff_format(path)
    if fmt != "zip" and path.suffix.lower() != ".zip":
        return out
    try:
        with zipfile.ZipFile(path) as zf:
            names = [n for n in zf.namelist() if n and not n.endswith("/")]
    except (OSError, zipfile.BadZipFile):
        return out
    out["inner"] = names[:50]
    out["innerCount"] = len(names)
    exes = [n for n in names if Path(n).suffix.lower() in {".exe", ".msi"}]
    if not exes:
        return out
    def is_setup(n: str) -> bool:
        leaf = Path(n).name.lower()
        return leaf in INSTALLER_NAMES or "setup" in leaf or "install" in leaf
    setups = [n for n in exes if is_setup(n)]
    if len(exes) == 1 and not setups:
        out["kindHint"] = "portable"
        out["innerFile"] = exes[0]
    elif setups:
        out["kindHint"] = "installer"
        out["innerFile"] = setups[0]
    elif len(exes) == 1:
        out["kindHint"] = "portable"
        out["innerFile"] = exes[0]
    return out


def pick_payload(folder: Path, meta: dict) -> Path | None:
    named = meta.get("file")
    if named:
        p = folder / named
        if p.is_file() and p.suffix.lower() in LAUNCH_EXT:
            return p
    files = _collect_launch(folder)
    if not files:
        return None
    primary = [p for p in files if not _skip_payload(p, folder)]
    pool = primary or files
    lower = {p.name.lower(): p for p in pool}
    for name in INSTALLER_NAMES:
        if name in lower:
            return lower[name]
    setupish = [p for p in pool if "setup" in p.name.lower() or "install" in p.name.lower()]
    if setupish:
        return max(setupish, key=lambda p: p.stat().st_size)
    binish = [p for p in pool if any(part.lower() in BIN_DIR_HINTS for part in p.parts)]
    exe = [p for p in (binish or pool) if p.suffix.lower() in {".exe", ".msi"}]
    if len(exe) == 1:
        return exe[0]
    if exe:
        return max(exe, key=lambda p: p.stat().st_size)
    return pool[0]


def _collect_launch(folder: Path, max_depth: int = 3) -> list[Path]:
    found: list[Path] = []
    stack = [(folder, 0)]
    while stack:
        cur, depth = stack.pop()
        try:
            kids = list(cur.iterdir())
        except OSError:
            continue
        for p in kids:
            name = p.name.lower()
            if name.startswith(".") or name in SKIP_DIR_NAMES:
                continue
            if p.is_file() and p.suffix.lower() in LAUNCH_EXT:
                found.append(p)
                if len(found) >= 80:
                    return found
            elif p.is_dir() and depth < max_depth:
                stack.append((p, depth + 1))
    return found


def _skip_payload(path: Path, root: Path) -> bool:
    try:
        rel = path.relative_to(root)
        parts = [x.lower() for x in rel.parts[:-1]]
    except ValueError:
        parts = [x.lower() for x in path.parts[:-1]]
    if any(p in SKIP_PAYLOAD_DIR for p in parts):
        return True
    stem = path.stem.lower()
    return any(h in stem for h in SKIP_EXE_SUB)


def _payload_rel(folder: Path, payload: Path | None) -> str | None:
    if payload is None:
        return None
    try:
        return payload.relative_to(folder).as_posix()
    except ValueError:
        return payload.name


def unit_payload_fields(payload: Path | None, meta: dict, fallback_name: str, folder: Path) -> dict:
    if payload is None:
        return {
            "name": meta.get("name") or fallback_name,
            "id": fallback_name,
            "folder": str(folder),
            "file": None,
            "filePath": None,
            "kind": meta.get("kind") or "empty",
            "engine": meta.get("engine") or "none",
            "silent": False,
            "silentFlags": None,
            "canLaunch": False,
            "icon": None,
            "format": "none",
            "payloadRel": None,
        }
    ext0 = payload.suffix.lower()
    if ext0 == ".exe":
        det_engine, det_silent = sniff_engine(payload)
    elif ext0 == ".msi":
        det_engine, det_silent = "msi", True
    else:
        det_engine, det_silent = "none", False
    engine = meta.get("engine")
    if engine in (None, "", "auto"):
        engine = det_engine
    silent = meta.get("silent")
    if silent is None:
        silent = True if isinstance(meta.get("silentFlags"), list) else det_silent
    kind = meta.get("kind")
    if not kind:
        ext = payload.suffix.lower()
        if ext in SAVE_EXT:
            kind = "save"
        elif ext in DOC_EXT:
            kind = "doc"
        elif ext in {".bat", ".cmd", ".ps1", ".vbs"}:
            kind = "script"
        elif ext in {".zip", ".7z", ".rar", ".iso"}:
            kind = "archive"
        elif ext == ".msi" or engine in {"innosetup", "nsis", "msi"}:
            kind = "installer"
        else:
            kind = "portable"
    launch = can_launch(payload)
    fmt = sniff_format(payload)
    inner = {}
    if kind == "archive" or fmt in {"zip", "7z", "rar"}:
        inner = peek_archive(payload)
        hint = inner.get("kindHint")
        if hint and not meta.get("kind"):
            kind = hint
    return {
        "name": meta.get("name") or fallback_name,
        "id": fallback_name,
        "folder": str(folder),
        "file": payload.name,
        "filePath": str(payload),
        "kind": kind,
        "engine": engine,
        "silent": bool(silent) and launch,
        "silentFlags": meta.get("silentFlags"),
        "canLaunch": launch,
        "icon": "/api/icon?file=" + str(payload) if launch and payload.suffix.lower() == ".exe" else None,
        "format": fmt,
        "innerFile": inner.get("innerFile"),
        "innerCount": inner.get("innerCount"),
        "archiveHint": inner.get("kindHint"),
        "payloadRel": _payload_rel(folder, payload),
    }


def guess_kind(folder: Path, payload: Path | None, meta: dict) -> str:
    if meta.get("kind"):
        return str(meta["kind"])
    names = set()
    try:
        names = {c.name.lower() for c in folder.iterdir()}
    except OSError:
        names = set()
    folder_l = folder.name.lower().replace(" ", "")
    if folder_l in {s.replace(" ", "") for s in SAVE_DIR_HINTS} or any(h in folder_l for h in ("save", "userdata")):
        if not payload or payload.suffix.lower() in SAVE_EXT:
            return "save"
    if any(n in names for n in GAME_FILE_HINTS) or any(n.endswith(".win") for n in names):
        return "game"
    if payload is None:
        if any(Path(folder, n).suffix.lower() in SAVE_EXT for n in names):
            return "save"
        return "empty"
    ext = payload.suffix.lower()
    if ext in SAVE_EXT:
        return "save"
    if ext in {".bat", ".cmd"}:
        return "script"
    if ext in {".zip", ".7z", ".rar", ".iso"}:
        return "archive"
    if ext == ".msi":
        return "installer"
    return ""


def unit_from_folder(folder: Path) -> dict:
    meta = read_depot_json(folder)
    payload = pick_payload(folder, meta)
    unit = unit_payload_fields(payload, meta, folder.name, folder)
    guessed = guess_kind(folder, payload, meta)
    if guessed:
        unit["kind"] = guessed
    try:
        kids = list(folder.iterdir())
    except OSError:
        kids = []
    names = {c.name.lower() for c in kids}
    unit["hasSaves"] = bool(names & SAVE_DIR_HINTS) or any(c.suffix.lower() in SAVE_EXT for c in kids if c.is_file())
    return unit


def unit_from_file(path: Path) -> dict:
    return unit_payload_fields(path, {}, path.stem, path.parent)


def _add_child(units: list, child: Path) -> None:
    if child.is_dir():
        units.append(unit_from_folder(child))
    elif child.is_file() and child.suffix.lower() in SCAN_FILE_EXT:
        units.append(unit_from_file(child))


def restore_sort_buckets(root: Path) -> int:
    moved = 0
    if not root.is_dir():
        return 0
    for bucket in list(SORT_FOLDERS):
        bdir = root / bucket
        if not bdir.is_dir():
            continue
        for child in list(bdir.iterdir()):
            dest = root / child.name
            if dest.exists():
                dest = root / (child.stem + "_" + bucket + child.suffix)
            try:
                shutil.move(str(child), str(dest))
                moved += 1
            except OSError:
                continue
        try:
            next(bdir.iterdir())
        except StopIteration:
            try:
                bdir.rmdir()
            except OSError:
                pass
        except OSError:
            pass
    return moved


def scan_root(root: Path, cat_id: str, target: str, skip_names: set | None = None) -> dict:
    units = []
    skip = {n.lower() for n in (skip_names or set())} | {n.lower() for n in SKIP_DIR_NAMES}
    if not root.is_dir():
        return {"id": cat_id, "path": str(root), "target": target, "units": units}
    try:
        kids = list(root.iterdir())
    except OSError:
        return {"id": cat_id, "path": str(root), "target": target, "units": units}
    for child in sorted(kids, key=lambda p: p.name.lower()):
        if child.name.startswith(".") or child.name.lower() in skip:
            continue
        if child.is_dir() and child.name in SORT_FOLDERS:
            try:
                inner = list(child.iterdir())
            except OSError:
                continue
            for item in sorted(inner, key=lambda p: p.name.lower()):
                if item.name.startswith("."):
                    continue
                _add_child(units, item)
            continue
        _add_child(units, child)
    return {"id": cat_id, "path": str(root), "target": target, "units": units}


def discover_library(cfg: dict) -> list[dict]:
    root = library_root(cfg)
    if not str(cfg.get("libraryRoot") or "").strip() or not root.exists():
        return [{"id": "MASS", "name": "MASS", "root": str(root), "target": "", "units": []}]
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    paths = cfg.get("paths") or {}
    cats = [scan_root(root, "MASS", paths.get("MASS") or "")]
    seen = {"mass"}
    for extra in cfg.get("addedCategories") or []:
        name = extra.get("id") or extra.get("name")
        extra_root = extra.get("root") or extra.get("path")
        if not name or not extra_root:
            continue
        if name.lower() in seen:
            continue
        seen.add(name.lower())
        target = extra.get("target") or paths.get(name) or ""
        cats.append(scan_root(Path(extra_root), name, target))
    return cats


def overlay_import_meta(cats: list[dict]) -> None:
    apply_meta(cats)


def overlay_futa_db(cfg: dict, cats: list[dict]) -> None:
    root = library_root(cfg)
    futa_db.apply(root, cats)
    futa_db.bind_icons(root, cats)


def apply_icons(cfg: dict, cats: list[dict]) -> int:
    return futa_db.bind_icons(library_root(cfg), cats)


def unblock_payloads(cats: list[dict]) -> int:
    n = 0
    for cat in cats:
        for unit in cat.get("units") or []:
            fp = unit.get("filePath")
            if fp and unblock_file(fp):
                n += 1
    return n


def persist_library(cfg: dict, cats: list[dict]) -> None:
    futa_db.persist(library_root(cfg), cats)


def scan_all(cfg: dict) -> list[dict]:
    cats = discover_library(cfg)
    overlay_import_meta(cats)
    overlay_futa_db(cfg, cats)
    return cats


def icon_source(unit: dict) -> Path | None:
    custom = custom_icon_path(unit)
    if custom.is_file():
        return custom
    folder = Path(unit.get("folder") or "")
    fp = Path(unit.get("filePath") or "")
    cands: list[Path] = []
    if fp.is_file():
        cands.append(fp)
    rel = unit.get("payloadRel")
    if rel and folder:
        cands.append(folder / str(rel))
    if folder.is_dir():
        for name in ("icon.ico", "icon.png", "app.ico", "logo.ico"):
            cands.append(folder / name)
        try:
            for e in folder.rglob("*"):
                if not e.is_file():
                    continue
                low = e.name.lower()
                if e.suffix.lower() != ".exe":
                    continue
                if any(x in low for x in ("unins", "crash", "vcredist", "unitycrash")):
                    continue
                cands.append(e)
                break
        except OSError:
            pass
    for p in cands:
        try:
            if p.is_file():
                return p
        except OSError:
            continue
    return None


def cached_icon(unit: dict) -> Path | None:
    p = unit.get("iconPath")
    if p and Path(p).is_file():
        return Path(p)
    try:
        root = library_root(load_config())
        dbp = futa_db.icon_path_for(root, unit)
        if dbp.is_file():
            return dbp
    except Exception:
        pass
    custom = custom_icon_path(unit)
    if custom.is_file():
        return custom
    src = icon_source(unit)
    if src is None:
        return None
    key = hashlib.sha1(str(src).encode("utf-8")).hexdigest()[:16]
    dest = ICON_CACHE / (key + ".png")
    if dest.is_file():
        return dest
    return None


def _icon_via_pil(src: Path, dest: Path) -> bool:
    try:
        from PIL import Image
    except ImportError:
        return False
    if src.suffix.lower() not in {".png", ".ico", ".jpg", ".jpeg", ".bmp", ".webp", ".gif"}:
        return False
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        Image.open(src).convert("RGBA").resize((128, 128)).save(dest, "PNG")
        return dest.is_file()
    except OSError:
        return False


def harvest_icons(cats: list[dict], cfg: dict | None = None) -> int:
    cfg = cfg or load_config()
    root = library_root(cfg)
    got = 0
    for cat in cats:
        for unit in cat.get("units") or []:
            dest = futa_db.icon_path_for(root, unit)
            if dest.is_file() and dest.stat().st_size > 32:
                unit["iconPath"] = str(dest)
                got += 1
                continue
            src = icon_source(unit)
            if src is None:
                continue
            unblock_file(src)
            if futa_db.extract_unit_icon(src, dest):
                unit["iconPath"] = str(dest)
                got += 1
    return got


def extract_icon_png(src: Path) -> Path | None:
    if not src.is_file():
        return None
    ICON_CACHE.mkdir(exist_ok=True)
    key = hashlib.sha1(str(src).encode("utf-8")).hexdigest()[:16]
    dest = ICON_CACHE / (key + ".png")
    if dest.exists():
        return dest
    if _icon_via_pil(src, dest):
        return dest
    if os.name != "nt":
        return None
    env = os.environ.copy()
    env["AW_ICON_SRC"] = str(src)
    env["AW_ICON_DST"] = str(dest)
    script = (
        "Add-Type -AssemblyName System.Drawing;"
        "$p = $env:AW_ICON_SRC; $o = $env:AW_ICON_DST;"
        "try { $i = [System.Drawing.Icon]::ExtractAssociatedIcon($p);"
        "  if ($i -eq $null) { exit 2 };"
        "  $i.ToBitmap().Save($o, [System.Drawing.Imaging.ImageFormat]::Png);"
        "} catch { exit 3 }"
    )
    try:
        proc = run_hidden(
            ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", script],
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return dest if proc.returncode == 0 and dest.exists() else None


def mass_child(unit: dict, cfg: dict | None = None) -> Path | None:
    cfg = cfg or load_config()
    mass = library_root(cfg).resolve()
    folder = Path(unit.get("folder") or "")
    fp = Path(unit.get("filePath") or "")
    try:
        if folder.is_dir():
            rel = folder.resolve().relative_to(mass)
            return mass / rel.parts[0]
        if fp.is_file():
            rel = fp.resolve().relative_to(mass)
            return mass / rel.parts[0]
    except (ValueError, OSError, IndexError):
        pass
    if fp.is_file():
        return fp
    if folder.is_dir():
        return folder
    return None


def rename_unit(unit: dict, new_name: str, cfg: dict | None = None) -> dict:
    name = (new_name or "").strip()
    if not name or any(c in name for c in '<>:"/\\|?*'):
        return {"ok": False, "error": "bad name"}
    child = mass_child(unit, cfg)
    if child is None or not child.exists():
        return {"ok": False, "error": "item missing"}
    dest_name = name if child.is_dir() else (name if name.lower().endswith(child.suffix.lower()) else name + child.suffix)
    dest = child.parent / dest_name
    if dest.resolve() == child.resolve():
        unit["name"] = name
        return {"ok": True, "path": str(dest), "name": name}
    if dest.exists():
        return {"ok": False, "error": "already exists"}
    try:
        child.rename(dest)
    except OSError as exc:
        return {"ok": False, "error": str(exc)}
    old_folder = str(unit.get("folder") or "")
    old_fp = str(unit.get("filePath") or "")
    if child.is_dir() or dest.is_dir():
        unit["folder"] = str(dest)
        unit["id"] = dest.name
        if old_fp:
            unit["filePath"] = old_fp.replace(str(child), str(dest), 1)
    else:
        unit["filePath"] = str(dest)
        unit["file"] = dest.name
        unit["id"] = dest.stem
    unit["name"] = dest.stem if dest.is_file() else dest.name
    meta = load_meta()
    moved = {}
    for k, v in meta.items():
        nk = k.replace(old_fp.lower(), str(unit.get("filePath") or "").lower()) if old_fp else k
        nk = nk.replace(old_folder.lower(), str(unit.get("folder") or "").lower()) if old_folder else nk
        moved[nk] = v
    if moved != meta:
        META_PATH.write_text(json.dumps(moved, indent=2), encoding="utf-8")
    return {"ok": True, "path": str(dest), "name": unit["name"]}


WINERR = {
    2: "file missing",
    3: "path missing",
    5: "blocked (MOTW / ACL) — Zone.Identifier stream",
    32: "file in use (AV or another handle)",
    53: "network path gone",
    206: "path too long",
    225: "Windows / SmartScreen blocked the file",
    740: "needs admin",
    1155: "no program associated — do not use ShellExecute",
    1223: "cancelled",
    193: "not a valid Win32 exe",
}


def unblock_file(path: Path | str) -> bool:
    """Drop the Zone.Identifier ADS. That stream is what makes Windows show a red file dialog with no details."""
    p = Path(path) if path else None
    if os.name != "nt" or p is None or not p.exists():
        return False
    ads = str(p) + ":Zone.Identifier"
    try:
        os.remove(ads)
        return True
    except FileNotFoundError:
        return False
    except OSError:
        try:
            env = os.environ.copy()
            env["AW_U"] = str(p)
            run_hidden(
                ["powershell", "-NoProfile", "-Command", "Unblock-File -LiteralPath $env:AW_U"],
                env=env,
                capture_output=True,
                text=True,
                timeout=8,
            )
            return True
        except (OSError, subprocess.TimeoutExpired):
            return False


def unblock_app_dir() -> None:
    try:
        for p in APP_DIR.iterdir():
            if p.is_file():
                unblock_file(p)
    except OSError:
        pass


def winerr_text(exc: BaseException) -> str:
    code = getattr(exc, "winerror", None)
    if code is None:
        code = getattr(exc, "errno", None)
    if code in WINERR:
        return f"{WINERR[code]} ({code})"
    return f"{exc} ({code})" if code is not None else str(exc)


def unblock_tree(path: Path) -> int:
    if os.name != "nt" or not path.exists():
        return 0
    cmd = [
        "powershell",
        "-NoProfile",
        "-Command",
        "Get-ChildItem -LiteralPath $env:AW_UNBLOCK -Recurse -File -ErrorAction SilentlyContinue | Unblock-File",
    ]
    env = os.environ.copy()
    env["AW_UNBLOCK"] = str(path)
    try:
        subprocess.run(cmd, check=False, env=env, capture_output=True, text=True)
        return 1
    except OSError:
        return 0


def silent_command(unit: dict, target_dir: Path) -> list[str] | None:
    file_path = unit.get("filePath")
    if not file_path:
        return None
    flags = unit.get("silentFlags")
    engine = (unit.get("engine") or unit.get("silentHint") or "").lower()
    if isinstance(flags, list) and flags:
        out = [file_path]
        for f in flags:
            out.append(str(f).replace("{target}", str(target_dir)))
        return out
    if engine == "msi" or file_path.lower().endswith(".msi"):
        return ["msiexec", "/i", file_path, "/qn", "TARGETDIR=" + str(target_dir)]
    if engine == "innosetup":
        return [file_path, "/VERYSILENT", "/NORESTART", "/DIR=" + str(target_dir)]
    if engine == "nsis":
        dest = str(target_dir)
        if " " in dest:
            return None
        return [file_path, "/S", "/D=" + dest]
    return None


def launch(cmd: list[str], cwd: str | None = None) -> dict:
    if not cmd:
        return {"ok": False, "error": "empty command"}
    target = Path(cmd[0])
    if target.is_file():
        unblock_file(target)
    work = cwd or (str(target.parent) if target.is_file() else None)
    ext = target.suffix.lower()
    try:
        if os.name == "nt" and target.is_file() and ext in {".exe", ".com"}:
            subprocess.Popen([str(target), *cmd[1:]], cwd=work)
            return {"ok": True, "cmd": cmd}
        if os.name == "nt" and ext in {".bat", ".cmd"}:
            subprocess.Popen(["cmd", "/c", str(target), *cmd[1:]], cwd=work)
            return {"ok": True, "cmd": cmd}
        if os.name == "nt" and ext == ".msi":
            subprocess.Popen(["msiexec", "/i", str(target), *cmd[1:]], cwd=work)
            return {"ok": True, "cmd": cmd}
        subprocess.Popen(cmd, cwd=work)
        return {"ok": True, "cmd": cmd}
    except OSError as exc:
        return {"ok": False, "error": winerr_text(exc), "cmd": cmd}


def open_path(path: Path) -> dict:
    if not path.exists():
        return {"ok": False, "error": "missing"}
    try:
        if os.name == "nt":
            if path.is_dir():
                subprocess.Popen(["explorer", str(path)])
            else:
                subprocess.Popen(["explorer", "/select,", str(path)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
        return {"ok": True}
    except OSError as exc:
        return {"ok": False, "error": str(exc)}


def pick_dialog(kind: str) -> dict:
    if os.name == "nt":
        if kind == "folder":
            script = (
                "Add-Type -AssemblyName System.Windows.Forms;"
                "$d = New-Object System.Windows.Forms.FolderBrowserDialog;"
                "$d.Description = 'AW_FutaDepot';"
                "if ($d.ShowDialog() -eq 'OK') { [Console]::Out.Write($d.SelectedPath) }"
            )
        else:
            script = (
                "Add-Type -AssemblyName System.Windows.Forms;"
                "$d = New-Object System.Windows.Forms.OpenFileDialog;"
                "$d.Filter = 'Programs (*.exe;*.msi;*.bat)|*.exe;*.msi;*.bat;*.cmd|All|*.*';"
                "if ($d.ShowDialog() -eq 'OK') { [Console]::Out.Write($d.FileName) }"
            )
        try:
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-STA", "-Command", script],
                capture_output=True,
                text=True,
                timeout=300,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"ok": False, "error": str(exc)}
        value = (proc.stdout or "").strip()
        return {"ok": bool(value), "path": value}
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        if kind == "folder":
            value = filedialog.askdirectory()
        else:
            value = filedialog.askopenfilename()
        root.destroy()
        return {"ok": bool(value), "path": value or ""}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def parse_winget(text: str) -> list[dict]:
    items = []
    for line in text.splitlines():
        raw = line.rstrip()
        if not raw.strip():
            continue
        if re.match(r"^[-+\s]+$", raw):
            continue
        parts = re.split(r"\s{2,}", raw.strip())
        if len(parts) < 2:
            continue
        name, pkg = parts[0], parts[1]
        if name.lower() in HEADER_JUNK or pkg.lower() in HEADER_JUNK:
            continue
        if "." not in pkg and "-" not in pkg:
            continue
        items.append({"id": pkg, "name": name, "tag": "winget", "src": "winget"})
    return items


def store_list(query: str) -> dict:
    q = (query or "").strip().lower()
    catalog = []
    for row in load_catalog():
        item = {
            "id": row.get("id"),
            "name": row.get("name") or row.get("id"),
            "tag": row.get("tag") or "App",
            "src": "catalog",
        }
        if not item["id"]:
            continue
        blob = (item["name"] + " " + item["id"] + " " + item["tag"]).lower()
        if not q or q in blob:
            catalog.append(item)
    remote = []
    if os.name == "nt" and q:
        args = [
            "winget",
            "search",
            query,
            "--accept-source-agreements",
            "--disable-interactivity",
        ]
        try:
            proc = subprocess.run(args, capture_output=True, text=True, timeout=60, env=proxy_env(load_config()))
            remote = parse_winget(proc.stdout or "")
        except (OSError, subprocess.TimeoutExpired):
            remote = []
    seen = {x["id"].lower() for x in catalog}
    for item in remote:
        if item["id"].lower() not in seen:
            catalog.append(item)
            seen.add(item["id"].lower())
    remember_search(query, len(catalog))
    return {"ok": True, "items": catalog[:80], "windows": os.name == "nt"}


def load_json_list(path: Path) -> list:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else data.get("items") or []
    except (OSError, json.JSONDecodeError):
        return []


def remember_search(query: str, hits: int) -> None:
    q = (query or "").strip()
    if not q:
        return
    items = load_json_list(HISTORY_PATH)
    items.append({"q": q, "hits": hits, "at": dt.datetime.now().isoformat(timespec="seconds")})
    HISTORY_PATH.write_text(json.dumps(items[-200:], indent=2), encoding="utf-8")


def load_meta() -> dict:
    if not META_PATH.exists():
        return {"units": {}}
    try:
        data = json.loads(META_PATH.read_text(encoding="utf-8"))
        data.setdefault("units", {})
        return data
    except (OSError, json.JSONDecodeError):
        return {"units": {}}


def save_meta(data: dict) -> None:
    META_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def save_user_note(unit: dict, text: str) -> dict:
    meta = load_meta()
    units = meta.setdefault("units", {})
    rec = None
    for key in alias_keys(unit.get("filePath"), unit.get("folder"), unit.get("id"), unit.get("name"), unit.get("file")):
        got = units.get(key)
        if isinstance(got, dict):
            rec = got
            break
    if rec is None:
        rec = {}
        units[unit_key(unit)] = rec
    rec["userNote"] = text
    unit["userNote"] = text
    save_meta(meta)
    try:
        futa_db.upsert_note(library_root(load_config()), unit, text)
    except Exception:
        pass
    return {"ok": True}


META_FIELDS = (
    "verified",
    "notes",
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
    "userNote",
)


def norm_key(raw) -> str:
    return str(raw or "").strip().lower().replace("\\", "/").rstrip("/")


def alias_keys(*parts) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in parts:
        k = norm_key(raw)
        if not k or k in seen:
            continue
        seen.add(k)
        out.append(k)
        leaf = k.split("/")[-1]
        if leaf and leaf not in seen:
            seen.add(leaf)
            out.append(leaf)
        if "." in leaf:
            stem = leaf.rsplit(".", 1)[0]
            if stem and stem not in seen:
                seen.add(stem)
                out.append(stem)
    return out


def apply_meta(cats: list[dict]) -> None:
    meta = load_meta().get("units") or {}
    for cat in cats:
        for unit in cat["units"]:
            keys = alias_keys(unit.get("filePath"), unit.get("folder"), unit.get("id"), unit.get("name"), unit.get("file"))
            extra = None
            for key in keys:
                extra = meta.get(key)
                if isinstance(extra, dict):
                    break
            if not isinstance(extra, dict):
                continue
            unit["meta"] = extra
            for field in META_FIELDS:
                val = extra.get(field)
                if val not in (None, ""):
                    unit[field] = val
            hint = str(extra.get("silentHint") or extra.get("engine") or "").lower()
            if hint in {"innosetup", "nsis", "msi", "wix"}:
                unit["engine"] = hint
                unit["silent"] = True
            if extra.get("sourceUrl") or extra.get("homepage") or extra.get("updateUrl") or extra.get("wingetId"):
                unit["hasSource"] = True


def file_stat(path: str | None) -> dict:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {"missing": True}
    info = {"exists": True, "isFile": p.is_file(), "isDir": p.is_dir()}
    if p.is_file():
        info["bytes"] = p.stat().st_size
        info["ext"] = p.suffix.lower()
    return info


SKIP_TREE_DIR = {".git", "__pycache__", ".iconcache", "node_modules", "$recycle.bin", "system volume information"}
CRACK_TOKENS = (
    "crack", "keygen", "keymaker", "cracked", "warez", "codex", "skidrow",
    "reloaded", "fitgirl", "igggames", "serials", "serial.key", "key.dat",
)
MAX_TREE_FILES = 400
MAX_TREE_DEPTH = 5


def _flag_rel(rel: str) -> list[str]:
    s = rel.lower().replace("\\", "/")
    leaf = s.split("/")[-1]
    flags = []
    if any(t in s for t in CRACK_TOKENS):
        flags.append("crack")
    if leaf.endswith(".nfo") or leaf.endswith(".diz"):
        flags.append("nfo")
    if leaf in {"setup.exe", "install.exe", "installer.exe"} or leaf.endswith(".msi"):
        flags.append("setup")
    if "unins" in leaf or leaf.startswith("uninstall"):
        flags.append("uninstaller")
    if leaf in {"steam_api.dll", "steam_api64.dll", "steam_emu.dll"}:
        flags.append("steam")
    if leaf in {"unityplayer.dll", "data.win"}:
        flags.append("unity")
    if any(h in s for h in ("/save/", "/saves/", "savedata", "savegame")):
        flags.append("save")
    if "/x86/" in f"/{s}/" or leaf == "x86":
        flags.append("x86")
    if "/x64/" in f"/{s}/" or leaf == "x64":
        flags.append("x64")
    if "/bin/" in f"/{s}/":
        flags.append("bin")
    if leaf.endswith(".exe"):
        flags.append("exe")
    if leaf in {"thumbs.db", ".ds_store"} or leaf.endswith(".tmp") or leaf.startswith("~$"):
        flags.append("junk")
    return flags


def walk_unit_tree(root: str | Path | None) -> dict:
    empty = {"files": 0, "dirs": 0, "exe": 0, "dll": 0, "bytes": 0, "flags": [], "tree": [], "truncated": False}
    if not root:
        return empty
    p = Path(root)
    if not p.exists():
        return {**empty, "missing": True}
    files = 0
    dirs = 0
    exe = 0
    dll = 0
    total = 0
    flags: set[str] = set()
    tree: list[str] = []
    truncated = False

    def add_line(rel: str, size: int, extra: str = "") -> None:
        nonlocal truncated
        fl = _flag_rel(rel)
        for f in fl:
            flags.add(f)
        mark = ("  FLAG:" + ",".join(x for x in fl if x not in {"exe", "x86", "x64", "bin"})) if any(x not in {"exe", "x86", "x64", "bin"} for x in fl) else ""
        line = f"{rel}  {fmt_size(size)}{extra}{mark}"
        if len(tree) < MAX_TREE_FILES:
            tree.append(line)
        else:
            truncated = True

    if p.is_file():
        try:
            n = p.stat().st_size
        except OSError:
            n = 0
        add_line(p.name, n)
        extra_zip = _archive_names(p)
        for name in extra_zip:
            add_line(p.name + " ! " + name, 0, "  in-archive")
        return {
            "files": 1,
            "dirs": 0,
            "exe": 1 if p.suffix.lower() == ".exe" else 0,
            "dll": 1 if p.suffix.lower() == ".dll" else 0,
            "bytes": n,
            "flags": sorted(flags),
            "tree": tree,
            "truncated": truncated,
        }

    for dirpath, dirnames, filenames in os.walk(p):
        rel_base = Path(dirpath)
        try:
            depth = len(rel_base.relative_to(p).parts)
        except ValueError:
            depth = 0
        dirnames[:] = [d for d in dirnames if d.lower() not in SKIP_TREE_DIR and not d.startswith(".")]
        if depth >= MAX_TREE_DEPTH:
            dirnames[:] = []
            continue
        dirs += len(dirnames)
        for fn in filenames:
            rel = (rel_base / fn).relative_to(p).as_posix()
            fp = rel_base / fn
            try:
                n = fp.stat().st_size
            except OSError:
                n = 0
            files += 1
            total += n
            low = fn.lower()
            if low.endswith(".exe"):
                exe += 1
            elif low.endswith(".dll"):
                dll += 1
            add_line(rel, n)
            if files >= MAX_TREE_FILES:
                truncated = True
                dirnames[:] = []
                break
        if truncated:
            break
    if p.suffix.lower() in {".zip", ".7z", ".rar"} or any(x.lower().endswith(".zip") for x in []):
        pass
    return {
        "files": files,
        "dirs": dirs,
        "exe": exe,
        "dll": dll,
        "bytes": total,
        "flags": sorted(flags),
        "tree": tree,
        "truncated": truncated,
    }


def _archive_names(path: Path) -> list[str]:
    if path.suffix.lower() != ".zip":
        return []
    try:
        with zipfile.ZipFile(path) as zf:
            return [n for n in zf.namelist() if not n.endswith("/")][:80]
    except (OSError, zipfile.BadZipFile):
        return []


def attach_tree(unit: dict) -> dict:
    root = unit.get("folder") or unit.get("filePath")
    info = walk_unit_tree(root)
    unit["tree"] = info["tree"]
    unit["treeFlags"] = info["flags"]
    unit["treeCounts"] = {k: info[k] for k in ("files", "dirs", "exe", "dll", "bytes")}
    unit["treeTruncated"] = info["truncated"]
    if "crack" in info["flags"] and not unit.get("notes"):
        unit["localNote"] = "folder contains crack/keygen-like names — inspect, do not run those as payload"
    return info


def build_dump(cfg: dict | None = None) -> dict:
    cfg = cfg or load_config()
    cats = scan_all(cfg)
    units = []
    for cat in cats:
        for unit in cat["units"]:
            attach_tree(unit)
            unit["localKind"] = unit.get("kind")
            unit["localGroup"] = KIND_FOLDER.get(unit.get("kind") or "", "Unknown")
            unit["localEngine"] = unit.get("engine")
            unit["localSilent"] = unit.get("silent")
            unit["localPayload"] = unit.get("payloadRel")
            unit["localFlags"] = list(unit.get("treeFlags") or [])
            row = dict(unit)
            row["category"] = cat["id"]
            row["categoryPath"] = cat.get("path")
            row["legend"] = LEGEND.get(unit.get("engine") or unit.get("kind") or "unknown", LEGEND["unknown"])
            row["stat"] = file_stat(unit.get("filePath"))
            units.append(row)
    return {
        "ok": True,
        "version": VERSION,
        "at": dt.datetime.now().isoformat(timespec="seconds"),
        "root": str(library_root(cfg)),
        "inbox": str(INBOX_DIR),
        "legend": LEGEND,
        "categories": cats,
        "units": units,
        "searchHistory": load_json_list(HISTORY_PATH),
        "meta": load_meta(),
        "config": {k: cfg.get(k) for k in ("libraryRoot", "paths", "channelId")},
    }


def write_report(cfg: dict | None = None) -> dict:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    dump = build_dump(cfg)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    json_path = REPORTS_DIR / f"depot-dump-{stamp}.json"
    md_path = REPORTS_DIR / f"depot-report-{stamp}.md"
    json_path.write_text(json.dumps(dump, indent=2), encoding="utf-8")
    lines = [
        f"# AW_FutaDepot dump {dump['at']}",
        f"version {dump['version']}",
        f"root `{dump['root']}`",
        f"inbox `{dump['inbox']}`",
        "",
        "## Legend",
    ]
    for key, spec in LEGEND.items():
        lines.append(f"- `{key}` {spec['label']} · silent={spec['silent']} · {spec['note']}")
    lines += ["", "## Categories"]
    for cat in dump["categories"]:
        lines.append(f"### {cat['id']}  ({len(cat['units'])})")
        lines.append(f"- path `{cat.get('path')}`")
        lines.append(f"- install `{cat.get('target') or '-'}`")
        for unit in cat["units"]:
            st = file_stat(unit.get("filePath"))
            size = st.get("bytes")
            size_s = f"{size} B" if size else "-"
            lines.append(
                f"  - **{unit.get('name')}** · {unit.get('kind')} · {unit.get('engine')} · "
                f"silent={unit.get('silent')} · launch={unit.get('canLaunch')} · {size_s}"
            )
            lines.append(f"    `{unit.get('filePath') or unit.get('folder')}`")
            counts = unit.get("treeCounts") or {}
            flags = unit.get("treeFlags") or []
            if counts or flags:
                lines.append(
                    f"    files={counts.get('files', 0)} dirs={counts.get('dirs', 0)} "
                    f"exe={counts.get('exe', 0)} dll={counts.get('dll', 0)} flags={','.join(flags) or '-'}"
                )
            for line in (unit.get("tree") or [])[:80]:
                lines.append(f"      {line}")
            if unit.get("treeTruncated"):
                lines.append("      … truncated")
            if unit.get("meta"):
                lines.append(f"    meta: `{json.dumps(unit['meta'], ensure_ascii=False)}`")
    lines += ["", "## Search history"]
    hist = dump.get("searchHistory") or []
    if not hist:
        lines.append("- empty")
    for row in hist:
        lines.append(f"- `{row.get('at')}` q=`{row.get('q')}` hits={row.get('hits')}")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    shutil.copy2(json_path, REPORTS_DIR / "depot-dump-latest.json")
    shutil.copy2(md_path, REPORTS_DIR / "depot-report-latest.md")
    return {"ok": True, "json": str(json_path), "md": str(md_path), "units": len(dump["units"])}


def import_meta_file(path: str) -> dict:
    p = Path(path)
    if not p.is_file():
        return {"ok": False, "error": "file missing"}
    try:
        text = p.read_text(encoding="utf-8")
        if text.startswith("\ufeff"):
            text = text[1:]
        if "```" in text:
            m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
            if m:
                text = m.group(1)
        i = text.find("{")
        if i > 0:
            text = text[i:]
        data = json.loads(text)
    except json.JSONDecodeError:
        return {"ok": False, "error": "need JSON from the dump chat"}
    incoming = {}
    if isinstance(data, dict) and isinstance(data.get("units"), dict):
        incoming = data["units"]
    elif isinstance(data, dict) and isinstance(data.get("units"), list):
        for row in data["units"]:
            if not isinstance(row, dict):
                continue
            key = row.get("filePath") or row.get("id") or row.get("name") or ""
            if key:
                incoming[key] = row.get("meta") or row
    elif isinstance(data, dict):
        incoming = {str(k): v for k, v in data.items() if isinstance(v, dict) and k not in {"updated", "ok", "version"}}
    else:
        return {"ok": False, "error": "unrecognized meta shape"}
    meta = load_meta()
    units = meta.setdefault("units", {})
    n = 0
    for key, val in incoming.items():
        if not isinstance(val, dict):
            continue
        for ak in alias_keys(key, val.get("filePath"), val.get("folder"), val.get("id"), val.get("name"), val.get("file")):
            units[ak] = val
        n += 1
    meta["updated"] = dt.datetime.now().isoformat(timespec="seconds")
    save_meta(meta)
    return {"ok": True, "merged": n, "aliases": len(units), "path": str(META_PATH)}


def fetch_url(url: str, timeout: int = 8) -> dict:
    url = (url or "").strip()
    if not url:
        return {"ok": False, "error": "empty url"}
    req = urllib.request.Request(url, headers={"User-Agent": "AW_FutaDepot/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
        text = raw.decode("utf-8", errors="replace")
        low = text.lstrip()[:80].lower()
        if low.startswith("<!doctype") or low.startswith("<html") or "accounts.google.com" in text[:400]:
            return {"ok": False, "error": "channel returned a login page, not JSON"}
        return {"ok": True, "text": text}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "error": "HTTP " + str(exc.code) + " " + url}
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {"ok": False, "error": str(exc)}


def parse_ver(text: str) -> tuple[int, ...]:
    parts = []
    for bit in (text or "0").split("."):
        try:
            parts.append(int(bit))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def check_update(cfg: dict | None = None) -> dict:
    cfg = cfg or load_config()
    url = (cfg.get("versionUrl") or "").strip()
    if not url or "VERSIONFILE" in url:
        return {"ok": False, "error": "version url not set", "current": VERSION}
    got = fetch_url(url)
    if not got.get("ok"):
        return {"ok": False, "error": got.get("error"), "current": VERSION}
    try:
        data = json.loads(got["text"])
    except json.JSONDecodeError:
        return {"ok": False, "error": "version file is not JSON", "current": VERSION}
    remote = str(data.get("version") or "")
    zip_url = data.get("zip") or ""
    newer = parse_ver(remote) > parse_ver(VERSION) if remote else False
    return {
        "ok": True,
        "current": VERSION,
        "remote": remote,
        "newer": newer,
        "zip": zip_url,
        "notes": data.get("notes") or "",
    }


def fetch_bytes(url: str, progress=None) -> dict:
    url = (url or "").strip()
    if not url:
        return {"ok": False, "error": "empty url"}
    req = urllib.request.Request(url, headers={"User-Agent": "AW_FutaDepot"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            total = int(resp.headers.get("Content-Length") or 0)
            chunks: list[bytes] = []
            n = 0
            while True:
                piece = resp.read(65536)
                if not piece:
                    break
                chunks.append(piece)
                n += len(piece)
                if progress:
                    progress(n, total)
        return {"ok": True, "data": b"".join(chunks)}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "error": "HTTP " + str(exc.code) + " zip"}
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {"ok": False, "error": str(exc)}


def apply_update(zip_url: str, progress=None) -> dict:
    got = fetch_bytes(zip_url, progress=progress)
    if not got.get("ok"):
        return got
    raw = got["data"]
    if raw[:2] != b"PK":
        return {"ok": False, "error": "download is not a zip"}
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    zpath = REPORTS_DIR / "update.zip"
    zpath.write_bytes(raw)
    incoming = APP_DIR / "_incoming"
    if incoming.exists():
        shutil.rmtree(incoming)
    incoming.mkdir()
    with zipfile.ZipFile(zpath) as zf:
        zf.extractall(incoming)
    src = incoming / "AW_FutaDepot"
    if not src.is_dir():
        src = incoming
    bat = APP_DIR / "_apply_update.bat"
    bat.write_text(
        "\r\n".join(
            [
                "@echo off",
                "cd /d \"%~dp0\"",
                "timeout /t 2 /nobreak >nul",
                f"robocopy \"{src}\" \".\" /E /NFL /NDL /NJH /NJS /XD library inbox icons-custom reports _incoming /XF config.json depot-meta.json search-history.json AW_FutaDepot.exe",
                "if exist \"_incoming\\AW_FutaDepot\\AW_FutaDepot.exe\" copy /y \"_incoming\\AW_FutaDepot\\AW_FutaDepot.exe\" \"AW_FutaDepot.exe\" >nul",
                "rmdir /s /q \"_incoming\"",
                "start \"\" \"AW_FutaDepot.exe\"",
                "del \"%~f0\"",
            ]
        ),
        encoding="utf-8",
    )
    if os.name == "nt":
        subprocess.Popen(["cmd", "/c", str(bat)], cwd=str(APP_DIR))
        return {"ok": True, "restart": True}
    for item in src.iterdir():
        if item.name in {"config.json", "depot-meta.json", "search-history.json", "library", "inbox", "icons-custom", "reports"}:
            continue
        dest = APP_DIR / item.name
        if item.is_dir():
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)
    return {"ok": True, "restart": False}


GH_SYNC_REPO = "2biteWolf/AW_FutaDepot"
GH_SYNC_BRANCH = "main"
GH_META_PATH = "channel/depot-meta.json"
GH_DUMP_PATH = "channel/depot-dump-latest.json"
DUMP_PUSH_MAX = 8 * 1024 * 1024


def _which(cmd: str) -> str | None:
    return shutil.which(cmd)


def ensure_local_meta() -> Path:
    """Ensure local depot-meta.json exists (empty units if missing)."""
    if not META_PATH.is_file():
        META_PATH.write_text(
            json.dumps({"updated": "", "units": {}}, indent=2),
            encoding="utf-8",
        )
    return META_PATH


def gh_auth_status() -> dict:
    gh = _which("gh")
    if not gh:
        return {"ok": False, "missing": True, "error": "gh not on PATH"}
    try:
        proc = subprocess.run(
            [gh, "auth", "status"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "missing": False, "error": str(exc)}
    out = (proc.stdout or "") + (proc.stderr or "")
    logged = proc.returncode == 0 and "Logged in" in out
    return {
        "ok": logged,
        "missing": False,
        "logged_in": logged,
        "code": proc.returncode,
        "text": out.strip(),
        "error": None if logged else "gh not logged in — run: gh auth login",
    }


def gh_install_hint() -> dict:
    """Structured result so UI can confirm installing GitHub CLI."""
    if os.name == "nt":
        if _which("winget"):
            return {
                "ok": False,
                "need_install": True,
                "tool": "gh",
                "installer": "winget",
                "command": "winget install GitHub.cli",
                "error": "GitHub CLI (gh) not found. Install with winget?",
            }
        if _which("scoop"):
            return {
                "ok": False,
                "need_install": True,
                "tool": "gh",
                "installer": "scoop",
                "command": "scoop install gh",
                "error": "GitHub CLI (gh) not found. Install with scoop?",
            }
        if _which("choco"):
            return {
                "ok": False,
                "need_install": True,
                "tool": "gh",
                "installer": "choco",
                "command": "choco install gh -y",
                "error": "GitHub CLI (gh) not found. Install with chocolatey?",
            }
        return {
            "ok": False,
            "need_install": True,
            "tool": "gh",
            "installer": "manual",
            "command": "winget install GitHub.cli",
            "url": "https://cli.github.com/",
            "error": "GitHub CLI (gh) not found. Install from https://cli.github.com/ then retry SYNC.",
        }
    return {
        "ok": False,
        "need_install": True,
        "tool": "gh",
        "installer": "manual",
        "command": "",
        "url": "https://cli.github.com/",
        "error": "GitHub CLI (gh) not found. Install from https://cli.github.com/",
    }


def run_install_command(command: str) -> dict:
    """Run a user-confirmed install command (winget/scoop/choco)."""
    command = (command or "").strip()
    if not command:
        return {"ok": False, "error": "empty install command"}
    try:
        proc = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=1800,
            env=proxy_env(load_config()),
        )
        ok = proc.returncode == 0
        return {
            "ok": ok,
            "code": proc.returncode,
            "out": (proc.stdout or "")[-2000:],
            "err": (proc.stderr or "")[-2000:],
            "error": None if ok else ((proc.stderr or proc.stdout or "install failed")[-400:]),
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "error": str(exc)}


def _gh_api_json(method: str, path: str, body: dict | None = None) -> dict:
    gh = _which("gh")
    if not gh:
        return {"ok": False, "error": "gh missing"}
    cmd = [gh, "api", "-X", method, path]
    if body is not None:
        cmd += ["--input", "-"]
    try:
        proc = subprocess.run(
            cmd,
            input=json.dumps(body) if body is not None else None,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "error": str(exc)}
    raw = (proc.stdout or "").strip()
    if proc.returncode != 0:
        err = (proc.stderr or raw or "gh api failed")[-600:]
        return {"ok": False, "error": err, "code": proc.returncode}
    if not raw:
        return {"ok": True, "data": {}}
    try:
        return {"ok": True, "data": json.loads(raw)}
    except json.JSONDecodeError:
        return {"ok": True, "data": {"raw": raw}}


def gh_put_file(repo: str, path: str, content: bytes, message: str, branch: str = GH_SYNC_BRANCH) -> dict:
    """Create or update a file on GitHub via gh api PUT contents (base64)."""
    api = f"repos/{repo}/contents/{path}"
    sha = None
    got = _gh_api_json("GET", f"{api}?ref={branch}")
    if got.get("ok") and isinstance(got.get("data"), dict):
        sha = got["data"].get("sha")
    body = {
        "message": message,
        "content": base64.b64encode(content).decode("ascii"),
        "branch": branch,
    }
    if sha:
        body["sha"] = sha
    put = _gh_api_json("PUT", api, body)
    if not put.get("ok"):
        return {"ok": False, "error": put.get("error") or "put failed", "path": path}
    return {"ok": True, "path": path, "sha": ((put.get("data") or {}).get("content") or {}).get("sha") or sha}


def push_sync_github(cfg: dict) -> dict:
    """Push local depot-meta.json and optionally dump to repo channel/."""
    if not _which("gh"):
        hint = gh_install_hint()
        hint["pushed"] = False
        return hint
    auth = gh_auth_status()
    if not auth.get("ok"):
        return {
            "ok": False,
            "pushed": False,
            "need_login": True,
            "error": auth.get("error") or "gh not logged in",
            "hint": "Run: gh auth login  (browser / device flow). Do not paste tokens into the app.",
            "auth": auth,
        }
    meta_path = ensure_local_meta()
    meta_bytes = meta_path.read_bytes()
    msg = "sync: update depot meta/dump"
    results = []
    meta_r = gh_put_file(GH_SYNC_REPO, GH_META_PATH, meta_bytes, msg)
    results.append(meta_r)
    dump_r = {"ok": False, "skipped": True, "reason": "missing"}
    dump_src = REPORTS_DIR / "depot-dump-latest.json"
    if dump_src.is_file():
        size = dump_src.stat().st_size
        if size > DUMP_PUSH_MAX:
            dump_r = {"ok": False, "skipped": True, "reason": f"dump too large ({size} > {DUMP_PUSH_MAX})"}
        else:
            dump_r = gh_put_file(GH_SYNC_REPO, GH_DUMP_PATH, dump_src.read_bytes(), msg)
    results.append(dump_r)
    ok = bool(meta_r.get("ok"))
    return {
        "ok": ok,
        "pushed": ok,
        "meta": meta_r,
        "dump": dump_r,
        "error": None if ok else (meta_r.get("error") or "meta push failed"),
    }


def push_sync_drive(cfg: dict) -> dict:
    """Optional rclone copy of meta + dump into driveFolder remote path."""
    target = (cfg.get("syncTarget") or "github").lower()
    if "drive" not in target and target != "both":
        return {"ok": True, "skipped": True, "reason": "syncTarget is not drive"}
    folder = (cfg.get("driveFolder") or "").strip()
    if not folder:
        return {"ok": False, "error": "driveFolder empty"}
    if not _which("rclone"):
        return {
            "ok": False,
            "need_install": True,
            "tool": "rclone",
            "url": "https://rclone.org/install/",
            "error": "rclone not found. Install from https://rclone.org/install/ or skip Drive push.",
        }
    ensure_local_meta()
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    files = [META_PATH]
    dump = REPORTS_DIR / "depot-dump-latest.json"
    if dump.is_file() and dump.stat().st_size <= DUMP_PUSH_MAX:
        files.append(dump)
    # driveFolder may be a share URL; rclone remote must be configured by user.
    remote = folder
    if remote.startswith("http"):
        return {
            "ok": False,
            "error": "driveFolder is a URL. Set syncTarget drive remote like gdrive:AW_FutaDepot/channel",
        }
    try:
        for f in files:
            proc = subprocess.run(
                ["rclone", "copy", str(f), remote, "--transfers", "1"],
                capture_output=True,
                text=True,
                timeout=300,
            )
            if proc.returncode != 0:
                return {"ok": False, "error": (proc.stderr or proc.stdout or "rclone fail")[-400:]}
        return {"ok": True, "pushed": True, "files": [f.name for f in files], "remote": remote}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "error": str(exc)}


def pull_sync_meta(cfg: dict) -> dict:
    url = (cfg.get("metaUrl") or "").strip()
    if not url:
        return {"ok": False, "error": "metaUrl empty"}
    got = fetch_url(url)
    if not got.get("ok"):
        return got
    tmp = REPORTS_DIR / "depot-meta-pulled.json"
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    tmp.write_text(got["text"], encoding="utf-8")
    try:
        json.loads(got["text"])
    except json.JSONDecodeError:
        return {"ok": False, "error": "pulled meta is not JSON"}
    return import_meta_file(str(tmp))


def sync_channel(cfg: dict | None = None) -> dict:
    """Write report, push sync DB to GitHub channel/, then pull metaUrl."""
    cfg = cfg or load_config()
    report = write_report(cfg)
    target = (cfg.get("syncTarget") or "github").lower()
    push = {"ok": True, "skipped": True}
    drive = {"ok": True, "skipped": True}

    if target in {"github", "both", ""}:
        push = push_sync_github(cfg)
        if push.get("need_install") or push.get("need_login"):
            return {
                "ok": False,
                "report": report,
                "push": push,
                "pull": {"ok": False, "skipped": True},
                "drive": drive,
                "folder": cfg.get("driveFolder") or "",
                "need_install": push.get("need_install"),
                "need_login": push.get("need_login"),
                "error": push.get("error"),
                "command": push.get("command"),
                "installer": push.get("installer"),
                "hint": push.get("hint"),
                "url": push.get("url"),
                "tool": push.get("tool") or "gh",
            }

    if target in {"drive", "both"}:
        drive = push_sync_drive(cfg)

    pulled = pull_sync_meta(cfg)
    ok = bool(push.get("ok") or push.get("skipped")) and bool(pulled.get("ok") or False)
    # push failure is soft if meta still pushed? require meta push when github
    if target in {"github", "both", ""} and not push.get("ok") and not push.get("skipped"):
        ok = False
    return {
        "ok": ok or bool(pulled.get("ok")),
        "report": report,
        "push": push,
        "pull": pulled,
        "drive": drive,
        "folder": cfg.get("driveFolder") or "",
        "error": None
        if (ok or pulled.get("ok"))
        else (push.get("error") or pulled.get("error") or drive.get("error")),
    }


def winget_install(pkg_id: str) -> dict:
    if not pkg_id:
        return {"ok": False, "error": "missing id"}
    if os.name != "nt":
        return {"ok": False, "error": "winget works on Windows only", "id": pkg_id}
    cmd = [
        "winget",
        "install",
        "-e",
        "--id",
        pkg_id,
        "--accept-package-agreements",
        "--accept-source-agreements",
        "--disable-interactivity",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1800, env=proxy_env(load_config()))
        return {
            "ok": proc.returncode == 0,
            "code": proc.returncode,
            "out": (proc.stdout or "")[-4000:],
            "err": (proc.stderr or "")[-2000:],
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "error": str(exc)}


def find_unit(cats: list[dict], cat_id: str, unit_id: str) -> tuple[dict | None, dict | None]:
    for cat in cats:
        if cat["id"] != cat_id:
            continue
        for unit in cat["units"]:
            if unit["id"] == unit_id or unit.get("name") == unit_id:
                return cat, unit
    return None, None


def add_file_to_category(cat: dict, src: str) -> dict:
    path = Path(src)
    if not path.is_file():
        return {"ok": False, "error": "file missing"}
    dest_dir = Path(cat["path"])
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / path.name
    if dest.resolve() != path.resolve():
        shutil.copy2(path, dest)
    return {"ok": True, "path": str(dest)}


def delete_unit(cat: dict, unit: dict) -> dict:
    folder = Path(unit.get("folder") or "")
    file_path = Path(unit["filePath"]) if unit.get("filePath") else None
    cat_path = Path(cat["path"]).resolve()
    try:
        if folder.resolve() == cat_path and file_path and file_path.parent.resolve() == cat_path:
            file_path.unlink()
            return {"ok": True}
        if folder.exists() and cat_path in folder.resolve().parents:
            shutil.rmtree(folder)
            return {"ok": True}
        if file_path and file_path.exists() and cat_path in file_path.resolve().parents:
            file_path.unlink()
            return {"ok": True}
        return {"ok": False, "error": "refuses to delete outside category"}
    except OSError as exc:
        return {"ok": False, "error": str(exc)}


PACK_FILES = [
    "app.py",
    "ui.py",
    "config.example.json",
    "icon.ico",
    "icon128.png",
    "AW_FutaDepot.exe",
    "START.bat",
    "COPY_TO.bat",
    "launcher.cs",
    "README.md",
    "INSTALL.txt",
    "CHANGELOG.md",
    "CHANGELOG.txt",
]
SKIP_COPY_DIR = {"__pycache__", ".iconcache", ".git", "__macosx", "$recycle.bin"}


def _skip_copy_dir(name: str) -> bool:
    if name == ".futa-db":
        return False
    return name in SKIP_COPY_DIR or name.startswith(".")


def _skip_copy_file(name: str) -> bool:
    low = name.lower()
    if low.endswith(".pyc") or low in {"thumbs.db", "ehthumbs.db", ".ds_store"}:
        return True
    return False


def count_copy_files(root: Path) -> int:
    if root.is_file():
        return 0 if _skip_copy_file(root.name) else 1
    if not root.is_dir():
        return 0
    n = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not _skip_copy_dir(d)]
        for fn in filenames:
            if not _skip_copy_file(fn):
                n += 1
    return n


def tree_bytes(root: Path) -> int:
    if root.is_file():
        try:
            return root.stat().st_size
        except OSError:
            return 0
    if not root.is_dir():
        return 0
    total = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not _skip_copy_dir(d)]
        for fn in filenames:
            if _skip_copy_file(fn):
                continue
            try:
                total += (Path(dirpath) / fn).stat().st_size
            except OSError:
                continue
    return total


def copy_plan(cfg: dict) -> dict:
    """App files + whole library (_FutaMass and extra roots), not just the launcher."""
    items = []
    seen: set[str] = set()

    def add(src: Path, rel: str) -> None:
        key = str(src.resolve()) if src.exists() else ""
        if not src.exists() or (key and key in seen):
            return
        if key:
            seen.add(key)
        n = tree_bytes(src)
        items.append({"src": str(src), "rel": rel, "bytes": n, "dir": src.is_dir()})

    for name in PACK_FILES:
        add(APP_DIR / name, name)
    add(APP_DIR / "lib", "lib")
    add(APP_DIR / "docs", "docs")
    add(APP_DIR / "web", "web")
    add(APP_DIR / "channel", "channel")
    add(APP_DIR / "win", "win")
    lib = library_root(cfg)
    add(lib, lib.name)
    for extra in cfg.get("addedCategories") or []:
        raw = extra.get("root") or extra.get("path")
        if not raw:
            continue
        p = Path(raw)
        name = extra.get("id") or extra.get("name") or p.name
        add(p, name)
    add(APP_DIR / "icons-custom", "icons-custom")
    add(APP_DIR / "reports", "reports")
    add(APP_DIR / "win-snapshot", "win-snapshot")
    add(APP_DIR / "depot-meta.json", "depot-meta.json")
    total = sum(i["bytes"] for i in items)
    lib_bytes = sum(i["bytes"] for i in items if i["rel"] in {lib.name} or Path(i["src"]).is_dir() and i["rel"] not in {"channel", "win", "icons-custom", "reports"})
    app_bytes = total - lib_bytes
    return {"ok": True, "total": total, "appBytes": app_bytes, "libBytes": lib_bytes, "items": items, "libName": lib.name}


def fmt_size(n: int) -> str:
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.2f} GB"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f} MB"
    if n >= 1000:
        return f"{n / 1000:.0f} KB"
    return f"{n} B"


def pack_bytes() -> int:
    return copy_plan(load_config()).get("total") or 0


def _copy_file(src: Path, dest: Path, progress) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    if progress:
        try:
            progress(src.stat().st_size, src.name)
        except OSError:
            progress(0, src.name)


def _copy_tree(src: Path, dest: Path, progress) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for dirpath, dirnames, filenames in os.walk(src):
        dirnames[:] = [d for d in dirnames if not _skip_copy_dir(d)]
        rel = Path(dirpath).relative_to(src)
        (dest / rel).mkdir(parents=True, exist_ok=True)
        for fn in filenames:
            if _skip_copy_file(fn):
                continue
            s = Path(dirpath) / fn
            d = dest / rel / fn
            try:
                shutil.copy2(s, d)
                if progress:
                    progress(s.stat().st_size, fn)
            except OSError:
                continue


def install_to(dest_root: str, cfg: dict | None = None, progress=None) -> dict:
    cfg = cfg or load_config()
    plan = copy_plan(cfg)
    dest = Path(dest_root) / "AW_FutaDepot"
    dest.mkdir(parents=True, exist_ok=True)
    try:
        dest_res = dest.resolve()
        src_res = APP_DIR.resolve()
        if dest_res == src_res or src_res in dest_res.parents or dest_res in src_res.parents:
            return {"ok": False, "error": "destination is the running folder"}
    except OSError:
        pass
    copied = []
    for item in plan["items"]:
        src = Path(item["src"])
        target = dest / item["rel"]
        try:
            if src.is_file():
                _copy_file(src, target, progress)
            elif os.name == "nt":
                import lib_opt

                r = lib_opt.robocopy_tree(src, target)
                if not r.get("ok"):
                    _copy_tree(src, target, progress)
            else:
                _copy_tree(src, target, progress)
            copied.append(item["rel"])
        except OSError as exc:
            return {"ok": False, "error": str(exc), "dest": str(dest), "copied": copied}
    missing = []
    for item in plan["items"]:
        src = Path(item["src"])
        target = dest / item["rel"]
        if item["dir"]:
            src_n = count_copy_files(src)
            dst_n = count_copy_files(target)
            if dst_n < src_n:
                missing.append(f"{item['rel']}: {dst_n}/{src_n} files")
        elif not target.is_file():
            missing.append(item["rel"])
    if missing:
        return {"ok": False, "error": "copy incomplete: " + "; ".join(missing[:8]), "dest": str(dest), "copied": copied}
    return {"ok": True, "dest": str(dest), "copied": copied, "bytes": plan["total"]}


def list_drives() -> list[dict]:
    system = (os.environ.get("SystemDrive") or "C:").rstrip("\\/") + "\\"
    out = []
    if os.name == "nt":
        types = {0: "unknown", 1: "no-root", 2: "removable", 3: "fixed", 4: "network", 5: "cd", 6: "ram"}
        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            root = Path(f"{letter}:/")
            if not root.exists():
                continue
            free = total = 0
            try:
                usage = shutil.disk_usage(root)
                free, total = usage.free, usage.total
            except OSError:
                pass
            dtype = 3
            try:
                dtype = ctypes_drive_type(f"{letter}:\\")
            except Exception:
                pass
            path = f"{letter}:\\"
            out.append(
                {
                    "path": path,
                    "free": free,
                    "total": total,
                    "label": letter,
                    "kind": types.get(dtype, "fixed"),
                    "system": path.upper() == system.upper(),
                    "boot": path.upper() == system.upper(),
                }
            )
        return out
    for p in [Path("/"), Path.home()]:
        try:
            usage = shutil.disk_usage(p)
            out.append(
                {
                    "path": str(p),
                    "free": usage.free,
                    "total": usage.total,
                    "label": p.name or "/",
                    "kind": "fixed",
                    "system": True,
                    "boot": True,
                }
            )
        except OSError:
            pass
    return out


def ctypes_drive_type(path: str) -> int:
    if os.name != "nt":
        return 3
    import ctypes

    return int(ctypes.windll.kernel32.GetDriveTypeW(path))


def proxy_env(cfg: dict) -> dict:
    env = os.environ.copy()
    if cfg.get("proxyEnabled"):
        http = (cfg.get("proxyHttp") or "").strip()
        https = (cfg.get("proxyHttps") or http).strip()
        if http:
            env["HTTP_PROXY"] = http
            env["http_proxy"] = http
        if https:
            env["HTTPS_PROXY"] = https
            env["https_proxy"] = https
    return env


def startup_dir() -> Path | None:
    if os.name != "nt":
        return None
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return None
    return Path(appdata) / "Microsoft/Windows/Start Menu/Programs/Startup"


def set_autostart(enabled: bool) -> dict:
    folder = startup_dir()
    if folder is None:
        return {"ok": False, "error": "startup folder only on Windows"}
    folder.mkdir(parents=True, exist_ok=True)
    link = folder / "AW_FutaDepot.lnk"
    exe = APP_DIR / "AW_FutaDepot.exe"
    target = str(exe if exe.exists() else APP_DIR / "START.bat")
    if not enabled:
        if link.exists():
            link.unlink()
        return {"ok": True, "autostart": False}
    script = (
        "$ws = New-Object -ComObject WScript.Shell;"
        "$s = $ws.CreateShortcut($env:AW_LNK);"
        "$s.TargetPath = $env:AW_TARGET;"
        "$s.WorkingDirectory = $env:AW_DIR;"
        "$s.IconLocation = $env:AW_ICON;"
        "$s.Save()"
    )
    env = os.environ.copy()
    env["AW_LNK"] = str(link)
    env["AW_TARGET"] = target
    env["AW_DIR"] = str(APP_DIR)
    icon = APP_DIR / "icon.ico"
    env["AW_ICON"] = str(icon if icon.exists() else target)
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "error": str(exc)}
    if proc.returncode != 0:
        return {"ok": False, "error": proc.stderr or "shortcut fail"}
    return {"ok": True, "autostart": True, "link": str(link)}


def open_windows(page: str) -> dict:
    allowed = {
        "defender": "ms-settings:windowsdefender",
        "activation": "ms-settings:activation",
        "proxy": "ms-settings:network-proxy",
        "startup": "ms-settings:startupapps",
        "update": "ms-settings:windowsupdate",
        "network": "ms-settings:network",
    }
    uri = allowed.get(page)
    if not uri:
        return {"ok": False, "error": "unknown page"}
    if os.name != "nt":
        return {"ok": False, "error": "Windows only"}
    try:
        subprocess.Popen(["cmd", "/c", "start", "", uri], shell=False)
        return {"ok": True, "page": page}
    except OSError as exc:
        return {"ok": False, "error": str(exc)}


def main() -> None:
    import ui as depot_ui

    depot_ui.main()


if __name__ == "__main__":
    main()
