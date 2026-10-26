#!/usr/bin/env python3
"""provedores.py — fontes de b-roll gratuito com uma interface só.

Cada provedor implementa `buscar(consulta, tipo, orientacao, quantos, idioma)` → lista de candidatos normalizados e
`detalhar(candidato)` → o mesmo candidato com `arquivos` (as versões que dá para baixar). Endpoints, limites e regras
de uso foram conferidos na documentação oficial em 2026-10-07 (references/fontes.md). Pexels e Pixabay pedem chave do
usuário; NASA, Wikimedia Commons, Internet Archive e Openverse não.

Candidato normalizado (dict):
  fonte, tipo ("video" | "imagem"), id_fonte, titulo, descricao, pagina_url, miniatura_url, largura, altura, duracao,
  autor, autor_url, licenca, licenca_id, licenca_url, exige_atribuicao, uso_comercial, permitida, motivo, risco,
  avisos [..], detalhado (bool), arquivos [{url, rotulo, largura, altura, bytes, formato, duracao}]
"""
from __future__ import annotations

import html
import re
import urllib.parse

import comum
import registro

_TAG = re.compile(r"<[^>]+>")
EXT_VIDEO = ("mp4", "webm", "mov", "m4v", "ogv", "mpeg", "mpg", "avi", "mkv")
EXT_IMAGEM = ("jpg", "jpeg", "png", "tif", "tiff", "webp")


def _texto(v, maximo: int = 300) -> str:
    """Campo de API → texto corrido: sem HTML, sem quebras, sem caractere de controle (ESC, inversor de direção), cortado."""
    if isinstance(v, (list, tuple)):
        v = "; ".join(str(x) for x in v if x)
    s = comum.sem_controle(html.unescape(_TAG.sub(" ", str(v or ""))))
    return s if len(s) <= maximo else s[:maximo - 1].rstrip() + "…"


def _ext(url: str) -> str:
    return urllib.parse.urlsplit(url).path.rsplit(".", 1)[-1].lower() if "." in urllib.parse.urlsplit(url).path.rsplit("/", 1)[-1] else ""


def ext_segura(valor, tipo: str | None = None) -> str:
    """Extensão de arquivo confiável ("mp4", "jpg") ou "" quando o valor não é uma. O valor pode ter vindo de uma API
    (o `filetype` do Openverse, o nome de um arquivo do Internet Archive): só o que passa por aqui vira nome de arquivo."""
    e = str(valor or "").strip().lower().lstrip(".")
    if not re.fullmatch(r"[a-z0-9]{1,5}", e):
        return ""
    aceitas = EXT_VIDEO if tipo == "video" else EXT_IMAGEM if tipo == "imagem" else EXT_VIDEO + EXT_IMAGEM
    return e if e in aceitas else ""


def sanear(c: dict) -> dict:
    """Passa o candidato pelo crivo antes de ele ir para o disco ou para o plano: `formato` de cada arquivo vira uma
    extensão conhecida do tipo do candidato (ou "", e a extensão sai do conteúdo depois de baixado)."""
    for a in c.get("arquivos") or []:
        a["formato"] = ext_segura(a.get("formato"), c.get("tipo")) or ext_segura(_ext(str(a.get("url") or "")), c.get("tipo"))
    return c


def _int(v):
    try:
        n = int(float(v))
        return n if n > 0 else None
    except (TypeError, ValueError):
        return None


def orientacao_de(largura, altura) -> str | None:
    if not largura or not altura:
        return None
    r = largura / altura
    return "horizontal" if r > 1.15 else "vertical" if r < 0.87 else "quadrado"


def candidato(fonte: str, tipo: str, id_fonte, titulo, pagina_url, licenca=None, licenca_url=None, **extra) -> dict:
    """Monta o candidato normalizado e aplica a política de licenças do registro."""
    ficha = registro.avaliar_licenca(licenca, licenca_url, fonte)
    c = {"fonte": fonte, "tipo": tipo, "id_fonte": str(id_fonte), "titulo": _texto(titulo, 120), "descricao": "", "pagina_url": pagina_url,
         "miniatura_url": None, "largura": None, "altura": None, "duracao": None, "autor": None, "autor_url": None,
         "licenca": ficha["nome"] if ficha["id"] != "desconhecida" or not licenca else _texto(licenca, 60), "licenca_id": ficha["id"],
         "licenca_url": ficha.get("url") or licenca_url, "exige_atribuicao": ficha["exige_atribuicao"], "uso_comercial": ficha["uso_comercial"],
         "permitida": ficha["permitida"], "motivo": ficha["motivo"], "risco": ficha["risco"], "avisos": [], "detalhado": False, "arquivos": []}
    c.update(extra)
    c["autor"] = _texto(c.get("autor"), 80) or None
    c["descricao"] = _texto(c.get("descricao"), 300)
    return c


