#!/bin/sh
# Remove os .pyc gerados na instalação (o gerenciador de pacotes não sabe deles). Sem find: imagens mínimas
# (openSUSE Tumbleweed, por exemplo) não têm findutils.
rm -rf /usr/lib/codar/codar/__pycache__ /usr/lib/codar/codar/*/__pycache__ /usr/lib/codar/codar/*/*/__pycache__ \
    /usr/lib/codar/codar/*/*/*/__pycache__ 2>/dev/null
exit 0
