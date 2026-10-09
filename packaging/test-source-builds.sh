#!/bin/sh
# Compila o codar a partir do código-fonte em contêineres limpos, como o Open Build Service faz: dpkg-buildpackage
# (packaging/debian) no Debian e no Ubuntu, rpmbuild (packaging/rpm/codar.spec) no Fedora e no openSUSE. Depois
# instala, usa, testa a atualização para uma versão nova (os .pyc precisam continuar lá) e remove.
#   packaging/test-source-builds.sh                       # todas
#   packaging/test-source-builds.sh debian:12 fedora:latest
set -u
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
docker="${DOCKER:-docker}"
images="${*:-debian:12 ubuntu:22.04 ubuntu:24.04 fedora:latest opensuse/tumbleweed opensuse/leap:15.6 opensuse/leap:16.0}"
version="$(sed -n 's/^__version__ = "\(.*\)"/\1/p' src/codar/__init__.py)"
mkdir -p build/src
# o mesmo conteúdo que o git archive daria, mas incluindo mudanças ainda sem commit (para testar antes do commit)
git ls-files -co --exclude-standard | tar -czf "build/src/codar-$version.tar.gz" --transform "s,^,codar-$version/," -T -

cat > build/src/deb.sh <<'DEB'
set -e
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq >/dev/null
apt-get install -y -qq --no-install-recommends build-essential debhelper python3 python3-tomli lintian >/dev/null 2>&1
mkdir -p /b && cd /b && tar xzf /src/codar-*.tar.gz && cd codar-*/
cp -r packaging/debian debian
dpkg-buildpackage -us -uc -b >/b/build.log 2>&1 || { tail -30 /b/build.log; exit 1; }
lintian --suppress-tags initial-upload-closes-no-bugs /b/codar_*.deb 2>/dev/null | grep -E "^[EW]:" && exit 1
apt-get install -y -qq /b/codar_*.deb >/dev/null 2>&1
codar run --local -l go "se total maior que 100 imprimir 'caro'" | grep -q 'if total > 100 {'
ls /usr/lib/codar/codar/__pycache__/*.pyc >/dev/null
apt-get remove -y -qq codar >/dev/null 2>&1
[ ! -e /usr/lib/codar ]
echo "$(. /etc/os-release; echo "$PRETTY_NAME"): compilou, lintian limpo, instalou, removeu"
DEB

cat > build/src/rpm.sh <<'RPM'
set -e
if command -v dnf >/dev/null; then
    dnf install -y -q rpm-build python3 >/dev/null 2>&1
    install() { dnf install -y -q "$1" >/dev/null 2>&1; }
else
    py=python3; grep -q 'VERSION="15' /etc/os-release && py=python311
    zypper -n -q in rpm-build "$py" >/dev/null 2>&1
    install() { zypper -n -q in --allow-unsigned-rpm "$1" >/dev/null 2>&1; }
fi
top=/root/rpmbuild; mkdir -p "$top/SOURCES"
cp /src/codar-*.tar.gz "$top/SOURCES/"
v="$(ls /src/codar-*.tar.gz | sed 's/.*codar-\(.*\)\.tar\.gz/\1/')"
sed "s/^Version:.*/Version:        $v/" /spec/codar.spec > /tmp/codar.spec
rpmbuild --define "_topdir $top" -bb /tmp/codar.spec >/tmp/build.log 2>&1 || { tail -30 /tmp/build.log; exit 1; }
# uma versão maior, para testar a atualização
cd /tmp && tar xzf "$top/SOURCES/codar-$v.tar.gz" && mv "codar-$v" "codar-$v.1" && tar czf "$top/SOURCES/codar-$v.1.tar.gz" "codar-$v.1"
sed "s/^Version:.*/Version:        $v.1/" /spec/codar.spec > /tmp/codar-novo.spec
rpmbuild --define "_topdir $top" -bb /tmp/codar-novo.spec >/tmp/build2.log 2>&1 || { tail -20 /tmp/build2.log; exit 1; }
install "$(ls "$top"/RPMS/noarch/codar-"$v"-*.rpm)"
codar run --local -l go "se total maior que 100 imprimir 'caro'" | grep -q 'if total > 100 {'
rpm -U --quiet "$(ls "$top"/RPMS/noarch/codar-"$v".1-*.rpm)" >/dev/null
ls /usr/lib/codar/codar/__pycache__/*.pyc >/dev/null || { echo "a atualização apagou os .pyc"; exit 1; }
rpm -e codar
[ ! -e /usr/lib/codar ]
echo "$(. /etc/os-release; echo "$PRETTY_NAME"): compilou, instalou, atualizou, removeu"
RPM

status=0
for img in $images; do
    case "$img" in
        debian* | ubuntu*) script=deb.sh ;;
        *) script=rpm.sh ;;
    esac
    printf '%-22s ' "$img"
    log="build/source-$(echo "$img" | tr '/:' '__').log"
    if "$docker" run --rm --security-opt label=disable -v "$root/build/src:/src:ro" -v "$root/packaging/rpm:/spec:ro" \
        "$img" sh "/src/$script" > "$log" 2>&1; then
        tail -1 "$log"
    else
        echo "FALHOU"
        tail -8 "$log" | sed 's/^/    /'
        status=1
    fi
done
exit $status
