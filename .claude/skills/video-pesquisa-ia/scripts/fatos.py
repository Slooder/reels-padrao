#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fatos.py — ficha de fatos verificada de um vídeo sobre inteligência artificial.

Skill video-pesquisa-ia. Mantém <projeto>/pesquisa/fatos.json (contrato da casa), gera
pesquisa/fatos.md e pesquisa/fontes.md, confere o roteiro e o storyboard contra a ficha e
entrega o crédito de fonte que vai para a tela.

Uso como módulo (outras skills):

    from pathlib import Path
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "video-pesquisa-ia" / "scripts"))
    import fatos
    ficha, caminho = fatos.carregar(projeto="/caminho/do/projeto")
    rel = fatos.validar_ficha(ficha)                      # {"ok", "erros", "avisos", "fatos"}
    txt = fatos.credito(fatos.obter(ficha, "F003"))["texto"]   # "Fonte: OpenAI, out/2026"

Só stdlib. Códigos de saída: 0 ok · 1 pendência/reprovado · 2 não há ficha · 64 uso incorreto ·
75 sem rede (nada foi verificado).

Gravação: todo comando que escreve na ficha (novo, adicionar, atualizar, remover, checar-links) faz
carregar → alterar → salvar dentro de uma trava de arquivo (pesquisa/_fatos.lock), para que comandos
disparados em paralelo não percam fatos nem repitam ids, e sempre com a data REAL do dia (--hoje e
VIDEO_OPS_HOJE só simulam leitura).
"""
from __future__ import annotations

import argparse
import concurrent.futures
import contextlib
import datetime as dt
import difflib
import hashlib
import html as _html
import http.cookiejar
import json
import os
import re
import socket
import ssl
import sys
import tempfile
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

try:                                                              # trava de arquivo: POSIX
    import fcntl as _fcntl
except ImportError:                                               # Windows: msvcrt (não testado nesta casa)
    _fcntl = None
    try:
        import msvcrt as _msvcrt
    except ImportError:
        _msvcrt = None

# ----------------------------------------------------------------------------- constantes
VERSAO_FICHA = 1
SAIDA_OK, SAIDA_PENDENCIA, SAIDA_SEM_FICHA, SAIDA_USO, SAIDA_SEM_REDE = 0, 1, 2, 64, 75

CATEGORIAS = ("modelo", "benchmark", "preco", "historia", "conceito", "empresa", "outro")
STATUS = ("confirmado", "divergente", "nao_confirmado")
CONFIANCAS = ("alta", "media", "baixa")
TIPOS_FONTE = ("primaria", "secundaria")

# Categorias voláteis: exigem caduca_em. Os dias são a validade sugerida pela casa (não é dado externo):
# preço muda sem aviso; catálogo de modelos e placares mudam em semanas.
VALIDADE_SUGERIDA = {"preco": 30, "modelo": 60, "benchmark": 60}
VALIDADE_LONGA = 180            # acima disto, aviso em categoria volátil
MAX_PALAVRAS_TRECHO = 25
MAX_EDITOR_CREDITO = 40         # caracteres; o editor é o que aparece no crédito da tela

CAMPOS_FATO = ("id", "afirmacao", "valor", "unidade", "referente_a", "categoria", "status", "confianca",
               "caduca_em", "fontes", "como_dizer", "notas")
CAMPOS_FONTE = ("titulo", "url", "editor", "tipo", "publicado_em", "acessado_em", "trecho")

MESES_ABREV = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")

# Domínios que nunca são fonte primária de um fato sobre terceiros (agregadores, fóruns e enciclopédias).
DOMINIOS_NAO_PRIMARIOS = ("wikipedia.org", "medium.com", "reddit.com", "quora.com", "substack.com")
# Sufixos públicos de dois níveis mais comuns (para achar o domínio registrável sem lista externa).
_SUFIXOS_2N = {"com.br", "org.br", "net.br", "gov.br", "edu.br", "jus.br", "leg.br", "co.uk", "org.uk", "ac.uk",
               "gov.uk", "com.au", "co.jp", "com.cn", "co.kr", "com.mx", "com.ar", "co.in", "com.pt", "co.nz"}

# Conferência do trecho de cada fonte (campo extra `conferencia` na fonte; só o fatos.py escreve):
# encontrado = checar-links --trechos achou o trecho na página · ausente = abriu e não achou ·
# nao_verificado = a página não pôde ser lida pelo robô (bloqueio, PDF, sem resposta) ·
# manual = alguém declarou, com nota, que abriu a página e leu o trecho.
CONFERENCIAS = ("encontrado", "ausente", "nao_verificado", "manual")
CONFERENCIAS_OK = ("encontrado", "manual")
MIN_NOTA_MANUAL = 20            # caracteres: a nota diz ONDE e COMO o trecho foi visto
ESPERA_TRAVA = 20.0             # segundos à espera de outro fatos.py que esteja gravando a mesma ficha


class ErroFatos(Exception):
    """Erro com mensagem acionável: o que houve + o que fazer."""

    def __init__(self, mensagem: str, dica: str | None = None, codigo: int = SAIDA_PENDENCIA):
        super().__init__(mensagem)
        self.mensagem, self.dica, self.codigo = mensagem, dica, codigo


# ----------------------------------------------------------------------------- utilidades
_RE_DATA = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def ler_data(valor) -> dt.date | None:
    """AAAA-MM-DD → date; qualquer outra coisa → None."""
    if not isinstance(valor, str) or not _RE_DATA.match(valor):
        return None
    try:
        return dt.date.fromisoformat(valor)
    except ValueError:
        return None


def data_real() -> dt.date:
    """A data de verdade — é a única que vai para a ficha (atualizado_em, acessado_em, conferência).

    VIDEO_OPS_RELOGIO_TESTE=AAAA-MM-DD troca o relógio inteiro e existe só para a suíte de testes ser
    determinística; não é para uso em projeto (para simular a data de publicação use --hoje em comando de leitura)."""
    bruto = os.environ.get("VIDEO_OPS_RELOGIO_TESTE")
    if bruto:
        d = ler_data(bruto)
        if d is None:
            raise ErroFatos(f"data inválida em VIDEO_OPS_RELOGIO_TESTE: {bruto!r}", "use AAAA-MM-DD", SAIDA_USO)
        return d
    return dt.date.today()


def hoje_local(texto: str | None = None) -> dt.date:
    """Data de hoje para LEITURA; `--hoje` ou a variável VIDEO_OPS_HOJE simulam outra (ex.: a da publicação).

    Comandos que gravam não usam esta função: usam data_real()."""
    bruto = texto or os.environ.get("VIDEO_OPS_HOJE")
    if bruto:
        d = ler_data(bruto)
        if d is None:
            raise ErroFatos(f"data inválida em --hoje/VIDEO_OPS_HOJE: {bruto!r}",
                            "use o formato AAAA-MM-DD, por exemplo 2026-10-06", SAIDA_USO)
        return d
    return data_real()


def data_br(valor) -> str:
    d = ler_data(valor) if isinstance(valor, str) else valor
    return d.strftime("%d/%m/%Y") if isinstance(d, dt.date) else "—"


def mes_ano(valor) -> str:
    d = ler_data(valor) if isinstance(valor, str) else valor
    return f"{MESES_ABREV[d.month - 1]}/{d.year}" if isinstance(d, dt.date) else ""


def normalizar(s) -> str:
    """minúsculas, sem acento, só letras e números separados por um espaço."""
    s = unicodedata.normalize("NFKD", str(s).lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def contar_palavras(s) -> int:
    return len(re.findall(r"\S+", s or ""))


def _fontes(f) -> list:
    """Só as fontes bem formadas (objetos) de um fato — a ficha pode ter sido editada à mão."""
    fs = f.get("fontes") if isinstance(f, dict) else None
    return [s for s in fs if isinstance(s, dict)] if isinstance(fs, list) else []


def _termos(f) -> list:
    ts = f.get("termos") if isinstance(f, dict) else None
    return [t for t in ts if isinstance(t, str)] if isinstance(ts, list) else []


def _volatil(f) -> bool:
    c = f.get("categoria") if isinstance(f, dict) else None
    return isinstance(c, str) and c in VALIDADE_SUGERIDA


def _txt(v) -> str:
    return v if isinstance(v, str) else ("" if v is None else str(v))


def _plural(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


_DICA_JSON = {
    "ficha": "corrija a sintaxe; a versão anterior da ficha fica em pesquisa/_fatos.anterior.json",
    "storyboard": "o storyboard é o roteiro/storyboard.json escrito pela skill video-animacao-explicativa: confira o "
                  "caminho (um roteiro .md se confere com `conferir-roteiro`) ou corrija a sintaxe do JSON",
    "json": "corrija a sintaxe do JSON",
}


def ler_json(caminho: Path, o_que: str = "ficha"):
    """Lê um JSON com mensagens acionáveis. `o_que`: ficha | storyboard | json (muda só a dica do erro)."""
    caminho = Path(caminho)
    try:
        return json.loads(caminho.read_text(encoding="utf-8-sig"))     # -sig: tolera BOM de editores do Windows
    except FileNotFoundError:
        raise ErroFatos(f"arquivo não encontrado: {caminho}", "confira o caminho (use aspas se houver espaço)")
    except IsADirectoryError:
        raise ErroFatos(f"{caminho} é uma pasta, não um arquivo JSON")
    except UnicodeDecodeError:
        raise ErroFatos(f"{caminho} não está em UTF-8", "regrave o arquivo em UTF-8")
    except json.JSONDecodeError as e:
        if caminho.suffix.lower() != ".json":
            dica = (f"{caminho.name} não é um arquivo .json: "
                    + ("--ficha espera o pesquisa/fatos.json (o fatos.md é gerado a partir dele)" if o_que == "ficha"
                       else _DICA_JSON.get(o_que, _DICA_JSON["json"])))
        else:
            dica = _DICA_JSON.get(o_que, _DICA_JSON["json"])
        raise ErroFatos(f"{caminho}: JSON inválido na linha {e.lineno}, coluna {e.colno} ({e.msg})", dica)


def gravar_texto(caminho: Path, texto: str) -> None:
    """Gravação atômica: arquivo temporário na mesma pasta + rename."""
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="_" + caminho.name + ".", suffix=".parcial", dir=str(caminho.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(texto)
        mascara = os.umask(0)
        os.umask(mascara)
        os.chmod(tmp, 0o666 & ~mascara)                           # mkstemp cria 0600; a ficha é lida por outras skills
        os.replace(tmp, caminho)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def gravar_json(caminho: Path, dados) -> None:
    gravar_texto(caminho, json.dumps(dados, ensure_ascii=False, indent=2) + "\n")


# ----------------------------------------------------------------------------- localizar e carregar
def achar_ficha(projeto=None, ficha=None, de=None) -> Path:
    """Caminho de pesquisa/fatos.json: --ficha > --projeto > subir as pastas a partir de `de`/cwd."""
    if ficha:
        return Path(ficha).expanduser()
    if projeto:
        return Path(projeto).expanduser() / "pesquisa" / "fatos.json"
    inicio = Path(de).expanduser() if de else Path.cwd()
    inicio = inicio.resolve()
    for pasta in (inicio, *inicio.parents):
        c = pasta / "pesquisa" / "fatos.json"
        if c.is_file():
            return c
    raise ErroFatos("nenhuma ficha de fatos (pesquisa/fatos.json) nesta pasta nem nas pastas acima",
                    'crie uma com: fatos.py novo --tema "assunto do vídeo" --projeto "<pasta do projeto>"',
                    SAIDA_SEM_FICHA)


def raiz_do_projeto(caminho_ficha: Path) -> Path:
    p = Path(caminho_ficha).resolve()
    return p.parent.parent if p.parent.name == "pesquisa" else p.parent


def carregar(projeto=None, ficha=None, de=None):
    """→ (ficha: dict, caminho: Path). Levanta ErroFatos (código 2) se não existe."""
    caminho = achar_ficha(projeto, ficha, de)
    if not caminho.is_file():
        raise ErroFatos(f"não há ficha de fatos em {caminho}",
                        'crie uma com: fatos.py novo --tema "assunto do vídeo" --projeto "<pasta do projeto>"',
                        SAIDA_SEM_FICHA)
    dados = ler_json(caminho)
    if not isinstance(dados, dict) or not isinstance(dados.get("fatos"), list):
        raise ErroFatos(f"{caminho} não tem o formato da ficha (objeto com a lista \"fatos\")",
                        "rode `fatos.py validar` para ver o que falta, ou restaure pesquisa/_fatos.anterior.json")
    return dados, caminho


@contextlib.contextmanager
def trava_da_ficha(caminho: Path, espera: float | None = None):
    """Trava exclusiva em volta de carregar → alterar → salvar (arquivo `_fatos.lock` ao lado da ficha).

    Sem ela, dois `adicionar` simultâneos leem a mesma ficha, atribuem o mesmo id e o último a gravar apaga o fato
    do outro. A trava é do sistema (flock): some sozinha se o processo morrer; o arquivo vazio pode ficar."""
    espera = ESPERA_TRAVA if espera is None else espera
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    arq = caminho.with_name("_fatos.lock")
    fh = open(arq, "a+b")
    travado = False
    try:
        limite = time.monotonic() + espera
        while True:
            try:
                if _fcntl is not None:
                    _fcntl.flock(fh.fileno(), _fcntl.LOCK_EX | _fcntl.LOCK_NB)
                elif _msvcrt is not None:
                    fh.seek(0)
                    _msvcrt.locking(fh.fileno(), _msvcrt.LK_NBLCK, 1)
                travado = True
                break
            except OSError:
                if time.monotonic() >= limite:
                    raise ErroFatos(f"outro fatos.py está gravando esta ficha há mais de {espera:g} s ({arq.name}): "
                                    "nada foi gravado",
                                    "espere o outro comando terminar e rode de novo; para registrar vários fatos de uma "
                                    "vez, passe uma lista JSON a um único `adicionar`")
                time.sleep(0.05)
        yield
    finally:
        try:
            if travado and _fcntl is not None:
                _fcntl.flock(fh.fileno(), _fcntl.LOCK_UN)
            elif travado and _msvcrt is not None:
                fh.seek(0)
                _msvcrt.locking(fh.fileno(), _msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
        fh.close()


def salvar(ficha: dict, caminho: Path, hoje: dt.date | None = None) -> None:
    """Grava a ficha (atualizado_em = data real) guardando a versão anterior em pesquisa/_fatos.anterior.json.

    Quem chama deve estar dentro de `trava_da_ficha(caminho)` e ter carregado a ficha já com a trava."""
    caminho = Path(caminho)
    ficha["atualizado_em"] = (hoje or data_real()).isoformat()
    if caminho.is_file():
        try:
            gravar_texto(caminho.with_name("_fatos.anterior.json"), caminho.read_text(encoding="utf-8"))
        except OSError:
            pass
    gravar_json(caminho, ficha)


def obter(ficha: dict, fid: str) -> dict:
    alvo = str(fid).strip().upper()
    for f in ficha.get("fatos", []):
        if isinstance(f, dict) and str(f.get("id", "")).upper() == alvo:
            return f
    ids = [f.get("id") for f in ficha.get("fatos", []) if isinstance(f, dict)]
    raise ErroFatos(f"não existe o fato {fid} na ficha",
                    f"ids existentes: {', '.join(map(str, ids)) or 'nenhum'} — veja com `fatos.py resumo`")


def proximo_id(ficha: dict) -> str:
    """Ids nunca são reaproveitados: roteiro e storyboard apontam para eles."""
    maior = int(ficha.get("ultimo_id") or 0)
    for f in ficha.get("fatos", []):
        m = re.fullmatch(r"F(\d{3,})", str(f.get("id", ""))) if isinstance(f, dict) else None
        if m:
            maior = max(maior, int(m.group(1)))
    return f"F{maior + 1:03d}"


# ----------------------------------------------------------------------------- números e nomes no texto
_STOP_PT = set("""a o os as um uma uns umas de do da dos das em no na nos nas por para pra com sem que e ou mas se como
quando onde quem qual quais ja nao sim mais menos muito pouco foi sao ser esta estao tem ha seu sua seus suas esse essa
isso este esta isto ele ela eles elas voce eu nos entre ate desde depois antes sobre cada todo toda todos todas tambem
ainda so apenas mesmo porque pelo pela pelos pelas ao aos num numa era eram sera vai vao pode podem tinha fazer feito
cerca quase hoje agora anos ano""".split())

# Substantivos que fazem do número uma contagem editorial ("3 motivos"), não um fato.
_ESTRUTURAIS = (r"motivos?|raz(?:ão|ões|ao|oes)|passos?|dicas?|coisas?|pontos?|etapas?|partes?|exemplos?|perguntas?|"
                r"jeitos?|formas?|maneiras?|erros?|li(?:ção|ções|cao|coes)|sina(?:l|is)|hábitos?|habitos?|segredos?|"
                r"truques?|ite(?:m|ns)|op(?:ção|ções|cao|coes)|minutos?|segundos?|vídeos?|videos?|aulas?|blocos?|"
                r"slides?|stories|cenas?|mitos?|verdades?|ideias?|conceitos?|tipos?|fases?")
_RE_ESTRUTURAL_DEPOIS = re.compile(
    r"^\s+(?:(?:grandes|principais|maiores|piores|melhores|primeir[oa]s|últim[oa]s|ultim[oa]s|simples|nov[oa]s)\s+)?"
    r"(?:" + _ESTRUTURAIS + r")\b", re.I)
_RE_ESTRUTURAL_ANTES = re.compile(
    r"(?:\b(?:passo|etapa|parte|slide|story|cap[ií]tulo|op[çc][ãa]o|item|n[ºo°]\.?|n[úu]mero|bloco|cena|motor|"
    r"n[íi]vel|fase|dia|top|vers[ãa]o|regra|li[çc][ãa]o|dica|erro|motivo|take|tomada|plano|quadro|epis[óo]dio|ep\.?|"
    r"aula|m[óo]dulo|v[íi]deo|hook|gancho|ato|rodada|tela|exemplo|caso|pergunta|mito|tipo|tentativa|rascunho)|#)\s?-?$",
    re.I)
_RE_UNIDADE_IGNORADA = re.compile(r"^(?:s|seg|min|h|ms|fps|p|px|º|ª|°|D|G)(?![A-Za-zÀ-ÿ])")
# faixa de tempo de roteiro ("0–3s", "45-60 s", "3–10 min"): minutagem, não dado
_RE_FAIXA_TEMPO = re.compile(r"(?<![\w.,])\d{1,4}\s?[–—-]\s?\d{1,4}\s?(?:s|seg|segundos?|min|minutos?|h|horas?)(?![A-Za-zÀ-ÿ])",
                             re.I)
# "caiu 10 vezes", "cresceu dez vezes": depois de verbo de mudança, "N vezes" é proporção (≠ "10 vezes por dia")
_RE_VEZES_SIMPLES = re.compile(r"^(?:\s+vezes|\s?x)(?![A-Za-zÀ-ÿ0-9])", re.I)
_RE_VERBO_MUDANCA = re.compile(
    r"\b(?:ca(?:iu|[íi]ram|i|em)|sub(?:iu|iram|ir[áa])|cresc(?:eu|eram|e)|aument(?:ou|aram|a)|diminu(?:iu|[íi]ram|i)|"
    r"encolh(?:eu|eram)|multiplic(?:ou|aram|a)|salt(?:ou|aram)|baix(?:ou|aram)|reduz(?:iu|iram)?|barate(?:ou|aram)|"
    r"encarec(?:eu|eram)|aceler(?:ou|aram)|melhor(?:ou|aram)|pior(?:ou|aram))\s+(?:[\wÀ-ÿ]+\s+){0,3}$", re.I)

_NUM = (r"\d{1,3}(?:[.\u00a0\u202f]\d{3})+(?:,\d+)?"      # 1.234.567,89 (PT)
        r"|\d{1,3}(?:,\d{3})+(?:\.\d+)?"                  # 1,234,567.89 (EN)
        r"|\d+(?:[.,]\d+)?")                              # 1250 · 1,25 · 1.25
_RE_NUM = re.compile(r"(?<![\w.,])(" + _NUM + r")(?!\d)")
_RE_MULT_LETRA = re.compile(r"^(k|K|M|B|T)(?![A-Za-zÀ-ÿ0-9])")
_RE_MULT_PALAVRA = re.compile(
    r"^\s*(mil|milh(?:ão|ões|ao|oes)|bilh(?:ão|ões|ao|oes)|trilh(?:ão|ões|ao|oes)|mi|bi|tri|"
    r"thousand|million|billion|trillion)\b", re.I)
_MULT = {"k": 1e3, "m": 1e6, "b": 1e9, "t": 1e12, "mil": 1e3, "mi": 1e6, "bi": 1e9, "tri": 1e12,
         "thousand": 1e3, "million": 1e6, "billion": 1e9, "trillion": 1e12}
_RE_MOEDA_ANTES = re.compile(r"(US\$|U\$S|R\$|\$|€|£|USD|BRL|EUR)\s?$")
_RE_MOEDA_DEPOIS = re.compile(
    r"^\s+(?:de\s+)?(dólar(?:es)?|dolar(?:es)?|reais|real|euros?|centavos?|cents?|libras?|dollars?|USD|BRL|EUR)\b", re.I)
_RE_MOEDA_DO_CENTAVO = re.compile(r"^\s+(?:de\s+|of\s+a\s+)?(dólar|dolar|dollar|real|euro)\b", re.I)
_RE_MOEDA_QUALQUER = re.compile(r"US\$|U\$S|R\$|\$|€|£|\b(?:USD|BRL|EUR|GBP|dólar(?:es)?|dolar(?:es)?|dollars?|reais|real|"
                                r"euros?|libras?)\b", re.I)
_RE_PCT_DEPOIS = re.compile(r"^(?:\s?%|\s+por\s+cento\b|\s+pontos?\s+percentua(?:l|is)\b|\s+percent\b)", re.I)
_RE_PCT_QUALQUER = re.compile(r"%|\bpor\s+cento\b|\bpercent(?:ual|uais|age)?\b|\bpontos?\s+percentua(?:l|is)\b", re.I)
# "100% gratuito" é ênfase de chamada, não medida.
_RE_PCT_ENFASE = re.compile(r"^\s*(?:gratuit[oa]s?|gr[áa]tis|de\s+gra[çc]a|free|online|pr[áa]tic[oa]s?|garantid[oa]s?|"
                            r"segur[oa]s?|verdade|certeza|foco|focad[oa]s?|sincer[oa]s?|honest[oa]s?)\b", re.I)
# comparação que faz do número uma proporção ("3 vezes mais rápido", "10x maior", "3 em cada 4")
_RE_VEZES_DEPOIS = re.compile(r"^(?:\s+vezes|\s?x)\s+(?:mais|menos|maior(?:es)?|menor(?:es)?|melhor(?:es)?|pior(?:es)?|"
                              r"superior(?:es)?|inferior(?:es)?|o\b|a\b)", re.I)
_RE_EM_CADA_DEPOIS = re.compile(r"^\s+(?:em|de|a)\s+cada\s+", re.I)
_RE_E_MEIO_DEPOIS = re.compile(r"^\s+e\s+mei[oa]\b", re.I)
_RE_FRACOES = [
    (re.compile(r"(?<![\w-])(?:(?:a|pela|na|da|à)\s+)?metade(?![\w-])", re.I), 0.5),
    (re.compile(r"(?<![\w-])(?:o\s+dobro|dobr(?:ou|aram|ar[áa])|duplic(?:ou|aram))(?![\w-])", re.I), 2.0),
    (re.compile(r"(?<![\w-])(?:o\s+triplo|triplic(?:ou|aram))(?![\w-])", re.I), 3.0),
    (re.compile(r"(?<![\w-])(?:o\s+qu[áa]druplo|quadruplic(?:ou|aram))(?![\w-])", re.I), 4.0),
    (re.compile(r"(?<![\w-])um\s+ter[çc]o(?![\w-])", re.I), 1 / 3),
    (re.compile(r"(?<![\w-])dois\s+ter[çc]os(?![\w-])", re.I), 2 / 3),
    (re.compile(r"(?<![\w-])um\s+quarto\s+(?=d[aeo]s?\b)", re.I), 0.25),
    (re.compile(r"(?<![\w-])tr[êe]s\s+quartos\s+(?=d[aeo]s?\b)", re.I), 0.75),
    (re.compile(r"(?<![\w-])um\s+quinto\s+(?=d[aeo]s?\b)", re.I), 0.2),
    (re.compile(r"(?<![\w-])um\s+d[ée]cimo\s+(?=d[aeo]s?\b)", re.I), 0.1),
]

# ---- datas: o dia e o mês de uma data não são "números" do fato; a data é comparada como data
_MES_NUM = {"janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6, "julho": 7, "agosto": 8,
            "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
            "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6, "july": 7, "august": 8,
            "september": 9, "october": 10, "november": 11, "december": 12,
            "jan": 1, "fev": 2, "feb": 2, "mar": 3, "abr": 4, "apr": 4, "mai": 5, "jun": 6, "jul": 7, "ago": 8,
            "aug": 8, "set": 9, "sep": 9, "sept": 9, "out": 10, "oct": 10, "nov": 11, "dez": 12, "dec": 12}
_M_PT = r"janeiro|fevereiro|mar[çc]o|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro"
_M_EN = r"january|february|march|april|may|june|july|august|september|october|november|december"
_A_PT = r"jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez"
_A_EN = r"jan|feb|mar|apr|may|jun|jul|aug|sept?|oct|nov|dec"
_NOMES_MES = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
              "novembro", "dezembro")
# (regex, grupo do dia, grupo do mês, grupo do ano, só em texto estrangeiro)
_PADROES_DATA = [
    (re.compile(r"(?<![\w/-])(\d{4})-(\d{2})-(\d{2})(?![\w-])"), 3, 2, 1, False),
    (re.compile(r"(?<![\w/.,])(\d{1,2})/(\d{1,2})/(\d{4})(?![\w/])"), 1, 2, 3, False),
    (re.compile(r"(?<![\w.,/])(\d{1,2})(?:º|°)?\s+de\s+(" + _M_PT + r")(?:\s+de\s+(\d{4}))?(?![\w])", re.I), 1, 2, 3, False),
    (re.compile(r"(?<![\w.,/])(\d{1,2})\s+(?:de\s+)?(" + _A_PT + r")\.?\s+(?:de\s+)?(\d{4})(?!\d)", re.I), 1, 2, 3, False),
    (re.compile(r"(?<![\w])(" + _M_EN + r"|" + _A_EN + r")\.?\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(\d{4}))?(?![\w])", re.I),
     2, 1, 3, True),
    (re.compile(r"(?<![\w.,/])(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?(" + _M_EN + r"|" + _A_EN + r")\.?,?\s+(\d{4})(?!\d)",
                re.I), 1, 2, 3, True),
    (re.compile(r"(?<![\w])(" + _M_PT + r")\s+(?:de\s+)?(\d{4})(?!\d)", re.I), None, 1, 2, False),
    (re.compile(r"(?<![\w])(" + _M_PT + r"|" + _A_PT + r")/(\d{4})(?!\d)", re.I), None, 1, 2, False),
    (re.compile(r"(?<![\w])(" + _M_EN + r")\s+(\d{4})(?!\d)", re.I), None, 1, 2, True),
    (re.compile(r"(?<![\w])(?:em|desde|at[ée]|durante|m[êe]s\s+de|in[íi]cio\s+de|come[çc]o\s+de|fi(?:m|nal)\s+de|"
                r"meados\s+de)\s+(" + _M_PT + r")(?![\w])", re.I), None, 1, None, False),
]
# dia por extenso: "doze de junho de 2017", "primeiro de janeiro"
_DIA_EXT = (r"trinta\s+e\s+um|trinta|vinte(?:\s+e\s+(?:uma?|dois|duas|tr[êe]s|quatro|cinco|seis|sete|oito|nove))?|dezenove|"
            r"dezoito|dezessete|dezesseis|quinze|catorze|quatorze|treze|doze|onze|dez|nove|oito|sete|seis|cinco|quatro|"
            r"tr[êe]s|dois|primeiro")
_RE_DATA_DIA_EXTENSO = re.compile(r"(?<![\w-])(" + _DIA_EXT + r")\s+de\s+(" + _M_PT + r")(?:\s+de\s+(\d{4}))?(?![\w])", re.I)

# ---- numerais por extenso (roteiro de locução escreve "nove dólares", "noventa por cento")
_RE_REFERENCIA_ANTES = re.compile(r"\b(?:os|as|es[st]es|es[st]as|aqueles|aquelas|dos|das|nos|nas|aos|[àa]s|pelos|pelas|"
                                  r"des[st]es|des[st]as|nes[st]es|nes[st]as)\s+$", re.I)
_EXT = {"e": ("e", 0)}
for _w, _v in (("zero", 0), ("um", 1), ("uma", 1), ("dois", 2), ("duas", 2), ("tres", 3), ("quatro", 4), ("cinco", 5),
               ("seis", 6), ("sete", 7), ("oito", 8), ("nove", 9), ("dez", 10), ("onze", 11), ("doze", 12),
               ("treze", 13), ("catorze", 14), ("quatorze", 14), ("quinze", 15), ("dezesseis", 16), ("dezasseis", 16),
               ("dezessete", 17), ("dezassete", 17), ("dezoito", 18), ("dezenove", 19), ("dezanove", 19),
               ("vinte", 20), ("trinta", 30), ("quarenta", 40), ("cinquenta", 50), ("sessenta", 60), ("setenta", 70),
               ("oitenta", 80), ("noventa", 90), ("cem", 100), ("cento", 100), ("duzentos", 200), ("duzentas", 200),
               ("trezentos", 300), ("trezentas", 300), ("quatrocentos", 400), ("quatrocentas", 400),
               ("quinhentos", 500), ("quinhentas", 500), ("seiscentos", 600), ("seiscentas", 600),
               ("setecentos", 700), ("setecentas", 700), ("oitocentos", 800), ("oitocentas", 800),
               ("novecentos", 900), ("novecentas", 900)):
    _EXT[_w] = ("n", float(_v))
for _w, _v in (("mil", 1e3), ("milhao", 1e6), ("milhoes", 1e6), ("bilhao", 1e9), ("bilhoes", 1e9),
               ("trilhao", 1e12), ("trilhoes", 1e12)):
    _EXT[_w] = ("esc", _v)
_EXT["meio"] = _EXT["meia"] = ("meio", 0.5)

# Nomes de modelo: famílias conhecidas (com ou sem versão) e, de forma genérica, letra+dígito colados ou com hífen.
_FAMILIAS = (r"ChatGPT|GPT|Claude|Gemini|Gemma|LLaMA|Llama|Grok|Phi|Mistral|Mixtral|Codestral|Qwen|DeepSeek|Sora|Veo|"
             r"Imagen|Whisper|Codex|DALL[-·]E|Midjourney|Flux|Nova|Titan|Command|Kimi|GLM|Ernie|Copilot|Opus|Sonnet|"
             r"Haiku|Stable\s+Diffusion|SDXL|BERT|PaLM|Bard|AlphaGo|AlphaFold|AlphaZero")
_SUFIXOS = (r"Pro|Flash|Lite|Sonnet|Opus|Haiku|Mini|Nano|Turbo|Ultra|Max|Large|Medium|Small|Preview|Thinking|"
            r"Instant|Plus|Reasoner|Coder|Vision|Omni|High|Low|Fast|Heavy|mini|nano")
_VERSAO = (r"[ -]?[vV]?\d+(?:\.\d+)?[a-z]?(?![\d.,]*\d)"
           r"(?!\s*(?:%|mil\b|milh|bilh|trilh|por\s+cento|tokens?\b|d[óo]lar|reais\b|anos?\b|vezes\b))")
_RE_MODELO = re.compile(
    r"(?<![\w-])(?:"
    # família + até 2 palavras de linha ("Claude Opus 5.5", "Gemini 3.8 Flash") + versão + sufixos
    r"(?:" + _FAMILIAS + r")(?:[ -][A-Z][A-Za-z]+){0,2}" + _VERSAO + r"(?:[ -](?:" + _SUFIXOS + r")\b)*"
    # família sem versão ("Claude", "Gemini Flash")
    r"|(?:" + _FAMILIAS + r")(?:[ -](?:" + _SUFIXOS + r")\b)*"
    # família desconhecida: duas ou três palavras com maiúscula + versão com ponto ("Muse Spark 1.1")
    r"|[A-Z][A-Za-z]+(?: [A-Z][A-Za-z]+){1,2} \d{1,2}\.\d{1,2}(?![\d.,]*\d)(?:[ -](?:" + _SUFIXOS + r")\b)*"
    # letra e dígito colados ou com hífen ("GPT-4o", "o3-mini", "R1", "Qwen2.5")
    r"|[A-Za-z]{1,12}-?\d+(?:[.-]\d+)*[A-Za-z]{0,3}(?:-[A-Za-z0-9.]+)*"
    r")(?![\w])")
_SO_UNIDADE = re.compile(r"^(?:mp[34]|h26[45]|covid-?19|co2|h2o|3d|4k|8k)$", re.I)

_SUBST_IA = (r"modelos?|ia|ias|intelig[êe]ncias?\s+artificia(?:l|is)|chatbots?|llms?|empresas?|laborat[óo]rios?|"
             r"benchmarks?|redes?\s+neura(?:l|is)|assistentes?|sistemas?|chips?|gpus?|startups?")
_RE_SUBST_IA = re.compile(r"\b(?:" + _SUBST_IA + r")\b", re.I)
_RE_SUPERLATIVO = re.compile(
    r"\b(?:(?:o|a|os|as)\s+(?:melhor(?:es)?|maior(?:es)?|pior(?:es)?|primeir[oa]s?|[úu]nic[oa]s?|l[íi]der(?:es)?)\b"
    r"|(?:o|a|os|as)\s+mais\s+(?!de\b|que\b|ou\b|uma?\b)\w+"
    r"|(?:o|a|os|as)\s+(?:" + _SUBST_IA + r")(?:\s+de\s+\w+)?\s+mais\s+(?!de\b|que\b|ou\b)\w+"
    r"|mais\s+\w+\s+(?:do\s+(?:mundo|mercado|planeta|brasil)|da\s+hist[óo]ria|j[áa]\s+\w+|(?:do\s+)?que)\b"
    r"|melhor(?:es)?\s+(?:do\s+)?que\b|pior(?:es)?\s+(?:do\s+)?que\b|maior(?:es)?\s+(?:do\s+)?que\b"
    r"|que\s+mais\s+\w+(?:\s+\w+){0,3}?\s+(?:(?:na|da)\s+hist[óo]ria|do\s+(?:mundo|mercado|planeta|brasil))"
    r"|de\s+todos\s+os\s+tempos"
    r"|imbat[íi]ve(?:l|is)|insuper[áa]ve(?:l|is)|revolucion[áa]ri[oa]s?|sem\s+rival|estado\s+da\s+arte"
    r"|state[- ]of[- ]the[- ]art|super(?:a|ou|am|aram)\b|ultrapass(?:a|ou|am|aram)\b|derrot(?:a|ou)\b"
    r"|mais\s+recentes?|mais\s+nov[oa]s?|[úu]ltim[oa]\s+(?:vers[ãa]o|modelo|gera[çc][ãa]o)"
    r"|acab(?:a|ou|aram)\s+de\s+(?:lan[çc]ar|sair|ser\s+lan[çc]ad[oa]|anunciar)|rec[ée]m[- ]lan[çc]ad[oa]s?)",
    re.I)
_RE_PRIMEIRO_ESTRUTURAL = re.compile(
    r"\b(?:o|a|os|as)\s+(?:primeir[oa]s?|[úu]nic[oa]s?|maior(?:es)?|melhor(?:es)?|pior(?:es)?)\s+(?:" + _ESTRUTURAIS
    + r"|vez(?:es)?|dias?|semanas?|momentos?|lugar(?:es)?|contatos?|impress(?:ão|ões|ao|oes)|problemas?|desafios?"
    r"|diferen[çc]as?|vantage(?:m|ns)|riscos?|dúvidas?|duvidas?)\b",
    re.I)
_RE_RELATIVO = re.compile(
    r"\b(?:hoje(?:\s+em\s+dia)?|atualmente|agora|neste\s+momento|no\s+momento|recentemente|este\s+(?:m[êe]s|ano)|"
    r"esta\s+semana|semana\s+passada|m[êe]s\s+passado|ano\s+passado|ontem|h[áa]\s+pouco|atual)\b", re.I)

# tempo relativo que, junto de um nome, já é afirmação datável ("o Google anunciou ontem")
_RE_RELATIVO_FORTE = re.compile(
    r"\b(?:ontem|anteontem|recentemente|rec[ée]m|h[áa]\s+pouco|(?:n?es[st][ae]|[úu]ltim[oa]|pr[óo]xim[oa])\s+(?:semana|"
    r"m[êe]s|ano)|(?:semana|m[êe]s|ano)\s+passad[oa]|(?:faz|h[áa])\s+(?:\w+\s+){1,2}(?:dias?|semanas?|meses|m[êe]s|anos?)|"
    r"(?:dias?|semanas?|meses|m[êe]s|anos?)\s+atr[áa]s|nos\s+[úu]ltimos\s+(?:\w+\s+)?(?:dias|meses|anos)|"
    r"acab(?:a|ou|aram)\s+de)\b", re.I)
# verbos e expressões que fazem de uma frase com nome próprio uma afirmação sobre ele. FORTES: lançamento, preço,
# licença, autoria, compra, placar — exatamente o que caduca; frase assim sem marcador é pendência.
_RE_VERBO_AFIRMACAO = re.compile(
    r"\b(?:lan[çc](?:a|ou|aram|ar[áa]|ad[oa]s?|amento)|anunci(?:a|ou|aram|ad[oa]s?)|apresent(?:ou|aram|ad[oa]s?)|"
    r"liber(?:ou|aram|ad[oa]s?)|cri(?:ou|aram|ad[oa]s?)|invent(?:ou|aram|ad[oa]s?)|fund(?:ou|aram|ad[oa]s?)|"
    r"desenvolv(?:eu|eram|id[oa]s?)|trein(?:ou|aram|ad[oa]s?)|cust(?:a|am|ava|avam|ou|aram)|cobr(?:a|am|ava|avam|ou)|"
    r"pre[çc]os?|gr[áa]tis|gratuit[oa]s?|de\s+gra[çc]a|compr(?:ou|aram|ad[oa]s?)|adquir(?:iu|iram|id[oa]s?)|"
    r"invest(?:iu|iram|imento)|levant(?:ou|aram)|demit(?:iu|iram)|bat(?:e|eu|eram)|venc(?:e|eu|eram)|"
    r"super(?:a|ou|aram)|pass(?:ou|aram)\s+(?:o|a|os|as)\b|ganh(?:a|ou|aram)|perd(?:e|eu|eram)|lider(?:a|ou|am)|"
    r"aposent(?:ou|aram|ad[oa]s?)|descontinu(?:ou|aram|ad[oa]s?)|deslig(?:ou|aram|ad[oa]s?)|estre(?:ia|ou|aram)|"
    r"pertence|proib(?:iu|iram|id[oa]s?)|banid[oa]s?|process(?:ou|aram|ad[oa]s?)|open[- ]source|c[óo]digo\s+aberto|"
    r"pesos\s+abertos|licen[çc]a|propriet[áa]ri[oa]s?|[ée]\s+d[ao]s?|nov[oa]s?\s+(?:modelo|vers[ãa]o|gera[çc][ãa]o))\b",
    re.I)
# FRACOS: descrevem o que a ferramenta faz ("o ChatGPT escreve e-mails"); com nome próprio e sem marcador dão aviso
_RE_VERBO_FRACO = re.compile(
    r"\b(?:sai(?:u|r[áa]|ram)?|cheg(?:a|ou|aram)|l[êe]|lia|leem|escrev(?:e|ia|em)|ger(?:a|ou|am)|suport(?:a|am|ava)|"
    r"aceit(?:a|am|ava)|foi\s+\w+ad[oa])\b", re.I)
# fala em primeira pessoa e chamadas ("eu uso 10 vezes por dia", "comenta 1", "manda para 2 amigos"): número pequeno
# aí não é dado (vai para a lista de IGNORADOS do relatório)
_RE_PRIMEIRA_PESSOA = re.compile(
    r"\b(?:eu|me|mim|meus?|minhas?|comigo|a\s+gente|n[óo]s|noss[oa]s?)\b"
    r"|\b(?:sou|estou|tenho|uso|usei|fiz|gravei|testei|fa[çc]o|vou|quero|acho|penso|gosto|levei|demorei|aprendi|comecei|"
    r"trabalh(?:o|ei)|gastei|paguei|li|vi|recebi)\b", re.I)
_RE_CHAMADA = re.compile(
    r"\b(?:coment[ae]|salv[ae]|segu[ea]|sig[ao]|compartilh[ae]|mand[ae]|envi[ae]|marqu?[ae]|curt[ae]|deix[ae]|cliqu?[ae]|"
    r"inscrev[ae]-?se|ativ[ae]|digit[ae]|respond[ae]|guard[ae]|paus[ae]|anot[ae])\b|\blink\s+na\s+bio\b"
    r"|\bd[áa]\s+o\s+play\b|\bfi(?:ca|que)\s+(?:comigo|at[ée]|a[íi]|ligad[oa])\b", re.I)
# frase dirigida ao espectador ("você não precisa de 5 ferramentas" × "você sabia que só 5 países…?"): ambígua —
# o número pequeno vira AVISO, não some
_RE_SEGUNDA_PESSOA = re.compile(r"\b(?:voc[êe]s?|te|ti|teus?|tuas?|contigo)\b", re.I)
# analogia declarada ("imagina uma biblioteca com 1 milhão de livros"): o número é ilustração
_RE_HIPOTESE = re.compile(r"^\W*(?:imagin[ae]|pens[ae]\s+(?:em|n[oa]s?|numa?|que|assim)|suponh?a|sup[õo]e|digamos|"
                          r"faz\s+de\s+conta|[ée]\s+como\s+se|como\s+se)\b", re.I)
_RE_TECNICO = re.compile(
    r"\b(?:tokens?|par[âa]metros?|contexto|janela|prompts?|apis?|datasets?|trein(?:o|amento)|benchmarks?|gpus?|chips?|"
    r"servidor(?:es)?|data\s*centers?|usu[áa]rios?|assinantes?|funcion[áa]rios?|mercado|d[óo]lar(?:es)?|reais|"
    r"empresas?|modelos?|ia|ias|intelig[êe]ncias?\s+artificia(?:l|is)|chatbots?|llms?|startups?|laborat[óo]rios?)\b",
    re.I)

_INICIO_COMUM = set("""o a os as um uma em no na nos nas de do da dos das para por com sem se que quando como mas e ou ja
hoje so isso esse essa este esta ele ela eles elas voce eu nos nao sim entao porque segundo desde ate entre depois antes
cada todo toda quem qual quanto onde foi e sao tem ha mais menos muito pouco seu sua meu minha aqui agora la tambem ainda
nem pra pro ao aos num numa olha imagina pensa veja repare calma bom bem tipo ok pronto resultado detalhe exemplo resumo
spoiler fonte fontes tudo nada algo alguem ninguem toda todo quase cerca apenas existe existem funciona parece vamos
vai imagine pense agora durante enquanto apos sera talvez basta primeiro segundo terceiro por fim alias inclusive
na pratica ou seja quer dizer""".split())
_SIGLAS_COMUNS = {"IA", "AI", "LLM", "LLMS", "API", "APIS", "GPU", "GPUS", "CPU", "PC", "TV", "PDF", "URL", "CTA",
                  "DM", "OK", "FAQ", "RAM", "USB", "HD", "SSD", "APP", "BR", "PT", "VS", "CEO", "PS", "OBS",
                  "US", "USD", "BRL", "EUR"}
_ENTIDADES = set("""google meta anthropic microsoft apple amazon nvidia mistral claude gemini llama grok copilot sora siri
alexa turing tesla samsung intel amd ibm baidu alibaba tencent huawei bytedance tiktok instagram youtube facebook whatsapp
twitter perplexity cursor midjourney stanford mit harvard berkeley cambridge oxford wikipedia reddit github cohere
stability runway elevenlabs transformer transformers deepmind openai xai deepseek qwen chatgpt""".split())
_CONECTORES = {"de", "da", "do", "dos", "das", "of", "the", "von", "van", "di", "del"}
_RE_PALAVRA = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ][\wÀ-ÖØ-öø-ÿ'’·-]*")


def _valores_numericos(s: str, idioma: str = "pt") -> set:
    """Interpretações possíveis de um numeral escrito. '1.250' em PT é 1250; em texto estrangeiro pode ser 1,25."""
    s = s.replace("\u00a0", "").replace("\u202f", "")
    vals = set()
    try:
        if "," in s and "." in s:
            if s.rfind(",") > s.rfind("."):
                vals.add(float(s.replace(".", "").replace(",", ".")))
            else:
                vals.add(float(s.replace(",", "")))
        elif "," in s:
            partes = s.split(",")
            if all(len(p) == 3 for p in partes[1:]) and 1 <= len(partes[0]) <= 3:
                vals.add(float(s.replace(",", "")))               # 400,000 copiado de fonte em inglês
                if len(partes) == 2:
                    vals.add(float(s.replace(",", ".")))          # 1,250 decimal em PT
            else:
                vals.add(float(s.replace(",", ".")))
        elif "." in s:
            partes = s.split(".")
            if all(len(p) == 3 for p in partes[1:]) and 1 <= len(partes[0]) <= 3:
                vals.add(float(s.replace(".", "")))               # 400.000 em PT
                if len(partes) == 2 and idioma != "pt":
                    vals.add(float(s))                            # 1.250 decimal em inglês
            else:
                vals.add(float(s))
        else:
            vals.add(float(s))
    except ValueError:
        pass
    return vals


def _mascarar_modelos(texto: str, termos=()):
    """Tira do texto os nomes de modelo (o '4' de GPT-4 não é número a checar). → (texto mascarado, nomes)."""
    nomes = []

    def troca(m):
        bruto = m.group(0).strip()
        if _SO_UNIDADE.match(bruto) or not bruto:
            return m.group(0)
        nomes.append(bruto)
        return " " * len(m.group(0))

    for termo in sorted({t for t in termos if isinstance(t, str) and len(t.strip()) >= 2}, key=len, reverse=True):
        if re.search(r"[A-ZÀ-Ý]", termo) and not re.fullmatch(r"[\d.,\s%$]+", termo):
            texto = re.sub(r"(?<![\w-])" + re.escape(termo.strip()) + r"(?![\w])", troca, texto)
    texto = _RE_MODELO.sub(troca, texto)
    return texto, nomes


def apelidos_de_modelo(nomes) -> list:
    """Formas curtas aceitas de um nome registrado: 'Claude Fable 5.1' → 'Fable 5.1' (última palavra + versão)."""
    saida = []
    for nome in nomes:
        partes = str(nome).split()
        for k in range(1, len(partes)):
            resto = partes[k:]
            curto = " ".join(resto)
            if len(resto) >= 2 and resto[0][:1].isupper() and any(c.isdigit() for c in curto) and curto not in saida:
                saida.append(curto)
    return saida


def nomes_da_ficha(ficha: dict) -> list:
    """Nomes de modelo e termos que a ficha ensina (termos + nomes achados em afirmacao/como_dizer + apelidos).

    Vêm ANTES da lista de famílias embutida: família nova entra no cruzamento assim que um fato a registra."""
    nomes = []
    for f in ficha.get("fatos", []) if isinstance(ficha, dict) else []:
        if not isinstance(f, dict):
            continue
        termos = [t for t in _termos(f) if re.search(r"[A-ZÀ-Ý]", t)]
        _, achados = _mascarar_modelos(" . ".join(_txt(f.get(k)) for k in ("afirmacao", "como_dizer")), termos)
        for n in termos + achados:
            if n and n not in nomes:
                nomes.append(n)
    for n in apelidos_de_modelo(nomes):
        if n not in nomes:
            nomes.append(n)
    return nomes


def _moeda_norm(txt) -> str | None:
    """'US$' → 'USD' · 'reais' → 'BRL' · 'centavos' → None (subunidade: a moeda vem do contexto)."""
    n = normalizar(txt or "") or (txt or "").strip()
    bruto = (txt or "").strip().upper()
    if bruto in ("US$", "U$S", "USD", "$") or n.startswith(("dolar", "dollar")):
        return "USD"
    if bruto in ("R$", "BRL") or n in ("reais", "real"):
        return "BRL"
    if bruto in ("€", "EUR") or n.startswith("euro"):
        return "EUR"
    if bruto in ("£", "GBP") or n.startswith("libra"):
        return "GBP"
    return None


def _item(tipo, bruto, valores, **extra) -> dict:
    return {"tipo": tipo, "bruto": re.sub(r"\s+", " ", bruto).strip(), "valores": sorted(valores), **extra}


def _extrair_datas(t: str, original: str, idioma: str, achados: list) -> str:
    """Acha datas em `t`, registra itens tipo 'data' e devolve `t` com as datas apagadas (mesmo comprimento)."""
    def dia_extenso(m):
        txt = normalizar(m.group(1))
        dia = 1 if txt == "primeiro" else _valor_extenso(txt.split())
        achados.append((m.start(), _item("data", original[m.start():m.end()], [], dia=int(dia),
                                         mes=_MES_NUM[normalizar(m.group(2))], ano=int(m.group(3)) if m.group(3) else None)))
        return " " * len(m.group(0))

    t = _RE_DATA_DIA_EXTENSO.sub(dia_extenso, t)
    for rx, gd, gm, ga, so_estrangeiro in _PADROES_DATA:
        if so_estrangeiro and idioma == "pt":
            continue

        def troca(m, gd=gd, gm=gm, ga=ga):
            mes_txt = m.group(gm)
            mes = int(mes_txt) if mes_txt.isdigit() else _MES_NUM.get(normalizar(mes_txt))
            dia = int(m.group(gd)) if gd and m.group(gd) else None
            ano = int(m.group(ga)) if ga and m.group(ga) else None
            if not mes or not 1 <= mes <= 12 or (dia is not None and not 1 <= dia <= 31) \
                    or (ano is not None and not 1000 <= ano <= 2999):
                return m.group(0)
            achados.append((m.start(), _item("data", original[m.start():m.end()], [], dia=dia, mes=mes, ano=ano)))
            return " " * len(m.group(0))

        t = rx.sub(troca, t)
    return t


def _valor_extenso(ws: list) -> float | None:
    """['dois', 'mil', 'e', 'dezessete'] → 2017.0; None se a sequência não é um numeral ('cento', 'meio')."""
    total = grupo = 0.0
    tem, ultima_escala = False, None
    for k, w in enumerate(ws):
        tipo, v = _EXT[w]
        if tipo == "e":
            continue
        if tipo == "meio":
            prox = next((x for x in ws[k + 1:] if x != "e"), None)
            if prox and _EXT[prox][0] == "esc":
                grupo += 0.5                                      # meio milhão
                tem = True
            elif ultima_escala and k > 0 and ws[k - 1] == "e" and grupo == 0:
                total += 0.5 * ultima_escala                      # um milhão e meio
            else:
                return None
        elif tipo == "esc":
            total += (grupo if grupo else 1.0) * v
            grupo, ultima_escala, tem = 0.0, v, True
        else:
            grupo += v
            tem = True
    if not tem or ws == ["cento"]:
        return None
    return total + grupo


def _extrair_extenso(t: str, original: str, tudo: bool, achados: list) -> str:
    """Numerais por extenso → itens (dinheiro, percentual, proporcao, data, ano, numero). Devolve `t` mascarado."""
    toks = [(m.start(), m.end(), normalizar(m.group(0))) for m in _RE_PALAVRA.finditer(t)]
    apagar = []
    i = 0
    while i < len(toks):
        w = toks[i][2]
        if w not in _EXT or w == "e":
            i += 1
            continue
        j = i + 1
        while j < len(toks) and not t[toks[j - 1][1]:toks[j][0]].strip():
            wj = toks[j][2]
            if wj == "e":
                if j + 1 < len(toks) and toks[j + 1][2] in _EXT and toks[j + 1][2] != "e" \
                        and not t[toks[j][1]:toks[j + 1][0]].strip():
                    j += 1
                    continue
                break
            if wj not in _EXT:
                break
            j += 1
        seq = toks[i:j]
        while seq and seq[-1][2] == "e":
            seq = seq[:-1]
        ws = [x[2] for x in seq]
        valor = _valor_extenso(ws)
        prox_i = i + len(seq)
        ini, fim = (seq[0][0], seq[-1][1]) if seq else (toks[i][0], toks[i][1])
        # "400 mil", "1 milhão e meio": a escala depois de dígito é multiplicador (caminho dos dígitos);
        # "por milhão de tokens": escala sozinha é denominador ou quantidade vaga, não um numeral
        so_escala = len(ws) == 1 and _EXT[ws[0]][0] == "esc" and ws[0] != "mil"
        apos_digito = bool(ws) and _EXT[ws[0]][0] == "esc" and bool(re.search(r"\d\s*$", t[:ini]))
        if valor is None or so_escala or apos_digito:
            i = max(prox_i, i + 1)
            continue
        antes, depois = t[max(0, ini - 16):ini], t[fim:fim + 48]
        me = _RE_E_MEIO_DEPOIS.match(depois) if _EXT[ws[-1]][0] == "esc" else None
        if me:                                                    # (já coberto quando "meio" entrou na sequência)
            valor += 0.5 * _EXT[ws[-1]][1]
            fim += me.end()
            depois = t[fim:fim + 48]
        sozinho_um = ws in (["um"], ["uma"])
        pequeno = len(ws) == 1 and 2 <= valor <= 10
        item = None
        mc = _RE_EM_CADA_DEPOIS.match(depois)
        moeda_d = _RE_MOEDA_DEPOIS.match(depois)
        pct = _RE_PCT_DEPOIS.match(depois)
        if mc:
            resto = t[fim + mc.end():fim + mc.end() + 60]
            den, tam = None, 0
            mnum = re.match(r"\d+", resto)
            if mnum:
                den, tam = float(mnum.group(0)), mnum.end()
            else:
                rs = [(m.start(), m.end(), normalizar(m.group(0))) for m in _RE_PALAVRA.finditer(resto)]
                k = 0
                while k < len(rs) and rs[k][2] in _EXT and (k == 0 and not resto[:rs[0][0]].strip()
                                                            or k > 0 and not resto[rs[k - 1][1]:rs[k][0]].strip()):
                    k += 1
                if k:
                    den, tam = _valor_extenso([x[2] for x in rs[:k]]), rs[k - 1][1]
            if den:
                fim += mc.end() + tam
                item = _item("proporcao", original[ini:fim], [valor / den])
        if item is None and moeda_d:
            fim += moeda_d.end()
            moeda = _moeda_norm(moeda_d.group(1))
            if moeda is None:                                     # centavos
                valor = valor / 100.0
                mm = _RE_MOEDA_DO_CENTAVO.match(t[fim:fim + 24])
                if mm:
                    moeda, fim = _moeda_norm(mm.group(1)), fim + mm.end()
            item = _item("dinheiro", original[ini:fim], [valor], moeda=moeda)
        elif item is None and pct:
            fim += pct.end()
            item = _item("percentual", original[ini:fim], [valor])
        elif item is None and (_RE_VEZES_DEPOIS.match(depois) or (
                _RE_VEZES_SIMPLES.match(depois) and _RE_VERBO_MUDANCA.search(t[max(0, ini - 48):ini]))):
            fim += re.match(r"^(?:\s+vezes|\s?x)", depois, re.I).end()
            item = _item("proporcao", original[ini:fim], [valor])
        elif item is None and not sozinho_um:
            if not tudo and (_RE_ESTRUTURAL_DEPOIS.match(depois) or _RE_ESTRUTURAL_ANTES.search(antes)):
                apagar.append((ini, fim))
                i = max(prox_i, i + 1)
                continue
            if pequeno and not tudo and _RE_REFERENCIA_ANTES.search(antes):
                apagar.append((ini, fim))                         # "os dois modelos", "esses três": referência
                i = max(prox_i, i + 1)
                continue
            tipo = "ano" if len(ws) > 1 and float(valor).is_integer() and 1900 <= valor <= 2100 else "numero"
            item = _item(tipo, original[ini:fim], [valor])
            if pequeno:
                item["pequeno"] = True
        if item is not None:
            item["extenso"] = True
            achados.append((ini, item))
            apagar.append((ini, fim))
        i = max(prox_i, i + 1)
        while i < len(toks) and toks[i][0] < fim:                 # o que o item consumiu ("… em cada quatro")
            i += 1
    for a, b in apagar:
        t = t[:a] + " " * (b - a) + t[b:]
    return t


def extrair_numeros(texto: str, idioma: str = "pt", tudo: bool = False, termos=()) -> list:
    """Dados numéricos do texto: [{'tipo', 'bruto', 'valores', …}], na ordem em que aparecem.

    tipos: dinheiro (com 'moeda': USD | BRL | EUR | GBP | None) · percentual · ano · numero · proporcao ("metade",
    "3 vezes mais", "3 em cada 4") · data ('dia', 'mes', 'ano'; 'valores' vazio). Lê dígitos e numerais por extenso.
    `tudo=True` não descarta contagens editoriais ("3 motivos") nem durações — usado para indexar a ficha."""
    texto = re.sub(r"https?://\S+", " ", texto or "")
    t, _ = _mascarar_modelos(texto, termos)
    achados = []
    t = _extrair_datas(t, texto, idioma, achados)
    for rx, v in _RE_FRACOES:
        def troca(m, v=v):
            achados.append((m.start(), _item("proporcao", texto[m.start():m.end()], [v])))
            return " " * len(m.group(0))
        t = rx.sub(troca, t)
    t = _extrair_extenso(t, texto, tudo, achados)
    if not tudo:
        t = _RE_FAIXA_TEMPO.sub(lambda m: " " * len(m.group(0)), t)       # "0–3s", "45–60s": minutagem
    pular_ate = -1
    for m in _RE_NUM.finditer(t):
        if m.start() < pular_ate:
            continue
        bruto_num = m.group(1)
        antes, depois = t[max(0, m.start() - 16):m.start()], t[m.end():m.end() + 48]
        if re.match(r"^:\d\d", depois) or re.search(r"\d:$", antes):
            continue                                              # horário / minutagem
        ini, fim = m.start(), m.end()
        vals = _valores_numericos(bruto_num, idioma)
        if not vals:
            continue
        mult = 1.0
        ml = _RE_MULT_LETRA.match(depois)
        mp = None if ml else _RE_MULT_PALAVRA.match(depois)
        if ml:
            mult, fim = _MULT[ml.group(1).lower()], fim + ml.end()
        elif mp:
            chave = normalizar(mp.group(1))
            chave = {"milhao": "million", "milhoes": "million", "bilhao": "billion", "bilhoes": "billion",
                     "trilhao": "trillion", "trilhoes": "trillion"}.get(chave, chave)
            mult, fim = _MULT[chave], fim + mp.end()
        elif not tudo and _RE_UNIDADE_IGNORADA.match(depois):
            continue                                              # 40s, 1080p, 60fps, 3D, 1º
        mudanca = bool(_RE_VERBO_MUDANCA.search(t[max(0, m.start() - 48):m.start()]))
        if not tudo and re.match(r"^x(?![A-Za-zÀ-ÿ0-9])", depois) and not _RE_VEZES_DEPOIS.match(depois) and not mudanca:
            continue                                              # "dá o play em 1,5x": velocidade, não comparação
        vals = {v * mult for v in vals}
        resto = t[fim:fim + 48]
        me = _RE_E_MEIO_DEPOIS.match(resto) if mult > 1 else None
        if me:                                                    # "1 milhão e meio"
            vals = {v + 0.5 * mult for v in vals}
            fim += me.end()
            resto = t[fim:fim + 48]
        moeda_a = _RE_MOEDA_ANTES.search(antes)
        moeda_d = _RE_MOEDA_DEPOIS.match(resto)
        pct = _RE_PCT_DEPOIS.match(resto)
        mc = _RE_EM_CADA_DEPOIS.match(resto)
        mden = re.match(r"\d+", t[fim + mc.end():fim + mc.end() + 12]) if mc else None
        extra = {}
        if mden and float(mden.group(0)):                         # "3 em cada 4"
            fim += mc.end() + mden.end()
            pular_ate = fim
            tipo, vals = "proporcao", {v / float(mden.group(0)) for v in vals}
        elif moeda_a or moeda_d:
            tipo = "dinheiro"
            moeda = _moeda_norm(moeda_a.group(1)) if moeda_a else None
            if moeda_a:
                ini = m.start() - (len(antes) - moeda_a.start())
            if moeda_d:
                fim += moeda_d.end()
                md = _moeda_norm(moeda_d.group(1))
                if md is None and normalizar(moeda_d.group(1)).startswith("cent"):
                    vals = {v / 100.0 for v in vals}              # 75 centavos = 0,75
                    mm = _RE_MOEDA_DO_CENTAVO.match(t[fim:fim + 24])
                    if mm:
                        md, fim = _moeda_norm(mm.group(1)), fim + mm.end()
                moeda = moeda or md
            extra["moeda"] = moeda
        elif pct:
            if not tudo and _RE_PCT_ENFASE.match(t[fim + pct.end():fim + pct.end() + 24]):
                continue                                          # "100% gratuito"
            tipo, fim = "percentual", fim + pct.end()
        elif _RE_VEZES_DEPOIS.match(resto) or (mudanca and _RE_VEZES_SIMPLES.match(resto)):
            tipo, fim = "proporcao", fim + re.match(r"^(?:\s+vezes|\s?x)", resto, re.I).end()
        elif mult == 1.0 and re.fullmatch(r"(?:19|20)\d{2}", bruto_num):
            tipo = "ano"
        else:
            tipo = "numero"
        if not tudo and tipo == "numero":
            if _RE_ESTRUTURAL_DEPOIS.match(resto) or _RE_ESTRUTURAL_ANTES.search(antes):
                continue
        achados.append((ini, _item(tipo, texto[ini:fim], vals, **extra)))
    achados.sort(key=lambda x: x[0])
    return [it for _, it in achados]


def _nome_forte(w: str) -> bool:
    """Palavra que é nome mesmo abrindo a frase: CamelCase, sigla ou entidade conhecida."""
    return bool(re.search(r"[a-zà-ÿ][A-ZÀ-Ý]", w)) or bool(re.fullmatch(r"x?AI|[A-ZÀ-Ý]{2,}s?", w)) \
        or normalizar(w) in _ENTIDADES


def extrair_nomes(texto: str) -> list:
    """Nomes próprios candidatos (heurística): sequências de palavras com inicial maiúscula, CamelCase e siglas.

    Palavra maiúscula que só abre a frase não conta, a menos que seja CamelCase, sigla ou entidade conhecida."""
    letras = [c for c in texto if c.isalpha()]
    if letras and sum(c.isupper() for c in letras) / len(letras) > 0.7:
        return []                                                 # frase toda em caixa alta: não dá para inferir
    sequencias, atual = [], []
    pos, primeiro = 0, True
    for m in _RE_PALAVRA.finditer(texto):
        w, sep = m.group(0), texto[pos:m.start()]
        pos = m.end()
        quebra = bool(re.search(r"[,;:()\[\]\"“”‘«»!?…—–/]|\.(?:\s|$)", sep))
        inicio = primeiro or bool(re.search(r"[.!?…:]\s*[\"“‘«(]*\s*$|[\"“‘«]\s*$|\s[—–]\s*$", sep))
        primeiro = False
        sigla_comum = bool(re.fullmatch(r"[A-ZÀ-Ý]{2,}s?", w)) and (w.upper() in _SIGLAS_COMUNS
                                                                    or w.upper().rstrip("S") in _SIGLAS_COMUNS)
        maiuscula = w[0].isupper() and len(w) > 1 and not sigla_comum
        if quebra and atual:
            sequencias.append(atual)
            atual = []
        if maiuscula:
            atual.append((w, inicio))
        elif atual and normalizar(w) in _CONECTORES:
            atual.append((w, False))                              # "Universidade de Toronto": decide no fechamento
        elif atual:
            sequencias.append(atual)
            atual = []
    if atual:
        sequencias.append(atual)
    nomes = []
    for seq in sequencias:
        while seq and not seq[-1][0][0].isupper():
            seq.pop()                                             # conector solto no fim
        if not seq:
            continue
        w0, abre_frase = seq[0]
        if abre_frase and not _nome_forte(w0):
            if normalizar(w0) in _INICIO_COMUM:
                seq = seq[1:]
                while seq and not seq[0][0][0].isupper():
                    seq = seq[1:]
            elif sum(1 for w, _ in seq if w[0].isupper()) < 2:
                continue                                          # "Modelos de linguagem…": só abre a frase
        if not seq:
            continue
        nome = " ".join(w for w, _ in seq)
        if nome not in nomes:
            nomes.append(nome)
    return nomes


def analisar_frase(frase: str, termos=(), aceitos=()) -> dict:
    """O que há de checável numa frase do roteiro.

    `termos`: nomes de modelo conhecidos (da ficha). `aceitos`: formas literais que os fatos citados na frase declaram
    equivalentes ao próprio valor ("75 centavos") — saem da frase antes de extrair os números.
    → {'fortes': dados numéricos + superlativos, 'modelos', 'nomes', 'relativos', 'relativos_fortes', 'versionados',
       'afirma': há verbo forte (lançamento, preço, licença, autoria…), 'afirma_fraca': só verbo que descreve uso,
       'ignorados': números de fala em primeira pessoa, chamada ou analogia declarada,
       'diretos': números pequenos em frase dirigida ao espectador ("você…") — ambíguos}"""
    limpa = re.sub(r"https?://\S+", " ", frase)
    para_numeros = limpa
    for forma in sorted({a.strip() for a in aceitos if isinstance(a, str) and len(a.strip()) >= 2}, key=len, reverse=True):
        para_numeros = re.sub(r"(?<![\w-])" + re.escape(forma) + r"(?![\w])", lambda m: " " * len(m.group(0)),
                              para_numeros, flags=re.I)
    mascarada, modelos = _mascarar_modelos(limpa, termos)
    fortes = extrair_numeros(para_numeros, "pt", termos=termos)
    sem_moeda = re.sub(r"(?:US\$|U\$S|R\$)", "  ", mascarada)
    nomes = [n for n in extrair_nomes(sem_moeda) if n not in modelos]
    tem_assunto = bool(modelos or nomes or _RE_SUBST_IA.search(limpa))
    # "os dois", "as três coisas": numeral pequeno por extenso só é dado quando a frase fala de alguém ou de IA
    fortes = [it for it in fortes if not (it.get("pequeno") and not tem_assunto)]
    ignorados, diretos = [], []
    primeira = bool(_RE_PRIMEIRA_PESSOA.search(limpa) or _RE_CHAMADA.search(limpa))
    hipotese = bool(_RE_HIPOTESE.search(limpa))
    segunda = bool(_RE_SEGUNDA_PESSOA.search(limpa))
    if (primeira or hipotese or segunda) and not (modelos or nomes) and not _RE_TECNICO.search(limpa):
        fica = []
        for it in fortes:
            leve = (it["tipo"] == "numero" and all(float(v).is_integer() and 0 <= v <= 100 for v in it["valores"])) \
                or (it["tipo"] == "data" and it.get("dia") is None and it.get("ano") is None) \
                or (hipotese and it["tipo"] == "numero")
            (fica if not leve else ignorados if (primeira or hipotese) else diretos).append(it)
        fortes = fica
    sem_estrutural = _RE_PRIMEIRO_ESTRUTURAL.sub(" ", limpa)
    if tem_assunto:
        vistos = set()
        for m in _RE_SUPERLATIVO.finditer(sem_estrutural):
            bruto = re.sub(r"\s+", " ", m.group(0)).strip()
            if bruto.lower() not in vistos:
                vistos.add(bruto.lower())
                fortes.append({"tipo": "superlativo", "bruto": bruto, "valores": []})
    relativos = sorted({re.sub(r"\s+", " ", m.group(0)).lower() for m in _RE_RELATIVO.finditer(limpa)})
    rel_fortes = sorted({re.sub(r"\s+", " ", m.group(0)).lower() for m in _RE_RELATIVO_FORTE.finditer(limpa)})
    return {"fortes": fortes, "modelos": modelos, "nomes": nomes, "relativos": relativos,
            "relativos_fortes": rel_fortes, "versionados": [m for m in modelos if any(c.isdigit() for c in m)],
            "afirma": bool(_RE_VERBO_AFIRMACAO.search(mascarada)),
            "afirma_fraca": bool(_RE_VERBO_FRACO.search(mascarada)), "ignorados": ignorados, "diretos": diretos}


def _palavras_de_conteudo(texto: str) -> set:
    return {w for w in normalizar(texto).split() if len(w) >= 4 and w not in _STOP_PT and not w.isdigit()}


_RE_MULT_NA_UNIDADE = re.compile(r"(?<![\d\s])\s*\b(mil|milh(?:ão|ões|ao|oes)|bilh(?:ão|ões|ao|oes)|trilh(?:ão|ões|ao|oes))\b"
                                 r"|^\s*(mil|milh(?:ão|ões|ao|oes)|bilh(?:ão|ões|ao|oes)|trilh(?:ão|ões|ao|oes))\b", re.I)


def _anolike(valores) -> bool:
    return any(float(v).is_integer() and 1900 <= v <= 2100 for v in valores)


def itens_do_valor(f: dict) -> list:
    """O campo `valor` como dado tipado: a `unidade` diz se é dinheiro (e a moeda), percentual ou contagem."""
    v = f.get("valor")
    unidade = _txt(f.get("unidade")).strip()
    if v is None or isinstance(v, bool):
        return []
    if isinstance(v, str):
        return extrair_numeros(f"{v} {unidade}".strip(), "pt", tudo=True, termos=_termos(f))
    if not isinstance(v, (int, float)):
        return []
    e_pct = bool(re.match(r"^\s*(?:%|por\s+cento|percent|pontos?\s+percentua)", unidade, re.I))
    cabeca = "" if e_pct else re.split(r"\s+por\s+|\s*/\s*|\s+a\s+cada\s+", unidade, maxsplit=1)[0]
    vals = {float(v)}
    mm = _RE_MULT_NA_UNIDADE.search(cabeca)
    if mm:
        chave = normalizar(mm.group(1) or mm.group(2))
        vals.add(float(v) * {"mil": 1e3, "milhao": 1e6, "milhoes": 1e6, "bilhao": 1e9, "bilhoes": 1e9,
                             "trilhao": 1e12, "trilhoes": 1e12}[chave])
    mo = _RE_MOEDA_QUALQUER.search(cabeca)
    bruto = f"{v} {unidade}".strip()
    if mo:
        return [_item("dinheiro", bruto, vals, moeda=_moeda_norm(mo.group(0)))]
    if e_pct or _RE_PCT_QUALQUER.search(cabeca):
        return [_item("percentual", bruto, vals)]
    if not unidade and _anolike(vals):
        return [_item("ano", bruto, vals)]
    return [_item("numero", bruto, vals)]


def indexar_fato(f: dict) -> dict:
    """Dados de um fato separados por PAPEL, para cruzar com frases do roteiro por tipo (dinheiro com dinheiro…).

    fortes = o que o roteiro pode dizer (valor, como_dizer, termos) · apoio = contexto (afirmacao, referente_a,
    unidade, data de publicação das fontes) · trecho = só o que está na citação da fonte (não valida frase)."""
    termos = _termos(f)
    ext = lambda t, idioma="pt": extrair_numeros(_txt(t), idioma, tudo=True, termos=termos) if t else []  # noqa: E731
    fontes = _fontes(f)
    valor_itens = itens_do_valor(f)
    como_dizer = _txt(f.get("como_dizer"))
    fortes = list(valor_itens) + ext(como_dizer)
    for t in termos:
        fortes += ext(t)
    apoio = ext(f.get("referente_a")) + ext(f.get("unidade"))
    for s in fontes:
        d = ler_data(s.get("publicado_em"))
        if d:
            apoio.append(_item("data", s["publicado_em"], [], dia=d.day, mes=d.month, ano=d.year))
    (fortes if not como_dizer.strip() else apoio).extend(ext(f.get("afirmacao")))   # sem como_dizer, vale a afirmação
    trecho = [it for s in fontes for it in ext(s.get("trecho"), "ambos")]
    valor = f.get("valor")
    valor_tipo = valor_itens[0]["tipo"] if valor_itens and isinstance(valor, (int, float)) \
        and not isinstance(valor, bool) else None
    pt = [_txt(f.get(k)) for k in ("afirmacao", "como_dizer", "referente_a", "unidade")] + termos
    if isinstance(valor, str):
        pt.append(valor)
    estrangeiro = [_txt(s.get("trecho")) for s in fontes]
    texto = " ".join(pt + estrangeiro + [_txt(s.get("editor")) for s in fontes] + [_txt(s.get("titulo")) for s in fontes])
    return {"fortes": fortes, "apoio": apoio, "trecho": trecho, "valor_tipo": valor_tipo,
            "valor_itens": valor_itens if valor_tipo else [],
            "numeros": {v for it in fortes + apoio for v in it["valores"]},
            "texto": " " + normalizar(texto) + " ", "palavras": _palavras_de_conteudo(" ".join(pt))}


def _bate(valores, numeros) -> bool:
    return any(abs(v - n) <= 1e-9 * max(1.0, abs(n)) for v in valores for n in numeros)


def _assinatura(itens) -> set:
    """Os dados de uma lista de itens como conjunto comparável: valores numéricos + datas (dia, mês, ano)."""
    s = set()
    for it in itens:
        if it["tipo"] == "data":
            s.add(("data", it.get("dia"), it.get("mes"), it.get("ano")))
        else:
            s.update(it["valores"])
    return s


def _tipos_compativeis(it: dict, alvo: dict) -> bool:
    t, ta = it["tipo"], alvo["tipo"]
    if t == "livre":                                              # número de params sem prefixo nem unidade
        return ta != "data"
    if t == ta:
        if t == "dinheiro":
            ma, mb = it.get("moeda"), alvo.get("moeda")
            return ma is None or mb is None or ma == mb
        return True
    return {t, ta} == {"ano", "numero"} and _anolike(it["valores"])   # "2000 tokens" × "em 2000": só valor com cara de ano


def _item_em(it: dict, alvos: list, todos: list | None = None) -> bool:
    """O dado `it` da frase está entre os dados `alvos` do fato? Compara por tipo; data se compara como data."""
    if it["tipo"] == "data":
        anos = {a["ano"] for a in (todos or alvos) if a["tipo"] == "data" and a.get("ano")} \
            | {int(v) for a in (todos or alvos) if a["tipo"] in ("ano", "numero") for v in a["valores"] if _anolike([v])}
        for a in alvos:
            if a["tipo"] != "data" or a.get("mes") != it.get("mes"):
                continue
            if it.get("dia") is not None and a.get("dia") != it["dia"]:
                continue
            if it.get("ano") is not None and (a.get("ano") != it["ano"] if a.get("ano") is not None
                                              else it["ano"] not in anos):
                continue
            return True
        return False
    for a in alvos:
        if a["tipo"] == "data":
            if it["tipo"] == "ano" and a.get("ano") is not None and _bate(it["valores"], [float(a["ano"])]):
                return True
            continue
        if _tipos_compativeis(it, a) and _bate(it["valores"], a["valores"]):
            return True
    return False


def situacao_do_item(it: dict, indice: dict) -> str:
    """'ok' · 'apoio' (está na afirmacao, mas como OUTRO dado do mesmo tipo do valor) · 'trecho' (só na citação da
    fonte) · 'trecho_valor' (só na citação e do mesmo tipo do valor: é outro dado) · 'fora'."""
    todos = indice["fortes"] + indice["apoio"]
    if _item_em(it, indice["fortes"], todos):
        return "ok"
    if _item_em(it, indice["apoio"], todos):
        mesmo_tipo = indice["valor_tipo"] is not None and it["tipo"] != "data" and any(
            _tipos_compativeis(it, v) for v in indice["valor_itens"])
        return "apoio" if mesmo_tipo else "ok"
    if _item_em(it, indice["trecho"]):
        mesmo_tipo = indice["valor_tipo"] is not None and it["tipo"] != "data" and any(
            _tipos_compativeis(it, v) for v in indice["valor_itens"])
        return "trecho_valor" if mesmo_tipo else "trecho"
    return "fora"


def _nome_no_fato(nome: str, indice: dict) -> bool:
    n = normalizar(nome)
    return bool(n) and (" " + n + " ") in indice["texto"]


# ----------------------------------------------------------------------------- validação
def _ach(lista, fid, campo, mensagem):
    lista.append({"id": fid, "campo": campo, "mensagem": mensagem})


def _url_ok(url) -> str | None:
    """None se a URL serve; senão o motivo."""
    if not isinstance(url, str) or not url.strip():
        return "URL vazia"
    if url != url.strip() or re.search(r"\s", url):
        return "URL com espaço"
    p = urllib.parse.urlsplit(url)
    if p.scheme != "https":
        return f"URL precisa ser https (veio {p.scheme or 'sem esquema'}://)"
    if not p.hostname or "." not in p.hostname:
        return "URL sem domínio válido"
    return None


def dominio_registravel(url) -> str:
    """'https://www.blog.exemplo.com.br/x' → 'exemplo.com.br' (sem lista pública de sufixos: cobre os casos comuns)."""
    host = (urllib.parse.urlsplit(url).hostname or "") if isinstance(url, str) else ""
    partes = host.lower().split(".")
    if len(partes) >= 3 and ".".join(partes[-2:]) in _SUFIXOS_2N:
        return ".".join(partes[-3:])
    return ".".join(partes[-2:]) if len(partes) >= 2 else host.lower()


def marca_da_fonte(s: dict) -> str:
    """Impressão digital de (url, trecho): a conferência só vale para o par que foi de fato conferido."""
    bruto = _txt(s.get("url")).strip() + "\n" + normalizar(_txt(s.get("trecho")))
    return hashlib.sha1(bruto.encode("utf-8")).hexdigest()[:12]


def conferencia_da_fonte(s: dict) -> dict | None:
    """A conferência registrada da fonte, se ainda vale para a url e o trecho atuais; senão None (nunca conferida)."""
    c = s.get("conferencia") if isinstance(s, dict) else None
    if not isinstance(c, dict) or c.get("estado") not in CONFERENCIAS or ler_data(c.get("em")) is None:
        return None
    if c.get("marca") != marca_da_fonte(s):
        return None                                               # a url ou o trecho mudaram depois da conferência
    return c


def conferencia_do_fato(f: dict) -> dict:
    """Situação dos trechos de um fato. → {'ok', 'encontrados', 'manuais', 'ausentes', 'nao_verificados', 'nunca'}
    (listas com o número de ordem das fontes, base 1). 'ok' = há fonte e todas têm trecho encontrado ou conferência
    manual declarada."""
    r = {"encontrados": [], "manuais": [], "ausentes": [], "nao_verificados": [], "nunca": []}
    chave = {"encontrado": "encontrados", "manual": "manuais", "ausente": "ausentes", "nao_verificado": "nao_verificados"}
    fontes = _fontes(f)
    for i, s in enumerate(fontes, 1):
        c = conferencia_da_fonte(s)
        r[chave[c["estado"]] if c else "nunca"].append(i)
    r["ok"] = bool(fontes) and not (r["ausentes"] or r["nao_verificados"] or r["nunca"])
    return r


def _secundarias_independentes(secundarias: list) -> int:
    """Quantas fontes secundárias contam: 2 se há um par com editor E domínio diferentes; senão 1 ou 0.

    A mesma página registrada duas vezes (ou dois "editores" no mesmo domínio) é uma fonte só."""
    for i, (ed_a, dom_a, url_a) in enumerate(secundarias):
        for ed_b, dom_b, url_b in secundarias[i + 1:]:
            if ed_a != ed_b and dom_a != dom_b and url_a != url_b:
                return 2
    return 1 if secundarias else 0


def validar_fato(f, hoje: dt.date | None = None):
    """→ (erros, avisos): listas de {'id', 'campo', 'mensagem'}."""
    hoje = hoje or hoje_local()
    erros, avisos = [], []
    if not isinstance(f, dict):
        _ach(erros, "?", "", "o fato não é um objeto JSON")
        return erros, avisos
    fid = f.get("id") if isinstance(f.get("id"), str) else "?"
    if not re.fullmatch(r"F\d{3,}", str(f.get("id", ""))):
        _ach(erros, fid, "id", f"id inválido ({f.get('id')!r}): o formato é F001, F002… (atribuído por `adicionar`)")
    for campo in CAMPOS_FATO:
        if campo not in f:
            _ach(erros, fid, campo, f"campo obrigatório ausente: {campo}")

    afirmacao = f.get("afirmacao")
    if "afirmacao" in f:
        if not isinstance(afirmacao, str) or not afirmacao.strip():
            _ach(erros, fid, "afirmacao", "afirmacao vazia: escreva uma frase completa e verificável")
        elif contar_palavras(afirmacao) < 4:
            _ach(avisos, fid, "afirmacao", "afirmacao curta demais para ser verificável sozinha: escreva a frase inteira "
                                           "(quem, o quê, quanto, quando)")
    valor = f.get("valor")
    if valor is not None and (isinstance(valor, bool) or not isinstance(valor, (int, float, str))):
        _ach(erros, fid, "valor", "valor deve ser null, número ou texto")
    if f.get("unidade") is not None and not isinstance(f.get("unidade"), str):
        _ach(erros, fid, "unidade", "unidade deve ser null ou texto (ex.: \"tokens\", \"US$ por 1M de tokens\")")
    if "referente_a" in f and (not isinstance(f.get("referente_a"), str) or not f["referente_a"].strip()):
        _ach(erros, fid, "referente_a", "referente_a vazio: diga a data ou o período a que o fato se refere "
                                        "(ex.: \"junho de 2017\", \"2026-10-06\")")
    for campo, opcoes in (("categoria", CATEGORIAS), ("status", STATUS), ("confianca", CONFIANCAS)):
        if campo in f and f.get(campo) not in opcoes:
            _ach(erros, fid, campo, f"{campo} inválido ({f.get(campo)!r}): use um de {', '.join(opcoes)}")
    for campo in ("como_dizer", "notas"):
        if campo in f and not isinstance(f.get(campo), str):
            _ach(erros, fid, campo, f"{campo} deve ser texto (use \"\" se não houver)")

    caduca = None
    if f.get("caduca_em") is not None:
        caduca = ler_data(f.get("caduca_em"))
        if caduca is None:
            _ach(erros, fid, "caduca_em", f"caduca_em inválido ({f.get('caduca_em')!r}): use AAAA-MM-DD ou null")

    fontes = f.get("fontes")
    acessos, primarias, secundarias, fracas = [], 0, [], 0
    if "fontes" in f and not isinstance(fontes, list):
        _ach(erros, fid, "fontes", "fontes deve ser uma lista")
        fontes = []
    for i, s in enumerate(fontes or [], 1):
        campo = f"fontes[{i}]"
        if not isinstance(s, dict):
            _ach(erros, fid, campo, "a fonte não é um objeto JSON")
            continue
        for k in CAMPOS_FONTE:
            if k not in s:
                _ach(erros, fid, f"{campo}.{k}", f"campo obrigatório ausente na fonte: {k}"
                     + (" (use null se a página não tem data de publicação)" if k == "publicado_em" else ""))
        for k in ("titulo", "editor"):
            if k in s and (not isinstance(s.get(k), str) or not s[k].strip()):
                _ach(erros, fid, f"{campo}.{k}", f"{k} vazio: " + ("o nome da página ou do artigo" if k == "titulo"
                     else "quem publica (OpenAI, arXiv, Google DeepMind…) — é o que vai para o crédito na tela"))
        if isinstance(s.get("editor"), str) and len(s["editor"].strip()) > MAX_EDITOR_CREDITO:
            _ach(avisos, fid, f"{campo}.editor", f"editor com {len(s['editor'].strip())} caracteres: é o nome que vai "
                 f"para o crédito na tela; abrevie para até {MAX_EDITOR_CREDITO} (o nome completo cabe em titulo)")
        if "url" in s:
            motivo = _url_ok(s.get("url"))
            if motivo:
                _ach(erros, fid, f"{campo}.url", f"{motivo}: {s.get('url')!r}")
        tipo = s.get("tipo")
        if "tipo" in s and tipo not in TIPOS_FONTE:
            _ach(erros, fid, f"{campo}.tipo", f"tipo inválido ({tipo!r}): use primaria ou secundaria")
        pub = None
        if s.get("publicado_em") is not None:
            pub = ler_data(s.get("publicado_em"))
            if pub is None:
                _ach(erros, fid, f"{campo}.publicado_em", f"publicado_em inválido ({s.get('publicado_em')!r}): "
                                                          "use AAAA-MM-DD ou null")
            elif pub > hoje:
                _ach(erros, fid, f"{campo}.publicado_em", f"publicado_em no futuro ({s['publicado_em']}; hoje é {hoje})")
        ace = None
        if "acessado_em" in s:
            ace = ler_data(s.get("acessado_em"))
            if ace is None:
                _ach(erros, fid, f"{campo}.acessado_em", f"acessado_em obrigatório e em AAAA-MM-DD (veio "
                     f"{s.get('acessado_em')!r}): é o dia em que você abriu a página e leu o trecho")
            elif ace > hoje:
                _ach(erros, fid, f"{campo}.acessado_em", f"acessado_em no futuro ({s['acessado_em']}; hoje é {hoje})")
            else:
                acessos.append(ace)
        if pub and ace and pub > ace:
            _ach(erros, fid, f"{campo}.publicado_em", f"publicado_em ({pub}) é posterior a acessado_em ({ace})")
        if "trecho" in s:
            trecho = s.get("trecho")
            if not isinstance(trecho, str) or not trecho.strip():
                _ach(erros, fid, f"{campo}.trecho", "trecho vazio: copie da página a frase (ou a linha da tabela) que "
                                                    "sustenta o fato, no idioma original")
            elif contar_palavras(trecho) > MAX_PALAVRAS_TRECHO:
                _ach(erros, fid, f"{campo}.trecho", f"trecho com {contar_palavras(trecho)} palavras; o máximo é "
                     f"{MAX_PALAVRAS_TRECHO} (citação curta): corte até o pedaço que contém o dado")
        host = (urllib.parse.urlsplit(s.get("url") or "").hostname or "") if isinstance(s.get("url"), str) else ""
        fraca = any(host == d or host.endswith("." + d) for d in DOMINIOS_NAO_PRIMARIOS)
        if tipo == "primaria":
            primarias += 1
            if fraca:
                _ach(avisos, fid, f"{campo}.tipo", f"{host} marcada como primária: enciclopédia, agregador e blog "
                     "pessoal são secundárias — vá à fonte que eles citam")
        elif tipo == "secundaria" and isinstance(s.get("editor"), str) and s["editor"].strip():
            secundarias.append((normalizar(s["editor"]), dominio_registravel(s.get("url")), _txt(s.get("url")).strip()))
            fracas += fraca
        if "conferencia" in s:
            c = s.get("conferencia")
            if not isinstance(c, dict) or c.get("estado") not in CONFERENCIAS or ler_data(c.get("em")) is None \
                    or not isinstance(c.get("marca"), str):
                _ach(erros, fid, f"{campo}.conferencia", "conferencia malformada (só o fatos.py escreve este campo): apague-o "
                     "e rode `fatos.py checar-links --trechos`")
            elif ler_data(c["em"]) > hoje:
                _ach(erros, fid, f"{campo}.conferencia", f"conferência no futuro ({c['em']}; hoje é {hoje})")
            elif c["estado"] == "manual" and len(_txt(c.get("nota")).strip()) < MIN_NOTA_MANUAL:
                _ach(erros, fid, f"{campo}.conferencia", "conferência manual sem nota: diga onde e como o trecho foi lido "
                     f"(ao menos {MIN_NOTA_MANUAL} caracteres) com `fatos.py atualizar {fid} --conferido-manual \"…\"`")

    status, categoria, confianca = f.get("status"), f.get("categoria"), f.get("confianca")
    como_dizer = f.get("como_dizer") if isinstance(f.get("como_dizer"), str) else ""
    notas = f.get("notas") if isinstance(f.get("notas"), str) else ""
    if status == "confirmado":
        n_sec = _secundarias_independentes(secundarias)
        if primarias < 1 and n_sec < 2:
            _ach(erros, fid, "status", "\"confirmado\" exige ao menos 1 fonte primária ou 2 secundárias de editores e "
                 f"domínios distintos (há {_plural(primarias, 'primária', 'primárias')} e "
                 f"{_plural(n_sec, 'editor secundário independente', 'editores secundários independentes')}; a mesma "
                 "página não conta duas vezes): acrescente a fonte que falta ou rebaixe para nao_confirmado")
        elif primarias < 1 and isinstance(categoria, str) and categoria in VALIDADE_SUGERIDA:
            _ach(erros, fid, "status", f"categoria \"{categoria}\" só se confirma com fonte primária (página oficial de "
                 "preços, de modelos, placar de quem roda o teste): secundária serve para achá-la, não para sustentar "
                 "o dado — abra a primária (references/fontes-primarias.md) ou rebaixe para nao_confirmado")
        if primarias < 1 and confianca == "alta":
            _ach(erros, fid, "confianca", "confiança alta exige fonte primária (duas secundárias dão, no máximo, "
                                          "confiança media)")
        if primarias < 1 and secundarias and fracas == len(secundarias):
            _ach(avisos, fid, "fontes", "sustentado só por enciclopédia, fórum ou blog (" + ", ".join(
                sorted({d for _, d, _ in secundarias})) + "): procure a fonte que eles citam")
        conf = conferencia_do_fato(f)
        if conf["ausentes"]:
            _ach(avisos, fid, "fontes", "TRECHO AUSENTE na(s) fonte(s) " + ", ".join(map(str, conf["ausentes"]))
                 + ": a última conferência não achou a citação na página — abra a página; se o dado mudou, atualize o "
                 "fato; se o trecho não era literal, corrija-o; se a página é montada por JavaScript, registre a leitura "
                 f"com `fatos.py atualizar {fid} --conferido-manual \"onde e como você leu\"`")
        pend_conf = conf["nao_verificados"] + conf["nunca"]
        if pend_conf:
            _ach(avisos, fid, "fontes", "trecho ainda não conferido na(s) fonte(s) " + ", ".join(map(str, sorted(pend_conf)))
                 + ": rode `fatos.py checar-links --trechos`" + (
                     f" (o robô não conseguiu ler a página: abra no navegador e registre com `fatos.py atualizar {fid} "
                     "--conferido-manual \"onde e como você leu\"`)" if conf["nao_verificados"] else "")
                 + " — sem isso o fato não vai para a tela nem passa em --estrito")
        if confianca == "baixa":
            _ach(avisos, fid, "confianca", "confirmado com confiança baixa: ou a fonte convence (suba a confiança) ou o "
                                           "status deveria ser nao_confirmado")
        if not como_dizer.strip():
            _ach(avisos, fid, "como_dizer", "sem como_dizer: escreva a redação segura que o roteiro deve usar")
    elif status == "divergente":
        if isinstance(fontes, list) and len(fontes) < 2:
            _ach(erros, fid, "status", "\"divergente\" exige ao menos 2 fontes (as que divergem): registre as duas")
        if not notas.strip():
            _ach(avisos, fid, "notas", "divergente sem notas: explique quem diz o quê e qual critério vai decidir")
    elif status == "nao_confirmado" and confianca == "alta":
        _ach(avisos, fid, "confianca", "nao_confirmado com confiança alta não faz sentido: confirme com fonte ou baixe "
                                       "a confiança")

    ultimo_acesso = max(acessos) if acessos else None
    if _volatil(f):
        dias = VALIDADE_SUGERIDA[categoria]
        if f.get("caduca_em") is None and "caduca_em" in f:
            base = ultimo_acesso or hoje
            _ach(erros, fid, "caduca_em", f"categoria \"{categoria}\" é volátil e exige caduca_em; sugestão: "
                 f"{(base + dt.timedelta(days=dias)).isoformat()} ({dias} dias após o último acesso)")
        elif caduca and ultimo_acesso and (caduca - ultimo_acesso).days > VALIDADE_LONGA:
            _ach(avisos, fid, "caduca_em", f"validade de {(caduca - ultimo_acesso).days} dias é longa para a categoria "
                 f"\"{categoria}\" (a casa sugere {dias}): confira se o dado aguenta tanto tempo")
        if como_dizer.strip() and not re.search(r"\b(?:19|20)\d{2}\b", como_dizer):
            _ach(avisos, fid, "como_dizer", "como_dizer sem data: fato volátil se diz datado (ex.: \"em outubro de "
                                            "2026, …\")")
    elif categoria == "empresa" and f.get("caduca_em") is None and isinstance(valor, (int, float)) \
            and not isinstance(valor, bool):
        _ach(avisos, fid, "caduca_em", "número de empresa (avaliação, usuários, funcionários) costuma mudar: "
                                       "considere preencher caduca_em")
    if isinstance(valor, (int, float)) and not isinstance(valor, bool) and isinstance(afirmacao, str) and afirmacao.strip():
        itens_af = extrair_numeros(afirmacao, "pt", tudo=True, termos=_termos(f))
        nums = {v for it in itens_af for v in it["valores"]} \
            | {float(it["ano"]) for it in itens_af if it["tipo"] == "data" and it.get("ano")}   # "junho de 2017" traz 2017
        if not _bate([float(valor)], nums):
            _ach(avisos, fid, "valor", f"o valor ({valor}) não aparece na afirmacao: se o dado mudou, atualize também a "
                                       "afirmacao, o como_dizer e o trecho da fonte")
    if caduca and caduca < hoje:
        _ach(avisos, fid, "caduca_em", f"VENCIDO em {caduca.isoformat()} (há {(hoje - caduca).days} dias): abra a fonte "
             f"de novo e rode `fatos.py atualizar {fid} --revalidado --caduca-em AAAA-MM-DD`")
    if f.get("autodeclarado") is True and como_dizer.strip():
        if not re.search(r"\b(?:segundo|de acordo com|conforme|afirma|diz|dizem|declara|divulg\w+|anunci\w+|relat\w+|"
                         r"inform\w+|estim\w+|nas contas d\w+|nos testes d\w+|(?:d?[ao]s?|pel[ao]s?|n[ao]s?) pr[óo]pri[ao]s?)\b",
                         como_dizer, re.I):
            _ach(avisos, fid, "como_dizer", "número autodeclarado sem atribuição no como_dizer: diga de quem é a conta "
                                            "(\"segundo a própria …\")")
    if "autodeclarado" in f and not isinstance(f.get("autodeclarado"), bool):
        _ach(erros, fid, "autodeclarado", "autodeclarado deve ser true ou false")
    if "termos" in f and (not isinstance(f.get("termos"), list) or not all(isinstance(t, str) for t in f["termos"])):
        _ach(erros, fid, "termos", "termos deve ser uma lista de textos")
    for campo, texto in (("afirmacao", afirmacao if isinstance(afirmacao, str) else ""), ("como_dizer", como_dizer)):
        an = analisar_frase(texto)
        sup = [it["bruto"] for it in an["fortes"] if it["tipo"] == "superlativo"]
        if sup and not re.search(r"\b(?:19|20)\d{2}\b", texto):
            _ach(avisos, fid, campo, f"superlativo sem data ({'; '.join(sup)}): diga o critério (qual teste, qual "
                                     "placar) e a data, ou tire o superlativo")
    return erros, avisos


def validar_ficha(ficha, hoje: dt.date | None = None) -> dict:
    """Esquema do contrato + regras da casa. → {'ok', 'erros', 'avisos', 'fatos'}."""
    hoje = hoje or hoje_local()
    erros, avisos = [], []
    if not isinstance(ficha, dict):
        _ach(erros, "ficha", "", "a ficha não é um objeto JSON")
        return {"ok": False, "erros": erros, "avisos": avisos, "fatos": 0}
    if ficha.get("versao") != VERSAO_FICHA:
        _ach(erros, "ficha", "versao", f"versao deve ser {VERSAO_FICHA} (veio {ficha.get('versao')!r})")
    if not isinstance(ficha.get("tema"), str) or not ficha["tema"].strip():
        _ach(erros, "ficha", "tema", "tema vazio: diga o assunto do vídeo")
    atual = ler_data(ficha.get("atualizado_em"))
    if atual is None:
        _ach(erros, "ficha", "atualizado_em", f"atualizado_em inválido ({ficha.get('atualizado_em')!r}): use AAAA-MM-DD")
    elif atual > hoje:
        _ach(erros, "ficha", "atualizado_em", f"atualizado_em no futuro ({atual}; hoje é {hoje})")
    fatos = ficha.get("fatos")
    if not isinstance(fatos, list):
        _ach(erros, "ficha", "fatos", "fatos deve ser uma lista")
        return {"ok": False, "erros": erros, "avisos": avisos, "fatos": 0}
    vistos, textos = {}, {}
    for i, f in enumerate(fatos):
        e, a = validar_fato(f, hoje)
        erros.extend(e)
        avisos.extend(a)
        if isinstance(f, dict):
            fid = f.get("id")
            if isinstance(fid, str):
                if fid in vistos:
                    _ach(erros, fid, "id", f"id repetido (posições {vistos[fid] + 1} e {i + 1} da lista)")
                vistos[fid] = i
            chave = normalizar(f.get("afirmacao") or "")
            if chave and chave in textos:
                _ach(avisos, str(fid), "afirmacao", f"mesma afirmação de {textos[chave]}: una os dois fatos")
            elif chave:
                textos[chave] = str(fid)
    return {"ok": not erros, "erros": erros, "avisos": avisos, "fatos": len(fatos)}


# ----------------------------------------------------------------------------- criar, adicionar, atualizar
def nova_ficha(tema: str, hoje: dt.date | None = None) -> dict:
    return {"versao": VERSAO_FICHA, "tema": tema.strip(), "atualizado_em": (hoje or data_real()).isoformat(),
            "fatos": []}


def _limpo(v):
    return re.sub(r"\s+", " ", v).strip() if isinstance(v, str) else v


def preparar_fato(bruto: dict, hoje: dt.date, acessado_hoje: bool = False, caduca_padrao: bool = False):
    """Completa os campos opcionais de um fato vindo do usuário. → (fato, observações)."""
    if not isinstance(bruto, dict):
        raise ErroFatos("o fato precisa ser um objeto JSON ({\"afirmacao\": …, \"categoria\": …, \"fontes\": [...]})",
                        codigo=SAIDA_USO)
    obs = []
    f = {"id": None}
    f["afirmacao"] = _limpo(bruto.get("afirmacao", ""))
    f["valor"] = bruto.get("valor")
    f["unidade"] = _limpo(bruto.get("unidade"))
    f["referente_a"] = _limpo(bruto.get("referente_a", ""))
    f["categoria"] = bruto.get("categoria")                       # obrigatória: é ela que decide se o fato caduca
    f["status"] = bruto.get("status", "nao_confirmado")
    if "status" not in bruto:
        obs.append("status não informado: gravado como nao_confirmado")
    f["confianca"] = bruto.get("confianca", "baixa")
    if "confianca" not in bruto:
        obs.append("confianca não informada: gravada como baixa")
    f["caduca_em"] = bruto.get("caduca_em")
    fontes = bruto.get("fontes", [])
    f["fontes"] = []
    if isinstance(fontes, list):
        for s in fontes:
            if not isinstance(s, dict):
                f["fontes"].append(s)
                continue
            n = {k: _limpo(s.get(k)) for k in ("titulo", "url", "editor", "tipo") if k in s}
            n["publicado_em"] = s.get("publicado_em")
            if "acessado_em" in s:
                n["acessado_em"] = s["acessado_em"]
            elif acessado_hoje:
                n["acessado_em"] = hoje.isoformat()
            if "trecho" in s:
                n["trecho"] = _limpo(s["trecho"])
            ordenado = {k: n[k] for k in CAMPOS_FONTE if k in n}
            # `conferencia` não entra por JSON do usuário: só checar-links --trechos e --conferido-manual a escrevem
            ordenado.update({k: v for k, v in s.items() if k not in CAMPOS_FONTE and k != "conferencia"})
            f["fontes"].append(ordenado)
    else:
        f["fontes"] = fontes
    f["como_dizer"] = _limpo(bruto.get("como_dizer", ""))
    f["notas"] = _limpo(bruto.get("notas", ""))
    for k, v in bruto.items():
        if k not in f:
            f[k] = v
    if caduca_padrao and f["caduca_em"] is None and _volatil(f):
        acessos = [ler_data(s.get("acessado_em")) for s in _fontes(f)]
        base = max([a for a in acessos if a] or [hoje])
        f["caduca_em"] = (base + dt.timedelta(days=VALIDADE_SUGERIDA[f["categoria"]])).isoformat()
        obs.append(f"caduca_em preenchido com a validade sugerida: {f['caduca_em']}")
    return f, obs


def _modelos_do_fato(f: dict) -> set:
    """Nomes de modelo de um fato (afirmacao + termos), normalizados — dois modelos diferentes são fatos diferentes."""
    termos = [t for t in _termos(f) if re.search(r"[A-ZÀ-Ý]", t)]
    _, achados = _mascarar_modelos(_txt(f.get("afirmacao")), termos)
    return {normalizar(n) for n in achados + termos if normalizar(n)}


def achar_duplicata(ficha: dict, novo: dict, ignorar_id: str | None = None):
    """Duplicata óbvia: mesma afirmação (normalizada); ou ≥ 90 % igual, com os mesmos números E os mesmos nomes de
    modelo; ou a mesma medida (valor + unidade + período) do mesmo modelo tirada da mesma URL. → (id, motivo) | None.

    "Gemini 3.8 Flash custa 0,75" e "Gemini 3.7 Flash custa 0,75" NÃO são duplicata: a tabela comparativa repete
    preços, e o nome do modelo é o que distingue os fatos."""
    na = normalizar(novo.get("afirmacao") or "")
    if not na:
        return None
    nums = lambda f: _assinatura(extrair_numeros(_txt(f.get("afirmacao")), "pt", tudo=True, termos=_termos(f)))  # noqa: E731
    nums_a, modelos_a = nums(novo), _modelos_do_fato(novo)
    urls_a = {s.get("url") for s in _fontes(novo) if isinstance(s.get("url"), str)}
    for f in ficha.get("fatos", []):
        if not isinstance(f, dict) or f.get("id") == ignorar_id:
            continue
        nb = normalizar(f.get("afirmacao") or "")
        if na == nb:
            return f.get("id"), "afirmação idêntica"
        if modelos_a != _modelos_do_fato(f):
            continue                                              # outro modelo: outro fato
        r = difflib.SequenceMatcher(None, na, nb).ratio()
        if r >= 0.9 and nums_a == nums(f):
            return f.get("id"), f"afirmação {r:.0%} igual, com os mesmos números"
        urls_b = {s.get("url") for s in _fontes(f) if isinstance(s.get("url"), str)}
        medida = isinstance(novo.get("valor"), (int, float)) and not isinstance(novo.get("valor"), bool) \
            and bool(novo.get("unidade"))                         # só grandeza com unidade: "2017" sozinho repete à toa
        if medida and novo.get("valor") == f.get("valor") and novo.get("unidade") == f.get("unidade") \
                and urls_a & urls_b and (modelos_a or r >= 0.6) \
                and normalizar(novo.get("referente_a") or "") == normalizar(f.get("referente_a") or ""):
            return f.get("id"), "mesmo valor, mesma unidade, mesmo período, mesma fonte" + (
                " e mesmo modelo" if modelos_a else " e afirmação parecida")
    return None


def adicionar(ficha: dict, bruto: dict, hoje: dt.date | None = None, acessado_hoje: bool = False,
              caduca_padrao: bool = False, forcar: bool = False) -> dict:
    """Valida e acrescenta um fato à ficha (em memória). → {'id', 'avisos', 'observacoes'}; ErroFatos se reprovar."""
    hoje = hoje or data_real()
    fato, obs = preparar_fato(bruto, hoje, acessado_hoje, caduca_padrao)
    if "id" in bruto and bruto["id"]:
        obs.append(f"id informado ({bruto['id']}) ignorado: a ficha atribui o próximo livre")
    fato["id"] = proximo_id(ficha)
    erros, avisos = validar_fato(fato, hoje)
    if erros:
        raise ErroFatos("fato recusado:\n" + "\n".join(f"  - {e['campo'] or 'fato'}: {e['mensagem']}" for e in erros),
                        "corrija o JSON e rode de novo; nada foi gravado"
                        + (" (para datar as fontes de hoje use --acessado-hoje)"
                           if any("acessado_em" in e["campo"] for e in erros) and not acessado_hoje else "")
                        + (" (para aceitar a validade sugerida use --caduca-padrao)"
                           if any(e["campo"] == "caduca_em" and "sugestão" in e["mensagem"] for e in erros) else ""))
    dup = achar_duplicata(ficha, fato)
    if dup and not forcar:
        raise ErroFatos(f"duplicata de {dup[0]} ({dup[1]}): nada foi gravado",
                        f"se é o mesmo fato, atualize o existente com `fatos.py atualizar {dup[0]} …`; se é OUTRO fato "
                        "(outra variante, outra grandeza, outra data), diga a diferença na afirmação — o nome exato do "
                        "modelo, a unidade, o período — ou confirme com --forcar")
    ficha.setdefault("fatos", []).append(fato)
    ficha["ultimo_id"] = int(fato["id"][1:])
    return {"id": fato["id"], "avisos": avisos, "observacoes": obs}


def atualizar(ficha: dict, fid: str, mudancas: dict | None = None, nova_fonte: dict | None = None,
              revalidado=None, hoje: dt.date | None = None, acessado_hoje: bool = False,
              conferido_manual: str | None = None, fontes_alvo=None) -> dict:
    """Aplica mudanças a um fato (em memória) e revalida. `revalidado`: 'todas' ou lista de índices (base 1).

    `conferido_manual`: nota de quem abriu a página e leu o trecho (onde e como) — grava a conferência manual nas
    fontes de `fontes_alvo` (índices base 1; padrão: todas). A conferência de uma fonte cai sozinha quando a url ou o
    trecho mudam. `revalidado` exige trecho conferido HOJE (automático ou manual) em cada fonte revalidada."""
    hoje = hoje or data_real()
    alvo = obter(ficha, fid)
    novo = json.loads(json.dumps(alvo))
    mudancas = dict(mudancas or {})
    if "id" in mudancas and mudancas["id"] != alvo["id"]:
        raise ErroFatos("o id de um fato não muda (roteiro e storyboard apontam para ele)", codigo=SAIDA_USO)
    mudancas.pop("id", None)
    antigas = {marca_da_fonte(s): s["conferencia"] for s in _fontes(alvo) if conferencia_da_fonte(s)}
    if "fontes" in mudancas and isinstance(mudancas["fontes"], list):
        prep, _ = preparar_fato({"fontes": mudancas["fontes"]}, hoje, acessado_hoje)
        mudancas["fontes"] = prep["fontes"]
    for k, v in mudancas.items():
        novo[k] = _limpo(v) if k in ("afirmacao", "unidade", "referente_a", "como_dizer", "notas") else v
    if nova_fonte is not None:
        prep, _ = preparar_fato({"fontes": [nova_fonte]}, hoje, acessado_hoje)
        url = prep["fontes"][0].get("url") if isinstance(prep["fontes"][0], dict) else None
        if url and any(s.get("url") == url for s in _fontes(novo)):
            raise ErroFatos(f"o fato {alvo['id']} já tem uma fonte com esta URL: {url}",
                            "para reconfirmar a mesma página use --revalidado")
        if not isinstance(novo.get("fontes"), list):
            novo["fontes"] = []
        novo["fontes"].append(prep["fontes"][0])
    for s in _fontes(novo):                                       # a conferência acompanha o par (url, trecho)
        s.pop("conferencia", None)
        if marca_da_fonte(s) in antigas:
            s["conferencia"] = antigas[marca_da_fonte(s)]
    fontes = _fontes(novo)

    def indices(quais, o_que):
        if not fontes:
            raise ErroFatos(f"{alvo['id']} não tem fontes para {o_que}", "acrescente uma com --nova-fonte")
        idx = list(range(1, len(fontes) + 1)) if quais in (None, "todas") else list(quais)
        for i in idx:
            if not 1 <= i <= len(fontes):
                raise ErroFatos(f"{alvo['id']} não tem a fonte {i} (tem {len(fontes)})", codigo=SAIDA_USO)
        return idx

    if conferido_manual is not None:
        nota = _limpo(conferido_manual)
        if len(nota) < MIN_NOTA_MANUAL:
            raise ErroFatos(f"a nota de --conferido-manual é curta demais ({len(nota)} caracteres)",
                            "diga onde e como você leu o trecho, por exemplo: \"aberta no navegador em 06/10; a linha do "
                            f"modelo na tabela de preços traz o valor citado\" (mínimo de {MIN_NOTA_MANUAL} caracteres)",
                            SAIDA_USO)
        for i in indices(fontes_alvo if fontes_alvo else (None if revalidado in (None, "todas") else revalidado),
                         "conferir"):
            antes = conferencia_da_fonte(fontes[i - 1])
            # `robo`: o que a conferência automática tinha dito desta página (ausente = JavaScript; nao_verificado =
            # bloqueio/PDF) — é o que deixa a leitura manual sobreviver à próxima rodada do checar-links
            robo = None if not antes else antes["estado"] if antes["estado"] in ("ausente", "nao_verificado") \
                else antes.get("robo") if antes["estado"] == "manual" else None
            fontes[i - 1]["conferencia"] = {"estado": "manual", "em": hoje.isoformat(), "metodo": "declarada",
                                            "nota": nota, "robo": robo, "marca": marca_da_fonte(fontes[i - 1])}
    if revalidado:
        sem = []
        for i in indices(revalidado, "revalidar"):
            c = conferencia_da_fonte(fontes[i - 1])
            if not c or c["estado"] not in CONFERENCIAS_OK or c["em"] != hoje.isoformat():
                sem.append(i)
            fontes[i - 1]["acessado_em"] = hoje.isoformat()
        if sem:
            raise ErroFatos(f"{alvo['id']}: revalidar exige o trecho conferido HOJE e a(s) fonte(s) "
                            f"{', '.join(map(str, sem))} não tem(têm) conferência de {hoje.isoformat()}: nada foi gravado",
                            f"rode `fatos.py checar-links --trechos --id {alvo['id']}` e repita; se o robô não lê a "
                            "página, abra-a no navegador e acrescente --conferido-manual \"onde e como você leu\"")
        novo["verificado_em"] = hoje.isoformat()
    erros, avisos = validar_fato(novo, hoje)
    if erros:
        raise ErroFatos(f"mudança recusada em {alvo['id']}:\n"
                        + "\n".join(f"  - {e['campo'] or 'fato'}: {e['mensagem']}" for e in erros),
                        "corrija e rode de novo; nada foi gravado")
    if "afirmacao" in mudancas:
        dup = achar_duplicata(ficha, novo, ignorar_id=alvo["id"])
        if dup:
            avisos.append({"id": alvo["id"], "campo": "afirmacao", "mensagem": f"ficou igual a {dup[0]} ({dup[1]})"})
    alvo.clear()
    alvo.update(novo)
    return {"id": alvo["id"], "avisos": avisos}


def registrar_conferencias(ficha: dict, rel: dict, hoje: dt.date | None = None) -> dict:
    """Grava em cada fonte o resultado de `checar_links(..., com_trechos=True)`. → contagem por estado.

    encontrado = achou o trecho · ausente = abriu e não achou (ou a página saiu do ar: 404/410) · nao_verificado = o
    robô não leu a página (bloqueio, PDF, sem resposta).

    A conferência manual declarada só cai diante de evidência NOVA: fica quando o robô continua sem ler a página
    (nao_verificado), quando foi declarada hoje, ou quando o robô já dava 'ausente' antes dela (página montada por
    JavaScript é sempre 'ausente' para o robô). Se o robô passa a ler a página e não acha o trecho, vale 'ausente'."""
    hoje = hoje or data_real()
    por_url = {r["url"]: r for r in rel.get("resultados", [])}
    cont = {"encontrado": 0, "ausente": 0, "nao_verificado": 0, "manual_mantida": 0}
    for f in ficha.get("fatos", []):
        for s in _fontes(f):
            r = por_url.get(s.get("url"))
            if r is None or not any(str(u).split("#")[0] == f.get("id") for u in (r.get("usos") or [])):
                continue
            achado = (r.get("trechos") or {}).get(s.get("trecho"))
            if isinstance(achado, str) and achado.startswith("encontrado"):
                estado = "encontrado"
            elif r.get("estado") == "quebrado" or (isinstance(achado, str) and achado.startswith("ausente")):
                estado = "ausente"
            else:
                estado = "nao_verificado"
            atual = conferencia_da_fonte(s)
            if estado != "encontrado" and atual and atual["estado"] == "manual" and (
                    estado == "nao_verificado" or atual["em"] == hoje.isoformat() or atual.get("robo") == "ausente"):
                s["conferencia"]["robo"] = estado                 # o que o robô viu por último
                cont["manual_mantida"] += 1
                continue
            s["conferencia"] = {"estado": estado, "em": hoje.isoformat(), "metodo": "checar-links",
                                "http": r.get("http"), "marca": marca_da_fonte(s)}
            cont[estado] += 1
    return cont


# ----------------------------------------------------------------------------- vencimentos, crédito, resumo
def vencimentos(ficha: dict, hoje: dt.date | None = None, dias: int = 14) -> dict:
    """→ {'vencidos': [...], 'a_vencer': [...]} (a vencer = caduca em até `dias` dias, incluindo hoje)."""
    hoje = hoje or hoje_local()
    vencidos, a_vencer = [], []
    for f in ficha.get("fatos", []):
        if not isinstance(f, dict):
            continue
        c = ler_data(f.get("caduca_em"))
        if c is None:
            continue
        item = {"id": f.get("id"), "caduca_em": c.isoformat(), "categoria": f.get("categoria"),
                "status": f.get("status"), "afirmacao": f.get("afirmacao"), "dias": (c - hoje).days}
        if c < hoje:
            vencidos.append(item)
        elif (c - hoje).days <= dias:
            a_vencer.append(item)
    vencidos.sort(key=lambda x: x["dias"])
    a_vencer.sort(key=lambda x: x["dias"])
    return {"hoje": hoje.isoformat(), "dias": dias, "vencidos": vencidos, "a_vencer": a_vencer}


def _escolher_fonte(fato: dict, indice: int | None = None):
    fontes = _fontes(fato)
    if not fontes:
        raise ErroFatos(f"{fato.get('id')} não tem fonte: não há crédito a mostrar",
                        "registre a fonte com `fatos.py atualizar <id> --nova-fonte @fonte.json`")
    if indice is not None:
        if not 1 <= indice <= len(fontes):
            raise ErroFatos(f"{fato.get('id')} não tem a fonte {indice} (tem {len(fontes)})", codigo=SAIDA_USO)
        return indice, fontes[indice - 1]
    for i, s in enumerate(fontes, 1):
        if s.get("tipo") == "primaria":
            return i, s
    return 1, fontes[0]


def _parte_credito(s: dict, formato_data: str) -> tuple:
    d = ler_data(s.get("publicado_em"))
    origem = "publicado_em"
    if d is None:
        d, origem = ler_data(s.get("acessado_em")), "acessado_em"
    if d is None:
        data = ""
    elif formato_data == "ano":
        data = str(d.year)
    else:
        data = mes_ano(d)
    editor = _txt(s.get("editor")).strip()
    return (f"{editor}, {data}" if data else editor), data, origem


def credito(fato: dict, indice: int | None = None, formato_data: str = "mes_ano", todas: bool = False) -> dict:
    """Crédito de fonte para a tela no padrão "Fonte: Editor, mês/ano".

    `param_cena` é o texto SEM o prefixo: as cenas `citacao` e `barras` do motor já escrevem "Fonte: "."""
    if todas:
        fontes = _fontes(fato)
        if not fontes:
            _escolher_fonte(fato)
        partes, vistos = [], set()
        for s in fontes:
            p = _parte_credito(s, formato_data)[0]
            if p not in vistos:
                vistos.add(p)
                partes.append(p)
        corpo = "; ".join(partes)
        return {"id": fato.get("id"), "texto": ("Fontes: " if len(partes) > 1 else "Fonte: ") + corpo,
                "param_cena": corpo, "editor": None, "data": None, "data_origem": None, "fonte": None}
    i, s = _escolher_fonte(fato, indice)
    corpo, data, origem = _parte_credito(s, formato_data)
    return {"id": fato.get("id"), "texto": "Fonte: " + corpo, "param_cena": corpo,
            "editor": str(s.get("editor") or "").strip(), "data": data, "data_origem": origem, "fonte": i}


def resumo(ficha: dict, hoje: dt.date | None = None) -> dict:
    hoje = hoje or hoje_local()
    fatos = [f for f in ficha.get("fatos", []) if isinstance(f, dict)]
    cont = lambda campo, opcoes: {o: sum(1 for f in fatos if _txt(f.get(campo)) == o) for o in opcoes}  # noqa: E731
    v = vencimentos(ficha, hoje)
    rel = validar_ficha(ficha, hoje)
    trechos = {"encontrados": 0, "manuais": 0, "ausentes": 0, "nao_verificados": 0, "nunca": 0}
    sem_conferencia = []
    for f in fatos:
        if _txt(f.get("status")) != "confirmado":
            continue
        c = conferencia_do_fato(f)
        for k in trechos:
            trechos[k] += len(c[k])
        if not c["ok"]:
            sem_conferencia.append(f.get("id"))
    return {"tema": ficha.get("tema"), "atualizado_em": ficha.get("atualizado_em"), "hoje": hoje.isoformat(),
            "trechos": trechos, "sem_conferencia": sem_conferencia,
            "fatos": len(fatos), "por_status": cont("status", STATUS), "por_categoria": cont("categoria", CATEGORIAS),
            "por_confianca": cont("confianca", CONFIANCAS),
            "fontes": sum(len(_fontes(f)) for f in fatos),
            "vencidos": [x["id"] for x in v["vencidos"]], "a_vencer": [x["id"] for x in v["a_vencer"]],
            "erros": len(rel["erros"]), "avisos": len(rel["avisos"])}


# ----------------------------------------------------------------------------- markdown
def _md(s) -> str:
    return str(s).replace("|", "\\|").replace("\n", " ")


def _fmt_valor(f: dict) -> str:
    v = f.get("valor")
    if v is None:
        return "—"
    if isinstance(v, bool):
        txt = str(v)
    elif isinstance(v, (int, float)):
        if float(v).is_integer():
            txt = f"{int(v):,}".replace(",", ".") if abs(v) >= 10000 else str(int(v))
        else:
            txt = f"{v:,.6f}".rstrip("0").rstrip(".")
            txt = txt.replace(",", "\0").replace(".", ",").replace("\0", ".")
    else:
        txt = str(v)
    return f"{txt} {f['unidade']}" if f.get("unidade") else txt


def gerar_fatos_md(ficha: dict, hoje: dt.date | None = None) -> str:
    hoje = hoje or hoje_local()
    fatos = [f for f in ficha.get("fatos", []) if isinstance(f, dict)]
    r = resumo(ficha, hoje)
    ps = r["por_status"]
    L = [f"# Ficha de fatos — {ficha.get('tema', '')}", "",
         f"Atualizada em {data_br(ficha.get('atualizado_em'))} · {_plural(len(fatos), 'fato', 'fatos')} "
         f"({_plural(ps['confirmado'], 'confirmado', 'confirmados')}, "
         f"{_plural(ps['divergente'], 'divergente', 'divergentes')}, "
         f"{_plural(ps['nao_confirmado'], 'não confirmado', 'não confirmados')}) · gerada em {data_br(hoje)} por "
         "`fatos.py md`.", "",
         "Não edite este arquivo: altere `pesquisa/fatos.json` com `fatos.py adicionar`/`atualizar` e gere de novo. "
         "No roteiro, cite cada fato pelo marcador entre colchetes (`[F001]`) e use a redação de \"Como dizer\".", ""]
    if r["vencidos"]:
        L += [f"**Vencidos (revalidar antes de gravar ou publicar):** {', '.join(r['vencidos'])}", ""]
    L += ["| id | categoria | status | confiança | caduca em | afirmação |", "|---|---|---|---|---|---|"]
    for f in fatos:
        c = ler_data(f.get("caduca_em"))
        caduca = "não caduca" if c is None else data_br(c) + (" (VENCIDO)" if c < hoje else "")
        L.append(f"| {f.get('id')} | {f.get('categoria')} | {f.get('status')} | {f.get('confianca')} | {caduca} | "
                 f"{_md(f.get('afirmacao', ''))} |")
    L.append("")
    for f in fatos:
        c = ler_data(f.get("caduca_em"))
        L += [f"## {f.get('id')} — {f.get('status')} · confiança {f.get('confianca')} · {f.get('categoria')}", "",
              f"**Afirmação:** {f.get('afirmacao', '')}", "",
              f"**Valor:** {_fmt_valor(f)} · **Refere-se a:** {f.get('referente_a', '')} · **Caduca em:** "
              + ("não caduca" if c is None else data_br(c) + (" — VENCIDO" if c < hoje else "")), ""]
        if f.get("autodeclarado") is True:
            L += ["**Número autodeclarado** pelo fabricante (sem verificação independente registrada).", ""]
        L += [f"**Como dizer no roteiro:** {f.get('como_dizer') or '_(sem redação segura: não usar)_'}", ""]
        confirmado = f.get("status") == "confirmado"
        conf = conferencia_do_fato(f)
        try:
            if confirmado and conf["ok"]:
                L += [f"**Crédito na tela:** {credito(f)['texto']}", ""]
            elif confirmado:
                L += ["**Crédito na tela:** _(indisponível: há trecho de fonte ausente ou ainda não conferido)_", ""]
        except ErroFatos:
            pass
        L.append("**Fontes:**")
        L.append("")
        for i, s in enumerate(_fontes(f), 1):
            pub = f"publicado em {data_br(s.get('publicado_em'))}" if s.get("publicado_em") else "sem data de publicação"
            L.append(f"{i}. [{'primária' if s.get('tipo') == 'primaria' else 'secundária'}] {s.get('titulo', '')} — "
                     f"{s.get('editor', '')}, {pub}, acessado em {data_br(s.get('acessado_em'))} — <{s.get('url', '')}>")
            if s.get("trecho"):
                L.append(f"   > “{s['trecho']}”")
            c = conferencia_da_fonte(s)
            if c is None:
                L.append("   - trecho **ainda não conferido** na página (`fatos.py checar-links --trechos`)")
            elif c["estado"] == "encontrado":
                L.append(f"   - trecho encontrado na página em {data_br(c['em'])} (conferência automática)")
            elif c["estado"] == "manual":
                L.append(f"   - conferência manual declarada em {data_br(c['em'])}: {_txt(c.get('nota'))}")
            elif c["estado"] == "ausente":
                L.append(f"   - **TRECHO AUSENTE** na conferência de {data_br(c['em'])}: abra a página antes de usar o fato")
            else:
                L.append(f"   - o robô não conseguiu ler a página em {data_br(c['em'])}: falta a conferência manual")
        if not _fontes(f):
            L.append("_(nenhuma fonte registrada)_")
        L.append("")
        if f.get("notas"):
            L += [f"**Notas:** {f['notas']}", ""]
    return "\n".join(L).rstrip() + "\n"


def marcadores_no_texto(texto: str) -> list:
    """Ids citados com [F001] (ou [F001, F002]) num texto, na ordem em que aparecem, sem repetir."""
    ids = []
    for m in _RE_MARCADOR.finditer(texto or ""):
        for fid in re.findall(r"F\d{3,}", m.group(0), re.I):
            if fid.upper() not in ids:
                ids.append(fid.upper())
    return ids


def fontes_para_descricao(ficha: dict, ids=None) -> list:
    """Fontes únicas (por URL) dos fatos CONFIRMADOS, na ordem da ficha. Divergente e não confirmado ficam de fora:
    não podem estar no roteiro, então a fonte deles não pode estar na descrição.

    → [{'n', 'titulo', 'editor', 'data', 'url', 'acessado_em', 'fatos': [...]}]"""
    saida, por_url = [], {}
    for f in ficha.get("fatos", []):
        if not isinstance(f, dict) or f.get("status") != "confirmado":
            continue
        if ids is not None and f.get("id") not in ids:
            continue
        for s in _fontes(f):
            if not isinstance(s.get("url"), str) or not s["url"].strip():
                continue
            if s["url"] in por_url:
                por_url[s["url"]]["fatos"].append(f.get("id"))
                continue
            pub = ler_data(s.get("publicado_em"))
            data = mes_ano(pub) if pub else ("acesso em " + mes_ano(s.get("acessado_em")) if s.get("acessado_em") else "")
            item = {"n": len(saida) + 1, "titulo": _txt(s.get("titulo")), "editor": _txt(s.get("editor")), "data": data,
                    "url": s["url"], "acessado_em": s.get("acessado_em"), "fatos": [f.get("id")]}
            por_url[s["url"]] = item
            saida.append(item)
    return saida


def _limite_descricao() -> int | None:
    """Limite de caracteres da descrição do YouTube, lido do kit de direção de arte (plataformas.json), se houver."""
    for kit in (Path(__file__).resolve().parents[2] / "video-direcao-de-arte" / "kit",
                Path("~/.claude/skills/video-direcao-de-arte/kit").expanduser()):
        try:
            dados = json.loads((kit / "plataformas.json").read_text(encoding="utf-8"))
            return int(dados["limites_texto"]["youtube"]["descricao_max_caracteres"])
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return None


def gerar_fontes_md(ficha: dict, hoje: dt.date | None = None, ids=None) -> str:
    hoje = hoje or hoje_local()
    itens = fontes_para_descricao(ficha, ids)
    bloco = ["Fontes:"]
    for it in itens:
        meio = f"{it['editor']}, {it['data']}" if it["data"] else it["editor"]
        bloco.append(f"{it['n']}. {it['titulo']} — {meio}: {it['url']}")
    acessos = sorted(d for d in (ler_data(it.get("acessado_em")) for it in itens) if d)
    if acessos:
        quando = (f"em {data_br(acessos[0])}" if acessos[0] == acessos[-1]
                  else f"entre {data_br(acessos[0])} e {data_br(acessos[-1])}")
        bloco.append(f"Fontes acessadas {quando}. Preços, versões e placares de modelos de IA mudam com frequência.")
    texto_bloco = "\n".join(bloco)
    editores = []
    for it in itens:
        rot = f"{it['editor']} ({it['data'].replace('acesso em ', '')})" if it["data"] else it["editor"]
        if rot not in editores:
            editores.append(rot)
    curta = "Fontes: " + "; ".join(editores) + "." if editores else "Fontes: —"
    limite = _limite_descricao()
    L = [f"# Fontes — {ficha.get('tema', '')}", "",
         f"Gerado em {data_br(hoje)} por `fatos.py md` a partir de `pesquisa/fatos.json` "
         f"({_plural(len(itens), 'fonte única', 'fontes únicas')}"
         + (", só os fatos confirmados citados no roteiro" if ids is not None else ", só fatos confirmados")
         + "). Não edite: gere de novo.", "",
         "## Para a descrição do vídeo (YouTube)", "",
         "Copie o que está entre os marcadores. Fatos divergentes e não confirmados ficam de fora.", "",
         "<!-- DESCRICAO:INICIO -->", texto_bloco, "<!-- DESCRICAO:FIM -->", ""]
    aviso_limite = ""
    if limite:
        aviso_limite = (f" de {limite} permitidos na descrição do YouTube (limite lido de plataformas.json do kit de "
                        "direção de arte)")
        if len(texto_bloco) > limite * 0.5:
            aviso_limite += " — ATENÇÃO: passa da metade do limite; use a versão curta ou um link para a lista completa"
    L += [f"{len(texto_bloco)} caracteres{aviso_limite}.", "",
          "## Versão curta (Shorts, Reels, TikTok)", "",
          "<!-- CURTA:INICIO -->", curta, "<!-- CURTA:FIM -->", "",
          f"{len(curta)} caracteres.", "", "## Fonte por fato", ""]
    for f in ficha.get("fatos", []):
        if not isinstance(f, dict):
            continue
        nums = [str(it["n"]) for it in itens if f.get("id") in it["fatos"]]
        if nums:
            L.append(f"- {f.get('id')} → {', '.join(nums)}")
        elif f.get("status") != "confirmado" and (ids is None or f.get("id") in ids):
            L.append(f"- {f.get('id')} → fora da lista ({'divergente' if f.get('status') == 'divergente' else 'não confirmado'})")
    return "\n".join(L).rstrip() + "\n"


# ----------------------------------------------------------------------------- conferir roteiro
_RE_MARCADOR = re.compile(r"\[\s*F\d{3,}(?:\s*(?:,|;|\+|e)\s*F\d{3,})*\s*\]", re.I)
_RE_DISPENSA = re.compile(r"\[\s*(?:sem[- ]fato|opini[aã]o)\s*(?::[^\]]*)?\]", re.I)
_RE_COLCHETE = re.compile(r"\[[^\]\n]*\]")
_ROTULOS_META = {"motor", "etapa do funil", "formato", "duracao alvo", "duracao", "metrica principal",
                 "hashtags fixas", "hashtags", "publico", "plataforma", "versao", "tese", "publico e objetivo",
                 "o que mudou", "falta voce fornecer"}
# seções que não são texto do vídeo (saída de gerar-roteiro/melhorar-roteiro): puladas e contadas no relatório
_SECOES_PULADAS = {"checklist": "checklist", "diagnostico": "diagnóstico"}
_ABREVIACOES = ("et al.", "etc.", "p. ex.", "ex.", "Dr.", "Dra.", "Sr.", "Sra.", "Prof.", "Profa.", "U.S.", "E.U.A.",
                "vs.", "pág.", "Inc.", "Ltd.", "Corp.", "Co.", "a.C.", "d.C.", "n.º", "No.", "approx.", "aprox.")
_RE_FIM_FRASE = re.compile(r"(?<=[.!?…])[\"”’»)]*\s+(?=(?:\[[^\]]*\]\s*)*[(\"“‘«]*[A-ZÀ-Ý0-9])")
# marcador logo depois do ponto pertence à frase anterior: "… em 2017. [F001]" → "… em 2017 [F001]."
_RE_MARCADOR_APOS_PONTO = re.compile(
    r"([.!?…]+[\"”’»)]*)((?:\s*\[\s*(?:F\d{3,}[^\]]*|sem[- ]fato[^\]]*|opini[aã]o[^\]]*)\])+)", re.I)
_RE_ROTULO_META = re.compile(r"\*\*([^*:]{1,40}):\*\*")


def frases_do_roteiro(texto: str, ignoradas: dict | None = None) -> list:
    """Divide o roteiro (markdown livre) em frases. → [{'linha', 'texto', 'ids', 'dispensada', 'origem'}]

    origem: 'texto' (fala), 'tabela' (uma linha de tabela = uma frase), 'titulo' (título de seção; título de vídeo
    também é afirmação) ou 'meta' (linha de metadados: **Motor:**, **Versão:**…). Blocos de código, comentários HTML
    e as seções "Checklist" e "Diagnóstico" não são texto do vídeo: ficam de fora e, se `ignoradas` for um dicionário,
    ele recebe a contagem de linhas por motivo."""
    conta = ignoradas if isinstance(ignoradas, dict) else {}
    paragrafos, atual = [], []
    pulando = None

    def fecha():
        nonlocal atual
        if atual:
            paragrafos.append(("texto", atual))
        atual = []

    def limpa(t: str) -> str:
        t = re.sub(r"\*\*|__|`|(?<!\w)[*_]|[*_](?!\w)", "", t)
        return _RE_MARCADOR_APOS_PONTO.sub(lambda m: " " + m.group(2).strip() + m.group(1), t).strip()

    em_comentario = em_codigo = False
    linhas = texto.lstrip("﻿").splitlines()
    for n, linha in enumerate(linhas, 1):
        bruta = linha.strip()
        if em_comentario:
            conta["comentário"] = conta.get("comentário", 0) + 1
            if "-->" in bruta:
                em_comentario = False
            continue
        if bruta.startswith("```") or bruta.startswith("~~~"):
            em_codigo = not em_codigo
            fecha()
            continue
        if em_codigo:
            conta["bloco de código"] = conta.get("bloco de código", 0) + 1
            continue
        if bruta.startswith("<!--"):
            conta["comentário"] = conta.get("comentário", 0) + 1
            em_comentario = "-->" not in bruta
            fecha()
            continue
        if not bruta or re.fullmatch(r"[-*_=]{3,}", bruta):
            fecha()
            continue
        if bruta.startswith("#"):
            fecha()
            titulo = bruta.lstrip("#").strip()
            pulando = next((rot for chave, rot in _SECOES_PULADAS.items() if normalizar(titulo).startswith(chave)), None)
            if pulando:
                continue
            titulo = re.sub(r"^roteiro(?:\s+melhorado)?\s*:?\s*", "", limpa(titulo), flags=re.I)
            if titulo:
                paragrafos.append(("titulo", [(n, titulo)]))
            continue
        if pulando:
            conta[f"seção {pulando}"] = conta.get(f"seção {pulando}", 0) + 1
            continue
        if bruta.startswith("|"):
            fecha()
            if re.fullmatch(r"[|\s:-]+", bruta):
                continue                                          # linha separadora do cabeçalho
            if n < len(linhas) and re.fullmatch(r"\|[|\s:-]+", linhas[n].strip()) and "-" in linhas[n]:
                conta["cabeçalho de tabela"] = conta.get("cabeçalho de tabela", 0) + 1
                continue                                          # "| Tempo | Fala |": nomes de coluna, não fala
            celulas = [limpa(c) for c in bruta.strip("|").split("|")]
            celulas = [c for c in celulas if c]
            if celulas:
                paragrafos.append(("tabela", [(n, " — ".join(celulas))]))
            continue
        m = _RE_ROTULO_META.match(bruta) or re.match(r"^([A-Za-zÀ-ÿ ]{1,40}):\s", bruta)
        if m and normalizar(m.group(1)) in _ROTULOS_META:
            fecha()
            valor = limpa(_RE_ROTULO_META.sub(" ", bruta[m.end():] if m.re is not _RE_ROTULO_META else bruta))
            if valor:
                paragrafos.append(("meta", [(n, valor)]))
            continue
        item = re.match(r"^(?:>\s*)*(?:[-*+]\s+|\d{1,3}[.)]\s+)", bruta)
        if item:
            fecha()
            bruta = bruta[item.end():]
        else:
            bruta = re.sub(r"^(?:>\s*)+", "", bruta)
        bruta = re.sub(r"^(?:slide|story|stories|cena|bloco|take|parte)\s+\d+\s*[—–:-]\s*", "", bruta, flags=re.I)
        bruta = limpa(bruta)
        if bruta:
            atual.append((n, bruta))
        if item:
            fecha()
    fecha()

    frases = []
    for origem, par in paragrafos:
        junto, mapa = "", []
        for n, t in par:
            mapa.append((len(junto), n))
            junto += t + " "
        junto = junto.rstrip()
        protegido = junto
        for ab in _ABREVIACOES:
            protegido = re.sub(re.escape(ab) + r"(?=\s)", ab.replace(".", "․"), protegido)
        ini = 0
        cortes = [m.end() for m in _RE_FIM_FRASE.finditer(protegido)] + [len(protegido)]
        for fim in cortes:
            pedaco = protegido[ini:fim].replace("․", ".").strip()
            pos = ini
            ini = fim
            if not pedaco:
                continue
            linha = par[0][0]
            for off, n in mapa:
                if off <= pos:
                    linha = n
            ids = marcadores_no_texto(pedaco)
            dispensada = bool(_RE_DISPENSA.search(pedaco))
            limpo = _RE_COLCHETE.sub(" ", pedaco)
            limpo = re.sub(r"\s+([.,;:!?…])", r"\1", re.sub(r"\s+", " ", limpo)).strip()
            limpo = re.sub(r"\s*[—–-]\s*$", "", limpo).strip().strip("\"“”").strip()
            if not re.search(r"[A-Za-zÀ-ÿ0-9]", limpo):
                continue
            frases.append({"linha": linha, "texto": limpo, "ids": ids, "dispensada": dispensada, "origem": origem})
    return frases


# período de cobrança dito na frase logo depois de um valor em dinheiro: assinatura não é preço de API
_PERIODOS_COBRANCA = (
    ("por mês", re.compile(r"\b(?:por\s+m[êe]s|ao\s+m[êe]s|/\s?m[êe]s|mensa(?:l|is)|mensalidade)\b", re.I)),
    ("por ano", re.compile(r"\b(?:por\s+ano|ao\s+ano|/\s?ano|anua(?:l|is)|anuidade)\b", re.I)),
    ("por usuário", re.compile(r"\bpor\s+(?:usu[áa]rio|pessoa|assento|licen[çc]a)\b", re.I)),
)


# entrada × saída: a troca mais comum em vídeo sobre IA (janela de contexto × limite de saída; preço de entrada ×
# preço de saída). Só acusa quando a frase fala de UM lado e o fato citado mede o OUTRO.
_RE_DIR_ENTRADA = re.compile(r"\b(?:entrada|input|l[êe]|lia|liam|l[êe]em|ler|leitura|janela|contexto)\b", re.I)
_RE_DIR_SAIDA = re.compile(r"\b(?:sa[íi]da|output|escrev\w+|ger(?:a|am|ava|avam|ar|ou|ad[oa]s?)|respostas?|respond\w+)\b", re.I)
_GRANDEZAS = (("tokens", r"tokens?"), ("palavras", r"palavras?"), ("páginas", r"p[áa]ginas?"),
              ("caracteres", r"caracteres?"), ("parâmetros", r"par[âa]metros?"), ("usuários", r"usu[áa]rios?"),
              ("linhas", r"linhas?"), ("imagens", r"image(?:m|ns)"), ("livros", r"livros?"), ("horas", r"horas?"),
              ("minutos", r"minutos?"), ("segundos", r"segundos?"), ("GPUs", r"gpus?"), ("chips", r"chips?"),
              ("camadas", r"camadas?"), ("documentos", r"documentos?"), ("arquivos", r"arquivos?"),
              ("mensagens", r"mensage(?:m|ns)"), ("perguntas", r"perguntas?"), ("assinantes", r"assinantes?"),
              ("funcionários", r"funcion[áa]rios?"), ("empresas", r"empresas?"), ("países", r"pa[íi]s(?:es)?"),
              ("idiomas", r"idiomas?|l[íi]nguas?"), ("modelos", r"modelos?"),
              ("bytes", r"(?:kilo|mega|giga|tera)?bytes?|[kmgt]b"))
_RE_GRANDEZA = re.compile(r"(?<![\w-])(?:" + "|".join(f"(?P<g{i}>{rx})" for i, (_, rx) in enumerate(_GRANDEZAS))
                          + r")(?![\w-])", re.I)


def _direcao(texto: str) -> str | None:
    """'entrada' | 'saida' | None (não fala de nenhum lado, ou fala dos dois)."""
    e, sd = bool(_RE_DIR_ENTRADA.search(texto or "")), bool(_RE_DIR_SAIDA.search(texto or ""))
    return "entrada" if e and not sd else "saida" if sd and not e else None


def _direcao_do_fato(f: dict) -> str | None:
    return _direcao(_txt(f.get("unidade"))) or _direcao(_txt(f.get("como_dizer")))


def _grandeza(texto: str, so_inicio: bool = False) -> str | None:
    """A primeira grandeza contável do texto ('tokens', 'palavras'…); com `so_inicio`, só se o texto começa por ela
    (depois de um "de" opcional): é o substantivo que o número mede."""
    if so_inicio:
        m = re.match(r"\s+(?:de\s+)?([\wÀ-ÿ-]+)", texto or "")
        texto = m.group(1) if m else ""
    m = _RE_GRANDEZA.search(texto or "")
    if not m or (so_inicio and m.span() != (0, len(texto))):
        return None
    return next(_GRANDEZAS[int(k[1:])][0] for k, v in m.groupdict().items() if v)


def _descreve_valor(indice: dict) -> str:
    if not indice["valor_itens"]:
        return "o valor do fato"
    return "o valor do fato é " + indice["valor_itens"][0]["bruto"]


def _conferir_itens(itens: list, ids: list, indices: dict) -> dict:
    """Cruza os dados numéricos `itens` com os fatos citados. → {'fora': [...], 'apoio': [(item, id)], 'trecho': [...]}"""
    r = {"fora": [], "apoio": [], "trecho": []}
    for it in itens:
        sit = {i: situacao_do_item(it, indices[i]) for i in ids}
        if "ok" in sit.values():
            continue
        if "apoio" in sit.values() or "trecho_valor" in sit.values():
            fid = next(i for i, v in sit.items() if v in ("apoio", "trecho_valor"))
            r["apoio"].append((it, fid, sit[fid]))
        elif "trecho" in sit.values():
            r["trecho"].append((it, next(i for i, v in sit.items() if v == "trecho")))
        else:
            r["fora"].append(it)
    return r


def conferir_roteiro(texto: str, ficha: dict, hoje: dt.date | None = None, dias: int = 14) -> dict:
    """Cruza cada frase do roteiro com a ficha. → relatório com 'pendencias', 'avisos', 'dispensadas', 'ignoradas'…

    A regra da casa é marcador explícito: frase com dado checável e sem [F###] é PENDÊNCIA, mesmo quando um fato da
    ficha parece cobri-la (o relatório sugere qual). Na frase marcada, cada dado é comparado POR TIPO com o fato
    citado: dinheiro com dinheiro (e a moeda), percentual com percentual, data com data, contagem com contagem."""
    hoje = hoje or hoje_local()
    fatos = {f["id"]: f for f in ficha.get("fatos", []) if isinstance(f, dict) and isinstance(f.get("id"), str)}
    indices = {fid: indexar_fato(f) for fid, f in fatos.items()}
    conhecidos = nomes_da_ficha(ficha)
    confirmados = [fid for fid, f in fatos.items() if f.get("status") == "confirmado"]
    pend, avisos, dispensadas, ignoradas = [], [], [], []
    usados, linhas_por_fato = [], {}
    linhas_ignoradas = {}
    frases = frases_do_roteiro(texto, linhas_ignoradas)
    checaveis = marcadas = 0

    def reg(lista, tipo, fr, detalhe, **extra):
        lista.append({"tipo": tipo, "linha": fr["linha"], "frase": fr["texto"], "detalhe": detalhe, **extra})

    for fr in frases:
        origem = fr.get("origem", "texto")
        ids_validos = [i for i in fr["ids"] if i in fatos]
        aceitos = [t for i in ids_validos for t in _termos(fatos[i])]
        an = analisar_frase(fr["texto"], conhecidos, aceitos)
        fortes, modelos, nomes = an["fortes"], an["modelos"], an["nomes"]
        if origem == "meta":                                      # "**Motor:** 2", "**Duração alvo:** 45–60s" não são dado
            fortes = [it for it in fortes if it["tipo"] in ("dinheiro", "percentual", "proporcao", "superlativo")]
        if origem in ("meta", "titulo"):                          # título e metadado: nome solto não é afirmação
            modelos, nomes = an["versionados"] if fortes or origem == "titulo" else [], []
        numericos = [it for it in fortes if it["tipo"] != "superlativo"]
        evid = [f"{it['bruto']} ({it['tipo']})" for it in fortes] + [f"{m} (modelo)" for m in modelos] \
            + [f"{n} (nome)" for n in nomes]
        if fortes or modelos or nomes:
            checaveis += 1
        if an["ignorados"] and not fr["ids"] and not fr["dispensada"]:
            reg(ignoradas, "fala_pessoal", fr, "número tratado como fala pessoal, chamada ou analogia, não como dado: "
                + ", ".join(it["bruto"] for it in an["ignorados"]))
        if an["diretos"] and not fr["ids"] and not fr["dispensada"]:
            reg(avisos, "fala_direta", fr, "número em frase dirigida ao espectador ("
                + ", ".join(it["bruto"] for it in an["diretos"]) + "): se é dado (\"você sabia que só 5 países…\"), "
                "registre o fato e marque; se é jeito de falar (\"você não precisa de 5 ferramentas\"), marque "
                "[sem-fato]", fato_ids=[], evidencias=[f"{it['bruto']} ({it['tipo']})" for it in an["diretos"]])
        for i in fr["ids"]:
            if i not in fatos:
                reg(pend, "marcador_inexistente", fr, f"o marcador [{i}] não existe na ficha: confira o id ou registre "
                    "o fato", fato_ids=[i], evidencias=evid)
        if fr["ids"]:
            marcadas += 1
        elif fr["dispensada"]:
            if fortes or modelos or nomes or an["diretos"]:
                reg(dispensadas, "dispensada", fr, "marcada como [sem-fato]/[opinião] pelo autor",
                    evidencias=evid + [f"{it['bruto']} ({it['tipo']})" for it in an["diretos"]])
            continue
        elif fortes:
            cruzados = []
            if numericos and not any(it["tipo"] == "superlativo" for it in fortes):
                cands = []
                for fid, ix in indices.items():
                    if not all(situacao_do_item(it, ix) == "ok" for it in numericos):
                        continue
                    comuns_nome = sum(1 for n in modelos + nomes if _nome_no_fato(n, ix))
                    comuns_pal = len(_palavras_de_conteudo(fr["texto"]) & ix["palavras"])
                    if comuns_nome >= 1 or (not (modelos or nomes) and comuns_pal >= 2):
                        cands.append((comuns_nome * 3 + comuns_pal, fid))
                if cands:
                    melhor = max(c[0] for c in cands)
                    cruzados = sorted(fid for pts, fid in cands if pts == melhor)
            if cruzados:
                reg(pend, "sem_marcador", fr, f"dado checável sem marcador; os números batem com {', '.join(cruzados)}: "
                    f"se a frase diz o que esse fato sustenta, acrescente [{cruzados[0]}] — o cruzamento automático "
                    "compara números e nomes, não o sentido", fato_ids=cruzados, evidencias=evid)
            else:
                so_sup = all(it["tipo"] == "superlativo" for it in fortes)
                reg(pend, "sem_fato", fr,
                    ("superlativo ou comparação sem fato: diga o critério e a data com fonte, ou tire"
                     if so_sup else "afirmação checável sem fato na ficha: pesquise a fonte primária e registre com "
                     "`fatos.py adicionar` (ou reescreva sem o dado; [sem-fato] só para o que não é afirmação)"),
                    fato_ids=[], evidencias=evid)
            continue
        elif modelos or nomes:
            falam = sorted(fid for fid, ix in indices.items() if any(_nome_no_fato(n, ix) for n in modelos + nomes))
            dica = (f" (os fatos {', '.join(falam)} falam desse nome: se a frase diz o que um deles sustenta, ponha o "
                    "marcador)" if falam else "")
            # o nome com versão que um fato CONFIRMADO registra pode ser dito de passagem; o que a ficha não conhece, não
            novos = [m for m in an["versionados"] if not any(_nome_no_fato(m, indices[i]) for i in confirmados)]
            if origem in ("titulo", "meta") and not (novos or an["afirma"] or an["relativos_fortes"]):
                continue                                          # título de seção com nome já registrado: não é fala
            if novos or an["afirma"] or an["relativos_fortes"]:
                motivo = ("modelo com versão que nenhum fato confirmado registra: " + ", ".join(novos) if novos else
                          "tempo relativo (" + ", ".join(an["relativos_fortes"]) + ")" if an["relativos_fortes"]
                          else "verbo de lançamento, preço, autoria ou licença")
                reg(pend, "sem_fato", fr, f"afirmação sobre nome próprio sem fato ({motivo}): nome, versão, data de "
                    "lançamento, preço e licença são exatamente o que caduca — registre o fato e marque, ou use "
                    f"[opinião]/[sem-fato] se não for afirmação{dica}", fato_ids=falam, evidencias=evid)
            else:
                reg(avisos, "so_nomes", fr, "cita nome próprio sem fato: se a frase afirma algo sobre ele (quem criou, "
                    f"quando, de quem é), registre o fato e marque{dica}", fato_ids=falam, evidencias=evid)
            continue
        else:
            continue

        for fid in ids_validos:
            if fid not in usados:
                usados.append(fid)
            linhas_por_fato.setdefault(fid, []).append(fr["linha"])
        if ids_validos:
            citados = ", ".join(ids_validos)
            r = _conferir_itens(numericos, ids_validos, indices)
            if r["fora"]:
                reg(pend, "numero_nao_bate", fr,
                    "a frase diz " + ", ".join(it["bruto"] for it in r["fora"]) + f", que não está em {citados} "
                    "(comparado por tipo com valor, como_dizer, termos, afirmacao e referente_a): corrija a frase ou o "
                    "fato", fato_ids=ids_validos, evidencias=evid)
            for it, fid, sit in r["apoio"]:
                onde = "na afirmacao" if sit == "apoio" else "só no trecho citado da fonte"
                reg(pend, "numero_nao_bate", fr, f"a frase diz {it['bruto']}, que aparece {onde} de {fid} como OUTRO dado "
                    f"({_descreve_valor(indices[fid])}): um fato por afirmação — registre esse número como fato próprio, "
                    "ou, se é o mesmo dado dito de outro jeito, ponha a forma em como_dizer ou termos",
                    fato_ids=[fid], evidencias=evid)
            for it, fid in r["trecho"]:
                reg(avisos, "so_no_trecho", fr, f"{it['bruto']} só aparece no trecho citado da fonte de {fid}, não em "
                    "valor, como_dizer, termos nem afirmacao: se o roteiro pode dizer esse dado, registre-o no fato",
                    fato_ids=[fid], evidencias=evid)
            textos = " ".join(normalizar(" ".join(_txt(fatos[i].get(k)) for k in ("unidade", "afirmacao", "como_dizer")))
                              for i in ids_validos)
            # dinheiro DITO na frase (antes de tirar as formas aceitas pelos termos: "quatro dólares por mês")
            dinheiro_dito = any(it["tipo"] == "dinheiro" for it in numericos) or any(
                it["tipo"] == "dinheiro" for it in extrair_numeros(fr["texto"], "pt", termos=conhecidos))
            for rotulo, rx in _PERIODOS_COBRANCA:
                if dinheiro_dito and rx.search(fr["texto"]) \
                        and not rx.search(" ".join(" ".join(_txt(fatos[i].get(k)) for k in
                                                            ("unidade", "afirmacao", "como_dizer")) for i in ids_validos)):
                    reg(pend, "unidade_nao_bate", fr, f"a frase cobra \"{rotulo}\" e {citados} não mede isso (unidade: "
                        + "; ".join(_txt(fatos[i].get("unidade")) or "—" for i in ids_validos) + "): preço de assinatura "
                        "e preço de API são fatos diferentes", fato_ids=ids_validos, evidencias=evid)
            lado = _direcao(fr["texto"])
            lados = {_direcao_do_fato(fatos[i]) for i in ids_validos} - {None}
            if lado and lados and lado not in lados and (numericos or dinheiro_dito):
                nome_lado = {"entrada": "entrada (o que o modelo lê)", "saida": "saída (o que o modelo escreve)"}
                reg(pend, "entrada_saida", fr, f"a frase fala de {nome_lado[lado]} e {citados} mede "
                    f"{nome_lado[next(iter(lados))]} (unidade: "
                    + "; ".join(_txt(fatos[i].get("unidade")) or "—" for i in ids_validos) + "): janela de contexto × "
                    "limite de saída e preço de entrada × preço de saída são fatos diferentes — cite o fato do lado "
                    "certo", fato_ids=ids_validos, evidencias=evid)
            for it in numericos:                                  # "1 milhão de PALAVRAS" citando fato de tokens
                if it["tipo"] not in ("numero", "ano"):
                    continue
                pos = fr["texto"].find(it["bruto"])
                dita = _grandeza(fr["texto"][pos + len(it["bruto"]):pos + len(it["bruto"]) + 40], True) if pos >= 0 else None
                if not dita:
                    continue
                rx_dita = re.compile(r"(?<![\w-])(?:" + dict(_GRANDEZAS)[dita] + r")(?![\w-])", re.I)
                medidas = {i: _grandeza(_txt(fatos[i].get("unidade"))) for i in ids_validos
                           if _item_em(it, indices[i]["valor_itens"])}
                # só acusa se o fato mede OUTRA grandeza e não fala da grandeza dita em lugar nenhum
                if medidas and all(g and g != dita and not rx_dita.search(" ".join(
                        [_txt(fatos[i].get(k)) for k in ("afirmacao", "como_dizer", "unidade")] + _termos(fatos[i])))
                        for i, g in medidas.items()):
                    fid = next(iter(medidas))
                    reg(pend, "unidade_nao_bate", fr, f"a frase diz {it['bruto']} de {dita} e {fid} mede "
                        f"{medidas[fid]} (unidade: {_txt(fatos[fid].get('unidade'))}): o número é o mesmo, a grandeza "
                        "não — corrija a frase ou cite o fato certo", fato_ids=[fid], evidencias=evid)
            for mnome in modelos:
                if not any(_nome_no_fato(mnome, indices[i]) for i in ids_validos):
                    reg(pend, "modelo_fora_do_fato", fr, f"a frase cita {mnome}, que não aparece em {citados}: o marcador "
                        "é o certo? Se a frase afirma algo sobre esse nome, cite também o fato dele; se é só outro "
                        "jeito de chamar o mesmo modelo, ponha em `termos` do fato", fato_ids=ids_validos,
                        evidencias=evid)
            for nome in nomes:
                if not any(_nome_no_fato(nome, indices[i]) for i in ids_validos):
                    reg(avisos, "nome_fora_do_fato", fr, f"a frase cita {nome}, que não aparece em {citados}: confira se "
                        "o fato sustenta o que a frase diz sobre esse nome", fato_ids=ids_validos, evidencias=evid)
            for it in fortes:
                if it["tipo"] == "superlativo" and (" " + normalizar(it["bruto"]) + " ") not in " " + textos + " ":
                    # sem marcador, superlativo é pendência; o marcador de um fato que não o sustenta não o absolve
                    reg(pend, "superlativo_fora_do_fato", fr, f"\"{it['bruto']}\" não está na redação de {citados}: "
                        "o fato não sustenta essa comparação — registre o fato que a sustenta (critério, placar e data) "
                        "e cite-o, ou tire o superlativo", fato_ids=ids_validos, evidencias=evid)
            if an["relativos"] and any(_volatil(fatos[i]) for i in ids_validos):
                reg(avisos, "tempo_relativo", fr, "tempo relativo (" + ", ".join(an["relativos"]) + ") em fato volátil: "
                    "troque por data (\"em outubro de 2026\") — o vídeo fica no ar depois que o dado muda",
                    fato_ids=ids_validos, evidencias=evid)

    for fid in usados:
        f = fatos[fid]
        linhas = ", ".join(str(n) for n in linhas_por_fato[fid])
        base = {"linha": linhas_por_fato[fid][0], "frase": f.get("afirmacao", ""), "fato_ids": [fid], "evidencias": []}
        if f.get("status") != "confirmado":
            dica = ("resolva a divergência (qual fonte prevalece e por quê) ou reescreva o fato como faixa/ressalva "
                    "verificável" if f.get("status") == "divergente" else "confirme com fonte primária ou tire do roteiro")
            pend.append({"tipo": "status", **base, "detalhe": f"{fid} está \"{f.get('status')}\" e é usado na(s) "
                         f"linha(s) {linhas}: {dica}"})
        else:
            conf = conferencia_do_fato(f)
            if conf["ausentes"]:
                pend.append({"tipo": "trecho_ausente", **base, "detalhe": f"{fid} é usado na(s) linha(s) {linhas} e a "
                             f"última conferência NÃO achou o trecho na página (fonte "
                             f"{', '.join(map(str, conf['ausentes']))}): abra a página; se o dado mudou, atualize o fato; "
                             "se ela é montada por JavaScript, registre a leitura com `fatos.py atualizar "
                             f"{fid} --conferido-manual \"…\"`"})
            elif not conf["ok"]:
                avisos.append({"tipo": "nao_conferido", **base, "detalhe": f"{fid} é usado na(s) linha(s) {linhas} e o "
                               "trecho da fonte ainda não foi conferido na página: rode `fatos.py checar-links "
                               "--trechos`"})
        c = ler_data(f.get("caduca_em"))
        if c and c < hoje:
            pend.append({"tipo": "vencido", **base, "detalhe": f"{fid} caducou em {c.isoformat()} (há "
                         f"{(hoje - c).days} dias) e é usado na(s) linha(s) {linhas}: abra a fonte de novo e rode "
                         f"`fatos.py atualizar {fid} --revalidado --caduca-em AAAA-MM-DD`"})
        elif c and (c - hoje).days <= dias:
            avisos.append({"tipo": "a_vencer", **base, "detalhe": f"{fid} caduca em {c.isoformat()} "
                           f"(em {(c - hoje).days} dias): se o vídeo sai depois disso, revalide antes de publicar"})
    nao_usados = [fid for fid in fatos if fid not in usados]
    return {"ok": not pend, "hoje": hoje.isoformat(),
            "frases": sum(1 for fr in frases if fr.get("origem") in ("texto", "tabela")),
            "titulos_e_metadados": sum(1 for fr in frases if fr.get("origem") in ("titulo", "meta")),
            "checaveis": checaveis, "marcadas": marcadas, "pendencias": pend, "avisos": avisos,
            "dispensadas": dispensadas, "ignoradas": ignoradas, "linhas_ignoradas": linhas_ignoradas,
            "fatos_usados": usados, "fatos_nao_usados": nao_usados}


# ----------------------------------------------------------------------------- conferir storyboard
# parâmetros de cena que não são texto do vídeo (aparência, arquivos, o próprio crédito)
_PARAMS_NAO_TEXTO = {"fonte", "plataforma", "cores", "cor", "papel", "alinhar", "posicao", "escala_titulo", "foto",
                     "arquivo", "imagem", "video", "audio", "src", "cena", "id", "entrada", "saida", "icone", "fundo",
                     "formato", "estilo", "tema", "animacao", "curva", "transicao", "prefixo", "unidade"}
# chaves cujo NÚMERO é dado mostrado na tela; os demais números de params são aparência (casas, destaque, max…)
_PARAMS_DADO = {"valor", "valores", "value", "values", "numero", "numeros", "total", "quantidade", "percentual",
                "pct", "preco"}
# Cenas embutidas do motor da direção de arte e o crédito (lido do kit em 2026-10-06, versão 1.3.0): só `citacao` e
# `barras` leem params.fonte (pela peça compartilhada cenas/_credito.js); `titulo`, `gc` e `moldura` o ignoram. Cena
# própria de outra skill desenha o crédito com ctx.kit.credito(texto). Único ponto a trocar se isso mudar no kit.
CENAS_SEM_CREDITO = ("titulo", "gc", "moldura")
_RE_ARQUIVO_OU_COR = re.compile(r"^(?:#[0-9a-fA-F]{3,8}|https?://\S+|[\w./\\ -]+\.[A-Za-z0-9]{2,5})$")


def dados_da_cena(cena: dict, conhecidos=(), aceitos=()) -> list:
    """Dados numéricos que a cena põe na TELA: do `trecho`, dos textos de `params` e dos números em chaves de dado
    (valor, valores, total…). → [(onde, item)]. Número de `params.dados[].valor` ganha o tipo de `prefixo`/`unidade`."""
    achados = []
    if isinstance(cena.get("trecho"), str):
        an = analisar_frase(cena["trecho"], conhecidos, aceitos)
        achados += [("trecho", it) for it in an["fortes"]]
    params = cena.get("params") if isinstance(cena.get("params"), dict) else {}
    prefixo, unidade = _txt(params.get("prefixo")), _txt(params.get("unidade"))
    moeda = _RE_MOEDA_QUALQUER.search(prefixo) or _RE_MOEDA_QUALQUER.search(unidade)
    e_pct = bool(_RE_PCT_QUALQUER.search(unidade))
    mult = _RE_MULT_PALAVRA.match(" " + unidade.strip()) or re.match(r"^\s*(k|K|M|B|T)\b", unidade)
    fator = _MULT.get({"milhao": "million", "milhoes": "million", "bilhao": "billion", "bilhoes": "billion",
                       "trilhao": "trillion", "trilhoes": "trillion"}.get(normalizar(mult.group(1)), normalizar(mult.group(1))),
                      1.0) if mult else 1.0

    def anda(obj, caminho, chave):
        if isinstance(obj, dict):
            for k, v in obj.items():
                anda(v, f"{caminho}.{k}", str(k).lower())
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                anda(v, f"{caminho}[{i}]", chave)
        elif isinstance(obj, str):
            if chave in _PARAMS_NAO_TEXTO or _RE_ARQUIVO_OU_COR.match(obj.strip()):
                return
            for it in analisar_frase(obj, conhecidos, aceitos)["fortes"]:
                achados.append((caminho, it))
        elif isinstance(obj, (int, float)) and not isinstance(obj, bool) and chave in _PARAMS_DADO:
            v = float(obj) * fator
            bruto = f"{prefixo}{obj:g}{unidade}".strip()
            if moeda:
                achados.append((caminho, _item("dinheiro", bruto, [v], moeda=_moeda_norm(moeda.group(0)))))
            elif e_pct:
                achados.append((caminho, _item("percentual", bruto, [v])))
            else:
                achados.append((caminho, _item("livre", bruto, [v])))

    anda(params, "params", "")
    return achados


def conferir_storyboard(sb, ficha: dict, hoje: dt.date | None = None, dias: int = 14) -> dict:
    """Confere roteiro/storyboard.json: fato_ids existem, estão confirmados, conferidos e vigentes; os números que a
    cena põe na tela (trecho e params) batem, por tipo, com os fatos citados; o crédito de cada cena."""
    hoje = hoje or hoje_local()
    fatos = {f["id"]: f for f in ficha.get("fatos", []) if isinstance(f, dict) and isinstance(f.get("id"), str)}
    indices = {fid: indexar_fato(f) for fid, f in fatos.items()}
    conhecidos = nomes_da_ficha(ficha)
    pend, avisos, cenas = [], [], []
    if not isinstance(sb, dict) or not isinstance(sb.get("cenas"), list):
        raise ErroFatos("o storyboard não tem o formato do contrato (objeto com a lista \"cenas\")",
                        "veja o contrato de roteiro/storyboard.json (skill video-animacao-explicativa)")
    for c in sb["cenas"]:
        if not isinstance(c, dict):
            continue
        cid = str(c.get("id", "?"))
        ids = [str(i).upper() for i in (c.get("fato_ids") or []) if isinstance(i, str)]
        params = c.get("params") if isinstance(c.get("params"), dict) else {}
        creditos, validos = [], []
        for fid in ids:
            f = fatos.get(fid)
            if f is None:
                pend.append({"tipo": "marcador_inexistente", "cena": cid, "fato_ids": [fid],
                             "detalhe": f"cena {cid}: o fato {fid} não existe na ficha"})
                continue
            validos.append(fid)
            if f.get("status") != "confirmado":
                pend.append({"tipo": "status", "cena": cid, "fato_ids": [fid],
                             "detalhe": f"cena {cid}: {fid} está \"{f.get('status')}\" — não vai para a tela"})
            else:
                conf = conferencia_do_fato(f)
                if conf["ausentes"]:
                    pend.append({"tipo": "trecho_ausente", "cena": cid, "fato_ids": [fid],
                                 "detalhe": f"cena {cid}: a última conferência não achou o trecho de {fid} na página — "
                                            "abra a fonte antes de renderizar"})
                elif not conf["ok"]:
                    avisos.append({"tipo": "nao_conferido", "cena": cid, "fato_ids": [fid],
                                   "detalhe": f"cena {cid}: o trecho de {fid} ainda não foi conferido na página (rode "
                                              "`fatos.py checar-links --trechos`)"})
            cd = ler_data(f.get("caduca_em"))
            if cd and cd < hoje:
                pend.append({"tipo": "vencido", "cena": cid, "fato_ids": [fid],
                             "detalhe": f"cena {cid}: {fid} caducou em {cd.isoformat()} — revalide antes de renderizar"})
            elif cd and (cd - hoje).days <= dias:
                avisos.append({"tipo": "a_vencer", "cena": cid, "fato_ids": [fid],
                               "detalhe": f"cena {cid}: {fid} caduca em {cd.isoformat()} (em {(cd - hoje).days} dias)"})
            try:
                creditos.append(credito(f)["param_cena"])
            except ErroFatos:
                pass
        esperado = "; ".join(dict.fromkeys(creditos))
        fonte = params.get("fonte")
        nome_cena = Path(_txt(c.get("cena"))).stem.lower()
        if ids and creditos and nome_cena in CENAS_SEM_CREDITO:
            avisos.append({"tipo": "sem_credito", "cena": cid, "fato_ids": ids,
                           "detalhe": f"cena {cid} mostra fato e a cena embutida `{nome_cena}` não desenha crédito (só "
                                      "`citacao` e `barras` leem params.fonte): mostre o dado numa delas ou credite "
                                      f"{json.dumps(esperado, ensure_ascii=False)} numa cena própria"})
        elif ids and creditos:
            if not isinstance(fonte, str) or not fonte.strip():
                avisos.append({"tipo": "sem_credito", "cena": cid, "fato_ids": ids,
                               "detalhe": f"cena {cid} mostra fato e não tem crédito: ponha params.fonte = "
                                          f"{json.dumps(esperado, ensure_ascii=False)}"})
            elif re.match(r"^\s*fontes?\s*:", fonte, re.I):
                avisos.append({"tipo": "prefixo_duplicado", "cena": cid, "fato_ids": ids,
                               "detalhe": f"cena {cid}: params.fonte já traz \"Fonte:\" — o prefixo é do motor (token "
                                          "graficos.citacao_fonte.prefixo da DA; versões antigas do kit o repetiam na "
                                          f"tela): passe só {json.dumps(esperado, ensure_ascii=False)}"})
            elif normalizar(fonte) != normalizar(esperado):
                avisos.append({"tipo": "credito_diferente", "cena": cid, "fato_ids": ids,
                               "detalhe": f"cena {cid}: params.fonte é {json.dumps(fonte, ensure_ascii=False)}; a ficha "
                                          f"dá {json.dumps(esperado, ensure_ascii=False)}"})
        aceitos = [t for i in validos for t in _termos(fatos[i])]
        na_tela = dados_da_cena(c, conhecidos, aceitos)
        if validos:
            numericos = [(onde, it) for onde, it in na_tela if it["tipo"] != "superlativo"]
            r = _conferir_itens([it for _, it in numericos], validos, indices)
            onde_de = {id(it): onde for onde, it in numericos}
            citados = ", ".join(validos)
            for it in r["fora"]:
                pend.append({"tipo": "numero_nao_bate", "cena": cid, "fato_ids": validos,
                             "detalhe": f"cena {cid}: a tela mostra {it['bruto']} ({onde_de[id(it)]}), que não está em "
                                        f"{citados}: corrija a cena ou o fato — é o número que o espectador pausa para ler"})
            for it, fid, sit in r["apoio"]:
                pend.append({"tipo": "numero_nao_bate", "cena": cid, "fato_ids": [fid],
                             "detalhe": f"cena {cid}: a tela mostra {it['bruto']} ({onde_de[id(it)]}), que em {fid} é "
                                        f"OUTRO dado ({_descreve_valor(indices[fid])}): cite o fato desse número"})
            for it, fid in r["trecho"]:
                avisos.append({"tipo": "so_no_trecho", "cena": cid, "fato_ids": [fid],
                               "detalhe": f"cena {cid}: {it['bruto']} ({onde_de[id(it)]}) só aparece no trecho citado "
                                          f"da fonte de {fid}: registre o dado no fato se ele vai para a tela"})
        elif not ids and na_tela:
            pend.append({"tipo": "sem_fato", "cena": cid, "fato_ids": [],
                         "detalhe": f"cena {cid}: a tela mostra dado checável ("
                                    + ", ".join(dict.fromkeys(f"{it['bruto']} em {onde}" for onde, it in na_tela))
                                    + ") e fato_ids está vazio: toda cena com número cita o fato e leva crédito"})
        cenas.append({"id": cid, "fato_ids": ids, "credito": esperado or None})
    return {"ok": not pend, "hoje": hoje.isoformat(), "cenas": cenas, "pendencias": pend, "avisos": avisos}


# ----------------------------------------------------------------------------- checar links
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
       "Chrome/126.0 Safari/537.36 video-ops-fatos/1")
_MAX_LEITURA = 3_000_000


class _Redirecionamentos(urllib.request.HTTPRedirectHandler):
    def __init__(self):
        self.cadeia = []

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.cadeia.append((code, newurl))
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _texto_da_pagina(corpo: bytes, charset: str | None):
    bruto = corpo.decode(charset or "utf-8", "replace")
    visivel = re.sub(r"(?is)<(script|style|noscript|svg|template)\b.*?</\1\s*>", " ", bruto)
    visivel = re.sub(r"(?s)<!--.*?-->", " ", visivel)
    visivel = _html.unescape(re.sub(r"(?s)<[^>]+>", " ", visivel))
    codigo = _html.unescape(re.sub(r"(?s)<[^>]+>", " ", bruto))
    return normalizar(visivel), normalizar(codigo)


def checar_url(url: str, prazo: float = 12.0, trechos=()) -> dict:
    """Um GET com prazo. Nunca levanta: devolve {'url', 'estado', 'http', 'final', 'detalhe', 'trechos'}.

    estados: ok · redirecionado · bloqueado (o site recusa robôs: 401/403/429, outros 4xx que não 404/410, 202 vazio
    ou laço de redirecionamento) · quebrado (404/410) · erro_servidor (5xx) · sem_resposta (DNS, conexão, tempo) ·
    erro_tls"""
    r = {"url": url, "estado": "sem_resposta", "http": None, "final": None, "detalhe": "", "trechos": {}}
    red = _Redirecionamentos()
    try:
        # cookies em memória, só durante esta requisição: há sites oficiais (ai.google.dev) que redirecionam em
        # laço para um login silencioso quando o cliente não devolve o cookie que acabaram de entregar
        opener = urllib.request.build_opener(red, urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        # inglês primeiro: os trechos da ficha estão no idioma original e há sites (ai.google.dev) que traduzem a
        # página conforme o Accept-Language — o trecho deixaria de ser encontrado
        req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept-Language": "en-US,en;q=0.9,pt-BR;q=0.6",
                                                   "Accept": "text/html,application/xhtml+xml,*/*;q=0.8"})
        with opener.open(req, timeout=prazo) as resp:
            r["http"] = resp.status
            final = resp.geturl()
            tipo = (resp.headers.get_content_type() or "").lower()
            charset = resp.headers.get_content_charset()
            corpo = resp.read(_MAX_LEITURA if trechos else 2048)
        r["estado"] = "ok"
        if r["http"] in (202, 204):
            r["estado"] = "bloqueado"
            r["detalhe"] = (f"HTTP {r['http']}: o servidor respondeu sem conteúdo (desafio anti-robô) — abra no navegador "
                            "para conferir")
        elif red.cadeia and final.rstrip("/") != url.rstrip("/"):
            r["estado"], r["final"] = "redirecionado", final
            codigos = "→".join(str(c) for c, _ in red.cadeia)
            r["detalhe"] = f"{codigos} → {final}" + (" (permanente: troque o endereço pelo destino)"
                                                      if any(c in (301, 308) for c, _ in red.cadeia) else "")
        for t in trechos:
            if r["estado"] == "bloqueado":
                r["trechos"][t] = "nao_verificado (a página não foi entregue ao robô)"
                continue
            if "html" not in tipo and "text" not in tipo:
                r["trechos"][t] = f"nao_verificado ({tipo or 'tipo desconhecido'}: confira abrindo o arquivo)"
                continue
            visivel, codigo = _texto_da_pagina(corpo, charset)
            alvo = normalizar(t)
            if alvo and alvo in visivel:
                r["trechos"][t] = "encontrado"
            elif alvo and alvo in codigo:
                r["trechos"][t] = "encontrado (no código da página)"
            else:
                r["trechos"][t] = ("ausente (o HTML baixado não contém o trecho: a página mudou ou é montada por "
                                   "JavaScript — abra no navegador e confira)")
    except urllib.error.HTTPError as e:
        r["http"] = e.code
        e.close()
        if e.code in (401, 403, 429, 451, 999):
            r["estado"] = "bloqueado"
            r["detalhe"] = f"HTTP {e.code}: o site recusa acesso automático — abra no navegador para conferir"
        elif 300 <= e.code < 400:
            r["estado"] = "bloqueado"
            r["detalhe"] = (f"HTTP {e.code}: redirecionamento em laço ou sem destino (o site exige login ou cookies) — "
                            "abra no navegador para conferir")
        elif 500 <= e.code < 600:
            r["estado"], r["detalhe"] = "erro_servidor", f"HTTP {e.code}: tente de novo mais tarde"
        elif e.code in (404, 410):
            r["estado"] = "quebrado"
            r["detalhe"] = f"HTTP {e.code}: a página saiu do ar ou mudou de endereço — ache a nova URL oficial"
        else:                                                     # 400, 405, 406…: o servidor recusou ESTE pedido
            r["estado"] = "bloqueado"
            r["detalhe"] = (f"HTTP {e.code}: o servidor recusou o pedido automático (não prova que a página caiu) — abra "
                            "no navegador para conferir")
    except urllib.error.URLError as e:
        motivo = e.reason
        if isinstance(motivo, ssl.SSLError):
            r["estado"], r["detalhe"] = "erro_tls", f"certificado/TLS: {motivo}"
        elif isinstance(motivo, socket.timeout) or "timed out" in str(motivo).lower():
            r["detalhe"] = f"sem resposta em {prazo:g} s"
        elif isinstance(motivo, socket.gaierror):
            r["detalhe"] = "o domínio não resolve (DNS)"
        else:
            r["detalhe"] = f"falha de conexão: {motivo}"
    except (socket.timeout, TimeoutError):
        r["detalhe"] = f"sem resposta em {prazo:g} s"
    except ssl.SSLError as e:
        r["estado"], r["detalhe"] = "erro_tls", f"certificado/TLS: {e}"
    except Exception as e:  # noqa: BLE001 — um link ruim não derruba os outros
        r["detalhe"] = f"{type(e).__name__}: {e}"
    return r


def tem_rede(prazo: float = 4.0) -> bool:
    """Sonda curta: consegue abrir uma conexão TCP 443 com algum servidor conhecido?"""
    for host in ("www.wikipedia.org", "www.google.com", "arxiv.org"):
        try:
            socket.create_connection((host, 443), timeout=prazo).close()
            return True
        except OSError:
            continue
    return False


def urls_de_texto(texto: str) -> list:
    """URLs http(s) de um texto qualquer (markdown, roteiro, descrição), sem repetir e na ordem em que aparecem."""
    vistos = []
    for m in re.finditer(r"https?://[^\s<>()\[\]\"'`|]+", texto or ""):
        u = m.group(0).rstrip(".,;:!?*_")
        if u not in vistos:
            vistos.append(u)
    return vistos


def checar_mapa(por_url: dict, prazo: float = 12.0, paralelo: int = 4, checar=checar_url, sonda=tem_rede) -> dict:
    """Confere um mapa {url: {'usos': [...], 'trechos': [...]}}. `checar` e `sonda` são injetáveis (testes sem rede)."""
    resultados = []
    if por_url:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, min(paralelo, len(por_url)))) as ex:
            futuros = {ex.submit(checar, url, prazo, tuple(d.get("trechos") or ())): url for url, d in por_url.items()}
            for fut in concurrent.futures.as_completed(futuros):
                url = futuros[fut]
                try:
                    r = fut.result()
                except Exception as e:  # noqa: BLE001 — um link ruim não derruba os outros
                    r = {"url": url, "estado": "sem_resposta", "http": None, "final": None,
                         "detalhe": f"{type(e).__name__}: {e}", "trechos": {}}
                r["usos"] = por_url[url].get("usos") or []
                resultados.append(r)
    ordem = list(por_url)
    resultados.sort(key=lambda r: ordem.index(r["url"]))
    cont = {}
    for r in resultados:
        cont[r["estado"]] = cont.get(r["estado"], 0) + 1
    sem_rede = bool(resultados) and all(r["estado"] == "sem_resposta" for r in resultados) and not sonda()
    falhas = [r for r in resultados if r["estado"] in ("quebrado", "erro_servidor", "erro_tls", "sem_resposta")]
    trechos_ausentes = sum(1 for r in resultados for v in r.get("trechos", {}).values() if v.startswith("ausente"))
    return {"conferido_em": dt.datetime.now().astimezone().isoformat(timespec="seconds"), "prazo": prazo,
            "urls": len(resultados), "contagem": cont, "sem_rede": sem_rede,
            "ok": not falhas and not sem_rede and not trechos_ausentes,
            "trechos_ausentes": trechos_ausentes, "resultados": resultados}


def checar_links(ficha: dict, prazo: float = 12.0, ids=None, com_trechos: bool = False, paralelo: int = 4,
                 checar=checar_url, sonda=tem_rede) -> dict:
    """Confere cada URL única das fontes da ficha (uma requisição por URL, mesmo que sirva a vários fatos)."""
    por_url = {}
    for f in ficha.get("fatos", []):
        if not isinstance(f, dict) or (ids and f.get("id") not in ids):
            continue
        for i, s in enumerate(f.get("fontes") if isinstance(f.get("fontes"), list) else [], 1):
            if isinstance(s, dict) and isinstance(s.get("url"), str) and s["url"].strip():
                item = por_url.setdefault(s["url"], {"usos": [], "trechos": []})
                item["usos"].append(f"{f.get('id')}#{i}")
                if com_trechos and s.get("trecho") and s["trecho"] not in item["trechos"]:
                    item["trechos"].append(s["trecho"])
    return checar_mapa(por_url, prazo, paralelo, checar, sonda)


# ----------------------------------------------------------------------------- medir o crédito com a DA (opcional)
def medir_credito(texto: str, projeto: Path, formato: str = "horizontal") -> dict:
    """Largura do crédito no papel/tamanho do token graficos.citacao_fonte × largura da zona segura.

    `texto` é o corpo do crédito ("Editor, mês/ano"); o prefixo é o da DA (graficos.citacao_fonte.prefixo, padrão
    "Fonte: ") e, como na peça de crédito do motor, não é duplicado se o texto já começar por ele.
    Único ponto de contato com o kit de direção de arte (API de kit-api.md §3 e §4): se a API mudar, é aqui."""
    kit = Path(__file__).resolve().parents[2] / "video-direcao-de-arte" / "kit"
    if not (kit / "da.py").is_file():
        kit = Path("~/.claude/skills/video-direcao-de-arte/kit").expanduser()
    if not (kit / "da.py").is_file():
        raise ErroFatos("o kit de direção de arte não está instalado ao lado desta skill",
                        "instale a skill video-direcao-de-arte em \"$CRIABR_SKILLS\"/ ou rode `credito` sem --caber")
    sys.path.insert(0, str(kit))
    sys.dont_write_bytecode = True                                # não deixar __pycache__ dentro do kit
    try:
        try:
            import da as _da                                      # type: ignore
            import texto as _texto                                # type: ignore
        except ImportError as e:
            raise ErroFatos(f"--caber usa o kit de direção de arte, que precisa de Pillow e numpy ({e})",
                            "rode com o Python que tem as duas bibliotecas (nesta casa: /opt/homebrew/bin/python3); "
                            "o resto do fatos.py funciona só com a biblioteca padrão")
        try:
            d = _da.carregar(str(projeto), compilar=False)
        except Exception as e:  # noqa: BLE001
            if type(e).__name__ == "SemDA":
                raise ErroFatos("o projeto ainda não tem direção de arte (da/da.json): não há como medir o crédito",
                                "crie a DA com a skill video-direcao-de-arte, ou rode `credito` sem --caber",
                                SAIDA_SEM_FICHA)
            raise ErroFatos(f"não consegui carregar a DA do projeto ({type(e).__name__}: {e})",
                            "rode `da.py validar` na pasta do projeto")
        try:
            cf = d["graficos"]["citacao_fonte"]
            prefixo = cf["prefixo"] if isinstance(cf.get("prefixo"), str) else "Fonte: "
            corpo = texto.strip()
            na_tela = corpo if not prefixo or corpo.lower().startswith(prefixo.strip().lower()) else prefixo + corpo
            px = d.px(cf["tamanho"], formato)
            estilo = _texto.Estilo.do_papel(d, cf["papel"], tamanho_px=px, cor=cf.get("cor", "texto_suave"))
            largura = float(_texto.medir(na_tela, estilo)["largura"])
            util = float(d.margens(formato)["largura"])
        except ErroFatos:
            raise
        except Exception as e:  # noqa: BLE001
            if type(e).__name__ == "DAErro":                      # erro de uso que o kit já explica (formato inexistente…)
                raise ErroFatos(f"--caber: {e}", "os formatos são os da DA do projeto (horizontal, vertical…)", SAIDA_USO)
            raise ErroFatos(f"a API do kit de direção de arte mudou ou a DA não tem graficos.citacao_fonte "
                            f"({type(e).__name__}: {e})", "confira kit-api.md; rode `credito` sem --caber")
        return {"formato": formato, "papel": cf["papel"], "tamanho_px": px, "posicao": cf.get("posicao"),
                "texto_na_tela": na_tela, "largura_px": round(largura, 1), "largura_util_px": round(util, 1),
                "cabe": largura <= util}
    finally:
        try:
            sys.path.remove(str(kit))
        except ValueError:
            pass


# ----------------------------------------------------------------------------- CLI
class _Formatador(argparse.RawDescriptionHelpFormatter):
    def add_usage(self, usage, actions, groups, prefix=None):
        return super().add_usage(usage, actions, groups, prefix="uso: " if prefix is None else prefix)


class _Parser(argparse.ArgumentParser):
    _TRADUCOES = [
        (r"the following arguments are required: (.*)", r"faltam argumentos obrigatórios: \1"),
        (r"unrecognized arguments: (.*)", r"argumentos não reconhecidos: \1"),
        (r"argument (.*?): invalid choice: (.*?) \(choose from (.*?)\)", r"argumento \1: opção inválida \2 (escolha entre \3)"),
        (r"invalid choice: (.*?) \(choose from (.*?)\)", r"opção inválida \1 (escolha entre \2)"),
        (r"maybe you meant: (.*)", r"você quis dizer: \1"),
        (r"argument (.*?): expected one argument", r"argumento \1: faltou o valor"),
        (r"argument (.*?): expected at least one argument", r"argumento \1: faltou ao menos um valor"),
        (r"argument (.*?): invalid (?:float|int) value: (.*)", r"argumento \1: número inválido \2"),
        (r"argument (.*?): not allowed with argument (.*)", r"argumento \1: não pode ser usado junto com \2"),
        (r"argument (.*?): ignored explicit argument (.*)", r"argumento \1: não recebe valor (veio \2)"),
    ]

    def __init__(self, *a, **k):
        k.setdefault("add_help", False)
        k.setdefault("formatter_class", _Formatador)
        super().__init__(*a, **k)
        self._positionals.title = "argumentos"
        self._optionals.title = "opções"
        self.add_argument("-h", "--help", action="help", default=argparse.SUPPRESS, help="mostra esta ajuda e sai")

    def error(self, message):
        for padrao, troca in self._TRADUCOES:
            message = re.sub(padrao, troca, message)
        self.print_usage(sys.stderr)
        self.exit(SAIDA_USO, f"erro: {message}\n  → veja as opções com: {self.prog} --help\n")


def _comuns() -> argparse.ArgumentParser:
    c = argparse.ArgumentParser(add_help=False)
    c.add_argument("--projeto", metavar="PASTA", default=argparse.SUPPRESS,
                   help="raiz do projeto de vídeo (padrão: sobe as pastas a partir da atual até achar pesquisa/fatos.json)")
    c.add_argument("--ficha", metavar="ARQUIVO", default=argparse.SUPPRESS,
                   help="caminho direto de um fatos.json (vence --projeto)")
    c.add_argument("--hoje", metavar="AAAA-MM-DD", default=argparse.SUPPRESS,
                   help="simula outra data em comando de LEITURA — ex.: a data de publicação, para ver o que estará "
                        "vencido (ou VIDEO_OPS_HOJE). Comando que grava recusa: a ficha leva sempre a data real")
    return c


def _ler_json_arg(valor: str, o_que: str = "o fato"):
    """JSON literal, @arquivo.json ou - (entrada padrão)."""
    if valor == "-":
        bruto, origem = sys.stdin.read(), "entrada padrão"
    elif valor.startswith("@"):
        caminho = Path(valor[1:]).expanduser()
        try:
            bruto, origem = caminho.read_text(encoding="utf-8-sig"), str(caminho)
        except FileNotFoundError:
            raise ErroFatos(f"arquivo não encontrado: {caminho}", "confira o caminho depois do @ (use aspas se houver "
                            "espaço: \"@pesquisa/_novo fato.json\")", SAIDA_USO)
        except (OSError, UnicodeDecodeError) as e:
            raise ErroFatos(f"não consegui ler {caminho}: {e}", codigo=SAIDA_USO)
    else:
        bruto, origem = valor, "argumento"
    try:
        return json.loads(bruto)
    except json.JSONDecodeError as e:
        raise ErroFatos(f"JSON inválido em {origem} (linha {e.lineno}, coluna {e.colno}: {e.msg})",
                        f"para {o_que}, grave o JSON num arquivo e passe @arquivo.json — evita briga de aspas no shell",
                        SAIDA_USO)


def _alvo(args):
    return getattr(args, "projeto", None), getattr(args, "ficha", None)


def _hoje(args) -> dt.date:
    """Data para comandos de LEITURA (aceita a simulação de --hoje / VIDEO_OPS_HOJE)."""
    return hoje_local(getattr(args, "hoje", None))


def _hoje_gravacao(args) -> dt.date:
    """Data para comandos que GRAVAM: sempre a real. Data simulada na ficha a faz reprovar ("data no futuro")."""
    if getattr(args, "hoje", None):
        raise ErroFatos(f"--hoje só simula leitura (vencidos, validar, conferir-roteiro, resumo…); `{args.comando}` grava "
                        "na ficha e usa sempre a data real", "rode de novo sem --hoje", SAIDA_USO)
    if os.environ.get("VIDEO_OPS_HOJE"):
        hoje_local()                                              # valida o formato; erro de uso se estiver ruim
        print(f"nota: VIDEO_OPS_HOJE={os.environ['VIDEO_OPS_HOJE']} ignorada — `{args.comando}` grava com a data real "
              f"({data_real().isoformat()})", file=sys.stderr)
    return data_real()


def _rel(caminho: Path) -> str:
    try:
        return os.path.relpath(caminho)
    except ValueError:
        return str(caminho)


def _imprimir_achados(titulo: str, itens: list, saida=None) -> None:
    saida = saida or sys.stdout
    if not itens:
        return
    print(f"{titulo} ({len(itens)})", file=saida)
    for it in itens:
        onde = it["id"] + (f".{it['campo']}" if it.get("campo") else "")
        print(f"  {onde}: {it['mensagem']}", file=saida)


def _cmd_novo(args) -> int:
    projeto, ficha_arg = _alvo(args)
    hoje = _hoje_gravacao(args)
    if ficha_arg:
        caminho = Path(ficha_arg).expanduser()
    else:
        raiz = Path(projeto).expanduser() if projeto else Path.cwd()
        if not projeto and not any((raiz / p).exists() for p in ("da", "roteiro", "pesquisa", "CLAUDE.md")):
            raise ErroFatos(f"{raiz} não parece a raiz de um projeto de vídeo (não tem da/, roteiro/, pesquisa/ nem "
                            "CLAUDE.md)", "se é aqui mesmo que o projeto começa, confirme a pasta: fatos.py novo --tema "
                            "\"…\" --projeto . (ou passe --projeto \"<pasta do projeto>\")", SAIDA_USO)
        if not raiz.is_dir():
            raise ErroFatos(f"a pasta do projeto não existe: {raiz}",
                            "crie o projeto antes (da.py init \"<pasta>\" --nome \"…\") ou confira o caminho", SAIDA_USO)
        caminho = raiz / "pesquisa" / "fatos.json"
    with trava_da_ficha(caminho):
        if caminho.exists() and not args.forcar:
            raise ErroFatos(f"já existe uma ficha em {caminho}: nada foi sobrescrito",
                            "continue com `adicionar`; para recomeçar do zero passe --forcar (a atual vira "
                            "pesquisa/_fatos.anterior.json)")
        ficha = nova_ficha(args.tema, hoje)
        salvar(ficha, caminho, hoje)
    print(f"ficha criada: {_rel(caminho)} (tema: {ficha['tema']})")
    print("próximo passo: pesquise cada afirmação na fonte primária e registre com `fatos.py adicionar "
          "\"@pesquisa/_novos.json\"` (uma lista JSON registra vários de uma vez, tudo ou nada); depois `fatos.py "
          "checar-links --trechos`")
    return SAIDA_OK


def _travada(caminho: Path, gravando: bool = True):
    """A trava da ficha, se a pasta dela existe (sem ficha, `carregar` dá o erro certo — não se cria pasta à toa)."""
    return trava_da_ficha(caminho) if gravando and Path(caminho).parent.is_dir() else contextlib.nullcontext()


def _cmd_adicionar(args) -> int:
    hoje = _hoje_gravacao(args)
    dados = _ler_json_arg(args.fato)
    lote = dados if isinstance(dados, list) else [dados]
    if not lote:
        raise ErroFatos("a lista de fatos veio vazia", codigo=SAIDA_USO)
    with _travada(achar_ficha(*_alvo(args)), not args.simular):
        ficha, caminho = carregar(*_alvo(args))
        feitos = []
        for n, bruto in enumerate(lote, 1):
            try:
                r = adicionar(ficha, bruto, hoje, args.acessado_hoje, args.caduca_padrao, args.forcar)
            except ErroFatos as e:
                if len(lote) > 1:
                    e.mensagem = f"item {n} da lista — {e.mensagem}"
                raise
            feitos.append(r)
        if args.simular:
            for r in feitos:
                print(f"(simulação) {r['id']} seria adicionado")
            print("nada foi gravado (--simular)")
            return SAIDA_OK
        salvar(ficha, caminho, hoje)
    for r in feitos:
        f = obter(ficha, r["id"])
        print(f"{r['id']} adicionado [{f['categoria']} · {f['status']} · confiança {f['confianca']}]: {f['afirmacao']}")
        for o in r["observacoes"]:
            print(f"  nota: {o}")
        for a in r["avisos"]:
            print(f"  aviso — {a['campo']}: {a['mensagem']}")
    print(f"ficha: {_rel(caminho)} ({_plural(len(ficha['fatos']), 'fato', 'fatos')})")
    return SAIDA_OK


def _cmd_atualizar(args) -> int:
    hoje = _hoje_gravacao(args)
    mudancas = {}
    if args.json:
        m = _ler_json_arg(args.json, "as mudanças")
        if not isinstance(m, dict):
            raise ErroFatos("as mudanças precisam ser um objeto JSON com os campos a alterar", codigo=SAIDA_USO)
        mudancas.update(m)
    for campo, valor in (("status", args.status), ("confianca", args.confianca), ("como_dizer", args.como_dizer),
                         ("notas", args.notas), ("afirmacao", args.afirmacao), ("referente_a", args.referente_a)):
        if valor is not None:
            mudancas[campo] = valor
    if args.caduca_em is not None:
        mudancas["caduca_em"] = None if args.caduca_em.lower() in ("null", "nunca", "nao", "não") else args.caduca_em
    nova_fonte = None
    if args.nova_fonte:
        nova_fonte = _ler_json_arg(args.nova_fonte, "a fonte")
        if not isinstance(nova_fonte, dict):
            raise ErroFatos("--nova-fonte precisa ser um objeto JSON (titulo, url, editor, tipo, publicado_em, "
                            "acessado_em, trecho)", codigo=SAIDA_USO)
    revalidado = "todas" if args.revalidado else (args.revalidar_fonte or None)
    if not mudancas and nova_fonte is None and not revalidado and args.conferido_manual is None:
        raise ErroFatos("nada a atualizar: passe um JSON com os campos, ou --status/--confianca/--caduca-em/"
                        "--como-dizer/--notas/--nova-fonte/--revalidado/--conferido-manual", codigo=SAIDA_USO)
    with _travada(achar_ficha(*_alvo(args))):
        ficha, caminho = carregar(*_alvo(args))
        r = atualizar(ficha, args.id, mudancas, nova_fonte, revalidado, hoje, args.acessado_hoje,
                      conferido_manual=args.conferido_manual, fontes_alvo=args.na_fonte)
        salvar(ficha, caminho, hoje)
    f = obter(ficha, r["id"])
    partes = sorted(mudancas) + (["nova fonte"] if nova_fonte else []) \
        + (["conferência manual registrada"] if args.conferido_manual is not None else []) \
        + (["fontes revalidadas hoje"] if revalidado else [])
    print(f"{r['id']} atualizado ({', '.join(partes)}) → [{f['categoria']} · {f['status']} · confiança {f['confianca']}"
          f" · caduca em {f['caduca_em'] or 'nunca'}]")
    for a in r["avisos"]:
        print(f"  aviso — {a['campo']}: {a['mensagem']}")
    return SAIDA_OK


def _cmd_remover(args) -> int:
    hoje = _hoje_gravacao(args) if args.sim else None
    with _travada(achar_ficha(*_alvo(args)), args.sim):
        ficha, caminho = carregar(*_alvo(args))
        alvo = obter(ficha, args.id)
        if not args.sim:
            print(f"(simulação) removeria {alvo['id']}: {alvo.get('afirmacao', '')}")
            print("nada foi gravado; confirme com --sim. O id não será reaproveitado; marcadores no roteiro e no "
                  "storyboard passam a acusar fato inexistente.")
            return SAIDA_OK
        ficha["ultimo_id"] = max(int(ficha.get("ultimo_id") or 0), int(proximo_id(ficha)[1:]) - 1)
        ficha["fatos"] = [f for f in ficha["fatos"] if f is not alvo]
        salvar(ficha, caminho, hoje)
    print(f"{alvo['id']} removido (cópia da ficha anterior em pesquisa/_fatos.anterior.json)")
    return SAIDA_OK


def _cmd_validar(args) -> int:
    caminho = achar_ficha(*_alvo(args))
    if not caminho.is_file():
        raise ErroFatos(f"não há ficha de fatos em {caminho}", 'crie uma com: fatos.py novo --tema "…"', SAIDA_SEM_FICHA)
    rel = validar_ficha(ler_json(caminho), _hoje(args))
    reprovado = bool(rel["erros"]) or (args.estrito and bool(rel["avisos"]))
    if args.json:
        print(json.dumps({**rel, "ok": not reprovado, "ficha": str(caminho)}, ensure_ascii=False, indent=2))
        return SAIDA_PENDENCIA if reprovado else SAIDA_OK
    _imprimir_achados("ERROS", rel["erros"])
    _imprimir_achados("AVISOS", rel["avisos"])
    print(f"{_rel(caminho)}: {_plural(rel['fatos'], 'fato', 'fatos')}, {_plural(len(rel['erros']), 'erro', 'erros')}, "
          f"{_plural(len(rel['avisos']), 'aviso', 'avisos')} → " + ("REPROVADA" if reprovado else "ok")
          + (" (--estrito: aviso reprova)" if args.estrito and not rel["erros"] and rel["avisos"] else ""))
    return SAIDA_PENDENCIA if reprovado else SAIDA_OK


def _cmd_vencidos(args) -> int:
    ficha, _ = carregar(*_alvo(args))
    if args.dias < 0:
        raise ErroFatos("--dias não pode ser negativo", codigo=SAIDA_USO)
    v = vencimentos(ficha, _hoje(args), args.dias)
    if args.json:
        print(json.dumps(v, ensure_ascii=False, indent=2))
        return SAIDA_PENDENCIA if v["vencidos"] else SAIDA_OK
    if v["vencidos"]:
        print(f"VENCIDOS ({len(v['vencidos'])}) — revalidar antes de gravar ou publicar")
        for x in v["vencidos"]:
            print(f"  {x['id']} [{x['categoria']}] caducou em {x['caduca_em']} (há {-x['dias']} dias): {x['afirmacao']}")
    if v["a_vencer"]:
        print(f"VENCEM EM ATÉ {v['dias']} DIAS ({len(v['a_vencer'])})")
        for x in v["a_vencer"]:
            quando = "hoje" if x["dias"] == 0 else f"em {x['dias']} dias"
            print(f"  {x['id']} [{x['categoria']}] caduca em {x['caduca_em']} ({quando}): {x['afirmacao']}")
    if not v["vencidos"] and not v["a_vencer"]:
        print(f"nenhum fato vencido nem a vencer em {v['dias']} dias (hoje: {v['hoje']})")
    else:
        print("para revalidar: abra a fonte, confira o trecho e rode `fatos.py atualizar <id> --revalidado "
              "--caduca-em AAAA-MM-DD` (se o valor mudou, atualize valor, afirmacao, como_dizer e trecho)")
    return SAIDA_PENDENCIA if v["vencidos"] else SAIDA_OK


def _cmd_md(args) -> int:
    ficha, caminho = carregar(*_alvo(args))
    hoje = _hoje(args)
    rel = validar_ficha(ficha, hoje)
    if rel["erros"] and not args.mesmo_com_erros:
        raise ErroFatos(f"a ficha tem {_plural(len(rel['erros']), 'erro', 'erros')} de validação: os .md não foram gerados",
                        "rode `fatos.py validar`, corrija e gere de novo (ou passe --mesmo-com-erros)")
    ids = None
    if args.roteiro:
        roteiro = Path(args.roteiro).expanduser()
        try:
            ids = marcadores_no_texto(roteiro.read_text(encoding="utf-8-sig"))
        except FileNotFoundError:
            raise ErroFatos(f"roteiro não encontrado: {roteiro}", "confira o caminho (use aspas se houver espaço)")
        except (OSError, UnicodeDecodeError) as e:
            raise ErroFatos(f"não consegui ler o roteiro {roteiro}: {e}")
    pasta = caminho.parent
    gravar_texto(pasta / "fatos.md", gerar_fatos_md(ficha, hoje))
    gravar_texto(pasta / "fontes.md", gerar_fontes_md(ficha, hoje, ids))
    n = len(fontes_para_descricao(ficha, ids))
    print(f"gerados: {_rel(pasta / 'fatos.md')} ({_plural(len(ficha['fatos']), 'fato', 'fatos')}) e "
          f"{_rel(pasta / 'fontes.md')} ({_plural(n, 'fonte única', 'fontes únicas')}"
          + (f", só de {_plural(len(ids), 'fato citado', 'fatos citados')} no roteiro" if ids is not None else "") + ")")
    if rel["avisos"]:
        print(f"a ficha tem {_plural(len(rel['avisos']), 'aviso', 'avisos')}: veja com `fatos.py validar`")
    return SAIDA_OK


def _ler_texto(caminho: str, o_que: str) -> str:
    p = Path(caminho).expanduser()
    try:
        return p.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        raise ErroFatos(f"{o_que} não encontrado: {p}", "confira o caminho (use aspas se houver espaço)", SAIDA_USO)
    except IsADirectoryError:
        raise ErroFatos(f"{p} é uma pasta: passe o arquivo de {o_que}", codigo=SAIDA_USO)
    except UnicodeDecodeError:
        raise ErroFatos(f"{p} não está em UTF-8", "regrave o arquivo em UTF-8")


def _cmd_conferir_roteiro(args) -> int:
    ficha, caminho = carregar(*_alvo(args))
    texto = _ler_texto(args.roteiro, "roteiro")
    rel = conferir_roteiro(texto, ficha, _hoje(args), args.dias)
    reprovado = bool(rel["pendencias"]) or (args.estrito and bool(rel["avisos"]))
    rel = {**rel, "ok": not reprovado, "roteiro": str(args.roteiro), "ficha": str(caminho)}
    if args.saida:
        gravar_json(Path(args.saida).expanduser(), rel)
    if args.json:
        print(json.dumps(rel, ensure_ascii=False, indent=2))
        return SAIDA_PENDENCIA if reprovado else SAIDA_OK
    print(f"CONFERÊNCIA DO ROTEIRO — {args.roteiro} × {_rel(caminho)} ({_plural(len(ficha['fatos']), 'fato', 'fatos')}) "
          f"— hoje {rel['hoje']}")
    print(f"frases: {rel['frases']} (+ {rel['titulos_e_metadados']} de título e metadado) · com algo checável: "
          f"{rel['checaveis']} · com marcador: {rel['marcadas']}")
    if rel["linhas_ignoradas"]:
        print("linhas fora da conferência: " + ", ".join(f"{n} de {motivo}" for motivo, n in
                                                           sorted(rel["linhas_ignoradas"].items())))
    rotulos = {"sem_fato": "sem fato", "numero_nao_bate": "não bate", "marcador_inexistente": "marcador inexistente",
               "status": "status", "vencido": "vencido", "sem_marcador": "sem marcador", "so_nomes": "nome próprio",
               "modelo_fora_do_fato": "modelo fora do fato", "tempo_relativo": "tempo relativo", "a_vencer": "a vencer",
               "dispensada": "dispensada", "unidade_nao_bate": "unidade", "so_no_trecho": "só no trecho",
               "nome_fora_do_fato": "nome fora do fato", "superlativo_fora_do_fato": "superlativo",
               "trecho_ausente": "trecho ausente", "nao_conferido": "não conferido", "fala_pessoal": "fala pessoal",
               "fala_direta": "fala ao espectador", "entrada_saida": "entrada × saída"}

    def bloco(titulo, itens):
        if not itens:
            return
        print(f"\n{titulo} ({len(itens)})")
        for it in itens:
            if it["tipo"] in ("status", "vencido", "a_vencer", "trecho_ausente", "nao_conferido"):
                print(f"  [{rotulos[it['tipo']]}] {it['detalhe']}")
                continue
            print(f"  [{rotulos.get(it['tipo'], it['tipo'])}] linha {it['linha']}: “{it['frase']}”")
            if it.get("evidencias"):
                print(f"      checável: {' · '.join(it['evidencias'])}")
            print(f"      → {it['detalhe']}")

    bloco("PENDÊNCIAS — o roteiro não segue para gravação assim", rel["pendencias"])
    bloco("AVISOS — revise a olho (com --estrito também reprovam)", rel["avisos"])
    bloco("DISPENSADAS PELO AUTOR — confira se são mesmo opinião ou chamada", rel["dispensadas"])
    bloco("NÚMEROS IGNORADOS — fala pessoal, chamada ou analogia; se for dado, ponha o marcador", rel["ignoradas"])
    if rel["fatos_nao_usados"]:
        print(f"\nfatos da ficha não usados no roteiro: {', '.join(rel['fatos_nao_usados'])}")
    print(f"\nRESULTADO: {_plural(len(rel['pendencias']), 'pendência', 'pendências')}, "
          f"{_plural(len(rel['avisos']), 'aviso', 'avisos')} → " + ("REPROVADO" if reprovado else "ok")
          + (" (--estrito: aviso reprova)" if args.estrito and not rel["pendencias"] and rel["avisos"] else "")
          + (" — há avisos: leia-os; antes de gravar rode com --estrito" if not reprovado and rel["avisos"] else ""))
    return SAIDA_PENDENCIA if reprovado else SAIDA_OK


def _cmd_conferir_storyboard(args) -> int:
    ficha, caminho = carregar(*_alvo(args))
    arq = Path(args.storyboard).expanduser() if args.storyboard else raiz_do_projeto(caminho) / "roteiro" / "storyboard.json"
    if not arq.is_file():
        raise ErroFatos(f"storyboard não encontrado: {arq}", "ele é escrito pela skill video-animacao-explicativa em "
                        "roteiro/storyboard.json; passe o caminho se estiver em outro lugar", SAIDA_USO)
    rel = conferir_storyboard(ler_json(arq, "storyboard"), ficha, _hoje(args), args.dias)
    reprovado = bool(rel["pendencias"]) or (args.estrito and bool(rel["avisos"]))
    if args.json:
        print(json.dumps({**rel, "ok": not reprovado, "storyboard": str(arq)}, ensure_ascii=False, indent=2))
        return SAIDA_PENDENCIA if reprovado else SAIDA_OK
    print(f"CONFERÊNCIA DO STORYBOARD — {_rel(arq)} × {_rel(caminho)} — hoje {rel['hoje']}")
    for c in rel["cenas"]:
        if c["fato_ids"]:
            print(f"  {c['id']}: {', '.join(c['fato_ids'])} → params.fonte = "
                  f"{json.dumps(c['credito'], ensure_ascii=False) if c['credito'] else '(sem crédito possível)'}")
    for titulo, itens in (("PENDÊNCIAS", rel["pendencias"]), ("AVISOS", rel["avisos"])):
        if itens:
            print(f"\n{titulo} ({len(itens)})")
            for it in itens:
                print(f"  {it['detalhe']}")
    print(f"\nRESULTADO: {_plural(len(rel['pendencias']), 'pendência', 'pendências')}, "
          f"{_plural(len(rel['avisos']), 'aviso', 'avisos')} → " + ("REPROVADO" if reprovado else "ok"))
    return SAIDA_PENDENCIA if reprovado else SAIDA_OK


def _cmd_credito(args) -> int:
    ficha, caminho = carregar(*_alvo(args))
    hoje = _hoje(args)
    f = obter(ficha, args.id)
    if f.get("status") != "confirmado" and not args.forcar:
        raise ErroFatos(f"{f['id']} está \"{f.get('status')}\": fato não confirmado não vai para a tela",
                        "confirme o fato (fonte primária) antes; --forcar só para ver o texto")
    conf = conferencia_do_fato(f)
    if f.get("status") == "confirmado" and not conf["ok"] and not args.forcar:
        if conf["ausentes"]:
            raise ErroFatos(f"{f['id']}: a última conferência NÃO achou o trecho na página (fonte "
                            f"{', '.join(map(str, conf['ausentes']))}): o fato não vai para a tela",
                            "abra a página; se o dado mudou, atualize o fato; se o trecho não era literal, corrija-o e "
                            "rode `fatos.py checar-links --trechos`; --forcar só para ver o texto")
        raise ErroFatos(f"{f['id']}: o trecho da fonte ainda não foi conferido na página: o fato não vai para a tela",
                        f"rode `fatos.py checar-links --trechos --id {f['id']}` (se o robô não lê a página: `fatos.py "
                        f"atualizar {f['id']} --conferido-manual \"onde e como você leu\"`); --forcar só para ver o texto")
    c = credito(f, args.fonte, args.data, args.todas)
    cd = ler_data(f.get("caduca_em"))
    if cd and cd < hoje:
        print(f"aviso: {f['id']} caducou em {cd.isoformat()} — revalide antes de renderizar a cena", file=sys.stderr)
    if c["data_origem"] == "acessado_em":
        print("nota: a fonte não tem data de publicação; o crédito usa o mês do acesso", file=sys.stderr)
    medida = None
    if args.caber:
        medida = medir_credito(c["param_cena"], raiz_do_projeto(caminho), args.caber)
    if args.json:
        print(json.dumps({**c, "medida": medida}, ensure_ascii=False, indent=2))
    else:
        print(c["param_cena"] if args.sem_prefixo else c["texto"])
    if medida:
        msg = (f"{'cabe' if medida['cabe'] else 'NÃO CABE'}: “{medida['texto_na_tela']}” mede {medida['largura_px']:g} px "
               f"de {medida['largura_util_px']:g} px úteis no formato {medida['formato']} (papel {medida['papel']}, "
               f"{medida['tamanho_px']} px, token graficos.citacao_fonte)")
        print(msg, file=sys.stderr)
        if not medida["cabe"]:
            print("  → encurte o editor na ficha, use --data ano, ou mostre uma fonte só (sem --todas)", file=sys.stderr)
            return SAIDA_PENDENCIA
    return SAIDA_OK


def _cmd_checar_links(args) -> int:
    if args.prazo <= 0:
        raise ErroFatos("--prazo precisa ser maior que zero", codigo=SAIDA_USO)
    conf = None
    if args.arquivo:
        if args.id or args.trechos:
            raise ErroFatos("--arquivo confere as URLs de um texto qualquer: não combina com --id nem com --trechos",
                            codigo=SAIDA_USO)
        urls = urls_de_texto(_ler_texto(args.arquivo, "arquivo"))
        rel = checar_mapa({u: {"usos": [], "trechos": []} for u in urls}, args.prazo)
        vazio = f"nenhuma URL encontrada em {args.arquivo}"
    else:
        hoje = _hoje_gravacao(args) if args.trechos else None
        ficha, caminho = carregar(*_alvo(args))
        ids = [i.upper() for i in args.id] if args.id else None
        for i in ids or []:
            obter(ficha, i)
        rel = checar_links(ficha, args.prazo, ids, args.trechos)   # a rede fica FORA da trava: pode demorar
        vazio = "nenhuma URL para conferir (a ficha não tem fontes)"
        if args.trechos and rel["resultados"] and not rel["sem_rede"]:
            with trava_da_ficha(caminho):
                ficha, caminho = carregar(*_alvo(args))           # recarrega: outro comando pode ter gravado
                conf = registrar_conferencias(ficha, rel, hoje)
                salvar(ficha, caminho, hoje)
            rel["conferencias"] = conf
            pendentes = [f.get("id") for f in ficha["fatos"] if isinstance(f, dict) and (not ids or f.get("id") in ids)
                         and f.get("status") == "confirmado" and _fontes(f) and not conferencia_do_fato(f)["ok"]]
            rel["fatos_sem_conferencia"] = pendentes
            rel["ok"] = rel["ok"] and not pendentes
        if not ids:
            try:
                gravar_json(caminho.with_name("_links.json"), rel)
            except OSError:
                pass
    codigo = SAIDA_SEM_REDE if rel["sem_rede"] else (SAIDA_OK if rel["ok"] else SAIDA_PENDENCIA)
    if args.json:
        print(json.dumps(rel, ensure_ascii=False, indent=2))
        return codigo
    if not rel["resultados"]:
        print(vazio)
        return SAIDA_OK
    for r in rel["resultados"]:
        http = f"HTTP {r['http']}" if r["http"] else "sem resposta"
        print(f"  {r['estado']:<13} {http:<13} {r['url']}" + (f"  [{', '.join(r['usos'])}]" if r["usos"] else ""))
        if r["detalhe"]:
            print(f"      {r['detalhe']}")
        for t, res in r.get("trechos", {}).items():
            print(f"      trecho “{t[:60]}{'…' if len(t) > 60 else ''}”: {res}")
    cont = ", ".join(f"{n} {e}" for e, n in sorted(rel["contagem"].items()))
    print(f"{_plural(rel['urls'], 'URL', 'URLs')}: {cont}")
    if rel["sem_rede"]:
        print("SEM REDE: nenhuma URL respondeu — nada foi verificado nem gravado; tente de novo com conexão",
              file=sys.stderr)
    elif rel["contagem"].get("bloqueado"):
        print("bloqueado ≠ quebrado: o site recusa robôs. Abra no navegador (ou com WebFetch) e confira à mão.")
    if conf is not None:
        print(f"trechos (gravado em cada fonte da ficha): {conf['encontrado']} encontrado(s), {conf['ausente']} "
              f"ausente(s), {conf['nao_verificado']} não verificado(s)"
              + (f", {conf['manual_mantida']} com conferência manual mantida" if conf["manual_mantida"] else ""))
        if rel["fatos_sem_conferencia"]:
            print("REPROVADO: fato confirmado com trecho ausente ou não verificado: "
                  + ", ".join(rel["fatos_sem_conferencia"]) + ". Abra cada página: se o dado mudou, atualize o fato; se "
                  "o trecho não era literal, corrija-o; se o robô não lê a página (JavaScript, PDF, bloqueio), leia no "
                  "navegador e registre com `fatos.py atualizar <id> --conferido-manual \"onde e como você leu\"`.")
    elif rel["trechos_ausentes"]:
        print(f"{_plural(rel['trechos_ausentes'], 'trecho não foi achado', 'trechos não foram achados')} no HTML: "
              "abra a página; se o dado mudou, o fato precisa ser atualizado")
    return codigo


def _cmd_resumo(args) -> int:
    ficha, caminho = carregar(*_alvo(args))
    hoje = _hoje(args)
    r = resumo(ficha, hoje)
    links = None
    try:
        links = json.loads(caminho.with_name("_links.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    if args.json:
        r["links"] = {"conferido_em": links.get("conferido_em"), "contagem": links.get("contagem"),
                      "trechos_ausentes": links.get("trechos_ausentes")} if links else None
        r["lista"] = [{"id": f.get("id"), "categoria": f.get("categoria"), "status": f.get("status"),
                       "confianca": f.get("confianca"), "caduca_em": f.get("caduca_em"),
                       "afirmacao": f.get("afirmacao")} for f in ficha["fatos"] if isinstance(f, dict)]
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return SAIDA_OK
    print(f"FICHA DE FATOS — {r['tema']} ({_rel(caminho)})")
    print(f"atualizada em {r['atualizado_em']} · hoje {r['hoje']} · {_plural(r['fatos'], 'fato', 'fatos')} · "
          f"{_plural(r['fontes'], 'fonte', 'fontes')}")
    print("status:    " + " · ".join(f"{k} {v}" for k, v in r["por_status"].items()))
    print("categoria: " + " · ".join(f"{k} {v}" for k, v in r["por_categoria"].items() if v) if r["fatos"] else "categoria: —")
    print("confiança: " + " · ".join(f"{k} {v}" for k, v in r["por_confianca"].items()))
    print(f"validação: {_plural(r['erros'], 'erro', 'erros')}, {_plural(r['avisos'], 'aviso', 'avisos')}"
          + (" → rode `fatos.py validar`" if r["erros"] or r["avisos"] else ""))
    print("vencidos:  " + (", ".join(r["vencidos"]) or "nenhum") + " · a vencer em 14 dias: "
          + (", ".join(r["a_vencer"]) or "nenhum"))
    if links:
        cont = ", ".join(f"{n} {e}" for e, n in sorted((links.get("contagem") or {}).items()))
        print(f"links:     conferidos em {str(links.get('conferido_em', ''))[:16].replace('T', ' ')} — {cont or '—'}")
    else:
        print("links:     ainda não conferidos (rode `fatos.py checar-links --trechos`)")
    t = r["trechos"]
    print(f"trechos:   {t['encontrados']} encontrado(s) · {t['manuais']} com conferência manual · {t['ausentes']} "
          f"AUSENTE(S) · {t['nao_verificados']} que o robô não leu · {t['nunca']} nunca conferido(s) (fontes de fatos "
          "confirmados)" + (f" → sem conferência completa: {', '.join(map(str, r['sem_conferencia']))}"
                            if r["sem_conferencia"] else ""))
    for f in ficha["fatos"]:
        if isinstance(f, dict):
            marca = {"confirmado": "✓", "divergente": "≠", "nao_confirmado": "?"}.get(_txt(f.get("status")), " ")
            if marca == "✓" and f.get("id") in r["sem_conferencia"]:
                marca = "!"                                       # confirmado, mas com trecho ausente ou não conferido
            af = str(f.get("afirmacao", ""))
            print(f"  {marca} {f.get('id')} [{f.get('categoria')}] {af[:96]}{'…' if len(af) > 96 else ''}")
    return SAIDA_OK


def construir_parser() -> _Parser:
    comuns = _comuns()
    p = _Parser(prog="fatos.py", parents=[comuns],
                description="Ficha de fatos verificada de um vídeo sobre IA: cada afirmação checável do roteiro com fonte "
                            "primária, data de acesso, trecho, confiança e data em que caduca.\n"
                            "A ficha mora em <projeto>/pesquisa/fatos.json; este script é o único que escreve nela.",
                epilog="Códigos de saída: 0 ok · 1 pendência/reprovado · 2 não há ficha · 64 uso incorreto · 75 sem rede.\n"
                       "Ordem de trabalho: novo → adicionar (um fato por afirmação) → validar → checar-links → md → "
                       "conferir-roteiro → credito → vencidos (antes de publicar).")
    sub = p.add_subparsers(dest="comando", metavar="<subcomando>", parser_class=_Parser, title="subcomandos")

    s = sub.add_parser("novo", parents=[comuns], help="cria pesquisa/fatos.json no projeto",
                       description="Cria a ficha vazia em <projeto>/pesquisa/fatos.json. Não sobrescreve uma existente.")
    s.add_argument("--tema", required=True, help="assunto do vídeo (ex.: \"Como funciona um modelo de linguagem\")")
    s.add_argument("--forcar", action="store_true", help="recomeça do zero (a ficha atual vira pesquisa/_fatos.anterior.json)")
    s.set_defaults(func=_cmd_novo)

    s = sub.add_parser("adicionar", parents=[comuns], help="acrescenta um fato (JSON, @arquivo ou -) e atribui o id F###",
                       description="Acrescenta um fato. O JSON traz afirmacao, valor, unidade, referente_a, categoria, "
                                   "status, confianca, caduca_em, fontes[], como_dizer, notas (e, se quiser, termos[] e "
                                   "autodeclarado). Uma lista de objetos adiciona vários de uma vez (tudo ou nada).\n"
                                   "Recusa: fato que não passa na validação e duplicata óbvia.")
    s.add_argument("fato", help="JSON do fato, @arquivo.json ou - (entrada padrão). Prefira @arquivo: evita briga de aspas")
    s.add_argument("--acessado-hoje", action="store_true", help="preenche acessado_em com a data de hoje nas fontes sem esse campo")
    s.add_argument("--caduca-padrao", action="store_true",
                   help="preenche caduca_em com a validade sugerida (preco 30 dias, modelo e benchmark 60) quando faltar")
    s.add_argument("--forcar", action="store_true", help="grava mesmo se parecer duplicata")
    s.add_argument("--simular", action="store_true", help="valida e mostra o id que seria atribuído, sem gravar")
    s.set_defaults(func=_cmd_adicionar)

    s = sub.add_parser("atualizar", parents=[comuns], help="altera campos de um fato, acrescenta fonte ou marca como revalidado",
                       description="Altera um fato existente e revalida antes de gravar. O JSON opcional traz só os campos "
                                   "que mudam (\"fontes\" substitui a lista inteira; para acrescentar uma, use "
                                   "--nova-fonte). Mudar a url ou o trecho de uma fonte apaga a conferência dela.")
    s.add_argument("id", help="id do fato (F001)")
    s.add_argument("json", nargs="?", help="JSON com os campos a alterar, @arquivo.json ou -")
    s.add_argument("--status", choices=STATUS, help="novo status")
    s.add_argument("--confianca", choices=CONFIANCAS, help="nova confiança")
    s.add_argument("--caduca-em", metavar="AAAA-MM-DD|null", help="nova data de validade (null = não caduca)")
    s.add_argument("--como-dizer", metavar="TEXTO", help="nova redação segura para o roteiro")
    s.add_argument("--afirmacao", metavar="TEXTO", help="nova afirmação")
    s.add_argument("--referente-a", metavar="TEXTO", help="novo período de referência")
    s.add_argument("--notas", metavar="TEXTO", help="novas notas")
    s.add_argument("--nova-fonte", metavar="JSON", help="acrescenta uma fonte (JSON, @arquivo ou -)")
    s.add_argument("--revalidado", action="store_true",
                   help="você abriu TODAS as fontes de novo HOJE e os trechos continuam lá: atualiza acessado_em de "
                        "todas e grava verificado_em. Exige o trecho conferido hoje (rode antes `checar-links --trechos "
                        "--id <id>`, ou junte --conferido-manual)")
    s.add_argument("--revalidar-fonte", type=int, action="append", metavar="N",
                   help="como --revalidado, mas só para a fonte N (1 = a primeira; pode repetir)")
    s.add_argument("--conferido-manual", metavar="NOTA",
                   help="declara que você abriu a página e leu o trecho quando o robô não consegue (página montada por "
                        "JavaScript, PDF, site que bloqueia): a NOTA diz onde e como leu (mínimo de 20 caracteres) e "
                        "fica na ficha e no fatos.md")
    s.add_argument("--na-fonte", type=int, action="append", metavar="N",
                   help="aplica --conferido-manual só à fonte N (padrão: todas as fontes do fato; pode repetir)")
    s.add_argument("--acessado-hoje", action="store_true", help="data de hoje nas fontes novas sem acessado_em")
    s.set_defaults(func=_cmd_atualizar)

    s = sub.add_parser("remover", parents=[comuns], help="tira um fato da ficha (simula; confirme com --sim)",
                       description="Remove um fato. Sem --sim só mostra o que faria. O id nunca é reaproveitado.")
    s.add_argument("id", help="id do fato (F001)")
    s.add_argument("--sim", action="store_true", help="confirma a remoção")
    s.set_defaults(func=_cmd_remover)

    s = sub.add_parser("validar", parents=[comuns], help="confere a ficha contra o contrato e as regras da casa",
                       description="Erros (código 1): esquema do contrato; \"confirmado\" sem 1 fonte primária ou 2 "
                                   "secundárias de editores e domínios distintos; preco, benchmark ou modelo confirmado "
                                   "sem fonte primária, ou sem caduca_em; confiança alta sem fonte primária; URL que não "
                                   "é https; trecho vazio ou com mais de 25 palavras; data inválida ou futura; "
                                   "acessado_em ausente; \"divergente\" com menos de 2 fontes.\n"
                                   "Avisos (reprovam com --estrito): trecho ausente ou ainda não conferido na página, "
                                   "fato vencido, validade longa demais, como_dizer sem data ou sem atribuição, "
                                   "superlativo sem data, enciclopédia marcada como primária, fato sustentado só por "
                                   "fórum ou blog.")
    s.add_argument("--estrito", action="store_true", help="avisos também reprovam (use antes de publicar)")
    s.add_argument("--json", action="store_true", help="saída em JSON")
    s.set_defaults(func=_cmd_validar)

    s = sub.add_parser("checar-links", parents=[comuns], help="abre cada URL das fontes (GET com prazo) e relata o estado",
                       description="Um GET por URL única, 4 em paralelo, sem derrubar o resto quando uma falha. Estados: "
                                   "ok · redirecionado (3xx; mostra o destino) · bloqueado (o site recusa robôs: "
                                   "401/403/429, 400, 202 vazio, laço de redirecionamento — confira no navegador) · "
                                   "quebrado (404/410) · erro_servidor (5xx) · erro_tls · sem_resposta.\nGrava o "
                                   "resultado em pesquisa/_links.json. Com --trechos, grava também em cada fonte da "
                                   "ficha se o trecho foi encontrado, está ausente ou não pôde ser lido pelo robô.\n"
                                   "Código 1 se houver link quebrado, erro de servidor, sem resposta ou, com --trechos, "
                                   "fato confirmado com trecho ausente ou não verificado; 75 se nenhuma URL respondeu "
                                   "(sem rede).")
    s.add_argument("--id", action="append", metavar="F001", help="só as fontes deste fato (pode repetir)")
    s.add_argument("--arquivo", metavar="ARQ", help="em vez da ficha, confere toda URL encontrada neste arquivo de texto "
                                                    "(roteiro, descrição, references/fontes-primarias.md); não precisa de ficha")
    s.add_argument("--prazo", type=float, default=12.0, metavar="S", help="segundos por URL (padrão: 12)")
    s.add_argument("--trechos", action="store_true",
                   help="baixa o HTML, procura o trecho citado e grava o resultado em cada fonte: é a prova de que o "
                        "fato foi lido e não lembrado (acusa página que mudou, trecho inventado e página montada por "
                        "JavaScript)")
    s.add_argument("--json", action="store_true", help="saída em JSON")
    s.set_defaults(func=_cmd_checar_links)

    s = sub.add_parser("vencidos", parents=[comuns], help="fatos caducados ou a caducar",
                       description="Lista fatos com caduca_em anterior a hoje (código 1) e os que vencem nos próximos N "
                                   "dias (só avisa). Com --hoje <data de publicação> responde \"o que estará vencido "
                                   "quando o vídeo sair?\".")
    s.add_argument("--dias", type=int, default=14, metavar="N", help="janela de \"a vencer\" em dias (padrão: 14)")
    s.add_argument("--json", action="store_true", help="saída em JSON")
    s.set_defaults(func=_cmd_vencidos)

    s = sub.add_parser("md", parents=[comuns], help="gera pesquisa/fatos.md e pesquisa/fontes.md",
                       description="fatos.md: a ficha legível (tabela + um bloco por fato). fontes.md: a lista de fontes "
                                   "pronta para a descrição do vídeo, entre <!-- DESCRICAO:INICIO --> e <!-- DESCRICAO:FIM "
                                   "-->, mais a versão curta para Shorts/Reels/TikTok (<!-- CURTA:… -->).")
    s.add_argument("--roteiro", metavar="ARQUIVO", help="em fontes.md, lista só as fontes dos fatos citados neste roteiro ([F001])")
    s.add_argument("--mesmo-com-erros", action="store_true", help="gera mesmo com a ficha reprovada na validação")
    s.set_defaults(func=_cmd_md)

    s = sub.add_parser("conferir-roteiro", parents=[comuns], help="cruza cada frase do roteiro com a ficha",
                       description="Extrai de cada frase números, percentuais, datas, valores em dinheiro, superlativos e "
                                   "nomes próprios candidatos e cruza com a ficha e com os marcadores [F001].\n"
                                   "Lê dígitos e numerais por extenso; compara por tipo (dinheiro com dinheiro e a moeda, "
                                   "percentual com percentual, data com data, contagem com contagem).\n"
                                   "Pendências (código 1): frase com dado checável sem marcador (mesmo que um fato pareça "
                                   "cobri-la); frase sem marcador com modelo versionado, verbo de lançamento/preço/licença "
                                   "ou tempo relativo junto de um nome; número, data ou modelo da frase que não está no "
                                   "fato citado; entrada × saída, grandeza (tokens × palavras) ou cobrança (\"por "
                                   "mês\") diferentes das do fato; superlativo que o fato citado não sustenta; marcador "
                                   "para id inexistente; fato usado com status ≠ confirmado, vencido ou com trecho "
                                   "ausente.\n"
                                   "Avisos (reprovam com --estrito): frase só com nome próprio; nome que não está no fato "
                                   "citado; número que só aparece no trecho da fonte; número pequeno em frase dirigida ao "
                                   "espectador (\"você…\"); tempo relativo (\"hoje\", \"atualmente\") em fato volátil; "
                                   "fato com trecho ainda não conferido; fato a vencer.\n[sem-fato] ou [opinião] na frase "
                                   "dispensa a checagem (e aparece no relatório). Títulos, linhas de tabela e metadados "
                                   "com dado também são conferidos; número de fala pessoal, chamada ou analogia é "
                                   "ignorado e listado.")
    s.add_argument("roteiro", help="arquivo do roteiro (ex.: roteiro/roteiro.md)")
    s.add_argument("--dias", type=int, default=14, metavar="N", help="janela de \"a vencer\" (padrão: 14)")
    s.add_argument("--estrito", action="store_true", help="avisos também reprovam")
    s.add_argument("--json", action="store_true", help="saída em JSON")
    s.add_argument("--saida", metavar="ARQUIVO", help="grava o relatório JSON neste arquivo (ex.: pesquisa/_conferencia.json)")
    s.set_defaults(func=_cmd_conferir_roteiro)

    s = sub.add_parser("conferir-storyboard", parents=[comuns], help="confere os fato_ids e os créditos do storyboard",
                       description="Para cada cena de roteiro/storyboard.json: os fato_ids existem, estão confirmados, "
                                   "vigentes e sem trecho ausente; os números que vão para a tela (trecho, textos de params "
                                   "e params de dado como dados[].valor) batem por tipo com os fatos citados; cena com "
                                   "número e sem fato_ids (pendências). params.fonte bate com o crédito da ficha (aviso).")
    s.add_argument("storyboard", nargs="?", help="arquivo do storyboard (padrão: <projeto>/roteiro/storyboard.json)")
    s.add_argument("--dias", type=int, default=14, metavar="N", help="janela de \"a vencer\" (padrão: 14)")
    s.add_argument("--estrito", action="store_true", help="avisos também reprovam")
    s.add_argument("--json", action="store_true", help="saída em JSON")
    s.set_defaults(func=_cmd_conferir_storyboard)

    s = sub.add_parser("credito", parents=[comuns], help="texto do crédito de fonte para a tela (\"Fonte: Editor, mês/ano\")",
                       description="Crédito curto da fonte de um fato, no padrão \"Fonte: Editor, mês/ano\" (mês da "
                                   "publicação; se a página não tem data, mês do acesso). Usa a 1ª fonte primária.\n"
                                   "Nas cenas `citacao` e `barras` do motor o parâmetro `fonte` recebe o prefixo da "
                                   "direção de arte (padrão \"Fonte: \"): passe a ele a saída de --sem-prefixo. A "
                                   "aparência vem do token graficos.citacao_fonte da DA, nunca daqui. Só sai de fato "
                                   "confirmado com o trecho conferido na página.")
    s.add_argument("id", help="id do fato (F001)")
    s.add_argument("--fonte", type=int, metavar="N", help="usa a fonte N do fato (1 = a primeira) em vez da 1ª primária")
    s.add_argument("--todas", action="store_true", help="cita todas as fontes do fato, separadas por ponto e vírgula")
    s.add_argument("--data", choices=("mes_ano", "ano"), default="mes_ano", help="formato da data (padrão: mes_ano → out/2026)")
    s.add_argument("--sem-prefixo", action="store_true", help="só \"Editor, mês/ano\" — é o valor de params.fonte das cenas")
    s.add_argument("--caber", metavar="FORMATO", help="mede o crédito com a DA do projeto (horizontal, vertical…) e "
                                                    "acusa se passa da zona segura (código 1)")
    s.add_argument("--forcar", action="store_true", help="mostra o crédito mesmo de fato não confirmado")
    s.add_argument("--json", action="store_true", help="saída em JSON (texto, param_cena, editor, data, medida)")
    s.set_defaults(func=_cmd_credito)

    s = sub.add_parser("resumo", parents=[comuns], help="situação da ficha numa tela",
                       description="Contagem por status, categoria e confiança; validação; vencidos; última checagem de "
                                   "links; uma linha por fato.")
    s.add_argument("--json", action="store_true", help="saída em JSON")
    s.set_defaults(func=_cmd_resumo)
    return p


def main(argv=None) -> int:
    parser = construir_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help(sys.stderr)
        return SAIDA_USO
    try:
        return args.func(args)
    except ErroFatos as e:
        print(f"erro: {e.mensagem}", file=sys.stderr)
        if e.dica:
            print(f"  → {e.dica}", file=sys.stderr)
        return e.codigo
    except BrokenPipeError:
        return SAIDA_OK
    except KeyboardInterrupt:
        print("interrompido", file=sys.stderr)
        return 130
    except Exception as e:  # noqa: BLE001 — sem traceback cru para o usuário
        if os.environ.get("VIDEO_OPS_DEBUG"):
            raise
        try:                                                      # a causa mais comum: ficha editada à mão e quebrada
            caminho = achar_ficha(*_alvo(args))
            rel = validar_ficha(ler_json(caminho), _hoje(args))
        except Exception:  # noqa: BLE001
            rel = None
        if rel and rel["erros"]:
            print(f"erro: a ficha tem {_plural(len(rel['erros']), 'erro', 'erros')} de estrutura e este comando não "
                  f"conseguiu lê-la ({type(e).__name__})", file=sys.stderr)
            print("  → rode `fatos.py validar`, corrija (ou restaure pesquisa/_fatos.anterior.json) e tente de novo",
                  file=sys.stderr)
            return SAIDA_PENDENCIA
        print(f"erro interno ({type(e).__name__}: {e})", file=sys.stderr)
        print("  → isto é defeito do script, não do seu uso: rode de novo com VIDEO_OPS_DEBUG=1 para ver o traceback",
              file=sys.stderr)
        return 70


if __name__ == "__main__":
    sys.exit(main())
