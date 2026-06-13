---
name: appstore-connect
description: "App Store Connect API + TestFlight from the CLI — set up & verify the API key, check build/processing status, fetch Xcode Cloud build logs, manage TestFlight groups/testers, and diagnose delivery rejections (ITMS errors). Invoke via /appstore-connect, or when asked about TestFlight, whether a build passed validation / its processing state, Xcode Cloud build logs, App Store Connect data, or why an upload was rejected."
---

# appstore-connect — App Store Connect API + TestFlight from the CLI

Query and drive App Store Connect without the web UI: build/processing status,
Xcode Cloud build logs, TestFlight delivery, and validation-rejection triage.
Complements `ios-run` (which builds and runs locally) — this is the cloud /
release side.

Access needs an App Store Connect **API key**. The key is per-Apple-account /
per-machine — not per-project — so it lives globally at `~/.appstoreconnect/`
and is shared by every Apple project on the machine. **Always run Step 0 first;
never assume access exists.**

Every recipe assumes the config is sourced:

```sh
set -a; . ~/.appstoreconnect/config.env; set +a
```

## 0. Preflight — ensure API access (first, every time)

Check for the key + helper:

```sh
ls ~/.appstoreconnect/config.env ~/.appstoreconnect/private_keys/AuthKey_*.p8 2>/dev/null
```

