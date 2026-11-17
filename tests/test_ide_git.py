"""Git do Studio contra repositórios de verdade: estado, trechos, commit, branches, marcas e conflitos."""

import os
import shutil
import subprocess

import pytest

from codar.ide import git
from codar.ide.git import ErroGit, Repositorio

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git não instalado")

LINHAS = [f"linha {n}" for n in range(1, 31)]


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """Repositório novo, com identidade própria e sem a configuração global de quem roda os testes."""
    config = tmp_path / "gitconfig"
    config.write_text("")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for variavel in ("GIT_AUTHOR_NAME", "GIT_COMMITTER_NAME"):
        monkeypatch.setenv(variavel, "Pessoa Teste")
    for variavel in ("GIT_AUTHOR_EMAIL", "GIT_COMMITTER_EMAIL"):
        monkeypatch.setenv(variavel, "pessoa@exemplo.invalid")
    for variavel in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        monkeypatch.delenv(variavel, raising=False)
    raiz = tmp_path / "projeto"
    raiz.mkdir()
    sh(raiz, "init", "-q", "-b", "main")
    return raiz


def sh(pasta, *args, ok=(0,)):
    saida = subprocess.run(["git", *args], cwd=pasta, capture_output=True, text=True)
    assert saida.returncode in ok, saida.stderr
    return saida.stdout


def escrever(raiz, nome, texto):
    caminho = raiz / nome
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(texto, encoding="utf-8")
    return caminho


def commitar(raiz, mensagem="base"):
    sh(raiz, "add", "-A")
    sh(raiz, "commit", "-q", "-m", mensagem)


def test_abrir_acha_a_raiz_e_recusa_pasta_sem_git(repo, tmp_path):
    (repo / "src" / "pacote").mkdir(parents=True)
    aberto = Repositorio.abrir(repo / "src" / "pacote")
    assert aberto is not None and aberto.raiz == repo.resolve()
    assert aberto.pasta_git() == (repo / ".git").resolve()
    fora = tmp_path / "solto"
    fora.mkdir()
    assert Repositorio.abrir(fora) is None
    with pytest.raises(ErroGit):
        aberto.absoluto("../fora.txt")


def test_repositorio_sem_commits(repo):
    r = Repositorio.abrir(repo)
    estado = r.estado()
    assert estado.branch == "main" and estado.commit is None and not r.tem_commits()
    assert r.historico() == [] and estado.mudancas == []
    escrever(repo, "a.py", "print(1)\n")
    assert r.estado().mudancas == [git.Mudanca("a.py", "?", "?")]
    r.preparar(["a.py"])
    assert r.estado().mudancas == [git.Mudanca("a.py", "A", ".")]
    assert r.original("a.py") == "print(1)\n"
    r.despreparar(["a.py"])  # sem HEAD, "restore --staged" não funciona: tira do índice com rm --cached
    assert r.estado().mudancas[0].nova and (repo / "a.py").exists()
    r.preparar(["a.py"])
    assert len(r.commit("primeiro commit")) >= 7
    assert [c.assunto for c in r.historico()] == ["primeiro commit"]


def test_estado_le_preparadas_alteradas_renomeadas_apagadas_e_novas(repo):
    for nome in ("a.txt", "b.txt", "velho.txt", "some.txt"):
        escrever(repo, nome, f"{nome}\n")
    commitar(repo)
    escrever(repo, "a.txt", "a mudou\n")  # só no trabalho
    escrever(repo, "b.txt", "b preparado\n")
    sh(repo, "add", "b.txt")
    escrever(repo, "b.txt", "b preparado e mudou de novo\n")  # preparado e alterado depois
    sh(repo, "mv", "velho.txt", "novo nome.txt")  # renomeação com espaço no nome
    (repo / "some.txt").unlink()
    escrever(repo, "pasta/ção nova.txt", "acentos\n")
    r = Repositorio.abrir(repo)
    estado = r.estado()
    por_nome = {m.caminho: m for m in estado.mudancas}
    assert set(por_nome) == {"a.txt", "b.txt", "novo nome.txt", "some.txt", "pasta/ção nova.txt"}
    assert por_nome["a.txt"].alterada and not por_nome["a.txt"].preparada
    assert por_nome["b.txt"].alterada and por_nome["b.txt"].preparada
    assert por_nome["novo nome.txt"].indice == "R" and por_nome["novo nome.txt"].origem == "velho.txt"
    assert por_nome["some.txt"].trabalho == "D" and por_nome["some.txt"].alterada
    assert por_nome["pasta/ção nova.txt"].nova and not por_nome["pasta/ção nova.txt"].alterada
    assert estado.branch == "main" and estado.commit and not estado.em_merge and estado.upstream is None


