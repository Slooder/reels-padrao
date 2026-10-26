#!/usr/bin/env python3
"""Texturas de fundo do estilo mídia mista, já no tamanho do vídeo + folga de 14,8% (para o empurrão de câmera).

uso (da raiz do projeto):
  audio/.venv/bin/python tools/texturas.py papel   videos/<nome>/img/papel_cinza.jpg   [--w 1080 --h 1920] [--cor 226,226,223]
  audio/.venv/bin/python tools/texturas.py tecido  videos/<nome>/img/tecido_escuro.jpg [--cor 24,23,22]
  audio/.venv/bin/python tools/texturas.py mesa    videos/<nome>/img/mesa_clara.jpg    [--cor 196,201,204]
  audio/.venv/bin/python tools/texturas.py madeira videos/<nome>/img/madeira.jpg --foto img/foto_de_madeira.jpg [--girar]
      → qualquer foto de madeira vira nogueira escura e quente (o tom da referência), recortada no formato do vídeo
  audio/.venv/bin/python tools/texturas.py desfocar videos/<nome>/img/mao_cut.png videos/<nome>/img/mao_blur.png [--raio 9]
      → versão leve e desfocada de um recorte (mãos "de passagem" em primeiro plano)
  audio/.venv/bin/python tools/texturas.py reduzir  videos/<nome>/img/chip_cut.png videos/<nome>/img/chip_s.png [--max 440]
      → recorte menor para padrões e adesivos (muitas cópias na tela = arquivo leve)
"""
import argparse, numpy as np
from PIL import Image, ImageDraw, ImageFilter

def tam(a): return round(a.w * 1.148), round(a.h * 1.148)

def papel(a, base, amp, fib, seed):
    W, H = tam(a); r = np.random.default_rng(seed)
    n = r.normal(0, 1, (H // 2, W // 2)); n = np.array(Image.fromarray(((n * 40) + 128).clip(0, 255).astype('uint8')).resize((W, H), Image.BILINEAR), float) - 128
    img = np.zeros((H, W, 3)); img[:] = base; img += (n[..., None] * amp / 40) + r.normal(0, 1, (H, W))[..., None] * amp * .5
    im = Image.fromarray(img.clip(0, 255).astype('uint8')); d = ImageDraw.Draw(im, 'RGBA')
    for _ in range(fib):   # fibras curtas, claras e escuras
        x, y = r.uniform(0, W), r.uniform(0, H); ang = r.uniform(0, 6.28); L = r.uniform(6, 26); c = 255 if r.random() < .5 else 0
        d.line([(x, y), (x + np.cos(ang) * L, y + np.sin(ang) * L)], fill=(c, c, c, int(r.uniform(8, 22))), width=1)
    im.save(a.saida, quality=90); print(a.saida, im.size)

def madeira(a):
    W, H = tam(a); wd = Image.open(a.foto).convert('RGB')
    if a.girar: wd = wd.rotate(90, expand=True)
    w0, h0 = wd.size; alvo = W / H
    if w0 / h0 > alvo: cw = int(h0 * alvo); wd = wd.crop(((w0 - cw) // 2, 0, (w0 + cw) // 2, h0))
    else: ch = int(w0 / alvo); wd = wd.crop((0, (h0 - ch) // 2, w0, (h0 + ch) // 2))
    x = np.asarray(wd.resize((W, H), Image.LANCZOS), float) / 255; lum = x @ [.3, .55, .15]; lum = (lum - lum.mean()) * 1.6 + .5
    out = np.stack([lum * .62 + .06, lum * .38 + .03, lum * .22 + .015], -1)
    Image.fromarray((out.clip(0, 1) * 255).astype('uint8')).save(a.saida, quality=90); print(a.saida, (W, H))

ap = argparse.ArgumentParser(); ap.add_argument('tipo', choices=['papel', 'tecido', 'mesa', 'madeira', 'desfocar', 'reduzir']); ap.add_argument('saida'); ap.add_argument('saida2', nargs='?')
ap.add_argument('--w', type=int, default=1080); ap.add_argument('--h', type=int, default=1920); ap.add_argument('--cor'); ap.add_argument('--foto'); ap.add_argument('--girar', action='store_true')
ap.add_argument('--raio', type=float, default=9); ap.add_argument('--max', type=int, default=440)
a = ap.parse_args(); cor = tuple(map(int, a.cor.split(','))) if a.cor else None
if a.tipo == 'papel': papel(a, cor or (226, 226, 223), 7, 900, 2)
elif a.tipo == 'tecido': papel(a, cor or (24, 23, 22), 9, 2600, 3)
elif a.tipo == 'mesa': papel(a, cor or (196, 201, 204), 8, 900, 4)
elif a.tipo == 'madeira': madeira(a)
elif a.tipo == 'desfocar':
    m = Image.open(a.saida).convert('RGBA'); m.thumbnail((560, 720)); m.filter(ImageFilter.GaussianBlur(a.raio)).save(a.saida2); print(a.saida2, m.size)
elif a.tipo == 'reduzir':
    m = Image.open(a.saida).convert('RGBA'); m.thumbnail((a.max, a.max), Image.LANCZOS); m.save(a.saida2); print(a.saida2, m.size)
