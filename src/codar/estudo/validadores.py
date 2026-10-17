"""Correções offline com escopo explícito: estrutura HTML/CSS e consultas SQLite.

Estes critérios não substituem renderização, auditoria de acessibilidade nem testes
da aplicação. HTML/CSS são inspecionados sem executar scripts ou acessar a rede.
"""

from collections import Counter
from dataclasses import dataclass, field
from html.parser import HTMLParser
import re
import sqlite3
import time


def _case(name, ok, expected, actual='', error=''):
    return {'input': name, 'expected': expected, 'actual': actual or ('presente' if ok else 'ausente ou inválido'),
            'ok': bool(ok), 'exit_code': None, 'error': error}


@dataclass
class Element:
    tag: str
    attrs: dict
    parent: object = None
    text: list = field(default_factory=list)

    def ancestor(self, tag):
        parent = self.parent
        while parent:
            if parent.tag == tag:
                return parent
            parent = parent.parent
        return None

    def content(self):
        return ''.join(self.text).strip()

    def enabled(self):
        node = self
        while node:
            if 'disabled' in node.attrs and (node is self or node.tag == 'fieldset'):
                return False
            node = node.parent
        return True


class Document(HTMLParser):
    VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}

    def __init__(self, code):
        super().__init__(convert_charrefs=True)
        self.elements, self.stack, self.errors = [], [], []
        self.doctype = False
        self.feed(code)
        self.close()
        if self.stack:
            self.errors.append('Elementos não fechados: ' + ', '.join(x.tag for x in self.stack))

    def handle_decl(self, decl):
        self.doctype |= decl.casefold().strip() == 'doctype html'

    def handle_starttag(self, tag, attrs):
        element = Element(tag, dict(attrs), self.stack[-1] if self.stack else None)
        if len(attrs) != len(element.attrs):
            self.errors.append('Atributo duplicado em ' + tag)
        self.elements.append(element)
        if tag not in self.VOID:
            self.stack.append(element)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            # Em HTML, a barra de fechamento não fecha elementos não vazios.
            self.errors.append('Elemento HTML não vazio com fechamento abreviado: ' + tag)

    def handle_endtag(self, tag):
        if not self.stack or self.stack[-1].tag != tag:
            self.errors.append('Fechamento fora de ordem: ' + tag)
            return
        self.stack.pop()

    def handle_data(self, data):
        if not any(e.tag in ('script', 'style') for e in self.stack):
            for element in self.stack:
                element.text.append(data)

    def by(self, tag):
        return [e for e in self.elements if e.tag == tag]


def _html(identity, code):
    doc = Document(code)
    counts = Counter(e.attrs.get('id') for e in doc.elements if e.attrs.get('id'))
    duplicate_ids = [identity for identity, count in counts.items() if count > 1]
    cases = [_case('estrutura', not doc.errors and not duplicate_ids,
                   'Tags fechadas em ordem, atributos e ids sem duplicação',
                   '; '.join(doc.errors + ['id duplicado: ' + i for i in duplicate_ids]))]
    if identity == 'html_documento':
        html = doc.by('html')
        titles = [e for e in doc.by('title') if e.ancestor('head') and e.content()]
        mains = [e for e in doc.by('main') if e.ancestor('body')]
        headings = [e for e in doc.by('h1') if e.ancestor('main') in mains and e.content()]
        charset = any(e.attrs.get('charset', '').lower() == 'utf-8' and e.ancestor('head') for e in doc.by('meta'))
        links = [e for e in doc.by('a') if e.ancestor('nav') and e.content()]
        linked = any(e.attrs.get('href', '').startswith('#') and e.attrs['href'][1:] in counts for e in links)
        cases.extend([
            _case('doctype e idioma', doc.doctype and len(html) == 1 and html[0].attrs.get('lang', '').lower() == 'pt-br',
                  'doctype html e um html lang="pt-BR"'),
            _case('metadados', len(doc.by('head')) == 1 and len(titles) == 1 and charset,
                  'head, title não vazio e meta charset UTF-8'),
            _case('conteúdo principal', len(mains) == 1 and len(headings) == 1,
                  'um main no body com um h1 não vazio'),
            _case('navegação interna', linked, 'nav com link textual para id existente'),
        ])
    else:
        names = Counter(e.attrs.get('name') for e in doc.by('input') if e.attrs.get('name'))
        inputs = [e for e in doc.by('input') if e.attrs.get('type', '').lower() == 'email'
                  and e.ancestor('form') and 'required' in e.attrs and e.enabled()
                  and e.attrs.get('name') and names[e.attrs['name']] == 1
                  and e.attrs.get('id') and counts[e.attrs['id']] == 1]
        labels = [e for e in doc.by('label') if e.content()]
        labeled = [e for e in inputs if any(label.attrs.get('for') == e.attrs['id'] for label in labels)]
        submits = [e for e in doc.by('button') if e.attrs.get('type', '').lower() == 'submit'
                   and e.content() and e.enabled()]
        # Um label externo ao form é válido por for/id; o botão de envio desta
        # atividade deve pertencer ao form do campo que estamos avaliando.
        submits_same_form = any(button.ancestor('form') is control.ancestor('form')
                                for button in submits for control in labeled)
        cases.extend([
            _case('controle de email', inputs, 'input email obrigatório, habilitado, com name e id únicos dentro do form'),
            _case('rótulo associado', labeled, 'label textual com for igual ao id do campo'),
            _case('envio', submits_same_form, 'button submit textual e habilitado no mesmo form'),
        ])
    return cases


