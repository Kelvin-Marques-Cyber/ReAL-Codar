"""Configuração: TOML com defaults embutidos + overrides por variável de ambiente."""

from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any

from codar import paths
from codar._compat import tomllib

DEFAULT_TOML = """\
# codar — configuração. Valores omitidos usam o padrão embutido.

[daemon]
endpoint = ""                 # "" = padrão do SO (Unix socket / Named Pipe). Ex.: "tcp://127.0.0.1:7878"
autostart = true              # clientes sobem o daemon sob demanda
max_connections = 64
max_request_kb = 2048          # snapshots antes/depois e propostas, limitadas por arquivo
max_inflight_per_conn = 8
log_level = "info"

[memory]
budget_mb = 3072              # teto rígido de RSS (daemon + runtime do modelo + módulos)
soft_pct = 80                 # acima disso: limpa caches, KV e devolve heap ao SO
hard_pct = 92                 # acima disso: descarrega o modelo
check_interval_s = 2.0
idle_unload_s = 900           # descarrega o modelo após N s sem uso (0 = nunca)
enforce = "auto"              # auto | cgroup | job | soft  (limite duro do SO quando disponível)
malloc_arena_max = 2

[model]
backend = "auto"              # auto | llama_cpp | llama_server | none
name = "qwen2.5-coder-1.5b"   # ver `codar model list`
path = ""                     # caminho explícito para um .gguf (tem precedência sobre name)
n_ctx = 1024
n_batch = 128                 # também limita o buffer de logits (n_vocab x n_ubatch x 4 bytes)
n_ubatch = 0                  # 0 = igual a n_batch
n_threads = 0                 # 0 = núcleos físicos (máx. 4)
n_threads_batch = 0           # 0 = núcleos lógicos (máx. 8)
use_mmap = false              # false: pesos contados uma vez só. Com mmap + repack AVX2 do llama.cpp os
                              # pesos ficam duplicados no RSS (medido: 3B Q4 = 3423 MB com mmap, 2166 MB sem)
use_mlock = false
preload = true                # carrega e aquece o modelo na subida do daemon
warm_langs = ["auto"]         # linguagens que a IA deixa prontas ao carregar (~12 s de CPU cada, em segundo plano,
                              # sem atrasar pedidos). "auto" = as 3 que você mais usa. Ex.: ["python", "powershell"]
max_tokens = 384
temperature = 0.15
top_p = 0.9
top_k = 40
repeat_penalty = 1.08
seed = 42
prompt_lookup = 0             # >0 ativa prompt-lookup decoding (n tokens especulados)
prompt_cache_mb = 64          # cache de estados KV por prefixo (~6 MB cada): alternar prompts não custa 20 s
server_bin = "llama-server"   # backend llama_server (processo isolado)

[router]
stages = [0, 1, 2]
pattern_min_score = 0.6       # confiança mínima para aceitar um padrão do banco (estágio 1)
rag = true                    # injeta o padrão mais próximo + skills no prompt do estágio 2
rag_min_score = 0.25
cache_size = 256
context_lines = 12            # linhas de contexto do editor enviadas ao SLM
max_block_lines = 30          # Ctrl+G com várias linhas selecionadas: tamanho máximo do bloco
max_edit_chars = 12000        # seleção de edição: recusa trechos maiores em vez de cortá-los
max_block_ai_lines = 8        # num bloco, no máximo N linhas vão para a IA (o resto vira TODO): tempo e RAM previsíveis

[audit]
enabled = true
inline_hints = false          # injeta comentários "Dica [ID]: ..." no código gerado
min_severity = "info"         # info | warning | error | critical
disabled = []                 # ids de regras desativadas, ex.: ["PERF010"]

[editing]
preview = true                # revisar edições no Studio antes de aplicar
native_validation = true      # validar com SDKs instalados; nunca executa o código gerado

# Regras próprias (regex, custo zero):
# [[audit.rules]]
# id = "ORG001"
# langs = ["python"]
# pattern = 'print\\('
# severity = "info"
# category = "style"
# message = "Prefira logging a print em código de produção."

[plugins]
disabled = []                 # nomes de plugins a ignorar
allow_python = false          # permite plugin.py (código executável) em plugins do usuário

[needle]
enabled = false               # roteador semântico com Cactus Needle (pip install cactus-needle)
min_confidence = 0.6

[hook]
lang = ""                     # linguagem padrão do hook global ("" = detectar pelo título da janela)
restore_clipboard = true
"""

DEFAULTS: dict[str, Any] = tomllib.loads(DEFAULT_TOML)

_ENV = {
    "CODAR_BUDGET_MB": ("memory", "budget_mb", int),
    "CODAR_THREADS": ("model", "n_threads", int),
    "CODAR_BACKEND": ("model", "backend", str),
    "CODAR_N_CTX": ("model", "n_ctx", int),
}


def _merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load(path: Path | None = None) -> dict[str, Any]:
    path = path or paths.config_file()
    cfg = copy.deepcopy(DEFAULTS)
    if path.is_file():
        with path.open("rb") as fh:
            cfg = _merge(cfg, tomllib.load(fh))
    for var, (section, key, cast) in _ENV.items():
        if (val := os.environ.get(var)) is not None:
            cfg[section][key] = cast(val)
    if model := os.environ.get("CODAR_MODEL"):
        if model.endswith(".gguf"):
            cfg["model"]["path"] = model
        else:
            cfg["model"]["name"] = model
    if ep := os.environ.get("CODAR_ENDPOINT"):
        cfg["daemon"]["endpoint"] = ep
    return cfg


def write_default(path: Path | None = None, force: bool = False) -> Path:
    path = path or paths.config_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    if force or not path.exists():
        path.write_text(DEFAULT_TOML, encoding="utf-8")
    return path


def set_value(dotted: str, raw: str, path: Path | None = None) -> None:
    """Altera uma chave simples no config.toml preservando o restante do arquivo."""
    import re

    path = path or write_default()
    section, key = dotted.split(".", 1)
    text = path.read_text(encoding="utf-8")
    try:
        tomllib.loads(f"v = {raw}")
        literal = raw  # já é um literal TOML válido (número, bool, lista, string entre aspas)
    except tomllib.TOMLDecodeError:
        literal = '"' + raw.replace("\\", "\\\\").replace('"', '\\"') + '"'
    sec_re = re.compile(rf"^\[{re.escape(section)}\]\s*$", re.M)
    m = sec_re.search(text)
    if not m:
        text = text.rstrip() + f"\n\n[{section}]\n{key} = {literal}\n"
    else:
        nxt = re.compile(r"^\[", re.M).search(text, m.end())
        end = nxt.start() if nxt else len(text)
        body = text[m.end():end]
        key_re = re.compile(rf"^{re.escape(key)}\s*=.*$", re.M)
        if key_re.search(body):
            body = key_re.sub(lambda _: f"{key} = {literal}", body, count=1)
        else:
            body = f"\n{key} = {literal}" + body
        text = text[: m.end()] + body + text[end:]
    tomllib.loads(text)  # valida antes de gravar
    path.write_text(text, encoding="utf-8")
