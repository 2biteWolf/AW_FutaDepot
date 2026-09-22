#!/usr/bin/env python3
"""Windows user-settings snapshot for AW_FutaDepot. HKCU + user files only."""

from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import subprocess
from pathlib import Path

SNAP_NAME = "win-snapshot"

REG_ITEMS = [
    ("explorer_hidden", "Explorer", "Show hidden files", r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "Hidden", {0: "no", 1: "yes", 2: "yes"}),
    ("explorer_superhidden", "Explorer", "Show OS files", r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "ShowSuperHidden", {0: "no", 1: "yes"}),
    ("hide_ext", "Explorer", "Hide file extensions", r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "HideFileExt", {0: "no", 1: "yes"}),
    ("show_checkboxes", "Explorer", "Item check boxes", r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "AutoCheckSelect", {0: "no", 1: "yes"}),
    ("launch_to", "Explorer", "Open File Explorer to", r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "LaunchTo", {1: "This PC", 2: "Quick access"}),
    ("taskbar_combine", "Taskbar", "Combine buttons", r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "TaskbarGlomLevel", {0: "always", 1: "when full", 2: "never"}),
    ("taskbar_small", "Taskbar", "Small taskbar buttons", r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "TaskbarSmallIcons", {0: "no", 1: "yes"}),
    ("apps_light", "Theme", "Apps color", r"HKCU\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize", "AppsUseLightTheme", {0: "dark", 1: "light"}),
    ("system_light", "Theme", "System color", r"HKCU\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize", "SystemUsesLightTheme", {0: "dark", 1: "light"}),
    ("transparency", "Theme", "Transparency", r"HKCU\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize", "EnableTransparency", {0: "off", 1: "on"}),
    ("accent_color", "Theme", "Accent color", r"HKCU\Software\Microsoft\Windows\DWM", "ColorizationColor", None),
    ("mouse_speed", "Mouse", "Pointer speed", r"HKCU\Control Panel\Mouse", "MouseSensitivity", None),
    ("keyboard_delay", "Keyboard", "Repeat delay", r"HKCU\Control Panel\Keyboard", "KeyboardDelay", {0: "short", 1: "medium", 2: "long", 3: "longest"}),
]


def snap_dir(app_dir: Path) -> Path:
    return app_dir / SNAP_NAME


def manifest_path(app_dir: Path) -> Path:
    return snap_dir(app_dir) / "manifest.json"


def load_manifest(app_dir: Path) -> dict:
    p = manifest_path(app_dir)
    if not p.is_file():
        return {"items": [], "at": None, "machine": None}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        data.setdefault("items", [])
        return data
    except (OSError, json.JSONDecodeError):
        return {"items": [], "at": None, "machine": None}


def _run(cmd: list[str], timeout: int = 40) -> subprocess.CompletedProcess:
    kw = {"capture_output": True, "text": True, "timeout": timeout}
    if os.name == "nt":
        kw["creationflags"] = 0x08000000
    return subprocess.run(cmd, **kw)


def _reg_query(key: str, value: str) -> str | None:
    try:
        proc = _run(["reg", "query", key, "/v", value], timeout=8)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    for line in (proc.stdout or "").splitlines():
        if value.lower() in line.lower() and "REG_" in line:
            parts = line.strip().rsplit(None, 1)
            return parts[-1] if parts else None
    return None


def _decode(raw: str | None, mapping: dict | None) -> str:
    if raw is None:
        return "—"
    if mapping:
        try:
            return mapping.get(int(raw, 0), raw)
        except ValueError:
            return mapping.get(raw, raw)
    if raw.lower() in {"0x0", "0"}:
        return "0"
    if raw.lower() in {"0x1", "1"}:
        return "1"
    return raw


def _copy_file(src: Path, dest: Path) -> bool:
    if not src.is_file():
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(src, dest)
        return True
    except OSError:
        return False


def _copy_tree(src: Path, dest: Path) -> int:
    if not src.is_dir():
        return 0
    n = 0
    dest.mkdir(parents=True, exist_ok=True)
    for item in src.rglob("*"):
        if not item.is_file():
            continue
        rel = item.relative_to(src)
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(item, target)
            n += 1
        except OSError:
            continue
    return n


