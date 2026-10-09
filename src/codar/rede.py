"""Ver no celular o que precisa de interface: prévia de páginas e imagens na rede local, e repasse de servidores de
desenvolvimento que só escutam em localhost (bun run dev, flask run, flutter run -d web-server).

- ServidorPrevia: serve uma pasta em http://IP:PORTA/CÓDIGO/, só leitura, sem arquivos ocultos (.env, .git), com uma
  página de índice que mostra as imagens e recarrega sozinha quando os arquivos mudam. O código aleatório no endereço
  impede que outro aparelho da rede veja só por adivinhar a porta.
- ProxyRede: repassa IP:PORTA -> 127.0.0.1:PORTA_DO_SERVIDOR (o servidor continua escutando só no computador).

Sem dependências; o endereço vira QR code (codar.qr) no Studio e no `codar servir`.
"""

from __future__ import annotations

import html
import json
import os
import secrets
import select
import shutil
import socket
import socketserver
import subprocess
import threading
import time
import urllib.parse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from codar import paths

IGNORAR = {"node_modules", "__pycache__", ".venv", "venv", "target", "dist", "build"}
_IMAGENS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".bmp"}
_RECARREGAR = """<script>(()=>{let v=null;setInterval(async()=>{try{const r=await fetch("%s__codar__/versao",
{cache:"no-store"});const t=await r.text();if(v!==null&&t!==v)location.reload();v=t}catch(e){}},1000)})()</script>"""


def ip_local() -> str:
    """O IP desta máquina na rede local (o que o celular usa). Não envia nada: só pergunta ao sistema a rota."""
    for alvo in ("10.255.255.255", "192.168.255.255", "8.8.8.8"):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect((alvo, 1))
                ip = s.getsockname()[0]
                if not ip.startswith("127."):
                    return ip
        except OSError:
            continue
    return "127.0.0.1"


def _porta_livre(host: str, porta: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, porta))
            return True
        except OSError:
            return False


def porta_preferida(host: str = "0.0.0.0") -> int:
    """A mesma porta de sessão para sessão (sorteada na primeira vez), para que uma regra de firewall valha sempre;
    se ela estiver ocupada, outra livre."""
    arquivo = paths.data_dir() / "rede.json"
    try:
        porta = int(json.loads(arquivo.read_text(encoding="utf-8"))["porta"])
    except (OSError, ValueError, KeyError):
        porta = 0
    if not porta:
        porta = secrets.choice(range(20000, 60000))
        try:
            arquivo.parent.mkdir(parents=True, exist_ok=True)
            arquivo.write_text(json.dumps({"porta": porta}), encoding="utf-8")
        except OSError:
            pass
    return porta if _porta_livre(host, porta) else 0


def aviso_firewall(porta: int) -> str | None:
    """Se um firewall está ativo, o comando para liberar a porta (vale até reiniciar)."""
    systemctl = shutil.which("systemctl")
    if not systemctl:
        return None
    for servico, comando in (("firewalld", f"sudo firewall-cmd --add-port={porta}/tcp"),
                             ("ufw", f"sudo ufw allow {porta}/tcp")):
        try:
            r = subprocess.run([systemctl, "is-active", servico], capture_output=True, text=True, timeout=3)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if r.stdout.strip() == "active":
            return f"o {servico} está ativo: se o celular não abrir, libere a porta com: {comando}"
    return None


def _assinatura(raiz: Path, limite: int = 5000) -> tuple[int, int]:
    """(arquivos, maior data de modificação) da pasta: muda quando algo é salvo."""
    n, maior = 0, 0
    for pasta, subpastas, nomes in os.walk(raiz):
        subpastas[:] = [d for d in subpastas if not d.startswith(".") and d not in IGNORAR]
        for nome in nomes:
            try:
                maior = max(maior, os.stat(os.path.join(pasta, nome)).st_mtime_ns)
            except OSError:
                continue
            n += 1
            if n >= limite:
                return n, maior
    return n, maior


