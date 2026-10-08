// Painel gráfico (webview) no estilo "mission control": telemetria, última tradução e consultor com botões de aceitar.
import * as crypto from "node:crypto";
import * as vscode from "vscode";
import { CodarClient, TranslateResult } from "./client";

type Msg = { type: "apply"; id: string; option: string } | { type: "refresh" } | { type: "studio" } | { type: "audit" };

export class MissionControl {
  static current: MissionControl | undefined;

  private constructor(private readonly panel: vscode.WebviewPanel, private readonly client: CodarClient) {
    panel.webview.html = this.html();
    panel.onDidDispose(() => (MissionControl.current = undefined));
    panel.webview.onDidReceiveMessage((m: Msg) => this.onMessage(m));
    void this.refresh();
  }

  static show(context: vscode.ExtensionContext, client: CodarClient): void {
    if (MissionControl.current) {
      MissionControl.current.panel.reveal();
      void MissionControl.current.refresh();
      return;
    }
    const panel = vscode.window.createWebviewPanel("codarMissionControl", "Codar · Mission Control", vscode.ViewColumn.Beside, {
      enableScripts: true,
      retainContextWhenHidden: true,
    });
    context.subscriptions.push(panel);
    MissionControl.current = new MissionControl(panel, client);
  }

  postStats(stats: unknown): void {
    void this.panel.webview.postMessage({ type: "stats", data: stats });
  }

  postLast(res: TranslateResult, intent: string): void {
    void this.panel.webview.postMessage({ type: "last", data: { ...res, intent } });
  }

  private async refresh(): Promise<void> {
    try {
      this.postStats(await this.client.call("stats"));
    } catch (err) {
      void this.panel.webview.postMessage({ type: "offline", message: (err as Error).message });
    }
    const root = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
    if (root) {
      try {
        void this.panel.webview.postMessage({ type: "advice", data: await this.client.call("advise", { root }) });
      } catch {
        /* consultor indisponível: o painel continua útil */
      }
    }
  }

  private async onMessage(m: Msg): Promise<void> {
    if (m.type === "refresh") return this.refresh();
    if (m.type === "studio") return void vscode.commands.executeCommand("codar.openStudio");
    if (m.type === "audit") return void vscode.commands.executeCommand("codar.auditFile");
    if (m.type === "apply") {
      const root = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
      if (!root) return;
      const { runAdvice } = await import("./extension");
      await runAdvice(root, m.id, m.option);
      setTimeout(() => void this.refresh(), 4000);
    }
  }

