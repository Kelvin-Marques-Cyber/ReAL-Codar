"""Consultor de projeto: sugestões com motivo + opções executáveis (ex.: npm -> pnpm ou Bun).

Fluxo: collect() levanta fatos baratos do projeto (sem rede, profundidade limitada) ->
conselhos declarativos dos plugins (advice.toml) + checagens em Python são avaliados ->
o cliente (CLI, Studio, VS Code) mostra as opções; ao aceitar, apply.apply_option executa
os passos com backup do que for substituído.
"""

from __future__ import annotations

import fnmatch
import json
import os
import shutil
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from codar import langs
from codar._compat import tomllib
from codar.plugin_loader import Advice

IGNORED_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", "target", ".next", ".cache",
                ".codar", "vendor", "bin", "obj", ".idea", ".vscode", ".mypy_cache", ".pytest_cache", "coverage"}
TOOLS = ["node", "npm", "pnpm", "bun", "yarn", "corepack", "deno", "python", "python3", "pip", "uv", "poetry", "git",
         "docker", "go", "cargo", "rustc", "java", "mvn", "gradle", "dotnet", "pwsh", "powershell", "shellcheck", "ruff"]


@dataclass
class Facts:
    root: Path
    files: list[str] = field(default_factory=list)
    langs: Counter = field(default_factory=Counter)
    tools: dict[str, str] = field(default_factory=dict)
    package_json: dict | None = None
    pyproject: dict | None = None
    gitignore: list[str] = field(default_factory=list)
    truncated: bool = False

    def has(self, pattern: str) -> bool:
        if "/" not in pattern and "*" not in pattern:
            return (self.root / pattern).exists()
        return any(fnmatch.fnmatch(f, pattern) for f in self.files)

    def summary(self) -> dict:
        deps = {}
        if self.package_json:
            deps = {**self.package_json.get("dependencies", {}), **self.package_json.get("devDependencies", {})}
        return {"root": str(self.root), "files": len(self.files), "truncated": self.truncated,
                "langs": dict(self.langs.most_common(8)), "tools": sorted(self.tools),
                "node_deps": sorted(deps)[:40], "git": (self.root / ".git").exists()}


def collect(root: Path, max_files: int = 5000, max_depth: int = 4) -> Facts:
    root = root.resolve()
    facts = Facts(root)
    base_depth = len(root.parts)
    for dirpath, dirnames, filenames in os.walk(root):
        depth = len(Path(dirpath).parts) - base_depth
        dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS and not d.startswith(".") or d in (".github",)]
        if depth >= max_depth:
            dirnames[:] = []
        rel_dir = Path(dirpath).relative_to(root)
        for name in filenames:
            rel = (rel_dir / name).as_posix()
            facts.files.append(rel)
            lang = langs.from_path(name)
            if lang:
                facts.langs[lang.id] += 1
            if len(facts.files) >= max_files:
                facts.truncated = True
                break
        if facts.truncated:
            break
    for t in TOOLS:
        p = shutil.which(t)
        if p:
            facts.tools[t] = p
    if (root / "package.json").is_file():
        try:
            facts.package_json = json.loads((root / "package.json").read_text(encoding="utf-8"))
        except (ValueError, OSError):
            facts.package_json = {}
    if (root / "pyproject.toml").is_file():
        try:
            facts.pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
        except (tomllib.TOMLDecodeError, OSError):
            facts.pyproject = {}
    if (root / ".gitignore").is_file():
        facts.gitignore = [ln.strip() for ln in (root / ".gitignore").read_text(encoding="utf-8", errors="ignore").splitlines()]
    return facts


def _json_get(data: Any, dotted: str) -> Any:
    node = data
    for part in _split_key(dotted):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def _json_get_dotted(data: Any, dotted: str) -> Any:
    node = data
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def detect_pm(root: Path) -> str:
    for lock, pm in (("pnpm-lock.yaml", "pnpm"), ("bun.lock", "bun"), ("bun.lockb", "bun"), ("yarn.lock", "yarn")):
        if (root / lock).exists():
            return pm
    return "npm"


def pm_command(root: Path, step: dict) -> str:
    pm = detect_pm(root)
    if "pm_add" in step:
        pkgs = step["pm_add"]
        dev, exact = step.get("dev", False), step.get("exact", False)
        flags = {"npm": (["--save-dev"] if dev else []) + (["--save-exact"] if exact else []),
                 "pnpm": (["-D"] if dev else []) + (["-E"] if exact else []),
                 "yarn": (["-D"] if dev else []) + (["-E"] if exact else []),
                 "bun": (["-d"] if dev else []) + (["--exact"] if exact else [])}[pm]
        verb = "install" if pm == "npm" else "add"
        return " ".join([pm, verb, *flags, pkgs])
    runner = {"npm": "npx --yes", "pnpm": "pnpm exec", "yarn": "yarn", "bun": "bunx"}[pm]
    return f"{runner} {step['pm_exec']}"


def _split_key(dotted: str) -> list[str]:
    """'devDependencies.@biomejs/biome' -> ['devDependencies', '@biomejs/biome'] (pacotes com escopo têm '/')."""
    head, _, rest = dotted.partition(".")
    return [head] + ([rest] if rest else [])


