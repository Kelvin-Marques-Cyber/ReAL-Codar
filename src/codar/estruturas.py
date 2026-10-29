"""Estrutura automática de projetos: pastas e arquivos iniciais de um modelo, sem sobrescrever nada.

Os modelos vêm dos plugins (`estruturas.toml`). `plano` mostra o que será criado e o que já existe; `aplicar` cria
somente o que falta, dentro da pasta do projeto, recusando caminhos que saiam dela ou passem por links simbólicos.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from codar.textutil import fold

_PEDIDO = re.compile(r"^(?:por favor[, ]+)?(?:crie|criar|cria|gere|gerar|monte|montar|prepare|preparar|estruture|"
                     r"estruturar|create|generate|scaffold|setup|set\s+up)\s+(?:(?:a|uma|o|the|an?)\s+)?"
                     r"(?:estrutura|esqueleto|scaffold|structure|skeleton|layout)\s+(?:(?:de|do|da|para|for|of)\s+)?"
                     r"(?:(?:um|uma|o|a|the|an?)\s+)?(?:(?:projeto|project|app|aplicacao|aplicativo)\s+)?(?P<tipo>.+)$")


@dataclass(frozen=True)
class Item:
    caminho: str
    tipo: str  # "pasta" | "arquivo"
    conteudo: str = ""
    existe: bool = False


def nomes(raiz: Path, nome: str | None = None) -> tuple[str, str]:
    """(nome do projeto, pacote): 'Minha Loja' -> ('minha-loja', 'minha_loja')."""
    base = re.sub(r"[^a-z0-9]+", "-", fold(nome or Path(raiz).resolve().name)).strip("-") or "projeto"
    pacote = base.replace("-", "_")
    return base, ("p_" + pacote if pacote[0].isdigit() else pacote)


def _preencher(texto: str, nome: str, pacote: str) -> str:
    return texto.replace("{{nome}}", nome).replace("{{pacote}}", pacote)


def pedido(texto: str) -> str | None:
    """O tipo de projeto de 'crie a estrutura de um projeto full stack typescript', ou None."""
    m = _PEDIDO.match(fold(texto.strip().rstrip(".")))
    return m["tipo"].strip() if m else None


_VAZIAS = frozenset("""de da do das dos um uma o a os as e em no na para com sem projeto projetos project app
aplicativo aplicacao of for the an and with""".split())


def buscar(estruturas: list, consulta: str) -> list:
    """Modelos em ordem de relevância para a descrição ('full stack ts', 'api python', 'latex')."""
    termos = set(re.findall(r"[a-z0-9+#]+", fold(consulta))) - _VAZIAS
    termos = {"typescript" if t == "ts" else "javascript" if t == "js" else t for t in termos}
    pontuados = []
    for e in estruturas:
        palavras = set(re.findall(r"[a-z0-9+#]+", fold(f"{e.id} {e.titulo} {e.palavras}"))) - _VAZIAS
        palavras |= {p.replace("-", "") for p in palavras}
        acertos = len(termos & palavras)
        if acertos:
            pontuados.append((acertos, e))
    pontuados.sort(key=lambda par: -par[0])
    return [e for _, e in pontuados]


def plano(raiz: Path, estrutura, nome: str | None = None) -> list[Item]:
    from codar.project import safe_path

    raiz = Path(raiz).resolve()
    nome_projeto, pacote = nomes(raiz, nome)
    itens: dict[str, Item] = {}
    caminhos = [(_preencher(p, nome_projeto, pacote), "pasta", "") for p in estrutura.pastas]
    caminhos += [(_preencher(c, nome_projeto, pacote), "arquivo", _preencher(t, nome_projeto, pacote))
                 for c, t in estrutura.arquivos.items()]
    for caminho, tipo, conteudo in caminhos:
        partes = caminho.split("/")
        for i in range(1, len(partes) if tipo == "arquivo" else len(partes) + 1):  # pastas intermediárias
            pasta = "/".join(partes[:i])
            if pasta not in itens:
                alvo = safe_path(raiz, pasta)
                itens[pasta] = Item(pasta, "pasta", existe=alvo.exists())
        if tipo == "arquivo":
            alvo = safe_path(raiz, caminho)
            itens[caminho] = Item(caminho, "arquivo", conteudo, existe=alvo.exists())
    return list(itens.values())


def aplicar(raiz: Path, itens: list[Item]) -> tuple[list[str], list[str]]:
    """(criados, mantidos). Arquivos existentes nunca são reescritos; um arquivo no lugar de uma pasta é um erro."""
    from codar.project import safe_path

    raiz = Path(raiz).resolve()
    criados, mantidos = [], []
    for item in itens:
        alvo = safe_path(raiz, item.caminho)  # confere de novo: o disco pode ter mudado desde a prévia
        if item.tipo == "pasta":
            if alvo.exists() and not alvo.is_dir():
                raise ValueError(f"{item.caminho} existe e não é uma pasta")
            if not alvo.exists():
                alvo.mkdir()
                criados.append(item.caminho + "/")
            continue
        try:
            with alvo.open("x", encoding="utf-8", newline="\n") as arquivo:
                arquivo.write(item.conteudo)
            criados.append(item.caminho)
        except FileExistsError:
            mantidos.append(item.caminho)
    return criados, mantidos
