#!/bin/sh
set -eu
root="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
command -v python3 >/dev/null 2>&1 || { echo "Instale Python 3.10+ e pipx primeiro. Veja README.md." >&2; exit 2; }
exec python3 "$root/install.py" "$@"
