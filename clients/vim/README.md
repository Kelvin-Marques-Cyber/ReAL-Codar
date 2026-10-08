# CODAR para Vim

Plugin para Vim 8+ (com `+job` e `+channel`). Ele chama o CLI (`codar run --json`) em segundo plano, então o editor não trava enquanto a IA gera.

## Instalação

**Pacote do sistema:** já está ativo (o plugin fica em `/usr/share/vim/vimfiles`, ou em `/usr/share/vim/site` no openSUSE).

**Do repositório:** no `.vimrc`, `set runtimepath+=~/ReAL-Codar/clients/vim`.

## Atalhos

| Tecla | Modo | O que faz |
|---|---|---|
| frase + espaço + `Enter` | inserção | traduz a linha (só quando ela parece uma frase) |
| `Ctrl+Enter` | normal, visual, inserção | traduz a linha ou o bloco selecionado |
| `Ctrl+G` | normal, visual | o mesmo, em terminais que não distinguem Ctrl+Enter |

## Comandos

| Comando | O que faz |
|---|---|
| `:Codar` / `:'<,'>Codar` | traduz a linha ou o intervalo |
| `:Codar <intenção>` | insere a tradução abaixo do cursor |
| `:CodarAudit` | auditoria do buffer na lista de locais (`:lopen`) |
| `:CodarStatus` | estado do daemon |

## Opções

```vim
let g:codar_cmd = 'codar'           " caminho do CLI, se não estiver no PATH
let g:codar_keymaps = 1             " Ctrl+Enter e Ctrl+G
let g:codar_space_enter = 1         " frase + espaço + Enter traduz a linha
let g:codar_context_lines = 40      " linhas acima do cursor enviadas como contexto
let g:codar_imports = 1             " insere no topo os imports que o código precisa
```
