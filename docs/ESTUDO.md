# Estudo offline e cobertura verificável

O material acompanha o código no painel ESTUDO do Studio e também funciona pelo terminal, sem modelo de IA. Explicações, exemplos, práticas e critérios de revisão são distribuídos no pacote. As referências oficiais são links complementares; ler as aulas não exige rede. Executar uma prática exige o runtime, os arquivos e as dependências indicados nela, preparados localmente.

## Percursos, busca e retomada

```console
codar study path --lang html --root .
codar study show html_metadados --lang html --root .
codar study search "formulários" --lang html
codar study mark html_metadados --lang html --root .
codar study resume --lang html --root .
codar study progress --lang html --root . --json
codar study export --root . --file progresso.json
codar study import --root outro-projeto --file progresso.json
```

`path` organiza as aulas disponíveis em módulos e níveis iniciante, intermediário e avançado; informa o ambiente e o projeto de revisão da linguagem. `show` mostra explicação, exemplo, prática, erro comum, revisão, referências e aulas anterior/próxima/relacionadas. A busca ignora acentos e procura nos títulos, explicações e práticas. `resume` apresenta a primeira aula ainda não marcada no percurso do projeto e linguagem escolhidos.

Marcar prática é uma decisão do aluno e não certifica domínio. Aprovações dos desafios ficam separadas sob `exercise.ID`; o percurso as mostra em `validated_exercises`, sem concluir aulas automaticamente. Uma aprovação registra o momento da verificação, não comprova que uma alteração futura no arquivo continua correta. O resultado de `check` contém o SHA-256 do texto avaliado. O aluno deve verificar novamente após editar a solução.

O progresso é salvo por projeto e linguagem, com bloqueio e substituição atômica. A exportação não inclui caminhos do projeto nem código. Importações são mescladas após validação. Se salvar o progresso falhar após a correção, `check` mantém o resultado dos testes e informa o erro de gravação.

## Desafios e correção real

```console
codar study exercises --lang python
codar study exercise fibonacci --lang python
codar study check fibonacci --root . --file solucao.py --json
codar study exercise html_formulario --lang html
codar study check html_formulario --root . --file cadastro.html --json
codar study check css_grade --root . --file estilo.css --json
codar study check sql_totais --root . --file consulta.sql --json
```

`check` detecta a linguagem pelo arquivo. O arquivo deve estar dentro do projeto. O comando executa explicitamente a solução dos desafios de programação; use somente código que você decidiu executar. São usados um snapshot da solução, limite de tempo/saída e encerramento do grupo de processos em caso de excesso. Isso não constitui uma sandbox de segurança ou bloqueio de rede do código do aluno.

| Avaliação | Desafios | Critérios e limites |
| --- | --- | --- |
| Comportamento de programas | `dobro`, `soma`, `ordenar`, `maximo`, `contar_pares`, `fibonacci`, `palavras` | Quatro casos por desafio, incluindo limites e negativos quando aplicáveis; compara saída, não a implementação. Precisa de runtime/compilador local. Ausência de runtime resulta em `skipped`, nunca aprovação. |
| Estrutura HTML | `html_documento`, `html_formulario` | Analisa tags, atributos, associação de rótulos, ids, controles, metadados e navegação requeridos. Ignora tags em comentários/scripts. Não abre navegador e não certifica acessibilidade, layout ou conformidade HTML integral. Para estes desafios, feche explicitamente as tags não vazias. |
| Declarações CSS | `css_grade` | Confere uma regra simples de topo `.galeria`, display, gap e o padrão responsivo declarado no enunciado; ignora comentários/strings e considera sobrescritas do mesmo seletor. Não implementa a cascata completa, `@` ou `!important` e não verifica aparência. |
| Consulta SQLite | `sql_totais` | Executa consulta somente de leitura em banco em memória contra quatro conjuntos, incluindo vazio e valores repetidos. Impede alterações, anexos e funções fora da lista permitida, limitando operações/tempo. O dialeto do desafio é SQLite. |

