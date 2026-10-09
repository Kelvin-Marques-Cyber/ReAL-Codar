"""Bake-off de modelos: `python -m codar.evals.runner --model qwen2.5-coder-0.5b [--model ...]`.

Cada modelo roda num processo filho (RSS de pico limpo, sem vazamento entre modelos);
cada solução gerada roda em outro subprocesso isolado (-I), com timeout e limite de memória.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from importlib import resources
from pathlib import Path

from codar._compat import tomllib

_SANDBOX = r'''
import os, resource, sys
limite = int(os.environ.get("CODAR_SANDBOX_MB", "768")) << 20  # memória virtual do teste (bibliotecas pedem mais)
try:
    resource.setrlimit(resource.RLIMIT_AS, (limite, limite))
except Exception:
    pass
code = open(sys.argv[1], encoding="utf-8").read()
test = open(sys.argv[2], encoding="utf-8").read()
ns = {"__name__": "candidate"}
exec(compile(code, "candidate.py", "exec"), ns)
exec(compile(test, "test.py", "exec"), ns)
'''


def load_tasks(path: Path | None = None) -> list[dict]:
    if path:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    else:
        data = tomllib.loads(resources.files("codar.evals").joinpath("tasks.toml").read_text(encoding="utf-8"))
    return data["task"]


def check(code: str, test: str, timeout: float = 10.0, python: str | None = None,
          memoria_mb: int = 768) -> tuple[bool, str]:
    """Roda o código e o teste num processo isolado, com limite de memória. `python` escolhe o interpretador (o de
    um ambiente com pandas/OpenCV, por exemplo); bibliotecas numéricas rodam com uma thread só."""
    env = {**os.environ, "CODAR_SANDBOX_MB": str(memoria_mb), "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1",
           "MKL_NUM_THREADS": "1", "MPLBACKEND": "Agg"}
    with tempfile.TemporaryDirectory() as tmp:
        c, t, s = Path(tmp, "c.py"), Path(tmp, "t.py"), Path(tmp, "s.py")
        c.write_text(code, encoding="utf-8")
        t.write_text(test, encoding="utf-8")
        s.write_text(_SANDBOX, encoding="utf-8")
        try:
            r = subprocess.run([python or sys.executable, "-I", str(s), str(c), str(t)], capture_output=True,
                               text=True, timeout=timeout, stdin=subprocess.DEVNULL, cwd=tmp, env=env)
        except subprocess.TimeoutExpired:
            return False, "timeout"
        if r.returncode == 0:
            return True, ""
        err = (r.stderr.strip().splitlines() or ["?"])[-1]
        return False, err[:160]


def _child(args: argparse.Namespace) -> int:
    """Executado no processo filho: carrega um modelo e resolve todas as tarefas."""
    import resource

    from llama_cpp import Llama

    from codar.engine.models import MODELS, STOP, build_prompt, guess_fmt
    from codar.engine.postprocess import clean_generation

    card = MODELS.get(args.model)
    path = Path(args.model_path) if args.model_path else card.local_path()
    fmt = card.fmt if card else guess_fmt(path)
    t0 = time.perf_counter()
    llm = Llama(str(path), n_ctx=args.n_ctx, n_threads=args.threads, n_threads_batch=os.cpu_count(),
                n_batch=args.n_batch, n_ubatch=args.n_batch, use_mmap=False, verbose=False, seed=1)
    load_s = time.perf_counter() - t0
    tasks = load_tasks(Path(args.tasks) if args.tasks else None)
    store = guidance = None
    if args.rag:
        from codar import config
        from codar.engine.stage1 import PatternStore
        from codar.plugin_loader import discover

        bundle = discover(config.load())
        store = PatternStore(":memory:")
        store.sync(bundle.patterns, bundle.fingerprint)
        guidance = next((s.guidance for s in bundle.skills if s.id == "python.base"), None)
    out = []
    for task in tasks:
        reference = None
        if store is not None:
            best = next((m for m in store.search(task["intent"], "python") if m.score >= 0.25 and m.has_lang), None)
            if best:
                reference = (best.pattern.title, "python", best.pattern.code["python"])
        prompt = build_prompt(fmt, "Python", "python", task["intent"], reference=reference, guidance=guidance)
        t1 = time.perf_counter()
        res = llm(prompt, max_tokens=args.max_tokens, temperature=0.0, stop=STOP, repeat_penalty=1.05)
        dt = time.perf_counter() - t1
        code = clean_generation(res["choices"][0]["text"], "python")
        ok, err = check(code, task["test"])
        out.append({"id": task["id"], "ok": ok, "err": err, "s": round(dt, 2), "rag": bool(reference),
                    "tokens": res["usage"]["completion_tokens"], "code": code})
        print(json.dumps({"progress": task["id"], "ok": ok}), file=sys.stderr, flush=True)
    peak_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    print(json.dumps({"model": args.model, "load_s": round(load_s, 2), "peak_rss_mb": round(peak_mb), "tasks": out}))
    return 0


def run_model(model: str, *, threads: int = 2, n_ctx: int = 1024, max_tokens: int = 320,
              tasks: str | None = None, model_path: str | None = None, n_batch: int = 128, rag: bool = False) -> dict:
    cmd = [sys.executable, "-m", "codar.evals.runner", "--child", "--model", model, "--threads", str(threads),
           "--n-ctx", str(n_ctx), "--max-tokens", str(max_tokens), "--n-batch", str(n_batch)] + (["--rag"] if rag else [])
    if tasks:
        cmd += ["--tasks", tasks]
    if model_path:
        cmd += ["--model-path", model_path]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr[-2000:])
    return json.loads(proc.stdout.strip().splitlines()[-1])


def summarize(result: dict) -> dict:
    tasks = result["tasks"]
    passed = sum(t["ok"] for t in tasks)
    toks = sum(t["tokens"] for t in tasks)
    secs = sum(t["s"] for t in tasks)
    return {"model": result["model"] + (" +RAG" if any(t.get("rag") for t in tasks) else ""), "pass": passed, "total": len(tasks), "pass_pct": round(100 * passed / len(tasks)),
            "avg_s": round(secs / len(tasks), 1), "tok_s": round(toks / secs, 1) if secs else 0,
            "peak_rss_mb": result["peak_rss_mb"], "load_s": result["load_s"]}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="codar-eval")
    ap.add_argument("--model", action="append", required=True)
    ap.add_argument("--model-path")
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--n-ctx", type=int, default=1024)
    ap.add_argument("--max-tokens", type=int, default=320)
    ap.add_argument("--n-batch", type=int, default=128)
    ap.add_argument("--rag", action="store_true", help="injeta o padrão mais próximo do banco no prompt")
    ap.add_argument("--tasks")
    ap.add_argument("--child", action="store_true")
    ap.add_argument("--out")
    args = ap.parse_args(argv)
    if args.child:
        args.model = args.model[0]
        return _child(args)
    report = []
    for model in args.model:
        res = run_model(model, threads=args.threads, n_ctx=args.n_ctx, max_tokens=args.max_tokens, tasks=args.tasks,
                        model_path=args.model_path, n_batch=args.n_batch, rag=args.rag)
        s = summarize(res)
        report.append({"summary": s, "result": res})
        print(f"{s['model']:<22} pass {s['pass']:>2}/{s['total']} ({s['pass_pct']:>3}%)  "
              f"{s['avg_s']:>5}s/tarefa  {s['tok_s']:>5} tok/s  pico {s['peak_rss_mb']} MB", flush=True)
    if args.out:
        Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
