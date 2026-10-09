#!/bin/sh
# Remove os .pyc gerados na instalação (o gerenciador de pacotes não sabe deles). Numa atualização não faz nada: o
# postinstall da versão nova recompila, e no rpm este script da versão antiga roda depois dele.
case "${1:-}" in
    upgrade | failed-upgrade) exit 0 ;;  # deb (prerm)
    [1-9] | [1-9][0-9]) exit 0 ;;        # rpm (%preun): 1 ou mais = ainda fica uma versão instalada
esac
# sem find: imagens mínimas (openSUSE Tumbleweed, por exemplo) não têm findutils
rm -rf /usr/lib/codar/codar/__pycache__ /usr/lib/codar/codar/*/__pycache__ /usr/lib/codar/codar/*/*/__pycache__ \
    /usr/lib/codar/codar/*/*/*/__pycache__ 2>/dev/null
exit 0