class _Pagina(SimpleHTTPRequestHandler):
    servidor: ServidorPrevia

    def __init__(self, *args, servidor: ServidorPrevia, **kwargs) -> None:
        self.servidor = servidor
        super().__init__(*args, directory=str(servidor.raiz), **kwargs)

    def log_message(self, fmt: str, *args) -> None:  # sem barulho no terminal
        if self.servidor.ao_acessar:
            self.servidor.ao_acessar(self.address_string(), self.path)

    def _relativo(self) -> str | None:
        """O caminho pedido sem o código do endereço; None se o código não bate ou se é um arquivo oculto."""
        caminho = urllib.parse.unquote(urllib.parse.urlsplit(self.path).path)
        prefixo = f"/{self.servidor.token}"
        if caminho != prefixo and not caminho.startswith(prefixo + "/"):
            return None
        rel = caminho[len(prefixo):].lstrip("/")
        if any(p.startswith(".") for p in rel.split("/") if p) or any(p in IGNORAR for p in rel.split("/")):
            return None
        return rel

    def send_head(self):
        rel = self._relativo()
        if rel is None:
            self.send_error(404)
            return None
        if rel == "__codar__/versao":
            corpo = str(self.servidor.versao).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            return _Memoria(corpo)
        alvo = self.servidor.raiz / rel
        if alvo.is_dir() and not self.path.split("?")[0].endswith("/"):
            self.send_response(301)
            self.send_header("Location", self.path.split("?")[0] + "/")
            self.end_headers()
            return None
        if alvo.is_dir() and (alvo / "index.html").is_file():
            alvo = alvo / "index.html"
        if alvo.is_dir():
            return self._indice(alvo, rel)
        if alvo.suffix.lower() in (".html", ".htm") and alvo.is_file():
            texto = alvo.read_text(encoding="utf-8", errors="replace")
            script = _RECARREGAR % f"/{self.servidor.token}/"
            texto = texto.replace("</body>", script + "</body>") if "</body>" in texto else texto + script
            return self._enviar(texto.encode("utf-8"), "text/html; charset=utf-8")
        self.path = "/" + rel  # o resto (CSS, JS, imagens) o SimpleHTTPRequestHandler serve
        return super().send_head()

    def _enviar(self, corpo: bytes, tipo: str):
        self.send_response(200)
        self.send_header("Content-Type", tipo)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        return _Memoria(corpo)

    def _indice(self, pasta: Path, rel: str):
        itens = []
        for p in sorted(pasta.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            if p.name.startswith(".") or p.name in IGNORAR:
                continue
            nome = html.escape(p.name) + ("/" if p.is_dir() else "")
            href = urllib.parse.quote(p.name) + ("/" if p.is_dir() else "")
            if p.suffix.lower() in _IMAGENS:
                itens.append(f'<a class="img" href="{href}"><img src="{href}" loading="lazy"><span>{nome}</span></a>')
            else:
                itens.append(f'<a href="{href}">{nome}</a>')
        titulo = html.escape("/" + rel if rel else self.servidor.raiz.name)
        pagina = f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{titulo}</title><style>
body{{margin:0;padding:16px;background:#05040A;color:#f0b32a;font:16px/1.5 system-ui,sans-serif}}
h1{{font-size:18px;color:#47FFA9}}a{{display:block;padding:10px 12px;margin:6px 0;border:1px solid #7a5a14;
border-radius:8px;color:#f0b32a;text-decoration:none}}a.img img{{display:block;max-width:100%;border-radius:4px;
margin-bottom:6px;background:#fff}}small{{color:#6b551f}}</style></head><body><h1>CODAR · {titulo}</h1>
{"".join(itens) or "<p>pasta vazia</p>"}<small>atualiza sozinho quando você salva no Studio</small>
{_RECARREGAR % f"/{self.servidor.token}/"}</body></html>"""
        return self._enviar(pagina.encode("utf-8"), "text/html; charset=utf-8")


class _Memoria:
    """Corpo de resposta já pronto, no formato de arquivo que o SimpleHTTPRequestHandler copia."""

    def __init__(self, dados: bytes) -> None:
        self.dados = dados

    def read(self, n: int = -1) -> bytes:
        dados, self.dados = (self.dados, b"") if n < 0 else (self.dados[:n], self.dados[n:])
        return dados

    def close(self) -> None:
        pass


class _Servidor(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class ServidorPrevia:
    """Prévia de uma pasta na rede local (ou só neste computador, com rede=False)."""

    def __init__(self, raiz: str | Path, porta: int | None = None, rede: bool = True, ao_acessar=None) -> None:
        self.raiz = Path(raiz).resolve()
        self.rede = rede
        self.token = secrets.token_urlsafe(6).replace("-", "x").replace("_", "y")
        self.versao = 0
        self.ao_acessar = ao_acessar
        host = "0.0.0.0" if rede else "127.0.0.1"
        porta = porta_preferida(host) if porta is None else porta
        self._http = _Servidor((host, porta), partial(_Pagina, servidor=self))
        self.porta = self._http.server_address[1]
        self._parar = threading.Event()

    def iniciar(self) -> ServidorPrevia:
        threading.Thread(target=self._http.serve_forever, name="codar-previa", daemon=True).start()
        threading.Thread(target=self._vigiar, name="codar-previa-vigia", daemon=True).start()
        return self

    def _vigiar(self) -> None:
        antes = _assinatura(self.raiz)
        while not self._parar.wait(1.5):
            agora = _assinatura(self.raiz)
            if agora != antes:
                antes = agora
                self.versao += 1

    def avisar_mudanca(self) -> None:
        self.versao += 1

    def parar(self) -> None:
        self._parar.set()
        self._http.shutdown()
        self._http.server_close()

    @property
    def url_local(self) -> str:
        return f"http://127.0.0.1:{self.porta}/{self.token}/"

    @property
    def url_rede(self) -> str | None:
        return f"http://{ip_local()}:{self.porta}/{self.token}/" if self.rede else None


class _Repasse(socketserver.BaseRequestHandler):
    destino: tuple[str, int]

    def handle(self) -> None:
        try:
            alvo = socket.create_connection(self.destino, timeout=5)
        except OSError:
            return
        alvo.settimeout(None)
        pares = {self.request: alvo, alvo: self.request}
        try:
            while True:
                prontos, _, erro = select.select(list(pares), [], list(pares), 60)
                if erro or not prontos:
                    break
                for s in prontos:
                    dados = s.recv(65536)
                    if not dados:
                        return
                    pares[s].sendall(dados)
        except OSError:
            pass
        finally:
            alvo.close()


class _ServidorTCP(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True


class ProxyRede:
    """Expõe na rede um servidor que só escuta em localhost (ex.: bun run dev em 127.0.0.1:5173)."""

    def __init__(self, porta_destino: int, porta: int | None = None, rede: bool = True) -> None:
        self.porta_destino = porta_destino
        self.rede = rede
        host = "0.0.0.0" if rede else "127.0.0.1"
        porta = porta_preferida(host) if porta is None else porta
        manipulador = type("Repasse", (_Repasse,), {"destino": ("127.0.0.1", porta_destino)})
        self._tcp = _ServidorTCP((host, porta), manipulador)
        self.porta = self._tcp.server_address[1]

    def iniciar(self) -> ProxyRede:
        threading.Thread(target=self._tcp.serve_forever, name="codar-proxy", daemon=True).start()
        return self

    def parar(self) -> None:
        self._tcp.shutdown()
        self._tcp.server_close()

    @property
    def url_rede(self) -> str:
        return f"http://{ip_local() if self.rede else '127.0.0.1'}:{self.porta}/"


def esperar_porta(porta: int, segundos: float = 5.0) -> bool:
    fim = time.monotonic() + segundos
    while time.monotonic() < fim:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", porta)) == 0:
                return True
        time.sleep(0.05)
    return False