def test_trechos_preparar_despreparar_e_descartar(repo):
    escrever(repo, "lista.txt", "\n".join(LINHAS) + "\n")
    commitar(repo)
    alterado = LINHAS.copy()
    alterado[1] = "linha 2 alterada"
    alterado.insert(2, "linha inserida")
    alterado[25] = "perto do fim alterada"
    escrever(repo, "lista.txt", "\n".join(alterado) + "\n")
    r = Repositorio.abrir(repo)
    diff = r.diferenca("lista.txt")
    assert len(diff.trechos) == 2 and not diff.binario
    assert diff.trechos[0].inicio_novo == 0 and "+linha inserida" in diff.trechos[0].linhas
    assert any(linha == "+perto do fim alterada" for linha in diff.trechos[1].linhas)

    r.preparar_trechos(diff, [1])  # só o segundo trecho vai para o índice
    preparado = r.diferenca("lista.txt", preparada=True)
    assert len(preparado.trechos) == 1 and "+perto do fim alterada" in preparado.trechos[0].linhas
    restante = r.diferenca("lista.txt")
    assert len(restante.trechos) == 1 and "+linha inserida" in restante.trechos[0].linhas
    assert "perto do fim alterada" in r.original("lista.txt") and "linha inserida" not in r.original("lista.txt")

    r.despreparar_trechos(preparado, [0])
    assert r.diferenca("lista.txt", preparada=True) is None
    assert len(r.diferenca("lista.txt").trechos) == 2

    r.descartar_trechos(r.diferenca("lista.txt"), [0])  # desfaz só o primeiro trecho no arquivo
    texto = (repo / "lista.txt").read_text()
    assert "linha inserida" not in texto and "linha 2\n" in texto and "perto do fim alterada" in texto
    assert len(r.diferenca("lista.txt").trechos) == 1


def test_trecho_sem_quebra_no_fim_e_crlf(repo):
    escrever(repo, "fim.txt", "a\nb\nc")
    (repo / "dos.txt").write_bytes(b"um\r\ndois\r\n")
    commitar(repo)
    escrever(repo, "fim.txt", "a\nb\nC mudou")
    (repo / "dos.txt").write_bytes(b"um\r\nDOIS\r\n")
    r = Repositorio.abrir(repo)
    diff = r.diferenca("fim.txt")
    assert "\\ No newline at end of file" in diff.trechos[0].linhas
    r.preparar_trechos(diff, [0])
    assert r.original("fim.txt") == "a\nb\nC mudou"
    crlf = r.diferenca("dos.txt")
    assert any(linha.endswith("\r") for linha in crlf.trechos[0].linhas)  # o \r não se perde no caminho
    r.preparar_trechos(crlf, [0])
    assert r.diferenca("dos.txt") is None


def test_diferenca_de_arquivo_novo_e_binario(repo):
    escrever(repo, "x.txt", "x\n")
    commitar(repo)
    escrever(repo, "novo.py", "a = 1\nb = 2\n")
    (repo / "img.bin").write_bytes(bytes(range(256)))
    r = Repositorio.abrir(repo)
    novo = r.diferenca("novo.py")
    assert len(novo.trechos) == 1 and novo.trechos[0].linhas == ("+a = 1", "+b = 2")
    assert novo.trechos[0].inicio_novo == 0
    r.preparar_trechos(novo, [0])  # o patch de um arquivo novo cria o arquivo no índice
    assert r.original("novo.py") == "a = 1\nb = 2\n"
    assert r.diferenca("img.bin").binario