Install/refresh the bundled client to the global location (idempotent — this
skill ships `asc.py` alongside `SKILL.md`; `<skill-dir>` is the "Base directory
for this skill" shown when it's invoked):

```sh
mkdir -p ~/.appstoreconnect/private_keys && chmod 700 ~/.appstoreconnect ~/.appstoreconnect/private_keys
cp -f "<skill-dir>/asc.py" ~/.appstoreconnect/asc.py
```

**If `config.env` or a `.p8` is missing, STOP and ask the user to create a key —
you cannot do it for them.** Give them these steps:

1. App Store Connect → **Users and Access** → **Integrations** → **App Store Connect API**.
2. Note the **Issuer ID** (UUID at the top).
3. Under **Team Keys** → **Generate API Key** → name it (e.g. `ci`), role
   **App Manager** (enough to read builds/Xcode Cloud and manage TestFlight) → **Generate**.
4. **Download API Key** — the `AuthKey_<KeyID>.p8`, downloadable only once — and note the **Key ID**.
5. Hand back: **Issuer ID**, **Key ID**, and where the `.p8` was saved.

Then store it (never commit a `.p8`; ensure `.gitignore` blocks `*.p8`):

```sh
mv ~/Downloads/AuthKey_<KEYID>.p8 ~/.appstoreconnect/private_keys/
chmod 600 ~/.appstoreconnect/private_keys/AuthKey_<KEYID>.p8
printf 'ASC_ISSUER_ID=%s\nASC_KEY_ID=%s\n' "<ISSUER_ID>" "<KEY_ID>" > ~/.appstoreconnect/config.env
chmod 600 ~/.appstoreconnect/config.env
```

Verify (prints the app name → auth works). The helper signs an ES256 JWT with
`openssl`, so no `pip install` is needed:

```sh
set -a; . ~/.appstoreconnect/config.env; set +a
python3 ~/.appstoreconnect/asc.py "/v1/apps?filter%5BbundleId%5D=<your.bundle.id>&fields%5Bapps%5D=name,bundleId"
```

Note the returned app `id` — most queries below filter by it.

## 1. Build status & validation — did it pass?

```sh
python3 ~/.appstoreconnect/asc.py "/v1/builds?filter%5Bapp%5D=<APP_ID>&sort=-uploadedDate&limit=10&fields%5Bbuilds%5D=version,uploadedDate,processingState,expired"
```

`processingState`: `PROCESSING` (still ingesting) · `VALID` (passed validation,
TestFlight-ready) · `INVALID` / `FAILED` (rejected — see §4). Rejected builds
often don't appear in this list at all; the rejection arrives by email and the
reasons are in §4. `version` is the build number (Xcode Cloud auto-assigns it
from its run counter, overriding the project's `CFBundleVersion`).

## 2. Xcode Cloud build runs + logs

```sh
python3 ~/.appstoreconnect/asc.py "/v1/ciProducts?filter%5Bapp%5D=<APP_ID>"                      # -> PRODUCT_ID
python3 ~/.appstoreconnect/asc.py "/v1/ciBuildRuns?filter%5Bproduct%5D=<PRODUCT_ID>&sort=-number&limit=5"
python3 ~/.appstoreconnect/asc.py "/v1/ciBuildRuns/<RUN_ID>/actions"                              # -> ACTION_ID(s)
python3 ~/.appstoreconnect/asc.py "/v1/ciBuildActions/<ACTION_ID>/issues"                         # errors/warnings
python3 ~/.appstoreconnect/asc.py "/v1/ciBuildActions/<ACTION_ID>/artifacts"                      # logs: fetch each downloadUrl
```

Build logs are artifacts — read an artifact's `downloadUrl` then `curl -L` it.

## 3. TestFlight — get a build onto a tester's device

Internal testing needs no Beta App Review; the build must be `VALID`. Read state:

```sh
python3 ~/.appstoreconnect/asc.py "/v1/apps/<APP_ID>/betaGroups?fields%5BbetaGroups%5D=name,isInternalGroup,hasAccessToAllBuilds"
python3 ~/.appstoreconnect/asc.py "/v1/betaGroups/<GID>/betaTesters?fields%5BbetaTesters%5D=email,state"  # state INSTALLED = has it
```

Writes mutate App Store Connect **and send invite emails — state the change and
confirm with the user before running**:

```sh
echo '{"data":{"type":"betaGroups","attributes":{"name":"Internal","isInternalGroup":true},"relationships":{"app":{"data":{"type":"apps","id":"<APP_ID>"}}}}}' \
  | python3 ~/.appstoreconnect/asc.py POST "/v1/betaGroups"
# internal tester must already be a user on the ASC team:
echo '{"data":{"type":"betaTesters","attributes":{"email":"<user@email>","firstName":"<First>","lastName":"<Last>"},"relationships":{"betaGroups":{"data":[{"type":"betaGroups","id":"<GID>"}]}}}}' \
  | python3 ~/.appstoreconnect/asc.py POST "/v1/betaTesters"
```

For a one-off internal setup, the App Store Connect UI (TestFlight → Internal
Testing) is usually faster than scripting — prefer guiding the user there, and
use the API for status, automation, and CI flows.

## 4. Build rejected at validation? Common ITMS fixes

A build can pass the Xcode Cloud build yet fail Apple's *delivery* validation
(emailed; `processingState: INVALID`). The build-config mechanics live in
`ios-run`; the common rejection → fix mapping:

| Error | Cause | Fix |
|---|---|---|
| **ITMS-90022 / 90023** | No 120×120 / 152×152 app icon | Add a real **1024×1024 opaque (no-alpha)** `AppIcon` — single-size, Xcode auto-generates the device sizes |
| **ITMS-90713** | Missing top-level `CFBundleIconName` | `GENERATE_INFOPLIST_FILE=YES` does **not** emit it (actool writes only the nested `CFBundleIcons`; `INFOPLIST_KEY_CFBundleIconName` is ignored). Use an **explicit `Info.plist`** with `CFBundleIconName=AppIcon`. |
| **ITMS-90683** (missing purpose string) | Used an API that needs a usage description | Add the matching `NS*UsageDescription` to `Info.plist` |
| Export-compliance prompt on every build | `ITSAppUsesNonExemptEncryption` unset | Set it `false` in `Info.plist` (standard HTTPS/TLS only) |

After fixing, push to the workflow's branch (or `xcodebuild archive` + upload)
and re-check §1.

## Security

- The **`.p8` is a private key** — never commit it, never print its contents. It
  lives only at `~/.appstoreconnect/private_keys/` (chmod 600) and the user's
  password manager. `.gitignore` must block `*.p8`.
- Issuer ID / Key ID are identifiers (not secrets) but still belong out of the
  repo, in `~/.appstoreconnect/config.env` (chmod 600).
- Every `POST`/`PATCH`/`DELETE` mutates the user's App Store Connect (and may
  email testers) — **describe the change and get confirmation first**.
