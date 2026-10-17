"""Catálogo de estudo também acessível pelo CLI, sem Studio e sem IA."""

import json
import sys
from pathlib import Path
from codar import estudo, langs
from codar.estudo import progresso


def cmd_study(args):
    try:
        lang = langs.resolve(args.lang).id
        topics = estudo.catalogo(lang)
        if args.action in ('path', 'resume'):
            from codar.estudo.curriculo import percurso

            value = percurso(lang, args.root)
            if args.action == 'path':
                if args.json:
                    print(json.dumps(value, ensure_ascii=False, indent=2))
                else:
                    print(f"Percurso {lang}: {value['practiced']}/{value['total']} práticas registradas.")
                    print(value['environment'])
                    for lesson in value['lessons']:
                        print(f"{'✓' if lesson['practiced'] else '·'} {lesson['id']} · {lesson['level']} · {lesson['module']} · {lesson['title']}")
                    print(value['assessment'])
                return 0
            if value['next'] is None:
                print(json.dumps({'language': lang, 'next': None}, ensure_ascii=False) if args.json else
                      'Todas as práticas disponíveis foram registradas. Revise o projeto e os desafios; isso não certifica domínio da linguagem.')
                return 0
            args.name = value['next']
        if args.action == 'search':
            from codar.estudo.curriculo import buscar

            matches = buscar(lang, args.name)
            values = [{'id': c.id, 'title': c.titulo, 'track': estudo.TRILHAS[c.trilha]} for c in matches]
            print(json.dumps(values, ensure_ascii=False, indent=2) if args.json else
                  '\n'.join(f"{c['id']}: {c['title']}" for c in values) or 'Nenhuma aula corresponde à busca.')
            return 0
        if args.action in ('exercises', 'exercise', 'check'):
            from codar.estudo.exercicios import EXERCISES, catalog, check

            if args.action == 'exercises':
                values = catalog(lang)
                print(json.dumps(values, ensure_ascii=False, indent=2) if args.json else
                      '\n'.join(f"{item['id']}: {item['title']} — {item['task']}" for item in values))
                return 0
            if args.name not in EXERCISES:
                raise ValueError('Exercício desconhecido. Use codar study exercises.')
            exercise = EXERCISES[args.name]
            if args.action == 'exercise':
                from dataclasses import asdict

                print(json.dumps(asdict(exercise), ensure_ascii=False, indent=2) if args.json else
                      f'{exercise.title} · {exercise.difficulty} · avaliação: {exercise.assessment}\n{exercise.task}\n\nDicas:\n' + '\n'.join(exercise.hints))
                return 0
            if not args.file:
                raise ValueError('Informe --file ARQUIVO com sua solução; o comando executa este código.')
            root = Path(args.root).resolve()
            file = Path(args.file).expanduser()
            relative = file.relative_to(root).as_posix() if file.is_absolute() else file.as_posix()
            result = check(root, relative, args.name)
            if args.json:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                print(result['message'])
                for case in result['cases']:
                    print(f"{'OK' if case['ok'] else 'FALHOU'} · entrada {case['input']!r} · esperado {case['expected']!r} · saída {case['actual']!r}")
                    if case['error']:
                        print(case['error'])
                if result.get('progress_error'):
                    print('Resultado validado, mas o progresso não foi salvo: ' + result['progress_error'])
            return 0 if result['status'] == 'ok' else 2 if result['status'] == 'skipped' else 1
        if args.action == 'progress':
            value = progresso.ler(args.root, lang)
            print(json.dumps(value, ensure_ascii=False, indent=2) if args.json else
                  '\n'.join(f'{name} · {date}' for name, date in value.items()) or 'Nenhuma prática registrada.')
            return 0
        if args.action in ('export', 'import'):
            if not args.file:
                raise ValueError('Informe --file ARQUIVO.json.')
            file = Path(args.file).expanduser()
            if args.action == 'export':
                payload = progresso.exportar(args.root)
                with file.open('x', encoding='utf-8') as handle:
                    json.dump(payload, handle, ensure_ascii=False, indent=2)
                print('Progresso exportado: ' + str(file))
            else:
                if file.stat().st_size > 1_000_000:
                    raise ValueError('Arquivo de progresso excede 1 MB.')
                total = progresso.importar(args.root, json.loads(file.read_text(encoding='utf-8')))
                print(f'{total} registro(s) de prática importados para este projeto.')
            return 0
        if args.action == 'list':
            values = [{'id': c.id, 'title': c.titulo, 'track': estudo.TRILHAS[c.trilha]} for c in topics]
            if args.json:
                print(json.dumps(values, ensure_ascii=False, indent=2))
            else:
                for item in values:
                    print(f"{item['id']:25} {item['title']} · {item['track']}")
            return 0
        concept = estudo.POR_ID.get(args.name)
        if concept not in topics:
            raise ValueError('Tópico ausente nesta linguagem. Use codar study list --lang ' + lang)
        if args.action == 'mark':
            progresso.marcar(args.root, lang, concept.id)
            print('Prática registrada: ' + concept.titulo)
            return 0
        code, _ = estudo.exemplo(concept, lang)
        value = dict(id=concept.id, title=concept.titulo, language=lang, text=estudo.explicacao(concept, lang),
                     example=code, practice=concept.pratique, common_errors=concept.erros_comuns,
                     check=concept.verifique, sources=estudo.fontes(concept, lang))
        from codar.estudo.curriculo import percurso

        lesson = next(item for item in percurso(lang, args.root)['lessons'] if item['id'] == concept.id)
        value.update({key: lesson[key] for key in ('level', 'module', 'previous', 'next', 'related', 'practiced')})
        if args.json:
            print(json.dumps(value, ensure_ascii=False, indent=2))
        else:
            print(f"{concept.titulo} ({lang})\n\n{value['text']}\n\n{code}\n\nPratique: {concept.pratique}")
            if concept.erros_comuns:
                print('Atenção: ' + concept.erros_comuns)
            if concept.verifique:
                print('Confira: ' + concept.verifique)
            print('Fontes: ' + '\n'.join(value['sources']))
            print(f"Percurso: {value['level']} · {value['module']}")
            if value['previous']:
                print('Anterior: ' + value['previous'])
            if value['next']:
                print('Próxima: ' + value['next'])
            if value['related']:
                print('Relacionadas: ' + ', '.join(value['related']))
        return 0
    except (OSError, ValueError, KeyError) as exc:
        print('codar: ' + str(exc), file=sys.stderr)
        return 1
