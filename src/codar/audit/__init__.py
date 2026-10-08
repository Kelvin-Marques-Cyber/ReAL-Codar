"""Auditor estático (custo zero de IA): segredos, segurança, desempenho e memória.

Camadas: assinaturas de segredos (todas as linguagens) -> AST (Python) -> regras regex dos
plugins, avaliadas sobre o código com comentários (e opcionalmente strings) mascarados e,
quando a regra pede, só dentro de corpos de laço.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from codar import langs
from codar.audit import python_rules, secrets
from codar.audit.lexer import loop_lines, mask
from codar.plugin_loader import Rule

SEVERITY = {"info": 0, "warning": 1, "error": 2, "critical": 3}


@dataclass
class Finding:
    id: str
    severity: str
    category: str
    message: str
    line: int
    col: int = 1
    suggestion: str = ""
    snippet: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class _Compiled:
    rule: Rule
    rx: re.Pattern[str]
    langs: frozenset[str]


class Auditor:
    def __init__(self, acfg: dict, rules: list[Rule]) -> None:
        self.disabled = set(acfg.get("disabled", []))
        self.min_sev = SEVERITY.get(acfg.get("min_severity", "info"), 0)
        custom = [Rule(source="config", **{k: v for k, v in r.items() if k in Rule.__dataclass_fields__})
                  for r in acfg.get("rules", [])]
        self.rules: list[_Compiled] = []
        for r in [*rules, *custom]:
            flags = re.M | (re.I if "i" in r.flags else 0) | (re.S if "s" in r.flags else 0)
            try:
                self.rules.append(_Compiled(r, re.compile(r.pattern, flags), frozenset(r.langs)))
            except re.error:
                continue

    def describe(self) -> list[dict]:
        builtin = [{"id": "SEC100-SEC110", "category": "secret", "langs": ["*"], "source": "core"},
                   {"id": "PY000-PY030", "category": "python-ast", "langs": ["python"], "source": "core"}]
        return builtin + [{"id": c.rule.id, "severity": c.rule.severity, "category": c.rule.category,
                           "langs": sorted(c.langs) or ["*"], "message": c.rule.message, "source": c.rule.source,
                           "enabled": c.rule.id not in self.disabled} for c in self.rules]

    def audit(self, code: str, lang: str) -> list[Finding]:
        lang = langs.try_resolve(lang).id if langs.try_resolve(lang) else lang
        found: list[Finding] = []
        src_lines = code.split("\n")

        def snippet(line: int) -> str:
            return src_lines[line - 1].strip()[:120] if 0 < line <= len(src_lines) else ""

        for rid, msg, line, col, frag in secrets.scan(code):
            found.append(Finding(rid, "critical", "secret", msg, line, col,
                                 "mova para variável de ambiente ou cofre de segredos (.env fora do git)", frag))
        if lang == "python":
            for rid, sev, cat, msg, line, sug in python_rules.check(code):
                found.append(Finding(rid, sev, cat, msg, line, 1, sug, snippet(line)))
        masked_code = mask(code, lang)
        masked_all = None
        loops = None
        for c in self.rules:
            if c.langs and lang not in c.langs:
                continue
            r = c.rule
            if r.scope == "nostrings":
                masked_all = masked_all if masked_all is not None else mask(code, lang, strings=True)
                text = masked_all
            elif r.scope == "all":
                text = code
            else:
                text = masked_code
            for m in c.rx.finditer(text):
                line = text.count("\n", 0, m.start()) + 1
                if r.in_loop:
                    loops = loops if loops is not None else loop_lines(code, lang)
                    if line not in loops:
                        continue
                col = m.start() - (text.rfind("\n", 0, m.start()) + 1) + 1
                found.append(Finding(r.id, r.severity, r.category, r.message, line, col, r.suggestion, snippet(line)))
        seen: set[tuple[str, int]] = set()
        secret_lines: set[int] = set()
        out = []
        # assinaturas específicas (SEC101+) vencem a regra AST (PY017), que vence a heurística genérica (SEC100)
        rank = {"PY017": 1, "SEC100": 2}
        for f in sorted(found, key=lambda f: (f.line, -SEVERITY.get(f.severity, 0), rank.get(f.id, 0), f.id)):
            if f.id in self.disabled or SEVERITY.get(f.severity, 0) < self.min_sev or (f.id, f.line) in seen:
                continue
            if f.category == "secret":
                if f.line in secret_lines:
                    continue
                secret_lines.add(f.line)
            seen.add((f.id, f.line))
            out.append(f)
        return out

    def annotate(self, code: str, findings: list[Finding], lang: str) -> str:
        """Injeta comentários "Dica [ID]" acima da instrução afetada, sem alterar a semântica."""
        if not findings:
            return code
        info = langs.try_resolve(lang)
        lines = code.split("\n")
        starts = python_rules.statement_starts(code) if lang == "python" else {}
        by_line: dict[int, list[Finding]] = {}
        for f in findings:
            target = starts.get(f.line, f.line)
            by_line.setdefault(max(1, min(target, len(lines))), []).append(f)
        out: list[str] = []
        for no, text in enumerate(lines, 1):
            for f in by_line.get(no, []):
                indent = text[: len(text) - len(text.lstrip())]
                tip = f"Dica [{f.id}]: {f.message}" + (f" — {f.suggestion}" if f.suggestion else "")
                out.append(indent + (langs.comment_line(info, tip) if info else f"# {tip}"))
            out.append(text)
        return "\n".join(out)
