#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""legendar.py — legenda queimada (karaokê, palavra única ou bloco) no estilo da direção de arte do projeto.

    python3 legendar.py --video cortes/_K01_base.mp4 --palavras transcricao/final.palavras.json --saida cortes/K01.mp4 \\
            --formato vertical --plataforma uniao --inicio 62.4 --fim 91.0
    python3 legendar.py --video … --palavras … --saida legendas/K01.mov --so-overlay      # faixa com alfa para o editor
    python3 legendar.py --video … --palavras … --previa                                    # só a folha de contato

Em Python (é o que as outras skills importam):

    import legendar
    r = legendar.legendar(video, palavras, saida, formato="vertical", plataforma="uniao", inicio=62.4, fim=91.0)
    r["saida"], r["srt"], r["cues_json"], r["avisos"], r["conferencia"]

Nada aqui escolhe cor, fonte, tamanho, posição ou tempo de animação: tudo vem do bloco `legenda` (e de
`movimento.duracoes`) do da/da.json, pelo kit. Os estados são desenhados por texto.py (em paridade com o motor) e
queimados numa única passada de ffmpeg por video.compor_cues.
"""
from __future__ import annotations

import math
import shutil
import sys
import time
from fractions import Fraction
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum  # noqa: E402
import cues as modulo_cues  # noqa: E402
from comum import Erro, br, relogio  # noqa: E402

AMPLITUDE_DO_POP = 0.08        # a palavra falada nasce 8 % maior e assenta: o mesmo número de motor/cenas/_legenda.js
CONTRASTE_RUIM = 3.0           # WCAG 2.2, critério 1.4.3: mínimo para texto grande (a legenda queimada é texto grande)
CONTRASTE_BOM = 4.5            # WCAG 2.2, critério 1.4.3: mínimo geral; abaixo disto a legenda merece atenção
CONTORNO_QUE_SEGURA = 0.05     # contorno a partir desta fração do tamanho isola a letra do fundo
FUNDO_CARREGADO = 0.45         # diferença de luminância (p90 − p10) atrás da legenda que denuncia texto ou gráfico do próprio vídeo
AMOSTRAS_DE_CONTRASTE = 16
ENQUADRAMENTOS = ("recorte", "encaixe")
CODECS_DE_OVERLAY = {"vp9alfa": ".webm", "prores4444": ".mov"}


# ───────────────────────────────────────────────────────── estados da cue ──
def linhas_permitidas(d) -> int:
    """Teto de linhas de uma cue: `legenda.max_linhas` da DA (no estilo `palavra`, uma)."""
    return 1 if d["legenda"]["estilo"] == "palavra" else int(d["legenda"]["max_linhas"])


def _estilos_do_estado(d, L: int, A: int, texto, marcadas: list[bool], i: int | None) -> list:
    """Um Estilo por palavra para o estado em que a palavra `i` é a falada (None = bloco): a receita do kit
    (texto.estados_da_legenda) mais uma regra — palavra de `destaque` do glossário fica em cor_destaque depois de
    dita (karaokê) ou sempre (bloco)."""
    normal = texto.Estilo.legenda(d, L, A)
    falando = texto.Estilo.legenda(d, L, A, destaque=True)
    ja_dita = texto.Estilo.legenda(d, L, A, falada=True)
    if i is None:
        return [falando if m else normal for m in marcadas]
    return [falando if k == i or (k < i and marcadas[k]) else ja_dita if k < i else normal for k in range(len(marcadas))]


def _estados_da_cue(cue: dict, d, L: int, A: int, plataforma, texto) -> list[tuple]:
    """[(imagem recortada, info)] de uma cue, na ordem das palavras, conforme legenda.estilo — por
    texto.estados_da_legenda (kit). Só as cues com palavra de `destaque` do glossário montam os estilos aqui
    (_estilos_do_estado). As linhas da cue valem enquanto respeitam `legenda.max_linhas`: acima disso a legenda sairia
    da faixa que a DA reserva para ela, e quem quebra é o kit."""
    palavras = [w["w"] for w in cue["palavras"]]
    estilo = d["legenda"]["estilo"]
    linhas = [len(l) for l in cue["linhas"]]
    opcoes = {"linhas": linhas} if estilo != "palavra" and len(palavras) > 1 and len(linhas) <= linhas_permitidas(d) else {}
    marcadas = [bool(w.get("destaque")) for w in cue["palavras"]]

    def montar(**op):
        if not any(marcadas) or estilo == "palavra":
            return texto.estados_da_legenda(palavras, d, L, A, plataforma=plataforma, **op)
        if estilo == "bloco":
            img, info = texto.compor_legenda(palavras, _estilos_do_estado(d, L, A, texto, marcadas, None), d, L, A,
                                             plataforma=plataforma, recortar=True, **op)
            return [(img, {**info, "indice": None})]
        saida = []
        for i in range(len(palavras)):
            img, info = texto.compor_legenda(palavras, _estilos_do_estado(d, L, A, texto, marcadas, i), d, L, A,
                                             plataforma=plataforma, recortar=True, **op)
            saida.append((img, {**info, "indice": i}))
        return saida

    estados = montar(**opcoes)
    if opcoes and estados[0][1]["encolheu"]:           # as linhas da cue não cabem: deixa o kit quebrar do jeito dele
        livres = montar()
        if livres[0][1]["tamanho"] > estados[0][1]["tamanho"] + 1e-6:
            estados = livres
    return estados


def _com_alfa(img, p: float):
    """A imagem com a opacidade multiplicada por p (fade)."""
    if p >= 0.999:
        return img
    copia = img.copy()
    copia.putalpha(img.getchannel("A").point(lambda v: int(v * max(0.0, p) + 0.5)))
    return copia


def _ampliar(img, e: float):
    """A imagem ampliada por e em torno do centro (alfa pré-multiplicado, para a borda não escurecer)."""
    from PIL import Image
    nw, nh = max(1, int(round(img.width * e))), max(1, int(round(img.height * e)))
    return img.convert("RGBa").resize((nw, nh), Image.LANCZOS).convert("RGBA")


def _folga_de_pop(caixa, zona, e: float) -> float:
    """O maior fator ≤ e com que a caixa (x0, y0, x1, y1), ampliada pelo centro, continua dentro da zona segura."""
    w, h = caixa[2] - caixa[0], caixa[3] - caixa[1]
    if w <= 0 or h <= 0:
        return 1.0
    sobra_x = min(caixa[0] - zona["x0"], zona["x1"] - caixa[2])
    sobra_y = min(caixa[1] - zona["y0"], zona["y1"] - caixa[3])
    return max(1.0, min(e, 1 + 2 * max(0.0, sobra_x) / w, 1 + 2 * max(0.0, sobra_y) / h))


def _pop_inteiro(img, info: dict, e: float):
    """Pop dos estilos `palavra` e `bloco`: a peça inteira cresce pelo centro (é o scale() do motor)."""
    e = _folga_de_pop(info["caixa"], info["zona"], e)
    if e <= 1.004:
        return img, info["x"], info["y"], 1.0
    maior = _ampliar(img, e)
    return maior, info["x"] - (maior.width - img.width) // 2, info["y"] - (maior.height - img.height) // 2, e


def _letras_das_outras(info: dict, i: int, estilos: list, texto):
    """Só o PREENCHIMENTO das letras das outras palavras do estado (sem contorno, sombra nem caixa), no mesmo desenho
    do kit, e o deslocamento (dx, dy) para colá-lo sobre a imagem do estado. None quando a cue tem uma palavra só.
    Serve ao pop: no desenho do kit todas as letras ficam por cima de todos os contornos; a palavra ampliada entra
    depois e, sem isto, o contorno dela passaria por cima do acento da linha de baixo e da letra da vizinha."""
    n = len(info["palavras"])
    if n < 2:
        return None
    k = info["tamanho"] / info["tamanho_pedido"]
    nus = [texto.escalar_estilo(est.com(contorno=None, sombra=None, fundo=None), k) for est in estilos]
    nus[i] = nus[i].com(cor=tuple(nus[i].cor[:3]) + (0,))                       # a própria palavra não entra
    camada, inf = texto.compor_bloco([q["texto"] for q in info["palavras"]], nus, linhas=info["indices"], alinhamento="centro")
    ref = 0 if i != 0 else 1                                                    # uma palavra visível serve de referência
    dx = int(round(info["palavras"][ref]["x0"] - info["x"] - inf["palavras"][ref]["x0"]))
    dy = int(round(info["palavras"][ref]["y0"] - info["y"] - inf["palavras"][ref]["y0"]))
    return camada, dx, dy


def _pop_no_lugar(img, info: dict, i: int, e: float, estilos: list, texto):
    """Pop do karaokê: só a palavra i cresce, no lugar, e as vizinhas não se mexem (como no motor).

    A palavra assentada é tirada do bloco já desenhado pelo kit pela SILHUETA dela (a mesma palavra desenhada sozinha,
    com contorno e sombra, serve de máscara — nada das vizinhas é apagado fora dela, nem sobra risco da palavra antiga);
    a palavra ampliada entra por cima e as letras das outras voltam para cima dela (_letras_das_outras), na ordem de
    camadas do kit. A ampliação é limitada duas vezes: pela zona segura e pelo vão — a palavra nunca cresce mais que
    meio vão para cada lado, senão cola na vizinha. `estilos` = um Estilo por palavra deste estado.
    Devolve (imagem, x, y, ampliação usada, a zona segura reduziu o pop?)."""
    import numpy as np
    from PIL import Image, ImageFilter
    est_palavra = estilos[i]
    ox, oy = info["x"], info["y"]
    p = info["palavras"][i]
    x0, x1, y0, y1 = p["x0"] - ox, p["x1"] - ox, p["y0"] - oy, p["y1"] - oy
    cont = float(info.get("contorno_px") or 0)
    pedido = e
    e = _folga_de_pop((p["x0"] - cont, p["y0"] - cont, p["x1"] + cont, p["y1"] + cont), info["zona"], e)
    pela_zona = e < pedido - 0.004
    da_linha = sorted((q["x0"] - ox, q["x1"] - ox) for q in info["palavras"] if q["linha"] == p["linha"])
    antes = [b for a, b in da_linha if b <= x0 + 0.01]
    depois = [a for a, b in da_linha if a >= x1 - 0.01]
    vaos = ([x0 - antes[-1]] if antes else []) + ([depois[0] - x1] if depois else [])
    if vaos:
        e = min(e, 1 + max(0.0, min(vaos)) / max(1.0, x1 - x0))
    if e <= 1.004:
        return img, ox, oy, 1.0, pela_zona
    tem_fundo = est_palavra.fundo is not None
    k = info["tamanho"] / info["tamanho_pedido"]
    sem_fundo = est_palavra.com(fundo=None) if tem_fundo else est_palavra

    def sozinha(fator: float):
        """A palavra desenhada sozinha (contorno e sombra dela) e onde colá-la para o centro cair no centro da caixa dela."""
        desenho, inf = texto.compor_bloco([p["texto"]], [texto.escalar_estilo(sem_fundo, k * fator)], alinhamento="centro")
        ct = inf["caixa_texto"]
        return desenho, int(round((x0 + x1) / 2 - (ct[0] + ct[2]) / 2)), int(round((y0 + y1) / 2 - (ct[1] + ct[3]) / 2))

    assentada, ax, ay = sozinha(1.0)
    palavra, px, py = sozinha(e)
    # máscara = onde a tinta da palavra assentada domina (a cauda fraca de uma sombra desfocada fica), com 1 px de folga
    silhueta = Image.new("L", img.size, 0)
    silhueta.paste(assentada.getchannel("A").point(lambda v: 255 if v >= 96 else 0), (ax, ay))
    mascara = np.asarray(silhueta.filter(ImageFilter.MaxFilter(3))) > 0
    limpa = np.array(img)                                  # cópia: o estado assentado continua intacto
    if tem_fundo:                                          # dentro da caixa a palavra dá lugar à cor da caixa
        cor_da_caixa = np.array(est_palavra.fundo["cor"], dtype=np.uint8)
        limpa[mascara & (limpa[..., 3] >= max(1, int(cor_da_caixa[3]) - 2))] = cor_da_caixa
    else:
        limpa[mascara] = 0
    mx0, my0 = min(0, px), min(0, py)
    mx1, my1 = max(img.width, px + palavra.width), max(img.height, py + palavra.height)
    tela = Image.new("RGBA", (mx1 - mx0, my1 - my0), (0, 0, 0, 0))
    tela.alpha_composite(Image.fromarray(limpa), (-mx0, -my0))
    tela.alpha_composite(palavra, (px - mx0, py - my0))
    outras = _letras_das_outras(info, i, estilos, texto)
    if outras is not None:                                 # só dentro da área que a palavra ampliada cobriu
        camada, dx, dy = outras
        cx0, cy0 = max(px, dx), max(py, dy)
        cx1, cy1 = min(px + palavra.width, dx + camada.width), min(py + palavra.height, dy + camada.height)
        if cx1 > cx0 and cy1 > cy0:
            tela.alpha_composite(camada.crop((cx0 - dx, cy0 - dy, cx1 - dx, cy1 - dy)), (cx0 - mx0, cy0 - my0))
    return tela, ox + mx0, oy + my0, e, pela_zona


class _Estados:
    """Linha do tempo da legenda em QUADROS: para cada cue, qual estado (palavra acesa), com que opacidade (fade) e
    com que ampliação (pop) em cada quadro. Cada estado diferente vira UM PNG pequeno em legendas/_png/<nome>/ (a lista
    que video.compor_cues recebe aponta para os arquivos: um vídeo longo não fica inteiro na memória)."""

    def __init__(self, doc: dict, d, L: int, A: int, fps: Fraction, pasta: Path):
        _, self.texto, _, _ = comum.kit()
        self.doc, self.d, self.L, self.A, self.fps, self.pasta = doc, d, L, A, fps, pasta
        leg = d["legenda"]
        self.estilo, self.animacao = leg["estilo"], leg.get("animacao", "nenhuma")
        self.plataforma = doc.get("plataforma")
        self.n_fade = max(0, int(round(d.dur("curta") * float(fps)))) if self.animacao == "fade" else 0
        self.n_pop = max(1, int(round(d.dur("micro") * float(fps)))) if self.animacao == "pop" else 0
        self.curva = d.facilitar("entrada")
        self.entradas: list[dict] = []
        self.rel = {"cues": 0, "estados": 0, "pngs": 0, "fora_da_zona": [], "encolhidas": [], "menor_tamanho_fracao": 1.0,
                    "sem_quadro": 0, "pop_reduzido": 0, "caixas": {}, "amostras": {}, "linhas_refeitas": [], "fora_da_faixa": []}
        self.faixa = d.faixa_legenda(f"{L}x{A}", self.plataforma)

    def _tempo(self, quadro: int) -> float:
        return float(Fraction(quadro) / self.fps)

    def montar(self) -> list[dict]:
        self.pasta.mkdir(parents=True, exist_ok=True)
        fps = float(self.fps)
        fim_anterior = 0
        for cue in self.doc["cues"]:
            F0 = max(fim_anterior, int(round(cue["t0"] * fps)))
            F1 = max(F0 + 1, int(round(cue["t1"] * fps)))
            fim_anterior = F1
            estados = _estados_da_cue(cue, self.d, self.L, self.A, self.plataforma, self.texto)
            self._conferir(cue, estados)
            if len(estados) == 1:                              # bloco: um estado para a cue inteira
                inicios = [F0]
            else:
                inicios, anterior = [], F0 - 1
                for n, w in enumerate(cue["palavras"]):
                    q = F0 if n == 0 else min(max(int(round(w["a"] * fps)), anterior + 1), F1)
                    inicios.append(q)
                    anterior = q
            fins = inicios[1:] + [F1]
            self.rel["sem_quadro"] += sum(1 for a, b in zip(inicios, fins) if b <= a)
            # um quadro de cada palavra para a prévia e para a conferência de contraste (o meio da palavra do meio)
            meio = len(estados) // 2
            self.rel["amostras"][cue["id"]] = {"t": self._tempo((inicios[meio] + max(inicios[meio] + 1, fins[meio])) // 2), "estado": meio,
                                               "caixa": estados[meio][1]["caixa"], "imagem": estados[meio][0],
                                               "x": estados[meio][1]["x"], "y": estados[meio][1]["y"]}
            chave_anterior, inicio_run = None, F0
            cache: dict = {}
            for q in range(F0, F1 + 1):
                chave = None
                if q < F1:
                    i = max(k for k, a in enumerate(inicios) if a <= q)
                    alfa, amp = 1.0, 1.0
                    if self.n_fade:                            # fade: a cue entra (karaokê, bloco) ou cada palavra entra (palavra)
                        base = inicios[i] if self.estilo == "palavra" else F0
                        dur = fins[i] - inicios[i] if self.estilo == "palavra" else F1 - F0
                        nf = min(self.n_fade, dur // 2)
                        if q - base < nf:
                            alfa = min(1.0, max(0.05, self.curva((q - base + 1) / (nf + 1))))
                    if self.n_pop:                             # pop: a palavra falada (ou o bloco, na entrada) nasce maior e assenta
                        base = F0 if self.estilo == "bloco" else inicios[i]
                        dur = (F1 - F0) if self.estilo == "bloco" else fins[i] - inicios[i]
                        npop = min(self.n_pop, max(1, dur // 2))
                        if q - base < npop:
                            assentou = min(1.0, max(0.0, self.curva((q - base) / npop)))
                            amp = 1 + AMPLITUDE_DO_POP * (1 - assentou)
                            if amp < 1.004:                    # menos de meio por cento: já assentou (não vale um estado)
                                amp = 1.0
                    chave = (i, round(alfa, 3), round(amp, 4))
                if chave != chave_anterior:
                    if chave_anterior is not None and q > inicio_run:
                        self._emitir(cue, estados, chave_anterior, inicio_run, q, cache)
                    chave_anterior, inicio_run = chave, q
            self.rel["cues"] += 1
        return self.entradas

    def _conferir(self, cue: dict, estados: list) -> None:
        info = estados[0][1]
        self.rel["menor_tamanho_fracao"] = min(self.rel["menor_tamanho_fracao"], info["tamanho_fracao"])
        self.rel["caixas"][cue["id"]] = info["caixa"]
        if any(not inf["dentro_da_zona"] or not inf["coube"] for _, inf in estados):
            self.rel["fora_da_zona"].append(cue["id"])
        if len(cue["linhas"]) > linhas_permitidas(self.d):
            self.rel["linhas_refeitas"].append(cue["id"])
        # a faixa que a DA reserva para a legenda (e de que GC, título e gráficos desviam): nenhum estado sai dela
        f = self.faixa
        if any(inf["caixa"][1] < f["y0"] - 1.5 or inf["caixa"][3] > f["y1"] + 1.5 for _, inf in estados):
            self.rel["fora_da_faixa"].append(cue["id"])
        if info["encolheu"]:
            self.rel["encolhidas"].append({"cue": cue["id"], "tamanho_fracao": round(info["tamanho_fracao"], 4),
                                           "texto": " ".join(w["w"] for w in cue["palavras"])})

    def _emitir(self, cue: dict, estados: list, chave: tuple, q0: int, q1: int, cache: dict) -> None:
        if chave not in cache:
            i, alfa, amp = chave
            img, info = estados[i]
            x, y = info["x"], info["y"]
            if amp > 1.0001:
                if self.estilo == "karaoke":
                    marcadas = [bool(w.get("destaque")) for w in cue["palavras"]]
                    ests = _estilos_do_estado(self.d, self.L, self.A, self.texto, marcadas, info["indice"])
                    img, x, y, usado, pela_zona = _pop_no_lugar(img, info, info["indice"], amp, ests, self.texto)
                else:
                    img, x, y, usado = _pop_inteiro(img, info, amp)
                    pela_zona = usado < amp - 0.004
                if pela_zona:
                    self.rel["pop_reduzido"] += 1
            img = _com_alfa(img, alfa)
            arq = self.pasta / f"c{cue['id']:04d}_{len(cache):03d}.png"
            img.save(arq, "PNG", compress_level=1)
            cache[chave] = (arq, x, y)
            self.rel["pngs"] += 1
        arq, x, y = cache[chave]
        self.entradas.append({"imagem": str(arq), "t0": self._tempo(q0), "t1": self._tempo(q1), "x": int(x), "y": int(y),
                              "cue": cue["id"], "indice": estados[chave[0]][1]["indice"], "alfa": chave[1], "ampliacao": chave[2],
                              "q0": q0, "q1": q1})
        self.rel["estados"] += 1


# ───────────────────────────────────────────────────── base e amostragem ──
def cadeia_da_base(d, info: dict, L: int, A: int, enquadramento: str = "recorte", foco=None, tratamento: bool = False) -> str | None:
    """Cadeia ffmpeg que leva a base ao quadro de saída: recorte (âncora `tratamento.recorte.ancora` da DA, ou `foco`)
    ou encaixe (`tratamento.encaixe` da DA) quando a proporção muda, e o tratamento de cor da DA quando pedido."""
    _, _, video, _ = comum.kit()
    partes = []
    origem = (info["largura"], info["altura"])
    if origem != (L, A):
        if enquadramento == "encaixe":
            partes.append(video.filtro_encaixe(origem, (L, A), d=d)["filtro"])
        else:
            partes.append(video.filtro_recorte(origem, (L, A), d["tratamento"]["recorte"]["ancora"], foco)["filtro"])
    if tratamento:
        t = video.filtro_tratamento(d, f"{L}x{A}")
        if t and t != "null":
            partes.append(t)
    return ",".join(partes) or None


def _quadros_da_base(video_arq: Path, tempos: list[float], cadeia: str | None, pasta: Path, largura: int | None, prefixo: str) -> list[Path]:
    """Um PNG da base (já no enquadramento de saída) em cada tempo; intermediários com `_` no nome. Cada quadro é um
    ffmpeg curto que salta direto para o instante (não decodifica o vídeo inteiro); a trava é pedida UMA vez para
    todos — pedida quadro a quadro, com a fila disputada, 16 amostras eram 16 esperas."""
    _, _, video, trava = comum.kit()
    saida = []
    with trava.Trava(rotulo="video-legendas: quadros de conferência"):
        for n, t in enumerate(tempos):
            arq = pasta / f"_{prefixo}_{n:03d}.png"
            video.extrair_quadro(video_arq, t, arq, largura=largura, tratamento=cadeia)
            saida.append(arq)
    return saida


def _luminancia(arr):
    """Luminância relativa (WCAG 2.2) de um array RGB 0–255."""
    import numpy as np
    c = arr.astype(np.float64) / 255.0
    lin = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * lin[..., 0] + 0.7152 * lin[..., 1] + 0.0722 * lin[..., 2]


def _razao(l1: float, l2: float) -> float:
    return (max(l1, l2) + 0.05) / (min(l1, l2) + 0.05)


def conferir_contraste(d, amostras: list[dict], L: int, A: int, estilo: str) -> dict:
    """Contraste da legenda contra o vídeo REAL atrás dela. `amostras` = [{'t', 'cue', 'quadro' (PIL RGB do quadro de
    saída, em qualquer escala), 'caixa' (x0, y0, x1, y1 em px do quadro L×A)}]. Para cada uma mede a luminância do
    fundo na caixa (p10 e p90: o texto passa por cima do claro e do escuro), já com a caixa `legenda.fundo` por cima
    se a DA tiver, e calcula a razão WCAG de cada cor da legenda. Contorno grosso isola a letra: vale o maior entre
    letra×fundo e letra×contorno. Devolve o resumo com os trechos ruins e a sugestão de TOKEN a ajustar."""
    import numpy as np
    da, _, _, _ = comum.kit()
    leg = d["legenda"]
    papeis = {"palavra": ["cor_destaque"], "bloco": ["cor"], "karaoke": ["cor", "cor_destaque"] + (["cor_falada"] if leg.get("cor_falada") else [])}[estilo]
    lum_cor = {p: da.luminancia(d.rgb(leg[p])) for p in papeis}
    fundo, contorno = leg.get("fundo"), leg.get("contorno")
    segura = bool(contorno) and float(contorno.get("espessura", 0)) >= CONTORNO_QUE_SEGURA
    lum_contorno = da.luminancia(d.rgb(contorno["cor"])) if contorno else None
    itens = []
    for am in amostras:
        q = am["quadro"].convert("RGB")
        sx, sy = q.width / L, q.height / A
        x0, y0, x1, y1 = am["caixa"]
        rec = q.crop((max(0, int(x0 * sx)), max(0, int(y0 * sy)), min(q.width, int(math.ceil(x1 * sx))), min(q.height, int(math.ceil(y1 * sy)))))
        if rec.width < 1 or rec.height < 1:
            continue
        arr = np.asarray(rec, dtype=np.float64)
        bruto = _luminancia(arr)
        if fundo:
            a = float(fundo.get("alfa", 0.85))
            arr = a * np.array(d.rgb(fundo["cor"]), dtype=np.float64) + (1 - a) * arr
        lum = _luminancia(arr)
        p10, p50, p90 = (float(np.percentile(lum, k)) for k in (10, 50, 90))
        razoes = {}
        for p in papeis:
            r = min(_razao(lum_cor[p], p10), _razao(lum_cor[p], p90))
            if segura:
                r = max(r, _razao(lum_cor[p], lum_contorno))
            razoes[p] = round(r, 2)
        pior = min(razoes.values())
        espalhamento = float(np.percentile(bruto, 90) - np.percentile(bruto, 10))
        itens.append({"t": round(am["t"], 3), "cue": am["cue"], "fundo_video": round(float(np.median(bruto)), 3), "detalhe": round(espalhamento, 3),
                      "fundo_efetivo": [round(p10, 3), round(p50, 3), round(p90, 3)], "contraste": razoes, "pior": pior,
                      "nivel": "ruim" if pior < CONTRASTE_RUIM else "atencao" if pior < CONTRASTE_BOM else "ok"})
    if not itens:
        return {"ok": True, "amostras": 0, "pior": None, "ruins": 0, "atencao": 0, "trechos": [], "carregado": [], "sugestoes": [], "itens": []}
    ruins = [i for i in itens if i["nivel"] == "ruim"]
    resumo = {"ok": not ruins, "amostras": len(itens), "pior": min(i["pior"] for i in itens), "ruins": len(ruins),
              "atencao": sum(1 for i in itens if i["nivel"] == "atencao"), "limites": {"ruim": CONTRASTE_RUIM, "bom": CONTRASTE_BOM},
              "trechos": [], "carregado": [i["t"] for i in itens if i["detalhe"] >= FUNDO_CARREGADO], "sugestoes": [], "itens": itens}
    # trechos: amostras ruins vizinhas viram um intervalo
    for n, it in enumerate(itens):
        if it["nivel"] != "ruim":
            continue
        if resumo["trechos"] and n > 0 and itens[n - 1]["nivel"] == "ruim":
            resumo["trechos"][-1]["t1"] = it["t"]
            resumo["trechos"][-1]["pior"] = min(resumo["trechos"][-1]["pior"], it["pior"])
        else:
            resumo["trechos"].append({"t0": it["t"], "t1": it["t"], "pior": it["pior"], "fundo_video": it["fundo_video"]})
    fracos = [i for i in itens if i["nivel"] != "ok"]
    if fracos:
        resumo["sugestoes"] = _sugestoes_de_token(d, fracos, papeis, lum_cor, segura, lum_contorno)
    return resumo


def _sugestoes_de_token(d, fracos: list[dict], papeis: list[str], lum_cor: dict, segura: bool, lum_contorno) -> list[str]:
    """O que mudar NA DA (token, nunca cor literal) para a legenda ler nesses trechos."""
    da, _, _, _ = comum.kit()
    leg = d["legenda"]
    fundo, contorno = leg.get("fundo"), leg.get("contorno")
    claro = sum(i["fundo_video"] for i in fracos) / len(fracos) > 0.4
    sug = []
    piores = {p: min(i["contraste"][p] for i in fracos) for p in papeis}
    so_um_papel = [p for p in papeis if piores[p] < CONTRASTE_BOM] if max(piores.values()) >= CONTRASTE_BOM else []
    if so_um_papel:                                        # a cor base lê, uma das outras não: é o token dessa cor
        alvo = fracos[0]["fundo_efetivo"]
        melhores = []
        for token in d["cor"]["paleta"]:
            if token in (leg.get("cor"), leg.get("cor_destaque"), leg.get("cor_falada"), "fundo", "superficie"):
                continue
            r = min(_razao(da.luminancia(d.rgb(token)), alvo[0]), _razao(da.luminancia(d.rgb(token)), alvo[2]))
            if r >= CONTRASTE_BOM:
                melhores.append((r, token))
        nomes = ", ".join(f"{t} ({br(r, 1)}:1)" for r, t in sorted(melhores, reverse=True)[:3])
        for p in so_um_papel:
            sug.append(f"legenda.{p} (token `{leg[p]}`) lê a {br(piores[p], 1)}:1 nesses trechos; "
                       + (f"tokens da paleta que leem melhor ali: {nomes}" if nomes else "nenhum token da paleta chega a 4,5:1 ali — a saída é caixa ou contorno"))
    if fundo:
        a = float(fundo.get("alfa", 0.85))
        if a < 0.8:
            sug.append(f"legenda.fundo.alfa está em {br(a)}: suba para 0,8 ou mais (a caixa deixa o vídeo {'claro' if claro else 'escuro'} vazar por trás da letra)")
        elif not so_um_papel:
            sug.append(f"legenda.fundo.cor (token `{fundo['cor']}`) tem pouco contraste com legenda.cor (token `{leg['cor']}`): troque um dos dois tokens")
    elif contorno:
        if not segura:
            sug.append(f"legenda.contorno.espessura está em {br(float(contorno.get('espessura', 0)))}: com 0,08 a 0,12 o contorno isola a letra de qualquer fundo")
        elif lum_contorno is not None and _razao(lum_cor[papeis[0]], lum_contorno) < CONTRASTE_BOM:
            sug.append(f"legenda.contorno.cor (token `{contorno['cor']}`) e legenda.{papeis[0]} (token `{leg[papeis[0]]}`) têm menos de 4,5:1 entre si: "
                       f"use no contorno um token {'escuro' if lum_cor[papeis[0]] > 0.4 else 'claro'} (fundo, neutro-1, neutro-2)")
    else:
        sug.append("a legenda desta DA não tem contorno nem caixa: ligue legenda.contorno (cor: token escuro como `fundo`, espessura 0,08–0,12) "
                   "ou legenda.fundo (cor: `fundo`, alfa ≥ 0,8)" + (" — o fundo desses trechos é claro" if claro else ""))
    if not sug:
        sug.append("mude legenda.posicao.<formato>.y para uma faixa mais calma do quadro, ou ligue legenda.fundo")
    sug.append(f"toda mudança é na DA: {comum.DA_CLI} revisar → editar da/da.json → validar → aprovar; depois rode o legendar de novo")
    return sug


# ───────────────────────────────────────────────────────────────── prévia ──
def _folha_de_previa(d, doc: dict, rel: dict, video_arq: Path, inicio: float, cadeia: str | None, L: int, A: int, pasta: Path,
                     saida: Path, quantas: int) -> tuple[Path, list[dict]]:
    """Folha de contato: um quadro por cue amostrada, com a legenda no lugar e a zona segura desenhada. Devolve
    (arquivo, amostras para a conferência de contraste)."""
    from PIL import Image, ImageDraw
    _, _, video, _ = comum.kit()
    ids = [c["id"] for c in doc["cues"]]
    quantas = max(1, min(quantas, len(ids)))
    escolhidas = [ids[int(round(k * (len(ids) - 1) / max(1, quantas - 1)))] for k in range(quantas)] if quantas > 1 else [ids[len(ids) // 2]]
    escolhidas = list(dict.fromkeys(escolhidas))
    por_id = {c["id"]: c for c in doc["cues"]}
    tempos = [rel["amostras"][i]["t"] for i in escolhidas]
    quadros = _quadros_da_base(video_arq, [inicio + t for t in tempos], cadeia, pasta, None, "previa")
    zona = d.margens("vertical" if A > L else "horizontal", doc.get("plataforma"), largura=L, altura=A)
    traco = max(2, min(L, A) // 270)
    prontos, legendas, amostras = [], [], []
    for cid, arq, t in zip(escolhidas, quadros, tempos):
        am = rel["amostras"][cid]
        base = Image.open(arq).convert("RGBA")
        if base.size != (L, A):
            base = base.resize((L, A), Image.LANCZOS)
        amostras.append({"t": t, "cue": cid, "quadro": base.convert("RGB"), "caixa": am["caixa"]})
        base.alpha_composite(am["imagem"], (max(0, am["x"]), max(0, am["y"])), (max(0, -am["x"]), max(0, -am["y"])))
        ImageDraw.Draw(base).rectangle([zona["x0"], zona["y0"], zona["x1"] - 1, zona["y1"] - 1], outline=d.rgba("primaria", 0.9), width=traco)
        base.convert("RGB").save(arq)
        prontos.append(arq)
        legendas.append(f"cue {cid} · {relogio(t)} · " + " ".join(w["w"] for w in por_id[cid]["palavras"]))
    vertical = A > L
    video.folha_de_contato(prontos, legendas, saida, colunas=4 if vertical else 2, largura_celula=360 if vertical else 640, da_obj=d,
                           titulo=f"Prévia da legenda — {doc['estilo']} · zona {doc['plataforma']} · {L}×{A}")
    return saida, amostras


def faixa_reservada(d, L: int, A: int) -> bool:
    """As peças do kit (GC, crédito, título, gráficos) desviam da faixa da legenda num quadro L×A? É `legenda.reservar_em`
    da DA: por padrão sim no vertical e no quadrado e NÃO no horizontal. Kit antigo, sem a pergunta, responde sim."""
    perguntar = getattr(d, "legenda_reservada", None)
    return True if perguntar is None else bool(perguntar(f"{L}x{A}"))


def _acertar_formato_do_carimbo(d, saida: Path, formato: str, insumos: list) -> None:
    """Contorno de um defeito do kit (1.4.0): video.nome_do_formato dá a um vídeo 1280×720 o nome `thumbnail`, porque a
    thumbnail da DA tem essas dimensões. Se o carimbo saiu com outro nome de formato, é regravado com o certo — mesmos
    parâmetros, mesmos insumos. É o ÚNICO ponto que mexe em carimbo aqui."""
    da, _, _, _ = comum.kit()
    carimbo = da.ler_carimbo(saida)
    if carimbo and carimbo.get("formato") != formato:
        d.carimbar(saida, comum.FERRAMENTA, formato, carimbo.get("parametros"), insumos=insumos)


# ─────────────────────────────────────────────────────────────── legendar ──
def legendar(video, palavras=None, saida=None, formato=None, plataforma=None, inicio=None, fim=None, **opcoes) -> dict:
    """Queima a legenda em `video` e grava `saida` (mp4), ou só a faixa com alfa (so_overlay=True: .webm VP9 e/ou
    .mov ProRes 4444), ou só a folha de contato (previa=True|N).

    video, palavras, saida : caminhos. `palavras` = JSON [{a, b, w, p}] da video-transcricao (tempos do vídeo inteiro).
    formato     : quadro de saída — formato da DA ('vertical', 'horizontal') ou 'LxA'; None = o do próprio vídeo.
    plataforma  : zona segura — None/'uniao' (padrão do vertical), 'reels', 'tiktok', 'shorts'.
    inicio, fim : trecho do vídeo (s); as cues, o .srt e o .vtt saem com os tempos rebaseados para o trecho.
    opcoes      : so_overlay, codec ('vp9alfa' | 'prores4444' | 'ambos'), previa (bool | nº de quadros), previa_saida,
                  cues (arquivo .cues.json já corrigido: não segmenta de novo), nome, glossario, projeto, escala,
                  enquadramento ('recorte' | 'encaixe'), foco (x, y em frações), tratamento (bool: aplica a cor da DA a
                  material bruto), pontuacao, limiar_confianca, refazer_cues, manter_png, sem_contraste, amostras, crf,
                  srt_ao_lado (padrão True: copia o .srt para junto da saída quando ela não fica em legendas/).
    Devolve um dict: saida, saidas, carimbo, cues_json, srt, vtt, srt_ao_lado, previa, nome, formato, largura, altura,
    plataforma, estilo, animacao, duracao, cues, palavras, estados, avisos (textos), conferencia {zona, contraste}, tempo_s.
    Levanta comum.Erro / da.DAErro (da.SemDA quando o projeto não tem direção de arte)."""
    t_inicio = time.time()
    da, texto, vid, trava = comum.kit()
    desconhecidas = set(opcoes) - {"so_overlay", "codec", "previa", "previa_saida", "cues", "nome", "glossario", "projeto", "escala",
                                   "enquadramento", "foco", "tratamento", "pontuacao", "limiar_confianca", "refazer_cues", "manter_png",
                                   "sem_contraste", "amostras", "crf", "srt_ao_lado", "silencioso"}
    if desconhecidas:
        raise Erro(f"legendar(): opção desconhecida {', '.join(sorted(desconhecidas))}.", "Veja a lista na docstring de legendar.legendar.", 64)
    so_overlay, previa = bool(opcoes.get("so_overlay")), opcoes.get("previa")
    if previa is not None and not isinstance(previa, bool):
        if int(previa) < 1:
            raise Erro(f"--previa {previa}: a folha de contato precisa de pelo menos 1 quadro.", "Use --previa (8 quadros) ou --previa N com N ≥ 1.", 64)
        previa = int(previa)
    previa = previa or None
    enquadramento = opcoes.get("enquadramento") or "recorte"
    if enquadramento not in ENQUADRAMENTOS:
        raise Erro(f"enquadramento {enquadramento!r} inválido; use {' ou '.join(ENQUADRAMENTOS)}.", codigo=64)
    if not video:
        raise Erro("faltou o vídeo (--video).", codigo=64)
    video_arq = comum.absoluto(video)                      # sem seguir link simbólico: o nome no projeto é o que vale
    if not video_arq.is_file():
        raise Erro(f"vídeo não encontrado: {video_arq}", "Confira o caminho (use aspas se tiver espaço).")
    if not saida and not previa:
        raise Erro("faltou a saída (--saida): o vídeo legendado, a faixa com alfa, ou use --previa para só ver a folha de contato.", codigo=64)
    if not palavras and not opcoes.get("cues"):
        raise Erro("faltou o arquivo de palavras (--palavras) — ou um arquivo de cues já corrigido (--cues).",
                   "As palavras cronometradas vêm da skill video-transcricao (transcricao/<nome>.palavras.json).", 64)
    saida_arq = comum.absoluto(saida) if saida else None
    d = comum.carregar_da(opcoes.get("projeto"), pistas=[saida_arq, video_arq])
    info = vid.sondar(video_arq)
    if not info.get("largura"):
        raise Erro(f"{video_arq.name} não tem trilha de vídeo.", "Passe o vídeo que vai receber a legenda (áudio sozinho é com a skill video-animacao-audio).")
    fps = info["fps"] or vid.fps_do_formato(d, formato or f"{info['largura']}x{info['altura']}")
    avisos: list[str] = []

    # 1. saída: extensão coerente com o modo
    codecs = []
    if saida_arq is not None and not previa:
        ext = saida_arq.suffix.lower()
        if so_overlay:
            pedido = opcoes.get("codec")
            if pedido == "ambos":
                codecs = ["vp9alfa", "prores4444"]
            elif pedido in CODECS_DE_OVERLAY:
                codecs = [pedido]
            elif pedido:
                raise Erro(f"codec {pedido!r} inválido para a faixa com alfa; use vp9alfa, prores4444 ou ambos.", codigo=64)
            elif ext in (".webm", ".mov"):
                codecs = ["vp9alfa" if ext == ".webm" else "prores4444"]
            else:
                raise Erro(f"--so-overlay grava faixa com alfa: a saída precisa ser .webm (VP9, para compor por ffmpeg) ou .mov (ProRes 4444, para o editor); veio {ext or 'sem extensão'}.",
                           "Troque a extensão de --saida ou passe --codec ambos para gravar as duas.", 64)
        elif ext not in (".mp4", ".mov", ".m4v"):
            raise Erro(f"a saída queimada é H.264: use .mp4 (veio {ext or 'sem extensão'}).", "Para faixa com alfa, acrescente --so-overlay e use .webm ou .mov.", 64)
        if saida_arq.resolve() == video_arq.resolve():
            raise Erro("a saída é o próprio vídeo de entrada.", "Escolha outro nome: a base nunca é sobrescrita.", 64)

    # 2. cues: arquivo corrigido à mão, ou segmentação nova
    nome = opcoes.get("nome") or (saida_arq.stem if saida_arq is not None else None)
    if opcoes.get("cues"):
        cues_arq = comum.absoluto(opcoes["cues"])
        doc, _ = modulo_cues._abrir_doc(cues_arq)
        L, A = int(doc["largura"]), int(doc["altura"])
        if formato or opcoes.get("escala") is not None:
            _, L2, A2 = modulo_cues.resolver_formato(d, formato, info, opcoes.get("escala"))
            if (L2, A2) != (L, A):
                raise Erro(f"as cues de {cues_arq.name} foram medidas para {L}×{A}, e o quadro pedido é {L2}×{A2}.",
                           "Tire --formato/--escala para usar o tamanho das cues, ou gere as cues de novo para o tamanho novo.", 64)
        jan = doc.get("janela") or {}
        for rotulo, pedido, gravado in (("--inicio", inicio, jan.get("inicio") or 0.0), ("--fim", fim, jan.get("fim"))):
            if pedido is not None and (gravado is None or abs(float(pedido) - float(gravado)) > 0.005):
                raise Erro(f"{rotulo} {br(float(pedido))} não é o trecho das cues de {cues_arq.name} ({br(float(jan.get('inicio') or 0))} s a "
                           f"{br(float(jan['fim'])) + ' s' if jan.get('fim') is not None else 'o fim'}).",
                           "Tire --inicio/--fim (o trecho vem das cues) ou gere as cues de novo para o trecho novo.", 64)
        inicio, fim = float(jan.get("inicio") or 0.0), jan.get("fim")
        arquivos = modulo_cues.caminhos(cues_arq.parent, modulo_cues._nome_do_arquivo(cues_arq))
        nome = modulo_cues._nome_do_arquivo(cues_arq)
        if plataforma and d.margens("vertical" if A > L else "horizontal", plataforma, largura=L, altura=A)["plataforma"] != doc.get("plataforma"):
            raise Erro(f"as cues de {cues_arq.name} foram medidas para a zona `{doc.get('plataforma')}`, e a pedida é `{plataforma}`.",
                       "Tire --plataforma ou gere as cues de novo para a outra zona.", 64)
        if doc.get("da_sha256") != d.sha256:
            avisos.append("a direção de arte mudou desde que as cues foram medidas: se tamanho, largura ou max_palavras da legenda mudaram, gere as cues de novo")
        if doc.get("estilo") != d["legenda"]["estilo"]:
            raise Erro(f"as cues de {cues_arq.name} foram segmentadas para o estilo `{doc.get('estilo')}`, e a DA agora pede `{d['legenda']['estilo']}`.",
                       "Gere as cues de novo (sem --cues); as correções à mão terão de ser refeitas com cues.py editar.")
    else:
        r = modulo_cues.gerar(palavras, d=d, video=video_arq, formato=formato, plataforma=plataforma, inicio=inicio, fim=fim, nome=nome,
                              glossario=opcoes.get("glossario"), escala=opcoes.get("escala"), fps=fps, forcar=bool(opcoes.get("refazer_cues")),
                              pontuacao=opcoes.get("pontuacao"), limiar=float(opcoes.get("limiar_confianca") or modulo_cues.LIMIAR_CONFIANCA),
                              gravar_arquivos=False)
        doc, arquivos, nome, L, A = r["doc"], r["arquivos"], r["nome"], r["largura"], r["altura"]
        inicio = float(inicio or 0.0)
        if doc["notas"].get("fim_pedido") is not None:
            fim = doc["janela"]["fim"]
            avisos.append(f"--fim {br(doc['notas']['fim_pedido'])} passa do fim do vídeo ({br(float(info['duracao']))} s): o trecho vai até o fim")
    duracao = float(doc["duracao"])
    recortado = inicio > 0.0005 or (fim is not None and float(fim) < float(info["duracao"]) - 0.02)
    fonte_rel = comum.relativo(video_arq, d.raiz)
    fonte_antes = doc.get("fonte")
    doc["fonte"] = {"video": fonte_rel, "inicio": round(inicio, 3), "fim": None if fim is None else round(float(fim), 3)}
    # `origem` = o vídeo cujo relógio as cues seguem: a própria fonte quando não há trecho; o vídeo legendado quando há
    queima = saida_arq is not None and not so_overlay and not previa
    if not opcoes.get("cues"):
        if not recortado:
            doc["origem"] = fonte_rel
        elif queima:
            doc["origem"] = comum.relativo(saida_arq, d.raiz)
        else:
            doc["origem"] = f"{fonte_rel}#t={inicio:.3f},{inicio + duracao:.3f}"
        modulo_cues.gravar(doc, arquivos["cues"].parent, nome)
    elif queima or not recortado:
        # cues corrigidas (prévia → editar → --cues): ao queimar, `origem` deixa de ser o endereço do trecho
        # ("…#t=início,fim") e passa a ser o vídeo legendado — a mesma regra do caminho sem --cues
        nova, antes = (comum.relativo(saida_arq, d.raiz) if recortado else fonte_rel), (doc.get("origem"), fonte_antes)
        doc["origem"] = nova
        if antes != (doc["origem"], doc["fonte"]):
            modulo_cues.gravar(doc, arquivos["cues"].parent, nome)
    if (doc.get("notas") or {}).get("depois_do_fim"):
        avisos.append(f"{doc['notas']['depois_do_fim']} palavra(s) da transcrição começam depois do fim do vídeo e ficaram de fora — a transcrição é mesmo deste vídeo?")
    avisos += [a["mensagem"] for a in doc.get("avisos") or [] if a["tipo"] in ("confianca", "largura", "linhas", "duracao", "relampago")]
    por_tipo: dict = {}
    for a in doc.get("avisos") or []:
        por_tipo[a["tipo"]] = por_tipo.get(a["tipo"], 0) + 1
    if por_tipo.get("leitura"):
        avisos.append(f"{por_tipo['leitura']} cue(s) passam de {modulo_cues.CPS_QUEIMADA} caracteres por segundo (fala muito rápida ou tempo ruim na transcrição)")

    # 3. estados → PNGs pequenos + linha do tempo em quadros
    pasta_png = d.raiz / "legendas" / "_png" / nome
    if pasta_png.exists():
        shutil.rmtree(pasta_png)
    cadeia = cadeia_da_base(d, info, L, A, enquadramento, opcoes.get("foco"), bool(opcoes.get("tratamento")))
    resultado = {"saida": None, "saidas": [], "carimbo": None, "cues_json": arquivos["cues"], "srt": arquivos["srt"], "vtt": arquivos["vtt"],
                 "srt_ao_lado": None, "previa": None, "nome": nome, "formato": doc["formato"], "largura": L, "altura": A,
                 "plataforma": doc["plataforma"], "estilo": d["legenda"]["estilo"], "animacao": d["legenda"].get("animacao", "nenhuma"),
                 "duracao": duracao, "cues": len(doc["cues"]), "palavras": sum(len(c["palavras"]) for c in doc["cues"]),
                 "estados": 0, "avisos": avisos, "glossario": doc.get("glossario") or {}, "conferencia": {}, "tempo_s": None}
    try:
        # Uma entrada só na fila de render para o trabalho inteiro (estados em PIL, quadros de conferência e o ffmpeg da
        # composição): as funções do kit chamadas aqui dentro reentram na mesma trava.
        with trava.Trava(rotulo="video-legendas"):
            montagem = _Estados(doc, d, L, A, fps, pasta_png)
            entradas = montagem.montar()
            rel = montagem.rel
            resultado["estados"] = rel["estados"]
            minimo = float(getattr(da, "MINIMO_LEGENDA", 0.04))
            pequenas = [e for e in rel["encolhidas"] if e["tamanho_fracao"] < minimo]
            zona = {"ok": not rel["fora_da_zona"], "estados": rel["estados"], "cues_fora": rel["fora_da_zona"],
                    "menor_tamanho_fracao": round(rel["menor_tamanho_fracao"], 4), "minimo_legivel": minimo,
                    "encolhidas": rel["encolhidas"], "abaixo_do_minimo": [e["cue"] for e in pequenas], "pop_reduzido": rel["pop_reduzido"],
                    "faixa_reservada": faixa_reservada(d, L, A), "fora_da_faixa": rel["fora_da_faixa"], "linhas_refeitas": rel["linhas_refeitas"]}
            resultado["conferencia"]["zona"] = zona
            if rel["fora_da_zona"]:
                raise Erro(f"{len(rel['fora_da_zona'])} cue(s) não cabem na zona segura `{doc['plataforma']}` nem no menor tamanho (cues {rel['fora_da_zona'][:8]}): nada foi gravado.",
                           "Divida essas cues (cues.py editar <arquivo> --cue N --dividir K) ou troque a palavra longa demais; depois rode com --cues.")
            for e in pequenas:
                avisos.append(f"cue {e['cue']}: encolheu para {br(e['tamanho_fracao'], 3)} do lado menor (mínimo legível {br(minimo, 3)}) — «{e['texto']}»; divida a cue com cues.py editar")
            if rel["encolhidas"] and not pequenas:
                avisos.append(f"{len(rel['encolhidas'])} cue(s) encolheram para caber (menor texto {br(rel['menor_tamanho_fracao'], 3)} do lado menor): palavra mais larga que o bloco "
                              f"da legenda, cujo teto é legenda.largura_max da DA dentro da zona segura — trocar de --plataforma não alarga")
            if rel["sem_quadro"]:
                avisos.append(f"{rel['sem_quadro']} palavra(s) duram menos de um quadro e não chegam a acender")
            if rel["pop_reduzido"]:
                avisos.append(f"em {rel['pop_reduzido']} estado(s) o pop foi reduzido para a palavra não sair da zona segura")
            if rel["linhas_refeitas"]:
                avisos.append(f"{len(rel['linhas_refeitas'])} cue(s) vieram com mais linhas que legenda.max_linhas ({linhas_permitidas(d)}) e foram quebradas de novo "
                              f"pelo kit (cues {rel['linhas_refeitas'][:8]}): a legenda não sai da faixa que a DA reserva para ela")
            if rel["fora_da_faixa"]:
                avisos.append(f"{len(rel['fora_da_faixa'])} cue(s) passam da faixa que a DA reserva para a legenda (cues {rel['fora_da_faixa'][:8]}) e podem "
                              f"encostar em GC, título ou gráfico: divida essas cues (cues.py editar … --dividir K)")
            if not zona["faixa_reservada"]:
                fmt = da.orientacao_de(L, A)
                avisos.append(f"a DA não reserva a faixa da legenda no {fmt}: GC, crédito e gráficos do kit ficam nesse mesmo lugar e não desviam "
                              f"(`{comum.DA_CLI} validar` mostra as duas faixas). Se este vídeo tem ou vai ter GC, inclua \"{fmt}\" em "
                              f"legenda.reservar_em (nova revisão da DA) e refaça essas peças antes de queimar; se não tem, siga")

            # 4. contraste contra o vídeo real (e prévia, que usa os mesmos quadros)
            pasta_tmp = d.raiz / "legendas" / "_png" / f"_{nome}_quadros"
            if pasta_tmp.exists():
                shutil.rmtree(pasta_tmp)
            pasta_tmp.mkdir(parents=True, exist_ok=True)
            try:
                amostras = None
                if previa:
                    quantas = 8 if previa is True else max(1, int(previa))
                    folha = comum.absoluto(opcoes.get("previa_saida") or (d.raiz / "legendas" / f"_previa_{nome}.png"))
                    folha, amostras = _folha_de_previa(d, doc, rel, video_arq, inicio, cadeia, L, A, pasta_tmp, folha, quantas)
                    resultado["previa"] = folha
                if not opcoes.get("sem_contraste"):
                    if amostras is None:
                        from PIL import Image
                        ids = [c["id"] for c in doc["cues"]]
                        n = min(len(ids), int(opcoes.get("amostras") or AMOSTRAS_DE_CONTRASTE))
                        escolhidas = list(dict.fromkeys(ids[int(round(k * (len(ids) - 1) / max(1, n - 1)))] for k in range(n))) if n > 1 else ids[:1]
                        tempos = [rel["amostras"][i]["t"] for i in escolhidas]
                        arqs = _quadros_da_base(video_arq, [inicio + t for t in tempos], cadeia, pasta_tmp, max(160, min(480, L)), "contraste")
                        amostras = []
                        for i, t, a in zip(escolhidas, tempos, arqs):
                            with Image.open(a) as im:
                                amostras.append({"t": t, "cue": i, "quadro": im.convert("RGB"), "caixa": rel["amostras"][i]["caixa"]})
                    contraste = conferir_contraste(d, amostras, L, A, d["legenda"]["estilo"])
                    resultado["conferencia"]["contraste"] = contraste
                    for tr in contraste["trechos"]:
                        intervalo = relogio(tr["t0"]) if tr["t1"] == tr["t0"] else f"{relogio(tr['t0'])}–{relogio(tr['t1'])}"
                        avisos.append(f"contraste ruim em {intervalo}: a legenda lê a {br(tr['pior'], 1)}:1 contra o vídeo (mínimo {br(CONTRASTE_RUIM, 0)}:1; "
                                      f"fundo {'claro' if tr['fundo_video'] > 0.4 else 'escuro'}, luminância {br(tr['fundo_video'])})")
                    if contraste["trechos"] or contraste["atencao"]:
                        if not contraste["trechos"]:
                            avisos.append(f"contraste entre {br(CONTRASTE_RUIM, 0)}:1 e {br(CONTRASTE_BOM, 1)}:1 em {contraste['atencao']} de {contraste['amostras']} amostra(s) (pior {br(contraste['pior'], 1)}:1): lê, mas no limite")
                        avisos += [f"  → {s}" for s in contraste["sugestoes"]]
                    if contraste["carregado"]:
                        onde = ", ".join(relogio(t) for t in contraste["carregado"][:6]) + ("…" if len(contraste["carregado"]) > 6 else "")
                        avisos.append(f"fundo carregado atrás da legenda em {onde}: há claro e escuro misturados na faixa (GC, texto ou legenda que o vídeo "
                                      f"já tem?) — olhe a prévia; se colidir, mude legenda.posicao.<formato>.y na DA ou legende o material sem os gráficos")
            finally:
                shutil.rmtree(pasta_tmp, ignore_errors=True)

            # 5. render
            parametros = {"cues_json": comum.relativo(arquivos["cues"], d.raiz), "cues_sha256": comum.sha256_arquivo(arquivos["cues"]),
                          "palavras": doc.get("palavras_origem"), "fonte": doc["fonte"], "plataforma": doc["plataforma"],
                          "estilo": resultado["estilo"], "animacao": resultado["animacao"], "n_cues": len(doc["cues"]),
                          "enquadramento": enquadramento if (info["largura"], info["altura"]) != (L, A) else None,
                          "tratamento_da_da": bool(opcoes.get("tratamento")), "editado": bool(doc.get("editado")),
                          "conferencia": {"zona_ok": zona["ok"], "menor_tamanho_fracao": zona["menor_tamanho_fracao"],
                                          "contraste_pior": (resultado["conferencia"].get("contraste") or {}).get("pior"),
                                          "contraste_trechos_ruins": len((resultado["conferencia"].get("contraste") or {}).get("trechos") or [])}}
            if previa:
                pass
            elif so_overlay:
                resultado["saidas"] = _gravar_overlay(d, entradas, saida_arq, codecs, L, A, fps, duracao, parametros, arquivos["cues"])
                resultado["saida"] = resultado["saidas"][0]
                for faixa in resultado["saidas"]:
                    _acertar_formato_do_carimbo(d, faixa, doc["formato"], [arquivos["cues"]])
            else:
                r = vid.compor_cues(video_arq, entradas, saida_arq, da_obj=d, inicio=inicio if recortado else None,
                                    duracao=duracao if recortado else None, tratamento_base=cadeia, tamanho=(L, A),
                                    crf=int(opcoes.get("crf") or 18), ferramenta=comum.FERRAMENTA, parametros=parametros, insumos=[arquivos["cues"]])
                resultado["saida"], resultado["saidas"], resultado["carimbo"] = r["saida"], [r["saida"]], r["carimbo"]
                _acertar_formato_do_carimbo(d, r["saida"], doc["formato"], [video_arq, arquivos["cues"]])
            if resultado["saida"] is not None and opcoes.get("srt_ao_lado", True):
                ao_lado = Path(resultado["saida"]).with_suffix(".srt")
                if ao_lado.parent.resolve() != arquivos["srt"].parent.resolve():
                    shutil.copyfile(arquivos["srt"], ao_lado)
                    resultado["srt_ao_lado"] = ao_lado
            if resultado["saidas"] and resultado["carimbo"] is None:
                resultado["carimbo"] = da.caminho_do_carimbo(resultado["saidas"][0])
    finally:
        if not opcoes.get("manter_png"):
            shutil.rmtree(pasta_png, ignore_errors=True)
            try:
                pasta_png.parent.rmdir()                       # legendas/_png some quando fica vazia
            except OSError:
                pass
    resultado["tempo_s"] = round(time.time() - t_inicio, 2)
    return resultado


def _gravar_overlay(d, entradas: list[dict], saida: Path, codecs: list[str], L: int, A: int, fps: Fraction, duracao: float,
                    parametros: dict, cues_arq: Path) -> list[Path]:
    """Faixa do tamanho do quadro, transparente fora da legenda: .webm (VP9 com alfa) e/ou .mov (ProRes 4444)."""
    from PIL import Image
    _, _, video, _ = comum.kit()
    total = max(1, int(round(duracao * float(fps))))
    linha = sorted(((int(round(e["t0"] * float(fps))), int(round(e["t1"] * float(fps))), e) for e in entradas), key=lambda x: x[0])
    vazio = bytes(L * A * 4)
    gravadas = []
    for codec in codecs:
        alvo = saida.with_suffix(CODECS_DE_OVERLAY[codec])
        with video.Codificador(alvo, largura=L, altura=A, fps=fps, codec=codec, da_obj=d, ferramenta=comum.FERRAMENTA,
                               parametros={**parametros, "so_overlay": True}, insumos=[cues_arq], rotulo="legenda com alfa") as cod:
            q = 0
            for q0, q1, e in linha:
                q0, q1 = max(q0, q), min(q1, total)
                if q1 <= q0:
                    continue
                if q0 > q:
                    cod.escrever(vazio, repetir=q0 - q)
                tela = Image.new("RGBA", (L, A), (0, 0, 0, 0))
                with Image.open(e["imagem"]) as im:
                    im = im.convert("RGBA")
                    tela.alpha_composite(im, (max(0, e["x"]), max(0, e["y"])), (max(0, -e["x"]), max(0, -e["y"])))
                cod.escrever(tela.tobytes(), repetir=q1 - q0)
                q = q1
            if q < total:
                cod.escrever(vazio, repetir=total - q)
        gravadas.append(alvo)
    return gravadas


# ───────────────────────────────────────────────────────────────────── CLI ──
def _foco(s: str):
    import argparse
    try:
        x, y = (float(v) for v in s.replace(";", ",").split(","))
        if not (0 <= x <= 1 and 0 <= y <= 1):
            raise ValueError
        return x, y
    except ValueError:
        raise argparse.ArgumentTypeError(f"esperava x,y em frações do quadro de origem (ex.: 0.5,0.35), veio {s!r}")


def montar_cli():
    ap = comum.Analisador(
        prog="legendar.py",
        description="Queima legenda palavra a palavra (karaokê), palavra única ou bloco num vídeo, com o estilo que a direção de\n"
                    "arte do projeto define (bloco `legenda` do da/da.json), sempre dentro da zona segura da plataforma.\n"
                    "Grava também legendas/<nome>.cues.json, .srt e .vtt. Uma passada de ffmpeg, áudio preservado, saída carimbada.",
        epilog="Códigos de saída: 0 ok · 1 erro (ou --estrito com aviso de legibilidade) · 2 projeto sem direção de arte · 64 uso incorreto ·\n"
               "75 desistiu da fila de render · 124 ffmpeg sem progresso.\n"
               "Estilo, cor, fonte, tamanho, posição e animação NÃO são opções: mude no da/da.json (skill video-direcao-de-arte).")
    ap.add_argument("--video", required=True, metavar="ARQ", help="vídeo que recebe a legenda (não é alterado)")
    ap.add_argument("--palavras", metavar="ARQ", help='transcrição palavra a palavra: [{"a": início_s, "b": fim_s, "w": "palavra", "p": confiança}]')
    ap.add_argument("--saida", metavar="ARQ", help="vídeo legendado (.mp4) ou, com --so-overlay, faixa com alfa (.webm ou .mov)")
    ap.add_argument("--formato", metavar="F", help="quadro de saída: formato da DA (vertical, horizontal…) ou LxA; padrão: o do vídeo")
    ap.add_argument("--plataforma", metavar="P", help="zona segura: uniao (padrão do vertical), reels, tiktok, shorts")
    ap.add_argument("--inicio", type=modulo_cues._tempo, metavar="S", help="início do trecho (segundos ou m:ss)")
    ap.add_argument("--fim", type=modulo_cues._tempo, metavar="S", help="fim do trecho")
    ap.add_argument("--so-overlay", action="store_true", help="grava só a legenda sobre fundo transparente, para o editor montar")
    ap.add_argument("--codec", choices=["vp9alfa", "prores4444", "ambos"], help="codec da faixa com alfa (padrão: pela extensão de --saida)")
    ap.add_argument("--previa", nargs="?", const=8, type=int, metavar="N", help="só gera a folha de contato com N cues amostradas (padrão 8); não renderiza vídeo")
    ap.add_argument("--previa-saida", metavar="ARQ", help="onde gravar a folha de contato (padrão: legendas/_previa_<nome>.png)")
    ap.add_argument("--cues", metavar="ARQ", help="usa um arquivo de cues já corrigido (cues.py editar) em vez de segmentar de novo")
    ap.add_argument("--refazer-cues", action="store_true", help="segmenta de novo mesmo que o arquivo de cues tenha correções à mão (elas se perdem)")
    ap.add_argument("--nome", metavar="NOME", help="nome dos arquivos em legendas/ (padrão: o da saída)")
    ap.add_argument("--glossario", metavar="ARQ", help="glossário (padrão: legendas/glossario.json, se existir)")
    ap.add_argument("--pontuacao", choices=modulo_cues.PONTUACOES, help="pontuação queimada (padrão: limpa; no estilo bloco, manter)")
    ap.add_argument("--limiar-confianca", type=float, metavar="P", help=f"confiança do whisper abaixo da qual a palavra vira aviso (padrão {modulo_cues.LIMIAR_CONFIANCA})")
    ap.add_argument("--enquadramento", choices=ENQUADRAMENTOS, default="recorte",
                    help="quando a proporção muda: recorte (âncora da DA; padrão) ou encaixe (vídeo inteiro, conforme tratamento.encaixe da DA)")
    ap.add_argument("--foco", type=_foco, metavar="X,Y", help="centro do recorte em frações do vídeo de origem (ex.: 0.5,0.35 para o rosto)")
    ap.add_argument("--tratamento", action="store_true", help="aplica o tratamento de cor da DA à base (só para material BRUTO; o render final já está tratado)")
    ap.add_argument("--escala", type=float, metavar="F", help="reduz o quadro de saída (0.5 = metade) para prévias e testes")
    ap.add_argument("--crf", type=int, metavar="N", help="qualidade do H.264 (padrão 18; menor = melhor e maior)")
    ap.add_argument("--amostras", type=int, metavar="N", help=f"quadros amostrados na conferência de contraste (padrão {AMOSTRAS_DE_CONTRASTE})")
    ap.add_argument("--sem-contraste", action="store_true", help="pula a conferência de contraste contra o vídeo")
    ap.add_argument("--sem-srt-ao-lado", action="store_true", help="não copia o .srt para junto da saída")
    ap.add_argument("--manter-png", action="store_true", help="mantém os PNGs dos estados em legendas/_png/<nome>/ (para depurar)")
    ap.add_argument("--projeto", metavar="PASTA", help="pasta do projeto (onde está da/da.json); padrão: a pasta atual, a da saída ou a do vídeo")
    ap.add_argument("--estrito", action="store_true", help="sai com código 1 se houver trecho de contraste ruim ou cue abaixo do tamanho mínimo legível")
    ap.add_argument("--json", action="store_true", help="imprime o resultado em JSON (para outra skill ler)")
    return ap


def _imprimir(r: dict, raiz) -> None:
    rel = lambda p: comum.relativo(p, raiz) if p else None  # noqa: E731
    cab = f"{r['cues']} cue(s), {r['palavras']} palavra(s), {r['estados']} estado(s) · {r['formato']} {r['largura']}×{r['altura']} · zona {r['plataforma']} · {r['estilo']}" \
          + (f" + {r['animacao']}" if r["animacao"] != "nenhuma" else "") + f" · {br(r['tempo_s'], 1)} s"
    if r["saida"]:
        print(f"{' + '.join(rel(s) for s in r['saidas'])}: {cab}")
    else:
        print(f"prévia {rel(r['previa'])}: {cab}")
    print(f"  cues: {rel(r['cues_json'])} (+ .srt e .vtt de frases inteiras)" + (f" · cópia do .srt em {rel(r['srt_ao_lado'])}" if r["srt_ao_lado"] else ""))
    g = r.get("glossario") or {}
    if any(g.get(k) for k in ("trocas", "numeros", "censuradas", "destaques")) or g.get("sem_ocorrencia"):
        print(f"  glossário: {g.get('trocas', 0)} troca(s), {g.get('numeros', 0)} número(s), {g.get('censuradas', 0)} censura(s), {g.get('destaques', 0)} destaque(s)"
              + (f" · sem ocorrência neste trecho: {', '.join(g['sem_ocorrencia'])}" if g.get("sem_ocorrencia") else ""))
    z = r["conferencia"].get("zona")
    if z:
        print(f"  zona segura: todos os {z['estados']} estados dentro · menor texto {br(z['menor_tamanho_fracao'], 3)} do lado menor (mínimo legível {br(z['minimo_legivel'], 3)})")
    c = r["conferencia"].get("contraste")
    if c and c["amostras"]:
        print(f"  contraste contra o vídeo: pior {br(c['pior'], 1)}:1 em {c['amostras']} amostra(s)" + (" — ok" if c["ok"] and not c["atencao"] else ""))
    if r["previa"] and r["saida"]:
        print(f"  prévia: {rel(r['previa'])}")
    principais = [a for a in r["avisos"] if "confiança" not in a]
    revisar = [a for a in r["avisos"] if "confiança" in a]
    for a in principais:
        print(f"  {'aviso: ' if not a.startswith('  →') else ''}{a}")
    for a in revisar[:10]:
        print(f"  revisar: {a}")
    if len(revisar) > 10:
        print(f"  revisar: … e mais {len(revisar) - 10} palavra(s) com confiança baixa (cues.py mostrar <arquivo> --avisos)")


def main(argv=None) -> int:
    import json
    args = montar_cli().parse_args(argv)
    r = legendar(args.video, args.palavras, args.saida, formato=args.formato, plataforma=args.plataforma, inicio=args.inicio, fim=args.fim,
                 so_overlay=args.so_overlay, codec=args.codec, previa=args.previa, previa_saida=args.previa_saida, cues=args.cues,
                 refazer_cues=args.refazer_cues, nome=args.nome, glossario=args.glossario, pontuacao=args.pontuacao,
                 limiar_confianca=args.limiar_confianca, enquadramento=args.enquadramento, foco=args.foco, tratamento=args.tratamento,
                 escala=args.escala, crf=args.crf, amostras=args.amostras, sem_contraste=args.sem_contraste,
                 srt_ao_lado=not args.sem_srt_ao_lado, manter_png=args.manter_png, projeto=args.projeto)
    raiz = Path(r["cues_json"]).parent.parent
    if args.json:
        limpo = json.loads(json.dumps(r, default=str, ensure_ascii=False))
        for it in (limpo.get("conferencia", {}).get("contraste") or {}).get("itens") or []:
            it.pop("quadro", None)
        print(json.dumps(limpo, ensure_ascii=False, indent=1))
    else:
        _imprimir(r, raiz)
    if args.estrito:
        c, z = r["conferencia"].get("contraste") or {}, r["conferencia"].get("zona") or {}
        if c.get("trechos") or z.get("abaixo_do_minimo"):
            print("reprovado (--estrito): há trecho de contraste ruim ou cue abaixo do tamanho mínimo legível.", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(modulo_cues.executar_cli(main))
