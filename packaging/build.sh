#!/bin/sh
# Gera em dist/: wheel e sdist (PyPI), .deb (apt), .rpm (zypper/dnf), .apk (Alpine) e .pkg.tar.zst (pacman).
#   packaging/build.sh            # todos os formatos
#   packaging/build.sh deb rpm    # só alguns
# Requer python3 e nfpm (https://nfpm.goreleaser.com; ou NFPM=/caminho/do/nfpm). Com npm e as dependências da
# extensão instaladas (clients/vscode/node_modules), o .vsix do VS Code também entra nos pacotes.
set -eu
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
python3 packaging/check_versions.py
formats="${*:-deb rpm apk archlinux}"
nfpm="${NFPM:-nfpm}"
version="$(sed -n 's/^__version__ = "\(.*\)"/\1/p' src/codar/__init__.py)"
export CODAR_VERSION="$version"
export CODAR_MAINTAINER="${CODAR_MAINTAINER:-Kelvin e Silva Marques <148489077+Kelvin-Marques-Cyber@users.noreply.github.com>}"
mkdir -p dist

if [ -d clients/vscode/node_modules ] && command -v npm >/dev/null 2>&1; then
    echo "extensão do VS Code…"
    (cd clients/vscode && npm run --silent compile && npm run --silent package >/dev/null)
fi

echo "wheel e sdist…"
if python3 -m build --version >/dev/null 2>&1; then
    python3 -m build --outdir dist . >/dev/null
else
    python3 -m pip wheel --no-deps --quiet -w dist .
    echo "  (sem o pacote 'build' não há sdist: pip install build)"
fi

echo "árvore de instalação…"
rm -rf build/root
VIM_DIRS="vimfiles site" packaging/stage.sh build/root

for f in $formats; do
    config=packaging/nfpm.yaml
    if [ "$f" = apk ]; then  # o apk recusa descrição multilinha e diretórios de "type: tree" (ver apk_config.py)
        config=build/nfpm-apk.yaml
        python3 packaging/apk_config.py packaging/nfpm.yaml > "$config"
    fi
    "$nfpm" package --config "$config" --packager "$f" --target dist/ | sed 's/^/  /'
done
rm -rf build/root
ls -1 dist/
