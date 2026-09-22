#!/usr/bin/env python3
"""AW_Update drop-in. Own channel = your version.json URL in config key versionUrl."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

KEEP_DIRS = ("library", "inbox", "icons-custom", "reports", "_incoming")
KEEP_FILES = ("config.json", "depot-meta.json", "search-history.json")


def parse_ver(text: str) -> tuple[int, ...]:
    parts = []
    for bit in (text or "0").split("."):
        try:
            parts.append(int(bit))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def fetch_url(url: str) -> dict:
    url = (url or "").strip()
    if not url:
        return {"ok": False, "error": "empty url"}
    req = urllib.request.Request(url, headers={"User-Agent": "AW_Update"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return {"ok": True, "text": resp.read().decode("utf-8", errors="replace")}
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {"ok": False, "error": str(exc)}


def fetch_bytes(url: str, progress=None) -> dict:
    url = (url or "").strip()
    if not url:
        return {"ok": False, "error": "empty url"}
    req = urllib.request.Request(url, headers={"User-Agent": "AW_Update"})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
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
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {"ok": False, "error": str(exc)}


def check_update(version_url: str, current: str) -> dict:
    got = fetch_url(version_url)
    if not got.get("ok"):
        return {"ok": False, "error": got.get("error"), "current": current}
    try:
        data = json.loads(got["text"])
    except json.JSONDecodeError:
        return {"ok": False, "error": "version file is not JSON", "current": current}
    remote = str(data.get("version") or "")
    return {
        "ok": True,
        "current": current,
        "remote": remote,
        "newer": parse_ver(remote) > parse_ver(current) if remote else False,
        "zip": data.get("zip") or "",
        "notes": data.get("notes") or "",
    }


def apply_update(app_dir: Path, zip_url: str, launch_name: str = "", progress=None) -> dict:
    app_dir = Path(app_dir)
    got = fetch_bytes(zip_url, progress=progress)
    if not got.get("ok"):
        return got
    raw = got["data"]
    if raw[:2] != b"PK":
        return {"ok": False, "error": "download is not a zip"}
    zpath = app_dir / "_update.zip"
    zpath.write_bytes(raw)
    incoming = app_dir / "_incoming"
    if incoming.exists():
        shutil.rmtree(incoming)
    incoming.mkdir()
    with zipfile.ZipFile(zpath) as zf:
        zf.extractall(incoming)
    kids = [p for p in incoming.iterdir() if p.is_dir()]
    src = kids[0] if len(kids) == 1 else incoming
    exe = launch_name or next((p.name for p in src.glob("*.exe")), "")
    if os.name == "nt":
        bat = app_dir / "_apply_update.bat"
        bat.write_text(
            "\r\n".join(
                [
                    "@echo off",
                    "cd /d \"%~dp0\"",
                    "timeout /t 2 /nobreak >nul",
                    f"robocopy \"{src}\" \".\" /E /NFL /NDL /NJH /NJS /XD {' '.join(KEEP_DIRS)} /XF {' '.join(KEEP_FILES)} {exe}",
                    f"if exist \"{src}\\{exe}\" copy /y \"{src}\\{exe}\" \"{exe}\" >nul" if exe else "rem",
                    "rmdir /s /q \"_incoming\"",
                    f"start \"\" \"{exe}\"" if exe else "rem",
                    "del \"%~f0\"",
                ]
            ),
            encoding="utf-8",
        )
        subprocess.Popen(["cmd", "/c", str(bat)], cwd=str(app_dir))
        return {"ok": True, "restart": True}
    for item in src.iterdir():
        if item.name in KEEP_DIRS or item.name in KEEP_FILES:
            continue
        dest = app_dir / item.name
        if item.is_dir():
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)
    return {"ok": True, "restart": False}
