#!/usr/bin/env python3
"""Recorta o objeto principal de uma foto (Vision, macOS) e entrega um PNG com alfa, já cortado
na caixa do objeto, com a borda do alfa endurecida para o contorno de adesivo (.stk) não fazer halo.

uso (da raiz do projeto):
  audio/.venv/bin/python tools/recortar.py img/mico.jpg img/mico_cut.png [--max 1400] [--pad 10]
  audio/.venv/bin/python tools/recortar.py img/foto.jpg img/foto_cut.png --caixa 0.1,0.2,0.8,0.95
      --caixa x0,y0,x1,y1 (frações 0–1) recorta a foto ANTES do Vision — útil quando há dois bichos
      e você só quer um, ou quando o objeto é pequeno no quadro.
"""
import argparse, os, subprocess, sys, tempfile
from PIL import Image

AQUI = os.path.dirname(os.path.abspath(__file__))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('entrada'); ap.add_argument('saida')
    ap.add_argument('--max', type=int, default=1400, help='largura máxima do PNG final (px)')
    ap.add_argument('--pad', type=int, default=10, help='margem transparente em volta do objeto (px)')
    ap.add_argument('--caixa', help='x0,y0,x1,y1 em frações: recorta a foto antes de mandar pro Vision')
    ap.add_argument('--bin', default=os.path.join(AQUI, 'cutout'), help='binário compilado de cutout.swift')
    a = ap.parse_args()
    if not os.path.exists(a.bin):
        sys.exit(f'não achei {a.bin} — rode scripts/setup.sh (compila cutout.swift; precisa de macOS 14+ e swiftc)')

    src = a.entrada; tmpdir = tempfile.mkdtemp()
    if a.caixa:
        x0, y0, x1, y1 = map(float, a.caixa.split(','))
        im = Image.open(src).convert('RGB'); W, H = im.size
        src = os.path.join(tmpdir, 'caixa.png'); im.crop((int(x0 * W), int(y0 * H), int(x1 * W), int(y1 * H))).save(src)

    mask_png = os.path.join(tmpdir, 'mask.png')
    r = subprocess.run([a.bin, src, mask_png], capture_output=True, text=True)
    print(r.stdout.strip())
    if r.returncode or not os.path.exists(mask_png):
        sys.exit('o Vision não achou objeto em primeiro plano — tente outra foto (objeto inteiro, fundo simples) ou use --caixa')

    im = Image.open(mask_png).convert('RGBA'); al = im.getchannel('A')
    # endurece a borda: some com o véu semitransparente que vira halo sob drop-shadow
    al = al.point(lambda v: 0 if v < 24 else min(255, int((v - 24) * 255 / 200)))
    im.putalpha(al)
    box = al.point(lambda v: 255 if v > 8 else 0).getbbox()
    if not box: sys.exit('máscara vazia')
    W, H = im.size; frac = (box[2] - box[0]) * (box[3] - box[1]) / (W * H)
    p = a.pad; box = (max(0, box[0] - p), max(0, box[1] - p), min(W, box[2] + p), min(H, box[3] + p))
    im = im.crop(box)
    if im.width > a.max: im = im.resize((a.max, round(im.height * a.max / im.width)), Image.LANCZOS)
    im.save(a.saida, optimize=True)
    cob = sum(im.getchannel('A').histogram()[129:]) / (im.width * im.height)
    print(f'{a.saida}: {im.width}×{im.height}  (objeto ocupava {frac:.0%} da foto; preenche {cob:.0%} do recorte)')
    if frac < .04: print('  aviso: objeto pequeno na foto — o recorte vai ficar com pouca resolução; prefira outra foto ou --caixa')
    if cob < .25: print('  aviso: recorte muito vazado — confira se não pegou só um pedaço (abra o PNG e olhe)')
    # prova sobre fundo verde: abra esta imagem pra conferir o contorno
    os.makedirs('previews', exist_ok=True); prova = os.path.join('previews', 'recorte-' + os.path.splitext(os.path.basename(a.saida))[0] + '.jpg')
    bg = Image.new('RGBA', im.size, (40, 160, 90, 255)); bg.alpha_composite(im); bg.convert('RGB').save(prova, quality=85)
    print(f'  prova: {prova} — confira; o Vision costuma perder partes finas (rabo, antena, bigode, pernas finas).')

if __name__ == '__main__':
    main()
