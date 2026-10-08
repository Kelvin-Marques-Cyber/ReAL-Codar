-- Comandos do codar. Carregam o módulo só quando usados; os atalhos vêm de require("codar").setup().
if vim.g.loaded_codar or vim.fn.has("nvim-0.10") == 0 then
  return
end
vim.g.loaded_codar = true

local function codar()
  return require("codar")
end

vim.api.nvim_create_user_command("Codar", function(o)
  if o.args ~= "" then
    codar().translate_input(o.args)
  elseif o.range > 0 then
    codar().translate_range(o.line1 - 1, o.line2 - 1)
  else
    codar().translate_line()
  end
end, { nargs = "*", range = true, desc = "codar: traduz a linha, o intervalo ou a intenção dada" })

vim.api.nvim_create_user_command("CodarAudit", function()
  codar().audit()
end, { desc = "codar: auditoria estática do buffer" })
vim.api.nvim_create_user_command("CodarAdvise", function()
  codar().advise()
end, { desc = "codar: sugestões para o projeto" })
vim.api.nvim_create_user_command("CodarStatus", function()
  codar().status()
end, { desc = "codar: RAM, modelo e estado do daemon" })
vim.api.nvim_create_user_command("CodarCancel", function()
  codar().cancel()
end, { desc = "codar: cancela a tradução em andamento" })
vim.api.nvim_create_user_command("CodarLast", function()
  codar().show_last()
end, { desc = "codar: mostra o último código gerado numa janela" })
vim.api.nvim_create_user_command("CodarRestart", function()
  codar().restart()
end, { desc = "codar: reinicia o daemon" })
vim.api.nvim_create_user_command("CodarStudio", function()
  codar().studio()
end, { desc = "codar: abre o Studio (TUI) numa aba" })
