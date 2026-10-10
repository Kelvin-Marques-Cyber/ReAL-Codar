import * as vscode from "vscode";
import { CodarClient, Finding, RpcError, TranslateResult } from "./client";
import { looksLikeIntent, wantsEdit } from "./intent";
import { MissionControl } from "./missionControl";
import { hoistImports } from "./imports";
import { editHistory, editProject, prepareBuffer, registerReview, reviewBuffer } from "./review";

let client: CodarClient;
let diagnostics: vscode.DiagnosticCollection;
let status: vscode.StatusBarItem;
let output: vscode.OutputChannel;
let lastResult: TranslateResult | undefined;
let lastIntent = "";

const STAGE_LABEL: Record<string, string> = {
  "0": "S0 compilador",
  "1": "S1 padrão",
  "2:tools": "S2 ferramentas",
  "2:adapt": "S2 adaptado",
  "2:gen": "S2 gerado",
  "2:pseudo": "S2 pseudocódigo",
  "2:edit": "S2 edição",
};

const LINE_COMMENT: Record<string, string> = {
  python: "#", shellscript: "#", powershell: "#", ruby: "#", yaml: "#", dockerfile: "#", perl: "#", r: "#",
  lua: "--", sql: "--", haskell: "--",
};

function cfg<T>(key: string, fallback: T): T {
  return vscode.workspace.getConfiguration("codar").get<T>(key, fallback);
}

function makeClient(): CodarClient {
  return new CodarClient({
    endpoint: cfg("endpoint", ""),
    executable: cfg("executable", "codar"),
    autoStart: cfg("autoStart", true),
    log: (m) => output.appendLine(m),
  });
}

/** Heurística do gatilho espaço+Enter (igual à do Studio): frase que não termina como código. */

function updateSpaceEnter(editor: vscode.TextEditor | undefined): void {
  let ready = false;
  let intent = false; // habilita Ctrl+Enter só em linhas que parecem frase (fora delas, vale o atalho padrão do VS Code)
  if (editor && editor.selections.length === 1 && editor.selection.isEmpty) {
    const pos = editor.selection.active;
    const line = editor.document.lineAt(pos.line).text;
    intent = looksLikeIntent(line);
    ready = cfg("spaceEnter.enabled", true) && intent && pos.character === line.length && line.endsWith(" ");
  }
  void vscode.commands.executeCommand("setContext", "codar.spaceEnterReady", ready);
  void vscode.commands.executeCommand("setContext", "codar.lineIsIntent", intent);
}

function indentUnit(editor: vscode.TextEditor): string {
  const { insertSpaces, tabSize } = editor.options;
  return insertSpaces === false ? "\t" : " ".repeat(typeof tabSize === "number" ? tabSize : 4);
}

function toSeverity(sev: Finding["severity"]): vscode.DiagnosticSeverity {
  if (sev === "critical" || sev === "error") return vscode.DiagnosticSeverity.Error;
  if (sev === "warning") return vscode.DiagnosticSeverity.Warning;
  return vscode.DiagnosticSeverity.Information;
}

function makeDiagnostic(doc: vscode.TextDocument, f: Finding, line: number): vscode.Diagnostic {
  const l = Math.min(Math.max(line, 0), doc.lineCount - 1);
  const text = doc.lineAt(l).text;
  const start = text.length - text.trimStart().length;
  const d = new vscode.Diagnostic(
    new vscode.Range(l, start, l, text.length),
    f.message + (f.suggestion ? ` → ${f.suggestion}` : ""),
    toSeverity(f.severity),
  );
  d.source = "codar";
  d.code = f.id;
  return d;
}

