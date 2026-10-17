"""Bibliotecas no Studio: inventário, fontes reais, trilhas e plano de instalação."""

from pathlib import Path
import shlex

from rich.syntax import Syntax
from rich.text import Text
from textual import on, work
from textual.containers import Grid, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, OptionList, RichLog, Select, Static
from textual.widgets.option_list import Option

from codar import langs
from codar.estudo.bibliotecas import LibraryTrack, track
from codar.estudo import progresso
from codar.libraries import LibraryCatalog
from codar.library_inventory import Dependency, inventory
from codar.library_packages import installation_plan
from codar.studio.screens import PromptScreen


class InstallPlanScreen(ModalScreen[bool]):
    DEFAULT_CSS = """
    InstallPlanScreen { align: center middle; background: $codar-bg 75%; }
    #library-plan { width: 110; max-width: 96%; height: 75%; padding: 1 2; border: round $codar-orange; }
    #library-plan-output { height: 1fr; margin: 1 0; }
    #library-plan-buttons { height: 3; }
    #library-plan-buttons Button { width: 1fr; }
    """
    BINDINGS = [('escape', 'cancel', 'Cancelar')]

    def __init__(self, root, commands):
        super().__init__()
        self.root, self.commands = root, commands

    def compose(self):
        with Vertical(id='library-plan'):
            yield Label('INSTALAR NO PROJETO · confira o plano')
            yield Static(Text(str(self.root)))
            yield RichLog(id='library-plan-output', wrap=True, markup=False)
            with Horizontal(id='library-plan-buttons'):
                yield Button('Executar instalação', id='library-confirm', variant='success')
                yield Button('Cancelar', id='library-decline')

    def on_mount(self):
        log = self.query_one('#library-plan-output', RichLog)
        for command in self.commands:
            log.write(Text(shlex.join(command)))
        self.query_one('#library-decline', Button).focus()

    def on_button_pressed(self, event):
        self.dismiss(event.button.id == 'library-confirm')

    def action_cancel(self):
        self.dismiss(False)


class LibraryStudyScreen(ModalScreen[None]):
    DEFAULT_CSS = """
    LibraryStudyScreen { align: center middle; background: $codar-bg 75%; }
    #library-study { width: 120; max-width: 96%; height: 92%; padding: 1 2; border: round $codar-orange; }
    #library-lesson { height: 1fr; margin: 1 0; }
    #library-study-buttons { height: 6; grid-size: 3; grid-columns: 1fr 1fr 1fr; grid-rows: 3 3; }
    #library-study-buttons Button { width: 100%; min-width: 10; }
    """
    BINDINGS = [('escape', 'close', 'Fechar')]

    def __init__(self, root: Path, value: LibraryTrack):
        super().__init__()
        self.root, self.value = root, value
        self.index, self.hints = 0, 0

    def compose(self):
        with Vertical(id='library-study'):
            yield Label(Text(f'TRILHA · {self.value.name} · {self.value.lang} · {self.value.version}'))
            yield Static('', id='library-study-progress')
            yield RichLog(id='library-lesson', wrap=True, markup=False, auto_scroll=False, min_width=1)
            with Grid(id='library-study-buttons'):
                yield Button('Anterior', id='lesson-prev')
                yield Button('Próxima', id='lesson-next')
                yield Button('Dica', id='lesson-hint')
                yield Button('Marcar praticado', id='lesson-mark')
                yield Button('Fontes', id='lesson-sources')
                yield Button('Fechar', id='lesson-close')

    def on_mount(self):
        self.render_lesson()

    def render_lesson(self):
        lesson = self.value.lessons[self.index]
        done = progresso.ler(self.root, self.value.lang)
        count = sum(item.id in done for item in self.value.lessons)
        self.query_one('#library-study-progress', Static).update(
            Text(f'Etapa {self.index + 1}/{len(self.value.lessons)} · {count} práticas registradas manualmente'))
        log = self.query_one('#library-lesson', RichLog)
        log.clear()
        log.write(Text(lesson.title, style='bold'))
        log.write(Text('\n' + lesson.text))
        if lesson.example:
            lexer = 'text' if self.index in (1, 3) else self.value.lang
            log.write(Syntax(lesson.example, lexer, word_wrap=True, background_color='default'))
        if lesson.practice:
            log.write(Text('\nPratique: ' + lesson.practice))
        for hint in lesson.hints[:self.hints]:
            log.write(Text('\nDica: ' + hint))
        self.query_one('#lesson-prev', Button).disabled = self.index == 0
        self.query_one('#lesson-next', Button).disabled = self.index == len(self.value.lessons) - 1
        self.query_one('#lesson-hint', Button).disabled = self.hints >= len(lesson.hints)
        self.query_one('#lesson-mark', Button).label = 'Praticado ✓' if lesson.id in done else 'Marcar praticado'
        log.scroll_home(animate=False)

    def on_button_pressed(self, event):
        identity = event.button.id
        if identity in ('lesson-prev', 'lesson-next'):
            self.index += -1 if identity == 'lesson-prev' else 1
            self.hints = 0
            self.render_lesson()
        elif identity == 'lesson-hint':
            self.hints += 1
            self.render_lesson()
        elif identity == 'lesson-mark':
            try:
                progresso.marcar(self.root, self.value.lang, self.value.lessons[self.index].id)
                self.render_lesson()
            except (OSError, ValueError) as exc:
                self.notify(str(exc), severity='error')
        elif identity == 'lesson-sources':
            log = self.query_one('#library-lesson', RichLog)
            log.write(Text('\nFontes da versão ' + self.value.version + ':'))
            for source in self.value.lessons[self.index].sources:
                log.write(Text(source))
        else:
            self.dismiss(None)

    def action_close(self):
        self.dismiss(None)


