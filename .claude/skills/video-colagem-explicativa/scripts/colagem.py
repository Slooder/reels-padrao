#!/usr/bin/env python3
"""Ferramentas de imagem da colagem explicativa (papel cinza reciclado + recortes).

uso (da raiz do projeto):
  audio/.venv/bin/python tools/colagem.py papel   videos/<nn>/img/papel.jpg [--cor 219,219,219] [--w 1400 --h 2400]
      → papel reciclado cinza-claro: manchas suaves, grão fino, fibras curtas escuras e claras, pintinhas.
        Sai maior que a tela (1400×2400) para a lib sortear deslocamentos (o papel "ferve").
  audio/.venv/bin/python tools/colagem.py adesivo videos/<nn>/img/x_cut.png videos/<nn>/img/x_pb.png --largura 900 [--borda 9] [--cor]
      → foto recortada (PNG com alfa) em P&B contrastado, no tamanho de uso, com BORDA BRANCA GROSSA
        assada no PNG (contorno arredondado, sem halo). --cor mantém as cores (só a borda).
  audio/.venv/bin/python tools/colagem.py pb videos/<nn>/img/x_cut.png videos/<nn>/img/x_pb.png --largura 820 [--desbota .14]
      → P&B SEM borda, com a base desbotando (foto dentro de uma mancha de tinta).
  audio/.venv/bin/python tools/colagem.py tamanho videos/<nn>/img/x_cut.png videos/<nn>/img/x_s.png --largura 1200
      → só reduz (foto colorida recortada SEM borda: prédios, montes, cidade).
"""
import argparse
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps


def papel(a):
    W, H = a.w, a.h; r = np.random.default_rng(a.seed)
    base = np.array(tuple(map(int, a.cor.split(','))), float)
    def ruido(escala, amp):
        n = r.normal(0, 1, (max(2, H // escala), max(2, W // escala)))
        im = Image.fromarray(((n * 40) + 128).clip(0, 255).astype('uint8')).resize((W, H), Image.BICUBIC)
        return (np.asarray(im, float) - 128) / 40 * amp
    lum = ruido(90, 2.2) + ruido(18, 1.6) + ruido(3, 1.4) + r.normal(0, 1, (H, W)) * 1.3
    img = base[None, None, :] + lum[..., None]
    im = Image.fromarray(img.clip(0, 255).astype('uint8')).convert('RGBA')
    camada = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(camada)
    for _ in range(int(W * H / 900)):          # fibras curtas e curvas
        x, y = r.uniform(0, W), r.uniform(0, H); ang = r.uniform(0, 6.283); L = r.uniform(5, 22); curva = r.uniform(-.25, .25)
        pts = []
        for k in range(6):
            u = k / 5; aa = ang + curva * u * 3
            pts.append((x + np.cos(aa) * L * u, y + np.sin(aa) * L * u))
        c = 255 if r.random() < .35 else int(r.uniform(90, 140))
        d.line(pts, fill=(c, c, c, int(r.uniform(14, 40))), width=1)
    for _ in range(int(W * H / 5000)):         # pintinhas escuras
        x, y = r.uniform(0, W), r.uniform(0, H); s = r.uniform(.6, 1.6); c = int(r.uniform(110, 160))
        d.ellipse([x - s, y - s, x + s, y + s], fill=(c, c, c, int(r.uniform(30, 80))))
    camada = camada.filter(ImageFilter.GaussianBlur(.35))
    im = Image.alpha_composite(im, camada).convert('RGB')
    im.save(a.saida, quality=92); print(a.saida, im.size)


def reduzir(im, largura):
    if im.width > largura:
        im = im.resize((largura, round(im.height * largura / im.width)), Image.LANCZOS)
    return im


def adesivo(a):
    im = Image.open(a.entrada).convert('RGBA')
    im = reduzir(im, a.largura - 2 * a.borda)
    rgb, al = im.convert('RGB'), im.getchannel('A')
    if not a.cor:   # P&B contrastado, como as fotos de pessoas da referência
        g = ImageOps.grayscale(rgb); g = ImageOps.autocontrast(g, cutoff=1)
        arr = np.asarray(g, float) / 255; arr = np.clip((arr - .5) * 1.12 + .52, 0, 1) ** 1.05
        rgb = Image.fromarray((arr * 255).astype('uint8')).convert('RGB')
    B = a.borda; W, H = im.width + 2 * B, im.height + 2 * B
    alfa = Image.new('L', (W, H), 0); alfa.paste(al, (B, B))
    alfa = alfa.point(lambda v: 255 if v > 110 else 0)
    # borda: dilata o alfa com um disco (MaxFilter quadrado + desfoque/limiar arredonda os cantos)
    borda = alfa.filter(ImageFilter.MaxFilter(2 * (B // 2) + 1)).filter(ImageFilter.MaxFilter(2 * (B - B // 2) + 1))
    borda = borda.filter(ImageFilter.GaussianBlur(B * .45)).point(lambda v: 255 if v > 70 else 0).filter(ImageFilter.GaussianBlur(.7))
    out = Image.new('RGBA', (W, H), (255, 255, 255, 0)); out.putalpha(borda)
    foto = Image.new('RGBA', (W, H), (0, 0, 0, 0)); foto.paste(rgb.convert('RGBA'), (B, B), al.point(lambda v: 255 if v > 110 else 0))
    branco = Image.new('RGBA', (W, H), (250, 250, 248, 255)); branco.putalpha(borda)
    out = Image.alpha_composite(branco, foto)
    out.save(a.saida, optimize=True); print(a.saida, out.size)


def pb(a):
    """P&B sem borda, base desbotando (foto dentro de mancha de tinta, como os técnicos da referência)."""
    im = reduzir(Image.open(a.entrada).convert('RGBA'), a.largura)
    al = np.asarray(im.getchannel('A'), float)
    g = ImageOps.autocontrast(ImageOps.grayscale(im.convert('RGB')), cutoff=1)
    arr = np.clip((np.asarray(g, float) / 255 - .5) * 1.1 + .53, 0, 1)
    H = im.height; ys = np.arange(H)[:, None] / H
    fade = np.clip((1 - ys) / max(a.desbota, 1e-3), 0, 1) if a.desbota > 0 else 1
    out = Image.fromarray((arr * 255).astype('uint8')).convert('RGBA')
    out.putalpha(Image.fromarray((al * fade).clip(0, 255).astype('uint8')))
    out.save(a.saida, optimize=True); print(a.saida, out.size)


def tamanho(a):
    im = reduzir(Image.open(a.entrada).convert('RGBA'), a.largura); im.save(a.saida, optimize=True); print(a.saida, im.size)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('tipo', choices=['papel', 'adesivo', 'pb', 'tamanho']); ap.add_argument('entrada'); ap.add_argument('saida', nargs='?')
    ap.add_argument('--desbota', type=float, default=.14)
    ap.add_argument('--cor', nargs='?', const='1', default=None); ap.add_argument('--w', type=int, default=1400); ap.add_argument('--h', type=int, default=2400)
    ap.add_argument('--seed', type=int, default=7); ap.add_argument('--largura', type=int, default=900); ap.add_argument('--borda', type=int, default=9)
    a = ap.parse_args()
    if a.tipo == 'papel':
        a.saida = a.entrada; a.cor = a.cor if a.cor and ',' in a.cor else '219,219,219'; papel(a)
    elif a.tipo == 'adesivo':
        a.cor = bool(a.cor); adesivo(a)
    elif a.tipo == 'pb':
        pb(a)
    else:
        tamanho(a)
