#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cv_base.py — o que os scripts da video-cortes-verticais dividem: achar o kit de direção de arte e a video-legendas
POR POSIÇÃO (skills instaladas lado a lado), erro com dica, JSON, palavras da transcrição e frases."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
AQUI = Path(__file__).resolve().parent
SKILLS = AQUI.parents[1]
FERRAMENTA = "video-cortes-verticais"
PLATAFORMAS = ("shorts", "reels", "tiktok")
ENQUADRAMENTOS = ("rosto", "centro", "faixa", "empilhado", "auto")
FIM_DE_FRASE = ".!?…"
ABREVIATURAS = {"sr.", "sra.", "dr.", "dra.", "prof.", "profa.", "etc.", "av.", "art.", "nº.", "n."}


def _vizinha(nome: str, miolo: str) -> Path:
    p = SKILLS / nome / miolo
    return p if p.exists() else Path(f"~/.claude/skills/{nome}/{miolo}").expanduser()


KIT = _vizinha("video-direcao-de-arte", "kit")
LEGENDAS = _vizinha("video-legendas", "scripts")
DA_CLI = "\"$CRIABR_SKILLS\"/video-direcao-de-arte/kit/bin/da"


class Erro(Exception):
    """Erro para o usuário: mensagem, dica (o que fazer) e código de saída."""

    def __init__(self, mensagem: str, dica: str | None = None, codigo: int = 1):
        super().__init__(mensagem)
        self.dica, self.codigo = dica, codigo


def kit():
    """Importa o kit (da, video, trava). Sem ele, erro claro em vez de ImportError."""
    if not (KIT / "da.py").is_file():
        raise Erro(f"não encontrei o kit de direção de arte em {KIT}.",
                   "Instale a skill video-direcao-de-arte ao lado desta (\"$CRIABR_SKILLS\"/video-direcao-de-arte/).", 127)
    if str(KIT) not in sys.path:
        sys.path.insert(0, str(KIT))
    try:
        import da, video, trava  # noqa: E401
    except ImportError as e:
        raise Erro(f"o kit de direção de arte não carregou: {e}.", "Rode com /opt/homebrew/bin/python3 (precisa de Pillow e numpy).", 127)
    return da, video, trava


def legendas():
    """O módulo legendar da skill vizinha video-legendas (a legenda queimada é dela, não refeita aqui)."""
    if not (LEGENDAS / "legendar.py").is_file():
        raise Erro(f"não encontrei a skill video-legendas em {LEGENDAS.parent}.",
                   "Instale a video-legendas ao lado desta, ou rode com --sem-legenda.", 127)
    if str(LEGENDAS) not in sys.path:
        sys.path.append(str(LEGENDAS))
    import legendar
    return legendar


def carregar_da(projeto=None):
    """Passo 0: a DA do projeto (pasta atual ou --projeto). Sem da/da.json sobe da.SemDA (código 2)."""
    da, _, _ = kit()
    return da.carregar(str(projeto)) if projeto else da.carregar()


def ler_json(caminho, o_que: str = "arquivo"):
    caminho = Path(caminho)
    if not caminho.is_file():
        raise Erro(f"{o_que} não encontrado: {caminho}")
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise Erro(f"{o_que} não é um JSON válido ({caminho.name}: linha {e.lineno}, {e.msg}).")


def gravar_json(caminho, obj) -> Path:
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return caminho


def br(x: float, casas: int = 2) -> str:
    return f"{x:.{casas}f}".replace(".", ",")


def ler_palavras(caminho) -> list[dict]:
    """Transcrição palavra a palavra [{a, b, w, p}] (video-transcricao), ordenada e conferida."""
    bruto = ler_json(caminho, "transcrição (palavras)")
    if isinstance(bruto, dict):
        bruto = bruto.get("palavras") or bruto.get("words") or []
    palavras = []
    for p in bruto:
        if not isinstance(p, dict) or "a" not in p or "b" not in p or not str(p.get("w", "")).strip():
            continue
        palavras.append({"a": float(p["a"]), "b": max(float(p["b"]), float(p["a"])), "w": str(p["w"]).strip(), "p": float(p.get("p", 1.0))})
    if not palavras:
        raise Erro(f"{Path(caminho).name} não tem palavras cronometradas no formato [{{a, b, w, p}}].",
                   "Gere a transcrição palavra a palavra com a skill video-transcricao.")
    return sorted(palavras, key=lambda p: p["a"])


def _fecha_frase(w: str) -> bool:
    w = w.rstrip("\"'”’)»")
    return w[-1:] in FIM_DE_FRASE and w.lower() not in ABREVIATURAS


def frases(palavras: list[dict], pausa: float = 0.7) -> list[dict]:
    """Palavras → frases [{n, i0, i1, t0, t1, texto}]. A frase fecha na pontuação final; em transcrição quase sem
    pontuação (menos de 1 ponto a cada 40 palavras), fecha também em pausa ≥ `pausa` segundos."""
    pontuada = sum(_fecha_frase(p["w"]) for p in palavras) * 40 >= len(palavras)
    saida, i0 = [], 0
    for i, p in enumerate(palavras):
        ultimo = i == len(palavras) - 1
        vao = 0.0 if ultimo else palavras[i + 1]["a"] - p["b"]
        if ultimo or _fecha_frase(p["w"]) or (not pontuada and vao >= pausa):
            saida.append({"n": len(saida), "i0": i0, "i1": i, "t0": palavras[i0]["a"], "t1": p["b"],
                          "texto": " ".join(q["w"] for q in palavras[i0:i + 1])})
            i0 = i + 1
    return saida


def limites(plataformas) -> dict:
    """Limites de duração lidos do kit (da.limite) para as plataformas pedidas — nenhum número mora nesta skill."""
    da, _, _ = kit()
    por = {}
    for p in plataformas:
        nome = da.nome_plataforma(p)
        por[nome] = {"min": da.limite(nome, "duracao_min_s"), "max": da.limite(nome, "duracao_max_s"),
                     "recomendada": da.limite(nome, "duracao_max_recomendada_s")}
    minimos = [v["min"] for v in por.values() if v["min"] is not None]
    maximos = [v["max"] for v in por.values() if v["max"] is not None]
    recs = [v["recomendada"] for v in por.values() if v["recomendada"] is not None]
    return {"min": float(max(minimos)) if minimos else 0.0, "max": float(min(maximos)) if maximos else None,
            "recomendada": float(min(recs)) if recs else None, "por_plataforma": por}


def sair_com_erro(e: Exception) -> int:
    """Imprime `erro: …` + dica e devolve o código (serve a Erro, da.DAErro e ao Erro da video-legendas)."""
    print(f"erro: {e}", file=sys.stderr)
    if getattr(e, "dica", None):
        print(f"  → {e.dica}", file=sys.stderr)
    return int(getattr(e, "codigo", 1) or 1)
