#!/usr/bin/env python3
"""registro.py — registro de licenças do b-roll de um projeto (broll/licencas.json) e créditos (broll/creditos.md).

Módulo compartilhado: a skill video-broll é a dona do arquivo; outras skills (video-pauta-midia) importam este
módulo por posição e gravam por ele. Só usa a biblioteca padrão (Python ≥ 3.9) e não depende do kit de direção
de arte.

    from pathlib import Path
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "video-broll" / "scripts"))
    import registro

    registro.carregar(projeto)                         -> {"versao": 1, "itens": [...]}
    registro.proximo_id(projeto, "B")                  -> "B004"   (B = banco, Y = YouTube, W = imagem/captura da web)
    registro.adicionar(projeto, item)                  -> "B004"   (valida, aplica a política de licenças, grava)
    registro.atualizar(projeto, "B004", risco="medio") -> item atualizado   (o id é o 2º argumento; id="B004" também vale)
    registro.marcar_uso(projeto, "B004", "C03")        -> ["C03"]
    registro.creditos_md(projeto)                      -> texto de broll/creditos.md (e grava o arquivo)
    registro.remover(projeto, "B004")                  -> item removido (recusa se houver usado_em)

Toda gravação acontece sob trava de arquivo (flock em broll/_registro.lock) e por troca atômica: dois processos
gravando ao mesmo tempo nunca perdem item nem repetem id. `projeto` é a RAIZ do projeto (a pasta que tem broll/).

Política de licenças (references/licencas.md): entram por padrão a licença do Pexels, a licença de conteúdo do
Pixabay, CC0/domínio público, mídia da NASA, CC BY e CC BY-SA; NC, ND, «todos os direitos reservados» e licença
desconhecida são recusadas, salvo exceção registrada com base_legal "citacao" ou "autorizacao" e `notas` explicando.
A leitura do texto é fechada: qualquer marca de restrição (não comercial, sem derivações, direitos reservados, «não
está em domínio público», «só nos EUA») vence, em qualquer grafia — colada (CCBYNC, BY-NCSA), pontuada (n.c.) ou com
traço tipográfico; depois de reconhecer «CC BY», termo que sobra sem ser versão, jurisdição ou palavra do nome da
licença faz o texto valer como desconhecido; texto e URL que divergem valem pela mais restritiva.

base_legal "proprio" é declaração, não salvo-conduto: não convive com licença de terceiro que a política recusa (NC,
ND, «todos os direitos reservados», licença padrão do YouTube) e, quando o material veio de outro lugar que não o
disco do usuário (fonte ≠ "local", ou há pagina_url/arquivo_url), exige `notas` dizendo por que ele é da casa.

O que este módulo acrescenta ao contrato de broll/licencas.json (campos a mais; nenhum do contrato muda de nome):
  notas            texto livre; OBRIGATÓRIO quando base_legal é "citacao" ou "autorizacao" (o que é citado e por quê,
                   ou quem autorizou e onde está a prova) e quando é "proprio" com fonte ≠ "local" ou com pagina_url
                   (por que o material publicado ali é da casa). Quem registra citação precisa mandar este campo.
  fonte "local"    valor a mais do campo `fonte`: arquivo do próprio usuário (registro.py adicionar --de-arquivo).
  licenca_id       id da política (cc-by, pd, nasa…);  licenca_original / licenca_url_original: o texto e a URL como
                   chegaram, quando `licenca` foi regravada com o nome canônico.
  credito_tela     crédito curto para a moldura;  tipo ("video" | "imagem"), titulo, id_fonte, bytes.
  trecho           (do contrato) intervalo DA FONTE, em segundos do vídeo original: a parte que o item usa ou cita
                   (espelho de t0/t1 da pauta). Nunca é regravado pelo tratamento.
  trecho_arquivo   onde está a parte aprovada DENTRO do arquivo baixado, em segundos do arquivo, quando ele traz sobra
                   (baixar.py --trecho corta no quadro-chave anterior). É o padrão do tratar.py; o trecho usado em cada
                   peça fica no carimbo dela (parametros.trecho).
  arquivo          sempre dentro de broll/bruto/ (caminho de fora é recusado).
"""
from __future__ import annotations

import argparse
import contextlib
import copy
try:
    import fcntl
except ImportError:                    # Windows: flock da adaptação local (video-direcao-de-arte/kit/_win.py)
    import os as _os, sys as _sys
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "video-direcao-de-arte", "kit"))
    import _win as fcntl
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata
from datetime import datetime
from pathlib import Path

sys.dont_write_bytecode = True
shutil.rmtree(Path(__file__).resolve().parent / "__pycache__", ignore_errors=True)     # a skill instalada não acumula .pyc

VERSAO = 1
ARQUIVO = Path("broll") / "licencas.json"
CREDITOS = Path("broll") / "creditos.md"
TRAVA = Path("broll") / "_registro.lock"
PASTA_BRUTO = Path("broll") / "bruto"
PASTA_TRATADO = Path("broll") / "tratado"

PREFIXOS = {"B": "banco de mídia", "Y": "YouTube", "W": "imagem ou captura da web"}
FONTES = ("pexels", "pixabay", "wikimedia", "archive", "nasa", "openverse", "youtube", "web", "local")
BASES_LEGAIS = ("licenca", "citacao", "autorizacao", "proprio")
RISCOS = ("baixo", "medio", "alto")
NOMES_FONTE = {"pexels": "Pexels", "pixabay": "Pixabay", "wikimedia": "Wikimedia Commons", "archive": "Internet Archive",
               "nasa": "NASA", "openverse": "Openverse", "youtube": "YouTube", "web": "web", "local": "arquivo próprio"}

SAIDA_OK, SAIDA_ERRO, SAIDA_SEM_PROJETO, SAIDA_USO = 0, 1, 2, 64


class RegistroErro(Exception):
    """Erro do registro com mensagem acionável (o que houve) e `dica` (o que fazer)."""

    def __init__(self, mensagem: str, dica: str | None = None, codigo: int = SAIDA_ERRO):
        super().__init__(mensagem)
        self.mensagem, self.dica, self.codigo = mensagem, dica, codigo

    def __str__(self) -> str:
        return self.mensagem if not self.dica else f"{self.mensagem}\n{self.dica}"


# ───────────────────────────────────────────────────────── política de licenças ──
# Conferido nas páginas oficiais em 2026-10-07 (resumo e links em references/licencas.md).
#   permitida  : entra por padrão com base_legal "licenca"
#   atribuicao : a licença EXIGE crédito            comercial : permite uso comercial (vídeo monetizado)
#   derivados  : permite recortar/tratar a cor      igual     : obras derivadas herdam a licença (ShareAlike)
def _lic(nome, url, permitida, atribuicao, comercial, derivados, igual=False, risco="baixo", motivo=""):
    return {"nome": nome, "url": url, "permitida": permitida, "exige_atribuicao": atribuicao, "uso_comercial": comercial,
            "permite_derivados": derivados, "compartilha_igual": igual, "risco": risco, "motivo": motivo}


_CC = "https://creativecommons.org/licenses/"
LICENCAS = {
    "pexels": _lic("Licença do Pexels", "https://www.pexels.com/license/", True, False, True, True),
    "pixabay": _lic("Licença de conteúdo do Pixabay", "https://pixabay.com/service/license-summary/", True, False, True, True),
    "cc0": _lic("CC0 1.0", "https://creativecommons.org/publicdomain/zero/1.0/", True, False, True, True),
    "pdm": _lic("Domínio público (Public Domain Mark 1.0)", "https://creativecommons.org/publicdomain/mark/1.0/", True, False, True, True),
    "pd": _lic("Domínio público", None, True, False, True, True),
    "nasa": _lic("Mídia da NASA", "https://www.nasa.gov/nasa-brand-center/images-and-media/", True, True, True, True,
                 motivo="em geral sem direito autoral nos EUA; a NASA pede ser citada como fonte; não pode sugerir endosso nem usar a insígnia"),
    "cc-by": _lic("CC BY", _CC + "by/4.0/", True, True, True, True),
    "cc-by-sa": _lic("CC BY-SA", _CC + "by-sa/4.0/", True, True, True, True, igual=True, risco="medio",
                     motivo="ShareAlike: se o uso contar como adaptação, a obra derivada tem de sair sob a mesma licença"),
    "cc-by-nc": _lic("CC BY-NC", _CC + "by-nc/4.0/", False, True, False, True, risco="alto",
                     motivo="NC proíbe uso voltado a vantagem comercial (canal monetizado, peça patrocinada)"),
    "cc-by-nc-sa": _lic("CC BY-NC-SA", _CC + "by-nc-sa/4.0/", False, True, False, True, igual=True, risco="alto",
                        motivo="NC proíbe uso voltado a vantagem comercial (canal monetizado, peça patrocinada)"),
    "cc-by-nd": _lic("CC BY-ND", _CC + "by-nd/4.0/", False, True, True, False, risco="alto",
                     motivo="ND proíbe compartilhar adaptações: recortar, tratar a cor ou montar com outro material já é adaptar"),
    "cc-by-nc-nd": _lic("CC BY-NC-ND", _CC + "by-nc-nd/4.0/", False, True, False, False, risco="alto",
                        motivo="NC e ND: sem uso comercial e sem adaptação"),
    "restrita": _lic("Licença de uso restrito (não comercial ou sem derivados)", None, False, True, False, False, risco="alto",
                     motivo="o texto da licença restringe o uso (não comercial, só editorial ou pessoal, sem modificação)"),
    "todos-os-direitos": _lic("Todos os direitos reservados", None, False, True, False, False, risco="alto",
                              motivo="sem licença de reuso: só com autorização do titular ou como citação"),
    "desconhecida": _lic("Licença desconhecida", None, False, True, False, False, risco="alto",
                         motivo="sem licença identificada não há permissão de uso"),
}
PERMITIDAS = tuple(k for k, v in LICENCAS.items() if v["permitida"])
# da menos para a mais restritiva: quando texto e URL divergem, vale a de número maior
_RIGOR = {"cc0": 0, "pdm": 0, "pd": 0, "pexels": 1, "pixabay": 1, "nasa": 2, "cc-by": 3, "cc-by-sa": 4, "cc-by-nc": 5, "cc-by-nd": 5,
          "cc-by-nc-sa": 6, "cc-by-nc-nd": 7, "restrita": 8, "todos-os-direitos": 9, "desconhecida": 10}
