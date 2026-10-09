# Codar para VS Code

Pseudocódigo e intenções em português ou inglês viram código, 100% offline. O daemon `codar` resolve em três estágios:
compilador determinístico (≈1 ms), banco de padrões verificados (≈3 ms) e um modelo local (≤3 GB de RAM).

| Ação | Atalho |
|---|---|
| Traduzir a linha atual | `Ctrl+Enter` numa linha que parece frase, ou `Ctrl+Alt+Enter` em qualquer linha (macOS: `Cmd`) |
| Traduzir pseudocódigo multilinha selecionado | selecione e `Ctrl+Enter` (ou `Ctrl+Alt+Enter`) |
| Espaço + Enter no fim de uma frase | traduz a linha em vez de quebrar linha |
| Mission Control (telemetria, consultor de projeto) | `Ctrl+Alt+M` ou clique em "codar" na barra de status |

Comandos (`Ctrl+Shift+P` → "Codar"): auditar arquivo, consultor de projeto, histórico, salvar seleção como padrão,
abrir o Studio no terminal e reiniciar o daemon.

Fora das linhas que parecem frase, o `Ctrl+Enter` mantém o comportamento padrão do VS Code (inserir linha abaixo).

Requisito: a CLI `codar` instalada (pacote do sistema, `pipx install` ou `pip install -e .` no repositório). Se ela não
estiver no PATH, aponte `codar.executable` para o caminho completo (ex.: `~/ReAL-Codar/.venv/bin/codar`).

Instalação: `code --install-extension codar.vsix --force`. Quando houver uma Release publicada com a extensão,
baixe o arquivo nela; um pacote do sistema que inclua a extensão instala o arquivo em `/usr/share/codar/vscode/codar.vsix`.

Para acompanhar a branch `main`, atualize seu checkout e rode em `clients/vscode`:

```bash
npm ci
npm run compile
npm run package
code --install-extension codar.vsix --force
```

Recarregue a janela. Atualizar a CLI com pipx não reinstala a extensão. Para evitar outra CLI no PATH, configure
`codar.executable` com o caminho absoluto do executável desejado. `codar version --verbose` mostra a revisão da CLI.
