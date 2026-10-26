#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""apoio.py — o que as suítes dividem: pasta temporária COM ESPAÇO E ACENTO no nome, projeto de teste com direção de
arte, palavras e vídeo sintéticos. Nada depende de rede nem de arquivos fora da skill e do kit."""
from __future__ import annotations

import json
import math
import os
import shutil
import struct
import sys
import tempfile
import wave
from pathlib import Path

sys.dont_write_bytecode = True
SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
import comum  # noqa: E402

PYTHON = sys.executable


def pasta_temporaria() -> Path:
    """Pasta nova com espaço e acento no caminho; VIDEO_OPS_HOME passa a apontar para dentro dela."""
    raiz = Path(tempfile.mkdtemp(prefix="legendas teste ção ")).resolve()       # /var → /private/var: os scripts resolvem caminhos
    os.environ["VIDEO_OPS_HOME"] = str(raiz / "ops home")
    return raiz


def apagar(pasta) -> None:
    shutil.rmtree(pasta, ignore_errors=True)


def projeto(raiz: Path, preset: str = "lab-ia", nome: str = "projeto de teste", **legenda) -> Path:
    """Projeto com a DA do preset; `legenda` troca tokens do bloco `legenda` (estilo="palavra", animacao="pop"…)."""
    da, _, _, _ = comum.kit()
    pasta = raiz / nome
    da.iniciar(pasta, nome=nome, base=preset)
    if legenda:
        arq = pasta / "da" / "da.json"
        dados = json.loads(arq.read_text(encoding="utf-8"))
        dados["legenda"].update(legenda)
        arq.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return pasta


FRASE = ("Em dois mil e dezessete, um artigo de oito páginas mudou a inteligência artificial. "
         "O Ashish Vaswani e mais sete autores propuseram a atenção, e hoje todo modelo de linguagem usa essa ideia. "
         "Não é mágica: são vinte e três por cento menos parâmetros!")


def palavras_sinteticas(texto: str = FRASE, inicio: float = 0.2, ritmo: float = 0.065, pausa_frase: float = 0.75,
                        pausa_virgula: float = 0.2) -> list[dict]:
    """Palavras cronometradas a partir de um texto: duração proporcional ao tamanho, pausa depois de vírgula e de ponto
    (no formato da video-transcricao, com as palavras coladas: o silêncio fica dentro da palavra anterior)."""
    saida, t = [], inicio
    for w in texto.split():
        dur = 0.12 + ritmo * len(w.strip(".,:;!?"))
        saida.append({"a": round(t, 3), "b": round(t + dur, 3), "w": w, "p": 0.95})
        t += dur + (pausa_frase if w[-1] in ".!?" else pausa_virgula if w[-1] in ",:;" else 0.0)
    return saida


def gravar_palavras(pasta: Path, palavras: list[dict], nome: str = "fala") -> Path:
    arq = pasta / "transcricao" / f"{nome}.palavras.json"
    arq.parent.mkdir(parents=True, exist_ok=True)
    arq.write_text(json.dumps(palavras, ensure_ascii=False), encoding="utf-8")
    return arq


def video_sintetico(pasta: Path, nome: str = "base", largura: int = 360, altura: int = 640, duracao: float = 2.0, fps: int = 30,
                    token: str = "superficie", audio: bool = True) -> Path:
    """Vídeo chapado numa cor da DA (token), com um tom de 440 Hz no áudio. Feito pelo Codificador do kit, sob a trava."""
    da, _, video, _ = comum.kit()
    from PIL import Image
    d = da.carregar(str(pasta))
    arq = pasta / "bruto" / f"{nome}.mp4"
    arq.parent.mkdir(parents=True, exist_ok=True)
    som = None
    if audio:
        som = pasta / "bruto" / f"_{nome}.wav"
        with wave.open(str(som), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(48000)
            w.writeframes(b"".join(struct.pack("<h", int(6000 * math.sin(2 * math.pi * 440 * n / 48000))) for n in range(int(48000 * duracao))))
    quadro = Image.new("RGB", (largura, altura), d.rgb(token))
    with video.Codificador(arq, largura=largura, altura=altura, fps=fps, da_obj=d, audio=som, carimbar=False, rotulo="teste: base sintética") as cod:
        cod.escrever(quadro, repetir=int(round(duracao * fps)))
    if som:
        som.unlink(missing_ok=True)
    return arq


def quadros_rgb(arquivo, indices: list[int]) -> tuple[dict, int, int]:
    """Os quadros pedidos (por índice) em RGB cru, numa passada de ffmpeg sob a trava: ({índice: bytes}, largura, altura).
    Vai para um arquivo provisório, não para a memória da trava (a captura do kit guarda só os últimos 8 MB)."""
    _, _, video, trava = comum.kit()
    arquivo = Path(str(arquivo))
    s = video.sondar(arquivo)
    indices = sorted(set(int(i) for i in indices))
    tmp = arquivo.with_name(f"_{arquivo.stem}.quadros.rgb")
    filtro = "select='" + "+".join(f"eq(n\\,{i})" for i in indices) + "'"
    try:
        r = trava.rodar([video.FFMPEG, "-v", "error", "-nostdin", "-y", "-i", str(arquivo), "-vf", filtro, "-fps_mode", "passthrough",
                         "-f", "rawvideo", "-pix_fmt", "rgb24", str(tmp)], rotulo="teste: ler quadros", capturar=True, inatividade=60)
        if r.codigo != 0:
            raise RuntimeError(f"ffmpeg não leu {arquivo.name}: {str(r.stderr)[-300:]}")
        dados = tmp.read_bytes()
    finally:
        tmp.unlink(missing_ok=True)
    tam = s["largura"] * s["altura"] * 3
    if len(dados) != tam * len(indices):
        raise RuntimeError(f"esperava {len(indices)} quadro(s) de {arquivo.name}, vieram {len(dados) / tam:.1f}")
    return {i: dados[k * tam:(k + 1) * tam] for k, i in enumerate(indices)}, s["largura"], s["altura"]


def rodar(script: str, *args, cwd=None, env=None) -> "subprocess.CompletedProcess":
    """Roda um script da skill como a linha de comando o rodaria (cwd com espaço), sem herdar o stdin."""
    import subprocess
    ambiente = {**os.environ, **(env or {})}
    return subprocess.run([PYTHON, str(SCRIPTS / script), *[str(a) for a in args]], cwd=cwd, env=ambiente, capture_output=True, text=True,
                          stdin=subprocess.DEVNULL, timeout=600)
