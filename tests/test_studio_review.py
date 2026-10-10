"""Prévia real do Studio: cancelar, aceitar, desfazer e recusar uma resposta atrasada."""

import asyncio

import pytest

pytest.importorskip("textual")

from codar.studio.app import Studio
from codar.studio.edits import EditTarget
from codar.studio.review import ReviewScreen
from codar.workspace import EditStore


class Backend:
    def stats(self):
        raise RuntimeError("sem daemon")

    def close(self):
        pass


@pytest.mark.parametrize("action", ["cancel", "accept", "changed", "invalid"])
def test_revisao_protege_editor_e_guarda_original(tmp_path, monkeypatch, action):
    monkeypatch.setenv("CODAR_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CODAR_NO_AUTOSTART", "1")
    file = tmp_path / "a.py"
    original = "x = 1\n"
    file.write_text(original, encoding="utf-8", newline="")
    app = Studio(tmp_path)
    app.backend = Backend()
    body = "x = 2\n" if action != "invalid" else "def f(:\n"
    res = dict(stage="2", source="teste", timings={}, body=body, code=body, lang="python",
               imports=[], findings=[], notes=[], complete=True)

    async def wait(pilot, condition):
        for _ in range(80):
            await pilot.pause(0.05)
            if condition():
                return
        assert condition()

    async def scenario():
        async with app.run_test(size=(150, 42)) as pilot:
            await app.open_file(file)
            await pilot.pause(0.2)
            editor = app.current_editor()
            target = EditTarget.capture(editor.text, "edit", (0, 0), ((0, 0), (0, 0)))
            app._apply(res, target, editor.id, "")
            await wait(pilot, lambda: isinstance(app.screen, ReviewScreen))
            assert editor.text == original
            if action == "cancel":
                await pilot.press("escape")
                assert editor.text == original and EditStore(tmp_path).list() == []
            else:
                if action == "changed":
                    editor.replace("x = 9\n", (0, 0), editor.document.end)
                await pilot.click("#review-apply")
                await asyncio.wait_for(asyncio.gather(*(worker.wait() for worker in app.workers
                                                        if worker.group == "review")), timeout=5)
                await pilot.pause(0.1)
                if action == "accept":
                    assert editor.text == body
                    records = EditStore(tmp_path).list()
                    assert records[0]["status"] == "buffer"
                    assert EditStore(tmp_path).get(records[0]["id"])["changes"][0]["before"] == original
                    editor.action_undo()
                    assert editor.text == original
                else:
                    assert editor.text == ("x = 9\n" if action == "changed" else original)
                    assert EditStore(tmp_path).list() == []
            assert file.read_text() == original
    asyncio.run(scenario())
