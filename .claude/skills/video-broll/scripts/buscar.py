#!/usr/bin/env python3
"""buscar.py — procura b-roll gratuito e de uso permitido nos provedores, normaliza, ordena e (com --folha) monta a
folha de contato dos candidatos para a escolha visual. Não baixa o material: só lista (e guarda miniaturas em cache).

    buscar.py "sala de servidores" --en "server room" --folha
    buscar.py "Terra vista do espaço" --en "earth from space" --fontes nasa --tipo video --min-duracao 5 --folha
    buscar.py "circuito eletrônico" --en "circuit board" --tipo imagem --orientacao horizontal

Resultado em broll/_busca/<consulta>.json (+ .png da folha). O número de cada candidato é o que baixar.py recebe em
--escolher. A mesma consulta com outros filtros ou outras fontes NÃO sobrescreve a anterior: vai para <consulta>-2.json
(os números de uma folha já mostrada continuam valendo). Respostas ficam em cache por 24 h em broll/_busca/_cache/
(o Pixabay exige; os outros agradecem)."""
from __future__ import annotations

import hashlib
import io
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum  # noqa: E402
import provedores as P  # noqa: E402

PASTA = Path("broll") / "_busca"
VALIDADE_CACHE = 24 * 3600
VERSAO_CACHE = 8
MAX_DURACAO_PADRAO = 600.0       # vídeo de mais de 10 min é palestra, evento ou filme: fica de fora salvo pedido (--max-duracao 0)


def _agora() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _cache_arq(raiz: Path, prov: str, tipo: str, consulta: str, orientacao, quantos: int, idioma: str) -> Path:
    chave = json.dumps([VERSAO_CACHE, prov, tipo, consulta.strip().lower(), orientacao, quantos, idioma], ensure_ascii=False)
    return raiz / PASTA / "_cache" / f"{prov}_{hashlib.sha1(chave.encode()).hexdigest()[:16]}.json"


def bater_com_nao_faca(consultas: list[str], nao_faca: list[str]) -> list[str]:
    """Regras de conceito.nao_faca que a consulta parece contrariar (palavra de 4+ letras em comum, sem acento)."""
    import unicodedata

    def palavras(s):
        s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
        return {w for w in re.findall(r"[a-z]{4,}", s)} - {"para", "como", "mais", "mesma", "tela", "outro", "cada", "sobre", "pela", "pelo", "meio", "coisa",
                                                           "qualquer", "duas", "cores", "texto", "cima", "baixo", "fundo", "quadro", "with", "from", "that"}
    alvo = set().union(*(palavras(c) for c in consultas if c))
    return [regra for regra in nao_faca or [] if alvo & palavras(regra)]


def sem_segredo(c: dict) -> dict:
    """O candidato como pode ir para o disco e para --json: toda string passa por comum.mascarar_dados. Versão cujo
    endereço trazia a chave do usuário é descartada — não dá para guardar a chave nem baixar por endereço mascarado."""
    limpo = comum.mascarar_dados(c)
    if limpo != c:
        originais = {a.get("url") for a in c.get("arquivos") or []}
        limpo["arquivos"] = [a for a in limpo.get("arquivos") or [] if a.get("url") in originais]
        limpo.setdefault("avisos", []).append("o provedor devolveu a chave de API dentro da resposta: ela foi apagada do que é gravado, e versão "
                                             "cujo endereço a trazia foi descartada")
    return limpo


def _arquivo_da_busca(raiz: Path, consulta: str, assinatura: str) -> tuple[Path, str]:
    """Onde esta busca é gravada: <slug>.json; se já existe uma busca de mesmo nome com OUTRA assinatura (outros filtros,
    outras fontes), <slug>-2.json, -3… — refazer a consulta de outro jeito nunca troca os números de uma folha já mostrada."""
    base = comum.slug(consulta)
    for k in range(1, 100):
        nome = base if k == 1 else f"{base}-{k}"
        arq = raiz / PASTA / f"{nome}.json"
        if not arq.is_file():
            return arq, nome
        try:
            if json.loads(arq.read_text(encoding="utf-8")).get("assinatura") == assinatura:
                return arq, nome
        except (json.JSONDecodeError, OSError, AttributeError):
            continue
    raise comum.Erro(f"há buscas demais com o nome {base!r} em {raiz / PASTA}.", "Apague as que não servem mais (são intermediárias) e busque de novo.")


