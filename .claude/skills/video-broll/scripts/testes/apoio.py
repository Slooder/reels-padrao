"""apoio.py — o que as suítes dividem: pasta temporária com espaço e acento, respostas simuladas dos provedores,
servidor HTTP local com Range (para o download) e projeto de teste com DA."""
from __future__ import annotations

import copy
import io
import json
import os
import shutil
import sys
import tempfile
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.dont_write_bytecode = True
SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
DADOS = Path(__file__).resolve().parent / "_dados"

import comum  # noqa: E402


def dado(nome: str):
    return json.loads((DADOS / f"{nome}.json").read_text(encoding="utf-8"))


# Contato FICTÍCIO, só para os testes que simulam a Wikimedia (ela é pulada sem contato). Ele não pode sair da máquina —
# a política da Wikimedia exige contato de verdade e mandar um inventado é pior que não mandar nenhum. Por isso há uma
# guarda logo abaixo: com este valor no ambiente, comum.Http só fala com 127.0.0.1 (o servidor da suíte); qualquer outro
# destino derruba o teste antes de abrir a conexão. Teste que fala com a internet (test_rede) nunca o define.
CONTATO_DE_TESTE = "https://exemplo.invalid/contato-de-teste"
# A identificação de quem está rodando a suíte, lida antes de qualquer teste mexer no ambiente (só test_rede a usa).
IDENTIFICACAO_DE_QUEM_RODA = {k: (os.environ.get(k) or "").strip() for k in ("VIDEO_OPS_CONTATO", "VIDEO_OPS_AGENTE")}

_abrir_de_verdade = comum.Http.abrir


def _abrir_vigiado(self, url, hosts, *args, **kw):
    host = (urllib.parse.urlsplit(str(url)).hostname or "").lower()
    if os.environ.get("VIDEO_OPS_CONTATO") == CONTATO_DE_TESTE and host not in ("127.0.0.1", "localhost", "::1") and comum.host_permitido(url, hosts):
        raise AssertionError(f"teste com contato fictício tentou falar com a internet ({host}): use HttpFalso, o servidor local ou pasta_temporaria(contato=False)")
    return _abrir_de_verdade(self, url, hosts, *args, **kw)


comum.Http.abrir = _abrir_vigiado


def pasta_temporaria(teste, contato: bool = False) -> Path:
    """Pasta com ESPAÇO e ACENTO no nome, apagada no fim do teste; VIDEO_OPS_HOME aponta para dentro dela e o ambiente
    fica como o de quem ainda não configurou nada (sem chaves, sem contato, sem modelo de agente).
    `contato=True` define o VIDEO_OPS_CONTATO fictício — só para teste com HTTP simulado ou servidor em 127.0.0.1 (sem ele a
    Wikimedia é pulada); a guarda acima impede que ele saia da máquina."""
    p = Path(tempfile.mkdtemp(prefix="broll teste ção "))
    teste.addCleanup(shutil.rmtree, p, True)
    antigos = {k: os.environ.get(k) for k in ("VIDEO_OPS_HOME", "PEXELS_API_KEY", "PIXABAY_API_KEY", "VIDEO_OPS_CONTATO", "VIDEO_OPS_AGENTE", "VIDEO_BROLL_PERMITIR_LOCAL")}

    def restaurar():
        for k, v in antigos.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    teste.addCleanup(restaurar)
    os.environ["VIDEO_OPS_HOME"] = str(p / "config do usuário")
    for k in ("PEXELS_API_KEY", "PIXABAY_API_KEY", "VIDEO_OPS_CONTATO", "VIDEO_OPS_AGENTE"):
        os.environ.pop(k, None)
    if contato:
        os.environ["VIDEO_OPS_CONTATO"] = CONTATO_DE_TESTE
    return p


class HttpFalso:
    """No lugar de comum.Http: devolve a resposta simulada da primeira regra cujo trecho aparece na URL."""

    def __init__(self, regras=None):
        self.regras = list(regras if regras is not None else REGRAS)
        self.pedidos = 0
        self.limites = {}
        self.chamadas = []

    def json(self, url, hosts, cabecalhos=None, intervalo=1.0, teto=0):
        self.pedidos += 1
        self.chamadas.append((url, dict(cabecalhos or {})))
        for trecho, resposta in self.regras:
            if trecho in url:
                if isinstance(resposta, Exception):
                    raise resposta
                return copy.deepcopy(resposta)
        raise comum.Erro(f"sem resposta simulada para {url}")

    def bytes(self, url, hosts, intervalo=0.3, teto=0):
        from PIL import Image
        self.pedidos += 1
        self.chamadas.append((url, {}))
        b = io.BytesIO()
        Image.new("L", (160, 90), 128).save(b, "PNG")
        return b.getvalue()


def regras():
    return [
        ("images-api.nasa.gov/asset/", dado("nasa_asset")),
        ("metadata.json", dado("nasa_metadata")),
        ("media_type=image", dado("nasa_busca_imagem")),
        ("images-api.nasa.gov/search", dado("nasa_busca")),
        ("filetype%3Avideo", dado("commons_video")),
        ("filetype%3Abitmap", dado("commons_imagem")),
        ("archive.org/advancedsearch.php", dado("archive_busca")),
        ("archive.org/metadata/", dado("archive_metadata")),
        ("api.openverse.org/v1/images/", dado("openverse_busca")),
        ("api.pexels.com/v1/videos/search", dado("pexels_videos")),
        ("api.pexels.com/v1/search", dado("pexels_fotos")),
        ("pixabay.com/api/videos/", dado("pixabay_videos")),
        ("pixabay.com/api/", dado("pixabay_imagens")),
    ]


