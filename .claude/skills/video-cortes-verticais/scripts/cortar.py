#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cortar.py — executa cortes/plano.json: do vídeo longo 16:9 para cortes 9:16 de Shorts, Reels e TikTok.

Para cada corte do plano: corte preciso no vão entre palavras (com respiro), enquadramento (rosto | centro | faixa |
empilhado | auto — ver enquadrar.py), título/gancho opcional nos primeiros segundos (cena `titulo` do motor, na área
livre da DA: dentro da zona segura e fora da faixa da legenda), loudness em som.loudness.curto (duas passagens do
kit), legenda queimada pela skill video-legendas e carimbo com t0/t1 de origem, plataformas e insumos.

  cortar.py [--plano cortes/plano.json] [--palavras ARQ] [--projeto PASTA] [--so K01,K02] [--validar] [--previa]
            [--formato vertical|LxA] [--abertura gancho|titulo|nenhuma] [--abertura-dur 2.5] [--sem-legenda]
            [--manter-cues] [--sem-rostos] [--fps-rostos 3] [--respiro 0.1] [--meio-de-frase] [--json]

Saídas por corte: cortes/K01.mp4, cortes/K01.srt, cortes/K01.mp4.da.json e a folha de contato cortes/_previa_K01.png
(com --previa, só a folha, feita do enquadramento, sem renderizar o corte). Códigos: 0 ok · 1 erro · 2 sem DA · 64 uso.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cv_base  # noqa: E402
import enquadrar  # noqa: E402
from cv_base import Erro, br  # noqa: E402

TOLERANCIA = 0.35        # quanto t0/t1 do plano podem distar da fronteira de frase (s)
RESPIRO_FIM = 2.0        # o respiro do fim é este múltiplo do respiro do início (a última sílaba pede mais ar)
INSTANTES_DA_FOLHA = (0.08, 0.36, 0.64, 0.92)


# ─────────────────────────────────────────────────────────────── plano ──

def _fronteira(palavras, fr, t: float, lado: str, livre: bool):
    """Índice da palavra em que o corte começa (lado='inicio') ou termina ('fim'), ou (None, mensagem de erro)."""
    chave, campo = ("t0", "i0") if lado == "inicio" else ("t1", "i1")
    f = min(fr, key=lambda f: abs(f[chave] - t))
    if abs(f[chave] - t) <= TOLERANCIA:
        return f[campo], None
    borda = "a" if lado == "inicio" else "b"
    i = min(range(len(palavras)), key=lambda i: abs(palavras[i][borda] - t))
    if livre:
        return i, None
    dentro = next((x for x in fr if x["t0"] - 1e-6 <= t <= x["t1"] + 1e-6), f)
    return None, (f"{'t0' if lado == 'inicio' else 't1'} = {br(t)} s cai no meio da frase «{' '.join(dentro['texto'].split()[:8])}…» "
                  f"(perto de «{palavras[i]['w']}»); a fronteira de frase mais próxima é {br(f[chave])} s")