def _load_json(root: Path, name: str) -> dict | None:
    try:
        text = (root / name).read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        return json.loads(text)
    except ValueError:
        import re

        try:  # tsconfig aceita comentários e vírgulas finais
            cleaned = re.sub(r"//[^\n]*|/\*.*?\*/", "", text, flags=re.S)
            return json.loads(re.sub(r",(\s*[}\]])", r"\1", cleaned))
        except ValueError:
            return None


def _ignored(facts: Facts, entry: str) -> bool:
    e = entry.strip("/")
    for ln in facts.gitignore:
        s = ln.strip().strip("/")
        if s and not s.startswith("#") and (s == e or s == f"{e}/" or s == f"/{e}" or fnmatch.fnmatch(e, s)):
            return True
    return False


def evaluate(when: dict, facts: Facts) -> bool:
    for pat in when.get("exists", []):
        if not facts.has(pat):
            return False
    for pat in when.get("missing", []):
        if facts.has(pat):
            return False
    if when.get("any") and not any(facts.has(p) for p in when["any"]):
        return False
    if when.get("lang") and not any(facts.langs.get(lg) for lg in when["lang"]):
        return False
    for tool in when.get("tool_missing", []):
        if tool in facts.tools:
            return False
    for tool in when.get("tool_present", []):
        if tool not in facts.tools:
            return False
    if "json_missing" in when:
        spec = when["json_missing"]
        data = _load_json(facts.root, spec["file"])
        if data is None or any(_json_get(data, k) is not None for k in spec["keys"]):
            return False
    if "toml_missing" in when:
        spec = when["toml_missing"]
        data = facts.pyproject if spec["file"] == "pyproject.toml" else None
        if data and any(_json_get_dotted(data, k) is not None for k in spec["keys"]):
            return False
    if "json_not" in when:
        spec = when["json_not"]
        data = _load_json(facts.root, spec["file"])
        if data is None or _json_get(data, spec["key"]) == spec["value"]:
            return False
    if "lines_missing" in when:
        spec = when["lines_missing"]
        if spec["file"] == ".gitignore":
            if not (facts.root / ".gitignore").exists():
                return False
            if all(_ignored(facts, ln) for ln in spec["lines"]):
                return False
        else:
            try:
                content = (facts.root / spec["file"]).read_text(encoding="utf-8")
            except OSError:
                return False
            if all(ln in content for ln in spec["lines"]):
                return False
    if when.get("not_ignored"):
        if all(_ignored(facts, e) or not facts.has(e) for e in when["not_ignored"]):
            return False
    if when.get("git") is True and not (facts.root / ".git").exists():
        return False
    if when.get("git") is False and (facts.root / ".git").exists():
        return False
    return True


def describe_step(step: dict) -> str:
    if "run" in step:
        extra = f"   (pula se `{step['unless']}` funcionar)" if step.get("unless") else ""
        cond = f"   (só se `{step['if_tool']}` existir)" if step.get("if_tool") else ""
        osf = f" [{step['os']}]" if step.get("os") else ""
        return f"$ {step['run']}{osf}{extra}{cond}"
    if "backup" in step:
        return f"backup de {step['backup']} -> .codar/backup/"
    if "write" in step:
        src = f"padrão {step['pattern']}" if step.get("pattern") else "conteúdo embutido"
        return f"criar {step['write']} ({src}){'' if step.get('if_missing', True) else ' — sobrescreve'}"
    if "append" in step:
        return f"acrescentar em {step['append']}: {', '.join(step.get('lines', []))}"
    if "json_set" in step:
        val = json.dumps(step["value"], ensure_ascii=False) if "value" in step else f"<saída de `{step.get('value_cmd')}`>"
        return f"definir {step['key']} = {val} em {step['json_set']}"
    if "pm_add" in step:
        return f"instalar {'(dev) ' if step.get('dev') else ''}{step['pm_add']} com o gerenciador do projeto"
    if "pm_exec" in step:
        return f"executar `{step['pm_exec']}` (npx/pnpm exec/bunx)"
    if "note" in step:
        return f"nota: {step['note']}"
    return json.dumps(step, ensure_ascii=False)


def render(a: Advice) -> dict:
    return {"id": a.id, "title": a.title, "reason": a.reason, "category": a.category, "impact": a.impact,
            "source": a.source, "options": [{"id": o.id, "label": o.label, "reason": o.reason,
                                             "steps": [describe_step(s) for s in o.steps]} for o in a.options]}


def scan_project(root: Path, advice: list[Advice]) -> dict:
    from codar.advisor.checks import python_checks

    facts = collect(root)
    out = []
    seen = set()
    for a in advice:
        if a.id in seen:
            continue
        try:
            if evaluate(a.when, facts):
                out.append(render(a))
                seen.add(a.id)
        except (KeyError, TypeError):
            continue
    out.extend(python_checks(facts))
    order = {"high": 0, "medium": 1, "low": 2}
    out.sort(key=lambda s: (order.get(s["impact"], 3), s["category"], s["id"]))
    return {"root": str(facts.root), "facts": facts.summary(), "suggestions": out}
