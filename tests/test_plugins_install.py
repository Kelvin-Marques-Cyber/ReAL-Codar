from codar.cli.plugincmd import install_plugin
from codar.plugin_loader import discover
import shutil
import subprocess
import json
import pytest


def test_plugins_embutidos_flutter_powershell_sem_erros(bundle, translate):
    selected = [p for p in bundle.plugins if p.name in ("flutter", "powershell")]
    assert len(selected) == 2 and not any(p.errors for p in selected)
    assert any(s.id == "dart.base" for s in bundle.skills)
    assert translate("criar widget stateless flutter", "dart").source == "pattern:flutter.stateless"
    assert translate("criar aplicativo flutter materialapp", "dart").source == "pattern:flutter.app"


def test_instalar_plugin_local_com_skills_sem_executar_python(tmp_path, monkeypatch):
    monkeypatch.setenv("CODAR_HOME", str(tmp_path / "home"))
    source = tmp_path / "meu_plugin"
    source.mkdir()
    (source / "plugin.toml").write_text('[plugin]\nname = "meu-plugin"\n', encoding="utf-8")
    (source / "skills.toml").write_text('[[skill]]\nid = "meu.skill"\nlangs = ["dart"]\nguidance = ["Use final"]\n', encoding="utf-8")
    (source / "plugin.py").write_text('raise RuntimeError("não executar durante instalação")', encoding="utf-8")
    assert install_plugin(str(source)) == 0
    installed = next(p for p in discover({}).plugins if p.name == "meu-plugin")
    assert installed.skills[0].id == "meu.skill" and not installed.errors
    assert install_plugin(str(source)) == 1  # preserva uma instalação existente


def test_plugin_invalido_nao_instala(tmp_path, monkeypatch):
    monkeypatch.setenv("CODAR_HOME", str(tmp_path / "home"))
    (tmp_path / "plugin.toml").write_text('[plugin]\nname = "../../fora"\n', encoding="utf-8")
    assert install_plugin(str(tmp_path)) == 1
    assert not (tmp_path / "home").exists()


@pytest.mark.skipif(not shutil.which("dart"), reason="SDK Dart ausente")
def test_sintaxe_dart_flutter_com_parser_do_sdk(bundle, tmp_path):
    for plugin in bundle.plugins:
        if plugin.name != "flutter":
            continue
        for pattern in plugin.patterns:
            file = tmp_path / (pattern.id + ".dart")
            file.write_text(pattern.code["dart"], encoding="utf-8")
            result = subprocess.run(["dart", "format", "--output=none", str(file)], capture_output=True, text=True,
                                    timeout=60)
            assert result.returncode == 0, result.stderr


@pytest.mark.skipif(not shutil.which("pwsh"), reason="PowerShell 7 ausente")
def test_funcao_powershell_le_caminho_literal_com_unicode(bundle, tmp_path):
    pattern = next(p for p in bundle.patterns if p.id == "powershell.json.file")
    data = tmp_path / "dados[1].json"
    data.write_text('{"nome":"João","total":2}', encoding="utf-8")
    script = tmp_path / "app.ps1"
    escaped = str(data).replace("'", "''")
    script.write_text(pattern.code["powershell"] + f"\nGet-JsonFile -Path '{escaped}' | ConvertTo-Json -Compress\n",
                      encoding="utf-8")
    result = subprocess.run(["pwsh", "-NoLogo", "-NoProfile", "-File", str(script)], capture_output=True, text=True,
                            timeout=60)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"nome": "João", "total": 2}
