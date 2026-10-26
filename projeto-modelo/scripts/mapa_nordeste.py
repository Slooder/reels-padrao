"""mapa_nordeste.py — o Nordeste como UMA forma só (sem divisa de estado nem capitais), em SVG para o Remotion.
Lê a malha do IBGE (broll/bruto/mapa/brasil-ufs.geojson) e grava src/videos/jp-testemunhos/nordeste.json:
{w, h, d (path de todos os anéis), cx, cy (onde vai o rótulo)}. Os estados são desenhados juntos, preenchidos e sem traço
de divisa: na tela vira um conjunto só. uso: python mapa_nordeste.py"""
import json
import math
from collections import Counter, defaultdict

import plano as P

LARGURA = 860                      # px no vídeo (1080 de largura)
PASSO = 1.2                        # px: ponto mais perto que isso do anterior é descartado (simplifica o contorno)
LAT0 = -9.0                        # projeção equirretangular com correção do cosseno no centro da região

geo = json.load(open(P.PROJ / "broll" / "bruto" / "mapa" / "brasil-ufs.geojson", encoding="utf-8"))
aneis = []
for f in geo["features"]:
    if f["properties"]["codarea"] not in P.UFS_NORDESTE:
        continue
    g = f["geometry"]
    polis = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
    # fora as ilhas oceânicas (Fernando de Noronha, Atol das Rocas): a costa mais a leste do continente fica em -34,79
    aneis += [anel for poli in polis for anel in poli if max(lon for lon, _ in anel) < -34.75]
k = math.cos(math.radians(LAT0))
xs = [lon * k for a in aneis for lon, _ in a]
ys = [-lat for a in aneis for _, lat in a]
x0, y0 = min(xs), min(ys)
esc = LARGURA / (max(xs) - x0)
altura = (max(ys) - y0) * esc

def caminho(lista):
    partes = []
    for a in lista:
        pts = []
        for lon, lat in a:
            p = ((lon * k - x0) * esc, (-lat - y0) * esc)
            if not pts or math.dist(p, pts[-1]) >= PASSO:
                pts.append(p)
        if len(pts) >= 3:
            partes.append("M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + "Z")
    return partes


partes = caminho(aneis)

# contorno da região (para o traço que se desenha): as divisas entre estados aparecem duas vezes na malha do IBGE
# (os vizinhos têm os mesmos vértices); as arestas que sobram uma vez só são a borda de fora — encadeadas em anéis
q = lambda p: (round(p[0], 6), round(p[1], 6))  # noqa: E731
conta = Counter(frozenset((q(p), q(r))) for a in aneis for p, r in zip(a, a[1:]))
viz = defaultdict(list)
for aresta, n in conta.items():
    if n == 1 and len(aresta) == 2:
        p, r = tuple(aresta)
        viz[p].append(r)
        viz[r].append(p)
assert all(len(v) == 2 for v in viz.values()), "borda com ponta solta: a malha não fecha"
contorno, usados = [], set()
for ini in viz:
    if ini in usados:
        continue
    anel, ant, cur = [ini], None, ini
    while True:
        usados.add(cur)
        nxt = next(p for p in viz[cur] if p != ant)
        if nxt == ini:
            break
        anel.append(nxt)
        ant, cur = cur, nxt
    contorno.append(anel + [ini])

saida = {"w": LARGURA, "h": round(altura, 1), "d": "".join(partes), "contorno": "".join(caminho(contorno)),
         "cx": round(LARGURA / 2, 1), "cy": round(altura * 0.45, 1)}   # rótulo no meio da forma (pedido do JP, 24/10)
destino = P.PROJ.parents[1] / "src" / "videos" / "jp-testemunhos" / "nordeste.json"
json.dump(saida, open(destino, "w", encoding="utf-8"))
print(f"{len(partes)} anéis · {sum(p.count('L') + 1 for p in partes)} pontos · contorno em {len(contorno)} anel(éis) · "
      f"{LARGURA}×{altura:.0f} px → {destino}")
