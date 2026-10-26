#!/usr/bin/env python3
"""tratar.py — do b-roll bruto ao tratado NA DIREÇÃO DE ARTE do projeto, numa passada de ffmpeg por formato:
trecho (t0/t1) → velocidade (token) → encaixe no formato (recorte com âncora/foco, fundo desfocado ou faixas) →
tratamento (cadeia do grade.json: cor, grão, vinheta, nitidez) → moldura da DA com rótulo e crédito (opcional) →
encode da casa, sem áudio → carimbo com origem, licença e insumos → `tratados` no registro.

    tratar.py B001 --formato horizontal vertical --t0 12 --t1 17 --previa      # antes × depois, sem gravar a peça
    tratar.py B001 --formato horizontal vertical --t0 12 --t1 17               # broll/tratado/B001_horizontal.mp4 e _vertical.mp4
    tratar.py B002 --formato vertical --encaixe recorte --foco 0.62,0.4 --moldura --rotulo "Arquivo · 2019"

Nenhuma cor, fonte, curva ou moldura é decidida aqui: tudo vem dos tokens `tratamento.*` da DA. Material registrado como
citação (base_legal "citacao") recebe por padrão só moldura e crédito — a cor do original não é alterada."""
from __future__ import annotations

import json
import re
import sys
from fractions import Fraction
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum  # noqa: E402
import registro  # noqa: E402

FERRAMENTA = "video-broll"
PASTA_MOLDURA = registro.PASTA_TRATADO / "_moldura"
PASTA_PREVIA = Path("broll") / "_previa"
DUR_IMAGEM = 5.0
MOLDURAS_DE_JANELA = ("janela", "polaroid")          # o vídeo entra DENTRO da moldura; nas outras, a moldura vai por cima


def _par(x: float) -> int:
    return max(2, int(round(x / 2)) * 2)


def _n(x: float, casas: int = 3) -> str:
    s = f"{float(x):.{casas}f}".rstrip("0").rstrip(".")
    return s or "0"


def _quebra_no_separador(credito: str) -> str:
    """O crédito com os espaços de dentro de cada parte trocados por espaço inseparável: se a moldura precisar quebrar a
    linha, só pode fazê-lo no separador («Autor» numa linha, «· CC BY 4.0» na outra)."""
    partes = re.split(r" (?=[·/] )", credito)
    return " ".join(parte.replace(" ", "\u00a0") for parte in partes)


