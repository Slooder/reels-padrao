# -*- coding: utf-8 -*-
"""Suíte sem rede do fatos.py (skill video-pesquisa-ia).

Rodar a partir de scripts/:   python3 -B -m unittest
(o -B evita deixar __pycache__ na pasta da skill; sem ele também roda)

Tudo acontece numa pasta temporária com espaço e acento no nome. O único tráfego é de laço local
(127.0.0.1), contra um servidor HTTP que o próprio teste sobe.
"""
import datetime as dt
import http.server
import json
import subprocess
import sys
import threading
import unittest
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
from apoio import (Base, HOJE, KIT, SCRIPTS, checar_falso, conferido, fato, fatos, fonte, mensagens,  # noqa: E402
                   preco)


# ----------------------------------------------------------------------------- criar e adicionar
class TestNovoEAdicionar(Base):
    def test_novo_cria_ficha_no_contrato(self):
        self.nova()
        f = self.ficha()
        self.assertEqual(f["versao"], 1)
        self.assertEqual(f["tema"], "Como funciona um modelo de linguagem")
        self.assertEqual(f["atualizado_em"], "2026-10-06")
        self.assertEqual(f["fatos"], [])
        modo = (self.proj / "pesquisa" / "fatos.json").stat().st_mode & 0o777
        self.assertTrue(modo & 0o044, f"a ficha precisa ser legível por outras ferramentas (modo {oct(modo)})")

    def test_novo_nao_sobrescreve(self):
        self.nova()
        r = self.cli("novo", "--tema", "Outro")
        self.assertEqual(r.returncode, 1)
        self.assertIn("nada foi sobrescrito", r.stderr)
        self.assertEqual(self.ficha()["tema"], "Como funciona um modelo de linguagem")
        r = self.cli("novo", "--tema", "Outro", "--forcar")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.ficha()["tema"], "Outro")
        self.assertTrue((self.proj / "pesquisa" / "_fatos.anterior.json").is_file())

    def test_sem_ficha_codigo_2(self):
        for cmd in (["resumo"], ["validar"], ["vencidos"], ["md"], ["credito", "F001"], ["checar-links"]):
            r = self.cli(*cmd)
            self.assertEqual(r.returncode, 2, f"{cmd}: {r.stderr}")
            self.assertIn("fatos.py novo", r.stderr)

    def test_novo_fora_de_projeto_exige_pasta(self):
        solta = self.tmp / "pasta solta"
        solta.mkdir()
        r = self.cli("novo", "--tema", "x", cwd=solta)
        self.assertEqual(r.returncode, 64)
        self.assertIn("--projeto", r.stderr)
        self.assertFalse((solta / "pesquisa").exists())
        r = self.cli("novo", "--tema", "x", "--projeto", solta, cwd=self.tmp)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((solta / "pesquisa" / "fatos.json").is_file())

    def test_projeto_antes_e_depois_do_subcomando(self):
        self.nova()
        for args in (["--projeto", self.proj, "resumo"], ["resumo", "--projeto", self.proj]):
            r = self.cli(*args, cwd=self.tmp)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("FICHA DE FATOS", r.stdout)

    def test_acha_a_ficha_subindo_pastas(self):
        self.nova()
        funda = self.proj / "animacoes" / "cena 01"
        funda.mkdir(parents=True)
        r = self.cli("resumo", cwd=funda)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_adicionar_atribui_ids_e_ordem_do_contrato(self):
        self.nova()
        r = self.adiciona(fato())
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("F001 adicionado", r.stdout)
        r = self.adiciona(preco())
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("F002 adicionado", r.stdout)
        f = self.ficha()
        self.assertEqual([x["id"] for x in f["fatos"]], ["F001", "F002"])
        self.assertEqual(list(f["fatos"][0])[:12], list(fatos.CAMPOS_FATO))
        self.assertEqual(list(f["fatos"][0]["fontes"][0]), list(fatos.CAMPOS_FONTE))
        self.assertEqual(f["fatos"][1]["termos"], ["Exemplo-1"])        # campo extra preservado
        self.assertEqual(fatos.validar_ficha(f, HOJE)["erros"], [])

    def test_adicionar_json_no_argumento_e_stdin(self):
        self.nova()
        r = self.cli("adicionar", json.dumps(fato(), ensure_ascii=False))
        self.assertEqual(r.returncode, 0, r.stderr)
        r = self.cli("adicionar", "-", entrada=json.dumps(preco(), ensure_ascii=False))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(self.ficha()["fatos"]), 2)

    def test_adicionar_recusa_duplicata_obvia(self):
        self.nova()
        self.assertEqual(self.adiciona(fato()).returncode, 0)
        r = self.adiciona(fato())
        self.assertEqual(r.returncode, 1)
        self.assertIn("duplicata de F001", r.stderr)
        quase = fato(afirmacao="O artigo que apresentou a arquitetura Transformer foi publicado no arXiv, em junho de 2017!")
        self.assertEqual(self.adiciona(quase).returncode, 1)
        self.assertEqual(len(self.ficha()["fatos"]), 1)
        # mesma frase com outro número NÃO é duplicata: é outro fato (ou uma contradição a investigar)
        outro = fato(afirmacao="O artigo que apresentou a arquitetura Transformer foi publicado no arXiv em junho de 2018.")
        self.assertEqual(self.adiciona(outro).returncode, 0)
        self.assertEqual(self.adiciona(fato(), "--forcar").returncode, 0)
        self.assertEqual([x["id"] for x in self.ficha()["fatos"]], ["F001", "F002", "F003"])

    def test_duplicata_por_valor_fonte_e_periodo(self):
        f = fatos.nova_ficha("t", HOJE)
        fatos.adicionar(f, preco(), HOJE)
        with self.assertRaises(fatos.ErroFatos) as c:
            fatos.adicionar(f, preco(afirmacao="Um milhão de tokens de entrada sai por US$ 1,25 no Exemplo-1."), HOJE)
        self.assertIn("mesmo valor", c.exception.mensagem)
        self.assertIn("mesmo modelo", c.exception.mensagem)

    def test_adicionar_recusa_fato_invalido_sem_gravar(self):
        self.nova()
        antes = (self.proj / "pesquisa" / "fatos.json").read_text(encoding="utf-8")
        sem_acesso = fato()
        del sem_acesso["fontes"][0]["acessado_em"]
        r = self.adiciona(sem_acesso)
        self.assertEqual(r.returncode, 1)
        self.assertIn("acessado_em", r.stderr)
        self.assertIn("--acessado-hoje", r.stderr)
        self.assertEqual((self.proj / "pesquisa" / "fatos.json").read_text(encoding="utf-8"), antes)
        r = self.adiciona(sem_acesso, "--acessado-hoje")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.ficha()["fatos"][0]["fontes"][0]["acessado_em"], "2026-10-06")

    def test_caduca_padrao(self):
        self.nova()
        r = self.adiciona(preco(caduca_em=None))
        self.assertEqual(r.returncode, 1)
        self.assertIn("2026-11-05", r.stderr)               # sugestão: 30 dias após o acesso
        self.assertIn("--caduca-padrao", r.stderr)
        r = self.adiciona(preco(caduca_em=None), "--caduca-padrao")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.ficha()["fatos"][0]["caduca_em"], "2026-11-05")

    def test_lote_e_tudo_ou_nada(self):
        self.nova()
        r = self.adiciona([fato(), preco(categoria="nenhuma")])
        self.assertEqual(r.returncode, 1)
        self.assertIn("item 2", r.stderr)
        self.assertEqual(self.ficha()["fatos"], [])
        r = self.adiciona([fato(), preco()])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(self.ficha()["fatos"]), 2)

    def test_simular_nao_grava(self):
        self.nova()
        r = self.adiciona(fato(), "--simular")
        self.assertEqual(r.returncode, 0)
        self.assertIn("nada foi gravado", r.stdout)
        self.assertEqual(self.ficha()["fatos"], [])

    def test_padroes_conservadores(self):
        self.nova()
        minimo = {"afirmacao": "A OpenAI foi fundada em dezembro de 2015.", "referente_a": "dezembro de 2015",
                  "categoria": "empresa", "fontes": []}
        r = self.adiciona(minimo)
        self.assertEqual(r.returncode, 0, r.stderr)
        f = self.ficha()["fatos"][0]
        self.assertEqual((f["status"], f["confianca"], f["valor"], f["caduca_em"]), ("nao_confirmado", "baixa", None, None))
        self.assertIn("nao_confirmado", r.stdout)
        sem_categoria = dict(minimo, afirmacao="A Anthropic foi fundada em 2021 por ex-funcionários da OpenAI.")
        del sem_categoria["categoria"]
        r = self.adiciona(sem_categoria)
        self.assertEqual(r.returncode, 1)
        self.assertIn("categoria", r.stderr)

    def test_erros_de_uso_sao_64_e_em_portugues(self):
        self.nova()
        r = self.cli("adicionar", '{"afirmacao": ')
        self.assertEqual(r.returncode, 64)
        self.assertIn("JSON inválido", r.stderr)
        self.assertIn("@arquivo.json", r.stderr)
        r = self.cli("adicionar", "@nao existe.json")
        self.assertEqual(r.returncode, 64)
        self.assertIn("arquivo não encontrado", r.stderr)
        r = self.cli("adicionar")
        self.assertEqual(r.returncode, 64)
        self.assertIn("faltam argumentos obrigatórios", r.stderr)
        r = self.cli("inventado")
        self.assertEqual(r.returncode, 64)
        self.assertIn("opção inválida", r.stderr)
        r = self.cli()
        self.assertEqual(r.returncode, 64)
        self.assertIn("uso: fatos.py", r.stderr)
        r = self.cli("resumo", "--hoje", "06/10/2026")
        self.assertEqual(r.returncode, 64)
        self.assertIn("AAAA-MM-DD", r.stderr)

    def test_ajuda_de_todos_os_subcomandos(self):
        r = self.cli("--help")
        self.assertEqual(r.returncode, 0)
        self.assertIn("uso: fatos.py", r.stdout)
        for sub in ("novo", "adicionar", "atualizar", "remover", "validar", "checar-links", "vencidos", "md",
                    "conferir-roteiro", "conferir-storyboard", "credito", "resumo"):
            self.assertIn(sub, r.stdout)
            h = self.cli(sub, "--help")
            self.assertEqual(h.returncode, 0, sub)
            self.assertIn(f"uso: fatos.py {sub}", h.stdout)
            self.assertIn("opções:", h.stdout)
            self.assertNotIn("usage:", h.stdout)