def licenca_declarada(c: dict, aviso: str) -> dict:
    """Marca o candidato de um acervo que NÃO confere a licença (ela é a que quem subiu o item declarou): nasce com risco
    médio e sinal «confira a origem» na folha, no plano e no registro. Quem rebaixa é o usuário, depois de abrir a página
    de origem (baixar.py --risco baixo)."""
    c["avisos"].append(aviso)
    c["conferir_origem"] = True
    if c.get("risco") == "baixo":
        c["risco"] = "medio"
    return c


class Provedor:
    nome = ""
    rotulo = ""
    tipos: tuple = ()
    chave_env: str | None = None            # nome da variável com a chave do usuário (None = não precisa)
    como_obter = ""
    hosts: tuple | None = ()                # hosts da API e das miniaturas
    hosts_arquivo: tuple | None = ()        # hosts de onde os arquivos são baixados (None = qualquer host público em https)
    intervalo = 1.0                         # segundos entre pedidos ao mesmo host
    idiomas = ("en",)                       # em que língua a busca rende; "pt" = aceita consulta em português
    por_pagina_max = 50
    exige_contato = False                   # True = a política do provedor exige contato no User-Agent (VIDEO_OPS_CONTATO)
    pede_agente = False                     # True = o provedor pede o modelo do agente de IA no User-Agent (VIDEO_OPS_AGENTE)

    def __init__(self, http: comum.Http | None = None):
        self.http = http or comum.Http()

    def disponivel(self) -> tuple[bool, str]:
        if self.chave_env and not comum.chave(self.chave_env):
            return False, (f"{self.rotulo} pulado: falta a chave {self.chave_env}. {self.como_obter} Guarde em "
                           f"{comum.video_ops_home() / 'chaves.env'} (linha {self.chave_env}=…) ou exporte a variável; nunca cole a chave na conversa.")
        if self.exige_contato and not comum.identificacao()["contato"]:
            return False, (f"{self.rotulo} pulado: falta o contato (VIDEO_OPS_CONTATO). A política de User-Agent dele exige um e-mail ou URL de contato em "
                           f"todo pedido e bloqueia sem aviso quem não se identifica. Pergunte ao usuário que contato ele quer usar e grave em "
                           f"{comum.video_ops_home() / 'chaves.env'} (linha VIDEO_OPS_CONTATO=…); não invente um.")
        return True, ""

    def avisos(self) -> list[str]:
        """O que quem roda precisa saber antes do primeiro pedido (não impede a busca)."""
        if self.pede_agente and not comum.identificacao()["agente"]:
            return [f"{self.rotulo}: consultado sem VIDEO_OPS_AGENTE — ele pede que agente de IA diga o modelo no User-Agent. "
                    "Se quem está rodando é um agente, defina VIDEO_OPS_AGENTE=<modelo> no comando."]
        return []

    def buscar(self, consulta: str, tipo: str, orientacao: str | None = None, quantos: int = 8, idioma: str = "en") -> list[dict]:
        raise NotImplementedError

    def detalhar(self, c: dict) -> dict:
        c["detalhado"] = True
        return c


# ───────────────────────────────────────────────────────────────────── Pexels ──
class Pexels(Provedor):
    nome, rotulo, tipos = "pexels", "Pexels", ("video", "imagem")
    chave_env = "PEXELS_API_KEY"
    como_obter = "Crie a chave gratuita em https://www.pexels.com/api/ (200 pedidos/hora, 20.000/mês)."
    hosts = hosts_arquivo = ("pexels.com", "vimeo.com")
    intervalo, idiomas, por_pagina_max = 1.0, ("pt", "en"), 80
    API = "https://api.pexels.com/v1/"

    def buscar(self, consulta, tipo, orientacao=None, quantos=8, idioma="en"):
        params = {"query": consulta, "per_page": max(1, min(self.por_pagina_max, quantos))}
        if orientacao in ("horizontal", "vertical", "quadrado"):
            params["orientation"] = {"horizontal": "landscape", "vertical": "portrait", "quadrado": "square"}[orientacao]
        if idioma == "pt":
            params["locale"] = "pt-BR"
        url = self.API + ("videos/search" if tipo == "video" else "search") + "?" + urllib.parse.urlencode(params)
        j = self.http.json(url, self.hosts, {"Authorization": comum.chave(self.chave_env) or ""}, self.intervalo)
        saida = []
        if tipo == "video":
            for v in j.get("videos") or []:
                arquivos = [{"url": f["link"], "rotulo": f"{f.get('quality') or ''} {f.get('height') or '?'}p".strip(), "largura": _int(f.get("width")),
                             "altura": _int(f.get("height")), "bytes": None, "formato": "mp4", "duracao": v.get("duration")}
                            for f in v.get("video_files") or [] if f.get("link") and f.get("file_type") == "video/mp4"]
                lesma = re.sub(r"-?\d+/?$", "", str(v.get("url") or "").rstrip("/").rsplit("/", 1)[-1]).replace("-", " ").strip()
                usuario = v.get("user") or {}
                saida.append(candidato(self.nome, "video", v.get("id"), lesma or f"Vídeo {v.get('id')}", v.get("url"), "Pexels License",
                                       miniatura_url=v.get("image"), largura=_int(v.get("width")), altura=_int(v.get("height")),
                                       duracao=float(v["duration"]) if v.get("duration") else None, autor=usuario.get("name"),
                                       autor_url=usuario.get("url"), arquivos=arquivos, detalhado=True))
        else:
            for p in j.get("photos") or []:
                src = p.get("src") or {}
                arquivos = [{"url": src[k], "rotulo": k, "largura": _int(p.get("width")) if k == "original" else None,
                             "altura": _int(p.get("height")) if k == "original" else None, "bytes": None, "formato": _ext(src[k]) or "jpg", "duracao": None}
                            for k in ("original", "large2x", "large") if src.get(k)]
                saida.append(candidato(self.nome, "imagem", p.get("id"), p.get("alt") or f"Foto {p.get('id')}", p.get("url"), "Pexels License",
                                       miniatura_url=src.get("medium") or src.get("small"), largura=_int(p.get("width")), altura=_int(p.get("height")),
                                       autor=p.get("photographer"), autor_url=p.get("photographer_url"), arquivos=arquivos, detalhado=True))
        return saida