function commentHints(body: string, findings: Finding[], languageId: string): string {
  const prefix = LINE_COMMENT[languageId] ?? "//";
  const lines = body.split("\n");
  const byLine = new Map<number, Finding[]>();
  for (const f of findings) {
    const l = Math.max(1, f.body_line ?? f.line);
    byLine.set(l, [...(byLine.get(l) ?? []), f]);
  }
  const out: string[] = [];
  lines.forEach((text, i) => {
    const indent = text.slice(0, text.length - text.trimStart().length);
    for (const f of byLine.get(i + 1) ?? []) {
      out.push(`${indent}${prefix} Dica [${f.id}]: ${f.message}${f.suggestion ? ` — ${f.suggestion}` : ""}`);
    }
    out.push(text);
  });
  return out.join("\n");
}

async function translate(editor: vscode.TextEditor, range: vscode.Range, intent: string, mode: "line" | "block" | "insert" | "edit"): Promise<void> {
  const doc = editor.document;
  if (mode === "insert") {
    const line = doc.lineAt(range.start.line);
    range = line.text.trim() ? new vscode.Range(line.range.end, line.range.end) : line.range;
  }
  const version = doc.version;
  const original = doc.getText(range);
  const firstLine = doc.lineAt(range.start.line).text;
  const indent = mode === "insert" ? "" : firstLine.slice(0, firstLine.length - firstLine.trimStart().length);
  const before = doc.getText(new vscode.Range(new vscode.Position(0, 0), range.start)).slice(-6000);
  const after = doc.getText(new vscode.Range(range.end, doc.lineAt(doc.lineCount - 1).range.end)).slice(0, 3000);
  const hintsMode = cfg<string>("hints.mode", "diagnostics");
  const ctrl = new AbortController();
  let tokens = 0;
  lastIntent = intent;
  const res = await vscode.window.withProgress(
    { location: vscode.ProgressLocation.Window, title: "Codar", cancellable: true },
    async (progress, token) => {
      token.onCancellationRequested(() => ctrl.abort());
      try {
        return await client.translate(
          {
            intent,
            lang: doc.languageId,
            context: { file: doc.uri.scheme === "file" ? doc.uri.fsPath : undefined, before, after,
              selected: mode === "edit" ? original : "", indent, indent_unit: indentUnit(editor) },
            options: { stages: cfg<number[]>("stages", [0, 1, 2]), audit: hintsMode !== "off", mode, stream: true },
          },
          {
            signal: ctrl.signal,
            onProgress: () => {
              tokens++;
              if (tokens % 4 === 0) progress.report({ message: `gerando… ${tokens} tokens` });
            },
          },
        );
      } catch (err) {
        if (err instanceof RpcError && err.code === -32800) return undefined; // cancelado
        const msg = err instanceof Error ? err.message : String(err);
        void vscode.window.showErrorMessage(`Codar: ${msg}`);
        return undefined;
      }
    },
  );
  if (!res) return;
  lastResult = res;
  MissionControl.current?.postLast(res, intent);
  status.text = `$(zap) codar ${STAGE_LABEL[res.stage] ?? res.stage} ${res.timings.total_ms?.toFixed(1) ?? "?"}ms`;
  status.tooltip = `${res.source}\n${res.findings.length} achado(s) da auditoria`;

  output.appendLine(res.code);
  if (res.complete === false) {
    void vscode.window.showWarningMessage("Codar: resposta incompleta. Código preservado; selecione um trecho menor ou aumente model.max_tokens.");
    return;
  }
  // Mudanças fora do trecho também deslocam o alvo. O cursor atual nunca redefine a edição.
  if (doc.isClosed || doc.version !== version) {
    const choice = await vscode.window.showWarningMessage("O arquivo mudou ou foi fechado enquanto o Codar respondia.", "Abrir em nova aba");
    if (choice === "Abrir em nova aba") {
      const d = await vscode.workspace.openTextDocument({ content: res.code, language: doc.languageId });
      await vscode.window.showTextDocument(d, vscode.ViewColumn.Beside);
      return;
    }
    return;
  }
  const hoist = cfg("imports.hoist", true);
  let body = hoist ? res.body : res.code;
  if ((hintsMode === "comments" || hintsMode === "both") && res.findings.length) body = commentHints(body, res.findings, doc.languageId);
  const eol = doc.eol === vscode.EndOfLine.CRLF ? "\r\n" : "\n";
  let startLine = range.start.line;
  if (mode === "insert") {
    const base = firstLine.slice(0, firstLine.length - firstLine.trimStart().length);
    body = body.split("\n").map((l) => (l.trim() ? base + l : l)).join("\n");
    if (firstLine.trim() && body) { body = "\n" + body; startLine++; }
  } else if (mode === "edit") {
    if (range.start.character > 0 && indent && body.startsWith(indent)) body = body.slice(indent.length);
    if (original.endsWith("\n") && !body.endsWith("\n")) body += "\n";
  }
  body = body.replace(/\r?\n/g, eol);
  const all = doc.getText();
  let replacement = all.slice(0, doc.offsetAt(range.start)) + body + all.slice(doc.offsetAt(range.end));
  if (hoist) {
    const imp = hoistImports(replacement, res.imports, doc.languageId, eol);
    replacement = imp.text;
    if (imp.at <= startLine) startLine += imp.added;
  }
  if (mode === "edit") {
    const reviewed = await reviewBuffer(client, doc, all, replacement, cfg("editing.preview", true));
    if (reviewed === undefined) return;
    replacement = reviewed;
  }
  if (doc.isClosed || doc.version !== version) {
    await vscode.window.showWarningMessage("O arquivo mudou durante a revisão; código preservado.");
    return;
  }
  const prepared = await prepareBuffer(client, doc, all, replacement, intent);
  if (doc.isClosed || doc.version !== version) return;
  const edit = new vscode.WorkspaceEdit();
  edit.replace(doc.uri, new vscode.Range(0, 0, doc.lineCount - 1, doc.lineAt(doc.lineCount - 1).text.length), replacement);
  const ok = await vscode.workspace.applyEdit(edit); // corpo e imports numa única operação = um único Ctrl+Z
  if (!ok) return;
  if (prepared) {
    try { await client.call("edits.commit", prepared); }
    catch (error) { output.appendLine(`Original guardado; confirmação do histórico falhou: ${String(error)}`); }
  }
  if (hintsMode === "diagnostics" || hintsMode === "both") {
    const diags = res.findings.map((f) => makeDiagnostic(doc, f, startLine + Math.max(1, f.body_line ?? f.line) - 1));
    diagnostics.set(doc.uri, diags);
  }
  for (const note of res.notes) output.appendLine(`[${res.source}] ${note}`);
  if (res.file_suggestion?.path && mode !== "block" && mode !== "edit") {
    void vscode.window.showInformationMessage(`Este padrão é um arquivo (${res.file_suggestion.path}). Criar no projeto?`, "Criar arquivo").then(async (c) => {
      const root = vscode.workspace.workspaceFolders?.[0]?.uri;
      if (c && root) {
        const target = vscode.Uri.joinPath(root, res.file_suggestion!.path);
        await vscode.workspace.fs.writeFile(target, Buffer.from(res.code + "\n", "utf8"));
        await vscode.window.showTextDocument(target);
      }
    });
  }
}

