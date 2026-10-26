#!/usr/bin/env python3
"""roteiro.py — do documento de roteiro com comentários de produção à pauta de mídia do projeto.

    roteiro.py ler "Roteiro ep 12.docx"      # .docx (Word ou exportado do Google Docs), .md ou .txt
    roteiro.py listar [--tipo T] [--status S] [--json]
    roteiro.py definir P003 --tipo video_youtube --url https://youtu.be/… --t0 1:10 --t1 1:25 --status aprovado
    roteiro.py exportar                      # roteiro/pauta.md (checklist legível)

Lê os parágrafos, os comentários de margem (trecho ancorado, autor, links) e as marcações no texto
([VÍDEO: …], [IMAGEM: …], [B-ROLL: …], [ANIMAÇÃO: …], [GC: …], [PRINT: …]) e grava roteiro/roteiro.md (narração
limpa) e roteiro/pauta.json. A classificação inicial é por regras: confira com `listar` e corrija com `definir`.
Só biblioteca padrão; o .docx é lido como zip + XML."""
from __future__ import annotations

import contextlib
try:
    import fcntl
except ImportError:                    # Windows: flock da adaptação local (video-direcao-de-arte/kit/_win.py)
    import os as _os, sys as _sys
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "video-direcao-de-arte", "kit"))
    import _win as fcntl
import json
import os
import re
import sys
import unicodedata
import urllib.parse
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import base  # noqa: E402

PAUTA, PAUTA_MD, ROTEIRO_MD = Path("roteiro/pauta.json"), Path("roteiro/pauta.md"), Path("roteiro/roteiro.md")
TIPOS = ("video_youtube", "imagem_web", "print", "banco", "animacao", "gc", "legenda", "musica", "sfx", "corte", "outro")
STATUS = ("pendente", "candidatos", "aprovado", "baixado", "tratado", "descartado")
NOMES = {"video_youtube": "vídeo do YouTube", "imagem_web": "imagem da web", "print": "print de tela", "banco": "b-roll de banco",
         "animacao": "animação", "gc": "GC", "legenda": "legenda", "musica": "música", "sfx": "efeito sonoro", "corte": "corte", "outro": "outro"}
SKILL_DO_TIPO = {"video_youtube": "video-pauta-midia", "imagem_web": "video-pauta-midia", "print": "video-pauta-midia", "banco": "video-broll",
                 "animacao": "video-animacao-explicativa", "gc": "video-motion-graphics", "legenda": "video-legendas", "musica": "video-mixagem",
                 "sfx": "video-efeitos-sonoros", "corte": "video-montagem", "outro": None}
ETIQUETAS = {"VIDEO": "video_youtube", "YOUTUBE": "video_youtube", "IMAGEM": "imagem_web", "FOTO": "imagem_web", "BROLL": "banco",
             "ANIMACAO": "animacao", "GC": "gc", "PRINT": "print", "MUSICA": "musica", "TRILHA": "musica", "SFX": "sfx",
             "LEGENDA": "legenda", "CORTE": "corte"}
REGRAS = (                                                    # a ordem é a prioridade; texto já sem acento e em minúsculas
    ("print", r"\bprints?\b|captura de tela|screenshot|\bprintar\b|\bmanchete\b|\btuite\b|\btweet\b"),
    ("sfx", r"\bsfx\b|efeitos? sonoros?|\bwhoosh\b|\bsom de \w+"),
    ("musica", r"\bmusica\b|\btrilha\b|\bbg\b"),
    ("legenda", r"\blegendas?\b|\blegendar\b|\bkaraoke\b"),
    ("gc", r"\bgc\b|lower third|\btarja\b|nome na tela|credito na tela|\bletreiro\b"),
    ("animacao", r"\banimac\w+|\banimar\b|\bgraficos?\b|\binfografico\b|\bdiagrama\b|\besquema\b|\bmotion\b"),
    ("banco", r"\bb-?roll\b|banco de (?:imagens?|videos?)|imagens? de (?:cobertura|apoio)|\bstock\b|\bfootage\b|\bcobertura\b"),
    ("video_youtube", r"\byoutube\b|\bvideos?\b|\bentrevista\b|\bclipe\b|\breportagem\b|\btrailer\b|\bpodcast\b"),
    ("imagem_web", r"\bfotos?\b|\bimagem\b|\bimagens\b|\blogo\b|\bretrato\b|\bcapa d[oae]\b|\bmapa\b"),
    ("corte", r"\bcortar\b|\bcorta (?:isso|esse|essa|aqui)\b|\bremover\b|\btirar\b|\bencurtar\b|\bcortes?\b"),
)
RE_URL = re.compile(r"https?://[^\s<>\"'\]\)]+")
RE_MARCA = re.compile(r"\[\s*([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\- ]{1,11}?)\s*:\s*([^\[\]]+?)\s*\]")
RE_PREFIXO = re.compile(r"^\[?\s*([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\- ]{1,11}?)\s*:\s*")
RE_TEMPO = re.compile(r"(?<![\d:])(?:(\d{1,2}):)?(\d{1,2}):(\d{2})(?![\d:])")
RE_YOUTUBE = re.compile(r"(?:^|[/.])(?:youtube\.com|youtu\.be)$")
RE_COMANDO = re.compile(r"^(?:(?:colocar|coloca|inserir|insere|buscar|busca|procurar|procura|achar|acha|usar|usa|por|mostrar|mostra|baixar|baixa|"
                        r"pegar|pega|aqui|um|uma|o|a|os|as|de|do|da|no|na|trechos?|videos?|imagem|imagens|fotos?|b-?roll|footage|stock|cobertura|apoio)\s+)+")
