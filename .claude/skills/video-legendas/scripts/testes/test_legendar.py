#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Linha do tempo, sincronia, zona segura, contraste, saídas e erros do legendar.py.

TestLinhaDoTempo não roda ffmpeg. As outras classes renderizam vídeos de 3 s a 360×640 (base sintética feita pelo
Codificador do kit), sempre pela trava global; a suíte inteira leva cerca de um minuto com a máquina livre."""
import json
import sys
import unittest
from fractions import Fraction
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import apoio  # noqa: E402
import comum  # noqa: E402
import cues  # noqa: E402
import legendar  # noqa: E402

TEXTO = "O dinheiro público some no caminho, e ninguém explica. Agora vai mudar?"


def palavras_curtas():
    """12 palavras em ~2,9 s (a última de 2,67 a 2,87 s), com vírgula, ponto e interrogação."""
    return apoio.palavras_sinteticas(TEXTO, inicio=0.1, ritmo=0.016, pausa_frase=0.3, pausa_virgula=0.12)


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raiz = apoio.pasta_temporaria()
        cls.da, cls.texto, cls.video, _ = comum.kit()

    @classmethod
    def tearDownClass(cls):
        apoio.apagar(cls.raiz)


class TestLinhaDoTempo(Base):
    """A linha do tempo em quadros, sem render: em cada instante, qual estado está na tela."""

    def montar(self, preset, L=540, A=960, fps=30, plataforma=None, **legenda):
        proj = apoio.projeto(self.raiz, preset, nome=f"lt {preset} {' '.join(f'{k} {v}' for k, v in legenda.items())}".strip(), **legenda)
        d = self.da.carregar(str(proj))
        doc = cues.construir(palavras_curtas(), d, L, A, f"{L}x{A}", plataforma=plataforma, duracao=3.0, fps=fps)
        m = legendar._Estados(doc, d, L, A, Fraction(fps), proj / "legendas" / "_png" / "teste")
        return d, doc, m, m.montar()

    def ativos(self, entradas, t):
        return [e for e in entradas if e["t0"] <= t < e["t1"]]

    def conferir_sincronia(self, doc, entradas, por_palavra=True):
        ordenadas = sorted(entradas, key=lambda e: e["t0"])
        for a, b in zip(ordenadas, ordenadas[1:]):
            self.assertLessEqual(a["t1"], b["t0"] + 1e-9, "dois estados no mesmo quadro")
        self.assertGreaterEqual(ordenadas[0]["t0"], 0)
        self.assertLessEqual(ordenadas[-1]["t1"], doc["duracao"] + 1e-6)
        for c in doc["cues"]:
            fins = [w["a"] for w in c["palavras"][1:]] + [c["t1"]]
            for i, (w, fim) in enumerate(zip(c["palavras"], fins)):
                no_ar = self.ativos(entradas, (w["a"] + fim) / 2)                # no MEIO da palavra…
                self.assertEqual(len(no_ar), 1, (c["id"], w["w"]))
                self.assertEqual(no_ar[0]["cue"], c["id"])
                self.assertEqual(no_ar[0]["indice"], i if por_palavra else None, (c["id"], w["w"]))   # …o estado é o daquela palavra

    def test_01_karaoke_com_fade(self):
        d, doc, m, ent = self.montar("lab-ia")
        self.assertEqual((m.estilo, m.animacao), ("karaoke", "fade"))
        self.conferir_sincronia(doc, ent)
        primeira = [e for e in ent if e["cue"] == 1]
        alfas = [e["alfa"] for e in primeira]
        subida = alfas[:alfas.index(1.0)]
        self.assertGreaterEqual(len(subida), 2)                                 # entra em mais de um quadro
        self.assertEqual(subida, sorted(subida))
        self.assertTrue(all(0 < a < 1 for a in subida))
        dur_fade = sum(e["t1"] - e["t0"] for e in primeira if e["alfa"] < 1)
        self.assertLessEqual(dur_fade, d.dur("curta") + 1 / 30 + 1e-6)         # duração da DA (movimento.duracoes.curta)
        self.assertTrue(all(e["ampliacao"] == 1.0 for e in ent))
        self.assertEqual(m.rel["fora_da_zona"], [])

    def test_02_palavra_com_pop(self):
        d, doc, m, ent = self.montar("neon-shorts")
        self.assertEqual((m.estilo, m.animacao), ("palavra", "pop"))
        self.conferir_sincronia(doc, ent)
        for c in doc["cues"]:
            for i in range(len(c["palavras"])):
                da_palavra = sorted((e for e in ent if e["cue"] == c["id"] and e["indice"] == i), key=lambda e: e["t0"])
                self.assertGreater(da_palavra[0]["ampliacao"], 1.0, "a palavra nasce maior")
                self.assertLessEqual(da_palavra[0]["ampliacao"], 1 + legendar.AMPLITUDE_DO_POP + 1e-9)
                self.assertEqual(da_palavra[-1]["ampliacao"], 1.0, "e assenta")
                self.assertLessEqual(sum(e["t1"] - e["t0"] for e in da_palavra if e["ampliacao"] > 1), d.dur("micro") + 1 / 30 + 1e-6)

    def test_03_bloco_e_um_estado_por_cue(self):
        d, doc, m, ent = self.montar("editorial-claro", animacao="nenhuma")
        self.conferir_sincronia(doc, ent, por_palavra=False)
        self.assertEqual(len(ent), len(doc["cues"]))
        for e, c in zip(sorted(ent, key=lambda e: e["t0"]), doc["cues"]):
            self.assertAlmostEqual(e["t0"], c["t0"], delta=0.5 / 30 + 1e-6)     # no quadro mais próximo
            self.assertAlmostEqual(e["t1"], c["t1"], delta=0.5 / 30 + 1e-6)

    def test_04_karaoke_com_pop_no_lugar(self):
        from PIL import Image
        for preset in ("lab-ia", "neon-shorts"):                               # com caixa de fundo · com contorno e sombra
            d, doc, m, ent = self.montar(preset, estilo="karaoke", animacao="pop")
            self.conferir_sincronia(doc, ent)
            self.assertEqual(m.rel["fora_da_zona"], [])
            c = next(c for c in doc["cues"] if len(c["palavras"]) >= 2)
            pop = next(e for e in ent if e["cue"] == c["id"] and e["indice"] == 1 and e["ampliacao"] > 1)
            assentado = next(e for e in ent if e["cue"] == c["id"] and e["indice"] == 1 and e["ampliacao"] == 1.0)
            a, b = Image.open(pop["imagem"]).convert("RGBA"), Image.open(assentado["imagem"]).convert("RGBA")
            # as vizinhas não se mexem: fora da faixa da palavra que cresce, os dois estados são idênticos
            estados = legendar._estados_da_cue(c, d, 540, 960, None, self.texto)
            info = estados[1][1]
            p0 = info["palavras"][0]
            tela_a, tela_b = Image.new("RGBA", (540, 960), (0, 0, 0, 0)), Image.new("RGBA", (540, 960), (0, 0, 0, 0))
            tela_a.alpha_composite(a, (pop["x"], pop["y"]))
            tela_b.alpha_composite(b, (assentado["x"], assentado["y"]))
            if info["palavras"][1]["linha"] == p0["linha"]:
                caixa = (int(p0["x0"]) - 2, int(p0["y0"]), int(p0["x0"] + (p0["x1"] - p0["x0"]) * 0.6), int(p0["y1"]))
                self.assertEqual(tela_a.crop(caixa).tobytes(), tela_b.crop(caixa).tobytes(), f"{preset}: a palavra vizinha mudou durante o pop")
            self.assertNotEqual(tela_a.tobytes(), tela_b.tobytes())

    def test_05_zona_segura_em_todas_as_plataformas(self):
        for preset in ("lab-ia", "neon-shorts", "dossie"):
            for (L, A, plat) in ((540, 960, None), (540, 960, "tiktok"), (540, 960, "reels"), (540, 960, "shorts"), (960, 540, None), (1080, 1920, None)):
                d, doc, m, ent = self.montar(preset, L=L, A=A, plataforma=plat)
                zona = d.margens("vertical" if A > L else "horizontal", plat, largura=L, altura=A)
                self.assertEqual(m.rel["fora_da_zona"], [], (preset, L, A, plat))
                for cid, (x0, y0, x1, y1) in m.rel["caixas"].items():
                    self.assertTrue(x0 >= zona["x0"] - 0.5 and x1 <= zona["x1"] + 0.5 and y0 >= zona["y0"] - 0.5 and y1 <= zona["y1"] + 0.5,
                                    (preset, L, A, plat, cid, (x0, y0, x1, y1), zona))

    def test_06_pop_nao_sai_da_zona(self):
        zona = {"x0": 100, "y0": 100, "x1": 500, "y1": 400}
        self.assertEqual(legendar._folga_de_pop((100, 200, 500, 260), zona, 1.08), 1.0)             # encostada: não cresce
        self.assertAlmostEqual(legendar._folga_de_pop((110, 200, 490, 260), zona, 1.08), 1 + 20 / 380)
        self.assertEqual(legendar._folga_de_pop((200, 200, 400, 260), zona, 1.08), 1.08)            # com folga: cresce tudo

    @staticmethod
    def _cue(linhas):
        """Uma cue do contrato a partir das linhas (0,3 s por palavra)."""
        palavras, t = [], 0.0
        for li, linha in enumerate(linhas):
            for w in linha:
                palavras.append({"a": round(t, 3), "b": round(t + 0.3, 3), "w": w, "linha": li, "destaque": False})
                t += 0.3
        return {"id": 1, "t0": 0.0, "t1": round(t, 3), "linhas": [list(l) for l in linhas], "palavras": palavras}

    def test_08_pop_do_karaoke_nao_cola_na_vizinha_nem_apaga_o_acento(self):
        """Regressão: por 1–4 quadros «uma investigação» virava «umainvestigação» e o «A» ampliado apagava o acento de «DENÚNCIA»."""
        import numpy as np
        L, A = 1080, 1920

        def cor_exata(img, rgba, x, y, caixa):
            """Quantos pixels opacos da cor `rgba` há na caixa (em px do quadro) de uma imagem colada em (x, y)."""
            tela = np.zeros((A, L, 4), dtype=np.uint8)
            arr = np.asarray(img.convert("RGBA"))
            tela[y:y + arr.shape[0], x:x + arr.shape[1]] = arr
            x0, y0, x1, y1 = (int(round(v)) for v in caixa)
            rec = tela[y0:y1, x0:x1]
            return int(((rec[..., :3] == np.array(rgba[:3], dtype=np.uint8)).all(axis=-1) & (rec[..., 3] == 255)).sum())

        # 1. palavra longa ao lado de uma curta (caixa de fundo e contorno): o vão não fecha
        for preset, linhas in (("lab-ia", [["uma", "investigação"]]), ("dossie", [["tem", "muito"]])):
            d = self.da.carregar(str(apoio.projeto(self.raiz, preset, nome=f"lt pop vão {preset}", estilo="karaoke", animacao="pop")))
            cue = self._cue(linhas)
            img, info = legendar._estados_da_cue(cue, d, L, A, None, self.texto)[1]
            self.assertEqual(len(info["linhas"]), 1, preset)
            ests = legendar._estilos_do_estado(d, L, A, self.texto, [False, False], 1)
            pop, x, y, usado, pela_zona = legendar._pop_no_lugar(img, info, 1, 1 + legendar.AMPLITUDE_DO_POP, ests, self.texto)
            p0, p1 = info["palavras"]
            vao, largura = p1["x0"] - p0["x1"], p1["x1"] - p1["x0"]
            self.assertGreater(usado, 1.0, preset)                              # cresce…
            self.assertLessEqual(usado, 1 + vao / largura + 1e-6, preset)       # …no máximo meio vão para cada lado
            self.assertFalse(pela_zona)
            meio = (p0["x1"] + p1["x0"]) / 2
            faixa = (meio - 1, p1["y0"], meio + 1, p1["y1"])                    # a coluna do meio do vão: nenhuma tinta da palavra falada
            self.assertEqual(cor_exata(pop, ests[1].cor, x, y, faixa), 0, f"{preset}: a palavra ampliada passou do meio do vão")
            esquerda = (p0["x0"], p0["y0"], p0["x1"] - 2, p0["y1"])             # a vizinha não muda (as letras dela ficam por cima)
            self.assertEqual(cor_exata(pop, ests[0].cor, x, y, esquerda), cor_exata(img, ests[0].cor, info["x"], info["y"], esquerda), preset)
        # 2. duas linhas, altura de linha apertada: o acento da linha de baixo continua lá quando a de cima cresce
        d = self.da.carregar(str(apoio.projeto(self.raiz, "neon-shorts", nome="lt pop acento", estilo="karaoke", animacao="pop")))
        cue = self._cue([["a"], ["denúncia"]])
        img, info = legendar._estados_da_cue(cue, d, L, A, None, self.texto)[0]
        self.assertEqual(len(info["linhas"]), 2)
        ests = legendar._estilos_do_estado(d, L, A, self.texto, [False, False], 0)
        pop, x, y, usado, _ = legendar._pop_no_lugar(img, info, 0, 1 + legendar.AMPLITUDE_DO_POP, ests, self.texto)
        self.assertGreater(usado, 1.04)
        baixo = info["palavras"][1]
        alt = baixo["y1"] - baixo["y0"]
        topo_da_linha = (baixo["x0"], baixo["y0"] - 0.3 * alt, baixo["x1"], baixo["y0"] + 0.25 * alt)       # onde mora o acento do Ú
        antes, depois = cor_exata(img, ests[1].cor, info["x"], info["y"], topo_da_linha), cor_exata(pop, ests[1].cor, x, y, topo_da_linha)
        self.assertGreater(antes, 50)
        self.assertGreaterEqual(depois, 0.97 * antes, "o contorno da palavra ampliada cobriu o acento da linha de baixo")
        # e não sobra risco da palavra assentada: a de cima, ampliada, tem a mesma quantidade de tinta do contorno que teria sozinha (±)
        self.assertEqual(pop.getchannel("A").getextrema()[1], 255)

    def test_09_linhas_acima_do_teto_da_da_sao_refeitas_e_nada_sai_da_faixa(self):
        """Regressão: cue com 4 linhas numa DA de 2 era desenhada assim mesmo, 111 px para fora da faixa reservada à legenda."""
        proj = apoio.projeto(self.raiz, "dossie", nome="lt linhas")
        d = self.da.carregar(str(proj))
        self.assertEqual(legendar.linhas_permitidas(d), 2)
        cue = self._cue([["tem"], ["muito"], ["mais"], ["peso"]])
        estados = legendar._estados_da_cue(cue, d, 1080, 1920, None, self.texto)
        faixa = d.faixa_legenda("1080x1920")
        for _, info in estados:
            self.assertLessEqual(len(info["linhas"]), 2)
            self.assertGreaterEqual(info["caixa"][1], faixa["y0"] - 1.5)
            self.assertLessEqual(info["caixa"][3], faixa["y1"] + 1.5)
        doc = cues.construir(palavras_curtas(), d, 1080, 1920, "vertical", duracao=3.0, fps=30)
        longa = next(c for c in doc["cues"] if len(c["palavras"]) >= 3)
        longa["linhas"] = [[w["w"]] for w in longa["palavras"]]
        for n, w in enumerate(longa["palavras"]):
            w["linha"] = n
        m = legendar._Estados(doc, d, 1080, 1920, Fraction(30), proj / "legendas" / "_png" / "teste")
        m.montar()
        self.assertEqual(m.rel["linhas_refeitas"], [longa["id"]])
        self.assertEqual(m.rel["fora_da_faixa"], [])
        self.assertEqual(m.rel["fora_da_zona"], [])
        # estilo `palavra`: o teto é uma linha
        self.assertEqual(legendar.linhas_permitidas(self.da.carregar(str(apoio.projeto(self.raiz, "neon-shorts", nome="lt linhas palavra")))), 1)

    def test_07_destaque_do_glossario_fica_aceso(self):
        proj = apoio.projeto(self.raiz, "dossie", nome="lt destaque")
        d = self.da.carregar(str(proj))
        g = {"trocas": {}, "censura": [], "numeros_em_algarismo": False, "mascara": "***", "destaques": ["dinheiro"]}
        doc = cues.construir(palavras_curtas(), d, 540, 960, "540x960", duracao=3.0, fps=30, glossario=g)
        c = doc["cues"][0]
        k = [w["w"] for w in c["palavras"]].index("dinheiro")
        estados = legendar._estados_da_cue(c, d, 540, 960, None, self.texto)
        sem = legendar._estados_da_cue({**c, "palavras": [{**w, "destaque": False} for w in c["palavras"]]}, d, 540, 960, None, self.texto)
        self.assertEqual(len(estados), len(c["palavras"]))
        self.assertEqual(estados[k][0].tobytes(), sem[k][0].tobytes())                 # enquanto é falada, igual
        if k + 1 < len(estados):
            self.assertNotEqual(estados[-1][0].tobytes(), sem[-1][0].tobytes())        # depois de dita, continua em cor_destaque
        if k > 0:
            self.assertEqual(estados[0][0].tobytes(), sem[0][0].tobytes())             # antes de ser dita, cor normal


class TestRender(Base):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # texto grande e sem animação: o teste de sincronia lê a COR dos pixels (o fade é conferido na linha do tempo)
        cls.proj = apoio.projeto(cls.raiz, "lab-ia", nome="projeto render ção", tamanho=0.085, animacao="nenhuma")
        cls.d = cls.da.carregar(str(cls.proj))
        cls.base = apoio.video_sintetico(cls.proj, "base vertical", 360, 640, 3.0, 30)
        cls.arq_palavras = apoio.gravar_palavras(cls.proj, palavras_curtas())
        cls.r = legendar.legendar(cls.base, cls.arq_palavras, cls.proj / "legendas" / "corte 01.mp4", projeto=cls.proj)
        cls.doc = json.loads(Path(cls.r["cues_json"]).read_text(encoding="utf-8"))

    def test_10_saida_midia_e_arquivos(self):
        r, s = self.r, self.video.sondar(self.r["saida"])
        self.assertEqual((s["largura"], s["altura"], s["fps"]), (360, 640, Fraction(30)))
        self.assertAlmostEqual(s["duracao"], 3.0, delta=0.08)
        self.assertTrue(s["tem_audio"], "o áudio da base tem de continuar")
        self.assertEqual(s["pix_fmt"], "yuv420p")
        for chave in ("cues_json", "srt", "vtt"):
            self.assertTrue(Path(r[chave]).is_file(), chave)
        self.assertEqual(Path(r["cues_json"]).name, "corte 01.cues.json")
        self.assertIsNone(r["srt_ao_lado"])                                     # a saída já está em legendas/
        self.assertFalse((self.proj / "legendas" / "_png").exists(), "os PNGs de trabalho têm de sumir")
        self.assertEqual(self.doc["origem"], "bruto/base vertical.mp4")         # relativo à raiz do projeto
        self.assertEqual(self.doc["fonte"], {"video": "bruto/base vertical.mp4", "inicio": 0.0, "fim": None})
        self.assertEqual((r["formato"], r["plataforma"], r["estilo"], r["animacao"]), ("360x640", "uniao", "karaoke", "nenhuma"))
        self.assertTrue(r["conferencia"]["zona"]["ok"])
        self.assertGreaterEqual(r["estados"], r["palavras"])

    def test_11_carimbo_com_cues_e_insumos(self):
        conf = self.da.conferir_carimbo([self.r["saida"]], da=str(self.proj))
        self.assertTrue(conf["ok"], conf["pecas"])
        c = self.da.ler_carimbo(self.r["saida"])
        self.assertEqual(c["ferramenta"], "video-legendas")
        self.assertEqual(c["da_sha256"], self.d.sha256)
        p = c["parametros"]
        self.assertEqual(p["cues_json"], "legendas/corte 01.cues.json")
        self.assertEqual(p["cues_sha256"], comum.sha256_arquivo(self.r["cues_json"]))
        self.assertEqual((p["estilo"], p["animacao"], p["plataforma"], p["n_cues"]), ("karaoke", "nenhuma", "uniao", len(self.doc["cues"])))
        self.assertTrue(p["conferencia"]["zona_ok"])
        self.assertEqual(sorted(i["arquivo"] for i in c["insumos"]), ["base vertical.mp4", "corte 01.cues.json"])

    def test_12_sincronia_no_video(self):
        """No meio de cada palavra, o quadro do vídeo tem AQUELA palavra na cor de destaque e as outras não."""
        meios = {}
        for c in self.doc["cues"]:
            fins = [w["a"] for w in c["palavras"][1:]] + [c["t1"]]
            for i, (w, fim) in enumerate(zip(c["palavras"], fins)):
                meios[(c["id"], i)] = int(round((w["a"] + fim) / 2 * 30))
        quadros, L, A = apoio.quadros_rgb(self.r["saida"], [0, *meios.values()])
        leg = self.d["legenda"]
        alvo = self.d.rgb(leg["cor_destaque"])
        outras = [self.d.rgb(leg["cor"])] + ([self.d.rgb(leg["cor_falada"])] if leg.get("cor_falada") else [])

        def fracao_acesa(quadro, caixa):
            x0, y0, x1, y1 = (int(round(v)) for v in caixa)
            acesos = total = 0
            for y in range(max(0, y0), min(A, y1)):
                linha = quadro[(y * L + max(0, x0)) * 3:(y * L + min(L, x1)) * 3]
                for k in range(0, len(linha), 3):
                    px = linha[k:k + 3]
                    d_alvo = sum((px[c] - alvo[c]) ** 2 for c in range(3))
                    if d_alvo < 70 ** 2 and all(d_alvo < sum((px[c] - o[c]) ** 2 for c in range(3)) for o in outras):
                        acesos += 1
                    total += 1
            return acesos / max(1, total)

        conferidas = 0
        for c in self.doc["cues"]:
            estados = legendar._estados_da_cue(c, self.d, L, A, None, self.texto)
            caixas = [(p["x0"], p["y0"], p["x1"], p["y1"]) for p in estados[0][1]["palavras"]]
            fins = [w["a"] for w in c["palavras"][1:]] + [c["t1"]]
            for i, (w, fim) in enumerate(zip(c["palavras"], fins)):
                q = quadros[meios[(c["id"], i)]]
                acesa = [fracao_acesa(q, cx) for cx in caixas]
                self.assertGreater(acesa[i], 0.06, (c["id"], w["w"], acesa))
                for j, f in enumerate(acesa):
                    if j != i:
                        self.assertLess(f, acesa[i] / 4, (c["id"], w["w"], "acesa junto:", c["palavras"][j]["w"], acesa))
                conferidas += 1
        self.assertEqual(conferidas, len(palavras_curtas()))
        # fora das cues não há legenda: o último quadro antes da primeira palavra é a base lisa
        antes = quadros[0]
        self.assertLess(len(set(antes[i:i + 3] for i in range(0, len(antes), 3 * 97))), 4)

    def test_13_janela_de_corte(self):
        r = legendar.legendar(self.base, self.arq_palavras, self.proj / "cortes" / "K01.mp4", inicio=1.0, fim=2.5, projeto=self.proj)
        s = self.video.sondar(r["saida"])
        self.assertAlmostEqual(s["duracao"], 1.5, delta=0.08)
        self.assertTrue(s["tem_audio"])
        doc = json.loads(Path(r["cues_json"]).read_text(encoding="utf-8"))
        todas = palavras_curtas()
        esperadas = [cues.partir_token(w["w"])[1] for w in todas if 1.0 <= (w["a"] + w["b"]) / 2 < 2.5]
        self.assertEqual([cues.partir_token(w["txt"])[1] for c in doc["cues"] for w in c["palavras"]], esperadas)
        self.assertLessEqual(doc["cues"][-1]["t1"], 1.5 + 1e-6)
        self.assertEqual(doc["origem"], "cortes/K01.mp4")                       # com trecho, os tempos são os do vídeo legendado
        self.assertEqual(doc["fonte"], {"video": "bruto/base vertical.mp4", "inicio": 1.0, "fim": 2.5})
        self.assertEqual(Path(r["srt_ao_lado"]), self.proj / "cortes" / "K01.srt")       # é onde video-publicacao procura
        self.assertEqual(Path(r["srt_ao_lado"]).read_text(encoding="utf-8"), Path(r["srt"]).read_text(encoding="utf-8"))
        self.assertTrue(self.da.conferir_carimbo([r["saida"]], da=str(self.proj))["ok"])

    def test_14_base_horizontal_vira_vertical_pelo_recorte_do_kit(self):
        base_h = apoio.video_sintetico(self.proj, "base horizontal", 640, 360, 2.0, 30, token="fundo", audio=False)
        r = legendar.legendar(base_h, self.arq_palavras, self.proj / "legendas" / "vertical do horizontal.mp4", formato="360x640",
                              fim=2.0, plataforma="tiktok", projeto=self.proj)
        s = self.video.sondar(r["saida"])
        self.assertEqual((s["largura"], s["altura"]), (360, 640))
        self.assertFalse(s["tem_audio"])
        self.assertEqual(r["plataforma"], "tiktok")
        self.assertEqual(self.da.ler_carimbo(r["saida"])["parametros"]["enquadramento"], "recorte")
        self.assertEqual(self.da.ler_carimbo(r["saida"])["formato"], "360x640")

    def test_15_so_overlay_com_alfa_nos_dois_codecs(self):
        r = legendar.legendar(self.base, self.arq_palavras, self.proj / "legendas" / "faixa.mov", so_overlay=True, codec="ambos", projeto=self.proj)
        self.assertEqual(sorted(Path(p).name for p in r["saidas"]), ["faixa.mov", "faixa.webm"])
        for p in r["saidas"]:
            s = self.video.sondar(p)
            self.assertTrue(s["tem_alfa"], p)
            self.assertEqual((s["largura"], s["altura"], s["quadros"]), (360, 640, 90), p)
            self.assertFalse(s["tem_audio"])
            self.assertTrue(self.da.conferir_carimbo([p], da=str(self.proj))["ok"], p)
            self.assertTrue(self.da.ler_carimbo(p)["parametros"]["so_overlay"])
        with self.assertRaises(comum.Erro) as cm:
            legendar.legendar(self.base, self.arq_palavras, self.proj / "legendas" / "faixa.mp4", so_overlay=True, projeto=self.proj)
        self.assertEqual(cm.exception.codigo, 64)

    def test_16_previa_nao_renderiza_video(self):
        r = legendar.legendar(self.base, self.arq_palavras, previa=3, nome="só prévia", projeto=self.proj)
        self.assertIsNone(r["saida"])
        self.assertEqual(Path(r["previa"]).name, "_previa_só prévia.png")       # `_`: intermediário, fora do lint e da conferência final
        from PIL import Image
        with Image.open(r["previa"]) as im:
            self.assertGreater(im.width, 3 * 300)
        self.assertTrue(Path(r["cues_json"]).is_file())
        self.assertFalse(list((self.proj / "legendas").glob("só prévia.mp4")))
        self.assertIn("contraste", r["conferencia"])

    def test_17_cues_corrigidas_sao_queimadas_como_estao(self):
        r0 = legendar.legendar(self.base, self.arq_palavras, self.proj / "legendas" / "corrigido.mp4", projeto=self.proj)
        doc, _ = cues.editar(json.loads(Path(r0["cues_json"]).read_text(encoding="utf-8")), self.d, 1, palavra=2, para="imposto")
        cues.gravar(doc, self.proj / "legendas", "corrigido")
        with self.assertRaises(comum.Erro) as cm:                               # sem --cues, apagaria a correção
            legendar.legendar(self.base, self.arq_palavras, self.proj / "legendas" / "corrigido.mp4", projeto=self.proj)
        self.assertIn("corrigido à mão", cm.exception.mensagem)
        r = legendar.legendar(self.base, None, self.proj / "legendas" / "corrigido.mp4", cues=r0["cues_json"], projeto=self.proj)
        self.assertTrue(self.da.ler_carimbo(r["saida"])["parametros"]["editado"])
        gravado = json.loads(Path(r["cues_json"]).read_text(encoding="utf-8"))
        self.assertEqual(gravado["cues"][0]["palavras"][1]["w"], "imposto")     # o arquivo corrigido não foi regravado
        for errado in (dict(formato="540x960"), dict(inicio=0.5), dict(plataforma="shorts")):
            with self.assertRaises(comum.Erro, msg=str(errado)):
                legendar.legendar(self.base, None, self.proj / "legendas" / "corrigido.mp4", cues=r0["cues_json"], projeto=self.proj, **errado)
        r = legendar.legendar(self.base, self.arq_palavras, self.proj / "legendas" / "corrigido.mp4", refazer_cues=True, projeto=self.proj)
        self.assertFalse(json.loads(Path(r["cues_json"]).read_text(encoding="utf-8"))["editado"])

    def test_20_trecho_nunca_grava_com_o_nome_do_video_inteiro(self):
        """Regressão (alta): `--inicio/--fim --previa` sem `--nome` gravava legendas/<vídeo>.srt — o arquivo que a
        video-publicacao envia como legenda do vídeo inteiro."""
        inteiro = cues.gerar(self.arq_palavras, projeto=self.proj, video=self.base, nome="base vertical")
        srt = inteiro["arquivos"]["srt"]
        antes = srt.read_text(encoding="utf-8")
        r = legendar.legendar(self.base, self.arq_palavras, inicio=1.0, fim=2.5, previa=1, sem_contraste=True, projeto=self.proj)
        self.assertEqual(r["nome"], "base vertical 1-2.5s")
        self.assertEqual(Path(r["srt"]).name, "base vertical 1-2.5s.srt")
        self.assertEqual(Path(r["previa"]).name, "_previa_base vertical 1-2.5s.png")
        self.assertEqual(json.loads(Path(r["cues_json"]).read_text(encoding="utf-8"))["origem"], "bruto/base vertical.mp4#t=1.000,2.500")
        self.assertEqual(srt.read_text(encoding="utf-8"), antes)               # a legenda do vídeo inteiro não foi tocada
        for kwargs in (dict(saida=self.proj / "legendas" / "base vertical.mp4"), dict(previa=1, nome="base vertical"), dict(previa=1, nome="fala")):
            with self.assertRaises(comum.Erro, msg=str(kwargs)) as cm:          # nome do vídeo ou da transcrição: reservado ao inteiro
                legendar.legendar(self.base, self.arq_palavras, inicio=1.0, fim=2.5, projeto=self.proj, **kwargs)
            self.assertEqual(cm.exception.codigo, 64)
            self.assertIn("INTEIRO", cm.exception.mensagem)
        self.assertEqual(srt.read_text(encoding="utf-8"), antes)
        self.assertFalse((self.proj / "legendas" / "base vertical.mp4").exists())
        cli = apoio.rodar("legendar.py", "--video", "bruto/base vertical.mp4", "--palavras", "transcricao/fala.palavras.json", "--inicio", "1", "--fim", "2.5",
                          "--previa", "1", "--sem-contraste", cwd=self.proj)
        self.assertEqual(cli.returncode, 0, cli.stderr)
        self.assertIn("legendas/base vertical 1-2.5s.cues.json", cli.stdout)

    def test_21_queimar_cues_corrigidas_de_um_trecho_atualiza_a_origem(self):
        """Regressão: no fluxo prévia → editar → `--cues`, `origem` continuava «vídeo#t=início,fim» em vez do vídeo legendado."""
        r0 = legendar.legendar(self.base, self.arq_palavras, inicio=1.0, fim=2.5, previa=1, nome="K07", sem_contraste=True, projeto=self.proj)
        arq = Path(r0["cues_json"])
        self.assertEqual(json.loads(arq.read_text(encoding="utf-8"))["origem"], "bruto/base vertical.mp4#t=1.000,2.500")
        doc, _ = cues.editar(json.loads(arq.read_text(encoding="utf-8")), self.d, 1, destacar=[1])
        cues.gravar(doc, arq.parent, "K07")
        faixa = legendar.legendar(self.base, None, self.proj / "legendas" / "K07 faixa.webm", cues=arq, so_overlay=True, sem_contraste=True, projeto=self.proj)
        self.assertIn("#t=", json.loads(arq.read_text(encoding="utf-8"))["origem"])            # faixa com alfa não é o vídeo legendado
        self.assertTrue(Path(faixa["saida"]).is_file())
        r = legendar.legendar(self.base, None, self.proj / "cortes" / "K07.mp4", cues=arq, sem_contraste=True, projeto=self.proj)
        gravado = json.loads(arq.read_text(encoding="utf-8"))
        self.assertEqual(gravado["origem"], "cortes/K07.mp4")
        self.assertEqual(gravado["fonte"], {"video": "bruto/base vertical.mp4", "inicio": 1.0, "fim": 2.5})
        self.assertTrue(gravado["editado"])
        self.assertTrue(gravado["cues"][0]["palavras"][0]["destaque"])          # a correção continua lá
        self.assertEqual(self.da.ler_carimbo(r["saida"])["parametros"]["cues_sha256"], comum.sha256_arquivo(arq))
        self.assertEqual(Path(r["srt_ao_lado"]), self.proj / "cortes" / "K07.srt")
        self.assertTrue(self.da.conferir_carimbo([r["saida"]], da=str(self.proj))["ok"])

    def test_22_formato_sem_faixa_reservada_avisa(self):
        """Regressão: queimar no horizontal não dizia que, por padrão, a DA põe GC e crédito no lugar da legenda."""
        proj = apoio.projeto(self.raiz, "dossie", nome="projeto reserva")
        arq = apoio.gravar_palavras(proj, palavras_curtas())
        deitado = apoio.video_sintetico(proj, "deitado", 640, 360, 2.0, 30, audio=False)
        em_pe = apoio.video_sintetico(proj, "em pé", 360, 640, 2.0, 30, audio=False)
        r = legendar.legendar(deitado, arq, previa=1, sem_contraste=True, projeto=proj)
        self.assertFalse(r["conferencia"]["zona"]["faixa_reservada"])
        aviso = [a for a in r["avisos"] if "legenda.reservar_em" in a]
        self.assertEqual(len(aviso), 1, r["avisos"])
        self.assertIn('"horizontal"', aviso[0])
        r = legendar.legendar(em_pe, arq, previa=1, sem_contraste=True, projeto=proj)
        self.assertTrue(r["conferencia"]["zona"]["faixa_reservada"])
        self.assertFalse([a for a in r["avisos"] if "reservar_em" in a], r["avisos"])
        da_json = proj / "da" / "da.json"                                       # a DA passa a reservar o horizontal: o aviso some
        dados = json.loads(da_json.read_text(encoding="utf-8"))
        dados["legenda"]["reservar_em"] = ["vertical", "quadrado", "horizontal"]
        da_json.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
        r = legendar.legendar(deitado, arq, previa=1, sem_contraste=True, refazer_cues=True, projeto=proj)
        self.assertTrue(r["conferencia"]["zona"]["faixa_reservada"])
        self.assertFalse([a for a in r["avisos"] if "reservar_em" in a], r["avisos"])
        self.assertEqual((r["conferencia"]["zona"]["fora_da_faixa"], r["conferencia"]["zona"]["linhas_refeitas"]), ([], []))

    def test_23_previa_zero_e_escala_zero_sao_erro_de_uso(self):
        """Regressão: `--previa 0` caía em «faltou a saída» e `--escala 0` renderizava em tamanho cheio."""
        for kwargs, trecho in ((dict(previa=0, nome="p0"), "--previa 0"), (dict(saida=self.proj / "legendas" / "e0.mp4", escala=0), "--escala"),
                               (dict(previa=1, nome="e0", escala=0.0), "--escala")):
            with self.assertRaises(comum.Erro, msg=str(kwargs)) as cm:
                legendar.legendar(self.base, self.arq_palavras, projeto=self.proj, **kwargs)
            self.assertEqual(cm.exception.codigo, 64, kwargs)
            self.assertIn(trecho, cm.exception.mensagem)
        self.assertFalse((self.proj / "legendas" / "e0.mp4").exists())
        cli = apoio.rodar("legendar.py", "--video", "bruto/base vertical.mp4", "--palavras", "transcricao/fala.palavras.json", "--previa", "0", cwd=self.proj)
        self.assertEqual(cli.returncode, 64, cli.stderr)
        self.assertIn("pelo menos 1 quadro", cli.stderr)

    def test_26_quadros_de_conferencia_entram_na_fila_uma_vez_so(self):
        """Regressão: cada quadro da conferência de contraste pedia a trava de novo (16 esperas com a fila disputada)."""
        _, _, video, trava = comum.kit()
        vistos, original = [], video.extrair_quadro

        def espiao(*a, **k):
            vistos.append(trava.sob_trava())
            return original(*a, **k)
        pasta = self.proj / "legendas" / "_png" / "_teste_quadros"
        pasta.mkdir(parents=True, exist_ok=True)
        video.extrair_quadro = espiao
        try:
            arqs = legendar._quadros_da_base(self.base, [0.5, 1.0, 1.5, 2.0], None, pasta, 160, "teste")
        finally:
            video.extrair_quadro = original
        self.assertEqual(len(arqs), 4)
        self.assertTrue(all(a.is_file() for a in arqs))
        self.assertEqual(len(set(vistos)), 1, vistos)                           # os quatro quadros sob a MESMA trava…
        self.assertIsNotNone(vistos[0])                                         # …já tomada antes do primeiro
        self.assertIsNone(trava.sob_trava())                                    # e solta no fim
        import shutil
        shutil.rmtree(pasta.parent, ignore_errors=True)

    def test_18_erros_de_uso(self):
        saida = self.proj / "legendas" / "x.mp4"
        for kwargs, trecho in ((dict(video=self.proj / "não existe.mp4", palavras=self.arq_palavras, saida=saida), "não encontrado"),
                               (dict(video=self.base, palavras=self.arq_palavras, saida=self.base), "próprio vídeo"),
                               (dict(video=self.base, palavras=self.arq_palavras), "saída"),
                               (dict(video=self.base, saida=saida), "palavras"),
                               (dict(video=self.base, palavras=self.arq_palavras, saida=saida.with_suffix(".avi")), ".mp4"),
                               (dict(video=self.base, palavras=self.arq_palavras, saida=saida, enquadramento="zoom"), "enquadramento"),
                               (dict(video=self.base, palavras=self.arq_palavras, saida=saida, inicio=9), "depois do fim"),
                               (dict(video=self.base, palavras=self.arq_palavras, saida=saida, opcao_inexistente=1), "desconhecida")):
            with self.assertRaises(comum.Erro, msg=trecho) as cm:
                legendar.legendar(projeto=self.proj, **kwargs)
            self.assertIn(trecho, cm.exception.mensagem)
        self.assertFalse(saida.exists())
        with self.assertRaises(self.da.SemDA):
            sem = self.raiz / "sem direção"
            sem.mkdir(exist_ok=True)
            legendar.legendar(self.base, self.arq_palavras, sem / "x.mp4", projeto=sem)

    def test_19_cli(self):
        r = apoio.rodar("legendar.py", "--video", "bruto/base vertical.mp4", "--palavras", "transcricao/fala.palavras.json",
                        "--saida", "legendas/pela cli ção.mp4", "--json", cwd=self.proj)
        self.assertEqual(r.returncode, 0, r.stderr)
        dados = json.loads(r.stdout)
        self.assertTrue(Path(dados["saida"]).is_file())
        self.assertEqual(dados["cues"], len(self.doc["cues"]))
        r = apoio.rodar("legendar.py", "--video", "bruto/base vertical.mp4", "--palavras", "transcricao/fala.palavras.json", "--previa", "2", cwd=self.proj)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("prévia legendas/_previa_base vertical.png", r.stdout)
        self.assertIn("zona segura: todos os", r.stdout)
        r = apoio.rodar("legendar.py", "--palavras", "transcricao/fala.palavras.json", "--saida", "x.mp4", cwd=self.proj)
        self.assertEqual(r.returncode, 64)
        self.assertIn("faltam argumentos obrigatórios: --video", r.stderr)
        r = apoio.rodar("legendar.py", "--video", "bruto/base vertical.mp4", "--palavras", "transcricao/fala.palavras.json", "--saida", "x.mp4", "--foco", "2,3", cwd=self.proj)
        self.assertEqual(r.returncode, 64)
        r = apoio.rodar("legendar.py", "--help", cwd=self.proj)
        self.assertEqual(r.returncode, 0)
        self.assertIn("uso: legendar.py", r.stdout)
        self.assertIn("--so-overlay", r.stdout)
        sem = self.raiz / "sem direção cli"
        sem.mkdir(exist_ok=True)
        r = apoio.rodar("legendar.py", "--video", self.base, "--palavras", self.arq_palavras, "--saida", sem / "x.mp4", "--projeto", sem, cwd=sem)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("video-direcao-de-arte", r.stderr)
        self.assertNotIn("Traceback", r.stderr)


