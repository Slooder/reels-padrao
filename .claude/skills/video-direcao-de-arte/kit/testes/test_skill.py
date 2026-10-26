#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Regressões da qualidade da skill: invocação (bin/da), forma única de alfa no CSS, identidade da DA, lint de Python,
higiene (sem __pycache__, licenças das fontes, bloco do CLAUDE.md, rótulo da trava) e coerência documentação × código.

Rodar a partir do kit:  python3 -m unittest testes.test_skill -v
Nada aqui abre browser nem ffmpeg; as travas usadas são arquivos privados da pasta temporária (nunca a global).
A conferência do alfa NO NAVEGADOR está em test_motor_robustez.test_12 (casos ok_alfa_css e x_alfa_barra*).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import stat
import struct
import subprocess
import sys
import time
from fractions import Fraction
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent
SKILL = KIT.parent
if str(KIT) not in sys.path:
    sys.path.insert(0, str(KIT))

import da  # noqa: E402
import texto  # noqa: E402
import trava  # noqa: E402
from testes.test_da import Base  # noqa: E402

BIN_DA = KIT / "bin" / "da"
CHAMADA = "~/.claude/skills/video-direcao-de-arte/kit/bin/da"
DOCS = [SKILL / "SKILL.md", *sorted((SKILL / "references").glob("*.md")), KIT / "LEIAME.md", KIT / "modelos" / "CLAUDE.projeto.md"]


def aviso_de_direitos(fonte: Path) -> dict:
    """{nameID: texto} da tabela `name` de uma fonte TrueType/OpenType (0 = direitos, 13 = licença, 14 = URL)."""
    b = fonte.read_bytes()
    n = struct.unpack(">H", b[4:6])[0]
    tabelas = {}
    for i in range(n):
        tag, _, off, tam = struct.unpack(">4sIII", b[12 + 16 * i: 28 + 16 * i])
        tabelas[tag] = (off, tam)
    off, _ = tabelas[b"name"]
    _, qtd, ini = struct.unpack(">HHH", b[off:off + 6])
    nomes: dict[int, str] = {}
    for i in range(qtd):
        pid, _eid, _lid, nid, tam, o = struct.unpack(">HHHHHH", b[off + 6 + 12 * i: off + 18 + 12 * i])
        bruto = b[off + ini + o: off + ini + o + tam]
        try:
            s = bruto.decode("utf-16-be") if pid in (0, 3) else bruto.decode("mac-roman")
        except UnicodeDecodeError:
            continue
        if nid not in nomes or pid == 3:
            nomes[nid] = s
    return nomes


# ═══════════════════════════════════════════════════════════ D5 · invocação ══
class TesteInvocacao(Base):
    def casa_falsa(self) -> Path:
        """HOME de mentira (com espaço e acento) em que ~/.claude/skills/video-direcao-de-arte aponta para esta skill."""
        casa = self.tmp / "casa do usuário"
        (casa / ".claude" / "skills").mkdir(parents=True)
        (casa / ".claude" / "skills" / "video-direcao-de-arte").symlink_to(SKILL, target_is_directory=True)
        return casa

    def shell(self, interpretador: list[str], script: str, casa: Path, cwd: Path | None = None, **env) -> subprocess.CompletedProcess:
        arq = self.tmp / "trecho.sh"
        arq.write_text(script, encoding="utf-8")
        ambiente = {**os.environ, "HOME": str(casa), **env}
        return subprocess.run([*interpretador, str(arq)], cwd=str(cwd or self.tmp), env=ambiente, capture_output=True, text=True, timeout=60)

    def test_bin_da_existe_e_e_executavel(self):
        self.assertTrue(BIN_DA.is_file())
        self.assertTrue(BIN_DA.stat().st_mode & stat.S_IXUSR, "kit/bin/da perdeu o bit de execução")
        self.assertTrue(BIN_DA.read_text(encoding="utf-8").startswith("#!/bin/sh\n"))

    def test_chamada_documentada_funciona_em_zsh_bash_e_sh(self):
        casa = self.casa_falsa()
        for nome, interp in (("zsh", ["/bin/zsh", "-f"]), ("bash", ["/bin/bash", "--noprofile", "--norc"]), ("sh", ["/bin/sh"])):
            if not Path(interp[0]).exists():
                continue
            with self.subTest(shell=nome):
                r = self.shell(interp, f"{CHAMADA} --versao\n", casa)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertIn(f"kit de direção de arte {da.KIT_VERSAO}", r.stdout)
                r = self.shell(interp, f"{CHAMADA} achar\n", casa)          # pasta sem DA: 2, e não 127
                self.assertEqual(r.returncode, 2, r.stderr)
                self.assertIn("Nenhuma direção de arte", r.stderr)
        # PATH mínimo (shell não interativo sem Homebrew no PATH): o executável acha o Python sozinho
        r = self.shell(["/bin/sh"], f"{CHAMADA} presets\n", casa, PATH="/usr/bin:/bin")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("dossie", r.stdout)

    def test_idioma_antigo_continua_quebrado_por_isso_saiu_da_documentacao(self):
        casa = self.casa_falsa()
        antigo = 'DA="python3 ~/.claude/skills/video-direcao-de-arte/kit/da.py"\n$DA --versao\n'
        if Path("/bin/zsh").exists():
            self.assertEqual(self.shell(["/bin/zsh", "-f"], antigo, casa).returncode, 127)       # zsh não divide $DA em palavras
        self.assertNotEqual(self.shell(["/bin/bash", "--noprofile", "--norc"], antigo, casa).returncode, 0)   # til entre aspas não expande
        da.montar_parser()
        subcomandos = "|".join(re.escape(n) for n in da._SUBCOMANDOS)
        for doc in DOCS:
            txt = doc.read_text(encoding="utf-8")
            # nenhuma linha de comando com a variável (a explicação de por que ela não funciona pode citá-la em prosa)
            self.assertIsNone(re.search(r"(?m)^\s*(?:\$DA\b|DA=)", txt), f"{doc.name} ainda usa o idioma $DA em linha de comando")
            self.assertIsNone(re.search(rf"\$DA\s+(?:--d[ae]\s+\S+\s+)?(?:{subcomandos})\b", txt), f"{doc.name} ainda chama `$DA <subcomando>`")

    def test_comandos_do_skill_md_e_do_bloco_do_projeto_rodam_como_estao_escritos(self):
        casa = self.casa_falsa()
        raiz = self.projeto(nome="Projeto da chamada", base="lab-ia", pasta="projeto da chamada é")
        claude = (raiz / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertIn(f"{CHAMADA} achar", claude)
        linhas = [ln.split("#")[0].strip() for ln in claude.splitlines() if ln.startswith(CHAMADA)]
        seguros = [ln for ln in linhas if re.match(rf"{re.escape(CHAMADA)} (achar|mostrar|validar|compilar|token |conferir-carimbo|lint )", ln)]
        self.assertGreaterEqual(len(seguros), 6, linhas)
        script = "set -e\n" + "\n".join(seguros) + "\n"
        for interp in (["/bin/zsh", "-f"], ["/bin/bash", "--noprofile", "--norc"]):
            if not Path(interp[0]).exists():
                continue
            r = self.shell(interp, script, casa, cwd=raiz, VIDEO_OPS_HOME=os.environ["VIDEO_OPS_HOME"])
            self.assertEqual(r.returncode, 0, f"{interp[0]}\n{r.stdout[-600:]}\n{r.stderr[-600:]}")
            self.assertIn("#38E1FF", r.stdout)                                              # token cor.paleta.primaria do lab-ia
        # o primeiro bloco do SKILL.md (lista de presets) também é executável como está
        skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        primeiro = next(ln for ln in skill.splitlines() if ln.startswith(CHAMADA))
        r = self.shell(["/bin/zsh", "-f"] if Path("/bin/zsh").exists() else ["/bin/sh"], primeiro.split("#")[0] + "\n", casa)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_trava_py_roda_com_o_python_do_sistema(self):
        """A documentação e o bloco do CLAUDE.md mandam chamar `python3 <kit>/trava.py -- <comando>`: num shell limpo
        esse python3 é o do sistema (3.9, sem Pillow). trava.py tem de continuar só com a biblioteca padrão."""
        sistema = Path("/usr/bin/python3")
        if not sistema.exists() or subprocess.run([str(sistema), "-c", "import sys; sys.exit(sys.version_info < (3, 9))"],
                                                  capture_output=True, timeout=30).returncode != 0:
            self.skipTest("sem /usr/bin/python3 utilizável")
        env = {"PATH": "/usr/bin:/bin", "HOME": str(self.tmp), trava.VAR_ARQUIVO: str(self.tmp / "trava do sistema.lock")}
        r = subprocess.run([str(sistema), str(KIT / "trava.py"), "--estado"], env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "trava livre"), r.stderr)
        r = subprocess.run([str(sistema), str(KIT / "trava.py"), "--silencioso", "--", "/bin/echo", "olá da trava"],
                           env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "olá da trava"), r.stderr)
        self.assertEqual([p for p in KIT.rglob("__pycache__") if "node_modules" not in p.parts], [])
        bloco = (KIT / "modelos" / "CLAUDE.projeto.md").read_text(encoding="utf-8")
        self.assertIn("python3 {{KIT}}/trava.py -- <comando>", bloco)

    def test_kit_copiado_para_pasta_com_espaco_e_chamado_por_link(self):
        copia = self.tmp / "kit copiado é" / "kit"
        shutil.copytree(KIT, copia, ignore=shutil.ignore_patterns("node_modules", "__pycache__", "testes"))
        link = self.tmp / "da link"
        link.symlink_to(copia / "bin" / "da")
        r = subprocess.run([str(link), "--versao"], capture_output=True, text=True, timeout=30)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, f"kit de direção de arte {da.KIT_VERSAO}"), r.stderr)
        # kit copiado pela metade e Python inexistente: 127 com mensagem (nunca 2, que é "sem DA")
        (copia / "da.py").unlink()
        r = subprocess.run([str(copia / "bin" / "da"), "--versao"], capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 127)
        self.assertIn("não encontrei da.py", r.stderr)
        r = subprocess.run([str(BIN_DA), "--versao"], capture_output=True, text=True, timeout=30,
                           env={**os.environ, "VIDEO_OPS_PYTHON": "/nao/existe/python3"})
        self.assertEqual(r.returncode, 127)
        self.assertIn("VIDEO_OPS_PYTHON", r.stderr)


