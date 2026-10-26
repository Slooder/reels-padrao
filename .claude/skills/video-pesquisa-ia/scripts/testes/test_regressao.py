# -*- coding: utf-8 -*-
"""Regressões dos defeitos achados na revisão independente de 2026-10-06 (sem rede).

Rodar a partir de scripts/:   python3 -B -m unittest testes.test_regressao

Cada classe leva o nome do defeito que impede de voltar. Dados fictícios (Exemplo-1, exemplo.example).
"""
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

try:
    import fcntl
except ImportError:                                               # Windows: a trava usa msvcrt; o teste da trava é POSIX
    fcntl = None

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
from apoio import (Base, FATOS_PY, HOJE, SKILL, ServidorLocal, conferido, fato, fatos, fonte, mensagens,  # noqa: E402
                   preco)


def preco_com_datas(**k):
    """Preço cujo texto está cheio de OUTROS números: datas, um aumento anunciado, o dia 31 no trecho."""
    base = preco(
        afirmacao="Em outubro de 2026, a tabela oficial da Exemplo cobrava US$ 0,75 por milhão de tokens de entrada no "
                  "Exemplo Flash 3.8, com aumento anunciado para US$ 1,50 em 1º de janeiro de 2027.",
        valor=0.75, referente_a="2026-10-06 (tabela atualizada em 2026-10-01)",
        fontes=[fonte(titulo="Pricing", url="https://exemplo.example/pricing", editor="Exemplo", publicado_em="2026-10-01",
                      trecho="$0.75 through December 31, 2026. $1.50 starting January 1, 2027.")],
        como_dizer="Em outubro de 2026, 1 milhão de tokens de entrada no Exemplo Flash 3.8 custava US$ 0,75 na tabela "
                   "oficial da Exemplo.",
        termos=["Exemplo Flash 3.8"])
    base.update(k)
    return base


def autores(**k):
    base = fato(afirmacao="O artigo que apresentou o Transformer foi enviado ao arXiv em 12 de junho de 2017 e é assinado "
                          "por 8 autores.", valor=8, unidade="autores", referente_a="junho de 2017",
                como_dizer="Em junho de 2017, oito pesquisadores publicaram o artigo que apresentou o Transformer.",
                termos=["Transformer"])
    base.update(k)
    return base


def janela(**k):
    base = fato(afirmacao="Em outubro de 2026, a tabela de modelos da Exemplo listava janela de contexto de 1M de tokens e "
                          "saída máxima de 128K tokens para o Exemplo Opus 5.5.",
                valor=1000000, unidade="tokens de janela de contexto", referente_a="2026-10-06", categoria="modelo",
                caduca_em="2026-12-05",
                fontes=[fonte(titulo="Models", url="https://exemplo.example/models", editor="Exemplo", publicado_em=None,
                              trecho="1M tokens")],
                como_dizer="Em outubro de 2026, segundo a documentação da Exemplo, o Exemplo Opus 5.5 lia até 1 milhão de "
                           "tokens de uma vez.", termos=["Exemplo Opus 5.5"])
    base.update(k)
    return base


class ComFicha(Base):
    FATOS = ()

    def setUp(self):
        super().setUp()
        self.nova()
        if self.FATOS:
            r = self.adiciona([f() for f in self.FATOS])
            self.assertEqual(r.returncode, 0, r.stderr)
            self.confere_trechos()

    def confere(self, texto, *extra, nome="roteiro.md"):
        p = self.proj / "roteiro" / nome
        p.write_text(texto, encoding="utf-8")
        r = self.cli("conferir-roteiro", p, "--json", *extra)
        return r, json.loads(r.stdout)

    def tipos(self, rel, chave="pendencias"):
        return sorted(p["tipo"] for p in rel[chave])