def snapshot(app_dir: Path) -> dict:
    root = snap_dir(app_dir)
    if root.exists():
        shutil.rmtree(root, ignore_errors=True)
    files = root / "files"
    hive = root / "hive"
    files.mkdir(parents=True, exist_ok=True)
    hive.mkdir(parents=True, exist_ok=True)
    items = []
    win = os.name == "nt"

    user = os.environ.get("USERNAME") or os.environ.get("USER") or "user"
    domain = os.environ.get("USERDOMAIN") or ""
    items.append(
        {
            "id": "profile",
            "group": "Profile",
            "title": "User profile",
            "value": f"{domain}\\{user}" if domain else user,
            "kind": "text",
            "preview": None,
            "apply": None,
        }
    )

    if win:
        for iid, group, title, key, name, mapping in REG_ITEMS:
            raw = _reg_query(key, name)
            items.append(
                {
                    "id": iid,
                    "group": group,
                    "title": title,
                    "value": _decode(raw, mapping),
                    "raw": raw,
                    "kind": "choice",
                    "preview": None,
                    "apply": None if raw is None else ["reg", "add", key, "/v", name, "/t", "REG_DWORD" if (raw or "").lower().startswith("0x") or (raw or "").isdigit() else "REG_SZ", "/d", str(int(raw, 0) if raw.lower().startswith("0x") else raw) if raw and (raw.lower().startswith("0x") or raw.isdigit()) else (raw or ""), "/f"],
                }
            )
        for key, fname in (
            (r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "explorer_advanced.reg"),
            (r"HKCU\Software\Microsoft\Windows\CurrentVersion\Themes", "themes.reg"),
            (r"HKCU\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize", "personalize.reg"),
            (r"HKCU\Control Panel\Desktop", "desktop.reg"),
            (r"HKCU\Control Panel\Mouse", "mouse.reg"),
            (r"HKCU\AppEvents\Schemes", "sounds.reg"),
        ):
            dest = hive / fname
            try:
                _run(["reg", "export", key, str(dest), "/y"], timeout=15)
            except (OSError, subprocess.TimeoutExpired):
                pass

        wall = _reg_query(r"HKCU\Control Panel\Desktop", "WallPaper")
        if wall and wall not in {"", "(value not set)"}:
            src = Path(wall.strip())
            dest = files / "wallpaper" / src.name
            if _copy_file(src, dest):
                items.append(
                    {
                        "id": "wallpaper",
                        "group": "Theme",
                        "title": "Wallpaper",
                        "value": src.name,
                        "kind": "image",
                        "preview": str(dest.relative_to(root)),
                        "apply": ["_wallpaper", str(dest)],
                    }
                )

        pic_dirs = [
            Path(os.environ.get("APPDATA") or "") / "Microsoft/Windows/AccountPictures",
            Path(os.environ.get("ProgramData") or r"C:\ProgramData") / "Microsoft/User Account Pictures",
        ]
        copied_pic = None
        for d in pic_dirs:
            if not d.is_dir():
                continue
            for ext in ("*.png", "*.jpg", "*.bmp", "*.jpeg"):
                for pic in d.glob(ext):
                    dest = files / "avatar" / pic.name
                    if _copy_file(pic, dest):
                        copied_pic = dest
                        break
                if copied_pic:
                    break
            if copied_pic:
                break
        if copied_pic:
            items.append(
                {
                    "id": "avatar",
                    "group": "Profile",
                    "title": "Account picture",
                    "value": copied_pic.name,
                    "kind": "image",
                    "preview": str(copied_pic.relative_to(root)),
                    "apply": ["_copyback", str(copied_pic), str(pic_dirs[0] / copied_pic.name)],
                }
            )

        startup = Path(os.environ.get("APPDATA") or "") / "Microsoft/Windows/Start Menu/Programs/Startup"
        n = _copy_tree(startup, files / "startup")
        items.append(
            {
                "id": "startup",
                "group": "Explorer",
                "title": "Startup folder shortcuts",
                "value": f"{n} files",
                "kind": "file",
                "preview": None,
                "apply": ["_copytree", str(files / "startup"), str(startup)],
            }
        )

        pinned = Path(os.environ.get("APPDATA") or "") / "Microsoft/Internet Explorer/Quick Launch/User Pinned"
        n = _copy_tree(pinned, files / "pinned")
        items.append(
            {
                "id": "pinned",
                "group": "Taskbar",
                "title": "Pinned shortcuts",
                "value": f"{n} files",
                "kind": "file",
                "preview": None,
                "apply": ["_copytree", str(files / "pinned"), str(pinned)],
            }
        )

        try:
            proc = _run(["powercfg", "/GETACTIVESCHEME"], timeout=10)
            line = (proc.stdout or "").strip().replace("\n", " ")
            guid = ""
            name = line or "unknown"
            for part in line.split():
                if part.count("-") == 4 and len(part) >= 32:
                    guid = part.strip("()")
            pow_path = files / "power" / "scheme.pow"
            pow_path.parent.mkdir(parents=True, exist_ok=True)
            if guid:
                _run(["powercfg", "-export", str(pow_path), guid], timeout=15)
            items.append(
                {
                    "id": "power",
                    "group": "Power",
                    "title": "Active power plan",
                    "value": name[:80],
                    "kind": "text",
                    "preview": None,
                    "apply": ["_power", str(pow_path)] if pow_path.exists() else None,
                }
            )
        except (OSError, subprocess.TimeoutExpired):
            items.append({"id": "power", "group": "Power", "title": "Active power plan", "value": "unavailable", "kind": "text", "preview": None, "apply": None})

        wlan_dir = files / "wlan"
        wlan_dir.mkdir(parents=True, exist_ok=True)
        try:
            _run(["netsh", "wlan", "export", "profile", f"folder={wlan_dir}", "key=clear"], timeout=20)
        except (OSError, subprocess.TimeoutExpired):
            pass
        xmls = list(wlan_dir.glob("*.xml"))
        items.append(
            {
                "id": "wlan",
                "group": "Network",
                "title": "Wi-Fi profiles",
                "value": f"{len(xmls)} profiles",
                "kind": "file",
                "preview": None,
                "apply": ["_wlan", str(wlan_dir)] if xmls else None,
            }
        )
    else:
        items.append({"id": "note", "group": "System", "title": "Snapshot", "value": "Windows only — run on the PC to capture", "kind": "text", "preview": None, "apply": None})

    data = {
        "at": dt.datetime.now().isoformat(timespec="seconds"),
        "machine": os.environ.get("COMPUTERNAME") or os.uname().nodename if hasattr(os, "uname") else "",
        "user": os.environ.get("USERNAME") or os.environ.get("USER"),
        "items": items,
    }
    manifest_path(app_dir).write_text(json.dumps(data, indent=2), encoding="utf-8")
    return {"ok": True, "count": len(items), "path": str(root), "at": data["at"]}


