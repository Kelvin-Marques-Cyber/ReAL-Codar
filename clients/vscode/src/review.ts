import * as vscode from "vscode";
import * as path from "node:path";
import { CodarClient } from "./client";
import { applyHunks, Change, Hunk } from "./changes";

export interface Validation { path: string; status: "ok" | "error" | "skipped"; message: string; }
export interface Proposal {
  id: string; root: string; changes: Change[]; applied_changes?: Change[];
  hunks: Hunk[]; validation: Validation[]; diff: string;
}
const documents = new Map<string, string>();
let sequence = 0;

export function registerReview(): vscode.Disposable {
  return vscode.workspace.registerTextDocumentContentProvider("codar-review", {
    provideTextDocumentContent: uri => documents.get(uri.toString()) ?? "",
  });
}
async function compare(change: Change, preview = true): Promise<void> {
  const id = ++sequence;
  const old = vscode.Uri.from({ scheme: "codar-review", path: `/${id}/antes/${change.path}` });
  const proposed = vscode.Uri.from({ scheme: "codar-review", path: `/${id}/proposta/${change.path}` });
  documents.set(old.toString(), change.before ?? "");
  documents.set(proposed.toString(), change.after ?? "");
  while (documents.size > 80) documents.delete(documents.keys().next().value!);
  await vscode.commands.executeCommand("vscode.diff", old, proposed, `Codar — ${change.path}`, { preview });
}

export function location(doc: vscode.TextDocument): { root: string; path: string } | undefined {
  if (doc.uri.scheme !== "file") return undefined;
  const folder = vscode.workspace.getWorkspaceFolder(doc.uri);
  const root = folder?.uri.fsPath ?? path.dirname(doc.uri.fsPath);
  const relative = path.relative(root, doc.uri.fsPath).split(path.sep).join("/");
  return { root, path: relative };
}

export async function reviewBuffer(client: CodarClient, doc: vscode.TextDocument, before: string,
                                   after: string, preview: boolean): Promise<string | undefined> {
  const loc = location(doc);
  let change: Change = { path: loc?.path ?? "sem-titulo", before, after };
  if (preview) {
    await compare(change);
    if (loc) {
      const result = await client.call<{ hunks: Hunk[] }>("edits.preview", { ...loc, before, after });
      const selected = await vscode.window.showQuickPick(result.hunks.map(h => ({ label: `${h.path}:${h.start}`,
        description: h.diff.split("\n").find(l => l.startsWith("+") && !l.startsWith("+++"))?.slice(1, 100),
        hunk: h, picked: true })), { canPickMany: true, title: "Codar — trechos a aplicar", ignoreFocusOut: true });
      if (!selected?.length) return undefined;
      after = applyHunks(change, result.hunks, new Set(selected.map(item => item.hunk.id))) ?? "";
      change = { ...change, after };
      await compare(change);
    }
  }
  {
    const check = await client.call<Validation>("edits.validate", { ...(loc ?? { root: vscode.workspace.workspaceFolders?.[0]?.uri.fsPath ?? process.cwd(), path: "buffer" }),
      before, after, lang: doc.languageId });
    if (check.status === "error") {
      await vscode.window.showErrorMessage(`Codar: ${check.message}. Seu código foi preservado.`);
      return undefined;
    }
    if (check.status === "skipped") await vscode.window.showWarningMessage("Codar: sintaxe não verificada; validador indisponível.");
  }
  if (preview && await vscode.window.showInformationMessage("Aplicar os trechos revisados?", "Aplicar") !== "Aplicar") return undefined;
  return after;
}

export async function prepareBuffer(client: CodarClient, doc: vscode.TextDocument, before: string,
                                     after: string, intent: string): Promise<{ id: string; root: string } | undefined> {
  const loc = location(doc);
  if (!loc || before === after) return undefined;
  const record = await client.call<{ id: string }>("edits.prepare", { ...loc, before, after, intent });
  return { id: record.id, root: loc.root };
}

