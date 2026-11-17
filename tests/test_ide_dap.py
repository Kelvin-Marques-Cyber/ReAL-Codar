"""Cliente DAP com depuradores reais: debugpy (Python) e o modo DAP do GDB (C)."""

import asyncio
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from codar.ide import dap
from codar.ide.dap import ErroDAP, SessaoDAP

PROGRAMA_PY = textwrap.dedent("""\
    def dobro(x):
        y = x * 2
        return y

    nome = "Ana"
    print("antes", flush=True)
    r = dobro(21)
    print("depois", r)
    """)


def _tem_debugpy(python=sys.executable):
    return subprocess.run([python, "-c", "import debugpy"], capture_output=True).returncode == 0


async def _esperar(condicao, vezes=300):
    for _ in range(vezes):
        if condicao():
            return True
        await asyncio.sleep(.05)
    return condicao()


def _sessao(plano, raiz, eventos):
    return SessaoDAP(plano.adaptador, raiz, ao_evento=lambda nome, corpo: eventos.append((nome, corpo)))


@pytest.mark.slow
def test_python_breakpoint_pilha_variaveis_passos_e_saida(tmp_path):
    if not _tem_debugpy():
        pytest.skip("debugpy ausente")
    arquivo = tmp_path / "alvo.py"
    arquivo.write_text(PROGRAMA_PY, encoding="utf-8")
    plano = dap.plano("python", arquivo, tmp_path, python=sys.executable)
    assert plano.falta == ""
    eventos = []

    async def cenario():
        sessao = _sessao(plano, tmp_path, eventos)
        await sessao.iniciar(plano.adapter_id, plano.lancamento, {arquivo: [1]})  # y = x * 2
        try:
            assert await _esperar(lambda: sessao.parado_em is not None)
            assert sessao.motivo_parada == "breakpoint"
            quadros = await sessao.pilha()
            assert (quadros[0].nome, quadros[0].linha) == ("dobro", 1)
            assert quadros[0].caminho.resolve() == arquivo.resolve() and quadros[1].nome == "<module>"
            escopo = (await sessao.escopos(quadros[0].id))[0]
            assert [(v.nome, v.valor) for v in await sessao.variaveis(escopo.referencia)] == [("x", "21")]
            assert await sessao.avaliar("x + 1", quadros[0].id) == "22"
            await sessao.proximo()
            assert await _esperar(lambda: sessao.parado_em is not None and sessao.motivo_parada == "step")
            assert (await sessao.pilha())[0].linha == 2
            await sessao.continuar()
            assert await _esperar(lambda: sessao.terminou)
            assert sessao.codigo_saida == 0
            assert "".join(t for c, t in sessao.saida if c == "stdout") == "antes\ndepois 42\n"
        finally:
            await sessao.encerrar()
        assert {"stopped", "output", "exited"} <= {nome for nome, _ in eventos}
    asyncio.run(cenario())


@pytest.mark.slow
def test_python_programa_inexistente_explica(tmp_path):
    if not _tem_debugpy():
        pytest.skip("debugpy ausente")
    plano = dap.plano("python", tmp_path / "nao_existe.py", tmp_path, python=sys.executable)

    async def cenario():
        sessao = _sessao(plano, tmp_path, [])
        try:
            await sessao.iniciar(plano.adapter_id, plano.lancamento, {})
        except ErroDAP as exc:  # o adaptador recusou o launch
            assert "não iniciou" in str(exc)
            return
        try:  # ou o Python começou e saiu com erro, explicando na saída
            assert await _esperar(lambda: sessao.terminou)
            assert sessao.codigo_saida not in (0, None)
            assert "nao_existe.py" in "".join(t for _, t in sessao.saida)
        finally:
            await sessao.encerrar()
    asyncio.run(cenario())


