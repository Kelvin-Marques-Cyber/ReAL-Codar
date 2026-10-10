"""Avaliações de edição: substituição completa, sintaxe, duplicação e comportamento.

`--reference` verifica apenas os gabaritos da suíte; não mede um modelo.
O teste executa o candidato em subprocesso, somente em fixtures temporárias.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from importlib import resources
from pathlib import Path

from codar import config
from codar._compat import tomllib
from codar.editing import validate_change
from codar.engine.router import Request, Router
from codar.engine.stage1 import PatternStore
from codar.engine.stage2 import Stage2
from codar.evals.runner import check
from codar.plugin_loader import discover
from codar.studio.edits import hoist_imports


def tasks() -> list[dict]:
    return tomllib.loads(resources.files("codar.evals").joinpath("editing_tasks.toml").read_text(encoding="utf-8"))["task"]


def evaluate(task: dict, body: str, imports: list[str] | None = None, *, complete=True) -> dict:
    if not complete:
        return {"ok": False, "reason": "incomplete", "error": "geração cortada; original preservado"}
    before, after = task.get("before", ""), task.get("after", "")
    original = before + task["selected"] + after
    if task["selected"].endswith("\n") and not body.endswith("\n"):
        body += "\n"
    candidate, _ = hoist_imports(before + body + after, imports or [], "python")
    syntax = validate_change(original, candidate, "candidate.py")
    if syntax["status"] != "ok":
        return {"ok": False, "reason": "validation", "error": syntax["message"]}
    ok, error = check(candidate, task["test"])
    return {"ok": ok, "reason": "passed" if ok else "behavior", "error": error, "code": candidate}


async def run(router: Router | None) -> dict:
    results = []
    for task in tasks():
        start = time.perf_counter()
        if router is None:
            result = evaluate(task, task["reference"])
        else:
            try:
                response = await router.translate(Request(intent=task["intent"], lang="python", lang_explicit=True,
                                                         file="candidate.py", mode="edit", selected=task["selected"],
                                                         before=task.get("before", ""), after=task.get("after", "")))
                result = evaluate(task, response.body, response.imports, complete=response.complete)
            except Exception as exc:
                result = {"ok": False, "reason": "generation", "error": str(exc)}
        results.append({"id": task["id"], **result, "seconds": round(time.perf_counter() - start, 3)})
    return {"mode": "reference" if router is None else "model", "passed": sum(t["ok"] for t in results),
            "total": len(results), "tasks": results}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", action="store_true")
    parser.add_argument("--model")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    stage, store = None, None
    try:
        router = None
        if not args.reference:
            cfg = config.load()
            if args.model:
                cfg["model"].update(name=args.model, path="")
            stage = Stage2(cfg)
            if not stage.configured():
                parser.error("modelo local indisponível; instale o extra llm e baixe um modelo com codar model pull")
            bundle = discover(cfg)
            store = PatternStore(":memory:")
            store.sync(bundle.patterns, bundle.fingerprint)
            router = Router(cfg, store, bundle, stage)
        result = asyncio.run(run(router))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if args.out:
            args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return 0 if result["passed"] == result["total"] else 1
    finally:
        if stage:
            stage.shutdown()
        if store:
            store.close()


if __name__ == "__main__":
    raise SystemExit(main())
