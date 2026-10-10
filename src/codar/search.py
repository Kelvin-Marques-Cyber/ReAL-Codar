"""Busca limitada ao projeto; a IA opcional sugere termos, sem executar o conteúdo."""

from __future__ import annotations

import asyncio
import json
import re

from codar.engine.models import STOP, build_prompt
from codar.engine.stage2 import ModelUnavailable
from codar.project import Project, read_source, safe_path
from codar.textutil import fold


async def keywords(router, query: str) -> list[str]:
    stage = router.stage2 if router else None
    if stage is None or not stage.configured():
        raise ModelUnavailable('Busca por contexto precisa da IA local instalada e de um modelo configurado.')
    task = ('Translate this code search description into useful identifier fragments or keywords in Portuguese '
            'and English. Return ONLY a JSON array of 1 to 8 short strings. No explanation, commands or code. '
            'Prefer concrete API and domain terms over generic words. Search description: ' + json.dumps(query))
    result = await asyncio.wrap_future(stage.submit(stage.generate,
            lambda level: build_prompt(stage.fmt, 'JSON', 'json', task), max_tokens=192,
            stop=STOP + ['<|im_start|>']))
    if result.finish == 'length':
        raise ValueError('A IA não concluiu os termos; tente uma descrição menor ou desligue Usar IA local.')
    raw = result.text.strip()
    if raw.startswith('```'):
        raw = re.sub(r'^```(?:json)?\s*|\s*```$', '', raw)
    try:
        values = json.loads(raw)
    except (ValueError, TypeError) as exc:
        raise ValueError('A IA devolveu termos inválidos. Use a busca literal ou reformule a descrição.') from exc
    if not isinstance(values, list) or not 1 <= len(values) <= 8 or any(
            not isinstance(value, str) or not value.strip() or len(value) > 64 or
            any(ord(char) < 32 for char in value) for value in values):
        raise ValueError('A IA deve devolver até oito palavras ou expressões curtas.')
    return list(dict.fromkeys(value.strip() for value in values))


def scan(project, query, terms, *, file='', buffer=None, names=True, limit=200):
    matches, skipped, total, scanned, truncated = [], [], 0, 0, False
    targets = [file] if file else project.files(code_only=False)
    truncated = not file and len(targets) >= project.max_files
    for name in targets:
        if names and any(term.casefold() in name.casefold() for term in terms):
            matches.append(dict(path=name, line=1, col=0, length=0, text='Nome do arquivo',
                                snippet=name, score=10, kind='name'))
        if buffer is not None and file:
            text = buffer  # snapshot do arquivo aberto, incluindo alterações não salvas
        else:
            try:
                if not project.allowed(name):
                    continue
                path = safe_path(project.root, name)
                size = path.stat().st_size
                if total + size > 32 * 1024 * 1024:
                    truncated = True
                    break
                total += size
                text = read_source(path)
            except (OSError, UnicodeError, ValueError):
                skipped.append(name)
                continue
        scanned += 1
        lines = text.splitlines()
        for row, line in enumerate(lines):
            hits = [(match.start(), match.end() - match.start()) for term in terms
                    if (match := re.search(re.escape(term), line, re.IGNORECASE))]
            if not hits and len(terms) > 1:
                folded, positions = '', []
                for index, char in enumerate(line):
                    part = fold(char)
                    folded += part
                    positions.extend([index] * len(part))
                for term in terms:
                    needle = fold(term)
                    at = folded.find(needle) if needle else -1
                    if at >= 0:
                        hits.append((positions[at], positions[at + len(needle) - 1] + 1 - positions[at]))
            if not hits:
                continue
            col, length = min(hits)
            matches.append(dict(path=name, line=row + 1, col=col, length=length, text=line[:600],
                                   snippet='\n'.join(lines[max(0, row - 2):row + 3])[:3000],
                                   score=len(hits) + (5 if query.casefold() in line.casefold() else 0), kind='content'))
            if len(matches) > limit * 2:
                matches.sort(key=lambda match: (-match['score'], match['path'], match['line']))
                del matches[limit:]
                truncated = True
        if len(matches) > limit:
            matches.sort(key=lambda match: (-match['score'], match['path'], match['line']))
            del matches[limit:]
            truncated = True
    matches.sort(key=lambda match: (-match['score'], match['path'], match['line']))
    return dict(query=query, terms=terms, results=matches[:limit], files_scanned=scanned,
                skipped=skipped[:30], truncated=truncated)


async def search_project(router, params):
    query = str(params.get('query', '')).strip()
    if not query or len(query) > 500:
        raise ValueError('Digite de 1 a 500 caracteres para buscar.')
    project = await asyncio.to_thread(Project.load, str(params.get('root', '.')))
    use_ai = bool(params.get('ai', False))
    terms = list(dict.fromkeys([query] + (await keywords(router, query) if use_ai else [])))
    file = str(params.get('file', ''))
    buffer = params.get('buffer')
    if file:
        safe_path(project.root, file)
        if buffer is None and not project.allowed(file):
            raise ValueError('Arquivo excluído da busca do projeto.')
    if buffer is not None and (not isinstance(buffer, str) or len(buffer) > 512_000 or not file):
        raise ValueError('O buffer deve ter até 512 mil caracteres e um nome de arquivo.')
    result = await asyncio.to_thread(scan, project, query, terms, file=file, buffer=buffer,
                                    names=bool(params.get('names', True)))
    result['ai'] = use_ai
    return result
