"""Registro de licenças: política, validação, ids, gravação concorrente e créditos. Sem rede e sem o kit."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

from testes import apoio

import registro as R

CC_BY_SA = {"fonte": "wikimedia", "titulo": "Sala de servidores", "autor": "Fulana de Tal", "licenca": "CC BY-SA 3.0",
            "licenca_url": "https://creativecommons.org/licenses/by-sa/3.0", "pagina_url": "https://commons.wikimedia.org/wiki/File:X.webm"}


class Politica(unittest.TestCase):
    def test_01_o_que_entra_e_o_que_e_recusado(self):
        casos = {
            "Pexels License": ("pexels", True), "Pixabay Content License": ("pixabay", True), "CC0": ("cc0", True), "cc-zero": ("cc0", True),
            "Public domain": ("pd", True), "PD-USGov": ("pd", True), "pdm": ("pdm", True), "NASA": ("nasa", True),
            "CC BY 4.0": ("cc-by", True), "cc-by-2.0": ("cc-by", True), "by": ("cc-by", True),
            "CC BY-SA 3.0": ("cc-by-sa", True), "Creative Commons Attribution-Share Alike 4.0": ("cc-by-sa", True), "by-sa": ("cc-by-sa", True),
            "CC BY-NC 4.0": ("cc-by-nc", False), "by-nc-sa": ("cc-by-nc-sa", False), "CC BY-ND 2.0": ("cc-by-nd", False), "by-nc-nd": ("cc-by-nc-nd", False),
            "Standard YouTube License": ("todos-os-direitos", False), "GFDL": ("desconhecida", False), "": ("desconhecida", False),
            "Attribution": ("desconhecida", False), "Copyrighted free use": ("desconhecida", False),
        }
        for texto, (lid, permitida) in casos.items():
            f = R.avaliar_licenca(texto)
            self.assertEqual((f["id"], f["permitida"]), (lid, permitida), texto)

    def test_02_a_url_da_licenca_decide_quando_o_texto_nao_diz(self):
        self.assertEqual(R.avaliar_licenca(None, "http://creativecommons.org/licenses/publicdomain/")["id"], "pd")
        self.assertEqual(R.avaliar_licenca(None, "https://creativecommons.org/publicdomain/zero/1.0/")["id"], "cc0")
        self.assertEqual(R.avaliar_licenca(None, "https://creativecommons.org/publicdomain/mark/1.0/")["id"], "pdm")
        f = R.avaliar_licenca("qualquer coisa", "https://creativecommons.org/licenses/by-nc-sa/2.0/")
        self.assertEqual((f["id"], f["versao"], f["permitida"]), ("cc-by-nc-sa", "2.0", False))
        self.assertFalse(R.avaliar_licenca("sampling+", "https://creativecommons.org/licenses/sampling+/1.0/")["permitida"])
        f = R.avaliar_licenca("CC BY-SA 2.5 br", "https://creativecommons.org/licenses/by-sa/2.5/br/")
        self.assertEqual((f["nome"], f["url"]), ("CC BY-SA 2.5", "https://creativecommons.org/licenses/by-sa/2.5/br/"))

    def test_03_o_que_cada_licenca_exige(self):
        self.assertFalse(R.avaliar_licenca("Pexels License")["exige_atribuicao"])
        self.assertTrue(R.avaliar_licenca("CC BY 4.0")["exige_atribuicao"])
        self.assertTrue(R.avaliar_licenca("NASA")["exige_atribuicao"])
        sa = R.avaliar_licenca("CC BY-SA 4.0")
        self.assertTrue(sa["compartilha_igual"])
        self.assertEqual(sa["risco"], "medio")
        self.assertFalse(R.avaliar_licenca("CC BY-NC 4.0")["uso_comercial"])
        self.assertFalse(R.avaliar_licenca("CC BY-ND 4.0")["permite_derivados"])
        self.assertEqual(R.avaliar_licenca(fonte="nasa")["id"], "nasa")           # sem texto, a fonte define
        self.assertEqual(R.avaliar_licenca(fonte="pexels")["id"], "pexels")


    def test_04_marca_restritiva_vence_em_qualquer_grafia(self):
        """Regressão: «Creative Commons Atribuição-SemDerivações 4.0 Internacional» entrava como CC BY e o texto sumia."""
        recusadas = {
            "Creative Commons Atribuição-SemDerivações 4.0 Internacional": "cc-by-nd", "Creative Commons Atribuição-Uso não-comercial 2.0": "cc-by-nc",
            "CC BY Não Comercial": "cc-by-nc", "CC BY Non Commercial 2.0": "cc-by-nc", "Creative Commons Attribution Non Commercial": "cc-by-nc",
            "CC BY No Derivs 2.0": "cc-by-nd", "CC BY Sem Derivações 4.0": "cc-by-nd",
            "Creative Commons - Attribution - Non Commercial - No Derivs": "cc-by-nc-nd", "AttributionNonCommercialNoDerivs": "cc-by-nc-nd",
            "Atribuição-NãoComercial-CompartilhaIgual 4.0 Internacional": "cc-by-nc-sa",
            "Copyright ESA/NASA, all rights reserved": "todos-os-direitos", "Vídeo da NASA, todos os direitos reservados": "todos-os-direitos",
            "© 2024 Fulano": "todos-os-direitos", "Copyright ESA/NASA": "todos-os-direitos",
            "Not in the public domain": "desconhecida", "Não está em domínio público": "desconhecida",
            "Editorial use only": "restrita", "Free for personal use only": "restrita", "Uso comercial proibido": "restrita",
            "Imagem do Pexels": "desconhecida", "NASA/ESA": "desconhecida",          # o nome do banco só vale quando o texto INTEIRO é a licença dele
        }
        for texto, lid in recusadas.items():
            f = R.avaliar_licenca(texto)
            self.assertEqual((f["id"], f["permitida"]), (lid, False), texto)
        entram = {"Creative Commons Attribution 4.0 International": "cc-by", "Some rights reserved — CC BY 2.0": "cc-by", "cc-by-sa-3.0-de": "cc-by-sa",
                  "CC BY-SA 3.0 IGO": "cc-by-sa", "No known copyright restrictions": "pd", "Public domain: not copyrighted": "pd",
                  "Domínio público": "pd", "Mídia da NASA": "nasa", "Licença do Pexels": "pexels", "Licença de conteúdo do Pixabay": "pixabay"}
        for texto, lid in entram.items():
            f = R.avaliar_licenca(texto)
            self.assertEqual((f["id"], f["permitida"]), (lid, True), texto)
        for lid, ficha in R.LICENCAS.items():                 # o nome canônico gravado no registro é relido como a mesma licença
            self.assertEqual(R.avaliar_licenca(R.avaliar_licenca(ficha["nome"])["nome"])["id"], lid, ficha["nome"])

    def test_05_texto_e_url_divergentes_vale_a_leitura_mais_restritiva(self):
        by = "https://creativecommons.org/licenses/by/4.0/"
        f = R.avaliar_licenca("CC BY-NC-ND 4.0", by)
        self.assertEqual((f["id"], f["permitida"], f["url"]), ("cc-by-nc-nd", False, "https://creativecommons.org/licenses/by-nc-nd/4.0/"))
        self.assertIn("mais restritiva", f["divergencia"])
        f = R.avaliar_licenca("CC BY 4.0", "https://creativecommons.org/licenses/by-nc/2.0/")
        self.assertEqual((f["id"], f["versao"], f["permitida"]), ("cc-by-nc", "2.0", False))
        f = R.avaliar_licenca("all rights reserved", "https://creativecommons.org/publicdomain/zero/1.0/")
        self.assertEqual((f["id"], f["permitida"], f["url"]), ("todos-os-direitos", False, None))
        f = R.avaliar_licenca("Not in the public domain", "https://creativecommons.org/publicdomain/mark/1.0/")
        self.assertFalse(f["permitida"], "negação explícita no texto não é desfeita pela URL")
        f = R.avaliar_licenca("Public domain", "https://creativecommons.org/licenses/by-sa/3.0/")
        self.assertEqual((f["id"], f["exige_atribuicao"]), ("cc-by-sa", True))
        f = R.avaliar_licenca("Public domain", "https://creativecommons.org/publicdomain/mark/1.0/")
        self.assertEqual((f["id"], f["divergencia"]), ("pdm", None), "a URL só é mais precisa: não é divergência")
        self.assertIsNone(R.avaliar_licenca("CC BY 4.0", by)["divergencia"])

    def test_06_codigo_colado_pontuado_ou_com_traco_tipografico_nao_passa_por_cc_by(self):
        """Regressão: «CC-BY-NCSA», «cc-by-ncnd», «cc by n.c.» e «CC BY-N C» entravam como CC BY (uso comercial verdadeiro), e
        «public domain in the US only; copyrighted elsewhere» entrava como domínio público. A leitura agora é fechada."""
        recusadas = {
            "CC-BY-NCSA": "cc-by-nc-sa", "cc-by-ncnd": "cc-by-nc-nd", "cc by n.c.": "cc-by-nc", "CC BY-N C": "cc-by-nc", "CC BY N-C": "cc-by-nc",
            "CCBYNC": "cc-by-nc", "CC-BYNC": "cc-by-nc", "CC\u2011BY\u2011NC": "cc-by-nc", "CC BY\u2013NC 4.0": "cc-by-nc", "CC BY\u2014ND": "cc-by-nd",
            "cc.by.nc.nd": "cc-by-nc-nd", "by-ncsa": "cc-by-nc-sa", "BYNC": "cc-by-nc", "cc by n d 4.0": "cc-by-nd", "CC BY\u00a0NC": "cc-by-nc",
            "public domain in the US only; copyrighted elsewhere": "desconhecida", "Domínio público apenas nos EUA": "desconhecida",
            "Public domain except in Germany": "desconhecida",
            "CC BY xx": "desconhecida", "cc by q": "desconhecida", "CC BY 3.0 zz-foo": "desconhecida", "Photo by John, Creative Commons": "desconhecida",
        }
        for texto, lid in recusadas.items():
            f = R.avaliar_licenca(texto)
            self.assertEqual((f["id"], f["permitida"]), (lid, False), texto)
        entram = {"ccbysa": "cc-by-sa", "CCBY4.0": "cc-by", "CC-BY-SA-4.0": "cc-by-sa", "CC BY 2.5 br": "cc-by", "CC BY-SA 3.0 de": "cc-by-sa", "CC BY 3.0 Brasil": "cc-by",
                  "Creative Commons Attribution-ShareAlike 3.0 Unported License": "cc-by-sa", "Creative Commons Atribuição 4.0 Internacional": "cc-by",
                  "Licensed under the Creative Commons Attribution 4.0 International License": "cc-by", "Public domain: not copyrighted": "pd", "PD-USGov": "pd"}
        for texto, lid in entram.items():
            f = R.avaliar_licenca(texto)
            self.assertEqual((f["id"], f["permitida"]), (lid, True), texto)
        by = "https://creativecommons.org/licenses/by/4.0/"
        self.assertFalse(R.avaliar_licenca("cc by n c", by)["permitida"], "resto que pode ser pedaço de NC: nem a URL desfaz")
        self.assertFalse(R.avaliar_licenca("CC BY xx", by)["permitida"], "termo curto que sobra depois de CC BY é veto")
        self.assertTrue(R.avaliar_licenca("Photo by John, Creative Commons", by)["permitida"], "texto que só não diz nada deixa a URL decidir")
        self.assertFalse(R.avaliar_licenca("public domain in the US only", "https://creativecommons.org/publicdomain/mark/1.0/")["permitida"])


class Registro(unittest.TestCase):
    def setUp(self):
        self.p = apoio.pasta_temporaria(self) / "Vídeo 2 — projeto de teste"
        (self.p / "broll").mkdir(parents=True)

    def test_10_adicionar_reserva_ids_por_prefixo_e_completa_o_item(self):
        self.assertEqual(R.carregar(self.p), {"versao": 1, "itens": []})
        b1 = R.adicionar(self.p, dict(CC_BY_SA))
        b2 = R.adicionar(self.p, {"fonte": "nasa", "titulo": "Earth Views", "pagina_url": "https://images.nasa.gov/details/abc"})
        y1 = R.adicionar(self.p, {"fonte": "youtube", "titulo": "Palestra", "autor": "Canal Tal", "base_legal": "citacao",
                                  "notas": "8 s para comentar a fala", "pagina_url": "https://www.youtube.com/watch?v=x"})
        w1 = R.adicionar(self.p, {"fonte": "web", "tipo": "imagem", "titulo": "Print", "base_legal": "citacao", "notas": "captura de tela comentada",
                                  "pagina_url": "https://example.com/pagina"})
        self.assertEqual((b1, b2, y1, w1), ("B001", "B002", "Y001", "W001"))
        self.assertEqual((R.proximo_id(self.p, "B"), R.proximo_id(self.p, "Y"), R.proximo_id(self.p, "W")), ("B003", "Y002", "W002"))
        item = R.obter(self.p, b1)
        for campo in ("id", "consulta", "pedido_id", "fonte", "pagina_url", "arquivo_url", "autor", "autor_url", "licenca", "licenca_url", "base_legal", "risco",
                      "exige_atribuicao", "atribuicao", "uso_comercial", "baixado_em", "arquivo", "sha256", "largura", "altura", "fps", "duracao", "trecho",
                      "tratados", "usado_em"):
            self.assertIn(campo, item, f"campo do contrato ausente: {campo}")
        self.assertEqual((item["licenca"], item["licenca_id"], item["risco"], item["exige_atribuicao"], item["uso_comercial"]),
                         ("CC BY-SA 3.0", "cc-by-sa", "medio", True, True))
        for pedaco in ("Sala de servidores", "Fulana de Tal", "CC BY-SA 3.0", "https://creativecommons.org/licenses/by-sa/3.0", "File:X.webm", "adaptado"):
            self.assertIn(pedaco, item["atribuicao"])
        self.assertEqual(item["credito_tela"], "Fulana de Tal · CC BY-SA 3.0")
        nasa = R.obter(self.p, b2)
        self.assertEqual((nasa["licenca_id"], nasa["exige_atribuicao"], nasa["credito_tela"]), ("nasa", True, "NASA"))
        cit = R.obter(self.p, y1)
        self.assertEqual((cit["base_legal"], cit["risco"], cit["exige_atribuicao"], cit["uso_comercial"]), ("citacao", "medio", True, False))
        self.assertIn("usado como citação", cit["atribuicao"])
        dados = json.loads((self.p / "broll" / "licencas.json").read_text(encoding="utf-8"))
        self.assertEqual(dados["versao"], 1)
        self.assertEqual([i["id"] for i in dados["itens"]], ["B001", "B002", "Y001", "W001"])

    def test_11_licenca_recusada_so_entra_como_excecao_com_nota(self):
        nc = {"fonte": "openverse", "titulo": "Foto", "autor": "X", "licenca": "CC BY-NC 2.0", "pagina_url": "https://example.org/foto"}
        with self.assertRaises(R.RegistroErro) as e:
            R.adicionar(self.p, dict(nc))
        self.assertIn("recusada pela política", str(e.exception))
        with self.assertRaises(R.RegistroErro):
            R.adicionar(self.p, {"fonte": "web", "titulo": "sem licença", "pagina_url": "https://example.org/x"})          # desconhecida
        with self.assertRaises(R.RegistroErro) as e:
            R.adicionar(self.p, {**nc, "base_legal": "autorizacao"})                                                  # exceção sem nota
        self.assertIn("notas", str(e.exception))
        iid = R.adicionar(self.p, {**nc, "base_legal": "autorizacao", "notas": "autorização por e-mail de 2026-10-01, guardada em pesquisa/"})
        item = R.obter(self.p, iid)
        self.assertEqual((item["base_legal"], item["exige_atribuicao"]), ("autorizacao", True))
        self.assertEqual(R.carregar(self.p)["itens"], [item], "recusas não deixam rastro no registro")

    def test_12_a_politica_nao_e_contornada_por_campo_falso(self):
        with self.assertRaises(R.RegistroErro) as e:
            R.adicionar(self.p, {**CC_BY_SA, "exige_atribuicao": False})
        self.assertIn("exige atribuição", str(e.exception))
        with self.assertRaises(R.RegistroErro):
            R.adicionar(self.p, {**CC_BY_SA, "risco": "nenhum"})
        with self.assertRaises(R.RegistroErro):
            R.adicionar(self.p, {**CC_BY_SA, "fonte": "torrent"})
        with self.assertRaises(R.RegistroErro):
            R.adicionar(self.p, {**CC_BY_SA, "pagina_url": "ftp://x"})
        with self.assertRaises(R.RegistroErro):
            R.adicionar(self.p, {**CC_BY_SA, "trecho": {"t0": 5, "t1": 2}})
        with self.assertRaises(R.RegistroErro):
            R.adicionar(self.p, {**CC_BY_SA, "arquivo": "/tmp/fora do projeto.mp4"})
        self.assertEqual(R.carregar(self.p)["itens"], [])

    def test_13_atualizar_marcar_uso_e_tratados(self):
        iid = R.adicionar(self.p, dict(CC_BY_SA))
        item = R.atualizar(self.p, iid, autor="Beltrano", trecho={"t0": 2, "t1": 6.5})
        self.assertIn("Beltrano", item["atribuicao"])                       # texto derivado é refeito
        self.assertEqual(item["credito_tela"], "Beltrano · CC BY-SA 3.0")
        self.assertEqual(item["trecho"], {"t0": 2.0, "t1": 6.5})
        with self.assertRaises(R.RegistroErro):
            R.atualizar(self.p, iid, licenca="CC BY-NC 4.0", licenca_url=None)   # atualizar também passa pela política
        with self.assertRaises(R.RegistroErro):
            R.atualizar(self.p, "B999", autor="x")
        self.assertEqual(R.marcar_uso(self.p, iid, "C03"), ["C03"])
        self.assertEqual(R.marcar_uso(self.p, iid, "C03"), ["C03"], "marcar duas vezes não duplica")
        self.assertEqual(R.marcar_uso(self.p, iid, "K01"), ["C03", "K01"])
        self.assertEqual(R.desmarcar_uso(self.p, iid, "C03"), ["K01"])
        (self.p / "broll" / "tratado").mkdir()
        (self.p / "broll" / "tratado" / "B001_vertical.mp4").write_bytes(b"x")
        self.assertEqual(R.registrar_tratado(self.p, iid, self.p / "broll" / "tratado" / "B001_vertical.mp4"), ["broll/tratado/B001_vertical.mp4"])
        (self.p / "broll" / "tratado" / "B001_horizontal.mp4").write_bytes(b"x")
        R.registrar_tratado(self.p, iid, self.p / "broll" / "tratado" / "B001_horizontal.mp4")
        R.registrar_tratado(self.p, iid, self.p / "broll" / "tratado" / "B001_vertical.mp4")       # de novo: não duplica
        self.assertEqual(R.obter(self.p, iid)["tratados"], ["broll/tratado/B001_horizontal.mp4", "broll/tratado/B001_vertical.mp4"], "ordem estável no arquivo")

    def test_14_mover_de_renomeia_o_arquivo_sob_a_trava(self):
        tmp = self.p / "broll" / "bruto" / "_baixando" / "abc.parcial"
        tmp.parent.mkdir(parents=True)
        tmp.write_bytes(b"conteudo")
        iid = R.adicionar(self.p, {**CC_BY_SA, "sha256": R.sha256_arquivo(tmp)}, mover_de=tmp, extensao=".webm")
        item = R.obter(self.p, iid)
        self.assertEqual(item["arquivo"], "broll/bruto/B001.webm")
        self.assertTrue((self.p / "broll" / "bruto" / "B001.webm").is_file())
        self.assertFalse(tmp.exists())
        self.assertTrue(R.validar(self.p, conferir_sha=True)["ok"])
        (self.p / "broll" / "bruto" / "B001.webm").write_bytes(b"outro")
        self.assertFalse(R.validar(self.p, conferir_sha=True)["ok"])
        (self.p / "broll" / "bruto" / "B001.webm").unlink()
        self.assertIn("não está no disco", " ".join(R.validar(self.p)["erros"]))

    def test_15_creditos_md_separa_obrigatorio_de_cortesia_e_so_lista_o_usado(self):
        a = R.adicionar(self.p, dict(CC_BY_SA))
        b = R.adicionar(self.p, {"fonte": "pexels", "tipo": "video", "autor": "Ana Lima", "pagina_url": "https://www.pexels.com/video/1/"})
        c = R.adicionar(self.p, {"fonte": "nasa", "titulo": "Earth Views", "pagina_url": "https://images.nasa.gov/details/abc"})
        texto = R.creditos_md(self.p)
        self.assertIn("Nenhum item tem `usado_em`", texto)
        obrig = texto.split("## Para a descrição")[1].split("## Cortesia")[0]
        cortesia = texto.split("## Cortesia")[1].split("##")[0]
        self.assertIn("Sala de servidores", obrig)
        self.assertIn("NASA", obrig)
        self.assertIn("Vídeo de Ana Lima no Pexels", cortesia)
        self.assertNotIn("Pexels", obrig)
        R.marcar_uso(self.p, b, "C01")
        R.marcar_uso(self.p, c, "C02")
        texto = (self.p / "broll" / "creditos.md").read_text(encoding="utf-8")       # regravado a cada mudança
        obrig = texto.split("## Para a descrição")[1].split("## Cortesia")[0]
        self.assertNotIn("Sala de servidores", obrig, "item não usado sai da lista para a descrição")
        self.assertIn("Earth Views", obrig)
        self.assertIn(f"| {a} | wikimedia | CC BY-SA 3.0 |", texto, "a tabela do registro continua completa")
        R.marcar_uso(self.p, a, "C03")
        self.assertIn("- " + R.obter(self.p, a)["atribuicao"], R.creditos_md(self.p, gravar=False), "o texto da descrição é o `atribuicao` do item, literal")

    def test_16_sincronizar_uso_com_o_storyboard(self):
        a = R.adicionar(self.p, dict(CC_BY_SA))
        b = R.adicionar(self.p, {"fonte": "nasa", "titulo": "Terra", "pagina_url": "https://images.nasa.gov/details/abc"})
        R.marcar_uso(self.p, b, "C09")
        (self.p / "roteiro").mkdir()
        (self.p / "roteiro" / "storyboard.json").write_text(json.dumps({"versao": 1, "cenas": [
            {"id": "C01", "broll_id": a}, {"id": "C02", "broll_id": None}, {"id": "C03", "broll_id": "B777"}, {"id": "C09", "broll_id": None}]}), encoding="utf-8")
        r = R.sincronizar_uso(self.p)
        self.assertEqual(r["marcados"], [(a, "C01")])
        self.assertEqual(r["sem_registro"], [("B777", "C03")])
        self.assertEqual(r["sobrando"], [(b, "C09")])
        self.assertEqual(R.obter(self.p, a)["usado_em"], ["C01"])
        self.assertEqual(R.obter(self.p, b)["usado_em"], ["C09"], "sincronizar não apaga marcação")

    def test_17_gravacoes_simultaneas_nao_perdem_item_nem_repetem_id(self):
        codigo = ("import sys; sys.path.insert(0, sys.argv[1]); import registro as R\n"
                  "for k in range(8):\n"
                  "    R.adicionar(sys.argv[2], {'fonte': 'nasa', 'titulo': f'proc {sys.argv[3]} item {k}', 'pagina_url': 'https://images.nasa.gov/details/x'})\n"
                  "    R.marcar_uso(sys.argv[2], 'B001', f'C{sys.argv[3]}{k}')\n")
        R.adicionar(self.p, dict(CC_BY_SA))
        procs = [subprocess.Popen([sys.executable, "-B", "-c", codigo, str(apoio.SCRIPTS), str(self.p), str(n)], stderr=subprocess.PIPE) for n in range(6)]
        erros = [p.communicate()[1].decode() for p in procs]
        self.assertEqual([p.returncode for p in procs], [0] * 6, erros)
        itens = R.carregar(self.p)["itens"]
        ids = [i["id"] for i in itens]
        self.assertEqual(len(itens), 1 + 6 * 8)
        self.assertEqual(len(set(ids)), len(ids), "id repetido")
        self.assertEqual(sorted(ids), [f"B{n:03d}" for n in range(1, 50)])
        self.assertEqual(len(R.obter(self.p, "B001")["usado_em"]), 48, "marcações simultâneas perdidas")
        self.assertTrue((self.p / "broll" / "licencas.json.bak").is_file())
        self.assertFalse(list((self.p / "broll").glob("*.parcial")))

    def test_18_registro_corrompido_da_erro_claro_e_nao_e_sobrescrito(self):
        (self.p / "broll" / "licencas.json").write_text('{"versao": 1, "itens": [', encoding="utf-8")
        with self.assertRaises(R.RegistroErro) as e:
            R.adicionar(self.p, dict(CC_BY_SA))
        self.assertIn("JSON inválido", str(e.exception))
        self.assertEqual((self.p / "broll" / "licencas.json").read_text(encoding="utf-8"), '{"versao": 1, "itens": [')

    def test_19_credito_curto_corta_o_autor_e_preserva_a_licenca(self):
        item = {"fonte": "wikimedia", "autor": "Maria Aparecida Exemplo dos Santos Oliveira", "licenca": "CC BY-SA 4.0"}
        curto = R.credito_curto(item, maximo=30)
        self.assertLessEqual(len(curto), 30)
        self.assertTrue(curto.endswith("· CC BY-SA 4.0"), curto)
        self.assertIn("…", curto)
        self.assertEqual(R.credito_curto({"fonte": "pexels", "autor": "Ana", "licenca": "Pexels License"}), "Ana / Pexels")
        self.assertEqual(R.credito_curto({"fonte": "local", "base_legal": "proprio"}), "")


    def test_20_o_texto_recebido_fica_guardado_e_a_divergencia_nao_passa(self):
        base = {"fonte": "web", "titulo": "Foto do evento", "autor": "Maria Souza", "pagina_url": "https://exemplo.org/foto"}
        with self.assertRaises(R.RegistroErro) as e:
            R.adicionar(self.p, {**base, "licenca": "Creative Commons Atribuição-SemDerivações 4.0 Internacional"})
        self.assertIn("ND proíbe", str(e.exception))
        with self.assertRaises(R.RegistroErro) as e:
            R.adicionar(self.p, {**base, "licenca": "CC BY-NC-ND 4.0", "licenca_url": "https://creativecommons.org/licenses/by/4.0/"})
        self.assertIn("CC BY-NC-ND", str(e.exception))
        for texto in ("Copyright ESA/NASA, all rights reserved", "Not in the public domain", "Não está em domínio público"):
            with self.assertRaises(R.RegistroErro, msg=texto):
                R.adicionar(self.p, {**base, "fonte": "nasa", "licenca": texto})
        self.assertEqual(R.carregar(self.p)["itens"], [])
        iid = R.adicionar(self.p, {**base, "licenca": "Creative Commons Attribution 4.0 International"})
        item = R.obter(self.p, iid)
        self.assertEqual((item["licenca"], item["licenca_id"], item["licenca_original"]), ("CC BY 4.0", "cc-by", "Creative Commons Attribution 4.0 International"))
        iid = R.adicionar(self.p, {**base, "licenca": "CC BY 2.0", "licenca_url": "https://creativecommons.org/licenses/by-sa/4.0/"})
        item = R.obter(self.p, iid)
        self.assertEqual((item["licenca_id"], item["licenca"], item["licenca_original"], item["risco"]), ("cc-by-sa", "CC BY-SA 4.0", "CC BY 2.0", "medio"))
        item = R.atualizar(self.p, iid, autor="Outra Pessoa")
        self.assertEqual(item["licenca_original"], "CC BY 2.0", "o texto original sobrevive a outras atualizações")
        self.assertTrue(R.validar(self.p)["ok"])

    def test_21_arquivo_so_dentro_de_broll_bruto_e_extensao_saneada(self):
        """Regressão: `formato` vindo da API ("/../../../CLAUDE.local.md") virava caminho e o arquivo saía de broll/bruto/."""
        tmp = self.p / "broll" / "bruto" / "_baixando" / "abc.parcial"
        tmp.parent.mkdir(parents=True)
        for ruim in ("/../../../CLAUDE.local.md", ".mp4/../../x", ". mp4", ".", "", ".tar.gz", ".MP4 ", ".aaaaaaaaa"):
            tmp.write_bytes(b"conteudo")
            with self.assertRaises(R.RegistroErro, msg=ruim) as e:
                R.adicionar(self.p, dict(CC_BY_SA), mover_de=tmp, extensao=ruim)
            self.assertIn("extensão", str(e.exception))
        self.assertTrue(tmp.is_file(), "recusa não move o arquivo")
        self.assertEqual(R.carregar(self.p)["itens"], [])
        self.assertEqual(sorted(x.name for x in self.p.iterdir()), ["broll"], "nada nasce fora de broll/")
        self.assertEqual(sorted(x.name for x in (self.p / "broll" / "bruto").iterdir()), ["_baixando"])
        iid = R.adicionar(self.p, dict(CC_BY_SA), mover_de=tmp, extensao=".MP4")
        self.assertEqual(R.obter(self.p, iid)["arquivo"], "broll/bruto/B001.mp4")
        (self.p / "solto.mp4").write_bytes(b"x")
        for fora in ("solto.mp4", "broll/tratado/x.mp4", "broll/bruto", "broll/bruto/../../solto.mp4"):
            with self.assertRaises(R.RegistroErro, msg=fora) as e:
                R.adicionar(self.p, {**CC_BY_SA, "arquivo": fora})
            self.assertIn("broll/bruto", str(e.exception))
        dados = json.loads((self.p / "broll" / "licencas.json").read_text(encoding="utf-8"))
        dados["itens"][0]["arquivo"] = "solto.mp4"                         # registro mexido à mão: validar acusa
        (self.p / "broll" / "licencas.json").write_text(json.dumps(dados), encoding="utf-8")
        r = R.validar(self.p)
        self.assertFalse(r["ok"])
        self.assertIn("broll/bruto", " ".join(r["erros"]))

    def test_22_atualizar_recalcula_o_que_depende_da_licenca(self):
        """Regressão: trocar a licença ou a base legal deixava risco, uso_comercial e exige_atribuicao da licença antiga."""
        iid = R.adicionar(self.p, {"fonte": "wikimedia", "titulo": "Mapa", "autor": "Fulano", "licenca": "Public domain", "pagina_url": "https://commons.wikimedia.org/wiki/File:M.png"})
        item = R.obter(self.p, iid)
        self.assertEqual((item["exige_atribuicao"], item["risco"]), (False, "baixo"))
        item = R.atualizar(self.p, iid, licenca="CC BY-SA 4.0")
        self.assertEqual((item["licenca_id"], item["exige_atribuicao"], item["risco"], item["uso_comercial"]), ("cc-by-sa", True, "medio", True))
        self.assertIn("CC BY-SA 4.0", item["atribuicao"])
        item = R.atualizar(self.p, iid, licenca="CC BY-NC 4.0", licenca_url=None, base_legal="citacao", notas="Trecho citado para comentar.")
        self.assertEqual((item["base_legal"], item["risco"], item["uso_comercial"], item["exige_atribuicao"]), ("citacao", "medio", False, True))
        item = R.atualizar(self.p, iid, risco="alto")
        self.assertEqual(item["risco"], "alto", "o que o chamador informa vale")
        item = R.atualizar(self.p, iid, autor="Beltrano")
        self.assertEqual(item["risco"], "alto", "mudar o autor não recalcula o risco")
        item = R.atualizar(self.p, iid, risco=None)
        self.assertEqual(item["risco"], "medio", "None pede o recálculo pela política")
        item = R.atualizar(self.p, id=iid, notas="id por nome também vale")              # o contrato escreve atualizar(projeto, id, **campos)
        self.assertEqual(item["notas"], "id por nome também vale")
        self.assertEqual(R.marcar_uso(self.p, id=iid, onde="C07"), ["C07"])
        self.assertEqual(R.desmarcar_uso(self.p, id=iid, onde="C07"), [])
        with self.assertRaises(R.RegistroErro):
            R.atualizar(self.p, risco="baixo")

    def test_23_remover_recusa_item_em_uso_e_nunca_apaga_arquivo(self):
        tmp = self.p / "entrada.webm"
        tmp.write_bytes(b"bruto")
        iid = R.adicionar(self.p, dict(CC_BY_SA), mover_de=tmp, extensao=".webm")
        tratado = self.p / "broll" / "tratado" / f"{iid}_vertical.mp4"
        tratado.parent.mkdir()
        tratado.write_bytes(b"tratado")
        tratado.with_name(tratado.name + ".da.json").write_text("{}", encoding="utf-8")
        R.registrar_tratado(self.p, iid, tratado)
        R.marcar_uso(self.p, iid, "C03")
        with self.assertRaises(R.RegistroErro) as e:
            R.remover(self.p, iid)
        self.assertIn("desmarcar-uso", str(e.exception))
        R.desmarcar_uso(self.p, iid, "C03")
        item = R.remover(self.p, iid, com_arquivos=True)
        self.assertEqual(sorted(item["movidos"]), [f"broll/_removidos/{iid}/{iid}.webm", f"broll/_removidos/{iid}/{iid}_vertical.mp4", f"broll/_removidos/{iid}/{iid}_vertical.mp4.da.json"])
        self.assertTrue(all((self.p / m).is_file() for m in item["movidos"]), "movidos, não apagados")
        self.assertFalse((self.p / "broll" / "bruto" / f"{iid}.webm").exists())
        self.assertEqual(R.carregar(self.p)["itens"], [])
        self.assertNotIn(iid, (self.p / "broll" / "creditos.md").read_text(encoding="utf-8"))
        self.assertEqual(R.adicionar(self.p, dict(CC_BY_SA)), "B002", "o id de um item removido não é reutilizado")
        with self.assertRaises(R.RegistroErro):
            R.adicionar(self.p, {**CC_BY_SA, "id": iid})
        with self.assertRaises(R.RegistroErro):
            R.remover(self.p, "B777")

    def test_25_proprio_nao_e_salvo_conduto(self):
        """Regressão: base_legal «proprio» deixava entrar vídeo de terceiro com a licença padrão do YouTube ou CC BY-NC, sem nota,
        com risco baixo, sem crédito e com uso comercial verdadeiro — e nada avisava."""
        alheio = {"fonte": "youtube", "pagina_url": "https://www.youtube.com/watch?v=zzz", "autor": "Canal Alheio", "titulo": "Clipe"}
        for licenca in ("Standard YouTube License", "CC BY-NC 4.0", "Todos os direitos reservados", "© 2024 Canal Alheio", "GFDL"):
            with self.assertRaises(R.RegistroErro, msg=licenca) as e:
                R.adicionar(self.p, {**alheio, "licenca": licenca, "base_legal": "proprio", "notas": "é nosso"})
            self.assertIn("não convive com licença de terceiro", str(e.exception))
            self.assertIn("citacao", str(e.exception))
        with self.assertRaises(R.RegistroErro) as e:              # a URL da licença também conta
            R.adicionar(self.p, {**alheio, "licenca_url": "https://creativecommons.org/licenses/by-nc/4.0/", "base_legal": "proprio", "notas": "é nosso"})
        self.assertIn("não convive", str(e.exception))
        with self.assertRaises(R.RegistroErro) as e:              # sem licença, mas veio de fora e não diz por que é da casa
            R.adicionar(self.p, {**alheio, "base_legal": "proprio"})
        self.assertIn("exige `notas`", str(e.exception))
        self.assertIn("YouTube", str(e.exception))
        with self.assertRaises(R.RegistroErro):                   # página de origem também é «de fora», mesmo com fonte local
            R.adicionar(self.p, {"fonte": "local", "titulo": "Drone", "pagina_url": "https://exemplo.org/drone", "base_legal": "proprio"})
        self.assertEqual(R.carregar(self.p)["itens"], [], "nenhuma das recusas deixou rastro")
        iid = R.adicionar(self.p, {**alheio, "autor": "Nosso Canal", "base_legal": "proprio", "notas": "Vídeo do nosso próprio canal, gravado pela equipe em 2025."})
        item = R.obter(self.p, iid)
        self.assertEqual((item["licenca"], item["base_legal"], item["risco"], item["exige_atribuicao"]), ("Material próprio", "proprio", "baixo", False))
        R.marcar_uso(self.p, iid, "C01")
        creditos = (self.p / "broll" / "creditos.md").read_text(encoding="utf-8")
        atencao = creditos.split("## Atenção antes de publicar")[1].split("##")[0]
        self.assertIn(iid, atencao)
        self.assertIn("declarado como material próprio, mas veio de YouTube", atencao)
        self.assertIn("gravado pela equipe", atencao)
        avisos = " ".join(R.validar(self.p)["avisos"])
        self.assertIn(f"{iid}: declarado como material próprio, mas veio de YouTube", avisos)
        proprio = R.adicionar(self.p, {"fonte": "local", "titulo": "Drone da equipe", "base_legal": "proprio"})      # o caso comum continua simples
        self.assertEqual(R.obter(self.p, proprio)["notas"], "")
        self.assertNotIn(f"{proprio}: declarado", " ".join(R.validar(self.p)["avisos"]))
        aberto = R.adicionar(self.p, {"fonte": "local", "titulo": "Nosso, publicado em CC BY", "autor": "Canal", "licenca": "CC BY 4.0", "base_legal": "proprio"})
        self.assertEqual(R.obter(self.p, aberto)["licenca_id"], "cc-by", "material da casa pode ter licença aberta")
        citado = R.adicionar(self.p, {**alheio, "pagina_url": "https://www.youtube.com/watch?v=abc", "licenca": "Standard YouTube License", "base_legal": "citacao",
                                      "notas": "6 s citados"})
        for campos in ({"base_legal": "proprio"}, {"base_legal": "proprio", "notas": "agora é nosso"}):                # atualizar passa pelo mesmo crivo
            with self.assertRaises(R.RegistroErro):
                R.atualizar(self.p, citado, **campos)
        self.assertEqual(R.obter(self.p, citado)["base_legal"], "citacao")
        item = R.atualizar(self.p, citado, base_legal="proprio", licenca=None, licenca_url=None, notas="O canal é nosso: vídeo publicado pela equipe.")
        self.assertEqual((item["base_legal"], item["licenca"]), ("proprio", "Material próprio"))

    def test_26_texto_de_terceiro_e_gravado_sem_caractere_de_controle(self):
        iid = R.adicionar(self.p, {**CC_BY_SA, "titulo": "Sala\nlicença: CC0\x1b[31m de servidores\u202e", "autor": "Fulana\r\nde Tal\x07"})
        item = R.obter(self.p, iid)
        self.assertEqual((item["titulo"], item["autor"]), ("Sala licença: CC0 [31m de servidores", "Fulana de Tal"))
        for campo in ("titulo", "autor", "atribuicao", "credito_tela"):
            self.assertFalse(any(ord(ch) < 32 or ch == "\u202e" for ch in item[campo]), campo)
        self.assertNotIn("\x1b", (self.p / "broll" / "creditos.md").read_text(encoding="utf-8"))

    def test_24_trecho_e_o_intervalo_da_fonte_e_o_tratamento_nao_o_regrava(self):
        iid = R.adicionar(self.p, {**CC_BY_SA, "trecho": {"t0": 50, "t1": 56}, "trecho_arquivo": {"t0": 2.1, "t1": 8.1}})
        (self.p / "broll" / "tratado").mkdir()
        (self.p / "broll" / "tratado" / "B001_vertical.mp4").write_bytes(b"x")
        R.registrar_tratado(self.p, iid, self.p / "broll" / "tratado" / "B001_vertical.mp4")
        item = R.obter(self.p, iid)
        self.assertEqual((item["trecho"], item["trecho_arquivo"]), ({"t0": 50.0, "t1": 56.0}, {"t0": 2.1, "t1": 8.1}))
        with self.assertRaises(R.RegistroErro):
            R.atualizar(self.p, iid, trecho_arquivo={"t0": 3, "t1": 1})
        self.assertNotIn("trecho_arquivo", R.atualizar(self.p, iid, trecho_arquivo=None))


class LinhaDeComando(unittest.TestCase):
    def rodar(self, *args, cwd=None):
        r = subprocess.run([sys.executable, "-B", str(apoio.SCRIPTS / "registro.py"), *args], capture_output=True, text=True, cwd=cwd,
                           stdin=subprocess.DEVNULL)      # entrada padrão vazia de verdade: herdada de um terminal, `--json -` esperaria para sempre
        return r.returncode, r.stdout, r.stderr

    def test_30_codigos_de_saida_e_mensagens(self):
        p = apoio.pasta_temporaria(self) / "projeto com espaço"
        (p / "broll").mkdir(parents=True)
        rc, out, _ = self.rodar("politica")
        self.assertEqual(rc, 0)
        self.assertIn("RECUSA", out)
        self.assertEqual(self.rodar("avaliar", "CC BY-NC 4.0")[0], 1)
        self.assertEqual(self.rodar("avaliar", "CC BY 4.0")[0], 0)
        rc, _, err = self.rodar("inexistente")
        self.assertEqual(rc, 64)
        self.assertIn("erro de uso", err)
        self.assertNotIn("Traceback", err)
        rc, _, err = self.rodar("listar", cwd=str(apoio.pasta_temporaria(self)))
        self.assertEqual(rc, 2)
        self.assertIn("--projeto", err)
        rc, out, _ = self.rodar("--projeto", str(p), "listar")
        self.assertEqual(rc, 0)
        self.assertIn("Registro vazio", out)
        item = json.dumps({"fonte": "nasa", "titulo": "Terra", "pagina_url": "https://images.nasa.gov/details/abc"})
        (p / "item.json").write_text(item, encoding="utf-8")
        rc, out, err = self.rodar("adicionar", "--json", str(p / "item.json"), cwd=str(p))
        self.assertEqual(rc, 0, err)
        self.assertIn("B001 registrado", out)
        rc, out, _ = self.rodar("marcar-uso", "B001", "C02", "C05", cwd=str(p / "broll"))      # acha o projeto subindo as pastas
        self.assertEqual(rc, 0)
        self.assertIn("C02, C05", out)
        rc, out, _ = self.rodar("atualizar", "B001", "risco=medio", 'trecho={"t0": 1, "t1": 4}', cwd=str(p))
        self.assertEqual(json.loads(out)["trecho"], {"t0": 1.0, "t1": 4.0})
        rc, _, err = self.rodar("atualizar", "B001", "licenca=CC BY-ND 4.0", "licenca_url=null", cwd=str(p))
        self.assertEqual(rc, 1)
        self.assertIn("ND proíbe", err)
        rc, out, _ = self.rodar("validar", cwd=str(p))
        self.assertEqual(rc, 0)
        self.assertIn("1 item(ns): 0 erro(s)", out)
        rc, out, _ = self.rodar("creditos", cwd=str(p))
        self.assertIn("«Terra» — NASA", out)
        self.assertTrue((p / "broll" / "creditos.md").is_file())
        for sub in ("listar", "adicionar", "atualizar", "sincronizar-uso"):
            rc, out, _ = self.rodar(sub, "--help")
            self.assertEqual(rc, 0)
            self.assertIn("uso:", out)


    def test_31_erro_de_uso_nunca_vira_traceback_e_remover_pela_linha_de_comando(self):
        p = apoio.pasta_temporaria(self) / "projeto com espaço"
        (p / "broll").mkdir(parents=True)
        (p / "lista.json").write_text("[1, 2]", encoding="utf-8")
        for args, pedaco in ((("adicionar", "--json", "não existe.json"), "não consegui ler"), (("adicionar", "--json", "lista.json"), "UM item"),
                             (("adicionar",), "--de-arquivo"), (("adicionar", "--de-arquivo", "sumiu.mp4", "--base-legal", "proprio"), "não encontrado")):
            rc, _, err = self.rodar(*args, cwd=str(p))
            self.assertIn(rc, (1, 64), args)
            self.assertIn(pedaco, err)
            self.assertNotIn("Traceback", err, args)
        self.assertEqual(self.rodar("adicionar", "--json", "lista.json", cwd=str(p))[0], 64)
        rc, _, err = self.rodar("adicionar", "--json", "-", cwd=str(p))            # entrada padrão vazia
        self.assertEqual(rc, 64)
        self.assertNotIn("Traceback", err)
        item = json.dumps({"fonte": "nasa", "titulo": "Terra", "pagina_url": "https://images.nasa.gov/details/abc"})
        (p / "item.json").write_text(item, encoding="utf-8")
        self.assertEqual(self.rodar("adicionar", "--json", "item.json", cwd=str(p))[0], 0)
        self.rodar("marcar-uso", "B001", "C02", cwd=str(p))
        rc, _, err = self.rodar("remover", "B001", cwd=str(p))
        self.assertEqual(rc, 1)
        self.assertIn("usado em C02", err)
        self.rodar("desmarcar-uso", "B001", "C02", cwd=str(p))
        rc, out, err = self.rodar("remover", "B001", cwd=str(p))
        self.assertEqual(rc, 0, err)
        self.assertIn("B001 removido", out)
        rc, out, _ = self.rodar("listar", cwd=str(p))
        self.assertIn("Registro vazio", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
