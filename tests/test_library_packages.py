"""Instalar é uma ação explícita, separada de inspecionar/importar APIs."""

import json
import subprocess

import pytest

from codar.cli.main import main
from codar.libraries import LibraryCatalog
from codar.library_packages import installation_plan, install


@pytest.fixture(autouse=True)
def private(tmp_path, monkeypatch):
    monkeypatch.setenv('CODAR_HOME', str(tmp_path / 'codar-home'))


def write(root, name, text):
    file = root / name
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(text, encoding='utf-8')
    return file


def test_python_cria_ambiente_do_projeto_sem_alterar_codar(tmp_path):
    plan = installation_plan(tmp_path, 'yt-dlp', 'python', '2026.1.2')
    assert plan[0][1:3] == ['-m', 'venv']
    assert plan[0][-1] == str(tmp_path / '.venv')
    assert plan[1][0].startswith(str(tmp_path / '.venv'))
    assert plan[1][1:] == ['-m', 'pip', 'install', 'yt-dlp==2026.1.2']
    assert not (tmp_path / '.venv').exists()


def test_python_usa_venv_existente_e_nao_sobrescreve_pasta(tmp_path):
    write(tmp_path, '.venv/pyvenv.cfg', 'home = /usr/bin\n')
    assert len(installation_plan(tmp_path, 'requests', 'python')) == 1
    (tmp_path / '.venv/pyvenv.cfg').unlink()
    with pytest.raises(ValueError, match='não será sobrescrita'):
        installation_plan(tmp_path, 'requests', 'python')


@pytest.mark.parametrize('package', ['--index-url', 'x; rm -rf /', '$(x)', 'https://exemplo/lib', '../lib', 'pkg[foo]'])
def test_nome_de_pacote_nao_vira_comando(tmp_path, package):
    with pytest.raises(ValueError, match='Nome de pacote inválido'):
        installation_plan(tmp_path, package, 'python')


@pytest.mark.parametrize('version', ['--pre', '2; executar', '>=2', 'https://exemplo/lib'])
def test_versao_nao_vira_comando(tmp_path, version):
    with pytest.raises(ValueError, match='versão exata'):
        installation_plan(tmp_path, 'requests', 'python', version)


def test_tkinter_nao_e_pacote_pip(tmp_path):
    with pytest.raises(ValueError, match='não é instalado pelo pip'):
        installation_plan(tmp_path, 'tkinter', 'python')


@pytest.mark.parametrize('lang,manifest,content,package,expected', [
    ('javascript', 'package.json', '{}', '@exemplo/videos', ['npm', 'install', '@exemplo/videos@1.2.0']),
    ('typescript', 'package.json', '{}', 'youtubei.js', ['npm', 'install', 'youtubei.js@1.2.0']),
    ('dart', 'pubspec.yaml', 'name: app\n', 'video_lib', ['dart', 'pub', 'add', 'video_lib:1.2.0']),
    ('dart', 'pubspec.yaml', 'dependencies:\n  flutter:\n    sdk: flutter\n', 'video_lib', ['flutter', 'pub', 'add', 'video_lib:1.2.0']),
    ('rust', 'Cargo.toml', '[package]\nname="app"\n', 'serde', ['cargo', 'add', 'serde@1.2.0']),
    ('csharp', 'app.csproj', '<Project/>', 'YoutubeExplode', ['dotnet', 'add', 'PROJECT', 'package', 'YoutubeExplode', '--version', '1.2.0']),
    ('php', 'composer.json', '{}', 'vendor/videos', ['composer', 'require', 'vendor/videos:1.2.0']),
    ('ruby', 'Gemfile', '', 'json', ['bundle', 'add', 'json', '--version', '1.2.0']),
    ('go', 'go.mod', 'module exemplo/app\n', 'example.com/video', ['go', 'get', 'example.com/video@v1.2.0']),
])
def test_planos_usam_gerenciador_nativo(tmp_path, monkeypatch, lang, manifest, content, package, expected):
    file = write(tmp_path, manifest, content)
    monkeypatch.setattr('codar.advisor.pacotes.gerenciador', lambda root: 'npm')
    plan = installation_plan(tmp_path, package, lang, '1.2.0')
    expected = [str(file) if item == 'PROJECT' else item for item in expected]
    assert plan[0] == expected


def test_node_respeita_gerenciador_pelo_lockfile(tmp_path):
    write(tmp_path, 'package.json', '{}')
    write(tmp_path, 'pnpm-lock.yaml', '')
    assert installation_plan(tmp_path, 'youtubei.js', 'javascript')[0] == ['pnpm', 'add', 'youtubei.js']