async function cmdTranslateLine(): Promise<void> {
  const editor = vscode.window.activeTextEditor;
  if (!editor) return;
  const line = editor.document.lineAt(editor.selection.active.line);
  if (!line.text.trim()) {
    void vscode.commands.executeCommand("codar.translateInput");
    return;
  }
  await translate(editor, line.range, line.text.trim(), "line");
}

async function cmdTranslateSelection(): Promise<void> {
  const editor = vscode.window.activeTextEditor;
  if (!editor || editor.selection.isEmpty) return cmdTranslateLine();
  const sel = editor.selection;
  const range = new vscode.Range(sel.start.line, 0, sel.end.line, editor.document.lineAt(sel.end.line).text.length);
  await translate(editor, range, editor.document.getText(range), "block");
}

async function cmdTranslateInput(): Promise<void> {
  const editor = vscode.window.activeTextEditor;
  if (!editor) return;
  const selection = editor.selection;
  const version = editor.document.version;
  const intent = await vscode.window.showInputBox({ prompt: "Descreva o código (pseudocódigo ou intenção)", placeHolder: "ex.: conectar ao redis em localhost:6380" });
  if (intent?.trim()) {
    if (editor.document.isClosed || editor.document.version !== version) {
      void vscode.window.showWarningMessage("O arquivo mudou durante o pedido. Selecione o trecho novamente.");
      return;
    }
    const edit = !selection.isEmpty || (editor.document.getText().trim() && wantsEdit(intent));
    const range = edit && selection.isEmpty
      ? new vscode.Range(0, 0, editor.document.lineCount - 1, editor.document.lineAt(editor.document.lineCount - 1).text.length)
      : selection;
    await translate(editor, range, intent.trim(), edit ? "edit" : "insert");
  }
}