# ----------------------------------------------------------------------------- validação
class TestValidacao(unittest.TestCase):
    def val(self, f):
        f = dict(f, id=f.get("id", "F001"))
        return fatos.validar_fato(f, HOJE)

    def assertErro(self, f, pedaco, campo=None):
        erros, _ = self.val(f)
        self.assertTrue(any(pedaco in e["mensagem"] and (campo is None or e["campo"] == campo) for e in erros),
                        f"esperava erro com {pedaco!r} em {campo}; veio: {mensagens(erros)}")

    def assertSemErros(self, f):
        erros, _ = self.val(f)
        self.assertEqual(erros, [], mensagens(erros))

    def assertAviso(self, f, pedaco):
        _, avisos = self.val(f)
        self.assertTrue(any(pedaco in a["mensagem"] for a in avisos), f"esperava aviso com {pedaco!r}; veio: {mensagens(avisos)}")

    def test_fato_modelo_passa_limpo(self):
        # recém-registrado: válido, com UM aviso — o trecho ainda não foi conferido na página
        for f in (fato(), preco()):
            erros, avisos = self.val(f)
            self.assertEqual(erros, [], mensagens(erros))
            self.assertEqual([a["campo"] for a in avisos], ["fontes"], mensagens(avisos))
            self.assertIn("ainda não conferido", avisos[0]["mensagem"])
            self.assertEqual(self.val(conferido(f)), ([], []))

    def test_confirmado_exige_primaria_ou_duas_secundarias_distintas(self):
        sec = lambda ed, u: fonte(tipo="secundaria", editor=ed, url=u)  # noqa: E731
        self.assertErro(fato(fontes=[]), "confirmado", "status")
        self.assertErro(fato(fontes=[sec("The Verge", "https://a.example/1")]), "1 editor secundário")
        self.assertErro(fato(fontes=[sec("The Verge", "https://a.example/1"), sec("the verge", "https://a.example/2")]),
                        "1 editor secundário")
        duas = [sec("The Verge", "https://a.example/1"), sec("Wired", "https://b.example/2")]
        self.assertSemErros(fato(confianca="media", fontes=duas))
        self.assertErro(fato(confianca="alta", fontes=duas), "confiança alta exige fonte primária", "confianca")
        self.assertSemErros(fato(fontes=[fonte()]))
        self.assertSemErros(fato(status="nao_confirmado", confianca="baixa", fontes=[]))

    def test_categorias_volateis_exigem_caduca_em(self):
        for cat, dias in (("preco", 30), ("benchmark", 60), ("modelo", 60)):
            esperado = (HOJE + dt.timedelta(days=dias)).isoformat()
            self.assertErro(fato(categoria=cat, caduca_em=None), esperado, "caduca_em")
            self.assertSemErros(fato(categoria=cat, caduca_em="2026-11-01"))
        for cat in ("historia", "conceito", "empresa", "outro"):
            self.assertSemErros(fato(categoria=cat, caduca_em=None))

    def test_url_precisa_ser_https(self):
        self.assertErro(fato(fontes=[fonte(url="http://arxiv.org/abs/1706.03762")]), "https", "fontes[1].url")
        self.assertErro(fato(fontes=[fonte(url="arxiv.org/abs/1706.03762")]), "https")
        self.assertErro(fato(fontes=[fonte(url="https://localhost/x")]), "domínio")
        self.assertErro(fato(fontes=[fonte(url="https://arxiv.org/abs/1706 03762")]), "espaço")
        self.assertErro(fato(fontes=[fonte(url="")]), "URL vazia")

    def test_trecho_no_maximo_25_palavras(self):
        self.assertSemErros(fato(fontes=[fonte(trecho=" ".join(["palavra"] * 25))]))
        self.assertErro(fato(fontes=[fonte(trecho=" ".join(["palavra"] * 26))]), "26 palavras", "fontes[1].trecho")
        self.assertErro(fato(fontes=[fonte(trecho="  ")]), "trecho vazio")

    def test_datas(self):
        self.assertErro(fato(fontes=[fonte(acessado_em="2026-13-01")]), "acessado_em")
        self.assertErro(fato(fontes=[fonte(acessado_em="06/10/2026")]), "acessado_em")
        self.assertErro(fato(fontes=[fonte(acessado_em="2026-10-07")]), "futuro", "fontes[1].acessado_em")
        self.assertErro(fato(fontes=[fonte(acessado_em=None)]), "acessado_em obrigatório")
        self.assertErro(fato(fontes=[fonte(publicado_em="2027-01-01")]), "futuro", "fontes[1].publicado_em")
        self.assertErro(fato(fontes=[fonte(publicado_em="2026-10-06", acessado_em="2026-10-01")]), "posterior")
        self.assertErro(fato(caduca_em="amanhã"), "caduca_em inválido")
        self.assertSemErros(fato(fontes=[fonte(publicado_em=None)]))
        sem = fonte()
        del sem["acessado_em"]
        self.assertErro(fato(fontes=[sem]), "campo obrigatório ausente na fonte: acessado_em")

    def test_esquema_do_contrato(self):
        for campo in fatos.CAMPOS_FATO:
            if campo == "id":
                continue
            f = fato()
            del f[campo]
            self.assertErro(f, f"campo obrigatório ausente: {campo}", campo)
        self.assertErro(fato(categoria="preço"), "categoria inválido")
        self.assertErro(fato(status="ok"), "status inválido")
        self.assertErro(fato(confianca="altíssima"), "confianca inválido")
        self.assertErro(fato(valor=[1]), "valor deve ser")
        self.assertErro(fato(valor=True), "valor deve ser")
        self.assertErro(fato(unidade=3), "unidade")
        self.assertErro(fato(referente_a=""), "referente_a vazio")
        self.assertErro(fato(afirmacao=" "), "afirmacao vazia")
        self.assertErro(fato(fontes="arxiv"), "lista")
        self.assertErro(fato(fontes=[fonte(tipo="oficial")]), "tipo inválido")
        self.assertErro(fato(fontes=[fonte(editor="")]), "editor vazio")
        self.assertErro(dict(fato(), id="1"), "id inválido")
        self.assertSemErros(fato(valor="GPT-5", unidade=None))
        self.assertSemErros(fato(valor=None))

    def test_divergente_exige_duas_fontes(self):
        self.assertErro(fato(status="divergente", fontes=[fonte()]), "divergente", "status")
        dois = [fonte(), fonte(url="https://b.example/x", editor="Outro")]
        self.assertSemErros(fato(status="divergente", fontes=dois, notas="A diz X; B diz Y."))
        self.assertAviso(fato(status="divergente", fontes=dois, notas=""), "divergente sem notas")

    def test_avisos_de_formulacao(self):
        self.assertAviso(preco(caduca_em="2026-10-01"), "VENCIDO em 2026-10-01")
        self.assertAviso(preco(como_dizer="A entrada do Exemplo-1 custa US$ 1,25 por milhão de tokens."), "como_dizer sem data")
        self.assertAviso(preco(caduca_em="2027-06-01"), "longa")
        self.assertAviso(fato(fontes=[fonte(url="https://pt.wikipedia.org/wiki/Transformer")]), "wikipedia.org marcada como primária")
        self.assertAviso(fato(como_dizer="O Transformer é a melhor arquitetura de IA."), "superlativo sem data")
        self.assertAviso(fato(como_dizer=""), "sem como_dizer")
        self.assertAviso(fato(confianca="baixa"), "confiança baixa")
        self.assertAviso(fato(status="nao_confirmado", fontes=[]), "nao_confirmado com confiança alta")
        self.assertAviso(preco(autodeclarado=True), "autodeclarado sem atribuição")
        _, avisos = self.val(conferido(preco(autodeclarado=True, como_dizer="Segundo a própria Exemplo, em outubro de "
                                             "2026 a entrada custava US$ 1,25 por milhão de tokens.")))
        self.assertEqual(avisos, [], mensagens(avisos))
        for atribuida in ("Em outubro de 2026, na estimativa da própria Exemplo, a entrada custava US$ 1,25 por milhão de tokens.",
                          "Em outubro de 2026, a Exemplo estimava a entrada em US$ 1,25 por milhão de tokens.",
                          "Em outubro de 2026, nas contas da Exemplo, a entrada custava US$ 1,25 por milhão de tokens."):
            _, avisos = self.val(conferido(preco(autodeclarado=True, como_dizer=atribuida)))
            self.assertEqual(avisos, [], atribuida)
        self.assertAviso(fato(fontes=[fonte(editor="Advances in Neural Information Processing Systems 30")]), "crédito na tela")
        self.assertAviso(fato(afirmacao="Transformer, 2017."), "curta demais")
        self.assertAviso(preco(valor=2.5), "o valor (2.5) não aparece na afirmacao")
        self.assertAviso(fato(valor=400000, unidade="tokens"), "não aparece na afirmacao")
        _, avisos = self.val(conferido(fato(valor=400000, unidade="tokens",
                                            afirmacao="O modelo Exemplo-1 lê 400 mil tokens de uma vez.")))
        self.assertEqual(avisos, [], mensagens(avisos))
        # o ano dentro de uma data ("junho de 2017") conta como o valor 2017
        _, avisos = self.val(conferido(fato(valor=2017)))
        self.assertEqual(avisos, [], mensagens(avisos))
        self.assertAviso(fato(categoria="empresa", valor=300000000000, unidade="US$"), "caduca_em")

    def test_ficha_inteira(self):
        f = fatos.nova_ficha("Tema", HOJE)
        self.assertTrue(fatos.validar_ficha(f, HOJE)["ok"])
        f["fatos"] = [dict(fato(), id="F001"), dict(preco(), id="F001")]
        rel = fatos.validar_ficha(f, HOJE)
        self.assertFalse(rel["ok"])
        self.assertIn("id repetido", mensagens(rel["erros"]))
        self.assertFalse(fatos.validar_ficha({"versao": 2, "tema": "", "atualizado_em": "2030-01-01", "fatos": []}, HOJE)["ok"])
        self.assertEqual(len(fatos.validar_ficha({"versao": 2, "tema": "", "atualizado_em": "2030-01-01", "fatos": []},
                                                 HOJE)["erros"]), 3)
        self.assertFalse(fatos.validar_ficha([], HOJE)["ok"])
        self.assertFalse(fatos.validar_ficha({"versao": 1, "tema": "t", "atualizado_em": "2026-10-06", "fatos": ["x"]},
                                             HOJE)["ok"])


