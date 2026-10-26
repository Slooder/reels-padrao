"""transcrever.py — transcrição palavra a palavra com faster-whisper, no formato que video-legendas e
video-cortes-verticais leem: transcricao/<nome>.palavras.json = [{"a", "b", "w", "p"}] (segundos, texto, confiança).

Uso: python transcrever.py <video_ou_audio> [--nome final] [--saida transcricao] [--modelo M] [--idioma pt] [--gpu]
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

MODELO_PADRAO = "mobiuslabsgmbh/faster-whisper-large-v3-turbo"


def para_palavras(segmentos) -> list[dict]:
    return [{"a": round(w.start, 3), "b": round(w.end, 3), "w": w.word.strip(), "p": round(w.probability, 3)}
            for s in segmentos for w in (s.words or []) if w.word.strip()]


def ler_audio(midia: Path) -> np.ndarray:
    # ffmpeg em vez do PyAV do faster-whisper: a versão do av instalada quebra o decode_audio dele
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", str(midia), "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(pcm, np.float32)


def carregar_modelo(nome: str, gpu: bool):
    from faster_whisper import WhisperModel
    # GPU só sob pedido: nesta máquina o modelo carrega na CUDA mas falha no encode (falta cublas64_12.dll)
    if gpu:
        return WhisperModel(nome, device="cuda", compute_type="float16")
    return WhisperModel(nome, device="cpu", compute_type="int8")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("midia")
    ap.add_argument("--nome", help="nome do arquivo de saída (padrão: nome da mídia)")
    ap.add_argument("--saida", default="transcricao")
    ap.add_argument("--modelo", default=MODELO_PADRAO)
    ap.add_argument("--idioma", default="pt")
    ap.add_argument("--gpu", action="store_true", help="usa CUDA (precisa das DLLs cuBLAS/cuDNN 12)")
    a = ap.parse_args()

    midia = Path(a.midia)
    if not midia.is_file():
        sys.exit(f"erro: não achei {midia}")
    modelo = carregar_modelo(a.modelo, a.gpu)
    segs, info = modelo.transcribe(ler_audio(midia), language=a.idioma, word_timestamps=True, vad_filter=True)
    palavras = para_palavras(segs)
    if not palavras:
        sys.exit("erro: nenhuma palavra reconhecida (áudio vazio ou idioma errado?).")

    destino = Path(a.saida) / f"{a.nome or midia.stem}.palavras.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(palavras, ensure_ascii=False, indent=0), encoding="utf-8")
    baixas = sum(1 for w in palavras if w["p"] < 0.6)
    print(f"{destino}  ·  {len(palavras)} palavras  ·  {info.duration:.1f} s  ·  {baixas} com confiança < 0,60")


if __name__ == "__main__":
    main()
