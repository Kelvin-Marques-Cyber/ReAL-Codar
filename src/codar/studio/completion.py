"""Completar comandos e caminhos sem executar o texto digitado nem iniciar um shell."""

from __future__ import annotations

import os
import re
import shlex
from pathlib import Path


def _token_start(text: str) -> int:
    quote, escaped, start = "", False, 0
    for i, ch in enumerate(text):
        if escaped:
            escaped = False
        elif ch == "\\" and os.name != "nt" and quote != "'":
            escaped = True
        elif quote:
            if ch == quote:
                quote = ""
        elif ch in "\"'":
            quote = ch
        elif ch.isspace() or ch in "|;&":
            start = i + 1
    return start


def _unquote(token: str) -> str:
    try:
        return shlex.split(token, posix=os.name != "nt")[0].strip('"')
    except (ValueError, IndexError):
        if token.startswith(('"', "'")):
            return token[1:]
        return token.replace("\\ ", " ") if os.name != "nt" else token


def _quote(token: str) -> str:
    if os.name == "nt":
        return '"' + token.replace('"', '\\"') + '"' if re.search(r'[\s&|<>^()]', token) else token
    return shlex.quote(token)


def complete_command(value: str, cursor: int, cwd: Path, env: dict[str, str],
                     history: list[str] = (), project: list[str] = (), limit: int = 80) -> list[tuple[str, int]]:
    """Lista (linha, cursor) para Tab/Shift+Tab, incluindo nomes com espaços e texto após o cursor."""
    left, right = value[:cursor], value[cursor:]
    start = _token_start(left)
    raw = left[start:]
    token = _unquote(raw)
    prefix = left[:start]
    out = []

    def add(replacement: str, space: bool = False):
        suffix = " " if space and not right.startswith(" ") else ""
        text = prefix + replacement + suffix
        candidate = (text + right, len(text))
        if candidate != (value, cursor) and candidate not in out and len(out) < limit:
            out.append(candidate)

    # Sugestões completas do projeto e histórico só no fim do campo.
    if not right and left.strip():
        for cmd in [*reversed(history), *project]:
            if cmd.startswith(left) and cmd != left and (cmd, len(cmd)) not in out:
                out.append((cmd, len(cmd)))
                if len(out) >= limit:
                    return out
    if token.startswith("$") and "/" not in token and "\\" not in token:
        for key in sorted(env):
            if key.startswith(token[1:]) and not key.endswith("="):
                add("$" + key)
        return out
    # PATH: nunca lê o conteúdo dos executáveis.
    command_position = not prefix.strip() or prefix.rstrip().endswith(("|", ";", "&"))
    if command_position and token and not any(ch in token for ch in "/\\~"):
        names = {"cd", "clear", "cls", "exit", "echo", "pwd"}
        for folder in env.get("PATH", "").split(os.pathsep)[:64]:
            if not folder:
                continue
            try:
                with os.scandir(folder) as entries:
                    for i, entry in enumerate(entries):
                        if i >= 10000:
                            break
                        if entry.name.startswith(token) and entry.is_file() and (os.name == "nt" or os.access(entry.path, os.X_OK)):
                            name = entry.name
                            if os.name == "nt" and Path(name).suffix.lower() in (".exe", ".cmd", ".bat", ".com"):
                                name = Path(name).stem
                            names.add(name)
            except OSError:
                continue
        for name in sorted(names):
            if name.startswith(token):
                add(_quote(name), space=True)
    # Caminhos são relativos à sessão ativa, inclusive depois de cd.
    separator = "\\" if os.name == "nt" and "\\" in token else "/"
    split = max(token.rfind("/"), token.rfind("\\") if os.name == "nt" else -1)
    directory, name = (token[:split + 1], token[split + 1:]) if split >= 0 else ("", token)
    if token == "~":
        directory, name = "~/", ""
    expanded = re.sub(r"\$(?:\{(\w+)\}|(\w+))", lambda m: env.get(m[1] or m[2], m[0]), directory)
    folder = cwd / os.path.expanduser(expanded or ".")
    output_directory = os.path.expanduser(expanded) if directory.startswith("~") or "$" in directory else directory
    directories_only = prefix.strip() == "cd"
    try:
        entries = []
        with os.scandir(folder) as scan:
            for i, entry in enumerate(scan):
                if i >= 10000:
                    break
                if not entry.name.startswith(name) or any(ord(c) < 32 for c in entry.name):
                    continue
                if not name.startswith(".") and entry.name.startswith("."):
                    continue
                is_dir = entry.is_dir()
                if directories_only and not is_dir:
                    continue
                entries.append((not is_dir, entry.name, is_dir))
        for _, entry_name, is_dir in sorted(entries)[:limit]:
            add(_quote(output_directory + entry_name + (separator if is_dir else "")), space=not is_dir)
    except OSError:
        pass
    return out
