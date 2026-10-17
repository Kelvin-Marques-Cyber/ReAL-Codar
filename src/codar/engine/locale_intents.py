"""Front-end ES conservador: preserva identificadores e literais antes da IR comum."""

import re
from codar.i18n import normalize_locale
from codar.textutil import fold

_ATOM = r'[A-Za-z_]\w*|-?\d+(?:\.\d+)?'


def _expression(value, known):
    if value in known or re.match(r'^[\"\'`]', value):
        return value
    text = fold(value)
    pair = re.fullmatch(rf'(?:(?:la|el)\s+)?(suma|promedio|producto|diferencia)\s+(?:de|entre)\s+({_ATOM})\s+(?:y|con)\s+({_ATOM})', value, re.I)
    if pair:
        op, a, b = pair.groups()
        return f'({a} + {b}) / 2' if op.lower() == 'promedio' else f'{a} ' + {'suma':'+','producto':'*','diferencia':'-'}[op.lower()] + f' {b}'
    size = re.fullmatch(r'(?:(?:el|la)\s+)?(?:tamaño|tamano|longitud|cantidad)\s+de\s+([A-Za-z_]\w*)', value, re.I)
    if size:
        return 'tamanho de ' + size[1]
    comparison = re.fullmatch(rf'({_ATOM})\s+(?:es\s+)?(mayor o igual a|menor o igual a|mayor que|menor que|igual a|diferente de|mas|más|menos|por)\s+({_ATOM})', value, re.I)
    if comparison:
        a, op, b = comparison.groups()
        operator = {'mayor o igual a':'>=','menor o igual a':'<=','mayor que':'>','menor que':'<','igual a':'==',
                    'diferente de':'!=','mas':'+','menos':'-','por':'*'}[fold(op)]
        return a + ' ' + operator + ' ' + b
    return {'verdadero':'verdadeiro','falso':'falso','nulo':'nulo'}.get(text, value)


def _normalize(intent, locale, known=None):
    if normalize_locale(locale) != 'es':
        return intent
    known = known or set()
    text = intent.strip()
    # Solo los conectores de una construcción completa son traducidos.
    assign = re.fullmatch(r'([A-Za-z_]\w*)\s+(?:es igual a|recibe|vale)\s+(.+)', text, re.I)
    if assign:
        return assign[1] + ' é igual a ' + _expression(assign[2], known)
    printing = re.fullmatch(r'(?:imprime|imprimir|muestra|mostrar|escribe|escribir)\s+(.+)', text, re.I)
    if printing:
        return 'imprimir ' + _expression(printing[1], known)
    returning = re.fullmatch(r'(?:devuelve|devolver|retorna|retornar)\s+(.+)', text, re.I)
    if returning:
        return 'retornar ' + _expression(returning[1], known)
    for_loop = re.fullmatch(r'para cada\s+([A-Za-z_]\w*)\s+en\s+([A-Za-z_]\w*)\s+(.+)', text, re.I)
    if for_loop:
        return f'para cada {for_loop[1]} em {for_loop[2]} ' + normalize(for_loop[3], locale, known)
    conditional = re.fullmatch(r'(si|mientras)\s+(.+?)\s+(?:entonces\s+)?((?:imprime|imprimir|muestra|mostrar|escribe)\s+.+)', text, re.I)
    if conditional:
        prefix = 'se' if conditional[1].lower() == 'si' else 'enquanto'
        return prefix + ' ' + _expression(conditional[2], known) + ' ' + normalize(conditional[3], locale, known)
    otherwise = re.fullmatch(r'(?:sino|si no)\s+(.+)', text, re.I)
    if otherwise:
        return 'senão ' + normalize(otherwise[1], locale, known)
    importing = re.fullmatch(r'(?:importa|importar|importe)\s+(?:la\s+|el\s+)?(?:(?:biblioteca|libreria|librería|paquete|modulo|módulo)\s+)?([@\w./-]+)', text, re.I)
    if importing:
        return 'importar biblioteca ' + importing[1]
    header = re.fullmatch(r'(si|mientras)\s+(.+)', text, re.I)
    if header:
        return ('se' if header[1].lower() == 'si' else 'enquanto') + ' ' + _expression(header[2].rstrip(':'), known)
    loop_header = re.fullmatch(r'para cada\s+([A-Za-z_]\w*)\s+en\s+([A-Za-z_]\w*)\s*:?$', text, re.I)
    if loop_header:
        return f'para cada {loop_header[1]} em {loop_header[2]}'
    return intent


def normalize(intent, locale, known=None):
    if normalize_locale(locale) != 'es':
        return intent
    prefix = intent[:len(intent) - len(intent.lstrip())]
    return prefix + _normalize(intent.strip(), locale, known)
