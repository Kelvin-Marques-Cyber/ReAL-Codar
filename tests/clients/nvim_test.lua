-- Teste do plugin do Neovim contra um daemon real. Rode com tests/clients/run.sh.
local root = vim.fn.fnamemodify(debug.getinfo(1, "S").source:sub(2), ":p:h:h:h")
vim.opt.rtp:prepend(root .. "/clients/nvim")
vim.cmd("runtime plugin/codar.lua")
local codar = require("codar")
codar.setup({ cmd = vim.env.CODAR_CMD or "codar" })

local log, fails = {}, 0
local function check(name, cond, extra)
  log[#log + 1] = (cond and "OK    " or "FALHA ") .. name .. (extra and ("  " .. extra) or "")
  if not cond then fails = fails + 1 end
end
local function buffer(ft, lines)
  vim.cmd("enew!")
  local b = vim.api.nvim_get_current_buf()
  vim.bo[b].filetype = ft
  vim.bo[b].expandtab = ft ~= "go"
  vim.bo[b].shiftwidth = 4
  vim.api.nvim_buf_set_lines(b, 0, -1, false, lines)
  vim.cmd("let &undolevels = &undolevels") -- como se o usuário tivesse acabado de digitar
  return b
end
local function lines(b) return vim.api.nvim_buf_get_lines(b, 0, -1, false) end
local function wait_change(b, before)
  return vim.wait(60000, function() return not vim.deep_equal(lines(b), before) end, 20)
end

-- mesma tabela de tests/test_routing.py
for _, l in ipairs({ "x é igual a 10", "x é igual a y mais 1", "total += preco", "imprimir o tamanho de pedidos",
  "some os dois números e imprima", "se total maior que 100 imprimir 'caro'", "# calcular a média das notas",
  "x vale 10", "print total", "imprimir total" }) do
  check("frase: " .. l, codar.looks_like_intent(l))
end
for _, l in ipairs({ "for i in range(10):", "return x + y", "import os", "console.log(x)", "if x > 10", "pass",
  "x = 1", "}", "elif x == 2:", "foo(bar, baz)", "let x = [1, 2]", "é", "i += 1" }) do
  check("código: " .. l, not codar.looks_like_intent(l))
end

local b = buffer("python", { "x = 10", "y = 20", "imprima a soma de x e y" })
vim.api.nvim_win_set_cursor(0, { 3, 0 })
local before = lines(b)
codar.translate_line()
check("python: linha com contexto", wait_change(b, before) and lines(b)[3] == "print(x + y)", vim.inspect(lines(b)))

b = buffer("go", { "package main", "", "func main() {", "\timprimir o tamanho de pedidos", "}" })
vim.api.nvim_win_set_cursor(0, { 4, 0 })
before = lines(b)
codar.translate_line()
wait_change(b, before)
check("go: import no topo + indentação", vim.deep_equal(lines(b),
  { "package main", 'import "fmt"', "", "func main() {", "\tfmt.Println(len(pedidos))", "}" }), vim.inspect(lines(b)))
vim.cmd("normal! u")
check("go: um único u desfaz código e import", vim.deep_equal(lines(b), before), vim.inspect(lines(b)))

b = buffer("javascript", { "para cada nome em nomes", "    imprimir nome" })
before = lines(b)
codar.translate_range(0, 1)
wait_change(b, before)
check("js: bloco", vim.deep_equal(lines(b), { "for (const nome of nomes) {", "    console.log(nome);", "}" }),
  vim.inspect(lines(b)))

b = buffer("python", { "def f(itens):", "    total = 0" })
vim.api.nvim_win_set_cursor(0, { 2, 0 })
before = lines(b)
vim.cmd("Codar total += preco")
wait_change(b, before)
check(":Codar insere abaixo", vim.deep_equal(lines(b), { "def f(itens):", "    total = 0", "    total += preco" }),
  vim.inspect(lines(b)))

b = buffer("python", { 'senha = "admin123"' })
codar.audit()
vim.wait(10000, function() return #vim.diagnostic.get(b) > 0 end, 20)
local d = vim.diagnostic.get(b)
check("auditoria vira diagnóstico", #d == 1 and d[1].code == "PY017", d[1] and d[1].message)

b = buffer("python", { "x é igual a 10" })
vim.api.nvim_win_set_cursor(0, { 1, 0 })
codar.translate_line()
vim.api.nvim_buf_set_lines(b, 0, 1, false, { "outra coisa" })
vim.wait(1500, function() return false end, 50)
check("não sobrescreve texto editado durante a resposta", lines(b)[1] == "outra coisa", vim.inspect(lines(b)))

local out = vim.env.CODAR_RESULT
log[#log + 1] = fails == 0 and "TUDO OK" or (fails .. " FALHA(S)")
if out and out ~= "" then vim.fn.writefile(log, out) else print(table.concat(log, "\n")) end
vim.cmd(fails == 0 and "qa!" or "cq!")
