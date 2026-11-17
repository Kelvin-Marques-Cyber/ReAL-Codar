"""Cliente LSP: protocolo, posições em UTF-16 e servidores reais (pylsp, pyright, clangd, gopls, TypeScript)."""

import asyncio
import os
import shutil
import sys
import textwrap
from pathlib import Path

import pytest

from codar.ide import lsp
from codar.ide.lsp import ClienteLSP, Edicao, ErroLSP, GerenteLSP, Intervalo

FALSO = [sys.executable, str(Path(__file__).with_name("lsp_falso.py"))]
# Servidores instalados no Python dos testes (pylsp) também entram no PATH.
PATH = os.pathsep.join([str(Path(sys.executable).parent), os.environ.get("PATH", "")])


async def _esperar(condicao, tentativas=250):
    for _ in range(tentativas):
        if condicao():
            return True
        await asyncio.sleep(.04)
    return condicao()


def test_colunas_em_utf16_com_acentos_e_emoji():
    linha = "s = 'ação 😀 alvo'"
    i = linha.index("alvo")
    assert lsp.para_unidades(linha, i, "utf-16") == i + 1  # o emoji ocupa duas unidades UTF-16
    assert lsp.de_unidades(linha, i + 1, "utf-16") == i
    assert lsp.para_unidades(linha, i, "utf-32") == i
    assert lsp.para_unidades(linha, i, "utf-8") == len(linha[:i].encode())
    assert lsp.de_unidades(linha, len(linha[:i].encode()), "utf-8") == i
    assert lsp.de_unidades(linha, 999, "utf-16") == len(linha)


def test_edicoes_aplicadas_de_tras_para_frente_preservando_crlf():
    texto = "a = alvo\r\nb = alvo + alvo\r\n"
    edicoes = [Edicao(Intervalo(1, 11, 1, 15), "novo"), Edicao(Intervalo(0, 4, 0, 8), "novo"),
               Edicao(Intervalo(1, 4, 1, 8), "novo")]
    assert lsp.aplicar(texto, edicoes) == "a = novo\r\nb = novo + novo\r\n"
    assert lsp.aplicar("x", [Edicao(Intervalo(0, 1, 0, 1), "y"), Edicao(Intervalo(9, 0, 9, 0), "!")]) == "xy!"


def test_uri_ida_e_volta(tmp_path):
    arquivo = tmp_path / "pasta com espaço" / "ação.py"
    assert lsp.caminho_de(lsp.uri_de(arquivo)) == arquivo.resolve()
    assert lsp.caminho_de("untitled:Untitled-1") is None
    assert lsp.texto_simples({"kind": "markdown", "value": "```python\nx: int\n```"}) == "x: int"
    assert lsp.texto_simples(["a", {"language": "py", "value": "b"}]) == "a\n\nb"


def test_cliente_fala_o_protocolo_inteiro(tmp_path):
    arquivo = tmp_path / "m.py"
    texto = "# comentário\nalvo = 1\nprint(alvo)  # 😀 erro\n"
    arquivo.write_text(texto, encoding="utf-8")
    diags = {}

    async def cenario():
        cliente = ClienteLSP(FALSO, tmp_path, ao_diagnosticar=lambda caminho, d: diags.__setitem__(caminho, d),
                             configuracao={"settings": {"falso": {"nivel": 3}}})
        await cliente.iniciar()
        try:
            await cliente.abrir(arquivo, "python", texto)
            assert await _esperar(lambda: arquivo.resolve() in diags)
            diag = diags[arquivo.resolve()][0]
            assert (diag.severidade, diag.fonte, diag.codigo, diag.mensagem) == ("error", "falso", "F1", "palavra proibida")
            coluna = texto.splitlines()[2].index("erro")
            assert diag.intervalo == Intervalo(2, coluna, 2, coluna + 4)  # depois do emoji, em caracteres do Python
            item = (await cliente.completar(arquivo, 1, 2))[0]
            assert (item.rotulo, item.tipo, item.documentacao) == ("alvo_completo", "função", "Faz **algo**.")
            assert await cliente.informacoes(arquivo, 1, 1) == "alvo: int"
            assert await cliente.assinatura(arquivo, 2, 7) == "alvo(x: int) -> int"
            [local] = await cliente.definicao(arquivo, 2, 7)
            assert (local.caminho, local.intervalo) == (arquivo.resolve(), Intervalo(1, 0, 1, 4))
            assert len(await cliente.referencias(arquivo, 1, 0)) == 2
            edicoes = await cliente.renomear(arquivo, 1, 0, "novo")
            assert lsp.aplicar(texto, edicoes[arquivo.resolve()]) == texto.replace("alvo", "novo")
            assert lsp.aplicar(texto, await cliente.formatar(arquivo)).startswith("# formatado\n# comentário")
            await cliente.alterar(arquivo, texto.replace("erro", "ok"))
            assert await _esperar(lambda: diags[arquivo.resolve()] == [])
            await cliente.salvar(arquivo, texto)
            assert await _esperar(lambda: "salvo com texto" in cliente.mensagens)
        finally:
            await cliente.encerrar()
        assert not cliente.vivo
        assert 'configuracao=[3]' in cliente.processo.ultimas_linhas(20)  # respondeu ao workspace/configuration
    asyncio.run(cenario())


