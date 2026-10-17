"""Trilhas de bibliotecas geradas de fontes locais, sem inventar chamadas de API."""

from dataclasses import dataclass, field
from pathlib import Path
import re
import shlex

from codar import langs
from codar.engine.imports import catalog_import
from codar.libraries import LibraryCatalog
from codar.library_packages import installation_plan


@dataclass
class Lesson:
    id: str
    title: str
    text: str
    example: str = ''
    practice: str = ''
    hints: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)


@dataclass
class LibraryTrack:
    name: str
    lang: str
    version: str
    fingerprint: str
    lessons: list[Lesson]
    documented: bool


def track(root: Path, name: str, lang: str, source: Path | None = None) -> LibraryTrack:
    lang = langs.resolve(lang).id
    ref = LibraryCatalog(root).learn(name, lang, source=source)
    sources = ref.sources if ref else []
    version = ref.version if ref else 'não resolvida'
    fingerprint = ref.fingerprint if ref else ''
    identity = re.sub(r'[^\w.-]', '_', name)[:100]
    prefix = 'library.' + identity + '.'
    intro = (f'{name} · {langs.LANGS[lang].name} · versão {version}. '
             'A trilha usa somente fontes, tipos e documentação disponíveis neste ambiente. '
             'Ler estas referências não executa a biblioteca.')
    if not ref:
        intro += ' As fontes locais não foram encontradas. Instale no projeto ou forneça learn --source ARQUIVO.'
    lessons = [Lesson(prefix + 'origem', '1. Conhecer a biblioteca e sua origem', intro,
                      practice='Confira a versão e de onde vêm as referências antes de seguir um tutorial.', sources=sources)]
    try:
        plan = installation_plan(root, name, lang)
        command = '\n'.join(shlex.join(argv) for argv in plan)
        install_text = 'Este é o plano para o ambiente do projeto. A trilha não executa a instalação.'
    except ValueError as exc:
        command, install_text = '', str(exc)
    lessons.append(Lesson(prefix + 'instalar', '2. Preparar o ambiente', install_text, command,
                          'Confira o runtime, a pasta do projeto e a versão desejada. Use a prévia antes de instalar.'))
    found = catalog_import('importar biblioteca ' + name, lang)
    code = found[0] if found else ''
    # Pacotes Dart particulares: usa apenas entradas encontradas de fato em lib/.
    if not code and lang == 'dart' and ref:
        entry = next((Path(p) for p in ref.sources if Path(p).suffix == '.dart' and 'lib' in Path(p).parts), None)
        if entry:
            parts = entry.parts
            relative = Path(*parts[parts.index('lib') + 1:]).as_posix()
            if re.fullmatch(r'[\w/-]+\.dart', relative) and re.fullmatch(r'[a-z][a-z0-9_]*', name):
                code = f"import 'package:{name}/{relative}';"
    lessons.append(Lesson(prefix + 'importar', '3. Importar sem implementar',
                          'Importar disponibiliza o módulo. Não cria um programa nem instala o pacote. '
                          + ('' if code else 'A sintaxe de importação depende da entrada/namespace real; consulte a fonte abaixo.'),
                          code, 'Crie seu arquivo de prática e escreva somente o import. Nenhum arquivo do editor será substituído.',
                          sources=sources))
    signatures = [s for s in ref.symbols if s and not s.startswith('  ')] if ref else []
    lessons.append(Lesson(prefix + 'api', '4. Ler a API da versão disponível',
                          ('Declarações extraídas estaticamente das fontes. Elas são referências, não um programa executável.'
                           if signatures else 'Nenhuma assinatura foi encontrada. Forneça fontes ou declarações de tipos antes de escolher uma API.'),
                          '\n'.join(signatures[:35]),
                          'Escolha uma declaração real. Identifique parâmetros obrigatórios, opcionais, retorno e origem.',
                          ['Comece pela função ou classe mais relacionada ao seu objetivo.',
                           'Consulte a declaração completa e a docstring no arquivo de origem.',
                           'Não deduza que um método existe apenas pelo nome da biblioteca.'], sources))
    docs = ref.documentation if ref else ''
    lessons.append(Lesson(prefix + 'praticar', '5. Praticar com um contrato explícito',
                          docs or 'Defina o que sua função deve receber e devolver antes de escrever a implementação.',
                          practice='Escreva um exemplo mínimo usando a API documentada. Teste um caso normal, um limite e um erro. '
                          'Use dados locais ou mocks para operações de rede. Execute seus testes explicitamente.',
                          hints=['Separe código de preparação, operação e verificação.',
                                 'Confira exceções e comportamento na documentação da versão instalada.',
                                 'Use codar check para sintaxe; depois rode o comando de testes do seu projeto.'], sources=sources))
    lessons.append(Lesson(prefix + 'projeto', '6. Consolidar e revisar',
                          'O registro de prática é manual e fica separado de um resultado de teste. '
                          'A conclusão da trilha não certifica a biblioteca nem código que não foi executado.',
                          practice='Integre o exemplo a uma função sua, acrescente testes e registre o que aprendeu. '
                          'Exporte o progresso para retomar em outro projeto.', sources=sources))
    return LibraryTrack(name, lang, version, fingerprint, lessons, ref is not None)