# ──────────────────────────────────────────────────────────────────── Pixabay ──
class Pixabay(Provedor):
    nome, rotulo, tipos = "pixabay", "Pixabay", ("video", "imagem")
    chave_env = "PIXABAY_API_KEY"
    como_obter = "Crie a conta e copie a chave em https://pixabay.com/api/docs/ (100 pedidos por 60 s; resultados devem ficar em cache por 24 h)."
    hosts = hosts_arquivo = ("pixabay.com",)
    intervalo, idiomas, por_pagina_max = 1.0, ("pt", "en"), 200
    API = "https://pixabay.com/api/"

    def buscar(self, consulta, tipo, orientacao=None, quantos=8, idioma="en"):
        # a documentação só oferece a chave como parâmetro `key` da URL; ela é mascarada em toda mensagem e nunca vai para o cache
        params = {"key": comum.chave(self.chave_env) or "", "q": consulta[:100], "lang": "pt" if idioma == "pt" else "en",
                  "safesearch": "true", "per_page": max(3, min(self.por_pagina_max, quantos))}
        if tipo == "video":
            params["video_type"] = "film"
        else:
            params["image_type"] = "photo"
            if orientacao in ("horizontal", "vertical"):
                params["orientation"] = orientacao
        j = self.http.json(self.API + ("videos/" if tipo == "video" else "") + "?" + urllib.parse.urlencode(params), self.hosts, None, self.intervalo)
        saida = []
        for h in j.get("hits") or []:
            autor = h.get("user")
            autor_url = f"https://pixabay.com/users/{urllib.parse.quote(str(autor))}-{h.get('user_id')}/" if autor and h.get("user_id") else None
            if tipo == "video":
                versoes = h.get("videos") or {}
                arquivos = [{"url": v["url"], "rotulo": f"{k} {v.get('height') or '?'}p", "largura": _int(v.get("width")), "altura": _int(v.get("height")),
                             "bytes": _int(v.get("size")), "formato": _ext(v["url"]) or "mp4", "duracao": h.get("duration")}
                            for k, v in versoes.items() if isinstance(v, dict) and v.get("url")]
                maior = max(arquivos, key=lambda a: a["altura"] or 0, default={})
                mini = next((versoes[k].get("thumbnail") for k in ("small", "tiny", "medium", "large") if isinstance(versoes.get(k), dict) and versoes[k].get("thumbnail")), None)
                saida.append(candidato(self.nome, "video", h.get("id"), h.get("tags") or f"Vídeo {h.get('id')}", h.get("pageURL"), "Pixabay Content License",
                                       miniatura_url=mini, largura=maior.get("largura"), altura=maior.get("altura"),
                                       duracao=float(h["duration"]) if h.get("duration") else None, autor=autor, autor_url=autor_url, arquivos=arquivos, detalhado=True))
            else:
                L, A = _int(h.get("imageWidth")), _int(h.get("imageHeight"))
                k = min(1.0, 1280 / max(L or 1, A or 1))
                arquivos = [{"url": h["largeImageURL"], "rotulo": "1280 px", "largura": int((L or 0) * k) or None, "altura": int((A or 0) * k) or None,
                             "bytes": None, "formato": _ext(h["largeImageURL"]) or "jpg", "duracao": None}] if h.get("largeImageURL") else []
                saida.append(candidato(self.nome, "imagem", h.get("id"), h.get("tags") or f"Imagem {h.get('id')}", h.get("pageURL"), "Pixabay Content License",
                                       miniatura_url=h.get("webformatURL") or h.get("previewURL"), largura=arquivos[0]["largura"] if arquivos else L,
                                       altura=arquivos[0]["altura"] if arquivos else A, autor=autor, autor_url=autor_url, arquivos=arquivos, detalhado=True,
                                       avisos=["a API entrega a imagem em até 1280 px; a resolução cheia só pelo site"]))
        return saida


