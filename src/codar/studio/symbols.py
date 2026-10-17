"""Índice estático e limitado para sugestões de símbolos e suas assinaturas."""

from dataclasses import dataclass
from pathlib import Path
import re

from codar import langs
from codar.libraries import LibraryCatalog, _symbols, import_modules
from codar.project import Project, read_source, safe_path


@dataclass(frozen=True)
class Completion:
    name: str
    signature: str
    source: str
    kind: str


def _entries(text, lang, source, kind):
    for signature in _symbols(text, lang):
        match = re.search(r'\b(?:def|class|function|func|fn|struct|interface|enum|type)\s+([A-Za-z_$][\w$]*)', signature)
        if not match:
            match = re.match(r'(?:[\w$]+\.)?([A-Za-z_$][\w$]*)\(', signature)
        if match:
            yield Completion(match[1], signature[:400], source, kind)


def index(root: Path, current: str | None, code: str, lang: str) -> list[Completion]:
    root = Path(root).resolve()
    project = Project.load(root)
    entries = list(_entries(code, lang, current or 'buffer', 'file'))
    used = 0
    for relative in project.files()[:300]:
        meta = langs.from_path(relative)
        if not meta or (meta.id != lang and not {meta.id, lang} <= {'javascript', 'typescript'}):
            continue
        try:
            file = safe_path(root, relative)
            size = file.stat().st_size
            if size > 128_000 or used + size > 2_000_000:
                continue
            if current and file == Path(current).resolve():
                continue
            used += size
            entries += list(_entries(read_source(file), lang, relative, 'project'))
        except (OSError, ValueError):
            continue
    catalog = LibraryCatalog(root, current)
    for module in import_modules(code, lang)[:8]:
        try:
            ref = catalog.learn(module, lang)
        except (OSError, ValueError):
            continue
        if ref:
            # Reutiliza as assinaturas já extraídas; não executa o pacote.
            for signature in ref.symbols:
                for item in _entries(signature, lang, ref.symbol_sources.get(signature, ref.source_root), 'library'):
                    entries.append(item)
                # Declarações Python isoladas precisam de corpo para ast.parse.
                match = re.match(r'(?:async )?def ([A-Za-z_]\w*)\(', signature)
                if match:
                    entries.append(Completion(match[1], signature, ref.symbol_sources.get(signature, ref.source_root), 'library'))
                member = re.match(r'([A-Za-z_]\w*)\.([A-Za-z_]\w*)\(', signature)
                if member:
                    entries.append(Completion(member[2], signature, ref.symbol_sources.get(signature, ref.source_root), 'library'))
    output, seen = [], set()
    for entry in entries:
        if entry.name not in seen:
            output.append(entry)
            seen.add(entry.name)
        if len(output) >= 1200:
            break
    return output
