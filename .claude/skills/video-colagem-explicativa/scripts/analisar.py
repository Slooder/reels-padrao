#!/usr/bin/env python3
"""Lê um vídeo de referência para copiar ESTILO e MOVIMENTO (nunca o conteúdo).

uso (da raiz do projeto, com o venv):
  audio/.venv/bin/python tools/analisar.py ler <video> previews/ref [--qps 6] [--limiar .28]
      → info, CORTES detectados (lista de planos com tempos), folhas de contato (4 s por folha),
        mosaico com 1 quadro por plano (planos.jpg), quadros-chave grandes, paleta geral e por plano,
        e um esqueleto de FICHA DE ESTILO (ficha.md) para você preencher olhando as imagens.
  audio/.venv/bin/python tools/analisar.py quadros <video> previews/ref --em 0.4,2.1,3.3 [--largura 720]
      → quadros grandes nos instantes pedidos (para medir posição, tamanho, tipografia).
  audio/.venv/bin/python tools/analisar.py passo <video> previews/ref --de 2.0 --ate 2.6 [--qps 30]
      → folha quadro a quadro de um trecho curto (para medir easing, duração de entrada/saída, stop-motion).
  audio/.venv/bin/python tools/analisar.py comparar <referencia> <nosso.mp4> previews/comparar.jpg [--n 8]
      → lado a lado (referência | nosso) em instantes proporcionais — use a cada rodada de ajuste.
"""
import argparse, json, math, os, re, subprocess, sys
from PIL import Image, ImageDraw

def sh(*c, **k): return subprocess.run(c, check=True, capture_output=True, text=True, **k)
def info(v):
    j = json.loads(sh('ffprobe', '-v', 'error', '-show_entries', 'format=duration:stream=width,height,r_frame_rate,codec_type', '-of', 'json', v).stdout)
    vs = [s for s in j['streams'] if s.get('codec_type') == 'video'][0]; n, d = vs['r_frame_rate'].split('/')
    return float(j['format']['duration']), vs['width'], vs['height'], float(n) / float(d), any(s.get('codec_type') == 'audio' for s in j['streams'])
def frame(v, t, w=360):
    out = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{t:.3f}', '-i', v, '-frames:v', '1', '-vf', f'scale={w}:-2', '-f', 'image2pipe', '-vcodec', 'png', '-'], capture_output=True, check=True).stdout
    import io; return Image.open(io.BytesIO(out)).convert('RGB')
def hexs(cols): return ' '.join(f'#{r:02x}{g:02x}{b:02x}' for r, g, b in cols)
def paleta(im, n=6):
    q = im.convert('RGB').quantize(colors=48, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE); pal = q.getpalette()
    out = []; tot = im.width * im.height
    for c, i in sorted(q.getcolors(), reverse=True):
        rgb = tuple(pal[i * 3:i * 3 + 3])
        if any(sum(abs(a - b) for a, b in zip(rgb, o)) < 42 for o, _ in out): continue
        out.append((rgb, 100 * c / tot))
        if len(out) >= n: break
    return out

def cortes(v, limiar):
    r = subprocess.run(['ffmpeg', '-v', 'info', '-i', v, '-vf', f"select='gt(scene,{limiar})',showinfo", '-an', '-f', 'null', '-'], capture_output=True, text=True)
    return [float(m) for m in re.findall(r'pts_time:([0-9.]+)', r.stderr)]

