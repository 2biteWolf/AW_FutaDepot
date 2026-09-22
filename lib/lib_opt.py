#!/usr/bin/env python3
"""Library size: junk sweep + transparent Windows compact. Copy via robocopy."""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

JUNK_FILE = {
    "thumbs.db",
    "ehthumbs.db",
    "ehthumbs_vista.db",
    ".ds_store",
    "iconcache.db",
    "thumbs.db:encryptable",
}
JUNK_EXT = {".tmp", ".temp", ".crdownload", ".partial", ".download"}
JUNK_DIR = {"__macosx", "__pycache__", ".git", ".iconcache", "$recycle.bin", "system volume information"}
SKIP_COMPACT_EXT = {
    ".zip", ".7z", ".rar", ".gz", ".xz", ".bz2", ".cab", ".msi", ".msix",
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".mp4", ".mkv", ".webm", ".avi",
    ".mp3", ".aac", ".ogg", ".flac", ".iso", ".wim", ".esd",
}

def _is_junk_file(name: str) -> bool:
    low = name.lower()
    if low in JUNK_FILE:
        return True
    if low.startswith("~$"):
        return True
    return Path(low).suffix in JUNK_EXT


def _skip_dir(name: str) -> bool:
    return name.lower() in JUNK_DIR or name.startswith(".")


def iter_lib_files(root: Path):
    if root.is_file():
        yield root
        return
    if not root.is_dir():
        return
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not _skip_dir(d)]
        for fn in filenames:
            yield Path(dirpath) / fn


def analyze(root: Path) -> dict:
    junk = []
    junk_bytes = 0
    compactable = 0
    compact_n = 0
    skip_n = 0
    skip_bytes = 0
    total = 0
    files = 0
    biggest = []
    for p in iter_lib_files(root):
        try:
            n = p.stat().st_size
        except OSError:
            continue
        files += 1
        total += n
        if _is_junk_file(p.name):
            junk.append({"path": str(p), "bytes": n})
            junk_bytes += n
            continue
        ext = p.suffix.lower()
        if n < 4096 or ext in SKIP_COMPACT_EXT:
            skip_n += 1
            skip_bytes += n
            continue
        compactable += n
        compact_n += 1
        if n >= 80_000_000:
            biggest.append({"path": str(p), "bytes": n, "ext": ext})
    biggest.sort(key=lambda x: -x["bytes"])
    return {
        "ok": True,
        "root": str(root),
        "files": files,
        "bytes": total,
        "junk": junk[:400],
        "junkCount": len(junk),
        "junkBytes": junk_bytes,
        "compactFiles": compact_n,
        "compactBytes": compactable,
        "skipFiles": skip_n,
        "skipBytes": skip_bytes,
        "biggest": biggest[:25],
        "note": "compact.exe is transparent: files stay in place and still run. Zip/7z of installers is skipped so setup.exe keeps working.",
    }


def purge_junk(root: Path) -> dict:
    removed = 0
    bytes_ = 0
    errors = []
    for p in list(iter_lib_files(root)):
        if not _is_junk_file(p.name):
            continue
        try:
            n = p.stat().st_size
            p.unlink()
            removed += 1
            bytes_ += n
        except OSError as exc:
            errors.append(str(p) + ": " + str(exc))
    return {"ok": True, "removed": removed, "bytes": bytes_, "errors": errors[:20]}


def compact_tree(root: Path, algo: str = "XPRESS8K", progress=None) -> dict:
    if os.name != "nt":
        return {"ok": False, "error": "compact.exe is Windows only (NTFS)"}
    if not root.exists():
        return {"ok": False, "error": "library missing"}
    algo = algo.upper() if algo.upper() in {"XPRESS4K", "XPRESS8K", "XPRESS16K", "LZX"} else "XPRESS8K"
    cmd = ["compact", "/c", "/i", "/f", "/exe:" + algo, "/s:" + str(root)]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=6 * 3600,
            creationflags=0x08000000,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "error": str(exc)}
    out = (proc.stdout or "")[-2000:]
    return {"ok": proc.returncode == 0, "code": proc.returncode, "algo": algo, "log": out}


def volume_fs(path: str) -> str:
    if os.name != "nt":
        return "unknown"
    try:
        import ctypes

        buf = ctypes.create_unicode_buffer(32)
        root = str(Path(path).anchor)
        if not root.endswith("\\"):
            root += "\\"
        ctypes.windll.kernel32.GetVolumeInformationW(root, None, 0, None, None, None, buf, 32)
        return buf.value or "unknown"
    except Exception:
        return "unknown"


def robocopy_tree(src: Path, dest: Path) -> dict:
    dest.mkdir(parents=True, exist_ok=True)
    cmd = [
        "robocopy",
        str(src),
        str(dest),
        "/E",
        "/COPY:DAT",
        "/DCOPY:DAT",
        "/R:1",
        "/W:1",
        "/MT:16",
        "/XO",
        "/NFL",
        "/NDL",
        "/NP",
        "/NJH",
        "/XF",
        "Thumbs.db",
        ".DS_Store",
        "desktop.ini",
        "/XD",
        "__MACOSX",
        "__pycache__",
        ".git",
        ".iconcache",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=24 * 3600, creationflags=0x08000000)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "error": str(exc)}
    code = proc.returncode
    return {"ok": code < 8, "code": code, "log": (proc.stdout or "")[-1500:]}
