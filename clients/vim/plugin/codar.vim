" codar para Vim 8+: escreva a intenção em pseudocódigo e troque a linha pelo código.
" Usa o CLI (`codar run --json`) em segundo plano; o daemon sobe sozinho na primeira chamada.
if exists('g:loaded_codar') || !has('job') || !has('channel')
  finish
endif
let g:loaded_codar = 1

let g:codar_cmd = get(g:, 'codar_cmd', 'codar')
let g:codar_context_lines = get(g:, 'codar_context_lines', 40)
let g:codar_imports = get(g:, 'codar_imports', 1)

command! -range -nargs=* Codar call codar#command(<line1>, <line2>, <range>, <q-args>)
command! CodarAudit call codar#audit()
command! CodarStatus call codar#status()

" Ctrl+Enter onde o terminal distingue a tecla (xterm com modifyOtherKeys, kitty, gVim…); Ctrl+G em qualquer um.
if get(g:, 'codar_keymaps', 1)
  for s:key in ['<C-CR>', '<C-g>']
    execute 'nnoremap <silent> ' . s:key . " :<C-u>call codar#translate(line('.'), line('.'))<CR>"
    execute 'xnoremap <silent> ' . s:key . " :<C-u>call codar#translate(line(\"'<\"), line(\"'>\"))<CR>"
  endfor
  inoremap <silent> <C-CR> <Esc>:call codar#translate(line('.'), line('.'))<CR>
endif

" Linha que parece frase + espaço + Enter traduz a linha (desligue com let g:codar_space_enter = 0).
if get(g:, 'codar_space_enter', 1)
  augroup codar_space_enter
    autocmd!
    autocmd InsertEnter * let b:codar_lines = line('$')
    autocmd TextChangedI * call codar#after_enter()
  augroup END
endif
