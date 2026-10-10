"""Arquivos citados em pedidos: resolução limitada ao projeto, sem escolher homônimos arbitrariamente."""

import re
from pathlib import Path

from codar import langs
from codar.project import Project, safe_path
from codar.textutil import fold


class AmbiguousReference(ValueError):
    def __init__(self, name: str, choices: list[str]):
        super().__init__(f"Mais de um arquivo corresponde a {name}")
        self.name, self.choices = name, choices


def uses_existing_code(intent: str) -> bool:
    return bool(re.search(r"\b(?:a partir|com base|basead\w*|diante|usando (?:o|meu|este)|"
                          r"(?:meu|meus|este|estes|esse|seu|neste|nesse|existing|current) (?:codigo|arquiv\w*|code|file\w*)|"
                          r"arquivo (?:aberto|atual|da pasta)|(?:in|from|based on) (?:this|the|my|existing) (?:file|code))\b",
                          fold(intent)))


def referenced_files(root: Path, intent: str) -> list[str]:
    project = Project.load(root)
    files = project.files()
    extensions = sorted({ext.lstrip(".") for lang in langs.LANGS.values() for ext in lang.exts}, key=len, reverse=True)
    suffix = r"\.(?:" + "|".join(map(re.escape, extensions)) + r")"
    quoted = re.findall(r"[`\"']([^`\"'\n]+" + suffix + r")[`\"']", intent, re.I)
    remaining = re.sub(r"[`\"'][^`\"'\n]+" + suffix + r"[`\"']", "", intent, flags=re.I)
    names = quoted + re.findall(r"(?<![\w/\\])((?:\.{0,2}/)?[\w.\-/]+" + suffix + r")(?!\w|\.\w)", remaining, re.I)
    out = []
    for name in dict.fromkeys(names):
        # Não lê caminhos fora do projeto, links, arquivos excluídos ou segredos.
        safe_path(project.root, name)
        if not project.allowed(name):
            raise ValueError(f"arquivo excluído do contexto: {name}")
        choices = [name] if name in files else [f for f in files if Path(f).name == name]
        if not choices:
            raise ValueError(f"não achei {name} no projeto; Ctrl+O busca arquivos")
        if len(choices) > 1:
            raise AmbiguousReference(name, choices)
        if choices[0] not in out:
            out.append(choices[0])
    if len(out) > 8:
        raise ValueError("cite no máximo oito arquivos por pedido")
    return out