class TestFormatoNoCarimbo(Base):
    def test_24_video_720p_nao_e_carimbado_como_thumbnail(self):
        """O kit dá ao quadro 1280×720 o nome do formato `thumbnail` (mesmas dimensões); a legenda carimba `1280x720`."""
        proj = apoio.projeto(self.raiz, "lab-ia", nome="formato 720p")
        base = apoio.video_sintetico(proj, "h720", 1280, 720, 1.0, 30, audio=False)
        arq = apoio.gravar_palavras(proj, palavras_curtas())
        r = legendar.legendar(base, arq, proj / "legendas" / "h720.mp4", sem_contraste=True, projeto=proj)
        c = self.da.ler_carimbo(r["saida"])
        self.assertEqual((r["formato"], c["formato"]), ("1280x720", "1280x720"))
        self.assertEqual(c["ferramenta"], "video-legendas")
        self.assertEqual(c["parametros"]["cues_json"], "legendas/h720.cues.json")           # os parâmetros sobrevivem ao acerto
        self.assertEqual(sorted(i["arquivo"] for i in c["insumos"]), ["h720.cues.json", "h720.mp4"])
        self.assertTrue(self.da.conferir_carimbo([r["saida"]], da=str(proj))["ok"])
        vertical = legendar.legendar(base, arq, proj / "legendas" / "v.mp4", formato="vertical", escala=0.25, sem_contraste=True, projeto=proj)
        self.assertEqual(self.da.ler_carimbo(vertical["saida"])["formato"], "270x480")


