" Implementação do plugin codar para Vim (carregada só no primeiro uso).

let s:import_line = '\v^(#!|package\s|\<\?php|[''"]use strict[''"]|import\s|from\s+\S+\s+import\s|using\s+[[:alnum:]_.]+;|#include\s|use\s+.+;|require[ (]|const\s+\w+\s*\=\s*require\(|local\s+\w+\s*\=\s*require)'

function! s:echo(msg, hl) abort
  execute 'echohl ' . a:hl
  echomsg 'codar: ' . a:msg
  echohl None
endfunction

" Roda `codar <args>` em segundo plano com `input` na entrada padrão; chama Done(saida, codigo_de_saida).
function! s:run(args, input, Done) abort
  let l:in = tempname()
  call writefile(split(a:input, "\n", 1), l:in, 'b')
  let l:ctx = {'out': [], 'err': [], 'Done': a:Done, 'files': [l:in], 'code': -1, 'closed': 0}
  function! l:ctx.finish() abort
    if self.closed && self.code >= 0
      for l:f in self.files
        call delete(l:f)
      endfor
      call self.Done(join(self.out, "\n"), self.code, join(self.err, "\n"))
    endif
  endfunction
  function! l:ctx.on_close(ch) abort
    let self.closed = 1
    call self.finish()
  endfunction
  function! l:ctx.on_exit(job, code) abort
    let self.code = a:code
    call self.finish()
  endfunction
  let l:job = job_start([g:codar_cmd] + a:args, {
        \ 'in_io': 'file', 'in_name': l:in,
        \ 'out_cb': {ch, msg -> add(l:ctx.out, msg)},
        \ 'err_cb': {ch, msg -> add(l:ctx.err, msg)},
        \ 'close_cb': l:ctx.on_close, 'exit_cb': l:ctx.on_exit,
        \ 'env': {'NO_COLOR': '1'},
        \ })
  if job_status(l:job) ==# 'fail'
    call s:echo('não consegui executar "' . g:codar_cmd . '" (ajuste g:codar_cmd)', 'ErrorMsg')
  endif
  return l:ctx
endfunction

function! s:hoist_imports(imports) abort
  if !g:codar_imports || empty(a:imports)
    return 0
  endif
  let l:missing = filter(copy(a:imports), {_, imp -> index(map(getline(1, '$'), 'trim(v:val)'), trim(imp)) < 0})
  if empty(l:missing)
    return 0
  endif
  let l:at = 0
  for l:i in range(1, min([line('$'), 200]))
    if trim(getline(l:i)) =~# s:import_line
      let l:at = l:i
    endif
  endfor
  if l:at == 0 && trim(getline(1)) !=# ''
    call add(l:missing, '')
  endif
  undojoin | call append(l:at, l:missing)
  return len(l:missing)
endfunction