  private html(): string {
    const nonce = crypto.randomBytes(16).toString("base64");
    const csp = `default-src 'none'; style-src 'nonce-${nonce}'; script-src 'nonce-${nonce}';`;
    return `<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="${csp}">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style nonce="${nonce}">
  :root { --bg:#05040A; --grid:#0F0C1C; --amber:#FF4747; --orange:#F26500; --mint:#47FFA9; --green:#54ff8a;
          --cyan:#39d6c8; --blue:#5f7bff; --text:#f0b32a; --dim:#6b551f; --line:#7a5a14; }
  * { box-sizing: border-box; }
  body { margin:0; padding:16px; background:var(--bg); color:var(--text); font: 12px/1.45 ui-monospace, "Share Tech Mono", Consolas, monospace; }
  header { display:flex; justify-content:space-between; align-items:flex-start; gap:16px; flex-wrap:wrap; margin-bottom:14px; }
  h1 { margin:0; color:var(--mint); font: 700 34px/0.9 "Saira Condensed", "Arial Narrow", sans-serif; letter-spacing:.02em;
       text-shadow:0 0 8px rgba(71,255,169,.55); text-transform:uppercase; }
  h1 em { font-style: oblique 12deg; }
  .meta { color:var(--dim); text-align:right; } .meta b { color:var(--green); font-weight:normal; }
  .grid { display:grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap:12px; }
  .panel { border:1.5px solid var(--orange); border-radius:8px; padding:10px 12px 12px;
           background: radial-gradient(120% 140% at 0% 0%, rgba(240,179,42,.05), transparent 55%), var(--bg); min-width:0; }
  .tag { display:inline-block; border:1.5px solid var(--orange); border-radius:5px; padding:1px 8px; margin-bottom:8px;
         color:var(--amber); font-weight:700; text-transform:uppercase; text-shadow:0 0 6px currentColor; }
  .kv { display:flex; justify-content:space-between; gap:8px; } .kv span:first-child { color:var(--dim); text-transform:uppercase; }
  .kv span:last-child { color:var(--green); text-align:right; overflow-wrap:anywhere; }
  .gauge { height:4px; background:var(--grid); margin:6px 0 2px; position:relative; border-radius:2px; }
  .gauge i { position:absolute; inset:0 auto 0 0; background:linear-gradient(90deg,var(--orange),var(--amber)); border-radius:2px; }
  pre { margin:8px 0 0; padding:8px; background:var(--grid); color:#cfd6e6; overflow:auto; max-height:240px; border-left:2px solid var(--line); }
  .card { border-top:1px dashed var(--line); padding:8px 0; } .card:first-of-type { border-top:0; }
  .card h3 { margin:0 0 4px; font-size:12px; color:var(--amber); } .card h3.medium { color:var(--orange); } .card h3.low { color:var(--cyan); }
  .card p { margin:0 0 6px; color:var(--text); }
  .opt { margin:4px 0; } .opt small { display:block; color:var(--dim); margin:2px 0 4px; }
  button { font:inherit; background:var(--bg); color:var(--mint); border:1.5px solid var(--mint); border-radius:5px; padding:3px 10px;
           cursor:pointer; text-transform:uppercase; } button:hover { background:var(--grid); box-shadow:0 0 8px rgba(71,255,169,.35); }
  button.ghost { color:var(--amber); border-color:var(--orange); }
  .bar { display:flex; gap:8px; flex-wrap:wrap; margin-top:12px; }
  .off { color:var(--amber); } .muted { color:var(--dim); } .ok { color:var(--mint); } .full { grid-column: 1 / -1; }
  @media (max-width: 480px) { h1 { font-size:26px; } .meta { text-align:left; } }
</style></head>
<body>
<header>
  <div><span class="tag">codar</span><h1><em>Intent</em> → code<br>mission control</h1></div>
  <div class="meta">SRC · <b>S0 COMPILER</b> · <b>S1 BANK</b> · <b>S2 SLM</b><br>OFFLINE · <span id="clock"></span></div>
</header>
<div class="grid">
  <section class="panel"><span class="tag">telemetria</span><div id="stats" class="muted">conectando ao daemon…</div></section>
  <section class="panel"><span class="tag">last translation</span><div id="last" class="muted">nenhuma tradução ainda — Ctrl+Alt+Enter numa linha, ou espaço+Enter no fim de uma frase.</div></section>
  <section class="panel full"><span class="tag">consultor de projeto</span><div id="advice" class="muted">analisando o projeto…</div></section>
</div>
<div class="bar"><button id="refresh">↻ atualizar</button><button class="ghost" id="audit">auditar arquivo</button><button class="ghost" id="studio">abrir studio (terminal)</button></div>
<script nonce="${nonce}">
  const vscode = acquireVsCodeApi();
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const kv = (k, v) => '<div class="kv"><span>' + esc(k) + '</span><span>' + esc(v) + '</span></div>';
  const tick = () => { $("clock").textContent = new Date().toISOString().slice(0, 16).replace("T", " ") + "Z"; };
  tick(); setInterval(tick, 30000);
  $("refresh").onclick = () => vscode.postMessage({ type: "refresh" });
  $("audit").onclick = () => vscode.postMessage({ type: "audit" });
  $("studio").onclick = () => vscode.postMessage({ type: "studio" });
  window.addEventListener("message", (ev) => {
    const m = ev.data;
    if (m.type === "offline") $("stats").innerHTML = '<span class="off">DAEMON OFFLINE</span> — ' + esc(m.message);
    if (m.type === "stats") {
      const s = m.data, mem = s.memory || {}, mod = s.model || {}, pat = s.patterns || {};
      const pct = Math.min(100, (100 * (mem.total_mb || 0)) / (mem.budget_mb || 1));
      let h = kv("ram", Math.round(mem.total_mb || 0) + " / " + mem.budget_mb + " MB") + '<div class="gauge"><i id="gauge"></i></div>';
      h += kv("pico", Math.round(mem.peak_mb || 0) + " MB") + kv("teto", mem.enforcement || "-");
      h += kv("modelo", (mod.name || "-") + (mod.loaded ? " ● carregado" : " ○ em espera"));
      h += kv("banco", (pat.patterns || 0) + " padrões · " + (s.rules || 0) + " regras");
      for (const [k, v] of Object.entries(s.stages || {})) h += kv("estágio " + k, "n=" + v.n + " p50=" + v.p50_ms + "ms");
      $("stats").innerHTML = h;
      $("gauge").style.width = pct + "%"; // CSSOM: permitido pela CSP (atributo style inline não seria)
    }
    if (m.type === "last") {
      const r = m.data;
      $("last").innerHTML = kv("intenção", r.intent) + kv("estágio", r.stage) + kv("fonte", r.source) +
        kv("latência", (r.timings.total_ms || 0).toFixed(2) + " ms") + kv("auditoria", r.findings.length ? r.findings.length + " achado(s)" : "✓ limpo") +
        "<pre>" + esc(r.code) + "</pre>";
    }
    if (m.type === "advice") {
      const sugs = m.data.suggestions || [];
      if (!sugs.length) { $("advice").innerHTML = '<span class="ok">✓ nenhuma sugestão — projeto em ordem</span>'; return; }
      $("advice").innerHTML = sugs.map((s) => '<div class="card"><h3 class="' + esc(s.impact) + '">▶ ' + esc(s.title) + '</h3><p>' + esc(s.reason) + '</p>' +
        s.options.map((o) => '<div class="opt"><button data-id="' + esc(s.id) + '" data-opt="' + esc(o.id) + '">✓ ' + esc(o.label) + '</button>' +
          (o.reason ? '<small>' + esc(o.reason) + '</small>' : '') + '<small>' + o.steps.map(esc).join(" · ") + '</small></div>').join("") + '</div>').join("");
      for (const b of document.querySelectorAll("button[data-id]")) {
        b.onclick = () => vscode.postMessage({ type: "apply", id: b.dataset.id, option: b.dataset.opt });
      }
    }
  });
</script>
</body></html>`;
  }
}
