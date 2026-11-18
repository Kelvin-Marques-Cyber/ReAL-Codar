# Validação da prévia 0.6.1

Verificações locais em 18/11/2026, Linux x86_64, Python 3.13.17 e Textual 8.2.8. A 0.6.1 muda só a disposição do Studio; o motor, os padrões e o protocolo são os da [0.6.0](VALIDACAO_0.6.0.md).

## Resultados executados

| Verificação | Resultado |
|---|---|
| Suíte Python completa, `python -m pytest -ra` | **2055 aprovados, 52 ignorados, 0 falhas**, 262,8 s. Os ignorados têm os mesmos motivos da [validação da 0.6.0](VALIDACAO_0.6.0.md#testes-ignorados) |
| Disposição, `tests/test_studio_disposicao.py` (11 testes) | Explorer, editor, painel e colunas em 136×35, 120×30, 100×30, 160×46 e 80×24; radar, feed e coluna da direita por tamanho; arrastar a alça (largura) e clicar nela (recolher e expandir), inclusive em sete alturas diferentes da alça da direita; título que recolhe e expande blocos e o painel; arrastar o título do painel; Shift+F9 com altura escolhida; F9; Alt+M; escolhas salvas e restauradas ao reabrir; rótulos curtos na barra de ferramentas |
| Terminal do painel, `tests/test_studio_terminal_saida.py` | A saída do terminal mantém pelo menos 6 linhas em 100×30 e o painel maximiza e volta |
| Versões, `python packaging/check_versions.py --tag v0.6.1` | Python, README, VS Code/lockfile, PowerShell, RPM, Debian, manual e CHANGELOG consistentes em 0.6.1 |

## Antes e depois, medido no Studio

Mesmo projeto, com um arquivo aberto, medido pelo driver de testes do Textual. "Linhas úteis" é a área de conteúdo do explorer.

| Janela | Explorer 0.6.0 | Explorer 0.6.1 | Editor 0.6.0 | Editor 0.6.1 | Coluna da direita |
|---|---|---|---|---|---|
| 136×35 | 1 linha | **17 linhas** | 66×14 | **102×14** | aparecia; agora só pela alça |
| 120×30 | 0 linhas | **14 linhas** | 50×9 | **86×9** | aparecia; agora só pela alça |
| 100×30 | 0 linhas | **14 linhas** (26 colunas) | 68×9 | 72×9 | oculta |
| 80×24 | oculto | oculto | 80×6 | 78×9 | oculta |
| 160×46 | 12 linhas | **24 linhas** | 90×25 | 88×25 | visível |
| 200×55 | 21 linhas | 23 linhas (com o radar) | 130×34 | 128×34 | visível |

Custo de redimensionar, na mesma sequência de 40 redimensionamentos entre 96×28 e 136×35: mediana de 132 a 139 ms na 0.6.0 e de 143 a 145 ms na 0.6.1, em duas rodadas cada, com outros testes rodando ao mesmo tempo. A diferença está dentro do ruído da medição; a 0.6.1 desenha mais conteúdo útil na mesma janela. O tempo é do processo Python sem terminal real: não mede o desenho no Windows Terminal.

## Pendente antes da tag v0.6.1

- Construir os artefatos (`packaging/build.sh`) a partir do commit final e conferir `SHA256SUMS`, `RELEASE.json`, o conteúdo dos pacotes e os pacotes Windows/macOS.
- Rodar de novo os clientes VS Code e Vim contra o daemon, o patternlint e o editbench com a versão 0.6.1. O código que eles exercitam não mudou desde a 0.6.0.
- Instalar a wheel 0.6.1 por pipx em diretórios isolados.

## Limites

- O arrasto das alças e dos títulos foi testado com o mouse simulado do Textual, em Linux. Não houve teste manual no Windows Terminal nem no macOS, onde o suporte a mouse depende do terminal.
- A medição de tempo de redimensionamento não inclui o terminal; numa janela real, o redesenho do emulador pode dominar.
- Os limites da [0.6.0](VALIDACAO_0.6.0.md#limites-desta-publicação) continuam valendo.
