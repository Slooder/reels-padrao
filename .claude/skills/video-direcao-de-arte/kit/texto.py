#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""texto.py — texto em PIL fiel aos papéis tipográficos da DA (para legendas, thumbnails e folhas).

Cobre: fonte variável (eixos wght/wdth via set_variation_by_axes), tracking (em), caixa alta, escala_x
(condensação geométrica, como o motor faz com scaleX), contorno, sombra desfocada, fundo arredondado,
quebra em linhas com largura máxima e sem palavra órfã, encolher até caber, medição (bbox) e retorno
RGBA recortado pelo bbox. A legenda (compor_legenda) é ciente da ZONA SEGURA da plataforma.

    import da, texto
    d = da.carregar()
    L, A = 1080, 1920
    est = texto.Estilo.legenda(d, L, A)                       # bloco `legenda` da DA inteiro
    dest = texto.Estilo.legenda(d, L, A, destaque=True)       # palavra falada (cor_destaque)
    img, info = texto.compor_legenda(["A", "conta", "que", "não", "fecha"], [est, dest, est, est, est], d, L, A)
    # → RGBA L×A; várias linhas; centrada e limitada ao retângulo da zona 'uniao'; info["caixa"], info["dentro_da_zona"]
    estados = texto.estados_da_legenda(["A", "conta", "que", "não"], d, L, A)   # um (imagem, info) por palavra, conforme legenda.estilo
    est2 = texto.Estilo.do_papel(d, "titulo", tamanho_px=92, cor="texto", contorno=("fundo", 0.06))
    bloco, info = texto.desenhar("A conta que não fecha", est2, largura_max=860)
    bloco, info = texto.compor_bloco(["A", "CONTA", "NÃO", "FECHA"], [est2, est2.com(cor="primaria"), est2, est2], largura_max=860)

Paridade com o motor (D10): o MESMO token rende o mesmo desenho em texto.py e em motor/cenas/_legenda.js —
  · vão entre palavras = avanço real do espaço da fonte (+ tracking), não uma constante;
  · o kerning da fonte vale também com tracking ≠ 0, como o letter-spacing do navegador;
  · contorno.espessura = fração do tamanho da fonte, espessura EXTERNA visível (para fora da letra), cantos redondos;
  · sombra.dx/dy/desfoque em fração do tamanho, projetada pelo texto JÁ com o contorno; desfoque no sentido do CSS
    (raio; o desvio-padrão é a metade);
  · legenda.estilo (karaoke | palavra | bloco) decide os estados de uma cue: estados_da_legenda();
  · escala_x condensa TUDO na horizontal (letra, contorno, sombra, respiro do fundo), como o scaleX do motor.