class LibrariesScreen(ModalScreen[dict | None]):
    DEFAULT_CSS = """
    LibrariesScreen { align: center middle; background: $codar-bg 75%; }
    #libraries-card { width: 140; max-width: 98%; height: 96%; padding: 0 1; border: round $codar-orange; }
    #libraries-filters { height: 3; }
    #libraries-language { width: 24; margin-right: 1; }
    #libraries-query { width: 1fr; }
    #libraries-content { height: 1fr; }
    #libraries-list { width: 38%; height: 1fr; min-width: 24; margin-right: 1; }
    #libraries-details { width: 1fr; height: 1fr; border: solid $codar-line; }
    #libraries-status { height: 1; }
    #libraries-actions { height: 6; grid-size: 3; grid-columns: 1fr 1fr 1fr; grid-rows: 3 3; }
    #libraries-actions Button { width: 100%; min-width: 10; }
    """
    BINDINGS = [('escape', 'close', 'Fechar')]

    def __init__(self, root: Path, lang: str):
        super().__init__()
        self.root, self.lang = root, langs.resolve(lang).id
        self.rows: list[Dependency] = []
        self.filtered: list[Dependency] = []
        self.generation = 0
        self.ready = False

    def compose(self):
        with Vertical(id='libraries-card'):
            yield Label('BIBLIOTECAS · ambiente, APIs e aprendizagem')
            with Horizontal(id='libraries-filters'):
                yield Select([(meta.name, key) for key, meta in langs.LANGS.items()], value=self.lang,
                             allow_blank=False, id='libraries-language', prompt='Linguagem')
                yield Input(placeholder='Buscar nome ou estado (instalada, importada…)…', id='libraries-query')
            with Horizontal(id='libraries-content'):
                yield OptionList(id='libraries-list')
                yield RichLog(id='libraries-details', markup=False, wrap=True, auto_scroll=False, min_width=1)
            yield Static('Carregando o ambiente…', id='libraries-status')
            with Grid(id='libraries-actions'):
                yield Button('Consultar API', id='libraries-api')
                yield Button('Abrir trilha', id='libraries-study')
                yield Button('Aprender fonte', id='libraries-source')
                yield Button('Instalar…', id='libraries-install')
                yield Button('Atualizar lista', id='libraries-refresh')
                yield Button('Fechar', id='libraries-close')

    def on_mount(self):
        self.ready = True
        self.refresh_inventory()
        self.query_one('#libraries-query', Input).focus()

    def refresh_inventory(self):
        self.generation += 1
        self.query_one('#libraries-status', Static).update('Lendo o ambiente local…')
        self.load_inventory(self.lang, self.generation)

    @work(thread=True, group='libraries-inventory', exclusive=True)
    def load_inventory(self, lang, generation):
        try:
            rows = inventory(self.root, lang)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            self.app.call_from_thread(self.show_error, str(exc), generation)
            return
        self.app.call_from_thread(self.loaded, rows, generation)

    def show_error(self, text, generation):
        if self.is_mounted and generation == self.generation:
            self.query_one('#libraries-status', Static).update(Text('Não foi possível ler: ' + text))

    def loaded(self, rows, generation):
        if not self.is_mounted or generation != self.generation:
            return
        self.rows = rows
        self.filter_rows()

    def filter_rows(self):
        query = self.query_one('#libraries-query', Input).value.casefold().split()
        self.filtered = [row for row in self.rows if all(word in (row.name + ' ' + row.lang + ' ' + row.status).casefold() for word in query)]
        options = self.query_one('#libraries-list', OptionList)
        options.clear_options()
        options.add_options([Option(Text(f'{row.name} · {row.version or row.requirement or "?"}\n{row.status}'), id=str(i))
                             for i, row in enumerate(self.filtered)])
        if self.filtered:
            options.highlighted = 0
            self.show_dependency(self.filtered[0])
        else:
            log = self.query_one('#libraries-details', RichLog)
            log.clear()
            log.write(Text('Nenhuma biblioteca neste filtro. Confira a linguagem e o ambiente do projeto.\n'
                           'Instalar… prepara um plano; Aprender fonte aceita documentação local.'))
        self.query_one('#libraries-status', Static).update(
            Text(f'{len(self.filtered)} de {len(self.rows)} dependências · leitura local · sem executar bibliotecas'))

    @on(Input.Changed, '#libraries-query')
    def query_changed(self):
        if self.ready:
            self.filter_rows()

    @on(Select.Changed, '#libraries-language')
    def language_changed(self, event):
        if self.ready and isinstance(event.value, str) and event.value != self.lang:
            self.lang = event.value
            self.rows = []
            self.filter_rows()
            self.refresh_inventory()

    @on(OptionList.OptionHighlighted, '#libraries-list')
    def highlighted(self, event):
        if event.option.id is not None and int(event.option.id) < len(self.filtered):
            self.show_dependency(self.filtered[int(event.option.id)])

    @on(OptionList.OptionSelected, '#libraries-list')
    def selected_option(self):
        self.open_reference(False)

    def selected_dependency(self):
        index = self.query_one('#libraries-list', OptionList).highlighted
        return self.filtered[index] if index is not None and index < len(self.filtered) else None

    def show_dependency(self, row):
        log = self.query_one('#libraries-details', RichLog)
        log.clear()
        log.write(Text(f'{row.name} · {row.lang}', style='bold'))
        log.write(Text(f'Versão: {row.version or "não detectada"}\nRequisito: {row.requirement or "não declarado"}\n'
                       f'Módulo: {row.module}\nEstado: {row.status}\n\nFontes locais:'))
        for source in row.sources:
            log.write(Text(source))
        log.write(Text('\nConsultar API lê assinaturas e docstrings. Abrir trilha organiza a prática em seis etapas.'))
        log.scroll_home(animate=False)

    def open_reference(self, study, source=None, name=None):
        row = self.selected_dependency()
        name = name or (row.module if row else '')
        if not name:
            self.notify('Selecione uma biblioteca ou use Aprender fonte.')
            return
        self.query_one('#libraries-status', Static).update('Lendo fontes e documentação…')
        self.load_reference(name, self.lang, study, source, self.generation)

    @work(thread=True, group='libraries-reference', exclusive=True)
    def load_reference(self, name, lang, study, source, generation):
        try:
            value = track(self.root, name, lang, source=source) if study else LibraryCatalog(self.root).learn(name, lang, source=source)
        except (OSError, ValueError) as exc:
            self.app.call_from_thread(self.show_error, str(exc), generation)
            return
        def show():
            if not self.is_mounted or generation != self.generation:
                return
            self.query_one('#libraries-status', Static).update('Fontes lidas; nenhuma API foi executada.')
            if study:
                self.app.push_screen(LibraryStudyScreen(self.root, value))
            else:
                log = self.query_one('#libraries-details', RichLog)
                log.clear()
                if value:
                    log.write(Text(f'{value.name} · versão {value.version} · {value.origin}', style='bold'))
                    log.write(Text('\n'.join(value.symbols) or 'Nenhuma assinatura legível.'))
                    log.write(Text(value.documentation))
                    log.write(Text('\nFontes:\n' + '\n'.join(value.sources)))
                else:
                    log.write(Text('Fontes/tipos indisponíveis. Use Aprender fonte para fornecer documentação local.'))
                log.scroll_home(animate=False)
        self.app.call_from_thread(show)

    def on_button_pressed(self, event):
        identity = event.button.id
        if identity == 'libraries-api':
            self.open_reference(False)
        elif identity == 'libraries-study':
            self.open_reference(True)
        elif identity == 'libraries-refresh':
            self.refresh_inventory()
        elif identity == 'libraries-source':
            row = self.selected_dependency()
            def ask_source(name):
                if name:
                    def learn(path):
                        if path:
                            self.open_reference(False, source=(self.root / Path(path).expanduser()).resolve(), name=name)
                    self.app.push_screen(PromptScreen('FONTE LOCAL · código, tipos ou documentação', ''), learn)
            self.app.push_screen(PromptScreen('NOME DO MÓDULO/BIBLIOTECA', row.module if row else ''), ask_source)
        elif identity == 'libraries-install':
            row = self.selected_dependency()
            def plan(name):
                if not name:
                    return
                try:
                    commands = installation_plan(self.root, name, self.lang)
                except ValueError as exc:
                    self.notify(str(exc), severity='warning', timeout=8)
                    return
                def confirm(yes):
                    if yes:
                        self.dismiss({'commands': commands, 'name': name})
                self.app.push_screen(InstallPlanScreen(self.root, commands), confirm)
            self.app.push_screen(PromptScreen('PACOTE PARA INSTALAR NO PROJETO', row.name if row else ''), plan)
        else:
            self.dismiss(None)

    def action_close(self):
        self.dismiss(None)
