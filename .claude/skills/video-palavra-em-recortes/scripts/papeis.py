#!/usr/bin/env python3
"""Texturas de papel para a montagem "palavra em recortes" (determinísticas, sem download).

Cada material sai em lib/papeis/<nome>.jpg com 760×1160 px; a página usa em 2× (1520×2320), o que
cobre o quadro 9:16 com zoom ≥ 1 e giro de até ~10°. Grão em 2 px de tela = papel, não ruído digital.

uso (da raiz do projeto):
  audio/.venv/bin/python tools/papeis.py                 → gera todos em lib/papeis/
  audio/.venv/bin/python tools/papeis.py kraft livro     → só os citados
  audio/.venv/bin/python tools/papeis.py --folha previews/papeis.jpg   → folha com todos (para conferir)
  audio/.venv/bin/python tools/papeis.py novo meu_papel --cor 210,190,150 [--fibras 900 --manchas 6 --amassado 3 --grao 6]
      → material novo (aparece em lib/papeis/meu_papel.jpg; registre em RC.MATERIAIS)
"""
import argparse, os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

W, H = 760, 1160
OUT = os.path.join('lib', 'papeis')

# nome: cor base, grão, nuvens (manchas suaves), fibras, manchas (foxing), amassado (vincos), extras
MATERIAIS = {
    'creme':   dict(cor=(226, 213, 186), grao=5, nuvens=4, fibras=1400, manchas=2, amassado=3),
    'jornal':  dict(cor=(214, 209, 196), grao=7, nuvens=3, fibras=2600, manchas=0, amassado=2, pontos=True),
    'revista': dict(cor=(246, 244, 239), grao=1.5, nuvens=1, fibras=0, manchas=0, amassado=0, brilho=True),
    'caderno': dict(cor=(250, 249, 243), grao=2.5, nuvens=1.5, fibras=300, manchas=0, amassado=1),
    'maquina': dict(cor=(239, 233, 220), grao=4, nuvens=3, fibras=900, manchas=1, amassado=1, respingos=True),
    'kraft':   dict(cor=(184, 142, 96), grao=9, nuvens=8, fibras=5200, manchas=0, amassado=4),
    'livro':   dict(cor=(232, 216, 180), grao=5, nuvens=6, fibras=1200, manchas=14, amassado=0, bordas=True),
    'escuro':  dict(cor=(30, 29, 28), grao=6, nuvens=4, fibras=1800, manchas=0, amassado=2, claro=True),
    'recibo':  dict(cor=(244, 241, 234), grao=2.5, nuvens=1.5, fibras=0, manchas=0, amassado=2, termico=True),
    'postit':  dict(cor=(255, 228, 104), grao=3, nuvens=3, fibras=200, manchas=0, amassado=0, degrade=True),
    'rosa':    dict(cor=(242, 196, 190), grao=6, nuvens=3, fibras=1500, manchas=0, amassado=1, pintas=True),
}