def validar_plano(plano: dict, palavras: list[dict], duracao: float, respiro: float = 0.1, meio_de_frase: bool = False) -> tuple[list, list]:
    """Confere o contrato de cortes/plano.json e as fronteiras e durações de cada corte. Devolve (erros, avisos) e
    anota em cada corte válido os índices das palavras (_i0, _i1) e os instantes exatos do corte (_t0, _t1)."""
    da, _, _ = cv_base.kit()
    erros, avisos = [], []
    if plano.get("versao") != 1:
        erros.append(f"plano: \"versao\" precisa ser 1 (veio {plano.get('versao')!r})")
    cortes = plano.get("cortes")
    if not isinstance(cortes, list) or not cortes:
        return erros + ["plano: \"cortes\" precisa ser uma lista com pelo menos um corte"], avisos
    fr = cv_base.frases(palavras)
    ids, saidas = set(), set()
    for n, c in enumerate(cortes):
        cid = str(c.get("id") or f"(corte {n + 1})")
        e = lambda m: erros.append(f"{cid}: {m}")      # noqa: E731
        if not re.fullmatch(r"K\d{2,}", cid):
            e("\"id\" precisa ter a forma K01, K02…")
        if cid in ids:
            e("id repetido")
        ids.add(cid)
        try:
            t0, t1 = float(c["t0"]), float(c["t1"])
        except (KeyError, TypeError, ValueError):
            e("\"t0\" e \"t1\" (segundos do vídeo de origem) são obrigatórios")
            continue
        if not (0 <= t0 < t1 <= duracao + 0.5):
            e(f"t0/t1 fora do vídeo ou invertidos ({br(t0)} → {br(t1)} s; o vídeo tem {br(duracao)} s)")
            continue
        modo = c.get("enquadramento") or "auto"
        if modo not in cv_base.ENQUADRAMENTOS:
            e(f"enquadramento {modo!r} inválido; use {', '.join(cv_base.ENQUADRAMENTOS)}")
        c["enquadramento"] = modo
        if c.get("pessoa") not in (None, "esquerda", "direita"):
            e(f"\"pessoa\" é \"esquerda\" ou \"direita\" (veio {c.get('pessoa')!r})")
        foco = c.get("foco")
        if foco is not None:
            dois = isinstance(foco, list) and len(foco) == 2 and all(isinstance(p, list) and len(p) == 2 for p in foco)
            um = isinstance(foco, list) and len(foco) == 2 and all(isinstance(v, (int, float)) for v in foco)
            if not (um or dois) or any(not 0 <= v <= 1 for p in (foco if dois else [foco]) for v in p):
                e(f"\"foco\" é null, [x, y] ou [[x, y], [x, y]] em frações de 0 a 1 do quadro de origem (veio {foco!r})")
            elif dois != (modo == "empilhado"):
                e("foco com dois pontos só serve ao `empilhado`, e o `empilhado` com foco manual pede os dois pontos (cima, baixo)")
        plats = c.get("plataformas") or list(cv_base.PLATAFORMAS)
        try:
            plats = [da.nome_plataforma(p) for p in plats]
        except da.DAErro as err:
            e(str(err))
            continue
        if any(p not in cv_base.PLATAFORMAS for p in plats):
            e(f"plataformas de corte vertical são {', '.join(cv_base.PLATAFORMAS)} (veio {', '.join(plats)})")
        c["plataformas"] = plats
        saida = str(c.get("saida") or f"cortes/{cid}.mp4")
        if not saida.startswith("cortes/") or not saida.endswith(".mp4") or ".." in saida or Path(saida).name.startswith("_"):
            e(f"\"saida\" precisa ser um .mp4 dentro de cortes/ sem prefixo _ (veio {saida!r})")
        if saida in saidas:
            e(f"saída repetida: {saida}")
        saidas.add(saida)
        c["saida"] = saida
        for campo in ("titulo", "gancho", "motivo"):
            if not str(c.get(campo) or "").strip():
                avisos.append(f"{cid}: sem \"{campo}\" — o plano é o registro da decisão editorial; preencha antes de aprovar")
        i0, m0 = _fronteira(palavras, fr, t0, "inicio", meio_de_frase)
        i1, m1 = _fronteira(palavras, fr, t1, "fim", meio_de_frase)
        for m in (m0, m1):
            if m:
                e(m)
        if i0 is None or i1 is None:
            continue
        if i1 < i0:
            e("não há nenhuma palavra entre t0 e t1")
            continue
        antes = palavras[i0]["a"] - (palavras[i0 - 1]["b"] if i0 > 0 else 0.0)
        depois = (palavras[i1 + 1]["a"] if i1 + 1 < len(palavras) else duracao) - palavras[i1]["b"]
        c["_i0"], c["_i1"] = i0, i1
        c["_t0"] = round(max(0.0, palavras[i0]["a"] - min(respiro, max(antes, 0.0) / 2)), 3)
        c["_t1"] = round(min(duracao, palavras[i1]["b"] + min(respiro * RESPIRO_FIM, max(depois, 0.0) / 2)), 3)
        if abs(palavras[i0]["a"] - t0) > TOLERANCIA or abs(palavras[i1]["b"] - t1) > TOLERANCIA:
            avisos.append(f"{cid}: t0/t1 foram levados para o vão entre palavras mais próximo ({br(c['_t0'])} → {br(c['_t1'])} s)")
        dur = c["_t1"] - c["_t0"]
        for p in plats:                                                    # limites do kit, nunca embutidos
            dmin, dmax, rec = da.limite(p, "duracao_min_s"), da.limite(p, "duracao_max_s"), da.limite(p, "duracao_max_recomendada_s")
            if dmin is not None and dur < dmin:
                e(f"{br(dur, 1)} s é menos que o mínimo do {p} ({dmin:g} s)")
            if dmax is not None and dur > dmax:
                e(f"{br(dur, 1)} s passa do máximo do {p} ({dmax:g} s)")
            elif rec is not None and dur > rec:
                avisos.append(f"{cid}: {br(dur, 1)} s passa da duração recomendada do {p} ({rec:g} s)")
    return erros, avisos


