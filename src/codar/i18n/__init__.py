"""Idiomas humanos independentes das linguagens de programação; fallback pt-BR."""

from functools import lru_cache
import json
from pathlib import Path
import os

LOCALES = {'pt-BR': 'Português (Brasil)', 'en': 'English', 'es': 'Español', 'pt-PT': 'Português (Portugal)'}


def normalize_locale(value):
    value = str(value or 'pt-BR').replace('_', '-').split('.')[0]
    aliases = {'pt': 'pt-BR', 'pt-br': 'pt-BR', 'pt-pt': 'pt-PT', 'en-us': 'en', 'en-gb': 'en', 'es-es': 'es'}
    value = aliases.get(value.lower(), value.lower() if value.lower() in ('en', 'es') else value)
    if value not in LOCALES:
        raise ValueError('Locale não suportado: ' + value + '. Use ' + ', '.join(LOCALES))
    return value


def get_locale():
    from codar import config

    return normalize_locale(os.environ.get('CODAR_LOCALE') or config.load().get('ui', {}).get('locale', 'pt-BR'))


@lru_cache(maxsize=4)
def resources(locale):
    return json.loads(Path(__file__).with_name(normalize_locale(locale) + '.json').read_text(encoding='utf-8'))


def tr(message, locale=None, **values):
    locale = normalize_locale(locale) if locale else get_locale()
    translated = resources(locale).get('ui', {}).get(message, message)
    return translated.format(**values) if values else translated


def localize_widgets(surface):
    """Traduz somente rótulos conhecidos; código, nomes, paths e fontes ficam intactos."""
    from rich.text import Text
    from textual.widgets import Button, Input, Static, Tab

    locale = get_locale()
    for widget in surface.walk_children():
        if widget.border_title:
            widget.border_title = tr(widget.border_title, locale)
        if isinstance(widget, (Button, Tab)):
            if isinstance(widget, Tab) and any(parent.id == 'editors' for parent in widget.ancestors):
                continue
            label = widget.label
            plain = label.plain if isinstance(label, Text) else str(label)
            translated = tr(plain, locale)
            if translated != plain:
                widget.label = translated
        elif isinstance(widget, Input):
            widget.placeholder = tr(widget.placeholder, locale)
        elif isinstance(widget, Static):
            content = widget.content
            if isinstance(content, (str, Text)):
                plain = content.plain if isinstance(content, Text) else content
                translated = tr(plain, locale)
                if translated != plain:
                    widget.update(Text(translated))
