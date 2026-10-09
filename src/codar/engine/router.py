"""Roteador de 3 estágios: compilador de intenções -> banco de padrões -> SLM (compositor/gerador).

O SLM só roda quando os estágios determinísticos não resolvem; mesmo assim ele primeiro
tenta *compor* ferramentas verificadas do banco antes de escrever código do zero.
"""

from __future__ import annotations

import asyncio
import dataclasses
import hashlib
import re
import threading
import textwrap
import time
from collections import OrderedDict, deque
from dataclasses import asdict, dataclass, field
from typing import Any, Callable

from codar import langs
from codar.audit import Auditor
from codar.engine import emmet, ir
from codar.engine.emit import EmitError, emit, emit_else
from functools import lru_cache

from codar.engine.models import STOP, build_literal_prompt, build_prompt
from codar.engine.postprocess import (clean_generation, detect_indent_unit, join_imports, prune_imports,
                                     prune_sample_data, reindent, split_imports)
from codar.engine.stage0 import Stage0, clean_intent, extract_lang_hint
from codar.engine.stage1 import Match, PatternStore, compose, extract_slots
from codar.engine.stage2 import Cancelled, ModelUnavailable, Stage2, plan_prompt, plan_schema
from codar.plugin_loader import Bundle, Pattern, Skill, _norm
from codar.textutil import analyze, fold

_IDENT = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")
_TASK_WORDS = frozenset("""
funcao funcoes function functions classe classes class programa program script api apis servidor server sistema
system app aplicacao aplicativo site pagina bot crud algoritmo calculadora jogo game modulo module biblioteca library
componente component endpoint conectar conexao connect implementar implemente implement gerar gere crie criar create
build construa construir escreva escrever write desenvolva develop projeto project cliente client servico service
""".split())
_CODE_TOKEN = re.compile(r"[=<>+*/%()\[\]{}]|\b\d+\b|\w_\w|\b[a-z]+[A-Z]\w*")
# (frase mostrada ao modelo, pseudocódigo que o compilador traduz). O último ensina a nomear pelo que a frase diz
# e a usar a coleção citada sem inventar dados: "quantos itens" -> itens, nunca a lista de outro exemplo.
_EXAMPLES = [("x é igual a 10", "x é igual a 10"),
             ("se total maior que 100 imprimir 'caro'", "se total maior que 100 imprimir 'caro'"),
             ("para cada nome em nomes imprimir nome", "para cada nome em nomes imprimir nome"),
             ("contar quantos pedidos existem", "total_pedidos recebe o tamanho de pedidos")]


_ANAPHORA = re.compile(r"\b(?:d|n)?(?:os|as)\s+(?:dois|duas|tres)\b|\b(?:ambos|ambas|esses|essas|estes|estas|este|esta|"
                       r"esse|essa|isso|isto|ele|ela|eles|elas|deles|delas|dele|dela)\b|\b(?:d|n)?(?:o|a|os|as)\s+"
                       r"(?:resultado|lista|valor|valores|variavel|texto|numero|numeros|soma|total|media|produto|item|"
                       r"itens|nome|nomes|anterior|atual)\b|\b(?:the two|both|it|them|these|those|the result|the list|"
                       r"the value|the total)\b")


def refers_to_context(intent: str, known: set[str]) -> bool:
    """A frase fala do código que já existe ("some os dois números", "imprima o resultado", "x + y")?"""
    if not known:
        return False
    folded = fold(intent)
    words = set(re.findall(r"[A-Za-z_]\w*", intent))
    return bool(_ANAPHORA.search(folded)) or bool(words & known)


def is_pseudocode(intent: str) -> bool:
    """Pseudocódigo = uma instrução a traduzir (não um pedido de funcionalidade nova)."""
    words = fold(intent).split()
    if not words or len(words) > 14 or any(w.strip(".,:;!?") in _TASK_WORDS for w in words):
        return False
    return bool(_CODE_TOKEN.search(intent)) or len(words) <= 8


