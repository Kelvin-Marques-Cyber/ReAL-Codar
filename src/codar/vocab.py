"""Vocabulário compartilhado pelo autocompletar do Studio, do REPL e da ajuda: palavras-chave por linguagem, o
pseudocódigo que o compilador entende e frases de exemplo que funcionam."""

from __future__ import annotations

KEYWORDS: dict[str, tuple[str, ...]] = {
    "python": ("False", "None", "True", "async", "await", "break", "class", "continue", "def", "elif", "else",
               "except", "finally", "import", "lambda", "nonlocal", "global", "pass", "raise", "return", "while",
               "with", "yield", "print", "range", "len", "isinstance", "enumerate", "sorted", "dict", "list"),
    "javascript": ("async", "await", "break", "class", "const", "continue", "default", "export", "extends",
                   "function", "import", "return", "switch", "throw", "typeof", "undefined", "console", "document"),
    "typescript": ("async", "await", "class", "const", "export", "extends", "function", "import", "interface",
                   "readonly", "return", "string", "number", "boolean", "undefined", "unknown", "type"),
    "go": ("break", "chan", "const", "continue", "defer", "fallthrough", "func", "import", "interface", "package",
           "range", "return", "select", "struct", "switch", "string", "error", "fmt"),
    "rust": ("break", "const", "continue", "crate", "else", "enum", "false", "impl", "loop", "match", "move", "return",
             "self", "Self", "static", "struct", "trait", "true", "type", "unsafe", "where", "while", "String", "Vec"),
    "powershell": ("Write-Output", "Write-Host", "Get-ChildItem", "Get-Content", "Set-Content", "ForEach-Object",
                   "Where-Object", "Select-Object", "function", "param", "return", "foreach", "switch", "throw"),
    "bash": ("echo", "printf", "local", "readonly", "function", "return", "while", "until", "case", "esac", "then"),
    "kotlin": ("fun", "val", "var", "class", "data", "object", "when", "return", "println", "readln", "listOf",
               "mutableListOf", "mapOf", "repeat", "until", "downTo", "override", "private", "suspend", "import"),
    "swift": ("func", "let", "var", "struct", "class", "enum", "guard", "return", "print", "readLine", "import",
              "extension", "protocol", "switch", "case", "defer", "throws", "async", "await"),
    "dart": ("void", "final", "const", "var", "class", "extends", "return", "print", "import", "async", "await",
             "Future", "List", "Map", "String", "int", "double", "late", "required", "stdin", "stdout"),
    "r": ("function", "return", "library", "print", "cat", "paste0", "length", "seq_len", "data.frame", "list",
          "TRUE", "FALSE", "NULL", "tryCatch", "readLines", "sapply", "lapply", "ggplot"),
    "julia": ("function", "end", "return", "println", "using", "import", "struct", "mutable", "begin", "elseif",
              "push!", "length", "readline", "parse", "global", "local", "nothing", "true", "false"),
}
PSEUDO_WORDS = ("imprimir", "imprima", "mostrar", "enquanto", "senão", "retornar", "retorne", "função", "funcao",
                "igual", "maior", "menor", "adicionar", "remover", "tamanho", "verdadeiro", "falso", "para", "cada",
                "recebe", "vale", "incrementar", "decrementar", "perguntar", "ler", "lista", "dicionário", "classe",
                "criar", "calcular", "soma", "média", "dobro", "metade", "repetir", "vezes", "nomes", "pedidos",
                "total", "resultado", "quantidade", "contador")

EXAMPLES: list[tuple[str, str]] = [
    ("x é igual a 10", "atribuição"), ("se total maior que 100 imprimir 'caro'", "condição"),
    ("para cada nome em nomes imprimir nome", "laço"), ("imprimir o tamanho de pedidos", "expressão"),
    ("criar uma calculadora", "padrão completo do banco"), ("validar cnpj", "padrão brasileiro"),
    ("ul>li.item$*3", "HTML (Tab num .html)"), ("df+jcc+aic", "CSS (Tab num .css)"),
]
