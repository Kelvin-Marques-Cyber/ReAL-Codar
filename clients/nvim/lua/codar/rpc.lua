-- Cliente JSON-RPC 2.0 (uma mensagem JSON por linha) do daemon codar, sobre Unix socket, Named Pipe ou TCP
-- local, usando o libuv do próprio Neovim: nenhum processo é criado por tradução.
local uv = vim.uv or vim.loop

local M = {}

local is_win = vim.fn.has("win32") == 1
local conn -- conexão compartilhada (aberta sob demanda)

local function runtime_dir()
  local home = vim.env.CODAR_HOME
  if home and home ~= "" then
    return home .. "/run"
  end
  if is_win then
    local base = vim.env.LOCALAPPDATA or ((vim.env.USERPROFILE or "") .. "\\AppData\\Local")
    return base .. "\\codar\\run"
  end
  local xdg = vim.env.XDG_RUNTIME_DIR
  if xdg and xdg ~= "" and vim.fn.isdirectory(xdg) == 1 then
    return xdg .. "/codar"
  end
  local tmp = (vim.env.TMPDIR or vim.env.TEMP or vim.env.TMP or "/tmp"):gsub("/+$", "")
  return tmp .. "/codar-" .. uv.getuid()
end

local function parse_endpoint(spec, token)
  spec = vim.trim(spec)
  if spec:find("^tcp://") then
    return { transport = "tcp", address = spec:sub(7), token = token or "" }
  elseif spec:find("^unix:") then
    return { transport = "unix", address = spec:sub(6), token = token or "" }
  elseif spec:find("^pipe:") then
    return { transport = "pipe", address = spec:sub(6), token = token or "" }
  end
  return { transport = spec:find("^\\\\%.\\pipe\\") and "pipe" or "unix", address = spec, token = token or "" }
end

--- Endpoint do daemon em execução: $CODAR_ENDPOINT ou <runtime>/endpoint.json (gravado pelo daemon ao subir).
function M.endpoint()
  if vim.env.CODAR_ENDPOINT and vim.env.CODAR_ENDPOINT ~= "" then
    return parse_endpoint(vim.env.CODAR_ENDPOINT, vim.env.CODAR_TOKEN)
  end
  local fh = io.open(runtime_dir() .. "/endpoint.json", "r")
  if not fh then
    return nil
  end
  local ok, data = pcall(vim.json.decode, fh:read("*a"))
  fh:close()
  if not ok or type(data) ~= "table" or not data.address then
    return nil
  end
  return { transport = data.transport, address = data.address, token = data.token or "" }
end

local Conn = {}
Conn.__index = Conn

local function fail_all(self, message)
  local pending = self.pending
  self.pending = {}
  for _, p in pairs(pending) do
    p.cb({ code = -32000, message = message })
  end
end

function Conn:_dispatch(line)
  local ok, msg = pcall(vim.json.decode, line, { luanil = { object = true, array = true } })
  if not ok or type(msg) ~= "table" then
    return
  end
  if msg.id ~= nil and (msg.result ~= nil or msg.error ~= nil) then
    local p = self.pending[msg.id]
    if p then
      self.pending[msg.id] = nil
      p.cb(msg.error, msg.result)
    end
  elseif msg.method and msg.params and msg.params.id ~= nil then -- $/progress de uma requisição
    local p = self.pending[msg.params.id]
    if p and p.on_notify then
      p.on_notify(msg.method, msg.params)
    end
  end
end

