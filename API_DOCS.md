# Lokaya_API - API Documentation

> Base URL (local): `http://127.0.0.1:5055`
> Replace with your deployed backend URL when calling from a multi-tool frontend.
> All responses are JSON, except the media endpoints which return `image/webp`.
> CORS is enabled, so browsers can call this API directly.

## Contents

1. [Quickstart](#1-quickstart)
2. [Authentication](#2-authentication)
3. [Endpoints](#3-endpoints)
4. [Errors](#4-errors)
5. [Data model](#5-data-model)
6. [Media rendering](#6-media-rendering)
7. [Caching & limits](#7-caching--limits)
8. [Self-hosting & accounts](#8-self-hosting--accounts)
9. [Troubleshooting](#9-troubleshooting)
10. [Version history](#10-version-history)

---

## 1. Quickstart

```js
// Player JSON
const res = await fetch('http://127.0.0.1:5055/player-info?uid=4422076728');
const data = await res.json();
console.log(data.basicInfo.nickname, data.basicInfo.level);

// Banner image URL (use directly in <img>)
const banner = data.mediaInfo.bannerUrl;
const avatar = data.mediaInfo.avatarUrl;
```

```html
<img id="banner" alt="player banner">
<script>
  fetch('http://127.0.0.1:5055/player-info?uid=4422076728')
    .then(r => r.json())
    .then(d => { document.getElementById('banner').src = d.mediaInfo.bannerUrl; });
</script>
```

---

## 2. Authentication

No API key is required. Service (guest) credentials are held **server-side**
in `accounts.txt` and are never exposed to clients. The browser only sends the
player `uid` being looked up.

---

## 3. Endpoints

### 3.1 Get player info

```http
GET /player-info?uid={uid}&region={region}
```

| Parameter | In | Required | Description |
|---|---|---|---|
| `uid` | query | Yes | Player UID, digits only (5-20 chars). |
| `region` | query | No | Region code (e.g. `BD`, `SG`, `VN`, `BR`). Omit for auto-detect across gateway regions. `EU` is accepted as an alias of `EUROPE`. |

**Success `200`** — full Garena player object plus a `mediaInfo` block:

```json
{
  "basicInfo": {
    "accountId": "4422076728",
    "nickname": "player name",
    "level": 67,
    "liked": 9196,
    "region": "BD",
    "createAt": "1637316422",
    "lastLoginAt": "1784889557",
    "headPic": 902050009,
    "bannerId": 901000116,
    "releaseVersion": "OB55"
  },
  "clanBasicInfo": { "clanId": "3015421980", "clanName": "...", "clanLevel": 5 },
  "captainBasicInfo": { "accountId": "...", "nickname": "...", "level": 65 },
  "socialInfo": { "signature": "...", "language": "English", "gender": "Female" },
  "mediaInfo": {
    "bannerUrl": "/api/banner/banner_4422076728.webp?region=BD&v=v7-...",
    "avatarUrl": "/api/avatar/avatar_4422076728.webp?region=BD&v=v7-...",
    "policy": "official-free-fire-cdn-only-with-local-fallback"
  }
}
```

### 3.2 Get player banner

```http
GET /api/banner/banner_{uid}.webp?region={region}
```

Returns `image/webp` (official CDN texture composited server-side, local fallback
when the CDN asset is unavailable). Useful response headers:

| Header | Meaning |
|---|---|
| `X-Free-Fire-Media-Source` | `official-free-fire-cdn` or fallback value |
| `X-Free-Fire-Official-Banner` | `1` if the real banner texture was used |
| `X-Free-Fire-Official-Avatar` | `1` if the real avatar texture was used |

### 3.3 Get player avatar

```http
GET /api/avatar/avatar_{uid}.webp?region={region}
```

Same behavior/headers as the banner endpoint, square avatar image.

### 3.4 Refresh tokens

```http
GET /refresh
POST /refresh
```

Forces a refresh of all regional gateway tokens. **Success `200`:**

```json
{ "message": "Tokens refreshed for all regions." }
```

---

## 4. Errors

Error responses are JSON with an `error` message and a machine-readable `code`:

```json
{ "error": "Player not found in the available regions.", "code": "PLAYER_NOT_FOUND" }
```

| HTTP | Code | Meaning |
|---|---|---|
| 400 | `INVALID_INPUT` | Missing/invalid `uid` or unsupported `region`. |
| 400 | `PLAYER_NOT_FOUND` | No player for this UID in the searched regions. |
| 502 | `UPSTREAM_CONNECTION_ERROR` | Free Fire service unreachable. Retry later. |
| 502 | `UPSTREAM_HTTP_ERROR` | Free Fire service returned an error. Retry later. |
| 502 | `UNRECOGNIZED_LOGIN_RESPONSE` | Service-account login returned no usable token. Check account/OB protocol. |
| 503 | `GUEST_AUTH_FAILED` | Service account could not authenticate. |
| 503 | `CREDENTIAL_CONFIG_ERROR` | Service account missing/misconfigured. |
| 503 | `LOOKUP_INCOMPLETE` | Some gateways unavailable; retry later or pass `region`. |
| 503 | `TOKEN_REFRESH_INCOMPLETE` | Partial failure of `/refresh`; working regions still usable. |

---

## 5. Data model

Top-level sections of `/player-info` (all optional except `basicInfo`):

| Section | Contents |
|---|---|
| `basicInfo` | `accountId`, `nickname`, `level`, `exp`, `liked`, `region`, `createAt`, `lastLoginAt`, `rankingPoints`, `csRankingPoints`, `headPic`, `bannerId`, `badgeId`, `badgeCnt`, `title`, `pinId`, `seasonId`, `releaseVersion`, `showBrRank`, `showCsRank` |
| `clanBasicInfo` | `clanId`, `clanName`, `clanLevel`, `memberNum`, `capacity` |
| `captainBasicInfo` | Guild leader `accountId`, `nickname`, `level`, `liked`, `createAt`, `lastLoginAt` |
| `socialInfo` | `signature`, `language`, `gender`, `modePrefer`, `rankShow` |
| `creditScoreInfo` | `creditScore` |
| `petInfo` | `id`, `level`, `exp`, `isSelected`, `selectedSkillId`, `skinId` |
| `profileInfo` | `avatarId`, `isSelectedAwaken`, `clothes[]`, `equipedSkills[]` |
| `diamondCostRes` | `diamondCost` |
| `mediaInfo` | `bannerUrl`, `avatarUrl`, `policy` (added by this API) |

Timestamps (`createAt`, `lastLoginAt`) are Unix seconds.

---

## 6. Media rendering

1. `/player-info` reads the player's `bannerId` / `headPic`.
2. Banner/avatar endpoints re-use the cached lookup and build allowlisted
   Garena CDN URLs (numeric item IDs only, HTTPS, fixed hosts).
3. ASTC textures are decoded natively and composited with nickname, UID,
   region, guild and level into a WebP image via Pillow.
4. Fallbacks: missing banner texture -> generated background + real avatar;
   missing avatar -> real banner + generated avatar; both missing -> fully
   local card. The browser keeps a canvas renderer as the last resort.

Security: UID 5-20 digits, item IDs 6-14 digits, 8 MiB CDN limit, redirects
disabled, 2D ASTC only, no arbitrary remote URLs.

---

## 7. Caching & limits

- Player JSON is cached in-memory for ~5 minutes per `(region, uid)`.
- Media responses carry `Cache-Control: public, max-age=300`.
- Gateway tokens live ~7 hours and refresh in the background.
- Pass an explicit `region` to skip auto-detect and reduce upstream calls.

---

## 8. Self-hosting & accounts

```bash
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m flask --app app run --host 127.0.0.1 --port 5055 --no-debugger --no-reload
```

Windows helper: `pwsh -NoProfile -File tools/start-local.ps1`

Service accounts (`accounts.txt`, one per line, `UID PASSWORD REGION`):

```text
# UID PASSWORD REGION
1234567890 example-password BR
2345678901 example-password VN
3456789012 example-password GLOBAL
```

- Regions: `BD IND SG VN TH BR US NA SAC ID RU TW ME PK CIS EUROPE`.
- `BR` falls back for `BR/US/NA/SAC/EUROPE`; `GLOBAL` serves `BD/SG/ME/PK/CIS/RU`.
- Optional env overrides: `FREEFIRE_<SCOPE>_UID` + `FREEFIRE_<SCOPE>_PASSWORD`
  (`SCOPE` = region or `AMERICAS`/`GLOBAL`). Exact-region wins over group.
- Restart the process after changing credentials to drop cached tokens.
- `fonts/` is required for nickname rendering — do not delete it.

---

## 9. Troubleshooting

| Symptom | Action |
|---|---|
| `PLAYER_NOT_FOUND` | Verify UID digits; try with explicit `region`. |
| `LOOKUP_INCOMPLETE` | Gateways partially down; retry or specify `region`. |
| `UNRECOGNIZED_LOGIN_RESPONSE` / `GUEST_AUTH_FAILED` | Service account issue; check `accounts.txt` / overrides, do not blind-retry. |
| Player OK but media fallback | CDN asset missing for that item ID; fallback is expected. |
| After code changes | Restart the server process; browser reload alone is not enough. |

Optional live diagnostics (never run in public CI, output is metadata-only):

```powershell
.\.venv\Scripts\python.exe tools/diagnose.py --regions BD --self-lookup
.\.venv\Scripts\python.exe tools/diagnose.py --regions IND BR VN ID TH TW BD --self-lookup
```

Protocol notes (OB55): requests send `ReleaseVersion: OB55` with a fresh
`X-GA-SV` Unix-timestamp header; OB55 `MajorLogin` replies carry a 64-byte
prefix that is stripped before Protobuf decoding (player replies have no
prefix). Tokenless field-13-only replies are reported as
`UNRECOGNIZED_LOGIN_RESPONSE`, never cached or retried blindly.

---

## 10. Version history

- **v2.2.0** — OB55 default + timestamp header, 64-byte login prefix handling,
  partial-gateway tolerance, scoped BR/VN accounts, offline CI tests.
- **v2.1.0** — Startup token warmup + background refresher, transport header cleanup.
- **v2.0.0** — Official CDN media, ASTC decoding, Unicode fallback, WebP endpoints.
- **v1.0.0** — Initial player stats lookup.

---

*Unofficial community project, not affiliated with or endorsed by Garena.
Use per Garena/Free Fire ToS and local privacy rules.*
