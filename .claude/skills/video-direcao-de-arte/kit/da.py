#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""da.py — núcleo do kit de direção de arte (DA) por projeto.

Cada projeto de vídeo tem UMA fonte de verdade visual: <projeto>/da/da.json.
Nenhuma skill decide cor, fonte, curva de animação, grade, legenda ou moldura por
conta própria: todas leem tokens da DA através deste arquivo, que é ao mesmo
tempo linha de comando e módulo importável.

Linha de comando: \"$CRIABR_SKILLS\"/video-direcao-de-arte/kit/bin/da <subcomando> [--help]
(bin/da é o executável que acha um Python com Pillow e roda este arquivo; funciona em zsh, bash e sh)
    init            cria a estrutura do projeto, o da.json e o bloco do CLAUDE.md
    achar           localiza a DA subindo as pastas (código 2 se não houver)
    validar         confere esquema e semântica (contraste, arquivos, faixas)
    compilar        gera da/build/ (resolvida, css, js, grade, lock) e da/DA.md
    mostrar         resumo legível no terminal
    token           imprime o valor de um token (resolve cores)
    presets         lista presets embutidos e pessoais
    salvar-preset   guarda a DA do projeto na biblioteca pessoal
    extrair         analisa imagens/vídeos de referência (paleta, contraste, grão)
    aprovar         marca a DA como aprovada
    revisar         abre nova revisão (zera a aprovação)
    lint            reprova cor/fonte literal em peças (HTML, CSS, JS, JSON, SVG e Python)
    carimbar        grava o sidecar <saida>.da.json
    conferir-carimbo  reprova peça sem carimbo, com DA velha ou auditoria pulada
    grade           mostra/aplica a cadeia ffmpeg do tratamento de imagem
Extensões (da_ext_*.py, carregadas sozinhas)
    conferencia     conferência final do projeto (camada C5): DA aprovada, lint, carimbos, loudness e limites de
                    plataforma → qa/relatorio.json, o portão de publicação (da_ext_conferencia.py)
    prancha · teste-movimento · render     documentos de aprovação e motor HTML → imagem/vídeo (da_ext_motor.py)

Como módulo
    import os, sys
    sys.path.insert(0, os.path.expanduser("~/.claude/skills/video-direcao-de-arte/kit"))
    import da
    d = da.carregar()                    # acha, recompila se preciso e devolve a DA
    d.cor("primaria")                    # "#FFC700"
    d.rgb("fundo")                       # (10, 10, 10)
    d.fonte("titulo")["caminho"]         # caminho absoluto do arquivo de fonte
    d.px(d["legenda"]["tamanho"], 1080, 1920)
    L, A, fps = d.formato("vertical")
    d.margens("vertical", "uniao")       # zona segura em pixels
    d.grade("horizontal")                # cadeia de filtros ffmpeg
    da.carimbar("render/cena.mp4", ferramenta="motor", formato="horizontal",
                parametros={...}, auditoria="ok")

Códigos de saída: 0 ok · 1 reprovado/erro · 2 nenhuma DA encontrada · 64 uso incorreto ·
75 desistiu de esperar a trava · 124 comando morto por inatividade · 128+N interrompido pelo sinal N.

Ponto de extensão: registrar_subcomando(nome, ajuda, configurar, executar) ou um
arquivo da_ext_<nome>.py ao lado deste, com uma função registrar(da).
"""
from __future__ import annotations

import argparse
import copy
import difflib
import hashlib
import importlib.util
import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unicodedata
from datetime import datetime
from fractions import Fraction
from pathlib import Path

sys.dont_write_bytecode = True     # D9: nada de __pycache__ dentro da skill (trava.py apaga o que já tiver nascido)
KIT = Path(__file__).resolve().parent
if str(KIT) not in sys.path:
    sys.path.insert(0, str(KIT))
import trava  # noqa: E402  (vizinho deste arquivo)

# ─────────────────────────────────────────────────────────────── constantes ──
try:
    KIT_VERSAO = (KIT / "VERSAO").read_text(encoding="utf-8").strip() or "0.0.0"
except OSError:
    KIT_VERSAO = "0.0.0"

KIT_FINAL = "\"$CRIABR_SKILLS\"/video-direcao-de-arte/kit"   # caminho citado em textos para humanos
DA_CLI = KIT_FINAL + "/bin/da"                             # a chamada que a documentação e as mensagens mostram (zsh, bash e sh)
SKILL_DA = "video-direcao-de-arte"
ESQUEMA_ARQ = KIT / "da_esquema.json"
PRESETS_DIR = KIT / "presets"
MODELO_CLAUDE = KIT / "modelos" / "CLAUDE.projeto.md"
PRESET_PADRAO = "dossie"

SAIDA_OK, SAIDA_ERRO, SAIDA_SEM_DA, SAIDA_USO = 0, 1, 2, 64

PASTAS_DA = ("fontes", "luts", "texturas", "logos", "referencias")
PASTAS_TRABALHO = ("pesquisa", "roteiro", "bruto", "transcricao", "broll", "animacoes",
                   "legendas", "cortes", "thumbs", "publicacao", "qa", "render")
PASTAS_COM_PECAS = ("animacoes", "legendas", "cortes", "thumbs", "render", "broll/tratado")
# subpastas que o init também cria: o b-roll baixado (nunca conferido) fica separado do tratado (carimbado, conferido)
SUBPASTAS_TRABALHO = ("broll/bruto", "broll/tratado")
# D15 — intermediários: pasta ou arquivo cujo nome começa por este prefixo (animacoes/_trabalho/, legendas/_png/,
# render/_base.mp4) não é peça: conferir-carimbo e o lint padrão passam por cima. broll/bruto/ também não é conferido.
PREFIXO_INTERMEDIARIO = "_"
PASTAS_SEM_PECAS = ("broll/bruto",)
PLATAFORMAS_ARQ = KIT / "plataformas.json"
PLATAFORMAS = ("youtube", "shorts", "reels", "tiktok")        # nomes canônicos (D16); apelidos em plataformas.json → apelidos
# nome canônico → chave da zona em formatos.margens_seguras do da.json (contrato v1: a zona do Reels chama-se "instagram")
ZONA_DA_PLATAFORMA = {"reels": "instagram", "youtube": "padrao", "shorts": "shorts", "tiktok": "tiktok"}
TRANSICOES = ("corte", "fade", "empurra", "mascara", "desliza", "zoom")
SAIDAS_BUILD = ("da.resolvida.json", "da.css", "da.js", "grade.json", "da.lock")
# Identidade (da_sha256), regra exata: TODO o conteúdo com a herança aplicada, EXCETO as seções abaixo e qualquer chave
# (em qualquer profundidade) iniciada por um dos prefixos de anotação livre. Ver identidade().
FORA_DA_IDENTIDADE = ("herda", "projeto", "conceito")
PREFIXOS_LIVRES = ("_", "x_")
PAPEIS_BASE = ("titulo", "subtitulo", "corpo", "dados", "legenda")
FORMATOS_VIDEO = ("horizontal", "vertical", "quadrado")
EXT_VIDEO = {".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi", ".mxf"}
EXT_IMAGEM = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff", ".gif"}
EXT_LUT = {".cube", ".3dl", ".dat", ".m3d", ".csp"}
CLAUDE_INI, CLAUDE_FIM = "<!-- DA:INICIO -->", "<!-- DA:FIM -->"


# ──────────────────────────────────────────────────────────────────── erros ──
class DAErro(Exception):
    """Erro do kit com mensagem acionável. `codigo` é o código de saída da CLI."""
    codigo = SAIDA_ERRO

    def __init__(self, mensagem: str, dica: str | None = None, codigo: int | None = None):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.dica = dica
        if codigo is not None:
            self.codigo = codigo

    def __str__(self) -> str:
        return self.mensagem if not self.dica else f"{self.mensagem}\n{self.dica}"


class SemDA(DAErro):
    """Nenhuma direção de arte encontrada (código de saída 2)."""
    codigo = SAIDA_SEM_DA


class DAInvalida(DAErro):
    """A DA não passou na validação; `erros` e `avisos` trazem os detalhes."""

    def __init__(self, caminho, erros: list[str], avisos: list[str] | None = None):
        self.erros = list(erros)
        self.avisos = list(avisos or [])
        linhas = "\n".join(f"  ✗ {e}" for e in self.erros)
        super().__init__(f"DA inválida ({len(self.erros)} erro(s)) em {caminho}:\n{linhas}",
                         dica="Corrija o da.json e rode `da.py validar` de novo.")


# ─────────────────────────────────────────────────────────── utilidades base ──
def agora_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def video_ops_home() -> Path:
    """Raiz de configuração do usuário (VIDEO_OPS_HOME ou ~/.config/video-ops)."""
    v = os.environ.get("VIDEO_OPS_HOME")
    return Path(v).expanduser() if v else Path.home() / ".config" / "video-ops"


def presets_pessoais_dir() -> Path:
    return video_ops_home() / "da-presets"


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_arquivo(caminho, limite: int | None = None) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        restante = limite
        while True:
            bloco = f.read(1 << 20 if restante is None else min(1 << 20, restante))
            if not bloco:
                break
            h.update(bloco)
            if restante is not None:
                restante -= len(bloco)
                if restante <= 0:
                    break
    return h.hexdigest()


def ler_json(caminho):
    caminho = Path(caminho)
    try:
        texto = caminho.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        raise DAErro(f"arquivo não encontrado: {caminho}")
    except (OSError, UnicodeDecodeError) as e:
        raise DAErro(f"não consegui ler {caminho}: {e}")
    try:
        return json.loads(texto)
    except json.JSONDecodeError as e:
        raise DAErro(f"{caminho}: JSON inválido na linha {e.lineno}, coluna {e.colno} ({e.msg}).",
                     dica="Vírgula sobrando, aspas faltando e comentários (// …) são as causas mais comuns.")


def _escalar(v) -> bool:
    return v is None or isinstance(v, (str, int, float, bool))


def _linha_json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(", ", ": "))


def json_bonito(obj, _nivel: int = 0, _largura: int = 92) -> str:
    """JSON indentado, mas com listas/objetos pequenos de escalares numa linha só
    (curvas, margens, paradas de gradiente) — legível para quem edita à mão."""
    recuo = "  " * _nivel
    if isinstance(obj, dict):
        if not obj:
            return "{}"
        plano = all(_escalar(v) or (isinstance(v, (list, tuple)) and all(_escalar(x) for x in v)) for v in obj.values())
        if plano and len(obj) <= 6:
            linha = _linha_json(obj)
            if len(linha) + len(recuo) <= _largura:
                return linha
        itens = [f"{recuo}  {json.dumps(str(k), ensure_ascii=False)}: {json_bonito(v, _nivel + 1, _largura)}"
                 for k, v in obj.items()]
        return "{\n" + ",\n".join(itens) + "\n" + recuo + "}"
    if isinstance(obj, (list, tuple)):
        if not obj:
            return "[]"
        simples = all(_escalar(v) or (isinstance(v, (list, tuple)) and all(_escalar(x) for x in v)) for v in obj)
        if simples:
            linha = _linha_json(obj)
            if len(linha) + len(recuo) <= _largura:
                return linha
        itens = [f"{recuo}  {json_bonito(v, _nivel + 1, _largura)}" for v in obj]
        return "[\n" + ",\n".join(itens) + "\n" + recuo + "]"
    return json.dumps(obj, ensure_ascii=False)


def gravar_texto(caminho, texto: str) -> Path:
    """Escrita atômica: grava <arquivo>.parcial e só então renomeia."""
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    tmp = caminho.with_name(f"{caminho.name}.{os.getpid()}.parcial")
    try:
        tmp.write_text(texto, encoding="utf-8")
        os.replace(tmp, caminho)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
    return caminho


def gravar_json(caminho, obj) -> Path:
    return gravar_texto(caminho, json_bonito(obj) + "\n")


def slugificar(nome: str) -> str:
    s = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode("ascii").lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "projeto"


def _num(x, casas: int = 4) -> str:
    """Número curto para CSS/ffmpeg: sem zeros à direita, sem notação científica."""
    if isinstance(x, bool):
        return "1" if x else "0"
    if isinstance(x, int):
        return str(x)
    s = f"{float(x):.{casas}f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return "0" if s in ("", "-0") else s


def _ptbr(x, casas: int = 2) -> str:
    """Número com vírgula decimal para textos em português."""
    return _num(x, casas).replace(".", ",")


def _sugerir(valor: str, opcoes, n: int = 1) -> str:
    perto = difflib.get_close_matches(str(valor), [str(o) for o in opcoes], n=n, cutoff=0.6)
    return f" Quis dizer {' ou '.join(repr(p) for p in perto)}?" if perto else ""


def _rel(caminho, base=None) -> str:
    """Caminho relativo à base (ou ao cwd) quando possível — para mensagens."""
    try:
        rel = os.path.relpath(str(caminho), str(base or os.getcwd()))
    except ValueError:
        return str(caminho)
    return str(caminho) if rel.startswith(".." + os.sep) or rel == ".." else rel   # fora da base: o absoluto lê melhor que ../../../


# ────────────────────────────────────────────────────────────────────── cor ──
_RE_HEX6 = re.compile(r"^#[0-9a-fA-F]{6}$")
_RE_HEX3 = re.compile(r"^#[0-9a-fA-F]{3}$")


def hex_normal(h: str) -> str:
    """'#fc0' ou '#ffcc00' → '#FFCC00'. Levanta DAErro se não for hex de cor."""
    if isinstance(h, str):
        h = h.strip()
        if _RE_HEX6.match(h):
            return h.upper()
        if _RE_HEX3.match(h):
            return "#" + "".join(c * 2 for c in h[1:]).upper()
    raise DAErro(f"{h!r} não é uma cor hexadecimal (#RRGGBB)")


def hex_para_rgb(h: str) -> tuple[int, int, int]:
    h = hex_normal(h)
    return int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)


def rgb_para_hex(r, g, b) -> str:
    return "#%02X%02X%02X" % tuple(max(0, min(255, int(round(v)))) for v in (r, g, b))


def _linear(c: float) -> float:
    c /= 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminancia(cor) -> float:
    """Luminância relativa WCAG (0–1) de um hex ou trio RGB."""
    r, g, b = hex_para_rgb(cor) if isinstance(cor, str) else cor
    return 0.2126 * _linear(r) + 0.7152 * _linear(g) + 0.0722 * _linear(b)


def contraste(a, b) -> float:
    """Razão de contraste WCAG entre duas cores (1 a 21)."""
    la, lb = luminancia(a), luminancia(b)
    if la < lb:
        la, lb = lb, la
    return (la + 0.05) / (lb + 0.05)


def rgb_para_lab(cor) -> tuple[float, float, float]:
    r, g, b = hex_para_rgb(cor) if isinstance(cor, str) else cor
    r, g, b = _linear(r), _linear(g), _linear(b)
    x = (0.4124564 * r + 0.3575761 * g + 0.1804375 * b) / 0.95047
    y = 0.2126729 * r + 0.7151522 * g + 0.0721750 * b
    z = (0.0193339 * r + 0.1191920 * g + 0.9503041 * b) / 1.08883

    def f(t):
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116

    fx, fy, fz = f(x), f(y), f(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def delta_e(a, b) -> float:
    """Distância perceptual simples (CIE76) entre duas cores."""
    la, lb = rgb_para_lab(a), rgb_para_lab(b)
    return math.sqrt(sum((p - q) ** 2 for p, q in zip(la, lb)))


def hex_do_item(v, secao_cor: dict) -> str:
    """Item de cor.dados (ou cor.neutros): '#RRGGBB' ou o NOME de uma cor da paleta ('primaria') → '#RRGGBB'.
    Escrever o nome em vez do hex faz a série acompanhar a paleta: troca-se a primária e dado-1 muda junto."""
    paleta = (secao_cor or {}).get("paleta") if isinstance(secao_cor, dict) else None
    if isinstance(v, str) and isinstance(paleta, dict) and v.strip() in paleta:
        return hex_normal(paleta[v.strip()])
    return hex_normal(v)


def resolver_cor(valor, secao_cor: dict, onde: str = "") -> str:
    """Token de cor → '#RRGGBB'. Aceita hex, nome da paleta, 'dado-N' e 'neutro-N' (N a partir de 1)."""
    prefixo = f"{onde}: " if onde else ""
    if not isinstance(valor, str) or not valor.strip():
        raise DAErro(f"{prefixo}esperava um token de cor (nome da paleta ou #RRGGBB), veio {valor!r}")
    valor = valor.strip()
    if valor.startswith("#"):
        try:
            return hex_normal(valor)
        except DAErro:
            raise DAErro(f"{prefixo}{valor!r} não é um hex válido; use #RRGGBB")
    paleta = (secao_cor or {}).get("paleta") or {}
    if valor in paleta:
        return hex_normal(paleta[valor])
    m = re.fullmatch(r"(dado|neutro)-(\d+)", valor)
    if m:
        lista = (secao_cor or {}).get("dados" if m.group(1) == "dado" else "neutros") or []
        i = int(m.group(2))
        if 1 <= i <= len(lista):
            return hex_do_item(lista[i - 1], secao_cor)
        raise DAErro(f"{prefixo}{valor!r} não existe: há {len(lista)} cor(es) em cor.{'dados' if m.group(1) == 'dado' else 'neutros'}")
    raise DAErro(f"{prefixo}cor {valor!r} não é um #RRGGBB nem um nome da paleta "
                 f"({', '.join(paleta) or 'paleta vazia'}).{_sugerir(valor, paleta)}")


def cores_permitidas(secao_cor: dict) -> list[str]:
    """Paleta + dados + neutros, sem repetição, na ordem em que aparecem."""
    vistas, saida = set(), []
    secao_cor = secao_cor if isinstance(secao_cor, dict) else {}
    paleta = secao_cor.get("paleta")
    fontes = list(paleta.values()) if isinstance(paleta, dict) else []
    for chave in ("dados", "neutros"):
        lista = secao_cor.get(chave)
        if isinstance(lista, (list, tuple)):
            fontes += list(lista)
    for v in fontes:
        try:
            h = hex_do_item(v, secao_cor)
        except DAErro:
            continue
        if h not in vistas:
            vistas.add(h)
            saida.append(h)
    return saida


def nome_do_token(hexa: str, secao_cor: dict) -> str | None:
    """Nome do token que vale exatamente `hexa` ('primaria', 'dado-2', 'neutro-1') ou None."""
    try:
        hexa = hex_normal(hexa)
    except DAErro:
        return None
    for k, v in ((secao_cor or {}).get("paleta") or {}).items():
        if isinstance(v, str) and v.upper() == hexa:
            return k
    for rotulo, chave in (("dado", "dados"), ("neutro", "neutros")):
        for i, v in enumerate((secao_cor or {}).get(chave) or [], 1):
            try:
                if isinstance(v, str) and hex_do_item(v, secao_cor) == hexa:
                    return f"{rotulo}-{i}"
            except DAErro:
                continue
    return None


def css_var_do_token(token: str) -> str:
    if token.startswith(("dado-", "neutro-")):
        return f"--da-{token}"
    return f"--da-cor-{token.replace('_', '-')}"


# ─────────────────────────────────────────────────────────────────── fontes ──
def info_fonte(caminho) -> dict:
    """Lê o cabeçalho sfnt e a tabela fvar: {'formato', 'variavel', 'eixos': {'wght': (mín, padrão, máx)}}.
    Levanta DAErro se o arquivo não for uma fonte TrueType/OpenType."""
    caminho = Path(caminho)
    try:
        with open(caminho, "rb") as f:
            cab = f.read(12)
            if len(cab) < 12:
                raise DAErro(f"{caminho} é pequeno demais para ser uma fonte")
            marca = cab[:4]
            if marca in (b"wOFF", b"wOF2"):
                return {"formato": marca.decode().lower(), "variavel": False, "eixos": {}, "inspecionada": False}
            base = 0
            if marca == b"ttcf":                       # coleção: usa a primeira fonte
                f.seek(12)
                base = struct.unpack(">I", f.read(4))[0]
                f.seek(base)
                cab = f.read(12)
                marca = cab[:4]
            if marca not in (b"\x00\x01\x00\x00", b"OTTO", b"true", b"typ1"):
                raise DAErro(f"{caminho} não é um arquivo de fonte TrueType/OpenType")
            n = struct.unpack(">H", cab[4:6])[0]
            tabelas = {}
            for _ in range(n):
                reg = f.read(16)
                if len(reg) < 16:
                    break
                tag, _cs, off, tam = struct.unpack(">4sIII", reg)
                tabelas[tag] = (off, tam)
            eixos = {}
            if b"fvar" in tabelas:
                off, tam = tabelas[b"fvar"]
                f.seek(off)
                dados = f.read(tam)
                _maj, _min, ini, _res, qtd, tam_eixo = struct.unpack(">HHHHHH", dados[:12])
                for i in range(qtd):
                    p = ini + i * tam_eixo
                    tag, mn, df, mx = struct.unpack(">4siii", dados[p:p + 16])
                    eixos[tag.decode("ascii", "replace").strip()] = (mn / 65536, df / 65536, mx / 65536)
            return {"formato": "otf" if marca == b"OTTO" else "ttf", "variavel": bool(eixos),
                    "eixos": eixos, "inspecionada": True}
    except (OSError, struct.error) as e:
        raise DAErro(f"não consegui ler a fonte {caminho}: {e}")


# ────────────────────────────────────────────────────────────── descoberta ──
def _alvo_da(valor, origem: str) -> Path:
    p = Path(str(valor)).expanduser()
    if p.is_dir():
        for cand in (p / "da" / "da.json", p / "da.json"):
            if cand.is_file():
                return cand.resolve()
        raise SemDA(f"{origem} aponta para a pasta {p}, mas ela não tem da/da.json nem da.json.",
                    dica=_dica_criar(p))
    if p.is_file():
        return p.resolve()
    if p.name == "da.json":
        projeto = p.parent.parent if p.parent.name == "da" else p.parent
    else:
        projeto = p if not p.suffix else p.parent
    raise SemDA(f"{origem} aponta para {p}, que não existe.", dica=_dica_criar(projeto))


def _dica_criar(pasta) -> str:
    return (f"Crie a direção de arte com a skill {SKILL_DA}:\n"
            f"  {DA_CLI} init \"{pasta}\" --nome \"Nome do projeto\" --base {PRESET_PADRAO}\n"
            f"Sem DA não se renderiza nada.")


def achar(de=None, da=None, obrigatorio: bool = True) -> Path | None:
    """Localiza o da.json do projeto.

    Ordem: argumento `da` (flag --da) > variável DA_JSON > subir as pastas a partir de
    `de` (flag --de) ou do diretório atual até encontrar da/da.json.
    Sem DA: levanta SemDA (código 2) — ou devolve None se obrigatorio=False."""
    if da:
        return _alvo_da(da, "--da")
    env = os.environ.get("DA_JSON", "").strip()
    if env:
        return _alvo_da(env, "DA_JSON")
    inicio = Path(str(de)).expanduser() if de else Path.cwd()
    try:
        inicio = inicio.resolve()
    except OSError:
        pass
    if inicio.is_file() or (not inicio.exists() and inicio.suffix):
        inicio = inicio.parent
    for pasta in (inicio, *inicio.parents):
        cand = pasta / "da" / "da.json"
        if cand.is_file():
            return cand
    if not obrigatorio:
        return None
    raise SemDA(f"Nenhuma direção de arte encontrada a partir de {inicio} "
                f"(procurei da/da.json nesta pasta e em todas as pastas acima).",
                dica=_dica_criar(inicio))


def raiz_do_projeto(da_json: Path) -> Path:
    da_json = Path(da_json)
    return da_json.parent.parent if da_json.parent.name == "da" else da_json.parent


def _dentro_do_kit(caminho: Path) -> bool:
    try:
        Path(caminho).resolve().relative_to(KIT)
        return True
    except ValueError:
        return False


def base_de_recursos(da_json: Path) -> Path:
    """Pasta contra a qual os caminhos relativos de um da.json são resolvidos:
    da/ no projeto, a pasta do preset na biblioteca pessoal, o kit nos presets embutidos."""
    da_json = Path(da_json).resolve()
    if da_json.parent == PRESETS_DIR:
        return KIT
    return da_json.parent


# ─────────────────────────────────────────────────────────── presets/herança ──
def listar_presets() -> list[dict]:
    """Presets embutidos e pessoais: [{'nome','origem','caminho','frase','valido'}]."""
    saida, vistos = [], set()
    if PRESETS_DIR.is_dir():
        for arq in sorted(PRESETS_DIR.glob("*.json")):
            saida.append({"nome": arq.stem, "origem": "embutido", "caminho": arq})
            vistos.add(arq.stem)
    pess = presets_pessoais_dir()
    if pess.is_dir():
        for pasta in sorted(p for p in pess.iterdir() if p.is_dir()):
            arq = pasta / "da.json"
            if arq.is_file():
                saida.append({"nome": pasta.name, "origem": "pessoal", "caminho": arq,
                              "ofuscado": pasta.name in vistos})
    for p in saida:
        try:
            dados = ler_json(p["caminho"])
            p["frase"] = ((dados.get("conceito") or {}).get("frase") or "").strip() or "(sem frase de conceito)"
            p["valido"] = True
        except DAErro as e:
            p["frase"] = f"(ilegível: {e.mensagem})"
            p["valido"] = False
    return saida


def achar_preset(nome: str) -> Path:
    """Caminho do da.json de um preset pelo nome (embutido primeiro, depois pessoal)."""
    nome = str(nome).strip()
    emb = PRESETS_DIR / f"{nome}.json"
    if emb.is_file():
        return emb
    pess = presets_pessoais_dir() / nome / "da.json"
    if pess.is_file():
        return pess
    nomes = [p["nome"] for p in listar_presets()]
    raise DAErro(f"preset {nome!r} não existe.{_sugerir(nome, nomes)}",
                 dica="Presets disponíveis: " + (", ".join(nomes) or "(nenhum)") +
                      f"\nLista completa: {DA_CLI} presets")


def _parece_caminho(v: str) -> bool:
    return v.endswith(".json") or "/" in v or os.sep in v or v.startswith(("~", "."))


def _resolver_herda(valor: str, pasta_do_filho: Path) -> Path:
    v = str(valor).strip()
    if _parece_caminho(v):
        p = Path(v).expanduser()
        if not p.is_absolute():
            p = pasta_do_filho / p
        if p.is_dir():
            p = p / "da" / "da.json" if (p / "da" / "da.json").is_file() else p / "da.json"
        if not p.is_file():
            raise DAErro(f"\"herda\": {valor!r} aponta para {p}, que não existe.",
                         dica="Use o nome de um preset (da.py presets) ou o caminho de outro da.json.")
        return p.resolve()
    return achar_preset(v).resolve()


def fundir(base, filho):
    """Deep-merge: o filho vence; dicionários se fundem; listas e escalares substituem inteiros."""
    if isinstance(base, dict) and isinstance(filho, dict):
        saida = {k: copy.deepcopy(v) for k, v in base.items()}
        for k, v in filho.items():
            saida[k] = fundir(saida[k], v) if k in saida else copy.deepcopy(v)
        return saida
    return copy.deepcopy(filho)


def carregar_cadeia(da_json) -> list[dict]:
    """Do arquivo pedido até o ancestral mais distante:
    [{'caminho': Path, 'dados': dict, 'sha256': str (bytes do arquivo), 'base': Path}]."""
    cadeia, atual = [], Path(da_json).resolve()
    while True:
        if any(c["caminho"] == atual for c in cadeia):
            trilha = " → ".join(_rel(c["caminho"]) for c in cadeia) + f" → {_rel(atual)}"
            raise DAErro(f"herança em ciclo: {trilha}",
                         dica="Um da.json não pode herdar (direta ou indiretamente) de si mesmo; corrija a chave \"herda\".")
        if len(cadeia) >= 12:
            raise DAErro("herança profunda demais (mais de 12 níveis); simplifique a cadeia de \"herda\".")
        dados = ler_json(atual)
        if not isinstance(dados, dict):
            raise DAErro(f"{atual}: o da.json precisa ser um objeto JSON ({{…}}).")
        cadeia.append({"caminho": atual, "dados": dados, "sha256": sha256_arquivo(atual),
                       "base": base_de_recursos(atual)})
        herda = dados.get("herda")
        if herda in (None, ""):
            break
        if not isinstance(herda, str):
            raise DAErro(f"{atual}: \"herda\" precisa ser o nome de um preset, um caminho ou null.")
        atual = _resolver_herda(herda, atual.parent)
    return cadeia


def projeto_pai(da_json) -> Path | None:
    """Se `da_json` é uma ROTA — <projeto>/da/rotas/<nome>/da/da.json —, devolve a raiz do projeto que a contém;
    senão None. Rotas enxergam as referências, o bruto e o b-roll do projeto-pai (prancha, teste de movimento, validar)."""
    p = Path(da_json)
    try:
        p = p.resolve()
    except OSError:
        pass
    partes = p.parts
    if len(partes) >= 6 and p.name == "da.json" and partes[-2] == "da" and partes[-4] == "rotas" and partes[-5] == "da":
        return Path(*partes[:-5])
    return None


def bases_da_cadeia(cadeia: list[dict]) -> list[Path]:
    """Pastas onde os caminhos relativos de uma DA são procurados: a de cada elo da herança, do filho ao ancestral —
    e, quando o filho é uma rota, o da/ do projeto-pai logo depois da pasta da própria rota (é lá que estão
    referencias/, fontes/, luts/ e logos/ que a rota cita)."""
    bases = [c["base"] for c in cadeia]
    pai = projeto_pai(cadeia[0]["caminho"]) if cadeia else None
    if pai is not None and (pai / "da").is_dir() and (pai / "da") not in bases:
        bases.insert(1, pai / "da")
    return bases


def fundir_cadeia(cadeia: list[dict]) -> dict:
    """Aplica a herança (ancestral → filho). `projeto` vem só do arquivo pedido — nome,
    revisão e aprovação nunca são herdados."""
    fundida: dict = {}
    for elo in reversed(cadeia):
        fundida = fundir(fundida, elo["dados"])
    proprio = cadeia[0]["dados"].get("projeto")
    if proprio is None:
        fundida.pop("projeto", None)
    else:
        fundida["projeto"] = copy.deepcopy(proprio)
    fundida["herda"] = cadeia[0]["dados"].get("herda")
    return fundida


def resolver_arquivo(valor, bases: list[Path]) -> Path | None:
    """Caminho de recurso → Path absoluto. Relativos são procurados nas bases, do filho
    ao ancestral; devolve o primeiro que existir (ou o caminho na primeira base)."""
    if not valor or not isinstance(valor, str):
        return None
    p = Path(valor).expanduser()
    if p.is_absolute():
        return p
    for b in bases:
        cand = b / p
        if cand.exists():
            return cand.resolve()
    return (bases[0] / p) if bases else p


# ──────────────────────────────────────────────────── esquema (validador enxuto) ──
_ESQUEMA_CACHE: dict | None = None
_TIPOS_PT = {"object": "objeto {…}", "array": "lista […]", "string": "texto", "number": "número",
             "integer": "número inteiro", "boolean": "true/false", "null": "null"}


def esquema() -> dict:
    """O JSON Schema da DA (da_esquema.json, ao lado deste arquivo)."""
    global _ESQUEMA_CACHE
    if _ESQUEMA_CACHE is None:
        _ESQUEMA_CACHE = ler_json(ESQUEMA_ARQ)
    return _ESQUEMA_CACHE


def _confere_tipo(v, t: str) -> bool:
    if t == "null":
        return v is None
    if t == "boolean":
        return isinstance(v, bool)
    if t == "string":
        return isinstance(v, str)
    if t == "number":
        return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
    if t == "integer":
        return (isinstance(v, int) and not isinstance(v, bool)) or (isinstance(v, float) and v.is_integer())
    if t == "array":
        return isinstance(v, list)
    if t == "object":
        return isinstance(v, dict)
    return True


def _nome_tipo(v) -> str:
    for t in ("null", "boolean", "integer", "number", "string", "array", "object"):
        if _confere_tipo(v, t):
            return _TIPOS_PT[t]
    return type(v).__name__


def _mostrar(v, n: int = 60) -> str:
    s = json.dumps(v, ensure_ascii=False)
    return s if len(s) <= n else s[:n - 1] + "…"


def _deref(no: dict, raiz: dict) -> dict:
    visto = 0
    while isinstance(no, dict) and "$ref" in no:
        ref = no["$ref"]
        if not ref.startswith("#/"):
            raise DAErro(f"esquema: só referências locais são aceitas ($ref {ref!r})")
        alvo = raiz
        for parte in ref[2:].split("/"):
            alvo = alvo[parte]
        extra = {k: v for k, v in no.items() if k != "$ref"}
        no = {**alvo, **extra} if extra else alvo
        visto += 1
        if visto > 20:
            raise DAErro("esquema: $ref em ciclo")
    return no


def _tipo_bate(v, no: dict) -> bool:
    if "const" in no:
        return v == no["const"]
    if "enum" in no and "type" not in no:
        return v in no["enum"]
    t = no.get("type")
    if t is None:
        return True
    return any(_confere_tipo(v, x) for x in ([t] if isinstance(t, str) else t))


def _junta(caminho: str, chave) -> str:
    if isinstance(chave, int):
        return f"{caminho}[{chave}]"
    return f"{caminho}.{chave}" if caminho else str(chave)


def _validar_no(v, no: dict, caminho: str, raiz: dict, erros: list, avisos: list) -> None:
    no = _deref(no, raiz)
    onde = caminho or "(raiz)"
    if "anyOf" in no:
        melhor = None
        for alt in no["anyOf"]:
            alt = _deref(alt, raiz)
            e2, a2 = [], []
            _validar_no(v, alt, caminho, raiz, e2, a2)
            if not e2:
                avisos.extend(a2)
                melhor = None
                break
            nota = (0 if _tipo_bate(v, alt) else 1, len(e2))
            if melhor is None or nota < melhor[0]:
                melhor = (nota, e2)
        else:
            if melhor[0][0] == 1:       # nenhum formato aceito combina com o tipo do valor
                aceitos = []
                for alt in no["anyOf"]:
                    alt = _deref(alt, raiz)
                    if "enum" in alt:
                        aceitos.append("um de " + ", ".join(map(str, alt["enum"])))
                    else:
                        t = alt.get("type", "?")
                        aceitos.append(" ou ".join(_TIPOS_PT.get(x, x) for x in ([t] if isinstance(t, str) else t)))
                erros.append(f"{onde}: valor {_mostrar(v)} não é aceito aqui (esperado: {' | '.join(aceitos)})")
            else:
                erros.extend(melhor[1])
        return
    if "const" in no and v != no["const"]:
        erros.append(f"{onde}: precisa ser {_mostrar(no['const'])} (veio {_mostrar(v)})")
        return
    if "enum" in no and v not in no["enum"]:
        dica = _sugerir(v, no["enum"]) if isinstance(v, str) else ""
        erros.append(f"{onde}: valor {_mostrar(v)} não é aceito; opções: {', '.join(map(str, no['enum']))}.{dica}")
        return
    t = no.get("type")
    if t is not None:
        tipos = [t] if isinstance(t, str) else list(t)
        if not any(_confere_tipo(v, x) for x in tipos):
            esperado = " ou ".join(_TIPOS_PT.get(x, x) for x in tipos)
            erros.append(f"{onde}: esperado {esperado}, veio {_nome_tipo(v)} ({_mostrar(v)})")
            return
    if isinstance(v, str):
        if "minLength" in no and len(v) < no["minLength"]:
            erros.append(f"{onde}: texto vazio ou curto demais (mínimo de {no['minLength']} caractere(s))")
        if "pattern" in no and not re.search(no["pattern"], v):
            erros.append(f"{onde}: {_mostrar(v)} está fora do formato esperado — {no.get('x-erro') or 'padrão ' + no['pattern']}")
    elif isinstance(v, (int, float)) and not isinstance(v, bool):
        if "minimum" in no and v < no["minimum"]:
            erros.append(f"{onde}: {_num(v, 6)} está abaixo do mínimo ({_num(no['minimum'], 6)})")
        if "maximum" in no and v > no["maximum"]:
            erros.append(f"{onde}: {_num(v, 6)} está acima do máximo ({_num(no['maximum'], 6)})")
        if "exclusiveMinimum" in no and v <= no["exclusiveMinimum"]:
            erros.append(f"{onde}: {_num(v, 6)} precisa ser maior que {_num(no['exclusiveMinimum'], 6)}")
        if "exclusiveMaximum" in no and v >= no["exclusiveMaximum"]:
            erros.append(f"{onde}: {_num(v, 6)} precisa ser menor que {_num(no['exclusiveMaximum'], 6)}")
    elif isinstance(v, list):
        if "minItems" in no and len(v) < no["minItems"]:
            erros.append(f"{onde}: precisa de pelo menos {no['minItems']} item(ns) (tem {len(v)})")
        if "maxItems" in no and len(v) > no["maxItems"]:
            erros.append(f"{onde}: aceita no máximo {no['maxItems']} item(ns) (tem {len(v)})")
        if no.get("uniqueItems") and len({json.dumps(x, sort_keys=True) for x in v}) != len(v):
            erros.append(f"{onde}: há itens repetidos")
        pre, itens = no.get("prefixItems"), no.get("items")
        for i, x in enumerate(v):
            sub = pre[i] if pre and i < len(pre) else (itens if isinstance(itens, dict) else None)
            if sub is not None:
                _validar_no(x, sub, _junta(caminho, i), raiz, erros, avisos)
    elif isinstance(v, dict):
        props = no.get("properties") or {}
        for k in no.get("required") or []:
            if k not in v:
                erros.append(f"{onde}: falta a chave obrigatória \"{k}\"")
        nomes = no.get("propertyNames")
        adic = no.get("additionalProperties")
        for k, x in v.items():
            if nomes and "pattern" in nomes and not re.search(nomes["pattern"], k):
                erros.append(f"{onde}: nome de chave \"{k}\" inválido — {nomes.get('x-erro') or 'padrão ' + nomes['pattern']}")
            if k in props:
                _validar_no(x, props[k], _junta(caminho, k), raiz, erros, avisos)
            elif isinstance(adic, dict):
                if str(k).startswith(PREFIXOS_LIVRES):
                    erros.append(f"{_junta(caminho, k)}: nome de token não pode começar por \"_\" nem \"x_\" — esses prefixos "
                                 f"são de anotação livre e ficam FORA da identidade da DA; aqui toda chave é um token que as peças usam. "
                                 f"Renomeie (ex.: \"{str(k).lstrip('_x') or 'extra'}\").")
                _validar_no(x, adic, _junta(caminho, k), raiz, erros, avisos)
            elif adic is False:
                erros.append(f"{onde}: chave \"{k}\" não é aceita aqui.{_sugerir(k, props)}")
            elif adic is None and props and not k.startswith(("_", "x_", "$")) and not k.endswith(("_hex", "_abs", "_css")):
                avisos.append(f"{_junta(caminho, k)}: chave desconhecida (o kit ignora).{_sugerir(k, props)}")


def _visitar(v, no: dict, caminho: str, raiz: dict, fn, pai=None, chave=None) -> None:
    """Percorre dado e esquema juntos; chama fn(caminho, valor, nó_do_esquema, pai, chave)."""
    no = _deref(no or {}, raiz)
    if "anyOf" in no:
        alt = next((a for a in (_deref(a, raiz) for a in no["anyOf"]) if _tipo_bate(v, a)), None)
        no = {**{k: x for k, x in no.items() if k != "anyOf"}, **(alt or {})}
    fn(caminho, v, no, pai, chave)
    if isinstance(v, dict):
        props, adic = no.get("properties") or {}, no.get("additionalProperties")
        for k, x in list(v.items()):
            sub = props.get(k) or (adic if isinstance(adic, dict) else {})
            _visitar(x, sub, _junta(caminho, k), raiz, fn, v, k)
    elif isinstance(v, list):
        pre, itens = no.get("prefixItems"), no.get("items")
        for i, x in enumerate(v):
            sub = pre[i] if pre and i < len(pre) else (itens if isinstance(itens, dict) else {})
            _visitar(x, sub, _junta(caminho, i), raiz, fn, v, i)


def _aplicar_padroes(v, no: dict, raiz: dict) -> None:
    """Preenche chaves opcionais ausentes com o `default` do esquema (no próprio objeto)."""
    no = _deref(no or {}, raiz)
    if "anyOf" in no:
        no = next((a for a in (_deref(a, raiz) for a in no["anyOf"]) if _tipo_bate(v, a)), {})
    if isinstance(v, dict):
        props, adic = no.get("properties") or {}, no.get("additionalProperties")
        for k, sub in props.items():
            sub = _deref(sub, raiz)
            if k not in v and "default" in sub:
                v[k] = copy.deepcopy(sub["default"])
        for k, x in v.items():
            sub = props.get(k) or (adic if isinstance(adic, dict) else None)
            if sub is not None:
                _aplicar_padroes(x, sub, raiz)
    elif isinstance(v, list) and isinstance(no.get("items"), dict):
        for x in v:
            _aplicar_padroes(x, no["items"], raiz)


def _e_token_de_cor(caminho: str, v, no: dict, chave) -> bool:
    """Campo de cor por formato do esquema — ou, em chaves que o esquema não conhece,
    pela convenção de nome: 'cor' ou 'cor_*' fora da seção `cor`."""
    if not isinstance(v, str):
        return False
    if no.get("format") == "da-cor-token":
        return True
    return (not no and isinstance(chave, str) and (chave == "cor" or chave.startswith("cor_"))
            and not chave.endswith(("_hex", "_css")) and not caminho.startswith("cor."))


def fps_racional(valor) -> Fraction:
    """'30000/1001' | '25' | 29.97 | '29.97' | '23,976' → Fraction (decimais NTSC viram o racional exato N/1001).
    Levanta DAErro se não for uma taxa plausível."""
    try:
        if isinstance(valor, str):
            m = re.fullmatch(r"\s*(\d+)\s*(?:/\s*(\d+))?\s*", valor)
            if not m and re.fullmatch(r"\s*\d+[.,]\d+\s*", valor):
                return fps_racional(float(valor.strip().replace(",", ".")))      # "29.97" / "23,976" (texto do ffprobe ou do usuário)
            if not m:
                raise ValueError
            f = Fraction(int(m.group(1)), int(m.group(2) or 1))
        elif isinstance(valor, (int, float)) and not isinstance(valor, bool):
            f = Fraction(valor).limit_denominator(1001)
            for ntsc in (24000, 30000, 48000, 60000, 120000):      # 23,976 / 29,97 / 59,94… → racional exato
                if abs(float(valor) - ntsc / 1001) < 0.01:
                    f = Fraction(ntsc, 1001)
        else:
            raise ValueError
    except (ValueError, ZeroDivisionError):
        raise DAErro(f"fps {valor!r} inválido; use um racional como \"30000/1001\", \"24000/1001\", \"25\" ou \"60\" (ou um decimal: 29.97)")
    if not (1 <= f <= 240):
        raise DAErro(f"fps {valor!r} fora da faixa plausível (1 a 240)")
    return f


# ─────────────────────────────────────────────────────────────── identidade ──
_SHA_CACHE: dict = {}


def _sha_recurso(caminho: Path) -> str | None:
    try:
        st = caminho.stat()
    except OSError:
        return None
    chave = (str(caminho), st.st_mtime_ns, st.st_size)
    if chave not in _SHA_CACHE:
        _SHA_CACHE[chave] = sha256_arquivo(caminho)
    return _SHA_CACHE[chave]


def _canonico(v):
    if isinstance(v, dict):
        return {k: _canonico(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_canonico(x) for x in v]
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v


def _sem_anotacoes(v):
    """Cópia sem as chaves iniciadas por `_` ou `x_` (anotações livres), em qualquer profundidade."""
    if isinstance(v, dict):
        return {k: _sem_anotacoes(x) for k, x in v.items() if not str(k).startswith(PREFIXOS_LIVRES)}
    if isinstance(v, list):
        return [_sem_anotacoes(x) for x in v]
    return v


def identidade(fundida: dict, bases: list[Path]) -> str:
    """sha256 que identifica a DA — o `da_sha256` dos carimbos e o `aprovada_sha256`.

    Cobre TODO o conteúdo com a herança aplicada (cor, tipografia, layout, movimento, tratamento, legenda, graficos,
    thumbnail, som, marca, formatos, versao_esquema e qualquer seção nova) + o conteúdo dos arquivos que essas seções
    referenciam (fontes, LUT, textura, logo), EXCETO:
      · `herda`        (o que conta é o resultado da herança, não de onde veio);
      · `projeto.*`    (nome, slug, datas, revisão, aprovação, base: administrativo);
      · `conceito.*`   (frase, palavras-chave, referências, faça/não faça: texto para humanos);
      · chaves iniciadas por `_` ou `x_`, em qualquer profundidade (anotações livres e dados de outras skills).
    Padrões do esquema NÃO entram (o hash é do que está escrito): uma versão nova do kit que acrescenta um token com
    padrão não invalida a aprovação nem os carimbos de quem não usa o token."""
    d = _sem_anotacoes({k: v for k, v in fundida.items() if k not in FORA_DA_IDENTIDADE}) if isinstance(fundida, dict) else {}
    recursos: list[str] = []

    def ver(caminho, v, no, pai, chave):
        if no.get("format") == "da-arquivo" and isinstance(v, str) and v:
            arq = resolver_arquivo(v, bases)
            sha = _sha_recurso(arq) if arq is not None else None
            recursos.append(f"{v}\t{sha or 'ausente'}")

    try:
        _visitar(d, esquema(), "", esquema(), ver)
    except (KeyError, TypeError, AttributeError):
        pass
    corpo = json.dumps(_canonico(d), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return sha256_bytes((corpo + "\n" + "\n".join(sorted(set(recursos)))).encode("utf-8"))


# ──────────────────────────────────────────────────────────────── validação ──
def _checar(nome: str, fn, erros: list, avisos: list, estrutura_ok: bool) -> None:
    try:
        fn()
    except DAErro as e:
        erros.append(e.mensagem)
    except (KeyError, TypeError, AttributeError, IndexError, ValueError, ArithmeticError) as e:
        if estrutura_ok:       # estrutura certa e mesmo assim quebrou: é defeito do kit, não esconda
            erros.append(f"erro interno na checagem '{nome}': {type(e).__name__}: {e}")


def validar_dados(fundida: dict, bases: list[Path], notas: list | None = None) -> tuple[list[str], list[str]]:
    """Valida uma DA já com a herança aplicada. Devolve (erros, avisos). `notas` (opcional): lista que recebe as
    observações que não são defeito — hoje, o formato em que a DA não reserva a faixa da legenda e o GC a ocupa."""
    erros: list[str] = []
    avisos: list[str] = []
    notas = notas if notas is not None else []
    raiz = esquema()
    if not isinstance(fundida, dict):
        return ["o da.json precisa ser um objeto JSON ({…})"], []
    ve = fundida.get("versao_esquema")
    if isinstance(ve, int) and not isinstance(ve, bool) and ve > 1:
        return [f"versao_esquema {ve} é mais nova que este kit ({KIT_VERSAO}, esquema 1); atualize a skill {SKILL_DA}"], []
    _validar_no(fundida, raiz, "", raiz, erros, avisos)
    estrutura_ok = not erros
    d = fundida
    cor = d.get("cor") if isinstance(d.get("cor"), dict) else {}
    permitidas = set(cores_permitidas(cor))
    papeis = ((d.get("tipografia") or {}).get("papeis") or {}) if isinstance(d.get("tipografia"), dict) else {}
    resolvidas: dict[str, str] = {}

    def hexa(token):
        return resolver_cor(token, cor)

    # 1. campos com formato (tokens de cor, papéis, fps, arquivos, fundo da thumbnail)
    def ver(caminho, v, no, pai, chave):
        fmt = no.get("format")
        if _e_token_de_cor(caminho, v, no, chave):
            try:
                h = resolver_cor(v, cor, caminho)
            except DAErro as e:
                erros.append(e.mensagem)
                return
            resolvidas[caminho] = h
            if v.strip().startswith("#") and h not in permitidas and not caminho.startswith("cor."):
                avisos.append(f"{caminho}: {h} é uma cor literal fora da paleta, dos dados e dos neutros — "
                              f"o auditor do motor reprova; use um token ou acrescente em cor.neutros")
        elif fmt == "da-papel" and isinstance(v, str):
            if v not in papeis:
                erros.append(f"{caminho}: papel tipográfico {v!r} não existe em tipografia.papeis "
                             f"({', '.join(papeis) or 'vazio'}).{_sugerir(v, papeis)}")
        elif fmt == "da-fps" and isinstance(v, str):
            try:
                fps_racional(v)
            except DAErro as e:
                erros.append(f"{caminho}: {e.mensagem}")
        elif fmt == "da-arquivo" and isinstance(v, str) and v:
            if re.match(r"^[a-z][a-z0-9+.-]*://", v):
                return
            arq = resolver_arquivo(v, bases)
            if arq is None or not arq.is_file():
                msg = f"{caminho}: arquivo não encontrado: {v} (procurei em {', '.join(str(b) for b in bases) or '.'})"
                (avisos if no.get("x-ausente") == "aviso" else erros).append(msg)
        elif fmt == "da-fundo" and isinstance(v, str):
            if v == "foto":
                return
            if v.startswith("gradiente:"):
                nome = v.split(":", 1)[1]
                grads = cor.get("gradientes") or {}
                if nome not in grads:
                    erros.append(f"{caminho}: gradiente {nome!r} não existe em cor.gradientes "
                                 f"({', '.join(grads) or 'nenhum'}).{_sugerir(nome, grads)}")
                return
            try:
                resolver_cor(v, cor, caminho)
            except DAErro as e:
                erros.append(e.mensagem + " (também valem 'foto' e 'gradiente:<nome>')")

    _checar("campos com formato", lambda: _visitar(d, raiz, "", raiz, ver), erros, avisos, estrutura_ok)

    # 2. contraste WCAG da paleta
    def contraste_paleta():
        p = cor["paleta"]
        for a, b in (("texto", "fundo"), ("texto", "superficie")):
            c = contraste(p[a], p[b])
            if c < 3.0:
                erros.append(f"cor.paleta: contraste {a}×{b} = {_ptbr(c)}:1 (mínimo 3,0:1; ideal ≥ 4,5:1) — "
                             f"{p[a]} sobre {p[b]} é ilegível")
            elif c < 4.5:
                avisos.append(f"cor.paleta: contraste {a}×{b} = {_ptbr(c)}:1 — abaixo de 4,5:1 (WCAG AA para texto)")
        for a in ("texto_suave", "primaria", "destaque"):
            c = contraste(p[a], p["fundo"])
            if c < 3.0:
                avisos.append(f"cor.paleta: contraste {a}×fundo = {_ptbr(c)}:1 — abaixo de 3,0:1; "
                              f"evite usar {a} em texto ou traço fino sobre o fundo")

    _checar("contraste da paleta", contraste_paleta, erros, avisos, estrutura_ok)

    # 3. legenda: contraste contra o que fica atrás do texto + zona segura
    def legenda():
        leg = d["legenda"]
        c_txt = hexa(leg["cor"])
        atras, rotulo = None, None
        if isinstance(leg.get("contorno"), dict) and leg["contorno"].get("espessura", 0) > 0:
            atras, rotulo = hexa(leg["contorno"]["cor"]), "contorno"
        elif isinstance(leg.get("fundo"), dict) and leg["fundo"].get("alfa", 0) >= 0.5:
            atras, rotulo = hexa(leg["fundo"]["cor"]), "fundo"
        if atras is None:
            avisos.append("legenda: sem contorno e sem caixa de fundo — a leitura depende do vídeo que estiver atrás")
        else:
            c = contraste(c_txt, atras)
            if c < 3.0:
                erros.append(f"legenda: contraste cor×{rotulo} = {_ptbr(c)}:1 (mínimo 3,0:1) — {c_txt} sobre {atras}")
            elif c < 4.5:
                avisos.append(f"legenda: contraste cor×{rotulo} = {_ptbr(c)}:1 — abaixo de 4,5:1")
            c2 = contraste(hexa(leg["cor_destaque"]), atras)
            if c2 < 3.0:
                avisos.append(f"legenda: contraste cor_destaque×{rotulo} = {_ptbr(c2)}:1 — a palavra em destaque some")
        if leg["estilo"] in ("karaoke", "palavra") and delta_e(c_txt, hexa(leg["cor_destaque"])) < 12:
            avisos.append("legenda: cor e cor_destaque são quase iguais — o destaque da palavra falada não aparece")
        if leg["papel"] in papeis:
            fmts = d["formatos"]
            alt_linha = float(papeis[leg["papel"]].get("altura_linha", 1.2))
            for nome_fmt, plat in (("vertical", "uniao"), ("horizontal", "padrao")):
                m = fmts["margens_seguras"][nome_fmt][plat]
                L, A = fmts[nome_fmt]["largura"], fmts[nome_fmt]["altura"]
                if not (L > 0 and A > 0):
                    continue                                   # dimensão inválida: reclamada em "formatos"
                y = leg["posicao"][nome_fmt]["y"]
                meia = leg["max_linhas"] * leg["tamanho"] * min(L, A) * alt_linha / 2 / A
                if y - meia < m[0] - 1e-9 or y + meia > 1 - m[2] + 1e-9:
                    avisos.append(
                        f"legenda.posicao.{nome_fmt}.y = {_ptbr(y, 3)}: com {leg['max_linhas']} linha(s) o bloco ocupa de "
                        f"{_ptbr(y - meia, 3)} a {_ptbr(y + meia, 3)} da altura e sai da zona segura '{plat}' "
                        f"({_ptbr(m[0], 3)} a {_ptbr(1 - m[2], 3)})")
                # eixo x (D11): a largura pedida e o centro têm de caber no RETÂNGULO da zona, não no quadro
                pos = leg["posicao"][nome_fmt]
                proprio = pos.get("largura_max") is not None
                larg = float(pos["largura_max"] if proprio else leg["largura_max"])
                livre = 1 - m[1] - m[3]
                campo = f"legenda.posicao.{nome_fmt}.largura_max" if proprio else "legenda.largura_max"
                if larg > livre + 5e-4:
                    avisos.append(
                        f"{campo} = {_ptbr(larg, 3)}: no {nome_fmt} a zona segura '{plat}' só deixa {_ptbr(livre, 3)} da largura "
                        f"(de {_ptbr(m[3], 3)} a {_ptbr(1 - m[1], 3)}). O kit limita a legenda à zona — a cue quebra ou encolhe antes do "
                        f"que a DA sugere; declare legenda.posicao.{nome_fmt}.largura_max ≤ {_ptbr(math.floor(livre * 100) / 100, 2)}")
                if pos.get("x") is not None:
                    meia_l = min(larg, livre) / 2
                    if pos["x"] - meia_l < m[3] - 5e-4 or pos["x"] + meia_l > 1 - m[1] + 5e-4:
                        avisos.append(
                            f"legenda.posicao.{nome_fmt}.x = {_ptbr(pos['x'], 3)}: com largura {_ptbr(min(larg, livre), 3)} o bloco vai de "
                            f"{_ptbr(pos['x'] - meia_l, 3)} a {_ptbr(pos['x'] + meia_l, 3)} da largura e sai da zona segura '{plat}' "
                            f"({_ptbr(m[3], 3)} a {_ptbr(1 - m[1], 3)}); o kit empurra o bloco para dentro")

    _checar("legenda", legenda, erros, avisos, estrutura_ok)

    # 3b. composição (D18/D19): legenda × GC, tamanho mínimo legível e proteção do GC sobre vídeo
    def composicao():
        leg, gc, fmts = d["legenda"], d["graficos"]["gc"], d["formatos"]
        reservar_em = leg.get("reservar_em") if leg.get("reservar_em") is not None else list(RESERVA_PADRAO)
        for nome_fmt in ("vertical", "quadrado", "horizontal"):
            if nome_fmt not in fmts:
                continue
            bloco = fmts["margens_seguras"].get(nome_fmt) or fmts["margens_seguras"]["horizontal"]
            plat = "uniao" if "uniao" in bloco else "padrao" if "padrao" in bloco else next(iter(bloco))
            L, A = fmts[nome_fmt]["largura"], fmts[nome_fmt]["altura"]
            if not (isinstance(L, int) and isinstance(A, int) and L > 0 and A > 0):
                continue
            chave_pos = nome_fmt if nome_fmt in leg["posicao"] else "horizontal"      # formato sem posição própria usa a do horizontal
            if nome_fmt not in reservar_em:
                # Formato SEM reserva: as cenas não desviam da legenda. Se o GC (na zona inteira, onde a produção o põe)
                # e a faixa da legenda se tocam, os dois não podem entrar juntos. No vertical e no quadrado — formatos de
                # Shorts/Reels/TikTok, onde legenda queimada é a regra — isso é aviso; no horizontal, onde vídeo longo
                # costuma sair sem legenda queimada, é uma nota: nada colide enquanto ninguém queimar legenda ali.
                zona = _zona_px(bloco[plat], L, A)
                f, g = faixa_da_legenda(d, L, A, zona), caixa_gc_estimada(d, L, A, zona)
                if g[0] < f["x1"] and f["x0"] < g[2] and g[1] < f["y1"] and f["y0"] < g[3]:
                    onde = (f"o GC ({gc.get('posicao', 'inferior_esquerda').replace('_', ' ')}, y {_num(g[1], 0)} a {_num(g[3], 0)} px) "
                            f"e a faixa da legenda (y {_num(f['y0'], 0)} a {_num(f['y1'], 0)} px)")
                    if nome_fmt == "horizontal":
                        notas.append(
                            f"horizontal sem reserva de legenda: \"horizontal\" não está em legenda.reservar_em, então {onde} "
                            f"ocupam o mesmo lugar e as cenas não desviam. Tudo certo se o vídeo horizontal NÃO leva legenda "
                            f"queimada (é o que a prancha e o teste de movimento mostram: GC na base, legenda à parte). Se levar, "
                            f"inclua \"horizontal\" em legenda.reservar_em — GC, título, gráficos e crédito passam a desviar da faixa")
                    else:
                        avisos.append(
                            f"legenda × GC no {nome_fmt}: \"{nome_fmt}\" não está em legenda.reservar_em e {onde} se sobrepõem — "
                            f"nesse formato as cenas não desviam da legenda. Inclua \"{nome_fmt}\" em legenda.reservar_em (GC, título, "
                            f"gráficos e crédito passam a desviar sozinhos) ou afaste os dois: graficos.gc.posicao / legenda.posicao.{chave_pos}.y")
                continue
            area = area_livre_de(d, L, A, _zona_px(bloco[plat], L, A), True)
            f, h_gc = area["faixa_legenda"], _altura_gc_estimada(d, min(L, A))
            livre = 0 if area.get("sem_espaco") else area["altura"]
            if livre < h_gc:
                avisos.append(
                    f"legenda × GC no {nome_fmt}: a faixa da legenda ({f['linhas']} linha(s) a {_num(f['tamanho'], 0)} px, de y "
                    f"{_num(f['y0'], 0)} a {_num(f['y1'], 0)} px) deixa {_num(livre, 0)} px livres na zona segura '{plat}' e o GC "
                    f"precisa de ≈ {_num(h_gc, 0)} px — os dois se sobrepõem. Mude legenda.posicao.{chave_pos}.y, reduza "
                    f"legenda.max_linhas ou os tamanhos de graficos.gc")
            elif livre < 0.2 * A:
                avisos.append(
                    f"legenda no {nome_fmt}: a faixa da legenda (y {_num(f['y0'], 0)} a {_num(f['y1'], 0)} px) deixa só "
                    f"{_num(livre, 0)} px de altura ({_ptbr(livre / A * 100, 0)}% do quadro) para GC, título e gráficos dentro da "
                    f"zona segura '{plat}' — as cenas encolhem para caber. Aproxime legenda.posicao.{chave_pos}.y de uma das bordas da zona")
        escala = d["tipografia"]["escala"]
        apoio = (("graficos.gc.tamanho_cargo", gc.get("tamanho_cargo", 0.022)),
                 ("graficos.citacao_fonte.tamanho", d["graficos"]["citacao_fonte"]["tamanho"]),
                 ("tipografia.escala.nota", escala["nota"]))
        for caminho, v in apoio:
            if isinstance(v, (int, float)) and v < MINIMO_LEGIVEL - 1e-9:
                avisos.append(f"{caminho} = {_ptbr(v, 4)}: abaixo do mínimo legível ({_ptbr(MINIMO_LEGIVEL, 3)} do lado menor = "
                              f"{round(MINIMO_LEGIVEL * 1080)} px em 1080) — num celular são {_ptbr(pt_no_celular(v), 1)} pt, "
                              f"só se lê com zoom; use ≥ {_ptbr(MINIMO_LEGIVEL, 3)} (recomendado 0,026)")
        if leg["tamanho"] < MINIMO_LEGENDA - 1e-9:
            avisos.append(f"legenda.tamanho = {_ptbr(leg['tamanho'], 3)}: abaixo de {_ptbr(MINIMO_LEGENDA, 2)} do lado menor "
                          f"({round(MINIMO_LEGENDA * 1080)} px em 1080; {_ptbr(pt_no_celular(leg['tamanho']), 1)} pt num celular) — "
                          f"legenda é lida de relance; recomendado ≥ 0,052")
        estilo, prot = gc["estilo"], gc.get("protecao", "auto")
        if estilo == "linha" and prot == "nenhuma":
            avisos.append("graficos.gc: estilo 'linha' com protecao 'nenhuma' — sem caixa, sombra nem contorno, nome e cargo "
                          "somem sobre vídeo claro ou movimentado; use protecao 'degrade', 'contorno' ou 'sombra' (ou 'auto')")
        if estilo in ("barra", "caixa") and gc.get("alfa_fundo", 0.86) < 0.6 and prot in ("auto", "nenhuma"):
            avisos.append(f"graficos.gc.alfa_fundo = {_ptbr(gc.get('alfa_fundo', 0.86))}: caixa quase transparente e sem proteção — "
                          f"suba para ≥ 0,6 ou declare graficos.gc.protecao ('sombra' ou 'contorno')")
        apoio_gc = hexa(gc.get("cor_fundo", "fundo"))
        pares = [("cor_nome", gc.get("cor_nome", "texto"), apoio_gc, "cor_fundo")]
        if estilo == "etiqueta":
            pares.append(("cor_cargo", gc.get("cor_cargo", "texto_suave"), hexa("superficie"), "superficie"))
        else:
            pares.append(("cor_cargo", gc.get("cor_cargo", "texto_suave"), apoio_gc, "cor_fundo"))
        for campo, token, atras, rotulo in pares:
            c = contraste(hexa(token), atras)
            if c < 3.0:
                avisos.append(f"graficos.gc.{campo}: contraste de {_ptbr(c)}:1 sobre {rotulo} ({hexa(token)} sobre {atras}) — "
                              f"o texto do GC precisa de ≥ 3,0:1 (ideal 4,5:1) contra o próprio apoio")

    _checar("composição", composicao, erros, avisos, estrutura_ok)

    def formatos():
        for nome, f in d["formatos"].items():
            if not (isinstance(f, dict) and "largura" in f):
                continue
            for lado in ("largura", "altura"):
                v = f.get(lado)
                if not isinstance(v, int) or isinstance(v, bool) or v <= 0:
                    erros.append(f"formatos.{nome}.{lado}: precisa ser um inteiro maior que zero (veio {_mostrar(v)})")

    _checar("formatos", formatos, erros, avisos, estrutura_ok)

    # 4. cores de dados
    def dados():
        for i, x in enumerate(cor["dados"]):
            if isinstance(x, str) and not x.strip().startswith("#") and x.strip() not in cor["paleta"]:
                raise DAErro(f"cor.dados.{i}: {x!r} não é um #RRGGBB nem o nome de uma cor da paleta "
                             f"({', '.join(cor['paleta'])}).{_sugerir(x, cor['paleta'])}")
        lista = [hex_do_item(x, cor) for x in cor["dados"]]
        por_token = False
        if len(set(lista)) < len(lista):
            rep = sorted({x for x in lista if lista.count(x) > 1})
            por_token = all(any(isinstance(v, str) and not v.strip().startswith("#") for v, h in zip(cor["dados"], lista) if h == x) for x in rep)
            if por_token:        # dois tokens que hoje têm a mesma cor (ex.: secundaria igual à primaria): avisa, não bloqueia
                quem = "; ".join(f"{x} = " + " e ".join(f"dado-{i + 1} ({v})" for i, (v, h) in enumerate(zip(cor["dados"], lista)) if h == x) for x in rep)
                avisos.append(f"cor.dados: itens que resolvem para a mesma cor ({quem}) — barras vizinhas ficam iguais; troque um deles por outra cor")
            else:
                erros.append(f"cor.dados: cores repetidas ({', '.join(rep)}); a série precisa de cores distintas")
        if len(set(lista)) < 6 and not por_token:           # menos de 6 por causa de dois tokens iguais já foi avisado acima
            erros.append(f"cor.dados: precisa de pelo menos 6 cores distintas (tem {len(set(lista))})")
        fundo = hex_normal(cor["paleta"]["fundo"])
        perto = [f"{a}~{b}" for i, a in enumerate(lista) for b in lista[i + 1:] if a != b and delta_e(a, b) < 12]
        if perto:
            avisos.append(f"cor.dados: pares difíceis de distinguir ({', '.join(perto)})")
        fracas = [x for x in lista if contraste(x, fundo) < 3.0]
        if fracas:
            avisos.append(f"cor.dados: contraste abaixo de 3,0:1 contra o fundo em {', '.join(fracas)} — "
                          f"barras e linhas nessas cores ficam apagadas")

    _checar("cores de dados", dados, erros, avisos, estrutura_ok)

    # 4b. coerência depois de trocar uma cor (rotas): quase-duplicatas, série que não acompanhou, gradiente chapado
    def coerencia_de_cor():
        pal = {k: hex_normal(v) for k, v in cor["paleta"].items()}
        nomes = list(pal)
        planos = {"fundo", "superficie", "texto", "texto_suave"}
        for i, a in enumerate(nomes):
            for b in nomes[i + 1:]:
                if {a, b} <= planos:                 # fundo × superfície e texto × texto suave são vizinhos de propósito
                    continue
                if pal[a] != pal[b] and delta_e(pal[a], pal[b]) < 5:
                    avisos.append(f"cor.paleta: {a} {pal[a]} e {b} {pal[b]} são quase idênticas (ΔE {_ptbr(delta_e(pal[a], pal[b]), 1)}) — "
                                  f"parece sobra de uma troca de cor: iguale as duas ou afaste-as")
        for i, v in enumerate(cor["dados"]):
            if not (isinstance(v, str) and v.strip().startswith("#")):
                continue
            h = hex_normal(v)
            perto = min(((delta_e(h, hp), n, hp) for n, hp in pal.items() if hp != h), default=None)
            if h not in pal.values() and perto and perto[0] < 6:
                avisos.append(f"cor.dados.{i} {h} é quase a cor {perto[1]} {perto[2]} (ΔE {_ptbr(perto[0], 1)}) — escreva "
                              f"\"{perto[1]}\" no lugar do hex para a série acompanhar a paleta")
        for nome, g in (cor.get("gradientes") or {}).items():
            hs = {resolver_cor(par[0], cor) for par in g["paradas"]}
            if len(hs) == 1:
                avisos.append(f"cor.gradientes.{nome}: todas as paradas resolvem para {next(iter(hs))} — o gradiente fica chapado "
                              f"({' → '.join(str(par[0]) for par in g['paradas'])} têm hoje a mesma cor)")

    _checar("coerência de cor", coerencia_de_cor, erros, avisos, estrutura_ok)

    # 5. movimento
    def movimento():
        mov = d["movimento"]
        for nome, c in mov["curvas"].items():
            if len(c) == 4 and not (0 <= c[0] <= 1 and 0 <= c[2] <= 1):
                erros.append(f"movimento.curvas.{nome}: x1 e x2 precisam estar entre 0 e 1 (veio {_mostrar(c)}) — "
                             f"fora disso a curva deixa de ser função do tempo")
        if mov["transicoes"]["padrao"] not in mov["transicoes"]["permitidas"]:
            erros.append(f"movimento.transicoes.padrao = {mov['transicoes']['padrao']!r} não está em permitidas "
                         f"({', '.join(mov['transicoes']['permitidas'])})")
        du = mov["duracoes"]
        if not (du["micro"] < du["curta"] < du["media"] < du["longa"]):
            avisos.append("movimento.duracoes: o esperado é micro < curta < media < longa")
        if mov["curvas"]["linear"] != [0, 0, 1, 1]:
            avisos.append("movimento.curvas.linear: o esperado é [0, 0, 1, 1]")

    _checar("movimento", movimento, erros, avisos, estrutura_ok)

    # 6. tipografia e arquivos de fonte
    def tipografia():
        esc = d["tipografia"]["escala"]
        ordem = ["display", "h1", "h2", "h3", "corpo", "nota"]
        if any(esc[a] <= esc[b] for a, b in zip(ordem, ordem[1:])):
            avisos.append("tipografia.escala: o esperado é display > h1 > h2 > h3 > corpo > nota")
        vistos: dict = {}
        for nome, p in papeis.items():
            onde = f"tipografia.papeis.{nome}"
            arq_txt = p.get("arquivo")
            if not arq_txt:
                avisos.append(f"{onde}: arquivo null — fonte do sistema ({p.get('familia')}); scripts em PIL não "
                              f"conseguem carregá-la e outra máquina pode não tê-la. Aponte o arquivo da fonte.")
                continue
            arq = resolver_arquivo(arq_txt, bases)
            if arq is None or not arq.is_file():
                continue                                     # já acusado em "campos com formato"
            chave = (p.get("familia"), p.get("peso"), p.get("estilo"))
            if chave in vistos and vistos[chave][0] != arq:
                info_a = info_fonte(arq)
                if not info_a["variavel"]:
                    erros.append(f"{onde}: mesma família/peso/estilo de tipografia.papeis.{vistos[chave][1]} "
                                 f"({p.get('familia')} {p.get('peso')}), mas arquivo diferente — o navegador usaria só um deles")
            vistos.setdefault(chave, (arq, nome))
            try:
                info = info_fonte(arq)
            except DAErro as e:
                erros.append(f"{onde}.arquivo: {e.mensagem}")
                continue
            if not info.get("inspecionada"):
                avisos.append(f"{onde}.arquivo: {arq.name} é WOFF; o PIL não lê esse formato — prefira TTF/OTF")
                continue
            eixos = info["eixos"]
            for tag, val in (p.get("eixos") or {}).items():
                if tag not in eixos:
                    erros.append(f"{onde}.eixos.{tag}: a fonte {arq.name} não tem esse eixo "
                                 f"({', '.join(eixos) or 'não é fonte variável'})")
                elif not (eixos[tag][0] <= val <= eixos[tag][2]):
                    avisos.append(f"{onde}.eixos.{tag} = {_num(val)}: fora da faixa da fonte "
                                  f"({_num(eixos[tag][0])} a {_num(eixos[tag][2])}); o valor será limitado")
            if p.get("largura") is not None and "wdth" not in eixos:
                avisos.append(f"{onde}.largura = {_num(p['largura'])}: {arq.name} não tem eixo wdth, então font-stretch "
                              f"não faz efeito; para condensar uma fonte estática use escala_x")
            if "wght" in eixos and not (eixos["wght"][0] <= p.get("peso", 400) <= eixos["wght"][2]):
                avisos.append(f"{onde}.peso = {p.get('peso')}: fora da faixa do eixo wght da fonte "
                              f"({_num(eixos['wght'][0])} a {_num(eixos['wght'][2])})")

    _checar("tipografia", tipografia, erros, avisos, estrutura_ok)

    # 7. gradientes, curva de cor, LUT, formatos, som
    def diversos():
        for nome, g in (cor.get("gradientes") or {}).items():
            pos = [p[1] for p in g["paradas"]]
            if any(b < a for a, b in zip(pos, pos[1:])):
                erros.append(f"cor.gradientes.{nome}: as posições das paradas precisam estar em ordem crescente ({_mostrar(pos)})")
        curva = d["tratamento"]["grade"]["curva"]
        conjuntos = {}
        if isinstance(curva, list):
            conjuntos = {"": curva}
        elif isinstance(curva, dict):
            conjuntos = {f".{k}": v for k, v in curva.items()}
        for sufixo, pts in conjuntos.items():
            xs = [p[0] for p in pts]
            if any(b <= a for a, b in zip(xs, xs[1:])):
                erros.append(f"tratamento.grade.curva{sufixo}: os x dos pontos precisam ser estritamente crescentes ({_mostrar(xs)})")
        lut = d["tratamento"]["grade"]["lut"]
        if lut and Path(lut).suffix.lower() not in EXT_LUT:
            erros.append(f"tratamento.grade.lut: extensão {Path(lut).suffix or '(nenhuma)'} não suportada; "
                         f"use {', '.join(sorted(EXT_LUT))}")
        fm = d["formatos"]
        if fm["horizontal"]["largura"] <= fm["horizontal"]["altura"]:
            avisos.append("formatos.horizontal: largura deveria ser maior que a altura")
        if fm["vertical"]["largura"] >= fm["vertical"]["altura"]:
            avisos.append("formatos.vertical: altura deveria ser maior que a largura")
        if fm["quadrado"]["largura"] != fm["quadrado"]["altura"]:
            avisos.append("formatos.quadrado: largura e altura deveriam ser iguais")
        bpm = d["som"]["musica"]["bpm"]
        if bpm[0] > bpm[1]:
            erros.append(f"som.musica.bpm: use [mínimo, máximo] (veio {_mostrar(bpm)})")

    _checar("diversos", diversos, erros, avisos, estrutura_ok)

    # 8. aprovação
    def aprovacao():
        proj = d["projeto"]
        if proj["aprovada"]:
            atual = identidade(d, bases)
            if not proj.get("aprovada_sha256"):
                avisos.append("projeto: aprovada = true sem aprovada_sha256 — aprove pelo comando `da.py aprovar`")
            elif proj["aprovada_sha256"] != atual:
                avisos.append("DA ALTERADA DEPOIS DA APROVAÇÃO: o conteúdo não bate mais com o que foi aprovado "
                              f"na revisão {proj['revisao']}. Rode `da.py revisar` (abre a revisão {proj['revisao'] + 1}) "
                              "e depois `da.py aprovar`.")

    _checar("aprovação", aprovacao, erros, avisos, estrutura_ok)

    def unicos(lista):
        vistos, saida = set(), []
        for x in lista:
            if x not in vistos:
                vistos.add(x)
                saida.append(x)
        return saida

    return unicos(erros), unicos(avisos)


def validar(caminho=None, de=None) -> dict:
    """Valida um da.json (ou a DA do projeto). Devolve
    {'caminho', 'erros', 'avisos', 'notas', 'sha256', 'revisao', 'aprovada'}. `notas` são observações que não reprovam
    nem em --estrito (ex.: o horizontal sem reserva de legenda, onde o GC ocupa a faixa dela)."""
    alvo = Path(caminho).expanduser().resolve() if caminho and Path(caminho).expanduser().is_file() else achar(de=de, da=caminho)
    cadeia = carregar_cadeia(alvo)
    fundida = fundir_cadeia(cadeia)
    bases = bases_da_cadeia(cadeia)
    notas: list[str] = []
    erros, avisos = validar_dados(fundida, bases, notas)
    proj = fundida.get("projeto") if isinstance(fundida.get("projeto"), dict) else {}
    return {"caminho": alvo, "erros": erros, "avisos": avisos, "notas": list(dict.fromkeys(notas)), "sha256": identidade(fundida, bases),
            "revisao": proj.get("revisao"), "aprovada": bool(proj.get("aprovada"))}


# ──────────────────────────────────────────────────────────────── resolução ──
def _gradiente_css(g: dict) -> str:
    paradas = ", ".join(f"{h} {_num(p * 100, 2)}%" for h, p in g["paradas_hex"])
    if g.get("tipo") == "radial":
        return f"radial-gradient(circle, {paradas})"
    return f"linear-gradient({_num(g.get('angulo', 90), 2)}deg, {paradas})"


def resolver(fundida: dict, cadeia: list[dict], compilado_em: str | None = None) -> dict:
    """DA fundida → DA resolvida: padrões do esquema aplicados, tokens de cor resolvidos em
    campos paralelos (<chave>_hex), caminhos absolutos (<chave>_abs) e bloco _meta.
    Pressupõe uma DA válida (rode validar_dados antes)."""
    raiz_esq = esquema()
    res = copy.deepcopy(fundida)
    bases = bases_da_cadeia(cadeia)
    da_json = cadeia[0]["caminho"]
    _aplicar_padroes(res, raiz_esq, raiz_esq)
    cor = res["cor"]
    cor["paleta"] = {k: hex_normal(v) for k, v in cor["paleta"].items()}
    cor["dados_tokens"] = [v.strip() if isinstance(v, str) and v.strip() in cor["paleta"] else None for v in cor["dados"]]
    cor["dados"] = [hex_do_item(v, cor) for v in cor["dados"]]
    cor["neutros"] = [hex_normal(v) for v in cor["neutros"]]

    pendentes: list[tuple] = []

    def ver(caminho, v, no, pai, chave):
        if not isinstance(chave, str) or caminho.startswith("cor."):
            return
        fmt = no.get("format")
        if fmt == "da-cor-token" and v is None:
            pendentes.append((pai, f"{chave}_hex", None))
        elif _e_token_de_cor(caminho, v, no, chave):
            pendentes.append((pai, f"{chave}_hex", resolver_cor(v, cor, caminho)))
        elif fmt == "da-arquivo":
            if isinstance(v, str) and v and not re.match(r"^[a-z][a-z0-9+.-]*://", v):
                arq = resolver_arquivo(v, bases)
                pendentes.append((pai, f"{chave}_abs", str(arq) if arq is not None else None))
            else:
                pendentes.append((pai, f"{chave}_abs", None))
        elif fmt == "da-fundo" and isinstance(v, str):
            if v == "foto":
                extra = {"_tipo": "foto", "_hex": None, "_css": None}
            elif v.startswith("gradiente:"):
                extra = {"_tipo": "gradiente", "_hex": None, "_css": ("gradiente", v.split(":", 1)[1])}
            else:
                h = resolver_cor(v, cor, caminho)
                extra = {"_tipo": "cor", "_hex": h, "_css": h}
            for suf, val in extra.items():
                pendentes.append((pai, chave + suf, val))

    _visitar(res, raiz_esq, "", raiz_esq, ver)

    for nome, g in cor["gradientes"].items():
        g["paradas_hex"] = [[resolver_cor(t, cor, f"cor.gradientes.{nome}"), p] for t, p in g["paradas"]]
        g["css"] = _gradiente_css(g)
    for pai, chave, val in pendentes:
        if isinstance(val, tuple) and val and val[0] == "gradiente":
            val = cor["gradientes"][val[1]]["css"]
        pai[chave] = val
    cor["paleta_rgb"] = {k: list(hex_para_rgb(v)) for k, v in cor["paleta"].items()}
    cor["permitidas"] = cores_permitidas(cor)

    for nome, p in res["tipografia"]["papeis"].items():
        p["css_familia"] = '"' + p["familia"] + '"'
        p["variavel"], p["eixos_fonte"], p["eixos_efetivos"], p["eixos_ordem"] = False, {}, {}, []
        arq = p.get("arquivo_abs")
        if arq and Path(arq).is_file():
            info = info_fonte(arq)
            p["variavel"] = info["variavel"]
            p["eixos_fonte"] = {t: list(f) for t, f in info["eixos"].items()}
            p["eixos_ordem"] = list(info["eixos"])
            for tag, (mn, df, mx) in info["eixos"].items():
                if tag in (p.get("eixos") or {}):
                    val = p["eixos"][tag]
                elif tag == "wght":
                    val = p["peso"]
                elif tag == "wdth" and p.get("largura") is not None:
                    val = p["largura"]
                else:
                    val = df
                p["eixos_efetivos"][tag] = max(mn, min(mx, val))
        p["css_variacao"] = (", ".join(f'"{t}" {_num(v)}' for t, v in (p.get("eixos") or {}).items()) or "normal")

    for nome, f in res["formatos"].items():
        if isinstance(f, dict) and "largura" in f and "altura" in f:
            f["lado_menor"] = min(f["largura"], f["altura"])
            if f.get("fps"):
                fr = fps_racional(f["fps"])
                f["fps_num"], f["fps_den"], f["fps_float"] = fr.numerator, fr.denominator, round(float(fr), 6)

    th = res["thumbnail"]
    th["zona_proibida_ret"] = retangulo_do_canto(th["zona_proibida"], th.get("zona_proibida_tamanho") or reserva_do_timestamp())

    proj = res["projeto"]
    sha = identidade(fundida, bases)
    pasta_da = da_json.parent
    res["_meta"] = {
        "sha256": sha,
        "revisao": proj["revisao"],
        "aprovada": bool(proj["aprovada"]),
        "aprovada_em": proj.get("aprovada_em"),
        "alterada_apos_aprovacao": bool(proj["aprovada"]) and proj.get("aprovada_sha256") != sha,
        "nome": proj["nome"],
        "slug": proj["slug"],
        "raiz": str(raiz_do_projeto(da_json)),
        "da_json": str(da_json),
        "pasta_da": str(pasta_da),
        "build": str(pasta_da / "build"),
        "kit_versao": KIT_VERSAO,
        "compilado_em": compilado_em,
        "ancestrais": [{"caminho": str(c["caminho"]), "sha256": c["sha256"]} for c in cadeia[1:]],
    }
    return res


# ──────────────────────────────────────────────────────────── gerador: CSS ──
def _css_nome(chave: str) -> str:
    return str(chave).replace("_", "-")


def _formato_fonte_css(arq: str) -> str:
    return {".otf": "opentype", ".woff": "woff", ".woff2": "woff2"}.get(Path(arq).suffix.lower(), "truetype")


def gerar_css(res: dict) -> str:
    """da.css: @font-face de cada papel, variáveis --da-* em :root e classes .da-<papel>."""
    m, cor, tip, lay, mov = res["_meta"], res["cor"], res["tipografia"], res["layout"], res["movimento"]
    L = [f"/* da.css — gerado por `da.py compilar` (kit {KIT_VERSAO}). NÃO EDITE: mude o da.json e recompile.",
         f"   DA \"{m['nome']}\" · revisão {m['revisao']} · sha256 {m['sha256'][:16]}…",
         "   Tamanhos são frações do lado menor do quadro: --da-lado vale 100vmin por padrão; o motor pode",
         "   fixá-lo em px no elemento <html> (ex.: style=\"--da-lado:1080px\") quando o viewport não é o quadro.",
         "   Cor da DA com transparência tem UMA forma: rgba(var(--da-cor-<nome>-rgb), a) — as variáveis -rgb valem \"r, g, b\"",
         "   (com vírgulas). rgb(var(--da-cor-<nome>-rgb) / a) é INVÁLIDO: o navegador descarta e a cor computa transparente",
         "   (o lint acusa como alfa-invalido e o auditor reprova). Em cena do motor: ctx.alfa(token, a). */", ""]
    faces = set()
    for nome, p in tip["papeis"].items():
        arq = p.get("arquivo_abs")
        if not arq:
            continue
        ef = p.get("eixos_fonte") or {}
        if p.get("variavel"):
            chave = (p["familia"], arq, p["estilo"])
            peso = f"{_num(ef['wght'][0])} {_num(ef['wght'][2])}" if "wght" in ef else str(p["peso"])
        else:
            chave = (p["familia"], arq, p["estilo"], p["peso"])
            peso = str(p["peso"])
        if chave in faces:
            continue
        faces.add(chave)
        regra = (f"@font-face{{font-family:{p['css_familia']};src:url(\"{Path(arq).as_uri()}\") "
                 f"format(\"{_formato_fonte_css(arq)}\");font-weight:{peso};")
        if "wdth" in ef:
            regra += f"font-stretch:{_num(ef['wdth'][0])}% {_num(ef['wdth'][2])}%;"
        regra += f"font-style:{p['estilo']};font-display:block}}"
        L.append(regra)
    L += ["", ":root{", "  --da-lado:100vmin;", "  /* cor */"]
    for k, h in cor["paleta"].items():
        r, g, b = hex_para_rgb(h)
        L.append(f"  --da-cor-{_css_nome(k)}:{h}; --da-cor-{_css_nome(k)}-rgb:{r}, {g}, {b};")
    for rotulo, lista in (("dado", cor["dados"]), ("neutro", cor["neutros"])):
        for i, h in enumerate(lista, 1):
            r, g, b = hex_para_rgb(h)
            L.append(f"  --da-{rotulo}-{i}:{h}; --da-{rotulo}-{i}-rgb:{r}, {g}, {b};")
    for nome, g in cor["gradientes"].items():
        L.append(f"  --da-gradiente-{_css_nome(nome)}:{g['css']};")
    L.append("  /* tipografia */")
    for nome, p in tip["papeis"].items():
        n = _css_nome(nome)
        L.append(f"  --da-fonte-{n}:{p['css_familia']}; --da-peso-{n}:{p['peso']}; "
                 f"--da-largura-{n}:{_num(p['largura']) + '%' if p.get('largura') is not None else '100%'}; "
                 f"--da-estilo-{n}:{p['estilo']}; --da-tracking-{n}:{_num(p['tracking'])}em; "
                 f"--da-caixa-{n}:{'uppercase' if p['caixa'] == 'alta' else 'none'}; "
                 f"--da-altura-linha-{n}:{_num(p['altura_linha'])}; --da-eixos-{n}:{p['css_variacao']}; "
                 f"--da-escala-x-{n}:{_num(p.get('escala_x', 1))};")
    for nome, f in tip["escala"].items():
        L.append(f"  --da-escala-{_css_nome(nome)}:calc(var(--da-lado) * {_num(f, 5)});")
    L.append("  /* layout */")
    L.append(f"  --da-colunas:{lay['grade']['colunas']};")
    for nome, f in (("margem", lay["grade"]["margem"]), ("calha", lay["grade"]["calha"]),
                    ("raio", lay["raio"]), ("traco", lay["traco"])):
        L.append(f"  --da-{nome}:calc(var(--da-lado) * {_num(f, 5)});")
    s = lay.get("sombra")
    if isinstance(s, dict):
        r, g, b = hex_para_rgb(s["cor_hex"])
        L.append(f"  --da-sombra:calc(var(--da-lado) * {_num(s['dx'], 5)}) calc(var(--da-lado) * {_num(s['dy'], 5)}) "
                 f"calc(var(--da-lado) * {_num(s['desfoque'], 5)}) rgba({r}, {g}, {b}, {_num(s['alfa'], 3)});")
    else:
        L.append("  --da-sombra:none;")
    L.append("  /* movimento (referência: peças não usam transition/animation; o tempo vem de seek(t)) */")
    for nome, d in mov["duracoes"].items():
        L.append(f"  --da-dur-{_css_nome(nome)}:{_num(d)}s;")
    L.append(f"  --da-escalonamento:{_num(mov['escalonamento'])}s;")
    for nome, c in mov["curvas"].items():
        L.append(f"  --da-curva-{_css_nome(nome)}:cubic-bezier({', '.join(_num(x) for x in c)});")
    L += ["}", ""]
    for nome in tip["papeis"]:
        n = _css_nome(nome)
        L.append(f".da-{n}{{font-family:var(--da-fonte-{n});font-weight:var(--da-peso-{n});"
                 f"font-stretch:var(--da-largura-{n});font-style:var(--da-estilo-{n});"
                 f"letter-spacing:var(--da-tracking-{n});text-transform:var(--da-caixa-{n});"
                 f"line-height:var(--da-altura-linha-{n});font-variation-settings:var(--da-eixos-{n})}}")
    return "\n".join(L) + "\n"


# ───────────────────────────────────────────────────────────── gerador: JS ──
def gerar_js(res: dict) -> str:
    """da.js: window.DA = {…resolvida…, _meta:{sha256, revisao, aprovada, raiz, …}} (congelado)."""
    corpo = json.dumps(res, ensure_ascii=False, separators=(",", ":"))
    corpo = corpo.replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    m = res["_meta"]
    return (f"/* da.js — gerado por `da.py compilar` (kit {KIT_VERSAO}). NÃO EDITE: mude o da.json e recompile.\n"
            f"   DA \"{m['nome']}\" · revisão {m['revisao']} · sha256 {m['sha256'][:16]}… */\n"
            "(function(g){\"use strict\";\n"
            "function congelar(o){if(o&&typeof o===\"object\"&&!Object.isFrozen(o)){"
            "Object.getOwnPropertyNames(o).forEach(function(k){congelar(o[k]);});Object.freeze(o);}return o;}\n"
            f"g.DA=congelar({corpo});\n"
            "})(typeof window!==\"undefined\"?window:globalThis);\n")


# ────────────────────────────────────────────── gerador: grade (filtros ffmpeg) ──
GUARDA_YUV = "format=yuv420p|yuv422p|yuv444p|yuvj420p|yuvj422p|yuvj444p"
MAPEAMENTO_GRADE = [
    {"token": "tratamento.grade.exposicao", "filtro": "lutyuv",
     "regra": "ganho K = 2^(EV/2,2) em Y, U e V (equivale a multiplicar R'G'B' por K); 0 = omitido"},
    {"token": "tratamento.grade.contraste | saturacao | gama", "filtro": "eq",
     "regra": "eq=contrast=C:saturation=S:gamma=G, só com os parâmetros diferentes de 1"},
    {"token": "tratamento.grade.matiz", "filtro": "hue", "regra": "hue=h=<graus>; 0 = omitido"},
    {"token": "tratamento.grade.temperatura", "filtro": "colortemperature",
     "regra": "t > 0 → 3500 K (quente); t < 0 → 12000 K (fria); mix = |t|/100; pl=1 preserva a luminosidade"},
    {"token": "tratamento.grade.curva", "filtro": "curves",
     "regra": "nome → curves=preset=…; lista de pontos → curves=all='x/y …'; objeto → master/r/g/b"},
    {"token": "tratamento.grade.lut + intensidade_lut", "filtro": "lut3d (+ split/blend)",
     "regra": "intensidade 1 → lut3d direto; entre 0 e 1 → split, lut3d num ramo e blend normal com all_opacity = intensidade"},
    {"token": "tratamento.duotone", "filtro": "colorchannelmixer + lutrgb (+ split/blend)",
     "regra": "luma BT.709 nos três canais e rampa linear sombra→luz por canal; mistura < 1 usa split/blend"},
    {"token": "tratamento.desfoque", "filtro": "gblur", "regra": "sigma = fração × lado menor do quadro (px)"},
    {"token": "tratamento.nitidez", "filtro": "unsharp", "regra": "unsharp 5x5 só na luma, la = nitidez"},
    {"token": "tratamento.vinheta", "filtro": "vignette", "regra": "vignette=angle=<angulo em rad>"},
    {"token": "tratamento.grao", "filtro": "noise",
     "regra": "ruído uniforme só na luma: noise=c0s=<intensidade>:c0f=t+u (temporal) ou c0f=u (fixo)"},
    {"token": "tratamento.velocidade", "filtro": "setpts / atempo",
     "regra": "fora da cadeia de cor: grade.json → velocidade.video e velocidade.audio"},
]


def _esc_filtro(caminho: str) -> str:
    """Escapa um caminho para valor de opção dentro de um filtergraph (dois níveis do ffmpeg)."""
    n1 = str(caminho).replace("\\", "\\\\").replace("'", "\\'").replace(":", "\\:")
    return "".join("\\" + ch if ch in "\\'[],;" else ch for ch in n1)


class _Cadeia:
    """Monta a cadeia controlando o domínio de cor (origem → RGB → YUV) para converter só quando preciso."""

    def __init__(self, retorno: str, prefixo: str):
        self.seg: list[str] = []
        self.passos: list[dict] = []
        self.estado = "origem"            # origem (formato da fonte) | rgb (gbrp) | yuv
        self.retorno = retorno
        self.prefixo = prefixo
        self._n = 0

    def rotulos(self) -> tuple[str, str, str]:
        self._n += 1
        return tuple(f"{self.prefixo}{self._n}{s}" for s in "abc")

    def _ir(self, dominio: str) -> None:
        if dominio == "rgb" and self.estado != "rgb":
            self.seg.append("format=gbrp")
            self.estado = "rgb"
        elif dominio in ("yuv", "luma") and self.estado == "rgb":
            self.seg.append(f"format={self.retorno}")
            self.estado = "yuv"
        elif dominio == "luma" and self.estado == "origem":
            self.seg.append(GUARDA_YUV)   # garante YUV sem converter quando a fonte já é YUV
            self.estado = "yuv"
        elif dominio == "yuv":
            self.estado = "yuv"

    def add(self, expr: str, dominio: str, token: str) -> None:
        self._ir(dominio)
        self.seg.append(expr)
        self.passos.append({"token": token, "filtro": expr})

    def fechar(self) -> str:
        if self.estado == "rgb":
            self.seg.append(f"format={self.retorno}")
            self.estado = "yuv"
        return ",".join(self.seg) if self.passos else "null"


def _pontos(pts) -> str:
    return " ".join(f"{_num(x)}/{_num(y)}" for x, y in pts)


def cadeia_tratamento(res: dict, largura: int, altura: int, partes=("cor", "acabamento"),
                      retorno: str = "yuv420p", prefixo: str = "da") -> dict:
    """Cadeia de filtros ffmpeg do tratamento para um quadro largura×altura.

    Devolve {'cadeia': str, 'passos': [{'token', 'filtro'}]}. A cadeia tem uma entrada e uma
    saída sem rótulo: serve em -vf ou dentro de um -filter_complex ("[0:v]<cadeia>[v]").
    Com tudo neutro devolve "null". Trabalha em 8 bits; se passar por RGB devolve `retorno`
    (yuv420p), senão mantém o formato de pixel da fonte."""
    t = res["tratamento"]
    g = t["grade"]
    lado = min(int(largura), int(altura))
    c = _Cadeia(retorno, prefixo)
    if "cor" in partes:
        if abs(g["exposicao"]) > 1e-9:
            k = _num(2 ** (g["exposicao"] / 2.2), 4)
            meio = "(maxval+minval)/2"
            c.add(f"lutyuv=y='clip((val-minval)*{k}+minval,minval,maxval)'"
                  f":u='clip((val-{meio})*{k}+{meio},minval,maxval)'"
                  f":v='clip((val-{meio})*{k}+{meio},minval,maxval)'", "yuv", "tratamento.grade.exposicao")
        eq = [f"{nome}={_num(g[chave])}" for chave, nome in
              (("contraste", "contrast"), ("saturacao", "saturation"), ("gama", "gamma")) if abs(g[chave] - 1) > 1e-9]
        if eq:
            c.add("eq=" + ":".join(eq), "yuv", "tratamento.grade.contraste/saturacao/gama")
        if abs(g["matiz"]) > 1e-9:
            c.add(f"hue=h={_num(g['matiz'])}", "yuv", "tratamento.grade.matiz")
        if abs(g["temperatura"]) > 1e-9:
            kelvin = 3500 if g["temperatura"] > 0 else 12000
            c.add(f"colortemperature=temperature={kelvin}:mix={_num(min(1.0, abs(g['temperatura']) / 100))}:pl=1",
                  "rgb", "tratamento.grade.temperatura")
        curva = g.get("curva")
        if isinstance(curva, str):
            c.add(f"curves=preset={curva}", "rgb", "tratamento.grade.curva")
        elif isinstance(curva, list):
            c.add(f"curves=all='{_pontos(curva)}'", "rgb", "tratamento.grade.curva")
        elif isinstance(curva, dict) and curva:
            nomes = {"mestre": "master", "r": "r", "g": "g", "b": "b"}
            c.add("curves=" + ":".join(f"{nomes[k]}='{_pontos(v)}'" for k, v in curva.items() if k in nomes),
                  "rgb", "tratamento.grade.curva")
        if g.get("lut") and g["intensidade_lut"] > 1e-9:
            lut = f"lut3d=file={_esc_filtro(g.get('lut_abs') or g['lut'])}:interp=tetrahedral"
            if g["intensidade_lut"] >= 1 - 1e-9:
                c.add(lut, "rgb", "tratamento.grade.lut")
            else:
                a, b, d = c.rotulos()
                c.add(f"split[{a}][{b}];[{b}]{lut}[{d}];[{d}][{a}]blend=all_mode=normal:all_opacity={_num(g['intensidade_lut'])}",
                      "rgb", "tratamento.grade.lut + intensidade_lut")
        duo = t["duotone"]
        if duo["ativo"] and duo["mistura"] > 1e-9:
            s, l = hex_para_rgb(duo["sombra_hex"]), hex_para_rgb(duo["luz_hex"])
            pesos = "0.2126:{p}g=0.7152:{p}b=0.0722"
            mono = "colorchannelmixer=" + ":".join(f"{p}r=" + pesos.format(p=p) for p in "rgb")
            rampa = "lutrgb=" + ":".join(
                f"{canal}='clip(({_num(s[i] / 255)}+({_num((l[i] - s[i]) / 255)})*val/maxval)*maxval,minval,maxval)'"
                for i, canal in enumerate("rgb"))
            if duo["mistura"] >= 1 - 1e-9:
                c.add(f"{mono},{rampa}", "rgb", "tratamento.duotone")
            else:
                a, b, d = c.rotulos()
                c.add(f"split[{a}][{b}];[{b}]{mono},{rampa}[{d}];[{d}][{a}]blend=all_mode=normal:all_opacity={_num(duo['mistura'])}",
                      "rgb", "tratamento.duotone + mistura")
    if "acabamento" in partes:
        if t["desfoque"] > 1e-9:
            c.add(f"gblur=sigma={_num(t['desfoque'] * lado, 3)}", "qualquer", "tratamento.desfoque")
        if t["nitidez"] > 1e-9:
            c.add(f"unsharp=lx=5:ly=5:la={_num(t['nitidez'])}:cx=5:cy=5:ca=0", "yuv", "tratamento.nitidez")
        if t["vinheta"]["ativo"] and t["vinheta"]["angulo"] > 1e-9:
            c.add(f"vignette=angle={_num(t['vinheta']['angulo'])}", "yuv", "tratamento.vinheta")
        if t["grao"]["ativo"] and round(t["grao"]["intensidade"]) >= 1:
            c.add(f"noise=c0s={int(round(t['grao']['intensidade']))}:c0f={'t+u' if t['grao']['temporal'] else 'u'}",
                  "luma", "tratamento.grao")
    return {"cadeia": c.fechar(), "passos": c.passos}


def _atempo(fator: float) -> str:
    partes, f = [], float(fator)
    while f < 0.5 - 1e-9:
        partes.append(0.5)
        f /= 0.5
    while f > 100 + 1e-9:
        partes.append(100.0)
        f /= 100.0
    partes.append(f)
    return ",".join(f"atempo={_num(p, 6)}" for p in partes)


def gerar_grade(res: dict) -> dict:
    """Conteúdo de build/grade.json: cadeias prontas por formato + mapeamento token → filtro."""
    formatos = {}
    for nome, f in res["formatos"].items():
        if not (isinstance(f, dict) and "largura" in f and "altura" in f):
            continue
        retorno = "yuv420p" if f.get("fps") else "yuv444p"       # formato sem fps = imagem parada
        L, A = f["largura"], f["altura"]
        completa = cadeia_tratamento(res, L, A, ("cor", "acabamento"), retorno)
        formatos[nome] = {
            "largura": L, "altura": A, "lado_menor": min(L, A), "retorno": retorno,
            "cadeia": completa["cadeia"],
            "cadeia_cor": cadeia_tratamento(res, L, A, ("cor",), retorno)["cadeia"],
            "cadeia_acabamento": cadeia_tratamento(res, L, A, ("acabamento",), retorno)["cadeia"],
            "neutro": completa["cadeia"] == "null",
            "passos": completa["passos"],
        }
    v = res["tratamento"]["velocidade"]
    neutra = abs(v - 1) < 1e-9
    return {
        "versao": 1,
        "da_sha256": res["_meta"]["sha256"],
        "kit_versao": KIT_VERSAO,
        "uso": ("ffmpeg -i entrada.mp4 -vf \"<cadeia>\" …  ou, num filter_complex, \"[0:v]<cadeia>[v]\". "
                "'cadeia' = cor + acabamento; 'cadeia_cor' = grade/LUT/duotone (por clipe); 'cadeia_acabamento' = "
                "desfoque/nitidez/vinheta/grão (uma vez, no fim). \"null\" = nada a fazer. 8 bits; se a cadeia "
                "passa por RGB ela devolve o formato 'retorno', senão mantém o da fonte."),
        "formatos": formatos,
        "velocidade": {"fator": v, "video": None if neutra else f"setpts=PTS/{_num(v, 6)}",
                       "audio": None if neutra else _atempo(v)},
        "mapeamento": MAPEAMENTO_GRADE,
    }


# ────────────────────────────────────────────────────────── gerador: DA.md ──
def _amostra_px(fracao: float, lado: int = 1080) -> str:
    return f"{_ptbr(fracao, 4)} ({round(fracao * lado)} px em {lado})"


def _md_reserva_da_legenda(leg: dict) -> str:
    """Linha do DA.md que diz em quais formatos as peças desviam da legenda — e o que acontece nos outros."""
    reserva = [f for f in ("vertical", "quadrado", "horizontal")
               if f in (leg["reservar_em"] if leg.get("reservar_em") is not None else RESERVA_PADRAO)]
    fora = [f for f in ("horizontal", "vertical", "quadrado") if f not in reserva]
    linha = ("Faixa da legenda reservada (GC, crédito, título e gráficos desviam dela) em: "
             + (", ".join(reserva) if reserva else "nenhum formato") + ".")
    if fora:
        linha += (f" Em {', '.join(fora)} as peças **não** desviam (GC, crédito e gráficos usam a zona segura inteira e podem ocupar "
                  f"a faixa da legenda): se esse formato levar legenda queimada, inclua-o em `legenda.reservar_em` antes de produzir.")
    return linha


def gerar_md(res: dict) -> str:
    """da/DA.md: a DA em linguagem de gente — é o que o CLAUDE.md do projeto importa."""
    m, c, cor, tip, lay, mov, t, leg = (res["_meta"], res["conceito"], res["cor"], res["tipografia"],
                                         res["layout"], res["movimento"], res["tratamento"], res["legenda"])
    pal = cor["paleta"]
    if m["aprovada"] and not m["alterada_apos_aprovacao"]:
        estado = f"APROVADA em {m.get('aprovada_em') or '?'}"
    elif m["aprovada"]:
        estado = "ALTERADA DEPOIS DA APROVAÇÃO — rode `da.py revisar` e `da.py aprovar`"
    else:
        estado = "NÃO APROVADA (rascunho)"
    L = [f"# Direção de arte — {m['nome']}", "",
         f"> {c['frase']}", "",
         f"Revisão {m['revisao']} · {estado} · sha256 `{m['sha256'][:16]}…`"
         + (f" · base: {res['projeto'].get('base')}" if res["projeto"].get("base") else "")
         + (f" · herda: {res.get('herda')}" if res.get("herda") else ""),
         "", "_Gerado por `da.py compilar`. Não edite este arquivo: mude `da/da.json` e recompile._", "",
         "## Conceito", ""]
    if c["palavras_chave"]:
        L += ["Palavras-chave: " + ", ".join(c["palavras_chave"]) + ".", ""]
    if c["faca"]:
        L += ["**Faça**", ""] + [f"- {x}" for x in c["faca"]] + [""]
    if c["nao_faca"]:
        L += ["**Não faça**", ""] + [f"- {x}" for x in c["nao_faca"]] + [""]
    if c["referencias"]:
        L += ["Referências:", ""] + [f"- `{r['arquivo']}` — {r['nota']}" for r in c["referencias"]] + [""]
    L += ["## Cor", "", "| token | hex | CSS | contraste c/ fundo |", "|---|---|---|---|"]
    for k, h in pal.items():
        L.append(f"| {k} | `{h}` | `var(--da-cor-{_css_nome(k)})` | {'—' if k == 'fundo' else _ptbr(contraste(h, pal['fundo']), 1) + ':1'} |")
    L += ["", "Dados (ordem fixa, `dado-1`…): " + " ".join(f"`{h}`" for h in cor["dados"]) + ".",
          "Neutros (`neutro-1`…): " + (" ".join(f"`{h}`" for h in cor["neutros"]) or "nenhum") + "."]
    if cor["gradientes"]:
        L.append("Gradientes: " + "; ".join(f"`{n}` = {g['css']}" for n, g in cor["gradientes"].items()) + ".")
    L += ["", "## Tipografia", "", "| papel | família | peso | largura | caixa | tracking | entrelinha | arquivo |", "|---|---|---|---|---|---|---|---|"]
    for nome, p in tip["papeis"].items():
        larg = f"{_num(p['largura'])}%" if p.get("largura") is not None else "normal"
        if abs(p.get("escala_x", 1) - 1) > 1e-9:
            larg += f" · escala_x {_ptbr(p['escala_x'])}"
        L.append(f"| {nome} | {p['familia']} | {p['peso']} | {larg} | {p['caixa']} | {_ptbr(p['tracking'], 3)} em | "
                 f"{_ptbr(p['altura_linha'])} | {('`' + p['arquivo'] + '`') if p.get('arquivo') else 'sistema'} |")
    L += ["", "Escala (fração do lado menor): " + "; ".join(f"{n} {_amostra_px(f)}" for n, f in tip["escala"].items()) + ".", "",
          "## Layout", "",
          f"Grade de {lay['grade']['colunas']} colunas, margem {_amostra_px(lay['grade']['margem'])}, calha {_amostra_px(lay['grade']['calha'])}; "
          f"raio {_amostra_px(lay['raio'])}; traço {_amostra_px(lay['traco'])}; "
          f"sombra {'nenhuma' if not lay['sombra'] else 'sim'}; densidade {lay['densidade']}.", "",
          "## Movimento", "",
          "Curvas (cubic-bezier): " + "; ".join(f"{n} [{', '.join(_ptbr(x, 3) for x in cv)}]" for n, cv in mov["curvas"].items()) + ".",
          "Durações: " + "; ".join(f"{n} {_ptbr(d)} s" for n, d in mov["duracoes"].items())
          + f"; escalonamento {_ptbr(mov['escalonamento'])} s.",
          f"Entrada padrão: {mov['entrada_padrao']} · saída padrão: {mov['saida_padrao']} · "
          f"transição padrão: {mov['transicoes']['padrao']} (permitidas: {', '.join(mov['transicoes']['permitidas'])})."]
    if mov["principios"]:
        L += [""] + [f"- {x}" for x in mov["principios"]]
    g = t["grade"]
    L += ["", "## Tratamento de imagem (footage e b-roll)", "",
          f"Grade: exposição {_ptbr(g['exposicao'])} EV · contraste {_ptbr(g['contraste'])} · saturação {_ptbr(g['saturacao'])} · "
          f"gama {_ptbr(g['gama'])} · temperatura {_ptbr(g['temperatura'])} · matiz {_ptbr(g['matiz'])}° · "
          f"LUT {('`' + g['lut'] + '` a ' + _ptbr(g['intensidade_lut'] * 100, 0) + '%') if g['lut'] else 'nenhuma'} · "
          f"curva {_mostrar(g['curva'], 40) if g['curva'] else 'nenhuma'}.",
          f"Duotone: {'sim (' + t['duotone']['sombra'] + ' → ' + t['duotone']['luz'] + ', mistura ' + _ptbr(t['duotone']['mistura']) + ')' if t['duotone']['ativo'] else 'não'} · "
          f"grão: {'intensidade ' + _ptbr(t['grao']['intensidade']) + (' temporal' if t['grao']['temporal'] else ' fixo') if t['grao']['ativo'] else 'não'} · "
          f"vinheta: {'ângulo ' + _ptbr(t['vinheta']['angulo']) if t['vinheta']['ativo'] else 'não'} · "
          f"nitidez {_ptbr(t['nitidez'])} · desfoque {_ptbr(t['desfoque'], 4)} · velocidade {_ptbr(t['velocidade'])}×.",
          f"Moldura: {t['moldura']['estilo']} (cor {t['moldura']['cor']}, espessura {_amostra_px(t['moldura']['espessura'])}, "
          f"margem {_amostra_px(t['moldura']['margem'])}, rótulo {'sim' if t['moldura']['rotulo'] else 'não'}) · "
          f"recorte ancorado em: {t['recorte']['ancora']}.",
          f"Cadeia ffmpeg (horizontal): `{cadeia_tratamento(res, res['formatos']['horizontal']['largura'], res['formatos']['horizontal']['altura'])['cadeia']}`",
          "", "## Legenda", "",
          f"Estilo {leg['estilo']}, papel `{leg['papel']}`, tamanho {_amostra_px(leg['tamanho'])}, caixa {leg['caixa']}; "
          f"cor {leg['cor']} (`{leg['cor_hex']}`), destaque {leg['cor_destaque']} (`{leg['cor_destaque_hex']}`)"
          + (f", já falada {leg['cor_falada']}" if leg.get("cor_falada") else "") + "; "
          f"contorno {('`' + leg['contorno']['cor_hex'] + '` ' + _ptbr(leg['contorno']['espessura']) + ' em') if leg['contorno'] else 'não'}; "
          f"sombra {'sim' if leg['sombra'] else 'não'}; caixa de fundo {('`' + leg['fundo']['cor_hex'] + '` a ' + _ptbr(leg['fundo']['alfa'] * 100, 0) + '%') if leg['fundo'] else 'não'}.",
          "Posição (y do centro): " + "; ".join(f"{n} {_ptbr(p['y'], 3)}" for n, p in leg["posicao"].items())
          + f" · largura máx. {_ptbr(leg['largura_max'])} · até {leg['max_linhas']} linha(s) e {leg['max_palavras']} palavra(s) por cue · animação {leg['animacao']}.",
          _md_reserva_da_legenda(leg),
          "", "## Gráficos, thumbnail, som e marca", ""]
    gr, th, som, marca = res["graficos"], res["thumbnail"], res["som"], res["marca"]
    L += [f"- GC: estilo {gr['gc']['estilo']}, {gr['gc']['posicao'].replace('_', ' ')}; nome em `{gr['gc']['papel_nome']}`, cargo em `{gr['gc']['papel_cargo']}`.",
          f"- Tarja: {gr['tarja']['estilo']}, texto {gr['tarja']['cor_texto']} sobre {gr['tarja']['cor_fundo']}, papel `{gr['tarja']['papel']}`.",
          f"- Ícones: {gr['icones']['estilo']} ({_amostra_px(gr['icones']['espessura'])}). Gráficos de dados: eixo {gr['dados']['eixo']}, grade {gr['dados']['grade']}, rótulos em `{gr['dados']['rotulo']}`.",
          f"- Crédito de fonte: papel `{gr['citacao_fonte']['papel']}`, {_amostra_px(gr['citacao_fonte']['tamanho'])}, {gr['citacao_fonte']['posicao'].replace('_', ' ')}.",
          f"- Thumbnail: até {th['max_palavras']} palavras em `{th['papel']}` ({_ptbr(th['tamanho'])} do lado menor); fundo {th['fundo']}; "
          f"foto com saturação {_ptbr(th['tratamento_foto']['saturacao'])} e contraste {_ptbr(th['tratamento_foto']['contraste'])}"
          f"{', pessoa recortada' if th['tratamento_foto']['recorte_pessoa'] else ''}; zona proibida: {th['zona_proibida'].replace('_', ' ')}.",
          f"- Som: {som['identidade']} Loudness: longo {_ptbr(som['loudness']['longo']['lufs'])} LUFS / {_ptbr(som['loudness']['longo']['pico_real'])} dBTP; "
          f"curto {_ptbr(som['loudness']['curto']['lufs'])} LUFS / {_ptbr(som['loudness']['curto']['pico_real'])} dBTP. "
          f"SFX: " + ", ".join(f"{k} = {v}" for k, v in som["sfx"].items()) + f". Música: {som['musica']['clima']} ({_num(som['musica']['bpm'][0])}–{_num(som['musica']['bpm'][1])} bpm).",
          f"- Marca: logo {('`' + marca['logo'] + '`') if marca['logo'] else 'nenhum'}; assinatura {marca['assinatura'] or 'nenhuma'}; "
          f"posição {marca['posicao_logo'].replace('_', ' ')}; marca d'água {'sim' if marca['marca_dagua'] else 'não'}.",
          "", "## Formatos e margens seguras", ""]
    fm = res["formatos"]
    for nome, f in fm.items():
        if isinstance(f, dict) and "largura" in f:
            L.append(f"- {nome}: {f['largura']}×{f['altura']}" + (f" a {f['fps']} fps" if f.get("fps") else ""))
    for nome_fmt, plats in fm["margens_seguras"].items():
        L.append(f"- margens seguras {nome_fmt} [topo, direita, base, esquerda]: "
                 + "; ".join(f"{p} [{', '.join(_ptbr(x, 4) for x in mm)}]" for p, mm in plats.items()))
    L += ["", "## Como as peças usam a DA", "",
          "- HTML/CSS: `<link rel=\"stylesheet\" href=\"da/build/da.css\">` e `var(--da-cor-primaria)`, `var(--da-fonte-titulo)`, "
          "`var(--da-escala-h1)`, classes `.da-titulo`, `.da-corpo`… Cor com transparência tem uma forma só: "
          "`rgba(var(--da-cor-fundo-rgb), 0.86)`. Em cena do motor: `ctx.cor(…)`, `ctx.alfa(…, a)`; fora dele, `window.DA` (de `da/build/da.js`).",
          f"- Python: `sys.path.insert(0, os.path.expanduser(\"{KIT_FINAL}\")); import da; d = da.carregar()` → `d.cor(\"primaria\")`, `d.fonte(\"titulo\")`, `d.px(...)`, `d.grade(\"horizontal\")`.",
          f"- Proibido cor ou fonte literal em peças (HTML, CSS, JS, JSON, SVG e Python): `{DA_CLI} lint <pasta>` reprova. "
          f"Toda saída leva carimbo: `{DA_CLI} conferir-carimbo`.",
          f"- Antes de publicar: `{DA_CLI} conferencia` — a conferência final (DA aprovada, lint, carimbos, loudness e limites de "
          "plataforma) grava `qa/relatorio.json` e `qa/relatorio.md`; nada vai para `publicacao/` com esse relatório reprovado.", ""]
    return "\n".join(L)


# ─────────────────────────────────────────────────────────────── compilação ──
_GERADOR_SHA: str | None = None


def _gerador_sha() -> str:
    """Impressão do gerador (este arquivo + esquema): kit atualizado ⇒ build velho."""
    global _GERADOR_SHA
    if _GERADOR_SHA is None:
        h = hashlib.sha256()
        for arq in (Path(__file__).resolve(), ESQUEMA_ARQ):
            try:
                h.update(arq.read_bytes())
            except OSError:
                pass
        _GERADOR_SHA = h.hexdigest()
    return _GERADOR_SHA


def _pasta_build(da_json: Path) -> Path:
    return Path(da_json).parent / "build"


def precisa_compilar(da_json) -> tuple[bool, str]:
    """(True, motivo) se da/build/ não existe ou está velho em relação ao da.json, aos
    ancestrais, aos arquivos referenciados, à pasta do projeto ou à versão do kit."""
    da_json = Path(da_json).resolve()
    build = _pasta_build(da_json)
    lock_arq = build / "da.lock"
    if not lock_arq.is_file():
        return True, "ainda não foi compilada"
    try:
        lock = ler_json(lock_arq)
    except DAErro:
        return True, "da.lock ilegível"
    for nome in SAIDAS_BUILD:
        if not (build / nome).is_file():
            return True, f"falta build/{nome}"
    if not (da_json.parent / "DA.md").is_file():
        return True, "falta DA.md"
    if lock.get("kit_versao") != KIT_VERSAO or lock.get("gerador_sha256") != _gerador_sha():
        return True, "o kit foi atualizado"
    if lock.get("raiz") != str(raiz_do_projeto(da_json)):
        return True, "o projeto mudou de pasta"
    cadeia = carregar_cadeia(da_json)
    atuais = [{"caminho": str(c["caminho"]), "sha256": c["sha256"]} for c in cadeia]
    if lock.get("arquivos") != atuais:
        return True, "o da.json (ou um preset herdado) mudou"
    if lock.get("sha256") != identidade(fundir_cadeia(cadeia), bases_da_cadeia(cadeia)):
        return True, "um arquivo referenciado (fonte, LUT ou logo) mudou"
    return False, "em dia"


def compilar_da(caminho=None, de=None) -> dict:
    """Valida e compila a DA do projeto em da/build/ (+ da/DA.md).

    Devolve {'da_json', 'build', 'sha256', 'avisos', 'arquivos'}. Levanta DAInvalida se houver erro."""
    da_json = achar(de=de, da=caminho).resolve()
    if _dentro_do_kit(da_json):
        raise DAErro(f"{da_json} é um preset embutido do kit; compile a DA de um projeto.",
                     dica=f"Crie o projeto: {DA_CLI} init <pasta> --nome \"…\" --base {da_json.stem}")
    cadeia = carregar_cadeia(da_json)
    fundida = fundir_cadeia(cadeia)
    bases = bases_da_cadeia(cadeia)
    erros, avisos = validar_dados(fundida, bases)
    if erros:
        raise DAInvalida(da_json, erros, avisos)
    carimbo_tempo = agora_iso()
    res = resolver(fundida, cadeia, compilado_em=carimbo_tempo)
    build = _pasta_build(da_json)
    escritos = [
        gravar_json(build / "da.resolvida.json", res),
        gravar_texto(build / "da.css", gerar_css(res)),
        gravar_texto(build / "da.js", gerar_js(res)),
        gravar_json(build / "grade.json", gerar_grade(res)),
        gravar_texto(da_json.parent / "DA.md", gerar_md(res)),
    ]
    lock = {
        "versao": 1,
        "sha256": res["_meta"]["sha256"],
        "arquivos": [{"caminho": str(c["caminho"]), "sha256": c["sha256"]} for c in cadeia],
        "raiz": res["_meta"]["raiz"],
        "kit_versao": KIT_VERSAO,
        "gerador_sha256": _gerador_sha(),
        "compilado_em": carimbo_tempo,
        "saidas": list(SAIDAS_BUILD) + ["../DA.md"],
    }
    escritos.append(gravar_json(build / "da.lock", lock))     # por último: só existe lock de build completo
    return {"da_json": da_json, "build": build, "sha256": res["_meta"]["sha256"], "avisos": avisos,
            "arquivos": escritos}


compilar = compilar_da


# ───────────────────────────────────────────────────────────── plataformas ──
_PLATAFORMAS_CACHE: dict = {}
# campos normalizados de da.plataforma(): (grupo, [chaves candidatas, na ordem]) — o primeiro valor não nulo vale
_CAMPOS_PLATAFORMA = {
    "titulo_max": ("limites_texto", ["titulo_max_caracteres"]),
    "texto_max": ("limites_texto", ["descricao_max_caracteres", "legenda_max_caracteres", "legenda_max_caracteres_api"]),
    "hashtags_max": ("limites_texto", ["hashtags_max"]),
    "duracao_min_s": ("specs", ["duracao_min_s"]),
    "duracao_max_s": ("specs", ["duracao_max_s"]),
    "duracao_max_recomendada_s": ("specs", ["duracao_max_recomendada_s"]),
    "proporcao": ("specs", ["proporcao"]),
    "resolucao_px": ("specs", ["resolucao_recomendada_px"]),
    "loudness_lufs": ("specs", ["loudness_alvo_lufs"]),
    "pico_real_dbtp": ("specs", ["true_peak_max_dbtp"]),
}
_HERDA_TEXTO = {"shorts": "youtube"}        # o Short usa os mesmos campos de texto do vídeo comum do YouTube


def plataformas() -> dict:
    """Conteúdo de kit/plataformas.json (cópia): zonas seguras, specs, limites de texto, thumbnail e capas por
    plataforma, com `verificado_em`. Todas as seções usam os nomes canônicos youtube, shorts, reels e tiktok;
    para um valor só, prefira da.limite(plataforma, chave) ou da.plataforma(nome)."""
    try:
        mt = PLATAFORMAS_ARQ.stat().st_mtime_ns
    except OSError:
        raise DAErro(f"não encontrei {PLATAFORMAS_ARQ}: o kit foi copiado pela metade?")
    if _PLATAFORMAS_CACHE.get("mt") != mt:
        _PLATAFORMAS_CACHE.update(mt=mt, dados=ler_json(PLATAFORMAS_ARQ))
    return copy.deepcopy(_PLATAFORMAS_CACHE["dados"])


def nome_plataforma(nome: str) -> str:
    """Apelido ou nome antigo → nome canônico ('instagram', 'instagram_reels', 'ig' → 'reels'; 'youtube_longo' →
    'youtube'). Levanta DAErro (com sugestão) se não for uma plataforma conhecida."""
    dados = _PLATAFORMAS_CACHE.get("dados") or plataformas()
    n = str(nome or "").strip().lower().replace(" ", "_")
    canon = n if n in PLATAFORMAS else (dados.get("apelidos") or {}).get(n) or (dados.get("apelidos") or {}).get(n.replace("_", "-"))
    if canon not in PLATAFORMAS:
        raise DAErro(f"plataforma {nome!r} não existe ({', '.join(PLATAFORMAS)}).{_sugerir(n, [*PLATAFORMAS, *(dados.get('apelidos') or {})])}")
    return canon


def _secao_plataforma(dados: dict, grupo: str, canon: str) -> dict:
    bloco = dados.get(grupo)
    return bloco.get(canon) if isinstance(bloco, dict) and isinstance(bloco.get(canon), dict) else {}


def limite(plataforma: str, chave: str, grupo: str | None = None):
    """Um limite de plataforma por nome canônico ou apelido: da.limite("reels", "hashtags_max") → 5;
    da.limite("youtube", "titulo_max_caracteres") → 100; da.limite("tiktok", "duracao_max_s") → 3600.

    Procura em limites_texto, depois specs, capas e thumbnail (ou só em `grupo`). `chave` pode ser a do JSON ou uma das
    normalizadas de da.plataforma() ('texto_max', 'titulo_max', 'duracao_max_s', 'tamanho_max_mb'…). Short herda do
    YouTube o que a seção dele não traz em limites_texto. Devolve None quando o número não existe ("não encontrado em
    fonte confiável" — não é zero nem "sem limite")."""
    dados = plataformas()
    canon = nome_plataforma(plataforma)
    if chave == "tamanho_max_mb" and grupo in (None, "specs"):
        return _tamanho_max_mb(_secao_plataforma(dados, "specs", canon))
    if chave in _CAMPOS_PLATAFORMA and (grupo is None or grupo == _CAMPOS_PLATAFORMA[chave][0]):
        g, candidatas = _CAMPOS_PLATAFORMA[chave]
        for plat in (canon, _HERDA_TEXTO.get(canon) if g == "limites_texto" else None):
            for c in candidatas if plat else ():
                v = _secao_plataforma(dados, g, plat).get(c)
                if v is not None:
                    return v
        return None
    for g in ([grupo] if grupo else ["limites_texto", "specs", "capas", "thumbnail"]):
        v = _secao_plataforma(dados, g, canon).get(chave)
        if v is None and g == "limites_texto" and canon in _HERDA_TEXTO:
            v = _secao_plataforma(dados, g, _HERDA_TEXTO[canon]).get(chave)
        if v is not None:
            return v
    return None


def _tamanho_max_mb(specs: dict):
    """Menor teto de tamanho de arquivo publicado para a plataforma, em MB (as seções misturam GB/MB e API/app)."""
    valores = []
    for k, v in specs.items():
        if not isinstance(v, (int, float)) or isinstance(v, bool) or "anuncio" in k:
            continue
        if k.startswith("tamanho_max") and "_gb" in k:
            valores.append(v * 1024)
        elif k.startswith("tamanho_max") and "_mb" in k:
            valores.append(v)
    return min(valores) if valores else None


def plataforma(nome: str) -> dict:
    """Tudo de UMA plataforma, com nomes de campo iguais para as quatro:
    {'nome', 'texto': {…limites_texto…}, 'specs': {…}, 'margens': {'topo','direita','base','esquerda', …} | None,
     'capa': {…} | None, 'thumbnail': {…} | None, 'titulo_max', 'texto_max' (descrição ou legenda), 'hashtags_max',
     'duracao_min_s', 'duracao_max_s', 'tamanho_max_mb', 'proporcao', 'resolucao_px', 'loudness_lufs', 'pico_real_dbtp',
     'verificado_em', 'idade_dias', 'vencida' (passou de revalidar_a_cada_meses)}. Valor ausente = None."""
    dados = plataformas()
    canon = nome_plataforma(nome)
    texto = dict(_secao_plataforma(dados, "limites_texto", canon))
    if canon in _HERDA_TEXTO:
        texto = {**_secao_plataforma(dados, "limites_texto", _HERDA_TEXTO[canon]), **{k: v for k, v in texto.items() if v is not None}}
    margens = _secao_plataforma(dados, "margens_seguras_vertical", canon) or (
        _secao_plataforma(dados, "margens_seguras_horizontal", "padrao") if canon == "youtube" else {})
    saida = {"nome": canon, "texto": texto, "specs": _secao_plataforma(dados, "specs", canon), "margens": margens or None,
             "capa": _secao_plataforma(dados, "capas", canon) or None, "thumbnail": _secao_plataforma(dados, "thumbnail", canon) or None}
    for campo in _CAMPOS_PLATAFORMA:
        saida[campo] = limite(canon, campo)
    saida["tamanho_max_mb"] = limite(canon, "tamanho_max_mb")
    saida["verificado_em"] = dados.get("verificado_em")
    try:
        idade = (datetime.now().date() - datetime.fromisoformat(str(dados.get("verificado_em"))[:10]).date()).days
    except ValueError:
        idade = None
    saida["idade_dias"] = idade
    saida["vencida"] = idade is None or idade > int(float(dados.get("revalidar_a_cada_meses") or 3) * 30.5)
    return saida


def reserva_do_timestamp() -> list[float]:
    """[largura, altura] (frações do quadro) que o selo de duração do YouTube cobre no canto da thumbnail — a
    reserva recomendada de plataformas.json (thumbnail.youtube.zona_timestamp). É o padrão de thumbnail.zona_proibida_tamanho."""
    try:
        r = plataformas()["thumbnail"]["youtube"]["zona_timestamp"]["reserva_recomendada"]
        return [float(r["largura"]), float(r["altura"])]
    except (KeyError, TypeError, ValueError, DAErro):
        return [0.25, 0.22]


def retangulo_do_canto(canto: str, tamanho) -> dict | None:
    """Canto ('inferior_direita', 'superior_centro'…) + [largura, altura] em frações → {'x','y','w','h'} em frações do
    quadro (origem no canto superior esquerdo). 'nenhuma' → None."""
    if not canto or canto == "nenhuma":
        return None
    w, h = float(tamanho[0]), float(tamanho[1])
    x = 0.0 if canto.endswith("esquerda") else 1.0 - w if canto.endswith("direita") else (1.0 - w) / 2
    y = 0.0 if canto.startswith("superior") else 1.0 - h if canto.startswith("inferior") else (1.0 - h) / 2
    return {"x": round(x, 6), "y": round(y, 6), "w": round(w, 6), "h": round(h, 6)}


# ─────────────────────────────────────────────────────────────── objeto DA ──
def _bezier(x1: float, y1: float, x2: float, y2: float):
    """cubic-bezier(x1, y1, x2, y2) como função pura p(t) → progresso (0–1 na entrada)."""
    def eixo(t, a, b):
        return 3 * a * t * (1 - t) ** 2 + 3 * b * t * t * (1 - t) + t ** 3

    def f(x: float) -> float:
        if x <= 0:
            return 0.0
        if x >= 1:
            return 1.0
        lo, hi = 0.0, 1.0
        for _ in range(40):                      # bisseção: x(t) é monótona com x1, x2 em [0, 1]
            meio = (lo + hi) / 2
            if eixo(meio, x1, x2) < x:
                lo = meio
            else:
                hi = meio
        return eixo((lo + hi) / 2, y1, y2)

    return f


# ───────────────────────────── faixa da legenda, área livre e mínimos legíveis ──
RESERVA_PADRAO = ("vertical", "quadrado")     # legenda.reservar_em quando a DA não declara
FOLGA_DA_LEGENDA = 0.012                      # respiro entre a faixa da legenda e a área útil (fração do lado menor)
MINIMO_LEGIVEL = 0.022                        # menor texto de apoio sem aviso (fração do lado menor): 24 px em 1080
MINIMO_LEGENDA = 0.04                         # menor legenda sem aviso: 43 px em 1080
LARGURA_DE_CELULAR_PT = 390                   # largura de referência (pontos) para converter px do quadro em pt de tela


def orientacao_de(largura: int, altura: int) -> str:
    """'horizontal' | 'vertical' | 'quadrado' pelas dimensões do quadro."""
    return "vertical" if altura > largura else "quadrado" if altura == largura else "horizontal"


def pt_no_celular(fracao: float) -> float:
    """Fração do lado menor → altura em pontos num celular de 390 pt de largura com o lado menor do vídeo ocupando a
    largura da tela (vertical em pé, horizontal com o aparelho deitado em tela cheia). 0,022 → 8,6 pt."""
    return float(fracao) * LARGURA_DE_CELULAR_PT


def _zona_px(margens4, L: int, A: int) -> dict:
    """[topo, direita, base, esquerda] em frações → zona em px (teto com folga de 0,1 px, igual ao runtime do motor)."""
    t, d, b, e = margens4
    topo, direita, base, esquerda = (int(math.ceil(t * A - 0.1)), int(math.ceil(d * L - 0.1)),
                                     int(math.ceil(b * A - 0.1)), int(math.ceil(e * L - 0.1)))
    return {"topo": topo, "direita": direita, "base": base, "esquerda": esquerda,
            "x0": esquerda, "y0": topo, "x1": L - direita, "y1": A - base,
            "largura": L - direita - esquerda, "altura": A - topo - base}


def faixa_da_legenda(dados: dict, L: int, A: int, zona: dict) -> dict:
    """Retângulo (px do quadro L×A) que a legenda da DA pode ocupar no PIOR caso: legenda.max_linhas linhas (1 no
    estilo 'palavra') no tamanho pedido, na largura máxima, com contorno ou caixa, mais a sombra para baixo.
    É a mesma conta de ctx.faixa_legenda() no motor e a faixa que as cenas deixam livre (D18)."""
    leg = dados["legenda"]
    fmt = orientacao_de(L, A)
    papel = (dados["tipografia"]["papeis"].get(leg["papel"]) or {})
    tam = float(leg["tamanho"]) * min(L, A)
    linhas = 1 if leg["estilo"] == "palavra" else int(leg["max_linhas"])
    cont = leg.get("contorno") or None
    esp = max(1, round(float(cont["espessura"]) * tam)) if cont and cont.get("espessura", 0) > 0 else 0
    fundo = leg.get("fundo") or None
    resp = (fundo.get("respiro") or [0.35, 0.18]) if fundo else [0, 0]
    borda_y = max(esp, float(resp[1]) * tam)
    pos = leg["posicao"].get(fmt) or leg["posicao"]["horizontal"]
    larg = min(float(pos.get("largura_max") or leg["largura_max"]) * L, float(zona["largura"]))
    h = linhas * tam * float(papel.get("altura_linha") or 1.1) + 2 * borda_y
    cx = float(pos["x"]) * L if pos.get("x") is not None else (zona["x0"] + zona["x1"]) / 2
    cy = float(pos["y"]) * A
    cx = min(max(cx, zona["x0"] + larg / 2), zona["x1"] - larg / 2)
    cy = (zona["y0"] + zona["y1"]) / 2 if h > zona["altura"] else min(max(cy, zona["y0"] + h / 2), zona["y1"] - h / 2)
    som = leg.get("sombra") or None
    sombra = max(0.0, (float(som.get("dy", 0)) + float(som.get("desfoque", 0)) / 2) * tam) if som else 0.0
    return {"x0": round(cx - larg / 2, 2), "y0": round(cy - h / 2, 2), "x1": round(cx + larg / 2, 2),
            "y1": round(cy + h / 2 + sombra, 2), "linhas": linhas, "tamanho": round(tam, 2), "formato": fmt}


def area_livre_de(dados: dict, L: int, A: int, zona: dict, reservar: bool | None = None) -> dict:
    """Zona segura MENOS a faixa da legenda: a área onde GC, título, gráfico, crédito e assinatura podem ficar sem
    encostar na legenda. `reservar`: True/False, ou None = conforme legenda.reservar_em (padrão: vertical e quadrado).
    Fica com o lado maior (acima ou abaixo da faixa). Devolve a zona (mesmas chaves de d.margens) com 'y0', 'y1',
    'altura', 'topo', 'base' ajustados e mais 'reservou', 'faixa_legenda' e 'lado' ('acima' | 'abaixo' | None)."""
    leg = dados["legenda"]
    fmt = orientacao_de(L, A)
    if reservar is None:
        reservar = fmt in (leg.get("reservar_em") if leg.get("reservar_em") is not None else RESERVA_PADRAO)
    base = {**zona, "reservou": False, "faixa_legenda": None, "lado": None}
    if not reservar:
        return base
    f = faixa_da_legenda(dados, L, A, zona)
    folga = FOLGA_DA_LEGENDA * min(L, A)
    acima, abaixo = f["y0"] - folga - zona["y0"], zona["y1"] - (f["y1"] + folga)
    if max(acima, abaixo) <= 0:                     # a legenda toma a zona inteira: nada a reservar, quem chama decide
        return {**base, "faixa_legenda": f, "sem_espaco": True}
    y0, y1 = (zona["y0"], f["y0"] - folga) if acima >= abaixo else (f["y1"] + folga, zona["y1"])
    y0, y1 = int(math.ceil(y0 - 1e-6)), int(math.floor(y1 + 1e-6))
    return {**zona, "y0": y0, "y1": y1, "altura": y1 - y0, "topo": y0, "base": A - y1, "reservou": True,
            "faixa_legenda": f, "lado": "acima" if acima >= abaixo else "abaixo"}


def _altura_gc_estimada(dados: dict, u: float) -> float:
    """Altura aproximada (px) do GC com nome e cargo em uma linha cada, pelas mesmas contas de motor/cenas/gc.js."""
    gc = dados["graficos"]["gc"]
    papeis = dados["tipografia"]["papeis"]
    tn, tc = float(gc.get("tamanho_nome", 0.042)) * u, float(gc.get("tamanho_cargo", 0.022)) * u
    nome = tn * float((papeis.get(gc.get("papel_nome", "subtitulo")) or {}).get("altura_linha") or 1.2)
    cargo = tc * float((papeis.get(gc.get("papel_cargo", "dados")) or {}).get("altura_linha") or 1.2)
    if gc["estilo"] in ("barra", "caixa"):
        return 0.9 * tn + nome + 0.35 * tc + cargo
    if gc["estilo"] == "linha":
        return 0.6 * tc + nome + 0.35 * tc + cargo + 0.6 * tn
    return nome + 0.36 * tn + 0.5 * tc + cargo + 0.44 * tc


def caixa_gc_estimada(dados: dict, L: int, A: int, zona: dict) -> tuple[float, float, float, float]:
    """Retângulo (x0, y0, x1, y1) que o GC pode ocupar em `zona` com nome e cargo de uma linha cada, na largura máxima
    (7 colunas da grade no horizontal; a zona inteira nos demais), ancorado por graficos.gc.posicao — as contas de
    motor/cenas/gc.js. É o que o validador cruza com a faixa da legenda nos formatos sem reserva."""
    gc = dados["graficos"]["gc"]
    u = min(L, A)
    h = _altura_gc_estimada(dados, u)
    g = (dados.get("layout") or {}).get("grade") or {}
    colunas, margem, calha = int(g.get("colunas") or 12), float(g.get("margem", 0.065)) * u, float(g.get("calha", 0.014)) * u
    col = (L - 2 * margem - (colunas - 1) * calha) / colunas
    larg = min(float(zona["largura"]), 7 * col + 6 * calha) if L > A else float(zona["largura"])
    pos = str(gc.get("posicao") or "inferior_esquerda")
    x0 = zona["x1"] - larg if pos.endswith("direita") else zona["x0"] + (zona["largura"] - larg) / 2 if pos.endswith("centro") else zona["x0"]
    y0 = zona["y0"] if pos.startswith("superior") else zona["y1"] - h
    return (float(x0), float(y0), float(x0 + larg), float(y0 + h))


class DA(dict):
    """A direção de arte resolvida: um dict (mesmo conteúdo de build/da.resolvida.json) com atalhos."""

    # -- identidade ---------------------------------------------------------
    @property
    def meta(self) -> dict:
        return self["_meta"]

    @property
    def sha256(self) -> str:
        return self["_meta"]["sha256"]

    @property
    def revisao(self) -> int:
        return self["_meta"]["revisao"]

    @property
    def aprovada(self) -> bool:
        return bool(self["_meta"]["aprovada"]) and not self["_meta"].get("alterada_apos_aprovacao")

    @property
    def raiz(self) -> Path:
        """Pasta raiz do projeto (a que contém da/)."""
        return Path(self["_meta"]["raiz"])

    @property
    def caminho(self) -> Path:
        return Path(self["_meta"]["da_json"])

    @property
    def pasta(self) -> Path:
        return Path(self["_meta"]["pasta_da"])

    @property
    def build(self) -> Path:
        return Path(self["_meta"]["build"])

    @property
    def css(self) -> Path:
        return self.build / "da.css"

    @property
    def js(self) -> Path:
        return self.build / "da.js"

    # -- cor ----------------------------------------------------------------
    def cor(self, nome_ou_hex: str) -> str:
        """Token ('primaria', 'dado-2', 'neutro-1') ou hex → '#RRGGBB'."""
        return resolver_cor(nome_ou_hex, self["cor"])

    def rgb(self, nome_ou_hex: str) -> tuple[int, int, int]:
        return hex_para_rgb(self.cor(nome_ou_hex))

    def rgba(self, nome_ou_hex: str, alfa: float = 1.0) -> tuple[int, int, int, int]:
        """(r, g, b, a) com a em 0–255 — pronto para o PIL."""
        return (*self.rgb(nome_ou_hex), max(0, min(255, int(round(alfa * 255)))))

    def contraste(self, a: str, b: str) -> float:
        return contraste(self.cor(a), self.cor(b))

    # -- tipografia ---------------------------------------------------------
    def fonte(self, papel: str) -> dict:
        """Papel tipográfico → dict do papel + 'caminho' (arquivo absoluto, ou None se for do sistema)."""
        papeis = self["tipografia"]["papeis"]
        if papel not in papeis:
            raise DAErro(f"papel tipográfico {papel!r} não existe ({', '.join(papeis)}).{_sugerir(papel, papeis)}")
        p = dict(papeis[papel])
        p["caminho"] = p.get("arquivo_abs")
        return p

    def fonte_pil(self, papel: str, tamanho_px: float):
        """PIL.ImageFont do papel, já com os eixos de fonte variável aplicados (peso, largura)."""
        from PIL import ImageFont
        p = self.fonte(papel)
        if not p["caminho"]:
            raise DAErro(f"o papel {papel!r} usa fonte do sistema (arquivo null); aponte um arquivo no da.json para usar com PIL")
        f = ImageFont.truetype(p["caminho"], max(1, int(round(tamanho_px))))
        if p.get("variavel") and p.get("eixos_ordem"):
            try:
                f.set_variation_by_axes([p["eixos_efetivos"][t] for t in p["eixos_ordem"]])
            except (OSError, ValueError, KeyError):
                pass
        return f

    def texto(self, papel: str, s: str) -> str:
        """Aplica a caixa do papel ('alta' → maiúsculas)."""
        return s.upper() if self.fonte(papel).get("caixa") == "alta" else s

    # -- geometria ----------------------------------------------------------
    def formato(self, nome: str) -> tuple[int, int, Fraction | None]:
        """Nome do formato → (largura, altura, fps como Fraction ou None)."""
        f = self["formatos"].get(nome)
        if not (isinstance(f, dict) and "largura" in f):
            validos = [k for k, v in self["formatos"].items() if isinstance(v, dict) and "largura" in v]
            raise DAErro(f"formato {nome!r} não existe ({', '.join(validos)}).{_sugerir(nome, validos)}")
        return f["largura"], f["altura"], (fps_racional(f["fps"]) if f.get("fps") else None)

    def _dimensoes(self, largura, altura=None) -> tuple[int, int]:
        if isinstance(largura, str):
            m = re.fullmatch(r"\s*(\d+)\s*[x×]\s*(\d+)\s*", largura)
            if m:                                         # "640x360": dimensões livres, como (640, 360)
                return int(m.group(1)), int(m.group(2))
            L, A, _ = self.formato(largura)
            return L, A
        if altura is None:
            raise DAErro("informe largura e altura do quadro (ou o nome de um formato)")
        return int(largura), int(altura)

    def dimensoes(self, formato, altura=None) -> tuple[int, int]:
        """(largura, altura) em px de um formato da DA ('vertical', 'thumbnail'…), de um texto 'LxA' ('540x960') ou do
        par (largura, altura) — o que os scripts recebem em --formato. Formato inexistente é DAErro com sugestão."""
        return self._dimensoes(formato, altura)

    def px(self, fracao: float, largura, altura=None) -> int:
        """Fração do lado menor → pixels inteiros. px(0.058, 1080, 1920) ou px(0.058, 'vertical')."""
        L, A = self._dimensoes(largura, altura)
        return int(round(float(fracao) * min(L, A)))

    def margens(self, formato: str = "horizontal", plataforma: str | None = None,
                largura: int | None = None, altura: int | None = None) -> dict:
        """Zona segura em pixels: {'topo','direita','base','esquerda','x0','y0','x1','y1','largura','altura','plataforma'}.

        plataforma: chave de formatos.margens_seguras do formato (vertical: instagram, tiktok, shorts, uniao;
        horizontal: padrao) ou nome canônico/apelido de plataforma ('reels' = instagram; 'youtube' = padrao).
        Padrão: 'padrao' no horizontal, 'uniao' (pior caso) no vertical. Zona que só existe em OUTRO formato (ex.:
        'uniao' ou 'tiktok' pedida para o horizontal) cai no padrão deste formato — o mesmo roteiro serve aos dois —
        e o resultado diz qual foi usada em 'plataforma'; nome que não existe em formato nenhum é DAErro.
        Formato sem entrada própria em formatos.margens_seguras usa horizontal.padrao."""
        L, A = (largura, altura) if largura and altura else self.formato(formato)[:2]
        tabela = self["formatos"]["margens_seguras"]
        bloco = tabela.get(formato) or tabela["horizontal"]
        padrao = "uniao" if "uniao" in bloco else "padrao" if "padrao" in bloco else next(iter(bloco))
        if plataforma is None:
            plataforma = padrao
        elif plataforma not in bloco:
            chave = str(plataforma).strip().lower()
            try:
                chave = ZONA_DA_PLATAFORMA.get(nome_plataforma(chave), chave)
            except DAErro:
                pass
            em_outro = any(isinstance(b, dict) and (plataforma in b or chave in b) for b in tabela.values())
            if chave in bloco:
                plataforma = chave
            elif em_outro or chave in ZONA_DA_PLATAFORMA.values():
                plataforma = padrao
            else:
                todas = sorted({k for b in tabela.values() if isinstance(b, dict) for k in b} | set(PLATAFORMAS))
                raise DAErro(f"margens seguras: {plataforma!r} não existe para o formato {formato!r} "
                             f"({', '.join(bloco)}) nem em outro formato.{_sugerir(str(plataforma), todas)}")
        # teto com folga de 0,1 px: a fração tem 4 casas (0,2778 × 1080 = 300,02 é 300, não 301); o runtime do motor faz igual
        return {**_zona_px(bloco[plataforma], L, A), "plataforma": plataforma}

    def _quadro_e_zona(self, formato, plataforma, largura, altura) -> tuple[int, int, dict]:
        if largura and altura:
            L, A = int(largura), int(altura)
        else:
            L, A = self._dimensoes(formato)
        nome = formato if isinstance(formato, str) and formato in self["formatos"]["margens_seguras"] else orientacao_de(L, A)
        return L, A, self.margens(nome, plataforma, largura=L, altura=A)

    def faixa_legenda(self, formato="vertical", plataforma: str | None = None,
                      largura: int | None = None, altura: int | None = None) -> dict:
        """Faixa (px) que a legenda desta DA pode ocupar no pior caso — max_linhas linhas, largura máxima, contorno/caixa
        e sombra — dentro da zona segura da plataforma: {'x0','y0','x1','y1','linhas','tamanho','formato'}.
        faixa_legenda('vertical'), faixa_legenda('540x960'), faixa_legenda(largura=540, altura=960). No motor: ctx.faixa_legenda()."""
        L, A, zona = self._quadro_e_zona(formato, plataforma, largura, altura)
        return faixa_da_legenda(self, L, A, zona)

    def area_livre(self, formato="vertical", plataforma: str | None = None, largura: int | None = None,
                   altura: int | None = None, legenda: bool | None = None) -> dict:
        """Zona segura menos a faixa da legenda: onde GC, título, gráfico, crédito e assinatura ficam sem encostar na
        legenda. `legenda`: True = reserva sempre, False = nunca, None = conforme legenda.reservar_em (padrão: vertical e
        quadrado; 'thumbnail' nunca reserva). Mesmas chaves de margens() + 'reservou', 'faixa_legenda', 'lado'.
        No motor: ctx.area_livre(plataforma, {legenda}) — é o que as cenas embutidas usam."""
        L, A, zona = self._quadro_e_zona(formato, plataforma, largura, altura)
        if legenda is None and formato == "thumbnail":
            legenda = False
        return area_livre_de(self, L, A, zona, legenda)

    def legenda_reservada(self, formato="vertical") -> bool:
        """As peças deste formato deixam livre a faixa da legenda (legenda.reservar_em)? Onde é False — por padrão, o
        horizontal —, GC, crédito e gráficos ficam na zona inteira e OCUPAM a faixa: quem for queimar legenda ali
        precisa avisar (ou a DA ganha o formato em legenda.reservar_em). Aceita nome de formato ou 'LxA'."""
        return bool(self.area_livre(formato)["reservou"])

    def zona_proibida(self, largura=None, altura: int | None = None) -> dict | None:
        """thumbnail.zona_proibida como retângulo. Sem argumentos: frações do quadro {'x','y','w','h'}; com um formato
        ('thumbnail') ou largura e altura: px {'x0','y0','x1','y1','largura','altura','canto'}. None = 'nenhuma'.
        O tamanho é thumbnail.zona_proibida_tamanho (padrão 0,25 × 0,22: o selo de duração do YouTube). No motor: ctx.zona_proibida()."""
        r = self["thumbnail"].get("zona_proibida_ret")
        if not r:
            return None
        if largura is None:
            return dict(r)
        L, A = self._dimensoes(largura, altura)
        x0, y0 = int(round(r["x"] * L)), int(round(r["y"] * A))
        w, h = int(round(r["w"] * L)), int(round(r["h"] * A))
        return {"x0": x0, "y0": y0, "x1": x0 + w, "y1": y0 + h, "largura": w, "altura": h, "canto": self["thumbnail"]["zona_proibida"]}

    def transicao(self, tipo: str | None = None) -> dict:
        """Transição da DA pronta para executar: {'tipo', 'duracao' (s; 0 no corte), 'permitidas'}. Sem `tipo`, a
        movimento.transicoes.padrao; tipo fora de movimento.transicoes.permitidas é DAErro (a DA decide quais existem)."""
        tr = self["movimento"]["transicoes"]
        t = tipo or tr["padrao"]
        if t not in TRANSICOES:
            raise DAErro(f"transição {t!r} não existe ({', '.join(TRANSICOES)}).{_sugerir(t, TRANSICOES)}")
        if t not in tr["permitidas"]:
            raise DAErro(f"transição {t!r} não está em movimento.transicoes.permitidas desta DA ({', '.join(tr['permitidas'])}).",
                         dica="Use uma das permitidas ou abra uma revisão da DA para acrescentá-la.")
        return {"tipo": t, "duracao": 0.0 if t == "corte" else self.dur("media"), "permitidas": list(tr["permitidas"])}

    # -- movimento ----------------------------------------------------------
    def curva(self, nome: str) -> tuple[float, float, float, float]:
        curvas = self["movimento"]["curvas"]
        if nome not in curvas:
            raise DAErro(f"curva {nome!r} não existe ({', '.join(curvas)}).{_sugerir(nome, curvas)}")
        return tuple(curvas[nome])

    def facilitar(self, nome: str):
        """Curva da DA como função pura: f(0..1) → progresso. Para animar em Python (legendas, PIL)."""
        return _bezier(*self.curva(nome))

    def dur(self, nome: str) -> float:
        d = self["movimento"]["duracoes"]
        if nome not in d:
            raise DAErro(f"duração {nome!r} não existe ({', '.join(d)}).{_sugerir(nome, d)}")
        return float(d[nome])

    # -- tratamento ---------------------------------------------------------
    def grade(self, largura="horizontal", altura: int | None = None, parte: str = "completa") -> str:
        """Cadeia de filtros ffmpeg do tratamento. grade('vertical'), grade(1280, 720), grade('640x360'),
        parte = 'completa' | 'cor' | 'acabamento'. "null" quando não há nada a fazer."""
        partes = {"completa": ("cor", "acabamento"), "cadeia": ("cor", "acabamento"),
                  "cor": ("cor",), "acabamento": ("acabamento",)}
        if parte not in partes:
            raise DAErro(f"parte {parte!r} inválida; use completa, cor ou acabamento")
        retorno = "yuv420p"
        if isinstance(largura, str) and not re.fullmatch(r"\s*\d+\s*[x×]\s*\d+\s*", largura):
            retorno = "yuv420p" if self["formatos"].get(largura, {}).get("fps") else "yuv444p"
        L, A = self._dimensoes(largura, altura)
        return cadeia_tratamento(self, L, A, partes[parte], retorno)["cadeia"]

    # -- acesso genérico ----------------------------------------------------
    def token(self, caminho: str, resolver_cores: bool = True):
        """Valor de um token por caminho pontilhado ('legenda.cor', 'cor.dados.0', 'movimento.curvas.entrada').
        Campos de cor devolvem o hex resolvido (a não ser com resolver_cores=False)."""
        partes = [p for p in re.split(r"[.\[\]]+", caminho.strip()) if p != ""]
        atual, andado = self, []
        for i, parte in enumerate(partes):
            if isinstance(atual, dict):
                if parte not in atual:
                    chaves = [k for k in atual if not str(k).startswith("_")]
                    raise DAErro(f"token {caminho!r}: não existe {parte!r} em {'.'.join(andado) or 'da.json'} "
                                 f"(chaves: {', '.join(map(str, chaves))}).{_sugerir(parte, chaves)}")
                if resolver_cores and i == len(partes) - 1 and f"{parte}_hex" in atual and atual[f"{parte}_hex"]:
                    return atual[f"{parte}_hex"]
                atual = atual[parte]
            elif isinstance(atual, list):
                if not parte.lstrip("-").isdigit() or not (-len(atual) <= int(parte) < len(atual)):
                    raise DAErro(f"token {caminho!r}: {'.'.join(andado)} é uma lista de {len(atual)} item(ns); "
                                 f"use um índice de 0 a {len(atual) - 1}")
                atual = atual[int(parte)]
            else:
                raise DAErro(f"token {caminho!r}: {'.'.join(andado)} é um valor simples, não tem {parte!r}")
            andado.append(parte)
        return atual

    def carimbar(self, saida, ferramenta: str, formato=None, parametros=None, auditoria: str = "n/a", insumos=None) -> Path:
        """Grava <saida>.da.json com a identidade desta DA. `insumos` = peças que entraram na composição (D14)."""
        return carimbar(saida, ferramenta, formato, parametros, auditoria, da=self, insumos=insumos)


def carregar(caminho=None, de=None, compilar: bool = True) -> DA:
    """Acha a DA, recompila da/build/ se estiver velho e devolve o objeto DA.

    caminho:  da.json ou pasta do projeto (equivale a --da); None = descobrir.
    de:       pasta de onde começar a subir (equivale a --de); None = diretório atual.
    compilar: False = resolve só em memória, sem tocar em da/build/.
    Levanta SemDA (código 2) se não houver DA e DAInvalida se ela tiver erros."""
    da_json = achar(de=de, da=caminho).resolve()
    if compilar and not _dentro_do_kit(da_json):
        velho, _motivo = precisa_compilar(da_json)
        if velho:
            compilar_da(da_json)
        return DA(ler_json(_pasta_build(da_json) / "da.resolvida.json"))
    cadeia = carregar_cadeia(da_json)
    fundida = fundir_cadeia(cadeia)
    erros, avisos = validar_dados(fundida, bases_da_cadeia(cadeia))
    if erros:
        raise DAInvalida(da_json, erros, avisos)
    return DA(resolver(fundida, cadeia))


# ───────────────────────────────────────────────────────────────── carimbo ──
AUDITORIAS = ("ok", "pulada", "n/a")
LIMITE_SHA_COMPLETO = 256 * 1024 * 1024
ESTADOS_CARIMBO = {
    "ok": "ok",
    "sem_carimbo": "SEM CARIMBO",
    "carimbo_invalido": "CARIMBO ILEGÍVEL",
    "sha_diferente": "DA DIFERENTE",
    "auditoria_pulada": "AUDITORIA PULADA",
    "arquivo_alterado": "ARQUIVO ALTERADO",
    "da_alterada": "DA ALTERADA APÓS APROVAÇÃO",
    "da_nao_aprovada": "DA NÃO APROVADA",
    "insumo_de_outra_da": "INSUMO DE OUTRA DA",
}
_PIOR_AUDITORIA = {"ok": 0, "n/a": 1, "pulada": 2}


def caminho_do_carimbo(saida) -> Path:
    s = str(saida).rstrip("/")
    return Path(s + ".da.json")


def _impressao_saida(saida: Path) -> dict:
    """Impressão digital da saída: liga o carimbo ao arquivo (regravar a peça sem recarimbar é pego)."""
    if saida.is_dir():
        arquivos = sorted(p for p in saida.rglob("*") if p.is_file())
        return {"tipo": "pasta", "arquivos": len(arquivos), "bytes": sum(p.stat().st_size for p in arquivos)}
    tam = saida.stat().st_size
    if tam <= LIMITE_SHA_COMPLETO:
        return {"tipo": "arquivo", "bytes": tam, "sha256": sha256_arquivo(saida), "modo": "completo"}
    h = hashlib.sha256()
    with open(saida, "rb") as f:                 # arquivos enormes: começo + fim + tamanho
        h.update(f.read(8 << 20))
        f.seek(max(0, tam - (8 << 20)))
        h.update(f.read(8 << 20))
    h.update(str(tam).encode())
    return {"tipo": "arquivo", "bytes": tam, "sha256": h.hexdigest(), "modo": "parcial"}


def _da_para(saida: Path, da=None) -> DA:
    if isinstance(da, DA):
        return da
    if da:
        return carregar(da)
    if os.environ.get("DA_JSON", "").strip():
        return carregar()
    try:
        return carregar(de=saida)                # a peça pertence ao projeto que a contém…
    except SemDA:
        return carregar()                        # …ou ao projeto do diretório atual


def ler_carimbo(peca) -> dict | None:
    """Carimbo (<peca>.da.json) de uma peça, ou None se não houver ou estiver ilegível."""
    sidecar = caminho_do_carimbo(peca)
    if not sidecar.is_file():
        return None
    try:
        c = ler_json(sidecar)
    except DAErro:
        return None
    return c if isinstance(c, dict) else None


def proveniencia(insumos, da_sha256: str | None = None) -> list[dict]:
    """Proveniência de uma composição (D14): para cada insumo, {'arquivo', 'caminho', 'carimbado', 'da_sha256',
    'auditoria', 'ferramenta'} lidos do carimbo dele (None quando o insumo não tem carimbo — footage bruto, por
    exemplo). Os insumos DOS insumos sobem junto (com 'via'), para uma cadeia de composições não esconder nada."""
    saida, vistos = [], set()

    def acrescentar(item: dict) -> None:
        chave = (item.get("arquivo"), item.get("da_sha256"), item.get("auditoria"), item.get("via"))
        if chave not in vistos:
            vistos.add(chave)
            saida.append(item)

    for ins in insumos or []:
        if isinstance(ins, dict):                                 # já veio pronto (de outro carimbo)
            acrescentar({k: ins.get(k) for k in ("arquivo", "caminho", "carimbado", "da_sha256", "auditoria", "ferramenta", "via") if k in ins})
            continue
        arq = Path(str(ins)).expanduser()
        c = ler_carimbo(arq)
        acrescentar({"arquivo": arq.name, "caminho": str(arq.resolve()), "carimbado": c is not None,
                     "da_sha256": c.get("da_sha256") if c else None, "auditoria": c.get("auditoria") if c else None,
                     "ferramenta": c.get("ferramenta") if c else None})
        for sub in (c.get("insumos") or []) if c else []:
            if isinstance(sub, dict) and sub.get("carimbado"):
                acrescentar({"arquivo": sub.get("arquivo"), "caminho": sub.get("caminho"), "carimbado": True, "da_sha256": sub.get("da_sha256"),
                             "auditoria": sub.get("auditoria"), "ferramenta": sub.get("ferramenta"), "via": sub.get("via") or arq.name})
    return saida


def _midia_do_arquivo(arquivo: Path, extensao: str) -> dict | None:
    """Largura, altura, fps e duração da peça, lidos do próprio arquivo (quem confere não precisa interpretar `formato`)."""
    try:
        if extensao in EXT_IMAGEM:
            from PIL import Image
            with Image.open(arquivo) as im:
                return {"tipo": "imagem", "largura": im.width, "altura": im.height}
        if extensao in EXT_VIDEO:
            r = subprocess.run([_bin("ffprobe"), "-v", "error", "-select_streams", "v:0", "-show_entries",
                                "stream=width,height,r_frame_rate,nb_frames,duration:format=duration", "-of", "json", str(arquivo)],
                               capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=30)
            if r.returncode != 0:
                return None
            dados = json.loads(r.stdout or "{}")
            v = (dados.get("streams") or [{}])[0]

            def num(x):
                try:
                    return round(float(x), 4)
                except (TypeError, ValueError):
                    return None

            midia = {"tipo": "video", "largura": int(v.get("width") or 0), "altura": int(v.get("height") or 0), "fps": v.get("r_frame_rate"),
                     "duracao": num(v.get("duration")) or num((dados.get("format") or {}).get("duration"))}
            if str(v.get("nb_frames") or "").isdigit():
                midia["quadros"] = int(v["nb_frames"])
            return midia if midia["largura"] else None
    except Exception:                                             # sondagem é um extra: nunca derruba o carimbo
        return None
    return None


def carimbar(saida, ferramenta: str, formato=None, parametros=None, auditoria: str = "n/a", da=None,
             sha_esperado: str | None = None, origem=None, reauditada: bool = False, insumos=None) -> Path:
    """Grava <saida>.da.json ao lado da peça. `auditoria`: 'ok' (passou pelo auditor C3 do motor) | 'pulada'
    (renderizada com --sem-auditoria) | 'n/a' (peça que não passa pelo motor: PIL, ffmpeg).

    Nunca promove: se a peça já tem carimbo 'pulada' e o arquivo é O MESMO (mesma impressão digital), pedir 'ok' ou
    'n/a' levanta DAErro e o carimbo 'pulada' fica como está — só um render novo, com o auditor ligado, limpa o estado.
    `reauditada=True` é de uso do motor: declara que ESTA chamada vem de um render que acabou de passar pelo auditor
    (um PNG re-renderizado pode sair idêntico byte a byte ao que tinha sido gerado com --sem-auditoria).

    Conteúdo: {da_sha256, da_revisao, da_aprovada, da_alterada_apos_aprovacao, kit_versao, ferramenta, formato,
    parametros, auditoria, gerado_em} + 'arquivo' e 'saida' (impressão digital do arquivo carimbado).

    sha_esperado: identidade (d.sha256) da DA com que a peça FOI DESENHADA, lida no início do trabalho. Se a DA
                  atual for outra (o da.json mudou no meio), levanta DAErro e não grava nada — uma peça com o
                  visual antigo nunca sai carimbada como se fosse da DA nova.
    origem:       arquivo ainda com nome provisório (ex.: <saida>.parcial) que vai ser renomeado para `saida`
                  logo depois: a impressão digital é tirada dele e o carimbo já nasce com o nome final.
    insumos:      peças (caminhos) que entraram nesta composição — overlay, base tratada, clipes juntados. O carimbo
                  guarda `insumos: [{arquivo, caminho, carimbado, da_sha256, auditoria, ferramenta}]` lidos dos carimbos
                  deles, e a `auditoria` gravada é a PIOR entre a pedida e as dos insumos (um overlay renderizado com
                  --sem-auditoria deixa a composição "pulada"); conferir-carimbo reprova a saída com insumo de outra DA.

    O carimbo traz também `midia` = {tipo, largura, altura, fps, duracao, quadros} lidos do próprio arquivo."""
    saida = Path(str(saida)).expanduser()
    fonte = Path(str(origem)).expanduser() if origem else saida
    if not fonte.exists():
        raise DAErro(f"não dá para carimbar {fonte}: o arquivo não existe (carimbe depois de gerar a peça)")
    if auditoria not in AUDITORIAS:
        raise DAErro(f"auditoria {auditoria!r} inválida; use {', '.join(AUDITORIAS)}")
    if not ferramenta or not str(ferramenta).strip():
        raise DAErro("informe a ferramenta que gerou a peça (ex.: 'motor', 'legendas', 'da.py grade')")
    if parametros is not None:
        try:
            json.dumps(parametros)
        except (TypeError, ValueError):
            raise DAErro("parametros precisa ser serializável em JSON (dict, list, texto, número)")
    d = _da_para(saida.resolve(), da)
    if sha_esperado and str(sha_esperado) != d.sha256:
        raise DAErro(f"a DA mudou enquanto a peça era gerada (começou com {str(sha_esperado)[:12]}…, agora é {d.sha256[:12]}…): "
                     f"{saida.name} não foi carimbada.",
                     dica="Gere a peça de novo: ela precisa ser desenhada e carimbada com a mesma DA.")
    impressao = _impressao_saida(fonte)
    if auditoria != "pulada" and not reauditada:
        try:
            anterior = ler_json(caminho_do_carimbo(saida)) if caminho_do_carimbo(saida).is_file() else None
        except DAErro:
            anterior = None
        if isinstance(anterior, dict) and anterior.get("auditoria") == "pulada":
            antes = anterior.get("saida")
            mesma = not isinstance(antes, dict) or all(antes.get(k) == impressao.get(k)
                                                       for k in ("tipo", "bytes", "sha256", "arquivos") if k in antes)
            if mesma:
                raise DAErro(f"{saida.name} foi renderizada com --sem-auditoria e o arquivo é o mesmo: o carimbo continua "
                             f"\"pulada\" (carimbar não promove peça que pulou o auditor para {auditoria!r}).",
                             dica="Renderize a peça de novo com o auditor ligado (sem --sem-auditoria); é o motor que grava \"ok\".")
    lista_insumos = proveniencia(insumos) if insumos else []
    for ins in lista_insumos:                                     # a auditoria da composição é a pior dos insumos
        if ins.get("auditoria") in _PIOR_AUDITORIA and _PIOR_AUDITORIA[ins["auditoria"]] > _PIOR_AUDITORIA[auditoria] and ins["auditoria"] == "pulada":
            auditoria = "pulada"
    carimbo = {
        "carimbo_versao": 1,
        "arquivo": saida.name,
        "da_sha256": d.sha256,
        "da_revisao": d.revisao,
        "da_aprovada": d.aprovada,
        "da_alterada_apos_aprovacao": bool(d.meta.get("alterada_apos_aprovacao")),
        "kit_versao": KIT_VERSAO,
        "ferramenta": str(ferramenta),
        "formato": formato,
        "parametros": parametros if parametros is not None else {},
        "auditoria": auditoria,
        "gerado_em": agora_iso(),
        "da_json": str(d.caminho),
        "saida": impressao,
    }
    midia = _midia_do_arquivo(fonte, saida.suffix.lower()) if fonte.is_file() else None
    if midia:
        carimbo["midia"] = midia
    if insumos:
        carimbo["insumos"] = lista_insumos
    return gravar_json(caminho_do_carimbo(saida), carimbo)


def _e_intermediario(nome: str) -> bool:
    """D15: nome começado por `_` (pasta ou arquivo) = intermediário de trabalho, não peça."""
    return str(nome).startswith(PREFIXO_INTERMEDIARIO)


def _pecas_em(pasta: Path, extensoes: set[str], raiz_projeto: Path | None = None) -> list[Path]:
    """Peças dentro de uma pasta: arquivos de mídia + subpastas que têm carimbo próprio
    (sequências de quadros). Não desce em da/, em pastas ocultas, em pastas carimbadas, em pastas ou arquivos
    de nome começado por `_` (intermediários, D15) nem em broll/bruto/ (material baixado, ainda sem tratamento)."""
    achadas: list[Path] = []
    sem_pecas = {(raiz_projeto / p).resolve() for p in PASTAS_SEM_PECAS} if raiz_projeto else set()
    for raiz, pastas, arquivos in os.walk(pasta):
        raiz_p = Path(raiz)
        manter = []
        for nome in sorted(pastas):
            sub = raiz_p / nome
            if nome.startswith(".") or nome in ("node_modules", "__pycache__") or (sub / "da.json").is_file():
                continue
            if _e_intermediario(nome) or (sem_pecas and sub.resolve() in sem_pecas):
                continue
            if nome == "build" and (raiz_p / "da.json").is_file():
                continue                         # da/build/: gerado pela compilação e pela prancha, não é peça
            if caminho_do_carimbo(sub).is_file():
                achadas.append(sub)              # pasta carimbada conta como uma peça só
                continue
            manter.append(nome)
        pastas[:] = manter
        for nome in sorted(arquivos):
            if nome.startswith(".") or nome.endswith(".parcial") or ".parcial." in nome or _e_intermediario(nome):
                continue                         # <saida>.parcial (motor), <nome>.parcial.<ext> (video.executar) e _intermediários
            if Path(nome).suffix.lower() in extensoes:
                achadas.append(raiz_p / nome)
    return achadas


def conferir_carimbo(caminhos=None, da=None, de=None, extensoes: set[str] | None = None,
                     exigir_aprovada: bool = False) -> dict:
    """Confere os carimbos das peças. Reprova: sem carimbo, carimbo ilegível, DA diferente da
    atual, auditoria pulada, arquivo alterado depois do carimbo e — mesmo com tudo isso em ordem —
    DA ALTERADA APÓS APROVAÇÃO (o da.json foi editado depois do `aprovar`: o visual em vigor não é o
    que o cliente aprovou; rode `revisar` + `aprovar`). Com exigir_aprovada=True (é como a conferência final chama)
    também reprova DA NÃO APROVADA.

    Composições (D14): peça cujo carimbo lista `insumos` reprova com AUDITORIA PULADA se algum insumo pulou o
    auditor e com INSUMO DE OUTRA DA se algum foi gerado com outra identidade. Intermediários (D15): pasta ou arquivo
    de nome começado por `_` não é conferido; broll/bruto/ também não.

    caminhos: arquivos e/ou pastas; None = pastas de peças do projeto (animacoes, legendas, cortes, thumbs, render,
    broll/tratado). Devolve {'ok': bool, 'da_sha256', 'da_revisao', 'da_aprovada',
    'da_alterada_apos_aprovacao', 'pecas': [{'arquivo','estado','detalhe','livres','insumos'}]}."""
    d = da if isinstance(da, DA) else carregar(da, de=de)
    alterada = bool(d.meta.get("alterada_apos_aprovacao"))
    extensoes = extensoes or (EXT_VIDEO | EXT_IMAGEM)
    if not caminhos:
        caminhos = [d.raiz / p for p in PASTAS_COM_PECAS if (d.raiz / p).is_dir()]
    pecas: list[Path] = []
    resultado: list[dict] = []
    for c in caminhos:
        p = Path(str(c)).expanduser()
        if p.name.endswith(".da.json") and p.is_file():
            p = Path(str(p)[:-len(".da.json")])  # passaram o sidecar: confere a peça dele
        if p.is_dir() and not caminho_do_carimbo(p).is_file():
            pecas += _pecas_em(p, extensoes, d.raiz)
        elif p.exists():
            pecas.append(p)
        else:
            resultado.append({"arquivo": str(p), "estado": "sem_carimbo", "detalhe": "o arquivo não existe"})
    for p in pecas:
        item = {"arquivo": str(p), "estado": "ok", "detalhe": ""}
        resultado.append(item)
        sidecar = caminho_do_carimbo(p)
        if not sidecar.is_file():
            item.update(estado="sem_carimbo", detalhe=f"falta {sidecar.name}: a peça não passou pelo kit")
            continue
        try:
            c = ler_json(sidecar)
            if not isinstance(c, dict) or "da_sha256" not in c or "auditoria" not in c:
                raise DAErro("faltam campos obrigatórios")
        except DAErro as e:
            item.update(estado="carimbo_invalido", detalhe=e.mensagem)
            continue
        item["carimbo"] = c
        if c["da_sha256"] != d.sha256:
            item.update(estado="sha_diferente",
                        detalhe=f"gerada com a DA {str(c['da_sha256'])[:12]}… (revisão {c.get('da_revisao', '?')}); "
                                f"a DA atual é {d.sha256[:12]}… (revisão {d.revisao}) — renderize de novo")
            continue
        insumos = [i for i in (c.get("insumos") or []) if isinstance(i, dict)]
        if insumos:
            item["insumos"] = insumos
        pulados = [i for i in insumos if i.get("auditoria") == "pulada"]
        if c["auditoria"] == "pulada" or pulados:
            item.update(estado="auditoria_pulada", detalhe=(
                "insumo(s) renderizado(s) com --sem-auditoria: " + ", ".join(str(i.get("arquivo")) for i in pulados)
                + " — renderize o insumo de novo com o auditor ligado e refaça a composição") if pulados
                else "renderizada com --sem-auditoria; renderize de novo com o auditor ligado")
            continue
        de_fora = [i for i in insumos if i.get("carimbado") and i.get("da_sha256") and i.get("da_sha256") != d.sha256]
        if de_fora:
            item.update(estado="insumo_de_outra_da", detalhe=(
                "composta com peça(s) de outra DA: " + ", ".join(f"{i.get('arquivo')} ({str(i.get('da_sha256'))[:12]}…)" for i in de_fora)
                + f" — a DA atual é {d.sha256[:12]}…; renderize o insumo de novo e refaça a composição"))
            continue
        esperado = c.get("saida")
        if isinstance(esperado, dict) and p.exists():
            atual = _impressao_saida(p)
            if any(atual.get(k) != esperado.get(k) for k in ("bytes", "sha256", "arquivos") if k in esperado):
                item.update(estado="arquivo_alterado", detalhe="o arquivo mudou depois do carimbo (foi regravado por fora do kit?)")
                continue
        livres = (c.get("parametros") or {}).get("livres") if isinstance(c.get("parametros"), dict) else None
        if isinstance(livres, list) and livres:
            item["livres"] = livres              # elementos data-da-livre da peça: a conferência final lista; alguém decide se procedem
        if alterada:
            item.update(estado="da_alterada",
                        detalhe=f"o da.json foi editado depois da aprovação da revisão {d.revisao}: rode `da.py revisar` e `da.py aprovar`")
            continue
        if exigir_aprovada and not d.aprovada:
            item.update(estado="da_nao_aprovada", detalhe=f"a DA (revisão {d.revisao}) ainda não foi aprovada: rode `da.py aprovar`")
            continue
        notas = []
        if not c.get("da_aprovada") and d.aprovada:
            notas.append("gerada antes da aprovação da DA (conteúdo igual ao aprovado)")
        if c.get("arquivo") and c["arquivo"] != p.name:
            notas.append(f"carimbo gravado para {c['arquivo']!r} (peça renomeada ou copiada; o conteúdo confere)")
        sem = [str(i.get("arquivo")) for i in insumos if not i.get("carimbado")]
        if sem:
            notas.append(f"insumo(s) sem carimbo (material bruto?): {', '.join(sem[:4])}")
        if item.get("livres"):
            notas.append(f"{len(item['livres'])} elemento(s) data-da-livre: "
                         + ", ".join(str(x.get("seletor", "?")) + (f" ({x['motivo']})" if x.get("motivo") else "")
                                     for x in item["livres"][:4] if isinstance(x, dict)))
        item["detalhe"] = "; ".join(notas)
    return {"ok": all(r["estado"] == "ok" for r in resultado), "da_sha256": d.sha256,
            "da_revisao": d.revisao, "da_aprovada": d.aprovada, "da_alterada_apos_aprovacao": alterada, "pecas": resultado}


# ──────────────────────────────────────────────────────────────────── lint ──
_CORES_CSS_TXT = (
    "aliceblue:f0f8ff antiquewhite:faebd7 aqua:00ffff aquamarine:7fffd4 azure:f0ffff beige:f5f5dc bisque:ffe4c4 "
    "black:000000 blanchedalmond:ffebcd blue:0000ff blueviolet:8a2be2 brown:a52a2a burlywood:deb887 cadetblue:5f9ea0 "
    "chartreuse:7fff00 chocolate:d2691e coral:ff7f50 cornflowerblue:6495ed cornsilk:fff8dc crimson:dc143c cyan:00ffff "
    "darkblue:00008b darkcyan:008b8b darkgoldenrod:b8860b darkgray:a9a9a9 darkgreen:006400 darkgrey:a9a9a9 "
    "darkkhaki:bdb76b darkmagenta:8b008b darkolivegreen:556b2f darkorange:ff8c00 darkorchid:9932cc darkred:8b0000 "
    "darksalmon:e9967a darkseagreen:8fbc8f darkslateblue:483d8b darkslategray:2f4f4f darkslategrey:2f4f4f "
    "darkturquoise:00ced1 darkviolet:9400d3 deeppink:ff1493 deepskyblue:00bfff dimgray:696969 dimgrey:696969 "
    "dodgerblue:1e90ff firebrick:b22222 floralwhite:fffaf0 forestgreen:228b22 fuchsia:ff00ff gainsboro:dcdcdc "
    "ghostwhite:f8f8ff gold:ffd700 goldenrod:daa520 gray:808080 green:008000 greenyellow:adff2f grey:808080 "
    "honeydew:f0fff0 hotpink:ff69b4 indianred:cd5c5c indigo:4b0082 ivory:fffff0 khaki:f0e68c lavender:e6e6fa "
    "lavenderblush:fff0f5 lawngreen:7cfc00 lemonchiffon:fffacd lightblue:add8e6 lightcoral:f08080 lightcyan:e0ffff "
    "lightgoldenrodyellow:fafad2 lightgray:d3d3d3 lightgreen:90ee90 lightgrey:d3d3d3 lightpink:ffb6c1 "
    "lightsalmon:ffa07a lightseagreen:20b2aa lightskyblue:87cefa lightslategray:778899 lightslategrey:778899 "
    "lightsteelblue:b0c4de lightyellow:ffffe0 lime:00ff00 limegreen:32cd32 linen:faf0e6 magenta:ff00ff maroon:800000 "
    "mediumaquamarine:66cdaa mediumblue:0000cd mediumorchid:ba55d3 mediumpurple:9370db mediumseagreen:3cb371 "
    "mediumslateblue:7b68ee mediumspringgreen:00fa9a mediumturquoise:48d1cc mediumvioletred:c71585 "
    "midnightblue:191970 mintcream:f5fffa mistyrose:ffe4e1 moccasin:ffe4b5 navajowhite:ffdead navy:000080 "
    "oldlace:fdf5e6 olive:808000 olivedrab:6b8e23 orange:ffa500 orangered:ff4500 orchid:da70d6 palegoldenrod:eee8aa "
    "palegreen:98fb98 paleturquoise:afeeee palevioletred:db7093 papayawhip:ffefd5 peachpuff:ffdab9 peru:cd853f "
    "pink:ffc0cb plum:dda0dd powderblue:b0e0e6 purple:800080 rebeccapurple:663399 red:ff0000 rosybrown:bc8f8f "
    "royalblue:4169e1 saddlebrown:8b4513 salmon:fa8072 sandybrown:f4a460 seagreen:2e8b57 seashell:fff5ee "
    "sienna:a0522d silver:c0c0c0 skyblue:87ceeb slateblue:6a5acd slategray:708090 slategrey:708090 snow:fffafa "
    "springgreen:00ff7f steelblue:4682b4 tan:d2b48c teal:008080 thistle:d8bfd8 tomato:ff6347 turquoise:40e0d0 "
    "violet:ee82ee wheat:f5deb3 white:ffffff whitesmoke:f5f5f5 yellow:ffff00 yellowgreen:9acd32")
CORES_CSS = {par.split(":")[0]: "#" + par.split(":")[1].upper() for par in _CORES_CSS_TXT.split()}

EXT_LINT = {".html", ".htm", ".css", ".js", ".mjs", ".cjs", ".json", ".svg", ".py"}
# Fontes de peça que o lint NÃO sabe ler: numa pasta, arquivo com uma destas extensões sai como "não conferido"
# (nunca como "conferido"); arquivo passado pelo nome com QUALQUER extensão fora de EXT_LINT também.
EXT_FONTE_NAO_COBERTA = {".ts", ".tsx", ".jsx", ".vue", ".svelte", ".scss", ".sass", ".less", ".styl", ".xml", ".xhtml",
                         ".yaml", ".yml", ".toml", ".sh", ".zsh", ".bash", ".swift", ".rb", ".php", ".lua", ".ipynb",
                         ".ass", ".ssa", ".jinja", ".j2", ".njk", ".hbs", ".mustache", ".pug", ".ejs", ".coffee",
                         ".pl", ".r", ".jl", ".go", ".rs", ".kt", ".java", ".c", ".cpp", ".m", ".mm", ".cs", ".dart"}
LINT_MAX_BYTES = 2 * 1024 * 1024
MARCA_LIVRE = "da-livre"
_DINAMICO = "\ue000"                # marca o lugar de uma {expressão} de f-string Python (como o ${…} de um template JS): valor dinâmico
_RE_MARCA_LIVRE = re.compile(r"(?<![\w-])da-livre(?![\w-]*\s*=)")      # o comentário; não o atributo data-da-livre="…"
_RE_TAG_LIVRE = re.compile(r"<([a-zA-Z][\w:-]*)\b[^<>]*\bdata-da-livre\b[^<>]*>")
_RE_ALFA_BARRA = re.compile(r"(?<![\w-])rgba?\(\s*var\(\s*(--da-[\w-]+-rgb)\s*\)\s*/\s*([^()]*?)\s*\)", re.I)
_RE_EXT_FONTE = re.compile(r"[\w)\]}-]\.(?:ttf|otf|ttc|woff2?|pfb|dfont)$", re.I)     # um NOME de arquivo de fonte (".otf" e "*.ttf" sozinhos não)
# Python: nomes (variável, atributo, chave de dict, argumento) que guardam cor
_PY_NOME_COR = re.compile(
    r"(?:^|_)(?:cor(?:es)?|colou?rs?|fill|outline|stroke|fundo|background|bg|fg|paleta|palette|tinta|tint|contorno|sombra|"
    r"borda|destaque|realce|highlight|accent|acento|primari[ao]|secundari[ao]|rgba?|"
    r"pret[oa]|branc[oa]|vermelh[oa]|verde|azul|amarel[oa]|laranja|rox[oa]|rosa|cinza|"
    r"black|white|red|green|blue|yellow|orange|purple|pink|gr[ae]y|magenta|cyan|ciano|dourad[oa]|gold)(?:$|_|\d)", re.I)
# Python: chamadas de desenho → índices dos argumentos POSICIONAIS que são cor (None = todos menos o primeiro, que é xy/caixa)
_PY_CHAMADAS_COR = {"new": (2,), "paste": (0,), "getrgb": (0,), "getcolor": (0,), "colorize": (1, 2, 3), "expand": (2,),
                    "full": (1,), "putpixel": (1,), "text": None, "multiline_text": None, "rectangle": None, "rounded_rectangle": None,
                    "ellipse": None, "circle": None, "line": None, "polygon": None, "regular_polygon": None, "point": None,
                    "arc": None, "chord": None, "pieslice": None, "floodfill": None, "bitmap": None}   # da-livre: índices de argumento, não cor
_PY_FONTE_CHAMADAS = {"truetype", "FreeTypeFont", "load", "load_path"}
# cor literal dentro de um filtro ffmpeg montado em texto: color=#RRGGBB, c=0xRRGGBB, fontcolor=white@0.5
_RE_FFMPEG_COR = re.compile(r"(?<![\w-])(?:color|c|c0|c1|color0|color1|fillcolor|bordercolor|fontcolor|shadowcolor|boxcolor|bgcolor)"
                            r"\s*=\s*(?:(#|0x)([0-9a-fA-F]{6})(?:[0-9a-fA-F]{2})?|([a-zA-Z]{3,}))(?=[@:,;\s'\"\]\[]|$)")
_RE_HEX_SOLTO = re.compile(r"(?<![\w&/.#-])#([0-9a-fA-F]{3,8})(?![\w-])")
_RE_FUNC_COR = re.compile(r"(?<![\w-])(rgba?|hsla?|hwb|lab|lch|oklab|oklch|color)\(\s*([^()]*)\)", re.I)
_RE_ARGS_LITERAIS = re.compile(r"^(?=[^a-zA-Z]*\d)(?:[\d\s.,%/+-]|e[+-]?\d|deg|rad|grad|turn|none)*$", re.I)
_RE_ARGS_COLOR = re.compile(r"^(?:srgb(?:-linear)?|display-p3|a98-rgb|prophoto-rgb|rec2020|xyz(?:-d50|-d65)?)\s+"
                            r"(?=[^a-zA-Z]*\d)(?:[\d\s.,%/+-]|e[+-]?\d|none)*$", re.I)       # color(display-p3 1 0 0)
_RE_URL_CSS = re.compile(r"url\(\s*(?:\"[^\"]*\"|'[^']*'|[^)]*)\)", re.I)
_RE_VAR_CSS = re.compile(r"var\([^()]*(?:\([^()]*\)[^()]*)*\)")
_RE_DECL = re.compile(r"(?:^|(?<=[{;\s\"'`]))(-{0,2}[a-zA-Z][\w-]*)\s*:\s*([^;{}]*)")
_RE_PALAVRA = re.compile(r"(?<![\w#.$-])([a-zA-Z]+)(?![\w(-])")
_RE_FONTE_OK = re.compile(r"^(?:var\(\s*--da-fonte-[\w-]+\s*\)|inherit|initial|unset|revert)$")
_PROPS_COR = re.compile(
    r"^(?:color|background(?:-color|-image)?|border(?:-(?:top|right|bottom|left|block|inline|start|end))*(?:-color)?|"
    r"outline(?:-color)?|fill|stroke|box-shadow|text-shadow|text-decoration(?:-color)?|caret-color|accent-color|"
    r"column-rule(?:-color)?|stop-color|flood-color|lighting-color|-webkit-text-stroke(?:-color)?|"
    r"-webkit-text-fill-color|scrollbar-color|--[\w-]+)$", re.I)
_ATRIB_COR = {"fill", "stroke", "color", "bgcolor", "stop-color", "flood-color", "lighting-color", "text", "link",
              "vlink", "alink", "background-color"}
_ATRIB_REF = re.compile(r"^(?:href|xlink:href|id|for|name|class|src|srcset|action|usemap|list|form|headers|"
                        r"aria-[\w-]+|data-(?:bs-)?(?:target|toggle|parent)|clip-path|mask|filter|marker-(?:start|mid|end)|"
                        r"alt|title|placeholder|d|points|viewbox|transform)$", re.I)
_JS_ANTES_SELETOR = re.compile(r"(?:(?:querySelector(?:All)?|getElementById|closest|matches|select(?:All)?|\$\$?)\s*\(\s*|"
                               r"\b(?:href|hash|id|src|url|to|selector|seletor|alvo)\s*[:=]\s*)$")
_JS_ANTES_COR = re.compile(
    r"(?:\b(?:color|background|backgroundColor|fill|stroke|fillStyle|strokeStyle|borderColor|"
    r"border(?:Top|Right|Bottom|Left)Color|outlineColor|shadowColor|stopColor|floodColor|caretColor|cor\w*|"
    r"fundo\w*|\w+(?:Color|Cor|_cor))\s*[:=]\s*|"
    r"setAttribute\(\s*[\"'](?:fill|stroke|color|stop-color|flood-color)[\"']\s*,\s*|"
    r"addColorStop\(\s*[\d.]+\s*,\s*|"
    r"setProperty\(\s*[\"'](?:color|background(?:-color)?|fill|stroke|border-color|--[\w-]+)[\"']\s*,\s*)$")
# propriedades compostas: a cor vem no meio do valor ('0 0 4px black', '1px solid navy', 'linear-gradient(red, blue)')
_JS_ANTES_COMPOSTA = re.compile(r"\b(?:boxShadow|textShadow|border(?:Top|Right|Bottom|Left)?|outline|background|backgroundImage|"
                                r"borderImage|filter)\s*[:=]\s*$")
_JS_ANTES_CONSOLE = re.compile(r"\bconsole\.\w+\s*\([^;{}]*$")
_JSON_CHAVE_CSS = re.compile(r"^(?:style|css|estilo|cssText)$", re.I)
_JS_ANTES_FONTE = re.compile(r"(?:\bfontFamily\s*[:=]\s*|\.font\s*=\s*|"
                             r"set(?:Property|Attribute)\(\s*[\"']font-family[\"']\s*,\s*)$")
_JSON_CHAVE_COR = re.compile(r"^(?:cor(?:_\w+)?|\w+_cor|color|colour|fundo|background|fill|stroke)$", re.I)
_JSON_CHAVE_REF = re.compile(r"^(?:id|href|src|url|link|hash|ancora|alvo|target|seletor|selector|classe|class|ref|"
                             r"elemento|element|query|\w+(?:_id|Id|_seletor|_selector|Selector|_alvo|_href|_url))$")
_JSON_CHAVE_FONTE = {"font_family", "fontFamily", "font-family", "familia", "fonte_familia"}
_RE_CONTEXTO_CSS = re.compile(r"(?:[:(,]|solid|dashed|dotted|double|px|em|%|deg)\s*$")
_LINT_IGNORAR_ARQ = {"package.json", "package-lock.json", "tsconfig.json", "jsconfig.json", "da.resolvida.json",
                     "grade.json", "referencias_analise.json", "da.json"}
_LINT_IGNORAR_DIR = {"node_modules", "__pycache__", "build", "dist", "vendor"}


def _apagar(texto: str, padrao: re.Pattern) -> str:
    """Troca os trechos casados por espaços (mantendo quebras de linha e posições)."""
    return padrao.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), texto)


def _varrer_js(t: str) -> tuple[str, list[tuple[int, int]]]:
    """Devolve (código com comentários apagados, [(início, fim) do miolo de cada string])."""
    saida, strings, i, n = list(t), [], 0, len(t)
    while i < n:
        c = t[i]
        if c in "\"'`":
            j = i + 1
            while j < n and t[j] != c:
                if t[j] == "\\":
                    j += 1
                elif t[j] == "\n" and c != "`":
                    break
                j += 1
            strings.append((i + 1, min(j, n)))
            i = j + 1
        elif c == "/" and t.startswith("//", i) and (i == 0 or t[i - 1] != ":"):
            j = t.find("\n", i)
            j = n if j < 0 else j
            saida[i:j] = " " * (j - i)
            i = j
        elif c == "/" and t.startswith("/*", i):
            j = t.find("*/", i + 2)
            j = n if j < 0 else j + 2
            saida[i:j] = [ch if ch == "\n" else " " for ch in t[i:j]]
            i = j
        else:
            i += 1
    return "".join(saida), strings


def _cor_de_funcao(nome: str, args: str) -> tuple[str | None, float | None]:
    """rgb()/hsl() com literais → ('#RRGGBB', alfa ou None). Outras funções: (None, None)."""
    nome = nome.lower()
    nums = re.findall(r"[-+]?\d*\.?\d+(?:e[-+]?\d+)?%?", args, flags=re.I)
    if len(nums) < 3:
        return None, None

    def valor(s, base=1.0):
        return float(s[:-1]) / 100 * base if s.endswith("%") else float(s)

    alfa = None
    if len(nums) >= 4:
        alfa = max(0.0, min(1.0, valor(nums[3], 1.0)))
    try:
        if nome in ("rgb", "rgba"):
            return rgb_para_hex(*(valor(x, 255) for x in nums[:3])), alfa
        if nome in ("hsl", "hsla"):
            h = (float(nums[0].rstrip("%")) % 360) / 360
            s, l = (float(x.rstrip("%")) / 100 for x in nums[1:3])
            q = l * (1 + s) if l < 0.5 else l + s - l * s
            p = 2 * l - q

            def canal(t):
                t %= 1
                if t < 1 / 6:
                    return p + (q - p) * 6 * t
                if t < 1 / 2:
                    return q
                if t < 2 / 3:
                    return p + (q - p) * (2 / 3 - t) * 6
                return p

            return rgb_para_hex(*(255 * canal(h + d) for d in (1 / 3, 0, -1 / 3))), alfa
    except ValueError:
        pass
    return None, None


class _Lint:
    def __init__(self, arquivo: Path, texto: str, da: DA | None):
        self.arquivo, self.texto, self.da = arquivo, texto, da
        self.achados: list[dict] = []
        self._vistos: set = set()
        self.inicios = [0]
        for m in re.finditer(r"\n", texto):
            self.inicios.append(m.end())
        linhas = texto.split("\n")
        self.livres: set[int] = set()
        dentro = False
        for i, linha in enumerate(linhas, 1):
            if f"{MARCA_LIVRE}:inicio" in linha:
                dentro = True
            if dentro or _RE_MARCA_LIVRE.search(linha):       # comentário `da-livre` libera a LINHA…
                self.livres.add(i)
            if f"{MARCA_LIVRE}:fim" in linha:
                dentro = False
        self.faixas: list[tuple[int, int]] = self._faixas_livres(texto)   # …e data-da-livre libera só o ELEMENTO (subárvore)
        self.nao_lido: str | None = None                     # motivo, quando o arquivo não pôde ser analisado
        self.papeis = list(da["tipografia"]["papeis"]) if da else list(PAPEIS_BASE)

    @staticmethod
    def _faixas_livres(texto: str) -> list[tuple[int, int]]:
        """[(início, fim)] de cada elemento com data-da-livre: da tag de abertura até a de fechamento correspondente
        (elemento vazio ou `/>`: só a tag). Vale para HTML/SVG e para marcação montada em texto de JS ou Python."""
        faixas = []
        for m in _RE_TAG_LIVRE.finditer(texto):
            fim, nome = m.end(), m.group(1)
            if not m.group(0).rstrip(">").rstrip().endswith("/") and nome.lower() not in (
                    "img", "br", "hr", "input", "meta", "link", "source", "track", "area", "base", "col", "embed", "param", "wbr"):
                nivel = 1
                for x in re.finditer(rf"<(/?){re.escape(nome)}\b[^<>]*>", texto[m.end():], flags=re.I):
                    if x.group(1):
                        nivel -= 1
                    elif not x.group(0).rstrip(">").rstrip().endswith("/"):
                        nivel += 1
                    if nivel == 0:
                        fim = m.end() + x.end()
                        break
            faixas.append((m.start(), fim))
        return faixas

    # -- registro -----------------------------------------------------------
    def _pos(self, pos: int) -> tuple[int, int]:
        lo, hi = 0, len(self.inicios) - 1
        while lo < hi:
            meio = (lo + hi + 1) // 2
            if self.inicios[meio] <= pos:
                lo = meio
            else:
                hi = meio - 1
        return lo + 1, pos - self.inicios[lo] + 1

    def liberar_trecho(self, ini: int, fim: int) -> None:
        a, b = self._pos(ini)[0], self._pos(max(ini, fim - 1))[0]
        self.livres.update(range(a, b + 1))

    def achado(self, pos: int, regra: str, trecho: str, sugestao: str, severidade: str = "erro") -> None:
        linha, coluna = self._pos(pos)
        if linha in self.livres or (pos, regra) in self._vistos or any(a <= pos < b for a, b in self.faixas):
            return
        self._vistos.add((pos, regra))
        self.achados.append({"arquivo": str(self.arquivo), "linha": linha, "coluna": coluna, "regra": regra,
                             "severidade": severidade, "trecho": " ".join(trecho.split())[:80], "sugestao": sugestao})

    # -- sugestões ----------------------------------------------------------
    def sugerir_cor(self, hexa: str | None, alfa: float | None, ctx: str) -> str:
        if self.da is None or hexa is None:
            if ctx == "py":
                return "use um token de cor da DA: d.cor(\"primaria\"), d.rgb(\"fundo\"), d.rgba(\"texto\", 0.6)"
            return "use um token de cor da DA (var(--da-cor-…) no CSS, ctx.cor(…) em cena, nome do token no JSON)"
        cor = self.da["cor"]
        melhor, dist = None, 1e9
        for h in cor["permitidas"]:
            d = delta_e(hexa, h)
            if d < dist:
                melhor, dist = h, d
        token = nome_do_token(melhor, cor) or melhor
        var = css_var_do_token(token)
        com_alfa = alfa is not None and alfa < 1
        if ctx == "json":
            forma = f"o token \"{token}\""
        elif ctx == "py":
            forma = f"d.rgba(\"{token}\", {_num(alfa, 3)})" if com_alfa else f"d.cor(\"{token}\") / d.rgb(\"{token}\")"
        elif com_alfa:
            forma = f"rgba(var({var}-rgb), {_num(alfa, 3)})"       # a ÚNICA forma de alfa da casa (D6); em cena: ctx.alfa(token, a)
        else:
            forma = f"var({var})"
        if ctx == "js":
            forma += " (em cena: ctx.alfa(token, a))" if com_alfa else " (em cena: ctx.cor(token))"
        if melhor == hexa:
            return f"use {forma} — é exatamente o token {token} ({melhor})"
        if dist <= 25:
            return f"use {forma} — token mais próximo: {token} ({melhor}, ΔE {_ptbr(dist, 0)})"
        return (f"cor fora da DA; o token mais próximo é {token} ({melhor}, ΔE {_ptbr(dist, 0)}). "
                f"Use um token ou proponha a cor nova no da.json")

    def sugerir_fonte(self, valor: str) -> str:
        if self.da is not None:
            primeira = valor.split(",")[0].strip().strip("\"'").lower()
            for nome, p in self.da["tipografia"]["papeis"].items():
                if p["familia"].lower() == primeira:
                    return f"use var(--da-fonte-{_css_nome(nome)}) ou a classe .da-{_css_nome(nome)} (papel {nome})"
        return ("use um papel da DA: " + ", ".join(f"var(--da-fonte-{_css_nome(p)})" for p in self.papeis[:5])
                + " (ou as classes .da-<papel>)")

    def sugerir_fonte_py(self) -> str:
        return (f"use a fonte de um papel da DA: d.fonte_pil(\"{self.papeis[0]}\", px) ou texto.Estilo.do_papel(d, \"{self.papeis[0]}\", …) "
                f"(papéis: {', '.join(self.papeis)}); o caminho do arquivo é d.fonte(papel)[\"caminho\"]")

    # -- regras comuns ------------------------------------------------------
    def _hex(self, m: re.Match, off: int, ctx: str) -> None:
        if len(m.group(1)) not in (3, 4, 6, 8):
            return
        corpo = m.group(1)
        base = corpo[:6] if len(corpo) >= 6 else corpo[:3]
        alfa = None
        if len(corpo) == 8:
            alfa = int(corpo[6:], 16) / 255
        elif len(corpo) == 4:
            alfa = int(corpo[3] * 2, 16) / 255
        self.achado(off + m.start(), "cor-hex", m.group(0), self.sugerir_cor(hex_normal("#" + base), alfa, ctx))

    def _funcoes(self, seg: str, off: int, ctx: str) -> None:
        for m in _RE_ALFA_BARRA.finditer(seg):
            self.achado(off + m.start(), "alfa-invalido", m.group(0),
                        f"computa TRANSPARENTE no navegador: {m.group(1)} vale \"r, g, b\" (com vírgulas) e a barra só existe na "
                        f"sintaxe com espaços. Use rgba(var({m.group(1)}), {m.group(2).strip() or 'a'}) — em cena, ctx.alfa(token, a)")
        for m in _RE_FUNC_COR.finditer(seg):
            if m.group(1).lower() == "color":
                if _RE_ARGS_COLOR.match(m.group(2).strip()):
                    self.achado(off + m.start(), "cor-funcao", m.group(0), self.sugerir_cor(None, None, ctx))
            elif _RE_ARGS_LITERAIS.match(m.group(2).strip()):
                hexa, alfa = _cor_de_funcao(m.group(1), m.group(2))
                self.achado(off + m.start(), "cor-funcao", m.group(0), self.sugerir_cor(hexa, alfa, ctx))

    def _declaracoes(self, seg: str, off: int, ctx: str) -> None:
        """Cores nomeadas, font-family literal e transition/animation em declarações CSS."""
        for m in _RE_DECL.finditer(seg):
            prop, val = m.group(1).lower(), m.group(2)
            ini_val = off + m.start(2)
            limpo = val.replace("!important", "").strip()
            if prop == "font-family":
                if limpo and not _RE_FONTE_OK.match(limpo) and "${" not in limpo and _DINAMICO not in limpo:
                    self.achado(ini_val, "fonte-literal", f"font-family: {limpo}", self.sugerir_fonte(limpo))
            elif prop == "font":
                if limpo and limpo not in ("inherit", "initial", "unset", "revert") and "var(--da-fonte-" not in limpo \
                        and "${" not in limpo and _DINAMICO not in limpo:
                    self.achado(ini_val, "fonte-literal", f"font: {limpo}", self.sugerir_fonte(limpo.split()[-1]))
            elif prop in ("transition", "animation") or prop.startswith(("transition-", "animation-")):
                if limpo and limpo.split()[0] not in ("none", "initial", "unset", "inherit"):
                    self.achado(off + m.start(1), "animacao-css", f"{prop}: {limpo}",
                                "peças não usam transition/animation CSS: todo estado é função pura de seek(t)", "aviso")
            elif _PROPS_COR.match(prop):
                sem_var = _apagar(val, _RE_VAR_CSS)
                for p in _RE_PALAVRA.finditer(sem_var):
                    nome = p.group(1).lower()
                    if nome in CORES_CSS:
                        self.achado(ini_val + p.start(1), "cor-nome", f"{prop}: {p.group(1)}",
                                    self.sugerir_cor(CORES_CSS[nome], None, ctx))

    # -- contextos ----------------------------------------------------------
    def css(self, seg: str, off: int, bloco: bool = True) -> None:
        seg = _apagar(_apagar(seg, re.compile(r"/\*.*?\*/", re.S)), _RE_URL_CSS)
        seg = re.sub(r"(?i)(\bcontent\s*:\s*)(\"(?:[^\"\\\n]|\\.)*\"|'(?:[^'\\\n]|\\.)*')",       # content: "red #fff" é texto
                     lambda m: m.group(1) + " " * len(m.group(2)), seg)
        for m in _RE_HEX_SOLTO.finditer(seg):
            antes = seg[:m.start()]
            corte = max(antes.rfind("{"), antes.rfind("}"), antes.rfind(";"))
            if ":" not in antes[corte + 1:]:
                continue                                    # seletor (#abc { … }), não valor
            if bloco:
                prox = re.search(r"[{};]", seg[m.end():])
                if prox and prox.group(0) == "{":
                    continue                                # a:hover #abc { … }
            self._hex(m, off, "css")
        self._funcoes(seg, off, "css")
        self._declaracoes(seg, off, "css")
        for m in re.finditer(r"@keyframes\b", seg):
            self.achado(off + m.start(), "animacao-css", "@keyframes",
                        "peças não usam animação CSS: todo estado é função pura de seek(t)", "aviso")

    def _hex_em_texto(self, s: str, off: int, ctx: str, contexto_de_cor: bool = False) -> None:
        """Hex dentro de uma string de JS/JSON: só conta quando é a string inteira, quando vem em
        contexto CSS ("2px solid #333", "color: #fff") ou quando a chave/propriedade é de cor.
        "Top #100" e "hashtag #cafe" são texto, não cor."""
        for m in _RE_HEX_SOLTO.finditer(s):
            inteiro = s.strip() == m.group(0)
            if inteiro or contexto_de_cor or _RE_CONTEXTO_CSS.search(s[:m.start()]):
                self._hex(m, off, ctx)

    def js(self, seg: str, off: int) -> None:
        codigo, strings = _varrer_js(seg)
        for a, b in strings:
            s = _apagar(codigo[a:b], _RE_URL_CSS)
            antes = codigo[max(0, a - 90):a - 1]
            if _JS_ANTES_CONSOLE.search(antes):
                continue                                    # console.log('cor: #ff0000 não é permitida') é mensagem, não cor
            if _JS_ANTES_COMPOSTA.search(antes):
                for pal in _RE_PALAVRA.finditer(_apagar(s, _RE_VAR_CSS)):
                    if pal.group(1).lower() in CORES_CSS:
                        self.achado(off + a + pal.start(1), "cor-nome", pal.group(1),
                                    self.sugerir_cor(CORES_CSS[pal.group(1).lower()], None, "js"))
            if not _JS_ANTES_SELETOR.search(antes):
                self._hex_em_texto(s, off + a, "js", bool(_JS_ANTES_COR.search(antes)))
            self._funcoes(s, off + a, "js")
            self._declaracoes(s, off + a, "js")
            nome = s.strip().lower()
            if nome in CORES_CSS and _JS_ANTES_COR.search(antes):
                self.achado(off + a, "cor-nome", s.strip(), self.sugerir_cor(CORES_CSS[nome], None, "js"))
            if _JS_ANTES_FONTE.search(antes) and s.strip() and "var(--da-fonte-" not in s and "${" not in s:
                self.achado(off + a, "fonte-literal", s.strip(), self.sugerir_fonte(s.strip().split()[-1]))
        for m in re.finditer(r"\brequestAnimationFrame\s*\(|\.animate\s*\(|\.style\.(?:transition|animation)\w*\s*=", codigo):
            self.achado(off + m.start(), "animacao-css", m.group(0),
                        "o motor chama seek(t) fora de ordem: nada de requestAnimationFrame, .animate() ou transition", "aviso")

    def json(self, seg: str, off: int) -> None:
        chave_de: dict[int, str] = {}                       # posição do valor-texto → chave dele
        for m in re.finditer(r"\"((?:[^\"\\\n]|\\.)*)\"\s*:\s*\"((?:[^\"\\\n]|\\.)*)\"", seg):
            chave_de[m.start(2)] = m.group(1)
        for m in re.finditer(r"\"((?:[^\"\\\n]|\\.)*)\"(\s*:)?", seg):
            if m.group(2):
                continue                                    # é chave
            s, ini = m.group(1), off + m.start(1)
            chave = chave_de.get(m.start(1))
            if chave is not None and _JSON_CHAVE_REF.match(chave):
                continue                                    # "id": "#abc", "alvo": "#palco": referência, não cor
            e_cor = chave is not None and bool(_JSON_CHAVE_COR.match(chave))
            limpo = _apagar(s, _RE_URL_CSS)
            self._hex_em_texto(limpo, ini, "json", e_cor)
            self._funcoes(limpo, ini, "json")
            if chave is None:
                continue
            if e_cor and s.strip().lower() in CORES_CSS:
                self.achado(ini, "cor-nome", f"\"{chave}\": \"{s}\"",
                            self.sugerir_cor(CORES_CSS[s.strip().lower()], None, "json"))
            elif e_cor and "(" in s:                        # "background": "linear-gradient(red, blue)"
                for pal in _RE_PALAVRA.finditer(_apagar(limpo, _RE_VAR_CSS)):
                    if pal.group(1).lower() in CORES_CSS:
                        self.achado(ini + pal.start(1), "cor-nome", f"\"{chave}\": … {pal.group(1)}",
                                    self.sugerir_cor(CORES_CSS[pal.group(1).lower()], None, "json"))
            if _JSON_CHAVE_CSS.match(chave):                # "style": "font-family: Arial; color: red"
                self._declaracoes(limpo, ini, "json")
            if chave in _JSON_CHAVE_FONTE and s.strip() and s not in self.papeis and "var(--da-fonte-" not in s:
                self.achado(ini, "fonte-literal", f"\"{chave}\": \"{s}\"",
                            "use o nome de um papel da DA: " + ", ".join(self.papeis))

    def marcacao(self, seg: str, off: int) -> None:
        for tag in re.finditer(r"<[a-zA-Z][^<>]*>", seg):
            corpo = tag.group(0)
            if re.search(r"\bdata-da-livre\b", corpo):
                continue                                    # o elemento (e a subárvore) já está em self.faixas
            for a in re.finditer(r"([:\w-]+)\s*=\s*(?:\"([^\"]*)\"|'([^']*)')", corpo):
                nome = a.group(1).lower()
                grupo = 2 if a.group(2) is not None else 3
                valor, ini = a.group(grupo), off + tag.start() + a.start(grupo)
                if nome == "style":
                    self.css(valor, ini, bloco=False)
                elif nome in ("font-family", "face"):
                    if valor.strip() and "var(--da-fonte-" not in valor:
                        self.achado(ini, "fonte-literal", f"{nome}=\"{valor}\"", self.sugerir_fonte(valor))
                elif nome in _ATRIB_COR:
                    limpo = _apagar(valor, _RE_URL_CSS)
                    for h in _RE_HEX_SOLTO.finditer(limpo):
                        self._hex(h, ini, "css")
                    self._funcoes(limpo, ini, "css")
                    if valor.strip().lower() in CORES_CSS:
                        self.achado(ini, "cor-nome", f"{nome}=\"{valor}\"",
                                    self.sugerir_cor(CORES_CSS[valor.strip().lower()], None, "css"))
                elif not _ATRIB_REF.match(nome) and not nome.startswith("on"):
                    h = _RE_HEX_SOLTO.fullmatch(valor.strip())
                    if h:
                        self._hex(h, ini + (len(valor) - len(valor.lstrip())), "css")
                    elif _RE_FUNC_COR.fullmatch(valor.strip()):
                        self._funcoes(valor, ini, "css")

    def html(self) -> None:
        t = _apagar(self.texto, re.compile(r"<!--.*?-->", re.S))
        for m in re.finditer(r"<style\b[^>]*>(.*?)</style\s*>", t, flags=re.S | re.I):
            self.css(m.group(1), m.start(1))
        for m in re.finditer(r"<script\b([^>]*)>(.*?)</script\s*>", t, flags=re.S | re.I):
            if "json" in m.group(1).lower():
                self.json(m.group(2), m.start(2))
            else:
                self.js(m.group(2), m.start(2))
        for padrao in (r"(<style\b[^>]*>)(.*?)(</style\s*>)", r"(<script\b[^>]*>)(.*?)(</script\s*>)"):
            t = re.sub(padrao, lambda m: m.group(1) + re.sub(r"[^\n]", " ", m.group(2)) + m.group(3), t, flags=re.S | re.I)
        self.marcacao(t, 0)

    # -- Python (PIL, numpy, filtros ffmpeg montados em texto) ---------------
    def py(self) -> None:
        """Cor e fonte literais em código Python que desenha. Pega: hex em string; tupla/lista RGB(A) literal e nome de cor
        passados a chamadas de desenho (Image.new, ImageDraw.*, paste, ImageColor.getrgb, ImageOps.colorize, np.full) ou a
        argumentos/variáveis/chaves com nome de cor (fill=, outline=, cor_x =, {"fundo": …}); cor literal em filtro ffmpeg
        (color=#…, fontcolor=white); rgb()/hsl() e CSS/SVG montados em texto; ImageFont.truetype com caminho literal,
        ImageFont.load_default() e qualquer caminho literal de arquivo de fonte. Escape: comentário `# da-livre` na linha
        (ou na primeira/última linha da instrução). (0, 0, 0, 0) — transparente — não é cor."""
        import ast
        try:
            arvore = ast.parse(self.texto)
        except (SyntaxError, ValueError) as e:
            self.nao_lido = f"erro de sintaxe na linha {getattr(e, 'lineno', '?')}: o lint de Python precisa analisar o arquivo inteiro"
            return
        linhas = self.texto.split("\n")
        instrucao: list[tuple[int, int]] = [(0, 0)]

        def pos(no) -> int:
            lin = max(1, min(getattr(no, "lineno", 1), len(linhas)))
            col = len(linhas[lin - 1].encode("utf-8")[:getattr(no, "col_offset", 0)].decode("utf-8", "ignore"))
            return self.inicios[lin - 1] + col

        def acusar(no, regra: str, trecho: str, sugestao: str) -> None:
            a, b = instrucao[-1]
            if a in self.livres or b in self.livres:
                return                                      # `# da-livre` na 1ª ou na última linha da instrução
            self.achado(pos(no), regra, trecho, sugestao)

        def e_int(n, lo=0, hi=255) -> bool:
            return isinstance(n, ast.Constant) and type(n.value) is int and lo <= n.value <= hi

        def tupla_cor(n):
            """(hex, alfa) se n é [r, g, b] ou [r, g, b, a] de inteiros 0–255 literais; None se não for (ou for transparente)."""
            if not isinstance(n, (ast.Tuple, ast.List)) or len(n.elts) not in (3, 4) or not all(e_int(x) for x in n.elts[:3]):
                return None
            alfa = None
            if len(n.elts) == 4:
                a = n.elts[3]
                if not (isinstance(a, ast.Constant) and type(a.value) in (int, float) and 0 <= a.value <= 255):
                    return None
                if a.value == 0:
                    return None                             # totalmente transparente: não é cor
                alfa = a.value / 255 if type(a.value) is int and a.value > 1 else float(a.value)
            return rgb_para_hex(*(x.value for x in n.elts[:3])), alfa

        def texto_cor(n):
            """('hex'|'nome', hex) se n é uma string que É uma cor: '#RRGGBB' ou nome CSS."""
            if not (isinstance(n, ast.Constant) and isinstance(n.value, str)):
                return None
            s = n.value.strip()
            m = _RE_HEX_SOLTO.fullmatch(s)
            if m and len(m.group(1)) in (3, 4, 6, 8):
                return "hex", s
            if s.lower() in CORES_CSS:
                return "nome", CORES_CSS[s.lower()]
            return None

        def literais(n):
            """Nós de cor literal dentro de n (o próprio, ou os itens de uma lista/tupla/dict de cores)."""
            if tupla_cor(n) or texto_cor(n):
                yield n
            elif isinstance(n, (ast.Tuple, ast.List, ast.Set)):
                for x in n.elts:
                    yield from literais(x)
            elif isinstance(n, ast.Dict):
                for x in n.values:
                    yield from literais(x)
            elif isinstance(n, ast.IfExp):
                yield from literais(n.body)
                yield from literais(n.orelse)

        def acusar_cor(n, onde: str) -> None:
            for lit in literais(n):
                tc = tupla_cor(lit)
                if tc:
                    self._py_vistos.add(id(lit))
                    acusar(lit, "cor-tupla", f"{onde}: {ast.unparse(lit)}", self.sugerir_cor(tc[0], tc[1], "py"))
                    continue
                tipo, hexa = texto_cor(lit)
                if tipo == "nome":                          # o hex inteiro em string já é acusado em toda string (regra cor-hex)
                    self._py_vistos.add(id(lit))
                    acusar(lit, "cor-nome", f"{onde}: {lit.value!r}", self.sugerir_cor(hexa, None, "py"))

        def nome_de(alvo) -> str:
            if isinstance(alvo, ast.Name):
                return alvo.id
            if isinstance(alvo, ast.Attribute):
                return alvo.attr
            if isinstance(alvo, ast.Subscript) and isinstance(alvo.slice, ast.Constant) and isinstance(alvo.slice.value, str):
                return alvo.slice.value
            if isinstance(alvo, ast.arg):
                return alvo.arg
            return ""

        def fatia_de_pixels(alvo) -> bool:
            """arr[:], arr[...], arr[y0:y1, x0:x1], arr[..., :3]: preencher uma FATIA com 3 ou 4 inteiros é pintar pixels
            (índice simples — pontos[0] = (1, 2, 3) — não conta: pode ser coordenada)."""
            if not isinstance(alvo, ast.Subscript):
                return False
            partes = alvo.slice.elts if isinstance(alvo.slice, ast.Tuple) else [alvo.slice]
            return any(isinstance(x, ast.Slice) or (isinstance(x, ast.Constant) and x.value is Ellipsis) for x in partes)

        def caminho_literal(n) -> bool:
            """O argumento de fonte é um caminho/nome escrito à mão: string ou f-string direta ("Arial", f"{p}/x.ttf"), ou uma
            expressão (Path(...) / ..., os.path.join(...)) que contém um texto com cara de caminho ou de arquivo de fonte.
            d.fonte("titulo")["caminho"] e p["caminho"] não contam: as strings ali são chaves, não caminhos."""
            if isinstance(n, ast.JoinedStr) or (isinstance(n, ast.Constant) and isinstance(n.value, str)):
                return True
            for x in ast.walk(n):
                if isinstance(x, ast.JoinedStr):
                    return True
                if isinstance(x, ast.Constant) and isinstance(x.value, str) and (
                        re.search(r"[/\\]", x.value) or x.value.startswith("~") or _RE_EXT_FONTE.search(x.value.strip())):
                    return True
            return False

        def string(n, s: str) -> None:
            """Confere o texto `s` de uma string (ou de uma f-string inteira, com _DINAMICO no lugar de cada {expressão})."""
            ini = pos(n)
            if not s.strip() or id(n) in self._py_vistos:
                return
            # posição do k-ésimo caractere da string no arquivo: depois do prefixo e das aspas (pedaço de f-string não tem
            # aspas próprias). Com escapes (\\n, \\") a coluna fica aproximada; a linha continua certa.
            aspas = re.match(r"[a-zA-Z]{0,3}(\"\"\"|'''|\"|')", self.texto[ini:ini + 8])
            miolo = ini + (aspas.end() if aspas else 0)

            def onde(k: int) -> int:
                return min(miolo + k, len(self.texto) - 1)
            m = _RE_HEX_SOLTO.fullmatch(s.strip())
            if m and len(m.group(1)) in (3, 4, 6, 8):
                corpo = m.group(1)
                base = corpo[:6] if len(corpo) >= 6 else corpo[:3]
                alfa = int(corpo[6:], 16) / 255 if len(corpo) == 8 else int(corpo[3] * 2, 16) / 255 if len(corpo) == 4 else None
                acusar(n, "cor-hex", s.strip(), self.sugerir_cor(hex_normal("#" + base), alfa, "py"))
                return
            if _RE_EXT_FONTE.search(s.strip()):
                acusar(n, "fonte-literal", s.strip(), self.sugerir_fonte_py())
                return
            for h in _RE_HEX_SOLTO.finditer(s):             # hex no meio de um texto: só com 6/8 dígitos e em contexto de cor
                if len(h.group(1)) in (6, 8) and _RE_CONTEXTO_CSS.search(s[:h.start()]) and not _RE_FFMPEG_COR.search(s[max(0, h.start() - 16):h.end()]):
                    a, b = instrucao[-1]
                    if a not in self.livres and b not in self.livres:
                        self.achado(onde(h.start()), "cor-hex", h.group(0), self.sugerir_cor(hex_normal("#" + h.group(1)[:6]), None, "py"))
            for f in _RE_FFMPEG_COR.finditer(s):
                hexa = "#" + f.group(2).upper() if f.group(2) else CORES_CSS.get((f.group(3) or "").lower())
                if hexa:
                    a, b = instrucao[-1]
                    if a not in self.livres and b not in self.livres:
                        self.achado(onde(f.start()), "cor-ffmpeg", f.group(0),
                                    self.sugerir_cor(hexa, None, "py") + " — em filtro ffmpeg: f\"color={d.cor('token')}\"")
            a, b = instrucao[-1]
            if a in self.livres or b in self.livres:
                return
            self._funcoes(s, miolo, "py")
            if "<" in s and ">" in s:
                self.marcacao(s, miolo)
            if any(c in s for c in "<{;") or "style" in s:
                self._declaracoes(s, miolo, "py")

        def visitar(n, docstring_ok: bool = False) -> None:
            e_instrucao = isinstance(n, ast.stmt) and not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.If,
                                                                         ast.For, ast.AsyncFor, ast.While, ast.With, ast.AsyncWith,
                                                                         ast.Try, ast.Match) + ((ast.TryStar,) if hasattr(ast, "TryStar") else ()))
            if e_instrucao:
                instrucao.append((n.lineno, getattr(n, "end_lineno", n.lineno) or n.lineno))
            try:
                if isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str):
                    return                                  # docstring / texto solto: não é dado
                if isinstance(n, ast.Call):
                    f = n.func
                    nome = f.attr if isinstance(f, ast.Attribute) else f.id if isinstance(f, ast.Name) else ""
                    dono = ast.unparse(f.value) if isinstance(f, ast.Attribute) else ""
                    for kw in n.keywords:
                        if kw.arg and (_PY_NOME_COR.search(kw.arg) or kw.arg in ("stroke_fill", "embedded_color", "mid")):
                            acusar_cor(kw.value, f"{nome or 'chamada'}({kw.arg}=…)")
                    if nome in _PY_CHAMADAS_COR:
                        indices = _PY_CHAMADAS_COR[nome]
                        for i, arg in enumerate(n.args):
                            if (indices is None and i >= 1) or (indices is not None and i in indices):
                                acusar_cor(arg, f"{(dono + '.') if dono else ''}{nome}(…)")
                    if nome in _PY_FONTE_CHAMADAS and (nome in ("truetype", "FreeTypeFont") or "ImageFont" in dono):
                        alvo = n.args[0] if n.args else next((k.value for k in n.keywords if k.arg in ("font", "filename")), None)
                        if alvo is not None and caminho_literal(alvo):
                            for x in ast.walk(alvo):
                                self._py_vistos.add(id(x))
                            acusar(alvo, "fonte-literal", f"{(dono + '.') if dono else ''}{nome}({ast.unparse(alvo)[:50]}…)", self.sugerir_fonte_py())
                    if nome == "load_default" and (not dono or "ImageFont" in dono):
                        acusar(n, "fonte-literal", f"{(dono + '.') if dono else ''}load_default()",
                               "a fonte embutida do PIL não é papel da DA. " + self.sugerir_fonte_py())
                elif isinstance(n, (ast.Assign, ast.AnnAssign, ast.AugAssign)) and getattr(n, "value", None) is not None:
                    alvos = n.targets if isinstance(n, ast.Assign) else [n.target]
                    planos = []
                    for a in alvos:
                        planos += list(a.elts) if isinstance(a, (ast.Tuple, ast.List)) else [a]
                    if any(_PY_NOME_COR.search(nome_de(a)) for a in planos):
                        acusar_cor(n.value, " = ".join(nome_de(a) for a in planos if nome_de(a)) or "atribuição")
                    elif any(fatia_de_pixels(a) for a in planos):
                        acusar_cor(n.value, "pixels[…] =")     # arr[:] = (255, 0, 0), arr[y0:y1, x0:x1] = (10, 10, 10)
                elif isinstance(n, ast.Dict):
                    for k, v in zip(n.keys, n.values):
                        if isinstance(k, ast.Constant) and isinstance(k.value, str) and _PY_NOME_COR.search(k.value):
                            acusar_cor(v, f"{{{k.value!r}: …}}")
                elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                    ar = n.args
                    posicionais = ar.posonlyargs + ar.args
                    for a, padrao in list(zip(posicionais[len(posicionais) - len(ar.defaults):], ar.defaults)) + \
                            [(a, p) for a, p in zip(ar.kwonlyargs, ar.kw_defaults) if p is not None]:
                        if _PY_NOME_COR.search(a.arg):
                            acusar_cor(padrao, f"padrão de {a.arg}")
                elif isinstance(n, ast.JoinedStr):
                    # f-string: confere o texto inteiro de uma vez (pedaço solto engana — "font-family:var(--da-fonte-" + {n} + ")")
                    string(n, "".join(v.value if isinstance(v, ast.Constant) and isinstance(v.value, str) else _DINAMICO for v in n.values))
                    for v in n.values:
                        if isinstance(v, ast.FormattedValue):
                            visitar(v.value)
                    return
                elif isinstance(n, ast.Constant) and isinstance(n.value, str):
                    string(n, n.value)
                for filho in ast.iter_child_nodes(n):
                    visitar(filho)
            finally:
                if e_instrucao:
                    instrucao.pop()

        self._py_vistos: set[int] = set()
        visitar(arvore)

    def rodar(self) -> list[dict]:
        ext = self.arquivo.suffix.lower()
        if ext == ".py":
            self.py()
        elif ext == ".css":
            self.css(self.texto, 0)
        elif ext in (".js", ".mjs", ".cjs"):
            self.js(self.texto, 0)
        elif ext == ".json":
            self.json(self.texto, 0)
        else:
            self.html()
        self.achados.sort(key=lambda a: (a["linha"], a["coluna"]))
        return self.achados


def _lint_le() -> str:
    return " ".join(sorted(EXT_LINT))


def _arquivos_para_lint(caminhos) -> tuple[list[Path], list[str], list[dict]]:
    """(arquivos que o lint sabe ler, notas, não conferidos [{'arquivo', 'motivo'}]).

    Arquivo passado pelo nome com extensão fora de EXT_LINT → não conferido (nunca "conferido": era o sinal verde falso
    para `lint thumbs/thumb.py`). Numa pasta, mídia e documentos são ignorados em silêncio, mas fonte de peça numa
    linguagem que o lint não lê (EXT_FONTE_NAO_COBERTA: .ts, .scss, .sh, .swift…) também sai como não conferida."""
    arquivos, notas, fora = [], [], []
    for c in caminhos:
        p = Path(str(c)).expanduser()
        if p.is_file():
            if p.suffix.lower() in EXT_LINT:
                arquivos.append(p)
            else:
                fora.append({"arquivo": str(p), "motivo": f"extensão {p.suffix or '(nenhuma)'} não é lida pelo lint (ele lê {_lint_le()})"})
        elif p.is_dir():
            for raiz, pastas, nomes in os.walk(p):
                raiz_p = Path(raiz)
                pulados = [d for d in pastas if _e_intermediario(d)] + [n for n in nomes if _e_intermediario(n) and Path(n).suffix.lower() in EXT_LINT]
                if pulados:                                    # D15: _trabalho/, _png/, _rascunho.js não são peças
                    notas.append(f"{_rel(raiz_p)}: {len(pulados)} intermediário(s) com prefixo _ fora do lint ({', '.join(sorted(pulados)[:4])}"
                                 f"{'…' if len(pulados) > 4 else ''}); passe o caminho pelo nome para conferir")
                pastas[:] = sorted(d for d in pastas if not d.startswith(".") and d not in _LINT_IGNORAR_DIR and not _e_intermediario(d)
                                   and not (raiz_p / d / "da.json").is_file())
                for nome in sorted(nomes):
                    if nome.startswith(".") or nome in _LINT_IGNORAR_ARQ or nome.endswith((".da.json", ".min.js", ".min.css")) or _e_intermediario(nome):
                        continue
                    ext = Path(nome).suffix.lower()
                    if ext in EXT_LINT:
                        arquivos.append(raiz_p / nome)
                    elif ext in EXT_FONTE_NAO_COBERTA:
                        fora.append({"arquivo": str(raiz_p / nome),
                                     "motivo": f"fonte de peça em {ext}: o lint não lê essa linguagem (ele lê {_lint_le()})"})
        else:
            raise DAErro(f"lint: {p} não existe")
    return arquivos, notas, fora


def lint(caminhos=None, da=None, de=None, estrito: bool = False) -> dict:
    """Reprova cor literal (hex, rgb()/hsl(), nome CSS, tupla RGB em Python, cor em filtro ffmpeg) e fonte literal
    (font-family, ImageFont.truetype com caminho literal) em fontes de peças: HTML, CSS, JS, SVG, JSON de storyboard e
    Python. Exceção por linha: comentário com `da-livre` (`# da-livre` em Python); por bloco: `da-livre:inicio` …
    `da-livre:fim`; por arquivo: `da-livre-arquivo` nas 10 primeiras linhas; por elemento HTML: atributo data-da-livre
    (vale para o elemento e a subárvore, não para o resto da linha).

    Devolve {'ok', 'arquivos' (quantos foram LIDOS), 'erros', 'avisos', 'achados': [{'arquivo','linha','coluna','regra',
    'severidade','trecho','sugestao'}], 'nao_conferidos': [{'arquivo','motivo'}], 'notas': [...]}.
    `nao_conferidos` = o que foi pedido e o lint não leu (extensão que ele não conhece, arquivo > 2 MB, ilegível, Python
    com erro de sintaxe): nunca conta em 'arquivos'. `estrito=True`: avisos e não conferidos também derrubam o 'ok'.
    Funciona sem DA (só não sugere tokens)."""
    notas: list[str] = []
    d = da if isinstance(da, DA) else None
    if d is None:
        try:
            d = carregar(da, de=de)
        except SemDA:
            notas.append("nenhuma DA encontrada: o lint roda, mas sem sugerir o token mais próximo")
        except DAInvalida as e:
            notas.append(f"a DA tem erros ({len(e.erros)}): o lint roda, mas sem sugerir tokens — rode `da.py validar`")
    if not caminhos:
        if d is None:
            raise DAErro("lint: informe arquivos ou pastas para conferir")
        caminhos = [d.raiz / p for p in PASTAS_COM_PECAS if (d.raiz / p).is_dir()]
    arquivos, notas2, fora = _arquivos_para_lint(caminhos)
    notas += notas2
    achados: list[dict] = []
    conferidos = 0
    for arq in arquivos:
        try:
            if arq.stat().st_size > LINT_MAX_BYTES:
                fora.append({"arquivo": str(arq), "motivo": "maior que 2 MB (biblioteca de terceiros?)"})
                continue
            texto = arq.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            fora.append({"arquivo": str(arq), "motivo": f"não consegui ler ({e.strerror or e})"})
            continue
        if f"{MARCA_LIVRE}-arquivo" in "\n".join(texto.split("\n")[:10]):
            notas.append(f"{_rel(arq)}: marcado com da-livre-arquivo, pulado")
            continue
        analise = _Lint(arq, texto, d)
        do_arquivo = analise.rodar()
        if analise.nao_lido:
            fora.append({"arquivo": str(arq), "motivo": analise.nao_lido})
            continue
        conferidos += 1
        achados += do_arquivo
    erros = sum(1 for a in achados if a["severidade"] == "erro")
    avisos = len(achados) - erros
    return {"ok": erros == 0 and not (estrito and (avisos or fora)), "arquivos": conferidos, "erros": erros, "avisos": avisos,
            "achados": achados, "nao_conferidos": fora, "notas": notas}


# ──────────────────────────────────────────────── recursos, init e presets ──
def recursos_referenciados(fundida: dict, bases: list[Path], com_referencias: bool = False) -> list[tuple[str, Path]]:
    """Arquivos de estilo que a DA usa por caminho RELATIVO: [(caminho como escrito, arquivo absoluto)].
    Cobre os campos de arquivo do esquema e qualquer texto que aponte para fontes/, luts/, texturas/ ou logos/."""
    achados: dict[str, Path] = {}

    def considerar(v: str) -> None:
        if not isinstance(v, str) or not v or Path(v).expanduser().is_absolute() or ".." in Path(v).parts:
            return
        arq = resolver_arquivo(v, bases)
        if arq is not None and arq.is_file():
            achados.setdefault(v, arq)

    def ver(caminho, v, no, pai, chave):
        if not isinstance(v, str):
            return
        if caminho.startswith("conceito.") and not com_referencias:
            return
        if no.get("format") == "da-arquivo" or re.match(r"^(?:fontes|luts|texturas|logos)/", v):
            considerar(v)

    _visitar(fundida, esquema(), "", esquema(), ver)
    return sorted(achados.items())


PASTA_LICENCAS = "LICENCAS"


def licenca_da_fonte(arquivo) -> Path | None:
    """Texto de licença que acompanha um arquivo de fonte: <pasta da fonte>/LICENCAS/OFL-<Prefixo>.txt, onde <Prefixo> é
    o nome do arquivo até o primeiro hífen (Urbanist-Black.ttf → OFL-Urbanist.txt). None se não houver."""
    arquivo = Path(arquivo)
    pasta = arquivo.parent / PASTA_LICENCAS
    prefixo = arquivo.stem.split("-")[0]
    for candidato in (pasta / f"OFL-{prefixo}.txt", pasta / f"LICENCA-{prefixo}.txt", pasta / f"{prefixo}.txt"):
        if candidato.is_file():
            return candidato
    return None


def copiar_recursos(recursos: list[tuple[str, Path]], destino: Path, sobrescrever: bool = True) -> list[Path]:
    """Copia os arquivos de estilo para `destino` mantendo o caminho relativo. A licença de cada fonte (ver
    licenca_da_fonte) vai junto, para <destino>/<pasta da fonte>/LICENCAS/ — a OFL exige que o texto acompanhe cada cópia."""
    copiados = []
    for rel, origem in recursos:
        alvo = destino / rel
        lic = licenca_da_fonte(origem)
        if lic is not None:
            alvo_lic = alvo.parent / PASTA_LICENCAS / lic.name
            if alvo_lic.resolve() != lic.resolve() and not alvo_lic.exists():
                alvo_lic.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(lic, alvo_lic)
        if alvo.resolve() == origem.resolve():
            continue
        if alvo.exists() and not sobrescrever:
            continue
        alvo.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(origem, alvo)
        copiados.append(alvo)
    return copiados


def bloco_claude(nome: str, base: str | None) -> str:
    try:
        modelo = MODELO_CLAUDE.read_text(encoding="utf-8")
    except OSError:
        raise DAErro(f"modelo do CLAUDE.md não encontrado: {MODELO_CLAUDE}")
    corpo = (modelo.replace("{{NOME}}", nome).replace("{{KIT}}", KIT_FINAL)
             .replace("{{PRESET}}", base or "—").replace("{{SKILL}}", SKILL_DA).strip())
    return f"{CLAUDE_INI}\n{corpo}\n{CLAUDE_FIM}"


_RE_CLAUDE_INI = re.compile(r"^[ \t]*" + re.escape(CLAUDE_INI) + r"[ \t]*\r?$", re.M)
_RE_CLAUDE_FIM = re.compile(r"^[ \t]*" + re.escape(CLAUDE_FIM) + r"[ \t]*\r?$", re.M)


def _localizar_bloco_claude(texto: str, arq) -> tuple[int, int]:
    """(início, fim) do bloco da DA no texto do CLAUDE.md — do começo da linha do delimitador de início ao fim da
    linha do delimitador de fim —, ou (-1, -1) se não houver bloco.

    Delimitador só vale quando ocupa a LINHA INTEIRA: uma menção em prosa ("o bloco `<!-- DA:INICIO -->` abaixo…")
    não é delimitador. Tem de haver exatamente um par, na ordem; qualquer outra combinação levanta DAErro e o init
    não mexe em nada (era assim que o bloco duplicava ou que texto do usuário sumia)."""
    inis, fins = list(_RE_CLAUDE_INI.finditer(texto)), list(_RE_CLAUDE_FIM.finditer(texto))
    if not inis and not fins:
        return -1, -1
    if len(inis) == 1 and len(fins) == 1 and fins[0].start() > inis[0].end():
        return inis[0].start(), fins[0].end()
    raise DAErro(f"{arq}: o bloco da DA precisa de exatamente um par de delimitadores, cada um sozinho na própria linha "
                 f"e na ordem ({CLAUDE_INI} … {CLAUDE_FIM}); encontrei {len(inis)} de início e {len(fins)} de fim.",
                 dica="Conserte o arquivo à mão (deixe um par ou nenhum) e rode o init de novo. Nada foi alterado.")


def atualizar_claude_md(raiz: Path, bloco: str, nome: str, registro: dict | None = None) -> str:
    """Escreve/atualiza o bloco delimitado no CLAUDE.md da raiz. Devolve 'criado', 'atualizado',
    'acrescentado' ou 'inalterado'. Nunca toca no que está fora dos delimitadores e, antes de regravar um
    CLAUDE.md que já existia, guarda uma cópia em CLAUDE.md.bak-<data> (o caminho vai em registro['backup_claude_md'])."""
    arq = raiz / "CLAUDE.md"
    if not arq.exists():
        gravar_texto(arq, f"# {nome}\n\n{bloco}\n")
        return "criado"
    try:
        texto = arq.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise DAErro(f"{arq} não está em UTF-8; converta o arquivo e rode o init de novo.")
    i, f = _localizar_bloco_claude(texto, arq)
    if i >= 0:
        novo = texto[:i] + bloco + texto[f:]
        estado = "atualizado"
    else:
        novo = texto.rstrip("\n") + ("\n\n" if texto.strip() else "") + bloco + "\n"
        estado = "acrescentado"
    if novo == texto:
        return "inalterado"
    backup = arq.with_name(f"CLAUDE.md.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
    n = 1
    while backup.exists():                               # dois init no mesmo segundo não sobrepõem o backup
        n += 1
        backup = arq.with_name(f"CLAUDE.md.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{n}")
    shutil.copy2(arq, backup)
    if registro is not None:
        registro["backup_claude_md"] = backup
    gravar_texto(arq, novo)
    return estado


def iniciar(pasta, nome: str | None = None, base: str | None = None, herdar: bool = False,
            forcar: bool = False) -> dict:
    """Cria (ou completa) a estrutura do projeto. Idempotente: sem `forcar`, nunca sobrescreve um da.json.
    Com `forcar` e sem `base`, recria a partir da mesma base da DA existente (projeto.base ou herda).

    Devolve {'raiz', 'da_json', 'criou_da', 'claude_md', 'pastas_criadas', 'recursos', 'avisos', 'backup',
    'backup_claude_md', 'base'}."""
    raiz = Path(str(pasta)).expanduser()
    if raiz.exists() and not raiz.is_dir():
        raise DAErro(f"{raiz} é um arquivo, não uma pasta.", dica="Passe a PASTA do projeto: da.py init <pasta> --nome \"…\"")
    # Tudo o que pode dar errado é conferido ANTES de criar qualquer pasta ou arquivo: um init que falha não deixa rastro.
    existia = (raiz / "da" / "da.json").is_file()
    base_herdada = None
    if existia and forcar and not base:
        # --forcar sem --base recria a DA a partir da MESMA base da atual (antes trocava em silêncio pelo preset padrão)
        try:
            antiga = ler_json(raiz / "da" / "da.json")
            proj_antigo = antiga.get("projeto") if isinstance(antiga.get("projeto"), dict) else {}
            base_herdada = proj_antigo.get("base") or (antiga.get("herda") if isinstance(antiga.get("herda"), str) else None)
        except (DAErro, AttributeError):
            base_herdada = None
        base = base_herdada or None
    if not existia or forcar:
        nome_previsto = nome
        if not nome_previsto and existia:
            try:
                nome_previsto = (ler_json(raiz / "da" / "da.json").get("projeto") or {}).get("nome")
            except (DAErro, AttributeError):
                nome_previsto = None
        if not nome_previsto:
            raise DAErro("faltou o nome do projeto.", dica="Use: da.py init <pasta> --nome \"Nome do projeto\" [--base <preset>]")
        carregar_cadeia(_resolver_herda(base or PRESET_PADRAO, Path.cwd()))      # preset inexistente/ilegível: erro aqui
    claude = raiz / "CLAUDE.md"
    if claude.is_file():
        try:
            _localizar_bloco_claude(claude.read_text(encoding="utf-8"), claude)   # delimitador solto: erro aqui
        except UnicodeDecodeError:
            raise DAErro(f"{claude} não está em UTF-8; converta o arquivo e rode o init de novo.")
    try:
        raiz.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise DAErro(f"não consegui criar a pasta do projeto {raiz}: {e.strerror or e}")
    raiz = raiz.resolve()
    pasta_da = raiz / "da"
    da_json = pasta_da / "da.json"
    criadas = []
    for p in [pasta_da, *(pasta_da / s for s in PASTAS_DA), *(raiz / s for s in PASTAS_TRABALHO), *(raiz / s for s in SUBPASTAS_TRABALHO)]:
        if not p.is_dir():
            p.mkdir(parents=True, exist_ok=True)
            criadas.append(p)
    info = {"raiz": raiz, "da_json": da_json, "criou_da": False, "pastas_criadas": criadas, "recursos": [],
            "avisos": [], "backup": None, "base": None, "backup_claude_md": None}
    if existia and forcar:
        if base_herdada:
            info["avisos"].append(f"--forcar sem --base: recriei a DA a partir da mesma base da anterior ({base_herdada}). "
                                  f"Para trocar de base, passe --base <preset>.")
        elif not base:
            info["avisos"].append(f"--forcar sem --base: a DA anterior não registrava a base; usei o preset padrão ({PRESET_PADRAO}). "
                                  f"Se não era isso, restaure o backup e rode de novo com --base <preset>.")
    if existia and not forcar:
        dados = ler_json(da_json)
        proj = dados.get("projeto") if isinstance(dados, dict) and isinstance(dados.get("projeto"), dict) else {}
        nome_final, base_final = proj.get("nome") or nome or raiz.name, proj.get("base") or dados.get("herda")
        if base and base != base_final:
            info["avisos"].append(f"já existe uma DA neste projeto (base {base_final or '—'}); --base {base} foi ignorado. "
                                  f"Use --forcar para recriar o da.json a partir do preset (o atual vira backup).")
    else:
        nome_final = nome
        if not nome_final and existia:
            try:
                nome_final = (ler_json(da_json).get("projeto") or {}).get("nome")
            except (DAErro, AttributeError):
                nome_final = None
        if not nome_final:
            raise DAErro("faltou o nome do projeto.", dica="Use: da.py init <pasta> --nome \"Nome do projeto\" [--base <preset>]")
        base_final = base or PRESET_PADRAO
        origem = _resolver_herda(base_final, Path.cwd())
        cadeia = carregar_cadeia(origem)
        fundida = fundir_cadeia(cadeia)
        bases = bases_da_cadeia(cadeia)
        projeto = {"nome": nome_final, "slug": slugificar(nome_final), "criada_em": agora_iso(), "revisao": 1,
                   "aprovada": False, "aprovada_em": None, "aprovada_sha256": None, "base": base_final}
        if herdar:
            dados = {"versao_esquema": 1, "herda": str(origem) if _parece_caminho(base_final) else base_final,
                     "projeto": projeto}
        else:
            dados = {"versao_esquema": 1, "herda": None, "projeto": projeto}
            for k, v in fundida.items():
                if k not in dados:
                    dados[k] = v
            if isinstance(dados.get("conceito"), dict):
                dados["conceito"]["referencias"] = []        # referências são do projeto, não do preset
        info["recursos"] = copiar_recursos(recursos_referenciados(fundida, bases), pasta_da, sobrescrever=forcar)
        if existia:
            backup = da_json.with_name(f"da.json.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
            shutil.copy2(da_json, backup)
            info["backup"] = backup
        gravar_json(da_json, dados)
        info["criou_da"] = True
    info["base"] = base_final
    info["claude_md"] = atualizar_claude_md(raiz, bloco_claude(nome_final, base_final), nome_final, registro=info)
    try:
        comp = compilar_da(da_json)
        info["avisos"] += comp["avisos"]
        info["sha256"] = comp["sha256"]
        if existia and forcar:                              # troca de base: as fontes da base anterior ficam em da/fontes/
            orfas = fontes_orfas(da_json)
            if orfas:
                info["avisos"].append(f"{len(orfas)} fonte(s) em da/fontes/ que a DA não usa mais: {', '.join(a.name for a in orfas)} "
                                      f"— sobra da base anterior; apague se não forem voltar")
    except DAInvalida as e:
        info["avisos"].append(f"a DA existente tem {len(e.erros)} erro(s) e não foi compilada — rode `da.py validar`")
    return info


def salvar_preset(nome: str, caminho=None, de=None, forcar: bool = False) -> dict:
    """Guarda a DA resolvida do projeto (herança aplicada) na biblioteca pessoal, com as fontes,
    LUTs, texturas e logos que ela referencia. Devolve {'pasta', 'da_json', 'recursos', 'avisos'}."""
    nome = str(nome).strip()
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", nome):
        raise DAErro(f"nome de preset {nome!r} inválido; use minúsculas, números e hífens (ex.: 'meu-canal').",
                     dica=f"Sugestão: {slugificar(nome)}")
    if (PRESETS_DIR / f"{nome}.json").is_file():
        raise DAErro(f"{nome!r} é o nome de um preset embutido do kit; escolha outro nome para o seu preset.")
    da_json = achar(de=de, da=caminho).resolve()
    cadeia = carregar_cadeia(da_json)
    fundida = fundir_cadeia(cadeia)
    bases = bases_da_cadeia(cadeia)
    erros, avisos = validar_dados(fundida, bases)
    if erros:
        raise DAInvalida(da_json, erros, avisos)
    destino = presets_pessoais_dir() / nome
    if (destino / "da.json").exists() and not forcar:
        raise DAErro(f"o preset pessoal {nome!r} já existe em {destino}.", dica="Use --forcar para substituir.")
    dados = copy.deepcopy(fundida)
    origem = dados.get("projeto") or {}
    dados["herda"] = None
    dados["projeto"] = {"nome": origem.get("nome") or nome, "slug": nome, "criada_em": agora_iso(), "revisao": 1,
                        "aprovada": False, "aprovada_em": None, "aprovada_sha256": None,
                        "base": origem.get("base")}
    notas = []
    if dados["conceito"].get("referencias"):
        notas.append(f"{len(dados['conceito']['referencias'])} referência(s) do projeto não foram levadas para o preset")
        dados["conceito"]["referencias"] = []
    if destino.exists() and forcar:
        for sub in PASTAS_DA:
            shutil.rmtree(destino / sub, ignore_errors=True)
    destino.mkdir(parents=True, exist_ok=True)
    copiados = copiar_recursos(recursos_referenciados(fundida, bases), destino)
    gravar_json(destino / "da.json", dados)
    return {"pasta": destino, "da_json": destino / "da.json", "recursos": copiados, "avisos": avisos, "notas": notas}


def remover_preset(nome: str) -> Path:
    """Apaga um preset da biblioteca PESSOAL ($VIDEO_OPS_HOME/da-presets/<nome>/). Embutidos não se removem.
    Devolve a pasta apagada."""
    nome = str(nome).strip()
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", nome):
        raise DAErro(f"nome de preset {nome!r} inválido (minúsculas, números e hífens).")
    pasta = presets_pessoais_dir() / nome
    if not (pasta / "da.json").is_file():
        if (PRESETS_DIR / f"{nome}.json").is_file():
            raise DAErro(f"{nome!r} é um preset embutido do kit: não é removível.")
        pessoais = [x["nome"] for x in listar_presets() if x["origem"] == "pessoal"]
        raise DAErro(f"o preset pessoal {nome!r} não existe em {presets_pessoais_dir()}.{_sugerir(nome, pessoais)}")
    shutil.rmtree(pasta)
    return pasta


def fontes_orfas(da_json) -> list[Path]:
    """Arquivos em <da>/fontes/ que a DA (com a herança aplicada) não usa mais — sobra de uma troca de base ou de rota.
    Só lista; apagar é decisão de quem chamou. Licenças (fontes/LICENCAS/) não contam."""
    da_json = Path(da_json).resolve()
    pasta = da_json.parent / "fontes"
    if not pasta.is_dir():
        return []
    cadeia = carregar_cadeia(da_json)
    usados = {arq.resolve() for _, arq in recursos_referenciados(fundir_cadeia(cadeia), bases_da_cadeia(cadeia))}
    return sorted(a for a in pasta.iterdir() if a.is_file() and not a.name.startswith(".") and a.resolve() not in usados)


# ─────────────────────────────────────────────────────────────────── rotas ──
PASTA_ROTAS = "rotas"
_RE_NOME_ROTA = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


def pasta_das_rotas(da_json) -> Path:
    """<projeto>/da/rotas/ do projeto a que `da_json` pertence (se `da_json` já é uma rota, a pasta das irmãs)."""
    pai = projeto_pai(da_json)
    return (pai / "da" if pai is not None else Path(da_json).resolve().parent) / PASTA_ROTAS


def _da_do_projeto(caminho=None, de=None) -> Path:
    """da.json do PROJETO (nunca o de uma rota): quem roda `rotas` de dentro de uma rota sobe para o pai."""
    da_json = achar(de=de, da=caminho).resolve()
    pai = projeto_pai(da_json)
    return (pai / "da" / "da.json") if pai is not None else da_json


def caminho_da_rota(nome: str, caminho=None, de=None) -> Path:
    """da.json de uma rota do projeto pelo nome; DAErro com sugestão se não existir."""
    da_json = _da_do_projeto(caminho, de)
    alvo = da_json.parent / PASTA_ROTAS / str(nome).strip() / "da" / "da.json"
    if not alvo.is_file():
        nomes = [r["nome"] for r in listar_rotas(caminho, de)]
        raise DAErro(f"a rota {nome!r} não existe em {da_json.parent / PASTA_ROTAS}.{_sugerir(str(nome), nomes)}",
                     dica="Rotas do projeto: " + (", ".join(nomes) or "(nenhuma)") + f" — crie com `{DA_CLI} rotas criar <nome> --base <preset>`")
    return alvo


def criar_rota(nome: str, base: str | None = None, frase: str | None = None, cores: dict | None = None,
               caminho=None, de=None, forcar: bool = False) -> dict:
    """Cria uma ROTA — uma DA candidata — em <projeto>/da/rotas/<nome>/da/da.json, herdando de `base` e sobrescrevendo só
    o que a diferencia. base: nome de preset, caminho de outro da.json ou None/'atual' (herda a DA do próprio projeto).
    cores: {'primaria': '#RRGGBB', …} vai para cor.paleta. Não cria pastas de trabalho: a rota enxerga as referências, o
    bruto e o b-roll do projeto-pai. Devolve {'nome', 'da_json', 'herda', 'erros', 'avisos'} (a validação já rodada)."""
    nome = str(nome).strip()
    if not _RE_NOME_ROTA.fullmatch(nome):
        raise DAErro(f"nome de rota {nome!r} inválido; use minúsculas, números e hífens (ex.: 'rota-a', 'papel-quente').",
                     dica=f"Sugestão: {slugificar(nome)}")
    da_json = _da_do_projeto(caminho, de)
    alvo = da_json.parent / PASTA_ROTAS / nome / "da" / "da.json"
    if alvo.exists() and not forcar:
        raise DAErro(f"a rota {nome!r} já existe em {alvo}.", dica="Use --forcar para recriá-la (a anterior vira backup).")
    if base in (None, "", "atual"):
        herda, rotulo_base = "../../../da.json", "a DA atual do projeto"
        carregar_cadeia(da_json)
    else:
        origem = _resolver_herda(str(base), Path.cwd())      # preset inexistente / caminho errado: erro aqui, antes de criar
        herda = str(origem) if _parece_caminho(str(base)) else str(base)
        rotulo_base = str(base)
    paleta = {}
    for chave, valor in (cores or {}).items():
        if not re.fullmatch(r"[a-z][a-z0-9_]*", str(chave)):
            raise DAErro(f"cor {chave!r}: use o nome de uma cor da paleta (primaria, secundaria, destaque, fundo, texto…).")
        paleta[str(chave)] = hex_normal(valor)
    proj_nome = (ler_json(da_json).get("projeto") or {}).get("nome") or da_json.parent.parent.name
    dados = {"versao_esquema": 1, "herda": herda,
             "projeto": {"nome": f"{proj_nome} — {nome if nome.startswith('rota') else 'rota ' + nome}",
                         "slug": f"rota-{nome}" if not nome.startswith("rota") else nome,
                         "criada_em": agora_iso(), "revisao": 1, "aprovada": False, "aprovada_em": None, "aprovada_sha256": None,
                         "base": rotulo_base if base not in (None, "", "atual") else None},
             "conceito": {"frase": frase.strip() if frase and frase.strip() else f"{nome}: escreva aqui a frase de conceito desta rota."}}
    if paleta:
        dados["cor"] = {"paleta": paleta}
    alvo.parent.mkdir(parents=True, exist_ok=True)
    if alvo.exists():
        shutil.copy2(alvo, alvo.with_name(f"da.json.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}"))
    gravar_json(alvo, dados)
    r = validar(alvo)
    return {"nome": nome, "da_json": alvo, "herda": herda, "erros": r["erros"], "avisos": r["avisos"]}


def listar_rotas(caminho=None, de=None) -> list[dict]:
    """Rotas do projeto: [{'nome', 'da_json', 'herda', 'frase', 'primaria', 'fundo', 'sha256', 'erros', 'avisos',
    'prancha' {formato: estado}, 'teste_movimento': estado}] — estado em 'em dia' | 'desatualizada' | 'ausente'."""
    da_json = _da_do_projeto(caminho, de)
    pasta = da_json.parent / PASTA_ROTAS
    saida = []
    if not pasta.is_dir():
        return saida
    for sub in sorted(x for x in pasta.iterdir() if x.is_dir() and not x.name.startswith((".", PREFIXO_INTERMEDIARIO))):
        arq = sub / "da" / "da.json"
        if not arq.is_file():
            continue
        item = {"nome": sub.name, "da_json": arq, "herda": None, "frase": "", "primaria": None, "fundo": None, "sha256": None,
                "erros": [], "avisos": [], "prancha": {}, "teste_movimento": "ausente"}
        try:
            cadeia = carregar_cadeia(arq)
            fundida = fundir_cadeia(cadeia)
            item["herda"] = cadeia[0]["dados"].get("herda")
            item["frase"] = ((fundida.get("conceito") or {}).get("frase") or "").strip()
            pal = ((fundida.get("cor") or {}).get("paleta") or {})
            item["primaria"], item["fundo"] = pal.get("primaria"), pal.get("fundo")
            item["erros"], item["avisos"] = validar_dados(fundida, bases_da_cadeia(cadeia))
            item["sha256"] = identidade(fundida, bases_da_cadeia(cadeia))
            docs = documentos_de_aprovacao(arq)
            item["prancha"] = {"horizontal": docs["prancha.png"]["estado"], "vertical": docs["prancha_vertical.png"]["estado"]}
            item["teste_movimento"] = docs["teste_movimento.mp4"]["estado"]
        except DAErro as e:
            item["erros"] = [e.mensagem]
        saida.append(item)
    return saida


def adotar_rota(nome: str, caminho=None, de=None) -> dict:
    """Adota uma rota como a DA do projeto, sem passar pela biblioteca pessoal: grava em <projeto>/da/da.json a rota com
    a herança aplicada, copia para da/ as fontes/LUTs/texturas/logos que ela usa (com as licenças), guarda o da.json
    anterior em da.json.bak-<data>, atualiza o bloco do CLAUDE.md e recompila. Preserva nome, slug e data de criação do
    projeto e as referências do conceito que o projeto já tinha; a aprovação é zerada e, se a DA anterior estava
    aprovada, a revisão sobe 1. Devolve {'da_json', 'backup', 'recursos', 'orfas', 'sha256', 'revisao', 'avisos'}."""
    da_json = _da_do_projeto(caminho, de)
    rota = caminho_da_rota(nome, caminho, de)
    cadeia = carregar_cadeia(rota)
    fundida = fundir_cadeia(cadeia)
    bases = bases_da_cadeia(cadeia)
    erros, avisos = validar_dados(fundida, bases)
    if erros:
        raise DAInvalida(rota, erros, avisos)
    atual = ler_json(da_json)
    proj_atual = atual.get("projeto") if isinstance(atual.get("projeto"), dict) else {}
    dados = copy.deepcopy(fundida)
    base = (dados.get("projeto") or {}).get("base") or cadeia[0]["dados"].get("herda")
    if isinstance(base, str) and base.endswith("da.json"):
        base = proj_atual.get("base")                      # a rota herdava a própria DA do projeto: a base continua a mesma
    dados["herda"] = None
    revisao = int(proj_atual.get("revisao") or 1) + (1 if proj_atual.get("aprovada") else 0)
    dados["projeto"] = {"nome": proj_atual.get("nome") or da_json.parent.parent.name,
                        "slug": proj_atual.get("slug") or slugificar(proj_atual.get("nome") or da_json.parent.parent.name),
                        "criada_em": proj_atual.get("criada_em") or agora_iso(), "revisao": revisao, "aprovada": False,
                        "aprovada_em": None, "aprovada_sha256": None, "base": base, "rota_adotada": nome}
    refs_rota = (dados.get("conceito") or {}).get("referencias") or []
    refs_proj = (atual.get("conceito") or {}).get("referencias") or [] if isinstance(atual.get("conceito"), dict) else []
    if isinstance(dados.get("conceito"), dict) and not refs_rota and refs_proj:
        dados["conceito"]["referencias"] = copy.deepcopy(refs_proj)
    copiados = copiar_recursos(recursos_referenciados(fundida, bases), da_json.parent, sobrescrever=True)
    backup = da_json.with_name(f"da.json.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
    shutil.copy2(da_json, backup)
    gravar_json(da_json, dados)
    raiz = da_json.parent.parent
    info = {"da_json": da_json, "backup": backup, "recursos": copiados, "rota": rota, "revisao": revisao, "avisos": list(avisos)}
    info["claude_md"] = atualizar_claude_md(raiz, bloco_claude(dados["projeto"]["nome"], base), dados["projeto"]["nome"], registro=info)
    comp = compilar_da(da_json)
    info["sha256"] = comp["sha256"]
    info["orfas"] = fontes_orfas(da_json)
    return info


# ────────────────────────────────────────────────────── aprovação e revisão ──
DOCUMENTOS_DE_APROVACAO = ("prancha.png", "prancha_vertical.png", "teste_movimento.mp4")


def documentos_de_aprovacao(caminho=None, de=None) -> dict:
    """Estado dos documentos que o cliente vê antes de aprovar — da/prancha.png, da/prancha_vertical.png e
    da/teste_movimento.mp4: {nome: {'arquivo', 'estado', 'detalhe'}} com estado 'em dia' (carimbo com o sha da DA atual),
    'desatualizada' (carimbo de outra DA, arquivo trocado sem carimbar, ou mais velho que o da.json) ou 'ausente'."""
    da_json = achar(de=de, da=caminho).resolve()
    cadeia = carregar_cadeia(da_json)
    sha = identidade(fundir_cadeia(cadeia), bases_da_cadeia(cadeia))
    saida = {}
    for nome in DOCUMENTOS_DE_APROVACAO:
        arq = da_json.parent / nome
        if not arq.is_file():
            saida[nome] = {"arquivo": arq, "estado": "ausente", "detalhe": "não foi gerado"}
            continue
        c = ler_carimbo(arq)
        if c is None:
            velho = arq.stat().st_mtime < da_json.stat().st_mtime
            saida[nome] = {"arquivo": arq, "estado": "desatualizada" if velho else "em dia",
                           "detalhe": "sem carimbo; mais velho que o da.json" if velho else "sem carimbo (conferido pela data)"}
        elif c.get("da_sha256") != sha:
            saida[nome] = {"arquivo": arq, "estado": "desatualizada",
                           "detalhe": f"feito com outra versão da DA (sha {str(c.get('da_sha256'))[:12]}…, atual {sha[:12]}…)"}
        else:
            saida[nome] = {"arquivo": arq, "estado": "em dia", "detalhe": f"sha {sha[:12]}…", "escala": (c.get("parametros") or {}).get("escala"),
                           "aprovada_no_carimbo": bool(c.get("da_aprovada"))}
    return saida


def aprovar(caminho=None, de=None) -> dict:
    """Marca a DA como aprovada: grava aprovada=true, aprovada_em e aprovada_sha256 e recompila.
    Devolve {'da_json', 'sha256', 'revisao', 'estado': 'aprovada' | 'ja_aprovada', 'avisos', 'notas'}."""
    da_json = achar(de=de, da=caminho).resolve()
    cadeia = carregar_cadeia(da_json)
    fundida = fundir_cadeia(cadeia)
    bases = bases_da_cadeia(cadeia)
    notas: list[str] = []
    erros, avisos = validar_dados(fundida, bases, notas)
    if erros:
        raise DAInvalida(da_json, erros, avisos)
    dados = cadeia[0]["dados"]
    proj = dados["projeto"]
    sha = identidade(fundida, bases)
    if proj.get("aprovada"):
        if proj.get("aprovada_sha256") == sha:
            return {"da_json": da_json, "sha256": sha, "revisao": proj["revisao"], "estado": "ja_aprovada", "avisos": avisos, "notas": list(dict.fromkeys(notas))}
        raise DAErro(f"a DA foi alterada depois da aprovação da revisão {proj['revisao']}.",
                     dica="Abra uma nova revisão com `da.py revisar` e só então rode `da.py aprovar`.")
    proj["aprovada"], proj["aprovada_em"], proj["aprovada_sha256"] = True, agora_iso(), sha
    gravar_json(da_json, dados)
    compilar_da(da_json)
    return {"da_json": da_json, "sha256": sha, "revisao": proj["revisao"], "estado": "aprovada",
            "avisos": [a for a in avisos if "DEPOIS DA APROVAÇÃO" not in a], "notas": list(dict.fromkeys(notas))}


def revisar(caminho=None, de=None) -> dict:
    """Abre uma nova revisão: incrementa projeto.revisao e zera a aprovação. Recompila se a DA for válida.
    Devolve {'da_json', 'revisao', 'anterior', 'estava_aprovada', 'compilada'}."""
    da_json = achar(de=de, da=caminho).resolve()
    dados = ler_json(da_json)
    proj = dados.get("projeto") if isinstance(dados, dict) else None
    if not isinstance(proj, dict) or not isinstance(proj.get("revisao"), int):
        raise DAErro(f"{da_json}: não encontrei projeto.revisao; rode `da.py validar` e corrija a estrutura.")
    anterior, estava = proj["revisao"], bool(proj.get("aprovada"))
    proj["revisao"] = anterior + 1
    proj["aprovada"], proj["aprovada_em"], proj["aprovada_sha256"] = False, None, None
    gravar_json(da_json, dados)
    compilada = True
    try:
        compilar_da(da_json)
    except DAInvalida:
        compilada = False
    return {"da_json": da_json, "revisao": proj["revisao"], "anterior": anterior, "estava_aprovada": estava,
            "compilada": compilada}


# ───────────────────────────────────────────────────────── ffmpeg (via trava) ──
def _bin(nome: str) -> str:
    return (os.environ.get(f"VIDEO_OPS_{nome.upper()}") or shutil.which(nome)
            or (f"/opt/homebrew/bin/{nome}" if Path(f"/opt/homebrew/bin/{nome}").exists() else nome))


def sondar(arquivo) -> dict:
    """ffprobe enxuto: {'largura', 'altura', 'duracao', 'fps', 'tem_audio'}."""
    try:
        r = subprocess.run([_bin("ffprobe"), "-v", "error", "-show_entries",
                            "stream=codec_type,width,height,r_frame_rate,duration:format=duration",
                            "-of", "json", str(arquivo)], capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=120)
    except FileNotFoundError:
        raise DAErro("ffprobe não encontrado; instale o ffmpeg (brew install ffmpeg)")
    except subprocess.TimeoutExpired:
        raise DAErro(f"ffprobe não respondeu em 120 s lendo {arquivo}; o arquivo está corrompido ou num disco que não responde")
    if r.returncode != 0:
        raise DAErro(f"ffprobe não conseguiu ler {arquivo}: {r.stderr.strip()[-300:]}")
    dados = json.loads(r.stdout or "{}")
    video = next((s for s in dados.get("streams", []) if s.get("codec_type") == "video"), None)
    if video is None:
        raise DAErro(f"{arquivo} não tem trilha de vídeo")

    def num(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return 0.0

    return {"largura": int(video.get("width") or 0), "altura": int(video.get("height") or 0),
            "duracao": num(video.get("duration")) or num((dados.get("format") or {}).get("duration")),
            "fps": video.get("r_frame_rate"),
            "tem_audio": any(s.get("codec_type") == "audio" for s in dados.get("streams", []))}


def _rodar_ffmpeg(args: list[str], rotulo: str) -> None:
    """ffmpeg sob a trava global; levanta DAErro com o fim do stderr se falhar."""
    cmd = [_bin("ffmpeg"), "-hide_banner", "-v", "error", "-nostdin", *args]
    try:
        r = trava.rodar(cmd, rotulo=rotulo, capturar=True, inatividade=trava.inatividade_padrao(120.0))
    except FileNotFoundError:
        raise DAErro("ffmpeg não encontrado; instale com `brew install ffmpeg`")
    if r.motivo:
        raise DAErro(f"ffmpeg travou em: {rotulo} — {trava.descrever_vigia(r)}")
    if r.codigo != 0:
        raise DAErro(f"ffmpeg falhou (código {r.codigo}) em: {rotulo}\n{(r.stderr or '').strip()[-800:]}")


def filtros_da_cadeia(cadeia: str) -> list[str]:
    """Nomes dos filtros usados numa cadeia (para conferir contra `ffmpeg -filters`)."""
    limpa = re.sub(r"\\.", "", cadeia)
    limpa = re.sub(r"'[^']*'", "", limpa)
    nomes = []
    for pedaco in re.split(r"[,;]", limpa):
        pedaco = re.sub(r"^(?:\s*\[[^\]]*\])+", "", pedaco.strip())
        m = re.match(r"[A-Za-z0-9_]+", pedaco)
        if m and m.group(0) not in nomes:
            nomes.append(m.group(0))
    return nomes


def filtros_do_ffmpeg() -> set[str]:
    try:
        r = subprocess.run([_bin("ffmpeg"), "-hide_banner", "-filters"], capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=60)
    except FileNotFoundError:
        raise DAErro("ffmpeg não encontrado; instale com `brew install ffmpeg`")
    nomes = set()
    for linha in r.stdout.splitlines():
        m = re.match(r"^\s*[TSC.]{2,3}\s+(\S+)\s+\S+->\S+", linha)
        if m:
            nomes.add(m.group(1))
    return nomes


def aplicar_grade(entrada, saida, da: DA | None = None, parte: str = "completa", inicio: float | None = None,
                  duracao: float | None = None, crf: int = 18) -> dict:
    """Aplica o tratamento da DA a um vídeo ou imagem (ffmpeg sob a trava) e carimba a saída.
    Vídeo sai em H.264 yuv420p (áudio copiado). Devolve {'saida', 'cadeia', 'carimbo'}."""
    entrada, saida = Path(str(entrada)).expanduser(), Path(str(saida)).expanduser()
    if not entrada.is_file():
        raise DAErro(f"entrada não encontrada: {entrada}")
    if entrada.resolve() == saida.resolve():
        raise DAErro("entrada e saída são o mesmo arquivo; escolha outro nome para a saída")
    d = da or _da_para(saida.parent.resolve() if saida.parent.exists() else Path.cwd())
    info = sondar(entrada)
    L, A = info["largura"], info["altura"]
    imagem = saida.suffix.lower() in EXT_IMAGEM
    partes = {"completa": ("cor", "acabamento"), "cor": ("cor",), "acabamento": ("acabamento",)}
    if parte not in partes:
        raise DAErro(f"parte {parte!r} inválida; use completa, cor ou acabamento")
    cadeia = cadeia_tratamento(d, L, A, partes[parte], "yuv444p" if imagem else "yuv420p")["cadeia"]
    saida.parent.mkdir(parents=True, exist_ok=True)
    tmp = saida.with_name(f"{saida.stem}.parcial{saida.suffix}")
    args = ["-y"]
    if inicio is not None:
        args += ["-ss", _num(inicio, 3)]
    if duracao is not None and not imagem:
        args += ["-t", _num(duracao, 3)]
    args += ["-i", str(entrada), "-vf", cadeia, "-threads", "2"]
    if imagem:
        args += ["-frames:v", "1", "-update", "1", "-an"]
    else:
        # encode da casa (o mesmo de video.args_encode): H.264 yuv420p marcado bt709, fps da FONTE preservado em forma
        # racional (o tratamento não muda a cadência; conformar fps é trabalho da montagem)
        try:
            fps = fps_racional(info["fps"]) if info.get("fps") and info["fps"] not in ("0/0", "0") else None
        except DAErro:
            fps = None
        args += ["-c:v", "libx264", "-preset", "medium", "-crf", str(int(crf)), "-pix_fmt", "yuv420p",
                 "-x264-params", "colorprim=bt709:transfer=bt709:colormatrix=bt709:range=tv", "-color_range", "tv"]
        if fps:
            args += ["-r", f"{fps.numerator}/{fps.denominator}", "-video_track_timescale", str(fps.numerator)]
        args += ["-c:a", "copy", "-movflags", "+faststart"]
    args.append(str(tmp))
    try:
        _rodar_ffmpeg(args, f"grade {entrada.name}")
        os.replace(tmp, saida)                               # só vira a saída com código 0
    finally:
        if tmp.exists():
            tmp.unlink()
    formato = next((n for n, f in d["formatos"].items()
                    if isinstance(f, dict) and f.get("largura") == L and f.get("altura") == A), f"{L}x{A}")
    carimbo = carimbar(saida, "da.py grade", formato,
                       {"entrada": entrada.name, "parte": parte, "inicio": inicio, "duracao": duracao, "cadeia": cadeia},
                       "n/a", da=d, insumos=[entrada])     # D14: tratar uma peça carimbada leva a DA e a auditoria dela junto
    return {"saida": saida, "cadeia": cadeia, "carimbo": carimbo}


# ───────────────────────────────────────────── extrair (análise de referências) ──
def _np_lab(rgb):
    """Array (N, 3) uint8 sRGB → (N, 3) float CIELAB (D65)."""
    import numpy as np
    c = rgb.astype(np.float64) / 255.0
    lin = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    m = np.array([[0.4124564, 0.3575761, 0.1804375], [0.2126729, 0.7151522, 0.0721750], [0.0193339, 0.1191920, 0.9503041]])
    xyz = lin @ m.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[:, 1] - 16, 500 * (f[:, 0] - f[:, 1]), 200 * (f[:, 1] - f[:, 2])], axis=1)


def _paleta_kmeans(rgb, k: int, semente: int = 7, minimo: int = 6) -> list[dict]:
    """Paleta dominante por k-means em CIELAB (k-means++ com semente fixa → resultado reprodutível).
    Funde grupos quase iguais (ΔE < 7) sem descer abaixo de `minimo`. Ordena por área."""
    import numpy as np
    rng = np.random.default_rng(semente)
    if len(rgb) > 60000:
        rgb = rgb[rng.choice(len(rgb), 60000, replace=False)]
    lab = _np_lab(rgb)
    n = len(lab)
    k = max(1, min(k, n))
    centros = [lab[rng.integers(n)]]
    d2 = ((lab - centros[0]) ** 2).sum(1)
    while len(centros) < k and d2.sum() > 1e-9:
        idx = rng.choice(n, p=d2 / d2.sum())
        centros.append(lab[idx])
        d2 = np.minimum(d2, ((lab - lab[idx]) ** 2).sum(1))
    C = np.array(centros)
    rot = np.zeros(n, dtype=int)
    for _ in range(30):
        rot = ((lab[:, None, :] - C[None, :, :]) ** 2).sum(-1).argmin(1)
        novo = np.array([lab[rot == j].mean(0) if np.any(rot == j) else C[j] for j in range(len(C))])
        if np.allclose(novo, C, atol=0.05):
            break
        C = novo
    grupos = []
    for j in range(len(C)):
        membros = rot == j
        if membros.any():
            grupos.append({"lab": lab[membros].mean(0), "rgb": rgb[membros].astype(np.float64).mean(0), "n": int(membros.sum())})
    while len(grupos) > minimo:                              # funde o par mais parecido, se for parecido demais
        melhor = None
        for a in range(len(grupos)):
            for b in range(a + 1, len(grupos)):
                d = float(np.linalg.norm(grupos[a]["lab"] - grupos[b]["lab"]))
                if melhor is None or d < melhor[0]:
                    melhor = (d, a, b)
        if melhor is None or melhor[0] >= 7:
            break
        _, a, b = melhor
        ga, gb = grupos[a], grupos.pop(b)
        tot = ga["n"] + gb["n"]
        ga["lab"] = (ga["lab"] * ga["n"] + gb["lab"] * gb["n"]) / tot
        ga["rgb"] = (ga["rgb"] * ga["n"] + gb["rgb"] * gb["n"]) / tot
        ga["n"] = tot
    grupos.sort(key=lambda g: -g["n"])
    return [{"hex": rgb_para_hex(*g["rgb"]), "area": round(g["n"] / n, 4),
             "lab": [round(float(x), 1) for x in g["lab"]],
             "croma": round(float(math.hypot(g["lab"][1], g["lab"][2])), 1)} for g in grupos]


def _estatisticas(rgb) -> dict:
    import numpy as np
    lab = _np_lab(rgb)
    L = lab[:, 0]
    f = rgb.astype(np.float64)
    mx, mn = f.max(1), f.min(1)
    claros = mx >= 0.12 * 255
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-9), 0.0)
    sat_validos = sat[claros] if claros.any() else sat
    b_medio, a_medio = float(lab[:, 2].mean()), float(lab[:, 1].mean())
    return {
        "luminancia_media": round(float(L.mean()), 1),
        "luminancia_p5": round(float(np.percentile(L, 5)), 1),
        "luminancia_p95": round(float(np.percentile(L, 95)), 1),
        "contraste_p5_p95": round(float(np.percentile(L, 95) - np.percentile(L, 5)), 1),
        "saturacao_media": round(float(sat_validos.mean()), 3),
        "saturacao_p90": round(float(np.percentile(sat_validos, 90)), 3),
        "croma_media": round(float(np.hypot(lab[:, 1], lab[:, 2]).mean()), 1),
        "temperatura": {"b_medio": round(b_medio, 1), "a_medio": round(a_medio, 1),
                        "rotulo": "quente" if b_medio > 4 else "fria" if b_medio < -4 else "neutra"},
    }


def _estimar_grao(cinza) -> dict:
    """Energia de alta frequência em áreas lisas de um recorte em resolução nativa (σ em níveis de 0–255)."""
    import numpy as np
    g = cinza.astype(np.float64)
    if g.shape[0] < 16 or g.shape[1] < 16:
        return _grao_de_sigma(None)
    p = np.pad(g, 1, mode="edge")
    media = sum(p[i:i + g.shape[0], j:j + g.shape[1]] for i in range(3) for j in range(3)) / 9.0
    residuo = g - media
    gx, gy = np.abs(np.diff(media, axis=1, prepend=media[:, :1])), np.abs(np.diff(media, axis=0, prepend=media[:1, :]))
    borda = gx + gy
    lisas = borda <= np.percentile(borda, 40)
    r = residuo[lisas]
    return _grao_de_sigma(float(1.4826 * np.median(np.abs(r - np.median(r))) / 0.943) if r.size else 0.0)


def _grao_de_sigma(sigma: float | None) -> dict:
    """σ do ruído → rótulo + intensidade equivalente do filtro noise (uniforme: σ ≈ 0,29 × força)."""
    if sigma is None:
        return {"sigma": None, "rotulo": "indeterminado", "intensidade_sugerida": None}
    rotulo = "limpo" if sigma < 0.8 else "leve" if sigma < 2.2 else "médio" if sigma < 4.5 else "forte"
    return {"sigma": round(sigma, 2), "rotulo": rotulo, "intensidade_sugerida": int(max(0, min(30, round(3.5 * sigma))))}


CROMA_DE_ACENTO = 45.0        # croma CIELAB a partir do qual uma cor é "viva" (pele e madeira ficam em 20–38)


def _acentos(rgb, maximo: int = 4, area_minima: float = 0.003) -> list[dict]:
    """Cores de ACENTO: vivas (croma ≥ CROMA_DE_ACENTO) mesmo ocupando pouca área — o amarelo do marca-texto, o vermelho
    do selo. A paleta por área não as vê (0,7 % da imagem some no k-means). Agrupa os pixels vivos por família de matiz
    (30°) e, de cada família, devolve a cor dos pixels MAIS puros (terço de cima do croma): a borda suavizada, que é
    mistura com o fundo, fica de fora. Família com menos de 0,3 % da área é ruído (um objeto ao fundo do footage).
    [{'hex', 'area', 'croma', 'matiz'}], da maior presença (área × croma) para a menor."""
    import numpy as np
    lab = _np_lab(rgb)
    croma = np.hypot(lab[:, 1], lab[:, 2])
    vivos = croma >= CROMA_DE_ACENTO
    n = len(rgb)
    if not vivos.any():
        return []
    matiz = (np.degrees(np.arctan2(lab[:, 2], lab[:, 1])) % 360)[vivos]
    cr, cores = croma[vivos], rgb[vivos].astype(np.float64)
    familias = ((matiz + 15) // 30).astype(int) % 12
    saida = []
    for f in np.unique(familias):
        m = familias == f
        area = float(m.sum()) / n
        if area < area_minima:
            continue
        corte = np.percentile(cr[m], 67)
        puros = cores[m][cr[m] >= corte]
        cor_rgb = np.median(puros, axis=0)
        saida.append({"hex": rgb_para_hex(*cor_rgb), "area": round(area, 5), "croma": round(float(np.median(cr[m][cr[m] >= corte])), 1),
                      "matiz": int(f) * 30})
    saida.sort(key=lambda c: -c["area"] * c["croma"])
    fundidos: list[dict] = []
    for c in saida:                                           # famílias vizinhas da mesma cor (laranja/amarelo): fica a mais presente
        if all(delta_e(c["hex"], o["hex"]) >= 18 for o in fundidos):
            fundidos.append(c)
    return fundidos[:maximo]


def _candidatos(paleta: list[dict], acentos: list[dict] | None = None) -> dict:
    """Sugere fundo, superfície, texto, primária e secundária a partir da paleta dominante e dos acentos.
    A primária é o acento mais presente (cor viva, mesmo de área pequena); sem acento nenhum, a cor mais viva da paleta
    por área — com o aviso de que pode ser pele ou madeira. O contraste com o fundo é informado, nunca usado como filtro."""
    if not paleta:
        return {}
    extremos = [c for c in paleta if (c["lab"][0] < 28 or c["lab"][0] > 78) and c["area"] >= 0.12]
    fundo = max(extremos or paleta, key=lambda c: c["area"])
    escuro = fundo["lab"][0] < 50
    outros = [c for c in paleta if c is not fundo]
    neutras = [c for c in outros if c["croma"] <= 18]          # texto pede cor quase neutra e contraste alto
    texto = max(neutras, key=lambda c: contraste(c["hex"], fundo["hex"]), default=None)
    derivado = False
    if texto is None or contraste(texto["hex"], fundo["hex"]) < 7:
        texto, derivado = {"hex": "#F4F4F2" if escuro else "#141414"}, True       # da-livre: neutro PROPOSTO pela análise, antes de existir DA
    vivos = [c for c in outros if c["croma"] >= 22]
    ordenar = lambda c: c["croma"] * math.sqrt(max(c["area"], 1e-4))       # noqa: E731
    acentos = list(acentos or [])
    de_acento = bool(acentos)
    primaria = acentos[0] if de_acento else max(vivos or outros or [fundo], key=ordenar)

    def matiz(c):
        if "matiz" in c:
            return float(c["matiz"])
        return math.degrees(math.atan2(c["lab"][2], c["lab"][1])) % 360
    restantes = [c for c in (acentos[1:] if de_acento else (vivos or outros)) if c is not primaria
                 and min(abs(matiz(c) - matiz(primaria)), 360 - abs(matiz(c) - matiz(primaria))) >= 40]
    secundaria = max(restantes, key=ordenar, default=None)
    vizinhos = [c for c in outros if abs(c["lab"][0] - fundo["lab"][0]) < 18 and c["croma"] < 25 and c is not primaria]
    superficie = max(vizinhos, key=lambda c: c["area"], default=None)
    saida = {
        "fundo": {"hex": fundo["hex"], "motivo": f"cor {'escura' if escuro else 'clara'} dominante ({_ptbr(fundo['area'] * 100, 0)}% da área)"},
        "texto": {"hex": texto["hex"], "motivo": ("neutro derivado (a paleta não tem cor quase neutra com contraste ≥ 7:1)" if derivado
                                                    else f"maior contraste com o fundo ({_ptbr(contraste(texto['hex'], fundo['hex']), 1)}:1)")},
    }
    c_prim = contraste(primaria["hex"], fundo["hex"])
    nota_contraste = (f"contraste {_ptbr(c_prim, 1)}:1 com o fundo" + ("" if c_prim >= 4.5 else " — serve a bloco, tarja e traço; "
                      "para carregar texto sobre o fundo, precisa de ≥ 4,5:1" if c_prim >= 3 else " — baixo: use em blocos chapados com texto por cima, não como cor de texto"))
    if de_acento:
        saida["primaria"] = {"hex": primaria["hex"], "motivo": f"acento: a cor viva mais presente (croma {_ptbr(primaria['croma'], 0)}, "
                                                              f"{_ptbr(primaria['area'] * 100, 2)}% da área; {nota_contraste})"}
    else:
        saida["primaria"] = {"hex": primaria["hex"], "motivo": f"NENHUMA cor de acento nas referências (croma ≥ {_ptbr(CROMA_DE_ACENTO, 0)}); esta é só a mais viva "
                                                              f"por área (croma {_ptbr(primaria['croma'], 0)}; {nota_contraste}) e pode ser pele, madeira "
                                                              f"ou luz ambiente — defina a primária pelo briefing ou por uma referência de design"}
    if secundaria:
        saida["secundaria"] = {"hex": secundaria["hex"], "motivo": "segunda cor viva, de matiz diferente da primária"}
    if superficie:
        saida["superficie"] = {"hex": superficie["hex"], "motivo": "tom vizinho do fundo, para planos e caixas"}
    return saida


def _amostrar_video(arquivo: Path, quadros: int, pasta_tmp: Path) -> list[tuple[Path, Path]]:
    """Extrai `quadros` quadros reduzidos (320 px de largura) + um recorte central em resolução
    nativa (para medir grão). Um ffmpeg leve por quadro, todos sob a mesma trava."""
    info = sondar(arquivo)
    dur = info["duracao"]
    tempos = [dur * (i + 0.5) / quadros for i in range(quadros)] if dur > 0 else [0.0]
    pares = []
    with trava.Trava(rotulo=f"extrair {arquivo.name}"):
        for i, t in enumerate(tempos):
            mini, corte = pasta_tmp / f"{arquivo.stem}_{i:02d}_m.png", pasta_tmp / f"{arquivo.stem}_{i:02d}_c.png"
            r = trava.rodar([_bin("ffmpeg"), "-hide_banner", "-v", "error", "-nostdin", "-y", "-ss", f"{t:.3f}",
                             "-i", str(arquivo), "-threads", "2", "-filter_complex",
                             "[0:v]split[a][b];[a]scale=320:-2:flags=area[s];[b]crop='min(iw,256)':'min(ih,256)'[c]",
                             "-map", "[s]", "-frames:v", "1", "-update", "1", str(mini),
                             "-map", "[c]", "-frames:v", "1", "-update", "1", str(corte)],
                            rotulo=f"extrair {arquivo.name}", capturar=True, inatividade=trava.inatividade_padrao(60.0))
            if r.returncode == 0 and mini.is_file():
                pares.append((mini, corte))
    if not pares:
        raise DAErro(f"não consegui extrair quadros de {arquivo} (ffmpeg falhou)")
    return pares


SAIDAS_DO_EXTRAIR = ("referencias_folha.png", "referencias_analise.json")


def e_saida_do_extrair(caminho) -> bool:
    """True para a folha e a análise que o próprio `extrair` grava (não são referência; `extrair` e a prancha as ignoram)."""
    return Path(str(caminho)).name.lower() in SAIDAS_DO_EXTRAIR


def _regiao(texto_ou_tupla) -> tuple[float, float, float, float] | None:
    """'x,y,l,a' em frações do quadro (0–1) → (x, y, l, a) conferido; None se não foi pedida."""
    if texto_ou_tupla in (None, ""):
        return None
    try:
        partes = [float(str(v).replace(",", ".")) for v in (re.split(r"[;,\s]+", texto_ou_tupla.strip()) if isinstance(texto_ou_tupla, str) else texto_ou_tupla)]
    except ValueError:
        partes = []
    if len(partes) != 4 or not all(0 <= v <= 1 for v in partes) or partes[2] <= 0 or partes[3] <= 0 or partes[0] + partes[2] > 1.0001 or partes[1] + partes[3] > 1.0001:
        raise DAErro(f"--regiao {texto_ou_tupla!r}: use x,y,largura,altura em frações do quadro (ex.: 0.1,0.6,0.3,0.2 = a faixa do marca-texto).",
                     codigo=SAIDA_USO)
    return tuple(partes)


def extrair(referencias, saida=None, quadros: int = 6, cores: int = 8, regiao=None) -> dict:
    """Analisa imagens e vídeos de referência: paleta dominante (k-means), ACENTOS (cores vivas de área pequena),
    luminância, contraste, saturação, temperatura e grão; sugere candidatos a fundo/texto/primária.
    Grava <saida>/referencias_analise.json e <saida>/referencias_folha.png. Devolve o dict da análise
    (`ignoradas` lista as saídas do próprio extrair que vieram na lista — o glob `da/referencias/*.png` da segunda
    execução traz a folha de volta — e foram deixadas de fora). `cores` de 6 a 8; `quadros` de 1 a 24.
    Uma PASTA na lista vale pelas imagens e vídeos dentro dela. `regiao` = (x, y, largura, altura) em frações do quadro
    (ou o texto 'x,y,l,a'): analisa só esse recorte de cada referência — para amostrar a cor de um detalhe."""
    try:
        import numpy as np
        from PIL import Image, ImageOps
    except ImportError as e:
        raise DAErro(f"o comando extrair precisa de numpy e Pillow ({e})")
    regiao = _regiao(regiao)
    refs, proprias = [], []
    entrada = []
    for r in (Path(str(r)).expanduser() for r in referencias):
        if r.is_dir():                                   # pasta: tudo o que é imagem ou vídeo dentro dela (sem intermediários)
            dentro = sorted(a for a in r.iterdir() if a.is_file() and a.suffix.lower() in EXT_VIDEO | EXT_IMAGEM
                            and not a.name.startswith((".", PREFIXO_INTERMEDIARIO)))
            if not dentro:
                raise DAErro(f"a pasta {r} não tem imagem nem vídeo de referência.")
            entrada += dentro
        else:
            entrada.append(r)
    for r in entrada:
        # a folha e a análise que este comando grava ficam na mesma pasta das referências: o glob da 2ª execução
        # (`da/referencias/*.png`) as traria de volta como referência e o fundo da folha dominaria a paleta
        (proprias if e_saida_do_extrair(r) else refs).append(r)
    if not refs:
        if proprias:
            raise DAErro(f"só recebi saídas do próprio extrair ({', '.join(p.name for p in proprias)}): elas não são referência.",
                         dica="Passe as imagens/vídeos de referência (ex.: da/referencias/ref*.png).")
        raise DAErro("informe ao menos uma imagem ou vídeo de referência")
    for r in refs:
        if not r.is_file():
            raise DAErro(f"referência não encontrada: {r}")
        if r.suffix.lower() not in EXT_VIDEO | EXT_IMAGEM:
            raise DAErro(f"{r.name}: extensão não suportada; use imagem ({', '.join(sorted(EXT_IMAGEM))}) "
                         f"ou vídeo ({', '.join(sorted(EXT_VIDEO))})")
    if not (6 <= int(cores) <= 8):
        raise DAErro(f"--cores {cores}: a paleta do conjunto tem de 6 a 8 cores (menos não separa fundo/texto/acento; "
                     f"mais vira ruído).", codigo=SAIDA_USO)
    if not (1 <= int(quadros) <= 24):
        raise DAErro(f"--quadros {quadros}: use de 1 a 24 quadros por vídeo.", codigo=SAIDA_USO)
    cores, quadros = int(cores), int(quadros)
    if saida is None:
        da_json = achar(obrigatorio=False)
        saida = (da_json.parent / "referencias") if da_json else Path.cwd() / "referencias_analise"
    saida = Path(str(saida)).expanduser()
    saida.mkdir(parents=True, exist_ok=True)
    itens, todos_px, todos_finos = [], [], []
    with tempfile.TemporaryDirectory(prefix="da-extrair-") as tmp:
        for ref in refs:
            video = ref.suffix.lower() in EXT_VIDEO
            if video:
                pares = _amostrar_video(ref, quadros, Path(tmp))
                minis = [Image.open(m).convert("RGB") for m, _ in pares]
                cortes = [Image.open(c).convert("L") for _, c in pares if c.is_file()]
                dims = sondar(ref)
                larg, alt = dims["largura"], dims["altura"]
            else:
                try:
                    img = ImageOps.exif_transpose(Image.open(ref)).convert("RGB")
                except OSError as e:
                    raise DAErro(f"não consegui abrir a imagem {ref}: {e}")
                larg, alt = img.size
                mini = img.copy()
                mini.thumbnail((320, 320), Image.LANCZOS)
                minis = [mini]
                lado = min(256, larg, alt)
                x0, y0 = (larg - lado) // 2, (alt - lado) // 2
                cortes = [img.crop((x0, y0, x0 + lado, y0 + lado)).convert("L")]
            if regiao:
                def recortar(im):
                    x0, y0 = round(regiao[0] * im.width), round(regiao[1] * im.height)
                    return im.crop((x0, y0, max(x0 + 1, round((regiao[0] + regiao[2]) * im.width)), max(y0 + 1, round((regiao[1] + regiao[3]) * im.height))))
                minis = [recortar(m) for m in minis]
            pixels = []
            for m in minis:
                a = m.copy()
                a.thumbnail((160, 160), Image.BILINEAR)
                pixels.append(np.asarray(a, dtype=np.uint8).reshape(-1, 3))
            px = np.concatenate(pixels)
            px_finos = np.concatenate([np.asarray(m, dtype=np.uint8).reshape(-1, 3) for m in minis])   # 320 px: acento fino não some
            graos = [g for g in (_estimar_grao(np.asarray(c)) for c in cortes) if g["sigma"] is not None]
            grao = _grao_de_sigma(float(np.median([g["sigma"] for g in graos])) if graos else None)
            item = {"arquivo": str(ref), "tipo": "video" if video else "imagem", "largura": larg, "altura": alt,
                    "quadros": len(minis), "paleta": _paleta_kmeans(px, 5, minimo=4), "acentos": _acentos(px_finos), **_estatisticas(px), "grao": grao}
            itens.append((item, minis))
            rng = np.random.default_rng(11)
            todos_px.append(px if len(px) <= 20000 else px[rng.choice(len(px), 20000, replace=False)])
            todos_finos.append(px_finos if len(px_finos) <= 120000 else px_finos[rng.choice(len(px_finos), 120000, replace=False)])
        geral_px = np.concatenate(todos_px)
        acentos = _acentos(np.concatenate(todos_finos))
        paleta = _paleta_kmeans(geral_px, cores, minimo=6)
        est = _estatisticas(geral_px)
        sigmas = [i["grao"]["sigma"] for i, _ in itens if i["grao"]["sigma"] is not None]
        grao_geral = _grao_de_sigma(float(np.median(sigmas)) if sigmas else None)
        cand = _candidatos(paleta, acentos)
        for c in paleta + acentos:
            if cand.get("fundo"):
                c["contraste_com_fundo"] = round(contraste(c["hex"], cand["fundo"]["hex"]), 2)
        L = est["luminancia_media"]
        leitura = [
            f"Imagem {'escura' if L < 35 else 'clara' if L > 65 else 'de luminosidade média'} (L* médio {_ptbr(L, 0)} de 100).",
            f"Contraste {'baixo' if est['contraste_p5_p95'] < 45 else 'alto' if est['contraste_p5_p95'] > 75 else 'médio'} "
            f"(L* de {_ptbr(est['luminancia_p5'], 0)} a {_ptbr(est['luminancia_p95'], 0)} entre os percentis 5 e 95).",
            f"{'Dessaturada' if est['saturacao_media'] < 0.22 else 'Muito saturada' if est['saturacao_media'] > 0.5 else 'Saturação moderada'} "
            f"(média {_ptbr(est['saturacao_media'])}; p90 {_ptbr(est['saturacao_p90'])}).",
            f"Temperatura {est['temperatura']['rotulo']} (b* médio {_ptbr(est['temperatura']['b_medio'], 1)}).",
        ]
        if grao_geral["sigma"] is not None:
            leitura.append(f"Grão {grao_geral['rotulo']} (desvio do ruído ≈ {_ptbr(grao_geral['sigma'])} em 255); "
                           f"equivale a tratamento.grao.intensidade ≈ {grao_geral['intensidade_sugerida']}.")
        if acentos:
            leitura.append("Acentos (cores vivas, mesmo em área pequena): "
                           + ", ".join(f"{a['hex']} ({_ptbr(a['area'] * 100, 2)}% da área, croma {_ptbr(a['croma'], 0)})" for a in acentos) + ".")
        else:
            leitura.append(f"Nenhuma cor de acento (croma ≥ {_ptbr(CROMA_DE_ACENTO, 0)}) nas referências: a cor de assinatura vem do briefing.")
        analise = {
            "gerado_em": agora_iso(), "kit_versao": KIT_VERSAO,
            "nota": "Insumo para propor tokens da DA; nada aqui é aplicado sozinho. Paleta por k-means em CIELAB (semente fixa).",
            "ignoradas": [str(p) for p in proprias],
            "regiao": list(regiao) if regiao else None,
            "referencias": [i for i, _ in itens],
            "geral": {"paleta": paleta, "acentos": acentos, **est, "grao": grao_geral, "candidatos": cand, "leitura": leitura},
        }
        arq_json = gravar_json(saida / "referencias_analise.json", analise)
        arq_png = _folha_referencias(itens, analise, saida / "referencias_folha.png")
    analise["_arquivos"] = {"json": str(arq_json), "folha": str(arq_png)}
    return analise


def _folha_referencias(itens: list, analise: dict, destino: Path) -> Path:
    """Folha PNG: miniaturas de cada referência + amostras de cor rotuladas com hex."""
    from PIL import Image, ImageDraw, ImageFont

    def fonte(tam: int, negrito: bool = False):
        # da-livre:inicio — folha de análise das referências: existe ANTES da DA (e sem projeto), por isso tem fonte e cores próprias
        for nome in (("IBMPlexMono-Bold.ttf",) if negrito else ()) + ("IBMPlexMono-Medium.ttf", "IBMPlexMono-Regular.ttf"):
            try:
                return ImageFont.truetype(str(KIT / "fontes" / nome), tam)
            except OSError:
                continue
        return ImageFont.load_default()
        # da-livre:fim

    # folha de análise: cores próprias de ferramenta (não é peça do projeto)
    FUNDO, TEXTO, SUAVE, LINHA = (20, 20, 20), (236, 236, 232), (150, 150, 146), (58, 58, 58)   # da-livre: idem
    W, M = 1600, 44
    f_tit, f_txt, f_peq, f_hex = fonte(34, True), fonte(20), fonte(16), fonte(18, True)
    alt_ref = 236
    geral = analise["geral"]
    H = M + 70 + len(itens) * alt_ref + 330 + (150 if geral.get("acentos") else 0) + (130 if geral.get("candidatos") else 0) + 30 * len(geral["leitura"]) + M
    img = Image.new("RGB", (W, H), FUNDO)
    d = ImageDraw.Draw(img)
    d.text((M, M), "Referências — análise de cor", font=f_tit, fill=TEXTO)
    d.text((M, M + 44), f"{len(itens)} referência(s) · {analise['gerado_em']} · kit {KIT_VERSAO}", font=f_peq, fill=SUAVE)
    y = M + 86

    def amostra(x, y0, larg, alt, cor_hex, linhas):
        rgb = hex_para_rgb(cor_hex)
        d.rectangle([x, y0, x + larg, y0 + alt], fill=rgb, outline=LINHA)
        for i, (txt, f, cor) in enumerate(linhas):
            d.text((x, y0 + alt + 6 + i * 20), txt, font=f, fill=cor)

    for item, minis in itens:
        d.line([(M, y - 10), (W - M, y - 10)], fill=LINHA, width=1)
        x = M
        mostrar = minis[:6]
        larg_mini = min(250, int((0.5 * (W - 2 * M) - 10 * (len(mostrar) - 1)) / max(1, len(mostrar))))   # as miniaturas ocupam meia folha
        for mini in mostrar:
            m = mini.copy()
            m.thumbnail((larg_mini, 150), Image.LANCZOS)
            img.paste(m, (x, y + 30))
            x += m.width + 10
        d.text((M, y), f"{Path(item['arquivo']).name}  ·  {item['tipo']} {item['largura']}×{item['altura']}"
                       + (f"  ·  {item['quadros']} quadros" if item["tipo"] == "video" else ""), font=f_txt, fill=TEXTO)
        px = M + int(0.52 * (W - 2 * M))                       # a paleta começa sempre na metade direita: nunca passa da borda
        for i, c in enumerate(item["paleta"][:5]):
            amostra(px + i * 108, y + 30, 96, 84, c["hex"], [(c["hex"], f_peq, TEXTO), (f"{_ptbr(c['area'] * 100, 0)}%", f_peq, SUAVE)])
        g = item["grao"]
        d.text((px, y + 172), f"L* {_ptbr(item['luminancia_media'], 0)} · contraste {_ptbr(item['contraste_p5_p95'], 0)} · "
                              f"sat {_ptbr(item['saturacao_media'])} · {item['temperatura']['rotulo']} · grão {g['rotulo']}",
               font=f_peq, fill=SUAVE)
        y += alt_ref
    d.line([(M, y - 10), (W - M, y - 10)], fill=LINHA, width=1)
    d.text((M, y), "Paleta dominante do conjunto", font=f_txt, fill=TEXTO)
    n = max(1, len(geral["paleta"]))
    larg = min(180, (W - 2 * M - (n - 1) * 12) // n)
    for i, c in enumerate(geral["paleta"]):
        amostra(M + i * (larg + 12), y + 36, larg, 150, c["hex"],
                [(c["hex"], f_hex, TEXTO), (f"{_ptbr(c['area'] * 100, 1)}% da área", f_peq, SUAVE),
                 (f"L* {_ptbr(c['lab'][0], 0)} · croma {_ptbr(c['croma'], 0)}", f_peq, SUAVE)])
    y += 290
    if geral.get("acentos"):
        d.text((M, y), "Acentos — cores vivas, mesmo em área pequena (é daqui que sai a primária)", font=f_txt, fill=TEXTO)
        for i, c in enumerate(geral["acentos"]):
            amostra(M + i * 260, y + 34, 120, 56, c["hex"], [])
            d.text((M + i * 260 + 132, y + 36), c["hex"], font=f_hex, fill=TEXTO)
            d.text((M + i * 260 + 132, y + 60), f"{_ptbr(c['area'] * 100, 2)}% · croma {_ptbr(c['croma'], 0)}", font=f_peq, fill=SUAVE)
        y += 150
    cand = geral.get("candidatos") or {}
    if cand:
        d.text((M, y), "Candidatos a token (proposta, não regra)", font=f_txt, fill=TEXTO)
        for i, (nome, c) in enumerate(cand.items()):
            amostra(M + i * 300, y + 34, 120, 56, c["hex"], [])
            d.text((M + i * 300 + 132, y + 36), nome, font=f_hex, fill=TEXTO)
            d.text((M + i * 300 + 132, y + 60), c["hex"], font=f_peq, fill=SUAVE)
        y += 130
    for linha in geral["leitura"]:
        d.text((M, y), "· " + linha, font=f_peq, fill=SUAVE)
        y += 30
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_name(f"{destino.stem}.parcial{destino.suffix}")
    img.save(tmp, "PNG", optimize=True)
    os.replace(tmp, destino)
    return destino


# ──────────────────────────────────────────────────────────────────── CLI ──
def _com_cor() -> bool:
    return sys.stdout.isatty() and not os.environ.get("NO_COLOR")


def _amostra_ansi(hexa: str) -> str:
    if not _com_cor():
        return ""
    r, g, b = hex_para_rgb(hexa)
    return f"\x1b[48;2;{r};{g};{b}m    \x1b[0m "


def _diz(*partes, erro: bool = False) -> None:
    print(*partes, file=sys.stderr if erro else sys.stdout)


def _imprimir_validacao(erros: list[str], avisos: list[str], cabecalho: str = "", erro: bool = False) -> None:
    if cabecalho:
        _diz(cabecalho, erro=erro)
    if erros:
        _diz(f"ERROS ({len(erros)})", erro=erro)
        for e in erros:
            _diz(f"  ✗ {e}", erro=erro)
    if avisos:
        _diz(f"AVISOS ({len(avisos)})", erro=erro)
        for a in avisos:
            _diz(f"  ! {a}", erro=erro)
    if not erros and not avisos:
        _diz("Sem erros nem avisos.", erro=erro)
    elif not erros:
        _diz("Sem erros.", erro=erro)


def texto_mostrar(d: DA) -> str:
    """Resumo da DA para o terminal."""
    m, cor, tip, mov, t, leg = d.meta, d["cor"], d["tipografia"], d["movimento"], d["tratamento"], d["legenda"]
    if d.aprovada:
        estado = f"aprovada em {m.get('aprovada_em')}"
    elif m["aprovada"]:
        estado = "ALTERADA DEPOIS DA APROVAÇÃO (rode revisar + aprovar)"
    else:
        estado = "não aprovada"
    L = [f"DA  {m['nome']}  ·  revisão {m['revisao']}  ·  {estado}",
         f"    {m['da_json']}",
         f"    sha256 {m['sha256']}" + (f"  ·  base {d['projeto'].get('base')}" if d["projeto"].get("base") else "")
         + (f"  ·  herda {d.get('herda')}" if d.get("herda") else ""),
         "", f"Conceito   {d['conceito']['frase']}"]
    if d["conceito"]["palavras_chave"]:
        L.append(f"           {', '.join(d['conceito']['palavras_chave'])}")
    L += ["", "Paleta"]
    for k, h in cor["paleta"].items():
        c = "" if k == "fundo" else f"  contraste c/ fundo {_ptbr(contraste(h, cor['paleta']['fundo']), 1)}:1"
        L.append(f"  {_amostra_ansi(h)}{k:<12} {h}{c}")
    L.append("  dados      " + " ".join(f"{_amostra_ansi(h)}{h}" for h in cor["dados"]))
    L.append("  neutros    " + (" ".join(f"{_amostra_ansi(h)}{h}" for h in cor["neutros"]) or "—"))
    L += ["", "Tipografia"]
    for nome, p in tip["papeis"].items():
        extra = []
        if p.get("largura") is not None:
            extra.append(f"largura {_num(p['largura'])}%")
        if abs(p.get("escala_x", 1) - 1) > 1e-9:
            extra.append(f"escala_x {_ptbr(p['escala_x'])}")
        if p["caixa"] == "alta":
            extra.append("CAIXA ALTA")
        L.append(f"  {nome:<10} {p['familia']} {p['peso']}" + (f"  ({', '.join(extra)})" if extra else "")
                 + f"  ·  {Path(p['arquivo']).name if p.get('arquivo') else 'fonte do sistema'}")
    L.append("  escala     " + "  ".join(f"{n} {_ptbr(f, 3)}" for n, f in tip["escala"].items()))
    L += ["", "Movimento",
          f"  entrada {mov['entrada_padrao']} · saída {mov['saida_padrao']} · transição {mov['transicoes']['padrao']} "
          f"(permitidas: {', '.join(mov['transicoes']['permitidas'])})",
          "  durações   " + "  ".join(f"{n} {_ptbr(v)}s" for n, v in mov["duracoes"].items())
          + f"  ·  escalonamento {_ptbr(mov['escalonamento'])}s",
          "  curvas     " + "  ".join(f"{n} [{', '.join(_num(x) for x in c)}]" for n, c in mov["curvas"].items()),
          "", "Tratamento",
          f"  cadeia ffmpeg (horizontal): {d.grade('horizontal')}",
          f"  moldura {t['moldura']['estilo']} · recorte {t['recorte']['ancora']} · velocidade {_ptbr(t['velocidade'])}×",
          "", "Legenda",
          f"  {leg['estilo']} · papel {leg['papel']} · tamanho {_ptbr(leg['tamanho'], 3)} · caixa {leg['caixa']} · "
          f"cor {leg['cor_hex']} · destaque {leg['cor_destaque_hex']} · animação {leg['animacao']}",
          f"  até {leg['max_linhas']} linha(s) × {leg['max_palavras']} palavra(s) · "
          + " · ".join(f"y {n} {_ptbr(p['y'], 3)}" for n, p in leg["posicao"].items()),
          "", "Formatos"]
    for nome, f in d["formatos"].items():
        if isinstance(f, dict) and "largura" in f:
            L.append(f"  {nome:<11} {f['largura']}×{f['altura']}" + (f"  {f['fps']} fps" if f.get("fps") else ""))
    L += ["", f"Build      {m['build']}", f"Leitura    {Path(m['pasta_da']) / 'DA.md'}"]
    return "\n".join(L)


# -- registro de subcomandos (ponto de extensão) ------------------------------
_SUBCOMANDOS: dict[str, dict] = {}


def registrar_subcomando(nome: str, ajuda: str, configurar=None, executar=None, descricao: str | None = None,
                         repasse: bool = False) -> None:
    """Acrescenta um subcomando à CLI.

    configurar(parser): recebe o argparse do subcomando para declarar argumentos (opcional).
    executar(args) -> int: roda o comando e devolve o código de saída (0 = ok).
    repasse=True: o subcomando repassa argumentos a outro programa (positional `argumentos` com nargs="...");
    opções desconhecidas (`--cena titulo …`) vão para args.argumentos em vez de dar erro de uso, sem exigir `--`.
    Toda extensão ganha de graça --da e --de (args.da, args.de). Para estender sem editar este
    arquivo, crie da_ext_<nome>.py ao lado dele com `def registrar(da): da.registrar_subcomando(...)`."""
    if executar is None:
        raise DAErro(f"subcomando {nome!r}: faltou a função executar(args)")
    _SUBCOMANDOS[nome] = {"ajuda": ajuda, "configurar": configurar, "executar": executar, "descricao": descricao or ajuda,
                          "repasse": bool(repasse)}


_EXTENSOES_CARREGADAS = False


def _carregar_extensoes() -> None:
    global _EXTENSOES_CARREGADAS
    if _EXTENSOES_CARREGADAS:
        return
    _EXTENSOES_CARREGADAS = True
    este = sys.modules[__name__]
    sys.modules.setdefault("da", este)                # `import da` dentro da extensão devolve ESTE módulo
    for arq in sorted(KIT.glob("da_ext_*.py")):
        try:
            spec = importlib.util.spec_from_file_location(arq.stem, arq)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if hasattr(mod, "registrar"):
                mod.registrar(este)
        except Exception as e:                        # extensão quebrada não derruba o núcleo
            print(f"aviso: extensão {arq.name} não carregou ({type(e).__name__}: {e})", file=sys.stderr)


class _Parser(argparse.ArgumentParser):
    _TRADUCOES = [
        (r"the following arguments are required: (.*)", r"faltam argumentos obrigatórios: \1"),
        (r"unrecognized arguments: (.*)", r"argumentos não reconhecidos: \1"),
        (r"argument (.*?): invalid choice: (.*?) \(choose from (.*)\)", r"argumento \1: opção inválida \2 (escolha entre \3)"),
        (r"argument (.*?): expected one argument", r"argumento \1: faltou o valor"),
        (r"argument (.*?): expected at least one argument", r"argumento \1: faltou ao menos um valor"),
        (r"argument (.*?): invalid (?:float|int) value: (.*)", r"argumento \1: número inválido \2"),
        (r"argument (.*?): not allowed with argument (.*)", r"argumento \1: não pode ser usado junto com \2"),
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
            message = re.sub(padrao, troca, message)
        self.print_usage(sys.stderr)
        self.exit(SAIDA_USO, f"erro: {message}\n")


def _opcoes_comuns() -> argparse.ArgumentParser:
    comum = argparse.ArgumentParser(add_help=False)
    comum.add_argument("--da", metavar="CAMINHO", default=argparse.SUPPRESS,
                       help="da.json (ou pasta do projeto) a usar; vence a variável DA_JSON e a descoberta")
    comum.add_argument("--de", metavar="PASTA", default=argparse.SUPPRESS,
                       help="pasta de onde começar a procurar da/da.json (padrão: diretório atual)")
    return comum


def _alvo(args) -> dict:
    return {"caminho": getattr(args, "da", None), "de": getattr(args, "de", None)}


# -- subcomandos do núcleo ----------------------------------------------------
def _cfg_init(p):
    p.add_argument("pasta", help="pasta do projeto (criada se não existir)")
    p.add_argument("--nome", help="nome do projeto (obrigatório ao criar a DA)")
    p.add_argument("--base", metavar="PRESET", help=f"preset de partida (padrão: {PRESET_PADRAO}); veja `da.py presets`")
    p.add_argument("--herdar", action="store_true",
                   help="cria um da.json enxuto com \"herda\": <preset> em vez de copiar o preset inteiro")
    p.add_argument("--forcar", action="store_true", help="recria o da.json mesmo que já exista (o antigo vira backup)")


def _cmd_init(args) -> int:
    info = iniciar(args.pasta, nome=args.nome, base=args.base, herdar=args.herdar, forcar=args.forcar)
    raiz = info["raiz"]
    if info["criou_da"]:
        _diz(f"DA criada em {info['da_json']} (base: {info['base']})")
        if info["backup"]:
            _diz(f"  backup do da.json anterior: {info['backup'].name}")
        if info["recursos"]:
            _diz(f"  {len(info['recursos'])} arquivo(s) de fonte/recurso copiados para da/")
    else:
        _diz(f"O projeto já tem DA em {info['da_json']}: nada foi sobrescrito.")
    if info["pastas_criadas"]:
        _diz(f"  pastas criadas: {', '.join(_rel(p, raiz) for p in info['pastas_criadas'])}")
    _diz(f"  CLAUDE.md: bloco da DA {info['claude_md']}"
         + (f" (cópia do arquivo anterior: {info['backup_claude_md'].name})" if info.get("backup_claude_md") else ""))
    for a in info["avisos"]:
        _diz(f"  ! {a}")
    if info["criou_da"]:
        _diz("\nPróximos passos:")
        _diz(f"  1. Ajuste da/da.json (conceito, paleta, tipografia…) — referências em da/referencias/.")
        _diz(f"  2. {DA_CLI} validar && {DA_CLI} compilar")
        _diz(f"  3. Quando o usuário aprovar o visual: {DA_CLI} aprovar")
    return SAIDA_OK


def _cfg_achar(p):
    g = p.add_mutually_exclusive_group()
    g.add_argument("--raiz", action="store_true", help="imprime a pasta raiz do projeto em vez do da.json")
    g.add_argument("--build", action="store_true", help="imprime a pasta da/build")
    g.add_argument("--json", action="store_true", help="imprime da_json, raiz e build em JSON")


def _cmd_achar(args) -> int:
    da_json = achar(de=getattr(args, "de", None), da=getattr(args, "da", None))
    if args.raiz:
        _diz(raiz_do_projeto(da_json))
    elif args.build:
        _diz(_pasta_build(da_json))
    elif args.json:
        _diz(json.dumps({"da_json": str(da_json), "raiz": str(raiz_do_projeto(da_json)),
                         "build": str(_pasta_build(da_json))}, ensure_ascii=False))
    else:
        _diz(da_json)
    return SAIDA_OK


def _cfg_validar(p):
    p.add_argument("arquivo", nargs="?", help="da.json ou preset a validar (padrão: a DA do projeto)")
    p.add_argument("--estrito", action="store_true", help="avisos também reprovam (código 1)")
    p.add_argument("--json", action="store_true", help="saída em JSON")


def _cmd_validar(args) -> int:
    alvo = args.arquivo or getattr(args, "da", None)
    r = validar(alvo, de=getattr(args, "de", None))
    reprovada = bool(r["erros"]) or (args.estrito and bool(r["avisos"]))
    if args.json:
        _diz(json.dumps({**r, "caminho": str(r["caminho"]), "ok": not reprovada}, ensure_ascii=False, indent=2))
    else:
        estado = "aprovada" if r["aprovada"] else "não aprovada"
        _imprimir_validacao(r["erros"], r["avisos"],
                            f"DA: {r['caminho']}  (revisão {r['revisao']}, {estado}, sha256 {r['sha256'][:12]}…)")
        if r["notas"]:
            _diz(f"NOTAS ({len(r['notas'])}) — não reprovam, mas leia")
            for n in r["notas"]:
                _diz(f"  · {n}")
    return SAIDA_ERRO if reprovada else SAIDA_OK


def _cfg_compilar(p):
    p.add_argument("--se-preciso", action="store_true", help="só compila se da/build/ estiver velho")
    p.add_argument("--json", action="store_true", help="saída em JSON")


def _cmd_compilar(args) -> int:
    da_json = achar(de=getattr(args, "de", None), da=getattr(args, "da", None))
    if args.se_preciso:
        velho, motivo = precisa_compilar(da_json)
        if not velho:
            _diz(json.dumps({"compilou": False, "motivo": motivo}) if args.json else f"da/build/ está em dia ({da_json}).")
            return SAIDA_OK
    r = compilar_da(da_json)
    if args.json:
        _diz(json.dumps({"compilou": True, "da_json": str(r["da_json"]), "build": str(r["build"]), "sha256": r["sha256"],
                         "avisos": r["avisos"], "arquivos": [str(a) for a in r["arquivos"]]}, ensure_ascii=False, indent=2))
        return SAIDA_OK
    _diz(f"Compilada: {r['da_json']}  (sha256 {r['sha256'][:12]}…)")
    for a in r["arquivos"]:
        _diz(f"  → {_rel(a, raiz_do_projeto(r['da_json']))}")
    if r["avisos"]:
        _diz(f"AVISOS ({len(r['avisos'])})")
        for a in r["avisos"]:
            _diz(f"  ! {a}")
    return SAIDA_OK


def _cmd_mostrar(args) -> int:
    _diz(texto_mostrar(carregar(**_alvo(args))))
    return SAIDA_OK


def _cfg_token(p):
    p.add_argument("caminho", help="caminho pontilhado, ex.: cor.paleta.primaria, legenda.cor, cor.dados.0, tipografia.escala.h1")
    p.add_argument("--bruto", action="store_true", help="não resolve tokens de cor (imprime o valor como está no da.json)")
    p.add_argument("--formato", metavar="NOME", help="converte uma fração do lado menor em pixels desse formato (ex.: vertical)")


def _cmd_token(args) -> int:
    d = carregar(**_alvo(args))
    v = d.token(args.caminho, resolver_cores=not args.bruto)
    if args.formato:
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            raise DAErro(f"--formato só converte números (frações); {args.caminho} vale {_mostrar(v)}")
        v = d.px(v, args.formato)
    if isinstance(v, (dict, list)):
        _diz(json_bonito(v))
    elif isinstance(v, bool):
        _diz("true" if v else "false")
    elif v is None:
        _diz("null")
    else:
        _diz(v)
    return SAIDA_OK


def _cfg_presets(p):
    p.add_argument("--json", action="store_true", help="saída em JSON")


def _cmd_presets(args) -> int:
    lista = listar_presets()
    if args.json:
        _diz(json.dumps([{**p, "caminho": str(p["caminho"])} for p in lista], ensure_ascii=False, indent=2))
        return SAIDA_OK
    for origem, titulo in (("embutido", "Presets embutidos"), ("pessoal", f"Presets pessoais ({presets_pessoais_dir()})")):
        grupo = [p for p in lista if p["origem"] == origem]
        _diz(titulo)
        if not grupo:
            _diz("  (nenhum — salve um com `da.py salvar-preset <nome>`)" if origem == "pessoal" else "  (nenhum)")
        for p in grupo:
            _diz(f"  {p['nome']:<18} {p['frase']}" + ("  [ofuscado por um embutido de mesmo nome]" if p.get("ofuscado") else ""))
        _diz("")
    _diz(f"Usar: {DA_CLI} init <pasta> --nome \"…\" --base <preset>")
    return SAIDA_OK


def _cfg_salvar_preset(p):
    p.add_argument("nome", help="nome do preset (minúsculas, números e hífens)")
    p.add_argument("--forcar", action="store_true", help="substitui um preset pessoal de mesmo nome")


def _cmd_salvar_preset(args) -> int:
    r = salvar_preset(args.nome, forcar=args.forcar, **_alvo(args))
    _diz(f"Preset pessoal salvo em {r['pasta']}")
    _diz(f"  {len(r['recursos'])} arquivo(s) de fonte/LUT/textura/logo copiados")
    for n in r["notas"]:
        _diz(f"  · {n}")
    _diz(f"Usar em outro projeto: {DA_CLI} init <pasta> --nome \"…\" --base {args.nome}")
    return SAIDA_OK


def _cfg_extrair(p):
    p.add_argument("referencias", nargs="+", help="imagens e/ou vídeos de referência; uma pasta vale por tudo o que há dentro dela")
    p.add_argument("--regiao", metavar="X,Y,L,A", help="analisa só um recorte de cada referência, em frações do quadro "
                                                        "(ex.: 0.1,0.6,0.3,0.2) — para amostrar a cor de um detalhe (marca-texto, selo, fita)")
    p.add_argument("--saida", metavar="PASTA", help="onde gravar a análise (padrão: da/referencias/ do projeto, ou ./referencias_analise/)")
    p.add_argument("--quadros", type=int, default=6, help="quadros amostrados por vídeo (padrão: 6)")
    p.add_argument("--cores", type=int, default=8, help="cores da paleta do conjunto, de 6 a 8 (padrão: 8); fora disso é erro de uso")
    p.add_argument("--json", action="store_true", help="imprime a análise completa em JSON")


def _cmd_extrair(args) -> int:
    saida = args.saida
    if saida is None:
        da_json = achar(de=getattr(args, "de", None), da=getattr(args, "da", None), obrigatorio=False)
        saida = (da_json.parent / "referencias") if da_json else Path.cwd() / "referencias_analise"
    a = extrair(args.referencias, saida=saida, quadros=args.quadros, cores=args.cores, regiao=args.regiao)
    if args.json:
        _diz(json.dumps(a, ensure_ascii=False, indent=2))
        return SAIDA_OK
    g = a["geral"]
    _diz(f"Análise de {len(a['referencias'])} referência(s)"
         + (f" ({len(a['ignoradas'])} ignorada(s): saída do próprio extrair — {', '.join(Path(x).name for x in a['ignoradas'])})"
            if a.get("ignoradas") else ""))
    _diz("Paleta dominante")
    for c in g["paleta"]:
        _diz(f"  {_amostra_ansi(c['hex'])}{c['hex']}  {_ptbr(c['area'] * 100, 1):>5}%  L* {_ptbr(c['lab'][0], 0):>3}  croma {_ptbr(c['croma'], 0)}")
    if g.get("acentos"):
        _diz("Acentos (cores vivas, mesmo em área pequena)")
        for c in g["acentos"]:
            _diz(f"  {_amostra_ansi(c['hex'])}{c['hex']}  {_ptbr(c['area'] * 100, 2):>5}%  croma {_ptbr(c['croma'], 0)}")
    _diz("Leitura")
    for linha in g["leitura"]:
        _diz(f"  · {linha}")
    if g["candidatos"]:
        _diz("Candidatos a token (proposta para discutir, não regra)")
        for nome, c in g["candidatos"].items():
            _diz(f"  {_amostra_ansi(c['hex'])}{nome:<11} {c['hex']}  — {c['motivo']}")
    _diz(f"Gravado: {a['_arquivos']['json']}")
    _diz(f"         {a['_arquivos']['folha']}")
    return SAIDA_OK


APOS_APROVAR: list = []        # ganchos das extensões: fn(da_json, documentos, args) -> lista de linhas a imprimir


def _cfg_aprovar(p):
    p.add_argument("--estrito", action="store_true",
                   help="recusa (código 1) se a prancha ou o teste de movimento estiverem ausentes ou desatualizados")
    p.add_argument("--sem-prancha", action="store_true",
                   help="não regenera a prancha depois de aprovar (por padrão ela é refeita para o cabeçalho dizer APROVADA)")


def _cmd_aprovar(args) -> int:
    alvo = _alvo(args)
    docs = documentos_de_aprovacao(**alvo)
    faltas = [f"{nome}: {d['estado']} ({d['detalhe']})" for nome, d in docs.items() if d["estado"] != "em dia"]
    tem_prancha = any(docs[n]["estado"] == "em dia" for n in ("prancha.png", "prancha_vertical.png"))
    pendentes = []
    if not tem_prancha:
        pendentes.append("nenhuma prancha em dia — o que o cliente aprovou não é o que está em disco. "
                         f"Gere com `{DA_CLI} prancha` e mostre antes de aprovar")
    if docs["teste_movimento.mp4"]["estado"] != "em dia":
        pendentes.append(f"teste de movimento {docs['teste_movimento.mp4']['estado'].replace('ada', 'ado')} — curvas e durações não foram vistas nesta versão. "
                         f"Gere com `{DA_CLI} teste-movimento`")
    if getattr(args, "estrito", False) and pendentes:
        _diz("erro: a DA NÃO foi aprovada (--estrito): os documentos de aprovação não estão em dia.", erro=True)
        for f in faltas:
            _diz(f"  · {f}", erro=True)
        return SAIDA_ERRO
    r = aprovar(**alvo)
    if r["estado"] == "ja_aprovada":
        _diz(f"A DA já estava aprovada na revisão {r['revisao']} (sha256 {r['sha256'][:12]}…). Nada mudou.")
    else:
        _diz(f"DA aprovada: revisão {r['revisao']}, sha256 {r['sha256'][:12]}…")
        _diz("  da/build/ e da/DA.md recompilados. Edições no da.json a partir de agora pedem `da.py revisar`.")
    for a in r["avisos"]:
        _diz(f"  ! {a}")
    for n in r.get("notas") or []:
        _diz(f"  · nota: {n}")
    for a in pendentes:
        _diz(f"  ! {a}")
    for f in faltas:
        if f.startswith("prancha") and tem_prancha:
            _diz(f"  · {f}")
    if r["estado"] == "aprovada":
        for gancho in APOS_APROVAR:
            try:
                for linha in gancho(r["da_json"], docs, args) or []:
                    _diz(f"  {linha}")
            except Exception as e:                     # o gancho é cortesia: a aprovação já está gravada
                _diz(f"  ! depois de aprovar: {type(e).__name__}: {e}")
    return SAIDA_OK


def _cfg_remover_preset(p):
    p.add_argument("nome", help="nome do preset PESSOAL a apagar (veja `da.py presets`)")


def _cmd_remover_preset(args) -> int:
    pasta = remover_preset(args.nome)
    _diz(f"Preset pessoal removido: {pasta}")
    return SAIDA_OK


ACOES_DE_ROTA = ("criar", "listar", "comparar", "adotar")


def _cfg_rotas(p):
    p.add_argument("acao", choices=ACOES_DE_ROTA, help="criar <nome> · listar · comparar [nomes…] · adotar <nome>")
    p.add_argument("nomes", nargs="*", help="nome(s) de rota (criar e adotar: um; comparar: nenhum = todas)")
    p.add_argument("--base", metavar="PRESET|ARQ", help="criar: de onde a rota herda — preset, caminho de da.json ou 'atual' (padrão: a DA do projeto)")
    p.add_argument("--frase", help="criar: frase de conceito da rota")
    p.add_argument("--primaria", metavar="#RRGGBB", help="criar: atalho para --cor primaria=#RRGGBB")
    p.add_argument("--cor", action="append", default=[], metavar="CHAVE=#RRGGBB", help="criar: sobrescreve uma cor da paleta (pode repetir)")
    p.add_argument("--forcar", action="store_true", help="criar: recria uma rota que já existe (a anterior vira backup)")
    p.add_argument("--formato", choices=("vertical", "horizontal"), default="vertical", help="comparar: orientação das pranchas (padrão: vertical)")
    p.add_argument("--com-atual", action="store_true", help="comparar: inclui a DA atual do projeto como primeira coluna")
    p.add_argument("--movimento", action="store_true", help="comparar: gera também os testes de movimento lado a lado (da/rotas/comparacao_movimento.mp4)")
    p.add_argument("--largura", type=int, default=None, metavar="PX", help="comparar: largura de cada coluna (padrão: 720 no vertical, 960 no horizontal)")
    p.add_argument("--regerar", action="store_true", help="comparar: refaz as pranchas mesmo que estejam em dia")
    p.add_argument("--saida", metavar="ARQ", help="comparar: imagem de saída (padrão: da/rotas/comparacao_<formato>.png)")
    p.add_argument("--json", action="store_true", help="listar: saída em JSON")


def _cmd_rotas(args) -> int:
    alvo = _alvo(args)
    acao = args.acao
    if acao == "listar":
        rotas = listar_rotas(**alvo)
        if args.json:
            _diz(json.dumps([{**r, "da_json": str(r["da_json"])} for r in rotas], ensure_ascii=False, indent=2))
            return SAIDA_OK
        if not rotas:
            _diz(f"Nenhuma rota em {pasta_das_rotas(_da_do_projeto(**alvo))}. Crie com: {DA_CLI} rotas criar <nome> --base <preset> --frase \"…\"")
            return SAIDA_OK
        for r in rotas:
            estado = f"{len(r['erros'])} erro(s)" if r["erros"] else (f"{len(r['avisos'])} aviso(s)" if r["avisos"] else "válida")
            _diz(f"{r['nome']:<18} herda {r['herda'] or '—'} · {_amostra_ansi(r['primaria']) if r['primaria'] else ''}primária {r['primaria'] or '?'} · "
                 f"fundo {r['fundo'] or '?'} · {estado}")
            _diz(f"{'':<18} {r['frase'] or '(sem frase de conceito)'}")
            _diz(f"{'':<18} prancha vertical: {r['prancha'].get('vertical', '?')} · horizontal: {r['prancha'].get('horizontal', '?')} · "
                 f"teste de movimento: {r['teste_movimento']}")
        _diz(f"\nLado a lado: {DA_CLI} rotas comparar     Adotar: {DA_CLI} rotas adotar <nome>")
        return SAIDA_OK
    if acao == "criar":
        if len(args.nomes) != 1:
            raise DAErro("rotas criar: informe UM nome de rota.", dica=f"{DA_CLI} rotas criar rota-a --base dossie --frase \"…\" --primaria \"#F6C614\"",
                         codigo=SAIDA_USO)
        cores = {}
        for par in args.cor:
            if "=" not in par:
                raise DAErro(f"--cor {par!r}: use CHAVE=#RRGGBB (ex.: --cor secundaria=#1D3557).", codigo=SAIDA_USO)
            k, v = par.split("=", 1)
            cores[k.strip()] = v.strip()
        if args.primaria:
            cores["primaria"] = args.primaria
        r = criar_rota(args.nomes[0], base=args.base, frase=args.frase, cores=cores, forcar=args.forcar, **alvo)
        _diz(f"Rota criada: {r['da_json']}  (herda {r['herda']})")
        _imprimir_validacao(r["erros"], r["avisos"])
        rel = f"da/{PASTA_ROTAS}/{r['nome']}"
        _diz("Próximos passos (da raiz do projeto):")
        _diz(f"  1. Edite {rel}/da/da.json — só o que diferencia a rota (cor, tipografia, movimento, legenda…).")
        _diz(f"  2. {DA_CLI} rotas comparar            # pranchas das rotas lado a lado (gera as que faltam)")
        _diz(f"  3. {DA_CLI} rotas adotar {r['nome']}")
        return SAIDA_ERRO if r["erros"] else SAIDA_OK
    if acao == "adotar":
        if len(args.nomes) != 1:
            raise DAErro("rotas adotar: informe UM nome de rota.", dica=f"Veja as rotas com `{DA_CLI} rotas listar`.", codigo=SAIDA_USO)
        r = adotar_rota(args.nomes[0], **alvo)
        _diz(f"Rota {args.nomes[0]!r} adotada: {r['da_json']}  (revisão {r['revisao']}, não aprovada, sha256 {r['sha256'][:12]}…)")
        _diz(f"  backup do da.json anterior: {r['backup'].name}")
        if r["recursos"]:
            _diz(f"  {len(r['recursos'])} arquivo(s) de fonte/recurso copiados para da/")
        if r["orfas"]:
            _diz(f"  ! {len(r['orfas'])} fonte(s) em da/fontes/ que a DA não usa mais: {', '.join(a.name for a in r['orfas'])} — apague se não forem voltar")
        for a in r["avisos"]:
            _diz(f"  ! {a}")
        _diz(f"Prancha e teste de movimento da DA anterior ficaram desatualizados: {DA_CLI} prancha && {DA_CLI} teste-movimento")
        return SAIDA_OK
    # comparar: precisa do motor (extensão)
    try:
        import da_ext_motor
    except ImportError as e:
        raise DAErro(f"rotas comparar precisa da extensão do motor (da_ext_motor.py): {e}")
    return da_ext_motor.cmd_comparar_rotas(args)


def _cmd_revisar(args) -> int:
    r = revisar(**_alvo(args))
    _diz(f"Revisão {r['anterior']} → {r['revisao']}; aprovação zerada"
         + ("" if r["estava_aprovada"] else " (a revisão anterior não estava aprovada)") + ".")
    if not r["compilada"]:
        _diz("  ! a DA tem erros e não foi recompilada — rode `da.py validar`")
    _diz("  Quando o visual estiver fechado de novo: `da.py aprovar`. Peças antigas precisam ser renderizadas outra vez se o conteúdo mudou.")
    return SAIDA_OK


def _cfg_lint(p):
    p.add_argument("caminhos", nargs="*", help="arquivos e/ou pastas (padrão: animacoes, legendas, cortes, thumbs e render do projeto)")
    p.add_argument("--estrito", action="store_true",
                   help="avisos (animação CSS) e arquivos NÃO conferidos (extensão que o lint não lê) também reprovam — é o modo da conferência final (`conferencia`)")
    p.add_argument("--json", action="store_true", help="saída em JSON")


def _cmd_lint(args) -> int:
    r = lint(args.caminhos, da=getattr(args, "da", None), de=getattr(args, "de", None), estrito=args.estrito)
    reprovado = not r["ok"]
    fora = r["nao_conferidos"]
    if args.json:
        _diz(json.dumps(r, ensure_ascii=False, indent=2))
        return SAIDA_ERRO if reprovado else SAIDA_OK
    for n in r["notas"]:
        _diz(f"nota: {n}", erro=True)
    for a in r["achados"]:
        marca = "" if a["severidade"] == "erro" else " (aviso)"
        _diz(f"{_rel(a['arquivo'])}:{a['linha']}:{a['coluna']}: [{a['regra']}]{marca} {a['trecho']}  →  {a['sugestao']}")
    for f in fora:
        _diz(f"NÃO CONFERIDO  {_rel(f['arquivo'])}  — {f['motivo']}")
    resumo = f"{r['arquivos']} arquivo(s) conferido(s): {r['erros']} violação(ões), {r['avisos']} aviso(s)"
    if fora:
        resumo += f"; {len(fora)} NÃO conferido(s)" + (" (reprova com --estrito)" if not args.estrito else "")
    if r["arquivos"] == 0:
        resumo += ". Nada foi lido: isto não é um sinal verde."
    elif not r["erros"] and not fora:
        resumo += ". Nenhuma cor ou fonte literal."
    else:
        resumo += "."
    _diz(resumo)
    if r["erros"]:
        _diz("Exceção legítima (foto, logo de terceiros, captura de tela)? Marque a linha com um comentário `da-livre` "
             "(`# da-livre` em Python) ou o elemento com data-da-livre.")
    return SAIDA_ERRO if reprovado else SAIDA_OK


def _cfg_carimbar(p):
    p.add_argument("saida", help="arquivo (ou pasta de quadros) gerado")
    p.add_argument("--ferramenta", required=True, help="quem gerou a peça (ex.: motor, legendas, thumbnail)")
    p.add_argument("--formato", help="formato da peça (horizontal, vertical, quadrado, thumbnail ou LxA)")
    p.add_argument("--parametros", metavar="JSON", help="parâmetros usados, em JSON (ou @arquivo.json)")
    p.add_argument("--auditoria", choices=AUDITORIAS, default="n/a",
                   help="n/a = peça que não passa pelo motor (padrão; é o que skills de PIL/ffmpeg usam); ok e pulada são "
                        "gravados pelo motor. Peça já carimbada como pulada não é promovida: renderize de novo")
    p.add_argument("--reauditada", action="store_true", help=argparse.SUPPRESS)      # uso do motor: o render acabou de passar pelo auditor
    p.add_argument("--sha-esperado", metavar="SHA", help="identidade da DA com que a peça foi desenhada; recusa (código 1) se a DA atual for outra")
    p.add_argument("--origem", metavar="ARQ", help="arquivo provisório (ex.: <saida>.parcial) que será renomeado para <saida>: a impressão digital sai dele")
    p.add_argument("--insumo", metavar="ARQ", action="append", default=[],
                   help="peça que entrou nesta composição (repita a opção): o carimbo guarda a DA e a auditoria de cada uma, "
                        "e a auditoria gravada é a pior entre elas")


def _avisar_alterada(d: DA) -> None:
    if d.meta.get("alterada_apos_aprovacao"):
        _diz(f"! DA ALTERADA DEPOIS DA APROVAÇÃO (revisão {d.revisao}): a peça sai carimbada como NÃO aprovada e "
             "conferir-carimbo acusa. Rode `da.py revisar` e `da.py aprovar` quando o visual estiver fechado.", erro=True)


def _cmd_carimbar(args) -> int:
    d = _da_para(Path(args.saida).expanduser().resolve(), getattr(args, "da", None))
    _avisar_alterada(d)
    parametros = None
    if args.parametros:
        bruto = args.parametros
        if bruto.startswith("@"):
            parametros = ler_json(bruto[1:])
        else:
            try:
                parametros = json.loads(bruto)
            except json.JSONDecodeError as e:
                raise DAErro(f"--parametros não é JSON válido ({e.msg}); ex.: --parametros '{{\"cena\": 3}}' ou --parametros @params.json")
    arq = carimbar(args.saida, args.ferramenta, args.formato, parametros, args.auditoria, da=d,
                   sha_esperado=args.sha_esperado, origem=args.origem, reauditada=args.reauditada, insumos=args.insumo or None)
    gravado = ler_json(arq)
    if gravado.get("auditoria") != args.auditoria:
        _diz(f"! auditoria gravada como \"{gravado.get('auditoria')}\": um insumo foi renderizado com --sem-auditoria", erro=True)
    _diz(f"Carimbo gravado: {arq}")
    return SAIDA_OK


def _cfg_conferir(p):
    p.add_argument("caminhos", nargs="*", help="arquivos e/ou pastas (padrão: animacoes, legendas, cortes, thumbs, render e broll/tratado do projeto; "
                                               "nomes começados por _ são intermediários e não são conferidos)")
    p.add_argument("--exigir-aprovada", action="store_true", help="reprova também quando a DA ainda não foi aprovada (é como a conferência final chama)")
    p.add_argument("--json", action="store_true", help="saída em JSON")


def _cmd_conferir(args) -> int:
    r = conferir_carimbo(args.caminhos, da=getattr(args, "da", None), de=getattr(args, "de", None),
                         exigir_aprovada=args.exigir_aprovada)
    if args.json:
        _diz(json.dumps(r, ensure_ascii=False, indent=2))
        return SAIDA_OK if r["ok"] else SAIDA_ERRO
    for p in r["pecas"]:
        linha = f"{ESTADOS_CARIMBO[p['estado']]:<17} {_rel(p['arquivo'])}"
        if p["estado"] in ("da_alterada", "da_nao_aprovada", "insumo_de_outra_da"):
            linha = f"{ESTADOS_CARIMBO[p['estado']]}  {_rel(p['arquivo'])}"
        _diz(linha + (f"  — {p['detalhe']}" if p["detalhe"] else ""))
    ruins = sum(1 for p in r["pecas"] if p["estado"] != "ok")
    if not r["pecas"]:
        _diz("Nenhuma peça encontrada para conferir.")
    else:
        situacao = ("ALTERADA DEPOIS DA APROVAÇÃO" if r["da_alterada_apos_aprovacao"] else "aprovada" if r["da_aprovada"] else "não aprovada")
        _diz(f"{len(r['pecas'])} peça(s): {len(r['pecas']) - ruins} em dia, {ruins} reprovada(s). "
             f"DA atual: revisão {r['da_revisao']}, {situacao}, sha256 {r['da_sha256'][:12]}…")
    return SAIDA_OK if r["ok"] else SAIDA_ERRO


def _cfg_plataformas(p):
    p.add_argument("nome", nargs="?", help="youtube, shorts, reels ou tiktok (apelidos valem: instagram, yt, tt…); sem nome, o resumo das quatro")
    p.add_argument("--chave", metavar="CHAVE", help="imprime só um limite (ex.: hashtags_max, titulo_max_caracteres, texto_max, duracao_max_s)")
    p.add_argument("--json", action="store_true", help="saída em JSON")


def _cmd_plataformas(args) -> int:
    nomes = [nome_plataforma(args.nome)] if args.nome else list(PLATAFORMAS)
    if args.chave:
        if not args.nome:
            raise DAErro("--chave pede o nome da plataforma (ex.: da.py plataformas reels --chave hashtags_max)", codigo=SAIDA_USO)
        v = limite(nomes[0], args.chave)
        _diz(json.dumps(v, ensure_ascii=False) if args.json or isinstance(v, (dict, list)) else ("null" if v is None else str(v)))
        return SAIDA_OK if v is not None else SAIDA_ERRO
    fichas = [plataforma(n) for n in nomes]
    if args.json:
        _diz(json.dumps(fichas[0] if args.nome else {f["nome"]: f for f in fichas}, ensure_ascii=False, indent=2))
        return SAIDA_OK

    def mostra(v, sufixo=""):
        return "—" if v is None else f"{v}{sufixo}"

    for f in fichas:
        _diz(f"{f['nome']:<8} título {mostra(f['titulo_max'])} · texto {mostra(f['texto_max'])} · hashtags {mostra(f['hashtags_max'])} · "
             f"duração {mostra(f['duracao_min_s'], ' s')} a {mostra(f['duracao_max_s'], ' s')} · até {mostra(f['tamanho_max_mb'], ' MB')} · {mostra(f['proporcao'])}")
    f = fichas[0]
    _diz(f"Verificado em {f['verificado_em']} ({f['idade_dias']} dia(s))" + (" — VENCIDO: revalide (references/plataformas.md §8)" if f["vencida"] else "")
         + ". — = não encontrado em fonte confiável.")
    return SAIDA_OK


def _cfg_grade(p):
    p.add_argument("--formato", metavar="NOME", default="horizontal", help="formato da cadeia impressa: nome da DA ou LxA, ex.: 640x360 (padrão: horizontal)")
    p.add_argument("--parte", choices=("completa", "cor", "acabamento"), default="completa",
                   help="completa = cor + acabamento; cor = grade/LUT/duotone; acabamento = desfoque/nitidez/vinheta/grão")
    p.add_argument("--entrada", metavar="ARQ", help="vídeo ou imagem a tratar (com --saida)")
    p.add_argument("--saida", metavar="ARQ", help="arquivo tratado (H.264 yuv420p para vídeo; carimbado)")
    p.add_argument("--inicio", type=float, metavar="S", help="começa em S segundos da entrada")
    p.add_argument("--duracao", type=float, metavar="S", help="trata só S segundos")
    p.add_argument("--crf", type=int, default=18, help="qualidade do H.264 (padrão: 18)")
    p.add_argument("--verificar", action="store_true", help="confere se este ffmpeg tem todos os filtros usados")
    p.add_argument("--json", action="store_true", help="imprime o grade.json inteiro")


def _cmd_grade(args) -> int:
    d = carregar(**_alvo(args))
    if bool(args.entrada) != bool(args.saida):
        raise DAErro("para aplicar o tratamento informe --entrada e --saida juntos")
    if args.entrada:
        _avisar_alterada(d)
        r = aplicar_grade(args.entrada, args.saida, da=d, parte=args.parte, inicio=args.inicio,
                          duracao=args.duracao, crf=args.crf)
        _diz(f"Tratado: {r['saida']}")
        _diz(f"  cadeia: {r['cadeia']}")
        _diz(f"  carimbo: {r['carimbo'].name}")
        return SAIDA_OK
    if args.verificar:
        tem = filtros_do_ffmpeg()
        usados = []
        for nome, f in gerar_grade(d)["formatos"].items():
            for filtro in filtros_da_cadeia(f["cadeia"]):
                if filtro not in usados:
                    usados.append(filtro)
        faltam = [f for f in usados if f not in tem]
        _diz("Filtros usados: " + (", ".join(usados) or "nenhum (tratamento neutro)"))
        if faltam:
            _diz(f"FALTAM neste ffmpeg: {', '.join(faltam)}")
            return SAIDA_ERRO
        _diz("Todos existem neste ffmpeg.")
        return SAIDA_OK
    if args.json:
        _diz(json_bonito(gerar_grade(d)))
    else:
        _diz(d.grade(args.formato, parte=args.parte))
    return SAIDA_OK


registrar_subcomando("init", "cria a estrutura do projeto, o da.json e o bloco do CLAUDE.md", _cfg_init, _cmd_init,
                     "Cria <pasta>/CLAUDE.md, <pasta>/da/ (da.json, fontes/, luts/, texturas/, logos/, referencias/, build/) e as "
                     "pastas de trabalho. Reexecutar é seguro: sem --forcar nada é sobrescrito.")
registrar_subcomando("achar", "localiza a DA subindo as pastas (código 2 se não houver)", _cfg_achar, _cmd_achar,
                     "Ordem: --da > variável DA_JSON > da/da.json nesta pasta ou em qualquer pasta acima. Sem DA: código 2.")
registrar_subcomando("validar", "confere esquema e semântica; código 1 se houver erro", _cfg_validar, _cmd_validar)
registrar_subcomando("compilar", "gera da/build/ (resolvida, css, js, grade, lock) e da/DA.md", _cfg_compilar, _cmd_compilar)
registrar_subcomando("mostrar", "resumo legível da DA no terminal", None, _cmd_mostrar)
registrar_subcomando("token", "imprime o valor de um token (resolve cores)", _cfg_token, _cmd_token)
registrar_subcomando("presets", "lista presets embutidos e pessoais", _cfg_presets, _cmd_presets)
registrar_subcomando("salvar-preset", "guarda a DA do projeto na biblioteca pessoal", _cfg_salvar_preset, _cmd_salvar_preset)
registrar_subcomando("extrair", "analisa referências: paleta, contraste, saturação, temperatura, grão", _cfg_extrair, _cmd_extrair,
                     "Grava referencias_analise.json e referencias_folha.png. Vídeos são amostrados com ffmpeg sob a trava global.")
registrar_subcomando("aprovar", "marca a DA como aprovada (grava data e sha256); avisa se prancha ou teste de movimento não estão em dia",
                     _cfg_aprovar, _cmd_aprovar,
                     "Grava aprovada=true, a data e o sha256 e recompila. Antes, confere os documentos que o cliente viu — da/prancha.png, "
                     "da/prancha_vertical.png e da/teste_movimento.mp4: ausentes ou feitos com outra versão da DA geram aviso (com --estrito, "
                     "recusa). Depois, a prancha em dia é regenerada para o cabeçalho dizer APROVADA (--sem-prancha desliga).")
registrar_subcomando("rotas", "rotas da DA: criar, listar, comparar (pranchas lado a lado) e adotar no projeto", _cfg_rotas, _cmd_rotas,
                     "Rotas são DAs candidatas em da/rotas/<nome>/da/da.json, herdando de um preset (ou da DA atual) e sobrescrevendo só o que as "
                     "diferencia. criar <nome> [--base PRESET] [--frase …] [--primaria #hex] [--cor chave=#hex]; listar; comparar [nomes…] "
                     "[--formato vertical|horizontal] [--com-atual] [--movimento] → da/rotas/comparacao_<formato>.png com as pranchas alinhadas "
                     "por seção (gera as que faltam); adotar <nome> → vira a DA do projeto (backup do da.json, fontes copiadas, CLAUDE.md "
                     "atualizado), sem passar pela biblioteca pessoal.")
registrar_subcomando("remover-preset", "apaga um preset da biblioteca pessoal", _cfg_remover_preset, _cmd_remover_preset)
registrar_subcomando("revisar", "abre nova revisão: incrementa o número e zera a aprovação", None, _cmd_revisar)
registrar_subcomando("lint", "reprova cor e fonte literais em peças (HTML/CSS/JS/SVG/JSON/Python)", _cfg_lint, _cmd_lint,
                     "Lê .html .htm .css .js .mjs .cjs .json .svg e .py (PIL: tupla RGB, hex, nome de cor, ImageFont.truetype "
                     "com caminho literal, cor em filtro ffmpeg). Arquivo que ele não sabe ler sai como NÃO CONFERIDO — nunca "
                     "como conferido — e reprova com --estrito. Exceções: comentário `da-livre` na linha (`# da-livre` em "
                     "Python); `da-livre:inicio` … `da-livre:fim`; `da-livre-arquivo` nas 10 primeiras linhas; atributo "
                     "data-da-livre no elemento (vale para ele e a subárvore). Código 1 se houver violação.")
registrar_subcomando("carimbar", "grava o sidecar <saida>.da.json de uma peça", _cfg_carimbar, _cmd_carimbar)
registrar_subcomando("conferir-carimbo", "reprova peça sem carimbo, com DA diferente, auditoria pulada ou DA alterada após a aprovação",
                     _cfg_conferir, _cmd_conferir,
                     "Estados: ok · SEM CARIMBO · CARIMBO ILEGÍVEL · DA DIFERENTE · AUDITORIA PULADA (da peça ou de um insumo dela) · "
                     "INSUMO DE OUTRA DA · ARQUIVO ALTERADO · DA ALTERADA APÓS APROVAÇÃO (da.json editado depois do `aprovar`) · "
                     "DA NÃO APROVADA (só com --exigir-aprovada). Elementos data-da-livre de cada peça aparecem no detalhe. "
                     "Pastas e arquivos de nome começado por _ são intermediários e não são conferidos. Código 1 se alguma reprovar.")
registrar_subcomando("plataformas", "limites e specs por plataforma (youtube, shorts, reels, tiktok)", _cfg_plataformas, _cmd_plataformas,
                     "Lê kit/plataformas.json com nomes canônicos: título, texto, hashtags, duração, tamanho e proporção. "
                     "`plataformas reels --chave hashtags_max` imprime um valor só; --json devolve a ficha inteira. Não precisa de DA.")
registrar_subcomando("grade", "mostra, verifica ou aplica a cadeia ffmpeg do tratamento", _cfg_grade, _cmd_grade,
                     "Sem --entrada: imprime a cadeia de filtros. Com --entrada e --saida: aplica (ffmpeg sob a trava) e carimba.")


def montar_parser() -> argparse.ArgumentParser:
    _carregar_extensoes()
    parser = _Parser(prog="da.py", description="Direção de arte por projeto: uma fonte de verdade visual (da/da.json) "
                                               "a que todas as skills de vídeo se submetem.",
                     epilog="Códigos de saída: 0 ok · 1 reprovado/erro · 2 nenhuma DA encontrada · 64 uso incorreto · "
                            "75 fila da trava · 124 sem progresso · 128+N sinal.\n"
                            f"Kit {KIT_VERSAO} · {KIT_FINAL}")
    parser.add_argument("--versao", action="version", version=f"kit de direção de arte {KIT_VERSAO}",
                        help="mostra a versão do kit e sai")
    comum = _opcoes_comuns()                       # --da/--de valem antes ou depois do subcomando
    parser.add_argument("--da", metavar="CAMINHO", help="da.json (ou pasta do projeto) a usar")
    parser.add_argument("--de", metavar="PASTA", help="pasta de onde começar a procurar da/da.json")
    sub = parser.add_subparsers(dest="subcomando", metavar="<subcomando>", title="subcomandos", parser_class=_Parser)
    for nome, info in _SUBCOMANDOS.items():
        p = sub.add_parser(nome, help=info["ajuda"], description=info["descricao"], parents=[comum])
        if info["configurar"]:
            info["configurar"](p)
        p.set_defaults(_executar=info["executar"], _repasse=info.get("repasse", False))
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = montar_parser()
    try:
        args, extras = parser.parse_known_args(argv)
        if extras:
            if getattr(args, "_repasse", False):
                # subcomando de repasse (ex.: render): as opções iniciais desconhecidas (--cena …) vêm como
                # "extras" e o REMAINDER só começa no primeiro valor; recompõe a linha na ordem original
                args.argumentos = list(extras) + list(getattr(args, "argumentos", None) or [])
            else:
                parser.parse_args(argv)           # reproduz o erro de uso padrão ("argumentos não reconhecidos")
    except SystemExit as e:
        return int(e.code) if isinstance(e.code, int) else SAIDA_USO
    executar = getattr(args, "_executar", None)
    if executar is None:
        parser.print_help()
        return SAIDA_USO
    try:
        return int(executar(args) or 0)
    except DAInvalida as e:
        _imprimir_validacao(e.erros, e.avisos, str(e).split("\n", 1)[0], erro=True)
        if e.dica:
            _diz(e.dica, erro=True)
        return e.codigo
    except DAErro as e:
        _diz(f"erro: {e}", erro=True)
        return e.codigo
    except trava.TempoEsgotado as e:
        _diz(f"erro: {e}", erro=True)
        return trava.SAIDA_TEMPO_ESGOTADO
    except trava.Interrompido as e:               # SIGTERM/SIGHUP sob a trava: filhos já mortos, trava já solta
        return int(e.code)
    except BrokenPipeError:
        return SAIDA_OK
    except KeyboardInterrupt:
        return 130
    except Exception as e:                        # defeito do kit ou dado inesperado: mensagem de uma linha, não traceback
        if os.environ.get("DA_DEBUG", "").strip() not in ("", "0"):
            raise
        _diz(f"erro interno: {type(e).__name__}: {e}", erro=True)
        _diz("Isto é um defeito do kit ou um dado que ele não previu. Rode de novo com DA_DEBUG=1 para ver o traceback.", erro=True)
        return SAIDA_ERRO


if __name__ == "__main__":
    sys.exit(main())
