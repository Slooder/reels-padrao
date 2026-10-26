#!/usr/bin/env python3
"""Testes SEM REDE da video-pauta-midia: fábrica de .docx com comentários, yt-dlp de mentira e servidor HTTP local.

    /opt/homebrew/bin/python3 ~/.claude/skills/video-pauta-midia/testes/test_pauta_midia.py

Tudo acontece numa pasta temporária (com espaço e acento no nome), apagada no fim; nada é baixado da internet."""
from __future__ import annotations

import http.server
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

sys.dont_write_bytecode = True
SKILL = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL / "scripts"
sys.path.insert(0, str(SCRIPTS))
import base  # noqa: E402
import roteiro  # noqa: E402

NS = ('xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
      'xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml" xmlns:w15="http://schemas.microsoft.com/office/word/2012/wordml"')
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
YT = "https://www.youtube.com/watch?v=AAAAAAAAAAA"
FALSO = r'''import json, os, shutil, sys
a = sys.argv[1:]
with open(os.environ["FALSO_LOG"], "a") as f:
    f.write(" ".join(a) + "\n")
if "--version" in a:
    print("2026.07.04"); sys.exit(0)
modo = os.environ.get("FALSO_MODO", "ok")
if modo == "bot":
    sys.stderr.write("ERROR: [youtube] AAAAAAAAAAA: Sign in to confirm you're not a bot\n"); sys.exit(1)
if modo == "velho":
    sys.stderr.write("ERROR: [youtube] AAAAAAAAAAA: nsig extraction failed: Some formats may be missing\n"); sys.exit(1)
if "--dump-single-json" in a and "--flat-playlist" in a:
    print(json.dumps({"entries": [{"id": "AAAAAAAAAAA", "title": "Palestra de teste", "channel": "Canal Aberto", "duration": 300, "ie_key": "Youtube"}]})); sys.exit(0)
if "--dump-single-json" in a:
    print(json.dumps({"id": "AAAAAAAAAAA", "title": "Palestra de teste", "channel": "Canal Aberto", "channel_url": "https://www.youtube.com/@canalaberto",
                      "duration": 300, "webpage_url": "https://www.youtube.com/watch?v=AAAAAAAAAAA", "license": os.environ.get("FALSO_LICENCA") or None,
                      "upload_date": "20240102", "formats": [{"height": 360, "vcodec": "avc1"}, {"height": 2160, "vcodec": "vp9"}]})); sys.exit(0)
if "--download-sections" in a:
    shutil.copyfile(os.environ["FALSO_MP4"], a[a.index("-o") + 1].replace("%(ext)s", "mp4")); sys.exit(0)
sys.exit(2)
'''


def par(*pedacos: str, estilo: str | None = None) -> str:
    ppr = f'<w:pPr><w:pStyle w:val="{estilo}"/></w:pPr>' if estilo else ""
    return f"<w:p>{ppr}{''.join(pedacos)}</w:p>"


def t(texto: str) -> str:
    return f'<w:r><w:t xml:space="preserve">{escape(texto)}</w:t></w:r>'


def ini(i) -> str:
    return f'<w:commentRangeStart w:id="{i}"/>'


def fim(i) -> str:
    return f'<w:commentRangeEnd w:id="{i}"/><w:r><w:commentReference w:id="{i}"/></w:r>'


def _rels(mapa: dict) -> str:
    return (f'<?xml version="1.0"?><Relationships xmlns="{REL_NS}">'
            + "".join(f'<Relationship Id="{k}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" Target="{escape(v)}" TargetMode="External"/>' for k, v in mapa.items())
            + "</Relationships>")


