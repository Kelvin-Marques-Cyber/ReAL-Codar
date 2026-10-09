"""Explica erros de programas em português: o que aconteceu, onde e como corrigir.

Sem rede e sem IA: regras para os erros mais comuns de quem está aprendendo, em Python, JavaScript/TypeScript (Node e
Bun), shell, Go, Rust, Java e C/C++. O Studio usa isto quando um programa termina com erro no terminal; na linha de
comando, `python app.py 2>&1 | codar explicar`.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Explicacao:
    tipo: str  # NameError, ReferenceError, comando não encontrado…
    titulo: str  # uma linha: o erro em português
    oque: str  # o que aconteceu
    como: str  # como corrigir
    arquivo: str | None = None
    linha: int | None = None
    trecho: str | None = None  # a linha de código que falhou, quando a saída mostra
    conceito: str | None = None  # assunto no material de estudo (ex.: "variavel")

    def texto(self) -> str:
        onde = f" (linha {self.linha} de {Path(self.arquivo).name})" if self.arquivo and self.linha else ""
        partes = [f"{self.tipo}: {self.titulo}{onde}"]
        if self.trecho:
            partes.append(f"    {self.trecho.strip()}")
        partes += [f"O que aconteceu: {self.oque}", f"Como corrigir: {self.como}"]
        return "\n".join(partes)


# nome no import -> pacote no pip (quando são diferentes)
PACOTES_PIP = {"cv2": "opencv-python-headless", "sklearn": "scikit-learn", "PIL": "pillow", "yaml": "pyyaml",
               "bs4": "beautifulsoup4", "skimage": "scikit-image", "dotenv": "python-dotenv", "jwt": "pyjwt",
               "Crypto": "pycryptodome", "serial": "pyserial", "usb": "pyusb", "dateutil": "python-dateutil",
               "docx": "python-docx", "pptx": "python-pptx", "fitz": "pymupdf", "magic": "python-magic",
               "telegram": "python-telegram-bot", "discord": "discord.py", "attr": "attrs", "OpenSSL": "pyopenssl",
               "git": "gitpython", "zmq": "pyzmq", "mpl_toolkits": "matplotlib", "google.protobuf": "protobuf",
               "MySQLdb": "mysqlclient", "psycopg2": "psycopg2-binary", "win32api": "pywin32", "Levenshtein": "levenshtein",
               "sentencepiece": "sentencepiece", "tflite_runtime": "tflite-runtime"}

_PY_ERRO = re.compile(r"^(?:[\w.]+\.)?(\w+(?:Error|Exception|Interrupt|Exit|Warning)|StopIteration)(?::\s*(.*))?$")
_PY_FRAME = re.compile(r'^\s*File "([^"]+)", line (\d+)')
_JS_ERRO = re.compile(r"^(?:Uncaught\s+)?(\w*Error)(?:\s*\[(\w+)\])?:\s*(.*)$")
_JS_FRAME = re.compile(r"\(?((?:file://)?/[^\s():]+|[A-Za-z]:\\[^\s():]+|\.{0,2}/?[\w./-]+\.[cm]?[jt]sx?):(\d+)(?::\d+)?\)?$")
_SH_NAO_ACHOU = [re.compile(p) for p in (r"^(?:ba|z|da|k)?sh: (?:\d+: )?(?:line \d+: )?([^\s:]+): (?:command )?not found$",
                                          r"^zsh: command not found: (\S+)$", r"^(\S+): comando não encontrado$",
                                          r"^(?:ba)?sh: (?:linha \d+: )?([^\s:]+): comando não encontrado$")]
_GO = re.compile(r"^(\S+\.go):(\d+):(\d+): (.+)$")  # o Go não escreve "error:"
_GCC = re.compile(r"^(\S+\.(?:java|c|cc|cpp|h|hpp|kt|cs)):(\d+)(?::\d+)?: (?:fatal )?error: (.+)$")  # gcc, javac
_TSC = re.compile(r"^(\S+\.[cm]?tsx?)(?:\((\d+),\d+\)|:(\d+):\d+) ?[-:] ?error (TS\d+): (.+)$")
_RUST_LOCAL = re.compile(r"^\s*--> ([^:]+):(\d+):(\d+)")
_INSTALAR = {"bun": "instale com: curl -fsSL https://bun.sh/install | bash (depois abra um terminal novo)",
             "node": "instale o Node.js pelo gerenciador do sistema (ex.: sudo zypper install nodejs) ou pelo nvm",
             "npm": "o npm vem junto com o Node.js: instale o pacote nodejs (ou nodejs-npm)",
             "npx": "o npx vem junto com o npm (Node.js)", "pnpm": "instale com: npm install -g pnpm (ou corepack enable)",
             "yarn": "ative com: corepack enable (vem com o Node.js)", "python": "use python3 (o nome comum no Linux)",
             "pip": "use python3 -m pip (ou crie um ambiente: python3 -m venv .venv)",
             "go": "instale o Go: sudo zypper install go (ou apt install golang)",
             "cargo": "instale o Rust com o rustup: curl https://sh.rustup.rs -sSf | sh",
             "rustc": "instale o Rust com o rustup: curl https://sh.rustup.rs -sSf | sh",
             "java": "instale um JDK: sudo zypper install java-21-openjdk-devel (ou apt install default-jdk)",
             "javac": "instale um JDK: sudo zypper install java-21-openjdk-devel (ou apt install default-jdk)",
             "gcc": "instale o compilador: sudo zypper install gcc (ou apt install build-essential)",
             "git": "instale o git: sudo zypper install git (ou apt install git)",
             "docker": "instale o Docker (ou o podman, que usa os mesmos comandos)",
             "flutter": "instale o Flutter SDK (flutter.dev) e ponha flutter/bin no PATH",
             "dart": "o Dart vem com o Flutter, ou instale o Dart SDK"}


def explicar(saida: str | list[str], raiz: Path | str | None = None) -> Explicacao | None:
    """A explicação do último erro na saída de um programa, ou None se não reconheceu nada."""
    linhas = saida.splitlines() if isinstance(saida, str) else list(saida)
    linhas = [ln.rstrip("\r") for ln in linhas][-400:]
    raiz = Path(raiz).resolve() if raiz else None
    for analisar in (_python, _outras, _javascript, _compiladores, _shell):  # específicas antes das genéricas
        exp = analisar(linhas, raiz)
        if exp is not None:
            return exp
    return None


def _no_projeto(caminho: str, raiz: Path | None) -> bool:
    if "site-packages" in caminho or "/lib/python" in caminho or "node_modules" in caminho or caminho.startswith("<"):
        return False
    if raiz is None:
        return True
    try:
        Path(caminho).resolve().relative_to(raiz)
        return True
    except (ValueError, OSError):
        return not Path(caminho).is_absolute()


def _codigo(arquivo: str | None, linha: int | None, raiz: Path | None) -> str | None:
    if not arquivo or not linha:
        return None
    caminho = Path(arquivo)
    if not caminho.is_absolute() and raiz is not None:
        caminho = raiz / caminho
    try:
        return caminho.read_text(encoding="utf-8", errors="replace").splitlines()[linha - 1]
    except (OSError, IndexError):
        return None


def _parecidos(nome: str, arquivo: str | None, raiz: Path | None) -> list[str]:
    """Nomes do arquivo parecidos com `nome` (erro de digitação: idade x idadde, Nome x nome)."""
    if not arquivo:
        return []
    caminho = Path(arquivo) if Path(arquivo).is_absolute() or raiz is None else raiz / arquivo
    try:
        texto = caminho.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    nomes = set(re.findall(r"[A-Za-z_]\w*", texto)) - {nome}
    iguais = [n for n in nomes if n.lower() == nome.lower()]
    return iguais or difflib.get_close_matches(nome, nomes, n=2, cutoff=0.75)


# ---------------------------------------------------------------------------------------------------------- Python
def _python(linhas: list[str], raiz: Path | None) -> Explicacao | None:
    fim = None
    for i in range(len(linhas) - 1, -1, -1):
        m = _PY_ERRO.match(linhas[i].strip())
        if m and (i == 0 or not linhas[i].startswith(" ")):
            fim = i
            break
    if fim is None:
        return None
    tipo, msg = _PY_ERRO.match(linhas[fim].strip()).group(1), (_PY_ERRO.match(linhas[fim].strip()).group(2) or "")
    frames = [(m.group(1), int(m.group(2)), i) for i, ln in enumerate(linhas[:fim]) if (m := _PY_FRAME.match(ln))]
    if not frames and tipo not in ("ModuleNotFoundError", "KeyboardInterrupt", "EOFError"):
        if not any(ln.startswith("Traceback (most recent call last)") for ln in linhas[:fim]):
            return None
    meus = [f for f in frames if _no_projeto(f[0], raiz)] or frames
    arquivo, linha, idx = meus[-1] if meus else (None, None, None)
    trecho = None
    if idx is not None and idx + 1 < fim and linhas[idx + 1].startswith("    ") and not _PY_FRAME.match(linhas[idx + 1]):
        trecho = linhas[idx + 1].strip()
    trecho = trecho or _codigo(arquivo, linha, raiz)
    exp = _regra_python(tipo, msg, arquivo, linha, trecho, raiz)
    exp.arquivo, exp.linha, exp.trecho = arquivo, linha, trecho
    return exp


def _regra_python(tipo: str, msg: str, arquivo, linha, trecho, raiz) -> Explicacao:
    def e(titulo: str, oque: str, como: str, conceito: str | None = None) -> Explicacao:
        return Explicacao(tipo, titulo, oque, como, conceito=conceito)

    if tipo == "NameError" and (m := re.search(r"name '(\w+)' is not defined", msg)):
        nome = m.group(1)
        parecidos = _parecidos(nome, arquivo, raiz)
        dica = f" Você quis dizer {' ou '.join(parecidos)}?" if parecidos else ""
        if nome in ("true", "false", "null", "none"):
            dica = f" Em Python escreve-se {'True' if nome == 'true' else 'False' if nome == 'false' else 'None'}."
        return e(f"o nome {nome} não existe", f"O programa usou {nome} antes de ele ser criado, ou o nome foi escrito "
                 f"diferente (Python diferencia maiúsculas e minúsculas).{dica}",
                 f"Crie {nome} antes desta linha (ex.: {nome} = ...) ou corrija o nome.", "variavel")
    if tipo == "UnboundLocalError" or (tipo == "NameError" and "free variable" in msg):
        nome = (re.search(r"'(\w+)'", msg) or re.search(r"(\w+)", msg)).group(1)
        return e(f"{nome} foi usada antes de receber valor dentro da função",
                 f"Dentro da função existe uma atribuição a {nome}, então o Python a trata como variável local; ela foi "
                 f"lida antes dessa atribuição.", f"Passe {nome} como parâmetro da função e devolva o novo valor com "
                 f"return (ou, se for mesmo uma variável global, declare global {nome} no início da função).", "funcao")
    if tipo == "TypeError":
        if re.search(r'can only concatenate str \(not "(\w+)"\) to str', msg) or "must be str, not" in msg:
            return e("juntou texto com número", "O + entre um texto e um número não funciona: Python não converte "
                     "sozinho.", "Use uma f-string: f\"Total: {total}\" (ou converta: \"Total: \" + str(total)).",
                     "fstring")
        if m := re.search(r"unsupported operand type\(s\) for ([^:]+): '(\w+)' and '(\w+)'", msg):
            op, a, b = m.groups()
            if "str" in (a, b):
                return e(f"operação {op.strip()} entre {a} e {b}", "Um dos valores é texto (str). O input() sempre devolve "
                         "texto, mesmo quando a pessoa digita um número.", "Converta antes de fazer a conta: "
                         "idade = int(input(\"Idade: \")) ou float(...) para números com vírgula.", "conversao")
            if "NoneType" in (a, b):
                return e(f"operação {op.strip()} com None", "Um dos valores é None: geralmente uma função que não "
                         "devolve nada (faltou o return).", "Confira se a função termina com return valor.", "funcao")
            return e(f"operação {op.strip()} entre {a} e {b}", f"Não dá para usar {op.strip()} entre {a} e {b}.",
                     "Converta um dos valores para o tipo do outro.", "conversao")
        if m := re.search(r"(\w+)\(\) missing (\d+) required positional argument[s]?: (.+)", msg):
            func, n, nomes = m.groups()
            if func == "__init__":
                return e("faltou argumento ao criar o objeto", f"O construtor (__init__) pede {nomes} e o objeto foi "
                         f"criado sem {'ele' if n == '1' else 'eles'}.", f"Passe os valores ao criar o objeto, na ordem "
                         f"dos parâmetros: Classe({nomes.replace(chr(39), '')}).", "construtor")
            return e(f"faltou argumento em {func}()", f"A função {func} pede {nomes} e foi chamada sem "
                     f"{'ele' if n == '1' else 'eles'}.", f"Chame {func}(...) passando {nomes}.", "funcao")
        if m := re.search(r"(\w+(?:\.\w+)?)\(\) takes (\d+) positional arguments? but (\d+) (?:were|was) given", msg):
            func, quer, deu = m.groups()
            if "." in func and int(deu) == int(quer) + 1:
                metodo = func.split(".")[-1]
                return e(f"faltou o self em {metodo}", "Ao chamar objeto.metodo(x), o Python passa o próprio objeto como "
                         "primeiro argumento. Na definição do método esse primeiro parâmetro (self) está faltando.",
                         f"Escreva def {metodo}(self, ...): na classe.", "metodo")
            return e(f"{func}() recebeu argumentos demais", f"{func} aceita {quer} e recebeu {deu}.",
                     "Confira a quantidade de argumentos na chamada e na definição da função.", "funcao")
        if m := re.search(r"'(\w+)' object is not callable", msg):
            return e(f"usou um {m.group(1)} como se fosse função", "Parênteses depois de um valor que não é função; "
                     "muitas vezes uma variável com o mesmo nome de uma função (ex.: list = [...] e depois list(...)).",
                     "Troque o nome da variável ou tire os parênteses.", "funcao")
        if m := re.search(r"'(\w+)' object is not subscriptable", msg):
            return e(f"usou [ ] num {m.group(1)}", f"Colchetes servem para listas, textos e dicionários; {m.group(1)} "
                     "não tem posições.", "Confira o valor da variável (um print antes ajuda).", "lista")
        if m := re.search(r"'(\w+)' object is not iterable", msg):
            return e(f"tentou percorrer um {m.group(1)}", f"O for precisa de uma sequência (lista, texto, range); "
                     f"{m.group(1)} não é.", "Para repetir N vezes use for i in range(N).", "for")
        if "object does not support item assignment" in msg:
            return e("tentou alterar um texto ou tupla", "Textos (str) e tuplas não mudam depois de criados.",
                     "Crie um novo valor (texto = texto.replace(...)) ou use uma lista.", "lista")
    if tipo == "ValueError":
        if m := re.search(r"invalid literal for int\(\) with base 10: '(.*)'", msg):
            valor = m.group(1)
            return e(f"'{valor}' não é um número inteiro", "int() só converte texto com dígitos" +
                     (" (texto vazio: a pessoa só apertou Enter)" if not valor else
                      " (para números com vírgula use float, e ponto no lugar da vírgula)" if re.match(r"^\d+[.,]\d+$", valor)
                      else "") + ".", "Valide a entrada: use try/except ValueError e peça de novo.", "excecao")
        if "could not convert string to float" in msg:
            return e("o texto não é um número", "float() só converte números escritos com ponto: 3.5, não 3,5.",
                     "Troque a vírgula: float(texto.replace(\",\", \".\")) e trate o erro com try/except.", "conversao")
        if m := re.search(r"too many values to unpack|not enough values to unpack", msg):
            return e("quantidade de variáveis diferente da de valores", "Na atribuição a, b = valores, o número de "
                     "variáveis à esquerda precisa ser igual ao de valores.", "Confira quantos itens a sequência tem.",
                     "lista")
    if tipo == "ZeroDivisionError":
        return e("divisão por zero", "O divisor valeu 0, e divisão por zero não existe.",
                 "Teste antes: if divisor != 0: ... (ou trate com try/except ZeroDivisionError).", "if")
    if tipo == "IndexError":
        return e("posição que não existe", "A lista (ou texto) tem menos itens do que a posição pedida. As posições "
                 "começam em 0: numa lista com 3 itens, vão de 0 a 2.",
                 "Use len(lista) para saber o tamanho, ou percorra com for item in lista.", "lista")
    if tipo == "KeyError":
        chave = msg.strip() or "a chave"
        return e(f"chave {chave} não existe no dicionário", "O dicionário não tem essa chave (atenção a maiúsculas e "
                 "espaços).", f"Use dicionario.get({chave}) para receber None em vez de erro, ou teste com "
                 f"if {chave} in dicionario.", "dicionario")
    if tipo == "AttributeError":
        if m := re.search(r"'NoneType' object has no attribute '(\w+)'", msg):
            return e(f"None não tem .{m.group(1)}", "A variável vale None: em geral uma função que não devolveu nada "
                     "(faltou o return) ou um método como .sort() que altera a lista e devolve None.",
                     "Confira de onde veio o valor (um print antes ajuda).", "funcao")
        if m := re.search(r"'(\w+)' object has no attribute '(\w+)'", msg):
            classe, attr = m.groups()
            if classe[:1].isupper() and classe not in ("NoneType",):
                return e(f"o objeto {classe} não tem {attr}", f"O atributo {attr} não foi criado no objeto. Atributos "
                         f"nascem no __init__ com self.{attr} = ...", f"Crie self.{attr} no __init__ de {classe} (ou "
                         "confira o nome).", "atributo")
            return e(f"{classe} não tem {attr}", f"O tipo {classe} não tem o método/atributo {attr}.",
                     f"Confira o nome (dir({classe}) lista o que existe).", None)
        if m := re.search(r"module '(\w+)' has no attribute '(\w+)'", msg):
            return e(f"o módulo {m.group(1)} não tem {m.group(2)}", "Ou o nome está errado, ou um arquivo seu tem o "
                     f"mesmo nome do módulo ({m.group(1)}.py) e está sendo importado no lugar dele.",
                     f"Confira o nome e renomeie arquivos chamados {m.group(1)}.py no projeto.", "import")
    if tipo in ("ModuleNotFoundError", "ImportError") and (m := re.search(r"No module named '([\w.]+)'", msg)):
        modulo = m.group(1)
        raiz_mod = modulo.split(".")[0]
        pacote = PACOTES_PIP.get(modulo) or PACOTES_PIP.get(raiz_mod) or raiz_mod
        extra = " (a versão headless, sem janelas, serve para servidores)" if raiz_mod == "cv2" else ""
        return e(f"o módulo {modulo} não está instalado", f"O import procurou {modulo} e não achou neste Python.",
                 f"Instale o pacote {pacote}{extra}: python3 -m pip install {pacote} (num ambiente do projeto: "
                 f"python3 -m venv .venv e depois .venv/bin/pip install {pacote}). Se {raiz_mod} for um arquivo seu, "
                 "confira o nome e a pasta.", "import")
    if tipo == "ImportError" and (m := re.search(r"cannot import name '(\w+)' from '([\w.]+)'", msg)):
        return e(f"{m.group(2)} não tem {m.group(1)}", "O nome importado não existe nesse módulo (ou há importação "
                 "circular: dois arquivos importando um ao outro).", "Confira o nome e de qual arquivo ele vem.", "import")
    if tipo in ("IndentationError", "TabError"):
        if "expected an indented block" in msg:
            return e("faltou indentar o bloco", "Depois de uma linha terminada em : (if, for, def, class) as linhas de "
                     "dentro precisam de 4 espaços a mais.", "Indente o corpo (Tab no Studio) ou, se ainda não há "
                     "nada, escreva pass.", "indentacao")
        if "unexpected indent" in msg:
            return e("indentação sobrando", "Esta linha tem espaços a mais no começo, sem um bloco (if, for, def) "
                     "que peça isso.", "Alinhe a linha com a de cima (Shift+Tab no Studio).", "indentacao")
        return e("indentação misturada", "Os espaços do começo desta linha não batem com nenhum nível acima (ou há "
                 "tabs misturados com espaços).", "Use sempre 4 espaços por nível; os pontinhos do editor mostram a "
                 "indentação.", "indentacao")
    if tipo == "SyntaxError":
        if "expected ':'" in msg:
            return e("faltou os dois-pontos", "Linhas de if, elif, else, for, while, def e class terminam com :.",
                     "Acrescente : no fim da linha.", "if")
        if "was never closed" in msg or "unexpected EOF" in msg:
            return e("parêntese, colchete ou aspas sem fechar", "Algo foi aberto e não fechado: ( [ { ou aspas.",
                     "Feche o par na própria linha (o editor do Studio fecha sozinho quando você abre).", None)
        if "unterminated string" in msg:
            return e("texto sem as aspas de fechamento", "Uma string começou com aspas e a linha acabou antes de "
                     "fechar.", "Feche as aspas do mesmo tipo que abriu.", "texto")
        if m := re.search(r"invalid character '(.)'", msg):
            return e(f"caractere inválido {m.group(1)}", "Aspas curvas ou símbolos copiados de sites e documentos não "
                     "são código.", "Troque por aspas retas \" ou ' (digite pelo teclado).", "texto")
        if "invalid syntax. Perhaps you forgot a comma" in msg:
            return e("faltou uma vírgula", "Dois valores lado a lado sem vírgula entre eles.",
                     "Separe os itens com vírgula.", "lista")
        if "'return' outside function" in msg:
            return e("return fora de função", "return só existe dentro de def.", "Coloque o código numa função ou "
                     "troque return por print.", "funcao")
        if "cannot assign to" in msg or "Maybe you meant '==' instead of '='" in msg:
            return e("= no lugar de ==", "= guarda um valor; para comparar use ==.", "Em if e while, use ==.", "if")
        return e("sintaxe inválida", "O Python não entendeu esta linha" + (f" ({msg})" if msg else "") + ".",
                 "Confira parênteses, dois-pontos, vírgulas e aspas perto do ^ que o Python marca.", None)
    if tipo == "FileNotFoundError" and (m := re.search(r"No such file or directory: '(.+)'", msg)):
        return e(f"o arquivo {m.group(1)} não existe", "O caminho é procurado a partir da pasta onde o programa roda "
                 "(no Studio, a raiz do projeto), não da pasta do .py.", "Confira o nome e use um caminho a partir "
                 "do arquivo: Path(__file__).parent / \"dados.csv\".", "arquivo")
    if tipo == "PermissionError":
        return e("sem permissão", "O sistema não deixou ler ou escrever esse arquivo.",
                 "Use uma pasta sua (dentro do projeto) ou confira as permissões com ls -l.", "arquivo")
    if tipo == "RecursionError":
        return e("a função chamou a si mesma sem parar", "Recursão sem caso de parada (ou com muitos níveis).",
                 "Garanta um if que devolve sem chamar de novo (o caso base).", "funcao")
    if tipo == "KeyboardInterrupt":
        return e("interrompido com Ctrl+C", "Você parou o programa pelo teclado.", "Nada a corrigir.", None)
    if tipo == "EOFError":
        return e("o programa pediu entrada e ela acabou", "O input() esperava uma linha e a entrada terminou.",
                 "Rode no terminal do Studio (F5) e responda; se a entrada vem de um arquivo, confira se tem linhas "
                 "suficientes.", "input")
    if tipo in ("JSONDecodeError",):
        return e("JSON inválido", "O texto não é JSON válido (aspas simples, vírgula sobrando ou vazio).",
                 "JSON usa aspas duplas e não aceita vírgula depois do último item.", None)
    if tipo == "AssertionError":
        return e("uma verificação (assert) falhou", "A condição do assert deu falso.",
                 "Veja os valores envolvidos (print) e corrija o código ou o teste.", None)
    if tipo == "StopIteration":
        return e("next() sem próximo item", "O iterador acabou.", "Use for, ou next(it, None) com valor padrão.", "for")
    if tipo == "RuntimeError" and "dictionary changed size during iteration" in msg:
        return e("o dicionário mudou enquanto era percorrido", "Não dá para acrescentar ou remover chaves dentro do for "
                 "que percorre o próprio dicionário.", "Percorra uma cópia: for k in list(d):", "dicionario")
    if tipo == "OverflowError":
        return e("número grande demais", "O resultado passou do limite do tipo (float).",
                 "Use números menores, int (que não tem limite) ou o módulo decimal.", None)
    if tipo == "MemoryError":
        return e("faltou memória", "O programa tentou guardar dados demais.",
                 "Processe em partes (leia o arquivo linha a linha, use geradores).", None)
    return e(msg or tipo, f"O Python parou com {tipo}" + (f": {msg}" if msg else "") + ".",
             "Veja a linha indicada; um print das variáveis antes dela ajuda a entender.", None)


# ---------------------------------------------------------------------------------------------- JavaScript / Bun
def _javascript(linhas: list[str], raiz: Path | None) -> Explicacao | None:
    for i in range(len(linhas) - 1, -1, -1):
        texto = linhas[i].strip()
        if m := re.match(r'^error: Cannot find (?:package|module) "([^"]+)"(?: from "([^"]+)")?', texto):
            return _js_modulo(m.group(1), m.group(2), None, raiz)
        if m := re.match(r'^error: Script not found "([^"]+)"', texto):
            return Explicacao("bun", f"o script {m.group(1)} não existe", "bun run procura o nome em \"scripts\" do "
                              "package.json (ou um arquivo com esse nome).", f"Acrescente \"{m.group(1)}\": \"...\" em "
                              "scripts no package.json, ou rode o arquivo direto: bun arquivo.ts")
        if "EADDRINUSE" in texto and (m := re.search(r":(\d{2,5})\b", texto)):
            return Explicacao("EADDRINUSE", f"a porta {m.group(1)} já está em uso", "Outro programa (talvez o mesmo "
                              "servidor rodando em outro terminal) já ocupa essa porta.", f"Pare o outro (Ctrl+C no "
                              f"terminal dele) ou use outra porta; para ver quem usa: ss -ltnp | grep {m.group(1)}")
        m = _JS_ERRO.match(texto)
        if not m or texto.startswith(("at ", "File ")):
            continue
        tipo, codigo, msg = m.groups()
        arquivo = linha = None
        for ln in linhas[i + 1:i + 12] + linhas[max(0, i - 8):i]:
            f = _JS_FRAME.search(ln.strip())
            if f and "node:internal" not in ln and "node_modules" not in ln:
                arquivo, linha = f.group(1).removeprefix("file://"), int(f.group(2))
                break
        exp = _regra_js(tipo, codigo, msg, arquivo, raiz)
        if exp is None:
            return None
        exp.arquivo, exp.linha = arquivo, linha
        exp.trecho = _codigo(arquivo, linha, raiz)
        return exp
    return None


def _js_modulo(nome: str, de: str | None, codigo: str | None, raiz: Path | None) -> Explicacao:
    if nome.startswith((".", "/")):
        return Explicacao("módulo", f"o arquivo {nome} não foi encontrado", "O import aponta para um arquivo do projeto "
                          "que não existe nesse caminho.", "Confira o caminho relativo (./, ../) e a extensão (.js, .ts).",
                          conceito="import")
    pacote = nome.split("/")[0] if not nome.startswith("@") else "/".join(nome.split("/")[:2])
    pm = "bun add" if raiz and ((raiz / "bun.lock").exists() or (raiz / "bun.lockb").exists()) else "npm install"
    return Explicacao("módulo", f"o pacote {pacote} não está instalado", f"O import procurou {pacote} em node_modules e "
                      "não achou.", f"Instale: {pm} {pacote} (se ele já está no package.json, rode só "
                      f"{pm.split()[0]} install).", conceito="import")


def _regra_js(tipo: str, codigo: str | None, msg: str, arquivo, raiz) -> Explicacao | None:
    def e(titulo, oque, como, conceito=None):
        return Explicacao(tipo, titulo, oque, como, conceito=conceito)

    if tipo == "ReferenceError" and (m := re.search(r"(\w+) is not defined", msg)):
        nome = m.group(1)
        if nome in ("require", "module", "exports"):
            return e(f"{nome} não existe em módulos ES", "O arquivo é um módulo ES (import/export), onde require não "
                     "existe.", "Use import ... from '...' (ou renomeie para .cjs).", "import")
        parecidos = _parecidos(nome, arquivo, raiz)
        return e(f"{nome} não existe", f"{nome} foi usado sem ter sido declarado." +
                 (f" Você quis dizer {' ou '.join(parecidos)}?" if parecidos else ""),
                 f"Declare antes: const {nome} = ... (ou let, se o valor muda).", "variavel")
    if tipo == "ReferenceError" and "before initialization" in msg:
        return e("variável usada antes da declaração", "let/const só existem depois da linha em que são declaradas.",
                 "Mova a declaração para antes do uso.", "variavel")
    if tipo == "TypeError":
        if m := re.search(r"Cannot read propert(?:y|ies) of (undefined|null)(?: \(reading '(\w+)'\))?", msg):
            valor, prop = m.groups()
            return e(f"leu .{prop or 'algo'} de {valor}", f"O objeto antes do .{prop or ''} vale {valor}: um dado que "
                     "ainda não chegou (fetch), um item que não existe na lista ou um nome de propriedade errado.",
                     f"Confira o valor antes (console.log) ou use encadeamento opcional: obj?.{prop or 'x'}.", "objeto")
        if m := re.search(r"([\w.$]+) is not a function", msg):
            return e(f"{m.group(1)} não é uma função", "Chamou com () algo que não é função: nome errado, import "
                     "errado (default x nomeado) ou um valor sobrescrito.", "Confira o nome e como foi importado.",
                     "funcao")
        if "Assignment to constant variable" in msg:
            return e("tentou mudar uma const", "const não aceita receber outro valor.", "Use let se o valor muda.",
                     "variavel")
    if tipo == "SyntaxError":
        if "Cannot use import statement outside a module" in msg:
            return e("import num arquivo que não é módulo", "O Node trata .js como CommonJS por padrão.",
                     "Acrescente \"type\": \"module\" no package.json (ou renomeie para .mjs), ou rode com bun.",
                     "import")
        if "Unexpected token" in msg or "Unexpected end of input" in msg or "missing ) after" in msg:
            return e("sintaxe inválida", f"O JavaScript não entendeu o código ({msg}).", "Confira parênteses, "
                     "chaves e vírgulas perto da linha indicada. JSX (<div>) precisa de .jsx/.tsx e do bun ou Vite.",
                     None)
    if tipo == "Error" and (m := re.search(r"Cannot find (?:module|package) '([^']+)'", msg)):
        return _js_modulo(m.group(1), None, codigo, raiz)
    if tipo == "RangeError" and "Maximum call stack" in msg:
        return e("a função chamou a si mesma sem parar", "Recursão sem caso de parada.",
                 "Garanta um if que retorna sem chamar de novo.", "funcao")
    return e(msg[:80] or tipo, f"O programa parou com {tipo}: {msg}", "Veja a linha indicada e os valores usados nela.")


# ---------------------------------------------------------------------------------------- Go, Rust, Java, C, TSC
def _compiladores(linhas: list[str], raiz: Path | None) -> Explicacao | None:
    for i, ln in enumerate(linhas):
        texto = ln.strip()
        if m := _GO.match(texto):
            return _regra_compilador(".go", None, m.group(4), m.group(1), int(m.group(2)), raiz)
        if m := _GCC.match(texto):
            return _regra_compilador(Path(m.group(1)).suffix, None, m.group(3), m.group(1), int(m.group(2)), raiz)
        if m := _TSC.match(texto):
            linha = int(m.group(2) or m.group(3))
            return _regra_compilador(Path(m.group(1)).suffix, m.group(4), m.group(5), m.group(1), linha, raiz)
        if m := re.match(r"^error(?:\[(E\d+)\])?: (.+)$", texto):  # rustc: o local vem na linha seguinte (-->)
            for seguinte in linhas[i + 1:i + 4]:
                if loc := _RUST_LOCAL.match(seguinte):
                    return _regra_compilador(".rs", m.group(1), m.group(2), loc.group(1), int(loc.group(2)), raiz)
        if m := re.match(r'^Exception in thread "main" ([\w.$]+)(?::\s*(.*))?$', texto):
            classe = m.group(1).split(".")[-1]
            local = next(((f.group(1), int(f.group(2))) for f in (re.search(r"\((\w+\.java):(\d+)\)", x)
                                                                  for x in linhas[i + 1:i + 8]) if f), (None, None))
            exp = _regra_java_runtime(classe, m.group(2) or "")
            exp.arquivo, exp.linha = local
            exp.trecho = _codigo(local[0], local[1], raiz)
            return exp
    if any("Segmentation fault" in ln for ln in linhas):
        return Explicacao("Segmentation fault", "acesso inválido à memória", "O programa leu ou escreveu numa posição de "
                          "memória que não é dele (ponteiro nulo, vetor fora do limite).", "Compile com -g -fsanitize="
                          "address e rode de novo: o relatório mostra a linha exata.", conceito=None)
    return None


def _regra_compilador(ext: str, codigo: str | None, msg: str, arquivo: str, linha: int, raiz) -> Explicacao:
    tipo = {".go": "Go", ".rs": "Rust", ".java": "Java", ".kt": "Kotlin", ".cs": "C#", ".ts": "TypeScript",
            ".tsx": "TypeScript"}.get(ext, "C/C++")

    def e(titulo, oque, como, conceito=None):
        return Explicacao(f"{tipo}", titulo, oque, como, arquivo, linha, _codigo(arquivo, linha, raiz), conceito)

    if m := re.search(r"undefined: (\w+)|cannot find (?:value|symbol)\W+(\w+)|'(\w+)' undeclared|use of undeclared "
                      r"identifier '(\w+)'|Cannot find name '(\w+)'|unresolved reference '?(\w+)'?", msg):
        nome = next(g for g in m.groups() if g)
        return e(f"{nome} não foi declarado", f"O código usa {nome}, que não existe neste ponto (nome errado ou "
                 "declarado depois/em outro escopo).", "Declare antes de usar ou corrija o nome.", "variavel")
    if "cannot find symbol" in msg:
        return e("símbolo não encontrado", "Um nome (variável, método ou classe) não existe ou faltou o import.",
                 "Confira o nome e os imports.", "variavel")
    if m := re.search(r'declared and not used: (\w+)|"([\w/]+)" imported and not used', msg):
        nome = next(g for g in m.groups() if g)
        return e(f"{nome} sobrando", "O Go não compila com variável ou import sem uso.",
                 f"Use {nome} ou apague a linha.", "variavel")
    if "expected ';'" in msg or "';' expected" in msg or "expected ';' before" in msg:
        return e("faltou ponto e vírgula", "Comandos terminam com ; nesta linguagem.",
                 "Coloque ; no fim da linha anterior.", None)
    if "mismatched types" in msg or "incompatible types" in msg or "cannot use" in msg:
        return e("tipos diferentes", f"O valor não tem o tipo esperado ({msg}).",
                 "Converta o valor ou ajuste o tipo da variável.", "conversao")
    if codigo == "E0382" or "borrow of moved value" in msg:
        return e("valor usado depois de ser movido", "Em Rust, passar um valor (como String) para outra variável ou "
                 "função transfere o dono; o original não pode mais ser usado.", "Passe uma referência (&valor) ou "
                 "use .clone().", None)
    if "implicit declaration of function" in msg:
        nome = (re.search(r"'(\w+)'", msg) or re.search(r"(\w+)", msg)).group(1)
        cabecalho = {"printf": "stdio.h", "scanf": "stdio.h", "malloc": "stdlib.h", "free": "stdlib.h",
                     "strlen": "string.h", "strcpy": "string.h", "sqrt": "math.h"}.get(nome, "o cabeçalho certo")
        return e(f"{nome} sem #include", f"A função {nome} é usada sem a declaração dela.",
                 f"Acrescente #include <{cabecalho}> no topo.", "import")
    if "should be declared in a file named" in msg:
        return e("nome do arquivo diferente da classe", "Em Java a classe pública precisa estar num arquivo com o "
                 "mesmo nome.", "Renomeie o arquivo (ou a classe) para ficarem iguais.", "classe")
    return e(msg[:90], f"O compilador recusou esta linha: {msg}", "Corrija a linha indicada e compile de novo.")


def _regra_java_runtime(classe: str, msg: str) -> Explicacao:
    regras = {"NullPointerException": ("valor null usado", "Um objeto vale null e foi usado (método ou atributo).",
                                       "Inicialize o objeto antes (new ...) ou teste se não é null.", "objeto"),
              "ArrayIndexOutOfBoundsException": ("posição fora do vetor", "O índice passou do tamanho do array (que vai "
                                                 "de 0 a length-1).", "Use i < array.length no laço.", "lista"),
              "NumberFormatException": ("texto que não é número", "Integer.parseInt recebeu texto sem dígitos.",
                                        "Valide a entrada com try/catch.", "conversao"),
              "ArithmeticException": ("divisão por zero", "Divisão inteira por zero.", "Teste o divisor antes.", "if")}
    titulo, oque, como, conceito = regras.get(classe, (msg or classe, f"O programa parou com {classe}.",
                                                        "Veja a linha indicada no rastro da pilha.", None))
    return Explicacao(classe, titulo, oque, como, conceito=conceito)


# ---------------------------------------------------------------------------------- R, Julia, Dart, Kotlin, Swift
_OUTRAS = [  # (regex na linha, linguagem, função que monta a explicação a partir do nome)
    (re.compile(r"object '(\w+)' not found|objeto '(\w+)' não encontrado"), "R",
     lambda n: (f"{n} não existe", f"O R não achou {n}: não foi criado antes (com <-) ou o nome está diferente.",
                f"Crie antes: {n} <- valor (e confira maiúsculas).", "variavel")),
    (re.compile(r"could not find function \"(\w+)\""), "R",
     lambda n: (f"a função {n} não existe", "Ou o nome está errado, ou a função é de um pacote que não foi carregado.",
                f"Carregue o pacote com library(...) (instale com install.packages(\"...\")) ou confira o nome.",
                "import")),
    (re.compile(r"UndefVarError: `?(\w+)`? not defined"), "Julia",
     lambda n: (f"{n} não existe", f"{n} foi usado sem ter sido criado; dentro de um laço no topo do arquivo, uma "
                "variável de fora só pode ser alterada com global.", f"Crie {n} antes, ou escreva global {n} no "
                "começo do laço.", "variavel")),
    (re.compile(r"Error: Undefined name '(\w+)'"), "Dart",
     lambda n: (f"{n} não existe", f"{n} foi usado sem ter sido declarado.", f"Declare antes: final {n} = ...;",
                "variavel")),
    (re.compile(r"[Uu]nresolved reference:? '?(\w+)'?"), "Kotlin",
     lambda n: (f"{n} não existe", f"O Kotlin não achou {n}: nome errado, declarado depois ou falta o import.",
                f"Declare antes (val {n} = ...) ou importe.", "variavel")),
    (re.compile(r"error: cannot find '(\w+)' in scope"), "Swift",
     lambda n: (f"{n} não existe", f"O Swift não achou {n} neste ponto do código.", f"Declare antes: let {n} = ...",
                "variavel")),
]


def _outras(linhas: list[str], raiz: Path | None) -> Explicacao | None:
    for ln in reversed(linhas):
        for padrao, lang, montar in _OUTRAS:
            if m := padrao.search(ln):
                nome = next(g for g in m.groups() if g)
                titulo, oque, como, conceito = montar(nome)
                local = re.search(r"([\w./-]+\.(?:R|r|jl|dart|kt|kts|swift)):(\d+)", "\n".join(linhas))
                arquivo, linha = (local.group(1), int(local.group(2))) if local else (None, None)
                return Explicacao(lang, titulo, oque, como, arquivo, linha, _codigo(arquivo, linha, raiz), conceito)
    return None


# ---------------------------------------------------------------------------------------------------------- shell
def _shell(linhas: list[str], raiz: Path | None) -> Explicacao | None:
    for ln in reversed(linhas):
        texto = ln.strip()
        for padrao in _SH_NAO_ACHOU:
            if m := padrao.match(texto):
                prog = m.group(1)
                como = _INSTALAR.get(prog, f"confira o nome; se for um programa, instale-o (ex.: sudo zypper install "
                                           f"{prog} ou sudo apt install {prog})")
                if prog.startswith(("./", "/")):
                    como = "confira o caminho do arquivo (ls mostra o que existe na pasta)"
                return Explicacao("comando não encontrado", f"{prog} não existe neste sistema",
                                  f"O terminal não achou um programa chamado {prog} no PATH.",
                                  como[0].upper() + como[1:] + ".")
        if m := re.match(r"^(?:\S+: )?(?:line \d+: )?(\./\S+|\S+\.sh): Permission denied$", texto):
            return Explicacao("permissão", f"{m.group(1)} não pode ser executado", "O arquivo não tem permissão de "
                              "execução.", f"Rode chmod +x {m.group(1)} (ou bash {m.group(1)}).")
    return None
