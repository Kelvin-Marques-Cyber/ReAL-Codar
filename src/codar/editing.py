"""Edição de projeto em propostas: geração delimitada, verificação e recuperação compartilhadas."""

from __future__ import annotations

import ast
import asyncio
import re
import threading
from collections import Counter

from codar import langs
from codar.engine.router import Request, TranslateError
from codar.engine.stage2 import Cancelled
from codar.project import Project, read_source, safe_path
from codar.studio.edits import hoist_imports
from codar.validation import check_project, validate_text
from codar.workspace import Change, EditStore, diff, hunks

METHODS = {"project.info", "project.context", "project.check", "project.edit", "edits.record", "edits.list",
           "edits.get", "edits.apply", "edits.restore", "edits.recover", "edits.validate", "edits.preview",
           "edits.prepare", "edits.commit"}


def edit_units(text: str, file: str, maximum: int) -> list[tuple[int, int]]:
    """Arquivos grandes são divididos em funções completas; nenhuma instrução é cortada ao meio."""
    if len(text) <= maximum:
        return [(0, len(text))]
    lines = text.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    units = []
    if file.endswith(".py"):
        try:
            tree = ast.parse(text)
        except SyntaxError as exc:
            raise TranslateError("arquivo grande com sintaxe incompleta: selecione a função que precisa de correção") from exc

        def visit(nodes):
            for node in nodes:
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    continue
                first = min([node.lineno] + [d.lineno for d in node.decorator_list])
                start, end = offsets[first - 1], offsets[node.end_lineno]
                if isinstance(node, ast.ClassDef) and end - start > maximum:
                    visit(node.body)
                else:
                    units.append((start, end))
        visit(tree.body)
    else:
        # Gramáticas opcionais reconhecem declarações Dart, PowerShell e outras linguagens.
        from codar.evals.patternlint import _parser

        language = langs.from_path(file)
        parser = _parser(language.id) if language and language.id not in ("r", "julia", "powershell") else None
        if parser:
            encoded = text.encode()
            tree = parser.parse(encoded)
            if tree.root_node.has_error:
                raise TranslateError("arquivo grande com sintaxe incompleta; selecione a função que precisa de correção")
            kinds = {"function_definition", "function_declaration", "method_definition", "method_declaration",
                     "function_item", "class_definition", "class_declaration"}

            def visit(node):
                if node.type in kinds and node.end_byte - node.start_byte <= maximum:
                    start = len(encoded[:node.start_byte].decode())
                    end = len(encoded[:node.end_byte].decode())
                    start = text.rfind("\n", 0, start) + 1
                    units.append((start, end))
                else:
                    if node.type in kinds and not node.type.startswith("class"):
                        raise TranslateError("uma função excede o orçamento; selecione um trecho menor")
                    children = node.named_children
                    skip = set()
                    for index, child in enumerate(children):
                        if index in skip:
                            continue
                        if child.type in ("function_signature", "method_signature") and index + 1 < len(children) \
                                and children[index + 1].type == "function_body":
                            body = children[index + 1]
                            start = len(encoded[:child.start_byte].decode())
                            end = len(encoded[:body.end_byte].decode())
                            start = text.rfind("\n", 0, start) + 1
                            if end - start > maximum:
                                raise TranslateError("uma função excede o orçamento; selecione um trecho menor")
                            units.append((start, end))
                            skip.add(index + 1)
                        else:
                            visit(child)
            visit(tree.root_node)
        elif language and language.id == "powershell":
            from codar.audit.lexer import mask

            # O lexer remove strings/comentários preservando as posições dos caracteres.
            masked = mask(text, "powershell", strings=True)
            for match in re.finditer(r"(?im)^\s*function\s+[\w:-]+\s*(?:\([^\n]*\)\s*)?\{", masked):
                depth, end = 1, match.end()
                while end < len(masked) and depth:
                    depth += (masked[end] == "{") - (masked[end] == "}")
                    end += 1
                if not depth:
                    units.append((match.start(), end))
    if not units or len(units) > 40 or any(end - start > maximum for start, end in units):
        raise TranslateError("há uma função maior que o orçamento de geração. Selecione esse trecho no editor "
                             "ou aumente model.max_tokens e model.n_ctx")
    ordered = sorted(set(units))
    if any(b > c for (_, b), (c, _) in zip(ordered, ordered[1:])):
        raise TranslateError("não foi possível separar declarações sem sobreposição; selecione um trecho menor")
    return ordered


