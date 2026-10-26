#!/usr/bin/env python3
"""Narração em pt-BR com a voz do sistema (say). Lê videos/<nome>/narration.src.json → gera audio/narr/<nome>/*.wav
e escreve videos/<nome>/narration.json com início e duração de cada fala (a linha do tempo do vídeo segue a narração)."""
import json, os, sys, subprocess, wave
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
name = sys.argv[1]; src = json.load(open(f'{ROOT}/videos/{name}/narration.src.json'))
voice, rate, t = src.get('voice', 'Luciana'), src.get('rate', 182), src.get('start', .6)
od = f'{ROOT}/audio/narr/{name}'; os.makedirs(od, exist_ok=True); out = []
for i, s in enumerate(src['segments']):
    t += s.get('gap', .35); f = f'{od}/{i:02d}.wav'
    subprocess.run(['say', '-v', voice, '-r', str(rate), '--file-format=WAVE', '--data-format=LEI16@48000', '-o', f, s['say']], check=True)
    w = wave.open(f); d = w.getnframes() / w.getframerate(); w.close()
    out.append({'id': s['id'], 'text': s.get('text', s['say']), 'start': round(t, 3), 'dur': round(d, 3), 'file': f'audio/narr/{name}/{i:02d}.wav'})
    t += d
json.dump({'segments': out, 'end': round(t, 3)}, open(f'{ROOT}/videos/{name}/narration.json', 'w'), ensure_ascii=False, indent=1)
for o in out: print(f"{o['start']:6.2f} +{o['dur']:.2f}  {o['text']}")
print('fim', round(t, 2))
