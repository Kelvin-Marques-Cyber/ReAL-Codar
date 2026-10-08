#!/bin/sh
# Instalador do CODAR: baixa o pacote da última versão publicada no GitHub e instala com o gerenciador de pacotes do
# sistema (apt, zypper, dnf, pacman ou apk). Sem um deles, mostra como instalar com pipx.
#
#   curl -fsSL https://raw.githubusercontent.com/Kelvin-Marques-Cyber/ReAL-Codar/main/packaging/install.sh | sh
#
# Variáveis opcionais:
#   CODAR_VERSION=0.1.0   versão específica em vez da última
#   CODAR_PKG=/caminho    instala um pacote já baixado (sem acessar a rede)
set -eu

REPO="Kelvin-Marques-Cyber/ReAL-Codar"

say() { printf '\033[1;38;5;208m▸\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31m✗\033[0m %s\n' "$*" >&2; exit 1; }

main() {
    if [ "$(id -u)" -eq 0 ]; then
        sudo=""
    elif command -v sudo >/dev/null 2>&1; then
        sudo="sudo"
    else
        fail "rode como root ou instale o sudo"
    fi

    if command -v apt-get >/dev/null 2>&1; then
        kind="deb"; suffix="_all.deb"
    elif command -v zypper >/dev/null 2>&1; then
        kind="zypper"; suffix=".noarch.rpm"
    elif command -v dnf >/dev/null 2>&1; then
        kind="dnf"; suffix=".noarch.rpm"
    elif command -v pacman >/dev/null 2>&1; then
        kind="pacman"; suffix="-any.pkg.tar.zst"
    elif command -v apk >/dev/null 2>&1; then
        kind="apk"; suffix="_noarch.apk"
    else
        say "nenhum gerenciador de pacotes conhecido; instale com pipx:"
        echo "    pipx install git+https://github.com/$REPO"
        exit 1
    fi

    tmp="$(mktemp -d)"
    trap 'rm -rf "$tmp"' EXIT
    if [ -n "${CODAR_PKG:-}" ]; then
        pkg="$CODAR_PKG"
    else
        command -v curl >/dev/null 2>&1 || fail "precisa do curl"
        if [ -n "${CODAR_VERSION:-}" ]; then
            api="https://api.github.com/repos/$REPO/releases/tags/v$CODAR_VERSION"
        else
            api="https://api.github.com/repos/$REPO/releases/latest"
        fi
        say "procurando a versão em github.com/$REPO"
        url="$(curl -fsSL "$api" | grep -o '"browser_download_url": *"[^"]*' | sed 's/.*"//' |
            grep -- "$suffix\$" | head -n 1)" || true
        [ -n "$url" ] || fail "não achei um pacote *$suffix na versão publicada"
        pkg="$tmp/$(basename "$url")"
        say "baixando $(basename "$url")"
        curl -fsSL -o "$pkg" "$url"
    fi
    case "$pkg" in /*) ;; *) pkg="$(pwd)/$pkg" ;; esac

    say "instalando com $kind (pode pedir sua senha)"
    case "$kind" in
        deb) $sudo apt-get install -y "$pkg" ;;
        zypper) $sudo zypper --non-interactive install --allow-unsigned-rpm "$pkg" ;;
        dnf) $sudo dnf install -y "$pkg" ;;
        pacman) $sudo pacman -U --noconfirm "$pkg" ;;
        apk) $sudo apk add --allow-untrusted "$pkg" ;;
    esac

    say "pronto: $(codar --version)"
    cat <<'EOF'

  Próximos passos:
    codar run "x é igual a 10"     o compilador já funciona, sem nada extra
    codar extras install           Studio (IDE no terminal) e IA local, só no seu usuário
    codar init                     configuração e modelo de IA (~1,1 GB)
    codar studio .                 abre a IDE no terminal

  No Neovim: require("codar").setup() no seu init.lua. Ajuda: man codar
EOF
}

main "$@"