def duplicate_definitions(text: str) -> Counter:
    counts = Counter()
    try:
        module = ast.parse(text)
    except SyntaxError:
        return counts

    def visit(body, scope):
        for node in body:
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                counts[(scope, node.name)] += 1
                visit(node.body, scope + (node.name,))
    visit(module.body, ())
    return counts


def validate_change(before: str, after: str, file: str, *, native: bool = True, lang: str | None = None) -> dict:
    checked = validate_text(after, file, native=native, lang=lang)
    if file.endswith(".py") or (lang and langs.resolve(lang).id == "python"):
        old, new = duplicate_definitions(before), duplicate_definitions(after)
        duplicate = [name for scope, name in new if new[(scope, name)] > max(1, old[(scope, name)])]
        if duplicate:
            checked.update(status="error", message="definição duplicada: " + ", ".join(duplicate))
    return checked


async def propose_project(router, root: str, files: list[str], intent: str, cancel: threading.Event | None = None) -> dict:
    project = await asyncio.to_thread(Project.load, root)
    if not isinstance(files, list) or any(not isinstance(name, str) for name in files) \
            or not intent.strip() or not files or len(files) > 8 or len(set(files)) != len(files):
        raise ValueError("informe a intenção e de 1 a 8 arquivos distintos")
    originals = {}
    for name in files:
        if not project.allowed(name) or not langs.from_path(name):
            raise ValueError(f"arquivo não suportado ou excluído: {name}")
        target = safe_path(project.root, name)
        originals[name] = await asyncio.to_thread(read_source, target) if target.exists() else None
    updates, checks, notes = {}, [], []
    maximum = max(200, min(int(router.rcfg.get("max_edit_chars", 12000)),
                           int(router.cfg["model"].get("max_tokens", 384)) * 2))
    for name in files:
        if cancel and cancel.is_set():
            raise Cancelled()
        original = originals[name]
        text = original or ""
        context = await asyncio.to_thread(project.context, intent, name, updates)
        if original is None:
            request = Request(intent=f"{intent}\nCreate only the complete file {name}.", file=str(project.root / name),
                              lang=langs.from_path(name).id, lang_explicit=True, stages=(2,),
                              project_context=context["context"], project_guidance=project.guidance,
                              project_skills=project.skills)
            res = await router.translate(request, cancel=cancel)
            if not res.complete:
                raise TranslateError(f"geração incompleta em {name}; arquivos preservados")
            text = res.code.rstrip("\n") + "\n"
        else:
            units = edit_units(original, name, maximum)
            if len(units) > 1 or units != [(0, len(original))]:
                notes.append(f"{name}: {len(units)} declaração(ões) editada(s); cabeçalhos e código fora delas preservados")
            replacements, imports = [], []
            for start, end in units:
                selected = original[start:end]
                indent = selected[:len(selected) - len(selected.lstrip(" \t"))]
                request = Request(intent=intent + f"\nChange only this selection in {name}; keep everything unrelated.",
                                  mode="edit", selected=selected, before=original[:start][-3000:],
                                  after=original[end:][:3000], file=str(project.root / name), indent=indent,
                                  lang=langs.from_path(name).id, lang_explicit=True,
                                  project_context=context["context"], project_guidance=project.guidance,
                                  project_skills=project.skills)
                res = await router.translate(request, cancel=cancel)
                if not res.complete:
                    raise TranslateError(f"edição incompleta em {name}; arquivos preservados")
                body = res.body
                if selected.endswith("\n") and not body.endswith("\n"):
                    body += "\n"
                replacements.append((start, end, body))
                imports += res.imports
            for start, end, body in reversed(replacements):
                text = text[:start] + body + text[end:]
            text, _ = hoist_imports(text, imports, langs.from_path(name).id)
        if "\r\n" in (original or ""):
            text = text.replace("\r\n", "\n").replace("\n", "\r\n")
        checked = await asyncio.to_thread(validate_change, original or "", text, name)
        for attempt in range(project.repair_attempts):
            if checked["status"] != "error":
                break
            if len(text) > maximum:
                notes.append(f"{name}: validação falhou; selecione a função com erro para corrigir")
                break
            repair = Request(intent=f"Repair the syntax or duplicate definition without changing behavior: {checked['message']}",
                             mode="edit", selected=text, file=str(project.root / name),
                             lang=langs.from_path(name).id, lang_explicit=True, project_context=context["context"],
                             project_guidance=project.guidance, project_skills=project.skills)
            res = await router.translate(repair, cancel=cancel)
            if not res.complete:
                break
            text = res.code.rstrip("\n") + "\n"
            if "\r\n" in (original or ""):
                text = text.replace("\r\n", "\n").replace("\n", "\r\n")
            checked = await asyncio.to_thread(validate_change, original or "", text, name)
            notes.append(f"{name}: tentativa de correção {attempt + 1}/{project.repair_attempts}")
        updates[name] = text
        checks.append(checked)
    changes = [Change(name, originals[name], updates[name]) for name in files if originals[name] != updates[name]]
    if cancel and cancel.is_set():
        raise Cancelled()
    store = EditStore(project.root)
    store._assert_originals(changes)
    return await asyncio.to_thread(store.create, changes, intent, validation=checks, notes=notes)


