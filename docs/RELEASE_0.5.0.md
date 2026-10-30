# CODAR 0.5.0 — Estudo em mais linguagens, POO e arquivos conectados, estrutura de projetos

O CODAR continua em fase alfa. Esta versão faz o modo Estudo explicar a linha que você está escrevendo em 36 tipos de arquivo, gera POO e imports entre arquivos sem IA, cria a estrutura inicial de projetos, mostra a saída do F5 em qualquer perspectiva e mostra de onde veio cada resultado.

## O que mudou

- **Estudo de mais 12 linguagens:** LaTeX, Markdown, JSON, TOML, XML, Makefile, GraphQL, Protocol Buffers, Terraform, Verilog, VHDL e Solidity têm guia, aulas do básico ao avançado, projeto de revisão e referência da linha do cursor (51 aulas e 136 verbetes; nenhuma linha das aulas fica só com o guia genérico). Os exemplos passam pela ferramenta oficial de cada linguagem: `pdflatex`, `xmllint` com XSD, `protoc`, `make`, `terraform fmt`, o parser do `graphql-js`, `iverilog`/`vvp`, `ghdl` e `solc`. No Studio, F5 compila `.tex` com `pdflatex` e roda Makefiles.
- **Estudo linha a linha em HTML e CSS:** o painel F7 explica cada elemento, atributo, tipo de `input`, propriedade, valor, unidade e seletor da linha do cursor, com a especificidade de cada seletor, e aponta problemas como `img` sem `alt`, campo sem rótulo, `button` sem `type` e viewport que bloqueia o zoom. Dentro de `<script>` e `<style>`, a linha é explicada como JavaScript ou CSS.
- **Construções próprias das linguagens de programação:** 128 verbetes com exemplo na própria linguagem — `#include` e ponteiros em C, `std::vector` em C++, LINQ em C#, null safety em Kotlin, `guard let` em Swift, tabelas em Lua, `JOIN` em SQL, `param` em PowerShell, goroutines em Go, `Result` em Rust, entre outros. Nas linhas das aulas, a explicação apenas pelo guia genérico caiu de 48% para 3%. `codar study explain --file ARQUIVO --line N` mostra o mesmo pela CLI.
- **POO sem IA (Python, JavaScript e TypeScript):** `classe Aluno herda de Pessoa com matricula` lê o construtor da mãe no arquivo ou no projeto e repassa os parâmetros certos; métodos com corpo usam os atributos da classe; objetos e chamadas são conferidos com o construtor e os métodos reais, com explicação quando algo não existe. Os testes executam o código gerado com `python` e `node`.
- **Arquivos conectados:** quando o código gerado usa uma função ou classe de outro arquivo do projeto, o import certo entra junto (Python absoluto, relativo ou layout `src`; ESM ou CommonJS conforme o arquivo). Nomes com mais de uma origem viram nota, sem adivinhar.
- **Estrutura de projeto:** o botão ESTRUTURA, a paleta, a frase `crie a estrutura de um projeto full stack typescript` ou `codar project scaffold` criam pastas e arquivos iniciais de 13 modelos (Full Stack TS e JS, site estático, pacote, API e dados em Python, Go, Rust, Java, C, C++, Dart e LaTeX). A prévia mostra o que será criado; nada existente é sobrescrito e nada é escrito fora da pasta.
- **Terminal e desempenho do Studio:** a saída do F5 aparece também na perspectiva Essencial, com mais espaço útil, e Shift+F9 maximiza o painel. Em arquivos grandes, o realce consulta só a área visível: num arquivo de 6 mil linhas, o custo por tecla que cresce com o tamanho caiu de ~230 ms para ~22 ms.
- **Segurança:** sugestões do consultor e de plugins não escrevem fora do projeto; a prévia na rede não segue links simbólicos nem entrega credenciais; nomes de slot de plugins não viram código; o instalador confere o SHA-256 dos pacotes com o `SHA256SUMS` da Release antes de instalar. Política e limites em [SECURITY.md](../SECURITY.md).
- **Pedidos encadeados:** `agora adicione tipagem`, `add type hints`, `añade tipos` ou `transforme em async` editam no Studio somente a função sob o cursor ou a recém-inserida. Se várias funções puderem ser o alvo e nada indicar qual, nada é enviado.
- **Procedência visível:** cada resultado traz `verification` — origem (compilador, banco ou IA), modelo, sintaxe conferida, fontes e se houve teste. Código da IA aparece sempre como **não testado**.
- **Correções e qualidade:** patternlint compila as variantes Go para conferir o código de saída real; o Studio não lança erro ao fechar com uma troca de aba pendente; pedidos equivalentes recebem a mesma classe nos quatro idiomas. Diagnóstico do CI e critérios de liberação em `docs/QUALIDADE.md`; CONTRIBUTING com guias para idiomas, material de estudo e plugins.

## Downloads e atualização

Pacotes DEB/RPM/APK/Arch, wheel e fontes, bundles Python para Windows/macOS, `codar.vsix`, `RELEASE.json` e `SHA256SUMS`. Windows/macOS requerem Python 3.10+ e pipx; não são EXE/DMG autônomos.

```sh
pipx install --force ./codar-0.5.0-py3-none-any.whl
codar --version
codar restart
```

Adicione o Studio com `codar extras install studio` e reabra-o após atualizar. A extensão é instalada separadamente com `code --install-extension codar.vsix --force`.

## Verificações e limites

- **1986 testes Python aprovados; 52 condicionais ignorados; nenhuma falha.**
- **107 exemplos de estudo** das novas linguagens aprovados pela ferramenta oficial (pdflatex, xmllint, protoc, make, terraform, graphql-js, iverilog, ghdl, solc).
- **8 testes do cliente VS Code** contra daemon real e **35 checagens do plugin Vim**, sem falhas.
- **158 execuções do banco de padrões sem falhas**; 352 variantes validadas, nenhum erro de sintaxe e 56 variantes sem validador disponível.

- O GitHub Actions continua sem iniciar os jobs (nenhum runner é atribuído); esta publicação foi construída e verificada localmente. A matriz de instalação em contêineres, a execução nativa em Windows/macOS e o plugin Neovim não foram validados.
- Não houve teste com modelo GGUF real: gerações e edições da IA foram testadas com backends controlados. POO, imports entre arquivos e estruturas de projeto não usam IA e foram testados executando o código gerado.
- O estudo das demais linguagens de programação (Haskell, Elixir, Scala, Perl, Fortran, entre outras) fica para a próxima versão.
- LSP, depurador (DAP) e Git avançado continuam fora do escopo desta versão.

Veja [docs/VALIDACAO_0.5.0.md](VALIDACAO_0.5.0.md), [docs/ESTUDO.md](ESTUDO.md#explicação-linha-a-linha) e [docs/QUALIDADE.md](QUALIDADE.md). `RELEASE.json` identifica o commit exato usado para os pacotes; compare os downloads com `SHA256SUMS`.
