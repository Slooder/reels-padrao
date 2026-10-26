"""Provedores com respostas simuladas (trechos de respostas reais de 2026-10-07 em _dados/; Pexels e Pixabay montados a
partir da documentação, porque não há chave nesta máquina), chaves, identificação e segurança de endereços. Sem rede."""
import os
import subprocess
import unittest
import urllib.parse

from testes import apoio

import comum
import provedores as P


class Normalizacao(unittest.TestCase):
    def setUp(self):
        self.tmp = apoio.pasta_temporaria(self)
        self.http = apoio.HttpFalso()

    def test_01_nasa_busca_e_detalhe(self):
        prov = P.Nasa(self.http)
        self.assertEqual(prov.disponivel(), (True, ""))
        cands = prov.buscar("earth from space", "video", None, 5)
        self.assertEqual(len(cands), 2)
        c = cands[0]
        self.assertEqual((c["fonte"], c["tipo"], c["licenca_id"], c["permitida"], c["exige_atribuicao"], c["autor"]), ("nasa", "video", "nasa", True, True, "NASA"))
        self.assertEqual(c["pagina_url"], "https://images.nasa.gov/details/Earth%20Views%20from%20the%20International%20Space%20Station")
        self.assertTrue(c["miniatura_url"].startswith("https://images-assets.nasa.gov/video/Earth%20Views"), c["miniatura_url"])
        self.assertFalse(c["detalhado"])
        self.assertIn("media_type=video", self.http.chamadas[0][0])
        c = prov.detalhar(c)
        rotulos = [a["rotulo"] for a in c["arquivos"]]
        self.assertEqual(sorted(rotulos), ["large", "medium", "mobile", "orig", "preview", "small"])
        orig = next(a for a in c["arquivos"] if a["rotulo"] == "orig")
        self.assertEqual((orig["largura"], orig["altura"], orig["duracao"]), (1280, 720, 200.0))
        self.assertTrue(all(a["url"].startswith("https://") and " " not in a["url"] for a in c["arquivos"]), "a NASA devolve http:// e espaços: têm de sair limpos")
        self.assertEqual((c["largura"], c["altura"], c["duracao"]), (1280, 720, 200.0))
        n = self.http.pedidos
        prov.detalhar(c)
        self.assertEqual(self.http.pedidos, n, "candidato já detalhado não gera pedido")

    def test_02_nasa_imagem_ja_traz_versoes_e_aviso_de_terceiros(self):
        prov = P.Nasa(self.http)
        c = prov.buscar("circuit board", "imagem", None, 3)[0]
        self.assertEqual(c["autor"], "NASA/MSFC")
        self.assertGreaterEqual(len(c["arquivos"]), 2)
        self.assertEqual(c["avisos"], [])
        self.assertTrue(prov._de_terceiros("Image credit: ESA/Hubble & J. Doe"))
        self.assertTrue(prov._de_terceiros("Photo © 2020 Maxar Technologies"))
        self.assertFalse(prov._de_terceiros("Image Credit: NASA/JPL-Caltech"))
        self.assertFalse(prov._de_terceiros("Technicians remove one of the circuit boards.", "NASA/JPL"))
        self.assertTrue(prov._de_terceiros("Rover test.", "SpaceX"))

    def test_03_wikimedia_video_licenca_autor_e_versoes(self):
        prov = P.Wikimedia(self.http)
        cands = prov.buscar("server room", "video", None, 2)
        self.assertEqual(len(cands), 2)
        self.assertIn("%22server+room%22+filetype%3Avideo", self.http.chamadas[0][0], "frase exata primeiro")
        c = next(c for c in cands if c["titulo"] == "Green IT")
        self.assertEqual((c["licenca"], c["licenca_id"], c["permitida"], c["exige_atribuicao"], c["risco"]), ("CC BY-SA 3.0", "cc-by-sa", True, True, "medio"))
        self.assertEqual(c["licenca_url"], "https://creativecommons.org/licenses/by-sa/3.0")
        self.assertEqual((c["largura"], c["altura"]), (640, 360))
        self.assertAlmostEqual(c["duracao"], 404.92)
        self.assertNotIn("<", c["autor"])
        self.assertEqual(c["pagina_url"], "https://commons.wikimedia.org/wiki/File:Green_IT.ogv")
        self.assertNotIn("utm_", c["arquivos"][0]["url"])
        self.assertEqual(c["arquivos"][0]["rotulo"], "original")
        webm = [a for a in c["arquivos"] if a["formato"] == "webm"]
        self.assertTrue(webm and webm[0]["bytes_estimado"])
        self.assertEqual(c["casou"], "frase")
        self.assertIn("User-Agent", comum.agente() and "User-Agent")

    def test_04_wikimedia_imagem_tem_versao_de_1920_e_miniatura_de_500(self):
        c = P.Wikimedia(self.http).buscar("circuit board", "imagem", None, 2)[0]
        self.assertEqual((c["tipo"], c["licenca_id"]), ("imagem", "cc-by"))
        self.assertIn("iiurlwidth=1920", self.http.chamadas[0][0])
        self.assertIn("/500px-", c["miniatura_url"])
        self.assertEqual([a["rotulo"] for a in c["arquivos"]][0], "original")

    def test_05_archive_busca_por_campo_e_detalha_arquivos(self):
        prov = P.Archive(self.http)
        cands = prov.buscar("server room", "video", None, 2)
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(self.http.chamadas[0][0]).query)["q"][0]
        self.assertIn('title:(server AND room)', q)
        self.assertIn("mediatype:movies", q)
        self.assertIn("licenseurl:*creativecommons.org*", q)
        c = cands[0]
        self.assertEqual((c["fonte"], c["licenca_id"], c["permitida"]), ("archive", "pd", True))
        self.assertTrue(any("não a garante" in a for a in c["avisos"]))
        self.assertEqual((c["risco"], c["conferir_origem"]), ("medio", True), "licença declarada por quem subiu o item: nasce com risco médio")
        self.assertIn("NOT licenseurl:*-nc*", q, "NC e ND ficam de fora já na consulta")
        self.assertIn("NOT licenseurl:*-nd*", q)
        c = prov.detalhar(c)
        formatos = {a["formato"] for a in c["arquivos"]}
        self.assertIn("mp4", formatos)
        self.assertNotIn("gif", formatos)
        mp4 = next(a for a in c["arquivos"] if a["formato"] == "mp4")
        self.assertEqual((mp4["largura"], mp4["altura"], mp4["bytes"]), (640, 480, 78054869))
        self.assertAlmostEqual(mp4["duracao"], 750.65)
        self.assertTrue(mp4["url"].startswith("https://archive.org/download/612Magic1958/"))
        self.assertTrue(all("thumbs" not in a["url"] for a in c["arquivos"]))

    def test_06_openverse_so_imagem_e_recusa_nc(self):
        prov = P.Openverse(self.http)
        self.assertEqual(prov.tipos, ("imagem",))
        cands = prov.buscar("circuit board", "imagem", "horizontal", 5)
        self.assertIn("aspect_ratio=wide", self.http.chamadas[0][0])
        self.assertIn("license_type=commercial%2Cmodification", self.http.chamadas[0][0])
        por_licenca = {c["licenca_id"]: c for c in cands}
        self.assertFalse(por_licenca["cc-by-nc"]["permitida"])
        ok, motivo = P.passa(por_licenca["cc-by-nc"])
        self.assertFalse(ok)
        self.assertIn("recusada", motivo)
        bom = next(c for c in cands if c["permitida"])
        self.assertTrue(any("não verifica a licença" in a for a in bom["avisos"]))
        self.assertTrue(all(c["conferir_origem"] and c["risco"] in ("medio", "alto") for c in cands), "o Openverse não confere a licença: nada sai dele com risco baixo")
        self.assertIsNone(prov.hosts_arquivo, "o arquivo do Openverse mora no site de origem")

    def test_07_pexels_e_pixabay_pulam_sem_chave_e_nunca_mostram_a_chave(self):
        for classe, var in ((P.Pexels, "PEXELS_API_KEY"), (P.Pixabay, "PIXABAY_API_KEY")):
            ok, motivo = classe(self.http).disponivel()
            self.assertFalse(ok)
            self.assertIn(var, motivo)
            self.assertIn("chaves.env", motivo)
        self.assertEqual(self.http.pedidos, 0, "sem chave não sai pedido")
        home = comum.video_ops_home()
        home.mkdir(parents=True, exist_ok=True)
        (home / "chaves.env").write_text('# chaves de teste\nexport PEXELS_API_KEY="segredo-pexels-123"\nPIXABAY_API_KEY=segredo&pixabay 456\n', encoding="utf-8")
        cands = P.Pexels(self.http).buscar("sala de servidores", "video", "horizontal", 4, "pt")
        url, cab = self.http.chamadas[-1]
        self.assertTrue(url.startswith("https://api.pexels.com/v1/videos/search?"))
        self.assertEqual(cab.get("Authorization"), "segredo-pexels-123")
        self.assertIn("locale=pt-BR", url)
        self.assertIn("orientation=landscape", url)
        self.assertNotIn("segredo", url)
        c = cands[0]
        self.assertEqual((c["licenca_id"], c["exige_atribuicao"], c["autor"], c["duracao"]), ("pexels", False, "Ana Lima", 14.0))
        self.assertEqual(len(c["arquivos"]), 3, "HLS fica de fora")
        self.assertEqual(c["titulo"], "server room with blinking lights")
        cands = P.Pixabay(self.http).buscar("servidor", "video", None, 4, "pt")
        url, _ = self.http.chamadas[-1]
        self.assertIn("key=segredo%26pixabay+456", url, "o Pixabay só aceita a chave na URL")
        self.assertNotIn("segredo", comum.mascarar(url))
        self.assertNotIn("segredo", comum.mascarar(f"falhou em {url} com a chave segredo&pixabay 456 e segredo-pexels-123"))
        self.assertEqual((cands[0]["licenca_id"], cands[0]["largura"], cands[0]["altura"]), ("pixabay", 1920, 1080))
        self.assertEqual(len(cands[0]["arquivos"]), 4)
        foto = P.Pexels(self.http).buscar("circuit board", "imagem", None, 2)[0]
        self.assertEqual((foto["tipo"], foto["autor"], foto["largura"]), ("imagem", "João Souza", 6000))
        img = P.Pixabay(self.http).buscar("circuit", "imagem", "vertical", 3)[0]
        self.assertIn("orientation=vertical", self.http.chamadas[-1][0])
        self.assertEqual(img["arquivos"][0]["largura"], 1280)

    def test_08_ordenar_filtrar_e_escolher_versao(self):
        base = dict(permitida=True, exige_atribuicao=False, tipo="video", avisos=[], risco="baixo")
        bom = dict(base, largura=1920, altura=1080, duracao=12.0)
        longo = dict(base, largura=1920, altura=1080, duracao=3600.0)
        pequeno = dict(base, largura=640, altura=360, duracao=12.0)
        recusado = dict(base, permitida=False, largura=3840, altura=2160, duracao=12.0)
        credito = dict(base, exige_atribuicao=True, largura=1920, altura=1080, duracao=12.0)
        notas = {k: P.pontuar(v) for k, v in dict(bom=bom, longo=longo, pequeno=pequeno, recusado=recusado, credito=credito).items()}
        ordem = sorted(notas, key=notas.get, reverse=True)
        self.assertEqual((ordem[:2], ordem[-1]), (["bom", "credito"], "recusado"), notas)
        self.assertLess(notas["longo"], notas["credito"], "vídeo de uma hora não é b-roll: fica abaixo do clipe curto")
        self.assertGreater(P.pontuar(dict(bom, largura=1080, altura=1920), "vertical"), P.pontuar(bom, "vertical"))
        self.assertGreater(P.pontuar(bom), P.pontuar(dict(bom, casou="palavras soltas")))
        self.assertGreater(P.pontuar(credito), P.pontuar(dict(bom, risco="medio", conferir_origem=True, avisos=["licença declarada"])),
                           "licença só declarada por quem subiu fica abaixo até do equivalente que exige crédito")
        self.assertEqual(P.passa(recusado)[0], False)
        self.assertEqual(P.passa(recusado, licenca="todas")[0], True)
        self.assertEqual(P.passa(credito, licenca="sem-atribuicao")[0], False)
        self.assertEqual(P.passa(bom, min_duracao=20)[0], False)
        self.assertEqual(P.passa(longo, max_duracao=600)[0], False)
        self.assertEqual(P.passa(dict(bom, duracao=None), min_duracao=20)[0], True, "valor desconhecido não elimina")
        self.assertEqual(P.passa(pequeno, min_altura=720)[0], False)
        arqs = [{"url": "u4k", "largura": 3840, "altura": 2160, "bytes": 300_000_000, "formato": "mp4", "rotulo": "uhd"},
                {"url": "uhd", "largura": 1920, "altura": 1080, "bytes": 40_000_000, "formato": "mp4", "rotulo": "hd"},
                {"url": "usd", "largura": 960, "altura": 540, "bytes": 8_000_000, "formato": "mp4", "rotulo": "sd"}]
        c = {"arquivos": arqs}
        self.assertEqual(P.escolher_arquivo(c, 1080)["url"], "uhd", "a MENOR versão que alcança o alvo")
        self.assertEqual(P.escolher_arquivo(c, 720)["url"], "uhd")
        self.assertEqual(P.escolher_arquivo(c, 1080, teto_bytes=20_000_000)["url"], "usd", "com teto, desce de versão")
        self.assertIsNone(P.escolher_arquivo(c, 1080, teto_bytes=1_000_000))
        self.assertEqual([a["url"] for a in P.ordenar_arquivos(c, 1080)], ["uhd", "u4k", "usd"])
        cegos = {"arquivos": [{"url": "o", "rotulo": "orig", "largura": 1280, "altura": 720}, {"url": "l", "rotulo": "large"}, {"url": "m", "rotulo": "medium"}]}
        self.assertEqual([a["url"] for a in P.ordenar_arquivos(cegos, 1080)], ["l", "m", "o"], "sem tamanho conhecido, vai pelo rótulo antes do que é pequeno")
        self.assertEqual(P.orientacao_de(1920, 1080), "horizontal")
        self.assertEqual(P.orientacao_de(1080, 1920), "vertical")
        self.assertEqual(P.orientacao_de(1000, 1000), "quadrado")
        self.assertIsNone(P.orientacao_de(None, 100))

    def test_09_wikimedia_so_e_consultada_com_contato(self):
        """A política de User-Agent da Wikimedia exige contato: sem VIDEO_OPS_CONTATO o provedor é pulado, não consultado."""
        ok, motivo = P.Wikimedia(self.http).disponivel()
        self.assertFalse(ok)
        self.assertIn("VIDEO_OPS_CONTATO", motivo)
        self.assertIn("não invente", motivo)
        os.environ["VIDEO_OPS_CONTATO"] = "https://exemplo.com/canal"
        self.assertEqual(P.Wikimedia(self.http).disponivel(), (True, ""))
        self.assertTrue(P.Archive(self.http).avisos(), "o Internet Archive pede o modelo do agente: avisa quando falta")
        os.environ["VIDEO_OPS_AGENTE"] = "modelo-x"
        self.assertEqual(P.Archive(self.http).avisos(), [])

    def test_10_texto_de_terceiro_nao_leva_controle_para_o_terminal(self):
        """Regressão: título com \\n e sequência ANSI forjava uma linha «licença: CC0» no plano de download."""
        c = P.candidato("nasa", "video", "x", "Título\nlicença: CC0\x1b[31m com\u202e controle", "https://images.nasa.gov/details/x", "NASA", autor="Fulano\r\nde Tal\x07")
        self.assertEqual(c["titulo"], "Título licença: CC0 [31m com controle")
        self.assertEqual(c["autor"], "Fulano de Tal")
        self.assertEqual(comum.sem_controle("fora\nlicença: CC0\x1b[31m.mp4"), "fora licença: CC0 [31m.mp4")
        self.assertEqual(comum.sem_controle(None), "")