@lru_cache(maxsize=32)
def literal_examples(lang: str) -> tuple[tuple[str, str], ...]:
    """Exemplos few-shot do modo literal, gerados pelo próprio compilador na linguagem-alvo."""
    stage0 = Stage0()
    out = []
    for shown, pseudo in _EXAMPLES:
        parsed = stage0.parse(pseudo, {"total", "nomes", "pedidos"})
        if parsed is None:
            continue
        try:
            _imports, body = emit(parsed.nodes, lang)
        except EmitError:
            continue
        out.append((shown, body))
    return tuple(out)


@dataclass
class Request:
    intent: str
    lang: str | None = None
    lang_explicit: bool = False
    file: str | None = None
    before: str = ""
    indent: str = ""
    indent_unit: str | None = None
    stages: tuple[int, ...] = (0, 1, 2)
    audit: bool = True
    hints: bool = False
    mode: str = "auto"  # auto | line | block

    @classmethod
    def from_params(cls, p: dict[str, Any], default_lang: str | None = None) -> Request:
        ctx = p.get("context") or {}
        opts = p.get("options") or {}
        stages = tuple(int(s) for s in opts.get("stages", (0, 1, 2)))
        return cls(intent=str(p.get("intent", "")), lang=p.get("lang") or default_lang,
                   lang_explicit=bool(p.get("lang")), file=ctx.get("file"), before=str(ctx.get("before", ""))[-6000:],
                   indent=str(ctx.get("indent", "")), indent_unit=ctx.get("indent_unit"), stages=stages,
                   audit=bool(opts.get("audit", True)), hints=bool(opts.get("hints", False)),
                   mode=str(opts.get("mode", "auto")))


@dataclass
class Result:
    code: str
    body: str
    imports: list[str]
    lang: str
    stage: str  # 0 | 1 | 2:tools | 2:adapt | 2:gen
    source: str
    confidence: float = 1.0
    timings: dict[str, float] = field(default_factory=dict)
    findings: list[dict] = field(default_factory=list)
    annotated: str | None = None
    slots: dict[str, str] = field(default_factory=dict)
    candidates: list[dict] = field(default_factory=list)
    file_suggestion: dict | None = None
    cached: bool = False
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return asdict(self)


class TranslateError(RuntimeError):
    def __init__(self, message: str, candidates: list[dict] | None = None):
        super().__init__(message)
        self.candidates = candidates or []


