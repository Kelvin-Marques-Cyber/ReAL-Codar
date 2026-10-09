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
{"transport": "unix", "address": "/run/user/1000/codar/codar.sock", "token": "", "uri": "unix:/run/user/1000/codar/codar.sock", "pid": 5837, "version": "0.2.0"}
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
# {"jsonrpc":"2.0","id":1,"result":{"pong":true,"version":"0.2.0","pid":5837}}
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
| `options.stages` | int[] | estágios permitidos, padrão `[0, 1, 2]` |
| `options.mode` | string | `auto`, `line`, `block` (pseudocódigo de várias linhas), `insert` ou `edit` (substituição completa da seleção por IA) |
| `options.audit` | bool | roda a auditoria no resultado (padrão `true`) |
| `options.hints` | bool | preenche `annotated` com as dicas como comentários |
| `options.stream` | bool | envia `$/progress` com cada pedaço gerado pela IA |

Resultado: `code` (imports + corpo), `body` (só o corpo, já indentado), `imports` (para o cliente inserir no topo do arquivo), `lang`, `stage` (`0` compilador, `1` banco, `2:pseudo` IA literal, `2:adapt` IA adaptando um padrão, `2:gen` IA livre, `2:tools` composição de padrões), `source`, `confidence`, `timings`, `findings`, `annotated`, `slots`, `candidates`, `file_suggestion` (quando o padrão é um arquivo do projeto, como `.gitignore`) e `notes`.

`2:edit` indica reescrita de código existente e exige S2. `complete=false` indica geração cortada pelo limite de tokens: o cliente deve mostrar a resposta para revisão e preservar o documento. Clientes antigos devem tratar a ausência do campo como `true`. `annotated_body` traz apenas o corpo com dicas (sem imports), para aplicação em editores; `annotated` continua trazendo o código completo.

O cliente deve capturar documento, seleção e posição antes da chamada. Ao aplicar, confere se o documento ainda é o mesmo e não mudou; mover o cursor ou trocar a aba não redefine o alvo. Substituição e imports devem formar uma única operação de desfazer. No modo `edit`, não remova sobreposições da resposta: as partes inalteradas da seleção fazem parte da substituição.

Cada item de `findings`: `id`, `severity` (`info`, `warning`, `error`, `critical`), `category`, `message`, `suggestion`, `line`, `col` e `body_line` (linha dentro de `body`).

## Notificações

| Direção | Método | Parâmetros |
|---|---|---|
| daemon → cliente | `$/progress` | `{"id": <id do pedido>, "delta": "<texto gerado>"}` |
| cliente → daemon | `$/cancelRequest` | `{"id": <id do pedido>}`; o pedido termina com o erro `-32800` |

## Outros métodos

| Método | Parâmetros | Resultado |
|---|---|---|
| `ping` | | `{"pong": true, "version": "0.2.0", "pid": 5837}` |
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

## Erros

| Código | Significado |
|---|---|
| `-32700`, `-32600`, `-32601`, `-32602` | erros padrão do JSON-RPC (JSON inválido, pedido inválido, método inexistente, parâmetros inválidos) |
| `-32001` | não autenticado (TCP sem `auth`) |
| `-32002` | ocupado: mais de 8 pedidos simultâneos na mesma conexão |
| `-32003` | modelo indisponível (não instalado ou acima do teto de memória) |
| `-32004` | nenhum estágio resolveu; `data.candidates` traz os padrões mais próximos |
| `-32800` | cancelado |
