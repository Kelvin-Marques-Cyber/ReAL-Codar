" Teste do plugin do Vim contra um daemon real. Rode com tests/clients/run.sh (ou veja lá como chamar).
set nocompatible
let s:root = fnamemodify(expand('<sfile>:p'), ':h:h:h')
let &runtimepath = s:root . '/clients/vim,' . &runtimepath
let g:codar_cmd = $CODAR_CMD !=# '' ? $CODAR_CMD : 'codar'
runtime plugin/codar.vim
let s:log = []
let s:fails = 0

function! Check(name, cond, extra) abort
  call add(s:log, (a:cond ? 'OK    ' : 'FALHA ') . a:name . '  ' . a:extra)
  let s:fails += !a:cond
endfunction

function! Buf(ft, lines) abort
  enew!
  let &l:filetype = a:ft
  setlocal expandtab shiftwidth=4
  if a:ft ==# 'go' | setlocal noexpandtab | endif
  call setline(1, a:lines)
  let &undolevels = &undolevels
endfunction

function! WaitChange(before) abort
  let l:n = 0
  while getline(1, '$') == a:before && l:n < 600
    sleep 50m
    let l:n += 1
  endwhile
endfunction

" mesma tabela de tests/test_routing.py
for s:l in ['x é igual a 10', 'x é igual a y mais 1', 'total += preco', 'imprimir o tamanho de pedidos',
      \ 'some os dois números e imprima', "se total maior que 100 imprimir 'caro'", '# calcular a média das notas',
      \ 'x vale 10', 'print total', 'imprimir total']
  call Check('frase: ' . s:l, codar#looks_like_intent(s:l), '')
endfor
for s:l in ['for i in range(10):', 'return x + y', 'import os', 'console.log(x)', 'if x > 10', 'pass', 'x = 1', '}',
      \ 'elif x == 2:', 'foo(bar, baz)', 'let x = [1, 2]', 'é', 'i += 1']
  call Check('código: ' . s:l, !codar#looks_like_intent(s:l), '')
endfor

call Buf('python', ['x = 10', 'y = 20', 'imprima a soma de x e y'])
let s:b = getline(1, '$')
call cursor(3, 1) | call codar#translate(3, 3) | call WaitChange(s:b)
call Check('python: linha', getline(3) ==# 'print(x + y)', string(getline(1, '$')))

call Buf('go', ['package main', '', 'func main() {', "\timprimir o tamanho de pedidos", '}'])
let s:b = getline(1, '$')
call codar#translate(4, 4) | call WaitChange(s:b)
call Check('go: imports + indentação', getline(1, '$') == ['package main', 'import "fmt"', '', 'func main() {', "\tfmt.Println(len(pedidos))", '}'], string(getline(1, '$')))
silent normal! u
call Check('go: um u desfaz tudo', getline(1, '$') == s:b, string(getline(1, '$')))

call Buf('javascript', ['para cada nome em nomes', '    imprimir nome'])
let s:b = getline(1, '$')
call codar#translate(1, 2) | call WaitChange(s:b)
call Check('js: bloco', getline(1, '$') == ['for (const nome of nomes) {', '    console.log(nome);', '}'], string(getline(1, '$')))

call Buf('python', ['def f(itens):', '    total = 0'])
let s:b = getline(1, '$')
call cursor(2, 1) | Codar total += preco
call WaitChange(s:b)
call Check(':Codar insere abaixo', getline(1, '$') == ['def f(itens):', '    total = 0', '    total += preco'], string(getline(1, '$')))

" espaço + Enter: simula o estado logo depois do Enter (a linha nova já existe e o contador viu uma linha a menos)
call Buf('python', ['def soma(itens):', '    total é igual a 0 ', '    '])
let b:codar_lines = 2
call cursor(3, 5)
let s:b = getline(1, '$')
call codar#after_enter() | call WaitChange(s:b) | sleep 300m
call Check('espaço + Enter (indentado)', getline(1, '$') == ['def soma(itens):', '    total = 0'], string(getline(1, '$')))

call Buf('python', ['for i in range(10): ', '    '])
let b:codar_lines = 1
call cursor(2, 5) | call codar#after_enter() | sleep 300m
call Check('espaço + Enter ignora código', getline(1, '$') == ['for i in range(10): ', '    '], string(getline(1, '$')))

call Buf('python', ['senha = "admin123"'])
call setloclist(0, [])
call codar#audit()
let s:n = 0
while empty(getloclist(0)) && s:n < 200 | sleep 50m | let s:n += 1 | endwhile
let s:l = getloclist(0)
call Check('audit: loclist', len(s:l) == 1 && s:l[0].text =~# 'PY017', string(map(copy(s:l), 'v:val.text')))

for s:hoist in [1, 0]
  let g:codar_imports = s:hoist
  call Buf('python', ['x = 10', 'print(x)'])
  call cursor(2, 1)
  let s:b = getline(1, '$')
  Codar import de biblioteca de youtube
  call WaitChange(s:b)
  let s:expected = s:hoist ? ['from yt_dlp import YoutubeDL', '', 'x = 10', 'print(x)'] : ['x = 10', 'print(x)', 'from yt_dlp import YoutubeDL']
  call Check('importação sem programa; hoist=' . s:hoist, getline(1, '$') == s:expected, string(getline(1, '$')))
  silent normal! u
  call Check('um undo restaura importação; hoist=' . s:hoist, getline(1, '$') == s:b, string(getline(1, '$')))
endfor

call writefile(s:log + [s:fails ? s:fails . ' FALHA(S)' : 'TUDO OK'], $CODAR_RESULT !=# '' ? $CODAR_RESULT : '/dev/stdout')
qa!
