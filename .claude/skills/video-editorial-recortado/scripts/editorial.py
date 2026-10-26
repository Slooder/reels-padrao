#!/usr/bin/env python3
"""Recorte editorial: foto P&B de alto contraste + borda colorida cortada a tesoura.

uso (da raiz do projeto):
  audio/.venv/bin/python tools/editorial.py recorte img/predio_cut.png img/predio_ed.png [--px 16] [--cor 5b7ba3]
      [--eps .45] [--var .5] [--seed 3] [--contraste 1.45] [--gama .92] [--grao 10] [--max 1400 | --largura 1100]
      → PNG com a foto em P&B e, por trás, a borda de papel azul com segmentos retos e espessura irregular.
        Grava também <saida>.json com a margem (px) somada em volta, para alinhar a peça na página.
  audio/.venv/bin/python tools/editorial.py pb img/foto.jpg img/foto_pb.jpg [--contraste 1.45]
      → só o tratamento P&B (com ou sem alfa).
  audio/.venv/bin/python tools/editorial.py papel img/papel.jpg [--w 1240 --h 2204] [--cor f5f5f3]
      → fundo de papel/reboco quase branco com nuvens de pontinhos cinza (114,8% do quadro 9:16, folga p/ câmera).

Como a borda é feita: distância até o objeto ≤ px·(1−var/2 … 1+var/2) (ruído suave = espessura que varia),
fecha buracos, traça o contorno externo de cada pedaço e simplifica (Douglas-Peucker, eps = px·eps):
o resultado são cortes retos e cantos vivos, como papel recortado à tesoura.
"""
import argparse, json, os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageOps
from scipy import ndimage as ndi

# ---------- P&B ----------
def pb(rgb, contraste=1.45, gama=.92, grao=10, seed=7):
    """rgb: array HxWx3 uint8 → L uint8 de alto contraste, com grão de impressão."""
    l = (rgb[..., 0] * .3 + rgb[..., 1] * .59 + rgb[..., 2] * .11).astype(np.float32) / 255
    lo, hi = np.percentile(l, 1.5), np.percentile(l, 98.5)
    l = np.clip((l - lo) / max(hi - lo, 1e-3), 0, 1)
    l = np.clip(.5 + (l - .5) * contraste, 0, 1) ** gama
    l = l * .84 + .045                                 # pretos #0b, brancos #e1 (foto impressa: nunca some no papel)
    if grao:
        r = np.random.default_rng(seed).normal(0, grao / 255, l.shape).astype(np.float32)
        l = l + ndi.gaussian_filter(r, .6) * 1.6
    return (np.clip(l, 0, 1) * 255).astype(np.uint8)

# ---------- contorno + simplificação ----------
DIRS = [(0, -1), (-1, -1), (-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1)]  # (dy,dx) em sentido horário, começando no oeste

def contorno(m):
    """Contorno externo (Moore) de uma máscara booleana de um pedaço só, sem buracos. → lista [(x,y)]."""
    H, W = m.shape
    ys, xs = np.nonzero(m)
    i = np.argmin(ys * W + xs); y0, x0 = int(ys[i]), int(xs[i])
    pts = [(x0, y0)]; cy, cx = y0, x0; b = 0
    for _ in range(4 * m.sum() + 10):
        for k in range(8):
            d = (b + k) % 8; ny, nx = cy + DIRS[d][0], cx + DIRS[d][1]
            if 0 <= ny < H and 0 <= nx < W and m[ny, nx]:
                p = (b + k - 1) % 8; py, px = cy + DIRS[p][0], cx + DIRS[p][1]
                cy, cx = ny, nx; b = DIRS.index((py - cy, px - cx)); break
        else:
            break
        if (cy, cx) == (y0, x0): break
        pts.append((cx, cy))
    return pts

