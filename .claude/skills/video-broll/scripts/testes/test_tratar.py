"""Tratamento na direção de arte: trecho, velocidade, encaixe, cadeia do grade.json, moldura do motor, carimbo e registro.
Sem rede. Usa ffmpeg e o motor do kit (Chromium) sob a trava global, com vídeos de 320×180 e até 1,5 s."""
import contextlib
import io
import json
import unittest
from pathlib import Path

from testes import apoio

import comum
import registro
import tratar


def _saida(*args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            rc = comum.rodar(lambda: tratar.main(list(args)))
        except SystemExit as e:
            rc = e.code
    return rc, out.getvalue(), err.getvalue()


def _quadro(video, arquivo, t, destino):
    from PIL import Image
    video.extrair_quadro(arquivo, t, destino)
    with Image.open(destino) as im:
        return im.convert("RGB").copy()


def _saturacao(im) -> float:
    import numpy as np
    a = np.asarray(im.convert("HSV"), dtype=float)
    return float(a[..., 1].mean())


class Tratar(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.video_bytes = apoio.video_sintetico()
        cls.kit = comum.importar_kit()

    def setUp(self):
        self.tmp = apoio.pasta_temporaria(self)

    def projeto(self, base="lab-ia", nome=None, **campos):
        """Projeto com DA e um vídeo de teste registrado como B001 (material próprio, salvo `campos`)."""
        raiz, d = apoio.projeto(self.tmp, nome or f"Vídeo de teste {base}", base)
        fonte = self.tmp / "fonte do teste.mp4"
        fonte.write_bytes(self.video_bytes)
        iid = registro.registrar_arquivo(raiz, fonte, **({"autor": "Canal de teste"} | campos))
        return raiz, d, iid

    def test_01_trata_carimba_e_registra_nos_dois_formatos(self):
        da, _texto, video, _trava = self.kit
        raiz, d, iid = self.projeto()
        rc, out, err = _saida(iid, "--formato", "320x180", "180x320", "--t0", "0.5", "--dur", "1", "--projeto", str(raiz))
        self.assertEqual(rc, 0, err + out)
        for nome, (L, A) in (("B001_320x180.mp4", (320, 180)), ("B001_180x320.mp4", (180, 320))):
            peca = raiz / "broll" / "tratado" / nome
            s = video.sondar(peca)
            self.assertEqual((s["largura"], s["altura"]), (L, A))
            self.assertAlmostEqual(s["duracao"], 1.0, delta=0.08)
            self.assertFalse(s["tem_audio"], "o áudio sai por padrão")
            self.assertEqual(s["pix_fmt"], "yuv420p")
            self.assertEqual(s["fps"], video.fps_do_formato(d, f"{L}x{A}"), "o encode leva o fps do formato na DA")
            c = da.ler_carimbo(peca)
            self.assertEqual((c["ferramenta"], c["da_sha256"], c["auditoria"]), ("video-broll", d.sha256, "n/a"))
            p = c["parametros"]
            self.assertEqual((p["id"], p["origem"], p["licenca"], p["base_legal"], p["trecho"], p["velocidade"], p["cor_tratada"], p["moldura"]),
                             ("B001", "broll/bruto/B001.mp4", "Material próprio", "proprio", {"t0": 0.5, "t1": 1.5}, 1.0, True, "nenhuma"))
            self.assertEqual(p["cadeia"], video.filtro_tratamento(d, f"{L}x{A}"), "a cadeia é a do grade.json, não uma daqui")
            self.assertEqual(p["origem_sha256"], registro.obter(raiz, iid)["sha256"])
            self.assertEqual([i["arquivo"] for i in c["insumos"]], ["B001.mp4"])
        self.assertEqual(da.ler_carimbo(raiz / "broll" / "tratado" / "B001_320x180.mp4")["parametros"]["encaixe"], "mesma proporção")
        self.assertEqual(da.ler_carimbo(raiz / "broll" / "tratado" / "B001_180x320.mp4")["parametros"]["encaixe"], "desfocado")
        item = registro.obter(raiz, iid)
        self.assertEqual(item["tratados"], ["broll/tratado/B001_180x320.mp4", "broll/tratado/B001_320x180.mp4"])
        self.assertIsNone(item["trecho"], "`trecho` no registro é o intervalo da FONTE: o tratamento não o regrava (o trecho da peça está no carimbo)")
        pedido = da.ler_carimbo(raiz / "broll" / "tratado" / "B001_320x180.mp4")["parametros"]["pedido"]
        self.assertEqual(pedido, {"t0": 0.5, "dur": 1.0}, "o carimbo guarda as opções como foram pedidas")
        conf = da.conferir_carimbo([raiz / "broll" / "tratado"], da=d)
        self.assertTrue(conf["ok"], conf)
        self.assertEqual(len(conf["pecas"]), 2)
        rc, out, _ = _saida("--todos", "--formato", "320x180", "180x320", "--projeto", str(raiz))
        self.assertEqual(rc, 0)
        self.assertIn("Nada a tratar", out)

    def test_02_a_mesma_peca_muda_de_cara_quando_a_da_muda(self):
        _da, _texto, video, _trava = self.kit
        from PIL import ImageChops, ImageStat
        quadros = {}
        for base in ("lab-ia", "dossie"):
            raiz, d, iid = self.projeto(base)
            self.assertEqual(_saida(iid, "--formato", "320x180", "--t0", "0.2", "--dur", "0.6", "--projeto", str(raiz))[0], 0)
            quadros[base] = _quadro(video, raiz / "broll" / "tratado" / "B001_320x180.mp4", 0.3, raiz / "qa" / "_q.png")
            if base == "lab-ia":
                bruto = _quadro(video, raiz / "broll" / "bruto" / "B001.mp4", 0.5, raiz / "qa" / "_bruto.png")
        self.assertLess(_saturacao(quadros["dossie"]), _saturacao(bruto) - 5, "dossiê: saturação 0,78 tira cor do bruto")
        self.assertLess(_saturacao(quadros["dossie"]), _saturacao(quadros["lab-ia"]))
        diferenca = ImageStat.Stat(ImageChops.difference(quadros["lab-ia"], quadros["dossie"])).mean
        self.assertGreater(sum(diferenca) / 3, 2.0, "dois presets, dois tratamentos — sem tocar no código")

    def test_03_recorte_com_foco_velocidade_e_audio(self):
        da, _texto, video, _trava = self.kit
        raiz, d, iid = self.projeto()
        rc, out, err = _saida(iid, "--formato", "180x320", "--encaixe", "recorte", "--foco", "0.9,0.5", "--t0", "0", "--t1", "1.2", "--velocidade", "0.5",
                              "--com-audio", "--projeto", str(raiz))
        self.assertEqual(rc, 0, err)
        peca = raiz / "broll" / "tratado" / "B001_180x320.mp4"
        s = video.sondar(peca)
        self.assertAlmostEqual(s["duracao"], 2.4, delta=0.12, msg="metade da velocidade, o dobro da duração")
        self.assertTrue(s["tem_audio"])
        p = da.ler_carimbo(peca)["parametros"]
        self.assertEqual((p["encaixe"], p["foco"], p["velocidade"], p["audio"]), ("recorte", [0.9, 0.5], 0.5, True))
        self.assertIn("setpts=PTS/0.5", p["filtro"])
        self.assertRegex(p["filtro"], r"crop=180:320:\d+:0")
        x = int(p["filtro"].split("crop=180:320:")[1].split(":")[0])
        self.assertGreater(x, 300, "foco à direita: o recorte anda para a direita")
        rc, out, err = _saida(iid, "--formato", "180x320", "--encaixe", "faixas", "--dur", "0.5", "--projeto", str(raiz))
        self.assertEqual(rc, 0, err)
        self.assertIn(d.cor("fundo").replace("#", "0x"), da.ler_carimbo(peca)["parametros"]["filtro"], "as faixas levam a cor do token, não uma cor daqui")

    def test_04_moldura_do_motor_com_rotulo_e_credito(self):
        da, _texto, video, _trava = self.kit
        raiz, d, iid = self.projeto("dossie", fonte="wikimedia", base_legal="licenca", licenca="CC BY 4.0", autor="Maria Exemplo",
                                    pagina_url="https://commons.wikimedia.org/wiki/File:Exemplo.webm")
        rc, out, err = _saida(iid, "--formato", "320x180", "--dur", "1.2", "--moldura", "--rotulo", "Arquivo · 2024", "--projeto", str(raiz))
        self.assertEqual(rc, 0, err + out)
        peca = raiz / "broll" / "tratado" / "B001_320x180.mp4"
        mold = raiz / "broll" / "tratado" / "_moldura" / "B001_320x180.webm"
        self.assertTrue(mold.is_file())
        cm = da.ler_carimbo(mold)
        self.assertEqual((cm["ferramenta"], cm["auditoria"]), ("motor", "ok"), "a moldura passa pelo auditor do motor")
        pm = cm["parametros"]["params"]
        self.assertEqual((pm["estilo"], pm["rotulo"], pm["sub"]), ("cantoneiras", "Arquivo · 2024", "Maria Exemplo · CC BY 4.0"))
        c = da.ler_carimbo(peca)
        self.assertEqual((c["parametros"]["moldura"], c["parametros"]["rotulo"], c["parametros"]["credito_na_tela"]), ("cantoneiras", "Arquivo · 2024", "Maria Exemplo · CC BY 4.0"))
        self.assertEqual(sorted(i["arquivo"] for i in c["insumos"]), ["B001.mp4", "B001_320x180.webm"])
        self.assertTrue(da.conferir_carimbo([raiz / "broll" / "tratado"], da=d)["ok"])
        # a moldura entra animada e fica até o último quadro (b-roll termina em corte): a saída da cena cai depois do fim da peça
        self.assertFalse(list((raiz / "broll" / "tratado" / "_moldura").glob("*sonda*")), "a sonda de layout não fica no disco")
        self.assertGreaterEqual(cm["parametros"]["layout"]["inicio_saida"], 1.2)
        self.assertGreater(cm["midia"]["duracao"], 1.2 + d.dur("media"))
        fim_q = _quadro(video, peca, 1.12, raiz / "qa" / "_fim.png")
        margem = round(d["tratamento"]["moldura"]["margem"] * 180)
        perto = [fim_q.getpixel((margem + dx, margem + dy)) for dx in range(0, 4) for dy in range(0, 4)]
        amarelado = [px for px in perto if px[0] > 180 and px[1] > 140 and px[2] < min(px[0], px[1]) - 40]     # primária do dossiê, já misturada pelo 4:2:0
        self.assertTrue(amarelado, f"cantoneira ausente no último instante: {perto[:4]}")

    def test_04b_vertical_com_janela_mantem_o_rotulo_e_o_credito_numa_linha(self):
        """Regressão: no vertical do lab-ia o rótulo pedido era descartado e, mesmo assim, o crédito saía em duas linhas, quebrado
        no meio do nome («MARIA EXEMPLO DA / SILVA · CC BY 4.0») ou da licença («… · CC / BY 4.0» a 540×960)."""
        da, _texto, video, _trava = self.kit
        raiz, d, iid = self.projeto("lab-ia", fonte="wikimedia", base_legal="licenca", licenca="CC BY 4.0", autor="Maria Exemplo da Silva",
                                    pagina_url="https://commons.wikimedia.org/wiki/File:Exemplo.webm")
        rc, out, err = _saida(iid, "--formato", "540x960", "--dur", "0.6", "--moldura", "--moldura-fixa", "--rotulo", "Arquivo · 2024", "--projeto", str(raiz))
        self.assertEqual(rc, 0, err + out)
        self.assertNotIn("retirado", out)
        peca = raiz / "broll" / "tratado" / "B001_540x960.mp4"
        p = da.ler_carimbo(peca)["parametros"]
        self.assertEqual((p["moldura"], p["rotulo"]), ("janela", "Arquivo · 2024"), "o rótulo que o usuário pediu fica")
        credito = p["credito_na_tela"]
        self.assertTrue(credito.endswith("· CC BY 4.0"), f"a licença nunca é cortada: {credito!r}")
        self.assertTrue(credito.startswith("Maria Exemplo"), credito)
        self.assertIn("…", credito, "a 540 px de largura o nome inteiro não cabe numa linha: o autor é encurtado")
        self.assertIn("encurtado para caber numa linha", out)
        lay = da.ler_carimbo(raiz / "broll" / "tratado" / "_moldura" / "B001_540x960_fixa.png")["parametros"]["layout"]
        alt = d.fonte("dados")["altura_linha"]
        for nome, tam in (("rotulo", lay["tamanho_rotulo"]), ("sub", lay["tamanho_sub"])):
            self.assertLess(lay[nome]["h"], 1.6 * alt * tam, f"{nome} em mais de uma linha: {lay[nome]}")
            self.assertGreaterEqual(lay[nome]["x"], lay["zona"]["x"] - 1)
            self.assertLessEqual(lay[nome]["x1"], lay["zona"]["x1"] + 1)
        self.assertTrue(lay["rotulo_na_zona"])
        self.assertGreaterEqual(lay["tamanho_sub"], lay["minimo_legivel"] - 0.01)
        self.assertLessEqual(lay["rotulo"]["y1"], lay["sub"]["y"] + 1, "sem espaço para os dois lado a lado: rótulo em cima, crédito embaixo")
        self.assertEqual(registro.obter(raiz, iid)["credito_tela"], "Maria Exemplo da Silva · CC BY 4.0", "o registro (e a descrição) ficam com o texto completo")
        plano = tratar.Plano(d, self.kit, registro.obter(raiz, iid), "540x960", {"dur": 0.6})
        self.assertEqual(plano._linhas({"h": 2 * alt * 12.0}, 12.0), 2)
        self.assertEqual(plano._linhas({"h": alt * 12.0 + 0.55 * 12.0}, 12.0), 1, "uma linha dentro de um chip (borda, cantoneiras) continua sendo uma")
        self.assertEqual(tratar._quebra_no_separador("Maria Exemplo da Silva · CC BY 4.0"), "Maria\u00a0Exemplo\u00a0da\u00a0Silva ·\u00a0CC\u00a0BY\u00a04.0")

    def test_05_moldura_de_janela_poe_o_video_dentro_e_respeita_rotulo_desligado(self):
        da, _texto, video, _trava = self.kit
        raiz, d, iid = self.projeto("lab-ia", fonte="nasa", base_legal="licenca", autor="NASA", titulo="Terra", pagina_url="https://images.nasa.gov/details/x")
        rc, out, err = _saida(iid, "--formato", "320x180", "--dur", "1", "--moldura", "--moldura-fixa", "--projeto", str(raiz))
        self.assertEqual(rc, 0, err + out)
        p = da.ler_carimbo(raiz / "broll" / "tratado" / "B001_320x180.mp4")["parametros"]
        self.assertEqual((p["moldura"], p["credito_na_tela"], p["moldura_animada"]), ("janela", "NASA", False))
        self.assertTrue(p["encaixe"].startswith("janela da moldura"))
        j = p["janela"]
        self.assertLess(j["w"], 320)
        self.assertLess(j["h"], 180)
        self.assertIn("gblur", p["filtro"], "o fundo da janela é o próprio material desfocado (tokens de encaixe)")
        self.assertEqual(p["cadeia"], video.filtro_tratamento(d, f"{j['w']}x{j['h']}"))
        raiz2, d2, iid2 = self.projeto("neon-shorts", fonte="nasa", base_legal="licenca", titulo="Terra", pagina_url="https://images.nasa.gov/details/x")
        self.assertFalse(d2["tratamento"]["moldura"]["rotulo"])
        rc, out, err = _saida(iid2, "--formato", "320x180", "--dur", "0.8", "--moldura", "--rotulo", "Arquivo", "--projeto", str(raiz2))
        self.assertEqual(rc, 0, err + out)
        self.assertIn("a DA desliga o rótulo", out)
        p2 = da.ler_carimbo(raiz2 / "broll" / "tratado" / "B001_320x180.mp4")["parametros"]
        self.assertEqual((p2["moldura"], p2["rotulo"], p2["credito_na_tela"]), ("borda", None, None))

    def test_05b_janela_com_fundo_chapado_quando_a_da_pede_faixas(self):
        da, _texto, video, _trava = self.kit
        raiz, d, iid = self.projeto("quadro-negro", nome="Vídeo com faixas")
        j = json.loads((raiz / "da" / "da.json").read_text(encoding="utf-8"))
        j["tratamento"]["encaixe"] = {"modo": "faixas", "cor": "superficie"}
        (raiz / "da" / "da.json").write_text(json.dumps(j, ensure_ascii=False, indent=2), encoding="utf-8")
        d = da.carregar(raiz)
        rc, out, err = _saida(iid, "--formato", "320x180", "--dur", "0.8", "--moldura", "--rotulo", "Arquivo", "--moldura-fixa", "--projeto", str(raiz))
        self.assertEqual(rc, 0, err + out)
        peca = raiz / "broll" / "tratado" / "B001_320x180.mp4"
        p = da.ler_carimbo(peca)["parametros"]
        self.assertEqual(p["moldura"], "polaroid")
        self.assertIn("color=c=" + d.cor("superficie").replace("#", "0x"), p["filtro"], "fundo chapado na cor do token de encaixe")
        self.assertNotIn("gblur", p["filtro"])
        self.assertIn("rotate=", p["filtro"], "a polaroid é inclinada: o vídeo gira com ela")
        q = _quadro(video, peca, 0.4, raiz / "qa" / "_q.png")
        canto = q.getpixel((2, 2))
        self.assertTrue(all(abs(a - b) < 28 for a, b in zip(canto, d.rgb("superficie"))), f"{canto} × {d.rgb('superficie')}")

    def test_06_citacao_so_recebe_moldura_e_credito(self):
        da, _texto, video, _trava = self.kit
        raiz, d, iid = self.projeto("dossie", fonte="youtube", base_legal="citacao", autor="Canal Tal", titulo="Palestra",
                                    pagina_url="https://www.youtube.com/watch?v=x", notas="trecho comentado no vídeo")
        self.assertEqual(iid, "Y001")
        plano = tratar.Plano(d, self.kit, registro.obter(raiz, iid), "320x180", {"dur": 0.8})
        self.assertEqual((plano.com_cor, plano.estilo, plano.rotulo, plano.credito), (False, "cantoneiras", "Reprodução", "Canal Tal · YouTube"))
        rc, out, err = _saida(iid, "--formato", "320x180", "--dur", "0.8", "--projeto", str(raiz))
        self.assertEqual(rc, 0, err + out)
        self.assertIn("cor original", out)
        p = da.ler_carimbo(raiz / "broll" / "tratado" / "Y001_320x180.mp4")["parametros"]
        self.assertEqual((p["cor_tratada"], p["cadeia"], p["base_legal"], p["credito_na_tela"]), (False, "null", "citacao", "Canal Tal · YouTube"))
        self.assertNotIn("eq=", p["filtro"])
        sem = tratar.Plano(d, self.kit, registro.obter(raiz, iid), "320x180", {"dur": 0.8, "moldura": False, "credito": False})
        self.assertEqual((sem.estilo, sem.credito, sem.tem_overlay), ("nenhuma", None, False))

    def test_07_imagem_vira_plano_parado_e_previa_nao_grava_peca(self):
        da, _texto, video, _trava = self.kit
        from PIL import Image
        raiz, d = apoio.projeto(self.tmp, "Vídeo com foto", "editorial-claro")
        foto = self.tmp / "foto de teste.png"
        Image.linear_gradient("L").resize((640, 480)).convert("RGB").save(foto)
        iid = registro.registrar_arquivo(raiz, foto, fonte="web", base_legal="proprio", prefixo="W", notas="Foto feita pela equipe e publicada no site do canal.")
        self.assertEqual((iid, registro.obter(raiz, iid)["tipo"]), ("W001", "imagem"))
        rc, out, err = _saida(iid, "--formato", "320x180", "--dur", "0.7", "--projeto", str(raiz))
        self.assertEqual(rc, 0, err + out)
        s = video.sondar(raiz / "broll" / "tratado" / "W001_320x180.mp4")
        self.assertEqual((s["largura"], s["altura"]), (320, 180))
        self.assertAlmostEqual(s["duracao"], 0.7, delta=0.08)
        self.assertIsNone(registro.obter(raiz, iid)["trecho"])
        fonte = self.tmp / "fonte.mp4"
        fonte.write_bytes(self.video_bytes)
        vid = registro.registrar_arquivo(raiz, fonte)
        rc, out, err = _saida(vid, "--formato", "320x180", "180x320", "--dur", "1", "--previa", "--projeto", str(raiz))
        self.assertEqual(rc, 0, err + out)
        folha = raiz / "broll" / "_previa" / f"{vid}.png"
        self.assertTrue(folha.is_file())
        with Image.open(folha) as im:
            self.assertGreater(im.width, 800)
            self.assertEqual(im.convert("RGB").getpixel((2, 2)), d.rgb("fundo"))
        self.assertFalse((raiz / "broll" / "tratado" / f"{vid}_320x180.mp4").exists(), "--previa não grava a peça")
        self.assertEqual(registro.obter(raiz, vid)["tratados"], [])

    def test_08_erros_de_uso_saem_antes_de_qualquer_render(self):
        raiz, d, iid = self.projeto()
        casos = [((iid, "--t0", "9", "--projeto", str(raiz)), 1, "segundos DO ARQUIVO"),
                 (("B999", "--projeto", str(raiz)), 64, "fora do registro"),
                 ((iid, "--formato", "panoramico", "--projeto", str(raiz)), 64, "panoramico"),
                 ((iid, "--foco", "2,3", "--projeto", str(raiz)), 64, "--foco"),
                 ((iid, "--area", "0.5,0.5,0.9,0.9", "--projeto", str(raiz)), 64, "--area"),
                 ((iid, "--t0", "1", "--t1", "0.5", "--projeto", str(raiz)), 64, "--t1"),
                 (("--projeto", str(raiz)), 64, "ID"),
                 ((iid, "--moldura", "--sem-moldura", "--projeto", str(raiz)), 64, "não pode vir junto")]
        for args, codigo, trecho in casos:
            rc, out, err = _saida(*args)
            self.assertEqual(rc, codigo, f"{args}: {err}")
            self.assertIn(trecho, err)
            self.assertNotIn("Traceback", err)
        self.assertFalse(list((raiz / "broll" / "tratado").glob("*.mp4")))
        vazio = self.tmp / "sem projeto"
        vazio.mkdir()
        rc, _, err = _saida("B001", "--projeto", str(vazio))
        self.assertEqual(rc, 2)
        self.assertIn("video-direcao-de-arte", err)
        (raiz / "broll" / "bruto" / "B001.mp4").unlink()
        rc, _, err = _saida(iid, "--t0", "0", "--projeto", str(raiz))
        self.assertEqual(rc, 1)
        self.assertIn("sumiu do disco", err)


    def test_09_trecho_da_fonte_que_nao_cabe_no_arquivo_e_aviso_nao_erro(self):
        """`trecho` no registro é o intervalo da FONTE (50–60 s do vídeo original); quando o arquivo baixado já é o recorte
        (2 s), o tratamento usa o arquivo inteiro e avisa. `trecho_arquivo`, quando existe, é o padrão."""
        da, _texto, video, _trava = self.kit
        raiz, d, iid = self.projeto()
        registro.atualizar(raiz, iid, trecho={"t0": 50, "t1": 60})
        rc, out, err = _saida(iid, "--formato", "320x180", "--projeto", str(raiz))
        self.assertEqual(rc, 0, err + out)
        self.assertIn("não cabe em B001.mp4", out)
        self.assertIn("usei o arquivo inteiro", out)
        peca = raiz / "broll" / "tratado" / "B001_320x180.mp4"
        self.assertEqual(da.ler_carimbo(peca)["parametros"]["trecho"], {"t0": 0.0, "t1": 2.0})
        self.assertEqual(registro.obter(raiz, iid)["trecho"], {"t0": 50.0, "t1": 60.0}, "o registro não é regravado")
        registro.atualizar(raiz, iid, trecho_arquivo={"t0": 0.6, "t1": 1.4})
        rc, out, err = _saida(iid, "--formato", "320x180", "--projeto", str(raiz))
        self.assertEqual(rc, 0, err + out)
        self.assertEqual(da.ler_carimbo(peca)["parametros"]["trecho"], {"t0": 0.6, "t1": 1.4}, "trecho_arquivo é o padrão do tratamento")
        self.assertAlmostEqual(video.sondar(peca)["duracao"], 0.8, delta=0.08)

    def test_10_desatualizados_refaz_com_as_mesmas_escolhas_quando_a_da_muda(self):
        """Regressão: depois de trocar a DA, `--todos` dizia «Nada a tratar» e a peça ficava «DA DIFERENTE» para sempre."""
        da, _texto, video, _trava = self.kit
        raiz, d, iid = self.projeto()
        rc, out, err = _saida(iid, "--formato", "180x320", "--t0", "0.4", "--dur", "0.8", "--encaixe", "recorte", "--foco", "0.8,0.5", "--projeto", str(raiz))
        self.assertEqual(rc, 0, err + out)
        peca = raiz / "broll" / "tratado" / "B001_180x320.mp4"
        antes = da.ler_carimbo(peca)
        rc, out, _ = _saida("--desatualizados", "--projeto", str(raiz))
        self.assertEqual(rc, 0)
        self.assertIn("Nada a refazer", out)
        j = json.loads((raiz / "da" / "da.json").read_text(encoding="utf-8"))
        j["tratamento"]["grade"]["saturacao"] = 0.4                      # a DA mudou: a identidade é outra
        (raiz / "da" / "da.json").write_text(json.dumps(j, ensure_ascii=False, indent=2), encoding="utf-8")
        d2 = da.carregar(raiz)
        self.assertNotEqual(d2.sha256, antes["da_sha256"])
        conf = da.conferir_carimbo([peca], da=d2)
        self.assertFalse(conf["ok"], "o kit acusa a peça: é o «DA DIFERENTE» de `da conferir-carimbo`")
        self.assertNotEqual(conf["pecas"][0]["estado"], "ok")
        velhas = tratar.pecas_desatualizadas(d2, da, raiz, registro.carregar(raiz)["itens"])
        self.assertEqual([(v["item"]["id"], v["formato"], v["motivo"]) for v in velhas], [("B001", "180x320", "feita com outra direção de arte")])
        rc, out, err = _saida("--todos", "--formato", "180x320", "--projeto", str(raiz))
        self.assertEqual(rc, 0)
        self.assertIn("Nada a tratar", out)
        self.assertIn("--desatualizados", err, "--todos não refaz, mas avisa que há peça velha")
        rc, _, err = _saida("--desatualizados", iid, "--projeto", str(raiz))
        self.assertEqual(rc, 64)
        rc, _, err = _saida("--desatualizados", "--foco", "0.1,0.1", "--projeto", str(raiz))
        self.assertEqual(rc, 64)
        self.assertIn("--foco", err)
        rc, out, err = _saida("--desatualizados", "--projeto", str(raiz))
        self.assertEqual(rc, 0, err + out)
        self.assertIn("refeita porque estava feita com outra direção de arte", out)
        depois = da.ler_carimbo(peca)
        self.assertEqual(depois["da_sha256"], d2.sha256)
        for chave in ("trecho", "encaixe", "foco", "velocidade", "moldura", "audio"):
            self.assertEqual(depois["parametros"][chave], antes["parametros"][chave], f"{chave} mudou ao refazer")
        self.assertNotEqual(depois["parametros"]["cadeia"], antes["parametros"]["cadeia"], "a cadeia é a da DA nova")
        self.assertTrue(da.conferir_carimbo([peca], da=d2)["ok"])
        self.assertEqual(tratar.pecas_desatualizadas(d2, da, raiz, registro.carregar(raiz)["itens"]), [])
        self.assertEqual(registro.obter(raiz, iid)["tratados"], ["broll/tratado/B001_180x320.mp4"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
