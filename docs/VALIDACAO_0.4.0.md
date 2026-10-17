# Validação da versão 0.4.0

Verificações realizadas em Linux com Python 3.12.14, Node.js 24.19.0 e Textual 8.2.8, em 17/10/2026 (UTC). O núcleo funcional foi validado no commit `443115c58984026da56434ba60092bac9bcdde1f`; o commit da tag inclui também as notas finais, instruções de instalação e metadados de empacotamento.

| Verificação | Resultado |
|---|---|
| Suíte Python completa (`pytest -ra`) | **983 aprovados, 57 ignorados**, 234,85 s |
| Cliente VS Code, compilado, contra daemon real por TCP local | **8 aprovados, nenhum ignorado** |
| Banco de padrões (`codar patternlint`) | 131 padrões; 341 variantes validadas; **153 execuções sem falhas**; nenhum erro de sintaxe nas variantes verificadas |
| Manifestos de versão | Python, VS Code, PowerShell, Debian, RPM e manual sincronizados em 0.4.0 |
| Análise estática e sintaxe dos scripts | Pyflakes dos arquivos Python alterados, `git diff --check` e sintaxe de 10 scripts de empacotamento aprovados |
| Studio | Fluxos de bibliotecas, estudo, cancelamento, assinaturas e perspectivas exercitados; telas inspecionadas em 150×42 e 80×24 |
| Distribuição Python | Wheel e sdist construídos; instalação isolada da wheel com versão, tradução ES→JS, inventário, tutorial e exercício executados |
| VS Code | TypeScript compilado e extensão VSIX 0.4.0 empacotada |

Os 57 testes condicionais não são aprovações: faltam a gramática R, os SDKs de Dart/PowerShell/Kotlin e a execução em contêineres. Um caso documenta uma construção sem equivalente em Bash, e dois fazem o mesmo para listas dinâmicas em C. O patternlint deixou 66 variantes sem validador; algumas execuções exigem PowerShell ou bibliotecas científicas opcionais ausentes.

O GitHub Actions não iniciou os jobs desta rodada. Os resultados acima são locais; o CI remoto não está verde. Consulte a aba Actions do repositório antes de integrar o PR. Os pacotes são construídos a partir do commit exato da tag, com os nomes, tamanhos, revisão de origem e SHA-256 registrados em `RELEASE.json` e `SHA256SUMS`.

## Limites da publicação

- Construir pacotes DEB/RPM/APK/Arch não comprova a instalação nas respectivas distribuições. Docker não está disponível neste ambiente; a matriz de instalação/remoção não foi repetida.
- Os bundles Windows/macOS foram verificados estruturalmente, sem execução nativa nesses sistemas. Requerem Python 3.10+ e pipx; não são EXE/DMG autônomos.
- Não havia um modelo GGUF local para validar a qualidade da IA. Cancelamento e proteção contra respostas tardias foram testados com backends controlados. Não há novo benchmark de memória nesta versão.
- Os exercícios executam código explicitamente escolhido com limites de tempo e saída; não constituem uma sandbox de segurança.
- A tradução da interface cobre os recursos descritos em [I18N.md](I18N.md). Conteúdo educacional e mensagens legadas podem manter o idioma original.
- O inventário é estático e limitado; não consulta registros de pacotes para prometer versões mais recentes. O autocompletar usa símbolos e assinaturas locais; não oferece inferência completa de tipos por LSP.

## Relação com o roteiro de melhorias

Esta versão entrega o fluxo de bibliotecas/APIs, trilhas, progresso portável, exercícios verificáveis, distinção entre consulta e edição, cancelamento, base de idiomas, autocompletar estático e perspectivas. Preserva o fluxo de imports precisos e a revisão de edições já existentes.

LSP/DAP completos, integração Git avançada, tradução integral do conteúdo legado e ampliação do catálogo de exercícios continuam como evolução futura. A versão não afirma que todos os itens P2 do roteiro estão concluídos.
