"""Catálogo de estudo também acessível pelo CLI, sem Studio e sem IA."""

import json
import sys
from codar import estudo, langs


def cmd_study(args):
    try:
        lang = langs.resolve(args.lang).id
        topics = estudo.catalogo(lang)
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
        code, _ = estudo.exemplo(concept, lang)
        value = dict(id=concept.id, title=concept.titulo, language=lang, text=estudo.explicacao(concept, lang),
                     example=code, practice=concept.pratique, common_errors=concept.erros_comuns,
                     check=concept.verifique, sources=estudo.fontes(concept, lang))
        if args.json:
            print(json.dumps(value, ensure_ascii=False, indent=2))
        else:
            print(f"{concept.titulo} ({lang})\n\n{value['text']}\n\n{code}\n\nPratique: {concept.pratique}")
            if concept.erros_comuns:
                print('Atenção: ' + concept.erros_comuns)
            if concept.verifique:
                print('Confira: ' + concept.verifique)
            print('Fontes: ' + '\n'.join(value['sources']))
        return 0
    except (ValueError, KeyError) as exc:
        print('codar: ' + str(exc), file=sys.stderr)
        return 1
