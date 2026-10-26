#!/usr/bin/env python3
"""base.py — o que roteiro.py, youtube.py e imagens.py dividem: erro com dica, pasta do projeto, tempos, e os módulos
das skills vizinhas (registro da video-broll e kit de direção de arte), achados pela POSIÇÃO desta pasta."""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
AQUI = Path(__file__).resolve().parent
SKILLS = AQUI.parents[1]
VERSAO = "1.0.0"
OK, ERRO, SEM_DA, USO, SEM_REDE = 0, 1, 2, 64, 75


class Erro(Exception):
    """Erro com mensagem (o que houve) e dica (o que fazer)."""

    def __init__(self, mensagem: str, dica: str | None = None, codigo: int = ERRO):
        super().__init__(mensagem)
        self.mensagem, self.dica, self.codigo = mensagem, dica, codigo


def diz(*partes, erro: bool = False) -> None:
    print(*partes, file=sys.stderr if erro else sys.stdout, flush=True)


def _vizinha(skill: str, sub: str, arquivo: str) -> Path:
    for raiz in (SKILLS, Path("~/.claude/skills").expanduser()):
        pasta = raiz / skill / sub
        if (pasta / arquivo).is_file():
            return pasta
    raise Erro(f"não achei {skill}/{sub}/{arquivo} ao lado desta skill.",
               f"Instale a skill {skill} em \"$CRIABR_SKILLS\"/ (a video-pauta-midia registra e trata a mídia por ela).")


def registro():
    """Módulo registro.py da video-broll (dono de broll/licencas.json e broll/creditos.md)."""
    pasta = str(_vizinha("video-broll", "scripts", "registro.py"))
    if pasta not in sys.path:
        sys.path.insert(0, pasta)
    import registro as modulo
    return modulo


def kit():
    """(da, video, trava) do kit de direção de arte."""
    pasta = str(_vizinha("video-direcao-de-arte", "kit", "da.py"))
    if pasta not in sys.path:
        sys.path.insert(0, pasta)
    try:
        import da
        import trava
        import video
    except ImportError as e:
        raise Erro(f"este Python ({sys.executable}) não tem {e.name}, de que o kit de direção de arte precisa.",
                   "Rode com /opt/homebrew/bin/python3 (qualquer Python 3.10+ com Pillow e numpy serve).")
    return da, video, trava


def contato() -> str:
    """Contato do usuário para o User-Agent (VIDEO_OPS_CONTATO, do ambiente ou da configuração da video-broll)."""
    valor = os.environ.get("VIDEO_OPS_CONTATO")
    if not valor:
        try:
            registro()
            import comum
            valor = comum.config("VIDEO_OPS_CONTATO")
        except Exception:                                    # sem a configuração da vizinha o contato só fica vazio
            valor = None
    return re.sub(r"[^\x20-\x7e]", "", valor or "") or "contato nao configurado: defina VIDEO_OPS_CONTATO"


def achar_projeto(arg=None) -> Path:
    """--projeto, ou a primeira pasta acima da atual com da/da.json, roteiro/pauta.json ou broll/licencas.json; senão, a atual."""
    if arg:
        p = Path(str(arg)).expanduser()
        if not p.is_dir():
            raise Erro(f"a pasta do projeto não existe: {p}", "Passe a raiz do projeto em --projeto (a pasta que tem da/ e roteiro/).", SEM_DA)
        return p.resolve()
    aqui = Path.cwd().resolve()
    for p in (aqui, *aqui.parents):
        if any((p / x).is_file() for x in ("da/da.json", "roteiro/pauta.json", "broll/licencas.json")):
            return p
    return aqui


def exigir_da(projeto: Path):
    """Passo 0: sem da/da.json nada é baixado para o projeto (o material só entra em peça pelo tratamento da DA)."""
    da, _video, _trava = kit()
    try:
        return da.carregar(projeto)
    except da.SemDA as e:
        raise Erro(str(getattr(e, "mensagem", e)), "Este projeto não tem direção de arte: pare e crie uma com a skill video-direcao-de-arte "
                   "(\"$CRIABR_SKILLS\"/video-direcao-de-arte/kit/bin/da init \"<pasta>\" --nome \"…\" --base <preset>).", SEM_DA)
    except da.DAErro as e:
        raise Erro(str(e), codigo=getattr(e, "codigo", ERRO) or ERRO)


def segundos(valor) -> float | None:
    """"83", "83.5", "1:23", "1:02:03" ou "1m23s" → segundos; None fica None."""
    if valor is None or valor == "":
        return None
    t = str(valor).strip().lower().replace(",", ".")
    m = re.fullmatch(r"(?:(\d+)h)?(?:(\d+)m)?(?:(\d+(?:\.\d+)?)s?)?", t)
    if m and any(m.groups()) and not re.fullmatch(r"\d+(\.\d+)?", t):
        return int(m.group(1) or 0) * 3600 + int(m.group(2) or 0) * 60 + float(m.group(3) or 0)
    try:
        total = 0.0
        for parte in t.split(":"):
            total = total * 60 + float(parte)
    except ValueError:
        raise Erro(f"tempo inválido: {valor!r}.", "Use segundos (83), mm:ss (1:23) ou hh:mm:ss (1:02:03).", USO)
    return total


def relogio(s) -> str:
    if s is None:
        return "—"
    s = float(s)
    h, resto = divmod(int(s), 3600)
    m, seg = divmod(resto, 60)
    fracao = f"{s - int(s):.1f}"[1:] if abs(s - int(s)) > 0.04 else ""
    return (f"{h}:{m:02d}:{seg:02d}" if h else f"{m}:{seg:02d}") + fracao


_PT = (("the following arguments are required", "faltou informar"), ("unrecognized arguments", "opção desconhecida"),
       ("expected one argument", "faltou o valor"), ("invalid choice", "valor fora da lista"), ("argument ", "opção "),
       ("choose from", "escolha entre"), ("not allowed with", "não combina com"), ("one of the arguments", "informe uma das opções"),
       ("is required", "é obrigatória"))


class Parser(argparse.ArgumentParser):
    def error(self, message):
        for de, para in _PT:
            message = message.replace(de, para)
        diz(f"uso incorreto: {message}\n  → veja: {self.prog} --help", erro=True)
        raise SystemExit(USO)


def rodar(principal) -> int:
    try:
        return int(principal() or 0)
    except Erro as e:
        diz(f"erro: {e.mensagem}" + (f"\n  → {e.dica}" if e.dica else ""), erro=True)
        return e.codigo
    except KeyboardInterrupt:
        diz("interrompido.", erro=True)
        return 130
    except Exception as e:                                   # RegistroErro da video-broll tem a mesma forma (mensagem, dica, codigo)
        if not hasattr(e, "mensagem"):
            raise
        dica = getattr(e, "dica", None)
        diz(f"erro: {e.mensagem}" + (f"\n  → {dica}" if dica else ""), erro=True)
        return getattr(e, "codigo", ERRO) or ERRO