Todas as medidas em px. Frações de tamanho da DA viram px com d.px(fracao, largura, altura).
"""
from __future__ import annotations

import math
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path

sys.dont_write_bytecode = True     # D9: nada de __pycache__ dentro da skill (trava.py apaga o que já tiver nascido)
KIT = Path(__file__).resolve().parent
if str(KIT) not in sys.path:
    sys.path.insert(0, str(KIT))
import da  # noqa: E402

from PIL import Image, ImageDraw, ImageFilter, ImageFont  # noqa: E402

_FONTES: dict = {}


# ───────────────────────────────────────────────────────────────── fontes ──
def carregar_fonte(arquivo, tamanho_px: float, eixos: dict | None = None, eixos_ordem: list | None = None):
    """ImageFont.FreeTypeFont com os eixos de fonte variável aplicados (cache por arquivo/tamanho/eixos).
    O tamanho é fracionário (centésimos de px), como no navegador: 0,062 × 540 = 33,48 px rende a mesma largura no
    motor e aqui. Num Pillow antigo, que só aceita tamanho inteiro, cai para o inteiro mais próximo."""
    tam = max(1.0, round(float(tamanho_px), 2))
    chave = (str(arquivo), tam, tuple(sorted((eixos or {}).items())))
    if chave in _FONTES:
        return _FONTES[chave]
    try:
        try:
            f = ImageFont.truetype(str(arquivo), tam if tam != int(tam) else int(tam))
        except TypeError:
            f = ImageFont.truetype(str(arquivo), max(1, int(round(tam))))
    except OSError as e:
        raise da.DAErro(f"não consegui abrir a fonte {arquivo}: {e}")
    if eixos:
        try:
            if eixos_ordem:
                f.set_variation_by_axes([eixos.get(t, 0) for t in eixos_ordem])
            else:
                ordem = [a["name"].decode() if isinstance(a.get("name"), bytes) else str(a.get("name")) for a in f.get_variation_axes()]
                f.set_variation_by_axes([eixos.get(_tag_do_eixo(n), 0) for n in ordem])
        except (OSError, ValueError, AttributeError):
            pass                                             # fonte estática: ignora
    _FONTES[chave] = f
    return f


def _tag_do_eixo(nome: str) -> str:
    n = str(nome).lower()
    return {"weight": "wght", "width": "wdth", "slant": "slnt", "italic": "ital", "optical size": "opsz"}.get(n, n[:4])


# ───────────────────────────────────────────────────────────────── estilo ──
@dataclass
class Estilo:
    """Tudo o que define o desenho de um texto. Crie com Estilo.do_papel(da, papel, …) e varie com .com(…)."""
    arquivo: str
    tamanho: float                                  # px
    cor: tuple = (255, 255, 255, 255)               # RGBA — da-livre: padrão neutro de um Estilo criado sem DA; do_papel sempre troca
    eixos: dict = field(default_factory=dict)       # {"wght": 700, "wdth": 82}
    eixos_ordem: list = field(default_factory=list)
    tracking: float = 0.0                           # em
    caixa_alta: bool = False
    escala_x: float = 1.0
    altura_linha: float = 1.2
    contorno: tuple | None = None                   # (RGBA, espessura_px)
    sombra: dict | None = None                      # {"dx","dy","desfoque" em px, "cor": RGBA}
    fundo: dict | None = None                       # {"cor": RGBA, "raio": px, "respiro": (x_px, y_px)}
    alinhamento: str = "esquerda"                   # esquerda | centro | direita
    alfa: float = 1.0                               # opacidade global (0–1)
    cores_da: dict | None = field(default=None, repr=False, compare=False)   # seção `cor` da DA: deixa .com(cor="primaria") resolver token

    @classmethod
    def do_papel(cls, d: "da.DA", papel: str, tamanho_px: float, cor="texto", contorno=None, sombra=None,
                 fundo=None, alinhamento: str = "esquerda", largura=None, altura=None) -> "Estilo":
        """Estilo a partir de um papel da DA.
        contorno: (token_ou_hex, espessura_em)  ·  sombra: {dx, dy, desfoque} em em + alfa/cor  ·
        fundo: {cor, alfa, raio, respiro: [x_em, y_em]}  (as mesmas chaves do bloco `legenda` do da.json)."""
        p = d.fonte(papel)
        if not p["caminho"]:
            raise da.DAErro(f"o papel {papel!r} usa fonte do sistema (arquivo null); aponte um arquivo no da.json para desenhar com PIL")
        est = cls(arquivo=p["caminho"], tamanho=float(tamanho_px), cor=d.rgba(cor), eixos=dict(p.get("eixos_efetivos") or {}),
                  eixos_ordem=list(p.get("eixos_ordem") or []), tracking=float(p.get("tracking") or 0), caixa_alta=p.get("caixa") == "alta",
                  escala_x=float(p.get("escala_x") or 1), altura_linha=float(p.get("altura_linha") or 1.2), alinhamento=alinhamento,
                  cores_da=d["cor"])
        if contorno:
            tok, esp = contorno if isinstance(contorno, (tuple, list)) else (contorno.get("cor"), contorno.get("espessura", 0))
            if esp and esp > 0:
                est.contorno = (d.rgba(tok), max(1.0, float(esp) * tamanho_px))
        if sombra:
            est.sombra = {"dx": float(sombra.get("dx", 0)) * tamanho_px, "dy": float(sombra.get("dy", 0)) * tamanho_px,
                          "desfoque": float(sombra.get("desfoque", 0)) * tamanho_px,
                          "cor": d.rgba(sombra.get("cor") or "neutro-1", float(sombra.get("alfa", 0.6)))}
        if fundo:
            resp = fundo.get("respiro") or [0.4, 0.2]
            est.fundo = {"cor": d.rgba(fundo["cor"], float(fundo.get("alfa", 0.85))), "raio": float(fundo.get("raio", 0)) * tamanho_px,
                         "respiro": (float(resp[0]) * tamanho_px, float(resp[1]) * tamanho_px)}
        return est

    @classmethod
    def legenda(cls, d: "da.DA", largura: int, altura: int, cor=None, destaque: bool = False, falada: bool = False) -> "Estilo":
        """Estilo da legenda da DA para um quadro largura×altura (bloco `legenda` inteiro).
        destaque=True → cor_destaque (palavra sendo dita); falada=True → cor_falada (palavras já ditas; null = cor)."""
        leg = d["legenda"]
        tam = float(leg["tamanho"]) * min(int(largura), int(altura))     # fracionário, como ctx.px no motor (d.px arredonda)
        token = cor or (leg["cor_destaque"] if destaque else (leg.get("cor_falada") or leg["cor"]) if falada else leg["cor"])
        est = cls.do_papel(d, leg["papel"], tam, cor=token,
                           contorno=leg.get("contorno"), sombra=leg.get("sombra"), fundo=leg.get("fundo"), alinhamento="centro")
        est.caixa_alta = leg.get("caixa", "alta") == "alta"
        return est

    @classmethod
    def thumbnail(cls, d: "da.DA", largura: int | None = None, altura: int | None = None, destaque: bool = False) -> "Estilo":
        """Estilo do título da thumbnail (bloco `thumbnail`: papel, tamanho, cor/cor_destaque, contorno). Sem
        dimensões, usa formatos.thumbnail. Para a palavra que salta: destaque=True (ou est.com(cor=…))."""
        th = d["thumbnail"]
        if not (largura and altura):
            largura, altura = d.formato("thumbnail")[:2]
        return cls.do_papel(d, th["papel"], float(th["tamanho"]) * min(int(largura), int(altura)),
                            cor=th.get("cor_destaque", "primaria") if destaque else th.get("cor", "texto"),
                            contorno=th.get("contorno"), alinhamento="esquerda")

    def com(self, **mudancas) -> "Estilo":
        """Cópia com alterações. `cor` aceita tupla RGBA/RGB, token da DA ("primaria", "dado-2", "neutro-1" — quando o
        estilo nasceu de Estilo.do_papel/legenda, que guardam a paleta), hex ou o par (d, "token")."""
        if "cor" in mudancas:
            c = mudancas["cor"]
            if isinstance(c, (tuple, list)) and len(c) == 2 and isinstance(c[1], str) and hasattr(c[0], "rgba"):
                c = c[0].rgba(c[1])                                   # (d, "token")
            elif isinstance(c, str):
                if self.cores_da is not None:
                    c = (*da.hex_para_rgb(da.resolver_cor(c, self.cores_da, "Estilo.com(cor=…)")), 255)
                elif c.strip().startswith("#"):
                    c = (*da.hex_para_rgb(c), 255)
                else:
                    raise da.DAErro(f"Estilo.com(cor={c!r}): este estilo não veio de Estilo.do_papel, então não conhece os tokens.",
                                    dica="Use est.com(cor=d.rgba(\"primaria\")) ou est.com(cor=(d, \"primaria\")).")
            elif isinstance(c, (tuple, list)) and len(c) == 3:
                c = (*c, 255)
            mudancas["cor"] = tuple(c)
        return replace(self, **mudancas)

    # -- fonte --------------------------------------------------------------
    def fonte(self, tamanho: float | None = None):
        return carregar_fonte(self.arquivo, tamanho or self.tamanho, self.eixos, self.eixos_ordem)

    def texto(self, s: str) -> str:
        return s.upper() if self.caixa_alta else s


# ───────────────────────────────────────────────────────────────── medição ──
def _tracking_px(est: Estilo, tamanho: float | None = None) -> float:
    return float(est.tracking) * float(tamanho or est.tamanho)


_SEM_LIGADURA = None      # features do raqm para medir/desenhar com tracking (o navegador desliga ligaduras com letter-spacing)


def _comprimento(f, s: str, com_tracking: bool = False) -> float:
    """Avanço de `s` com o kerning da fonte. Com tracking, sem ligaduras opcionais — como o navegador faz com
    letter-spacing. Sem libraqm no Pillow, cai no layout básico (sem kerning GPOS)."""
    global _SEM_LIGADURA
    if not com_tracking:
        return f.getlength(s)
    if _SEM_LIGADURA is None:
        try:
            from PIL import features
            _SEM_LIGADURA = ["-liga", "-clig"] if features.check("raqm") else []
        except Exception:
            _SEM_LIGADURA = []
    try:
        return f.getlength(s, features=_SEM_LIGADURA) if _SEM_LIGADURA else f.getlength(s)
    except (KeyError, ValueError, OSError):
        return f.getlength(s)


def largura_texto(s: str, est: Estilo, tamanho: float | None = None) -> float:
    """Largura de avanço de `s` (já com tracking e escala_x) em px. O kerning da fonte vale também com tracking ≠ 0
    (é o que o navegador faz com letter-spacing): avanço com kerning + tracking entre os caracteres."""
    f = est.fonte(tamanho)
    s = est.texto(s)
    tr = _tracking_px(est, tamanho)
    if abs(tr) < 1e-6:
        w = f.getlength(s)
    else:
        w = _comprimento(f, s, True) + tr * max(0, len(s) - 1)
    return w * est.escala_x


def altura_linha_px(est: Estilo, tamanho: float | None = None) -> float:
    return float(tamanho or est.tamanho) * est.altura_linha


def quebrar_linhas(s: str, est: Estilo, largura_max: float, tamanho: float | None = None, max_linhas: int | None = None,
                   sem_orfa: bool = True) -> list[str]:
    """Quebra por palavras dentro de largura_max; evita palavra órfã na última linha (quando há ≥ 3 palavras
    e cabe juntar). Palavra maior que a largura fica sozinha na linha (não é partida)."""
    palavras = s.split()
    if not palavras:
        return [""]
    linhas: list[list[str]] = [[]]
    for w in palavras:
        teste = " ".join(linhas[-1] + [w])
        if linhas[-1] and largura_texto(teste, est, tamanho) > largura_max:
            linhas.append([w])
        else:
            linhas[-1].append(w)
    if sem_orfa and len(linhas) >= 2 and len(linhas[-1]) == 1 and len(linhas[-2]) >= 2:
        candidata = [linhas[-2][-1], linhas[-1][0]]
        resto = linhas[-2][:-1]
        if largura_texto(" ".join(candidata), est, tamanho) <= largura_max:
            linhas[-2], linhas[-1] = resto, candidata
    out = [" ".join(l) for l in linhas]
    if max_linhas is not None and len(out) > max_linhas:
        out = out[:max_linhas - 1] + [" ".join(out[max_linhas - 1:])]
    return out


def encolher_ate_caber(s: str, est: Estilo, largura_max: float, altura_max: float | None = None, max_linhas: int | None = None,
                       minimo: float = 10.0, passo: float = 0.94) -> tuple[float, list[str]]:
    """Reduz o tamanho até o texto caber (largura, altura, nº de linhas). Devolve (tamanho_px, linhas)."""
    tam = float(est.tamanho)
    while True:
        linhas = quebrar_linhas(s, est, largura_max, tam, None)
        cabe_w = all(largura_texto(l, est, tam) <= largura_max + 0.5 for l in linhas)
        cabe_n = max_linhas is None or len(linhas) <= max_linhas
        cabe_h = altura_max is None or len(linhas) * altura_linha_px(est, tam) <= altura_max + 0.5
        if (cabe_w and cabe_n and cabe_h) or tam * passo < minimo:
            if max_linhas is not None and len(linhas) > max_linhas:
                linhas = quebrar_linhas(s, est, largura_max, tam, max_linhas)
            return tam, linhas
        tam = max(minimo, tam * passo)


def medir(s: str, est: Estilo, largura_max: float | None = None, tamanho: float | None = None) -> dict:
    """{'largura', 'altura', 'linhas': [...], 'tamanho'} do bloco de texto (sem contorno/sombra/fundo)."""
    tam = tamanho or est.tamanho
    linhas = quebrar_linhas(s, est, largura_max, tam) if largura_max else [s]
    return {"largura": max(largura_texto(l, est, tam) for l in linhas), "altura": len(linhas) * altura_linha_px(est, tam),
            "linhas": linhas, "tamanho": tam}


ANCORAS_X, ANCORAS_Y = ("esquerda", "centro", "direita"), ("topo", "centro", "base")


# ───────────────────────────────────────────────────────────────── desenho ──
def _desenhar_linha_crua(desenho: ImageDraw.ImageDraw, xy, s: str, f, est: Estilo, fill, stroke_width: int = 0, stroke_fill=None, tamanho=None):
    """Desenha uma linha com tracking (caractere a caractere quando tracking ≠ 0). Cada caractere cai onde o
    navegador o poria: avanço COM kerning do trecho anterior + tracking acumulado."""
    x, y = xy
    tr = _tracking_px(est, tamanho)
    if abs(tr) < 1e-6:
        desenho.text((x, y), s, font=f, fill=fill, stroke_width=stroke_width, stroke_fill=stroke_fill)
        return
    for i, ch in enumerate(s):
        origem = _comprimento(f, s[:i + 1], True) - f.getlength(ch)        # início do caractere i, com o kerning dos pares anteriores
        desenho.text((x + origem + tr * i, y), ch, font=f, fill=fill, stroke_width=stroke_width, stroke_fill=stroke_fill)


def _sigma(desfoque_px: float) -> float:
    """`sombra.desfoque` é o RAIO de desfoque no sentido do CSS (text-shadow): o desvio-padrão do gaussiano é a metade.
    É assim que o Chromium do motor desenha; o GaussianBlur do PIL recebe o desvio-padrão."""
    return max(0.0, float(desfoque_px or 0)) / 2.0


def desenhar(s: str, est: Estilo, largura_max: float | None = None, altura_max: float | None = None, max_linhas: int | None = None,
             encolher: bool = True, minimo: float = 10.0) -> tuple[Image.Image, dict]:
    """Desenha `s` com o estilo e devolve (imagem RGBA recortada pelo bbox, info).

    info = {'linhas', 'tamanho', 'largura', 'altura', 'caixa': (x0, y0, x1, y1) do recorte dentro da camada,
            'linha_base': y da base da primeira linha, 'origem_x': x onde o texto começa dentro da imagem (sem o
            contorno/sombra), 'avanco': largura de avanço da linha mais larga}. A imagem inclui contorno, sombra e fundo.
    Contorno: `est.contorno[1]` px PARA FORA da letra. Sombra: desfoque = raio CSS (desvio-padrão = metade)."""
    s = est.texto(s)
    tam = float(est.tamanho)
    if largura_max and encolher:
        tam, linhas = encolher_ate_caber(s, est, largura_max, altura_max, max_linhas, minimo)
    elif largura_max:
        linhas = quebrar_linhas(s, est, largura_max, tam, max_linhas)
    else:
        linhas = s.split("\n") if "\n" in s else [s]
    f = est.fonte(tam)
    tr = _tracking_px(est, tam)
    alt_l = altura_linha_px(est, tam)
    larguras = [largura_texto(l, est, tam) / est.escala_x for l in linhas]      # largura ANTES da escala_x
    larg_txt = max(larguras) if larguras else 0
    asc, desc = f.getmetrics()
    esp_cont = int(round(est.contorno[1])) if est.contorno else 0
    somb = est.sombra or {}
    sig = _sigma(somb.get("desfoque", 0))
    margem_x = esp_cont + int(math.ceil(abs(somb.get("dx", 0)) + sig * 3)) + 4
    margem_y = esp_cont + int(math.ceil(abs(somb.get("dy", 0)) + sig * 3)) + 4 + int(math.ceil(max(0.0, (asc + desc - alt_l) / 2)))
    W = int(math.ceil(larg_txt)) + 2 * margem_x + int(abs(tr))
    H = int(math.ceil(alt_l * len(linhas) + max(0, desc))) + 2 * margem_y
    camada = Image.new("RGBA", (max(1, W), max(1, H)), (0, 0, 0, 0))
    d = ImageDraw.Draw(camada)
    # posição das linhas (centradas no avanço da altura_linha)
    posicoes = []
    for i, (l, lw) in enumerate(zip(linhas, larguras)):
        if est.alinhamento == "centro":
            x = margem_x + (larg_txt - lw) / 2
        elif est.alinhamento == "direita":
            x = margem_x + (larg_txt - lw)
        else:
            x = margem_x
        y = margem_y + i * alt_l + (alt_l - (asc + desc)) / 2
        posicoes.append((x, y, l))
    if est.sombra:
        sombra = Image.new("RGBA", camada.size, (0, 0, 0, 0))
        ds = ImageDraw.Draw(sombra)
        for x, y, l in posicoes:
            _desenhar_linha_crua(ds, (x + somb.get("dx", 0), y + somb.get("dy", 0)), l, f, est, somb["cor"], esp_cont, somb["cor"], tam)
        if sig > 0:
            sombra = sombra.filter(ImageFilter.GaussianBlur(sig))
        camada.alpha_composite(sombra)
    if est.contorno:
        for x, y, l in posicoes:
            _desenhar_linha_crua(d, (x, y), l, f, est, est.contorno[0], esp_cont, est.contorno[0], tam)
    for x, y, l in posicoes:
        _desenhar_linha_crua(d, (x, y), l, f, est, est.cor, 0, None, tam)
    # escala_x: condensação geométrica (como scaleX no motor)
    origem_x = float(min(p[0] for p in posicoes)) if posicoes else float(margem_x)
    if abs(est.escala_x - 1) > 1e-6:
        novo_w = max(1, int(round(camada.width * est.escala_x)))
        camada = camada.resize((novo_w, camada.height), Image.LANCZOS)
        margem_x = margem_x * est.escala_x
        larg_txt *= est.escala_x
        origem_x *= est.escala_x
    base_y = (posicoes[0][1] + asc) if posicoes else 0            # y da linha de base da 1ª linha (coords da camada)
    # fundo arredondado atrás do texto: a caixa é a do BLOCO (linhas × altura de linha) mais o respiro — a mesma conta
    # do motor (padding em volta da caixa de linha) e de compor_bloco; não acompanha a tinta de contorno/sombra
    if est.fundo:
        rx, ry = est.fundo["respiro"]
        topo_txt = posicoes[0][1] - (alt_l - (asc + desc)) / 2 if posicoes else margem_y
        x0, y0 = origem_x - rx, topo_txt - ry
        x1, y1 = origem_x + larg_txt + rx, topo_txt + alt_l * len(linhas) + ry
        off_x, off_y = max(0, int(math.ceil(-x0))), max(0, int(math.ceil(-y0)))
        nova = Image.new("RGBA", (int(math.ceil(max(camada.width, x1) + off_x)), int(math.ceil(max(camada.height, y1) + off_y))), (0, 0, 0, 0))
        ImageDraw.Draw(nova).rounded_rectangle([x0 + off_x, y0 + off_y, x1 + off_x, y1 + off_y], radius=est.fundo["raio"], fill=est.fundo["cor"])
        nova.alpha_composite(camada, (off_x, off_y))
        camada = nova
        base_y += off_y
        origem_x += off_x
    if est.alfa < 1:
        a = camada.getchannel("A").point(lambda v: int(v * est.alfa))
        camada.putalpha(a)
    bbox = camada.getbbox() or (0, 0, 1, 1)
    recorte = camada.crop(bbox)
    info = {"linhas": linhas, "tamanho": tam, "largura": recorte.width, "altura": recorte.height,
            "caixa": bbox, "linha_base": base_y - bbox[1], "ascendente": asc, "descendente": desc,
            "origem_x": origem_x - bbox[0], "avanco": larg_txt}
    return recorte, info


# ─────────────────────────────────────────────── bloco palavra a palavra ──
def vao_entre_palavras(est: Estilo, tamanho: float | None = None, espaco_em: float | None = None) -> float:
    """Vão entre duas palavras vizinhas, em px já com escala_x: o avanço REAL do caractere de espaço da fonte mais o
    tracking de cada lado (é o que o navegador põe entre duas palavras). `espaco_em` força um vão fixo em em."""
    tam = float(tamanho or est.tamanho)
    if espaco_em is not None:
        return float(espaco_em) * tam * est.escala_x
    return (est.fonte(tam).getlength(" ") + 2 * _tracking_px(est, tam)) * est.escala_x


def quebrar_palavras(larguras: list[float], vao: float, largura_max: float | None, max_linhas: int | None = None) -> list[list[int]] | None:
    """Distribui palavras (por largura de avanço) em linhas: enche cada linha até `largura_max` e depois equilibra
    (passa a última palavra de uma linha para a seguinte enquanto isso diminuir a linha mais larga do par).
    Devolve a lista de linhas (índices das palavras) ou None se não couber (palavra maior que a largura, ou mais
    linhas que `max_linhas`). motor/cenas/_legenda.js usa o MESMO algoritmo: a quebra é igual nos dois caminhos."""
    n = len(larguras)
    if n == 0:
        return []
    if largura_max is None:
        return [list(range(n))]
    if any(w > largura_max + 0.5 for w in larguras):
        return None
    linhas, atual, w_atual = [], [0], larguras[0]
    for i in range(1, n):
        if w_atual + vao + larguras[i] <= largura_max + 0.5:
            atual.append(i)
            w_atual += vao + larguras[i]
        else:
            linhas.append(atual)
            atual, w_atual = [i], larguras[i]
    linhas.append(atual)
    if max_linhas is not None and len(linhas) > max_linhas:
        return None

    def larg(l):
        return sum(larguras[i] for i in l) + vao * max(0, len(l) - 1)

    for _ in range(4 * n):                                    # equilíbrio: nunca aumenta a linha mais larga do par
        mudou = False
        for j in range(len(linhas) - 1):
            a, b = linhas[j], linhas[j + 1]
            if len(a) < 2:
                continue
            a2, b2 = a[:-1], [a[-1]] + b
            if larg(b2) <= largura_max + 0.5 and max(larg(a2), larg(b2)) < max(larg(a), larg(b)) - 0.5:
                linhas[j], linhas[j + 1] = a2, b2
                mudou = True
        if not mudou:
            break
    return linhas


def escalar_estilo(est: Estilo, k: float) -> Estilo:
    """Cópia do estilo com TUDO o que é medida multiplicado por k: tamanho, contorno, sombra (dx, dy, desfoque) e caixa
    de fundo (raio, respiro). É como o kit encolhe uma cue em conjunto; serve também para o "pop" de uma palavra
    (escalar_estilo(est, 1.08) no primeiro estado dela)."""
    k = float(k)
    if abs(k - 1.0) < 1e-9:
        return est
    return replace(est, tamanho=est.tamanho * k,
                   contorno=(est.contorno[0], est.contorno[1] * k) if est.contorno else None,
                   sombra={**est.sombra, **{c: float(est.sombra.get(c, 0) or 0) * k for c in ("dx", "dy", "desfoque")}} if est.sombra else None,
                   fundo={**est.fundo, "raio": est.fundo["raio"] * k,
                          "respiro": (est.fundo["respiro"][0] * k, est.fundo["respiro"][1] * k)} if est.fundo else None)


def _linhas_forcadas(n: int, linhas) -> list[list[int]]:
    """`linhas` explícitas: lista de contagens ([3, 2]) ou de listas de índices ([[0, 1, 2], [3, 4]])."""
    if all(isinstance(x, int) for x in linhas):
        saida, i = [], 0
        for q in linhas:
            saida.append(list(range(i, i + q)))
            i += q
    else:
        saida = [list(l) for l in linhas]
    plano = [i for l in saida for i in l]
    if plano != list(range(n)) or any(not l for l in saida):
        raise da.DAErro(f"linhas={linhas!r} não cobre as {n} palavras em ordem (use contagens por linha, ex.: [3, 2], ou listas de índices)")
    return saida


def compor_bloco(palavras: list[str], estilos: list[Estilo] | Estilo, largura_max: float | None = None, max_linhas: int | None = None,
                 altura_max: float | None = None, alinhamento: str | None = None, espaco_em: float | None = None,
                 minimo: float = 10.0, linhas=None, passo: float = 0.94) -> tuple[Image.Image, dict]:
    """Bloco de texto palavra a palavra, cada palavra com o próprio estilo (karaokê, palavra em destaque de thumbnail).

    Quebra em até `max_linhas` linhas equilibradas dentro de `largura_max` e só então encolhe (todas as palavras juntas)
    até caber; `largura_max`/`altura_max` valem para o que se VÊ: texto + contorno + caixa de fundo (a sombra, não).
    Contorno, sombra, fundo, tracking, escala_x, altura de linha e alinhamento vêm do PRIMEIRO estilo; os demais só
    mudam cor e tamanho. A caixa de fundo é UMA para o bloco inteiro (como no motor). `linhas` força a quebra
    (contagens por linha ou listas de índices).

    Devolve (RGBA recortada pelo que foi desenhado, info):
      info['linhas'] [[texto, …], …] · info['indices'] [[i, …], …] · info['palavras'] [{'texto','linha','x0','x1','y0','y1'}]
      (caixas de AVANÇO, em px da imagem devolvida) · info['caixa_texto'] e info['caixa'] (texto; texto + contorno +
      fundo) como (x0, y0, x1, y1) na imagem · info['linhas_base'] [y, …] · 'tamanho', 'tamanho_pedido', 'encolheu',
      'coube' (False = nem no tamanho mínimo coube), 'largura', 'altura' (da imagem)."""
    palavras = [str(w) for w in palavras]
    n = len(palavras)
    if n == 0:
        raise da.DAErro("compor_bloco: informe ao menos uma palavra")
    if isinstance(estilos, Estilo):
        estilos = [estilos] * n
    estilos = list(estilos)
    if len(estilos) != n:
        raise da.DAErro(f"compor_bloco: são {n} palavra(s) e {len(estilos)} estilo(s); passe um estilo por palavra ou um só para todas")
    base = estilos[0]
    alin = alinhamento or base.alinhamento
    if alin not in ANCORAS_X:
        raise da.DAErro(f"compor_bloco: alinhamento {alin!r} inválido ({', '.join(ANCORAS_X)})")
    sx = float(base.escala_x) or 1.0
    forcadas = _linhas_forcadas(n, linhas) if linhas else None
    escala, coube = 1.0, True
    while True:
        ests = [escalar_estilo(e, escala) for e in estilos]
        b = ests[0]
        larguras = [largura_texto(w, e) for w, e in zip(palavras, ests)]
        vao = vao_entre_palavras(b, espaco_em=espaco_em)
        esp = int(round(b.contorno[1])) if b.contorno else 0
        rx, ry = b.fundo["respiro"] if b.fundo else (0.0, 0.0)
        borda_x, borda_y = max(esp, rx) * sx, max(esp, ry)       # o que se vê além do texto: contorno OU respiro da caixa, o maior
        util = None if largura_max is None else float(largura_max) - 2 * borda_x
        quebra = forcadas if forcadas else quebrar_palavras(larguras, vao, util, max_linhas)
        alt_l = altura_linha_px(b)
        if forcadas and util is not None and any(sum(larguras[i] for i in l) + vao * (len(l) - 1) > util + 0.5 for l in forcadas):
            quebra = None
        cabe_h = quebra is not None and (altura_max is None or len(quebra) * alt_l + 2 * borda_y <= float(altura_max) + 0.5)
        if quebra is not None and cabe_h:
            break
        if base.tamanho * escala * passo < minimo:
            coube = False
            quebra = forcadas or quebrar_palavras(larguras, vao, None)        # não coube nem no mínimo: uma linha só
            if max_linhas and max_linhas > 1 and not forcadas and n > 1:       # …ou o máximo de linhas, cheias por igual
                por = math.ceil(n / max_linhas)
                quebra = [list(range(i, min(n, i + por))) for i in range(0, n, por)]
            break
        escala *= passo
    tam = base.tamanho * escala
    larg_linhas = [sum(larguras[i] for i in l) + vao * (len(l) - 1) for l in quebra]
    larg_txt = max(larg_linhas)
    alt_txt = len(quebra) * alt_l
    f_base = b.fonte()
    asc, desc = f_base.getmetrics()
    somb = b.sombra or {}
    sig = _sigma(somb.get("desfoque", 0))
    transbordo = max(0.0, (asc + desc - alt_l) / 2)             # glifos mais altos que a caixa da linha (altura_linha < 1,2)
    mx = int(math.ceil((max(esp + abs(somb.get("dx", 0)) + sig * 3, rx)) * sx)) + 6
    my = int(math.ceil(max(esp + abs(somb.get("dy", 0)) + sig * 3 + transbordo, ry))) + 6
    # tudo é desenhado no espaço ANTES da escala_x (x dividido por sx) e condensado no fim, como o scaleX do motor
    Wc = int(math.ceil((larg_txt + 2 * mx) / sx)) + 2
    Hc = int(math.ceil(alt_txt + 2 * my)) + 2
    camada = Image.new("RGBA", (Wc, Hc), (0, 0, 0, 0))
    itens, caixas, bases = [], [None] * n, []
    for li, l in enumerate(quebra):
        x = mx + (0 if alin == "esquerda" else (larg_txt - larg_linhas[li]) / (2 if alin == "centro" else 1))
        topo = my + li * alt_l
        y_base = topo + (alt_l - (asc + desc)) / 2 + asc
        bases.append(y_base)
        for i in l:
            e = ests[i]
            fe = e.fonte()
            itens.append((x / sx, y_base - fe.getmetrics()[0], e.texto(palavras[i]), fe, e))
            caixas[i] = (li, x, x + larguras[i], topo, topo + alt_l)
            x += larguras[i] + vao
    if b.fundo:
        # caixa única do bloco: texto + respiro (o padding do motor), desenhada antes da condensação como tudo o mais
        ImageDraw.Draw(camada).rounded_rectangle([mx / sx - rx, my - ry, (mx + larg_txt) / sx + rx, my + alt_txt + ry],
                                                 radius=b.fundo["raio"], fill=b.fundo["cor"])
    if b.sombra:
        sombra = Image.new("RGBA", camada.size, (0, 0, 0, 0))
        ds = ImageDraw.Draw(sombra)
        for x, y, s_, fe, e in itens:
            _desenhar_linha_crua(ds, (x + somb.get("dx", 0), y + somb.get("dy", 0)), s_, fe, e, somb["cor"], esp, somb["cor"])
        if sig > 0:
            sombra = sombra.filter(ImageFilter.GaussianBlur(sig))
        camada.alpha_composite(sombra)
    dr = ImageDraw.Draw(camada)
    if b.contorno:
        for x, y, s_, fe, e in itens:
            _desenhar_linha_crua(dr, (x, y), s_, fe, e, b.contorno[0], esp, b.contorno[0])
    for x, y, s_, fe, e in itens:
        _desenhar_linha_crua(dr, (x, y), s_, fe, e, e.cor, 0, None)
    if abs(sx - 1) > 1e-6:
        camada = camada.resize((max(1, int(round(camada.width * sx))), camada.height), Image.LANCZOS)
    if base.alfa < 1:
        camada.putalpha(camada.getchannel("A").point(lambda v: int(v * base.alfa)))
    bbox = camada.getbbox() or (0, 0, 1, 1)
    recorte = camada.crop(bbox)
    ox, oy = bbox[0], bbox[1]
    info = {
        "linhas": [[ests[i].texto(palavras[i]) for i in l] for l in quebra], "indices": [list(l) for l in quebra],
        "palavras": [{"texto": palavras[i], "linha": caixas[i][0], "x0": round(caixas[i][1] - ox, 2), "x1": round(caixas[i][2] - ox, 2),
                      "y0": round(caixas[i][3] - oy, 2), "y1": round(caixas[i][4] - oy, 2)} for i in range(n)],
        "caixa_texto": (round(mx - ox, 2), round(my - oy, 2), round(mx + larg_txt - ox, 2), round(my + alt_txt - oy, 2)),
        "caixa": (round(mx - borda_x - ox, 2), round(my - borda_y - oy, 2), round(mx + larg_txt + borda_x - ox, 2), round(my + alt_txt + borda_y - oy, 2)),
        "linhas_base": [round(y - oy, 2) for y in bases], "tamanho": tam, "tamanho_pedido": float(base.tamanho),
        "encolheu": tam < base.tamanho - 1e-6, "coube": coube, "largura": recorte.width, "altura": recorte.height,
        "vao": vao, "contorno_px": esp, "alinhamento": alin,
    }
    return recorte, info


# ────────────────────────────────────────────── legenda ciente da zona segura ──
def _formato_do_quadro(largura: int, altura: int, formato: str | None = None) -> str:
    return formato or ("vertical" if altura > largura else "quadrado" if altura == largura else "horizontal")


def zona_da_legenda(d: "da.DA", largura: int, altura: int, plataforma: str | None = None, formato: str | None = None) -> dict:
    """Retângulo onde a legenda pode ficar: a zona segura da plataforma (padrão do formato: 'uniao' no vertical,
    'padrao' no resto) em px do quadro largura×altura. plataforma='quadro' = o quadro inteiro (sem zona).
    Devolve o dict de d.margens() ('x0','y0','x1','y1','largura','altura','plataforma')."""
    if plataforma == "quadro":
        return {"topo": 0, "direita": 0, "base": 0, "esquerda": 0, "x0": 0, "y0": 0, "x1": largura, "y1": altura,
                "largura": largura, "altura": altura, "plataforma": "quadro"}
    return d.margens(_formato_do_quadro(largura, altura, formato), plataforma, largura=largura, altura=altura)


def caixa_da_legenda(d: "da.DA", largura: int, altura: int, plataforma: str | None = None, formato: str | None = None) -> dict:
    """Onde a legenda da DA cai num quadro largura×altura, antes de qualquer texto: {'x', 'y' (centro, px),
    'largura_max' (px, já limitada à zona), 'zona', 'formato'}. É a conta que compor_legenda e o validador usam."""
    leg = d["legenda"]
    fmt = _formato_do_quadro(largura, altura, formato)
    pos = leg["posicao"].get(fmt) or leg["posicao"]["horizontal"]
    zona = zona_da_legenda(d, largura, altura, plataforma, fmt)
    lmax = float(pos.get("largura_max") or leg["largura_max"]) * largura
    x = float(pos["x"]) * largura if pos.get("x") is not None else (zona["x0"] + zona["x1"]) / 2
    return {"x": x, "y": float(pos["y"]) * altura, "largura_max": min(lmax, float(zona["largura"])), "largura_pedida": lmax,
            "zona": zona, "formato": fmt}


def compor_legenda(palavras: list[str], estilos: list[Estilo] | Estilo, d: "da.DA", largura: int, altura: int,
                   plataforma: str | None = None, x: float | None = None, y: float | None = None, max_linhas: int | None = None,
                   largura_max: float | None = None, formato: str | None = None, linhas=None, espaco_em: float | None = None,
                   minimo: float = 10.0, recortar: bool = False, apenas: int | None = None) -> tuple[Image.Image, dict]:
    """Legenda palavra a palavra, com várias linhas, DENTRO da zona segura da plataforma (D11).

    palavras, estilos : uma cue; um Estilo por palavra (karaokê: Estilo.legenda(d, L, A, destaque=True) na falada).
    plataforma        : zona segura (None = padrão do formato: 'uniao' no vertical, 'padrao' no horizontal/quadrado;
                        'reels'/'instagram', 'tiktok', 'shorts'; 'quadro' = quadro inteiro, sem zona).
    x, y              : CENTRO do bloco em px (None = legenda.posicao.<formato>.x/.y da DA; sem `x` na DA, o centro
                        horizontal é o do RETÂNGULO da zona — no vertical 'uniao' fica em x = 450 de 1080, não em 540).
    max_linhas        : padrão legenda.max_linhas.   largura_max: px (padrão legenda.posicao.<formato>.largura_max ou
                        legenda.largura_max × largura); nunca passa da largura da zona.
    A cue quebra em linhas equilibradas e, só se ainda não couber, encolhe; o bloco é empurrado para dentro da zona se
    o centro pedido o deixaria para fora. `recortar=True` devolve só o retângulo desenhado (PNG pequeno para
    video.compor_cues) em vez do quadro inteiro.
    apenas            : índice de UMA palavra da cue — desenha só ela, centrada, mas no tamanho em que TODAS as palavras
                        da cue cabem sozinhas numa linha (é o estilo `palavra` do motor: a fonte não muda de tamanho de
                        uma palavra para a outra dentro da cue). Para os três estilos prontos, use estados_da_legenda().

    Devolve (RGBA, info). Coordenadas em px do QUADRO: info['bbox'] (tudo o que foi desenhado, com sombra),
    info['caixa'] (texto + contorno + fundo), info['caixa_texto'], info['palavras'] [{'texto','linha','x0','x1','y0','y1'}],
    info['linhas'], info['linha_base'], info['zona'], info['dentro_da_zona'], info['tamanho'], info['tamanho_pedido'],
    info['encolheu'], info['coube']; com recortar=True, info['x'], info['y'] = canto superior esquerdo do recorte.
    info['faixa_reservada']: as peças do kit DESVIAM da faixa da legenda neste formato (legenda.reservar_em)? False — por
    padrão, no horizontal — quer dizer que GC, crédito e gráficos ocupam esse lugar: antes de queimar a legenda, ponha
    o formato em legenda.reservar_em (e refaça as peças) ou confira que nenhum GC/crédito está no ar nesse trecho."""
    leg = d["legenda"]
    ref = caixa_da_legenda(d, largura, altura, plataforma, formato)
    zona = ref["zona"]
    lmax = min(float(largura_max), float(zona["largura"])) if largura_max else ref["largura_max"]
    nl = int(max_linhas or leg["max_linhas"])
    if apenas is None:
        bloco, inf = compor_bloco(palavras, estilos, largura_max=lmax, max_linhas=nl, altura_max=float(zona["altura"]),
                                  alinhamento="centro", espaco_em=espaco_em, minimo=minimo, linhas=linhas)
        cx0, cy0, cx1, cy1 = inf["caixa"]
        w, h = cx1 - cx0, cy1 - cy0
        w_ref, h_ref = w, h
    else:
        # uma palavra por vez: o tamanho é o da cue (a maior escala em que cada palavra cabe sozinha) e o centro é
        # travado pela palavra MAIS LARGA — a palavra visível não muda de tamanho nem de lugar ao longo da cue
        palavras = [str(p) for p in palavras]
        lista = [estilos] * len(palavras) if isinstance(estilos, Estilo) else list(estilos)
        if not (0 <= int(apenas) < len(palavras)) or len(lista) != len(palavras):
            raise da.DAErro(f"compor_legenda: apenas={apenas!r} não é o índice de uma das {len(palavras)} palavra(s) (e é preciso um estilo por palavra)")
        k, coube = 1.0, True
        for w_, e_ in zip(palavras, lista):
            _, i_ = compor_bloco([w_], [e_], largura_max=lmax, max_linhas=1, altura_max=float(zona["altura"]), alinhamento="centro", minimo=minimo)
            k, coube = min(k, i_["tamanho"] / i_["tamanho_pedido"]), coube and i_["coube"]
        medidas = [compor_bloco([w_], [escalar_estilo(e_, k)], alinhamento="centro")[1]["caixa"] for w_, e_ in zip(palavras, lista)]
        w_ref, h_ref = max(c[2] - c[0] for c in medidas), max(c[3] - c[1] for c in medidas)
        i = int(apenas)
        bloco, inf = compor_bloco([palavras[i]], [escalar_estilo(lista[i], k)], alinhamento="centro")
        inf.update(tamanho_pedido=float(lista[i].tamanho), encolheu=k < 1 - 1e-9, coube=coube, indices=[[i]])
        cx0, cy0, cx1, cy1 = inf["caixa"]
        w, h = cx1 - cx0, cy1 - cy0
    cx = ref["x"] if x is None else float(x)                      # centro pedido, empurrado para dentro da zona
    cy = ref["y"] if y is None else float(y)
    cx = (zona["x0"] + zona["x1"]) / 2 if w_ref > zona["largura"] else min(max(cx, zona["x0"] + w_ref / 2), zona["x1"] - w_ref / 2)
    cy = (zona["y0"] + zona["y1"]) / 2 if h_ref > zona["altura"] else min(max(cy, zona["y0"] + h_ref / 2), zona["y1"] - h_ref / 2)
    px, py = cx - w / 2, cy - h / 2                               # canto da CAIXA (texto + contorno + fundo) no quadro
    ox, oy = int(round(px - cx0)), int(round(py - cy0))          # canto do recorte no quadro
    desl = lambda c: (round(c[0] + ox, 2), round(c[1] + oy, 2), round(c[2] + ox, 2), round(c[3] + oy, 2))  # noqa: E731
    caixa = desl(inf["caixa"])
    info = {
        "palavras": [{**p, "x0": round(p["x0"] + ox, 2), "x1": round(p["x1"] + ox, 2), "y0": round(p["y0"] + oy, 2), "y1": round(p["y1"] + oy, 2)}
                     for p in inf["palavras"]],
        "linhas": inf["linhas"], "indices": inf["indices"], "bbox": (ox, oy, ox + bloco.width, oy + bloco.height), "caixa": caixa,
        "caixa_texto": desl(inf["caixa_texto"]), "linha_base": inf["linhas_base"][0] + oy, "linhas_base": [b + oy for b in inf["linhas_base"]],
        "tamanho": inf["tamanho"], "tamanho_pedido": inf["tamanho_pedido"], "tamanho_fracao": inf["tamanho"] / min(largura, altura),
        "encolheu": inf["encolheu"], "coube": inf["coube"], "zona": zona, "plataforma": zona["plataforma"], "formato": ref["formato"],
        "dentro_da_zona": (caixa[0] >= zona["x0"] - 0.5 and caixa[2] <= zona["x1"] + 0.5 and caixa[1] >= zona["y0"] - 0.5 and caixa[3] <= zona["y1"] + 0.5),
        "largura_max": lmax, "vao": inf["vao"], "contorno_px": inf["contorno_px"], "x": ox, "y": oy, "apenas": apenas,
        "faixa_reservada": ref["formato"] in (leg["reservar_em"] if leg.get("reservar_em") is not None else da.RESERVA_PADRAO),
    }
    if recortar:
        return bloco, info
    quadro = Image.new("RGBA", (int(largura), int(altura)), (0, 0, 0, 0))
    quadro.alpha_composite(bloco, (max(0, ox), max(0, oy)), (max(0, -ox), max(0, -oy)))
    return quadro, info


def estados_da_legenda(palavras: list[str], d: "da.DA", largura: int, altura: int, plataforma: str | None = None,
                       x: float | None = None, y: float | None = None, formato: str | None = None,
                       recortar: bool = True, **opcoes) -> list[tuple[Image.Image, dict]]:
    """Os ESTADOS de uma cue conforme legenda.estilo da DA — os mesmos que ctx.kit.legenda(palavras).seek(i) mostra no motor:

      karaoke : um estado por palavra — o bloco inteiro, a palavra i em cor_destaque, as já ditas em cor_falada;
      palavra : um estado por palavra — só a palavra i, em cor_destaque, todas no mesmo tamanho (compor_legenda(apenas=i));
      bloco   : um estado só — o bloco inteiro em `cor`.

    Devolve [(imagem, info), …] na ordem das palavras; info é o de compor_legenda mais info['indice'] (palavra falada;
    None no estilo bloco). Com recortar=True (padrão) cada imagem é o recorte pequeno e info['x'], info['y'] dizem onde
    colar — o formato das cues de video.compor_cues. `opcoes` vão para compor_legenda (max_linhas, largura_max, linhas…)."""
    palavras = [str(p) for p in palavras]
    if not palavras:
        raise da.DAErro("estados_da_legenda: informe ao menos uma palavra")
    estilo = d["legenda"]["estilo"]
    normal = Estilo.legenda(d, largura, altura)
    falando = Estilo.legenda(d, largura, altura, destaque=True)
    ja_dita = Estilo.legenda(d, largura, altura, falada=True)
    comum = dict(plataforma=plataforma, x=x, y=y, formato=formato, recortar=recortar, **opcoes)
    saida = []
    if estilo == "bloco":
        img, info = compor_legenda(palavras, normal, d, largura, altura, **comum)
        return [(img, {**info, "indice": None})]
    for i in range(len(palavras)):
        if estilo == "palavra":
            img, info = compor_legenda(palavras, [falando] * len(palavras), d, largura, altura, apenas=i, **comum)
        else:
            ests = [ja_dita if k < i else falando if k == i else normal for k in range(len(palavras))]
            img, info = compor_legenda(palavras, ests, d, largura, altura, **comum)
        saida.append((img, {**info, "indice": i}))
    return saida


def desenhar_linha(palavras: list[str], estilos: list[Estilo] | Estilo, d: "da.DA", largura: int, altura: int,
                   formato: str | None = None, espaco_em: float | None = None, largura_max: float | None = None,
                   plataforma: str | None = None, x: float | None = None, y: float | None = None) -> tuple[Image.Image, dict]:
    """UMA linha de legenda palavra a palavra (cada palavra com o próprio estilo). É compor_legenda com max_linhas=1:
    centrada no RETÂNGULO da zona segura (`plataforma`; padrão 'uniao' no vertical) e limitada a ele; se não couber,
    todas as palavras encolhem juntas e info['encolheu'] vem True — para quebrar em linhas em vez de encolher, use
    compor_legenda. `x`, `y` = centro em px; `espaco_em` força um vão fixo (padrão: o espaço real da fonte).

    Devolve (RGBA largura×altura, info) com 'palavras' [{'texto','x0','x1','y0','y1'}], 'tamanho', 'tamanho_pedido',
    'encolheu', 'linha_base' e os demais campos de compor_legenda ('caixa', 'bbox', 'zona', 'dentro_da_zona')."""
    return compor_legenda(palavras, estilos, d, largura, altura, plataforma=plataforma, x=x, y=y, max_linhas=1,
                          largura_max=largura_max, formato=formato, espaco_em=espaco_em)


def credito_fonte(d: "da.DA", texto_credito: str, largura: int, altura: int, plataforma: str | None = None,
                  formato: str | None = None, prefixo: str | None = None, posicao: str | None = None, max_linhas: int = 2,
                  recortar: bool = False, reservar_legenda: bool | None = None) -> tuple[Image.Image, dict]:
    """Crédito de fonte ("Fonte: IBGE, 2024") conforme graficos.citacao_fonte — a mesma peça de ctx.kit.credito no motor:
    papel, tamanho, cor, prefixo (graficos.citacao_fonte.prefixo; não duplica se o texto já começa por ele) e as 7
    posições do esquema, sempre dentro da zona segura da plataforma e FORA da faixa da legenda quando a peça leva
    legenda queimada (d.area_livre; `reservar_legenda` True/False força, None segue legenda.reservar_em da DA).

    Devolve (RGBA do quadro largura×altura — ou só o recorte com recortar=True —, info) com info['x'], info['y'] (canto
    do recorte no quadro), info['caixa'] (x0, y0, x1, y1), info['texto'], info['posicao'], info['zona']."""
    cf = d["graficos"]["citacao_fonte"]
    if plataforma == "quadro":
        zona = zona_da_legenda(d, largura, altura, plataforma, formato)
    else:
        zona = d.area_livre(_formato_do_quadro(largura, altura, formato), plataforma, largura=largura, altura=altura, legenda=reservar_legenda)
    pos = posicao or cf["posicao"]
    pre = cf.get("prefixo", "Fonte: ") if prefixo is None else prefixo
    bruto = str(texto_credito or "").strip()
    completo = pre + bruto if pre and not bruto.lower().startswith(pre.strip().lower()) else bruto
    alin = "direita" if pos.endswith("direita") else "centro" if pos.endswith("centro") else "esquerda"
    est = Estilo.do_papel(d, cf["papel"], d.px(cf["tamanho"], largura, altura), cor=cf.get("cor", "texto_suave"), alinhamento=alin)
    img, inf = desenhar(completo, est, largura_max=zona["largura"], max_linhas=max_linhas, minimo=est.tamanho * 0.8)
    x = zona["x0"] if alin == "esquerda" else zona["x1"] - img.width if alin == "direita" else zona["x0"] + (zona["largura"] - img.width) // 2
    y = zona["y0"] if pos.startswith("superior") else zona["y1"] - img.height if pos.startswith("inferior") else zona["y0"] + (zona["altura"] - img.height) // 2
    info = {"x": int(x), "y": int(y), "caixa": (int(x), int(y), int(x) + img.width, int(y) + img.height), "texto": completo, "posicao": pos,
            "zona": zona, "linhas": inf["linhas"], "tamanho": inf["tamanho"]}
    if recortar:
        return img, info
    quadro = Image.new("RGBA", (int(largura), int(altura)), (0, 0, 0, 0))
    quadro.alpha_composite(img, (int(x), int(y)))
    return quadro, info


def colar(destino: Image.Image, camada: Image.Image, x: int, y: int, ancora: str = "esquerda_topo") -> tuple[int, int]:
    """Cola uma camada RGBA em destino; (x, y) é o ponto da camada indicado por `ancora`. Devolve (x0, y0) do canto.

    ancora = '<x>_<y>' com x em esquerda|centro|direita e y em topo|centro|base ('esquerda_topo', 'centro_base',
    'direita_centro'…). Atalhos: 'centro' = 'centro_centro' (centra nos DOIS eixos); 'esquerda'/'direita' sozinhos
    valem com o topo; 'topo'/'base' sozinhos valem com a esquerda."""
    partes = str(ancora).split("_")
    if partes == ["centro"]:
        ax, ay = "centro", "centro"
    elif len(partes) == 1 and partes[0] in ANCORAS_Y:
        ax, ay = "esquerda", partes[0]
    else:
        ax, ay = (partes + ["topo"])[:2]
    if len(partes) > 2 or ax not in ANCORAS_X or ay not in ANCORAS_Y:
        raise da.DAErro(f"colar: âncora {ancora!r} inválida; use <x>_<y> com x em {'|'.join(ANCORAS_X)} e y em {'|'.join(ANCORAS_Y)} "
                        f"(ex.: 'centro_base'); 'centro' sozinho centra nos dois eixos.")
    x0 = x - (camada.width // 2 if ax == "centro" else camada.width if ax == "direita" else 0)
    y0 = y - (camada.height // 2 if ay == "centro" else camada.height if ay == "base" else 0)
    destino.alpha_composite(camada, (int(x0), int(y0)))
    return int(x0), int(y0)


if __name__ == "__main__":
    print(__doc__)
