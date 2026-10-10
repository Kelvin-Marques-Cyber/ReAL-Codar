"""Referências locais de bibliotecas, sem executar imports nem treinar o modelo.

Inspeciona código, declarações de tipos e documentação como dados. O catálogo
é separado por projeto, linguagem, origem e versão/conteúdo da biblioteca.
"""

from __future__ import annotations

import ast
from dataclasses import asdict, dataclass, field
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import re
import sysconfig
import tempfile
from urllib.parse import unquote, urlparse

from codar import paths
from codar._compat import tomllib
from codar.library_names import python_module
from codar.project import EXCLUDED_DIRS, Project, SECRET_NAMES, find_root
from codar.textutil import STOPWORDS, fold

MAX_BYTES = 512_000
MAX_FILES = 24
MAX_SYMBOLS = 600
CACHE_SCHEMA = 3
EXTENSIONS = {'.py', '.pyi', '.js', '.ts', '.mjs', '.cjs', '.dart', '.rs', '.go', '.java', '.kt',
              '.cs', '.h', '.hpp', '.php', '.rb', '.lua', '.sh', '.ps1', '.psm1', '.swift', '.r',
              '.jl', '.md', '.rst', '.txt', '.xml', '.json', '.yaml', '.toml', '.css', '.html'}


def project_root(root: str | Path | None = None, file: str | Path | None = None) -> Path | None:
    if root:
        candidate = Path(root).expanduser().resolve()
    elif file:
        candidate = find_root(file) or Path(file).expanduser().resolve().parent
    else:
        return None
    return candidate if candidate.is_dir() else None


def _read(file: Path) -> str:
    if file.name in SECRET_NAMES or file.name.startswith('.env') or (
            file.suffix.lower() not in EXTENSIONS and file.name not in ('METADATA', 'Cargo.lock', 'go.mod')):
        return ''
    try:
        if not file.is_file() or file.stat().st_size > MAX_BYTES:
            return ''
        text = file.read_text(encoding='utf-8')
        return text if '\0' not in text and len(text.encode('utf-8')) <= MAX_BYTES else ''
    except (OSError, UnicodeError):
        return ''


def _signature(text: str) -> str:
    return text if len(text) <= 1200 else text[:1160] + ' … [assinatura abreviada; consulte a fonte]'


def _symbols(text: str, lang: str, query: str = '') -> list[str]:
    """Assinaturas e docstrings; nunca avalia anotações, decorators ou código."""
    if lang == 'python':
        try:
            tree = ast.parse(text)
        except (SyntaxError, ValueError, RecursionError):
            return []
        output = []
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if isinstance(node, ast.ClassDef):
                    signature = 'class ' + node.name
                else:
                    signature = ('async ' if isinstance(node, ast.AsyncFunctionDef) else '') + 'def ' + node.name
                    signature += '(' + ast.unparse(node.args) + ')'
                    if node.returns:
                        signature += ' -> ' + ast.unparse(node.returns)
                output.append(_signature(signature))
                doc = ast.get_docstring(node)
                if doc:
                    output.append('  ' + doc.splitlines()[0][:240])
                if isinstance(node, ast.ClassDef):
                    for member in node.body:
                        if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
                                not member.name.startswith('_') or member.name == '__init__'):
                            output.append(_signature(node.name + '.' + member.name + '(' + ast.unparse(member.args) + ')'))
            elif isinstance(node, ast.ImportFrom):
                output.append(ast.unparse(node)[:300])
        if query:
            output.sort(key=lambda line: -_symbol_relevance(line, query))
        return output[:MAX_SYMBOLS]
    # Tipos e declarações legíveis de outros ecossistemas; documentação mantém
    # a sintaxe original quando a linguagem não tem um analisador específico.
    declaration = re.compile(
        r'^\s*(?:export\s+|default\s+|public\s+|static\s+|async\s+|declare\s+|pub\s+|abstract\s+)*'
        r'(?:def |function |class |interface |type |enum |struct |func |fn |module |trait |const |let |val |'
        r'extension |protocol |[\w<>?\[\],]+\s+[\w-]+\s*\()')
    method = re.compile(r'^\s*(?:(?:static|readonly|async|get|set)\s+)*[A-Za-z_$][\w$]*'
                        r'(?:<[^>]+>)?\s*\([^)]*\)\s*[:{]')
    output = [line.strip()[:300] for line in text.splitlines() if declaration.match(line) or (
        lang in ('javascript', 'typescript') and method.match(line))]
    if query:
        output.sort(key=lambda line: -_symbol_relevance(line, query))
    return output[:MAX_SYMBOLS]


