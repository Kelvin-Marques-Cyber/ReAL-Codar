"""Procedência de cada resultado: de onde veio o código e o que foi de fato verificado.

Código produzido pela IA nunca é apresentado como testado. Uma variante do banco só conta como testada quando
tem teste executável no patternlint; slots preenchidos a partir do pedido são informados, porque alteram o texto
que o teste exercitou. A sintaxe é conferida pelo mesmo validador estático das gerações, sem executar nada.
"""

from __future__ import annotations

import re

from codar.engine.validation import generation_problem, validator_name

_ORIGIN = {"0": "compiler", "1": "pattern", "2:tools": "composition"}
_LIBRARY = re.compile(r"^(\S+) \[[^;\]]+; versão ([^;\]]*); ([^;\]]*); revisão \w+\]", re.M)


def verification(stage: str, source: str, code: str, lang: str, *, pattern_tested: bool | None = None,
                 slots: dict | None = None, library_context: str = "") -> dict:
    origin = _ORIGIN.get(stage) or ("ai" if stage.startswith("2") else "compiler")
    if source == "imports:only" and stage == "0":
        origin = "compiler"
    model = source.split(":", 1)[1].split("+", 1)[0] if source.startswith("slm:") else None
    validator = validator_name(lang)
    problem = generation_problem(code, lang) if code.strip() else "empty_output"
    syntax = "error" if problem else "lexical" if validator == "lexical" else "ok"
    tested = origin == "pattern" and bool(pattern_tested)
    sources = [source] if origin in ("pattern", "composition") or "+ref:" in source else []
    if origin == "ai":
        sources += [f"{name} {version} ({where})".replace(" ()", "") for name, version, where in
                    _LIBRARY.findall(library_context)][:4]
    out = {"origin": origin, "model": model, "tested": tested, "syntax": syntax, "validator": validator,
           "sources": sources}
    if problem:
        out["reason"] = problem
    out["summary"] = _summary(out, slots or {})
    return out


def _summary(v: dict, slots: dict) -> str:
    who = {"compiler": "compilador determinístico", "pattern": "banco de padrões",
           "composition": "composição de padrões pela IA", "ai": "IA local"}[v["origin"]]
    if v["model"]:
        who += f" ({v['model']})"
    syntax = {"ok": f"sintaxe verificada ({v['validator']})", "lexical": "só delimitadores conferidos",
              "error": f"sintaxe inválida ({v.get('reason', '')})"}[v["syntax"]]
    if v["tested"]:
        tests = "variante testada no patternlint" + (" antes dos slots " + ", ".join(sorted(slots)) if slots else "")
    elif v["origin"] in ("ai", "composition"):
        tests = "não testado: revise antes de usar"
    else:
        tests = "sem execução"
    return f"{who}; {syntax}; {tests}"