class Metrics:
    def __init__(self) -> None:
        self.count: dict[str, int] = {}
        self.lat: dict[str, deque] = {}
        self.history: deque = deque(maxlen=200)
        self._lock = threading.Lock()

    def record(self, res: Result, intent: str) -> None:
        key = "cache" if res.cached else res.stage
        with self._lock:
            self.count[key] = self.count.get(key, 0) + 1
            self.lat.setdefault(key, deque(maxlen=512)).append(res.timings.get("total_ms", 0.0))
            self.history.appendleft({"ts": time.time(), "intent": intent[:200], "lang": res.lang, "stage": res.stage,
                                     "source": res.source, "ms": res.timings.get("total_ms", 0.0),
                                     "preview": res.code[:400], "findings": len(res.findings), "cached": res.cached})

    def snapshot(self) -> dict:
        with self._lock:
            out = {}
            for k, values in self.lat.items():
                xs = sorted(values)
                if xs:
                    out[k] = {"n": self.count.get(k, 0), "p50_ms": round(xs[len(xs) // 2], 2),
                              "p95_ms": round(xs[min(len(xs) - 1, int(len(xs) * 0.95))], 2)}
            return out


class Router:
    def __init__(self, cfg: dict, store: PatternStore, bundle: Bundle, stage2: Stage2 | None = None,
                 needle: Any | None = None) -> None:
        self.cfg = cfg
        self.rcfg = cfg["router"]
        self.store = store
        self.bundle = bundle
        self.stage0 = Stage0()
        self.stage2 = stage2
        self.needle = needle
        self.auditor = Auditor(cfg.get("audit", {}), bundle.rules)
        self.skills: list[Skill] = bundle.skills
        self.metrics = Metrics()
        self._cache: OrderedDict[str, Result] = OrderedDict()
        self._cache_lock = threading.Lock()
        self.default_lang = "python"

    # ------------------------------------------------------------------ cache
    def _key(self, req: Request, lang: str, intent: str) -> str:
        ctx = hashlib.sha1(req.before[-400:].encode()).hexdigest()[:8] if 2 in req.stages else ""
        return "|".join([fold(intent), lang, req.indent, str(req.indent_unit), ",".join(map(str, req.stages)),
                         str(req.hints), str(req.audit), req.mode, ctx])

    def cache_get(self, key: str) -> Result | None:
        with self._cache_lock:
            res = self._cache.get(key)
            if res is not None:
                self._cache.move_to_end(key)
            return res

    def cache_put(self, key: str, res: Result) -> None:
        with self._cache_lock:
            self._cache[key] = res
            self._cache.move_to_end(key)
            while len(self._cache) > int(self.rcfg.get("cache_size", 256)):
                self._cache.popitem(last=False)

    def clear_cache(self) -> int:
        with self._cache_lock:
            n = len(self._cache)
            self._cache.clear()
            return n

    # ------------------------------------------------------------------ API principal
    async def translate(self, req: Request, on_token: Callable[[str], None] | None = None,
                        cancel: threading.Event | None = None) -> Result:
        t0 = time.perf_counter()
        timings: dict[str, float] = {}
        intent = clean_intent(req.intent) if "\n" not in req.intent.strip() else req.intent.strip("\n")
        intent, hinted = extract_lang_hint(intent)
        lang = self._resolve_lang(req, hinted)
        key = self._key(req, lang.id, intent)
        if (hit := self.cache_get(key)) is not None:
            res = Result(**{**hit.as_dict(), "cached": True})
            res.timings = {**hit.timings, "total_ms": round((time.perf_counter() - t0) * 1000, 3)}
            self.metrics.record(res, intent)
            return res
        known = set(_IDENT.findall(req.before[-3000:]))
        if req.mode == "block" or (req.mode == "auto" and "\n" in intent.strip()):
            res = await self._compile_block(intent, lang, req, known, timings, cancel)
        else:
            res = await self._translate_line(intent, lang, req, known, timings, on_token, cancel)
        self._finish(res, req, timings, t0)
        if res.stage != "2:gen" or not res.notes:
            self.cache_put(key, res)
        self.metrics.record(res, intent)
        return res

    def _resolve_lang(self, req: Request, hinted: str | None) -> langs.Lang:
        if req.lang_explicit and req.lang:
            return langs.resolve(req.lang)
        if hinted:
            return langs.resolve(hinted)
        if req.lang:
            return langs.resolve(req.lang)
        return langs.from_path(req.file) or langs.resolve(self.default_lang)

    def _finish(self, res: Result, req: Request, timings: dict[str, float], t0: float) -> None:
        unit = req.indent_unit
        if unit is not None or req.indent:
            src = detect_indent_unit(res.body)
            res.body = reindent(res.body, unit if unit is not None else src, req.indent, src)
        res.code = join_imports(res.imports, res.body.strip("\n") if not req.indent else res.body, res.lang)
        if req.audit and self.cfg.get("audit", {}).get("enabled", True):
            ta = time.perf_counter()
            # audita sem a indentação da linha do editor: "    total = 0" sozinho é erro de sintaxe em Python
            margin = min((len(ln) - len(ln.lstrip()) for ln in res.body.split("\n") if ln.strip()), default=0)
            audited = join_imports(res.imports, textwrap.dedent(res.body).strip("\n"), res.lang) if margin else res.code
            offset = len(join_imports(res.imports, "", res.lang).split("\n")) + 1 if res.imports else 0
            prefixo = 0
            if res.source == "stage0:else" and res.lang == "python":  # "else:" sozinho não é Python válido
                audited, prefixo = "if True:\n    pass\n" + audited, 2
            findings = [dataclasses.replace(f, line=f.line - prefixo) for f in self.auditor.audit(audited, res.lang)
                        if f.line > prefixo]
            res.findings = [{**f.as_dict(), "body_line": f.line - offset,
                             **({"col": f.col + margin} if margin and f.line > offset else {})} for f in findings]
            if req.hints or self.cfg.get("audit", {}).get("inline_hints"):
                res.annotated = self.auditor.annotate(res.code, findings, res.lang)
            timings["audit_ms"] = round((time.perf_counter() - ta) * 1000, 3)
        timings["total_ms"] = round((time.perf_counter() - t0) * 1000, 3)
        res.timings = timings

    # ------------------------------------------------------------------ uma linha
    @staticmethod
    def _emmet(intent: str, lang: langs.Lang, req: Request) -> Result | None:
        """Abreviações Emmet em HTML/CSS (e em JSX/TSX, só as inequívocas): "ul>li*3", "df+jcc"."""
        text = intent.strip()
        jsx_file = (req.file or "").endswith((".jsx", ".tsx"))
        if lang.id == "html":
            code, kind = emmet.expand(text), "html"
        elif lang.id == "css":
            code, kind = emmet.expand_css(text), "css"
        elif lang.id in ("javascript", "typescript") and jsx_file and emmet.jsx_candidate(text):
            code, kind = emmet.expand(text, jsx=True), "jsx"
        else:
            return None
        if code is None:
            return None
        return Result(code="", body=code, imports=[], lang=lang.id, stage="0", source=f"emmet:{kind}")

    async def _translate_line(self, intent: str, lang: langs.Lang, req: Request, known: set[str],
                              timings: dict[str, float], on_token, cancel) -> Result:
        if 0 in req.stages and (res := self._emmet(intent, lang, req)) is not None:
            return res
        if 0 in req.stages:
            t = time.perf_counter()
            parsed = self.stage0.parse(intent, known)
            res = None
            if parsed and len(parsed.nodes) == 1 and isinstance(parsed.nodes[0], ir.Else):
                try:  # "senão …" sozinho: continuação do if que está acima no arquivo
                    imports, body = emit_else(parsed.nodes[0], lang.id)
                except EmitError as exc:
                    raise TranslateError(str(exc)) from exc  # sem IA: ela inventaria um if inteiro
                return Result(code="", body=body, imports=imports, lang=lang.id, stage="0", source="stage0:else")
            if parsed:
                try:
                    imports, body = emit(parsed.nodes, lang.id)
                    res = Result(code="", body=body, imports=imports, lang=lang.id, stage="0",
                                 source=f"stage0:{parsed.construct}", confidence=parsed.confidence)
                except EmitError as exc:
                    timings["stage0_skip"] = 1
                    del exc
            timings["stage0_ms"] = round((time.perf_counter() - t) * 1000, 3)
            if res:
                return res
        t = time.perf_counter()
        matches = self.store.search(intent, lang.id) if (1 in req.stages or 2 in req.stages) else []
        timings["stage1_ms"] = round((time.perf_counter() - t) * 1000, 3)
        cands = [m.as_dict() for m in matches[:5]]
        accept = float(self.rcfg.get("pattern_min_score", 0.6))
        best = next((m for m in matches if m.has_lang or m.pattern.kind == "file"), None)
        pseudo = is_pseudocode(intent)
        contextual = pseudo and refers_to_context(intent, known)
        if pseudo:  # instrução sobre o código: só aceita um padrão se ele explicar praticamente a frase toda
            accept_ok = best is not None and best.score >= 0.85 and best.coverage >= 0.8 and not contextual
        else:
            accept_ok = best is not None and best.score >= accept and best.coverage >= 0.6
        if 1 in req.stages and best and accept_ok:
            fill_lang = lang.id if lang.id in best.pattern.code else next(iter(best.pattern.code))
            filled = self.store.fill(best.pattern, fill_lang, intent)
            self.store.hit(best.pattern.id)
            return self._from_pattern(best, filled, lang, cands, "1")
        if 2 not in req.stages or self.stage2 is None:
            raise TranslateError("nenhum estágio determinístico resolveu a intenção e o Estágio 2 está desligado", cands)
        if not self.stage2.configured():
            raise TranslateError(f"Estágio 2 indisponível: {self.stage2.load_error or 'modelo não configurado'} "
                                 "(rode `codar model pull`)", cands)
        rag_min = float(self.rcfg.get("rag_min_score", 0.25))
        useful = [m for m in matches if m.score >= rag_min]
        loop = asyncio.get_running_loop()
        if pseudo:  # pseudocódigo nunca vira padrão por similaridade parcial: tradução literal
            return await self._literal(intent, lang, req, timings, on_token, cancel, cands)
            return await self._literal(intent, lang, req, timings, on_token, cancel, cands)
        # 2a: compositor — a IA escolhe ferramentas verificadas em vez de escrever código
        if useful:
            t = time.perf_counter()
            steps = await self._plan(intent, lang, useful, cancel)
            timings["plan_ms"] = round((time.perf_counter() - t) * 1000, 1)
            if steps:
                coverage = self._plan_coverage(intent, [p for p, _ in steps])
                if coverage >= 0.7 and all(lang.id in p.code for p, _ in steps):
                    filled = compose(self.store, steps, lang.id, intent)
                    for p, _ in steps:
                        self.store.hit(p.id)
                    res = Result(code="", body=filled.body, imports=filled.imports, lang=lang.id, stage="2:tools",
                                 source="+".join(p.id for p, _ in steps), confidence=round(coverage, 2),
                                 slots=filled.slots, candidates=cands)
                    res.notes.append(f"composto a partir de {len(steps)} ferramenta(s) do banco")
                    return res
                ref_pattern = steps[0][0]
            else:
                ref_pattern = useful[0].pattern
        else:
            ref_pattern = None
        # 2b: gerador ancorado (RAG + skills)
        reference = self._reference(ref_pattern, lang.id) if ref_pattern else None
        guidance = self._guidance(intent, lang.id)
        context = "\n".join(req.before.rstrip("\n").split("\n")[-int(self.rcfg.get("context_lines", 12)):]) \
            if req.before.strip() else ""
        fmt = self.stage2.fmt

        def builder(level: int) -> str:
            ref = reference if level < 2 else None
            if ref and level == 1:
                ref = (ref[0], ref[1], "\n".join(ref[2].split("\n")[:30]))
            return build_prompt(fmt, lang.name, lang.fence, intent, guidance=guidance if level < 3 else guidance[:2],
                                reference=ref, context=context if level == 0 else "")

        t = time.perf_counter()
        try:
            gen = await asyncio.wrap_future(self.stage2.submit(self.stage2.generate, builder, on_token=on_token,
                                                               cancel=cancel), loop=loop)
        except ModelUnavailable as exc:
            raise TranslateError(str(exc), cands) from exc
        timings["stage2_ms"] = round((time.perf_counter() - t) * 1000, 1)
        timings["tokens"] = gen.tokens
        code = prune_imports(clean_generation(gen.text, lang.id), lang.id)
        imports, body = split_imports(code, lang.id)
        res = Result(code="", body=body, imports=imports, lang=lang.id, stage="2:adapt" if reference else "2:gen",
                     source=f"slm:{self.stage2.name}" + (f"+ref:{ref_pattern.id}" if ref_pattern else ""),
                     confidence=0.5, candidates=cands)
        if gen.finish == "length":
            res.notes.append("geração atingiu o limite de tokens; revise o final do código")
        return res

    async def _literal(self, intent: str, lang: langs.Lang, req: Request, timings: dict[str, float], on_token, cancel,
                       cands: list[dict]) -> Result:
        """Estágio 2 em modo tradução literal: só a linha pedida, nada de programas inventados."""
        examples = list(literal_examples(lang.id))
        ctx_lines = req.before.rstrip("\n").split("\n")[-6:] if req.before.strip() else []
        context = "\n".join(ctx_lines)
        fmt = self.stage2.fmt

        def builder(level: int) -> str:
            return build_literal_prompt(fmt, lang.name, lang.fence, intent, examples[: 3 - level] if level else examples,
                                        context if level == 0 else "")

        n_lines = intent.count("\n") + 1
        t = time.perf_counter()
        try:
            gen = await asyncio.wrap_future(self.stage2.submit(
                self.stage2.generate, builder, on_token=on_token, cancel=cancel, max_tokens=48 + 40 * n_lines,
                stop=STOP + ["<|im_start|>"]), loop=asyncio.get_running_loop())
        except ModelUnavailable as exc:
            raise TranslateError(str(exc), cands) from exc
        timings["stage2_ms"] = round((time.perf_counter() - t) * 1000, 1)
        timings["tokens"] = gen.tokens
        code = clean_generation(gen.text, lang.id)
        if n_lines == 1 and "\n\n" in code.strip("\n"):
            code = code.strip("\n").split("\n\n", 1)[0]  # uma linha de pseudocódigo -> um bloco de código
        lines = code.split("\n")
        while lines and ctx_lines and lines[0].strip() and lines[0].strip() in {c.strip() for c in ctx_lines}:
            lines.pop(0)  # o modelo repetiu o contexto
        imports, body = split_imports(prune_sample_data(prune_imports("\n".join(lines), lang.id), intent), lang.id)
        res = Result(code="", body=body, imports=imports, lang=lang.id, stage="2:pseudo",
                     source=f"slm:{self.stage2.name}:literal", confidence=0.6, candidates=cands)
        res.notes.append("pseudocódigo traduzido pela IA em modo literal; ensine o compilador salvando como padrão")
        return res

    def _from_pattern(self, m: Match, filled, lang: langs.Lang, cands: list[dict], stage: str) -> Result:
        p = m.pattern
        out_lang = lang.id if lang.id in p.code or p.kind != "file" else next(iter(p.code))
        res = Result(code="", body=filled.body, imports=filled.imports, lang=out_lang, stage=stage,
                     source=f"pattern:{p.id}", confidence=round(m.score, 3), slots=filled.slots, candidates=cands)
        if p.kind == "file":
            res.file_suggestion = {"path": p.path or "", "kind": "file"}
        return res

    def _reference(self, p: Pattern, lang: str) -> tuple[str, str, str] | None:
        if lang in p.code:
            code_lang = lang
        else:
            code_lang = next((x for x in ("python", "javascript", "typescript", "go") if x in p.code), next(iter(p.code)))
        code = p.code[code_lang]
        lines = code.split("\n")
        if len(lines) > 60:
            code = "\n".join(lines[:60])
        fence = langs.LANGS[code_lang].fence if code_lang in langs.LANGS else code_lang
        return (f"{p.title} [{code_lang}]", fence, code)

    def _guidance(self, intent: str, lang: str) -> list[str]:
        concepts = {_norm(c) for _, cs, _ in analyze(intent) for c in cs}
        scored = []
        for s in self.skills:
            if s.langs and lang not in s.langs:
                continue
            base = s.id.endswith(".base")
            overlap = len(s.concepts & concepts)
            if base or overlap:
                scored.append((2 if base else 1, overlap, s))
        scored.sort(key=lambda x: (x[0] == 2, x[1]), reverse=True)
        out: list[str] = []
        for _, _, s in scored[:4]:
            for g in s.guidance:
                if g not in out:
                    out.append(g)
        return out[:6]

    def _plan_coverage(self, intent: str, patterns: list[Pattern]) -> float:
        terms = analyze(intent)
        total = sum(w for _, _, w in terms) or 1.0
        union = frozenset().union(*(p.concepts for p in patterns))
        covered = sum(w for _, cs, w in terms if {_norm(c) for c in cs} & union)
        return covered / total

    async def _plan(self, intent: str, lang: langs.Lang, useful: list[Match], cancel) -> list[tuple[Pattern, dict]]:
        tools = [{"id": m.pattern.id, "title": m.pattern.title, "params": sorted(m.pattern.slots)} for m in useful[:5]]
        by_id = {m.pattern.id: m.pattern for m in useful[:5]}
        raw_steps: list[dict] = []
        if self.needle is not None:
            raw_steps = await asyncio.get_running_loop().run_in_executor(None, self.needle.plan, intent, tools)
        elif self.stage2 is not None:
            prompt = plan_prompt(self.stage2.fmt, intent, lang.name, tools)
            try:
                data, _ = await asyncio.wrap_future(self.stage2.submit(self.stage2.plan, prompt, plan_schema(tools),
                                                                       cancel=cancel))
            except (ModelUnavailable, Cancelled):
                return []
            raw_steps = data.get("steps", []) if isinstance(data, dict) else []
        steps: list[tuple[Pattern, dict]] = []
        folded = fold(intent)
        extracted = extract_slots(intent)
        for step in raw_steps[:3]:
            p = by_id.get(step.get("pattern", ""))
            if p is None or any(p is q for q, _ in steps):
                continue
            args = {}
            for k, v in (step.get("args") or {}).items():
                v = str(v).strip()
                # aterramento: só aceita valores que estão escritos na intenção (anti-alucinação)
                if k in p.slots and v and (fold(v) in folded or v in extracted.values()):
                    args[k] = v
            steps.append((p, args))
        return steps

    # ------------------------------------------------------------------ pseudocódigo (bloco)
    async def _compile_block(self, text: str, lang: langs.Lang, req: Request, known: set[str],
                             timings: dict[str, float], cancel) -> Result:
        t = time.perf_counter()
        nodes, misses = self.stage0.parse_program(text, known)
        timings["stage0_ms"] = round((time.perf_counter() - t) * 1000, 3)
        stages_used = {"0"}
        unresolved = [n for n in _walk_all(nodes) if isinstance(n, ir.Unresolved)]
        for node in unresolved:
            sub = Request(intent=node.text, lang=lang.id, lang_explicit=True, stages=tuple(s for s in req.stages if s),
                          audit=False, mode="line")
            try:
                res = await self._translate_line(node.text, lang, sub, known, {}, None, cancel)
                stages_used.add(res.stage)
                _replace(nodes, node, ir.Raw(res.body, res.imports))
            except TranslateError:
                continue
        try:
            imports, body = emit(nodes, lang.id)
        except EmitError as exc:
            raise TranslateError(f"pseudocódigo não suportado em {lang.name}: {exc}") from exc
        stage = max(stages_used, key=lambda s: (s[0], len(s)))
        res = Result(code="", body=body, imports=imports, lang=lang.id, stage=stage,
                     source=f"block:{len(text.splitlines())} linhas", confidence=1.0 if not misses else 0.7)
        left = sum(1 for n in _walk_all(nodes) if isinstance(n, ir.Unresolved))
        if left:
            res.notes.append(f"{left} linha(s) não resolvida(s) viraram TODO")
        return res

    # ------------------------------------------------------------------ utilidades
    def audit(self, code: str, lang: str, hints: bool = False) -> dict:
        t = time.perf_counter()
        findings = self.auditor.audit(code, lang)
        out = {"findings": [f.as_dict() for f in findings], "ms": round((time.perf_counter() - t) * 1000, 3)}
        if hints:
            out["annotated"] = self.auditor.annotate(code, findings, lang)
        return out


def _walk_all(nodes: list[ir.Node]):
    for n in nodes:
        yield n
        if isinstance(n, ir.Block):
            yield from _walk_all(n.body)
        if isinstance(n, ir.If):
            for _, b in n.elifs:
                yield from _walk_all(b)
            if n.orelse:
                yield from _walk_all(n.orelse)


def _replace(nodes: list[ir.Node], old: ir.Node, new: ir.Node) -> bool:
    for i, n in enumerate(nodes):
        if n is old:
            nodes[i] = new
            return True
        if isinstance(n, ir.Block) and _replace(n.body, old, new):
            return True
        if isinstance(n, ir.If):
            if any(_replace(b, old, new) for _, b in n.elifs):
                return True
            if n.orelse and _replace(n.orelse, old, new):
                return True
    return False
