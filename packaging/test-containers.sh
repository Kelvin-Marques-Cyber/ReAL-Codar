#!/bin/sh
# Instala os pacotes de dist/ em contêineres limpos de cada distro, usa o codar e desinstala.
#   packaging/test-containers.sh                 # todas
#   packaging/test-containers.sh debian:12 alpine:latest
# Requer docker (ou DOCKER=podman). Os contêineres são descartados no fim (--rm). Com SELinux, o rótulo
# dos volumes é desligado só nesses contêineres (label=disable), sem reetiquetar os arquivos do projeto.
set -u
root="$(cd "$(dirname "$0")/.." && pwd)"
docker="${DOCKER:-docker}"
images="${*:-debian:12 ubuntu:22.04 ubuntu:24.04 fedora:latest opensuse/tumbleweed opensuse/leap:15.6 alpine:latest archlinux:latest}"
deb="$(ls "$root"/dist/codar_*_all.deb | tail -1)"
rpm="$(ls "$root"/dist/codar-*.noarch.rpm | tail -1)"
apk="$(ls "$root"/dist/codar_*_noarch.apk | tail -1)"
arch="$(ls "$root"/dist/codar-*-any.pkg.tar.zst | tail -1)"

mkdir -p "$root/build"
cat > "$root/build/container-check.sh" <<'CHECK'
set -eu
fail() { echo "FALHA: $*"; exit 1; }
codar --version
out="$(codar run --local -l go "se total maior que 100 imprimir 'caro'")"
echo "$out" | grep -q 'if total > 100 {' || fail "compilador: $out"
codar run --local "criar uma calculadora" | grep -q "def calcular" || fail "banco de padrões"
codar start >/dev/null || fail "codar start"
r="$(codar run -l py "x é igual a 10")"
[ "$r" = "x = 10" ] || fail "daemon: $r"
printf 'sort -u nomes.txt > nomes.txt\n' > /tmp/t.sh
codar audit --json /tmp/t.sh | grep -q SH012 || fail "auditoria"
codar stop >/dev/null
codar extras | grep -q "codar extras install" || fail "dica dos extras"
test -f /usr/share/nvim/site/pack/codar/start/codar/plugin/codar.lua || fail "plugin do Neovim"
test -n "$(ls /usr/share/vim/*/plugin/codar.vim 2>/dev/null)" || fail "plugin do Vim"
# o manual pelo índice do pacote: imagens Docker de Ubuntu e Arch descartam /usr/share/man de propósito
eval "$LIST" | grep -q "/usr/share/man/man1/codar.1.gz" || fail "manual no pacote"
ls /usr/lib/codar/codar/__pycache__/*.pyc >/dev/null 2>&1 || fail "pyc da instalação"
echo "uso OK"
CHECK

status=0
for img in $images; do
    case "$img" in
        debian*|ubuntu*) pkg="$deb"
            install="apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq /pkg/$(basename "$deb") >/dev/null"
            remove="apt-get remove -y -qq codar >/dev/null"; list="dpkg -L codar" ;;
        fedora*) pkg="$rpm"
            install="dnf install -y -q /pkg/$(basename "$rpm") >/dev/null"
            remove="dnf remove -y -q codar >/dev/null"; list="rpm -ql codar" ;;
        opensuse*) pkg="$rpm"
            install="zypper -n -q in --allow-unsigned-rpm /pkg/$(basename "$rpm") >/dev/null"
            remove="zypper -n -q rm codar >/dev/null"; list="rpm -ql codar" ;;
        alpine*) pkg="$apk"
            install="apk add -q --allow-untrusted /pkg/$(basename "$apk")"
            remove="apk del -q codar"; list="apk info -L codar" ;;
        archlinux*) pkg="$arch"
            install="pacman -Sy --noconfirm >/dev/null && pacman -U --noconfirm /pkg/$(basename "$arch") >/dev/null"
            remove="pacman -R --noconfirm codar >/dev/null"; list="pacman -Ql codar" ;;
        *) echo "$img: distro desconhecida"; continue ;;
    esac
    printf '%-22s ' "$img"
    if "$docker" run --rm --security-opt label=disable -v "$root/dist:/pkg:ro" -v "$root/build/container-check.sh:/check.sh:ro" -e LIST="$list" "$img" sh -c "
        $install || { echo 'FALHA: instalação'; exit 1; }
        sh /check.sh || exit 1
        $remove || { echo 'FALHA: remoção'; exit 1; }
        if [ -e /usr/lib/codar ] || [ -e /usr/bin/codar ]; then echo 'FALHA: sobrou arquivo depois da remoção'; exit 1; fi
        echo 'removido OK'" > "$root/build/container-$(echo "$img" | tr '/:' '__').log" 2>&1; then
        echo "OK  ($(grep -m1 '^codar ' "$root/build/container-$(echo "$img" | tr '/:' '__').log"))"
    else
        echo "FALHOU"; tail -5 "$root/build/container-$(echo "$img" | tr '/:' '__').log" | sed 's/^/    /'; status=1
    fi
done
exit $status
