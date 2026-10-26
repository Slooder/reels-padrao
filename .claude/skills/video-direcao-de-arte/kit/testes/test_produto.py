#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Regressões do PRODUTO visual e do método (decisões D18–D21): vertical sem colisão por padrão, GC legível sobre
footage, rotas como recurso de primeira classe, prancha que representa a produção, teste de movimento que não corta
animação, `extrair` que acha a cor de acento e validador que acusa DA incoerente.

Rodar a partir do kit:  python3 -m unittest testes.test_produto -v
Pasta temporária com espaço e acento, VIDEO_OPS_HOME isolado, trava global de verdade. Os renders são quadros PNG a
270×480 / 480×270; o único vídeo é um ato do teste de movimento (≈ 2 s a 270×480).
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
if str(KIT) not in sys.path:
    sys.path.insert(0, str(KIT))
import da  # noqa: E402
import da_ext_motor as motor  # noqa: E402
import texto  # noqa: E402

PRESETS = ("dossie", "lab-ia", "editorial-claro", "neon-shorts", "quadro-negro")
PY = sys.executable


def editar(da_json: Path, fn) -> None:
    dados = json.loads(da_json.read_text(encoding="utf-8"))
    fn(dados)
    da_json.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")


def cruzam(a, b, folga: float = 0.5) -> bool:
    """Dois retângulos (x0, y0, x1, y1) se sobrepõem?"""
    return a[0] < b[2] - folga and b[0] < a[2] - folga and a[1] < b[3] - folga and b[1] < a[3] - folga


def ret(r: dict) -> tuple:
    """Retângulo de layout do motor ({x, y, x1, y1} ou {x0, y0, x1, y1}) → tupla."""
    return (r["x0"], r["y0"], r["x1"], r["y1"]) if "x0" in r else (r["x"], r["y"], r["x1"], r["y1"])


def imagem_footage(destino: Path, largura=540, altura=960) -> Path:
    """Quadro que imita footage CLARO e movimentado (o pior caso para texto sem apoio): faixas claras, pele e tecido."""
    import numpy as np
    from PIL import Image
    y, x = np.mgrid[0:altura, 0:largura]
    # da-livre:inicio — pixels de teste que imitam footage; não é peça
    base = np.stack([200 + 40 * np.sin(x / 37.0), 190 + 40 * np.cos(y / 53.0), 170 + 50 * np.sin((x + y) / 29.0)], -1)
    base[altura // 3: altura // 2] = (225, 180, 150)
    # da-livre:fim
    destino.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.clip(base, 0, 255).astype("uint8"), "RGB").save(destino)
    return destino


def cartela_com_marca_texto(destino: Path) -> Path:
    """Referência de design: cartela preta, texto claro e um marca-texto amarelo que ocupa ≈ 0,7 % da área."""
    from PIL import Image, ImageDraw, ImageFilter
    # da-livre:inicio — referência sintética para o `extrair`
    im = Image.new("RGB", (1920, 1080), (14, 14, 14))
    d = ImageDraw.Draw(im)
    d.rectangle([160, 300, 900, 360], fill=(238, 236, 228))
    d.rectangle([160, 420, 520, 458], fill=(246, 198, 20))
    d.rectangle([160, 500, 600, 540], fill=(138, 165, 174))
    # da-livre:fim
    destino.parent.mkdir(parents=True, exist_ok=True)
    im.filter(ImageFilter.GaussianBlur(0.8)).save(destino, quality=90)
    return destino


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = Path(tempfile.mkdtemp(prefix="da produto é ")).resolve()
        cls._env = {k: os.environ.get(k) for k in ("VIDEO_OPS_HOME", "DA_JSON")}
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
            da.iniciar(pasta, nome=f"Produto {chave}", base=preset)
            cls.projetos[chave] = pasta
        return cls.projetos[chave]

    def cli(self, *args, cwd=None):
        r = subprocess.run([PY, str(KIT / "da.py"), *[str(a) for a in args]], cwd=str(cwd) if cwd else None, capture_output=True,
                           text=True, env=os.environ.copy(), stdin=subprocess.DEVNULL, timeout=300)
        return r.returncode, r.stdout, r.stderr

    def validar(self, raiz: Path):
        r = da.validar(raiz / "da" / "da.json")
        return r["erros"], r["avisos"]


