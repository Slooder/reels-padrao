#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""comum.py — o que cues.py e legendar.py dividem: achar o kit de direção de arte, erros, tempo e arquivos.

Nada aqui desenha. O kit é achado pela POSIÇÃO deste arquivo (<skills>/video-legendas/scripts/ → <skills>/
video-direcao-de-arte/kit), nunca por caminho embutido: a instalação final é uma cópia de pastas.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

sys.dont_write_bytecode = True          # a pasta da skill não acumula __pycache__

AQUI = Path(__file__).resolve().parent
SKILL = AQUI.parent
KIT = SKILL.parent / "video-direcao-de-arte" / "kit"
if not (KIT / "da.py").is_file():
    KIT = Path("~/.claude/skills/video-direcao-de-arte/kit").expanduser()
FERRAMENTA = "video-legendas"
DA_CLI = "\"$CRIABR_SKILLS\"/video-direcao-de-arte/kit/bin/da"


class Erro(Exception):
    """Erro com mensagem acionável: o que houve + o que fazer. `codigo` é o código de saída da CLI."""

    def __init__(self, mensagem: str, dica: str | None = None, codigo: int = 1):
        super().__init__(mensagem)
        self.mensagem, self.dica, self.codigo = mensagem, dica, codigo


def kit():
    """Importa o kit (da, texto, video, trava). Sem o kit instalado ao lado, erro claro em vez de ImportError."""
    if not (KIT / "da.py").is_file():
        raise Erro(f"não encontrei o kit de direção de arte em {KIT}.",
                   "Instale a skill video-direcao-de-arte ao lado desta (\"$CRIABR_SKILLS\"/video-direcao-de-arte/).", 127)
    if str(KIT) not in sys.path:
        sys.path.insert(0, str(KIT))
    try:
        import da, texto, video, trava  # noqa: E401
    except ImportError as e:
        raise Erro(f"o kit de direção de arte não carregou: {e}.",
                   "Rode com /opt/homebrew/bin/python3 (precisa de Pillow e numpy; o Python do sistema não tem).", 127)
    return da, texto, video, trava


def carregar_da(projeto=None, pistas=()):
    """A DA do projeto: `projeto` (pasta ou da.json) quando dado; senão a pasta atual e, por fim, as `pistas`
    (pasta da saída, pasta do vídeo). Sem DA em lugar nenhum, sobe da.SemDA (código 2: pare e chame a
    skill video-direcao-de-arte)."""
    da, _, _, _ = kit()
    if projeto:
        return da.carregar(str(projeto))
    falha = None
    for de in (Path.cwd(), *[Path(p) for p in pistas if p]):
        de = de if de.is_dir() else de.parent
        if not de.is_dir():
            continue
        try:
            return da.carregar(de=str(de))
        except da.SemDA as e:
            falha = falha or e
    if falha is not None:
        raise falha
    return da.carregar()


# ───────────────────────────────────────────────────────── linha de comando ──
class Analisador(argparse.ArgumentParser):
    """argparse com ajuda e erros em português; erro de uso sai com 64 (o 2 do argparse seria lido como "sem DA")."""
    _TRADUCOES = [
        (r"the following arguments are required: (.*)", r"faltam argumentos obrigatórios: \1"),
        (r"unrecognized arguments: (.*)", r"argumentos não reconhecidos: \1"),
        (r"argument (.*?): invalid choice: (.*?) \(choose from (.*)\)", r"argumento \1: opção inválida \2 (escolha entre \3)"),
        (r"argument (.*?): expected one argument", r"argumento \1: faltou o valor"),
        (r"argument (.*?): expected at least one argument", r"argumento \1: faltou ao menos um valor"),
        (r"argument (.*?): invalid (?:float|int) value: (.*)", r"argumento \1: número inválido \2"),
        (r"argument (.*?): invalid \w+ value: (.*)", r"argumento \1: valor inválido \2"),
        (r"argument (.*?): not allowed with argument (.*)", r"argumento \1: não pode ser usado junto com \2"),
        (r"argument (.*?): ignored explicit argument (.*)", r"argumento \1: não recebe valor (veio \2)"),
        (r"argument (.*?): (.*)", r"argumento \1: \2"),
    ]

    def __init__(self, *a, **k):
        k.setdefault("add_help", False)
        k.setdefault("formatter_class", argparse.RawDescriptionHelpFormatter)
        super().__init__(*a, **k)
        self._positionals.title = "argumentos"
        self._optionals.title = "opções"
        self.add_argument("-h", "--help", action="help", default=argparse.SUPPRESS, help="mostra esta ajuda e sai")

    def format_usage(self):
        return super().format_usage().replace("usage: ", "uso: ", 1)

    def format_help(self):
        return super().format_help().replace("usage: ", "uso: ", 1)

    def error(self, message):
        for padrao, troca in self._TRADUCOES:
            novo = re.sub(padrao, troca, message)
            if novo != message:
                message = novo
                break
        self.print_usage(sys.stderr)
        self.exit(64, f"erro: {message}\n  → veja as opções com --help\n")


