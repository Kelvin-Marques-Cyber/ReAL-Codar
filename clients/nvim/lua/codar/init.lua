-- codar para Neovim: escreva a intenção em pseudocódigo e troque a linha pelo código, sem sair do editor.
--
--   require("codar").setup()          -- Ctrl+Enter ou Ctrl+G traduz a linha (normal) ou o bloco (visual);
--                                      -- no modo de inserção, termine a frase com espaço e aperte Enter
--   :Codar ler o nome do usuário       -- insere a tradução abaixo do cursor
--   :CodarAudit  :CodarAdvise  :CodarStatus  :CodarStudio
local rpc = require("codar.rpc")

local M = {}

M.config = {
  cmd = "codar", -- executável usado para subir o daemon (:CodarRestart, autostart) e abrir o Studio
  autostart = true, -- sobe o daemon na primeira tradução se ele não estiver rodando
  keymaps = true, -- Ctrl+Enter e Ctrl+G (normal/visual), Ctrl+Enter e Ctrl+G Ctrl+G (inserção)
  space_enter = true, -- linha que parece frase + espaço + Enter traduz a linha (como no VS Code)
  stages = { 0, 1, 2 }, -- 0 = compilador, 1 = banco de padrões, 2 = IA local
  hints = "diagnostics", -- diagnostics | comments | both | off
  imports = true, -- insere no topo do arquivo os imports que o código gerado precisa
  context_lines = 40, -- linhas acima do cursor enviadas como contexto
}

local ns = vim.api.nvim_create_namespace("codar")
local inflight = {} -- funções de cancelamento das requisições em andamento
M.last = nil -- último resultado (para :CodarLast)

local SEVERITY = {
  critical = vim.diagnostic.severity.ERROR,
  error = vim.diagnostic.severity.ERROR,
  warning = vim.diagnostic.severity.WARN,
  info = vim.diagnostic.severity.INFO,
}

local function notify(msg, level)
  vim.notify("codar: " .. msg, level or vim.log.levels.INFO)
end

local function request(method, params, cb, on_notify)
  local key = {}
  local cancel
  cancel = rpc.request(M.config, method, params, function(err, res)
    inflight[key] = nil
    cb(err, res)
  end, on_notify)
  inflight[key] = cancel
  return cancel
end

local function indent_unit(buf)
  if vim.bo[buf].expandtab then
    local sw = vim.bo[buf].shiftwidth
    return string.rep(" ", sw > 0 and sw or vim.bo[buf].tabstop)
  end
  return "\t"
end

local function comment_prefix(buf)
  local cs = vim.bo[buf].commentstring
  return (cs ~= "" and cs:match("^(.-)%s*%%s") or "#")
end

-- Linha onde os imports entram: depois de shebang, package, <?php e dos imports que já existem.
local IMPORT_LINE = {
  "^#!", "^package%s", "^<%?php", "^[\"']use strict[\"']",
  "^import%s", "^from%s+%S+%s+import%s", "^using%s+[%w%.]+;", "^#include%s", "^use%s+.+;",
  "^require[%s%(]", "^const%s+%w+%s*=%s*require%(", "^local%s+%w+%s*=%s*require",
}