# ══════════════════════════════════════════════════ validador e geometria (sem browser) ══
class TesteValidadorEGeometria(Base):
    def test_01_presets_validam_limpos_e_respeitam_o_minimo_legivel(self):
        """Era: cargo do GC e crédito com 17–20 px em 4 presets (6–7 pt num celular), e nada avisava."""
        for preset in PRESETS:
            with self.subTest(preset=preset):
                r = da.validar(da.achar_preset(preset))
                self.assertEqual((r["erros"], r["avisos"]), ([], []))
                d = da.carregar(self.projeto(preset))
                for v in (d["graficos"]["gc"]["tamanho_cargo"], d["graficos"]["citacao_fonte"]["tamanho"], d["tipografia"]["escala"]["nota"]):
                    self.assertGreaterEqual(v, da.MINIMO_LEGIVEL)
                self.assertGreaterEqual(d["legenda"]["tamanho"], da.MINIMO_LEGENDA)

    def test_02_validador_avisa_texto_abaixo_do_minimo(self):
        raiz = self.projeto("dossie", " mínimo")
        editar(raiz / "da/da.json", lambda j: (j["graficos"]["gc"].update(tamanho_cargo=0.018), j["graficos"]["citacao_fonte"].update(tamanho=0.016),
                                               j["legenda"].update(tamanho=0.03)))
        erros, avisos = self.validar(raiz)
        self.assertEqual(erros, [])
        txt = "\n".join(avisos)
        self.assertIn("graficos.gc.tamanho_cargo = 0,018: abaixo do mínimo legível", txt)
        self.assertIn("graficos.citacao_fonte.tamanho = 0,016", txt)
        self.assertIn("legenda.tamanho = 0,03", txt)
        self.assertIn("pt", txt)                                    # a mensagem diz o tamanho no celular

    def test_03_validador_avisa_gc_sobre_a_legenda(self):
        """Era: GC e legenda sobrepostos no vertical dos 5 presets e `validar` respondia "Sem erros nem avisos"."""
        raiz = self.projeto("dossie", " colisão")
        editar(raiz / "da/da.json", lambda j: (j["legenda"].update(max_linhas=6, tamanho=0.12), j["legenda"]["posicao"]["vertical"].update(y=0.4)))
        _, avisos = self.validar(raiz)
        self.assertTrue(any(a.startswith("legenda × GC no vertical") and "se sobrepõem" in a for a in avisos), avisos)
        # horizontal só entra na conta quando a DA diz que o horizontal leva legenda queimada
        self.assertFalse(any(a.startswith("legenda × GC no horizontal") for a in avisos), avisos)

    def test_13_formato_sem_reserva_avisa_no_vertical_e_anota_no_horizontal(self):
        """Fecho. Era: no horizontal o GC nascia em cima da legenda e `validar` dizia "Sem erros nem avisos"; com
        `legenda.reservar_em: []` (reserva desligada também no vertical) continuava com 0 avisos."""
        for preset in PRESETS:
            with self.subTest(preset=preset):
                r = da.validar(da.achar_preset(preset))
                self.assertEqual(r["avisos"], [])                       # o padrão segue limpo…
                self.assertEqual(len(r["notas"]), 1, r["notas"])        # …mas diz o que o horizontal entrega
                self.assertTrue(r["notas"][0].startswith("horizontal sem reserva de legenda"), r["notas"])
                self.assertIn('inclua "horizontal" em legenda.reservar_em', r["notas"][0])
                d = da.carregar(self.projeto(preset))
                self.assertFalse(d.legenda_reservada("horizontal")); self.assertTrue(d.legenda_reservada("vertical"))
                # quem queima a legenda recebe a mesma resposta junto com a imagem (texto.compor_legenda → info)
                reservas = [texto.compor_legenda(["a", "conta"], texto.Estilo.legenda(d, L, A), d, L, A, recortar=True)[1]["faixa_reservada"]
                            for L, A in ((1920, 1080), (1080, 1920), (1080, 1080))]
                self.assertEqual(reservas, [False, True, True])
                # e o DA.md (lido por toda sessão via CLAUDE.md) diz a mesma coisa em português
                md = (d.pasta / "DA.md").read_text(encoding="utf-8")
                self.assertIn("Faixa da legenda reservada (GC, crédito, título e gráficos desviam dela) em: vertical, quadrado.", md)
                self.assertIn("Em horizontal as peças **não** desviam", md)
                # a nota fala da mesma geometria que a produção usa: GC na base da zona, dentro da faixa da legenda
                zona, faixa = d.margens("horizontal"), d.faixa_legenda("horizontal")
                g = da.caixa_gc_estimada(d, 1920, 1080, zona)
                self.assertEqual(g[3], zona["y1"]); self.assertTrue(cruzam(g, ret(faixa)), (g, faixa))
        raiz = self.projeto("dossie", " sem reserva")
        editar(raiz / "da/da.json", lambda j: j["legenda"].update(reservar_em=[]))
        r = da.validar(raiz / "da/da.json")
        self.assertEqual(r["erros"], [])
        for fmt in ("vertical", "quadrado"):
            self.assertTrue(any(a.startswith(f"legenda × GC no {fmt}") and "não está em legenda.reservar_em" in a and "se sobrepõem" in a
                                for a in r["avisos"]), (fmt, r["avisos"]))
        self.assertFalse(any("no horizontal" in a for a in r["avisos"]), r["avisos"])        # horizontal: nota, não aviso
        self.assertEqual(len(r["notas"]), 1)
        rc, out, _ = self.cli("validar", cwd=raiz)
        self.assertEqual(rc, 0); self.assertIn("AVISOS (2)", out); self.assertIn("NOTAS (1)", out)
        rc, _, _ = self.cli("validar", "--estrito", cwd=raiz)
        self.assertEqual(rc, 1)
        # GC e legenda que não se tocam (legenda no alto) não geram nada, mesmo sem reserva
        editar(raiz / "da/da.json", lambda j: (j["legenda"]["posicao"]["vertical"].update(y=0.3), j["legenda"]["posicao"]["horizontal"].update(y=0.3)))
        r = da.validar(raiz / "da/da.json")
        self.assertEqual((r["avisos"], r["notas"]), ([], []))
        # com o horizontal reservado, a nota some (e nenhuma nota reprova em --estrito)
        raiz2 = self.projeto("dossie", " horizontal reservado")
        editar(raiz2 / "da/da.json", lambda j: j["legenda"].update(reservar_em=["vertical", "quadrado", "horizontal"]))
        r = da.validar(raiz2 / "da/da.json")
        self.assertEqual((r["erros"], r["avisos"], r["notas"]), ([], [], []))
        md = (da.carregar(raiz2).pasta / "DA.md").read_text(encoding="utf-8")
        self.assertIn("em: vertical, quadrado, horizontal.", md); self.assertNotIn("**não** desviam", md)
        rc, out, _ = self.cli("validar", "--estrito", cwd=self.projeto("neon-shorts"))
        self.assertEqual(rc, 0, out); self.assertIn("Sem erros nem avisos.", out); self.assertIn("NOTAS (1)", out)

    def test_04_faixa_da_legenda_e_area_livre_nos_cinco_presets(self):
        """D18: no vertical, a área livre das cenas termina antes da faixa da legenda e cabe o GC inteiro."""
        for preset in PRESETS:
            with self.subTest(preset=preset):
                d = da.carregar(self.projeto(preset))
                zona, faixa, area = d.margens("vertical"), d.faixa_legenda("vertical"), d.area_livre("vertical")
                self.assertTrue(area["reservou"])
                self.assertGreaterEqual(faixa["y0"], zona["y0"]); self.assertLessEqual(faixa["y1"], zona["y1"] + 0.5 + faixa["tamanho"])
                self.assertGreaterEqual(faixa["x0"], zona["x0"] - 0.5); self.assertLessEqual(faixa["x1"], zona["x1"] + 0.5)
                self.assertLessEqual(area["y1"], faixa["y0"])        # a área livre fica ACIMA da faixa
                self.assertGreaterEqual(area["altura"], da._altura_gc_estimada(d, 1080))
                self.assertFalse(d.area_livre("horizontal")["reservou"])          # padrão: horizontal não leva legenda queimada
                self.assertTrue(d.area_livre("horizontal", legenda=True)["reservou"])
                self.assertFalse(d.area_livre("thumbnail")["reservou"])
        # com "horizontal" em legenda.reservar_em, o horizontal passa a reservar sozinho
        raiz = self.projeto("dossie", " reserva")
        editar(raiz / "da/da.json", lambda j: j["legenda"].update(reservar_em=["vertical", "quadrado", "horizontal"]))
        self.assertTrue(da.carregar(raiz).area_livre("horizontal")["reservou"])

    def test_05_gc_linha_sem_protecao_e_contraste_do_gc(self):
        """D19: estilo 'linha' sem apoio é avisado; o padrão ('auto') protege com o painel em cor_fundo."""
        raiz = self.projeto("editorial-claro", " gc")
        self.assertEqual(da.carregar(raiz)["graficos"]["gc"]["protecao"], "auto")
        editar(raiz / "da/da.json", lambda j: j["graficos"]["gc"].update(protecao="nenhuma"))
        _, avisos = self.validar(raiz)
        self.assertTrue(any("estilo 'linha' com protecao 'nenhuma'" in a for a in avisos), avisos)
        editar(raiz / "da/da.json", lambda j: j["graficos"]["gc"].update(protecao="contorno", cor_cargo="fundo"))
        _, avisos = self.validar(raiz)
        self.assertTrue(any("graficos.gc.cor_cargo: contraste de 1:1 sobre cor_fundo" in a for a in avisos), avisos)
        editar(raiz / "da/da.json", lambda j: j["graficos"]["gc"].update(protecao="holofote"))
        erros, _ = self.validar(raiz)
        self.assertTrue(any("graficos.gc.protecao" in e for e in erros), erros)

    def test_06_rota_do_exemplo_antigo_do_skill_md_agora_e_acusada(self):
        """Era: herda neon-shorts + primaria e destaque #FF2D95 → secundária quase idêntica, gradiente chapado, e `validar` limpo."""
        raiz = self.projeto("dossie", " rotas")
        rota = raiz / "da/rotas/rota-b/da/da.json"
        rota.parent.mkdir(parents=True)
        rota.write_text(json.dumps({"versao_esquema": 1, "herda": "neon-shorts",
                                    "projeto": {"nome": "Rota B", "slug": "rota-b", "criada_em": "2026-10-05", "revisao": 1, "aprovada": False,
                                                "aprovada_em": None, "aprovada_sha256": None},
                                    "conceito": {"frase": "Rota B."}, "cor": {"paleta": {"primaria": "#FF2D95", "destaque": "#FF2D95"}}}), encoding="utf-8")
        r = da.validar(rota)
        self.assertEqual(r["erros"], [])
        txt = "\n".join(r["avisos"])
        self.assertIn("primaria #FF2D95 e secundaria #FF2E93 são quase idênticas", txt)
        self.assertIn("cor.gradientes.choque: todas as paradas resolvem para #FF2D95", txt)
        # e a série de dados acompanhou a troca: dado-1 é o token "primaria", não o verde-limão do preset
        d = da.carregar(rota)
        self.assertEqual(d.cor("dado-1"), "#FF2D95")
        self.assertEqual(d["cor"]["dados_tokens"][0], "primaria")

    def test_07_cor_dados_aceita_token_e_recusa_nome_que_nao_existe(self):
        raiz = self.projeto("dossie", " dados")
        editar(raiz / "da/da.json", lambda j: j["cor"]["paleta"].update(primaria="#F6C614"))
        d = da.carregar(raiz)
        self.assertEqual((d.cor("dado-1"), d["cor"]["dados"][0]), ("#F6C614", "#F6C614"))
        self.assertIn("#F6C614", d["cor"]["permitidas"])
        self.assertIn("--da-dado-1:#F6C614;", d.css.read_text(encoding="utf-8"))
        editar(raiz / "da/da.json", lambda j: j["cor"]["dados"].__setitem__(1, "#F6C714"))       # hex quase igual à primária
        _, avisos = self.validar(raiz)
        self.assertTrue(any("cor.dados.1 #F6C714 é quase a cor primaria" in a for a in avisos), avisos)
        editar(raiz / "da/da.json", lambda j: j["cor"]["dados"].__setitem__(1, "primeira"))
        erros, _ = self.validar(raiz)
        self.assertTrue(any("cor.dados.1" in e and "primaria" in e for e in erros), erros)
        editar(raiz / "da/da.json", lambda j: j["cor"]["dados"].__setitem__(1, "secundaria"))
        editar(raiz / "da/da.json", lambda j: j["cor"]["paleta"].update(secundaria="#F6C614"))     # dois tokens com a mesma cor: aviso, não erro
        erros, avisos = self.validar(raiz)
        self.assertEqual(erros, [])
        self.assertTrue(any("itens que resolvem para a mesma cor" in a for a in avisos), avisos)

    def test_08_credito_em_pil_fica_acima_da_faixa_da_legenda(self):
        for preset in ("dossie", "lab-ia", "neon-shorts"):
            with self.subTest(preset=preset):
                d = da.carregar(self.projeto(preset))
                _, info = texto.credito_fonte(d, "Tesouro Nacional, 2024", 1080, 1920, recortar=True)
                faixa, zona = d.faixa_legenda("vertical"), d.margens("vertical")
                self.assertFalse(cruzam(info["caixa"], ret(faixa)), (info["caixa"], faixa))
                self.assertGreaterEqual(info["caixa"][0], zona["x0"]); self.assertLessEqual(info["caixa"][2], zona["x1"])
                self.assertGreaterEqual(info["caixa"][1], zona["y0"]); self.assertLessEqual(info["caixa"][3], zona["y1"])
                self.assertFalse(info["texto"].startswith("Fonte: Fonte"))
        _, info = texto.credito_fonte(da.carregar(self.projeto("dossie")), "Fonte: IBGE", 1080, 1920, recortar=True)
        self.assertEqual(info["texto"], "Fonte: IBGE")                # prefixo nunca duplica

    def test_09_plano_do_teste_de_movimento_sai_das_duracoes_da_da(self):
        """Era: tempos em fração fixa de 4 s — em preset lento as barras paravam em valores errados."""
        for preset in PRESETS:
            with self.subTest(preset=preset):
                d = da.carregar(self.projeto(preset))
                p = motor.duracao_do_teste(d)
                du, e = d["movimento"]["duracoes"], d["movimento"]["escalonamento"]
                entrada_barras = 0.05 + 10 * e + du["longa"] + 0.5 * du["media"]
                self.assertGreater(p["total"], entrada_barras + du["longa"])          # cabe a entrada inteira das barras e a do título
                self.assertAlmostEqual(p["total"], p["natural"], places=3)
                curto = motor.duracao_do_teste(d, pedida=1.0)
                self.assertAlmostEqual(curto["total"], curto["minima"], places=3)     # --dur não corta animação: vale o mínimo
                self.assertAlmostEqual(curto["respiro"], 0.2, places=3)
                longo = motor.duracao_do_teste(d, pedida=p["natural"] + 3)
                self.assertAlmostEqual(longo["total"], p["natural"] + 3, places=2)    # --dur maior só estica os respiros
                so_gc = motor.duracao_do_teste(d, atos=["gc"])
                self.assertEqual(so_gc["atos"], ["gc"]); self.assertLess(so_gc["total"], 3.0)
        self.assertGreater(motor.duracao_do_teste(da.carregar(self.projeto("editorial-claro")))["total"],
                           motor.duracao_do_teste(da.carregar(self.projeto("neon-shorts")))["total"] + 2)