def buscar(d, consulta: str, en: str | None = None, tipo: str = "video", orientacao: str | None = None, fontes=None, por_fonte: int = 6,
           min_duracao=None, max_duracao=MAX_DURACAO_PADRAO, min_largura=None, min_altura=None, licenca: str = "permitidas", sem_cache: bool = False,
           detalhar: bool = True, pedido: str | None = None, http: comum.Http | None = None, avisar=None) -> dict:
    """Roda a busca em todos os provedores disponíveis e grava broll/_busca/<slug>.json. Devolve o dict gravado.

    d = DA do projeto (dá a raiz e o lado-alvo para a nota). `en` = a mesma consulta em inglês (é onde os acervos rendem);
    provedores com busca em português (Pexels, Pixabay, Commons) rodam as duas. tipo: video | imagem | ambos.
    max_duracao: padrão 600 s; 0 ou None = sem limite."""
    avisar = avisar or (lambda m: comum.diz(m, erro=True))
    raiz = Path(d.raiz)
    http = http or comum.Http()
    max_duracao = max_duracao or None
    tipos = ("video", "imagem") if tipo == "ambos" else (tipo,)
    nomes = list(fontes) if fontes else list(P.ORDEM)
    for n in nomes:
        if n not in P.PROVEDORES:
            raise comum.Erro(f"provedor desconhecido: {n!r}.", f"Use: {', '.join(P.ORDEM)}.", comum.SAIDA_USO)
    filtros = {"min_duracao": min_duracao, "max_duracao": max_duracao, "min_largura": min_largura, "min_altura": min_altura, "licenca": licenca}
    assinatura = hashlib.sha1(json.dumps([consulta.strip().lower(), (en or "").strip().lower(), tipo, orientacao or "qualquer", sorted(nomes), por_fonte,
                                          bool(detalhar), filtros], ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:12]
    lado_alvo = min(d.dimensoes("horizontal"))
    relato, todos, vistos, sem_rede = {}, [], set(), []
    for nome in nomes:
        prov = P.PROVEDORES[nome](http)
        ok, motivo = prov.disponivel()
        if not ok:
            relato[nome] = {"ok": False, "achados": 0, "aviso": motivo}
            avisar(f"  · {motivo}")
            continue
        if not any(t in prov.tipos for t in tipos):
            relato[nome] = {"ok": True, "achados": 0, "aviso": f"{prov.rotulo} só tem {' e '.join(prov.tipos)}"}
            continue
        for aviso in prov.avisos():
            avisar(f"  · {aviso}")
        achados, do_cache, erro = [], True, None
        for t in tipos:
            if t not in prov.tipos:
                continue
            consultas = [(en or consulta, "en")]
            if en and en.strip().lower() != consulta.strip().lower() and "pt" in prov.idiomas:
                consultas.append((consulta, "pt"))
            for texto_q, idioma in consultas:
                arq = _cache_arq(raiz, nome, t, texto_q, orientacao, por_fonte, idioma)
                itens = None
                if not sem_cache and arq.is_file() and time.time() - arq.stat().st_mtime < VALIDADE_CACHE:
                    try:
                        itens = json.loads(arq.read_text(encoding="utf-8"))["candidatos"]
                    except (json.JSONDecodeError, KeyError, OSError):
                        itens = None
                if itens is None:
                    do_cache = False
                    try:
                        itens = prov.buscar(texto_q, t, orientacao if orientacao != "qualquer" else None, por_fonte, idioma)
                        if detalhar:
                            itens = [prov.detalhar(c) for c in itens[:por_fonte]]
                    except comum.Erro as e:
                        erro = comum.mascarar(e.mensagem)
                        avisar(f"  · {prov.rotulo}: {erro}")
                        if e.codigo == comum.SAIDA_SEM_REDE:
                            sem_rede.append(nome)
                            break
                        continue
                    itens = [sem_segredo(c) for c in itens]     # nada do que vai para o cache leva a chave, nem que o provedor a devolva
                    arq.parent.mkdir(parents=True, exist_ok=True)
                    arq.write_text(json.dumps({"consultado_em": _agora(), "provedor": nome, "consulta": texto_q, "candidatos": itens}, ensure_ascii=False), encoding="utf-8")
                else:
                    itens = [sem_segredo(c) for c in itens]     # cache gravado por versão antiga
                for pos, c in enumerate(itens[:por_fonte]):
                    P.sanear(c)                                # extensão vinda da API (ou de um cache antigo) nunca segue crua
                    marca = (c["fonte"], c["tipo"], c["id_fonte"])
                    if marca in vistos:
                        continue
                    vistos.add(marca)
                    c["_posicao"] = pos
                    c["consulta_usada"] = texto_q
                    achados.append(c)
        relato[nome] = {"ok": erro is None, "achados": len(achados), "do_cache": do_cache and bool(achados), "aviso": erro}
        todos += achados
    tentados = [n for n, r in relato.items() if r.get("ok") or n in sem_rede]
    if sem_rede and not todos and set(tentados) == set(sem_rede):
        raise comum.Erro("nenhum provedor respondeu: sem conexão com a internet (ou todos fora do ar).",
                         "Confira a rede e tente de novo. Buscas feitas nas últimas 24 h continuam em broll/_busca/ e podem ser usadas por baixar.py.", comum.SAIDA_SEM_REDE)
    fora = []
    candidatos = []
    for c in todos:
        entra, motivo = P.passa(c, min_duracao, max_duracao, min_largura, min_altura, licenca)
        if not entra:
            fora.append({"fonte": c["fonte"], "titulo": c["titulo"], "motivo": motivo})
            continue
        c["pontos"] = round(P.pontuar(c, None if orientacao in (None, "qualquer") else orientacao, lado_alvo, c.pop("_posicao", 0)), 1)
        candidatos.append(c)
    candidatos.sort(key=lambda c: (-c["pontos"], P.ORDEM.index(c["fonte"]) if c["fonte"] in P.ORDEM else 99))
    for n, c in enumerate(candidatos, 1):
        c["n"] = n
        c.pop("_posicao", None)
    saida, nome_slug = _arquivo_da_busca(raiz, consulta, assinatura)
    anterior = None
    if saida.is_file():
        try:
            anterior = [(c.get("fonte"), c.get("id_fonte")) for c in json.loads(saida.read_text(encoding="utf-8")).get("candidatos") or []]
        except (json.JSONDecodeError, OSError):
            anterior = None
    resultado = comum.mascarar_dados({
        "versao": 1, "consulta": consulta, "en": en, "slug": nome_slug, "assinatura": assinatura, "tipo": tipo, "orientacao": orientacao or "qualquer",
        "fontes": nomes, "pedido_id": pedido, "feito_em": _agora(), "filtros": filtros, "identificacao": comum.identificacao(),
        "provedores": relato, "fora": fora, "pedidos_http": http.pedidos, "cota": http.limites, "candidatos": candidatos})
    candidatos = resultado["candidatos"]
    saida.parent.mkdir(parents=True, exist_ok=True)
    tmp = saida.with_name(saida.name + ".parcial")
    tmp.write_text(json.dumps(resultado, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(saida)
    resultado["arquivo"] = str(saida)
    resultado["mudou"] = anterior is not None and anterior != [(c["fonte"], c["id_fonte"]) for c in candidatos]     # mesma busca, outra ordem: a folha antiga caducou
    return resultado


def carregar_busca(raiz: Path, referencia: str) -> dict:
    """Uma busca gravada, pela consulta ("sala de servidores"), pelo slug ou pelo caminho do .json."""
    p = Path(referencia).expanduser()
    for cand in (p, raiz / p, raiz / PASTA / f"{comum.slug(referencia)}.json", raiz / PASTA / f"{referencia}.json"):
        if cand.is_file() and cand.suffix == ".json":
            try:
                dados = json.loads(cand.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                raise comum.Erro(f"{cand}: JSON inválido ({e}).", "Refaça a busca com buscar.py.")
            dados["arquivo"] = str(cand)
            base = re.sub(r"-\d+$", "", cand.stem)
            dados["variantes"] = sorted(x.stem for x in cand.parent.glob(f"{base}*.json") if x != cand and re.fullmatch(rf"{re.escape(base)}(-\d+)?", x.stem))
            return dados
    feitas = sorted(x.stem for x in (raiz / PASTA).glob("*.json") if not x.name.startswith("_")) if (raiz / PASTA).is_dir() else []
    raise comum.Erro(f"não achei a busca {referencia!r} em {raiz / PASTA}.",
                     ("Buscas gravadas: " + ", ".join(feitas)) if feitas else "Rode buscar.py primeiro.", comum.SAIDA_USO)


# ───────────────────────────────────────────────────────────── folha de contato ──
def _miniatura(raiz: Path, http: comum.Http, c: dict):
    """PIL.Image da miniatura (cache em broll/_busca/_mini/), ou None se não deu."""
    from PIL import Image, ImageOps
    url = c.get("miniatura_url")
    if not url:
        return None
    arq = raiz / PASTA / "_mini" / (hashlib.sha1(url.encode()).hexdigest()[:20] + ".img")
    try:
        if not arq.is_file():
            prov = P.PROVEDORES[c["fonte"]]
            dados = http.bytes(url, prov.hosts, intervalo=prov.intervalo if c["fonte"] == "openverse" else 0.3)
            arq.parent.mkdir(parents=True, exist_ok=True)
            arq.write_bytes(dados)
        with Image.open(arq) as im:
            im = ImageOps.exif_transpose(im).convert("RGB")
            im.thumbnail((960, 960))
            return im.copy()
    except (comum.Erro, OSError, ValueError):
        return None


def _uma_linha(texto, s: str, est, largura: int | None = None):
    """Desenha `s` numa linha só, no tamanho do estilo, cortando com reticências (desenhar() encolheria a fonte).
    Devolve (imagem, info) — info['linha_base'] e info['origem_x'] servem para alinhar pela linha de base."""
    s = "".join(ch for ch in " ".join(str(s).split()) if ord(ch) < 0x250 or ch in "–—‘’“”…·×•")     # fora do alfabeto latino a fonte da DA não tem glifo
    if largura and texto.largura_texto(s, est) > largura:
        while len(s) > 1 and texto.largura_texto(s.rstrip() + "…", est) > largura:
            s = s[:-1]
        s = s.rstrip(" ,.;:-–") + "…"
    return texto.desenhar(s or "—", est)


def _por(img, bloco_info, x: int, base: int) -> int:
    """Cola o texto com a origem em x e a LINHA DE BASE em `base` (linhas vizinhas ficam alinhadas). Devolve a largura."""
    bloco, info = bloco_info
    img.alpha_composite(bloco, (max(0, int(round(x - info["origem_x"]))), max(0, int(round(base - info["linha_base"])))))
    return bloco.width


def rotulo_licenca(c: dict, curto: bool = False) -> tuple[str, str]:
    """(texto, token de cor do sinal): positivo = livre de crédito e de origem conferida; alerta = crédito obrigatório,
    origem a conferir (licença declarada por quem subiu o item, crédito de terceiros) ou relevância baixa; negativo =
    recusada. `curto` = a forma que cabe na célula da folha de contato."""
    if not c.get("permitida"):
        return f"{c.get('licenca')} — recusada", "negativo"
    nome = {"pexels": "Pexels", "pixabay": "Pixabay", "nasa": "NASA", "pd": "Domínio público", "pdm": "Domínio público"}.get(c.get("licenca_id"), c.get("licenca"))
    if c.get("casou") == "palavras soltas":
        return f"{nome} · relevância baixa", "alerta"
    conferir = bool(c.get("conferir_origem")) or (c.get("risco") in ("medio", "alto") and c.get("licenca_id") != "cc-by-sa")
    if c.get("exige_atribuicao"):
        return f"{nome} · " + (("crédito · confira a origem" if curto else "crédito obrigatório · confira a origem") if conferir else "crédito obrigatório"), "alerta"
    if conferir:
        return f"{nome} · confira a origem", "alerta"
    return f"{nome} · crédito opcional", "positivo"


def folha(d, resultado: dict, saida=None, colunas: int = 4, largura_celula: int = 420, http: comum.Http | None = None) -> Path:
    """Folha de contato dos candidatos (só miniaturas), desenhada com os tokens da DA. Grava broll/_busca/<slug>.png."""
    _da, texto, _video, _trava = comum.importar_kit()
    from PIL import Image, ImageDraw, ImageOps
    raiz = Path(d.raiz)
    http = http or comum.Http()
    cands = resultado["candidatos"]
    colunas = max(1, min(colunas, len(cands) or 1))
    u = largura_celula
    margem, vao = int(u * 0.11), int(u * 0.05)
    alt_mini = int(u * 9 / 16)
    t_nota, t_corpo, t_titulo = max(13, int(u * 0.036)), max(15, int(u * 0.043)), int(u * 0.085)
    alt_leg = int(t_corpo * 1.9 + t_nota * 3.6)
    raio = int(d["layout"]["raio"] * u * 2.2)
    traco = max(1, int(round(d["layout"]["traco"] * u)))
    linhas = max(1, -(-len(cands) // colunas))
    cab = int(t_titulo * 3.3)
    rodape = int(t_nota * 3.0)
    W = max(margem * 2 + colunas * u + (colunas - 1) * vao, margem * 2 + int(u * 2.3))
    H = margem + cab + linhas * (alt_mini + alt_leg) + (linhas - 1) * vao + rodape + margem // 2
    img = Image.new("RGBA", (W, H), d.rgba("fundo"))
    des = ImageDraw.Draw(img)
    e_titulo = texto.Estilo.do_papel(d, "titulo", t_titulo, cor="texto")
    e_nome = texto.Estilo.do_papel(d, "corpo", t_corpo, cor="texto")
    e_nota = texto.Estilo.do_papel(d, "dados", t_nota, cor="texto_suave")
    cor_selo = "fundo" if d.contraste("fundo", "primaria") >= d.contraste("texto", "primaria") else "texto"
    e_num = texto.Estilo.do_papel(d, "dados", int(t_corpo * 1.25), cor=cor_selo)
    e_tag = texto.Estilo.do_papel(d, "dados", t_nota, cor="texto")

    _por(img, _uma_linha(texto, f"B-roll · {resultado['consulta']}", e_titulo, W - 2 * margem), margem, margem + t_titulo)
    quando = resultado.get("feito_em", "")[:10]
    em = f" · em inglês: {resultado['en']}" if resultado.get("en") else ""
    _por(img, _uma_linha(texto, f"{len(cands)} candidato(s){em} · {quando} · miniaturas de terceiros, só para a escolha", e_nota, W - 2 * margem),
         margem, margem + int(t_titulo * 1.75))
    y_fio = margem + cab - int(t_titulo * 0.62)
    des.rectangle([margem, y_fio, W - margem, y_fio + traco], fill=d.rgba("primaria"))

    def sinal(x, base, token):
        r = max(3, int(t_nota * 0.34))
        cy = base - int(t_nota * 0.36)
        des.ellipse([x, cy - r, x + 2 * r, cy + r], fill=d.rgba(token))
        return 2 * r + int(t_nota * 0.5)

    for i, c in enumerate(cands):
        col, lin = i % colunas, i // colunas
        x = margem + col * (u + vao)
        y = margem + cab + lin * (alt_mini + alt_leg + vao)
        celula = Image.new("RGBA", (u, alt_mini), d.rgba("superficie"))
        mini = _miniatura(raiz, http, c)
        if mini is not None:
            mini = ImageOps.contain(mini, (u, alt_mini), Image.LANCZOS)                 # miniatura de terceiros: entra inteira, sem recorte
            celula.paste(mini, ((u - mini.width) // 2, (alt_mini - mini.height) // 2))
        else:
            vazio, _ = texto.desenhar("sem miniatura", e_nota)
            celula.alpha_composite(vazio, ((u - vazio.width) // 2, (alt_mini - vazio.height) // 2))
        mascara = Image.new("L", (u, alt_mini), 0)
        ImageDraw.Draw(mascara).rounded_rectangle([0, 0, u - 1, alt_mini - 1], radius=raio, fill=255)
        img.paste(celula, (x, y), mascara)
        # selo com o número (é o que vai em baixar.py --escolher)
        num = _uma_linha(texto, f"{c['n']:02d}", e_num)
        alt_selo = int(e_num.tamanho * 1.9)
        larg_selo = max(alt_selo, num[0].width + alt_selo // 2)
        des.rounded_rectangle([x, y, x + larg_selo, y + alt_selo], radius=raio, fill=d.rgba("primaria"))
        img.alpha_composite(num[0], (x + (larg_selo - num[0].width) // 2, y + (alt_selo - num[0].height) // 2))
        # etiqueta do tipo (vídeo + duração | imagem)
        tag = _uma_linha(texto, ("VÍDEO " + comum.duracao_legivel(c.get("duracao"))) if c["tipo"] == "video" else "IMAGEM", e_tag)
        pad = int(t_nota * 0.55)
        alt_tag = t_nota + 2 * pad
        des.rounded_rectangle([x + u - tag[0].width - 2 * pad, y + alt_mini - alt_tag, x + u, y + alt_mini], radius=raio, fill=d.rgba("fundo", 0.84))
        _por(img, tag, x + u - tag[0].width - pad + tag[1]["origem_x"], y + alt_mini - pad - int(t_nota * 0.12))
        # legenda: título, fonte · resolução, licença com sinal — três linhas de base fixas
        base = y + alt_mini + int(t_corpo * 1.45)
        _por(img, _uma_linha(texto, c.get("titulo") or "(sem título)", e_nome, u), x, base)
        base += int(t_nota * 1.75)
        dims = f"{c['largura']}×{c['altura']}" if c.get("largura") and c.get("altura") else "resolução ?"
        _por(img, _uma_linha(texto, f"{P.PROVEDORES[c['fonte']].rotulo.split(' Image')[0]} · {dims}", e_nota, u), x, base)
        base += int(t_nota * 1.65)
        txt_lic, token = rotulo_licenca(c, curto=True)
        dx = sinal(x, base, token)
        _por(img, _uma_linha(texto, txt_lic, e_nota, u - dx), x + dx, base)

    # rodapé: legenda dos sinais
    base = H - margem // 2 - int(t_nota * 0.9)
    xr = margem
    for token, rot in (("positivo", "crédito opcional"), ("alerta", "crédito obrigatório, origem a conferir ou relevância baixa"), ("negativo", "licença recusada pela política")):
        xr += sinal(xr, base, token)
        xr += _por(img, _uma_linha(texto, rot, e_nota), xr, base) + int(t_nota * 2.2)
    saida = Path(saida) if saida else raiz / PASTA / f"{resultado['slug']}.png"
    saida.parent.mkdir(parents=True, exist_ok=True)
    tmp = saida.with_name(saida.stem + ".parcial.png")
    img.convert("RGB").save(tmp, "PNG", optimize=True)
    tmp.replace(saida)
    return saida


# ─────────────────────────────────────────────────────────────────────── CLI ──
def imprimir(resultado: dict) -> None:
    cands = resultado["candidatos"]
    for nome, r in resultado["provedores"].items():
        if r.get("ok") and not r.get("aviso"):
            comum.diz(f"  {nome:10} {r['achados']:2} achado(s){' (do cache)' if r.get('do_cache') else ''}")
        elif r.get("ok"):
            comum.diz(f"  {nome:10}  — {r['aviso']}")
    if not cands:
        comum.diz("\nNenhum candidato passou nos filtros. Tente a consulta em inglês (--en), termos mais concretos (o objeto, não a ideia), "
                  "--tipo imagem ou --licenca todas para ver o que foi recusado.")
        if resultado.get("fora"):
            comum.diz(f"{len(resultado['fora'])} resultado(s) ficaram de fora: " + "; ".join(sorted({str(f.get('motivo')) for f in resultado['fora']}))[:300])
        return
    comum.diz(f"\n nº  fonte      tipo    resolução    duração  licença")
    for c in cands:
        dims = f"{c['largura']}×{c['altura']}" if c.get("largura") and c.get("altura") else "?"
        dur = comum.duracao_legivel(c.get("duracao")) if c["tipo"] == "video" else "—"
        comum.diz(f" {c['n']:2}  {c['fonte']:10} {('vídeo' if c['tipo'] == 'video' else 'imagem'):7} {dims:>11}  {dur:>7}  {rotulo_licenca(c)[0]}")
        comum.diz(f"       {comum.sem_controle(c['titulo'])[:88]}")
        comum.diz(f"       {comum.sem_controle(c['pagina_url'])}")
        for av in c.get("avisos") or []:
            comum.diz(f"       ! {comum.sem_controle(av)}")
    if resultado.get("fora"):
        longos = sum(1 for f in resultado["fora"] if str(f.get("motivo", "")).startswith("longo demais"))
        comum.diz(f"\n{len(resultado['fora'])} resultado(s) ficaram de fora pelos filtros (lista em `fora` no JSON)"
                  + (f"; {longos} por passar de {resultado['filtros']['max_duracao']:g} s — --max-duracao 0 mostra, e baixar.py --trecho pega só um pedaço." if longos else "."))


def main(argv=None) -> int:
    ap = comum.Parser(prog="buscar.py", description="Procura b-roll gratuito e de uso permitido (Pexels, Pixabay, NASA, Wikimedia Commons, Internet Archive, "
                      "Openverse), ordena e monta a folha de contato dos candidatos. Não baixa o material.",
                      epilog="Chaves (só Pexels e Pixabay): variáveis PEXELS_API_KEY / PIXABAY_API_KEY ou $VIDEO_OPS_HOME/chaves.env. "
                             "Identificação: sem VIDEO_OPS_CONTATO (e-mail ou URL do usuário, em chaves.env) a Wikimedia Commons é pulada — a política "
                             "dela exige contato; o Internet Archive pede o modelo do agente em VIDEO_OPS_AGENTE. Detalhes em references/fontes.md.")
    ap.add_argument("consulta", help='conceito visual concreto, em português (ex.: "sala de servidores")')
    ap.add_argument("--en", metavar="TEXTO", help='a mesma consulta em inglês (ex.: "server room") — é onde os acervos rendem')
    ap.add_argument("--tipo", choices=("video", "imagem", "ambos"), default="video", help="padrão: video")
    ap.add_argument("--orientacao", choices=("horizontal", "vertical", "quadrado", "qualquer"), default="qualquer", help="padrão: qualquer (o tratamento encaixa)")
    ap.add_argument("--fontes", metavar="A,B", help=f"provedores, separados por vírgula (padrão: todos — {', '.join(P.ORDEM)})")
    ap.add_argument("--por-fonte", type=int, default=6, metavar="N", help="resultados por provedor e por consulta (padrão 6; máx. 20)")
    ap.add_argument("--min-duracao", type=float, metavar="S", help="duração mínima do vídeo, em segundos")
    ap.add_argument("--max-duracao", type=float, default=MAX_DURACAO_PADRAO, metavar="S",
                    help=f"duração máxima do vídeo, em segundos (padrão {MAX_DURACAO_PADRAO:g}: palestra e filme inteiro ficam de fora; 0 = sem limite)")
    ap.add_argument("--min-largura", type=int, metavar="PX")
    ap.add_argument("--min-altura", type=int, metavar="PX")
    ap.add_argument("--licenca", choices=("permitidas", "sem-atribuicao", "todas"), default="permitidas",
                    help="permitidas (padrão) · sem-atribuicao (só o que dispensa crédito) · todas (mostra também o que a política recusa)")
    ap.add_argument("--folha", action="store_true", help="gera a folha de contato dos candidatos (baixa só as miniaturas)")
    ap.add_argument("--colunas", type=int, default=4, help="colunas da folha (padrão 4)")
    ap.add_argument("--pedido", metavar="P003", help="id do pedido em roteiro/pauta.json a que a busca atende")
    ap.add_argument("--sem-cache", action="store_true", help="ignora o cache de 24 h e consulta de novo")
    ap.add_argument("--rapido", action="store_true", help="não busca os detalhes (versões e duração) de NASA e Internet Archive")
    ap.add_argument("--json", action="store_true", help="imprime o resultado em JSON")
    ap.add_argument("--projeto", metavar="PASTA", help="raiz do projeto (padrão: acha pela pasta atual)")
    a = ap.parse_args(argv)
    if not 1 <= a.por_fonte <= 20:
        ap.error("--por-fonte vai de 1 a 20")
    for nome in ("min_duracao", "max_duracao", "min_largura", "min_altura"):
        if getattr(a, nome) is not None and getattr(a, nome) < 0:
            ap.error(f"--{nome.replace('_', '-')} não pode ser negativo")
    d, _da = comum.carregar_da(a.projeto)                    # Passo 0: sem DA, código 2
    fontes = [f.strip() for f in a.fontes.split(",") if f.strip()] if a.fontes else None
    conceito = d.get("conceito") or {}
    bate = bater_com_nao_faca([a.consulta, a.en or ""], conceito.get("nao_faca") or [])
    if not a.json:
        comum.diz(f"Busca: «{a.consulta}»" + (f" / «{a.en}»" if a.en else "") + f" · {a.tipo} · projeto {Path(d.raiz).name}")
        for regra in bate:
            comum.diz(f"  ! a consulta parece bater com o que a DA proíbe (conceito.nao_faca): «{regra}» — prefira outra imagem para a mesma ideia")
    r = buscar(d, a.consulta, a.en, a.tipo, a.orientacao, fontes, a.por_fonte, a.min_duracao, a.max_duracao, a.min_largura, a.min_altura,
               a.licenca, a.sem_cache, not a.rapido, a.pedido)
    r["nao_faca"] = bate
    png = Path(r["arquivo"]).with_suffix(".png")
    if a.folha and r["candidatos"]:
        r["folha"] = str(folha(d, r, colunas=a.colunas))
    elif r.get("mudou") and png.is_file():                   # a folha antiga mostra números que não valem mais
        png.unlink()
        r["folha_caduca"] = True
    if a.json:
        print(json.dumps(comum.mascarar_dados(r), ensure_ascii=False, indent=1))
        return 0 if r["candidatos"] else 1
    imprimir(r)
    comum.diz(f"\nResultado: {r['arquivo']}")
    if r.get("mudou"):
        comum.diz("! Esta busca já tinha sido feita e os candidatos mudaram de ordem: os números de antes NÃO valem mais"
                  + (" (a folha antiga foi apagada; gere outra com --folha)." if r.get("folha_caduca") else " — mostre a folha nova."))
    if r.get("folha"):
        comum.diz(f"Folha de contato: {r['folha']}  (mostre ao usuário; a escolha é dele)")
    if r["candidatos"]:
        exemplo = "1" if len(r["candidatos"]) == 1 else "1,2"
        comum.diz(f"Depois da escolha do usuário: baixar.py --busca \"{r['slug']}\" --escolher {exemplo}   (só monta o PLANO e imprime o código dele; "
                  "o download é baixar.py --plano CÓDIGO --confirmar, depois do «sim»)")
    return 0 if r["candidatos"] else 1


if __name__ == "__main__":
    sys.exit(comum.rodar(main))