async function cmdAuditFile(): Promise<void> {
  const editor = vscode.window.activeTextEditor;
  if (!editor) return;
  const doc = editor.document;
  try {
    const res = await client.call<{ findings: Finding[]; ms: number }>("audit", { code: doc.getText(), lang: doc.languageId, file: doc.fileName });
    diagnostics.set(doc.uri, res.findings.map((f) => makeDiagnostic(doc, f, f.line - 1)));
    status.text = `$(shield) codar auditoria: ${res.findings.length} achado(s) em ${res.ms.toFixed(1)}ms`;
    if (res.findings.length) void vscode.commands.executeCommand("workbench.actions.view.problems");
  } catch (err) {
    void vscode.window.showErrorMessage(`Codar: ${(err as Error).message}`);
  }
}

interface Suggestion {
  id: string;
  title: string;
  reason: string;
  impact: string;
  options: { id: string; label: string; reason?: string; steps: string[] }[];
}

export async function runAdvice(root: string, sid: string, oid: string): Promise<void> {
  const exe = cfg("executable", "codar");
  const term = vscode.window.terminals.find((t) => t.name === "Codar") ?? vscode.window.createTerminal({ name: "Codar", cwd: root });
  term.show();
  const q = (s: string) => (process.platform === "win32" ? `"${s}"` : `'${s.replace(/'/g, "'\\''")}'`);
  term.sendText(`${q(exe)} advise ${q(root)} --apply ${sid} --option ${oid} --yes`);
}

async function cmdAdvise(): Promise<void> {
  const root = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
  if (!root) {
    void vscode.window.showWarningMessage("Abra uma pasta de projeto para usar o consultor.");
    return;
  }
  let report: { suggestions: Suggestion[] };
  try {
    report = await client.call("advise", { root });
  } catch (err) {
    void vscode.window.showErrorMessage(`Codar: ${(err as Error).message}`);
    return;
  }
  if (!report.suggestions.length) {
    void vscode.window.showInformationMessage("Codar: nenhuma sugestão — projeto em ordem.");
    return;
  }
  const icon: Record<string, string> = { high: "$(error)", medium: "$(warning)", low: "$(info)" };
  const pick = await vscode.window.showQuickPick(
    report.suggestions.map((s) => ({ label: `${icon[s.impact] ?? ""} ${s.title}`, detail: s.reason, s })),
    { title: "Codar — consultor de projeto", matchOnDetail: true },
  );
  if (!pick) return;
  const opt = await vscode.window.showQuickPick(
    pick.s.options.map((o) => ({ label: `$(check) ${o.label}`, detail: [o.reason, ...o.steps].filter(Boolean).join("  ·  "), o })),
    { title: pick.s.title },
  );
  if (!opt) return;
  const ok = await vscode.window.showWarningMessage(
    `Aplicar "${opt.o.label}"?`,
    { modal: true, detail: opt.o.steps.join("\n") },
    "Aplicar",
  );
  if (ok === "Aplicar") await runAdvice(root, pick.s.id, opt.o.id);
}