RE_INTERVALO = re.compile(r"(?i)\b(?:(?:de|do|entre|em|a partir de)\s+)?\d{1,2}:\d{2}(?::\d{2})?(?:\s*(?:a|à|às|até|ate|e|-|–|—)\s*\d{1,2}:\d{2}(?::\d{2})?)?")
RE_DURACAO = re.compile(r"(?i)\b(?:(?:uns|umas|cerca de|por|durante|só|so|apenas)\s+)?\d{1,3}(?:[.,]\d+)?\s*(?:segundos?|segs?|s|minutos?|min)\b")
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
W14 = "{http://schemas.microsoft.com/office/word/2010/wordml}"
W15 = "{http://schemas.microsoft.com/office/word/2012/wordml}"
REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"
TETO_XML = 60_000_000


def sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _arruma(t: str) -> str:
    linhas = (re.sub(r"[ \t ]+", " ", x).strip() for x in t.replace("\r", "\n").split("\n"))
    return re.sub(r"\s+([.,;:!?])", r"\1", "\n".join(x for x in linhas if x))


def _etq(t: str) -> str:
    return re.sub(r"[^A-Z]", "", sem_acento(t).upper())


def _frase(texto: str, primeira: bool, teto: int = 280) -> str:
    frases = [f for f in re.split(r"(?<=[.!?…])\s+", texto.strip()) if f.strip()]
    f = (frases[0] if primeira else frases[-1]) if frases else ""
    return f if len(f) <= teto else f[:teto - 1].rstrip() + "…"


# ─────────────────────────────────────────────────────────── classificação por regras ──
def host_youtube(url: str | None) -> bool:
    return bool(url) and bool(RE_YOUTUBE.search(urllib.parse.urlsplit(url).hostname or ""))


def classificar(pedido: str, url: str | None = None, etiqueta: str | None = None) -> str:
    if etiqueta in TIPOS:
        return etiqueta
    t = sem_acento(RE_URL.sub(" ", pedido)).lower()
    if re.search(REGRAS[0][1], t):
        return "print"
    if url:
        p = urllib.parse.urlsplit(url)
        if host_youtube(url):
            return "video_youtube"
        if re.search(r"\.(?:jpe?g|png|webp|gif|svg)$", p.path, re.I) or (p.hostname or "").endswith("wikimedia.org"):
            return "imagem_web"
    for tipo, padrao in REGRAS[1:]:
        if re.search(padrao, t):
            return tipo
    return "outro"


def skill_do(tipo: str, pedido: str = "") -> str | None:
    if tipo == "corte" and re.search(r"vertical|reels?|shorts?|tiktok", sem_acento(pedido).lower()):
        return "video-cortes-verticais"
    return SKILL_DO_TIPO[tipo]


def tempos(pedido: str, url: str | None = None) -> tuple[float | None, float | None]:
    achados = [int(h or 0) * 3600 + int(m) * 60 + int(s) for h, m, s in RE_TEMPO.findall(RE_URL.sub(" ", pedido))]
    t0 = float(achados[0]) if achados else None
    t1 = float(achados[1]) if len(achados) > 1 and achados[1] > achados[0] else None
    if t0 is None and url:
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
        bruto = (q.get("t") or q.get("start") or [None])[0]
        with contextlib.suppress(base.Erro):
            t0 = base.segundos(bruto)
    return t0, t1


