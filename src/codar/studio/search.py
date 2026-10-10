"""Localizador de nomes e conteúdo, com palavras-chave sugeridas pela IA local."""

import asyncio

from rich.text import Text
from textual import on, work
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, ListItem, ListView, Select, Static

from codar.studio.screens import CopyableOutput


class SearchScreen(ModalScreen[dict | None]):
    DEFAULT_CSS = """
    SearchScreen { align: center middle; background: $codar-bg 75%; }
    #search-card { width: 125; max-width: 96%; height: 94%; padding: 1 2; border: round $codar-orange; }
    #search-options { height: 3; }
    #search-scope { width: 24; }
    #search-ai { width: 26; }
    #search-results { height: 9; border: solid $codar-dim; margin: 1 0; }
    #search-preview { height: 1fr; }
    #search-buttons { height: 3; margin-top: 1; }
    #search-buttons Button { margin-right: 2; }
    #search-status { height: auto; max-height: 3; }
    """
    BINDINGS = [('escape', 'close', 'Fechar'), ('f3', 'next_result(1)', 'Próximo'),
                ('shift+f3', 'next_result(-1)', 'Anterior')]

    def __init__(self, root, backend, *, file='', buffer=None, project=False, query=''):
        super().__init__()
        self.root, self.backend = root, backend
        self.file, self.buffer = file, buffer
        self.project, self.query_text = project, query
        self.results = []
        self.serial = 0

    def compose(self):
        with Vertical(id='search-card'):
            yield Label('BUSCAR · arquivos e conteúdo')
            yield Input(value=self.query_text, placeholder='Palavra, código ou descrição com IA local', id='search-query')
            with Horizontal(id='search-options'):
                yield Select([('Arquivo aberto', 'file'), ('Projeto', 'project')], allow_blank=False,
                             value='project' if self.project or not self.file else 'file', id='search-scope')
                yield Checkbox('Usar IA local', id='search-ai')
                yield Checkbox('Incluir nomes', value=True, id='search-names')
            yield Static('Enter busca · F3 / Shift+F3 percorre · escolha um resultado para abrir a linha.', id='search-status')
            yield ListView(id='search-results')
            yield CopyableOutput('', read_only=True, show_line_numbers=False, id='search-preview')
            with Horizontal(id='search-buttons'):
                yield Button('Buscar', id='search-run', variant='primary')
                yield Button('Abrir resultado', id='search-open', disabled=True)
                yield Button('Fechar', id='search-close')

    def on_mount(self):
        self.query_one('#search-query', Input).focus()

    @on(Input.Submitted, '#search-query')
    @on(Button.Pressed, '#search-run')
    def run_search(self):
        scope = self.query_one('#search-scope', Select).value
        if scope == 'file' and not self.file:
            self.query_one('#search-status', Static).update('Abra um arquivo ou escolha Projeto.')
            return
        self.serial += 1
        params = dict(root=str(self.root), query=self.query_one('#search-query', Input).value,
                      ai=self.query_one('#search-ai', Checkbox).value,
                      names=self.query_one('#search-names', Checkbox).value)
        if scope == 'file':
            params.update(file=self.file, buffer=self.buffer)
        self.query_one('#search-status', Static).update('Buscando…' + (' a IA local pode precisar carregar o modelo.' if params['ai'] else ''))
        self.search_worker(self.serial, params)

    @work(thread=True, exclusive=True, group='search')
    def search_worker(self, serial, params):
        try:
            if params['ai']:
                result = self.backend.call('project.search', params)
            else:
                from codar.search import search_project

                result = asyncio.run(search_project(None, params))
            self.app.call_from_thread(self.deliver, serial, result, '')
        except Exception as exc:
            self.app.call_from_thread(self.deliver, serial, {}, str(exc))

    async def deliver(self, serial, result, error):
        if not self.is_mounted or serial != self.serial:
            return
        view = self.query_one('#search-results', ListView)
        await view.clear()
        self.results = result.get('results', [])
        self.query_one('#search-open', Button).disabled = not self.results
        self.query_one('#search-preview', CopyableOutput).load_text('')
        if error:
            self.query_one('#search-status', Static).update(Text('Busca não concluída: ' + error))
            return
        status = f"{len(self.results)} resultados · {result['files_scanned']} arquivos · termos: " + ', '.join(result['terms'])
        if result.get('truncated'):
            status += ' · limite atingido; refine a busca'
        if result.get('skipped'):
            status += f" · {len(result['skipped'])} arquivos ilegíveis/binários ignorados"
        self.query_one('#search-status', Static).update(Text(status))
        await view.extend(ListItem(Static(Text(f"{hit['path']}:{hit['line']}  {hit['text'].strip()[:100]}"))) for hit in self.results)
        if self.results:
            view.index = 0

    @on(ListView.Highlighted, '#search-results')
    def preview(self, event):
        index = event.list_view.index
        if index is not None and index < len(self.results):
            self.query_one('#search-preview', CopyableOutput).load_text(self.results[index]['snippet'])

    @on(ListView.Selected, '#search-results')
    @on(Button.Pressed, '#search-open')
    def open_result(self):
        index = self.query_one('#search-results', ListView).index
        if index is not None and index < len(self.results):
            self.dismiss(self.results[index])

    @on(Button.Pressed, '#search-close')
    def action_close(self):
        self.dismiss(None)

    def action_next_result(self, step):
        view = self.query_one('#search-results', ListView)
        if self.results:
            view.index = ((view.index or 0) + step) % len(self.results)