REGRAS = regras()


class _Manipulador(BaseHTTPRequestHandler):
    """Serve os arquivos de servidor.arquivos {caminho: bytes} com suporte a Range; anota cada pedido.
    Maus comportamentos sob encomenda (para os testes de segurança):
      servidor.redirecionar {caminho: (métodos, destino)}  → 302 para `destino` nos métodos dados ("GET", "HEAD")
      servidor.anunciar     {caminho: n}                    → o HEAD diz que o arquivo tem n bytes (o GET manda o de verdade)
      servidor.sem_tamanho  {caminho, …}                    → o GET não informa Content-Length nem aceita Range"""

    def log_message(self, *a):
        pass

    def _responder(self, corpo_tambem: bool):
        srv = self.server
        caminho = urllib.parse.unquote(self.path.split("?")[0])
        srv.pedidos.append((self.command, caminho, self.headers.get("Range"), self.headers.get("User-Agent")))
        metodos, destino = srv.redirecionar.get(caminho, ((), None))
        if self.command in metodos:
            self.send_response(302)
            self.send_header("Location", destino)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        dados = srv.arquivos.get(caminho)
        if dados is None:
            self.send_error(404)
            return
        if not corpo_tambem and caminho in srv.anunciar:
            self.send_response(200)
            self.send_header("Content-Type", srv.tipos.get(caminho, "video/mp4"))
            self.send_header("Content-Length", str(srv.anunciar[caminho]))
            self.end_headers()
            return
        if corpo_tambem and caminho in srv.sem_tamanho:
            self.send_response(200)
            self.send_header("Content-Type", srv.tipos.get(caminho, "video/mp4"))
            self.end_headers()
            try:
                self.wfile.write(dados)
            except (BrokenPipeError, ConnectionResetError):
                pass
            return
        total = len(dados)
        faixa = self.headers.get("Range")
        inicio, fim = 0, total - 1
        if faixa and srv.aceita_range:
            a, _, b = faixa.removeprefix("bytes=").partition("-")
            inicio = int(a) if a else 0
            fim = int(b) if b else total - 1
            if inicio >= total:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{total}")
                self.end_headers()
                return
            fim = min(fim, total - 1)
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {inicio}-{fim}/{total}")
        else:
            self.send_response(200)
        self.send_header("Content-Type", srv.tipos.get(caminho, "video/mp4"))
        self.send_header("Content-Length", str(fim - inicio + 1))
        if srv.aceita_range:
            self.send_header("Accept-Ranges", "bytes")
        self.end_headers()
        if corpo_tambem:
            try:
                self.wfile.write(dados[inicio:fim + 1])
            except (BrokenPipeError, ConnectionResetError):
                pass

    def do_GET(self):
        self._responder(True)

    def do_HEAD(self):
        self._responder(False)


def servidor(teste, arquivos: dict, aceita_range: bool = True, tipos: dict | None = None):
    """Sobe um servidor em 127.0.0.1 (porta livre), só durante o teste. Devolve (url_base, servidor)."""
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Manipulador)
    srv.arquivos, srv.aceita_range, srv.tipos, srv.pedidos = dict(arquivos), aceita_range, dict(tipos or {}), []
    srv.redirecionar, srv.anunciar, srv.sem_tamanho = {}, {}, set()
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()

    def parar():
        srv.shutdown()
        srv.server_close()
    teste.addCleanup(parar)
    os.environ["VIDEO_BROLL_PERMITIR_LOCAL"] = "1"
    return f"http://127.0.0.1:{srv.server_address[1]}", srv


def projeto(pasta: Path, nome: str = "Vídeo de teste", base: str = "lab-ia"):
    """Projeto com DA (preset do kit) dentro de `pasta`. Devolve (raiz, d)."""
    da, _texto, _video, _trava = comum.importar_kit()
    raiz = pasta / nome
    da.iniciar(raiz, nome, base)
    return raiz, da.carregar(raiz)


_VIDEO = {}


def video_sintetico(largura: int = 320, altura: int = 180, dur: float = 2.0, com_audio: bool = True) -> bytes:
    """Vídeo de teste minúsculo (barras coloridas em movimento + tom), gerado pelo ffmpeg do kit sob a trava; em cache."""
    chave = (largura, altura, dur, com_audio)
    if chave not in _VIDEO:
        _da, _texto, video, _trava = comum.importar_kit()
        with tempfile.TemporaryDirectory(prefix="broll sintético ") as tmp:
            saida = Path(tmp) / "fonte.mp4"
            args = ["-f", "lavfi", "-i", f"testsrc2=size={largura}x{altura}:rate=30:duration={dur}"]
            if com_audio:
                args += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={dur}"]
            video.executar([*args, *video.args_encode(30, crf=30, audio=com_audio), "-g", "15"], saida, rotulo="vídeo sintético de teste")
            _VIDEO[chave] = saida.read_bytes()
    return _VIDEO[chave]
