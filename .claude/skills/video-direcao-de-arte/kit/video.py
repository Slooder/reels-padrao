#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""video.py — helpers de ffmpeg da casa, submetidos à DA e à trava global.

    import da, video
    d = da.carregar()
    info = video.sondar("bruto/entrevista.mp4")            # dict completo (largura, altura, fps, duração, áudio…)
    video.executar(args, saida, rotulo="…")                 # ffmpeg sob a trava, grava <nome>.parcial.<ext> e renomeia só com rc 0
    video.args_encode(d, formato="vertical", crf=18)         # H.264 yuv420p bt709 +faststart no fps do formato da DA
    video.filtro_tratamento(d, "horizontal")                # cadeia do grade.json (ou "null")
    video.filtro_recorte((1920, 1080), (1080, 1920), "rosto", foco=(0.5, 0.33))
    video.filtro_encaixe((1920, 1080), (1080, 1920), d=d)   # vídeo inteiro sobre fundo desfocado (tratamento.encaixe)
    video.filtro_loudnorm(d, "curto")                       # loudnorm com o alvo de som.loudness (medida=… → 2 passagens)
    video.medir_loudness("render/final.mp4")                # {'lufs', 'lra', 'pico_real', 'limiar'}
    video.extrair_quadro("bruto/x.mp4", 12.5, "qa/_q.png")
    video.folha_de_contato([...quadros...], [...legendas...], "qa/folha.png", da_obj=d)
    video.compor_overlay("base.mp4", "animacoes/gc.webm", "render/x.mp4", t0=3.0, da_obj=d)
    video.compor_cues("cortes/corte.mp4", cues, "legendas/corte.mp4", da_obj=d)   # N legendas numa passada só
    video.juntar(["a.mp4", "b.mp4"], "render/ab.mp4", da_obj=d)                   # transição da DA (concat/xfade)
    with video.Codificador("animacoes/card.webm", formato="vertical", da_obj=d) as cod:   # quadros PIL → vídeo (com alfa)
        for img in quadros: cod.escrever(img)