def consulta_inicial(pedido: str, tipo: str, url: str | None) -> list[str]:
    if url or tipo not in ("video_youtube", "imagem_web", "banco"):
        return []
    t = RE_DURACAO.sub(" ", RE_INTERVALO.sub(" ", RE_URL.sub(" ", pedido)))      # «de 0:30 a 0:36» e «uns 6 segundos» não são assunto
    t = re.sub(r"(?i)\b(?:d?o|n?o) (?:youtube|google imagens|google)\b", " ", t)
    t = re.sub(r"[\"«»“”()\[\]:;,]", " ", t)
    palavras = [p for p in t.split() if p.strip(" .,;:-–—")]
    while palavras and RE_COMANDO.match(sem_acento(palavras[0]).lower() + " "):
        palavras.pop(0)
    while palavras and sem_acento(palavras[-1]).lower().strip(" .") in ("de", "do", "da", "a", "e", "ate", "uns", "com", "por", "em"):
        palavras.pop()
    return [" ".join(palavras[:10]).strip(" .,;:-–—")] if len(palavras) >= 2 else []


# ───────────────────────────────────────────────────────────────────── leitura do .docx ──
def _xml(z: zipfile.ZipFile, nome: str) -> ET.Element:
    if z.getinfo(nome).file_size > TETO_XML:
        raise base.Erro(f"{nome} dentro do .docx é grande demais para ser um roteiro.", "Exporte o documento de novo, sem anexos.")
    dados = z.read(nome)
    if b"<!DOCTYPE" in dados[:4096] or b"<!ENTITY" in dados[:4096]:
        raise base.Erro(f"{nome} traz uma declaração que um .docx de verdade não tem.", "Abra o arquivo no Word ou no Google Docs e salve de novo.")
    return ET.fromstring(dados)


def _rels(z: zipfile.ZipFile, nome: str) -> dict:
    if nome not in z.namelist():
        return {}
    return {r.get("Id"): r.get("Target") for r in _xml(z, nome).iter(REL + "Relationship")
            if (r.get("TargetMode") or "").lower() == "external" and (r.get("Target") or "").lower().startswith("http")}


def _nivel(p: ET.Element) -> int:
    estilo = p.find(f"{W}pPr/{W}pStyle")
    m = re.fullmatch(r"(?:heading|ttulo|titulo|title)\s*(\d)?", sem_acento((estilo.get(W + "val") or "") if estilo is not None else "").lower())
    return 0 if not m else int(m.group(1) or 1)


def _comentarios(z: zipfile.ZipFile) -> dict:
    nomes, saida = z.namelist(), {}
    if "word/comments.xml" not in nomes:
        return saida
    rels = _rels(z, "word/_rels/comments.xml.rels")
    for c in _xml(z, "word/comments.xml").iter(W + "comment"):
        pars, links, para_id = [], [], None
        for p in c.iter(W + "p"):
            pedacos = []
            for e in p.iter():
                if e.tag == W + "t":
                    pedacos.append(e.text or "")
                elif e.tag in (W + "br", W + "cr"):
                    pedacos.append("\n")
                elif e.tag == W + "tab":
                    pedacos.append(" ")
                elif e.tag == W + "hyperlink" and rels.get(e.get(R + "id") or ""):
                    links.append(rels[e.get(R + "id")])
                elif e.tag == W + "instrText" and (m := re.search(r'HYPERLINK\s+"([^"]+)"', e.text or "")):
                    links.append(m.group(1))
            if t := _arruma("".join(pedacos)):
                pars.append(t)
            para_id = p.get(W14 + "paraId") or para_id
        saida[c.get(W + "id")] = {"texto": "\n".join(pars), "autor": (c.get(W + "author") or "").strip() or None, "links": links, "para_id": para_id}
    if "word/commentsExtended.xml" in nomes:                  # fios e «resolvido» do Word
        por_para = {v["para_id"]: k for k, v in saida.items() if v["para_id"]}
        for e in _xml(z, "word/commentsExtended.xml").iter(W15 + "commentEx"):
            cid, pai = por_para.get(e.get(W15 + "paraId")), por_para.get(e.get(W15 + "paraIdParent") or "")
            if cid is None:
                continue
            if pai is not None and pai != cid:
                saida[cid]["pai"] = pai
            if e.get(W15 + "done") in ("1", "true"):
                saida[cid]["resolvido"] = True
    return saida