def test_descartar_arquivos_e_mover_nao_rastreado_para_a_lixeira(repo):
    from codar.studio.explorer import pasta_lixeira

    escrever(repo, "a.txt", "original\n")
    commitar(repo)
    escrever(repo, "a.txt", "estragado\n")
    escrever(repo, "lixo.txt", "temporário\n")
    r = Repositorio.abrir(repo)
    r.descartar(["a.txt"])
    assert (repo / "a.txt").read_text() == "original\n"
    lixeira = pasta_lixeira(repo)
    with pytest.raises(ErroGit):
        r.mover_nao_rastreado("a.txt", lixeira / "a.txt")  # rastreado: nunca sai por aqui
    r.mover_nao_rastreado("lixo.txt", lixeira / "lixo.txt")
    assert not (repo / "lixo.txt").exists() and (lixeira / "lixo.txt").read_text() == "temporário\n"
    # A lixeira (.codar) se ignora: nada dela aparece como arquivo novo.
    assert r.estado().mudancas == [] and (repo / ".codar" / ".gitignore").read_text().endswith("*\n")


def test_commit_emendar_historico_e_detalhes(repo):
    escrever(repo, "a.txt", "1\n")
    commitar(repo, "base")
    r = Repositorio.abrir(repo)
    with pytest.raises(ErroGit, match="nada preparado"):
        r.commit("sem nada")
    escrever(repo, "a.txt", "2\n")
    r.preparar(["a.txt"])
    with pytest.raises(ErroGit, match="mensagem"):
        r.commit("   ")
    curto = r.commit("Corrige a soma\n\nDetalhes com acentuação: ção.")
    historico = r.historico()
    assert [c.assunto for c in historico] == ["Corrige a soma", "base"] and historico[0].hash == curto
    assert historico[0].autor == "Pessoa Teste" and len(historico[0].data) == 10
    escrever(repo, "b.txt", "esqueci\n")
    r.preparar(["b.txt"])
    r.commit("", emendar=True)  # sem mensagem: mantém a do último commit
    assert [c.assunto for c in r.historico()] == ["Corrige a soma", "base"]
    assert "b.txt" in r.detalhes(r.historico()[0].hash)
    assert [c.assunto for c in r.historico(caminho="a.txt")] == ["Corrige a soma", "base"]
    with pytest.raises(ErroGit):
        r.detalhes("--output=/tmp/x")


def test_branches_criar_trocar_remoto_e_nomes_invalidos(repo, tmp_path):
    escrever(repo, "a.txt", "a\n")
    commitar(repo)
    r = Repositorio.abrir(repo)
    for invalido in ("a..b", "-x", "com espaço", "fim.lock", ""):
        with pytest.raises(ErroGit):
            r.criar_branch(invalido)
    r.criar_branch("feature/ideia")
    assert r.estado().branch == "feature/ideia"
    assert {(b.nome, b.atual) for b in r.branches()} == {("main", False), ("feature/ideia", True)}
    r.trocar_branch("main")
    assert r.estado().branch == "main"
    with pytest.raises(ErroGit):
        r.trocar_branch("--orphan")

    remoto = tmp_path / "remoto.git"
    sh(tmp_path, "init", "-q", "--bare", "-b", "main", str(remoto))
    sh(repo, "remote", "add", "origin", str(remoto))
    sh(repo, "push", "-q", "-u", "origin", "main")
    escrever(repo, "a.txt", "a2\n")
    commitar(repo, "local")
    outro = tmp_path / "outro"
    sh(tmp_path, "clone", "-q", str(remoto), str(outro))
    escrever(outro, "b.txt", "b\n")
    commitar(outro, "remoto 1")
    escrever(outro, "c.txt", "c\n")
    commitar(outro, "remoto 2")
    sh(outro, "push", "-q", "origin", "main")
    sh(repo, "fetch", "-q", "origin")
    estado = r.estado()
    assert estado.upstream == "origin/main" and (estado.a_frente, estado.atras) == (1, 2)
    branches = {b.nome: b for b in r.branches()}
    assert branches["origin/main"].remoto and branches["main"].upstream == "origin/main"
    assert "origin/HEAD" not in branches