# ═════════════════════════════════════════════════ D6 · forma única de alfa ══
class TesteAlfa(Base):
    def test_da_css_e_modelo_usam_a_forma_que_funciona(self):
        raiz = self.projeto()
        css = (raiz / "da/build/da.css").read_text(encoding="utf-8")
        self.assertIn("--da-cor-fundo-rgb:10, 10, 10;", css)                 # contrato: r, g, b com vírgulas
        self.assertIn("rgba(var(--da-cor-<nome>-rgb), a)", css)              # a forma está escrita no cabeçalho do próprio da.css
        claude = (raiz / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertIn("rgba(var(--da-cor-fundo-rgb), 0.86)", claude)
        for doc in [*DOCS, raiz / "da/DA.md"]:
            for m in re.finditer(r"rgba?\(\s*var\(--da-[\w-]+-rgb\)\s*/[^)]*\)", doc.read_text(encoding="utf-8")):
                linha = doc.read_text(encoding="utf-8")[:m.start()].count("\n") + 1
                contexto = doc.read_text(encoding="utf-8").splitlines()[linha - 1]
                self.assertRegex(contexto, r"(?i)transparente|nunca|reprova|alfa-invalido|inválid",
                                 f"{doc.name}:{linha} recomenda a forma com barra, que computa transparente")

    def test_lint_reprova_a_forma_com_barra_e_sugere_a_certa(self):
        raiz = self.projeto()
        d = da.carregar(raiz)
        casos = {
            "a.css": ".a{background:rgb(var(--da-cor-fundo-rgb) / 0.86)}\n.b{background:rgba(var(--da-cor-fundo-rgb), 0.86)}\n",
            "a.js": "el.style.background = 'rgba(var(--da-dado-2-rgb) / .5)';\nel.style.color = 'rgba(var(--da-dado-2-rgb), .5)';\n",
            "a.json": "{\"style\": \"color: rgb(var(--da-neutro-1-rgb) / 50%)\"}\n",
            "a.py": "css = 'background: rgb(var(--da-cor-primaria-rgb) / 0.3)'\n",
            "a.html": "<div style=\"border-color: rgb(var(--da-cor-texto-rgb) / .2)\">x</div>\n",
        }
        for nome, conteudo in casos.items():
            with self.subTest(arquivo=nome):
                arq = raiz / "animacoes" / nome
                arq.write_text(conteudo, encoding="utf-8")
                achados = da.lint([arq], da=d)["achados"]
                self.assertEqual([(a["regra"], a["linha"]) for a in achados], [("alfa-invalido", 1)], achados)
                self.assertIn("TRANSPARENTE", achados[0]["sugestao"])
                self.assertRegex(achados[0]["sugestao"], r"rgba\(var\(--da-[\w-]+-rgb\), ")
        a = da.lint([self._arquivo(raiz, "s.css", ".a{color:rgba(10, 10, 10, .5)}\n")], da=d)["achados"][0]
        self.assertIn("rgba(var(--da-cor-fundo-rgb), 0.5)", a["sugestao"])

    @staticmethod
    def _arquivo(raiz: Path, nome: str, conteudo: str) -> Path:
        arq = raiz / "animacoes" / nome
        arq.write_text(conteudo, encoding="utf-8")
        return arq


# ════════════════════════════════════════════════════════ D7 · identidade ══
class TesteIdentidade(Base):
    def sha(self, raiz: Path) -> str:
        return da.validar(raiz / "da/da.json")["sha256"]

    def test_o_que_nao_entra_na_identidade(self):
        raiz = self.projeto(base="lab-ia")
        dj = raiz / "da/da.json"
        base = self.sha(raiz)
        fora = {
            "anotação na raiz": lambda x: x.update({"_nota": "livre", "x_legendas": {"cues_por_tela": 2, "cor_teste": "primaria"}}),
            "anotação aninhada": lambda x: (x["legenda"].update({"_obs": "ver com o cliente"}), x["cor"].update({"x_rascunho": ["#123456"]})),
            "projeto.nome/slug": lambda x: x["projeto"].update({"nome": "Outro nome", "slug": "outro-nome"}),
            "projeto.criada_em/base": lambda x: x["projeto"].update({"criada_em": "2020-01-01T00:00:00-03:00", "base": "qualquer"}),
            "conceito.frase": lambda x: x["conceito"].update({"frase": "Outra frase de conceito."}),
            "conceito.listas": lambda x: x["conceito"].update({"palavras_chave": ["a", "b"], "faca": ["x"], "nao_faca": ["y"]}),
        }
        for nome, mutar in fora.items():
            with self.subTest(caso=nome):
                self.editar(dj, mutar)
                self.assertEqual(self.sha(raiz), base, f"{nome} mudou o da_sha256 (não devia)")
        self.assertEqual(da.validar(dj)["erros"], [])
        d = da.carregar(raiz)
        self.assertEqual(d.sha256, base)
        self.assertEqual(d["x_legendas"]["cues_por_tela"], 2)                   # a anotação continua acessível…
        self.assertEqual(d["x_legendas"]["cor_teste_hex"], d.cor("primaria"))   # …e cor dentro dela ainda é resolvida

    def test_o_que_entra_na_identidade(self):
        raiz = self.projeto(base="lab-ia")
        dj = raiz / "da/da.json"
        visto = {self.sha(raiz)}
        dentro = {
            "cor": lambda x: x["cor"]["paleta"].__setitem__("primaria", "#00C2FF"),
            "tipografia": lambda x: x["tipografia"]["escala"].__setitem__("h1", 0.09),
            "legenda": lambda x: x["legenda"].__setitem__("max_palavras", 3),
            "movimento": lambda x: x["movimento"]["duracoes"].__setitem__("media", 0.41),
            "tratamento": lambda x: x["tratamento"]["grao"].__setitem__("intensidade", 9),
            "som": lambda x: x["som"]["musica"].__setitem__("clima", "outro clima"),
            "marca": lambda x: x["marca"].__setitem__("assinatura", "@outro"),
            "formatos": lambda x: x["formatos"]["thumbnail"].__setitem__("largura", 1920),
        }
        for nome, mutar in dentro.items():
            with self.subTest(caso=nome):
                self.editar(dj, mutar)
                sha = self.sha(raiz)
                self.assertNotIn(sha, visto, f"{nome} NÃO mudou o da_sha256 (devia)")
                visto.add(sha)

    def test_anotar_e_renomear_nao_derruba_aprovacao_nem_carimbos(self):
        raiz = self.projeto(base="lab-ia")
        peca = raiz / "render" / "peça 1.png"
        peca.write_bytes(b"png de mentira")
        da.carimbar(peca, "teste", "horizontal", {}, "n/a")
        da.aprovar(raiz)
        self.editar(raiz / "da/da.json", lambda x: (x.update({"x_legendas": {"modo": "karaokê"}, "_nota": "ok"}),
                                                   x["projeto"].__setitem__("nome", "Renomeado"),
                                                   x["conceito"].__setitem__("frase", "Frase nova, mesmo visual.")))
        r = da.validar(raiz / "da/da.json")
        self.assertFalse(any("DEPOIS DA APROVAÇÃO" in a for a in r["avisos"]), r["avisos"])
        self.assertEqual(da.aprovar(raiz)["estado"], "ja_aprovada")
        c = da.conferir_carimbo([peca], da=raiz)
        self.assertTrue(c["ok"], c["pecas"])
        self.assertFalse(c["da_alterada_apos_aprovacao"])
        self.assertEqual(da.carregar(raiz).meta["nome"], "Renomeado")          # o build acompanha (o lock olha o arquivo)
        self.assertIn("Frase nova", (raiz / "da/DA.md").read_text(encoding="utf-8"))
        self.editar(raiz / "da/da.json", lambda x: x["cor"]["paleta"].__setitem__("primaria", "#00C2FF"))
        self.assertTrue(any("DEPOIS DA APROVAÇÃO" in a for a in da.validar(raiz / "da/da.json")["avisos"]))

    def test_prefixo_de_anotacao_nao_pode_nomear_token(self):
        for mutar, onde in ((lambda d: d["cor"]["paleta"].__setitem__("x_extra", "#FF0000"), "cor.paleta.x_extra"),
                            (lambda d: d["tipografia"]["escala"].__setitem__("_gigante", 0.3), "tipografia.escala._gigante")):
            erros, _ = self.validar_mutado(mutar)
            self.assertContem(erros, onde)
            self.assertContem(erros, "anotação livre")

    def test_documentacao_descreve_a_regra_exata(self):
        self.assertEqual((da.FORA_DA_IDENTIDADE, da.PREFIXOS_LIVRES), (("herda", "projeto", "conceito"), ("_", "x_")))
        for doc in (SKILL / "SKILL.md", SKILL / "references" / "tokens.md", SKILL / "references" / "kit-api.md"):
            txt = doc.read_text(encoding="utf-8")
            for termo in ("`herda`", "`projeto.*`", "`conceito.*`", "`x_`"):
                self.assertIn(termo, txt, f"{doc.name} não cita {termo} na regra da identidade")


# ═════════════════════════════════════════════════════ D8 · lint de Python ══
PIL_RUIM = '''"""Docstring com "#FF0000" e (255, 0, 0) não conta."""
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageColor
import numpy as np

FUNDO = (255, 0, 0)
COR_TEXTO = "#00FF00"
PALETA = {"primaria": (255, 199, 0), "sombra": [0, 0, 0, 128]}

def desenhar(d, cor=(12, 34, 56)):
    img = Image.new("RGB", (1280, 720), (255, 0, 0))
    img2 = Image.new("RGBA", (1280, 720), "white")
    g = ImageDraw.Draw(img)
    fonte = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 80)
    padrao = ImageFont.load_default()
    g.text((10, 10), "Olá", fill="#00FF00", font=fonte)
    g.rectangle((0, 0, 100, 50), fill=(0, 0, 255), outline="red")
    g.rectangle((0, 0, 100, 50), (1, 2, 3, 255))
    img.paste((40, 40, 40), (0, 0, 10, 10))
    arr = np.full((10, 10, 3), (200, 100, 50), dtype=np.uint8)
    x = ImageColor.getrgb("navy")
    y = ImageOps.colorize(img.convert("L"), black=(0, 0, 0), white="#FFC700")
    filtro = "color=c=#112233:s=1280x720,drawbox=color=red@0.5,pad=1280:720:0:0:color=black"
    svg = '<svg><rect fill="blue" width="10"/><text style="font-family: Arial">x</text></svg>'
    CAMINHO = "fontes/MinhaFonte-Bold.otf"
    return img
'''
PIL_BOM = '''"""Thumb feita só com tokens: nada aqui é literal."""
from PIL import Image, ImageDraw
import texto

TAMANHO = (1280, 720)
CAIXA = (0, 0, 100, 50)
TRANSPARENTE = (0, 0, 0, 0)
ORIGEM = (0, 0, 0)          # ponto 3D, não é cor: o nome não é de cor
MSG = "Top #100 de 2024, hashtag #cafe, a palavra red e erro: red alert"

def desenhar(d, cor=None, fundo="fundo"):
    L, A = TAMANHO
    img = Image.new("RGB", TAMANHO, d.rgb(fundo))
    camada = Image.new("RGBA", TAMANHO, (0, 0, 0, 0))
    mascara = Image.new("L", TAMANHO, 0)
    g = ImageDraw.Draw(img)
    g.rectangle(CAIXA, fill=d.rgb("primaria"), outline=d.rgba("texto", 0.5), width=2)
    g.rectangle((0, 0, 100, 50), d.rgb("superficie"))
    g.line([(0, 0), (10, 10)], fill=cor or d.rgb("texto"), width=3)
    g.text((10, 10), d.texto("titulo", "olá"), fill=d.cor("texto"), font=d.fonte_pil("titulo", 80))
    est = texto.Estilo.do_papel(d, "legenda", 60, cor="texto", contorno=("fundo", 0.1))
    img.paste(camada, (0, 0), camada)
    filtro = f"color=c={d.cor('fundo')}:s={L}x{A},pad={L}:{A}:0:0:color={d.cor('neutro-1')}"
    caminho = d.fonte("titulo")["caminho"]
    return img, mascara, est, filtro, caminho
'''


class TesteLintPython(Base):
    def setUp(self):
        super().setUp()
        self.raiz = self.projeto()
        self.d = da.carregar(self.raiz)
        self.pasta = self.raiz / "thumbs"

    def lint(self, nome: str, conteudo: str, **k) -> dict:
        arq = self.pasta / nome
        arq.write_text(conteudo, encoding="utf-8")
        return da.lint([arq], da=self.d, **k)

    def test_reprova_cor_e_fonte_literais_em_pil(self):
        r = self.lint("thumb.py", PIL_RUIM)
        self.assertEqual((r["arquivos"], r["ok"], r["nao_conferidos"]), (1, False, []))
        self.assertEqual([(a["regra"], a["linha"]) for a in r["achados"]], [
            ("cor-tupla", 5), ("cor-hex", 6), ("cor-tupla", 7), ("cor-tupla", 7), ("cor-tupla", 9), ("cor-tupla", 10), ("cor-nome", 11),
            ("fonte-literal", 13), ("fonte-literal", 14), ("cor-hex", 15), ("cor-tupla", 16), ("cor-nome", 16), ("cor-tupla", 17),
            ("cor-tupla", 18), ("cor-tupla", 19), ("cor-nome", 20), ("cor-tupla", 21), ("cor-hex", 21),
            ("cor-ffmpeg", 22), ("cor-ffmpeg", 22), ("cor-ffmpeg", 22), ("cor-nome", 23), ("fonte-literal", 23), ("fonte-literal", 24)])
        por_linha = {a["linha"]: a["sugestao"] for a in r["achados"]}
        self.assertIn('d.cor("primaria") / d.rgb("primaria")', por_linha[21])          # "#FFC700" é exatamente a primária
        self.assertIn("exatamente o token primaria", por_linha[21])
        self.assertIn("d.fonte_pil(", por_linha[13])
        self.assertIn("load_default", [a for a in r["achados"] if a["linha"] == 14][0]["trecho"])
        sombra = [a for a in r["achados"] if a["linha"] == 7][1]
        self.assertIn('d.rgba("neutro-1", 0.502)', sombra["sugestao"])                # tupla RGBA → d.rgba(token, alfa)
        # o caso do revisor: o comando dava "1 arquivo(s) conferido(s): 0 violação(ões)… Nenhuma cor ou fonte literal."
        rc, out, _ = self.cli("lint", self.pasta / "thumb.py", "--da", self.raiz)
        self.assertEqual(rc, 1)
        self.assertIn("1 arquivo(s) conferido(s): 24 violação(ões)", out)
        self.assertNotIn("Nenhuma cor ou fonte literal", out)
        self.assertIn("# da-livre", out)

    def test_codigo_que_so_usa_tokens_passa(self):
        r = self.lint("limpo.py", PIL_BOM)
        self.assertEqual((r["achados"], r["arquivos"], r["ok"]), ([], 1, True),
                         "\n".join(f"{a['linha']}:{a['coluna']} {a['regra']} {a['trecho']}" for a in r["achados"]))
        rc, out, _ = self.cli("lint", self.pasta / "limpo.py", "--da", self.raiz, "--estrito")
        self.assertEqual(rc, 0)
        self.assertIn("Nenhuma cor ou fonte literal", out)

    def test_fstrings_chaves_e_caminhos_nao_viram_falso_positivo(self):
        codigo = ("from PIL import ImageFont\n"
                  "def f(d, pasta, familia, n):\n"
                  "    a = f\"font-family: {familia}; color: {d.cor('texto')}\"\n"                 # 3: valor dinâmico — passa
                  "    b = f\"color=c={d.cor('fundo')}:s=1280x720\"\n"                          # 4: token no filtro — passa
                  "    c = f\"{pasta}/MinhaFonte-Bold.ttf\"\n"                                  # 5: arquivo de fonte escrito à mão
                  "    e = ImageFont.truetype(d.fonte('titulo')['caminho'], 40)\n"              # 6: 'titulo'/'caminho' são chaves — passa
                  "    g = ImageFont.truetype('Arial', 40)\n"                                   # 7: nome de fonte do sistema
                  "    h = ImageFont.truetype(pasta / 'fontes' / n, 40)\n"                      # 8: caminho montado sem literal de arquivo — passa
                  "    i = f\"background: rgb({d.rgb('fundo')[0]}, 2, 3); border: 1px solid red\"\n"   # 9: só o red
                  "    j = ImageFont.truetype(str(pasta / 'Library/Fonts/Helvetica.ttc'), 40)\n"  # 10
                  "    return a, b, c, e, g, h, i, j, {'.otf': 'opentype'}, '*.ttf'\n")           # 11: extensão e glob não são arquivo
        r = self.lint("fstr.py", codigo)
        self.assertEqual([(a["regra"], a["linha"]) for a in r["achados"]],
                         [("fonte-literal", 5), ("fonte-literal", 7), ("cor-nome", 9), ("fonte-literal", 10)], r["achados"])

    def test_nomes_de_cor_e_pixels_em_numpy(self):
        codigo = ("import numpy as np\n"
                  "highlight = (255, 0, 0)\n"                       # 2
                  "ACENTO = (255, 0, 0)\n"                          # 3
                  "primaria = [255, 199, 0]\n"                      # 4
                  "def f(img, arr, pontos, d):\n"
                  "    arr[:] = (255, 0, 0)\n"                      # 6: fatia inteira pintada
                  "    arr[10:20, 30:40] = (10, 10, 10, 255)\n"     # 7
                  "    arr[..., :3] = [1, 2, 3]\n"                  # 8
                  "    img.putpixel((0, 0), (255, 0, 0))\n"         # 9
                  "    pontos[0] = (10, 20, 30)\n"                  # índice simples: coordenada, passa
                  "    arr[:] = d.rgb('fundo')\n"                   # token: passa
                  "    arr[:, :, 3] = 255\n"                        # canal alfa: passa
                  "    arr[5:9] = (0, 0, 0, 0)\n"                   # transparente: passa
                  "    TAMANHO = (640, 360, 3)\n")                  # 640 > 255: não é cor
        r = self.lint("numpy.py", codigo)
        self.assertEqual([(a["regra"], a["linha"]) for a in r["achados"]],
                         [("cor-tupla", 2), ("cor-tupla", 3), ("cor-tupla", 4), ("cor-tupla", 6), ("cor-tupla", 7), ("cor-tupla", 8), ("cor-tupla", 9)],
                         "\n".join(f"{a['linha']} {a['regra']} {a['trecho']}" for a in r["achados"]))

    def test_o_proprio_kit_passa_no_lint(self):
        alvos = [*sorted(KIT.glob("*.py")), KIT / "motor"]
        r = da.lint(alvos, da=self.d, estrito=True)
        self.assertEqual(r["nao_conferidos"], [])
        self.assertEqual(r["achados"], [], "\n".join(f"{Path(a['arquivo']).name}:{a['linha']} {a['regra']} {a['trecho']}" for a in r["achados"]))
        self.assertGreaterEqual(r["arquivos"], 13)

    def test_escape_por_comentario(self):
        codigo = ("from PIL import Image\n"
                  "LOGO_DO_PATROCINADOR = (227, 6, 19)  # da-livre: vermelho da marca do patrocinador\n"
                  "COR_B = (1, 2, 3)\n"
                  "img = Image.new(\n    'RGB', (10, 10),\n    (9, 9, 9),\n)  # da-livre\n"
                  "# da-livre:inicio\nCOR_C = '#abcdef'\nCOR_D = 'red'\n# da-livre:fim\n"
                  "COR_E = 'red'\n")
        r = self.lint("escape.py", codigo)
        self.assertEqual([(a["regra"], a["linha"]) for a in r["achados"]], [("cor-tupla", 3), ("cor-nome", 12)])
        r = self.lint("livre.py", "# da-livre-arquivo: gerado por terceiros\nCOR = (1, 2, 3)\n")
        self.assertEqual((r["achados"], r["arquivos"], r["nao_conferidos"]), ([], 0, []))
        self.assertContem(r["notas"], "da-livre-arquivo")

    def test_o_que_o_lint_nao_le_nunca_sai_como_conferido(self):
        # 1. Python que não dá para analisar
        r = self.lint("quebrado.py", "def f(:\n    COR = (255, 0, 0)\n")
        self.assertEqual((r["arquivos"], r["achados"], r["ok"]), (0, [], True))
        self.assertEqual(len(r["nao_conferidos"]), 1)
        self.assertIn("erro de sintaxe na linha 1", r["nao_conferidos"][0]["motivo"])
        self.assertFalse(self.lint("quebrado.py", "def f(:\n", estrito=True)["ok"])
        # 2. extensão desconhecida passada pelo nome
        nota = self.pasta / "roteiro da thumb.md"
        nota.write_text("fundo: #FF0000\n", encoding="utf-8")
        r = da.lint([nota], da=self.d)
        self.assertEqual((r["arquivos"], r["ok"]), (0, True))
        self.assertIn(".md não é lida pelo lint", r["nao_conferidos"][0]["motivo"])
        self.assertFalse(da.lint([nota], da=self.d, estrito=True)["ok"])
        rc, out, _ = self.cli("lint", nota, "--da", self.raiz)
        self.assertEqual(rc, 0)
        self.assertIn("NÃO CONFERIDO", out)
        self.assertIn("0 arquivo(s) conferido(s)", out)
        self.assertIn("Nada foi lido: isto não é um sinal verde", out)
        self.assertNotIn("Nenhuma cor ou fonte literal", out)
        self.assertEqual(self.cli("lint", nota, "--da", self.raiz, "--estrito")[0], 1)
        rc, out, _ = self.cli("lint", nota, "--da", self.raiz, "--json")
        self.assertEqual((rc, json.loads(out)["nao_conferidos"][0]["arquivo"]), (0, str(nota)))
        # 3. numa pasta: fonte de peça em linguagem não coberta é listada; mídia e documentos, não
        for nome, conteudo in (("estilo.scss", "a{color:red}\n"), ("cena.ts", "const cor = '#ff0000';\n"), ("gerar.sh", "echo red\n"),
                               ("capa.png", "png"), ("notas.txt", "x"), ("ok.css", ".a{color:var(--da-cor-texto)}\n")):
            (self.pasta / "sub").mkdir(exist_ok=True)
            (self.pasta / "sub" / nome).write_text(conteudo, encoding="utf-8")
        r = da.lint([self.pasta / "sub"], da=self.d)
        self.assertEqual(r["arquivos"], 1)
        self.assertEqual(sorted(Path(x["arquivo"]).name for x in r["nao_conferidos"]), ["cena.ts", "estilo.scss", "gerar.sh"])
        self.assertTrue(r["ok"])
        self.assertFalse(da.lint([self.pasta / "sub"], da=self.d, estrito=True)["ok"])

    def test_data_da_livre_vale_para_o_elemento_e_nao_para_a_linha(self):
        html = ('<div><img data-da-livre src="a.png"><span style="color:#FF0000;font-family:Arial">texto</span></div>\n'
                '<div data-da-livre="captura"><p style="color:#00FF00">dentro<b style="color:#0000FF">neto</b></p></div><i style="color:#123456">fora</i>\n'
                '<svg><image data-da-livre="logo" href="l.png"/><rect fill="#FF00FF"/></svg>\n')
        r = self.lint("linha.html", html)
        self.assertEqual([(a["regra"], a["linha"], a["trecho"]) for a in r["achados"]],
                         [("cor-hex", 1, "#FF0000"), ("fonte-literal", 1, "font-family: Arial"), ("cor-hex", 2, "#123456"), ("cor-hex", 3, "#FF00FF")])
        js = ("el.setAttribute('data-da-livre', 'foto'); el.style.outlineColor = '#FF0000';\n"       # o atributo não libera a linha
              "const marcacao = `<figure data-da-livre=\"foto\"><i style=\"color:#00FF00\">a</i></figure><b style=\"color:#0000FF\">b</b>`;\n")
        r = self.lint("linha.js", js)
        self.assertEqual([(a["regra"], a["linha"], a["trecho"]) for a in r["achados"]], [("cor-hex", 1, "#FF0000"), ("cor-hex", 2, "#0000FF")])


# ═══════════════════════════════════════════════════════════ D9 · higiene ══
class TesteHigiene(Base):
    def test_nada_gera_pycache_dentro_da_skill(self):
        copia = self.tmp / "skill copiada é" / "kit"
        shutil.copytree(KIT, copia, ignore=shutil.ignore_patterns("node_modules", "__pycache__", "*.pyc"))
        env = {k: v for k, v in os.environ.items() if k != "PYTHONDONTWRITEBYTECODE"}
        comandos = [
            [sys.executable, str(copia / "da.py"), "--versao"],
            [sys.executable, str(copia / "da.py"), "presets"],
            [sys.executable, str(copia / "trava.py"), "--estado"],
            [sys.executable, "-c", f"import sys; sys.path.insert(0, {str(copia)!r}); import da, texto, video, trava"],
            [sys.executable, "-c", f"import sys; sys.path.insert(0, {str(copia)!r}); import texto"],
            [sys.executable, "-c", f"import sys; sys.path.insert(0, {str(copia)!r}); import trava, video"],
            [sys.executable, "-m", "unittest", "testes.test_da.TesteUtilidades.test_cor_e_contraste"],
        ]
        for cmd in comandos:
            r = subprocess.run(cmd, cwd=str(copia), env={**env, trava.VAR_ARQUIVO: str(self.tmp / "t.lock")}, capture_output=True, text=True, timeout=120)
            self.assertIn(r.returncode, (0, 1), f"{cmd[1:]}\n{r.stderr[-500:]}")         # --estado devolve 1 quando ocupada
            sujeira = [str(p.relative_to(copia)) for p in copia.rglob("*") if p.name == "__pycache__" or p.suffix == ".pyc"]
            self.assertEqual(sujeira, [], f"{' '.join(cmd[1:3])} deixou bytecode na skill")

    def test_cada_fonte_do_kit_tem_a_licenca_ao_lado(self):
        fontes = sorted((KIT / "fontes").glob("*.[ot]tf"))
        self.assertGreaterEqual(len(fontes), 13)
        for fonte in fontes:
            with self.subTest(fonte=fonte.name):
                lic = da.licenca_da_fonte(fonte)
                self.assertIsNotNone(lic, f"falta fontes/LICENCAS/OFL-{fonte.stem.split('-')[0]}.txt")
                txt = lic.read_text(encoding="utf-8")
                nomes = aviso_de_direitos(fonte)
                self.assertIn("SIL Open Font License, Version 1.1", nomes[13])           # a própria fonte declara a OFL
                self.assertTrue(txt.startswith(nomes[0].strip() + "\n"), "o cabeçalho da licença tem de ser o aviso de direitos da fonte")
                self.assertIn("SIL OPEN FONT LICENSE Version 1.1 - 26 February 2007", txt)
                for trecho in ("PERMISSION & CONDITIONS", "TERMINATION", "DISCLAIMER", "Reserved Font Name"):
                    self.assertIn(trecho, txt)
                self.assertIn(f"`{fonte.name}`", (KIT / "fontes" / "LICENCAS" / "LEIAME.md").read_text(encoding="utf-8"))

    def test_init_e_salvar_preset_levam_a_licenca_junto(self):
        raiz = self.projeto(base="lab-ia")
        fontes = sorted(p.name for p in (raiz / "da/fontes").glob("*.ttf"))
        self.assertEqual(fontes, ["FiraCode-Variable.ttf", "Roboto-Variable.ttf"])
        self.assertEqual(sorted(p.name for p in (raiz / "da/fontes/LICENCAS").iterdir()), ["OFL-FiraCode.txt", "OFL-Roboto.txt"])
        da.salvar_preset("canal-com-licenca", raiz)
        preset = Path(os.environ["VIDEO_OPS_HOME"]) / "da-presets" / "canal-com-licenca"
        self.assertEqual(sorted(p.name for p in (preset / "fontes/LICENCAS").iterdir()), ["OFL-FiraCode.txt", "OFL-Roboto.txt"])
        outro = self.projeto(nome="Do preset", base="canal-com-licenca", pasta="vindo do preset")
        self.assertTrue((outro / "da/fontes/LICENCAS/OFL-Roboto.txt").is_file())
        self.assertEqual(da.validar(outro / "da/da.json")["erros"], [])
        self.assertEqual(da.conferir_carimbo(None, da=outro)["pecas"], [])               # licença não é peça

    def test_bloco_do_claude_md_so_reconhece_delimitador_em_linha_propria(self):
        # caso 1 do revisor: prosa ANTES do bloco citando os dois delimitadores → o bloco duplicava
        raiz = self.projeto(pasta="init C")
        claude = raiz / "CLAUDE.md"
        original = claude.read_text(encoding="utf-8")
        nota = f"Nota do usuário: o bloco `{da.CLAUDE_INI} … {da.CLAUDE_FIM}` abaixo é gerado pelo init; não editar.\n\n"
        cabeca, resto = original.split(da.CLAUDE_INI, 1)
        claude.write_text(cabeca + nota + da.CLAUDE_INI + resto, encoding="utf-8")
        antes = claude.read_text(encoding="utf-8")
        info = da.iniciar(raiz)
        self.assertEqual(info["claude_md"], "inalterado")
        self.assertEqual(claude.read_text(encoding="utf-8"), antes)
        self.assertIsNone(info["backup_claude_md"])
        self.assertEqual(list(raiz.glob("CLAUDE.md.bak-*")), [])                          # sem alteração, sem backup
        # caso 2: menções em prosa em volta de texto do cliente, sem bloco nenhum → o texto sumia
        raiz2 = self.tmp / "init C2"
        raiz2.mkdir()
        texto_cliente = (f"# Projeto\n\nO bloco da direção de arte começa em {da.CLAUDE_INI} (não mexer).\n\n"
                         "## Regras do cliente (NÃO PERDER)\n- Nunca citar o concorrente pelo nome.\n\n"
                         f"…e termina em {da.CLAUDE_FIM}, logo depois.\n")
        (raiz2 / "CLAUDE.md").write_text(texto_cliente, encoding="utf-8")
        info = da.iniciar(raiz2, nome="Init C2")
        novo = (raiz2 / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertEqual(info["claude_md"], "acrescentado")
        self.assertTrue(novo.startswith(texto_cliente.rstrip("\n")))                      # nada do usuário foi tocado
        self.assertIn("Nunca citar o concorrente pelo nome.", novo)
        self.assertEqual(len(re.findall(rf"(?m)^{re.escape(da.CLAUDE_INI)}$", novo)), 1)
        self.assertEqual(info["backup_claude_md"].read_text(encoding="utf-8"), texto_cliente)   # e há cópia do arquivo anterior
        # reexecutar continua idempotente
        self.assertEqual(da.iniciar(raiz2)["claude_md"], "inalterado")
        self.assertEqual(len(list(raiz2.glob("CLAUDE.md.bak-*"))), 1)

    def test_bloco_editado_e_atualizado_com_backup_e_dois_blocos_param_tudo(self):
        raiz = self.projeto(pasta="init D")
        claude = raiz / "CLAUDE.md"
        editado = claude.read_text(encoding="utf-8").replace("Regra de submissão", "REGRA MEXIDA À MÃO") + "\n## Minhas notas\nficam.\n"
        claude.write_text(editado, encoding="utf-8")
        info = da.iniciar(raiz)
        self.assertEqual(info["claude_md"], "atualizado")
        novo = claude.read_text(encoding="utf-8")
        self.assertNotIn("REGRA MEXIDA", novo)
        self.assertTrue(novo.rstrip().endswith("ficam."))
        self.assertEqual(info["backup_claude_md"].read_text(encoding="utf-8"), editado)
        rc, out, _ = self.cli("init", raiz)
        self.assertEqual(rc, 0)
        self.assertIn("inalterado", out)
        # dois pares (ou delimitadores fora de ordem): erro acionável e NADA muda, nem pastas novas
        duplo = novo + "\n" + da.CLAUDE_INI + "\nbloco colado por engano\n" + da.CLAUDE_FIM + "\n"
        claude.write_text(duplo, encoding="utf-8")
        with self.assertRaises(da.DAErro) as c:
            da.iniciar(raiz)
        self.assertIn("exatamente um par", str(c.exception))
        self.assertEqual(claude.read_text(encoding="utf-8"), duplo)
        claude.write_text(f"x\n{da.CLAUDE_FIM}\ntexto\n{da.CLAUDE_INI}\n", encoding="utf-8")
        with self.assertRaises(da.DAErro):
            da.iniciar(raiz)
        novo_proj = self.tmp / "init E"
        novo_proj.mkdir()
        (novo_proj / "CLAUDE.md").write_text(f"{da.CLAUDE_INI}\nsem fim\n", encoding="utf-8")
        with self.assertRaises(da.DAErro):
            da.iniciar(novo_proj, nome="E")
        self.assertEqual(sorted(p.name for p in novo_proj.iterdir()), ["CLAUDE.md"])     # init que falha não deixa rastro

    def test_forcar_sem_base_recria_da_mesma_base(self):
        raiz = self.projeto(base="lab-ia", pasta="forcar")
        self.assertEqual(da.carregar(raiz).cor("primaria"), "#38E1FF")
        info = da.iniciar(raiz, forcar=True)                                             # antes: virava dossiê em silêncio
        self.assertEqual(info["base"], "lab-ia")
        self.assertContem(info["avisos"], "mesma base da anterior (lab-ia)")
        self.assertTrue(info["backup"].is_file())
        self.assertEqual(da.carregar(raiz).cor("primaria"), "#38E1FF")
        self.assertEqual(da.iniciar(raiz, base="dossie", forcar=True)["base"], "dossie")  # --base explícito continua valendo
        self.assertEqual(da.carregar(raiz).cor("primaria"), "#FFC700")
        filho = self.projeto(nome="Filho", base="quadro-negro", herdar=True, pasta="forcar herdado")
        self.editar(filho / "da/da.json", lambda x: x["projeto"].pop("base"))
        self.assertEqual(da.iniciar(filho, forcar=True)["base"], "quadro-negro")         # sem projeto.base: usa o `herda`

    def test_extrair_ignora_a_propria_folha_e_valida_as_faixas(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow ausente")
        raiz = self.projeto(pasta="extrair 2x")
        ref = raiz / "da/referencias/ref 01 cartela.png"
        img = Image.new("RGB", (400, 240), self_cor("#F4F1EA"))
        img.paste(self_cor("#C8102E"), (0, 0, 120, 240))
        img.save(ref)
        os.chdir(raiz)
        r1 = da.extrair([ref])
        self.assertTrue((raiz / "da/referencias/referencias_folha.png").is_file())
        globo = sorted((raiz / "da/referencias").glob("*.png"))                           # o glob do SKILL.md na 2ª execução
        self.assertEqual(len(globo), 2)
        r2 = da.extrair(globo)
        self.assertEqual([Path(x["arquivo"]).name for x in r2["referencias"]], ["ref 01 cartela.png"])
        self.assertEqual([Path(x).name for x in r2["ignoradas"]], ["referencias_folha.png"])
        self.assertEqual(r2["geral"]["paleta"], r1["geral"]["paleta"])                    # a folha não contamina a paleta
        rc, out, _ = self.cli("extrair", *globo)
        self.assertEqual(rc, 0)
        self.assertIn("Análise de 1 referência(s) (1 ignorada(s)", out)
        with self.assertRaises(da.DAErro) as c:
            da.extrair([raiz / "da/referencias/referencias_folha.png"])
        self.assertIn("não são referência", str(c.exception))
        rc, _, err = self.cli("extrair", ref, "--cores", "20")
        self.assertEqual(rc, da.SAIDA_USO)
        self.assertIn("6 a 8", err)
        self.assertEqual(self.cli("extrair", ref, "--quadros", "0")[0], da.SAIDA_USO)

    def test_rotulo_padrao_da_trava_nao_vaza_a_linha_de_comando(self):
        segredo = "https://exemplo.invalid/v.mp4?key=VALOR-FICTICIO-DE-TESTE-123"
        self.assertEqual(trava._rotulo_padrao(["/opt/homebrew/bin/ffmpeg", "-i", segredo, "saida.mp4"]), "ffmpeg")
        self.assertEqual(trava._rotulo_padrao([sys.executable, "-c", "import time", segredo]), Path(sys.executable).name)
        self.assertEqual(trava._rotulo_padrao(["/usr/bin/python3", "/x/y/baixar video.py", "--url", segredo]), "python3 baixar video.py")
        self.assertEqual(trava._rotulo_padrao(["node", "--no-warnings", "/kit/motor/render.mjs", "--cena", "titulo"]), "node render.mjs")
        self.assertEqual(trava._rotulo_padrao(["yt-dlp", segredo]), "yt-dlp")
        arquivo = self.tmp / "trava privada.lock"
        env = {**os.environ, trava.VAR_ARQUIVO: str(arquivo)}
        env.pop(trava.VAR_DONO, None)
        dono = subprocess.Popen([sys.executable, str(KIT / "trava.py"), "--silencioso", "--", sys.executable, "-c", "import time; time.sleep(8)", segredo],
                                env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            limite = time.monotonic() + 10
            while time.monotonic() < limite and not (arquivo.is_file() and arquivo.stat().st_size > 0):
                time.sleep(0.05)
            registro = arquivo.read_text(encoding="utf-8", errors="replace")
            self.assertNotIn("VALOR-FICTICIO", registro)
            self.assertNotIn("exemplo.invalid", registro)
            self.assertIn(Path(sys.executable).name, registro)
            self.assertEqual(stat.S_IMODE(arquivo.stat().st_mode), 0o600)                 # só o dono lê e escreve o registro
            espera = subprocess.run([sys.executable, str(KIT / "trava.py"), "--espera-max", "0.6", "--", "/bin/echo", "x"],
                                    env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(espera.returncode, trava.SAIDA_TEMPO_ESGOTADO)
            self.assertIn("aguardando trava", espera.stderr)
            self.assertNotIn("VALOR-FICTICIO", espera.stderr)                             # quem espera não imprime o comando do dono
        finally:
            dono.terminate()
            try:
                dono.wait(timeout=10)
            except subprocess.TimeoutExpired:
                dono.kill()
            for fluxo in (dono.stdout, dono.stderr):
                fluxo.close()

    def test_erro_de_uso_do_render_nao_espera_a_fila_da_trava(self):
        """`da.py render` entrava na trava ANTES de o node conferir os argumentos: com a fila ocupada, um parâmetro
        digitado errado esperava minutos para dar erro 64. Agora a conferência (leve, sem browser) roda antes da fila."""
        try:
            import da_ext_motor
            da_ext_motor.achar_node()
        except da.DAErro:
            self.skipTest("node ausente")
        raiz = self.projeto(pasta="render sem fila")
        arquivo = self.tmp / "trava ocupada.lock"
        env = {**os.environ, trava.VAR_ARQUIVO: str(arquivo)}
        env.pop(trava.VAR_DONO, None)
        ocupante = subprocess.Popen([sys.executable, str(KIT / "trava.py"), "--silencioso", "--rotulo", "ocupante de teste", "--", "/bin/sleep", "40"],
                                    env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            limite = time.monotonic() + 10
            while time.monotonic() < limite and trava.estado(str(arquivo))["livre"]:
                time.sleep(0.05)
            self.assertFalse(trava.estado(str(arquivo))["livre"], "o ocupante de teste não pegou a trava privada")

            def render(*args, espera=20):
                t0 = time.monotonic()
                r = subprocess.run([str(BIN_DA), "render", *args], cwd=str(raiz), env=env, capture_output=True, text=True, timeout=espera)
                return r, time.monotonic() - t0

            fila = raiz / "animacoes" / "fila ruim.json"
            fila.write_text(json.dumps([{"cena": "titulo", "saida": "f1.png", "quadro": 0.5, "params": {"titulo": "A"}},
                                        {"cena": "barras", "saida": "f2.png", "quadro": 0.5, "params": {"dados": "x"}}]), encoding="utf-8")
            casos = [
                (["--cena", "titulo", "--saida", "animacoes/x.png", "--quadro", "0.5", "--params", '{"titlo": "AO VIVO"}'], 64, 'Quis dizer "titulo"?'),
                (["--cena", "titulo", "--saida", "animacoes/x.png", "--escla", "0.5"], 64, "Quis dizer --escala?"),
                (["--fila", str(fila)], 64, "job 1 (barras)"),
                (["--cena", "titulo", "--saida", "animacoes/x.png", "--quadro", "0.5", "--params", '{"titulo": "AO VIVO"}', "--validar"], 0, "VÁLIDO: 1 job(s)"),
                (["--", "--help"], 0, "--validar"),
            ]
            for args, codigo, trecho in casos:
                with self.subTest(args=" ".join(args[:4])):
                    r, dt = render(*args)
                    self.assertEqual(r.returncode, codigo, r.stderr[-400:])
                    self.assertIn(trecho, r.stdout + r.stderr)
                    self.assertNotIn("aguardando trava", r.stderr)                         # nunca entrou na fila
                    self.assertLess(dt, 10, "o erro de uso esperou a trava")
            self.assertFalse((raiz / "animacoes" / "x.png").exists())
            self.assertFalse(trava.estado(str(arquivo))["livre"])                          # o ocupante continua lá: ninguém o esperou
            # a ajuda do motor não depende de haver DA
            r = subprocess.run([str(BIN_DA), "render", "--", "--help"], cwd=str(self.tmp), env=env, capture_output=True, text=True, timeout=20)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("--cena ARQ", r.stdout)
        finally:
            ocupante.terminate()
            try:
                ocupante.wait(timeout=10)
            except subprocess.TimeoutExpired:
                ocupante.kill()
        # com a trava livre a conferência prévia é dispensada (custaria um node a mais em todo render)
        import da_ext_motor
        chamadas = []
        original = da_ext_motor._conferir_fora_da_trava
        da_ext_motor._conferir_fora_da_trava = lambda cmd, cwd, capturar=True: (chamadas.append(cmd), original(cmd, cwd, capturar))[1]
        antes = {k: os.environ.get(k) for k in (trava.VAR_ARQUIVO, trava.VAR_DONO)}
        os.environ[trava.VAR_ARQUIVO] = str(self.tmp / "trava livre.lock")
        os.environ.pop(trava.VAR_DONO, None)
        try:
            r = da_ext_motor.render(["--cena", "titulo", "--saida", str(raiz / "animacoes" / "y.png"), "--quadro", "0.5", "--params", '{"titlo": 1}'],
                                    da_obj=da.carregar(raiz), capturar=True)
            self.assertEqual((r.returncode, chamadas), (64, []))                           # erro de uso veio do próprio motor, já dentro da trava livre
        finally:
            da_ext_motor._conferir_fora_da_trava = original
            for k, v in antes.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    def test_chamadas_documentadas_da_api_fazem_o_que_a_documentacao_mostra(self):
        from PIL import Image
        self.assertEqual(da.fps_racional("29.97"), Fraction(30000, 1001))                 # kit-api §3
        self.assertEqual(da.fps_racional("23,976"), Fraction(24000, 1001))
        self.assertEqual(da.fps_racional("59.94"), Fraction(60000, 1001))
        self.assertEqual(da.fps_racional("12.5"), Fraction(25, 2))
        d = da.carregar(self.projeto())
        est = texto.Estilo.do_papel(d, "legenda", tamanho_px=67, cor="texto", contorno=("fundo", 0.11))
        self.assertEqual(est.com(cor="primaria").cor, d.rgba("primaria"))                  # exemplo do docstring de texto.py
        self.assertEqual(est.com(cor=d.cor("primaria")).cor, d.rgba("primaria"))           # exemplo da kit-api §4
        self.assertEqual(est.com(cor=(d, "dado-2")).cor, d.rgba("dado-2"))
        self.assertEqual(est.com(cor=d.rgba("texto", 0.5), tamanho=40).tamanho, 40)
        with self.assertRaises(da.DAErro):
            est.com(cor="primarya")
        destino, camada = Image.new("RGBA", (400, 300), d.rgba("fundo", 0)), Image.new("RGBA", (100, 60), d.rgba("primaria"))
        self.assertEqual(texto.colar(destino, camada, 200, 150, ancora="centro"), (150, 120))          # centra nos DOIS eixos
        self.assertEqual(texto.colar(destino, camada, 200, 150, ancora="centro_centro"), (150, 120))
        self.assertEqual(texto.colar(destino, camada, 200, 150, ancora="centro_base"), (150, 90))
        self.assertEqual(texto.colar(destino, camada, 200, 150, ancora="direita_base"), (100, 90))
        self.assertEqual(texto.colar(destino, camada, 200, 150), (200, 150))
        with self.assertRaises(da.DAErro):
            texto.colar(destino, camada, 0, 0, ancora="meio")
        _, info = texto.desenhar_linha(["dinheiro", "público", "desviado", "sempre"], texto.Estilo.legenda(d, 1080, 1920), d, 1080, 1920)
        self.assertTrue(info["encolheu"])                                                  # encolher deixou de ser silencioso
        self.assertLess(info["tamanho"], info["tamanho_pedido"])
        _, info = texto.desenhar_linha(["A", "conta"], texto.Estilo.legenda(d, 1080, 1920), d, 1080, 1920)
        self.assertFalse(info["encolheu"])


def self_cor(hexa: str) -> tuple:
    return da.hex_para_rgb(hexa)


# ═════════════════════════════════════════ coerência documentação × código ══
class TesteDocumentacao(Base):
    def test_frontmatter_e_tamanho_do_skill_md(self):
        linhas = (SKILL / "SKILL.md").read_text(encoding="utf-8").split("\n")
        self.assertEqual(linhas[0], "---")
        fim = linhas.index("---", 1)
        campos = [ln.split(":", 1)[0] for ln in linhas[1:fim]]
        self.assertEqual(campos, ["name", "description"])                                  # dois campos, description numa linha só
        self.assertEqual(linhas[1], f"name: {SKILL.name}")
        self.assertIn("Difere das irmãs:", linhas[2])
        self.assertLess(len(linhas), 400)

    def test_nenhum_arquivo_da_skill_embute_o_caminho_de_montagem(self):
        proibidos = ("/private/tmp/", "scratchpad", "/Downloads/video 2", "/var/folders/")
        arquivos = [*DOCS, BIN_DA, KIT / "fontes" / "LICENCAS" / "LEIAME.md", *sorted(KIT.glob("*.py")), KIT / "plataformas.json",
                    *sorted((KIT / "motor").glob("*.*")), *sorted((KIT / "motor" / "cenas").glob("*.js"))]
        for arq in arquivos:
            txt = arq.read_text(encoding="utf-8")
            for p in proibidos:
                self.assertNotIn(p, txt, f"{arq.relative_to(SKILL)} cita {p}")

    def test_todo_subcomando_esta_documentado(self):
        da.montar_parser()
        api = (SKILL / "references" / "kit-api.md").read_text(encoding="utf-8")
        skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        bloco = (KIT / "modelos" / "CLAUDE.projeto.md").read_text(encoding="utf-8")
        for nome in da._SUBCOMANDOS:
            if nome.startswith("meu-") or nome.startswith("teste-ext"):
                continue                                                                   # registrados por outros testes
            self.assertRegex(api, rf"\| `{re.escape(nome)}[ `]", f"kit-api.md §2 não documenta o subcomando {nome}")
            self.assertRegex(skill, rf"(?:bin/da |· |`){re.escape(nome)}\b", f"SKILL.md não cita o subcomando {nome}")
        self.assertIn(f"{len([n for n in da._SUBCOMANDOS if not n.startswith(('meu-', 'teste-ext'))])} subcomandos", skill)
        for nome in ("achar", "validar", "compilar", "lint", "conferir-carimbo", "render", "aprovar", "revisar", "conferencia"):
            self.assertIn(f"bin/da {nome}", bloco)

    def test_exemplos_de_codigo_da_kit_api_passam_no_lint_e_compilam(self):
        """Os próximos engenheiros copiam estes blocos: a cena de exemplo (§9) tem de passar no lint estrito e os
        blocos Python têm de ser sintaxe válida (os nomes citados existem nos módulos)."""
        import ast
        api = (SKILL / "references" / "kit-api.md").read_text(encoding="utf-8")
        cena = re.search(r"```js\n(// selo\.js.*?)```", api, re.S)
        self.assertIsNotNone(cena, "kit-api.md §9 perdeu o exemplo selo.js")
        raiz = self.projeto(base="lab-ia")
        arq = raiz / "animacoes" / "selo.js"
        arq.write_text(cena.group(1), encoding="utf-8")
        r = da.lint([arq], da=da.carregar(raiz), estrito=True)
        self.assertEqual((r["ok"], r["arquivos"], r["achados"]), (True, 1, []))
        for trecho in ("export const meta", "export function build(palco, p, ctx)", "export function seek(t)"):
            self.assertIn(trecho, cena.group(1))
        import video
        modulos = {"da": da, "texto": texto, "video": video, "trava": trava}
        blocos = re.findall(r"```python\n(.*?)```", api, re.S)
        self.assertGreaterEqual(len(blocos), 6)
        for bloco in blocos:
            limpo = bloco.replace("…", "None")
            limpo = re.sub(r"=\s*b\"None\" \| iteravel_de_bytes", "=None", limpo)       # `entrada=b"…" | iteravel_de_bytes` é notação
            try:
                arvore = ast.parse(limpo)
            except SyntaxError as e:
                self.fail(f"bloco Python do kit-api.md não é sintaxe válida (linha {e.lineno}: {e.text!r})\n{bloco[:300]}")
            for no in ast.walk(arvore):                                                   # da.x / texto.x / video.x / trava.x citados existem
                if isinstance(no, ast.Attribute) and isinstance(no.value, ast.Name) and no.value.id in modulos:
                    self.assertTrue(hasattr(modulos[no.value.id], no.attr), f"kit-api.md cita {no.value.id}.{no.attr}, que não existe")

    def test_documentacao_esta_no_escopo_final_da_operacao(self):
        """Escopo final (1.6.0): não existem skills de QA nem de thumbnail — a conferência final (C5) é o comando
        `da conferencia` e a thumbnail sai direto pelo kit; a video-pauta-midia está no mapa do pipeline; nenhuma
        skill aparece como promessa."""
        import argparse
        da.montar_parser()
        fontes = [*DOCS, *sorted(KIT.glob("*.py")), *sorted((KIT / "motor").glob("*.*")), *sorted((KIT / "motor" / "cenas").glob("*.js"))]
        textos = {arq.relative_to(SKILL).as_posix(): arq.read_text(encoding="utf-8") for arq in fontes}
        raiz = self.projeto()
        da.compilar_da(raiz / "da" / "da.json")
        textos["<projeto>/CLAUDE.md"] = (raiz / "CLAUDE.md").read_text(encoding="utf-8")       # textos gerados pelo da.py
        textos["<projeto>/da/DA.md"] = (raiz / "da" / "DA.md").read_text(encoding="utf-8")
        existem = {"video-direcao-de-arte", "video-pesquisa-ia", "video-pauta-midia", "video-broll", "video-animacao-explicativa",
                   "video-legendas", "video-cortes-verticais", "video-publicacao", "video-transcricao", "video-montagem",
                   "video-motion-graphics", "video-animacao-audio", "video-efeitos-sonoros", "video-mixagem"}
        roteiro = {"gerar-ganchos", "gerar-roteiro", "melhorar-roteiro"}
        for nome, txt in textos.items():
            for proibido in ("video-" + "qa", "video-" + "thumbnail", "(futura)", "(futuras)"):
                self.assertNotIn(proibido, txt, f"{nome} ainda cita {proibido}")
            citadas = set(re.findall(r"(?<![\w/.-])video-[a-z]+(?:-[a-z]+)*", txt)) - {"video-ops"}
            self.assertLessEqual(citadas, existem, f"{nome} cita skill que não existe: {sorted(citadas - existem)}")
        # o mapa do pipeline traz todas as skills que existem, e a video-pauta-midia com o que ela lê e escreve
        pipeline = textos["references/pipeline.md"]
        for skill in sorted(existem | roteiro):
            self.assertIn(skill, pipeline, f"pipeline.md não cita {skill}")
        pauta = next(ln for ln in pipeline.split("\n") if ln.startswith("| **video-pauta-midia**"))
        for trecho in ("roteiro/roteiro.md", "roteiro/pauta.json", "roteiro comentado", "broll/bruto/", "broll/licencas.json", "YouTube", "animacoes/"):
            self.assertIn(trecho, pauta)
        self.assertRegex(pipeline, r"DIREÇÃO DE ARTE[^\n]*\n→ pauta de mídia")                   # na ordem: depois da DA aprovada
        self.assertIn("video-pauta-midia", textos["references/kit-api.md"].split("## 17. ")[1].split("### 17.1")[0])
        self.assertIn("video-pauta-midia", textos["SKILL.md"].split("\n")[2])                    # na description: irmã que produz peça
        # C5 é um comando do kit: tabela das camadas, §18 da kit-api com o contrato e TODAS as opções da CLI
        skill = textos["SKILL.md"]
        self.assertRegex(skill, r"\| \*\*C5 conferência final\*\* \| `da conferencia` — um comando do kit, não uma skill")
        c5 = textos["references/kit-api.md"].split("## 18. Conferência final (C5)")[1]
        for campo in ("versao", "ok", "verificado_em", "da_sha256", "alvos", "arquivo", "sha256", "bytes", "resumo", "erros", "avisos",
                      "itens", "id", "categoria", "alvo", "severidade", "mensagem", "como_corrigir"):
            self.assertIn(f'"{campo}"', c5, f"kit-api.md §18 não mostra o campo {campo} do contrato")
        import da_ext_conferencia as conferencia
        for categoria in conferencia.CATEGORIAS:
            self.assertIn(f"`{categoria}`", c5)
        analisador = argparse.ArgumentParser()
        da._SUBCOMANDOS["conferencia"]["configurar"](analisador)
        opcoes = sorted(o for acao in analisador._actions for o in acao.option_strings if o.startswith("--") and o != "--help")
        self.assertEqual(opcoes, ["--corte", "--json", "--plataforma", "--previa", "--saida"])
        linha_cli = next(ln for ln in textos["references/kit-api.md"].split("\n") if ln.startswith("| `conferencia "))
        for opcao in opcoes:
            self.assertIn(f"`{opcao}", c5, f"kit-api.md §18 não documenta {opcao}")
            self.assertIn(opcao, linha_cli)
            self.assertIn(opcao, skill)
        for nome in ("SKILL.md", "references/pipeline.md", "references/kit-api.md", "kit/LEIAME.md", "kit/modelos/CLAUDE.projeto.md",
                     "<projeto>/CLAUDE.md", "<projeto>/da/DA.md", "references/metodo-da.md", "references/tokens.md", "references/plataformas.md"):
            self.assertRegex(textos[nome], r"da(?:\.py)? conferencia", f"{nome} não aponta o comando da conferência final")
        # thumbnail: sem skill, direto pelo kit, apontando a receita executada (§17.1)
        self.assertIn("### 17.1 Thumbnail — direto pelo kit", textos["references/kit-api.md"])
        for nome in ("SKILL.md", "references/pipeline.md", "references/plataformas.md", "references/tokens.md", "<projeto>/CLAUDE.md"):
            self.assertIn("§17.1", textos[nome], f"{nome} não aponta a receita de thumbnail do kit")

    def test_numeros_da_documentacao_batem_com_o_codigo(self):
        skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        api = (SKILL / "references" / "kit-api.md").read_text(encoding="utf-8")
        tokens = (SKILL / "references" / "tokens.md").read_text(encoding="utf-8")
        self.assertEqual(len(da.PASTAS_TRABALHO), 12)
        self.assertIn("12 pastas de trabalho", skill)
        self.assertIn("12 pastas de trabalho", api)
        self.assertNotIn("13 pastas", skill + api)
        self.assertIn(f"Kit {da.KIT_VERSAO}", skill)
        self.assertIn(f"kit {da.KIT_VERSAO}", api)
        d = da.carregar(self.projeto(base="lab-ia"))
        self.assertEqual(d.cor("primaria"), "#38E1FF")
        self.assertIn('`"#38E1FF"`', api)                                                  # exemplo de d.cor("primaria") (lab-ia)
        self.assertEqual(len(d["cor"]["permitidas"]), 12)
        self.assertNotIn("13 cores", api)
        m = d.margens("vertical")
        self.assertEqual((m["x0"], m["x1"], m["largura"], m["y0"], m["y1"], m["altura"]), (120, 780, 660, 288, 1248, 960))
        self.assertIn("'x1': 780", api)
        self.assertIn("x 120–780", skill)
        posicoes = da.esquema()["$defs"]["posicao"]["enum"] if "posicao" in da.esquema().get("$defs", {}) else None
        if posicoes:
            self.assertIn(f"{len(posicoes)} posições", tokens)
        for suite in sorted((KIT / "testes").glob("test_*.py")):                           # contagem de testes citada no SKILL.md
            n = len(re.findall(r"(?m)^    def test_", suite.read_text(encoding="utf-8")))
            self.assertIn(f"`{suite.name}` ({n})", skill, f"SKILL.md cita outra contagem para {suite.name} (são {n})")
        plataformas = json.loads((KIT / "plataformas.json").read_text(encoding="utf-8"))
        uniao = plataformas["margens_seguras_vertical"]["uniao"]
        self.assertEqual((uniao["oficial"], uniao["derivado_de"]), (False, ["reels", "tiktok", "shorts"]))     # nomes canônicos (D16)
        self.assertEqual(uniao["retangulo_px"], {"x0": m["x0"], "y0": m["y0"], "x1": m["x1"], "y1": m["y1"], "largura": m["largura"], "altura": m["altura"]})


if __name__ == "__main__":
    import unittest
    unittest.main(verbosity=2)
