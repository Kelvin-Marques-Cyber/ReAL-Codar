#!/bin/sh
# Lançador do codar instalado por pacote do sistema (apt, zypper, dnf, pacman, apk).
# O código fica em <prefixo>/lib/codar. Os extras opcionais (Studio e IA local) ficam num ambiente virtual do
# usuário, criado por `codar extras install`; quando ele existe, é o Python dele que roda o codar.
self="$0"
command -v readlink >/dev/null 2>&1 && self="$(readlink -f "$0" 2>/dev/null || echo "$0")"
lib="$(cd "$(dirname "$self")/../lib/codar" 2>/dev/null && pwd)"
if [ -z "$lib" ] || [ ! -d "$lib/codar" ]; then
    echo "codar: instalação incompleta (não achei $(dirname "$self")/../lib/codar)" >&2
    exit 1
fi

if [ -n "$CODAR_HOME" ]; then
    data="$CODAR_HOME/data"
else
    data="${XDG_DATA_HOME:-$HOME/.local/share}/codar"
fi

py="$data/venv/bin/python3"
if [ ! -x "$py" ]; then  # sem extras (ou o Python do sistema mudou de versão e o ambiente ficou para trás)
    py=""
    for c in python3 python3.14 python3.13 python3.12 python3.11 python3.10; do
        if command -v "$c" >/dev/null 2>&1 &&
            "$c" -c 'import sys; sys.exit(sys.version_info < (3, 10))' 2>/dev/null; then
            py="$(command -v "$c")"
            break
        fi
    done
fi
if [ -z "$py" ]; then
    echo "codar: precisa do Python 3.10 ou mais novo (openSUSE Leap 15: sudo zypper install python311)" >&2
    exit 1
fi

PYTHONPATH="$lib${PYTHONPATH:+:$PYTHONPATH}"
CODAR_PACKAGED=1
export PYTHONPATH CODAR_PACKAGED
exec "$py" -m codar "$@"
