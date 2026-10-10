# Codar para VS Code

Pseudocódigo e intenções em português ou inglês viram código com um motor local. O daemon `codar` tenta o compilador determinístico, o banco de padrões e, quando necessário, um modelo de IA opcional. Tradução e auditoria funcionam offline depois da instalação; downloads usam a rede. O orçamento padrão do daemon é 3072 MiB, configurável, e não inclui a memória do VS Code nem dos programas do projeto.

## Instalar e começar

1. Instale/atualize a CLI conforme o [README principal](../../README.md#instalação). Confirme no terminal: `codar version --verbose` e `codar doctor`. CLI e extensão devem usar o mesmo ambiente onde os arquivos estão acessíveis.
2. Em um checkout atualizado do repositório, compile e instale a extensão:

```bash
cd clients/vscode
npm ci
npm run compile
npm run package
code --install-extension codar.vsix --force
```

3. Recarregue a janela, abra uma pasta de projeto e um arquivo `.py`, `.dart` ou `.ps1`. Digite `x é igual a 10` e pressione **Ctrl+Alt+Enter**: a linha será traduzida. Esse exemplo usa o compilador e funciona sem modelo de IA.
4. Para corrigir código existente, **selecione o trecho**, abra **Ctrl+Shift+P → Codar: Gerar código a partir de uma intenção…** e escreva a correção. Revise o diff, escolha os trechos e clique em **Aplicar**. Essa edição exige o extra `llm` e um modelo local instalado; não usa um serviço de IA externo.

A CLI não instala automaticamente a extensão. Se o VS Code abrir pelo menu do sistema e não encontrar `codar`, configure **Settings → Codar: Executable** com o caminho absoluto da CLI. No Linux com pipx, por exemplo: `/home/kelvin/.local/bin/codar`, substituindo pelo seu usuário. `Codar: Reiniciar daemon` reinicia o motor, e **View → Output → Codar** mostra os erros.

## Revisão, projetos e histórico

- Pedidos de correção com uma seleção substituem somente o alvo; pedidos explícitos sem seleção editam o arquivo aberto inteiro. Sem uma intenção de edição, geração insere código abaixo da linha atual.
- A prévia é controlada por `codar.editing.preview` (padrão `true`). Resposta cortada, aba fechada ou documento modificado durante a geração/revisão preserva o código original. **Ctrl+Z** desfaz corpo e imports juntos.
- **Codar: Histórico de edições e recuperação** guarda os originais de arquivos nomeados nos dados privados da CLI e permite revisar uma restauração. Buffers sem nome têm desfazer normal, sem histórico persistente por arquivo.
- **Codar: Editar vários arquivos…** escolhe até oito arquivos salvos, prepara uma proposta e abre suas comparações. Depois da escolha dos trechos, **Aplicar aos arquivos** escreve no disco e guarda os originais. Arquivos com alterações não salvas precisam ser salvos antes.
- **Codar: Verificar projeto** oferece sintaxe, testes ou analisador. Os dois últimos executam comandos do projeto somente quando escolhidos; confira `codar.toml`.
- **Codar: Gerenciar plugins** abre a CLI para instalar, atualizar, desativar, remover ou restaurar um pacote. Operações e diagnósticos completos também estão em `codar plugins --help`.

Convenções, skills e comandos são os mesmos da CLI. `codar project init` cria um `codar.toml` de exemplo. Dart/Flutter precisam de seus SDKs para execução e análise; a extensão não substitui o plugin Dart/Flutter do editor nem um servidor de linguagem.

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
