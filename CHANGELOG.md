# Histórico de mudanças

O formato segue o [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e as versões seguem o [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Não publicado]

## [0.1.1] - 2026-10-09

### Correções de atualização
- A versão Python passa a ter uma única fonte: `codar.__version__`. A wheel e o sdist usam esse valor.
- Versões de VS Code, PowerShell, RPM, Debian e manual sincronizadas; CI, build e Release conferem divergências.
- `packaging/install.sh --pipx` instala ou atualiza `main` com Studio, mesmo quando a versão declarada não mudou.
- O instalador de pacotes informa quando não consegue obter uma Release e avisa se outro `codar` tem prioridade no PATH.
- `codar version --verbose` e `--json` identificam Python, código, origem e commit (quando disponível).
- `doctor` e `status` avisam quando o daemon usa outra versão, instalação ou commit. `restart` não informa sucesso se a parada falhar.
- README distingue `main` de Releases, explica a atualização com pipx e a reinstalação separada da extensão do VS Code.

### Recursos incorporados desde 0.1.0
- Prévia no celular por QR Code: F4 no Studio e `codar servir`, incluindo proxy para servidor de desenvolvimento.
- Explorer, abas, terminais integrados, execução com F5, modo de estudo com F7 e explicação de erros.

Esta seção descreve a versão do código; os pacotes binários dependem da publicação de uma Release.

## [0.1.0] - 2026-10-08

Primeira versão pública.

### Tradução
- Compilador de pseudocódigo em português e inglês (sem IA, menos de 1 ms):
  - atribuições, condições, laços, impressão e funções;
  - expressões como "o tamanho de pedidos", "a média entre x e y" e "o dobro de preço";
  - saída para 14 linguagens.
- Abreviações HTML e CSS no estilo Emmet (`ul>li.item$*3`, `form:post>input:email+btn:s`, `df+jcc+aic`), com JSX em `.jsx` e `.tsx`.
- Banco com 101 padrões testados, entre eles uma calculadora com tratamento de erros em 9 linguagens, Dijkstra, CPF e o novo CNPJ alfanumérico, Pix copia e cola, programas de linha de comando com subcomandos, gravação atômica e leitura de arquivos grandes, CI e Dockerfile.
- IA local (Qwen2.5-Coder 1.5B) em modo literal:
  - traduz só o que a linha diz e usa o código acima como contexto;
  - remove imports inúteis e dados de exemplo inventados.
- Pré-aquecimento das linguagens mais usadas (`warm_langs`), cedendo a vez aos pedidos.

### Terminal
- Studio, IDE no terminal:
  - **editor:** tradução por espaço+Enter, Ctrl+Enter e Ctrl+G; autocompletar; Tab para expandir abreviações;
  - **interface:** ajuda no F1, dicas conforme o contexto, auditoria e consultor de projeto.
- Plugins para Neovim (libuv, sem subprocesso) e Vim 8+, com os mesmos atalhos.
- Completar com Tab para bash, zsh e fish (`codar completion`), incluído no `codar shell-init`.
- Módulo PowerShell com pipeline, `Ctrl+Enter`/`Ctrl+G` no PSReadLine e atalho global no Windows.

### Qualidade e segurança
- Auditoria estática com cerca de 140 regras: segredos, injeção de SQL e comando de shell que apaga o próprio arquivo (`sort -u a > a`), entre outras.
- Consultor de projeto com opções aplicáveis (npm → pnpm ou Bun, Ruff, pytest, PSScriptAnalyzer…).

### Memória
- Teto de 3 GB com vigia do daemon:
  - 80% do teto: limpa caches;
  - 92%: descarrega o modelo;
  - 15 minutos ocioso: descarrega o modelo.
- `use_mmap = false` e cache compacto de prefixos: o modelo padrão fica em ~1,3 GB.

### Distribuição
- Pacotes `.deb`, `.rpm`, `.apk` e Arch, testados em contêineres de 8 distros:
  - manual, completar com Tab, plugins de editor e serviço do systemd incluídos;
  - extras do PyPI num ambiente virtual do usuário (`codar extras install`).
- Instalador de uma linha (`packaging/install.sh`).
- Extensão do VS Code.
