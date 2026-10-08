"""Normalização de texto PT/EN e léxico de conceitos usado pelo roteador.

Cada palavra da intenção vira um conjunto de *conceitos* canônicos (em inglês):
"conectar", "conexão" e "connection" -> {"connect"}. Isso torna o banco de padrões
bilíngue sem embeddings e com custo O(1) por palavra.
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

_WORD = re.compile(r"[a-z0-9_#+]+")


def _build_table() -> dict[int, str]:
    table: dict[int, str] = {}
    for cp in range(0x00C0, 0x0250):
        ch = chr(cp)
        base = "".join(c for c in unicodedata.normalize("NFKD", ch) if not unicodedata.combining(c)).lower()
        if len(base) == 1 and base != ch:
            table[cp] = base
    table[0x0130] = "i"  # İ -> i (lower() viraria 2 caracteres)
    return table


_FOLD = _build_table()


def fold(text: str) -> str:
    """Minúsculas e sem acentos (tabela para latim, NFKD como fallback)."""
    out = text.translate(_FOLD).lower()
    if out.isascii():
        return out
    norm = unicodedata.normalize("NFKD", out)
    return "".join(c for c in norm if not unicodedata.combining(c))


def fold_keep_len(text: str) -> str:
    """Como fold(), mas preserva o comprimento (índices batem com o texto original)."""
    out = text.translate(_FOLD)
    if len(out.lower()) == len(out):
        return out.lower()
    return "".join(c.lower() if len(c.lower()) == 1 else c for c in out)


def words(text: str) -> list[str]:
    return [w.strip("_") for w in _WORD.findall(fold(text)) if w.strip("_")]


STOPWORDS = frozenset("""
a o as os um uma uns umas de da do das dos em na no nas nos num numa para pra pro por pelo pela pelos pelas
com sem e ou que se ao aos meu minha meus minhas seu sua seus suas isso isto esse essa este esta aquele aquela
como qual quais quando onde mais muito muita ja tambem so apenas entre sobre todo toda todos todas cada
outro outra eu voce ele ela eles elas ser sera estar esta ter tem tenha quero queria preciso precisa
gostaria favor porfavor algum alguma alguns algumas aqui ali la lo le the an of to in on for with and or
that this these those is are be been it its by from at as into using via please i me my you your we our
do does did can could would should will shall ai just also then than so very some any all each every
nele nela dele dela deles delas seja sejam vai vamos dado dada
""".split())

# Palavras que descrevem o pedido, não o conteúdo: contam pouco na cobertura.
META_WEIGHT = {w: 0.25 for w in """
crie criar cria faca fazer faz gere gerar gera implemente implementar implementa escreva escrever monte montar
desenvolva desenvolver construa construir create make build generate implement write develop
funcao funcoes function functions metodo method codigo code script programa program snippet exemplo example
simples simple basico basica basic rapido rapida quick novo nova new usando utilizando using use usar
algoritmo algoritmos algorithm algorithms implementacao implementation rotina routine trecho exemplo
""".split()}

LANG_WORDS = frozenset("""
python py python3 javascript js node nodejs typescript ts golang go rust rs java c cpp c++ csharp c# cs
bash sh shell zsh powershell pwsh ps1 lua ruby rb php sql kotlin swift
""".split())

# conceito: variantes (já sem acento). Uma variante pode pertencer a mais de um conceito.
_LEXICON_SRC = """
connect: conectar conecta conecte conectando conexao conexoes connect connection connections conn ligar
read: ler leia le lendo leitura read reading load carregar carrega carregue abrir abra open
write: escrever escreva escreve escrita gravar grave salvar salve save write writing persistir dump
append: anexar append acrescentar adicionar_no_final
file: arquivo arquivos ficheiro file files
dir: pasta pastas diretorio diretorios directory directories folder folders dir dirs
list: lista listas array arrays vetor vetores list lists listar liste listagem enumerar
sort: ordenar ordene ordena ordenacao ordenado ordenada sort sorted sorting classificar
search: buscar busca busque procurar procure pesquisar pesquisa search find lookup encontrar encontre localizar achar
binary: binaria binario binary
linear: linear sequencial sequential
delete: deletar delete apagar apague remover remova remove excluir exclua eliminar del rm
create: criar crie cria create gerar novo nova
update: atualizar atualize atualiza update modificar alterar editar edit upsert
request: requisicao requisicoes request requests chamada chamadas
http: http https web rest api apis endpoint endpoints
get: get obter obtenha pegar recuperar fetch
post: post postar submeter
send: enviar envie envia send sending mandar
server: servidor servidores server servers servir serve listen escutar
client: cliente clientes client clients
database: banco bancos bd db database databases sgbd
data: dados data dataset
date: data datas date dates dia dias day days calendario calendar
now: agora atual atuais now current hoje today
time: tempo hora horas time timer horario timestamp
measure: medir meca medicao measure benchmark cronometrar cronometro elapsed
json: json
csv: csv tsv
xml: xml
yaml: yaml yml
toml: toml
ini: ini
env: ambiente env environment dotenv
var: variavel variaveis variable variables var
hash: hash hashes hashear sha sha256 sha1 md5 digest checksum
password: senha senhas password passwords pwd passwd
encrypt: criptografar criptografia cifrar encriptar encrypt encryption crypto aes cifra cripto
decrypt: descriptografar decifrar decrypt decryption
sign: assinar assinatura sign signature hmac
random: aleatorio aleatoria aleatorios aleatorias random rand randomico sortear sorteio shuffle embaralhar
number: numero numeros number numbers numerico numeric
digit: digito digitos digit digits algarismo algarismos
int: inteiro inteiros int integer integers
float: float decimal decimais flutuante double
string: string strings texto textos text str cadeia
reverse: inverter inverta inverte inverso invertida invertido reverse reversed reverter
count: contar conte conta contagem count counter contador contabilizar quantidade
sum: soma somar some sum total totalizar
average: media mean average
max: maximo maxima max maximum
min: minimo minima min minimum
prime: primo primos prime primes primalidade
fibonacci: fibonacci fib
factorial: fatorial factorial
palindrome: palindromo palindromos palindroma palindrome
anagram: anagrama anagramas anagram anagrams
stack: pilha pilhas stack lifo
queue: fila filas queue queues fifo deque
tree: arvore arvores tree trees bst
graph: grafo grafos graph graphs
linked: ligada ligadas encadeada encadeadas linked
node: vertice vertices node nodes nodo nodos
path: caminho caminhos path paths
shortest: curto curta shortest menor_caminho
bfs: bfs largura breadth
dfs: dfs profundidade depth
dijkstra: dijkstra
cache: cache caching memoizar memoize memoization memo
lru: lru
thread: thread threads threading paralelo paralela paralelos paralelismo parallel concorrente concorrentes concorrencia concurrency concurrent worker workers pool goroutine goroutines
async: async assincrono assincrona assincronos asynchronous await promise promises
sleep: esperar espere dormir sleep wait aguardar delay pausar pausa
log: log logs logging registrar logger
test: teste testes testar test tests testing unitario unitarios unit pytest jest junit pester
mock: mock mocks simular stub stubs
regex: regex regexp regular regulares
expression: expressao expressoes expression expressions formula formulas
calculator: calculadora calculadoras calculator calc
compute: calcular calcule calcula calculando calculo calculos compute computar
math: matematica matematicas matematico math mathematical aritmetica aritmeticas arithmetic
email: email emails e-mail
validate: validar valide valida validacao validate validation verificar verifique verifica check checar
parse: parse parsear analisar parsing interpretar parser
convert: converter converta converte conversao convert conversion transformar transform
format: formatar formate formata formatacao format formatting
upper: maiuscula maiusculas maiusculo upper uppercase capitalize capitalizar
lower: minuscula minusculas minusculo lower lowercase
split: dividir divida split separar quebrar
join: juntar junte join unir concatenar concatenate concat
replace: substituir substitua substitui replace trocar troque
trim: trim aparar strip
download: baixar baixe baixa download downloads
upload: upload subir
compress: zip compactar compacte compactacao compress comprimir zipar gzip tar archive arquivar
extract: descompactar descompacte unzip extrair extraia extract
copy: copiar copie copy cp duplicar
move: mover mova move mv renomear renomeie rename
exists: existe existir exists exist
size: tamanho tamanhos size sizes
large: grande grandes large big enorme enormes pesado pesados
process: processo processos process processes pid
kill: matar mate kill encerrar encerre finalizar terminate
port: porta portas port ports
memory: memoria memory ram
disk: disco discos disk storage armazenamento espaco
cpu: cpu processador
user: usuario usuarios user users
auth: autenticacao autenticar login auth authentication logar autorizar authorization
jwt: jwt
token: token tokens
uuid: uuid guid
url: url urls link links uri
cli: cli terminal argparse
command: comando comandos command commands cmd
arg: argumento argumentos argument arguments args parametro parametros parameter parameters flag flags opcoes options
config: configuracao configuracoes config configuration settings
confirm: confirmar confirme confirma confirmacao confirmacoes confirm confirmation
retry: retry retentativa retentativas backoff tentativa tentativas
rate: rate limite limitador limiter throttle throttling
debounce: debounce
singleton: singleton
factory: factory fabrica
builder: builder construtor
strategy: strategy estrategia
observer: observer observador
event: evento eventos event events emitter listener
socket: socket sockets websocket websockets tcp udp
smtp: smtp
docker: docker container containers dockerfile
git: git commit commits branch branches
service: servico servicos service services daemon systemd
schedule: agendar agendamento agendada agendado schedule scheduled cron crontab
backup: backup backups
excel: excel xlsx planilha planilhas spreadsheet
pdf: pdf
image: imagem imagens image images foto fotos
matrix: matriz matrizes matrix
dict: dicionario dicionarios dict dictionary hashmap mapa mapas map
set: conjunto conjuntos set sets
class: classe classes class
loop: loop loops laco lacos repeticao iterar iteracao iterate
duplicate: duplicado duplicados duplicadas duplicate duplicates repetido repetidos dedupe unicos unicas unique distinct
group: agrupar agrupe agrupamento group groupby
filter: filtrar filtre filtra filter filtro
merge: mesclar mescle merge combinar
flatten: achatar flatten aplanar
chunk: pedaco pedacos chunk chunks lote lotes batch batches
frequency: frequencia frequencias frequency ocorrencias occurrences
word: palavra palavras word words
line: linha linhas line lines
char: caractere caracteres char chars character characters letra letras
cpf: cpf
cnpj: cnpj
cep: cep viacep
currency: moeda moedas dinheiro currency money reais brl
input: entrada input teclado stdin
output: saida output stdout
print: imprimir imprima print printar mostrar mostre exibir exiba
table: tabela tabelas table tables
query: consulta consultas consultar query queries select
insert: inserir insira insert
transaction: transacao transacoes transaction transactions
pagination: paginacao paginar paginada pagination paginate
index: indice indices index indexes
migration: migracao migracoes migration migrations
redis: redis
postgres: postgres postgresql pg psql psycopg
mysql: mysql mariadb
sqlite: sqlite sqlite3
mongo: mongo mongodb
kafka: kafka
rabbitmq: rabbitmq amqp
orm: orm sqlalchemy prisma gorm
react: react jsx usestate useeffect componente componentes component components
hook: hook hooks
dom: dom
storage: localstorage sessionstorage storage
form: formulario formularios form forms
express: express
fastapi: fastapi
flask: flask
pandas: pandas dataframe dataframes
numpy: numpy
plot: grafico graficos plot plotar chart charts matplotlib
regression: regressao regression
kmeans: kmeans clustering clusterizar
train: treinar treino train training
signal: sinal sinais signal signals sigint sigterm
shutdown: desligamento desligar shutdown graceful
lock: lock locks mutex trava travar semaforo semaphore
channel: canal canais channel channels
producer: produtor produtores producer producers consumidor consumidores consumer consumers
timeout: timeout timeouts expirar expiracao ttl prazo
scrape: scraping raspar scrape scraper crawler
html: html
markdown: markdown
base64: base64
encode: codificar codifique encode encoding
decode: decodificar decodifique decode decoding
unicode: utf8 unicode acentos acento
slug: slug slugify
diff: diferenca diferencas diff difference
age: idade age
window: janela janelas window sliding deslizante
permutation: permutacao permutacoes permutation permutations
combination: combinacao combinacoes combination combinations
subset: subconjunto subconjuntos subset subsets powerset
backtracking: backtracking
knapsack: mochila knapsack
lcs: lcs subsequencia subsequence
levenshtein: levenshtein edicao edit
distance: distancia distance
coin: coin coins troco
heap: heap heaps prioridade priority heapq
unionfind: union find dsu disjoint
topological: topologica topologico topological topo
mst: mst geradora spanning kruskal prim
trie: trie prefixo prefixos prefix
gcd: mdc gcd divisor
lcm: mmc lcm multiplo
power: potencia power pow exponenciacao exponentiation
sieve: crivo sieve eratostenes eratosthenes
bit: bit bits bitwise
quicksort: quicksort quick
mergesort: mergesort
bubble: bubble bolha
insertion: insertion insercao
selection: selection selecao
counting: counting
heapsort: heapsort
two: two
target: alvo target objetivo
even: par impar even odd parity paridade
pair: par pares pair pairs
interval: intervalo intervalos interval intervals
prefixsum: prefixsum acumulada acumulado cumulative
matrixmul: multiplicacao multiplicar multiply multiplication
transpose: transpor transposta transpose
rotate: rotacionar rotacione girar rotate rotation
fizzbuzz: fizzbuzz
temperature: temperatura celsius fahrenheit
bmi: imc bmi
vowel: vogal vogais vowel vowels
watch: monitorar observar watch watcher
notify: notificar notificacao notification notify
ping: ping
dns: dns
ip: ip ips
ssh: ssh scp
systemd: systemd unit
registry: registro registry regedit
eventlog: eventlog
admin: admin administrador elevado elevated sudo root
module: modulo modulos module modules
manifest: manifest manifesto psd1
pipeline: pipeline pipe
parallel: parallel
credential: credencial credenciais credential credentials
remote: remoto remota remote
csharp_record: record
dataclass: dataclass
interface: interface interfaces trait traits protocolo protocol
enum: enum enumeracao enumeration
generic: generico generics generic
iterator: iterador iterator generator gerador yield
decorator: decorador decorator decorators
contextmanager: contexto context
middleware: middleware middlewares
cors: cors
crud: crud
repository: repository repositorio
dependency: dependencia dependencias dependency injection injecao di
state: estado estados state machine maquina
result: result either
option: option optional opcional
benchmark: benchmark desempenho performance profiling perfil
health: health healthcheck saude
grpc: grpc protobuf
graphql: graphql
s3: s3 bucket buckets
aws: aws amazon
pubsub: pubsub publish subscribe publicar assinar
gitignore: gitignore
editorconfig: editorconfig
dockerignore: dockerignore
dockerfile: dockerfile
compose: compose docker-compose
ci: ci cd pipeline pipelines integracao continua workflow workflows
actions: actions action
ruff: ruff
eslint: eslint
tsconfig: tsconfig
psscriptanalyzer: psscriptanalyzer analyzer
pester: pester
pytest: pytest
vitest: vitest
toolchain: toolchain rustup
golangci: golangci
shellcheck: shellcheck
precommit: precommit pre-commit
readme: readme
license: licenca license licenses mit apache gpl
multiplication: tabuada multiplicacao
"""

SPECIFIC = frozenset("""
redis postgres mysql sqlite mongo kafka rabbitmq docker git react express fastapi flask pandas numpy jwt
cpf cnpj cep json csv xml yaml toml excel pdf html markdown base64 smtp s3 aws graphql grpc kmeans
dijkstra fibonacci factorial palindrome anagram quicksort mergesort bubble insertion selection heapsort
knapsack lcs levenshtein trie lru bfs dfs topological mst sieve gcd lcm fizzbuzz uuid regex email
binary linear prime singleton factory builder observer strategy debounce systemd ssh dns registry eventlog
""".split())


def _parse_lexicon() -> dict[str, frozenset[str]]:
    table: dict[str, set[str]] = {}
    for raw in _LEXICON_SRC.strip().splitlines():
        concept, _, variants = raw.partition(":")
        for v in variants.split():
            table.setdefault(v, set()).add(concept.strip())
    return {k: frozenset(v) for k, v in table.items()}


LEXICON = _parse_lexicon()
_STEMS: dict[str, frozenset[str]] = {}
for _v, _c in LEXICON.items():
    if len(_v) >= 5:
        _STEMS[_v[:5]] = _STEMS.get(_v[:5], frozenset()) | _c


def stem(word: str) -> str:
    return word[:5] if len(word) > 5 else word


@lru_cache(maxsize=4096)
def concepts(word: str) -> frozenset[str]:
    """Conceitos de uma palavra já normalizada (fold)."""
    if word in LEXICON:
        return LEXICON[word]
    if len(word) > 3 and word.endswith("s") and word[:-1] in LEXICON:
        return LEXICON[word[:-1]]
    if len(word) >= 5 and (c := _STEMS.get(word[:5])):
        return c
    return frozenset({"~" + stem(word)})


def analyze(text: str) -> list[tuple[str, frozenset[str], float]]:
    """[(palavra, conceitos, peso)] sem stopwords, nomes de linguagem e números puros."""
    out = []
    for w in words(text):
        if w in STOPWORDS or w in LANG_WORDS or w.isdigit() or len(w) < 2:
            continue
        out.append((w, concepts(w), META_WEIGHT.get(w, 1.0)))
    return out


def concept_set(text: str) -> set[str]:
    return {c for _, cs, _ in analyze(text) for c in cs}


# --------------------------------------------------------------------------- gatilho espaço + Enter
# Uma linha terminada em espaço + Enter só vira tradução se parecer frase. Mesma regra em clients/vscode
# (extension.ts), clients/nvim (init.lua) e clients/vim (autoload/codar.vim): mude as quatro juntas.
_CODE_END = ("{", "}", ";", ":", "(", ")", "[", "]", ",", "=", "\\", "+", "-", "*", "/", ">", "<")
_CODE_KEYWORDS = frozenset("""
return import from print const let var function def class if else elif for while in not and or pass break
continue echo local then do end fi done new public private static void int string fn func package use using
include require try catch except finally throw raise yield await async self this null none true false nil
match case switch default struct enum interface type val mut
""".split())
_WORD_TOKEN = re.compile(r"[^\W\d_]+", re.U)


def looks_like_intent(line: str) -> bool:
    """A linha é uma frase (pseudocódigo) e não código? Ex.: "x é igual a 10" sim, "for i in range(3):" não."""
    text = line.strip()
    for prefix in ("//", "#", "--", ";"):
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
            break
    if len(text) < 5 or text.endswith(_CODE_END) or text.count("(") != text.count(")"):
        return False
    tokens = text.split()
    words = [w for t in tokens if _WORD_TOKEN.fullmatch(w := t.strip("'\".,!?"))]
    if len(tokens) < 2 or len(words) * 2 < len(tokens):
        return False
    return any(len(w) >= 3 and w.lower() not in _CODE_KEYWORDS for w in words)

