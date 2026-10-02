# Account configuration

## Source of truth

The application now reads active service credentials from the repository's `accounts.txt`. The owner explicitly authorized public distribution of the new BR and VN guest test-account pairs. These are shared service credentials, not the player UID being searched.

Before this change, app.py returned hardcoded pairs and never read accounts.txt. The earlier BR/VN failure concerned those hardcoded pairs; it was not a test of every row in the legacy account list.

## Format

```text
# UID PASSWORD REGION
1234567890 example-password BR
2345678901 example-password VN
3456789012 example-password GLOBAL
```

The examples above are placeholders. The repository file contains the actual owner-approved pairs. Preserve credentials as strings. Whitespace separates columns. Empty lines and lines beginning with # are ignored.

The original two-column `UID PASSWORD` inventory has moved to `accounts-legacy.txt`. Its rows have no region metadata and their current login status has not been checked. The application never loads that file. `accounts.txt` contains only active three-column rows with unique, supported scopes. Invalid or duplicate scopes fail with CREDENTIAL_CONFIG_ERROR without exposing the pair.

Active bundled scopes: IND, BR, VN, ID, TH, TW, GLOBAL.

- BR is the fallback for BR/US/NA/SAC/EUROPE (EU aliases EUROPE).
- GLOBAL serves BD/SG/ME/PK/CIS/RU.
- Exact scoped rows take precedence over group rows.
- An AMERICAS row, if deliberately configured, takes precedence over BR for other Americas regions.

## Resolution order

1. Complete exact-region environment override.
2. Complete group environment override (AMERICAS or GLOBAL, where applicable).
3. Exact-region row in accounts.txt.
4. Group row in accounts.txt.

Missing or incomplete credentials fail explicitly. No values from different pairs are mixed. Restart the process after replacing a pair to discard cached tokens.

## Fresh checkout

Install requirements and run the application normally. The bundled file is sufficient; neither this computer's encrypted file nor its Windows user profile is required.

```powershell
python -m pip install -r requirements.txt
python -m flask --app app run --host 127.0.0.1 --port 5055 --no-debugger --no-reload
python tools/diagnose.py --regions BR VN
```

The Windows helper `tools/start-local.ps1` also uses bundled credentials by default. To deliberately load the previous local encrypted overrides, pass `-UsePrivateCredentials`. Environment variables supplied by the host still take precedence in either mode.

Public shared accounts can become unavailable independently of the code. Diagnose OAuth, MajorLogin and player lookup separately before changing protocol values. Never label an unrecognized error response as a confirmed ban or queue without evidence.

Verification on 2026-09-27: all seven configured groups (IND, BR, VN, ID, TH, TW, GLOBAL via BD) passed live OB55 login and self player lookup from `accounts.txt`, without private overrides. This is a point-in-time check; shared accounts can later stop working. The offline test suite runs on every GitHub push and pull request. CI never performs live login. Use `python tools/diagnose.py --regions IND BR VN ID TH TW BD --self-lookup` for a manual repeat; it prints status and response sections without account IDs, passwords, tokens or raw player data.

A temporary fresh copy containing only repository files, with no `.private` directory or credential environment overrides, installed dependencies, passed all 45 offline tests, served the homepage, resolved all seven bundled groups, and completed BR/VN live self-lookups. The temporary copy was removed after verification.