def ler(a):
    os.makedirs(a.saida, exist_ok=True); dur, W, H, fps, aud = info(a.video)
    print(f'{os.path.basename(a.video)}: {W}x{H} ({W / H:.3f}), {dur:.2f} s, {fps:.2f} qps, áudio: {"sim" if aud else "não"}')
    cs = [c for c in cortes(a.video, a.limiar) if c > .15 and c < dur - .1]
    # junta cortes muito próximos (flashes)
    cuts = []
    for c in cs:
        if not cuts or c - cuts[-1] > .2: cuts.append(c)
    planos = list(zip([0] + cuts, cuts + [dur]))
    print(f'\n{len(planos)} planos (corte por diferença de quadro > {a.limiar}); duração média {dur / len(planos):.2f} s')
    # folhas de contato
    cols, per = 10, 4.0; rows = math.ceil(per * a.qps / cols)
    for i in range(math.ceil(dur / per)):
        out = os.path.join(a.saida, f'folha_{i:02d}_{i * per:05.1f}s.jpg')
        sh('ffmpeg', '-v', 'error', '-y', '-ss', str(i * per), '-t', str(per), '-i', a.video, '-vf', f'fps={a.qps},scale=200:-2,tile={cols}x{rows}', '-frames:v', '1', out)
    print(f'folhas de contato: {a.saida}/folha_*.jpg ({1 / a.qps:.3f} s por célula, ler em linhas)')
    # mosaico: 1 quadro por plano + paleta por plano
    tw = 240; ims = []; linhas = []
    for k, (t0, t1) in enumerate(planos):
        im = frame(a.video, (t0 + t1) / 2, tw); ims.append(im); p = paleta(im, 3)
        linhas.append((k + 1, t0, t1, hexs([c for c, _ in p])))
    th = ims[0].height + 22; c6 = 6; sheet = Image.new('RGB', (tw * c6, th * math.ceil(len(ims) / c6)), (24, 24, 24)); d = ImageDraw.Draw(sheet)
    for k, im in enumerate(ims):
        x, y = (k % c6) * tw, (k // c6) * th; sheet.paste(im, (x, y + 22)); d.text((x + 6, y + 5), f'{k + 1:02d}  {planos[k][0]:.2f}–{planos[k][1]:.2f}s', fill=(255, 220, 90))
    sheet.save(os.path.join(a.saida, 'planos.jpg'), quality=88); print(f'mosaico de planos: {a.saida}/planos.jpg')
    # quadros-chave grandes (meio de cada plano, até 30)
    qd = os.path.join(a.saida, 'quadros'); os.makedirs(qd, exist_ok=True)
    for k, (t0, t1) in enumerate(planos[:30]): frame(a.video, (t0 + t1) / 2, 720).save(os.path.join(qd, f'plano_{k + 1:02d}_{(t0 + t1) / 2:05.2f}s.jpg'), quality=90)
    # paleta geral
    amostra = Image.new('RGB', (120 * 24, int(120 * H / W)))
    for i in range(24): amostra.paste(frame(a.video, dur * (i + .5) / 24, 120), (i * 120, 0))
    pg = paleta(amostra, 10)
    print('\npaleta geral (% da área):'); [print(f'  #{r:02x}{g:02x}{b:02x}  {p:5.1f}%') for (r, g, b), p in pg]
    # ficha de estilo (esqueleto)
    f = open(os.path.join(a.saida, 'ficha.md'), 'w')
    f.write(f"# Ficha de estilo — {os.path.basename(a.video)}\n\n{W}x{H} · {dur:.1f} s · {fps:.0f} qps · {len(planos)} planos (média {dur / len(planos):.2f} s)\n\n")
    f.write("Paleta geral: " + hexs([c for c, _ in pg]) + "\n\n")
    f.write("## Planos\n\n| # | início | fim | dur | cores | o que acontece (fundo · objetos · texto · movimento) | entra/sai como |\n|---|---|---|---|---|---|---|\n")
    for k, t0, t1, cs_ in linhas: f.write(f"| {k} | {t0:.2f} | {t1:.2f} | {t1 - t0:.2f} | {cs_} |  |  |\n")
    f.write("""
## Gramática (preencha olhando folhas, mosaico e quadros)
- **Família do estilo:** (colagem 2.5D · traço chapado · risografia · mídia mista · documentário editado · tipografia cinética · 3D · UI/mockup · stop-motion · outro)
- **Fundo/texturas:**
- **Tipografia:** (família parecida, peso, caixa, tamanho em % da altura, cor, como aparece: digitada / máscara / escala / piscando)
- **Objetos e fotos:** (fotos reais? recortes com borda? vetores? 3D? de onde viriam)
- **Movimento:** (eases, durações típicas de entrada/saída, câmera: empurrão, parallax, chicote, tremor; stop-motion em quantos qps)
- **Transições:** (corte seco, zoom com desfoque, chicote, wipe, caleidoscópio, máscara, flash)
- **Acabamento:** (grão, vinheta, aberração, brilho, film weave, bordas que fervem)
- **Ritmo:** (cortes por segundo, onde respira, como termina)
- **Som:** (trilha: estilo/bpm; efeitos nos cortes e entradas)
- **O que torna esse estilo reconhecível (3 coisas):**
""")
    f.close(); print(f'\nficha de estilo para preencher: {a.saida}/ficha.md')

def quadros(a):
    os.makedirs(a.saida, exist_ok=True)
    for t in [float(x) for x in a.em.split(',') if x.strip()]:
        p = os.path.join(a.saida, f'quadro_{t:06.2f}s.jpg'); frame(a.video, t, a.largura).save(p, quality=92); print(p)

def passo(a):
    os.makedirs(a.saida, exist_ok=True); n = max(1, round((a.ate - a.de) * a.qps)); cols = min(10, n); rows = math.ceil(n / cols)
    out = os.path.join(a.saida, f'passo_{a.de:05.2f}-{a.ate:05.2f}s.jpg')
    sh('ffmpeg', '-v', 'error', '-y', '-ss', str(a.de), '-t', str(a.ate - a.de), '-i', a.video, '-vf', f'fps={a.qps},scale=216:-2,tile={cols}x{rows}', '-frames:v', '1', out)
    print(out, f'({n} quadros, {1 / a.qps:.3f} s cada)')

def comparar(a):
    d1 = info(a.ref)[0]; d2 = info(a.nosso)[0]; tw = 300; pares = []
    for i in range(a.n):
        u = (i + .5) / a.n; pares.append((frame(a.ref, d1 * u, tw), frame(a.nosso, d2 * u, tw), d1 * u, d2 * u))
    h = max(max(p[0].height, p[1].height) for p in pares) + 20; cols = 4
    rows = math.ceil(a.n / cols); sheet = Image.new('RGB', (cols * (2 * tw + 16), rows * h), (30, 30, 30)); d = ImageDraw.Draw(sheet)
    for i, (r, o, t1, t2) in enumerate(pares):
        x, y = (i % cols) * (2 * tw + 16), (i // cols) * h
        sheet.paste(r, (x, y + 20)); sheet.paste(o, (x + tw + 4, y + 20)); d.text((x + 4, y + 4), f'ref {t1:.1f}s', fill=(255, 220, 90)); d.text((x + tw + 8, y + 4), f'nosso {t2:.1f}s', fill=(120, 230, 160))
    sheet.save(a.saida, quality=88); print(a.saida)

ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest='cmd', required=True)
p = sp.add_parser('ler'); p.add_argument('video'); p.add_argument('saida'); p.add_argument('--qps', type=float, default=6); p.add_argument('--limiar', type=float, default=.28)
p = sp.add_parser('quadros'); p.add_argument('video'); p.add_argument('saida'); p.add_argument('--em', required=True); p.add_argument('--largura', type=int, default=720)
p = sp.add_parser('passo'); p.add_argument('video'); p.add_argument('saida'); p.add_argument('--de', type=float, required=True); p.add_argument('--ate', type=float, required=True); p.add_argument('--qps', type=float, default=30)
p = sp.add_parser('comparar'); p.add_argument('ref'); p.add_argument('nosso'); p.add_argument('saida'); p.add_argument('--n', type=int, default=8)
a = ap.parse_args(); {'ler': ler, 'quadros': quadros, 'passo': passo, 'comparar': comparar}[a.cmd](a)