class Plano:
    """Tudo o que uma saída precisa, resolvido antes de qualquer processo pesado (erro de uso sai antes da fila da trava)."""

    def __init__(self, d, kit, item: dict, formato: str, op: dict):
        da, _texto, video, _trava = kit
        self.d, self.item, self.op = d, item, op
        self.raiz = Path(d.raiz)
        self.formato_pedido = formato
        self.L, self.A = d.dimensoes(formato)
        self.formato = video.nome_do_formato(d, self.L, self.A)
        self.fps = video.fps_do_formato(d, formato)
        if not item.get("arquivo"):
            raise comum.Erro(f"{item['id']} está no registro mas não tem arquivo baixado.", "Baixe com baixar.py … --confirmar (depois da aprovação do usuário).")
        self.origem = self.raiz / item["arquivo"]
        if not self.origem.is_file():
            raise comum.Erro(f"o arquivo de {item['id']} sumiu do disco: {self.origem}", "Baixe de novo ou corrija `arquivo` no registro (registro.py atualizar).")
        self.imagem = item.get("tipo") == "imagem" or self.origem.suffix.lower() in da.EXT_IMAGEM
        if self.imagem:
            from PIL import Image, ImageOps
            with Image.open(self.origem) as im:
                self.ol, self.oa = ImageOps.exif_transpose(im).size
            self.dur_origem = None
        else:
            s = video.sondar(self.origem)
            self.ol, self.oa, self.dur_origem = s["largura"], s["altura"], float(s["duracao"] or 0)
            if not self.ol or self.dur_origem <= 0:
                raise comum.Erro(f"{self.origem.name} não tem trilha de vídeo legível.", "Confira o arquivo com ffprobe; se for imagem, registre com tipo=imagem.")
        # trecho, em segundos DO ARQUIVO: linha de comando > `trecho_arquivo` do registro (a parte aprovada dentro do que foi
        # baixado) > `trecho` do registro quando cabe no arquivo (ele é o intervalo da FONTE: só serve se o arquivo for a fonte
        # inteira) > o arquivo inteiro. Nada daqui é gravado de volta no registro: o trecho de cada peça fica no carimbo dela.
        self.avisos = []
        if self.imagem:
            self.t0, self.t1 = 0.0, float(op.get("dur") or DUR_IMAGEM)
        else:
            explicito = op.get("t0") is not None or op.get("t1") is not None
            base = None
            for campo in ("trecho_arquivo", "trecho"):
                tr = item.get(campo)
                if not tr or base is not None:
                    continue
                if tr["t1"] <= self.dur_origem + 0.1:
                    base = tr
                    if campo == "trecho" and not explicito:
                        self.avisos.append(f"usei o trecho {tr['t0']:g}–{tr['t1']:g} s do registro como segundos do arquivo ({self.dur_origem:.1f} s); "
                                           "se o arquivo já é o recorte, passe --t0 0")
                elif not explicito:
                    self.avisos.append(f"o {campo} do registro ({tr['t0']:g}–{tr['t1']:g} s) não cabe em {self.origem.name} ({self.dur_origem:.2f} s)"
                                       + (": ele é o intervalo da FONTE e o arquivo já é o recorte — usei o arquivo inteiro" if campo == "trecho" else ": ignorado"))
            t0 = op.get("t0") if op.get("t0") is not None else (base["t0"] if base else 0.0)
            t1 = op.get("t1") if op.get("t1") is not None else (t0 + op["dur"] if op.get("dur") else (base["t1"] if base and base["t1"] > t0 else self.dur_origem))
            if t0 < 0 or t0 >= self.dur_origem - 0.04:
                raise comum.Erro(f"o trecho começa em {t0:g} s, mas {self.origem.name} tem {self.dur_origem:.2f} s.",
                                 "--t0, --t1 e --dur são segundos DO ARQUIVO baixado (o que está em broll/bruto/), não do vídeo original.")
            self.t0, self.t1 = float(t0), float(min(t1, self.dur_origem))
            if self.t1 - self.t0 < 0.2:
                raise comum.Erro(f"trecho curto demais ({self.t1 - self.t0:.2f} s).", "Use pelo menos 0,2 s; b-roll costuma ter de 2 a 8 s.")
        # velocidade: token da DA, salvo pedido explícito
        self.velocidade = float(op.get("velocidade") or d["tratamento"]["velocidade"])
        if not 0.1 <= self.velocidade <= 10:
            raise comum.Erro(f"velocidade {self.velocidade:g} fora de 0,1–10.", codigo=comum.SAIDA_USO)
        self.dur = (self.t1 - self.t0) / (1.0 if self.imagem else self.velocidade)
        # citação: só moldura e crédito, cor intacta
        self.citacao = item.get("base_legal") == "citacao"
        self.com_cor = (not self.citacao) if op.get("cor") is None else bool(op["cor"])
        mold = d["tratamento"]["moldura"]
        quer_moldura = self.citacao if op.get("moldura") is None else bool(op["moldura"])
        self.estilo = mold["estilo"] if quer_moldura else "nenhuma"
        self.rotulo_permitido = bool(mold.get("rotulo", True))
        cred = op.get("credito")
        if cred is None:                                   # padrão: crédito quando há moldura com rótulo, e sempre na citação
            cred = self.citacao or (quer_moldura and self.rotulo_permitido and bool(item.get("credito_tela")))
        self.credito = (cred if isinstance(cred, str) else item.get("credito_tela") or registro.credito_curto(item)) if cred else None
        self.rotulo = op.get("rotulo") or ("Reprodução" if self.citacao and quer_moldura else None)
        if self.rotulo and not self.rotulo_permitido:
            self.avisos.append("a DA desliga o rótulo da moldura (tratamento.moldura.rotulo = false): o rótulo não foi desenhado. "
                               "Para tê-lo, proponha uma revisão da DA — não é exceção de peça.")
            self.rotulo = None
        self.tem_overlay = self.estilo != "nenhuma" or bool(self.credito) or bool(self.rotulo)
        self.janela = self.estilo in MOLDURAS_DE_JANELA
        self.encaixe = op.get("encaixe") or (d["tratamento"].get("encaixe") or {}).get("modo") or "desfocado"
        self.ancora = op.get("ancora") or d["tratamento"]["recorte"]["ancora"]
        self.foco = op.get("foco")
        self.plataforma = op.get("plataforma")
        self.area = op.get("area")
        self.reservar_legenda = op.get("reservar_legenda")
        self.fixa = bool(op.get("moldura_fixa"))
        self.com_audio = bool(op.get("com_audio")) and not self.imagem
        self.crf = int(op.get("crf") or 18)
        self.saida = self.raiz / registro.PASTA_TRATADO / f"{item['id']}_{formato}.mp4"
        self.moldura_arq = None
        self.layout = None

    # ── moldura (cena do motor, com alfa) ──
    def params_moldura(self) -> dict:
        p = {"estilo": self.estilo}
        if self.rotulo:
            p["rotulo"] = self.rotulo
        if self.credito:
            p["sub"] = self.credito
        if self.plataforma:
            p["plataforma"] = self.plataforma
        if self.area:
            p["area"] = list(self.area)
        if self.reservar_legenda is not None:
            p["reservar_legenda"] = self.reservar_legenda
        return p

    def _linhas(self, ret: dict | None, tamanho: float | None, papel: str = "dados") -> int:
        """Em quantas linhas a moldura pôs um texto (rótulo ou crédito), pela altura do retângulo que o carimbo devolve.
        Uma linha mede altura_linha × tamanho (mais o respiro do chip, em borda e cantoneiras); duas, o dobro."""
        if not ret or not tamanho:
            return 0
        alt = float(self.d.fonte(papel).get("altura_linha") or 1.25)
        return 1 if ret["h"] <= (1.5 * alt + 0.3) * tamanho else max(2, round(ret["h"] / (alt * tamanho)))

    def _largura_do_credito(self) -> float:
        """Largura que a moldura dá ao crédito, em px, estimada pelo layout: da esquerda do texto até a borda direita da
        janela (janela, polaroid) ou da zona segura (borda, cantoneiras), menos o respiro lateral."""
        lay = self.layout or {}
        sub, jan, zona = lay.get("sub") or {}, lay.get("janela") or {}, lay.get("zona") or {}
        direita = jan.get("x", 0) + jan.get("w", self.L)
        if not self.janela:
            direita = min(direita, zona.get("x1", self.L))
        return max(1.0, direita - sub.get("x", 0) - (0.9 if self.janela else 1.5) * float(lay.get("tamanho_sub") or 0))

    def render_moldura(self, kit, quadro: float | None = None) -> Path:
        """Renderiza a cena `moldura` do kit no tamanho da saída (WebM com alfa; PNG quando `quadro` é dado) e lê o layout.
        A moldura entra animada e NÃO sai: a cena é renderizada mais longa que a peça, para a saída dela cair depois do
        último quadro (b-roll termina em corte).

        A cena faz rótulo e crédito caberem sozinha (lado a lado; se não der, empilha e quebra em até 2 linhas). Aqui só se
        cuida do que ela não sabe: crédito quebrado no meio do nome ou da licença é feio e confunde — antes do render final,
        uma sonda (um PNG da mesma cena, ~1 s) mede o layout e, se o crédito ocupou mais de uma linha, o NOME DO AUTOR é
        encurtado até caber numa (a licença nunca; o texto completo continua em `atribuicao`, para a descrição). O rótulo
        pedido não é sacrificado: quando os dois não cabem lado a lado, ficam em duas linhas no cabeçalho."""
        da, _texto, _video, _trava = kit
        if str(comum.kit()) not in sys.path:
            sys.path.insert(0, str(comum.kit()))
        import da_ext_motor
        pasta = self.raiz / PASTA_MOLDURA
        pasta.mkdir(parents=True, exist_ok=True)
        base = f"{self.item['id']}_{self.formato_pedido}"
        alvo = pasta / (base + ("_fixa.png" if quadro is not None else ".webm"))
        sonda = alvo if quadro is not None else pasta / f"_{base}_sonda.png"
        dur_cena = self.dur + self.d.dur("media") + self.d.dur("curta") + 0.2

        def cena(saida: Path, instante: float | None) -> dict:
            args = ["--cena", "moldura", "--saida", str(saida), "--formato", f"{self.L}x{self.A}", "--dur", _n(dur_cena),
                    "--fps", f"{self.fps.numerator}/{self.fps.denominator}", "--params", json.dumps(self.params_moldura(), ensure_ascii=False)]
            args += ["--quadro", _n(instante), "--alfa"] if instante is not None else ["--codec", "vp9alfa"]
            r = da_ext_motor.render(args, da_obj=self.d, cwd=self.raiz, rotulo="moldura de b-roll", capturar=True)
            if r.returncode != 0:
                raise comum.Erro(f"o motor não renderizou a moldura (código {r.returncode}):\n{(r.stderr or r.stdout or '').strip()[-600:]}",
                                 "Se o erro fala em auditor ou cor, o problema está na DA ou no kit — não contorne com --sem-auditoria.", r.returncode if r.returncode in (2, 64, 75, 124) else 1)
            return ((da.ler_carimbo(saida) or {}).get("parametros") or {}).get("layout") or {}

        original = self.credito
        do_registro = bool(original) and original == (self.item.get("credito_tela") or registro.credito_curto(self.item))
        if self.credito or self.rotulo:                        # só texto pede sonda: moldura sem rótulo nem crédito não tem o que ajustar
            instante = quadro if quadro is not None else self.dur
            self.layout = cena(sonda, instante)
            limite = len(self.credito or "")
            for _tentativa in range(4):
                lay = self.layout
                if not self.credito or self._linhas(lay.get("sub"), lay.get("tamanho_sub")) <= 1:
                    break
                sub, linhas = lay["sub"], self._linhas(lay.get("sub"), lay.get("tamanho_sub"))
                por_letra = max(1.0, sub["w"]) / max(1.0, len(self.credito) / linhas)        # a linha mais larga tem ~len/linhas letras
                limite = min(limite - 2, int(self._largura_do_credito() / por_letra) - 1)     # só encolhe, nunca volta a crescer
                if limite < 12:
                    break
                novo = registro.credito_curto({**self.item, "credito_tela": None}, maximo=limite) if do_registro else original
                self.credito = novo if len(novo) <= limite else original[:limite - 1].rstrip(" ·/,") + "…"
                self.layout = cena(sonda, instante)
            if self.credito and self._linhas(self.layout.get("sub"), self.layout.get("tamanho_sub")) > 1:
                # nem com o autor encurtado coube numa linha: volta o texto inteiro, com a quebra presa ao separador
                # (autor numa linha, licença na outra) — nunca no meio do nome ou da licença
                self.credito = _quebra_no_separador(original)
                self.layout = cena(sonda, instante)
                self.avisos.append(f"o crédito «{original}» não cabe numa linha desta moldura: ficou em duas, com a quebra entre o autor e a licença. "
                                   "Use --area ou --plataforma para dar largura, ou --credito \"texto mais curto\"")
            elif self.credito and self.credito != original:
                self.avisos.append(f"crédito na tela encurtado para caber numa linha: «{self.credito}» (o texto completo vai na descrição, em `atribuicao`)")
            papel_rotulo = "subtitulo" if self.estilo == "polaroid" else "dados"
            if self.rotulo and self._linhas(self.layout.get("rotulo"), self.layout.get("tamanho_rotulo"), papel_rotulo) > 1:
                self.avisos.append(f"o rótulo «{self.rotulo}» quebrou em mais de uma linha nesta moldura: encurte-o (duas ou três palavras)")
        if quadro is None:
            self.layout = cena(alvo, None)
            if sonda != alvo:
                for resto in (sonda, sonda.with_name(sonda.name + ".da.json")):
                    resto.unlink(missing_ok=True)
        elif not (self.credito or self.rotulo):
            self.layout = cena(alvo, quadro)
        jan = self.layout.get("janela") or {}
        if self.janela and not self.area and jan.get("w") and jan.get("h"):
            fracao = jan["w"] * jan["h"] / float(self.L * self.A)
            if fracao < 0.35:                                   # no vertical a zona segura só deixa ~61 % da largura e a legenda reserva a base
                self.avisos.append(f"a moldura «{self.estilo}» fica numa janela de {jan['w']:.0f}×{jan['h']:.0f} px — {fracao:.0%} do quadro {self.L}×{self.A} "
                                   "(o cabeçalho tem de caber na zona segura e fora da faixa da legenda). O material é recortado para a janela: mire com --foco x,y. "
                                   "Para o b-roll em TELA CHEIA com rótulo e crédito na zona segura, tire o --moldura e use --encaixe recorte --foco x,y --credito")
        if self.layout.get("rotulo_na_zona") is False and (self.credito or self.rotulo):
            zona = (self.layout.get("zona") or {}).get("plataforma") or "padrão"
            self.avisos.append(f"rótulo ou crédito ficaram fora da zona segura «{zona}»" + (" com esta --area" if self.area else "")
                               + ": no app, podem ficar sob a interface. Encurte o texto ou dê largura (--area, --plataforma)")
        self.moldura_arq = alvo
        return alvo

    # ── grafo de filtros ──
    def _encaixar(self, video, alvo_l: int, alvo_a: int, forcar_recorte: bool = False) -> tuple[str, str]:
        """Filtro que leva a origem ao tamanho alvo, e o modo usado."""
        if abs(self.ol / self.oa - alvo_l / alvo_a) < 0.01:
            return f"scale={alvo_l}:{alvo_a}:flags=lanczos", "mesma proporção"
        if forcar_recorte or self.encaixe == "recorte":
            return video.filtro_recorte((self.ol, self.oa), (alvo_l, alvo_a), self.ancora, self.foco)["filtro"], "recorte"
        return video.filtro_encaixe((self.ol, self.oa), (alvo_l, alvo_a), modo=self.encaixe, d=self.d)["filtro"], self.encaixe

    def grafo(self, kit, moldura_parada: bool = False) -> dict:
        """filter_complex da saída. Entrada 0 = bruto; entrada 1 = moldura (quando há). Devolve {filtro, modo, cadeia_tratamento}."""
        _da, _texto, video, _trava = kit
        d, L, A = self.d, self.L, self.A
        pre = []
        if not self.imagem and abs(self.velocidade - 1) > 1e-6:
            pre.append(f"setpts=PTS/{_n(self.velocidade, 6)}")
        pre.append(f"fps={self.fps.numerator}/{self.fps.denominator}")
        if self.janela and self.layout:
            j = self.layout["janela_girada"]
            w, h, cx, cy, ang = _par(j["w"]), _par(j["h"]), float(j["cx"]), float(j["cy"]), float(j.get("angulo") or 0)
            enc, modo = self._encaixar(video, w, h, forcar_recorte=True)
            trat = video.filtro_tratamento(d, f"{w}x{h}") if self.com_cor else "null"
            base = f"[0:v]{','.join(pre)},{enc},setsar=1,{trat},split[jan_a][jan_b]"
            cfg = d["tratamento"].get("encaixe") or {}
            if (cfg.get("modo") or "desfocado") == "desfocado":           # fundo = o próprio material, desfocado e escurecido (tokens de encaixe)
                bl, ba = _par(L / 4), _par(A / 4)
                sig = max(0.5, float(cfg.get("desfoque", 0.035)) * min(L, A) / 4)
                esc = float(cfg.get("escurecer", 0.25))
                fundo = (f"[jan_a]scale={bl}:{ba}:force_original_aspect_ratio=increase:flags=bilinear,crop={bl}:{ba},gblur=sigma={_n(sig)},"
                         f"lutyuv=y='clip((val-minval)*{_n(max(0.0, 1 - esc))}+minval,minval,maxval)',scale={L}:{A}:flags=bilinear,setsar=1[fundo]")
            else:                                                         # fundo chapado na cor de tratamento.encaixe.cor
                fundo = (f"[jan_a]nullsink;color=c={d.cor(cfg.get('cor') or 'fundo').replace('#', '0x')}:s={L}x{A}:"
                         f"r={self.fps.numerator}/{self.fps.denominator}:d={_n(self.dur + 0.5)},setsar=1[fundo]")
            ins = "[jan_b]format=rgba"
            if not self.fixa and not moldura_parada:                      # o insert aparece junto com a moldura (que entra em `media`; a polaroid, em `longa`)
                entrada = d.dur("longa" if self.estilo == "polaroid" else "media") * 0.6    # fade linear ≈ curva de entrada (ease-out) no mesmo tempo
                ins += f",fade=t=in:st=0:d={_n(min(entrada, self.dur / 3))}:alpha=1"
            if abs(ang) > 1e-6:
                rad = f"{_n(ang, 4)}*PI/180"
                ins += f",rotate={rad}:c=none:ow=rotw({rad}):oh=roth({rad})"   # da-livre: c=none é transparência, não cor
            filtro = (f"{base};{fundo};{ins}[ins];[fundo][ins]overlay={_n(cx, 2)}-w/2:{_n(cy, 2)}-h/2:format=auto[com];"
                      f"[1:v]format=rgba[mol];[com][mol]overlay=0:0:eof_action=pass:format=auto,format=yuv420p[v]")
            return {"filtro": filtro, "modo": f"janela da moldura ({modo})", "cadeia_tratamento": trat, "janela": {"cx": cx, "cy": cy, "w": w, "h": h, "angulo": ang}}
        enc, modo = self._encaixar(video, L, A)
        trat = video.filtro_tratamento(d, f"{L}x{A}") if self.com_cor else "null"
        base = f"[0:v]{','.join(pre)},{enc},setsar=1,{trat}"
        if self.tem_overlay:
            filtro = f"{base}[b];[1:v]format=rgba[mol];[b][mol]overlay=0:0:eof_action=pass:format=auto,format=yuv420p[v]"
        else:
            filtro = f"{base},format=yuv420p[v]"
        return {"filtro": filtro, "modo": modo, "cadeia_tratamento": trat, "janela": None}

    def entradas(self, kit, t0: float | None = None, dur: float | None = None, moldura: Path | None = None) -> list[str]:
        _da, _texto, video, _trava = kit
        t0 = self.t0 if t0 is None else t0
        dur = (self.t1 - self.t0) if dur is None else dur
        r = f"{self.fps.numerator}/{self.fps.denominator}"
        if self.imagem:
            args = ["-loop", "1", "-framerate", r, "-t", _n(dur), "-i", str(self.origem)]
        else:
            args = ["-ss", _n(t0), "-t", _n(dur), "-i", str(self.origem)]
        if moldura is not None:
            if moldura.suffix.lower() == ".png":
                args += ["-loop", "1", "-framerate", r, "-t", _n(dur / (1 if self.imagem else self.velocidade) + 0.5), "-i", str(moldura)]
            else:
                args += video.entrada_com_alfa(moldura)
        return args

    def parametros(self, g: dict) -> dict:
        """O que vai para o carimbo: o suficiente para refazer a peça e para o QA saber de onde ela veio."""
        i = self.item
        return {"id": i["id"], "origem": i.get("arquivo"), "origem_sha256": i.get("sha256"), "fonte": i.get("fonte"), "pagina_url": i.get("pagina_url"),
                "autor": i.get("autor"), "licenca": i.get("licenca"), "licenca_url": i.get("licenca_url"), "base_legal": i.get("base_legal"),
                "exige_atribuicao": i.get("exige_atribuicao"), "atribuicao": i.get("atribuicao"),
                "trecho": None if self.imagem else {"t0": round(self.t0, 3), "t1": round(self.t1, 3)}, "velocidade": 1.0 if self.imagem else self.velocidade,
                "duracao": round(self.dur, 3), "encaixe": g["modo"], "ancora": self.ancora, "foco": list(self.foco) if self.foco else None,
                "cor_tratada": self.com_cor, "cadeia": g["cadeia_tratamento"], "moldura": self.estilo, "moldura_animada": self.tem_overlay and not self.fixa,
                "area": list(self.area) if self.area else None,
                "rotulo": self.rotulo, "credito_na_tela": self.credito, "plataforma": self.plataforma, "janela": g["janela"],
                "audio": self.com_audio, "filtro": g["filtro"],
                # as opções como foram pedidas (só as que fugiram do padrão): é com elas que --desatualizados refaz a peça quando a DA muda
                "pedido": {k: (list(v) if isinstance(v, tuple) else v) for k, v in self.op.items() if v is not None and not (k == "crf" and v == 18)
                           and not (v is False and k in ("moldura_fixa", "com_audio"))}}


