"""Completar com Tab: o script gerado do parser precisa ser válido e completar subcomandos, ações e valores."""

import shutil
import subprocess

import pytest

from codar.cli.completion import script

BASH = shutil.which("bash")


def complete_bash(tmp_path, line: str) -> list[str]:
    f = tmp_path / "codar.bash"
    f.write_text(script("bash"), encoding="utf-8")
    driver = f'''
source "{f}"
COMP_LINE="$1"; read -ra COMP_WORDS <<< "$1"; [[ "$1" == *" " ]] && COMP_WORDS+=("")
COMP_CWORD=$(( ${{#COMP_WORDS[@]}} - 1 )); COMP_POINT=${{#1}}
_codar; printf '%s\\n' "${{COMPREPLY[@]}}"
'''
    out = subprocess.run([BASH, "-c", driver, "_", line], capture_output=True, text=True, check=True).stdout
    return out.split()


@pytest.mark.skipif(not BASH, reason="sem bash")
@pytest.mark.parametrize("line,expected", [
    ("codar ru", {"run"}),
    ("codar model ", {"list", "pull", "use", "info"}),
    ("codar model use qwen2.5-coder-1", {"qwen2.5-coder-1.5b"}),
    ("codar run -l p", {"py", "python", "php", "powershell"}),
    ("codar extras install ", {"studio", "llm", "all"}),
    ("codar config get memory.bud", {"memory.budget_mb"}),
    ("codar completion ", {"bash", "zsh", "fish"}),
])
def test_bash(tmp_path, line, expected):
    assert expected <= set(complete_bash(tmp_path, line))


@pytest.mark.skipif(not BASH, reason="sem bash")
def test_bash_sintaxe(tmp_path):
    f = tmp_path / "c.bash"
    f.write_text(script("bash"), encoding="utf-8")
    subprocess.run([BASH, "-n", str(f)], check=True)


@pytest.mark.parametrize("shell,marker", [("zsh", "#compdef codar"), ("fish", "complete -c codar")])
def test_zsh_fish_geram_script(shell, marker):
    text = script(shell)
    assert text.startswith(marker) or marker in text
    assert "model" in text and "qwen2.5-coder-1.5b" in text
