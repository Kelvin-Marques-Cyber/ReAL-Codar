# Protocolo

JSON-RPC 2.0 com **uma mensagem JSON por linha** (UTF-8, terminada em `\n`), sobre o transporte local do daemon.

## Descobrindo o daemon

O daemon grava `endpoint.json` no diretório de execução ao subir e o apaga ao sair:

| Sistema | Diretório |
|---|---|
| Linux | `$XDG_RUNTIME_DIR/codar/`, ou `/tmp/codar-<uid>/` |
| macOS | `$TMPDIR/codar-<uid>/` |
| Windows | `%LOCALAPPDATA%\codar\run\` |
| qualquer um | `$CODAR_HOME/run/`, se `CODAR_HOME` estiver definido |

```json
{"transport": "unix", "address": "/run/user/1000/codar/codar.sock", "token": "", "uri": "unix:/run/user/1000/codar/codar.sock", "pid": 5837, "version": "0.3.2"}
```

`transport` é `unix`, `pipe` (Windows, `\\.\pipe\codar-<usuário>`) ou `tcp` (`127.0.0.1:porta`). A variável `CODAR_ENDPOINT` (`unix:/caminho`, `pipe:\\.\pipe\nome`, `tcp://127.0.0.1:7878`) tem precedência; com TCP, `CODAR_TOKEN` leva o token.

**Autenticação:** só no TCP. A primeira chamada da conexão precisa ser `auth` com o token do `endpoint.json`. Unix sockets e Named Pipes são protegidos pelas permissões do sistema.

## Exemplo

```text
→ {"jsonrpc":"2.0","id":1,"method":"translate","params":{"intent":"x é igual a 10","lang":"python"}}
← {"jsonrpc":"2.0","id":1,"result":{"code":"x = 10","body":"x = 10","imports":[],"lang":"python","stage":"0","source":"stage0:assign","confidence":1.0,"timings":{"stage0_ms":0.27,"total_ms":0.31},"findings":[],"notes":[], "...": "..."}}
```

