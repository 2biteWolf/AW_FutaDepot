# Changelog

## 0.1.46 — 2026-09-22

- Repo layout: root keeps entry points; helpers in `lib/`, docs in `docs/`, `web/index.html`.
- SYNC pushes local `depot-meta.json` (+ dump ≤8MB) to GitHub `channel/` via `gh api`, then pulls `metaUrl`.
- Default meta/dump URLs point at raw GitHub channel files. Missing `gh` → UI askyesno winget install.
- Optional Drive push when `syncTarget` includes drive and `rclone` exists.


## 0.1.45 — 2026-09-22

- Apply icons from `_FutaMass/.futa-db` on REFRESH and on launch. Scan pipeline unchanged.



## 0.1.44 — 2026-09-22

- SCAN is 5 separate steps: discover → import overlay → load .futa-db → unblock → icons one-by-one → persist. No mega-chain.
- Icons extracted per file, never one giant PowerShell. Boot no longer harvests in parallel with reload.



## 0.1.43 — 2026-09-22

- Icons: Explorer shell icon (SHGetFileInfo) on SCAN. Old PowerShell -Command was too long and silently ate every icon.
- Portable DB in `_FutaMass/.futa-db/` (index.json + icons). Key = pack name + payload, not disk path. Notes, import meta, icons travel with the library.



## 0.1.42 — 2026-09-22

- Inspector locked 50/50. Long paths clipped; hover = acid-green full text. Bigger left labels. No gap before the comment pane.



## 0.1.41 — 2026-09-22

- Inspector split 50/50. Left: compact properties (name, ext, type, size, path, group, verified, Source YES/NO). Extra in DETAILS ▾.
- Right: square comment, purple frame, acid-green pixel text. Enter saves.



## 0.1.40 — 2026-09-22

- No default library path. On start, if unset/missing: SELECT or NEW PACK.
- SELECT: any folder, any disk. NEW PACK: creates `_FutaMass` there and opens it.
- Both buttons on the nav bar. USB/other-volume paths stay absolute (no reset to app folder).



## 0.1.39 — 2026-09-22

- Launch no longer uses ShellExecute (`os.startfile`). That was the empty Windows red file dialog (association / Zone.Identifier ADS).
- Drop `file:Zone.Identifier` on SCAN + RUN. Error text now has the Win32 code (32 = in use, 5 = blocked, 1155 = no association).



## 0.1.38 — 2026-09-22

- B F Futa: drop-in debug overlay. Dummy checkbox in SETTINGS. 3× туда-сюда in 5s opens lime log window. One click closes.
- Click a log line → square 1/6-screen popup, copy + OK. Alpha slider on the overlay.



## 0.1.37 — 2026-09-22

- SCAN extracts Windows icons from exe/rar/folder payload (batch). Tiles refresh when done.
- AUTOSORT: color group buttons + 2-column list + inspector. No empty 90% strip.
- Inspector scrolls; OPEN FOLDER / RUN / COPY TO / DELETE stay at the bottom.
- Click name → rename file and its folder (Enter). DELETE asks YES.
- Settings/Net Install compact for ultrawide. COPY_TO.bat + COPY TO in UI (robocopy).
- Portable: relative `_FutaMass`, START.bat builds AW_FutaDepot.exe via csc, finds Python off PATH.



## 0.1.36 — 2026-09-21

- Tiles reflow live when the window resizes. No more one-column start / empty half after stretch / Refresh.
- Inspector sash no longer live-resizes the grid (no lag). Dark scrollbar.



## 0.1.35 — 2026-09-20

- COMPRESS SIZE: junk sweep + transparent NTFS `compact /exe:XPRESS8K`. Installers/zips not re-packed so they still run.
- COPY ALL uses robocopy (16 threads, resume, skip already copied). FAT32 4 GB warning.



## 0.1.34 — 2026-09-19

- WIN CFG tab: snapshot Explorer/theme/power/pins/wallpaper/avatar/Wi-Fi. Checkboxes + image hover. Apply selected.
- COPY ALL also takes `win-snapshot` and verifies file counts so the library is not silently truncated.



## 0.1.33 — 2026-09-19

- Dump sends localKind / localGroup as a hypothesis. Chat must verify and override.
- Prompt 0.1.33 — recopy.



## 0.1.32 — 2026-09-19

- REPORT includes a per-unit folder tree (path, size, flags). Crack/keygen/nfo/setup marked.
- Inspector shows the tree. Dump chat prompt 0.1.32 — recopy.


## 0.1.31 — 2026-09-19