# ============================================================ achado 1: o saco de números
class TestNumeroComparadoPorTipo(ComFicha):
    """Antes, qualquer número do fato (pedaço de data, dia do trecho, "1º de janeiro") validava qualquer número da
    frase: "US$ 6", "US$ 10" e "US$ 31" passavam contra um fato de US$ 0,75 por causa de "2026-10-06" e "December 31"."""
    FATOS = (preco_com_datas, autores, janela, preco)

    FRASE = "Em outubro de 2026, 1 milhão de tokens de entrada no Exemplo Flash 3.8 custava US$ {} na tabela oficial da Exemplo [F001].\n"

    def test_preco_errado_com_marcador_e_pendencia(self):
        r, rel = self.confere(self.FRASE.format("0,75"))
        self.assertEqual((r.returncode, rel["pendencias"]), (0, []), r.stdout)
        for errado in ("6", "10", "31", "1", "2026", "7,50", "0,50", "75"):
            r, rel = self.confere(self.FRASE.format(errado), "--estrito")
            self.assertEqual(r.returncode, 1, errado)
            self.assertEqual(self.tipos(rel), ["numero_nao_bate"], errado)

    def test_outro_dado_da_afirmacao_nao_valida_a_frase(self):
        # US$ 1,50 está na afirmacao (aumento anunciado), não é o valor nem está em como_dizer: é OUTRO dado
        r, rel = self.confere(self.FRASE.format("1,50"))
        self.assertEqual(self.tipos(rel), ["numero_nao_bate"])
        self.assertIn("OUTRO dado", rel["pendencias"][0]["detalhe"])
        # quando o como_dizer passa a dizer esse dado, o roteiro pode dizê-lo
        r = self.cli("atualizar", "F001", "--como-dizer", "Em outubro de 2026, 1 milhão de tokens de entrada no Exemplo "
                     "Flash 3.8 custava US$ 0,75, com aumento anunciado para US$ 1,50 em janeiro de 2027.")
        self.assertEqual(r.returncode, 0, r.stderr)
        r, rel = self.confere("Em outubro de 2026, o Exemplo Flash 3.8 custava US$ 0,75 por milhão de tokens de entrada e "
                              "o aumento anunciado para janeiro de 2027 era para US$ 1,50 [F001].\n")
        self.assertEqual(rel["pendencias"], [], r.stdout)

    def test_dia_da_data_nao_vira_contagem(self):
        ok = ("Em junho de 2017, 8 pesquisadores publicaram o artigo que apresentou o Transformer [F002].\n",
              "Em junho de 2017, oito pesquisadores publicaram o artigo que apresentou o Transformer [F002].\n",
              "Em 12 de junho de 2017, 8 autores enviaram ao arXiv o artigo que apresentou o Transformer [F002].\n")
        for frase in ok:
            r, rel = self.confere(frase)
            self.assertEqual(rel["pendencias"], [], frase)
        for frase in ("Em junho de 2017, 12 pesquisadores publicaram o artigo que apresentou o Transformer [F002].\n",
                      "Em junho de 2018, oito pesquisadores publicaram o artigo que apresentou o Transformer [F002].\n",
                      "Em julho de 2017, oito pesquisadores publicaram o artigo que apresentou o Transformer [F002].\n",
                      "Em 13 de junho de 2017, 8 autores enviaram ao arXiv o artigo do Transformer [F002].\n"):
            r, rel = self.confere(frase)
            self.assertEqual(self.tipos(rel), ["numero_nao_bate"], frase)

    def test_moeda_centavos_e_ordem_de_grandeza(self):
        base = "Em outubro de 2026, a entrada do Exemplo-1 custava {} por milhão de tokens [F004].\n"
        for certo in ("US$ 1,25", "1,25 dólar", "125 centavos de dólar"):
            self.assertEqual(self.confere(base.format(certo))[1]["pendencias"], [], certo)
        for errado in ("R$ 1,25", "1,25 centavo", "US$ 1,25 mil", "US$ 12,5", "€ 1,25"):
            self.assertEqual(self.tipos(self.confere(base.format(errado))[1]), ["numero_nao_bate"], errado)

    def test_numero_de_outro_campo_do_mesmo_fato(self):
        # 128 mil está na afirmacao do F003 como OUTRA medida (saída); a janela (valor) é 1 milhão
        r, rel = self.confere("Em outubro de 2026, o Exemplo Opus 5.5 lia até 128 mil tokens de uma vez [F003].\n")
        self.assertEqual(self.tipos(rel), ["numero_nao_bate"])
        r, rel = self.confere("Em outubro de 2026, o Exemplo Opus 5.5 lia até 1 milhão de tokens de uma vez [F003].\n")
        self.assertEqual(rel["pendencias"], [])

    def test_indice_do_fato_separa_papeis(self):
        ix = fatos.indexar_fato(dict(preco_com_datas(), id="F001"))
        fortes = {v for it in ix["fortes"] for v in it["valores"]}
        self.assertIn(0.75, fortes)
        for intruso in (6.0, 10.0, 31.0, 2027.0, 1.5):
            self.assertNotIn(intruso, fortes)
        self.assertEqual(ix["valor_tipo"], "dinheiro")
        self.assertEqual({it["tipo"] for it in ix["trecho"]}, {"dinheiro", "data"})

    def test_entrada_x_saida_e_grandeza(self):
        casos = {
            "Em outubro de 2026, 1 milhão de tokens de saída no Exemplo-1 custava US$ 1,25 [F004].\n": "entrada_saida",
            "Em outubro de 2026, o Exemplo Opus 5.5 escrevia até 1 milhão de tokens por resposta [F003].\n": "entrada_saida",
            "Em outubro de 2026, o Exemplo Opus 5.5 lia até 1 milhão de palavras de uma vez [F003].\n": "unidade_nao_bate",
            "Em outubro de 2026, a entrada do Exemplo-1 custava US$ 1,25 por mês [F004].\n": "unidade_nao_bate",
        }
        for frase, tipo in casos.items():
            r, rel = self.confere(frase)
            self.assertEqual(r.returncode, 1, frase)
            self.assertIn(tipo, self.tipos(rel), frase)
        # a frase que fala dos dois lados não é acusada
        r, rel = self.confere("Em outubro de 2026, o Exemplo Opus 5.5 lia até 1 milhão de tokens antes de escrever a "
                              "resposta [F003].\n")
        self.assertEqual(rel["pendencias"], [], r.stdout)


