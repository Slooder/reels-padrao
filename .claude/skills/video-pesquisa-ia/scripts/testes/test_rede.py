# -*- coding: utf-8 -*-
"""Testes que dependem de rede (pulados sem conexão).

Rodar a partir de scripts/:   python3 -B -m unittest testes.test_rede
Fazem 5 requisições GET leves a arxiv.org, doi.org e www.iana.org. Não precisam de chave nenhuma.
"""
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))
sys.dont_write_bytecode = True
import fatos  # noqa: E402

TEM_REDE = fatos.tem_rede(prazo=4)
HOJE = dt.date.today()


@unittest.skipUnless(TEM_REDE, "sem conexão com a internet")
class TestRede(unittest.TestCase):
    def test_pagina_viva_e_trecho_literal(self):
        literal = "[v1] Mon, 12 Jun 2017 17:57:34 UTC (1,102 KB)"
        inventado = "The Transformer was submitted on 13 July 2018"
        r = fatos.checar_url("https://arxiv.org/abs/1706.03762", prazo=20, trechos=(literal, inventado))
        self.assertEqual((r["estado"], r["http"]), ("ok", 200), r)
        self.assertEqual(r["trechos"][literal], "encontrado")
        self.assertTrue(r["trechos"][inventado].startswith("ausente"))

    def test_redirecionamento_mostra_o_destino(self):
        r = fatos.checar_url("https://doi.org/10.48550/arXiv.1706.03762", prazo=20)
        self.assertEqual(r["estado"], "redirecionado", r)
        self.assertIn("arxiv.org/abs/1706.03762", r["final"])

    def test_404_e_quebrado(self):
        r = fatos.checar_url("https://www.iana.org/pagina-que-nao-existe-video-ops", prazo=20)
        self.assertEqual((r["estado"], r["http"]), ("quebrado", 404), r)

    def test_dominio_morto_nao_vira_sem_rede(self):
        f = fatos.nova_ficha("teste de rede", HOJE)
        base = {"valor": None, "unidade": None, "referente_a": "2017", "categoria": "historia", "status": "confirmado",
                "confianca": "alta", "caduca_em": None, "como_dizer": "Em 2017 saiu o artigo.", "notas": ""}
        fonte = {"titulo": "t", "editor": "e", "tipo": "primaria", "publicado_em": None,
                 "acessado_em": HOJE.isoformat(), "trecho": "x"}
        fatos.adicionar(f, dict(base, afirmacao="O domínio reservado .invalid nunca resolve em 2017.",
                                fontes=[dict(fonte, url="https://dominio-inexistente-video-ops.invalid/")]), HOJE)
        rel = fatos.checar_links(f, prazo=10)
        self.assertEqual(rel["resultados"][0]["estado"], "sem_resposta")
        self.assertFalse(rel["sem_rede"])          # a sonda achou a internet: o problema é do link
        self.assertFalse(rel["ok"])

    def test_cli_checar_links_em_pasta_com_espaco(self):
        tmp = Path(tempfile.mkdtemp(prefix="rede çã "))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        proj = tmp / "projeto com espaço"
        (proj / "roteiro").mkdir(parents=True)
        env = dict(os.environ, VIDEO_OPS_HOME=str(tmp / "_ops"), PYTHONDONTWRITEBYTECODE="1")
        env.pop("VIDEO_OPS_HOJE", None)

        def cli(*a):
            return subprocess.run([sys.executable, "-B", str(SCRIPTS / "fatos.py"), *map(str, a)], cwd=str(proj),
                                  capture_output=True, text=True, env=env, timeout=120)

        self.assertEqual(cli("novo", "--tema", "rede").returncode, 0)
        fato = {"afirmacao": "O artigo Attention Is All You Need foi enviado ao arXiv em 12 de junho de 2017.",
                "valor": None, "unidade": None, "referente_a": "2017-06-12", "categoria": "historia",
                "status": "confirmado", "confianca": "alta", "caduca_em": None,
                "fontes": [{"titulo": "Attention Is All You Need", "url": "https://arxiv.org/abs/1706.03762",
                            "editor": "arXiv", "tipo": "primaria", "publicado_em": "2017-06-12",
                            "trecho": "[v1] Mon, 12 Jun 2017 17:57:34 UTC (1,102 KB)"}],
                "como_dizer": "Em junho de 2017 saiu o artigo que apresentou o Transformer.", "notas": ""}
        (proj / "pesquisa" / "_f.json").write_text(json.dumps(fato, ensure_ascii=False), encoding="utf-8")
        r = cli("adicionar", "@pesquisa/_f.json", "--acessado-hoje")
        self.assertEqual(r.returncode, 0, r.stderr)
        r = cli("checar-links", "--trechos", "--prazo", "20")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("encontrado", r.stdout)
        salvo = json.loads((proj / "pesquisa" / "_links.json").read_text(encoding="utf-8"))
        self.assertEqual(salvo["contagem"], {"ok": 1})
        self.assertIn("conferidos em", cli("resumo").stdout)


if __name__ == "__main__":
    unittest.main()