def ler_docx(caminho: Path) -> tuple[list[dict], list[dict]]:
    """(blocos [{texto, nivel}], comentários [{trecho, bloco, pedido, autor, links, respostas, resolvido}]) em ordem de documento."""
    dica = "No Word: Salvar como → .docx. No Google Docs: Arquivo → Baixar → Microsoft Word (.docx). Arquivos .doc antigo, .pages e .odt não são lidos."
    try:
        z = zipfile.ZipFile(caminho)
    except (zipfile.BadZipFile, OSError):
        raise base.Erro(f"{caminho.name} não é um .docx legível.", dica)
    with z:
        if "word/document.xml" not in z.namelist():
            raise base.Erro(f"{caminho.name} é um zip, mas não tem word/document.xml.", dica)
        try:
            doc, rels, com = _xml(z, "word/document.xml"), _rels(z, "word/_rels/document.xml.rels"), _comentarios(z)
        except ET.ParseError as e:
            raise base.Erro(f"o XML de {caminho.name} está corrompido ({e}).", dica)
    blocos, seq_bloco, abertos, ancoras, ordem = [], {}, {}, {}, []
    est = {"seq": 0, "buf": [], "pontuais": []}

    def texto(s: str) -> None:
        est["buf"].append(s)
        for a in abertos.values():
            if s.strip() and a["seq"] is None:
                a["seq"] = est["seq"]
            a["txt"].append(s)

    def anda(el: ET.Element) -> None:
        tag = el.tag
        if tag in (W + "del", W + "moveFrom"):                # sugestão de exclusão: não é texto do roteiro
            return
        if tag == W + "p":
            salvo = (est["buf"], est["pontuais"])
            est["seq"] += 1
            minha = est["seq"]
            est["buf"], est["pontuais"] = [], []
            for f in el:
                anda(f)
            t = _arruma("".join(est["buf"]))
            if t:
                blocos.append({"texto": t, "nivel": _nivel(el)})
                seq_bloco[minha] = len(blocos) - 1
            for cid in est["pontuais"]:
                ancoras[cid]["txt"].append(t)
            for a in abertos.values():
                a["txt"].append(" ")
            est["buf"], est["pontuais"] = salvo
            return
        cid = el.get(W + "id")
        if tag == W + "commentRangeStart":
            abertos[cid] = {"seq": None, "seq0": est["seq"], "txt": [], "links": []}
            ordem.append(cid)
        elif tag == W + "commentRangeEnd":
            if cid in abertos:
                ancoras[cid] = abertos.pop(cid)
        elif tag == W + "commentReference":
            if cid not in abertos and cid not in ancoras:     # comentário sem intervalo: vale o parágrafo inteiro
                ancoras[cid] = {"seq": est["seq"], "txt": [], "links": []}
                ordem.append(cid)
                est["pontuais"].append(cid)
        elif tag == W + "t":
            texto(el.text or "")
        elif tag == W + "tab":
            texto(" ")
        elif tag in (W + "br", W + "cr"):
            texto("\n")
        elif tag == W + "noBreakHyphen":
            texto("-")
        elif tag == W + "instrText":
            if m := re.search(r'HYPERLINK\s+"([^"]+)"', el.text or ""):
                for a in abertos.values():
                    a["links"].append(m.group(1))
        else:
            if tag == W + "hyperlink" and rels.get(el.get(R + "id") or ""):
                for a in abertos.values():
                    a["links"].append(rels[el.get(R + "id")])
            for f in el:
                anda(f)

    anda(doc)
    ancoras.update(abertos)                                   # intervalo aberto e nunca fechado: vale até o fim
    seqs = sorted(seq_bloco)

    def bloco_de(seq) -> int | None:
        if seq is None or not seqs:
            return None
        return seq_bloco[next((s for s in seqs if s >= seq), seqs[-1])]

    comentarios = []
    for cid in ordem:
        c = com.get(cid)
        if not c or c.get("pai") or not c["texto"]:
            continue
        a = ancoras[cid]
        bloco = bloco_de(a["seq"] or a.get("seq0"))
        ancorado = _arruma("".join(a["txt"])) or (blocos[bloco]["texto"] if bloco is not None else "")
        comentarios.append({"trecho": ancorado, "bloco": bloco, "pedido": c["texto"], "autor": c["autor"],
                            "links": c["links"] + a["links"], "resolvido": bool(c.get("resolvido")),
                            "respostas": [(r["autor"], r["texto"]) for r in com.values() if r.get("pai") == cid and r["texto"]]})
    return blocos, comentarios


