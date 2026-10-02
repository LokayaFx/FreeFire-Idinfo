# Lokaya_API — Free Fire Player Lookup

[![Version](https://img.shields.io/badge/version-2.2.0-blue.svg)](API_DOCS.md)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/flask-3.x-lightgrey.svg)](https://flask.palletsprojects.com/)

A Flask-based Free Fire player lookup API + web app. Enter any player UID to get
live profile stats, ranks, guild info and official profile media (banner/avatar
rendered server-side from Garena CDN assets). The backend is CORS-enabled, so it
can also serve as the API for a separate multi-tool frontend.

Full API reference: **[API_DOCS.md](API_DOCS.md)**

---

## Features

- **Live player lookup** — nickname, level, EXP, likes, region, ranks, guild, pet, loadout and more.
- **Official profile media** — banner/avatar WebP images composited server-side from official Garena CDN textures, with automatic local fallback.
- **Glassmorphism web UI** — clean white frosted-glass interface with copyable raw JSON output.
- **Multi-region support** — `BD IND SG VN TH BR US NA SAC ID RU TW ME PK CIS EUROPE` (explicit `region` optional; auto-detects when omitted).
- **Backend-ready** — CORS enabled; `/player-info` and media endpoints can be called directly from any frontend.

---

## Quickstart

**Requirements:** Python `3.10`+ on Windows, Linux or macOS.

```bash
# 1. Create a virtual environment
python -m venv .venv
```

**Windows (PowerShell):**

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m flask --app app run --host 127.0.0.1 --port 5055 --no-debugger --no-reload
```

**Linux / macOS:**

```bash
source .venv/bin/activate
pip install -r requirements.txt
python -m flask --app app run --host 127.0.0.1 --port 5055 --no-debugger --no-reload
```

Shortcut on Windows:

```powershell
pwsh -NoProfile -File tools/start-local.ps1
```

Open `http://127.0.0.1:5055` and search any player UID.

---

## API (summary)

```http
GET /player-info?uid={uid}&region={region}
GET /api/banner/banner_{uid}.webp?region={region}
GET /api/avatar/avatar_{uid}.webp?region={region}
GET /refresh          # refresh all regional gateway tokens
```

```js
const data = await (await fetch('http://127.0.0.1:5055/player-info?uid=4422076728')).json();
console.log(data.basicInfo.nickname, data.mediaInfo.bannerUrl);
```

Parameters, response schema, error codes and media headers are documented in
**[API_DOCS.md](API_DOCS.md)**.

---

## Project structure

```text
app.py             # Flask app, routes, token management
credentials.py     # service-account resolution (accounts.txt + env overrides)
protocol.py        # OB protocol profiles, headers, login decoding
official_media.py  # CDN media rendering (ASTC -> WebP)
proto/             # protobuf message definitions
templates/         # web UI (glassmorphism)
static/            # web UI styles + frontend JS
fonts/             # nickname rendering fonts (required, do not delete)
accounts.txt       # active service accounts (UID PASSWORD REGION rows)
tools/             # local runner + live diagnostics
vercel.json        # Vercel deployment config
API_DOCS.md        # full API reference
```

---

## Configuration

Service accounts live in `accounts.txt` (one `UID PASSWORD REGION` row per scope).
Optional environment overrides: `FREEFIRE_<SCOPE>_UID` + `FREEFIRE_<SCOPE>_PASSWORD`
where `SCOPE` is a region (`BR`, `VN`, …) or a group (`AMERICAS`, `GLOBAL`).
Restart the server after changing credentials so cached tokens are cleared.
See [API_DOCS.md](API_DOCS.md) for the full account guide.

---

## Developer

- **LokayaGfx** — *Lokaya_API*

---

## Disclaimer

Unofficial community project. Not affiliated with or endorsed by Garena.
Use in accordance with Garena / Free Fire terms of service and local privacy regulations.
