"""`codar shell-init <shell>`: imprime a integração do prompt (padrão: Ctrl+G traduz a linha atual).

    bash:  eval "$(codar shell-init bash)"            (~/.bashrc)
    zsh:   eval "$(codar shell-init zsh)"             (~/.zshrc)
    fish:  codar shell-init fish | source             (~/.config/fish/config.fish)
    pwsh:  Invoke-Expression (& codar shell-init pwsh | Out-String)   ($PROFILE)

A tecla pode ser trocada com CODAR_KEY (ex.: "\\C-x\\C-g" no bash). O mesmo eval também ativa o completar com Tab
(desligue com CODAR_NO_COMPLETION=1, por exemplo se o pacote do sistema já instalou as completações).
"""

from __future__ import annotations

import os
import sys

BASH = r'''# codar — Ctrl+G traduz a linha digitada em comando bash
__codar_widget() {
  local intent="$READLINE_LINE" out
  [[ -z "${intent//[[:space:]]/}" ]] && return
  out="$(command codar run --lang bash --quiet --no-audit -- "$intent" 2>/dev/null)" || return
  READLINE_LINE="$out"
  READLINE_POINT=${#READLINE_LINE}
}
bind -x '"__KEY__": __codar_widget'
'''

ZSH = r'''# codar — Ctrl+G traduz a linha digitada em comando
__codar_widget() {
  [[ -z "${BUFFER//[[:space:]]/}" ]] && return
  local out
  out="$(command codar run --lang bash --quiet --no-audit -- "$BUFFER" 2>/dev/null)" || return
  BUFFER="$out"
  CURSOR=${#BUFFER}
  zle redisplay
}
zle -N __codar_widget
bindkey '__KEY__' __codar_widget
'''

FISH = r'''# codar — Ctrl+G traduz a linha digitada (gera sintaxe bash; ideal para comandos simples)
function __codar_widget
    set -l intent (commandline)
    if test -z (string trim -- "$intent")
        return
    end
    set -l out (command codar run --lang bash --quiet --no-audit -- "$intent" 2>/dev/null | string collect)
    or return
    commandline -r -- $out
end
bind __KEY__ __codar_widget
'''

PWSH = r'''# codar — Ctrl+G traduz a linha digitada em PowerShell (PSReadLine)
# Para a integração completa (Named Pipe direto, sem processo extra) use o módulo Codar: Import-Module Codar
Set-PSReadLineKeyHandler -Chord '__KEY__' -BriefDescription 'codar' -Description 'Traduz a linha atual em PowerShell' -ScriptBlock {
    $line = $null
    $cursor = $null
    [Microsoft.PowerShell.PSConsoleReadLine]::GetBufferState([ref]$line, [ref]$cursor)
    if ([string]::IsNullOrWhiteSpace($line)) { return }
    $out = (& codar run --lang powershell --quiet --no-audit -- $line 2>$null) -join [Environment]::NewLine
    if ($LASTEXITCODE -eq 0 -and $out) {
        [Microsoft.PowerShell.PSConsoleReadLine]::Replace(0, $line.Length, $out)
    }
}
'''

DEFAULT_KEYS = {"bash": r"\C-g", "zsh": "^G", "fish": r"\cg", "pwsh": "Ctrl+g"}


def script(shell: str) -> str:
    shell = "pwsh" if shell == "powershell" else shell
    body = {"bash": BASH, "zsh": ZSH, "fish": FISH, "pwsh": PWSH}[shell]
    return body.replace("__KEY__", os.environ.get("CODAR_KEY") or DEFAULT_KEYS[shell])


def cmd_shell_init(args) -> int:
    sys.stdout.write(script(args.shell))
    shell = "pwsh" if args.shell == "powershell" else args.shell
    if shell in ("bash", "zsh", "fish") and not os.environ.get("CODAR_NO_COMPLETION"):
        from codar.cli.completion import script as completion

        sys.stdout.write("\n" + completion(shell))  # junto com o atalho: um único eval no .bashrc
    return 0