# ════════════════════════════════════════════════════════════ extrair (sem browser) ══
class TesteExtrair(Base):
    def test_10_acento_pequeno_vira_a_primaria(self):
        """Era: cartela preta com marca-texto amarelo (0,66 % da área) → primária #A16748 (pele/madeira), sem amarelo na paleta."""
        ref = cartela_com_marca_texto(self.base / "refs é" / "ref 01 cartela.jpg")
        a = da.extrair([ref], saida=self.base / "saida 1")
        ac = a["geral"]["acentos"]
        self.assertTrue(ac, "nenhum acento encontrado")
        self.assertLess(da.delta_e(ac[0]["hex"], "#F6C614"), 12, ac)
        self.assertLess(ac[0]["area"], 0.02)
        prim = a["geral"]["candidatos"]["primaria"]
        self.assertEqual(prim["hex"], ac[0]["hex"])
        self.assertIn("acento", prim["motivo"])
        self.assertTrue(Path(a["_arquivos"]["folha"]).is_file())

    def test_11_sem_acento_o_candidato_avisa_que_pode_ser_pele(self):
        from PIL import Image
        # da-livre:inicio — "footage" sintético só com tons de pele e madeira (croma baixo)
        im = Image.new("RGB", (640, 360), (26, 30, 32))
        im.paste((215, 166, 142), (200, 80, 420, 300))
        im.paste((107, 70, 43), (0, 250, 640, 360))
        # da-livre:fim
        ref = self.base / "refs é" / "bruto falso.png"
        ref.parent.mkdir(parents=True, exist_ok=True)
        im.save(ref)
        a = da.extrair([ref], saida=self.base / "saida 2")
        self.assertEqual(a["geral"]["acentos"], [])
        self.assertIn("NENHUMA cor de acento", a["geral"]["candidatos"]["primaria"]["motivo"])
        self.assertTrue(any("Nenhuma cor de acento" in l for l in a["geral"]["leitura"]))

    def test_12_pasta_regiao_e_saidas_proprias(self):
        pasta = self.base / "refs pasta"
        cartela_com_marca_texto(pasta / "ref 01.jpg")
        a = da.extrair([pasta], saida=pasta)                         # 1ª vez: grava a folha DENTRO da pasta de referências
        self.assertEqual(len(a["referencias"]), 1)
        b = da.extrair([pasta], saida=pasta)                         # 2ª vez: a folha e a análise não viram referência
        self.assertEqual(len(b["referencias"]), 1)
        self.assertEqual(len(b["ignoradas"]), 1)                     # só a folha é imagem; a análise .json nem entra na lista
        c = da.extrair([pasta / "ref 01.jpg"], saida=self.base / "saida 3", regiao="0.08,0.38,0.2,0.05")
        self.assertLess(da.delta_e(c["geral"]["candidatos"]["primaria"]["hex"], "#F6C614"), 12)
        self.assertGreater(c["geral"]["acentos"][0]["area"], 0.4)    # no recorte, o marca-texto é quase tudo
        with self.assertRaises(da.DAErro):
            da.extrair([pasta / "ref 01.jpg"], saida=self.base / "saida 3", regiao="0.9,0.9,0.5,0.5")
        rc, out, err = self.cli("extrair", pasta, "--saida", self.base / "saida 4")
        self.assertEqual(rc, 0, err)
        self.assertIn("Acentos (cores vivas", out)


