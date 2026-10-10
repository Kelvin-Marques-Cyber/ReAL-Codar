"""Guias nativos e práticas com referências oficiais consultadas em 10/10/2026."""

FONTES = {
    'python': 'https://docs.python.org/3/tutorial/',
    'javascript': 'https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide',
    'typescript': 'https://www.typescriptlang.org/docs/handbook/intro.html',
    'go': 'https://go.dev/tour/', 'rust': 'https://doc.rust-lang.org/book/',
    'java': 'https://dev.java/learn/',
    'c': 'https://gcc.gnu.org/onlinedocs/gcc/Standards.html',
    'cpp': 'https://isocpp.org/std/the-standard',
    'csharp': 'https://learn.microsoft.com/dotnet/csharp/tour-of-csharp/',
    'bash': 'https://www.gnu.org/software/bash/manual/bash.html',
    'powershell': 'https://learn.microsoft.com/powershell/scripting/learn/ps101/00-introduction',
    'lua': 'https://www.lua.org/manual/5.4/', 'ruby': 'https://docs.ruby-lang.org/en/master/',
    'php': 'https://www.php.net/manual/en/langref.php',
    'sql': 'https://www.postgresql.org/docs/current/tutorial.html',
    'kotlin': 'https://kotlinlang.org/docs/basic-syntax.html',
    'swift': 'https://docs.swift.org/swift-book/documentation/the-swift-programming-language/',
    'dart': 'https://dart.dev/language',
    'r': 'https://cran.r-project.org/doc/manuals/r-release/R-intro.html',
    'julia': 'https://docs.julialang.org/en/v1/manual/getting-started/',
    'html': 'https://html.spec.whatwg.org/multipage/', 'css': 'https://www.w3.org/TR/css-flexbox-1/',
    'yaml': 'https://yaml.org/spec/1.2.2/', 'dockerfile': 'https://docs.docker.com/reference/dockerfile/',
}

