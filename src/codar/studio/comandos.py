"""Pedidos de arquivo na barra de intenção: "crie o arquivo main.py", "crie as pastas src e tests", "crie um arquivo
python chamado app", "abra conta.py". O que não for pedido de arquivo continua virando código."""

from __future__ import annotations

import re
from dataclasses import dataclass

from codar import langs

_NOME = r"[\w.@/-]+"
_CRIAR = re.compile(
    r"^\s*(?:cri(?:e|ar|a)|fa[cç]a|fazer|gere|gerar|adicion(?:e|ar)|nov[oa]|make|create|new)\s+"
    r"(?:(?:um|uma|o|a|os|as|the|a)\s+)?(?P<tipo>arquivo|pasta|diret[oó]rio|folder|file|directory)s?\s+"
    r"(?:(?P<lang>[\w+#]+)\s+)??(?:(?:chamad[oa]s?|com o nome(?: de)?|de nome|named|called)\s+)?"
    rf"(?P<nomes>{_NOME}(?:\s*(?:,|\be\b|\band\b)\s*{_NOME})*)\s*$", re.I)
_ABRIR = re.compile(rf"^\s*(?:abr(?:a|ir|e)|open)\s+(?:(?:o|a|the)\s+)?(?:arquivo\s+|file\s+)?(?P<nome>{_NOME})\s*$",
                    re.I)


@dataclass
class PedidoArquivo:
    acao: str  # "criar_arquivo" | "criar_pasta" | "abrir"
    caminhos: list[str]


def interpretar(texto: str) -> PedidoArquivo | None:
    if m := _CRIAR.match(texto):
        pasta = m.group("tipo").lower() in ("pasta", "diretório", "diretorio", "folder", "directory")
        lang = langs.try_resolve(m.group("lang")) if m.group("lang") else None
        if m.group("lang") and lang is None:  # "crie o arquivo de testes" não é um pedido de arquivo com linguagem
            return None
        nomes = [n.strip() for n in re.split(r"\s*(?:,|\be\b|\band\b)\s*", m.group("nomes")) if n.strip()]
        if not pasta and lang is not None and lang.exts:
            nomes = [n if "." in n.rsplit("/", 1)[-1] else n + lang.exts[0] for n in nomes]
        return PedidoArquivo("criar_pasta" if pasta else "criar_arquivo", nomes)
    if m := _ABRIR.match(texto):
        return PedidoArquivo("abrir", [m.group("nome")])
    return None
