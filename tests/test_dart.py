import json

from codar.advisor import pacotes
from codar.dart import project_for, runner


def project(tmp_path, flutter=True):
    (tmp_path / "lib").mkdir()
    main = tmp_path / "lib" / "main.dart"
    main.write_text("void main() {}", encoding="utf-8")
    (tmp_path / "pubspec.yaml").write_text("name: meu_app\ndependencies:\n" +
        ("  flutter:\n    sdk: flutter\n" if flutter else "") + "  http: ^1.0.0\n", encoding="utf-8")
    return main


def test_flutter_roda_main_em_vez_do_widget_aberto(tmp_path):
    main = project(tmp_path)
    widget = tmp_path / "lib" / "tela.dart"
    p = project_for(widget, tmp_path)
    assert p.flutter and p.name == "meu_app"
    assert runner(widget, tmp_path) == (("flutter", "run", "--target", str(main)), tmp_path)
    assert runner(tmp_path / "test" / "widget_test.dart", tmp_path) == (("flutter", "test", "{file}"), tmp_path)


def test_dart_e_projeto_aninhado(tmp_path):
    project(tmp_path)
    nested = tmp_path / "tools"
    nested.mkdir()
    main = project(nested, flutter=False)
    assert not project_for(main, tmp_path).flutter
    assert runner(main, tmp_path) == (("dart", "run", "{file}"), nested)
    assert project_for(tmp_path.parent / "outro.dart", tmp_path) is None


def test_dependencias_flutter_sdk_e_pacote_proprio(tmp_path):
    main = project(tmp_path)
    code = "import 'dart:io';\nimport 'package:meu_app/tela.dart';\nimport 'package:flutter/material.dart';\n" \
           "import 'package:http/http.dart';\nimport 'package:provider/provider.dart';\n"
    hints = pacotes.dicas(tmp_path, main, code, "dart")
    assert [h.comando for h in hints] == ["flutter pub get", "flutter pub add provider"]
    assert all(h.cwd == tmp_path for h in hints)
    (tmp_path / ".dart_tool").mkdir()
    (tmp_path / ".dart_tool" / "package_config.json").write_text(
        json.dumps({"packages": [{"name": p} for p in ("flutter", "http", "provider")]}), encoding="utf-8")
    assert pacotes.dicas(tmp_path, main, code, "dart") == []


def test_dart_usa_pub_add_e_ignora_imports_comentados(tmp_path):
    main = project(tmp_path, flutter=False)
    code = "// import 'package:nao_existe/a.dart';\nimport 'package:collection/collection.dart';\n"
    assert [h.comando for h in pacotes.dicas_dart(tmp_path, main, code)] == ["dart pub add collection"]
    assert pacotes.dicas_dart(tmp_path, main, "import 'dart:convert';") == []


def test_emissor_preserva_alias_importado():
    from codar.engine.emit import emit
    from codar.engine.ir import Import

    imports, body = emit([Import("dart:convert as conversor")], "dart")
    assert "import 'dart:convert' as conversor;" in "\n".join(imports) + body