def test_servidor_que_quebra_explica_o_motivo(tmp_path):
    comando = [sys.executable, "-c", "import sys; sys.stderr.write('faltou a biblioteca X'); sys.exit(3)"]

    async def cenario():
        with pytest.raises(ErroLSP, match="faltou a biblioteca X"):
            await ClienteLSP(comando, tmp_path, tempo=5).iniciar()
    asyncio.run(cenario())


def test_gerente_divide_o_servidor_e_lembra_o_que_falta(tmp_path):
    (tmp_path / "a.py").write_text("alvo = 1\n")
    (tmp_path / "b.py").write_text("alvo = 2\n")

    async def cenario():
        gerente = GerenteLSP(tmp_path, env={"PATH": PATH}, servidores={"python": FALSO, "go": ["nao-existe-gopls"]})
        try:
            primeiro = await gerente.abrir(tmp_path / "a.py", "python", "alvo = 1\n")
            segundo = await gerente.abrir(tmp_path / "b.py", "python", "alvo = 2\n")
            assert primeiro is segundo and gerente.aberto(tmp_path / "a.py")
            assert await gerente.abrir(tmp_path / "c.go", "go", "package main\n") is None
            assert "nenhum servidor instalado (nao-existe-gopls)" in gerente.estado()["go"]
            assert gerente.comando("javascript") is None or gerente.comando("javascript")[0].endswith("typescript-language-server")
            [local] = await gerente.definicao(tmp_path / "b.py", 0, 1)
            assert local.caminho == (tmp_path / "b.py").resolve()
            await gerente.fechar(tmp_path / "a.py")
            assert not gerente.aberto(tmp_path / "a.py")
            with pytest.raises(ErroLSP, match="nenhum servidor"):
                await gerente.informacoes(tmp_path / "a.py", 0, 0)
        finally:
            await gerente.encerrar()
    asyncio.run(cenario())


# --------------------------------------------------------------------------------------- servidores reais
def _real(nome):
    if not shutil.which(nome, path=PATH):
        pytest.skip(f"{nome} ausente")


def _projeto(raiz: Path, arquivos: dict[str, str]):
    for nome, conteudo in arquivos.items():
        (raiz / nome).parent.mkdir(parents=True, exist_ok=True)
        (raiz / nome).write_text(textwrap.dedent(conteudo), encoding="utf-8")


def _rodar(raiz, lang, principal, verificar, servidores=None):
    diags = {}

    async def cenario():
        gerente = GerenteLSP(raiz, env={**os.environ, "PATH": PATH}, servidores=servidores,
                             ao_diagnosticar=lambda caminho, d: diags.__setitem__(caminho, d))
        try:
            caminho = raiz / principal
            assert await gerente.abrir(caminho, lang, caminho.read_text()) is not None, gerente.estado()
            await verificar(gerente, caminho, diags)
        finally:
            await gerente.encerrar()
    asyncio.run(cenario())


