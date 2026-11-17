"""Serviços de IDE para o Studio: servidores de linguagem (LSP), depurador (DAP) e Git.

Cada serviço fala com uma ferramenta externa já instalada (pylsp, clangd, debugpy, gdb, git), por processos sem shell.
Nada é baixado nem instalado aqui; quando a ferramenta falta, o Studio explica como prepará-la.
"""