class TestValidarCLI(Base):
    def test_validar_ok_reprovado_estrito_e_json(self):
        self.nova()
        self.assertEqual(self.adiciona([fato(), preco()]).returncode, 0)
        r = self.cli("validar")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("2 fatos, 0 erros, 2 avisos → ok", r.stdout)     # trechos ainda não conferidos
        self.assertIn("ainda não conferido", r.stdout)
        r = self.cli("validar", "--estrito")
        self.assertEqual(r.returncode, 1, r.stdout)                      # fato lido × fato lembrado: --estrito cobra a prova
        self.confere_trechos()
        r = self.cli("validar", "--estrito")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("2 fatos, 0 erros, 0 avisos → ok", r.stdout)
        # edição à mão que quebra regras: http, sem caduca_em, vencimento
        f = self.ficha()
        f["fatos"][0]["fontes"][0]["url"] = "http://arxiv.org/abs/1706.03762"
        f["fatos"][1]["caduca_em"] = None
        self.grava_json("pesquisa/fatos.json", f)
        r = self.cli("validar")
        self.assertEqual(r.returncode, 1)
        self.assertIn("F001.fontes[1].url", r.stdout)
        self.assertIn("F002.caduca_em", r.stdout)
        self.assertIn("REPROVADA", r.stdout)
        j = json.loads(self.cli("validar", "--json").stdout)
        self.assertFalse(j["ok"])
        self.assertEqual(len(j["erros"]), 2)
        # só aviso: passa; com --estrito reprova
        f["fatos"][0]["fontes"][0]["url"] = "https://arxiv.org/abs/1706.03762"
        f["fatos"][1]["caduca_em"] = "2026-10-01"
        self.grava_json("pesquisa/fatos.json", f)
        self.assertEqual(self.cli("validar").returncode, 0)
        r = self.cli("validar", "--estrito")
        self.assertEqual(r.returncode, 1)
        self.assertIn("VENCIDO", r.stdout)

    def test_ficha_corrompida_da_mensagem_e_nao_traceback(self):
        self.nova()
        (self.proj / "pesquisa" / "fatos.json").write_text('{"versao": 1,\n "fatos": [', encoding="utf-8")
        r = self.cli("validar")
        self.assertEqual(r.returncode, 1)
        self.assertIn("JSON inválido na linha 2", r.stderr)
        r = self.cli("resumo")
        self.assertEqual(r.returncode, 1)
        (self.proj / "pesquisa" / "fatos.json").write_text("[]", encoding="utf-8")
        r = self.cli("resumo")
        self.assertEqual(r.returncode, 1)
        self.assertIn("formato da ficha", r.stderr)


class TestFichaEditadaAMao(Base):
    """A ficha pode chegar quebrada (edição manual): nada pode levantar exceção crua nem sair com 'erro interno'."""

    LIXO = [None, True, 0, -1, 3.5, "", " ", "texto", "2026-13-45", "2026-10-06", [], [1], {}, {"a": 1}, ["x", None], "F001",
            "https://x.example/a", "http://x", 10 ** 20, "ção ü 中文", "preco", "confirmado", "alta", "primaria"]

    def _fato_lixo(self, rnd):
        f = {k: rnd.choice(self.LIXO) for k in fatos.CAMPOS_FATO if rnd.random() > .15}
        if rnd.random() > .3:
            f["fontes"] = [rnd.choice([{k: rnd.choice(self.LIXO) for k in fatos.CAMPOS_FONTE if rnd.random() > .15},
                                       rnd.choice(self.LIXO)]) for _ in range(rnd.randint(0, 3))]
        if rnd.random() > .5:
            f["id"] = rnd.choice(["F001", "F002", "x", 3])
        if rnd.random() > .6:
            f["termos"] = rnd.choice(self.LIXO)
        return f

    def test_funcoes_nao_levantam_com_lixo(self):
        import random
        rnd = random.Random(7)
        ok = lambda u, p, t=(): {"url": u, "estado": "ok", "http": 200, "final": None, "detalhe": "", "trechos": {}}  # noqa: E731
        for _ in range(150):
            ficha = {"versao": rnd.choice([1, 2, None]), "tema": rnd.choice(self.LIXO), "atualizado_em": rnd.choice(self.LIXO),
                     "fatos": [rnd.choice([self._fato_lixo(rnd), rnd.choice(self.LIXO)]) for _ in range(rnd.randint(0, 4))]}
            chamadas = (lambda: fatos.validar_ficha(ficha, HOJE), lambda: fatos.resumo(ficha, HOJE),
                        lambda: fatos.vencimentos(ficha, HOJE), lambda: fatos.gerar_fatos_md(ficha, HOJE),
                        lambda: fatos.gerar_fontes_md(ficha, HOJE),
                        lambda: fatos.conferir_roteiro("Em 2017 o GPT-4 custava US$ 2 [F001].", ficha, HOJE),
                        lambda: fatos.conferir_storyboard({"cenas": [{"id": "C1", "fato_ids": ["F001"], "params": {}}]}, ficha, HOJE),
                        lambda: fatos.checar_links(ficha, checar=ok, sonda=lambda: True),
                        lambda: fatos.adicionar(json.loads(json.dumps(ficha)), self._fato_lixo(rnd), HOJE))
            for chamada in chamadas:
                try:
                    chamada()
                except fatos.ErroFatos:
                    pass                                                 # recusa com mensagem é o comportamento certo

    def test_cli_nunca_da_erro_interno(self):
        ruim = {"versao": 1, "tema": "t", "atualizado_em": "2026-10-06", "fatos": [
            {"id": "F001", "afirmacao": ["lista"], "valor": {"a": 1}, "unidade": 3, "referente_a": None, "categoria": ["preco"],
             "status": {"x": 1}, "confianca": True, "caduca_em": 20261106, "fontes": True, "como_dizer": None, "notas": 0,
             "termos": "texto"},
            {"id": "F002", "fontes": [True, {"url": ["x"], "editor": False, "titulo": 9, "acessado_em": [], "trecho": {}}]},
            "nem objeto é"]}
        self.grava_json("pesquisa/fatos.json", ruim)
        (self.proj / "roteiro" / "r.md").write_text("Em 2017 o GPT-4 custava US$ 2 [F001] e 3% [F002].\n", encoding="utf-8")
        r = self.cli("validar")
        self.assertEqual(r.returncode, 1)
        self.assertIn("ERROS", r.stdout)
        for cmd in (["resumo"], ["resumo", "--json"], ["vencidos"], ["md"], ["md", "--mesmo-com-erros"], ["credito", "F001"],
                    ["credito", "F002", "--forcar"], ["conferir-roteiro", "roteiro/r.md"], ["atualizar", "F001", "--notas", "x"],
                    ["remover", "F002"], ["checar-links", "--id", "F001"]):
            r = self.cli(*cmd)
            self.assertIn(r.returncode, (0, 1), f"{cmd}: código {r.returncode}\n{r.stderr}")
            self.assertNotIn("erro interno", r.stderr, cmd)


