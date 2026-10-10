import json
import os
import shutil
import subprocess

import pytest

from codar import paths
from codar.plugin_loader import discover, load_plugin, version_matches
from codar.plugin_manager import METADATA, install_plugin, recover_plugins, remove_plugin, restore_plugin, update_plugin


@pytest.fixture
def source(tmp_path, monkeypatch):
    monkeypatch.setenv("CODAR_HOME", str(tmp_path / "home"))
    directory = tmp_path / "source"
    directory.mkdir()
    (directory / "plugin.toml").write_text('[plugin]\nname="exemplo"\nversion="1.0.0"\n', encoding="utf-8", newline="")
    (directory / "skills.toml").write_text('[[skill]]\nid="exemplo.base"\nguidance=["Use explicit errors"]\n', encoding="utf-8", newline="")
    return directory


def test_atualizacao_remocao_e_recuperacao_mantem_origem(source):
    install_plugin(str(source))
    (source / "plugin.toml").write_text('[plugin]\nname="exemplo"\nversion="1.1.0"\n', encoding="utf-8", newline="")
    assert update_plugin("exemplo")["version"] == "1.1.0"
    assert restore_plugin("exemplo")["version"] == "1.0.0"
    assert json.loads((paths.user_plugins_dir() / "exemplo" / METADATA).read_text())["source"] == str(source)
    remove_plugin("exemplo")
    assert not (paths.user_plugins_dir() / "exemplo").exists()
    assert restore_plugin("exemplo")["version"] == "1.0.0"


def test_origem_invalida_ou_modificacao_local_preserva_instalacao(source):
    install_plugin(str(source))
    installed = paths.user_plugins_dir() / "exemplo"
    original = (installed / "plugin.toml").read_bytes()
    (source / "skills.toml").write_text("[[skill]\n", encoding="utf-8", newline="")
    with pytest.raises(ValueError, match="inválido"):
        update_plugin("exemplo")
    assert (installed / "plugin.toml").read_bytes() == original
    (installed / "local.txt").write_text("minha alteração", encoding="utf-8", newline="")
    (source / "skills.toml").write_text('[[skill]]\nid="a"\nguidance=["regra"]', encoding="utf-8", newline="")
    with pytest.raises(ValueError, match="modificado"):
        update_plugin("exemplo")
    assert (installed / "local.txt").read_text() == "minha alteração"


def test_falha_ao_publicar_atualizacao_restaura_instalacao(source, monkeypatch):
    install_plugin(str(source))
    installed = paths.user_plugins_dir() / "exemplo"
    old = (installed / "plugin.toml").read_text()
    (source / "plugin.toml").write_text('[plugin]\nname="exemplo"\nversion="2.0.0"\n', encoding="utf-8", newline="")
    real = os.replace
    def fail(src, dst):
        if str(dst) == str(installed) and str(src).endswith("package"):
            raise OSError("disco indisponível")
        return real(src, dst)
    monkeypatch.setattr(os, "replace", fail)
    with pytest.raises(OSError):
        update_plugin("exemplo")
    assert (installed / "plugin.toml").read_text() == old
    assert not (paths.data_dir() / "plugin-backups" / "transaction.json").exists()


def test_transacao_interrompida_e_recuperada(source):
    install_plugin(str(source))
    installed = paths.user_plugins_dir() / "exemplo"
    backup = paths.data_dir() / "plugin-backups" / "exemplo" / "1"
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(installed), backup)
    journal = paths.data_dir() / "plugin-backups" / "transaction.json"
    journal.write_text(json.dumps({"name": "exemplo", "backup": "exemplo/1"}), encoding="utf-8", newline="")
    assert recover_plugins()["recovered"]
    assert (installed / "plugin.toml").exists() and not journal.exists()


@pytest.mark.parametrize("content", ['[plugin]\nname="exemplo"\nrequires_codar=">=999.0.0"',
                                     '[plugin]\nname="exemplo"\nversion="banana"',
                                     '[plugin\n', '[plugin]\nname=["exemplo"]'])
def test_manifesto_invalido_nao_derruba_outros_plugins(source, content):
    install_plugin(str(source))
    (paths.user_plugins_dir() / "exemplo" / "plugin.toml").write_text(content, encoding="utf-8", newline="")
    bundle = discover({})
    invalid = next(p for p in bundle.plugins if p.root.name == "exemplo")
    assert invalid.errors and any(p.id.startswith("flutter.") for p in bundle.patterns)
    assert not any(s.source == "exemplo" for s in bundle.skills)


def test_regex_invalida_isolada(source):
    (source / "rules.toml").write_text('[[rule]]\nid="EX001"\npattern="["\nmessage="a"\n', encoding="utf-8", newline="")
    assert load_plugin(source, False).errors
    with pytest.raises(ValueError):
        install_plugin(str(source))


def test_guidance_texto_simples_nao_e_convertida_em_caracteres(source):
    (source / "skills.toml").write_text('[[skill]]\nid="exemplo.base"\nguidance="Use errors"\n', encoding="utf-8", newline="")
    assert load_plugin(source, False).errors


