# Validação da prévia 0.5.0

Verificações locais em 30/10/2026, Linux x86_64, Python 3.13.17, Textual 8.2.8, Node.js 22, Go 1.24 e Rust 1.97. A revisão exata de cada distribuição consta no `RELEASE.json` que acompanha os downloads. Os resultados são locais: o GitHub Actions não atribuiu runners aos jobs (veja [QUALIDADE.md](QUALIDADE.md)).

## Resultados executados

| Verificação | Resultado |
|---|---|
| Suíte Python completa, `python -m pytest -ra` | **1986 aprovados, 52 ignorados, 0 falhas**, 194,9 s |
| Cliente VS Code, `npm run compile` e `npm test` | **8 aprovados, 0 falhas, nenhum ignorado**, contra daemon real por socket Unix |
| Plugin Vim, `tests/clients/run.sh` | **35 checagens OK** contra daemon real; Neovim não instalado neste ambiente |
| Banco de padrões, `python -m codar.evals.patternlint` | **132 padrões, 352 variantes validadas, 56 sem validador; 158 execuções, 0 erros de sintaxe, 0 falhas** |
| Exemplos de estudo das novas linguagens, `tests/test_estudo_linguagens.py` | **107 exemplos aprovados pela ferramenta oficial**: pdfTeX 1.40.25 (TeX Live 2023), xmllint (libxml2 2.9.14) com XSD, protoc 3.21.12, GNU Make 4.3, Terraform 1.9.8 (`fmt -check`), graphql-js 16.9.0, Icarus Verilog 12, GHDL 4.1 e solc 0.8.28 (sem erros nem avisos) |
| Estudo | 36 linguagens com guia, aulas e projeto; 264 verbetes de referência; 0% das linhas das aulas das novas linguagens e 3% das demais só com o guia genérico |
| POO, imports entre arquivos e estruturas de projeto | Código gerado executado com `python` e `node`; pontos de entrada das estruturas compilados com `go`, `rustc`, `gcc` e `g++` |
| Versões, `python packaging/check_versions.py --tag v0.5.0` | Python, README, VS Code/lockfile, PowerShell, RPM, Debian, manual e CHANGELOG consistentes |
| Fixtures de edição, `python -m codar.evals.editbench --reference` | **6 de 6 aprovadas**; verifica os gabaritos, sem avaliar um modelo |
| Build, `packaging/build.sh`, com nfpm 2.47.0 | Wheel, sdist, DEB, RPM, Alpine APK, Arch, distribuições Python Windows/macOS, VSIX, `RELEASE.json` (revisão de origem, árvore limpa) e `SHA256SUMS` gerados; `sha256sum -c` sem divergências |
| Conteúdo das distribuições | **161 arquivos de código/dados** comparados byte a byte com a fonte na wheel, no sdist e nos quatro pacotes Linux, sem diferenças |
| Distribuições Windows/macOS | Manifestos SHA-256 conferidos pelo instalador com `--verify-only`; wheel e VSIX internos idênticos aos downloads separados |
| Instalação Python em Linux | Wheel instalada por pipx em diretórios isolados; `codar --version` confirmou 0.5.0 e `codar run --local --stages 0,1 --json "x é igual a 10"` produziu `x = 10`, estágio 0 |
| Sintaxe e revisão | `sh -n` nos 9 scripts POSIX de empacotamento e instalação; `git diff --check` sem erros |
| Memória sem IA (29/10, revisão `bce276c`) | Três processos novos por cenário: mediana RSS **30,75 MiB** no motor local e **66,72 MiB** no Studio headless; [dados completos](benchmarks/memory-0.5.0.json) |
| Cenários mínimos de regressão | 8 cenários mapeados para testes existentes, todos aprovados |

## Testes ignorados

| Motivo | Quantidade |
|---|---:|
| Contêineres de distribuições não habilitados | 21 |
| SDK/runtime Dart ausente | 9 |
| SDK/runtime PowerShell ausente | 9 |
| Kotlin ausente | 7 |
| Construções sem equivalente: classe em Bash e listas dinâmicas em C | 3 |
| Modelo GGUF real não configurado | 2 |
| Clipboard nativo sem Xvfb/xclip | 1 |
| **Total** | **52** |

Os testes ignorados não são aprovações. Sem a ferramenta de cada linguagem no PATH, os exemplos de estudo correspondentes também são ignorados. O patternlint deixou 56 variantes sem validador; 34 padrões não foram executados por falta de bibliotecas científicas (numpy, pandas, cv2, sklearn, matplotlib, PIL), e as variantes PowerShell não foram validadas porque o `pwsh` não está instalado. Os números diferem da linha de base em [QUALIDADE.md](QUALIDADE.md) e da rodada de 29/10 porque os ambientes, as ferramentas disponíveis e o código diferem.

## Defeitos encontrados durante a validação

- Variantes Go do patternlint executadas com `go run` perdiam o código de saída: três execuções de `cli.subcommands` falhavam onde há Go instalado, como nos runners do GitHub. Corrigido.
- O Studio podia lançar `NoMatches` ao fechar, quando uma troca de aba do painel chegava depois da desmontagem da tela. Corrigido.
- `tests/test_estudo_multilingue.py` importava `tests.test_estudo`, que falha com `pytest` sem `python -m`. Corrigido.
- Sob carga, o teste da trilha de bibliotecas consultava um botão antes de a tela terminar de montar (`NoMatches`). O teste agora espera o botão; repetido 5 vezes com a CPU ocupada, sem falhas.
- Dois exemplos de estudo não passavam na ferramenta oficial na primeira versão (um Makefile sem alvo final e um serviço Protobuf que usava mensagens não declaradas). Corrigidos antes da publicação.

## Limites desta publicação

- O CI remoto terminou sem runner e sem passos nos jobs. A publicação é **prévia alfa**, de acordo com os critérios do projeto; a causa administrativa exata não foi verificada.
- Não foram executadas instalação, atualização e remoção pelos gerenciadores de todas as distribuições. A conferência do conteúdo dos pacotes não substitui essa matriz. Docker não está disponível neste ambiente.
- Windows e macOS não foram executados nativamente. Seus arquivos requerem Python 3.10+ e pipx e não são EXE/DMG autônomos. O `.apk` desta publicação é um pacote **Alpine Linux**, não um aplicativo Android.
- Os testes Node verificam o cliente, o protocolo e o histórico; não executam a interface em um Extension Host do VS Code.
- Não foi instalado/carregado um modelo GGUF. Respostas controladas em testes e gabaritos do editbench não medem a qualidade da IA. Não há novo percentual de acerto de IA nesta versão.
- A medição de memória exclui modelo, daemon separado, emulador de terminal, servidores de linguagem, builds e programas filhos ativos, e foi feita antes das mudanças de estudo, POO e terminal desta versão. Não houve teste comparativo com outras IDEs nem de monorepositório.
- Os alertas do Estudo analisam a linha do cursor; problemas que dependem do documento inteiro (ids repetidos, ordem dos títulos) continuam na revisão manual e nos desafios estruturais.
- Exercícios e plugins Python não são uma sandbox de segurança. LSP/DAP completos, Git integrado avançado e tradução integral do conteúdo legado continuam fora da cobertura. O estudo das demais linguagens de programação (Haskell, Elixir, Scala, Perl, Fortran e outras) não faz parte desta versão.

O [diagnóstico frente a IDEs](DIAGNOSTICO_IDE_0.5.0.md) detalha os pontos fortes, as lacunas e as prioridades técnicas.