@pytest.mark.slow
def test_pylsp_diagnostico_definicao_referencias_e_renomear_entre_arquivos(tmp_path):
    _real("pylsp")
    _projeto(tmp_path, {"calc.py": "def somar(a, b):\n    return a + b\n",
                        "main.py": "from calc import somar\n\ntotal = somar(2, 3)\nprint(totl)\n"})

    async def verificar(gerente, main, diags):
        assert await _esperar(lambda: any("totl" in d.mensagem for d in diags.get(main.resolve(), [])))
        [local] = await gerente.definicao(main, 2, 9)
        assert local.caminho == (tmp_path / "calc.py").resolve() and local.intervalo.linha == 0
        caminhos = {r.caminho.name for r in await gerente.referencias(main, 2, 9)}
        assert {"calc.py", "main.py"} <= caminhos
        assert "somar" in await gerente.informacoes(main, 2, 9)
        assert any(i.rotulo.startswith("somar") for i in await gerente.completar(main, 2, 11))
        edicoes = await gerente.renomear(main, 2, 9, "adicionar")
        novo = lsp.aplicar((tmp_path / "calc.py").read_text(), edicoes[(tmp_path / "calc.py").resolve()])
        assert novo.startswith("def adicionar(a, b):")
    _rodar(tmp_path, "python", "main.py", verificar)


@pytest.mark.slow
def test_pyright_acusa_erro_de_tipo(tmp_path):
    _real("pyright-langserver")
    _projeto(tmp_path, {"tipos.py": "idade: int = 'vinte'\n"})

    async def verificar(gerente, arquivo, diags):
        assert await _esperar(lambda: any(d.severidade == "error" for d in diags.get(arquivo.resolve(), [])))
    _rodar(tmp_path, "python", "tipos.py", verificar, servidores={"python": ["pyright-langserver", "--stdio"]})


@pytest.mark.slow
def test_clangd_diagnostico_e_definicao_em_c(tmp_path):
    _real("clangd")
    _projeto(tmp_path, {"main.c": "int dobro(int x) { return x * 2; }\nint main(void) { return dobro(nada); }\n"})

    async def verificar(gerente, arquivo, diags):
        assert await _esperar(lambda: any("nada" in d.mensagem for d in diags.get(arquivo.resolve(), [])))
        [local] = await gerente.definicao(arquivo, 1, 26)
        assert local.intervalo.linha == 0
    _rodar(tmp_path, "c", "main.c", verificar)


@pytest.mark.slow
def test_gopls_definicao_em_outro_arquivo_do_pacote(tmp_path):
    _real("gopls")
    _projeto(tmp_path, {"go.mod": "module exemplo\n\ngo 1.21\n",
                        "calc.go": "package main\n\nfunc Dobro(x int) int { return x * 2 }\n",
                        "main.go": "package main\n\nimport \"fmt\"\n\nfunc main() { fmt.Println(Dobro(2)) }\n"})

    async def verificar(gerente, arquivo, diags):
        [local] = await gerente.definicao(arquivo, 4, 27)
        assert local.caminho.name == "calc.go" and local.intervalo.linha == 2
    _rodar(tmp_path, "go", "main.go", verificar)


@pytest.mark.slow
def test_typescript_diagnostico_de_tipo_e_definicao_importada(tmp_path):
    _real("typescript-language-server")
    _projeto(tmp_path, {"tsconfig.json": '{"compilerOptions": {"strict": true}}\n',
                        "calc.ts": "export function dobro(x: number): number {\n  return x * 2;\n}\n",
                        "main.ts": "import { dobro } from \"./calc\";\nconst r: number = dobro(\"2\");\n"})

    async def verificar(gerente, arquivo, diags):
        assert await _esperar(lambda: any(d.severidade == "error" for d in diags.get(arquivo.resolve(), [])))
        [local] = await gerente.definicao(arquivo, 1, 19)
        assert local.caminho.name == "calc.ts" and local.intervalo.linha == 0
    _rodar(tmp_path, "typescript", "main.ts", verificar)
