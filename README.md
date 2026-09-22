# AW_FutaDepot

Portable Windows library for installers, games, tools, archives and scripts. One folder. Tk window. No browser.

**Current version: 0.1.46**

RU: Лаунчер-проводник. Кидаешь папки и exe в `_FutaMass`, SCAN, плитки по типу, инспектор справа, RUN / SILENT / OPEN FOLDER.

## Links

| | |
| --- | --- |
| Repo | https://github.com/2biteWolf/AW_FutaDepot |
| Releases | https://github.com/2biteWolf/AW_FutaDepot/releases |
| Update channel | https://raw.githubusercontent.com/2biteWolf/AW_FutaDepot/main/channel/version.json |
| Sync meta | https://raw.githubusercontent.com/2biteWolf/AW_FutaDepot/main/channel/depot-meta.json |

## Download

1. Latest zip from [Releases](https://github.com/2biteWolf/AW_FutaDepot/releases).
2. Unpack. Keep root entry points together (`ui.py`, `app.py`, `START.bat`, `icon.ico`).
3. `_FutaMass` stays next to the program. Copy `_FutaMass` and `icons-custom` if you already have a library.

Need **Python 3** with Tk. Pillow optional (custom tile icons).

```
START.bat
```

or

```
py -3 ui.py
```

Language follows Windows locale (RU / EN).

## Layout

```
AW_FutaDepot/
  ui.py / app.py        entry points (insert lib/ on sys.path)
  START.bat / AW_FutaDepot.exe / launcher.cs
  config.example.json   icon.ico  icon128.png
  README.md  INSTALL.txt  CHANGELOG.md  CHANGELOG.txt
  lib/                  bf_futa.py futa_db.py aw_update.py lib_opt.py win_cfg.py catalog.json
  docs/                 SPEC.md BF_FUTA.md CHAT_DUMP_PROMPT.md
  channel/              version.json depot-meta.json (SYNC)
  web/                  index.html
  win/                  go launcher sources
  _FutaMass/            drop root — one file or folder = one tile
  icons-custom/         pasted icons (created at runtime)
  reports/              depot-dump-*.json (created at runtime)
```

One default root: `_FutaMass`. Plus on the left adds extra group folders.

## How it works

| Action | What |
| --- | --- |
| HOME | All units from `_FutaMass`. Click a tile → inspector. |
| FILTER (left colors) | Games / Saves / Scripts / Installers / Portable / Archives / Docs. |
| SCAN | Depth 1. Each child of `_FutaMass` is one unit. |
| RUN AS-IS / SILENT | Launch / silent install when sniffed. |
| REPORT | `reports/depot-dump-latest.json` → send to dump chat. |
| IMPORT | Merge chat JSON into local `depot-meta.json`. |
| SYNC | Write report → push meta (+ dump ≤8MB) to GitHub `channel/` via `gh` → pull `metaUrl` and merge. Needs GitHub CLI. |
| UPDATE | SETTINGS. Reads `versionUrl`. Quiet auto-check off by default. |

Default `syncTarget` is `github`. Optional Drive push if `syncTarget` includes `drive` and `rclone` is installed.

## Kinds

| kind | color | |
| --- | --- | --- |
| game | blue `#3b82f6` | Unity / GM / steam_api / game.exe |
| save | orange `#f97316` | save folders, `.sav` `.sl2` |
| script | purple `#a855f7` | `.bat` `.cmd` `.ps1` |
| installer | lime `#99e550` | Inno / NSIS / MSI / setup.exe |
| portable | cyan `#22d3ee` | lone exe or zip with one exe |
| archive | gray | zip/7z/rar without clear payload |
| doc | white-ish | pdf/txt/md packs |

## License

Personal / internal use. Ship the zip from Releases; do not commit personal `config.json` or library contents.
