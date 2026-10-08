"""Registro de modelos GGUF (cartões com URL, SHA-256 oficial, formato de prompt) e montagem de prompts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from codar import paths

HF = "https://huggingface.co"


@dataclass(frozen=True)
class ModelCard:
    key: str
    title: str
    file: str
    url: str
    sha256: str
    size_bytes: int
    fmt: str  # chatml | chatml-nothink
    tier: str  # fast | balanced | quality
    notes: str = ""
    license: str = "apache-2.0"  # segundo o cartão do modelo no Hugging Face

    @property
    def restricted(self) -> bool:
        """Licença com restrição de uso (ex.: qwen-research proíbe uso comercial)."""
        return self.license not in ("apache-2.0", "mit")

    @property
    def size_mb(self) -> int:
        return round(self.size_bytes / 1048576)

    def local_path(self) -> Path:
        return paths.models_dir() / self.file


MODELS: dict[str, ModelCard] = {m.key: m for m in [
    ModelCard(
        "qwen2.5-coder-0.5b", "Qwen2.5-Coder 0.5B Instruct Q4_K_M",
        "qwen2.5-coder-0.5b-instruct-q4_k_m.gguf",
        f"{HF}/Qwen/Qwen2.5-Coder-0.5B-Instruct-GGUF/resolve/main/qwen2.5-coder-0.5b-instruct-q4_k_m.gguf",
        "1d9614638d18024d0fbb36575a15f1302a3adf044df10345688ec4f6e1c4ff32", 491400064, "chatml", "fast",
        "Menor latência; bom para snippets curtos.",
    ),
    ModelCard(
        "qwen3.5-0.8b", "Qwen3.5 0.8B Q4_K_M (unsloth)",
        "Qwen3.5-0.8B-Q4_K_M.gguf",
        f"{HF}/unsloth/Qwen3.5-0.8B-GGUF/resolve/main/Qwen3.5-0.8B-Q4_K_M.gguf",
        "bd258782e35f7f458f8aced1adc053e6e92e89bc735ba3be89d38a06121dc517", 532517120, "chatml-nothink", "fast",
        "Híbrido Gated DeltaNet (mar/2026); KV cache mínimo.",
    ),
    ModelCard(
        "qwen2.5-coder-1.5b", "Qwen2.5-Coder 1.5B Instruct Q4_K_M",
        "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf",
        f"{HF}/Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF/resolve/main/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf",
        "cc324af070c2ecbfd324a30884d2f951a7ff756aba85cb811a6ec436933bb046", 1117320768, "chatml", "balanced",
        "Especialista em código; mais lento em CPUs de 2 núcleos.",
    ),
    ModelCard(
        "qwen3.5-2b", "Qwen3.5 2B Q4_K_M (unsloth)",
        "Qwen3.5-2B-Q4_K_M.gguf",
        f"{HF}/unsloth/Qwen3.5-2B-GGUF/resolve/main/Qwen3.5-2B-Q4_K_M.gguf",
        "aaf42c8b7c3cab2bf3d69c355048d4a0ee9973d48f16c731c0520ee914699223", 1280835840, "chatml-nothink", "quality",
        "Generalista; ~1,9 GB de RSS e lento em CPUs de 2 núcleos.",
    ),
    ModelCard(
        "qwen2.5-coder-3b", "Qwen2.5-Coder 3B Instruct Q4_K_M",
        "qwen2.5-coder-3b-instruct-q4_k_m.gguf",
        f"{HF}/Qwen/Qwen2.5-Coder-3B-Instruct-GGUF/resolve/main/qwen2.5-coder-3b-instruct-q4_k_m.gguf",
        "724fb256bec1ff062b2f65e4569e871ad2e95ab2a3989723d1769c54294730b7", 2104932800, "chatml", "quality",
        "Melhor qualidade de código dentro de 3 GB (~2,2 GB de RSS).",
        license="qwen-research",
    ),
    ModelCard(
        "qwen3.5-4b", "Qwen3.5 4B Q4_K_M (unsloth)",
        "Qwen3.5-4B-Q4_K_M.gguf",
        f"{HF}/unsloth/Qwen3.5-4B-GGUF/resolve/main/Qwen3.5-4B-Q4_K_M.gguf",
        "00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4", 2740937888, "chatml-nothink", "quality",
        "Generalista forte; exige orçamento >= 3,5 GB (fora do teto padrão de 3 GB).",
    ),
    ModelCard(
        "qwen2.5-coder-3b-q3", "Qwen2.5-Coder 3B Instruct Q3_K_M",
        "qwen2.5-coder-3b-instruct-q3_k_m.gguf",
        f"{HF}/Qwen/Qwen2.5-Coder-3B-Instruct-GGUF/resolve/main/qwen2.5-coder-3b-instruct-q3_k_m.gguf",
        "fc3937db7dda9d9ef68ce1f63b5a84ac850ec3c07578461d645e5a88509348e3", 1724178880, "chatml", "quality",
        "3B com quantização Q3 (~1,9 GB); qualidade inferior ao Q4_K_M.",
        license="qwen-research",
    ),
    ModelCard(
        "smollm2-360m", "SmolLM2 360M Instruct Q4_K_M",
        "SmolLM2-360M-Instruct-Q4_K_M.gguf",
        f"{HF}/bartowski/SmolLM2-360M-Instruct-GGUF/resolve/main/SmolLM2-360M-Instruct-Q4_K_M.gguf",
        "2fa3f013dcdd7b99f9b237717fa0b12d75bbb89984cc1274be1471a465bac9c2", 270590880, "chatml", "fast",
        "Para orçamentos de ~1GB; qualidade de código limitada.",
    ),
]}

STOP = ["```", "<|im_end|>", "<|endoftext|>", "<|im_start|>"]

SYSTEM = ("You are a precise code generator. Write {lang} code only: no explanations, no prose, no markdown. "
          "Prefer the standard library, clear names, input validation and proper error handling.")


def resolve_model(cfg_model: dict) -> tuple[ModelCard | None, Path | None]:
    """(cartão, caminho) a partir da seção [model] da configuração."""
    if cfg_model.get("path"):
        p = Path(cfg_model["path"]).expanduser()
        card = next((m for m in MODELS.values() if m.file == p.name), None)
        return card, p
    card = MODELS.get(cfg_model.get("name", ""))
    return card, (card.local_path() if card else None)


def guess_fmt(path: Path) -> str:
    name = path.name.lower()
    return "chatml-nothink" if ("qwen3" in name) else "chatml"


def build_prompt(fmt: str, lang_name: str, fence: str, task: str, *, guidance: list[str] | None = None,
                 reference: tuple[str, str, str] | None = None, context: str = "") -> str:
    """Prompt mínimo com resposta pré-preenchida (abre o bloco de código), o que elimina texto explicativo."""
    system = SYSTEM.format(lang=lang_name)
    if guidance:
        system += "\nRules:\n" + "\n".join(f"- {g}" for g in guidance)
    user = []
    if reference:
        title, ref_fence, code = reference
        user.append(f"Reference pattern ({title}); adapt it, do not copy blindly:\n```{ref_fence}\n{code.strip()}\n```")
    if context:
        user.append(f"Existing code before the cursor:\n```{fence}\n{context.rstrip()}\n```")
    user.append(f"Task: {task.strip()}")
    prompt = (f"<|im_start|>system\n{system}<|im_end|>\n"
              f"<|im_start|>user\n" + "\n\n".join(user) + "<|im_end|>\n<|im_start|>assistant\n")
    if fmt == "chatml-nothink":
        prompt += "<think>\n\n</think>\n\n"
    return prompt + f"```{fence}\n"


LITERAL_SYSTEM = ("You translate pseudo-code (Portuguese or English) into {lang}. Output ONLY the code for exactly what "
                  "the line says. Never add functions, classes, examples, tests, prints, input reading, imports or "
                  "comments that were not asked for. Reuse identifiers exactly as written; when the line does not name a "
                  "variable, derive the name from its own words (\"a lista\" -> lista), never from the examples. Assume every "
                  "variable mentioned already exists: never initialize it with sample values.")


def build_literal_prompt(fmt: str, lang_name: str, fence: str, intent: str, examples: list[tuple[str, str]],
                         context: str = "") -> str:
    """Tradução literal de pseudocódigo: exemplos few-shot (gerados pelo compilador do Estágio 0) ensinam o
    modelo a responder só a linha pedida — é o que impede a "alucinação" de programas inteiros."""
    think = "<think>\n\n</think>\n\n" if fmt == "chatml-nothink" else ""
    parts = [f"<|im_start|>system\n{LITERAL_SYSTEM.format(lang=lang_name)}<|im_end|>\n"]
    for pseudo, code in examples:
        parts.append(f"<|im_start|>user\n{pseudo}<|im_end|>\n<|im_start|>assistant\n{think}```{fence}\n{code}\n```<|im_end|>\n")
    user = intent.strip()
    if context:
        user = f"Code already written (do not repeat it):\n```{fence}\n{context.rstrip()}\n```\n\n{user}"
    parts.append(f"<|im_start|>user\n{user}<|im_end|>\n<|im_start|>assistant\n{think}```{fence}\n")
    return "".join(parts)