export async function editHistory(client: CodarClient): Promise<void> {
  const editor = vscode.window.activeTextEditor;
  const loc = editor && location(editor.document);
  if (!editor || !loc) return;
  const doc = editor.document, version = doc.version, before = doc.getText();
  const records = await client.call<{ id: string; created: number; intent: string; status: string }[]>("edits.list",
    { root: loc.root, file: loc.path });
  if (!records.length) { await vscode.window.showInformationMessage("Codar: esse arquivo ainda não tem versões guardadas."); return; }
  const picked = await vscode.window.showQuickPick(records.map(r => ({ label: new Date(r.created * 1000).toLocaleString(),
    description: r.intent, detail: r.status, id: r.id })), { title: "Codar — recuperar o original de uma edição" });
  if (!picked) return;
  const record = await client.call<Proposal>("edits.get", { root: loc.root, id: picked.id });
  const previous = record.changes.find(c => c.path === loc.path)?.before ?? "";
  const after = await reviewBuffer(client, doc, before, previous, true);
  if (after === undefined) return;
  if (doc.isClosed || doc.version !== version) { await vscode.window.showWarningMessage("O arquivo mudou durante a revisão; código preservado."); return; }
  const prepared = await prepareBuffer(client, doc, before, after, "restauração do histórico");
  if (doc.isClosed || doc.version !== version) return;
  const edit = new vscode.WorkspaceEdit();
  edit.replace(doc.uri, new vscode.Range(0, 0, doc.lineCount - 1, doc.lineAt(doc.lineCount - 1).text.length), after);
  if (await vscode.workspace.applyEdit(edit) && prepared) await client.call("edits.commit", prepared);
}

export async function editProject(client: CodarClient): Promise<void> {
  const root = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
  if (!root) { await vscode.window.showInformationMessage("Abra uma pasta de projeto."); return; }
  const info = await client.call<{ files: string[] }>("project.info", { root });
  const files = await vscode.window.showQuickPick(info.files.map(file => ({ label: file })),
    { canPickMany: true, title: "Codar — arquivos a editar (máximo 8)", ignoreFocusOut: true });
  if (!files?.length) return;
  if (files.length > 8) { await vscode.window.showWarningMessage("Escolha no máximo 8 arquivos por proposta."); return; }
  const names = files.map(f => f.label);
  const dirty = () => vscode.workspace.textDocuments.some(d => d.isDirty && location(d)?.root === root && names.includes(location(d)!.path));
  if (dirty()) { await vscode.window.showWarningMessage("Salve os arquivos escolhidos antes de editar o projeto."); return; }
  const intent = await vscode.window.showInputBox({ title: "Codar — edição de projeto", prompt: "O que mudar nesses arquivos?" });
  if (!intent) return;
  const controller = new AbortController();
  const proposal = await vscode.window.withProgress({ location: vscode.ProgressLocation.Notification, title: "Codar — preparando proposta", cancellable: true },
    async (_, token) => {
      token.onCancellationRequested(() => controller.abort());
      return client.call<Proposal>("project.edit", { root, files: names, intent }, { signal: controller.signal });
    });
  for (const change of proposal.changes) await compare(change, false);
  const selected = await vscode.window.showQuickPick(proposal.hunks.map(h => ({ label: `${h.path}:${h.start}`, hunk: h, picked: true })),
    { canPickMany: true, title: "Codar — trechos da proposta", ignoreFocusOut: true });
  if (!selected?.length) return;
  for (const change of proposal.changes) {
    const chosen = applyHunks(change, proposal.hunks.filter(h => h.path === change.path), new Set(selected.map(s => s.hunk.id)));
    await compare({ ...change, after: chosen }, false);
  }
  if (await vscode.window.showInformationMessage("Aplicar a proposta aos arquivos salvos? Os originais ficarão no histórico.", "Aplicar aos arquivos") !== "Aplicar aos arquivos") return;
  if (dirty()) { await vscode.window.showWarningMessage("Há alterações novas no editor; arquivos preservados."); return; }
  await client.call("edits.apply", { root, id: proposal.id, hunks: selected.map(s => s.hunk.id) });
  await vscode.window.showInformationMessage("Codar: proposta aplicada. O histórico permite recuperar os originais.");
}
