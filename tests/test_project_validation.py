import sys

import pytest

from codar import toolchains
from codar.validation import check_project, run_command, validate_text


@pytest.mark.parametrize("name,extension,valid,invalid", [
    ("dart", ".dart", "int main() { return 1; }", "int main( {"),
    ("powershell", ".ps1", "param([string]$Name)\nWrite-Output $Name", "function Broken { if ($true) {")
])
def test_parser_nativo_sem_executar_programa(tmp_path, name, extension, valid, invalid):
    if not toolchains.executable(name):
        pytest.skip(f"{name} não instalado")
    assert validate_text(valid, "a" + extension)["status"] == "ok"
    assert validate_text(invalid, "a" + extension)["status"] == "error"
    sentinel = tmp_path / "executed"
    dangerous = f"[System.IO.File]::WriteAllText('{sentinel.as_posix()}', 'oops')" if name == "powershell" else \
        f"import 'dart:io'; void main() {{ File('{sentinel.as_posix()}').writeAsStringSync('oops'); }}"
    assert validate_text(dangerous, "a" + extension)["status"] == "ok"
    assert not sentinel.exists()


def test_comandos_sao_explicitos_e_argumentos_nao_passam_por_shell(tmp_path):
    sentinel = tmp_path / "executed"
    import json

    command = [sys.executable, "-c", "from pathlib import Path; Path('executed').write_text('yes')"]
    (tmp_path / "codar.toml").write_text("[commands]\ntest = " + json.dumps(command) + "\n", encoding="utf-8", newline="")
    assert check_project(tmp_path)["ok"] and not sentinel.exists()
    assert check_project(tmp_path, actions=["test"])["ok"] and sentinel.exists()
    result = run_command([sys.executable, "-c", "import sys; print(sys.argv[1])", "$(echo no); spaces &"], tmp_path)
    assert result["message"].strip() == "$(echo no); spaces &"


def test_timeout_e_saida_limitada(tmp_path):
    result = run_command([sys.executable, "-c", "import time; print('hi', flush=True); time.sleep(10)"], tmp_path, 1)
    assert result["status"] == "error" and "tempo limite" in result["message"]
    result = run_command([sys.executable, "-c", "print('x'*40000)"], tmp_path)
    assert result["status"] == "ok" and result["output_truncated"] and len(result["message"]) <= 32000
