# Lokaya_API - Documentation

Single consolidated guide for setup, accounts, API usage and troubleshooting.
(Consolidated from the previous `docs/` + changelog files.)

## 1. Setup

```bash
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m flask --app app run --host 127.0.0.1 --port 5055 --no-debugger --no-reload
```

Open `http://127.0.0.1:5055`.

Windows shortcut:

```powershell
pwsh -NoProfile -File tools/start-local.ps1
```

Tests (optional, needs dev deps):

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

## 2. Accounts (`accounts.txt`)

- Active credentials live in `accounts.txt`, one per line:
  `UID PASSWORD REGION` (3 columns, unique scope).
- Supported regions: `BD IND SG VN TH BR US NA SAC ID RU TW ME PK CIS EUROPE`.
- `EU` is accepted as an alias for `EUROPE`.
- Empty lines and `#` comment lines are ignored.
- Invalid / duplicate scopes fail with `CREDENTIAL_CONFIG_ERROR` (no secret is exposed).
- The old `accounts-legacy.txt` inventory (unscoped, unverified) is never loaded by the app.

Environment overrides (optional, never mixed with defaults):

- `FREEFIRE_<SCOPE>_UID` + `FREEFIRE_<SCOPE>_PASSWORD`
- Scope can be a region (`BR`, `VN`, ...) or a group (`AMERICAS`, `GLOBAL`).
- `AMERICAS` = BR US NA SAC EUROPE, `GLOBAL` = BD SG ME PK CIS RU.
- Region-specific rows fall back to `AMERICAS` / `GLOBAL` / `BR` where applicable.

## 3. API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/` | Web UI (Lokaya_API Player Inspector) |
| GET | `/player-info?uid=<UID>&region=<REGION>` | Player JSON (`region` optional, auto-detects) |
| GET | `/api/banner/banner_<UID>.webp?region=<REGION>` | Official banner WebP |
| GET | `/api/avatar/avatar_<UID>.webp?region=<REGION>` | Official avatar WebP |
| GET/POST | `/refresh` | Refresh all regional tokens |

CORS is enabled, so a separate multi-tool frontend can call these directly:

```js
fetch('http://127.0.0.1:5055/player-info?uid=4422076728')
  .then(r => r.json())
```

Common error codes: `PLAYER_NOT_FOUND`, `LOOKUP_INCOMPLETE`,
`GUEST_AUTH_FAILED`, `CREDENTIAL_CONFIG_ERROR`, `UPSTREAM_HTTP_ERROR`,
`UPSTREAM_CONNECTION_ERROR`, `UNRECOGNIZED_LOGIN_RESPONSE`.

## 4. Media

- Banner/avatar are rendered server-side from official Garena CDN ASTC textures
  (`bannerId` / `headPic`), with local fallback when CDN is unavailable.
- Response headers: `X-Free-Fire-Media-Source`, `X-Free-Fire-Official-Banner`,
  `X-Free-Fire-Official-Avatar`.
- Bundled `fonts/` (NotoSans family) are required for nickname rendering.
  Do not delete `fonts/`.

## 5. Troubleshooting (OB)

- Protocol default is OB55. Token warmup runs at startup; tokens refresh every ~7h.
- If login returns a tokenless / unrecognized reply: `UNRECOGNIZED_LOGIN_RESPONSE`
  (check account + OB protocol, do not blind-retry).
- If some gateways are down: `LOOKUP_INCOMPLETE` (retry later or specify region).
- If player works but media fails: check CDN/ASTC/fonts via media headers.
- Manual live diagnostics (optional):
  `python tools/diagnose.py --regions BD --self-lookup`
  `python tools/diagnose.py --regions IND BR VN ID TH TW BD --self-lookup`

## 6. Version history (summary)

- v2.2.0 - OB55 default, 64-byte login prefix handling, partial gateway failure
  handling, BR/VN scoped accounts, offline CI tests.
- v2.1.0 - Startup token warmup + background refresher, header cleanup.
- v2.0.0 - Official Garena CDN media, ASTC decode, Unicode fallback, WebP endpoints.
- v1.0.0 - Initial player stats lookup.

## 7. Disclaimer

Unofficial community project, not affiliated with or endorsed by Garena.
Use in accordance with Garena/Free Fire terms of service and local privacy rules.