class TestDAMudou(Base):
    """As cues são medidas com a DA: se ela muda depois, `--cues` avisa (tamanho) ou recusa (estilo)."""

    def test_25_cues_velhas_avisam_e_estilo_trocado_e_erro(self):
        proj = apoio.projeto(self.raiz, "lab-ia", nome="da que muda")
        base = apoio.video_sintetico(proj, "base", 360, 640, 3.0, 30, audio=False)
        arq = apoio.gravar_palavras(proj, palavras_curtas())
        r = legendar.legendar(base, arq, previa=1, nome="corte", sem_contraste=True, projeto=proj)
        self.assertFalse([a for a in r["avisos"] if "direção de arte mudou" in a])
        da_json = proj / "da" / "da.json"
        dados = json.loads(da_json.read_text(encoding="utf-8"))
        dados["legenda"]["tamanho"] = 0.07
        da_json.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
        r2 = legendar.legendar(base, None, proj / "legendas" / "corte.mp4", cues=r["cues_json"], sem_contraste=True, projeto=proj)
        self.assertTrue([a for a in r2["avisos"] if "direção de arte mudou" in a], r2["avisos"])
        self.assertTrue(r2["conferencia"]["zona"]["ok"])                        # mesmo com cues velhas, nada sai da zona (o kit encolhe)
        self.assertEqual(self.da.ler_carimbo(r2["saida"])["da_sha256"], self.da.carregar(str(proj)).sha256)     # carimbo com a DA de agora
        dados["legenda"]["estilo"] = "palavra"
        da_json.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
        with self.assertRaises(comum.Erro) as cm:
            legendar.legendar(base, None, proj / "legendas" / "corte.mp4", cues=r["cues_json"], sem_contraste=True, projeto=proj)
        self.assertIn("estilo", cm.exception.mensagem)