def tratar(d, kit, plano: Plano) -> dict:
    """Grava broll/tratado/<id>_<formato>.mp4, carimba (o trecho usado fica no carimbo) e atualiza `tratados` no registro."""
    da, _texto, video, _trava = kit
    moldura = plano.render_moldura(kit, quadro=plano.dur if plano.fixa else None) if plano.tem_overlay else None
    g = plano.grafo(kit)
    args = [*plano.entradas(kit, moldura=moldura), "-filter_complex", g["filtro"], "-map", "[v]"]
    if plano.com_audio:
        args += ["-map", "0:a:0?"]
        if abs(plano.velocidade - 1) > 1e-6:
            args += ["-af", (da.ler_json(d.build / "grade.json").get("velocidade") or {}).get("audio") or f"atempo={_n(plano.velocidade, 6)}"]
    args += video.args_encode(plano.fps, crf=plano.crf, audio=plano.com_audio) + ["-t", _n(plano.dur)]
    video.executar(args, plano.saida, rotulo="tratar b-roll")
    carimbo = d.carimbar(plano.saida, FERRAMENTA, plano.formato, plano.parametros(g), insumos=[plano.origem, *([moldura] if moldura else [])])
    registro.registrar_tratado(plano.raiz, plano.item["id"], plano.saida)
    s = video.sondar(plano.saida)
    return {"id": plano.item["id"], "formato": plano.formato, "saida": str(plano.saida), "carimbo": str(carimbo), "largura": s["largura"], "altura": s["altura"],
            "duracao": round(s["duracao"], 3), "fps": str(s["fps"]), "encaixe": g["modo"], "moldura": plano.estilo, "credito": plano.credito,
            "cor_tratada": plano.com_cor, "avisos": plano.avisos}


