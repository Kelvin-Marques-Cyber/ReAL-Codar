"""Prática por projeto/linguagem, com gravação atômica e intercâmbio validado."""

import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from codar import langs, paths
from codar.locking import file_lock


def _file():
    return paths.data_dir() / 'study-progress.json'


def _load():
    try:
        file = _file()
        if file.stat().st_size > 8_000_000:
            raise ValueError('Arquivo de progresso excede o limite de leitura.')
        state = json.loads(file.read_text(encoding='utf-8'))
    except FileNotFoundError:
        return {}
    if not isinstance(state, dict):
        raise ValueError('Arquivo de progresso inválido: ' + str(file))
    return state


def _save(state):
    file = _file()
    paths.ensure_private_dir(file.parent)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=file.parent, delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(state, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(file)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)


def _validate(progress):
    if not isinstance(progress, dict) or len(progress) > len(langs.LANGS):
        raise ValueError('Progresso de aprendizagem inválido.')
    for lang, entries in progress.items():
        if lang not in langs.LANGS or not isinstance(entries, dict) or len(entries) > 2000:
            raise ValueError('Linguagem ou registros de progresso inválidos.')
        for concept, date in entries.items():
            if not isinstance(concept, str) or not re.fullmatch(r'[\w.:-]{1,180}', concept):
                raise ValueError('Identificador de prática inválido.')
            if not isinstance(date, str) or len(date) > 40:
                raise ValueError('Data de prática inválida.')
            try:
                parsed = datetime.fromisoformat(date.replace('Z', '+00:00'))
            except ValueError as exc:
                raise ValueError('Data de prática inválida.') from exc
            if parsed.tzinfo is None:
                raise ValueError('A data de prática deve incluir o fuso horário.')
    return progress


def ler(project, lang):
    try:
        progress = _load().get(str(Path(project).resolve()), {})
        _validate(progress)
        return dict(progress.get(lang, {}))
    except (OSError, ValueError, AttributeError):
        return {}


def marcar(project, lang, concept):
    importar(project, {'schema': 1, 'progress': {lang: {concept: datetime.now(timezone.utc).isoformat()}}})


def exportar(project):
    """Exporta somente este projeto, sem caminhos de outros projetos ou código."""
    progress = _load().get(str(Path(project).resolve()), {})
    _validate(progress)
    return {'schema': 1, 'progress': progress}


def importar(project, payload):
    """Mescla no projeto escolhido; nunca adota caminhos de um arquivo importado."""
    if not isinstance(payload, dict) or type(payload.get('schema')) is not int or payload['schema'] != 1:
        raise ValueError('Formato de progresso não suportado; esperado schema 1.')
    incoming = _validate(payload.get('progress'))
    with file_lock(_file().with_suffix('.lock')):
        state = _load()
        key = str(Path(project).resolve())
        target = _validate(state.get(key, {}))
        for lang, entries in incoming.items():
            destination = target.setdefault(lang, {})
            for concept, date in entries.items():
                old = destination.get(concept)
                if old is None or datetime.fromisoformat(date.replace('Z', '+00:00')) > datetime.fromisoformat(old.replace('Z', '+00:00')):
                    destination[concept] = date
        state[key] = target
        _save(state)
    return sum(len(entries) for entries in incoming.values())