function cmdOpenStudio(): void {
  const root = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath ?? process.cwd();
  const file = vscode.window.activeTextEditor?.document.uri.fsPath;
  const term = vscode.window.createTerminal({ name: "Codar Studio", cwd: root });
  term.show();
  term.sendText(`${cfg("executable", "codar")} studio "${root}"`);
  if (file) output.appendLine(`Studio aberto em ${root} (arquivo atual: ${file})`);
}

async function cmdHistory(): Promise<void> {
  const editor = vscode.window.activeTextEditor;
  const hist = await client.call<{ intent: string; stage: string; source: string; preview: string; lang: string }[]>("history", { limit: 50 });
  const pick = await vscode.window.showQuickPick(
    hist.map((h) => ({ label: h.intent, description: `${STAGE_LABEL[h.stage] ?? h.stage} · ${h.lang}`, detail: h.preview.split("\n")[0], h })),
    { title: "Codar — histórico (compartilhado com o Studio e a CLI)" },
  );
  if (pick && editor) await editor.edit((e) => e.insert(editor.selection.active, pick.h.preview));
}

async function cmdSaveAsPattern(): Promise<void> {
  const editor = vscode.window.activeTextEditor;
  const code = editor && !editor.selection.isEmpty ? editor.document.getText(editor.selection) : lastResult?.code;
  if (!code || !editor) {
    void vscode.window.showWarningMessage("Selecione o código (ou gere algo antes) para salvar como padrão.");
    return;
  }
  const id = await vscode.window.showInputBox({ prompt: "Id do padrão (ex.: equipe.cliente_api)", validateInput: (v) => (/^[\w.-]+$/.test(v) ? undefined : "use letras, números, . _ -") });
  if (!id) return;
  const title = await vscode.window.showInputBox({ prompt: "Título / quando usar", value: lastIntent });
  if (title === undefined) return;
  await client.call("patterns.add", { id, title: title || id, lang: editor.document.languageId, code, keywords: title });
  void vscode.window.showInformationMessage(`Codar: padrão ${id} salvo — próximas intenções parecidas usarão este código.`);
}

async function cmdRestart(): Promise<void> {
  const { execFile } = await import("node:child_process");
  client.dispose();
  execFile(cfg("executable", "codar"), ["restart"], { windowsHide: true }, (err, stdout, stderr) => {
    output.appendLine(stdout + stderr);
    if (err) void vscode.window.showErrorMessage(`Codar: ${stderr || err.message}`);
    else void vscode.window.showInformationMessage("Codar: daemon reiniciado.");
  });
}

async function refreshStatus(): Promise<void> {
  if (!client.connected) return;
  try {
    const s = await client.call<{ memory: { total_mb: number; budget_mb: number }; model: { name: string; loaded: boolean } }>("stats");
    if (!status.text.includes("zap")) {
      status.text = `$(circle-filled) codar ${s.memory.total_mb.toFixed(0)}/${s.memory.budget_mb}MB`;
    }
    status.tooltip = `modelo ${s.model.name} ${s.model.loaded ? "carregado" : "em espera"}`;
    MissionControl.current?.postStats(s);
  } catch {
    status.text = "$(circle-outline) codar offline";
  }
}

async function safely(action: () => Promise<void>): Promise<void> {
  try { await action(); }
  catch (error) {
    if (error instanceof RpcError && error.code === -32800) return;
    await vscode.window.showErrorMessage(`Codar: ${error instanceof Error ? error.message : String(error)}`);
  }
}

