"""Preferências do Studio entre sessões (tema escolhido, histórico do terminal), em <dados>/studio.json."""

from __future__ import annotations

import json
from typing import Any

from codar import paths


def ler() -> dict[str, Any]:
    try:
        return json.loads((paths.data_dir() / "studio.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def salvar(**valores: Any) -> None:
    arquivo = paths.data_dir() / "studio.json"
    try:
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        arquivo.write_text(json.dumps({**ler(), **valores}, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
