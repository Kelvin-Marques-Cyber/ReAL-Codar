# Validação da versão 0.5.0

Verificações realizadas em Linux com Python 3.13.17, Node.js 22, Rust e Go, em 29/10/2026 (UTC), sobre o commit da versão. Os resultados são locais: o GitHub Actions não atribuiu runners aos jobs (veja [QUALIDADE.md](QUALIDADE.md)).

| Verificação | Resultado |
|---|---|
| Suíte Python completa (`pytest -ra`) | **1569 aprovados, 52 ignorados, 0 falhas**, 145,6 s |
| Cliente VS Code, compilado, contra daemon real (`npm test`) | **8 aprovados, nenhum ignorado** |
| Plugin Vim contra daemon real (`tests/clients/run.sh`) | **35 checagens OK**; Neovim não instalado neste ambiente |
| Banco de padrões (`patternlint`) | 132 padrões; 352 variantes validadas; **158 execuções sem falhas**; nenhum erro de sintaxe |
| Manifestos de versão (`check_versions.py`) | Python, VS Code, PowerShell, Debian, RPM, manual e README sincronizados em 0.5.0 |
| Cenários mínimos de regressão | 8 cenários mapeados para testes existentes, todos aprovados |
| Estudo | 204 verbetes de referência; nenhum exemplo dispara os próprios alertas; 3% das linhas das aulas só com o guia genérico |

Os 52 testes ignorados não são aprovações: faltam os SDKs de Dart, PowerShell e Kotlin, o modelo GGUF (`CODAR_TEST_MODEL`), Xvfb e a execução em contêineres; três casos documentam construções sem equivalente (classes em Bash, listas dinâmicas em C). O patternlint deixou 56 variantes sem validador; 34 padrões não foram executados por falta de bibliotecas científicas (numpy, pandas, cv2, sklearn, matplotlib, PIL), e as variantes PowerShell não foram validadas porque o `pwsh` não está instalado.

## Defeitos encontrados durante a validação

- Variantes Go do patternlint executadas com `go run` perdiam o código de saída: três execuções de `cli.subcommands` falhavam onde há Go instalado, como nos runners do GitHub. Corrigido.
- O Studio podia lançar `NoMatches` ao fechar, quando uma troca de aba do painel chegava depois da desmontagem da tela. Corrigido.
- `tests/test_estudo_multilingue.py` importava `tests.test_estudo`, que falha com `pytest` sem `python -m`. Corrigido.

## Limites da publicação

- Pacotes DEB/RPM/APK/Arch construídos não comprovam instalação nas distribuições: Docker não estava disponível, e a matriz de contêineres não foi repetida.
- Os bundles Windows/macOS são verificados estruturalmente, sem execução nativa.
- Não havia modelo GGUF local: a qualidade das gerações e das edições por IA não foi medida nesta versão; cancelamento, pedidos encadeados e procedência foram testados com backends controlados.
- Os alertas do Estudo analisam a linha do cursor; problemas que dependem do documento inteiro (ids repetidos, ordem dos títulos) continuam na revisão manual e nos desafios estruturais.
- Os exercícios executam código escolhido pelo aluno com limites de tempo e saída; não são uma sandbox.