async function cmdCheckProject(): Promise<void> {
  const root = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
  if (!root) return;
  const selected = await vscode.window.showQuickPick([
    { label: "Sintaxe dos arquivos salvos", action: "" },
    { label: "Executar analisador", action: "analyze" },
    { label: "Executar testes", action: "test" },
  ], { title: "Codar — verificar projeto" });
  if (!selected) return;
  const result = await vscode.window.withProgress({ location: vscode.ProgressLocation.Notification, title: "Codar — verificando" },
    () => client.call<{ ok: boolean; skipped: number; files: unknown[]; commands: unknown[] }>("project.check",
      { root, actions: selected.action ? [selected.action] : [] }));
  output.appendLine(JSON.stringify(result, null, 2)); output.show();
  await vscode.window.showInformationMessage(`Codar: ${result.ok ? "sem erros detectados" : "verificação falhou"}; ${result.skipped} não verificadas.`);
}

async function cmdManagePlugins(): Promise<void> {
  const command = await vscode.window.showQuickPick(["list", "install", "update", "remove", "restore", "enable", "disable", "info"],
    { title: "Codar — gerenciar plugins" });
  if (!command) return;
  const name = command === "list" ? "" : await vscode.window.showInputBox({ prompt: command === "install" ? "Pasta local ou URL Git HTTPS" : "Nome do plugin" });
  if (name === undefined) return;
  const terminal = vscode.window.createTerminal({ name: "Codar — plugins", shellPath: cfg("executable", "codar"),
    shellArgs: ["plugins", command, ...(name ? [name] : [])] });
  terminal.show();
}

export function activate(context: vscode.ExtensionContext): void {
  output = vscode.window.createOutputChannel("Codar");
  diagnostics = vscode.languages.createDiagnosticCollection("codar");
  status = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
  status.text = "$(circle-outline) codar";
  status.command = "codar.missionControl";
  status.show();
  client = makeClient();
  const timer = setInterval(() => void refreshStatus(), 10_000);
  context.subscriptions.push(
    output, diagnostics, status, registerReview(),
    { dispose: () => clearInterval(timer) },
    { dispose: () => client.dispose() },
    vscode.commands.registerCommand("codar.translateLine", () => safely(cmdTranslateLine)),
    vscode.commands.registerCommand("codar.translateSelection", () => safely(cmdTranslateSelection)),
    vscode.commands.registerCommand("codar.translateInput", () => safely(cmdTranslateInput)),
    vscode.commands.registerCommand("codar.auditFile", cmdAuditFile),
    vscode.commands.registerCommand("codar.advise", cmdAdvise),
    vscode.commands.registerCommand("codar.openStudio", cmdOpenStudio),
    vscode.commands.registerCommand("codar.showHistory", cmdHistory),
    vscode.commands.registerCommand("codar.editHistory", () => safely(() => editHistory(client))),
    vscode.commands.registerCommand("codar.editProject", () => safely(() => editProject(client))),
    vscode.commands.registerCommand("codar.checkProject", () => safely(cmdCheckProject)),
    vscode.commands.registerCommand("codar.managePlugins", () => safely(cmdManagePlugins)),
    vscode.commands.registerCommand("codar.saveAsPattern", cmdSaveAsPattern),
    vscode.commands.registerCommand("codar.restartDaemon", cmdRestart),
    vscode.commands.registerCommand("codar.missionControl", () => MissionControl.show(context, client)),
    vscode.window.onDidChangeTextEditorSelection((e) => updateSpaceEnter(e.textEditor)),
    vscode.window.onDidChangeActiveTextEditor((e) => updateSpaceEnter(e)),
    vscode.workspace.onDidChangeConfiguration((e) => {
      if (e.affectsConfiguration("codar.endpoint") || e.affectsConfiguration("codar.executable")) {
        client.dispose();
        client = makeClient();
      }
    }),
  );
  updateSpaceEnter(vscode.window.activeTextEditor);
  void client.connect().then(refreshStatus, (err) => output.appendLine(`daemon indisponível: ${(err as Error).message}`));
}

export function deactivate(): void {
  client?.dispose();
}