# ----------------------------------------------------------------------------- atualizar, remover, vencidos
class TestAtualizarRemoverVencidos(Base):
    def setUp(self):
        super().setUp()
        self.nova()
        self.assertEqual(self.adiciona([fato(), preco()]).returncode, 0)

    def test_atualizar_campos(self):
        r = self.cli("atualizar", "F002", '{"valor": 2.5, "afirmacao": "A entrada do modelo Exemplo-1 custa US$ 2,50 por '
                                          'milhão de tokens na API."}', "--confianca", "media", "--notas", "subiu em outubro")
        self.assertEqual(r.returncode, 0, r.stderr)
        f = self.ficha()["fatos"][1]
        self.assertEqual((f["valor"], f["confianca"], f["notas"]), (2.5, "media", "subiu em outubro"))
        self.assertEqual(f["id"], "F002")

    def test_atualizar_recusa_mudanca_invalida_sem_gravar(self):
        antes = self.ficha()
        r = self.cli("atualizar", "F002", "--caduca-em", "null")
        self.assertEqual(r.returncode, 1)
        self.assertIn("exige caduca_em", r.stderr)
        r = self.cli("atualizar", "F001", '{"fontes": []}')
        self.assertEqual(r.returncode, 1)
        self.assertIn("confirmado", r.stderr)
        r = self.cli("atualizar", "F001", '{"id": "F009"}')
        self.assertEqual(r.returncode, 64)
        r = self.cli("atualizar", "F009", "--status", "divergente")
        self.assertEqual(r.returncode, 1)
        self.assertIn("ids existentes: F001, F002", r.stderr)
        r = self.cli("atualizar", "F001")
        self.assertEqual(r.returncode, 64)
        r = self.cli("atualizar", "F001", "--status", "talvez")
        self.assertEqual(r.returncode, 64)
        self.assertIn("opção inválida", r.stderr)
        self.assertEqual(self.ficha()["fatos"], antes["fatos"])

    def test_nova_fonte_e_revalidado(self):
        velha = self.ficha()
        velha["fatos"][1]["fontes"][0]["acessado_em"] = "2026-09-01"
        velha["fatos"][1]["caduca_em"] = "2026-10-01"
        self.grava_json("pesquisa/fatos.json", velha)
        self.assertEqual(self.cli("vencidos").returncode, 1)
        nova = self.grava_json("pesquisa/_fonte nova.json", fonte(titulo="Models", url="https://exemplo.example/models",
                                                                 editor="Exemplo", publicado_em=None,
                                                                 trecho="Exemplo-1 input $1.25"))
        del_acesso = json.loads(nova.read_text(encoding="utf-8"))
        del del_acesso["acessado_em"]
        nova.write_text(json.dumps(del_acesso), encoding="utf-8")
        r = self.cli("atualizar", "F002", "--nova-fonte", "@" + str(nova), "--acessado-hoje")
        self.assertEqual(r.returncode, 0, r.stderr)
        r = self.cli("atualizar", "F002", "--nova-fonte", "@" + str(nova), "--acessado-hoje")
        self.assertEqual(r.returncode, 1)
        self.assertIn("já tem uma fonte com esta URL", r.stderr)
        # revalidar é declarar "abri hoje e o trecho está lá": sem conferência de hoje, recusa
        r = self.cli("atualizar", "F002", "--revalidar-fonte", "1", "--caduca-em", "2026-11-05")
        self.assertEqual(r.returncode, 1)
        self.assertIn("conferido HOJE", r.stderr)
        self.assertIn("checar-links --trechos --id F002", r.stderr)
        self.assertEqual(self.ficha()["fatos"][1]["caduca_em"], "2026-10-01")       # nada foi gravado
        self.confere_trechos()
        r = self.cli("atualizar", "F002", "--revalidar-fonte", "1", "--caduca-em", "2026-11-05")
        self.assertEqual(r.returncode, 0, r.stderr)
        f = self.ficha()["fatos"][1]
        self.assertEqual([s["acessado_em"] for s in f["fontes"]], ["2026-10-06", "2026-10-06"])
        self.assertEqual((f["verificado_em"], f["caduca_em"]), ("2026-10-06", "2026-11-05"))
        self.assertEqual(self.cli("vencidos").returncode, 0)
        r = self.cli("atualizar", "F002", "--revalidar-fonte", "7")
        self.assertEqual(r.returncode, 64)

    def test_revalidado_todas(self):
        velha = self.ficha()
        velha["fatos"][0]["fontes"][0]["acessado_em"] = "2026-01-15"
        self.grava_json("pesquisa/fatos.json", velha)
        self.assertEqual(self.cli("atualizar", "F001", "--revalidado").returncode, 1)
        r = self.cli("atualizar", "F001", "--revalidado", "--conferido-manual", "curta")
        self.assertEqual(r.returncode, 64)
        self.assertIn("curta demais", r.stderr)
        r = self.cli("atualizar", "F001", "--revalidado", "--conferido-manual",
                     "aberta no navegador; o resumo do artigo traz a frase citada")
        self.assertEqual(r.returncode, 0, r.stderr)
        s = self.ficha()["fatos"][0]["fontes"][0]
        self.assertEqual(s["acessado_em"], "2026-10-06")
        self.assertEqual((s["conferencia"]["estado"], s["conferencia"]["em"]), ("manual", "2026-10-06"))
        self.assertIn("resumo do artigo", s["conferencia"]["nota"])

    def test_remover_simula_e_nao_reaproveita_id(self):
        r = self.cli("remover", "F002")
        self.assertEqual(r.returncode, 0)
        self.assertIn("simulação", r.stdout)
        self.assertEqual(len(self.ficha()["fatos"]), 2)
        r = self.cli("remover", "F002", "--sim")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual([x["id"] for x in self.ficha()["fatos"]], ["F001"])
        r = self.adiciona(preco())
        self.assertIn("F003 adicionado", r.stdout)

    def test_vencidos(self):
        r = self.cli("vencidos")
        self.assertEqual(r.returncode, 0)
        self.assertIn("nenhum fato vencido", r.stdout)
        r = self.cli("vencidos", "--dias", "45")
        self.assertEqual(r.returncode, 0)
        self.assertIn("VENCEM EM ATÉ 45 DIAS (1)", r.stdout)
        self.assertIn("F002", r.stdout)
        r = self.cli("vencidos", "--hoje", "2026-11-05")
        self.assertEqual(r.returncode, 0)
        self.assertIn("(hoje)", r.stdout)
        r = self.cli("vencidos", "--hoje", "2026-11-20")
        self.assertEqual(r.returncode, 1)
        self.assertIn("VENCIDOS (1)", r.stdout)
        self.assertIn("há 15 dias", r.stdout)
        j = json.loads(self.cli("vencidos", "--hoje", "2026-11-20", "--json").stdout)
        self.assertEqual([x["id"] for x in j["vencidos"]], ["F002"])
        self.assertEqual(self.cli("vencidos", "--dias", "-1").returncode, 64)
        env = dict(self.env, VIDEO_OPS_HOJE="2026-11-20")
        self.assertEqual(self.cli("vencidos", env=env).returncode, 1)

    def test_hoje_simulado_nao_grava(self):
        """--hoje / VIDEO_OPS_HOJE simulam LEITURA; comando que grava usa a data real (a ficha não ganha data futura)."""
        antes = self.ficha()
        for cmd in (["atualizar", "F001", "--notas", "x", "--hoje", "2026-11-20"],
                    ["adicionar", "{}", "--hoje", "2026-11-20"], ["novo", "--tema", "x", "--forcar", "--hoje", "2026-11-20"],
                    ["remover", "F001", "--sim", "--hoje", "2026-11-20"],
                    ["checar-links", "--trechos", "--hoje", "2026-11-20"]):
            r = self.cli(*cmd)
            self.assertEqual(r.returncode, 64, cmd)
            self.assertIn("--hoje só simula leitura", r.stderr)
        self.assertEqual(self.ficha(), antes)
        env = dict(self.env, VIDEO_OPS_HOJE="2026-11-20")
        r = self.cli("atualizar", "F001", "--notas", "nota nova", env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("VIDEO_OPS_HOJE=2026-11-20 ignorada", r.stderr)
        self.assertEqual(self.ficha()["atualizado_em"], "2026-10-06")
        self.assertEqual(self.cli("validar").returncode, 0)             # nenhuma "data no futuro"


# ----------------------------------------------------------------------------- md e crédito
class TestMdECredito(Base):
    def setUp(self):
        super().setUp()
        self.nova()
        nao = fato(afirmacao="O modelo Exemplo-2 teria 1 trilhão de parâmetros.", valor=None, status="nao_confirmado",
                   confianca="baixa", categoria="outro", referente_a="2026", como_dizer="",
                   fontes=[fonte(tipo="secundaria", url="https://boato.example/x", editor="Blog do Boato")])
        dois = fato(afirmacao="O Transformer dispensa recorrência e convoluções.", categoria="conceito", valor=None,
                    referente_a="2017", como_dizer="O Transformer trocou a recorrência por atenção.",
                    fontes=[fonte(), fonte(titulo="NeurIPS 2017", url="https://papers.nips.cc/paper/7181", editor="NeurIPS",
                                           publicado_em="2017-12-04")])
        self.assertEqual(self.adiciona([fato(), preco(), nao, dois]).returncode, 0)
        self.confere_trechos()

    def test_md_gera_os_dois_arquivos(self):
        r = self.cli("md")
        self.assertEqual(r.returncode, 0, r.stderr)
        fm = (self.proj / "pesquisa" / "fatos.md").read_text(encoding="utf-8")
        fo = (self.proj / "pesquisa" / "fontes.md").read_text(encoding="utf-8")
        for fid in ("F001", "F002", "F003", "F004"):
            self.assertIn(f"## {fid} —", fm)
        self.assertIn("**Crédito na tela:** Fonte: arXiv, jun/2017", fm)
        self.assertIn("1,25 US$ por 1M de tokens de entrada", fm)
        self.assertIn("05/11/2026", fm)
        self.assertIn("“We propose a new simple network architecture, the Transformer”", fm)
        self.assertIn("trecho encontrado na página em 06/10/2026", fm)
        bloco = fo.split("<!-- DESCRICAO:INICIO -->")[1].split("<!-- DESCRICAO:FIM -->")[0].strip().splitlines()
        self.assertEqual(bloco[0], "Fontes:")
        self.assertEqual(bloco[1], "1. Attention Is All You Need — arXiv, jun/2017: https://arxiv.org/abs/1706.03762")
        self.assertEqual(bloco[2], "2. Pricing — Exemplo, acesso em out/2026: https://exemplo.example/pricing")
        self.assertEqual(bloco[3], "3. NeurIPS 2017 — NeurIPS, dez/2017: https://papers.nips.cc/paper/7181")
        self.assertIn("Fontes acessadas em 06/10/2026.", bloco[4])
        self.assertEqual(len(bloco), 5)                              # arXiv não repete; o boato fica fora
        self.assertNotIn("boato.example", fo)
        curta = fo.split("<!-- CURTA:INICIO -->")[1].split("<!-- CURTA:FIM -->")[0].strip()
        self.assertEqual(curta, "Fontes: arXiv (jun/2017); Exemplo (out/2026); NeurIPS (dez/2017).")
        self.assertIn("- F003 → fora da lista (não confirmado)", fo)
        self.assertIn("- F004 → 1, 3", fo)

    def test_md_filtra_pelo_roteiro(self):
        rot = self.proj / "roteiro" / "roteiro final.md"
        rot.write_text("Em 2017 saiu o artigo do Transformer [F001].\n", encoding="utf-8")
        r = self.cli("md", "--roteiro", rot)
        self.assertEqual(r.returncode, 0, r.stderr)
        fo = (self.proj / "pesquisa" / "fontes.md").read_text(encoding="utf-8")
        self.assertIn("arxiv.org", fo)
        self.assertNotIn("exemplo.example", fo)
        self.assertEqual(self.cli("md", "--roteiro", "nao existe.md").returncode, 1)

    def test_md_recusa_ficha_reprovada(self):
        f = self.ficha()
        f["fatos"][1]["caduca_em"] = None
        self.grava_json("pesquisa/fatos.json", f)
        r = self.cli("md")
        self.assertEqual(r.returncode, 1)
        self.assertFalse((self.proj / "pesquisa" / "fatos.md").exists())
        self.assertEqual(self.cli("md", "--mesmo-com-erros").returncode, 0)

    def test_credito(self):
        r = self.cli("credito", "F001")
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "Fonte: arXiv, jun/2017"))
        self.assertEqual(self.cli("credito", "f001", "--sem-prefixo").stdout.strip(), "arXiv, jun/2017")
        self.assertEqual(self.cli("credito", "F001", "--data", "ano").stdout.strip(), "Fonte: arXiv, 2017")
        r = self.cli("credito", "F002")                              # página sem data de publicação: mês do acesso
        self.assertEqual(r.stdout.strip(), "Fonte: Exemplo, out/2026")
        self.assertIn("mês do acesso", r.stderr)
        self.assertEqual(self.cli("credito", "F004", "--todas").stdout.strip(), "Fontes: arXiv, jun/2017; NeurIPS, dez/2017")
        self.assertEqual(self.cli("credito", "F004", "--fonte", "2").stdout.strip(), "Fonte: NeurIPS, dez/2017")
        self.assertEqual(self.cli("credito", "F004", "--fonte", "5").returncode, 64)
        r = self.cli("credito", "F003")
        self.assertEqual(r.returncode, 1)
        self.assertIn("não vai para a tela", r.stderr)
        self.assertEqual(self.cli("credito", "F003", "--forcar").returncode, 0)
        j = json.loads(self.cli("credito", "F001", "--json").stdout)
        self.assertEqual((j["texto"], j["param_cena"], j["editor"], j["data"], j["data_origem"]),
                         ("Fonte: arXiv, jun/2017", "arXiv, jun/2017", "arXiv", "jun/2017", "publicado_em"))
        r = self.cli("credito", "F002", "--hoje", "2026-12-25")
        self.assertEqual(r.returncode, 0)
        self.assertIn("caducou", r.stderr)

    def test_credito_so_de_fato_com_trecho_conferido(self):
        f = self.ficha()
        for x in f["fatos"]:
            for s in x["fontes"]:
                s.pop("conferencia", None)
        self.grava_json("pesquisa/fatos.json", f)
        r = self.cli("credito", "F001")
        self.assertEqual((r.returncode, r.stdout), (1, ""))
        self.assertIn("ainda não foi conferido", r.stderr)
        self.assertIn("checar-links --trechos --id F001", r.stderr)
        self.assertEqual(self.cli("credito", "F001", "--forcar").stdout.strip(), "Fonte: arXiv, jun/2017")
        self.assertEqual(self.cli("md").returncode, 0)
        fm = (self.proj / "pesquisa" / "fatos.md").read_text(encoding="utf-8")
        self.assertIn("**Crédito na tela:** _(indisponível", fm)
        self.assertIn("ainda não conferido", fm)
        self.confere_trechos(trecho="ausente (o HTML baixado não contém o trecho)")
        r = self.cli("credito", "F001")
        self.assertEqual(r.returncode, 1)
        self.assertIn("NÃO achou o trecho", r.stderr)

    def test_divergente_fica_fora_do_fontes_md(self):
        r = self.cli("atualizar", "F004", "--status", "divergente", "--confianca", "media", "--notas", "arXiv diz X; NeurIPS diz Y")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.cli("md").returncode, 0)
        fo = (self.proj / "pesquisa" / "fontes.md").read_text(encoding="utf-8")
        self.assertNotIn("papers.nips.cc", fo)                          # só o F004 usava essa fonte
        self.assertIn("- F004 → fora da lista (divergente)", fo)

    def test_meses_em_portugues(self):
        esperado = "jan fev mar abr mai jun jul ago set out nov dez".split()
        for m in range(1, 13):
            self.assertEqual(fatos.mes_ano(f"2026-{m:02d}-15"), f"{esperado[m - 1]}/2026")

    def test_resumo(self):
        r = self.cli("resumo")
        self.assertEqual(r.returncode, 0)
        self.assertIn("4 fatos", r.stdout)
        self.assertIn("confirmado 3 · divergente 0 · nao_confirmado 1", r.stdout)
        self.assertIn("ainda não conferidos", r.stdout)
        j = json.loads(self.cli("resumo", "--json").stdout)
        self.assertEqual(j["por_categoria"]["preco"], 1)
        self.assertEqual(len(j["lista"]), 4)


