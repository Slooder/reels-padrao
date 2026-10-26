"""Busca (provedores simulados), folha de contato e download contra um servidor em 127.0.0.1 — nada sai para a internet.
Precisa do kit de direção de arte (projeto com DA) e do ffmpeg/ffprobe para gerar e validar o vídeo de teste."""
import contextlib
import hashlib
import io
import json
import os
import re
import time
import unittest
from pathlib import Path
from unittest import mock

from testes import apoio

import baixar
import buscar
import comum
import registro


def _quieto(fn, *args, **kw):
    """Roda a função engolindo o progresso que ela imprime."""
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kw)


def _saida(fn, *args):
    """(código, stdout, stderr) de um main(argv) rodado dentro do processo, como comum.rodar faria."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            rc = comum.rodar(lambda: fn(list(args)))
        except SystemExit as e:
            rc = e.code
    return rc, out.getvalue(), err.getvalue()


def _codigo(saida: str) -> str:
    """O código de plano que baixar.py imprime no fim do plano."""
    m = re.search(r"Código deste plano: ([0-9a-f]{8})", saida)
    assert m, f"o plano não imprimiu código:\n{saida}"
    return m.group(1)


class Busca(unittest.TestCase):
    def setUp(self):
        self.tmp = apoio.pasta_temporaria(self, contato=True)      # HTTP simulado: o contato fictício não sai da máquina (guarda em apoio.py)
        self.raiz, self.d = apoio.projeto(self.tmp)
        self.http = apoio.HttpFalso()

    def test_01_busca_normaliza_ordena_grava_e_usa_o_cache(self):
        r = buscar.buscar(self.d, "sala de servidores", "server room", "video", http=self.http, avisar=lambda m: None)
        arq = self.raiz / "broll" / "_busca" / "sala-de-servidores.json"
        self.assertEqual(Path(r["arquivo"]).resolve(), arq.resolve())
        self.assertTrue(arq.is_file())
        fontes = {c["fonte"] for c in r["candidatos"]}
        self.assertEqual(fontes, {"nasa", "wikimedia"})
        self.assertEqual(r["filtros"]["max_duracao"], 600.0, "padrão: vídeo de mais de 10 min é palestra ou filme e fica de fora")
        self.assertEqual({(f["fonte"], f["motivo"]) for f in r["fora"] if f["fonte"] == "archive"}, {("archive", "longo demais (751 s)")})
        self.assertFalse(r["provedores"]["pexels"]["ok"])
        self.assertIn("PEXELS_API_KEY", r["provedores"]["pexels"]["aviso"])
        self.assertIn("só tem imagem", r["provedores"]["openverse"]["aviso"])
        self.assertEqual([c["n"] for c in r["candidatos"]], list(range(1, len(r["candidatos"]) + 1)))
        self.assertEqual([c["pontos"] for c in r["candidatos"]], sorted((c["pontos"] for c in r["candidatos"]), reverse=True))
        self.assertTrue(all(c["permitida"] for c in r["candidatos"]))
        nasa = next(c for c in r["candidatos"] if c["fonte"] == "nasa")
        self.assertTrue(nasa["detalhado"] and nasa["arquivos"], "NASA e Internet Archive já saem detalhados da busca")
        pedidos = self.http.pedidos
        r2 = buscar.buscar(self.d, "sala de servidores", "server room", "video", http=self.http, avisar=lambda m: None)
        self.assertEqual(self.http.pedidos, pedidos, "segunda busca igual sai toda do cache de 24 h")
        self.assertTrue(r2["provedores"]["nasa"]["do_cache"])
        self.assertEqual([c["id_fonte"] for c in r2["candidatos"]], [c["id_fonte"] for c in r["candidatos"]])
        buscar.buscar(self.d, "sala de servidores", "server room", "video", http=self.http, sem_cache=True, avisar=lambda m: None)
        self.assertGreater(self.http.pedidos, pedidos)
        cache = "".join(p.read_text(encoding="utf-8") for p in (self.raiz / "broll" / "_busca" / "_cache").glob("*.json"))
        self.assertNotIn("key=", cache)
        longos = buscar.buscar(self.d, "sala de servidores", "server room", "video", max_duracao=0, http=self.http, avisar=lambda m: None)
        self.assertEqual({c["fonte"] for c in longos["candidatos"]}, {"nasa", "wikimedia", "archive"}, "--max-duracao 0 tira o limite")
        self.assertEqual(longos["slug"], "sala-de-servidores-2", "mesma consulta com outro filtro não sobrescreve a busca anterior")
        self.assertEqual(json.loads(arq.read_text(encoding="utf-8"))["assinatura"], r["assinatura"], "a primeira busca continua intacta")
        self.assertEqual(buscar.carregar_busca(self.raiz, "sala de servidores")["variantes"], ["sala-de-servidores-2"])
        arquivo = next(c for c in longos["candidatos"] if c["fonte"] == "archive")
        self.assertEqual((arquivo["risco"], buscar.rotulo_licenca(arquivo)), ("medio", ("Domínio público · confira a origem", "alerta")),
                         "Internet Archive: a licença é a declarada por quem subiu — nunca sai com sinal verde")

    def test_02_filtros_e_licencas(self):
        r = buscar.buscar(self.d, "circuito eletrônico", "circuit board", "imagem", fontes=["openverse"], http=self.http, avisar=lambda m: None)
        self.assertTrue(all(c["licenca_id"] != "cc-by-nc" for c in r["candidatos"]))
        self.assertTrue(any("recusada" in f["motivo"] for f in r["fora"]))
        r = buscar.buscar(self.d, "circuito eletrônico", "circuit board", "imagem", fontes=["openverse"], licenca="todas", http=self.http, avisar=lambda m: None)
        self.assertTrue(any(c["licenca_id"] == "cc-by-nc" and not c["permitida"] for c in r["candidatos"]))
        self.assertFalse(r["candidatos"][-1]["permitida"], "o que a política recusa vai para o fim da lista")
        r = buscar.buscar(self.d, "sala de servidores", "server room", "video", fontes=["wikimedia"], max_duracao=60, http=self.http, avisar=lambda m: None)
        self.assertEqual(r["candidatos"], [])
        self.assertTrue(all("longo demais" in f["motivo"] for f in r["fora"]))
        with self.assertRaises(comum.Erro):
            buscar.buscar(self.d, "x", fontes=["getty"], http=self.http)

    def test_03_com_chave_os_provedores_pagos_entram_e_a_chave_nao_vaza(self):
        os.environ["PEXELS_API_KEY"] = "chave-secreta-de-teste"
        os.environ["PIXABAY_API_KEY"] = "outra-chave-secreta"
        r = buscar.buscar(self.d, "sala de servidores", "server room", "video", fontes=["pexels", "pixabay"], http=self.http, avisar=lambda m: None)
        self.assertEqual({c["fonte"] for c in r["candidatos"]}, {"pexels", "pixabay"})
        self.assertEqual(r["candidatos"][0]["exige_atribuicao"], False)
        tudo = "".join(p.read_text(encoding="utf-8") for p in (self.raiz / "broll" / "_busca").rglob("*.json"))
        self.assertNotIn("chave-secreta-de-teste", tudo)
        self.assertNotIn("outra-chave-secreta", tudo)

    def test_04_falha_de_um_provedor_nao_derruba_a_busca(self):
        regras = [("images-api.nasa.gov", comum.Erro("images-api.nasa.gov respondeu HTTP 503"))] + apoio.regras()
        avisos = []
        r = buscar.buscar(self.d, "terra", "earth", "video", fontes=["nasa", "wikimedia"], http=apoio.HttpFalso(regras), avisar=avisos.append)
        self.assertFalse(r["provedores"]["nasa"]["ok"])
        self.assertIn("503", " ".join(avisos))
        self.assertTrue(r["candidatos"])

    def test_04b_sem_rede_em_tudo_sai_com_75(self):
        fora = comum.Erro("sem resposta de x depois de 3 tentativa(s)", codigo=comum.SAIDA_SEM_REDE)
        regras = [("nasa.gov", fora), ("wikimedia.org", fora)]
        with self.assertRaises(comum.Erro) as e:
            buscar.buscar(self.d, "terra", "earth", "video", fontes=["nasa", "wikimedia"], http=apoio.HttpFalso(regras), avisar=lambda m: None)
        self.assertEqual(e.exception.codigo, 75)
        self.assertIn("sem conexão", str(e.exception))

    def test_05_folha_de_contato_e_nao_faca(self):
        r = buscar.buscar(self.d, "Terra vista do espaço", "earth from space", "video", http=self.http, avisar=lambda m: None)
        png = buscar.folha(self.d, r, http=self.http)
        self.assertEqual(png.resolve(), (self.raiz / "broll" / "_busca" / "terra-vista-do-espaco.png").resolve())
        from PIL import Image
        with Image.open(png) as im:
            self.assertGreater(im.width, 1200)
            self.assertGreater(im.height, 400)
            self.assertEqual(im.convert("RGB").getpixel((3, 3)), self.d.rgb("fundo"), "a folha é desenhada com os tokens da DA")
        self.assertTrue(list((self.raiz / "broll" / "_busca" / "_mini").glob("*.img")))
        regras = self.d["conceito"]["nao_faca"]
        self.assertTrue(buscar.bater_com_nao_faca(["robô humanoide brilhante", "glowing brain"], regras))
        self.assertEqual(buscar.bater_com_nao_faca(["sala de servidores", "server room"], regras), [])
        self.assertEqual(buscar.rotulo_licenca({"permitida": True, "exige_atribuicao": True, "licenca": "CC BY 4.0", "licenca_id": "cc-by"}), ("CC BY 4.0 · crédito obrigatório", "alerta"))
        self.assertEqual(buscar.rotulo_licenca({"permitida": False, "licenca": "CC BY-NC 4.0"})[1], "negativo")
        declarada = {"permitida": True, "exige_atribuicao": True, "licenca": "CC BY 4.0", "licenca_id": "cc-by", "risco": "medio", "conferir_origem": True}
        self.assertEqual(buscar.rotulo_licenca(declarada), ("CC BY 4.0 · crédito obrigatório · confira a origem", "alerta"))
        self.assertEqual(buscar.rotulo_licenca(declarada, curto=True), ("CC BY 4.0 · crédito · confira a origem", "alerta"))
        self.assertEqual(buscar.rotulo_licenca({"permitida": True, "exige_atribuicao": False, "licenca_id": "pd", "risco": "medio", "conferir_origem": True}),
                         ("Domínio público · confira a origem", "alerta"))
        self.assertEqual(buscar.rotulo_licenca({"permitida": True, "exige_atribuicao": False, "licenca_id": "pexels", "risco": "baixo"}), ("Pexels · crédito opcional", "positivo"))
        self.assertEqual(buscar.rotulo_licenca({"permitida": True, "exige_atribuicao": True, "licenca": "CC BY-SA 3.0", "licenca_id": "cc-by-sa", "risco": "medio"}),
                         ("CC BY-SA 3.0 · crédito obrigatório", "alerta"), "risco médio do ShareAlike não é dúvida sobre a origem")
        imagens = buscar.buscar(self.d, "circuito eletrônico", "circuit board", "imagem", fontes=["openverse"], http=self.http, avisar=lambda m: None)
        self.assertTrue(imagens["candidatos"])
        self.assertTrue(all(buscar.rotulo_licenca(c)[1] == "alerta" and "confira a origem" in buscar.rotulo_licenca(c)[0] for c in imagens["candidatos"]),
                        "Openverse: nenhum candidato com sinal verde")

    def test_06_cli_sem_da_sai_com_2_e_uso_errado_com_64(self):
        vazio = self.tmp / "pasta sem projeto"
        vazio.mkdir()
        rc, _, err = _saida(buscar.main, "sala de servidores", "--projeto", str(vazio))
        self.assertEqual(rc, 2)
        self.assertIn("video-direcao-de-arte", err)
        rc, _, err = _saida(buscar.main, "x", "--por-fonte", "99", "--projeto", str(self.raiz))
        self.assertEqual(rc, 64)
        rc, _, err = _saida(buscar.main, "x", "--tipo", "audio")
        self.assertEqual(rc, 64)
        self.assertIn("erro de uso", err)
        rc, _, err = _saida(baixar.main, "--busca", "nunca feita", "--escolher", "1", "--projeto", str(self.raiz))
        self.assertEqual(rc, 64)
        self.assertIn("buscar.py", err)

    def test_07_a_dica_final_ensina_o_fluxo_que_o_baixar_aceita(self):
        """Regressão: a busca terminava com «só baixa com --confirmar» e o exemplo --escolher 1,3 — fluxo e números que o baixar.py recusa."""
        with mock.patch.object(comum, "Http", lambda *a, **k: self.http):
            rc, out, err = _saida(buscar.main, "Terra vista do espaço", "--en", "earth from space", "--fontes", "nasa", "--projeto", str(self.raiz))
        self.assertEqual(rc, 0, err)
        dica = out.strip().splitlines()[-1]
        self.assertIn('baixar.py --busca "terra-vista-do-espaco" --escolher 1,2', dica)
        self.assertIn("baixar.py --plano CÓDIGO --confirmar", dica)
        self.assertNotIn("1,3", dica)

    def test_08_chave_devolvida_pelo_provedor_nao_vai_para_cache_busca_nem_json(self):
        """Regressão: um provedor que ecoasse a chave num campo (a URL do pedido) a gravava em _cache/, na busca e no --json."""
        os.environ["PIXABAY_API_KEY"] = "PIXFALSA-9f3+a/Zq=77"
        resposta = apoio.dado("pixabay_videos")
        eco = "https://cdn.pixabay.com/video/eco.mp4?key=PIXFALSA-9f3%2Ba%2FZq%3D77"
        resposta["hits"][0]["videos"]["large"]["url"] = eco
        resposta["hits"][0]["tags"] = "servidor, PIXFALSA-9f3+a/Zq=77"
        http = apoio.HttpFalso([("pixabay.com/api/videos/", resposta)] + apoio.regras())
        with mock.patch.object(comum, "Http", lambda *a, **k: http):
            rc, out, err = _saida(buscar.main, "servidor", "--fontes", "pixabay", "--json", "--projeto", str(self.raiz))
        self.assertEqual(rc, 0, err)
        self.assertTrue(http.pedidos, "o pedido simulado saiu com a chave na URL (é o que a API documenta)")
        gravado = "".join(p.read_text(encoding="utf-8") for p in (self.raiz / "broll" / "_busca").rglob("*.json"))
        for onde, texto in (("stdout", out), ("stderr", err), ("disco", gravado)):
            self.assertNotIn("PIXFALSA", texto, onde)
            self.assertNotIn("9f3%2B", texto, onde)
        c = json.loads(out)["candidatos"][0]
        self.assertNotIn(eco, [a["url"] for a in c["arquivos"]], "a versão cujo endereço trazia a chave foi descartada")
        self.assertTrue(c["arquivos"], "as outras versões continuam")
        self.assertTrue(any("chave de API" in a for a in c["avisos"]))


class Download(unittest.TestCase):
    """Servidor local com Range; os candidatos apontam para ele. É o caminho real de baixar.py, sem internet."""

    @classmethod
    def setUpClass(cls):
        cls.video = apoio.video_sintetico()

    def setUp(self):
        self.tmp = apoio.pasta_temporaria(self, contato=True)      # só fala com 127.0.0.1 (a guarda de apoio.py garante)
        self.raiz, self.d = apoio.projeto(self.tmp)
        pagina = b"<html><body>404 - pagina de erro que nao e video</body></html>" * 40
        self.base, self.srv = apoio.servidor(self, {"/video/Earth Views~orig.mp4": self.video, "/video/pagina.mp4": pagina, "/video/grande.mp4": self.video * 3},
                                             tipos={"/video/pagina.mp4": "text/html"})
        self.sha = hashlib.sha256(self.video).hexdigest()

        def cand(n, caminho, **extra):
            c = {"n": n, "fonte": "nasa", "tipo": "video", "id_fonte": f"teste-{n}", "titulo": f"Vídeo de teste {n}", "pagina_url": f"https://images.nasa.gov/details/teste-{n}",
                 "miniatura_url": None, "largura": 320, "altura": 180, "duracao": 2.0, "autor": "NASA", "autor_url": "https://www.nasa.gov/", "licenca": "Mídia da NASA",
                 "licenca_id": "nasa", "licenca_url": "https://www.nasa.gov/nasa-brand-center/images-and-media/", "exige_atribuicao": True, "uso_comercial": True,
                 "permitida": True, "motivo": "", "risco": "baixo", "avisos": [], "detalhado": True,
                 "arquivos": [{"url": comum.url_limpa(self.base + caminho), "rotulo": "orig", "largura": 320, "altura": 180, "bytes": None, "formato": "mp4", "duracao": 2.0}]}
            c.update(extra)
            return c
        self.busca = {"versao": 1, "consulta": "Terra vista do espaço", "slug": "terra-vista-do-espaco", "pedido_id": "P003", "candidatos": [
            cand(1, "/video/Earth Views~orig.mp4"), cand(2, "/video/pagina.mp4"), cand(3, "/video/grande.mp4"),
            cand(4, "/video/Earth Views~orig.mp4", fonte="wikimedia", licenca="CC BY-NC 4.0", licenca_id="cc-by-nc", permitida=False, motivo="NC proíbe uso comercial",
                 pagina_url="https://commons.wikimedia.org/wiki/File:Teste.webm", licenca_url="https://creativecommons.org/licenses/by-nc/4.0/", autor="Fulano")]}
        pasta = self.raiz / "broll" / "_busca"
        pasta.mkdir(parents=True, exist_ok=True)
        (pasta / "terra-vista-do-espaco.json").write_text(json.dumps(self.busca, ensure_ascii=False), encoding="utf-8")

    def test_10_sem_confirmar_so_ha_plano(self):
        rc, out, err = _saida(baixar.main, "--busca", "Terra vista do espaço", "--escolher", "1", "--projeto", str(self.raiz))
        self.assertEqual(rc, 0, err)
        self.assertIn("PLANO DE DOWNLOAD — nada foi baixado", out)
        self.assertIn("Earth Views~orig.mp4", out)
        self.assertIn(comum.tamanho_legivel(len(self.video)), out)
        self.assertIn("NASA · crédito obrigatório", out)
        codigo = _codigo(out)
        self.assertIn(f"baixar.py --plano {codigo} --confirmar", out)
        self.assertTrue((self.raiz / "broll" / "_busca" / f"_plano_{codigo}.json").is_file())
        self.assertEqual(registro.carregar(self.raiz)["itens"], [])
        self.assertFalse([p for p in (self.raiz / "broll" / "bruto").rglob("*") if p.is_file()])
        self.assertEqual({m for m, *_ in self.srv.pedidos}, {"HEAD"}, "o plano só pergunta o tamanho (HEAD); não baixa")
        self.assertTrue(all("video-broll/" in (ua or "") for *_, ua in self.srv.pedidos), "todo pedido leva a identificação")

    def test_11_plano_codigo_e_so_entao_confirmar(self):
        """O download tem dois tempos amarrados por um código: plano (nada baixa) → «sim» do usuário → --plano CÓDIGO --confirmar."""
        base = ("--projeto", str(self.raiz))
        rc, _, err = _saida(baixar.main, "--busca", "terra-vista-do-espaco", "--escolher", "1", "--confirmar", *base)
        self.assertEqual(rc, 64, "sem plano mostrado não há o que confirmar")
        self.assertIn("--confirmar exige --plano CÓDIGO", err)
        self.assertEqual(self.srv.pedidos, [], "nem um HEAD saiu")
        rc, out, err = _saida(baixar.main, "--busca", "terra-vista-do-espaco", "--escolher", "1", *base)
        self.assertEqual(rc, 0, err)
        codigo = _codigo(out)
        self.assertEqual(_codigo(_saida(baixar.main, "--busca", "terra-vista-do-espaco", "--escolher", "1", *base)[1]), codigo, "o mesmo plano dá o mesmo código")
        self.assertNotEqual(_codigo(_saida(baixar.main, "--busca", "terra-vista-do-espaco", "--escolher", "1", "--teto-mb", "70", *base)[1]), codigo, "outra opção, outro código")
        rc, out, _ = _saida(baixar.main, "--plano", codigo, *base)
        self.assertEqual(rc, 0)
        self.assertIn("PLANO DE DOWNLOAD — nada foi baixado", out, "--plano sem --confirmar só mostra o plano de novo")
        rc, _, err = _saida(baixar.main, "--plano", codigo, "--escolher", "2", "--confirmar", *base)
        self.assertEqual(rc, 64, "não se troca a escolha de um plano aprovado")
        self.assertIn("monte outro plano", err)
        self.assertEqual(registro.carregar(self.raiz)["itens"], [])
        rc, out, err = _saida(baixar.main, "--plano", codigo, "--confirmar", *base)
        self.assertEqual(rc, 0, err + out)
        self.assertIn(f"DOWNLOAD — plano {codigo}", out)
        self.assertIn("✓ [1] B001 → broll/bruto/B001.mp4", out)
        arq = self.raiz / "broll" / "bruto" / "B001.mp4"
        self.assertEqual(arq.read_bytes(), self.video)
        item = registro.obter(self.raiz, "B001")
        self.assertEqual((item["sha256"], item["bytes"], item["largura"], item["altura"], item["fonte"], item["pedido_id"], item["consulta"]),
                         (self.sha, len(self.video), 320, 180, "nasa", "P003", "Terra vista do espaço"))
        self.assertAlmostEqual(item["duracao"], 2.0, delta=0.1)
        self.assertAlmostEqual(item["fps"], 30.0, delta=0.01)
        self.assertEqual((item["base_legal"], item["exige_atribuicao"], item["trecho"], item["tratados"], item["usado_em"]), ("licenca", True, None, [], []))
        self.assertNotIn("trecho_arquivo", item)
        self.assertTrue(item["arquivo_url"].startswith(self.base))
        self.assertIn("NASA", (self.raiz / "broll" / "creditos.md").read_text(encoding="utf-8"))
        self.assertFalse((self.raiz / "broll" / "bruto" / "_baixando").exists(), "a pasta provisória some quando fica vazia")
        rc, out, _ = _saida(baixar.main, "--plano", codigo, "--confirmar", *base)
        self.assertEqual(rc, 0)
        self.assertIn("já está no registro como B001", out)
        self.assertEqual(len(registro.carregar(self.raiz)["itens"]), 1)
        rc, out, _ = _saida(baixar.main, "--busca", "terra-vista-do-espaco", "--escolher", "1", *base)
        self.assertEqual(rc, 0)
        self.assertIn("não há o que baixar", out)
        self.assertNotIn("Código deste plano", out, "plano sem nada a baixar não ganha código")

    def test_11b_plano_alterado_vencido_ou_de_arquivo_que_mudou_nao_vale(self):
        """O que é baixado é EXATAMENTE o plano mostrado: mexer no arquivo do plano, deixá-lo vencer ou o servidor trocar o
        arquivo invalida a aprovação."""
        base = ("--projeto", str(self.raiz))
        codigo = _codigo(_saida(baixar.main, "--busca", "terra-vista-do-espaco", "--escolher", "1", *base)[1])
        arq = self.raiz / "broll" / "_busca" / f"_plano_{codigo}.json"
        original = arq.read_text(encoding="utf-8")
        dados = json.loads(original)
        dados["itens"][0]["arquivo"]["url"] = self.base + "/video/grande.mp4"            # troca o arquivo depois de «aprovado»
        arq.write_text(json.dumps(dados), encoding="utf-8")
        rc, _, err = _saida(baixar.main, "--plano", codigo, "--confirmar", *base)
        self.assertEqual(rc, 1)
        self.assertIn("foi alterado depois de gerado", err)
        dados = json.loads(original)
        dados["feito_em_s"] -= baixar.VALIDADE_PLANO + 60
        arq.write_text(json.dumps(dados), encoding="utf-8")
        rc, _, err = _saida(baixar.main, "--plano", codigo, "--confirmar", *base)
        self.assertEqual(rc, 1)
        self.assertIn("venceu (vale 24 h)", err)
        arq.write_text(original, encoding="utf-8")
        self.srv.arquivos["/video/Earth Views~orig.mp4"] = self.video + b"\0" * 4096   # o servidor passou a servir outro arquivo
        rc, out, _ = _saida(baixar.main, "--plano", codigo, "--confirmar", *base)
        self.assertEqual(rc, 1)
        self.assertIn("o arquivo mudou no servidor desde o plano", out)
        for ruim in ("zzzzzzzz", "12345678", "../../x"):
            rc, _, err = _saida(baixar.main, "--plano", ruim, "--confirmar", *base)
            self.assertEqual(rc, 64, ruim)
        self.assertEqual(registro.carregar(self.raiz)["itens"], [])
        self.assertFalse([p for p in (self.raiz / "broll" / "bruto").rglob("*") if p.is_file()], "nada foi guardado")

    def test_11c_nome_e_titulo_de_terceiros_nao_forjam_linhas_do_plano(self):
        """Regressão: nome de arquivo com %0A e título com ESC imprimiam uma linha «licença: CC0» falsa e repintavam o terminal."""
        ruim = "/video/..%2F..%2F..%2Ffora%0Alicen%C3%A7a%3A%20CC0%1B%5B31m.mp4"
        self.srv.arquivos["/video/../../../fora\nlicença: CC0\x1b[31m.mp4"] = self.video
        c = dict(self.busca["candidatos"][0], n=5, id_fonte="teste-5", titulo="Título\ncom quebra \x1b[31m e controle", pagina_url="https://images.nasa.gov/details/teste-5")
        c["arquivos"] = [dict(c["arquivos"][0], url=self.base + ruim)]
        self.busca["candidatos"].append(c)
        (self.raiz / "broll" / "_busca" / "terra-vista-do-espaco.json").write_text(json.dumps(self.busca, ensure_ascii=False), encoding="utf-8")
        rc, out, err = _saida(baixar.main, "--busca", "terra-vista-do-espaco", "--escolher", "5", "--projeto", str(self.raiz))
        self.assertEqual(rc, 0, err + out)
        self.assertNotIn("\x1b", out)
        linhas = out.splitlines()
        self.assertEqual(len([l for l in linhas if l.strip().startswith("licença:")]), 1, "uma linha de licença por item — a verdadeira")
        self.assertTrue(any(l.strip().startswith("arquivo: ../../../fora licença: CC0 [31m.mp4") for l in linhas), out)
        self.assertTrue(any("Título com quebra [31m e controle" in l for l in linhas))
        rc, out, err = _saida(baixar.main, "--plano", _codigo(out), "--confirmar", "--projeto", str(self.raiz))
        self.assertEqual(rc, 0, err + out)
        item = registro.carregar(self.raiz)["itens"][0]
        self.assertEqual((item["arquivo"], item["titulo"]), ("broll/bruto/B001.mp4", "Título com quebra [31m e controle"), "nome seguro no disco, título limpo no registro")
        self.assertEqual(sorted(p.name for p in self.raiz.iterdir() if p.name == "fora"), [], "nada saiu de broll/bruto/")

    def test_11d_sem_rede_o_plano_sai_com_75_e_nao_manda_confirmar(self):
        """Regressão: com a rede cortada o plano saía com código 1 e ainda sugeria confirmar um plano sem nada baixável."""
        morto = dict(self.busca["candidatos"][0], n=6, id_fonte="teste-6", pagina_url="https://images.nasa.gov/details/teste-6")
        morto["arquivos"] = [dict(morto["arquivos"][0], url="http://127.0.0.1:9/video/sem-resposta.mp4")]      # porta 9: ninguém responde
        self.busca["candidatos"].append(morto)
        (self.raiz / "broll" / "_busca" / "terra-vista-do-espaco.json").write_text(json.dumps(self.busca, ensure_ascii=False), encoding="utf-8")
        with mock.patch.object(comum.time, "sleep", lambda s: None):                 # sem as esperas entre tentativas
            rc, out, err = _saida(baixar.main, "--busca", "terra-vista-do-espaco", "--escolher", "5", "--projeto", str(self.raiz))
        self.assertEqual(rc, 75, out + err)
        self.assertIn("✗ NÃO SERÁ BAIXADO: sem resposta de 127.0.0.1", out)
        self.assertNotIn("Código deste plano", out)
        self.assertNotIn("--confirmar", out)
        self.assertIn("Sem resposta dos servidores", err)
        self.assertFalse(list((self.raiz / "broll" / "_busca").glob("_plano_*.json")), "plano sem nada a baixar não é gravado")
        rc, out, _ = _saida(baixar.main, "--busca", "terra-vista-do-espaco", "--escolher", "4", "--projeto", str(self.raiz))
        self.assertEqual(rc, 1, "recusa pela política continua sendo 1, não 75")
        self.assertIn("Nenhum item deste plano pode ser baixado", _saida(baixar.main, "--busca", "terra-vista-do-espaco", "--escolher", "4", "--projeto", str(self.raiz))[2])

    def test_12_retoma_download_interrompido(self):
        plano = baixar.planejar(self.d, self.busca, [1])
        url = plano[0]["arquivo"]["url"]
        tmp = self.raiz / "broll" / "bruto" / "_baixando" / (hashlib.sha1(url.encode()).hexdigest()[:16] + ".parcial")
        tmp.parent.mkdir(parents=True)
        metade = len(self.video) // 2
        tmp.write_bytes(self.video[:metade])
        self.srv.pedidos.clear()
        res = _quieto(baixar.baixar, self.d, self.busca, plano)
        self.assertEqual(res[0].get("sha256"), self.sha, res)
        faixas = [f for m, _, f, _ in self.srv.pedidos if m == "GET"]
        self.assertEqual(faixas, [f"bytes={metade}-"], "só o que faltava foi pedido")
        self.assertEqual((self.raiz / "broll" / "bruto" / "B001.mp4").read_bytes(), self.video)

    def test_13_teto_pagina_de_erro_e_licenca_recusada(self):
        teto_mb = len(self.video) * 2 / 1e6
        plano = baixar.planejar(self.d, self.busca, [1, 2, 3, 4], teto_mb=teto_mb)
        por_n = {e["n"]: e for e in plano}
        self.assertIsNone(por_n[1]["problema"])
        self.assertIn("nenhuma versão cabe no teto", por_n[3]["problema"], "arquivo maior que o teto não entra no plano")
        self.assertIn("--trecho", por_n[3]["problema"])
        self.assertIn("recusada pela política", por_n[4]["problema"])
        res = {r["n"]: r for r in _quieto(baixar.baixar, self.d, self.busca, plano, teto_mb=teto_mb)}
        self.assertEqual(res[1].get("id"), "B001")
        self.assertIn("ffprobe", res[2]["erro"], "página de erro com nome .mp4 não passa pela validação")
        self.assertTrue(res[3]["erro"] and res[4]["erro"])
        self.assertEqual([i["id"] for i in registro.carregar(self.raiz)["itens"]], ["B001"])
        self.assertEqual(sorted(p.name for p in (self.raiz / "broll" / "bruto").rglob("*") if p.is_file()), ["B001.mp4"], "nada de resto de download inválido")
        rc, out, _ = _saida(baixar.main, "--busca", "terra-vista-do-espaco", "--escolher", "4", "--projeto", str(self.raiz))
        self.assertEqual(rc, 1)
        self.assertIn("NÃO SERÁ BAIXADO", out)
        rc, out, _ = _saida(baixar.main, "--busca", "terra-vista-do-espaco", "--escolher", "4", "--base-legal", "autorizacao", "--projeto", str(self.raiz))
        self.assertEqual(rc, 1)
        self.assertIn("exige --nota", out)
        plano = baixar.planejar(self.d, self.busca, [4], base_legal="autorizacao", nota="autorizado por e-mail em 2026-10-01")
        self.assertIsNone(plano[0]["problema"])
        res = _quieto(baixar.baixar, self.d, self.busca, plano, base_legal="autorizacao", nota="autorizado por e-mail em 2026-10-01")
        self.assertTrue(res[0].get("repetido"), "mesmo conteúdo (sha256) de B001: não duplica")

    def test_14_excecao_registrada_com_base_legal_e_nota(self):
        rc, out, err = _saida(baixar.main, "--busca", "terra-vista-do-espaco", "--escolher", "4", "--base-legal", "citacao", "--nota", "6 s citados para comentar o trecho",
                              "--projeto", str(self.raiz))
        self.assertEqual(rc, 0, err + out)
        self.assertIn("licença: CC BY-NC 4.0 — recusada pela política", out)
        self.assertIn("⚠ ENTRA COMO EXCEÇÃO: citação — nota: «6 s citados para comentar o trecho» — risco medio — sem uso comercial — crédito obrigatório", out,
                      "o plano mostra o que o usuário está aprovando: a exceção, a nota e o risco que serão gravados")
        _codigo(out)
        plano = baixar.planejar(self.d, self.busca, [4], base_legal="citacao", nota="6 s citados para comentar o trecho")
        res = _quieto(baixar.baixar, self.d, self.busca, plano, base_legal="citacao", nota="6 s citados para comentar o trecho", risco="alto")
        item = registro.obter(self.raiz, res[0]["id"])
        self.assertEqual((item["base_legal"], item["risco"], item["licenca"], item["uso_comercial"]), ("citacao", "alto", "CC BY-NC 4.0", False))
        self.assertIn("6 s citados", item["notas"])
        self.assertIn("usado como citação", item["atribuicao"])
        self.assertIn("Atenção antes de publicar", (self.raiz / "broll" / "creditos.md").read_text(encoding="utf-8"))

    def test_15_trecho_baixa_so_o_intervalo_sem_recodificar(self):
        plano = baixar.planejar(self.d, self.busca, [1], trecho=(0.5, 1.5))
        self.assertIsNone(plano[0]["problema"])
        self.srv.pedidos.clear()
        res = _quieto(baixar.baixar, self.d, self.busca, plano, trecho=(0.5, 1.5))
        self.assertTrue(res[0].get("id"), res)
        item = registro.obter(self.raiz, res[0]["id"])
        self.assertEqual(item["trecho"], {"t0": 0.5, "t1": 1.5}, "`trecho` é o intervalo da FONTE que o item usa")
        if "trecho_arquivo" in item:                           # o corte caiu num quadro-chave anterior: a sobra fica marcada
            self.assertAlmostEqual(item["trecho_arquivo"]["t1"] - item["trecho_arquivo"]["t0"], 1.0, delta=0.1)
            self.assertAlmostEqual(item["trecho_arquivo"]["t1"], item["duracao"], delta=0.01)
        self.assertLess(item["duracao"], 1.7)
        self.assertGreater(item["duracao"], 0.5)
        self.assertLess(item["bytes"], len(self.video))
        self.assertNotEqual(item["sha256"], self.sha)
        self.assertTrue(any("video-broll/" in (ua or "") for *_, ua in self.srv.pedidos), "o ffmpeg também se identifica")
        with self.assertRaises(comum.Erro):
            baixar._trecho("10-5")
        self.assertEqual(baixar._trecho("1:05-1:20"), (65.0, 80.0))
        self.assertEqual(baixar._numeros("1-3,5", 6), [1, 2, 3, 5])
        with self.assertRaises(comum.Erro):
            baixar._numeros("9", 4)

    def test_16_servidor_sem_range_recomeca_do_zero(self):
        base, srv = apoio.servidor(self, {"/v.mp4": self.video}, aceita_range=False)
        http = comum.Http()
        destino = self.tmp / "parcial sem range.bin"
        destino.write_bytes(self.video[:1000])
        r = http.baixar(base + "/v.mp4", destino, ("nasa.gov",), teto=10_000_000, esperado=len(self.video))
        self.assertEqual((r["sha256"], r["retomado_de"]), (self.sha, 0))
        with self.assertRaises(comum.Erro) as e:
            http.baixar(base + "/v.mp4", self.tmp / "x.bin", ("nasa.gov",), teto=1000)
        self.assertIn("teto", str(e.exception))
        info = http.tamanho(base + "/v.mp4", ("nasa.gov",))
        self.assertEqual((info["bytes"], info["retoma"]), (len(self.video), False))
        with self.assertRaises(comum.Erro) as e:
            http.json(base + "/nao-existe", ("nasa.gov",))
        self.assertIn("404", str(e.exception))
        t0 = time.monotonic()
        http.tamanho(base + "/v.mp4", ("nasa.gov",), intervalo=0.4)
        http.tamanho(base + "/v.mp4", ("nasa.gov",), intervalo=0.4)
        self.assertGreaterEqual(time.monotonic() - t0, 0.4, "há um intervalo mínimo entre pedidos ao mesmo host")


if __name__ == "__main__":
    unittest.main(verbosity=2)
