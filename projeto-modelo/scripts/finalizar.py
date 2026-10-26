"""finalizar.py — palavras da legenda no tempo do vídeo final (lidas pelo Remotion) e a normalização de loudness da entrega."""
import json
import subprocess
import sys

import plano as P

CORRECOES = {"Nicolas": "Nikolas", "Nicolas,": "Nikolas,",   # grafia do nome (o whisper escreve com c)
             "Apocalipse": "Apocalipse.", "nordeste,": "Nordeste,"}   # o "21, 8" saiu no corte; região com maiúscula


def palavras_finais(versao):
    sem = [(e["de"], e["ate"]) for e in P.eventos(versao) if e["id"] in P.SEM_LEGENDA]
    fim = P.fim_da_fala(versao)
    saida = []
    for fonte, arq in (("A", "IMG_5666"), ("B", "IMG_5676")):
        for w in json.load(open(P.PROJ / "roteiro" / f"{arq}.palavras.json", encoding="utf-8")):
            # palavra encostada num respiro cortado (o whisper estica a palavra por cima da pausa): fica presa ao pedaço que
            # contém o meio dela ou, se o meio caiu no respiro, o fim dela; palavra que sumiu inteira no corte (o "21, 8") sai
            c = P.trecho(versao, fonte, (w["a"] + w["b"]) / 2) or P.trecho(versao, fonte, w["b"])
            if c is None:
                continue
            a = c["ini"] + max(w["a"], c["a"]) - c["a"]
            b = c["ini"] + min(w["b"], c["b"]) - c["a"]
            if b > fim + 0.5:
                continue
            meio = (a + b) / 2
            if any(x <= meio < y for x, y in sem):
                continue
            saida.append({"a": round(a, 3), "b": round(b, 3), "w": CORRECOES.get(w["w"], w["w"]), "p": w["p"]})
    saida.sort(key=lambda x: x["a"])
    for i in range(len(saida) - 1, 0, -1):                  # o whisper separa a ênclise: "apoiá" + "-lo." → "apoiá-lo."
        if saida[i]["w"].startswith("-"):
            saida[i - 1]["w"] += saida[i]["w"]
            saida[i - 1]["b"] = saida[i]["b"]
            del saida[i]
    destino = P.PROJ / "transcricao" / f"final_{versao}.palavras.json"
    destino.parent.mkdir(exist_ok=True)
    json.dump(sorted(saida, key=lambda x: x["a"]), open(destino, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    return destino, len(saida)


def normalizar(entrada, saida):
    """Só a voz, sem trilha nem efeitos (o JP faz o som à mão, 24/10): loudness de Reels, −14 LUFS / −1 dBTP, em duas passadas."""
    medir = subprocess.run(["ffmpeg", "-v", "info", "-i", str(entrada), "-vn", "-af", "loudnorm=I=-14:TP=-1:LRA=11:print_format=json",
                            "-f", "null", "-"], capture_output=True, text=True).stderr
    m = json.loads(medir[medir.rindex("{"):medir.rindex("}") + 1])
    af = (f"loudnorm=I=-14:TP=-1:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}"
          f":measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true,aresample=48000")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(entrada), "-map", "0:v", "-map", "0:a", "-c:v", "copy", "-af", af,
                    "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", str(saida)], check=True)
    return saida


if __name__ == "__main__":
    # uso: python finalizar.py palavras        → transcricao/final_v2.palavras.json (antes do Remotion)
    #      python finalizar.py <render.mp4>    → render/final_v2.mp4 (depois do Remotion)
    if sys.argv[1] == "palavras":
        print(palavras_finais("v2"))
    else:
        print("final:", normalizar(sys.argv[1], P.PROJ / "render" / "final_v2.mp4"))