@pytest.mark.slow
def test_c_compilado_e_depurado_pelo_gdb(tmp_path):
    if (dap.versao_gdb() or 0) < 14 or not shutil.which("cc"):
        pytest.skip("gdb 14+ ou compilador C ausente")
    arquivo = tmp_path / "alvo.c"
    arquivo.write_text("#include <stdio.h>\nint dobro(int x) {\n    int y = x * 2;\n    return y;\n}\n"
                       "int main(void) {\n    int r = dobro(21);\n    printf(\"depois %d\\n\", r);\n    return 0;\n}\n")
    plano = dap.plano("c", arquivo, tmp_path, python=sys.executable, pasta_build=tmp_path / "build")
    assert plano.falta == ""
    (tmp_path / "build").mkdir()
    subprocess.run(plano.compilar, check=True, capture_output=True)
    eventos = []

    async def cenario():
        sessao = _sessao(plano, tmp_path, eventos)
        await sessao.iniciar(plano.adapter_id, plano.lancamento, {arquivo: [2]},  # int y = x * 2;
                             configurar_antes=plano.configurar_antes)
        try:
            assert await _esperar(lambda: sessao.parado_em is not None)
            [quadro, *_] = await sessao.pilha()
            assert (quadro.nome, quadro.linha, quadro.caminho.name) == ("dobro", 2, "alvo.c")
            valores = {v.nome: v.valor for e in await sessao.escopos(quadro.id) if not e.caro
                       for v in await sessao.variaveis(e.referencia)}
            assert valores["x"] == "21"
            await sessao.sair()  # volta para main
            assert await _esperar(lambda: sessao.parado_em is not None and sessao.motivo_parada != "breakpoint")
            assert (await sessao.pilha())[0].nome == "main"
            await sessao.continuar()
            assert await _esperar(lambda: sessao.terminou)
            assert sessao.codigo_saida == 0 and "depois 42" in "".join(t for _, t in sessao.saida)
        finally:
            await sessao.encerrar()
    asyncio.run(cenario())


_FONTES_COMPILADAS = {
    "cpp": ("alvo.cpp", "#include <iostream>\nint dobro(int x) {\n    int y = x * 2;\n    return y;\n}\n"
                        "int main() {\n    int r = dobro(21);\n    std::cout << \"depois \" << r << std::endl;\n"
                        "    return 0;\n}\n"),
    "rust": ("alvo.rs", "// alvo\nfn dobro(x: i32) -> i32 {\n    let y = x * 2;\n    y\n}\n"
                        "fn main() {\n    let r = dobro(21);\n    println!(\"depois {}\", r);\n}\n"),
}


@pytest.mark.slow
@pytest.mark.parametrize("lang", sorted(_FONTES_COMPILADAS))
def test_cpp_e_rust_compilados_e_depurados_pelo_gdb(tmp_path, lang):
    nome, fonte = _FONTES_COMPILADAS[lang]
    arquivo = tmp_path / nome
    arquivo.write_text(fonte)
    plano = dap.plano(lang, arquivo, tmp_path, python=sys.executable, pasta_build=tmp_path / "build")
    if plano.falta:
        pytest.skip(plano.falta)
    (tmp_path / "build").mkdir()
    subprocess.run(plano.compilar, check=True, capture_output=True)
    eventos = []

    async def cenario():
        sessao = _sessao(plano, tmp_path, eventos)
        await sessao.iniciar(plano.adapter_id, plano.lancamento, {arquivo: [2]},  # y = x * 2
                             configurar_antes=plano.configurar_antes)
        try:
            assert await _esperar(lambda: sessao.parado_em is not None)
            [quadro, *_] = await sessao.pilha()
            assert "dobro" in quadro.nome and (quadro.linha, quadro.caminho.name) == (2, nome)
            valores = {v.nome: v.valor for e in await sessao.escopos(quadro.id) if not e.caro
                       for v in await sessao.variaveis(e.referencia)}
            assert valores["x"] == "21"
            await sessao.sair()
            assert await _esperar(lambda: sessao.parado_em is not None and sessao.motivo_parada != "breakpoint")
            assert "main" in (await sessao.pilha())[0].nome
            await sessao.continuar()
            assert await _esperar(lambda: sessao.terminou)
            assert sessao.codigo_saida == 0 and "depois 42" in "".join(t for _, t in sessao.saida)
        finally:
            await sessao.encerrar()
    asyncio.run(cenario())


def test_planos_por_linguagem(tmp_path):
    sem_debugpy = shutil.which("python3", path="/usr/bin")
    if sem_debugpy and not _tem_debugpy(sem_debugpy):
        plano = dap.plano("python", tmp_path / "a.py", tmp_path, python=sem_debugpy)
        assert "debugpy" in plano.falta and plano.instalar[-1] == "debugpy"
    rust = dap.plano("rust", tmp_path / "main.rs", tmp_path, python=sys.executable, pasta_build=tmp_path)
    assert rust.compilar[:4] == [rust.compilar[0], "-g", "-C", "opt-level=0"]
    assert rust.lancamento["program"] == str(tmp_path / "main")
    assert dap.plano("html", tmp_path / "a.html", tmp_path, python=sys.executable) is None
