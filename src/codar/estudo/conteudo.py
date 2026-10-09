"""Material de estudo: os conceitos que o painel ESTUDO explica enquanto você programa.

Cada conceito tem uma explicação curta, um exemplo, um exercício e como reconhecê-lo numa linha de código (por
linguagem) ou num comentário. Exemplos em `pseudo` são compilados pelo CODAR para a linguagem do arquivo aberto;
`exemplos` são escritos à mão (Python e JavaScript), para o que o compilador não gera (métodos, herança…).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Conceito:
    id: str
    titulo: str
    trilha: str  # "fundamentos" | "poo" | "web"
    texto: str
    pratique: str
    linha: dict[str, tuple[str, ...]] = field(default_factory=dict)  # grupo de linguagem -> regex na linha de código
    palavras: tuple[str, ...] = ()  # em comentários: "# quero uma classe Pessoa…"
    pseudo: str = ""  # exemplo em pseudocódigo (compilado para a linguagem do arquivo)
    exemplos: dict[str, str] = field(default_factory=dict)  # exemplos escritos à mão, por grupo de linguagem
    relacionados: tuple[str, ...] = ()


TRILHAS = {"fundamentos": "FUNDAMENTOS", "poo": "ORIENTAÇÃO A OBJETOS", "web": "JAVASCRIPT E WEB"}

CONCEITOS: list[Conceito] = [
    # ------------------------------------------------------------------------------------------- fundamentos
    Conceito(
        "variavel", "Variável", "fundamentos",
        "Uma variável é um nome que guarda um valor para usar depois. O = guarda (não compara): idade = 20 lê-se "
        "\"idade recebe 20\". O valor pode mudar ao longo do programa, e o nome deve dizer o que ele guarda.",
        "Crie as variáveis nome e idade, mude a idade para idade + 1 e imprima as duas.",
        linha={"py": (r"^\s*[a-z_]\w*\s*(?:: *\w+\s*)?=[^=]",), "js": (r"^\s*(?:let|const|var)\s+\w+",),
               "*": (r"^\s*\w+\s*:?=[^=]",)},
        palavras=("variável", "variavel", "guardar", "valor"),
        pseudo="idade é igual a 20\nidade é igual a idade mais 1\nimprimir idade",
        relacionados=("conversao", "texto")),
    Conceito(
        "print", "Mostrar na tela", "fundamentos",
        "print (console.log no JavaScript) escreve na tela. É a forma mais simples de ver o que o programa está "
        "fazendo: imprimir uma variável antes da linha que dá erro mostra o valor que ela tinha.",
        "Imprima uma frase que junte texto e uma variável (veja o conceito \"Montar textos\").",
        linha={"py": (r"\bprint\(",), "js": (r"\bconsole\.(?:log|error)\(",), "*": (r"\b(?:printf|println|Println|puts|echo|Write-Output)\b",)},
        palavras=("imprimir", "mostrar", "exibir", "print"),
        pseudo="imprimir 'Olá, mundo!'", relacionados=("fstring",)),
    Conceito(
        "input", "Ler do teclado", "fundamentos",
        "input() mostra uma pergunta e espera a pessoa digitar e apertar Enter. Ele sempre devolve texto: mesmo que a "
        "pessoa digite 20, o valor é \"20\". Para fazer contas, converta com int() ou float().",
        "Pergunte o nome e a idade e responda \"Ana, ano que vem você terá 21 anos\".",
        linha={"py": (r"\binput\(",), "js": (r"\b(?:prompt|readline|question)\(",), "*": (r"\b(?:scanf|Scanner|ReadLine|read -r)\b",)},
        palavras=("perguntar", "digitar", "entrada", "ler do teclado", "input"),
        pseudo="pedir o nome ao usuário\nimprimir 'Olá, ' + nome", relacionados=("conversao", "variavel")),
    Conceito(
        "conversao", "Converter tipos", "fundamentos",
        "Cada valor tem um tipo: texto (str), inteiro (int), número com casas decimais (float), verdadeiro/falso "
        "(bool). Python não mistura tipos sozinho: \"10\" + 5 é erro. Converta: int(\"10\"), float(\"2.5\"), str(5).",
        "Leia dois números com input, converta e imprima a soma (e não a junção dos textos).",
        linha={"py": (r"\b(?:int|float|str|bool)\(",), "js": (r"\b(?:Number|parseInt|parseFloat|String)\(",)},
        palavras=("converter", "conversão", "inteiro", "número", "tipo"),
        pseudo="perguntar a idade do usuário como inteiro\nimprimir idade mais 1", relacionados=("input", "excecao")),
    Conceito(
        "fstring", "Montar textos", "fundamentos",
        "Para juntar texto e valores, use uma f-string: f\"Olá, {nome}! Você tem {idade} anos\". O que está entre "
        "chaves é calculado e convertido para texto sozinho. No JavaScript, a mesma ideia usa crases: `Olá, ${nome}`.",
        "Imprima o total de uma compra com duas casas: f\"Total: R$ {total:.2f}\".",
        linha={"py": (r"\bf[\"']",), "js": (r"`[^`]*\$\{",)},
        palavras=("formatar", "juntar texto", "concatenar", "f-string", "mensagem"),
        exemplos={"py": 'nome = "Ana"\nidade = 20\nprint(f"Olá, {nome}! Você tem {idade} anos.")\n'
                        'print(f"Ano que vem: {idade + 1}")',
                  "js": 'const nome = "Ana";\nconst idade = 20;\nconsole.log(`Olá, ${nome}! Você tem ${idade} anos.`);'},
        relacionados=("texto", "print")),
    Conceito(
        "texto", "Textos (strings)", "fundamentos",
        "Texto fica entre aspas, simples ou duplas (as mesmas para abrir e fechar). Textos têm métodos úteis: "
        ".upper(), .lower(), .strip() (tira espaços das pontas), .split() (quebra em lista), .replace(a, b).",
        "Leia um nome com input, tire os espaços com .strip() e imprima em maiúsculas.",
        linha={"py": (r"\.(?:upper|lower|strip|split|replace|join|startswith|endswith)\(",),
               "js": (r"\.(?:toUpperCase|toLowerCase|trim|split|replace|includes)\(",)},
        palavras=("texto", "string", "palavra", "frase", "maiúscula"),
        exemplos={"py": 'frase = "  aprender Python  "\nprint(frase.strip().upper())\nprint(frase.split())',
                  "js": 'const frase = "  aprender JavaScript  ";\nconsole.log(frase.trim().toUpperCase());'},
        relacionados=("fstring", "lista")),
    Conceito(
        "if", "Decisões (if, elif, else)", "fundamentos",
        "if executa um bloco só quando a condição é verdadeira; elif testa outra condição; else cobre o resto. As "
        "comparações usam == (igual), != (diferente), >, <, >=, <=, e se combinam com and, or e not. A linha termina "
        "com dois-pontos e o bloco de dentro vai indentado.",
        "Leia uma nota e imprima \"aprovado\" (7 ou mais), \"recuperação\" (5 a 6.9) ou \"reprovado\".",
        linha={"py": (r"^\s*(?:if|elif|else)\b",), "js": (r"^\s*(?:\}\s*)?(?:if|else)\b",), "*": (r"^\s*(?:\}\s*)?(?:if|else|elif|elsif)\b",)},
        palavras=("condição", "se ", "senão", "caso", "decidir", "verificar"),
        pseudo="idade é igual a 20\nse idade maior que 17\n    imprimir 'maior de idade'\nsenão\n    imprimir 'menor de idade'",
        relacionados=("indentacao", "while")),
    Conceito(
        "for", "Repetição com for", "fundamentos",
        "for repete um bloco para cada item de uma sequência: for nome in nomes passa por cada nome da lista. Para "
        "repetir N vezes, use range: for i in range(3) dá 0, 1 e 2.",
        "Some todos os números de uma lista com um for (sem usar sum) e imprima o total.",
        linha={"py": (r"^\s*for\s+\w+",), "js": (r"^\s*for\s*\(", r"\.forEach\("), "*": (r"^\s*for\b",)},
        palavras=("para cada", "percorrer", "repetir", "laço", "loop", "cada item"),
        pseudo="nomes é igual a ['Ana', 'Bia', 'Caio']\npara cada nome em nomes imprimir nome\nrepetir 3 vezes imprimir 'oi'",
        relacionados=("lista", "while")),
    Conceito(
        "while", "Repetição com while", "fundamentos",
        "while repete enquanto a condição for verdadeira. Algo dentro do bloco precisa mudar a condição, senão o laço "
        "nunca termina (Ctrl+C interrompe). Use while quando não se sabe quantas vezes vai repetir, como num menu.",
        "Peça números até a pessoa digitar 0 e imprima a soma deles.",
        linha={"py": (r"^\s*while\b",), "js": (r"^\s*(?:do|while)\b",), "*": (r"^\s*while\b",)},
        palavras=("enquanto", "até que", "repetir até", "while"),
        exemplos={"py": "contador = 0\nwhile contador < 3:\n    print(contador)\n    contador += 1",
                  "js": "let contador = 0;\nwhile (contador < 3) {\n  console.log(contador);\n  contador++;\n}"},
        relacionados=("for", "if")),
    Conceito(
        "lista", "Listas", "fundamentos",
        "Uma lista guarda vários valores em ordem: nomes = [\"Ana\", \"Bia\"]. As posições começam em 0 (nomes[0] é "
        "\"Ana\"); len(nomes) dá o tamanho; .append(x) acrescenta no fim. No JavaScript a lista se chama array.",
        "Crie uma lista de compras, acrescente dois itens e imprima cada um com a posição (use enumerate).",
        linha={"py": (r"=\s*\[", r"\.append\(", r"\blen\("), "js": (r"=\s*\[", r"\.push\(", r"\.length\b")},
        palavras=("lista", "vetor", "array", "vários valores", "coleção"),
        pseudo="nomes é igual a ['Ana', 'Bia']\nadicionar 'Caio' em nomes\npara cada nome em nomes imprimir nome",
        relacionados=("for", "dicionario", "compreensao")),
    Conceito(
        "dicionario", "Dicionários", "fundamentos",
        "Um dicionário guarda pares chave: valor, como uma ficha: pessoa = {\"nome\": \"Ana\", \"idade\": 20}. Lê-se "
        "pela chave (pessoa[\"nome\"]); .get(chave) devolve None em vez de erro quando a chave não existe. No "
        "JavaScript, o equivalente é o objeto literal { nome: \"Ana\" }.",
        "Conte quantas vezes cada palavra aparece numa frase usando um dicionário.",
        linha={"py": (r"=\s*\{[^}]*:", r"\.get\(", r"\.items\(\)"), "js": (r"=\s*\{\s*$", r"=\s*\{\s*\w+\s*:")},
        palavras=("dicionário", "dicionario", "chave", "mapa", "ficha"),
        exemplos={"py": 'pessoa = {"nome": "Ana", "idade": 20}\nprint(pessoa["nome"])\npessoa["cidade"] = "Recife"\n'
                        'for chave, valor in pessoa.items():\n    print(chave, "=", valor)',
                  "js": 'const pessoa = { nome: "Ana", idade: 20 };\nconsole.log(pessoa.nome);\npessoa.cidade = "Recife";'},
        relacionados=("lista", "classe")),
    Conceito(
        "funcao", "Funções", "fundamentos",
        "Uma função é um bloco de código com nome, que você escreve uma vez e usa quantas vezes quiser. Ela recebe "
        "valores (parâmetros) e pode devolver um resultado com return. Funções pequenas, que fazem uma coisa só, "
        "deixam o programa fácil de ler e de testar.",
        "Escreva uma função media(a, b) que devolve a média e use com três pares de números.",
        linha={"py": (r"^def\s+\w+", r"^\s*return\b"), "js": (r"\bfunction\s+\w+", r"^\s*return\b"),
               "*": (r"^\s*(?:func|fn|def|function|sub)\s+\w+",)},
        palavras=("função", "funcao", "reutilizar", "parâmetro", "retornar", "return"),
        pseudo="definir função dobro que recebe x e retorna x vezes 2",
        relacionados=("main", "metodo")),
    Conceito(
        "import", "Módulos e import", "fundamentos",
        "import traz código de outro arquivo ou biblioteca. from conta import Conta busca a classe Conta no arquivo "
        "conta.py da mesma pasta. Bibliotecas de fora (pandas, requests) precisam ser instaladas com pip antes.",
        "Separe uma função num arquivo util.py e use-a em main.py com from util import nome_da_funcao.",
        linha={"py": (r"^\s*(?:import|from)\s+\w+",), "js": (r"^\s*(?:import|export)\b", r"\brequire\("),
               "*": (r"^\s*(?:import|#include|using|use)\b",)},
        palavras=("importar", "módulo", "biblioteca", "pacote", "import"),
        exemplos={"py": "# conta.py define a classe; main.py usa:\nfrom conta import Conta\n\nconta = Conta(\"Ana\", 100)",
                  "js": "// conta.js: export class Conta { ... }\nimport { Conta } from \"./conta.js\";\n\nconst conta = new Conta(\"Ana\", 100);"},
        relacionados=("main",)),
    Conceito(
        "excecao", "Tratar erros (try/except)", "fundamentos",
        "Alguns erros são esperados: a pessoa digita \"abc\" onde devia digitar um número, o arquivo não existe. "
        "try executa o código; se acontecer o erro indicado em except, o programa trata em vez de parar.",
        "Peça um número até a pessoa digitar um válido, tratando ValueError.",
        linha={"py": (r"^\s*(?:try|except|finally|raise)\b",), "js": (r"^\s*(?:\}\s*)?(?:try|catch|finally|throw)\b",),
               "*": (r"\b(?:try|catch|except|rescue|throw|raise)\b",)},
        palavras=("erro", "exceção", "excecao", "tratar", "validar", "try"),
        exemplos={"py": 'while True:\n    try:\n        idade = int(input("Idade: "))\n        break\n'
                        '    except ValueError:\n        print("Digite só números.")',
                  "js": 'try {\n  const dados = JSON.parse(texto);\n} catch (erro) {\n  console.error("JSON inválido:", erro.message);\n}'},
        relacionados=("conversao", "arquivo")),
    Conceito(
        "arquivo", "Arquivos", "fundamentos",
        "with open(\"dados.txt\") as arquivo abre o arquivo e fecha sozinho no fim do bloco. \"r\" lê (padrão), \"w\" "
        "escreve do zero, \"a\" acrescenta no fim. Use encoding=\"utf-8\" para acentos funcionarem em qualquer sistema.",
        "Salve uma lista de nomes num arquivo, um por linha, e depois leia e imprima.",
        linha={"py": (r"\bopen\(", r"\bPath\("), "js": (r"\b(?:readFile|writeFile|readFileSync|Bun\.file)\b",)},
        palavras=("arquivo", "salvar", "ler arquivo", "gravar", "csv", "txt"),
        exemplos={"py": 'with open("nomes.txt", "w", encoding="utf-8") as arquivo:\n    arquivo.write("Ana\\nBia\\n")\n\n'
                        'with open("nomes.txt", encoding="utf-8") as arquivo:\n    for linha in arquivo:\n        print(linha.strip())'},
        relacionados=("excecao",)),
    Conceito(
        "indentacao", "Indentação", "fundamentos",
        "Em Python, os espaços no começo da linha dizem o que está dentro de quê: depois de uma linha com dois-pontos "
        "(if, for, def, class), o bloco vem 4 espaços para a direita, e voltar à margem anterior encerra o bloco. Os "
        "pontinhos do editor mostram os níveis.",
        "Escreva um for com um if dentro e observe os níveis de indentação (pontinhos).",
        palavras=("indentação", "indentacao", "espaços", "bloco"),
        exemplos={"py": "for n in [1, 2, 3]:\n    if n > 1:\n        print(n, \"é maior que 1\")\n    print(\"fim da volta\")\nprint(\"fim do for\")"},
        relacionados=("if", "for")),
    Conceito(
        "compreensao", "Compreensão de lista", "fundamentos",
        "Uma forma curta de criar uma lista a partir de outra: [x * 2 for x in numeros] dobra cada número; com if, "
        "filtra: [x for x in numeros if x > 0]. Use quando a lógica cabe numa linha; se ficar difícil de ler, um for "
        "normal é melhor.",
        "Crie a lista dos quadrados dos números pares de 1 a 10 numa linha.",
        linha={"py": (r"\[[^\]]+\bfor\b[^\]]+\bin\b",), "js": (r"\.(?:map|filter)\(",)},
        palavras=("compreensão", "list comprehension", "transformar lista", "filtrar"),
        exemplos={"py": "numeros = [1, 2, 3, 4]\ndobros = [n * 2 for n in numeros]\npares = [n for n in numeros if n % 2 == 0]\nprint(dobros, pares)"},
        relacionados=("lista", "for")),
    Conceito(
        "main", "Ponto de entrada", "fundamentos",
        "if __name__ == \"__main__\": marca o código que roda só quando o arquivo é executado direto (F5), e não quando "
        "ele é importado por outro. Assim conta.py pode definir a classe e main.py usa, sem um rodar o código do outro.",
        "Mova o código solto do seu arquivo para uma função main() e chame dentro do if __name__ == \"__main__\".",
        linha={"py": (r"__name__\s*==\s*['\"]__main__",), "*": (r"\b(?:static void main|func main|fn main|int main)\b",)},
        palavras=("main", "ponto de entrada", "executar", "começo do programa"),
        exemplos={"py": 'def main() -> None:\n    print("o programa começa aqui")\n\n\nif __name__ == "__main__":\n    main()'},
        relacionados=("import", "funcao")),

    # ------------------------------------------------------------------------------------------------- POO
    Conceito(
        "classe", "Classe", "poo",
        "Uma classe é o molde de um tipo de coisa do seu programa: diz quais dados cada objeto tem (atributos) e o que "
        "ele sabe fazer (métodos). A classe Conta descreve contas em geral; cada conta de verdade (a da Ana, a do "
        "Bruno) é um objeto criado a partir dela. O nome de classe começa com maiúscula.",
        "Escolha algo do seu dia (Livro, Pet, Produto) e crie a classe com dois atributos.",
        linha={"py": (r"^\s*class\s+[A-Za-z_]\w*\s*[:(]",), "js": (r"^\s*(?:export\s+)?class\s+\w+",),
               "*": (r"^\s*(?:public\s+)?(?:data\s+)?(?:class|struct|record)\s+\w+",)},
        palavras=("classe", "molde", "class"),
        pseudo="criar uma classe Pessoa com nome e idade",
        exemplos={"py": "class Conta:\n    def __init__(self, titular, saldo=0):\n        self.titular = titular\n        self.saldo = saldo",
                  "js": "class Conta {\n  constructor(titular, saldo = 0) {\n    this.titular = titular;\n    this.saldo = saldo;\n  }\n}"},
        relacionados=("objeto", "construtor", "atributo")),
    Conceito(
        "construtor", "Construtor (__init__)", "poo",
        "O construtor é o método que roda quando um objeto nasce: Conta(\"Ana\", 100) chama __init__(self, titular, "
        "saldo). Ele recebe os dados iniciais e guarda no objeto. No JavaScript ele se chama constructor.",
        "Dê à sua classe um __init__ que receba e guarde dois dados, com um valor padrão em um deles.",
        linha={"py": (r"\bdef\s+__init__\s*\(",), "js": (r"^\s*constructor\s*\(",)},
        palavras=("construtor", "__init__", "inicializar", "criar o objeto"),
        exemplos={"py": "class Pessoa:\n    def __init__(self, nome, idade=0):\n        self.nome = nome\n        self.idade = idade\n\n\nana = Pessoa(\"Ana\", 20)  # chama o __init__",
                  "js": "class Pessoa {\n  constructor(nome, idade = 0) {\n    this.nome = nome;\n    this.idade = idade;\n  }\n}\n\nconst ana = new Pessoa(\"Ana\", 20);"},
        relacionados=("atributo", "objeto")),
    Conceito(
        "atributo", "Atributos (self)", "poo",
        "Atributos são os dados de cada objeto: self.saldo é o saldo desta conta. self é o próprio objeto que está "
        "sendo usado; cada objeto tem os seus atributos, então mudar ana.saldo não muda bruno.saldo. No JavaScript, "
        "self se chama this.",
        "Crie dois objetos da sua classe, mude um atributo de um deles e imprima os dois para ver a diferença.",
        linha={"py": (r"\bself\.\w+\s*(?:[+\-*/]?=)(?!=)",), "js": (r"\bthis\.\w+\s*=(?!=)",)},
        palavras=("atributo", "propriedade", "self", "this", "característica"),
        exemplos={"py": "ana = Pessoa(\"Ana\", 20)\nbruno = Pessoa(\"Bruno\", 31)\nana.idade = 21\nprint(ana.idade, bruno.idade)  # 21 31"},
        relacionados=("construtor", "encapsulamento")),
    Conceito(
        "metodo", "Métodos", "poo",
        "Métodos são as ações do objeto: funções definidas dentro da classe que usam e alteram os atributos. O "
        "primeiro parâmetro é sempre self. conta.depositar(50) chama depositar com self = conta e valor = 50.",
        "Crie um método que altere um atributo (depositar, aniversario…) e outro que devolva um texto.",
        linha={"py": (r"^\s+def\s+(?!__)\w+\s*\(\s*self\b",), "js": (r"^\s+(?:async\s+)?(?!if\b|for\b|while\b|switch\b|catch\b|function\b)\w+\s*\([^)]*\)\s*\{",)},
        palavras=("método", "metodo", "ação", "comportamento"),
        exemplos={"py": "class Conta:\n    def __init__(self, saldo=0):\n        self.saldo = saldo\n\n    def depositar(self, valor):\n        if valor <= 0:\n            raise ValueError(\"valor inválido\")\n        self.saldo += valor\n\n\nconta = Conta()\nconta.depositar(50)",
                  "js": "class Conta {\n  constructor(saldo = 0) {\n    this.saldo = saldo;\n  }\n\n  depositar(valor) {\n    this.saldo += valor;\n  }\n}"},
        relacionados=("atributo", "objeto")),
    Conceito(
        "objeto", "Objetos (instâncias)", "poo",
        "Um objeto é uma coisa concreta criada a partir da classe: ana = Pessoa(\"Ana\", 20). Cada objeto tem os seus "
        "próprios atributos e usa os métodos da classe com o ponto: ana.aniversario(). Criar o objeto é chamar a "
        "classe como uma função (no JavaScript, com new).",
        "Crie uma lista com três objetos da sua classe e percorra com for chamando um método de cada um.",
        linha={"py": (r"\b\w+\s*=\s*[A-Z]\w*\(", r"\b[a-z_]\w*\.[a-z_]\w*\("), "js": (r"\bnew\s+[A-Z]\w*\(",),
               "*": (r"\bnew\s+[A-Z]\w*",)},
        palavras=("objeto", "instância", "instancia", "instanciar"),
        exemplos={"py": "contas = [Conta(\"Ana\", 100), Conta(\"Bia\", 50)]\nfor conta in contas:\n    conta.depositar(10)\n    print(conta.titular, conta.saldo)",
                  "js": "const contas = [new Conta(\"Ana\", 100), new Conta(\"Bia\", 50)];\nfor (const conta of contas) conta.depositar(10);"},
        relacionados=("classe", "metodo")),
    Conceito(
        "str", "Mostrar o objeto (__str__)", "poo",
        "print(conta) mostra algo como <Conta object at 0x7f…> porque o Python não sabe como você quer descrever o "
        "objeto. O método __str__ ensina: ele devolve o texto que o print usa. No JavaScript, toString().",
        "Escreva o __str__ da sua classe e imprima um objeto.",
        linha={"py": (r"\bdef\s+__(?:str|repr)__\s*\(",), "js": (r"^\s*toString\s*\(",)},
        palavras=("__str__", "imprimir objeto", "representação", "tostring"),
        exemplos={"py": "class Conta:\n    def __init__(self, titular, saldo=0):\n        self.titular = titular\n        self.saldo = saldo\n\n    def __str__(self):\n        return f\"{self.titular}: R$ {self.saldo:.2f}\"\n\n\nprint(Conta(\"Ana\", 100))  # Ana: R$ 100.00"},
        relacionados=("metodo",)),
    Conceito(
        "encapsulamento", "Encapsulamento", "poo",
        "Encapsular é proteger os dados do objeto para que só mudem do jeito certo. Por convenção, _saldo (com "
        "sublinhado) é interno; quem está fora usa métodos (depositar) que validam a regra. @property deixa ler "
        "conta.saldo como atributo sem permitir atribuir um valor inválido. No JavaScript, #saldo é privado de verdade.",
        "Torne um atributo interno (_nome) e crie uma @property para ler; tente impedir valores negativos.",
        linha={"py": (r"\bself\._\w+", r"^\s*@property\b", r"^\s*@\w+\.setter\b"), "js": (r"\bthis\.#\w+", r"^\s*#\w+\s*[;=]", r"^\s*get\s+\w+\(")},
        palavras=("encapsul", "privado", "proteger", "property", "getter", "setter"),
        exemplos={"py": "class Conta:\n    def __init__(self, saldo=0):\n        self._saldo = saldo  # interno\n\n    @property\n    def saldo(self):\n        return self._saldo\n\n    def depositar(self, valor):\n        if valor <= 0:\n            raise ValueError(\"valor inválido\")\n        self._saldo += valor",
                  "js": "class Conta {\n  #saldo = 0;\n  get saldo() { return this.#saldo; }\n  depositar(valor) {\n    if (valor <= 0) throw new Error(\"valor inválido\");\n    this.#saldo += valor;\n  }\n}"},
        relacionados=("atributo", "metodo")),
    Conceito(
        "heranca", "Herança", "poo",
        "Herança cria uma classe a partir de outra: class Poupanca(Conta) recebe tudo o que Conta tem e acrescenta ou "
        "muda o que for diferente. Use quando a filha é um tipo da mãe (uma poupança é uma conta).",
        "Crie uma classe filha da sua, com um atributo a mais e um método novo.",
        linha={"py": (r"^\s*class\s+\w+\s*\(\s*(?!object\b)[A-Z]\w*",), "js": (r"\bclass\s+\w+\s+extends\s+\w+",),
               "*": (r"\b(?:extends|implements)\b|class\s+\w+\s*:\s*\w+",)},
        palavras=("herança", "heranca", "herda", "herdar", "subclasse", "classe filha", "extends"),
        exemplos={"py": "class Poupanca(Conta):\n    def __init__(self, titular, saldo=0, taxa=0.005):\n        super().__init__(titular, saldo)\n        self.taxa = taxa\n\n    def render(self):\n        self.saldo += self.saldo * self.taxa",
                  "js": "class Poupanca extends Conta {\n  constructor(titular, saldo = 0, taxa = 0.005) {\n    super(titular, saldo);\n    this.taxa = taxa;\n  }\n}"},
        relacionados=("super", "polimorfismo")),
    Conceito(
        "super", "super()", "poo",
        "Na classe filha, super() acessa a classe mãe. super().__init__(...) roda o construtor da mãe para ela "
        "preparar os atributos dela, e depois a filha acrescenta os seus. Sem isso, os atributos da mãe não existem.",
        "No construtor da sua classe filha, chame super().__init__ antes de criar o atributo novo.",
        linha={"py": (r"\bsuper\(\)",), "js": (r"\bsuper\s*[(.]",)},
        palavras=("super", "classe mãe", "construtor da mãe"),
        exemplos={"py": "class Gerente(Funcionario):\n    def __init__(self, nome, salario, equipe):\n        super().__init__(nome, salario)\n        self.equipe = equipe"},
        relacionados=("heranca", "construtor")),
    Conceito(
        "polimorfismo", "Polimorfismo", "poo",
        "Polimorfismo é o mesmo comando funcionando de jeitos diferentes conforme o objeto: cada classe filha "
        "sobrescreve (redefine) um método da mãe. O código que chama não precisa saber o tipo: for forma in formas: "
        "print(forma.area()) funciona para círculos e quadrados.",
        "Crie duas classes filhas que sobrescrevem o mesmo método e chame-o numa lista com objetos das duas.",
        palavras=("polimorfismo", "sobrescrever", "sobrescrita", "override"),
        exemplos={"py": "class Forma:\n    def area(self):\n        return 0\n\n\nclass Quadrado(Forma):\n    def __init__(self, lado):\n        self.lado = lado\n\n    def area(self):\n        return self.lado ** 2\n\n\nclass Circulo(Forma):\n    def __init__(self, raio):\n        self.raio = raio\n\n    def area(self):\n        return 3.14159 * self.raio ** 2\n\n\nfor forma in [Quadrado(2), Circulo(1)]:\n    print(forma.area())"},
        relacionados=("heranca", "metodo")),
    Conceito(
        "composicao", "Composição", "poo",
        "Composição é um objeto ter outros objetos como atributos: um Pedido tem uma lista de Itens, uma Pessoa tem um "
        "Endereco. É o jeito mais comum de juntar classes; prefira composição quando a relação é \"tem um\" (e "
        "herança quando é \"é um\").",
        "Crie uma classe Endereco e dê à sua classe um atributo que seja um Endereco.",
        linha={"py": (r"\bself\.\w+\s*=\s*[A-Z]\w*\(", r"\bself\.\w+\s*=\s*\[\]"), "js": (r"\bthis\.\w+\s*=\s*new\s+[A-Z]",)},
        palavras=("composição", "composicao", "tem um", "dentro do objeto"),
        exemplos={"py": "class Item:\n    def __init__(self, nome, preco):\n        self.nome, self.preco = nome, preco\n\n\nclass Pedido:\n    def __init__(self):\n        self.itens = []  # um Pedido tem Itens\n\n    def adicionar(self, item):\n        self.itens.append(item)\n\n    def total(self):\n        return sum(i.preco for i in self.itens)"},
        relacionados=("classe", "lista")),

    # ---------------------------------------------------------------------------------------- JavaScript e web
    Conceito(
        "let_const", "let e const", "web",
        "const cria um nome que não recebe outro valor (o mais comum); let, um que pode mudar. Evite var, que tem "
        "regras de escopo confusas. const com lista ou objeto ainda deixa mudar o conteúdo, só não troca o objeto.",
        "Troque todos os var de um código por const ou let e veja quais precisavam mudar de valor.",
        linha={"js": (r"^\s*(?:let|const|var)\s+",)}, palavras=("let", "const", "var"),
        exemplos={"js": "const nome = \"Ana\";   // não muda\nlet pontos = 0;        // muda\npontos += 10;"},
        relacionados=("variavel",)),
    Conceito(
        "arrow", "Funções de seta (=>)", "web",
        "(x) => x * 2 é uma função curta: recebe x e devolve x * 2. É muito usada como argumento de map, filter, "
        "addEventListener e em componentes React. Com chaves, precisa de return: (x) => { return x * 2; }.",
        "Reescreva uma function pequena como função de seta.",
        linha={"js": (r"=>",)}, palavras=("arrow", "seta", "=>", "callback"),
        exemplos={"js": "const dobro = (x) => x * 2;\nconst numeros = [1, 2, 3].map((n) => dobro(n));"},
        relacionados=("funcao", "array_metodos")),
    Conceito(
        "array_metodos", "map, filter e reduce", "web",
        "Arrays têm métodos que recebem uma função: map transforma cada item (devolve um array novo), filter fica com "
        "os itens que passam no teste, reduce junta tudo num valor só (como uma soma).",
        "De uma lista de produtos {nome, preco}, faça a lista de nomes com preço acima de 50.",
        linha={"js": (r"\.(?:map|filter|reduce|find|some|every)\(",)}, palavras=("map", "filter", "reduce"),
        exemplos={"js": "const precos = [10, 60, 80];\nconst caros = precos.filter((p) => p > 50);\nconst total = precos.reduce((soma, p) => soma + p, 0);"},
        relacionados=("arrow", "lista")),
    Conceito(
        "async", "async e await", "web",
        "Algumas operações demoram (buscar dados na internet, ler arquivo). Uma função async pode usar await para "
        "esperar o resultado sem travar o resto. fetch devolve uma Promise: await fetch(url) espera a resposta.",
        "Busque um JSON com fetch e imprima um campo dele, tratando erro com try/catch.",
        linha={"js": (r"\basync\b", r"\bawait\b", r"\.then\(")}, palavras=("async", "await", "promise", "fetch"),
        exemplos={"js": "async function buscar() {\n  const resposta = await fetch(\"https://api.github.com\");\n  const dados = await resposta.json();\n  console.log(dados);\n}"},
        relacionados=("excecao",)),
    Conceito(
        "componente", "Componente React", "web",
        "Um componente React é uma função que devolve a tela em JSX (HTML dentro do JavaScript). Recebe dados por "
        "props e guarda estado com useState: quando o estado muda, o React redesenha só o necessário.",
        "Crie um componente Contador com um botão que soma 1 a cada clique.",
        linha={"js": (r"\buse[A-Z]\w*\(", r"return\s*\(?\s*<", r"<[A-Z]\w*[\s/>]")},
        palavras=("react", "componente", "jsx", "usestate", "props"),
        exemplos={"js": "import { useState } from \"react\";\n\nexport function Contador() {\n  const [n, setN] = useState(0);\n  return <button onClick={() => setN(n + 1)}>cliques: {n}</button>;\n}"},
        relacionados=("arrow",)),
    Conceito(
        "tipos_ts", "Tipos no TypeScript", "web",
        "TypeScript é JavaScript com tipos: nome: string, idade: number. O editor e o compilador avisam antes de rodar "
        "quando um valor não combina com o tipo. interface (ou type) descreve o formato de um objeto.",
        "Crie uma interface Produto e uma função que recebe um Produto e devolve o preço com desconto.",
        linha={"js": (r"^\s*(?:export\s+)?(?:interface|type)\s+\w+", r":\s*(?:string|number|boolean)\b")},
        palavras=("typescript", "interface", "tipo", "type"),
        exemplos={"js": "interface Produto {\n  nome: string;\n  preco: number;\n}\n\nfunction comDesconto(p: Produto, pct: number): number {\n  return p.preco * (1 - pct / 100);\n}"},
        relacionados=("classe",)),
]

POR_ID: dict[str, Conceito] = {c.id: c for c in CONCEITOS}
TRILHA_POO = ["classe", "construtor", "atributo", "metodo", "objeto", "str", "encapsulamento", "heranca", "super",
              "polimorfismo", "composicao"]