def test_conflito_de_merge_resolvido_no_studio(repo):
    escrever(repo, "app.py", "def saudacao():\n    return 'oi'\n\nprint(saudacao())\n")
    commitar(repo)
    sh(repo, "switch", "-q", "-c", "outra")
    escrever(repo, "app.py", "def saudacao():\n    return 'olá'\n\nprint(saudacao())\n")
    commitar(repo, "outra")
    sh(repo, "switch", "-q", "main")
    escrever(repo, "app.py", "def saudacao():\n    return 'bom dia'\n\nprint(saudacao())\n")
    commitar(repo, "main")
    sh(repo, "merge", "outra", ok=(1,))
    r = Repositorio.abrir(repo)
    estado = r.estado()
    assert estado.em_merge and [m.caminho for m in estado.conflitos] == ["app.py"]
    assert not estado.conflitos[0].preparada and not estado.conflitos[0].alterada
    texto = (repo / "app.py").read_text()
    blocos = git.conflitos_no_texto(texto)
    assert len(blocos) == 1
    assert blocos[0].nosso == ("    return 'bom dia'",) and blocos[0].deles == ("    return 'olá'",)
    assert blocos[0].rotulo_nosso == "HEAD" and blocos[0].rotulo_deles == "outra"
    resolvido = git.resolver_conflito(texto, 0, "ambos")
    assert "<<<<<<<" not in resolvido and "return 'bom dia'\n    return 'olá'\n" in resolvido
    assert git.resolver_conflito(texto, 0, "deles").startswith("def saudacao():\n    return 'olá'\n")
    escrever(repo, "app.py", git.resolver_conflito(texto, 0, "nosso"))
    r.preparar(["app.py"])
    r.commit("Merge da outra")
    assert not r.estado().em_merge and r.estado().mudancas == []


def test_abortar_merge_e_conflito_diff3(repo):
    escrever(repo, "a.txt", "base\n")
    commitar(repo)
    sh(repo, "switch", "-q", "-c", "outra")
    escrever(repo, "a.txt", "deles\n")
    commitar(repo, "outra")
    sh(repo, "switch", "-q", "main")
    escrever(repo, "a.txt", "nosso\n")
    commitar(repo, "main")
    sh(repo, "-c", "merge.conflictStyle=diff3", "merge", "outra", ok=(1,))
    texto = (repo / "a.txt").read_text()
    assert "|||||||" in texto
    bloco = git.conflitos_no_texto(texto)[0]
    assert (bloco.nosso, bloco.deles) == (("nosso",), ("deles",))  # a base não entra em nenhum dos lados
    r = Repositorio.abrir(repo)
    r.abortar_merge()
    assert not r.estado().em_merge and (repo / "a.txt").read_text() == "nosso\n"


@pytest.mark.parametrize("original,atual,esperado", [
    ("a\nb\nc\n", "a\nb\nc\n", {}),
    ("a\nb\nc\n", "a\nX\nc\n", {1: "alterado"}),
    ("a\nb\nc\n", "a\nb\nnova\nc\n", {2: "novo"}),
    ("a\nb\nc\n", "a\nc\n", {1: "apagado"}),
    ("a\nb\nc\n", "a\nb\n", {2: "apagado"}),  # apagou a última: a marca fica na linha vazia do fim
    ("a\nb\n", "a\nb\nc\nd\n", {2: "novo", 3: "novo"}),
    ("a\r\nb\r\n", "a\nB\n", {1: "alterado"}),
    (None, "x\ny\n", {0: "novo", 1: "novo"}),
])
def test_marcas_de_linha(original, atual, esperado):
    assert git.marcas_de_linha(original, atual) == esperado


def test_analisar_diff_sem_diferenca_e_patch_so_dos_escolhidos():
    assert git.analisar_diff("x", "") is None
    texto = ("diff --git a/x b/x\nindex 1..2 100644\n--- a/x\n+++ b/x\n@@ -1,2 +1,2 @@\n-a\n+A\n b\n"
             "@@ -10,1 +9,0 @@ def f():\n-velha\n")
    diff = git.analisar_diff("x", texto)
    assert [t.inicio_novo for t in diff.trechos] == [0, 9]  # sem linhas do lado novo: a remoção fica depois da 9
    assert diff.patch([1]) == "diff --git a/x b/x\nindex 1..2 100644\n--- a/x\n+++ b/x\n@@ -10,1 +9,0 @@ def f():\n-velha\n"


def test_git_ausente(monkeypatch, tmp_path):
    monkeypatch.setattr(git.shutil, "which", lambda nome: None)
    assert Repositorio.abrir(tmp_path) is None
    ambiente = git._ambiente()
    assert ambiente["GIT_TERMINAL_PROMPT"] == "0" and ambiente["GIT_OPTIONAL_LOCKS"] == "0"
    assert ambiente is not os.environ  # uma cópia: o ambiente do próprio Studio não muda
