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

## Instalação, compatibilidade e recuperação

```bash
codar plugins validate ./meu-plugin
codar plugins install ./meu-plugin
codar plugins install https://github.com/SEU-USUARIO/SEU-REPO.git --ref v1.0.0 --subdir plugins/meu-plugin
codar plugins info meu-plugin
codar plugins update meu-plugin
codar plugins update meu-plugin ./outra-origem
codar plugins disable meu-plugin
codar plugins enable meu-plugin
codar plugins remove meu-plugin
codar plugins restore meu-plugin
```

O exemplo Git requer uma URL, referência e subpasta existentes. `--ref` aceita branch, tag ou SHA; `info` mostra a revisão obtida. Sem referência fixa, atualizar busca novamente a branch padrão. A instalação valida os TOMLs, nomes, versões, regex e dependências antes de publicar. Recusa links simbólicos e limita o pacote a 1000 arquivos, 20 MB totais, 8 MB por arquivo e 2 MB por TOML.

Um manifesto pode declarar requisitos:

```toml
[plugin]
name = "meu-plugin"
version = "1.0.0"
description = "Convenções da equipe"
requires_codar = ">=0.3.0,<0.4.0"
# requires_plugins = { outro_plugin = ">=1.0.0,<2.0.0" }
```

As faixas aceitam comparações numéricas `>=`, `>`, `<=`, `<`, `==` e `!=`, separadas por vírgula. Não aceitam expressões npm (`^`, `~`, curingas). Instale dependências antes do pacote; ciclos e dependências indisponíveis impedem sua ativação. Nomes embutidos são reservados; um plugin próprio pode sobrescrever ids de padrões existentes sem usar o nome do pacote embutido.

Atualizar valida uma cópia preparada e preserva a instalação anterior se falhar. Se uma instalação gerenciada foi editada diretamente, recusa a atualização para guardar suas mudanças. Mantenha as alterações no repositório de origem ou use a pasta editada como origem de outro plugin. Instalações antigas sem metadados aceitam uma origem explícita.

Atualização e remoção guardam versões nos dados privados do Codar; `restore` recupera a cópia mais recente, mantendo a origem original registrada. Remoção é bloqueada enquanto plugins ativos dependem dele. Um diário recupera trocas interrompidas no próximo início do daemon ou na próxima operação de gestão. Operações pedem recarga ao daemon já iniciado; se não for possível, a CLI pede `codar restart`.

Pacotes declarativos inválidos não entram no banco e não desativam os demais. `allow_python=true` autoriza extensões locais de confiança: exceções comuns de importação são relatadas, mas código Python pode travar, executar comandos ou falhar em código nativo. Essa opção não cria sandbox ou isolamento de processo.

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

Consulte as diretrizes com `codar skills list -l dart` ou `codar skills show flutter.widgets`. Instale um plugin com `codar plugins install ./pasta-do-plugin`; a pasta precisa ter `plugin.toml`. Em `codar.toml`, use `[project] skills = ["flutter.widgets"]` para ativar uma skill por projeto. Ids inexistentes são recusados durante a geração. A validação do pacote não executa seu `plugin.py`.

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
