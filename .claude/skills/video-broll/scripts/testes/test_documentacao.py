"""A documentação descreve o código que existe: todo comando citado em SKILL.md e nas referências usa opções e subcomandos
que o script aceita, e o download é sempre plano → código → `--plano CÓDIGO --confirmar`. Sem rede e sem o kit.

Regressão da revisão de 2026-10-12: o SKILL.md mandava rodar `baixar.py --busca … --escolher … --confirmar` (o código já
recusava, com 64) e as referências descreviam comportamento antigo."""
import re
import subprocess
import sys
import unittest
from pathlib import Path

from testes import apoio

SKILL = apoio.SCRIPTS.parent
DOCS = [SKILL / "SKILL.md", SKILL / "references" / "fontes.md", SKILL / "references" / "licencas.md"]
SCRIPTS = ("buscar", "baixar", "tratar", "registro")
_CITADO = re.compile(r"\b(buscar|baixar|tratar|registro)\.py\b([^`\n]*)")
_AJUDA = {}


def ajuda(script: str, sub: str | None = None) -> str:
    chave = (script, sub)
    if chave not in _AJUDA:
        cmd = [sys.executable, str(apoio.SCRIPTS / f"{script}.py"), *([sub] if sub else []), "--help"]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        _AJUDA[chave] = r.stdout if r.returncode == 0 else ""
    return _AJUDA[chave]


def subcomandos_do_registro() -> set[str]:
    return set(re.findall(r"^\s{4}([a-z][a-z-]+)\s", ajuda("registro"), flags=re.M))


def comandos_citados():
    """(arquivo, nº da linha, script, resto da linha) de cada citação com opção ou subcomando; comentário de shell fica de fora."""
    for doc in DOCS:
        for n, linha in enumerate(doc.read_text(encoding="utf-8").splitlines(), 1):
            for m in _CITADO.finditer(linha):
                resto = re.split(r"\s#\s", m.group(2))[0]
                yield doc.name, n, m.group(1), resto


class Documentacao(unittest.TestCase):
    def test_01_toda_opcao_citada_existe_no_script(self):
        subs, faltas, vistos = subcomandos_do_registro(), [], 0
        self.assertTrue({"adicionar", "atualizar", "marcar-uso", "validar", "creditos"} <= subs, subs)
        for doc, n, script, resto in comandos_citados():
            texto = ajuda(script)
            self.assertTrue(texto, f"{script}.py --help falhou")
            if script == "registro":
                palavra = re.match(r"\s+([a-z][a-z-]+)\b", resto)
                if palavra and palavra.group(1) in subs:
                    texto += ajuda("registro", palavra.group(1))
            for opcao in re.findall(r"(?<![\w-])--[a-z][a-z0-9-]*", resto):
                vistos += 1
                if not re.search(re.escape(opcao) + r"(?![\w-])", texto):
                    faltas.append(f"{doc}:{n}: {script}.py não tem {opcao}")
        self.assertGreater(vistos, 40, "o teste deixou de enxergar os comandos da documentação")
        self.assertEqual(faltas, [])

    def test_02_download_e_sempre_plano_codigo_e_confirmar(self):
        confirmacoes = [(doc, n, resto) for doc, n, script, resto in comandos_citados() if script == "baixar" and "--confirmar" in resto]
        self.assertTrue(confirmacoes, "a documentação não mostra mais como confirmar o download")
        for doc, n, resto in confirmacoes:
            self.assertIn("--plano", resto, f"{doc}:{n}: --confirmar sem --plano CÓDIGO não roda (erro de uso 64)")
            self.assertNotIn("--escolher", resto, f"{doc}:{n}: --confirmar junto de --escolher não roda")
        skill = DOCS[0].read_text(encoding="utf-8")
        for trecho in ("vale 24 h", "--plano CÓDIGO --confirmar", "VIDEO_OPS_CONTATO", "trecho_arquivo"):
            self.assertIn(trecho, skill)
        # a dica que o buscar.py imprime no fim aponta o mesmo caminho
        self.assertIn("--plano CÓDIGO --confirmar", (apoio.SCRIPTS / "buscar.py").read_text(encoding="utf-8"))

    def test_03_skill_md_no_formato_e_sem_skill_que_nao_existe(self):
        skill = DOCS[0].read_text(encoding="utf-8")
        cabeca = re.match(r"---\nname: video-broll\ndescription: [^\n]+\n---\n", skill)
        self.assertTrue(cabeca, "frontmatter com name e description de uma linha")
        self.assertLess(len(skill[cabeca.end():].splitlines()), 250)
        for titulo in ("## Passo 0 — Direção de arte", "## Armadilhas"):
            self.assertIn(titulo, skill)
        for doc in DOCS:
            texto = doc.read_text(encoding="utf-8")
            for fantasma in ("video-qa", "video-thumbnail"):
                self.assertNotIn(fantasma, texto, f"{doc.name} cita {fantasma}, que não existe")
            self.assertNotIn("/private/tmp", texto)


if __name__ == "__main__":
    unittest.main()