# ═══════════════════════════════════════════════════ rotas e aprovação (sem browser) ══
class TesteRotasEAprovacao(Base):
    def test_20_criar_listar_e_adotar_rota(self):
        raiz = self.projeto("dossie", " com rotas")
        da_json = raiz / "da" / "da.json"
        editar(da_json, lambda j: j["conceito"].update(referencias=[{"arquivo": "referencias/ref 01.jpg", "nota": "marca-texto amarelo"}]))
        cartela_com_marca_texto(raiz / "da/referencias/ref 01.jpg")
        a = da.criar_rota("rota-a", base="editorial-claro", frase="Rota A: papel quente.", cores={"primaria": "#C1121F"}, caminho=raiz)
        self.assertEqual(a["erros"], [])
        self.assertTrue((raiz / "da/rotas/rota-a/da/da.json").is_file())
        self.assertFalse((raiz / "da/rotas/rota-a/bruto").exists())          # rota não ganha pastas de trabalho
        b = da.criar_rota("rota-b", cores={"primaria": "#F6C614", "destaque": "#F6C614"}, caminho=raiz)     # herda a DA atual do projeto
        self.assertEqual((b["erros"], b["avisos"]), ([], []))
        self.assertEqual(da.carregar(b["da_json"]).cor("dado-1"), "#F6C614")
        with self.assertRaises(da.DAErro):
            da.criar_rota("rota-a", base="lab-ia", caminho=raiz)             # já existe
        with self.assertRaises(da.DAErro):
            da.criar_rota("Rota C", caminho=raiz)                            # nome inválido
        with self.assertRaises(da.DAErro):
            da.criar_rota("rota-c", base="nao-existe", caminho=raiz)         # preset inexistente: nada é criado
        self.assertFalse((raiz / "da/rotas/rota-c").exists())
        # a rota enxerga as referências do projeto-pai (era: 2 avisos "arquivo não encontrado" dentro da rota)
        editar(b["da_json"], lambda j: j["conceito"].update(referencias=[{"arquivo": "referencias/ref 01.jpg", "nota": "idem"}]))
        r = da.validar(b["da_json"])
        self.assertEqual((r["erros"], r["avisos"]), ([], []))
        self.assertEqual(da.projeto_pai(b["da_json"]), raiz)
        self.assertIsNone(da.projeto_pai(da_json))
        rotas = da.listar_rotas(caminho=raiz)
        self.assertEqual([x["nome"] for x in rotas], ["rota-a", "rota-b"])
        self.assertEqual(rotas[0]["prancha"], {"horizontal": "ausente", "vertical": "ausente"})
        rc, out, _ = self.cli("rotas", "listar", cwd=raiz)
        self.assertEqual(rc, 0); self.assertIn("rota-a", out); self.assertIn("Rota A: papel quente.", out)
        rc, out, _ = self.cli("rotas", "listar", cwd=raiz / "da/rotas/rota-a/da")     # de dentro da rota, lista as do projeto
        self.assertEqual(rc, 0); self.assertIn("rota-b", out)
        # adotar: backup, fontes copiadas, projeto preservado, sem passar pela biblioteca pessoal
        sha_rota = da.carregar(a["da_json"]).sha256
        r = da.adotar_rota("rota-a", caminho=raiz)
        d = da.carregar(raiz)
        self.assertEqual(d.sha256, sha_rota)                                 # a identidade visual é a da rota
        self.assertEqual((d["projeto"]["nome"], d["projeto"]["rota_adotada"], d["projeto"]["base"]), ("Produto dossie com rotas", "rota-a", "editorial-claro"))
        self.assertTrue(r["backup"].is_file())
        self.assertTrue((raiz / "da/fontes/Montserrat-Variable.ttf").is_file())
        self.assertTrue((raiz / "da/fontes/LICENCAS/OFL-Montserrat.txt").is_file())
        self.assertTrue(str(d.fonte("titulo")["caminho"]).startswith(str(raiz)))      # as fontes resolvem para o projeto, não para o kit
        self.assertEqual(d["conceito"]["referencias"][0]["arquivo"], "referencias/ref 01.jpg")   # referências do projeto ficam
        self.assertIn("ArchivoSemiExpanded-Black.ttf", [x.name for x in r["orfas"]])   # fonte da base anterior: avisada, não apagada
        self.assertEqual([x["nome"] for x in da.listar_presets() if x["origem"] == "pessoal"], [])
        self.assertIn("editorial-claro", (raiz / "CLAUDE.md").read_text(encoding="utf-8"))
        rc, _, err = self.cli("rotas", "adotar", "nao-existe", cwd=raiz)
        self.assertEqual(rc, 1); self.assertIn("rota-a", err)

    def test_21_aprovar_confere_prancha_e_teste_de_movimento(self):
        """Era: `aprovar` numa DA sem prancha nem teste respondia "DA aprovada" e pronto."""
        raiz = self.projeto("dossie", " aprovação")
        docs = da.documentos_de_aprovacao(raiz)
        self.assertEqual({d["estado"] for d in docs.values()}, {"ausente"})
        rc, out, err = self.cli("aprovar", "--estrito", cwd=raiz)
        self.assertEqual(rc, 1, out)
        self.assertIn("NÃO foi aprovada", err)
        self.assertFalse(da.carregar(raiz).aprovada)
        # documento carimbado com a DA atual = em dia; depois de mexer num token, desatualizado
        d = da.carregar(raiz)
        for nome in da.DOCUMENTOS_DE_APROVACAO:
            (d.pasta / nome).write_bytes(b"x")
            d.carimbar(d.pasta / nome, "teste", "vertical")
        self.assertEqual({x["estado"] for x in da.documentos_de_aprovacao(raiz).values()}, {"em dia"})
        editar(raiz / "da/da.json", lambda j: j["legenda"].update(tamanho=0.06))
        self.assertEqual({x["estado"] for x in da.documentos_de_aprovacao(raiz).values()}, {"desatualizada"})
        rc, out, _ = self.cli("aprovar", "--sem-prancha", cwd=raiz)
        self.assertEqual(rc, 0)                                              # sem --estrito aprova, mas avisa
        self.assertIn("nenhuma prancha em dia", out)
        self.assertIn("teste de movimento desatualizado", out)
        self.assertTrue(da.carregar(raiz).aprovada)

    def test_22_remover_preset_pessoal_e_fontes_orfas_no_init_forcar(self):
        raiz = self.projeto("dossie", " preset")
        da.salvar_preset("rota-escolhida", caminho=raiz)
        self.assertIn("rota-escolhida", [x["nome"] for x in da.listar_presets()])
        rc, out, _ = self.cli("remover-preset", "rota-escolhida")
        self.assertEqual(rc, 0, out)
        self.assertNotIn("rota-escolhida", [x["nome"] for x in da.listar_presets()])
        rc, _, err = self.cli("remover-preset", "dossie")
        self.assertEqual(rc, 1); self.assertIn("embutido", err)
        info = da.iniciar(raiz, base="neon-shorts", forcar=True)             # troca de base: as fontes antigas ficam e são avisadas
        self.assertTrue(any("que a DA não usa mais" in a and "ArchivoSemiExpanded-Black.ttf" in a for a in info["avisos"]), info["avisos"])


