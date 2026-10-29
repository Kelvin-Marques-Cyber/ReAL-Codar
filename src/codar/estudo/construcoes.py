"""Referência de construções por linguagem: o que uma linha típica de cada linguagem faz.

Os conceitos gerais (variável, condição, laço) valem para todas as linguagens, mas não reconhecem a forma própria
de cada uma: #include e ponteiros em C, LINQ em C#, guard let em Swift, tabelas em Lua, JOIN em SQL, param em
PowerShell. Cada verbete tem o padrão da linha, uma explicação, um exemplo na própria linguagem e o erro comum.
Os verbetes ficam no catálogo e na busca, fora da sequência do percurso, como a referência de HTML e CSS.
"""

from __future__ import annotations

from codar.estudo.ampliado import FONTES

_PRATIQUE = "Altere o exemplo, preveja o resultado antes de executar e explique a diferença com suas palavras."

# linguagem -> [(chave, padrões, título, explicação, exemplo, erro comum)]
REFERENCIA: dict[str, list[tuple[str, tuple[str, ...], str, str, str, str]]] = {
    "python": [
        ("decorador", (r"^\s*@\w",), "Decoradores (@)",
         "@decorador acima de uma função ou classe a transforma ao ser definida: @property cria um atributo calculado, "
         "@staticmethod dispensa self, @dataclass gera __init__, __repr__ e __eq__ a partir dos campos anotados. "
         "@dataclass(frozen=True) impede alterar os campos depois de criar o objeto.",
         "from dataclasses import dataclass\n\n@dataclass(frozen=True)\nclass Produto:\n    nome: str\n    preco: float\n\n"
         "    @property\n    def com_imposto(self) -> float:\n        return self.preco * 1.1\n\nprint(Produto(\"Caderno\", 10).com_imposto)", ""),
        ("post_init", (r"\bdef\s+__post_init__\b",), "__post_init__ · validar dataclasses",
         "Numa dataclass, __post_init__ roda logo depois do __init__ gerado: é o lugar para validar ou calcular campos. "
         "Lançar ValueError ali impede criar um objeto inválido.",
         "from dataclasses import dataclass\n\n@dataclass\nclass Produto:\n    nome: str\n    preco: float\n\n"
         "    def __post_init__(self):\n        if not self.nome.strip() or self.preco < 0:\n            raise ValueError(\"produto inválido\")", ""),
        ("async", (r"\basync\s+(?:def|with|for)\b", r"\bawait\b", r"\basyncio\."), "async def, await e asyncio",
         "async def cria uma corrotina; await espera outra corrotina sem bloquear o programa. asyncio.run(main()) inicia "
         "o laço de eventos; asyncio.gather executa várias tarefas ao mesmo tempo e devolve os resultados na ordem pedida.",
         "import asyncio\n\nasync def tarefa(nome, atraso):\n    await asyncio.sleep(atraso)\n    return nome\n\n"
         "async def main():\n    print(await asyncio.gather(tarefa(\"A\", .02), tarefa(\"B\", .01)))\n\nasyncio.run(main())",
         "Chamar uma corrotina sem await: ela não é executada."),
    ],
    "javascript": [
        ("dom", (r"\bdocument\.", r"\.(?:textContent|innerHTML|classList|append|appendChild|querySelector(?:All)?)\b"),
         "DOM · alterar a página",
         "document.querySelector encontra um elemento pelo seletor CSS; textContent troca o texto com segurança; "
         "append e appendChild inserem elementos criados com document.createElement; classList liga e desliga classes. "
         "innerHTML interpreta HTML — com texto vindo do usuário, permite injeção de código.",
         "const lista = document.querySelector(\"#lista\");\nconst item = document.createElement(\"li\");\n"
         "item.textContent = \"Novo item\";\nlista.append(item);\nlista.classList.add(\"atualizada\");",
         "Usar innerHTML com texto digitado pelo usuário."),
    ],
    "dockerfile": [
        ("user", (r"^\s*USER\b",), "USER · executar sem root",
         "USER define o usuário (ou UID:GID) dos comandos seguintes e do container. Rodar como um usuário sem privilégios "
         "reduz o estrago se a aplicação for comprometida; números (10001:10001) funcionam mesmo sem o usuário existir na imagem.",
         "FROM python:3.13-slim\nRUN useradd --uid 10001 --no-create-home app\nWORKDIR /app\nCOPY --chown=10001:10001 app.py .\n"
         "USER 10001:10001\nCMD [\"python\", \"app.py\"]", "Deixar o container rodando como root sem necessidade."),
    ],
    "c": [
        ("include", (r"^\s*#\s*include\b",), "#include · cabeçalhos",
         "#include copia, antes da compilação, as declarações de um cabeçalho: <stdio.h> traz printf e scanf, <string.h> "
         "funções de texto, <stdlib.h> memória e conversões. Entre <> o compilador procura nos cabeçalhos do sistema; "
         "entre aspas, primeiro na pasta do projeto. Incluir o cabeçalho não liga uma biblioteca externa: isso é feito "
         "ao compilar (por exemplo, -lm).",
         "#include <stdio.h>\n#include \"calculos.h\"\n\nint main(void) {\n    printf(\"%d\\n\", soma(2, 3));\n    return 0;\n}",
         "Usar uma função sem incluir seu cabeçalho: o compilador avisa \"implicit declaration\" e o resultado pode sair errado."),
        ("main", (r"\bint\s+main\s*\(",), "main · ponto de entrada",
         "A execução começa em main. int main(void) não recebe argumentos; int main(int argc, char *argv[]) recebe os "
         "da linha de comando (argv[0] é o nome do programa). O valor devolvido vira o código de saída: 0 indica sucesso.",
         "#include <stdio.h>\n\nint main(int argc, char *argv[]) {\n    if (argc < 2) {\n        fprintf(stderr, \"uso: %s NOME\\n\", argv[0]);\n"
         "        return 1;\n    }\n    printf(\"Olá, %s!\\n\", argv[1]);\n    return 0;\n}",
         "Esquecer o return 0 em funções que não são main, ou devolver sucesso quando algo falhou."),
        ("printf", (r"\b(?:printf|fprintf|snprintf|scanf|puts)\s*\(",), "printf e scanf · formatos",
         "printf escreve usando especificadores: %d int, %ld long, %f double, %s texto, %c caractere e %zu size_t; \\n "
         "quebra a linha. scanf lê no formato indicado e recebe o endereço da variável (&n). Confira o retorno de scanf: "
         "é a quantidade de itens lidos com sucesso.",
         "int idade;\nif (scanf(\"%d\", &idade) != 1) {\n    fprintf(stderr, \"número inválido\\n\");\n    return 1;\n}\n"
         "printf(\"Ano que vem: %d\\n\", idade + 1);",
         "Especificador que não corresponde ao tipo (%d com double) ou scanf(\"%s\") sem limite de tamanho."),
        ("strings", (r"\bchar\s+\w+\s*\[", r"\bstr(?:len|cpy|ncpy|cmp|cat|chr)\s*\("), "Arrays de char e strings",
         "Em C, uma string é um array de char terminado por '\\0'. char nome[8] reserva 8 bytes, incluindo o terminador. "
         "strlen conta até o '\\0' e strcmp compara (0 significa iguais). Escrever além do tamanho corrompe a memória: "
         "prefira snprintf, que respeita o limite.",
         "char nome[16];\nsnprintf(nome, sizeof nome, \"%s\", \"Ana\");\nprintf(\"%s tem %zu letras\\n\", nome, strlen(nome));\n"
         "if (strcmp(nome, \"Ana\") == 0) {\n    puts(\"iguais\");\n}",
         "Comparar strings com == (compara endereços) ou esquecer o espaço do '\\0'."),
        ("ponteiros", (r"\b(?:int|char|long|double|float|void|size_t|struct\s+\w+|\w+_t)\s*\*+\s*\w+", r"->"),
         "Ponteiros e endereços",
         "Um ponteiro guarda o endereço de outro valor: int *p = &x faz p apontar para x; *p lê ou altera x. p->campo "
         "acessa o campo de uma struct apontada. Passar um ponteiro permite que a função altere a variável de quem chamou. "
         "Antes de usar, o ponteiro precisa apontar para algo válido (não NULL e não liberado).",
         "void dobrar(int *valor) {\n    *valor *= 2;\n}\n\nint main(void) {\n    int x = 21;\n    dobrar(&x);\n"
         "    printf(\"%d\\n\", x);  /* 42 */\n    return 0;\n}",
         "Usar um ponteiro não inicializado ou depois de free."),
        ("memoria", (r"\b(?:malloc|calloc|realloc|free)\s*\(",), "malloc, calloc e free",
         "Memória dinâmica vem do heap: malloc reserva bytes sem zerar, calloc reserva e zera, realloc muda o tamanho. "
         "Confira se o retorno é NULL e devolva com free quando terminar; cada bloco é liberado uma única vez. "
         "sizeof *ptr calcula o tamanho pelo próprio ponteiro e continua certo se o tipo mudar.",
         "size_t n = 5;\nint *valores = calloc(n, sizeof *valores);\nif (valores == NULL) {\n    return 1;\n}\n"
         "valores[0] = 42;\nfree(valores);\nvalores = NULL;",
         "Esquecer free (vazamento de memória) ou liberar o mesmo bloco duas vezes."),
        ("struct", (r"\bstruct\s+\w+", r"\btypedef\b"), "struct e typedef",
         "struct junta campos de tipos diferentes num só valor; typedef dá um nome curto ao tipo. Acesse os campos com . "
         "(no valor) ou -> (pelo ponteiro).",
         "typedef struct {\n    char nome[32];\n    int idade;\n} Pessoa;\n\nPessoa p = {\"Ana\", 20};\nPessoa *ref = &p;\n"
         "ref->idade++;\nprintf(\"%s %d\\n\", p.nome, p.idade);", ""),
        ("conversao", (r"\bstrto(?:l|ll|ul|d)\s*\(", r"\berrno\b", r"\bato[il]\s*\("), "strtol e errno · conversão segura",
         "strtol converte texto em número e informa onde parou (no ponteiro fim) e se houve estouro (errno == ERANGE). "
         "atoi não informa erros: \"abc\" vira 0 sem aviso.",
         "#include <errno.h>\n#include <stdlib.h>\n\nchar *fim;\nerrno = 0;\nlong n = strtol(\"42abc\", &fim, 10);\n"
         "if (errno == ERANGE || *fim != '\\0') {\n    puts(\"número inválido\");\n}",
         "Usar atoi em entrada do usuário e tratar 0 como valor válido."),
        ("funcao", (r"^\s*(?:static\s+)?(?:int|void|double|float|char|long|bool|size_t)\s+\w+\s*\([^;]*\)\s*\{",),
         "Funções em C",
         "Uma função declara o tipo de retorno, o nome e os parâmetros com tipos: int dobro(int x). void indica que não "
         "devolve valor. Para usar uma função definida mais abaixo ou em outro arquivo, declare antes o protótipo "
         "(int dobro(int x);), normalmente num arquivo .h.",
         "int dobro(int x);  /* protótipo */\n\nint main(void) {\n    printf(\"%d\\n\", dobro(10));\n    return 0;\n}\n\n"
         "int dobro(int x) {\n    return x * 2;\n}",
         "Chamar a função antes de declará-la ou esquecer o tipo dos parâmetros."),
    ],
    "cpp": [
        ("include", (r"^\s*#\s*include\b",), "#include na biblioteca padrão C++",
         "Cada recurso da biblioteca padrão tem seu cabeçalho: <iostream> (std::cout, std::cin), <vector>, <string>, "
         "<map>, <algorithm>, <memory>. Os cabeçalhos herdados de C ganham o prefixo c: <cmath>, <cstdio>. Inclua o "
         "que usar, sem depender de inclusões indiretas.",
         "#include <iostream>\n#include <string>\n#include <vector>\n\nint main() {\n    std::vector<std::string> nomes{\"Ana\", \"Bia\"};\n"
         "    std::cout << nomes.size() << \"\\n\";\n}",
         "Usar #include <bits/stdc++.h>, que não é padrão e torna a compilação lenta."),
        ("main", (r"\bint\s+main\s*\(",), "main · ponto de entrada",
         "A execução começa em main. Em C++, chegar ao fim de main sem return equivale a return 0. Recebe os argumentos "
         "da linha de comando em int main(int argc, char* argv[]).",
         "#include <iostream>\n\nint main(int argc, char* argv[]) {\n    std::cout << \"argumentos: \" << argc - 1 << \"\\n\";\n}", ""),
        ("iostream", (r"\bstd::(?:cout|cin|cerr)\b", r"\bcout\s*<<", r"\bcin\s*>>"), "std::cout e std::cin",
         "<< envia valores para a saída e >> lê da entrada, convertendo para o tipo da variável. \"\\n\" quebra a linha "
         "(std::endl também esvazia o buffer, o que é mais lento). while (std::cin >> x) para no fim da entrada ou num "
         "valor inválido.",
         "int total = 0, x;\nwhile (std::cin >> x) {\n    total += x;\n}\nstd::cout << \"Total: \" << total << \"\\n\";",
         "Não verificar se a leitura deu certo e continuar com um valor lixo."),
        ("vector", (r"\bstd::vector\b", r"\bvector<"), "std::vector · lista dinâmica",
         "Array que cresce: push_back acrescenta, size() conta, [i] acessa sem conferir limites e at(i) confere e lança "
         "exceção. Percorra com for (const auto& v : valores). Algoritmos de <algorithm> recebem o intervalo "
         "begin(), end().",
         "std::vector<int> valores{3, 1, 2};\nvalores.push_back(5);\nstd::sort(valores.begin(), valores.end());\n"
         "for (const auto& v : valores) {\n    std::cout << v << ' ';\n}",
         "Acessar valores[i] com i fora do tamanho: comportamento indefinido, sem erro garantido."),
        ("string_map", (r"\bstd::(?:string|map|unordered_map|set|istringstream)\b",), "std::string, std::map e fluxos de texto",
         "std::string gerencia a memória do texto (compare com ==, junte com +). std::map guarda pares chave→valor "
         "ordenados pela chave; m[chave] cria a chave com valor padrão se ela não existir — para só consultar, use find "
         "ou contains (C++20). std::istringstream lê palavras de um texto como se fosse a entrada.",
         "std::istringstream entrada(\"ana bia ana\");\nstd::map<std::string, int> contagem;\nstd::string palavra;\n"
         "while (entrada >> palavra) {\n    ++contagem[palavra];\n}\nstd::cout << contagem[\"ana\"] << \"\\n\";  // 2",
         "Usar m[chave] num if só para verificar existência: a consulta cria a chave."),
        ("algoritmos", (r"\bstd::(?:sort|find|find_if|count|count_if|accumulate|transform|max_element|min_element|remove_if)\b",),
         "Algoritmos da biblioteca padrão",
         "sort ordena, find procura, count conta, accumulate (em <numeric>) soma e max_element encontra o maior. Recebem "
         "um intervalo de iteradores [início, fim) e, às vezes, uma função lambda com o critério.",
         "#include <algorithm>\n#include <numeric>\n\nstd::vector<int> v{4, 1, 3};\nstd::sort(v.begin(), v.end());\n"
         "int soma = std::accumulate(v.begin(), v.end(), 0);\nauto pares = std::count_if(v.begin(), v.end(), [](int n) { return n % 2 == 0; });",
         "Usar remove_if sem chamar erase depois: os itens só são movidos para o fim."),
        ("ponteiros", (r"\bstd::(?:make_unique|make_shared|unique_ptr|shared_ptr|move)\b", r"\bnullptr\b"),
         "Ponteiros inteligentes e std::move",
         "unique_ptr é o único dono de um objeto e o libera sozinho ao sair de escopo; make_unique cria. std::move "
         "transfere a posse: o original fica vazio (nullptr). shared_ptr permite vários donos com contagem de "
         "referências. Evite new e delete diretos.",
         "auto origem = std::make_unique<int>(42);\nauto destino = std::move(origem);\n"
         "std::cout << *destino << \" \" << (origem == nullptr) << \"\\n\";  // 42 1",
         "Usar o objeto original depois de std::move."),
        ("auto", (r"\bauto\b",), "auto e for de intervalo",
         "auto deixa o compilador deduzir o tipo pela inicialização; o tipo continua fixo. for (const auto& x : lista) "
         "percorre sem copiar; use auto& para alterar os itens.",
         "std::map<std::string, int> idades{{\"Ana\", 20}};\nfor (const auto& [nome, idade] : idades) {\n"
         "    std::cout << nome << \": \" << idade << \"\\n\";\n}", "Usar auto (cópia) quando queria alterar o item original."),
        ("classes", (r"^\s*class\s+\w+", r"^\s*(?:public|private|protected)\s*:"), "Classes em C++",
         "class agrupa dados e funções; membros são private por padrão (em struct, public). O construtor tem o nome da "
         "classe e inicializa membros na lista após os dois-pontos. const depois de um método promete não alterar o objeto.",
         "class Conta {\npublic:\n    explicit Conta(double saldo) : saldo_(saldo) {}\n    double saldo() const { return saldo_; }\n"
         "    void depositar(double v) { if (v > 0) saldo_ += v; }\nprivate:\n    double saldo_;\n};",
         "Deixar membros públicos e alterar o estado sem validação."),
        ("namespace", (r"\busing\s+namespace\b", r"^\s*namespace\s+\w+"), "namespace e using",
         "namespace agrupa nomes para evitar conflitos; std é o da biblioteca padrão. using namespace std; num cabeçalho "
         "espalha todos esses nomes para quem o incluir — prefira std:: explícito ou using std::cout pontual.",
         "namespace loja {\n    double preco_com_desconto(double p) { return p * 0.9; }\n}\n\n"
         "int main() {\n    std::cout << loja::preco_com_desconto(100) << \"\\n\";\n}",
         "Colocar using namespace std; em arquivos .h."),
    ],
    "csharp": [
        ("using", (r"^\s*using\s+[\w.]+\s*;",), "using · namespaces",
         "using System.Linq; permite escrever Where em vez do nome completo. Namespaces organizam tipos; pacotes NuGet são "
         "instalados à parte (dotnet add package NOME). Com implicit usings, projetos novos já incluem os mais comuns.",
         "using System.Collections.Generic;\nusing System.Linq;\n\nvar nomes = new List<string> { \"Ana\", \"Bia\" };\n"
         "Console.WriteLine(nomes.Count(n => n.StartsWith(\"A\")));",
         "Confundir using de namespace com a instrução using que libera recursos (using var arquivo = ...)."),
        ("main", (r"\bstatic\s+(?:async\s+)?(?:void|int|Task(?:<int>)?)\s+Main\s*\(",), "Main · ponto de entrada",
         "Sem top-level statements, a execução começa em static void Main(string[] args). Com async Task Main é possível "
         "usar await. Em projetos novos, o código pode ficar direto em Program.cs.",
         "class Programa\n{\n    static async Task Main(string[] args)\n    {\n        await Task.Delay(10);\n"
         "        Console.WriteLine($\"Argumentos: {args.Length}\");\n    }\n}", ""),
        ("console", (r"\bConsole\.(?:WriteLine|Write|ReadLine)\b",), "Console e interpolação",
         "Console.WriteLine escreve com quebra de linha; $\"Olá, {nome}\" interpola valores; {preco:C} e {media:F2} "
         "formatam. Console.ReadLine devolve string? — pode ser null quando a entrada termina.",
         "Console.Write(\"Nome: \");\nstring? nome = Console.ReadLine();\nConsole.WriteLine($\"Olá, {nome ?? \"visitante\"}!\");",
         "Converter a entrada com int.Parse sem tratar formato inválido; prefira int.TryParse."),
        ("colecoes", (r"\bnew\s+(?:List|Dictionary|HashSet|Queue|Stack)<", r"\b(?:List|Dictionary|HashSet)<[^>]+>\s+\w+"),
         "List, Dictionary e HashSet",
         "List<T> cresce com Add; Dictionary<K,V> mapeia chaves: TryGetValue consulta sem exceção quando a chave falta, "
         "enquanto dic[chave] lança KeyNotFoundException. HashSet<T> guarda itens únicos. var deduz o tipo, que continua "
         "estático.",
         "var catalogo = new Dictionary<int, string> { [1] = \"Caderno\" };\n"
         "Console.WriteLine(catalogo.TryGetValue(2, out var nome) ? nome : \"ausente\");",
         "Ler dic[chave] sem saber se a chave existe."),
        ("linq", (r"\.(?:Where|Select|SelectMany|OrderBy|OrderByDescending|GroupBy|Any|All|First|FirstOrDefault|Sum|Count|"
                  r"ToList|ToArray|ToDictionary)\s*\(",), "LINQ · consultas em coleções",
         "Where filtra, Select transforma, OrderBy ordena, GroupBy agrupa e Sum/Count agregam. n => n % 2 == 0 é uma "
         "expressão lambda. A consulta só é executada ao percorrer o resultado ou chamar ToList/ToArray (execução adiada).",
         "var valores = new List<int> { 1, 2, 3, 4 };\nvar paresDobrados = valores.Where(n => n % 2 == 0).Select(n => n * 2).ToList();\n"
         "Console.WriteLine(string.Join(\", \", paresDobrados));  // 4, 8",
         "Percorrer a mesma consulta adiada várias vezes, refazendo o trabalho; materialize com ToList."),
        ("async", (r"\basync\b", r"\bawait\b", r"\bTask(?:<[^>]+>)?\b"), "async, await e Task",
         "Um método async devolve Task (ou Task<T>) e pode usar await para esperar outra tarefa sem bloquear a thread. "
         "Exceções da tarefa aparecem no await, onde try/catch as trata. Evite .Result e .Wait(), que bloqueiam.",
         "static async Task<int> DobroAsync(int n)\n{\n    await Task.Delay(100);\n    return n * 2;\n}\n\n"
         "Console.WriteLine(await DobroAsync(10));",
         "async void fora de eventos: exceções não podem ser aguardadas nem tratadas."),
        ("excecoes", (r"^\s*(?:try|finally)\b", r"\bcatch\s*\(", r"\bthrow\s+new\b"), "Exceções em C#",
         "try executa; catch (TipoDeExcecao e) trata o erro esperado; finally sempre roda (ou use using para liberar "
         "recursos). Capture o tipo mais específico e não esconda exceções sem registrar.",
         "try\n{\n    var numero = int.Parse(\"abc\");\n}\ncatch (FormatException e)\n{\n    Console.WriteLine($\"Entrada inválida: {e.Message}\");\n}",
         "catch (Exception) vazio, que esconde falhas reais."),
        ("expressao", (r"\)\s*=>",), "Membros com =>",
         "static int Dobro(int x) => x * 2; define um método de uma única expressão. O mesmo vale para propriedades "
         "(public string Nome => $\"{Primeiro} {Ultimo}\";).",
         "static int Dobro(int x) => x * 2;\nstatic bool EhPar(int x) => x % 2 == 0;\nConsole.WriteLine(Dobro(10));", ""),
        ("tipos", (r"\b(?:class|record|struct|interface|enum)\s+\w+", r"\{\s*get;"), "Classes, records e propriedades",
         "Propriedades { get; set; } expõem dados com controle; init permite atribuir só na criação. record cria tipos de "
         "dados com igualdade por valor e cópia com with. struct é tipo de valor (copiado na atribuição).",
         "public record Produto(string Nome, decimal Preco);\n\nvar caderno = new Produto(\"Caderno\", 12.5m);\n"
         "var promocao = caderno with { Preco = 10m };\nConsole.WriteLine(promocao);",
         "Campos públicos mutáveis em vez de propriedades."),
        ("nulos", (r"\?\?", r"\?\.", r"\b\w+\?\s+\w+\s*[=;)]"), "Tipos anuláveis, ?. e ??",
         "string? indica que o valor pode ser null; o compilador avisa usos inseguros. ?. acessa só quando não é null; "
         "?? fornece um padrão; ??= atribui se ainda for null.",
         "string? apelido = null;\nint tamanho = apelido?.Length ?? 0;\napelido ??= \"sem apelido\";", ""),
    ],
    "java": [
        ("import", (r"^\s*import\s+[\w.*]+\s*;",), "import · pacotes",
         "import java.util.List; permite usar List sem o nome completo; java.util.* importa as classes do pacote, mas não "
         "os subpacotes. java.lang (String, Math, System) já vem importado. Bibliotecas externas vêm do Maven ou Gradle.",
         "import java.util.ArrayList;\nimport java.util.List;\n\nList<String> nomes = new ArrayList<>();",
         "Importar classes de mesmo nome de pacotes diferentes (java.util.List e java.awt.List)."),
        ("main", (r"public\s+static\s+void\s+main\s*\(",), "main · ponto de entrada",
         "A JVM começa por public static void main(String[] args) da classe indicada; args traz os argumentos da linha de "
         "comando. Desde o Java 11, java Programa.java compila e executa um arquivo único.",
         "public class Programa {\n    public static void main(String[] args) {\n"
         "        System.out.println(\"Argumentos: \" + args.length);\n    }\n}", ""),
        ("println", (r"\bSystem\.(?:out|err)\.(?:println|printf|print)\b",), "System.out.println e printf",
         "println escreve e quebra a linha; printf formata (%d inteiro, %.2f decimal com 2 casas, %s texto, %n quebra). "
         "System.err é a saída de erros.",
         "String nome = \"Ana\";\ndouble media = 7.456;\nSystem.out.printf(\"%s: %.2f%n\", nome, media);", ""),
        ("colecoes", (r"\b(?:List|ArrayList|Map|HashMap|Set|HashSet|Deque|ArrayDeque)<",), "Coleções: List, Map e Set",
         "Declare pela interface (List<String> nomes) e crie pela implementação (new ArrayList<>()). List.of cria uma "
         "lista imutável: add lança UnsupportedOperationException — copie para um ArrayList para alterar. Coleções usam "
         "classes (Integer), não tipos primitivos (int).",
         "List<String> nomes = new ArrayList<>(List.of(\"Ana\", \"Beatriz\"));\nnomes.add(\"Caio\");\n"
         "Map<String, Integer> idades = new HashMap<>();\nidades.put(\"Ana\", 20);\nSystem.out.println(idades.getOrDefault(\"Bia\", 0));",
         "Alterar uma lista criada com List.of."),
        ("excecoes", (r"^\s*try\s*\(", r"\bthrow\s+new\b", r"\bthrows\b", r"\bcatch\s*\("), "Exceções e try-with-resources",
         "try (recurso) fecha o recurso automaticamente, mesmo com erro. throw new IllegalArgumentException(...) sinaliza "
         "um problema; exceções verificadas (IOException) precisam ser tratadas com catch ou declaradas com throws.",
         "try (BufferedReader leitor = new BufferedReader(new FileReader(\"dados.txt\"))) {\n"
         "    System.out.println(leitor.readLine());\n} catch (IOException e) {\n    System.err.println(\"Falha: \" + e.getMessage());\n}",
         "catch vazio, que esconde o erro."),
        ("classes", (r"\b(?:class|record|interface|enum)\s+\w+", r"^\s*private\s+[\w<>\[\]]+\s+\w+"),
         "Classes, encapsulamento e records",
         "Campos private só são acessados pelos métodos da classe, que validam as mudanças de estado. record cria uma "
         "classe de dados imutável com construtor, getters, equals e toString.",
         "public record Livro(String titulo, int ano) {}\n\nclass Emprestimo {\n    private boolean ativo;\n"
         "    void iniciar() {\n        if (ativo) throw new IllegalStateException(\"já emprestado\");\n        ativo = true;\n    }\n}", ""),
        ("metodos", (r"^\s*(?:public\s+|private\s+|protected\s+)?static\s+[\w<>\[\]]+\s+\w+\s*\((?!String\[\])",), "Métodos static",
         "Um método static pertence à classe, não a um objeto: é chamado como Classe.metodo(). Declara o tipo de retorno "
         "(void quando não devolve nada) e o tipo de cada parâmetro.",
         "static int dobro(int x) {\n    return x * 2;\n}\n\npublic static void main(String[] args) {\n"
         "    System.out.println(dobro(10));\n}", ""),
        ("streams", (r"\.stream\(\)", r"\.(?:filter|map|collect|toList|reduce|sorted)\s*\("), "Streams",
         "stream() processa uma coleção em etapas: filter seleciona, map transforma, collect ou toList (Java 16+) junta o "
         "resultado. Nada é executado até a operação final.",
         "List<Integer> numeros = List.of(1, 2, 3, 4);\nList<Integer> paresDobrados = numeros.stream()\n"
         "        .filter(n -> n % 2 == 0)\n        .map(n -> n * 2)\n        .toList();", ""),
    ],
    "kotlin": [
        ("main", (r"\bfun\s+main\s*\(",), "fun main · ponto de entrada",
         "O programa começa em fun main(). Para receber argumentos da linha de comando, use fun main(args: Array<String>).",
         "fun main(args: Array<String>) {\n    println(\"Argumentos: ${args.size}\")\n}", ""),
        ("val_var", (r"^\s*(?:val|var)\s+\w+",), "val e var",
         "val não pode ser reatribuído; var pode. O tipo é deduzido (val idade = 20) ou declarado (val idade: Int = 20). "
         "Prefira val: o código fica mais previsível.",
         "val nome = \"Ana\"\nvar pontos = 0\npontos += 10\nprintln(\"$nome tem $pontos pontos\")",
         "Usar var por hábito e deixar o valor mudar onde não deveria."),
        ("nulos", (r"\w\?\s*[=),]", r"\?\.", r"\?:", r"!!"), "Null safety: ?, ?. e ?:",
         "String? aceita null; String não. ?. chama só se o valor não for null; ?: (Elvis) dá um padrão; !! força o "
         "acesso e lança NullPointerException se for null.",
         "val nome: String? = null\nval tamanho = nome?.length ?: 0\nprintln(tamanho)",
         "Usar !! para silenciar o compilador."),
        ("colecoes", (r"\b(?:listOf|mutableListOf|mapOf|mutableMapOf|setOf)\s*\(", r"\.(?:map|filter|mapNotNull|forEach|any|none|all|first|sumOf|count)\s*\{"),
         "Coleções e lambdas (it)",
         "listOf cria uma lista somente leitura; mutableListOf permite alterar. map e filter devolvem novas listas. Numa "
         "lambda de um parâmetro, it é esse parâmetro; mapNotNull descarta os null.",
         "val entradas = listOf(\"1\", \"x\", \"3\")\nval numeros = entradas.mapNotNull { it.toIntOrNull() }\nprintln(numeros.sum())  // 4",
         "Tentar add em listOf: a lista não é mutável."),
        ("when", (r"\bwhen\s*[({]",), "when · escolha por casos",
         "when compara um valor com vários casos, aceita faixas (in 1..5) e testa tipos (is). Como expressão, precisa cobrir "
         "todos os casos — com else ou com uma sealed class.",
         "fun classificar(nota: Int) = when (nota) {\n    in 9..10 -> \"ótimo\"\n    in 6..8 -> \"bom\"\n    else -> \"revisar\"\n}", ""),
        ("classes", (r"\b(?:sealed|data|enum|abstract|open)\s+class\b", r"^\s*class\s+\w+"), "data class e sealed class",
         "data class gera equals, hashCode, toString e copy a partir do construtor. sealed class limita as subclasses ao "
         "mesmo pacote, e o when sabe quando todos os casos foram tratados.",
         "sealed class Resultado {\n    data class Ok(val valor: Int) : Resultado()\n    data class Erro(val motivo: String) : Resultado()\n}\n\n"
         "fun resumo(r: Resultado) = when (r) {\n    is Resultado.Ok -> \"valor ${r.valor}\"\n    is Resultado.Erro -> \"erro: ${r.motivo}\"\n}", ""),
        ("pre_condicoes", (r"\b(?:require|check|requireNotNull|error)\s*\(",), "require, check e error",
         "require(condição) valida argumentos e lança IllegalArgumentException; check valida o estado e lança "
         "IllegalStateException; error(mensagem) lança uma exceção imediatamente.",
         "fun sacar(saldo: Int, valor: Int): Int {\n    require(valor > 0) { \"valor deve ser positivo\" }\n"
         "    check(saldo >= valor) { \"saldo insuficiente\" }\n    return saldo - valor\n}", ""),
        ("funcao", (r"\bfun\s+\w+\s*\(",), "fun · funções",
         "fun nome(param: Tipo): Retorno { ... }. Funções de uma expressão usam =: fun dobro(x: Int) = x * 2. Parâmetros "
         "podem ter valor padrão e ser passados pelo nome na chamada.",
         "fun saudacao(nome: String, formal: Boolean = false) = if (formal) \"Prezado $nome\" else \"Oi, $nome\"\n\n"
         "println(saudacao(\"Ana\", formal = true))", ""),
        ("templates", (r"\"[^\"]*\$\{?\w",), "Templates de string",
         "\"Olá, $nome\" insere o valor de uma variável; \"${a + b}\" insere o resultado de uma expressão.",
         "val itens = 3\nval preco = 2.5\nprintln(\"Total de $itens itens: ${itens * preco}\")", ""),
    ],
    "swift": [
        ("let_var", (r"^\s*(?:let|var)\s+\w+",), "let e var",
         "let cria uma constante; var, uma variável. O tipo é deduzido ou declarado (let idade: Int = 20). Prefira let.",
         "let nome = \"Ana\"\nvar pontos = 0\npontos += 10\nprint(\"\\(nome): \\(pontos)\")", ""),
        ("opcionais", (r"\b(?:guard|if)\s+let\b", r"\?\?", r"\w\?\."), "Opcionais: if let, guard let e ??",
         "Int(texto) devolve Int? — pode ser nil. if let usa o valor quando ele existe; guard let sai cedo (return ou "
         "throw) quando não existe e deixa o valor disponível no resto da função; ?? fornece um padrão.",
         "func dobro(_ texto: String) -> Int? {\n    guard let numero = Int(texto) else { return nil }\n    return numero * 2\n}\n\n"
         "print(dobro(\"3\") ?? 0)",
         "Forçar com ! e derrubar o programa quando o valor é nil."),
        ("func", (r"\bfunc\s+\w+",), "func · funções e rótulos de argumento",
         "func dobro(_ x: Int) -> Int: _ dispensa o rótulo na chamada (dobro(10)); sem _, a chamada usa o nome do "
         "parâmetro (dobro(x: 10)). -> indica o tipo de retorno.",
         "func saudar(_ nome: String, com saudacao: String = \"Olá\") -> String {\n    \"\\(saudacao), \\(nome)!\"\n}\n\n"
         "print(saudar(\"Ana\", com: \"Bom dia\"))", ""),
        ("tipos", (r"\b(?:struct|class|protocol|enum|extension)\s+\w+",), "struct, class e protocol",
         "struct é tipo de valor: a atribuição copia. class é tipo de referência: duas variáveis podem apontar para o mesmo "
         "objeto. protocol define requisitos que structs e classes adotam.",
         "protocol Descritivel {\n    func descrever() -> String\n}\n\nstruct Produto: Descritivel {\n    let nome: String\n"
         "    func descrever() -> String { \"Produto: \\(nome)\" }\n}\n\nprint(Produto(nome: \"Caderno\").descrever())", ""),
        ("erros", (r"\bdo\s*\{", r"\btry[?!]?\s", r"\bcatch\b", r"\bthrows\b"), "Erros: throws, try e do/catch",
         "Funções que podem falhar são marcadas com throws e chamadas com try dentro de do { } catch { }. try? transforma "
         "o erro em nil; try! derruba o programa se houver erro.",
         "enum ErroDeEntrada: Error { case vazia }\n\nfunc validar(_ texto: String) throws -> String {\n"
         "    if texto.isEmpty { throw ErroDeEntrada.vazia }\n    return texto\n}\n\n"
         "do {\n    print(try validar(\"\"))\n} catch {\n    print(\"Erro: \\(error)\")\n}", ""),
        ("codable", (r"\b(?:Codable|Decodable|Encodable|JSONDecoder|JSONEncoder)\b",), "Codable e JSON",
         "Um tipo que adota Codable pode ser convertido de e para JSON. JSONDecoder().decode(Tipo.self, from: dados) lança "
         "erro se o JSON não corresponder ao tipo.",
         "import Foundation\n\nstruct Produto: Codable { let id: Int; let nome: String }\n"
         "let dados = Data(\"{\\\"id\\\": 1, \\\"nome\\\": \\\"Caderno\\\"}\".utf8)\n"
         "do {\n    let produto = try JSONDecoder().decode(Produto.self, from: dados)\n    print(produto.nome)\n} catch {\n"
         "    print(\"JSON inválido: \\(error)\")\n}", ""),
        ("import", (r"^\s*import\s+\w+",), "import · módulos",
         "import Foundation traz datas, JSON, arquivos e textos avançados; SwiftUI e UIKit são para interfaces. Pacotes "
         "externos entram pelo Swift Package Manager.",
         "import Foundation\n\nlet agora = Date()\nprint(agora.timeIntervalSince1970 > 0)", ""),
        ("print", (r"\bprint\s*\(", r"\\\("), "print e interpolação",
         "print escreve uma linha; \\(expressão) insere valores dentro da string.",
         "let itens = 3\nprint(\"Você tem \\(itens) itens; o dobro é \\(itens * 2).\")", ""),
    ],
    "dart": [
        ("main", (r"\bvoid\s+main\s*\(", r"\bFuture<void>\s+main\s*\("), "main · ponto de entrada",
         "Programas Dart e aplicativos Flutter começam em main. Com operações assíncronas, use Future<void> main() async "
         "para poder usar await.",
         "Future<void> main() async {\n  await Future.delayed(const Duration(milliseconds: 10));\n  print('pronto');\n}", ""),
        ("final_const", (r"^\s*(?:final|const|var|late)\s+",), "final, const, var e late",
         "final não pode ser reatribuído (o valor é definido ao executar); const é constante de compilação; var deduz o "
         "tipo e permite reatribuir; late adia a inicialização e falha se o valor for lido antes.",
         "const taxa = 0.1;\nfinal agora = DateTime.now();\nvar total = 100.0;\ntotal += total * taxa;\nprint(total);",
         "Usar late para evitar inicialização e ganhar um erro em tempo de execução."),
        ("colecoes", (r"\.(?:where|map|toList|fold|reduce|any|every|forEach|firstWhere)\s*\(",), "Listas, where e map",
         "where filtra e map transforma; ambos devolvem um Iterable preguiçoso — chame toList() para materializar. fold "
         "acumula um resultado começando de um valor inicial.",
         "final valores = [1, 2, 3, 4];\nfinal pares = valores.where((n) => n.isEven).map((n) => n * 2).toList();\n"
         "final soma = valores.fold(0, (total, n) => total + n);\nprint('$pares $soma');", ""),
        ("arrow", (r"\)\s*=>",), "Funções de uma expressão (=>)",
         "int dobro(int x) => x * 2; é uma função cujo corpo é uma única expressão. O mesmo => aparece em funções anônimas: "
         "(n) => n * 2.",
         "int dobro(int x) => x * 2;\nbool ehPar(int x) => x.isEven;\nvoid main() => print(dobro(10));", ""),
        ("print", (r"\bprint\s*\(",), "print e interpolação",
         "print escreve uma linha. Dentro de strings, $nome insere uma variável e ${expressão} insere o resultado de uma "
         "expressão.",
         "final itens = 3;\nprint('Você tem $itens itens; o dobro é ${itens * 2}.');", ""),
        ("classes", (r"^\s*(?:abstract\s+|final\s+|sealed\s+)?class\s+\w+", r"\bthis\.\w+", r"^\s*const\s+\w+\s*\("),
         "Classes e construtores",
         "Tarefa(this.id, this.titulo) atribui os parâmetros direto aos campos; {this.feita = false} são parâmetros "
         "nomeados com valor padrão. Campos final com construtor const permitem instâncias imutáveis.",
         "class Tarefa {\n  final int id;\n  final String titulo;\n  final bool feita;\n  const Tarefa(this.id, this.titulo, {this.feita = false});\n"
         "  Tarefa concluir() => Tarefa(id, titulo, feita: true);\n}", ""),
        ("conversao", (r"\b(?:int|double|num)\.(?:parse|tryParse)\s*\(", r"\bthrow\b", r"\bon\s+\w+(?:Exception|Error)"),
         "Conversão e exceções",
         "int.parse lança FormatException com texto inválido; int.tryParse devolve null. try/on TipoDeErro/catch trata "
         "exceções específicas.",
         "final idade = int.tryParse('vinte') ?? 0;\ntry {\n  int.parse('abc');\n} on FormatException catch (e) {\n"
         "  print('Entrada inválida: ${e.message}');\n}", ""),
    ],
    "lua": [
        ("local", (r"^\s*local\s+(?!function)\w",), "local · variáveis locais",
         "Sem local, a variável é global e fica visível no programa inteiro. Use local sempre. nil representa ausência "
         "de valor.",
         "local nome = \"Ana\"\nlocal pontos = 10\nprint(nome, pontos)", "Esquecer local e sobrescrever uma variável global por acidente."),
        ("tabelas", (r"=\s*\{", r"\w\[[^\]]+\]\s*=", r"\w\.\w+\s*="), "Tabelas · listas e dicionários",
         "Uma tabela {} serve de lista (índices a partir de 1) e de dicionário (t[\"chave\"] ou t.chave). Uma chave ausente "
         "devolve nil; # dá o tamanho da parte de lista.",
         "local frutas = {\"maçã\", \"uva\"}\nlocal idades = {ana = 20, bia = 16}\nidades.caio = 18\nprint(frutas[1], #frutas, idades.ana)",
         "Começar a lista pelo índice 0 e depois estranhar o resultado de #."),
        ("funcao", (r"^\s*(?:local\s+)?function\b",), "function · funções",
         "local function nome(param) ... end define uma função. Funções são valores: podem ser guardadas em variáveis e "
         "tabelas. Podem devolver vários valores (return a, b).",
         "local function dividir(a, b)\n  if b == 0 then\n    return nil, \"divisão por zero\"\n  end\n  return a / b\nend\n\n"
         "local resultado, erro = dividir(10, 0)\nprint(resultado, erro)", ""),
        ("retorno", (r"^\s*return\b",), "return · devolver valores",
         "return encerra a função e devolve um ou mais valores. Sem return, a função devolve nil.",
         "local function minmax(a, b)\n  if a < b then return a, b end\n  return b, a\nend\nprint(minmax(5, 2))", ""),
        ("padrao", (r"\bor\s+(?:\d|\"|'|\{)",), "or como valor padrão",
         "(x or 0) usa 0 quando x é nil ou false. Só nil e false são falsos em Lua: 0 e \"\" são verdadeiros.",
         "local contagem = {}\nfor _, palavra in ipairs({\"ana\", \"bia\", \"ana\"}) do\n"
         "  contagem[palavra] = (contagem[palavra] or 0) + 1\nend\nprint(contagem.ana)  -- 2",
         "Usar or para padrão quando false é um valor válido."),
        ("erros", (r"\b(?:pcall|xpcall|error|assert)\s*\(",), "error, assert e pcall",
         "error(mensagem) interrompe a execução; assert(condição, mensagem) lança o erro quando a condição é falsa ou nil; "
         "pcall(f, ...) chama f de forma protegida e devolve ok seguido do resultado ou da mensagem de erro.",
         "local function dobro(n)\n  assert(type(n) == \"number\", \"número esperado\")\n  return n * 2\nend\n\n"
         "local ok, resposta = pcall(dobro, \"x\")\nprint(ok, resposta)", ""),
        ("pairs", (r"\bi?pairs\s*\(",), "for com pairs e ipairs",
         "ipairs percorre a parte de lista na ordem 1, 2, 3… e para no primeiro nil; pairs percorre todas as chaves, em "
         "ordem não definida.",
         "local notas = {ana = 9, bia = 7}\nfor nome, nota in pairs(notas) do\n  print(nome, nota)\nend\n"
         "for i, fruta in ipairs({\"maçã\", \"uva\"}) do\n  print(i, fruta)\nend", "Esperar ordem fixa de pairs."),
        ("concatenar", (r"\.\.",), "Concatenação com ..",
         "\"Olá, \" .. nome junta textos; números são convertidos automaticamente, mas nil causa erro. tostring(x) "
         "converte explicitamente.",
         "local nome = \"Ana\"\nlocal idade = 20\nprint(\"Olá, \" .. nome .. \"! Idade: \" .. tostring(idade))",
         "Usar + para juntar textos: Lua tenta somar números."),
        ("comparacao", (r"~=", r"\bthen\b"), "Condições e ~=",
         "if condição then ... elseif ... else ... end. == compara igualdade e ~= diferença. and e or devolvem um dos "
         "operandos, não necessariamente true/false.",
         "local idade = 17\nif idade >= 18 then\n  print(\"adulto\")\nelseif idade ~= 0 then\n  print(\"menor\")\nend", ""),
        ("print", (r"^\s*print\s*\(",), "print · saída",
         "print separa os argumentos com tabulação e quebra a linha no fim. string.format formata com %d, %s e %.2f.",
         "print(\"total\", 10)\nprint(string.format(\"%s: %.2f\", \"média\", 7.456))", ""),
    ],
    "php": [
        ("abertura", (r"^\s*<\?php", r"declare\s*\(\s*strict_types"), "<?php e strict_types",
         "<?php abre o código PHP; num arquivo só de PHP, omita ?> no fim para não enviar espaços por engano. "
         "declare(strict_types=1) faz chamadas com tipos errados lançarem TypeError em vez de converter em silêncio.",
         "<?php\ndeclare(strict_types=1);\n\nfunction dobro(int $x): int\n{\n    return $x * 2;\n}\n\necho dobro(10), PHP_EOL;", ""),
        ("variaveis", (r"^\s*\$\w+\s*=", r"\$\w+\["), "$variáveis e arrays",
         "Variáveis começam com $. [] cria um array, que funciona como lista e como mapa (chave => valor). Ler uma chave "
         "ausente gera aviso — use ?? para um valor padrão.",
         "<?php\n$frutas = ['maçã', 'uva'];\n$idades = ['ana' => 20, 'bia' => 16];\n$idades['caio'] = 18;\n"
         "echo count($frutas), ' ', $idades['ana'], PHP_EOL;", ""),
        ("foreach", (r"\bforeach\s*\(",), "foreach",
         "foreach ($itens as $item) percorre os valores; foreach ($mapa as $chave => $valor) percorre os pares.",
         "<?php\n$contagem = [];\nforeach (['ana', 'bia', 'ana'] as $palavra) {\n"
         "    $contagem[$palavra] = ($contagem[$palavra] ?? 0) + 1;\n}\nprint_r($contagem);",
         "Alterar $item esperando mudar o array: use a chave ou &$item."),
        ("padrao", (r"\?\?",), "?? · valor padrão",
         "$x ?? 'padrão' usa o padrão quando $x não existe ou é null, sem aviso. ??= atribui só se ainda não houver valor.",
         "<?php\n$nome = $_GET['nome'] ?? 'visitante';\n$config['tema'] ??= 'claro';", ""),
        ("seguranca", (r"\bhtmlspecialchars\s*\(", r"\$_(?:GET|POST|REQUEST|COOKIE)\b", r"<script"), "Entrada do usuário e XSS",
         "Dados de $_GET, $_POST e cookies não são confiáveis. Ao escrever em HTML, use htmlspecialchars($texto, "
         "ENT_QUOTES, 'UTF-8'); em SQL, consultas preparadas (PDO). Um texto com <script> só é perigoso se for impresso "
         "sem escape.",
         "<?php\n$nome = $_GET['nome'] ?? '';\necho '<p>', htmlspecialchars($nome, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8'), '</p>';",
         "Imprimir entrada do usuário direto no HTML (XSS)."),
        ("validacao", (r"\bfilter_var\s*\(",), "filter_var · validação",
         "filter_var valida e normaliza valores: FILTER_VALIDATE_EMAIL, FILTER_VALIDATE_INT, FILTER_VALIDATE_URL. Devolve "
         "false quando o valor é inválido — compare com !== false.",
         "<?php\nfunction emailValido(string $email): bool\n{\n    return filter_var($email, FILTER_VALIDATE_EMAIL) !== false;\n}", ""),
        ("funcao", (r"\bfunction\s+\w+\s*\(",), "Funções com tipos",
         "function dobro(int $x): int declara os tipos dos parâmetros e do retorno; ?string aceita null; com "
         "strict_types, tipos errados geram TypeError.",
         "<?php\nfunction saudacao(string $nome, bool $formal = false): string\n{\n"
         "    return $formal ? \"Prezado {$nome}\" : \"Oi, {$nome}\";\n}", ""),
    ],
    "sql": [
        ("select", (r"^\s*SELECT\b", r"^\s*FROM\b"), "SELECT … FROM · consultar",
         "SELECT escolhe as colunas e FROM, a tabela. A ordem lógica de execução é FROM → WHERE → GROUP BY → HAVING → "
         "SELECT → ORDER BY; por isso um apelido criado no SELECT não pode ser usado no WHERE. Em aplicações, liste as "
         "colunas em vez de usar *.",
         "SELECT nome, idade\nFROM pessoas\nWHERE idade >= 18\nORDER BY nome;", ""),
        ("where", (r"\bWHERE\b",), "WHERE · filtrar linhas",
         "WHERE mantém só as linhas em que a condição é verdadeira. NULL não é igual a nada, nem a NULL: use IS NULL ou "
         "IS NOT NULL. Combine AND e OR com parênteses para deixar a precedência clara.",
         "SELECT nome\nFROM clientes\nWHERE (cidade = 'Recife' OR cidade = 'Natal')\n  AND email IS NOT NULL;",
         "Escrever coluna = NULL, que nunca é verdadeiro."),
        ("join", (r"\bJOIN\b",), "JOIN · combinar tabelas",
         "INNER JOIN mantém só as linhas com par nas duas tabelas; LEFT JOIN mantém todas as da esquerda e preenche com "
         "NULL quando não há par. ON define a ligação, normalmente chave estrangeira = chave primária.",
         "SELECT p.nome, c.valor\nFROM pessoas p\nLEFT JOIN compras c ON c.pessoa_id = p.id\nORDER BY p.nome;",
         "Filtrar a tabela da direita no WHERE depois de um LEFT JOIN, o que o transforma em INNER JOIN."),
        ("ordenar", (r"\bORDER\s+BY\b", r"\bLIMIT\b"), "ORDER BY e LIMIT",
         "Sem ORDER BY, a ordem do resultado não é garantida. DESC inverte a ordem; LIMIT n restringe a quantidade de "
         "linhas (use junto de ORDER BY para resultados estáveis).",
         "SELECT produto, total\nFROM vendas\nORDER BY total DESC\nLIMIT 3;", ""),
        ("cte", (r"^\s*WITH\b", r"\bAS\s*\(\s*(?:VALUES|SELECT)\b"), "WITH · consultas nomeadas (CTE)",
         "WITH nome AS (consulta) cria um resultado temporário com nome, usado na consulta seguinte. Ajuda a dividir uma "
         "consulta grande em etapas legíveis.",
         "WITH vendas(categoria, valor) AS (\n  VALUES ('A', 10), ('A', 20), ('B', 5)\n)\n"
         "SELECT categoria, SUM(valor) AS total\nFROM vendas\nGROUP BY categoria;", ""),
        ("tabela", (r"\bCREATE\s+TABLE\b", r"\bPRIMARY\s+KEY\b", r"\bNOT\s+NULL\b", r"\bCHECK\s*\(", r"\bREFERENCES\b"),
         "CREATE TABLE e restrições",
         "CREATE TABLE define colunas e tipos. PRIMARY KEY identifica cada linha; NOT NULL proíbe ausência; CHECK valida "
         "valores; REFERENCES cria uma chave estrangeira. As restrições protegem os dados mesmo contra erros da aplicação.",
         "CREATE TABLE estoque (\n  id INTEGER PRIMARY KEY,\n  produto TEXT NOT NULL,\n  quantidade INTEGER NOT NULL CHECK (quantidade >= 0)\n);", ""),
        ("alterar", (r"^\s*(?:INSERT|UPDATE|DELETE)\b",), "INSERT, UPDATE e DELETE",
         "INSERT adiciona linhas; UPDATE altera; DELETE remove. Confira o WHERE de UPDATE e DELETE: sem ele, todas as "
         "linhas mudam. Teste antes com um SELECT usando o mesmo WHERE. Na aplicação, passe valores por parâmetros, "
         "nunca concatenando texto (injeção de SQL).",
         "INSERT INTO estoque (id, produto, quantidade) VALUES (1, 'caderno', 5);\n"
         "UPDATE estoque SET quantidade = quantidade - 2 WHERE id = 1;",
         "Rodar UPDATE ou DELETE sem WHERE."),
        ("transacao", (r"^\s*(?:BEGIN|COMMIT|ROLLBACK|START\s+TRANSACTION|SAVEPOINT)\b",), "Transações",
         "BEGIN inicia uma transação; COMMIT confirma todas as alterações; ROLLBACK desfaz. Agrupe operações que precisam "
         "acontecer juntas, como debitar uma conta e creditar outra.",
         "BEGIN;\nUPDATE contas SET saldo = saldo - 100 WHERE id = 1;\nUPDATE contas SET saldo = saldo + 100 WHERE id = 2;\nCOMMIT;", ""),
    ],
    "powershell": [
        ("param", (r"^\s*param\s*\(",), "param · parâmetros do script",
         "param(...) declara os parâmetros do script ou da função. [Parameter(Mandatory)] torna obrigatório; "
         "[ValidateRange(0,1000)] e [ValidateSet('a','b')] validam antes do código rodar; o tipo [int] converte o argumento.",
         "param(\n    [Parameter(Mandatory)]\n    [ValidateRange(0, 1000)]\n    [int]$Quantidade\n)\n\n"
         "\"Dobro: $($Quantidade * 2)\"", ""),
        ("cmdletbinding", (r"\[CmdletBinding\b", r"\bShouldProcess\b", r"-WhatIf\b", r"-Confirm\b"), "CmdletBinding, -WhatIf e -Confirm",
         "[CmdletBinding(SupportsShouldProcess)] dá ao script os parâmetros comuns (-Verbose, -WhatIf, -Confirm). Antes de "
         "alterar algo, chame $PSCmdlet.ShouldProcess(alvo): com -WhatIf, a ação é apenas descrita.",
         "[CmdletBinding(SupportsShouldProcess)]\nparam([Parameter(Mandatory)][string]$LiteralPath)\n\n"
         "if ($PSCmdlet.ShouldProcess($LiteralPath, 'Remover')) {\n    Remove-Item -LiteralPath $LiteralPath\n}", ""),
        ("objetos", (r"\[pscustomobject\]", r"@\{"), "Objetos e hashtables",
         "@{ Chave = valor } cria uma hashtable; [pscustomobject]@{ ... } cria um objeto com propriedades, que o pipeline, "
         "Select-Object, Format-Table e Export-Csv entendem.",
         "$pessoa = [pscustomobject]@{ Nome = 'Ana'; Idade = 20 }\n$pessoa | Format-Table\n$pessoa.Nome", ""),
        ("comparacao", (r"\s-(?:eq|ne|gt|ge|lt|le|like|notlike|match|notmatch|contains|in|notin)\b",), "Operadores de comparação",
         "PowerShell usa -eq, -ne, -gt, -lt, -ge e -le em vez de ==, >. Comparações de texto ignoram maiúsculas por "
         "padrão (-ceq diferencia). -like usa curingas (*); -match, expressões regulares.",
         "$idade = 20\nif ($idade -ge 18 -and 'Ana' -like 'A*') {\n    'maior de idade'\n}",
         "Escrever > para comparar: em PowerShell, > redireciona a saída para um arquivo."),
        ("variaveis", (r"^\s*\$\w+\s*=",), "Variáveis $",
         "$nome = valor cria a variável. Tipos são dinâmicos, mas podem ser fixados: [int]$n = 5. Variáveis de ambiente "
         "ficam em $env:NOME. Em aspas duplas, \"$nome\" e \"$($a + $b)\" são interpolados.",
         "$nome = 'Ana'\n[int]$pontos = '10'\n\"$nome tem $($pontos * 2) pontos\"", ""),
        ("caminhos", (r"-LiteralPath\b", r"-Path\b"), "-Path e -LiteralPath",
         "-Path interpreta curingas ([ ], *, ?); -LiteralPath usa o nome exatamente como foi escrito — mais seguro para "
         "nomes vindos de fora, que podem conter colchetes.",
         "Get-Item -LiteralPath 'relatorio[2026].txt'\nGet-ChildItem -Path '*.txt'", ""),
        ("propriedades", (r"\$\w+\.\w+",), "Propriedades de objetos",
         "$objeto.Propriedade lê uma propriedade; propriedades podem conter outros objetos ($a.B.C). Get-Member lista o "
         "que um objeto oferece.",
         "$arquivo = Get-Item -LiteralPath $PSCommandPath\n$arquivo.Name\n$arquivo.Directory.FullName\n$arquivo | Get-Member", ""),
    ],
    "go": [
        ("package", (r"^\s*package\s+\w+", r"^\s*import\b"), "package e import",
         "Todo arquivo começa com package; programas executáveis usam package main com func main(). import traz pacotes "
         "da biblioteca padrão (\"fmt\", \"strings\") ou de módulos do go.mod. Um import não usado é erro de compilação.",
         "package main\n\nimport (\n\t\"fmt\"\n\t\"strings\"\n)\n\nfunc main() {\n\tfmt.Println(strings.ToUpper(\"olá\"))\n}", ""),
        ("declarar", (r"^\s*(?!(?:for|if|switch|select)\b)[\w, ]+:=",), ":= · declarar e atribuir",
         "x := 10 declara e deduz o tipo (só dentro de funções); var x int declara com o valor zero do tipo. Com mapas, "
         "valor, existe := m[chave] informa se a chave está presente.",
         "idades := map[string]int{\"Ana\": 20}\nidade, existe := idades[\"Bia\"]\nfmt.Println(idade, existe)  // 0 false", ""),
        ("slices", (r"\bmap\[", r"\[\]\w+\{", r"\bappend\s*\(", r"\bmake\s*\("), "Slices e maps",
         "Um slice []int é uma janela sobre um array: append pode realocar, então guarde o retorno (s = append(s, x)). "
         "Cópias de slice compartilham os dados — use copy para duplicar. Um map consultado com chave ausente devolve o "
         "valor zero.",
         "original := []int{1, 2, 3}\ncopia := make([]int, len(original))\ncopy(copia, original)\ncopia[0] = 9\n"
         "fmt.Println(original, copia)  // [1 2 3] [9 2 3]",
         "Chamar append sem guardar o resultado."),
        ("concorrencia", (r"\bgo\s+func\b", r"\bgo\s+\w+\(", r"<-", r"\bchan\b", r"\bdefer\b"), "Goroutines, canais e defer",
         "go f() roda f concorrentemente. Canais (chan) passam valores entre goroutines: ch <- v envia, <-ch recebe; "
         "close avisa que não há mais valores. defer executa uma chamada quando a função atual termina.",
         "valores := make(chan int)\ngo func() {\n\tdefer close(valores)\n\tfor i := 1; i <= 3; i++ {\n\t\tvalores <- i\n\t}\n}()\n"
         "for v := range valores {\n\tfmt.Println(v)\n}", "Terminar main antes das goroutines ou nunca fechar o canal usado em range."),
        ("main", (r"\bfunc\s+main\s*\(",), "func main · ponto de entrada",
         "func main() do package main é onde o programa começa. Não recebe parâmetros: os argumentos ficam em os.Args.",
         "package main\n\nimport (\n\t\"fmt\"\n\t\"os\"\n)\n\nfunc main() {\n\tfmt.Println(\"argumentos:\", len(os.Args)-1)\n}", ""),
    ],
    "rust": [
        ("let", (r"^\s*let\s+(?:mut\s+)?\w+",), "let e mut",
         "Variáveis são imutáveis por padrão; let mut permite alterar. O tipo é deduzido ou anotado (let soma: i32). "
         "let x = x + 1 cria uma nova variável com o mesmo nome (shadowing).",
         "let nome = \"Ana\";\nlet mut pontos = 0;\npontos += 10;\nprintln!(\"{nome}: {pontos}\");",
         "Tentar alterar uma variável declarada sem mut."),
        ("iteradores", (r"\bvec!\[", r"\.iter\(\)", r"\.(?:map|filter|sum|collect|copied|enumerate|fold)\s*\("), "Vec e iteradores",
         "vec![...] cria um vetor. .iter() empresta os itens; map e filter são preguiçosos e só executam quando um "
         "consumidor (sum, collect, for) pede os valores. |n| n * 2 é uma closure.",
         "let valores = vec![1, 2, 3, 4];\nlet soma: i32 = valores.iter().copied().filter(|n| n % 2 == 0).sum();\n"
         "let dobrados: Vec<i32> = valores.iter().map(|n| n * 2).collect();\nprintln!(\"{soma} {dobrados:?}\");", ""),
        ("atributos", (r"#\[derive\(", r"#\[(?:test|cfg)"), "#[derive] e atributos",
         "#[derive(Debug, PartialEq)] gera implementações automáticas: imprimir com {:?} e comparar com ==. #[cfg(test)] "
         "compila o módulo só nos testes; #[test] marca uma função de teste executada por cargo test.",
         "#[derive(Debug, PartialEq)]\nenum Estado { Pendente, Feita }\n\n#[cfg(test)]\nmod tests {\n    use super::*;\n"
         "    #[test]\n    fn compara() {\n        assert_eq!(Estado::Feita, Estado::Feita);\n    }\n}", ""),
        ("enum_match", (r"\benum\s+\w+", r"\bmatch\s+\w"), "enum e match",
         "enum lista variantes, que podem carregar dados. match precisa cobrir todas as variantes; _ cobre as restantes. "
         "O compilador avisa quando um caso foi esquecido.",
         "enum Forma { Circulo(f64), Retangulo(f64, f64) }\n\nfn area(f: &Forma) -> f64 {\n    match f {\n"
         "        Forma::Circulo(r) => 3.14159 * r * r,\n        Forma::Retangulo(l, a) => l * a,\n    }\n}", ""),
        ("result", (r"\b(?:Result|Option|Some|None|Ok|Err)\b", r"\?\s*;", r"\.unwrap\(\)"), "Option, Result e ?",
         "Option<T> é Some(valor) ou None; Result<T, E> é Ok(valor) ou Err(erro). O operador ? devolve o erro para quem "
         "chamou. unwrap() derruba o programa se não houver valor — use match, if let ou ?.",
         "fn dobro(texto: &str) -> Result<i32, std::num::ParseIntError> {\n    let n: i32 = texto.trim().parse()?;\n    Ok(n * 2)\n}\n\n"
         "fn main() {\n    match dobro(\"21\") {\n        Ok(v) => println!(\"{v}\"),\n        Err(e) => eprintln!(\"inválido: {e}\"),\n    }\n}",
         "Espalhar unwrap() em entradas do usuário."),
        ("println", (r"\b(?:println|print|eprintln|format)!\s*\(",), "println! e format!",
         "Macros terminam com !. {} usa a formatação Display; {:?} usa Debug; {:.2} limita casas decimais; {nome} insere "
         "uma variável pelo nome.",
         "let media = 7.456;\nlet nomes = vec![\"Ana\", \"Bia\"];\nprintln!(\"{media:.2} {nomes:?}\");", ""),
    ],
    "ruby": [
        ("saida", (r"^\s*(?:p|puts|pp|print)\b",), "puts, p e print",
         "puts imprime com quebra de linha (arrays, um item por linha); p mostra a representação para depuração (strings "
         "com aspas) e devolve o valor; print não quebra a linha.",
         "valores = [1, 2]\nputs valores\np valores\nprint \"sem quebra\", \"\\n\"", ""),
        ("require", (r"^\s*require(?:_relative)?\b",), "require e require_relative",
         "require carrega bibliotecas instaladas ou da biblioteca padrão (\"json\", \"set\"); require_relative carrega um "
         "arquivo do projeto pelo caminho relativo ao arquivo atual.",
         "require \"json\"\nrequire_relative \"calculos\"\n\nputs JSON.generate({ total: soma(2, 3) })", ""),
        ("blocos", (r"\{\s*\|\w", r"\bdo\s*\|"), "Blocos { |x| … } e do … end",
         "Blocos são trechos de código passados a métodos: { |x| x * 2 } numa linha, do |x| ... end em várias. O "
         "último valor do bloco é o resultado.",
         "dobrados = [1, 2, 3].map { |n| n * 2 }\n[1, 2].each do |n|\n  puts \"Número #{n}\"\nend", ""),
        ("enumerable", (r"\.(?:each|map|select|reject|sum|count|each_line|reduce|inject|each_with_index|tally)\b",), "Enumerable",
         "map transforma, select filtra, reject exclui, sum soma, count conta e tally conta ocorrências. Funcionam em "
         "arrays, hashes, intervalos e leitores de arquivo.",
         "palavras = %w[ana bia ana]\np palavras.tally          # {\"ana\"=>2, \"bia\"=>1}\np (1..10).select(&:even?).sum", ""),
        ("testes", (r"\bassert(?:_equal|_raises|_nil|_includes)?\b", r"minitest"), "Testes com Minitest",
         "require \"minitest/autorun\" executa as classes de teste ao final. assert_equal esperado, obtido compara; "
         "assert_raises verifica se um erro é lançado.",
         "require \"minitest/autorun\"\n\ndef total(valores) = valores.sum\n\nclass TotalTest < Minitest::Test\n"
         "  def test_soma\n    assert_equal 30, total([10, 20])\n  end\nend", ""),
    ],
    "julia": [
        ("funcao_curta", (r"^\s*\w+\([^)]*\)\s*=[^=]",), "Funções curtas e despacho múltiplo",
         "dobro(x) = x * 2 define uma função numa linha. Com tipos, cada versão vira um método: dobro(x::Number) e "
         "dobro(x::AbstractString) coexistem, e Julia escolhe pelo tipo dos argumentos.",
         "dobro(x::Number) = x * 2\ndobro(x::AbstractString) = x * x\nprintln(dobro(4), \" \", dobro(\"ab\"))  # 8 abab", ""),
        ("using", (r"^\s*using\b", r"@testset", r"@test\b"), "using e testes",
         "using Statistics carrega o pacote e traz seus nomes exportados. @testset agrupa testes e @test confere uma "
         "expressão booleana.",
         "using Test, Statistics\n\n@testset \"média\" begin\n    @test mean([2, 4]) == 3\nend", ""),
        ("missing", (r"\bmissing\b", r"\bskipmissing\b"), "missing · valores ausentes",
         "missing representa um dado ausente e se propaga nas contas (1 + missing é missing). skipmissing ignora os "
         "ausentes ao calcular.",
         "using Statistics\nmedidas = [2, missing, 4]\nprintln(mean(skipmissing(medidas)))  # 3.0", ""),
        ("indices", (r"\w\[\d+\]\s*=",), "Índices começam em 1",
         "Arrays em Julia começam no índice 1 e terminam em end. Atribuir a um índice altera o array no lugar; copy cria "
         "uma cópia independente.",
         "original = [1, 2, 3]\ncopia = copy(original)\ncopia[1] = 9\nprintln(original, copia[end])", ""),
    ],
    "r": [
        ("funcao", (r"<-\s*function\s*\(",), "Funções em R",
         "nome <- function(parâmetros) corpo. O último valor calculado é devolvido; return é opcional. Parâmetros podem "
         "ter valor padrão.",
         "media_segura <- function(x, na.rm = TRUE) {\n  if (length(x) == 0) return(NA)\n  mean(x, na.rm = na.rm)\n}\n"
         "print(media_segura(c(2, NA, 4)))", ""),
        ("na", (r"\bis\.na\s*\(", r"\[!"), "NA e filtros lógicos",
         "is.na(x) indica os valores ausentes; x[!is.na(x)] mantém só os presentes. Muitas funções aceitam na.rm = TRUE.",
         "notas <- c(7, NA, 9)\nvalidas <- notas[!is.na(notas)]\nprint(mean(validas))", ""),
        ("stopifnot", (r"\bstopifnot\s*\(",), "stopifnot · verificações",
         "stopifnot(condição) interrompe com erro quando a condição é falsa: uma forma simples de testar suposições.",
         "dobro <- function(x) x * 2\nstopifnot(dobro(2) == 4, is.numeric(dobro(1.5)))", ""),
        ("print", (r"^\s*print\s*\(",), "print em R",
         "print mostra um objeto (vetores, data frames, listas) no formato adequado. cat junta textos sem aspas.",
         "valores <- c(10, 20)\nprint(valores)\ncat(\"Total:\", sum(valores), \"\\n\")", ""),
        ("colunas", (r"\$\w+",), "Colunas com $",
         "df$coluna acessa uma coluna de um data frame ou um elemento de uma lista pelo nome.",
         "resumo <- data.frame(categoria = c(\"A\", \"B\"), valor = c(30, 5))\nprint(resumo$valor[resumo$categoria == \"A\"])", ""),
    ],
    "bash": [
        ("shebang", (r"^#!",), "#! · shebang",
         "A primeira linha diz qual interpretador executa o script: #!/usr/bin/env bash procura o bash no PATH. Dê "
         "permissão com chmod +x script.sh e rode ./script.sh.",
         "#!/usr/bin/env bash\nset -euo pipefail\necho \"Olá, $USER\"", ""),
        ("modo_seguro", (r"^\s*set\s+-[euxo]",), "set -euo pipefail · modo seguro",
         "-e encerra no primeiro comando com erro; -u acusa variável não definida; -o pipefail faz um pipeline falhar se "
         "qualquer comando falhar, não só o último.",
         "#!/usr/bin/env bash\nset -euo pipefail\n\ngrep -c erro app.log | tee total.txt", ""),
        ("aspas", (r"\"\$\{?\w+",), "Aspas em variáveis",
         "Use \"$var\": sem aspas, espaços dividem o valor em várias palavras e * vira uma lista de arquivos.",
         "arquivo=\"relatório final.txt\"\ntouch \"$arquivo\"\nls -l \"$arquivo\"",
         "Escrever rm $arquivo sem aspas num nome com espaço."),
        ("substituicao", (r"\$\(\(", r"\$\("), "$(comando) e $((conta))",
         "$(comando) substitui pelo resultado do comando; $((expressão)) faz contas com inteiros.",
         "hoje=$(date +%F)\nn=21\necho \"$hoje: $((n * 2))\"", ""),
        ("testes", (r"\[\[", r"^\s*if\s+\["), "Testes com [[ ]]",
         "[[ ... ]] avalia condições: -f arquivo existe, -d pasta, -z texto vazio, == compara textos e -lt/-gt comparam "
         "números.",
         "if [[ -f config.txt && $# -gt 0 ]]; then\n  echo \"config encontrada, $# argumento(s)\"\nfi", ""),
    ],
}


def ampliar_construcoes(C) -> list:
    out = []
    for lang, verbetes in REFERENCIA.items():
        for chave, padroes, titulo, texto, exemplo, erro in verbetes:
            # "#!" é comentário no léxico: o shebang também é reconhecido pelas palavras da linha.
            palavras = ("#!/",) if chave == "shebang" else ()
            out.append(C(f"{lang}_ref_{chave}", titulo, "referencia", texto, _PRATIQUE, linha={lang: padroes},
                         palavras=palavras, exemplos={lang: exemplo}, fontes=(FONTES[lang],), erros_comuns=erro))
    return out
