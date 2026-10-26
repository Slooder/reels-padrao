"""montagem.py — base do vídeo: chunks do bruto com zoom contínuo (recorte por quadro via sendcmd), inserções do vídeo
do Nikolas, dissolves entre chunks e a cauda preta para a bandeira/cartela. Saída: render/_base_<versao>.mp4.
uso: python montagem.py v2 [--sem-janelas]   (--sem-janelas: o JP não desce para as janelas — prévia só da decupagem)"""
import math
import subprocess
import sys
from pathlib import Path

import plano as P

SW, SH = 2160, 3840            # brutos 4K verticais
PASTA = P.PROJ / "render" / "_chunks"


def ease(p: float) -> float:
    p = min(1.0, max(0.0, p))
    return 0.5 - 0.5 * math.cos(math.pi * p)


def zoom_base(versao, t):
    kf = sorted((P.out(versao, f, s), z) for f, s, z in P.ZOOM if P.out(versao, f, s) is not None)
    if t <= kf[0][0]:
        return kf[0][1]
    for (t0, z0), (t1, z1) in zip(kf, kf[1:]):
        if t <= t1:
            return z0 + (z1 - z0) * ease((t - t0) / (t1 - t0))
    return kf[-1][1]


def intervalos_janela(versao):
    iv = sorted((e["de"], e["ate"]) for e in P.eventos(versao) if e["tipo"] == "janela")
    junto = [list(iv[0])]
    for a, b in iv[1:]:
        if a - junto[-1][1] < 3.0:          # janelas próximas: o JP não sobe e desce à toa
            junto[-1][1] = max(junto[-1][1], b)
        else:
            junto.append([a, b])
    return junto


def peso_janela(ivs, t):
    w = 0.0
    for a, b in ivs:
        w = max(w, min(ease((t - a + P.RAMPA / 2) / P.RAMPA), ease((b + P.RAMPA / 2 - t) / P.RAMPA)))
    return w


def recorte(versao, t, ivs):
    zb = zoom_base(versao, t)
    w = peso_janela(ivs, t)
    z = zb + w * (max(P.ZOOM_JANELA, zb) - zb)
    sy = P.ROSTO[1] + w * (P.Y_JANELA - P.ROSTO[1])
    cw, ch = SW / z, SH / z
    x = min(max(P.ROSTO[0] * SW - P.ROSTO[0] * cw, 0), SW - cw)
    y = min(max(P.ROSTO[1] * SH - sy * ch, 0), SH - ch)
    return int(cw) // 2 * 2, int(ch) // 2 * 2, int(x), int(y)


def recorte_insercao(tl):           # vídeo do Nikolas: push-in lento 1,00 → 1,06 no centro
    z = 1.0 + 0.06 * ease(tl)
    cw, ch = SW / z, SH / z
    return int(cw) // 2 * 2, int(ch) // 2 * 2, int((SW - cw) / 2), int((SH - ch) * 0.45)


def render_chunk(versao, i, c, ivs):
    saida = PASTA / f"{versao}_{i:02d}.mp4"
    dur = c["b"] - c["a"]
    cmds = PASTA / f"{versao}_{i:02d}.cmd"
    linhas = []
    for k in range(int(round(dur * P.FPS)) + 1):
        tl = k / P.FPS
        if c["fonte"] == "N":
            w, h, x, y = recorte_insercao(tl / dur)
        else:
            w, h, x, y = recorte(versao, c["ini"] + tl, ivs)
        linhas.append(f"{tl:.4f} crop w {w}, crop h {h}, crop x {x}, crop y {y};")
    cmds.write_text("\n".join(linhas), encoding="utf-8")
    grade = "eq=contrast=1.06:saturation=1.03,unsharp=5:5:0.4" if c["fonte"] != "N" else "null"
    vf = (f"fps={P.FPS},sendcmd=f='{cmds.as_posix().replace(':', chr(92) + ':')}',crop=w={SW}:h={SH}:x=0:y=0,"
          f"scale={P.W}:{P.H}:flags=lanczos,setsar=1,{grade},format=yuv420p")
    n = int(round(dur * P.FPS))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{c['a']:.3f}", "-t", f"{dur + 0.5:.3f}", "-i", str(P.FONTES[c["fonte"]]),
                    "-map", "0:v:0", "-map", "0:a:0", "-vf", vf, "-frames:v", str(n),
                    "-af", f"aresample=48000,aformat=channel_layouts=stereo,apad,atrim=0:{n / P.FPS:.6f}",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "16", "-r", str(P.FPS), "-c:a", "pcm_s16le",
                    str(saida.with_suffix(".mov"))], check=True)
    return saida.with_suffix(".mov")