# ─────────────────────────────────────────────────────────── peças do corte ──

def _zona(plataformas: list[str]) -> str | None:
    """Zona segura da legenda e da abertura: a da plataforma única; para várias, a união (None = padrão do kit)."""
    return plataformas[0] if len(plataformas) == 1 else None


def posicionar_abertura(bloco: tuple[float, float], livre: tuple[float, float], rostos: list, folga: float = 4.0) -> tuple[int, bool]:
    """Deslocamento vertical (px) que tira o bloco da abertura de cima dos rostos SEM sair da área livre (zona segura
    menos a faixa da legenda). Devolve (dy, cobre_rosto): fica onde o motor pôs se ali não há rosto; senão vai para o
    maior vão sem rosto em que caiba, centrado nele; se não cabe em nenhum, fica no lugar (o padrão ou o topo da área
    livre) que cobre menos rosto e cobre_rosto = True."""
    y0, y1 = bloco
    h = y1 - y0
    if not any(min(y1, r1) - max(y0, r0) > 0.25 * h for r0, r1 in rostos):
        return 0, False
    vaos, cursor = [], livre[0]
    for r0, r1 in sorted(rostos):
        if r0 > cursor:
            vaos.append((cursor, min(r0, livre[1])))
        cursor = max(cursor, r1)
    if cursor < livre[1]:
        vaos.append((cursor, livre[1]))
    cabem = [(b - a, a, b) for a, b in vaos if b - a >= h + 2 * folga]
    if not cabem:                                                       # nenhum vão: o lugar (padrão ou topo) que cobre menos rosto
        sobre = lambda y: max(min(y + h, r1) - max(y, r0) for r0, r1 in rostos)      # noqa: E731
        melhor = min((y0, livre[0]), key=sobre)
        return int(round(melhor - y0)), sobre(melhor) > 0.25 * h
    _, a, b = max(cabem)
    return int(round((a + b - h) / 2 - y0)), False


def abertura(d, texto: str, saida: Path, formato: str, L: int, A: int, dur: float, zona: str | None, rostos: list | None = None) -> dict:
    """Título/gancho dos primeiros segundos: cena `titulo` do motor, com alfa, na área livre da DA. O bloco sai de cima
    dos rostos quando há vão livre (posicionar_abertura) e é conferido pelo layout do carimbo: dentro da zona segura e
    sem tocar a faixa da legenda; se tocar, nada é usado."""
    da, _, _ = cv_base.kit()
    import da_ext_motor as motor
    params = {"titulo": texto, "alinhar": "centro", "posicao": "base", "escala_titulo": "h2", "assinatura": False, "reservar_legenda": True}
    if zona:
        params["plataforma"] = zona
    saida.parent.mkdir(parents=True, exist_ok=True)
    r = motor.render(["--cena", "titulo", "--saida", str(saida), "--formato", formato, "--dur", f"{dur:g}", "--alfa",
                      "--params", json.dumps(params, ensure_ascii=False)], da_obj=d, capturar=True)
    if r.returncode != 0 or not saida.is_file():
        fim = " | ".join((r.stderr or r.stdout or "").strip().splitlines()[-3:])
        raise Erro(f"a peça de abertura não renderizou (código {r.returncode}): {fim[:400]}", "Rode de novo com --abertura nenhuma para seguir sem ela.")
    bloco = ((da.ler_carimbo(saida) or {}).get("parametros", {}).get("layout") or {}).get("bloco")
    if not bloco:
        raise Erro("a peça de abertura não devolveu o layout do bloco no carimbo: não há como conferir a zona segura.")
    faixa = d.faixa_legenda(formato, zona) if zona else d.faixa_legenda(formato)
    m = d.margens("vertical", zona or "uniao", largura=L, altura=A)
    x1, y1 = bloco.get("x1", bloco["x"] + bloco["w"]), bloco.get("y1", bloco["y"] + bloco["h"])
    livre = d.area_livre(formato, zona) if zona else d.area_livre(formato)
    dy, cobre = posicionar_abertura((bloco["y"], y1), (livre["y0"], livre["y1"]), [(a * A, b * A) for a, b in rostos or []], folga=A / 240)
    bloco, y1 = {**bloco, "y": bloco["y"] + dy}, y1 + dy
    colide = y1 > faixa["y0"] and bloco["y"] < faixa["y1"] and x1 > faixa["x0"] and bloco["x"] < faixa["x1"]
    dentro = bloco["x"] >= m["x0"] - 1 and x1 <= m["x1"] + 1 and bloco["y"] >= m["y0"] - 1 and y1 <= m["y1"] + 1
    if colide or not dentro:
        raise Erro(f"a abertura «{texto}» {'colide com a faixa da legenda' if colide else 'sai da zona segura'} "
                   f"(bloco y {bloco['y']:.0f}–{y1:.0f}; legenda y {faixa['y0']:.0f}–{faixa['y1']:.0f}): não foi usada.",
                   "Encurte o texto do gancho/título, ou rode com --abertura nenhuma.")
    return {"arquivo": saida, "texto": texto, "duracao": dur, "bloco": [round(bloco["x"]), round(bloco["y"]), round(x1), round(y1)],
            "faixa_legenda": [round(faixa["y0"]), round(faixa["y1"])], "dentro_da_zona": True, "colide_com_legenda": False,
            "deslocamento_y": dy, "cobre_rosto": cobre}