# Código escrito para a linguagem; não há conversão silenciosa para Python.
GUIAS = {
    'python': ('Blocos, funções e nomes', 'Indentação delimita blocos; def cria uma função e return devolve um valor.',
               'def dobro(x):\n    return x * 2\n\nprint(dobro(10))'),
    'javascript': ('Valores e funções', 'const impede reatribuir o nome; objetos ainda podem ser alterados. Funções podem receber e devolver valores.',
                   'const dobro = (x) => x * 2;\nconsole.log(dobro(10));'),
    'typescript': ('Tipos e execução', 'Tipos são verificados antes da execução. Anotações não validam automaticamente dados vindos da rede.',
                   'function dobro(x: number): number {\n  return x * 2;\n}\nconsole.log(dobro(10));'),
    'go': ('Pacote main e funções', 'Um executável usa package main e func main. Tipos são estáticos; := declara uma variável dentro de funções.',
           'package main\nimport "fmt"\nfunc dobro(x int) int { return x * 2 }\nfunc main() { fmt.Println(dobro(10)) }'),
    'rust': ('Tipos, mutabilidade e posse', 'let cria um vínculo imutável; mut permite alterar. A posse de valores controla o tempo de vida dos recursos.',
             'fn dobro(x: i32) -> i32 { x * 2 }\nfn main() { println!("{}", dobro(10)); }'),
    'java': ('Classes, métodos e ponto de entrada', 'Métodos pertencem a classes. static permite chamar sem criar um objeto; o tipo da resposta aparece antes do nome.',
             'class Exemplo {\n    static int dobro(int x) { return x * 2; }\n    public static void main(String[] args) {\n        System.out.println(dobro(10));\n    }\n}'),
    'c': ('Tipos, funções e memória', 'Funções declaram os tipos de parâmetros e retorno. Arrays e ponteiros exigem cuidado com tamanho e tempo de vida.',
          '#include <stdio.h>\nint dobro(int x) { return x * 2; }\nint main(void) { printf("%d\\n", dobro(10)); return 0; }'),
    'cpp': ('Objetos e duração de recursos', 'Use objetos e containers para gerenciar recursos. Destrutores liberam recursos quando o objeto sai do escopo (RAII).',
            '#include <iostream>\nint dobro(int x) { return x * 2; }\nint main() { std::cout << dobro(10) << "\\n"; }'),
    'csharp': ('Tipos e métodos', 'C# é tipado e roda sobre .NET. Console.WriteLine mostra valores; o exemplo usa uma classe e um Main tradicionais.',
               'using System;\nclass Exemplo {\n    static int Dobro(int x) => x * 2;\n    static void Main() { Console.WriteLine(Dobro(10)); }\n}'),
    'bash': ('Expansão e argumentos', 'O shell expande variáveis antes de chamar comandos. Aspas preservam espaços; funções recebem argumentos em $1, $2 e assim por diante.',
             'dobro() { printf "%s\\n" "$(( $1 * 2 ))"; }\ndobro 10'),
    'powershell': ('Objetos, funções e pipeline', 'Cmdlets devolvem objetos; o pipeline transporta propriedades e valores, não apenas linhas de texto.',
                   'function Get-Dobro { param([int]$Valor) $Valor * 2 }\nGet-Dobro -Valor 10 | Write-Output'),
    'lua': ('Funções e tabelas', 'local limita o escopo; tabelas representam sequências e mapas. Sequências convencionais começam no índice 1.',
            'local function dobro(x)\n  return x * 2\nend\nprint(dobro(10))'),
    'ruby': ('Métodos e objetos', 'Valores são objetos; def define um método. A última expressão é devolvida sem precisar escrever return.',
             'def dobro(x)\n  x * 2\nend\nputs dobro(10)'),
    'php': ('Variáveis e funções', 'Variáveis começam com $. Declare tipos quando ajudam a entender o contrato de uma função.',
            '<?php\nfunction dobro(int $x): int { return $x * 2; }\necho dobro(10), PHP_EOL;'),
    'sql': ('Consulta, filtro e ordenação', 'SQL descreve os dados desejados. SELECT escolhe colunas, WHERE filtra registros e ORDER BY define a ordem.',
            "SELECT nome, idade\nFROM (VALUES ('Ana', 20), ('Bia', 16)) AS pessoas(nome, idade)\nWHERE idade >= 18\nORDER BY nome;"),
    'kotlin': ('val, var e funções', 'val impede reatribuição; var permite. Tipos podem ser inferidos; um tipo com ? permite null.',
               'fun dobro(x: Int): Int = x * 2\nfun main() {\n    val resultado = dobro(10)\n    println(resultado)\n}'),
    'swift': ('Constantes e opcionais', 'let cria constantes e var cria variáveis. Optionals representam ausência e precisam ser tratados antes do uso.',
              'func dobro(_ x: Int) -> Int { x * 2 }\nlet resultado = dobro(10)\nprint(resultado)'),
    'dart': ('Tipos, final e null safety', 'final impede reatribuir; tipos com ? admitem null. main é o ponto de entrada de programas Dart e Flutter.',
             'int dobro(int x) => x * 2;\nvoid main() {\n  final resultado = dobro(10);\n  print(resultado);\n}'),
    'r': ('Vetores e funções', '<- atribui valores. Muitas operações trabalham sobre o vetor inteiro, e índices comuns começam em 1.',
          'dobro <- function(x) x * 2\nvalores <- c(10, 20, 30)\nprint(dobro(valores))'),
    'julia': ('Funções e arrays', 'Funções podem especializar comportamento por tipo. O ponto em dobro.(valores) aplica a função elemento por elemento.',
              'dobro(x) = x * 2\nvalores = [10, 20, 30]\nprintln(dobro.(valores))'),
    'html': ('Estrutura e significado', 'Elementos descrevem o conteúdo. Use títulos, labels e botões semânticos para apoiar navegação e acessibilidade.',
             '<!doctype html>\n<html lang="pt-BR">\n<meta charset="utf-8">\n<title>Meu projeto</title>\n<main><h1>Cadastro</h1>\n<label for="nome">Nome</label>\n<input id="nome" name="nome">\n<button type="button">Salvar</button></main>\n</html>'),
    'css': ('Seletores, propriedades e layout', 'Seletores escolhem elementos; propriedades definem apresentação. Flexbox organiza filhos em uma dimensão.',
            '.lista {\n  display: flex;\n  gap: 1rem;\n  flex-wrap: wrap;\n}\n.lista > button { padding: .5rem 1rem; }'),
    'yaml': ('Mapas, sequências e indentação', 'Mapas usam chave: valor; sequências usam -. Indentação usa espaços e expressa hierarquia; strings ambíguas podem ser colocadas entre aspas.',
             'projeto:\n  nome: "Minha aplicação"\n  ativo: true\n  portas:\n    - 8080\n    - 8081'),
    'dockerfile': ('Imagem, camadas e comando', 'FROM escolhe a base; WORKDIR muda a pasta de trabalho; COPY adiciona arquivos. CMD define o comando padrão do container.',
                   'FROM python:3.13-slim\nWORKDIR /app\nCOPY app.py .\nCMD ["python", "app.py"]'),
}

