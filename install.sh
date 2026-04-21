#!/bin/sh
# clank bootstrap — fetch the repo tarball and run install.py. Zero-clone UX.
#
# Usage:
#   cd ~/repos/new-project
#   curl -fsSL https://raw.githubusercontent.com/blancpain/clank/main/install.sh \
#     | sh -s -- --preset python-sql
#
# clank installs into the current directory by default (with a y/N confirm).
# Pass --target explicitly to install somewhere else, or --force to skip the
# CWD confirm in non-interactive contexts. Any flags after `--` are passed
# straight through to install.py (see docs/install.md).
#
# Environment:
#   CLANK_REF   git ref (branch, tag, or SHA) to fetch. Default: main.
#   CLANK_REPO  GitHub owner/repo override. Default: blancpain/clank.

set -eu

CLANK_REF="${CLANK_REF:-main}"
CLANK_REPO="${CLANK_REPO:-blancpain/clank}"

die() {
    printf 'clank bootstrap: %s\n' "$1" >&2
    exit 1
}

command -v curl    >/dev/null 2>&1 || die "curl not found"
command -v tar     >/dev/null 2>&1 || die "tar not found"
command -v python3 >/dev/null 2>&1 || die "python3 not found (clank requires Python 3.11+)"

# install.py uses tomllib, which landed in Python 3.11.
py_ok=$(python3 -c 'import sys; print(1 if sys.version_info >= (3, 11) else 0)')
if [ "$py_ok" != "1" ]; then
    py_ver=$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')
    die "Python 3.11+ required, found $py_ver"
fi

tmpdir=$(mktemp -d 2>/dev/null || mktemp -d -t clank)
trap 'rm -rf "$tmpdir"' EXIT INT TERM HUP

url="https://github.com/${CLANK_REPO}/archive/${CLANK_REF}.tar.gz"
printf 'clank: fetching %s\n' "$url" >&2
curl -fsSL "$url" | tar -xz -C "$tmpdir" \
    || die "failed to fetch or extract $url (check CLANK_REF=$CLANK_REF)"

# GitHub archives extract to a single top-level dir like clank-<ref>/.
# Find it without relying on non-POSIX find flags.
clank_dir=""
for d in "$tmpdir"/*/; do
    if [ -d "$d" ] && [ -f "${d}install.py" ]; then
        clank_dir="${d%/}"
        break
    fi
done
[ -n "$clank_dir" ] || die "extracted tarball missing install.py"

# Drop a sidecar file with the fetched ref so install.py's _git_commit()
# can surface it in the receipt without needing a user-facing CLI flag.
# install.py prefers this file over `git rev-parse HEAD` when present.
printf '%s\n' "$CLANK_REF" > "$clank_dir/.clank-ref"

# install.py uses input() for the interactive picker and conflict prompts.
# When invoked via `curl | sh`, the shell's stdin is the curl pipe — already
# consumed — so python's input() would hit EOF. Fix: redirect python's stdin
# from /dev/tty so prompts reach the controlling terminal.
#
# IMPORTANT: this must be a per-command redirect (< /dev/tty on the python
# invocation), NOT `exec < /dev/tty` on the shell. Under `curl | sh -s --`,
# the shell is still reading the script one statement at a time from the
# curl pipe; reassigning the shell's stdin would make subsequent reads come
# from /dev/tty and hang waiting for "more script" at the terminal.
#
# In non-interactive contexts (CI, no tty) /dev/tty isn't readable — fall
# through to an unredirected invocation so EOF reaches input() immediately.
# The user should pass --force or a fully-specified --include/--exclude
# selection in that case to avoid prompts altogether.
if [ -r /dev/tty ]; then
    python3 "$clank_dir/install.py" "$@" < /dev/tty
else
    python3 "$clank_dir/install.py" "$@"
fi
