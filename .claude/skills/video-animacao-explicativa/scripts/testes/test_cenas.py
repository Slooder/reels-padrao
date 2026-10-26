# -*- coding: utf-8 -*-
"""Todas as cenas da biblioteca no motor de verdade (Chromium + ffmpeg, sempre sob a trava global do kit).

A lista de cenas é a PASTA cenas/ (apoio.NOMES): cena nova entra em todos os testes sem ser registrada em lugar nenhum.
Para CADA cena: quadro do meio em horizontal e vertical, em dois presets bem diferentes (lab-ia e editorial-claro),
passando pelo auditor C3; lint estrito; pureza (o quadro T avulso é o quadro T do vídeo); os erros de dado que só
aparecem no build; o caso apertado (vertical do neon-shorts) e, num terceiro preset, os três formatos de vídeo.
Tudo em escala reduzida (480×270 / 270×480) e a 6 quadros por segundo: com 19 cenas a suíte leva cerca de 4 minutos
numa máquina livre (mais, se a fila da trava estiver ocupada por outro processo)."""
import json
import unittest
from pathlib import Path

from testes import apoio
import da  # noqa: E402  (apoio põe o kit no caminho)
import da_ext_motor  # noqa: E402
import video  # noqa: E402
from PIL import Image, ImageChops, ImageStat

PRESETS = ("lab-ia", "editorial-claro")
FORMATOS = ("horizontal", "vertical")
ESCALA = 0.25
FPS = 6


def motor(d, args):
    return da_ext_motor.render([*args, "--inatividade", "90"], da_obj=d, capturar=True, rotulo="teste das cenas de IA")


