"""Adaptador opcional do Cactus Needle como roteador de ferramentas ([needle] enabled = true).

Medição nesta implementação de referência (x86_64, i7-7500U, Needle 3.0.2): 26–121 s por consulta,
roteamento incorreto em frases em português e estado vazando entre consultas. Por isso o padrão
é o compositor com o próprio SLM + gramática JSON; o Needle fica para dispositivos ARM, onde o
engine nativo é otimizado. Telemetria é sempre desligada e, após o primeiro download, roda offline.
"""

from __future__ import annotations

import os
import re

os.environ["NEEDLE_TELEMETRY"] = "0"
os.environ["DO_NOT_TRACK"] = "1"


class NeedleRouter:
    def __init__(self, min_confidence: float = 0.6) -> None:
        import needle  # noqa: F401  (falha cedo se não estiver instalado)

        self.min_confidence = min_confidence
        self._needle = needle
        os.environ.setdefault("HF_HUB_OFFLINE", "1" if self._cached() else "0")

    @staticmethod
    def _cached() -> bool:
        return os.path.isdir(os.path.expanduser("~/.cache/cactus-needle"))

    def plan(self, intent: str, tools: list[dict]) -> list[dict]:
        funcs = []
        for t in tools:
            params = ", ".join(f"{p}: str = ''" for p in t["params"])
            name = re.sub(r"\W", "_", t["id"])
            ns: dict = {}
            exec(f"def {name}({params}):\n    {t['title']!r}\n    return {{}}", ns)  # noqa: S102 - ids/títulos do banco
            fn = ns[name]
            fn.__doc__ = t["title"]
            funcs.append(self._needle.tool(fn))
        agent = self._needle.Needle(tools=funcs)  # agente novo por consulta: evita vazamento de estado
        result = agent.run(intent)
        if float(result.get("confidence", 0)) < self.min_confidence:
            return []
        by_name = {re.sub(r"\W", "_", t["id"]): t["id"] for t in tools}
        ungrounded = set((result.get("validation") or {}).get("ungrounded", []))
        steps = []
        for call in result.get("function_calls", []):
            pid = by_name.get(call.get("name", ""))
            if not pid:
                continue
            args = {k: str(v) for k, v in (call.get("arguments") or {}).items() if f"{call['name']}.{k}" not in ungrounded}
            steps.append({"pattern": pid, "args": args})
        return steps