def cauda(versao):
    saida = PASTA / f"{versao}_cauda.mov"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=black:s={P.W}x{P.H}:r={P.FPS}:d={P.CAUDA}",
                    "-f", "lavfi", "-i", f"anullsrc=r=48000:cl=stereo", "-t", str(P.CAUDA), "-c:v", "libx264", "-crf", "16",
                    "-pix_fmt", "yuv420p", "-c:a", "pcm_s16le", str(saida)], check=True)
    return saida


def emendar(arquivos, saida):
    """Junta por corte (sem recodificar): mesmos codecs e parâmetros, então o concat demuxer basta."""
    lista = saida.with_suffix(".txt")
    lista.write_text("".join(f"file '{p.as_posix()}'\n" for p in arquivos), encoding="utf-8")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lista), "-c", "copy", str(saida)], check=True)
    return saida


def juntar(versao, partes, tl):
    """Corte (dissolve 0) vira emenda direta; o resto é uma cadeia só de xfade/acrossfade."""
    blocos, xs = [[partes[0]]], []
    for i in range(1, len(partes)):
        x = tl[i]["x"] if i < len(tl) else 0.0
        if x > 0:
            blocos.append([partes[i]])
            xs.append(x)
        else:
            blocos[-1].append(partes[i])
    arqs = [b[0] if len(b) == 1 else emendar(b, PASTA / f"{versao}_bloco{k}.mov") for k, b in enumerate(blocos)]
    durs = [float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)],
                                 capture_output=True, text=True).stdout) for f in arqs]
    entradas, fc = [], []
    for f in arqs:
        entradas += ["-i", str(f)]
    v, a = ("[0:v]", "[0:a]") if len(arqs) > 1 else ("0:v", "0:a")   # só cortes secos: nada para o filtro
    acumulado = durs[0]
    for i in range(1, len(arqs)):
        x = xs[i - 1]
        fc.append(f"{v}[{i}:v]xfade=transition=fade:duration={x}:offset={acumulado - x:.4f}[v{i}]")
        fc.append(f"{a}[{i}:a]acrossfade=d={x}:c1=tri:c2=tri[a{i}]")
        acumulado += durs[i] - x
        v, a = f"[v{i}]", f"[a{i}]"
    saida = P.PROJ / "render" / f"_base_{versao}.mp4"
    subprocess.run(["ffmpeg", "-v", "warning", "-y", *entradas, *(["-filter_complex", ";".join(fc)] if fc else []), "-map", v, "-map", a,
                    "-c:v", "libx264", "-preset", "medium", "-crf", "16", "-pix_fmt", "yuv420p", "-r", str(P.FPS),
                    "-c:a", "aac", "-b:a", "256k", str(saida)], check=True)
    return saida, acumulado


if __name__ == "__main__":
    versao = sys.argv[1]
    PASTA.mkdir(parents=True, exist_ok=True)
    tl = P.linha_do_tempo(versao)
    ivs = [] if "--sem-janelas" in sys.argv else intervalos_janela(versao)
    partes = []
    for i, c in enumerate(tl):
        partes.append(render_chunk(versao, i, c, ivs))
        print(f"chunk {i} ok: {c['fonte']} {c['a']}–{c['b']}", flush=True)
    partes.append(cauda(versao))
    saida, dur = juntar(versao, partes, tl)
    print(f"{saida} · esperado {P.duracao(versao):.2f} s · montado {dur:.2f} s")
