# AW_FutaDepot

Portable Windows library for installers, games, tools, archives and scripts. One folder. Tk window. No browser.

**Current version: 0.1.45**

RU: Ð›Ð°ÑƒÐ½Ñ‡ÐµÑ€-Ð¿Ñ€Ð¾Ð²Ð¾Ð´Ð½Ð¸Ðº. ÐšÐ¸Ð´Ð°ÐµÑˆÑŒ Ð¿Ð°Ð¿ÐºÐ¸ Ð¸ exe Ð² `_FutaMass`, SCAN, Ð¿Ð»Ð¸Ñ‚ÐºÐ¸ Ð¿Ð¾ Ñ‚Ð¸Ð¿Ñƒ, Ð¸Ð½ÑÐ¿ÐµÐºÑ‚Ð¾Ñ€ ÑÐ¿Ñ€Ð°Ð²Ð°, RUN / SILENT / OPEN FOLDER.

## Links

| | |
| --- | --- |
| Repo | https://github.com/2biteWolf/AW_FutaDepot |
| Releases | https://github.com/2biteWolf/AW_FutaDepot/releases |
| Update channel | https://raw.githubusercontent.com/2biteWolf/AW_FutaDepot/main/channel/version.json |

## Download

1. Latest zip from [Releases](https://github.com/2biteWolf/AW_FutaDepot/releases).
2. Unpack. Keep `ui.py`, `app.py`, `START.bat`, `catalog.json`, `icon.ico` together.
3. `_FutaMass` stays next to the program. Do not merge old zip piles into a new one blindly â€” copy `_FutaMass` and `icons-custom` if you already have a library.

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
  ui.py                 window
  app.py                scan / run / dump / update / winget
  catalog.json          NET INSTALL list
  START.bat
  CHAT_DUMP_PROMPT.md   prompt for the dump chat
  channel/version.json  auto-update pointer
  _FutaMass/            drop root â€” one file or folder = one tile
  icons-custom/         pasted icons
  reports/              depot-dump-*.json
```

One default root: `_FutaMass`. Plus on the left adds extra group folders. No empty default Games/Apps/Tools.

## How it works

| Action | What |
| --- | --- |
| HOME | All units from `_FutaMass`. Click a tile â†’ inspector. |
| FILTER (left colors) | Games / Saves / Scripts / Installers / Portable / Archives / Docs. Filters the list. Does not move files. |
| AUTOSORT tab | Same units grouped by color. Disk is unchanged unless you confirm move. |
| SCAN | Depth 1. Each child of `_FutaMass` is one unit. Zip: peek namelist; one inner exe = portable, setup.exe = installer. |
| RUN AS-IS | Launch the file. Zip with inner exe â†’ unpack then run. |
| SILENT | On only after Inno / NSIS / MSI sniff. |
| OPEN FOLDER | Explorer on that path. |
| NET INSTALL | winget from `catalog.json`. |
| REPORT | `reports/depot-dump-latest.json` â†’ send to dump chat. |
| IMPORT / SYNC | Merge metadata (`sourceUrl`, `wingetId`, `updateUrl`). |
| UPDATE | SETTINGS button. Reads `versionUrl`. Does not freeze the window. Quiet auto-check is off by default. |
| ICONS | Ctrl+click icon then Ctrl+V, 1:1 crop. |
| ? | Help + COPY PROMPT. |

## Kinds

| kind | color | |
| --- | --- | --- |
| game | blue `#3b82f6` | Unity / GM / steam_api / game.exe |
| save | orange `#f97316` | save folders, `.sav` `.sl2` |
| script | purple `#a855f7` | `.bat` `.cmd` `.ps1` |
| installer | lime `#99e550` | Inno / NSIS / MSI / setup.exe |
| portable | cyan `#22d3ee` | lone exe or zip with one exe |
| archive | yellow `#eab308` | zip / 7z / rar / iso |
| doc | gray `#94a3b8` | root `.txt` `.md` |
| unknown | black | needs REPORT |

## Dump chat

1. COPY PROMPT from Help.
2. New chat first line: `Ð¿Ñ€Ð¸Ð½ÑÑ‚Ð¾, Ð¶Ð´Ñƒ Ð´Ð°Ð½Ð½Ñ‹Ðµ`
3. Send `depot-dump-latest.json` only.
4. Chat returns import JSON. Then IMPORT.

Prompt file: [`CHAT_DUMP_PROMPT.md`](CHAT_DUMP_PROMPT.md) (updated 0.1.26+).

## Update channel

`config.json` â†’ `versionUrl`:

`https://raw.githubusercontent.com/2biteWolf/AW_FutaDepot/main/channel/version.json`

```json
{
  "version": "0.1.28",
  "zip": "https://github.com/2biteWolf/AW_FutaDepot/releases/download/v0.1.28/AW_FutaDepot_0.1.28.zip",
  "notes": "fast explorer, no browser server"
}
```

Until that file and the Release zip exist on this repo, UPDATE cannot pull. Use the zip from Releases or the public Drive folder.

## Versions

| ver | |
| --- | --- |
| 0.1.30 | SORT moves the folder unit, not the inner setup. |
| 0.1.30 | COPY ALL copies program + full `_FutaMass` (GB size), not just the launcher. |
| 0.1.29 | SCAN inside x86/x64/bin. Nested extras stay in the pack. |
| 0.1.28 | Drop HTTP server. No PowerShell on paint. No resize rebuild. SCAN = disk only. |
| 0.1.27 | Update check off UI thread. 8s timeout. Quiet 404. |
| 0.1.26 | Click from HOME opens inspector. Split panes. Zip peek. |
| 0.1.25 | Depth-1 units, restore buckets, hidden PowerShell. |
| 0.1.19â€“0.1.24 | Icons, report dump, INSTALLED, PACK zip, `_FutaMass`. |

See [CHANGELOG.md](CHANGELOG.md).

## Rules

- Do not change working logic without an explicit order.
- No stub implementations.
- Silent only after a real engine sniff.
- No crack / activation / disable-defender how-tos.
- Code: English. Product talk: Russian.

## License

Private AW workspace. Not a store listing.

