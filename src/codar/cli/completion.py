"""`codar completion <shell>`: completar com Tab no bash, zsh e fish, gerado a partir do próprio parser do CLI.

    bash:  eval "$(codar completion bash)"     (os pacotes já instalam em /usr/share/bash-completion)
    zsh:   eval "$(codar completion zsh)"
    fish:  codar completion fish | source

Completa subcomandos, opções, linguagens (-l), ações (model use, extras install…), nomes de modelos, ids de padrões
e chaves de configuração.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field


@dataclass
class Command:
    name: str
    help: str
    options: list[tuple[list[str], str, list[str] | None, bool]] = field(default_factory=list)
    # (flags, ajuda, valores possíveis, recebe valor?)
    positionals: list[list[str]] = field(default_factory=list)  # valores possíveis por posição ([] = livre)
    files: bool = False  # algum posicional é caminho de arquivo


def _dynamic() -> dict[str, list[str]]:
    """Valores que não estão no parser: linguagens, modelos, padrões e chaves de configuração."""
    from codar import config, langs
    from codar.engine.models import MODELS

    lang_values = sorted(set(langs.LANGS) | {"py", "js", "ts", "rs", "cs", "sh", "ps1", "rb", "pwsh"})
    try:
        from codar.plugin_loader import discover

        pattern_ids = sorted(p.id for p in discover(config.load()).patterns)
    except Exception:  # pragma: no cover - plugins quebrados não podem quebrar o completar
        pattern_ids = []
    keys = sorted(f"{sec}.{k}" for sec, body in config.DEFAULTS.items() if isinstance(body, dict) for k in body)
    return {"langs": lang_values, "models": sorted(MODELS), "patterns": pattern_ids, "config": keys}


def describe(parser: argparse.ArgumentParser) -> list[Command]:
    dyn = _dynamic()
    sub = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
    helps = {a.dest: a.help or "" for a in sub._choices_actions}
    out: list[Command] = []
    seen: set[int] = set()
    for name, p in sub.choices.items():
        if id(p) in seen:  # aliases (p, tui, ide) apontam para o mesmo parser: completa só o nome principal
            continue
        seen.add(id(p))
        cmd = Command(name, helps.get(name, ""))
        for a in p._actions:
            if isinstance(a, argparse._HelpAction):
                continue
            if a.option_strings:
                values = list(a.choices) if a.choices else (dyn["langs"] if a.dest == "lang" else None)
                takes = a.nargs != 0 and not isinstance(a, (argparse._StoreTrueAction, argparse._StoreFalseAction,
                                                             argparse._CountAction))
                cmd.options.append((list(a.option_strings), a.help or "", values, takes))
            else:
                if a.choices:
                    cmd.positionals.append([str(c) for c in a.choices])
                elif a.dest in ("file", "path", "root") or a.metavar in ("ARQUIVO",):
                    cmd.positionals.append([])
                    cmd.files = True
                else:
                    cmd.positionals.append([])
        # segunda posição com valores conhecidos
        if name == "model":
            cmd.positionals[1:2] = [dyn["models"]]
        elif name in ("patterns", "p"):
            cmd.positionals[1:2] = [dyn["patterns"]]
        elif name == "config":
            cmd.positionals[1:2] = [dyn["config"]]
        elif name == "extras":
            cmd.positionals[1:] = [["studio", "llm", "all"]]
        out.append(cmd)
    return out


def _clean(text: str) -> str:
    return re.sub(r"[\[\]:'\"`$\\]", "", text).replace("\n", " ")[:70]


def bash(cmds: list[Command]) -> str:
    names = " ".join(c.name for c in cmds)
    cases = []
    for c in cmds:
        opts = " ".join(f for flags, _, _, _ in c.options for f in flags)
        with_value = "|".join(f for flags, _, _, takes in c.options if takes for f in flags)
        value_cases = []
        for flags, _, values, takes in c.options:
            if takes and values:
                value_cases.append(f'        {"|".join(flags)}) words_="{" ".join(values)}" ;;')
            elif takes:
                value_cases.append(f'        {"|".join(flags)}) words_="__files__" ;;')
        pos = "\n".join(f'        {i}) words_="{" ".join(v)}" ;;' for i, v in enumerate(c.positionals) if v)
        cases.append(f'''    {c.name})
      opts_="{opts}"; valued_="{with_value}"; files_={1 if c.files else 0}
      case "$prev" in
{chr(10).join(value_cases) if value_cases else "        __none__) ;;"}
      esac
      if [[ -z "$words_" ]]; then
        __codar_position "$valued_"
        case "$pos_" in
{pos if pos else "        __none__) ;;"}
        esac
      fi ;;''')
    return f'''# codar: completar com Tab no bash (gerado por `codar completion bash`)
__codar_position() {{  # posição do argumento atual entre os posicionais do subcomando
  local i w skip=0
  pos_=0
  for ((i = cmdi + 1; i < COMP_CWORD; i++)); do
    w="${{COMP_WORDS[i]}}"
    if ((skip)); then skip=0; continue; fi
    if [[ "$w" == -* ]]; then [[ -n "$1" && "|$1|" == *"|$w|"* ]] && skip=1; continue; fi
    ((pos_++))
  done
}}

_codar() {{
  local cur="${{COMP_WORDS[COMP_CWORD]}}" prev="${{COMP_WORDS[COMP_CWORD-1]}}"
  local cmd="" cmdi=0 i opts_="" valued_="" words_="" files_=0 pos_=0
  for ((i = 1; i < COMP_CWORD; i++)); do
    if [[ "${{COMP_WORDS[i]}}" != -* ]]; then cmd="${{COMP_WORDS[i]}}"; cmdi=$i; break; fi
  done
  if [[ -z "$cmd" ]]; then
    mapfile -t COMPREPLY < <(compgen -W "{names} -h --help -V --version" -- "$cur")
    return
  fi
  case "$cmd" in
{chr(10).join(cases)}
  esac
  if [[ "$words_" == "__files__" ]]; then
    mapfile -t COMPREPLY < <(compgen -f -- "$cur")
  elif [[ "$cur" == -* ]]; then
    mapfile -t COMPREPLY < <(compgen -W "$opts_ -h --help" -- "$cur")
  elif [[ -n "$words_" ]]; then
    mapfile -t COMPREPLY < <(compgen -W "$words_" -- "$cur")
  elif ((files_)); then
    mapfile -t COMPREPLY < <(compgen -f -- "$cur")
  fi
}}
complete -o bashdefault -o default -F _codar codar
'''


def zsh(cmds: list[Command]) -> str:
    lines = ["#compdef codar", "# codar: completar com Tab no zsh (gerado por `codar completion zsh`)", "", "_codar() {",
             "  local -a commands", "  commands=("]
    lines += [f"    '{c.name}:{_clean(c.help)}'" for c in cmds]
    lines += ["  )", "  if (( CURRENT == 2 )); then", "    _describe 'comando' commands", "    return", "  fi",
              "  local cmd=${words[2]}", "  shift words", "  (( CURRENT-- ))", "  case $cmd in"]
    for c in cmds:
        specs = []
        for flags, help_, values, takes in c.options:
            excl = f"'({' '.join(flags)})'" if len(flags) > 1 else ""
            names = "{" + ",".join(flags) + "}" if len(flags) > 1 else flags[0]
            if takes:
                action = f"({' '.join(values)})" if values else "_files"
                specs.append(f"{excl}{names}'[{_clean(help_)}]:valor:{action}'")
            else:
                specs.append(f"{excl}{names}'[{_clean(help_)}]'")
        for i, values in enumerate(c.positionals, start=1):
            if values:
                specs.append(f"'{i}:valor:({' '.join(values)})'")
            elif c.files:
                specs.append(f"'{i}:arquivo:_files'")
        if c.files and not c.positionals:
            specs.append("'*:arquivo:_files'")
        lines.append(f"    {c.name}) _arguments -s \\")
        lines += [f"      {s} \\" for s in specs]
        lines.append("      ;;")
    lines += ["  esac", "}", "", 'if [[ "$funcstack[1]" == "_codar" ]]; then', '  _codar "$@"', "else",
              "  compdef _codar codar", "fi", ""]
    return "\n".join(lines)


def fish(cmds: list[Command]) -> str:
    names = " ".join(c.name for c in cmds)
    out = ["# codar: completar com Tab no fish (gerado por `codar completion fish`)", "complete -c codar -f"]
    for c in cmds:
        out.append(f"complete -c codar -n 'not __fish_seen_subcommand_from {names}' -a {c.name} "
                   f"-d '{_clean(c.help)}'")
        cond = f"__fish_seen_subcommand_from {c.name}"
        for flags, help_, values, takes in c.options:
            parts = []
            for f in flags:
                parts.append(f"-l {f[2:]}" if f.startswith("--") else f"-s {f[1:]}" if len(f) == 2 else f"-o {f[1:]}")
            arg = ""
            if takes:
                arg = f" -xa '{' '.join(values)}'" if values else " -rF"
            out.append(f"complete -c codar -n '{cond}' {' '.join(parts)}{arg} -d '{_clean(help_)}'")
        for values in c.positionals:
            if values:
                out.append(f"complete -c codar -n '{cond}' -a '{' '.join(values)}'")
        if c.files:
            out.append(f"complete -c codar -n '{cond}' -F")
    return "\n".join(out) + "\n"


def script(shell: str) -> str:
    from codar.cli.main import build_parser

    cmds = describe(build_parser())
    return {"bash": bash, "zsh": zsh, "fish": fish}[shell](cmds)


def cmd_completion(args) -> int:
    sys.stdout.write(script(args.shell))
    return 0