_CC_CODIGOS = ("by", "by-sa", "by-nc", "by-nd", "by-nc-sa", "by-nc-nd")

_RE_VERSAO = re.compile(r"(?<![\d.])(\d\.\d)(?!\d)")
_RE_CC_URL = re.compile(r"creativecommons\.org/(licenses|publicdomain)/([a-z+\-]+)(?:/(\d\.\d))?(?:/([a-z]{2,5}))?", re.I)
# Marcas lidas no texto já sem acento, em minúsculas e com toda pontuação virando espaço ("CC BY-NC" → "cc by nc").
# As RESTRITIVAS são procuradas antes de qualquer classificação positiva: na dúvida, a licença é recusada.
_M_NC = re.compile(r"\bnc\b|non ?commercial|nao ?comercia(?:l|is)|\bno ?comercial|not for commercial|"
                   r"\b(?:sem|without|no) (?:uso|fins?|use) comercia(?:l|is)|commercial use (?:is )?(?:prohibited|forbidden|not allowed|not permitted)|"
                   r"uso comercial (?:e )?(?:proibido|vedado|nao permitido)|\b(?:personal|editorial|educational) use only|"
                   r"\b(?:somente|apenas|so) (?:para )?uso (?:pessoal|editorial|educacional)")
_M_ND = re.compile(r"\bnd\b|noderiv|\bno deriv\w*|semderiv|\bsem deriv\w*|\bsin (?:obras? )?deriv\w*|nao a obras derivadas|"
                   r"(?:vedad|proibid)\w+ (?:a criacao de )?obras derivadas|\bno modifications?\b|\bsem modificac\w+")
_M_RESERVADO = re.compile(r"all rights? reserved|todos os direitos|standard youtube licen[cs]e|licenca padrao do youtube")
_M_NEGA_PD = re.compile(r"\b(?:not|nao|never|nunca|no longer)\b(?: \w+){0,3} (?:public domain|dominio publico)")
_M_RESTRITA = re.compile(r"uso restrito|restricao de uso|restricted use")
_M_CC = re.compile(r"\bcc\b|creative ?commons")
_M_BY = re.compile(r"\bby\b|attribution|atribuicao|atribucion|reconocimiento")
_M_SA = re.compile(r"\bsa\b|share ?alike|compartilha ?igual|compartir ?igual")
_M_PEXELS = re.compile(r"(?:licenca (?:de conteudo )?d[oa] )?(pexels|pixabay)(?: content)?(?: licen[cs]e| licenca)?")
_M_NASA = re.compile(r"(?:midia da |media da )?nasa(?: media usage guidelines| media guidelines| media| image and video library)?")
# «domínio público» com ressalva não é domínio público: "in the US only", "copyrighted elsewhere", "exceto…"
_M_PD_PARCIAL = re.compile(r"\bonly\b|\bsomente\b|\bapenas\b|\belsewhere\b|\bexcept\b|\bexceto\b|\boutside\b|\bfora d[oa]s?\b|"
                           r"(?<!not )(?<!no )(?<!nao )\bcopyrighted\b|\bprotegid[oa]s?\b|\bmay be (?:copyrighted|protected)\b|\bpode estar protegid")
_M_PROPRIO = re.compile(r"(?:(?:material|arquivo|acervo|obra|producao|gravacao|imagem|video|footage|conteudo) )?(?:proprio|propria|autoral|pessoal|da casa|da equipe)|own work|own footage")
# Leitura FECHADA de «CC BY»: além dos códigos, só passam versão, jurisdição e as palavras do nome da licença.
_RE_CODIGOS_COLADOS = re.compile(r"(?:cc|by|nc|nd|sa){2,}")
_JURISDICOES_CC = frozenset("ar at au be bg br ca ch cl cn co cr cz de dk ec ee eg es fi fr gr gt hk hr hu ie il in it jp kr lu mk mt mx my "
                            "nl no nz pe ph pl pr pt ro rs se sg si th tw ug uk us ve vn za igo scotland "
                            "brasil brazil portugal germany deutschland france spain espana italy italia netherlands australia canada japan "
                            "india china mexico argentina chile colombia austria switzerland england wales united states kingdom".split())
_PALAVRAS_CC = frozenset("cc by sa creative commons attribution atribuicao atribucion reconocimiento share alike sharealike compartilha igual "
                         "compartilhaigual compartir compartirigual license licence licenca licencia licensed licenciado licenciada under sob "
                         "international internacional intl unported generic generico generica version versao v deed legalcode "
                         "some rights reserved alguns direitos reservados the a an of this work is esta este obra uma o da do".split())


