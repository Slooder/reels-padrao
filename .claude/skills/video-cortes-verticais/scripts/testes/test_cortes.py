#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Testes da video-cortes-verticais. Rodar:  /opt/homebrew/bin/python3 scripts/testes/test_cortes.py
Nada depende de rede nem de arquivo fora da skill e do kit: vídeo e palavras são sintéticos, o projeto de teste nasce
numa pasta temporária COM ESPAÇO E ACENTO no nome e VIDEO_OPS_HOME aponta para dentro dela."""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
RAIZ_TMP = Path(tempfile.mkdtemp(prefix="cortes teste ção ")).resolve()
os.environ["VIDEO_OPS_HOME"] = str(RAIZ_TMP / "ops home")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import candidatos  # noqa: E402
import cortar  # noqa: E402
import cv_base  # noqa: E402
import enquadrar  # noqa: E402

da, video, trava = cv_base.kit()


def tearDownModule():
    shutil.rmtree(RAIZ_TMP, ignore_errors=True)


def palavras_de(texto: str, t0: float = 0.2, dur: float = 0.3, vao: float = 0.05, pausa_na_frase: float = 0.4) -> list[dict]:
    """Palavras cronometradas sintéticas: `dur` por palavra, `vao` entre elas e `pausa_na_frase` depois de . ! ?"""
    saida, t = [], t0
    for w in texto.split():
        saida.append({"a": round(t, 3), "b": round(t + dur, 3), "w": w, "p": 0.95})
        t += dur + (pausa_na_frase if w[-1] in ".!?" else vao)
    return saida


TEXTO = ("Você sabe quanto custa um erro desses? Custa 3 milhões por ano. E ninguém fala disso. "
         "A conta chega para todo mundo. Então preste atenção no que vem agora.")


def quadros_de(pessoas: list, n: int = 24, fps: float = 3.0) -> list[dict]:
    """Quadros de detecção sintéticos: pessoas = [função t → cx | None]; rosto de 0,12 × 0,2 com centro em y 0,45."""
    qs = []
    for k in range(n):
        t = k / fps
        rostos = [{"x": cx - 0.06, "y": 0.35, "w": 0.12, "h": 0.2, "conf": 0.9} for cx in (f(t) for f in pessoas) if cx is not None]
        qs.append({"t": round(t, 3), "rostos": rostos})
    return qs


class Candidatos(unittest.TestCase):
    def test_01_janelas_em_fronteira_de_frase_com_limites_do_kit(self):
        pal = palavras_de(TEXTO)
        fr = cv_base.frases(pal)
        self.assertEqual(len(fr), 5)
        piso = cv_base.limites(cv_base.PLATAFORMAS)["min"]                  # o mínimo também vem do kit
        dmin, dmax, lim = candidatos.faixa_de_duracao(["shorts", "reels", "tiktok"], piso, 6)
        self.assertEqual(lim["por_plataforma"]["shorts"]["max"], da.limite("shorts", "duracao_max_s"))      # lido do kit, não embutido
        self.assertEqual(lim["min"], max(v for v in (da.limite(p, "duracao_min_s") for p in cv_base.PLATAFORMAS) if v is not None))
        js = candidatos.janelas(pal, fr, dmin, dmax)
        self.assertTrue(js)
        inicios, fins = {round(f["t0"], 3) for f in fr}, {round(f["t1"], 3) for f in fr}
        for j in js:
            self.assertIn(j["t0"], inicios)
            self.assertIn(j["t1"], fins)
            self.assertTrue(piso <= j["duracao"] <= 6)
        with self.assertRaises(cv_base.Erro) as e:                          # --max além do teto das plataformas: erro de uso
            candidatos.faixa_de_duracao(["shorts"], 10, da.limite("shorts", "duracao_max_s") + 1)
        self.assertEqual(e.exception.codigo, 64)

    def test_02_sinais_de_abertura_pausas_e_densidade(self):
        pal = palavras_de(TEXTO)
        fr = cv_base.frases(pal)
        s0, s1, s2 = (candidatos.sinais(pal, fr, i, i) for i in (0, 1, 2))
        self.assertTrue(s0["abre_com_pergunta"] and not s0["abre_com_numero"])
        self.assertTrue(s1["abre_com_numero"] and not s1["abre_com_pergunta"])
        self.assertTrue(s2["abre_dependente"])                              # "E ninguém…" pede contexto
        self.assertGreater(candidatos.pontos(s0), candidatos.pontos(s2))
        longa = candidatos.sinais(pal, fr, 0, 2)
        self.assertEqual(longa["pausas"], 0)                                # pausa de frase aqui é 0,4 s (< 0,5)
        self.assertAlmostEqual(longa["maior_pausa"], 0.4, places=2)
        self.assertTrue(2.0 < longa["palavras_por_s"] < 3.5)
        escolhidas = candidatos.escolher(candidatos.janelas(pal, fr, 1, 8), 3)
        self.assertEqual(len(escolhidas), 3)


class Plano(unittest.TestCase):
    def setUp(self):
        self.pal = palavras_de(TEXTO)
        self.fr = cv_base.frases(self.pal)
        self.dur = self.pal[-1]["b"] + 1.0

    def plano(self, **corte):
        base = {"id": "K01", "t0": self.fr[1]["t0"], "t1": self.fr[3]["t1"], "titulo": "t", "gancho": "g", "motivo": "m",
                "enquadramento": "centro", "foco": None, "plataformas": ["shorts", "tiktok"], "saida": "cortes/K01.mp4"}
        base.update(corte)
        return {"versao": 1, "origem": "render/final.mp4", "cortes": [base]}

    def test_03_corte_cai_no_vao_entre_palavras_com_respiro(self):
        p = self.plano()
        erros, avisos = cortar.validar_plano(p, self.pal, self.dur, respiro=0.1)
        self.assertEqual((erros, avisos), ([], []))
        c = p["cortes"][0]
        primeira, ultima = self.pal[c["_i0"]], self.pal[c["_i1"]]
        anterior, seguinte = self.pal[c["_i0"] - 1], self.pal[c["_i1"] + 1]
        self.assertAlmostEqual(c["_t0"], primeira["a"] - 0.1, places=3)       # respiro inteiro: o vão (0,4 s) comporta
        self.assertAlmostEqual(c["_t1"], ultima["b"] + 0.2, places=3)
        self.assertTrue(anterior["b"] < c["_t0"] < primeira["a"] and ultima["b"] < c["_t1"] < seguinte["a"])
        cortar.validar_plano(p, self.pal, self.dur, respiro=5.0)             # respiro exagerado nunca passa do meio do vão
        self.assertAlmostEqual(c["_t0"], (anterior["b"] + primeira["a"]) / 2, places=3)
        self.assertAlmostEqual(c["_t1"], (ultima["b"] + seguinte["a"]) / 2, places=3)

    def test_04_meio_de_frase_e_contrato_reprovam(self):
        meio = self.pal[self.fr[1]["i0"] + 2]["a"]
        p = self.plano(t0=meio)
        erros, _ = cortar.validar_plano(p, self.pal, self.dur)
        self.assertEqual(len(erros), 1)
        self.assertIn("meio da frase", erros[0])
        self.assertIn(cv_base.br(self.fr[1]["t0"]), erros[0])                # diz qual é a fronteira mais próxima
        erros, avisos = cortar.validar_plano(p, self.pal, self.dur, meio_de_frase=True)
        self.assertEqual(erros, [])
        ruim = self.plano(enquadramento="diagonal", foco=[1.4, 0.2], saida="saida/x.mov", id="corte1", plataformas=["youtube"])
        erros, _ = cortar.validar_plano(ruim, self.pal, self.dur)
        for trecho in ("K01, K02", "enquadramento", "foco", "saida", "plataformas de corte vertical"):
            self.assertTrue(any(trecho in e for e in erros), f"faltou reprovar: {trecho} em {erros}")

    def test_05_duracao_por_plataforma_vem_do_kit(self):
        minimo = da.limite("reels", "duracao_min_s")
        curto = self.plano(t0=self.fr[4]["t0"], t1=self.fr[4]["t1"], plataformas=["shorts", "reels"])
        dur = self.fr[4]["t1"] - self.fr[4]["t0"]
        self.assertLess(dur + 0.3, minimo)
        erros, _ = cortar.validar_plano(curto, self.pal, self.dur)
        self.assertTrue(len(erros) == 1 and "mínimo do reels" in erros[0], erros)
        self.assertEqual(cortar.validar_plano(self.plano(t0=self.fr[4]["t0"], t1=self.fr[4]["t1"], plataformas=["shorts"]), self.pal, self.dur)[0], [])
        teto = da.limite("shorts", "duracao_max_s")
        longo = palavras_de(" ".join(["palavra"] * int(teto / 0.35 + 40)) + " fim.")
        p = {"versao": 1, "origem": "x.mp4", "cortes": [{"id": "K01", "t0": longo[0]["a"], "t1": longo[-1]["b"], "titulo": "t", "gancho": "g",
                                                         "motivo": "m", "enquadramento": "faixa", "plataformas": ["shorts", "tiktok"]}]}
        erros, _ = cortar.validar_plano(p, longo, longo[-1]["b"] + 1)
        self.assertTrue(len(erros) == 1 and "máximo do shorts" in erros[0], erros)


class Enquadramento(unittest.TestCase):
    R = 0.316                                                               # recorte 9:16 de altura cheia num 16:9

    def varrer(self, traj, t1: float, passo: float = 1 / 30):
        return [enquadrar.posicao(traj, k * passo) for k in range(int(t1 / passo) + 1)]

    def test_06_trajetoria_parada_com_tremor_e_ponto_solto(self):
        tremor = [(k / 3, 0.30 + (0.02 if k % 2 else -0.02)) for k in range(30)]
        tremor[11] = (tremor[11][0], 0.62)                                   # uma detecção errada isolada
        tremor[20] = (tremor[20][0], 0.36)                                   # saiu da zona morta por UMA amostra e voltou
        traj = enquadrar.trajetoria(tremor, self.R)
        self.assertEqual(traj["movimentos"], [])
        cs = self.varrer(traj, 10)
        self.assertEqual(max(cs) - min(cs), 0.0)                             # nenhum pixel de movimento
        self.assertAlmostEqual(cs[0], 0.30, delta=0.021)

    def test_07_trajetoria_so_anda_fora_da_zona_suave_e_corta_em_troca_de_plano(self):
        def rosto(t):
            return 0.30 if t < 2 else 0.30 + 0.10 * (t - 2) if t < 4 else 0.50
        pontos = [(k / 3, rosto(k / 3)) for k in range(27)]
        traj = enquadrar.trajetoria(pontos, self.R)
        ms = traj["movimentos"]
        self.assertTrue(1 <= len(ms) <= 3, ms)
        self.assertTrue(all(m["tipo"] == "suave" and m["para"] > m["de"] and m["tb"] - m["ta"] >= 0.5 - 1e-6 for m in ms), ms)
        self.assertGreater(ms[0]["ta"], 2.0)                                 # não reage antes de o rosto sair da zona morta
        passo = 1 / 30
        cs = self.varrer(traj, 9, passo)
        deltas = [b - a for a, b in zip(cs, cs[1:])]
        self.assertTrue(all(d >= -1e-9 for d in deltas))                     # sem vai e volta
        self.assertLessEqual(max(deltas) / passo, self.R)                    # velocidade de pico ≤ uma largura de recorte por segundo
        self.assertLessEqual(max(abs(b - a) for a, b in zip(deltas, deltas[1:])), 0.002)   # sem tranco: aceleração contínua
        self.assertAlmostEqual(cs[-1], 0.50, delta=enquadrar.ZONA_MORTA * self.R)
        for t, cx in pontos:                                                 # o rosto inteiro (0,12 de largura) nunca sai do recorte
            self.assertLess(abs(cx - enquadrar.posicao(traj, t)) + 0.06, self.R / 2)
        salto = [(k / 3, 0.25 if k < 12 else 0.75) for k in range(24)]       # outra câmera: o rosto pula de lado
        ms = enquadrar.trajetoria(salto, self.R)["movimentos"]
        self.assertEqual(len(ms), 1)
        self.assertEqual((ms[0]["tipo"], ms[0]["ta"]), ("corte", ms[0]["tb"]))
        self.assertTrue(11 / 3 < ms[0]["ta"] < 12 / 3)

    def test_08_sugestao_pelo_numero_de_rostos_e_cadeias(self):
        dois = quadros_de([lambda t: 0.28, lambda t: 0.74, lambda t: 0.5 if t < 1 else None])   # o 3º rosto só passa
        self.assertEqual(enquadrar.sugerir(dois)["enquadramento"], "empilhado")
        self.assertEqual(len(enquadrar.sugerir(dois)["pessoas"]), 2)
        um = quadros_de([lambda t: 0.4])
        self.assertEqual(enquadrar.sugerir(um)["enquadramento"], "rosto")
        self.assertEqual(enquadrar.sugerir(quadros_de([]))["enquadramento"], "centro")
        W, H, L, A = 1280, 720, 270, 480
        e = enquadrar.montar("auto", (W, H), (L, A), 0, 8, dois)
        self.assertEqual(e["modo"], "empilhado")
        for painel, cx in zip(e["dados"]["paineis"], (0.28, 0.74)):          # cada painel centrado no rosto, só uma pessoa em cada
            self.assertAlmostEqual(painel["x"] + painel["w"] / 2, cx * W, delta=2)
            self.assertAlmostEqual((0.45 * H - painel["y"]) / painel["h"], enquadrar.ALTURA_DO_ROSTO, delta=0.02)
            self.assertLessEqual(painel["w"], (0.74 - 0.28) * W + 2)
        invertido = enquadrar.montar("empilhado", (W, H), (L, A), 0, 8, dois, pessoa="direita")
        self.assertGreater(invertido["dados"]["paineis"][0]["x"], invertido["dados"]["paineis"][1]["x"])
        direita = enquadrar.montar("rosto", (W, H), (L, A), 0, 8, dois, pessoa="direita")
        self.assertEqual(direita["avisos"], [])
        self.assertAlmostEqual(direita["dados"]["trajetoria"]["inicio"], 0.74, delta=0.01)
        self.assertTrue(any("pessoa" in a for a in enquadrar.montar("rosto", (W, H), (L, A), 0, 8, dois)["avisos"]))
        sem = enquadrar.montar("rosto", (W, H), (L, A), 0, 8, None, sem_rostos="Vision indisponível")
        self.assertEqual(sem["modo"], "centro")                              # sem detecção: cai para centro, com aviso claro
        self.assertTrue(len(sem["avisos"]) == 1 and "Vision indisponível" in sem["avisos"][0] and "centro" in sem["avisos"][0])
        manual = enquadrar.montar("rosto", (W, H), (L, A), 0, 8, dois, foco=[0.6, 0.5])      # foco manual vence a detecção
        self.assertTrue(manual["dados"]["manual"])
        self.assertAlmostEqual(manual["dados"]["recorte"][2] + manual["dados"]["recorte"][0] / 2, 0.6 * W, delta=2)
        # troca de plano no meio do corte (dois apresentadores → plano fechado de um): corte seco para o rosto que ficou
        troca = quadros_de([lambda t: 0.28 if t < 4 else None, lambda t: 0.74 if t < 4 else None, lambda t: 0.5 if t >= 4 else None])
        ms = enquadrar.montar("rosto", (W, H), (L, A), 0, 8, troca, pessoa="esquerda")["dados"]["trajetoria"]["movimentos"]
        self.assertEqual([(m["tipo"], round(m["para"], 2)) for m in ms], [("corte", 0.5)])
        some = quadros_de([lambda t: None if 3 <= t < 5 else 0.28, lambda t: 0.74])      # o alvo só deixou de ser detectado: não pula para o colega
        self.assertEqual(enquadrar.montar("rosto", (W, H), (L, A), 0, 8, some, pessoa="esquerda")["dados"]["trajetoria"]["movimentos"], [])
        self.assertTrue(any("juntos" in a for a in enquadrar.montar("empilhado", (W, H), (L, A), 0, 8, some)["avisos"]))
        # a abertura sai de cima do rosto sem sair da área livre (zona segura menos a faixa da legenda)
        cabecas = [(a * 960, b * 960) for a, b in e["dados"]["rostos_na_saida"]]
        self.assertTrue(len(cabecas) == 2 and cabecas[0][1] < 480 < cabecas[1][0])        # uma cabeça em cada metade
        self.assertEqual(cortar.posicionar_abertura((487, 532), (144, 532), [(50, 281), (530, 761)]), (0, False))   # já está num vão: fica
        dy, cobre = cortar.posicionar_abertura((487, 532), (144, 532), [(203, 526)])
        self.assertTrue(not cobre and 487 + dy >= 144 and 532 + dy <= 203, dy)             # sobe para cima da cabeça
        self.assertEqual(cortar.posicionar_abertura((487, 532), (144, 532), [(150, 526)]), (0, True))             # não cabe: avisa


class Render(unittest.TestCase):
    """Peças de verdade, minúsculas: 3 s de vídeo sintético 320×180 → cortes 180×320."""

    @classmethod
    def setUpClass(cls):
        cls.projeto = RAIZ_TMP / "projeto de teste"
        da.iniciar(str(cls.projeto), "Cortes teste", "lab-ia")
        (cls.projeto / "render").mkdir(exist_ok=True)
        cls.origem = cls.projeto / "render" / "final.mp4"
        # barra clara parada em x 40–60 sobre fundo neutro (cores do gerador de teste do ffmpeg, não da peça) + tom de 220 Hz
        video.executar(["-f", "lavfi", "-i", "color=c=gray:s=320x180:r=30:d=3,drawbox=x=40:y=0:w=20:h=180:color=white:t=fill",  # da-livre
                        "-f", "lavfi", "-i", "sine=frequency=220:duration=3", "-shortest", *video.args_encode("30", crf=20)], cls.origem, rotulo="teste")
        cls.pal = palavras_de("Isso muda tudo. Veja agora como.", t0=0.3, dur=0.3, vao=0.05, pausa_na_frase=0.3)
        (cls.projeto / "transcricao").mkdir(exist_ok=True)
        cv_base.gravar_json(cls.projeto / "transcricao" / "final.palavras.json", cls.pal)

    def test_09_recorte_movel_roda_no_ffmpeg_e_anda(self):
        traj = {"inicio": 0.2, "movimentos": [{"ta": 0.8, "tb": 1.6, "de": 0.2, "para": 0.7, "tipo": "suave"}]}
        cw, W = 100, 320
        expr = enquadrar._expressao(traj, 0.0, lambda c: min(max(c * W - cw / 2, 0), W - cw))
        saida = self.projeto / "cortes" / "_movel.mp4"
        saida.parent.mkdir(exist_ok=True)
        video.executar(["-i", str(self.origem), "-vf", f"crop={cw}:180:'{expr}':0:exact=1", "-an", *video.args_encode("30", audio=False)], saida, rotulo="teste")
        from PIL import Image, ImageStat
        medias = []
        for n, t in enumerate((0.2, 2.3)):
            q = video.extrair_quadro(saida, t, saida.with_name(f"_q{n}.png"))
            with Image.open(q) as im:
                medias.append(ImageStat.Stat(im.convert("L")).mean[0])
        self.assertGreater(medias[0], medias[1] + 15)                        # no início a barra clara está no recorte; no fim, saiu

    def test_10_plano_vira_corte_com_legenda_srt_carimbo_e_previa(self):
        fr = cv_base.frases(self.pal)
        plano = {"versao": 1, "origem": "render/final.mp4", "cortes": [
            {"id": "K01", "t0": fr[0]["t0"], "t1": fr[1]["t1"], "titulo": "Isso muda tudo", "gancho": "Isso muda tudo", "motivo": "teste",
             "enquadramento": "rosto", "foco": None, "plataformas": ["shorts", "tiktok"], "saida": "cortes/K01.mp4"},
            {"id": "K02", "t0": fr[0]["t0"], "t1": fr[1]["t1"], "titulo": "Faixa", "gancho": "g", "motivo": "teste",
             "enquadramento": "faixa", "foco": None, "plataformas": ["shorts"], "saida": "cortes/K02.mp4"}]}
        cv_base.gravar_json(self.projeto / "cortes" / "plano.json", plano)
        self.assertEqual(cortar.main(["--projeto", str(self.projeto), "--formato", "180x320", "--previa", "--so", "K01"]), 0)
        self.assertTrue((self.projeto / "cortes" / "_previa_K01.png").is_file())
        self.assertFalse((self.projeto / "cortes" / "K01.mp4").exists())      # prévia não renderiza o corte
        self.assertEqual(cortar.main(["--projeto", str(self.projeto), "--formato", "180x320"]), 0)
        for cid, modo in (("K01", "centro"), ("K02", "faixa")):              # vídeo sem rosto: `rosto` caiu para `centro`
            saida = self.projeto / "cortes" / f"{cid}.mp4"
            s = video.sondar(saida)
            self.assertEqual((s["largura"], s["altura"], s["tem_audio"]), (180, 320, True))
            car = da.ler_carimbo(saida)
            p = car["parametros"]
            self.assertEqual((car["ferramenta"], p["enquadramento"]["modo"]), ("video-cortes-verticais", modo))
            self.assertAlmostEqual(s["duracao"], p["t1_origem"] - p["t0_origem"], delta=0.08)
            self.assertTrue(p["t0_origem"] < fr[0]["t0"] and p["t1_origem"] > fr[1]["t1"])
            self.assertEqual(car["insumos"][0]["arquivo"], "final.mp4")
            self.assertTrue(p["loudness"]["ok"], p["loudness"])
            self.assertIn("Isso muda tudo", saida.with_suffix(".srt").read_text(encoding="utf-8"))
            self.assertTrue((self.projeto / "cortes" / f"_previa_{cid}.png").is_file())
        self.assertEqual(da.ler_carimbo(self.projeto / "cortes" / "K01.mp4")["parametros"]["plataformas"], ["shorts", "tiktok"])
        if sys.platform == "darwin" and shutil.which("swiftc"):              # a detecção rodou de verdade e não achou rosto
            cache = json.loads((self.projeto / "cortes" / "_rostos" / "final.json").read_text(encoding="utf-8"))
            self.assertTrue(cache["quadros"] and all(q["rostos"] == [] for q in cache["quadros"]))
        sobras = [a.name for a in (self.projeto / "cortes").iterdir() if a.name.endswith("_base.mp4") or a.name.endswith("_quadros")]
        self.assertEqual(sobras, [])
        conf = da.conferir_carimbo([str(self.projeto / "cortes" / "K01.mp4")], da=da.carregar(str(self.projeto)))
        self.assertEqual(conf["pecas"][0]["estado"], "ok", conf["pecas"][0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
