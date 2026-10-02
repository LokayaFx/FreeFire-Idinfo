> **Current configuration:** Active credentials, including the owner-approved public BR/VN pairs, now come from `accounts.txt`. Private overrides are optional. Earlier DPAPI-only statements below describe historical stages. See [account configuration](ACCOUNT_CONFIGURATION.md).

# BR/VN login investigation — 2026-09-27

## Status

The incorrect queue classification is fixed. VN authentication is now restored on this Windows installation using the owner-created VN test account. BR is also restored locally using the owner-created Free Fire MAX guest account; bundled credentials remain unchanged. Their configured guest accounts authenticate at OAuth, but MajorLogin returns no usable token or server URL. Do not describe this incident as a confirmed queue or ban.

## Evidence

- BD control login succeeds with the same OB55 headers, encryption and framing.
- BR and VN MajorLogin responses: HTTP 200, 78 bytes; 14 bytes remain after the observed 64-byte prefix.
- Top-level field 13 contains varint field 1 = 1 and varint field 3 = 1756478597 (BR) or 1766375816 (VN).
- The legacy descriptor labels these as queue allow and wait seconds. The values correspond to past UTC dates when interpreted as Unix timestamps, which makes the queue interpretation unreliable.
- Current public community descriptors inspected repeat the legacy mapping or omit error fields; none establishes an authoritative OB55 mapping for field 13.
- The local PHP monorepo bundles the same BR/VN credential pairs. No alternate credentials from that repository can provide an independent control.

The shape could represent a restriction response, but this is unverified. Neither HTTP 200 nor successful parsing establishes semantic correctness.

## Implemented changes

- OB55 field-13-only responses now produce UNRECOGNIZED_LOGIN_RESPONSE (502), not LOGIN_QUEUE or advice to wait.
- Legacy OB54 queue handling remains version-specific.
- No tokenless response is cached. No blind retry loop or guessed schema change was introduced.
- Optional complete private credential overrides are supported, with exact-region precedence over group overrides. Incomplete overrides fail closed rather than mixing with bundled credentials.
- Regression coverage includes the observed numeric shapes, no-cache behavior, error propagation, credential encoding and override precedence.

## Controlled comparison needed

Use an existing authorized, working test account in the affected region. Verify its normal official-client login first. Do not use credential dumps or assume that a bundled account is healthy.

Set process environment variables through your private local configuration or deployment secret manager:

| Scope | UID variable | Password variable |
| --- | --- | --- |
| BR only | FREEFIRE_BR_UID | FREEFIRE_BR_PASSWORD |
| VN only | FREEFIRE_VN_UID | FREEFIRE_VN_PASSWORD |
| Americas group | FREEFIRE_AMERICAS_UID | FREEFIRE_AMERICAS_PASSWORD |
| Global group | FREEFIRE_GLOBAL_UID | FREEFIRE_GLOBAL_PASSWORD |

Each supported region also accepts FREEFIRE_<REGION>_UID and FREEFIRE_<REGION>_PASSWORD. Exact-region values take precedence. Americas covers BR/US/NA/SAC/EUROPE; global covers BD/SG/ME/PK/CIS/RU. Both values must be set together. Values are form-encoded before use. No automatic .env loading is implemented: supply actual process environment variables. Restart the app after changing credentials so previously cached tokens are cleared. Do not paste credentials into chat, source files, logs or fixtures.

Then run:

```powershell
.\.venv\Scripts\python.exe tools/diagnose.py --regions BR VN
```

- Working account succeeds while the bundled account fails: investigate the bundled account's state using the official client/support process.
- Official client succeeds but the same account fails here: obtain that client build's request/response descriptors and compare required fields/framing.
- A verified current descriptor identifies field 13: implement a separate versioned error schema and synthetic fixtures. Do not rename a field based only on its numeric values.

## Validation

38 offline tests passed. Live BD login passed. BR/VN correctly report UNRECOGNIZED_LOGIN_RESPONSE and remain unavailable with bundled credentials. The remaining blocker is live account/schema evidence, not an unimplemented retry.


## VN resolution — owner-controlled account comparison

On 2026-09-27, the owner created a guest account in the official `com.dts.freefireth` client on their rooted Android 13 phone and reached the VN lobby. With authorized read-only ADB access, the complete guest pair was found in:

`/data/data/com.dts.freefireth/shared_prefs/com.garena.msdk.persist.fallback.xml`

The observed keys were `com.garena.msdk.guest_uid` and `com.garena.msdk.guest_password`. This location is evidence for the tested installation, not a guarantee for every build. No app data was cleared or modified and no raw preference file was saved locally.

The new pair succeeded with the same OB55 implementation that failed for the bundled VN pair. MajorLogin returned a usable token and lock region VN. The new account's own player profile was retrieved successfully. This establishes an account-dependent difference; it does not prove a ban or the exact semantics of the old field-13 response.

The pair is stored only in `.private/credentials.dpapi`, encrypted with Windows DPAPI for the current Windows user and excluded by `.gitignore`. No account identifier, password, token or player response is committed in this record.

Local startup:

```powershell
pwsh -NoProfile -File tools/start-local.ps1
pwsh -NoProfile -File tools/start-local.ps1 -Diagnose -Regions VN
```

The launcher loads the encrypted configuration into process environment variables, starts Flask (or diagnostics), and restores the previous environment on exit. Running Flask directly does not load this encrypted file. DPAPI storage is specific to the Windows user/profile; it is not a portable deployment secret. Other hosts should receive an authorized complete pair through their secret manager.

Post-restart verification: explicit VN lookup returned HTTP 200 and region VN; automatic lookup of the same cached player also returned HTTP 200. Other regions retain their existing configuration. BR has not been restored or verified with a new account.


## BR resolution and final local verification — 2026-09-27

The owner created a BR guest account in `com.dts.freefiremax` on their connected phone. Authorized read-only inspection found its pair in `shared_prefs/com.garena.msdk.persist.fallback.xml`, using the same guest UID/password keys as the tested standard client. No Facebook preferences or tokens were inspected.

Using the existing protocol, MajorLogin returned lock region BR and a usable token. The account's own player lookup also succeeded. The BR pair was merged into the DPAPI-encrypted configuration without replacing the VN pair. Neither pair was written in plaintext or committed.

The final restarted local service returned HTTP 200 and the correct region for both BR and VN using automatic lookup first and then explicit-region lookup. BR/VN are now restored locally; this does not establish why the old accounts fail or change the bundled defaults for other installations.

Port 5000 was also occupied by a separate project at `M:/Codenew/BB/FreeFireInfoSite`. That process was preserved. The encrypted-config launcher now defaults to **http://127.0.0.1:5055/**. Use `-Port` to select another free port. Always verify the listening process belongs to the intended checkout; on Windows the venv launcher may spawn a child from the base Python installation.
