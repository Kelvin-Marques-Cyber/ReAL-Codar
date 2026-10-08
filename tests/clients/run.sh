#!/usr/bin/env bash
# Testes dos plugins de editor contra um daemon real. Uso: tests/clients/run.sh [caminho/do/codar]
# Usa nvim e vim do PATH (ou NVIM=/caminho VIM=/caminho). Linguagens sem editor instalado são puladas.
set -uo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
export CODAR_CMD="${1:-$(command -v codar)}"
[ -x "$CODAR_CMD" ] || { echo "codar não encontrado (passe o caminho como argumento)"; exit 2; }
"$CODAR_CMD" start >/dev/null || exit 2
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
status=0

run() {  # run <nome> <comando...>
  local name="$1"; shift
  CODAR_RESULT="$tmp/$name.txt" timeout 300 "$@" >/dev/null 2>&1
  if grep -q "TUDO OK" "$tmp/$name.txt" 2>/dev/null; then
    echo "$name: $(grep -c '^OK' "$tmp/$name.txt") checagens OK"
  else
    echo "$name: FALHOU"; grep -v '^OK' "$tmp/$name.txt" 2>/dev/null || echo "  (sem saída)"; status=1
  fi
}

NVIM="${NVIM:-$(command -v nvim || true)}"
VIM="${VIM:-$(command -v vim || true)}"
if [ -n "$NVIM" ]; then
  run neovim "$NVIM" --headless --clean -c "luafile $here/nvim_test.lua"
  # espaço + Enter digitado de verdade: um processo manda as teclas, uma de cada vez, para o Neovim
  sock="$tmp/nvim.sock"
  "$NVIM" --headless --clean --listen "$sock" -c "set rtp^=$here/../../clients/nvim" -c "runtime plugin/codar.lua" \
    -c "lua require('codar').setup({ cmd = '$CODAR_CMD' })" -c "setfiletype python" -c "setlocal et sw=4" \
    >/dev/null 2>&1 &
  sleep 1.5
  for keys in 'idef soma(itens):' '<CR>' 'total é igual a 0 ' '<CR>'; do
    "$NVIM" --server "$sock" --remote-send "$keys"; sleep 0.4
  done
  sleep 3
  got="$("$NVIM" --server "$sock" --remote-expr 'string(getline(1, "$"))')"
  "$NVIM" --server "$sock" --remote-send '<Esc>:qa!<CR>' >/dev/null 2>&1
  if [ "$got" = "['def soma(itens):', '    total = 0']" ]; then
    echo "neovim espaço + Enter: OK"
  else
    echo "neovim espaço + Enter: FALHOU ($got)"; status=1
  fi
else
  echo "neovim: pulado (nvim não encontrado)"
fi
if [ -n "$VIM" ]; then
  run vim "$VIM" -Nu NONE -i NONE --not-a-term -S "$here/vim_test.vim"
else
  echo "vim: pulado (vim não encontrado)"
fi
exit $status
