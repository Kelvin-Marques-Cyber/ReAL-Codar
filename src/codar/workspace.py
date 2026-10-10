"""Propostas revisáveis e diário de edição. O texto esperado protege contra sobrescritas atrasadas."""

from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
import tempfile
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

from codar import paths
from codar.locking import file_lock
from codar.project import MAX_FILE_BYTES, Project, read_source, safe_path


class EditConflict(ValueError):
    pass


@dataclass
class Change:
    path: str
    before: str | None
    after: str | None


def hunks(change: Change) -> list[dict]:
    old, new = (change.before or "").splitlines(keepends=True), (change.after or "").splitlines(keepends=True)
    groups = difflib.SequenceMatcher(None, old, new, autojunk=len(old) + len(new) > 4000).get_grouped_opcodes(3)
    result = []
    for i, group in enumerate(groups):
        a, b = group[0][1], group[-1][2]
        c, d = group[0][3], group[-1][4]
        patch = [f"@@ -{a + 1},{b - a} +{c + 1},{d - c} @@\n"]
        for tag, a1, a2, b1, b2 in group:
            if tag == "equal":
                patch += [" " + line for line in old[a1:a2]]
            else:
                patch += ["-" + line for line in old[a1:a2]]
                patch += ["+" + line for line in new[b1:b2]]
        result.append({"id": f"{change.path}:{i}", "path": change.path, "start": a + 1,
                       "diff": "".join(patch), "opcodes": [list(op) for op in group if op[0] != "equal"]})
    return result


def select_hunks(change: Change, selected: set[str]) -> Change:
    if change.before is None or change.after is None:
        return change if any(h["id"] in selected for h in hunks(change)) else Change(change.path, change.before, change.before)
    old, new = change.before.splitlines(keepends=True), change.after.splitlines(keepends=True)
    replacements = [op for h in hunks(change) if h["id"] in selected for op in h["opcodes"]]
    for _, a, b, c, d in reversed(replacements):
        old[a:b] = new[c:d]
    return Change(change.path, change.before, "".join(old))


def diff(changes: list[Change]) -> str:
    return "".join("".join(difflib.unified_diff((ch.before or "").splitlines(keepends=True),
                                             (ch.after or "").splitlines(keepends=True),
                                             fromfile="a/" + ch.path, tofile="b/" + ch.path)) for ch in changes)