function! s:apply(buf, first, last, original, tick, mode, out, code, err) abort
  if a:code != 0
    let l:msg = trim(a:err) !=# '' ? split(trim(a:err), "\n")[-1] : 'falhou (código ' . a:code . ')'
    return s:echo(l:msg, 'WarningMsg')
  endif
  try
    let l:res = json_decode(a:out)
  catch
    return s:echo('resposta inválida do CLI: ' . a:out[:120], 'ErrorMsg')
  endtry
  if bufnr('%') != a:buf
    return s:echo('o buffer mudou; o código ficou em :messages', 'WarningMsg') | echomsg l:res.code
  endif
  if get(l:res, 'complete', v:true) == v:false
    call s:echo('resposta incompleta; código original preservado', 'WarningMsg')
    echomsg l:res.code
    return
  endif
  if b:changedtick != a:tick
    call s:echo('o texto mudou enquanto o codar respondia; nada foi alterado', 'WarningMsg')
    return
  endif
  let l:body = split(l:res.body, "\n", 1)
  let &undolevels = &undolevels " a tradução vira um passo próprio de desfazer
  if a:mode ==# 'insert'
    let l:base = matchstr(getline(a:first), '^\s*')
    call map(l:body, {_, l -> l ==# '' ? l : l:base . l})
    if trim(getline(a:first)) ==# ''
      call setline(a:first, l:body[0])
      if len(l:body) > 1
        undojoin | call append(a:first, l:body[1:])
      endif
      let l:start = a:first
    else
      call append(a:first, l:body)
      let l:start = a:first + 1
    endif
  else
    call setline(a:first, l:body[0])
    if a:last > a:first
      undojoin | silent execute (a:first + 1) . ',' . a:last . 'delete _'
    endif
    if len(l:body) > 1
      undojoin | call append(a:first, l:body[1:])
    endif
    let l:start = a:first
  endif
  let l:shift = s:hoist_imports(get(l:res, 'imports', []))
  let l:start += l:shift
  call cursor(l:start + len(l:body) - 1, 1)
  let l:loc = map(copy(get(l:res, 'findings', [])), {_, f -> {
        \ 'bufnr': a:buf, 'lnum': l:start + max([1, get(f, 'body_line', f.line)]) - 1, 'col': get(f, 'col', 1),
        \ 'type': f.severity =~# 'critical\|error' ? 'E' : (f.severity ==# 'warning' ? 'W' : 'I'),
        \ 'text': '[' . f.id . '] ' . f.message . (has_key(f, 'suggestion') && type(f.suggestion) == v:t_string ? ' → ' . f.suggestion : '')}})
  call setloclist(0, l:loc, 'r')
  let l:stage = get({'0': 'compilador', '1': 'banco de padrões', '2': 'IA', '2:pseudo': 'IA literal'}, l:res.stage, l:res.stage)
  echo printf('codar: %s · %s%s', l:stage, l:res.source, empty(l:loc) ? '' : ' · ' . len(l:loc) . ' achado(s) em :lopen')
endfunction

" Traduz as linhas [first, last]: uma linha = intenção; várias = bloco de pseudocódigo indentado.
function! codar#translate(first, last, ...) abort
  let l:mode = a:0 ? a:1 : (a:first == a:last ? 'line' : 'block')
  let l:intent = a:0 > 1 ? a:2 : join(a:first == a:last ? [trim(getline(a:first))] : getline(a:first, a:last), "\n")
  if trim(l:intent) ==# ''
    return s:echo('nada para traduzir: escreva a intenção na linha', 'WarningMsg')
  endif
  let l:ctxfile = tempname()
  call writefile(getline(max([1, a:first - g:codar_context_lines]), a:first - 1), l:ctxfile)
  let l:args = ['run', '--json', '--context', l:ctxfile, '--mode', l:mode ==# 'block' ? 'block' : 'auto',
        \ '--indent', l:mode ==# 'insert' ? '' : matchstr(getline(a:first), '^\s*'),
        \ '--indent-unit', &expandtab ? repeat(' ', shiftwidth()) : "\t"]
  if &filetype !=# ''
    let l:args += ['-l', &filetype]
  endif
  if expand('%:p') !=# ''
    let l:args += ['--file', expand('%:p')]
  endif
  echo 'codar: traduzindo…'
  let l:ctx = s:run(l:args, l:intent, function('s:apply', [bufnr('%'), a:first, a:last, getline(a:first, a:last),
        \ b:changedtick, l:mode]))
  call add(l:ctx.files, l:ctxfile)
endfunction

function! codar#command(line1, line2, range, args) abort
  if a:args !=# ''
    return codar#translate(line('.'), line('.'), 'insert', a:args)
  endif
  return codar#translate(a:range ? a:line1 : line('.'), a:range ? a:line2 : line('.'))
endfunction

function! s:audit_done(buf, out, code, err) abort
  try
    let l:res = json_decode(a:out)
  catch
    return s:echo('auditoria falhou: ' . trim(a:err), 'ErrorMsg')
  endtry
  let l:loc = map(copy(l:res.findings), {_, f -> {'bufnr': a:buf, 'lnum': f.line, 'col': f.col,
        \ 'type': f.severity =~# 'critical\|error' ? 'E' : (f.severity ==# 'warning' ? 'W' : 'I'),
        \ 'text': '[' . f.id . '] ' . f.message . (type(get(f, 'suggestion')) == v:t_string ? ' → ' . f.suggestion : '')}})
  call setloclist(0, l:loc, 'r')
  if empty(l:loc)
    echo 'codar: nenhum achado'
  else
    lopen
  endif
endfunction

function! codar#audit() abort
  let l:args = ['audit', '--json'] + (&filetype !=# '' ? ['-l', &filetype] : [])
  call s:run(l:args, join(getline(1, '$'), "\n") . "\n", function('s:audit_done', [bufnr('%')]))
endfunction

function! codar#status() abort
  call s:run(['status'], '', {out, code, err -> s:echo(trim(out !=# '' ? out : err), code ? 'WarningMsg' : 'None')})
endfunction

" Mesma regra de codar.textutil.looks_like_intent (Python), do VS Code e do Neovim: mude as quatro juntas.
let s:keywords = {}
for s:w in split('return import from print const let var function def class if else elif for while in not and or '
      \ . 'pass break continue echo local then do end fi done new public private static void int string fn func '
      \ . 'package use using include require try catch except finally throw raise yield await async self this null '
      \ . 'none true false nil match case switch default struct enum interface type val mut')
  let s:keywords[s:w] = 1
endfor

" A linha é uma frase (pseudocódigo) e não código? "x é igual a 10" sim, "for i in range(3):" não.
function! codar#looks_like_intent(line) abort
  let l:text = trim(a:line)
  for l:prefix in ['//', '#', '--', ';']
    if strpart(l:text, 0, len(l:prefix)) ==# l:prefix
      let l:text = trim(strpart(l:text, len(l:prefix)))
      break
    endif
  endfor
  if strchars(l:text) < 5 || l:text =~# '[{}:;()\[\],=\\+\-*/<>]$' || count(l:text, '(') != count(l:text, ')')
    return 0
  endif
  let l:tokens = split(l:text)
  let l:words = filter(map(copy(l:tokens), {_, t -> substitute(t, '^[''".,!?]\+\|[''".,!?]\+$', '', 'g')}),
        \ {_, w -> w =~# '^\%(\a\|[^\x00-\x7f]\)\+$'})
  if len(l:tokens) < 2 || len(l:words) * 2 < len(l:tokens)
    return 0
  endif
  for l:w in l:words
    if strchars(l:w) >= 3 && !has_key(s:keywords, tolower(l:w))
      return 1
    endif
  endfor
  return 0
endfunction

" Espaço + Enter: o Enter acontece normalmente; logo depois, se a linha de cima termina em espaço e parece
" frase, a quebra é desfeita e a linha é traduzida. Sai do modo de inserção antes de mexer nas linhas: ao sair,
" o Vim apaga a indentação automática da linha do cursor, que precisa ser a linha nova, não a frase.
function! codar#after_enter() abort
  let l:before = get(b:, 'codar_lines', -1)
  let b:codar_lines = line('$')
  if l:before < 0 || line('$') != l:before + 1 || &buftype !=# '' || line('.') < 2
    return
  endif
  let l:row = line('.')
  let l:intent = getline(l:row - 1)
  if l:intent !~# ' $' || getline(l:row) !~# '^\s*$' || !codar#looks_like_intent(l:intent)
    return
  endif
  stopinsert
  call timer_start(10, {-> s:space_enter_apply(bufnr('%'), l:row, 20)})
endfunction

function! s:space_enter_apply(buf, row, tries) abort
  if bufnr('%') != a:buf
    return
  endif
  if mode() =~# '^i' && a:tries > 0
    call timer_start(10, {-> s:space_enter_apply(a:buf, a:row, a:tries - 1)})
    return
  endif
  if trim(getline(a:row)) ==# ''
    silent execute a:row . 'delete _'
  endif
  let b:codar_lines = line('$')
  call cursor(a:row - 1, 1)
  call codar#translate(a:row - 1, a:row - 1)
endfunction
