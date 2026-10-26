#!/usr/bin/env python3
"""Dados de mapa para o estilo mapa-documental (tudo de domínio público).

  baixar    texturas de relevo NASA (GIBS: Blue Marble + ASTER) e vetores Natural Earth
  texturas  tinge o relevo em 3 materiais com alfa = terra: <nome>_cinza.webp, _verde.webp, _vermelho.webp
  vetores   estados/províncias, contorno do país e rios → geo.json (lon/lat simplificados)

Exemplos (da raiz do estúdio):
  audio/.venv/bin/python -I tools/mapa.py baixar fontes --bbox=-76,-36,-32,7 --ppd 64 --nome br
  audio/.venv/bin/python -I tools/mapa.py texturas fontes br videos/01-x/img --relevo
  audio/.venv/bin/python -I tools/mapa.py vetores fontes Brazil videos/01-x/geo.json --bbox=-76,-36,-32,7
  (país = nome em inglês do Natural Earth: Brazil, Portugal, Mexico, Japan…; países fora do 50m usam o 10m, baixado na hora)

A projeção da página é equirretangular (x = lon·cos(lat0), y = −lat): cada textura é uma grade lon/lat
comum, então basta desenhá-la no retângulo da sua caixa (drawImage) — não há reprojeção.
"""
import argparse, json, math, os, sys, urllib.request
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

GIBS = ('https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi?SERVICE=WMS&REQUEST=GetMap&VERSION=1.1.1'
        '&SRS=EPSG:4326&FORMAT=image/jpeg&LAYERS={L}&BBOX={b}&WIDTH={w}&HEIGHT={h}')
NE = 'https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/{}.geojson'
NE_FILES = ['ne_50m_land', 'ne_50m_lakes', 'ne_50m_admin_0_countries', 'ne_50m_admin_1_states_provinces', 'ne_10m_rivers_lake_centerlines']

# materiais medidos na referência: (sombra, meio, luz) em RGB
MAT = {
    'cinza':    [(14, 15, 14), (46, 47, 45), (98, 100, 95)],
    'verde':    [(0, 10, 5), (3, 44, 28), (24, 112, 76)],
    'vermelho': [(92, 12, 4), (192, 36, 16), (244, 98, 58)],
}
AGUA = {'cinza': (62, 66, 62), 'verde': (64, 214, 164), 'vermelho': (255, 140, 100)}


