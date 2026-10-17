"""Validação estática da resposta, sem executar código gerado ou baixar parsers."""

from __future__ import annotations

import ast
import importlib
import re
import textwrap
from functools import lru_cache


_GRAMMARS = {
    'javascript': 'javascript', 'typescript': 'typescript', 'go': 'go', 'rust': 'rust',
    'java': 'java', 'c': 'c', 'cpp': 'cpp', 'csharp': 'c_sharp', 'bash': 'bash',
    'powershell': 'powershell', 'lua': 'lua', 'ruby': 'ruby', 'php': 'php',
    'kotlin': 'kotlin', 'swift': 'swift', 'dart': 'dart', 'julia': 'julia', 'yaml': 'yaml',
    'html': 'html', 'css': 'css',
}


@lru_cache(maxsize=24)
def _parser(lang: str):
    """Só gramáticas opcionais já instaladas; nunca usa language-pack (pode baixar)."""
    grammar = _GRAMMARS.get(lang)
    if not grammar:
        return None
    try:
        from tree_sitter import Language, Parser

        module = importlib.import_module('tree_sitter_' + grammar)
        factory = getattr(module, 'language_typescript' if lang == 'typescript' else
                          'language_php' if lang == 'php' else 'language')
        return Parser(Language(factory()))
    except (ImportError, AttributeError, TypeError, ValueError):
        return None


def validator_name(lang: str) -> str:
    return 'python_ast' if lang == 'python' else 'tree_sitter' if _parser(lang) else 'lexical'


def generation_problem(code: str, lang: str) -> str:
    """Motivo identificável, ou string vazia. Aceita trechos dependentes de um bloco pai."""
    code = textwrap.dedent(code).strip('\n')
    if not code.strip():
        return 'empty_output'
    if '\ufffd' in code or re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', code):
        return 'invalid_characters'
    if code.lstrip().startswith('<think>') or re.search(r'<\|(?:im_start|im_end|endoftext)\|>', code):
        return 'unexpected_model_delimiter'
    if re.match(r'\s*(?:aqui est[aá]|segue o c[oó]digo|here (?:is|are)|sure[,!]|claro[,!]|'
                r'i (?:cannot|can\x27t)|n[aã]o (?:posso|consigo))\b', code, re.I):
        return 'prose_instead_of_code'
    if lang == 'python':
        candidate = code
        if re.match(r'\s*(?:else|elif)\b', code):
            candidate = 'if True:\n    pass\n' + code
        elif re.match(r'\s*(?:except|finally)\b', code):
            candidate = 'try:\n    pass\n' + code
        elif re.match(r'\s*case\b', code):
            candidate = 'match value:\n' + textwrap.indent(code, '    ')
        try:
            tree = ast.parse(candidate)
        except (SyntaxError, ValueError) as exc:
            return 'python_syntax: ' + str(getattr(exc, 'msg', exc))
        if not tree.body:
            return 'no_instruction'
        if tree.body and all(isinstance(n, ast.Expr) and isinstance(n.value, ast.Name) for n in tree.body):
            return 'identifiers_without_instruction'
        return ''
    parser = _parser(lang)
    if parser:
        candidates = [code]
        wrappers = {
            'go': ('package main\nfunc main() {\n', '\n}'),
            'rust': ('fn main() {\n', '\n}'),
            'java': ('class CodarFragment { void run() {\n', '\n} }'),
            'c': ('void codar_fragment(void) {\n', '\n}'),
            'cpp': ('void codar_fragment() {\n', '\n}'),
            'csharp': ('class CodarFragment { void Run() {\n', '\n} }'),
            'php': ('<?php\n', '\n'),
        }
        if lang in wrappers:
            head, tail = wrappers[lang]
            candidates.append(head + code + tail)
        if lang == 'go' and code.lstrip().startswith('import '):
            candidates.append('package main\n' + code)
        if any(not parser.parse(candidate.encode('utf-8')).root_node.has_error for candidate in candidates):
            return ''
        return lang + '_syntax'
    # O núcleo continua sem dependências. Sem gramática local, rejeita prosa
    # e lixo reconhecíveis; o diagnóstico informa que esta checagem é lexical.
    from codar.audit.lexer import SYNTAX, mask

    if lang in SYNTAX and lang != 'bash':
        stack = []
        for char in mask(code, lang, strings=True):
            if char in '([{':
                stack.append(char)
            elif char in ')]}' and stack:
                if stack.pop() != dict(zip(')]}', '([{'))[char]:
                    return 'unbalanced_delimiters'
        if stack:
            return 'unclosed_delimiters'
    if lang in ('html', 'css'):
        return '' if re.search(r'<[!/?A-Za-z]|[{}]|@(?:import|media|charset)', code) else 'no_markup_or_style'
    if lang == 'dockerfile':
        return '' if re.match(r'\s*(?:#|FROM|RUN|COPY|ADD|ARG|ENV|WORKDIR|ENTRYPOINT|CMD|EXPOSE|USER|LABEL|VOLUME|SHELL|HEALTHCHECK|ONBUILD|STOPSIGNAL)\b', code, re.I) else 'no_docker_instruction'
    if re.fullmatch(r'[\w\s.,!?]+', code) and not re.match(
            r'\s*(?:return|yield|break|continue|pass|end|fi|done|SELECT|COMMIT|ROLLBACK|BEGIN|using|import)\b', code, re.I):
        return 'prose_instead_of_code'
    return ''
