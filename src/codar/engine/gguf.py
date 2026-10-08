"""Leitor mínimo de metadados GGUF (sem dependências) e estimativa de RSS antes de carregar o modelo."""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_SCALARS = {0: "<B", 1: "<b", 2: "<H", 3: "<h", 4: "<I", 5: "<i", 6: "<f", 7: "<?", 10: "<Q", 11: "<q", 12: "<d"}
_STRING, _ARRAY = 8, 9


class GGUFError(ValueError):
    pass


class _Cursor:
    """Leitura por offsets sobre mmap: pular 250 mil strings do tokenizer custa ~50 ms, não ~1,3 s."""

    def __init__(self, buf) -> None:
        self.buf = buf
        self.off = 0

    def take(self, fmt: str) -> Any:
        try:
            value = struct.unpack_from(fmt, self.buf, self.off)[0]
        except struct.error as exc:
            raise GGUFError("arquivo truncado") from exc
        self.off += struct.calcsize(fmt)
        return value

    def string(self) -> str:
        n = self.take("<Q")
        if n > 1 << 24:
            raise GGUFError("string grande demais")
        s = bytes(self.buf[self.off:self.off + n]).decode("utf-8", "replace")
        self.off += n
        return s

    def value(self, vtype: int) -> Any:
        if vtype in _SCALARS:
            return self.take(_SCALARS[vtype])
        if vtype == _STRING:
            return self.string()
        if vtype == _ARRAY:
            itype = self.take("<I")
            count = self.take("<Q")
            if itype in _SCALARS:
                self.off += struct.calcsize(_SCALARS[itype]) * count
            elif itype == _STRING:
                unpack, buf, off = struct.unpack_from, self.buf, self.off
                for _ in range(count):
                    off += 8 + unpack("<Q", buf, off)[0]
                self.off = off
            else:
                for _ in range(count):
                    self.value(itype)
            return ("array", count)
        raise GGUFError(f"tipo de valor desconhecido {vtype}")


@dataclass
class GGUFInfo:
    path: Path
    version: int
    tensors: int
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def arch(self) -> str:
        return str(self.meta.get("general.architecture", "?"))

    def get(self, key: str, default: Any = None) -> Any:
        return self.meta.get(f"{self.arch}.{key}", default)

    @property
    def n_vocab(self) -> int:
        tokens = self.meta.get("tokenizer.ggml.tokens")
        if isinstance(tokens, tuple):
            return int(tokens[1])
        return int(self.get("vocab_size", 32000))

    @property
    def n_layer(self) -> int:
        return int(self.get("block_count", 0))

    @property
    def n_embd(self) -> int:
        return int(self.get("embedding_length", 0))

    @property
    def n_head(self) -> int:
        v = self.get("attention.head_count", 1)
        return int(max(v) if isinstance(v, list) else v)

    @property
    def n_head_kv(self) -> int:
        v = self.get("attention.head_count_kv", self.n_head)
        if isinstance(v, list):
            v = max(v)
        return int(v) if v else self.n_head

    @property
    def head_dim(self) -> int:
        return int(self.get("attention.key_length", 0) or (self.n_embd // max(self.n_head, 1)))

    @property
    def attn_layers(self) -> int:
        """Camadas com KV cache. Arquiteturas híbridas (DeltaNet/Mamba) só têm KV nas camadas de atenção."""
        interval = self.get("full_attention_interval")
        if interval:
            return max(1, self.n_layer // int(interval))
        return self.n_layer

    def describe(self) -> dict[str, Any]:
        return {"arch": self.arch, "name": self.meta.get("general.name", ""), "layers": self.n_layer,
                "attn_layers": self.attn_layers, "embd": self.n_embd, "heads": self.n_head,
                "heads_kv": self.n_head_kv, "head_dim": self.head_dim, "vocab": self.n_vocab,
                "ctx_train": self.get("context_length"), "file_type": self.meta.get("general.file_type")}


def read_gguf(path: Path | str) -> GGUFInfo:
    import mmap

    path = Path(path)
    with path.open("rb") as fh, mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ) as mm:
        if mm[:4] != b"GGUF":
            raise GGUFError(f"{path.name} não é um arquivo GGUF")
        cur = _Cursor(mm)
        cur.off = 4
        version = cur.take("<I")
        if version < 2:
            raise GGUFError(f"GGUF v{version} não suportado")
        n_tensors = cur.take("<Q")
        n_kv = cur.take("<Q")
        info = GGUFInfo(path, version, n_tensors)
        for _ in range(n_kv):
            key = cur.string()
            info.meta[key] = cur.value(cur.take("<I"))
    return info


@dataclass
class MemoryEstimate:
    weights_mb: float
    kv_mb: float
    compute_mb: float
    runtime_mb: float

    @property
    def total_mb(self) -> float:
        return self.weights_mb + self.kv_mb + self.compute_mb + self.runtime_mb

    def as_dict(self) -> dict[str, float]:
        return {"weights_mb": round(self.weights_mb), "kv_mb": round(self.kv_mb, 1),
                "compute_mb": round(self.compute_mb), "runtime_mb": round(self.runtime_mb),
                "total_mb": round(self.total_mb)}


def estimate(info: GGUFInfo, n_ctx: int, n_ubatch: int, kv_bytes: int = 2, runtime_mb: float = 90 + 64,
             use_mmap: bool = False) -> MemoryEstimate:
    """RSS esperado. Calibrado com medições reais (Qwen2.5-Coder 0.5B: estimado 650 MB, medido 671 MB).

    pesos  = arquivo inteiro (mmap; todas as páginas são tocadas a cada token)
    kv     = n_ctx * camadas_de_atenção * heads_kv * head_dim * (K+V) * bytes
    compute= logits do ubatch (n_vocab * n_ubatch * fp32) + ativações (~6 * n_embd * n_ubatch * fp32)
    """
    weights = info.path.stat().st_size / 1048576
    if use_mmap:  # páginas do arquivo + cópia reempacotada (repack AVX2) dos tensores Q4/Q8: medido ~1,65x
        weights *= 1.65
    kv = n_ctx * info.attn_layers * info.n_head_kv * info.head_dim * 2 * kv_bytes / 1048576
    compute = (info.n_vocab * n_ubatch * 4 + 6 * info.n_embd * n_ubatch * 4) / 1048576
    if info.attn_layers < info.n_layer:  # híbridos: estados recorrentes + buffers de convolução
        compute = compute * 1.1 + 64
    return MemoryEstimate(weights, kv, compute, runtime_mb)
