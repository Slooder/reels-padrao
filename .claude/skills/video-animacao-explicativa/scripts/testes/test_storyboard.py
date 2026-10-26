# -*- coding: utf-8 -*-
"""storyboard.py: contrato, edição, validação (com o validador do motor, sem browser), sincronia, fila e catálogo.
Nada aqui abre o Chromium nem o ffmpeg; cada teste leva de décimos de segundo a poucos segundos."""
import json
import unittest
from pathlib import Path

from testes import apoio
import storyboard  # noqa: E402  (apoio põe scripts/ no caminho)

CAMPOS = ["id", "trecho", "t0", "dur", "cena", "params", "formatos", "fato_ids", "broll_id", "saida"]


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.area = apoio.Area()
        cls.proj = cls.area.projeto("lab-ia")

    @classmethod
    def tearDownClass(cls):
        cls.area.limpar()

    def setUp(self):
        r = apoio.sb(self.proj, "novo", "--forcar")
        self.assertEqual(r.returncode, 0, r.stderr)


class TestCli(Base):
    def test_01_sem_da_sai_com_2(self):
        fora = self.area.raiz / "sem direção"
        fora.mkdir(exist_ok=True)
        r = apoio.sb(fora, "mostrar")
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("video-direcao-de-arte", r.stderr)

    def test_02_ajuda_em_portugues_e_uso_incorreto_64(self):
        r = apoio.sb(None, "--help")
        self.assertEqual(r.returncode, 0)
        for sub in ("novo", "cenas", "adicionar", "definir", "validar", "sincronizar", "fila", "prever", "render", "ancoras", "conferir"):
            self.assertIn(sub, r.stdout)
        r = apoio.sb(self.proj, "inexistente")
        self.assertEqual(r.returncode, 64)
        self.assertNotIn("Traceback", r.stderr)
        r = apoio.sb(self.proj, "adicionar")
        self.assertEqual(r.returncode, 64)
        self.assertIn("--cena", r.stderr)

    def test_03_novo_nao_sobrescreve(self):
        r = apoio.sb(self.proj, "novo")
        self.assertEqual(r.returncode, 64)
        self.assertIn("--forcar", r.stderr)

    def test_04_adicionar_grava_o_contrato_exato(self):
        r = apoio.sb(self.proj, "adicionar", "--cena", "tokenizacao", "--trecho", "A frase vira pedaços | e cada pedaço vira um número", "--fato", "F001")
        self.assertEqual(r.returncode, 0, r.stderr)
        r = apoio.sb(self.proj, "adicionar", "--cena", "gc", "--params", '{"nome": "Ana Souza", "cargo": "Pesquisadora"}', "--formatos", "horizontal")
        self.assertEqual(r.returncode, 0, r.stderr)
        sbd = apoio.ler_storyboard(self.proj)
        self.assertEqual(sbd["versao"], 1)
        c1, c2 = sbd["cenas"]
        self.assertEqual(list(c1)[:len(CAMPOS)], CAMPOS)
        self.assertEqual((c1["id"], c1["t0"], c1["dur"], c1["formatos"], c1["fato_ids"], c1["broll_id"], c1["saida"]),
                         ("C01", None, 9, ["horizontal", "vertical"], ["F001"], None, "animacoes/C01"))
        self.assertEqual((c2["id"], c2["formatos"], c2["saida"]), ("C02", ["horizontal"], "animacoes/C02"))
        self.assertEqual(storyboard.conferir_contrato(sbd), [])

    def test_05_param_ruim_ou_cena_inexistente_nao_grava(self):
        antes = apoio.ler_storyboard(self.proj)
        r = apoio.sb(self.proj, "adicionar", "--cena", "embeddings", "--params", '{"pontoz": 1}')
        self.assertEqual(r.returncode, 64)
        self.assertIn('Quis dizer "pontos"', r.stderr)
        r = apoio.sb(self.proj, "adicionar", "--cena", "tokenizaca")
        self.assertEqual(r.returncode, 64)
        self.assertIn("tokenizacao", r.stderr)
        r = apoio.sb(self.proj, "adicionar", "--cena", "atencao", "--params", "{isto não é json")
        self.assertEqual(r.returncode, 64)
        self.assertEqual(apoio.ler_storyboard(self.proj), antes)

    def test_06_definir_funde_params_e_recusa_duracao_curta(self):
        apoio.sb(self.proj, "adicionar", "--cena", "atencao")
        r = apoio.sb(self.proj, "definir", "C01", "--param", 'titulo="Quem olha para quem"', "--param", "consulta=3", "--dur", "12", "--t0", "4,5")
        self.assertEqual(r.returncode, 0, r.stderr)
        c = apoio.ler_storyboard(self.proj)["cenas"][0]
        self.assertEqual((c["params"], c["dur"], c["t0"]), ({"titulo": "Quem olha para quem", "consulta": 3}, 12.0, 4.5))
        r = apoio.sb(self.proj, "definir", "C01", "--dur", "2")
        self.assertEqual(r.returncode, 64)
        self.assertIn("curta demais", r.stderr)
        self.assertEqual(apoio.ler_storyboard(self.proj)["cenas"][0]["dur"], 12.0)
        r = apoio.sb(self.proj, "definir", "C01", "--sem-param", "consulta", "--t0", "null")
        self.assertEqual(r.returncode, 0, r.stderr)
        c = apoio.ler_storyboard(self.proj)["cenas"][0]
        self.assertEqual((c["params"], c["t0"]), ({"titulo": "Quem olha para quem"}, None))

    def test_07_validar_reprova_o_que_o_render_reprovaria(self):
        apoio.sb(self.proj, "adicionar", "--cena", "tokenizacao")
        apoio.sb(self.proj, "adicionar", "--cena", "treino")
        arq = Path(self.proj) / "roteiro" / "storyboard.json"
        sbd = json.loads(arq.read_text(encoding="utf-8"))
        sbd["cenas"][0]["params"] = {"passos_t": [0, 1, 2, 3, 4], "ilustrativo": False}
        sbd["cenas"][1]["params"] = {"prob_alvo": [0.1, 2]}
        sbd["cenas"][1]["formatos"] = ["horizontal", "panoramico"]
        sbd["cenas"].append({"id": "C01", "cena": "titulo"})
        arq.write_text(json.dumps(sbd, ensure_ascii=False), encoding="utf-8")
        r = apoio.sb(self.proj, "validar", "--json")
        self.assertEqual(r.returncode, 1)
        rel = json.loads(r.stdout)
        msgs = " | ".join(a["msg"] for a in rel["achados"] if a["nivel"] == "erro")
        for trecho in ("passos_t tem 5 instantes e a cena tem 4", "falta params.fonte", "fato_ids", "id repetido", 'formato "panoramico"', 'falta o campo "dur"'):
            self.assertIn(trecho, msgs)
        sbd["cenas"] = sbd["cenas"][:2]
        sbd["cenas"][0]["params"] = {}
        sbd["cenas"][1]["formatos"] = ["horizontal"]
        arq.write_text(json.dumps(sbd, ensure_ascii=False), encoding="utf-8")
        r = apoio.sb(self.proj, "validar")
        self.assertEqual(r.returncode, 1)
        self.assertIn("prob_alvo", r.stdout)                      # este vem do validador do motor (máximo 0,999)
        sbd["cenas"][1]["params"] = {}
        arq.write_text(json.dumps(sbd, ensure_ascii=False), encoding="utf-8")
        r = apoio.sb(self.proj, "validar")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("VÁLIDO: 2 cena(s), 0 erro(s)", r.stdout)

    def test_08_fila_do_motor_por_formato_opaca_e_com_alfa(self):
        apoio.sb(self.proj, "adicionar", "--cena", "tokenizacao")
        apoio.sb(self.proj, "adicionar", "--cena", "gc", "--params", '{"nome": "Ana Souza"}', "--formatos", "horizontal")
        r = apoio.sb(self.proj, "fila", "--codec-alfa", "prores4444")
        self.assertEqual(r.returncode, 0, r.stderr)
        h = json.loads((Path(self.proj) / "animacoes" / "_fila_horizontal.json").read_text(encoding="utf-8"))
        v = json.loads((Path(self.proj) / "animacoes" / "_fila_vertical.json").read_text(encoding="utf-8"))
        self.assertEqual([(j["saida"], j["codec"], j["alfa"]) for j in h], [("C01_horizontal.mp4", "h264", False), ("C02_horizontal.mov", "prores4444", True)])
        self.assertEqual([j["saida"] for j in v], ["C01_vertical.mp4"])
        self.assertEqual(h[1]["cena"], "gc")                       # cena do kit vai pelo nome; a da biblioteca, pelo arquivo
        self.assertTrue(h[0]["cena"].endswith("cenas/tokenizacao.js"))
        d, _ = storyboard.carregar_da(self.proj)
        ok, msg = storyboard.validar_no_motor(d, Path(self.proj) / "animacoes" / "_fila_horizontal.json")
        self.assertTrue(ok, msg)

    def test_09_catalogo_lista_biblioteca_e_kit_com_params(self):
        r = apoio.sb(self.proj, "cenas", "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        cat = {c["nome"]: c for c in json.loads(r.stdout) if not c["sombreada"]}
        for nome in apoio.NOMES:
            self.assertEqual(cat[nome]["origem"], "skill")
            self.assertTrue(cat[nome]["tem_roteiro"], nome)
            for comum in ("titulo", "legendas", "passos_t", "cor", "ilustrativo", "fonte", "plataforma", "reservar_legenda"):
                self.assertIn(comum, cat[nome]["meta"]["params"], f"{nome}.{comum}")
            self.assertEqual(sorted(cat[nome]["meta"]["formatos"]), ["horizontal", "quadrado", "vertical"])
        for nome in ("titulo", "gc", "barras", "citacao", "moldura"):
            self.assertEqual(cat[nome]["origem"], "kit")
        r = apoio.sb(self.proj, "cenas", "proximo_token")
        self.assertIn("temperatura", r.stdout)
        self.assertIn("passos sincronizáveis: sim", r.stdout)

    def test_16_duracao_padrao_acompanha_o_ritmo_da_da(self):
        calmo = self.area.projeto("editorial-claro")              # durações longas: a mesma cena precisa de mais tempo
        apoio.sb(calmo, "novo", "--forcar")
        r = apoio.sb(calmo, "adicionar", "--cena", "atencao")
        self.assertEqual(r.returncode, 0, r.stderr)
        apoio.sb(self.proj, "adicionar", "--cena", "atencao")
        rapido, lento = apoio.ler_storyboard(self.proj)["cenas"][0]["dur"], apoio.ler_storyboard(calmo)["cenas"][0]["dur"]
        self.assertEqual(rapido, 11)
        self.assertGreater(lento, rapido)
        self.assertEqual(apoio.sb(calmo, "validar", "--estrito").returncode, 0)

    def test_10_cena_propria_do_projeto_tem_precedencia(self):
        pasta = Path(self.proj) / "animacoes" / "cenas"
        pasta.mkdir(parents=True, exist_ok=True)
        (pasta / "titulo.js").write_text("export const meta = { nome: 'titulo', descricao: 'do projeto', dur_padrao: 2, params: {} };\nexport function build() {}\nexport function seek() {}\n", encoding="utf-8")
        try:
            arq, origem = storyboard.resolver_cena(Path(self.proj), "titulo")
            self.assertEqual((origem, arq.parent), ("projeto", pasta))
        finally:
            (pasta / "titulo.js").unlink()
            pasta.rmdir()


class TestSincronia(Base):
    FALA = ("Olá pessoal hoje eu vou mostrar como o modelo lê o seu texto primeiro a frase vira pedaços e cada pedaço vira um número "
            "depois cada token consulta os anteriores e distribui pesos que somam cem por cento e é isso")

    def _gravar_fala(self, nome="fala.palavras.json"):
        arq = Path(self.proj) / "transcricao" / nome
        arq.write_text(json.dumps(apoio.palavras_de(self.FALA), ensure_ascii=False), encoding="utf-8")
        return arq

    def tearDown(self):
        for a in (Path(self.proj) / "transcricao").glob("*.palavras.json"):
            a.unlink()

    def test_11_ancorar_acha_trecho_exato_e_aproximado(self):
        falas = [storyboard.normalizar(w) for w in self.FALA.split()]
        tok, marcas = storyboard.fatiar_trecho("a frase vira pedaços | e cada pedaço vira um número [F001]")
        a = storyboard.ancorar(tok, falas)
        self.assertEqual((a["i0"], a["i1"], a["nota"]), (14, 23, 1.0))
        self.assertEqual(marcas, [4])
        tok, _ = storyboard.fatiar_trecho("cada token consulta todos os anteriores, e distribui os pesos")   # roteiro ≠ fala
        a = storyboard.ancorar(tok, falas)
        self.assertGreaterEqual(a["nota"], 0.7)
        self.assertEqual(falas[a["i0"]], "cada")
        self.assertIsNone(storyboard.ancorar(storyboard.fatiar_trecho("abacaxi helicóptero")[0], falas))

    def test_12_sincronizar_preenche_t0_dur_e_passos_t(self):
        self._gravar_fala()
        apoio.sb(self.proj, "adicionar", "--cena", "tokenizacao", "--trecho", "a frase vira pedaços | e cada pedaço vira um número")
        apoio.sb(self.proj, "adicionar", "--cena", "titulo", "--params", '{"titulo": "Atenção"}', "--dur", "3")
        apoio.sb(self.proj, "adicionar", "--cena", "atencao", "--trecho", "cada token consulta os anteriores | e distribui pesos | que somam cem por cento")
        r = apoio.sb(self.proj, "sincronizar", "--manter-dur")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        c1, c2, c3 = apoio.ler_storyboard(self.proj)["cenas"]
        self.assertAlmostEqual(c1["t0"], 1.0 + 14 * 0.4 - 0.2, places=2)             # 0,2 s antes da palavra "a"
        self.assertEqual(c1["params"]["passos_t"][0], 0.0)
        self.assertAlmostEqual(c1["params"]["passos_t"][1], (1.0 + 18 * 0.4) - c1["t0"] - 0.08, places=2)   # a palavra depois da marca: "e"
        self.assertEqual((c1["dur"], c2["t0"]), (9, None))                           # --manter-dur; cartela sem trecho não é tocada
        self.assertEqual(len(c3["params"]["passos_t"]), 3)
        self.assertGreater(c3["t0"], c1["t0"])
        self.assertEqual(apoio.ler_storyboard(self.proj)["sincronia"]["origem"], "transcricao/fala.palavras.json")

    def test_13_marcas_demais_trecho_ausente_e_duas_transcricoes(self):
        self._gravar_fala()
        apoio.sb(self.proj, "adicionar", "--cena", "tokenizacao", "--trecho", "a | frase | vira | pedaços | e cada pedaço")
        apoio.sb(self.proj, "adicionar", "--cena", "embeddings", "--trecho", "um parágrafo que ninguém falou no vídeo inteiro")
        antes = apoio.ler_storyboard(self.proj)
        r = apoio.sb(self.proj, "sincronizar")
        self.assertEqual(r.returncode, 1)
        self.assertIn("4 marca(s) | e a cena tem 4 passo(s)", r.stdout)
        self.assertIn("não achei o trecho", r.stdout)
        self.assertEqual(apoio.ler_storyboard(self.proj)["cenas"], antes["cenas"])
        self._gravar_fala("outra tomada.palavras.json")
        r = apoio.sb(self.proj, "sincronizar")
        self.assertEqual(r.returncode, 64)
        self.assertIn("--palavras", r.stderr)


class TestMotorSemBrowser(Base):
    def test_14_params_ruins_dao_64_antes_do_browser_em_todas_as_cenas(self):
        import da_ext_motor
        d, _ = storyboard.carregar_da(self.proj)
        for nome in apoio.NOMES:
            cena = str(apoio.CENAS / f"{nome}.js")
            for params, trecho in (({"parametro_que_nao_existe": 1}, "não existe na cena"), ({"passos_t": ["dois"]}, "esperado número"), ({"cor": "roxo-berrante"}, "não é um token da DA")):
                r = da_ext_motor.render(["--cena", cena, "--saida", str(self.area.raiz / "x.png"), "--quadro", "1", "--params", json.dumps(params), "--validar"], da_obj=d, capturar=True)
                self.assertEqual(r.returncode, 64, f"{nome} {params}: {r.stderr}")
                self.assertIn(trecho, r.stderr, nome)
            r = da_ext_motor.render(["--cena", cena, "--saida", str(self.area.raiz / "x.png"), "--quadro", "1", "--validar"], da_obj=d, capturar=True)
            self.assertEqual(r.returncode, 0, f"{nome}: {r.stderr}")

    def test_15_roteiro_de_cada_cena_tem_passos_e_duracao_padrao_folgada(self):
        d, raiz = storyboard.carregar_da(self.proj)
        cenas = [{"cena": n, "params": {}} for n in apoio.NOMES]
        metas = {c["nome"]: c["meta"] for c in storyboard.catalogo(raiz) if c["origem"] == "skill"}
        for nome, rot in zip(apoio.NOMES, storyboard.roteiros(raiz, d, cenas)):
            # cena que explica o modelo por dentro tem pelo menos 4 ideias; as genéricas (chat, numero, conceito) podem ter 2 ou 3
            self.assertGreaterEqual(len(rot["passos"]), 4 if nome in apoio.NOMES_MODELO else 2, nome)
            self.assertTrue(all(p["anim"] > 0 and p["tipo"] in ("entrada", "enfase", "texto") for p in rot["passos"]), nome)
            self.assertGreaterEqual(metas[nome]["dur_padrao"], rot["recomendada"], f"{nome}: dur_padrao {metas[nome]['dur_padrao']} < recomendada {rot['recomendada']}")


if __name__ == "__main__":
    unittest.main()
