> **Current configuration:** Active credentials, including the owner-approved public BR/VN pairs, now come from `accounts.txt`. Private overrides are optional. Earlier DPAPI-only statements below describe historical stages. See [account configuration](ACCOUNT_CONFIGURATION.md).

# OB update and troubleshooting runbook

## Current status — 2026-09-27 / v2.2.0

The default protocol is OB55. See [OB55 research](OB55_RESEARCH_2026-09-27.md) for evidence and test results. That file is a historical snapshot of the investigation before implementation; this runbook describes the current implementation.

Verified fixes:

- Send `ReleaseVersion: OB55` and generate `X-GA-SV` from the current Unix time in seconds for each request. Do not use a fixed timestamp.
- Remove the 64-byte prefix from OB55 **MajorLogin** responses before Protobuf decoding. Player responses do not have this prefix.
- The existing AES key/IV and request schema worked for the tested BD lookup. Generated `_pb2.py` files were not edited manually.
- The existing `loginbp.ggblueshark.com` host worked with the corrected headers. Changing the host alone does not resolve this failure.
- Queue-only replies, missing tokens/servers and malformed responses are not cached.

## Code map

| Concern | File / function |
| --- | --- |
| OB profile, prefix, timestamp header | `protocol.py`: PROFILES, binary_headers |
| Login endpoint and returned-host allowlist | `protocol.py`: LOGIN_URL, PLAYER_HOSTS, validate_server |
| Framing, queues and required fields | `protocol.py`: decode_login |
| Guest authentication, JWT and token TTL | `app.py`: get_access_token, create_jwt, get_token_info |
| Player request and decoding | `app.py`: GetAccountInformation |
| Region fallback and cache | `app.py`: get_player_data |
| Live diagnostics | `tools/diagnose.py` |
| Offline regression tests | `tests/test_protocol.py`, `tests/test_official_media.py` |
| Official media/CDN | `official_media.py` |

## Running locally