def get(url, dest):
    if os.path.exists(dest) and os.path.getsize(dest) > 1000: return
    req = urllib.request.Request(url, headers={'User-Agent': 'mapa-documental/1.0'})
    with urllib.request.urlopen(req, timeout=180) as r, open(dest, 'wb') as f: f.write(r.read())
    print('  baixado', dest, os.path.getsize(dest) // 1024, 'KB')


def caixa(s): return [float(v) for v in s.split(',')]


def baixar(a):
    os.makedirs(os.path.join(a.pasta, 'ne'), exist_ok=True); os.makedirs(os.path.join(a.pasta, 'gibs'), exist_ok=True)
    for n in NE_FILES: get(NE.format(n), os.path.join(a.pasta, 'ne', n + '.geojson'))
    if a.bbox:
        x0, y0, x1, y1 = caixa(a.bbox); w, h = round((x1 - x0) * a.ppd), round((y1 - y0) * a.ppd)
        if max(w, h) > 8000: sys.exit(f'caixa grande demais ({w}x{h}); reduza --ppd ou divida a caixa')
        b = f'{x0},{y0},{x1},{y1}'
        get(GIBS.format(L='BlueMarble_ShadedRelief', b=b, w=w, h=h), os.path.join(a.pasta, 'gibs', f'{a.nome}_bm.jpg'))
        if a.ppd >= 40: get(GIBS.format(L='ASTER_GDEM_Greyscale_Shaded_Relief', b=b, w=w, h=h), os.path.join(a.pasta, 'gibs', f'{a.nome}_as.jpg'))
        json.dump({'bbox': [x0, y0, x1, y1], 'ppd': a.ppd}, open(os.path.join(a.pasta, 'gibs', f'{a.nome}.json'), 'w'))
        print(f'{a.nome}: {w}x{h} px, caixa {b}')


def aneis(geom):
    if not geom: return []
    if geom['type'] == 'Polygon': return geom['coordinates']
    if geom['type'] == 'MultiPolygon': return [r for p in geom['coordinates'] for r in p]
    return []


def mascara_terra(pasta, bbox, W, H, ss=2):
    x0, y0, x1, y1 = bbox
    im = Image.new('L', (W * ss, H * ss), 0); d = ImageDraw.Draw(im)
    land = json.load(open(os.path.join(pasta, 'ne', 'ne_50m_land.geojson')))
    for f in land['features']:
        for g, ring in enumerate(aneis(f['geometry'])):
            xs = [((p[0] - x0) / (x1 - x0)) * W * ss for p in ring]; ys = [((y1 - p[1]) / (y1 - y0)) * H * ss for p in ring]
            if max(xs) < 0 or min(xs) > W * ss or max(ys) < 0 or min(ys) > H * ss: continue
            d.polygon(list(zip(xs, ys)), fill=255)
    lg = Image.new('L', (W * ss, H * ss), 0); dl = ImageDraw.Draw(lg)
    lakes = os.path.join(pasta, 'ne', 'ne_50m_lakes.geojson')
    if os.path.exists(lakes):
        for f in json.load(open(lakes))['features']:
            for ring in aneis(f['geometry']):
                xs = [((p[0] - x0) / (x1 - x0)) * W * ss for p in ring]; ys = [((y1 - p[1]) / (y1 - y0)) * H * ss for p in ring]
                if max(xs) < 0 or min(xs) > W * ss or max(ys) < 0 or min(ys) > H * ss: continue
                dl.polygon(list(zip(xs, ys)), fill=255)
    return (im.resize((W, H), Image.LANCZOS).filter(ImageFilter.GaussianBlur(.6)),
            lg.resize((W, H), Image.LANCZOS).filter(ImageFilter.GaussianBlur(.8)))


def rampa(v, cores):
    """v em 0..1 → cor interpolada sombra→meio→luz"""
    c = np.array(cores, float); v = np.clip(v, 0, 1)[..., None]
    lo = c[0] + (c[1] - c[0]) * np.clip(v * 2, 0, 1)
    return np.where(v < .5, lo, c[1] + (c[2] - c[1]) * np.clip(v * 2 - 1, 0, 1))


def texturas(a):
    meta = json.load(open(os.path.join(a.pasta, 'gibs', f'{a.nome}.json'))); bbox = meta['bbox']
    bm = np.asarray(Image.open(os.path.join(a.pasta, 'gibs', f'{a.nome}_bm.jpg')).convert('RGB'), float)
    H, W = bm.shape[:2]
    lum = (bm @ [.3, .59, .11]) / 255
    # contraste local (o relevo "enruga" como no satélite da referência)
    blur = np.asarray(Image.fromarray((lum * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(max(2, W / 120))), float) / 255
    det = lum - blur
    v = .5 + (lum - np.median(lum)) * 1.8 + det * 2.2
    asp = os.path.join(a.pasta, 'gibs', f'{a.nome}_as.jpg')
    if a.relevo and os.path.exists(asp):
        rel = np.asarray(Image.open(asp).convert('L'), float) / 255
        v = v + (rel - np.median(rel)) * .9
    # água (represas, rios largos): escura e azulada no Blue Marble
    agua = np.clip(((bm[..., 2] - bm[..., 0]) / 255 * 6) * (lum < .22), 0, 1) * np.clip((.22 - lum) * 12, 0, 1)
    agua = np.asarray(Image.fromarray((agua * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(.8)), float) / 255
    terra, lagos = mascara_terra(a.pasta, bbox, W, H)
    m = np.asarray(terra, float) / 255; agua = np.maximum(agua, np.asarray(lagos, float) / 255)
    if a.borda > 0:  # esfuma as bordas da caixa para a textura fina se fundir com a grossa por baixo
        bx, by = max(2, int(W * a.borda)), max(2, int(H * a.borda))
        fx = np.clip(np.minimum(np.arange(W), np.arange(W)[::-1]) / bx, 0, 1); fy = np.clip(np.minimum(np.arange(H), np.arange(H)[::-1]) / by, 0, 1)
        m = m * (fy[:, None] * fx[None, :]) ** .8
    os.makedirs(a.saida, exist_ok=True)
    for nome, cores in MAT.items():
        rgb = rampa(v, cores); rgb = rgb * (1 - agua[..., None]) + np.array(AGUA[nome]) * agua[..., None]
        out = np.dstack([np.clip(rgb, 0, 255), m * 255]).astype(np.uint8)
        p = os.path.join(a.saida, f'{a.nome}_{nome}.webp')
        Image.fromarray(out, 'RGBA').save(p, 'WEBP', quality=a.q, method=5)
        print(' ', p, f'{W}x{H}', os.path.getsize(p) // 1024, 'KB')
    # caixa para a página (lon0, lat0, lon1, lat1)
    print(f"  TEX '{a.nome}': bbox {bbox}")


def simplificar(pts, tol):
    if len(pts) < 4 or tol <= 0: return pts
    P = np.array(pts)
    if np.allclose(P[0], P[-1]):  # anel fechado: corta no ponto mais distante do início e simplifica as duas metades
        k = int(np.argmax(np.hypot(*(P - P[0]).T)))
        if 0 < k < len(P) - 1: return simplificar(pts[:k + 1], tol)[:-1] + simplificar(pts[k:], tol)
    keep = np.zeros(len(P), bool); keep[0] = keep[-1] = True; st = [(0, len(P) - 1)]
    while st:
        i, j = st.pop()
        if j <= i + 1: continue
        a, b = P[i], P[j]; ab = b - a; L = np.hypot(*ab) + 1e-12
        d = np.abs(ab[0] * (P[i + 1:j, 1] - a[1]) - ab[1] * (P[i + 1:j, 0] - a[0])) / L
        k = int(np.argmax(d))
        if d[k] > tol: keep[i + 1 + k] = True; st += [(i, i + 1 + k), (i + 1 + k, j)]
    return P[keep].tolist()


def vetores(a):
    x0, y0, x1, y1 = caixa(a.bbox) if a.bbox else (-180, -90, 180, 90)
    r3 = lambda ring: [[round(p[0], 3), round(p[1], 3)] for p in simplificar(ring, a.tol)]
    f1 = os.path.join(a.pasta, 'ne', 'ne_50m_admin_1_states_provinces.geojson')
    adm1 = json.load(open(f1))
    if a.adm1 == '10m' or not any(f['properties'].get('admin') == a.pais for f in adm1['features']):
        # o 50m só tem estados de 9 países (Brasil, EUA, Canadá, China, Índia, Rússia, Indonésia, Austrália, África do Sul)
        f1 = os.path.join(a.pasta, 'ne', 'ne_10m_admin_1_states_provinces.geojson')
        get(NE.format('ne_10m_admin_1_states_provinces'), f1); adm1 = json.load(open(f1))
    est = []
    for f in adm1['features']:
        pr = f['properties']
        if pr.get('admin') != a.pais: continue
        rs = [r3(r) for r in aneis(f['geometry'])]; rs = [r for r in rs if len(r) >= 4]
        est.append({'nome': pr['name'], 'sigla': (pr.get('postal') or pr.get('abbrev') or '').replace('.', ''),
                    'centro': [round(pr.get('longitude') or 0, 3), round(pr.get('latitude') or 0, 3)], 'aneis': rs})
    adm0 = json.load(open(os.path.join(a.pasta, 'ne', 'ne_50m_admin_0_countries.geojson')))
    pais = []
    for f in adm0['features']:
        if f['properties'].get('ADMIN') == a.pais or f['properties'].get('NAME') == a.pais:
            pais = [r3(r) for r in aneis(f['geometry']) if len(r) >= 4]
    if not est and pais:  # país sem divisões: o próprio contorno vira a única "região"
        est = [{'nome': a.pais, 'sigla': '', 'centro': [0, 0], 'aneis': pais}]
    rios = []
    rv = json.load(open(os.path.join(a.pasta, 'ne', 'ne_10m_rivers_lake_centerlines.geojson')))
    for f in rv['features']:
        g = f['geometry']
        if not g: continue
        ls = g['coordinates'] if g['type'] == 'MultiLineString' else [g['coordinates']]
        rank = f['properties'].get('scalerank') or 9
        if rank > a.rank: continue
        for l in ls:
            if any(x0 < p[0] < x1 and y0 < p[1] < y1 for p in l):
                rios.append({'nome': f['properties'].get('name'), 'rank': rank, 'pts': r3(l)})
    out = {'pais': a.pais, 'estados': est, 'contorno': pais, 'rios': rios}
    json.dump(out, open(a.saida, 'w'), separators=(',', ':'), ensure_ascii=False)
    print(f'{a.saida}: {len(est)} estados, {len(pais)} anéis de contorno, {len(rios)} rios, {os.path.getsize(a.saida) // 1024} KB')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter); sp = ap.add_subparsers(dest='cmd', required=True)
    b = sp.add_parser('baixar'); b.add_argument('pasta'); b.add_argument('--bbox'); b.add_argument('--ppd', type=float, default=64); b.add_argument('--nome', default='tex')
    t = sp.add_parser('texturas'); t.add_argument('pasta'); t.add_argument('nome'); t.add_argument('saida'); t.add_argument('--relevo', action='store_true'); t.add_argument('--q', type=int, default=82); t.add_argument('--borda', type=float, default=.04, help='esfumar bordas (fração); 0 na textura de base')
    v = sp.add_parser('vetores'); v.add_argument('pasta'); v.add_argument('pais'); v.add_argument('saida'); v.add_argument('--bbox'); v.add_argument('--tol', type=float, default=.01); v.add_argument('--rank', type=int, default=8); v.add_argument('--adm1', default='50m', help='50m (leve) ou 10m (todos os países)')
    a = ap.parse_args(); {'baixar': baixar, 'texturas': texturas, 'vetores': vetores}[a.cmd](a)
