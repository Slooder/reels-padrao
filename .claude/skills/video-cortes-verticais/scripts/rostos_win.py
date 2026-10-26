"""rostos_win.py — substituto do rostos.swift fora do macOS (ADAPTAÇÃO LOCAL, não vem da crIAbr).
Mesma linha de comando e mesmo JSON: caixas de rosto NORMALIZADAS (0–1, origem no canto superior esquerdo) de alguns
quadros por segundo. Detector: YuNet (OpenCV), modelo face_detection_yunet_2023mar.onnx ao lado deste arquivo.

uso: python rostos_win.py <video> <saida.json> [--fps 3] [--inicio S] [--fim S] [--lado 640]
"""
import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

MODELO = Path(__file__).resolve().parent / "face_detection_yunet_2023mar.onnx"
CONFIANCA_MINIMA = 0.8


def sair(codigo: int, msg: str):
    print(msg, file=sys.stderr)
    sys.exit(codigo)


def opcao(args, nome, padrao):
    return float(args[args.index(nome) + 1]) if nome in args and args.index(nome) + 1 < len(args) else padrao


def sondar(video: Path) -> tuple[float, float, float]:
    """(largura, altura, duração) como o vídeo é exibido (rotação aplicada)."""
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=width,height:stream_side_data=rotation:format=duration", "-of", "json", str(video)],
                       capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        sair(1, f"rostos: ffprobe não leu o vídeo: {r.stderr.strip()[:200]}")
    d = json.loads(r.stdout)
    s = (d.get("streams") or [{}])[0]
    if "width" not in s:
        sair(1, "rostos: o arquivo não tem trilha de vídeo")
    w, h = float(s["width"]), float(s["height"])
    rot = next((abs(int(x.get("rotation", 0))) for x in s.get("side_data_list", []) if "rotation" in x), 0)
    if rot in (90, 270):
        w, h = h, w
    return w, h, float(d.get("format", {}).get("duration", 0))


def main():
    a = sys.argv
    if len(a) < 3:
        sair(64, "uso: rostos_win.py <video> <saida.json> [--fps 3] [--inicio S] [--fim S] [--lado 640]")
    video, saida = Path(a[1]), Path(a[2])
    if not video.is_file():
        sair(1, f"rostos: vídeo não encontrado: {video}")
    largura, altura, duracao = sondar(video)
    fps = max(0.5, min(15.0, opcao(a, "--fps", 3.0)))
    inicio = max(0.0, opcao(a, "--inicio", 0.0))
    fim = min(duracao, opcao(a, "--fim", duracao))
    lado = max(160.0, opcao(a, "--lado", 640.0))
    if fim <= inicio:
        sair(64, f"rostos: trecho vazio (--inicio {inicio} --fim {fim}; o vídeo tem {duracao} s)")

    escala = lado / max(largura, altura)
    w2, h2 = max(2, int(largura * escala) // 2 * 2), max(2, int(altura * escala) // 2 * 2)
    bruto = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{inicio:.3f}", "-to", f"{fim:.3f}", "-i", str(video),
                            "-vf", f"fps={fps},scale={w2}:{h2}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
                           capture_output=True).stdout
    n_quadros = len(bruto) // (w2 * h2 * 3)
    # o caminho do projeto pode ter acento, que o leitor de ONNX do OpenCV não abre no Windows: carrega da memória
    detector = cv2.FaceDetectorYN.create("onnx", np.frombuffer(MODELO.read_bytes(), np.uint8), np.array([], np.uint8),
                                         (w2, h2), CONFIANCA_MINIMA)

    quadros, falhas = [], 0
    for k in range(n_quadros):
        t = inicio + k / fps
        if t >= fim:
            break
        img = np.frombuffer(bruto, np.uint8, w2 * h2 * 3, k * w2 * h2 * 3).reshape(h2, w2, 3)
        rostos = []
        try:
            _, achados = detector.detect(img)
            for f in achados if achados is not None else []:
                x, y, w, h = (float(v) for v in f[:4])
                x0, y0 = max(0.0, x), max(0.0, y)
                rostos.append({"x": x0 / w2, "y": y0 / h2, "w": (min(w2, x + w) - x0) / w2, "h": (min(h2, y + h) - y0) / h2,
                               "conf": float(f[-1])})
        except cv2.error:
            falhas += 1
        quadros.append({"t": round(t, 3), "rostos": rostos})
    if not quadros or falhas == len(quadros):
        sair(1, f"rostos: nenhum quadro pôde ser lido ou analisado ({falhas} falha(s))")

    doc = {"versao": 1, "detector": "OpenCV YuNet 2023mar", "largura": largura, "altura": altura, "duracao": duracao,
           "fps": fps, "inicio": inicio, "fim": fim, "falhas": falhas, "quadros": quadros}
    saida.write_text(json.dumps(doc, sort_keys=True), encoding="utf-8")
    print(f"rostos: {len(quadros)} quadro(s) de {inicio} a {fim} s, {sum(1 for q in quadros if q['rostos'])} com rosto")


if __name__ == "__main__":
    main()