# ----------------------------------------------------------------------------- números, nomes e frases
class TestExtracao(unittest.TestCase):
    def nums(self, texto, **k):
        return [(i["tipo"], i["valores"]) for i in fatos.extrair_numeros(texto, **k)]

    def test_formatos_de_numero(self):
        self.assertEqual(self.nums("custa US$ 1,25 por milhão"), [("dinheiro", [1.25])])
        self.assertEqual(self.nums("são 400 mil tokens"), [("numero", [400000.0])])
        self.assertEqual(self.nums("400.000 tokens"), [("numero", [400000.0])])
        self.assertEqual(self.nums("1.047.576 tokens"), [("numero", [1047576.0])])
        self.assertEqual(self.nums("janela de 128k"), [("numero", [128000.0])])
        self.assertEqual(self.nums("tem 405B de parâmetros"), [("numero", [405e9])])
        self.assertEqual(self.nums("2,5 milhões de usuários"), [("numero", [2.5e6])])
        self.assertEqual(self.nums("acerta 87,5% das questões"), [("percentual", [87.5])])
        self.assertEqual(self.nums("subiu 12 por cento"), [("percentual", [12.0])])
        self.assertEqual(self.nums("em 2017 e em 2022"), [("ano", [2017.0]), ("ano", [2022.0])])
        self.assertEqual(self.nums("109 bilhões de dólares"), [("dinheiro", [109e9])])
        self.assertEqual(self.nums("R$ 5 mil por mês"), [("dinheiro", [5000.0])])
        self.assertEqual(self.nums("R$ 1.234,56"), [("dinheiro", [1234.56])])
        self.assertEqual(self.nums("$1.25 / 1M tokens", idioma="ambos"), [("dinheiro", [1.25]), ("numero", [1e6])])
        # ambíguo: 400,000 copiado de fonte em inglês × decimal em português
        self.assertEqual(self.nums("400,000 tokens"), [("numero", [400.0, 400000.0])])
        self.assertEqual(self.nums("1.250 palavras"), [("numero", [1250.0])])
        self.assertEqual(self.nums("1.250 words", idioma="ambos"), [("numero", [1.25, 1250.0])])

    def test_o_que_nao_e_numero_a_checar(self):
        for frase in ("O GPT-4o e o Claude 3.5 Sonnet respondem.", "Em 30 segundos você entende 3 coisas.",
                      "Passo 2: abra o Gemini 2.5 Pro.", "São 5 erros e 3 motivos.", "O vídeo começa às 10:30.",
                      "Veja em https://exemplo.example/2024/12/texto.", "Slide 3 mostra o o3-mini e o R1.",
                      "Grave em 1080p a 60fps.", "É o 1º da lista."):
            self.assertEqual(self.nums(frase), [], frase)
        # indexando a ficha nada é descartado
        self.assertEqual(self.nums("3 motivos em 30 segundos", tudo=True), [("numero", [3.0]), ("numero", [30.0])])

    def test_versao_de_modelo_nao_engole_quantidade(self):
        a = fatos.analisar_frase("O Llama 3 bilhões de parâmetros? O Llama 3.1 tem 405B.")
        self.assertEqual([i["valores"] for i in a["fortes"]], [[3e9], [405e9]])
        self.assertIn("Llama 3.1", a["modelos"])

    def test_nomes_de_modelo_sem_ajuda_de_termos(self):
        casos = {
            "O Claude Opus 5.5 tem janela de 1 milhão de tokens.": (["Claude Opus 5.5"], [[1e6]]),
            "O Claude Fable 5.1 e o Claude Haiku 4.5 custam diferente.": (["Claude Fable 5.1", "Claude Haiku 4.5"], []),
            "O Gemini 3.8 Flash-Lite custa US$ 0,30.": (["Gemini 3.8 Flash-Lite"], [[0.3]]),
            "A Meta lançou o Muse Spark 1.1 em julho de 2026.": (["Muse Spark 1.1"], [("data", None, 7, 2026)]),
            "O GPT-6.1 Sol saiu em 29 de setembro de 2026.": (["GPT-6.1"], [("data", 29, 9, 2026)]),
            "O Claude e o Gemini Flash erram.": (["Claude", "Gemini Flash"], []),
            "O Claude Opus 200 mil tokens? Não.": (["Claude Opus"], [[200000.0]]),
            "O Sonnet 4.6 e o Opus 4.8 seguem ativos.": (["Sonnet 4.6", "Opus 4.8"], []),
        }
        for frase, (modelos, numeros) in casos.items():
            a = fatos.analisar_frase(frase)
            self.assertEqual(a["modelos"], modelos, frase)
            vistos = [("data", i["dia"], i["mes"], i["ano"]) if i["tipo"] == "data" else i["valores"] for i in a["fortes"]]
            self.assertEqual(vistos, numeros, frase)

    def test_nomes_proprios(self):
        an = fatos.analisar_frase
        self.assertEqual(an("A OpenAI foi fundada por Sam Altman e Elon Musk.")["nomes"], ["OpenAI", "Sam Altman", "Elon Musk"])
        self.assertEqual(an("Modelos de linguagem preveem a próxima palavra.")["nomes"], [])
        self.assertEqual(an("Segundo a Universidade de Stanford, o custo caiu.")["nomes"], ["Universidade de Stanford"])
        self.assertEqual(an("Google lançou o artigo.")["nomes"], ["Google"])
        self.assertEqual(an("Attention Is All You Need mudou tudo.")["nomes"], ["Attention Is All You Need"])
        self.assertEqual(an("A IA NÃO PENSA COMO VOCÊ")["nomes"], [])
        self.assertEqual(an("A IA usa uma API e uma GPU.")["nomes"], [])
        self.assertEqual(an("Custa US$ 3 no Brasil.")["nomes"], ["Brasil"])
        self.assertEqual(an("O ChatGPT e o Claude 3.5 Sonnet erram.")["modelos"], ["ChatGPT", "Claude 3.5 Sonnet"])

    def test_superlativos_e_tempo_relativo(self):
        sup = lambda t: [i["bruto"].lower() for i in fatos.analisar_frase(t)["fortes"] if i["tipo"] == "superlativo"]  # noqa: E731
        self.assertEqual(sup("O GPT-4o é o melhor modelo do mundo."), ["o melhor"])
        self.assertTrue(sup("A IA mais avançada da história acabou de ser lançada pela Anthropic."))
        self.assertTrue(sup("O Gemini é mais rápido que o Claude."))
        self.assertTrue(sup("O modelo mais recente da OpenAI chegou."))
        self.assertEqual(sup("O primeiro passo é entender o que é um token."), [])
        self.assertEqual(sup("A primeira vez que usei o ChatGPT foi estranha."), [])
        self.assertEqual(sup("o que mais importa num modelo é o contexto"), [])
        self.assertEqual(sup("Essa é a melhor forma de estudar."), [])        # sem assunto de IA: não é afirmação checável
        self.assertEqual(fatos.analisar_frase("Hoje o ChatGPT é atualmente o líder.")["relativos"], ["atualmente", "hoje"])

    def test_frases_do_roteiro(self):
        texto = ("## Roteiro: teste\n\n**Motor:** 2 · Crença (45–60s)\n**Duração alvo:** 45–60s\n\n"
                 "Em 2017 saiu o Transformer. [F001] O GPT-4.1 custa US$ 2,00 [F002]. Segundo Vaswani et al. o modelo "
                 "dispensa recorrência!\nEle usa atenção.\n\n"
                 "- Slide 2 — O preço caiu 80% [F003, F004]\n"
                 "1. \"Você paga 3 vezes mais?\" — [quebra de crença]\n\n"
                 "Em 60 segundos eu explico. [sem-fato]\n\n<!-- nota: 99% -->\n\n"
                 "## Checklist (confirmado)\n\nTodos os 9 itens passaram em 2026.\n")
        ignoradas = {}
        fr = fatos.frases_do_roteiro(texto, ignoradas)
        self.assertEqual([(f["linha"], f["origem"], f["texto"]) for f in fr if f["origem"] != "texto"],
                         [(1, "titulo", "teste"), (3, "meta", "2 · Crença (45–60s)"), (4, "meta", "45–60s")])
        self.assertEqual(ignoradas, {"comentário": 1, "seção checklist": 1})
        resumo = [(f["linha"], f["texto"], f["ids"], f["dispensada"]) for f in fr if f["origem"] == "texto"]
        self.assertEqual(resumo, [
            (6, "Em 2017 saiu o Transformer.", ["F001"], False),
            (6, "O GPT-4.1 custa US$ 2,00.", ["F002"], False),
            (6, "Segundo Vaswani et al. o modelo dispensa recorrência!", [], False),
            (7, "Ele usa atenção.", [], False),
            (9, "O preço caiu 80%", ["F003", "F004"], False),
            (10, "Você paga 3 vezes mais?", [], False),
            (12, "Em 60 segundos eu explico.", [], True),
        ])

    def test_marcadores(self):
        self.assertEqual(fatos.marcadores_no_texto("a [F001] b [f002, F010] c [F001] [F12] [G001]"), ["F001", "F002", "F010"])


