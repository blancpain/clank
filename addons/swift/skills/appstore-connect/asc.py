"""Minimal App Store Connect API client — no third-party dependencies.

Signs an ES256 JWT with `openssl` (the box may have no PyJWT/cryptography),
calls the App Store Connect REST API, prints the JSON response.

Reads ASC_ISSUER_ID / ASC_KEY_ID from the environment; the private key is at
~/.appstoreconnect/private_keys/AuthKey_<KEY_ID>.p8 (override with ASC_KEY_PATH).

  source the config first:  set -a; . ~/.appstoreconnect/config.env; set +a

  GET:    python3 asc.py "/v1/apps?filter[bundleId]=net.example.app"
  write:  echo '<json>' | python3 asc.py POST "/v1/betaGroups"
          (methods: GET POST PATCH PUT DELETE — body read from stdin for writes)
"""
import base64
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

SETUP_HELP = (
    "App Store Connect API access isn't configured on this machine.\n"
    "  1. App Store Connect > Users and Access > Integrations > App Store Connect\n"
    "     API > Team Keys > Generate API Key (role: App Manager). Note the Issuer\n"
    "     ID + Key ID; download AuthKey_<KEYID>.p8 (downloadable only once).\n"
    "  2. mkdir -p ~/.appstoreconnect/private_keys && chmod 700 ~/.appstoreconnect\n"
    "     mv ~/Downloads/AuthKey_<KEYID>.p8 ~/.appstoreconnect/private_keys/\n"
    "     chmod 600 ~/.appstoreconnect/private_keys/AuthKey_<KEYID>.p8\n"
    "  3. printf 'ASC_ISSUER_ID=%s\\nASC_KEY_ID=%s\\n' <ISSUER> <KEYID> "
    "> ~/.appstoreconnect/config.env\n"
    "  4. source it: set -a; . ~/.appstoreconnect/config.env; set +a\n"
    "(See the appstore-connect skill, Step 0.)"
)


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        sys.exit(f"asc.py: {name} is not set.\n\n{SETUP_HELP}")
    return value


ISSUER = _require_env("ASC_ISSUER_ID")
KEY_ID = _require_env("ASC_KEY_ID")
KEY_PATH = os.environ.get(
    "ASC_KEY_PATH",
    os.path.expanduser(f"~/.appstoreconnect/private_keys/AuthKey_{KEY_ID}.p8"),
)
if not os.path.isfile(KEY_PATH):
    sys.exit(f"asc.py: private key not found at {KEY_PATH}.\n\n{SETUP_HELP}")
BASE = "https://api.appstoreconnect.apple.com"
WRITE_METHODS = {"POST", "PATCH", "PUT"}


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def der_to_raw(der: bytes) -> bytes:
    """Convert a DER-encoded ECDSA signature to JOSE raw R||S (64 bytes)."""
    if der[0] != 0x30:
        raise ValueError("not a DER sequence")
    idx = 2
    if der[1] & 0x80:
        idx = 2 + (der[1] & 0x7F)

    def read_int(i):
        if der[i] != 0x02:
            raise ValueError("expected INTEGER")
        length = der[i + 1]
        end = i + 2 + length
        if end > len(der):
            raise ValueError("INTEGER length exceeds buffer")
        return der[i + 2 : end], end

    r, idx = read_int(idx)
    s, idx = read_int(idx)
    if idx != len(der):
        raise ValueError("unexpected trailing bytes in DER signature")
    r = r.lstrip(b"\x00")
    s = s.lstrip(b"\x00")
    if len(r) > 32 or len(s) > 32:
        raise ValueError("ECDSA component exceeds 32 bytes")
    return r.rjust(32, b"\x00") + s.rjust(32, b"\x00")


def make_token() -> str:
    header = {"alg": "ES256", "kid": KEY_ID, "typ": "JWT"}
    now = int(time.time())
    payload = {"iss": ISSUER, "iat": now, "exp": now + 600, "aud": "appstoreconnect-v1"}
    signing_input = (
        b64url(json.dumps(header, separators=(",", ":")).encode())
        + "."
        + b64url(json.dumps(payload, separators=(",", ":")).encode())
    )
    proc = subprocess.run(
        ["openssl", "dgst", "-sha256", "-sign", KEY_PATH],
        input=signing_input.encode(),
        capture_output=True,
    )
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr.decode())
        sys.exit(1)
    return signing_input + "." + b64url(der_to_raw(proc.stdout))


def request(method: str, path: str, body: bytes | None = None) -> str:
    if path.startswith("http"):
        host = urllib.parse.urlparse(path).netloc
        if host != "api.appstoreconnect.apple.com":
            raise ValueError(f"refusing to send credentials to non-ASC host: {host}")
        url = path
    else:
        url = BASE + path
    headers = {"Authorization": "Bearer " + make_token()}
    if body:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.read().decode() or f"(HTTP {resp.status}, empty body)"
    except urllib.error.HTTPError as e:
        sys.stderr.write(f"HTTP {e.code} {e.reason}\n")
        return e.read().decode()


if __name__ == "__main__":
    args = sys.argv[1:]
    method = "GET"
    if args and args[0].upper() in {"GET", *WRITE_METHODS, "DELETE"}:
        method = args.pop(0).upper()
    if not args:
        sys.exit("usage: asc.py [METHOD] <path>   (body on stdin for writes)")
    body = sys.stdin.buffer.read() if method in WRITE_METHODS and not sys.stdin.isatty() else None
    print(request(method, args[0], body))