class TestContraste(Base):
    """Legenda clara sobre vídeo claro: avisa quando a DA não protege a letra, e não avisa quando protege."""

    def medir(self, nome, **legenda):
        proj = apoio.projeto(self.raiz, "lab-ia", nome=nome, **legenda)
        base = apoio.video_sintetico(proj, "claro", 360, 640, 2.0, 30, token="texto", audio=False)      # fundo da cor do próprio texto
        arq = apoio.gravar_palavras(proj, palavras_curtas())
        return legendar.legendar(base, arq, previa=2, fim=2.0, projeto=proj)

    def test_30_sem_contorno_nem_caixa_o_aviso_sugere_token(self):
        r = self.medir("contraste nu", fundo=None, contorno=None, sombra=None)
        c = r["conferencia"]["contraste"]
        self.assertFalse(c["ok"])
        self.assertLess(c["pior"], 1.5)
        self.assertGreaterEqual(len(c["trechos"]), 1)
        texto_avisos = "\n".join(r["avisos"])
        self.assertIn("contraste ruim", texto_avisos)
        self.assertIn("legenda.contorno", texto_avisos)
        self.assertIn("legenda.fundo", texto_avisos)
        self.assertIn("revisar", texto_avisos)                                  # o caminho é uma revisão da DA
        self.assertNotRegex(texto_avisos, r"#[0-9A-Fa-f]{3,8}\b")               # nunca cor literal
        self.assertNotRegex(texto_avisos, r"rgb\(")
        proj = self.raiz / "contraste nu"                                       # --estrito transforma o aviso em código de saída 1 (para automação)
        cli = apoio.rodar("legendar.py", "--video", "bruto/claro.mp4", "--palavras", "transcricao/fala.palavras.json", "--previa", "2", "--fim", "2",
                          "--estrito", cwd=proj)
        self.assertEqual(cli.returncode, 1, cli.stderr)
        self.assertIn("reprovado (--estrito)", cli.stderr)
        self.assertIn("contraste ruim", cli.stdout)

    def test_31_caixa_de_fundo_da_da_segura_a_leitura(self):
        r = self.medir("contraste com caixa")
        c = r["conferencia"]["contraste"]
        self.assertTrue(c["ok"], c)                                             # nenhum trecho ruim…
        self.assertEqual(c["trechos"], [])
        self.assertGreaterEqual(min(i["contraste"]["cor"] for i in c["itens"]), legendar.CONTRASTE_BOM)
        self.assertFalse([a for a in r["avisos"] if "contraste ruim" in a])
        # …mas a cor das palavras já ditas (texto_suave), mais fraca, fica no limite sobre vídeo claro: o aviso nomeia o token
        if c["atencao"]:
            self.assertIn("legenda.cor_falada", "\n".join(r["avisos"]))

    def test_32_caixa_transparente_demais_pede_o_token_alfa(self):
        r = self.medir("contraste caixa fraca", fundo={"cor": "fundo", "alfa": 0.2, "raio": 0.2, "respiro": [0.4, 0.2]})
        self.assertFalse(r["conferencia"]["contraste"]["ok"])
        self.assertIn("legenda.fundo.alfa", "\n".join(r["avisos"]))

    def test_33_contorno_grosso_isola_a_letra(self):
        r = self.medir("contraste contorno", fundo=None, contorno={"cor": "fundo", "espessura": 0.1})
        self.assertTrue(r["conferencia"]["contraste"]["ok"])

    def test_34_funcao_pura(self):
        from PIL import Image
        proj = apoio.projeto(self.raiz, "lab-ia", nome="contraste puro", fundo=None, contorno=None, sombra=None)
        d = self.da.carregar(str(proj))
        escuro, claro = Image.new("RGB", (90, 160), d.rgb("fundo")), Image.new("RGB", (90, 160), d.rgb("texto"))
        r = legendar.conferir_contraste(d, [{"t": 0.5, "cue": 1, "quadro": escuro, "caixa": (60, 600, 300, 660)},
                                            {"t": 1.5, "cue": 2, "quadro": claro, "caixa": (60, 600, 300, 660)},
                                            {"t": 2.5, "cue": 3, "quadro": claro, "caixa": (60, 600, 300, 660)}], 360, 640, "karaoke")
        self.assertEqual([i["nivel"] for i in r["itens"]], ["ok", "ruim", "ruim"])
        self.assertEqual(r["trechos"], [{"t0": 1.5, "t1": 2.5, "pior": r["itens"][1]["pior"], "fundo_video": r["itens"][1]["fundo_video"]}])
        self.assertAlmostEqual(r["itens"][0]["contraste"]["cor"], round(d.contraste("texto", "fundo"), 2), delta=0.05)
        self.assertEqual(r["carregado"], [])                                    # fundo liso não é "carregado"
        listras = Image.new("RGB", (90, 160), d.rgb("fundo"))                   # texto claro sobre escuro atrás da legenda (um GC do próprio vídeo)
        for y in range(150, 166, 4):
            listras.paste(d.rgb("texto"), (0, y, 90, y + 2))
        r = legendar.conferir_contraste(d, [{"t": 0.5, "cue": 1, "quadro": listras, "caixa": (60, 600, 300, 660)}], 360, 640, "karaoke")
        self.assertEqual(r["carregado"], [0.5])


if __name__ == "__main__":
    unittest.main()
