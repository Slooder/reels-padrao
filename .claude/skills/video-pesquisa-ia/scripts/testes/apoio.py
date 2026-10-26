# -*- coding: utf-8 -*-
"""Apoio comum das suítes do fatos.py: fatos de exemplo, relógio fixo e a base que roda o CLI em pasta com espaço.

Não é módulo de teste (o nome não começa por test_): os dois arquivos de teste importam daqui.
Todos os dados são fictícios (domínios .example, "Exemplo-1"): a suíte não registra especificação real de modelo.
"""
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

AQUI = Path(__file__).resolve().parent
SCRIPTS = AQUI.parent
SKILL = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))
sys.dont_write_bytecode = True
import fatos  # noqa: E402

FATOS_PY = SCRIPTS / "fatos.py"
HOJE = dt.date(2026, 10, 6)
KIT = SCRIPTS.parents[1] / "video-direcao-de-arte" / "kit"

# Relógio fixo: o que o fatos.py GRAVA leva a data real (--hoje e VIDEO_OPS_HOJE só simulam leitura); a suíte troca
# o relógio inteiro para ser determinística em qualquer dia.
os.environ["VIDEO_OPS_RELOGIO_TESTE"] = HOJE.isoformat()
os.environ.pop("VIDEO_OPS_HOJE", None)


def fonte(**k):
    base = {"titulo": "Attention Is All You Need", "url": "https://arxiv.org/abs/1706.03762", "editor": "arXiv",
            "tipo": "primaria", "publicado_em": "2017-06-12", "acessado_em": "2026-10-06",
            "trecho": "We propose a new simple network architecture, the Transformer"}
    base.update(k)
    return base


def fato(**k):
    base = {"afirmacao": "O artigo que apresentou a arquitetura Transformer foi publicado no arXiv em junho de 2017.",
            "valor": 2017, "unidade": None, "referente_a": "2017-06-12", "categoria": "historia",
            "status": "confirmado", "confianca": "alta", "caduca_em": None, "fontes": [fonte()],
            "como_dizer": "Em 2017, pesquisadores do Google publicaram o artigo que apresentou o Transformer.",
            "notas": ""}
    base.update(k)
    return base


def preco(**k):
    base = fato(afirmacao="A entrada do modelo Exemplo-1 custa US$ 1,25 por milhão de tokens na API.",
                valor=1.25, unidade="US$ por 1M de tokens de entrada", referente_a="outubro de 2026",
                categoria="preco", caduca_em="2026-11-05",
                fontes=[fonte(titulo="Pricing", url="https://exemplo.example/pricing", editor="Exemplo",
                              publicado_em=None, trecho="Input: $1.25 / 1M tokens")],
                como_dizer="Em outubro de 2026, a entrada do Exemplo-1 custava US$ 1,25 por milhão de tokens.",
                termos=["Exemplo-1"])
    base.update(k)
    return base


def mensagens(achados):
    return " | ".join(f"{a['campo']}: {a['mensagem']}" for a in achados)


def conferido(f, estado="encontrado", em=HOJE):
    """Cópia do fato com a conferência de trecho gravada em cada fonte (como `checar-links --trechos` deixa)."""
    f = json.loads(json.dumps(f))
    for s in f.get("fontes", []):
        s["conferencia"] = {"estado": estado, "em": em.isoformat(), "metodo": "checar-links", "http": 200,
                            "marca": fatos.marca_da_fonte(s)}
    return f


def checar_falso(estado="ok", http=200, trecho="encontrado"):
    """Substituto de fatos.checar_url para testes sem rede: toda URL responde `estado` e todo trecho sai `trecho`."""
    def checar(url, prazo, trechos=()):
        return {"url": url, "estado": estado, "http": http, "final": None, "detalhe": "",
                "trechos": {t: trecho for t in trechos}}
    return checar


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pesquisa ia çã "))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.proj = self.tmp / "Vídeo 1 — modelos de linguagem"
        (self.proj / "roteiro").mkdir(parents=True)
        self.env = dict(os.environ, VIDEO_OPS_HOME=str(self.tmp / "_ops"), VIDEO_OPS_RELOGIO_TESTE=HOJE.isoformat(),
                        PYTHONDONTWRITEBYTECODE="1")
        self.env.pop("VIDEO_OPS_DEBUG", None)
        self.env.pop("VIDEO_OPS_HOJE", None)

    def cli(self, *args, cwd=None, entrada=None, env=None):
        r = subprocess.run([sys.executable, "-B", str(FATOS_PY), *map(str, args)], cwd=str(cwd or self.proj),
                           input=entrada, capture_output=True, text=True, env=env or self.env, timeout=60)
        self.assertNotIn("Traceback", r.stderr, f"traceback cru em: {args}\n{r.stderr}")
        return r

    def nova(self):
        r = self.cli("novo", "--tema", "Como funciona um modelo de linguagem")
        self.assertEqual(r.returncode, 0, r.stderr)

    def grava_json(self, nome, dados):
        p = self.proj / nome
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
        return p

    def adiciona(self, dados, *extra):
        arq = self.grava_json("pesquisa/_novo fato.json", dados)
        return self.cli("adicionar", "@" + str(arq), *extra)

    def ficha(self):
        return json.loads((self.proj / "pesquisa" / "fatos.json").read_text(encoding="utf-8"))

    def confere_trechos(self, trecho="encontrado", estado="ok", http=200):
        """Faz na ficha o que `checar-links --trechos` faria com a rede respondendo `estado`/`trecho` (sem rede)."""
        f = self.ficha()
        rel = fatos.checar_links(f, com_trechos=True, checar=checar_falso(estado, http, trecho), sonda=lambda: True)
        cont = fatos.registrar_conferencias(f, rel, HOJE)
        self.grava_json("pesquisa/fatos.json", f)
        return cont


class ServidorLocal:
    """Mixin: sobe um servidor HTTP em 127.0.0.1 com três páginas — /pagina (HTML com um preço fictício),
    /documento.pdf (o robô não lê) e qualquer outra → 404. `self.base` é o endereço."""

    @classmethod
    def setUpClass(cls):
        import http.server
        import threading

        class Manipulador(http.server.BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                if self.path == "/pagina":
                    dados = ("<html><body><h1>Pricing</h1><table><tr><td>Exemplo-1</td><td>Input: <b>$1.25</b> / 1M "
                             "tokens</td></tr></table></body></html>").encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                elif self.path == "/documento.pdf":
                    dados = b"%PDF-1.4"
                    self.send_response(200)
                    self.send_header("Content-Type", "application/pdf")
                else:
                    dados = b""
                    self.send_response(404)
                self.send_header("Content-Length", str(len(dados)))
                self.end_headers()
                self.wfile.write(dados)

            def log_message(self, *a):
                pass

        cls.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Manipulador)
        cls.base = f"http://127.0.0.1:{cls.srv.server_address[1]}"
        cls.fio = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.fio.start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
