"""Provedores SEM chave contra a internet de verdade (NASA, Internet Archive, Openverse e, só com contato real, Wikimedia
Commons): leitura de API e um HEAD — nenhum arquivo de mídia é baixado. Pulado sem conexão ou com VIDEO_BROLL_SEM_REDE=1.

Identificação: estes testes saem para a rede com o User-Agent de quem roda a suíte — VIDEO_OPS_CONTATO e VIDEO_OPS_AGENTE do
ambiente, se existirem — e NUNCA com o contato fictício dos testes simulados. A Wikimedia exige contato de verdade: sem
VIDEO_OPS_CONTATO no ambiente, o teste dela é pulado (ninguém inventa um contato para ela).

O download real de um arquivo pequeno só roda com VIDEO_BROLL_TESTE_BAIXAR=1: baixar é ação externa e precisa da
aprovação explícita de quem está na máquina (o arquivo vai para uma pasta temporária e é apagado no fim)."""
import os
import socket
import unittest
from pathlib import Path

from testes import apoio

import comum
import provedores as P


def _tem_rede() -> bool:
    if os.environ.get("VIDEO_BROLL_SEM_REDE") == "1":
        return False
    try:
        socket.create_connection(("images-api.nasa.gov", 443), timeout=4).close()
        return True
    except OSError:
        return False


TEM_REDE = _tem_rede()
CONTATO = apoio.IDENTIFICACAO_DE_QUEM_RODA["VIDEO_OPS_CONTATO"]
CONTATO_REAL = CONTATO if CONTATO and CONTATO != apoio.CONTATO_DE_TESTE else ""


@unittest.skipUnless(TEM_REDE, "sem conexão (ou VIDEO_BROLL_SEM_REDE=1): testes de rede pulados")
class Rede(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.http = comum.Http()

    def setUp(self):
        self.tmp = apoio.pasta_temporaria(self)              # sem contato fictício: o que sai para a rede é a identificação de quem roda
        for nome, valor in apoio.IDENTIFICACAO_DE_QUEM_RODA.items():
            if valor and valor != apoio.CONTATO_DE_TESTE:
                os.environ[nome] = valor                     # restaurado no fim pelo addCleanup de pasta_temporaria
        self.assertNotIn(apoio.CONTATO_DE_TESTE, comum.agente(), "teste de rede com o contato fictício no User-Agent")

    def conferir(self, c: dict, fonte: str, tipo: str):
        self.assertEqual((c["fonte"], c["tipo"]), (fonte, tipo))
        self.assertTrue(c["titulo"])
        self.assertTrue(str(c["pagina_url"]).startswith("https://"), c["pagina_url"])
        self.assertIn(c["licenca_id"], P.registro.LICENCAS)
        self.assertIsInstance(c["permitida"], bool)

    def test_01_nasa_busca_detalha_e_informa_tamanho_sem_baixar(self):
        prov = P.Nasa(self.http)
        cands = prov.buscar("earth from space", "video", None, 2)
        self.assertTrue(cands, "a NASA não devolveu nada para 'earth from space'")
        self.conferir(cands[0], "nasa", "video")
        self.assertEqual(cands[0]["licenca_id"], "nasa")
        c = prov.detalhar(cands[0])
        self.assertTrue(c["arquivos"], "o manifesto /asset/ mudou de formato?")
        self.assertTrue(all(a["url"].startswith("https://images-assets.nasa.gov/") and " " not in a["url"] for a in c["arquivos"]))
        menor = next((a for a in c["arquivos"] if a["rotulo"] in ("preview", "mobile", "small")), c["arquivos"][0])
        info = self.http.tamanho(menor["url"], prov.hosts_arquivo)
        self.assertGreater(info["bytes"] or 0, 1000, "o HEAD não informou o tamanho")

    @unittest.skipUnless(CONTATO_REAL, "a Wikimedia exige contato real no User-Agent: defina VIDEO_OPS_CONTATO (e-mail ou URL seu) para rodar este teste")
    def test_02_wikimedia_commons_traz_licenca_e_versoes(self):
        prov = P.Wikimedia(self.http)
        self.assertEqual(prov.disponivel(), (True, ""))
        cands = prov.buscar("earth from space", "video", None, 3)
        self.assertTrue(cands)
        for c in cands:
            self.conferir(c, "wikimedia", "video")
            self.assertTrue(c["arquivos"] and c["arquivos"][0]["url"].startswith("https://upload.wikimedia.org/"))
            self.assertNotIn("utm_", c["arquivos"][0]["url"])
        self.assertTrue(any(c["licenca_id"] != "desconhecida" for c in cands), "extmetadata deixou de trazer a licença?")

    def test_03_internet_archive_busca_e_metadados(self):
        prov = P.Archive(self.http)
        cands = prov.buscar("earth from space", "video", None, 2)
        self.assertTrue(cands)
        self.conferir(cands[0], "archive", "video")
        self.assertTrue(all(c["permitida"] for c in cands), "o filtro de licença da consulta deixou passar item sem licença aberta")
        self.assertTrue(all(c["risco"] == "medio" and c["conferir_origem"] for c in cands), "licença declarada por quem subiu: nasce «confira a origem»")
        c = prov.detalhar(cands[0])
        self.assertTrue(c["arquivos"])
        self.assertTrue(all(a["url"].startswith("https://archive.org/download/") for a in c["arquivos"]))

    def test_04_openverse_imagens_com_licenca_comercial(self):
        prov = P.Openverse(self.http)
        cands = prov.buscar("circuit board", "imagem", "horizontal", 3)
        self.assertTrue(cands)
        for c in cands:
            self.conferir(c, "openverse", "imagem")
            self.assertTrue(c["permitida"], f"license_type=commercial,modification devolveu {c['licenca']}")
        cota = self.http.limites.get("api.openverse.org") or {}
        self.assertTrue(any("ratelimit" in k for k in cota), "os cabeçalhos de cota do Openverse mudaram de nome?")

    @unittest.skipUnless(os.environ.get("VIDEO_BROLL_TESTE_BAIXAR") == "1", "download real só com VIDEO_BROLL_TESTE_BAIXAR=1 (precisa de aprovação explícita)")
    def test_10_download_real_de_um_arquivo_pequeno(self):
        prov = P.Nasa(self.http)
        c = prov.detalhar(prov.buscar("earth from space", "video", None, 1)[0])
        arq = next(a for a in c["arquivos"] if a["rotulo"] in ("preview", "mobile"))
        info = self.http.tamanho(arq["url"], prov.hosts_arquivo)
        self.assertLess(info["bytes"], 15_000_000, "arquivo de teste grande demais")
        destino = Path(self.tmp) / "download real.parcial"
        r = self.http.baixar(arq["url"], destino, prov.hosts_arquivo, teto=15_000_000, esperado=info["bytes"])
        self.assertEqual(r["bytes"], info["bytes"])
        _da, _texto, video, _trava = comum.importar_kit()
        self.assertGreater(video.sondar(destino)["duracao"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
