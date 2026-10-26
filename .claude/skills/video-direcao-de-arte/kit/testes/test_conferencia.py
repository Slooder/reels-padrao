#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Regressões da conferência final (camada C5 como comando do kit): `da conferencia` / da_ext_conferencia.conferir.

Rodar a partir do kit:  python3 -m unittest testes.test_conferencia -v
Cada caso monta um projeto mínimo numa pasta temporária com espaço e acento (VIDEO_OPS_HOME isolado). Os três clipes
de matéria-prima têm 2 s, no máximo 320×180, e são gerados uma vez; as medições de loudness passam pela trava global de
verdade. Nada aqui abre browser.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent
if str(KIT) not in sys.path:
    sys.path.insert(0, str(KIT))
import da  # noqa: E402
import da_ext_conferencia as conferencia  # noqa: E402
import video  # noqa: E402

BIN_DA = KIT / "bin" / "da"
CAMPOS_RELATORIO = ["versao", "ok", "verificado_em", "da_sha256", "alvos", "resumo", "itens"]
CAMPOS_ALVO = ["arquivo", "sha256", "bytes"]
CAMPOS_ITEM = ["id", "categoria", "alvo", "severidade", "mensagem", "como_corrigir"]
CATEGORIAS = {"da", "carimbo", "lint", "tecnico", "loudness", "zona_segura", "fatos", "licencas", "texto"}
SEVERIDADES = {"erro", "aviso", "info"}
LUFS_DO_SENO = -21.8      # loudness integrado do `sine` do ffmpeg (amplitude 1/8) depois de virar estéreo AAC: medido com ebur128
CENA_LIMPA = ("export const meta = { nome: 'ok', dur_padrao: 1 };\n"
              "export function build(palco, p, ctx) { palco.style.background = ctx.cor('fundo'); }\n"
              "export function seek(t) {}\n")
CENA_COM_COR_LITERAL = ("export const meta = { nome: 'ruim', dur_padrao: 1 };\n"
                        "export function build(palco, p, ctx) {\n"
                        "  palco.style.background = '#FF0000';\n"
                        "}\n"
                        "export function seek(t) {}\n")
FATOS_FALSO = r'''import json, sys
sub = sys.argv[1]
if "--projeto" not in sys.argv or "--json" not in sys.argv:
    sys.exit(64)
if sub == "validar":
    print(json.dumps({"ok": False, "fatos": 2, "erros": [{"id": "F001", "campo": "fontes", "mensagem": "confirmado sem fonte primária"}],
                      "avisos": [{"id": "F002", "campo": "caduca_em", "mensagem": "fato vencido"}]}))
    sys.exit(1)
if sub == "conferir-roteiro":
    print(json.dumps({"ok": True, "pendencias": [], "avisos": []}))
    sys.exit(0)
if sub == "conferir-storyboard":
    print(json.dumps({"ok": False, "pendencias": [{"tipo": "numero_nao_bate", "cena": "C02", "detalhe": "C02: 40 % na tela, 4 % no fato"}],
                      "avisos": [{"tipo": "sem_credito", "cena": "C03", "detalhe": "C03: cena com fato e sem crédito"}]}))
    sys.exit(1)
sys.exit(64)
'''


def editar(da_json: Path, fn) -> None:
    dados = json.loads(da_json.read_text(encoding="utf-8"))
    fn(dados)
    da_json.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")


def erros(rel: dict) -> list[dict]:
    return [i for i in rel["itens"] if i["severidade"] == "erro"]


def ids(rel: dict, severidade: str | None = None) -> list[str]:
    return [i["id"] for i in rel["itens"] if severidade is None or i["severidade"] == severidade]


