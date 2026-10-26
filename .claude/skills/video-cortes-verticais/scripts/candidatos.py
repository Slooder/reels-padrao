#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""candidatos.py — da transcrição palavra a palavra para JANELAS candidatas a corte vertical.

Toda janela começa em início de frase e termina em fim de frase, com duração dentro dos limites das plataformas
(lidos do kit por da.limite; --min/--max só estreitam). Para cada uma saem SINAIS — abertura com pergunta ou número,
abertura dependente de contexto, pausas, densidade de fala, confiança da transcrição, folga para o corte —, e uma
pontuação que serve só para ordenar a lista. A escolha editorial NÃO é deste script: é de quem lê (critérios da skill
gerar-ganchos) e do usuário, que aprova cortes/plano.json.

  candidatos.py PALAVRAS.json [--plataformas shorts,reels,tiktok] [--min S] [--max S] [--quantos 12]
                [--frases] [--json] [--saida cortes/_candidatos.json]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cv_base  # noqa: E402
from cv_base import Erro, br  # noqa: E402

CONECTIVOS = {"e", "mas", "então", "entao", "aí", "ai", "porque", "pois", "só", "so", "ou", "inclusive", "porém", "porem",
              "também", "tambem", "além", "alem", "daí", "dai", "agora", "aliás", "alias", "isso", "esse", "essa", "ele", "ela"}
NUMERAIS = {"dois", "duas", "três", "tres", "quatro", "cinco", "seis", "sete", "oito", "nove", "dez", "cem", "mil", "milhão",
            "milhao", "milhões", "milhoes", "bilhão", "bilhao", "bilhões", "bilhoes", "metade", "dobro", "triplo", "primeiro", "primeira"}
PAUSA = 0.5          # vão entre palavras que conta como pausa perceptível (s)


def _limpa(w: str) -> str:
    return re.sub(r"[^\wÀ-ÿ%$]", "", w).lower()


def sinais(palavras: list[dict], fr: list[dict], i: int, j: int) -> dict:
    """Sinais objetivos da janela que vai da frase i à frase j (inclusive)."""
    i0, i1 = fr[i]["i0"], fr[j]["i1"]
    ws = palavras[i0:i1 + 1]
    t0, t1 = ws[0]["a"], ws[-1]["b"]
    dur = max(t1 - t0, 1e-6)
    vaos = [b["a"] - a["b"] for a, b in zip(ws, ws[1:])]
    pausas = [v for v in vaos if v >= PAUSA]
    primeira = [_limpa(p["w"]) for p in palavras[fr[i]["i0"]:fr[i]["i1"] + 1]]
    cabeca = primeira[:8]
    antes = t0 - (palavras[i0 - 1]["b"] if i0 > 0 else 0.0)
    depois = (palavras[i1 + 1]["a"] - t1) if i1 + 1 < len(palavras) else 1.0
    fala = sum(p["b"] - p["a"] for p in ws)
    return {
        "abre_com_pergunta": fr[i]["texto"].rstrip("\"'”’)»").endswith("?"),
        "abre_com_numero": any(re.search(r"\d", w) or w in NUMERAIS for w in cabeca),
        "abre_dependente": bool(primeira) and primeira[0] in CONECTIVOS,      # começa por conectivo/pronome: pode pedir contexto
        "fecha_com": fr[j]["texto"].rstrip("\"'”’)»")[-1:],
        "pausas": len(pausas),
        "maior_pausa": round(max(vaos, default=0.0), 2),
        "silencio": round(sum(pausas), 2),
        "palavras_por_s": round(len(ws) / dur, 2),
        "fala_fracao": round(min(1.0, fala / dur), 2),
        "confianca": round(sum(p["p"] for p in ws) / len(ws), 3),
        "palavras_duvidosas": sum(p["p"] < 0.5 for p in ws),
        "folga_antes": round(max(antes, 0.0), 2),
        "folga_depois": round(max(depois, 0.0), 2),
    }


def pontos(s: dict) -> float:
    """Pontuação de ORDENAÇÃO (não de decisão): quem lê os sinais é o editor."""
    n = 2.0 * s["abre_com_pergunta"] + 2.0 * s["abre_com_numero"] - 2.0 * s["abre_dependente"]
    n += 1.0 if s["palavras_por_s"] >= 2.2 else (-1.0 if s["palavras_por_s"] < 1.4 else 0.0)
    n -= 1.0 * (s["maior_pausa"] >= 1.0) + 0.5 * max(0, s["pausas"] - 2)
    n += 0.5 * (s["folga_antes"] >= 0.15) + 0.5 * (s["folga_depois"] >= 0.15)
    n -= 1.0 * (s["confianca"] < 0.7)
    return round(n, 2)


def janelas(palavras: list[dict], fr: list[dict], dmin: float, dmax: float) -> list[dict]:
    """Todas as janelas frase-a-frase com duração em [dmin, dmax]."""
    saida = []
    for i in range(len(fr)):
        for j in range(i, len(fr)):
            dur = fr[j]["t1"] - fr[i]["t0"]
            if dur > dmax:
                break
            if dur < dmin:
                continue
            s = sinais(palavras, fr, i, j)
            saida.append({"t0": round(fr[i]["t0"], 3), "t1": round(fr[j]["t1"], 3), "duracao": round(dur, 2), "frases": [i, j],
                          "abre": " ".join(fr[i]["texto"].split()[:14]), "fecha": " ".join(fr[j]["texto"].split()[-10:]),
                          "sinais": s, "pontos": pontos(s)})
    return saida


