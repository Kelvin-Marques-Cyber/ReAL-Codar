# CODAR para Neovim

Escreva a intenção em pseudocódigo e troque a linha pelo código, sem sair do editor. O plugin fala direto com o daemon pelo socket local (libuv), sem criar um processo por tradução. Requer Neovim 0.10+.

## Instalação

**Pacote do sistema** (`.deb`, `.rpm`, Arch, Alpine): o plugin já está em `/usr/share/nvim/site/pack/codar`. Só ative os atalhos no `init.lua`:

```lua
require("codar").setup()
```

**lazy.nvim**, a partir do repositório clonado:

```lua
{ dir = "~/ReAL-Codar/clients/nvim", config = function() require("codar").setup() end }
```

**Manual:** `set runtimepath+=~/ReAL-Codar/clients/nvim` e o mesmo `setup()`.

## Atalhos

| Tecla | Modo | O que faz |
|---|---|---|
| frase + espaço + `Enter` | inserção | traduz a linha (só quando ela parece uma frase; código quebra a linha normalmente) |
| `Ctrl+Enter` | normal, visual, inserção | traduz a linha ou o bloco selecionado |
| `Ctrl+G` | normal, visual | o mesmo, em terminais que não distinguem Ctrl+Enter |
| `Ctrl+G Ctrl+G` | inserção | o mesmo |

O espaço+Enter funciona junto com nvim-cmp, autopairs e afins: o plugin não remapeia o Enter. Ele observa a quebra de linha logo depois que ela acontece e, se for o caso, desfaz a quebra e traduz. Um único `u` desfaz a tradução, incluindo os imports que ela acrescentou.

## Comandos

| Comando | O que faz |
|---|---|
| `:Codar` | traduz a linha (ou o intervalo, em `:'<,'>Codar`) |
| `:Codar <intenção>` | insere a tradução abaixo do cursor, com a indentação da linha |
| `:CodarAudit` | auditoria do buffer como diagnósticos |
| `:CodarAdvise` | consultor de projeto (aplica a opção escolhida num terminal) |
| `:CodarStatus` | RAM, modelo e estado do daemon |
| `:CodarCancel` | cancela a tradução em andamento |
| `:CodarLast` | mostra o último código gerado numa janela |
| `:CodarStudio` | abre o Studio numa aba |
| `:CodarRestart` | reinicia o daemon |

## Opções

```lua
require("codar").setup({
  cmd = "codar",          -- executável usado para subir o daemon e abrir o Studio
  autostart = true,       -- sobe o daemon na primeira tradução
  keymaps = true,         -- Ctrl+Enter e Ctrl+G
  space_enter = true,     -- frase + espaço + Enter traduz a linha
  stages = { 0, 1, 2 },   -- 0 = compilador, 1 = banco de padrões, 2 = IA local
  hints = "diagnostics",  -- diagnostics | comments | both | off
  imports = true,         -- insere no topo do arquivo os imports que o código precisa
  context_lines = 40,     -- linhas acima do cursor enviadas como contexto
})
```

Se o texto mudar enquanto o daemon responde, o plugin não sobrescreve nada: o código abre numa janela ao lado.