def apply_items(app_dir: Path, ids: list[str]) -> dict:
    man = load_manifest(app_dir)
    root = snap_dir(app_dir)
    wanted = set(ids)
    done = []
    errors = []
    for item in man.get("items") or []:
        if item.get("id") not in wanted:
            continue
        cmd = item.get("apply")
        if not cmd:
            errors.append(item["id"] + ": nothing to apply")
            continue
        try:
            if cmd[0] == "_copytree":
                _copy_tree(Path(cmd[1]), Path(cmd[2]))
            elif cmd[0] == "_copyback":
                _copy_file(Path(cmd[1]), Path(cmd[2]))
            elif cmd[0] == "_wallpaper":
                img = Path(cmd[1])
                if os.name == "nt" and img.is_file():
                    _run(["reg", "add", r"HKCU\Control Panel\Desktop", "/v", "WallPaper", "/t", "REG_SZ", "/d", str(img), "/f"])
                    _run(["rundll32.exe", "user32.dll,UpdatePerUserSystemParameters"])
            elif cmd[0] == "_power":
                if Path(cmd[1]).is_file():
                    _run(["powercfg", "-import", cmd[1]])
            elif cmd[0] == "_wlan":
                folder = Path(cmd[1])
                for xml in folder.glob("*.xml"):
                    _run(["netsh", "wlan", "add", "profile", f"filename={xml}", "user=current"])
            else:
                _run([str(c) for c in cmd], timeout=20)
            done.append(item["id"])
        except (OSError, subprocess.TimeoutExpired) as exc:
            errors.append(item["id"] + ": " + str(exc))
    return {"ok": not errors, "applied": done, "errors": errors, "root": str(root)}
