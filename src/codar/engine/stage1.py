"""Estágio 1 — banco de padrões (SQLite + FTS5), alvo < 5 ms.

Os padrões são as "ferramentas" verificadas do framework. A busca é em duas fases:
FTS5/bm25 traz candidatos; a re-pontuação por conceitos (cobertura da intenção x
precisão do padrão) decide se o padrão serve inteiro, serve de referência (RAG) ou não serve.
"""

from __future__ import annotations

import json
import re
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from codar.engine.postprocess import join_imports, split_imports
from codar.plugin_loader import Pattern, _norm
from codar.textutil import SPECIFIC, analyze, concept_set, fold

SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS patterns(
    id TEXT PRIMARY KEY, title TEXT NOT NULL, kind TEXT NOT NULL, keywords TEXT NOT NULL DEFAULT '',
    require TEXT NOT NULL DEFAULT '[]', slots TEXT NOT NULL DEFAULT '{}', produces TEXT NOT NULL DEFAULT '',
    consumes TEXT NOT NULL DEFAULT '', tags TEXT NOT NULL DEFAULT '[]', path TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL, concepts TEXT NOT NULL, core TEXT NOT NULL, hits INTEGER NOT NULL DEFAULT 0,
    created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS variants(
    pid TEXT NOT NULL REFERENCES patterns(id) ON DELETE CASCADE, lang TEXT NOT NULL, code TEXT NOT NULL,
    PRIMARY KEY (pid, lang)
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS variants_lang ON variants(lang);
CREATE VIRTUAL TABLE IF NOT EXISTS pfts USING fts5(
    pid UNINDEXED, concepts, title, keywords, tokenize = 'unicode61 remove_diacritics 2'
);
"""


@dataclass
class Match:
    pattern: Pattern
    score: float
    coverage: float
    precision: float
    has_lang: bool

    def as_dict(self) -> dict:
        return {"id": self.pattern.id, "title": self.pattern.title, "score": round(self.score, 3),
                "coverage": round(self.coverage, 3), "precision": round(self.precision, 3),
                "has_lang": self.has_lang, "langs": sorted(self.pattern.code), "kind": self.pattern.kind,
                "source": self.pattern.source}


@dataclass
class Filled:
    code: str
    imports: list[str]
    body: str
    slots: dict[str, str] = field(default_factory=dict)


# --------------------------------------------------------------------------- extração de slots

_SLOT_RX: list[tuple[str, re.Pattern[str]]] = [
    ("url", re.compile(r"\b(https?://[^\s'\"<>]+)", re.I)),
    ("hostport", re.compile(r"\b((?:\d{1,3}\.){3}\d{1,3}|localhost|[a-z0-9-]+(?:\.[a-z0-9-]+)+):(\d{2,5})\b", re.I)),
    ("port", re.compile(r"\b(?:porta|port)\s*:?\s*(\d{2,5})\b", re.I)),
    ("host", re.compile(r"\b(?:host|servidor|server|em|at|no|on)\s+((?:\d{1,3}\.){3}\d{1,3}|localhost|"
                        r"[a-z0-9-]+(?:\.[a-z0-9-]+)*\.[a-z]{2,})\b", re.I)),
    ("table", re.compile(r"\b(?:tabela|table)\s+[\"']?([A-Za-z_]\w*)", re.I)),
    ("database", re.compile(r"\b(?:banco(?:\s+de\s+dados)?|database|db|base)\s+(?:chamad[oa]\s+|named\s+)?"
                            r"[\"']?([A-Za-z_][\w-]*)", re.I)),
    ("user", re.compile(r"\b(?:usu[aá]rio|user|usuario)\s+[\"']?([A-Za-z_][\w.-]*)", re.I)),
    ("dir", re.compile(r"\b(?:pasta|diret[oó]rio|directory|folder|dir)\s+[\"']?([\w./\\~-]+)", re.I)),
    ("path", re.compile(r"[\"']([^\"']+\.[A-Za-z0-9]{1,6})[\"']|(?<![\w/])((?:[\w.~-]+/)*[\w-]+\.(?:json|csv|tsv|txt|"
                        r"log|md|yaml|yml|toml|xml|html|sql|db|sqlite|zip|tar|gz|png|jpg|jpeg|pdf|xlsx|ini|env|"
                        r"conf|py|js|ts|go|rs|ps1|sh))\b", re.I)),
    ("ext", re.compile(r"\b(?:arquivos?|files?|extens[aã]o|extension)\s+\.?(json|csv|txt|log|md|py|js|ts|go|rs|"
                       r"ps1|sh|png|jpg|pdf|xml|yaml|yml|html|sql)\b", re.I)),
    ("size", re.compile(r"\b(\d+)\s*(kb|mb|gb|k|m|g)\b", re.I)),
    ("seconds", re.compile(r"\b(\d+)\s*(?:s|seg|segundos?|seconds?|secs?)\b", re.I)),
    ("name", re.compile(r"\b(?:chamad[oa]|named|called|nome)\s+[\"']?([A-Za-z_][\w-]*)", re.I)),
    ("key", re.compile(r"\b(?:chave|key)\s+[\"']?([A-Za-z_][\w:.-]*)", re.I)),
    ("field", re.compile(r"\b(?:campo|field|coluna|column|atributo)\s+[\"']?([A-Za-z_]\w*)", re.I)),
    ("text", re.compile(r"[\"']([^\"']{1,200})[\"']")),
    ("n", re.compile(r"(?<![\w.:/-])(\d+)(?![\w.:/-])")),
]

_ALIASES = {
    "file": "path", "filename": "path", "src": "path", "source": "path", "output": "dest", "out": "dest",
    "destino": "dest", "saida": "dest", "target": "dest", "dest_path": "dest", "arquivo": "path", "input": "path", "output_path": "dest",
    "db": "database", "dbname": "database", "count": "n", "limit": "n", "times": "n", "size_mb": "size_mb",
    "folder": "dir", "directory": "dir", "message": "text", "msg": "text", "query_text": "text",
    "endpoint": "url", "timeout": "seconds", "interval": "seconds", "column": "field", "username": "user",
}


def extract_slots(intent: str) -> dict[str, str]:
    found: dict[str, str] = {}
    consumed: list[tuple[int, int]] = []

    def free(span: tuple[int, int]) -> bool:
        return all(span[1] <= s or span[0] >= e for s, e in consumed)

    for name, rx in _SLOT_RX:
        for m in rx.finditer(intent):
            if not free(m.span()):
                continue
            if name == "hostport":
                found.setdefault("host", m.group(1))
                found.setdefault("port", m.group(2))
            elif name == "path":
                found.setdefault("path" if "path" not in found else "dest", m.group(1) or m.group(2))
                consumed.append(m.span())
                continue
            elif name == "host" and m.group(1).rsplit(".", 1)[-1].lower() in _FILE_EXTS:
                continue
            elif name == "size":
                num, unit = int(m.group(1)), m.group(2).lower()[0]
                mb = num // 1024 if unit == "k" else num * 1024 if unit == "g" else num
                found.setdefault("size", f"{num}{unit.upper()}")
                found.setdefault("size_mb", str(max(mb, 1)))
            elif name in ("host", "dir", "user", "name", "database") and fold(m.group(1)) in _STOP_VALUES:
                continue
            else:
                found.setdefault(name, m.group(1))
            consumed.append(m.span())
            break
    return found


_FILE_EXTS = {"json", "csv", "tsv", "txt", "log", "md", "yaml", "yml", "toml", "xml", "html", "sql", "db", "zip",
              "gz", "tar", "png", "jpg", "jpeg", "pdf", "xlsx", "py", "js", "ts", "go", "rs", "ps1", "sh", "ini", "env"}
_STOP_VALUES = {"o", "a", "de", "do", "da", "um", "uma", "the", "an", "dados", "data", "para", "com", "e"}


# --------------------------------------------------------------------------- store

class PatternStore:
    """Acesso thread-safe (uma conexão, um lock) ao banco de padrões."""

    def __init__(self, path: Path | str, cache_kb: int = 2048) -> None:
        self.path = Path(path)
        if str(path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._db.executescript(SCHEMA)
            self._db.execute(f"PRAGMA cache_size = -{int(cache_kb)}")
            self._db.execute("PRAGMA temp_store = MEMORY")
            self._db.execute("PRAGMA mmap_size = 0")
            self._db.execute("PRAGMA foreign_keys = ON")
        self._cache: dict[str, Pattern] = {}

    def close(self) -> None:
        with self._lock:
            self._db.close()

    # ------------------------------------------------------------------ escrita
    def fingerprint(self) -> str:
        row = self._db.execute("SELECT value FROM meta WHERE key = 'fingerprint'").fetchone()
        return row[0] if row else ""

    def sync(self, patterns: list[Pattern], fingerprint: str, force: bool = False) -> bool:
        """Reconstrói os padrões vindos de plugins se mudaram. Padrões do usuário ('user') são preservados."""
        if not force and fingerprint and fingerprint == self.fingerprint():
            return False
        with self._lock:
            db = self._db
            db.execute("BEGIN")
            try:
                db.execute("DELETE FROM pfts WHERE pid IN (SELECT id FROM patterns WHERE source != 'user')")
                db.execute("DELETE FROM patterns WHERE source != 'user'")
                user_ids = {r[0] for r in db.execute("SELECT id FROM patterns")}
                for p in patterns:
                    if p.id not in user_ids:
                        self._insert(p)
                db.execute("INSERT OR REPLACE INTO meta VALUES ('fingerprint', ?)", (fingerprint,))
                db.execute("INSERT OR REPLACE INTO meta VALUES ('built', ?)", (str(time.time()),))
                db.execute("COMMIT")
            except BaseException:
                db.execute("ROLLBACK")
                raise
            db.execute("INSERT INTO pfts(pfts) VALUES ('optimize')")
            self._cache.clear()
        return True

    def _insert(self, p: Pattern) -> None:
        self._db.execute(
            "INSERT OR REPLACE INTO patterns VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,0,?)",
            (p.id, p.title, p.kind, p.keywords, json.dumps(p.require), json.dumps(p.slots), p.produces, p.consumes,
             json.dumps(p.tags), p.path, p.source, " ".join(sorted(p.concepts)), " ".join(sorted(p.core)), time.time()),
        )
        self._db.executemany("INSERT OR REPLACE INTO variants VALUES (?,?,?)", [(p.id, k, v) for k, v in p.code.items()])
        self._db.execute("INSERT INTO pfts(pid, concepts, title, keywords) VALUES (?,?,?,?)",
                         (p.id, " ".join(sorted(p.concepts)), p.title, f"{p.keywords} {p.id.replace('.', ' ')}"))

    def add(self, p: Pattern) -> None:
        """Adiciona/atualiza um padrão do usuário (ex.: 'salvar como padrão' na TUI ou no VS Code)."""
        p.source = "user"
        p.finalize()
        with self._lock:
            self._db.execute("BEGIN")
            try:
                existing = self.get(p.id, lock=False)
                if existing:
                    p.code = {**existing.code, **p.code}
                    self._db.execute("DELETE FROM pfts WHERE pid = ?", (p.id,))
                    self._db.execute("DELETE FROM variants WHERE pid = ?", (p.id,))
                self._insert(p)
                self._db.execute("COMMIT")
            except BaseException:
                self._db.execute("ROLLBACK")
                raise
            self._cache.pop(p.id, None)

    def remove(self, pid: str) -> bool:
        with self._lock:
            cur = self._db.execute("DELETE FROM patterns WHERE id = ? AND source = 'user'", (pid,))
            if cur.rowcount:
                self._db.execute("DELETE FROM pfts WHERE pid = ?", (pid,))
            self._cache.pop(pid, None)
            return bool(cur.rowcount)

    def hit(self, pid: str) -> None:
        with self._lock:
            self._db.execute("UPDATE patterns SET hits = hits + 1 WHERE id = ?", (pid,))

    # ------------------------------------------------------------------ leitura
    def get(self, pid: str, lock: bool = True) -> Pattern | None:
        if pid in self._cache:
            return self._cache[pid]
        if lock:
            with self._lock:
                return self._get(pid)
        return self._get(pid)

    def _get(self, pid: str) -> Pattern | None:
        row = self._db.execute("SELECT * FROM patterns WHERE id = ?", (pid,)).fetchone()
        if not row:
            return None
        code = {r["lang"]: r["code"] for r in self._db.execute("SELECT lang, code FROM variants WHERE pid = ?", (pid,))}
        p = Pattern(id=row["id"], title=row["title"], code=code, keywords=row["keywords"], kind=row["kind"],
                    require=json.loads(row["require"]), slots=json.loads(row["slots"]), produces=row["produces"],
                    consumes=row["consumes"], tags=json.loads(row["tags"]), path=row["path"], source=row["source"],
                    concepts=frozenset(row["concepts"].split()), core=frozenset(row["core"].split()))
        if len(self._cache) > 512:
            self._cache.clear()
        self._cache[pid] = p
        return p

    def stats(self) -> dict:
        with self._lock:
            n = self._db.execute("SELECT count(*) FROM patterns").fetchone()[0]
            v = self._db.execute("SELECT count(*) FROM variants").fetchone()[0]
            by_lang = dict(self._db.execute("SELECT lang, count(*) FROM variants GROUP BY lang ORDER BY 2 DESC").fetchall())
            user = self._db.execute("SELECT count(*) FROM patterns WHERE source = 'user'").fetchone()[0]
        return {"patterns": n, "variants": v, "user": user, "langs": by_lang}

    def list(self, lang: str | None = None, query: str | None = None, limit: int = 500) -> list[dict]:
        sql = ("SELECT p.id, p.title, p.kind, p.source, p.hits, group_concat(v.lang, ',') AS langs FROM patterns p "
               "JOIN variants v ON v.pid = p.id GROUP BY p.id")
        rows = []
        with self._lock:
            for r in self._db.execute(sql + " ORDER BY p.id LIMIT ?", (limit * 4,)):
                langs = sorted(r["langs"].split(","))
                if lang and lang not in langs:
                    continue
                if query and fold(query) not in fold(f"{r['id']} {r['title']}"):
                    continue
                rows.append({"id": r["id"], "title": r["title"], "kind": r["kind"], "source": r["source"],
                             "hits": r["hits"], "langs": langs})
        return rows[:limit]

    # ------------------------------------------------------------------ busca
    def search(self, intent: str, lang: str | None, limit: int = 5) -> list[Match]:
        # o valor de um slot ("livro.txt") não é parte do pedido: não pode contar contra a cobertura
        slots = extract_slots(intent)
        text = intent
        for key in ("path", "dest"):
            if slots.get(key):
                text = text.replace(slots[key], " ")
        terms = analyze(text)
        if "path" in slots:  # "do arquivo livro.txt": a palavra arquivo só anuncia o caminho
            terms = [(w, cs, min(wt, 0.25) if "file" in cs else wt) for w, cs, wt in terms]
        if not terms:
            return []
        tokens = set()
        for word, cs, _ in terms:
            for c in cs:
                tokens.add(_norm(c))
            if len(word) >= 4:
                tokens.add(word[:5] + "*")
        q = " OR ".join(f'"{t[:-1]}"*' if t.endswith("*") else f'"{t}"' for t in sorted(tokens) if t.strip("*"))
        if not q:
            return []
        with self._lock:
            try:
                rows = self._db.execute(
                    "SELECT pid, bm25(pfts, 0.0, 3.0, 2.0, 1.0) AS rank FROM pfts WHERE pfts MATCH ? "
                    "ORDER BY rank LIMIT 40", (q,)).fetchall()
            except sqlite3.OperationalError:
                return []
        intent_concepts = {_norm(c) for _, cs, _ in terms for c in cs}
        # o tipo do arquivo citado conta para as palavras obrigatórias: "ler o arquivo vendas.csv" é um pedido de CSV
        tipos = {_norm(c) for k in ("path", "dest") if slots.get(k) and "." in slots[k]
                 for c in concept_set(slots[k].rsplit(".", 1)[-1].lower())}
        intent_specific = intent_concepts & SPECIFIC
        total_w = sum(w for _, _, w in terms)
        out: list[Match] = []
        for row in rows:
            p = self.get(row["pid"])
            if p is None:
                continue
            if p.require and not ({_norm(c) for c in _concepts_of(p.require)} & (intent_concepts | tipos)):
                continue
            p_specific = p.core & SPECIFIC
            if p_specific - intent_concepts - tipos:
                continue
            matched = sum(w for word, cs, w in terms if {_norm(c) for c in cs} & p.concepts
                          or any(k.startswith(word[:5]) for k in p.concepts if len(word) >= 5))
            coverage = matched / total_w if total_w else 0.0
            # require = alternativas ("qualquer um destes"); já garantido pelo filtro acima. Sem require, o núcleo
            # são os conceitos do título e todos contam (precisão = fração presente na intenção).
            precision = 1.0 if p.require else (len(p.core & intent_concepts) / len(p.core) if p.core else 1.0)
            score = 0.65 * coverage + 0.35 * precision
            if intent_specific - p.concepts:
                score *= 0.7
            out.append(Match(p, score, coverage, precision, bool(lang and lang in p.code)))
        out.sort(key=lambda m: (m.score, m.has_lang, -len(m.pattern.core)), reverse=True)
        return out[:limit]

    # ------------------------------------------------------------------ preenchimento
    def fill(self, p: Pattern, lang: str, intent: str = "", overrides: dict[str, str] | None = None,
             extracted: dict[str, str] | None = None) -> Filled:
        code = p.code[lang]
        extracted = extracted if extracted is not None else extract_slots(intent)
        values: dict[str, str] = {}
        for slot, default in p.slots.items():
            val = (overrides or {}).get(slot) or extracted.get(slot) or extracted.get(_ALIASES.get(slot, ""))
            values[slot] = str(val) if val else default
        for slot, val in values.items():
            code = code.replace("{{" + slot + "}}", val)
        code = code.rstrip("\n")
        imports, body = split_imports(code, lang)
        return Filled(code=code, imports=imports, body=body, slots=values)


def _concepts_of(words: list[str]) -> set[str]:
    out: set[str] = set()
    for w in words:
        for _, cs, _ in analyze(w):
            out |= set(cs)
        out.add(fold(w))
    return out


def compose(store: PatternStore, steps: list[tuple[Pattern, dict[str, str]]], lang: str, intent: str) -> Filled:
    """Encadeia várias ferramentas: a saída (produces) de um passo alimenta a entrada (consumes) do próximo."""
    imports: list[str] = []
    bodies: list[str] = []
    slots: dict[str, str] = {}
    prev_out = ""
    extracted = extract_slots(intent)
    for p, args in steps:
        args = dict(args)
        if p.consumes and prev_out and p.consumes not in args:
            args[p.consumes] = prev_out
        filled = store.fill(p, lang, intent, args, extracted)
        for imp in filled.imports:
            if imp not in imports:
                imports.append(imp)
        bodies.append(filled.body)
        slots.update({f"{p.id}.{k}": v for k, v in filled.slots.items()})
        prev_out = args.get(p.produces) or (filled.slots.get(p.produces) if p.produces in p.slots else p.produces) \
            or prev_out
    body = "\n\n".join(b for b in bodies if b.strip())
    return Filled(code=join_imports(imports, body, lang), imports=imports, body=body, slots=slots)
