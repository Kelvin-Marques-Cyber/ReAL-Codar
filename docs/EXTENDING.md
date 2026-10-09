# Estendendo o CODAR

Tudo que o CODAR sabe além do compilador está em arquivos TOML: padrões de código, regras de auditoria, skills (diretrizes para a IA) e sugestões do consultor. Você não precisa escrever Python para ensinar algo novo.

## Onde ficam

```text
src/codar/plugins/<plugin>/          plugins que vêm com o CODAR
~/.config/codar/plugins/<plugin>/    seus plugins (Windows: %APPDATA%\codar\plugins)
  plugin.toml                        nome, versão, descrição
  patterns/*.toml                    padrões de código
  rules.toml                         regras de auditoria
  skills.toml                        diretrizes para a IA
  advice.toml                        sugestões do consultor
```

```bash
codar plugins new meu-plugin    # cria plugin.toml, patterns/exemplo.toml, rules.toml, skills.toml e advice.toml de exemplo
codar plugins list
codar restart                   # o daemon relê os plugins
```

Um plugin desativa-se com `[plugins] disabled = ["nome"]` no `config.toml`. Plugins do usuário não executam Python, a menos que você ative `[plugins] allow_python = true`.

## Padrões

Um padrão é uma solução com boas práticas para um pedido de funcionalidade, em uma ou mais linguagens.

```toml
[[pattern]]
id = "util.media"                          # único; prefixo = área (util, algo, app, br, file…)
title = "Média de uma lista de números"
keywords = "media average mean lista numeros calcular"
require = ["media", "average", "mean"]     # pelo menos uma destas palavras precisa estar na frase
tags = ["math"]

[pattern.code]
python = '''
def media(numeros: list[float]) -> float:
    """Média aritmética; ValueError para lista vazia."""
    if not numeros:
        raise ValueError("lista vazia")
    return sum(numeros) / len(numeros)
'''
javascript = '''
export function media(numeros) {
  if (numeros.length === 0) throw new Error("lista vazia");
  return numeros.reduce((a, b) => a + b, 0) / numeros.length;
}
'''

[pattern.test]
python = '''
assert media([1, 2, 3]) == 2
try:
    media([])
except ValueError:
    pass
else:
    raise AssertionError("lista vazia deveria falhar")
'''
javascript = '''
if (media([1, 2, 3]) !== 2) throw new Error("falhou");
'''
```

**Como o padrão é escolhido.** A frase passa por um léxico bilíngue ("somar", "sum" e "adicionar" viram o mesmo conceito) e é buscada em `title` e `keywords`. O padrão só é aceito quando cobre a maior parte da frase e contém uma palavra de `require`. Escreva `require` com as palavras que *definem* o pedido, não com palavras genéricas como "lista" ou "criar".

**Slots.** Trechos variáveis do código são escritos como `{{nome}}` e precisam de um valor padrão em `slots = { nome = "valor" }`. O CODAR preenche os slots com o que reconhecer na frase: em "frequência de palavras do arquivo livro.txt", o `{{path}}` do padrão `algo.word_frequency` vira `livro.txt`. O valor do slot não conta contra a cobertura da frase.

**Testes.** `[pattern.test]` aceita um teste por linguagem (`python`, `javascript`, `typescript`, `powershell`, `bash`). O teste é anexado ao código e executado; ele passa se terminar sem erro. `<lang>_setup` roda antes do código, para preparar arquivos ou variáveis.

Para programas interativos, use uma **sessão**: a entrada digitada e os trechos que a saída precisa conter, em ordem. A sessão roda em toda linguagem que tiver toolchain na máquina (Python, Node, Java, Go, PowerShell, Bash):

```toml
[pattern.test]
stdin = """2 + 3
10 / 0
q
"""
expect = ["= 5", "Erro: divisão por zero"]
```

Para programas de linha de comando, use **execuções**: argumentos, entrada opcional, o código de saída esperado e os trechos que a saída (stdout + stderr) precisa conter. `langs` restringe uma execução às linguagens que seguem aquela convenção de opções:

```toml
[[pattern.test.runs]]
args = ["adicionar", "comprar pão", "--prioridade", "5"]
expect = ["adicionada: comprar pão (prioridade 5)"]
langs = ["python", "javascript", "go", "bash"]

[[pattern.test.runs]]
args = ["voar"]
status = 2
expect = ["voar"]
```

