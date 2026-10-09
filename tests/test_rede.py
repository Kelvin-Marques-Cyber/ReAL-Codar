"""Prévia na rede (ver no celular) e QR code: o servidor só entrega a pasta com o código certo no endereço, esconde
arquivos ocultos, recarrega páginas ao salvar e repassa servidores de desenvolvimento; o QR tem a estrutura certa."""

import http.server
import threading
import time
import urllib.error
import urllib.request

import pytest

from codar import rede
from codar.qr import QR


def _get(url: str) -> tuple[int, bytes]:
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as exc:
        return exc.code, b""


@pytest.fixture()
def previa(tmp_path, monkeypatch):
    monkeypatch.setenv("CODAR_HOME", str(tmp_path / "home"))
    (tmp_path / "site").mkdir()
    (tmp_path / "site" / "index.html").write_text("<html><body><h1>Oi</h1></body></html>", encoding="utf-8")
    (tmp_path / "site" / "grafico.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 100)
    (tmp_path / "site" / ".env").write_text("SENHA=123", encoding="utf-8")
    servidor = rede.ServidorPrevia(tmp_path / "site", porta=0, rede=False).iniciar()
    yield servidor, tmp_path / "site"
    servidor.parar()


def test_so_entrega_com_o_codigo_do_endereco_e_esconde_ocultos(previa):
    servidor, _ = previa
    base = f"http://127.0.0.1:{servidor.porta}"
    assert _get(f"{base}/")[0] == 404  # sem o código: nada
    assert _get(f"{base}/outrocodigo/")[0] == 404
    assert _get(f"{servidor.url_local}.env")[0] == 404  # arquivos ocultos nunca saem
    status, corpo = _get(servidor.url_local)
    assert status == 200 and b"<h1>Oi</h1>" in corpo and b"__codar__/versao" in corpo  # recarrega ao salvar
    status, corpo = _get(servidor.url_local + "grafico.png")
    assert status == 200 and corpo.startswith(b"\x89PNG")


def test_indice_mostra_as_imagens_e_a_versao_muda_ao_salvar(previa):
    servidor, pasta = previa
    (pasta / "index.html").unlink()
    status, corpo = _get(servidor.url_local)
    assert status == 200 and b'<img src="grafico.png"' in corpo and b".env" not in corpo
    antes = _get(servidor.url_local + "__codar__/versao")[1]
    time.sleep(0.05)
    (pasta / "novo.txt").write_text("x", encoding="utf-8")
    for _ in range(40):  # o vigia confere a cada 1,5 s
        if _get(servidor.url_local + "__codar__/versao")[1] != antes:
            break
        time.sleep(0.1)
    assert _get(servidor.url_local + "__codar__/versao")[1] != antes


def test_proxy_repassa_um_servidor_que_so_escuta_em_localhost(tmp_path):
    (tmp_path / "pagina.txt").write_text("servidor de desenvolvimento", encoding="utf-8")

    class Silencioso(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(tmp_path), **k)

        def log_message(self, *a):
            pass

    dev = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Silencioso)
    threading.Thread(target=dev.serve_forever, daemon=True).start()
    proxy = rede.ProxyRede(dev.server_address[1], porta=0, rede=False).iniciar()
    try:
        status, corpo = _get(f"http://127.0.0.1:{proxy.porta}/pagina.txt")
        assert status == 200 and corpo == b"servidor de desenvolvimento"
    finally:
        proxy.parar()
        dev.shutdown()


def test_qr_tem_localizadores_e_cabe_um_endereco_tipico():
    qr = QR("http://192.168.0.12:54321/k7Fq9xZa/")
    assert (qr.versao, qr.tamanho) == (3, 29)
    m = qr.modulos
    for cx, cy in ((0, 0), (22, 0), (0, 22)):  # os três quadrados dos cantos: borda escura, anel claro, centro escuro
        assert all(m[cy][cx + i] for i in range(7)) and not m[cy + 1][cx + 1] and m[cy + 3][cx + 3]
    assert [m[6][x] for x in range(8, 21)] == [x % 2 == 0 for x in range(8, 21)]  # linha de sincronismo
    with pytest.raises(ValueError):
        QR("x" * 400)


def test_qr_igual_ao_conferido_com_um_leitor_de_verdade():
    # matriz lida de volta pelo zxing-cpp (leitor de QR usado em apps): se o gerador mudar e ela mudar junto,
    # confira de novo com um leitor antes de atualizar
    esperado = [
        "#######.###...#######", "#.....#...##..#.....#", "#.###.#...#...#.###.#", "#.###.#.#.....#.###.#",
        "#.###.#.......#.###.#", "#.....#...##..#.....#", "#######.#.#.#.#######", "..........###........",
        "..#.###.###..#...#..#", "..####.##.#.###...##.", "....#.#...####..##.##", "##.##..#...#.##.....#",
        ".....##.##..#.#.#.#.#", "........###..###...#.", "#######..#..#..#..###", "#.....#.#.#######....",
        "#.###.#.#.######..###", "#.###.#........#.#.#.", "#.###.#.#.##.##.###.#", "#.....#...#...###..#.",
        "#######..#.#.#..#####",
    ]
    qr = QR("CODAR", "M", mascara=0)
    assert (qr.versao, qr.nivel) == (1, "H")  # sobrou espaço: o nível de correção sobe sozinho
    assert ["".join("#" if c else "." for c in linha) for linha in qr.modulos] == esperado


def test_f5_em_pagina_html_abre_a_previa_com_qr_no_studio(tmp_path, monkeypatch):
    pytest.importorskip("textual")
    import asyncio

    from codar.studio.app import Studio
    from codar.studio.screens import CelularScreen

    monkeypatch.setenv("CODAR_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CODAR_NO_AUTOSTART", "1")
    (tmp_path / "index.html").write_text("<html><body><p>pagina do teste</p></body></html>", encoding="utf-8")

    async def cenario():
        app = Studio(tmp_path)
        async with app.run_test(size=(150, 42)) as pilot:
            await app.open_file(tmp_path / "index.html")
            await pilot.pause(0.3)
            await pilot.press("f5")
            await pilot.pause(0.3)
            assert isinstance(app.screen, CelularScreen)
            url_local = app.screen.url_local
            assert url_local.endswith("/index.html") and app.rede_srv is not None
            status, corpo = await asyncio.to_thread(_get, url_local)
            assert status == 200 and b"pagina do teste" in corpo
            await pilot.press("p")  # para o servidor
            await pilot.pause(0.2)
            assert app.rede_srv is None

    asyncio.run(cenario())