# ─────────────────────────────────────────────────────────────── arquivos ──
def ler_json(caminho, o_que: str = "arquivo"):
    caminho = Path(str(caminho)).expanduser()
    if not caminho.is_file():
        raise Erro(f"{o_que} não encontrado: {caminho}", codigo=1)
    try:
        return json.loads(caminho.read_text(encoding="utf-8-sig"))
    except UnicodeDecodeError:
        raise Erro(f"{o_que} {caminho.name} não está em UTF-8.", "Regrave o arquivo em UTF-8.")
    except json.JSONDecodeError as e:
        raise Erro(f"{o_que} {caminho.name} não é JSON válido (linha {e.lineno}, coluna {e.colno}: {e.msg}).",
                   "Confira vírgulas e aspas; o arquivo precisa ser JSON puro.")


def gravar_texto(caminho, texto: str) -> Path:
    """Grava de forma atômica (arquivo provisório + troca): leitor nenhum vê o arquivo pela metade."""
    caminho = Path(str(caminho)).expanduser()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    tmp = caminho.with_name(f"_{caminho.name}.parcial")
    tmp.write_text(texto, encoding="utf-8")
    os.replace(tmp, caminho)
    return caminho


def gravar_json(caminho, obj) -> Path:
    return gravar_texto(caminho, json.dumps(obj, ensure_ascii=False, indent=1) + "\n")


def sha256_arquivo(caminho) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def absoluto(caminho) -> Path:
    """Caminho absoluto SEM seguir o atalho do último componente: `render/final.mp4` que é um link simbólico para um
    disco externo continua se chamando `final.mp4` e morando em `render/` (o nome das legendas sai dele)."""
    return Path(os.path.abspath(str(Path(str(caminho)).expanduser())))


def relativo(caminho, raiz) -> str:
    """Caminho relativo à raiz do projeto, com barras normais (contrato entre as skills); fora da raiz, absoluto.
    Arquivo ou pasta do projeto que é link simbólico para fora continua relativo: vale o lugar do link, não o do alvo."""
    p = absoluto(caminho)
    raizes = [absoluto(raiz), Path(str(raiz)).expanduser().resolve()]
    for cand in (p, p.parent.resolve() / p.name, p.resolve()):
        for r in raizes:
            try:
                return cand.relative_to(r).as_posix()
            except ValueError:
                continue
    return p.resolve().as_posix()


# ──────────────────────────────────────────────────────────────── texto ──
def sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def chave(s: str) -> str:
    """Forma de comparação: minúsculas e sem acento ("História" = "historia")."""
    return sem_acento(s).casefold().strip()


def nome_de_arquivo(s: str) -> str:
    """Nome seguro para arquivo, preservando acentos e espaços; só tira o que o sistema de arquivos não aceita."""
    s = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "-", str(s)).strip(" .")
    return s or "legenda"


# ──────────────────────────────────────────────────────────────── tempo ──
def hms(t: float, sep: str = ",") -> str:
    """Segundos → HH:MM:SS,mmm (SRT, vírgula) ou HH:MM:SS.mmm (WebVTT, ponto)."""
    ms = int(round(max(0.0, float(t)) * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"


def relogio(t: float) -> str:
    """Segundos → m:ss,d para mensagens ("0:07,4")."""
    t = max(0.0, float(t))
    m, s = divmod(t, 60)
    return f"{int(m)}:{s:04.1f}".replace(".", ",")


def br(x: float, casas: int = 2) -> str:
    """Número com vírgula decimal, para mensagens em português."""
    return f"{float(x):.{casas}f}".replace(".", ",")


def tempo_cli(valor: str) -> float:
    """Tempo digitado na linha de comando: segundos ("12.5", "12,5") ou relógio ("1:02.5", "0:01:02,5")."""
    s = str(valor).strip().replace(",", ".")
    try:
        partes = [float(p) for p in s.split(":")]
    except ValueError:
        raise ValueError(f"tempo inválido: {valor!r} (use segundos, ex.: 12.5, ou m:ss, ex.: 1:02.5)")
    if not 1 <= len(partes) <= 3 or any(p < 0 for p in partes):
        raise ValueError(f"tempo inválido: {valor!r} (use segundos, ex.: 12.5, ou m:ss, ex.: 1:02.5)")
    total = 0.0
    for p in partes:
        total = total * 60 + p
    return total
