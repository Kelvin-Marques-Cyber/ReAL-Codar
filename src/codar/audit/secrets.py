"""Detecção de segredos: assinaturas conhecidas + atribuições suspeitas + entropia de Shannon."""

from __future__ import annotations

import math
import re

SIGNATURES: list[tuple[str, str, re.Pattern[str]]] = [
    ("SEC101", "Chave de acesso AWS exposta", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("SEC102", "Token do GitHub exposto", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{60,})\b")),
    ("SEC103", "Token do GitLab exposto", re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}\b")),
    ("SEC104", "Token do Slack exposto", re.compile(r"\bxox[abposr]-[A-Za-z0-9-]{10,}\b")),
    ("SEC105", "Chave secreta do Stripe exposta", re.compile(r"\b[sr]k_live_[A-Za-z0-9]{20,}\b")),
    ("SEC106", "Chave de API do Google exposta", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("SEC107", "Chave de API de LLM exposta", re.compile(r"\bsk-(?:ant-|proj-)?[A-Za-z0-9_-]{24,}\b")),
    ("SEC108", "Chave privada embutida no código", re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY")),
    ("SEC109", "JWT literal no código", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
    ("SEC110", "String de conexão com usuário e senha embutidos",
     re.compile(r"\b[a-z][a-z0-9+.-]{1,15}://[^\s:/@'\"{}$]{1,64}:[^\s@/'\"{}$]{3,128}@[^\s'\"]+", re.I)),
]

_ASSIGN = re.compile(
    r"""(?ix)\b(?P<name>[\w.-]*(?:pass(?:word|wd)?|pwd|senha|secret|segredo|token|api[_-]?key|apikey|
    access[_-]?key|private[_-]?key|client[_-]?secret|auth)[\w.-]*)\b["']?\s*(?::=|=>|=|:)\s*
    (?P<q>["'`])(?P<value>[^"'`\n]{4,})(?P=q)""",
)
_PLACEHOLDER = re.compile(
    r"(?i)^(?:changeme|change_me|password|senha|secret|token|example|exemplo|test|teste|dummy|xxx+|\*+|\.+|"
    r"<[^>]*>|\$\{[^}]*\}|\{\{[^}]*\}\}|%[sd]|your[_-].*|seu[_-].*|sua[_-].*|placeholder|redacted|null|none|todo)$"
)


def entropy(s: str) -> float:
    if not s:
        return 0.0
    freq = {c: s.count(c) for c in set(s)}
    return -sum(f / len(s) * math.log2(f / len(s)) for f in freq.values())


def scan(code: str) -> list[tuple[str, str, int, int, str]]:
    """[(id, mensagem, linha, coluna, trecho)]"""
    out = []
    for rid, msg, rx in SIGNATURES:
        for m in rx.finditer(code):
            line = code.count("\n", 0, m.start()) + 1
            col = m.start() - (code.rfind("\n", 0, m.start()) + 1) + 1
            out.append((rid, msg, line, col, m.group()[:12] + "…"))
    for m in _ASSIGN.finditer(code):
        value = m.group("value").strip()
        if _PLACEHOLDER.match(value) or value.startswith(("os.environ", "process.env", "$env:", "getenv")):
            continue
        if re.search(r"(?i)\b(?:environ|getenv|process\.env|config|settings|input|read)", value):
            continue
        if len(value) < 6 and entropy(value) < 2.0:
            continue
        line = code.count("\n", 0, m.start()) + 1
        col = m.start() - (code.rfind("\n", 0, m.start()) + 1) + 1
        out.append(("SEC100", f"Segredo atribuído diretamente em '{m.group('name')}'", line, col, m.group("name")))
    return out
