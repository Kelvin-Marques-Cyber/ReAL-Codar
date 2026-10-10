"""Plugins: pacotes declarativos (TOML) de padrões, skills, regras de auditoria e conselhos de projeto.

Estrutura de um plugin (embutido em codar/plugins/<nome> ou do usuário em <config>/plugins/<nome>):

    plugin.toml        [plugin] name, version, description
    patterns/*.toml    [[pattern]]  ferramentas de código verificadas (o "arcabouço" da IA)
    skills.toml        [[skill]]    diretrizes injetadas no prompt quando o SLM precisa adaptar algo
    rules.toml         [[rule]]     regras estáticas de auditoria (regex, custo zero)
    advice.toml        [[advice]]   sugestões de projeto com opções executáveis (ex.: npm -> pnpm/bun)
    plugin.py          opcional; só carregado com [plugins] allow_python = true
"""

from __future__ import annotations

import hashlib
import importlib.util
import logging
import os
import re
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any

from codar import __version__, paths
from codar._compat import tomllib
from codar.textutil import SPECIFIC, analyze, concept_set, words

log = logging.getLogger("codar.plugins")


@dataclass
class Pattern:
    id: str
    title: str
    code: dict[str, str]
    keywords: str = ""
    kind: str = "snippet"  # snippet | file | module
    require: list[str] = field(default_factory=list)
    slots: dict[str, str] = field(default_factory=dict)
    produces: str = ""
    consumes: str = ""
    tags: list[str] = field(default_factory=list)
    path: str = ""  # caminho sugerido para kind = "file"
    tests: dict[str, str] = field(default_factory=dict)  # testes executáveis por linguagem (lint)
    source: str = "builtin"
    concepts: frozenset[str] = frozenset()
    core: frozenset[str] = frozenset()

    def finalize(self) -> Pattern:
        self.concepts = frozenset(_norm(c) for c in concept_set(f"{self.title} {self.keywords} {self.id.replace('.', ' ')}"))
        # Núcleo = conceitos essenciais. `require` é explícito; sem ele, vale o título.
        source = " ".join(self.require) if self.require else self.title
        self.core = frozenset(_norm(c) for c in concept_set(source))
        return self


def _norm(concept: str) -> str:
    return concept[1:] if concept.startswith("~") else concept


@dataclass
class Skill:
    id: str
    guidance: list[str]
    langs: list[str] = field(default_factory=list)
    triggers: str = ""
    patterns: list[str] = field(default_factory=list)
    source: str = "builtin"
    concepts: frozenset[str] = frozenset()

    def finalize(self) -> Skill:
        self.concepts = frozenset(_norm(c) for c in concept_set(self.triggers))
        return self


@dataclass
class Rule:
    id: str
    pattern: str
    message: str
    langs: list[str] = field(default_factory=list)
    severity: str = "warning"
    category: str = "security"
    scope: str = "code"  # code (sem comentários) | nostrings (sem comentários nem strings) | all
    in_loop: bool = False
    suggestion: str = ""
    flags: str = ""
    source: str = "builtin"


@dataclass
class AdviceOption:
    id: str
    label: str
    reason: str = ""
    steps: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class Advice:
    id: str
    title: str
    reason: str
    options: list[AdviceOption]
    category: str = "tooling"
    impact: str = "medium"  # low | medium | high
    when: dict[str, Any] = field(default_factory=dict)
    source: str = "builtin"


@dataclass
class Plugin:
    name: str
    version: str = "0"
    description: str = ""
    root: Path | None = None
    builtin: bool = True
    patterns: list[Pattern] = field(default_factory=list)
    skills: list[Skill] = field(default_factory=list)
    rules: list[Rule] = field(default_factory=list)
    advice: list[Advice] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    requires_codar: str = ""
    requires_plugins: dict[str, str] = field(default_factory=dict)


@dataclass
class Bundle:
    plugins: list[Plugin]
    patterns: list[Pattern]
    skills: list[Skill]
    rules: list[Rule]
    advice: list[Advice]
    fingerprint: str
    hooks: list[Any] = field(default_factory=list)


