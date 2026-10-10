# Histórico de mudanças

O formato segue o [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e as versões seguem o [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Não publicado]

## [0.3.0] - 2026-10-09

### Projetos e CLI
- `codar project init|info|context|doctor|run` configura convenções, skills, comandos e requisitos de versões de SDKs por projeto.
- `codar edit` propõe alterações em até oito arquivos, usando referências do projeto e as alterações já propostas como contexto.
- `codar edits list|show|apply|restore|recover` oferece comparação, escolha de trechos, histórico durável e recuperação de aplicações interrompidas.
- Snapshots, diário e verificação do texto atual protegem contra respostas atrasadas; falhas ao trocar arquivos tentam restaurar os originais sem apagar alterações externas.
- `codar check` verifica sintaxe; `--tests`, `--analyze` e `--format` executam comandos explícitos, com timeout e saída limitada.
- Validação Python/JSON/TOML, parsers nativos de Dart e PowerShell e gramáticas opcionais. Validador ausente é informado como não verificado.
- Geração reserva espaço para a substituição inteira; arquivos grandes usam funções completas, sem cortar instruções. Erros de sintaxe recebem tentativas limitadas de reparo.

### Plugins e editores
- Plugins de pasta ou Git HTTPS registram origem e revisão; atualização, remoção e restauração guardam cópias privadas de recuperação.
- Compatibilidade de Codar e dependências entre plugins, rejeição de ciclos, manifesto estrito, limites de tamanho e isolamento de pacotes inválidos.
- Studio e VS Code mostram prévias com escolha de trechos, histórico de edições, edição de vários arquivos, verificações e gestão de plugins.
- README com fluxo principal da CLI e guia de uso da extensão; seu número de versão passa a ser conferido pelo guard de publicação.
- Suíte de comportamento de edição Python, testes de falhas e cancelamento, integração do cliente VS Code com daemon real e CI de edição para Windows/macOS.

## [0.2.0] - 2026-10-09

### Edição de código
- A barra de intenção no Studio e no VS Code substitui a seleção. Pedidos explícitos de correção, refatoração ou complemento sem seleção editam o arquivo aberto.
- O motor recebe código antes/depois e o trecho a substituir em `mode=edit`, sem recorrer a snippets genéricos. A seleção não é cortada silenciosamente.
- Respostas incompletas, arquivos modificados durante a geração e abas fechadas preservam o código original. Corpo e imports são desfeitos juntos.
- A limpeza de edições preserva o fim do código; imports não entram de novo dentro do corpo com dicas inline. Cache distingue seleção, contexto, caixa e literais.
- Neovim e Vim também preservam o buffer quando a geração é incompleta ou o documento mudou.
- Imports preservam docstrings/future do Python e param/CmdletBinding do PowerShell. Cancelar uma requisição no VS Code impede aplicação tardia e remove os listeners do pedido.

### Dart, Flutter e PowerShell
- F5 reconhece o pubspec mais próximo: executa o aplicativo Flutter por lib/main.dart, testes por flutter test e scripts Dart por dart run.
- Dicas de dependências reconhecem package_config.json, pacotes do projeto e bibliotecas do SDK; comandos pub usam a pasta do projeto, inclusive em projetos aninhados.
- Plugins Flutter e PowerShell acrescentam seis padrões, cinco skills e três regras de auditoria. Imports Dart preservam aliases.
- `codar toolchains list|install|env` detecta e instala SDKs de programação; `--dry-run` mostra o plano. Dart e PowerShell usam downloads oficiais com SHA-256; Flutter usa o repositório oficial estável. Outros runtimes usam o gerenciador do sistema.
- SDKs por usuário ficam disponíveis nos terminais do Studio sem alterar arquivos de inicialização do shell.
- `codar plugins install PASTA` valida e instala plugins locais sem sobrescrever os existentes; `codar skills list|show` permite consultar diretrizes.


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