# ────────────────────────────────────────────────────────── Wikimedia Commons ──
class Wikimedia(Provedor):
    nome, rotulo, tipos = "wikimedia", "Wikimedia Commons", ("video", "imagem")
    hosts = hosts_arquivo = ("wikimedia.org",)
    intervalo, idiomas = 1.0, ("pt", "en")
    exige_contato = True                    # https://foundation.wikimedia.org/wiki/Policy:Wikimedia_Foundation_User-Agent_Policy
    API = "https://commons.wikimedia.org/w/api.php"
    _META = "Artist|Credit|LicenseShortName|LicenseUrl|License|AttributionRequired|Copyrighted|UsageTerms|Restrictions|ObjectName|ImageDescription"

    def buscar(self, consulta, tipo, orientacao=None, quantos=8, idioma="en"):
        # a busca do Commons é de texto integral: palavras soltas trazem palestras de uma hora que só citam o termo (medido em
        # 2026-10-07: "server room" sem aspas devolveu quatro eventos da Casa Branca de 35 a 66 min). Primeiro a frase exata;
        # as palavras soltas só entram quando a frase não trouxe NADA, e saem marcadas como de relevância baixa
        limpa = " ".join(consulta.replace('"', " ").split())
        if " " not in limpa:
            saida = self._buscar(limpa, tipo, quantos)
            for c in saida:
                c["casou"] = "frase"
            return saida[:quantos]
        saida = self._buscar(f'"{limpa}"', tipo, quantos)
        for c in saida:
            c["casou"] = "frase"
        if not saida:
            saida = self._buscar(limpa, tipo, quantos)
            for c in saida:
                c["casou"] = "palavras soltas"
                c["avisos"].append("relevância baixa: o Commons não achou a frase exata e casou palavras soltas do texto — confira se é mesmo o assunto")
        return saida[:quantos]

    def _buscar(self, termo, tipo, quantos):
        params = {"action": "query", "format": "json", "formatversion": "2", "maxlag": "5", "generator": "search",
                  "gsrsearch": f"{termo} filetype:{'video' if tipo == 'video' else 'bitmap'}", "gsrnamespace": "6", "gsrlimit": str(max(1, min(50, quantos))),
                  "prop": "imageinfo|videoinfo" if tipo == "video" else "imageinfo", "iiprop": "url|size|mime|mediatype|extmetadata",
                  "iiextmetadatafilter": self._META, "iiurlwidth": "500" if tipo == "video" else "1920"}
        if tipo == "video":
            params["viprop"] = "derivatives"
        j = self.http.json(self.API + "?" + urllib.parse.urlencode(params), self.hosts, None, self.intervalo)
        if isinstance(j, dict) and j.get("error"):
            raise comum.Erro(f"Wikimedia Commons recusou a busca: {j['error'].get('code')} — {_texto(j['error'].get('info'), 160)}",
                             "Código maxlag/ratelimited = servidores ocupados: espere um minuto e tente de novo.")
        paginas = sorted((j.get("query") or {}).get("pages") or [], key=lambda p: p.get("index", 0))
        saida = []
        for p in paginas:
            ii = (p.get("imageinfo") or [{}])[0]
            if not ii.get("url"):
                continue
            meta = {k: (v.get("value") if isinstance(v, dict) else v) for k, v in (ii.get("extmetadata") or {}).items()}
            artista = str(meta.get("Artist") or "")
            m = re.search(r'href="([^"]+)"', artista)
            autor_url = html.unescape(m.group(1)) if m else None
            if autor_url and autor_url.startswith("//"):
                autor_url = "https:" + autor_url
            if autor_url and "redlink=1" in autor_url:
                autor_url = None
            c = candidato(self.nome, tipo, p.get("pageid"), meta.get("ObjectName") or re.sub(r"\.\w+$", "", str(p.get("title", "")).removeprefix("File:")),
                          ii.get("descriptionurl"), meta.get("LicenseShortName") or meta.get("License"), meta.get("LicenseUrl"),
                          descricao=meta.get("ImageDescription"), largura=_int(ii.get("width")), altura=_int(ii.get("height")),
                          duracao=float(ii["duration"]) if ii.get("duration") else None, autor=_texto(artista, 80) or _texto(meta.get("Credit"), 80),
                          autor_url=autor_url, detalhado=True)
            if c["licenca_id"] == "desconhecida" and meta.get("License"):          # o código curto às vezes diz mais que o nome
                ficha = registro.avaliar_licenca(meta.get("License"), meta.get("LicenseUrl"))
                if ficha["id"] != "desconhecida":
                    c.update(licenca=ficha["nome"], licenca_id=ficha["id"], licenca_url=ficha.get("url"), exige_atribuicao=ficha["exige_atribuicao"],
                             uso_comercial=ficha["uso_comercial"], permitida=ficha["permitida"], motivo=ficha["motivo"], risco=ficha["risco"])
            if _texto(meta.get("Restrictions")):
                c["avisos"].append(f"restrições além do direito autoral: {_texto(meta.get('Restrictions'), 60)} (marca, direito de imagem…)")
            original = {"url": comum.url_limpa(ii["url"]), "rotulo": "original", "largura": c["largura"], "altura": c["altura"], "bytes": _int(ii.get("size")),
                        "formato": _ext(ii["url"]), "duracao": c["duracao"]}
            arquivos = [original]
            mini = ii.get("thumburl")
            if tipo == "video":
                for dv in ((p.get("videoinfo") or [{}])[0].get("derivatives") or []):
                    if not dv.get("src") or not dv.get("transcodekey") or "webm" not in str(dv.get("type")):
                        continue
                    arquivos.append({"url": comum.url_limpa(dv["src"]), "rotulo": dv["transcodekey"], "largura": _int(dv.get("width")), "altura": _int(dv.get("height")),
                                     "bytes": int(dv["bandwidth"] / 8 * c["duracao"]) if dv.get("bandwidth") and c["duracao"] else None,
                                     "bytes_estimado": True, "formato": "webm", "duracao": c["duracao"]})
            elif mini and ii.get("thumbwidth") and ii["thumbwidth"] < (c["largura"] or 0):
                arquivos.append({"url": comum.url_limpa(mini), "rotulo": f"{ii['thumbwidth']} px", "largura": _int(ii.get("thumbwidth")), "altura": _int(ii.get("thumbheight")),
                                 "bytes": None, "formato": _ext(mini) or "jpg", "duracao": None})
                mini = re.sub(r"/\d+px-", "/500px-", mini)
            c["miniatura_url"] = comum.url_limpa(mini) if mini else None
            c["arquivos"] = arquivos
            saida.append(c)
        return saida