def rdp(p, eps):
    """Douglas-Peucker numa polilinha aberta (array Nx2)."""
    if len(p) < 3: return p
    a, b = p[0], p[-1]; ab = b - a; n = np.hypot(*ab)
    q = p - a
    d = np.abs(ab[0] * q[:, 1] - ab[1] * q[:, 0]) / n if n > 1e-9 else np.hypot(q[:, 0], q[:, 1])
    i = int(np.argmax(d))
    if d[i] > eps:
        return np.vstack([rdp(p[:i + 1], eps)[:-1], rdp(p[i:], eps)])
    return np.vstack([a, b])

def poligono(pts, eps):
    p = np.array(pts, float)
    far = int(np.argmax(np.hypot(*(p - p[0]).T)))       # fecha o laço partindo no ponto mais distante
    return np.vstack([rdp(p[:far + 1], eps)[:-1], rdp(np.vstack([p[far:], p[:1]]), eps)[:-1]])

def ruido_suave(shape, escala, seed):
    g = np.random.default_rng(seed).random(shape).astype(np.float32)
    g = ndi.gaussian_filter(g, escala)
    return (g - g.min()) / max(np.ptp(g), 1e-6)

def borda(alpha, px=16, eps=.45, var=.5, seed=3, reduz=2):
    """alpha: HxW uint8 → máscara (HxW bool) do papel recortado em volta do objeto."""
    H, W = alpha.shape
    m = alpha[::reduz, ::reduz] > 110
    r = px / reduz
    dist = ndi.distance_transform_edt(~m)
    esp = r * (1 - var / 2 + var * ruido_suave(m.shape, max(6, 9 * r), seed))
    d = ndi.binary_fill_holes(dist <= esp)
    lab, n = ndi.label(d)
    img = Image.new('L', (W, H), 0); dr = ImageDraw.Draw(img)
    rng = np.random.default_rng(seed + 1)
    for k in range(1, n + 1):
        comp = lab == k
        if comp.sum() < 30: continue
        poly = poligono(contorno(comp), max(1.0, r * eps))
        poly = poly * reduz + rng.uniform(-.25, .25, poly.shape) * px * .25   # tesoura não é régua
        dr.polygon([tuple(map(float, q)) for q in poly], fill=255)
    return np.array(img) > 127

