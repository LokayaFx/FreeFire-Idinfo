# Changelog

All notable changes to the **Free Fire Info Site — Official Dynamic Media Edition** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Account distribution
- With explicit owner authorization, bundle verified BR/VN test credentials in accounts.txt together with the existing active region pairs.
- Resolve active `UID PASSWORD REGION` rows from accounts.txt; move the unscoped, unverified historical inventory to accounts-legacy.txt. Remove hardcoded pairs from app.py.
- Keep environment overrides optional and require -UsePrivateCredentials to load Windows DPAPI overrides.
- Validate login and self player lookup for all seven configured account groups; add metadata-only --self-lookup diagnostics.
- Run offline tests on GitHub push and pull request, with no live login in CI.
- Distinguish player-not-found, account/configuration failure, and upstream failure in API and browser messages.


### Fixed
- Stop labeling unverified OB55 field-13 login replies as queues; return UNRECOGNIZED_LOGIN_RESPONSE without caching or blind retries.
- Keep legacy queue handling scoped to OB54.

### Added
- Windows local launcher supporting DPAPI-encrypted private credentials; verified owner-created BR/VN accounts restore local login and lookup for both regions; local launcher defaults to port 5055 to avoid a conflicting project.
- Complete private credential overrides by exact region or group, with validation and form encoding.
- BR/VN evidence correction, comparison instructions and regression tests.

## [2.2.0] - 2026-09-27

### Fixed
- Default to OB55 and send a fresh X-GA-SV timestamp for binary requests.
- Decode the observed 64-byte OB55 login prefix; keep player responses unprefixed.
- Reject missing tokens, malformed login responses, queue-only replies and unsupported returned servers.
- Check upstream HTTP errors before decoding; preserve partial gateway failures as inconclusive lookups rather than false player-not-found.
- Report partial token refresh failure instead of claiming every region refreshed.

### Added
- Separate OB54/OB55 profiles, synthetic protocol regression tests and opt-in metadata-only live diagnostics.
- English OB maintenance/troubleshooting runbook and dated research evidence.

### Known limitations
- BR/VN bundled accounts returned tokenless replies initially misclassified as queues; their semantics remain unverified. Complete official OB55 schema provenance and all-region validation remain outstanding.

## [2.1.0] - 2026-08-21

### Added
- **Server Startup Token Warmup**: Automatic asynchronous pre-warming of JWT tokens across all supported regional Free Fire clusters on local server launch (`asyncio.run(initialize_tokens())`), eliminating first-request latency.
- **Background Daemon Token Refresher**: Background thread (`start_token_refresher`) automatically refreshing regional gateway authentication tokens every 7 hours (`25200s`) to ensure zero token expiration downtime.

### Changed
- **Optimized HTTP Transport Headers**: Cleaned up manual connection management headers (`Expect: 100-continue`, `Connection: Keep-Alive`, `Accept-Encoding: gzip`) in `create_jwt` and `GetAccountInformation` for robust compatibility across proxy gateways and modern HTTP clients.
- **Protobuf & Python Compatibility**: Enhanced dependency definitions and cross-runtime compatibility with Python 3.10 through 3.14.

---

## [2.0.0] - 2026-07-24

### Added
- **Official Garena CDN Integration**: Direct binary ASTC texture downloading from Garena Icon CDN (`dl-tata.freefireind.in` & `dl.tata.freefiremobile.com`) using player `bannerId` and `headPic`.
- **Native ASTC Texture Decoder**: Server-side decoding of 2D ASTC textures using `texture2ddecoder` and PIL/Pillow.
- **Full Unicode Font Stack Fallback**: Comprehensive character-level font stack fallback (`NotoSans`, `NotoSansCherokee`, `NotoSansSC`, `NotoSansMath`, `NotoSansSymbols`, `Microsoft Himalaya`, `Segoe UI Symbol`) rendering all Free Fire nicknames containing Cherokee, CJK, Tibetan, Math symbols, and special characters cleanly without missing glyph boxes (`🗙`).
- **Gameskinbo Card Layout & Styling**: 4:1 aspect ratio profile card with a 3px solid white square avatar frame, unblurred background graphics, and clean text layout (`Lvl. XX`).
- **Image Sharpness & Contrast Enhancement**: Automatic server-side contrast and sharpness enhancement (`ImageEnhance.Sharpness`) for Garena CDN textures.
- **Vercel & Serverless Support**: Added `vercel.json` and `wsgi.py` for one-click Vercel deployment.

### Changed
- Removed third-party external image composition dependencies.
- Replaced static sample avatar images with dynamic server-side generated WebP media endpoints (`/api/banner/banner_<UID>.webp` and `/api/avatar/avatar_<UID>.webp`).

### Fixed
- Fixed 180° texture orientation and bounding box trimming for Free Fire avatar icons.
- Fixed invisible Hangul filler (`\u3164`) and Braille blank spacing in guild names.

---

## [1.0.0] - 2026-07-01

### Added
- Initial release of Free Fire Info Checker with multi-region protobuf decryption.
- Player stats lookup (`level`, `likes`, `rank`, `guild`, `BR/CS points`).
