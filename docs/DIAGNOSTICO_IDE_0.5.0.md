# Diagnóstico do CODAR 0.5.0 frente a IDEs

Avaliação de 29/10/2026. Código funcional inspecionado em `bce276c562841774495567f870ef19079a8f748a`, com manifestos e documentação preparados para 0.5.0. Os resultados executados nesta rodada estão em [VALIDACAO_0.5.0.md](VALIDACAO_0.5.0.md).

## Parecer

**O CODAR ainda não tem a abrangência nem a robustez comprovada do VS Code ou do PyCharm como ambiente principal de desenvolvimento.** Já oferece recursos úteis de tradução de intenção, estudo offline e edição controlada. As melhorias desta versão estão implementadas; isso não encerra o desenvolvimento nem demonstra equivalência com uma IDE de uso geral.

A recomendação técnica é publicar a 0.5.0 como prévia alfa. Para trabalho profissional com depuração, navegação semântica e controle de versão frequentes, usar a extensão do CODAR dentro de um editor estabelecido oferece hoje o conjunto mais completo. O Studio atende melhor estudo, terminal/SSH e projetos pequenos dentro da cobertura documentada.

## Comparação por capacidade

| Capacidade | CODAR Studio 0.5.0 | VS Code / PyCharm | Avaliação |
|---|---|---|---|
| Edição de arquivos | Abas, busca, autosave opcional, seleção preservada e prévia de alterações | Editores com navegação, múltiplos recursos de edição e serviços de linguagem | Base útil; paridade geral não demonstrada |
| Completar e entender código | Índice estático de símbolos e assinaturas locais; F10 mostra a origem | VS Code oferece serviços semânticos conforme a linguagem/extensão; PyCharm oferece análise e refatorações de Python | Lacuna importante |
| Refatoração | Pedido por intenção com comparação, validação e recuperação; depende da resposta gerada | Renomear, extrair e outras operações orientadas a símbolos e referências | Reescrever com IA não oferece as mesmas garantias semânticas |
| Depuração | F5 executa o arquivo; saída e interrupção no terminal | Breakpoints, passos, pilha e inspeção de estado no depurador | Falta uma integração de depuração no Studio |
| Testes do projeto aberto | Comandos configurados e exercícios verificáveis | Descoberta, execução e depuração de testes integradas, conforme suporte da linguagem | CLI funcional; experiência integrada incompleta |
| Git | Git pode ser usado no terminal; leitura de contexto respeita exclusões do projeto | VS Code integra revisão, staging, commits, branches e resolução de conflitos | Não há painel equivalente no Studio inspecionado |
| Extensões | Plugins TOML, clientes de editores e Python opcional de confiança | Plataformas extensíveis com serviços de linguagem, depuradores e integrações | Extensibilidade existente; compatibilidade e isolamento ainda limitados |
| Remoto | TUI utilizável por SSH e prévia de projeto em rede sob solicitação | VS Code oferece Remote SSH, WSL e Dev Containers | SSH de terminal é útil; não cobre toda essa integração |
| Aprendizagem | Pseudocódigo, trilhas, exercícios, explicações por linha e referências locais | Recursos variam por produto e extensões | Diferencial claro do CODAR; não medido em estudo comparativo |
| IA e operação offline | Compilador e padrões dispensam modelo; IA local opcional | Capacidades de IA dependem da configuração, produto e provedor | Proposta coerente; qualidade da IA real desta versão ainda sem nova medição |

As capacidades de VS Code dependem dos serviços/extensões instalados; as de PyCharm variam por linguagem, edição e configuração. A tabela compara funções documentadas, sem alegar que todas funcionem igualmente em qualquer projeto.

## Evidências no repositório

- [Edição de projeto](../src/codar/editing.py): propostas de um a oito arquivos. [Histórico](../src/codar/workspace.py): comparação do conteúdo atual, aplicação por trechos, gravações atômicas e recuperação de falhas. São proteções reais contra perda de alterações, exercitadas pelos testes de edição e histórico.
- [Índice do Studio](../src/codar/studio/symbols.py): consulta até 300 arquivos do inventário, ignora arquivos acima de 128.000 bytes, limita a leitura acumulada a 2.000.000 bytes e retorna até 1.200 sugestões. Isso limita trabalho e memória, mas deixa símbolos de projetos maiores fora da consulta. Não implementa resolução completa de tipos e referências.
- [Contexto do projeto](../src/codar/project.py): limite de 512.000 bytes por fonte, exclusão de dependências/saídas e rejeição de caminhos externos e links simbólicos como alvos de edição. São escolhas conservadoras; não equivalem a compreender todo o projeto.
- [Procedência](../src/codar/engine/provenance.py): distingue compilador, padrões e IA, expõe o validador e marca resultado da IA como não testado. Sintaxe válida não prova comportamento correto.
- [Terminal](../src/codar/studio/terminal.py): painel de comandos e saída; a própria implementação recomenda F12/shell externo para programas que precisam de terminal completo. Um painel de execução não substitui um emulador completo nem um depurador.
- Não foi encontrada implementação de cliente LSP, integração DAP ou painel Git completo no Studio. A extensão utiliza o ambiente do VS Code; isso não transfere automaticamente essas capacidades ao Studio.

