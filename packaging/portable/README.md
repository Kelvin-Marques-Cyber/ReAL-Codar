# Codar @VERSION@ — @PLATFORM@

Este arquivo inclui a wheel da CLI, um instalador Python, a licença e, quando compilada, a extensão do VS Code. Não inclui um runtime Python, modelo de IA ou SDKs. Requer **Python 3.10+ e pipx**. Os pacotes são independentes de arquitetura; extensões opcionais precisam de wheels compatíveis com seu sistema.

## Windows

Instale Python pelo site oficial e, no PowerShell, instale pipx:

```powershell
py -3 -m pip install --user pipx
```

Extraia o ZIP e execute dentro da pasta extraída:

```powershell
py -3 .\install.py
# alternativa: .\install.ps1
```

A execução direta do Python funciona mesmo quando a política do PowerShell bloqueia scripts. O módulo de integração com PowerShell está em `powershell/Codar`; sua ativação é opcional com `Import-Module ./powershell/Codar/Codar.psd1`.

## macOS

Instale Python 3.10+ e pipx. Se você já usa Homebrew:

```sh
brew install python pipx
```

Extraia o TAR.GZ, entre na pasta extraída e execute:

```sh
sh install.sh
```

## Instalação e atualização

O instalador confere os arquivos incluídos, reinstala esta versão pelo pipx e verifica o executável resultante. Studio e gramáticas de edição são instalados por padrão; use `--core` para instalar só a CLI. Dependências opcionais podem precisar de acesso ao índice de pacotes. Use `--verify-only` para conferir os arquivos sem instalar e compare o arquivo baixado com `SHA256SUMS` publicado na Release.

Abra um terminal novo e confira:

```sh
codar --version
codar restart
codar run "x é igual a 10"
```

O instalador mostra o caminho completo do executável. Se outra instalação aparecer primeiro no PATH, use esse caminho. Para habilitar IA local: `codar extras install llm` e `codar init` (baixa um modelo). Modelos e configuração existentes ficam na pasta de dados do usuário.

Se `codar.vsix` estiver incluído, instale a extensão separadamente:

```sh
code --install-extension codar.vsix --force
```

Abra uma pasta e um arquivo; **Ctrl+Alt+Enter** traduz a linha (macOS: **Cmd+Alt+Enter**). Para editar código, selecione o trecho e use **Codar: Gerar código a partir de uma intenção…** na paleta. Edições por IA precisam do modelo local.

Confira nas notas da Release as verificações efetivamente executadas em cada plataforma. Estes arquivos não são instaladores autônomos EXE/DMG.