def previa(d, kit, planos: list[Plano], instantes: int = 3) -> Path:
    """Folha «antes × depois»: para cada formato, os mesmos instantes do bruto e do tratado (mesmo grafo da peça final, um
    quadro por instante, moldura parada). Não grava peça nem mexe no registro. Vai para broll/_previa/<id>.png."""
    da, texto, video, _trava = kit
    from PIL import Image, ImageDraw, ImageOps
    p0 = planos[0]
    pasta = p0.raiz / PASTA_PREVIA / f"_{p0.item['id']}"
    pasta.mkdir(parents=True, exist_ok=True)
    fracoes = [0.5] if instantes == 1 or p0.imagem else [(k + 0.5) / instantes for k in range(instantes)]
    blocos = []
    for plano in planos:
        moldura = plano.render_moldura(kit, quadro=plano.dur) if plano.tem_overlay else None
        g = plano.grafo(kit, moldura_parada=True)
        antes, depois = [], []
        for k, f in enumerate(fracoes):
            t = plano.t0 + (plano.t1 - plano.t0) * f
            a = pasta / f"antes_{plano.formato_pedido}_{k}.png"
            if plano.imagem:
                with Image.open(plano.origem) as im:
                    ImageOps.exif_transpose(im).convert("RGB").save(a)
            else:
                video.extrair_quadro(plano.origem, t, a, largura=min(plano.ol, 960))
            b = pasta / f"depois_{plano.formato_pedido}_{k}.png"
            args = [*plano.entradas(kit, t0=t, dur=0.5, moldura=moldura), "-filter_complex", g["filtro"], "-map", "[v]", "-frames:v", "1", "-update", "1", "-threads", video.THREADS]
            video.executar(args, b, rotulo="prévia de b-roll")
            antes.append(a)
            depois.append(b)
        blocos.append((plano, g, antes, depois))

    # folha: uma faixa por formato — linha de cima o bruto, linha de baixo o tratado; tipografia e cores da DA
    alt = 300
    margem, vao = 44, 14
    e_tit = texto.Estilo.do_papel(d, "subtitulo", 30, cor="texto")
    e_rot = texto.Estilo.do_papel(d, "dados", 17, cor="texto_suave")
    e_dest = texto.Estilo.do_papel(d, "dados", 17, cor="primaria")
    faixas = []
    for plano, g, antes, depois in blocos:
        alt_d = alt if plano.L >= plano.A else int(alt * 1.55)
        linha_a = [ImageOps.contain(Image.open(x).convert("RGB"), (4000, alt)) for x in antes]
        linha_d = [ImageOps.contain(Image.open(x).convert("RGB"), (4000, alt_d)) for x in depois]
        faixas.append((plano, g, linha_a, linha_d))
    larg = max(max(sum(i.width for i in la) + vao * (len(la) - 1), sum(i.width for i in ld) + vao * (len(ld) - 1)) for _, _, la, ld in faixas)
    W = max(larg + 2 * margem, 900)
    H = margem + 86 + sum(34 + la[0].height + 34 + ld[0].height + 40 for _, _, la, ld in faixas) + margem // 2
    img = Image.new("RGBA", (W, H), d.rgba("fundo"))
    des = ImageDraw.Draw(img)
    it = p0.item
    t, _ = texto.desenhar(f"{it['id']} · antes × depois", e_tit)
    img.alpha_composite(t, (margem, margem - 6))
    sub = f"{d.meta.get('nome')} · DA revisão {d.revisao}{'' if d.aprovada else ' (não aprovada)'} · {it.get('licenca')} · {it.get('fonte')}"
    t, _ = texto.desenhar(sub, e_rot, largura_max=W - 2 * margem, max_linhas=1)
    img.alpha_composite(t, (margem, margem + 36))
    des.rectangle([margem, margem + 68, W - margem, margem + 68 + max(1, int(d["layout"]["traco"] * 400))], fill=d.rgba("primaria"))
    y = margem + 86
    for plano, g, la, ld in faixas:
        for rot, est, linha in ((f"ANTES — bruto {plano.ol}×{plano.oa}", e_rot, la),
                                (f"DEPOIS — {plano.formato + ' ' if 'x' not in plano.formato else ''}{plano.L}×{plano.A} · encaixe: {g['modo']} · "
                                 f"{'tratamento da DA' if plano.com_cor else 'cor original (citação)'} · moldura: {plano.estilo}"
                                 + (f" · crédito: {plano.credito}" if plano.credito else ""), e_dest, ld)):
            t, _ = texto.desenhar(rot, est, largura_max=W - 2 * margem, max_linhas=1)
            img.alpha_composite(t, (margem, y + 6))
            y += 34
            x = margem
            for im in linha:
                img.paste(im, (x, y))
                x += im.width + vao
            y += linha[0].height
        y += 40
    saida = p0.raiz / PASTA_PREVIA / f"{it['id']}.png"
    tmp = saida.with_name(saida.stem + ".parcial.png")
    img.convert("RGB").save(tmp, "PNG", optimize=True)
    tmp.replace(saida)
    return saida


