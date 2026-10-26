#!/usr/bin/env python3
"""Planeta chapado para a colagem explicativa: projeta os continentes (Natural Earth 1:110m,
domínio público) numa vista ortográfica centrada onde você quiser e grava um JSON com os
paths SVG (raio 1, centro 0,0) que a lib/colagem.js desenha com CE.planeta().

uso (da raiz do projeto):
  audio/.venv/bin/python tools/globo.py videos/<nn>/img/globo.json --lon -52 --lat -12 [--destaque brasil]
      --lon/--lat   centro da vista (graus). Brasil: -52,-12 · África: 20,5 · Europa: 15,45
      --destaque    pinta um país com outra cor (usa tools/ne/<nome>.geojson; vem 'brasil')
"""
import argparse, json, math, os

AQUI = os.path.dirname(os.path.abspath(__file__))

def aneis(geom):
    if geom['type'] == 'Polygon': return geom['coordinates']
    return [r for p in geom['coordinates'] for r in p]

def densifica(r, passo=1.0):
    out = []
    for (x0, y0), (x1, y1) in zip(r, r[1:] + r[:1]):
        n = max(1, int(max(abs(x1 - x0), abs(y1 - y0)) / passo))
        out += [(x0 + (x1 - x0) * k / n, y0 + (y1 - y0) * k / n) for k in range(n)]
    return out

def projeta(lon, lat, lon0, lat0):
    l, p, l0, p0 = map(math.radians, (lon, lat, lon0, lat0))
    cosc = math.sin(p0) * math.sin(p) + math.cos(p0) * math.cos(p) * math.cos(l - l0)
    x = math.cos(p) * math.sin(l - l0)
    y = math.cos(p0) * math.sin(p) - math.sin(p0) * math.cos(p) * math.cos(l - l0)
    if cosc < 0:  # lado de trás: empurra para a borda (o recorte circular fecha o contorno)
        n = math.hypot(x, y) or 1; x, y = x / n, y / n
    return x, -y, cosc >= 0

def path(feats, lon0, lat0):
    ds = []
    for f in feats:
        for r in aneis(f['geometry']):
            pts = [projeta(lo, la, lon0, lat0) for lo, la in densifica([tuple(p) for p in r[:-1]])]
            if not any(v for _, _, v in pts): continue
            ds.append('M' + 'L'.join(f'{x:.4f} {y:.4f}' for x, y, _ in pts) + 'Z')
    return ''.join(ds)

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('saida')
    ap.add_argument('--lon', type=float, default=-52); ap.add_argument('--lat', type=float, default=-12)
    ap.add_argument('--destaque', default='')
    a = ap.parse_args()
    terra = json.load(open(os.path.join(AQUI, 'ne', 'land.geojson')))['features']
    out = {'lon': a.lon, 'lat': a.lat, 'terra': path(terra, a.lon, a.lat)}
    if a.destaque:
        out['destaque'] = path(json.load(open(os.path.join(AQUI, 'ne', a.destaque + '.geojson')))['features'], a.lon, a.lat)
    os.makedirs(os.path.dirname(a.saida) or '.', exist_ok=True)
    json.dump(out, open(a.saida, 'w'))
    print(f"{a.saida}: terra {len(out['terra'])//1000} kB" + (f", destaque {len(out.get('destaque',''))//1000} kB" if a.destaque else ''))
