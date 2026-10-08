"""Execução de uma opção aceita pelo usuário: passos com backup e saída em streaming."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Callable

from codar.advisor import _load_json, collect, describe_step, evaluate, pm_command
from codar.advisor.checks import python_checks
from codar.plugin_loader import Bundle

Out = Callable[[str], None]


class ApplyError(RuntimeError):
    pass


def find_option(root: Path, bundle: Bundle, sid: str, oid: str | None) -> tuple[str, dict | None, list[dict]]:
    """(título, opção-render, passos executáveis)."""
    facts = collect(root)
    for a in bundle.advice:
        if a.id == sid:
            if not evaluate(a.when, facts):
                raise ApplyError(f"a sugestão {sid} não se aplica mais a este projeto")
            opt = next((o for o in a.options if o.id == oid), a.options[0] if len(a.options) == 1 and not oid else None)
            if opt is None:
                raise ApplyError(f"opção inválida; escolha uma de: {', '.join(o.id for o in a.options)}")
            return a.title, {"id": opt.id, "label": opt.label}, opt.steps
    for s in python_checks(facts):
        if s["id"] == sid:
            opt = next((o for o in s["options"] if o["id"] == oid), s["options"][0] if not oid else None)
            if opt is None:
                raise ApplyError(f"opção inválida; escolha uma de: {', '.join(o['id'] for o in s['options'])}")
            return s["title"], {"id": opt["id"], "label": opt["label"]}, opt["_steps"]
    raise ApplyError(f"sugestão desconhecida: {sid}")


def apply_steps(root: Path, steps: list[dict], bundle: Bundle, out: Out, dry_run: bool = False) -> None:
    root = root.resolve()
    backup_dir = root / ".codar" / "backup" / time.strftime("%Y%m%d-%H%M%S")
    patterns = {p.id: p for p in bundle.patterns}
    for i, step in enumerate(steps, 1):
        osf = step.get("os")
        if osf and ((osf == "windows") != (os.name == "nt")):
            continue
        out(f"[{i}/{len(steps)}] {describe_step(step)}")
        if dry_run:
            continue
        if "run" in step:
            if step.get("if_tool") and not shutil.which(step["if_tool"]):
                out("    ↷ pulado (ferramenta ausente)")
                continue
            if step.get("unless") and _ok(step["unless"], root):
                out("    ↷ pulado (já satisfeito)")
                continue
            _run(step["run"], root, out, step.get("allow_fail", False))
        elif "pm_add" in step or "pm_exec" in step:
            _run(pm_command(root, step), root, out, step.get("allow_fail", False))
        elif "backup" in step:
            src = root / step["backup"]
            if src.exists():
                backup_dir.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(backup_dir / src.name))
                out(f"    ✓ movido para {backup_dir.relative_to(root)}/{src.name}")
        elif "write" in step:
            dest = root / step["write"]
            if dest.exists() and step.get("if_missing", True):
                out("    ↷ já existe")
                continue
            content = _content(step, patterns, root)
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists():
                backup_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dest, backup_dir / dest.name)
            dest.write_text(content, encoding="utf-8")
            out(f"    ✓ {step['write']} ({len(content.splitlines())} linhas)")
        elif "append" in step:
            dest = root / step["append"]
            existing = dest.read_text(encoding="utf-8").splitlines() if dest.exists() else []
            norm = {ln.strip().strip("/") for ln in existing}
            new = [ln for ln in step.get("lines", []) if ln.strip().strip("/") not in norm]
            if new:
                with dest.open("a", encoding="utf-8") as fh:
                    if existing and existing[-1].strip():
                        fh.write("\n")
                    fh.write("\n".join(new) + "\n")
                out(f"    ✓ +{len(new)} linha(s)")
            else:
                out("    ↷ nada a acrescentar")
        elif "json_set" in step:
            dest = root / step["json_set"]
            data = (_load_json(root, step["json_set"]) if dest.exists() else {}) or {}
            if dest.exists():
                backup_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dest, backup_dir / dest.name)
            value = step.get("value")
            if step.get("value_cmd"):
                raw = subprocess.run(step["value_cmd"], shell=True, cwd=root, capture_output=True, text=True).stdout.strip()
                if not raw:
                    out("    ↷ valor indisponível; pulado")
                    continue
                value = step.get("format", "{}").format(raw)
            node = data
            parts = step["key"].split(".")
            for part in parts[:-1]:
                node = node.setdefault(part, {})
            node[parts[-1]] = value
            dest.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            out(f"    ✓ {step['key']} = {json.dumps(value, ensure_ascii=False)}")
        elif "note" in step:
            out("    ℹ " + step["note"])


def _content(step: dict, patterns: dict, root: Path) -> str:
    if step.get("pattern"):
        p = patterns.get(step["pattern"])
        if p is None:
            raise ApplyError(f"padrão {step['pattern']} não encontrado")
        lang = step.get("lang") or next(iter(p.code))
        text = p.code[lang]
        for slot, default in p.slots.items():
            text = text.replace("{{" + slot + "}}", str(step.get("slots", {}).get(slot, default)))
        return text
    if step.get("from_env_keys"):
        src = root / step["from_env_keys"]
        keys = []
        for ln in src.read_text(encoding="utf-8", errors="ignore").splitlines():
            if "=" in ln and not ln.lstrip().startswith("#"):
                keys.append(ln.split("=", 1)[0].strip() + "=")
        return "\n".join(keys) + "\n"
    return str(step.get("content", ""))


def _ok(cmd: str, root: Path) -> bool:
    try:
        return subprocess.run(cmd, shell=True, cwd=root, capture_output=True, timeout=60).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _run(cmd: str, root: Path, out: Out, allow_fail: bool) -> None:
    proc = subprocess.Popen(cmd, shell=True, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                            encoding="utf-8", errors="replace")
    assert proc.stdout is not None
    for line in proc.stdout:
        out("    " + line.rstrip())
    code = proc.wait()
    if code != 0 and not allow_fail:
        raise ApplyError(f"comando falhou (código {code}): {cmd}")
