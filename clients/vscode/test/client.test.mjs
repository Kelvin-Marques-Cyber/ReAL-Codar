// Testes de integração do cliente da extensão contra um daemon real (`codar start`).
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import test from "node:test";

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
    const ac = new AbortController();
    const pend = c.translate({ intent: "classe de fila circular com capacidade fixa e métodos enfileirar e desenfileirar",
      lang: "python" }, { signal: ac.signal });
    setTimeout(() => ac.abort(), 50);
    await assert.rejects(pend, (e) => e instanceof RpcError && e.code === -32800);
  } finally {
    c.dispose();
  }
});

// Mesma tabela de tests/test_routing.py: as implementações em Python, TypeScript, Lua e Vim precisam concordar.
const { looksLikeIntent } = createRequire(import.meta.url)("../out/intent.js");
const INTENT_LINES = ["x é igual a 10", "x é igual a y mais 1", "total += preco", "imprimir o tamanho de pedidos",
  "some os dois números e imprima", "se total maior que 100 imprimir 'caro'", "# calcular a média das notas",
  "x vale 10", "print total", "imprimir total"];
const CODE_LINES = ["for i in range(10):", "return x + y", "import os", "console.log(x)", "if x > 10", "pass", "x = 1",
  "}", "elif x == 2:", "foo(bar, baz)", "let x = [1, 2]", "é", "i += 1"];

test("looksLikeIntent: frases disparam, código não", () => {
  for (const l of INTENT_LINES) assert.equal(looksLikeIntent(l), true, l);
  for (const l of CODE_LINES) assert.equal(looksLikeIntent(l), false, l);
});
