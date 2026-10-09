// Testes de integração do cliente da extensão contra um daemon real (`codar start`).
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import test from "node:test";
import * as net from "node:net";

const { CodarClient, RpcError, discoverEndpoint, parseEndpoint } = createRequire(import.meta.url)("../out/client.js");

test("parseEndpoint entende unix, pipe e tcp", () => {
  assert.deepEqual(parseEndpoint("unix:/tmp/x.sock"), { transport: "unix", address: "/tmp/x.sock", token: "" });
  assert.equal(parseEndpoint("pipe:\\\\.\\pipe\\codar-ana").transport, "pipe");
  assert.equal(parseEndpoint("tcp://127.0.0.1:7878", "t").address, "127.0.0.1:7878");
});

const ep = discoverEndpoint();
test("daemon: ping, translate, audit, stats, erro e cancelamento", { skip: !ep && "daemon parado (rode codar start)" }, async () => {
  const c = new CodarClient({ autoStart: false });
  await c.connect();
  try {
    const pong = await c.call("ping");
    assert.equal(pong.pong, true);
    const r = await c.translate({ intent: "x é igual a 10", lang: "go", options: { stages: [0] } });
    assert.equal(r.stage, "0");
    assert.equal(r.code, "x := 10");
    const r2 = await c.translate({ intent: "função soma com a e b que retorna a + b", lang: "typescript",
      context: { indent: "  ", indent_unit: "  " }, options: { stages: [0] } });
    assert.match(r2.body, /^ {2}function soma\(a: number, b: number\): number \{/);
    const a = await c.call("audit", { code: "eval(x)", lang: "javascript" });
    assert.ok(a.findings.some((f) => f.id === "INJ010"));
    const s = await c.call("stats");
    assert.ok(s.memory.budget_mb > 0 && s.patterns.patterns > 50);
    await assert.rejects(c.translate({ intent: "xyzzy plugh quux", lang: "python", options: { stages: [0, 1] } }),
      (e) => e instanceof RpcError && e.code === -32004);
    await assert.rejects(c.call("nao.existe"), (e) => e instanceof RpcError && e.code === -32601);
    await assert.rejects(c.translate({ intent: "corrija", lang: "powershell",
      context: { selected: "$x = 1", after: "\nWrite-Output $x" }, options: { mode: "edit", stages: [0, 1] } }),
      (e) => e instanceof RpcError && e.code === -32004);
    const ac = new AbortController();
    ac.abort(); // cancelamento antes de enviar não depende de um modelo instalado nem da velocidade do servidor
    const pend = c.translate({ intent: "classe de fila circular com capacidade fixa e métodos enfileirar e desenfileirar",
      lang: "python" }, { signal: ac.signal });
    await assert.rejects(pend, (e) => e instanceof RpcError && e.code === -32800);
  } finally {
    c.dispose();
  }
});

test("cancelamento em andamento rejeita imediatamente e avisa o daemon", async () => {
  const ac = new AbortController();
  let socket;
  let resolveCancel;
  const cancelled = new Promise((resolve) => { resolveCancel = resolve; });
  const server = net.createServer((s) => {
    socket = s;
    let pending = "";
    s.on("data", (chunk) => {
      pending += chunk.toString();
      while (pending.includes("\n")) {
        const end = pending.indexOf("\n");
        const msg = JSON.parse(pending.slice(0, end));
        pending = pending.slice(end + 1);
        if (msg.method === "translate") ac.abort();
        if (msg.method === "$/cancelRequest") resolveCancel();
      }
    });
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const client = new CodarClient({ endpoint: `tcp://127.0.0.1:${server.address().port}`, autoStart: false });
  try {
    await assert.rejects(client.translate({ intent: "corrija", context: { selected: "x = 1" },
      options: { mode: "edit" } }, { signal: ac.signal }), (e) => e instanceof RpcError && e.code === -32800);
    await cancelled;
  } finally {
    client.dispose();
    socket?.destroy();
    await new Promise((resolve) => server.close(resolve));
  }
});

// Mesma tabela de tests/test_routing.py: as implementações em Python, TypeScript, Lua e Vim precisam concordar.
const { looksLikeIntent, wantsEdit } = createRequire(import.meta.url)("../out/intent.js");
const INTENT_LINES = ["x é igual a 10", "x é igual a y mais 1", "total += preco", "imprimir o tamanho de pedidos",
  "some os dois números e imprima", "se total maior que 100 imprimir 'caro'", "# calcular a média das notas",
  "x vale 10", "print total", "imprimir total"];
const CODE_LINES = ["for i in range(10):", "return x + y", "import os", "console.log(x)", "if x > 10", "pass", "x = 1",
  "}", "elif x == 2:", "foo(bar, baz)", "let x = [1, 2]", "é", "i += 1"];

test("looksLikeIntent: frases disparam, código não", () => {
  for (const l of INTENT_LINES) assert.equal(looksLikeIntent(l), true, l);
  for (const l of CODE_LINES) assert.equal(looksLikeIntent(l), false, l);
});

test("wantsEdit: sobrescrita explícita, criação continua inserindo", () => {
  for (const text of ["corrija meu código", "por favor, refatore", "complete a função"]) assert.equal(wantsEdit(text), true);
  for (const text of ["crie uma classe", "imprimir total"]) assert.equal(wantsEdit(text), false);
});

const { hoistImports } = createRequire(import.meta.url)("../out/imports.js");
test("imports preservam cabeçalhos, param e imports locais", () => {
  const ps = "[CmdletBinding()]\nparam([string] $Name = '(João)')\nWrite-Output $Name";
  assert.match(hoistImports(ps, ["Import-Module Microsoft.PowerShell.Utility"], "powershell").text,
    /^\[CmdletBinding\(\)\]\nparam[^\n]+\nImport-Module/);
  const python = '"""Descrição."""\nfrom __future__ import annotations\ndef f():\n    import sys\n    return sys.version';
  assert.match(hoistImports(python, ["import os", "import os"], "python").text,
    /^"""Descrição."""\nfrom __future__ import annotations\nimport os\n\ndef f/);
  const dart = hoistImports("library app;\nvoid main() {}", ["import 'dart:io';"], "dart", "\r\n");
  assert.ok(dart.text.startsWith("library app;\r\nimport 'dart:io';\r\n"));
});