def ler_texto(caminho: Path) -> tuple[list[dict], list[dict]]:
    bruto = caminho.read_bytes()
    try:
        t = bruto.decode("utf-8-sig")
    except UnicodeDecodeError:
        t = bruto.decode("latin-1")
    blocos = []
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    if caminho.suffix.lower() != ".txt":                      # título de markdown é sempre um bloco só dele
        t = re.sub(r"(?m)^(#{1,6}[ \t]+.*)$", r"\n\1\n", t)
    for par in re.split(r"\n\s*\n", t):
        par = _arruma(par)
        if not par:
            continue
        m = re.match(r"(#{1,6})\s+(.*)", par, re.S) if caminho.suffix.lower() != ".txt" else None
        blocos.append({"texto": m.group(2) if m else par, "nivel": len(m.group(1)) if m else 0})
    return blocos, []


# ────────────────────────────────────────────────────────────────── montagem da pauta ──
def montar(blocos: list[dict], comentarios: list[dict]) -> tuple[list[dict], list[dict]]:
    """(blocos de narração limpa, itens da pauta sem id) a partir do que foi lido."""
    limpos, mapa, brutos, orfaos = [], {}, [], []
    for i, b in enumerate(blocos):
        marcas: list[tuple[str, str]] = []

        def troca(m: re.Match) -> str:
            tipo = ETIQUETAS.get(_etq(m.group(1)))
            if not tipo:
                return m.group(0)
            marcas.append((tipo, _arruma(m.group(2)).replace("\n", " ")))
            return "\x00"

        partes = RE_MARCA.sub(troca, b["texto"]).split("\x00")
        limpo = _arruma(" ".join(partes))
        if limpo:
            limpos.append({"texto": limpo, "nivel": b["nivel"]})
            mapa[i] = len(limpos)
            for o in orfaos:
                o["paragrafo"], o["trecho"] = len(limpos), _frase(limpo, primeira=True)
            orfaos = []
        for k, (tipo, pedido) in enumerate(marcas):
            antes = _arruma(partes[k]) or _arruma(" ".join(partes[:k]))
            it = {"pedido": pedido, "autor": None, "etiqueta": tipo, "links": [], "ordem": (i, k), "notas": []}
            if antes:
                it["trecho"], it["paragrafo"] = _frase(antes, primeira=False), mapa[i]
            elif limpo:
                it["trecho"], it["paragrafo"] = _frase(limpo, primeira=True), mapa[i]
            elif limpos:
                it["trecho"], it["paragrafo"] = _frase(limpos[-1]["texto"], primeira=False), len(limpos)
            else:
                it["trecho"], it["paragrafo"] = "", 0
                orfaos.append(it)
            brutos.append(it)
    for n, c in enumerate(comentarios):
        i = c["bloco"]
        par = 0 if i is None else next((mapa[j] for j in range(i, len(blocos)) if j in mapa), len(limpos))
        trecho = _arruma(RE_MARCA.sub(lambda m: "" if ETIQUETAS.get(_etq(m.group(1))) else m.group(0), c["trecho"])).replace("\n", " ")
        pedido, etiqueta = c["pedido"], None
        if (m := RE_PREFIXO.match(pedido)) and ETIQUETAS.get(_etq(m.group(1))):
            etiqueta, pedido = ETIQUETAS[_etq(m.group(1))], pedido[m.end():].rstrip(" ]") or pedido
        notas = [f"resposta de {a or 'alguém'}: {t}" for a, t in c["respostas"]]
        if c["resolvido"]:
            notas.append("comentário marcado como resolvido no documento")
        brutos.append({"pedido": pedido, "autor": c["autor"], "etiqueta": etiqueta, "links": c["links"], "notas": notas,
                       "trecho": trecho if len(trecho) <= 400 else trecho[:399].rstrip() + "…", "paragrafo": par,
                       "ordem": (i if i is not None else len(blocos), 1000 + n)})
    itens = []
    for b in sorted(brutos, key=lambda x: x["ordem"]):
        links = list(dict.fromkeys(u.rstrip(".,;") for u in [*b["links"], *RE_URL.findall(b["pedido"])]))
        url = links[0] if links else None
        tipo = classificar(b["pedido"], url, b["etiqueta"])
        t0, t1 = tempos(b["pedido"], url)
        notas = b["notas"] + ([f"outros links: {' '.join(links[1:])}"] if len(links) > 1 else [])
        itens.append({"id": None, "trecho": b["trecho"], "paragrafo": b["paragrafo"], "pedido": b["pedido"], "autor": b["autor"], "tipo": tipo,
                      "skill": skill_do(tipo, b["pedido"]), "url": url, "consultas": consulta_inicial(b["pedido"], tipo, url),
                      "t0": t0, "t1": t1, "status": "pendente", "midia_ids": [], "notas": " · ".join(notas)})
    return limpos, itens


