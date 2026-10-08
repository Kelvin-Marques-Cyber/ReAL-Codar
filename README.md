# CODAR

**Você escreve a intenção em pseudocódigo. O CODAR escreve o código.**
Um ambiente de programação para o terminal, com IA local, que roda 100% offline e cabe em 3 GB de RAM.

![CODAR Studio: o editor no terminal, com a linha "se total maior que 100 imprimir 'frete grátis'" já traduzida para Python](docs/img/studio.png)

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

## Por que existe

Gerar o programa inteiro com IA tem três custos: você para de aprender, não percebe quando a IA errou (ninguém revisa 3 mil linhas) e fica dependente de internet e assinatura.

No CODAR a lógica continua sendo sua. Você escreve linha por linha o que quer, em português ou inglês, e ele traduz para a linguagem escolhida. Se a lógica estiver errada, o código sai com o mesmo erro, e você entende onde errou. O que some é a barreira da sintaxe.

## Como funciona

Cada linha passa por três camadas, da mais barata para a mais cara:

| Camada | O que faz | Tempo típico* |
|---|---|---|
| **0 · Compilador** | Regras determinísticas para atribuições, condições, laços, impressão, contas e expressões em português ("o tamanho de pedidos", "a média entre x e y"), além de abreviações HTML e CSS no estilo Emmet. Sem IA. | < 1 ms |
| **1 · Banco de padrões** | 101 padrões com boas práticas, testados automaticamente: calculadora, Dijkstra, CPF/CNPJ (incluindo o CNPJ alfanumérico), Pix copia e cola, programas de linha de comando, gravação atômica de arquivos, CI, Dockerfile e mais. Usado quando você pede uma funcionalidade ("criar uma calculadora"). | < 5 ms |
| **2 · IA local** | Qwen2.5-Coder 1.5B via llama.cpp, em **modo literal**: traduz só o que a linha diz, sem inventar funções, imports ou dados de exemplo. Usa o código acima do cursor como contexto. | ~2 s |

\* Medido num notebook Intel i7-7500U (2 núcleos, 2016), sem GPU. A primeira frase de cada linguagem que não foi pré-aquecida leva cerca de 10 s.

Além da tradução:

- **Auditoria estática a cada geração**: segredos no código, injeção de SQL, comandos de shell que apagam o próprio arquivo e outras 140 regras (Python, JavaScript, PowerShell, Bash, SQL, Docker e mais), cada uma com a correção sugerida.
- **Consultor de projeto**: "O projeto usa npm. pnpm e Bun instalam as mesmas dependências bem mais rápido…". Você escolhe a opção e ele executa a migração.
- **14 linguagens** de programação: Python, JavaScript, TypeScript, Go, Rust, Java, C#, C, C++, PHP, Ruby, Lua, Bash e PowerShell, mais HTML e CSS.

## Instalação

### Linux, pelo gerenciador de pacotes (recomendado)

```bash
curl -fsSL https://raw.githubusercontent.com/Kelvin-Marques-Cyber/ReAL-Codar/main/packaging/install.sh | sh
```