# ============================================================ achado 2: número por extenso
class TestNumeroPorExtenso(ComFicha):
    FATOS = (preco,)

    def test_extenso_vale_o_mesmo_que_digitos(self):
        casos = {
            "criado em dois mil e dezessete": [("ano", [2017.0])],
            "assinado por oito pesquisadores da empresa": [("numero", [8.0])],
            "Noventa por cento das empresas": [("percentual", [90.0])],
            "custou cem milhões de dólares": [("dinheiro", [1e8])],
            "Três em cada quatro programadores": [("proporcao", [0.75])],
            "é de um milhão de tokens": [("numero", [1e6])],
            "tem um trilhão de parâmetros": [("numero", [1e12])],
            "caiu pela metade": [("proporcao", [0.5])],
            "custava nove dólares": [("dinheiro", [9.0])],
            "vinte e cinco centavos de dólar": [("dinheiro", [0.25])],
            "um milhão e meio de usuários": [("numero", [1.5e6])],
            "ficou duas vezes mais rápido": [("proporcao", [2.0])],
            "o custo caiu dez vezes": [("proporcao", [10.0])],
            "dois terços das empresas": [("proporcao", [2 / 3])],
            "quatrocentos e cinco bilhões de parâmetros": [("numero", [405e9])],
        }
        for texto, esperado in casos.items():
            vistos = [(i["tipo"], i["valores"]) for i in fatos.extrair_numeros(texto)]
            self.assertEqual(vistos, esperado, texto)
        d = fatos.extrair_numeros("enviado em doze de junho de 2017")[0]
        self.assertEqual((d["tipo"], d["dia"], d["mes"], d["ano"]), ("data", 12, 6, 2017))
        self.assertEqual(fatos.extrair_numeros("nove dólares")[0]["moeda"], "USD")

    def test_o_que_por_extenso_nao_e_dado(self):
        for texto in ("por milhão de tokens", "uma coisa de cada vez", "os dois modelos erram", "um deles é o Exemplo-1",
                      "três motivos para testar", "em dez segundos eu explico"):
            self.assertEqual(fatos.extrair_numeros(texto), [], texto)

    def test_preco_errado_por_extenso_reprova(self):
        r, rel = self.confere("Em outubro de 2026, 1 milhão de tokens de entrada no Exemplo-1 custava nove dólares [F001].\n",
                              "--estrito")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.tipos(rel), ["numero_nao_bate"])
        self.assertIn("nove dólares", rel["pendencias"][0]["detalhe"])

    def test_frases_por_extenso_sem_marcador_sao_pendencia(self):
        frases = ("Noventa por cento das empresas já usam IA.", "O treinamento custou cem milhões de dólares.",
                  "A janela de contexto é de um milhão de tokens.", "Três em cada quatro programadores usam IA.",
                  "O preço caiu pela metade em um ano.", "O Exemplo-5 tem um trilhão de parâmetros.",
                  "O Transformer foi criado em dois mil e dezessete por oito pesquisadores.")
        for frase in frases:
            r, rel = self.confere(frase + "\n")
            self.assertEqual(r.returncode, 1, frase)
            self.assertTrue(rel["pendencias"], frase)

    def test_limite_conhecido_um_sozinho(self):
        """"um"/"uma" sozinhos (sem escala, sem moeda) não são lidos como número — documentado em metodo.md §15."""
        r, rel = self.confere("O sistema roda num data center de um gigawatt.\n")
        self.assertEqual((r.returncode, rel["pendencias"]), (0, []))


