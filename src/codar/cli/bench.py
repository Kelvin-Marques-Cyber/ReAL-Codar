"""`codar bench`: teste de carga do daemon (latência por estágio, concorrência, RAM e detecção de vazamento)."""

from __future__ import annotations

import json
import statistics
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

S0 = ["imprimir olá mundo", "x = 10", "loop de 1 a 100 imprimindo i", "função soma com a e b que retorna a + b",
      "se idade >= 18 imprimir 'adulto' senão imprimir 'menor'", "para cada nome em nomes imprimir nome",
      "lista numeros com 1, 2, 3 e 4", "classe Pessoa com nome, idade e email", "esperar 2 segundos",
      "ler um número inteiro em idade"]
S1 = ["criar uma calculadora", "avaliar expressão matemática com segurança", "busca binária", "algoritmo de dijkstra",
      "validar cpf", "validar cnpj", "remover duplicados", "gerar uuid", "ordenação topológica", "gitignore para node"]
S2 = ["função que converte números romanos para inteiros", "função que agrupa anagramas de uma lista de palavras",
      "função que valida se parênteses estão balanceados", "classe de fila circular com capacidade fixa",
      "função que calcula a distância de hamming entre duas strings"]
LANGS = ["python", "javascript", "go", "rust", "powershell", "bash", "typescript", "java"]


def _pct(xs: list[float], p: float) -> float:
    if not xs:
        return 0.0
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(p / 100 * (len(xs) - 1))))]


def _worker(jobs: list[tuple[str, str]], results: list, errors: list, lock: threading.Lock,
            stages: tuple[int, ...]) -> None:
    from codar.client import Client, RpcError

    with Client.connect() as c:
        for intent, lang in jobs:
            t = time.perf_counter()
            try:
                r = c.translate(intent, lang, stages=stages)
                rtt = (time.perf_counter() - t) * 1000
                with lock:
                    results.append((r["stage"], rtt, r["timings"].get("total_ms", 0.0), r.get("cached", False)))
            except RpcError as exc:
                with lock:
                    errors.append(exc.message)


def run_load(intents: list[str], n: int, concurrency: int, salt: bool,
             stages: tuple[int, ...] = (0, 1)) -> tuple[list, list, float]:
    jobs = []
    for i in range(n):
        intent = intents[i % len(intents)]
        lang = LANGS[(i // len(intents)) % len(LANGS)]
        jobs.append((intent + (f" {i}" if salt and "imprimir" in intent else ""), lang))
    chunks = [jobs[k::concurrency] for k in range(concurrency)]
    results: list = []
    errors: list = []
    lock = threading.Lock()
    t0 = time.perf_counter()
    with ThreadPoolExecutor(concurrency) as pool:
        for f in [pool.submit(_worker, ch, results, errors, lock, stages) for ch in chunks if ch]:
            f.result()
    return results, errors, time.perf_counter() - t0


def cmd_bench(args) -> int:
    from codar.cli.hud import Hud
    from codar.client import Client

    hud = Hud(sys.stdout)
    with Client.connect() as c:
        c.call("cache.clear")
        before = c.stats()["memory"]
    report: dict = {"before": before, "stages": {}}
    print(hud.rule("codar bench"))
    print(hud.kv("ram inicial", f"{before['total_mb']:.0f} MB") + "   " + hud.kv("orçamento", f"{before['budget_mb']} MB"))
    plans = [("S0 compilador", S0, args.n, False), ("S1 padrões", S1, args.n, False), ("cache", S0, args.n, False)]
    if args.stage2 > 0:
        plans.append(("S2 modelo", S2, args.stage2, False))
    for label, intents, n, salt in plans:
        conc = 1 if label.startswith("S2") else args.concurrency
        results, errors, wall = run_load(intents, n, conc, salt, (0, 1, 2) if label.startswith("S2") else (0, 1))
        rtts = [r[1] for r in results]
        server = [r[2] for r in results]
        stages = sorted({r[0] for r in results})
        row = {"n": len(results), "errors": len(errors), "rps": round(len(results) / wall, 1) if wall else 0,
               "p50_ms": round(_pct(rtts, 50), 2), "p95_ms": round(_pct(rtts, 95), 2), "p99_ms": round(_pct(rtts, 99), 2),
               "server_p50_ms": round(statistics.median(server), 3) if server else 0, "stages": stages,
               "cached": sum(1 for r in results if r[3])}
        report["stages"][label] = row
        print(hud.pill(label, "red") + " " + hud.kv("n", str(row["n"])) + "  " + hud.kv("rps", str(row["rps"])) + "  " +
              hud.kv("p50", f"{row['p50_ms']}ms") + "  " + hud.kv("p95", f"{row['p95_ms']}ms") + "  " +
              hud.kv("p99", f"{row['p99_ms']}ms") + "  " + hud.kv("servidor p50", f"{row['server_p50_ms']}ms", "cyan") +
              "  " + hud.kv("estágios", ",".join(stages), "dim") +
              (hud.c(f"  {len(errors)} erros: {errors[0][:60]}", "red") if errors else ""))
    if args.soak:
        samples = []
        with Client.connect() as c:
            c.call("cache.clear")
        step = max(50, args.soak // 10)
        done = 0
        while done < args.soak:
            run_load(S0 + S1, step, args.concurrency, salt=True)
            done += step
            with Client.connect() as c:
                c.call("cache.clear")
                samples.append((done, c.stats()["memory"]["rss_mb"]))
        warm = samples[len(samples) // 3:]
        slope = 0.0
        if len(warm) >= 2:
            xs, ys = [s[0] for s in warm], [s[1] for s in warm]
            mx, my = statistics.mean(xs), statistics.mean(ys)
            den = sum((x - mx) ** 2 for x in xs) or 1
            slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den * 1000
        report["soak"] = {"requests": done, "samples": samples, "mb_per_1k": round(slope, 3)}
        verdict = "estável" if abs(slope) < 2 else "SUSPEITA DE VAZAMENTO"
        print(hud.pill("SOAK", "red") + " " + hud.kv("requisições", str(done)) + "  " +
              hud.kv("inclinação", f"{slope:+.2f} MB/1k req") + "  " +
              hud.c(verdict, "mint" if abs(slope) < 2 else "red", bold=True))
    with Client.connect() as c:
        after = c.stats()["memory"]
    report["after"] = after
    ok = after["peak_mb"] <= after["budget_mb"]
    print(hud.kv("ram final", f"{after['total_mb']:.0f} MB") + "  " + hud.kv("pico", f"{after['peak_mb']:.0f} MB") + "  " +
          hud.bar(after["peak_mb"], after["budget_mb"], 30) + "  " +
          hud.c("DENTRO DO ORÇAMENTO" if ok else "ACIMA DO ORÇAMENTO", "mint" if ok else "red", bold=True))
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if ok else 2
