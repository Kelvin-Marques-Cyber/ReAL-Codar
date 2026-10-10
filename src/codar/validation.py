"""Validação sem executar o programa gerado; comandos de projeto são ações explícitas."""

from __future__ import annotations

import ast
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

from codar import langs, toolchains
from codar.project import Project, read_source, safe_path


def run_command(command: list[str], root: Path, timeout: int = 60) -> dict:
    """Saída limitada, stdin fechado, sem shell e com término dos filhos no timeout."""
    if not command or any(not isinstance(arg, str) or "\0" in arg for arg in command):
        raise ValueError("comando inválido")
    with tempfile.TemporaryFile() as output:
        try:
            proc = subprocess.Popen(command, cwd=root, stdin=subprocess.DEVNULL, stdout=output, stderr=output,
                                    env=toolchains.environment(), start_new_session=os.name != "nt")
        except OSError as exc:
            return {"command": command, "status": "skipped", "message": str(exc), "exit_code": None}
        try:
            code = proc.wait(timeout=max(1, min(timeout, 300)))
            status = "ok" if code == 0 else "error"
        except subprocess.TimeoutExpired:
            if os.name != "nt":
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            else:
                try:
                    subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, timeout=10)
                except (OSError, subprocess.TimeoutExpired):
                    pass
                proc.kill()
            proc.wait()
            code, status = None, "error"
        size = output.tell()
        output.seek(max(0, size - 32000))
        message = output.read().decode("utf-8", errors="replace")
        if code is None:
            message = "tempo limite excedido\n" + message
        return {"command": command, "status": status, "message": message, "exit_code": code,
                "output_truncated": size > 32000}


def validate_text(text: str, file: str, *, native: bool = True, lang: str | None = None) -> dict:
    language = langs.try_resolve(lang) if lang else langs.from_path(file)
    name = language.id if language else ""
    result = {"path": file, "lang": name, "status": "skipped", "validator": "", "message": "sem validador disponível"}
    try:
        if name == "python":
            ast.parse(text, filename=file)
            result.update(status="ok", validator="ast", message="")
            return result
        if Path(file).suffix.lower() == ".json":
            json.loads(text)
            result.update(status="ok", validator="json", message="")
            return result
        if Path(file).suffix.lower() == ".toml":
            from codar._compat import tomllib

            tomllib.loads(text)
            result.update(status="ok", validator="toml", message="")
            return result
    except (SyntaxError, ValueError) as exc:
        result.update(status="error", validator="ast" if name == "python" else Path(file).suffix[1:],
                      message=str(exc), line=getattr(exc, "lineno", 0), col=getattr(exc, "offset", 0))
        return result

    command, binary = None, None
    if native:
        if name == "dart":
            binary = toolchains.executable("dart")
            command = [binary, "format", "--output=none", "{file}"] if binary else None
        elif name == "powershell":
            binary = toolchains.executable("powershell")
            script = ("$tokens=$null; $errors=$null; "
                      "[System.Management.Automation.Language.Parser]::ParseFile($args[0],[ref]$tokens,[ref]$errors) | Out-Null; "
                      "if ($errors.Count) { $errors | ForEach-Object { '{0}:{1}: {2}' -f "
                      "$_.Extent.StartLineNumber,$_.Extent.StartColumnNumber,$_.Message }; exit 1 }")
            command = [binary, "-NoLogo", "-NoProfile", "-NonInteractive", "-File", "{parser}", "{file}"] if binary else None
        elif name in ("javascript", "bash", "ruby", "php"):
            binary = shutil.which("bash", path=toolchains.environment()["PATH"]) if name == "bash" else toolchains.executable(name)
            flag = {"javascript": "--check", "bash": "-n", "ruby": "-c", "php": "-l"}[name]
            command = [binary, flag, "{file}"] if binary else None
    if command:
        with tempfile.TemporaryDirectory(prefix="codar-check-") as directory:
            root = Path(directory)
            target = root / ("candidate" + (Path(file).suffix or ".txt"))
            target.write_text(text, encoding="utf-8")
            parser = root / "parse.ps1"
            if name == "powershell":
                parser.write_text(script, encoding="utf-8")
            checked = run_command([arg.replace("{file}", str(target)).replace("{parser}", str(parser)) for arg in command], root, 30)
            result.update(status=checked["status"], validator=Path(binary).name, message=checked["message"])
            return result
    # Gramáticas opcionais já usadas pelo banco de padrões. Não há download nem execução de código.
    if name and name not in ("powershell", "r", "julia"):
        try:
            from codar.evals.patternlint import _first_error, _parser

            parser = _parser(name)
            if parser:
                tree = parser.parse(text.encode())
                error = _first_error(tree.root_node)
                result.update(status="error" if error else "ok", validator="tree-sitter", message="")
                if error:
                    result.update(line=error.start_point[0] + 1, col=error.start_point[1] + 1,
                                  message=f"sintaxe inválida na linha {error.start_point[0] + 1}")
        except (ImportError, ValueError, AttributeError):
            pass
    return result


def default_command(project: Project, action: str, file: str | None = None) -> list[str] | None:
    if action in project.commands:
        if any("{file}" in arg for arg in project.commands[action]) and not file:
            raise ValueError(f"commands.{action} precisa de um arquivo")
        absolute = str(safe_path(project.root, file)) if file else ""
        return [arg.replace("{file}", absolute).replace("{root}", str(project.root)) for arg in project.commands[action]]
    root = project.root
    if (root / "pubspec.yaml").exists():
        pubspec = (root / "pubspec.yaml").read_text(encoding="utf-8")
        flutter = bool(re.search(r"(?m)^\s*flutter\s*:", pubspec))
        binary = toolchains.executable("flutter" if flutter else "dart")
        if action in ("test", "analyze"):
            return [binary or ("flutter" if flutter else "dart"), action]
        if action == "format":
            return [toolchains.executable("dart") or "dart", "format", str(root)]
    if (root / "pyproject.toml").exists() or (root / "pytest.ini").exists():
        if action == "test":
            from codar.advisor.pacotes import python_do_projeto

            return [python_do_projeto(root) or sys.executable, "-m", "pytest"]
    if (root / "package.json").exists() and action in ("test", "format", "analyze"):
        scripts = json.loads((root / "package.json").read_text(encoding="utf-8")).get("scripts", {})
        key = "lint" if action == "analyze" else action
        if key in scripts:
            return ["npm", "run", key]
    if file and action == "run":
        language = langs.from_path(file)
        if language and language.runner:
            return [arg.replace("{file}", str(safe_path(root, file))) for arg in language.runner]
    return None


def check_project(root: str | Path, files: list[str] | None = None, *, actions: list[str] | None = None,
                  native: bool = True, timeout: int = 60) -> dict:
    project = Project.load(root)
    if files is not None and (not isinstance(files, list) or any(not isinstance(name, str) for name in files)):
        raise ValueError("files deve ser uma lista de caminhos relativos")
    results = []
    for name in files or project.files():
        try:
            results.append(validate_text(read_source(safe_path(project.root, name)), name, native=native))
        except (OSError, ValueError, UnicodeError) as exc:
            results.append({"path": name, "status": "error", "message": str(exc)})
    commands = []
    for action in actions or []:
        command = default_command(project, action)
        commands.append(run_command(command, project.root, timeout) if command else
                        {"status": "skipped", "command": [], "message": f"configure commands.{action} em codar.toml"})
    return {"root": str(project.root), "files": results, "commands": commands,
            "ok": not any(r["status"] == "error" for r in results + commands),
            "skipped": sum(r["status"] == "skipped" for r in results + commands)}