Python 3.10+ is required; this installation was verified with Python 3.10. In PowerShell:

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m flask --app app run --host 127.0.0.1 --port 5055 --no-debugger --no-reload
```

The Flask CLI authenticates lazily on the first lookup. Running `python app.py` enables startup token warmup and periodic refresh. Successful regions remain usable when warmup partially fails. Restart the process after code changes; reloading the browser alone is insufficient.

## Investigating failures after a new OB release

1. Confirm the OB label and date using Garena's official patch notes. Record the client build/hash, region and test time. Treat community code as a hypothesis to verify.
2. Run offline tests first, then perform manual diagnostics with an authorized test account:

   ```powershell
   .\.venv\Scripts\python.exe tools/diagnose.py --regions BD IND BR VN ID TH TW
   .\.venv\Scripts\python.exe tools/diagnose.py --regions BD --uid YOUR_TEST_UID
   ```

   Exit code 0 means the requested checks passed; exit code 1 indicates a failure or a player-not-found result. These commands make live network requests; do not run them in public CI. Output excludes tokens, passwords, open IDs, UIDs and raw player data.

3. Isolate the failing stage: guest OAuth → MajorLogin → framing/Protobuf → returned regional server → player lookup → media. A working homepage does not establish API health.
4. Keep the account and request consistent while changing one variable at a time: release header, timestamp header, host or framing. HTTP 200 alone is insufficient; require a token, region and validated HTTPS server.
5. Add a new entry to PROFILES for a new version while preserving the old profile. Update the supported-version list, tests and documentation together. Increasing the OB number alone does not establish production compatibility.
6. Verify response framing independently. Do not remove 64 bytes from every binary response, scan arbitrary offsets or accept a JWT regex match as a complete login. The new prefix's meaning has not yet been verified against an official specification.
7. When exact client descriptors are available, compare normalized field numbers and types. Matching field names do not guarantee matching wire contracts. Regenerate generated code instead of editing it manually.
8. Use non-secret synthetic fixtures to test request bytes, AES ciphertext, framed/unframed responses, queues, errors and truncation. Keep captures containing secrets out of Git.
9. Verify login, valid/invalid player lookup, cache expiry, partial outages and media for every account group. Success in one region does not establish success elsewhere.
10. Update CHANGELOG and the evidence record, restart the server and verify the complete flow in the browser.

## Error reference

For OB55, `UNRECOGNIZED_LOGIN_RESPONSE` means a tokenless field-13 response whose semantics have not been verified. Do not assume that waiting or retrying resolves it. `CREDENTIAL_CONFIG_ERROR` means the active account file or an environment override is missing or invalid.


| Code / symptom | Meaning and next checks |
| --- | --- |
| UPSTREAM_HTTP_ERROR, MajorLogin 503 | Check OB header routing as well as service availability. The OB54-to-OB55 incident produced this response. |
| MajorLogin 400 | Check request headers, framing and client profile. A missing X-GA-SV produced this response with OB55. |
| INVALID_LOGIN_RESPONSE | Verify prefix length, body shape and schema. Do not decode an HTML error as Protobuf. |
| LOGIN_QUEUE | A legacy OB54 queue-only reply is exposed as HTTP 503 and is not a usable JWT. Retry later without a tight loop. This does not establish an account ban. |
| INCOMPLETE_LOGIN | The response lacks a token, region or server despite HTTP 200; it will not be cached. |
| GUEST_AUTH_FAILED | Guest authentication returned incomplete credentials; the failure precedes MajorLogin. |
| INVALID_LOGIN_SERVER | The returned host may have changed. Verify ownership and current client evidence before extending the allowlist. |
| LOOKUP_INCOMPLETE | At least one gateway failed and no player was found elsewhere. A definitive not-found result is unavailable. Diagnose with an explicit region. |
| UPSTREAM_CONNECTION_ERROR | Check DNS, TLS, timeouts and connectivity. Keep certificate validation enabled. |
| Player data works but media fails | Investigate CDN, ASTC and fonts separately using media logs. |

## Configuration and rollback

`FREEFIRE_OB_VERSION` supports OB54 and OB55; the default is OB55. It is read at process startup. In PowerShell, `$env:FREEFIRE_OB_VERSION='OB54'` selects the previous framing behavior for rollback/debugging. The current upstream rejected OB54 requests, so selecting OB54 does not guarantee restored service. Preserve the old profile until the new release is verified. To roll back code, check out the intended version and restart the process.

## Limitations and release checklist

- The original hardcoded BR/VN accounts returned unrecognized tokenless replies, initially misclassified by the legacy schema as queues. Their exact failure reason remains unverified. See [BR/VN investigation](BR_VN_INVESTIGATION.md). The replacement active accounts passed live checks on 2026-09-27; availability can change later.
- Full official OB55 schema/build provenance remains outstanding. A successful lookup with the existing schema does not establish support for every new field.
- Required fields and the returned server are validated after removing the prefix; the prefix's cryptographic meaning has not been verified.
- Caches are process-local. There is no shared cache or refresh lock across workers; high-load deployments need additional work.
- Research observed a TTL of 28,800 seconds; the application caps caching at 25,200 seconds.
- Do not publish bodies, headers or trace dumps containing secrets. The owner authorized the seven bundled service pairs; use environment overrides for any other private accounts.

An evidence record should include UTC time, commit, OB/client build/hash, region/group, guest/login/player HTTP statuses, framing length, required-field presence, cache/media results, failures and remaining unknowns. Exclude credentials, tokens and raw responses.

## Implementation verification — 2026-09-27

- Offline suite: 26 tests passed (protocol and existing media tests).
- Updated-code live diagnostic: BD login and player lookup passed.
- In-app browser: OB55 v2.2.0 displayed; UI example player search populated account, rank, guild and pet sections.
- Browser banner request: HTTP 200; UI reported official CDN assets served locally.
- Avatar endpoint: HTTP 200 with image/webp.
- git diff --check passed after line-ending cleanup.
- No GitHub push or deployment performed. Local Flask server restarted.


## Current account verification — 2026-09-27

The active `accounts.txt` has seven scoped rows; `accounts-legacy.txt` contains 2,724 unscoped historical rows and is never read. No claim has been made that those historical accounts work or fail. With no private overrides, all seven active groups passed MajorLogin and their own player lookup:

| Configured group | Diagnostic region | Login | Own player lookup |
| --- | --- | --- | --- |
| IND | IND | OK | OK |
| BR / Americas | BR | OK | OK |
| VN | VN | OK | OK |
| ID | ID | OK | OK |
| TH | TH | OK | OK |
| TW | TW | OK | OK |
| GLOBAL | BD (locks to SG) | OK | OK |

Repeat manually with `.\.venv\Scripts\python.exe tools/diagnose.py --regions IND BR VN ID TH TW BD --self-lookup`. This reads the account ID from each login token only in memory and prints status and response section names, never credentials, account IDs, tokens or raw player data. CI runs only the offline suite.

The older account investigation in [BR/VN investigation](BR_VN_INVESTIGATION.md) is historical. The owner-approved BR/VN pairs are now bundled in `accounts.txt`; the optional encrypted local overrides are not needed for a fresh checkout.