# ----------------------------------------------------------------------------- conferir roteiro
class TestConferirRoteiro(Base):
    def setUp(self):
        super().setUp()
        self.nova()
        div = fato(afirmacao="O Exemplo-1 tem janela de contexto de 400 mil tokens.", valor=400000, unidade="tokens",
                   categoria="modelo", caduca_em="2026-12-05", status="divergente", confianca="media",
                   referente_a="outubro de 2026", notas="A página de modelos diz 400 mil; o blog diz 272 mil de entrada.",
                   fontes=[fonte(titulo="Models", url="https://exemplo.example/models", editor="Exemplo", publicado_em=None,
                                 trecho="400,000 context window"),
                           fonte(titulo="Blog", url="https://exemplo.example/blog", editor="Exemplo Blog",
                                 tipo="secundaria", publicado_em="2026-08-07", trecho="272,000 input tokens")],
                   como_dizer="Em outubro de 2026, a documentação do Exemplo-1 falava em 400 mil tokens de contexto.",
                   termos=["Exemplo-1"])
        self.assertEqual(self.adiciona([fato(), preco(), div]).returncode, 0)
        self.confere_trechos()

    def roteiro(self, texto, nome="roteiro.md"):
        p = self.proj / "roteiro" / nome
        p.write_text(texto, encoding="utf-8")
        return p

    def confere(self, texto, *extra):
        r = self.cli("conferir-roteiro", self.roteiro(texto), "--json", *extra)
        return r, json.loads(r.stdout)

    def tipos(self, rel, chave="pendencias"):
        return sorted(p["tipo"] for p in rel[chave])

    def test_roteiro_limpo_passa(self):
        r, rel = self.confere("## Roteiro: Transformer\n\n**Motor:** 2 · Crença, revelação, implicação\n\n"
                              "Você fala com uma IA todo dia e não sabe de onde ela veio.\n\n"
                              "Em 2017, pesquisadores do Google publicaram o artigo que apresentou o Transformer [F001].\n\n"
                              "Em outubro de 2026, a entrada do Exemplo-1 custava US$ 1,25 por milhão de tokens [F002].\n\n"
                              "Me conta nos comentários o que você quer entender.\n")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertTrue(rel["ok"])
        self.assertEqual((rel["pendencias"], rel["avisos"]), ([], []))
        self.assertEqual(rel["fatos_usados"], ["F001", "F002"])
        self.assertEqual(rel["fatos_nao_usados"], ["F003"])

    def test_frase_checavel_sem_fato(self):
        r, rel = self.confere("O Exemplo-9 acerta 92% das questões de matemática.\n\nIsso custou 3 bilhões de dólares.\n")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.tipos(rel), ["sem_fato", "sem_fato"])
        self.assertEqual([p["linha"] for p in rel["pendencias"]], [1, 3])
        self.assertIn("92% (percentual)", rel["pendencias"][0]["evidencias"])

    def test_numero_que_nao_bate_com_o_fato_citado(self):
        r, rel = self.confere("Em outubro de 2026, a entrada do Exemplo-1 custava US$ 2 por milhão de tokens [F002].\n")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.tipos(rel), ["numero_nao_bate"])
        self.assertIn("US$ 2", rel["pendencias"][0]["detalhe"])
        # o mesmo número escrito de outro jeito bate
        r, rel = self.confere("Em 2026, um milhão de tokens de entrada do Exemplo-1 saía por 1,25 dólar [F002].\n")
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_termos_ensinam_outra_forma_de_dizer(self):
        frase = "Em 2026, um milhão de tokens de entrada do Exemplo-1 saía por um dólar e um quarto [F002].\n"
        r, rel = self.confere(frase)
        self.assertEqual(self.tipos(rel), ["numero_nao_bate"])
        r = self.cli("atualizar", "F002", '{"termos": ["Exemplo-1", "um dólar e um quarto"]}')
        self.assertEqual(r.returncode, 0, r.stderr)
        r, rel = self.confere(frase)
        self.assertEqual((r.returncode, rel["pendencias"]), (0, []))
        # centavos e por extenso já são entendidos sem ajuda: 125 centavos de dólar = US$ 1,25
        r, rel = self.confere("Em 2026, um milhão de tokens de entrada do Exemplo-1 saía por 125 centavos de dólar [F002].\n")
        self.assertEqual((r.returncode, rel["pendencias"]), (0, []))

    def test_marcador_inexistente_status_e_vencido(self):
        r, rel = self.confere("O Exemplo-1 lê 400 mil tokens de uma vez [F003].\n\nIsso muda tudo [F099].\n")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.tipos(rel), ["marcador_inexistente", "status"])
        self.assertIn("divergente", [p for p in rel["pendencias"] if p["tipo"] == "status"][0]["detalhe"])
        r, rel = self.confere("Em outubro de 2026, a entrada do Exemplo-1 custava US$ 1,25 [F002].\n", "--hoje", "2026-11-30")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.tipos(rel), ["vencido"])
        r, rel = self.confere("Em outubro de 2026, a entrada do Exemplo-1 custava US$ 1,25 [F002].\n", "--hoje", "2026-11-01")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.tipos(rel, "avisos"), ["a_vencer"])

    def test_avisos_nao_reprovam_sem_estrito(self):
        texto = ("A OpenAI e a Anthropic disputam esse mercado.\n\n"               # só nomes
                 "Hoje a entrada do Exemplo-1 custa US$ 1,25 [F002].\n\n"          # tempo relativo em fato volátil
                 "Você não precisa de 5 ferramentas, precisa de uma.\n")           # número em fala ao espectador
        r, rel = self.confere(texto)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(self.tipos(rel, "avisos"), ["fala_direta", "so_nomes", "tempo_relativo"])
        r, rel = self.confere(texto, "--estrito")
        self.assertEqual(r.returncode, 1)
        self.assertFalse(rel["ok"])

    def test_dado_sem_marcador_e_pendencia_mesmo_quando_um_fato_parece_cobrir(self):
        r, rel = self.confere("Em 2017 o Google publicou o artigo do Transformer.\n")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.tipos(rel), ["sem_marcador"])
        self.assertEqual(rel["pendencias"][0]["fato_ids"], ["F001"])     # o relatório sugere o fato; não o aplica
        self.assertEqual(rel["fatos_usados"], [])

    def test_cruzamento_nao_cobre_numero_de_outro_assunto(self):
        r, rel = self.confere("Em 2017 eu comprei 1,25 quilo de café no Google.\n")
        self.assertEqual(r.returncode, 1)                                    # 2017 é do F001, 1,25 é do F002: nenhum cobre os dois
        self.assertEqual(self.tipos(rel), ["sem_fato"])

    def test_superlativo_sem_fato_e_dispensa(self):
        r, rel = self.confere("O Exemplo-1 é o melhor modelo do mundo.\n")
        self.assertEqual(r.returncode, 1)
        self.assertIn("superlativo", rel["pendencias"][0]["detalhe"])
        r, rel = self.confere("Em 2 anos você vai rir disso. [sem-fato]\n\nPra mim, o Exemplo-1 é o melhor modelo [opinião].\n")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(len(rel["dispensadas"]), 2)

    def test_modelo_citado_fora_do_fato(self):
        r, rel = self.confere("Em outubro de 2026, a entrada do Exemplo-7 custava US$ 1,25 [F002].\n")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.tipos(rel), ["modelo_fora_do_fato"])

    def test_arquivos_com_bom_e_crlf(self):
        p = self.proj / "roteiro" / "do windows.md"
        p.write_bytes("\ufeff## Roteiro: de onde veio\r\n\r\nEm 2017 saiu o Transformer [F001].\r\nO Exemplo-9 acerta 92%.\r\n".encode("utf-8"))
        r = self.cli("conferir-roteiro", p, "--json")
        rel = json.loads(r.stdout)
        self.assertEqual([(x["tipo"], x["linha"]) for x in rel["pendencias"]], [("sem_fato", 4)])
        self.assertEqual((rel["frases"], rel["titulos_e_metadados"]), (2, 1))   # o BOM não estragou o título
        novo = self.proj / "pesquisa" / "_com bom.json"
        novo.write_bytes(b"\xef\xbb\xbf" + json.dumps(fato(afirmacao="A sigla GPT apareceu no artigo da OpenAI de 2018."),
                                                       ensure_ascii=False).encode("utf-8"))
        self.assertEqual(self.cli("adicionar", "@" + str(novo)).returncode, 0)

    def test_saida_humana_e_arquivo(self):
        p = self.roteiro("O Exemplo-9 acerta 92% das questões.\n\nEm 2017 saiu o Transformer [F001].\n", "roteiro v2 final.md")
        saida = self.proj / "pesquisa" / "_conferência.json"
        r = self.cli("conferir-roteiro", p, "--saida", saida)
        self.assertEqual(r.returncode, 1)
        self.assertIn("PENDÊNCIAS", r.stdout)
        self.assertIn("[sem fato] linha 1", r.stdout)
        self.assertIn("RESULTADO: 1 pendência, 0 avisos → REPROVADO", r.stdout)
        self.assertEqual(json.loads(saida.read_text(encoding="utf-8"))["pendencias"][0]["tipo"], "sem_fato")
        r = self.cli("conferir-roteiro", "roteiro/nao existe.md")
        self.assertEqual(r.returncode, 64)
        self.assertIn("roteiro não encontrado", r.stderr)


