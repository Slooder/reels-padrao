#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""enquadrar.py — do 16:9 para o quadro vertical: detecção de rosto (Vision, via rostos.swift), trilhas por pessoa,
sugestão de enquadramento e a cadeia ffmpeg de cada modo.

  rosto     recorte que ACOMPANHA a pessoa, com trajetória suave: parado enquanto o rosto está na zona morta;
            só anda (com aceleração e freio) quando o rosto sai dela e fica fora; salto grande = troca de plano = corte seco
  centro    recorte parado no centro (ou no foco manual)
  faixa     o 16:9 inteiro sobre fundo desfocado (video.filtro_encaixe do kit)
  empilhado um recorte por apresentador, um sobre o outro, cada um centrado no próprio rosto

Linha de comando (diagnóstico e sugestão para preencher o plano):
  enquadrar.py VIDEO [--inicio S] [--fim S] [--fps 3] [--projeto PASTA] [--json]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import statistics
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cv_base  # noqa: E402
from cv_base import Erro, br  # noqa: E402

FONTE_SWIFT = Path(__file__).resolve().parent / "rostos.swift"
FPS_ROSTOS = 3.0
PRESENCA_MINIMA = 0.5        # fração dos quadros amostrados em que a pessoa precisa aparecer para ser "persistente"
ROSTO_MINIMO = 0.04          # largura mínima do rosto (fração do quadro): ignora rosto de fundo, pôster, tela
ZONA_MORTA = 0.15            # meia-largura da zona morta, em fração da largura do RECORTE
ALTURA_DO_ROSTO = 0.42       # onde o centro do rosto fica no recorte (0 = topo): sobra cabeça em cima, tronco embaixo
CABELO, QUEIXO = 1.05, 0.55  # a cabeça inteira, em alturas da caixa do Vision a partir do centro dela (para cima, para baixo)
JUNTOS_MINIMO = 0.85         # o empilhado avisa quando os dois rostos aparecem juntos em menos que isto do trecho


class SemVision(Erro):
    """Não há como detectar rosto nesta máquina (sem swiftc/Vision): quem chama cai para `centro` com aviso."""


# ─────────────────────────────────────────────────────────── detecção (Vision) ──

def binario() -> Path:
    """Compila rostos.swift uma vez (swiftc sob a trava do kit) para $VIDEO_OPS_HOME/cache e devolve o executável."""
    da, _, trava = cv_base.kit()
    if sys.platform != "darwin":        # adaptação local: fora do macOS, OpenCV YuNet com o mesmo JSON (rostos_win.py)
        try:
            import cv2  # noqa: F401
        except ImportError:
            raise SemVision("detecção de rosto indisponível: fora do macOS ela usa o OpenCV, que não está instalado.",
                            "Instale com: python -m pip install opencv-python")
        return [sys.executable, str(FONTE_SWIFT.with_name("rostos_win.py"))]
    marca = hashlib.sha256(FONTE_SWIFT.read_bytes()).hexdigest()[:12]
    destino = da.video_ops_home() / "cache" / f"rostos-{marca}"
    if destino.is_file() and os.access(destino, os.X_OK):
        return destino
    destino.parent.mkdir(parents=True, exist_ok=True)
    parcial = destino.with_name(destino.name + ".parcial")
    try:
        r = trava.rodar(["swiftc", "-O", str(FONTE_SWIFT), "-o", str(parcial)], rotulo="swiftc rostos", capturar=True, inatividade=240)
    except FileNotFoundError:
        raise SemVision("detecção de rosto indisponível: não há `swiftc` nesta máquina.", "Instale as Command Line Tools: xcode-select --install.")
    if r.codigo != 0 or not parcial.is_file():
        parcial.unlink(missing_ok=True)
        erros = [ln for ln in (r.stderr or "").splitlines() if "error" in ln]
        raise SemVision("detecção de rosto indisponível: o rostos.swift não compilou" + (f" ({erros[0].strip()[:160]})" if erros else f" (código {r.codigo})") + ".",
                        "Confira `swiftc --version` e as Command Line Tools (xcode-select --install).")
    parcial.replace(destino)
    for velho in destino.parent.glob("rostos-*"):
        if velho != destino:
            velho.unlink(missing_ok=True)
    return destino


