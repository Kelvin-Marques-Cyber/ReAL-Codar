# Validação da prévia 0.5.0

Verificações locais em 29/10/2026, Linux x86_64, Python 3.12.14 e Textual 8.2.8. O código funcional corresponde à revisão `bce276c562841774495567f870ef19079a8f748a`; a preparação da versão altera manifestos e documentação. A revisão exata de cada distribuição deve ser consultada no `RELEASE.json` que acompanha os downloads.

## Resultados executados

| Verificação | Resultado |
|---|---|
| Suíte Python completa, `python -m pytest -ra` | **1.557 aprovados, 64 ignorados, 0 falhas**, 1.621 coletados, 247,68 s |
| Cliente VS Code, `npm run compile` e `npm test` | **8 aprovados, 0 falhas, nenhum ignorado**, contra daemon real por TCP local autenticado |
| Empacotamento da extensão, `npm run package` | VSIX 0.5.0 gerado |
| Banco de padrões, `python -m codar.evals.patternlint` | **132 padrões, 342 variantes validadas, 66 sem validador; 152 execuções, 0 erros de sintaxe nas variantes verificadas, 0 falhas** |
| Fixtures de edição, `python -m codar.evals.editbench --reference` | **6 de 6 aprovadas**; verifica os gabaritos, sem avaliar um modelo |
| Versões, `python packaging/check_versions.py --tag v0.5.0` | Python, README, VS Code/lockfile, PowerShell, RPM, Debian, manual e CHANGELOG consistentes |
| Build, `packaging/build.sh`, com nfpm 2.47.0 | Wheel, sdist, DEB, RPM, Alpine APK, Arch, distribuições Python Windows/macOS, VSIX, inventário e checksums gerados |
| Conteúdo das distribuições | **154 arquivos de código/dados** comparados byte a byte com a fonte em cada wheel, sdist e nos quatro pacotes Linux, sem diferenças |
| Distribuições Windows/macOS | Manifestos SHA-256 conferidos pelo instalador com `--verify-only`; wheel e VSIX internos idênticos aos downloads separados |
| Instalação Python em Linux | Wheel instalada por pipx em diretórios isolados; `codar --version` confirmou 0.5.0 e `codar run --local --stages 0,1 --json "x é igual a 10"` produziu `x = 10`, estágio 0 |
| Sintaxe e revisão | `sh -n` nos scripts POSIX de empacotamento/instalação e clientes; `git diff --check` sem erros |
| Memória sem IA | Três processos novos por cenário: mediana RSS **30,75 MiB** no motor local e **66,72 MiB** no Studio headless; [dados completos](benchmarks/memory-0.5.0.json) |

O build preliminar foi conferido antes de registrar estas notas. A distribuição final deve ser reconstruída do commit publicado, com árvore limpa, e ter seu inventário e hashes conferidos novamente. `RELEASE.json.source_revision` identifica o commit; um inventário com `source_dirty: true` ou revisão nula não serve como comprovação de uma publicação final.

## Testes ignorados

| Motivo | Quantidade |
|---|---:|
| Contêineres de distribuições não habilitados | 21 |
| SDK/runtime Dart ausente | 9 |
| SDK/runtime PowerShell ausente | 9 |
| Gramática R indisponível | 8 |
| Kotlin ausente | 7 |
| Go ausente | 3 |
| Construções sem equivalente: classe em Bash e listas dinâmicas em C | 3 |
| Modelo GGUF real não configurado | 2 |
| Clipboard nativo sem Xvfb/xclip | 1 |
| Rust ausente em um exercício executável | 1 |
| **Total** | **64** |

Os testes ignorados não são aprovações. O patternlint também informa bibliotecas científicas opcionais e SDKs ausentes; suas execuções faltantes não entram nas 152 aprovadas. Os números diferem da linha de base anterior em [QUALIDADE.md](QUALIDADE.md) porque os ambientes e as ferramentas disponíveis diferem.

## Limites desta publicação

- O [CI da revisão funcional](https://github.com/Kelvin-Marques-Cyber/ReAL-Codar/actions/runs/40914322185) terminou sem runner e sem passos nos dez jobs. A publicação é **prévia alfa**, de acordo com os critérios do projeto. O CI remoto não está aprovado; a causa administrativa exata não foi verificada nesta sessão.
- Não foram executadas instalação, atualização e remoção pelos gerenciadores de todas as distribuições. A conferência do conteúdo dos pacotes não substitui essa matriz. Docker não está disponível neste ambiente.
- Windows e macOS não foram executados nativamente. Seus arquivos requerem Python 3.10+ e pipx e não são EXE/DMG autônomos. O `.apk` desta publicação é um pacote **Alpine Linux**, não um aplicativo Android.
- O ambiente desta verificação bloqueia sockets Unix. O teste real do cliente usou a alternativa TCP em `127.0.0.1`, com porta escolhida pelo sistema e token de autenticação. Isso não é um defeito demonstrado no transporte Unix do CODAR.
- Os testes Node verificam o cliente, o protocolo e o histórico; não executam a interface em um Extension Host do VS Code.
- Não foi instalado/carregado um modelo GGUF. Respostas controladas em testes e gabaritos do editbench não medem a qualidade da IA. Não há novo percentual de acerto de IA nesta versão.
- A medição de memória exclui modelo, daemon separado, emulador de terminal, servidores de linguagem, builds e programas filhos ativos. Não houve teste comparativo com outras IDEs nem de monorepositório.
- Exercícios e plugins Python não são uma sandbox de segurança. LSP/DAP completos, Git integrado avançado e tradução integral do conteúdo legado continuam fora da cobertura.

O [diagnóstico frente a IDEs](DIAGNOSTICO_IDE_0.5.0.md) detalha os pontos fortes, as lacunas e as prioridades técnicas.