# ═════════════════════════════════════════════════════════════════ motor (browser) ══
class TesteMotorProduto(Base):
    def render(self, d, *args, esperado=0):
        r = motor.render([str(a) for a in args], da_obj=d, cwd=d.raiz, capturar=True)
        if r.returncode != esperado:
            self.fail(f"render devolveu {r.returncode} (esperava {esperado})\nSTDOUT:\n{r.stdout}\nSTDERR:\n{r.stderr}")
        return r

    def layout(self, saida) -> dict:
        return da.ler_carimbo(saida)["parametros"]["layout"]

    def test_30_vertical_sem_colisao_e_dentro_da_uniao_nos_cinco_presets(self):
        """D18: GC, cartela (com assinatura), barras com 8 categorias + crédito, citação com autor longo e moldura, todos
        na zona `uniao` e fora da faixa da legenda — por padrão, sem nenhum parâmetro de posição."""
        oito = [{"rotulo": f"Estado número {i + 1}", "valor": 0.3 + 0.37 * i} for i in range(8)]
        for preset in PRESETS:
            raiz = self.projeto(preset, " vertical")
            editar(raiz / "da/da.json", lambda j: j["marca"].update(assinatura="@canal.teste"))
            d = da.carregar(raiz)
            jobs = [
                {"cena": "gc", "saida": "_v gc.png", "quadro": 2.5, "params": {"nome": "Mariana Albuquerque", "cargo": "Procuradora de Justiça", "selo": "ao vivo"}},
                {"cena": "titulo", "saida": "_v titulo.png", "quadro": 2.5, "params": {"titulo": "A conta que não fecha", "sobretitulo": "Capítulo 2", "subtitulo": "Como o dinheiro some no caminho até Brasília"}},
                {"cena": "barras", "saida": "_v barras.png", "quadro": 5.0, "params": {"titulo": "Quanto cada estado recebe de volta por real enviado", "dados": oito, "fonte": "Fonte: Tesouro Nacional, 2024", "prefixo": "R$ ", "casas": 2}},
                {"cena": "citacao", "saida": "_v citacao.png", "quadro": 4.0, "params": {"texto": "O dinheiro sai daqui e não volta na mesma proporção.", "autor": "Mariana Albuquerque de Vasconcelos Sobrinho", "cargo": "Procuradora de Justiça do Estado de Santa Catarina", "fonte": "Folha, 2024"}},
                {"cena": "moldura", "saida": "_v moldura.png", "quadro": 3.0, "params": {"rotulo": "Arquivo · 2018", "sub": "Reprodução"}},
            ]
            for j in jobs:
                j.update(formato="vertical", escala=0.25)
            fila = raiz / "animacoes" / "_fila vertical.json"
            fila.write_text(json.dumps(jobs, ensure_ascii=False), encoding="utf-8")
            self.render(d, "--fila", fila)
            zona, faixa = d.margens("vertical"), ret(d.faixa_legenda("vertical"))
            z = (zona["x0"], zona["y0"], zona["x1"], zona["y1"])

            def dentro(r, nome, folga=1.5):
                self.assertTrue(r[0] >= z[0] - folga and r[1] >= z[1] - folga and r[2] <= z[2] + folga and r[3] <= z[3] + folga,
                                f"{preset}: {nome} {tuple(round(v) for v in r)} fora da zona uniao {z}")
                self.assertFalse(cruzam(r, faixa), f"{preset}: {nome} {tuple(round(v) for v in r)} em cima da faixa da legenda {faixa}")

            with self.subTest(preset=preset):
                gc = self.layout(raiz / "animacoes" / "_v gc.png")
                dentro(ret(gc["caixa"]), "GC")
                self.assertTrue(gc["reservou_legenda"])
                for k, v in zip(faixa, ret(gc["faixa_legenda"])):
                    self.assertAlmostEqual(k, v, delta=0.6)          # mesma faixa em Python (d.faixa_legenda) e no motor (ctx.faixa_legenda)
                tit = self.layout(raiz / "animacoes" / "_v titulo.png")
                dentro(ret(tit["bloco"]), "bloco do título")
                bar = self.layout(raiz / "animacoes" / "_v barras.png")
                dentro(ret(bar["bloco"]), "bloco das barras"); dentro(ret(bar["credito"]), "crédito das barras")
                self.assertFalse(cruzam(ret(bar["bloco"]), ret(bar["credito"])), f"{preset}: crédito sobre o gráfico")
                self.assertEqual(bar["cores"], "primaria")           # 8 barras > cores da série: uma cor só, sem repetir
                cit = self.layout(raiz / "animacoes" / "_v citacao.png")
                dentro(ret(cit["bloco"]), "bloco da citação (com autor e cargo longos)"); dentro(ret(cit["credito"]), "crédito da citação")
                mol = self.layout(raiz / "animacoes" / "_v moldura.png")
                self.assertTrue(mol["rotulo_na_zona"], f"{preset}: rótulo da moldura fora da zona")
                for nome in ("rotulo", "sub"):
                    if mol.get(nome):
                        dentro(ret(mol[nome]), f"{nome} da moldura", folga=6)

    def test_38_moldura_quebra_ou_encolhe_rotulo_e_sub_nos_cinco_estilos(self):
        """Fecho. Era: rótulo de 37 caracteres saía da zona `uniao` em todos os estilos (até x 514 contra 390), o sub da
        janela e da polaroid ia até x 636–670 num quadro de 540 (cortado na borda) e o carimbo dizia rotulo_na_zona: true."""
        raiz = self.projeto("quadro-negro", " moldura longa")
        d = da.carregar(raiz)
        textos = {"longo": {"rotulo": "ARQUIVO PESSOAL · FLORIANÓPOLIS · 2018 · A", "sub": "Reprodução / TV Globo · Jornal"},      # 40 e 29 caracteres
                  "curto": {"rotulo": "Reprodução / TV Globo · 2018", "sub": "Arquivo pessoal"},
                  "só sub": {"sub": "Reprodução / TV Globo · Jornal do Almoço · 2018"}}
        estilos = ("nenhuma", "borda", "cantoneiras", "janela", "polaroid")
        jobs = [{"cena": "moldura", "saida": f"_m {e} {t} {f}.png", "formato": f, "quadro": 2, "dur": 4, "params": {**p, "estilo": e}}
                for e in estilos for t, p in textos.items() for f in ("540x960", "960x540")]
        jobs.append({"cena": "moldura", "saida": "_m fora.png", "formato": "540x960", "quadro": 2, "dur": 4,
                     "params": {"rotulo": "Arquivo", "sub": "2018", "estilo": "janela", "area": [0.0, 0.0, 1.0, 0.5]}})
        fila = raiz / "animacoes" / "_fila moldura.json"
        fila.write_text(json.dumps(jobs, ensure_ascii=False), encoding="utf-8")
        self.render(d, "--fila", fila)
        for j in jobs[:-1]:
            lay = self.layout(raiz / "animacoes" / j["saida"])
            L, A = (int(v) for v in j["formato"].split("x"))
            z = lay["zona"]
            with self.subTest(peca=j["saida"]):
                self.assertTrue(lay["rotulo_na_zona"], lay)
                rets = [ret(lay[k]) for k in ("rotulo", "sub") if lay.get(k)]
                self.assertEqual(len(rets), len(j["params"]) - 1)
                for q in rets:                                         # dentro da zona segura (e, portanto, do quadro); 2 px pelo giro da polaroid
                    self.assertTrue(q[0] >= z["x"] - 2 and q[1] >= z["y"] - 2 and q[2] <= z["x1"] + 2 and q[3] <= z["y1"] + 2, (q, z))
                    self.assertTrue(q[2] <= L and q[3] <= A)
                if len(rets) == 2:
                    # na polaroid os retângulos são as caixas JÁ GIRADAS (−1,5°): o giro incha cada uma em largura × sen(1,5°)
                    giro = 2 + abs(lay["inclinacao"]) * 3.1416 / 180 * max(q[2] - q[0] for q in rets)
                    self.assertFalse(cruzam(rets[0], rets[1], folga=giro), f"rótulo e sub sobrepostos: {rets}")
                for k in ("tamanho_rotulo", "tamanho_sub"):            # encolhe, mas nunca abaixo do mínimo legível
                    if lay[k] is not None:
                        self.assertGreaterEqual(lay[k], lay["minimo_legivel"] - 0.01)
                self.assertAlmostEqual(lay["minimo_legivel"], da.MINIMO_LEGIVEL * min(L, A), delta=0.01)
                if "longo" in j["saida"] and L < A:
                    self.assertTrue(lay["rotulo_empilhado"])            # no vertical, 40 + 29 caracteres não cabem lado a lado
                jan = lay["janela"]                                    # a janela do insert continua com área útil
                self.assertGreater(jan["w"], 0.3 * L); self.assertGreater(jan["h"], 0.15 * A)
        # rotulo_na_zona é MEDIDO: com uma `area` que põe o cabeçalho da janela fora da zona `uniao`, o carimbo diz a verdade
        self.assertFalse(self.layout(raiz / "animacoes" / "_m fora.png")["rotulo_na_zona"])

    def test_31_gc_linha_e_legivel_sobre_footage_claro(self):
        """D19. Era: editorial-claro (GC 'linha', texto escuro) sobre footage — nome a 2,6:1 e cargo a 1,15:1."""
        from PIL import Image
        import numpy as np
        for preset in ("editorial-claro", "lab-ia"):
            raiz = self.projeto(preset, " gc legível")
            d = da.carregar(raiz)
            png = raiz / "animacoes" / "_gc linha.png"
            self.render(d, "--cena", "gc", "--formato", "vertical", "--escala", "0.5", "--quadro", "2.5", "--saida", png,
                        "--params", json.dumps({"nome": "Marina Albuquerque", "cargo": "Pesquisadora de inteligência artificial"}))
            lay = self.layout(png)
            self.assertEqual((lay["estilo"], lay["protecao"]), ("linha", "degrade"))
            fundo = Image.open(imagem_footage(raiz / "bruto" / "_footage claro.png")).convert("RGBA")
            comp = Image.alpha_composite(fundo, Image.open(png).convert("RGBA")).convert("RGB")
            x0, y0, x1, y1 = [int(v * 0.5) for v in ret(lay["caixa"])]
            sob = np.asarray(comp.crop((x0, y0, x1, y1))).reshape(-1, 3)
            gc = d["graficos"]["gc"]
            # o apoio é a cor mais comum sob o bloco (o painel); o texto ocupa a minoria dos pixels
            vals, cont = np.unique(sob // 8, axis=0, return_counts=True)
            apoio = da.rgb_para_hex(*(vals[cont.argmax()] * 8 + 4))
            with self.subTest(preset=preset):
                self.assertGreaterEqual(da.contraste(gc["cor_nome_hex"], apoio), 4.5, f"nome {gc['cor_nome_hex']} sobre {apoio}")
                self.assertGreaterEqual(da.contraste(gc["cor_cargo_hex"], apoio), 3.0, f"cargo {gc['cor_cargo_hex']} sobre {apoio}")
                self.assertLess(da.delta_e(apoio, gc["cor_fundo_hex"]), 20, f"o apoio sob o GC ({apoio}) não é a cor_fundo ({gc['cor_fundo_hex']})")

    def test_32_prancha_mostra_a_legenda_da_producao_e_a_faixa_1x1(self):
        """D21. Era: legenda da prancha desenhada pelo motor (≠ texto.py) e reduzida a 0,44×; paleta do dossiê estourando a margem."""
        from PIL import Image
        import numpy as np
        raiz = self.projeto("dossie", " prancha")
        shutil.copy2(imagem_footage(self.base / "footage.png"), raiz / "bruto" / "gravação 01.png")
        cartela_com_marca_texto(raiz / "da/referencias/ref 01 cartela.jpg")       # print de design: NÃO pode virar o "antes"
        editar(raiz / "da/da.json", lambda j: j["conceito"].update(referencias=[{"arquivo": "referencias/ref 01 cartela.jpg", "nota": "marca-texto"}]))
        d = da.carregar(raiz)
        r = motor.gerar_prancha(d, ("vertical", "horizontal"), escala=0.25)
        self.assertEqual(r["falhas"], [])
        self.assertIn("gravação 01.png", r["origem_referencia"])                  # footage do bruto vem antes das referências de design
        for fmt, nome, L in (("vertical", "prancha_vertical.png", 1080), ("horizontal", "prancha.png", 1920)):
            with self.subTest(formato=fmt):
                png = d.pasta / nome
                carimbo = da.ler_carimbo(png)
                lay = carimbo["parametros"]["layout"]
                self.assertEqual(lay["legenda"], "texto.py")
                self.assertTrue(any("texto.compor_legenda" in str(x) for x in carimbo["parametros"]["livres"]))
                titulos = [m["titulo"] for m in lay["mapa"]]
                self.assertEqual(titulos[0], "Referências")
                self.assertIn("Em escala 1:1", titulos)
                f = lay["faixa_1x1"]
                # Fecho: o GC da prancha é o da PRODUÇÃO — a mesma caixa da cena `gc` renderizada sem parâmetro de posição
                # (era: a prancha forçava reservar_legenda e mostrava o GC horizontal 200 px acima de onde a produção o põe)
                amostra = carimbo["parametros"]["params"]
                gc_png = raiz / "animacoes" / f"_gc padrão {fmt}.png"
                self.render(d, "--cena", "gc", "--formato", fmt, "--escala", "0.25", "--quadro", "2.5", "--saida", gc_png,
                            "--params", json.dumps({"nome": amostra["nome_exemplo"], "cargo": amostra["cargo_exemplo"]}))
                producao = self.layout(gc_png)
                self.assertEqual(ret(f["gc"]), ret(producao["caixa"]), f"{fmt}: GC da prancha ≠ GC da produção")
                self.assertEqual(f["reservou_legenda"], producao["reservou_legenda"])
                if fmt == "vertical":
                    self.assertTrue(f["juntos"] and f["reservou_legenda"])
                    self.assertFalse(cruzam(ret(f["gc"]), ret(f["legenda"])), f)
                    self.assertEqual([x["conteudo"] for x in f["tiras"]], ["gc+legenda"])
                else:
                    # horizontal sem reserva: a prancha não finge um layout que a produção não entrega — GC na base, legenda à parte
                    self.assertFalse(f["juntos"] or f["reservou_legenda"])
                    self.assertEqual([x["conteudo"] for x in f["tiras"]], ["gc", "legenda"])
                    self.assertTrue(cruzam(ret(f["gc"]), ret(f["faixa_legenda"])))
                    self.assertAlmostEqual(f["gc"]["y1"], d.margens("horizontal")["y1"], delta=1)
                # o PNG da legenda é o de texto.estados_da_legenda, na posição que a produção usa
                p = json.loads((d.build / "prancha" / f"params_{fmt}.json").read_text(encoding="utf-8"))["legenda"]
                A = 1920 if fmt == "vertical" else 1080
                img, info = texto.estados_da_legenda(p["palavras"], d, L, A, formato=fmt)[p["falada"]]
                self.assertEqual((p["x"], p["y"], p["w"], p["h"]), (info["x"], info["y"], img.width, img.height))
                with Image.open(p["arquivo"]) as salvo:
                    self.assertEqual(salvo.tobytes(), img.tobytes())
                self.assertNotIn(" que não", " ".join(p["palavras"]) + " ")      # a amostra nunca é uma frase cortada
                # a faixa 1:1 é sangrada: ocupa a largura inteira da prancha; fora dela nada passa da margem direita
                im = np.asarray(Image.open(png).convert("RGB")).astype(int)
                k = im.shape[1] / L
                fundo = np.array(d.rgb("fundo"))
                pad = (56 if fmt == "vertical" else 80) * k
                margem = np.abs(im[:, int(im.shape[1] - pad + 3):, :] - fundo).sum(axis=2) > 40
                linhas_sujas = np.where(margem.any(axis=1))[0]
                sec = next(m for m in lay["mapa"] if m["titulo"] == "Em escala 1:1")     # a seção inteira (uma tira ou duas)
                y0, y1 = sec["y"] * k, (sec["y"] + sec["h"]) * k
                fora = [int(y) for y in linhas_sujas if not (y0 - 4 <= y <= y1 + 4)]
                self.assertEqual(fora, [], f"conteúdo passando da margem direita da prancha {fmt} em y={fora[:5]}…")

    def test_33_digita_revela_linha_a_linha(self):
        """Era: 'digita' = corte de máscara na caixa inteira: 3 linhas avançando juntas, glifos pela metade."""
        from PIL import Image
        import numpy as np
        raiz = self.projeto("lab-ia", " digita")
        d = da.carregar(raiz)
        self.assertEqual(d["movimento"]["entrada_padrao"], "digita")
        params = json.dumps({"titulo": "Por que Santa Catarina recebe tão pouco de volta da União?"})
        cheio, meio = raiz / "animacoes" / "_dig cheio.png", raiz / "animacoes" / "_dig meio.png"
        self.render(d, "--cena", "titulo", "--formato", "480x270", "--quadro", "2", "--saida", cheio, "--params", params)
        lay = self.layout(cheio)
        self.assertGreaterEqual(lay["linhas"], 2)
        t = 0.05 + d.dur("longa") * 0.04                               # começo da digitação: só a 1ª linha
        self.render(d, "--cena", "titulo", "--formato", "480x270", "--quadro", f"{t:.3f}", "--saida", meio, "--params", params)
        tit = ret(lay["titulo"])
        fundo = np.array(d.rgb("fundo"))

        def tinta(arq):
            a = np.asarray(Image.open(arq).convert("RGB")).astype(int)
            return (np.abs(a - fundo).sum(axis=2) > 200)[int(tit[1]):int(tit[3]), int(tit[0]):int(tit[2])]
        c, m = tinta(cheio), tinta(meio)
        alt = c.shape[0] // lay["linhas"]
        self.assertTrue(m[:alt].any(), "a primeira linha ainda não começou")
        self.assertFalse(m[alt + 4:].any(), "linhas de baixo aparecendo antes de a primeira terminar")
        self.assertLess(m[:alt].sum(), c[:alt].sum())                 # e a primeira ainda está pela metade

    def test_34_teste_de_movimento_nao_corta_animacao(self):
        """D21. Era: 4 s fixos — no editorial-claro as barras paravam em R$ 1,44 em vez de 1,65."""
        from PIL import Image
        import numpy as np
        raiz = self.projeto("editorial-claro", " movimento")
        d = da.carregar(raiz)
        plano = motor.duracao_do_teste(d)
        # o motor usa a duração que a CENA calcula (mesma conta em Python e em JS), e --dur 3 não corta nada
        r = self.render(d, "--cena", "teste_movimento", "--formato", "480x270", "--dur", "3", "--saida", raiz / "da" / "x.mp4", "--validar", "--json")
        job = json.loads(r.stdout)["jobs"][0]
        self.assertAlmostEqual(job["dur"], motor.duracao_do_teste(d, pedida=3)["total"], places=2)
        self.assertGreater(job["dur"], 3)
        r = self.render(d, "--cena", "teste_movimento", "--formato", "480x270", "--saida", raiz / "da" / "x.mp4", "--validar", "--json")
        self.assertAlmostEqual(json.loads(r.stdout)["jobs"][0]["dur"], plano["total"], places=2)
        # no fim da peça o gráfico está parado nos valores finais: o último quadro é igual ao de 0,3 s antes
        fim, antes = raiz / "qa" / "_tm fim.png", raiz / "qa" / "_tm antes.png"
        self.render(d, "--cena", "teste_movimento", "--formato", "480x270", "--quadro", "fim", "--saida", fim)
        self.render(d, "--cena", "teste_movimento", "--formato", "480x270", "--quadro", f"{plano['total'] - 0.3:.3f}", "--saida", antes)
        a, b = (np.asarray(Image.open(x).convert("L").resize((96, 54), Image.BILINEAR)).astype(int) for x in (fim, antes))
        self.assertLess(np.abs(a - b).mean(), 1.0, "o gráfico ainda estava animando no fim do teste")
        lay = self.layout(fim)
        self.assertEqual(lay["atos"], ["titulo", "gc", "barras"])
        self.assertAlmostEqual(lay["total"], plano["total"], places=2)
        self.assertGreaterEqual(lay["janelas"]["barras"]["cena"], lay["barras"]["fim_entrada"])     # cabe a entrada inteira das barras
        self.assertGreaterEqual(lay["janelas"]["titulo"]["cena"], lay["titulo"]["fim_entrada"] + d.dur("media"))
        # Fecho: o ato do GC é o da produção. No horizontal a DA não reserva a faixa da legenda: o GC fica na base e a
        # legenda NÃO entra junto (era: o teste forçava reservar_legenda e mostrava um layout que a produção não entrega)
        self.assertFalse(lay["gc"]["reservou_legenda"])
        self.assertIsNone(lay["legenda"]); self.assertFalse(lay["gc_e_legenda_juntos"])
        self.assertIn("legenda.reservar_em", lay["legenda_omitida"])
        self.assertAlmostEqual(lay["gc"]["caixa"]["y1"], d.margens("horizontal", largura=480, altura=270)["y1"], delta=1)
        # com "horizontal" em legenda.reservar_em, GC e legenda voltam a entrar juntos, sem se tocar
        raiz2 = self.projeto("editorial-claro", " movimento reservado")
        editar(raiz2 / "da/da.json", lambda j: j["legenda"].update(reservar_em=["vertical", "quadrado", "horizontal"]))
        d2 = da.carregar(raiz2)
        meio = raiz2 / "qa" / "_tm gc.png"
        self.render(d2, "--cena", "teste_movimento", "--formato", "480x270", "--quadro", "0.6", "--saida", meio, "--params", json.dumps({"atos": ["gc"]}))
        lay2 = self.layout(meio)
        self.assertTrue(lay2["gc"]["reservou_legenda"] and lay2["gc_e_legenda_juntos"])
        self.assertFalse(cruzam(ret(lay2["gc"]["caixa"]), ret(lay2["legenda"])), "GC sobre a legenda no teste de movimento")

    def test_35_ato_do_gc_no_vertical_com_legenda_e_footage(self):
        raiz = self.projeto("dossie", " ato gc")
        shutil.copy2(imagem_footage(self.base / "footage v.png"), raiz / "bruto" / "gravação 01.png")
        d = da.carregar(raiz)
        r, saida, plano = motor.gerar_teste_de_movimento(d, "vertical", escala=0.25, atos=["gc"])
        self.assertEqual(r.returncode, 0)
        self.assertLess(plano["total"], 3.0)
        carimbo = da.ler_carimbo(saida)
        self.assertEqual(carimbo["parametros"]["quadros"], round(plano["total"] * 30000 / 1001))
        lay = carimbo["parametros"]["layout"]
        self.assertEqual(lay["atos"], ["gc"])
        zona = d.margens("vertical")
        for nome, rr in (("GC", ret(lay["gc"]["caixa"])), ("legenda", ret(lay["legenda"]))):
            self.assertTrue(rr[0] >= zona["x0"] - 1 and rr[2] <= zona["x1"] + 1 and rr[1] >= zona["y0"] - 1 and rr[3] <= zona["y1"] + 1, (nome, rr))
        self.assertFalse(cruzam(ret(lay["gc"]["caixa"]), ret(lay["legenda"])))
        self.assertTrue(any("footage" in str(x) for x in carimbo["parametros"]["livres"]))       # o fundo é um quadro do projeto
        rc, _, err = self.cli("teste-movimento", "--atos", "titulo,abertura", cwd=raiz)
        self.assertEqual(rc, 64, err)

    def test_36_rotas_comparar_usa_o_footage_do_projeto_e_alinha_por_secao(self):
        """D20. Era: prancha de rota com quadro sintético e "lado a lado" feito à mão."""
        from PIL import Image
        raiz = self.projeto("dossie", " comparar")
        shutil.copy2(imagem_footage(self.base / "footage c.png"), raiz / "bruto" / "gravação 01.png")
        da.criar_rota("rota-a", base="lab-ia", frase="Rota A: painel frio.", caminho=raiz)
        da.criar_rota("rota-b", cores={"primaria": "#F6C614"}, frase="Rota B: o dossiê com outro amarelo.", caminho=raiz)
        r = motor.comparar_rotas(None, formato="vertical", largura=270, caminho=raiz)
        self.assertEqual((r["colunas"], sorted(r["geradas"])), (["rota-a", "rota-b"], ["rota-a", "rota-b"]))
        with Image.open(r["saida"]) as im:
            self.assertEqual(im.width, 2 * 270 + 3 * 16)
            self.assertGreater(im.height, 1500)
        self.assertEqual(r["saida"], raiz / "da/rotas/comparacao_vertical.png")
        origem = json.loads((raiz / "da/rotas/rota-a/da/build/prancha/params_vertical.json").read_text(encoding="utf-8"))["origem_referencia"]
        self.assertIn("gravação 01.png", origem)                       # a rota achou o bruto do projeto-pai
        r2 = motor.comparar_rotas(None, formato="vertical", largura=270, com_atual=True, caminho=raiz)
        self.assertEqual((r2["colunas"], r2["geradas"]), (["atual", "rota-a", "rota-b"], ["atual"]))       # as das rotas estavam em dia
        self.assertEqual({x["prancha"]["vertical"] for x in da.listar_rotas(caminho=raiz)}, {"em dia"})
        with self.assertRaises(da.DAErro):
            motor.comparar_rotas(["rota-a"], caminho=raiz)             # uma coluna só não é comparação
        with self.assertRaises(da.DAErro):
            motor.comparar_rotas(["rota-x", "rota-a"], caminho=raiz)

    def test_37_aprovar_regenera_a_prancha_com_o_selo(self):
        """Era: depois de `aprovar`, a prancha continuava com "REVISÃO 1 · RASCUNHO" no cabeçalho."""
        raiz = self.projeto("dossie", " selo")
        d = da.carregar(raiz)
        self.assertEqual(motor.gerar_prancha(d, ("vertical",), escala=0.25)["falhas"], [])
        png = d.pasta / "prancha_vertical.png"
        self.assertFalse(da.ler_carimbo(png)["da_aprovada"])
        antes = png.read_bytes()
        rc, out, err = self.cli("aprovar", cwd=raiz)
        self.assertEqual(rc, 0, err)
        self.assertIn("regenerada com o cabeçalho APROVADA", out)
        self.assertIn("teste de movimento ausente", out)                # avisa o que faltou ver
        c = da.ler_carimbo(png)
        self.assertTrue(c["da_aprovada"])
        self.assertEqual(c["parametros"]["escala"], 0.25)               # mesma escala da prancha que o cliente viu
        self.assertNotEqual(png.read_bytes(), antes)
        self.assertEqual(da.documentos_de_aprovacao(raiz)["prancha_vertical.png"]["estado"], "em dia")


if __name__ == "__main__":
    unittest.main(verbosity=2)