# ----------------------------------------------------------------------------- storyboard
class TestStoryboard(Base):
    def test_conferir_storyboard(self):
        self.nova()
        nao = fato(afirmacao="O Exemplo-2 teria 1 trilhão de parâmetros.", status="nao_confirmado", confianca="baixa",
                   valor=None, fontes=[], como_dizer="")
        self.assertEqual(self.adiciona([fato(), preco(), nao]).returncode, 0)
        self.confere_trechos()
        sb = {"versao": 1, "cenas": [
            {"id": "C01", "trecho": "Em 2017…", "t0": None, "dur": 5, "cena": "citacao", "params": {"texto": "x", "fonte": "arXiv, jun/2017"},
             "formatos": ["horizontal"], "fato_ids": ["F001"], "broll_id": None, "saida": "animacoes/C01"},
            {"id": "C02", "trecho": "custa US$ 1,25", "dur": 6, "cena": "barras", "params": {"dados": []}, "fato_ids": ["F002"]},
            {"id": "C03", "trecho": "x", "dur": 6, "cena": "barras", "params": {"fonte": "Fonte: Exemplo, out/2026"}, "fato_ids": ["F002"]},
            {"id": "C04", "trecho": "x", "dur": 4, "cena": "titulo", "params": {}, "fato_ids": ["F003", "F077"]},
            {"id": "C05", "trecho": "O modelo acerta 92% das questões", "dur": 4, "cena": "titulo", "params": {}, "fato_ids": []},
        ]}
        self.grava_json("roteiro/storyboard.json", sb)
        r = self.cli("conferir-storyboard", "--json")
        rel = json.loads(r.stdout)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(sorted(p["tipo"] for p in rel["pendencias"]), ["marcador_inexistente", "sem_fato", "status"])
        self.assertEqual(sorted(a["tipo"] for a in rel["avisos"]), ["prefixo_duplicado", "sem_credito"])
        self.assertEqual(rel["cenas"][0], {"id": "C01", "fato_ids": ["F001"], "credito": "arXiv, jun/2017"})
        sb["cenas"] = sb["cenas"][:1]
        self.grava_json("roteiro/storyboard.json", sb)
        r = self.cli("conferir-storyboard")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn('C01: F001 → params.fonte = "arXiv, jun/2017"', r.stdout)
        (self.proj / "roteiro" / "storyboard.json").unlink()
        self.assertEqual(self.cli("conferir-storyboard").returncode, 64)


# ----------------------------------------------------------------------------- links (sem rede externa)
class _Manipulador(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        if self.path == "/ok":
            corpo = ("<html><head><style>p{color:red}</style></head><body><h1>Pre&ccedil;os</h1>"
                     "<p>Input: <b>$1.25</b> / 1M tokens</p><script>var x='só no script 9.99';</script></body></html>")
            dados = corpo.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(dados)))
            self.end_headers()
            self.wfile.write(dados)
        elif self.path == "/pdf":
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Length", "4")
            self.end_headers()
            self.wfile.write(b"%PDF")
        elif self.path == "/mudou":
            self.send_response(301)
            self.send_header("Location", "/ok")
            self.end_headers()
        elif self.path == "/laco":
            self.send_response(302)
            self.send_header("Location", "/laco")
            self.end_headers()
        elif self.path == "/cookie":                                 # como ai.google.dev: só serve a quem devolve o cookie
            if "visto=1" in (self.headers.get("Cookie") or ""):
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", "2")
                self.end_headers()
                self.wfile.write(b"ok")
            else:
                self.send_response(302)
                self.send_header("Set-Cookie", "visto=1; Path=/")
                self.send_header("Location", "/cookie")
                self.end_headers()
        elif self.path == "/lento":
            import time
            time.sleep(1.5)
            self.send_response(200)
            self.end_headers()
        else:
            codigo = {"/sumiu": 404, "/foi": 410, "/robo": 403, "/muitos": 429, "/caiu": 503, "/recusou": 400,
                      "/desafio": 202}.get(self.path, 404)
            self.send_response(codigo)
            self.send_header("Content-Length", "0")
            self.end_headers()

    def log_message(self, *a):
        pass