# ──────────────────────────────────────────────────── NASA Image and Video Library ──
class Nasa(Provedor):
    nome, rotulo, tipos = "nasa", "NASA Image and Video Library", ("video", "imagem")
    hosts = hosts_arquivo = ("nasa.gov",)
    intervalo = 1.0
    API = "https://images-api.nasa.gov/"
    _TERCEIROS = re.compile(r"©|\(c\)|copyright|courtesy of|cortesia de", re.I)
    _DA_CASA = re.compile(r"nasa|jpl|caltech|goddard|gsfc|jsc|ksc|msfc|ames|langley|glenn|stsci|johnson space|kennedy space", re.I)

    def _de_terceiros(self, descricao: str, coautor: str = "") -> bool:
        """A NASA avisa que material de terceiros publicado por ela continua protegido: procura os sinais disso no texto."""
        if self._TERCEIROS.search(descricao or ""):
            return True
        credito = re.search(r"(?:image |photo |video )?credits?:\s*([^.\n]{3,80})", descricao or "", re.I)
        if credito and not self._DA_CASA.search(credito.group(1)):
            return True
        return bool(coautor.strip()) and not self._DA_CASA.search(coautor)

    def buscar(self, consulta, tipo, orientacao=None, quantos=8, idioma="en"):
        params = {"q": consulta, "media_type": "video" if tipo == "video" else "image", "page_size": max(1, min(self.por_pagina_max, quantos))}
        j = self.http.json(self.API + "search?" + urllib.parse.urlencode(params), self.hosts, None, self.intervalo)
        saida = []
        for it in ((j.get("collection") or {}).get("items") or [])[:quantos]:
            d = (it.get("data") or [{}])[0]
            nid = d.get("nasa_id")
            if not nid:
                continue
            imagens = [l for l in it.get("links") or [] if l.get("render") == "image" and l.get("href")]
            previa = next((l for l in imagens if l.get("rel") == "preview"), None) or (imagens[0] if imagens else None)
            centro = str(d.get("center") or "").strip()
            c = candidato(self.nome, tipo, nid, d.get("title") or nid, "https://images.nasa.gov/details/" + urllib.parse.quote(str(nid)), "NASA",
                          descricao=d.get("description"), miniatura_url=comum.url_limpa(previa["href"]) if previa else None,
                          autor="NASA" if centro in ("", "HQ") else f"NASA/{centro}", autor_url="https://www.nasa.gov/")
            c["criado_em"] = str(d.get("date_created") or "")[:10] or None
            if tipo == "imagem":
                arquivos = [{"url": comum.url_limpa(l["href"]), "rotulo": re.sub(r".*~(\w+)\.\w+$", r"\1", l["href"]), "largura": _int(l.get("width")),
                             "altura": _int(l.get("height")), "bytes": _int(l.get("size")), "formato": _ext(l["href"]) or "jpg", "duracao": None}
                            for l in imagens if l.get("rel") != "preview" and l.get("width")]
                maior = max(arquivos, key=lambda a: a["largura"] or 0, default={})
                c.update(largura=maior.get("largura"), altura=maior.get("altura"), arquivos=arquivos)
            if self._de_terceiros(str(d.get("description") or ""), str(d.get("secondary_creator") or "")):
                c["avisos"].append("a descrição cita crédito ou copyright de terceiros: material que não é da NASA precisa de licença própria")
                c["risco"] = "medio"
            saida.append(c)
        return saida

    def detalhar(self, c):
        if c.get("detalhado"):
            return c
        nid = urllib.parse.quote(c["id_fonte"])
        j = self.http.json(self.API + "asset/" + nid, self.hosts, None, self.intervalo)
        hrefs = [comum.url_limpa(i["href"]) for i in ((j.get("collection") or {}).get("items") or []) if i.get("href")]
        exts = EXT_VIDEO if c["tipo"] == "video" else EXT_IMAGEM
        conhecidos = {a["url"]: a for a in c.get("arquivos") or []}
        arquivos = []
        for h in hrefs:
            m = re.search(r"~(orig|large|medium|small|mobile|preview)\.(\w+)$", h)
            if not m or m.group(2).lower() not in exts:
                continue
            arquivos.append(conhecidos.get(h) or {"url": h, "rotulo": m.group(1), "largura": None, "altura": None, "bytes": None,
                                                  "formato": m.group(2).lower(), "duracao": None})
        meta_url = next((h for h in hrefs if h.endswith("/metadata.json")), None)
        if meta_url:
            try:
                meta = self.http.json(meta_url, self.hosts, None, self.intervalo, teto=2 << 20)
            except comum.Erro:
                meta = {}
            L = _int(meta.get("QuickTime:ImageWidth") or meta.get("File:ImageWidth") or meta.get("EXIF:ImageWidth"))
            A = _int(meta.get("QuickTime:ImageHeight") or meta.get("File:ImageHeight") or meta.get("EXIF:ImageHeight"))
            dur = comum.segundos(meta.get("QuickTime:Duration") or meta.get("QuickTime:MediaDuration"))
            if c["tipo"] == "video":
                c["duracao"] = dur
            for a in arquivos:
                if a["rotulo"] == "orig":
                    a.update(largura=a["largura"] or L, altura=a["altura"] or A)
                if c["tipo"] == "video":
                    a["duracao"] = dur
            if not c.get("largura") and L:
                c.update(largura=L, altura=A)
            direitos = " ".join(str(meta.get(k) or "") for k in ("XMP:Rights", "EXIF:Copyright", "IPTC:CopyrightNotice", "XMP:UsageTerms"))
            if self._TERCEIROS.search(direitos) and "nasa" not in direitos.lower():
                c["avisos"].append(f"os metadados trazem aviso de direitos: «{_texto(direitos, 80)}»")
                c["risco"] = "medio"
        c.update(arquivos=arquivos, detalhado=True)
        return c