def _load_toml(path: Path) -> dict:
    if path.stat().st_size > 2_000_000:
        raise ValueError(f"{path.name}: TOML excede 2 MB")
    with path.open("rb") as fh:
        return tomllib.load(fh)


PLUGIN_IGNORE = {".git", "__pycache__", ".venv", "node_modules", ".codar-install.json"}


def plugin_files(root: Path) -> list[Path]:
    """Enumeração limitada, sem seguir links ou percorrer dependências vendorizadas."""
    files, total, entries = [], 0, 0
    for directory, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in PLUGIN_IGNORE)
        for name in [*dirs, *sorted(names)]:
            if name in PLUGIN_IGNORE:
                continue
            path = Path(directory) / name
            entries += 1
            if path.is_symlink():
                raise ValueError("plugin contém links simbólicos")
            if entries > 2000:
                raise ValueError("plugin excede o limite de arquivos e pastas")
            if path.is_file():
                size = path.stat().st_size
                total += size
                files.append(path)
                if len(files) > 1000 or size > 8_000_000 or total > 20_000_000:
                    raise ValueError("plugin excede 1000 arquivos ou 20 MB")
    return sorted(files)


def _texts(value, field: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{field}: use uma lista de textos")
    return value


def _patterns_from(data: dict, source: str, errors: list[str]) -> list[Pattern]:
    out = []
    for raw in data.get("pattern", []):
        try:
            raw_code = raw.get("code") or {}
            bad = [k for k, v in raw_code.items() if not isinstance(v, str)]
            if bad:
                raise ValueError(f"variante(s) {bad} não são texto (chave fora do lugar após [pattern.code]?)")
            code = {k: v.strip("\n") + "\n" for k, v in raw_code.items()}
            p = Pattern(
                id=raw["id"], title=raw["title"], code=code, keywords=raw.get("keywords", ""),
                kind=raw.get("kind", "snippet"), require=_texts(raw.get("require", []), "require"),
                slots={k: str(v) for k, v in (raw.get("slots") or {}).items()}, produces=raw.get("produces", ""),
                consumes=raw.get("consumes", ""), tags=_texts(raw.get("tags", []), "tags"), path=raw.get("path", ""),
                tests=dict(raw.get("test") or {}), source=source,
            ).finalize()
            if not p.code:
                raise ValueError("sem variantes de código")
            out.append(p)
        except (KeyError, ValueError, TypeError, AttributeError) as exc:
            errors.append(f"{source}: padrão {raw.get('id', '?') if isinstance(raw, dict) else '?'}: {exc}")
    return out


def load_plugin(root: Path, builtin: bool) -> Plugin:
    plugin = Plugin(name=root.name, root=root, builtin=builtin)
    try:
        meta = _load_toml(root / "plugin.toml").get("plugin", {})
        if not isinstance(meta, dict) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", str(meta.get("name", root.name))):
            raise ValueError("nome de plugin inválido")
        plugin.name = meta.get("name", root.name)
        plugin.version = str(meta.get("version", "0"))
        plugin.description = meta.get("description", "")
        plugin.requires_codar = meta.get("requires_codar", "")
        plugin.requires_plugins = meta.get("requires_plugins", {})
        if not isinstance(plugin.name, str) or not isinstance(plugin.description, str) \
                or not isinstance(plugin.requires_codar, str) or not isinstance(plugin.requires_plugins, dict):
            raise ValueError("manifesto com campos de tipo inválido")
        if not re.fullmatch(r"\d+(?:\.\d+){0,2}(?:[-+][A-Za-z0-9.-]+)?", plugin.version):
            raise ValueError("version deve ser uma versão numérica, ex.: 1.2.0")
        if plugin.requires_codar and not version_matches(__version__, plugin.requires_codar):
            raise ValueError(f"requer Codar {plugin.requires_codar}; instalado {__version__}")
        for name, spec in plugin.requires_plugins.items():
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", name) or not isinstance(spec, str):
                raise ValueError("requires_plugins: use nome = faixa de versões")
            version_matches("0", spec)  # valida a expressão, mesmo antes de resolver dependências
        plugin_files(root)
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        plugin.errors.append(f"{root.name}: {exc}")
        return plugin
    src = plugin.name
    try:
        for f in sorted((root / "patterns").glob("*.toml")) if (root / "patterns").is_dir() else []:
            plugin.patterns += _patterns_from(_load_toml(f), src, plugin.errors)
        if (root / "patterns.toml").exists():
            plugin.patterns += _patterns_from(_load_toml(root / "patterns.toml"), src, plugin.errors)
        if (root / "skills.toml").exists():
            for raw in _load_toml(root / "skills.toml").get("skill", []):
                plugin.skills.append(Skill(id=raw["id"], guidance=_texts(raw["guidance"], "guidance"),
                                           langs=_texts(raw.get("langs", []), "langs"),
                                           triggers=raw.get("triggers", ""), patterns=_texts(raw.get("patterns", []), "patterns"),
                                           source=src).finalize())
        if (root / "rules.toml").exists():
            for raw in _load_toml(root / "rules.toml").get("rule", []):
                plugin.rules.append(Rule(source=src, **{k: v for k, v in raw.items() if k in Rule.__dataclass_fields__}))
        if (root / "advice.toml").exists():
            for raw in _load_toml(root / "advice.toml").get("advice", []):
                options = [AdviceOption(id=o["id"], label=o["label"], reason=o.get("reason", ""),
                                        steps=list(o.get("steps", []))) for o in raw.get("option", [])]
                plugin.advice.append(Advice(id=raw["id"], title=raw["title"], reason=raw.get("reason", ""),
                                            options=options, category=raw.get("category", "tooling"),
                                            impact=raw.get("impact", "medium"), when=raw.get("when", {}), source=src))
        all_items = [*plugin.patterns, *plugin.skills, *plugin.rules, *plugin.advice]
        ids = [item.id for item in all_items]
        if any(not isinstance(identity, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]+", identity) for identity in ids):
            raise ValueError("ids devem ser textos não vazios")
        for items in (plugin.patterns, plugin.skills, plugin.rules, plugin.advice):
            if len({item.id for item in items}) != len(items):
                raise ValueError("ids repetidos no plugin")
        for skill in plugin.skills:
            if not skill.guidance or any(not isinstance(g, str) for g in skill.guidance):
                raise ValueError(f"skill {skill.id}: guidance deve ser uma lista de textos")
        for rule in plugin.rules:
            _texts(rule.langs, "langs")
            if rule.severity not in ("info", "warning", "error", "critical") or not isinstance(rule.message, str):
                raise ValueError(f"regra {rule.id}: severidade ou mensagem inválida")
            if rule.scope not in ("code", "nostrings", "all"):
                raise ValueError(f"regra {rule.id}: scope inválido")
            re.compile(rule.pattern)
    except (OSError, ValueError, KeyError, TypeError, AttributeError, re.error) as exc:
        plugin.errors.append(f"{src}: {exc}")
    return plugin


def version_matches(version: str, spec: str) -> bool:
    def number(value):
        match = re.fullmatch(r"(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:[-+][\w.-]+)?", value)
        if not match:
            raise ValueError(f"versão inválida: {value}")
        return tuple(int(x or 0) for x in match.groups())
    actual = number(version)
    ok = True
    for clause in spec.split(","):
        match = re.fullmatch(r"\s*(>=|<=|!=|==|>|<|=)?\s*(\d+(?:\.\d+){0,2}(?:[-+][\w.-]+)?)\s*", clause)
        if not match:
            raise ValueError(f"faixa inválida: {spec}; use >=0.3.0,<0.4.0")
        op, wanted = match[1] or "==", number(match[2])
        ok &= {">=": actual >= wanted, "<=": actual <= wanted, ">": actual > wanted, "<": actual < wanted,
               "=": actual == wanted, "==": actual == wanted, "!=": actual != wanted}[op]
    return ok


def builtin_root() -> Path:
    return Path(str(resources.files("codar").joinpath("plugins")))


def discover(cfg: dict | None = None) -> Bundle:
    cfg = cfg or {}
    disabled = set((cfg.get("plugins") or {}).get("disabled", []))
    allow_python = bool((cfg.get("plugins") or {}).get("allow_python", False))
    roots: list[tuple[Path, bool]] = []
    base = builtin_root()
    if base.is_dir():
        roots += [(p, True) for p in sorted(base.iterdir()) if p.is_dir() and not p.name.startswith(("_", "."))]
    user = paths.user_plugins_dir()
    if user.is_dir():
        roots += [(p, False) for p in sorted(user.iterdir()) if p.is_dir() and not p.name.startswith(("_", "."))]
    plugins, hooks = [], []
    digest = hashlib.sha256()
    for root, builtin in roots:
        try:
            plugin = load_plugin(root, builtin)
        except Exception as exc:
            plugin = Plugin(name=root.name, root=root, builtin=builtin, errors=[f"falha ao carregar: {exc}"])
        if plugin.name in disabled:
            continue
        plugins.append(plugin)
        try:
            for f in plugin_files(root):
                if f.suffix == ".toml" or f.name == "plugin.py":
                    digest.update(str(f).encode() + f.read_bytes())
        except (OSError, ValueError) as exc:
            plugin.errors.append(f"não foi possível ler plugin: {exc}")
        for err in plugin.errors:
            log.warning("plugin %s: %s", plugin.name, err)
    names = {}
    for plugin in plugins:
        if plugin.name in names:
            plugin.errors.append(f"nome já usado por {names[plugin.name].root}")
        elif not plugin.errors:
            names[plugin.name] = plugin
    # Ciclos não têm uma ordem válida de inicialização.
    visited, stack = set(), []
    def visit(name):
        if name in stack:
            for cyclic in stack[stack.index(name):]:
                names[cyclic].errors.append("ciclo de dependências: " + " -> ".join(stack + [name]))
            return
        if name in visited or name not in names:
            return
        visited.add(name)
        stack.append(name)
        for dependency in names[name].requires_plugins:
            visit(dependency)
        stack.pop()
    for name in names:
        visit(name)
    # Propaga dependências indisponíveis antes de carregar extensões Python.
    for _ in range(len(plugins)):
        changed = False
        for plugin in plugins:
            if plugin.errors:
                continue
            for name, spec in plugin.requires_plugins.items():
                dependency = names.get(name)
                if dependency is None or dependency.errors or not version_matches(dependency.version, spec):
                    plugin.errors.append(f"dependência indisponível: {name} {spec}")
                    changed = True
                    break
        if not changed:
            break
    active = [p for p in plugins if not p.errors]
    registered = {}
    for plugin in active:
        file = plugin.root / "plugin.py"
        if file.exists() and (plugin.builtin or allow_python):
            hook = _load_python(file, plugin)
            if hook:
                registered[plugin.name] = hook
    for _ in range(len(active)):
        changed = False
        for plugin in active:
            if not plugin.errors and any(names[name].errors for name in plugin.requires_plugins):
                plugin.errors.append("dependência falhou ao carregar a extensão Python")
                changed = True
        if not changed:
            break
    active = [p for p in active if not p.errors]
    hooks = [registered[p.name] for p in active if p.name in registered]
    seen: dict[str, Pattern] = {}
    for plugin in active:  # plugins do usuário vêm depois e sobrescrevem ids embutidos
        for p in plugin.patterns:
            seen[p.id] = p
    return Bundle(plugins=plugins, patterns=list(seen.values()),
                  skills=[s for p in active for s in p.skills], rules=[r for p in active for r in p.rules],
                  advice=[a for p in active for a in p.advice], fingerprint=digest.hexdigest()[:16], hooks=hooks)


def _load_python(path: Path, plugin: Plugin):
    spec = importlib.util.spec_from_file_location(f"codar_plugin_{plugin.name}", path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except (Exception, SystemExit) as exc:  # falhas comuns de extensão não encerram o daemon
        plugin.errors.append(f"plugin.py: {exc}")
        return None
    return getattr(module, "register", None)


def specific_concepts(text: str) -> set[str]:
    return {c for _, cs, _ in analyze(text) for c in cs if c in SPECIFIC}


def keyword_stems(text: str) -> set[str]:
    return {w[:5] for w in words(text) if len(w) >= 4}