class EditStore:
    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().resolve()
        Project.load(self.root)
        key = hashlib.sha256(str(self.root).encode()).hexdigest()[:24]
        self.directory = paths.ensure_private_dir(paths.data_dir() / "edits" / key)
        self.lock = self.directory / ".lock"

    def _path(self, identity: str):
        if not re.fullmatch(r"[0-9a-f]{32}", identity):
            raise ValueError("id de edição inválido")
        return self.directory / (identity + ".json")

    def get(self, identity: str) -> dict:
        record = json.loads(self._path(identity).read_text(encoding="utf-8"))
        if not isinstance(record, dict) or record.get("root") != str(self.root):
            raise ValueError("edição pertence a outro projeto")
        return record

    def _write(self, record: dict):
        descriptor, name = tempfile.mkstemp(prefix=".journal-", dir=self.directory)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(record, handle, ensure_ascii=False)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(name, self._path(record["id"]))
        finally:
            Path(name).unlink(missing_ok=True)

    def create(self, changes: list[Change], intent: str = "", *, validation: list[dict] | None = None,
               status: str = "draft", notes: list[str] | None = None) -> dict:
        if not 1 <= len(changes) <= 20 or len({ch.path for ch in changes}) != len(changes):
            raise ValueError("uma proposta precisa de 1 a 20 arquivos distintos")
        project = Project.load(self.root)
        for change in changes:
            safe_path(self.root, change.path)
            if not project.allowed(change.path):
                raise ValueError(f"arquivo excluído: {change.path}")
            for text in (change.before, change.after):
                if text is not None and (not isinstance(text, str) or len(text.encode()) > MAX_FILE_BYTES or "\0" in text):
                    raise ValueError(f"texto inválido ou grande demais: {change.path}")
        if all(ch.before == ch.after for ch in changes):
            raise ValueError("nenhuma alteração proposta")
        if status not in ("draft", "buffer", "prepared"):
            raise ValueError("estado inicial inválido")
        record = {"id": uuid.uuid4().hex, "root": str(self.root), "created": time.time(), "status": status,
                  "intent": intent[:4000], "changes": [asdict(c) for c in changes], "validation": validation or [],
                  "notes": notes or []}
        with file_lock(self.lock):
            self._write(record)
        return self.describe(record)

    def commit_buffer(self, identity: str) -> dict:
        with file_lock(self.lock):
            record = self.get(identity)
            if record["status"] != "prepared":
                raise EditConflict("essa edição não está preparada")
            record.update(status="buffer", finished=time.time())
            self._write(record)
            return {"id": identity, "status": "buffer"}

    @staticmethod
    def describe(record: dict) -> dict:
        changes = [Change(**c) for c in record["changes"]]
        result = {**record, "diff": diff(changes), "hunks": [h for c in changes for h in hunks(c)]}
        if "applied_changes" in record:
            result["applied_diff"] = diff([Change(**c) for c in record["applied_changes"]])
        return result

    def list(self, limit: int = 50, file: str | None = None) -> list[dict]:
        records = []
        for path in self.directory.glob("*.json"):
            try:
                rec = self.get(path.stem)
                if file and file not in [c["path"] for c in rec["changes"]]:
                    continue
                records.append({k: rec[k] for k in ("id", "created", "status", "intent")})
                records[-1]["files"] = [c["path"] for c in rec["changes"]]
            except (OSError, ValueError, KeyError, TypeError):
                continue
        return sorted(records, key=lambda r: r["created"], reverse=True)[:max(1, min(limit, 200))]

    def apply(self, identity: str, selected: list[str] | None = None) -> dict:
        with file_lock(self.lock):
            record = self.get(identity)
            if record["status"] != "draft":
                raise EditConflict("essa proposta já foi aplicada ou não é uma edição de arquivos")
            changes = [Change(**c) for c in record["changes"]]
            if selected is not None:
                available = {h["id"] for c in changes for h in hunks(c)}
                if not set(selected) <= available:
                    raise ValueError("trecho não pertence à proposta")
                changes = [select_hunks(c, set(selected)) for c in changes]
            changes = [c for c in changes if c.before != c.after]
            if not changes:
                raise ValueError("selecione ao menos uma alteração")
            from codar.editing import validate_change

            checks = [validate_change(c.before or "", c.after, c.path) for c in changes if c.after is not None]
            if any(c["status"] == "error" for c in checks):
                raise ValueError("a proposta contém erro de sintaxe; revise os trechos antes de aplicar")
            if selected is None and any(c.get("status") == "error" for c in record.get("validation", [])):
                raise ValueError("a validação da proposta falhou; gere uma correção antes de aplicar")
            record["applied_changes"] = [asdict(c) for c in changes]
            self._replace(record, changes, "applied")
            return self.describe(record)

    def restore(self, identity: str) -> dict:
        with file_lock(self.lock):
            record = self.get(identity)
            if record["status"] not in ("applied", "buffer"):
                raise EditConflict("essa edição não está aplicada")
            changes = []
            for c in record.get("applied_changes", record["changes"]):
                expected, original = c["after"], c["before"]
                if record["status"] == "buffer" and isinstance(expected, str) and "\r\n" not in expected:
                    target = safe_path(self.root, c["path"])
                    current = read_source(target) if target.exists() else None
                    # TextArea usa LF no buffer; salvar no Windows pode produzir CRLF no disco.
                    if isinstance(current, str) and "\r\n" in current and current.replace("\r\n", "\n") == expected:
                        expected = current
                        if isinstance(original, str):
                            original = original.replace("\r\n", "\n").replace("\n", "\r\n")
                changes.append(Change(c["path"], expected, original))
            self._replace(record, changes, "restored")
            return self.describe(record)

    def _replace(self, record: dict, changes: list[Change], success: str):
        self._assert_originals(changes)
        staged, written = [], []
        old_status = record["status"]
        try:
            for change in changes:
                target = safe_path(self.root, change.path)
                target.parent.mkdir(parents=True, exist_ok=True)
                staged.append((change, self._stage(target, change.after)))
            record.update(status="applying", previous_status=old_status, transaction=[asdict(c) for c in changes],
                          transaction_result=success)
            self._write(record)  # originais duráveis ANTES da primeira troca
            for change, temporary in staged:
                self._assert_originals([change])
                target = safe_path(self.root, change.path)
                if temporary is None:
                    target.unlink(missing_ok=True)
                else:
                    os.replace(temporary, target)
                written.append(change)
            record["status"] = success
            record["finished"] = time.time()
            self._write(record)
        except BaseException:
            # Se outro editor mudou um arquivo, não sobrescreve a mudança para desfazer.
            conflicts = self._rollback(written)
            record["status"] = "conflict" if conflicts else old_status
            record["conflicts"] = conflicts
            self._write(record)
            raise
        finally:
            for _, temporary in staged:
                if temporary:
                    temporary.unlink(missing_ok=True)

    def recover(self) -> list[dict]:
        """Recupera transações interrompidas; alterações posteriores tornam-se conflitos explícitos."""
        results = []
        with file_lock(self.lock):
            for path in self.directory.glob("*.json"):
                try:
                    record = self.get(path.stem)
                except (OSError, ValueError, KeyError):
                    continue
                if record.get("status") != "applying":
                    continue
                changes = [Change(**c) for c in record["transaction"]]
                conflicts = self._rollback(changes)
                record["status"] = "conflict" if conflicts else record["previous_status"]
                record["conflicts"] = conflicts
                self._write(record)
                results.append({"id": record["id"], "status": record["status"], "conflicts": conflicts})
        return results

    def _rollback(self, changes: list[Change]) -> list[str]:
        conflicts = []
        for change in reversed(changes):
            try:
                target = safe_path(self.root, change.path)
                current = read_source(target) if target.exists() else None
                if current == change.before:
                    continue
                if current != change.after:
                    conflicts.append(change.path)
                    continue
                if change.before is None:
                    target.unlink(missing_ok=True)
                else:
                    temporary = self._stage(target, change.before)
                    try:
                        os.replace(temporary, target)
                    finally:
                        temporary.unlink(missing_ok=True)
            except (OSError, ValueError):
                conflicts.append(change.path)
        return conflicts

    def _assert_originals(self, changes: list[Change]):
        for change in changes:
            target = safe_path(self.root, change.path)
            current = read_source(target) if target.exists() else None
            if current != change.before:
                raise EditConflict(f"{change.path} mudou desde a proposta; arquivo preservado")

    @staticmethod
    def _stage(target: Path, text: str | None) -> Path | None:
        if text is None:
            return None
        descriptor, name = tempfile.mkstemp(prefix=".codar-edit-", dir=target.parent)
        temporary = Path(name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            temporary.chmod(target.stat().st_mode & 0o777 if target.exists() else 0o644)
            return temporary
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