@lru_cache(maxsize=32)
def _query_words(query: str) -> frozenset[str]:
    ignored = STOPWORDS | {'import', 'from', 'def', 'self', 'const', 'return', 'function', 'class',
                          'funcao', 'funcoes', 'biblioteca', 'library', 'codigo', 'code', 'crie', 'usar'}
    tokens = re.findall(r'[\w]+', fold(query))
    return frozenset(dict.fromkeys(part for word in tokens for part in (word, *word.split('_'))
                                  if len(part) >= 3 and part not in ignored))


def _relevance(text: str, query: str) -> int:
    text = fold(text)
    exact = set(re.findall(r'\w+', text))
    return sum(3 if word in exact else 1
               for word in _query_words(query) if word in text)


def _symbol_relevance(text: str, query: str) -> int:
    score = _relevance(text, query)
    if text.startswith(('from ', 'import ')):
        return score
    name = re.search(r'(?:def|class|function|func|fn)\s+([\w.]+)|^([\w.$]+)\s*\(', text)
    if name:
        score += 10 * _relevance(name[1] or name[2], query)
    return score


def _lazy_reexports(tree: ast.Module) -> list[ast.ImportFrom]:
    """Tabelas literais de exports preguiçosos (Pydantic/Transformers), sem eval."""
    imports = []
    for node in tree.body:
        value = node.value if isinstance(node, (ast.Assign, ast.AnnAssign)) else None
        targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
        if not isinstance(value, ast.Dict) or not any(isinstance(t, ast.Name) and t.id in (
                '_dynamic_imports', '_import_structure', '_lazy_imports') for t in targets):
            continue
        for key, item in zip(value.keys, value.values):
            if not isinstance(key, ast.Constant) or not isinstance(key.value, str):
                continue
            if isinstance(item, ast.Tuple) and item.elts and isinstance(item.elts[-1], ast.Constant) and isinstance(item.elts[-1].value, str):
                module, symbols = item.elts[-1].value, [key.value]
            elif isinstance(item, (ast.List, ast.Set)):
                module = '.' + key.value
                symbols = [e.value for e in item.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]
            else:
                continue
            if not module.startswith('.') or not re.fullmatch(r'[.\w]+', module):
                continue
            aliases = [ast.alias(name=s, asname=None) for s in symbols if s.isidentifier()]
            if aliases:
                imports.append(ast.ImportFrom(module=module.lstrip('.'),
                                              names=aliases, level=len(module) - len(module.lstrip('.'))))
    return imports


def _top_names(text: str) -> set[str]:
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError, RecursionError):
        return set()
    return {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}


def _module_for(file: Path, root: Path) -> str:
    base = root / 'src' if (root / 'src').is_dir() and file.is_relative_to(root / 'src') else root
    relative = file.relative_to(base).with_suffix('')
    parts = list(relative.parts)
    if parts[-1] == '__init__':
        parts.pop()
    if not parts or not all(part.isidentifier() for part in parts):
        raise ValueError('O caminho do módulo precisa usar nomes Python válidos.')
    return '.'.join(parts)


def _relative_module(module: str, current: str | Path | None, root: Path) -> str:
    if not current:
        return module
    current = Path(current).resolve()
    if not current.is_relative_to(root) or not (current.parent / '__init__.py').is_file():
        return module
    current_parts = _module_for(current, root).split('.')[:-1]
    target = module.split('.')
    common = 0
    for a, b in zip(current_parts, target):
        if a != b:
            break
        common += 1
    if not common:
        return module
    return '.' * (len(current_parts) - common + 1) + '.'.join(target[common:])


