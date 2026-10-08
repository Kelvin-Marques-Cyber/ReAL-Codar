"""Checagens do consultor que não cabem em regras declarativas."""

from __future__ import annotations

import subprocess

from codar.advisor import Facts
from codar.audit import secrets

_TEXT_EXT = {".py", ".js", ".ts", ".go", ".rs", ".java", ".cs", ".php", ".rb", ".ps1", ".sh", ".env", ".json", ".yml",
             ".yaml", ".toml", ".ini", ".cfg", ".conf", ".properties", ".xml", ".tf", ".lua"}


def python_checks(facts: Facts) -> list[dict]:
    out: list[dict] = []
    out += _secrets(facts)
    out += _env_tracked(facts)
    out += _docker_user(facts)
    return out


def _secrets(facts: Facts) -> list[dict]:
    hits: dict[str, list[str]] = {}
    scanned = 0
    for rel in facts.files:
        if scanned >= 400:
            break
        p = facts.root / rel
        if p.suffix.lower() not in _TEXT_EXT and not p.name.startswith(".env"):
            continue
        try:
            if p.stat().st_size > 256_000:
                continue
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        scanned += 1
        for rid, msg, line, _col, _frag in secrets.scan(text):
            if rid != "SEC100":  # só assinaturas fortes, sem a heurística genérica
                hits.setdefault(rel, []).append(f"{msg} (linha {line})")
    if not hits:
        return []
    files = sorted(hits)
    steps_ignore = [{"append": ".gitignore", "lines": [f for f in files if f.startswith(".env")] or [".env"]}]
    return [{
        "id": "security.secrets", "title": f"Segredos expostos em {len(files)} arquivo(s)", "category": "security",
        "impact": "high", "source": "core",
        "reason": "Encontrei credenciais com formato reconhecível: " + "; ".join(
            f"{f}: {hits[f][0]}" for f in files[:5]) + ". Quem tem acesso ao repositório pode usá-las.",
        "options": [
            {"id": "ignore", "label": "Tirar do git e ignorar", "reason": "Evita novos commits com o segredo.",
             "steps": ["acrescentar arquivos .env* ao .gitignore", "$ git rm --cached <arquivo> (manual)",
                       "nota: rotacione (revogue e gere de novo) cada credencial exposta"], "_steps": steps_ignore},
            {"id": "manual", "label": "Só me mostre os arquivos", "reason": "Revisão manual.",
             "steps": [f"nota: {f}" for f in files[:20]], "_steps": [{"note": f} for f in files[:20]]},
        ]}]


def _env_tracked(facts: Facts) -> list[dict]:
    if not (facts.root / ".git").exists() or not (facts.root / ".env").exists() or "git" not in facts.tools:
        return []
    r = subprocess.run(["git", "ls-files", "--error-unmatch", ".env"], cwd=facts.root, capture_output=True)
    if r.returncode != 0:
        return []
    steps = [{"run": "git rm --cached .env"}, {"append": ".gitignore", "lines": [".env"]},
             {"write": ".env.example", "from_env_keys": ".env"}]
    return [{"id": "security.env_tracked", "title": ".env versionado no git", "category": "security", "impact": "high",
             "source": "core", "reason": "O .env está no histórico do git; qualquer clone recebe suas variáveis.",
             "options": [{"id": "untrack", "label": "Parar de versionar e criar .env.example",
                          "reason": "Mantém o arquivo local, remove do índice e documenta as chaves sem valores.",
                          "steps": ["$ git rm --cached .env", "acrescentar .env ao .gitignore",
                                    "criar .env.example só com os nomes das variáveis"], "_steps": steps}]}]


def _docker_user(facts: Facts) -> list[dict]:
    df = facts.root / "Dockerfile"
    if not df.is_file():
        return []
    text = df.read_text(encoding="utf-8", errors="ignore")
    if any(ln.strip().upper().startswith("USER ") for ln in text.splitlines()):
        return []
    return [{"id": "docker.root", "title": "Container roda como root", "category": "security", "impact": "medium",
             "source": "core", "reason": "Sem a instrução USER, uma falha no app dá root dentro do container.",
             "options": [{"id": "manual", "label": "Mostrar o trecho a adicionar",
                          "reason": "Criar um usuário sem privilégios antes do CMD.",
                          "steps": ["nota: RUN useradd --system --uid 10001 app", "nota: USER app"],
                          "_steps": [{"note": "Adicione antes do CMD:\n  RUN useradd --system --uid 10001 app\n  USER app"}]}]}]
