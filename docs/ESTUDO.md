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

## Estudo diretamente no Studio

O Studio agora oferece **Catálogo**, **Continuar**, **Exercícios**, **Marcar praticado** e **Fontes** na aba ESTUDO. É possível abrir uma aula pelo Catálogo ou retomar a primeira prática pendente pelo botão **Continuar** sem criar um arquivo de código antes. As aulas são apresentadas por nível (iniciante, intermediário, avançado) e módulo, com indicação de prática registrada. Se um arquivo estiver aberto, o painel também continua acompanhando o contexto do editor.

Marcar uma aula como praticada registra somente a atividade declarada pelo aluno no projeto e linguagem atuais. **Não executa nem aprova automaticamente a solução.** Para um desafio com correção automática, utilize **Exercícios** ou `codar study check` com um arquivo escolhido explicitamente. O material, os identificadores e o progresso usam a mesma fonte dos comandos `codar study path` e `codar study resume`.

## Explicação linha a linha

Em arquivos `.html` e `.css`, o painel ESTUDO identifica cada tag ou regra da linha do cursor e mostra o verbete da **referência local**: o que o elemento ou a propriedade faz, um exemplo correto, a prática sugerida, o erro comum e o link do MDN. Logo abaixo, **NESTA LINHA** explica o que está escrito ali: cada atributo e seu valor (`type="number"`, `lang="pt-BR"`, `data-*`), o tipo do `input`, entidades como `&nbsp;`, a especificidade de cada seletor CSS, valores (`display: flex`, `margin: 0 auto`), unidades e funções (`rem`, `fr`, `minmax`, `clamp`).

Os alertas apontam problemas visíveis na própria linha: `img` sem `alt` ou com o nome do arquivo no `alt`, `button` sem `type` dentro de formulário, campo sem rótulo, `a` sem `href`, viewport que bloqueia o zoom, `div` clicável, `iframe` sem `title`, elementos obsoletos, propriedades CSS com erro de grafia (`colr` → `color`) e `outline: none`. Não há alerta para o que depende do documento inteiro, como ids repetidos ou a ordem dos títulos; isso continua na revisão manual e nos desafios `html_documento`/`html_formulario`.

Num `.html`, linhas dentro de `<script>` são explicadas como JavaScript e dentro de `<style>` como CSS; `<script type="application/json">` continua HTML.

As demais linguagens têm uma **referência de construções** com o que cada linha típica faz na forma própria da linguagem: `#include`, `main`, ponteiros, `malloc` e `strtol` em C; `std::vector`, `std::map`, ponteiros inteligentes e algoritmos em C++; `using`, LINQ, `async`/`Task` e tipos anuláveis em C#; coleções, streams e try-with-resources em Java; `val`/`var`, null safety, `when` e `data class` em Kotlin; opcionais, `guard let` e `Codable` em Swift; `final`/`const`, `where`/`map` e construtores em Dart; tabelas, `pcall` e `pairs` em Lua; `<?php`, `strict_types`, `??` e XSS em PHP; `SELECT`, `JOIN`, `WITH`, restrições e transações em SQL; `param`, `-WhatIf` e operadores em PowerShell; `:=`, slices e goroutines em Go; `let mut`, iteradores, `Result` e `#[derive]` em Rust; além de verbetes de Python, JavaScript, Ruby, Julia, R, Bash e Dockerfile. Nas linhas das próprias aulas, a parcela explicada só pelo guia genérico caiu de 48% para 3%.

Em C, C++, C#, Rust e outras linguagens em que `#` abre diretivas ou atributos, `#include` e `#[derive]` são código, não comentário; `# texto` continua sendo um comentário com palavras-chave. Ao todo são 204 verbetes, que ficam no catálogo e na busca (`codar study search "texto alternativo" --lang html`) e não entram na sequência do percurso. Pela CLI:

```bash
codar study explain '<input type="number" id="cpf" name="cpf">' --lang html
codar study explain --file index.html --line 12
codar study show html_ref_img --lang html
```

## Programação orientada a objetos (POO)

O material de POO diferencia **classe**, **instância**, **método**, **atributo**, **construtor**, **herança** e **composição**. No editor Python, uma intenção como `crie um método depositar com valor` precisa estar **dentro da classe**, com recuo. Fora da classe, use `crie uma função depositar com valor`. O compilador S0 cria a **assinatura/esqueleto** do método; implementar o seu comportamento exige instrução adicional ou edição do corpo. Não considere o esqueleto uma solução funcional de negócio.

### POO pelo compilador, sem IA (Python, JavaScript e TypeScript)

