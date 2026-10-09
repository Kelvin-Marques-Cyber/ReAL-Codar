#!/bin/sh
# Instalador do CODAR: baixa o pacote da última versão publicada no GitHub e instala com o gerenciador de pacotes do
# sistema (apt, zypper, dnf, pacman ou apk). --pipx instala/atualiza a branch main no usuário.
#
#   curl -fsSL https://raw.githubusercontent.com/Kelvin-Marques-Cyber/ReAL-Codar/main/packaging/install.sh | sh
#
# Variáveis opcionais:
#   CODAR_VERSION=0.1.1   Release específica em vez da última (também aceita v0.1.1)
#   CODAR_PKG=/caminho    instala um pacote já baixado (sem acessar a rede)
set -eu

REPO="Kelvin-Marques-Cyber/ReAL-Codar"

say() { printf '\033[1;38;5;208m▸\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31m✗\033[0m %s\n' "$*" >&2; exit 1; }

install_pipx() {
    [ -z "${CODAR_VERSION:-}${CODAR_PKG:-}" ] || fail "--pipx usa main; não combine com CODAR_VERSION/CODAR_PKG"
    [ "$(id -u)" -ne 0 ] || fail "use --pipx no seu usuário, sem sudo"
    command -v pipx >/dev/null 2>&1 || fail "instale pipx e Git pelo gerenciador da sua distro e tente novamente"
    command -v git >/dev/null 2>&1 || fail "instale o Git para baixar a branch main"
    say "instalando/atualizando main com Studio no ambiente do pipx"
    pipx install --force --pip-args='--no-cache-dir' "codar[studio] @ git+https://github.com/$REPO.git@main"
    bin="$(pipx environment --value PIPX_BIN_DIR)"
    [ -x "$bin/codar" ] || fail "pipx terminou, mas não encontrei $bin/codar"
    "$bin/codar" version --verbose
    say "feche o Studio aberto e execute no seu terminal:"
    printf '  pipx ensurepath --prepend\n  hash -r\n  "%s/codar" restart\n  "%s/codar" doctor\n' "$bin" "$bin"
}

main() {
    case "${1:-}" in
        --pipx) [ "$#" -eq 1 ] || fail "uso: install.sh [--pipx]"; install_pipx; return ;;
        "") ;;
        *) fail "uso: install.sh [--pipx]" ;;
    esac

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
        echo "    pipx install --force 'codar[studio] @ git+https://github.com/$REPO.git@main'"
        exit 1
    fi

    tmp="$(mktemp -d)"
    trap 'rm -rf "$tmp"' EXIT
    if [ -n "${CODAR_PKG:-}" ]; then
        pkg="$CODAR_PKG"
    else
        command -v curl >/dev/null 2>&1 || fail "precisa do curl"
        if [ -n "${CODAR_VERSION:-}" ]; then
            api="https://api.github.com/repos/$REPO/releases/tags/v${CODAR_VERSION#v}"
        else
            api="https://api.github.com/repos/$REPO/releases/latest"
        fi
        say "procurando a versão em github.com/$REPO"
        if ! curl -fsSL -o "$tmp/release.json" "$api"; then
            fail "não consegui consultar a Release (ela pode não existir, ou a API estar indisponível). Para instalar/atualizar main, use este script com --pipx, sem sudo."
        fi
        url="$(grep -o '"browser_download_url": *"[^"]*' "$tmp/release.json" | sed 's/.*"//' |
            grep -- "$suffix\$" | head -n 1)" || true
        [ -n "$url" ] || fail "a Release não contém um pacote *$suffix; para usar main, execute este script com --pipx, sem sudo"
        pkg="$tmp/$(basename "$url")"
        say "baixando $(basename "$url")"
        curl -fsSL -o "$pkg" "$url"
    fi
    case "$pkg" in /*) ;; *) pkg="$(pwd)/$pkg" ;; esac
    [ -f "$pkg" ] || fail "pacote não encontrado: $pkg"

    if [ "$(id -u)" -eq 0 ]; then
        sudo=""
    elif command -v sudo >/dev/null 2>&1; then
        sudo="sudo"
    else
        fail "rode como root ou instale o sudo"
    fi

    say "instalando com $kind (pode pedir sua senha)"
    case "$kind" in
        deb) $sudo apt-get install -y "$pkg" ;;
        zypper) $sudo zypper --non-interactive install --allow-unsigned-rpm "$pkg" ;;
        dnf) $sudo dnf install -y "$pkg" ;;
        pacman) $sudo pacman -U --noconfirm "$pkg" ;;
        apk) $sudo apk add --allow-untrusted "$pkg" ;;
    esac

    say "pacote do sistema instalado: $(/usr/bin/codar --version)"
    active="$(command -v codar || true)"
    if [ -n "$active" ] && [ "$(readlink -f "$active")" != "$(readlink -f /usr/bin/codar)" ]; then
        say "atenção: seu PATH usa $active; este instalador atualizou /usr/bin/codar"
        say "se você usa pipx, atualize essa instalação com --pipx no seu usuário"
    fi
    cat <<'EOF'

  Próximos passos:
    /usr/bin/codar restart         reinicia o daemon com o pacote atualizado; feche e reabra o Studio
    codar run "x é igual a 10"     o compilador já funciona, sem nada extra
    codar extras install           Studio (IDE no terminal) e IA local, só no seu usuário
    codar init                     configuração e modelo de IA (~1,1 GB)
    codar studio .                 abre a IDE no terminal

  No Neovim: require("codar").setup() no seu init.lua. Ajuda: man codar
EOF
}

main "$@"