def ruido(r, esc):
    """ruído suave: normal em baixa resolução ampliado"""
    n = r.normal(0, 1, (max(2, H // esc), max(2, W // esc)))
    im = Image.fromarray(((n * 40) + 128).clip(0, 255).astype('uint8')).resize((W, H), Image.BICUBIC)
    return (np.asarray(im, float) - 128) / 40


def gerar(nome, p, seed=None):
    r = np.random.default_rng(seed if seed is not None else sum(map(ord, nome)) * 97)
    img = np.zeros((H, W, 3)); img[:] = p['cor']
    luz = 1 if not p.get('claro') else -1
    img += (ruido(r, 140) * p['nuvens'] + ruido(r, 36) * p['nuvens'] * .3)[..., None]
    img += r.normal(0, 1, (H, W))[..., None] * p['grao']
    if p.get('degrade'):
        y = np.linspace(0, 1, H)[:, None, None]; img *= 1 - .07 * y
    if p.get('brilho'):  # brilho diagonal de papel couché
        yy, xx = np.mgrid[0:H, 0:W]; u = (xx * .6 + yy * .4) / (W * .6 + H * .4)
        img += (np.exp(-((u - .42) / .12) ** 2) * 10)[..., None]
    if p.get('termico'):  # faixas cinzentas de papel térmico
        img -= (ruido(r, 220) * 3)[..., None]
    if p.get('bordas'):  # papel de livro amarelando nas bordas
        yy, xx = np.mgrid[0:H, 0:W]; d = np.minimum(np.minimum(xx, W - xx) / W, np.minimum(yy, H - yy) / H)
        img -= (np.clip(.12 - d, 0, 1) / .12 * 30)[..., None] * np.array([.6, .8, 1.2])
    im = Image.fromarray(img.clip(0, 255).astype('uint8'))
    d = ImageDraw.Draw(im, 'RGBA')
    for _ in range(p['fibras']):  # fibras curtas claras e escuras
        x, y = r.uniform(0, W), r.uniform(0, H); a = r.uniform(0, 6.283); L = r.uniform(3, 14)
        c = 255 if r.random() < .5 else 0
        d.line([(x, y), (x + np.cos(a) * L, y + np.sin(a) * L)], fill=(c, c, c, int(r.uniform(6, 26 if nome == 'kraft' else 18))), width=1)
    if p.get('pontos'):  # pontinhos escuros de papel jornal reciclado
        for _ in range(900):
            x, y = r.uniform(0, W), r.uniform(0, H); s = r.uniform(.4, 1.3)
            d.ellipse([x - s, y - s, x + s, y + s], fill=(40, 35, 30, int(r.uniform(30, 90))))
    if p.get('pintas'):  # pintas coloridas de papel reciclado
        for _ in range(500):
            x, y = r.uniform(0, W), r.uniform(0, H); s = r.uniform(.4, 1.2); c = [(60, 90, 160), (200, 60, 80), (40, 40, 40)][int(r.uniform(0, 3))]
            d.ellipse([x - s, y - s, x + s, y + s], fill=c + (int(r.uniform(50, 120)),))
    if p.get('respingos'):  # sujeirinhas de tinta de máquina
        for _ in range(140):
            x, y = r.uniform(0, W), r.uniform(0, H); s = r.uniform(.3, 1.0)
            d.ellipse([x - s, y - s, x + s, y + s], fill=(25, 25, 25, int(r.uniform(40, 110))))
    for _ in range(p['manchas']):  # manchas de envelhecimento (foxing)
        x, y = r.uniform(0, W), r.uniform(0, H); s = r.uniform(3, 14)
        lay = Image.new('L', (W, H), 0); ImageDraw.Draw(lay).ellipse([x - s, y - s * r.uniform(.6, 1.2), x + s, y + s], fill=int(r.uniform(50, 110)))
        lay = lay.filter(ImageFilter.GaussianBlur(s * .5)); im = Image.composite(Image.new('RGB', (W, H), (150, 105, 50)), im, lay)
    if p['amassado']:  # vincos: linha escura + linha clara deslocada (relevo)
        lay = Image.new('RGBA', (W, H), (0, 0, 0, 0)); dl = ImageDraw.Draw(lay)
        for _ in range(p['amassado']):
            pts = []; x, y = r.uniform(-50, W + 50), r.uniform(-50, 0) if r.random() < .5 else r.uniform(0, H)
            a = r.uniform(0, 6.283)
            for k in range(14):
                pts.append((x, y)); a += r.normal(0, .18); x += np.cos(a) * 90; y += np.sin(a) * 90
            dl.line(pts, fill=(0, 0, 0, 34 if luz > 0 else 60), width=2)
            dl.line([(px + 1.5, py + 1.5) for px, py in pts], fill=(255, 255, 255, 60 if luz > 0 else 22), width=2)
        im = Image.alpha_composite(im.convert('RGBA'), lay.filter(ImageFilter.GaussianBlur(1.1))).convert('RGB')
    os.makedirs(OUT, exist_ok=True)
    caminho = os.path.join(OUT, nome + '.jpg'); im.save(caminho, quality=86)
    return caminho


def folha(saida):
    nomes = sorted(f[:-4] for f in os.listdir(OUT) if f.endswith('.jpg'))
    tw, th = 190, 290; S = Image.new('RGB', (tw * len(nomes), th + 24), '#111'); d = ImageDraw.Draw(S)
    for i, n in enumerate(nomes):
        S.paste(Image.open(os.path.join(OUT, n + '.jpg')).resize((tw, th)), (i * tw, 0)); d.text((i * tw + 6, th + 6), n, fill='#ff0')
    S.save(saida, quality=88); print(saida)


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'novo':
        ap = argparse.ArgumentParser(); ap.add_argument('cmd'); ap.add_argument('nome'); ap.add_argument('--cor', default='220,210,190')
        ap.add_argument('--grao', type=float, default=5); ap.add_argument('--nuvens', type=float, default=8); ap.add_argument('--fibras', type=int, default=1200)
        ap.add_argument('--manchas', type=int, default=0); ap.add_argument('--amassado', type=int, default=2)
        a = ap.parse_args()
        print(gerar(a.nome, dict(cor=tuple(map(int, a.cor.split(','))), grao=a.grao, nuvens=a.nuvens, fibras=a.fibras, manchas=a.manchas, amassado=a.amassado)))
        sys.exit()
    ap = argparse.ArgumentParser(); ap.add_argument('nomes', nargs='*'); ap.add_argument('--folha')
    a = ap.parse_args()
    for n in (a.nomes or MATERIAIS):
        print(gerar(n, MATERIAIS[n]))
    if a.folha: folha(a.folha)
