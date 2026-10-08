"""Gera a configuração do nfpm para o Alpine a partir de packaging/nfpm.yaml.

O apk (2 e 3) recusa dois detalhes que deb, rpm e Arch aceitam: descrição com mais de uma linha no .PKGINFO e as
entradas de diretório que o nfpm cria em `type: tree`. Aqui a descrição vira uma linha só e cada árvore vira a lista
explícita dos seus arquivos.

    python3 packaging/apk_config.py packaging/nfpm.yaml > build/nfpm-apk.yaml
"""

import re
import sys
from pathlib import Path


def main(path: str) -> str:
    text = Path(path).read_text(encoding="utf-8")
    # descrição: só a primeira linha do bloco "description: |-"
    text = re.sub(r"^description: \|-\n {2}(.+)\n(?: {2}.*\n)*", lambda m: f'description: "{m.group(1)}"\n', text,
                  flags=re.M)
    out = []
    for block in re.split(r"(?=^  - src: )", text, flags=re.M):
        m = re.match(r"  - src: (\S+)\n    dst: (\S+)\n    type: tree\n", block)
        if not m:
            out.append(block)
            continue
        src, dst = Path(m.group(1)), m.group(2).rstrip("/")
        files = sorted(p for p in src.rglob("*") if p.is_file())
        out.extend(f"  - src: ./{p.as_posix()}\n    dst: {dst}/{p.relative_to(src).as_posix()}\n" for p in files)
        out.append(block[m.end():])
    return "".join(out)


if __name__ == "__main__":
    sys.stdout.write(main(sys.argv[1]))
