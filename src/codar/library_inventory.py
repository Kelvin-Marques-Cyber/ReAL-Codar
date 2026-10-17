"""Inventário offline: manifestos, instalação, imports e referências reais.

Nenhuma biblioteca é importada e nenhum gerenciador é executado.
Versões mais recentes no registro não são inferidas a partir de dados locais.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from codar import langs
from codar._compat import tomllib
from codar.libraries import LibraryCatalog, _read as _library_read, import_modules
from codar.library_names import python_distribution, python_module
from codar.project import Project

LIMIT = 1000


@dataclass
class Dependency:
    name: str
    lang: str
    module: str
    version: str = ''
    requirement: str = ''
    declared: bool = False
    installed: bool = False
    imported: bool = False
    documented: bool = False
    origin: str = ''
    sources: list[str] = field(default_factory=list)

    @property
    def unresolved(self):
        return (self.declared or self.imported) and not self.installed and self.origin != 'projeto'

    @property
    def status(self):
        from codar.i18n import tr

        flags = [('declarada', self.declared), ('instalada', self.installed), ('importada', self.imported),
                 ('documentada', self.documented), ('não resolvida', self.unresolved)]
        return ' · '.join(tr(label) for label, yes in flags if yes) or self.origin or 'referência'


def _read(file):
    return "" if file.is_symlink() else _library_read(file)


def _json(file, boundary=None):
    if boundary and not file.resolve().is_relative_to(boundary.resolve()):
        return {}
    try:
        value = json.loads(_read(file) or '{}')
        return value if isinstance(value, dict) else {}
    except (ValueError, TypeError):
        return {}


def _toml(file):
    if file.is_symlink():
        return {}
    try:
        return tomllib.loads(_read(file) or '')
    except ValueError:
        return {}


def _mapping(value):
    return value if isinstance(value, dict) else {}


def _key(name, lang):
    if lang == 'python':
        return re.sub(r'[-_.]+', '-', python_distribution(name)).lower()
    return name.lower() if lang == 'csharp' else name.replace('-', '_') if lang == 'rust' else name


def _module(name, lang):
    return python_module(name).replace('-', '_') if lang == 'python' else name.replace('-', '_') if lang == 'rust' else name


def inventory(root: Path, lang: str, query: str = '') -> list[Dependency]:
    root = Path(root).resolve()
    project = Project.load(root)
    lang = langs.resolve(lang).id
    catalog = LibraryCatalog(root)
    rows, aliases = {}, {}

    def add(name, *, module=None, source='', **values):
        if not isinstance(name, str) or not name or len(name) > 180 or any(ord(c) < 32 for c in name):
            return None
        key = aliases.get(name, _key(name, lang))
        if key not in rows and len(rows) >= LIMIT:
            return None
        row = rows.setdefault(key, Dependency(name, lang, module or _module(name, lang)))
        if module:
            row.module = module
            aliases[module] = key
        for field_name, value in values.items():
            if value:
                setattr(row, field_name, value)
        if source and source not in row.sources:
            row.sources.append(source)
        return row

    def declared(name, requirement, source, module=None):
        return add(name, module=module, requirement=str(requirement), source=source, declared=True)

    if lang == 'python':
        data = _toml(root / 'pyproject.toml')
        pkg = _mapping(data.get('project'))
        requirements = list(pkg.get('dependencies', [])) if isinstance(pkg, dict) else []
        for group in _mapping(pkg.get('optional-dependencies')).values() if isinstance(pkg, dict) else []:
            if isinstance(group, list):
                requirements += group
        for value in requirements:
            if isinstance(value, str) and (match := re.match(r'^\s*([A-Za-z0-9][\w.-]*)', value)):
                declared(match[1], value[match.end():].strip(), 'pyproject.toml')
        poetry = _mapping(_mapping(_mapping(data.get('tool')).get('poetry')).get('dependencies'))
        if isinstance(poetry, dict):
            for name, version in poetry.items():
                if name != 'python':
                    declared(name, version.get('version', '') if isinstance(version, dict) else version, 'pyproject.toml')
        for file in sorted(root.glob('*requirements*.txt'))[:20] + sorted(root.glob('requirements*.in'))[:20]:
            if file.is_symlink():
                continue
            for line in _read(file).splitlines():
                if match := re.match(r'^\s*([A-Za-z0-9][\w.-]*)(?:\[[^\]]+\])?\s*([^#]*)', line):
                    declared(match[1], match[2].strip(), file.name)
        for base in catalog._python_roots():
            if base.name != 'site-packages':
                continue
            for metadata in sorted(base.glob('*.dist-info/METADATA'))[:LIMIT]:
                if metadata.is_symlink() or not metadata.resolve().is_relative_to(base.resolve()):
                    continue
                text = _read(metadata)
                name = re.search(r'^Name:\s*(.+)$', text, re.M)
                version = re.search(r'^Version:\s*(.+)$', text, re.M)
                if not name:
                    continue
                top_file = metadata.parent / 'top_level.txt'
                top = _read(top_file) if not top_file.is_symlink() else ''
                modules = [line for line in top.splitlines() if line.isidentifier()]
                row = add(name[1].strip(), module=modules[0] if modules else None, installed=True,
                          version=version[1].strip() if version else '', source=str(metadata), origin='instalada')
                if row:
                    for module in modules:
                        aliases[module] = _key(row.name, lang)
            break  # o ambiente escolhido tem precedência sobre alternativas
    elif lang in ('javascript', 'typescript'):
        data = _json(root / 'package.json', root)
        for group in ('dependencies', 'devDependencies', 'peerDependencies', 'optionalDependencies'):
            dependencies = data.get(group, {})
            if isinstance(dependencies, dict):
                for name, version in dependencies.items():
                    declared(name, version, 'package.json')
        modules = root / 'node_modules'
        candidates = []
        if modules.is_dir() and not modules.is_symlink():
            for entry in sorted(modules.iterdir())[:LIMIT]:
                if entry.name.startswith('@') and entry.is_dir() and not entry.is_symlink():
                    candidates += sorted(entry.iterdir())[:LIMIT]
                elif not entry.name.startswith('.'):
                    candidates.append(entry)
        for folder in candidates[:LIMIT]:
            if not folder.resolve().is_relative_to(modules.resolve()):
                continue
            data = _json(folder / 'package.json', modules)
            if data.get('name'):
                add(data['name'], installed=True, version=str(data.get('version', '')), origin='instalada',
                    source=str(folder / 'package.json'))
    elif lang == 'dart':
        section = ''
        for line in _read(root / 'pubspec.yaml').splitlines():
            if match := re.match(r'^(\w+):', line):
                section = match[1]
            elif section in ('dependencies', 'dev_dependencies') and (match := re.match(r'^  (\w+):\s*(.*)', line)):
                declared(match[1], match[2].split('#')[0].strip(), 'pubspec.yaml')
        data = _json(root / '.dart_tool/package_config.json', root)
        for package in data.get('packages', [])[:LIMIT]:
            if isinstance(package, dict) and isinstance(package.get('name'), str):
                found = catalog._resolve(package['name'], lang)
                if found:
                    add(package['name'], version=found[1], origin=found[2], installed=True, source=str(found[0]))
    elif lang == 'rust':
        data = _toml(root / 'Cargo.toml')
        groups = [data.get(name, {}) for name in ('dependencies', 'dev-dependencies', 'build-dependencies')]
        for target in _mapping(data.get('target')).values():
            if isinstance(target, dict):
                groups += [target.get(name, {}) for name in ('dependencies', 'dev-dependencies', 'build-dependencies')]
        for group in groups:
            if isinstance(group, dict):
                for name, details in group.items():
                    version = details.get('version', '') if isinstance(details, dict) else details
                    actual = details.get('package', name) if isinstance(details, dict) else name
                    declared(actual, version, 'Cargo.toml', module=name.replace('-', '_'))
    elif lang == 'go':
        for name, version in re.findall(r'^\s*(?:require\s+)?([^\s()]+)\s+(v\S+)', _read(root / 'go.mod'), re.M):
            declared(name, version, 'go.mod')
    elif lang == 'csharp':
        for file in sorted(root.glob('*.csproj'))[:50]:
            text = _read(file)
            if '<!DOCTYPE' in text or '<!ENTITY' in text:
                continue
            try:
                tree = ET.fromstring(text)
            except ET.ParseError:
                continue
            for node in tree.iter():
                if node.tag.split('}')[-1] == 'PackageReference' and node.get('Include'):
                    version = node.get('Version') or next((n.text for n in node if n.tag.split('}')[-1] == 'Version'), '')
                    declared(node.get('Include'), version or '', file.name)
        assets = _json(root / 'obj/project.assets.json', root)
        for package in _mapping(assets.get('libraries')):
            if '/' in package:
                name, version = package.rsplit('/', 1)
                found = catalog._resolve(name, lang)
                if found:
                    add(name, installed=True, version=version, origin=found[2], source=str(found[0]))

    for relative in project.files()[:500]:
        file = root / relative
        detected = langs.from_path(file)
        compatible = detected and (detected.id == lang or {detected.id, lang} <= {'javascript', 'typescript'})
        if not compatible or file.is_symlink() or not file.resolve().is_relative_to(root):
            continue
        for name in import_modules(_read(file), lang):
            if lang == 'python':
                if name.startswith('.'):
                    continue
                name = name.split('.')[0]
            elif lang in ('javascript', 'typescript'):
                if name.startswith(('.', 'node:')):
                    continue
                name = '/'.join(name.split('/')[:2]) if name.startswith('@') else name.split('/')[0]
            elif lang == 'rust':
                name = name.split('::')[0]
                if name in ('crate', 'self', 'super', 'std', 'core', 'alloc'):
                    continue
            add(name, imported=True, source=relative)

    for ref in catalog.list():
        if ref.lang == lang:
            add(ref.name, documented=True, source=ref.source_root)
    for row in rows.values():
        if not row.installed and (row.imported or row.declared):
            try:
                found = catalog._resolve(row.module, lang)
            except (OSError, ValueError, TypeError):
                found = None
            if found:
                row.origin = found[2]
                row.installed = found[2] == 'instalada'
                row.version = found[1]
                if str(found[0]) not in row.sources:
                    row.sources.append(str(found[0]))
    words = query.casefold().split()
    return sorted((row for row in rows.values() if all(word in (row.name + ' ' + row.lang + ' ' + row.status).casefold() for word in words)),
                  key=lambda row: (not row.unresolved, row.name.casefold()))
