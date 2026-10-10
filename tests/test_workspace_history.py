import os
import random

import pytest

from codar.workspace import Change, EditConflict, EditStore, hunks, select_hunks


@pytest.fixture
def store(tmp_path, monkeypatch):
    root = tmp_path / "project"
    root.mkdir()
    monkeypatch.setenv("CODAR_HOME", str(tmp_path / "data"))
    return EditStore(root)


def test_proposta_nao_altera_arquivo_e_recupera_depois_de_reabrir(store):
    file = store.root / "a.py"
    file.write_text("x=1\n", encoding="utf-8", newline="")
    record = store.create([Change("a.py", "x=1\n", "x=2\n")], "corrija")
    assert file.read_text() == "x=1\n"
    reopened = EditStore(store.root)
    assert reopened.list()[0]["id"] == record["id"]
    reopened.apply(record["id"])
    assert file.read_text() == "x=2\n"
    reopened.restore(record["id"])
    assert file.read_text() == "x=1\n"


def test_aplicar_e_restaurar_recusam_mudancas_posteriores(store):
    file = store.root / "a.py"
    file.write_text("x=1\n", encoding="utf-8", newline="")
    record = store.create([Change("a.py", "x=1\n", "x=2\n")])
    file.write_text("x=3\n", encoding="utf-8", newline="")
    with pytest.raises(EditConflict, match="mudou"):
        store.apply(record["id"])
    assert file.read_text() == "x=3\n"
    file.write_text("x=1\n", encoding="utf-8", newline="")
    store.apply(record["id"])
    file.write_text("x=4\n", encoding="utf-8", newline="")
    with pytest.raises(EditConflict):
        store.restore(record["id"])
    assert file.read_text() == "x=4\n"


def test_falha_no_segundo_arquivo_desfaz_o_primeiro(store, monkeypatch):
    for name in ("a.py", "b.py"):
        (store.root / name).write_text("x=1\n", encoding="utf-8", newline="")
    record = store.create([Change(n, "x=1\n", "x=2\n") for n in ("a.py", "b.py")])
    real = os.replace
    def fail(source, destination):
        if str(destination) == str(store.root / "b.py"):
            raise OSError("falha de publicação")
        return real(source, destination)
    monkeypatch.setattr(os, "replace", fail)
    with pytest.raises(OSError):
        store.apply(record["id"])
    assert all((store.root / n).read_text() == "x=1\n" for n in ("a.py", "b.py"))
    assert store.get(record["id"])["status"] == "draft"


def test_recuperacao_de_interrupcao_preserva_alteracao_externa(store):
    (store.root / "a.py").write_text("x=2\n", encoding="utf-8", newline="")
    (store.root / "b.py").write_text("x=9\n", encoding="utf-8", newline="")
    changes = [Change(n, "x=1\n", "x=2\n") for n in ("a.py", "b.py")]
    record = store.create(changes)
    raw = store.get(record["id"])
    raw.update(status="applying", previous_status="draft", transaction=raw["changes"])
    store._write(raw)
    result = store.recover()
    assert result[0]["conflicts"] == ["b.py"]
    assert (store.root / "a.py").read_text() == "x=1\n"
    assert (store.root / "b.py").read_text() == "x=9\n"


def test_selecao_de_um_trecho_aplica_somente_aquela_mudanca(store):
    before = "\n".join(f"v{i}={i}" for i in range(30)) + "\n"
    after = before.replace("v1=1\n", "v1=101\n").replace("v28=28\n", "v28=128\n")
    (store.root / "a.py").write_text(before, encoding="utf-8", newline="")
    record = store.create([Change("a.py", before, after)])
    assert len(record["hunks"]) == 2
    store.apply(record["id"], [record["hunks"][0]["id"]])
    assert (store.root / "a.py").read_text() == before.replace("v1=1\n", "v1=101\n")
    store.restore(record["id"])
    assert (store.root / "a.py").read_text() == before


def test_hunks_reconstroem_edicoes_com_insercoes_remocoes_e_crlf():
    randomizer = random.Random(42)
    for _ in range(100):
        before = [f"x{i}={i}\r\n" for i in range(30)]
        after = before.copy()
        for _ in range(4):
            at = randomizer.randrange(len(after))
            after[at:at + randomizer.randrange(3)] = ["novo=1\r\n"]
        change = Change("a.py", "".join(before), "".join(after))
        parts = hunks(change)
        assert select_hunks(change, {h["id"] for h in parts}).after == change.after
        assert select_hunks(change, set()).after == change.before


def test_recusa_sintaxe_invalida_e_definicao_duplicada(store):
    before = "def f():\n    return 1\n"
    (store.root / "a.py").write_text(before, encoding="utf-8", newline="")
    for after in ("def f(:\n", before + before):
        record = store.create([Change("a.py", before, after)])
        with pytest.raises(ValueError, match="sintaxe"):
            store.apply(record["id"])
        assert (store.root / "a.py").read_text() == before


def test_arquivo_novo_e_permissoes_preservados(store):
    record = store.create([Change("lib/a.py", None, "x=1\n")])
    store.apply(record["id"])
    assert (store.root / "lib/a.py").read_text() == "x=1\n"
    store.restore(record["id"])
    assert not (store.root / "lib/a.py").exists()
    file = store.root / "exec.py"
    file.write_text("x=1\n", encoding="utf-8", newline="")
    file.chmod(0o755)
    record = store.create([Change("exec.py", "x=1\n", "x=2\n")])
    store.apply(record["id"])
    if os.name != "nt":
        assert file.stat().st_mode & 0o777 == 0o755


def test_snapshot_do_editor_exige_confirmacao_e_continua_disponivel(store):
    record = store.create([Change("a.py", "x=1", "x=2")], status="prepared")
    assert store.list()[0]["status"] == "prepared"
    store.commit_buffer(record["id"])
    assert store.list()[0]["status"] == "buffer"
    with pytest.raises(EditConflict):
        store.apply(record["id"])


def test_historico_ignora_registro_corrompido(store):
    (store.directory / ("a" * 32 + ".json")).write_text("{", encoding="utf-8", newline="")
    assert store.list() == []
    assert store.recover() == []


def test_historico_do_buffer_restaura_apos_salvar_crlf(store):
    file = store.root / "a.py"
    before, after = "x=1\ny=2\n", "x=3\ny=4\n"
    record = store.create([Change("a.py", before, after)], status="buffer")
    file.write_bytes(after.replace("\n", "\r\n").encode())
    store.restore(record["id"])
    assert file.read_bytes() == before.replace("\n", "\r\n").encode()