# ============================================================ achado 3: dado inventado atravessava os portões
class TestTrechoConferido(ServidorLocal, Base):
    INVENTADO = dict(preco(), valor=2, afirmacao="A entrada do modelo Exemplo-1 custa US$ 2 por milhão de tokens na API.",
                     como_dizer="Em outubro de 2026, a entrada do Exemplo-1 custava US$ 2 por milhão de tokens.",
                     caduca_em=None)
    ROTEIRO = "Em outubro de 2026, a entrada do Exemplo-1 custava US$ 2 por milhão de tokens [F001].\n"

    def _inventa(self):
        self.nova()
        dado = json.loads(json.dumps(self.INVENTADO))
        dado["fontes"][0]["trecho"] = "Exemplo-1 costs $2 per million input tokens"
        del dado["fontes"][0]["acessado_em"]
        r = self.adiciona(dado, "--acessado-hoje", "--caduca-padrao")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("ainda não conferido", r.stdout)                   # o próprio adicionar já avisa
        (self.proj / "roteiro" / "roteiro.md").write_text(self.ROTEIRO, encoding="utf-8")

    def test_fato_nunca_conferido_nao_passa_no_portao_final(self):
        self._inventa()
        self.assertEqual(self.cli("validar").returncode, 0)             # válido no formato…
        r = self.cli("validar", "--estrito")
        self.assertEqual(r.returncode, 1)                                # …mas sem prova de leitura
        self.assertIn("ainda não conferido", r.stdout)
        r = self.cli("conferir-roteiro", "roteiro/roteiro.md", "--estrito")
        self.assertEqual(r.returncode, 1)
        self.assertIn("[não conferido]", r.stdout)
        r = self.cli("credito", "F001")
        self.assertEqual((r.returncode, r.stdout), (1, ""))
        j = json.loads(self.cli("resumo", "--json").stdout)
        self.assertEqual((j["trechos"]["nunca"], j["sem_conferencia"]), (1, ["F001"]))
        self.assertIn("! F001", self.cli("resumo").stdout)

    def test_trecho_ausente_reprova_tudo(self):
        self._inventa()
        cont = self.confere_trechos(trecho="ausente (o HTML baixado não contém o trecho)")
        self.assertEqual(cont["ausente"], 1)
        r = self.cli("validar", "--estrito")
        self.assertEqual(r.returncode, 1)
        self.assertIn("TRECHO AUSENTE", r.stdout)
        r = self.cli("conferir-roteiro", "roteiro/roteiro.md")           # nem precisa de --estrito
        self.assertEqual(r.returncode, 1)
        self.assertIn("[trecho ausente]", r.stdout)
        r = self.cli("credito", "F001")
        self.assertEqual(r.returncode, 1)
        self.assertIn("NÃO achou o trecho", r.stderr)
        self.assertIn("1 AUSENTE(S)", self.cli("resumo").stdout)
        self.grava_json("roteiro/storyboard.json", {"versao": 1, "cenas": [
            {"id": "C01", "trecho": "custava US$ 2", "dur": 5, "cena": "barras", "params": {"fonte": "Exemplo, out/2026"},
             "fato_ids": ["F001"]}]})
        r = self.cli("conferir-storyboard", "--json")
        self.assertEqual(r.returncode, 1)
        self.assertEqual([p["tipo"] for p in json.loads(r.stdout)["pendencias"]], ["trecho_ausente"])

    def test_conferencia_vale_para_o_par_url_trecho(self):
        self._inventa()
        self.confere_trechos()
        self.assertEqual(self.cli("validar", "--estrito").returncode, 0)
        self.assertEqual(self.cli("credito", "F001").stdout.strip(), "Fonte: Exemplo, out/2026")
        nova = dict(self.ficha()["fatos"][0]["fontes"][0], trecho="Input: $2.00 / 1M tokens")
        nova.pop("conferencia")
        r = self.cli("atualizar", "F001", json.dumps({"fontes": [nova]}))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("conferencia", self.ficha()["fatos"][0]["fontes"][0])   # trecho novo: prova velha não vale
        self.assertEqual(self.cli("validar", "--estrito").returncode, 1)
        # mudar outra coisa (notas) não derruba a conferência
        self.confere_trechos()
        self.assertEqual(self.cli("atualizar", "F001", "--notas", "conferido").returncode, 0)
        self.assertEqual(self.ficha()["fatos"][0]["fontes"][0]["conferencia"]["estado"], "encontrado")

    def test_conferencia_nao_entra_pelo_json_do_usuario(self):
        self.nova()
        forjado = conferido(preco())
        r = self.adiciona(forjado)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("conferencia", self.ficha()["fatos"][0]["fontes"][0])
        s = dict(forjado["fontes"][0], trecho="Input: $1.25 / 1M tokens!")
        s["conferencia"]["marca"] = fatos.marca_da_fonte(s)
        self.assertEqual(self.cli("atualizar", "F001", json.dumps({"fontes": [s]})).returncode, 0)
        self.assertNotIn("conferencia", self.ficha()["fatos"][0]["fontes"][0])

    def test_conferencia_manual_exige_nota_e_fica_registrada(self):
        self._inventa()
        r = self.cli("atualizar", "F001", "--conferido-manual", "vi")
        self.assertEqual(r.returncode, 64)
        r = self.cli("atualizar", "F001", "--conferido-manual", "aberta no navegador; linha do Exemplo-1 na tabela de preços")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.cli("validar", "--estrito").returncode, 0)
        self.assertEqual(self.cli("md").returncode, 0)
        fm = (self.proj / "pesquisa" / "fatos.md").read_text(encoding="utf-8")
        self.assertIn("conferência manual declarada em 06/10/2026: aberta no navegador", fm)
        # um "ausente" automático do mesmo dia não apaga a leitura declarada (página montada por JavaScript)
        cont = self.confere_trechos(trecho="ausente (…)")
        self.assertEqual((cont["manual_mantida"], cont["ausente"]), (1, 0))
        self.assertEqual(self.ficha()["fatos"][0]["fontes"][0]["conferencia"]["estado"], "manual")

    def test_conferencia_manual_so_cai_com_evidencia_nova(self):
        ontem = "2026-10-05"

        def manual_de_ontem(robo):
            f = fatos.nova_ficha("t", HOJE)
            fatos.adicionar(f, preco(), HOJE)
            s = f["fatos"][0]["fontes"][0]
            s["conferencia"] = {"estado": "manual", "em": ontem, "metodo": "declarada", "robo": robo,
                                "nota": "aberta no navegador; linha do Exemplo-1", "marca": fatos.marca_da_fonte(s)}
            return f

        def roda(f, estado, trecho):
            from apoio import checar_falso
            rel = fatos.checar_links(f, com_trechos=True, checar=checar_falso(estado, 200, trecho), sonda=lambda: True)
            fatos.registrar_conferencias(f, rel, HOJE)
            return f["fatos"][0]["fontes"][0]["conferencia"]["estado"]

        # o robô continua barrado: nada de novo, a leitura declarada fica (fato histórico não exige redeclarar todo dia)
        self.assertEqual(roda(manual_de_ontem("nao_verificado"), "bloqueado", "nao_verificado (…)"), "manual")
        # página montada por JavaScript: o robô já dizia "ausente" antes da leitura manual
        self.assertEqual(roda(manual_de_ontem("ausente"), "ok", "ausente (…)"), "manual")
        # antes barrado, agora o robô LÊ a página e o trecho não está: evidência nova, vale "ausente"
        self.assertEqual(roda(manual_de_ontem("nao_verificado"), "ok", "ausente (…)"), "ausente")
        self.assertEqual(roda(manual_de_ontem(None), "ok", "ausente (…)"), "ausente")
        # e achar o trecho sempre substitui a declaração pela prova
        self.assertEqual(roda(manual_de_ontem("ausente"), "ok", "encontrado"), "encontrado")
        # revalidar exige conferência de HOJE: a manual de ontem não serve
        f = manual_de_ontem("ausente")
        with self.assertRaises(fatos.ErroFatos) as c:
            fatos.atualizar(f, "F001", revalidado="todas", hoje=HOJE)
        self.assertIn("conferido HOJE", c.exception.mensagem)

    def _ficha_local(self, *caminhos_e_trechos):
        """Ficha cujas fontes apontam para o servidor local (edição direta: `adicionar` exige https)."""
        f = fatos.nova_ficha("local", HOJE)
        for i, (caminho, trecho) in enumerate(caminhos_e_trechos, 1):
            f["fatos"].append(dict(preco(fontes=[fonte(titulo="Pricing", url=self.base + caminho, editor="Exemplo",
                                                       publicado_em=None, trecho=trecho)],
                                         afirmacao=f"A entrada do modelo Exemplo-{i} custa US$ 1,25 por milhão de tokens."),
                                   id=f"F{i:03d}"))
        self.grava_json("pesquisa/fatos.json", f)

    def test_cli_checar_links_trechos_grava_e_reprova(self):
        self._ficha_local(("/pagina", "Input: $1.25 / 1M tokens"), ("/pagina", "Input: $9.99 / 1M tokens"),
                          ("/documento.pdf", "qualquer coisa"), ("/sumiu", "Input: $1.25 / 1M tokens"))
        r = self.cli("checar-links", "--trechos", "--prazo", "5")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)          # antes: código 0 com "ausente" só no texto
        self.assertIn("REPROVADO: fato confirmado com trecho ausente ou não verificado: F002, F003, F004", r.stdout)
        self.assertIn("1 encontrado(s), 2 ausente(s), 1 não verificado(s)", r.stdout)
        estados = [f["fontes"][0]["conferencia"]["estado"] for f in self.ficha()["fatos"]]
        self.assertEqual(estados, ["encontrado", "ausente", "nao_verificado", "ausente"])
        salvo = json.loads((self.proj / "pesquisa" / "_links.json").read_text(encoding="utf-8"))
        self.assertEqual((salvo["ok"], salvo["trechos_ausentes"], salvo["fatos_sem_conferencia"]),
                         (False, 1, ["F002", "F003", "F004"]))
        resumo = self.cli("resumo").stdout
        self.assertIn("1 encontrado(s) · 0 com conferência manual · 2 AUSENTE(S) · 1 que o robô não leu", resumo)
        self.assertIn("✓ F001", resumo)
        self.assertIn("! F002", resumo)
        j = json.loads(self.cli("checar-links", "--trechos", "--prazo", "5", "--id", "F001", "--json").stdout)
        self.assertEqual((j["ok"], j["conferencias"]["encontrado"]), (True, 1))

    def test_cli_tudo_encontrado_sai_com_zero(self):
        self._ficha_local(("/pagina", "Input: $1.25 / 1M tokens"), ("/pagina", "Exemplo-1"))
        r = self.cli("checar-links", "--trechos", "--prazo", "5")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("2 encontrado(s), 0 ausente(s)", r.stdout)
        # sem --trechos nada é gravado na ficha
        self._ficha_local(("/pagina", "Input: $9.99 / 1M tokens"))
        self.assertEqual(self.cli("checar-links", "--prazo", "5").returncode, 0)
        self.assertNotIn("conferencia", self.ficha()["fatos"][0]["fontes"][0])


