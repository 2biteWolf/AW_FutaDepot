# AW_FutaDepot

Windows library launcher for installer packs. Tk window. No browser UI.

**Current: 0.1.19**

Public source and releases live here. Project notes, Drive packs and the working zip for the owner live on Notion — that page is private.

- GitHub: https://github.com/2biteWolf/AW_FutaDepot
- Latest zip (after Actions): https://github.com/2biteWolf/AW_FutaDepot/releases/latest
- Update channel: [`channel/version.json`](https://raw.githubusercontent.com/2biteWolf/AW_FutaDepot/main/channel/version.json)
- Notion (owner): [AW_FutaDepot.app](https://app.notion.com/p/3dd34221c11781d59278c0e9bfed0216)
- Hub: [Grok Project Space](https://app.notion.com/p/3cc34221c11780bbb0bad73405a44f1d)
- Drive sync folder (owner): [AW_FutaDepot_sync](https://drive.google.com/drive/folders/1Lqwt0iIrV3oDsrXR66lvNWqRJtAneoy_)

EN: Local folder library for games, apps, tools and drivers. Scan installers (Inno / NSIS / MSI / portable), run as-is or silent when the engine is known, pull winget packages, dump the catalog to JSON for a chat enricher, import metadata back.

RU: Локальная библиотека установщиков. Скан движка, запуск как есть или тихо, Net Install через winget, REPORT/IMPORT дампа, автообновление с GitHub Releases.

## Download

1. Open [Releases](https://github.com/2biteWolf/AW_FutaDepot/releases/latest).
2. Take `AW_FutaDepot_0.1.19.zip` (version matches `VERSION` in `app.py`).
3. Unpack the folder. Keep the folder together — config, library and icons travel with it.

Owner copy also sits on the Notion DOWNLOAD block. Do not treat old zip piles as current.

## Run

Need **Python 3 + Tcl/Tk**. Pillow is used for custom icons.

```
START.bat
```

or

```
py -3 ui.py
```

`AW_FutaDepot.exe` is a thin Go stub that finds Python and starts `ui.py`. It is not in git (see `.gitignore`). Build it on Windows from `win/main.go` if you want the stub.

Language follows Windows. Toggle sits in the header.

## Layout

```
AW_FutaDepot/
  ui.py              window
  app.py             scan, install, dump, update, winget
  aw_update.py       channel check + zip apply
  catalog.json       winget Net Install list
  START.bat
  channel/version.json
  library/           optional extra roots (Games, Apps, Tools, Drivers)
  _FutaMass/         default library root (inbox + packs)
  inbox/             drop folder (also scanned)
  icons-custom/      pasted tile icons, survives scan
  reports/           depot-dump-*.json + .md
```

Categories = folders at the library root + ADD FOLDER. No shared dump pile. Each category has its own install destination. Silent stays locked until that path is set. Paths must not use junk characters; do not put spaces in the target.

## How it works

| Action | What happens |
| --- | --- |
| SCAN | Walks `_FutaMass`. Detects installer / portable / game / save / script / archive. Marks `hasSaves`. |
| RUN | Always launches the file as it lies. Game launchers are not rewritten. |
| SILENT | On only when the scan knows the engine (Inno `/VERYSILENT /NORESTART /DIR=`, NSIS `/S /D=`, MSI `msiexec /qn`). Else the button stays off. |
| NET INSTALL | winget catalog from `catalog.json`. Click = install command. Queue error = skip, continue. |
| PATHS | One destination per category. |
| REPORT | Writes `reports/depot-dump-*.json` + markdown + latest copies. |
| IMPORT | Merges chat JSON into `depot-meta.json`. Schema in `CHAT_DUMP_PROMPT.md`. |
| SYNC | Pulls `depot-meta.json` from the configured Drive URL. |
| UPDATE | Reads `versionUrl` (`channel/version.json` on this repo). Downloads the release zip. Keeps `library`, `inbox`, `icons-custom`, `reports`, `config.json`, `depot-meta.json`, `search-history.json`. Quiet checkbox default ON. |
| TOOLBOX | Proxy for net install, shortcuts to Defender / Network / Update / Startup. |
| ICONS | Select tile, Ctrl+V, 1:1 crop. Saved under `icons-custom/`. |

Optional `depot.json` next to a payload:

```json
{
  "name": "7-Zip",
  "kind": "installer",
  "file": "7z2408-x64.exe",
  "engine": "innosetup",
  "silentFlags": ["/VERYSILENT", "/NORESTART", "/DIR={target}"]
}
```

## Kinds

| kind | color | what |
| --- | --- | --- |
| installer | lime | Inno/NSIS/MSI |
| portable | olive | lone exe |
| game | blue | Unity/GM/Steam API/game.exe |
| save | orange | save/userdata + .sav .sl2 |
| script | purple | bat/cmd |
| archive | brown | zip/7z/rar/iso |
| empty/unknown | black | scan or REPORT |

## Dump chat

Copy `CHAT_DUMP_PROMPT.md` into a new chat. First reply must be `принято, жду данные`. Drop `depot-dump-*.json`. Chat returns import JSON only — metadata, no library rewrite.

## Update channel

`config.json` key `versionUrl` defaults to:

`https://raw.githubusercontent.com/2biteWolf/AW_FutaDepot/main/channel/version.json`

```json
{
  "version": "0.1.18",
  "zip": "https://github.com/2biteWolf/AW_FutaDepot/releases/download/v0.1.18/AW_FutaDepot_0.1.19.zip",
  "notes": "github actions"
}
```

Push to `main` or tag `v*` runs `.github/workflows/deploy.yml`: packs the tree, publishes the GitHub Release, writes `channel/version.json`.

## Versions

See [CHANGELOG.md](CHANGELOG.md). Patch `+0.0.1` on every change. Latest source version is **0.1.19**.

Working public artifacts are the GitHub Release zips produced by Actions. Historical local zips in the project folder are not the channel.

## Rules

- Do not change working logic without an explicit order.
- No stub implementations.
- Silent only after a real engine sniff.
- No crack / activation / disable-defender how-tos in dumps or docs.
- Code and comments: English. Product talk: Russian.

## License

Private use for the AW workspace. Not a store listing.
