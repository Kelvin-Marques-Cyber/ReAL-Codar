# CODAR 0.6.0 — Estudo em mais linguagens, POO e arquivos conectados, estrutura de projetos

**Prévia alfa.** Esta versão faz o modo Estudo explicar a linha que você está escrevendo em 36 tipos de arquivo, gera POO e imports entre arquivos sem IA, cria a estrutura inicial de projetos, mostra a saída do F5 em qualquer perspectiva e protege melhor o projeto contra sugestões e pacotes adulterados. Inclui tudo o que veio na [0.5.0](RELEASE_0.5.0.md). A validação foi local em Linux; a matriz remota e a execução nativa em Windows/macOS continuam pendentes.

## O que mudou

- **Estudo de mais 12 linguagens:** LaTeX, Markdown, JSON, TOML, XML, Makefile, GraphQL, Protocol Buffers, Terraform, Verilog, VHDL e Solidity têm guia, aulas do básico ao avançado, projeto de revisão e referência da linha do cursor (51 aulas e 136 verbetes; nenhuma linha das aulas fica só com o guia genérico). Os exemplos passam pela ferramenta oficial de cada linguagem: `pdflatex`, `xmllint` com XSD, `protoc`, `make`, `terraform fmt`, o parser do `graphql-js`, `iverilog`/`vvp`, `ghdl` e `solc`. No Studio, F5 compila `.tex` com `pdflatex` e roda Makefiles.
- **POO sem IA (Python, JavaScript e TypeScript):** `classe Aluno herda de Pessoa com matricula` lê o construtor da mãe no arquivo ou no projeto e repassa os parâmetros certos; métodos com corpo usam os atributos da classe; objetos e chamadas são conferidos com o construtor e os métodos reais, com explicação quando algo não existe. Os testes executam o código gerado com `python` e `node`.
- **Arquivos conectados:** quando o código gerado usa uma função ou classe de outro arquivo do projeto, o import certo entra junto (Python absoluto, relativo ou layout `src`; ESM ou CommonJS conforme o arquivo). Nomes com mais de uma origem viram nota, sem adivinhar.
- **Estrutura de projeto:** o botão ESTRUTURA, a paleta, a frase `crie a estrutura de um projeto full stack typescript` ou `codar project scaffold` criam pastas e arquivos iniciais de 13 modelos (Full Stack TS e JS, site estático, pacote, API e dados em Python, Go, Rust, Java, C, C++, Dart e LaTeX). A prévia mostra o que será criado; nada existente é sobrescrito e nada é escrito fora da pasta.
- **Terminal e desempenho do Studio:** a saída do F5 aparece também na perspectiva Essencial, com mais espaço útil, e Shift+F9 maximiza o painel. Em arquivos grandes, o realce consulta só a área visível: num arquivo de 6 mil linhas, o custo por tecla que cresce com o tamanho caiu de ~230 ms para ~22 ms.
- **Segurança:** sugestões do consultor e de plugins não escrevem fora do projeto; a prévia na rede não segue links simbólicos nem entrega credenciais; nomes de slot de plugins não viram código; o instalador confere o SHA-256 dos pacotes com o `SHA256SUMS` da Release antes de instalar. Política e limites em [SECURITY.md](../SECURITY.md).

## Downloads

| Sistema / uso | Arquivo |
|---|---|
| Debian / Ubuntu | `codar_0.6.0-1_all.deb` |
| openSUSE / Fedora e distribuições RPM | `codar-0.6.0-1.noarch.rpm` |
| Alpine Linux | `codar_0.6.0-r1_noarch.apk` |
| Arch Linux | `codar-0.6.0-1-any.pkg.tar.zst` |
| Windows, com Python/pipx | `codar-0.6.0-windows-python.zip` |
| macOS, com Python/pipx | `codar-0.6.0-macos-python.tar.gz` |
| Python / pipx | `codar-0.6.0-py3-none-any.whl` |
| Código-fonte e receitas de empacotamento | `codar-0.6.0.tar.gz` |
| Extensão VS Code | `codar.vsix` |

`SHA256SUMS` permite conferir a integridade. `RELEASE.json` informa tamanhos, hashes e revisão Git de origem. Pacotes Linux não possuem assinatura de repositório. Windows/macOS requerem **Python 3.10+ e pipx**; não são instaladores EXE/DMG. O APK é para **Alpine**, não Android. Modelos de IA e SDKs são instalados separadamente.

## Atualização

Na pasta onde baixou a wheel:

```sh
pipx install --force ./codar-0.6.0-py3-none-any.whl
codar --version
codar restart
```

`--force` reinstala a distribuição no ambiente do pipx. `--version` deve mostrar 0.6.0; `restart` reinicia um daemon anterior. Feche e reabra o Studio. Para adicionar a interface, use `codar extras install studio`.

A extensão é atualizada separadamente:

```sh
code --install-extension codar.vsix --force
```

`--install-extension` instala o VSIX local; `--force` substitui uma versão anterior. Recarregue a janela do VS Code.

Esta é uma **prévia**: o instalador Linux padrão consulta a última versão estável. Para solicitar explicitamente a 0.6.0, use o arquivo baixado ou `CODAR_VERSION=0.6.0` no processo que executa `packaging/install.sh`, conforme o README.

## Verificação e limites

- **1986 testes Python aprovados, 52 ignorados, nenhuma falha.** As ausências estão discriminadas em `docs/VALIDACAO_0.6.0.md`.
- **107 exemplos de estudo** das novas linguagens aprovados pela ferramenta oficial (pdflatex, xmllint, protoc, make, terraform, graphql-js, iverilog, ghdl, solc).
- **8 testes do cliente VS Code** contra daemon real e **35 checagens do plugin Vim**, sem falhas. Os testes Node não são testes de interface em um Extension Host.
- **158 execuções do banco de padrões sem falhas**; 352 variantes validadas, nenhum erro de sintaxe e 56 variantes sem validador disponível. Seis gabaritos do editbench aprovados; esse modo não avalia a IA.
- Wheel, fontes, VSIX e quatro pacotes Linux construídos. **161 arquivos de código/dados por distribuição** comparados byte a byte com a fonte. Manifestos Windows/macOS e checksums conferidos; instalação pipx isolada testada em Linux.
- **CI remoto sem runner/etapas**, sem aprovação da matriz; não houve validação nativa Windows/macOS nem instalação nas nove imagens Linux. Por isso, a versão permanece prévia alfa.
- Nenhum benchmark de qualidade com modelo GGUF: gerações e edições da IA foram testadas com backends controlados. POO, imports entre arquivos e estruturas de projeto não usam IA e foram testados executando o código gerado. A medição de memória sem IA da 0.5.0 (29/10) registrou medianas de 30,75 MiB no motor e 66,72 MiB no Studio headless, em carga pequena; não é uma comparação com outras IDEs.
- O CODAR tem recursos de edição controlada e estudo offline. **Ainda não apresenta equivalência com VS Code/PyCharm** em análise semântica, depuração, Git e validação multiplataforma: as mudanças desta versão (terminal, desempenho, imports entre arquivos, estruturas) não alteram as lacunas descritas no [diagnóstico frente a IDEs](DIAGNOSTICO_IDE_0.5.0.md). O estudo das demais linguagens de programação (Haskell, Elixir, Scala, Perl, Fortran, entre outras) fica para a próxima versão.

Consulte `docs/VALIDACAO_0.6.0.md`, `docs/DIAGNOSTICO_IDE_0.5.0.md` e `docs/BENCHMARKS.md` na tag da versão. O commit exato dos pacotes consta em `RELEASE.json`.
