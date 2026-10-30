"""Estudo das demais linguagens: uma ficha por linguagem, com o mesmo padrão das linguagens principais.

Cada ficha traz a fonte oficial, o guia (título, explicação e exemplo), como preparar o ambiente offline, as aulas em
ordem de nível (a última é o projeto de revisão) e a referência de construções que o painel ESTUDO reconhece na linha
do cursor. Os exemplos são escritos na própria linguagem e conferidos com a ferramenta oficial quando ela está
instalada (tests/test_estudo_linguagens.py); nada é traduzido automaticamente de outra linguagem.

Para acrescentar uma linguagem: registre-a em codar/langs.py, escreva a ficha num módulo deste pacote e
acrescente o validador dela em tests/test_estudo_linguagens.py.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Ficha:
    fonte: str
    guia: tuple[str, str, str]  # título, explicação, exemplo
    ambiente: str
    # (chave, título, nível, módulo, texto, pratique, código, erro comum, confira); a última é a chave "projeto"
    aulas: tuple[tuple[str, str, str, str, str, str, str, str, str], ...]
    # (chave, padrões da linha, título, explicação, exemplo, erro comum)
    referencia: tuple[tuple[str, tuple[str, ...], str, str, str, str], ...]


def _reunir() -> dict[str, Ficha]:
    from codar.estudo.linguagens import documentos, hardware

    fichas: dict[str, Ficha] = {}
    for modulo in (documentos, hardware):
        repetidas = fichas.keys() & modulo.FICHAS.keys()
        if repetidas:
            raise ValueError(f"ficha repetida: {sorted(repetidas)}")
        fichas.update(modulo.FICHAS)
    return fichas


FICHAS = _reunir()
