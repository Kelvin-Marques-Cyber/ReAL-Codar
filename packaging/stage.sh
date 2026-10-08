#!/bin/sh
# Instala o codar em DESTDIR com o layout dos pacotes de sistema. O layout é definido só aqui: o nfpm
# (packaging/build.sh), o spec RPM, o debian/rules e o PKGBUILD chamam este script.
#
#   packaging/stage.sh DESTDIR [PREFIX]          PREFIX padrão: /usr
#   VIM_DIRS="vimfiles site" packaging/stage.sh  diretórios do Vim em PREFIX/share/vim/ (openSUSE usa "site")
set -eu
dest="${1:?uso: packaging/stage.sh DESTDIR [PREFIX]}"
prefix="${2:-/usr}"
root="$(cd "$(dirname "$0")/.." && pwd)"
d="$dest$prefix"

copy() {  # copy <modo> <origem> <destino>
    install -d "$(dirname "$3")"
    install -m "$1" "$2" "$3"
}

# programa: lançador + código Python (sem caches; os .pyc são gerados na instalação)
copy 0755 "$root/packaging/codar.sh" "$d/bin/codar"
(cd "$root/src" && find codar -type f ! -name '*.pyc' ! -path '*/__pycache__/*') | while IFS= read -r f; do
    copy 0644 "$root/src/$f" "$d/lib/codar/$f"
done

# documentação, licença, manual e serviço do usuário
for f in README.md CHANGELOG.md; do
    [ -f "$root/$f" ] && copy 0644 "$root/$f" "$d/share/doc/codar/$f"
done
for f in "$root"/docs/*.md "$root"/docs/img/*; do
    [ -f "$f" ] && copy 0644 "$f" "$d/share/doc/codar/${f#"$root"/}"
done
copy 0644 "$root/LICENSE" "$d/share/licenses/codar/LICENSE"
install -d "$d/share/man/man1"
gzip -9n -c "$root/packaging/codar.1" > "$d/share/man/man1/codar.1.gz"
chmod 0644 "$d/share/man/man1/codar.1.gz"
copy 0644 "$root/packaging/codar.service" "$d/lib/systemd/user/codar.service"

# completar com Tab no bash, zsh e fish (gerado a partir do parser do próprio CLI)
for sh in bash zsh fish; do
    case "$sh" in
        bash) out="$d/share/bash-completion/completions/codar" ;;
        zsh) out="$d/share/zsh/site-functions/_codar" ;;
        fish) out="$d/share/fish/vendor_completions.d/codar.fish" ;;
    esac
    install -d "$(dirname "$out")"
    # CODAR_HOME vazio: só os plugins do pacote entram (nada da configuração de quem está empacotando)
    home="$(mktemp -d)"
    CODAR_HOME="$home" PYTHONPATH="$root/src" python3 -m codar completion "$sh" > "$out"
    rm -rf "$home"
    chmod 0644 "$out"
done

# editores: o Neovim carrega pack/*/start sozinho; o Vim lê plugin/ e autoload/ do diretório do sistema
nvim="$d/share/nvim/site/pack/codar/start/codar"
copy 0644 "$root/clients/nvim/plugin/codar.lua" "$nvim/plugin/codar.lua"
for f in "$root"/clients/nvim/lua/codar/*.lua; do
    copy 0644 "$f" "$nvim/lua/codar/$(basename "$f")"
done
for v in ${VIM_DIRS:-vimfiles}; do
    copy 0644 "$root/clients/vim/plugin/codar.vim" "$d/share/vim/$v/plugin/codar.vim"
    copy 0644 "$root/clients/vim/autoload/codar.vim" "$d/share/vim/$v/autoload/codar.vim"
done

# PowerShell (Import-Module /usr/share/codar/powershell/Codar) e a extensão do VS Code, se já foi gerada
for f in "$root"/clients/powershell/Codar/*; do
    copy 0644 "$f" "$d/share/codar/powershell/Codar/$(basename "$f")"
done
if [ -f "$root/clients/vscode/codar.vsix" ]; then
    copy 0644 "$root/clients/vscode/codar.vsix" "$d/share/codar/vscode/codar.vsix"
fi