def _sem_acento(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")


def _termos(cru: str) -> str:
    """Texto de licença → termos em minúsculas e sem acento, separados por um espaço. Toda pontuação vira espaço —
    inclusive a que não é ASCII (o hífen U+2011 de «CC‑BY‑NC» e a meia-risca de «BY–NC» sumiam e colavam os códigos);
    o ponto só fica entre dígitos (4.0); letras soltas em sequência são juntadas («n.c.» → «nc») e códigos colados
    são separados («ccbync» → «cc by nc», «ncsa» → «nc sa»)."""
    s = unicodedata.normalize("NFKD", str(cru))
    s = "".join(" " if unicodedata.category(ch)[0] in "PZSC" and ch not in ".+" else ch for ch in s)
    s = re.sub(r"[^a-z0-9.+]+", " ", s.encode("ascii", "ignore").decode("ascii").lower())
    s = re.sub(r"(?<!\d)\.|\.(?!\d)", " ", s)
    s = re.sub(r"(?<=[a-z])(?=\d\.\d)", " ", s)                    # «by4.0» → «by 4.0»
    termos, soltas = [], ""
    for tk in s.split() + [""]:                                    # o "" final descarrega as letras soltas pendentes
        if len(tk) == 1 and tk.isalpha():
            soltas += tk
            continue
        if soltas:
            termos.append(soltas)
            soltas = ""
        if tk:
            termos.append(tk)
    saida = []
    for tk in termos:
        saida += re.findall(r"cc|by|nc|nd|sa", tk) if _RE_CODIGOS_COLADOS.fullmatch(tk) else [tk]
    return " ".join(saida)


def _termo_conhecido(tk: str) -> bool:
    return tk in _PALAVRAS_CC or tk in _JURISDICOES_CC or bool(re.fullmatch(r"\d(?:\.\d)?", tk))


def _licenca_pela_url(url) -> tuple[str | None, str | None]:
    """(id, versão) que a URL de uma licença Creative Commons declara; (None, None) quando não é uma URL da CC."""
    m = _RE_CC_URL.search(str(url or ""))
    if not m:
        return None, None
    tipo, codigo, versao = m.group(1).lower(), m.group(2).lower(), m.group(3)
    if tipo == "publicdomain":
        return {"zero": "cc0", "mark": "pdm"}.get(codigo, "pd"), versao
    if codigo == "publicdomain":                         # http://creativecommons.org/licenses/publicdomain/ (dedicatória antiga)
        return "pd", None
    if codigo in _CC_CODIGOS:
        return "cc-" + codigo, versao
    return "desconhecida", versao                       # sampling+, devnations…: fora da política


def _licenca_pelo_texto(licenca) -> tuple[str | None, str | None, bool]:
    """(id, versão, veto) pelo TEXTO da licença. id None = texto vazio. veto = o texto traz uma restrição ou negação
    explícita, que nenhuma URL desfaz."""
    cru = str(licenca or "")
    t = _termos(cru)
    if not t and "©" not in cru:
        return None, None, False
    m = _RE_VERSAO.search(t)
    versao = m.group(1) if m else None
    if _M_RESERVADO.search(t):
        return "todos-os-direitos", None, True
    if _M_NEGA_PD.search(t):
        return "desconhecida", versao, True
    nucleo = re.sub(r"\s*\d\.\d.*$", "", t).split()
    so_codigo = bool(nucleo) and set(nucleo) <= {"cc", "by", "sa", "nc", "nd"} and "by" in nucleo      # códigos do Openverse: "by-sa"
    cc, by, sa, nc, nd = (bool(r.search(t)) for r in (_M_CC, _M_BY, _M_SA, _M_NC, _M_ND))
    if nc or nd:
        if cc or by:
            return "cc-by" + ("-nc" if nc else "") + ("-nd" if nd else "-sa" if sa else ""), versao, True
        return "restrita", versao, True
    if _M_RESTRITA.search(t):
        return "restrita", versao, True
    if so_codigo:                                        # o que vem DEPOIS da versão também é lido: «CC BY 3.0 de» entra, «CC BY 3.0 xyz» não
        sobra = [tk for tk in t.split() if not _termo_conhecido(tk)]
        if sobra:
            return "desconhecida", versao, any(len(tk) <= 2 for tk in sobra)
        return "cc-by" + ("-sa" if "sa" in nucleo else ""), versao, False
    m = _M_PEXELS.fullmatch(t)                           # só quando o texto INTEIRO é a licença do banco, nunca por menção
    if m:
        return m.group(1), None, False
    if re.search(r"\bcc ?0\b|\bcc zero\b", t):
        return "cc0", versao or "1.0", False
    if re.search(r"\bpdm\b|public domain mark", t):
        return "pdm", versao or "1.0", False
    if re.search(r"public domain|dominio publico|^pd\b|no known copyright|no restrictions|sem restricoes", t):
        if _M_PD_PARCIAL.search(t):                      # «public domain in the US only; copyrighted elsewhere»: não é domínio público aqui
            return "desconhecida", versao, True
        return "pd", None, False
    if _M_NASA.fullmatch(t):
        return "nasa", None, False
    if cc and by:
        sobra = [tk for tk in t.split() if not _termo_conhecido(tk)]
        if sobra:                                        # leitura fechada: o que não foi reconhecido não vira «CC BY» por omissão;
            return "desconhecida", versao, any(len(tk) <= 2 for tk in sobra)     # resto curto pode ser pedaço de NC/ND: nem a URL desfaz
        return "cc-by" + ("-sa" if sa else ""), versao, False
    if "©" in cru or "(c)" in cru.lower() or re.match(r"copyright\b", t):
        return "todos-os-direitos", None, True
    return "desconhecida", versao, False


def _identificar(licenca=None, url=None, fonte=None) -> tuple[str, str | None, str | None]:
    """(id, versão, divergência). Texto e URL são lidos separados; se discordam, vale a leitura mais restritiva e a
    divergência volta descrita (para o aviso). Texto que não diz nada deixa a URL decidir; sem os dois, a fonte."""
    id_u, v_u = _licenca_pela_url(url)
    id_t, v_t, veto = _licenca_pelo_texto(licenca)
    if id_t is None and id_u is None:
        return ({"pexels": "pexels", "pixabay": "pixabay", "nasa": "nasa"}.get(fonte) or "desconhecida"), None, None
    if id_u is None:
        return id_t, v_t, None
    if id_t is None or id_t == id_u or (id_t == "desconhecida" and not veto):
        return id_u, v_u or (v_t if id_t == id_u else None), None
    if _RIGOR[id_t] == _RIGOR[id_u] and _RIGOR[id_t] < 5:   # "Public domain" + URL da marca de domínio público: a URL só é mais precisa
        return id_u, v_u, None
    if id_t.startswith("cc-by") and id_u.startswith("cc-by"):
        partes = set(id_t.split("-")[2:]) | set(id_u.split("-")[2:])
        final = "cc-by" + ("-nc" if "nc" in partes else "") + ("-nd" if "nd" in partes else "-sa" if "sa" in partes else "")
    else:
        final = max((id_t, id_u), key=_RIGOR.__getitem__)
    versao = v_u if final == id_u else v_t if final == id_t else (v_t or v_u)
    return final, versao, (f"o texto da licença diz «{LICENCAS[id_t]['nome']}» e a URL diz «{LICENCAS[id_u]['nome']}»: "
                           f"valeu a leitura mais restritiva ({LICENCAS[final]['nome']})")


def identificar_licenca(licenca: str | None = None, url: str | None = None, fonte: str | None = None) -> tuple[str, str | None]:
    """(id da política, versão ou None) a partir do texto da licença, da URL dela e da fonte. Não sabe → 'desconhecida'."""
    return _identificar(licenca, url, fonte)[:2]


def avaliar_licenca(licenca: str | None = None, url: str | None = None, fonte: str | None = None) -> dict:
    """Ficha da política para uma licença: {id, versao, nome, url, permitida, exige_atribuicao, uso_comercial,
    permite_derivados, compartilha_igual, risco, motivo, divergencia}. `nome` já vem com a versão ("CC BY-SA 3.0");
    `divergencia` (texto ou None) diz quando o texto e a URL recebidos não contavam a mesma história."""
    lid, versao, divergencia = _identificar(licenca, url, fonte)
    ficha = dict(LICENCAS[lid], id=lid, versao=versao, divergencia=divergencia)
    url_confere = bool(url) and _licenca_pela_url(url)[0] == lid
    if lid.startswith("cc-by"):
        v = versao or "4.0"
        ficha["nome"] = f"{LICENCAS[lid]['nome']} {v}"
        ficha["url"] = (str(url).split("?")[0] if url_confere else f"{_CC}{lid[3:]}/{v}/").replace("http://", "https://")
    elif url and not divergencia and lid in ("pd", "desconhecida", "todos-os-direitos", "restrita"):
        ficha["url"] = str(url)
    return ficha


# ───────────────────────────────────────────────────────────── textos de crédito ──
def _limpo(v) -> str:
    """Texto de uma linha só: sem quebras e sem caractere de controle ou de formatação (ESC, BOM, inversor de direção) —
    título e autor vêm de API de terceiros e vão para o terminal, para o registro e para a descrição do vídeo."""
    return " ".join("".join(" " if unicodedata.category(ch)[0] == "C" else ch for ch in str(v or "")).split())


def e_material_proprio(texto) -> bool:
    """O texto de licença só diz que o material é da casa («Material próprio», «own work»)?"""
    return bool(_M_PROPRIO.fullmatch(" ".join(_sem_acento(_limpo(texto)).lower().split())))


def de_fora(item: dict) -> bool:
    """O item veio de algum lugar que não o disco do usuário (fonte ≠ "local", ou tem página ou endereço de arquivo)?
    É o que faz base_legal "proprio" pedir `notas` e aparecer em «Atenção antes de publicar»."""
    return item.get("fonte") not in (None, "local") or bool(item.get("pagina_url")) or bool(item.get("arquivo_url"))


def montar_atribuicao(item: dict) -> str:
    """Texto pronto para a descrição do vídeo, conforme a licença e a base legal do item."""
    titulo, autor = _limpo(item.get("titulo")), _limpo(item.get("autor"))
    pagina = _limpo(item.get("pagina_url"))
    fonte = NOMES_FONTE.get(item.get("fonte"), _limpo(item.get("fonte")) or "web")
    base = item.get("base_legal") or "licenca"
    lid = item.get("licenca_id") or identificar_licenca(item.get("licenca"), item.get("licenca_url"), item.get("fonte"))[0]
    obra = f"«{titulo}»" if titulo else "Material"
    de = f", de {autor}" if autor else ""
    onde = f": {pagina}" if pagina else ""
    if base == "proprio":
        return ""
    if base == "citacao":
        return f"Trecho de {obra}{de}, usado como citação{onde}"
    if base == "autorizacao":
        return f"{obra}{de}, usado com autorização{onde}"
    if lid == "nasa":
        return f"{obra} — NASA{(' / ' + autor) if autor and 'nasa' not in autor.lower() else ''}{onde}"
    if lid in ("pexels", "pixabay"):
        tipo = "Imagem" if item.get("tipo") == "imagem" else "Vídeo"
        return f"{tipo} de {autor or 'autor não informado'} no {fonte}{onde}"
    if lid in ("cc0", "pdm", "pd"):
        return f"{obra}{de} — {_limpo(item.get('licenca')) or LICENCAS[lid]['nome']}, via {fonte}{onde}"
    lic, lurl = _limpo(item.get("licenca")) or "licença não informada", _limpo(item.get("licenca_url"))
    return f"{obra}{de} — {lic}{(' (' + lurl + ')') if lurl else ''}, via {fonte}{onde} (adaptado: recorte e cor)"


def credito_curto(item: dict, maximo: int = 44) -> str:
    """Crédito para a TELA (rótulo da moldura): curto, sem URL. Ex.: "NASA", "Fulano · CC BY-SA 4.0", "Fulano / Pexels"."""
    autor = _limpo(item.get("autor"))
    lid = item.get("licenca_id") or identificar_licenca(item.get("licenca"), item.get("licenca_url"), item.get("fonte"))[0]
    fonte = NOMES_FONTE.get(item.get("fonte"), "")
    base = item.get("base_legal") or "licenca"
    if base == "proprio":
        return ""
    if base in ("citacao", "autorizacao"):
        texto = " · ".join(x for x in (autor, fonte if item.get("fonte") in ("youtube",) else "") if x) or _limpo(item.get("titulo"))
    elif lid == "nasa":
        texto = "NASA" if not autor or "nasa" in autor.lower() else f"NASA / {autor}"
    elif lid in ("pexels", "pixabay"):
        texto = f"{autor} / {fonte}" if autor else fonte
    elif lid in ("cc0", "pdm", "pd"):
        texto = autor or fonte
    else:
        texto = " · ".join(x for x in (autor, _limpo(item.get("licenca"))) if x)
    if len(texto) > maximo:                                   # corta o autor, nunca a licença
        cauda = texto[len(autor):] if autor and texto.startswith(autor) else ""
        espaco = max(8, maximo - len(cauda) - 1)
        texto = (autor[:espaco].rstrip(" ,.-") + "…" + cauda) if cauda else texto[:maximo - 1].rstrip() + "…"
    return texto


# ───────────────────────────────────────────────────────────────── arquivo e trava ──
def agora_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def raiz(projeto) -> Path:
    p = Path(str(projeto)).expanduser()
    if not p.is_dir():
        raise RegistroErro(f"a pasta do projeto não existe: {p}", "Passe a raiz do projeto (a pasta que tem broll/ e da/).", SAIDA_SEM_PROJETO)
    return p.resolve()


def achar_projeto(de=None) -> Path:
    """Sobe as pastas a partir de `de` (ou do cwd) até a que tem broll/licencas.json, da/da.json ou broll/."""
    inicio = Path(str(de)).expanduser().resolve() if de else Path.cwd().resolve()
    for p in (inicio, *inicio.parents):
        if (p / ARQUIVO).is_file() or (p / "da" / "da.json").is_file():
            return p
    for p in (inicio, *inicio.parents):
        if (p / "broll").is_dir():
            return p
    raise RegistroErro(f"não achei um projeto de vídeo a partir de {inicio} (nenhuma pasta acima tem da/da.json nem broll/).",
                       "Rode de dentro do projeto ou passe --projeto \"<pasta>\".", SAIDA_SEM_PROJETO)


@contextlib.contextmanager
def _travado(projeto: Path, espera: float = 30.0):
    """Trava exclusiva do registro (flock): uma gravação por vez, de qualquer processo ou skill."""
    (projeto / "broll").mkdir(parents=True, exist_ok=True)
    fd = os.open(str(projeto / TRAVA), os.O_RDWR | os.O_CREAT, 0o644)
    try:
        limite = time.monotonic() + espera
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= limite:
                    raise RegistroErro(f"o registro de licenças está em uso por outro processo há mais de {int(espera)} s ({projeto / TRAVA}).",
                                       "Espere a outra gravação terminar e rode de novo. A trava é do processo: apagar o arquivo não libera nada.")
                time.sleep(0.05)
        yield
    finally:
        with contextlib.suppress(OSError):
            fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _ler(projeto: Path) -> dict:
    arq = projeto / ARQUIVO
    if not arq.is_file():
        return {"versao": VERSAO, "itens": []}
    try:
        dados = json.loads(arq.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as e:
        raise RegistroErro(f"{arq}: JSON inválido na linha {e.lineno}, coluna {e.colno} ({e.msg}).",
                           "Conserte o arquivo à mão (vírgula sobrando é a causa comum) ou restaure a cópia licencas.json.bak ao lado.")
    if not isinstance(dados, dict) or not isinstance(dados.get("itens"), list):
        raise RegistroErro(f"{arq} não tem o formato do contrato ({{\"versao\": 1, \"itens\": [...]}}).",
                           "Restaure a cópia licencas.json.bak ao lado ou recrie o registro.")
    dados.setdefault("versao", VERSAO)
    return dados


def _gravar_texto(arq: Path, texto: str) -> None:
    arq.parent.mkdir(parents=True, exist_ok=True)
    tmp = arq.with_name(f"{arq.name}.{os.getpid()}.parcial")
    try:
        tmp.write_text(texto, encoding="utf-8")
        os.replace(tmp, arq)
    finally:
        with contextlib.suppress(OSError):
            tmp.unlink()


def _gravar(projeto: Path, dados: dict) -> None:
    arq = projeto / ARQUIVO
    if arq.is_file():
        with contextlib.suppress(OSError):
            shutil.copy2(arq, arq.with_name(arq.name + ".bak"))   # uma cópia da versão anterior, sempre
    dados["versao"] = VERSAO
    dados["atualizado_em"] = agora_iso()
    _gravar_texto(arq, json.dumps(dados, ensure_ascii=False, indent=2) + "\n")
    _gravar_texto(projeto / CREDITOS, _texto_creditos(projeto, dados))


def carregar(projeto) -> dict:
    """O registro inteiro: {"versao": 1, "itens": [...]} (lista vazia se o arquivo ainda não existe)."""
    return _ler(raiz(projeto))


def obter(projeto, id_: str) -> dict:
    for item in carregar(projeto)["itens"]:
        if item.get("id") == id_:
            return item
    raise RegistroErro(f"não há item {id_!r} em {ARQUIVO}.", "Veja os ids com: registro.py listar")


def procurar(projeto, **criterios) -> list[dict]:
    """Itens cujos campos batem com TODOS os critérios (ex.: procurar(p, sha256="…") ou procurar(p, pagina_url="…"))."""
    return [i for i in carregar(projeto)["itens"] if all(i.get(k) == v for k, v in criterios.items())]


def _proximo(dados: dict, prefixo: str) -> str:
    if prefixo not in PREFIXOS:
        raise RegistroErro(f"prefixo de id {prefixo!r} inválido.", "Use B (banco de mídia), Y (YouTube) ou W (imagem/captura da web).", SAIDA_USO)
    ids = [i.get("id") for i in dados["itens"]] + list(dados.get("ids_removidos") or [])       # id de item removido não volta a ser usado
    usados = [int(m.group(1)) for i in ids if (m := re.fullmatch(rf"{prefixo}(\d+)", str(i or "")))]
    return f"{prefixo}{(max(usados) + 1 if usados else 1):03d}"


def proximo_id(projeto, prefixo: str = "B") -> str:
    """Próximo id livre para o prefixo (só consulta: quem reserva o id é `adicionar`, sob a trava)."""
    return _proximo(carregar(projeto), prefixo)


# ───────────────────────────────────────────────────────────────────── validação ──
_URL = re.compile(r"^https?://\S+$", re.I)
_RE_EXTENSAO = re.compile(r"\.[a-z0-9]{1,5}")
_CAMPOS_URL = ("pagina_url", "arquivo_url", "autor_url", "licenca_url")
_PADROES = {"consulta": None, "pedido_id": None, "pagina_url": None, "arquivo_url": None, "autor": None, "autor_url": None,
            "licenca_url": None, "baixado_em": None, "arquivo": None, "sha256": None, "largura": None, "altura": None,
            "fps": None, "duracao": None, "trecho": None}


def _relativo(projeto: Path, caminho) -> str:
    p = Path(str(caminho)).expanduser()
    absoluto = p if p.is_absolute() else projeto / p
    try:
        return absoluto.resolve().relative_to(projeto).as_posix()
    except ValueError:
        raise RegistroErro(f"o caminho {caminho} fica fora do projeto ({projeto}).",
                           "O registro só guarda caminhos relativos à raiz do projeto: copie o arquivo para broll/bruto/.")


def _dentro_de(projeto: Path, relativo: str, pasta: Path) -> bool:
    """O caminho (relativo à raiz, já resolvido) fica DENTRO de `pasta` do projeto — e não é a própria pasta?"""
    alvo, base = (projeto / relativo).resolve(), (projeto / pasta).resolve()
    return base in alvo.parents


def _normalizar(projeto: Path, item: dict) -> tuple[dict, list[str]]:
    """Completa e valida um item. Devolve (item pronto, avisos); levanta RegistroErro com todos os problemas."""
    it = copy.deepcopy(item)
    erros, avisos = [], []
    for k, v in _PADROES.items():
        it.setdefault(k, v)
    if it.get("fonte") not in FONTES:
        erros.append(f"fonte {it.get('fonte')!r} inválida (use {', '.join(FONTES)})")
    base = it.setdefault("base_legal", "licenca")
    if base not in BASES_LEGAIS:
        erros.append(f"base_legal {base!r} inválida (use {', '.join(BASES_LEGAIS)})")
    for k in _CAMPOS_URL:
        if it.get(k) and not _URL.match(str(it[k])):
            erros.append(f"{k} não é um endereço http(s): {it[k]!r}")
    for k in ("titulo", "autor", "consulta", "licenca", "credito_tela"):      # texto de terceiros: uma linha, sem controle
        if isinstance(it.get(k), str):
            it[k] = _limpo(it[k]) or None
    recebida, url_recebida = _limpo(it.get("licenca")), it.get("licenca_url")
    ficha = avaliar_licenca(it.get("licenca"), it.get("licenca_url"), it.get("fonte"))
    if base == "proprio" and ((recebida and not e_material_proprio(recebida)) or url_recebida) and not ficha["permitida"]:
        erros.append(f"base_legal 'proprio' não convive com licença de terceiro que a política recusa ({recebida or url_recebida}: "
                     f"{ficha['nome']}). Se o material é mesmo da casa, apague `licenca` e `licenca_url` (vira «Material próprio») e diga "
                     "em `notas` de onde ele veio; se é de outra pessoa, a base legal é 'citacao' ou 'autorizacao', com `notas`")
    if base == "proprio" and not it.get("licenca"):
        it["licenca"] = "Material próprio"
    elif base in ("citacao", "autorizacao") and not it.get("licenca"):
        it["licenca"] = "Todos os direitos reservados"
        ficha = avaliar_licenca(it["licenca"])
    elif ficha["id"] != "desconhecida" and (not it.get("licenca") or ficha["id"].startswith("cc")):
        it["licenca"] = ficha["nome"]
    if recebida and recebida != it["licenca"] and not it.get("licenca_original"):
        it["licenca_original"] = recebida                 # o texto como chegou nunca se perde quando o nome é regravado
    it["licenca_id"] = ficha["id"]
    if ficha.get("divergencia"):                          # a URL que contradiz o texto não fica como se fosse a da licença
        avisos.append(ficha["divergencia"] + " — confira na página de origem")
        if url_recebida and url_recebida != ficha.get("url") and not it.get("licenca_url_original"):
            it["licenca_url_original"] = url_recebida
        it["licenca_url"] = ficha.get("url")
    elif not it.get("licenca_url") and ficha.get("url"):
        it["licenca_url"] = ficha["url"]
    notas = _limpo(it.get("notas"))
    if base == "licenca":
        if not ficha["permitida"]:
            erros.append(f"licença recusada pela política: {it.get('licenca') or 'não informada'} — {ficha['motivo']}. "
                         "Só entra como exceção: base_legal 'citacao' ou 'autorizacao' e `notas` dizendo por quê")
    elif base in ("citacao", "autorizacao") and not notas:
        erros.append(f"base_legal '{base}' é exceção à política e exige `notas` (o que é citado e por quê, ou quem autorizou e onde está a prova)")
    elif base == "proprio" and de_fora(it) and not notas:
        origem = NOMES_FONTE.get(it.get("fonte"), "outro lugar") if it.get("fonte") != "local" else (it.get("pagina_url") or it.get("arquivo_url"))
        erros.append(f"base_legal 'proprio' para material que veio de {origem} exige `notas` dizendo por que ele é da casa (canal próprio, "
                     "arquivo da equipe publicado ali): sem isso, material de terceiro entraria sem crédito e com risco baixo")
    it["notas"] = notas
    # bools e risco: o que o chamador informou vale; o que faltou vem da política
    padrao_atr = {"licenca": ficha["exige_atribuicao"], "citacao": True, "autorizacao": True, "proprio": False}[base if base in BASES_LEGAIS else "licenca"]
    padrao_com = {"licenca": ficha["uso_comercial"], "citacao": False, "autorizacao": False, "proprio": True}[base if base in BASES_LEGAIS else "licenca"]
    padrao_risco = {"licenca": ficha["risco"], "citacao": "medio", "autorizacao": "baixo", "proprio": "baixo"}[base if base in BASES_LEGAIS else "licenca"]
    for campo, padrao in (("exige_atribuicao", padrao_atr), ("uso_comercial", padrao_com)):
        if it.get(campo) is None:
            it[campo] = padrao
        elif not isinstance(it[campo], bool):
            erros.append(f"{campo} precisa ser true ou false (veio {it[campo]!r})")
    if base == "licenca" and ficha["permitida"] and ficha["exige_atribuicao"] and it.get("exige_atribuicao") is False:
        erros.append(f"{ficha['nome']} exige atribuição: exige_atribuicao não pode ser false")
    if base == "licenca" and ficha["permitida"] and not ficha["uso_comercial"] and it.get("uso_comercial") is True:
        erros.append(f"{ficha['nome']} não permite uso comercial: uso_comercial não pode ser true")
    if it.get("risco") is None:
        it["risco"] = padrao_risco
    if it["risco"] not in RISCOS:
        erros.append(f"risco {it['risco']!r} inválido (use {', '.join(RISCOS)})")
    if not _limpo(it.get("atribuicao")):
        it["atribuicao"] = montar_atribuicao(it)
    it["atribuicao"] = _limpo(it["atribuicao"])
    if it.get("exige_atribuicao") is True and not it["atribuicao"]:
        erros.append("exige_atribuicao é true mas não há texto em `atribuicao` (informe autor, título e pagina_url)")
    if not _limpo(it.get("credito_tela")):
        it["credito_tela"] = credito_curto(it)
    if it.get("arquivo"):
        it["arquivo"] = _relativo(projeto, it["arquivo"])
        if not _dentro_de(projeto, it["arquivo"], PASTA_BRUTO):
            erros.append(f"arquivo precisa ficar dentro de {PASTA_BRUTO.as_posix()}/ (veio {it['arquivo']!r}): copie o material para lá "
                         "ou registre com adicionar --de-arquivo")
    for campo, de_que in (("trecho", "da FONTE (o vídeo original)"), ("trecho_arquivo", "do ARQUIVO baixado")):
        tr = it.get(campo)
        if tr is None:
            if campo != "trecho":
                it.pop(campo, None)
            continue
        try:
            t0, t1 = float(tr["t0"]), float(tr["t1"])
            if t0 < 0 or t1 <= t0:
                raise ValueError
            it[campo] = {"t0": round(t0, 3), "t1": round(t1, 3)}
        except (TypeError, KeyError, ValueError):
            erros.append(f"{campo} precisa ser null ou {{\"t0\": s, \"t1\": s}} com 0 ≤ t0 < t1, em segundos {de_que} (veio {tr!r})")
    for campo in ("tratados", "usado_em"):
        v = it.get(campo)
        if v is None:
            it[campo] = []
        elif not isinstance(v, list) or not all(isinstance(x, str) and x.strip() for x in v):
            erros.append(f"{campo} precisa ser uma lista de textos (veio {v!r})")
    if isinstance(it.get("tratados"), list) and not erros:
        it["tratados"] = sorted(dict.fromkeys(_relativo(projeto, t) for t in it["tratados"]))
    for campo in ("largura", "altura"):
        if it.get(campo) is not None and (not isinstance(it[campo], int) or it[campo] <= 0):
            erros.append(f"{campo} precisa ser inteiro positivo ou null (veio {it[campo]!r})")
    for campo in ("fps", "duracao"):
        if it.get(campo) is not None and (isinstance(it[campo], bool) or not isinstance(it[campo], (int, float)) or it[campo] < 0):
            erros.append(f"{campo} precisa ser número ≥ 0 ou null (veio {it[campo]!r})")
    if ficha["id"] == "cc-by-sa" and base == "licenca":
        avisos.append("CC BY-SA: se o vídeo contar como adaptação do material, ele herda a licença — leia references/licencas.md antes de usar em peça patrocinada")
    if it.get("uso_comercial") is False:
        avisos.append("sem uso comercial: não entra em canal monetizado nem em peça patrocinada")
    if base == "proprio" and de_fora(it):
        avisos.append(f"declarado como material próprio, mas veio de {NOMES_FONTE.get(it.get('fonte'), 'outro lugar') if it.get('fonte') != 'local' else 'uma página da web'}: "
                      "entra sem crédito e com risco baixo só pela palavra de quem registrou — confira a nota antes de publicar")
    if erros:
        quem = it.get("id") or it.get("pagina_url") or it.get("arquivo") or "item"
        raise RegistroErro(f"{quem}: " + "; ".join(erros) + ".", "Corrija os campos e grave de novo. Política: registro.py politica")
    return it, avisos


_ORDEM = ("id", "tipo", "titulo", "consulta", "pedido_id", "fonte", "id_fonte", "pagina_url", "arquivo_url", "autor", "autor_url", "licenca",
          "licenca_id", "licenca_original", "licenca_url", "licenca_url_original", "base_legal", "risco", "exige_atribuicao", "atribuicao",
          "credito_tela", "uso_comercial", "baixado_em", "arquivo", "sha256", "bytes", "largura", "altura", "fps", "duracao", "trecho",
          "trecho_arquivo", "tratados", "usado_em", "notas")


def _ordenado(item: dict) -> dict:
    return {**{k: item[k] for k in _ORDEM if k in item}, **{k: v for k, v in item.items() if k not in _ORDEM}}


def adicionar(projeto, item: dict, mover_de=None, extensao: str | None = None) -> str:
    """Valida o item, aplica a política de licenças, reserva o id e grava. Devolve o id.

    item["id"] ausente → o próximo livre do prefixo: item["prefixo"] ("B", "Y", "W") ou, sem ele, Y para fonte youtube,
    W para fonte web e B para o resto. `mover_de` = arquivo recém-baixado (nome provisório): sob a mesma trava ele é
    renomeado para broll/bruto/<id><extensao> e vira item["arquivo"] — dois downloads simultâneos nunca disputam o nome."""
    projeto = raiz(projeto)
    item = dict(item)
    prefixo = item.pop("prefixo", None) or {"youtube": "Y", "web": "W"}.get(item.get("fonte"), "B")
    with _travado(projeto):
        dados = _ler(projeto)
        ids = {i.get("id") for i in dados["itens"]} | set(dados.get("ids_removidos") or [])
        if item.get("id"):
            if not re.fullmatch(r"[BYW]\d{3,}", str(item["id"])):
                raise RegistroErro(f"id {item['id']!r} fora do padrão.", "Use B001 (banco), Y001 (YouTube) ou W001 (web) — ou omita o id.", SAIDA_USO)
            if item["id"] in ids:
                raise RegistroErro(f"o id {item['id']} já foi usado neste registro (item existente ou removido).",
                                   "Omita o id para receber o próximo livre, ou use atualizar().")
        else:
            item["id"] = _proximo(dados, prefixo)
        destino = None
        if mover_de is not None:
            origem = Path(str(mover_de)).expanduser()
            if not origem.is_file():
                raise RegistroErro(f"arquivo a registrar não encontrado: {origem}")
            ext = str(extensao if extensao is not None else origem.suffix).lower()
            if not _RE_EXTENSAO.fullmatch(ext):               # a extensão pode ter vindo de uma API: nunca vira pedaço de caminho
                raise RegistroErro(f"extensão de arquivo inválida: {ext[:24]!r}.",
                                   "Use uma extensão simples (.mp4, .webm, .mov, .jpg, .png…); se o arquivo não tem, renomeie antes de registrar.", SAIDA_USO)
            destino = projeto / PASTA_BRUTO / f"{item['id']}{ext}"
            if destino.parent.resolve() != (projeto / PASTA_BRUTO).resolve():
                raise RegistroErro(f"o destino {destino} sairia de {PASTA_BRUTO.as_posix()}/.", "Confira se broll/bruto não é um atalho para outro lugar.")
            if destino.exists():
                raise RegistroErro(f"{destino} já existe e não pertence a nenhum item do registro.", "Mova ou renomeie o arquivo e rode de novo.")
            item["arquivo"] = destino.relative_to(projeto).as_posix()
        pronto, _avisos = _normalizar(projeto, item)
        if destino is not None:
            (projeto / PASTA_BRUTO).mkdir(parents=True, exist_ok=True)
            os.replace(origem, destino)
        dados["itens"].append(_ordenado(pronto))
        _gravar(projeto, dados)
    return pronto["id"]


def atualizar(projeto, id_: str | None = None, /, **campos) -> dict:
    """Troca campos de um item (valida de novo, com a política). Devolve o item gravado. `id` não muda.

    atualizar(projeto, "B004", risco="medio") ou atualizar(projeto, id="B004", risco="medio"). Quando `licenca`,
    `licenca_url` ou `base_legal` mudam, `exige_atribuicao`, `uso_comercial` e `risco` que não vieram na mesma chamada
    são recalculados pela política (um item de domínio público corrigido para CC BY-SA passa a exigir crédito); passar
    um deles como None pede o mesmo recálculo. Os textos `atribuicao` e `credito_tela` são refeitos junto."""
    projeto = raiz(projeto)
    if id_ is None:
        id_ = campos.pop("id", None) or campos.pop("id_", None)
    if not id_:
        raise RegistroErro("atualizar: faltou o id do item.", "Ex.: registro.atualizar(projeto, \"B001\", risco=\"medio\").", SAIDA_USO)
    if "id" in campos and campos["id"] != id_:
        raise RegistroErro("o id de um item não muda.", "Registre outro item se for outro material.", SAIDA_USO)
    with _travado(projeto):
        dados = _ler(projeto)
        for n, atual in enumerate(dados["itens"]):
            if atual.get("id") == id_:
                novo = {**atual, **campos}
                for derivado in ("atribuicao", "credito_tela"):      # texto derivado é refeito quando muda o que o gera
                    if derivado not in campos and any(k in campos for k in ("autor", "titulo", "licenca", "licenca_url", "pagina_url", "base_legal", "fonte")):
                        novo[derivado] = ""
                if any(k in campos for k in ("licenca", "licenca_url", "base_legal")):
                    for sinal in ("exige_atribuicao", "uso_comercial", "risco"):     # o que valia para a licença antiga não vale para a nova
                        if sinal not in campos:
                            novo[sinal] = None
                    if "licenca" in campos:
                        novo.pop("licenca_original", None)
                    if "licenca_url" in campos:
                        novo.pop("licenca_url_original", None)
                pronto, _ = _normalizar(projeto, novo)
                dados["itens"][n] = _ordenado(pronto)
                _gravar(projeto, dados)
                return dados["itens"][n]
    raise RegistroErro(f"não há item {id_!r} em {ARQUIVO}.", "Veja os ids com: registro.py listar")


def _mexer_lista(projeto, id_: str, campo: str, valor: str, remover: bool = False) -> list:
    projeto = raiz(projeto)
    valor = str(valor or "").strip()
    if not id_ or not valor:
        raise RegistroErro(f"{campo}: faltou o id do item ou o valor.", "Ex.: registro.marcar_uso(projeto, \"B001\", \"C03\").", SAIDA_USO)
    with _travado(projeto):
        dados = _ler(projeto)
        for item in dados["itens"]:
            if item.get("id") == id_:
                lista = [x for x in (item.get(campo) or []) if x != valor]
                if not remover:
                    lista.append(valor)
                if campo == "tratados":                       # ordem estável no arquivo, qualquer que seja a ordem de tratamento
                    lista = sorted(lista)
                item[campo] = lista
                _gravar(projeto, dados)
                return lista
    raise RegistroErro(f"não há item {id_!r} em {ARQUIVO}.", "Veja os ids com: registro.py listar")


def marcar_uso(projeto, id_: str | None = None, onde: str | None = None, *, id: str | None = None) -> list:
    """Acrescenta `onde` (id de cena do storyboard, "C03"; ou de corte, "K01") a usado_em. Idempotente. Devolve a lista.
    marcar_uso(projeto, "B004", "C03") ou marcar_uso(projeto, id="B004", onde="C03")."""
    return _mexer_lista(projeto, id_ or id, "usado_em", onde)


def desmarcar_uso(projeto, id_: str | None = None, onde: str | None = None, *, id: str | None = None) -> list:
    return _mexer_lista(projeto, id_ or id, "usado_em", onde, remover=True)


def registrar_tratado(projeto, id_: str, caminho) -> list:
    """Acrescenta um arquivo de broll/tratado/ à lista `tratados` do item. O trecho usado em cada peça fica no carimbo
    dela: `trecho` no registro é o intervalo da FONTE e nunca é regravado pelo tratamento."""
    projeto = raiz(projeto)
    return _mexer_lista(projeto, id_, "tratados", _relativo(projeto, caminho))


def remover(projeto, id_: str, com_arquivos: bool = False) -> dict:
    """Tira um item do registro e devolve o item removido. Recusa enquanto houver `usado_em` (o crédito de uma cena não
    some por engano: desmarque o uso antes). Com `com_arquivos`, o bruto, os tratados e os carimbos deles vão para
    broll/_removidos/<id>/ — nada é apagado; sem isso, os arquivos ficam onde estão, fora do registro."""
    projeto = raiz(projeto)
    with _travado(projeto):
        dados = _ler(projeto)
        for n, item in enumerate(dados["itens"]):
            if item.get("id") != id_:
                continue
            if item.get("usado_em"):
                raise RegistroErro(f"{id_} está marcado como usado em {', '.join(item['usado_em'])}: não foi removido.",
                                   f"Se o material saiu mesmo dessas cenas: registro.py desmarcar-uso {id_} {' '.join(item['usado_em'])} — e remova de novo.")
            movidos = []
            if com_arquivos:
                lixo = projeto / "broll" / "_removidos" / id_
                candidatos = [(item.get("arquivo"), PASTA_BRUTO), *((t, PASTA_TRATADO) for t in item.get("tratados") or [])]
                for rel, pasta in candidatos:
                    if not rel or not _dentro_de(projeto, rel, pasta):
                        continue                              # só mexe no que é comprovadamente deste registro
                    for arq in (projeto / rel, projeto / (rel + ".da.json")):
                        if arq.is_file():
                            lixo.mkdir(parents=True, exist_ok=True)
                            destino = lixo / arq.name
                            k = 1
                            while destino.exists():
                                destino = lixo / f"{arq.stem}.{k}{arq.suffix}"
                                k += 1
                            os.replace(arq, destino)
                            movidos.append(destino.relative_to(projeto).as_posix())
            del dados["itens"][n]
            dados["ids_removidos"] = sorted({*(dados.get("ids_removidos") or []), id_})
            _gravar(projeto, dados)
            return {**item, "movidos": movidos}
    raise RegistroErro(f"não há item {id_!r} em {ARQUIVO}.", "Veja os ids com: registro.py listar")


def sincronizar_uso(projeto) -> dict:
    """Lê roteiro/storyboard.json e marca em usado_em cada cena que aponta para um b-roll (campo `broll_id`).
    Devolve {'marcados': [(id, cena)], 'sem_registro': [(id, cena)], 'sobrando': [(id, cena)]} — `sobrando` = cena
    C## que está em usado_em mas o storyboard não liga mais ao item (não é apagada: use desmarcar_uso)."""
    projeto = raiz(projeto)
    arq = projeto / "roteiro" / "storyboard.json"
    if not arq.is_file():
        raise RegistroErro(f"não há {arq.relative_to(projeto)} neste projeto.", "O storyboard é da skill video-animacao-explicativa; sem ele, use marcar-uso à mão.")
    try:
        cenas = json.loads(arq.read_text(encoding="utf-8-sig")).get("cenas") or []
    except (json.JSONDecodeError, AttributeError) as e:
        raise RegistroErro(f"{arq}: não consegui ler o storyboard ({e}).")
    pares = [(str(c["broll_id"]), str(c.get("id"))) for c in cenas if isinstance(c, dict) and c.get("broll_id")]
    ids_cena = {str(c.get("id")) for c in cenas if isinstance(c, dict)}
    itens = {i.get("id"): i for i in carregar(projeto)["itens"]}
    res = {"marcados": [], "sem_registro": [], "sobrando": []}
    for bid, cena in pares:
        if bid not in itens:
            res["sem_registro"].append((bid, cena))
        elif cena not in (itens[bid].get("usado_em") or []):
            marcar_uso(projeto, bid, cena)
            res["marcados"].append((bid, cena))
    for bid, item in itens.items():
        for onde in item.get("usado_em") or []:
            if onde in ids_cena and (bid, onde) not in pares:
                res["sobrando"].append((bid, onde))
    return res


# ─────────────────────────────────────────────────────────────────────── créditos ──
def _texto_creditos(projeto: Path, dados: dict) -> str:
    itens = dados.get("itens") or []
    usados = [i for i in itens if i.get("usado_em")]
    alvo = usados if usados else itens
    obrig, cortesia = [], []
    for i in alvo:
        texto = _limpo(i.get("atribuicao"))
        if not texto:
            continue
        (obrig if i.get("exige_atribuicao") else cortesia).append(texto)
    obrig, cortesia = list(dict.fromkeys(obrig)), list(dict.fromkeys(cortesia))
    L = ["# Créditos de b-roll", "",
         f"Gerado por video-broll a partir de `{ARQUIVO.as_posix()}` em {agora_iso()[:10]}. Não edite: este arquivo é regravado a cada mudança no registro.",
         ("Lista só o material marcado em `usado_em`." if usados else
          "Nenhum item tem `usado_em` ainda: a lista abaixo traz TUDO o que foi registrado. Marque o uso (`registro.py marcar-uso` ou `sincronizar-uso`) antes de publicar."), ""]
    L += ["## Para a descrição — atribuição obrigatória", ""]
    L += [f"- {t}" for t in obrig] or ["(nenhum item exige crédito)"]
    L += ["", "## Cortesia — a licença não exige, mas o crédito é bem-vindo", ""]
    L += [f"- {t}" for t in cortesia] or ["(nenhum)"]
    def proprio_de_fora(i):
        return i.get("base_legal") == "proprio" and de_fora(i)

    alertas = [i for i in alvo if i.get("uso_comercial") is False or i.get("risco") in ("medio", "alto") or i.get("base_legal") in ("citacao", "autorizacao")
               or proprio_de_fora(i)]
    if alertas:
        L += ["", "## Atenção antes de publicar", ""]
        for i in alertas:
            motivos = []
            if i.get("base_legal") in ("citacao", "autorizacao"):
                motivos.append(f"base legal: {i['base_legal']}")
            if proprio_de_fora(i):
                motivos.append(f"declarado como material próprio, mas veio de {NOMES_FONTE.get(i.get('fonte'), 'outro lugar') if i.get('fonte') != 'local' else 'uma página da web'}"
                               " (sem crédito e sem licença de terceiro: confira que é mesmo da casa)")
            if i.get("uso_comercial") is False:
                motivos.append("sem uso comercial")
            if i.get("risco") in ("medio", "alto"):
                motivos.append(f"risco {i['risco']}")
            L.append(f"- {i.get('id')} ({i.get('licenca')}): {', '.join(motivos)}{(' — ' + i['notas']) if i.get('notas') else ''}")
    L += ["", "## Registro", "", "| id | fonte | licença | base legal | risco | crédito exigido | arquivo | usado em |", "|---|---|---|---|---|---|---|---|"]
    for i in itens:
        L.append(f"| {i.get('id')} | {i.get('fonte')} | {i.get('licenca')} | {i.get('base_legal')} | {i.get('risco')} | "
                 f"{'sim' if i.get('exige_atribuicao') else 'não'} | {i.get('arquivo') or '—'} | {', '.join(i.get('usado_em') or []) or '—'} |")
    return "\n".join(L) + "\n"


def creditos_md(projeto, gravar: bool = True) -> str:
    """Texto de broll/creditos.md (seção "Para a descrição" pronta para colar). Com gravar=True, regrava o arquivo."""
    projeto = raiz(projeto)
    if not gravar:
        return _texto_creditos(projeto, _ler(projeto))
    with _travado(projeto):
        texto = _texto_creditos(projeto, _ler(projeto))
        _gravar_texto(projeto / CREDITOS, texto)
    return texto


# ───────────────────────────────────────────────────────────── conferência geral ──
def sha256_arquivo(caminho) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def validar(projeto, conferir_sha: bool = False) -> dict:
    """Confere o registro inteiro: política, textos de crédito, arquivos no disco, tratados e ids repetidos.
    Devolve {'ok', 'erros': [...], 'avisos': [...], 'itens': n}."""
    projeto = raiz(projeto)
    dados = _ler(projeto)
    erros, avisos, vistos = [], [], set()
    for item in dados["itens"]:
        iid = item.get("id") or "(sem id)"
        if iid in vistos:
            erros.append(f"{iid}: id repetido")
        vistos.add(iid)
        if not re.fullmatch(r"[BYW]\d{3,}", str(iid)):
            erros.append(f"{iid}: id fora do padrão B001/Y001/W001")
        try:
            _, av = _normalizar(projeto, item)
            avisos += [f"{iid}: {a}" for a in av]
        except RegistroErro as e:
            erros.append(e.mensagem)
            continue
        arq = item.get("arquivo")
        if not arq:
            avisos.append(f"{iid}: sem arquivo (registrado mas não baixado)")
        elif not (projeto / arq).is_file():
            erros.append(f"{iid}: o arquivo {arq} não está no disco")
        elif conferir_sha and item.get("sha256") and sha256_arquivo(projeto / arq) != item["sha256"]:
            erros.append(f"{iid}: {arq} mudou depois do registro (sha256 diferente)")
        for t in item.get("tratados") or []:
            if not (projeto / t).is_file():
                avisos.append(f"{iid}: o tratado {t} não está no disco (rode tratar.py de novo ou tire da lista)")
        if item.get("usado_em") and not item.get("tratados"):
            avisos.append(f"{iid}: marcado como usado em {', '.join(item['usado_em'])} mas ainda não foi tratado na DA")
    return {"ok": not erros, "erros": erros, "avisos": avisos, "itens": len(dados["itens"])}


# ─────────────────────────────────────────────────────────────────────────── CLI ──
def _sondar(arquivo: Path) -> dict:
    """largura/altura/fps/duracao por ffprobe (leve); imagem → só largura/altura. Falha vira RegistroErro."""
    ffprobe = shutil.which("ffprobe") or "/opt/homebrew/bin/ffprobe"
    try:
        r = subprocess.run([ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries",
                            "stream=width,height,avg_frame_rate,duration,codec_name:format=duration,format_name", "-of", "json", str(arquivo)],
                           capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=60)
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        raise RegistroErro(f"não consegui rodar o ffprobe em {arquivo.name}: {e}", "Instale o ffmpeg (brew install ffmpeg).")
    try:
        dados = json.loads(r.stdout or "{}")
        s = dados["streams"][0]
    except (json.JSONDecodeError, KeyError, IndexError):
        raise RegistroErro(f"{arquivo.name} não é um vídeo nem uma imagem que o ffprobe leia.", (r.stderr or "").strip()[-200:] or None)
    num, _, den = str(s.get("avg_frame_rate") or "0/1").partition("/")
    try:
        fps = round(float(num) / float(den or 1), 3)
    except (ValueError, ZeroDivisionError):
        fps = 0.0
    try:
        dur = float(s.get("duration") or dados.get("format", {}).get("duration") or 0)
    except ValueError:
        dur = 0.0
    imagem = "image2" in str(dados.get("format", {}).get("format_name")) or "_pipe" in str(dados.get("format", {}).get("format_name")) or dur <= 0.05
    return {"largura": int(s.get("width") or 0) or None, "altura": int(s.get("height") or 0) or None,
            "fps": None if imagem else fps, "duracao": None if imagem else round(dur, 3), "tipo": "imagem" if imagem else "video"}


def registrar_arquivo(projeto, origem, **campos) -> str:
    """Copia um arquivo local para broll/bruto/ e o registra (material próprio, autorizado ou de fonte sem API).
    `campos` são os do contrato (fonte, base_legal, autor, titulo, licenca, pagina_url, notas…). Devolve o id."""
    projeto = raiz(projeto)
    origem = Path(str(origem)).expanduser()
    if not origem.is_file():
        raise RegistroErro(f"arquivo não encontrado: {origem}")
    info = _sondar(origem)
    tmp = projeto / PASTA_BRUTO / f"_entrando_{os.getpid()}_{origem.name}"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(origem, tmp)
    item = {"fonte": "local", "base_legal": "proprio", "titulo": origem.stem, "baixado_em": agora_iso(), "sha256": sha256_arquivo(tmp),
            "bytes": tmp.stat().st_size, **info, **{k: v for k, v in campos.items() if v is not None}}
    try:
        return adicionar(projeto, item, mover_de=tmp, extensao=origem.suffix)
    finally:
        with contextlib.suppress(OSError):
            tmp.unlink()


def _valor(texto: str):
    if texto.lower() in ("null", "none", "nulo"):
        return None
    if texto.lower() in ("true", "sim", "verdadeiro"):
        return True
    if texto.lower() in ("false", "nao", "não", "falso"):
        return False
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        return texto


def _cmd_listar(a, projeto):
    itens = carregar(projeto)["itens"]
    if a.json:
        print(json.dumps(itens, ensure_ascii=False, indent=2))
        return 0
    if not itens:
        print(f"Registro vazio ({projeto / ARQUIVO}). Baixe com baixar.py ou registre com: registro.py adicionar --de-arquivo …")
        return 0
    for i in itens:
        dims = f"{i.get('largura')}×{i.get('altura')}" if i.get("largura") else "?"
        dur = f"{i['duracao']:.1f} s".replace(".", ",") if i.get("duracao") else "imagem" if i.get("tipo") == "imagem" else "?"
        print(f"{i.get('id'):5} {i.get('fonte', '?'):9} {dims:>10} {dur:>8}  {i.get('licenca', '?')}"
              f"{' · crédito obrigatório' if i.get('exige_atribuicao') else ''}{' · SEM uso comercial' if i.get('uso_comercial') is False else ''}"
              f" · risco {i.get('risco')}")
        print(f"      {i.get('titulo') or i.get('consulta') or ''}  [{i.get('arquivo') or 'sem arquivo'}]")
        print(f"      tratados: {len(i.get('tratados') or [])} · usado em: {', '.join(i.get('usado_em') or []) or '—'}")
    return 0


def _cmd_mostrar(a, projeto):
    print(json.dumps(obter(projeto, a.id), ensure_ascii=False, indent=2))
    return 0


def _cmd_validar(a, projeto):
    r = validar(projeto, conferir_sha=a.sha)
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        for e in r["erros"]:
            print(f"  ✗ {e}")
        for v in r["avisos"]:
            print(f"  ! {v}")
        print(f"{r['itens']} item(ns): {len(r['erros'])} erro(s), {len(r['avisos'])} aviso(s).")
    return SAIDA_OK if r["ok"] else SAIDA_ERRO


def _cmd_creditos(a, projeto):
    texto = creditos_md(projeto, gravar=not a.sem_gravar)
    print(texto, end="")
    if not a.sem_gravar:
        print(f"\n→ gravado em {projeto / CREDITOS}", file=sys.stderr)
    return 0


def _cmd_marcar(a, projeto):
    fn = desmarcar_uso if a.cmd == "desmarcar-uso" else marcar_uso
    for onde in a.onde:
        lista = fn(projeto, a.id, onde)
    print(f"{a.id} usado em: {', '.join(lista) or '—'}")
    return 0


def _cmd_sincronizar(a, projeto):
    r = sincronizar_uso(projeto)
    for bid, cena in r["marcados"]:
        print(f"  + {bid} marcado em {cena}")
    for bid, cena in r["sem_registro"]:
        print(f"  ✗ a cena {cena} usa {bid}, que não está no registro: baixe/registre o material ou corrija o storyboard")
    for bid, cena in r["sobrando"]:
        print(f"  ! {bid} tem {cena} em usado_em, mas o storyboard não liga mais a cena a ele (registro.py desmarcar-uso {bid} {cena})")
    print(f"{len(r['marcados'])} marcado(s), {len(r['sem_registro'])} sem registro, {len(r['sobrando'])} sobrando.")
    return SAIDA_ERRO if r["sem_registro"] else SAIDA_OK


def _cmd_adicionar(a, projeto):
    campos = {}
    for par in a.campo or []:
        if "=" not in par:
            raise RegistroErro(f"--campo espera nome=valor (veio {par!r}).", codigo=SAIDA_USO)
        k, v = par.split("=", 1)
        campos[k.strip()] = _valor(v.strip())
    for k in ("fonte", "base_legal", "autor", "titulo", "licenca", "licenca_url", "pagina_url", "notas", "risco", "pedido_id"):
        v = getattr(a, k, None)
        if v is not None:
            campos[k] = v
    if a.de_arquivo:
        iid = registrar_arquivo(projeto, a.de_arquivo, **campos)
    elif a.json_item:
        try:
            bruto = sys.stdin.read() if a.json_item == "-" else Path(a.json_item).expanduser().read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError) as e:
            raise RegistroErro(f"--json: não consegui ler {a.json_item!r} ({getattr(e, 'strerror', None) or type(e).__name__}).",
                               "Passe o caminho de um arquivo .json em UTF-8 com o item, ou - para ler da entrada padrão.", SAIDA_USO)
        try:
            item = json.loads(bruto)
        except json.JSONDecodeError as e:
            raise RegistroErro(f"--json: JSON inválido ({e}).", codigo=SAIDA_USO)
        if not isinstance(item, dict):
            raise RegistroErro(f"--json: esperado UM item (objeto {{\"fonte\": …, \"licenca\": …}}), veio {type(item).__name__}.",
                               "Registre um item por vez; os campos estão no --help e no contrato de broll/licencas.json.", SAIDA_USO)
        iid = adicionar(projeto, {**item, **campos})
    else:
        raise RegistroErro("informe --de-arquivo ARQ (copia e registra um arquivo local) ou --json ARQ|- (item pronto).", codigo=SAIDA_USO)
    item = obter(projeto, iid)
    print(f"{iid} registrado: {item.get('arquivo') or 'sem arquivo'} · {item.get('licenca')} · base legal {item.get('base_legal')} · risco {item.get('risco')}")
    for aviso in _normalizar(projeto, item)[1]:
        print(f"  ! {aviso}")
    return 0


def _cmd_atualizar(a, projeto):
    campos = {}
    for par in a.pares:
        if "=" not in par:
            raise RegistroErro(f"esperado campo=valor (veio {par!r}).", "Ex.: registro.py atualizar B001 autor=\"Fulana\" risco=medio trecho='{\"t0\": 2, \"t1\": 6}'", SAIDA_USO)
        k, v = par.split("=", 1)
        campos[k.strip()] = _valor(v.strip())
    item = atualizar(projeto, a.id, **campos)
    print(json.dumps(item, ensure_ascii=False, indent=2))
    return 0


def _cmd_remover(a, projeto):
    item = remover(projeto, a.id, com_arquivos=a.com_arquivos)
    print(f"{a.id} removido do registro ({item.get('licenca')}; {item.get('arquivo') or 'sem arquivo'}).")
    if item["movidos"]:
        print(f"  {len(item['movidos'])} arquivo(s) movido(s) para {(Path('broll') / '_removidos' / a.id).as_posix()}/ — nada foi apagado.")
    elif item.get("arquivo") or item.get("tratados"):
        print("  Os arquivos continuam no disco, agora fora do registro (use --com-arquivos para tirá-los do caminho).")
    return 0


def _cmd_politica(a, projeto=None):
    print("Política de licenças do b-roll (conferida nas páginas oficiais em 2026-10-07; detalhes em references/licencas.md)\n")
    for lid, f in LICENCAS.items():
        marca = "entra " if f["permitida"] else "RECUSA"
        print(f"  {marca}  {f['nome']:<52} crédito {'obrigatório' if f['exige_atribuicao'] else 'opcional   '}  "
              f"comercial {'sim' if f['uso_comercial'] else 'NÃO'}  risco {f['risco']}")
        if f["motivo"]:
            print(f"          ↳ {f['motivo']}")
    print("\nExceção (NC, ND, sem licença): só com base_legal 'citacao' ou 'autorizacao' e `notas` explicando.")
    print("Material da casa usa base_legal 'proprio': não convive com licença de terceiro que a política recusa e, se veio de fora do disco\n"
          "(YouTube, web, página de origem), também exige `notas` dizendo por que é seu.")
    return 0


def _cmd_avaliar(a, projeto=None):
    f = avaliar_licenca(a.licenca, a.url)
    print(json.dumps(f, ensure_ascii=False, indent=2))
    return SAIDA_OK if f["permitida"] else SAIDA_ERRO


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        for en, pt in (("the following arguments are required", "faltou informar"), ("unrecognized arguments", "opção desconhecida"), ("invalid choice", "valor inválido"),
                       ("choose from", "opções"), ("expected one argument", "faltou o valor"), ("expected at least one argument", "faltou pelo menos um valor"),
                       ("argument ", "argumento ")):
            message = message.replace(en, pt)
        print(f"erro de uso: {message}\nVeja: registro.py {'' if self.prog.endswith('registro.py') else self.prog.split()[-1] + ' '}--help", file=sys.stderr)
        sys.exit(SAIDA_USO)

    def format_help(self):
        return super().format_help().replace("usage:", "uso:").replace("positional arguments:", "argumentos:").replace("options:", "opções:") \
            .replace("show this help message and exit", "mostra esta ajuda e sai")


def montar_parser() -> argparse.ArgumentParser:
    comum = argparse.ArgumentParser(add_help=False)
    comum.add_argument("--projeto", metavar="PASTA", default=argparse.SUPPRESS, help="raiz do projeto (padrão: sobe as pastas a partir da atual)")
    p = _Parser(prog="registro.py", parents=[comum], formatter_class=argparse.RawDescriptionHelpFormatter,
                description="Registro de licenças do b-roll (broll/licencas.json) e créditos (broll/creditos.md).",
                epilog="Não confere a direção de arte: só precisa da pasta do projeto (código 2 = projeto não encontrado).\n"
                       "Exemplos:\n  registro.py listar\n  registro.py marcar-uso B001 C03\n  registro.py sincronizar-uso\n  registro.py creditos\n"
                       "  registro.py adicionar --de-arquivo \"bruto/drone.mp4\" --base-legal proprio --autor \"Canal\"\n  registro.py politica")
    sub = p.add_subparsers(dest="cmd", metavar="<subcomando>", parser_class=_Parser)
    s = sub.add_parser("listar", parents=[comum], help="lista os itens do registro")
    s.add_argument("--json", action="store_true", help="saída em JSON")
    s.set_defaults(fn=_cmd_listar)
    s = sub.add_parser("mostrar", parents=[comum], help="mostra um item inteiro em JSON")
    s.add_argument("id")
    s.set_defaults(fn=_cmd_mostrar)
    s = sub.add_parser("validar", parents=[comum], help="confere política, créditos, arquivos e tratados de todos os itens")
    s.add_argument("--sha", action="store_true", help="recalcula o sha256 de cada arquivo (lento em arquivo grande)")
    s.add_argument("--json", action="store_true", help="saída em JSON")
    s.set_defaults(fn=_cmd_validar)
    s = sub.add_parser("creditos", parents=[comum], help="regrava broll/creditos.md e imprime o texto")
    s.add_argument("--sem-gravar", action="store_true", help="só imprime")
    s.set_defaults(fn=_cmd_creditos)
    for nome, ajuda in (("marcar-uso", "marca onde o item aparece (cena C03, corte K01…)"), ("desmarcar-uso", "tira uma marcação de uso")):
        s = sub.add_parser(nome, parents=[comum], help=ajuda)
        s.add_argument("id")
        s.add_argument("onde", nargs="+", help="id(s) de cena ou de corte")
        s.set_defaults(fn=_cmd_marcar)
    s = sub.add_parser("sincronizar-uso", parents=[comum], help="marca usado_em a partir de broll_id das cenas de roteiro/storyboard.json")
    s.set_defaults(fn=_cmd_sincronizar)
    s = sub.add_parser("adicionar", parents=[comum], help="registra material próprio, autorizado ou de fonte sem API",
                       description="Registra um item. --de-arquivo copia o arquivo para broll/bruto/ e mede sha256, tamanho e duração.")
    s.add_argument("--de-arquivo", metavar="ARQ", help="arquivo local a copiar e registrar")
    s.add_argument("--json", dest="json_item", metavar="ARQ|-", help="item pronto em JSON (arquivo ou stdin)")
    s.add_argument("--fonte", choices=FONTES)
    s.add_argument("--base-legal", dest="base_legal", choices=BASES_LEGAIS)
    s.add_argument("--autor")
    s.add_argument("--titulo")
    s.add_argument("--licenca")
    s.add_argument("--licenca-url", dest="licenca_url")
    s.add_argument("--pagina-url", dest="pagina_url")
    s.add_argument("--risco", choices=RISCOS)
    s.add_argument("--pedido", dest="pedido_id", metavar="P003", help="id do pedido em roteiro/pauta.json")
    s.add_argument("--notas", help="obrigatório em exceção (citacao, autorizacao)")
    s.add_argument("--campo", action="append", metavar="nome=valor", help="qualquer outro campo do contrato (repetível)")
    s.set_defaults(fn=_cmd_adicionar)
    s = sub.add_parser("atualizar", parents=[comum], help="troca campos de um item: atualizar B001 campo=valor …")
    s.add_argument("id")
    s.add_argument("pares", nargs="+", metavar="campo=valor")
    s.set_defaults(fn=_cmd_atualizar)
    s = sub.add_parser("remover", parents=[comum], help="tira um item do registro (recusa se estiver marcado como usado)",
                       description="Tira um item do registro. Recusa enquanto houver usado_em. Nada é apagado: com --com-arquivos, o bruto, "
                                   "os tratados e os carimbos vão para broll/_removidos/<id>/.")
    s.add_argument("id")
    s.add_argument("--com-arquivos", action="store_true", help="move o bruto, os tratados e os carimbos para broll/_removidos/<id>/")
    s.set_defaults(fn=_cmd_remover)
    s = sub.add_parser("politica", help="mostra a política de licenças")
    s.set_defaults(fn=_cmd_politica, sem_projeto=True)
    s = sub.add_parser("avaliar", help="diz se uma licença entra (código 1 = recusada)")
    s.add_argument("licenca", nargs="?", help='texto da licença, ex.: "CC BY-NC 4.0"')
    s.add_argument("--url", help="URL da licença")
    s.set_defaults(fn=_cmd_avaliar, sem_projeto=True)
    return p


def main(argv=None) -> int:
    p = montar_parser()
    a = p.parse_args(argv)
    if not getattr(a, "fn", None):
        p.print_help()
        return SAIDA_USO
    try:
        projeto = None if getattr(a, "sem_projeto", False) else (raiz(a.projeto) if getattr(a, "projeto", None) else achar_projeto())
        return a.fn(a, projeto) or 0
    except RegistroErro as e:
        print(f"erro: {e}", file=sys.stderr)
        return e.codigo
    except BrokenPipeError:
        return 0
    except KeyboardInterrupt:
        print("interrompido.", file=sys.stderr)
        return 130
    except Exception as e:                                    # defeito interno: uma linha, não um traceback (DA_DEBUG=1 mostra)
        if os.environ.get("DA_DEBUG") == "1":
            raise
        print(f"erro interno: {type(e).__name__}: {e} (DA_DEBUG=1 mostra o traceback)", file=sys.stderr)
        return SAIDA_ERRO


if __name__ == "__main__":
    sys.exit(main())
