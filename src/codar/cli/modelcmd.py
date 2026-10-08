"""`codar model`: list | pull | use | info | load | unload | eval."""

from __future__ import annotations

import hashlib
import json
import sys
import time
import urllib.request
from pathlib import Path

from codar import config
from codar.engine.models import MODELS, ModelCard


def register(sub) -> None:
    p = sub.add_parser("model", aliases=["m"], help="modelos: list | pull | use | info | load | unload | eval")
    p.add_argument("action", choices=["list", "pull", "use", "info", "load", "unload", "eval"])
    p.add_argument("key", nargs="*")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_model)


def _hud():
    from codar.cli.hud import Hud

    return Hud(sys.stdout)


def cmd_model(args) -> int:
    hud = _hud()
    cfg = config.load()
    if args.action == "list":
        return list_models(cfg, hud, args.json)
    if args.action == "pull":
        keys = args.key or [cfg["model"]["name"]]
        return max(pull(k, hud) for k in keys)
    if args.action == "use":
        if not args.key or args.key[0] not in MODELS and not args.key[0].endswith(".gguf"):
            print(f"modelos conhecidos: {', '.join(MODELS)}", file=sys.stderr)
            return 1
        key = args.key[0]
        if key.endswith(".gguf"):
            config.set_value("model.path", json.dumps(str(Path(key).expanduser().resolve())))
        else:
            config.set_value("model.name", json.dumps(key))
            config.set_value("model.path", '""')
        print(hud.pill("MODELO", "mint") + " " + hud.c(key, "green") + hud.c("  (reinicie o daemon: codar restart)", "dim"))
        return 0
    if args.action == "eval":
        from codar.evals.runner import main as eval_main

        keys = args.key or [cfg["model"]["name"]]
        return eval_main([x for k in keys for x in ("--model", k)])
    from codar.client import Client

    with Client.connect() as c:
        method = {"info": "model.info", "load": "model.load", "unload": "model.unload"}[args.action]
        res = c.call(method)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


def list_models(cfg: dict, hud, as_json: bool) -> int:
    from codar.engine.gguf import GGUFError, estimate, read_gguf

    budget = int(cfg["memory"]["budget_mb"])
    hard = budget * float(cfg["memory"]["hard_pct"]) / 100
    n_ctx = int(cfg["model"]["n_ctx"])
    ub = int(cfg["model"].get("n_ubatch") or cfg["model"]["n_batch"])
    rows = []
    for card in MODELS.values():
        local = card.local_path().is_file()
        est = None
        if local:
            try:
                est = round(estimate(read_gguf(card.local_path()), n_ctx, ub, use_mmap=bool(cfg["model"].get("use_mmap"))).total_mb)
            except (GGUFError, OSError):
                est = None
        rows.append({"key": card.key, "title": card.title, "size_mb": card.size_mb, "tier": card.tier, "local": local,
                     "estimate_mb": est, "fits": None if est is None else est <= hard,
                     "active": card.key == cfg["model"]["name"] and not cfg["model"].get("path"), "notes": card.notes,
                     "license": card.license})
    if as_json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0
    print(hud.rule("modelos"))
    for r in rows:
        mark = hud.c("●", "mint") if r["active"] else hud.c("○", "dim")
        state = hud.c("LOCAL", "green") if r["local"] else hud.c("—", "dim")
        fit = "" if r["estimate_mb"] is None else (hud.c(f"~{r['estimate_mb']} MB ✓", "mint") if r["fits"]
                                                    else hud.c(f"~{r['estimate_mb']} MB ✗ excede", "red"))
        print(f" {mark} {hud.c(r['key']):<32} {hud.c(r['tier'].upper(), 'cyan'):<20} {hud.c(str(r['size_mb']) + ' MB', 'dim'):<18} "
              f"{state:<16} {fit}")
        lic = r["license"]
        print("     " + hud.c(r["notes"], "dim") + "  " + (hud.c(f"licença {lic}: uso não comercial", "orange")
                                                    if lic not in ("apache-2.0", "mit") else hud.c(f"licença {lic}", "dim")))
    print(hud.c(f"orçamento {budget} MB · teto duro {hard:.0f} MB · n_ctx {n_ctx} · n_ubatch {ub}", "dim"))
    return 0


def pull(key: str, hud) -> int:
    card = MODELS.get(key)
    if card is None:
        print(f"modelo desconhecido: {key} (conhecidos: {', '.join(MODELS)})", file=sys.stderr)
        return 1
    if card.restricted:
        print(hud.pill("LICENÇA", "orange") + " " + hud.c(
            f"{card.title} usa a licença {card.license}, que não permite uso comercial. Para uso comercial, prefira "
            "qwen2.5-coder-1.5b (Apache-2.0).", "orange"), file=sys.stderr)
    dest = card.local_path()
    if dest.is_file() and dest.stat().st_size == card.size_bytes:
        print(hud.pill("OK", "mint") + " " + hud.c(f"{card.title} já baixado em {dest}", "green"))
        return 0
    try:
        download(card, dest, hud)
    except (OSError, ValueError) as exc:
        print(hud.pill("FALHA", "red") + f" {exc}", file=sys.stderr)
        return 1
    print(hud.pill("MODELO PRONTO", "mint") + " " + hud.c(str(dest), "green"))
    return 0


def download(card: ModelCard, dest: Path, hud) -> None:
    """Download retomável (.part + Range) com verificação do SHA-256 oficial do Hugging Face."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")
    have = part.stat().st_size if part.exists() else 0
    req = urllib.request.Request(card.url, headers={"User-Agent": "codar/0.1"})
    if have:
        req.add_header("Range", f"bytes={have}-")
    sha = hashlib.sha256()
    if have:
        with part.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                sha.update(chunk)
    with urllib.request.urlopen(req, timeout=60) as resp:
        if have and resp.status != 206:  # servidor ignorou o Range: recomeça
            have, sha = 0, hashlib.sha256()
            part.unlink(missing_ok=True)
        total = card.size_bytes
        done = have
        t0 = time.monotonic()
        last = 0.0
        with part.open("ab") as out:
            while chunk := resp.read(1 << 20):
                out.write(chunk)
                sha.update(chunk)
                done += len(chunk)
                now = time.monotonic()
                if now - last > 0.2 or done == total:
                    last = now
                    speed = (done - have) / max(now - t0, 1e-3) / 1048576
                    line = (hud.pill("PULL", "red") + " " + hud.c(card.key, "green") + " " + hud.bar(done, total, 32) +
                            " " + hud.c(f"{done / 1048576:6.0f}/{total / 1048576:.0f} MB  {speed:5.1f} MB/s", "mint"))
                    sys.stdout.write("\r" + line)
                    sys.stdout.flush()
    sys.stdout.write("\n")
    if part.stat().st_size != card.size_bytes:
        raise ValueError(f"tamanho inesperado ({part.stat().st_size} bytes); rode o pull de novo para retomar")
    if sha.hexdigest() != card.sha256:
        part.unlink(missing_ok=True)
        raise ValueError("SHA-256 não confere com o oficial; arquivo descartado")
    part.replace(dest)