def _op_do_carimbo(carimbo: dict | None) -> dict:
    """As opções com que uma peça foi tratada, lidas do carimbo dela (parametros.pedido + o trecho efetivamente usado)."""
    p = (carimbo or {}).get("parametros") or {}
    op = dict(p.get("pedido") or {})
    if not op:                                              # carimbo sem `pedido` (versão anterior): o que dá para ler dos parâmetros
        op = {"foco": p.get("foco"), "area": p.get("area"), "plataforma": p.get("plataforma"), "rotulo": p.get("rotulo"),
              "com_audio": bool(p.get("audio")), "moldura": True if p.get("moldura") not in (None, "nenhuma") else None,
              "encaixe": p.get("encaixe") if p.get("encaixe") in ("recorte", "faixas") else None}
    for k in ("foco", "area"):
        if op.get(k):
            op[k] = tuple(op[k])
    for k in ("t0", "t1", "dur"):
        op.pop(k, None)
    if p.get("trecho"):                                     # o trecho que a peça de fato usou, já resolvido
        op["t0"], op["t1"] = float(p["trecho"]["t0"]), float(p["trecho"]["t1"])
    elif p.get("duracao"):
        op["dur"] = float(p["duracao"])
    return op


def pecas_desatualizadas(d, da, raiz: Path, itens: list[dict]) -> list[dict]:
    """Peças de broll/tratado/ que o registro lista e que não estão em dia com a DA atual: feitas com outra identidade
    (o que `da conferir-carimbo` chama de DA DIFERENTE), sem carimbo ou sumidas do disco.
    → [{item, formato, arquivo, motivo, op | None}] (`op` None = não há carimbo de onde ler as escolhas)."""
    saida = []
    for item in itens:
        for rel in item.get("tratados") or []:
            peca = raiz / rel
            m = re.fullmatch(rf"{re.escape(str(item.get('id')))}_(.+)\.mp4", peca.name)
            if not m:
                continue
            carimbo = da.ler_carimbo(peca)
            if peca.is_file() and carimbo and carimbo.get("da_sha256") == d.sha256:
                continue
            motivo = "a peça sumiu do disco" if not peca.is_file() else "sem carimbo" if not carimbo else "feita com outra direção de arte"
            saida.append({"item": item, "formato": m.group(1), "arquivo": rel, "motivo": motivo, "op": _op_do_carimbo(carimbo) if carimbo else None})
    return saida


