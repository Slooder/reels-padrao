#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Testes de ponta a ponta do motor de render (motor/render.mjs + da_ext_motor.py + texto.py + video.py).

Rodar a partir do kit:  python3 -m unittest testes.test_motor -v
Tudo acontece numa pasta temporária com espaço e acento no nome e VIDEO_OPS_HOME isolado. Os renders são
minúsculos (≤ 2 s, ≤ 960×540) e passam pela trava global de verdade: se outro agente estiver com um render
longo, a suíte espera em vez de falhar.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KIT))
import da  # noqa: E402
import da_ext_motor as motor  # noqa: E402
import texto  # noqa: E402
import video  # noqa: E402

PY = sys.executable
RENDER = KIT / "motor" / "render.mjs"
FFMPEG = da._bin("ffmpeg")


def rodar(cmd, cwd=None, env=None):
    return subprocess.run([str(c) for c in cmd], cwd=str(cwd) if cwd else None, capture_output=True, text=True,
                          env={**os.environ, **(env or {})})


def quadro_rgba(arquivo, t=0.3):
    """Decodifica um quadro em RGBA (preservando alfa de WebM/ProRes) e devolve a imagem PIL."""
    from PIL import Image
    arquivo = Path(arquivo)
    saida = arquivo.with_name(arquivo.stem + "_q.png")
    extra = ["-c:v", "libvpx-vp9"] if arquivo.suffix == ".webm" else []
    r = subprocess.run([FFMPEG, "-v", "error", "-y", *extra, "-i", str(arquivo), "-ss", str(t), "-frames:v", "1", "-update", "1",
                        "-pix_fmt", "rgba", str(saida)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return Image.open(saida).convert("RGBA")


class TestMotor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = Path(tempfile.mkdtemp(prefix="da motor é ")).resolve()
        cls.home = cls.base / "video ops home"
        cls.home.mkdir()
        os.environ["VIDEO_OPS_HOME"] = str(cls.home)
        os.environ.pop("DA_JSON", None)
        cls.node = motor.achar_node()
        cls.projetos = {}
        for preset in ("dossie", "neon-shorts"):
            pasta = cls.base / f"projeto {preset} ção"
            info = da.iniciar(pasta, nome=f"Teste {preset}", base=preset)
            assert info["criou_da"], info
            cls.projetos[preset] = pasta
        cls.proj = cls.projetos["dossie"]
        cls.d = da.carregar(cls.proj)
        cls.tempos = {}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.base, ignore_errors=True)
        if cls.tempos:
            print("\nTempos medidos (s):", json.dumps(cls.tempos, ensure_ascii=False))

    # -- helpers --------------------------------------------------------------
    def render(self, *args, cwd=None, esperado=0):
        import time
        t0 = time.monotonic()
        r = rodar([self.node, RENDER, *args], cwd=cwd or self.proj)
        self.__class__.tempos[" ".join(str(a) for a in args[:4])] = round(time.monotonic() - t0, 1)
        if r.returncode != esperado:
            self.fail(f"render devolveu {r.returncode} (esperava {esperado})\nSTDOUT:\n{r.stdout}\nSTDERR:\n{r.stderr}")
        return r

    def probe(self, arquivo):
        extra = ["-c:v", "libvpx-vp9"] if str(arquivo).endswith(".webm") else []
        r = subprocess.run([da._bin("ffprobe"), "-v", "error", *extra, "-select_streams", "v:0", "-count_frames", "-show_entries",
                            "stream=codec_name,width,height,pix_fmt,r_frame_rate,nb_read_frames", "-of", "json", str(arquivo)],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)["streams"][0]

    def cena_de_teste(self, nome, css_extra="", atributo=""):
        """Cena mínima: um bloco com texto no papel titulo + um elemento com estilo arbitrário (para o auditor)."""
        arq = self.proj / "animacoes" / f"{nome}.js"
        arq.write_text(f"""
export const meta = {{ nome: '{nome}', dur_padrao: 1, params: {{}} }};
const S = {{}};
export function build(palco, p, ctx) {{
  const t = ctx.texto('titulo', 'Olá, ação', {{ tam: ctx.tam('h1') }});
  palco.appendChild(t); ctx.medir(t);
  const caixa = ctx.el('div', 'caixa', 'Bloco de teste');
  ctx.estilo(caixa, 'corpo', {{ tam: ctx.tam('corpo') }});
  caixa.style.cssText = 'position:absolute;left:100px;top:300px;padding:20px;' + {json.dumps(css_extra)};
  {('caixa.setAttribute("data-da-livre", "teste");' if atributo else '')}
  palco.appendChild(caixa);
  S.t = t;
}}
export function seek(t) {{ S.t.style.opacity = t < 0.5 ? '1' : '0.5'; }}
""", encoding="utf-8")
        return arq

    # -- 1. prancha -----------------------------------------------------------
    def test_01_prancha_dois_presets(self):
        import time
        from PIL import Image, ImageStat
        medias = {}
        for preset, pasta in self.projetos.items():
            t0 = time.monotonic()
            r = rodar([PY, KIT / "da.py", "prancha", "--escala", "0.5", "--da", pasta])
            self.__class__.tempos[f"prancha {preset} (ambas, escala 0.5)"] = round(time.monotonic() - t0, 1)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            h, v = pasta / "da" / "prancha.png", pasta / "da" / "prancha_vertical.png"
            self.assertTrue(h.is_file() and v.is_file(), r.stdout + r.stderr)
            with Image.open(h) as im:
                self.assertEqual(im.width, 960)                       # 1920 × escala 0,5
                self.assertGreater(im.height, 1500)
                medias[preset] = tuple(ImageStat.Stat(im.convert("RGB")).mean)
            with Image.open(v) as im:
                self.assertEqual(im.width, 540)
                self.assertGreater(im.height, 2000)
            self.assertTrue((h.parent / "prancha.png.da.json").is_file(), "prancha sem carimbo")
            self.assertTrue((pasta / "da" / "build" / "prancha" / "depois.png").is_file())
        a, b = self.projetos["dossie"] / "da" / "prancha.png", self.projetos["neon-shorts"] / "da" / "prancha.png"
        self.assertNotEqual(a.read_bytes(), b.read_bytes(), "pranchas de presets diferentes saíram iguais")
        from PIL import ImageChops
        with Image.open(a) as ia, Image.open(b) as ib:
            h = min(ia.height, ib.height)
            dif = ImageChops.difference(ia.convert("RGB").crop((0, 0, 960, h)), ib.convert("RGB").crop((0, 0, 960, h)))
            self.assertGreater(ImageStat.Stat(dif).mean[0] + ImageStat.Stat(dif).mean[1] + ImageStat.Stat(dif).mean[2], 20,
                               "as pranchas deveriam diferir claramente (paleta e tipografia próprias)")

    # -- 2. vídeo h264 --------------------------------------------------------
    def test_02_render_titulo_h264_escala(self):
        saida = self.proj / "animacoes" / "título teste.mp4"
        self.render("--cena", "titulo", "--saida", saida, "--dur", "1", "--escala", "0.5",
                    "--params", '{"titulo": "A conta que não fecha", "sobretitulo": "Capítulo 2"}')
        s = self.probe(saida)
        self.assertEqual((s["width"], s["height"]), (960, 540))
        self.assertEqual(s["codec_name"], "h264")
        self.assertEqual(s["pix_fmt"], "yuv420p")
        self.assertEqual(s["r_frame_rate"], "30000/1001")
        self.assertEqual(int(s["nb_read_frames"]), 30)
        carimbo = json.loads((self.proj / "animacoes" / "título teste.mp4.da.json").read_text())
        self.assertEqual(carimbo["auditoria"], "ok")
        self.assertEqual(carimbo["ferramenta"], "motor")
        self.assertEqual(carimbo["da_sha256"], self.d.sha256)
        self.assertEqual(carimbo["parametros"]["quadros"], 30)
        r = rodar([PY, KIT / "da.py", "conferir-carimbo", saida, "--da", self.proj])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("ok", r.stdout)

    # -- 3. alfa ----------------------------------------------------------------
    def test_03_alfa_prores4444(self):
        saida = self.proj / "animacoes" / "gc alfa.mov"
        self.render("--cena", "gc", "--saida", saida, "--dur", "1", "--formato", "960x540", "--codec", "prores4444",
                    "--params", '{"nome": "Mariana Albuquerque", "cargo": "Procuradora"}')
        s = self.probe(saida)
        self.assertEqual(s["codec_name"], "prores")
        self.assertRegex(s["pix_fmt"], r"^yuva444p1[02]le$")
        self.assertEqual(int(s["nb_read_frames"]), 30)
        im = quadro_rgba(saida, 0.45)                          # entrada concluída, saída ainda não começou
        alfa = im.getchannel("A")
        self.assertEqual(alfa.getpixel((5, 5)), 0, "canto superior esquerdo deveria ser transparente")
        self.assertEqual(alfa.getextrema()[1], 255, "o GC deveria ter pixels opacos")

    def test_04_alfa_vp9(self):
        saida = self.proj / "animacoes" / "moldura alfa.webm"
        self.render("--cena", "moldura", "--saida", saida, "--dur", "1", "--formato", "960x540", "--codec", "vp9alfa",
                    "--params", '{"rotulo": "Arquivo · 2018"}')
        s = self.probe(saida)
        self.assertEqual(s["codec_name"], "vp9")
        self.assertEqual(s["pix_fmt"], "yuva420p")
        im = quadro_rgba(saida, 0.45)
        alfa = im.getchannel("A")
        self.assertLess(alfa.getpixel((480, 270)), 8, "o centro da moldura (janela) deveria ser transparente")
        self.assertGreater(alfa.getextrema()[1], 200)
        info = video.sondar(saida)
        self.assertTrue(info["tem_alfa"])
        self.assertTrue(info["tem_alfa"] and info["pix_fmt"] == "yuva420p")

    # -- 5. auditor -------------------------------------------------------------
    def test_05_auditor_reprova_cor_literal(self):
        cena = self.cena_de_teste("cor_ruim", "background:#ff0000;color:rgb(1,2,3)")
        saida = self.proj / "animacoes" / "cor ruim.png"
        r = self.render("--cena", cena, "--saida", saida, "--quadro", "0.2", "--escala", "0.25", esperado=1)
        self.assertIn("AUDITORIA REPROVADA", r.stderr)
        self.assertIn("cor fora da DA", r.stderr)
        self.assertIn("background-color", r.stderr)
        self.assertFalse(saida.exists(), "a peça reprovada não deveria ser gravada")
        self.assertFalse((self.proj / "animacoes" / "cor ruim.png.da.json").exists())

    def test_06_auditor_reprova_fonte(self):
        cena = self.cena_de_teste("fonte_ruim", "font-family:Georgia, serif")
        saida = self.proj / "animacoes" / "fonte ruim.png"
        r = self.render("--cena", cena, "--saida", saida, "--quadro", "0.2", "--escala", "0.25", esperado=1)
        self.assertIn("font-family", r.stderr)
        self.assertIn("fonte fora da DA", r.stderr)

    def test_07_auditor_aprova_data_da_livre(self):
        cena = self.cena_de_teste("livre", "background:#ff0000;font-family:Georgia", atributo="data-da-livre")
        saida = self.proj / "animacoes" / "livre.png"
        self.render("--cena", cena, "--saida", saida, "--quadro", "0.2", "--escala", "0.25")
        self.assertTrue(saida.is_file())
        from PIL import Image
        with Image.open(saida) as im:
            self.assertEqual(im.size, (480, 270))
        carimbo = json.loads((self.proj / "animacoes" / "livre.png.da.json").read_text())
        self.assertEqual(carimbo["auditoria"], "ok")

    def test_08_sem_auditoria_fica_no_carimbo(self):
        cena = self.cena_de_teste("pulada", "background:#ff0000")
        saida = self.proj / "animacoes" / "pulada.png"
        r = self.render("--cena", cena, "--saida", saida, "--quadro", "0.2", "--escala", "0.25", "--sem-auditoria")
        self.assertIn("AUDITORIA PULADA", r.stderr)
        carimbo = json.loads((self.proj / "animacoes" / "pulada.png.da.json").read_text())
        self.assertEqual(carimbo["auditoria"], "pulada")
        r = rodar([PY, KIT / "da.py", "conferir-carimbo", saida, "--da", self.proj])
        self.assertEqual(r.returncode, 1)
        self.assertIn("AUDITORIA PULADA", r.stdout)

    def test_09_auditor_reprova_transition(self):
        cena = self.cena_de_teste("transicao", "transition: opacity 0.3s")
        saida = self.proj / "animacoes" / "transicao.png"
        r = self.render("--cena", cena, "--saida", saida, "--quadro", "0.2", "--escala", "0.25", esperado=1)
        self.assertIn("transition", r.stderr)

    # -- 10. lock velho recompila --------------------------------------------------
    def test_10_lock_velho_recompila(self):
        lock_arq = self.proj / "da" / "build" / "da.lock"
        antes = json.loads(lock_arq.read_text())
        dados = da.ler_json(self.proj / "da" / "da.json")
        dados["conceito"]["frase"] = "Frase alterada para forçar a recompilação."
        da.gravar_json(self.proj / "da" / "da.json", dados)
        self.assertTrue(da.precisa_compilar(self.proj / "da" / "da.json")[0])
        saida = self.proj / "animacoes" / "recompila.png"
        r = self.render("--cena", "titulo", "--saida", saida, "--quadro", "1", "--escala", "0.25", "--params", '{"titulo": "Recompila"}')
        self.assertIn("build recompilado", r.stderr)
        depois = json.loads(lock_arq.read_text())
        self.assertNotEqual(antes["arquivos"][0]["sha256"], depois["arquivos"][0]["sha256"])
        self.assertFalse(da.precisa_compilar(self.proj / "da" / "da.json")[0])
        carimbo = json.loads((self.proj / "animacoes" / "recompila.png.da.json").read_text())
        self.assertEqual(carimbo["da_sha256"], depois["sha256"])
        self.__class__.d = da.carregar(self.proj)

    # -- 11. teste de movimento, fila e erros de uso -----------------------------------
    def test_11_teste_movimento(self):
        import time
        t0 = time.monotonic()
        # um ato só (o do GC com legenda): ≈ 2 s de vídeo. A duração sai das durações da DA, não de um número fixo (D21)
        r = rodar([PY, KIT / "da.py", "teste-movimento", "--escala", "0.25", "--atos", "gc", "--da", self.proj])
        self.__class__.tempos["teste-movimento, ato do GC a 480x270"] = round(time.monotonic() - t0, 1)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        saida = self.proj / "da" / "teste_movimento.mp4"
        s = self.probe(saida)
        self.assertEqual((s["width"], s["height"]), (480, 270))
        carimbo = json.loads((saida.parent / "teste_movimento.mp4.da.json").read_text())
        lay = carimbo["parametros"]["layout"]
        self.assertEqual(lay["atos"], ["gc"])
        self.assertLess(lay["total"], 3.0)
        self.assertEqual(int(s["nb_read_frames"]), round(lay["total"] * 30000 / 1001))
        self.assertGreaterEqual(lay["janelas"]["gc"]["cena"], lay["gc"]["fim_entrada"], "a entrada do GC tem de caber inteira no ato")
        # o GC entra e a legenda corre: o começo e o meio do ato não podem ser iguais
        a, b = quadro_rgba(saida, 0.05).convert("RGB"), quadro_rgba(saida, lay["total"] * 0.6).convert("RGB")
        self.assertNotEqual(a.tobytes(), b.tobytes())

    def test_12_fila_continua_apos_falha(self):
        fila = self.proj / "animacoes" / "fila.json"
        ruim = self.cena_de_teste("fila_ruim", "color:#123456")
        fila.write_text(json.dumps([
            {"cena": str(ruim), "saida": "fila ruim.png", "quadro": 0.1, "escala": 0.25},
            {"cena": "citacao", "saida": "fila boa.png", "quadro": 2, "escala": 0.25, "params": {"texto": "Frase curta.", "autor": "Alguém"}},
            {"cena": "barras", "saida": "fila barras.png", "quadro": 3, "escala": 0.25, "formato": "vertical",
             "params": {"titulo": "Teste", "dados": [{"rotulo": "A", "valor": 1}, {"rotulo": "B", "valor": 2}]}},
        ], ensure_ascii=False), encoding="utf-8")
        r = self.render("--fila", fila, esperado=1)
        self.assertIn("RESUMO: 2 ok, 1 falha(s)", r.stderr)
        self.assertTrue((self.proj / "animacoes" / "fila boa.png").is_file())
        self.assertTrue((self.proj / "animacoes" / "fila barras.png").is_file())
        self.assertFalse((self.proj / "animacoes" / "fila ruim.png").exists())

    def test_13_erros_de_uso(self):
        r = self.render("--cena", "titulo", "--saida", self.proj / "animacoes" / "x.png", "--quadro", "0", "--params", '{"titulo": "x", "inexistente": 1}', esperado=64)
        self.assertIn("inexistente", r.stderr)
        r = self.render("--cena", "titulo", "--saida", self.proj / "animacoes" / "x.png", "--quadro", "0", esperado=64)
        self.assertIn("obrigatório", r.stderr)
        r = self.render("--cena", "gc", "--saida", self.proj / "animacoes" / "x.mp4", "--dur", "0.2", "--params", '{"nome": "x"}', "--codec", "h264", esperado=64)
        self.assertIn("alfa", r.stderr)
        r = rodar([self.node, RENDER, "--cena", "titulo", "--saida", "x.png", "--quadro", "0", "--params", '{"titulo": "x"}'], cwd=self.base)
        self.assertEqual(r.returncode, 2, r.stderr)                     # C1: sem DA, código 2
        self.assertIn("video-direcao-de-arte", r.stderr)
        # `da.py render --cena …` sem `--`: as opções do motor são repassadas (regressão: argparse mandava --cena para "extras")
        r = rodar([PY, KIT / "da.py", "render", "--cena", "titulo", "--saida", "repasse.png", "--quadro", "0.5", "--formato", "320x180",
                   "--params", '{"titulo": "Repasse"}'], cwd=self.proj / "animacoes")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.proj / "animacoes" / "repasse.png").is_file())
        r = rodar([PY, KIT / "da.py", "render", "--cena", "titulo", "--saida", "x.png", "--quadro", "0", "--params", '{"titulo": "x", "inexistente": 1}'], cwd=self.proj)
        self.assertEqual(r.returncode, 64, r.stderr)                    # erro de uso do motor atravessa o da.py
        self.assertIn("inexistente", r.stderr)
        r = rodar([PY, KIT / "da.py", "validar", "--xyz"], cwd=self.proj)
        self.assertEqual(r.returncode, 64)                              # subcomando comum continua estrito com opção desconhecida
        self.assertIn("não reconhecidos", r.stderr)
        # fila: `cena` com caminho é relativa à pasta do fila.json (como `saida`)
        fila = self.proj / "animacoes" / "fila rel.json"
        self.cena_de_teste("rel_ok", "")
        fila.write_text(json.dumps([{"cena": "rel_ok.js", "saida": "rel ok.png", "quadro": 0.1, "escala": 0.25}]), encoding="utf-8")
        r = self.render("--fila", fila)
        self.assertTrue((self.proj / "animacoes" / "rel ok.png").is_file(), r.stderr)

    # -- 14. texto.py e video.py -----------------------------------------------------
    def test_14_texto_pil(self):
        est = texto.Estilo.legenda(self.d, 1920, 1080)
        img, info = texto.desenhar("A conta que não fecha de jeito nenhum", est, largura_max=700, max_linhas=2)
        self.assertEqual(img.mode, "RGBA")
        self.assertLessEqual(len(info["linhas"]), 2)
        self.assertLessEqual(img.width, 700 + 40)
        self.assertNotEqual(info["linhas"][-1].count(" "), 0, "última linha não pode ter palavra órfã")
        destaque = texto.Estilo.legenda(self.d, 1920, 1080, destaque=True)
        quadro, inf = texto.desenhar_linha(["A", "conta", "que", "não"], [est, destaque, est, est], self.d, 1920, 1080)
        self.assertEqual(quadro.size, (1920, 1080))
        self.assertEqual(len(inf["palavras"]), 4)
        self.assertLess(inf["palavras"][0]["x0"], inf["palavras"][1]["x0"])
        linhas = texto.quebrar_linhas("um dois três quatro cinco", est, 100000)
        self.assertEqual(linhas, ["um dois três quatro cinco"])

    def test_15_video_helpers(self):
        rec = video.filtro_recorte((1920, 1080), (1080, 1920), "rosto")
        self.assertIn("crop=1080:1920", rec["filtro"])
        self.assertEqual(rec["escala"][0] % 2, 0)
        rec2 = video.filtro_recorte((658, 1170), (1920, 1080), "centro", foco=(0.5, 0.2))
        self.assertEqual(rec2["corte"][2:], (1920, 1080))
        self.assertIn("libx264", video.args_encode("25"))
        cadeia = video.filtro_tratamento(self.d, "horizontal")
        self.assertTrue(cadeia == "null" or "eq=" in cadeia or "noise" in cadeia)
        # clipe sintético (testsrc2 + tom): o teste não depende de fixture fora da skill — antes era pulado na cópia instalada
        fixture = self.proj / "bruto" / "sintético 1s.mp4"
        video.executar(["-f", "lavfi", "-i", "testsrc2=size=640x360:rate=30000/1001:duration=1",
                        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=1",
                        *video.args_encode("30000/1001", crf=30)], fixture, rotulo="teste: clipe sintético")
        info = video.sondar(fixture)
        self.assertEqual((info["largura"], info["altura"], info["tem_audio"]), (640, 360, True))
        base = self.proj / "render" / "base curta.mp4"
        video.executar(["-ss", "0.2", "-t", "0.5", "-i", str(fixture), "-vf", "scale=480:270", *video.args_encode(info["fps"], crf=28)], base, rotulo="teste base")
        self.assertTrue(base.is_file() and not base.with_name("base curta.parcial.mp4").exists())
        ov = self.proj / "animacoes" / "moldura alfa.webm"
        if ov.is_file():
            r = video.compor_overlay(base, ov, self.proj / "render" / "composto.mp4", t0=0.0, da_obj=self.d, escala_overlay="480:270")
            self.assertTrue(Path(r["saida"]).is_file())
            self.assertTrue(Path(r["carimbo"]).is_file())
        # overlay de IMAGEM sem `fim`: a saída tem os mesmos quadros da base (com -shortest saía com 2 a menos)
        from PIL import Image
        selo = self.proj / "legendas" / "selo de teste.png"
        selo.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGBA", (80, 40), self.d.rgba("primaria", 0.8)).save(selo)
        quadros_base = video.sondar(base)["quadros"]
        for nome, extra in (("sem fim", {}), ("com fim", {"fim": 0.3})):
            r = video.compor_overlay(base, selo, self.proj / "render" / f"selo {nome}.mp4", t0=0.1, x=10, y=10, da_obj=self.d, **extra)
            self.assertEqual(video.sondar(r["saida"])["quadros"], quadros_base, f"overlay PNG {nome} mudou o número de quadros")
            self.assertEqual(json.loads(Path(r["carimbo"]).read_text(encoding="utf-8"))["ferramenta"], "video.py compor_overlay")
        # ffmpeg que sai com 0 sem gravar nada (instante depois do fim) vira erro acionável, não FileNotFoundError
        with self.assertRaises(da.DAErro) as c:
            video.extrair_quadro(base, 9.0, self.proj / "qa" / "depois do fim.png")
        self.assertIn("não gravou nada", str(c.exception))
        m = video.medir_loudness(base)
        self.assertIsNotNone(m["lufs"])
        q = video.extrair_quadro(base, 0.2, self.proj / "qa" / "q.png", largura=240)
        folha = video.folha_de_contato([q, q], ["um", "dois"], self.proj / "qa" / "folha.png", colunas=2, da_obj=self.d, titulo="Folha")
        self.assertTrue(folha.is_file())


if __name__ == "__main__":
    unittest.main(verbosity=2)