Tudo o que grava peça carimba a saída e registra a proveniência dos insumos (D14).
Este ffmpeg não tem drawtext/subtitles/ass: texto só via PNG RGBA (texto.py / motor) + overlay.
"""
from __future__ import annotations

import json
import math
import os
import queue
import re
import subprocess
import sys
import threading
from fractions import Fraction
from pathlib import Path

sys.dont_write_bytecode = True     # D9: nada de __pycache__ dentro da skill (trava.py apaga o que já tiver nascido)
KIT = Path(__file__).resolve().parent
if str(KIT) not in sys.path:
    sys.path.insert(0, str(KIT))
import da  # noqa: E402
import trava  # noqa: E402

_NUCLEO = da     # o módulo da.py sob um nome que os parâmetros `da=` (sinônimo de da_obj) não escondem

FFMPEG = da._bin("ffmpeg")
FFPROBE = da._bin("ffprobe")
THREADS = "2"
EXT_ALFA_WEBM = {".webm"}
INATIVIDADE_PADRAO = 120.0      # segundos sem progresso (CPU, saída crescendo, entrada consumida) até o ffmpeg ser morto
_LE_STDIN = {"-", "pipe:", "pipe:0", "/dev/stdin", "fd:0", "fd:"}


# ───────────────────────────────────────────────────────────────── sondar ──
def sondar(arquivo) -> dict:
    """ffprobe completo: {'largura','altura','fps' (Fraction),'fps_texto','duracao','quadros','pix_fmt','codec',
    'tem_audio','audio': {'codec','taxa','canais'}|None, 'tem_alfa', 'rotacao', 'streams': [...]}."""
    arquivo = Path(str(arquivo)).expanduser()
    if not arquivo.is_file():
        raise da.DAErro(f"arquivo não encontrado: {arquivo}")
    extra = ["-c:v", "libvpx-vp9"] if arquivo.suffix.lower() in EXT_ALFA_WEBM else []   # alfa de WebM só com o decoder libvpx
    try:
        r = subprocess.run([FFPROBE, "-v", "error", *extra, "-show_entries",
                            "stream=index,codec_type,codec_name,width,height,r_frame_rate,avg_frame_rate,duration,nb_frames,pix_fmt,"
                            "sample_rate,channels,side_data_list:stream_tags=rotate:format=duration,size,format_name",
                            "-of", "json", str(arquivo)], capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=120)
    except FileNotFoundError:
        raise da.DAErro("ffprobe não encontrado; instale o ffmpeg (brew install ffmpeg)")
    except subprocess.TimeoutExpired:
        raise da.DAErro(f"ffprobe não respondeu em 120 s lendo {arquivo}; o arquivo está corrompido ou num disco que não responde")
    if r.returncode != 0:
        raise da.DAErro(f"ffprobe não conseguiu ler {arquivo}: {r.stderr.strip()[-300:]}")
    dados = json.loads(r.stdout or "{}")
    streams = dados.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"), None)
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)
    fmt = dados.get("format") or {}

    def num(x):
        try:
            return float(x)
        except (TypeError, ValueError):
            return 0.0

    info = {"arquivo": str(arquivo), "duracao": num(fmt.get("duration")), "bytes": int(fmt.get("size") or 0),
            "formato": fmt.get("format_name"), "tem_audio": a is not None, "audio": None, "streams": streams}
    if a:
        info["audio"] = {"codec": a.get("codec_name"), "taxa": int(a.get("sample_rate") or 0), "canais": int(a.get("channels") or 0)}
    if v:
        fps_txt = v.get("avg_frame_rate") if v.get("avg_frame_rate") not in (None, "0/0") else v.get("r_frame_rate")
        try:
            fps = Fraction(fps_txt)
        except (ValueError, ZeroDivisionError, TypeError):
            fps = Fraction(0)
        rot = 0
        for sd in v.get("side_data_list") or []:
            if "rotation" in sd:
                rot = int(sd["rotation"])
        rot = rot or int(num((v.get("tags") or {}).get("rotate")))
        info.update(largura=int(v.get("width") or 0), altura=int(v.get("height") or 0), fps=fps, fps_texto=str(fps_txt),
                    pix_fmt=v.get("pix_fmt"), codec=v.get("codec_name"), quadros=int(v.get("nb_frames") or 0),
                    duracao=num(v.get("duration")) or info["duracao"], rotacao=rot,
                    tem_alfa=bool(re.match(r"^(?:yuva|gbrap|rgba|bgra|argb|abgr|ya\d|pal8)", v.get("pix_fmt") or "")))
        if abs(rot) in (90, 270):
            info["largura"], info["altura"] = info["altura"], info["largura"]
        if not info["quadros"] and info["duracao"] and fps:
            info["quadros"] = int(round(info["duracao"] * float(fps)))
    else:
        info.update(largura=0, altura=0, fps=Fraction(0), fps_texto=None, pix_fmt=None, codec=None, quadros=0, rotacao=0, tem_alfa=False)
    return info


# ───────────────────────────────────────────────────────────────── executar ──
def executar(args: list[str], saida, rotulo: str | None = None, espera_max: float | None = None, silencioso: bool = True,
             entrada=None, inatividade: float | None = INATIVIDADE_PADRAO, prazo: float | None = None) -> Path:
    """Roda `ffmpeg <args> <nome>.parcial.<ext>` sob a trava global; renomeia para `saida` só com rc 0.
    `args` NÃO inclui o arquivo de saída (é acrescentado aqui). Devolve o Path da saída.

    entrada:     None = o ffmpeg roda com o stdin em /dev/null. Se `args` lê do stdin (`-i -`, `pipe:0`), passe aqui
                 os bytes ou um ITERÁVEL de bytes (ex.: um PNG por quadro para args_png_para_yuv420): uma thread
                 escreve, fecha o stdin no fim e para sozinha se o ffmpeg sair antes. Ler do stdin sem `entrada`
                 é erro imediato (antes isso pendurava o ffmpeg com a trava global presa).
    inatividade: segundos sem progresso (CPU, tamanho do .parcial, entrada consumida) até o ffmpeg ser morto e a
                 trava liberada (padrão 120; VIDEO_OPS_INATIVIDADE troca; None/0 desliga). `prazo` limita o total.
    O ffmpeg roda em grupo de processos próprio: SIGINT/SIGTERM/SIGHUP neste processo o matam antes de soltar a trava.
    Levanta DAErro com o fim do stderr se o ffmpeg falhar, travar ou passar do prazo."""
    saida = Path(str(saida)).expanduser()
    args = [str(a) for a in args]
    le_stdin = any(a == "-i" and i + 1 < len(args) and args[i + 1] in _LE_STDIN for i, a in enumerate(args))
    if le_stdin and entrada is None:
        raise da.DAErro(f"video.executar ({rotulo or saida.name}): os argumentos leem do stdin (-i -), mas nenhuma `entrada` foi passada.",
                        dica="Passe entrada=<bytes ou iterável de bytes> (um PNG por quadro com args_png_para_yuv420), "
                             "ou troque o -i por um arquivo. Sem isso o ffmpeg ficaria esperando para sempre com a trava presa.")
    saida.parent.mkdir(parents=True, exist_ok=True)
    tmp = saida.with_name(f"{saida.stem}.parcial{saida.suffix}")
    cmd = [FFMPEG, "-hide_banner", "-v", "error" if silencioso else "warning", "-nostdin", "-y", *args, str(tmp)]
    nome = rotulo or f"ffmpeg {saida.name}"
    if inatividade is INATIVIDADE_PADRAO:
        inatividade = trava.inatividade_padrao(INATIVIDADE_PADRAO)
    try:
        try:
            r = trava.rodar(cmd, rotulo=nome, espera_max=espera_max, capturar=True, entrada=entrada,
                            inatividade=inatividade, prazo=prazo, vigiar=[tmp])
        except FileNotFoundError:
            raise da.DAErro("ffmpeg não encontrado; instale com `brew install ffmpeg` (ou aponte VIDEO_OPS_FFMPEG)")
        if r.motivo:
            raise da.DAErro(f"ffmpeg travou em {nome}: {trava.descrever_vigia(r)}\n{(r.stderr or '').strip()[-600:]}".rstrip(),
                            dica="Comando: " + " ".join(_citar(c) for c in cmd))
        if r.codigo != 0:
            raise da.DAErro(f"ffmpeg falhou (código {r.codigo}) em {nome}:\n{(r.stderr or '').strip()[-900:]}",
                            dica="Comando: " + " ".join(_citar(c) for c in cmd))
        if not tmp.is_file():
            raise da.DAErro(f"o ffmpeg terminou sem erro mas não gravou nada em {nome} (nenhum quadro chegou à saída).",
                            dica="Causas comuns: -ss/instante depois do fim do vídeo, -t 0, filtro que descarta todos os quadros. "
                                 "Comando: " + " ".join(_citar(c) for c in cmd))
        os.replace(tmp, saida)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
    return saida


def _citar(s: str) -> str:
    return s if re.fullmatch(r"[\w./:=+,-]+", s) else "'" + s.replace("'", "'\\''") + "'"


def fps_texto(fps) -> str:
    f = da.fps_racional(fps) if not isinstance(fps, Fraction) else fps
    return f"{f.numerator}/{f.denominator}"


def _da(da_obj=None, da=None, de=None) -> "da.DA":
    """A DA em uso: o objeto passado (`da_obj=` ou o sinônimo `da=`) ou a do projeto que contém `de` / o diretório atual."""
    d = da_obj if da_obj is not None else da
    if isinstance(d, _NUCLEO.DA):
        return d
    if d is not None:
        return _NUCLEO.carregar(d)
    return _NUCLEO._da_para(Path(de).resolve()) if de is not None else _NUCLEO.carregar()


def nome_do_formato(d: "da.DA", largura: int, altura: int) -> str:
    """Nome do formato da DA com essas dimensões ('vertical', 'horizontal'…) ou 'LxA'. É o `formato` dos carimbos."""
    for nome, f in d["formatos"].items():
        if isinstance(f, dict) and f.get("largura") == largura and f.get("altura") == altura:
            return nome
    return f"{largura}x{altura}"


def fps_do_formato(d: "da.DA", formato="horizontal") -> Fraction:
    """fps (Fraction) de um formato da DA; para 'LxA' ou formato sem fps, o da orientação equivalente."""
    try:
        f = d.formato(formato)[2] if isinstance(formato, str) and not re.fullmatch(r"\d+x\d+", formato) else None
    except da.DAErro:
        f = None
    if f is None:
        L, A = d._dimensoes(formato) if isinstance(formato, str) else formato
        f = d.formato("horizontal" if L > A else "vertical" if L < A else "quadrado")[2]
    return f or Fraction(30000, 1001)


def args_encode(fps="30000/1001", crf: int = 18, preset: str = "medium", audio: bool = True, bitrate_audio: str = "192k",
                faststart: bool = True, threads: str = THREADS, formato: str = "horizontal") -> list[str]:
    """Encode padrão da casa: H.264 yuv420p marcado bt709 (+faststart), fps racional, AAC 48 kHz estéreo.
    `fps` pode ser a própria DA — args_encode(d, formato="vertical") usa o fps do formato — ou um valor
    ("30000/1001", 25, Fraction). Sem argumento vale 30000/1001, o padrão dos presets."""
    if isinstance(fps, da.DA):
        f = fps_do_formato(fps, formato)
    else:
        f = da.fps_racional(fps) if not isinstance(fps, Fraction) else fps
    args = ["-c:v", "libx264", "-preset", preset, "-crf", str(int(crf)), "-pix_fmt", "yuv420p", "-threads", threads,
            "-x264-params", "colorprim=bt709:transfer=bt709:colormatrix=bt709:range=tv", "-color_range", "tv",
            "-r", f"{f.numerator}/{f.denominator}", "-video_track_timescale", str(f.numerator)]
    if audio:
        args += ["-c:a", "aac", "-b:a", bitrate_audio, "-ar", "48000", "-ac", "2"]
    else:
        args += ["-an"]
    if faststart:
        args += ["-movflags", "+faststart"]
    return args


def args_png_para_yuv420(fps="30000/1001") -> list[str]:
    """Entrada de quadros PNG por pipe (image2pipe) para compor com args_encode. Como termina em `-i -`, só funciona
    com `executar(..., entrada=<iterável de PNGs em bytes>)`: é o `entrada` que escreve e FECHA o stdin do ffmpeg."""
    f = da.fps_racional(fps) if not isinstance(fps, Fraction) else fps
    return ["-f", "image2pipe", "-framerate", f"{f.numerator}/{f.denominator}", "-vcodec", "png", "-i", "-"]


# ───────────────────────────────────────────────────────────────── filtros ──
def filtro_tratamento(d: "da.DA", formato="horizontal", parte: str = "completa") -> str:
    """Cadeia de filtros do tratamento da DA (lida do grade.json compilado; recalcula para LxA fora dos formatos).
    "null" quando não há nada a fazer — pode entrar direto em -vf."""
    if isinstance(formato, str) and not re.fullmatch(r"\d+x\d+", formato):
        try:
            g = da.ler_json(d.build / "grade.json")
            f = g["formatos"].get(formato)
            if f and g.get("da_sha256") == d.sha256:
                return {"completa": f["cadeia"], "cor": f["cadeia_cor"], "acabamento": f["cadeia_acabamento"]}[parte]
        except (da.DAErro, KeyError):
            pass
        return d.grade(formato, parte=parte)
    if isinstance(formato, str):
        L, A = (int(x) for x in formato.lower().split("x"))
    else:
        L, A = formato
    return d.grade(L, A, parte=parte)


def _par(x: float) -> int:
    return max(2, int(round(x / 2)) * 2)


def filtro_recorte(origem, formato, ancora: str = "centro", foco=None, zoom: float = 1.0) -> dict:
    """scale+crop de origem (L, A) para formato (L, A) ou nome LxA, com dimensões pares.

    ancora: centro | rosto | terco_esq | terco_dir (tratamento.recorte.ancora da DA). `foco` = (fx, fy) em frações
    da origem (ex.: centro do rosto detectado) sobrepõe a âncora. zoom > 1 aproxima antes de cortar.
    Devolve {'filtro', 'escala': (w, h), 'corte': (x, y, w, h)}."""
    if isinstance(origem, str):
        origem = tuple(int(x) for x in origem.lower().split("x"))
    if isinstance(formato, str):
        formato = tuple(int(x) for x in formato.lower().split("x"))
    (ol, oa), (fl, fa) = origem, formato
    if min(ol, oa, fl, fa) <= 0:
        raise da.DAErro("filtro_recorte: dimensões precisam ser positivas")
    s = max(fl / ol, fa / oa) * max(1.0, zoom)
    sw, sh = _par(ol * s), _par(oa * s)
    sw, sh = max(sw, fl), max(sh, fa)
    if foco is None:
        fx, fy = {"centro": (0.5, 0.5), "rosto": (0.5, 0.36), "terco_esq": (1 / 3, 0.42), "terco_dir": (2 / 3, 0.42)}.get(ancora, (0.5, 0.5))
    else:
        fx, fy = float(foco[0]), float(foco[1])
    x = int(round(min(max(0, fx * sw - fl / 2), sw - fl)))
    y = int(round(min(max(0, fy * sh - fa / 2), sh - fa)))
    x -= x % 2
    y -= y % 2
    filtro = f"scale={sw}:{sh}:flags=lanczos,crop={fl}:{fa}:{x}:{y}"
    return {"filtro": filtro, "escala": (sw, sh), "corte": (x, y, fl, fa)}


MODOS_ENCAIXE = ("desfocado", "recorte", "faixas")


def filtro_encaixe(origem, formato, modo: str | None = None, d: "da.DA | None" = None, ancora: str | None = None, foco=None,
                   desfoque: float | None = None, escurecer: float | None = None, cor: str | None = None) -> dict:
    """Como um vídeo de OUTRA proporção entra no quadro (ex.: 16:9 → 9:16). Uma entrada, uma saída: serve em -vf.

    modo (padrão: tratamento.encaixe.modo da DA, ou 'desfocado'):
      'desfocado'  o vídeo INTEIRO, na largura (ou altura) do quadro, por cima de uma cópia dele ampliada, desfocada
                   (tratamento.encaixe.desfoque = sigma em fração do lado menor da saída) e escurecida (encaixe.escurecer);
      'recorte'    amplia e corta (o mesmo de filtro_recorte, com tratamento.recorte.ancora ou `ancora`/`foco`);
      'faixas'     o vídeo inteiro com faixas na cor tratamento.encaixe.cor.
    Não confundir com tratamento.desfoque, que borra o footage INTEIRO na cadeia de acabamento.
    Devolve {'filtro', 'modo', 'janela': (x, y, w, h) onde o vídeo original ficou no quadro, 'saida': (L, A)}."""
    if isinstance(origem, str):
        origem = tuple(int(x) for x in origem.lower().split("x"))
    if isinstance(formato, str):
        formato = d._dimensoes(formato) if d is not None and not re.fullmatch(r"\d+x\d+", formato.lower()) else tuple(int(x) for x in formato.lower().split("x"))
    (ol, oa), (fl, fa) = origem, formato
    if min(ol, oa, fl, fa) <= 0:
        raise da.DAErro("filtro_encaixe: dimensões precisam ser positivas")
    enc = (d["tratamento"].get("encaixe") if d is not None else None) or {}
    modo = modo or enc.get("modo") or "desfocado"
    if modo not in MODOS_ENCAIXE:
        raise da.DAErro(f"filtro_encaixe: modo {modo!r} inválido ({', '.join(MODOS_ENCAIXE)})")
    if modo == "recorte":
        r = filtro_recorte(origem, formato, ancora or (d["tratamento"]["recorte"]["ancora"] if d is not None else "centro"), foco)
        return {"filtro": r["filtro"], "modo": modo, "janela": (0, 0, fl, fa), "saida": (fl, fa)}
    k = min(fl / ol, fa / oa)                                   # o vídeo inteiro cabe no quadro
    w, h = min(fl, _par(ol * k)), min(fa, _par(oa * k))
    x, y = (fl - w) // 2, (fa - h) // 2
    if modo == "faixas":
        hexa = d.cor(cor or enc.get("cor") or "fundo") if d is not None else None
        if hexa is None:
            raise da.DAErro("filtro_encaixe(modo='faixas') precisa da DA (d=…) para a cor das faixas")
        filtro = f"scale={w}:{h}:flags=lanczos,setsar=1,pad={fl}:{fa}:{x}:{y}:color=0x{hexa.lstrip('#')}"
        return {"filtro": filtro, "modo": modo, "janela": (x, y, w, h), "saida": (fl, fa)}
    sig = float(desfoque if desfoque is not None else enc.get("desfoque", 0.035)) * min(fl, fa)
    esc = float(escurecer if escurecer is not None else enc.get("escurecer", 0.25))
    # fundo: preenche o quadro a 1/4 da resolução, desfoca lá (4× menos pixels, sigma 4× menor: mesmo resultado, bem mais rápido) e amplia
    bl, ba = _par(fl / 4), _par(fa / 4)
    cobre = max(bl / ol, ba / oa)
    sl, sa = max(bl, _par(ol * cobre)), max(ba, _par(oa * cobre))
    fundo = f"scale={sl}:{sa}:flags=bilinear,crop={bl}:{ba},gblur=sigma={da._num(max(0.5, sig / 4), 3)}"
    if esc > 1e-6:
        fundo += f",lutyuv=y='clip((val-minval)*{da._num(max(0.0, 1 - esc), 3)}+minval,minval,maxval)'"
    fundo += f",scale={fl}:{fa}:flags=bilinear"
    filtro = (f"split[enc_a][enc_b];[enc_a]{fundo}[enc_f];[enc_b]scale={w}:{h}:flags=lanczos[enc_v];"
              f"[enc_f][enc_v]overlay={x}:{y},setsar=1")
    return {"filtro": filtro, "modo": modo, "janela": (x, y, w, h), "saida": (fl, fa)}


# ──────────────────────────────────────────────────────────────── loudness ──
def _alvo_loudness(d: "da.DA", tipo: str) -> dict:
    alvos = d["som"]["loudness"]
    if tipo not in alvos:
        raise da.DAErro(f"som.loudness não tem {tipo!r} ({', '.join(alvos)})")
    return alvos[tipo]


def filtro_loudnorm(d: "da.DA", tipo: str = "longo", lra: float = 11.0, medida: dict | None = None, folga_pico: float = 0.0) -> str:
    """Filtro de áudio que leva a peça ao alvo de som.loudness.<tipo> da DA ('longo' ou 'curto').

    Sem `medida`: passagem única, dinâmica — "loudnorm=I=-14:TP=-1:LRA=11". Serve a peça longa; em peça de poucos
    segundos erra o alvo (medido num corte de 4 s: −15,1 LUFS para alvo −14).
    Com `medida` = medir_para_loudnorm(arquivo, d, tipo): segunda passagem com os valores medidos e ganho linear
    (measured_I/TP/LRA/thresh + offset + linear=true), que acerta o alvo também em peça curta.
    folga_pico: dB a menos no teto de pico pedido ao filtro (0 = o pico_real da DA). O AAC devolve o pico uns 0,2 dB
    acima do que o limitador deixou (medido: −0,8 dBTP para teto −1); folga_pico=0.5 deixa a peça codificada abaixo do alvo.
    Confira o resultado com conferir_loudness(d, arquivo, tipo)."""
    alvo = _alvo_loudness(d, tipo)
    base = f"loudnorm=I={da._num(alvo['lufs'], 2)}:TP={da._num(float(alvo['pico_real']) - abs(float(folga_pico)), 2)}:LRA={da._num(lra, 2)}"
    if not medida:
        return base
    try:
        return (f"{base}:measured_I={da._num(medida['input_i'], 2)}:measured_TP={da._num(medida['input_tp'], 2)}"
                f":measured_LRA={da._num(medida['input_lra'], 2)}:measured_thresh={da._num(medida['input_thresh'], 2)}"
                f":offset={da._num(medida.get('target_offset', 0.0), 2)}:linear=true")
    except (KeyError, TypeError, ValueError):
        raise da.DAErro("filtro_loudnorm: `medida` precisa ser o dict de video.medir_para_loudnorm(arquivo, d, tipo)")


def medir_para_loudnorm(arquivo, d: "da.DA", tipo: str = "longo", lra: float = 11.0, inicio: float | None = None,
                        duracao: float | None = None, folga_pico: float = 0.0) -> dict:
    """Primeira passagem do loudnorm (só áudio, sob a trava): {'input_i', 'input_tp', 'input_lra', 'input_thresh',
    'target_offset'} em números — o `medida` de filtro_loudnorm. `inicio`/`duracao` medem só o trecho que será usado;
    passe aqui a mesma `folga_pico` da segunda passagem.
    Levanta DAErro se não houver áudio ou se o trecho for silêncio (não há o que normalizar)."""
    arquivo = Path(str(arquivo)).expanduser()
    if not sondar(arquivo)["tem_audio"]:
        raise da.DAErro(f"{arquivo.name} não tem trilha de áudio")
    args = [FFMPEG, "-hide_banner", "-nostdin", "-nostats"]
    if inicio is not None:
        args += ["-ss", da._num(inicio, 3)]
    if duracao is not None:
        args += ["-t", da._num(duracao, 3)]
    args += ["-i", str(arquivo), "-map", "0:a:0", "-af", filtro_loudnorm(d, tipo, lra, folga_pico=folga_pico) + ":print_format=json", "-f", "null", "-"]
    r = trava.rodar(args, rotulo=f"loudnorm (medida) {arquivo.name}", capturar=True, inatividade=trava.inatividade_padrao(INATIVIDADE_PADRAO))
    if r.motivo:
        raise da.DAErro(f"a medição para o loudnorm de {arquivo.name} travou: {trava.descrever_vigia(r)}")
    txt = r.stderr or ""
    ini, fim = txt.rfind("{"), txt.rfind("}")
    try:
        bruto = json.loads(txt[ini:fim + 1]) if 0 <= ini < fim else {}
        medida = {k: float(bruto[k]) for k in ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset")}
    except (ValueError, KeyError):
        raise da.DAErro(f"não consegui medir {arquivo.name} para o loudnorm: {txt.strip()[-300:]}")
    if any(math.isinf(v) or math.isnan(v) for v in medida.values()):
        raise da.DAErro(f"{arquivo.name}: o trecho é silêncio (loudness −inf); não há o que normalizar")
    return medida


def medir_loudness(arquivo, inicio: float | None = None, duracao: float | None = None) -> dict:
    """ebur128: {'lufs' (I integrado), 'lra', 'pico_real' (dBTP), 'limiar'}. Levanta DAErro se não houver áudio."""
    arquivo = Path(str(arquivo)).expanduser()
    if not sondar(arquivo)["tem_audio"]:
        raise da.DAErro(f"{arquivo.name} não tem trilha de áudio")
    args = [FFMPEG, "-hide_banner", "-nostdin", "-nostats"]
    if inicio is not None:
        args += ["-ss", da._num(inicio, 3)]
    if duracao is not None:
        args += ["-t", da._num(duracao, 3)]
    args += ["-i", str(arquivo), "-map", "0:a:0", "-af", "ebur128=peak=true", "-f", "null", "-"]
    r = trava.rodar(args, rotulo=f"loudness {arquivo.name}", capturar=True, inatividade=trava.inatividade_padrao(INATIVIDADE_PADRAO))
    if r.motivo:
        raise da.DAErro(f"a medição de loudness de {arquivo.name} travou: {trava.descrever_vigia(r)}")
    txt = r.stderr or ""
    resumo = txt[txt.rfind("Summary:"):] if "Summary:" in txt else txt

    def pegar(padrao):
        m = re.search(padrao, resumo)
        return float(m.group(1)) if m else None

    saida = {"lufs": pegar(r"I:\s*(-?[\d.]+)\s*LUFS"), "limiar": pegar(r"Threshold:\s*(-?[\d.]+)\s*LUFS"),
             "lra": pegar(r"LRA:\s*(-?[\d.]+)\s*LU"), "pico_real": pegar(r"Peak:\s*(-?[\d.]+)\s*dBFS")}
    if saida["lufs"] is None:
        raise da.DAErro(f"não consegui medir o loudness de {arquivo.name}: {txt.strip()[-300:]}")
    return saida


def conferir_loudness(d: "da.DA", arquivo, tipo: str = "longo", tolerancia: float = 1.0) -> dict:
    """Compara com som.loudness.<tipo> da DA. Devolve {'ok', 'medido', 'alvo', 'desvio_lufs', 'estoura_pico'}."""
    alvo = d["som"]["loudness"][tipo]
    m = medir_loudness(arquivo)
    desvio = m["lufs"] - alvo["lufs"]
    estoura = m["pico_real"] is not None and m["pico_real"] > alvo["pico_real"] + 0.1
    return {"ok": abs(desvio) <= tolerancia and not estoura, "medido": m, "alvo": alvo, "desvio_lufs": round(desvio, 2), "estoura_pico": estoura}


# ─────────────────────────────────────────────────────────────── quadros ──
def extrair_quadro(arquivo, t: float, saida, largura: int | None = None, tratamento: str | None = None) -> Path:
    """Um quadro PNG em t segundos (opcionalmente redimensionado e com uma cadeia de filtros antes)."""
    arquivo = Path(str(arquivo)).expanduser()
    vf = []
    if tratamento and tratamento != "null":
        vf.append(tratamento)
    if largura:
        vf.append(f"scale={int(largura)}:-2:flags=lanczos")
    args = ["-ss", da._num(max(0.0, float(t)), 3), "-i", str(arquivo), "-frames:v", "1", "-update", "1", "-threads", THREADS]
    if vf:
        args += ["-vf", ",".join(vf)]
    return executar(args, saida, rotulo=f"quadro {arquivo.name} @ {t:.2f}s")


def folha_de_contato(quadros, legendas=None, saida="folha.png", colunas: int = 4, largura_celula: int = 480, da_obj: "da.DA | None" = None,
                     titulo: str | None = None, proporcao=None, da=None):
    """Folha de contato em PIL: miniaturas (arquivos PNG/JPG) com legenda embaixo, tipografia da DA quando houver.

    proporcao: largura/altura da célula — número (9 / 16), par (9, 16) ou texto "9:16"; None = a do PRIMEIRO quadro
    (peça vertical gera célula vertical). Cada quadro entra INTEIRO na célula (nunca é cortado): quem tem outra
    proporção fica centrado sobre a cor de superfície — as margens seguras do topo e da base continuam à vista."""
    from PIL import Image, ImageOps
    import texto
    quadros = [Path(str(q)) for q in quadros]
    legendas = list(legendas or [""] * len(quadros))
    if len(legendas) < len(quadros):
        legendas += [""] * (len(quadros) - len(legendas))
    d = da_obj if da_obj is not None else da if isinstance(da, _NUCLEO.DA) else None
    if d is None:
        try:
            d = _NUCLEO.carregar()
        except _NUCLEO.DAErro:
            d = None
    fundo = d.rgba("fundo") if d else (18, 18, 18, 255)       # da-livre: folha de conferência fora de qualquer projeto (sem DA)
    cor_celula = d.rgba("superficie") if d else (36, 36, 36, 255)   # da-livre: idem
    cor_txt = "texto_suave" if d else None
    razao = None
    if proporcao is not None:
        if isinstance(proporcao, str):
            a, b = re.split(r"[:x/]", proporcao.strip())
            razao = float(a) / float(b)
        elif isinstance(proporcao, (tuple, list)):
            razao = float(proporcao[0]) / float(proporcao[1])
        else:
            razao = float(proporcao)
    else:
        for q in quadros:
            try:
                with Image.open(q) as im:
                    im = ImageOps.exif_transpose(im)
                    razao = im.width / im.height
                break
            except OSError:
                continue
    razao = razao or 16 / 9
    margem, respiro = 32, 14
    colunas = max(1, min(colunas, len(quadros) or 1))
    tam_leg = max(12, int(largura_celula * 0.034))
    alt_cel = max(2, int(round(largura_celula / razao)))
    alt_leg = int(tam_leg * 2.8)
    linhas = math.ceil(len(quadros) / colunas)
    alt_titulo = int(max(largura_celula, 240) * 0.12) if titulo else 0
    W = margem * 2 + colunas * largura_celula + (colunas - 1) * respiro
    H = margem * 2 + alt_titulo + linhas * (alt_cel + alt_leg) + (linhas - 1) * respiro
    img = Image.new("RGBA", (W, H), fundo)
    est_leg = texto.Estilo.do_papel(d, "dados", tam_leg, cor=cor_txt) if d else None
    if titulo:
        if d:
            tt, _ = texto.desenhar(titulo, texto.Estilo.do_papel(d, "subtitulo", int(alt_titulo * 0.42), cor="texto"), largura_max=W - 2 * margem)
            img.alpha_composite(tt, (margem, margem))
    for i, (q, leg) in enumerate(zip(quadros, legendas)):
        c, l = i % colunas, i // colunas
        x = margem + c * (largura_celula + respiro)
        y = margem + alt_titulo + l * (alt_cel + alt_leg + respiro)
        celula = Image.new("RGBA", (largura_celula, alt_cel), cor_celula)
        try:
            mini = ImageOps.exif_transpose(Image.open(q)).convert("RGBA")
            mini = ImageOps.contain(mini, (largura_celula, alt_cel), Image.LANCZOS)      # inteiro, sem cortar
            celula.alpha_composite(mini, ((largura_celula - mini.width) // 2, (alt_cel - mini.height) // 2))
        except OSError:
            celula = Image.new("RGBA", (largura_celula, alt_cel), (60, 60, 60, 255))     # da-livre: marcador de quadro ilegível
        img.alpha_composite(celula, (x, y))
        if leg and est_leg:
            tl, _ = texto.desenhar(str(leg), est_leg, largura_max=largura_celula, max_linhas=2)
            img.alpha_composite(tl, (x, y + alt_cel + int(tam_leg * 0.5)))
    saida = Path(str(saida)).expanduser()
    saida.parent.mkdir(parents=True, exist_ok=True)
    tmp = saida.with_name(saida.stem + ".parcial.png")
    img.convert("RGB").save(tmp, "PNG", optimize=True)
    os.replace(tmp, saida)
    return saida


# ─────────────────────────────────────────────────────────────── overlay ──
def entrada_com_alfa(arquivo) -> list[str]:
    """Args de entrada que preservam o alfa: WebM VP9 precisa de -c:v libvpx-vp9 ANTES do -i."""
    arquivo = Path(str(arquivo))
    if arquivo.suffix.lower() in EXT_ALFA_WEBM:
        return ["-c:v", "libvpx-vp9", "-i", str(arquivo)]
    return ["-i", str(arquivo)]


def _carimbar_saida(d, saida: Path, ferramenta: str, parametros: dict, insumos, formato: str | None = None) -> Path:
    """Carimbo de uma composição: formato lido da PRÓPRIA saída (não da base) e proveniência dos insumos (D14)."""
    if formato is None:
        s = sondar(saida)
        formato = nome_do_formato(d, s["largura"], s["altura"])
    return _NUCLEO.carimbar(saida, ferramenta, formato, parametros, "n/a", da=d, insumos=insumos)


def _args_trecho(inicio, duracao) -> list[str]:
    args = []
    if inicio is not None and float(inicio) > 0:
        args += ["-ss", _NUCLEO._num(float(inicio), 3)]
    if duracao is not None:
        if float(duracao) <= 0:
            raise _NUCLEO.DAErro("duracao precisa ser maior que zero")
        args += ["-t", _NUCLEO._num(float(duracao), 3)]
    return args


def compor_overlay(base, overlay, saida, t0: float = 0.0, x: int | str = 0, y: int | str = 0, fim: float | None = None,
                   da_obj: "da.DA | None" = None, tratamento_base: str | None = None, crf: int = 18, carimbar: bool = True,
                   fps=None, escala_overlay: str | None = None, inicio: float | None = None, duracao: float | None = None,
                   filtro_base: str | None = None, da=None) -> dict:
    """Compõe um overlay com alfa (WebM VP9, MOV ProRes 4444, PNG/sequência) sobre o vídeo base a partir de t0.

    inicio, duracao : trecho da BASE a usar (segundos), sem encode intermediário; t0 e fim contam a partir desse início.
    tratamento_base : cadeia ffmpeg aplicada à base antes da composição (ex.: filtro_tratamento(d, 'horizontal'), ou
                      filtro_recorte(...)['filtro'] + ',' + tratamento). `filtro_base` é sinônimo.
    A saída tem sempre os quadros da base (PNG sem `fim` fica até o último quadro). O áudio da base é copiado
    (recodificado em AAC quando há `inicio`, para o corte cair no quadro certo). O carimbo leva o formato da SAÍDA
    (um recorte para 540×960 sai 'vertical'/'540x960', não o formato da base) e a proveniência de base e overlay:
    overlay renderizado com --sem-auditoria deixa a composição "pulada". Devolve {'saida', 'filtro', 'carimbo'}."""
    base, overlay, saida = Path(str(base)).expanduser(), Path(str(overlay)).expanduser(), Path(str(saida)).expanduser()
    tratamento_base = tratamento_base or filtro_base
    info = sondar(base)
    fps_f = fps or info["fps"] or Fraction(30000, 1001)
    dur_base = float(duracao) if duracao is not None else max(0.04, float(info["duracao"] or 0) - float(inicio or 0))
    ov_args = entrada_com_alfa(overlay)
    imagem = overlay.suffix.lower() in _NUCLEO.EXT_IMAGEM
    if imagem:
        # imagem parada: repete só pelo tempo da base. Com `-loop 1` sem limite + `-shortest`, a saída perdia os
        # últimos quadros (base de 30 quadros saía com 28): quem decide o fim é a base, nunca o overlay.
        ov_args = ["-loop", "1", "-framerate", fps_texto(fps_f), "-t", _NUCLEO._num(dur_base + 0.5, 3), *ov_args]
    cadeia_base = f"[0:v]{tratamento_base}[b]" if tratamento_base and tratamento_base != "null" else "[0:v]null[b]"
    ov = "[1:v]format=rgba"
    if escala_overlay:
        ov += f",scale={escala_overlay}"
    ov += f",setpts=PTS-STARTPTS+{_NUCLEO._num(t0, 3)}/TB[o]"
    habilitado = f":enable='between(t,{_NUCLEO._num(t0, 3)},{_NUCLEO._num(fim, 3)})'" if fim is not None else f":enable='gte(t,{_NUCLEO._num(t0, 3)})'"
    filtro = f"{cadeia_base};{ov};[b][o]overlay={x}:{y}:eof_action=pass:format=auto{habilitado},format=yuv420p[v]"
    trecho = _args_trecho(inicio, duracao)
    args = [*trecho, "-i", str(base), *ov_args, "-filter_complex", filtro, "-map", "[v]"]
    com_audio = bool(info["tem_audio"])
    if com_audio:
        args += ["-map", "0:a?"] + (["-c:a", "copy"] if not trecho else [])
    args += [a for a in args_encode(fps_f, crf=crf, audio=com_audio and bool(trecho)) if a != "-an"]
    if duracao is not None:
        args += ["-t", _NUCLEO._num(float(duracao), 3)]
    executar(args, saida, rotulo=f"overlay {overlay.name} sobre {base.name}")
    carimbo = None
    if carimbar:
        d = _da(da_obj, da, de=saida.parent)
        carimbo = _carimbar_saida(d, saida, "video.py compor_overlay",
                                  {"base": base.name, "overlay": overlay.name, "t0": t0, "fim": fim, "x": x, "y": y, "inicio": inicio,
                                   "duracao": duracao, "tratamento_base": tratamento_base}, [base, overlay])
    return {"saida": saida, "filtro": filtro, "carimbo": carimbo}


# ───────────────────────────────────────────── quadros PIL → vídeo (D12) ──
CODECS = {
    # nome: (extensões, tem alfa, pix_fmt de entrada do pipe, argumentos de encode sem fps)
    "h264": ((".mp4", ".mov", ".m4v"), False, "rgb24"),
    "vp9alfa": ((".webm",), True, "rgba"),
    "prores4444": ((".mov",), True, "rgba"),
}


def args_codec(codec: str, fps, crf: int | None = None, audio: bool = False, threads: str = THREADS) -> list[str]:
    """Argumentos de SAÍDA de cada codec da casa (os mesmos do motor): 'h264' (opaco, yuv420p bt709 +faststart),
    'vp9alfa' (WebM com alfa, para compor via ffmpeg) e 'prores4444' (MOV com alfa, para o Premiere)."""
    f = _NUCLEO.fps_racional(fps) if not isinstance(fps, Fraction) else fps
    r = f"{f.numerator}/{f.denominator}"
    if codec == "h264":
        return ["-vf", "scale=in_range=full:out_range=tv:out_color_matrix=bt709:out_primaries=bt709:out_transfer=bt709,format=yuv420p",
                *args_encode(f, crf=17 if crf is None else crf, audio=audio, threads=threads)]
    som = ["-c:a", "libopus", "-b:a", "160k"] if audio and codec == "vp9alfa" else ["-c:a", "pcm_s16le"] if audio else ["-an"]
    if codec == "vp9alfa":
        return ["-vf", "format=rgba", "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-auto-alt-ref", "0", "-crf", str(24 if crf is None else int(crf)),
                "-b:v", "0", "-deadline", "good", "-cpu-used", "2", "-row-mt", "1", "-threads", threads, "-r", r, *som]
    if codec == "prores4444":
        return ["-vf", "format=rgba", "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le", "-vendor", "apl0",
                "-qscale:v", str(11 if crf is None else int(crf)), "-threads", threads, "-r", r, "-video_track_timescale", str(f.numerator), *som]
    raise _NUCLEO.DAErro(f"codec {codec!r} desconhecido ({', '.join(CODECS)})")


class _Abortado(Exception):
    """O produtor dos quadros desistiu (exceção dentro do `with`): o ffmpeg é morto e nada é gravado."""


class Codificador:
    """Quadros PIL (ou bytes RGBA) → vídeo, por pipe para UM ffmpeg, sob a trava global. Gerenciador de contexto:

        with video.Codificador("animacoes/onda.webm", formato="vertical", da_obj=d) as cod:     # .webm → vp9alfa
            for i in range(n):
                cod.escrever(desenhar_quadro(i))          # PIL.Image (qualquer modo), bytes RGBA L×A×4 ou array numpy
        cod.resultado → {'saida', 'quadros', 'carimbo', 'largura', 'altura', 'fps', 'codec'}

    codec    : 'h264' (.mp4, opaco), 'vp9alfa' (.webm, alfa), 'prores4444' (.mov, alfa); padrão pela extensão da saída.
               Em h264, quadro com transparência é achatado sobre a cor `fundo` da DA (token; padrão 'fundo').
    formato  : nome de formato da DA ou 'LxA' — dá o tamanho e o fps; ou passe largura/altura/fps. Sem tamanho, vale o
               do primeiro quadro; todos têm de ter o mesmo.
    audio    : arquivo de áudio para muxar junto (opcional).
    Garantias: a trava é pedida no `with` e solta na saída dele, aconteça o que acontecer; o ffmpeg roda em grupo de
    processos próprio, com o stderr drenado e o vigia de inatividade (padrão 120 s sem progresso — quadro nenhum
    chegando, ffmpeg parado — mata o ffmpeg e a escrita seguinte levanta DAErro); a saída nasce `<nome>.parcial<ext>`
    e só vira o arquivo final com código 0; exceção dentro do `with` (ou SIGTERM) mata o ffmpeg e não deixa nada;
    a peça sai carimbada (`ferramenta`, `parametros`, `insumos`), com a identidade da DA lida no início."""

    def __init__(self, saida, largura: int | None = None, altura: int | None = None, fps=None, codec: str | None = None,
                 da_obj: "da.DA | None" = None, formato: str | None = None, crf: int | None = None, audio=None, fundo: str = "fundo",
                 carimbar: bool = True, ferramenta: str = "video.py Codificador", parametros: dict | None = None, insumos=None,
                 rotulo: str | None = None, inatividade: float | None = INATIVIDADE_PADRAO, espera_max: float | None = None,
                 fila: int = 4, da=None):
        self.saida = Path(str(saida)).expanduser()
        ext = self.saida.suffix.lower()
        self.codec = codec or {".webm": "vp9alfa", ".mov": "prores4444"}.get(ext, "h264")
        if self.codec not in CODECS:
            raise _NUCLEO.DAErro(f"Codificador: codec {self.codec!r} desconhecido ({', '.join(CODECS)})")
        if ext not in CODECS[self.codec][0]:
            raise _NUCLEO.DAErro(f"Codificador: {self.codec} precisa de saída {' ou '.join(CODECS[self.codec][0])} (veio {ext or 'sem extensão'})")
        self._d_pedida, self._da_alias = da_obj, da
        self.d = None
        self.formato, self.largura, self.altura, self._fps = formato, largura, altura, fps
        self.crf, self.audio, self.fundo = crf, (Path(str(audio)).expanduser() if audio else None), fundo
        self._carimbar, self.ferramenta, self.parametros, self.insumos = carimbar, ferramenta, dict(parametros or {}), list(insumos or [])
        self.rotulo = rotulo or f"codificar {self.saida.name}"
        self.inatividade, self.espera_max = inatividade, espera_max
        self.quadros = 0
        self.resultado: dict | None = None
        self._q: queue.Queue = queue.Queue(maxsize=max(1, int(fila)))
        self._fio: threading.Thread | None = None
        self._erro: BaseException | None = None
        self._trava = None
        self._cor_fundo = None

    # -- ciclo de vida ---------------------------------------------------------
    def __enter__(self) -> "Codificador":
        if self._carimbar or self.formato or self.codec == "h264":
            try:
                self.d = _da(self._d_pedida, self._da_alias, de=self.saida.parent if self.saida.parent.exists() else None)
            except _NUCLEO.SemDA:
                if self._carimbar or (self.formato and not re.fullmatch(r"\d+x\d+", str(self.formato))):
                    raise
        if self.formato and not (self.largura and self.altura):
            self.largura, self.altura = (self.d._dimensoes(self.formato) if self.d is not None else
                                         tuple(int(x) for x in str(self.formato).lower().split("x")))
        self.fps = None if self._fps is None else _NUCLEO.fps_racional(self._fps) if not isinstance(self._fps, Fraction) else self._fps
        if self.d is not None:
            self._cor_fundo = self.d.rgb(self.fundo)
        if self.audio is not None and not self.audio.is_file():
            raise _NUCLEO.DAErro(f"Codificador: áudio não encontrado: {self.audio}")
        self._trava = trava.Trava(rotulo=self.rotulo, espera_max=self.espera_max)
        self._trava.adquirir()                                   # a fila da máquina é aqui; PIL e ffmpeg ficam sob a mesma trava
        return self

    def _gerador(self):
        while True:
            item = self._q.get()
            if item is None:
                return
            if item is _Abortado:
                raise _Abortado()
            yield item

    def _iniciar(self) -> None:
        if self.largura % 2 or self.altura % 2:
            raise _NUCLEO.DAErro(f"Codificador: {self.largura}×{self.altura} — largura e altura precisam ser pares")
        if self.fps is None:                                     # fps do formato da DA (ou da orientação do quadro); sem DA, 30000/1001
            self.fps = fps_do_formato(self.d, self.formato or (self.largura, self.altura)) if self.d is not None else Fraction(30000, 1001)
        pix = CODECS[self.codec][2]
        args = ["-f", "rawvideo", "-pix_fmt", pix, "-s", f"{self.largura}x{self.altura}", "-framerate", fps_texto(self.fps), "-i", "-"]
        if self.audio is not None:
            args += ["-i", str(self.audio), "-map", "0:v:0", "-map", "1:a:0", "-shortest"]
        args += args_codec(self.codec, self.fps, self.crf, audio=self.audio is not None)

        def trabalho():
            try:
                executar(args, self.saida, rotulo=self.rotulo, entrada=self._gerador(), inatividade=self.inatividade)
            except BaseException as e:                           # inclusive _Abortado: quem decide o que fazer é a thread principal
                self._erro = e

        self._fio = threading.Thread(target=trabalho, name="codificador-ffmpeg", daemon=True)
        self._fio.start()

    def _bytes(self, quadro) -> bytes:
        from PIL import Image
        alfa = CODECS[self.codec][1]
        if isinstance(quadro, Image.Image):
            if not (self.largura and self.altura):
                self.largura, self.altura = quadro.size
            if quadro.size != (self.largura, self.altura):
                raise _NUCLEO.DAErro(f"Codificador: quadro {self.quadros} tem {quadro.width}×{quadro.height}, o vídeo é {self.largura}×{self.altura}")
            if alfa:
                return quadro.convert("RGBA").tobytes()
            if quadro.mode in ("RGBA", "LA", "PA") or "transparency" in quadro.info:
                base = Image.new("RGBA", quadro.size, (*(self._cor_fundo or (0, 0, 0)), 255))     # da-livre: sem DA não há cor de fundo; preto
                base.alpha_composite(quadro.convert("RGBA"))
                return base.convert("RGB").tobytes()
            return quadro.convert("RGB").tobytes()
        if hasattr(quadro, "tobytes") and hasattr(quadro, "shape"):                              # array numpy A×L×(3|4) uint8
            forma = tuple(quadro.shape)
            if not (self.largura and self.altura):
                self.altura, self.largura = forma[0], forma[1]
            if len(forma) != 3 or forma[:2] != (self.altura, self.largura) or forma[2] not in (3, 4):
                raise _NUCLEO.DAErro(f"Codificador: array {forma} não é altura×largura×3|4 de {self.largura}×{self.altura}")
            return self._bytes(Image.fromarray(quadro, "RGBA" if forma[2] == 4 else "RGB"))
        if isinstance(quadro, (bytes, bytearray, memoryview)):
            if not (self.largura and self.altura):
                raise _NUCLEO.DAErro("Codificador: para escrever bytes crus informe largura e altura (ou formato) ao criar")
            n = self.largura * self.altura
            if len(quadro) == n * 4:
                return bytes(quadro) if alfa else self._bytes(Image.frombuffer("RGBA", (self.largura, self.altura), bytes(quadro)))
            if len(quadro) == n * 3 and not alfa:
                return bytes(quadro)
            raise _NUCLEO.DAErro(f"Codificador: {len(quadro)} bytes não são um quadro RGBA de {self.largura}×{self.altura} ({n * 4} bytes)")
        raise _NUCLEO.DAErro(f"Codificador.escrever: esperava PIL.Image, bytes RGBA ou array numpy (veio {type(quadro).__name__})")

    def _levantar_erro(self) -> None:
        e = self._erro
        if e is None:
            raise _NUCLEO.DAErro(f"o ffmpeg de {self.rotulo} terminou antes do fim dos quadros (quadro {self.quadros}); nada foi gravado")
        if isinstance(e, _NUCLEO.DAErro):
            raise _NUCLEO.DAErro(f"{e.mensagem}\n(quadro {self.quadros} de {self.rotulo}; nada foi gravado)", dica=e.dica)
        raise e

    def escrever(self, quadro, repetir: int = 1) -> int:
        """Acrescenta um quadro (ou o mesmo quadro `repetir` vezes). Devolve o total escrito. Se o ffmpeg tiver morrido
        (erro, inatividade), levanta DAErro com o motivo — a escrita nunca fica esperando para sempre."""
        if self._trava is None:
            raise _NUCLEO.DAErro("Codificador: use dentro de `with video.Codificador(...) as cod:`")
        dados = self._bytes(quadro)
        if self._fio is None:
            self._iniciar()
        for _ in range(max(1, int(repetir))):
            while True:
                if not self._fio.is_alive():
                    self._levantar_erro()
                try:
                    self._q.put(dados, timeout=0.25)
                    break
                except queue.Full:
                    continue
            self.quadros += 1
        return self.quadros

    def _encerrar(self, sinal) -> None:
        if self._fio is None:
            return
        if sinal is _Abortado:                                   # esvazia a fila para o aviso chegar já
            try:
                while True:
                    self._q.get_nowait()
            except queue.Empty:
                pass
        while self._fio.is_alive():
            try:
                self._q.put(sinal, timeout=0.25)
                break
            except queue.Full:
                continue
        self._fio.join()

    def __exit__(self, tipo, valor, tb) -> bool:
        try:
            if tipo is not None:
                self._encerrar(_Abortado)                        # mata o ffmpeg; executar() apaga o .parcial
                return False
            if self._fio is None:
                raise _NUCLEO.DAErro(f"Codificador: nenhum quadro foi escrito em {self.saida.name}; nada foi gravado")
            self._encerrar(None)
            if self._erro is not None:
                self._levantar_erro()
            carimbo = None
            if self._carimbar:
                carimbo = _carimbar_saida(self.d, self.saida, self.ferramenta,
                                          {**self.parametros, "codec": self.codec, "fps": fps_texto(self.fps), "quadros": self.quadros,
                                           "largura": self.largura, "altura": self.altura, "alfa": CODECS[self.codec][1]},
                                          self.insumos + ([self.audio] if self.audio else []) or None,
                                          formato=nome_do_formato(self.d, self.largura, self.altura))
            self.resultado = {"saida": self.saida, "quadros": self.quadros, "carimbo": carimbo, "largura": self.largura, "altura": self.altura,
                              "fps": self.fps, "codec": self.codec}
            return False
        finally:
            tr, self._trava = self._trava, None
            if tr is not None:
                tr.liberar()


def codificar_quadros(quadros, saida, **opcoes) -> dict:
    """Atalho do Codificador para um iterável: codificar_quadros((desenhar(i) for i in range(n)), "x.webm", formato="vertical", da_obj=d).
    Aceita as mesmas opções (codec, fps, largura, altura, formato, audio, crf, ferramenta, parametros, insumos…).
    Devolve {'saida', 'quadros', 'carimbo', 'largura', 'altura', 'fps', 'codec'}."""
    with Codificador(saida, **opcoes) as cod:
        for q in quadros:
            cod.escrever(q)
    return cod.resultado


# ─────────────────────────────────── N overlays numa passada só (D12) ──
def compor_cues(base, cues, saida, da_obj: "da.DA | None" = None, inicio: float | None = None, duracao: float | None = None,
                tratamento_base: str | None = None, tamanho=None, crf: int = 18, fps=None, carimbar: bool = True,
                ferramenta: str = "video.py compor_cues", parametros: dict | None = None, insumos=None, da=None) -> dict:
    """Queima N estados de overlay (legendas palavra a palavra, GCs em PNG, selos) sobre a base numa ÚNICA passada de
    ffmpeg, com DUAS entradas — a base e uma faixa RGBA gerada aqui por pipe —, não uma entrada por cue.

    cues : lista de dicts {'imagem': PIL.Image ou caminho de PNG, 't0': s, 't1': s, 'x': px, 'y': px}. (x, y) = canto
           superior esquerdo da imagem no quadro de SAÍDA; imagem do tamanho do quadro dispensa x/y. Cues podem se
           sobrepor no tempo (são empilhadas na ordem da lista). Tempos contam a partir de `inicio`.
    inicio, duracao : trecho da base (s).   tratamento_base : cadeia aplicada à base antes (recorte, grade).
    tamanho : (L, A) do quadro de saída quando `tratamento_base` muda as dimensões (padrão: as da base).
    A faixa só cobre o retângulo que as cues ocupam (legenda de 660×200 px num quadro 1080×1920 = 0,5 MB por quadro,
    não 8 MB) e cada estado é composto uma vez. Medido: 64 cues em 10 s a 320×180 → 1 ffmpeg, 2 entradas, 1,6 s.
    Áudio da base preservado. Carimba com a proveniência da base e das cues que têm carimbo. Devolve
    {'saida', 'cues', 'estados', 'quadros_gerados', 'regiao': (x, y, w, h), 'filtro', 'carimbo'}."""
    from PIL import Image
    base, saida = Path(str(base)).expanduser(), Path(str(saida)).expanduser()
    info = sondar(base)
    if not info["largura"]:
        raise _NUCLEO.DAErro(f"{base.name} não tem trilha de vídeo")
    L, A = (int(tamanho[0]), int(tamanho[1])) if tamanho else (info["largura"], info["altura"])
    fps_f = _NUCLEO.fps_racional(fps) if fps is not None and not isinstance(fps, Fraction) else (fps or info["fps"] or Fraction(30000, 1001))
    dur = float(duracao) if duracao is not None else max(0.04, float(info["duracao"] or 0) - float(inicio or 0))
    lista = []
    for i, c in enumerate(cues or []):
        if not isinstance(c, dict):
            raise _NUCLEO.DAErro(f"compor_cues: cue {i} precisa ser um dict {{'imagem', 't0', 't1', 'x', 'y'}}")
        fonte = c.get("imagem", c.get("png", c.get("arquivo")))
        if fonte is None or "t0" not in c or "t1" not in c:
            raise _NUCLEO.DAErro(f"compor_cues: cue {i} sem 'imagem', 't0' ou 't1'")
        if isinstance(fonte, Image.Image):
            tam, caminho = fonte.size, None
        else:
            caminho = Path(str(fonte)).expanduser()
            try:
                with Image.open(caminho) as im:
                    tam = im.size
            except OSError as e:
                raise _NUCLEO.DAErro(f"compor_cues: cue {i}: não consegui abrir {caminho} ({e})")
        f0, f1 = int(round(float(c["t0"]) * fps_f)), int(round(float(c["t1"]) * fps_f))
        if f1 <= f0:
            continue                                             # cue mais curta que um quadro: não aparece
        lista.append({"i": i, "fonte": fonte, "caminho": caminho, "x": int(round(c.get("x", 0))), "y": int(round(c.get("y", 0))),
                      "w": tam[0], "h": tam[1], "f0": f0, "f1": f1})
    if not lista:
        raise _NUCLEO.DAErro("compor_cues: nenhuma cue com duração de pelo menos um quadro")
    # região = união das cues dentro do quadro (lados pares, para o overlay cair em pixel inteiro do yuv420p)
    x0 = max(0, min(c["x"] for c in lista)); y0 = max(0, min(c["y"] for c in lista))
    x1 = min(L, max(c["x"] + c["w"] for c in lista)); y1 = min(A, max(c["y"] + c["h"] for c in lista))
    x0 -= x0 % 2; y0 -= y0 % 2
    x1 = min(L, x1 + (x1 - x0) % 2); y1 = min(A, y1 + (y1 - y0) % 2)
    rw, rh = x1 - x0, y1 - y0
    if rw <= 0 or rh <= 0:
        raise _NUCLEO.DAErro(f"compor_cues: as cues caem fora do quadro {L}×{A} (confira x/y, ou passe tamanho=(L, A) da saída)")
    n_quadros = int(math.ceil(dur * fps_f)) + 1
    estado = {"estados": 0, "gerados": 0}

    def faixa():
        abertas: dict = {}
        ultima_chave, dados = None, None
        vazio = bytes(rw * rh * 4)
        for k in range(n_quadros):
            ativas = tuple(c["i"] for c in lista if c["f0"] <= k < c["f1"])
            if ativas != ultima_chave:
                for i in [i for i in abertas if i not in ativas]:
                    del abertas[i]
                if not ativas:
                    dados = vazio
                else:
                    tela = Image.new("RGBA", (rw, rh), (0, 0, 0, 0))
                    for c in lista:
                        if c["i"] not in ativas:
                            continue
                        if c["i"] not in abertas:
                            im = c["fonte"] if isinstance(c["fonte"], Image.Image) else Image.open(c["caminho"])
                            abertas[c["i"]] = im.convert("RGBA")
                        im = abertas[c["i"]]
                        dx, dy = c["x"] - x0, c["y"] - y0
                        tela.alpha_composite(im, (max(0, dx), max(0, dy)), (max(0, -dx), max(0, -dy)))
                    dados = tela.tobytes()
                    estado["estados"] += 1
                ultima_chave = ativas
            estado["gerados"] += 1
            yield dados

    cadeia_base = f"[0:v]{tratamento_base}[b]" if tratamento_base and tratamento_base != "null" else "[0:v]null[b]"
    filtro = f"{cadeia_base};[1:v]format=rgba,setpts=PTS-STARTPTS[o];[b][o]overlay={x0}:{y0}:eof_action=pass:format=auto,format=yuv420p[v]"
    trecho = _args_trecho(inicio, duracao)
    args = [*trecho, "-i", str(base), "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{rw}x{rh}", "-framerate", fps_texto(fps_f), "-i", "-",
            "-filter_complex", filtro, "-map", "[v]"]
    com_audio = bool(info["tem_audio"])
    if com_audio:
        args += ["-map", "0:a?"] + (["-c:a", "copy"] if not trecho else [])
    args += [a for a in args_encode(fps_f, crf=crf, audio=com_audio and bool(trecho)) if a != "-an"]
    if duracao is not None:
        args += ["-t", _NUCLEO._num(float(duracao), 3)]
    d = _da(da_obj, da, de=saida.parent) if carimbar else None       # a identidade é a do INÍCIO do trabalho
    executar(args, saida, rotulo=f"{len(lista)} cues sobre {base.name}", entrada=faixa())
    carimbo = None
    if carimbar:
        com_carimbo = [c["caminho"] for c in lista if c["caminho"] is not None and _NUCLEO.caminho_do_carimbo(c["caminho"]).is_file()]
        carimbo = _carimbar_saida(d, saida, ferramenta,
                                  {**(parametros or {}), "base": base.name, "cues": len(lista), "estados": estado["estados"], "inicio": inicio,
                                   "duracao": duracao, "tratamento_base": tratamento_base, "regiao": [x0, y0, rw, rh]},
                                  [base, *com_carimbo, *(insumos or [])])
    return {"saida": saida, "cues": len(lista), "estados": estado["estados"], "quadros_gerados": estado["gerados"],
            "regiao": (x0, y0, rw, rh), "filtro": filtro, "carimbo": carimbo}


# ───────────────────────────────────────── transições entre clipes (D13) ──
# movimento.transicoes da DA → ffmpeg. O motor usa os mesmos nomes em ctx.transicao (tabela em references/tokens.md).
XFADE = {"fade": "fade", "empurra": "slideleft", "mascara": "wipeleft", "desliza": "coverleft", "zoom": "zoomin"}


def filtro_transicao(tipo: str, duracao: float, inicio: float) -> str | None:
    """Filtro xfade de uma transição da DA (None para 'corte', que é concatenação): "xfade=transition=wipeleft:duration=0.36:offset=2.14".
    `inicio` = instante, no primeiro clipe, em que a transição começa."""
    if tipo == "corte":
        return None
    if tipo not in XFADE:
        raise _NUCLEO.DAErro(f"transição {tipo!r} não existe ({', '.join(_NUCLEO.TRANSICOES)})")
    return f"xfade=transition={XFADE[tipo]}:duration={_NUCLEO._num(duracao, 4)}:offset={_NUCLEO._num(max(0.0, inicio), 4)}"


def juntar(clipes, saida, transicao: str | None = None, da_obj: "da.DA | None" = None, duracao: float | None = None,
           formato=None, fps=None, crf: int = 18, carimbar: bool = True, ferramenta: str = "video.py juntar",
           parametros: dict | None = None, da=None) -> dict:
    """Junta clipes em sequência com a transição da DA, numa passada de ffmpeg.

    transicao : 'corte' | 'fade' | 'empurra' | 'mascara' | 'desliza' | 'zoom' — padrão movimento.transicoes.padrao;
                fora de movimento.transicoes.permitidas é DAErro (a DA decide quais existem). Uma lista dá o tipo de
                cada junção (len(clipes) − 1 itens).
    duracao   : segundos de cada transição (padrão: movimento.duracoes.media; 'corte' = 0). O xfade é linear: as
                curvas da DA valem no motor (ctx.transicao), não aqui.
    formato   : nome de formato da DA, 'LxA' ou (L, A) — padrão: as dimensões do primeiro clipe; os demais são
                redimensionados (cobrindo o quadro) para ele. fps: padrão o do formato na DA.
    Mapeamento: corte → concat; fade → xfade fade; empurra → slideleft; mascara → wipeleft; desliza → coverleft;
    zoom → zoomin. Cada transição come `duracao` segundos do total (os clipes se sobrepõem); o áudio cruza junto
    (acrossfade) e clipe sem áudio entra com silêncio. Carimba com a proveniência de cada clipe.
    Devolve {'saida', 'duracao', 'transicoes': [{tipo, inicio, duracao}], 'filtro', 'carimbo'}."""
    clipes = [Path(str(c)).expanduser() for c in clipes]
    saida = Path(str(saida)).expanduser()
    if len(clipes) < 2:
        raise _NUCLEO.DAErro("juntar: informe ao menos dois clipes")
    d = _da(da_obj, da, de=saida.parent if saida.parent.exists() else None)
    tipos = list(transicao) if isinstance(transicao, (list, tuple)) else [transicao] * (len(clipes) - 1)
    if len(tipos) != len(clipes) - 1:
        raise _NUCLEO.DAErro(f"juntar: {len(clipes)} clipes pedem {len(clipes) - 1} transição(ões), vieram {len(tipos)}")
    trans = [d.transicao(t) for t in tipos]
    for t in trans:
        if t["tipo"] != "corte" and duracao is not None:
            t["duracao"] = float(duracao)
    infos = [sondar(c) for c in clipes]
    if formato is None:
        L, A = infos[0]["largura"], infos[0]["altura"]
    elif isinstance(formato, str):
        L, A = d._dimensoes(formato)
    else:
        L, A = int(formato[0]), int(formato[1])
    fps_f = _NUCLEO.fps_racional(fps) if fps is not None and not isinstance(fps, Fraction) else (fps or fps_do_formato(d, (L, A)))
    for c, i in zip(clipes, infos):
        if not i["largura"] or not i["duracao"]:
            raise _NUCLEO.DAErro(f"juntar: {c.name} não tem vídeo (ou duração) legível")
    for k, t in enumerate(trans):
        if t["duracao"] > 0 and t["duracao"] >= min(infos[k]["duracao"], infos[k + 1]["duracao"]) - 0.04:
            raise _NUCLEO.DAErro(f"juntar: a transição {t['tipo']} de {_NUCLEO._num(t['duracao'], 2)} s não cabe entre {clipes[k].name} "
                                 f"({_NUCLEO._num(infos[k]['duracao'], 2)} s) e {clipes[k + 1].name} ({_NUCLEO._num(infos[k + 1]['duracao'], 2)} s)",
                                 dica="Use clipes mais longos, duracao=<menor> ou transicao='corte'.")
    partes, args = [], []
    for k, (c, i) in enumerate(zip(clipes, infos)):
        args += ["-i", str(c)]
        partes.append(f"[{k}:v]scale={L}:{A}:force_original_aspect_ratio=increase:flags=lanczos,crop={L}:{A},setsar=1,"
                      f"fps={fps_texto(fps_f)},format=yuv420p,settb=AVTB,setpts=PTS-STARTPTS[v{k}]")
        if i["tem_audio"]:
            partes.append(f"[{k}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,asetpts=PTS-STARTPTS[a{k}]")
        else:
            partes.append(f"anullsrc=r=48000:cl=stereo,atrim=duration={_NUCLEO._num(i['duracao'], 4)}[a{k}]")
    v_atual, a_atual, acumulado, registro = "v0", "a0", float(infos[0]["duracao"]), []
    for k, t in enumerate(trans, start=1):
        if t["tipo"] == "corte":
            partes.append(f"[{v_atual}][v{k}]concat=n=2:v=1:a=0[vx{k}]")
            partes.append(f"[{a_atual}][a{k}]concat=n=2:v=0:a=1[ax{k}]")
            registro.append({"tipo": "corte", "inicio": round(acumulado, 4), "duracao": 0.0})
            acumulado += float(infos[k]["duracao"])
        else:
            ini = acumulado - t["duracao"]
            partes.append(f"[{v_atual}][v{k}]{filtro_transicao(t['tipo'], t['duracao'], ini)}[vx{k}]")
            partes.append(f"[{a_atual}][a{k}]acrossfade=d={_NUCLEO._num(t['duracao'], 4)}:c1=tri:c2=tri[ax{k}]")
            registro.append({"tipo": t["tipo"], "inicio": round(ini, 4), "duracao": t["duracao"]})
            acumulado += float(infos[k]["duracao"]) - t["duracao"]
        v_atual, a_atual = f"vx{k}", f"ax{k}"
    filtro = ";".join(partes)
    args += ["-filter_complex", filtro, "-map", f"[{v_atual}]", "-map", f"[{a_atual}]", *args_encode(fps_f, crf=crf, audio=True)]
    executar(args, saida, rotulo=f"juntar {len(clipes)} clipes")
    carimbo = None
    if carimbar:
        carimbo = _carimbar_saida(d, saida, ferramenta, {**(parametros or {}), "clipes": [c.name for c in clipes], "transicoes": registro,
                                                         "fps": fps_texto(fps_f)}, clipes, formato=nome_do_formato(d, L, A))
    return {"saida": saida, "duracao": round(acumulado, 4), "transicoes": registro, "filtro": filtro, "carimbo": carimbo}


# ─────────────────────────────────────── insert dentro da moldura (D17) ──
def encaixar_em_janela(base, insert, saida, janela, moldura=None, da_obj: "da.DA | None" = None, inicio: float | None = None,
                       duracao: float | None = None, crf: int = 18, carimbar: bool = True, da=None) -> dict:
    """Põe um insert (vídeo ou imagem) na janela de uma moldura do kit, sobre a base, e a moldura por cima — uma passada.

    janela  : o `layout` que a cena/peça moldura devolve (carimbo → parametros.layout: usa `janela_girada`, que já
              traz centro, tamanho e ângulo da polaroid inclinada) ou um dict {'x','y','w','h'} / {'cx','cy','w','h','angulo'} em px.
    moldura : overlay com alfa renderizado pela cena `moldura` (WebM/MOV/PNG), opcional.
    O insert cobre a janela (amplia e corta pelo centro) e gira com ela: não sobram cunhas nos cantos.
    Devolve {'saida', 'filtro', 'carimbo'}."""
    base, insert, saida = Path(str(base)).expanduser(), Path(str(insert)).expanduser(), Path(str(saida)).expanduser()
    moldura = Path(str(moldura)).expanduser() if moldura else None
    j = janela.get("janela_girada") or janela.get("janela") or janela if isinstance(janela, dict) else None
    if not isinstance(j, dict) or not ({"w", "h"} <= set(j)):
        raise _NUCLEO.DAErro("encaixar_em_janela: `janela` precisa ser o layout da moldura ou {'x','y','w','h'} / {'cx','cy','w','h','angulo'}")
    w, h = _par(j["w"]), _par(j["h"])
    cx = float(j["cx"]) if "cx" in j else float(j["x"]) + float(j["w"]) / 2
    cy = float(j["cy"]) if "cy" in j else float(j["y"]) + float(j["h"]) / 2
    ang = float(j.get("angulo", 0) or 0)
    info = sondar(base)
    fps_f = info["fps"] or Fraction(30000, 1001)
    dur = float(duracao) if duracao is not None else max(0.04, float(info["duracao"] or 0) - float(inicio or 0))
    parado = insert.suffix.lower() in _NUCLEO.EXT_IMAGEM
    ent_insert = (["-loop", "1", "-framerate", fps_texto(fps_f), "-t", _NUCLEO._num(dur + 0.5, 3)] if parado else []) + ["-i", str(insert)]
    cadeia = f"[1:v]scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos,crop={w}:{h},setsar=1,format=rgba"
    if abs(ang) > 1e-6:
        cadeia += f",rotate={_NUCLEO._num(ang, 4)}*PI/180:c=none:ow=rotw({_NUCLEO._num(ang, 4)}*PI/180):oh=roth({_NUCLEO._num(ang, 4)}*PI/180)"
    cadeia += f"[ins];[0:v][ins]overlay={_NUCLEO._num(cx, 2)}-w/2:{_NUCLEO._num(cy, 2)}-h/2:eof_action=pass:format=auto"
    args = [*_args_trecho(inicio, duracao), "-i", str(base), *ent_insert]
    if moldura is not None:
        im = sondar(moldura)
        if (im["largura"], im["altura"]) != (info["largura"], info["altura"]):
            raise _NUCLEO.DAErro(f"encaixar_em_janela: a moldura ({im['largura']}×{im['altura']}) e a base ({info['largura']}×{info['altura']}) têm tamanhos "
                                 "diferentes: a janela devolvida pela moldura está em px do quadro DELA.",
                                 dica="Renderize a moldura no formato da base (--formato LxA) e use o layout desse render.")
        mold_parada = moldura.suffix.lower() in _NUCLEO.EXT_IMAGEM
        args += (["-loop", "1", "-framerate", fps_texto(fps_f), "-t", _NUCLEO._num(dur + 0.5, 3)] if mold_parada else []) + entrada_com_alfa(moldura)
        cadeia += "[com];[2:v]format=rgba[mol];[com][mol]overlay=0:0:eof_action=pass:format=auto"
    filtro = cadeia + ",format=yuv420p[v]"
    args += ["-filter_complex", filtro, "-map", "[v]"]
    com_audio = bool(info["tem_audio"])
    if com_audio:
        args += ["-map", "0:a?"]
    args += [a for a in args_encode(fps_f, crf=crf, audio=com_audio) if a != "-an"] + ["-t", _NUCLEO._num(dur, 3)]
    d = _da(da_obj, da, de=saida.parent) if carimbar else None
    executar(args, saida, rotulo=f"insert {insert.name} na moldura")
    carimbo = None
    if carimbar:
        carimbo = _carimbar_saida(d, saida, "video.py encaixar_em_janela",
                                  {"base": base.name, "insert": insert.name, "moldura": moldura.name if moldura else None,
                                   "janela": {"cx": cx, "cy": cy, "w": w, "h": h, "angulo": ang}, "inicio": inicio, "duracao": duracao},
                                  [base, insert, *([moldura] if moldura else [])])
    return {"saida": saida, "filtro": filtro, "carimbo": carimbo}


if __name__ == "__main__":
    print(__doc__)