def local_python_import(intent: str, root: Path | None, current: str | None = None) -> str | None:
    """Resolve pedidos por função/arquivo usando o projeto como fonte de verdade."""
    if root is None:
        return None
    text = fold(intent)
    paths_in_text = re.findall(r'[\w./\\-]+\.py\b', intent)
    asks_symbol = bool(re.search(r'\b(?:funcao|funcoes|function|functions|classe|class|classes)\b', text))
    asks_local = bool(re.search(r'\b(?:minha|minhas|meu|meus|propri[oa]s?)\b', text))
    if not paths_in_text and not asks_symbol and not asks_local:
        return None
    files = []
    for relative in Project.load(root).files():
        if relative.endswith('.py'):
            file = root / relative
            if file.is_symlink() or not file.resolve().is_relative_to(root):
                continue
            if current and file.resolve() == Path(current).resolve():
                continue
            files.append(file)
    explicit = bool(paths_in_text)
    if explicit:
        matches = set()
        for wanted in paths_in_text:
            wanted = wanted.replace('\\', '/')
            if Path(wanted).is_absolute() or '..' in Path(wanted).parts:
                raise ValueError('Informe um arquivo Python dentro do projeto.')
            matches.update(f for f in files if f.relative_to(root).as_posix() == wanted or (
                '/' not in wanted and f.name == wanted))
        files = sorted(matches)
        if not files:
            raise ValueError('Arquivo Python não encontrado no projeto: ' + ', '.join(paths_in_text))
    words = set(re.findall(r'\w+', text))
    if asks_local and not asks_symbol and not explicit:
        files = [file for file in files if fold(file.stem) in words]
        explicit = bool(files)
    matches = []
    all_functions = bool(re.search(r'\b(?:todas|todos|all)\b', text))
    for file in files[:2000]:
        names = _top_names(_read(file))
        if explicit and all_functions and 'classe' not in text and 'class' not in text:
            try:
                names = {n.name for n in ast.parse(_read(file)).body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
            except (SyntaxError, ValueError, RecursionError):
                names = set()
        requested = sorted(name for name in names if fold(name) in words or (
            explicit and all_functions and not name.startswith('_')))
        if requested or explicit and not asks_symbol:
            matches.append((file, requested))
    if not matches:
        if explicit or re.search(r'\b(?:minha|minhas|meu|meus|propri[oa]s?)\b', text):
            raise ValueError('Função/classe não encontrada. Informe seu nome e o arquivo .py de origem.')
        return None
    if len(matches) != 1:
        choices = ', '.join(file.relative_to(root).as_posix() for file, _ in matches[:8])
        raise ValueError('Importação ambígua; indique o arquivo de origem: ' + choices)
    file, names = matches[0]
    module = _module_for(file, root)
    if names:
        return 'from ' + _relative_module(module, current, root) + ' import ' + ', '.join(names)
    return 'import ' + module


@dataclass
class Reference:
    name: str
    lang: str
    version: str
    origin: str
    fingerprint: str
    symbols: list[str] = field(default_factory=list)
    documentation: str = ''
    sources: list[str] = field(default_factory=list)
    source_root: str = ''
    symbol_sources: dict[str, str] = field(default_factory=dict)

    def context(self, query: str = '') -> str:
        # ChatML delimiters in dependency documentation must stay inert data.
        symbols = sorted(self.symbols, key=lambda line: -_symbol_relevance(line, query)) if query else self.symbols
        docs = self.documentation
        if query:
            lines = docs.splitlines()
            matching = [i for i, line in enumerate(lines) if _relevance(line, query)]
            if matching:
                selected = sorted({j for i in matching[:6] for j in range(max(0, i - 1), min(len(lines), i + 3))})
                docs = '\n'.join(lines[i] for i in selected)
        selected = []
        used = 0
        for line in symbols:
            origin = self.symbol_sources.get(line, '')
            line = line + (f' [fonte: {origin}]' if origin else '')
            if used + len(line) + 1 > 1950:
                continue
            selected.append(line)
            used += len(line) + 1
        text = (f'{self.name} [{self.lang}; versão {self.version}; {self.origin}; '
                f'revisão {self.fingerprint[:12]}]\n' +
                '\n'.join(selected) + '\n' + docs[:600])
        return text.replace('<|', '< |').replace('```', "'''")[:2600]


def import_modules(code: str, lang: str) -> list[str]:
    if lang == 'python':
        # O buffer pode ainda conter pseudocódigo: analisa linhas de imports
        # isoladas quando o arquivo inteiro não é Python válido.
        try:
            nodes = ast.parse(code).body
        except (SyntaxError, ValueError, RecursionError):
            nodes = []
            for line in code.splitlines():
                try:
                    nodes.extend(ast.parse(line.strip()).body)
                except (SyntaxError, ValueError, RecursionError):
                    pass
        names = []
        for node in nodes:
            if isinstance(node, ast.Import):
                names.extend(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                module = '.' * node.level + (node.module or '')
                names.append(module)
                names.extend(module + ('' if module.endswith('.') else '.') + a.name for a in node.names if a.name != '*')
    else:
        names = re.findall(r'''(?:from\s+|require(?:_relative)?\s*\(?\s*|import\s+|source\s+|@import\s+)['"]([^'"\n]+)['"]''', code)
        if lang == 'dart':
            names = [n[8:].split('/')[0] if n.startswith('package:') else n for n in names]
        if lang in ('java', 'kotlin', 'csharp', 'swift', 'rust', 'julia'):
            names += re.findall(r'(?:import|using|use)\s+([\w.:]+)', code)
        if lang == 'powershell':
            names += re.findall(r"(?i)Import-Module\s+(?:-Name\s+)?['\"]?([\w./\\-]+)", code)
        if lang == 'r':
            names += re.findall(r'''(?:library|require)\(\s*['"]?(\w+)''', code)
        if lang in ('c', 'cpp'):
            names += re.findall(r'#\s*include\s*[<"]([^>"\n]+)', code)
    return list(dict.fromkeys(names))[:12]


class LibraryCatalog:
    def __init__(self, root: Path | None, current: str | None = None):
        self.root = root
        self.current = Path(current).resolve() if current else None

    def _scope(self) -> str:
        return hashlib.sha256(str(self.root).encode()).hexdigest()[:20]

    def _directory(self) -> Path:
        return paths.data_dir() / 'libraries' / self._scope()

    def _python_roots(self) -> list[Path]:
        roots = []
        if self.root:
            roots += [self.root / 'src', self.root]
            if self.current:
                roots.append(self.current.parent)
            # Lê os ambientes do projeto e a seleção explícita de runtime.
            environments = [self.root / '.venv', self.root / 'venv']
            try:
                from codar.runtimes import selected

                runtime = selected('python', self.root)
                if runtime:
                    environments.insert(0, Path(runtime['executable']).parent.parent)
            except ValueError:
                pass
            for env in environments:
                roots += sorted((env / 'lib').glob('python*/site-packages'))[:6]
                roots.append(env / 'Lib' / 'site-packages')
        roots += [Path(sysconfig.get_path('stdlib'))]
        return list(dict.fromkeys(p for p in roots if p.is_dir()))

    def _resolve(self, name: str, lang: str) -> tuple[Path, str, str] | None:
        if not name or '..' in Path(name.replace('.', '/')).parts or '\0' in name:
            return None
        if lang == 'python':
            if not name.startswith('.'):
                name = python_module(name)
            if name.startswith('.'):
                if not self.current or not self.root:
                    return None
                level = len(name) - len(name.lstrip('.'))
                base = self.current.parent
                for _ in range(level - 1):
                    base = base.parent
                if not base.is_relative_to(self.root):
                    return None
                roots = [base]
                name = name[level:]
            else:
                roots = self._python_roots()
            if name and not all(part.isidentifier() for part in name.split('.')):
                return None
            for base in roots:
                candidate = base.joinpath(*name.split('.')) if name else base
                source = next((p for p in (candidate.with_suffix('.pyi'), candidate.with_suffix('.py'),
                                          candidate / '__init__.pyi', candidate / '__init__.py') if p.is_file()), None)
                if source:
                    if not source.resolve().is_relative_to(base.resolve()):
                        continue
                    version = 'local'
                    for metadata in sorted(base.glob('*.dist-info/METADATA'))[:300]:
                        metadata_text = _read(metadata)
                        dist_name = re.search(r'^Name:\s*(.+)$', metadata_text, re.M)
                        normalized = re.sub('[-_.]+', '-', dist_name[1].strip()).lower() if dist_name else ''
                        top_levels = _read(metadata.parent / 'top_level.txt').splitlines()
                        if normalized == re.sub('[-_.]+', '-', name.split('.')[0]).lower() or name.split('.')[0] in top_levels or (
                                dist_name and python_module(dist_name[1].strip()).split('.')[0] == name.split('.')[0]):
                            match = re.search(r'^Version:\s*(.+)$', metadata_text, re.M)
                            if match:
                                version = match[1].strip()
                            break
                    return source, version, 'projeto' if self.root and source.is_relative_to(self.root) and (
                        'site-packages' not in source.parts) else 'instalada'
        elif lang in ('javascript', 'typescript') and self.root:
            if name.startswith('.') and self.current:
                folder = (self.current.parent / name).resolve()
                if folder.is_relative_to(self.root):
                    for file in (folder, folder.with_suffix('.ts'), folder.with_suffix('.js')):
                        if file.exists():
                            return file, 'local', 'projeto'
                return None
            if not re.fullmatch(r'(?:@[\w.-]+/)?[\w.-]+(?:/[\w./-]+)?', name) or '..' in Path(name).parts:
                return None
            parts = name.split('/')
            package = '/'.join(parts[:2]) if name.startswith('@') else parts[0]
            for parent in (self.root, *list(self.root.parents)[:4]):
                folder = parent / 'node_modules' / package
                if folder.is_dir():
                    try:
                        metadata = json.loads(_read(folder / 'package.json') or '{}')
                    except (ValueError, TypeError):
                        metadata = {}
                    version = str(metadata.get('version', 'local'))
                    # Muitas bibliotecas JS publicam os tipos em @types, como
                    # React e Express. Vincula ambas as versões à referência.
                    types_name = package[1:].replace('/', '__') if package.startswith('@') else package
                    types = parent / 'node_modules' / '@types' / types_name
                    if not metadata.get('types') and not metadata.get('typings') and not any(folder.glob('*.d.ts')) and types.is_dir():
                        try:
                            types_metadata = json.loads(_read(types / 'package.json') or '{}')
                        except (ValueError, TypeError):
                            types_metadata = {}
                        return types, version + '; @types ' + str(types_metadata.get('version', 'local')), 'instalada'
                    return folder, version, 'instalada'
        elif lang == 'dart' and self.root:
            try:
                config_file = self.root / '.dart_tool' / 'package_config.json'
                config = json.loads(_read(config_file))
                for package in config.get('packages', []):
                    if package.get('name') == name:
                        uri = urlparse(package['rootUri'])
                        if uri.scheme not in ('', 'file'):
                            continue
                        folder = Path(unquote(uri.path)) if uri.scheme == 'file' else config_file.parent / unquote(uri.path)
                        match = re.search(r'^version:\s*([^\s#]+)', _read(folder / 'pubspec.yaml'), re.M)
                        return folder.resolve(), match[1] if match else 'local', 'instalada'
            except (OSError, ValueError, KeyError, TypeError):
                pass
        elif lang == 'rust' and self.root:
            crate = name.split('::')[0]
            if re.fullmatch(r'\w+', crate):
                try:
                    lock = tomllib.loads(_read(self.root / 'Cargo.lock') or '')
                    versions = {p['version'] for p in lock.get('package', []) if p.get('name', '').replace('-', '_') == crate}
                    cargo = Path(os.environ.get('CARGO_HOME', str(Path.home() / '.cargo')))
                    candidates = [p for p in (cargo / 'registry/src').glob('*/*') if p.is_dir() and
                                  any(p.name.replace('-', '_') == crate + '_' + v for v in versions)]
                    if len(candidates) == 1:
                        return candidates[0], next(iter(versions)), 'instalada'
                except (OSError, ValueError, KeyError, TypeError):
                    pass
        elif lang == 'go' and self.root:
            # go.mod vincula a versão usada; go.sum também retém versões antigas.
            for module, version in re.findall(r'^\s*(?:require\s+)?([^\s()]+)\s+(v\S+)', _read(self.root / 'go.mod'), re.M):
                if not (name == module or name.startswith(module + '/')):
                    continue
                escaped = re.sub(r'[A-Z]', lambda m: '!' + m[0].lower(), module)
                cache = Path(os.environ.get('GOMODCACHE', str(Path(os.environ.get('GOPATH', str(Path.home() / 'go'))).joinpath('pkg/mod'))))
                folder = cache / (escaped + '@' + version) / name[len(module):].lstrip('/')
                if folder.is_dir():
                    return folder, version, 'instalada'
        elif lang == 'csharp' and self.root:
            try:
                assets = json.loads(_read(self.root / 'obj/project.assets.json') or '{}')
                for package in assets.get('libraries', {}):
                    package_name, version = package.rsplit('/', 1)
                    if name == package_name or name.startswith(package_name + '.'):
                        for folder in assets.get('packageFolders', {}):
                            candidate = Path(folder) / package_name.lower() / version
                            if candidate.is_dir():
                                return candidate, version, 'instalada'
            except (OSError, ValueError, TypeError):
                pass
        if self.root:
            # Outros ecossistemas: fontes/documentação que acompanham o projeto.
            short = name.split('::')[0].split('.')[0]
            if short and re.fullmatch(r'[\w@/-]+', short) and not Path(short).is_absolute() and '..' not in Path(short).parts:
                for folder in ('vendor', 'lib', 'libs', 'packages', 'docs'):
                    candidate = self.root / folder / short
                    if candidate.exists() and candidate.resolve().is_relative_to(self.root):
                        return candidate, 'local', 'projeto'
        return None

    @staticmethod
    def _files(source: Path, query: str = '') -> list[Path]:
        if source.is_file():
            files = [source]
            if source.name.startswith('__init__.'):
                # Segue exports locais/absolutos dentro deste pacote (pandas,
                # requests, FastAPI, etc.), sem importar nem visitar o venv.
                root = source.parent.resolve()
                queue = [(source, 0, 0)]
                visited = {source.resolve()}
                while queue and len(files) < MAX_FILES:
                    queue.sort(key=lambda item: -item[2])
                    file, depth, score = queue.pop(0)
                    if file != source:
                        files.append(file)
                    if depth >= 3:
                        continue
                    try:
                        tree = ast.parse(_read(file))
                    except (SyntaxError, ValueError, RecursionError):
                        continue
                    nodes = [n for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)] + _lazy_reexports(tree)
                    nodes.sort(key=lambda n: -_relevance(ast.unparse(n), query))
                    for node in nodes:
                        parts = (node.module or '').split('.') if node.module else []
                        if node.level:
                            base = file.parent
                            for _ in range(node.level - 1):
                                base = base.parent
                        elif parts and parts[0] == root.name:
                            base, parts = root, parts[1:]
                        else:
                            continue
                        modules = [base.joinpath(*parts)] if parts else [base / a.name for a in node.names if a.name != '*']
                        for module in modules:
                            if len(visited) >= 160:
                                break
                            candidate = next((p for p in (module.with_suffix('.pyi'), module.with_suffix('.py'),
                                                          module / '__init__.pyi', module / '__init__.py') if p.is_file()), None)
                            if not candidate or candidate.resolve() in visited or not candidate.resolve().is_relative_to(root) or candidate.is_symlink():
                                continue
                            visited.add(candidate.resolve())
                            queue.append((candidate, depth + 1, max(score, _relevance(ast.unparse(node), query))))
                            # Bibliotecas grandes mantêm a busca limitada ao
                            # pacote, sem percorrer o ambiente inteiro.
                            if len(visited) >= 160:
                                break
                        if len(visited) >= 160:
                            break
                neighbors = sorted([*root.glob('*.pyi'), *root.glob('*.py')], key=lambda p: (-_relevance(p.stem, query), p.name))
                files += [p for p in neighbors if not p.is_symlink() and p.resolve() not in visited][:MAX_FILES - len(files)]
            return list(dict.fromkeys(files))[:MAX_FILES]
        files = []
        preferred = ['index.d.ts', 'src/lib.rs', 'README.md', 'README.rst']
        try:
            metadata = json.loads(_read(source / 'package.json') or '{}')
            preferred += [metadata[key] for key in ('types', 'typings', 'module', 'main') if isinstance(metadata.get(key), str)]
        except (ValueError, TypeError):
            pass
        for name in preferred:
            file = source / name
            if file.is_file() and file.resolve().is_relative_to(source.resolve()) and not file.is_symlink():
                files.append(file)
        seen = 0
        for folder, directories, names in os.walk(source, followlinks=False):
            seen += 1
            if seen > 80:
                break
            directories[:] = sorted((d for d in directories if d not in EXCLUDED_DIRS and not d.startswith('.') and
                                     len(Path(folder).relative_to(source).parts) < 3), key=lambda n: (-_relevance(n, query), n))
            for name in sorted(names, key=lambda n: (-_relevance(n, query), not n.endswith('.d.ts'), not n.lower().startswith(('readme', 'index')), n)):
                file = Path(folder) / name
                if file.suffix.lower() in EXTENSIONS and not file.is_symlink() and file not in files:
                    files.append(file)
                    if len(files) >= MAX_FILES:
                        return files
        return files

    def learn(self, name: str, lang: str, source: Path | None = None, version: str | None = None,
              query: str = '') -> Reference | None:
        found = (source.expanduser().resolve(), version or 'manual', 'documentação fornecida') if source else self._resolve(name, lang)
        if not found:
            return self._manual(name, lang)
        source, detected_version, origin = found
        if not source.exists():
            raise ValueError('Fonte de documentação não encontrada: ' + str(source))
        files = self._files(source, query)
        texts = [(file, _read(file)) for file in files]
        texts = [(file, text) for file, text in texts if text]
        if not texts:
            if source and origin == 'documentação fornecida':
                raise ValueError('A fonte não contém documentação/código legível dentro dos limites de leitura.')
            return self._manual(name, lang)
        digest = hashlib.sha256()
        for file, text in sorted(texts, key=lambda item: str(item[0])):
            digest.update(str(file).encode())
            digest.update(text.encode())
        fingerprint = digest.hexdigest()
        cache_key = hashlib.sha256(repr((name, lang, str(source), detected_version)).encode()).hexdigest()
        focus = hashlib.sha256(repr(sorted(_query_words(query))).encode()).hexdigest() if query else ''
        cache_file = self._directory() / (cache_key + '.json')
        try:
            value = json.loads(_read(cache_file))
            cached = Reference(**{k: v for k, v in value.items() if k not in ('schema', 'focus')})
            if cached.fingerprint == fingerprint and value.get('schema') == CACHE_SCHEMA and value.get('focus', '') == focus:
                if origin == 'documentação fornecida':
                    cache_file.touch()
                return cached
        except (OSError, ValueError, TypeError):
            pass
        symbols = []
        symbol_sources = {}
        docs = []
        for file, text in texts:
            extracted = _symbols(text, lang, query)
            base = source.parent if source.is_file() else source
            label = str(file.relative_to(base)) if file.is_relative_to(base) else file.name
            for symbol in extracted:
                symbol_sources.setdefault(symbol, label)
            symbols += extracted
            if file.suffix.lower() in ('.md', '.rst', '.txt', '.xml'):
                docs.append(text[:1600])
            elif file.suffix in ('.py', '.pyi'):
                try:
                    doc = ast.get_docstring(ast.parse(text))
                    if doc:
                        docs.append(doc[:500])
                except (SyntaxError, ValueError, RecursionError):
                    pass
        if query:
            symbols.sort(key=lambda line: -_symbol_relevance(line, query))
        retained = []
        used = 0
        for symbol in dict.fromkeys(symbols):
            size = len(symbol.encode('utf-8')) + len(symbol_sources[symbol].encode('utf-8'))
            if used + size > 150_000 or len(retained) >= MAX_SYMBOLS:
                break
            retained.append(symbol)
            used += size
        ref = Reference(name, lang, version or detected_version, origin, fingerprint,
                        retained, '\n'.join(docs)[:2200], [str(f) for f, _ in texts], str(source),
                        {s: symbol_sources[s] for s in retained})
        directory = paths.ensure_private_dir(self._directory())
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=directory, delete=False) as handle:
            json.dump({**asdict(ref), 'schema': CACHE_SCHEMA, 'focus': focus}, handle, ensure_ascii=False)
            temporary = Path(handle.name)
        temporary.replace(cache_file)
        return ref

    def list(self) -> list[Reference]:
        output = []
        newest = sorted(self._directory().glob('*.json'), key=lambda p: p.stat().st_mtime_ns, reverse=True)[:400]
        for file in reversed(newest):
            try:
                value = json.loads(_read(file))
                output.append(Reference(**{k: v for k, v in value.items() if k not in ('schema', 'focus')}))
            except (OSError, ValueError, TypeError):
                continue
        return output

    def forget(self, name: str, lang: str) -> int:
        removed = 0
        for file in self._directory().glob('*.json'):
            try:
                value = json.loads(_read(file))
                ref = Reference(**{k: v for k, v in value.items() if k not in ('schema', 'focus')})
                if ref.name == name and ref.lang == lang:
                    file.unlink()
                    removed += 1
            except (OSError, ValueError, TypeError):
                continue
        return removed

    def verify(self, name: str, lang: str) -> dict:
        old = next((ref for ref in reversed(self.list()) if ref.name == name and ref.lang == lang), None)
        try:
            current = self.learn(name, lang)
        except (OSError, ValueError) as exc:
            return {'ok': False, 'message': str(exc)}
        if not current:
            return {'ok': False, 'message': 'Fontes/tipos/documentação indisponíveis; nenhum código foi executado.'}
        changed = bool(old and (old.version, old.fingerprint) != (current.version, current.fingerprint))
        return {'ok': True, 'name': name, 'lang': lang, 'version': current.version, 'changed': changed,
                'fingerprint': current.fingerprint,
                'message': 'Referência atualizada após mudança de versão/conteúdo.' if changed else 'Referência local verificada.'}

    def _manual(self, name: str, lang: str) -> Reference | None:
        for ref in reversed(self.list()):
            if ref.name == name and ref.lang == lang and ref.origin == 'documentação fornecida':
                # Relê as fontes: APIs alteradas não ficam congeladas no cache.
                source = Path(ref.source_root) if ref.source_root else None
                if source and source.exists():
                    return self.learn(name, lang, source, ref.version)
        return None

    def context(self, code: str, lang: str, query: str = '') -> str:
        references = []
        fingerprints = set()
        modules = import_modules(code, lang)
        # Imports no topo de um arquivo grande podem estar fora da janela do
        # cursor enviada pelo editor. O buffer recebido continua prioritário.
        if self.current and self.root and self.current.is_relative_to(self.root) and (
                Project.load(self.root).allowed(self.current.relative_to(self.root).as_posix())):
            modules += [name for name in import_modules(_read(self.current), lang) if name not in modules]
        if query:
            modules.sort(key=lambda name: -_relevance(name, query))
        for name in modules[:12]:
            try:
                reference = self.learn(name, lang, query=query)
            except (OSError, ValueError, RecursionError):
                continue
            if reference and reference.fingerprint not in fingerprints:
                fingerprints.add(reference.fingerprint)
                references.append(reference.context(query))
                if len(references) >= 4:
                    break
        return '\n\n'.join(references)[:8000]
