#!/usr/bin/env python3
"""Ferramentas do estilo texto-grifado: recorte P&B com contorno de cor liso e papel-reboco quase branco.

uso (da raiz do projeto):
  audio/.venv/bin/python -I tools/grifado.py recorte img/foto.jpg img/foto_gr.png --largura 1000
      [--poli "x,y x,y x,y …"]...   polígono(s) em px da foto ORIGINAL somados à máscara do Vision
                                     (o Vision perde papel branco, cabos, objetos segurados na mão)
      [--caixa x0,y0,x1,y1]          recorta a foto (px da original) depois da máscara — enquadra o assunto
      [--sangra b|lb|rb|…]           bordas por onde o assunto VAZA da tela: ali não nasce contorno
      [--px 14] [--cor f3c069]       espessura (px na saída) e cor do contorno
      [--contraste 1.35] [--gama .95] [--grao 6] [--nitidez .9]
      → PNG com a foto em P&B de alto contraste e, por trás, o contorno amarelo liso que segue a silhueta.
        Grava também <saida>.json com a margem somada (px) e a escala, para alinhar a peça na página.
  audio/.venv/bin/python -I tools/grifado.py papel img/papel.jpg [--w 2700 --h 2300] [--seed 4]
      → papel-reboco quase branco (#fcfcfc) com manchas fracas, pontinhos e rachaduras finas.

O contorno é a distância até o objeto ≤ px, depois desfocado e limiarizado de novo: sai liso e com
cantos arredondados, como o traço de contorno de um app de design (e não "tesoura", que é outro estilo).
"""
import argparse, json, os, subprocess, sys, tempfile
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi

AQUI = os.path.dirname(os.path.abspath(__file__))


def hexrgb(h):
    h = h.lstrip('#'); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def mascara_vision(foto):
    exe = os.path.join(AQUI, 'cutout')
    if not os.path.exists(exe):
        sys.exit(f'não achei {exe} — rode o setup (compila cutout.swift; precisa de macOS 14+ e swiftc)')
    tmp = os.path.join(tempfile.mkdtemp(), 'm.png')
    r = subprocess.run([exe, foto, tmp], capture_output=True, text=True)
    if r.returncode or not os.path.exists(tmp):
        sys.exit('o Vision não achou objeto em primeiro plano: use --poli para desenhar a máscara')
    return np.asarray(Image.open(tmp).convert('RGBA').getchannel('A')).astype(np.float32) / 255


def pb(rgb, contraste=1.35, gama=.95, grao=6, nitidez=.9, seed=7):
    """HxWx3 uint8 → HxW float 0–1, P&B de alto contraste (pretos fundos, brancos ~#f0)."""
    l = (rgb[..., 0] * .3 + rgb[..., 1] * .59 + rgb[..., 2] * .11).astype(np.float32) / 255
    lo, hi = np.percentile(l, 1), np.percentile(l, 99.2)
    l = np.clip((l - lo) / max(hi - lo, 1e-3), 0, 1)
    l = np.clip(.5 + (l - .5) * contraste, 0, 1) ** gama
    if nitidez:                                          # contraste local: traço fino (papel, desenho) não some
        l = np.clip(l + nitidez * (l - ndi.gaussian_filter(l, 2.5)), 0, 1)
    l = l * .91 + .035                                   # pretos #09, brancos #ef
    if grao:
        r = np.random.default_rng(seed).normal(0, grao / 255, l.shape).astype(np.float32)
        l = l + ndi.gaussian_filter(r, .7) * 1.8
    return np.clip(l, 0, 1)


def contorno(m, px, sangra):
    """m: máscara bool → campo 0–1 do contorno liso (inclui o próprio objeto)."""
    p = int(px * 2 + 6)
    pads = ((0 if 't' in sangra else p, 0 if 'b' in sangra else p), (0 if 'l' in sangra else p, 0 if 'r' in sangra else p))
    mm = np.pad(m, pads, mode='constant')
    # nas bordas que sangram, o objeto "continua" para fora: replica a última linha/coluna
    E = p
    if 'b' in sangra: mm = np.pad(mm, ((0, E), (0, 0)), mode='edge')
    if 't' in sangra: mm = np.pad(mm, ((E, 0), (0, 0)), mode='edge')
    if 'l' in sangra: mm = np.pad(mm, ((0, 0), (E, 0)), mode='edge')
    if 'r' in sangra: mm = np.pad(mm, ((0, 0), (0, E)), mode='edge')
    d = ndi.distance_transform_edt(~mm)
    f = ndi.gaussian_filter((d <= px).astype(np.float32), px * .3)
    f = np.clip((f - .5) * 4 + .5, 0, 1)                 # limiar suave: borda lisa e antisserrilhada
    # tira o que foi replicado
    y0 = E if 't' in sangra else 0; x0 = E if 'l' in sangra else 0
    f = f[y0:y0 + m.shape[0] + pads[0][0] + pads[0][1], x0:x0 + m.shape[1] + pads[1][0] + pads[1][1]]
    return f, pads