def folha(d, quadros: list[Path], rotulos: list[str], saida: Path, titulo: str) -> Path:
    _, video, _ = cv_base.kit()
    video.folha_de_contato(quadros, rotulos, saida, colunas=len(quadros), largura_celula=270, da_obj=d, titulo=titulo)
    return saida


def cortar(d, origem: Path, info: dict, palavras: list[dict], c: dict, op: dict) -> dict:
    """Um corte do plano → cortes/<id>.mp4 (+ .srt, carimbo e folha de contato). Devolve o resumo do que foi feito."""
    da, video, _ = cv_base.kit()
    raiz, cid, formato = d.raiz, c["id"], op["formato"]
    L, A = op["tamanho"]
    t0, t1 = c["_t0"], c["_t1"]
    dur = round(t1 - t0, 3)
    saida = raiz / c["saida"]
    pasta = saida.parent
    pasta.mkdir(parents=True, exist_ok=True)
    zona = _zona(c["plataformas"])
    avisos: list[str] = []

    # 1. rostos (só quando o modo depende deles e não há foco manual)
    quadros, sem = None, None
    if c["enquadramento"] in ("rosto", "empilhado", "auto") and c.get("foco") is None:
        if op.get("sem_rostos"):
            sem = "detecção desligada por --sem-rostos"
        else:
            try:
                quadros = enquadrar.detectar(origem, raiz / "cortes" / "_rostos", t0 - 0.5, t1 + 0.5, op.get("fps_rostos") or enquadrar.FPS_ROSTOS)["quadros"]
            except enquadrar.SemVision as e:
                sem = str(e)
    enq = enquadrar.montar(c["enquadramento"], (info["largura"], info["altura"]), (L, A), t0, t1, quadros, c.get("foco"), c.get("pessoa"), d, sem,
                           video_origem=origem)
    avisos += enq["avisos"]
    resumo = {"id": cid, "saida": saida, "t0": t0, "t1": t1, "duracao": dur, "enquadramento": enq["modo"], "pedido": enq["pedido"],
              "movimentos": len((enq["dados"].get("trajetoria") or {}).get("movimentos") or []), "avisos": avisos, "previa": None}
    tmp = pasta / f"_{saida.stem}_quadros"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    arq_folha = pasta / f"_previa_{saida.stem}.png"
    instantes = list(INSTANTES_DA_FOLHA)
    try:
        if op.get("previa"):                                               # só o enquadramento, sem renderizar o corte
            qs = [video.extrair_quadro(origem, t0 + dur * f, tmp / f"q{n}.png", tratamento=enq["em"](dur * f)) for n, f in enumerate(instantes)]
            resumo["previa"] = folha(d, qs, [f"{br(t0 + dur * f, 1)} s" for f in instantes], arq_folha, f"{cid} · {enq['modo']} · prévia do enquadramento")
            return resumo

        # 2. abertura (título ou gancho) — peça do motor, conferida contra a zona segura e a faixa da legenda
        ab = None
        qual = c.get("abertura", op.get("abertura"))
        texto_ab = str(c.get(qual) or "").strip() if qual in ("gancho", "titulo") else ""
        if texto_ab:
            ab = abertura(d, texto_ab, pasta / "_abertura" / f"{saida.stem}.webm", formato, L, A, min(float(op.get("abertura_dur") or 2.5), dur), zona,
                          enq["dados"].get("rostos_na_saida"))
            instantes[0] = min(0.7 * ab["duracao"] / dur, 0.3)             # o 1º quadro da folha mostra a abertura inteira
            if ab["cobre_rosto"]:
                avisos.append("a abertura não coube em nenhum vão sem rosto e ficou sobre parte dele: olhe a prévia, encurte o texto ou use --abertura nenhuma")

        # 3. base: corte + enquadramento (+ abertura) + loudness em duas passagens, num ffmpeg só
        if not info.get("tem_audio"):
            raise Erro(f"{origem.name} não tem áudio: corte de fala precisa da trilha de som.")
        medida = video.medir_para_loudnorm(origem, d, "curto", inicio=t0, duracao=dur, folga_pico=0.5)
        som = video.filtro_loudnorm(d, "curto", medida=medida, folga_pico=0.5)
        args = ["-ss", f"{t0:.3f}", "-t", f"{dur:.3f}", "-i", str(origem)]
        grafo, rotulo = f"[0:v]{enq['filtro']}[cv_q]", "[cv_q]"
        if ab:
            args += video.entrada_com_alfa(str(ab["arquivo"]))
            grafo, rotulo = grafo + f";[cv_q][1:v]overlay=0:{ab['deslocamento_y']}:eof_action=pass[cv_v]", "[cv_v]"
        com_legenda = not op.get("sem_legenda")
        base = pasta / f"_{saida.stem}_base.mp4" if com_legenda else saida
        args += ["-filter_complex", grafo, "-map", rotulo, "-map", "0:a:0", "-af", som,
                 *video.args_encode(d, formato=formato, crf=15 if com_legenda else 18)]
        video.executar(args, base, rotulo=f"corte {cid}")

        # 4. legenda queimada pela video-legendas (palavras rebaseadas para o corte), .srt ao lado
        insumos, leg = [origem], None
        if com_legenda:
            pal = [{"a": round(max(0.0, p["a"] - t0), 3), "b": round(min(dur, p["b"] - t0), 3), "w": p["w"], "p": p["p"]}
                   for p in palavras[c["_i0"]:c["_i1"] + 1]]
            arq_pal = cv_base.gravar_json(tmp / f"{saida.stem}.palavras.json", pal)
            prontas = raiz / "legendas" / f"{saida.stem}.cues.json"       # --manter-cues: usa as cues já corrigidas à mão
            cues = {"cues": str(prontas)} if (op.get("manter_cues") and prontas.is_file()) else {"refazer_cues": True}
            try:
                leg = cv_base.legendas().legendar(str(base), str(arq_pal), str(saida), formato=f"{L}x{A}", plataforma=zona,
                                                  nome=saida.stem, projeto=str(raiz), silencioso=True, **cues)
            finally:
                base.unlink(missing_ok=True)
                Path(str(da.caminho_do_carimbo(base))).unlink(missing_ok=True)
            avisos += [f"legenda: {a}" for a in leg.get("avisos") or []]
            insumos.append(leg["cues_json"])
        if ab:
            insumos.append(ab["arquivo"])

        # 5. conferência do som e carimbo (t0/t1 de origem, plataformas, insumos)
        som_final = video.conferir_loudness(d, saida, tipo="curto")
        if not som_final["ok"]:
            avisos.append(f"loudness fora do alvo: {som_final['medido']} (alvo {som_final['alvo']})")
        parametros = {
            "corte": cid, "titulo": c.get("titulo"), "gancho": c.get("gancho"), "motivo": c.get("motivo"),
            "origem": cv_base_rel(origem, raiz), "t0_origem": t0, "t1_origem": t1, "t0_plano": float(c["t0"]), "t1_plano": float(c["t1"]),
            "duracao": dur, "plataformas": c["plataformas"], "plataforma": zona or "uniao", "plano_sha256": op.get("plano_sha256"),
            "enquadramento": {"modo": enq["modo"], "pedido": enq["pedido"], "rostos_analisados": len(quadros or []), **enq["dados"]},
            "abertura": {**ab, "arquivo": cv_base_rel(ab["arquivo"], raiz)} if ab else None,
            "legenda": ({"cues_json": cv_base_rel(leg["cues_json"], raiz), "estilo": leg.get("estilo"), "cues": leg.get("cues"),
                         "zona_ok": (leg.get("conferencia") or {}).get("zona", {}).get("ok")} if leg else None),
            "loudness": {"medida_origem": medida, "final": som_final["medido"], "alvo": som_final["alvo"], "ok": som_final["ok"]},
        }
        resumo["carimbo"] = d.carimbar(saida, ferramenta=cv_base.FERRAMENTA, formato=formato, parametros=parametros, insumos=insumos)
        resumo.update(srt=saida.with_suffix(".srt") if saida.with_suffix(".srt").is_file() else None, loudness=som_final["medido"],
                      abertura=bool(ab), legenda=bool(leg))

        # 6. folha de contato do corte PRONTO (para olhar: rosto inteiro e centrado, legenda e abertura no lugar)
        fim_real = video.sondar(saida)["duracao"]
        qs = [video.extrair_quadro(saida, min(dur * f, fim_real - 0.05), tmp / f"q{n}.png") for n, f in enumerate(instantes)]
        resumo["previa"] = folha(d, qs, [f"{br(t0 + dur * f, 1)} s" for f in instantes], arq_folha, f"{cid} · {enq['modo']} · {br(dur, 1)} s")
        return resumo
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def cv_base_rel(caminho, raiz) -> str:
    try:
        return str(Path(caminho).resolve().relative_to(Path(raiz).resolve()))
    except ValueError:
        return str(caminho)


