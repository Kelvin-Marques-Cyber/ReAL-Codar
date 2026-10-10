# CODAR

**Você escreve a intenção em pseudocódigo. O CODAR escreve o código.**
Um ambiente de programação com foco na CLI, tradução offline, IA local opcional e orçamento de memória configurável (3072 MiB por padrão para o daemon).

![CODAR Studio 0.3.1 com editor, painel de estudo e controles de busca, SDKs e autosave](docs/img/manual/01-studio.png)

```text
x é igual a 10                            →  x = 10
imprima a soma de x e y                   →  Write-Output ($x + $y)                (PowerShell)
quantidade é igual ao tamanho de pedidos  →  const quantidade = pedidos.length;    (JavaScript)
se total maior que 100 imprimir 'caro'    →  if total > 100 {                      (Go)
                                                 fmt.Println("caro")
                                             }
ul>li.item$*3                             →  <ul><li class="item1"></li>…</ul>     (HTML, Tab)
df+jcc+aic                                →  display: flex; justify-content: …     (CSS, Tab)
```

> Projeto em fase alfa: o compilador, o banco de padrões e os clientes de terminal estão testados; espere mudanças.

**Versão do código: 0.3.2.** [Downloads e notas da Release v0.3.2](https://github.com/Kelvin-Marques-Cyber/ReAL-Codar/releases/tag/v0.3.2): pacotes Linux, wheel/sdist, instaladores via Python para Windows/macOS, extensão do VS Code e checksums. A branch `main` recebe as mudanças mais recentes; os comandos abaixo distinguem a instalação de uma versão publicada da instalação de `main`.

## Novidades da 0.3.2

Pedidos de bibliotecas agora geram somente importações, com validação de escopo para todas as linguagens. Nomes explícitos funcionam offline: NumPy, pandas, Requests, FastAPI, PyTorch, React, Express, Axios, Dio e bibliotecas particulares, entre outras. Aliases e símbolos solicitados são preservados. A geração explícita de funcionalidades permanece disponível.

- **Seu próprio código:** `importar função somar de util.py` procura a função nos arquivos reais e gera `from util import somar`. Inclui subpastas, imports relativos em pacotes e layout `src`; funções homônimas exigem a origem.
- **Contexto de bibliotecas:** assinaturas, tipos, docstrings e documentação local entram nas próximas gerações, com catálogo por projeto, versão e conteúdo consultado. A busca segue reexportações Python, tabelas de exports sob demanda e tipos `@types` de bibliotecas JS. Prioriza APIs relacionadas ao pedido e identifica seus arquivos de origem. Referências fornecidas com `--source` funcionam nas 24 linguagens/formatos.
- **Gerenciamento pelo CLI:** `codar libraries` consulta, verifica, remove referências e instala dependências explicitamente no ambiente do projeto, com prévia `--dry-run`. [Guia completo, exemplos e cobertura dos ecossistemas](docs/LIBRARIES.md).

## Novidades da 0.3.1

- **Busca:** Ctrl+F no arquivo e Ctrl+Shift+F no projeto, por nome e conteúdo. A opção **Usar IA local** transforma descrições em palavras-chave visíveis; os resultados vêm dos arquivos existentes.
- **Estudo em todas as linguagens reconhecidas:** exemplos nativos, catálogo com filtro, exercícios, erros comuns, fontes oficiais e registro manual de prática por projeto. Inclui Dart/Flutter, PowerShell, R, Julia, SQL, HTML, CSS, YAML e Dockerfile.
- **Várias versões Python:** instale versões lado a lado, escolha uma para cada projeto e crie ambientes separados. **SDKs** no Studio abre o seletor; F5, dependências e novos comandos do terminal respeitam a escolha.
- **Salvamento automático opcional:** botão **AUTO ON/OFF**, preferência persistente e intervalo configurável. Arquivos sem nome usam Ctrl+S; alterações externas pausam o autosave daquela aba.
- **Mais contexto e controle:** o código antes e depois do cursor participa da tradução. Ctrl+Enter respeita o campo em foco e a seleção exata; arquivos citados no pedido são localizados no projeto.
- **Terminal mais prático:** Tab/Shift+Tab, histórico, seleção/cópia de saída, limpeza/EOF e instalação de dependências pelo consultor. Tcl/Tk recebe a orientação ou o instalador apropriado ao Python em uso.

## Veja funcionando

Quatro demonstrações curtas, com comandos e saídas reais da versão 0.3.1. As pausas foram editadas para facilitar a leitura; não há áudio nem modelo de IA carregado nestes vídeos.

**1. Uma intenção em Python, Dart e PowerShell; um widget do banco de padrões Flutter.**

https://github.com/user-attachments/assets/9d9afb4e-2b19-4559-a722-89cac1a982cb

**2. Revisar uma proposta, aplicar sem duplicar código e restaurar o original.** A proposta foi preparada localmente para demonstrar aplicação/histórico; o vídeo não mede geração por IA.

https://github.com/user-attachments/assets/5fdec0f3-c2dc-4df4-9975-e5b21e194a95

**3. Validar/instalar um plugin local, listar suas skills e consultar o plano do Flutter.** O `--dry-run` do SDK não faz download.

https://github.com/user-attachments/assets/ce88291d-208f-490a-9001-5b0efa3553b0

**4. Studio: seleção com Ctrl+Enter, Tab no terminal, execução e cópia da saída.**

https://github.com/user-attachments/assets/d8159b43-fa9b-43ed-9075-0281f3549136

O [manual completo com capturas](docs/MANUAL.md) reúne instalação, atualização, CLI, Studio, linguagens, SDKs, plugins, estudo, configuração, recuperação e desenvolvimento.

## Por que existe

Quando a geração de código substitui também o raciocínio e a revisão, você pode aprender menos, deixar erros passarem e depender da ferramenta para continuar.

O CODAR foi criado para manter você envolvido na programação. Você escreve a intenção em pseudocódigo, linha por linha, em português ou inglês, e acompanha a tradução para a linguagem escolhida. O compilador e os padrões ajudam com a sintaxe; a IA local amplia os pedidos possíveis. O código gerado continua precisando de revisão e testes.

A CLI é o fluxo principal. O Studio oferece um editor no terminal, inclusive via SSH; as integrações com VS Code, Neovim, Vim e PowerShell permitem usar o mesmo motor no seu ambiente de trabalho.

## Como funciona

Na tradução de intenções, o motor tenta resolver o pedido por regras, depois por padrões e, quando necessário, pela IA local:

| Camada | O que faz | Tempo típico* |
|---|---|---|
| **0 · Compilador** | Regras determinísticas para atribuições, condições, laços, impressão, contas e expressões em português ("o tamanho de pedidos", "a média entre x e y"), além de abreviações HTML e CSS no estilo Emmet. Sem IA. | < 1 ms |
| **1 · Banco de padrões** | 131 padrões incluídos: calculadora, Dijkstra, CPF/CNPJ (incluindo o CNPJ alfanumérico), Pix copia e cola, widgets Flutter, funções PowerShell, programas de linha de comando, gravação atômica de arquivos, CI, Dockerfile e mais. Usado quando você pede uma funcionalidade ("criar uma calculadora"). | < 5 ms |
| **2 · IA local** | Qwen2.5-Coder 1.5B via llama.cpp, opcional. Para pseudocódigo, o prompt pede tradução literal e usa o contexto disponível. Correções, complementos e refatorações usam um modo de edição com o código existente como referência. | ~2 s |

\* Medições de geração registradas em [docs/BENCHMARKS.md](docs/BENCHMARKS.md), num notebook Intel i7-7500U (2 núcleos, 2016), sem GPU. A primeira frase de cada linguagem que não foi pré-aquecida leva cerca de 10 s. Esses números não são um novo benchmark de qualidade das edições da versão 0.3.0.

O compilador e o banco de padrões funcionam sem instalar um modelo. Com modelos e dependências já disponíveis na máquina, a tradução e a auditoria funcionam offline. Instalação, atualização e downloads de modelos, SDKs e dependências usam a rede; veja também a seção **Privacidade**.

## Leve para começar, completo para crescer

**Você pode programar sem carregar um modelo de IA.** Regras, padrões, auditoria e histórico funcionam localmente; o Studio acrescenta arquivos, abas e terminal. Na medição sem IA da 0.3.1:

| Cenário | RAM depois das traduções (mediana de 3 execuções) | Faixa observada |
|---|---|---|
| Motor local: 20 traduções por regras e uma calculadora por padrão | **25,8 MiB** | 25,80–25,81 MiB |
| Studio + motor: três abas de 200 linhas, as mesmas traduções e uma intenção aplicada no editor | **60,3 MiB** | 60,24–60,31 MiB |

RSS medido no Linux x86_64, Python 3.12.14 e Textual 8.2.8, em processos novos. O Studio foi executado com o driver headless do Textual, em 150 × 42 células. Esses valores incluem o motor no mesmo processo; não incluem modelo, daemon separado, emulador de terminal, servidores de linguagem ou programas executados pelo usuário. [Resultados e método reproduzível](docs/BENCHMARKS.md#memória-sem-ia-031).

**Com IA, o consumo muda:** o benchmark anterior do daemon com Qwen2.5-Coder 1.5B registrou cerca de 1,27–1,41 GB. Isso não é uma medição nova da 0.3.1. O orçamento padrão de **3072 MiB** é configurável e se aplica ao serviço/motor monitorado; não representa a RAM de todo o ambiente de desenvolvimento. O monitor limpa caches e descarrega o modelo sob pressão; limites do sistema operacional são usados quando disponíveis.

Outras vantagens no trabalho diário:

- **Terminal e SSH:** trabalhe na máquina local ou num servidor sem precisar de um desktop gráfico.
- **Sem GPU obrigatória:** regras e padrões funcionam sem IA; o backend local também oferece execução do modelo pela CPU.
- **Sem assinatura de IA para traduzir:** o motor roda na sua máquina; depois dos downloads necessários, a tradução funciona offline.
- **Instale o que usa:** o núcleo não exige bibliotecas externas no Python 3.11+; Studio, gramáticas e IA são extras opcionais. No Python 3.10, o núcleo usa `tomli`.
- **Menos espera nas intenções comuns:** regras e padrões respondem sem inferência, com as latências registradas acima.
- **Acompanhe e desfaça:** veja propostas, escolha alterações, consulte o histórico e restaure versões. A lógica e a revisão continuam nas suas mãos.
- **Adapte ao projeto:** skills, plugins e comandos configuráveis permitem ampliar o ambiente e reutilizar convenções.

## O que já está disponível na versão 0.3.0

- **19 linguagens** de programação: Python, JavaScript, TypeScript, Go, Rust, Java, Kotlin, Swift, Dart, C#, C, C++, PHP, Ruby, Lua, R, Julia, Bash e PowerShell, mais HTML e CSS.
- **Correção e complemento do código existente**: uma edição substitui o trecho aprovado. A geração reserva espaço para uma resposta completa e os arquivos grandes são divididos por declarações inteiras; respostas incompletas são recusadas. A validação também rejeita novas definições Python duplicadas.
- **Revisão de até oito arquivos**: veja a comparação entre originais e propostas, escolha os trechos a aplicar e consulte o histórico. Há restauração e recuperação de operações interrompidas; alterações externas são conferidas antes de escrever.
- **Contexto por projeto**: `codar.toml` reúne convenções, skills, requisitos de SDKs e comandos. `codar check` verifica sintaxe; testes, análise e formatação são executados quando você solicita.
- **Dart/Flutter e PowerShell**: padrões, skills e validadores específicos. O Studio reconhece projetos Flutter, executa apps e testes e oferece comandos de dependências na pasta correta, inclusive em projetos aninhados.
- **SDKs e dependências**: `codar toolchains` detecta e instala ambientes por comando explícito; `--dry-run` mostra o plano. Dart e PowerShell usam downloads oficiais com SHA-256; Flutter usa o repositório oficial. As instalações gerenciadas ficam nos dados do seu usuário.
- **Plugins com recuperação**: instalar de pasta ou Git HTTPS, conferir origem, revisão, compatibilidade e dependências, atualizar, desativar, remover e restaurar versões guardadas. Uma atualização inválida preserva a instalação anterior.
- **Studio e editores**: explorador, abas, terminal integrado, execução, modo de estudo e explicação de erros. Studio e VS Code oferecem prévias de edições e histórico; Neovim, Vim e PowerShell também têm integrações.
- **Prévia no celular**: `codar servir` e F4 no Studio mostram projetos pela rede local com QR Code, incluindo proxy para um servidor de desenvolvimento.
- **Auditoria estática**: 117 regras nos plugins, além das verificações de AST Python e segredos, para apontar casos como credenciais no código e SQL concatenado, com sugestões de correção.
- **Consultor de projeto**: sugestões para o ambiente e dependências, incluindo migrações de npm para pnpm ou Bun. Você escolhe a ação a executar.
- **Atualização e distribuição**: versões dos componentes sincronizadas, diagnóstico de instalações duplicadas ou daemon antigo e arquivos publicados para Linux, Windows e macOS. Windows/macOS requerem Python 3.10+ e pipx; a extensão VS Code é instalada separadamente.

O [CHANGELOG](CHANGELOG.md) separa as mudanças por versão. As [notas da Release v0.3.0](https://github.com/Kelvin-Marques-Cyber/ReAL-Codar/releases/tag/v0.3.0) registram os testes executados e as plataformas ainda sem validação nativa nesta publicação.

### Correções e praticidade na 0.3.1

- **Ctrl+Enter respeita o foco**: na barra de intenção envia o pedido; no editor traduz a seleção exata ou, sem seleção, a linha do cursor; no terminal envia o comando. Ctrl+G é a alternativa para terminais que não distinguem Ctrl+Enter. A seleção termina antes da linha seguinte quando o fim está na coluna zero. Mover o cursor depois de enviar não muda o alvo capturado; se o texto mudar, a resposta fica na saída para revisão.
- **Seu arquivo entra no pedido**: por exemplo, `crie uma interface gráfica com base no arquivo.py`. O Studio encontra e abre o arquivo da pasta do projeto, usa seu código como contexto e mostra uma prévia de substituição. Se houver nomes repetidos, você escolhe o caminho. Cite até oito arquivos para edição de projeto.
- **Terminal com Tab/Shift+Tab**: completa caminhos, comandos disponíveis, histórico e scripts do projeto, incluindo nomes com espaços e a pasta atual após `cd`. Ações de copiar, selecionar, limpar e interromper ficam visíveis na barra.
- **Copiar sem perder texto**: Ctrl+Shift+C copia a saída do terminal ativo; Ctrl+Shift+A abre uma janela para selecionar com mouse/teclado e copiar um trecho ou tudo. Há suporte ao clipboard local quando disponível e OSC 52; em terminais que bloqueiam esse recurso, use a seleção nativa do terminal (geralmente Shift + arrastar).
- **Instalação com botão**: F8 → selecione a dependência → confira o comando → clique em **Instalar**. Bibliotecas Python vão para o venv do projeto. Tkinter é um componente do Python: Tcl/Tk usa o gerenciador da distribuição; Homebrew e Conda têm caminhos próprios. Windows ou Python compilado/pyenv recebe o procedimento oficial para modificar/recompilar o mesmo Python, sem sugerir um pacote pip incorreto.

O terminal integrado executa comandos e entrada de programas. Para aliases, conclusão específica de cada shell ou apps interativos de tela inteira, **F12** abre seu shell na pasta da sessão; `exit` volta ao Studio.

## Instalação

### Começar pela versão publicada (pipx)

Requer **Python 3.10+ e pipx**. Baixe `codar-0.3.2-py3-none-any.whl` na [Release v0.3.2](https://github.com/Kelvin-Marques-Cyber/ReAL-Codar/releases/tag/v0.3.2) e execute na pasta do download:

```sh
pipx install --force ./codar-0.3.2-py3-none-any.whl
pipx ensurepath --prepend
```

Esse comando instala ou atualiza o núcleo da CLI. Abra um terminal novo, confira `codar --version` (deve mostrar `0.3.2`) e experimente `codar run "x é igual a 10"`. Para adicionar o Studio, use `codar extras install studio`; para a IA local, siga **Depois de instalar**. Se estiver atualizando uma sessão em uso, feche o Studio e execute `codar restart` pelo executável atualizado.

### Código atual da branch `main` (pipx)

Requer **Python 3.10+, Git e pipx**. Execute no seu usuário, sem `sudo`. O extra `studio` instala a interface de terminal; o modelo de IA é opcional e separado.

```bash
pipx install 'codar[studio] @ git+https://github.com/Kelvin-Marques-Cyber/ReAL-Codar.git@main'
pipx ensurepath --prepend
```

Abra um novo terminal depois do `ensurepath`. Em Linux, o executável normalmente fica em `~/.local/bin/codar`; consulte `pipx environment --value PIPX_BIN_DIR` se você personalizou esse diretório.

### Atualizar uma instalação existente com pipx

Feche o Studio antes de atualizar. Este comando busca `main` novamente, inclusive quando dois commits declaram o mesmo número de versão:

```bash
pipx install --force --pip-args='--no-cache-dir' \
  'codar[studio] @ git+https://github.com/Kelvin-Marques-Cyber/ReAL-Codar.git@main'
```

Depois, no Bash ou Zsh:

```bash
export PATH="$(pipx environment --value PIPX_BIN_DIR):$PATH"
hash -r
codar version --verbose
codar restart
codar doctor
codar servir --help
codar toolchains --help
```

O `version --verbose` mostra o caminho do código e o **commit instalado**. Assim você consegue distinguir revisões que ainda têm o mesmo número de versão. `codar version --json` fornece esses dados para scripts. Configurações, modelos e plugins do usuário ficam fora do ambiente do pipx e não são apagados por essa atualização.

No Linux, o instalador também oferece esse fluxo:

```bash
curl -fsSL https://raw.githubusercontent.com/Kelvin-Marques-Cyber/ReAL-Codar/main/packaging/install.sh | sh -s -- --pipx
```

Ele instala/atualiza `main` com Studio e imprime os passos de reinício. Não use `sudo` nesse modo. `pipx upgrade codar` segue a origem registrada na instalação anterior; para mudar de uma instalação antiga/local para este repositório, use o comando completo com `--force` acima.

### Se ainda aparecer a versão antiga

```bash
type -a codar
readlink -f "$(command -v codar)"
pipx list
codar version --verbose
codar status
```

| Resultado | O que verificar |
|---|---|
| `~/.local/bin/codar` aponta para um ambiente `pipx/venvs/codar` | Atualize pelo `pipx`. Instalar um RPM em `/usr/bin` não atualiza essa cópia. |
| `/usr/bin/codar` vem antes no PATH | Use o caminho retornado por `pipx environment --value PIPX_BIN_DIR` ou ajuste o PATH com os comandos acima. |
| `/bin/codar` e `/usr/bin/codar` aparecem juntos | Podem ser o mesmo arquivo por causa de links do sistema; compare com `readlink -f`. |
| `--version` e `status` mostram versões diferentes | O daemon antigo continua na memória. Execute `restart` pelo executável atualizado. |
| A versão continua igual, mas o commit mudou | O código foi atualizado; números de versão não são incrementados a cada commit. |
| `version --verbose` não é reconhecido | Essa CLI é anterior à correção; execute a instalação forçada e confira o caminho do executável. |

O serviço opcional `codar.service` usa **`/usr/bin/codar`**. Se você o ativou e quer passar a usar pipx, pare e desative esse serviço com `systemctl --user disable --now codar`, depois execute o `codar restart` da instalação pipx. Se vai continuar no pacote da distro, use `systemctl --user restart codar` após atualizar o pacote. Reabra o Studio para carregar o código novo.

### Linux, por uma Release publicada

Baixe o pacote da sua distro em [Releases](https://github.com/Kelvin-Marques-Cyber/ReAL-Codar/releases) ou use o instalador abaixo. **O instalador padrão não instala `main` e não atualiza uma instalação pipx.**

```bash
curl -fsSL https://raw.githubusercontent.com/Kelvin-Marques-Cyber/ReAL-Codar/main/packaging/install.sh | sh
```

O instalador detecta apt, zypper, dnf, pacman ou apk e baixa o pacote da última Release. Para fixar uma versão já publicada, passe `CODAR_VERSION=0.3.2` ao processo `sh`. Se preferir baixar o arquivo manualmente, substitua `<versao>` pelo número do pacote baixado:

| Distro | Comando |
|---|---|
| Debian 12+, Ubuntu 22.04+ | `sudo apt install ./codar_<versao>-1_all.deb` |
| openSUSE Tumbleweed, Leap 16.0 e 15.6 | `sudo zypper install --allow-unsigned-rpm ./codar-<versao>-1.noarch.rpm` |
| Fedora | `sudo dnf install ./codar-<versao>-1.noarch.rpm` |
| Arch | `sudo pacman -U ./codar-<versao>-1-any.pkg.tar.zst` |
| Alpine | `sudo apk add --allow-untrusted ./codar_<versao>-r1_noarch.apk` |

O pacote traz o comando `codar`, a página de manual (`man codar`), o completar com Tab para bash, zsh e fish, os plugins de Neovim e Vim já ativos e um serviço opcional do systemd (`systemctl --user enable --now codar`). Ele depende só do Python 3.10+ do sistema. O CI está configurado para instalar e remover os pacotes em contêineres limpos dessas distros; confira os resultados da execução, especialmente em publicações manuais ([docs/PACKAGING.md](docs/PACKAGING.md)).

### Windows e macOS, por uma Release publicada

Esses arquivos requerem **Python 3.10+ e pipx**; não são instaladores autônomos EXE/DMG. Baixe e extraia o arquivo correspondente em [Releases](https://github.com/Kelvin-Marques-Cyber/ReAL-Codar/releases):

| Sistema | Arquivo | Comando dentro da pasta extraída |
|---|---|---|
| Windows | `codar-0.3.2-windows-python.zip` | `py -3 .\install.py` no PowerShell |
| macOS | `codar-0.3.2-macos-python.tar.gz` | `sh install.sh` |

O instalador confere a integridade dos arquivos, instala a wheel incluída pelo pipx, verifica a versão e mostra o executável exato. Studio e gramáticas opcionais entram por padrão; `--core` instala só a CLI. O README dentro de cada arquivo explica como instalar os pré-requisitos. Abra um terminal novo e execute `codar restart` depois de atualizar. A extensão `codar.vsix` continua sendo instalada separadamente no VS Code.

Cada Release inclui `SHA256SUMS` e `RELEASE.json` com versões, tamanhos, hashes e a revisão de origem. As notas da Release descrevem quais verificações foram executadas; uma compilação bem-sucedida não comprova a instalação em todos os sistemas.

### Importar bibliotecas sem gerar uma aplicação

Pedidos de importação têm escopo próprio em todas as linguagens. A finalidade da biblioteca não é uma ordem para implementar funções, exemplos ou downloads. Por exemplo:

```bash
codar run "importar bibliotecas numpy e pandas" --lang python --local
# import numpy as np
# import pandas as pd
codar run "importar biblioteca requests para consultar uma API" --lang python --local
# import requests
codar run "importar classe FastAPI de fastapi" --lang python --local
# from fastapi import FastAPI
codar run "importar biblioteca axios" --lang typescript --local
# import axios from 'axios';
codar run "importar biblioteca dio" --lang dart --local
# import 'package:dio/dio.dart';
```

O reconhecimento aceita nomes, aliases, símbolos e listas de bibliotecas. Pacotes particulares com um nome de módulo válido também funcionam, sem depender de um catálogo fechado. Nomes de distribuição conhecidos são relacionados ao import correto, como **scikit-learn → sklearn**, **Pillow → PIL**, **OpenCV → cv2** e **beautifulsoup4 → bs4**. A instalação é separada, no ambiente do projeto; importar não executa pip, npm, pub, consultas remotas nem downloads.

Quando o nome ou a entrada de uma biblioteca não puder ser resolvido, a IA local opcional sugere somente declarações de importação. O motor valida e descarta qualquer implementação extra antes de mostrar ou aplicar o resultado. Respostas inválidas ou incompletas preservam o código existente. SQL, YAML e Dockerfile explicam que não possuem esse tipo de importação. Para pedir uma implementação, escreva explicitamente, por exemplo: `crie uma função para consultar uma API com requests`.

Nas próximas gerações, o CODAR consulta as fontes/tipos/documentação locais dos pacotes usados no arquivo e prioriza APIs relacionadas ao pedido. A inspeção inclui reexportações de Python e tipos externos de React/Express em `@types`, sem executar os pacotes. Veja exemplos de bibliotecas, instalação, cobertura e limites em [Bibliotecas e código do projeto](docs/LIBRARIES.md).

## Depois de instalar

```bash
codar run "x é igual a 10"     # o compilador e o banco de padrões já funcionam, sem nada extra
codar studio .                  # já disponível se você instalou com [studio]
codar extras install studio     # para quem instalou só o núcleo/pacote da distro
codar doctor                   # confere o ambiente e diz o que falta
```

Para habilitar também a IA local:

```bash
codar extras install llm
codar init                     # configuração e modelo de IA padrão (~1,1 GB)
codar restart
```

Sem o modelo, só as frases que nem o compilador nem o banco entendem ficam sem resposta, com uma mensagem dizendo como instalar o modelo. Testado em Linux, inclusive Ubuntu Server via SSH. O código também cobre macOS e Windows (Named Pipe, Job Object). Os workflows de CI incluem testes de edição e recuperação em Windows e macOS, além do cliente VS Code em Windows e Linux. Confira os resultados no GitHub Actions; a validação local desta versão foi feita em Linux.

## Primeiros passos

```bash
codar run "x é igual a 10"                       # Python é o padrão
codar run -l go "se total maior que 100 imprimir 'caro'"
codar run -l html "ul>li.item\$*3"               # abreviação HTML
codar run "criar uma calculadora" > calc.py       # padrão completo do banco

printf 'x = 10\ny = 20\n' > conta.py
codar run --file conta.py "some os dois números e imprima"   # IA com o arquivo como contexto: print(x + y)

codar compile -l rust algoritmo.txt              # pseudocódigo indentado de várias linhas
codar audit app.py                               # auditoria de um arquivo
codar advise                                     # sugestões para o projeto atual
codar studio .                                   # IDE no terminal
```

O Studio funciona em qualquer terminal, inclusive via SSH; no console puro do Linux (`TERM=linux`) os gráficos viram ASCII. `F1` mostra todos os atalhos.

![Ajuda do Studio (F1) com os atalhos agrupados](docs/img/manual/02-atalhos.png)

O Studio também tem explorer de arquivos, abas, terminal integrado, execução com **F5**, auditoria com **F6**, modo de estudo com **F7** e consultor com **F8**. `Ctrl+E`, `Ctrl+T` e `Esc` alternam o foco entre explorer, terminal e editor. `codar explicar -- python app.py` executa um programa e explica erros reconhecidos; também aceita a saída pelo stdin.

### Buscar no arquivo e no projeto

**Ctrl+F** busca no arquivo aberto, incluindo o que ainda não foi salvo. **Ctrl+Shift+F** e o botão **BUSCAR** pesquisam nomes e conteúdo no projeto, incluindo documentação e configurações de texto. A busca do projeto usa os arquivos em disco. Os resultados mostram caminho, linha e prévia; **Abrir** ou Enter na lista levam ao trecho; **F3/Shift+F3** percorrem a lista.

A busca literal funciona sem modelo e sem daemon. Para descrições como “onde o usuário faz login”, marque **Usar IA local**: o modelo sugere termos como `login` e `autenticacao`, e a busca procura esses termos nos arquivos. Os termos ficam visíveis para revisão; essa opção precisa da IA configurada e não garante compreensão semântica do projeto inteiro.

```bash
codar project search login --root .
codar project search "onde o usuário entra" --root . --ai
codar project search salvar --file app.py --json
```

A busca respeita exclusões e não segue links para fora da pasta. Há limites de 200 resultados, 2.000 arquivos e 32 MiB de leitura por pesquisa, além do limite por arquivo; o painel informa quando há corte ou arquivos ignorados.

### Ativar salvamento automático

Clique em **AUTO OFF** para ativar ou **AUTO ON** para desativar. A preferência persiste entre sessões; o padrão é desligado. O Studio salva arquivos nomeados e já existentes após uma pausa, mantendo permissões e fazendo a troca do arquivo de forma atômica. Se outro programa alterar ou apagar o arquivo, aquela aba pausa o autosave e mantém o buffer para revisão.

```bash
codar config set studio.autosave true
codar config set studio.autosave_delay_s 1.5
```

O intervalo é aplicado ao iniciar o Studio e fica entre 0,3 e 60 segundos. Arquivos sem nome e novos caminhos precisam de **Ctrl+S** primeiro. **Ctrl+Z** desfaz no buffer; com autosave ligado, a versão desfeita será salva após a pausa. Propostas de IA continuam passando pela prévia antes de entrar no editor.

### Estudar na linguagem que você usa

Ative **F7** e mova o cursor: o painel explica o conceito, mostra um exemplo na linguagem do arquivo e propõe um exercício. **Catálogo** ou **Ctrl+Shift+F7** lista somente tópicos com exemplos para aquela linguagem, com filtro por nome/trilha. **Fontes** abre as referências oficiais; **Marcar praticado** registra sua prática por projeto/linguagem, sem avaliação automática de domínio.

São 24 tipos de arquivo reconhecidos: as 19 linguagens do compilador, HTML, CSS, YAML e Dockerfile. O catálogo inclui testes, tipos, geradores, logs e ambientes Python; null safety, Future e widgets/estado Flutter em Dart; pipeline e erros PowerShell; posse Rust; erros Go; agregações SQL; acessibilidade HTML; Flexbox; vetores R e broadcast Julia. Material e links oficiais revisados em **10/10/2026**.

```bash
codar study list --lang dart
codar study show flutter_estado --lang dart
codar estudar list --lang powershell
codar study show guia_sql --lang sql
```

As linguagens têm catálogos de profundidades diferentes. A **trilha automática de POO** que analisa o arquivo e sugere `main` continua disponível para Python e JavaScript/TypeScript; as demais têm guias e exercícios nativos. O Estudo não insere exemplos no seu código automaticamente. Shift+F7 cria uma sugestão somente quando ela existe e não sobrescreve um arquivo já criado.

### Editar um projeto pela CLI

Dentro da pasta do projeto, inicialize suas convenções e peça uma alteração. A geração de edições exige o extra `llm` e um modelo local instalado; `project`, `check` e o histórico funcionam sem IA.

```bash
codar project init
codar project info
codar project context "corrigir autenticação" --file app.py
codar edit "corrija a autenticação e atualize os testes" --file app.py --file test_app.py
```

`edit` mostra uma proposta e seu identificador, sem escrever nos arquivos. Revise o diff e então use o id real mostrado:

```bash
codar edits list
codar edits show ID
codar edits apply ID
codar check --tests
codar edits restore ID          # recupera os originais, se não houve novas alterações
codar edits recover             # recupera uma aplicação interrompida
```

`edits show ID --json` lista os identificadores dos trechos. `edits apply ID --hunk 'app.py:0'` aplica apenas aquele trecho; repita `--hunk` para escolher vários. `edit --apply` aplica diretamente depois da validação. `--root PASTA` escolhe o projeto; `edit --local` gera sem daemon.

O Codar recebe referências de arquivos relacionados e as convenções do projeto. Diretórios de dependências e saída, arquivos gerados, links simbólicos e nomes usuais de segredos ficam excluídos. Em repositórios Git, a seleção de referências respeita `.gitignore`; fora deles, interpreta regras comuns do arquivo da raiz. Use `project.exclude` para regras próprias. Não é uma análise semântica completa como a de um servidor de linguagem.

Arquivos grandes são divididos em **declarações completas**, preservando o texto fora delas. Python e PowerShell têm divisão própria; Dart, JavaScript, TypeScript, Go e Rust usam gramáticas opcionais (`codar extras install syntax`). Uma função que não cabe no orçamento é recusada, sem truncar seu código. Novos arquivos e arquivos pequenos são gerados por inteiro.

Antes de aplicar, o Codar verifica a sintaxe disponível e rejeita novas definições Python duplicadas. Dart usa `dart format --output=none`; PowerShell usa seu parser oficial. Esses verificadores não executam o programa gerado. A geração tenta corrigir erros de sintaxe no máximo duas vezes, conforme `repair_attempts`; erros restantes ficam na proposta e bloqueiam sua aplicação. Se faltar um validador, o resultado aparece como `skipped`, sem alegar que passou.

Os originais ficam nos dados privados do Codar. A aplicação compara o texto atual com o snapshot, guarda um diário antes de trocar arquivos e tenta desfazer trocas já realizadas se ocorrer uma falha. Mudanças feitas por outro editor impedem a sobrescrita. Arquivos são trocados individualmente: a recuperação reduz o risco de uma edição parcial, mas não oferece uma transação do sistema de arquivos entre vários arquivos.

### Convenções, comandos e SDKs por projeto

Exemplo de `codar.toml` para Flutter:

```toml
[project]
skills = ["flutter.widgets"]
guidance = ["Preserve public APIs and the project architecture."]
exclude = ["lib/generated/*"]
context_chars = 4000
repair_attempts = 1

[commands]
run = ["flutter", "run"]
test = ["flutter", "test"]
analyze = ["flutter", "analyze"]
format = ["dart", "format", "."]

[toolchains]
dart = ">=3.0.0,<4.0.0"
```

```bash
codar project doctor           # verifica versões declaradas; não instala nem troca SDKs
codar project run --file lib/main.dart
codar check lib/main.dart     # sintaxe de um arquivo salvo
codar check --analyze --tests # executa os comandos explicitamente solicitados
codar check --format          # formata arquivos com o comando do projeto
```

Os comandos são listas de argumentos, executadas sem shell; `{root}` e `{file}` representam caminhos. Testes, analisadores e formatadores só rodam quando solicitados e podem executar código do projeto. Há comandos padrão para projetos Flutter/Dart, pytest e scripts npm; `codar.toml` permite adaptá-los. `check --timeout 120` define o tempo de cada comando, até 300 segundos. A saída retornada é limitada aos últimos 32 KB.

### Corrigir e completar código existente no editor

No Studio, selecione o trecho, pressione **Ctrl+L** e descreva a alteração, por exemplo: `corrija a validação sem mudar a assinatura`. A resposta **substitui a seleção**. No VS Code, use **Codar: Gerar código a partir de uma intenção…** com o trecho selecionado.

Studio e VS Code abrem uma comparação antes de aplicar edições e permitem escolher trechos. Cancelar mantém o original. No Studio, **Ctrl+Shift+H** abre as versões do arquivo e **Ctrl+Shift+G** propõe uma edição em vários arquivos salvos; a paleta de comandos também oferece verificações do projeto e gestão de plugins. No VS Code, os comandos equivalentes ficam em **Ctrl+Shift+P → Codar**.

Sem seleção, pedidos que começam com `corrija`, `refatore`, `reescreva`, `substitua`, `complete`, `melhore` ou `otimize` substituem o **arquivo aberto inteiro**, se ele contém código. Pedidos de criação continuam inserindo código abaixo da linha atual. Para uma alteração pequena, selecione apenas o trecho necessário. **Ctrl+Z** desfaz corpo e imports juntos; o arquivo só é salvo quando você manda salvar.

A edição usa a IA local (S2). O motor recebe o trecho original e o código ao redor, com instruções para devolver uma substituição completa. Se o arquivo mudar durante a geração, a aba for fechada ou a resposta atingir o limite de tokens, o código original é preservado e a resposta fica em **SAÍDA**. A qualidade do resultado depende do modelo: revise a alteração antes de salvar.

O limite de seleção é `router.max_edit_chars` (12.000 caracteres). Isso não aumenta a capacidade do modelo. Se o prompt não couber ou a resposta ficar incompleta, selecione um trecho menor. Para edições maiores, ajuste o contexto e a saída e reinicie o daemon, respeitando a RAM disponível:

```bash
codar config set model.n_ctx 4096
codar config set model.max_tokens 1024
codar restart
```

Pelo terminal, você pode gerar a substituição sem escrever no arquivo original:

```bash
codar run --mode edit --file app.ps1 "refatore preservando os parâmetros" > app-revisado.ps1
```

### Dart, Flutter e PowerShell

O compilador já traduz pseudocódigo para Dart e PowerShell. Os plugins incluídos acrescentam exemplos de **MaterialApp**, **StatelessWidget**, **StatefulWidget**, consumo de JSON em Dart e funções PowerShell com parâmetros e pipeline:

```bash
codar run --local --stages 0,1 -l flutter "criar aplicativo flutter materialapp"
codar run --local --stages 0,1 -l dart "criar widget stateless flutter"
codar run --local --stages 0,1 -l powershell "ler arquivo json powershell"
```

No Studio, **F5** em `lib/` de um projeto Flutter executa `lib/main.dart`; em `test/*_test.dart`, executa `flutter test`. Arquivos Dart comuns usam `dart run`. A detecção procura o `pubspec.yaml` mais próximo dentro da pasta aberta, inclusive em projetos aninhados. **F8** mostra dependências ausentes e oferece `flutter pub get`, `flutter pub add`, `dart pub get` ou `dart pub add` na pasta correta. Imports de `dart:`, do próprio pacote e de bibliotecas já resolvidas não geram instalação indevida.

Para criar um projeto, abra o terminal do Studio (**Ctrl+T**) e use `flutter create meu_app` ou `dart create meu_app`; depois abra essa pasta com `codar studio meu_app`. Em Flutter, selecione o dispositivo quando o comando pedir; `r` e Enter no terminal enviam hot reload. `flutter doctor` identifica os requisitos de Android, web ou desktop que ainda faltam.

### Várias versões Python e ambientes por projeto

Você pode manter várias versões instaladas e vários ambientes virtuais. Cada projeto/sessão usa um interpretador por execução; terminais já rodando continuam com seu processo atual. O Python que executa o CODAR não é trocado.

```bash
codar toolchains install python --version 3.12 --version 3.13 --dry-run
codar toolchains install python --version 3.12 --version 3.13
codar toolchains versions python
codar toolchains use python 3.13 --root ./meu-projeto
codar toolchains venv python --version 3.13 --root ./meu-projeto --venv .venv313
codar toolchains use python --path ./meu-projeto/.venv313/bin/python --root ./meu-projeto
codar toolchains use python 3.12 --global
```

No Windows, o executável do venv fica em `.venv313\Scripts\python.exe`. O botão **SDKs** do Studio lista versões e permite instalar outra ou criar um ambiente; o ambiente novo não substitui uma pasta existente. Subpastas herdam a escolha do projeto, e um projeto com escolha explícita tem precedência sobre o padrão global. F5, consultor de pacotes, `project run`, verificações e novos comandos no terminal usam o ambiente escolhido.

Downloads de versões Python usam [uv](https://docs.astral.sh/uv/guides/install-python/) e as distribuições `python-build-standalone` da Astral. Se uv estiver ausente, o comando oferece a instalação via pipx e informa a origem. As instalações ficam nos dados do CODAR. Outros SDKs usam o fluxo abaixo; `use --path` também pode selecionar um executável Dart, Flutter ou PowerShell instalado separadamente. `--version` na instalação é, nesta versão, exclusivo de Python.

### Instalar ferramentas de programação

O CODAR funciona sem SDKs para **gerar** código. Para **executar**, instale as ferramentas necessárias:

```bash
codar toolchains list
codar toolchains install flutter --dry-run  # mostra a origem e a pasta, sem baixar
codar toolchains install flutter           # canal stable; requer Git
codar toolchains install dart              # SDK Dart independente, se ainda não existir
codar toolchains install powershell        # PowerShell 7, comando pwsh
codar toolchains install go rust           # pelo gerenciador do sistema
```

SDKs de Dart e PowerShell são baixados de fontes oficiais e conferidos por **SHA-256**, extraídos numa pasta temporária e publicados só depois da validação. Flutter vem do [repositório oficial](https://github.com/flutter/flutter), branch `stable`; o primeiro uso prepara as dependências do SDK e pode baixar arquivos adicionais. SDKs gerenciados ficam na pasta de dados do CODAR, no seu usuário, sem alterar arquivos do shell. Os terminais do Studio os reconhecem automaticamente. PowerShell portátil ainda depende das bibliotecas nativas do seu sistema.

Python, Node.js/TypeScript, Go, Rust, Java, C/C++, PHP, Ruby e Lua usam o gerenciador disponível: apt, dnf, zypper, pacman, apk, Homebrew ou WinGet. A disponibilidade varia por sistema; ferramentas ausentes no catálogo daquele gerenciador geram uma mensagem clara. Instalações de pacotes do sistema podem solicitar a senha do `sudo` ou elevação do Windows. Instalações existentes são aproveitadas.

Para usar os SDKs gerenciados também fora do Studio, execute no terminal atual:

```bash
eval "$(codar toolchains env)"                    # Bash/Zsh
codar toolchains env --shell fish | source         # Fish
```

No PowerShell: `codar toolchains env --shell powershell | Invoke-Expression`. Fontes e requisitos: [Dart SDK](https://dart.dev/get-dart), [Flutter](https://docs.flutter.dev/install/manual) e [PowerShell](https://learn.microsoft.com/powershell/scripting/install/installing-powershell).

### Ver o projeto no celular

No Studio, **F4** mostra a prévia na rede local com QR Code; **F5** em uma página HTML também abre a prévia. Pelo terminal:

```bash
codar servir .                 # páginas, imagens e gráficos salvos nesta pasta
codar servir --proxy 5173       # repassa um servidor de desenvolvimento local
codar servir . --local         # acesso somente neste computador
```

O celular precisa alcançar o computador pela rede (por exemplo, no mesmo Wi-Fi). Em SSH, o endereço pertence ao servidor remoto e precisa estar acessível ao celular. O programa avisa quando detecta uma possível regra de firewall bloqueando a porta. A prévia de pasta usa um código aleatório na URL e oculta arquivos como `.env` e `.git`; compartilhe somente a pasta necessária, em rede confiável, e pare com `Ctrl+C`. No modo proxy, o conteúdo e as permissões são os do servidor de desenvolvimento.

## Atalhos

Os mesmos gestos em todos os lugares:

| Gesto | O que faz | Onde |
|---|---|---|
| frase + **espaço** + **Enter** | traduz a linha em vez de quebrar a linha (só quando a linha parece uma frase, nunca em código) | Studio, Neovim, Vim, VS Code |
| **Ctrl+Enter** | traduz a linha, ou o bloco selecionado | Studio, Neovim, Vim, VS Code, PowerShell |
| **Ctrl+Enter** na intenção | envia o pedido usando o arquivo citado ou a seleção/arquivo aberto | Studio |
| **Ctrl+G** | o mesmo, em terminais que não distinguem Ctrl+Enter | Studio, Neovim, Vim, PowerShell, bash, zsh, fish |
| **Tab** | aceita a sugestão do autocompletar; em `.html`, `.css` e `.jsx` expande abreviações (`ul>li*3`, `a:blank`, `df+jcc`) | Studio |
| **→** | aceita a sugestão (no editor e na barra de intenção) | Studio |
| **Tab** no shell | completa comandos, opções, linguagens, modelos e padrões do `codar` | bash, zsh, fish |
| **Tab / Shift+Tab** no terminal integrado | completa/percorre comandos e caminhos, histórico e scripts | Studio |
| **Ctrl+Shift+C / Ctrl+Shift+A** | copia saída inteira / abre saída selecionável | Studio |
| **Ctrl+L / Ctrl+W** no terminal integrado | limpa saída / apaga palavra anterior do comando | Studio |
| **Ctrl+D / Ctrl+Shift+W** | envia EOF ou fecha sessão vazia / fecha sessão ociosa | Studio |
| **F12** | abre seu shell; `exit` volta ao Studio | Studio |
| **F4** | prévia do projeto no celular, com QR Code | Studio |
| **F5** / **F7** | executa o arquivo / abre o modo de estudo | Studio |
| **Ctrl+F** / **Ctrl+Shift+F** | busca no buffer / nomes e conteúdo do projeto; IA opcional | Studio |
| **Ctrl+Shift+F7** | abre o catálogo de estudo da linguagem do arquivo | Studio |
| **AUTO ON/OFF** / **SDKs** | configura autosave / escolhe a versão Python do projeto | Studio |

O autocompletar do Studio sugere palavras do próprio arquivo, palavras-chave da linguagem e o vocabulário do pseudocódigo ("imprimir", "enquanto", "senão"…). A barra de intenção sugere o que você já pediu e frases de exemplo.

## Editores e terminais

Todos falam com o mesmo daemon local, que sobe sozinho no primeiro uso.

| Onde | Como ativar |
|---|---|
| **Studio** | `codar studio .` (depois de `codar extras install`) |
| **Neovim** 0.10+ | com o pacote do sistema, o plugin já está instalado: ponha `require("codar").setup()` no `init.lua`. Do repositório: `{ dir = "~/ReAL-Codar/clients/nvim", config = function() require("codar").setup() end }` no lazy.nvim |
| **Vim** 8+ | com o pacote do sistema, já está ativo. Do repositório: `set runtimepath+=~/ReAL-Codar/clients/vim` no `.vimrc` |
| **bash / zsh** | `eval "$(codar shell-init bash)"` no `.bashrc`; no `.zshrc`, troque `bash` por `zsh` |
| **fish** | `codar shell-init fish \| source` no `config.fish` |
| **PowerShell** | `Import-Module /usr/share/codar/powershell/Codar` (pacote) ou `Import-Module ./clients/powershell/Codar` (repositório); depois `cdr "x é igual a 10"` e `Enable-CodarKeyHandler` |
| **Qualquer app** | `codar hook install` mostra como criar um atalho global no seu sistema |
| **VS Code** | `code --install-extension codar.vsix` ([clients/vscode](clients/vscode)) |

No Neovim: `:Codar <intenção>` insere abaixo do cursor, `:CodarAudit` mostra a auditoria como diagnósticos, `:CodarAdvise` abre o consultor, `:CodarStatus` mostra RAM e modelo e `:CodarStudio` abre o Studio numa aba. Detalhes em [clients/nvim](clients/nvim) e [clients/vim](clients/vim).

A extensão do **VS Code é atualizada separadamente** da CLI. Para compilar a partir do repositório atualizado:

```bash
cd clients/vscode
npm ci
npm run compile
npm run package
code --install-extension codar.vsix --force
```

Recarregue a janela do VS Code. Se houver instalações duplicadas, configure `codar.executable` com o caminho absoluto da CLI desejada (por exemplo, `/home/kelvin/.local/bin/codar`, substituindo pelo seu usuário).

Para começar: abra uma pasta com **Arquivo → Abrir Pasta**, abra um `.py`, `.dart` ou `.ps1` e digite `x é igual a 10`. Pressione **Ctrl+Alt+Enter** para traduzir a linha. Para corrigir código, **selecione o trecho**, abra **Ctrl+Shift+P**, escolha **Codar: Gerar código a partir de uma intenção…**, descreva a correção e revise a comparação antes de aplicar. Reescrita requer a IA local instalada na CLI. Instalar a CLI não instala automaticamente a extensão; um guia completo está em [clients/vscode/README.md](clients/vscode/README.md).

## Memória: orçamento padrão de 3 GB

O daemon usa um orçamento configurável para a própria memória (RSS), consultada a cada 2 segundos. Com o padrão de 3 GB, ele reage ao uso medido:

- **80% do orçamento**: limpa caches e o estado da IA, mantendo o modelo carregado.
- **92%**: descarrega o modelo. O compilador e o banco continuam respondendo.
- **15 minutos sem uso**: descarrega o modelo e devolve a memória ao sistema.

| Modelo | Arquivo | RAM medida | Acerto* | Licença |
|---|---|---|---|---|
| `qwen2.5-coder-0.5b` | 469 MB | ~0,7 GB | 83% | Apache-2.0 |
| **`qwen2.5-coder-1.5b`** (padrão) | 1066 MB | ~1,3 GB | 88% | Apache-2.0 |
| `qwen2.5-coder-3b` | 2007 MB | ~2,2 GB | 88% | qwen-research (uso não comercial) |

\* Medições anteriores de geração: pass@1 em 24 tarefas em português, com o código executado contra testes. O consumo depende do modelo, contexto e ambiente; esses percentuais não avaliam a edição de projetos da versão 0.3.0. Detalhes e outros modelos em [docs/BENCHMARKS.md](docs/BENCHMARKS.md).

```bash
codar model list            # modelos, tamanho, RAM estimada e licença
codar model use qwen2.5-coder-0.5b
codar bench --soak 200      # teste de carga: latência por camada, pico de RAM e vazamento
```

O orçamento fica em `[memory] budget_mb` no arquivo de configuração (`codar config path`). No Linux com systemd, o daemon também pede ao sistema um limite rígido de memória quando isso está disponível; o `codar doctor` mostra como ativar. O orçamento do daemon não limita os programas e SDKs executados nos terminais do projeto.

## Configuração

```bash
codar config path                     # onde fica o config.toml
codar config get model
codar config set model.warm_langs '["python", "powershell"]'
codar restart
```

`warm_langs` define as linguagens que a IA deixa prontas ao carregar. O padrão `["auto"]` aquece as três que você mais usa. O aquecimento roda em segundo plano e cede a vez a qualquer pedido seu.

## Privacidade

A tradução e a auditoria rodam localmente. O daemon escuta só localmente (Unix socket com permissão `0600`, Named Pipe no Windows ou TCP em `127.0.0.1` com token). Instalação, atualização, download de modelos/extras e comandos aprovados no consultor podem acessar a rede. `codar servir` e F4 no Studio compartilham a prévia pela rede quando solicitados; use `--local` para restringi-la ao computador. Programas que você executa no terminal seguem o próprio comportamento de rede.

## Estendendo

Padrões, regras de auditoria, skills e sugestões do consultor são arquivos TOML. Um padrão novo pode trazer testes, e o `patternlint` executa esses testes em cada linguagem antes de aceitar o padrão:

```bash
codar plugins new meu-plugin          # cria a estrutura em ~/.config/codar/plugins/meu-plugin
codar plugins install ./meu-plugin    # valida e instala um plugin local, sem sobrescrever outro
codar plugins install https://github.com/SEU-USUARIO/SEU-PLUGIN.git --ref v1.0.0
codar plugins update meu-plugin      # repete a origem registrada e guarda a versão anterior
codar plugins info meu-plugin        # versão, origem, revisão Git e erros
codar plugins disable meu-plugin
codar plugins enable meu-plugin
codar plugins remove meu-plugin      # guarda uma cópia para recuperação
codar plugins restore meu-plugin
codar plugins list
codar skills list -l dart
codar skills show flutter.widgets
codar patterns add --title "Ler CSV" --keywords "ler csv arquivo" --code-file ler_csv.py -l python
```

Guia completo em [docs/EXTENDING.md](docs/EXTENDING.md). Arquitetura e protocolo em [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) e [docs/PROTOCOL.md](docs/PROTOCOL.md).

Skills do CODAR são diretrizes TOML usadas pela IA local. Você pode editá-las dentro de um plugin criado com `plugins new`, instalar a pasta com `plugins install` e ativá-las por projeto. Operações de gestão pedem recarga ao daemon já iniciado; se isso falhar, execute `codar restart`. Manifestos inválidos e dependências incompatíveis ficam isolados; uma atualização inválida preserva a instalação anterior. Extensões Python de terceiros dependem da opção explícita `plugins.allow_python`: ela autoriza código local de confiança, sem sandbox nem proteção contra travamento nativo.

## Desenvolvimento

```bash
git clone https://github.com/Kelvin-Marques-Cyber/ReAL-Codar
cd ReAL-Codar
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,studio]"
python packaging/check_versions.py        # versões dos pacotes, fonte Python e changelog
pytest                                   # motor, compilador, Emmet, roteamento e completar
python -m codar.evals.patternlint        # sintaxe de cada padrão + testes executáveis
python -m codar.evals.editbench --reference # verifica os gabaritos de edição; não mede IA
python -m codar.evals.editbench --out editing-results.json # mede o modelo local configurado
tests/clients/run.sh "$(command -v codar)"   # plugins de Neovim e Vim contra o daemon real
```

Veja [CONTRIBUTING.md](CONTRIBUTING.md) e o [histórico de mudanças](CHANGELOG.md).

## Licença

[Apache 2.0](LICENSE). Os modelos de IA não fazem parte do repositório: são baixados por `codar model pull` e cada um segue a licença do autor (veja a tabela acima).

---

**In English:** Version 0.3.2 restricts library requests to imports, without implementing their purpose. CODAR translates line-by-line pseudocode into 19 languages, with HTML/CSS abbreviations and optional local AI. Version 0.3.1 adds native study guides for all 24 supported languages and file formats, file/project search, optional autosave, project-specific Python versions and virtual environments, improved editing context, terminal completion/copy, and guided dependency installation. It includes reviewed edits, history, plugins, Dart/Flutter and PowerShell workflows, a terminal Studio and editor clients. In a reproducible Linux benchmark without AI, the engine used about 26 MiB and the headless Studio about 60 MiB; model and external process memory are separate. Local translation and study work offline after installation; downloads require network access. [Release v0.3.2](https://github.com/Kelvin-Marques-Cyber/ReAL-Codar/releases/tag/v0.3.2) includes Linux packages, Python/pipx installers for Windows/macOS, wheel/source archives and VSIX. Alpha project, Apache-2.0 licensed.