class TestLinks(Base):
    @classmethod
    def setUpClass(cls):
        cls.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Manipulador)
        cls.base = f"http://127.0.0.1:{cls.srv.server_address[1]}"
        cls.fio = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.fio.start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def test_estados_http(self):
        casos = {"/ok": ("ok", 200), "/sumiu": ("quebrado", 404), "/foi": ("quebrado", 410), "/robo": ("bloqueado", 403),
                 "/muitos": ("bloqueado", 429), "/caiu": ("erro_servidor", 503), "/mudou": ("redirecionado", 200),
                 "/recusou": ("bloqueado", 400), "/desafio": ("bloqueado", 202)}
        for caminho, (estado, http_) in casos.items():
            r = fatos.checar_url(self.base + caminho, prazo=5)
            self.assertEqual((r["estado"], r["http"]), (estado, http_), caminho)
        r = fatos.checar_url(self.base + "/mudou", prazo=5)
        self.assertTrue(r["final"].endswith("/ok"))
        self.assertIn("troque o endereço", r["detalhe"])

    def test_laco_de_redirecionamento_e_cookie(self):
        r = fatos.checar_url(self.base + "/laco", prazo=5)
        self.assertEqual(r["estado"], "bloqueado")
        self.assertIn("navegador", r["detalhe"])
        r = fatos.checar_url(self.base + "/cookie", prazo=5)
        self.assertEqual((r["estado"], r["http"]), ("ok", 200), r)

    def test_tempo_esgotado_e_conexao_recusada_nao_levantam(self):
        r = fatos.checar_url(self.base + "/lento", prazo=0.4)
        self.assertEqual(r["estado"], "sem_resposta")
        self.assertIn("sem resposta em 0.4 s", r["detalhe"])
        r = fatos.checar_url("http://127.0.0.1:9/nada", prazo=2)
        self.assertEqual(r["estado"], "sem_resposta")
        r = fatos.checar_url("isto não é url", prazo=2)
        self.assertEqual(r["estado"], "sem_resposta")

    def test_trechos(self):
        t = ("Input: $1.25 / 1M tokens", "Input: $9.99 / 1M tokens", "só no script 9.99", "Preços")
        r = fatos.checar_url(self.base + "/ok", prazo=5, trechos=t)
        self.assertEqual(r["trechos"][t[0]], "encontrado")
        self.assertTrue(r["trechos"][t[1]].startswith("ausente"))
        self.assertEqual(r["trechos"][t[2]], "encontrado (no código da página)")
        self.assertEqual(r["trechos"][t[3]], "encontrado")
        r = fatos.checar_url(self.base + "/pdf", prazo=5, trechos=("qualquer",))
        self.assertTrue(r["trechos"]["qualquer"].startswith("nao_verificado"))

    def _ficha(self):
        f = fatos.nova_ficha("t", HOJE)
        fatos.adicionar(f, fato(), HOJE)
        fatos.adicionar(f, preco(), HOJE)
        fatos.adicionar(f, fato(afirmacao="O Transformer dispensa recorrência e convoluções.", categoria="conceito"), HOJE)
        return f

    def test_checar_links_agrega_sem_derrubar(self):
        estados = {"https://arxiv.org/abs/1706.03762": "ok", "https://exemplo.example/pricing": "quebrado"}

        def falso(url, prazo, trechos=()):
            if url.endswith("pricing"):
                raise RuntimeError("explodiu")                       # um link ruim não derruba os outros
            return {"url": url, "estado": estados[url], "http": 200, "final": None, "detalhe": "", "trechos": {}}

        rel = fatos.checar_links(self._ficha(), checar=falso, sonda=lambda: True)
        self.assertEqual(rel["urls"], 2)                             # arXiv aparece em dois fatos: uma requisição só
        self.assertEqual(rel["resultados"][0]["usos"], ["F001#1", "F003#1"])
        self.assertEqual(rel["contagem"], {"ok": 1, "sem_resposta": 1})
        self.assertFalse(rel["ok"])
        self.assertFalse(rel["sem_rede"])

    def test_sem_rede_e_diferente_de_link_quebrado(self):
        morto = lambda url, prazo, trechos=(): {"url": url, "estado": "sem_resposta", "http": None, "final": None,  # noqa: E731
                                                "detalhe": "o domínio não resolve (DNS)", "trechos": {}}
        self.assertTrue(fatos.checar_links(self._ficha(), checar=morto, sonda=lambda: False)["sem_rede"])
        rel = fatos.checar_links(self._ficha(), checar=morto, sonda=lambda: True)
        self.assertFalse(rel["sem_rede"])
        self.assertFalse(rel["ok"])
        bloq = lambda url, prazo, trechos=(): {"url": url, "estado": "bloqueado", "http": 403, "final": None,  # noqa: E731
                                               "detalhe": "", "trechos": {}}
        self.assertTrue(fatos.checar_links(self._ficha(), checar=bloq, sonda=lambda: True)["ok"])   # bloqueado ≠ quebrado
        # trecho ausente reprova o conjunto; trecho encontrado, não
        rel = fatos.checar_links(self._ficha(), com_trechos=True, checar=checar_falso(trecho="ausente (…)"), sonda=lambda: True)
        self.assertEqual((rel["ok"], rel["trechos_ausentes"]), (False, 2))     # 3 fatos, 2 pares (url, trecho)
        rel = fatos.checar_links(self._ficha(), com_trechos=True, checar=checar_falso(), sonda=lambda: True)
        self.assertEqual((rel["ok"], rel["trechos_ausentes"]), (True, 0))
        rel = fatos.checar_links(self._ficha(), ids=["F002"], checar=bloq, sonda=lambda: True)
        self.assertEqual(rel["urls"], 1)

    def test_urls_de_texto_e_mapa(self):
        texto = ("| OpenAI | https://a.example/x | nota |\nVeja (https://b.example/y), <https://c.example/z>. "
                 "Repetida: https://a.example/x e http://d.example/w?q=1#frag.")
        self.assertEqual(fatos.urls_de_texto(texto), ["https://a.example/x", "https://b.example/y", "https://c.example/z",
                                                      "http://d.example/w?q=1#frag"])
        ok = lambda url, prazo, trechos=(): {"url": url, "estado": "ok", "http": 200, "final": None, "detalhe": "",  # noqa: E731
                                             "trechos": {}}
        rel = fatos.checar_mapa({u: {} for u in fatos.urls_de_texto(texto)}, checar=ok, sonda=lambda: True)
        self.assertEqual((rel["urls"], rel["ok"], rel["contagem"]), (4, True, {"ok": 4}))

    def test_cli_arquivo_sem_ficha(self):
        lista = self.proj / "lista de links.md"
        lista.write_text(f"- [vivo]({self.base}/ok)\n- morto: {self.base}/sumiu\n- robô: {self.base}/robo\n", encoding="utf-8")
        r = self.cli("checar-links", "--arquivo", lista, "--prazo", "5")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)          # tem um 404
        self.assertIn("3 URLs: 1 bloqueado, 1 ok, 1 quebrado", r.stdout)
        self.assertIn("bloqueado ≠ quebrado", r.stdout)
        self.assertFalse((self.proj / "pesquisa").exists())             # não exige nem cria ficha
        lista.write_text("sem links aqui\n", encoding="utf-8")
        self.assertIn("nenhuma URL encontrada", self.cli("checar-links", "--arquivo", lista).stdout)
        self.assertEqual(self.cli("checar-links", "--arquivo", lista, "--trechos").returncode, 64)
        self.assertEqual(self.cli("checar-links", "--arquivo", "nao existe.md").returncode, 64)

    def test_cli_sem_rede_sai_com_75(self):
        self.nova()
        self.assertEqual(self.adiciona([fato(), preco()]).returncode, 0)
        desligado = ("import socket, sys\n"
                     "def cai(*a, **k): raise OSError('rede desligada no teste')\n"
                     "socket.create_connection = cai; socket.getaddrinfo = cai\n"
                     "sys.path.insert(0, sys.argv[1]); import fatos\n"
                     "sys.exit(fatos.main(['checar-links', '--prazo', '2']))")
        r = subprocess.run([sys.executable, "-B", "-c", desligado, str(SCRIPTS)], cwd=str(self.proj), capture_output=True,
                           text=True, env=self.env, timeout=60)
        self.assertEqual(r.returncode, 75, r.stdout + r.stderr)
        self.assertIn("SEM REDE", r.stderr)
        self.assertNotIn("Traceback", r.stderr)
        self.assertIn("2 URLs: 2 sem_resposta", r.stdout)

    def test_cli_sem_fontes(self):
        self.nova()
        r = self.cli("checar-links")
        self.assertEqual(r.returncode, 0)
        self.assertIn("nenhuma URL", r.stdout)
        self.assertEqual(self.cli("checar-links", "--prazo", "0").returncode, 64)


# ----------------------------------------------------------------------------- integração com a DA (kit)
def _tem_pil():
    try:
        import PIL  # noqa: F401
        import numpy  # noqa: F401
        return True
    except ImportError:
        return False


class TestCaberSemPillow(Base):
    @unittest.skipIf(_tem_pil() or not (KIT / "da.py").is_file(), "só faz sentido num Python sem Pillow")
    def test_mensagem_acionavel(self):
        self.nova()
        self.assertEqual(self.adiciona(fato()).returncode, 0)
        self.confere_trechos()
        r = self.cli("credito", "F001", "--caber", "horizontal")
        self.assertEqual(r.returncode, 1)
        self.assertIn("Pillow", r.stderr)


@unittest.skipUnless((KIT / "da.py").is_file() and _tem_pil(), "precisa do kit de direção de arte ao lado e de Pillow/numpy")
class TestCreditoCabeNaDA(Base):
    def test_caber(self):
        antes = sorted(p.name for p in KIT.rglob("__pycache__/*"))
        self.addCleanup(lambda: self.assertEqual(sorted(p.name for p in KIT.rglob("__pycache__/*")), antes,
                                                 "o teste não pode escrever __pycache__ dentro do kit"))
        self.nova()
        longo = fato(afirmacao="O placar independente mede modelos em tarefas de programação desde 2024.",
                     categoria="conceito", referente_a="2024",
                     fontes=[fonte(editor="Instituto Internacional de Avaliação", url="https://x.example/y")])
        self.assertEqual(self.adiciona([fato(), longo]).returncode, 0)
        self.confere_trechos()
        r = self.cli("credito", "F001", "--caber", "horizontal")
        self.assertEqual(r.returncode, 2, r.stderr)                  # projeto ainda sem DA: avisa e não inventa medida
        self.assertIn("direção de arte", r.stderr)
        ini = subprocess.run([sys.executable, "-B", str(KIT / "da.py"), "init", str(self.proj), "--nome", "Teste",
                              "--base", "lab-ia"], capture_output=True, text=True, env=self.env, timeout=120)
        self.assertEqual(ini.returncode, 0, ini.stderr)
        r = self.cli("credito", "F001", "--caber", "vertical", "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        m = json.loads(r.stdout)["medida"]
        self.assertTrue(m["cabe"])
        self.assertGreater(m["largura_px"], 50)
        self.assertGreater(m["largura_util_px"], m["largura_px"])
        self.assertEqual(m["formato"], "vertical")
        self.assertEqual(m["texto_na_tela"], "Fonte: arXiv, jun/2017")      # corpo + prefixo da DA, sem duplicar
        r = self.cli("credito", "F001", "--caber", "vertical")
        self.assertIn("“Fonte: arXiv, jun/2017” mede", r.stderr)
        estreito = subprocess.run([sys.executable, "-B", "-c", (
            "import sys; sys.path.insert(0, sys.argv[1]); import fatos\n"
            "m = fatos.medir_credito('Fonte: ' + 'Instituto Internacional de Avaliação de Modelos, ' * 4 + 'out/2026', "
            "sys.argv[2], 'vertical'); print(m['cabe'])"), str(SCRIPTS), str(self.proj)],
            capture_output=True, text=True, env=self.env, timeout=120)
        self.assertEqual(estreito.stdout.strip(), "False", estreito.stderr)
        r = self.cli("credito", "F002", "--caber", "formato-que-nao-existe")
        self.assertEqual(r.returncode, 64, r.stderr)
        self.assertIn("formato", r.stderr)


if __name__ == "__main__":
    unittest.main()