Teste rápido no terminal:

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"ping"}' | nc -U -q1 "$XDG_RUNTIME_DIR/codar/codar.sock"
# {"jsonrpc":"2.0","id":1,"result":{"pong":true,"version":"0.3.2","pid":5837}}
```

## `translate`

| Parâmetro | Tipo | Descrição |
|---|---|---|
| `intent` | string | a frase ou o bloco de pseudocódigo |
| `lang` | string? | id ou apelido (`python`, `py`, `ps1`, `cs`, filetype do Neovim, languageId do VS Code). Sem ele, vale a extensão de `context.file` |
| `context.file` | string? | caminho do arquivo (detecção de linguagem) |
| `context.before` | string? | código acima do cursor (até 6000 caracteres); vira contexto da IA e define as variáveis conhecidas |
| `context.after` | string? | código após o alvo (até 3000 caracteres); deve ser preservado |
| `context.selected` | string? | código inteiro a substituir em `edit`; não é truncado, e seleções acima de `router.max_edit_chars` são recusadas |
| `context.indent` | string? | indentação da linha atual, aplicada a todas as linhas do resultado |
| `context.indent_unit` | string? | unidade de indentação do arquivo (`"    "`, `"\t"`) |
| `context.root` | string? | raiz explícita para convenções e referências de `codar.toml`; sem ela, usa os marcadores próximos de `context.file` |
| `options.stages` | int[] | estágios permitidos, padrão `[0, 1, 2]` |
| `options.mode` | string | `auto`, `line`, `block` (pseudocódigo de várias linhas), `insert` ou `edit` (substituição completa da seleção por IA) |
| `options.audit` | bool | roda a auditoria no resultado (padrão `true`) |
| `options.hints` | bool | preenche `annotated` com as dicas como comentários |
| `options.stream` | bool | envia `$/progress` com cada pedaço gerado pela IA |

Resultado: `code` (imports + corpo), `body` (só o corpo, já indentado), `imports` (para o cliente inserir no topo do arquivo), `lang`, `stage` (`0` compilador, `1` banco, `2:pseudo` IA literal, `2:adapt` IA adaptando um padrão, `2:gen` IA livre, `2:tools` composição de padrões), `source`, `confidence`, `timings`, `findings`, `annotated`, `slots`, `candidates`, `file_suggestion` (quando o padrão é um arquivo do projeto, como `.gitignore`) e `notes`.

`2:edit` indica reescrita de código existente e exige S2. `complete=false` indica geração cortada pelo limite de tokens: o cliente deve mostrar a resposta para revisão e preservar o documento. Clientes antigos devem tratar a ausência do campo como `true`. `annotated_body` traz apenas o corpo com dicas (sem imports), para aplicação em editores; `annotated` continua trazendo o código completo.

O cliente deve capturar documento, seleção e posição antes da chamada. Ao aplicar, confere se o documento ainda é o mesmo e não mudou; mover o cursor ou trocar a aba não redefine o alvo. Substituição e imports devem formar uma única operação de desfazer. No modo `edit`, não remova sobreposições da resposta: as partes inalteradas da seleção fazem parte da substituição.

O S2 reserva ao menos a contagem de tokens da seleção mais uma margem para a saída. Reduz referências opcionais primeiro; se não couber, recusa a geração. O limite de mensagem é `daemon.max_request_kb` (2048 KB por padrão); snapshots têm limite individual de 512 KB.

Cada item de `findings`: `id`, `severity` (`info`, `warning`, `error`, `critical`), `category`, `message`, `suggestion`, `line`, `col` e `body_line` (linha dentro de `body`).

## Notificações

| Direção | Método | Parâmetros |
|---|---|---|
| daemon → cliente | `$/progress` | `{"id": <id do pedido>, "delta": "<texto gerado>"}` |
| cliente → daemon | `$/cancelRequest` | `{"id": <id do pedido>}`; o pedido termina com o erro `-32800` |

## Outros métodos

| Método | Parâmetros | Resultado |
|---|---|---|
| `project.search` | `root`, `query`, `file?`, `buffer?`, `names?`, `ai?` | termos, resultados reais com caminho/linha/prévia, arquivos ignorados e indicador de corte |
| `ping` | | `{"pong": true, "version": "0.3.2", "pid": 5837}` |
| `auth` | `token` | `{"ok": true}` |
| `audit` | `code`, `lang`, `hints?` | `{"findings": [...], "ms": 0.4}` |
| `stats` | | memória, modelo, estágios, cache, número de pedidos |
| `history` | `limit?` | últimas traduções |
| `advise` | `root` | `{"facts": {...}, "suggestions": [{"id", "title", "reason", "options": [...]}]}` |
| `patterns.search` | `intent`, `lang?`, `limit?` | candidatos com pontuação |
| `patterns.list` | `lang?`, `query?`, `limit?` | resumo dos padrões |
| `patterns.get` | `id` | padrão completo |
| `patterns.add` | `id`, `title`, `lang`, `code`, `keywords?`, `slots?`, `tags?` | `{"ok": true, "id": ...}` |
| `patterns.remove` | `id` | `{"removed": true}` |
| `model.load`, `model.unload`, `model.info` | | estado do modelo |
| `rules.list`, `skills.list`, `langs.list`, `plugins.list` | | catálogos |
| `cache.clear` | | limpa o cache de respostas |
| `reload` | | relê plugins e configuração |
| `shutdown` | | encerra o daemon |

## Propostas, validação e histórico

Todos estes métodos recebem `root` (pasta absoluta do projeto). Caminhos de arquivo são relativos à raiz, com `/`, sem escapes nem links simbólicos.

| Método | Parâmetros além de `root` | Resultado |
|---|---|---|
| `project.info` | | configuração e lista limitada de arquivos de código |
| `project.context` | `intent`, `file?` | referências e contexto com orçamento limitado |
| `project.edit` | `intent`, `files` (1–8 caminhos distintos) | proposta durável; não altera os arquivos |
| `project.check` | `files?`, `actions?`, `native?`, `timeout?` | validações, saídas de comandos, `ok`, `skipped` |
| `edits.preview` | `path`, `before`, `after` | `diff` e `hunks`, sem criar histórico |
| `edits.validate` | `path`, `before`, `after`, `lang?` | `status`, `validator`, `message`, posição quando disponível |
| `edits.prepare` | `path`, `before`, `after`, `intent?` | guarda o original antes da alteração no buffer; estado `prepared` |
| `edits.commit` | `id` | confirma a operação do cliente; estado `buffer` |
| `edits.record` | `path`, `before`, `after`, `intent?` | snapshot de uma edição já aplicada pelo cliente |
| `edits.list` | `limit?`, `file?` | resumo das últimas edições do projeto |
| `edits.get` | `id` | proposta, originais, diff, trechos e validação |
| `edits.apply` | `id`, `hunks?` | aplica uma proposta `draft`; guarda `applied_changes` e `applied_diff` |
| `edits.restore` | `id` | restaura uma edição `applied` ou `buffer`, se o disco ainda contém seu resultado |
| `edits.recover` | | recupera diários interrompidos; informa conflitos sem apagar mudanças externas |

`project.check.actions` aceita `test`, `analyze` e `format`: executam os comandos configurados, somente quando solicitados. Validação de sintaxe retorna `ok`, `error` ou `skipped`; `skipped` significa ausência do verificador. `ok` em `project.check` significa ausência de erros detectados, não que todas as verificações tenham sido possíveis.

Uma proposta tem `id`, `root`, `status`, `changes=[{path,before,after}]`, `validation`, `notes`, `diff` e `hunks`. `null` representa arquivo ausente. Cada trecho tem `id`, `path`, `start`, `diff` e `opcodes=[tag,a,b,c,d]`; os intervalos são índices de linhas de base zero, com limite final exclusivo. Aplique os opcodes selecionados em ordem inversa ao snapshot, mantendo suas quebras de linha.

Fluxo do editor: gerar → prévia → escolher trechos → validar o documento final → conferir a versão atual → `edits.prepare` → uma substituição com imports → `edits.commit`. Se o documento mudar, não aplique a resposta. Uma preparação não confirmada continua recuperável pelo histórico, mas não pode ser aplicada como proposta de disco.

Estados de disco: `draft` → `applying` → `applied` → `applying` → `restored`. Falhas tentam voltar ao estado anterior; mudanças externas produzem `conflict`. A recuperação é explícita e compara o conteúdo antes de restaurá-lo. A troca de vários arquivos usa um diário, não uma única operação atômica do sistema de arquivos.

## Erros

| Código | Significado |
|---|---|
| `-32700`, `-32600`, `-32601`, `-32602` | erros padrão do JSON-RPC (JSON inválido, pedido inválido, método inexistente, parâmetros inválidos) |
| `-32001` | não autenticado (TCP sem `auth`) |
| `-32002` | ocupado: mais de 8 pedidos simultâneos na mesma conexão |
| `-32003` | modelo indisponível (não instalado ou acima do teto de memória) |
| `-32004` | nenhum estágio resolveu; `data.candidates` traz os padrões mais próximos |
| `-32800` | cancelado |

## Busca de projeto

`project.search` usa busca literal por padrão. `file` restringe o alvo e `buffer` permite buscar alterações não salvas (limite de 512 KiB). `names` inclui nomes de arquivos (padrão true). `ai=true` exige IA local configurada e retorna os termos sugeridos antes dos resultados. O scanner respeita exclusões e limites de leitura do projeto; `truncated=true` indica um limite de arquivos, leitura ou resultados.

```json
{"jsonrpc":"2.0","id":3,"method":"project.search","params":{"root":"/meu/projeto","query":"login","names":true,"ai":false}}
```

Cada resultado traz `path`, `kind` (name/content), `line` (base 1), `col` (base 0, caracteres Unicode), `length`, `text`, `snippet` e `score`. O retorno também traz `query`, `terms`, `files_scanned`, `skipped` e `truncated`. Um resultado de nome aponta para a primeira linha; conteúdo aponta para um trecho encontrado. A busca não modifica arquivos nem executa o conteúdo.