# ─────────────────────────────────────────────────────────── Internet Archive ──
class Archive(Provedor):
    nome, rotulo, tipos = "archive", "Internet Archive", ("video", "imagem")
    hosts = hosts_arquivo = ("archive.org",)
    intervalo = 1.0
    pede_agente = True                      # https://archive.org/developers/bots.html (página aberta em 2026-10-12)
    # só licença aberta JÁ na consulta: sem os dois NOT, 4 de 6 resultados de "earth from space" eram NC ou ND (medido em 2026-10-07)
    _FILTRO = "(licenseurl:*creativecommons.org* OR licenseurl:*publicdomain*) AND NOT licenseurl:*-nc* AND NOT licenseurl:*-nd*"

    def buscar(self, consulta, tipo, orientacao=None, quantos=8, idioma="en"):
        # busca por campo: o texto livre casa com qualquer menção e, ordenado por downloads, devolve filmes inteiros sem relação
        limpa = " ".join(re.sub(r'["()\[\]:]', " ", consulta).split())
        palavras = " AND ".join(limpa.split())
        q = (f'(title:({palavras}) OR subject:"{limpa}" OR description:"{limpa}") AND mediatype:{"movies" if tipo == "video" else "image"} AND {self._FILTRO}')
        params = [("q", q), *[("fl[]", f) for f in ("identifier", "title", "licenseurl", "creator", "year", "description", "downloads")],
                  ("rows", str(max(1, min(self.por_pagina_max, quantos)))), ("page", "1"), ("output", "json")]
        j = self.http.json("https://archive.org/advancedsearch.php?" + urllib.parse.urlencode(params), self.hosts, None, self.intervalo)
        saida = []
        for d in (j.get("response") or {}).get("docs") or []:
            ident = d.get("identifier")
            if not ident:
                continue
            c = candidato(self.nome, tipo, ident, d.get("title") or ident, "https://archive.org/details/" + urllib.parse.quote(ident), None, d.get("licenseurl"),
                          descricao=d.get("description"), miniatura_url="https://archive.org/services/img/" + urllib.parse.quote(ident),
                          autor=_texto(d.get("creator"), 80) or None)
            c["criado_em"] = str(d.get("year") or "") or None
            saida.append(licenca_declarada(c, "a licença é a declarada por quem subiu o item; o Internet Archive não a garante"))
        return saida

    def detalhar(self, c):
        if c.get("detalhado"):
            return c
        ident = c["id_fonte"]
        j = self.http.json("https://archive.org/metadata/" + urllib.parse.quote(ident), self.hosts, None, self.intervalo)
        exts = EXT_VIDEO if c["tipo"] == "video" else EXT_IMAGEM
        arquivos = []
        for f in j.get("files") or []:
            nome = str(f.get("name") or "")
            ext = nome.rsplit(".", 1)[-1].lower() if "." in nome else ""
            if ext not in exts or "/" in nome or str(f.get("format")).lower() in ("thumbnail", "item tile", "animated gif"):
                continue
            arquivos.append({"url": f"https://archive.org/download/{urllib.parse.quote(ident)}/{urllib.parse.quote(nome)}",
                             "rotulo": f"{f.get('format') or ext} ({'original' if f.get('source') == 'original' else 'derivado'})",
                             "largura": _int(f.get("width")), "altura": _int(f.get("height")), "bytes": _int(f.get("size")), "formato": ext,
                             "duracao": comum.segundos(f.get("length"))})
        melhor = max(arquivos, key=lambda a: (a["altura"] or 0, a["formato"] == "mp4"), default={})
        c.update(arquivos=arquivos, detalhado=True, largura=melhor.get("largura") or c.get("largura"), altura=melhor.get("altura") or c.get("altura"),
                 duracao=melhor.get("duracao") or c.get("duracao"))
        return c


