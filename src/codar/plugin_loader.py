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
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any

from codar import paths
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
    with path.open("rb") as fh:
        return tomllib.load(fh)


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
                kind=raw.get("kind", "snippet"), require=list(raw.get("require", [])),
                slots={k: str(v) for k, v in (raw.get("slots") or {}).items()}, produces=raw.get("produces", ""),
                consumes=raw.get("consumes", ""), tags=list(raw.get("tags", [])), path=raw.get("path", ""),
                tests=dict(raw.get("test") or {}), source=source,
            ).finalize()
            if not p.code:
                raise ValueError("sem variantes de código")
            out.append(p)
        except (KeyError, ValueError, TypeError, AttributeError) as exc:
            errors.append(f"{source}: padrão {raw.get('id', '?')}: {exc}")
    return out


def load_plugin(root: Path, builtin: bool) -> Plugin:
    meta = _load_toml(root / "plugin.toml").get("plugin", {}) if (root / "plugin.toml").exists() else {}
    plugin = Plugin(name=meta.get("name", root.name), version=str(meta.get("version", "0")),
                    description=meta.get("description", ""), root=root, builtin=builtin)
    src = plugin.name
    try:
        for f in sorted((root / "patterns").glob("*.toml")) if (root / "patterns").is_dir() else []:
            plugin.patterns += _patterns_from(_load_toml(f), src, plugin.errors)
        if (root / "patterns.toml").exists():
            plugin.patterns += _patterns_from(_load_toml(root / "patterns.toml"), src, plugin.errors)
        if (root / "skills.toml").exists():
            for raw in _load_toml(root / "skills.toml").get("skill", []):
                plugin.skills.append(Skill(id=raw["id"], guidance=list(raw["guidance"]), langs=list(raw.get("langs", [])),
                                           triggers=raw.get("triggers", ""), patterns=list(raw.get("patterns", [])),
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
    except (tomllib.TOMLDecodeError, KeyError, TypeError) as exc:
        plugin.errors.append(f"{src}: {exc}")
    return plugin


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
        plugin = load_plugin(root, builtin)
        if plugin.name in disabled:
            continue
        plugins.append(plugin)
        for f in sorted(root.rglob("*.toml")):
            st = f.stat()
            digest.update(f"{f}:{st.st_size}:{st.st_mtime_ns}".encode())
        if (root / "plugin.py").exists() and (builtin or allow_python):
            hook = _load_python(root / "plugin.py", plugin)
            if hook:
                hooks.append(hook)
        for err in plugin.errors:
            log.warning("plugin %s: %s", plugin.name, err)
    seen: dict[str, Pattern] = {}
    for plugin in plugins:  # plugins do usuário vêm depois e sobrescrevem ids embutidos
        for p in plugin.patterns:
            seen[p.id] = p
    return Bundle(plugins=plugins, patterns=list(seen.values()),
                  skills=[s for p in plugins for s in p.skills], rules=[r for p in plugins for r in p.rules],
                  advice=[a for p in plugins for a in p.advice], fingerprint=digest.hexdigest()[:16], hooks=hooks)


def _load_python(path: Path, plugin: Plugin):
    spec = importlib.util.spec_from_file_location(f"codar_plugin_{plugin.name}", path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # plugin de terceiro: nunca derruba o daemon
        plugin.errors.append(f"plugin.py: {exc}")
        return None
    return getattr(module, "register", None)


def specific_concepts(text: str) -> set[str]:
    return {c for _, cs, _ in analyze(text) for c in cs if c in SPECIFIC}


def keyword_stems(text: str) -> set[str]:
    return {w[:5] for w in words(text) if len(w) >= 4}