def _foco(texto: str | None):
    if not texto:
        return None
    try:
        x, y = (float(v) for v in texto.replace(";", ",").split(","))
        if not (0 <= x <= 1 and 0 <= y <= 1):
            raise ValueError
        return (x, y)
    except ValueError:
        raise comum.Erro(f"--foco: {texto!r} inválido.", "Use x,y em frações do quadro de origem, ex.: --foco 0.62,0.4 (0,0 = canto superior esquerdo).", comum.SAIDA_USO)


def _area(texto: str | None):
    if not texto:
        return None
    try:
        x, y, l, a = (float(v) for v in texto.replace(";", ",").split(","))
        if not (0 <= x < 1 and 0 <= y < 1 and 0 < l <= 1 - x + 1e-9 and 0 < a <= 1 - y + 1e-9):
            raise ValueError
        return (x, y, l, a)
    except ValueError:
        raise comum.Erro(f"--area: {texto!r} inválida.", "Use x,y,largura,altura em frações do quadro, dentro dele: --area 0.06,0.1,0.88,0.5.", comum.SAIDA_USO)


def main(argv=None) -> int:
    ap = comum.Parser(prog="tratar.py", description="Trata o b-roll bruto na direção de arte do projeto: trecho, velocidade, encaixe no formato, cor/grão/vinheta "
                      "(grade.json), moldura da DA com rótulo e crédito, encode da casa, carimbo e registro. Saída: broll/tratado/<id>_<formato>.mp4.",
                      epilog="Tempos em segundos DO ARQUIVO baixado (não do vídeo original). Sem --t0/--t1 vale o trecho_arquivo do registro (a parte "
                             "aprovada no download com --trecho) ou o arquivo inteiro. Formato: nome da DA (horizontal, vertical, quadrado) ou LxA par (960x540, para teste rápido).")
    ap.add_argument("ids", nargs="*", metavar="ID", help="ids do registro (B001, Y002…); com --todos, os que ainda não têm tratado")
    ap.add_argument("--todos", action="store_true", help="trata todos os itens baixados que ainda não foram tratados nos formatos pedidos")
    ap.add_argument("--desatualizados", action="store_true",
                    help="refaz, com as escolhas gravadas no carimbo de cada uma (trecho, encaixe, moldura, rótulo…), as peças de broll/tratado/ feitas "
                         "com outra direção de arte — o que `da conferir-carimbo` acusa como DA DIFERENTE depois que a DA muda")
    ap.add_argument("--formato", nargs="+", default=None, metavar="F", help="um ou mais: horizontal vertical quadrado LxA (padrão: horizontal)")
    ap.add_argument("--t0", type=float, metavar="S", help="início do trecho, em segundos do arquivo (padrão: o trecho_arquivo do registro, ou 0)")
    ap.add_argument("--t1", type=float, metavar="S", help="fim do trecho, em segundos do arquivo (padrão: o trecho_arquivo do registro, ou o fim do arquivo)")
    ap.add_argument("--dur", type=float, metavar="S", help=f"duração a partir de --t0; em imagem, quanto tempo ela fica (padrão {DUR_IMAGEM:g} s)")
    ap.add_argument("--velocidade", type=float, metavar="X", help="padrão: tratamento.velocidade da DA (0,85 = câmera lenta sutil)")
    ap.add_argument("--encaixe", choices=("recorte", "desfocado", "faixas"), help="como material de outra proporção entra no quadro (padrão: tratamento.encaixe.modo da DA)")
    ap.add_argument("--ancora", choices=("centro", "rosto", "terco_esq", "terco_dir"), help="onde ancorar o recorte (padrão: tratamento.recorte.ancora)")
    ap.add_argument("--foco", metavar="X,Y", help="ponto de interesse em frações da origem (sobrepõe a âncora), ex.: 0.62,0.4")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--moldura", dest="moldura", action="store_true", default=None, help="põe a moldura da DA (tratamento.moldura) por cima")
    g.add_argument("--sem-moldura", dest="moldura", action="store_false", help="sem moldura, mesmo em citação")
    ap.add_argument("--moldura-fixa", action="store_true", help="moldura parada do começo ao fim (sem a entrada e a saída animadas)")
    ap.add_argument("--rotulo", metavar="TEXTO", help='rótulo curto da moldura, ex.: "Arquivo · 2019"')
    c = ap.add_mutually_exclusive_group()
    c.add_argument("--credito", nargs="?", const=True, default=None, metavar="TEXTO", help="crédito na tela (sem texto: o do registro)")
    c.add_argument("--sem-credito", dest="credito", action="store_false", help="sem crédito na tela (o da descrição continua obrigatório)")
    ap.add_argument("--plataforma", metavar="ZONA", help="zona segura do rótulo e do crédito no vertical: uniao (padrão), reels, tiktok, shorts")
    ap.add_argument("--area", metavar="X,Y,L,A", help="onde fica a moldura, em frações do quadro (ex.: 0.06,0.1,0.88,0.5); padrão: a cena decide pela zona segura")
    ap.add_argument("--sem-reserva-de-legenda", dest="reservar_legenda", action="store_false", default=None,
                    help="deixa a moldura ocupar também a faixa da legenda (para peça que não leva legenda queimada)")
    k = ap.add_mutually_exclusive_group()
    k.add_argument("--sem-cor", dest="cor", action="store_false", default=None, help="não aplica a cadeia de cor/grão (padrão em citação)")
    k.add_argument("--com-cor", dest="cor", action="store_true", help="aplica o tratamento mesmo em citação")
    ap.add_argument("--com-audio", action="store_true", help="mantém o áudio do material (padrão: sem áudio)")
    ap.add_argument("--crf", type=int, default=18, help="qualidade do encode (padrão 18)")
    ap.add_argument("--previa", action="store_true", help="só a folha «antes × depois» em broll/_previa/<id>.png (não grava a peça)")
    ap.add_argument("--json", action="store_true", help="saída em JSON")
    ap.add_argument("--projeto", metavar="PASTA", help="raiz do projeto (padrão: acha pela pasta atual)")
    a = ap.parse_args(argv)
    if a.desatualizados:
        de_peca = [n for n in ("formato", "t0", "t1", "dur", "velocidade", "encaixe", "ancora", "foco", "moldura", "rotulo", "credito", "plataforma", "area",
                               "reservar_legenda", "cor") if getattr(a, n) is not None] + [n for n in ("moldura_fixa", "com_audio", "todos") if getattr(a, n)]
        if a.ids or de_peca:
            ap.error("--desatualizados refaz cada peça com as escolhas gravadas no carimbo dela: não aceita ids, --todos nem opções de peça ("
                     + ", ".join(["ids"] * bool(a.ids) + [f"--{n.replace('_', '-')}" for n in de_peca]) + "). Para mudar uma escolha, trate a peça pelo id")
    elif not a.ids and not a.todos:
        ap.error("informe pelo menos um ID do registro, --todos ou --desatualizados")
    a.formato = a.formato or ["horizontal"]
    for nome in ("t0", "t1", "dur", "velocidade"):
        v = getattr(a, nome)
        if v is not None and (v < 0 or (nome != "t0" and v <= 0)):
            ap.error(f"--{nome} precisa ser positivo")
    if a.t0 is not None and a.t1 is not None and a.t1 <= a.t0:
        ap.error("--t1 precisa ser maior que --t0")
    if not 0 <= a.crf <= 51:
        ap.error("--crf vai de 0 (sem perda) a 51; o padrão da casa é 18")
    d, da = comum.carregar_da(a.projeto)                     # Passo 0: sem DA, código 2
    kit = comum.importar_kit()
    raiz = Path(d.raiz)
    try:
        for f in dict.fromkeys(a.formato):                   # tudo o que impede o encode é conferido aqui, antes da fila
            L, A = d.dimensoes(f)
            if L % 2 or A % 2:
                raise comum.Erro(f"--formato {f}: {L}×{A} tem lado ímpar e o H.264 da casa (yuv420p) só aceita lados pares.",
                                 f"Use {L + L % 2}x{A + A % 2}.", comum.SAIDA_USO)
            if not re.fullmatch(r"\d+x\d+", f) and d.formato(f)[2] is None:
                raise comum.Erro(f"--formato {f}: é formato de imagem (sem fps na DA); b-roll tratado é vídeo.",
                                 "Use horizontal, vertical, quadrado ou LxA.", comum.SAIDA_USO)
        itens = registro.carregar(raiz)["itens"]
    except da.DAErro as e:
        raise comum.Erro(str(e), codigo=comum.SAIDA_USO)
    a.formato = list(dict.fromkeys(a.formato))
    por_id = {i["id"]: i for i in itens}
    velhas = pecas_desatualizadas(d, da, raiz, itens)
    op = {"t0": a.t0, "t1": a.t1, "dur": a.dur, "velocidade": a.velocidade, "encaixe": a.encaixe, "ancora": a.ancora, "foco": _foco(a.foco), "moldura": a.moldura,
          "moldura_fixa": a.moldura_fixa, "rotulo": a.rotulo, "credito": a.credito, "plataforma": a.plataforma, "cor": a.cor, "com_audio": a.com_audio, "crf": a.crf,
          "area": _area(a.area), "reservar_legenda": a.reservar_legenda}
    lotes = []                                               # [(id, [Plano, …])] — tudo conferido antes de entrar na fila
    try:
        if a.desatualizados:
            if not velhas:
                comum.diz("Nada a refazer: toda peça de broll/tratado/ que o registro lista está em dia com a DA atual.")
                return 0
            for v in velhas:
                if v["op"] is None or not v["item"].get("arquivo"):
                    comum.diz(f"  ! {v['arquivo']}: {v['motivo']} e não há carimbo de onde ler as escolhas — trate de novo pelo id: tratar.py {v['item']['id']} --formato {v['formato']} …", erro=True)
                    continue
                plano = Plano(d, kit, v["item"], v["formato"], {**op, **v["op"], "crf": v["op"].get("crf") or a.crf})
                plano.avisos.insert(0, f"refeita porque estava {v['motivo']}")
                lotes.append((v["item"]["id"], [plano]))
        else:
            if a.todos:
                ids = [i["id"] for i in itens if i.get("arquivo") and any(f"{registro.PASTA_TRATADO.as_posix()}/{i['id']}_{f}.mp4" not in (i.get("tratados") or []) for f in a.formato)]
                if not ids:
                    comum.diz("Nada a tratar: todo item baixado já tem tratado nesses formatos.")
            else:
                ids = a.ids
            faltam = [i for i in ids if i not in por_id]
            if faltam:
                raise comum.Erro(f"id(s) fora do registro: {', '.join(faltam)}.", f"Ids registrados: {', '.join(por_id) or 'nenhum'} (registro.py listar).", comum.SAIDA_USO)
            lotes = [(iid, [Plano(d, kit, por_id[iid], f, op) for f in a.formato]) for iid in ids]
            refeitas = {(iid, p.formato_pedido) for iid, lista in lotes for p in lista}
            sobram = [v for v in velhas if (v["item"]["id"], v["formato"]) not in refeitas]
            if sobram and not a.previa and not a.json:      # --todos não refaz o que já existe: quem mudou a DA precisa saber que há peça velha
                comum.diz(f"! {len(sobram)} peça(s) já tratada(s) não estão em dia com a DA atual ({', '.join(v['arquivo'] for v in sobram[:4])}{'…' if len(sobram) > 4 else ''}): "
                          "tratar.py --desatualizados refaz cada uma com as mesmas escolhas.", erro=True)
            if not lotes:
                return 0
    except da.DAErro as e:
        raise comum.Erro(str(e))
    resultados = []
    for iid, lista in lotes:
        if a.previa:
            folha = previa(d, kit, lista)
            resultados.append({"id": iid, "previa": str(folha), "avisos": sum((p.avisos for p in lista), [])})
            if not a.json:
                comum.diz(f"{iid}: prévia em {folha}  (olhe antes de gravar; nada foi tratado ainda)")
        else:
            for plano in lista:
                r = tratar(d, kit, plano)
                resultados.append(r)
                if not a.json:
                    comum.diz(f"{iid} → {r['saida']}\n    {r['largura']}×{r['altura']} · {r['duracao']:.2f} s · {r['fps']} fps · encaixe: {r['encaixe']} · "
                              f"{'tratamento da DA' if r['cor_tratada'] else 'cor original'} · moldura: {r['moldura']}" + (f" · crédito: {r['credito']}" if r["credito"] else ""))
        if not a.json:
            for av in dict.fromkeys(sum((p.avisos for p in lista), [])):
                comum.diz(f"    ! {av}")
    if a.json:
        print(json.dumps(resultados, ensure_ascii=False, indent=1))
    elif not a.previa:
        comum.diz(f"\nCarimbos ao lado de cada peça (.da.json) · registro atualizado: {raiz / registro.ARQUIVO}")
        comum.diz("Quando souber a cena: registro.py marcar-uso <ID> <C03>  (ou sincronizar-uso, a partir do storyboard)")
    return 0


if __name__ == "__main__":
    sys.exit(comum.rodar(main))