def _cache(video: Path, pasta: Path) -> tuple[Path, dict]:
    st = video.stat()
    identidade = {"bytes": st.st_size, "mtime_ns": st.st_mtime_ns}
    arq = pasta / f"{video.stem}.json"
    doc = None
    if arq.is_file():
        try:
            doc = json.loads(arq.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            doc = None
    if not doc or doc.get("identidade") != identidade:
        doc = {"versao": 1, "video": video.name, "identidade": identidade, "trechos": [], "quadros": []}
    return arq, doc


def detectar(video, pasta_cache, inicio: float, fim: float, fps: float = FPS_ROSTOS) -> dict:
    """Caixas de rosto de `video` entre inicio e fim: {largura, altura, fps, quadros: [{t, rostos: [{x, y, w, h, conf}]}]}.
    Guarda por vídeo em `pasta_cache` (cortes/_rostos/<nome>.json) e só analisa o trecho que ainda não foi visto."""
    _, _, trava = cv_base.kit()
    video, pasta_cache = Path(video), Path(pasta_cache)
    arq, doc = _cache(video, pasta_cache)
    inicio = max(0.0, float(inicio))
    coberto = any(t["fps"] >= fps - 1e-6 and t["inicio"] <= inicio + 1e-3 and t["fim"] >= fim - 1e-3 for t in doc["trechos"])
    if not coberto:
        exe = binario()
        pasta_cache.mkdir(parents=True, exist_ok=True)
        bruto = pasta_cache / f"_{video.stem}.parcial.json"
        r = trava.rodar([*(exe if isinstance(exe, list) else [str(exe)]), str(video), str(bruto), "--fps", str(fps), "--inicio", f"{inicio:.3f}", "--fim", f"{fim:.3f}"],
                        rotulo="rostos (Vision)", capturar=True, inatividade=120)
        if r.codigo != 0 or not bruto.is_file():
            bruto.unlink(missing_ok=True)
            raise SemVision(f"a detecção de rosto falhou (código {r.codigo}): {(r.stderr or '').strip()[:200]}")
        novo = json.loads(bruto.read_text(encoding="utf-8"))
        bruto.unlink(missing_ok=True)
        doc.update(largura=novo["largura"], altura=novo["altura"], detector=novo.get("detector"))
        fora = [q for q in doc["quadros"] if not (novo["inicio"] - 1e-6 <= q["t"] < novo["fim"])]
        doc["quadros"] = sorted(fora + novo["quadros"], key=lambda q: q["t"])
        doc["trechos"] = [t for t in doc["trechos"] if not (inicio <= t["inicio"] and t["fim"] <= fim)] + [{"inicio": inicio, "fim": float(fim), "fps": fps}]
        cv_base.gravar_json(arq, doc)
    quadros = [q for q in doc["quadros"] if inicio - 1e-6 <= q["t"] < fim]
    return {"largura": doc.get("largura"), "altura": doc.get("altura"), "fps": fps, "quadros": quadros, "cache": arq}


# ───────────────────────────────────────────────────────── trilhas e sugestão ──

def trilhas(quadros: list[dict], distancia: float = 0.12) -> list[dict]:
    """Agrupa as caixas em pessoas (trilhas), da esquerda para a direita. Cada trilha: cx, cy, w, h (medianas),
    presenca (fração dos quadros), persistente (bool) e pontos [(t, cx, cy)]."""
    ts: list[dict] = []
    for q in quadros:
        usadas = set()
        for r in sorted(q.get("rostos") or [], key=lambda r: -r["w"] * r["h"]):
            if r["w"] < ROSTO_MINIMO:
                continue
            cx, cy = r["x"] + r["w"] / 2, r["y"] + r["h"] / 2
            livres = [(abs(cx - t["ultimo"]), i) for i, t in enumerate(ts) if i not in usadas and abs(cx - t["ultimo"]) <= distancia]
            if livres:
                i = min(livres)[1]
            else:
                ts.append({"pontos": [], "ws": [], "hs": [], "ultimo": cx})
                i = len(ts) - 1
            usadas.add(i)
            ts[i]["pontos"].append((q["t"], cx, cy))
            ts[i]["ws"].append(r["w"])
            ts[i]["hs"].append(r["h"])
            ts[i]["ultimo"] = cx
    saida = []
    for t in ts:
        presenca = len(t["pontos"]) / max(1, len(quadros))
        saida.append({"cx": statistics.median(p[1] for p in t["pontos"]), "cy": statistics.median(p[2] for p in t["pontos"]),
                      "w": statistics.median(t["ws"]), "h": statistics.median(t["hs"]), "presenca": round(presenca, 3),
                      "persistente": presenca >= PRESENCA_MINIMA, "pontos": t["pontos"]})
    return sorted(saida, key=lambda t: t["cx"])


def sugerir(quadros: list[dict]) -> dict:
    """Enquadramento sugerido pelo número de rostos persistentes: 2+ → empilhado; 1 → rosto; 0 → centro."""
    pessoas = [t for t in trilhas(quadros) if t["persistente"]]
    if len(pessoas) >= 2:
        modo, motivo = "empilhado", f"{len(pessoas)} rostos persistentes no trecho"
    elif len(pessoas) == 1:
        modo, motivo = "rosto", "1 rosto persistente no trecho"
    else:
        modo, motivo = "centro", "nenhum rosto persistente no trecho" if quadros else "sem quadros analisados"
    return {"enquadramento": modo, "motivo": motivo, "pessoas": pessoas}


# ─────────────────────────────────────────────────── trajetória suave (modo rosto) ──

def _mediana3(valores: list[float]) -> list[float]:
    return [statistics.median(valores[max(0, i - 1):i + 2]) for i in range(len(valores))]


def trajetoria(pontos: list[tuple], r: float, zona: float = ZONA_MORTA, persistencia: float = 0.6, salto: float | None = None,
               janela: float = 1.0) -> dict:
    """Centro do recorte ao longo do tempo, a partir das posições do rosto [(t, cx)] (cx e r em fração da largura da
    fonte; r = largura do recorte). Devolve {"inicio": c0, "movimentos": [{"ta", "tb", "de", "para", "tipo"}]}.

    Regras (as do "sem tremor"): mediana de 3 amostras tira o ponto solto; o recorte fica PARADO enquanto o rosto
    está a até `zona` × r do centro; só reage se o rosto ficar fora por `persistencia` segundos; o destino é a mediana
    do rosto no segundo seguinte (não o ponto do instante), e o caminho é uma rampa suave (smoothstep) com duração
    proporcional à distância; salto maior que `salto` entre duas amostras é troca de plano: corte seco, sem panorâmica."""
    meio = r / 2
    prender = lambda c: min(max(c, meio), 1 - meio) if r < 1 else 0.5      # noqa: E731 — o recorte não sai do quadro
    if not pontos:
        return {"inicio": 0.5, "movimentos": []}
    ts = [p[0] for p in pontos]
    xs = _mediana3([p[1] for p in pontos])
    salto = salto if salto is not None else max(0.6 * r, 0.12)
    z = zona * r
    c = prender(statistics.median(x for t, x in zip(ts, xs) if t <= ts[0] + janela))
    inicio, movimentos, i, livre_ate = c, [], 0, ts[0]
    while i < len(ts):
        t, x = ts[i], xs[i]
        if t < livre_ate or abs(x - c) <= z:
            i += 1
            continue
        lado = 1 if x > c else -1
        adiante = [(tt, xx) for tt, xx in zip(ts[i:], xs[i:]) if tt <= t + persistencia]
        resto_curto = ts[-1] - t < persistencia
        if any((xx - c) * lado <= z for _, xx in adiante) or (resto_curto and len(adiante) < 2):
            i += 1                                                         # voltou para a zona (ou acabou o trecho): não reage
            continue
        alvo = prender(statistics.median(xx for tt, xx in zip(ts[i:], xs[i:]) if tt <= t + janela))
        if abs(alvo - c) < 1e-4:
            i += 1
            continue
        if i > 0 and abs(x - xs[i - 1]) > salto:                           # troca de plano: corte seco no meio das duas amostras
            tc = (ts[i - 1] + t) / 2
            movimentos.append({"ta": tc, "tb": tc, "de": c, "para": alvo, "tipo": "corte", "entre": [ts[i - 1], t]})
            livre_ate = t
        else:
            dur = min(1.4, max(0.5, 1.6 * abs(alvo - c) / r))
            movimentos.append({"ta": t, "tb": t + dur, "de": c, "para": alvo, "tipo": "suave"})
            livre_ate = t + dur
        c = alvo
        i += 1
    return {"inicio": inicio, "movimentos": movimentos}


def pontos_do_alvo(quadros: list[dict], alvo: dict, todas: list[dict], pessoa: str | None = None) -> list[tuple]:
    """Posição [(t, cx)] do rosto seguido, quadro a quadro (`todas` = trilhas do trecho). Quando o alvo some da tela e
    aparece um rosto que NÃO é colega dele no mesmo plano (colega = trilha que divide a tela com o alvo; aí o alvo só
    deixou de ser detectado), o plano trocou: segue o rosto que está na tela (o do lado pedido, se houver mais de um).
    A trajetória trata o salto como corte seco."""
    do_alvo = {t: cx for t, cx, _ in alvo["pontos"]}
    outros = [p for p in todas if p is not alvo and 2 * sum(pt[0] in do_alvo for pt in p["pontos"]) >= len(do_alvo)]

    def colega(r) -> bool:
        cx = r["x"] + r["w"] / 2
        return any(abs(cx - o["cx"]) <= 0.12 and 0.65 <= r["w"] / o["w"] <= 1.5 for o in outros)

    pts = []
    for q in quadros:
        if q["t"] in do_alvo:
            pts.append((q["t"], do_alvo[q["t"]]))
            continue
        rs = sorted((r for r in q.get("rostos") or [] if r["w"] >= ROSTO_MINIMO and not colega(r)), key=lambda r: r["x"])
        if rs:
            r = rs[-1] if pessoa == "direita" else rs[0] if (pessoa == "esquerda" or len(rs) == 1) else max(rs, key=lambda r: r["w"] * r["h"])
            pts.append((q["t"], r["x"] + r["w"] / 2))
    return pts


def troca_de_plano(video_origem, a: float, b: float) -> float | None:
    """Instante (s) do primeiro quadro do plano novo entre duas amostras: o quadro de maior mudança de cena do trecho."""
    _, video, trava = cv_base.kit()
    try:
        r = trava.rodar([video.FFMPEG, "-hide_banner", "-nostdin", "-ss", f"{a:.3f}", "-t", f"{b - a + 0.1:.3f}", "-i", str(video_origem),
                         "-vf", "select='gt(scene,0.08)',metadata=print", "-an", "-f", "null", "-"],
                        rotulo="troca de plano", capturar=True, inatividade=60)
    except OSError:
        return None
    achados = re.findall(r"pts_time:([\d.]+)[^\n]*\n[^\n]*lavfi\.scene_score=([\d.]+)", r.stderr or "")
    return a + float(max(achados, key=lambda m: float(m[1]))[0]) if achados else None


def _cabeca(centro: float, altura: float) -> list[float]:
    """Faixa vertical [y0, y1] (frações do quadro de saída) ocupada pela cabeça inteira, a partir da caixa do rosto."""
    return [round(max(0.0, centro - CABELO * altura), 4), round(min(1.0, centro + QUEIXO * altura), 4)]


def posicao(traj: dict, t: float) -> float:
    """Centro do recorte no instante t (mesma conta da expressão do ffmpeg)."""
    c = traj["inicio"]
    for m in traj["movimentos"]:
        if t < m["ta"]:
            return c
        if t < m["tb"]:
            u = (t - m["ta"]) / (m["tb"] - m["ta"])
            return m["de"] + (m["para"] - m["de"]) * u * u * (3 - 2 * u)
        c = m["para"]
    return c


def _expressao(traj: dict, t0: float, para_px) -> str:
    """Expressão do ffmpeg para o x do recorte (em px), com `t` contado a partir do início do corte (t0)."""
    expr = f"{para_px(traj['movimentos'][-1]['para']):.2f}" if traj["movimentos"] else f"{para_px(traj['inicio']):.2f}"
    for m in reversed(traj["movimentos"]):
        a, b, xa, xb = m["ta"] - t0, m["tb"] - t0, para_px(m["de"]), para_px(m["para"])
        if b > a:
            u = f"((t-{a:.3f})/{b - a:.3f})"
            expr = f"if(lt(t,{b:.3f}),{xa:.2f}+{xb - xa:.2f}*{u}*{u}*(3-2*{u}),{expr})"
        expr = f"if(lt(t,{a:.3f}),{xa:.2f},{expr})"
    return expr


# ───────────────────────────────────────────────────────────── cadeias ffmpeg ──

def _par(v: float) -> int:
    return max(2, int(v) // 2 * 2)


def _caixa(W: int, H: int, L: int, A: int, largura_max: float | None = None) -> tuple[int, int]:
    """Maior recorte da fonte na proporção L:A (opcionalmente limitado em largura), com lados pares."""
    cw = min(W, H * L / A, largura_max or W)
    return _par(cw), _par(min(H, cw * A / L))


def _y(cy: float, ch: int, H: int) -> int:
    return int(round(min(max(cy * H - ALTURA_DO_ROSTO * ch, 0), H - ch)))


def _x(cx: float, cw: int, W: int) -> int:
    return int(round(min(max(cx * W - cw / 2, 0), W - cw)))


def _ponto(foco, o_que: str = "foco") -> tuple[float, float]:
    try:
        x, y = float(foco[0]), float(foco[1])
    except (TypeError, ValueError, IndexError):
        raise Erro(f"{o_que} inválido: {foco!r}.", "Use [x, y] em frações do quadro de origem (0–1), ex.: [0.3, 0.4].", 64)
    if not (0 <= x <= 1 and 0 <= y <= 1):
        raise Erro(f"{o_que} fora do quadro: {foco!r}.", "x e y são frações de 0 a 1 do quadro de ORIGEM.", 64)
    return x, y


def montar(modo: str, origem: tuple[int, int], saida: tuple[int, int], t0: float, t1: float, quadros: list[dict] | None = None,
           foco=None, pessoa: str | None = None, d=None, sem_rostos: str | None = None, video_origem=None) -> dict:
    """Cadeia ffmpeg (uma entrada, uma saída; `t` = 0 no início do corte) do enquadramento pedido.
    Devolve {modo (o efetivo), pedido, filtro, em(t_rel) → cadeia parada naquele instante, avisos, dados}.
    `quadros` = caixas de rosto do trecho (ou None); `sem_rostos` = motivo de não haver detecção (vira aviso).
    `foco` manual sempre vence a detecção: [x, y] (rosto, centro, faixa) ou [[x, y], [x, y]] (empilhado: cima, baixo).
    `video_origem` (opcional) deixa o corte seco do modo rosto cair no quadro exato da troca de plano.
    dados["rostos_na_saida"] = faixas verticais [y0, y1] (frações da altura de saída) ocupadas pelas cabeças."""
    _, video, _ = cv_base.kit()
    (W, H), (L, A) = origem, saida
    avisos, dados, pedido = [], {}, modo
    todas = trilhas(quadros or [])
    pessoas = [t for t in todas if t["persistente"]]
    if modo == "auto":
        modo = "centro" if foco is not None and not isinstance(foco[0], (list, tuple)) else sugerir(quadros or [])["enquadramento"]
        dados["sugerido"] = modo
    fim = ",setsar=1"
    escala = f"scale={L}:{A}:flags=lanczos"

    def cair_para_centro(motivo: str) -> None:
        nonlocal modo
        avisos.append(f"enquadramento `{pedido}` sem rosto para seguir ({motivo}): usei `centro`. Confira a prévia ou dê o `foco` do corte no plano")
        modo = "centro"

    if modo == "empilhado":
        if foco is not None:
            if not (isinstance(foco, (list, tuple)) and len(foco) == 2 and isinstance(foco[0], (list, tuple))):
                raise Erro(f"foco do empilhado inválido: {foco!r}.", "No empilhado o foco são dois pontos: [[x, y] de cima, [x, y] de baixo].", 64)
            centros, largura_rosto = [_ponto(foco[0]), _ponto(foco[1])], None
        elif len(pessoas) >= 2:
            dupla = sorted(sorted(pessoas, key=lambda t: -t["w"] * t["h"] * t["presenca"])[:2], key=lambda t: t["cx"])
            if pessoa == "direita":
                dupla.reverse()
            centros, largura_rosto = [(t["cx"], t["cy"]) for t in dupla], max(t["w"] for t in dupla)
            juntos = len({p[0] for p in dupla[0]["pontos"]} & {p[0] for p in dupla[1]["pontos"]}) / max(1, len(quadros or []))
            if juntos < JUNTOS_MINIMO:
                avisos.append(f"os dois rostos só aparecem juntos em {juntos:.0%} do trecho (troca de plano?): o `empilhado` é um quadro "
                              "fixo — confira a prévia ou use `rosto` neste corte")
            if len(pessoas) > 2:
                avisos.append(f"há {len(pessoas)} rostos persistentes: empilhei os 2 maiores")
        elif len(pessoas) == 1:
            avisos.append("`empilhado` pede dois rostos persistentes e só há 1 no trecho: usei `rosto`")
            modo = "rosto"
        else:
            cair_para_centro(sem_rostos or "nenhum rosto persistente no trecho")
    if modo == "empilhado":
        vao = abs(centros[0][0] - centros[1][0]) * W
        piso = 3 * largura_rosto * W if largura_rosto else 0
        cw, ch = _caixa(W, H, L, A // 2, largura_max=max(vao, piso, 0.3 * W))     # cada painel pega UMA pessoa: largura ≈ distância entre os rostos
        paineis = [{"x": _x(cx, cw, W), "y": _y(cy, ch, H), "w": cw, "h": ch} for cx, cy in centros]
        meia = _par(A / 2)
        filtro = ("split[cv_a][cv_b];" + ";".join(f"[cv_{r}]crop={p['w']}:{p['h']}:{p['x']}:{p['y']},scale={L}:{meia}:flags=lanczos[cv_{r}2]"
                                                    for r, p in zip("ab", paineis)) + f";[cv_a2][cv_b2]vstack{fim}")
        dados.update(paineis=paineis, centros=[[round(v, 4) for v in c] for c in centros], manual=foco is not None)
        if foco is None:
            dados["rostos_na_saida"] = [_cabeca((k + (t["cy"] * H - p["y"]) / p["h"]) / 2, t["h"] * H / p["h"] / 2)
                                        for k, (t, p) in enumerate(zip(dupla, paineis))]
        return {"modo": modo, "pedido": pedido, "filtro": filtro, "em": lambda t: filtro, "avisos": avisos, "dados": dados}

    if modo == "faixa":
        enc = video.filtro_encaixe((W, H), (L, A), modo="desfocado", d=d)
        dados.update(janela=list(enc["janela"]))
        return {"modo": modo, "pedido": pedido, "filtro": enc["filtro"], "em": lambda t: enc["filtro"], "avisos": avisos, "dados": dados}

    cw, ch = _caixa(W, H, L, A)
    if modo == "rosto" and foco is None:
        if not pessoas:
            cair_para_centro(sem_rostos or "nenhum rosto persistente no trecho")
        else:
            if pessoa in ("esquerda", "direita"):
                alvo = pessoas[0] if pessoa == "esquerda" else pessoas[-1]
            else:
                alvo = max(pessoas, key=lambda t: (t["w"] * t["h"] * t["presenca"], -t["cx"]))
                if len(pessoas) > 1:
                    avisos.append(f"há {len(pessoas)} rostos persistentes e o plano não diz qual seguir: fiquei com o maior "
                                  f"(x = {br(alvo['cx'])}). Ponha \"pessoa\": \"esquerda\" ou \"direita\" no corte")
            r = cw / W
            traj = trajetoria(pontos_do_alvo(quadros or [], alvo, todas, pessoa), r)
            for m in traj["movimentos"]:                                 # corte seco: no quadro exato da troca de plano
                exato = troca_de_plano(video_origem, *m["entre"]) if (m["tipo"] == "corte" and video_origem) else None
                if exato is not None:
                    m["ta"] = m["tb"] = exato - 0.01
            para_px = lambda c: min(max(c * W - cw / 2, 0), W - cw)        # noqa: E731
            y = _y(alvo["cy"], ch, H)
            dados["rostos_na_saida"] = [_cabeca((alvo["cy"] * H - y) / ch, alvo["h"] * H / ch)]
            dados.update(pessoa=pessoa or "maior", rosto=[round(alvo["cx"], 4), round(alvo["cy"], 4)], recorte=[cw, ch], y=y,
                         trajetoria={"inicio": round(traj["inicio"], 4),
                                     "movimentos": [{k: (round(v, 4) if isinstance(v, float) else v) for k, v in m.items()} for m in traj["movimentos"]]},
                         zona_morta=ZONA_MORTA)
            if traj["movimentos"]:
                filtro = f"crop={cw}:{ch}:'{_expressao(traj, t0, para_px)}':{y}:exact=1,{escala}{fim}"
            else:
                filtro = f"crop={cw}:{ch}:{int(round(para_px(traj['inicio'])))}:{y},{escala}{fim}"
            parado = lambda t: f"crop={cw}:{ch}:{int(round(para_px(posicao(traj, t0 + t))))}:{y},{escala}{fim}"      # noqa: E731
            return {"modo": modo, "pedido": pedido, "filtro": filtro, "em": parado, "avisos": avisos, "dados": dados}
    if foco is not None:                                                    # rosto ou centro com foco manual: recorte parado no ponto
        cx, cy = _ponto(foco)
        x, y = _x(cx, cw, W), _y(cy, ch, H)
        filtro = f"crop={cw}:{ch}:{x}:{y},{escala}{fim}"
        dados.update(manual=True, foco=[cx, cy], recorte=[cw, ch, x, y])
    else:
        filtro = video.filtro_recorte((W, H), (L, A), "centro")["filtro"] + fim
    return {"modo": modo, "pedido": pedido, "filtro": filtro, "em": lambda t: filtro, "avisos": avisos, "dados": dados}


# ─────────────────────────────────────────────────────────── linha de comando ──

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Detecta rostos num trecho do vídeo (Vision) e sugere o enquadramento vertical.")
    ap.add_argument("video")
    ap.add_argument("--inicio", type=float, default=0.0)
    ap.add_argument("--fim", type=float, default=None)
    ap.add_argument("--fps", type=float, default=FPS_ROSTOS, help="quadros analisados por segundo (padrão 3)")
    ap.add_argument("--projeto", default=None, help="pasta do projeto (padrão: a atual); o cache fica em cortes/_rostos/")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        _, video, _ = cv_base.kit()
        arq = Path(a.video).expanduser().resolve()
        if not arq.is_file():
            raise Erro(f"vídeo não encontrado: {arq}")
        raiz = Path(a.projeto).expanduser().resolve() if a.projeto else Path.cwd()
        fim = a.fim if a.fim is not None else video.sondar(arq)["duracao"]
        det = detectar(arq, raiz / "cortes" / "_rostos", a.inicio, fim, a.fps)
        s = sugerir(det["quadros"])
        todas = trilhas(det["quadros"])
        if a.json:
            print(json.dumps({"enquadramento": s["enquadramento"], "motivo": s["motivo"], "quadros": len(det["quadros"]),
                              "pessoas": [{k: v for k, v in t.items() if k != "pontos"} for t in todas], "cache": str(det["cache"])}, ensure_ascii=False, indent=1))
        else:
            print(f"{arq.name} de {br(a.inicio)} a {br(fim)} s: {len(det['quadros'])} quadro(s) analisado(s) a {a.fps:g} por segundo")
            for n, t in enumerate(todas):
                lado = "única" if len(todas) == 1 else "esquerda" if n == 0 else "direita" if n == len(todas) - 1 else "meio"
                print(f"  pessoa {n + 1} ({lado}): centro x {br(t['cx'])} y {br(t['cy'])}, rosto {br(t['w'])} da largura, "
                      f"presente em {t['presenca']:.0%} dos quadros{'' if t['persistente'] else ' — não persistente'}")
            print(f"enquadramento sugerido: {s['enquadramento']} ({s['motivo']})")
        return 0
    except SemVision as e:
        print(f"aviso: {e} Sem detecção, os modos `rosto` e `empilhado` caem para `centro`; use `foco` manual no plano.", file=sys.stderr)
        return 3
    except Exception as e:  # noqa: BLE001 — Erro, da.DAErro
        if not hasattr(e, "codigo"):
            raise
        return cv_base.sair_com_erro(e)


if __name__ == "__main__":
    sys.exit(main())