# ============================================================ achado 4: gravações paralelas
class TestGravacaoParalela(Base):
    def _fatos_distintos(self, n):
        temas = ("tokens", "parâmetros", "camadas", "idiomas", "imagens", "documentos", "linhas", "perguntas")
        for i in range(n):
            f = fato(afirmacao=f"O estudo número {i + 1} mediu {100 + i} {temas[i]} no conjunto de teste de 2017.",
                     valor=100 + i, unidade=temas[i], como_dizer=f"Em 2017, o estudo mediu {100 + i} {temas[i]}.")
            self.grava_json(f"pesquisa/_c{i + 1}.json", f)

    def test_seis_adicionar_simultaneos_gravam_seis_fatos_com_ids_unicos(self):
        self.nova()
        self._fatos_distintos(6)
        for rodada in range(2):
            self.assertEqual(self.cli("novo", "--tema", "corrida", "--forcar").returncode, 0)
            ps = [subprocess.Popen([sys.executable, "-B", str(FATOS_PY), "adicionar", f"@pesquisa/_c{i}.json"],
                                   cwd=str(self.proj), env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True) for i in range(1, 7)]
            saidas = [p.communicate(timeout=120) + (p.returncode,) for p in ps]
            self.assertEqual([rc for *_, rc in saidas], [0] * 6, saidas)
            anunciados = sorted(o.split()[0] for o, _, _ in saidas)
            ficha = self.ficha()
            self.assertEqual(anunciados, [f"F00{i}" for i in range(1, 7)], f"rodada {rodada + 1}")
            self.assertEqual(sorted(f["id"] for f in ficha["fatos"]), anunciados)
            self.assertEqual(len({f["afirmacao"] for f in ficha["fatos"]}), 6)        # nenhum fato perdido
            self.assertEqual(ficha["ultimo_id"], 6)
            for o, _, _ in saidas:                                                    # o id anunciado é o do fato gravado
                fid = o.split()[0]
                gravado = next(f for f in ficha["fatos"] if f["id"] == fid)
                self.assertIn(gravado["afirmacao"], o)

    @unittest.skipIf(fcntl is None, "flock é POSIX")
    def test_trava_ocupada_da_mensagem_acionavel_e_nao_grava(self):
        self.nova()
        caminho = self.proj / "pesquisa" / "fatos.json"
        antes = caminho.read_text(encoding="utf-8")
        with open(caminho.with_name("_fatos.lock"), "a+b") as outro:
            fcntl.flock(outro.fileno(), fcntl.LOCK_EX)
            with self.assertRaises(fatos.ErroFatos) as c:
                with fatos.trava_da_ficha(caminho, espera=0.3):
                    self.fail("entrou na trava ocupada")
            self.assertIn("outro fatos.py está gravando", c.exception.mensagem)
            self.assertIn("lista JSON", c.exception.dica)
        self.assertEqual(caminho.read_text(encoding="utf-8"), antes)
        with fatos.trava_da_ficha(caminho, espera=0.3):                  # liberada: entra de novo
            pass

    def test_leitura_nao_cria_trava_nem_pasta(self):
        vazio = self.tmp / "sem ficha"
        vazio.mkdir()
        self.assertEqual(self.cli("atualizar", "F001", "--notas", "x", cwd=vazio).returncode, 2)
        self.assertEqual(list(vazio.iterdir()), [])


