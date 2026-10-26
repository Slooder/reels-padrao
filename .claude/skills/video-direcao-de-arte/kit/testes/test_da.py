#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Testes do núcleo do kit de direção de arte (da.py + trava.py).

Rodar a partir da pasta do kit:
    python3 -m unittest                 # tudo
    python3 -m unittest testes.test_da.TesteLint -v

Só biblioteca padrão (+ Pillow/numpy nos testes de `extrair`). Toda pasta temporária tem ESPAÇO e
acento no nome; VIDEO_OPS_HOME aponta para dentro dela. Os dois testes que chamam o ffmpeg usam
um clipe sintético de 0,5 s em 320x180 e passam pela trava global de verdade.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from fractions import Fraction
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent
if str(KIT) not in sys.path:
    sys.path.insert(0, str(KIT))

import da  # noqa: E402
import trava  # noqa: E402

PRESETS = ("dossie", "lab-ia", "editorial-claro", "neon-shorts", "quadro-negro")
FFMPEG = shutil.which("ffmpeg") or ("/opt/homebrew/bin/ffmpeg" if Path("/opt/homebrew/bin/ffmpeg").exists() else None)


class Base(unittest.TestCase):
    """Pasta temporária com espaço no nome, VIDEO_OPS_HOME isolado, DA_JSON limpo, cwd restaurado."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="da teste é ")).resolve()
        self._env = {k: os.environ.get(k) for k in ("VIDEO_OPS_HOME", "DA_JSON", "NO_COLOR")}
        os.environ["VIDEO_OPS_HOME"] = str(self.tmp / "video ops home")
        os.environ.pop("DA_JSON", None)
        os.environ["NO_COLOR"] = "1"
        self._cwd = os.getcwd()
        os.chdir(self.tmp)

    def tearDown(self):
        os.chdir(self._cwd)
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.tmp, ignore_errors=True)

    # -- ajudantes ----------------------------------------------------------
    def projeto(self, nome="Projeto de teste", base="dossie", pasta="projeto com espaço", **k) -> Path:
        raiz = self.tmp / pasta
        da.iniciar(raiz, nome=nome, base=base, **k)
        return raiz

    def cli(self, *args) -> tuple[int, str, str]:
        """Roda a CLI no mesmo processo; devolve (código, stdout, stderr)."""
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = da.main([str(a) for a in args])
        return rc, out.getvalue(), err.getvalue()

    def processo(self, *args, cwd=None, env=None) -> subprocess.CompletedProcess:
        ambiente = dict(os.environ)
        ambiente.update(env or {})
        return subprocess.run([sys.executable, str(KIT / "da.py"), *map(str, args)], cwd=str(cwd or self.tmp),
                              env=ambiente, capture_output=True, text=True)

    @staticmethod
    def editar(da_json: Path, fn) -> None:
        dados = json.loads(da_json.read_text(encoding="utf-8"))
        fn(dados)
        da_json.write_text(da.json_bonito(dados) + "\n", encoding="utf-8")

    def validar_mutado(self, fn, base="dossie") -> tuple[list[str], list[str]]:
        """Valida o preset `base` depois de aplicar a mutação fn(dados)."""
        cadeia = da.carregar_cadeia(da.achar_preset(base))
        fundida = da.fundir_cadeia(cadeia)
        fn(fundida)
        return da.validar_dados(fundida, [c["base"] for c in cadeia])

    def assertContem(self, lista: list[str], trecho: str):
        self.assertTrue(any(trecho in x for x in lista), f"{trecho!r} não apareceu em:\n  " + "\n  ".join(lista or ["(vazio)"]))


# ════════════════════════════════════════════════════════════════════ trava ══
class TesteTrava(Base):
    def setUp(self):
        super().setUp()
        self._trava_env = {k: os.environ.get(k) for k in (trava.VAR_ARQUIVO, trava.VAR_DONO)}
        os.environ[trava.VAR_ARQUIVO] = str(self.tmp / "trava de teste.lock")   # nunca a trava real
        os.environ.pop(trava.VAR_DONO, None)

    def tearDown(self):
        for k, v in self._trava_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        super().tearDown()

    def test_repassa_codigo_de_saida(self):
        self.assertEqual(trava.main(["--", sys.executable, "-c", "import sys; sys.exit(7)"]), 7)
        self.assertEqual(trava.main(["--", sys.executable, "-c", "pass"]), 0)
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(trava.main(["--silencioso", "--", "comando-que-nao-existe-xyz"]), 127)
            self.assertEqual(trava.main([]), trava.SAIDA_USO)
            self.assertEqual(trava.main(["--espera-max", "abc", "--", "true"]), trava.SAIDA_USO)
        self.assertIn("comando não encontrado", err.getvalue())
        self.assertIn("faltou o comando", err.getvalue())
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(trava.main(["--help"]), 0)
            self.assertEqual(trava.main(["--estado"]), 0)                      # livre
        self.assertIn("aguardando trava", out.getvalue())
        self.assertIn("trava livre", out.getvalue())

    def test_filho_recebe_o_dono_e_reentra(self):
        codigo = ("import os, sys; sys.path.insert(0, sys.argv[1]); import trava\n"
                  "assert trava.sob_trava() == int(os.environ['VIDEO_OPS_TRAVA'])\n"
                  "t = trava.Trava(espera_max=0.5).adquirir(); assert t.reentrante; t.liberar()\n")
        self.assertEqual(trava.main(["--", sys.executable, "-c", codigo, str(KIT)]), 0)

    def test_with_e_reentrancia_no_mesmo_processo(self):
        self.assertIsNone(trava.sob_trava())
        with trava.Trava(rotulo="externa") as t1:
            self.assertFalse(t1.reentrante)
            self.assertEqual(trava.sob_trava(), os.getpid())
            self.assertFalse(trava.estado()["livre"])
            with trava.Trava(espera_max=0.5) as t2:
                self.assertTrue(t2.reentrante)
            self.assertEqual(trava.sob_trava(), os.getpid())      # a interna não soltou a externa
        self.assertIsNone(trava.sob_trava())
        self.assertTrue(trava.estado()["livre"])
        self.assertNotIn(trava.VAR_DONO, os.environ)

    def test_fila_bloqueia_e_espera_max_desiste(self):
        segura = subprocess.Popen([sys.executable, str(KIT / "trava.py"), "--rotulo", "segura", "--",
                                   sys.executable, "-c", "import time; time.sleep(1.5)"])
        try:
            for _ in range(60):
                if not trava.estado()["livre"]:
                    break
                time.sleep(0.05)
            self.assertFalse(trava.estado()["livre"])
            self.assertEqual(trava.estado()["dono"]["rotulo"], "segura")
            with self.assertRaises(trava.TempoEsgotado):
                trava.Trava(espera_max=0.3, silencioso=True).adquirir()
            t0 = time.monotonic()
            with trava.Trava(silencioso=True) as t:                # entra na fila e espera a vez
                self.assertGreater(t.esperou, 0.2)
            self.assertLess(time.monotonic() - t0, 10)
        finally:
            segura.wait(timeout=10)

    def test_variavel_herdada_de_dono_que_ja_soltou_nao_engana(self):
        os.environ[trava.VAR_DONO] = str(os.getpid())              # vivo, mas não registrado no arquivo
        self.assertIsNone(trava.sob_trava())
        with trava.Trava(espera_max=1) as t:
            self.assertFalse(t.reentrante)


# ═════════════════════════════════════════════════════════════════════ init ══
class TesteInit(Base):
    def test_cria_estrutura_completa(self):
        raiz = self.projeto()
        for p in ("CLAUDE.md", "da/da.json", "da/DA.md", "da/build/da.css", "da/build/da.js", "da/build/da.resolvida.json",
                  "da/build/grade.json", "da/build/da.lock", "da/fontes/ArchivoSemiExpanded-Black.ttf",
                  "da/fontes/IBMPlexMono-Bold.ttf"):
            self.assertTrue((raiz / p).is_file(), p)
        for p in ("da/fontes", "da/luts", "da/texturas", "da/logos", "da/referencias", "pesquisa", "roteiro", "bruto",
                  "transcricao", "broll", "animacoes", "legendas", "cortes", "thumbs", "publicacao", "qa", "render"):
            self.assertTrue((raiz / p).is_dir(), p)
        dados = json.loads((raiz / "da/da.json").read_text(encoding="utf-8"))
        self.assertEqual(dados["projeto"]["nome"], "Projeto de teste")
        self.assertEqual(dados["projeto"]["slug"], "projeto-de-teste")
        self.assertEqual(dados["projeto"]["base"], "dossie")
        self.assertEqual((dados["projeto"]["revisao"], dados["projeto"]["aprovada"]), (1, False))
        self.assertIsNone(dados["herda"])
        self.assertEqual(dados["cor"]["paleta"]["primaria"], "#FFC700")
        claude = (raiz / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertEqual(claude.count(da.CLAUDE_INI), 1)
        self.assertEqual(claude.count(da.CLAUDE_FIM), 1)
        self.assertIn("Projeto de teste", claude)
        self.assertIn("@da/DA.md", claude)
        # a ordem do pipeline no escopo final: pauta de mídia depois da DA, thumbnail direto pelo kit, conferência final como comando
        self.assertIn("pesquisa (ficha de fatos) → roteiro → **direção de arte**", claude)
        for trecho in ("→ pauta de mídia →", "→ thumbnail (direto pelo kit) →", "→ **conferência final** (`da.py conferencia`) → publicação",
                       "/bin/da conferencia"):
            self.assertIn(trecho, claude)
        for skill_que_nao_existe in ("video-qa", "video-thumbnail", "(futura)"):
            self.assertNotIn(skill_que_nao_existe, claude)
        self.assertNotIn("{{", claude)
        self.assertNotIn(str(KIT), claude)                         # documentação cita o caminho final, não o de montagem
        self.assertEqual(da.validar(raiz / "da/da.json")["erros"], [])

    def test_idempotente(self):
        raiz = self.projeto()
        da_json, claude = raiz / "da/da.json", raiz / "CLAUDE.md"
        antes_da = da_json.read_bytes()
        claude.write_text("# Meu cabeçalho\n\n" + claude.read_text(encoding="utf-8") + "\n## Notas minhas\nnão apagar\n",
                          encoding="utf-8")
        antes_claude = claude.read_text(encoding="utf-8")
        info = da.iniciar(raiz, nome="Outro nome", base="neon-shorts")
        self.assertFalse(info["criou_da"])
        self.assertEqual(info["claude_md"], "inalterado")
        self.assertEqual(da_json.read_bytes(), antes_da)           # nada sobrescrito
        self.assertEqual(claude.read_text(encoding="utf-8"), antes_claude)
        self.assertEqual(claude.read_text(encoding="utf-8").count(da.CLAUDE_INI), 1)
        self.assertContem(info["avisos"], "--forcar")
        self.assertEqual(list(raiz.glob("da/da.json.bak-*")), [])

    def test_forcar_recria_com_backup(self):
        raiz = self.projeto()
        info = da.iniciar(raiz, base="lab-ia", forcar=True)
        self.assertTrue(info["criou_da"])
        self.assertTrue(info["backup"].is_file())
        dados = json.loads((raiz / "da/da.json").read_text(encoding="utf-8"))
        self.assertEqual(dados["projeto"]["nome"], "Projeto de teste")      # nome reaproveitado
        self.assertEqual(dados["cor"]["paleta"]["primaria"], "#38E1FF")
        self.assertTrue((raiz / "da/fontes/Roboto-Variable.ttf").is_file())

    def test_claude_md_existente_e_bloco_atualizado_sem_duplicar(self):
        raiz = self.tmp / "com claude"
        raiz.mkdir()
        (raiz / "CLAUDE.md").write_text("# Regras antigas\n\n- regra 1\n", encoding="utf-8")
        da.iniciar(raiz, nome="X", base="dossie")
        texto = (raiz / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertTrue(texto.startswith("# Regras antigas\n\n- regra 1\n"))
        self.assertEqual(texto.count(da.CLAUDE_INI), 1)
        # bloco velho é substituído no lugar, o resto fica
        velho = texto.replace("Regra de submissão", "REGRA VELHA")
        (raiz / "CLAUDE.md").write_text(velho + "\nrodapé\n", encoding="utf-8")
        info = da.iniciar(raiz)
        novo = (raiz / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertEqual(info["claude_md"], "atualizado")
        self.assertNotIn("REGRA VELHA", novo)
        self.assertEqual(novo.count(da.CLAUDE_INI), 1)
        self.assertTrue(novo.rstrip().endswith("rodapé"))

    def test_claude_md_com_um_delimitador_so_nao_e_destruido(self):
        raiz = self.tmp / "quebrado"
        raiz.mkdir()
        (raiz / "CLAUDE.md").write_text(f"algo\n{da.CLAUDE_INI}\nsem fim\n", encoding="utf-8")
        with self.assertRaises(da.DAErro):
            da.iniciar(raiz, nome="X")
        self.assertEqual((raiz / "CLAUDE.md").read_text(encoding="utf-8"), f"algo\n{da.CLAUDE_INI}\nsem fim\n")

    def test_herdar_cria_filho_enxuto(self):
        raiz = self.projeto(base="quadro-negro", herdar=True)
        dados = json.loads((raiz / "da/da.json").read_text(encoding="utf-8"))
        self.assertEqual(dados["herda"], "quadro-negro")
        self.assertEqual(set(dados), {"versao_esquema", "herda", "projeto"})
        d = da.carregar(raiz)
        self.assertEqual(d.cor("primaria"), "#F6D55C")
        self.assertEqual(d.meta["nome"], "Projeto de teste")
        self.assertTrue(Path(d.fonte("titulo")["caminho"]).is_relative_to(raiz))   # usa a cópia local da fonte

    def test_erros_de_uso(self):
        with self.assertRaises(da.DAErro) as c:
            da.iniciar(self.tmp / "p1")
        self.assertIn("--nome", str(c.exception))
        with self.assertRaises(da.DAErro) as c:
            da.iniciar(self.tmp / "p2", nome="X", base="dosie")
        self.assertIn("dossie", str(c.exception))                  # sugere o nome certo
        rc, out, err = self.cli("init")
        self.assertEqual(rc, da.SAIDA_USO)
        self.assertIn("faltam argumentos", err)

    def test_init_que_falha_nao_deixa_rastro(self):
        # preset inexistente e nome faltando: antes ficavam as 18 pastas do esqueleto, sem da.json nem CLAUDE.md
        for pasta, kw in (("x y", {"nome": "X", "base": "dosie"}), ("sem nome", {})):
            with self.assertRaises(da.DAErro):
                da.iniciar(self.tmp / pasta, **kw)
            self.assertFalse((self.tmp / pasta).exists(), f"o init que falhou criou {pasta!r}")
        # pasta que já existia continua exatamente como estava
        antiga = self.tmp / "já existia"
        antiga.mkdir()
        (antiga / "nota.txt").write_text("minha", encoding="utf-8")
        with self.assertRaises(da.DAErro):
            da.iniciar(antiga, nome="X", base="nao-existe")
        self.assertEqual(sorted(x.name for x in antiga.iterdir()), ["nota.txt"])
        # --forcar com CLAUDE.md quebrado: antes trocava o da.json (com backup) e só então falhava — aplicava pela metade
        raiz = self.projeto(pasta="meio a meio")
        antes = (raiz / "da" / "da.json").read_bytes()
        (raiz / "CLAUDE.md").write_text(f"texto\n{da.CLAUDE_INI}\nsem o fim\n", encoding="utf-8")
        with self.assertRaises(da.DAErro):
            da.iniciar(raiz, nome="Outro", base="lab-ia", forcar=True)
        self.assertEqual((raiz / "da" / "da.json").read_bytes(), antes)
        self.assertFalse(list((raiz / "da").glob("da.json.bak-*")))

    def test_init_em_cima_de_um_arquivo_tem_mensagem_e_nao_traceback(self):
        arq = self.tmp / "sou um arquivo.txt"
        arq.write_text("x", encoding="utf-8")
        r = self.processo("init", arq, "--nome", "X")
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn("é um arquivo, não uma pasta", r.stderr)
        self.assertNotIn("Traceback", r.stderr)


# ════════════════════════════════════════════════════════════════════ achar ══
class TesteAchar(Base):
    def test_sobe_de_subpasta_profunda(self):
        raiz = self.projeto()
        funda = raiz / "animacoes" / "cena 01" / "a" / "b c"
        funda.mkdir(parents=True)
        self.assertEqual(da.achar(de=funda), raiz / "da" / "da.json")
        self.assertEqual(da.achar(de=funda / "arquivo_que_nao_existe.html"), raiz / "da" / "da.json")
        os.chdir(funda)
        self.assertEqual(da.achar(), raiz / "da" / "da.json")
        r = self.processo("achar", "--raiz", cwd=funda)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, str(raiz)))

    def test_sem_da_sai_com_codigo_2(self):
        vazia = self.tmp / "sem da"
        vazia.mkdir()
        for comando in (["achar"], ["mostrar"], ["compilar"], ["token", "cor.paleta.primaria"], ["conferir-carimbo"],
                        ["grade"]):
            r = self.processo(*comando, cwd=vazia)
            self.assertEqual(r.returncode, 2, comando)
            self.assertIn("video-direcao-de-arte", r.stderr)
            self.assertIn("init", r.stderr)
        self.assertIsNone(da.achar(de=vazia, obrigatorio=False))
        with self.assertRaises(da.SemDA) as c:
            da.carregar(de=vazia)
        self.assertEqual(c.exception.codigo, 2)

    def test_da_json_e_flag_da_sobrepoem(self):
        a = self.projeto(pasta="projeto a", base="dossie")
        b = self.projeto(pasta="projeto b", base="lab-ia")
        os.chdir(a)
        self.assertEqual(da.achar(), a / "da/da.json")
        os.environ["DA_JSON"] = str(b / "da" / "da.json")
        self.assertEqual(da.achar(), b / "da/da.json")             # variável vence a descoberta
        self.assertEqual(da.achar(da=a), a / "da/da.json")         # flag vence a variável (aceita a pasta do projeto)
        r = self.processo("token", "cor.paleta.primaria", cwd=a)
        self.assertEqual(r.stdout.strip(), "#38E1FF")
        r = self.processo("token", "cor.paleta.primaria", "--da", a / "da/da.json", cwd=a)
        self.assertEqual(r.stdout.strip(), "#FFC700")
        r = self.processo("--da", a, "token", "cor.paleta.primaria", cwd=self.tmp)   # opção global antes do subcomando
        self.assertEqual(r.stdout.strip(), "#FFC700")
        os.environ["DA_JSON"] = str(self.tmp / "nao existe" / "da.json")
        with self.assertRaises(da.SemDA):
            da.achar()


# ══════════════════════════════════════════════════════════════════ validar ══
class TesteValidar(Base):
    def test_todos_os_presets_sao_validos_e_completos(self):
        plat = json.loads((KIT / "plataformas.json").read_text(encoding="utf-8"))
        vert, horiz = plat["margens_seguras_vertical"], plat["margens_seguras_horizontal"]
        nomes = {p["nome"] for p in da.listar_presets() if p["origem"] == "embutido"}
        self.assertTrue(set(PRESETS) <= nomes)
        frases = set()
        for nome in PRESETS:
            with self.subTest(preset=nome):
                r = da.validar(da.achar_preset(nome))
                self.assertEqual(r["erros"], [])
                self.assertEqual(r["avisos"], [])
                dados = da.ler_json(da.achar_preset(nome))
                ms = dados["formatos"]["margens_seguras"]
                for app in ("instagram", "tiktok", "shorts", "uniao"):       # números vêm de plataformas.json
                    canonico = {"instagram": "reels"}.get(app, app)           # no da.json a zona do Reels chama-se "instagram" (contrato v1)
                    self.assertEqual(ms["vertical"][app], [vert[canonico][k] for k in ("topo", "direita", "base", "esquerda")])
                self.assertEqual(ms["horizontal"]["padrao"], [horiz["padrao"][k] for k in ("topo", "direita", "base", "esquerda")])
                self.assertGreaterEqual(len(set(dados["cor"]["dados"])), 6)
                self.assertGreaterEqual(len(dados["conceito"]["faca"]), 3)
                self.assertGreaterEqual(len(dados["conceito"]["nao_faca"]), 3)
                for papel in dados["tipografia"]["papeis"].values():         # só fontes do kit, por caminho relativo
                    self.assertTrue((KIT / papel["arquivo"]).is_file(), papel["arquivo"])
                frases.add(dados["conceito"]["frase"])
        self.assertEqual(len(frases), len(PRESETS))
        paletas = {da.ler_json(da.achar_preset(n))["cor"]["paleta"]["primaria"] for n in PRESETS}
        self.assertEqual(len(paletas), len(PRESETS))                 # visualmente distintos

    def test_erros_estruturais(self):
        casos = [
            (lambda d: d["cor"]["paleta"].__setitem__("primaria", "#GGG"), "cor.paleta.primaria", "#RRGGBB"),
            (lambda d: d["cor"]["paleta"].pop("texto"), "cor.paleta", "falta a chave obrigatória \"texto\""),
            (lambda d: d.pop("legenda"), "(raiz)", "\"legenda\""),
            (lambda d: d["tipografia"]["papeis"]["titulo"].__setitem__("peso", "900"), "tipografia.papeis.titulo.peso", "esperado número inteiro"),
            (lambda d: d["movimento"].__setitem__("entrada_padrao", "sob"), "movimento.entrada_padrao", "'sobe'"),
            (lambda d: d["formatos"]["margens_seguras"]["vertical"]["tiktok"].__setitem__(2, 0.5), "margens_seguras.vertical.tiktok[2]", "menor que 0.5"),
            (lambda d: d["formatos"]["margens_seguras"]["horizontal"]["padrao"].__setitem__(0, -0.1), "horizontal.padrao[0]", "abaixo do mínimo"),
            (lambda d: d["formatos"]["margens_seguras"]["horizontal"].__setitem__("padrao", [0.05, 0.05]), "horizontal.padrao", "pelo menos 4"),
            (lambda d: d["movimento"]["curvas"].__setitem__("entrada", [0.2, 0.1, 0.3]), "movimento.curvas.entrada", "pelo menos 4"),
            (lambda d: d["legenda"].__setitem__("max_palavras", 0), "legenda.max_palavras", "abaixo do mínimo"),
            (lambda d: d["legenda"].__setitem__("max_linhas", 0), "legenda.max_linhas", "abaixo do mínimo"),
            (lambda d: d["cor"].__setitem__("dados", ["#111111", "#222222", "#333333", "#444444", "#555555"]), "cor.dados", "pelo menos 6"),
            (lambda d: d["tipografia"]["escala"].__setitem__("h1", 0), "tipografia.escala.h1", "maior que 0"),
            (lambda d: d["legenda"].__setitem__("contorno", "preto"), "legenda.contorno", "não é aceito aqui"),
            (lambda d: d["tratamento"]["grade"].__setitem__("curva", "contraste_forte"), "tratamento.grade.curva", "não é aceito"),
            (lambda d: d.__setitem__("versao_esquema", 2), "versao_esquema", "atualize"),
            (lambda d: d["projeto"].__setitem__("slug", "Com Espaço"), "projeto.slug", "hífens"),
        ]
        for mutacao, onde, trecho in casos:
            with self.subTest(onde=onde):
                erros, _ = self.validar_mutado(mutacao)
                self.assertTrue(any(onde in e and trecho in e for e in erros) or
                                any(trecho in e for e in erros), f"{onde} / {trecho}\n" + "\n".join(erros))

    def test_erros_semanticos(self):
        casos = [
            (lambda d: d["cor"]["paleta"].__setitem__("texto", "#1A1A1A"), "contraste texto×fundo"),
            (lambda d: d["cor"]["paleta"].__setitem__("superficie", "#E0DDD6"), "contraste texto×superficie"),
            (lambda d: d["legenda"]["contorno"].__setitem__("cor", "texto"), "legenda: contraste cor×contorno"),
            (lambda d: d["tipografia"]["papeis"]["titulo"].__setitem__("arquivo", "fontes/NaoExiste.ttf"), "arquivo não encontrado: fontes/NaoExiste.ttf"),
            (lambda d: d["tratamento"]["grade"].__setitem__("lut", "luts/nada.cube"), "tratamento.grade.lut: arquivo não encontrado"),
            (lambda d: d["tratamento"]["grade"].__setitem__("lut", "fontes/IBMPlexMono-Bold.ttf"), "extensão .ttf não suportada"),
            (lambda d: d["marca"].__setitem__("logo", "logos/sumiu.png"), "marca.logo: arquivo não encontrado"),
            (lambda d: d["formatos"]["horizontal"].__setitem__("fps", "trinta"), "formatos.horizontal.fps"),
            (lambda d: d["formatos"]["vertical"].__setitem__("fps", "0/1"), "formatos.vertical.fps"),
            (lambda d: d["formatos"]["vertical"].__setitem__("fps", "30/0"), "formatos.vertical.fps"),
            (lambda d: d["cor"].__setitem__("dados", ["#FFC700"] * 3 + ["#F4F1EA", "#8A8A8A", "#FF6B35"]), "cores repetidas"),
            (lambda d: d["movimento"]["curvas"].__setitem__("entrada", [1.2, 0, 0.3, 1]), "x1 e x2 precisam estar entre 0 e 1"),
            (lambda d: d["legenda"].__setitem__("cor", "primarya"), "Quis dizer 'primaria'?"),
            (lambda d: d["legenda"].__setitem__("cor", "dado-9"), "'dado-9' não existe"),
            (lambda d: d["legenda"].__setitem__("papel", "legendas"), "papel tipográfico 'legendas' não existe"),
            (lambda d: d["thumbnail"].__setitem__("fundo", "gradiente:nao_tem"), "gradiente 'nao_tem' não existe"),
            (lambda d: d["movimento"]["transicoes"].__setitem__("padrao", "zoom"), "não está em permitidas"),
            (lambda d: d["cor"]["gradientes"]["profundidade"].__setitem__("paradas", [["fundo", 0.8], ["texto", 0.2]]), "ordem crescente"),
            (lambda d: d["tratamento"]["grade"].__setitem__("curva", [[0, 0], [0.5, 0.4], [0.5, 0.6], [1, 1]]), "estritamente crescentes"),
            (lambda d: d["som"]["musica"].__setitem__("bpm", [120, 90]), "[mínimo, máximo]"),
            (lambda d: d["tipografia"]["papeis"]["titulo"].__setitem__("eixos", {"wght": 900}), "não tem esse eixo"),
            (lambda d: d["tipografia"]["papeis"]["titulo"].__setitem__("arquivo", "plataformas.json"), "não é um arquivo de fonte"),
        ]
        for mutacao, trecho in casos:
            with self.subTest(trecho=trecho):
                erros, _ = self.validar_mutado(mutacao)
                self.assertContem(erros, trecho)

    def test_avisos(self):
        casos = [
            (lambda d: d["cor"]["paleta"].__setitem__("texto", "#7A7A7A"), "abaixo de 4,5:1"),
            (lambda d: d["cor"]["paleta"].__setitem__("texto_suave", "#333333"), "contraste texto_suave×fundo"),
            (lambda d: d["legenda"].__setitem__("corr", "texto"), "legenda.corr: chave desconhecida"),
            (lambda d: d["legenda"]["contorno"].__setitem__("cor", "#123456"), "cor literal fora da paleta"),
            (lambda d: d["legenda"]["posicao"]["vertical"].__setitem__("y", 0.7), "sai da zona segura 'uniao'"),
            (lambda d: d["legenda"].update(contorno=None, fundo=None), "sem contorno e sem caixa de fundo"),
            (lambda d: d["legenda"].__setitem__("cor_destaque", "texto"), "quase iguais"),
            (lambda d: d["cor"].__setitem__("dados", ["#FFC700", "#FFC801", "#8A8A8A", "#FF6B35", "#4FB8B0", "#B08BE8"]), "difíceis de distinguir"),
            (lambda d: d["cor"]["dados"].__setitem__(2, "#1C1C1C"), "ficam apagadas"),
            (lambda d: d["movimento"]["duracoes"].__setitem__("curta", 2.0), "micro < curta < media < longa"),
            (lambda d: d["tipografia"]["escala"].__setitem__("h2", 0.2), "display > h1 > h2"),
            (lambda d: d["tipografia"]["papeis"]["titulo"].__setitem__("largura", 68), "não tem eixo wdth"),
            (lambda d: d["tipografia"]["papeis"]["corpo"].update(arquivo=None, familia="Helvetica Neue"), "fonte do sistema"),
            (lambda d: d["conceito"]["referencias"].append({"arquivo": "referencias/x.jpg", "nota": "n"}), "arquivo não encontrado: referencias/x.jpg"),
            (lambda d: d["formatos"]["vertical"].update(largura=1920, altura=1080), "altura deveria ser maior"),
        ]
        for mutacao, trecho in casos:
            with self.subTest(trecho=trecho):
                erros, avisos = self.validar_mutado(mutacao)
                self.assertEqual(erros, [], "\n".join(erros))
                self.assertContem(avisos, trecho)

    def test_extensao_cor_em_chave_desconhecida_tambem_e_token(self):
        erros, avisos = self.validar_mutado(lambda d: d["graficos"].__setitem__("x_selo", {"cor_fundo": "primarya"}))
        self.assertContem(erros, "graficos.x_selo.cor_fundo")

    def test_tipos_trocados_e_dimensao_zero_nao_viram_traceback(self):
        for descricao, mutar in (
                ("cor.neutros número", lambda d: d["cor"].__setitem__("neutros", 5)),
                ("cor.paleta texto", lambda d: d["cor"].__setitem__("paleta", "amarelo")),
                ("cor.paleta lista", lambda d: d["cor"].__setitem__("paleta", ["#000000"])),
                ("cor.dados objeto", lambda d: d["cor"].__setitem__("dados", {"a": 1})),
                ("cor número", lambda d: d.__setitem__("cor", 7)),
                ("altura zero", lambda d: d["formatos"]["horizontal"].__setitem__("altura", 0)),
                ("largura zero no vertical", lambda d: d["formatos"]["vertical"].__setitem__("largura", 0)),
                ("legenda texto", lambda d: d.__setitem__("legenda", "karaoke")),
                ("tipografia lista", lambda d: d.__setitem__("tipografia", [])),
        ):
            try:
                erros, _ = self.validar_mutado(mutar)
            except Exception as e:                                   # noqa: BLE001 — é exatamente o que o teste proíbe
                self.fail(f"{descricao}: a validação levantou {type(e).__name__}: {e}")
            self.assertTrue(erros, f"{descricao}: deveria reprovar")
            self.assertFalse([e for e in erros if "erro interno" in e], f"{descricao}: {erros}")
        erros, _ = self.validar_mutado(lambda d: d["formatos"]["horizontal"].__setitem__("altura", 0))
        self.assertContem(erros, "formatos.horizontal.altura")
        # pela CLI: mensagem de validação, código 1, sem traceback
        raiz = self.projeto()
        self.editar(raiz / "da" / "da.json", lambda d: d["cor"].__setitem__("neutros", 5))
        r = self.processo("validar", cwd=raiz)
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertNotIn("Traceback", r.stdout + r.stderr)
        self.assertIn("cor.neutros", r.stdout + r.stderr)

    def test_cli_codigos_de_saida(self):
        raiz = self.projeto()
        rc, out, _ = self.cli("validar", "--de", raiz)
        self.assertEqual(rc, 0)
        self.assertIn("Sem erros nem avisos", out)
        self.editar(raiz / "da/da.json", lambda d: d["legenda"]["posicao"]["vertical"].__setitem__("y", 0.7))
        rc, out, _ = self.cli("validar", "--de", raiz)
        self.assertEqual(rc, 0)
        self.assertIn("AVISOS (1)", out)
        self.assertEqual(self.cli("validar", "--de", raiz, "--estrito")[0], 1)
        self.editar(raiz / "da/da.json", lambda d: d["cor"]["paleta"].__setitem__("texto", "#111111"))
        rc, out, _ = self.cli("validar", "--de", raiz)
        self.assertEqual(rc, 1)
        self.assertIn("ERROS (3)", out)                       # texto×fundo, texto×superficie e legenda×contorno
        self.assertIn("AVISOS (3)", out)                      # legenda fora da zona + nome do GC sem contraste + dado "texto" apagado
        self.assertIn("graficos.gc.cor_nome", out)
        self.assertIn("cor.dados: contraste abaixo", out)     # a série usa o token "texto": acompanhou a troca da paleta
        rc, out, _ = self.cli("validar", "--de", raiz, "--json")
        self.assertEqual((rc, json.loads(out)["ok"]), (1, False))
        (raiz / "da/da.json").write_text("{ \"versao_esquema\": 1, }", encoding="utf-8")
        rc, _, err = self.cli("validar", "--de", raiz)
        self.assertEqual(rc, 1)
        self.assertIn("JSON inválido na linha 1", err)
        self.assertEqual(self.cli("validar", da.achar_preset("lab-ia"))[0], 0)       # valida um arquivo avulso


# ══════════════════════════════════════════════════════════════════ herança ══
class TesteHeranca(Base):
    def filho(self, pasta: str, herda, extra: dict | None = None) -> Path:
        p = self.tmp / pasta / "da"
        p.mkdir(parents=True)
        dados = {"versao_esquema": 1, "herda": herda,
                 "projeto": {"nome": pasta, "slug": da.slugificar(pasta), "criada_em": "2026-10-05", "revisao": 1,
                             "aprovada": False, "aprovada_em": None, "aprovada_sha256": None}}
        dados.update(extra or {})
        (p / "da.json").write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
        return p / "da.json"

    def test_deep_merge_filho_vence_e_listas_substituem(self):
        arq = self.filho("série á", "dossie", {
            "cor": {"paleta": {"primaria": "#00C2FF"}, "dados": ["#111111", "#333333", "#555555", "#777777", "#999999", "#BBBBBB"]},
            "movimento": {"transicoes": {"permitidas": ["corte"]}},
            "conceito": {"faca": ["só isto"]},
        })
        d = da.carregar(arq)
        self.assertEqual(d.cor("primaria"), "#00C2FF")                       # filho vence
        self.assertEqual(d.cor("fundo"), "#0A0A0A")                          # resto herdado
        self.assertEqual(d["movimento"]["transicoes"]["permitidas"], ["corte"])   # lista substitui inteira
        self.assertEqual(d["movimento"]["transicoes"]["padrao"], "corte")
        self.assertEqual(d["conceito"]["faca"], ["só isto"])
        self.assertEqual(len(d["conceito"]["nao_faca"]), 5)
        self.assertEqual(d.meta["nome"], "série á")                          # projeto nunca é herdado
        self.assertFalse(d.meta["aprovada"])
        self.assertEqual(len(d.meta["ancestrais"]), 1)
        self.assertTrue(Path(d.fonte("titulo")["caminho"]).is_file())       # fonte achada na base do ancestral (kit)
        lock = da.ler_json(arq.parent / "build" / "da.lock")
        self.assertEqual(len(lock["arquivos"]), 2)                           # da.json + ancestral

    def test_cadeia_de_dois_niveis_por_caminho(self):
        avo = self.filho("avó", "lab-ia", {"cor": {"paleta": {"destaque": "#FF00AA"}}})
        neto = self.filho("neto", "../../avó/da/da.json", {"cor": {"paleta": {"primaria": "#ABCDEF"}}})
        d = da.carregar(neto)
        self.assertEqual((d.cor("primaria"), d.cor("destaque"), d.cor("secundaria")), ("#ABCDEF", "#FF00AA", "#9D7BFF"))
        self.assertEqual(len(d.meta["ancestrais"]), 2)
        sha1 = d.sha256
        time.sleep(0.01)
        self.editar(avo, lambda x: x["cor"]["paleta"].__setitem__("destaque", "#00FF00"))
        self.assertTrue(da.precisa_compilar(neto)[0])                        # ancestral mudou ⇒ lock velho
        d2 = da.carregar(neto)
        self.assertEqual(d2.cor("destaque"), "#00FF00")
        self.assertNotEqual(d2.sha256, sha1)

    def test_filho_sem_projeto_e_invalido(self):
        arq = self.filho("sem projeto", "dossie")
        self.editar(arq, lambda x: x.pop("projeto"))
        self.assertContem(da.validar(arq)["erros"], "\"projeto\"")

    def test_ciclo_e_detectado(self):
        a = self.filho("ciclo a", "../../ciclo b/da/da.json")
        b = self.filho("ciclo b", "../../ciclo a/da/da.json")
        for arq in (a, b):
            with self.assertRaises(da.DAErro) as c:
                da.carregar(arq)
            self.assertIn("ciclo", str(c.exception))
        eu = self.filho("eu mesmo", "da.json")
        with self.assertRaises(da.DAErro) as c:
            da.validar(eu)
        self.assertIn("ciclo", str(c.exception))
        r = self.processo("compilar", "--da", a)
        self.assertEqual(r.returncode, 1)
        self.assertIn("ciclo", r.stderr)

    def test_herda_inexistente(self):
        with self.assertRaises(da.DAErro) as c:
            da.carregar(self.filho("órfão", "dossiee"))
        self.assertIn("dossie", str(c.exception))
        with self.assertRaises(da.DAErro) as c:
            da.carregar(self.filho("órfão 2", "../nada/da.json"))
        self.assertIn("não existe", str(c.exception))


# ═════════════════════════════════════════════════════════════════ compilar ══
class TesteCompilar(Base):
    def test_saidas_e_conteudo(self):
        raiz = self.projeto()
        build = raiz / "da" / "build"
        css = (build / "da.css").read_text(encoding="utf-8")
        for trecho in ("--da-cor-primaria:#FFC700;", "--da-cor-primaria-rgb:255, 199, 0;", "--da-cor-texto-suave:#8A8A8A;",
                       "--da-dado-1:#FFC700;", "--da-neutro-1:#000000;", "--da-fonte-titulo:\"Archivo SemiExpanded\";",
                       "--da-peso-titulo:900;", "--da-largura-titulo:100%;", "--da-tracking-subtitulo:0.2em;",
                       "--da-caixa-titulo:uppercase;", "--da-caixa-corpo:none;", "--da-escala-h1:calc(var(--da-lado) * 0.085);",
                       "--da-dur-curta:0.28s;", "--da-curva-entrada:cubic-bezier(0.215, 0.61, 0.355, 1);",
                       "--da-margem:calc(var(--da-lado) * 0.065);", "--da-calha:", "--da-raio:", "--da-traco:",
                       "--da-escala-x-titulo:0.66;", "--da-gradiente-profundidade:linear-gradient(180deg, #161616 0%, #0A0A0A 100%);",
                       ".da-titulo{", ".da-subtitulo{", ".da-corpo{", ".da-dados{", ".da-legenda{"):
            self.assertIn(trecho, css)
        self.assertIn("projeto%20com%20espa%C3%A7o/da/fontes/ArchivoSemiExpanded-Black.ttf", css)    # URL file:// codificada
        self.assertEqual(css.count("@font-face"), 3)                         # Archivo + Plex Bold + Plex Medium (sem duplicar)
        js = (build / "da.js").read_text(encoding="utf-8")
        self.assertIn("g.DA=congelar({", js)
        corpo = js[js.index("congelar({") + len("congelar("):js.rindex(");\n})")]
        obj = json.loads(corpo)
        self.assertEqual(set(obj["_meta"]) >= {"sha256", "revisao", "aprovada", "raiz"}, True)
        self.assertEqual(obj["_meta"]["raiz"], str(raiz))
        res = da.ler_json(build / "da.resolvida.json")
        self.assertEqual(res["legenda"]["cor_hex"], "#F4F1EA")               # tokens resolvidos em campos paralelos
        self.assertEqual(res["legenda"]["cor"], "texto")
        self.assertIsNone(res["legenda"]["cor_falada_hex"])
        self.assertEqual(res["tratamento"]["moldura"]["cor_hex"], "#FFC700")
        self.assertEqual(res["cor"]["gradientes"]["profundidade"]["paradas_hex"], [["#161616", 0], ["#0A0A0A", 1]])
        self.assertTrue(Path(res["tipografia"]["papeis"]["titulo"]["arquivo_abs"]).is_absolute())
        self.assertEqual(res["formatos"]["horizontal"]["fps_num"], 30000)
        self.assertEqual(res["thumbnail"]["fundo_tipo"], "cor")
        self.assertIn("#FFC700", res["cor"]["permitidas"])
        grade = da.ler_json(build / "grade.json")
        self.assertEqual(set(grade["formatos"]), {"horizontal", "vertical", "quadrado", "thumbnail"})
        self.assertEqual(grade["formatos"]["horizontal"]["cadeia"], "eq=contrast=1.08:saturation=0.78,vignette=angle=0.35,noise=c0s=6:c0f=t+u")
        self.assertEqual(grade["formatos"]["horizontal"]["cadeia_cor"], "eq=contrast=1.08:saturation=0.78")
        self.assertIsNone(grade["velocidade"]["video"])
        self.assertGreaterEqual(len(grade["mapeamento"]), 10)
        lock = da.ler_json(build / "da.lock")
        self.assertEqual(lock["sha256"], res["_meta"]["sha256"])
        self.assertEqual(lock["kit_versao"], da.KIT_VERSAO)
        md = (raiz / "da" / "DA.md").read_text(encoding="utf-8")
        for trecho in ("# Direção de arte — Projeto de teste", "**Faça**", "**Não faça**", "`#FFC700`", "Archivo SemiExpanded",
                       "## Movimento", "## Tratamento de imagem", "NÃO APROVADA"):
            self.assertIn(trecho, md)

    def test_fonte_variavel_no_css_e_no_pil(self):
        raiz = self.projeto(base="lab-ia")
        css = (raiz / "da/build/da.css").read_text(encoding="utf-8")
        self.assertIn("font-weight:100 900;font-stretch:75% 100%;", css)      # Roboto: eixos wght e wdth
        self.assertIn("font-weight:300 700;", css)                            # Fira Code: só wght
        self.assertIn("--da-eixos-titulo:\"wght\" 700, \"wdth\" 82;", css)
        self.assertIn("--da-largura-titulo:82%;", css)
        self.assertEqual(css.count("@font-face"), 2)                          # uma regra por arquivo variável
        d = da.carregar(raiz)
        p = d.fonte("legenda")
        self.assertTrue(p["variavel"])
        self.assertEqual(p["eixos_efetivos"], {"wght": 800, "wdth": 88})
        try:
            f = d.fonte_pil("legenda", 40)
        except ImportError:
            self.skipTest("Pillow ausente")
        larga = da.carregar(raiz).fonte_pil("corpo", 40).getlength("Direção de arte")
        self.assertGreater(larga, 0)
        self.assertGreater(f.getlength("Direção de arte"), 0)

    def test_lock_velho_recompila_sozinho(self):
        raiz = self.projeto()
        lock = raiz / "da/build/da.lock"
        self.assertEqual(da.precisa_compilar(raiz / "da/da.json"), (False, "em dia"))
        antes = lock.stat().st_mtime_ns
        d = da.carregar(raiz)                                                 # em dia: não reescreve nada
        self.assertEqual(lock.stat().st_mtime_ns, antes)
        sha1 = d.sha256
        time.sleep(0.01)
        self.editar(raiz / "da/da.json", lambda x: x["cor"]["paleta"].__setitem__("primaria", "#00C2FF"))
        velho, motivo = da.precisa_compilar(raiz / "da/da.json")
        self.assertTrue(velho)
        self.assertIn("da.json", motivo)
        d2 = da.carregar(raiz)                                                # consumidor recompila sozinho
        self.assertEqual(d2.cor("primaria"), "#00C2FF")
        self.assertNotEqual(d2.sha256, sha1)
        self.assertIn("--da-cor-primaria:#00C2FF;", (raiz / "da/build/da.css").read_text(encoding="utf-8"))
        self.assertFalse(da.precisa_compilar(raiz / "da/da.json")[0])
        (raiz / "da/build/da.css").unlink()                                   # saída apagada ⇒ velho
        self.assertTrue(da.precisa_compilar(raiz / "da/da.json")[0])
        da.carregar(raiz)
        self.assertTrue((raiz / "da/build/da.css").is_file())

    def test_arquivo_referenciado_mudou_muda_a_identidade(self):
        raiz = self.projeto()
        sha1 = da.carregar(raiz).sha256
        fonte = raiz / "da/fontes/IBMPlexMono-Medium.ttf"
        shutil.copy2(KIT / "fontes" / "IBMPlexMono-Regular.ttf", fonte)       # mesma chave, outro arquivo
        velho, motivo = da.precisa_compilar(raiz / "da/da.json")
        self.assertTrue(velho)
        self.assertIn("referenciado", motivo)
        self.assertNotEqual(da.carregar(raiz).sha256, sha1)

    def test_da_invalida_nao_compila_nem_deixa_lock_novo(self):
        raiz = self.projeto()
        lock_antes = (raiz / "da/build/da.lock").read_bytes()
        self.editar(raiz / "da/da.json", lambda x: x["cor"]["paleta"].__setitem__("texto", "#101010"))
        with self.assertRaises(da.DAInvalida) as c:
            da.compilar(raiz)
        self.assertContem(c.exception.erros, "contraste texto×fundo")
        with self.assertRaises(da.DAInvalida):
            da.carregar(raiz)
        self.assertEqual((raiz / "da/build/da.lock").read_bytes(), lock_antes)
        rc, _, err = self.cli("compilar", "--de", raiz)
        self.assertEqual(rc, 1)
        self.assertIn("contraste texto×fundo", err)

    def test_preset_embutido_nao_e_compilado_no_kit(self):
        with self.assertRaises(da.DAErro):
            da.compilar(da.achar_preset("dossie"))
        d = da.carregar(da.achar_preset("dossie"))                            # mas pode ser lido em memória
        self.assertEqual(d.cor("primaria"), "#FFC700")
        self.assertFalse((KIT / "presets" / "build").exists())
        self.assertFalse((KIT / "build").exists())

    def test_tratamento_neutro_vira_null(self):
        raiz = self.projeto()

        def neutro(x):
            t = x["tratamento"]
            t["grade"].update(lut=None, exposicao=0, contraste=1, saturacao=1.0, gama=1, temperatura=0, matiz=0, curva=None)
            t["duotone"]["ativo"] = False
            t["grao"]["ativo"] = False
            t["vinheta"]["ativo"] = False
            t.update(nitidez=0, desfoque=0)

        self.editar(raiz / "da/da.json", neutro)
        d = da.carregar(raiz)
        for parte in ("completa", "cor", "acabamento"):
            self.assertEqual(d.grade("horizontal", parte=parte), "null")
        g = da.ler_json(raiz / "da/build/grade.json")
        self.assertTrue(all(f["neutro"] and f["cadeia"] == "null" for f in g["formatos"].values()))

    def test_cadeia_completa_e_dominios_de_cor(self):
        raiz = self.projeto()
        (raiz / "da/luts/teste d'água, v1.cube").write_text("LUT_3D_SIZE 2\n0 0 0\n1 0 0\n0 1 0\n1 1 0\n0 0 1\n1 0 1\n0 1 1\n1 1 1\n")

        def tudo(x):
            t = x["tratamento"]
            t["grade"].update(lut="luts/teste d'água, v1.cube", intensidade_lut=0.5, exposicao=0.5, temperatura=-40, matiz=10,
                              curva=[[0, 0], [0.5, 0.56], [1, 1]])
            t["duotone"].update(ativo=True, mistura=0.3)
            t.update(nitidez=0.4, desfoque=0.002, velocidade=0.25)

        self.editar(raiz / "da/da.json", tudo)
        d = da.carregar(raiz)
        c = d.grade("horizontal")
        ordem = ["lutyuv=", "eq=", "hue=h=10", "format=gbrp", "colortemperature=temperature=12000:mix=0.4:pl=1", "curves=all='0/0 0.5/0.56 1/1'",
                 "lut3d=file=", "blend=all_mode=normal:all_opacity=0.5", "colorchannelmixer=", "lutrgb=", "all_opacity=0.3",
                 "gblur=sigma=2.16", "format=yuv420p", "unsharp=", "vignette=", "noise=c0s=6:c0f=t+u"]
        posicoes = [c.index(x) for x in ordem]
        self.assertEqual(posicoes, sorted(posicoes), c)
        self.assertEqual(c.count("format=gbrp"), 1)                           # uma ida a RGB…
        self.assertEqual(c.count("format=yuv420p"), 1)                        # …e uma volta
        self.assertIn("teste d\\\\\\'água\\, v1.cube", c)                     # caminho escapado nos dois níveis
        self.assertIn("gblur=sigma=1.44", d.grade(1280, 720))                 # px seguem o lado menor
        self.assertTrue(d.grade("thumbnail").endswith("noise=c0s=6:c0f=t+u"))
        self.assertIn("format=yuv444p", d.grade("thumbnail"))                 # imagem parada volta em 4:4:4
        self.assertTrue(d.grade("horizontal", parte="cor").endswith("format=yuv420p"))
        self.assertTrue(d.grade("horizontal", parte="acabamento").startswith("gblur="))
        self.assertEqual(da.filtros_da_cadeia(c), ["lutyuv", "eq", "hue", "format", "colortemperature", "curves", "split",
                                                   "lut3d", "blend", "colorchannelmixer", "lutrgb", "gblur", "unsharp",
                                                   "vignette", "noise"])
        g = da.ler_json(raiz / "da/build/grade.json")
        self.assertEqual(g["velocidade"], {"fator": 0.25, "video": "setpts=PTS/0.25", "audio": "atempo=0.5,atempo=0.5"})
        # só grão sobre fonte de formato desconhecido: a guarda garante que o ruído cai na luma
        self.editar(raiz / "da/da.json", lambda x: (x["tratamento"]["grade"].update(lut=None, exposicao=0, contraste=1, saturacao=1, temperatura=0, matiz=0, curva=None),
                                                    x["tratamento"]["duotone"].update(ativo=False), x["tratamento"]["vinheta"].update(ativo=False),
                                                    x["tratamento"].update(nitidez=0, desfoque=0)))
        self.assertEqual(da.carregar(raiz).grade("horizontal"), da.GUARDA_YUV + ",noise=c0s=6:c0f=t+u")

    def test_api_do_objeto(self):
        raiz = self.projeto()
        os.chdir(raiz / "animacoes")
        d = da.carregar()
        self.assertIsInstance(d, dict)
        self.assertEqual(d.raiz, raiz)
        self.assertEqual(d.caminho, raiz / "da/da.json")
        self.assertEqual((d.revisao, d.aprovada), (1, False))
        self.assertEqual(len(d.sha256), 64)
        self.assertEqual(d.cor("primaria"), "#FFC700")
        self.assertEqual(d.cor("#fc0"), "#FFCC00")
        self.assertEqual(d.cor("dado-2"), "#F4F1EA")
        self.assertEqual(d.cor("neutro-1"), "#000000")
        self.assertEqual(d.rgb("fundo"), (10, 10, 10))
        self.assertEqual(d.rgba("primaria", 0.5), (255, 199, 0, 128))
        with self.assertRaises(da.DAErro) as c:
            d.cor("primarya")
        self.assertIn("Quis dizer 'primaria'?", str(c.exception))
        f = d.fonte("titulo")
        self.assertEqual((f["familia"], f["peso"], f["caixa"], f["escala_x"]), ("Archivo SemiExpanded", 900, "alta", 0.66))
        self.assertEqual(Path(f["caminho"]), raiz / "da/fontes/ArchivoSemiExpanded-Black.ttf")
        self.assertEqual(d.fonte("corpo")["escala_x"], 1)                     # padrão do esquema aplicado
        self.assertEqual(d.texto("titulo", "olá"), "OLÁ")
        self.assertEqual(d.texto("corpo", "olá"), "olá")
        with self.assertRaises(da.DAErro):
            d.fonte("rodape")
        self.assertEqual(d.px(0.058, 1080, 1920), 63)
        self.assertEqual(d.px(0.058, 1920, 1080), 63)                         # sempre o lado menor
        self.assertEqual(d.px(0.1, "thumbnail"), 72)
        self.assertEqual(d.formato("vertical"), (1080, 1920, Fraction(30000, 1001)))
        self.assertEqual(d.formato("thumbnail"), (1280, 720, None))
        with self.assertRaises(da.DAErro):
            d.formato("panoramico")
        m = d.margens("vertical")                                              # padrão: união (pior caso)
        self.assertEqual((m["plataforma"], m["topo"], m["base"], m["esquerda"], m["direita"]), ("uniao", 288, 672, 120, 300))
        self.assertEqual((m["x0"], m["y0"], m["x1"], m["y1"], m["largura"]), (120, 288, 780, 1248, 660))   # = plataformas.json (0,2778 × 1080 = 300,02 → 300)
        self.assertEqual(d.margens("vertical", "instagram")["topo"], 269)
        self.assertEqual(d.margens("horizontal")["largura"], 1728)
        self.assertEqual(d.margens("thumbnail")["x0"], 64)                    # sem entrada própria: usa horizontal.padrao
        with self.assertRaises(da.DAErro):
            d.margens("vertical", "kwai")
        self.assertEqual(d.curva("entrada"), (0.215, 0.61, 0.355, 1))
        e = d.facilitar("entrada")
        self.assertEqual((e(0), e(1), e(-1), e(2)), (0.0, 1.0, 0.0, 1.0))
        self.assertGreater(e(0.5), 0.5)                                        # curva de saída suave: adianta o progresso
        self.assertAlmostEqual(d.facilitar("linear")(0.37), 0.37, places=4)
        self.assertEqual(d.dur("curta"), 0.28)
        self.assertEqual(d.token("legenda.cor"), "#F4F1EA")
        self.assertEqual(d.token("legenda.cor", resolver_cores=False), "texto")
        self.assertEqual(d.token("cor.dados.0"), "#FFC700")
        self.assertEqual(d.token("cor.dados[1]"), "#F4F1EA")
        self.assertEqual(d.token("movimento.duracoes.media"), 0.5)
        with self.assertRaises(da.DAErro):
            d.token("legenda.nada")
        self.assertEqual(d.css, raiz / "da/build/da.css")
        self.assertGreater(d.contraste("texto", "fundo"), 15)

    def test_cli_token_mostrar_presets_compilar(self):
        raiz = self.projeto()
        os.chdir(raiz)
        self.assertEqual(self.cli("token", "cor.paleta.primaria")[1].strip(), "#FFC700")
        self.assertEqual(self.cli("token", "legenda.cor", "--bruto")[1].strip(), "texto")
        self.assertEqual(self.cli("token", "tipografia.escala.h1", "--formato", "vertical")[1].strip(), "92")
        self.assertEqual(json.loads(self.cli("token", "movimento.curvas.linear")[1]), [0, 0, 1, 1])
        self.assertEqual(self.cli("token", "marca.logo")[1].strip(), "null")
        rc, _, err = self.cli("token", "cor.paleta.primari")
        self.assertEqual(rc, 1)
        self.assertIn("Quis dizer 'primaria'?", err)
        rc, out, _ = self.cli("mostrar")
        self.assertEqual(rc, 0)
        for trecho in ("Projeto de teste", "não aprovada", "#FFC700", "Archivo SemiExpanded 900", "cadeia ffmpeg"):
            self.assertIn(trecho, out)
        rc, out, _ = self.cli("compilar", "--se-preciso")
        self.assertIn("em dia", out)
        rc, out, _ = self.cli("compilar")
        self.assertIn("da/build/da.css", out)
        rc, out, _ = self.cli("presets")
        for nome in PRESETS:
            self.assertIn(nome, out)
        self.assertIn("Dossiê investigativo", out)
        rc, out, _ = self.cli("grade", "--formato", "vertical", "--parte", "cor")
        self.assertEqual(out.strip(), "eq=contrast=1.08:saturation=0.78")
        rc, out, _ = self.cli("achar", "--json")
        self.assertEqual(json.loads(out)["raiz"], str(raiz))
        r = self.processo("--help")
        self.assertEqual(r.returncode, 0)
        self.assertIn("uso: da.py", r.stdout)
        self.assertIn("conferir-carimbo", r.stdout)
        self.assertNotIn("usage:", r.stdout)
        self.assertEqual(self.cli()[0], da.SAIDA_USO)
        self.assertEqual(self.cli("comando-que-nao-existe")[0], da.SAIDA_USO)


# ════════════════════════════════════════════════════════════════ aprovação ══
class TesteAprovacao(Base):
    def test_aprovar_editar_revisar(self):
        raiz = self.projeto()
        arq = raiz / "da/da.json"
        sha0 = da.carregar(raiz).sha256
        r = da.aprovar(raiz)
        self.assertEqual((r["estado"], r["revisao"], r["sha256"]), ("aprovada", 1, sha0))
        proj = da.ler_json(arq)["projeto"]
        self.assertTrue(proj["aprovada"])
        self.assertEqual(proj["aprovada_sha256"], sha0)
        self.assertRegex(proj["aprovada_em"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")
        d = da.carregar(raiz)
        self.assertTrue(d.aprovada)
        self.assertEqual(d.sha256, sha0)                                       # aprovar não muda a identidade
        self.assertIn("APROVADA em", (raiz / "da/DA.md").read_text(encoding="utf-8"))
        self.assertEqual(da.validar(raiz)["avisos"], [])
        self.assertEqual(da.aprovar(raiz)["estado"], "ja_aprovada")
        # edição depois da aprovação: aviso forte em validar e compilar; aprovar recusa
        self.editar(arq, lambda x: x["cor"]["paleta"].__setitem__("primaria", "#FFD21F"))
        self.assertContem(da.validar(raiz)["avisos"], "ALTERADA DEPOIS DA APROVAÇÃO")
        self.assertContem(da.compilar(raiz)["avisos"], "ALTERADA DEPOIS DA APROVAÇÃO")
        d = da.carregar(raiz)
        self.assertFalse(d.aprovada)
        self.assertTrue(d.meta["alterada_apos_aprovacao"])
        self.assertIn("ALTERADA DEPOIS DA APROVAÇÃO", (raiz / "da/DA.md").read_text(encoding="utf-8"))
        with self.assertRaises(da.DAErro) as c:
            da.aprovar(raiz)
        self.assertIn("revisar", str(c.exception))
        # revisar: sobe a revisão e zera a aprovação, sem mexer na identidade
        sha1 = d.sha256
        r = da.revisar(raiz)
        self.assertEqual((r["anterior"], r["revisao"], r["estava_aprovada"]), (1, 2, True))
        proj = da.ler_json(arq)["projeto"]
        self.assertEqual((proj["revisao"], proj["aprovada"], proj["aprovada_em"], proj["aprovada_sha256"]), (2, False, None, None))
        self.assertEqual(da.validar(raiz)["avisos"], [])
        self.assertEqual(da.carregar(raiz).sha256, sha1)
        r = da.aprovar(raiz)
        self.assertEqual((r["estado"], r["revisao"], r["sha256"]), ("aprovada", 2, sha1))
        self.assertNotEqual(sha0, sha1)

    def test_nao_aprova_da_invalida(self):
        raiz = self.projeto()
        self.editar(raiz / "da/da.json", lambda x: x["cor"]["paleta"].__setitem__("texto", "#101010"))
        with self.assertRaises(da.DAInvalida):
            da.aprovar(raiz)
        self.assertFalse(da.ler_json(raiz / "da/da.json")["projeto"]["aprovada"])

    def test_cli(self):
        raiz = self.projeto()
        os.chdir(raiz / "render")
        rc, out, _ = self.cli("aprovar")
        self.assertEqual(rc, 0)
        self.assertIn("DA aprovada: revisão 1", out)
        self.assertIn("já estava aprovada", self.cli("aprovar")[1])
        rc, out, _ = self.cli("revisar")
        self.assertIn("Revisão 1 → 2", out)
        self.assertIn("revisão 2", self.cli("mostrar")[1])


# ═════════════════════════════════════════════════════════════════════ lint ══
class TesteLint(Base):
    def setUp(self):
        super().setUp()
        self.raiz = self.projeto()
        self.cena = self.raiz / "animacoes" / "cena 01"
        self.cena.mkdir(parents=True)
        self.d = da.carregar(self.raiz)

    def achados(self, nome: str, conteudo: str) -> list[dict]:
        arq = self.cena / nome
        arq.write_text(conteudo, encoding="utf-8")
        return da.lint([arq], da=self.d)["achados"]

    def regras(self, nome: str, conteudo: str) -> list[tuple[str, int]]:
        return [(a["regra"], a["linha"]) for a in self.achados(nome, conteudo) if a["severidade"] == "erro"]

    def test_positivos_css(self):
        css = ("#palco { color: #FFC700; }\n"                         # 1 hex
               ".a { background: rgba(10, 10, 10, .86); }\n"          # 2 função
               ".b { border: 1px solid red; }\n"                      # 3 nome
               ".c { font-family: 'Archivo SemiExpanded', sans-serif; }\n"   # 4 fonte
               ".d { color: hsl(47 100% 50%); }\n"                    # 5 função
               ".e { font: 700 20px Arial; }\n"                       # 6 fonte (atalho)
               ".f { --minha: #fff; box-shadow: 0 0 4px #0008; }\n"   # 7 hex ×2 (3 e 4 dígitos)
               ".g { background: linear-gradient(90deg, white, #000000); }\n"   # 8 nome + hex
               ".h { fill: Tomato; stroke: rgb(0 0 0 / 50%); }\n"     # 9 nome (qualquer caixa) + função
               "@font-face { font-family: \"Minha\"; src: url(x.ttf); }\n")     # 10 fonte
        self.assertEqual(self.regras("ruim.css", css),
                         [("cor-hex", 1), ("cor-funcao", 2), ("cor-nome", 3), ("fonte-literal", 4), ("cor-funcao", 5),
                          ("fonte-literal", 6), ("cor-hex", 7), ("cor-hex", 7), ("cor-nome", 8), ("cor-hex", 8),
                          ("cor-nome", 9), ("cor-funcao", 9), ("fonte-literal", 10)])

    def test_positivos_html_js_json_svg(self):
        html = ("<html><head><style>\n.t{color:#abcdef}\n</style></head><body>\n"                # 2
                "<div style=\"color:#fff; border-color: white\">x</div>\n"                       # 4 ×2
                "<svg><rect fill=\"#0a0a0a\" stroke=\"black\"/><text font-family=\"Arial\">a</text></svg>\n"   # 5 ×3
                "<font face=\"Verdana\" color=\"red\">x</font>\n"                                # 6 ×2
                "<div data-cor=\"#FFC700\"></div>\n"                                             # 7
                "<script>\nel.style.color = 'red';\nel.style.background = \"#1a2b3c\";\n"        # 9, 10
                "ctx.font = 'bold 20px Helvetica';\nconst s = {fontFamily: \"Roboto\", cor: 'white'};\n"   # 11, 12 ×2
                "el.style.cssText = 'color: blue; font-family: Georgia';\n"                      # 13 ×2
                "g.addColorStop(0, 'black'); e.setAttribute('fill', 'orange');\n</script></body></html>\n")   # 14 ×2
        self.assertEqual(self.regras("ruim.html", html),
                         [("cor-hex", 2), ("cor-hex", 4), ("cor-nome", 4), ("cor-hex", 5), ("cor-nome", 5), ("fonte-literal", 5),
                          ("fonte-literal", 6), ("cor-nome", 6), ("cor-hex", 7), ("cor-nome", 9), ("cor-hex", 10),
                          ("fonte-literal", 11), ("fonte-literal", 12), ("cor-nome", 12), ("cor-nome", 13), ("fonte-literal", 13),
                          ("cor-nome", 14), ("cor-nome", 14)])
        js = ("export const Y = '#FFC700';\nconst caixa = `rgba(10,10,10,.86)`;\nel.style.fill = \"white\";\n"
              "el.style.fontFamily = 'PlexMono, monospace';\nel.style.cssText = 'border: 1px solid #333';\n"
              "const cor = 'veja #abc';\n")                         # 5: hex em contexto CSS · 6: propriedade de cor
        self.assertEqual(self.regras("ruim.js", js), [("cor-hex", 1), ("cor-funcao", 2), ("cor-nome", 3), ("fonte-literal", 4),
                                                       ("cor-hex", 5), ("cor-hex", 6)])
        sb = ("{\"cenas\": [{\"cor\": \"#F4F1EA\", \"fundo\": \"white\", \"borda\": \"2px solid #333\",\n"
              "  \"sombra\": \"rgba(0,0,0,0.5)\", \"font_family\": \"Arial\", \"cor_titulo\": \"gold\", \"cor_x\": \"tom #abc\"}]}\n")
        self.assertEqual(self.regras("ruim.json", sb), [("cor-hex", 1), ("cor-nome", 1), ("cor-hex", 1), ("cor-funcao", 2),
                                                         ("fonte-literal", 2), ("cor-nome", 2), ("cor-hex", 2)])
        svg = "<svg xmlns=\"http://www.w3.org/2000/svg\"><style>.a{fill:#ff0000}</style><circle stroke=\"rgb(1,2,3)\"/></svg>\n"
        self.assertEqual(self.regras("ruim.svg", svg), [("cor-hex", 1), ("cor-funcao", 1)])

    def test_casos_de_borda_nos_dois_sentidos(self):
        # deviam acusar e não acusavam
        js = ("const s = { cor: '#FF0000', fundo: 'navy' };\n"                 # 1: hex + nome em chave de cor
              "palco.style.boxShadow = '0 0 4px black';\n"                     # 2: nome dentro de propriedade composta
              "el.style.border = '1px solid tomato';\n"                        # 3
              "el.style.background = 'linear-gradient(red, var(--da-cor-fundo))';\n")   # 4: só o red
        self.assertEqual(self.regras("borda.js", js), [("cor-hex", 1), ("cor-nome", 1), ("cor-nome", 2), ("cor-nome", 3), ("cor-nome", 4)])
        self.assertEqual(self.regras("borda.css", ".a { color: color(display-p3 1 0 0); }\n"), [("cor-funcao", 1)])
        sb = ("{\"background\": \"linear-gradient(red, blue)\",\n"                 # 1: dois nomes
              " \"style\": \"font-family: Arial; color: navy\"}\n")                # 2: fonte + nome
        self.assertEqual(self.regras("borda.json", sb), [("cor-nome", 1), ("cor-nome", 1), ("fonte-literal", 2), ("cor-nome", 2)])
        # acusavam e não deviam
        self.assertEqual(self.regras("texto.css", ".a::before { content: \"red #fff\"; color: var(--da-cor-texto); }\n"), [])
        self.assertEqual(self.regras("log.js", "console.log('cor: #ff0000 não é permitida');\nconsole.warn(`fundo: red`);\n"), [])
        self.assertEqual(self.regras("mix.css", ".a { color: color-mix(in srgb, var(--da-cor-primaria) 50%, transparent); }\n"), [])
        # "é exatamente" só quando é o mesmo hex
        a = self.achados("quase.css", ".a { color: rgb(1, 2, 3); }\n.b { color: #000000; }\n")
        self.assertNotIn("é exatamente", a[0]["sugestao"])
        self.assertIn("mais próximo", a[0]["sugestao"])
        self.assertIn("é exatamente o token neutro-1", a[1]["sugestao"])

    def test_negativos(self):
        limpos = {
            "bom.css": ("/* comentário com #FFC700 e red não conta */\n"
                        "#abc, #fade > .x, a:hover #bad { color: var(--da-cor-texto); }\n"
                        "#palco{background:var(--da-cor-fundo);border:var(--da-traco) solid var(--da-cor-primaria)}\n"
                        ".a{background:rgba(var(--da-cor-fundo-rgb), .86);color:rgba(var(--da-cor-texto-rgb), .5)}\n"
                        ".b{font-family:var(--da-fonte-titulo);font-size:var(--da-escala-h1);font:inherit}\n"
                        ".c{fill:none;stroke:currentColor;color:inherit;background:transparent;border-color:initial}\n"
                        ".d{background:var(--da-gradiente-profundidade), url(textura#fff.png);box-shadow:var(--da-sombra)}\n"
                        ".e{background:url(\"data:image/svg+xml;utf8,<svg fill='#fff' stroke='red'/>\");mask:url(#abc)}\n"
                        ".f{color:color-mix(in srgb, var(--da-cor-primaria) 50%, transparent);transition:none}\n"
                        "@media (min-width:100px){ #add { opacity:.5 } }\n"
                        ".g{--da-lado:1080px;grid-template-columns:repeat(var(--da-colunas),1fr);filter:grayscale(1)}\n"),
            "bom.html": ("<!doctype html><html><head><!-- #fff red font-family: Arial -->\n"
                         "<link rel=\"stylesheet\" href=\"../../da/build/da.css\"><meta charset=\"utf-8\"></head><body>\n"
                         "<a href=\"#fff\" id=\"abc\" class=\"red\" name=\"#cafe\">âncora</a><label for=\"#bad\">x</label>\n"
                         "<p>Texto com #123456, hashtag #cafe, rgb(1,2,3) e a palavra red não é estilo.</p>\n"
                         "<svg><use xlink:href=\"#fed\"/><rect fill=\"url(#grad)\" clip-path=\"url(#abc)\" stroke=\"none\"/>\n"
                         "<rect fill=\"currentColor\" style=\"fill:var(--da-cor-primaria)\"/></svg>\n"
                         "<div class=\"da-titulo\" style=\"color:var(--da-cor-texto);font-family:var(--da-fonte-corpo)\">ok</div>\n"
                         "<script src=\"../../da/build/da.js\"></script><script>\n"
                         "// comentário: el.style.color = '#ffffff'; font-family: Arial\n"
                         "/* bloco: red #000 rgb(0,0,0) */\n"
                         "const el = document.querySelector('#fff'), b = document.getElementById(\"#abc\"), c = $('#bad');\n"
                         "el.style.color = DA.cor.paleta.primaria; el.style.background = `rgb(${DA.cor.paleta_rgb.fundo.join(' ')} / .8)`;\n"
                         "ctx.fillStyle = `rgba(${r}, ${g}, ${b}, .5)`; ctx.font = `${px}px ${DA.tipografia.papeis.titulo.familia}`;\n"
                         "el.style.fontFamily = 'var(--da-fonte-dados)'; const red = 1, tan = Math.tan(red), cor = red;\n"
                         "const t = 'color', u = \"Top #100\", href = '#abc', estado = {cor: 'primaria', fundo: \"superficie\"};\n"
                         "window.seek = function(t){ el.style.opacity = Math.min(1, t / DA.movimento.duracoes.curta); };\n"
                         "</script></body></html>\n"),
            "bom.json": ("{\"cenas\": [{\"titulo\": \"Top #100 de 2024 #cafe\", \"cor\": \"primaria\", \"fundo\": \"superficie\",\n"
                         " \"fonte\": \"IBGE, 2024\", \"familia\": \"titulo\", \"font_family\": \"dados\", \"texto\": \"O céu é blue e red\",\n"
                         " \"nota\": \"veja rgba(var(--da-cor-fundo-rgb), .5)\", \"id\": \"#abc\", \"cor_serie\": \"dado-2\",\n"
                         " \"alvo\": \"#palco\", \"seletor\": \"#fff\", \"elemento_id\": \"#bad\", \"href\": \"#cafe\"}]}\n"),
            "bom.js": ("import {x} from './lib.js'; // #fff\nexport const cor = DA.cor.paleta.primaria;\n"
                       "const re = /#[0-9a-f]{6}/i; class A { #abc = 1; m(){ return this.#abc; } }\n"
                       "const url = 'https://exemplo.com/pagina#fff'; const css = `var(--da-cor-texto)`;\n"),
        }
        for nome, conteudo in limpos.items():
            with self.subTest(arquivo=nome):
                achados = self.achados(nome, conteudo)
                self.assertEqual(achados, [], "\n".join(f"{a['linha']}:{a['coluna']} {a['regra']} {a['trecho']}" for a in achados))

    def test_excecoes_da_livre(self):
        self.assertEqual(self.regras("ex.css", ".a{color:#123456} /* da-livre: cor da marca do patrocinador */\n.b{color:#654321}\n"),
                         [("cor-hex", 2)])
        bloco = "/* da-livre:inicio */\n.a{color:#111111}\n.b{color:red}\n/* da-livre:fim */\n.c{color:#222222}\n"
        self.assertEqual(self.regras("bloco.css", bloco), [("cor-hex", 5)])
        html = ("<img src=\"logo.png\" data-da-livre\n     style=\"border:2px solid #00ff00\">\n"
                "<span style=\"color:#00ff00\">x</span>\n")
        self.assertEqual(self.regras("ex.html", html), [("cor-hex", 3)])        # o elemento inteiro (2 linhas) fica livre
        arq = self.cena / "terceiros.js"
        arq.write_text("// da-livre-arquivo: biblioteca de terceiros\nconst a = '#ff0000';\n", encoding="utf-8")
        r = da.lint([arq], da=self.d)
        self.assertEqual((r["achados"], r["arquivos"]), ([], 0))
        self.assertContem(r["notas"], "da-livre-arquivo")

    def test_avisos_de_animacao_nao_reprovam_sem_estrito(self):
        css = ".a{transition:opacity .3s;animation-name:pisca}\n@keyframes pisca{from{opacity:0}to{opacity:1}}\n"
        arq = self.cena / "anim.css"
        arq.write_text(css + "", encoding="utf-8")
        (self.cena / "anim.js").write_text("requestAnimationFrame(loop); el.animate([], 300); el.style.transition = 'none';\n", encoding="utf-8")
        r = da.lint([self.cena], da=self.d)
        self.assertEqual((r["erros"], r["avisos"], r["ok"]), (0, 6, True))
        self.assertTrue(all(a["regra"] == "animacao-css" for a in r["achados"]))
        self.assertEqual(self.cli("lint", self.cena, "--da", self.raiz)[0], 0)
        self.assertEqual(self.cli("lint", self.cena, "--da", self.raiz, "--estrito")[0], 1)

    def test_sugere_o_token_mais_proximo_e_posicao(self):
        a = self.achados("s.css", ".a{\n  color: #FFC700;\n  background: rgba(10, 10, 10, .86);\n  border-color: #F9C400;\n  outline-color: #00FF00;\n}\n")
        self.assertEqual((a[0]["linha"], a[0]["coluna"]), (2, 10))
        self.assertIn("var(--da-cor-primaria)", a[0]["sugestao"])
        self.assertIn("exatamente o token primaria", a[0]["sugestao"])
        self.assertIn("rgba(var(--da-cor-fundo-rgb), 0.86)", a[1]["sugestao"])       # a forma única de alfa (D6)
        self.assertNotIn("/ 0.86", a[1]["sugestao"])
        self.assertIn("token mais próximo: primaria", a[2]["sugestao"])
        self.assertIn("cor fora da DA", a[3]["sugestao"])
        f = self.achados("f.css", ".a{font-family: \"IBM Plex Mono\", monospace}\n")
        self.assertIn("var(--da-fonte-subtitulo)", f[0]["sugestao"])
        j = self.achados("j.json", "{\"cor\": \"#FFFFFF\"}\n")
        self.assertIn("\"neutro-2\"", j[0]["sugestao"])

    def test_cli_pastas_ignoradas_e_json(self):
        (self.cena / "ruim.css").write_text(".a{color:#ff0000}\n", encoding="utf-8")
        (self.cena / "boa.css").write_text(".a{color:var(--da-cor-texto)}\n", encoding="utf-8")
        for ignorada in ("node_modules/lib", "build", ".oculta"):
            p = self.raiz / "animacoes" / ignorada
            p.mkdir(parents=True)
            (p / "x.css").write_text(".a{color:#ff0000}\n", encoding="utf-8")
        (self.cena / "lib.min.js").write_text("var a='#ff0000'\n", encoding="utf-8")
        (self.cena / "render.mp4.da.json").write_text("{\"cor\": \"#ff0000\"}\n", encoding="utf-8")
        os.chdir(self.raiz)
        rc, out, _ = self.cli("lint")                                           # padrão: pastas de peças do projeto
        self.assertEqual(rc, 1)
        self.assertEqual(out.count("[cor-hex]"), 1)
        self.assertIn("animacoes/cena 01/ruim.css:1:10: [cor-hex] #ff0000", out)
        self.assertIn("2 arquivo(s) conferido(s): 1 violação(ões)", out)
        rc, out, _ = self.cli("lint", "animacoes/cena 01/boa.css")
        self.assertEqual(rc, 0)
        rc, out, _ = self.cli("lint", "animacoes", "--json")
        r = json.loads(out)
        self.assertEqual((rc, r["ok"], r["erros"], r["achados"][0]["regra"]), (1, False, 1, "cor-hex"))
        rc, out, _ = self.cli("lint", "da")                                     # a própria DA nunca é varrida
        self.assertEqual(rc, 0)
        rc, _, err = self.cli("lint", "nao_existe")
        self.assertEqual(rc, 1)

    def test_funciona_sem_da(self):
        fora = self.tmp / "sem da"
        fora.mkdir()
        (fora / "x.css").write_text(".a{color:#ff0000;font-family:Arial}\n", encoding="utf-8")
        r = da.lint([fora], de=fora)
        self.assertEqual(r["erros"], 2)
        self.assertContem(r["notas"], "nenhuma DA encontrada")


# ══════════════════════════════════════════════════════════════════ carimbo ══
class TesteCarimbo(Base):
    def setUp(self):
        super().setUp()
        self.raiz = self.projeto()
        self.peca = self.raiz / "render" / "cena 1.mp4"
        self.peca.write_bytes(b"video de mentira")

    def estados(self, *caminhos) -> dict[str, str]:
        r = da.conferir_carimbo(list(caminhos) or None, da=self.raiz)
        return {Path(p["arquivo"]).name: p["estado"] for p in r["pecas"]}

    def test_carimbo_ok_e_conteudo(self):
        d = da.carregar(self.raiz)
        arq = da.carimbar(self.peca, ferramenta="motor", formato="horizontal", parametros={"cena": 1}, auditoria="ok")
        self.assertEqual(arq, self.raiz / "render" / "cena 1.mp4.da.json")
        c = da.ler_json(arq)
        for chave in ("da_sha256", "da_revisao", "da_aprovada", "kit_versao", "ferramenta", "formato", "parametros",
                      "auditoria", "gerado_em"):
            self.assertIn(chave, c)
        self.assertEqual((c["da_sha256"], c["da_revisao"], c["da_aprovada"], c["kit_versao"]), (d.sha256, 1, False, da.KIT_VERSAO))
        self.assertEqual((c["ferramenta"], c["formato"], c["parametros"], c["auditoria"]), ("motor", "horizontal", {"cena": 1}, "ok"))
        self.assertRegex(c["gerado_em"], r"^\d{4}-\d{2}-\d{2}T")
        r = da.conferir_carimbo([self.peca], da=self.raiz)
        self.assertTrue(r["ok"])
        self.assertEqual(self.estados(self.peca), {"cena 1.mp4": "ok"})
        self.assertEqual(self.estados(arq), {"cena 1.mp4": "ok"})               # aceitou o próprio sidecar
        self.assertEqual(d.carimbar(self.peca, "motor", "horizontal", None, "n/a"), arq)   # atalho no objeto

    def test_reprovacoes(self):
        self.assertEqual(self.estados(), {"cena 1.mp4": "sem_carimbo"})         # ausente
        da.carimbar(self.peca, "motor", "horizontal", {}, "pulada")
        self.assertEqual(self.estados(), {"cena 1.mp4": "auditoria_pulada"})
        # carimbar NUNCA promove a peça que pulou o auditor: o mesmo arquivo continua "pulada" (por API e por CLI)
        for pedido in ("ok", "n/a"):
            with self.assertRaises(da.DAErro) as c:
                da.carimbar(self.peca, "motor", "horizontal", {}, pedido)
            self.assertIn("--sem-auditoria", str(c.exception))
        rc, _, err = self.cli("carimbar", self.peca, "--ferramenta", "motor", "--auditoria", "ok", "--da", self.raiz)
        self.assertEqual(rc, 1)
        self.assertIn("continua \"pulada\"", err)
        self.assertEqual(da.ler_json(da.caminho_do_carimbo(self.peca))["auditoria"], "pulada")
        self.assertEqual(self.estados(), {"cena 1.mp4": "auditoria_pulada"})
        # só um render novo limpa: arquivo regenerado (outro conteúdo) ou o motor declarando que acabou de auditar
        da.carimbar(self.peca, "motor", "horizontal", {}, "ok", reauditada=True)       # PNG re-renderizado pode sair idêntico
        self.assertEqual(self.estados(), {"cena 1.mp4": "ok"})
        da.carimbar(self.peca, "motor", "horizontal", {}, "pulada")                    # rebaixar sempre pode
        self.peca.write_bytes(b"video de mentira, renderizado de novo")
        da.carimbar(self.peca, "motor", "horizontal", {}, "ok")
        self.assertEqual(self.estados(), {"cena 1.mp4": "ok"})
        self.peca.write_bytes(b"regravado por fora do kit")
        self.assertEqual(self.estados(), {"cena 1.mp4": "arquivo_alterado"})
        da.carimbar(self.peca, "motor", "horizontal", {}, "ok")
        da.caminho_do_carimbo(self.peca).write_text("{ quebrado", encoding="utf-8")
        self.assertEqual(self.estados(), {"cena 1.mp4": "carimbo_invalido"})
        da.carimbar(self.peca, "motor", "horizontal", {}, "ok")
        self.editar(self.raiz / "da/da.json", lambda x: x["cor"]["paleta"].__setitem__("primaria", "#00C2FF"))
        r = da.conferir_carimbo(None, da=self.raiz)                             # DA mudou ⇒ sha velho
        self.assertFalse(r["ok"])
        self.assertEqual(r["pecas"][0]["estado"], "sha_diferente")
        self.assertIn("renderize de novo", r["pecas"][0]["detalhe"])
        da.carimbar(self.peca, "motor", "horizontal", {}, "ok")
        self.assertEqual(self.estados(), {"cena 1.mp4": "ok"})

    def test_aprovar_nao_envelhece_o_carimbo(self):
        da.carimbar(self.peca, "motor", "horizontal", {}, "ok")
        da.aprovar(self.raiz)
        r = da.conferir_carimbo(None, da=self.raiz)
        self.assertTrue(r["ok"])
        self.assertIn("antes da aprovação", r["pecas"][0]["detalhe"])

    def test_pastas_sequencias_e_varredura(self):
        seq = self.raiz / "animacoes" / "seq 01"
        seq.mkdir(parents=True)
        for i in range(3):
            (seq / f"{i:04d}.png").write_bytes(b"png")
        (self.raiz / "thumbs" / "capa.jpg").write_bytes(b"jpg")
        (self.raiz / "render" / "notas.txt").write_text("não é peça")
        (self.raiz / "bruto" / "gravacao.mp4").write_bytes("bruto não entra na varredura padrão".encode("utf-8"))
        self.assertEqual(self.estados(), {"0000.png": "sem_carimbo", "0001.png": "sem_carimbo", "0002.png": "sem_carimbo",
                                          "capa.jpg": "sem_carimbo", "cena 1.mp4": "sem_carimbo"})
        da.carimbar(seq, "motor", "vertical", {"quadros": 3}, "ok")              # pasta carimbada = uma peça
        da.carimbar(self.peca, "motor", "horizontal", {}, "ok")
        da.carimbar(self.raiz / "thumbs" / "capa.jpg", "thumbnail", "thumbnail", {}, "n/a")
        self.assertEqual(self.estados(), {"seq 01": "ok", "capa.jpg": "ok", "cena 1.mp4": "ok"})
        (seq / "0003.png").write_bytes(b"quadro novo")
        self.assertEqual(self.estados(seq), {"seq 01": "arquivo_alterado"})

    def test_erros_e_cli(self):
        with self.assertRaises(da.DAErro):
            da.carimbar(self.raiz / "render" / "nao existe.mp4", "motor")
        with self.assertRaises(da.DAErro):
            da.carimbar(self.peca, "motor", auditoria="talvez")
        with self.assertRaises(da.DAErro):
            da.carimbar(self.peca, "")
        with self.assertRaises(da.DAErro):
            da.carimbar(self.peca, "motor", parametros={"x": object()})
        os.chdir(self.raiz / "render")
        rc, out, _ = self.cli("conferir-carimbo")
        self.assertEqual(rc, 1)
        self.assertIn("SEM CARIMBO", out)
        rc, out, _ = self.cli("carimbar", "cena 1.mp4", "--ferramenta", "motor", "--formato", "horizontal",
                              "--parametros", "{\"cena\": 1}", "--auditoria", "ok")
        self.assertEqual(rc, 0)
        rc, out, _ = self.cli("conferir-carimbo")
        self.assertEqual(rc, 0)
        self.assertIn("1 peça(s): 1 em dia", out)
        self.assertEqual(self.cli("carimbar", "cena 1.mp4", "--ferramenta", "m", "--parametros", "{cena:1}")[0], 1)
        self.assertEqual(self.cli("carimbar", "cena 1.mp4", "--ferramenta", "m", "--auditoria", "talvez")[0], da.SAIDA_USO)
        rc, out, _ = self.cli("conferir-carimbo", "--json")
        self.assertTrue(json.loads(out)["ok"])

    def test_peca_fora_do_projeto_usa_a_da_do_diretorio_atual(self):
        fora = self.tmp / "exportados"
        fora.mkdir()
        (fora / "x.png").write_bytes(b"x")
        os.chdir(self.raiz)
        c = da.ler_json(da.carimbar(fora / "x.png", "thumbnail"))
        self.assertEqual(c["da_sha256"], da.carregar(self.raiz).sha256)


# ══════════════════════════════════════════════════════════════════ presets ══
class TestePresets(Base):
    def test_salvar_listar_e_reusar(self):
        raiz = self.projeto(nome="Canal do Zé", base="lab-ia")
        (raiz / "da/logos/logo.png").write_bytes(b"png de mentira")
        (raiz / "da/texturas/papel.png").write_bytes(b"textura")
        (raiz / "da/referencias/ref.jpg").write_bytes(b"ref")

        def personalizar(x):
            x["cor"]["paleta"]["primaria"] = "#00FFA3"
            x["marca"].update(logo="logos/logo.png", assinatura="@canaldoze")
            x["conceito"]["referencias"] = [{"arquivo": "referencias/ref.jpg", "nota": "clima"}]
            x["x_textura"] = "texturas/papel.png"                                 # campo de extensão que aponta arquivo

        self.editar(raiz / "da/da.json", personalizar)
        da.aprovar(raiz)
        with self.assertRaises(da.DAErro):
            da.salvar_preset("dossie", raiz)                                      # nome de embutido é reservado
        with self.assertRaises(da.DAErro):
            da.salvar_preset("Meu Canal", raiz)
        r = da.salvar_preset("meu-canal", raiz)
        pasta = Path(os.environ["VIDEO_OPS_HOME"]) / "da-presets" / "meu-canal"
        self.assertEqual(r["pasta"], pasta)
        for p in ("da.json", "fontes/Roboto-Variable.ttf", "fontes/FiraCode-Variable.ttf", "logos/logo.png", "texturas/papel.png"):
            self.assertTrue((pasta / p).is_file(), p)
        self.assertFalse((pasta / "referencias").exists())                        # referências ficam no projeto
        salvo = da.ler_json(pasta / "da.json")
        self.assertEqual((salvo["herda"], salvo["projeto"]["aprovada"], salvo["projeto"]["revisao"]), (None, False, 1))
        self.assertEqual(salvo["conceito"]["referencias"], [])
        self.assertEqual(da.validar(pasta / "da.json")["erros"], [])
        with self.assertRaises(da.DAErro):
            da.salvar_preset("meu-canal", raiz)                                   # já existe
        da.salvar_preset("meu-canal", raiz, forcar=True)
        lista = {p["nome"]: p for p in da.listar_presets()}
        self.assertEqual(lista["meu-canal"]["origem"], "pessoal")
        self.assertEqual(lista["dossie"]["origem"], "embutido")
        self.assertIn("Laboratório de IA", lista["meu-canal"]["frase"])
        rc, out, _ = self.cli("presets")
        self.assertIn("meu-canal", out)
        self.assertIn("Presets pessoais", out)
        # outro projeto nasce do preset pessoal, com os arquivos copiados
        novo = self.projeto(nome="Episódio 2", base="meu-canal", pasta="episódio 2")
        d = da.carregar(novo)
        self.assertEqual((d.cor("primaria"), d["marca"]["assinatura"]), ("#00FFA3", "@canaldoze"))
        self.assertTrue((novo / "da/logos/logo.png").is_file())
        self.assertTrue((novo / "da/texturas/papel.png").is_file())
        self.assertEqual(Path(d["marca"]["logo_abs"]), novo / "da/logos/logo.png")
        # e também pode ser herdado pelo nome
        filho = self.projeto(nome="Episódio 3", base="meu-canal", pasta="episódio 3", herdar=True)
        self.assertEqual(da.carregar(filho).cor("primaria"), "#00FFA3")

    def test_cli_salvar_preset(self):
        raiz = self.projeto()
        os.chdir(raiz)
        rc, out, _ = self.cli("salvar-preset", "casa-nova")
        self.assertEqual(rc, 0)
        self.assertTrue((Path(os.environ["VIDEO_OPS_HOME"]) / "da-presets/casa-nova/da.json").is_file())
        rc, _, err = self.cli("salvar-preset", "casa-nova")
        self.assertEqual(rc, 1)
        self.assertIn("--forcar", err)
        self.assertEqual(self.cli("presets", "--json")[0], 0)


# ══════════════════════════════════════════════════════════════════ extrair ══
class TesteExtrair(Base):
    def setUp(self):
        super().setUp()
        try:
            import numpy  # noqa: F401
            from PIL import Image  # noqa: F401
        except ImportError:
            self.skipTest("numpy/Pillow ausentes")

    def imagem(self, nome: str, blocos: list[tuple[str, float]], tam=(400, 240)) -> Path:
        from PIL import Image, ImageDraw
        img = Image.new("RGB", tam, blocos[0][0])
        d, x = ImageDraw.Draw(img), 0
        for cor, fracao in blocos:
            larg = int(round(tam[0] * fracao))
            d.rectangle([x, 0, x + larg, tam[1]], fill=cor)
            x += larg
        arq = self.tmp / nome
        img.save(arq)
        return arq

    def test_paleta_estatisticas_candidatos_e_arquivos(self):
        a = self.imagem("ref escura.png", [("#101216", 0.6), ("#E8E4DA", 0.25), ("#FFC400", 0.15)])
        b = self.imagem("ref 2.jpg", [("#101216", 0.7), ("#2E86DE", 0.3)])
        saida = self.tmp / "saída análise"
        r = da.extrair([a, b], saida=saida, cores=8)
        self.assertTrue((saida / "referencias_analise.json").is_file())
        self.assertTrue((saida / "referencias_folha.png").is_file())
        self.assertLess((saida / "referencias_folha.png").stat().st_size, 5_000_000)
        g = r["geral"]
        self.assertTrue(6 <= len(g["paleta"]) <= 8)
        self.assertAlmostEqual(sum(c["area"] for c in g["paleta"]), 1.0, places=2)
        self.assertEqual(g["paleta"], sorted(g["paleta"], key=lambda c: -c["area"]))     # ordenada por área
        self.assertLess(da.delta_e(g["paleta"][0]["hex"], "#101216"), 6)                 # dominante = o fundo escuro
        self.assertGreater(g["paleta"][0]["area"], 0.5)
        hexes = [c["hex"] for c in g["paleta"]]
        for esperado in ("#E8E4DA", "#FFC400", "#2E86DE"):
            self.assertLess(min(da.delta_e(h, esperado) for h in hexes), 12, esperado)
        self.assertLess(g["luminancia_media"], 40)
        self.assertGreater(g["contraste_p5_p95"], 50)
        self.assertIn(g["temperatura"]["rotulo"], ("quente", "fria", "neutra"))
        self.assertIn("saturacao_p90", g)
        cand = g["candidatos"]
        self.assertLess(da.delta_e(cand["fundo"]["hex"], "#101216"), 6)
        self.assertGreaterEqual(da.contraste(cand["texto"]["hex"], cand["fundo"]["hex"]), 7)
        self.assertLess(min(da.delta_e(cand["primaria"]["hex"], x) for x in ("#FFC400", "#2E86DE")), 12)
        self.assertEqual(len(r["referencias"]), 2)
        self.assertEqual(r["referencias"][0]["grao"]["rotulo"], "limpo")                 # blocos chapados não têm grão
        salvo = da.ler_json(saida / "referencias_analise.json")
        self.assertEqual(salvo["geral"]["paleta"], g["paleta"])
        r2 = da.extrair([a, b], saida=saida, cores=8)                                    # semente fixa ⇒ reprodutível
        self.assertEqual(r2["geral"]["paleta"], g["paleta"])

    def test_grao_e_detectado(self):
        import numpy as np
        from PIL import Image
        rng = np.random.default_rng(3)
        base = np.full((300, 300, 3), 120, dtype=np.float64)
        ruidosa = np.clip(base + rng.normal(0, 6, base.shape), 0, 255).astype(np.uint8)
        arq = self.tmp / "granulada.png"
        Image.fromarray(ruidosa).save(arq)
        g = da.extrair([arq], saida=self.tmp / "g")["referencias"][0]["grao"]
        self.assertIn(g["rotulo"], ("médio", "forte"))
        self.assertGreater(g["sigma"], 3)
        self.assertGreaterEqual(g["intensidade_sugerida"], 10)

    def test_destino_padrao_e_erros(self):
        raiz = self.projeto()
        a = self.imagem("r.png", [("#202020", 0.5), ("#F0F0F0", 0.5)])
        os.chdir(raiz / "pesquisa")
        rc, out, _ = self.cli("extrair", a)
        self.assertEqual(rc, 0)
        self.assertTrue((raiz / "da/referencias/referencias_analise.json").is_file())    # dentro do projeto: da/referencias/
        self.assertIn("Paleta dominante", out)
        self.assertEqual(da.lint([raiz / "da"], da=raiz)["achados"], [])                 # a análise não é varrida pelo lint
        with self.assertRaises(da.DAErro):
            da.extrair([self.tmp / "nao existe.png"])
        (self.tmp / "doc.txt").write_text("x")
        with self.assertRaises(da.DAErro):
            da.extrair([self.tmp / "doc.txt"])


# ═══════════════════════════════════════════════════════ ffmpeg (via trava) ══
@unittest.skipUnless(FFMPEG, "ffmpeg não encontrado")
class TesteGradeFFmpeg(Base):
    def test_filtros_de_todos_os_presets_existem_neste_ffmpeg(self):
        tem = da.filtros_do_ffmpeg()
        self.assertIn("eq", tem)
        for nome in PRESETS:
            d = da.carregar(da.achar_preset(nome))
            for fmt in ("horizontal", "vertical", "thumbnail"):
                faltam = [f for f in da.filtros_da_cadeia(d.grade(fmt)) if f not in tem]
                self.assertEqual(faltam, [], f"{nome}/{fmt}")
        for item in da.MAPEAMENTO_GRADE:                                          # tudo o que o mapeamento cita existe
            for filtro in item["filtro"].replace("(+", " ").replace(")", " ").replace("+", " ").replace("/", " ").split():
                self.assertIn(filtro, tem, filtro)

    def test_aplica_grade_completa_em_clipe_minusculo(self):
        """0,5 s de testsrc2 em 320x180: cadeia com TODOS os recursos (LUT parcial num caminho com
        apóstrofo e vírgula, duotone parcial, temperatura, curva, exposição, desfoque, nitidez, vinheta, grão)."""
        raiz = self.projeto(pasta="projeto d'água, ffmpeg")
        clipe = raiz / "bruto" / "clipe sintético.mp4"
        rc = trava.executar([FFMPEG, "-hide_banner", "-v", "error", "-nostdin", "-y", "-f", "lavfi", "-i",
                             "testsrc2=size=320x180:rate=30:duration=0.5", "-c:v", "libx264", "-preset", "ultrafast",
                             "-pix_fmt", "yuv420p", str(clipe)], rotulo="teste: clipe sintético")
        self.assertEqual(rc, 0)
        (raiz / "da/luts/teste d'água, v1.cube").write_text("LUT_3D_SIZE 2\n0 0 0\n1 0 0\n0 1 0\n1 1 0\n0 0 0.5\n1 0 0.5\n0 1 0.5\n1 1 0.5\n")

        def tudo(x):
            t = x["tratamento"]
            t["grade"].update(lut="luts/teste d'água, v1.cube", intensidade_lut=0.5, exposicao=0.3, gama=1.05,
                              temperatura=25, matiz=-8, curva={"mestre": [[0, 0], [0.5, 0.55], [1, 1]], "b": [[0, 0.02], [1, 0.96]]})
            t["duotone"].update(ativo=True, mistura=0.3)
            t.update(nitidez=0.4, desfoque=0.003)

        self.editar(raiz / "da/da.json", tudo)
        saida = raiz / "broll" / "clipe tratado.mp4"
        r = da.aplicar_grade(clipe, saida, da=da.carregar(raiz))
        self.assertTrue(saida.is_file())
        self.assertFalse(list(saida.parent.glob("*.parcial*")))
        info = da.sondar(saida)
        self.assertEqual((info["largura"], info["altura"]), (320, 180))
        self.assertAlmostEqual(info["duracao"], 0.5, delta=0.1)
        c = da.ler_json(r["carimbo"])
        self.assertEqual((c["ferramenta"], c["formato"], c["auditoria"]), ("da.py grade", "320x180", "n/a"))
        self.assertEqual(c["parametros"]["cadeia"], r["cadeia"])
        self.assertTrue(da.conferir_carimbo([saida], da=raiz)["ok"])
        # imagem parada pelo mesmo caminho + amostragem de vídeo do `extrair`
        quadro = raiz / "thumbs" / "quadro tratado.png"
        da.aplicar_grade(clipe, quadro, da=da.carregar(raiz), parte="cor", inicio=0.2)
        self.assertTrue(quadro.is_file())
        rc, out, err = self.cli("grade", "--de", raiz, "--entrada", clipe, "--saida", raiz / "broll" / "pela cli.mp4", "--duracao", "0.2")
        self.assertEqual(rc, 0, err)
        self.assertEqual(self.cli("grade", "--de", raiz, "--verificar")[0], 0)
        try:
            a = da.extrair([clipe], saida=raiz / "da" / "referencias", quadros=2)
        except da.DAErro as e:
            if "numpy" in str(e):
                self.skipTest("numpy/Pillow ausentes")
            raise
        self.assertEqual((a["referencias"][0]["tipo"], a["referencias"][0]["quadros"]), ("video", 2))
        # falha do ffmpeg vira erro claro e não deixa .parcial para trás
        with self.assertRaises(da.DAErro):
            da.aplicar_grade(raiz / "da" / "da.json", raiz / "broll" / "x.mp4", da=da.carregar(raiz))
        with self.assertRaises(da.DAErro):
            da.aplicar_grade(clipe, clipe, da=da.carregar(raiz))
        self.assertFalse(list((raiz / "broll").glob("*.parcial*")))


# ══════════════════════════════════════════════════════ utilidades/extensão ══
class TesteUtilidades(Base):
    def test_cor_e_contraste(self):
        self.assertEqual(da.hex_normal("#fc0"), "#FFCC00")
        self.assertEqual(da.hex_normal(" #a1b2c3 "), "#A1B2C3")
        for ruim in ("fc0", "#12345", "#GGGGGG", None, 12):
            with self.assertRaises(da.DAErro):
                da.hex_normal(ruim)
        self.assertEqual(da.hex_para_rgb("#FFC700"), (255, 199, 0))
        self.assertEqual(da.rgb_para_hex(255, 199.4, -3), "#FFC700")
        self.assertAlmostEqual(da.contraste("#000000", "#FFFFFF"), 21.0, places=3)
        self.assertAlmostEqual(da.contraste("#FFFFFF", "#000000"), 21.0, places=3)
        self.assertAlmostEqual(da.contraste("#777777", "#FFFFFF"), 4.48, places=2)
        self.assertEqual(da.delta_e("#123456", "#123456"), 0)
        self.assertGreater(da.delta_e("#FF0000", "#00FF00"), 80)
        self.assertEqual(da.css_var_do_token("texto_suave"), "--da-cor-texto-suave")
        self.assertEqual(da.css_var_do_token("dado-3"), "--da-dado-3")

    def test_numeros_json_fps_e_slug(self):
        self.assertEqual([da._num(x, c) for x, c in ((30, 0), (30.0, 0), (100.0, 0), (0.5, 4), (1.0, 4), (0.12345678, 4), (-0.0, 2), (1e-9, 4), (12000, 4))],
                         ["30", "30", "100", "0.5", "1", "0.1235", "0", "0", "12000"])
        self.assertEqual(da._ptbr(4.5, 1), "4,5")
        dados = {"a": [0, 0, 1, 1], "b": {"x": 1, "y": None}, "c": [["primaria", 0], ["fundo", 1]], "d": "ç é", "e": [], "f": {},
                 "g": [{"k": [1, 2]}, "texto longo " * 12]}
        bonito = da.json_bonito(dados)
        self.assertEqual(json.loads(bonito), dados)
        self.assertIn("\"a\": [0, 0, 1, 1]", bonito)                              # listas curtas numa linha
        self.assertIn("\"c\": [[\"primaria\", 0], [\"fundo\", 1]]", bonito)
        self.assertIn("ç é", bonito)
        self.assertEqual(da.fps_racional("30000/1001"), Fraction(30000, 1001))
        self.assertEqual(da.fps_racional("25"), 25)
        self.assertEqual(da.fps_racional(29.97), Fraction(30000, 1001))
        for ruim in ("abc", "0", "30/0", "1000", "", None, True):
            with self.assertRaises(da.DAErro):
                da.fps_racional(ruim)
        self.assertEqual(da.slugificar("Vídeo de teste — núcleo #1"), "video-de-teste-nucleo-1")
        self.assertEqual(da.slugificar("———"), "projeto")
        self.assertEqual(da.fundir({"a": {"b": 1, "c": [1, 2]}, "d": 1}, {"a": {"c": [3], "e": None}}),
                         {"a": {"b": 1, "c": [3], "e": None}, "d": 1})

    def test_fontes_do_kit(self):
        self.assertEqual(da.info_fonte(KIT / "fontes/Roboto-Variable.ttf")["eixos"], {"wght": (100.0, 400.0, 900.0), "wdth": (75.0, 100.0, 100.0)})
        self.assertFalse(da.info_fonte(KIT / "fontes/BebasNeue-Regular.ttf")["variavel"])
        with self.assertRaises(da.DAErro):
            da.info_fonte(KIT / "VERSAO")

    def test_escrita_atomica_e_json_invalido(self):
        arq = self.tmp / "pasta nova" / "x.json"
        da.gravar_json(arq, {"a": 1})
        self.assertEqual(da.ler_json(arq), {"a": 1})
        self.assertEqual([p.name for p in arq.parent.iterdir()], ["x.json"])      # nenhum .parcial sobrando
        arq.write_text("{\n  \"a\": 1,\n}", encoding="utf-8")
        with self.assertRaises(da.DAErro) as c:
            da.ler_json(arq)
        self.assertRegex(str(c.exception), r"JSON inválido na linha [23]")      # a linha varia com a versão do Python
        with self.assertRaises(da.DAErro):
            da.ler_json(self.tmp / "nao existe.json")

    def test_kit_nao_embute_caminho_de_montagem(self):
        proibidos = ("/private/tmp/", "scratchpad", "/Downloads/video 2")
        for arq in [KIT / "da.py", KIT / "trava.py", KIT / "da_esquema.json", KIT / "modelos/CLAUDE.projeto.md",
                    KIT / "LEIAME.md", *sorted((KIT / "presets").glob("*.json"))]:
            texto = arq.read_text(encoding="utf-8")
            for p in proibidos:
                self.assertNotIn(p, texto, f"{arq.name} cita {p}")
        self.assertEqual((KIT / "VERSAO").read_text().strip(), da.KIT_VERSAO)
        self.assertRegex(da.KIT_VERSAO, r"^\d+\.\d+\.\d+$")

    def test_defeito_interno_sai_em_uma_linha_e_da_debug_mostra_o_traceback(self):
        def quebrar(args):
            raise ZeroDivisionError("conta impossível")

        da.registrar_subcomando("quebra-teste", "subcomando que quebra", None, quebrar)
        try:
            os.environ.pop("DA_DEBUG", None)
            rc, _, err = self.cli("quebra-teste")
            self.assertEqual(rc, da.SAIDA_ERRO)
            self.assertIn("erro interno: ZeroDivisionError: conta impossível", err)
            self.assertIn("DA_DEBUG=1", err)
            self.assertNotIn("Traceback", err)
            os.environ["DA_DEBUG"] = "1"
            with self.assertRaises(ZeroDivisionError):
                self.cli("quebra-teste")
        finally:
            os.environ.pop("DA_DEBUG", None)
            da._SUBCOMANDOS.pop("quebra-teste", None)

    def test_caminho_fora_da_base_sai_absoluto_e_dica_do_da_inexistente(self):
        fora = Path(tempfile.mkdtemp(prefix="da fora é ")).resolve()
        try:
            self.assertEqual(da._rel(fora / "peça.png", self.tmp / "a" / "b"), str(fora / "peça.png"))   # nada de ../../../
            self.assertEqual(da._rel(self.tmp / "a" / "x.png", self.tmp), os.path.join("a", "x.png"))
        finally:
            shutil.rmtree(fora, ignore_errors=True)
        with self.assertRaises(da.SemDA) as c:
            da.achar(da=self.tmp / "nada")
        self.assertIn(f'init "{self.tmp / "nada"}"', str(c.exception))      # sugere criar NA pasta apontada, não na mãe
        with self.assertRaises(da.SemDA) as c:
            da.achar(da=self.tmp / "proj" / "da" / "da.json")
        self.assertIn(f'init "{self.tmp / "proj"}"', str(c.exception))

    def test_ponto_de_extensao_de_subcomandos(self):
        chamadas = []

        def configurar(p):
            p.add_argument("--formato", default="horizontal")

        def executar(args):
            d = da.carregar(getattr(args, "da", None), de=getattr(args, "de", None))
            chamadas.append((args.formato, d.cor("primaria")))
            print("prancha de", d.meta["nome"])
            return 0

        da.registrar_subcomando("prancha-teste", "subcomando de teste", configurar, executar)
        try:
            raiz = self.projeto()
            rc, out, _ = self.cli("prancha-teste", "--formato", "vertical", "--de", raiz)
            self.assertEqual((rc, out.strip()), (0, "prancha de Projeto de teste"))
            self.assertEqual(chamadas, [("vertical", "#FFC700")])
            self.assertIn("prancha-teste", da.montar_parser().format_help())
            rc, _, err = self.cli("prancha-teste", "--de", self.tmp)               # extensão também respeita "sem DA = 2"
            self.assertEqual(rc, 2)
        finally:
            da._SUBCOMANDOS.pop("prancha-teste", None)
        with self.assertRaises(da.DAErro):
            da.registrar_subcomando("x", "sem executar")


if __name__ == "__main__":
    unittest.main(verbosity=2)