# ─────────────────────────────────────────────────────────────── pauta.json no disco ──
@contextlib.contextmanager
def _travada(projeto: Path):
    (projeto / "roteiro").mkdir(parents=True, exist_ok=True)
    with open(projeto / "roteiro" / "_pauta.lock", "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        yield


def _gravar(arq: Path, texto: str) -> None:
    arq.parent.mkdir(parents=True, exist_ok=True)
    tmp = arq.with_name(f"_{arq.name}.{os.getpid()}.tmp")
    tmp.write_text(texto, encoding="utf-8")
    os.replace(tmp, arq)


def carregar(projeto: Path) -> dict:
    arq = projeto / PAUTA
    if not arq.is_file():
        raise base.Erro(f"não há pauta em {arq}.", "Rode primeiro: roteiro.py ler \"<documento do roteiro>\".")
    try:
        return json.loads(arq.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise base.Erro(f"{arq} não é um JSON válido ({e}).", "Corrija o arquivo ou rode roteiro.py ler de novo.")


def _salvar(projeto: Path, pauta: dict) -> None:
    _gravar(projeto / PAUTA, json.dumps(pauta, ensure_ascii=False, indent=2) + "\n")


def _achar(pauta: dict, pid: str) -> dict:
    for it in pauta["itens"]:
        if it["id"] == pid.upper():
            return it
    raise base.Erro(f"a pauta não tem o item {pid}.", "Veja os ids com: roteiro.py listar.")


def alterar(projeto: Path, pid: str, midia: str | None = None, consulta: str | None = None, **campos) -> dict:
    """Troca campos de um item sob trava (usado também por youtube.py e imagens.py). Devolve o item gravado."""
    with _travada(projeto):
        pauta = carregar(projeto)
        it = _achar(pauta, pid)
        if campos.get("tipo") and campos["tipo"] != it["tipo"] and "skill" not in campos:
            campos["skill"] = skill_do(campos["tipo"], it["pedido"])
        it.update({k: v for k, v in campos.items() if v is not None})
        if midia and midia not in it["midia_ids"]:
            it["midia_ids"].append(midia)
        if consulta and consulta not in it["consultas"]:
            it["consultas"].append(consulta)
        if it["tipo"] not in TIPOS or it["status"] not in STATUS:
            raise base.Erro(f"tipo ou status inválido em {pid}.", f"tipos: {', '.join(TIPOS)} · status: {', '.join(STATUS)}", base.USO)
        if it["t0"] is not None and it["t1"] is not None and it["t1"] <= it["t0"]:
            raise base.Erro(f"{pid}: t1 ({base.relogio(it['t1'])}) precisa ser maior que t0 ({base.relogio(it['t0'])}).", codigo=base.USO)
        if it["url"] and not re.match(r"https?://\S+$", it["url"]):
            raise base.Erro(f"{pid}: url precisa ser um endereço http(s).", codigo=base.USO)
        _salvar(projeto, pauta)
    return it


def _chave(it: dict) -> tuple:
    return (" ".join(sem_acento(it["pedido"]).lower().split()), " ".join(sem_acento(it["trecho"]).lower().split()))


def cmd_ler(a) -> int:
    origem = Path(a.arquivo).expanduser()
    if not origem.is_file():
        raise base.Erro(f"arquivo não encontrado: {origem}", codigo=base.USO)
    projeto = base.achar_projeto(a.projeto)
    ext = origem.suffix.lower()
    if ext == ".docx":
        blocos, comentarios = ler_docx(origem)
    elif ext in (".md", ".txt", ".markdown"):
        blocos, comentarios = ler_texto(origem)
    else:
        raise base.Erro(f"formato não lido: {ext or 'sem extensão'}.", "Use .docx (Word ou exportado do Google Docs), .md ou .txt.", base.USO)
    limpos, itens = montar(blocos, comentarios)
    if not limpos:
        raise base.Erro(f"{origem.name} não tem texto de roteiro.", "Confira se é o documento certo (texto em caixa de imagem não é lido).")
    destino = projeto / ROTEIRO_MD
    if destino.is_file() and origem.resolve() == destino.resolve():      # a fonte é o próprio roteiro.md: guarda o original com as marcações
        guardado = destino.with_name("roteiro.original.md")
        _gravar(guardado, destino.read_text(encoding="utf-8"))
        origem = guardado
    with _travada(projeto):
        antigos, mantidos = {}, []
        if (projeto / PAUTA).is_file():
            velha = carregar(projeto)
            antigos = {_chave(it): it for it in velha["itens"]}
            usados = [int(it["id"][1:]) for it in velha["itens"]]
        else:
            usados = []
        proximo = max(usados, default=0) + 1
        novos = 0
        for it in itens:
            velho = antigos.pop(_chave(it), None)
            if velho:                                         # o mesmo pedido no mesmo trecho: o que já foi decidido fica
                it.update({k: velho[k] for k in ("id", "tipo", "skill", "url", "consultas", "t0", "t1", "status", "midia_ids", "notas")})
            else:
                it["id"], proximo, novos = f"P{proximo:03d}", proximo + 1, novos + 1
        for velho in antigos.values():                        # saiu do documento: só fica o que já teve trabalho
            if velho["status"] != "pendente" or velho["midia_ids"]:
                if "não está mais no documento" not in velho["notas"]:
                    velho["notas"] = " · ".join(x for x in (velho["notas"], "não está mais no documento do roteiro") if x)
                mantidos.append(velho)
        try:
            origem_txt = origem.resolve().relative_to(projeto).as_posix()
        except ValueError:
            origem_txt = origem.name
        pauta = {"versao": 1, "origem": origem_txt, "itens": itens + mantidos}
        _gravar(destino, "\n\n".join(("#" * b["nivel"] + " " if b["nivel"] else "") + b["texto"] for b in limpos) + "\n")
        _salvar(projeto, pauta)
    palavras = sum(len(b["texto"].split()) for b in limpos if not b["nivel"])
    base.diz(f"roteiro: {len(limpos)} parágrafo(s), {palavras} palavra(s) de narração → {destino}")
    base.diz(f"pauta:   {len(pauta['itens'])} item(ns) ({novos} novo(s), {len(mantidos)} mantido(s) fora do documento) → {projeto / PAUTA}")
    por_tipo: dict[str, int] = {}
    for it in pauta["itens"]:
        por_tipo[it["tipo"]] = por_tipo.get(it["tipo"], 0) + 1
    base.diz("         " + " · ".join(f"{NOMES[t]}: {n}" for t, n in por_tipo.items()) if por_tipo else "         nenhum comentário ou marcação encontrado")
    base.diz("A classificação é por regras: confira com «roteiro.py listar» e corrija com «roteiro.py definir <id> --tipo …».")
    return base.OK


def _linha(it: dict) -> str:
    tempo = f" [{base.relogio(it['t0'])}–{base.relogio(it['t1'])}]" if it["t0"] is not None else ""
    pedido = it["pedido"].replace("\n", " ")
    pedido = pedido if len(pedido) <= 70 else pedido[:69] + "…"
    extra = "".join((f" → {it['url']}" if it["url"] else "", tempo, f" · mídia: {', '.join(it['midia_ids'])}" if it["midia_ids"] else ""))
    return f"{it['id']}  {it['tipo']:<13}  {it['status']:<10}  par. {it['paragrafo']:<3} {it['skill'] or '—':<26}  {pedido}{extra}"


def cmd_listar(a) -> int:
    pauta = carregar(base.achar_projeto(a.projeto))
    itens = [it for it in pauta["itens"] if (not a.tipo or it["tipo"] == a.tipo) and (not a.status or it["status"] == a.status)]
    if a.json:
        base.diz(json.dumps({**pauta, "itens": itens}, ensure_ascii=False, indent=2))
        return base.OK
    for it in itens:
        base.diz(_linha(it))
    base.diz(f"{len(itens)} de {len(pauta['itens'])} item(ns) · origem: {pauta.get('origem')}")
    return base.OK


def cmd_definir(a) -> int:
    projeto = base.achar_projeto(a.projeto)
    campos = {"tipo": a.tipo, "skill": a.skill, "status": a.status, "url": a.url, "t0": base.segundos(a.t0), "t1": base.segundos(a.t1), "notas": a.notas}
    campos = {k: v for k, v in campos.items() if v is not None}
    if a.limpar_consultas:
        campos["consultas"] = []
    if not campos and not a.consulta and not a.midia:
        raise base.Erro("nada a definir.", "Informe ao menos uma opção (--tipo, --status, --url, --t0, --t1, --consulta, --midia, --notas).", base.USO)
    it = alterar(projeto, a.id, **campos)
    for c in a.consulta or []:
        it = alterar(projeto, a.id, consulta=c)
    for m in a.midia or []:
        it = alterar(projeto, a.id, midia=m)
    base.diz(_linha(it))
    return base.OK


def texto_md(pauta: dict) -> str:
    itens = pauta["itens"]
    contagem = " · ".join(f"{s}: {n}" for s in STATUS if (n := sum(1 for it in itens if it["status"] == s)))
    linhas = ["# Pauta de mídia", "", f"Origem: `{pauta.get('origem')}` · {len(itens)} item(ns) · {contagem or 'vazia'}", "",
              "Gerado por `roteiro.py exportar` a partir de `roteiro/pauta.json` — edite a pauta pelo `roteiro.py definir`, não aqui.", ""]
    for skill in dict.fromkeys(it["skill"] or "a decidir" for it in itens):
        linhas += [f"## {skill}", ""]
        for it in (x for x in itens if (x["skill"] or "a decidir") == skill):
            feito = "x" if it["status"] in ("baixado", "tratado") else " "
            pedido = it["pedido"].replace("\n", " ")
            titulo = f"**{it['id']}** · {NOMES[it['tipo']]} · par. {it['paragrafo']} · {it['status']} — {pedido}"
            linhas.append(f"- [{feito}] " + (f"~~{titulo}~~" if it["status"] == "descartado" else titulo))
            if it["trecho"]:
                linhas.append(f"  - trecho: «{it['trecho']}»")
            if it["autor"]:
                linhas.append(f"  - comentário de {it['autor']}")
            if it["url"]:
                linhas.append(f"  - link: {it['url']}" + (f" ({base.relogio(it['t0'])}–{base.relogio(it['t1'])})" if it["t0"] is not None else ""))
            elif it["t0"] is not None:
                linhas.append(f"  - tempo: {base.relogio(it['t0'])}–{base.relogio(it['t1'])}")
            if it["consultas"]:
                linhas.append("  - consultas: " + " | ".join(it["consultas"]))
            if it["midia_ids"]:
                linhas.append("  - mídia no registro: " + ", ".join(it["midia_ids"]))
            if it["notas"]:
                linhas.append(f"  - notas: {it['notas']}")
        linhas.append("")
    return "\n".join(linhas)


def cmd_exportar(a) -> int:
    projeto = base.achar_projeto(a.projeto)
    _gravar(projeto / PAUTA_MD, texto_md(carregar(projeto)))
    base.diz(f"checklist gravado em {projeto / PAUTA_MD}")
    return base.OK


def main(argv=None) -> int:
    ap = base.Parser(prog="roteiro.py", description="Documento de roteiro com comentários de produção → narração limpa e pauta de mídia.")
    sub = ap.add_subparsers(dest="cmd", required=True, parser_class=base.Parser)
    p = sub.add_parser("ler", help="lê .docx/.md/.txt e grava roteiro/roteiro.md e roteiro/pauta.json")
    p.add_argument("arquivo")
    p.set_defaults(f=cmd_ler)
    p = sub.add_parser("listar", help="mostra a pauta")
    p.add_argument("--tipo", choices=TIPOS)
    p.add_argument("--status", choices=STATUS)
    p.add_argument("--json", action="store_true")
    p.set_defaults(f=cmd_listar)
    p = sub.add_parser("definir", help="corrige ou completa um item")
    p.add_argument("id")
    p.add_argument("--tipo", choices=TIPOS)
    p.add_argument("--skill", help="skill que atende (padrão: a do tipo)")
    p.add_argument("--status", choices=STATUS)
    p.add_argument("--url")
    p.add_argument("--t0", help="início do trecho na fonte (segundos, mm:ss ou hh:mm:ss)")
    p.add_argument("--t1", help="fim do trecho na fonte")
    p.add_argument("--consulta", action="append", help="acrescenta uma consulta de busca (pode repetir)")
    p.add_argument("--limpar-consultas", action="store_true")
    p.add_argument("--midia", action="append", help="acrescenta um id do registro (Y001, W002…)")
    p.add_argument("--notas")
    p.set_defaults(f=cmd_definir)
    p = sub.add_parser("exportar", help="grava roteiro/pauta.md (checklist legível)")
    p.set_defaults(f=cmd_exportar)
    for s in sub.choices.values():
        s.add_argument("--projeto", metavar="PASTA", help="raiz do projeto (padrão: acha pela pasta atual)")
    a = ap.parse_args(argv)
    return a.f(a)


if __name__ == "__main__":
    sys.exit(base.rodar(main))
