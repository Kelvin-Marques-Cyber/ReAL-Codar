"""Consulta e adiciona referências de dependências ao catálogo do projeto."""

from dataclasses import asdict
import json
from pathlib import Path
import sys
import shlex
import subprocess

from codar import langs
from codar.libraries import LibraryCatalog, project_root
from codar.library_names import python_module


def cmd_libraries(args):
    try:
        root = project_root(args.root)
        if root is None:
            raise ValueError('Projeto não encontrado: ' + args.root)
        catalog = LibraryCatalog(root)
        lang = langs.resolve(args.lang).id
        if args.action == 'list':
            references = catalog.list()
            if args.json:
                print(json.dumps([asdict(ref) for ref in references], ensure_ascii=False, indent=2))
            else:
                for ref in references:
                    print(f'{ref.name} ({ref.lang}) · {ref.version} · {len(ref.symbols)} declarações · {ref.origin}')
            return 0
        if not args.name:
            raise ValueError('Informe o nome da biblioteca/módulo.')
        if args.action == 'install':
            from codar.library_packages import installation_plan, install

            commands = installation_plan(root, args.name, lang, args.library_version)
            if args.dry_run:
                print(json.dumps({'root': str(root), 'commands': commands}, ensure_ascii=False, indent=2) if args.json
                      else '\n'.join(shlex.join(command) for command in commands))
                return 0
            install(root, commands)
            name = args.module or (python_module(args.name) if lang == 'python' else args.name)
            reference = catalog.learn(name, lang)
            print('Dependência instalada no projeto. ' + ('Referências locais atualizadas.' if reference else
                  'Fontes/tipos/documentação ainda indisponíveis; use learn --source ou --module NOME_DO_IMPORT.'))
            return 0
        if args.action == 'forget':
            print(f'{catalog.forget(args.name, lang)} referência(s) removida(s) do catálogo; a biblioteca continua instalada.')
            return 0
        if args.action == 'verify':
            value = catalog.verify(args.name, lang)
            print(json.dumps(value, ensure_ascii=False, indent=2) if args.json else value['message'])
            return 0 if value['ok'] else 1
        source = Path(args.source) if args.source and args.action == 'learn' else None
        ref = catalog.learn(args.name, lang, source, args.library_version)
        if not ref:
            raise ValueError('Fontes/tipos/documentação local indisponíveis. Use learn --source ARQUIVO; '
                             'o CODAR não executa nem instala a dependência para inspecioná-la.')
        print(json.dumps(asdict(ref), ensure_ascii=False, indent=2) if args.json else ref.context())
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        print('codar: ' + str(exc), file=sys.stderr)
        return 1
