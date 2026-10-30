# Validação da versão 0.5.0

Verificações realizadas em Linux com Python 3.13.17, Node.js 22, Go 1.24 e Rust 1.97, em 30/10/2026 (UTC), sobre o commit da versão. Os resultados são locais: o GitHub Actions não atribuiu runners aos jobs (veja [QUALIDADE.md](QUALIDADE.md)).

| Verificação | Resultado |
|---|---|
| Suíte Python completa (`pytest -ra`) | **1986 aprovados, 52 ignorados, 0 falhas**, 194,9 s |
| Cliente VS Code, compilado, contra daemon real (`npm test`) | **8 aprovados, nenhum ignorado** |
| Plugin Vim contra daemon real (`tests/clients/run.sh`) | **35 checagens OK**; Neovim não instalado neste ambiente |
| Banco de padrões (`patternlint`) | 132 padrões; 352 variantes validadas; **158 execuções sem falhas**; nenhum erro de sintaxe |
| Manifestos de versão (`check_versions.py --tag v0.5.0`) | Python, VS Code, PowerShell, Debian, RPM, manual, README e changelog sincronizados em 0.5.0 |
| Exemplos de estudo das novas linguagens (`tests/test_estudo_linguagens.py`) | **107 exemplos aprovados pela ferramenta oficial**: pdfTeX 1.40.25 (TeX Live 2023), xmllint (libxml2 2.9.14) com XSD, protoc 3.21.12, GNU Make 4.3, Terraform 1.9.8 (`fmt -check`), graphql-js 16.9.0, Icarus Verilog 12, GHDL 4.1 e solc 0.8.28 (sem erros nem avisos) |
| Estudo | 36 linguagens com guia, aulas e projeto; 264 verbetes de referência; 0% das linhas das aulas das novas linguagens e 3% das demais só com o guia genérico |
| POO, imports entre arquivos e estruturas de projeto | Código gerado executado com `python` e `node`; pontos de entrada das estruturas compilados com `go`, `rustc`, `gcc` e `g++` |
| Cenários mínimos de regressão | 8 cenários mapeados para testes existentes, todos aprovados |

Os testes ignorados não são aprovações: faltam os SDKs de Dart, PowerShell e Kotlin, o modelo GGUF (`CODAR_TEST_MODEL`), Xvfb e a execução em contêineres; três casos documentam construções sem equivalente (classes em Bash, listas dinâmicas em C). Sem as ferramentas de cada linguagem no PATH, os exemplos de estudo correspondentes também são ignorados. O patternlint deixou 56 variantes sem validador; 34 padrões não foram executados por falta de bibliotecas científicas (numpy, pandas, cv2, sklearn, matplotlib, PIL), e as variantes PowerShell não foram validadas porque o `pwsh` não está instalado.

## Defeitos encontrados durante a validação

- Variantes Go do patternlint executadas com `go run` perdiam o código de saída: três execuções de `cli.subcommands` falhavam onde há Go instalado, como nos runners do GitHub. Corrigido.
- O Studio podia lançar `NoMatches` ao fechar, quando uma troca de aba do painel chegava depois da desmontagem da tela. Corrigido.
- `tests/test_estudo_multilingue.py` importava `tests.test_estudo`, que falha com `pytest` sem `python -m`. Corrigido.
- Sob carga, o teste da trilha de bibliotecas consultava um botão antes de a tela terminar de montar (`NoMatches`). O teste agora espera o botão; repetido 5 vezes com a CPU ocupada, sem falhas.
- Dois exemplos de estudo não passavam na ferramenta oficial na primeira versão (um Makefile sem alvo final e um serviço Protobuf que usava mensagens não declaradas). Corrigidos antes da publicação.

## Limites da publicação

- Pacotes DEB/RPM/APK/Arch construídos não comprovam instalação nas distribuições: Docker não estava disponível, e a matriz de contêineres não foi repetida.
- Os bundles Windows/macOS são verificados estruturalmente, sem execução nativa.
- Não havia modelo GGUF local: a qualidade das gerações e das edições por IA não foi medida nesta versão; cancelamento, pedidos encadeados e procedência foram testados com backends controlados.
- Os alertas do Estudo analisam a linha do cursor; problemas que dependem do documento inteiro (ids repetidos, ordem dos títulos) continuam na revisão manual e nos desafios estruturais.
- Os exercícios executam código escolhido pelo aluno com limites de tempo e saída; não são uma sandbox.
- O estudo das demais linguagens de programação (Haskell, Elixir, Scala, Perl, Fortran e outras) não faz parte desta versão.