| Pedido | Resultado |
|---|---|
| `classe Aluno herda de Pessoa com matricula` | subclasse cujo construtor repassa à mãe exatamente os parâmetros dela (lidos do arquivo ou do projeto); com uma dataclass, `@dataclass class Aluno(Pessoa)`; mãe desconhecida repassa `*args`/`...args`, sem inventar nomes |
| `classe Conta com saldo e métodos depositar(valor) e sacar(valor)` | campos e métodos declarados, com corpo que sinaliza a implementação pendente |
| `método depositar com valor que soma valor ao saldo` (com recuo, dentro da classe) | `self.saldo += valor` / `this.saldo += valor`; também `subtrai … do`, `define … para`, `imprime o saldo`, `retorna o saldo` |
| `objeto ana da classe Pessoa com nome 'Ana' e idade 20` | `ana = Pessoa(nome="Ana", idade=20)`; em JS, `new Pessoa("Ana", 20)` na ordem do construtor |
| `chame apresentar de ana e guarde em mensagem` | `mensagem = ana.apresentar()` |

Os pedidos são conferidos com as classes reais: um parâmetro que o construtor não tem, um argumento obrigatório faltando ou um método que a classe do objeto não oferece produzem uma explicação com o que existe, em vez de código que falharia ao rodar. Classes de outros arquivos entram com o import certo. As frases também funcionam em inglês e espanhol (`class Aluno extends Pessoa with matricula`, `clase Alumno hereda de Persona con matricula`).

Exemplo mínimo distribuído em dois arquivos:

```python
# receiver.py
class PlaylistExtract:
    def extract(self, url):
        return url
```

```python
# teste.py
from receiver import PlaylistExtract

extractor = PlaylistExtract()
print(extractor.extract("https://exemplo.invalid/lista"))
```

`extract` é um **método de instância**, não um símbolo importável diretamente de `receiver`. Portanto `from receiver import extract` está incorreto para esse exemplo. O Codar deve identificar a diferença e sugerir importar `PlaylistExtract`, sem executar `receiver.py` durante a análise. O usuário precisa conferir o construtor e fornecer seus argumentos reais: uma classe com `__init__(self, token)`, por exemplo, exige um token para criar a instância.

No painel ESTUDO, a trilha detecta campos gerados por `@dataclass`, inclusive o `__init__` implícito. **Shift+F7** pode sugerir um `main.py` demonstrativo; métodos que exigem parâmetros, propriedades e corrotinas não são chamados às cegas. A sugestão nunca garante que código do projeto com dependências externas, argumentos desconhecidos ou efeitos colaterais esteja pronto para produção. Revise e execute o exemplo explicitamente com F5.

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

### Documentos, dados, build, hardware e contratos (0.5.0)

LaTeX, Markdown, JSON, TOML, XML, Makefile, GraphQL, Protocol Buffers, Terraform, Verilog, VHDL e Solidity têm guia, aulas do básico ao avançado, projeto de revisão e referência de construções: 51 aulas e 136 verbetes,
com 0% das linhas das aulas caindo só no guia genérico. Cada exemplo de guia e aula (e os trechos de referência de
JSON, TOML, GraphQL, Protobuf e Terraform) passa pela ferramenta oficial em `tests/test_estudo_linguagens.py` quando
ela está instalada: `pdflatex` (duas compilações, sem referências indefinidas), `xmllint` com o XSD da aula, `protoc`,
`make -n`, `terraform fmt -check`, o parser do `graphql-js`, `iverilog`/`vvp` com os testbenches, `ghdl` com os asserts
e `solc` sem erros nem avisos. No Studio, F5 compila `.tex` com `pdflatex` e roda Makefiles com `make -f`.

Essas linguagens não são programas de entrada e saída: os desafios de comportamento não são listados para elas.
JSON não tem comentários, então Ctrl+/ avisa em vez de inserir texto inválido.

## Validação e lacunas

Os testes educacionais incluem navegação/retomada pela CLI, persistência e importação, execução de exemplos com runtimes locais, correção de soluções válidas e inválidas, HTML com falsos rótulos/comentários/scripts, CSS com strings/comentários/sobrescritas e consultas SQL maliciosas ou sem fim. O painel Studio é exercitado com Textual e troca entre todas as linguagens. Os resultados da execução de testes devem ser consultados no relatório da alteração; uma gramática sintática opcional não equivale à execução no runtime.

Este material ainda é um currículo em expansão, não um curso exaustivo dos vinte eixos para todas as linguagens. Frameworks específicos, ecossistemas de pacotes, APIs de rede reais, concorrência avançada e avaliações automáticas por projeto precisam de expansão e validação próprias. Navegador, contraste, leitores de tela, multimídia e layout responsivo exigem revisão manual adicional. Não foram acrescentados módulos vazios para cobrir essas lacunas.