class Seguranca(unittest.TestCase):
    def setUp(self):
        self.tmp = apoio.pasta_temporaria(self)

    def test_20_so_https_e_so_os_hosts_do_provedor(self):
        nasa = ("nasa.gov",)
        self.assertTrue(comum.host_permitido("https://images-assets.nasa.gov/video/x.mp4", nasa))
        self.assertTrue(comum.host_permitido("https://nasa.gov/x", nasa))
        self.assertFalse(comum.host_permitido("http://images-assets.nasa.gov/video/x.mp4", nasa), "http é recusado")
        self.assertFalse(comum.host_permitido("https://evilnasa.gov/x.mp4", nasa))
        self.assertFalse(comum.host_permitido("https://nasa.gov.exemplo.com/x.mp4", nasa))
        self.assertFalse(comum.host_permitido("https://exemplo.com/?u=nasa.gov", nasa))
        self.assertFalse(comum.host_permitido("file:///etc/passwd", nasa))
        self.assertFalse(comum.host_permitido("http://127.0.0.1:8000/x", nasa), "host local só com a variável de teste")
        self.assertFalse(comum.host_permitido("https://10.0.0.5/x.jpg", None), "host «qualquer» não inclui rede privada")
        self.assertFalse(comum.host_permitido("https://127.0.0.1/x.jpg", None))
        os.environ["VIDEO_BROLL_PERMITIR_LOCAL"] = "1"
        self.assertTrue(comum.host_permitido("http://127.0.0.1:8000/x", nasa))
        with self.assertRaises(comum.Erro):
            comum.Http().abrir("https://exemplo.invalid/x", nasa)

    def test_21_url_limpa(self):
        self.assertEqual(comum.url_limpa("http://images-assets.nasa.gov/video/Earth Views/Earth Views~orig.mp4"),
                         "https://images-assets.nasa.gov/video/Earth%20Views/Earth%20Views~orig.mp4")
        self.assertEqual(comum.url_limpa("https://upload.wikimedia.org/a/b/X.ogv?utm_source=commons&utm_campaign=api&utm_content=original"),
                         "https://upload.wikimedia.org/a/b/X.ogv")
        self.assertEqual(comum.url_limpa("https://upload.wikimedia.org/a/Aurora_%282009%29.jpg"), "https://upload.wikimedia.org/a/Aurora_(2009).jpg")
        self.assertEqual(comum.url_limpa("https://x.org/a?b=1&utm_x=2"), "https://x.org/a?b=1")

    def test_22_identificacao_sem_dado_do_usuario_por_padrao(self):
        ua = comum.agente()
        self.assertTrue(ua.startswith(f"video-broll/{comum.VERSAO} ("))
        self.assertIn("contato nao configurado", ua)
        self.assertNotIn("@", ua)
        ua.encode("latin-1")                                  # cabeçalho HTTP: sem acento
        os.environ["VIDEO_OPS_CONTATO"] = "https://exemplo.com/canal"
        os.environ["VIDEO_OPS_AGENTE"] = "modelo-x 1.0 (teste)"
        ua = comum.agente()
        self.assertIn("https://exemplo.com/canal", ua)
        self.assertTrue(ua.endswith("(modelo-x1.0teste)"), ua)

    def test_23_chaves_e_utilidades(self):
        self.assertIsNone(comum.chave("PEXELS_API_KEY"))
        os.environ["PEXELS_API_KEY"] = "  do-ambiente  "
        self.assertEqual(comum.chave("PEXELS_API_KEY"), "do-ambiente")
        self.assertEqual(comum.mascarar("Authorization: do-ambiente"), "Authorization: ***")
        self.assertEqual(comum.mascarar("https://pixabay.com/api/?key=abc123&q=x"), "https://pixabay.com/api/?key=***&q=x")
        self.assertEqual(comum.segundos("0:03:20"), 200.0)
        self.assertEqual(comum.segundos("12:30"), 750.0)
        self.assertEqual(comum.segundos("750.65"), 750.65)
        self.assertEqual(comum.segundos("12.5 s"), 12.5)
        self.assertIsNone(comum.segundos("abc"))
        self.assertEqual(comum.slug("Terra vista do espaço!"), "terra-vista-do-espaco")
        self.assertEqual(comum.duracao_legivel(3725), "1:02:05")
        self.assertEqual(comum.duracao_legivel(75), "1:15")
        self.assertEqual(comum.duracao_legivel(5.7), "5,7 s")
        self.assertEqual(comum.tamanho_legivel(12_300_000), "12,3 MB")

    def test_24_o_contato_ficticio_dos_testes_nunca_sai_da_maquina(self):
        """Regressão: a suíte, com rede, consultava Wikimedia, NASA, Internet Archive e Openverse com um contato inventado.
        Agora o contato fictício é opcional (padrão: nenhum) e, com ele no ambiente, comum.Http só fala com 127.0.0.1."""
        self.assertIsNone(os.environ.get("VIDEO_OPS_CONTATO"), "pasta_temporaria() não define contato por padrão")
        self.assertNotIn(apoio.CONTATO_DE_TESTE, comum.agente())
        apoio.pasta_temporaria(self, contato=True)
        self.assertIn(apoio.CONTATO_DE_TESTE, comum.agente())
        for url, hosts in (("https://commons.wikimedia.org/w/api.php?action=query", P.Wikimedia.hosts), ("https://images-api.nasa.gov/search?q=x", P.Nasa.hosts),
                           ("https://archive.org/advancedsearch.php?q=x", P.Archive.hosts), ("https://api.openverse.org/v1/images/?q=x", P.Openverse.hosts)):
            with self.assertRaises(AssertionError, msg=url) as e:
                comum.Http(tentativas=1).abrir(url, hosts)
            self.assertIn("contato fictício", str(e.exception))
        base, srv = apoio.servidor(self, {"/x.json": b"{}"})
        self.assertEqual(comum.Http().json(base + "/x.json", ("nasa.gov",)), {}, "o servidor local continua acessível")
        self.assertIn(apoio.CONTATO_DE_TESTE, srv.pedidos[0][3])
        import testes.test_rede as rede
        import inspect
        self.assertNotIn("contato=True", inspect.getsource(rede), "teste de rede não pode pedir o contato fictício")

    def test_25_a_chave_nao_chega_ao_disco_nem_que_o_provedor_a_devolva(self):
        """Regressão: cache, JSON da busca, plano e --json não passavam por nenhuma máscara."""
        os.environ["PIXABAY_API_KEY"] = "PIXFALSA-9f3+a/Zq=77"
        chave = comum.chave("PIXABAY_API_KEY")
        eco = f"https://pixabay.com/api/videos/?key={urllib.parse.quote(chave, safe='')}&q=x"
        dados = comum.mascarar_dados({"url": eco, "lista": [f"Authorization: {chave}", 3, None], "ok": "https://cdn.exemplo.com/v.mp4?token=assinado-do-cdn",
                                      chave: "até em nome de campo"})
        texto = repr(dados)
        self.assertNotIn("PIXFALSA", texto)
        self.assertNotIn("9f3%2B", texto)
        self.assertEqual(dados["lista"][1:], [3, None])
        self.assertEqual(dados["ok"], "https://cdn.exemplo.com/v.mp4?token=assinado-do-cdn", "token que não é segredo do usuário (endereço assinado) não é mexido")
        self.assertEqual(comum.mascarar(f"falhou em {eco.replace('%2B', '%2b')}"), "falhou em https://pixabay.com/api/videos/?key=***&q=x", "%2b minúsculo também")
        import buscar
        c = {"titulo": "Vídeo", "avisos": [], "miniatura_url": eco, "arquivos": [{"url": eco, "rotulo": "com chave"}, {"url": "https://cdn.pixabay.com/v.mp4", "rotulo": "limpo"}]}
        limpo = buscar.sem_segredo(c)
        self.assertEqual([a["rotulo"] for a in limpo["arquivos"]], ["limpo"], "versão cujo endereço trazia a chave é descartada")
        self.assertNotIn("PIXFALSA", repr(limpo))
        self.assertTrue(any("chave de API" in a for a in limpo["avisos"]))
        intacto = {"titulo": "Vídeo", "avisos": [], "arquivos": [{"url": "https://cdn.pixabay.com/v.mp4"}]}
        self.assertEqual(buscar.sem_segredo(intacto), intacto)

    def test_26_python_sem_pillow_recebe_instrucao_e_nao_erro_interno(self):
        """Regressão: /usr/bin/python3 respondia «erro interno: ModuleNotFoundError: No module named 'PIL'»."""
        candidato = "/usr/bin/python3"
        if not os.path.exists(candidato) or subprocess.run([candidato, "-c", "import PIL"], capture_output=True).returncode == 0:
            self.skipTest("não há nesta máquina um python3 sem Pillow para provocar o erro")
        r = subprocess.run([candidato, "-B", str(apoio.SCRIPTS / "buscar.py"), "x", "--projeto", str(self.tmp)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn("não tem o Pillow", r.stderr)
        self.assertIn("/opt/homebrew/bin/python3", r.stderr)
        self.assertNotIn("erro interno", r.stderr)
        self.assertNotIn("Traceback", r.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