# ─────────────────────────────────────────────────────────── linha de comando ──

def _achar_palavras(raiz: Path, plano: dict, origem: Path, pedido) -> Path:
    candidatos = [pedido, plano.get("palavras"), f"transcricao/{origem.stem}.palavras.json", str(origem.with_suffix(".palavras.json"))]
    for c in candidatos:
        if c:
            p = Path(c).expanduser()
            p = p if p.is_absolute() else raiz / p
            if p.is_file():
                return p
            if c is pedido:
                raise Erro(f"transcrição não encontrada: {p}")
    raise Erro(f"não achei a transcrição palavra a palavra de {origem.name}.",
               "Passe --palavras ARQ (ou \"palavras\" no plano); ela vem da skill video-transcricao (transcricao/<nome>.palavras.json).")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Executa cortes/plano.json: cortes verticais enquadrados, legendados, com loudness e carimbo.")
    ap.add_argument("--plano", default="cortes/plano.json")
    ap.add_argument("--palavras", default=None, help="transcrição palavra a palavra do vídeo de origem (padrão: transcricao/<origem>.palavras.json)")
    ap.add_argument("--projeto", default=None, help="pasta do projeto (padrão: a atual)")
    ap.add_argument("--so", default=None, help="só estes cortes, separados por vírgula (ex.: K01,K03)")
    ap.add_argument("--validar", action="store_true", help="só confere o plano (fronteiras de frase e duração por plataforma)")
    ap.add_argument("--previa", action="store_true", help="só a folha de contato do enquadramento de cada corte (não renderiza)")
    ap.add_argument("--formato", default="vertical", help="formato da DA ou LxA (padrão: vertical)")
    ap.add_argument("--abertura", choices=("gancho", "titulo", "nenhuma"), default="nenhuma", help="texto na tela nos primeiros segundos")
    ap.add_argument("--abertura-dur", type=float, default=2.5, help="duração da abertura em segundos (padrão 2,5)")
    ap.add_argument("--sem-legenda", action="store_true", help="não queima legenda (e não gera o .srt)")
    ap.add_argument("--manter-cues", action="store_true", help="usa legendas/<id>.cues.json já existente (corrigido à mão) em vez de segmentar de novo")
    ap.add_argument("--sem-rostos", action="store_true", help="não detecta rosto: `rosto` e `empilhado` sem foco manual caem para `centro`")
    ap.add_argument("--fps-rostos", type=float, default=enquadrar.FPS_ROSTOS, help="quadros analisados por segundo na detecção (padrão 3)")
    ap.add_argument("--respiro", type=float, default=0.1, help="ar antes da primeira palavra, em s (o do fim é o dobro); nunca passa do meio do vão")
    ap.add_argument("--meio-de-frase", action="store_true", help="aceita t0/t1 fora de fronteira de frase (leva ao vão entre palavras mais próximo)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        da, video, _ = cv_base.kit()
        d = cv_base.carregar_da(a.projeto)                                 # Passo 0: sem DA sai com código 2
        raiz = d.raiz
        arq_plano = Path(a.plano).expanduser()
        arq_plano = arq_plano if arq_plano.is_absolute() else raiz / arq_plano
        plano = cv_base.ler_json(arq_plano, "plano de cortes")
        origem = raiz / str(plano.get("origem") or "render/final.mp4")
        if not origem.is_file():
            raise Erro(f"vídeo de origem não encontrado: {origem}", "Confira \"origem\" no plano (caminho relativo à pasta do projeto).")
        info = video.sondar(origem)
        L, A = d.dimensoes(a.formato)
        if A <= L:
            raise Erro(f"o formato {a.formato} ({L}×{A}) não é vertical.", "Use --formato vertical ou LxA com A > L (ex.: 540x960).", 64)
        palavras = cv_base.ler_palavras(_achar_palavras(raiz, plano, origem, a.palavras))
        erros, avisos = validar_plano(plano, palavras, info["duracao"], a.respiro, a.meio_de_frase)
        for m in avisos:
            print(f"aviso: {m}", file=sys.stderr)
        if erros:
            for m in erros:
                print(f"erro: {m}", file=sys.stderr)
            print(f"plano reprovado: {len(erros)} erro(s). Nada foi renderizado.", file=sys.stderr)
            return 1
        cortes = plano["cortes"]
        if a.so:
            pedidos = {s.strip() for s in a.so.split(",") if s.strip()}
            faltam = pedidos - {c["id"] for c in cortes}
            if faltam:
                raise Erro(f"--so: corte(s) fora do plano: {', '.join(sorted(faltam))}.", codigo=64)
            cortes = [c for c in cortes if c["id"] in pedidos]
        if a.validar:
            for c in cortes:
                print(f"{c['id']}: {br(c['_t0'])} → {br(c['_t1'])} s ({br(c['_t1'] - c['_t0'], 1)} s) · {c['enquadramento']} · {', '.join(c['plataformas'])}")
            print(f"plano válido: {len(cortes)} corte(s). Nada foi renderizado.")
            return 0
        op = {"formato": a.formato, "tamanho": (L, A), "previa": a.previa, "abertura": a.abertura, "abertura_dur": a.abertura_dur,
              "sem_legenda": a.sem_legenda, "manter_cues": a.manter_cues, "sem_rostos": a.sem_rostos, "fps_rostos": a.fps_rostos,
              "plano_sha256": hashlib.sha256(arq_plano.read_bytes()).hexdigest()}
        feitos = []
        for c in cortes:
            inicio = time.time()
            r = cortar(d, origem, info, palavras, c, op)
            r["tempo_s"] = round(time.time() - inicio, 1)
            feitos.append(r)
            if not a.json:
                o_que = "prévia" if a.previa else cv_base_rel(r["saida"], raiz)
                print(f"{r['id']}: {o_que} · {br(r['t0'])} → {br(r['t1'])} s ({br(r['duracao'], 1)} s) · {r['enquadramento']}"
                      + (f" (pedido: {r['pedido']})" if r["pedido"] != r["enquadramento"] else "")
                      + (f" · {r['movimentos']} movimento(s) de câmera" if r["enquadramento"] == "rosto" else "")
                      + (f" · {r['loudness']['lufs']} LUFS" if r.get("loudness") else "") + f" · {br(r['tempo_s'], 1)} s")
                print(f"    olhe: {cv_base_rel(r['previa'], raiz)}")
            for m in r["avisos"]:
                print(f"aviso: {r['id']}: {m}", file=sys.stderr)
        if a.json:
            print(json.dumps(feitos, ensure_ascii=False, indent=1, default=str))
        elif not a.previa:
            print(f"{len(feitos)} corte(s) pronto(s). Conferência final: {cv_base.DA_CLI} conferencia --corte " + " --corte ".join(r["id"] for r in feitos))
        return 0
    except Exception as e:  # noqa: BLE001 — Erro, da.DAErro, Erro da video-legendas
        if not hasattr(e, "codigo"):
            raise
        return cv_base.sair_com_erro(e)


if __name__ == "__main__":
    sys.exit(main())