# ============================================================ achado 6: o que é pendência e o que é aviso
class TestPendenciaAvisoEFalsoPositivo(ComFicha):
    FATOS = (preco, janela)

    def test_afirmacao_sobre_nome_sem_marcador_e_pendencia(self):
        for frase in ("O Exemplo Flash 3.8 foi lançado semana passada.", "Ontem a Exemplo anunciou o Exemplo-4.",
                      "O Exemplo-4 é open source.", "O Exemplo-7 bateu o Exemplo-1 em todos os testes.",
                      "A Exemplo lançou o Exemplo Opus 5.5 no mês passado.", "A OpenAI comprou a Exemplo.",
                      "O Exemplo-9 chega no fim do ano.", "Faz três meses que o Exemplo-8 saiu."):
            r, rel = self.confere(frase + "\n")
            self.assertEqual(r.returncode, 1, frase)
            self.assertEqual(self.tipos(rel), ["sem_fato"], frase)

    def test_nome_dito_de_passagem_e_aviso(self):
        for frase in ("O ChatGPT escreve e-mails pra você.", "Abre o Exemplo Opus 5.5 e cola o texto.",
                      "A Siri chegou antes, mas não entendia contexto.", "É assim que o Transformer funciona."):
            r, rel = self.confere(frase + "\n")
            self.assertEqual((r.returncode, rel["pendencias"]), (0, []), frase)
            self.assertEqual(self.tipos(rel, "avisos"), ["so_nomes"], frase)
        # o mesmo modelo com versão que NENHUM fato confirmado registra: pendência
        r, rel = self.confere("Abre o Exemplo Opus 9.9 e cola o texto.\n")
        self.assertEqual(self.tipos(rel), ["sem_fato"])
        self.assertIn("nenhum fato confirmado registra", rel["pendencias"][0]["detalhe"])

    def test_chamadas_e_fala_pessoal_nao_viram_pendencia(self):
        inocentes = ("Em 60 segundos eu te explico.", "Aqui vão 3 motivos para você testar.",
                     "Se você tem 2 minutos, fica comigo.", "Eu uso isso 10 vezes por dia.", "Me segue para a parte 2.",
                     "Comenta 1 se você quer a planilha.", "Deixa o like, em 24 horas sai a continuação.",
                     "Link na bio, 100% gratuito.", "Eu tenho 34 anos e nunca vi nada igual.",
                     "São 7 da manhã e eu já estou gravando.", "A melhor forma de aprender IA é praticando.",
                     "Isso é o mais importante do vídeo.", "Salva esse vídeo e manda para 2 amigos.",
                     "Imagina uma biblioteca com 1 milhão de livros.", "Dá o play em 1,5x se estiver com pressa.")
        r, rel = self.confere("\n\n".join(inocentes) + "\n", "--estrito")
        self.assertEqual((r.returncode, rel["pendencias"], rel["avisos"]), (0, [], []), r.stdout)
        self.assertGreaterEqual(len(rel["ignoradas"]), 5)                # e o relatório mostra o que foi ignorado
        # frase dirigida ao espectador com número pequeno é ambígua: aviso, nunca silêncio
        r, rel = self.confere("Você sabia que só 5 países treinam esses sistemas?\n")
        self.assertEqual((r.returncode, self.tipos(rel, "avisos")), (0, ["fala_direta"]))
        self.assertEqual(self.confere("Você sabia que só 5 países treinam esses sistemas?\n", "--estrito")[0].returncode, 1)

    def test_apelido_e_nomes_que_a_ficha_ensina(self):
        r = self.adiciona([preco(afirmacao="A entrada do modelo Exemplo Fable 5.1 custa US$ 10 por milhão de tokens na API.",
                                 valor=10, termos=["Exemplo Fable 5.1"],
                                 como_dizer="Em outubro de 2026, a entrada do Exemplo Fable 5.1 custava US$ 10 por milhão de tokens."),
                           janela(afirmacao="Em outubro de 2026, a documentação listava janela de contexto de 400 mil tokens "
                                            "para o Fulano 3.", valor=400000, termos=["Fulano 3"],
                                  como_dizer="Em outubro de 2026, o Fulano 3 lia até 400 mil tokens de uma vez.")])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.confere_trechos()
        # "Fable 5.1" é a forma curta do nome registrado; "Fulano 3" é família que a lista embutida não conhece
        for frase in ("Em outubro de 2026, a entrada do Fable 5.1 custava US$ 10 por milhão de tokens [F003].\n",
                      "Em outubro de 2026, o Fulano 3 lia até 400 mil tokens de uma vez [F004].\n"):
            r, rel = self.confere(frase)
            self.assertEqual(rel["pendencias"], [], frase + r.stdout)

    def test_titulos_tabelas_e_metadados_com_dado_sao_conferidos(self):
        texto = ("# O Exemplo-9 custa US$ 1 e é o melhor modelo do mundo\n\n"
                 "**Motor:** 2 · Crença\n**Duração alvo:** 45–60s\n**Versão:** o Exemplo-1 custa US$ 99 por milhão de tokens\n\n"
                 "## Gancho (0–3s)\n\nA IA não pensa.\n\n## Take 2 (plano B)\n\n"
                 "| Modelo | Preço |\n|---|---|\n| Exemplo-1 | US$ 33 |\n| 0–3s | A IA completa a próxima palavra. |\n")
        r, rel = self.confere(texto)
        self.assertEqual(sorted((p["linha"], p["tipo"]) for p in rel["pendencias"]),
                         [(1, "sem_fato"), (5, "sem_fato"), (15, "sem_fato")], r.stdout)
        self.assertEqual(rel["linhas_ignoradas"], {"cabeçalho de tabela": 1})
        self.assertEqual(rel["avisos"], [])
        # título de seção que só nomeia um modelo já registrado não é fala; modelo que a ficha não conhece é pendência
        r, rel = self.confere("## Bloco 2 — Exemplo Opus 5.5\n\nA IA não pensa.\n", "--estrito")
        self.assertEqual((r.returncode, rel["pendencias"], rel["avisos"]), (0, [], []), r.stdout)
        r, rel = self.confere("## Bloco 2 — Exemplo Opus 9.9\n\nA IA não pensa.\n")
        self.assertEqual(self.tipos(rel), ["sem_fato"])