def escolher(js: list[dict], quantos: int, sobreposicao: float = 0.6) -> list[dict]:
    """As `quantos` melhores pela pontuação, sem repetir quase a mesma janela (interseção/união acima de `sobreposicao`)."""
    escolhidas = []
    for j in sorted(js, key=lambda j: (-j["pontos"], j["t0"], j["duracao"])):
        def iou(o):
            inter = min(j["t1"], o["t1"]) - max(j["t0"], o["t0"])
            return inter / (max(j["t1"], o["t1"]) - min(j["t0"], o["t0"])) if inter > 0 else 0.0
        if all(iou(o) <= sobreposicao for o in escolhidas):
            escolhidas.append(j)
        if len(escolhidas) >= quantos:
            break
    return sorted(escolhidas, key=lambda j: j["t0"])


def faixa_de_duracao(plataformas, pedido_min=None, pedido_max=None) -> tuple[float, float, dict]:
    """Faixa de duração: a dos limites do kit, estreitada por --min/--max (que não podem sair dela)."""
    lim = cv_base.limites(plataformas)
    teto = lim["max"]
    dmin = lim["min"] if pedido_min is None else float(pedido_min)
    dmax = (lim["recomendada"] or teto) if pedido_max is None else float(pedido_max)
    if dmin < lim["min"] or (teto is not None and dmax > teto) or dmin >= dmax:
        raise Erro(f"faixa de duração {br(dmin, 0)}–{br(dmax, 0)} s fora dos limites das plataformas ({br(lim['min'], 0)}–{br(teto or 0, 0)} s para "
                   f"{', '.join(lim['por_plataforma'])}).", f"Os limites vêm do kit: {cv_base.DA_CLI} plataformas. Ajuste --min/--max ou --plataformas.", 64)
    return dmin, dmax, lim


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Lista janelas candidatas a corte vertical (início e fim em fronteira de frase) com sinais para julgamento.")
    ap.add_argument("palavras", help="transcrição palavra a palavra: JSON [{a, b, w, p}]")
    ap.add_argument("--plataformas", default=",".join(cv_base.PLATAFORMAS), help="destinos, separados por vírgula (padrão: shorts,reels,tiktok)")
    ap.add_argument("--min", type=float, default=None, dest="dmin", help="duração mínima desejada (s); padrão: o mínimo das plataformas")
    ap.add_argument("--max", type=float, default=None, dest="dmax", help="duração máxima desejada (s); padrão: a máxima recomendada das plataformas")
    ap.add_argument("--quantos", type=int, default=12, help="quantas janelas listar (padrão 12)")
    ap.add_argument("--frases", action="store_true", help="lista também todas as frases com os tempos (para montar uma janela à mão)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--saida", default=None, help="grava o JSON completo (frases + janelas) neste arquivo")
    a = ap.parse_args(argv)
    try:
        plataformas = [p.strip() for p in a.plataformas.split(",") if p.strip()]
        dmin, dmax, lim = faixa_de_duracao(plataformas, a.dmin, a.dmax)
        palavras = cv_base.ler_palavras(a.palavras)
        fr = cv_base.frases(palavras)
        todas = janelas(palavras, fr, dmin, dmax)
        lista = escolher(todas, max(1, a.quantos))
        doc = {"palavras": Path(a.palavras).name, "limites": lim, "faixa": {"min": dmin, "max": dmax}, "frases": fr,
               "janelas_possiveis": len(todas), "janelas": lista}
        if a.saida:
            cv_base.gravar_json(a.saida, doc)
        if a.json:
            print(json.dumps(doc, ensure_ascii=False, indent=1))
            return 0
        print(f"{len(fr)} frase(s), {len(todas)} janela(s) possíveis entre {br(dmin, 0)} e {br(dmax, 0)} s "
              f"(limites do kit para {', '.join(lim['por_plataforma'])}); listando {len(lista)}:")
        for j in lista:
            s = j["sinais"]
            marcas = [m for m, v in (("pergunta", s["abre_com_pergunta"]), ("número", s["abre_com_numero"]), ("abre dependente", s["abre_dependente"])) if v]
            print(f"\n  {br(j['t0'])} → {br(j['t1'])} s ({br(j['duracao'], 1)} s; frases {j['frases'][0]}–{j['frases'][1]}; pontos {j['pontos']:g})"
                  f"{'  [' + ', '.join(marcas) + ']' if marcas else ''}")
            print(f"    abre: «{j['abre']}…»   fecha: «…{j['fecha']}»")
            print(f"    {br(s['palavras_por_s'], 1)} palavras/s · {s['pausas']} pausa(s), maior {br(s['maior_pausa'], 1)} s · confiança {br(s['confianca'])}"
                  f" · folga {br(s['folga_antes'])}/{br(s['folga_depois'])} s")
        if a.frases:
            print("\nfrases:")
            for f in fr:
                print(f"  {f['n']:>3}  {br(f['t0']):>8} → {br(f['t1']):>8}  {f['texto']}")
        if not lista:
            print("nenhuma janela cabe na faixa pedida: alargue --min/--max.")
        return 0
    except Exception as e:  # noqa: BLE001 — Erro, da.DAErro
        if not hasattr(e, "codigo"):
            raise
        return cv_base.sair_com_erro(e)


if __name__ == "__main__":
    sys.exit(main())
