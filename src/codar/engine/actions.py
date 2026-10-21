"""Separa pedidos informativos de geração antes de escolher um estágio do motor."""

from pathlib import Path
import re
import shlex

from codar.engine.imports import is_import_request, is_native_import
from codar.textutil import fold

INFORMATIONAL = frozenset({'query', 'install', 'execute', 'study'})
# Verbos de execução também abrem construções de código: "teste se x > 1" é um if,
# "execute 3 vezes" um laço e "teste unitário para somar" pede o código do teste.
_CONSTRUCT = re.compile(r'^(?:test\w*|verific\w*|chec\w*|check\w*|comprob\w*|comprueb\w*|prueb\w*)\s+'
                        r'(?:se|if|whether|si)\b|^(?:testes?|tests?|pruebas?)\s+(?:unitari\w*|unit\w*|de\s+unidade|'
                        r'automatizad\w*|automated)\b')


def _code_construct(intent: str, text: str, locale: str | None) -> bool:
    if _CONSTRUCT.match(text):
        return True
    from codar.engine.locale_intents import normalize
    from codar.engine.stage0 import Stage0

    return Stage0().parse(normalize(intent, locale) if locale else intent) is not None


def classify(intent: str, lang: str | None = None, locale: str | None = None) -> str:
    """Mesma classe para pedidos equivalentes em pt-BR, en, es e pt-PT; identificadores ficam intactos."""
    if is_native_import(intent.strip(), lang) or is_import_request(intent, lang):
        return 'import'
    if '\n' in intent.strip():
        return 'generate'
    text = fold(intent).strip().lstrip('#/ ')
    text = re.sub(r'^(?:por favor|please|por favor,)\s*[, :]?\s*', '', text)
    if re.match(r'^(?:instal\w*|install|add package|adicione o pacote)\b', text):
        return 'install'
    if re.match(r"^(?:(?:eu\s+)?quero|quiero|gostaria\s+de|quisiera|i\s+want\s+to|i\s+would\s+like\s+to|i'd\s+like\s+to)?"
                r"\s*(?:estud\w*|study|learn|aprend(?:er|a|e|amos)\b)", text):
        return 'study'
    # "correr o programa" é executar em pt-PT; "corre las pruebas", em espanhol.
    if re.match(r'^(?:execut\w*|ejecut\w*|rodar|rode|run|testar|teste|test|prueba)\b|^corr(?:a|e|er)\s+(?:(?:o|a|os|as|el|la|'
                r'los|las|meu|minha|meus|minhas|mi|mis)\s+)*(?:programa|arquivo|ficheiro|archivo|script|testes?|pruebas?|'
                r'codigo|projeto|projecto|proyecto|aplicacao|aplicacion|app)\b', text):
        return 'generate' if _code_construct(intent, text, locale) else 'execute'
    if re.match(r'^(?:expli\w*|explain|consult\w*|look\s+up|mostrar a api|show (?:the )?(?:api|documentation)|'
                r'como\b|how\b|qual\b|quais\b|what\b|que es\b|cual\b|o\s+que\s+(?:e|eh|sao|significa)\b)\b', text):
        return 'query'
    return 'generate'


def information(kind, intent, lang, root=None, file=None, code=''):
    """Produz orientação/fontes locais; nunca gera implementação nem executa ações."""
    from codar import estudo
    from codar.libraries import LibraryCatalog, import_modules

    root = Path(root).resolve() if root else None
    catalog = LibraryCatalog(root, file)
    if kind == 'install':
        from codar.library_packages import installation_plan

        match = re.search(r'(?:instal\w*|install)\s+(?:(?:a|o|the|uma|um)\s+)?'
                          r'(?:(?:biblioteca|pacote|library|package)\s+)?([@\w./-]+)', fold(intent))
        name = match[1] if match else ''
        if not root or not name:
            return 'Escolha o projeto e o pacote em Bibliotecas → Instalar… ou use codar libraries install NOME --dry-run.'
        try:
            plan = installation_plan(root, name, lang)
        except ValueError as exc:
            return str(exc)
        return ('Plano de instalação no projeto ' + str(root) + ':\n' + '\n'.join(shlex.join(argv) for argv in plan) +
                '\n\nNenhum comando foi executado. Use Bibliotecas → Instalar… para revisar e confirmar o plano.')
    if kind == 'execute':
        return ('Para executar o arquivo aberto, use F5. Para testes do projeto, use Verificar projeto na paleta. '
                'Exercícios: codar study exercises e codar study check ID --file ARQUIVO. Nenhum código foi executado por esta consulta.')
    modules = import_modules(code, lang)
    # Um nome explícito de API tem prioridade sobre imports não relacionados.
    match = re.search(r'\b(?:api|biblioteca|library|pacote|package|modulo|module)\s+(?:(?:de|do|da|of|for)\s+)?([@\w./-]+)', intent, re.I)
    if match:
        modules.insert(0, match[1])
    for name in dict.fromkeys(modules[:8]):
        ref = catalog.learn(name, lang)
        if ref:
            if kind == 'study' and root:
                from codar.estudo.bibliotecas import track

                value = track(root, name, lang)
                return '\n\n'.join(lesson.title + '\n' + lesson.text + '\n' + lesson.example + '\nPratique: ' + lesson.practice
                                   for lesson in value.lessons)
            return ref.context(intent) + '\n\nFontes locais:\n' + '\n'.join(ref.sources)
    concepts = estudo.conceitos_da_linha('# ' + intent, lang)
    if not concepts:
        for line in code.splitlines()[:80]:
            concepts += [c for c in estudo.conceitos_da_linha(line, lang) if c not in concepts]
            if len(concepts) >= 3:
                break
    if concepts:
        output = []
        for concept in concepts[:3]:
            example, _ = estudo.exemplo(concept, lang)
            output.append(concept.titulo + '\n' + estudo.explicacao(concept, lang) + '\n\n' + example +
                          '\n\nPratique: ' + concept.pratique + '\nFontes: ' + ', '.join(estudo.fontes(concept, lang)))
        return '\n\n'.join(output)
    return ('Abra Estudo (F7) para explicações contextuais ou Bibliotecas (Ctrl+Shift+L) para APIs e trilhas. '
            'Escolha uma linha/função ou informe a biblioteca para uma consulta específica. Seu arquivo foi preservado.')