- IMPORT matches by file path, folder, id, filename aliases. JSON from chat can be in ``` fences.
- Inspector: RUN AS-IS cyan, SILENT lime, OPEN SOURCE blue, GET UPDATE orange.
- RUN uses Windows startfile. Enabled if a file exists, not only after PE sniff.
- Meta silentHint turns Silent on. Source/update/winget buttons after a real import.
- Dump prompt 0.1.31 — recopy from Help.


## 0.1.30 — 2026-09-19

- COPY ALL HERE copies the program **and the whole `_FutaMass` library** (and extra roots), not just launcher files.
- Size dialog shows program / library / TOTAL in GB. Counts the real tree.
- Copy runs in a background thread with a progress bar. Will not format or wipe the disk.
- Blocks if free space is less than library size + 200 MB.


## 0.1.30 — 2026-09-19

- SORT / move: unit = top-level folder. Inner setup/exe stays inside. No more empty husks in Unknown (DuckStation, Knock-knock, Loop Hero).
- IMPORT meta also matches folder path, not only payload path.

## 0.1.29 — 2026-09-19

- SCAN looks inside x86 / x64 / bin (depth 3). DisplayFusion-style packs are portable, not Unknown.
- Nested extras stay in the pack. Launch file is the app exe, not a nested extra.
- Inspector shows `run` relative path (e.g. `x86/App.exe`).


## 0.1.28 — 2026-09-19

- Removed leftover HTTP/browser server
- SCAN is depth-1 disk only, no PowerShell on paint, no restore on every scan
- No window rebuild on resize, no auto-update on start
- Click from HOME still opens inspector

## 0.1.27 — 2026-09-19

- Update check off UI thread, 8s timeout
- Quiet 404 on missing channel

## 0.1.26 — 2026-09-19

- Inspector from HOME and filters
- Split panes with minsize
- Zip peek: one inner exe = portable, setup = installer


## 0.1.18 — 2026-09-19

- VERSION 0.1.18
- Default update channel points at GitHub `channel/version.json`
- GitHub Actions pack + release (`deploy.yml`)

## 0.1.17 — 2026-09-19

- Library root `_FutaMass`
- Dump / meta / Drive URLs kept in config defaults

## 0.1.16 — 2026-09-19

- Inbox + mass folder scan path cleanup

## 0.1.15 — 2026-09-19

- Import / report latest copies under `reports/`

## 0.1.14 — 2026-09-19

- Custom icon key by unit hash

## 0.1.13 — 2026-09-19

- Keep-dirs on update: library, inbox, icons-custom, reports

## 0.1.12 — 2026-09-19

- `aw_update.py` drop-in channel module

## 0.1.11 — 2026-09-19

- Quiet auto-update checkbox default ON
- Progress bar, no confirm dialog

## 0.1.10 — 2026-09-19

- Auto-update from version.json on start and SETTINGS → UPDATE
- Keeps library/inbox/icons/config/meta

## 0.1.9 — 2026-09-19

- Google Drive folder AW_FutaDepot_sync
- SYNC pulls depot-meta.json by URL, writes local dump

## 0.1.8 — 2026-09-19

- Stop Configure flicker/grow loop
- Fixed 200px square tiles, no stretch on fullscreen

## 0.1.7 — 2026-09-19

- Custom icons: select icon frame, Ctrl+V, 1:1 crop editor
- Saved to icons-custom/, survives scan

## 0.1.6 — 2026-09-19

- REPORT writes reports/depot-dump-*.json + *.md + latest copies
- Search history persisted
- inbox/ drop folder scanned as INBOX
- IMPORT merges dump-chat JSON into depot-meta.json
- CHAT_DUMP_PROMPT.md for the enrichment chat

## 0.1.5 — 2026-09-16

- Taskbar AppUserModelID + window icon
- Equal home/store tiles, 6-16 per page, PREV/NEXT
- Full-row category hit target, hover/press accents
- Tooltips with size/source
- Drive copy confirm: size, free space, system/boot/kind, no format
- 4K scale via DPI

## 0.1.4 — 2026-09-16

- Standalone Tk window. No Edge, no Chrome, no 127.0.0.1
- Exe launches ui.py directly

## 0.1.3 — 2026-09-16

- Persistent BACK / FORWARD / HOME / REFRESH on every screen
- History stack across tabs and categories
- Back first closes the unit panel

## 0.1.2 — 2026-09-16

- SETTINGS: library root, list of drives, copy pack onto USB/second disk
- Autostart shortcut in Windows Startup
- TOOLBOX: proxy for net install, open Defender / Activation / Network / Update / Startup
- GHOST tile reserved for Ghost Mode Toolbox modules

## 0.1.1 — 2026-09-16

- AW_FutaDepot.exe app window, HOME, icons, catalog, delete/add file

## 0.1.0 — 2026-09-16

First running build.