# ============================================================ achado 8: validar × método
class TestConfirmadoExigeFonteQueSustente(unittest.TestCase):
    def val(self, f):
        return fatos.validar_fato(dict(f, id="F001"), HOJE)

    def test_categoria_volatil_nao_se_confirma_so_com_secundarias(self):
        sec = lambda ed, u: fonte(tipo="secundaria", editor=ed, url=u, publicado_em=None)  # noqa: E731
        blogs = [sec("Blog do Fulano", "https://medium.com/@alguem/precos"), sec("Reddit", "https://www.reddit.com/r/x/1")]
        for cat in ("preco", "modelo", "benchmark"):
            erros, _ = self.val(preco(categoria=cat, confianca="media", fontes=blogs))
            self.assertIn("só se confirma com fonte primária", mensagens(erros), cat)
        erros, avisos = self.val(fato(confianca="media", fontes=blogs))      # história: duas secundárias bastam…
        self.assertEqual(erros, [], mensagens(erros))
        self.assertIn("sustentado só por enciclopédia, fórum ou blog", mensagens(avisos))   # …mas o aviso fica
        erros, _ = self.val(fato(confianca="alta", fontes=blogs))
        self.assertIn("confiança alta exige fonte primária", mensagens(erros))

    def test_mesma_pagina_ou_mesmo_dominio_nao_sao_duas_fontes(self):
        sec = lambda ed, u: fonte(tipo="secundaria", editor=ed, url=u)  # noqa: E731
        casos = ([sec("Site A", "https://exemplo.example/materia"), sec("Site B", "https://exemplo.example/materia")],
                 [sec("Site A", "https://www.exemplo.example/a"), sec("Site B", "https://blog.exemplo.example/b")],
                 [sec("Site A", "https://a.example/1"), sec("site a", "https://b.example/2")])
        for fontes in casos:
            erros, _ = self.val(fato(confianca="media", fontes=fontes))
            self.assertIn("1 editor secundário independente", mensagens(erros), fontes)
        erros, _ = self.val(fato(confianca="media", fontes=[sec("Site A", "https://a.example/1"),
                                                            sec("Site B", "https://b.example/2")]))
        self.assertEqual(erros, [])
        self.assertEqual(fatos.dominio_registravel("https://www.blog.exemplo.com.br/x"), "exemplo.com.br")


# ============================================================ achado 9: duplicata × tabela comparativa
class TestDuplicataDistingueModelos(Base):
    def test_mesmo_preco_na_mesma_pagina_para_modelos_diferentes(self):
        self.nova()
        mk = lambda nome, frase=None: preco(  # noqa: E731
            afirmacao=frase or f"Em outubro de 2026, a tabela oficial da Exemplo cobrava US$ 0,75 por milhão de tokens de "
                               f"entrada no {nome}.", valor=0.75, termos=[nome],
            como_dizer=f"Em outubro de 2026, 1 milhão de tokens de entrada no {nome} custava US$ 0,75.")
        self.assertEqual(self.adiciona(mk("Exemplo Flash 3.8")).returncode, 0)
        r = self.adiciona(mk("Exemplo Flash 3.7"))                          # antes: "duplicata… 99% igual"
        self.assertEqual(r.returncode, 0, r.stderr)
        r = self.adiciona(mk("Exemplo Flash 3.6", "O Exemplo Flash 3.6, modelo anterior da linha, tinha em outubro de 2026 "
                                                  "o preço de entrada de US$ 0,75 por milhão de tokens."))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(self.ficha()["fatos"]), 3)
        # o MESMO modelo, mesma medida, mesma página, dito de outro jeito: isso é duplicata
        r = self.adiciona(mk("Exemplo Flash 3.8", "Um milhão de tokens de entrada saía por US$ 0,75 no Exemplo Flash 3.8 "
                                                  "em outubro de 2026."))
        self.assertEqual(r.returncode, 1)
        self.assertIn("duplicata de F001", r.stderr)
        self.assertIn("--forcar", r.stderr)
        self.assertIn("nome exato do modelo", r.stderr)


# ============================================================ achado 10: o número que vai para a TELA
class TestStoryboardConfereOsNumerosDaTela(ComFicha):
    FATOS = (preco,)

    def sb(self, *cenas):
        self.grava_json("roteiro/storyboard.json", {"versao": 1, "cenas": list(cenas)})
        r = self.cli("conferir-storyboard", "--json")
        return r, json.loads(r.stdout)

    def cena(self, **k):
        base = {"id": "C01", "trecho": "custava US$ 1,25", "t0": None, "dur": 6, "cena": "barras",
                "params": {"titulo": "Preço de entrada", "fonte": "Exemplo, out/2026", "prefixo": "US$ ", "casas": 2,
                           "max": 10, "destaque": 0, "dados": [{"rotulo": "Exemplo-1", "valor": 1.25}]},
                "formatos": ["horizontal"], "fato_ids": ["F001"], "broll_id": None, "saida": "animacoes/C01"}
        base.update(k)
        return base

    def test_cena_certa_passa_e_aparencia_nao_e_dado(self):
        r, rel = self.sb(self.cena())
        self.assertEqual((r.returncode, rel["pendencias"], rel["avisos"]), (0, [], []), r.stdout)

    def test_numero_errado_na_tela_e_pendencia(self):
        errada = self.cena(trecho="custava US$ 9", params={"titulo": "US$ 9 por milhão", "fonte": "Exemplo, out/2026",
                                                           "itens": [{"rotulo": "Exemplo-1", "valor": 9}]})
        r, rel = self.sb(errada)
        self.assertEqual(r.returncode, 1)
        self.assertEqual([p["tipo"] for p in rel["pendencias"]], ["numero_nao_bate"] * 3)
        detalhes = " ".join(p["detalhe"] for p in rel["pendencias"])
        for onde in ("(trecho)", "(params.titulo)", "(params.itens[0].valor)"):
            self.assertIn(onde, detalhes)

    def test_tipo_vem_do_prefixo_e_da_unidade(self):
        p = dict(self.cena()["params"], prefixo="", unidade="%")
        r, rel = self.sb(self.cena(trecho="x", params=p))                  # 1,25 % não é US$ 1,25
        self.assertEqual([x["tipo"] for x in rel["pendencias"]], ["numero_nao_bate"])
        p = dict(self.cena()["params"], prefixo="R$ ")
        r, rel = self.sb(self.cena(trecho="x", params=p))                  # outra moeda
        self.assertEqual([x["tipo"] for x in rel["pendencias"]], ["numero_nao_bate"])

    def test_cena_embutida_que_nao_desenha_credito(self):
        r, rel = self.sb(self.cena(cena="titulo", trecho="custava US$ 1,25", params={"titulo": "US$ 1,25"}))
        self.assertEqual(rel["pendencias"], [])
        self.assertEqual([a["tipo"] for a in rel["avisos"]], ["sem_credito"])
        self.assertIn("`titulo` não desenha crédito", rel["avisos"][0]["detalhe"])
        r, rel = self.sb(self.cena(params={"dados": [{"rotulo": "Exemplo-1", "valor": 1.25}], "prefixo": "US$ "}))
        self.assertIn("ponha params.fonte = \"Exemplo, out/2026\"", rel["avisos"][0]["detalhe"])

    def test_cena_com_numero_e_sem_fato(self):
        r, rel = self.sb(self.cena(id="C09", trecho="O Exemplo-9 custa US$ 1", params={"texto": "97% de acerto"},
                                   fato_ids=[]))
        self.assertEqual(r.returncode, 1)
        self.assertEqual([p["tipo"] for p in rel["pendencias"]], ["sem_fato"])


