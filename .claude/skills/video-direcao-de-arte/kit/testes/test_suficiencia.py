#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Regressões da API de que as skills irmãs dependem (decisões D10–D17): texto.py × motor, legenda na zona segura,
quadros PIL → vídeo, N cues numa passada, transições, proveniência, intermediários, plataformas e peças do kit.

Rodar a partir do kit:  python3 -m unittest testes.test_suficiencia -v
Tudo acontece numa pasta temporária com espaço e acento e VIDEO_OPS_HOME isolado. Os vídeos são minúsculos
(≤ 320×180; o maior tem 10 s porque a decisão D12 pede 60 cues em 10 s) e passam pela trava global de verdade; os dois
testes que provocam travamento usam um arquivo de trava privado e prazos de 2 s.
"""
from __future__ import annotations

import inspect
import json
import os
import shutil
import stat
import sys
import tempfile
import time
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent
if str(KIT) not in sys.path:
    sys.path.insert(0, str(KIT))
import da  # noqa: E402
import da_ext_motor as motor  # noqa: E402
import texto  # noqa: E402
import trava  # noqa: E402
import video  # noqa: E402

PRESETS = ("dossie", "lab-ia", "editorial-claro", "neon-shorts", "quadro-negro")


def editar(da_json: Path, fn) -> None:
    dados = json.loads(da_json.read_text(encoding="utf-8"))
    fn(dados)
    da_json.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")


def caixas_opacas(img, cor_rgb, limiar=200, folga=40):
    """(bbox de tudo o que é opaco, bbox dos pixels opacos na cor dada) — para medir contorno em px."""
    import numpy as np
    a = np.array(img.convert("RGBA"))
    op = a[..., 3] > limiar
    ys, xs = np.where(op)
    tudo = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
    r, g, b = cor_rgb
    m = op & (abs(a[..., 0].astype(int) - r) < folga) & (abs(a[..., 1].astype(int) - g) < folga) & (abs(a[..., 2].astype(int) - b) < folga)
    ys, xs = np.where(m)
    return tudo, (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = Path(tempfile.mkdtemp(prefix="da suficiência é ")).resolve()
        cls._env = {k: os.environ.get(k) for k in ("VIDEO_OPS_HOME", "DA_JSON", "VIDEO_OPS_TRAVA_ARQUIVO")}
        os.environ["VIDEO_OPS_HOME"] = str(cls.base / "video ops home")
        os.environ.pop("DA_JSON", None)
        cls._cwd = os.getcwd()
        cls.projetos = {}

    @classmethod
    def tearDownClass(cls):
        os.chdir(cls._cwd)
        for k, v in cls._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(cls.base, ignore_errors=True)

    @classmethod
    def projeto(cls, preset="dossie", sufixo="") -> Path:
        chave = preset + sufixo
        if chave not in cls.projetos:
            pasta = cls.base / f"projeto {chave} ção"
            da.iniciar(pasta, nome=f"Suficiência {chave}", base=preset)
            cls.projetos[chave] = pasta
        return cls.projetos[chave]


# ══════════════════════════════════════════════════════════ texto.py (D10, D11) ══
class TesteTexto(Base):
    def test_01_legenda_do_vertical_fica_dentro_da_zona_uniao_nos_cinco_presets(self):
        """Era: desenhar_linha centrava no QUADRO e passava 93 px da margem direita da zona; sem x, sem y, uma linha só."""
        L, A = 1080, 1920
        cues = (["dinheiro", "público", "desaparece"], ["A", "conta", "que", "não"], ["Brasília"],
                ["inconstitucionalissimamente", "falando"], ["para", "onde", "vai", "o", "dinheiro", "de", "Brasília"])
        for preset in PRESETS:
            d = da.carregar(self.projeto(preset))
            z = d.margens("vertical")
            est, dest = texto.Estilo.legenda(d, L, A), texto.Estilo.legenda(d, L, A, destaque=True)
            for cue in cues:
                with self.subTest(preset=preset, cue=" ".join(cue)):
                    estilos = [dest if i == 1 else est for i in range(len(cue))]
                    img, info = texto.compor_legenda(cue, estilos, d, L, A)
                    self.assertEqual(img.size, (L, A))
                    x0, y0, x1, y1 = info["caixa"]
                    self.assertTrue(info["dentro_da_zona"], info["caixa"])
                    self.assertGreaterEqual(x0, z["x0"] - 0.5); self.assertLessEqual(x1, z["x1"] + 0.5)
                    self.assertGreaterEqual(y0, z["y0"] - 0.5); self.assertLessEqual(y1, z["y1"] + 0.5)
                    self.assertAlmostEqual((x0 + x1) / 2, (z["x0"] + z["x1"]) / 2, delta=1.0)        # centro do RETÂNGULO da zona
                    self.assertLessEqual(len(info["linhas"]), d["legenda"]["max_linhas"])
                    self.assertEqual(sum(len(l) for l in info["linhas"]), len(cue))
                    tinta = img.getbbox()                                                            # o que foi pintado (sem a sombra difusa) fica na zona
                    self.assertGreaterEqual(tinta[0], z["x0"] - 12); self.assertLessEqual(tinta[2], z["x1"] + 12)
        d = da.carregar(self.projeto("dossie"))
        est = texto.Estilo.legenda(d, L, A)
        # três palavras que não cabem numa linha da zona: quebra em duas ANTES de encolher
        _, info = texto.compor_legenda(["dinheiro", "público", "desaparece"], est, d, L, A)
        self.assertEqual((len(info["linhas"]), info["encolheu"]), (2, False))
        # desenhar_linha continua existindo (uma linha só), agora dentro da zona; x e y deslocam o centro
        _, uma = texto.desenhar_linha(["dinheiro", "público", "desaparece"], est, d, L, A)
        self.assertTrue(uma["dentro_da_zona"] and uma["encolheu"] and len(uma["linhas"]) == 1)
        _, sub = texto.compor_legenda(["A", "conta"], est, d, L, A, x=300, y=500)
        self.assertAlmostEqual((sub["caixa"][0] + sub["caixa"][2]) / 2, 300, delta=1)
        self.assertAlmostEqual((sub["caixa"][1] + sub["caixa"][3]) / 2, 500, delta=1)
        _, canto = texto.compor_legenda(["A", "conta"], est, d, L, A, x=5000, y=5000)                 # pedido fora: empurrado para dentro
        self.assertTrue(canto["dentro_da_zona"])
        # plataforma por nome canônico/apelido; 'quadro' = sem zona
        _, tk = texto.compor_legenda(["A", "conta"], est, d, L, A, plataforma="tiktok")
        self.assertEqual(tk["zona"]["plataforma"], "tiktok")
        _, rl = texto.compor_legenda(["A", "conta"], est, d, L, A, plataforma="reels")
        self.assertEqual(rl["zona"]["plataforma"], "instagram")
        _, qd = texto.compor_legenda(["A", "conta"], est, d, L, A, plataforma="quadro")
        self.assertAlmostEqual((qd["caixa"][0] + qd["caixa"][2]) / 2, L / 2, delta=1)
        # recortar=True devolve o PNG pequeno + onde colar (o formato que video.compor_cues recebe)
        rec, inf = texto.compor_legenda(["A", "conta"], est, d, L, A, recortar=True)
        self.assertLess(rec.width, L // 2)
        self.assertEqual((inf["x"], inf["y"]), inf["bbox"][:2])
        # horizontal: zona simétrica, a legenda fica no centro do quadro como antes
        _, h = texto.compor_legenda(["A", "conta", "que", "não"], texto.Estilo.legenda(d, 1920, 1080), d, 1920, 1080)
        self.assertAlmostEqual((h["caixa"][0] + h["caixa"][2]) / 2, 960, delta=1)

    def test_02_o_vao_entre_palavras_e_o_espaco_da_fonte_e_a_linha_mede_como_o_texto_corrido(self):
        """Era: vão fixo de 0,28 em somado à largura da TINTA (com contorno) de cada palavra: 23–36 % mais larga."""
        for preset in PRESETS:
            with self.subTest(preset=preset):
                d = da.carregar(self.projeto(preset))
                est = texto.Estilo.legenda(d, 1920, 1080)
                f = est.fonte()
                esperado = (f.getlength(" ") + 2 * est.tracking * est.tamanho) * est.escala_x
                self.assertAlmostEqual(texto.vao_entre_palavras(est), esperado, places=3)
                palavras = ["A", "conta", "que", "não", "fecha"]
                _, info = texto.compor_legenda(palavras, est, d, 1920, 1080, max_linhas=1, plataforma="quadro", largura_max=1900)
                corrido = texto.largura_texto(" ".join(palavras), est)
                bloco = info["caixa_texto"][2] - info["caixa_texto"][0]
                self.assertLess(abs(bloco - corrido) / corrido, 0.03, f"{preset}: bloco {bloco:.1f} × corrido {corrido:.1f}")
                vaos = [b["x0"] - a["x1"] for a, b in zip(info["palavras"], info["palavras"][1:])]
                for v in vaos:
                    self.assertAlmostEqual(v, esperado, delta=0.05)

    def test_03_contorno_e_espessura_externa_e_a_caixa_de_fundo_e_uma_so(self):
        d = da.carregar(self.projeto("dossie"))                    # contorno 0,11 × 67 px = 7 px para fora (5 na horizontal: escala_x 0,7)
        est = texto.Estilo.legenda(d, 1920, 1080)
        img, info = texto.compor_legenda(["HIH"], est, d, 1920, 1080)
        tudo, miolo = caixas_opacas(img, d.rgb("texto"))
        esp = round(d["legenda"]["contorno"]["espessura"] * est.tamanho)
        self.assertEqual(info["contorno_px"], esp)
        for lado, medido, alvo in (("topo", miolo[1] - tudo[1], esp), ("base", tudo[3] - miolo[3], esp),
                                   ("esquerda", miolo[0] - tudo[0], esp * est.escala_x), ("direita", tudo[2] - miolo[2], esp * est.escala_x)):
            self.assertAlmostEqual(medido, alvo, delta=1.0, msg=f"contorno {lado}: {medido} px, esperado {alvo:.1f}")
        # lab-ia: caixa de fundo ÚNICA para o bloco (o vão entre as palavras é caixa, não transparência)
        d2 = da.carregar(self.projeto("lab-ia"))
        e2 = texto.Estilo.legenda(d2, 1920, 1080)
        img2, inf2 = texto.compor_legenda(["A", "conta", "fecha"], e2, d2, 1920, 1080)
        a, b = inf2["palavras"][0], inf2["palavras"][1]
        meio = (int((a["x1"] + b["x0"]) / 2), int((a["y0"] + a["y1"]) / 2))
        self.assertGreater(img2.getpixel(meio)[3], 150, "o vão entre duas palavras deveria ser a caixa de fundo")
        respiro = d2["legenda"]["fundo"]["respiro"]
        self.assertAlmostEqual(inf2["caixa"][3] - inf2["caixa"][1], e2.tamanho * e2.altura_linha + 2 * respiro[1] * e2.tamanho, delta=1.5)

    def test_04_validador_avisa_legenda_que_nao_cabe_na_zona_no_eixo_x(self):
        for preset in PRESETS:                                     # os presets declaram o teto do vertical: nenhum aviso
            self.assertEqual(da.validar(self.projeto(preset))["avisos"], [], preset)
        raiz = self.projeto("dossie", " validador")
        editar(raiz / "da" / "da.json", lambda j: j["legenda"]["posicao"]["vertical"].update(largura_max=0.8))
        avisos = da.validar(raiz)["avisos"]
        self.assertTrue(any("legenda.posicao.vertical.largura_max = 0,8" in a and "0,611" in a for a in avisos), avisos)
        editar(raiz / "da" / "da.json", lambda j: j["legenda"]["posicao"]["vertical"].pop("largura_max"))
        avisos = da.validar(raiz)["avisos"]                         # sem teto próprio vale legenda.largura_max (0,8)
        self.assertTrue(any(a.startswith("legenda.largura_max = 0,8") and "'uniao'" in a for a in avisos), avisos)
        editar(raiz / "da" / "da.json", lambda j: j["legenda"]["posicao"]["vertical"].update(largura_max=0.5, x=0.7))
        avisos = da.validar(raiz)["avisos"]
        self.assertTrue(any("legenda.posicao.vertical.x = 0,7" in a for a in avisos), avisos)
        editar(raiz / "da" / "da.json", lambda j: j["legenda"]["posicao"]["vertical"].update(x=0.4))
        self.assertEqual(da.validar(raiz)["avisos"], [])
        d = da.carregar(raiz)                                       # x da DA é respeitado por compor_legenda
        _, info = texto.compor_legenda(["A", "conta"], texto.Estilo.legenda(d, 1080, 1920), d, 1080, 1920)
        self.assertAlmostEqual((info["caixa"][0] + info["caixa"][2]) / 2, 0.4 * 1080, delta=1)

    def test_05_exemplos_dos_docstrings_e_sinonimo_da(self):
        """Era: est.com(cor="primaria") e folha_de_contato(..., da=d) dos docstrings levantavam erro."""
        from PIL import Image
        d = da.carregar(self.projeto("dossie"))
        L, A = 1080, 1920
        est = texto.Estilo.legenda(d, L, A)
        dest = texto.Estilo.legenda(d, L, A, destaque=True)
        img, info = texto.compor_legenda(["A", "conta", "que", "não", "fecha"], [est, dest, est, est, est], d, L, A)
        self.assertTrue(info["dentro_da_zona"])
        est2 = texto.Estilo.do_papel(d, "titulo", tamanho_px=92, cor="texto", contorno=("fundo", 0.06))
        bloco, _ = texto.desenhar("A conta que não fecha", est2, largura_max=860)
        self.assertLessEqual(bloco.width, 860 + 20)
        bloco, inf = texto.compor_bloco(["A", "CONTA", "NÃO", "FECHA"], [est2, est2.com(cor="primaria"), est2, est2], largura_max=860)
        self.assertEqual(est2.com(cor="primaria").cor, d.rgba("primaria"))
        self.assertEqual(texto.Estilo.legenda(d, L, A, falada=True).cor, d.rgba(d["legenda"].get("cor_falada") or d["legenda"]["cor"]))
        th, thd = texto.Estilo.thumbnail(d), texto.Estilo.thumbnail(d, destaque=True)
        self.assertEqual((th.cor, thd.cor), (d.rgba(d["thumbnail"]["cor"]), d.rgba(d["thumbnail"]["cor_destaque"])))
        titulo, inf = texto.compor_bloco(["A", "CONTA", "NÃO", "FECHA"], [th, th, th, thd], largura_max=700, max_linhas=3, alinhamento="esquerda")
        self.assertLessEqual(inf["caixa"][2] - inf["caixa"][0], 700.5)
        self.assertGreater(len(inf["linhas"]), 1)
        # video.py: `da=` é sinônimo de `da_obj=` em tudo o que carimba ou desenha
        for fn in (video.folha_de_contato, video.compor_overlay, video.compor_cues, video.juntar, video.encaixar_em_janela, video.Codificador.__init__):
            nomes = inspect.signature(fn).parameters
            self.assertIn("da", nomes, fn.__qualname__); self.assertIn("da_obj", nomes, fn.__qualname__)
        q = self.projeto("dossie") / "qa" / "_q.png"
        q.parent.mkdir(exist_ok=True)
        Image.new("RGB", (270, 480), d.rgb("primaria")).save(q)
        folha = video.folha_de_contato([q, q], ["um", "dois"], q.with_name("folha vertical.png"), colunas=2, largura_celula=270, da=d)
        with Image.open(folha) as f:                                 # peça vertical: célula vertical, quadro inteiro (era cortada para 16:9)
            self.assertGreater(f.height, 480)
            self.assertEqual(f.convert("RGB").getpixel((32 + 135, 32 + 10)), d.rgb("primaria"))
            self.assertEqual(f.convert("RGB").getpixel((32 + 135, 32 + 470)), d.rgb("primaria"))
        folha2 = video.folha_de_contato([q], ["um"], q.with_name("folha 16x9.png"), colunas=1, largura_celula=320, da_obj=d, proporcao="16:9")
        with Image.open(folha2) as f:                                # proporção forçada: o quadro entra inteiro, com faixas de superfície
            self.assertEqual(f.convert("RGB").getpixel((32 + 5, 32 + 90)), d.rgb("superficie"))
        self.assertIn("-r", video.args_encode(d, formato="vertical"))
        self.assertIn("30000/1001", video.args_encode(d, formato="vertical"))
        self.assertEqual(video.filtro_loudnorm(d, "curto"), "loudnorm=I=-14:TP=-1:LRA=11")

    def test_07_estados_da_legenda_nos_tres_estilos_e_kerning_com_tracking(self):
        """legenda.estilo decide os estados de uma cue (karaoke, palavra, bloco), como ctx.kit.legenda(...).seek(i) no motor."""
        L, A = 540, 960
        cue = ["dinheiro", "público", "desaparece"]
        d = da.carregar(self.projeto("dossie"))                               # karaoke: o bloco inteiro, uma palavra acesa por vez
        est = texto.estados_da_legenda(cue, d, L, A)
        self.assertEqual([i["indice"] for _, i in est], [0, 1, 2])
        self.assertEqual(len({(i["x"], i["y"], img.size) for img, i in est}), 1, "o bloco não muda de lugar nem de tamanho entre os estados")
        prim = d.rgb("primaria")
        for img, info in est:
            for k, pal in enumerate(info["palavras"]):
                rec = img.convert("RGB").crop((int(pal["x0"] - info["x"]), int(pal["y0"] - info["y"]), int(pal["x1"] - info["x"]), int(pal["y1"] - info["y"])))
                acesos = sum(n for n, c in (rec.getcolors(100000) or []) if all(abs(a - b) < 40 for a, b in zip(c, prim)))
                (self.assertGreater if k == info["indice"] else self.assertLess)(acesos, 20, f"estado {info['indice']}, palavra {k}")
        dn = da.carregar(self.projeto("neon-shorts"))                         # palavra: só a falada, todas no MESMO tamanho e no mesmo centro
        estn = texto.estados_da_legenda(cue, dn, L, A, recortar=False)
        self.assertEqual([len(i["palavras"]) for _, i in estn], [1, 1, 1])
        self.assertEqual([i["palavras"][0]["texto"] for _, i in estn], cue)
        self.assertEqual(len({round(i["tamanho"], 2) for _, i in estn}), 1)
        self.assertTrue(all(i["encolheu"] and i["dentro_da_zona"] for _, i in estn))   # "desaparece" não cabe a 0,092: a cue inteira encolhe junto
        centros = [(i["caixa"][0] + i["caixa"][2]) / 2 for _, i in estn]
        self.assertLess(max(centros) - min(centros), 1.0)
        sozinha = texto.compor_legenda(["público"], texto.Estilo.legenda(dn, L, A, destaque=True), dn, L, A)[1]
        self.assertGreater(sozinha["tamanho"], estn[1][1]["tamanho"] + 1)     # sem `apenas`, cada palavra teria o próprio tamanho
        with self.assertRaises(da.DAErro):
            texto.compor_legenda(cue, texto.Estilo.legenda(dn, L, A), dn, L, A, apenas=7)
        de = da.carregar(self.projeto("editorial-claro"))                     # bloco: um estado só
        estb = texto.estados_da_legenda(cue, de, L, A)
        self.assertEqual((len(estb), estb[0][1]["indice"], len(estb[0][1]["palavras"])), (1, None, 3))
        # escalar_estilo: tudo o que é medida acompanha (é o "pop" e o encolher em conjunto)
        e = texto.Estilo.legenda(dn, L, A)
        e2 = texto.escalar_estilo(e, 0.5)
        self.assertAlmostEqual(e2.tamanho, e.tamanho / 2); self.assertAlmostEqual(e2.contorno[1], e.contorno[1] / 2)
        self.assertAlmostEqual(e2.sombra["dy"], e.sombra["dy"] / 2); self.assertIs(texto.escalar_estilo(e, 1.0), e)
        # tracking ≠ 0 não joga fora o kerning da fonte (o navegador aplica os dois): "PA" em Montserrat 900 tem par de kerning
        from PIL import features
        if features.check("raqm"):
            f = e.fonte()
            solta = (sum(f.getlength(c) for c in "DESAPARECE") + e.tracking * e.tamanho * 9) * e.escala_x
            self.assertLess(texto.largura_texto("desaparece", e), solta - 0.5)

    def test_06_credito_de_fonte_nas_sete_posicoes_e_sem_prefixo_duplicado(self):
        d = da.carregar(self.projeto("dossie"))
        for L, A in ((1080, 1920), (1920, 1080)):
            z = d.margens("vertical" if A > L else "horizontal")
            for pos in da.esquema()["$defs"]["posicao"]["enum"]:
                with self.subTest(pos=pos, quadro=(L, A)):
                    img, info = texto.credito_fonte(d, "Tesouro Nacional, 2024", L, A, posicao=pos)
                    x0, y0, x1, y1 = info["caixa"]
                    self.assertTrue(x0 >= z["x0"] and x1 <= z["x1"] and y0 >= z["y0"] and y1 <= z["y1"], (pos, info["caixa"]))
                    if pos.endswith("centro"):
                        self.assertAlmostEqual((x0 + x1) / 2, (z["x0"] + z["x1"]) / 2, delta=1.5)
                    self.assertEqual(info["texto"], "Fonte: Tesouro Nacional, 2024")
        _, info = texto.credito_fonte(d, "Fonte: IBGE", 1920, 1080)
        self.assertEqual(info["texto"], "Fonte: IBGE")
        _, info = texto.credito_fonte(d, "IBGE", 1920, 1080, prefixo="")
        self.assertEqual(info["texto"], "IBGE")


# ══════════════════════════════════════════ núcleo: plataformas, carimbo, lint (D14–D16) ══
class TesteNucleo(Base):
    def test_10_plataformas_com_nomes_canonicos_e_acessores(self):
        dados = da.plataformas()
        self.assertEqual(tuple(dados["plataformas"]), da.PLATAFORMAS)
        for secao in ("specs", "limites_texto"):
            self.assertEqual(set(dados[secao]), set(da.PLATAFORMAS), secao)
        self.assertLessEqual({"reels", "tiktok", "shorts", "uniao"}, set(dados["margens_seguras_vertical"]))
        self.assertLessEqual(set(dados["capas"]), set(da.PLATAFORMAS))
        self.assertEqual(set(dados["thumbnail"]), {"youtube"})
        for apelido, canonico in (("instagram", "reels"), ("instagram_reels", "reels"), ("IG", "reels"), ("youtube_longo", "youtube"),
                                  ("yt", "youtube"), ("tt", "tiktok"), ("short", "shorts"), ("Reels", "reels")):
            self.assertEqual(da.nome_plataforma(apelido), canonico)
        with self.assertRaises(da.DAErro):
            da.nome_plataforma("kwai")
        self.assertEqual(da.limite("reels", "hashtags_max"), dados["limites_texto"]["reels"]["hashtags_max"])
        self.assertEqual(da.limite("instagram", "legenda_max_caracteres"), 2200)
        self.assertEqual(da.limite("youtube", "titulo_max_caracteres"), 100)
        self.assertEqual(da.limite("shorts", "hashtags_exibidas_junto_ao_titulo"), 3)              # o Short herda os campos de texto do YouTube
        self.assertEqual(da.limite("tiktok", "duracao_max_s"), dados["specs"]["tiktok"]["duracao_max_s"])
        self.assertEqual(da.limite("tiktok", "texto_max"), 2200)                                    # campo normalizado
        self.assertIsNone(da.limite("tiktok", "hashtags_max"))                                      # null = não encontrado
        self.assertIsNone(da.limite("reels", "chave_que_nao_existe"))
        self.assertEqual(da.limite("youtube", "peso_max_seguro_mb"), 2)                             # thumbnail: achado sem dizer o grupo
        self.assertIsNone(da.limite("youtube", "tamanho_max_mb", grupo="thumbnail"))                # com grupo, não devolve o teto do VÍDEO (era 262144)
        self.assertEqual(da.limite("youtube", "tamanho_max_mb", grupo="specs"), da.limite("youtube", "tamanho_max_mb"))
        ficha = da.plataforma("instagram")
        self.assertEqual((ficha["nome"], ficha["texto_max"], ficha["hashtags_max"], ficha["duracao_min_s"], ficha["tamanho_max_mb"]),
                         ("reels", 2200, 5, 3, 300))
        self.assertEqual(ficha["margens"]["topo"], 0.14)
        self.assertEqual(da.plataforma("youtube")["margens"]["topo"], 0.05)
        self.assertIn("vencida", ficha)
        dados["verificado_em"] = "1999-01-01"                                                       # é cópia: mexer nela não muda o kit
        self.assertNotEqual(da.plataformas()["verificado_em"], "1999-01-01")
        # CLI
        import contextlib, io
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(da.main(["plataformas", "instagram", "--chave", "hashtags_max"]), 0)
        self.assertEqual(out.getvalue().strip(), "5")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(da.main(["plataformas", "tiktok", "--json"]), 0)
        self.assertEqual(json.loads(out.getvalue())["nome"], "tiktok")
        # margens por nome canônico; zona de outro formato cai no padrão deste; nome inexistente é erro
        d = da.carregar(self.projeto("dossie"))
        self.assertEqual(d.margens("vertical", "reels"), d.margens("vertical", "instagram"))
        self.assertEqual(d.margens("horizontal", "uniao")["plataforma"], "padrao")
        self.assertEqual(d.margens("horizontal", "tiktok")["plataforma"], "padrao")
        self.assertEqual(d.margens("vertical", "youtube")["plataforma"], "uniao")
        with self.assertRaises(da.DAErro):
            d.margens("vertical", "kwai")
        # zona proibida da thumbnail: retângulo em frações e em px, com o tamanho de plataformas.json
        reserva = dados["thumbnail"]["youtube"]["zona_timestamp"]["reserva_recomendada"]
        self.assertEqual(da.reserva_do_timestamp(), [reserva["largura"], reserva["altura"]])
        self.assertEqual(da.esquema()["properties"]["thumbnail"]["properties"]["zona_proibida_tamanho"]["default"], da.reserva_do_timestamp())
        self.assertEqual(d.zona_proibida(), {"x": 0.75, "y": 0.78, "w": 0.25, "h": 0.22})
        self.assertEqual(d.zona_proibida("thumbnail"), {"x0": 960, "y0": 562, "x1": 1280, "y1": 720, "largura": 320, "altura": 158, "canto": "inferior_direita"})
        self.assertEqual(d.zona_proibida(1920, 1080)["largura"], 480)
        raiz = self.projeto("dossie", " zona")
        editar(raiz / "da" / "da.json", lambda j: j["thumbnail"].update(zona_proibida="superior_esquerda", zona_proibida_tamanho=[0.3, 0.2]))
        self.assertEqual(da.carregar(raiz).zona_proibida(1000, 500), {"x0": 0, "y0": 0, "x1": 300, "y1": 100, "largura": 300, "altura": 100, "canto": "superior_esquerda"})
        editar(raiz / "da" / "da.json", lambda j: j["thumbnail"].update(zona_proibida="nenhuma"))
        self.assertIsNone(da.carregar(raiz).zona_proibida("thumbnail"))
        # tokens novos têm padrão e não mexem na identidade de quem não os escreve
        self.assertEqual(d["tratamento"]["encaixe"]["modo"], "desfocado")
        self.assertEqual(d["graficos"]["citacao_fonte"]["prefixo"], "Fonte: ")
        self.assertEqual(d.transicao()["tipo"], d["movimento"]["transicoes"]["padrao"])
        with self.assertRaises(da.DAErro):
            d.transicao("empurra")                                                                  # fora de permitidas no dossiê
        with self.assertRaises(da.DAErro):
            d.transicao("quica")

    def test_11_intermediarios_com_prefixo_e_broll(self):
        """D15: _pasta/ e _arquivo não são peças; broll/bruto/ não é conferido; broll/tratado/ é, por padrão."""
        from PIL import Image
        raiz = self.projeto("dossie", " intermediarios")
        d = da.carregar(raiz)

        def png(rel):
            arq = raiz / rel
            arq.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (8, 8), d.rgb("fundo")).save(arq)
            return arq

        for rel in ("animacoes/_trabalho/quadro 1.png", "legendas/_png/cue 0.png", "render/_base.png", "thumbs/_foto bruta.png",
                    "broll/bruto/baixado.png", "legendas/_seq/0001.png"):
            png(rel)
        peca = png("render/final.png")
        tratado = png("broll/tratado/cidade.png")
        d.carimbar(peca, "teste", "8x8")
        r = da.conferir_carimbo(da=d)
        vistos = {Path(p["arquivo"]).name: p["estado"] for p in r["pecas"]}
        self.assertEqual(vistos, {"final.png": "ok", "cidade.png": "sem_carimbo"})
        d.carimbar(tratado, "video-broll", "8x8")
        self.assertTrue(da.conferir_carimbo(da=d)["ok"])
        self.assertEqual(da.conferir_carimbo([raiz / "animacoes" / "_trabalho" / "quadro 1.png"], da=d)["pecas"][0]["estado"], "sem_carimbo")   # pelo nome, confere
        # lint: intermediário não entra na varredura da pasta (e a nota diz), mas é lido quando passado pelo nome
        rascunho = raiz / "animacoes" / "_rascunho.js"
        rascunho.write_text("el.style.color = '#FF0000';\n", encoding="utf-8")
        (raiz / "animacoes" / "_trabalho" / "teste.css").write_text("a { color: red; }\n", encoding="utf-8")
        (raiz / "animacoes" / "cena.js").write_text("export const meta = {};\n", encoding="utf-8")
        r = da.lint([raiz / "animacoes"], da=d)
        self.assertEqual((r["arquivos"], r["erros"]), (1, 0))
        self.assertTrue(any("intermediário" in n for n in r["notas"]), r["notas"])
        self.assertEqual(da.lint([rascunho], da=d)["erros"], 1)

    def test_12_proveniencia_dos_insumos_em_composicoes(self):
        """Era: overlay renderizado com --sem-auditoria (ou com outra DA) sumia na composição: o final saía 'n/a' e passava."""
        from PIL import Image
        raiz = self.projeto("dossie", " proveniencia")
        d = da.carregar(raiz)

        def png(nome, cor="primaria"):
            arq = raiz / "render" / nome
            Image.new("RGB", (16, 16), d.rgb(cor)).save(arq)
            return arq

        bruto, ok, pulado = png("_bruto.png"), png("overlay ok.png"), png("overlay pulado.png", "fundo")
        d.carimbar(ok, "motor", "16x16", auditoria="ok")
        d.carimbar(pulado, "motor", "16x16", auditoria="pulada")
        limpa = png("composta limpa.png", "texto")
        c = da.ler_json(d.carimbar(limpa, "minha-skill", "16x16", insumos=[bruto, ok]))
        self.assertEqual(c["auditoria"], "n/a")
        self.assertEqual([(i["arquivo"], i["carimbado"], i["auditoria"]) for i in c["insumos"]], [("_bruto.png", False, None), ("overlay ok.png", True, "ok")])
        self.assertEqual(c["insumos"][1]["da_sha256"], d.sha256)
        self.assertEqual(c["midia"], {"tipo": "imagem", "largura": 16, "altura": 16})
        r = da.conferir_carimbo([limpa], da=d)
        self.assertTrue(r["ok"]); self.assertIn("sem carimbo", r["pecas"][0]["detalhe"])
        suja = png("composta suja.png", "texto_suave")
        c = da.ler_json(d.carimbar(suja, "minha-skill", "16x16", insumos=[bruto, pulado]))
        self.assertEqual(c["auditoria"], "pulada")                                                  # a pior dos insumos
        p = da.conferir_carimbo([suja], da=d)["pecas"][0]
        self.assertEqual(p["estado"], "auditoria_pulada"); self.assertIn("overlay pulado.png", p["detalhe"])
        with self.assertRaises(da.DAErro):                                                          # e não se promove depois
            d.carimbar(suja, "minha-skill", "16x16", auditoria="ok")
        # cadeia: a composição da composição herda a lista (com `via`) e continua reprovada
        neta = png("neta.png", "secundaria")
        c = da.ler_json(d.carimbar(neta, "minha-skill", "16x16", insumos=[suja]))
        self.assertEqual(c["auditoria"], "pulada")
        self.assertTrue(any(i.get("via") == "composta suja.png" and i["arquivo"] == "overlay pulado.png" for i in c["insumos"]), c["insumos"])
        # insumo de OUTRA DA: muda um token (o sha muda), compõe com o overlay antigo
        editar(raiz / "da" / "da.json", lambda j: j["cor"]["paleta"].update(destaque="#12AB34"))
        d2 = da.carregar(raiz)
        self.assertNotEqual(d2.sha256, d.sha256)
        nova = png("composta nova.png", "superficie")
        d2.carimbar(nova, "minha-skill", "16x16", insumos=[ok])
        p = da.conferir_carimbo([nova], da=d2)["pecas"][0]
        self.assertEqual(p["estado"], "insumo_de_outra_da"); self.assertIn("overlay ok.png", p["detalhe"])
        # CLI: --insumo (repetível)
        import contextlib, io
        outra = png("pela cli.png", "alerta")
        d2.carimbar(pulado, "motor", "16x16", auditoria="pulada")
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            rc = da.main(["--da", str(raiz), "carimbar", str(outra), "--ferramenta", "cli", "--insumo", str(bruto), "--insumo", str(pulado)])
        self.assertEqual(rc, 0)
        self.assertIn("pulada", err.getvalue())
        self.assertEqual(da.ler_carimbo(outra)["auditoria"], "pulada")


# ═════════════════════════════════════════════ video.py com ffmpeg de verdade (D12–D14, D17) ══
class TesteVideo(Base):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.raiz = cls.projeto("dossie", " video")
        cls.d = da.carregar(cls.raiz)
        cls.tempos = {}

    @classmethod
    def tearDownClass(cls):
        if cls.tempos:
            print("\nTempos medidos (s):", json.dumps(cls.tempos, ensure_ascii=False))
        super().tearDownClass()

    def clipe(self, nome: str, dur: float, tamanho="320x180", fps="30", tom=440) -> Path:
        arq = self.raiz / "bruto" / nome
        if not arq.is_file():
            video.executar(["-f", "lavfi", "-i", f"testsrc2=size={tamanho}:rate={fps}:duration={dur}",
                            "-f", "lavfi", "-i", f"sine=frequency={tom}:sample_rate=48000:duration={dur}",
                            *video.args_encode(fps, crf=32, preset="ultrafast")], arq, rotulo="teste: clipe sintético")
        return arq

    def quadro(self, arquivo, t):
        from PIL import Image
        saida = self.raiz / "qa" / f"_q {Path(arquivo).stem} {t}.png"
        video.extrair_quadro(arquivo, t, saida)
        return Image.open(saida).convert("RGB")

    def test_20_codificador_quadros_pil_para_video_nos_tres_codecs(self):
        from PIL import Image
        d = self.d

        def quadros(n):
            for i in range(n):
                q = Image.new("RGBA", (160, 90), d.rgba("primaria", 0))
                q.paste(d.rgba("primaria"), (i * 8, 20, i * 8 + 40, 70))
                yield q

        for ext, codec, pix, alfa in ((".webm", "vp9alfa", "yuva420p", True), (".mov", "prores4444", "yuva444p12le", True), (".mp4", "h264", "yuv420p", False)):
            with self.subTest(codec=codec):
                saida = self.raiz / "animacoes" / f"peça codificada{ext}"
                t0 = time.monotonic()
                with video.Codificador(saida, largura=160, altura=90, fps="30000/1001", da_obj=d, ferramenta="teste", parametros={"cena": "barra"}) as cod:
                    for q in quadros(15):
                        cod.escrever(q)
                self.tempos[f"Codificador {codec} 15 quadros 160x90"] = round(time.monotonic() - t0, 2)
                s = video.sondar(saida)
                self.assertEqual((s["quadros"], s["largura"], s["altura"], s["pix_fmt"], s["tem_alfa"], str(s["fps"])), (15, 160, 90, pix, alfa, "30000/1001"))
                self.assertEqual(cod.resultado["codec"], codec)
                self.assertFalse(saida.with_name(f"{saida.stem}.parcial{ext}").exists())
                c = da.ler_carimbo(saida)
                self.assertEqual((c["ferramenta"], c["da_sha256"], c["auditoria"], c["formato"]), ("teste", d.sha256, "n/a", "160x90"))
                self.assertEqual((c["parametros"]["quadros"], c["parametros"]["cena"], c["midia"]["largura"]), (15, "barra", 160))
                self.assertIsNone(trava.sob_trava())
        # o alfa chega inteiro: fora do retângulo o WebM é transparente; o h264 foi achatado sobre a cor `fundo` da DA
        import subprocess
        png = self.raiz / "qa" / "_alfa.png"
        subprocess.run([video.FFMPEG, "-v", "error", "-y", "-c:v", "libvpx-vp9", "-i", str(self.raiz / "animacoes" / "peça codificada.webm"),
                        "-frames:v", "1", "-update", "1", "-pix_fmt", "rgba", str(png)], check=True, stdin=subprocess.DEVNULL)
        with Image.open(png) as im:
            self.assertEqual(im.convert("RGBA").getpixel((150, 5))[3], 0)
            self.assertGreater(im.convert("RGBA").getpixel((20, 45))[3], 250)
        r, g, b = self.quadro(self.raiz / "animacoes" / "peça codificada.mp4", 0.0).getpixel((150, 5))
        fr, fg, fb = d.rgb("fundo")
        self.assertTrue(abs(r - fr) < 12 and abs(g - fg) < 12 and abs(b - fb) < 12, (r, g, b))
        # atalho para iterável + formato da DA (tamanho e fps vêm do formato); bytes crus e numpy também valem
        res = video.codificar_quadros((Image.new("RGB", (1080, 1080), d.rgb("fundo")) for _ in range(3)), self.raiz / "animacoes" / "_q.mp4",
                                      formato="quadrado", da_obj=d, crf=40)
        self.assertEqual((res["quadros"], res["largura"], str(res["fps"])), (3, 1080, "30000/1001"))
        import numpy as np
        with video.Codificador(self.raiz / "animacoes" / "_bytes.webm", largura=64, altura=36, fps=25, da_obj=d) as cod:
            cod.escrever(bytes(64 * 36 * 4), repetir=3)
            cod.escrever(np.zeros((36, 64, 4), dtype=np.uint8))
        self.assertEqual(video.sondar(self.raiz / "animacoes" / "_bytes.webm")["quadros"], 4)
        # erros de uso antes de qualquer processo
        with self.assertRaises(da.DAErro):
            video.Codificador(self.raiz / "animacoes" / "x.webm", codec="h264")
        with self.assertRaises(da.DAErro):
            with video.Codificador(self.raiz / "animacoes" / "_impar.mp4", largura=161, altura=90, fps=30, da_obj=d) as cod:
                cod.escrever(Image.new("RGB", (161, 90)))
        with self.assertRaises(da.DAErro):                           # nenhum quadro: nada gravado
            with video.Codificador(self.raiz / "animacoes" / "_vazio.mp4", largura=160, altura=90, fps=30, da_obj=d):
                pass
        self.assertFalse((self.raiz / "animacoes" / "_vazio.mp4").exists())
        self.assertIsNone(trava.sob_trava())

    def test_21_codificador_nunca_segura_a_trava(self):
        """Exceção no meio, quadro de tamanho errado, ffmpeg que morre e ffmpeg que para de ler: a trava é solta e nada fica."""
        from PIL import Image
        d = self.d
        privado = self.base / "trava privada é.lock"
        os.environ["VIDEO_OPS_TRAVA_ARQUIVO"] = str(privado)
        ffmpeg_real = video.FFMPEG
        try:
            saida = self.raiz / "animacoes" / "abortada.webm"
            with self.assertRaises(RuntimeError):
                with video.Codificador(saida, largura=160, altura=90, fps=30, da_obj=d) as cod:
                    cod.escrever(Image.new("RGBA", (160, 90)))
                    raise RuntimeError("o produtor quebrou")
            self.assertEqual(list(saida.parent.glob("abortada*")), [])           # nem peça, nem .parcial, nem carimbo
            self.assertTrue(trava.estado()["livre"])
            with self.assertRaises(da.DAErro) as c:
                with video.Codificador(saida, largura=160, altura=90, fps=30, da_obj=d) as cod:
                    cod.escrever(Image.new("RGBA", (160, 90)))
                    cod.escrever(Image.new("RGBA", (100, 90)))
            self.assertIn("100×90", str(c.exception))
            self.assertTrue(trava.estado()["livre"])
            # ffmpeg que morre depois de ler um pouco: a escrita seguinte levanta DAErro em segundos (não fica presa)
            falso = self.base / "ffmpeg que morre.py"
            falso.write_text("#!/bin/sh\nhead -c 20000 >/dev/null\necho 'morri de propósito' >&2\nexit 9\n", encoding="utf-8")
            falso.chmod(falso.stat().st_mode | stat.S_IXUSR)
            video.FFMPEG = str(falso)
            t0 = time.monotonic()
            with self.assertRaises(da.DAErro) as c:
                with video.Codificador(saida, largura=160, altura=90, fps=30, da_obj=d) as cod:
                    for _ in range(400):
                        cod.escrever(Image.new("RGBA", (160, 90)))
            self.assertLess(time.monotonic() - t0, 20)
            self.assertIn("código 9", str(c.exception)); self.assertIn("morri de propósito", str(c.exception))
            self.assertTrue(trava.estado()["livre"])
            # ffmpeg que não lê a entrada: o vigia de inatividade (2 s aqui) mata e a escrita levanta
            parado = self.base / "ffmpeg parado.py"
            parado.write_text("#!/bin/sh\nexec sleep 60\n", encoding="utf-8")
            parado.chmod(parado.stat().st_mode | stat.S_IXUSR)
            video.FFMPEG = str(parado)
            t0 = time.monotonic()
            with self.assertRaises(da.DAErro) as c:
                with video.Codificador(saida, largura=160, altura=90, fps=30, da_obj=d, inatividade=2) as cod:
                    for _ in range(2000):
                        cod.escrever(Image.new("RGBA", (160, 90)))
            self.assertLess(time.monotonic() - t0, 25)
            self.assertIn("progresso", str(c.exception))
            self.assertTrue(trava.estado()["livre"])
            self.assertEqual(list(saida.parent.glob("abortada*")), [])
        finally:
            video.FFMPEG = ffmpeg_real
            os.environ.pop("VIDEO_OPS_TRAVA_ARQUIVO", None)
            import subprocess
            vivos = subprocess.run(["pgrep", "-f", str(self.base)], capture_output=True, text=True).stdout.split()
            self.assertEqual(vivos, [], "sobrou processo de teste vivo")

    def test_22_compor_cues_64_legendas_em_10_s_numa_passada(self):
        """Era: um reencode por estado de karaokê (compor_overlay em cadeia) ou uma entrada de ffmpeg por cue."""
        from PIL import Image
        d = self.d
        L, A = 320, 180
        # base de 10 s feita pelo próprio Codificador (quadros chapados na cor `superficie` + tom): exercita o `audio=`
        tom = self.raiz / "bruto" / "tom 10 s.wav"
        video.executar(["-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=10", "-c:a", "pcm_s16le"], tom, rotulo="teste: tom")
        base = self.raiz / "bruto" / "base lisa 10 s.mp4"
        liso = Image.new("RGB", (L, A), d.rgb("superficie"))
        res = video.codificar_quadros((liso for _ in range(300)), base, largura=L, altura=A, fps=30, audio=tom, da_obj=d, carimbar=False)
        self.assertEqual((res["quadros"], res["carimbo"]), (300, None))
        est, dest = texto.Estilo.legenda(d, L, A), texto.Estilo.legenda(d, L, A, destaque=True)
        frases = (["a", "conta", "que", "não"], ["fecha", "no", "fim", "do"], ["mês", "é", "sempre", "sua"], ["e", "ninguém", "explica", "nada"])
        cues, passo, caixas = [], 10 / 64, []
        for k in range(64):
            fr = frases[(k // 4) % 4]
            img, info = texto.compor_legenda(fr, [dest if i == k % 4 else est for i in range(4)], d, L, A, recortar=True)
            cues.append({"imagem": img, "t0": k * passo, "t1": (k + 1) * passo, "x": info["x"], "y": info["y"]})
            caixas.append(info)
        registro = []
        real = trava.rodar

        def espiao(cmd, **k):
            registro.append(list(cmd))
            return real(cmd, **k)

        trava.rodar = espiao
        try:
            t0 = time.monotonic()
            r = video.compor_cues(base, cues, self.raiz / "legendas" / "corte legendado.mp4", da_obj=d, parametros={"skill": "video-legendas"})
            self.tempos["compor_cues 64 cues, 10 s, 320x180"] = round(time.monotonic() - t0, 2)
        finally:
            trava.rodar = real
        self.assertEqual(len(registro), 1, "tem de ser UMA passada de ffmpeg")
        self.assertEqual(registro[0].count("-i"), 2, "duas entradas (base + faixa por pipe), não uma por cue")
        self.assertEqual((r["cues"], r["estados"]), (64, 64))
        s, sb = video.sondar(r["saida"]), video.sondar(base)
        self.assertEqual((s["quadros"], s["largura"], s["altura"], s["tem_audio"]), (sb["quadros"], L, A, True))
        self.assertLess(r["regiao"][2] * r["regiao"][3], L * A / 3, "a faixa cobre só a região das cues, não o quadro inteiro")
        c = da.ler_carimbo(r["saida"])
        self.assertEqual((c["ferramenta"], c["parametros"]["cues"], c["parametros"]["skill"], c["insumos"][0]["arquivo"]), ("video.py compor_cues", 64, "video-legendas", "base lisa 10 s.mp4"))
        # a palavra em destaque é a certa em três instantes (centro de cada cue): amarela na falada, clara nas outras
        prim = d.rgb("primaria")
        for k in (3, 30, 61):
            t = (k + 0.5) * passo
            q = self.quadro(r["saida"], round(t, 3))
            info = caixas[k]
            for i, p in enumerate(info["palavras"]):
                recorte = q.crop((int(p["x0"]) + 1, int(p["y0"]), int(p["x1"]), int(p["y1"]) + 1))
                cores = recorte.getcolors(100000) or []
                amarelos = sum(n for n, (rr, gg, bb) in cores if abs(rr - prim[0]) < 70 and abs(gg - prim[1]) < 70 and bb < 120 and rr > 150)
                if i == k % 4:
                    self.assertGreater(amarelos, 4, f"cue {k} em t={t:.2f}: a palavra {i} deveria estar em destaque")
                else:
                    self.assertLess(amarelos, 3, f"cue {k} em t={t:.2f}: a palavra {i} não deveria estar em destaque")
        # trecho da base + cues em arquivo (PNG com carimbo entra na proveniência) + erros de uso
        png = self.raiz / "legendas" / "_png" / "cue 0.png"
        png.parent.mkdir(parents=True, exist_ok=True)
        cues[0]["imagem"].save(png)
        d.carimbar(png, "video-legendas", "320x180")
        r2 = video.compor_cues(base, [{"imagem": png, "t0": 0.2, "t1": 0.8, "x": cues[0]["x"], "y": cues[0]["y"]}], self.raiz / "legendas" / "trecho.mp4",
                               da_obj=d, inicio=2.0, duracao=1.0)
        s2 = video.sondar(r2["saida"])
        self.assertAlmostEqual(s2["duracao"], 1.0, delta=0.07)
        self.assertEqual([i["arquivo"] for i in da.ler_carimbo(r2["saida"])["insumos"]], ["base lisa 10 s.mp4", "cue 0.png"])
        with self.assertRaises(da.DAErro):
            video.compor_cues(base, [], self.raiz / "legendas" / "x.mp4", da_obj=d)
        with self.assertRaises(da.DAErro):
            video.compor_cues(base, [{"imagem": cues[0]["imagem"], "t0": 0, "t1": 1, "x": 5000, "y": 5000}], self.raiz / "legendas" / "x.mp4", da_obj=d)

    def test_23_juntar_executa_as_transicoes_da_da(self):
        """Era: movimento.transicoes validado e impresso, mas nenhuma peça do kit o executava."""
        raiz = self.projeto("neon-shorts", " transicoes")           # permitidas: corte, empurra, zoom
        d = da.carregar(raiz)
        a = self.clipe("clipe a.mp4", 1.5, tom=440)
        b = self.clipe("clipe b.mp4", 1.5, tamanho="180x320", tom=660)        # outra proporção: é ajustado ao primeiro
        mudo = self.raiz / "bruto" / "clipe mudo.mp4"
        if not mudo.is_file():
            video.executar(["-f", "lavfi", "-i", "testsrc2=size=320x180:rate=30:duration=1.5", *video.args_encode(30, crf=32, preset="ultrafast", audio=False)], mudo)
        T = d.dur("media")
        self.assertEqual(video.filtro_transicao("empurra", T, 1.0), f"xfade=transition=slideleft:duration={da._num(T, 4)}:offset=1")
        self.assertIsNone(video.filtro_transicao("corte", 0, 1.0))
        self.assertEqual(video.XFADE, {"fade": "fade", "empurra": "slideleft", "mascara": "wipeleft", "desliza": "coverleft", "zoom": "zoomin"})
        r = video.juntar([a, b, mudo], raiz / "render" / "junto padrão.mp4", da_obj=d)            # padrão da DA: corte
        s = video.sondar(r["saida"])
        self.assertEqual([t["tipo"] for t in r["transicoes"]], ["corte", "corte"])
        self.assertAlmostEqual(s["duracao"], 4.5, delta=0.12)
        self.assertEqual((s["largura"], s["altura"], str(s["fps"]), s["tem_audio"]), (320, 180, "30000/1001", True))
        t0 = time.monotonic()
        r = video.juntar([a, b, mudo], raiz / "render" / "junto empurra.mp4", transicao="empurra", da_obj=d)
        self.tempos["juntar 3 clipes de 1,5 s com empurra"] = round(time.monotonic() - t0, 2)
        s = video.sondar(r["saida"])
        self.assertAlmostEqual(s["duracao"], 4.5 - 2 * T, delta=0.12)                               # cada transição come T segundos
        self.assertAlmostEqual(r["duracao"], 4.5 - 2 * T, delta=0.01)
        self.assertEqual([t["tipo"] for t in r["transicoes"]], ["empurra", "empurra"])
        c = da.ler_carimbo(r["saida"])
        self.assertEqual((c["ferramenta"], [i["arquivo"] for i in c["insumos"]]), ("video.py juntar", ["clipe a.mp4", "clipe b.mp4", "clipe mudo.mp4"]))
        # no meio da 1ª transição o quadro mistura os dois clipes: a metade esquerda ainda é o A empurrado, a direita já é o B
        antes, meio = self.quadro(r["saida"], 0.5), self.quadro(r["saida"], round(1.5 - T / 2, 3))
        ref_a = self.quadro(a, 0.5)
        self.assertLess(sum(abs(x - y) for x, y in zip(antes.resize((8, 8)).tobytes(), ref_a.resize((8, 8)).tobytes())) / 192, 12)
        self.assertGreater(sum(abs(x - y) for x, y in zip(meio.resize((8, 8)).tobytes(), self.quadro(a, round(1.5 - T / 2, 3)).resize((8, 8)).tobytes())) / 192, 12)
        r = video.juntar([a, b], raiz / "render" / "junto misto.mp4", transicao=["zoom"], da_obj=d, duracao=0.2)
        self.assertEqual(r["transicoes"][0]["duracao"], 0.2)
        with self.assertRaises(da.DAErro) as cm:                      # fora de permitidas: a DA decide
            video.juntar([a, b], raiz / "render" / "x.mp4", transicao="fade", da_obj=d)
        self.assertIn("permitidas", str(cm.exception))
        with self.assertRaises(da.DAErro):                            # transição maior que o clipe
            video.juntar([a, b], raiz / "render" / "x.mp4", transicao="zoom", da_obj=d, duracao=3)

    def test_24_compor_overlay_trecho_formato_da_saida_e_proveniencia(self):
        """Era: formato do carimbo vinha da BASE, não havia inicio/duracao, e a auditoria pulada do overlay sumia."""
        from PIL import Image
        d = self.d
        base = self.clipe("base 10 s.mp4", 10)
        selo = self.raiz / "animacoes" / "selo ok.png"
        Image.new("RGBA", (60, 30), d.rgba("primaria")).save(selo)
        d.carimbar(selo, "motor", "60x30", auditoria="ok")
        rec = video.filtro_recorte((320, 180), (90, 160), "centro")
        r = video.compor_overlay(base, selo, self.raiz / "render" / "vertical com selo.mp4", x=10, y=100, inicio=2.0, duracao=1.0,
                                 tratamento_base=rec["filtro"], da_obj=d)
        s, c = video.sondar(r["saida"]), da.ler_carimbo(r["saida"])
        self.assertEqual((s["largura"], s["altura"], s["quadros"], s["tem_audio"]), (90, 160, 30, True))
        self.assertEqual(c["formato"], "90x160")                                                   # o da SAÍDA (a base é 320x180)
        self.assertEqual((c["midia"]["largura"], c["midia"]["altura"]), (90, 160))
        self.assertEqual([(i["arquivo"], i["auditoria"]) for i in c["insumos"]], [("base 10 s.mp4", None), ("selo ok.png", "ok")])
        self.assertTrue(da.conferir_carimbo([r["saida"]], da=d)["ok"])
        curta = self.clipe("clipe a.mp4", 1.5)                                                      # PNG sem `fim` sobre a base inteira: nenhum quadro a menos
        inteira = video.compor_overlay(curta, selo, self.raiz / "render" / "_png sem fim.mp4", da_obj=d, carimbar=False)
        self.assertEqual(video.sondar(inteira["saida"])["quadros"], video.sondar(curta)["quadros"])
        pulado = self.raiz / "animacoes" / "selo pulado.png"
        Image.new("RGBA", (60, 30), d.rgba("texto")).save(pulado)
        d.carimbar(pulado, "motor", "60x30", auditoria="pulada")
        r = video.compor_overlay(base, pulado, self.raiz / "render" / "com pulado.mp4", duracao=0.5, da=d)
        self.assertEqual(da.ler_carimbo(r["saida"])["auditoria"], "pulada")
        self.assertEqual(da.conferir_carimbo([r["saida"]], da=d)["pecas"][0]["estado"], "auditoria_pulada")
        # da.py grade sobre peça carimbada leva a proveniência junto; fps da fonte preservado em forma racional
        g = da.aplicar_grade(r["saida"], self.raiz / "broll" / "tratado" / "com pulado tratado.mp4", da=d)
        cg = da.ler_carimbo(g["saida"])
        self.assertEqual((cg["auditoria"], cg["insumos"][0]["arquivo"]), ("pulada", "com pulado.mp4"))
        self.assertTrue(any(i.get("via") == "com pulado.mp4" for i in cg["insumos"]))
        self.assertEqual(str(video.sondar(g["saida"])["fps"]), "30")

    def test_25_encaixe_desfocado_e_token_de_desfoque_sem_ambiguidade(self):
        d = self.d
        base = self.clipe("base 10 s.mp4", 10)
        enc = video.filtro_encaixe((320, 180), (180, 320), d=d)
        self.assertEqual((enc["modo"], enc["janela"], enc["saida"]), ("desfocado", (0, 109, 180, 102), (180, 320)))
        self.assertIn("gblur", enc["filtro"])
        saida = video.executar(["-ss", "1", "-t", "0.3", "-i", str(base), "-vf", enc["filtro"], *video.args_encode(30, crf=30)], self.raiz / "cortes" / "_encaixe.mp4")
        s = video.sondar(saida)
        self.assertEqual((s["largura"], s["altura"]), (180, 320))
        q = self.quadro(saida, 0.1)
        ref = self.quadro(base, 1.1).resize((180, 102))
        meio = q.crop((0, 109, 180, 211))
        dif_meio = sum(abs(x - y) for x, y in zip(meio.resize((12, 8)).tobytes(), ref.resize((12, 8)).tobytes())) / (12 * 8 * 3)
        self.assertLess(dif_meio, 14, "o vídeo original inteiro fica na janela")
        topo = q.crop((0, 0, 180, 100)).resize((12, 8)).tobytes()
        self.assertGreater(len(set(topo)), 3, "o fundo é imagem (desfocada), não cor chapada")
        # modos e tokens: `recorte` preenche o quadro; `faixas` usa a cor da DA; tratamento.desfoque NÃO é o do encaixe
        self.assertEqual(video.filtro_encaixe((320, 180), (180, 320), modo="recorte", d=d)["janela"], (0, 0, 180, 320))
        faixas = video.filtro_encaixe((320, 180), (180, 320), modo="faixas", d=d)
        self.assertIn("color=0x" + d.cor("fundo").lstrip("#"), faixas["filtro"])
        with self.assertRaises(da.DAErro):
            video.filtro_encaixe((320, 180), (180, 320), modo="espelho", d=d)
        self.assertNotIn("gblur", d.grade("vertical"))                                              # desfoque 0 na cadeia principal
        raiz = self.projeto("dossie", " desfoque")
        editar(raiz / "da" / "da.json", lambda j: j["tratamento"].update(encaixe={"modo": "faixas", "desfoque": 0.05, "escurecer": 0, "cor": "primaria"}))
        d2 = da.carregar(raiz)
        self.assertEqual(da.validar(raiz)["erros"], [])
        self.assertNotIn("gblur", d2.grade("vertical"))                                             # encaixe.desfoque não entra na cadeia de tratamento
        self.assertIn("color=0x" + d2.cor("primaria").lstrip("#"), video.filtro_encaixe((320, 180), (180, 320), d=d2)["filtro"])

    def test_26_loudnorm_em_duas_passagens_acerta_o_alvo_da_da_em_peca_curta(self):
        """Era: loudnorm escrito à mão em cada skill; a passagem única erra o alvo em peça de poucos segundos."""
        d = self.d
        bruto = self.raiz / "bruto" / "fala sintética 3 s.wav"                # tom com volume oscilando, bem abaixo do alvo
        video.executar(["-f", "lavfi", "-i", "sine=frequency=220:sample_rate=48000:duration=3", "-af", "volume='0.25+0.2*sin(2*PI*t*1.5)':eval=frame",
                        "-c:a", "pcm_s16le"], bruto, rotulo="teste: fala sintética")
        medida = video.medir_para_loudnorm(bruto, d, "curto", folga_pico=0.5)
        self.assertEqual(set(medida), {"input_i", "input_tp", "input_lra", "input_thresh", "target_offset"})
        self.assertLess(medida["input_i"], d["som"]["loudness"]["curto"]["lufs"] - 3)
        af = video.filtro_loudnorm(d, "curto", medida=medida, folga_pico=0.5)
        self.assertTrue(af.startswith("loudnorm=I=-14:TP=-1.5:LRA=11:measured_I="), af)
        self.assertTrue(af.endswith(":linear=true"), af)
        saida = video.executar(["-i", str(bruto), "-af", af, "-c:a", "aac", "-b:a", "192k", "-ar", "48000"], self.raiz / "cortes" / "_normalizado.m4a")
        r = video.conferir_loudness(d, saida, "curto")
        self.assertTrue(r["ok"], r)                                           # dentro de ±1 LU do alvo e sem estourar o pico
        self.assertLessEqual(abs(r["desvio_lufs"]), 1.0)
        mudo = self.raiz / "bruto" / "silêncio 1 s.wav"
        video.executar(["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", "1", "-c:a", "pcm_s16le"], mudo, rotulo="teste: silêncio")
        with self.assertRaises(da.DAErro) as cm:
            video.medir_para_loudnorm(mudo, d, "curto")
        self.assertIn("silêncio", str(cm.exception))
        with self.assertRaises(da.DAErro):
            video.filtro_loudnorm(d, "curto", medida={"input_i": -20})
        with self.assertRaises(da.DAErro):
            video.filtro_loudnorm(d, "médio")
        self.assertEqual(d.dimensoes("vertical"), (1080, 1920)); self.assertEqual(d.dimensoes("540x960"), (540, 960)); self.assertEqual(d.dimensoes(320, 180), (320, 180))
        with self.assertRaises(da.DAErro):
            d.dimensoes("panoramico")
        for sub in ("broll/bruto", "broll/tratado"):                          # o init já separa o b-roll baixado do tratado (D15)
            self.assertTrue((self.raiz / sub).is_dir(), sub)


# ════════════════════════════════════════════════════ motor: paridade e peças (D10, D13, D17) ══
CENA_LEGENDA = """
export const meta = { nome: 'legenda_kit', dur_padrao: 1, alfa_padrao: true,
  params: { palavras: { tipo: 'lista', obrigatorio: true, itens: { tipo: 'texto' } }, falada: { tipo: 'inteiro', padrao: -1 }, pulso: { tipo: 'numero', padrao: 1 },
    plataforma: { tipo: 'plataforma', padrao: null } } };
