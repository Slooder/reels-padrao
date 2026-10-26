"""checar_legenda.py — mede a legenda do vídeo pronto contra a base sem legenda (diferença de quadros = só a legenda):
desvio do centro horizontal (regra do Studio: ≤ 8 px) e altura do bloco. Mede no fim de cada frase (bloco todo aceso).
uso: python checar_legenda.py <video_legendado.mp4> [base.mp4]"""
import json
import subprocess
import sys

import numpy as np

import plano as P


def quadro(video, t):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1", "-f", "rawvideo",
                          "-pix_fmt", "gray", "-"], capture_output=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(P.H, P.W).astype(int)


video = sys.argv[1]
base = sys.argv[2] if len(sys.argv) > 2 else P.PROJ / "render" / "_base_v2.mp4"
pal = json.load(open(P.PROJ / "transcricao" / "final_v2.palavras.json", encoding="utf-8"))
telas = [(e["de"], e["ate"]) for e in P.eventos("v2") if e["tipo"] != "janela"]   # tela cheia e dividida: a legenda some ou muda de lugar
ts = [t for t in (max(p["a"] + 0.12, p["b"] - 0.05) for p in pal if p["w"][-1:] in ".?!,")   # última palavra já acesa, antes do bloco sair
      if not any(a - 0.6 <= t <= b + 0.6 for a, b in telas)]
res = []
for t in ts:
    leg, bas = quadro(video, t), quadro(base, t)
    # pixels brancos que não existem na base (a mão que mexe entre os dois quadros também difere, mas não é branca;
    # o pescoço chega a ~226 de cinza, então a diferença exigida é pequena e o branco, quase puro)
    m = (leg > 245) & (leg - bas > 15)
    m[:1100] = False                                          # a legenda nunca sobe acima de y 1100
    cols, rows = np.where(m.sum(0) >= 2)[0], np.where(m.sum(1) >= 3)[0]
    if len(cols) < 20:
        continue
    res.append((round(t, 1), round((cols[0] + cols[-1]) / 2 - P.W / 2), int(rows[0]), int(rows[-1])))
fora = [(t, d) for t, d, *_ in res if abs(d) > 8]
print(f"{len(res)} amostras · desvio do centro máx {max(abs(d) for _, d, *_ in res)} px · "
      f"topo {min(r[2] for r in res)}–{max(r[2] for r in res)} px · base {min(r[3] for r in res)}–{max(r[3] for r in res)} px")
print("FORA DO CENTRO:", fora or "nenhuma")