# ---------- papel ----------
def papel(w, h, cor=(245, 245, 243), seed=11):
    """Papel/reboco quase branco com nuvens de pontinhos cinza (fotocópia de parede) e manchas muito suaves."""
    rng = np.random.default_rng(seed)
    base = np.ones((h, w), np.float32)
    nuvem = ruido_suave((h // 4, w // 4), 10, seed)                       # onde os pontinhos se juntam
    nuvem = np.array(Image.fromarray((nuvem * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC), np.float32) / 255
    dens = np.clip((nuvem - .45) * 2.2, 0, 1) ** 1.4 * .085 + .003
    pts = (rng.random((h, w)) < dens).astype(np.float32) * rng.uniform(.06, .22, (h, w)).astype(np.float32)
    pts = ndi.gaussian_filter(pts, .7) * 2.2                                  # pontinho com 1–3 px, borda macia
    mancha = ndi.gaussian_filter(rng.random((h // 8, w // 8)).astype(np.float32), 6)
    mancha = np.array(Image.fromarray(((mancha - mancha.min()) / np.ptp(mancha) * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC), np.float32) / 255
    fibra = ndi.gaussian_filter(rng.normal(0, 1, (h, w)).astype(np.float32), .8) * .006
    l = base - np.clip(pts, 0, .35) - np.clip(mancha - .62, 0, 1) * .06 + fibra
    rgb = np.stack([np.clip(l * c, 0, 255) for c in cor], -1).astype(np.uint8)
    return Image.fromarray(rgb)

# ---------- comandos ----------
def cmd_recorte(a):
    im = Image.open(a.entrada).convert('RGBA')
    if a.largura: im = im.resize((a.largura, round(im.height * a.largura / im.width)), Image.LANCZOS)
    elif a.max and im.width > a.max: im = im.resize((a.max, round(im.height * a.max / im.width)), Image.LANCZOS)
    pad = int(a.px * 1.8) + 4
    big = Image.new('RGBA', (im.width + 2 * pad, im.height + 2 * pad), (0, 0, 0, 0)); big.paste(im, (pad, pad))
    arr = np.array(big); al = arr[..., 3]
    mask = borda(al, a.px, a.eps, a.var, a.seed)
    cor = tuple(int(a.cor.lstrip('#')[i:i + 2], 16) for i in (0, 2, 4))
    out = np.zeros_like(arr)
    out[mask] = (*cor, 255)
    l = pb(arr[..., :3], a.contraste, a.gama, a.grao, a.seed)
    f = al.astype(np.float32)[..., None] / 255
    foto = np.dstack([l, l, l]).astype(np.float32)
    out[..., :3] = (foto * f + out[..., :3].astype(np.float32) * (1 - f)).astype(np.uint8)
    out[..., 3] = np.maximum(out[..., 3], al)
    # corta a sobra transparente, mas guarda a margem
    ys, xs = np.nonzero(out[..., 3] > 0)
    x0, y0, x1, y1 = xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
    Image.fromarray(out[y0:y1, x0:x1]).save(a.saida, optimize=True)
    meta = {'fonte': os.path.basename(a.entrada), 'w': int(x1 - x0), 'h': int(y1 - y0),
            'foto_x': int(pad - x0), 'foto_y': int(pad - y0), 'foto_w': im.width, 'foto_h': im.height, 'px': a.px}
    json.dump(meta, open(os.path.splitext(a.saida)[0] + '.json', 'w'), indent=1)
    print(f"{a.saida}: {meta['w']}×{meta['h']} · foto em ({meta['foto_x']},{meta['foto_y']}) {im.width}×{im.height}")

def cmd_pb(a):
    im = Image.open(a.entrada); arr = np.array(im.convert('RGBA'))
    l = pb(arr[..., :3], a.contraste, a.gama, a.grao)
    if im.mode in ('RGBA', 'LA', 'P'):
        Image.fromarray(np.dstack([l, l, l, arr[..., 3]])).save(a.saida)
    else:
        Image.fromarray(l).save(a.saida, quality=90)
    print(a.saida)

def cmd_papel(a):
    cor = tuple(int(a.cor.lstrip('#')[i:i + 2], 16) for i in (0, 2, 4))
    papel(a.w, a.h, cor, a.seed).save(a.saida, quality=88); print(a.saida, f'{a.w}×{a.h}')

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='cmd', required=True)
    r = sp.add_parser('recorte'); r.add_argument('entrada'); r.add_argument('saida')
    r.add_argument('--px', type=float, default=16, help='espessura média da borda (px na imagem final)')
    r.add_argument('--cor', default='5b7ba3'); r.add_argument('--eps', type=float, default=.45, help='quanto a tesoura "corta caminho" (× px)')
    r.add_argument('--var', type=float, default=.5, help='variação da espessura (0 = constante)')
    r.add_argument('--seed', type=int, default=3); r.add_argument('--max', type=int, default=1400)
    r.add_argument('--largura', type=int, help='largura exata da foto na página (px) — redimensiona para cima ou para baixo')
    for p in (r, sp.add_parser('pb')):
        if p is not r: p.add_argument('entrada'); p.add_argument('saida')
        p.add_argument('--contraste', type=float, default=1.45); p.add_argument('--gama', type=float, default=.92)
        p.add_argument('--grao', type=float, default=10)
    pp = sp.add_parser('papel'); pp.add_argument('saida'); pp.add_argument('--w', type=int, default=1240); pp.add_argument('--h', type=int, default=2204)
    pp.add_argument('--cor', default='f5f5f3'); pp.add_argument('--seed', type=int, default=11)
    a = ap.parse_args()
    {'recorte': cmd_recorte, 'pb': cmd_pb, 'papel': cmd_papel}[a.cmd](a)

if __name__ == '__main__':
    main()