const S = {};
export function build(palco, p, ctx) {
  S.p = p; S.leg = ctx.kit.legenda(p.palavras, { falada: p.falada, plataforma: p.plataforma || undefined });
  palco.appendChild(S.leg.el); S.leg.posicionar();
  return { legenda: S.leg.layout };
}
export function seek(t) { S.leg.seek(S.p.falada, { pulso: S.p.pulso }); }
"""

CENA_PECAS = """
// cena de OUTRA skill reutilizando as peças do kit por ctx.kit — duas instâncias de cada, numa página só
export const meta = { nome: 'pecas_do_kit', dur_padrao: 3, alfa_padrao: false, params: { plataforma: { tipo: 'plataforma', padrao: null } } };
const S = {};
export async function build(palco, p, ctx) {
  const area = ctx.area_segura(p.plataforma || undefined);
  const camA = ctx.el('div'), camB = ctx.el('div');
  for (const c of [camA, camB]) { Object.assign(c.style, { position: 'absolute', inset: '0', background: ctx.cor('fundo') }); palco.appendChild(c); }
  const c1 = ctx.kit.credito('IBGE, 2024', { plataforma: p.plataforma || undefined, posicao: 'inferior_centro' });
  const c2 = ctx.kit.credito('Fonte: Tesouro Nacional', { plataforma: p.plataforma || undefined, posicao: 'superior_direita' });
  camA.appendChild(c1.el); camA.appendChild(c2.el);
  const r1 = c1.posicionar(), r2 = c2.posicionar();
  const t1 = ctx.kit.tarja('Capítulo 1'), t2 = ctx.kit.tarja('Capítulo 2', { inverter: true });
  for (const [t, y] of [[t1, 0.3], [t2, 0.4]]) { camA.appendChild(t.el); t.medir(); ctx.place(t.el, { x: area.x, y: area.y + area.h * y }); }
  const leg = ctx.kit.legenda(['a', 'conta', 'não', 'fecha'], { falada: 1 });
  camA.appendChild(leg.el); leg.posicionar();
  const m1 = ctx.kit.moldura({ rotulo: 'arquivo', estilo: 'borda', area: [0.1, 0.2, 0.3, 0.3] });
  const m2 = ctx.kit.moldura({ rotulo: 'reprodução', estilo: 'cantoneiras', area: [0.5, 0.2, 0.3, 0.3] });
  camB.appendChild(m1.el); camB.appendChild(m2.el);
  const g1 = await ctx.kit.cena('gc', { nome: 'Mariana Albuquerque', cargo: 'Procuradora' }, { palco: (() => { const e = ctx.el('div'); Object.assign(e.style, { position: 'absolute', inset: '0' }); camB.appendChild(e); return e; })(), dur: 3 });
  const g2 = await ctx.kit.cena('gc', { nome: 'João Pereira' }, { palco: (() => { const e = ctx.el('div'); Object.assign(e.style, { position: 'absolute', inset: '0' }); camB.appendChild(e); return e; })(), dur: 3 });
  Object.assign(S, { ctx, camA, camB, c1, c2, t1, t2, leg, m1, m2, g1, g2 });
  return { creditos: [r1.rect, r2.rect], textos: [c1.texto, c2.texto], area, molduras: [m1.layout.janela, m2.layout.janela], gcs: [g1.layout.caixa, g2.layout.caixa],
    zona_proibida: ctx.zona_proibida(), dur_transicao: ctx.dur_transicao('fade'), fim_entrada: 0.6, inicio_saida: 2.4 };
}
export function seek(t) {
  const { ctx, camA, camB, c1, c2, t1, t2, leg, m1, m2, g1, g2 } = S;
  c1.seek(ctx.prog(t, 0, 0.4)); c2.seek(ctx.prog(t, 0.1, 0.4));
  t1.seek(ctx.prog(t, 0, 0.3), ctx.prog(t, 0.2, 0.3)); t2.seek(ctx.prog(t, 0.1, 0.3), ctx.prog(t, 0.3, 0.3));
  leg.seek(Math.min(3, Math.floor(t * 2)));
  m1.seek(Math.max(0, t - 1.5)); m2.seek(Math.max(0, t - 1.5)); g1.seek(Math.max(0, t - 1.5)); g2.seek(Math.max(0, t - 1.5));
  ctx.transicao(camA, camB, ctx.prog(t, 1.3, ctx.dur_transicao('fade'), 'suave'), 'fade');
}
"""


class TesteMotor(Base):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.raiz = cls.projeto("dossie", " motor")
        cls.d = da.carregar(cls.raiz)
        (cls.raiz / "animacoes" / "legenda_kit.js").write_text(CENA_LEGENDA, encoding="utf-8")
        (cls.raiz / "animacoes" / "pecas_do_kit.js").write_text(CENA_PECAS, encoding="utf-8")

    def render(self, *args, d=None, esperado=0):
        r = motor.render([str(a) for a in args], da_obj=d or self.d, cwd=(d or self.d).raiz, capturar=True)
        if r.returncode != esperado:
            self.fail(f"render devolveu {r.returncode} (esperava {esperado})\nSTDOUT:\n{r.stdout}\nSTDERR:\n{r.stderr}")
        return r

    def layout(self, saida) -> dict:
        return da.ler_carimbo(saida)["parametros"]["layout"]

    def test_30_paridade_motor_x_pil_no_mesmo_token(self):
        """D10: a mesma linha pelos dois caminhos — largura ≤ 3 %, palavras e contorno a ≤ 1 px, as duas na zona segura."""
        from PIL import Image
        d = self.d
        palavras = ["dinheiro", "público", "desaparece"]
        fila = []
        for nome, fmt, pal in (("par v", "540x960", palavras), ("par h", "1920x1080", palavras), ("hih", "1920x1080", ["HIH"])):
            fila.append({"cena": "legenda_kit.js", "saida": f"_paridade/{nome}.png", "formato": fmt, "quadro": 0, "params": {"palavras": pal}})
        arq_fila = self.raiz / "animacoes" / "fila paridade.json"
        arq_fila.write_text(json.dumps(fila, ensure_ascii=False), encoding="utf-8")
        self.render("--fila", arq_fila)
        pasta = self.raiz / "animacoes" / "_paridade"
        for nome, (L, A) in (("par v", (540, 960)), ("par h", (1920, 1080))):
            with self.subTest(quadro=(L, A)):
                lay = self.layout(pasta / f"{nome}.png")["legenda"]
                img, info = texto.compor_legenda(palavras, texto.Estilo.legenda(d, L, A), d, L, A)
                self.assertEqual(info["linhas"], [[w.upper() for w in l] for l in lay["linhas"]])       # mesma quebra
                self.assertAlmostEqual(info["tamanho"], lay["tamanho"], delta=0.05)
                larg_pil, larg_motor = info["caixa"][2] - info["caixa"][0], lay["caixa"]["x1"] - lay["caixa"]["x0"]
                self.assertLess(abs(larg_pil - larg_motor) / larg_motor, 0.03, f"largura PIL {larg_pil:.1f} × motor {larg_motor:.1f}")
                for a, b in zip(info["palavras"], lay["palavras"]):
                    self.assertAlmostEqual(a["x0"], b["x0"], delta=1.0, msg=a["texto"]); self.assertAlmostEqual(a["x1"], b["x1"], delta=1.0, msg=a["texto"])
                self.assertAlmostEqual(info["vao"], lay["vao"], delta=0.3)
                self.assertTrue(info["dentro_da_zona"] and lay["dentro_da_zona"])
                with Image.open(pasta / f"{nome}.png") as m:                                         # os pixels também coincidem
                    tm, _ = caixas_opacas(m, d.rgb("texto")); tp, _ = caixas_opacas(img, d.rgb("texto"))
                for x, y in zip(tm, tp):
                    self.assertLessEqual(abs(x - y), 2, f"bbox opaco motor {tm} × PIL {tp}")
        with Image.open(pasta / "hih.png") as m:
            tm, mm = caixas_opacas(m, d.rgb("texto"))
        img, info = texto.compor_legenda(["HIH"], texto.Estilo.legenda(d, 1920, 1080), d, 1920, 1080)
        tp, mp = caixas_opacas(img, d.rgb("texto"))
        contorno_m = (mm[0] - tm[0], mm[1] - tm[1], tm[2] - mm[2], tm[3] - mm[3])
        contorno_p = (mp[0] - tp[0], mp[1] - tp[1], tp[2] - mp[2], tp[3] - mp[3])
        for a, b in zip(contorno_m, contorno_p):
            self.assertLessEqual(abs(a - b), 1, f"contorno (esq, topo, dir, base): motor {contorno_m} × PIL {contorno_p}")
        self.assertAlmostEqual(contorno_m[1], d["legenda"]["contorno"]["espessura"] * info["tamanho"], delta=1.0)   # 0,11 × 67 = 7 px para fora
        # estilo `palavra` + contorno grosso + sombra dura (neon-shorts): só a palavra falada, no tamanho comum da cue;
        # a sombra é projetada pelo texto COM o contorno e o contorno tem cantos redondos nos dois caminhos
        raiz_n = self.projeto("neon-shorts", " paridade")
        dn = da.carregar(raiz_n)
        (raiz_n / "animacoes" / "legenda_kit.js").write_text(CENA_LEGENDA, encoding="utf-8")
        png = raiz_n / "animacoes" / "_palavra.png"
        self.render("--cena", "animacoes/legenda_kit.js", "--saida", png, "--formato", "540x960", "--quadro", "0",
                    "--params", json.dumps({"palavras": palavras, "falada": 1}), d=dn)
        lay = self.layout(png)["legenda"]
        estados = texto.estados_da_legenda(palavras, dn, 540, 960, recortar=False)
        self.assertAlmostEqual(estados[1][1]["tamanho"], lay["tamanho"], delta=0.05)               # 0,092 × 540 encolhido duas vezes: 43,9 px nos dois
        self.assertLess(lay["tamanho"], lay["tamanho_pedido"])
        with Image.open(png) as m:
            bm = m.convert("RGBA").getbbox()
        bp = estados[1][0].getbbox()
        for a, b in zip(bm, bp):                                                                      # tudo o que foi pintado: letra + contorno + sombra
            self.assertLessEqual(abs(a - b), 2, f"palavra falada: bbox do motor {bm} × PIL {bp}")
        esp = round(dn["legenda"]["contorno"]["espessura"] * lay["tamanho"])
        sombra = dn["legenda"]["sombra"]["dy"] * lay["tamanho"]
        self.assertGreater(esp, sombra)                                                              # contorno mais grosso que o deslocamento da sombra
        sem_sombra = [texto.Estilo.legenda(dn, 540, 960, destaque=True).com(sombra=None)] * 3
        b0 = texto.compor_legenda(palavras, sem_sombra, dn, 540, 960, apenas=1)[0].getbbox()
        self.assertAlmostEqual(bp[3] - b0[3], sombra, delta=1.0, msg="a sombra desce além do contorno (no motor ficava escondida atrás dele)")
        self.assertAlmostEqual(bm[3] - b0[3], sombra, delta=2.0, msg="…e no motor também")

    def test_31_cena_externa_reusa_pecas_do_kit_com_varias_instancias(self):
        """D17: ctx.kit.credito/tarja/legenda/moldura/cena; antes só adivinhando import(new URL('cenas/_tarja.js', document.baseURI))."""
        saida = self.raiz / "animacoes" / "peças.png"
        r = self.render("--cena", "animacoes/pecas_do_kit.js", "--saida", saida, "--formato", "960x540", "--quadro", "0.7")
        self.assertIn("auditoria ok", r.stderr)
        lay = self.layout(saida)
        area = lay["area"]
        c1, c2 = lay["creditos"]
        self.assertAlmostEqual((c1["x"] + c1["x1"]) / 2, (area["x"] + area["x1"]) / 2, delta=1.5)    # inferior_centro: centrado na zona (era à direita do centro)
        self.assertAlmostEqual(c1["y1"], area["y1"], delta=1.5)
        self.assertAlmostEqual(c2["x1"], area["x1"], delta=1.5); self.assertAlmostEqual(c2["y"], area["y"], delta=1.5)
        self.assertEqual(lay["textos"], ["Fonte: IBGE, 2024", "Fonte: Tesouro Nacional"])           # prefixo do token, sem duplicar
        self.assertNotEqual(lay["molduras"][0], lay["molduras"][1])
        self.assertTrue(all(g and g["w"] > 0 for g in lay["gcs"]))
        self.assertEqual(lay["zona_proibida"], {"x": 720, "y": 421, "w": 240, "h": 119, "x1": 960, "y1": 540, "canto": "inferior_direita"})
        self.assertEqual(lay["dur_transicao"], self.d.dur("media"))
        # vídeo curto com a transição 'fade' entre as duas camadas: passa pelo auditor e pela checagem de pureza
        mp4 = self.raiz / "animacoes" / "peças.mp4"
        r = self.render("--cena", "animacoes/pecas_do_kit.js", "--saida", mp4, "--formato", "480x270", "--dur", "2.4", "--fps", "10")
        self.assertIn("pureza em", r.stderr)
        self.assertEqual(video.sondar(mp4)["quadros"], 24)
        # transição fora das permitidas da DA é erro da cena (o dossiê não permite 'empurra')
        ruim = self.raiz / "animacoes" / "transicao_proibida.js"
        ruim.write_text(CENA_PECAS.replace("'fade');\n}", "'empurra');\n}"), encoding="utf-8")
        r = self.render("--cena", ruim, "--saida", self.raiz / "animacoes" / "_x.png", "--formato", "480x270", "--quadro", "1.4", esperado=1)
        self.assertIn("movimento.transicoes.permitidas", r.stderr)

    def test_32_barras_e_citacao_usam_a_mesma_peca_de_credito(self):
        raiz = self.projeto("dossie", " crédito ao centro")
        editar(raiz / "da" / "da.json", lambda j: j["graficos"]["citacao_fonte"].update(posicao="inferior_centro", prefixo="Dados: "))
        d = da.carregar(raiz)
        fila = [{"cena": "citacao", "saida": "c.png", "formato": "960x540", "quadro": 4, "params": {"texto": "A conta não fecha", "autor": "Alguém", "fonte": "Folha, 2024"}},
                {"cena": "barras", "saida": "b.png", "formato": "960x540", "quadro": 4,
                 "params": {"dados": [{"rotulo": "A", "valor": 1}, {"rotulo": "B", "valor": 2}], "fonte": "Dados: IBGE"}},
                {"cena": "barras", "saida": "bv.png", "formato": "540x960", "quadro": 4, "params": {"dados": [{"rotulo": "A", "valor": 1}], "fonte": "IBGE", "plataforma": "reels"}}]
        arq = raiz / "animacoes" / "fila crédito.json"
        arq.write_text(json.dumps(fila, ensure_ascii=False), encoding="utf-8")
        self.render("--fila", arq, d=d)
        zona_h = d.margens("horizontal", largura=960, altura=540)
        for nome in ("c.png", "b.png"):
            cr = self.layout(raiz / "animacoes" / nome)["credito"]
            self.assertAlmostEqual(cr["x"] + cr["w"] / 2, (zona_h["x0"] + zona_h["x1"]) / 2, delta=2, msg=nome)   # antes: 530 (citacao) e 98 (barras) num quadro de centro 480
            self.assertAlmostEqual(cr["y1"], zona_h["y1"], delta=2, msg=nome)
        zona_v = d.margens("vertical", "instagram", largura=540, altura=960)
        cr = self.layout(raiz / "animacoes" / "bv.png")["credito"]
        self.assertAlmostEqual(cr["x"] + cr["w"] / 2, (zona_v["x0"] + zona_v["x1"]) / 2, delta=2)

    def test_33_params_itens_de_lista_e_tipo_plataforma_antes_do_browser(self):
        """Era: itens de lista sem validação e plataforma como texto livre que só falhava depois de abrir o browser."""
        d = self.d
        base = ["--cena", "animacoes/legenda_kit.js", "--saida", self.raiz / "animacoes" / "_v.png", "--quadro", "0", "--validar"]
        r = self.render(*base, "--params", json.dumps({"palavras": ["a", {"x": 1}, None]}), esperado=64)
        self.assertIn("palavras[1]", r.stderr)
        r = self.render(*base, "--params", json.dumps({"palavras": ["a", None]}), esperado=64)
        self.assertIn("palavras[1]", r.stderr)
        r = self.render(*base, "--params", json.dumps({"palavras": ["a"], "plataforma": "tiktokk"}), esperado=64)
        self.assertIn("tiktok", r.stderr); self.assertIn("Quis dizer", r.stderr)
        r = self.render(*base, "--params", json.dumps({"palavras": ["a"], "plataforma": "uniao"}), "--formato", "horizontal")
        self.assertIn("usa \"padrao\"", r.stderr)                                                   # o mesmo storyboard serve aos dois formatos, com aviso
        r = self.render(*base, "--params", json.dumps({"palavras": ["a"], "plataforma": "reels"}), "--formato", "vertical")
        self.assertNotIn("não existe no formato", r.stderr)
        barras = ["--cena", "barras", "--saida", self.raiz / "animacoes" / "_b.png", "--quadro", "0", "--validar"]
        r = self.render(*barras, "--params", json.dumps({"dados": [{"rotulo": "A", "valor": "dez"}]}), esperado=64)
        self.assertIn("dados[0].valor", r.stderr)
        r = self.render(*barras, "--params", json.dumps({"dados": [{"rotulo": "A", "valr": 3}]}), esperado=64)
        self.assertIn("Quis dizer", r.stderr)
        r = self.render(*barras, "--params", json.dumps({"dados": []}), esperado=64)
        self.assertIn("mínimo", r.stderr)
        self.render(*barras, "--params", json.dumps({"dados": [{"rotulo": "A", "valor": 3}]}))
        # e na página: 'uniao' num quadro horizontal cai em 'padrao' em vez de derrubar o render
        saida = self.raiz / "animacoes" / "_h.png"
        self.render("--cena", "animacoes/legenda_kit.js", "--saida", saida, "--quadro", "0", "--formato", "960x540",
                    "--params", json.dumps({"palavras": ["a", "conta"], "plataforma": "uniao"}))
        self.assertEqual(self.layout(saida)["legenda"]["zona"]["plataforma"], "padrao")

    def test_34_moldura_rotulo_na_zona_segura_e_janela_girada(self):
        fila = [{"cena": "moldura", "saida": "_m/v.png", "formato": "540x960", "quadro": 1.5, "params": {"rotulo": "arquivo · 2018", "sub": "reprodução", "estilo": "cantoneiras"}},
                {"cena": "moldura", "saida": "_m/vt.png", "formato": "540x960", "quadro": 1.5, "params": {"rotulo": "arquivo", "sub": "tv", "estilo": "borda", "plataforma": "tiktok"}},
                {"cena": "moldura", "saida": "_m/p.png", "formato": "960x540", "quadro": 1.5, "params": {"rotulo": "arquivo", "estilo": "polaroid", "area": [0.25, 0.12, 0.5, 0.76]}},
                {"cena": "moldura", "saida": "_m/p0.png", "formato": "960x540", "quadro": 1.5, "params": {"estilo": "polaroid", "area": [0.25, 0.12, 0.5, 0.76], "inclinacao": 0}}]
        arq = self.raiz / "animacoes" / "fila moldura.json"
        arq.write_text(json.dumps(fila, ensure_ascii=False), encoding="utf-8")
        self.render("--fila", arq)
        pasta = self.raiz / "animacoes" / "_m"
        for nome, plat in (("v.png", "uniao"), ("vt.png", "tiktok")):
            lay = self.layout(pasta / nome)
            z = self.d.margens("vertical", plat, largura=540, altura=960)
            self.assertEqual(lay["zona"]["plataforma"], plat)
            for chave in ("rotulo", "sub"):                          # antes: rótulo em y≈58 (zona começa em 144) e sub em x 410–485 (zona acaba em 389)
                r = lay[chave]
                self.assertTrue(r["x"] >= z["x0"] - 1 and r["x1"] <= z["x1"] + 1 and r["y"] >= z["y0"] - 1 and r["y1"] <= z["y1"] + 1, (nome, chave, r, z))
            self.assertTrue(lay["rotulo"]["x1"] <= lay["sub"]["x"] or lay["rotulo"]["y1"] <= lay["sub"]["y"], "rótulo e sub não se sobrepõem")
        import math
        lay, reto = self.layout(pasta / "p.png"), self.layout(pasta / "p0.png")
        g, j = lay["janela_girada"], lay["janela"]
        self.assertEqual((g["angulo"], lay["inclinacao"]), (-1.5, -1.5))
        rad = math.radians(-1.5)
        cx, cy = j["x"] + j["w"] / 2 - 480, j["y"] + j["h"] / 2 - 270                              # a raiz gira em torno do centro do quadro
        self.assertAlmostEqual(g["cx"], 480 + cx * math.cos(rad) - cy * math.sin(rad), delta=0.6)
        self.assertAlmostEqual(g["cy"], 270 + cx * math.sin(rad) + cy * math.cos(rad), delta=0.6)
        self.assertEqual(len(g["cantos"]), 4)
        self.assertNotEqual(g["cantos"][0][1], g["cantos"][1][1])                                   # inclinada: o topo não é horizontal
        for girado, reto_px in zip(reto["janela_girada"]["cantos"][0], (reto["janela"]["x"], reto["janela"]["y"])):
            self.assertAlmostEqual(girado, reto_px, delta=0.6)                                      # sem inclinação: a mesma janela
        # o insert entra girado junto com a janela: nos 4 cantos da janela girada (por dentro) há insert, não a base
        d = self.d
        from PIL import Image
        base = self.raiz / "render" / "_base escura.png"
        base.parent.mkdir(exist_ok=True)
        Image.new("RGB", (960, 540), d.rgb("fundo")).save(base)
        insert = self.raiz / "render" / "_insert claro.png"
        Image.new("RGB", (640, 360), d.rgb("primaria")).save(insert)
        fundo = video.executar(["-loop", "1", "-framerate", "10", "-t", "0.3", "-i", str(base), *video.args_encode(10, crf=30, audio=False)], self.raiz / "render" / "_base escura.mp4")
        r = video.encaixar_em_janela(fundo, insert, self.raiz / "render" / "insert na polaroid.mp4", lay, da_obj=d)
        q = self.raiz / "qa" / "_polaroid.png"
        video.extrair_quadro(r["saida"], 0.1, q)
        with Image.open(q) as im:
            im = im.convert("RGB")
            prim = d.rgb("primaria")
            for (x, y) in g["cantos"]:
                px = (x + (g["cx"] - x) * 0.06, y + (g["cy"] - y) * 0.06)                           # um passo para dentro do canto
                cor = im.getpixel((int(px[0]), int(px[1])))
                self.assertTrue(all(abs(a - b) < 45 for a, b in zip(cor, prim)), f"canto {x, y}: {cor} não é o insert")
            fora = im.getpixel((int(g["cantos"][0][0] - 12), int(g["cantos"][0][1] - 12)))
            self.assertTrue(all(abs(a - b) < 30 for a, b in zip(fora, d.rgb("fundo"))), fora)
        self.assertEqual([i["arquivo"] for i in da.ler_carimbo(r["saida"])["insumos"]], ["_base escura.mp4", "_insert claro.png"])

    def test_35_teste_de_movimento_executa_a_transicao_padrao_da_da(self):
        raiz = self.projeto("dossie", " transição")
        editar(raiz / "da" / "da.json", lambda j: j["movimento"]["transicoes"].update(padrao="mascara"))
        d = da.carregar(raiz)
        base = ["--cena", "teste_movimento", "--formato", "480x270"]
        png0 = raiz / "qa" / "_tm 0.png"
        r = motor.render([*base, "--saida", str(png0), "--quadro", "0"], da_obj=d, cwd=raiz, capturar=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        lay = self.layout(png0)
        self.assertEqual((lay["transicao"], lay["dur_transicao"]), ("mascara", d.dur("media")))
        # o teste tem três atos (título → GC → barras) e a transição da DA entre eles: no meio da máscara que traz o ato
        # do GC, o quadro é metade cartela (já vazia) e metade o plano do GC — difere dos dois lados da transição
        j = lay["janelas"]["gc"]
        self.assertEqual((j["pre"], round(j["inicio"] - j["t0"], 3)), (d.dur("media"), d.dur("media")))
        from PIL import Image
        qs = {}
        for nome, t in (("antes", j["t0"] - 0.05), ("meio", j["t0"] + j["pre"] * 0.5), ("depois", j["inicio"] + 0.01)):
            png = raiz / "qa" / f"_tm {nome}.png"
            rr = motor.render([*base, "--saida", str(png), "--quadro", str(round(t, 3))], da_obj=d, cwd=raiz, capturar=True)
            self.assertEqual(rr.returncode, 0, rr.stderr)
            with Image.open(png) as im:
                qs[nome] = im.convert("RGB").resize((48, 27)).tobytes()
        self.assertNotEqual(qs["meio"], qs["antes"]); self.assertNotEqual(qs["meio"], qs["depois"])

if __name__ == "__main__":
    unittest.main(verbosity=2)