# ============================================================ achados 11 e 12: documentação × código
class TestMensagensEAjuda(Base):
    def test_ajuda_de_atualizar_cita_a_opcao_que_existe(self):
        h = self.cli("atualizar", "--help").stdout
        self.assertIn("--nova-fonte", h)
        self.assertNotRegex(h, r"use\s+--fonte\b")
        self.nova()
        self.assertEqual(self.adiciona(fato()).returncode, 0)
        r = self.cli("atualizar", "F001", "--fonte", "{}")
        self.assertEqual(r.returncode, 64)

    def test_dica_de_json_invalido_depende_do_arquivo(self):
        self.nova()
        (self.proj / "roteiro" / "roteiro.md").write_text("Em 2017 saiu o Transformer.\n", encoding="utf-8")
        r = self.cli("conferir-storyboard", "roteiro/roteiro.md")
        self.assertEqual(r.returncode, 1)
        self.assertIn("conferir-roteiro", r.stderr)
        self.assertNotIn("_fatos.anterior.json", r.stderr)
        (self.proj / "pesquisa" / "fatos.md").write_text("# não é json\n", encoding="utf-8")
        r = self.cli("--ficha", "pesquisa/fatos.md", "resumo")
        self.assertIn("--ficha espera o pesquisa/fatos.json", r.stderr)

    def test_novo_em_pasta_vazia_ensina_o_comando(self):
        vazia = self.tmp / "Projeto novo sem DA"
        vazia.mkdir()
        r = self.cli("novo", "--tema", "x", cwd=vazia)
        self.assertEqual(r.returncode, 64)
        self.assertIn("--projeto .", r.stderr)
        r = self.cli("novo", "--tema", "x", "--projeto", ".", cwd=vazia)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("checar-links --trechos", r.stdout)


class TestDocumentacao(unittest.TestCase):
    """O SKILL.md entra no contexto a cada disparo: não pode cortar o gatilho nem carregar dado perecível."""

    @classmethod
    def setUpClass(cls):
        cls.texto = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        m = re.match(r"---\n(.*?)\n---\n", cls.texto, re.S)
        cls.frente = m.group(1) if m else ""
        cls.corpo = cls.texto[m.end():] if m else cls.texto

    def test_frontmatter_de_dois_campos_e_description_inteira_na_listagem(self):
        linhas = self.frente.splitlines()
        self.assertEqual([l.split(":", 1)[0] for l in linhas], ["name", "description"])
        self.assertEqual(linhas[0], f"name: {SKILL.name}")
        bruto = linhas[1].split(":", 1)[1].strip()
        self.assertTrue(bruto.startswith('"') and bruto.endswith('"'), "description entre aspas duplas (YAML estrito)")
        descricao = json.loads(bruto)                    # escalar entre aspas duplas sem escapes exóticos = JSON
        self.assertLessEqual(len(descricao), 1500, "a listagem de skills corta a description em 1.536 caracteres")
        self.assertIn("Difere das irmãs", descricao)
        for irma in ("gerar-roteiro", "melhorar-roteiro", "video-broll", "video-publicacao",
                     "video-direcao-de-arte", "video-animacao-explicativa"):
            self.assertIn(irma, descricao)

    def test_corpo_curto_e_sem_caminho_de_montagem(self):
        self.assertLess(len(self.corpo.splitlines()), 300)
        for arq in [SKILL / "SKILL.md", *sorted((SKILL / "references").glob("*.md")), SKILL / "scripts" / "fatos.py"]:
            t = arq.read_text(encoding="utf-8")
            self.assertNotIn("scratchpad", t, arq.name)
            self.assertNotIn("/private/tmp", t, arq.name)

    def test_exemplos_copiaveis_nao_trazem_especificacao_real(self):
        """O exemplo de fato do SKILL.md é fictício: colado sem pesquisa, não pode virar preço "confirmado"."""
        blocos = re.findall(r"```.*?\n(.*?)```", self.corpo, re.S)
        urls = [u for b in blocos for u in fatos.urls_de_texto(b)]
        self.assertTrue(urls, "o SKILL.md deveria ter ao menos um exemplo de fonte")
        for u in urls:
            host = re.sub(r"^https?://", "", u).split("/")[0]
            self.assertTrue(host.endswith((".example", "example.com", "example.org")), f"URL real em exemplo copiável: {u}")
        for arq in (SKILL / "SKILL.md", SKILL / "references" / "metodo.md"):
            t = arq.read_text(encoding="utf-8")
            achados = re.findall(r"(?:US\$|\$)\s?\d+[.,]\d{2}\b[^\n]{0,60}", t)
            reais = [a for a in achados if not re.search(r"exemplo|fict[íi]ci|Exemplo", a + t[max(0, t.find(a) - 200):t.find(a)])]
            self.assertEqual(reais, [], f"{arq.name}: preço que parece real fora de exemplo fictício")


if __name__ == "__main__":
    unittest.main()
