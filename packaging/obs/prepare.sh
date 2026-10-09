#!/bin/sh
# Monta em build/obs/ os arquivos do pacote "codar" para o Open Build Service, que gera e assina repositórios para
# apt (Debian, Ubuntu), zypper (openSUSE) e dnf (Fedora) a partir do mesmo código-fonte:
#   codar-<versão>.tar.gz   código-fonte do commit atual (git archive)
#   codar.spec              receita RPM (packaging/rpm/codar.spec)
#   codar.dsc + debian.*    receita Debian (packaging/debian/, no formato do debtransform do OBS)
#
# Uso (veja docs/PACKAGING.md):
#   packaging/obs/prepare.sh
#   cd <checkout do osc>/home:<usuário>/codar && cp ~/ReAL-Codar/build/obs/* . && osc addremove && osc commit -m "codar <versão>"
set -eu
root="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$root"
version="$(sed -n 's/^__version__ = "\(.*\)"/\1/p' src/codar/__init__.py)"
debver="$(sed -n '1s/^codar (\([^)]*\)).*/\1/p' packaging/debian/changelog)"
case "$debver" in
    "$version"-*) ;;
    *) echo "packaging/debian/changelog está na versão $debver, mas o código está na $version" >&2; exit 1 ;;
esac
if [ -n "$(git status --porcelain -- src packaging)" ]; then
    echo "aviso: há mudanças sem commit em src/ ou packaging/; o tarball usa só o que está no commit atual" >&2
fi

out=build/obs
rm -rf "$out"
mkdir -p "$out"
git archive --format=tar.gz --prefix="codar-$version/" -o "$out/codar-$version.tar.gz" HEAD
sed "s/^Version:.*/Version:        $version/" packaging/rpm/codar.spec > "$out/codar.spec"
for f in control rules changelog copyright codar.postinst codar.prerm; do
    cp "packaging/debian/$f" "$out/debian.$f"
done
build_depends="$(sed -n 's/^Build-Depends: //p' packaging/debian/control)"
maintainer="$(sed -n 's/^Maintainer: //p' packaging/debian/control)"
cat > "$out/codar.dsc" <<DSC
Format: 1.0
Source: codar
Binary: codar
Architecture: all
Version: $debver
Maintainer: $maintainer
Homepage: https://github.com/Kelvin-Marques-Cyber/ReAL-Codar
Standards-Version: 4.7.0
Build-Depends: $build_depends
DEBTRANSFORM-TAR: codar-$version.tar.gz
DSC
ls -1 "$out"
