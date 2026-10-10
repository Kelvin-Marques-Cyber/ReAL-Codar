import asyncio
import json
import subprocess

import pytest

from codar.cli.main import main
from codar.engine.router import Request
from codar.project import Project, read_source, safe_path


def test_contexto_prioriza_imports_e_mantem_arquivos_excluidos_fora(tmp_path):
    (tmp_path / "codar.toml").write_text('[project]\nexclude=["privado.py"]\ncontext_chars=800\n', encoding="utf-8", newline="")
    (tmp_path / "app.py").write_text('from token_service import validar_token\nvalidar_token("abc")\n', encoding="utf-8", newline="")
    (tmp_path / "token_service.py").write_text('def validar_token(valor):\n    return valor == "abc"\n', encoding="utf-8", newline="")
    (tmp_path / "aaa.py").write_text('def auxiliar():\n    pass\n', encoding="utf-8", newline="")
    (tmp_path / "privado.py").write_text('SENHA = "não incluir"\n', encoding="utf-8", newline="")
    (tmp_path / ".env").write_text('CHAVE="não incluir"', encoding="utf-8", newline="")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "a.py").write_text('SECRET="não incluir"\n', encoding="utf-8", newline="")
    context = Project.load(tmp_path).context("corrija autenticação", "app.py")
    assert context["files"][0]["path"] == "token_service.py"
    assert 'valor == "abc"' in context["context"]
    assert "não incluir" not in context["context"] and len(context["context"]) < 900


def test_git_respeita_ignore_negacoes_e_projetos_aninhados(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text('*.py\n!publico.py\n', encoding="utf-8", newline="")
    (tmp_path / "publico.py").write_text('x=1', encoding="utf-8", newline="")
    (tmp_path / "segredo.py").write_text('x=2', encoding="utf-8", newline="")
    assert Project.load(tmp_path).files() == ["publico.py"]


@pytest.mark.parametrize("path", ["../fora.py", "/tmp/fora.py", "C:/fora.py", "a\\b.py", ""])
def test_caminhos_fora_do_projeto_sao_recusados(tmp_path, path):
    with pytest.raises(ValueError):
        safe_path(tmp_path, path)


def test_contexto_nao_segue_links(tmp_path):
    file = tmp_path / "real.py"
    file.write_text("x=1", encoding="utf-8", newline="")
    try:
        (tmp_path / "link.py").symlink_to(file)
    except OSError:
        pytest.skip("criação de symlinks indisponível")
    assert "link.py" not in Project(tmp_path).files()
    with pytest.raises(ValueError, match="link"):
        safe_path(tmp_path, "link.py")


@pytest.mark.parametrize("config", ['[commands]\ntest="python -m pytest"', '[project]\nrepair_attempts=20',
                                    '[project]\nskills="python.base"', '[toolchains]\npython=312'])
def test_configuracao_invalida_tem_erro_claro(tmp_path, config):
    (tmp_path / "codar.toml").write_text(config, encoding="utf-8", newline="")
    with pytest.raises(ValueError):
        Project.load(tmp_path)


def test_skills_e_convencoes_do_projeto_no_prompt_e_cache_invalida(tmp_path, router):
    (tmp_path / "codar.toml").write_text('[project]\nskills=["python.base"]\nguidance=["Use repository conventions"]\n', encoding="utf-8", newline="")
    (tmp_path / "app.py").write_text('def login():\n    pass\n', encoding="utf-8", newline="")
    helper = tmp_path / "login_helper.py"
    helper.write_text('def login_helper():\n    return 1\n', encoding="utf-8", newline="")
    request = Request(intent="corrija login", selected='def login():\n    pass\n', file=str(tmp_path / "app.py"), mode="edit")
    router.stage2.answer = "def login():\n    return 1\n"
    one = asyncio.run(router.translate(request))
    assert "login_helper.py" in router.stage2.prompts[-1] and "Use repository conventions" in router.stage2.prompts[-1]
    assert asyncio.run(router.translate(request)).cached
    helper.write_text('def login_helper():\n    return 2\n', encoding="utf-8", newline="")
    assert not asyncio.run(router.translate(request)).cached and not one.cached


def test_project_init_nao_sobrescreve_e_check_retorna_erros(tmp_path, capsys):
    assert main(["project", "init", "--root", str(tmp_path)]) == 0
    original = (tmp_path / "codar.toml").read_text()
    assert main(["project", "init", "--root", str(tmp_path)]) == 1
    assert (tmp_path / "codar.toml").read_text() == original
    (tmp_path / "app.py").write_text("def f(:\n", encoding="utf-8", newline="")
    capsys.readouterr()
    assert main(["check", "app.py", "--root", str(tmp_path), "--json"]) == 2
    assert json.loads(capsys.readouterr().out)["files"][0]["status"] == "error"


def test_arquivo_grande_nao_e_truncado_silenciosamente(tmp_path):
    file = tmp_path / "grande.py"
    file.write_text("#" * 512001, encoding="utf-8", newline="")
    with pytest.raises(ValueError, match="excede"):
        read_source(file)