local function import_edit(buf, imports)
  if not M.config.imports or not imports or #imports == 0 then
    return nil
  end
  local lines = vim.api.nvim_buf_get_lines(buf, 0, -1, false)
  local present = {}
  for _, l in ipairs(lines) do
    present[vim.trim(l)] = true
  end
  local missing = {}
  for _, imp in ipairs(imports) do
    if not present[vim.trim(imp)] then
      missing[#missing + 1] = imp
    end
  end
  if #missing == 0 then
    return nil
  end
  local at = 0
  for i = 1, math.min(#lines, 200) do
    local t = vim.trim(lines[i])
    for _, pat in ipairs(IMPORT_LINE) do
      if t:find(pat) then
        at = i
        break
      end
    end
  end
  if at == 0 and lines[1] and vim.trim(lines[1]) ~= "" then
    missing[#missing + 1] = "" -- separa os imports do código
  end
  return { row = at, lines = missing }
end

local function with_hints(buf, body_lines, findings)
  local prefix = comment_prefix(buf)
  local by_line = {}
  for _, f in ipairs(findings) do
    local l = math.max(1, f.body_line or f.line or 1)
    by_line[l] = by_line[l] or {}
    table.insert(by_line[l], f)
  end
  local out = {}
  for i, text in ipairs(body_lines) do
    local indent = text:match("^%s*")
    for _, f in ipairs(by_line[i] or {}) do
      out[#out + 1] = ("%s%s Dica [%s]: %s%s"):format(indent, prefix, f.id, f.message,
        f.suggestion and (" — " .. f.suggestion) or "")
    end
    out[#out + 1] = text
  end
  return out
end

local function set_diagnostics(buf, findings, first_row)
  local diags = {}
  for _, f in ipairs(findings or {}) do
    diags[#diags + 1] = {
      lnum = first_row + math.max(1, f.body_line or f.line or 1) - 1,
      col = math.max(0, (f.col or 1) - 1),
      severity = SEVERITY[f.severity] or vim.diagnostic.severity.HINT,
      message = f.message .. (f.suggestion and ("\n→ " .. f.suggestion) or ""),
      source = "codar",
      code = f.id,
    }
  end
  vim.diagnostic.set(ns, buf, diags)
end

local function show_scratch(code, ft, title)
  vim.cmd("botright new")
  local b = vim.api.nvim_get_current_buf()
  vim.bo[b].buftype = "nofile"
  vim.bo[b].bufhidden = "wipe"
  vim.bo[b].filetype = ft
  vim.api.nvim_buf_set_name(b, title)
  vim.api.nvim_buf_set_lines(b, 0, -1, false, vim.split(code, "\n", { plain = true }))
end

local function spinner(buf, row)
  local id = vim.api.nvim_buf_set_extmark(buf, ns, row, 0, {
    virt_text = { { "  ⟳ codar…", "Comment" } },
    virt_text_pos = "eol",
  })
  local tokens = 0
  return {
    tick = function()
      tokens = tokens + 1
      if tokens % 4 == 0 and vim.api.nvim_buf_is_valid(buf) then
        pcall(vim.api.nvim_buf_set_extmark, buf, ns, row, 0, {
          id = id, virt_text = { { ("  ⟳ codar… %d tokens"):format(tokens), "Comment" } }, virt_text_pos = "eol",
        })
      end
    end,
    stop = function()
      if vim.api.nvim_buf_is_valid(buf) then
        pcall(vim.api.nvim_buf_del_extmark, buf, ns, id)
      end
    end,
  }
end

--- Traduz as linhas [first, last] (0-based, inclusivas). mode: "line" | "block" | "insert".
local function translate(buf, first, last, intent, mode)
  if vim.trim(intent) == "" then
    return notify("nada para traduzir: escreva a intenção na linha", vim.log.levels.WARN)
  end
  local original = vim.api.nvim_buf_get_lines(buf, first, last + 1, false)
  local tick = vim.api.nvim_buf_get_changedtick(buf)
  local indent = mode == "insert" and "" or (original[1] or ""):match("^%s*")
  local ctx_from = math.max(0, first - M.config.context_lines)
  local before = table.concat(vim.api.nvim_buf_get_lines(buf, ctx_from, first, false), "\n")
  local file = vim.api.nvim_buf_get_name(buf)
  local ft = vim.bo[buf].filetype
  local spin = spinner(buf, first)

  request("translate", {
    intent = intent,
    lang = ft ~= "" and ft or nil,
    context = {
      file = file ~= "" and file or nil,
      before = before ~= "" and (before .. "\n") or "",
      indent = indent,
      indent_unit = indent_unit(buf),
    },
    options = {
      stages = M.config.stages,
      audit = M.config.hints ~= "off",
      mode = mode == "block" and "block" or "auto",
      stream = true,
    },
  }, function(err, res)
    spin.stop()
    if err then
      if err.code == -32800 then
        return notify("cancelado")
      end
      local msg = err.message
      if err.code == -32004 and err.data and err.data.candidates and #err.data.candidates > 0 then
        local c = {}
        for i = 1, math.min(3, #err.data.candidates) do
          local cand = err.data.candidates[i]
          c[#c + 1] = ("%s (%.2f) %s"):format(cand.id, cand.score, cand.title)
        end
        msg = msg .. "\nparecidos: " .. table.concat(c, " · ")
      end
      return notify(msg, vim.log.levels.WARN)
    end
    M.last = { intent = intent, result = res, ft = ft }
    if not vim.api.nvim_buf_is_valid(buf) then
      return
    end
    -- atomicidade: se o trecho mudou enquanto o daemon respondia, não sobrescreve; mostra o código ao lado
    if vim.api.nvim_buf_get_changedtick(buf) ~= tick
        and not vim.deep_equal(vim.api.nvim_buf_get_lines(buf, first, last + 1, false), original) then
      notify("o texto mudou enquanto o codar respondia; o código abriu numa janela ao lado", vim.log.levels.WARN)
      return show_scratch(res.code, ft, "codar://resultado")
    end

    local body = vim.split(res.body, "\n", { plain = true })
    if (M.config.hints == "comments" or M.config.hints == "both") and #res.findings > 0 then
      body = with_hints(buf, body, res.findings)
    end
    local imp = import_edit(buf, res.imports)
    local first_row
    vim.api.nvim_buf_call(buf, function()
      vim.cmd("let &undolevels = &undolevels") -- a tradução vira um passo próprio de desfazer
      if mode == "insert" then
        local cur = original[1] or ""
        local base = cur:match("^%s*")
        for i, l in ipairs(body) do
          body[i] = l ~= "" and (base .. l) or l
        end
        if vim.trim(cur) ~= "" then
          vim.api.nvim_buf_set_lines(buf, first + 1, first + 1, false, body)
          first_row = first + 1
        else
          vim.api.nvim_buf_set_lines(buf, first, first + 1, false, body)
          first_row = first
        end
      else
        vim.api.nvim_buf_set_lines(buf, first, last + 1, false, body)
        first_row = first
      end
      if imp then
        vim.cmd("undojoin") -- código e imports num único passo de desfazer (u)
        vim.api.nvim_buf_set_lines(buf, imp.row, imp.row, false, imp.lines)
        if imp.row <= first_row then
          first_row = first_row + #imp.lines
        end
      end
    end)
    if M.config.hints == "diagnostics" or M.config.hints == "both" then
      set_diagnostics(buf, res.findings, first_row)
    end
    if vim.api.nvim_get_current_buf() == buf then
      local last_row = first_row + #body - 1
      vim.api.nvim_win_set_cursor(0, { last_row + 1, #(body[#body] or "") })
    end
    local stage = ({ ["0"] = "compilador", ["1"] = "banco de padrões", ["2"] = "IA", ["2:pseudo"] = "IA literal" })[res.stage]
      or res.stage
    local ms = res.timings and res.timings.total_ms or 0
    vim.api.nvim_echo({ { ("codar: %s · %s · %.1f ms"):format(stage or "?", res.source, ms), "Comment" } }, false, {})
    if res.file_suggestion and res.file_suggestion.path then
      notify(("este padrão é um arquivo do projeto (%s); use :CodarLast para abri-lo à parte"):format(
        res.file_suggestion.path))
    end
  end, function()
    spin.tick()
  end)
end

function M.translate_line()
  local buf = vim.api.nvim_get_current_buf()
  local row = vim.api.nvim_win_get_cursor(0)[1] - 1
  local line = vim.api.nvim_buf_get_lines(buf, row, row + 1, false)[1] or ""
  translate(buf, row, row, vim.trim(line), "line")
end

function M.translate_range(first, last)
  local buf = vim.api.nvim_get_current_buf()
  local lines = vim.api.nvim_buf_get_lines(buf, first, last + 1, false)
  if first == last then
    return translate(buf, first, last, vim.trim(lines[1] or ""), "line")
  end
  translate(buf, first, last, table.concat(lines, "\n"), "block")
end

function M.translate_input(intent)
  local buf = vim.api.nvim_get_current_buf()
  local row = vim.api.nvim_win_get_cursor(0)[1] - 1
  translate(buf, row, row, intent, "insert")
end

function M.audit()
  local buf = vim.api.nvim_get_current_buf()
  local code = table.concat(vim.api.nvim_buf_get_lines(buf, 0, -1, false), "\n") .. "\n"
  request("audit", { code = code, lang = vim.bo[buf].filetype }, function(err, res)
    if err then
      return notify(err.message, vim.log.levels.ERROR)
    end
    if not vim.api.nvim_buf_is_valid(buf) then
      return
    end
    set_diagnostics(buf, res.findings, 0)
    notify(("%d achado(s) em %.1f ms"):format(#res.findings, res.ms or 0))
  end)
end

function M.status()
  request("stats", nil, function(err, s)
    if err then
      return notify(err.message, vim.log.levels.ERROR)
    end
    local m, mem = s.model or {}, s.memory or {}
    local lines = {
      ("daemon %s · pid %s · %ds no ar · %d requisições"):format(s.version or "?", s.pid or "?", s.uptime_s or 0,
        s.requests or 0),
      ("RAM %.0f / %d MB (pico %.0f MB, nível %s)"):format(mem.total_mb or 0, mem.budget_mb or 0, mem.peak_mb or 0,
        mem.level or "?"),
      ("modelo %s · %s"):format(m.name or "nenhum", m.loaded and "carregado" or "descarregado (carrega na próxima IA)"),
    }
    vim.api.nvim_echo({ { table.concat(lines, "\n") } }, true, {})
  end)
end

local function run_in_terminal(argv)
  vim.cmd("botright 14split")
  if vim.fn.has("nvim-0.11") == 1 then
    vim.cmd("enew")
    vim.fn.jobstart(argv, { term = true })
  else
    vim.fn.termopen(argv)
  end
  vim.cmd("startinsert")
end

function M.advise()
  local root = vim.fn.getcwd()
  request("advise", { root = root }, function(err, res)
    if err then
      return notify(err.message, vim.log.levels.ERROR)
    end
    local items = res.suggestions or {}
    if #items == 0 then
      return notify("nenhuma sugestão para " .. root)
    end
    vim.ui.select(items, {
      prompt = "codar: sugestões para o projeto",
      format_item = function(s)
        return s.title .. " — " .. s.reason
      end,
    }, function(s)
      if not s then
        return
      end
      local function apply(opt)
        local argv = { M.config.cmd, "advise", root, "--apply", s.id }
        if opt then
          vim.list_extend(argv, { "--option", opt.id })
        end
        run_in_terminal(argv) -- o comando mostra cada passo e pede confirmação antes de executar
      end
      local opts = s.options or {}
      if #opts <= 1 then
        return apply(opts[1])
      end
      vim.ui.select(opts, {
        prompt = s.title,
        format_item = function(o)
          return o.label .. (o.recommended and " (recomendado)" or "")
        end,
      }, function(o)
        if o then
          apply(o)
        end
      end)
    end)
  end)
end

function M.cancel()
  local n = 0
  for key, cancel in pairs(inflight) do
    cancel()
    inflight[key] = nil
    n = n + 1
  end
  notify(n > 0 and ("%d requisição(ões) cancelada(s)"):format(n) or "nada em andamento")
end

function M.show_last()
  if not M.last then
    return notify("nenhuma tradução ainda", vim.log.levels.WARN)
  end
  show_scratch(M.last.result.code, M.last.ft, "codar://" .. M.last.intent:gsub("%s+", "_"):sub(1, 40))
end

function M.restart()
  rpc.disconnect()
  vim.system({ M.config.cmd, "restart" }, { text = true }, function(res)
    vim.schedule(function()
      notify(res.code == 0 and "daemon reiniciado" or ("falhou: " .. vim.trim(res.stderr)),
        res.code == 0 and vim.log.levels.INFO or vim.log.levels.ERROR)
    end)
  end)
end

function M.studio()
  local file = vim.api.nvim_buf_get_name(0)
  vim.cmd("tabnew")
  local argv = { M.config.cmd, "studio" }
  if file ~= "" then
    argv[#argv + 1] = file
  end
  if vim.fn.has("nvim-0.11") == 1 then
    vim.fn.jobstart(argv, { term = true })
  else
    vim.fn.termopen(argv)
  end
  vim.cmd("startinsert")
end

-- Mesma regra de codar.textutil.looks_like_intent (Python), do VS Code e do Vim: mude as quatro juntas.
local CODE_KEYWORDS = {}
for w in ([[return import from print const let var function def class if else elif for while in not and or pass
  break continue echo local then do end fi done new public private static void int string fn func package use using
  include require try catch except finally throw raise yield await async self this null none true false nil match
  case switch default struct enum interface type val mut]]):gmatch("%S+") do
  CODE_KEYWORDS[w] = true
end

--- A linha é uma frase (pseudocódigo) e não código? "x é igual a 10" sim, "for i in range(3):" não.
function M.looks_like_intent(line)
  local text = vim.trim(line)
  for _, prefix in ipairs({ "//", "#", "--", ";" }) do
    if text:sub(1, #prefix) == prefix then
      text = vim.trim(text:sub(#prefix + 1))
      break
    end
  end
  if vim.fn.strchars(text) < 5 or text:find("[{}:;%(%)%[%],=\\%+%-%*/<>]$") then
    return false
  end
  local _, open = text:gsub("%(", "")
  local _, close = text:gsub("%)", "")
  if open ~= close then
    return false
  end
  local tokens, words = 0, {}
  for tok in text:gmatch("%S+") do
    tokens = tokens + 1
    local w = tok:gsub("^['\".,!?]+", ""):gsub("['\".,!?]+$", "")
    if w ~= "" and w:match("^[%a\128-\255]+$") then -- bytes >= 128: letras acentuadas em UTF-8
      words[#words + 1] = w
    end
  end
  if tokens < 2 or #words * 2 < tokens then
    return false
  end
  for _, w in ipairs(words) do
    if vim.fn.strchars(w) >= 3 and not CODE_KEYWORDS[w:lower()] then
      return true
    end
  end
  return false
end

-- Espaço + Enter: o Enter acontece normalmente (nvim-cmp, autopairs etc. continuam funcionando); logo depois,
-- se a linha de cima termina em espaço e parece uma frase, a quebra é desfeita e a linha é traduzida.
local line_count = {}

local function after_enter(buf)
  local n = vim.api.nvim_buf_line_count(buf)
  local before = line_count[buf]
  line_count[buf] = n
  if not before or n ~= before + 1 or vim.bo[buf].buftype ~= "" then
    return
  end
  local row = vim.api.nvim_win_get_cursor(0)[1] -- 1-based: a linha nova
  if row < 2 then
    return
  end
  local lines = vim.api.nvim_buf_get_lines(buf, row - 2, row, false)
  local intent, new = lines[1], lines[2]
  if not (intent and new and intent:sub(-1) == " " and new:match("^%s*$") and M.looks_like_intent(intent)) then
    return
  end
  -- Sai do modo de inserção antes de mexer nas linhas: ao sair, o Vim apaga a indentação automática da linha
  -- do cursor, e ela precisa ser a linha nova (vazia), não a frase.
  vim.cmd("stopinsert")
  local function apply(tries)
    if not vim.api.nvim_buf_is_valid(buf) then
      return
    end
    if vim.api.nvim_get_mode().mode:sub(1, 1) == "i" and tries > 0 then
      return vim.defer_fn(function()
        apply(tries - 1)
      end, 10)
    end
    if vim.trim(vim.api.nvim_buf_get_lines(buf, row - 1, row, false)[1] or "x") == "" then
      vim.api.nvim_buf_set_lines(buf, row - 1, row, false, {}) -- desfaz a quebra de linha
    end
    line_count[buf] = vim.api.nvim_buf_line_count(buf)
    if vim.api.nvim_get_current_buf() == buf then
      vim.api.nvim_win_set_cursor(0, { row - 1, 0 })
    end
    translate(buf, row - 2, row - 2, vim.trim(intent), "line")
  end
  vim.schedule(function()
    apply(20)
  end)
end

local function translate_visual()
  local a, b = vim.fn.line("v"), vim.fn.line(".")
  vim.api.nvim_feedkeys(vim.api.nvim_replace_termcodes("<Esc>", true, false, true), "nx", false)
  M.translate_range(math.min(a, b) - 1, math.max(a, b) - 1)
end

local function translate_from_insert()
  vim.cmd("stopinsert")
  M.translate_line()
end

function M.setup(opts)
  M.config = vim.tbl_deep_extend("force", M.config, opts or {})
  if M.config.keymaps then
    -- Ctrl+Enter onde o terminal distingue a tecla (kitty, WezTerm, foot, Ghostty, Neovide…); Ctrl+G em qualquer um
    for _, key in ipairs({ "<C-CR>", "<C-g>" }) do
      vim.keymap.set("n", key, M.translate_line, { desc = "codar: traduzir a linha" })
      vim.keymap.set("x", key, translate_visual, { desc = "codar: traduzir o bloco selecionado" })
    end
    vim.keymap.set("i", "<C-CR>", translate_from_insert, { desc = "codar: traduzir a linha" })
    vim.keymap.set("i", "<C-g><C-g>", translate_from_insert, { desc = "codar: traduzir a linha" })
  end
  if M.config.space_enter then
    local group = vim.api.nvim_create_augroup("codar_space_enter", { clear = true })
    vim.api.nvim_create_autocmd("InsertEnter", {
      group = group,
      callback = function(ev)
        line_count[ev.buf] = vim.api.nvim_buf_line_count(ev.buf)
      end,
    })
    vim.api.nvim_create_autocmd("TextChangedI", {
      group = group,
      callback = function(ev)
        after_enter(ev.buf)
      end,
    })
    vim.api.nvim_create_autocmd("BufWipeout", {
      group = group,
      callback = function(ev)
        line_count[ev.buf] = nil
      end,
    })
  end
end

return M