async def workspace_call(router, method: str, p: dict, cancel=None) -> dict | list:
    root = p.get("root")
    if not isinstance(root, str) or not root:
        raise ValueError("informe root (pasta do projeto)")
    if method == "project.edit":
        return await propose_project(router, root, p.get("files", []), str(p.get("intent", "")), cancel)
    if method in ("project.info", "project.context", "project.check"):
        project = await asyncio.to_thread(Project.load, root)
        if method == "project.info":
            return {**project.as_dict(), "files": await asyncio.to_thread(project.files)}
        if method == "project.context":
            return await asyncio.to_thread(project.context, str(p.get("intent", "")), str(p.get("file", "")))
        actions = p.get("actions", [])
        if not isinstance(actions, list) or any(a not in ("test", "analyze", "format") for a in actions):
            raise ValueError("actions: use test, analyze ou format")
        return await asyncio.to_thread(check_project, root, p.get("files"), actions=actions,
                                       native=bool(p.get("native", True)), timeout=int(p.get("timeout", 60)))
    if method == "edits.validate":
        project = Project.load(root)
        name = str(p.get("path", ""))
        safe_path(project.root, name)
        return await asyncio.to_thread(validate_change, str(p.get("before", "")), str(p.get("after", "")), name,
                                       native=bool(router.cfg.get("editing", {}).get("native_validation", True)), lang=p.get("lang"))
    if method == "edits.preview":
        project = Project.load(root)
        name = str(p.get("path", ""))
        safe_path(project.root, name)
        change = Change(name, str(p.get("before", "")), str(p.get("after", "")))
        return {"hunks": hunks(change), "diff": diff([change])}
    store = await asyncio.to_thread(EditStore, root)
    if method in ("edits.record", "edits.prepare"):
        return await asyncio.to_thread(store.create, [Change(str(p.get("path", "")), p.get("before"), p.get("after"))],
                                       str(p.get("intent", "")), status="prepared" if method == "edits.prepare" else "buffer")
    if method == "edits.commit":
        return await asyncio.to_thread(store.commit_buffer, str(p.get("id", "")))
    if method == "edits.list":
        return await asyncio.to_thread(store.list, int(p.get("limit", 50)), p.get("file"))
    if method == "edits.get":
        return store.describe(await asyncio.to_thread(store.get, str(p.get("id", ""))))
    if method == "edits.apply":
        return await asyncio.to_thread(store.apply, str(p.get("id", "")), p.get("hunks"))
    if method == "edits.restore":
        return await asyncio.to_thread(store.restore, str(p.get("id", "")))
    if method == "edits.recover":
        return await asyncio.to_thread(store.recover)
    raise ValueError("método de edição desconhecido")