**Arquivos de projeto.** Com `kind = "file"` e `path = ".gitignore"`, o padrão vira um arquivo: os editores oferecem criá-lo no projeto em vez de inserir o texto no cursor.

**Validação.** Antes de abrir um PR, rode:

```bash
python -m codar.evals.patternlint
```

Ele confere a sintaxe de cada variante (tree-sitter e o parser oficial do PowerShell), imports que faltam (Python e Go), slots declarados e não usados, e executa os testes e as sessões. Um padrão novo precisa terminar com 0 erros e 0 falhas.

## Regras de auditoria

Regras são expressões regulares avaliadas sobre o código com comentários mascarados, sem IA:

```toml
[[rule]]
id = "ORG001"                       # único
pattern = 'print\('
langs = ["python"]                  # omitido = todas
scope = "code"                      # code (padrão) | nostrings (ignora o conteúdo de strings) | all
in_loop = false                     # true = só dentro de laços (ex.: query dentro de for)
severity = "info"                   # info | warning | error | critical
category = "style"
message = "Prefira logging a print em código de produção."
suggestion = "use logging.getLogger(__name__).info(...)"
```

Para Python há também regras sobre a árvore sintática (`src/codar/audit/python_rules.py`), que enxergam escopo e fluxo. Regras específicas de um projeto também podem ir direto no `config.toml`, em `[[audit.rules]]`. Para desativar uma regra: `[audit] disabled = ["SQL104"]`.

## Skills

Consulte as diretrizes carregadas com `codar skills list -l dart` ou `codar skills show flutter.widgets`. Para instalar um plugin local com seus padrões, regras e `skills.toml`, execute `codar plugins install ./pasta-do-plugin` e depois `codar restart`. A pasta precisa ter `plugin.toml`; arquivos inválidos, links simbólicos e destinos existentes são recusados. A validação não executa `plugin.py`.

Skills são diretrizes curtas que entram no prompt da IA quando ela gera código livre (não no modo literal). Ficam em inglês porque modelos pequenos seguem instruções em inglês com mais consistência:

```toml
[[skill]]
id = "python.sql"
langs = ["python"]
triggers = "sql query consulta banco database select insert"   # palavras da frase que ativam a skill
guidance = ["Always use parameterized queries.", "Close cursors with a context manager."]
```

Uma skill com id `<lang>.base` entra sempre para aquela linguagem.

## Sugestões do consultor

Cada sugestão tem um motivo, condições sobre o projeto (`when`) e opções com passos executáveis. O usuário vê o motivo, escolhe a opção e confirma cada passo:

```toml
[[advice]]
id = "python.lint"
title = "Sem linter no projeto Python"
category = "quality"
impact = "medium"
reason = "O Ruff substitui flake8, isort, pyupgrade e parte do bandit (segurança) num único binário muito rápido."
when = { lang = ["python"], missing = ["ruff.toml", ".ruff.toml", ".flake8", "setup.cfg"], toml_missing = { file = "pyproject.toml", keys = ["tool.ruff", "tool.flake8", "tool.pylint"] } }

[[advice.option]]
id = "ruff"
label = "Configurar Ruff"
steps = [
  { write = "ruff.toml", pattern = "file.ruff" },
  { run = "python -m pip install --user ruff", unless = "ruff --version" },
  { run = "ruff check .", allow_fail = true },
]
```

Condições em `when`: `exists`, `missing`, `any`, `lang`, `tool_present`, `lines`, `lines_missing`, `json_missing`, `json_not`, `toml_missing` (com `file` e `keys`). Passos: `run` (comando, com `unless`, `if_tool`, `os`, `allow_fail`), `backup`, `write` (a partir de um padrão ou de `content`), `append`, `json_set`, `pm_add` (instala com o gerenciador de pacotes detectado), `pm_exec` e `note`. Veja `src/codar/plugins/scaffolds/advice.toml` para exemplos completos, como a migração de npm para pnpm ou Bun.

## Ensinando o compilador

Frases que você usa sempre e que hoje vão para a IA podem virar regra do compilador (`src/codar/engine/stage0.py`): elas passam a responder em menos de 1 ms, sem modelo. Toda regra nova precisa de um caso em `tests/test_stage0.py` mostrando a frase e o código esperado em pelo menos duas linguagens.
