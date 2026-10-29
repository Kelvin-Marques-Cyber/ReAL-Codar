# CODAR 0.5.0 — Estudo linha a linha, pedidos encadeados e procedência

O CODAR continua em fase alfa. Esta versão faz o modo Estudo explicar a linha que você está escrevendo, faz pedidos de continuação editarem a função certa e mostra de onde veio cada resultado.

## O que mudou

- **Estudo linha a linha em HTML e CSS:** o painel F7 explica cada elemento, atributo, tipo de `input`, propriedade, valor, unidade e seletor da linha do cursor, com a especificidade de cada seletor. Alertas apontam problemas visíveis ali: `img` sem `alt`, `button` sem `type`, campo sem rótulo, `a` sem `href`, viewport que bloqueia o zoom, `div` clicável, `iframe` sem `title`, elementos obsoletos, erro de grafia em propriedades e `outline: none`. Dentro de `<script>` e `<style>`, a linha é explicada como JavaScript ou CSS.
- **Construções próprias de 20 linguagens:** 128 verbetes com exemplo na própria linguagem — `#include`, ponteiros e `malloc` em C; `std::vector` e ponteiros inteligentes em C++; LINQ, `async` e tipos anuláveis em C#; coleções e streams em Java; null safety e `when` em Kotlin; `guard let` e `Codable` em Swift; tabelas e `pcall` em Lua; `JOIN`, `WITH` e transações em SQL; `param` e `-WhatIf` em PowerShell; `:=` e goroutines em Go; `Result` e `#[derive]` em Rust, entre outros. Nas linhas das próprias aulas, a explicação apenas pelo guia genérico caiu de 48% para 3%. `codar study explain --file ARQUIVO --line N` mostra o mesmo pela CLI.
- **Pedidos encadeados:** `agora adicione tipagem`, `add type hints`, `añade tipos` ou `transforme em async` editam no Studio somente a função sob o cursor ou a que acabou de ser inserida, em vez de gerar outra função ou reescrever o arquivo. Se várias funções puderem ser o alvo e nada indicar qual, nada é enviado e o pedido fica na barra.
- **Procedência visível:** cada resultado traz `verification` — origem (compilador, banco ou IA), modelo, sintaxe conferida, fontes e se houve teste. Só variantes do banco com teste executável contam como testadas; código da IA aparece sempre como **não testado** (HUD da CLI, `codar run -v` e cartão do Studio).
- **Correções:** o patternlint compila as variantes Go para conferir o código de saída real; o Studio não lança erro ao fechar com uma troca de aba pendente; `#include`, `#[derive]` e `#region` deixam de ser tratados como comentários no Estudo; pedidos equivalentes recebem a mesma classe nos quatro idiomas; métodos Python gerados não anotam `self`.
- **Qualidade e contribuição:** diagnóstico do CI, critérios de liberação e cenários mínimos de regressão em `docs/QUALIDADE.md`; CONTRIBUTING com guias para idiomas humanos, material de estudo e plugins.

## Downloads e atualização

Pacotes DEB/RPM/APK/Arch, wheel e fontes, bundles Python para Windows/macOS, `codar.vsix`, `RELEASE.json` e `SHA256SUMS`. Windows/macOS requerem Python 3.10+ e pipx; não são EXE/DMG autônomos.

```sh
pipx install --force ./codar-0.5.0-py3-none-any.whl
codar --version
codar restart
```

Adicione o Studio com `codar extras install studio` e reabra-o após atualizar. A extensão é instalada separadamente com `code --install-extension codar.vsix --force`.

## Verificações e limites

- **1569 testes Python aprovados; 52 condicionais ignorados; nenhuma falha.**
- **8 testes do cliente VS Code** contra daemon real e **35 checagens do plugin Vim**, sem falhas.
- **158 execuções do banco de padrões sem falhas**; 352 variantes validadas, nenhum erro de sintaxe e 56 variantes sem validador disponível.
- O GitHub Actions continua sem iniciar os jobs (nenhum runner é atribuído); esta publicação foi construída e verificada localmente. A matriz de instalação em contêineres, a execução nativa em Windows/macOS e o plugin Neovim não foram validados.
- Não houve teste com modelo GGUF real: a edição por pedidos encadeados e as gerações da IA foram testadas com backends controlados. A detecção do alvo de pedidos encadeados existe no Studio, ainda não nos clientes VS Code, Neovim e Vim.
- LSP, depurador (DAP) e Git avançado continuam fora do escopo desta versão.

Veja [docs/VALIDACAO_0.5.0.md](VALIDACAO_0.5.0.md), [docs/ESTUDO.md](ESTUDO.md#explicação-linha-a-linha) e [docs/QUALIDADE.md](QUALIDADE.md). `RELEASE.json` identifica o commit exato usado para os pacotes; compare os downloads com `SHA256SUMS`.
