"""Dicas de pacotes enquanto você programa: imports de bibliotecas que não estão instaladas (React, Express, pandas,
OpenCV…), TypeScript ou JSX sem como rodar. Cada dica traz o comando de instalação para o gerenciador do projeto
(bun, pnpm, yarn ou npm; no Python, um ambiente .venv do projeto). Sem rede: só olha arquivos e o que está instalado.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from codar.explicar import PACOTES_PIP

NODE_EMBUTIDOS = {"assert", "async_hooks", "buffer", "child_process", "cluster", "console", "constants", "crypto",
                  "dgram", "diagnostics_channel", "dns", "domain", "events", "fs", "http", "http2", "https", "inspector",
                  "module", "net", "os", "path", "perf_hooks", "process", "punycode", "querystring", "readline", "repl",
                  "stream", "string_decoder", "sys", "timers", "tls", "trace_events", "tty", "url", "util", "v8", "vm",
                  "wasi", "worker_threads", "zlib", "test", "sqlite"}
_JS_IMPORT = re.compile(r"""(?:^|[;\s])(?:import\s+(?:[\w*{}\s,$]+\s+from\s+)?|export\s+[\w*{}\s,$]+\s+from\s+|"""
                        r"""require\s*\(\s*|import\s*\(\s*)["']([^"'\s]+)["']""", re.M)
_PY_IMPORT = re.compile(r"^\s*(?:from\s+([A-Za-z_][\w.]*)\s+import\b|import\s+([A-Za-z_][\w.]*(?:\s*,\s*[A-Za-z_][\w.]*)*))",
                        re.M)
# pacotes que pedem companheiros: (pacote, extensão do arquivo) -> extras
_JUNTO = {"react": ["react-dom"]}
_TIPOS = {"react", "react-dom", "express", "node", "lodash", "cors", "jsonwebtoken", "bcrypt", "pg", "multer"}


@dataclass
class DicaPacote:
    id: str
    titulo: str
    motivo: str
    comando: str
    curta: str  # para a barra de status
    cwd: Path | None = None

    def como_sugestao(self) -> dict:
        """No formato das sugestões do consultor (F8), para a lista do Studio."""
        return {"id": self.id, "title": self.titulo, "reason": self.motivo, "category": "pacotes", "impact": "high",
                "source": "pacotes", "comando": self.comando,
                "cwd": str(self.cwd) if self.cwd else None,
                "options": [{"id": "instalar", "label": "Instalar", "reason": self.motivo,
                             "steps": [f"$ {self.comando}"]}]}


def gerenciador(raiz: Path, caminho: str | None = None) -> str:
    """bun, pnpm, yarn ou npm: pelo lockfile; sem lockfile, o bun se estiver instalado."""
    for trava, pm in (("bun.lock", "bun"), ("bun.lockb", "bun"), ("pnpm-lock.yaml", "pnpm"), ("yarn.lock", "yarn"),
                      ("package-lock.json", "npm")):
        if (raiz / trava).exists():
            return pm
    return "bun" if shutil.which("bun", path=caminho) else "npm"


def _adicionar(pm: str, pacotes: list[str], dev: bool = False) -> str:
    if pm == "npm":
        return f"npm install{' --save-dev' if dev else ''} {' '.join(pacotes)}"
    return f"{pm} add{' -D' if dev else ''} {' '.join(pacotes)}"


def imports_js(codigo: str) -> list[str]:
    """Pacotes de fora importados (sem caminhos relativos e sem módulos do Node/Bun): "@tanstack/query", "react"."""
    pacotes = []
    for alvo in _JS_IMPORT.findall(codigo):
        if alvo.startswith((".", "/", "node:", "bun:", "#", "http:", "https:", "data:", "~", "@/")) or alvo == "bun":
            continue
        nome = "/".join(alvo.split("/")[:2]) if alvo.startswith("@") else alvo.split("/")[0]
        if nome not in NODE_EMBUTIDOS and nome not in pacotes:
            pacotes.append(nome)
    return pacotes


def imports_py(codigo: str) -> list[str]:
    """Módulos de fora importados (sem a biblioteca padrão)."""
    modulos = []
    for de, lista in _PY_IMPORT.findall(codigo):
        for item in ([de] if de else [x.strip().split(" ")[0] for x in lista.split(",")]):
            raiz = item.split(".")[0]
            if raiz and raiz not in sys.stdlib_module_names and raiz != "__future__" and raiz not in modulos:
                modulos.append(raiz)
    return modulos


def _pacote_json(raiz: Path) -> dict | None:
    try:
        return json.loads((raiz / "package.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _instalado_js(raiz: Path, arquivo: Path, pacote: str) -> bool:
    pasta = arquivo.parent
    while True:
        if (pasta / "node_modules" / pacote / "package.json").exists():
            return True
        if pasta == raiz or pasta.parent == pasta:
            return False
        pasta = pasta.parent


def _versao_node(caminho: str | None) -> tuple[int, int]:
    node = shutil.which("node", path=caminho)
    if not node:
        return (0, 0)
    try:
        saida = subprocess.run([node, "--version"], capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.TimeoutExpired):
        return (0, 0)
    m = re.match(r"v(\d+)\.(\d+)", saida.strip())
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


def node_roda_ts(caminho: str | None) -> bool:
    """O Node roda .ts sem configuração a partir da 22.18 (e na 23.6+): só apaga os tipos."""
    v = _versao_node(caminho)
    return v >= (23, 6) or (22, 18) <= v < (23, 0)


def dicas_js(raiz: Path, arquivo: Path, codigo: str, caminho: str | None = None) -> list[DicaPacote]:
    out: list[DicaPacote] = []
    pm = gerenciador(raiz, caminho)
    pacote = _pacote_json(raiz)
    declarados = {}
    if pacote:
        for chave in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
            declarados.update(pacote.get(chave) or {})
    faltam = [p for p in imports_js(codigo) if not _instalado_js(raiz, arquivo, p)]
    ts = arquivo.suffix in (".ts", ".tsx", ".mts", ".cts")
    if faltam and pacote is None:
        out.append(DicaPacote("pacotes:init", "o projeto ainda não tem package.json",
                              "Sem package.json, os pacotes instalados não ficam registrados (e outra pessoa não "
                              "consegue instalar os mesmos).", f"{pm} init -y" if pm != "npm" else "npm init -y",
                              "SEM PACKAGE.JSON"))
    so_instalar = [p for p in faltam if p in declarados]
    if so_instalar:
        out.append(DicaPacote("pacotes:install", f"{', '.join(so_instalar[:3])} está no package.json mas não instalado",
                              "Os pacotes estão declarados, mas a pasta node_modules não tem eles (projeto recém-clonado?).",
                              f"{pm} install", "RODE INSTALL"))
    novos = [p for p in faltam if p not in declarados]
    for p in novos:
        extras = [e for e in _JUNTO.get(p, []) if e not in declarados and not _instalado_js(raiz, arquivo, e)]
        out.append(DicaPacote(f"pacotes:js:{p}", f"{p} não está instalado",
                              f"O arquivo importa {p}, que não está em node_modules.",
                              _adicionar(pm, [p, *extras]), f"{p.upper()} FALTA"))
    if ts:
        usados = [p for p in imports_js(codigo) if p in _TIPOS]
        if re.search(r"""from\s+["'](?:node:)?(?:fs|path|http|os|crypto|child_process|url)["']""", codigo):
            usados.append("node")
        sem_tipos = [p for p in dict.fromkeys(usados) if f"@types/{p}" not in declarados
                     and not _instalado_js(raiz, arquivo, f"@types/{p}") and not (p == "node" and pm == "bun")]
        if sem_tipos:
            tipos = [f"@types/{p}" for p in sem_tipos]
            out.append(DicaPacote("pacotes:tipos", f"faltam os tipos de {', '.join(sem_tipos)}",
                                  "Sem os pacotes @types, o TypeScript não sabe o formato das funções desses pacotes "
                                  "(o editor não ajuda e o tsc reclama).", _adicionar(pm, tipos, dev=True),
                                  "TIPOS FALTAM"))
    jsx = arquivo.suffix in (".jsx", ".tsx")
    if (ts or jsx) and not shutil.which("bun", path=caminho) and (jsx or not node_roda_ts(caminho)):
        out.append(DicaPacote("pacotes:bun", f"nada aqui roda {'JSX' if jsx else 'TypeScript'} direto",
                              f"O Bun roda .ts, .tsx e .jsx sem configurar nada (e instala pacotes bem mais rápido). "
                              f"{'O Node não entende JSX.' if jsx else 'Este Node é antigo para rodar .ts.'}",
                              "curl -fsSL https://bun.sh/install | bash", "INSTALE O BUN"))
    return out


def python_do_projeto(raiz: Path) -> str:
    """O Python que roda o projeto: o do .venv (ou venv) do projeto, se existir; senão o do Studio."""
    for pasta in (".venv", "venv", "env"):
        candidato = raiz / pasta / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        if candidato.exists():
            return str(candidato)
    return sys.executable


def modulos_ausentes(python: str, modulos: list[str]) -> list[str]:
    if not modulos:
        return []
    teste = "import importlib.util,sys;print(' '.join(m for m in sys.argv[1:] if importlib.util.find_spec(m) is None))"
    try:
        r = subprocess.run([python, "-c", teste, *modulos], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return []
    return r.stdout.split() if r.returncode == 0 else []


def dicas_python(raiz: Path, arquivo: Path, codigo: str) -> list[DicaPacote]:
    locais = {p.stem for p in arquivo.parent.glob("*.py")} | {p.stem for p in raiz.glob("*.py")} | \
             {p.name for p in raiz.iterdir() if p.is_dir()} | {p.name for p in arquivo.parent.iterdir() if p.is_dir()}
    modulos = [m for m in imports_py(codigo) if m not in locais]
    python = python_do_projeto(raiz)
    faltam = modulos_ausentes(python, modulos)
    if not faltam:
        return []
    pacotes = [PACOTES_PIP.get(m, m) for m in faltam]
    tem_venv = python != sys.executable
    pip = f"{Path(python).relative_to(raiz) if tem_venv else '.venv/bin/python'} -m pip install {' '.join(pacotes)}"
    comando = pip if tem_venv else f"python3 -m venv .venv && {pip}"
    onde = "no ambiente .venv do projeto" if tem_venv else \
        "num ambiente .venv do projeto (criado agora; o F5 passa a usar ele)"
    nomes = ", ".join(f"{m} ({p})" if p != m else m for m, p in zip(faltam, pacotes))
    return [DicaPacote(f"pacotes:py:{'+'.join(faltam)}", f"{', '.join(faltam)} não está instalado",
                       f"O arquivo importa {nomes}. A instalação vai {onde}.", comando,
                       f"{faltam[0].upper()} FALTA")]


def dicas(raiz: Path, arquivo: Path, codigo: str, lang: str | None, caminho: str | None = None) -> list[DicaPacote]:
    """Dicas de pacotes para o arquivo aberto. `caminho` é o PATH do shell do usuário (para achar bun, node…)."""
    raiz = raiz.resolve()
    arquivo = arquivo.resolve()
    if lang in ("javascript", "typescript"):
        return dicas_js(raiz, arquivo, codigo, caminho)
    if lang == "python":
        return dicas_python(raiz, arquivo, codigo)
    if lang == "dart":
        return dicas_dart(raiz, arquivo, codigo)
    return []


def dicas_dart(raiz: Path, arquivo: Path, codigo: str) -> list[DicaPacote]:
    from codar.dart import project_for

    project = project_for(arquivo, raiz)
    packages = list(dict.fromkeys(re.findall(
        r"^\s*(?:import|export)\s+['\"]package:([a-zA-Z_]\w*)/", codigo, re.M)))
    if not project:
        if not packages:
            return []  # Dart puro com dart:io/dart:convert não precisa de pubspec.
        flutter = "flutter" in packages
        return [DicaPacote("pacotes:pubspec", "o projeto precisa de pubspec.yaml",
                           "Imports package: precisam de um projeto. Crie o projeto numa pasta nova e abra-a no Studio.",
                           "flutter create novo_app" if flutter else "dart create novo_app", "SEM PUBSPEC", raiz)]
    installed = set()
    try:
        cfg = json.loads((project.root / ".dart_tool" / "package_config.json").read_text(encoding="utf-8"))
        installed = {p["name"] for p in cfg.get("packages", [])}
    except (OSError, ValueError, KeyError, TypeError):
        pass
    missing = [p for p in packages if p != project.name and p not in installed]
    declared = [p for p in missing if p in project.dependencies]
    out = []
    if declared:
        out.append(DicaPacote("pacotes:pub:get", f"faltam as dependências: {', '.join(declared)}",
                              "Estão no pubspec.yaml, mas não foram resolvidas em .dart_tool/package_config.json.",
                              f"{project.tool} pub get", "RODE PUB GET", project.root))
    for p in missing:
        if p in declared:
            continue
        if p in ("flutter", "flutter_test", "flutter_driver"):
            # Bibliotecas do SDK não são pacotes publicados no pub.dev.
            out.append(DicaPacote(f"pacotes:sdk:{p}", f"{p} exige o SDK Flutter no pubspec",
                                  f"Declare {p}: com sdk: flutter no pubspec.yaml e resolva as dependências.",
                                  "flutter pub get", "CONFIGURE FLUTTER", project.root))
        else:
            out.append(DicaPacote(f"pacotes:dart:{p}", f"{p} não está instalado",
                                  f"O arquivo importa package:{p}, ausente nas dependências resolvidas.",
                                  f"{project.tool} pub add {p}", f"{p.upper()} FALTA", project.root))
    return out