def fabrica_docx(caminho: Path, corpo: str, comentarios=(), links=None, links_com=None, fios=()) -> Path:
    """comentarios: (id, autor, texto ou XML de runs, paraId) · fios: (paraId, paraId do pai ou None, resolvido)."""
    with zipfile.ZipFile(caminho, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
        z.writestr("word/document.xml", f'<?xml version="1.0" encoding="UTF-8"?><w:document {NS}><w:body>{corpo}</w:body></w:document>')
        if links:
            z.writestr("word/_rels/document.xml.rels", _rels(links))
        if comentarios:
            z.writestr("word/comments.xml", f'<?xml version="1.0" encoding="UTF-8"?><w:comments {NS}>' + "".join(
                f'<w:comment w:id="{i}" w:author="{escape(autor)}" w:date="2026-10-01T10:00:00Z"><w:p w14:paraId="{pid}">{x if x.startswith("<w:") else t(x)}</w:p></w:comment>'
                for i, autor, x, pid in comentarios) + "</w:comments>")
        if links_com:
            z.writestr("word/_rels/comments.xml.rels", _rels(links_com))
        if fios:
            z.writestr("word/commentsExtended.xml", f'<?xml version="1.0"?><w15:commentsEx {NS}>' + "".join(
                f'<w15:commentEx w15:paraId="{p}"' + (f' w15:paraIdParent="{pai}"' if pai else "") + f' w15:done="{int(feito)}"/>' for p, pai, feito in fios) + "</w15:commentsEx>")
    return caminho


class Servidor(http.server.BaseHTTPRequestHandler):
    rotas: dict = {}
    pedidos: list = []

    def do_GET(self):
        Servidor.pedidos.append(self.path)
        tipo, corpo = Servidor.rotas.get(self.path, ("text/plain", b"nada"))
        self.send_response(200 if self.path in Servidor.rotas else 404)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def log_message(self, *a):
        pass


class Caso(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="pauta mídia teste "))
        cls.env = {**os.environ, "VIDEO_OPS_HOME": str(cls.tmp / "home"), "PYTHONDONTWRITEBYTECODE": "1", "VIDEO_PAUTA_TESTE_LOCAL": "1",
                   "VIDEO_OPS_CONTATO": "teste@exemplo.invalid", "FALSO_LOG": str(cls.tmp / "ytdlp.log"), "FALSO_MP4": str(cls.tmp / "mini.mp4")}
        falso = cls.tmp / "yt-dlp-falso"
        falso.write_text(f"#!{sys.executable}\n{FALSO}", encoding="utf-8")
        falso.chmod(0o755)
        cls.env["VIDEO_PAUTA_YTDLP"] = str(falso)
        cls.com_da = cls.tmp / "projeto com DA"
        cls.sem_da = cls.tmp / "projeto sem DA"
        cls.com_da.mkdir()
        cls.sem_da.mkdir()
        kit = SKILL.parent / "video-direcao-de-arte" / "kit"
        r = subprocess.run([*(["sh"] if os.name == "nt" else []), str(kit / "bin" / "da"), "init", str(cls.com_da), "--nome", "Teste", "--base", "lab-ia"], env=cls.env, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        sys.path.insert(0, str(kit))
        import trava
        ffmpeg = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"
        r = trava.rodar([ffmpeg, "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=s=160x90:d=1:r=15", "-f", "lavfi", "-i", "sine=d=1", "-c:v", "libx264",
                         "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(cls.tmp / "mini.mp4")], rotulo="teste pauta: mini mp4", capturar=True, inatividade=60)
        assert r.codigo == 0, r.stderr
        from PIL import Image
        grande, pequena = io.BytesIO(), io.BytesIO()
        Image.new("RGB", (800, 600)).save(grande, "PNG")
        Image.new("RGB", (120, 90)).save(pequena, "PNG")
        Servidor.rotas = {"/foto.png": ("image/png", grande.getvalue()), "/mini.png": ("image/png", pequena.getvalue()),
                          "/pagina.jpg": ("text/html", b"<html>pagina</html>"), "/falsa.png": ("image/png", b"<html>nao e imagem</html>")}
        cls.http = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Servidor)
        threading.Thread(target=cls.http.serve_forever, daemon=True).start()
        cls.base_url = f"http://127.0.0.1:{cls.http.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown()
        cls.http.server_close()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def roda(self, script: str, *args, projeto: Path | None = None, **env):
        r = subprocess.run([sys.executable, str(SCRIPTS / script), *map(str, args)], cwd=projeto or self.com_da, env={**self.env, **env}, capture_output=True, text=True)
        return r.returncode, r.stdout, r.stderr

    def pauta(self, projeto: Path | None = None) -> dict:
        return json.loads(((projeto or self.com_da) / "roteiro" / "pauta.json").read_text(encoding="utf-8"))

    def registro(self) -> list:
        arq = self.com_da / "broll" / "licencas.json"
        return json.loads(arq.read_text(encoding="utf-8"))["itens"] if arq.is_file() else []

    # ── roteiro.py ──
    def test_01_docx_word_comentario_ancorado(self):
        doc = fabrica_docx(self.tmp / "word.docx", par(t("Abertura"), estilo="Ttulo1") + par(
            t("Em 1936, "), ini(0), t("Alan Turing descreveu uma máquina universal"), fim(0), t(". Ninguém ligou.")),
            comentarios=[(0, "Marina", "Colocar foto do Alan Turing jovem", "0A")])
        blocos, com = roteiro.ler_docx(doc)
        self.assertEqual([b["nivel"] for b in blocos], [1, 0])
        self.assertEqual(blocos[1]["texto"], "Em 1936, Alan Turing descreveu uma máquina universal. Ninguém ligou.")
        limpos, itens = roteiro.montar(blocos, com)
        self.assertEqual(len(itens), 1)
        it = itens[0]
        self.assertEqual((it["trecho"], it["paragrafo"], it["autor"], it["tipo"], it["skill"]),
                         ("Alan Turing descreveu uma máquina universal", 2, "Marina", "imagem_web", "video-pauta-midia"))
        self.assertEqual(it["consultas"], ["Alan Turing jovem"])
        self.assertEqual(roteiro.consulta_inicial("trecho de vídeo do YouTube: Big Buck Bunny, uns 6 segundos, de 0:30 a 0:36", "video_youtube", None), ["Big Buck Bunny"])
        self.assertEqual(roteiro.consulta_inicial("b-roll de data center", "banco", None), ["data center"])

    def test_02_docx_intervalo_em_dois_paragrafos_links_e_tempos(self):
        corpo = (par(t("Primeira frase. "), ini(1), t("A segunda começa aqui")) + par(t("e termina "), '<w:hyperlink r:id="rId9">' + t("neste link") + "</w:hyperlink>", fim(1), t(" depois."))
                 + par(ini(2), t("Outra fala."), fim(2)))
        doc = fabrica_docx(self.tmp / "dois.docx", corpo, links={"rId9": "https://exemplo.org/materia?a=1&b=2"}, links_com={"rId1": "https://youtu.be/AAAAAAAAAAA?t=83"},
                           comentarios=[(1, "Edu", "print da manchete", "0A"), (2, "Edu", '<w:hyperlink r:id="rId1">' + t("trecho da entrevista") + "</w:hyperlink>" + t(" de 1:23 a 1:40"), "0B")])
        _limpos, itens = roteiro.montar(*roteiro.ler_docx(doc))
        a, b = itens
        self.assertEqual((a["tipo"], a["url"], a["paragrafo"]), ("print", "https://exemplo.org/materia?a=1&b=2", 1))
        self.assertEqual(a["trecho"], "A segunda começa aqui e termina neste link")
        self.assertEqual((b["tipo"], b["url"], b["t0"], b["t1"], b["paragrafo"]), ("video_youtube", "https://youtu.be/AAAAAAAAAAA?t=83", 83.0, 100.0, 3))

    def test_03_docx_sugestoes_comentario_pontual_e_fio(self):
        corpo = (par(t("Texto "), "<w:ins>" + t("inserido") + "</w:ins>", '<w:del><w:r><w:delText>apagado</w:delText></w:r></w:del>', t(" final."), '<w:r><w:commentReference w:id="5"/></w:r>')
                 + par(ini(6), t("Segundo parágrafo."), fim(6)))
        doc = fabrica_docx(self.tmp / "gdocs.docx", corpo, comentarios=[(5, "Ana", "música mais calma aqui", "1A"), (6, "Ana", "gráfico de barras com os números", "1B"),
                                                                           (7, "Edu", "pode ser, mas só 5 segundos", "1C")], fios=[("1A", None, True), ("1B", None, False), ("1C", "1B", False)])
        blocos, com = roteiro.ler_docx(doc)
        self.assertEqual(blocos[0]["texto"], "Texto inserido final.")
        _limpos, itens = roteiro.montar(blocos, com)
        self.assertEqual([(i["tipo"], i["skill"]) for i in itens], [("musica", "video-mixagem"), ("animacao", "video-animacao-explicativa")])
        self.assertEqual(itens[0]["trecho"], "Texto inserido final.")
        self.assertIn("resolvido", itens[0]["notas"])
        self.assertIn("resposta de Edu: pode ser", itens[1]["notas"])

    def test_04_md_marcacoes_e_narracao_limpa(self):
        proj = self.tmp / "projeto md"
        proj.mkdir()
        (proj / "ep.md").write_text("# Episódio\n\nA primeira IA jogava damas. [IMAGEM: foto do Arthur Samuel no IBM 701] Ela aprendia sozinha [GC: Arthur Samuel, 1959].\n\n"
                                    "[VÍDEO: https://www.youtube.com/watch?v=AAAAAAAAAAA de 0:10 a 0:16]\n\nDepois veio o inverno [risos: não é marcação].\n\n[B-ROLL: sala de servidores]\n", encoding="utf-8")
        rc, out, err = self.roda("roteiro.py", "ler", "ep.md", "--projeto", proj, projeto=proj)
        self.assertEqual(rc, 0, err)
        md = (proj / "roteiro" / "roteiro.md").read_text(encoding="utf-8")
        self.assertEqual(md, "# Episódio\n\nA primeira IA jogava damas. Ela aprendia sozinha.\n\nDepois veio o inverno [risos: não é marcação].\n")
        p = self.pauta(proj)
        self.assertEqual((p["versao"], p["origem"]), (1, "ep.md"))
        self.assertEqual([(i["id"], i["tipo"], i["paragrafo"]) for i in p["itens"]],
                         [("P001", "imagem_web", 2), ("P002", "gc", 2), ("P003", "video_youtube", 2), ("P004", "banco", 3)])
        self.assertEqual(p["itens"][0]["trecho"], "A primeira IA jogava damas.")
        self.assertEqual((p["itens"][2]["t0"], p["itens"][2]["t1"], p["itens"][2]["trecho"]), (10.0, 16.0, "Ela aprendia sozinha."))
        self.assertEqual(set(p["itens"][0]), {"id", "trecho", "paragrafo", "pedido", "autor", "tipo", "skill", "url", "consultas", "t0", "t1", "status", "midia_ids", "notas"})

    def test_05_classificacao_por_regras(self):
        casos = [("print do site do G1 com a manchete", None, "print"), ("efeito sonoro de whoosh na entrada", None, "sfx"), ("legenda maior nessa parte", None, "legenda"),
                 ("GC com o nome dela", None, "gc"), ("animação explicando a rede neural", None, "animacao"), ("imagens de cobertura de fábrica", None, "banco"),
                 ("trecho da entrevista no Roda Viva", None, "video_youtube"), ("aqui", "https://youtu.be/AAAAAAAAAAA", "video_youtube"),
                 ("essa", "https://upload.wikimedia.org/wikipedia/commons/a/a1/X.jpg", "imagem_web"), ("cortar essa repetição", None, "corte"), ("rever o tom", None, "outro")]
        for pedido, url, esperado in casos:
            self.assertEqual(roteiro.classificar(pedido, url), esperado, pedido)
        self.assertEqual(roteiro.skill_do("corte", "corte vertical pro Reels"), "video-cortes-verticais")
        self.assertEqual(roteiro.skill_do("corte", "cortar essa repetição"), "video-montagem")
        self.assertEqual(base.segundos("1:02:03"), 3723.0)
        self.assertEqual(base.segundos("1m23s"), 83.0)

    def test_06_definir_listar_exportar_e_releitura(self):
        proj = self.tmp / "projeto pauta"
        proj.mkdir()
        (proj / "r.txt").write_text("Fala um. [VÍDEO: entrevista do Geoffrey Hinton]\n\nFala dois. [IMAGEM: foto de um perceptron]\n", encoding="utf-8")
        self.assertEqual(self.roda("roteiro.py", "ler", "r.txt", projeto=proj)[0], 0)
        rc, _o, err = self.roda("roteiro.py", "definir", "P001", "--url", YT, "--t0", "1:10", "--t1", "1:25", "--status", "aprovado", "--consulta", "hinton entrevista", projeto=proj)
        self.assertEqual(rc, 0, err)
        self.assertEqual(self.roda("roteiro.py", "definir", "P001", "--t1", "0:05", projeto=proj)[0], 64)       # t1 antes de t0
        self.assertEqual(self.roda("roteiro.py", "definir", "P001", "--status", "pronto", projeto=proj)[0], 64)   # status fora da lista
        self.assertEqual(self.roda("roteiro.py", "definir", "P009", "--status", "aprovado", projeto=proj)[0], 1)
        rc, out, _e = self.roda("roteiro.py", "listar", "--status", "aprovado", projeto=proj)
        self.assertIn("P001", out)
        self.assertNotIn("P002", out)
        self.assertEqual(self.roda("roteiro.py", "exportar", projeto=proj)[0], 0)
        md = (proj / "roteiro" / "pauta.md").read_text(encoding="utf-8")
        self.assertIn("**P001** · vídeo do YouTube · par. 1 · aprovado", md)
        self.assertIn("(1:10–1:25)", md)
        (proj / "r.txt").write_text("Fala um. [VÍDEO: entrevista do Geoffrey Hinton]\n\nFala nova. [GC: nome novo]\n", encoding="utf-8")
        self.assertEqual(self.roda("roteiro.py", "ler", "r.txt", projeto=proj)[0], 0)
        itens = {i["id"]: i for i in self.pauta(proj)["itens"]}
        self.assertEqual((itens["P001"]["status"], itens["P001"]["t0"]), ("aprovado", 70.0))                       # o decidido fica
        self.assertNotIn("P002", itens)                                                                             # pendente que saiu do documento some
        self.assertEqual(itens["P003"]["tipo"], "gc")                                                               # id nunca é reaproveitado

    # ── youtube.py ──
    def test_07_youtube_plano_e_recusas_sem_baixar(self):
        self.assertEqual(self.roda("youtube.py", "baixar", YT)[0], 64)                                              # sem trecho: nunca o vídeo inteiro
        self.assertEqual(self.roda("youtube.py", "baixar", YT, "--t0", "0", "--t1", "45", FALSO_LICENCA="Creative Commons Attribution license (reuse allowed)")[0], 1)   # teto de 30 s
        rc, _o, err = self.roda("youtube.py", "baixar", YT, "--t0", "10", "--t1", "16")                            # licença padrão sem base legal
        self.assertEqual(rc, 1)
        self.assertIn("licença padrão do YouTube", err)
        self.assertEqual(self.roda("youtube.py", "baixar", YT, "--t0", "10", "--t1", "16", "--base-legal", "citacao")[0], 64)   # citação sem nota
        self.assertEqual(self.roda("youtube.py", "baixar", YT, "--t0", "10", "--t1", "70", "--teto", "90", "--base-legal", "citacao", "--nota", "x")[0], 64)   # teto máximo da citação
        self.assertEqual(self.roda("youtube.py", "baixar", YT, "--t0", "10", "--t1", "16", projeto=self.sem_da)[0], 2)          # sem direção de arte
        rc, out, err = self.roda("youtube.py", "baixar", YT, "--t0", "10", "--t1", "16", FALSO_LICENCA="Creative Commons Attribution license (reuse allowed)")
        self.assertEqual(rc, 0, err)
        self.assertIn("PLANO — nada foi baixado", out)
        self.assertIn("CC BY 4.0", out)
        self.assertNotIn("--download-sections", Path(self.env["FALSO_LOG"]).read_text(encoding="utf-8"))
        self.assertEqual([i for i in self.registro() if i["fonte"] == "youtube"], [])

    def test_08_youtube_baixa_trecho_registra_e_fecha_a_pauta(self):
        (self.com_da / "r.md").write_text("Ele disse isso em público. [VÍDEO: trecho da palestra de teste]\n", encoding="utf-8")
        self.assertEqual(self.roda("roteiro.py", "ler", "r.md")[0], 0)
        rc, out, _e = self.roda("youtube.py", "buscar", "palestra de teste", "--pedido", "P001")
        self.assertEqual(rc, 0)
        self.assertIn("Canal Aberto", out)
        self.assertEqual(self.pauta()["itens"][0]["status"], "candidatos")
        args = ("youtube.py", "baixar", YT, "--t0", "10", "--t1", "16", "--base-legal", "citacao", "--nota", "fala comentada no vídeo", "--pedido", "P001", "--confirmar")
        rc, _o, err = self.roda(*args)                                                                              # candidato ainda não aprovado
        self.assertEqual(rc, 1)
        self.assertIn("ainda não foi aprovado", err)
        self.assertEqual(self.roda("roteiro.py", "definir", "P001", "--status", "aprovado")[0], 0)
        rc, out, err = self.roda(*args)
        self.assertEqual(rc, 0, err)
        y = [i for i in self.registro() if i["fonte"] == "youtube"]
        self.assertEqual(len(y), 1)
        y = y[0]
        self.assertEqual((y["id"], y["autor"], y["base_legal"], y["risco"], y["trecho"], y["arquivo"]),
                         ("Y001", "Canal Aberto", "citacao", "medio", {"t0": 10.0, "t1": 16.0}, "broll/bruto/Y001.mp4"))
        self.assertEqual(y["credito_tela"], "Reprodução: Canal Aberto / YouTube")
        self.assertTrue((self.com_da / y["arquivo"]).is_file())
        self.assertEqual([p.name for p in (self.com_da / "broll" / "bruto").glob("_entrando*")], [])
        it = self.pauta()["itens"][0]
        self.assertEqual((it["status"], it["midia_ids"], it["t0"], it["t1"]), ("baixado", ["Y001"], 10.0, 16.0))
        self.assertIn("Palestra de teste", (self.com_da / "broll" / "creditos.md").read_text(encoding="utf-8"))
        self.assertIn("nada a baixar", self.roda(*args)[1])                                                         # o mesmo trecho não baixa duas vezes

    def test_09_youtube_bloqueado_desatualizado_ou_ausente(self):
        rc, _o, err = self.roda("youtube.py", "info", YT, FALSO_MODO="bot")
        self.assertEqual(rc, 1)
        self.assertIn("bloqueou o pedido", err)
        self.assertIn("não usa os cookies", err)
        rc, _o, err = self.roda("youtube.py", "info", YT, FALSO_MODO="velho")
        self.assertEqual(rc, 1)
        self.assertIn("brew upgrade yt-dlp", err)
        self.assertIn("2026.07.04", err)
        rc, _o, err = self.roda("youtube.py", "info", YT, VIDEO_PAUTA_YTDLP=str(self.tmp / "não existe"))
        self.assertEqual(rc, 1)
        self.assertIn("brew install yt-dlp", err)
        self.assertEqual(self.roda("youtube.py", "info", "https://vimeo.com/123")[0], 64)

    # ── imagens.py ──
    def test_10_imagem_plano_download_conferencias_e_captura(self):
        pagina = "https://commons.wikimedia.org/wiki/File:Foto.png"
        comum = ("--pagina", pagina, "--autor", "Fulana de Tal", "--titulo", "Foto de teste")
        Servidor.pedidos.clear()
        rc, out, err = self.roda("imagens.py", "baixar", "--url", self.base_url + "/foto.png", *comum, "--licenca", "CC BY-SA 4.0")
        self.assertEqual(rc, 0, err)
        self.assertIn("PLANO — nada foi baixado", out)
        self.assertEqual(Servidor.pedidos, [])                                                                      # o plano não toca a rede
        self.assertEqual(self.roda("imagens.py", "baixar", "--url", self.base_url + "/foto.png", *comum)[0], 1)    # sem licença nem base legal
        rc, _o, err = self.roda("imagens.py", "baixar", "--url", self.base_url + "/foto.png", *comum, "--licenca", "CC BY-NC 4.0", "--confirmar")
        self.assertEqual(rc, 1)
        self.assertIn("recusada pela política", err)
        for rota, trecho in (("/pagina.jpg", "não entrega uma imagem"), ("/falsa.png", "não é uma imagem legível"), ("/mini.png", "pequena demais")):
            rc, _o, err = self.roda("imagens.py", "baixar", "--url", self.base_url + rota, *comum, "--licenca", "CC BY-SA 4.0", "--confirmar")
            self.assertEqual(rc, 1, rota)
            self.assertIn(trecho, err)
        self.assertEqual(self.roda("imagens.py", "baixar", "--url", self.base_url + "/foto.png", *comum, "--licenca", "CC BY-SA 4.0", "--teto-mb", "0.0001", "--confirmar")[0], 1)
        self.assertEqual([i for i in self.registro() if i["fonte"] == "web"], [])                                   # nenhuma recusa deixou registro
        rc, out, err = self.roda("imagens.py", "baixar", "--url", self.base_url + "/foto.png", *comum, "--licenca", "CC BY-SA 4.0", "--confirmar")
        self.assertEqual(rc, 0, err)
        w = [i for i in self.registro() if i["fonte"] == "web"][0]
        self.assertEqual((w["id"], w["tipo"], w["licenca"], w["largura"], w["altura"], w["arquivo"], w["pagina_url"]),
                         ("W001", "imagem", "CC BY-SA 4.0", 800, 600, "broll/bruto/W001.png", pagina))
        captura = self.tmp / "print de tela.png"
        shutil.copyfile(self.com_da / w["arquivo"], captura)
        rc, _o, err = self.roda("imagens.py", "baixar", "--arquivo", captura, "--pagina", "https://exemplo.org/noticia", "--autor", "Portal Exemplo", "--base-legal", "citacao", "--nota", "manchete comentada")
        self.assertEqual(rc, 0, err)
        w2 = [i for i in self.registro() if i["id"] == "W002"][0]
        self.assertEqual((w2["base_legal"], w2["credito_tela"]), ("citacao", "Reprodução: Portal Exemplo"))
        self.assertEqual([p.name for p in (self.com_da / "broll" / "bruto").glob("_entrando*")], [])
        self.assertIn("Fulana de Tal", (self.com_da / "broll" / "creditos.md").read_text(encoding="utf-8"))

    def test_11_docx_pela_linha_de_comando_e_arquivo_invalido(self):
        proj = self.tmp / "projeto docx"
        proj.mkdir()
        doc = fabrica_docx(proj / "Roteiro ep 1.docx", par(ini(0), t("Frase com pedido."), fim(0)) + par(t("Frase livre. [PRINT: site do jornal]")),
                           comentarios=[(0, "Marina", "[VÍDEO: https://youtu.be/AAAAAAAAAAA 0:05 a 0:11]", "0A")])
        rc, out, err = self.roda("roteiro.py", "ler", doc, projeto=proj)
        self.assertEqual(rc, 0, err)
        itens = self.pauta(proj)["itens"]
        self.assertEqual([(i["tipo"], i["autor"], i["t0"], i["t1"]) for i in itens], [("video_youtube", "Marina", 5.0, 11.0), ("print", None, None, None)])
        self.assertEqual((proj / "roteiro" / "roteiro.md").read_text(encoding="utf-8"), "Frase com pedido.\n\nFrase livre.\n")
        (proj / "falso.docx").write_text("isto não é um zip", encoding="utf-8")
        rc, _o, err = self.roda("roteiro.py", "ler", "falso.docx", projeto=proj)
        self.assertEqual(rc, 1)
        self.assertIn("não é um .docx legível", err)
        self.assertEqual(self.roda("roteiro.py", "ler", "roteiro.pages", projeto=proj)[0], 64)


if __name__ == "__main__":
    unittest.main(verbosity=2)