class TestCenas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.area = apoio.Area()
        cls.das = {p: da.carregar(str(cls.area.projeto(p))) for p in PRESETS}
        cls.metas = {}
        import storyboard
        for c in storyboard.catalogo(None):
            if c["origem"] == "skill":
                cls.metas[c["nome"]] = c["meta"]

    @classmethod
    def tearDownClass(cls):
        cls.area.limpar()

    def test_01_lint_estrito_nas_cenas_e_nos_scripts(self):
        alvos = [str(apoio.CENAS), str(apoio.CENAS / "_ia.js"), str(apoio.SCRIPTS / "storyboard.py"), str(apoio.SCRIPTS / "cenas.mjs")]
        rel = da.lint(alvos, da=self.das["lab-ia"], estrito=True)
        self.assertTrue(rel["ok"], json.dumps(rel["achados"][:5], ensure_ascii=False) + json.dumps(rel.get("nao_conferidos"), ensure_ascii=False))
        self.assertGreaterEqual(rel["arquivos"], len(apoio.NOMES) + 3)

    def test_02_quadro_do_meio_passa_no_auditor_em_2_presets_e_2_formatos(self):
        for preset in PRESETS:
            d = self.das[preset]
            pasta = Path(d.raiz) / "animacoes" / "_quadros"
            pasta.mkdir(parents=True, exist_ok=True)
            fila = [{"cena": str(apoio.CENAS / f"{n}.js"), "saida": f"{n}_{f}.png", "formato": f, "escala": ESCALA, "quadro": round(self.metas[n]["dur_padrao"] * 0.6, 2)}
                    for n in apoio.NOMES for f in FORMATOS]
            (pasta / "_fila.json").write_text(json.dumps(fila), encoding="utf-8")
            r = motor(d, ["--fila", str(pasta / "_fila.json"), "--json"])
            self.assertEqual(r.returncode, 0, f"{preset}: {r.stderr[-3000:]}")
            res = json.loads(r.stdout[r.stdout.index("{"):])
            self.assertEqual((len(res["renderizados"]), res["falhas"]), (len(fila), []), preset)
            for j in fila:
                arq = pasta / j["saida"]
                car = da.ler_carimbo(arq)
                self.assertEqual((car["auditoria"], car["da_sha256"]), ("ok", d.sha256), arq.name)
                self.assertEqual(car["parametros"]["livres"], [], f"{arq.name}: nenhuma cena da biblioteca usa data-da-livre")
                lay = car["parametros"]["layout"]
                self.assertTrue(lay["ilustrativo"], arq.name)
                c, a = lay["conteudo"], lay["area"]
                self.assertTrue(a["x"] <= c["x"] and c["x"] + c["w"] <= a["x"] + a["w"] + 1 and a["y"] <= c["y"] and c["y"] + c["h"] <= a["y"] + a["h"] + 1, f"{arq.name}: conteúdo fora da zona segura")
                bloco = lay.get("bloco") or lay.get("mosaico") or lay.get("plano") or lay.get("rede") or lay.get("grafico") or lay.get("painel")
                self.assertIsNotNone(bloco, arq.name)
                im = Image.open(arq).convert("RGB")
                L, A = d.dimensoes(j["formato"])
                self.assertEqual(im.size, (round(L * ESCALA), round(A * ESCALA)), arq.name)
                self.assertGreater(sum(ImageStat.Stat(im).stddev), 12, f"{arq.name}: quadro quase vazio")
            sem = da.conferir_carimbo([str(pasta / j["saida"]) for j in fila], da=d)
            self.assertTrue(sem["ok"], preset)

    def test_03_pureza_quadro_avulso_igual_ao_quadro_do_video(self):
        d = self.das["lab-ia"]
        pasta = Path(d.raiz) / "animacoes" / "_pureza"
        pasta.mkdir(parents=True, exist_ok=True)
        fila, planos = [], []
        for n in apoio.NOMES:
            dur = self.metas[n]["dur_padrao"]
            k = int(dur * 0.55 * FPS)                             # um quadro no meio de um passo, longe da saída
            comum = {"cena": str(apoio.CENAS / f"{n}.js"), "formato": "horizontal", "escala": ESCALA, "dur": dur}
            fila.append({**comum, "saida": f"{n}.mp4", "fps": str(FPS)})
            fila.append({**comum, "saida": f"{n}.png", "quadro": k / FPS})
            planos.append((n, k))
        (pasta / "_fila.json").write_text(json.dumps(fila), encoding="utf-8")
        r = motor(d, ["--fila", str(pasta / "_fila.json"), "--json"])
        self.assertEqual(r.returncode, 0, r.stderr[-3000:])                # o próprio motor confere a pureza em 4 instantes de cada vídeo
        for n, k in planos:
            car = da.ler_carimbo(pasta / f"{n}.mp4")
            self.assertEqual(car["midia"]["quadros"], round(self.metas[n]["dur_padrao"] * FPS), n)
            self.assertGreater(car["parametros"]["quadros_reaproveitados"], 0, f"{n}: key(t) não reaproveitou nenhum quadro parado")
            nomes = [a["nome"] for a in car["parametros"]["ancoras"]]
            self.assertEqual(nomes[-1], "saida", n)
            passos = [p["nome"] for p in car["parametros"]["layout"]["passos"]]
            self.assertEqual([x for x in nomes[:-1] if x in passos], passos, f"{n}: todo passo vira âncora, na ordem")
            # além dos passos, a cena pode marcar âncoras dentro de um passo (P.marcar: fim_da_resposta, valor_final, fim_da_digitacao)
            ts = [a["t"] for a in car["parametros"]["ancoras"]]
            self.assertEqual(ts, sorted(ts), f"{n}: âncoras fora de ordem")
            self.assertTrue(all(0 <= a["t"] <= self.metas[n]["dur_padrao"] and a["tipo"] in ("entrada", "enfase", "texto", "saida") for a in car["parametros"]["ancoras"]), n)
            do_video = pasta / f"_{n}_do_video.png"
            video.extrair_quadro(str(pasta / f"{n}.mp4"), (k + 0.5) / FPS, str(do_video))
            a, b = Image.open(pasta / f"{n}.png").convert("RGB"), Image.open(do_video).convert("RGB")
            self.assertEqual(a.size, b.size, n)
            dif = sum(ImageStat.Stat(ImageChops.difference(a, b)).mean) / 3
            self.assertLess(dif, 3.0, f"{n}: o quadro {k} do vídeo difere do PNG avulso (diferença média {dif:.2f} de 255)")

    def test_05_letra_grande_no_vertical_nao_encavala(self):
        # neon-shorts tem a maior escala tipográfica e a maior faixa de legenda: é onde as fileiras se encostavam
        d = da.carregar(str(self.area.projeto("neon-shorts")))
        pasta = Path(d.raiz) / "animacoes" / "_apertado"
        pasta.mkdir(parents=True, exist_ok=True)
        fila = [{"cena": str(apoio.CENAS / f"{n}.js"), "saida": f"{n}.png", "formato": "vertical", "escala": ESCALA, "quadro": round(self.metas[n]["dur_padrao"] * 0.6, 2)} for n in apoio.NOMES]
        (pasta / "_fila.json").write_text(json.dumps(fila), encoding="utf-8")
        r = motor(d, ["--fila", str(pasta / "_fila.json")])
        self.assertEqual(r.returncode, 0, r.stderr[-3000:])
        lay = {n: da.ler_carimbo(pasta / f"{n}.png")["parametros"]["layout"] for n in apoio.NOMES}
        self.assertEqual(lay["rag"]["arranjo"], "coluna_so_titulos")           # sem altura para abrir os trechos, ficam os títulos
        self.assertTrue(lay["agente"]["contexto_rola"])                        # a lista do contexto rola em vez de encolher a letra
        self.assertGreaterEqual(lay["treino"]["fileira"]["passo"], lay["treino"]["fileira"]["ficha"])
        self.assertGreaterEqual(lay["rede_neural"]["passo_no"], 2 * lay["rede_neural"]["raio_no"])
        nota = d.px(d["tipografia"]["escala"]["nota"], "vertical")
        for n in ("tokenizacao", "atencao", "proximo_token", "treino"):
            chave = "tamanho_token" if "tamanho_token" in lay[n] else "tamanho_ficha"
            self.assertGreaterEqual(lay[n][chave], nota - 0.5, f"{n}: letra abaixo do mínimo legível da DA")
        for n in apoio.NOMES:
            c, b = lay[n]["conteudo"], lay[n].get("bloco")
            if b:
                self.assertLessEqual(b["y"] + b["h"], c["y"] + c["h"] + 2, f"{n}: o bloco passa da área de conteúdo ({b} × {c})")
                self.assertGreaterEqual(b["y"], c["y"] - 2, f"{n}: o bloco começa acima da área de conteúdo ({b} × {c})")
            if b and "w" in b:
                self.assertTrue(c["x"] - 2 <= b["x"] and b["x"] + b["w"] <= c["x"] + c["w"] + 2, f"{n}: o bloco sai pelos lados ({b} × {c})")
            for chave, valor in lay[n].items():                                # toda letra que a cena declara no carimbo
                if chave.startswith("tamanho_") and isinstance(valor, (int, float)):
                    self.assertGreaterEqual(valor, nota - 0.5, f"{n}.{chave} = {valor}: abaixo do mínimo legível da DA ({nota})")

    def test_04_passos_t_manda_no_ritmo_e_erros_de_dado_falam_claro(self):
        d = self.das["lab-ia"]
        pasta = Path(d.raiz) / "animacoes" / "_casos"
        pasta.mkdir(parents=True, exist_ok=True)
        tok = str(apoio.CENAS / "tokenizacao.js")
        cena = lambda nome: str(apoio.CENAS / f"{nome}.js")       # noqa: E731

        def quadro(cena, params, nome, dur=None, formato="horizontal"):
            args = ["--cena", cena, "--saida", str(pasta / nome), "--formato", formato, "--escala", str(ESCALA), "--quadro", "5", "--params", json.dumps(params, ensure_ascii=False)]
            return motor(d, args + (["--dur", str(dur)] if dur else []))

        r = quadro(tok, {"passos_t": [0.5, 2.0, 4.0, 6.0]}, "passos.png", dur=9)
        self.assertEqual(r.returncode, 0, r.stderr[-2000:])
        lay = da.ler_carimbo(pasta / "passos.png")["parametros"]["layout"]
        self.assertEqual([p["t"] for p in lay["passos"]], [0.5, 2.0, 4.0, 6.0])
        casos = [
            (tok, {"passos_t": [3, 2]}, "ordem crescente"),
            (tok, {"passos_t": [0, 1, 2, 8.9]}, "cai na saída da cena"),
            (tok, {"ilustrativo": False}, 'passe também "fonte"'),
            (tok, {"tokens": ["a", "b"], "ids": [1]}, "um número por pedaço"),
            (str(apoio.CENAS / "atencao.js"), {"tokens": ["o", "gato", "mia"]}, 'faltou "pesos"'),
            (str(apoio.CENAS / "atencao.js"), {"pesos": [0.5, 0.5, 0.5, 0.5, 0.5]}, "soma 1"),
            (str(apoio.CENAS / "atencao.js"), {"consulta": 1, "pesos": [0.2, 0.3, 0.5, 0, 0]}, "causal=true"),
            (str(apoio.CENAS / "proximo_token.js"), {"semente": 4}, "A cena não força o resultado do sorteio"),
            (str(apoio.CENAS / "embeddings.js"), {"destaque": "tigre"}, "não está em pontos"),
            (str(apoio.CENAS / "rede_neural.js"), {"camadas": [2, 3, 1], "entradas": [1, 2, 3]}, "1ª camada tem 2"),
            (str(apoio.CENAS / "difusao.js"), {"imagem": ["......", "..##..", "..#?..", "......", "......", "......"]}, 'símbolo "?"'),
            (str(apoio.CENAS / "janela_contexto.js"), {"blocos": [{"tokens": 60, "tipo": "entrada"}, {"tokens": 60, "tipo": "saida"}, {"tokens": 60, "tipo": "entrada"}]}, "até 140"),
            # cenas de sistema e genéricas
            (cena("rag"), {"resposta": "A troca leva 30 dias."}, "nenhuma citação"),
            (cena("rag"), {"k": 1}, "o modelo não pode citar o que não recebeu"),
            (cena("agente"), {"voltas": [{"ferramenta": "buscar", "resultado": " "}]}, "faltou a ferramenta ou o resultado"),
            (cena("fluxo"), {"ligacoes": [{"de": "texto", "para": "nuvem"}]}, "não é id de nenhum nó"),
            (cena("fluxo"), {"ordem": [["texto", "tokens"]]}, 'faltou o nó "modelo"'),
            (cena("comparativo"), {"opcoes": [{"nome": "X", "valores": ["1", "2", "3"]}, {"nome": "Y", "valores": ["4", "5", "6"]}]}, "diga se estes dados são reais ou inventados"),
            (cena("comparativo"), {"ilustrativo": True, "opcoes": [{"nome": "X", "valores": ["1"]}, {"nome": "Y", "valores": ["4", "5", "6"]}]}, "é um valor por critério"),
            (cena("linha_do_tempo"), {"escala": "tempo"}, 'não tem "ano"'),
            (cena("terminal"), {"blocos": [{"comando": "  "}]}, "o comando está vazio"),
            (cena("chat"), {"mensagens": [{"de": "modelo", "texto": "Olá, mundo", "tokens": ["Olá", " mundo"]}]}, "não remonta o texto"),
            (cena("numero"), {"valor": 200, "unidade": " mil tokens"}, "diga se estes dados são reais ou inventados"),
            (cena("numero"), {"valor": 200, "ilustrativo": False}, 'passe também "fonte"'),
            (cena("conceito"), {"termo": "RAG"}, 'faltou "definicao"'),
            (cena("versus"), {"lados": [{"titulo": " ", "itens": ["a"]}, {"titulo": "B", "itens": ["b"]}]}, "não podem ser vazios"),
            (cena("lista"), {"itens": ["um", " "]}, "há um tópico vazio"),
        ]
        for cena, params, trecho in casos:
            r = quadro(cena, params, "erro.png")
            self.assertEqual(r.returncode, 1, f"{Path(cena).name} {params}: {r.stderr[-600:]}")
            self.assertIn(trecho, r.stderr, f"{Path(cena).name} {params}")
            self.assertFalse((pasta / "erro.png").exists())
        # dado real: com fonte, o selo sai e o crédito do kit entra, dentro da zona segura
        r = quadro(tok, {"ilustrativo": False, "fonte": "Laboratório Exemplo, out/2026", "ids": [1, 2, 3, 4, 5, 6, 7]}, "real.png", formato="vertical")
        self.assertEqual(r.returncode, 0, r.stderr[-2000:])
        lay = da.ler_carimbo(pasta / "real.png")["parametros"]["layout"]
        self.assertFalse(lay["ilustrativo"])
        cr, a = lay["credito"], lay["area"]
        self.assertTrue(a["x"] <= cr["x"] and cr["x1"] <= a["x"] + a["w"] + 1 and a["y"] <= cr["y"] and cr["y1"] <= a["y"] + a["h"] + 1, "crédito fora da zona segura")
        # a semente decide o sorteio e o carimbo registra o que saiu
        r = quadro(str(apoio.CENAS / "proximo_token.js"), {}, "sorteio.png")
        self.assertEqual(r.returncode, 0, r.stderr[-2000:])
        sorteios = da.ler_carimbo(pasta / "sorteio.png")["parametros"]["layout"]["sorteios"]
        self.assertEqual([s["token"] for s in sorteios], [" Paris", ",", " cidade"])
        self.assertTrue(all(0 <= s["u"] < 1 for s in sorteios))

    def test_07_o_que_as_cenas_de_sistema_fazem_com_os_dados(self):
        d = self.das["lab-ia"]
        pasta = Path(d.raiz) / "animacoes" / "_sistema"
        pasta.mkdir(parents=True, exist_ok=True)
        casos = {
            # número real: sem selo, com o crédito do kit dentro da zona, e o texto final é exatamente o valor pedido
            "numero": ("vertical", {"valor": 1234.5, "casas": 1, "prefixo": "US$ ", "unidade": " mil", "rotulo": "Preço · Modelo X", "ilustrativo": False, "fonte": "Laboratório Exemplo, out/2026"}),
            # dados próprios declarados como exemplo: selo ligado
            "comparativo": ("horizontal", {"ilustrativo": True, "criterios": ["Custo"], "opcoes": [{"nome": "Plano X", "valores": ["baixo"]}, {"nome": "Plano Y", "valores": ["alto"]}], "destaque_opcao": 1}),
            # a busca ORDENA pela pontuação: com k = 3 entram os três de maior pontuação, na ordem
            "rag": ("horizontal", {"k": 3, "resposta": "Trinta dias [1], doze meses [2] e depende do CEP [3]."}),
            # tokens informados: o contador conta os tokens de verdade
            "chat": ("vertical", {"mensagens": [{"de": "usuario", "texto": "Oi?"}, {"de": "modelo", "texto": "Olá, mundo!", "tokens": ["Ol", "á", ",", " mundo", "!"]}]}),
            # ligação que volta é desenhada como retorno; nó fora de `ordem` seria erro (test_04)
            "fluxo": ("vertical", {"destaque": "modelo"}),
            # eixo proporcional ao ano: contínuo
            "linha_do_tempo": ("horizontal", {"ilustrativo": True, "escala": "tempo", "marcos": [{"data": "2001", "titulo": "A", "ano": 2001}, {"data": "2004", "titulo": "B", "ano": 2004}, {"data": "2010", "titulo": "C", "ano": 2010}]}),
            # texto do roteiro: sem selo; com ilustrativo=true o selo aparece
            "lista": ("horizontal", {"itens": ["um", "dois"], "ilustrativo": True}),
        }
        fila = [{"cena": str(apoio.CENAS / f"{n}.js"), "saida": f"{n}.png", "formato": f, "escala": ESCALA, "quadro": round(self.metas[n]["dur_padrao"] * 0.9, 2), "params": pr} for n, (f, pr) in casos.items()]
        (pasta / "_fila.json").write_text(json.dumps(fila, ensure_ascii=False), encoding="utf-8")
        r = motor(d, ["--fila", str(pasta / "_fila.json")])
        self.assertEqual(r.returncode, 0, r.stderr[-3000:])
        lay = {n: da.ler_carimbo(pasta / f"{n}.png")["parametros"]["layout"] for n in casos}
        self.assertEqual((lay["numero"]["texto_final"], lay["numero"]["ilustrativo"], lay["numero"]["selo"]), ("US$ 1.234,5 mil", False, False))
        cr, a = lay["numero"]["credito"], lay["numero"]["area"]
        self.assertTrue(a["x"] <= cr["x"] and cr["x1"] <= a["x"] + a["w"] + 1 and a["y"] <= cr["y"] and cr["y1"] <= a["y"] + a["h"] + 1, "crédito fora da zona segura")
        self.assertEqual((lay["comparativo"]["selo"], lay["comparativo"]["disposicao"], lay["comparativo"]["passos"][-1]["nome"]), (True, "tabela", "destaque"))
        self.assertEqual([x["titulo"] for x in lay["rag"]["recuperados"]], ["Trocas e devoluções", "Garantia", "Entrega"])
        self.assertEqual([x["pontuacao"] for x in lay["rag"]["recuperados"]], [0.91, 0.62, 0.44])
        self.assertEqual((lay["chat"]["recorte"], lay["chat"]["tokens"]), ("informado", [5]))
        self.assertEqual((lay["fluxo"]["retornos"], lay["fluxo"]["sentido"], lay["fluxo"]["passos"][-1]["nome"]), (["proximo>tokens"], "vertical", "destaque"))
        self.assertEqual((lay["linha_do_tempo"]["eixo"], lay["linha_do_tempo"]["escala_do_eixo"]), ("continuo", "tempo"))
        self.assertTrue(lay["lista"]["selo"])
        # sem selo quando a cena só mostra o texto do roteiro (o padrão das cenas de texto)
        r = motor(d, ["--cena", str(apoio.CENAS / "lista.js"), "--saida", str(pasta / "lista_texto.png"), "--escala", str(ESCALA), "--quadro", "5", "--params", json.dumps({"itens": ["um", "dois"]})])
        self.assertEqual(r.returncode, 0, r.stderr[-2000:])
        self.assertFalse(da.ler_carimbo(pasta / "lista_texto.png")["parametros"]["layout"]["selo"])

    def test_06_todas_as_cenas_da_pasta_nos_tres_formatos_num_terceiro_preset(self):
        # A lista vem do disco, não de uma constante: cena nova que reprove no auditor derruba a suíte no dia em que entra.
        nomes = sorted(a.stem for a in apoio.CENAS.glob("*.js") if not a.name.startswith("_"))
        self.assertEqual(sorted(self.metas), nomes, "o catálogo do storyboard e a pasta cenas/ têm de listar as mesmas cenas")
        self.assertEqual(sorted(apoio.NOMES_MODELO + apoio.NOMES_SISTEMA), nomes, "cena nova: registre a família em testes/apoio.py e documente em references/catalogo.md")
        d = da.carregar(str(self.area.projeto("quadro-negro")))
        pasta = Path(d.raiz) / "animacoes" / "_todas"
        pasta.mkdir(parents=True, exist_ok=True)
        formatos = ("horizontal", "vertical", "quadrado")
        fila = [{"cena": str(apoio.CENAS / f"{n}.js"), "saida": f"{n}_{f}.png", "formato": f, "escala": ESCALA, "quadro": round(self.metas[n]["dur_padrao"] * 0.5, 2)} for n in nomes for f in formatos]
        (pasta / "_fila.json").write_text(json.dumps(fila), encoding="utf-8")
        r = motor(d, ["--fila", str(pasta / "_fila.json"), "--json"])
        res = json.loads(r.stdout[r.stdout.index("{"):]) if "{" in r.stdout else {"falhas": [{"cena": "?", "saida": "?", "erro": r.stderr[-2000:]}], "renderizados": []}
        falhas = [f'{Path(f["cena"]).stem} ({Path(f["saida"]).stem}): {f["erro"][:300]}' for f in res["falhas"]]
        self.assertEqual(falhas, [], "cenas reprovadas no motor (auditor, pureza ou erro de build)")
        self.assertEqual((r.returncode, len(res["renderizados"])), (0, len(fila)))
        for j in fila:
            car = da.ler_carimbo(pasta / j["saida"])
            self.assertEqual((car["auditoria"], car["parametros"]["livres"]), ("ok", []), j["saida"])
            self.assertEqual(car["parametros"]["layout"]["area"]["reservou_legenda"], j["formato"] != "horizontal", j["saida"])

    def test_08_tudo_o_que_e_desenhado_fica_na_area_livre(self):
        # O auditor confere cor e fonte, não posição; `layout.bloco` é o que a cena DIZ que ocupou. Aqui se mede o que
        # ela desenhou de fato: render com fundo transparente (sem grão), caixa dos pixels visíveis × d.area_livre().
        # neon-shorts é o caso duro: tarja inclinada (−3°), a maior letra e a maior faixa de legenda. Foi este teste que
        # achou o chapéu inclinado saindo pelo topo, a moldura de janela_contexto saindo pelos lados e o nome da
        # ferramenta de `agente` vazando da caixa — nada disso reprovava no auditor.
        d = da.carregar(str(self.area.projeto("neon-shorts")))
        pasta = Path(d.raiz) / "animacoes" / "_zona"
        pasta.mkdir(parents=True, exist_ok=True)
        esc = 0.5                                                 # a 0,25 o contorno suavizado engana a checagem de quietude do motor em fundo transparente
        fila = []
        for n in apoio.NOMES:
            dur = self.metas[n]["dur_padrao"]
            for f in ("horizontal", "vertical", "quadrado"):
                for rotulo, t in (("meio", round(dur * 0.55, 2)), ("fim", round(dur - 1.3, 2))):
                    fila.append({"cena": str(apoio.CENAS / f"{n}.js"), "saida": f"{n}_{f}_{rotulo}.png", "formato": f, "escala": esc, "quadro": t, "alfa": True})
        pendentes, falhas = fila, []
        for tentativa in (1, 2):                                  # uma repetição só para a falha intermitente de quietude (pendência do kit)
            (pasta / "_fila.json").write_text(json.dumps(pendentes), encoding="utf-8")
            r = motor(d, ["--fila", str(pasta / "_fila.json"), "--json"])
            res = json.loads(r.stdout[r.stdout.index("{"):])
            falhas = res["falhas"]
            inquietas = {Path(f["saida"]).name for f in falhas if "se mexe fora de seek" in f["erro"]}
            if not falhas or len(inquietas) != len(falhas) or tentativa == 2:
                break
            pendentes = [j for j in fila if j["saida"] in inquietas]
        self.assertEqual([f'{Path(f["saida"]).stem}: {f["erro"][:200]}' for f in falhas], [])
        fora = []
        for j in fila:
            al = d.area_livre(j["formato"])
            caixa = Image.open(pasta / j["saida"]).getchannel("A").point(lambda v: 255 if v > 24 else 0).getbbox()
            self.assertIsNotNone(caixa, f'{j["saida"]}: quadro vazio')
            x0, y0, x1, y1 = (v / esc for v in caixa)
            tol = 2 / esc + 1                                      # um pixel do quadro reduzido + arredondamento
            if x0 < al["x0"] - tol or y0 < al["y0"] - tol or x1 > al["x1"] + tol or y1 > al["y1"] + tol:
                fora.append(f'{Path(j["saida"]).stem}: desenhou ({x0:.0f}, {y0:.0f})–({x1:.0f}, {y1:.0f}); área livre ({al["x0"]}, {al["y0"]})–({al["x1"]}, {al["y1"]})')
        self.assertEqual(fora, [], "cenas que desenham fora da zona segura (menos a faixa da legenda)")


if __name__ == "__main__":
    unittest.main()