def test_ciclo_de_dependencias_nao_executa_extensao_python(source):
    install_plugin(str(source))
    first = paths.user_plugins_dir() / "exemplo"
    (first / "plugin.toml").write_text('[plugin]\nname="exemplo"\nrequires_plugins={other=">=1.0.0"}\n', encoding="utf-8", newline="")
    other = paths.user_plugins_dir() / "other"
    other.mkdir()
    (other / "plugin.toml").write_text('[plugin]\nname="other"\nversion="1.0.0"\nrequires_plugins={exemplo=">=1.0.0"}\n', encoding="utf-8", newline="")
    sentinel = source / "executed"
    (other / "plugin.py").write_text(f"from pathlib import Path\nPath({str(sentinel)!r}).touch()\n", encoding="utf-8", newline="")
    bundle = discover({"plugins": {"allow_python": True}})
    assert all(p.errors for p in bundle.plugins if p.name in ("exemplo", "other"))
    assert not sentinel.exists()


def test_limites_de_tamanho_isolam_plugin(source):
    (source / "oversized.bin").write_bytes(b"x" * 8_000_001)
    with pytest.raises(ValueError, match="excede"):
        install_plugin(str(source))


@pytest.mark.parametrize("version,spec,expected", [("0.3.0", ">=0.3.0,<0.4.0", True),
                                                  ("1.0.0", ">=2.0", False), ("1.2", "==1.2.0", True),
                                                  ("1.3.0", "!=1.3.0", False)])
def test_faixas_de_versao(version, spec, expected):
    assert version_matches(version, spec) is expected


def test_atualizacao_recusa_incompatibilidade_de_dependentes(source, tmp_path):
    install_plugin(str(source))
    dependent = tmp_path / "dependent"
    dependent.mkdir()
    (dependent / "plugin.toml").write_text('[plugin]\nname="dependent"\nrequires_plugins={exemplo="<2.0.0"}\n', encoding="utf-8", newline="")
    install_plugin(str(dependent))
    (source / "plugin.toml").write_text('[plugin]\nname="exemplo"\nversion="2.0.0"\n', encoding="utf-8", newline="")
    with pytest.raises(ValueError, match="dependent requer"):
        update_plugin("exemplo")
    with pytest.raises(ValueError, match="dependem"):
        remove_plugin("exemplo")


def test_instalacao_antiga_sem_origem_pode_receber_atualizacao_explicita(source):
    installed = paths.user_plugins_dir() / "exemplo"
    installed.parent.mkdir(parents=True)
    shutil.copytree(source, installed)
    with pytest.raises(ValueError, match="origem"):
        update_plugin("exemplo")
    assert update_plugin("exemplo", str(source))["source"] == str(source)


def test_restore_de_instalacao_antiga_sem_metadados(source):
    installed = paths.user_plugins_dir() / "exemplo"
    installed.parent.mkdir(parents=True)
    shutil.copytree(source, installed)
    (source / "plugin.toml").write_text('[plugin]\nname="exemplo"\nversion="2.0.0"\n', encoding="utf-8", newline="")
    update_plugin("exemplo", str(source))
    restored = restore_plugin("exemplo")
    assert restored["version"] == "1.0.0" and restored["source"] == str(source)


def test_url_invalida_e_nome_embutido_recusados(source):
    with pytest.raises(ValueError, match="credenciais"):
        install_plugin("https://user:password@example.com/repo.git")
    (source / "plugin.toml").write_text('[plugin]\nname="core"\n', encoding="utf-8", newline="")
    with pytest.raises(ValueError, match="reservado"):
        install_plugin(str(source))


def test_git_respeita_tag_subpasta_e_registra_revisao(source, monkeypatch):
    if not shutil.which("git"):
        pytest.skip("Git não instalado")
    from codar import plugin_manager as manager

    repository = source.parent / "remote"
    repository.mkdir()
    plugin = repository / "plugins" / "example"
    shutil.copytree(source, plugin)
    def git(*args):
        result = subprocess.run(["git", "-C", str(repository), *args], capture_output=True, text=True, check=True)
        return result.stdout.strip()
    git("init")
    git("config", "user.name", "Fixture")
    git("config", "user.email", "fixture@example.invalid")
    git("add", ".")
    git("commit", "-m", "version one")
    first = git("rev-parse", "HEAD")
    git("tag", "v1.0.0")
    (plugin / "plugin.toml").write_text('[plugin]\nname="exemplo"\nversion="2.0.0"\n', encoding="utf-8", newline="")
    git("add", ".")
    git("commit", "-m", "version two")
    second = git("rev-parse", "HEAD")
    git("tag", "v2.0.0")
    actual_git = manager._git
    def transport(command, directory):
        # Apenas o transporte HTTPS aponta para a fixture; clone/fetch/checkout são Git reais.
        command = [str(repository) if arg == "https://example.invalid/plugin.git" else arg for arg in command]
        return actual_git(command, directory)
    monkeypatch.setattr(manager, "_git", transport)
    installed = manager.install_plugin("https://example.invalid/plugin.git", ref="v1.0.0", subdir="plugins/example")
    assert installed["version"] == "1.0.0" and installed["revision"] == first
    updated = manager.update_plugin("exemplo", ref="v2.0.0")
    assert updated["version"] == "2.0.0" and updated["revision"] == second
    assert manager.restore_plugin("exemplo")["revision"] == first