function Conn:_read()
  self.handle:read_start(function(err, chunk)
    if err or not chunk then
      self:close()
      vim.schedule(function()
        fail_all(self, "o daemon fechou a conexão" .. (err and (": " .. err) or ""))
      end)
      return
    end
    self.buf = self.buf .. chunk
    local lines = {}
    while true do
      local nl = self.buf:find("\n", 1, true)
      if not nl then
        break
      end
      lines[#lines + 1] = self.buf:sub(1, nl - 1)
      self.buf = self.buf:sub(nl + 1)
    end
    if #lines > 0 then
      vim.schedule(function() -- a API do Neovim só pode ser usada fora do callback do libuv
        for _, l in ipairs(lines) do
          self:_dispatch(l)
        end
      end)
    end
  end)
end

function Conn:send(msg)
  if self.closed then
    return false
  end
  self.handle:write(vim.json.encode(msg) .. "\n")
  return true
end

function Conn:request(method, params, cb, on_notify)
  local id = self.next_id
  self.next_id = id + 1
  self.pending[id] = { cb = cb, on_notify = on_notify }
  if not self:send({ jsonrpc = "2.0", id = id, method = method, params = params or vim.empty_dict() }) then
    self.pending[id] = nil
    cb({ code = -32000, message = "conexão fechada" })
  end
  return id
end

function Conn:close()
  if not self.closed then
    self.closed = true
    if not self.handle:is_closing() then
      self.handle:close()
    end
  end
end

local function open(ep, cb)
  local handle
  local function done(err)
    vim.schedule(function()
      if err then
        if not handle:is_closing() then
          handle:close()
        end
        return cb(err)
      end
      local c = setmetatable({ handle = handle, buf = "", next_id = 1, pending = {}, closed = false }, Conn)
      c:_read()
      if ep.transport == "tcp" and ep.token ~= "" then
        c:request("auth", { token = ep.token }, function(aerr)
          if aerr then
            c:close()
            return cb("autenticação recusada: " .. aerr.message)
          end
          cb(nil, c)
        end)
      else
        cb(nil, c)
      end
    end)
  end
  if ep.transport == "tcp" then
    local host, port = ep.address:match("^(.*):(%d+)$")
    if not host then
      return cb("endpoint TCP inválido: " .. ep.address)
    end
    handle = uv.new_tcp()
    handle:connect(host, tonumber(port), done)
  else
    handle = uv.new_pipe(false)
    handle:connect(ep.address, done)
  end
end

--- Conecta (subindo o daemon com `<cmd> start` se ele não estiver rodando) e entrega a conexão a `cb(err, conn)`.
function M.connect(opts, cb)
  if conn and not conn.closed then
    return cb(nil, conn)
  end
  local function try(retry)
    local ep = M.endpoint()
    local function on_fail(err)
      if not retry or not opts.autostart then
        return cb(err or "daemon não está em execução (rode `codar start`)")
      end
      vim.notify("codar: subindo o daemon…", vim.log.levels.INFO)
      vim.system({ opts.cmd, "start" }, { text = true }, function(res)
        vim.schedule(function()
          if res.code ~= 0 then
            return cb("não consegui subir o daemon: " .. vim.trim(res.stderr ~= "" and res.stderr or res.stdout))
          end
          try(false)
        end)
      end)
    end
    if not ep then
      return on_fail(nil)
    end
    open(ep, function(err, c)
      if err then
        return on_fail("não conectou em " .. ep.address .. ": " .. err)
      end
      conn = c
      cb(nil, c)
    end)
  end
  local ok, err = pcall(try, true)
  if not ok then -- `cmd` fora do PATH, por exemplo
    cb(tostring(err))
  end
end

--- Faz uma requisição; `cb(err, result)`. Devolve uma função que cancela a requisição.
function M.request(opts, method, params, cb, on_notify)
  local cancelled, conn_ref, id = false, nil, nil
  M.connect(opts, function(err, c)
    if err then
      return cb({ code = -32000, message = err })
    end
    if cancelled then
      return cb({ code = -32800, message = "cancelado" })
    end
    conn_ref = c
    id = c:request(method, params, cb, on_notify)
  end)
  return function()
    cancelled = true
    if conn_ref and id then
      conn_ref:send({ jsonrpc = "2.0", method = "$/cancelRequest", params = { id = id } })
    end
  end
end

function M.disconnect()
  if conn then
    conn:close()
    conn = nil
  end
end

return M
