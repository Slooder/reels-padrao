#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Segmentação, glossário, tempos, janela de corte, .srt/.vtt e edição (cues.py). Não usa ffmpeg nem rede:
precisa só do kit de direção de arte ao lado (fonte e tamanho reais da DA medem as cues)."""
import json
import re
import sys
import unittest
from fractions import Fraction
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import apoio  # noqa: E402
import comum  # noqa: E402
import cues  # noqa: E402

RE_SRT = re.compile(r"^(\d{2}):(\d{2}):(\d{2}),(\d{3}) --> (\d{2}):(\d{2}):(\d{2}),(\d{3})$")
RE_VTT = re.compile(r"^(\d{2}):(\d{2}):(\d{2})\.(\d{3}) --> (\d{2}):(\d{2}):(\d{2})\.(\d{3})$")


def seg(g):
    return int(g[0]) * 3600 + int(g[1]) * 60 + int(g[2]) + int(g[3]) / 1000


def pal(texto, ritmo=0.3, inicio=0.0, pausas=None):
    """Palavras coladas, uma a cada `ritmo` s; pausas = {índice: segundos de silêncio DEPOIS da palavra}."""
    saida, t = [], inicio
    for i, w in enumerate(texto.split()):
        saida.append({"a": round(t, 3), "b": round(t + ritmo, 3), "w": w, "p": 0.9})
        t += ritmo + (pausas or {}).get(i, 0.0)
    return saida


def textos(pal_, grupos, f=lambda p: p.w()):
    return [" ".join(f(p) for p in pal_[a:b]) for a, b in grupos]


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raiz = apoio.pasta_temporaria()
        cls.da, cls.texto, _, _ = comum.kit()

    @classmethod
    def tearDownClass(cls):
        apoio.apagar(cls.raiz)


class TestPalavras(Base):
    def test_01_partir_token(self):
        self.assertEqual(cues.partir_token("“Brasília,”"), ("“", "Brasília", ",”"))
        self.assertEqual(cues.partir_token("B.O.s"), ("", "B.O.s", ""))
        self.assertEqual(cues.partir_token("S.A."), ("", "S.A.", ""))
        self.assertEqual(cues.partir_token("agora?"), ("", "agora", "?"))
        self.assertEqual(cues.partir_token("50%"), ("", "50%", ""))
        self.assertEqual(cues.partir_token("..."), ("", "", "..."))

    def test_02_exibicao_por_politica_de_pontuacao(self):
        p = cues.Pal(0, 1, "agora", pos="?")
        q = cues.Pal(0, 1, "sabem", pos=",")
        self.assertEqual((p.w("limpa"), p.w("manter"), p.w("nenhuma")), ("agora?", "agora?", "agora"))
        self.assertEqual((q.w("limpa"), q.w("manter"), q.txt), ("sabem", "sabem,", "sabem,"))

    def test_03_formato_invalido_e_erro_acionavel(self):
        for ruim in ([], [{"w": "oi"}], [{"a": "x", "w": "oi"}], {"palavras": []}, [{"a": -1, "b": 0, "w": "oi"}]):
            with self.assertRaises(comum.Erro):
                cues.ler_palavras(ruim)
        ok = cues.ler_palavras([{"a": 0, "b": 0.2, "w": "oi"}])                # sem `p`: confiança 1
        self.assertEqual(ok[0]["p"], 1.0)

    def test_04_tokens_de_controle_e_pontuacao_solta(self):
        dados = [{"a": 0.0, "b": 0.3, "w": "[_BEG_]", "p": 1}, {"a": 0.3, "b": 0.6, "w": "disse", "p": 0.9}, {"a": 0.6, "b": 0.62, "w": "-me", "p": 0.8},
                 {"a": 0.7, "b": 0.9, "w": "isso", "p": 0.9}, {"a": 0.9, "b": 0.9, "w": "...", "p": 0.9}]
        p, notas = cues.preparar(dados)
        self.assertEqual([x.nucleo for x in p], ["disse-me", "isso"])
        self.assertEqual(p[1].pos, "...")
        self.assertEqual(notas["tokens_fundidos"], 2)
        self.assertAlmostEqual(p[0].p, 0.8)                                     # a confiança do conjunto é a menor

    def test_05_janela_rebaseia_e_usa_o_meio_da_palavra(self):
        dados = pal("zero um dois três quatro cinco seis sete oito nove", ritmo=0.5)      # palavra k: k/2 … k/2 + 0,5
        p, notas = cues.preparar(dados, inicio=1.2, fim=3.2)
        self.assertEqual([x.nucleo for x in p], ["dois", "três", "quatro", "cinco"])      # meios 1,25 · 1,75 · 2,25 · 2,75
        self.assertEqual(p[0].a, 0.0)                                                      # começou antes da janela: prende em 0
        self.assertAlmostEqual(p[1].a, 0.3)
        self.assertLessEqual(p[-1].b, 2.0 + 1e-9)
        self.assertEqual(notas["fora_da_janela"], 6)
        with self.assertRaises(comum.Erro):
            cues.preparar(dados, inicio=40, fim=50)
        with self.assertRaises(comum.Erro):
            cues.preparar(dados, inicio=3, fim=2)

    def test_06_duracao_zero_rouba_da_anterior_sem_empurrar_as_seguintes(self):
        dados = [{"a": 0.0, "b": 0.6, "w": "assista.", "p": 1}, {"a": 1.4, "b": 1.4, "w": "E", "p": 1}, {"a": 1.4, "b": 1.4, "w": "eu", "p": 1},
                 {"a": 1.4, "b": 1.9, "w": "vou", "p": 1}, {"a": 1.9, "b": 1.9, "w": "ainda", "p": 1}, {"a": 1.9, "b": 2.4, "w": "contar", "p": 1}]
        p, notas = cues.preparar(dados)
        a = [x.a for x in p]
        self.assertEqual(a, sorted(a))
        for x, y in zip(p, p[1:]):
            self.assertGreaterEqual(round(y.a - x.a, 3), cues.MIN_PALAVRA - 1e-9, (x.nucleo, y.nucleo))
            self.assertLessEqual(x.b, y.a + 1e-9)
        self.assertEqual(p[3].a, 1.4)                                           # "vou" não saiu do lugar
        self.assertEqual(p[5].a, 1.9)                                           # "contar" também não
        self.assertLess(p[1].a, 1.4 - 0.15)                                     # "E eu" foi puxado para o silêncio anterior
        self.assertGreaterEqual(p[1].a, 0.6)                                    # …sem entrar na palavra "assista."
        self.assertGreater(p[4].a, 1.4 + 0.15)                                  # "ainda" tirou no máximo 60 % de "vou"
        self.assertGreaterEqual(notas["tempos_reparados"], 3)


class TestSegmentacao(Base):
    def agrupar(self, texto, max_palavras=4, caracteres=30, linhas=2, **k):
        p, _ = cues.preparar(pal(texto, **k))
        return p, cues.segmentar(p, cues.MedidorDeCaracteres(caracteres, linhas), max_palavras)

    def test_10_fim_de_frase_sempre_fecha(self):
        p, g = self.agrupar("Isso é fato. Ninguém discorda disso hoje.")
        self.assertEqual(textos(p, g), ["Isso é fato", "Ninguém discorda disso hoje"])

    def test_11_pausa_longa_fecha_mesmo_sem_pontuacao(self):
        p, g = self.agrupar("um dia ela mudou para lá", max_palavras=6, pausas={2: 0.9})
        self.assertEqual(textos(p, g), ["um dia ela", "mudou para lá"])

    def test_12_virgula_e_melhor_que_meio_de_sintagma(self):
        p, g = self.agrupar("se a conta não fecha, o dinheiro some rápido", max_palavras=5)
        self.assertEqual(textos(p, g), ["se a conta não fecha", "o dinheiro some rápido"])

    def test_13_nao_termina_em_artigo_preposicao_ou_conjuncao(self):
        p, g = self.agrupar("ele comprou a casa de praia com o dinheiro da herança que recebeu", max_palavras=4)
        soltas = cues.ARTIGOS | cues.PREPOSICOES | cues.CONJUNCOES
        for t in textos(p, g)[:-1]:
            self.assertNotIn(t.split()[-1].lower(), soltas, textos(p, g))
        for a, b in g:
            self.assertLessEqual(b - a, 4)

    def test_14_numero_fica_com_a_unidade_e_nome_com_sobrenome(self):
        p, g = self.agrupar("o modelo ficou 23 % mais rápido segundo o Ashish Vaswani ontem", max_palavras=4)
        junto = " | ".join(textos(p, g))
        self.assertRegex(junto, r"23 %")
        self.assertRegex(junto, r"Ashish Vaswani")
        p, g = self.agrupar("a empresa captou 3 milhões de dólares em 2024 com Sam Altman", max_palavras=3)
        junto = " | ".join(textos(p, g))
        self.assertRegex(junto, r"3 milhões")
        self.assertRegex(junto, r"Sam Altman")

    def test_15_e_verbo_nao_e_tratado_como_e_conjuncao(self):
        p, _ = cues.preparar(pal("isso é real e claro"))
        self.assertLess(cues.custo_quebra(p, 1, linha=True), cues.custo_quebra(p, 3, linha=True))    # depois de "é" < depois de "e"

    def test_16_sem_palavra_orfa_no_meio_da_frase(self):
        p, g = self.agrupar("a gente precisa falar sobre isso agora mesmo pessoal", max_palavras=4)
        self.assertTrue(all(b - a >= 2 for a, b in g), textos(p, g))

    def test_17_cue_respeita_a_largura_do_medidor(self):
        p, g = self.agrupar("responsabilidade institucional extraordinariamente desproporcional compromete tudo", max_palavras=5, caracteres=20, linhas=1)
        for t in textos(p, g):
            self.assertTrue(len(t) <= 20 or " " not in t, t)                   # só passa da largura a palavra que não cabe sozinha

    def test_18_melhor_quebra_prefere_o_sentido(self):
        p, _ = cues.preparar(pal("que ele falou ali que é real"))
        med = cues.MedidorDeCaracteres(18, 2)
        partes = cues.melhor_quebra(p, [med.largura(x.w()) for x in p], med)
        self.assertEqual(partes, [4, 3])                                        # "que ele falou ali / que é real", não "… falou / ali que é real"
        self.assertEqual(cues.melhor_quebra(p[:3], [med.largura(x.w()) for x in p[:3]], med), [3])     # cabe numa linha: uma linha
        self.assertIsNone(cues.melhor_quebra(p, [med.largura(x.w()) for x in p], cues.MedidorDeCaracteres(8, 2)))

    def test_19_nome_com_particula_e_numeral_composto_sao_blocos(self):
        """Regressão: «Luiz Inácio Lula | da Silva», «São José | dos Campos», «vinte | e três por cento», «de mil / novecentos»."""
        def cortes(texto):
            p, _ = cues.preparar(pal(texto))
            n = [x.nucleo for x in p]
            return p, n, lambda palavra, linha=False: cues.custo_quebra(p, n.index(palavra), linha=linha)
        # 1. custos: toda junção dentro do nome ou do numeral custa caro, em fim de cue e em fim de linha…
        p, n, depois_de = cortes("Ontem o Luiz Inácio Lula da Silva falou com a imprensa")
        for palavra in ("Luiz", "Inácio", "Lula", "da"):
            for linha in (False, True):
                self.assertGreaterEqual(depois_de(palavra, linha), 10, (palavra, linha))
        self.assertLess(depois_de("Silva"), 1)                                  # …e o corte bom é depois do nome
        self.assertLess(depois_de("Lula"), depois_de("da"))                     # se tiver de partir, antes da partícula, nunca depois
        self.assertGreater(depois_de("o"), depois_de("Lula"))                   # e pendurar o artigo não é saída para poupar o nome
        p, n, depois_de = cortes("o Lula e a Dilma vieram, Lula e Dilma falaram")
        self.assertLess(cues.custo_quebra(p, n.index("vieram") + 1), 6)         # "Lula | e Dilma": com "e" podem ser dois nomes
        p, n, depois_de = cortes("custou cento e cinquenta mil reais em 1999 e ninguém viu, vinte e três por cento")
        for palavra in ("cento", "cinquenta", "mil", "vinte", "três", "por"):
            self.assertGreaterEqual(depois_de(palavra), 10, palavra)
        self.assertGreaterEqual(cues.custo_quebra(p, n.index("cento") + 1), 12)                  # "cento e | cinquenta"
        self.assertLess(depois_de("1999"), 0)                                   # "1999 | e ninguém viu" é bom corte
        # 2. com espaço para o nome inteiro, ele fica inteiro
        p, g = self.agrupar("Ontem o Luiz Inácio Lula da Silva falou com a imprensa sobre o caso", max_palavras=7, caracteres=60)
        self.assertTrue(any("o Luiz Inácio Lula da Silva" in t for t in textos(p, g)), textos(p, g))
        p, g = self.agrupar("ela nasceu em São José dos Campos e depois mudou para longe", max_palavras=5, caracteres=40)
        self.assertIn("em São José dos Campos", textos(p, g))
        p, g = self.agrupar("Naquele ano foram vinte e três por cento de aumento desde mil novecentos e noventa", max_palavras=5, caracteres=40)
        self.assertIn("vinte e três por cento", textos(p, g))
        self.assertIn("desde mil novecentos e noventa", textos(p, g))
        # 3. nome de seis palavras em cues de cinco: parte, mas nunca deixa artigo, partícula ou "e" do numeral pendurados
        for texto in ("Ontem o Luiz Inácio Lula da Silva falou com a imprensa sobre o caso",
                      "O projeto custou cento e cinquenta mil reais no ano de mil novecentos e noventa e nove e ninguém viu"):
            for mp, car in ((4, 30), (5, 40)):
                p, g = self.agrupar(texto, max_palavras=mp, caracteres=car)
                for t in textos(p, g)[:-1]:
                    self.assertNotIn(t.split()[-1], ("o", "da", "de", "e", "no"), (mp, textos(p, g)))
        # 4. quebra de linha: sem palavra de ligação pendurada no fim da linha de cima
        p, n, _ = cortes("custou cento e cinquenta mil reais")
        med = cues.MedidorDeCaracteres(22, 2)
        partes = cues.melhor_quebra(p[1:], [med.largura(x.w()) for x in p[1:]], med)
        self.assertNotEqual(p[1:][partes[0] - 1].nucleo, "e", partes)
        # … nem quando a alternativa é uma linha de uma palavra só (dossie vertical dava «cento e / cinquenta mil»)
        for texto, caracteres, proibida in (("cento e cinquenta mil", 20, "e"), ("a Maria da Conceição Tavares", 22, "da"),
                                            ("vinte e três por cento", 16, "e")):
            p, n, _ = cortes(texto)
            med = cues.MedidorDeCaracteres(caracteres, 2)
            partes = cues.melhor_quebra(p, [med.largura(x.w()) for x in p], med)
            self.assertNotEqual(p[partes[0] - 1].nucleo, proibida, (texto, partes))
        p, n, depois_de = cortes("cento e cinquenta mil")
        self.assertGreater(cues.custo_quebra(p, 1, linha=True), depois_de("cento", True) + 4)     # folga maior que a pena da linha de uma palavra


class TestDocumento(Base):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.proj = apoio.projeto(cls.raiz, "lab-ia")
        cls.d = cls.da.carregar(str(cls.proj))
        cls.palavras = apoio.palavras_sinteticas()
        cls.duracao = cls.palavras[-1]["b"] + 0.5
        cls.doc = cues.construir(cls.palavras, cls.d, 1080, 1920, "vertical", duracao=cls.duracao, fps=Fraction(30000, 1001))

    def test_20_contrato(self):
        doc = self.doc
        for campo in ("versao", "origem", "formato", "plataforma", "estilo", "cues"):
            self.assertIn(campo, doc)
        self.assertEqual((doc["versao"], doc["formato"], doc["plataforma"], doc["estilo"]), (1, "vertical", "uniao", "karaoke"))
        for c in doc["cues"]:
            self.assertEqual(set(("t0", "t1", "linhas", "palavras")) - set(c), set())
            for w in c["palavras"]:
                self.assertEqual(set(("a", "b", "w", "linha", "destaque")) - set(w), set())
                self.assertIsInstance(w["destaque"], bool)
        self.assertEqual(cues.validar(doc), [])
        json.dumps(doc)                                                         # serializável

    def test_21_agrupamento_segue_a_da(self):
        leg = self.d["legenda"]
        todas = [w["w"] for c in self.doc["cues"] for w in c["palavras"]]
        self.assertEqual(len(todas), len(self.palavras))                        # nenhuma palavra se perde
        for c in self.doc["cues"]:
            self.assertLessEqual(len(c["palavras"]), leg["max_palavras"])       # o teto é o da DA, sem exceção
            self.assertLessEqual(len(c["linhas"]), leg["max_linhas"])
            self.assertEqual([w for l in c["linhas"] for w in l], [w["w"] for w in c["palavras"]])
        self.assertFalse([a for a in self.doc["avisos"] if a["tipo"] == "largura"])

    def test_22_toda_cue_cabe_sem_encolher_na_zona_segura(self):
        for (L, A, plat) in ((1080, 1920, None), (1080, 1920, "tiktok"), (540, 960, "reels"), (1920, 1080, None)):
            doc = cues.construir(self.palavras, self.d, L, A, f"{L}x{A}", plataforma=plat, duracao=self.duracao, fps=30)
            for c in doc["cues"]:
                _, info = self.texto.compor_legenda([w["w"] for w in c["palavras"]], self.texto.Estilo.legenda(self.d, L, A), self.d, L, A,
                                                    plataforma=plat, linhas=[len(l) for l in c["linhas"]])
                self.assertFalse(info["encolheu"], (L, A, plat, c["linhas"]))
                self.assertTrue(info["dentro_da_zona"], (L, A, plat, c["linhas"]))

    def test_23_tempos(self):
        doc, regras = self.doc, self.doc["regras"]
        self.assertGreaterEqual(doc["cues"][0]["t0"], 0)
        self.assertLessEqual(doc["cues"][-1]["t1"], doc["duracao"] + 1e-6)
        for c, prox in zip(doc["cues"], doc["cues"][1:] + [None]):
            self.assertGreater(c["t1"], c["t0"])
            self.assertAlmostEqual(c["t0"], c["palavras"][0]["a"], places=3)   # a cue entra na primeira palavra
            a = [w["a"] for w in c["palavras"]]
            self.assertEqual(a, sorted(a))
            self.assertLess(a[-1], c["t1"])
            if prox:
                self.assertGreaterEqual(prox["t0"] - c["t1"], regras["respiro"] - 1e-3, (c["id"], "respiro entre cues"))
            ultima = c["palavras"][-1]
            self.assertLessEqual(c["t1"] - ultima["a"], cues.TETO_FALA[0] + cues.TETO_FALA[1] * 30 + cues.SEGURA + cues.FECHA_VAO,
                                 "a cue não fica pendurada no silêncio")
        curtas = [c for c in doc["cues"] if c["t1"] - c["t0"] < cues.DUR_MIN - 1e-6]
        self.assertEqual(len(curtas), len([a for a in doc["avisos"] if a["tipo"] == "duracao"]))

    def test_24_confianca_baixa_vira_aviso(self):
        p = [dict(w) for w in self.palavras]
        p[3]["p"], p[10]["p"] = 0.31, 0.59
        doc = cues.construir(p, self.d, 1080, 1920, "vertical", duracao=self.duracao)
        avisos = [a for a in doc["avisos"] if a["tipo"] == "confianca"]
        self.assertEqual([a["p"] for a in avisos], [0.31, 0.59])
        self.assertIn("0,31", avisos[0]["mensagem"])
        self.assertEqual(len([a for a in cues.construir(p, self.d, 1080, 1920, "vertical", duracao=self.duracao, limiar=0.2)["avisos"]
                              if a["tipo"] == "confianca"]), 0)

    def test_29_transcricao_mais_longa_que_o_video(self):
        doc = cues.construir(self.palavras, self.d, 1080, 1920, "vertical", duracao=4.0)
        self.assertGreater(doc["notas"]["depois_do_fim"], 0)
        self.assertLessEqual(doc["cues"][-1]["t1"], 4.0 + 1e-6)
        self.assertTrue(all(w["a"] < 4.0 for c in doc["cues"] for w in c["palavras"]))
        with self.assertRaises(comum.Erro) as cm:
            cues.construir(self.palavras, self.d, 1080, 1920, "vertical", inicio=0, duracao=0.1)
        self.assertIn("outro vídeo", cm.exception.dica)

    def test_25_estilos_da_da(self):
        for preset, estilo, pont in (("neon-shorts", "palavra", "limpa"), ("editorial-claro", "bloco", "manter")):
            d = self.da.carregar(str(apoio.projeto(self.raiz, preset, nome=f"proj {preset}")))
            doc = cues.construir(self.palavras, d, 1080, 1920, "vertical", duracao=self.duracao)
            self.assertEqual((doc["estilo"], doc["pontuacao"]), (estilo, pont))
            self.assertEqual(cues.validar(doc), [])
            for c in doc["cues"]:
                self.assertLessEqual(len(c["palavras"]), d["legenda"]["max_palavras"])
            if estilo == "palavra":
                self.assertEqual(doc["regras"]["respiro"], 0.0)                 # uma palavra por vez: não há bloco para respirar
                self.assertTrue(all(len(c["linhas"]) == 1 for c in doc["cues"]))
            else:
                self.assertTrue(any(w["w"].endswith((",", ".")) for c in doc["cues"] for w in c["palavras"]))    # bloco mantém a pontuação

    def test_2A_max_palavras_e_teto_mesmo_com_fala_rapida(self):
        """Regressão: cue curta era fundida até max_palavras + 1 (5 palavras numa DA de 4), sem aviso."""
        d = self.da.carregar(str(apoio.projeto(self.raiz, "dossie", nome="proj teto")))
        self.assertEqual(d["legenda"]["max_palavras"], 4)
        rapida = apoio.palavras_sinteticas("E aquela coisa também, né galera, se teve uma coisa que ele falou ali que é real, é real. "
                                           "Então por mais que tenha uma investigação e não dê em nada, eu acho pouco provável, sabe, "
                                           "eu acho que vai ter alguma coisa assim, mas mesmo que ele não dê em nada a denúncia pesa.",
                                           ritmo=0.022, pausa_frase=0.25, pausa_virgula=0.04)
        doc = cues.construir(rapida, d, 1080, 1920, "vertical", fps=30)
        self.assertEqual(max(len(c["palavras"]) for c in doc["cues"]), 4, [len(c["palavras"]) for c in doc["cues"]])
        self.assertTrue(all(len(c["linhas"]) <= d["legenda"]["max_linhas"] for c in doc["cues"]))
        curtas = [c["id"] for c in doc["cues"] if c["t1"] - c["t0"] < cues.DUR_MIN - 1e-6]
        self.assertEqual(curtas, [a["cue"] for a in doc["avisos"] if a["tipo"] == "duracao"])      # o que ficou curto está avisado
        # o agrupamento já nasce evitando o flash: com o custo desligado sobram mais cues curtas
        pesos = dict(cues.PESOS_QUEIMADA)
        try:
            cues.PESOS_QUEIMADA["relampago"] = 0.0
            sem = cues.construir(rapida, d, 1080, 1920, "vertical", fps=30)
        finally:
            cues.PESOS_QUEIMADA.update(pesos)
        self.assertLessEqual(len(curtas), len([a for a in sem["avisos"] if a["tipo"] == "duracao"]))

    def test_2B_estilo_palavra_mede_a_leitura_pela_duracao_real(self):
        """Regressão: no estilo `palavra` a conta usava 0,5 s fixos e quase toda cue de 13+ caracteres «passava de 25 por segundo»."""
        d = self.da.carregar(str(apoio.projeto(self.raiz, "neon-shorts", nome="proj leitura")))
        doc = cues.construir(self.palavras, d, 1080, 1920, "vertical", duracao=self.duracao)
        self.assertEqual(doc["estilo"], "palavra")
        longas = [c for c in doc["cues"] if len(" ".join(w["w"] for w in c["palavras"])) > 13 and len(c["palavras"]) > 1]
        self.assertTrue(longas)                                                 # há cues que a conta antiga acusava…
        self.assertEqual([a for a in doc["avisos"] if a["tipo"] == "leitura"], [])                # …e a fala é normal (12–15 caracteres/s)
        self.assertEqual([a for a in doc["avisos"] if a["tipo"] == "duracao"], [])                # no estilo `palavra` não há aviso de cue curta
        corrida = [dict(w, a=round(w["a"] / 3, 3), b=round(w["b"] / 3, 3)) for w in self.palavras]   # a mesma fala três vezes mais rápida
        doc = cues.construir(corrida, d, 1080, 1920, "vertical", duracao=self.duracao / 3)
        avisos = [a for a in doc["avisos"] if a["tipo"] == "leitura"]
        self.assertTrue(avisos)
        por_id = {c["id"]: c for c in doc["cues"]}
        for a in avisos:
            c = por_id[a["cue"]]
            self.assertGreater(len(" ".join(w["w"] for w in c["palavras"])) / (c["t1"] - c["t0"]), cues.CPS_QUEIMADA)

    def test_26_srt_e_vtt_validos(self):
        srt, vtt = cues.texto_srt(self.doc["frases"]), cues.texto_vtt(self.doc["frases"])
        blocos = [b for b in srt.strip().split("\n\n")]
        self.assertEqual(len(blocos), len(self.doc["frases"]))
        fim_anterior = 0.0
        for n, b in enumerate(blocos, 1):
            linhas = b.split("\n")
            self.assertEqual(linhas[0], str(n))
            m = RE_SRT.match(linhas[1])
            self.assertIsNotNone(m, linhas[1])
            t0, t1 = seg(m.groups()[:4]), seg(m.groups()[4:])
            self.assertGreater(t1, t0)
            self.assertGreaterEqual(t0, fim_anterior)                           # sem sobreposição
            self.assertLessEqual(t1, self.doc["duracao"] + 0.001)
            self.assertLessEqual(t1 - t0, cues.OCULTA_DUR_MAX + 0.001)
            fim_anterior = t1
            corpo = linhas[2:]
            self.assertTrue(1 <= len(corpo) <= cues.OCULTA_LINHAS, corpo)
            for l in corpo:
                self.assertTrue(l.strip())
                self.assertLessEqual(len(l), cues.OCULTA_CARACTERES, l)
        self.assertEqual(" ".join(" ".join(b.split("\n")[2:]) for b in blocos), apoio.FRASE)       # o texto inteiro, com a pontuação
        self.assertTrue(vtt.startswith("WEBVTT\n\n"))
        tempos = [l for l in vtt.split("\n") if "-->" in l]
        self.assertEqual(len(tempos), len(blocos))
        self.assertTrue(all(RE_VTT.match(l) for l in tempos), tempos[:2])
        self.assertNotIn(",", "".join(tempos))

    def test_27_vtt_escapa_marcacao_e_srt_nunca_sobrepoe(self):
        itens = [{"t0": 0.0, "t1": 1.0004, "texto": "P&D <rápido> a --> b"}, {"t0": 1.0, "t1": 1.0003, "texto": "fim"}]
        vtt = cues.texto_vtt(itens)
        self.assertIn("P&amp;D &lt;rápido&gt;", vtt)
        self.assertEqual(vtt.count("-->"), 2)                                   # só as duas linhas de tempo
        srt = cues.texto_srt(itens)
        t = [RE_SRT.match(l).groups() for l in srt.split("\n") if "-->" in l]
        self.assertLessEqual(seg(t[0][4:]), seg(t[1][:4]))
        self.assertGreater(seg(t[1][4:]), seg(t[1][:4]))

    def test_28_srt_passa_no_conferidor_da_publicacao(self):
        pacote = comum.SKILL.parent / "video-publicacao" / "scripts" / "pacote.py"
        if not pacote.is_file():
            self.skipTest("skill video-publicacao não está instalada ao lado")
        arq = cues.gravar(self.doc, self.proj / "legendas", "contrato publicação")
        sys.path.insert(0, str(pacote.parent))
        try:
            import pacote as pub
        finally:
            sys.path.remove(str(pacote.parent))
        an = pub.analisar_srt(arq["srt"])
        self.assertEqual(an["problemas"], [])
        self.assertEqual(len(an["cues"]), len(self.doc["frases"]))


class TestGlossario(Base):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.proj = apoio.projeto(cls.raiz, "lab-ia")
        cls.d = cls.da.carregar(str(cls.proj))

    def aplicar(self, texto, g, **k):
        p, _ = cues.preparar(pal(texto, **k))
        base = {"trocas": {}, "censura": [], "destaques": [], "numeros_em_algarismo": False, "mascara": "***"}
        return cues.aplicar_glossario(p, {**base, **g})

    def test_30_troca_simples_guarda_tempo_pontuacao_e_original(self):
        p, rel = self.aplicar("o professor Souza, disse isso", {"trocas": {"souza": "Sousa"}})
        self.assertEqual([x.nucleo for x in p], ["o", "professor", "Sousa", "disse", "isso"])
        self.assertEqual((p[2].a, p[2].b, p[2].pos, p[2].orig), (0.6, 0.9, ",", "Souza,"))
        self.assertEqual(rel["trocas"], 1)

    def test_31_troca_de_varias_palavras_reparte_o_intervalo(self):
        p, _ = self.aplicar("talvez da de manhã ele venha", {"trocas": {"talvez da de": "talvez até de"}})
        self.assertEqual([x.nucleo for x in p][:3], ["talvez", "até", "de"])
        p, _ = self.aplicar("a inteligência artificial geral chegou", {"trocas": {"inteligência artificial geral": "AGI"}})
        self.assertEqual([x.nucleo for x in p], ["a", "AGI", "chegou"])
        self.assertEqual((p[1].a, p[1].b), (0.3, 1.2))                          # do início da 1ª ao fim da última
        p, _ = self.aplicar("o gpt chegou", {"trocas": {"gpt": "GPT 4 Turbo"}})
        self.assertEqual([x.nucleo for x in p], ["o", "GPT", "4", "Turbo", "chegou"])
        self.assertAlmostEqual(p[1].a, 0.3)
        self.assertAlmostEqual(p[3].b, 0.6)
        self.assertTrue(p[1].b <= p[2].a + 1e-9 and p[2].b <= p[3].a + 1e-9)

    def test_32_troca_respeita_acento_e_inicio_de_frase(self):
        p, _ = self.aplicar("ele da aula. Abc é sigla", {"trocas": {"dá": "DÁ", "abc": "abd"}})
        self.assertEqual([x.nucleo for x in p], ["ele", "da", "aula", "Abd", "é", "sigla"])       # "da" ≠ "dá"; maiúscula de frase mantida

    def test_33_censura_mascara_e_nao_deixa_rastro(self):
        p, rel = self.aplicar("foi o Fulano de Tal, o tal fulano", {"censura": ["Fulano de Tal", "fulano"], "mascara": "###"})
        self.assertEqual([x.nucleo for x in p], ["foi", "o", "###", "o", "tal", "###"])
        self.assertEqual(rel["censuradas"], 2)
        self.assertTrue(all(x.orig is None and x.censurada for x in p if x.nucleo == "###"))
        self.assertEqual((p[2].a, p[2].b, p[2].pos), (0.6, 1.5, ","))
        arq = apoio.gravar_palavras(self.proj, pal("foi o Fulano de Tal, o tal fulano falou. Fim."), "censura")
        (self.proj / "legendas").mkdir(exist_ok=True)
        (self.proj / "legendas" / "glossario.json").write_text(json.dumps({"censura": ["Fulano de Tal", "fulano"]}), encoding="utf-8")
        try:
            r = cues.gerar(arq, projeto=self.proj, formato="vertical", nome="censura")
            for a in r["arquivos"].values():
                self.assertNotIn("fulano", a.read_text(encoding="utf-8").lower(), a.name)
            self.assertIn("***", r["arquivos"]["srt"].read_text(encoding="utf-8"))
        finally:
            (self.proj / "legendas" / "glossario.json").unlink()

    def test_34_numeros_em_algarismo_sem_perder_a_sincronia(self):
        p, rel = self.aplicar("em dois mil e dezessete eram vinte e três por cento.", {"numeros_em_algarismo": True})
        self.assertEqual([x.nucleo for x in p], ["em", "2017", "eram", "23%"])
        self.assertEqual((p[1].a, p[1].b), (0.3, 1.5))
        self.assertEqual((p[3].a, p[3].b, p[3].pos), (1.8, 3.3, "."))
        self.assertEqual(rel["numeros"], 2)
        p, _ = self.aplicar("vinte, e três depois", {"numeros_em_algarismo": True})               # a vírgula corta o número
        self.assertEqual([x.nucleo for x in p], ["20", "e", "três", "depois"])
        p, _ = self.aplicar("em dois mil e dezessete", {})                                         # desligado: nada muda
        self.assertEqual(len(p), 5)

    def test_35_destaques_marcam_a_palavra_no_documento(self):
        dados = pal("a atenção mudou tudo e o modelo de linguagem também")
        g = {"trocas": {}, "censura": [], "numeros_em_algarismo": False, "mascara": "***", "destaques": ["Atenção", "modelo de linguagem", "inexistente"]}
        doc = cues.construir(dados, self.d, 1080, 1920, "vertical", glossario=g)
        marcadas = [w["w"] for c in doc["cues"] for w in c["palavras"] if w["destaque"]]
        self.assertEqual(marcadas, ["atenção", "modelo", "de", "linguagem"])
        self.assertEqual(doc["glossario"]["destaques"], 2)
        self.assertEqual(doc["glossario"]["sem_ocorrencia"], ["destaque «inexistente»"])

    def _sem_buracos(self, doc, rotulo):
        """Fala contínua (palavras coladas): entre duas cues só cabe o respiro; nenhuma some no meio da fala."""
        for c, prox in zip(doc["cues"], doc["cues"][1:]):
            self.assertLessEqual(prox["t0"] - c["t1"], doc["regras"]["respiro"] + 2e-3,
                                 f"{rotulo}: {prox['t0'] - c['t1']:.2f} s sem legenda depois de «{' '.join(w['w'] for w in c['palavras'])}»")

    def test_37_texto_mais_curto_nao_tira_a_cue_no_meio_da_fala(self):
        """Regressão (alta): o fim da fala era estimado pelo texto NOVO — «cento e cinquenta mil» → «150.000» saía da tela
        0,6 s antes de a fala acabar, e a pausa inventada separava o número de «reais»."""
        base = {"trocas": {}, "censura": [], "destaques": [], "numeros_em_algarismo": False, "mascara": "***"}
        frase = "O projeto custou cento e cinquenta mil reais no ano de mil novecentos e noventa e nove e ninguém viu"
        dados, t = [], 1.0
        for w in frase.split():                                                 # 0,12 s + 0,06 s por letra, coladas (como a video-transcricao entrega)
            dados.append({"a": round(t, 3), "b": round(t + 0.12 + 0.06 * len(w), 3), "w": w, "p": 0.95})
            t = dados[-1]["b"]
        doc = cues.construir(dados, self.d, 1080, 1920, "vertical", glossario={**base, "numeros_em_algarismo": True}, fps=30)
        textos_ = [" ".join(w["w"] for w in c["palavras"]) for c in doc["cues"]]
        self.assertTrue(any("150.000 reais" in x for x in textos_), textos_)    # número e unidade na mesma cue
        self.assertTrue(any("1999" in x for x in textos_), textos_)
        self._sem_buracos(doc, "números")
        self._sem_buracos(cues.construir(dados, self.d, 1080, 1920, "vertical", fps=30), "sem glossário")
        w = next(w for c in doc["cues"] for w in c["palavras"] if w["w"] == "150.000")
        mil = next(x for x in dados if x["w"] == "mil")
        self.assertAlmostEqual(w["fala_fim"], mil["b"], places=3)               # a palavra-número «dura» até o fim de "mil"
        self.assertEqual(doc["frases"], cues.editar(doc, self.d, 1, destacar=[1])[0]["frases"])    # o fim de fala sobrevive a uma edição
        # nome longo censurado e troca por texto mais curto: a mesma coisa
        dados, t = [], 1.0
        for w in "Ontem o Luiz Inácio Lula da Silva falou com a imprensa sobre o caso".split():
            dados.append({"a": round(t, 3), "b": round(t + 0.12 + 0.06 * len(w), 3), "w": w, "p": 0.95})
            t = dados[-1]["b"]
        fim_do_nome = next(x for x in dados if x["w"] == "Silva")["b"]
        for rotulo, g, na_tela in (("censura", {"censura": ["Luiz Inácio Lula da Silva"]}, "***"),
                                   ("troca", {"trocas": {"Luiz Inácio Lula da Silva": "Lula"}}, "Lula")):
            doc = cues.construir(dados, self.d, 1080, 1920, "vertical", glossario={**base, **g}, fps=30)
            self._sem_buracos(doc, rotulo)
            cue = next(c for c in doc["cues"] if any(w["w"] == na_tela for w in c["palavras"]))
            self.assertGreaterEqual(cue["t1"], fim_do_nome - doc["regras"]["respiro"] - 2e-3, rotulo)     # na tela enquanto o nome é dito
            self.assertAlmostEqual(next(w for w in cue["palavras"] if w["w"] == na_tela)["fala_fim"], fim_do_nome, places=3)
        # palavra tirada pelo glossário (troca por vazio): a anterior fica na tela enquanto ela é dita
        p, _ = self.aplicar("isso aqui né galera é sério", {"trocas": {"né galera": ""}})
        self.assertEqual([x.nucleo for x in p], ["isso", "aqui", "é", "sério"])
        self.assertAlmostEqual(p[1].fim_da_fala, 1.2)

    def test_38_troca_seguida_de_censura_nao_deixa_a_transcricao_original(self):
        """Regressão: «Anna Nakamora» → «Ana Nakamura» + censura de «Nakamura» deixava "orig": "Anna Nakamora," na palavra «Ana»."""
        g = {"trocas": {"Anna Nakamora": "Ana Nakamura"}, "censura": ["Nakamura"], "destaques": [], "numeros_em_algarismo": False, "mascara": "***"}
        doc = cues.construir(pal("ontem a Anna Nakamora, falou sobre isso."), self.d, 1080, 1920, "vertical", glossario=g)
        bruto = json.dumps(doc, ensure_ascii=False)
        self.assertNotIn("Nakamora", bruto)
        self.assertNotIn("Nakamura", bruto)
        self.assertIn("Ana", bruto)
        self.assertEqual(sum(1 for c in doc["cues"] for w in c["palavras"] if w.get("censurada")), 1)
        self.assertEqual(cues.texto_srt(doc["frases"]).count("***"), 1)

    def test_39_texto_do_glossario_nao_pede_revisao_palavra_a_palavra(self):
        """Regressão: «né galera» (p 0,44) → «né, minha gente querida» gerava 4 avisos de confiança para um texto escrito por gente."""
        dados = pal("isso também né galera, e são vinte e três por cento.")
        for w in dados:
            if cues.partir_token(w["w"])[1] in ("né", "galera", "vinte", "três"):
                w["p"] = 0.44
        g = {"trocas": {"né galera": "né, minha gente querida"}, "censura": [], "destaques": [], "numeros_em_algarismo": True, "mascara": "***"}
        doc = cues.construir(dados, self.d, 1080, 1920, "vertical", glossario=g)
        avisados = [a["palavra"] for a in doc["avisos"] if a["tipo"] == "confianca"]
        self.assertEqual(avisados, ["23%"])                                     # o número veio do whisper: um aviso só, com a menor confiança
        self.assertTrue(all(w["p"] == 1.0 for c in doc["cues"] for w in c["palavras"] if w["w"] in ("né", "minha", "gente", "querida")))

    def test_36_glossario_malformado(self):
        pasta = self.proj / "legendas"
        pasta.mkdir(exist_ok=True)
        arq = pasta / "_glossario ruim.json"
        for conteudo, trecho in (('{"troca": {"a": "b"}}', "Quis dizer 'trocas'"), ('{"trocas": ["a"]}', "trocas"), ('{"censura": "nome"}', "censura"),
                                 ('{"numeros_em_algarismo": "sim"}', "true ou false"), ('{"mascara": "a b"}', "mascara"), ('{"mascara": "[…]"}', "mascara"), ("{", "JSON")):
            arq.write_text(conteudo, encoding="utf-8")
            with self.assertRaises(comum.Erro) as cm:
                cues.ler_glossario(arq)
            self.assertIn(trecho, cm.exception.mensagem)
        arq.write_text('{"_nota": "livre", "trocas": {"a": "b"}}', encoding="utf-8")
        self.assertEqual(cues.ler_glossario(arq)["trocas"], {"a": "b"})
        arq.unlink()


class TestArquivosEEdicao(Base):
    def setUp(self):
        self.proj = apoio.projeto(self.raiz, "lab-ia", nome=f"projeto {self._testMethodName}")
        self.arq = apoio.gravar_palavras(self.proj, apoio.palavras_sinteticas())

    def test_40_gerar_grava_os_tres_arquivos_com_nome_acentuado(self):
        r = cues.gerar(self.arq, projeto=self.proj, formato="vertical", nome="corte 01 ação")
        self.assertEqual(sorted(p.name for p in (self.proj / "legendas").iterdir()),
                         ["corte 01 ação.cues.json", "corte 01 ação.srt", "corte 01 ação.vtt"])
        doc = json.loads(r["arquivos"]["cues"].read_text(encoding="utf-8"))
        self.assertEqual(doc["palavras_origem"], "transcricao/fala.palavras.json")          # relativo à raiz do projeto
        self.assertIsNone(doc["origem"])                                                     # sem vídeo, sem origem
        self.assertEqual((doc["largura"], doc["altura"]), (1080, 1920))
        self.assertEqual(cues.gerar(self.arq, projeto=self.proj, formato="540x960", escala=None)["doc"]["formato"], "540x960")
        self.assertEqual(cues.gerar(self.arq, projeto=self.proj, formato="horizontal", escala=0.5)["doc"]["formato"], "960x540")
        with self.assertRaises(comum.Erro):
            cues.gerar(self.arq, projeto=self.proj)                                          # sem formato e sem vídeo
        with self.assertRaises(self.da.DAErro):
            cues.gerar(self.arq, projeto=self.proj, formato="vertical", plataforma="kwai")   # zona que não existe

    def test_41_editar_palavra_guarda_os_tempos_e_regrava_srt(self):
        r = cues.gerar(self.arq, projeto=self.proj, formato="vertical", nome="edição")
        d = self.da.carregar(str(self.proj))
        doc = r["doc"]
        alvo = next(c for c in doc["cues"] if any(w["w"] == "Vaswani" for w in c["palavras"]))
        k = [w["w"] for w in alvo["palavras"]].index("Vaswani") + 1
        antes = alvo["palavras"][k - 1]
        doc2, feito = cues.editar(doc, d, alvo["id"], palavra=k, para="Váswani")
        depois = next(c for c in doc2["cues"] if c["id"] == alvo["id"])["palavras"][k - 1]
        self.assertEqual((depois["w"], depois["a"], depois["b"]), ("Váswani", antes["a"], antes["b"]))
        self.assertTrue(doc2["editado"])
        self.assertEqual(len(doc2["edicoes"]), 1)
        self.assertIn("Váswani", " ".join(f["texto"] for f in doc2["frases"]))
        self.assertEqual(cues.validar(doc2), [])
        cues.gravar(doc2, self.proj / "legendas", "edição")
        self.assertIn("Váswani", (self.proj / "legendas" / "edição.srt").read_text(encoding="utf-8"))
        with self.assertRaises(comum.Erro) as cm:                                            # gerar de novo apagaria a correção
            cues.gerar(self.arq, projeto=self.proj, formato="vertical", nome="edição")
        self.assertIn("corrigido à mão", cm.exception.mensagem)
        self.assertFalse(cues.gerar(self.arq, projeto=self.proj, formato="vertical", nome="edição", forcar=True)["doc"]["editado"])

    def test_42_editar_texto_com_outra_quantidade_de_palavras(self):
        doc = cues.gerar(self.arq, projeto=self.proj, formato="vertical")["doc"]
        d = self.da.carregar(str(self.proj))
        c = doc["cues"][1]
        velhas = c["palavras"]
        novo = " ".join(w["txt"] for w in velhas[:-1]) + " muito " + velhas[-1]["txt"]       # uma palavra a mais antes da última
        doc2, _ = cues.editar(doc, d, c["id"], texto=novo)
        novas = doc2["cues"][1]["palavras"]
        self.assertEqual(len(novas), len(velhas) + 1)
        self.assertEqual([(w["a"]) for w in novas[:len(velhas) - 2]], [w["a"] for w in velhas[:-2]])   # o que não mudou não andou
        a = [w["a"] for w in novas]
        self.assertEqual(a, sorted(a))
        self.assertEqual(cues.validar(doc2), [])
        self.assertEqual(len(doc2["cues"]), len(doc["cues"]))                                # as outras cues não foram refeitas
        self.assertEqual(doc2["cues"][3], doc["cues"][3])

    def test_43_dividir_juntar_remover_tempos_e_linhas(self):
        doc = cues.gerar(self.arq, projeto=self.proj, formato="vertical")["doc"]
        d = self.da.carregar(str(self.proj))
        n = len(doc["cues"])
        longa = next(c for c in doc["cues"] if len(c["palavras"]) >= 4)
        dividido, _ = cues.editar(doc, d, longa["id"], dividir=2)
        self.assertEqual(len(dividido["cues"]), n + 1)
        a, b = dividido["cues"][longa["id"] - 1], dividido["cues"][longa["id"]]
        self.assertEqual(len(a["palavras"]), 2)
        self.assertLessEqual(a["t1"], b["t0"])
        self.assertEqual([c["id"] for c in dividido["cues"]], list(range(1, n + 2)))         # renumerado
        junto, _ = cues.editar(dividido, d, longa["id"], juntar=True)
        self.assertEqual([[w["w"] for w in c["palavras"]] for c in junto["cues"]], [[w["w"] for w in c["palavras"]] for c in doc["cues"]])
        sem, _ = cues.editar(doc, d, 2, remover=True)
        self.assertEqual(len(sem["cues"]), n - 1)
        self.assertEqual(sum(len(c["palavras"]) for c in sem["cues"]), sum(len(c["palavras"]) for c in doc["cues"]) - len(doc["cues"][1]["palavras"]))
        self.assertEqual(cues.validar(sem), [])
        c2 = doc["cues"][1]
        mexido, _ = cues.editar(doc, d, 2, t1=round(c2["t1"] - 0.05, 3))
        self.assertAlmostEqual(mexido["cues"][1]["t1"], c2["t1"] - 0.05, places=3)
        for ruim in (dict(t1=doc["cues"][2]["t0"] + 0.2), dict(t0=doc["cues"][0]["t1"] - 0.2), dict(t0=5, t1=4), dict(dividir=99),
                     dict(palavra=99, para="x"), dict(para="x"), dict(linhas=[9, 9]), dict()):
            with self.assertRaises(comum.Erro, msg=str(ruim)):
                cues.editar(doc, d, 2, **ruim)
        with self.assertRaises(comum.Erro):
            cues.editar(doc, d, 999, remover=True)
        duas = next(c for c in doc["cues"] if len(c["palavras"]) >= 3)
        forcado, _ = cues.editar(doc, d, duas["id"], linhas=[1, len(duas["palavras"]) - 1], destacar=[1])
        nova = forcado["cues"][duas["id"] - 1]
        self.assertEqual(len(nova["linhas"][0]), 1)
        self.assertTrue(nova["palavras"][0]["destaque"])

    def test_46_trecho_nunca_leva_o_nome_da_legenda_do_video_inteiro(self):
        """Regressão (alta): `--inicio/--fim` sem `--nome` gravava legendas/<vídeo>.srt por cima da legenda do vídeo inteiro."""
        inteiro = cues.gerar(self.arq, projeto=self.proj, formato="vertical")
        srt = inteiro["arquivos"]["srt"]
        self.assertEqual((inteiro["nome"], srt.name), ("fala", "fala.srt"))
        antes = srt.read_text(encoding="utf-8")
        trecho = cues.gerar(self.arq, projeto=self.proj, formato="vertical", inicio=2.0, fim=6.5)
        self.assertEqual(trecho["nome"], "fala 2-6.5s")
        self.assertEqual(trecho["arquivos"]["srt"].name, "fala 2-6.5s.srt")
        self.assertEqual(srt.read_text(encoding="utf-8"), antes)               # a legenda do vídeo inteiro ficou como estava
        self.assertEqual(cues.gerar(self.arq, projeto=self.proj, formato="vertical", inicio=2.0)["nome"], "fala 2-fim")
        with self.assertRaises(comum.Erro) as cm:                               # pedir o nome do vídeo inteiro para um trecho é erro de uso
            cues.gerar(self.arq, projeto=self.proj, formato="vertical", inicio=2.0, fim=6.5, nome="fala")
        self.assertEqual(cm.exception.codigo, 64)
        self.assertIn('--nome "fala 2-6.5s"', cm.exception.dica)
        self.assertEqual(srt.read_text(encoding="utf-8"), antes)
        cues.gerar(self.arq, projeto=self.proj, formato="vertical", nome="abertura")             # outra legenda de vídeo inteiro
        with self.assertRaises(comum.Erro) as cm:
            cues.gerar(self.arq, projeto=self.proj, formato="vertical", inicio=2.0, fim=6.5, nome="abertura")
        self.assertIn("INTEIRO", cm.exception.mensagem)
        self.assertIsNone(json.loads((self.proj / "legendas" / "abertura.cues.json").read_text(encoding="utf-8"))["janela"]["fim"])
        self.assertEqual(cues.gerar(self.arq, projeto=self.proj, formato="vertical", inicio=2.0, fim=6.5, nome="abertura", forcar=True)["doc"]["janela"]["fim"], 6.5)
        cues.gerar(self.arq, projeto=self.proj, formato="vertical", inicio=2.0, fim=6.5, nome="K01")   # ajustar o ponto de corte de um trecho
        self.assertEqual(cues.gerar(self.arq, projeto=self.proj, formato="vertical", inicio=1.5, fim=6.5, nome="K01")["doc"]["janela"]["inicio"], 1.5)
        r = apoio.rodar("cues.py", "gerar", "--palavras", "transcricao/fala.palavras.json", "--formato", "vertical", "--inicio", "2", "--fim", "6.5",
                        "--nome", "fala", cwd=self.proj)
        self.assertEqual(r.returncode, 64, r.stderr)
        self.assertIn("vídeo INTEIRO", r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_47_linhas_nao_passam_do_teto_da_da(self):
        """Regressão: `editar --linhas 1,1,1,1` era aceito numa DA de 2 linhas e a legenda saía da faixa reservada a ela."""
        doc = cues.gerar(self.arq, projeto=self.proj, formato="vertical")["doc"]
        d = self.da.carregar(str(self.proj))
        self.assertEqual(d["legenda"]["max_linhas"], 2)
        longa = next(c for c in doc["cues"] if len(c["palavras"]) >= 3)
        with self.assertRaises(comum.Erro) as cm:
            cues.editar(doc, d, longa["id"], linhas=[1] * len(longa["palavras"]))
        self.assertEqual(cm.exception.codigo, 64)
        self.assertIn("legenda.max_linhas", cm.exception.mensagem)
        self.assertIn("--dividir", cm.exception.dica)
        r = apoio.rodar("cues.py", "editar", "legendas/fala.cues.json", "--cue", str(longa["id"]), "--linhas", ",".join(["1"] * len(longa["palavras"])), cwd=self.proj)
        self.assertEqual(r.returncode, 64, r.stderr)
        self.assertFalse(json.loads((self.proj / "legendas" / "fala.cues.json").read_text(encoding="utf-8"))["editado"])
        # arquivo mexido à mão com linhas a mais: é aceito, com aviso do tipo `linhas`
        cue = doc["cues"][longa["id"] - 1]
        cue["linhas"] = [[w["w"]] for w in cue["palavras"]]
        for n, w in enumerate(cue["palavras"]):
            w["linha"] = n
        outro, _ = cues.editar(doc, d, 1, destacar=[1])
        self.assertEqual([a["cue"] for a in outro["avisos"] if a["tipo"] == "linhas"], [longa["id"]])
        # no estilo `palavra` não há linhas para repartir
        proj = apoio.projeto(self.raiz, "neon-shorts", nome="proj linhas palavra")
        doc_p = cues.gerar(apoio.gravar_palavras(proj, apoio.palavras_sinteticas()), projeto=proj, formato="vertical")["doc"]
        duas = next(c for c in doc_p["cues"] if len(c["palavras"]) >= 2)
        with self.assertRaises(comum.Erro) as cm:
            cues.editar(doc_p, self.da.carregar(str(proj)), duas["id"], linhas=[1, len(duas["palavras"]) - 1])
        self.assertIn("palavra", cm.exception.mensagem)

    def test_48_escala_zero_e_erro_de_uso(self):
        """Regressão: `--escala 0` era lida como «sem escala» e renderizava em tamanho cheio."""
        for ruim in (0, 0.0, 5, -1):
            with self.assertRaises(comum.Erro, msg=str(ruim)) as cm:
                cues.gerar(self.arq, projeto=self.proj, formato="vertical", escala=ruim)
            self.assertEqual(cm.exception.codigo, 64)
        self.assertEqual(cues.gerar(self.arq, projeto=self.proj, formato="vertical", escala=1)["largura"], 1080)
        r = apoio.rodar("cues.py", "gerar", "--palavras", "transcricao/fala.palavras.json", "--formato", "vertical", "--escala", "0", cwd=self.proj)
        self.assertEqual(r.returncode, 64, r.stderr)

    def test_44_cli_em_pasta_com_espaco(self):
        r = apoio.rodar("cues.py", "gerar", "--palavras", "transcricao/fala.palavras.json", "--formato", "vertical", "--nome", "pela cli", cwd=self.proj)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("legendas/pela cli.cues.json", r.stdout)
        self.assertTrue((self.proj / "legendas" / "pela cli.srt").is_file())
        r = apoio.rodar("cues.py", "mostrar", "legendas/pela cli.cues.json", cwd=self.proj)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(" / ", r.stdout)                                                       # alguma cue em duas linhas
        r = apoio.rodar("cues.py", "editar", "legendas/pela cli.cues.json", "--cue", "1", "--palavra", "1", "--para", "No", cwd=self.proj)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(json.loads((self.proj / "legendas" / "pela cli.cues.json").read_text(encoding="utf-8"))["editado"])
        r = apoio.rodar("cues.py", "exportar", "legendas/pela cli.cues.json", cwd=self.proj)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_45_cli_erros_de_uso_e_projeto_sem_da(self):
        r = apoio.rodar("cues.py", "gerar", "--formato", "vertical", cwd=self.proj)
        self.assertEqual(r.returncode, 64, r.stderr)
        self.assertIn("faltam argumentos obrigatórios", r.stderr)
        self.assertNotIn("Traceback", r.stderr)
        r = apoio.rodar("cues.py", "gerar", "--palavras", "não existe.json", "--formato", "vertical", cwd=self.proj)
        self.assertEqual(r.returncode, 1)
        self.assertIn("não encontrado", r.stderr)
        r = apoio.rodar("cues.py", "editar", "legendas/x.cues.json", "--cue", "um", cwd=self.proj)
        self.assertEqual(r.returncode, 64)
        sem = self.raiz / "pasta sem direção de arte"
        (sem / "transcricao").mkdir(parents=True, exist_ok=True)
        (sem / "transcricao" / "f.json").write_text(json.dumps(apoio.palavras_sinteticas()), encoding="utf-8")
        r = apoio.rodar("cues.py", "gerar", "--palavras", "transcricao/f.json", "--formato", "vertical", cwd=sem)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("video-direcao-de-arte", r.stderr)
        self.assertNotIn("Traceback", r.stderr)
        r = apoio.rodar("cues.py", "--help", cwd=sem)
        self.assertEqual(r.returncode, 0)
        self.assertIn("uso:", r.stdout)


if __name__ == "__main__":
    unittest.main()