## Confiabilidade e limites da validação

O [CI da revisão inspecionada](https://github.com/Kelvin-Marques-Cyber/ReAL-Codar/actions/runs/40914322185) terminou com dez jobs sem runner e sem etapas. A causa administrativa exata não foi verificada nesta sessão. A falha anterior de cobrança foi relatada no histórico; o dado observável atual é a ausência de execução. O projeto exige a matriz remota aprovada antes de uma versão estável em [QUALIDADE.md](QUALIDADE.md).

Os oito testes Node da extensão validam o cliente/protocolo e o histórico contra um daemon real. Eles não abrem uma janela do VS Code e não demonstram que todos os comandos, atalhos e painéis funcionem no Extension Host. Muitos testes Python usam respostas controladas do modelo: comprovam o fluxo e as proteções, sem medir a capacidade de um GGUF real.

Nesta rodada, três processos novos por cenário mediram mediana de **30,75 MiB** para o motor local e **66,72 MiB** para o Studio headless, sem modelo. [Dados e condições](benchmarks/memory-0.5.0.json). Isso comprova apenas esse cenário pequeno. Não houve medição equivalente de VS Code/PyCharm nem teste de monorepositório, portanto não há base para anunciar uma porcentagem de vantagem de memória, velocidade ou robustez.

Exercícios e comandos executam código local com limites; não são uma sandbox de segurança. Plugins Python opcionais também rodam no processo do daemon. O orçamento de memória do daemon não limita todos os SDKs e processos do projeto.

## Atualização de 30/10/2026

Depois da revisão inspecionada, a 0.5.0 recebeu: saída do F5 visível em todas as perspectivas e painel maximizável;
realce restrito à área visível (num arquivo de 6 mil linhas, o custo por tecla que cresce com o tamanho caiu de ~230 ms
para ~22 ms); imports automáticos de funções e classes de outros arquivos do projeto e POO conferida com as classes
reais, sem IA; estrutura inicial de projetos; estudo de mais 12 linguagens; e correções de segurança no consultor, na
prévia em rede, nos plugins e no instalador. Nada disso muda o parecer: continuam ausentes cliente LSP, depurador
(DAP) e painel Git, e a validação multiplataforma segue pendente.

## Prioridades para aproximar o Studio de uma IDE principal

1. **Restabelecer a validação de distribuição:** executar a matriz CI, Windows/macOS, instalação/atualização/remoção nas distribuições e testes de recuperação; liberar estabilidade só com evidência.
2. **Integrar servidores de linguagem:** definições, referências, diagnósticos, completar por tipo e renomeação de símbolos; começar por Python e TypeScript e testar colisões de nomes entre módulos.
3. **Integrar depuração e testes:** breakpoints, passos, variáveis/pilha e descoberta de testes, aproveitando protocolos e ferramentas já estabelecidos.
4. **Adicionar fluxo Git integrado:** diff, staging por trecho, commits, branches e conflitos, preservando operações do usuário feitas fora do Studio.
5. **Medir uso real:** tarefas de edição com modelo verdadeiro, projetos grandes, sessões prolongadas, cancelamento durante I/O e testes de interface do VS Code em um Extension Host real. Publicar falhas e casos ignorados junto aos acertos.

## Fontes primárias dos comparadores

- [VS Code: recursos do editor, testes, terminal e controle de versão](https://code.visualstudio.com/docs/editing/getting-started/overview)
- [VS Code: IntelliSense e serviços de linguagem](https://code.visualstudio.com/docs/editing/intellisense)
- [VS Code: navegação por símbolos e referências](https://code.visualstudio.com/docs/editing/editingevolved)
- [VS Code: depuração](https://code.visualstudio.com/docs/debugtest/debugging)
- [VS Code: controle de versão](https://code.visualstudio.com/docs/sourcecontrol/overview)
- [VS Code: desenvolvimento remoto](https://code.visualstudio.com/docs/remote/remote-overview)
- [PyCharm: refatorações](https://www.jetbrains.com/help/pycharm/refactoring-source-code.html)
- [PyCharm: depuração](https://www.jetbrains.com/help/pycharm/debugging-code.html)

Não foram executados benchmarks nem testes de interface dos comparadores. As conclusões sobre lacunas resultam da inspeção do CODAR e das capacidades descritas nessas fontes.
