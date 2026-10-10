"""Registro manual de prática, separado por projeto e linguagem."""

import json
from datetime import datetime, timezone
from pathlib import Path
from codar import paths


def _file():
    return paths.data_dir() / 'study-progress.json'


def ler(project, lang):
    try:
        state = json.loads(_file().read_text(encoding='utf-8'))
        return state.get(str(Path(project).resolve()), {}).get(lang, {})
    except (OSError, ValueError, AttributeError):
        return {}


def marcar(project, lang, concept):
    file = _file()
    try:
        state = json.loads(file.read_text(encoding='utf-8'))
    except FileNotFoundError:
        state = {}
    if not isinstance(state, dict):
        raise ValueError('Arquivo de progresso inválido: ' + str(file))
    state.setdefault(str(Path(project).resolve()), {}).setdefault(lang, {})[concept] = datetime.now(timezone.utc).isoformat()
    file.parent.mkdir(parents=True, exist_ok=True)
    temporary = file.with_suffix('.tmp')
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(file)