# Exemplos dos conceitos de dados que também são próprios de R.
EXEMPLOS_R = {
    'dataframe': 'vendas <- data.frame(categoria=c("A", "B"), preco=c(10, 20))\nprint(vendas)\nprint(vendas[vendas$preco > 15, ])',
    'agrupamento': 'vendas <- data.frame(categoria=c("A", "A", "B"), preco=c(10, 20, 5))\nprint(aggregate(preco ~ categoria, data=vendas, FUN=sum))',
    'grafico': 'png("grafico.png")\nbarplot(c(3, 5), names.arg=c("A", "B"))\ndev.off()',
}


def ampliar(C):
    lessons = []
    for lang, (title, text, code) in GUIAS.items():
        lessons.append(C('guia_' + lang, title, 'linguagens', text,
                         'Modifique o exemplo, explique cada linha com suas palavras e confira o resultado.',
                         linha={lang: (r'\S',)}, exemplos={lang: code}, fontes=(FONTES[lang],),
                         erros_comuns='Copiar sintaxe de outra linguagem sem conferir tipos, escopo e forma de execução.',
                         verifique='Você consegue prever o resultado antes de executar? Explique o efeito da sua alteração.'))

    def add(identity, title, lang, text, practice, regex, code, source=None, error='', check=''):
        lessons.append(C(identity, title, 'praticas', text, practice, linha={lang: tuple(regex)},
                         palavras=(identity.replace('_', ' '),), exemplos={lang: code},
                         fontes=(source or FONTES[lang],), erros_comuns=error, verifique=check))

    add('tipos_python', 'Anotações de tipos', 'python',
        'Anotações documentam contratos e ajudam verificadores como mypy. Python não valida esses tipos sozinho ao executar.',
        'Anote uma função de média e teste entradas numéricas e um texto.', [r'def .+->', r':\s*(?:str|int|float|list|dict)\b'],
        'def media(a: float, b: float) -> float:\n    return (a + b) / 2\n\nprint(media(6, 8))',
        error='Esperar que a anotação substitua validação de entrada. Use testes e um verificador quando necessário.')
    add('contexto_python', 'Gerenciadores de contexto', 'python',
        'with garante a finalização do recurso mesmo se o bloco terminar com uma exceção. open fecha o arquivo ao sair.',
        'Leia um arquivo e provoque uma exceção dentro do with; confira se o arquivo é fechado.', [r'^\s*(?:async\s+)?with\b'],
        'with open("notas.txt", encoding="utf-8") as arquivo:\n    linhas = arquivo.readlines()\nprint(len(linhas))',
        'https://docs.python.org/3/library/contextlib.html', error='Guardar a referência e tentar ler depois que o with fechou o arquivo.')
    add('geradores_python', 'Geradores e consumo sob demanda', 'python',
        'yield devolve um item e suspende a função. Um gerador produz valores sob demanda e pode ser esgotado após uma passagem.',
        'Produza os pares de 0 a 20 com yield e percorra o gerador duas vezes.', [r'\byield\b'],
        'def pares(limite):\n    for n in range(limite):\n        if n % 2 == 0:\n            yield n\n\nprint(list(pares(10)))',
        'https://docs.python.org/3/tutorial/classes.html#generators', error='Esperar reutilizar um gerador já esgotado; crie outro.')
    add('testes_python', 'Testes de comportamento', 'python',
        'Um teste compara o comportamento observado com o esperado. Cubra entradas comuns, limites e erros, sem depender da implementação interna.',
        'Acrescente casos com zero, negativos e entrada inválida; rode python -m unittest.', [r'\bunittest\b', r'^\s*def test_', r'\bassert(?:Equal|Raises)?\b'],
        'import unittest\n\ndef dobro(x):\n    return x * 2\n\nclass TestDobro(unittest.TestCase):\n    def test_negativo(self):\n        self.assertEqual(dobro(-2), -4)\n\nif __name__ == "__main__":\n    unittest.main()',
        'https://docs.python.org/3/library/unittest.html', check='O teste falha se você introduzir um erro no cálculo?')
    add('logging_python', 'Logs com nível e contexto', 'python',
        'logging organiza mensagens por nível e destino. Evite registrar senhas e tokens; use parâmetros em vez de montar a mensagem antecipadamente.',
        'Registre o início e o resultado de uma operação usando INFO; registre uma falha com exception.', [r'\blogging\.', r'\blogger\.'],
        'import logging\nlogging.basicConfig(level=logging.INFO)\nlogger = logging.getLogger(__name__)\nlogger.info("Total processado: %s", 10)',
        'https://docs.python.org/3/howto/logging.html')
    add('venv_python', 'Versões e ambientes virtuais', 'python',
        'A versão do interpretador e o ambiente de dependências são escolhas separadas. Um venv é criado por uma versão Python e isola seus pacotes.',
        'Instale duas versões com toolchains install --version e crie um venv separado para cada projeto.', [r'\b(?:venv|sys\.executable)\b'],
        'import sys\nprint(sys.version)\nprint(sys.executable)\nprint(sys.prefix)',
        'https://docs.python.org/3/tutorial/venv.html', error='Usar pip de outro Python. Prefira python -m pip dentro do ambiente escolhido.')
    add('null_safety_dart', 'Dart e valores opcionais', 'dart',
        'String? aceita null; String não aceita. Confira null antes de usar o valor ou forneça um padrão com ??. O operador ! pode falhar em execução.',
        'Alterne entre null e um nome; use ?? e observe a saída.', [r'\b(?:String|int|double|bool|[A-Z]\w*)\?', r'\?\?|\?\.'],
        'void main() {\n  String? nome;\n  print(nome ?? "Visitante");\n}',
        'https://dart.dev/null-safety/understanding-null-safety', error='Usar ! para silenciar um erro sem garantir que o valor existe.')
    add('future_dart', 'Dart Future e await', 'dart',
        'Future representa um resultado que chegará depois. async permite await; uma falha é tratada com try/catch em torno do await.',
        'Crie uma Future que falha e trate a exceção, mostrando uma mensagem.', [r'\b(?:Future|async|await)\b'],
        'Future<int> dobro(int x) async => x * 2;\nFuture<void> main() async {\n  print(await dobro(10));\n}',
        'https://dart.dev/libraries/async/async-await')
    add('flutter_widget', 'Flutter e composição de widgets', 'dart',
        'Widgets descrevem a interface. StatelessWidget usa sua configuração para montar outros widgets; build pode ser chamado muitas vezes.',
        'Crie dois textos e um botão dentro de uma Column. Separe um trecho da tela em outro widget.', [r'\b(?:StatelessWidget|MaterialApp|Scaffold|Widget build)\b'],
        "import 'package:flutter/material.dart';\nvoid main() => runApp(const MaterialApp(home: Tela()));\nclass Tela extends StatelessWidget {\n  const Tela({super.key});\n  @override\n  Widget build(BuildContext context) => const Scaffold(\n    body: Center(child: Text('Olá, CODAR!')),\n  );\n}",
        'https://api.flutter.dev/flutter/widgets/StatelessWidget-class.html', error='Iniciar requisições e efeitos colaterais diretamente em build.')
    add('flutter_estado', 'Flutter estado e ciclo de vida', 'dart',
        'StatefulWidget é imutável; seu objeto State guarda dados mutáveis. setState notifica a mudança. Libere controllers e assinaturas em dispose.',
        'Crie um contador e explique por que o número é guardado em State, não em build.', [r'\b(?:StatefulWidget|setState|initState|dispose)\b'],
        "import 'package:flutter/material.dart';\nclass Contador extends StatefulWidget {\n  const Contador({super.key});\n  @override\n  State<Contador> createState() => _ContadorState();\n}\nclass _ContadorState extends State<Contador> {\n  int valor = 0;\n  @override\n  Widget build(BuildContext context) => TextButton(\n    onPressed: () => setState(() => valor++),\n    child: Text('$valor'),\n  );\n}",
        'https://api.flutter.dev/flutter/widgets/StatefulWidget-class.html', error='Chamar setState após dispose; confira mounted em callbacks assíncronos e cancele o trabalho ao encerrar.')
    add('pipeline_powershell', 'PowerShell pipeline de objetos', 'powershell',
        'Where-Object filtra objetos e Select-Object escolhe propriedades. $_ representa o objeto atual; formatação deve ficar no fim do pipeline.',
        'Filtre processos por consumo e escolha Name e Id; explique por que Format-Table vem por último.', [r'\|', r'\b(?:Where-Object|Select-Object|ForEach-Object)\b'],
        'Get-Process | Where-Object { $_.WorkingSet64 -gt 100MB } |\n    Select-Object Name, Id, WorkingSet64',
        'https://learn.microsoft.com/powershell/module/microsoft.powershell.core/about/about_pipelines',
        error='Aplicar Format-Table antes de filtrar: os objetos de formatação deixam de ser os dados originais.')
    add('erros_powershell', 'PowerShell erros terminantes', 'powershell',
        'try/catch trata erros terminantes. Muitos cmdlets geram erros não terminantes; -ErrorAction Stop permite capturá-los nesse bloco.',
        'Tente ler um arquivo inexistente e mostre uma mensagem no catch.', [r'\b(?:try|catch)\b', r'-ErrorAction\s+Stop'],
        'try {\n    Get-Content ./ausente.txt -ErrorAction Stop\n} catch {\n    Write-Warning $_.Exception.Message\n}',
        'https://learn.microsoft.com/powershell/module/microsoft.powershell.core/about/about_try_catch_finally')
    add('posse_rust', 'Rust empréstimo e posse', 'rust',
        'Um empréstimo &T permite ler sem mover o valor. &mut T permite alterar com acesso exclusivo, conforme as regras do compilador.',
        'Passe uma String por referência a duas funções; depois compare com passar por valor.', [r'&mut\b', r'&\w+', r'\bString::'],
        'fn tamanho(texto: &str) -> usize { texto.len() }\nfn main() {\n    let nome = String::from("Ana");\n    println!("{} {}", tamanho(&nome), nome);\n}',
        'https://doc.rust-lang.org/book/ch04-02-references-and-borrowing.html')
    add('erros_go', 'Go valores de erro', 'go',
        'Funções podem devolver resultado e error. Confira err antes de usar o resultado; err != nil descreve uma falha.',
        'Converta uma entrada inválida com strconv.Atoi e trate err.', [r'\berr\s*!=\s*nil', r'\berror\b'],
        'package main\nimport ("fmt"; "strconv")\nfunc main() {\n    numero, err := strconv.Atoi("10")\n    if err != nil { fmt.Println(err); return }\n    fmt.Println(numero)\n}', 'https://go.dev/tour/methods/19')
    add('html_semantica', 'HTML formulários acessíveis', 'html',
        'label associa o texto ao controle pelo id. Escolha o tipo de input e indique campos obrigatórios; validação no servidor continua necessária.',
        'Monte um formulário com nome e email e navegue usando somente o teclado.', [r'<(?:form|label|input|button)\b'],
        '<form><label for="email">Email</label>\n<input id="email" name="email" type="email" required>\n<button type="submit">Enviar</button></form>',
        error='Usar apenas placeholder como rótulo ou confiar na validação do navegador para segurança.')
    add('css_flex', 'CSS Flexbox e espaçamento', 'css',
        'display: flex cria um contexto de layout. gap define distância entre filhos; flex-wrap permite passar itens à próxima linha.',
        'Altere largura, alinhamento e gap de uma barra de botões.', [r'\b(?:flex|gap|justify-content|align-items)\b'],
        '.acoes { display: flex; gap: 1rem; flex-wrap: wrap; align-items: center; }')
    add('sql_agrupar', 'SQL agrupamento e agregações', 'sql',
        'GROUP BY reúne linhas por chave; COUNT e SUM calculam valores por grupo. HAVING filtra grupos após a agregação.',
        'Conte vendas por categoria e filtre grupos com mais de duas vendas.', [r'\b(?:GROUP BY|HAVING|COUNT\(|SUM\()'],
        'SELECT categoria, COUNT(*) AS quantidade\nFROM vendas\nGROUP BY categoria\nHAVING COUNT(*) > 2\nORDER BY quantidade DESC;',
        error='Selecionar uma coluna que não foi agrupada nem agregada.')
    add('yaml_sequencia', 'YAML sequências e tipos', 'yaml',
        'Cada item da sequência começa com -. A indentação mantém os itens sob a chave. Aspas ajudam a preservar um valor como string.',
        'Adicione dois serviços com nome e porta; explique a diferença entre "8080" e 8080.', [r'^\s*-\s', r'^\s*\w+:'],
        'servicos:\n  - nome: api\n    porta: 8080\n  - nome: site\n    porta: 8081', error='Usar tabs ou indentar itens em níveis diferentes.')
    add('docker_camadas', 'Dockerfile cache e dependências', 'dockerfile',
        'Camadas podem ser reutilizadas até uma instrução ou entrada mudar. Copie o manifesto de dependências antes do código para aproveitar cache.',
        'Separe COPY de requirements.txt e app.py; altere só o código e observe quais camadas são reutilizadas.',
        [r'^\s*(?:FROM|RUN|COPY|WORKDIR|CMD|ENTRYPOINT)\b'],
        'FROM python:3.13-slim\nWORKDIR /app\nCOPY requirements.txt .\nRUN python -m pip install --no-cache-dir -r requirements.txt\nCOPY app.py .\nCMD ["python", "app.py"]', error='Copiar segredos para a imagem ou executar um container como root sem necessidade.')
    add('vetores_r', 'R operações vetorizadas', 'r',
        'Operações como + e > são aplicadas elemento por elemento. Um vetor lógico filtra valores; NA representa um valor ausente.',
        'Filtre valores acima da média e confira o efeito de NA com mean(..., na.rm=TRUE).', [r'\bc\(', r'\bmean\(', r'\bNA\b'],
        'valores <- c(3, 7, 8, 12)\nprint(valores[valores > mean(valores)])', error='Ignorar reciclagem de vetores com comprimentos diferentes.')
    add('broadcast_julia', 'Julia broadcast e índices', 'julia',
        'Operadores e chamadas com ponto aplicam operações elemento por elemento. Arrays convencionais começam em 1; eachindex respeita o array usado.',
        'Compare valores * 2 e valores .* 2; percorra índices com eachindex.', [r'\.\*|\.\+', r'\w+\.\(', r'\beachindex\b'],
        'valores = [3, 7, 8, 12]\nprintln(valores .* 2)\nfor i in eachindex(valores)\n    println(i, ": ", valores[i])\nend')
    return lessons