A CLI lista desafios aplicáveis à linguagem escolhida. YAML e Dockerfile têm projetos e revisão no consumidor; não são anunciados como programas stdin/stdout executáveis. A disponibilidade de C#, compiladores e runtimes específicos deve ser conferida no ambiente; um desafio listado para uma linguagem de programação pode resultar em ausência de executor configurado.

## Cobertura real desta etapa

O catálogo inicial tinha 86 conceitos únicos, muitos reutilizados entre linguagens por tradução determinística. Esta etapa acrescenta 91 aulas específicas, chegando a 177 conceitos únicos. A tabela conta aulas que efetivamente têm exemplo para a linguagem, incluindo material anterior e traduções suportadas. Cada aula nova contém explicação, prática, código, erro comum e critério de revisão. Cada linguagem tem um projeto final proposto com critérios; esses projetos não são automaticamente implementados ou aprovados pelo Codar.

| Linguagem | Antes | Disponíveis | Aulas específicas novas |
| --- | ---: | ---: | ---: |
| Python | 42 | 48 | 6 |
| JavaScript | 27 | 34 | 7 |
| TypeScript | 27 | 34 | 7 |
| Go | 11 | 14 | 3 |
| Rust | 11 | 14 | 3 |
| Java | 10 | 13 | 3 |
| C | 9 | 12 | 3 |
| C++ | 10 | 13 | 3 |
| C# | 10 | 13 | 3 |
| Bash | 9 | 12 | 3 |
| PowerShell | 12 | 15 | 3 |
| Lua | 10 | 13 | 3 |
| Ruby | 10 | 13 | 3 |
| PHP | 10 | 13 | 3 |
| SQL | 2 | 5 | 3 |
| Kotlin | 10 | 13 | 3 |
| Swift | 10 | 13 | 3 |
| Dart | 14 | 17 | 3 |
| R | 14 | 17 | 3 |
| Julia | 11 | 14 | 3 |
| HTML | 2 | 9 | 7 |
| CSS | 2 | 9 | 7 |
| YAML | 2 | 5 | 3 |
| Dockerfile | 2 | 5 | 3 |

HTML inclui documento/semântica, formulários, metadados, imagens, tabelas, mídia, integração com CSS/JS e revisão de um caderno acessível. CSS inclui cascata, caixa, Flexbox, Grid, responsividade/foco, animação com movimento reduzido, tokens/camadas e painel adaptável. JS inclui DOM, eventos, promessas, API testável sem rede, módulos, testes Node e tarefas com armazenamento. TS acrescenta unknown, uniões, genéricos, DOM tipado, serviços assíncronos, strict e domínio independente de framework. Python acrescenta dataclasses, CSV, contrato JSON, asyncio, automação com prévia e relatório monetário testável.

As demais linguagens recebem práticas próprias de dados, erros, memória, concorrência, contratos ou segurança conforme a linguagem, além de projetos de revisão. A estrutura não inventa POO, funções ou concorrência de aplicação para HTML, CSS, SQL, YAML ou Dockerfile.

## Validação e lacunas

Os testes educacionais incluem navegação/retomada pela CLI, persistência e importação, execução de exemplos com runtimes locais, correção de soluções válidas e inválidas, HTML com falsos rótulos/comentários/scripts, CSS com strings/comentários/sobrescritas e consultas SQL maliciosas ou sem fim. O painel Studio é exercitado com Textual e troca entre todas as linguagens. Os resultados da execução de testes devem ser consultados no relatório da alteração; uma gramática sintática opcional não equivale à execução no runtime.

Este material ainda é um currículo em expansão, não um curso exaustivo dos vinte eixos para todas as linguagens. Frameworks específicos, ecossistemas de pacotes, APIs de rede reais, concorrência avançada e avaliações automáticas por projeto precisam de expansão e validação próprias. Navegador, contraste, leitores de tela, multimídia e layout responsivo exigem revisão manual adicional. Não foram acrescentados módulos vazios para cobrir essas lacunas.