def _css(identity, code):
    # Reconhecemos regras simples de topo; blocos @ e variáveis calculadas não
    # provam o contrato desta atividade e exigem avaliação no navegador.
    chunks, i = [], 0
    while i < len(code):
        if code.startswith('/*', i):
            end = code.find('*/', i + 2)
            if end < 0:
                return [_case('sintaxe', False, 'comentários fechados', error='Comentário CSS não fechado.')]
            chunks.append(' ')
            i = end + 2
        elif code[i] in ('"', "'"):
            quote = code[i]
            i += 1
            while i < len(code) and code[i] != quote:
                i += 2 if code[i] == '\\' else 1
            if i >= len(code):
                return [_case('sintaxe', False, 'strings fechadas', error='String CSS não fechada.')]
            chunks.append('STRING')
            i += 1
        else:
            chunks.append(code[i])
            i += 1
    masked = ''.join(chunks)
    depth, start, selector, declarations, valid = 0, 0, '', {}, True
    for index, char in enumerate(masked):
        if char == '{':
            if depth == 0:
                selector, start = masked[start:index].strip(), index + 1
            depth += 1
        elif char == '}':
            depth -= 1
            if depth < 0:
                valid = False
                break
            if depth == 0:
                if '.galeria' in [s.strip() for s in selector.split(',')]:
                    for declaration in masked[start:index].split(';'):
                        if ':' in declaration:
                            key, value = declaration.split(':', 1)
                            declarations[key.strip().lower()] = re.sub(r'\s+', '', value).lower()
                start = index + 1
    valid = valid and depth == 0 and not masked[start:].strip()
    gap = declarations.get('gap', '')
    positive = re.fullmatch(r'(\d+(?:\.\d+)?|\.\d+)(px|rem|em|%)', gap)
    columns = declarations.get('grid-template-columns', '')
    # A atividade pede este padrão concreto para tornar os critérios auditáveis.
    dimension = r'(?:\d+(?:\.\d+)?|\.\d+)(?:px|rem|em)'
    template = re.fullmatch(r'repeat\(auto-fit,minmax\(min\(100%,' + dimension + r'\),1fr\)\)', columns)
    return [_case('sintaxe', valid, 'regras e comentários fechados'),
            _case('display', declarations.get('display') == 'grid', '.galeria com display:grid'),
            _case('espaçamento', positive and float(positive.group(1)) > 0, 'gap positivo em px, rem, em ou %'),
            _case('colunas', template, 'repeat(auto-fit, minmax(min(100%, mínimo), 1fr))')]


_DATASETS = (
    (('A', 10), ('A', 20), ('B', 5)),
    (('C', 0), ('B', 2), ('B', 2), ('A', 1)),
    (),
    (('estudo', 7), ('casa', 10), ('estudo', 3)),
)


def _sql(code, timeout):
    cases = []
    for index, rows in enumerate(_DATASETS):
        connection = sqlite3.connect(':memory:')
        try:
            connection.execute('CREATE TABLE vendas(categoria TEXT NOT NULL, valor INTEGER NOT NULL)')
            connection.executemany('INSERT INTO vendas VALUES (?, ?)', rows)
            expected = connection.execute('SELECT categoria, SUM(valor) FROM vendas GROUP BY categoria ORDER BY categoria').fetchall()
            started = time.monotonic()
            allowed = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION, sqlite3.SQLITE_RECURSIVE}

            def authorize(action, arg1, arg2, database, trigger):
                functions = {'sum', 'total', 'count', 'avg', 'min', 'max', 'coalesce', 'ifnull', 'nullif', 'round', 'abs', 'length', 'lower', 'upper', 'typeof'}
                if action == sqlite3.SQLITE_FUNCTION and str(arg2 or arg1).lower() not in functions:
                    return sqlite3.SQLITE_DENY
                return sqlite3.SQLITE_OK if action in allowed else sqlite3.SQLITE_DENY

            connection.set_authorizer(authorize)
            calls = 0

            def interrupt():
                nonlocal calls
                calls += 1
                return calls > 1000 or time.monotonic() - started > max(.1, min(timeout, 3))

            connection.set_progress_handler(interrupt, 1000)
            actual = connection.execute(code).fetchmany(101)
            cases.append(_case('conjunto ' + str(index + 1), actual == expected, repr(expected), repr(actual)))
        except sqlite3.Error as exc:
            cases.append(_case('conjunto ' + str(index + 1), False, 'consulta SELECT válida e limitada', error=str(exc)))
            break
        finally:
            connection.close()
    return cases


def evaluate(identity, code, *, timeout=3):
    if identity.startswith('html_'):
        return _html(identity, code)
    if identity == 'css_grade':
        return _css(identity, code)
    if identity == 'sql_totais':
        return _sql(code, timeout)
    raise ValueError('Corretor não implementado: ' + identity)