# ────────────────────────────────────────────────────────────────── Openverse ──
class Openverse(Provedor):
    nome, rotulo, tipos = "openverse", "Openverse", ("imagem",)
    hosts = ("openverse.org",)
    hosts_arquivo = None                      # o arquivo mora no site de origem (Flickr, museus…): qualquer host público em https
    intervalo, por_pagina_max = 3.2, 20       # anônimo: 20 pedidos/min e 200/dia (cabeçalhos x-ratelimit-* de 2026-10-07)

    def buscar(self, consulta, tipo, orientacao=None, quantos=8, idioma="en"):
        params = {"q": consulta[:200], "page_size": max(1, min(self.por_pagina_max, quantos)), "license_type": "commercial,modification", "mature": "false"}
        if orientacao in ("horizontal", "vertical", "quadrado"):
            params["aspect_ratio"] = {"horizontal": "wide", "vertical": "tall", "quadrado": "square"}[orientacao]
        j = self.http.json("https://api.openverse.org/v1/images/?" + urllib.parse.urlencode(params), self.hosts, None, self.intervalo)
        saida = []
        for r in j.get("results") or []:
            if not r.get("url"):
                continue
            lic = " ".join(x for x in (str(r.get("license") or ""), str(r.get("license_version") or "")) if x)
            c = candidato(self.nome, "imagem", r.get("id"), r.get("title") or "Imagem", r.get("foreign_landing_url"), lic, r.get("license_url"),
                          miniatura_url=r.get("thumbnail"), largura=_int(r.get("width")), altura=_int(r.get("height")), autor=r.get("creator"),
                          autor_url=r.get("creator_url"), detalhado=True)
            c["arquivos"] = [{"url": r["url"], "rotulo": f"original ({r.get('source') or r.get('provider') or 'origem'})", "largura": c["largura"], "altura": c["altura"],
                              "bytes": _int(r.get("filesize")), "formato": ext_segura(r.get("filetype"), "imagem") or ext_segura(_ext(r["url"]), "imagem"),
                              "duracao": None}]
            c["origem"] = _texto(r.get("source") or r.get("provider"), 40) or None
            saida.append(licenca_declarada(c, "o Openverse não verifica a licença: confira na página de origem antes de usar"))
        return saida