def test_cli_dry_run_nao_executa_instalacao(tmp_path, capsys, monkeypatch):
    def unexpected(*args, **kwargs):
        raise AssertionError('dry-run executou um comando')
    monkeypatch.setattr(subprocess, 'run', unexpected)
    assert main(['libraries', 'install', 'yt-dlp', '--root', str(tmp_path), '--dry-run', '--json']) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['commands'][1][-1] == 'yt-dlp'
    assert not (tmp_path / '.venv').exists()


def test_instalacao_usa_argv_sem_shell_e_interrompe_em_falha(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr('codar.library_packages.environment', lambda env, root: env)
    monkeypatch.setattr('codar.library_packages.shutil.which', lambda *a, **k: '/usr/bin/pm')
    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        raise subprocess.CalledProcessError(1, argv)
    monkeypatch.setattr(subprocess, 'run', run)
    with pytest.raises(subprocess.CalledProcessError):
        install(tmp_path, [['pm', 'add', 'lib'], ['pm', 'fetch']])
    assert len(calls) == 1
    assert calls[0][1]['cwd'] == tmp_path
    assert 'shell' not in calls[0][1]


def test_verifica_e_esquece_referencia_sem_remover_biblioteca(tmp_path):
    module = write(tmp_path, 'minhalib.py', 'def buscar(url):\n    pass\n')
    catalog = LibraryCatalog(tmp_path)
    assert catalog.verify('minhalib', 'python')['ok']
    module.write_text('def buscar(url, *, limit=2):\n    pass\n')
    assert catalog.verify('minhalib', 'python')['changed']
    assert catalog.forget('minhalib', 'python') == 1
    assert module.exists() and not catalog.list()


def test_rust_usa_versao_do_lockfile(tmp_path, monkeypatch):
    cargo = tmp_path / 'cargo-cache'
    monkeypatch.setenv('CARGO_HOME', str(cargo))
    write(tmp_path, 'Cargo.lock', '[[package]]\nname="video-lib"\nversion="2.0.0"\n')
    write(cargo, 'registry/src/index/video-lib-2.0.0/src/lib.rs', 'pub fn playlist(id: &str) {}\n')
    write(cargo, 'registry/src/index/video-lib-1.0.0/src/lib.rs', 'pub fn obsoleta() {}\n')
    context = LibraryCatalog(tmp_path).context('use video_lib::playlist;', 'rust')
    assert 'versão 2.0.0' in context and 'playlist' in context
    assert 'obsoleta' not in context


def test_go_usa_go_mod_em_vez_de_historico_do_go_sum(tmp_path, monkeypatch):
    cache = tmp_path / 'go-cache'
    monkeypatch.setenv('GOMODCACHE', str(cache))
    write(tmp_path, 'go.mod', 'module app\nrequire (\n  example.com/video v2.0.0\n)\n')
    write(cache, 'example.com/video@v2.0.0/video.go', 'func Playlist(id string) {}\n')
    context = LibraryCatalog(tmp_path).context('import "example.com/video"', 'go')
    assert 'versão v2.0.0' in context and 'Playlist' in context


def test_nuget_usa_assets_e_documentacao_xml(tmp_path):
    cache = tmp_path / 'nuget'
    write(cache, 'youtubeexplode/6.0/lib/netstandard2.0/YoutubeExplode.xml',
          '<member name="M:YoutubeExplode.Playlists.GetAsync(System.String)">Ler playlist</member>')
    write(tmp_path, 'obj/project.assets.json', json.dumps({'libraries': {'YoutubeExplode/6.0': {}},
                                                        'packageFolders': {str(cache): {}}}))
    context = LibraryCatalog(tmp_path).context('using YoutubeExplode;', 'csharp')
    assert 'versão 6.0' in context and 'Playlists.GetAsync' in context


def test_import_js_relativo_nao_inspeciona_node_modules_inteiro(tmp_path):
    current = write(tmp_path, 'src/app.ts', '')
    write(tmp_path, 'node_modules/errado/index.d.ts', 'export class Errado {}')
    write(tmp_path, 'src/util.ts', 'export function minhaFuncao() {}')
    context = LibraryCatalog(tmp_path, str(current)).context("import { minhaFuncao } from './util';", 'typescript')
    assert 'minhaFuncao' in context and 'Errado' not in context