def item(rel: dict, prefixo: str) -> dict | None:
    return next((i for i in rel["itens"] if i["id"] == prefixo or i["id"].startswith(prefixo + ".")), None)


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = Path(tempfile.mkdtemp(prefix="da conferência é ")).resolve()
        cls._env = {k: os.environ.get(k) for k in ("VIDEO_OPS_HOME", "DA_JSON")}
        os.environ["VIDEO_OPS_HOME"] = str(cls.base / "video ops home")
        os.environ.pop("DA_JSON", None)
        cls._cwd = os.getcwd()
        cls._clipes: dict[str, Path] = {}
        cls._n = 0

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
    def clipe(cls, nome: str) -> Path:
        """Matéria-prima (gerada uma vez): 'longo' 320×180 e 'corte' 180×320 no alvo de loudness da DA; 'baixo' = corte 10 dB abaixo."""
        if nome not in cls._clipes:
            molde = cls.base / "molde da matéria prima"
            if not (molde / "da" / "da.json").is_file():
                da.iniciar(molde, nome="Molde", base="dossie")
            d = da.carregar(molde)
            tamanho, formato, tipo, folga = {"longo": ("320x180", "horizontal", "longo", 0), "corte": ("180x320", "vertical", "curto", 0),
                                             "baixo": ("180x320", "vertical", "curto", -10)}[nome]
            ganho = d["som"]["loudness"][tipo]["lufs"] - LUFS_DO_SENO + folga
            destino = molde / "bruto" / f"{nome}.mp4"
            video.executar(["-f", "lavfi", "-i", f"testsrc2=size={tamanho}:rate=30000/1001:duration=2",
                            "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=2", "-af", f"volume={ganho:.2f}dB",
                            *video.args_encode(d, formato=formato, crf=34, preset="ultrafast"), "-shortest"], destino,
                           rotulo="teste: matéria-prima da conferência")
            cls._clipes[nome] = destino
        return cls._clipes[nome]

    @classmethod
    def projeto(cls, aprovada: bool = True, final: bool = True, cortes=("K01",), preset: str = "dossie") -> Path:
        """Projeto mínimo: DA (aprovada ou não), uma cena limpa em animacoes/, render/final.mp4 e cortes/<nome>.mp4 carimbados."""
        cls._n += 1
        raiz = cls.base / f"projeto {cls._n:02d} conferência ção"
        da.iniciar(raiz, nome=f"Conferência {cls._n}", base=preset)
        if aprovada:
            da.aprovar(raiz)
        (raiz / "animacoes" / "cena limpa.js").write_text(CENA_LIMPA, encoding="utf-8")
        d = da.carregar(raiz)
        if final:
            shutil.copy2(cls.clipe("longo"), raiz / "render" / "final.mp4")
            d.carimbar(raiz / "render" / "final.mp4", "teste: mixagem", "320x180", {"origem": "sintético"})
        for nome in cortes:
            cls.por_corte(raiz, nome)
        return raiz

    @classmethod
    def por_corte(cls, raiz: Path, nome: str, clipe: str = "corte", plataforma: str | None = "shorts") -> Path:
        destino = raiz / "cortes" / f"{nome}.mp4"
        shutil.copy2(cls.clipe(clipe), destino)
        insumos = [raiz / "render" / "final.mp4"] if (raiz / "render" / "final.mp4").is_file() else None
        da.carregar(raiz).carimbar(destino, "teste: cortes", "180x320", {"plataforma": plataforma} if plataforma else {}, insumos=insumos)
        return destino

    def cli(self, raiz: Path, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
        return subprocess.run([str(BIN_DA), "conferencia", *args], cwd=str(cwd or raiz), capture_output=True, text=True, timeout=600)

    def assertSemErros(self, rel: dict) -> None:
        self.assertEqual(erros(rel), [], "a conferência não devia ter erros")
        self.assertTrue(rel["ok"])


# ═══════════════════════════════════════════════ caso ok e contrato do relatório ══
class TesteContrato(Base):
    def test_01_caso_ok_grava_o_relatorio_no_contrato_campo_a_campo(self):
        raiz = self.projeto()
        d = da.carregar(raiz)
        tratado = raiz / "broll" / "tratado" / "arquivo tratado.mp4"
        shutil.copy2(self.clipe("longo"), tratado)
        d.carimbar(tratado, "teste: broll", "320x180", {"origem": "sintético"})
        antes = {str(p.relative_to(raiz)): p.stat().st_mtime_ns for p in raiz.rglob("*") if p.is_file() and "qa" not in p.relative_to(raiz).parts}
        rel = conferencia.conferir(raiz)
        self.assertSemErros(rel)
        # nada foi renderizado nem regravado: a conferência só escreve em qa/
        depois = {str(p.relative_to(raiz)): p.stat().st_mtime_ns for p in raiz.rglob("*") if p.is_file() and "qa" not in p.relative_to(raiz).parts}
        self.assertEqual(antes, depois)
        arq_json, arq_md = raiz / "qa" / "relatorio.json", raiz / "qa" / "relatorio.md"
        self.assertEqual((Path(rel.json), Path(rel.md)), (arq_json, arq_md))
        gravado = json.loads(arq_json.read_text(encoding="utf-8"))
        self.assertEqual(gravado, dict(rel))
        # ── contrato, campo a campo ──
        self.assertEqual(list(gravado), CAMPOS_RELATORIO)
        self.assertIs(type(gravado["versao"]), int)
        self.assertEqual(gravado["versao"], 1)
        self.assertIs(gravado["ok"], True)
        quando = datetime.fromisoformat(gravado["verificado_em"])
        self.assertIsNotNone(quando.tzinfo, "verificado_em precisa de fuso (da.agora_iso())")
        self.assertLessEqual(quando.timestamp(), arq_json.stat().st_mtime + 1)              # não fica à frente do próprio arquivo…
        for alvo in ("render/final.mp4", "cortes/K01.mp4"):                                 # …e não é mais velho que o entregável (o portão de publicação compara)
            self.assertGreaterEqual(quando.timestamp() + 1, (raiz / alvo).stat().st_mtime)
        self.assertEqual(gravado["da_sha256"], d.sha256)
        self.assertEqual([a["arquivo"] for a in gravado["alvos"]], ["render/final.mp4", "cortes/K01.mp4"])     # relativos à raiz; broll/tratado é peça, não entregável
        for a in gravado["alvos"]:
            self.assertEqual(list(a), CAMPOS_ALVO)
            arq = raiz / a["arquivo"]
            self.assertEqual(a["sha256"], hashlib.sha256(arq.read_bytes()).hexdigest())
            self.assertEqual(a["bytes"], arq.stat().st_size)
        self.assertEqual(list(gravado["resumo"]), ["erros", "avisos"])
        self.assertEqual(gravado["resumo"]["erros"], 0)
        self.assertEqual(gravado["resumo"]["avisos"], len(ids(gravado, "aviso")))
        self.assertGreater(len(gravado["itens"]), 0)
        for i in gravado["itens"]:
            self.assertEqual(list(i), CAMPOS_ITEM)
            self.assertIn(i["categoria"], CATEGORIAS)
            self.assertIn(i["severidade"], SEVERIDADES)
            self.assertTrue(all(isinstance(i[c], str) for c in CAMPOS_ITEM))
            self.assertTrue(i["id"].startswith(i["categoria"] + "."))
            self.assertTrue(i["mensagem"] and "\n" not in i["mensagem"])
            if i["severidade"] != "info":
                self.assertTrue(i["como_corrigir"], f"{i['id']} não diz como corrigir")
        self.assertEqual(len(set(ids(gravado))), len(gravado["itens"]), "ids repetidos")
        # o que foi conferido aparece: lint leu a cena, os carimbos das 3 peças, loudness e técnica dos 2 entregáveis
        self.assertIn("1 arquivo(s) lido(s)", item(gravado, "lint.resumo")["mensagem"])
        self.assertIn("--exigir-aprovada: 3 peça(s), 3 em dia", item(gravado, "carimbo.resumo")["mensagem"])
        medidos = {i["alvo"]: i["mensagem"] for i in gravado["itens"] if i["id"].startswith("loudness.medido")}
        self.assertEqual(sorted(medidos), ["cortes/K01.mp4", "render/final.mp4"])
        self.assertIn("som.loudness.longo", medidos["render/final.mp4"])
        self.assertIn("som.loudness.curto", medidos["cortes/K01.mp4"])
        tecnicos = {i["alvo"]: i["mensagem"] for i in gravado["itens"] if i["id"].startswith("tecnico.medidas")}
        self.assertIn("conferido contra youtube", tecnicos["render/final.mp4"])
        self.assertTrue(tecnicos["cortes/K01.mp4"].endswith("conferido contra shorts"))     # a plataforma declarada no carimbo do corte
        md = arq_md.read_text(encoding="utf-8")
        self.assertIn("# Conferência final — Conferência", md)
        self.assertIn("**APROVADO**", md)
        self.assertIn("`render/final.mp4`", md)
        for i in gravado["itens"]:
            self.assertIn(i["id"], md)

    def test_02_cli_imprime_resumo_e_json_e_sai_com_0(self):
        raiz = self.projeto(cortes=())
        r = self.cli(raiz, cwd=raiz / "render")                                             # de dentro de uma subpasta, caminho com espaço e acento
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("CONFERÊNCIA FINAL — Conferência", r.stdout)
        self.assertIn("render/final.mp4  (vídeo longo → youtube)", r.stdout)
        self.assertIn("APROVADO: 0 erro(s)", r.stdout)
        self.assertIn("relatorio.json", r.stdout)
        r = self.cli(raiz, "--json", "--saida", str(raiz / "qa" / "pasta com espaço"))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        impresso = json.loads(r.stdout)
        self.assertEqual(list(impresso), CAMPOS_RELATORIO)
        self.assertEqual(impresso, json.loads((raiz / "qa" / "pasta com espaço" / "relatorio.json").read_text(encoding="utf-8")))
        self.assertTrue((raiz / "qa" / "pasta com espaço" / "relatorio.md").is_file())
        r = self.cli(raiz, "--saida", str(raiz / "qa" / "outro nome.json"))                  # caminho do .json: o .md vai ao lado
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue((raiz / "qa" / "outro nome.json").is_file() and (raiz / "qa" / "outro nome.md").is_file())

    def test_03_erros_de_uso_e_projeto_sem_da(self):
        raiz = self.projeto(final=False, cortes=("K01",))
        for args, trecho in ((["render/nao existe.mp4"], "não encontrei o alvo"), (["--corte", "K99"], "Cortes do projeto: K01.mp4"),
                             (["--corte", "K01", "--plataforma", "kwai"], "plataforma 'kwai' não existe"), (["cortes"], "é uma pasta"),
                             ([str(self.clipe("corte"))], "está fora do projeto"), (["--opcao-que-nao-existe"], "argumentos não reconhecidos")):
            with self.subTest(args=args):
                r = self.cli(raiz, *args)
                self.assertEqual(r.returncode, 64, r.stdout + r.stderr)
                self.assertIn(trecho, r.stderr)
        self.assertFalse((raiz / "qa" / "relatorio.json").exists(), "erro de uso não grava relatório")
        vazia = self.base / "pasta sem DA"
        vazia.mkdir(exist_ok=True)
        r = self.cli(vazia)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        ajuda = self.cli(raiz, "--help").stdout
        for trecho in ("--corte", "--plataforma", "--previa", "--saida", "--json", "qa/relatorio.json"):
            self.assertIn(trecho, ajuda)

    def test_04_sem_entregavel_nao_reprova_mas_avisa_que_nada_foi_liberado(self):
        raiz = self.projeto(final=False, cortes=())
        rel = conferencia.conferir(raiz)
        self.assertSemErros(rel)
        self.assertEqual(rel["alvos"], [])
        self.assertEqual(item(rel, "tecnico.sem_entregavel")["severidade"], "aviso")
        self.assertIn("Nenhum. Sem entregável", (raiz / "qa" / "relatorio.md").read_text(encoding="utf-8"))


# ═══════════════════════════════════════════════════════ (a) DA · (b) lint · (c) carimbo ══
class TesteReprovacoes(Base):
    def test_10_da_nao_aprovada_reprova_e_previa_rebaixa_sem_tocar_no_portao(self):
        raiz = self.projeto(aprovada=False, cortes=())
        rel = conferencia.conferir(raiz)
        self.assertFalse(rel["ok"])
        nao = item(rel, "da.nao_aprovada")
        self.assertEqual((nao["severidade"], nao["categoria"], nao["alvo"]), ("erro", "da", "da/da.json"))
        self.assertIn("da aprovar", nao["como_corrigir"])
        agrupado = item(rel, "carimbo.da_nao_aprovada")                                     # conferir-carimbo com exigência de DA aprovada: um item, não um por peça
        self.assertEqual(agrupado["severidade"], "erro")
        self.assertIn("render/final.mp4", agrupado["mensagem"])
        self.assertEqual(self.cli(raiz).returncode, 1)
        portao = (raiz / "qa" / "relatorio.json").read_text(encoding="utf-8")
        previa = conferencia.conferir(raiz, previa=True)
        self.assertSemErros(previa)
        self.assertEqual(item(previa, "da.nao_aprovada")["severidade"], "aviso")
        self.assertIsNone(item(previa, "carimbo.da_nao_aprovada"))
        self.assertEqual(Path(previa.json), raiz / "qa" / "previa.json")
        self.assertTrue((raiz / "qa" / "previa.md").is_file())
        self.assertEqual((raiz / "qa" / "relatorio.json").read_text(encoding="utf-8"), portao, "a prévia não pode regravar o portão de publicação")
        self.assertFalse(json.loads(portao)["ok"])
        r = self.cli(raiz, "--previa")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("PRÉVIA", r.stdout)
        # nem pedindo: --saida apontando para o portão é erro de uso, e o relatório reprovado continua lá
        for destino in (str(raiz / "qa" / "relatorio.json"), "qa/relatorio.json"):
            r = self.cli(raiz, "--previa", "--saida", destino)
            self.assertEqual(r.returncode, 64, r.stdout + r.stderr)
            self.assertIn("portão de publicação", r.stderr)
        self.assertEqual((raiz / "qa" / "relatorio.json").read_text(encoding="utf-8"), portao)
        self.assertEqual(self.cli(raiz, "--previa", "--saida", "qa").returncode, 0)             # pasta: grava qa/previa.json

    def test_11_da_alterada_depois_da_aprovacao_reprova_com_a_mensagem_certa(self):
        raiz = self.projeto(cortes=())
        self.assertSemErros(conferencia.conferir(raiz, gravar=False))
        editar(raiz / "da" / "da.json", lambda j: j["legenda"].update(max_palavras=j["legenda"]["max_palavras"] + 1))
        self.assertTrue(da.precisa_compilar(raiz / "da" / "da.json")[0])
        gerados = [raiz / "da" / "DA.md", *sorted((raiz / "da" / "build").iterdir())]
        antes = {p.name: p.stat().st_mtime_ns for p in gerados}
        rel = conferencia.conferir(raiz)
        self.assertFalse(rel["ok"])
        # mesmo com o build velho, a conferência lê a DA em memória: não recompila, só escreve em qa/
        self.assertEqual(antes, {p.name: p.stat().st_mtime_ns for p in gerados})
        self.assertTrue(da.precisa_compilar(raiz / "da" / "da.json")[0])
        alterada = item(rel, "da.alterada_apos_aprovacao")
        self.assertEqual(alterada["severidade"], "erro")
        self.assertIn("DA ALTERADA DEPOIS DA APROVAÇÃO", alterada["mensagem"])
        self.assertIn("da revisar", alterada["como_corrigir"])
        self.assertIn("da aprovar", alterada["como_corrigir"])
        self.assertIsNone(item(rel, "da.nao_aprovada"))
        velha = item(rel, "carimbo.sha_diferente")                                          # a peça feita com a DA aprovada agora é de outra DA
        self.assertEqual((velha["alvo"], velha["severidade"]), ("render/final.mp4", "erro"))
        self.assertEqual(rel["da_sha256"], da.carregar(raiz).sha256)
        r = self.cli(raiz)
        self.assertEqual(r.returncode, 1)
        self.assertIn("DA ALTERADA DEPOIS DA APROVAÇÃO", r.stdout)
        self.assertIn("REPROVADO", r.stdout)

    def test_12_da_invalida_reprova_e_diz_que_o_resto_nao_foi_conferido(self):
        raiz = self.projeto(cortes=())
        editar(raiz / "da" / "da.json", lambda j: j["cor"].update(dados=j["cor"]["dados"][:2]))
        rel = conferencia.conferir(raiz)
        self.assertFalse(rel["ok"])
        self.assertEqual(item(rel, "da.erro")["severidade"], "erro")
        self.assertIn("NÃO foram conferidos", item(rel, "da.invalida")["mensagem"])
        self.assertEqual(rel["alvos"], [])
        self.assertTrue(rel["da_sha256"])
        self.assertTrue((raiz / "qa" / "relatorio.json").is_file())
        # da.json que nem JSON é: o relatório antigo não pode continuar valendo — sai um novo, reprovado, com da_sha256 vazio
        (raiz / "da" / "da.json").write_text("{quebrado", encoding="utf-8")
        r = self.cli(raiz, "--json")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        ilegivel = json.loads(r.stdout)
        self.assertEqual(list(ilegivel), CAMPOS_RELATORIO)
        self.assertIs(ilegivel["ok"], False)
        self.assertEqual((ilegivel["da_sha256"], ilegivel["alvos"]), ("", []))
        self.assertIn("JSON inválido", item(ilegivel, "da.erro")["mensagem"])
        self.assertEqual(item(ilegivel, "da.invalida")["severidade"], "erro")
        self.assertEqual(json.loads((raiz / "qa" / "relatorio.json").read_text(encoding="utf-8")), ilegivel)

    def test_13_peca_sem_carimbo_peca_de_outra_da_e_intermediario(self):
        from PIL import Image
        raiz = self.projeto(cortes=())
        d = da.carregar(raiz)
        Image.new("RGB", (32, 18), d.rgb("fundo")).save(raiz / "animacoes" / "peça solta.png")
        Image.new("RGB", (32, 18), d.rgb("fundo")).save(raiz / "animacoes" / "_rascunho.png")           # intermediário: fora da conferência
        outro = self.projeto(final=False, cortes=(), preset="lab-ia")                                    # outra DA, outro sha
        d2 = da.carregar(outro)
        self.assertNotEqual(d.sha256, d2.sha256)
        thumb = outro / "thumbs" / "thumb de fora.png"
        Image.new("RGB", (32, 18), d2.rgb("fundo")).save(thumb)
        d2.carimbar(thumb, "teste: thumbnail", "thumbnail")
        shutil.copy2(thumb, raiz / "thumbs" / thumb.name)
        shutil.copy2(da.caminho_do_carimbo(thumb), raiz / "thumbs" / (thumb.name + ".da.json"))
        fora_da_zona = raiz / "animacoes" / "moldura apertada.png"
        Image.new("RGB", (32, 18), d.rgb("fundo")).save(fora_da_zona)
        d.carimbar(fora_da_zona, "teste: motor", "horizontal", {"layout": {"rotulo_na_zona": False, "janela": {"x": 0}}})
        rel = conferencia.conferir(raiz)
        self.assertFalse(rel["ok"])
        sem = item(rel, "carimbo.sem_carimbo")
        self.assertEqual((sem["alvo"], sem["severidade"], sem["categoria"]), ("animacoes/peça solta.png", "erro", "carimbo"))
        self.assertIn("SEM CARIMBO", sem["mensagem"])
        self.assertIn("d.carimbar", sem["como_corrigir"])
        outra = item(rel, "carimbo.sha_diferente")
        self.assertEqual((outra["alvo"], outra["severidade"]), ("thumbs/thumb de fora.png", "erro"))
        self.assertIn("DA DIFERENTE", outra["mensagem"])
        self.assertIn(d2.sha256[:12], outra["mensagem"])
        self.assertEqual(len(erros(rel)), 2, erros(rel))
        self.assertNotIn("_rascunho", json.dumps(rel, ensure_ascii=False))
        zona = item(rel, "zona_segura.fora_da_zona")                                                      # o que o kit mediu e gravou no carimbo
        self.assertEqual((zona["alvo"], zona["severidade"], zona["categoria"]), ("animacoes/moldura apertada.png", "aviso", "zona_segura"))
        self.assertIn("layout.rotulo_na_zona", zona["mensagem"])
        # conferência restrita a um alvo: as peças soltas do resto do projeto não entram (carimbo vale só para o alvo)
        restrita = conferencia.conferir(raiz, alvos=["render/final.mp4"], gravar=False)
        self.assertSemErros(restrita)
        self.assertEqual([a["arquivo"] for a in restrita["alvos"]], ["render/final.mp4"])
        self.assertTrue(restrita.restrito)

    def test_14_cor_literal_numa_cena_reprova_pelo_lint_estrito(self):
        raiz = self.projeto(cortes=())
        (raiz / "animacoes" / "cena ruim.js").write_text(CENA_COM_COR_LITERAL, encoding="utf-8")
        (raiz / "animacoes" / "estilo.scss").write_text("$x: 1;\n", encoding="utf-8")                      # o lint não lê: NÃO CONFERIDO reprova no estrito
        rel = conferencia.conferir(raiz)
        self.assertFalse(rel["ok"])
        cor = item(rel, "lint.cor-hex")
        self.assertEqual((cor["alvo"], cor["severidade"], cor["categoria"]), ("animacoes/cena ruim.js", "erro", "lint"))
        self.assertIn("linha 3", cor["mensagem"])
        self.assertIn("#FF0000", cor["mensagem"])
        self.assertIn("token mais próximo", cor["como_corrigir"])                                         # a sugestão do `da lint`, com o token e o ΔE
        nao = item(rel, "lint.nao_conferido")
        self.assertEqual((nao["alvo"], nao["severidade"]), ("animacoes/estilo.scss", "erro"))
        self.assertEqual(sorted(i["categoria"] for i in erros(rel)), ["lint", "lint"])
        # mesmo restrita a um corte, a cor literal do projeto continua reprovando (DA e lint são do projeto inteiro)
        self.por_corte(raiz, "K01")
        restrita = conferencia.conferir(raiz, cortes=["K01"], gravar=False)
        self.assertEqual(sorted(i["categoria"] for i in erros(restrita)), ["lint", "lint"])


# ═══════════════════════════════════════════════════════ (d) loudness · (e) técnica ══
class TesteEntregaveis(Base):
    def test_20_corte_com_loudness_fora_do_alvo_e_conferencia_de_um_corte_so(self):
        raiz = self.projeto(cortes=("K01",))
        self.por_corte(raiz, "K02", clipe="baixo")
        rel = conferencia.conferir(raiz)
        self.assertFalse(rel["ok"])
        fora = item(rel, "loudness.fora_do_alvo")
        self.assertEqual((fora["alvo"], fora["severidade"], fora["categoria"]), ("cortes/K02.mp4", "erro", "loudness"))
        self.assertIn("som.loudness.curto", fora["mensagem"])
        self.assertIn("filtro_loudnorm", fora["como_corrigir"])
        self.assertEqual([i["id"] for i in erros(rel)], ["loudness.fora_do_alvo.1"])
        self.assertEqual([a["arquivo"] for a in rel["alvos"]], ["render/final.mp4", "cortes/K01.mp4", "cortes/K02.mp4"])
        # só um corte: pelo nome (sem extensão), pelo caminho e pela CLI
        so = conferencia.conferir(raiz, cortes=["K01"], gravar=False)
        self.assertSemErros(so)
        self.assertEqual([a["arquivo"] for a in so["alvos"]], ["cortes/K01.mp4"])
        self.assertIn("2 peça(s), 2 em dia", item(so, "carimbo.resumo")["mensagem"])        # o corte e o insumo carimbado dele (render/final.mp4)
        # cadeia de composições: K03 ← legendas/base.mp4 ← animacoes/gc.png (sem auditoria). Conferir só o K03 acha o problema lá atrás
        from PIL import Image
        d = da.carregar(raiz)
        gc, base = raiz / "animacoes" / "gc da cadeia.png", raiz / "legendas" / "base da cadeia.mp4"
        Image.new("RGB", (32, 18), d.rgb("fundo")).save(gc)
        d.carimbar(gc, "teste: motor", "horizontal", auditoria="pulada")
        shutil.copy2(self.clipe("corte"), base)
        d.carimbar(base, "teste: legendas", "180x320", insumos=[gc])
        shutil.copy2(self.clipe("corte"), raiz / "cortes" / "K03.mp4")
        d.carimbar(raiz / "cortes" / "K03.mp4", "teste: cortes", "180x320", {"plataforma": "shorts"}, insumos=[base])
        cadeia = conferencia.conferir(raiz, cortes=["K03"], gravar=False)
        puladas = {i["alvo"] for i in erros(cadeia) if i["id"].startswith("carimbo.auditoria_pulada")}
        self.assertEqual(puladas, {"cortes/K03.mp4", "legendas/base da cadeia.mp4", "animacoes/gc da cadeia.png"})
        self.assertIn("3 peça(s), 0 em dia (2 insumo(s) de composição", item(cadeia, "carimbo.resumo")["mensagem"])
        for arq in (gc, base, raiz / "cortes" / "K03.mp4"):
            arq.unlink()
            da.caminho_do_carimbo(arq).unlink()
        ruim = conferencia.conferir(raiz, cortes=[str(raiz / "cortes" / "K02.mp4")], gravar=False)
        self.assertEqual([i["id"] for i in erros(ruim)], ["loudness.fora_do_alvo.1"])
        r = self.cli(raiz, "--corte", "K02")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("loudness.fora_do_alvo.1", r.stdout)
        gravado = json.loads((raiz / "qa" / "relatorio.json").read_text(encoding="utf-8"))
        self.assertEqual([a["arquivo"] for a in gravado["alvos"]], ["cortes/K02.mp4"])
        self.assertEqual(self.cli(raiz, "--corte", "K01").returncode, 0)

    def test_21_entregavel_acima_do_limite_de_duracao_da_plataforma(self):
        raiz = self.projeto(cortes=("K01",))
        duracao = video.sondar(raiz / "cortes" / "K01.mp4")["duracao"]
        self.assertSemErros(conferencia.conferir(raiz, cortes=["K01"], gravar=False))       # com os limites de verdade, 2 s cabem no Shorts
        limites = json.loads(da.PLATAFORMAS_ARQ.read_text(encoding="utf-8"))
        limites["specs"]["shorts"]["duracao_max_s"] = duracao / 2                             # o limite é LIDO de plataformas.json: nenhum número no código
        falso = self.base / "plataformas de teste.json"
        falso.write_text(json.dumps(limites, ensure_ascii=False), encoding="utf-8")
        original = da.PLATAFORMAS_ARQ
        da.PLATAFORMAS_ARQ = falso
        try:
            self.assertEqual(da.limite("shorts", "duracao_max_s"), duracao / 2)
            rel = conferencia.conferir(raiz, cortes=["K01"])
        finally:
            da.PLATAFORMAS_ARQ = original
            da._PLATAFORMAS_CACHE.clear()
        self.assertFalse(rel["ok"])
        longo = item(rel, "tecnico.duracao_max")
        self.assertEqual((longo["alvo"], longo["severidade"], longo["categoria"]), ("cortes/K01.mp4", "erro", "tecnico"))
        self.assertIn("passa do máximo de shorts", longo["mensagem"])
        self.assertEqual([i["id"] for i in erros(rel)], ["tecnico.duracao_max.1"])
        # o mínimo também vale, com o limite real: destino pedido na linha de comando vence o do carimbo
        minimo = da.limite("reels", "duracao_min_s")
        if minimo and duracao < minimo:
            curto = conferencia.conferir(raiz, cortes=["K01"], plataformas=["instagram"], gravar=False)
            self.assertEqual([i["id"] for i in erros(curto)], ["tecnico.duracao_min.1"])
            self.assertIn("mínimo de reels", item(curto, "tecnico.duracao_min")["mensagem"])

    def test_22_tipo_e_plataformas_de_cada_entregavel(self):
        raiz = self.projeto(cortes=("K01",))
        self.por_corte(raiz, "K02", plataforma="uniao")                                     # zona, não plataforma: vale para todas as verticais
        (raiz / "cortes" / "_base.mp4").write_bytes(b"intermediario")                         # nome com _ não é entregável
        verticais = [n for n in da.PLATAFORMAS if da.orientacao_de(*da.plataforma(n)["resolucao_px"]) == "vertical"]
        self.assertGreaterEqual(len(verticais), 2)
        padrao = {e["rel"]: (e["tipo"], e["plataformas"]) for e in conferencia.listar_entregaveis(raiz)}
        self.assertEqual(list(padrao), ["render/final.mp4", "cortes/K01.mp4", "cortes/K02.mp4"])
        self.assertEqual(padrao["render/final.mp4"][0], "longo")
        self.assertNotIn(padrao["render/final.mp4"][1][0], verticais)
        self.assertEqual(padrao["cortes/K01.mp4"], ("curto", ["shorts"]))
        self.assertEqual(padrao["cortes/K02.mp4"], ("curto", verticais))
        # peça vertical nativa que mora em render/: --corte a confere como peça curta
        nativa = conferencia.listar_entregaveis(raiz, cortes=["render/final.mp4"], plataformas=["tt"])
        self.assertEqual([(e["rel"], e["tipo"], e["plataformas"]) for e in nativa], [("render/final.mp4", "curto", ["tiktok"])])
        # o vídeo longo (horizontal) conferido como peça curta: orientação reprova, com o nome da plataforma
        rel = conferencia.conferir(raiz, cortes=["render/final.mp4"], plataformas=["shorts"], gravar=False)
        orient = item(rel, "tecnico.orientacao")
        self.assertEqual((orient["alvo"], orient["severidade"]), ("render/final.mp4", "erro"))
        self.assertIn("shorts pede vertical", orient["mensagem"])


# ═══════════════════════════════════════════════════════ (f) skills irmãs ══
class TesteIrmas(Base):
    def test_30_registro_de_licencas_exige_o_credito_no_creditos_md(self):
        raiz = self.projeto(final=False, cortes=())
        atribuicao = "«Sala de servidores», de Maria Exemplo — CC BY 4.0, via Wikimedia Commons (adaptado: recorte e cor)"
        registro = {"versao": 1, "itens": [
            {"id": "B001", "licenca": "CC BY 4.0", "exige_atribuicao": True, "atribuicao": atribuicao, "usado_em": ["C01"]},
            {"id": "B002", "licenca": "Pexels", "exige_atribuicao": False, "atribuicao": "Vídeo de Fulano no Pexels", "usado_em": ["C02"]},
            {"id": "B003", "licenca": "CC BY-SA 4.0", "exige_atribuicao": True, "atribuicao": "«Não usado», de Beltrano — CC BY-SA 4.0", "usado_em": []}]}
        (raiz / "broll" / "licencas.json").write_text(json.dumps(registro, ensure_ascii=False), encoding="utf-8")
        rel = conferencia.conferir(raiz, gravar=False)
        self.assertEqual([i["id"] for i in erros(rel)], ["licencas.sem_credito.1"])          # B003 não foi usado: não entra, como no creditos.md
        falta = item(rel, "licencas.sem_credito")
        self.assertEqual((falta["alvo"], falta["categoria"]), ("broll/licencas.json#B001", "licencas"))
        self.assertIn("registro.py creditos", falta["como_corrigir"])
        (raiz / "broll" / "creditos.md").write_text(f"# Créditos de b-roll\n\n## Para a descrição\n\n- {atribuicao}\n", encoding="utf-8")
        em_dia = conferencia.conferir(raiz, gravar=False)
        self.assertSemErros(em_dia)
        self.assertIn("1 exige(m) atribuição, 1 com o crédito", item(em_dia, "licencas.resumo")["mensagem"])
        (raiz / "broll" / "licencas.json").write_text("{quebrado", encoding="utf-8")
        self.assertEqual([i["id"] for i in erros(conferencia.conferir(raiz, gravar=False))], ["licencas.registro_ilegivel"])

    def test_31_ficha_de_fatos_chamada_por_posicao_e_skill_ausente_e_so_informacao(self):
        raiz = self.projeto(final=False, cortes=())
        sem_ficha = conferencia.conferir(raiz, gravar=False)
        self.assertEqual(item(sem_ficha, "fatos.sem_ficha")["severidade"], "info")
        (raiz / "pesquisa" / "fatos.json").write_text('{"versao": 1, "tema": "teste", "atualizado_em": "2026-10-12", "fatos": []}', encoding="utf-8")
        (raiz / "roteiro" / "roteiro.md").write_text("# Roteiro\n\nFrase sem dado.\n", encoding="utf-8")
        (raiz / "roteiro" / "storyboard.json").write_text('{"cenas": []}', encoding="utf-8")
        irma_real = conferencia._skill_irma
        skills = self.base / "skills de mentira"
        falso = skills / "video-pesquisa-ia" / "scripts" / "fatos.py"
        falso.parent.mkdir(parents=True, exist_ok=True)
        try:
            # 1. skill ausente: item "info", nunca erro
            conferencia._skill_irma = lambda nome, relativo: skills / "nao instalada" / nome / relativo
            ausente = conferencia.conferir(raiz, gravar=False)
            self.assertSemErros(ausente)
            self.assertEqual([(i["id"], i["severidade"]) for i in ausente["itens"] if i["categoria"] == "fatos"], [("fatos.skill_ausente", "info")])
            self.assertIn("NÃO foram conferidos", item(ausente, "fatos.skill_ausente")["mensagem"])
            # 2. skill presente (um fatos.py de mentira que fala o mesmo protocolo: --json, código 0/1)
            conferencia._skill_irma = lambda nome, relativo: skills / nome / relativo
            falso.write_text(FATOS_FALSO, encoding="utf-8")
            rel = conferencia.conferir(raiz, gravar=False)
            de_fatos = {i["id"]: i for i in rel["itens"] if i["categoria"] == "fatos"}
            self.assertEqual((de_fatos["fatos.ficha.1"]["severidade"], de_fatos["fatos.ficha.1"]["alvo"]), ("erro", "pesquisa/fatos.json#F001"))
            self.assertIn("confirmado sem fonte primária", de_fatos["fatos.ficha.1"]["mensagem"])
            self.assertEqual(de_fatos["fatos.ficha.2"]["severidade"], "erro")                 # aviso do validar: reprova porque a chamada é --estrito
            self.assertEqual(de_fatos["fatos.roteiro_ok.1"]["severidade"], "info")
            self.assertEqual((de_fatos["fatos.storyboard.1"]["severidade"], de_fatos["fatos.storyboard.1"]["alvo"]), ("erro", "roteiro/storyboard.json#C02"))
            self.assertEqual(de_fatos["fatos.storyboard.2"]["severidade"], "aviso")           # conferir-storyboard roda sem --estrito
            self.assertIn("fatos.py validar --estrito", de_fatos["fatos.ficha.1"]["como_corrigir"])
            self.assertEqual(len(erros(rel)), 3)
            # 3. skill presente que quebra: não dá para dizer que os fatos estão em ordem
            falso.write_text("import sys\nprint('estourou', file=sys.stderr)\nsys.exit(70)\n", encoding="utf-8")
            quebrada = conferencia.conferir(raiz, gravar=False)
            self.assertEqual(item(quebrada, "fatos.ficha_nao_conferido")["severidade"], "erro")
            self.assertIn("estourou", item(quebrada, "fatos.ficha_nao_conferido")["mensagem"])
        finally:
            conferencia._skill_irma = irma_real
        self.assertEqual(conferencia._skill_irma("video-pesquisa-ia", "scripts/fatos.py"), KIT.parent.parent / "video-pesquisa-ia" / "scripts" / "fatos.py")


if __name__ == "__main__":
    unittest.main(verbosity=2)