PROVEDORES = {p.nome: p for p in (Pexels, Pixabay, Nasa, Wikimedia, Archive, Openverse)}
ORDEM = ("pexels", "pixabay", "nasa", "wikimedia", "archive", "openverse")


# ──────────────────────────────────────────────────────── ordenar e filtrar ──
def pontuar(c: dict, orientacao: str | None = None, lado_alvo: int = 1080, posicao: int = 0) -> float:
    """Nota de um candidato para ordenar a lista: licença primeiro, depois orientação, resolução, duração e crédito."""
    nota = 100.0 if c.get("permitida") else -1000.0
    ori = orientacao_de(c.get("largura"), c.get("altura"))
    if orientacao and ori:
        nota += 30 if ori == orientacao else -10
    menor = min(c.get("largura") or 0, c.get("altura") or 0)
    if menor:
        nota += 20 if menor >= lado_alvo else 10 if menor >= 720 else -5 if menor >= 480 else -25
    d = c.get("duracao")
    if c.get("tipo") == "video" and d:
        nota += 15 if 4 <= d <= 45 else 5 if d <= 180 else -8 if d <= 600 else -30      # mais de 10 min é palestra ou filme, não b-roll
    if not c.get("exige_atribuicao"):
        nota += 5
    if c.get("risco") == "medio":
        nota -= 5
    if c.get("conferir_origem"):                              # licença só declarada por quem subiu: fica abaixo do equivalente de origem conferida
        nota -= 12
    if c.get("casou") == "palavras soltas":
        nota -= 40
    nota -= 3 * len(c.get("avisos") or [])
    return nota - posicao * 1.5


def passa(c: dict, min_duracao=None, max_duracao=None, min_largura=None, min_altura=None, licenca: str = "permitidas") -> tuple[bool, str]:
    """Filtro: (entra?, motivo de sair). Valor desconhecido não elimina — aparece com "?" para o usuário julgar."""
    if licenca == "permitidas" and not c.get("permitida"):
        return False, f"licença recusada ({c.get('licenca')})"
    if licenca == "sem-atribuicao" and (not c.get("permitida") or c.get("exige_atribuicao")):
        return False, "exige atribuição"
    d = c.get("duracao")
    if c.get("tipo") == "video" and d is not None:
        if min_duracao and d < min_duracao:
            return False, f"curto demais ({d:.1f} s)"
        if max_duracao and d > max_duracao:
            return False, f"longo demais ({d:.0f} s)"
    if min_largura and c.get("largura") and c["largura"] < min_largura:
        return False, f"largura {c['largura']} < {min_largura}"
    if min_altura and c.get("altura") and c["altura"] < min_altura:
        return False, f"altura {c['altura']} < {min_altura}"
    return True, ""


def ordenar_arquivos(c: dict, lado_alvo: int = 1080, teto_bytes: int | None = None) -> list[dict]:
    """As versões de um candidato, da melhor para a pior escolha: primeiro a MENOR cujo lado menor alcança `lado_alvo`
    (e as maiores em seguida), depois as que ficam abaixo, da maior para a menor; versões de tamanho desconhecido (NASA)
    entram por rótulo. Fica de fora o que já se sabe que passa do teto. Formato que o ffmpeg lê sem surpresa ganha no empate."""
    preferencia = {"mp4": 0, "webm": 1, "mov": 1, "m4v": 1, "jpg": 0, "jpeg": 0, "png": 1}
    rotulos = {"large": 0, "medium": 1, "small": 2, "orig": 3, "original": 3, "mobile": 4, "preview": 5}

    def lado(a):
        return min(a.get("largura") or 0, a.get("altura") or 0)

    arquivos = [a for a in c.get("arquivos") or [] if a.get("url") and not (teto_bytes and a.get("bytes") and not a.get("bytes_estimado") and a["bytes"] > teto_bytes)]
    quase = lado_alvo * 0.88        # um "1080p" de vídeo 2:1 tem 1920×960: é da classe pedida
    bons = sorted((a for a in arquivos if lado(a) >= quase), key=lambda a: (lado(a), preferencia.get(a.get("formato"), 5), a.get("bytes") or 0))
    cegos = sorted((a for a in arquivos if not lado(a)), key=lambda a: (rotulos.get(a.get("rotulo"), 9), preferencia.get(a.get("formato"), 5)))
    menores = sorted((a for a in arquivos if 0 < lado(a) < quase), key=lambda a: (-lado(a), preferencia.get(a.get("formato"), 5)))
    return bons + cegos + menores


def escolher_arquivo(c: dict, lado_alvo: int = 1080, teto_bytes: int | None = None) -> dict | None:
    """A primeira de `ordenar_arquivos` (ou None se nada cabe no teto)."""
    ordem = ordenar_arquivos(c, lado_alvo, teto_bytes)
    return ordem[0] if ordem else None