def cmd_recorte(a):
    foto = Image.open(a.entrada).convert('RGB'); W, H = foto.size
    al = mascara_vision(a.entrada)
    if al.shape != (H, W): al = np.asarray(Image.fromarray((al * 255).astype(np.uint8)).resize((W, H))).astype(np.float32) / 255
    if a.poli:
        im = Image.new('L', (W, H), 0); d = ImageDraw.Draw(im)
        for p in a.poli:
            pts = [tuple(map(float, q.split(','))) for q in p.split()]
            d.polygon(pts, fill=255)
        al = np.maximum(al, np.asarray(im).astype(np.float32) / 255)
    rgb = np.asarray(foto)
    if a.caixa:
        x0, y0, x1, y1 = map(int, a.caixa.split(','))
        rgb = rgb[y0:y1, x0:x1]; al = al[y0:y1, x0:x1]
    s = a.largura / rgb.shape[1]
    nw, nh = a.largura, round(rgb.shape[0] * s)
    rgb = np.asarray(Image.fromarray(rgb).resize((nw, nh), Image.LANCZOS))
    al = np.asarray(Image.fromarray((al * 255).astype(np.uint8)).resize((nw, nh), Image.LANCZOS)).astype(np.float32) / 255
    al = ndi.gaussian_filter(al, 1.0); al = np.clip((al - .5) * 3 + .5, 0, 1)
    m = al > .5
    # tira ilhas pequenas (sujeira do Vision)
    lab, n = ndi.label(m)
    if n > 1:
        tam = ndi.sum(m, lab, range(1, n + 1)); keep = np.isin(lab, 1 + np.where(tam > tam.max() * .02)[0])
        al = al * keep; m = m & keep
    f, pads = contorno(m, a.px, a.sangra)
    Hh, Ww = f.shape
    out = np.zeros((Hh, Ww, 4), np.float32)
    c = np.array(hexrgb(a.cor), np.float32) / 255
    out[..., :3] = c; out[..., 3] = f
    l = pb(rgb, a.contraste, a.gama, a.grao, a.nitidez)
    alp = np.zeros((Hh, Ww), np.float32); lum = np.zeros((Hh, Ww), np.float32)
    alp[pads[0][0]:pads[0][0] + nh, pads[1][0]:pads[1][0] + nw] = al
    lum[pads[0][0]:pads[0][0] + nh, pads[1][0]:pads[1][0] + nw] = l
    out[..., :3] = out[..., :3] * (1 - alp[..., None]) + lum[..., None] * alp[..., None]
    out[..., 3] = np.maximum(out[..., 3], alp)
    Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8), 'RGBA').save(a.saida, optimize=True)
    meta = {'margem_esq': pads[1][0], 'margem_topo': pads[0][0], 'escala': s, 'w': Ww, 'h': Hh, 'foto_w': nw, 'foto_h': nh}
    json.dump(meta, open(os.path.splitext(a.saida)[0] + '.json', 'w'))
    print(f'{a.saida}: {Ww}×{Hh} (foto {nw}×{nh}, contorno {a.px}px #{a.cor}, sangra "{a.sangra}")')


def fbm(shape, escalas, rng):
    v = np.zeros(shape, np.float32); amp = 1; tot = 0
    for e in escalas:
        g = rng.random(shape).astype(np.float32); g = ndi.gaussian_filter(g, e)
        g = (g - g.mean()) / (g.std() + 1e-6); v += g * amp; tot += amp; amp *= .55
    return v / tot


def cmd_papel(a):
    rng = np.random.default_rng(a.seed); H, W = a.h, a.w
    base = np.full((H, W), 252.5, np.float32)
    # manchas (reboco): só a parte escura do ruído, bem fraca
    v = fbm((H, W), (90, 34, 12), rng)
    base -= np.clip(v - .35, 0, None) * 5.5
    # nuvens de pontinhos: densidade modulada por outro ruído
    dens = np.clip(fbm((H // 4, W // 4), (20, 8), rng) - .2, 0, None)
    dens = np.asarray(Image.fromarray(dens).resize((W, H), Image.BILINEAR))
    pts = rng.random((H, W)).astype(np.float32) < dens * .035
    pont = ndi.gaussian_filter(pts.astype(np.float32), .7) * 60
    base -= pont
    # rachaduras finas (passeio aleatório com falhas)
    im = Image.new('L', (W, H), 0); d = ImageDraw.Draw(im)
    for _ in range(a.rachaduras):
        x, y = rng.random() * W, rng.random() * H; ang = rng.random() * np.pi * 2
        for i in range(int(60 + rng.random() * 120)):
            ang += rng.normal(0, .35); nx, ny = x + np.cos(ang) * 6, y + np.sin(ang) * 6
            if rng.random() > .12: d.line([(x, y), (nx, ny)], fill=int(90 + rng.random() * 120), width=1)
            x, y = nx, ny
    rach = ndi.gaussian_filter(np.asarray(im).astype(np.float32), .5) / 255 * 26
    base -= rach
    # grão fino
    base += rng.normal(0, .9, (H, W)).astype(np.float32)
    img = np.clip(base, 0, 255).astype(np.uint8)
    Image.fromarray(np.dstack([img, img, img])).save(a.saida, quality=90)
    print(f'{a.saida}: {W}×{H}  p1/p5/p50 = {np.percentile(img, 1):.0f}/{np.percentile(img, 5):.0f}/{np.percentile(img, 50):.0f}  (ref: 243/247/252)')


def main():
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest='cmd', required=True)
    r = sp.add_parser('recorte'); r.add_argument('entrada'); r.add_argument('saida')
    r.add_argument('--largura', type=int, default=1000); r.add_argument('--poli', action='append')
    r.add_argument('--caixa'); r.add_argument('--sangra', default='b')
    r.add_argument('--px', type=float, default=14); r.add_argument('--cor', default='f3c069')
    r.add_argument('--contraste', type=float, default=1.35); r.add_argument('--gama', type=float, default=.95)
    r.add_argument('--grao', type=float, default=6); r.add_argument('--nitidez', type=float, default=.9)
    p = sp.add_parser('papel'); p.add_argument('saida'); p.add_argument('--w', type=int, default=2700)
    p.add_argument('--h', type=int, default=2300); p.add_argument('--seed', type=int, default=4)
    p.add_argument('--rachaduras', type=int, default=5)
    a = ap.parse_args()
    {'recorte': cmd_recorte, 'papel': cmd_papel}[a.cmd](a)


if __name__ == '__main__':
    main()