O instalador detecta apt, zypper, dnf, pacman ou apk, baixa o pacote da última versão em [Releases](https://github.com/Kelvin-Marques-Cyber/ReAL-Codar/releases) e instala. Se preferir fazer à mão, baixe o pacote da sua distro e:

| Distro | Comando |
|---|---|
| Debian 12+, Ubuntu 22.04+ | `sudo apt install ./codar_0.1.0-1_all.deb` |
| openSUSE Tumbleweed e Leap | `sudo zypper install --allow-unsigned-rpm ./codar-0.1.0-1.noarch.rpm` |
| Fedora | `sudo dnf install ./codar-0.1.0-1.noarch.rpm` |
| Arch | `sudo pacman -U ./codar-0.1.0-1-any.pkg.tar.zst` |
| Alpine | `sudo apk add --allow-untrusted ./codar_0.1.0-r1_noarch.apk` |

O pacote traz o comando `codar`, a página de manual (`man codar`), o completar com Tab para bash, zsh e fish, os plugins de Neovim e Vim já ativos e um serviço opcional do systemd (`systemctl --user enable --now codar`). Ele depende só do Python 3.10+ do sistema. A cada mudança, o CI instala o pacote em contêineres limpos de todas essas distros, usa o codar e remove o pacote ([docs/PACKAGING.md](docs/PACKAGING.md)).

### Qualquer sistema com Python 3.10+

```bash
pipx install git+https://github.com/Kelvin-Marques-Cyber/ReAL-Codar
```

### Depois de instalar

```bash
codar run "x é igual a 10"     # o compilador e o banco de padrões já funcionam, sem nada extra
codar extras install           # Studio (IDE no terminal) e IA local, instalados só no seu usuário
codar init                     # configuração e o modelo de IA padrão (~1,1 GB)
codar doctor                   # confere o ambiente e diz o que falta
```

Sem o modelo, só as frases que nem o compilador nem o banco entendem ficam sem resposta, com uma mensagem dizendo como instalar o modelo. Testado em Linux, inclusive Ubuntu Server via SSH. O código também cobre macOS e Windows (Named Pipe, Job Object), mas essas plataformas ainda não têm testes automatizados.

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

![Ajuda do Studio (F1) com os atalhos agrupados](docs/img/ajuda.png)

## Atalhos

Os mesmos gestos em todos os lugares:

| Gesto | O que faz | Onde |
|---|---|---|
| frase + **espaço** + **Enter** | traduz a linha em vez de quebrar a linha (só quando a linha parece uma frase, nunca em código) | Studio, Neovim, Vim, VS Code |
| **Ctrl+Enter** | traduz a linha, ou o bloco selecionado | Studio, Neovim, Vim, VS Code, PowerShell |
| **Ctrl+G** | o mesmo, em terminais que não distinguem Ctrl+Enter | Studio, Neovim, Vim, PowerShell, bash, zsh, fish |
| **Tab** | aceita a sugestão do autocompletar; em `.html`, `.css` e `.jsx` expande abreviações (`ul>li*3`, `a:blank`, `df+jcc`) | Studio |
| **→** | aceita a sugestão (no editor e na barra de intenção) | Studio |
| **Tab** no shell | completa comandos, opções, linguagens, modelos e padrões do `codar` | bash, zsh, fish |

O autocompletar do Studio sugere palavras do próprio arquivo, palavras-chave da linguagem e o vocabulário do pseudocódigo ("imprimir", "enquanto", "senão"…). A barra de intenção sugere o que você já pediu e frases de exemplo.

## Editores e terminais

Todos falam com o mesmo daemon local, que sobe sozinho no primeiro uso.

| Onde | Como ativar |
|---|---|
| **Studio** | `codar studio .` (depois de `codar extras install`) |
| **Neovim** 0.10+ | com o pacote do sistema, o plugin já está instalado: ponha `require("codar").setup()` no `init.lua`. Do repositório: `{ dir = "~/ReAL-Codar/clients/nvim", config = function() require("codar").setup() end }` no lazy.nvim |
| **Vim** 8+ | com o pacote do sistema, já está ativo. Do repositório: `set runtimepath+=~/ReAL-Codar/clients/vim` no `.vimrc` |
| **bash, zsh, fish** | `eval "$(codar shell-init bash)"` no `.bashrc` (Ctrl+G no prompt + completar com Tab) |
| **PowerShell** | `Import-Module /usr/share/codar/powershell/Codar` (pacote) ou `Import-Module ./clients/powershell/Codar` (repositório); depois `cdr "x é igual a 10"` e `Enable-CodarKeyHandler` |
| **Qualquer app** | `codar hook install` mostra como criar um atalho global no seu sistema |
| **VS Code** | `code --install-extension codar.vsix` ([clients/vscode](clients/vscode)) |

No Neovim: `:Codar <intenção>` insere abaixo do cursor, `:CodarAudit` mostra a auditoria como diagnósticos, `:CodarAdvise` abre o consultor, `:CodarStatus` mostra RAM e modelo e `:CodarStudio` abre o Studio numa aba. Detalhes em [clients/nvim](clients/nvim) e [clients/vim](clients/vim).

## Memória: teto de 3 GB

O daemon mede a própria memória (RSS) a cada 2 segundos e age antes de estourar:

- **80% do orçamento**: limpa caches e o estado da IA, mantendo o modelo carregado.
- **92%**: descarrega o modelo. O compilador e o banco continuam respondendo.
- **15 minutos sem uso**: descarrega o modelo e devolve a memória ao sistema.

| Modelo | Arquivo | RAM medida | Acerto* | Licença |
|---|---|---|---|---|
| `qwen2.5-coder-0.5b` | 469 MB | ~0,7 GB | 83% | Apache-2.0 |
| **`qwen2.5-coder-1.5b`** (padrão) | 1066 MB | ~1,3 GB | 88% | Apache-2.0 |
| `qwen2.5-coder-3b` | 2007 MB | ~2,2 GB | 88% | qwen-research (uso não comercial) |

\* pass@1 em 24 tarefas em português, com o código executado contra testes. Detalhes, outros modelos e por que um modelo de 8B não compensa dentro de 3 GB em [docs/BENCHMARKS.md](docs/BENCHMARKS.md).

```bash
codar model list            # modelos, tamanho, RAM estimada e licença
codar model use qwen2.5-coder-0.5b
codar bench --soak 200      # teste de carga: latência por camada, pico de RAM e vazamento
```

O orçamento fica em `[memory] budget_mb` no arquivo de configuração (`codar config path`). No Linux com systemd, o daemon também pede ao sistema um limite rígido de memória quando isso está disponível; o `codar doctor` mostra como ativar.

## Configuração

```bash
codar config path                     # onde fica o config.toml
codar config get model
codar config set model.warm_langs '["python", "powershell"]'
codar restart
```

`warm_langs` define as linguagens que a IA deixa prontas ao carregar. O padrão `["auto"]` aquece as três que você mais usa. O aquecimento roda em segundo plano e cede a vez a qualquer pedido seu.

## Privacidade

Nada sai do seu computador. O daemon escuta só localmente (Unix socket com permissão `0600`, Named Pipe no Windows ou TCP em `127.0.0.1` com token). A rede só é usada por `codar model pull`, `codar extras install` e pelos comandos que você aprova no consultor, como instalar o pnpm.

## Estendendo

Padrões, regras de auditoria, skills e sugestões do consultor são arquivos TOML. Um padrão novo pode trazer testes, e o `patternlint` executa esses testes em cada linguagem antes de aceitar o padrão:

```bash
codar plugins new meu-plugin          # cria a estrutura em ~/.config/codar/plugins/meu-plugin
codar patterns add --title "Ler CSV" --keywords "ler csv arquivo" --code-file ler_csv.py -l python
```

Guia completo em [docs/EXTENDING.md](docs/EXTENDING.md). Arquitetura e protocolo em [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) e [docs/PROTOCOL.md](docs/PROTOCOL.md).

## Desenvolvimento

```bash
git clone https://github.com/Kelvin-Marques-Cyber/ReAL-Codar
cd ReAL-Codar
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,studio]"
pytest                                   # motor, compilador, Emmet, roteamento e completar
python -m codar.evals.patternlint        # sintaxe de cada padrão + testes executáveis
tests/clients/run.sh "$(command -v codar)"   # plugins de Neovim e Vim contra o daemon real
```

Veja [CONTRIBUTING.md](CONTRIBUTING.md) e o [histórico de mudanças](CHANGELOG.md).

## Licença

[Apache 2.0](LICENSE). Os modelos de IA não fazem parte do repositório: são baixados por `codar model pull` e cada um segue a licença do autor (veja a tabela acima).

---

**In English:** CODAR turns line-by-line pseudocode (Portuguese or English) into code in 14 languages, plus Emmet-style HTML and CSS abbreviations. A rule-based compiler, a bank of tested patterns and a small local LLM in "literal" mode run 100% offline within a 3 GB RAM budget. It ships a terminal IDE (works over SSH on Ubuntu Server), Neovim, Vim, PowerShell and VS Code clients, shell completion, a static auditor and a project advisor. Packages for Debian/Ubuntu, Fedora, openSUSE, Arch and Alpine. Apache-2.0 licensed.
