#!/usr/bin/env python3
"""imagens.py — baixa UMA imagem por link direto (ou registra uma captura já salva) com a página de origem e o crédito.

    imagens.py baixar --url https://upload.wikimedia.org/…/Foto.jpg --pagina https://commons.wikimedia.org/wiki/File:Foto.jpg \
        --autor "Fulana" --titulo "Foto" --licenca "CC BY-SA 4.0" [--pedido P002]            # só o PLANO
    imagens.py baixar … --confirmar                                                          # baixa, confere e registra
    imagens.py baixar --arquivo "~/Desktop/print.png" --pagina https://site/noticia --base-legal citacao --nota "…"

Não busca: a busca no Google Imagens é feita pelo navegador da sessão (procedimento no SKILL.md) e termina aqui, com o
link da imagem, a página de origem e o crédito recolhidos lá. Confere tipo, dimensões e tamanho; grava em
broll/bruto/W###.<ext> e registra em broll/licencas.json pelo módulo da video-broll (fonte "web")."""
from __future__ import annotations

import json
import os
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import base  # noqa: E402
import roteiro  # noqa: E402

EXTENSOES = {"JPEG": ".jpg", "MPO": ".jpg", "PNG": ".png", "WEBP": ".webp", "GIF": ".gif"}
TETO_PIXELS = 80_000_000


def _local(host: str) -> bool:
    return host in ("127.0.0.1", "localhost", "::1")


def _url_ok(url: str, nome: str) -> str:
    p = urllib.parse.urlsplit((url or "").strip())
    if p.scheme == "https" and p.hostname and not _local(p.hostname):
        return urllib.parse.urlunsplit(p)
    if p.scheme == "http" and _local(p.hostname or "") and os.environ.get("VIDEO_PAUTA_TESTE_LOCAL") == "1":   # só a suíte de testes
        return urllib.parse.urlunsplit(p)
    raise base.Erro(f"{nome} precisa ser um endereço https público (veio {url!r:.120}).", "Copie o link no navegador (botão direito → copiar endereço da imagem).", base.USO)


class _SoHttps(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _url_ok(newurl, "o redirecionamento")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _baixar(url: str, destino: Path, teto: int) -> str:
    """Grava a resposta em `destino` (até `teto` bytes) e devolve o Content-Type."""
    agente = f"video-pauta-midia/{base.VERSAO} (pauta de midia de video, uso editorial; {base.contato()}) Python-urllib/{sys.version_info.major}.{sys.version_info.minor}"
    pedido = urllib.request.Request(url, headers={"User-Agent": agente, "Accept": "image/*"})
    try:
        with urllib.request.build_opener(_SoHttps()).open(pedido, timeout=30) as r:
            tipo = (r.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            if not tipo.startswith("image/") or "svg" in tipo:
                raise base.Erro(f"o link não entrega uma imagem de pixels (tipo: {tipo or 'não informado'}).",
                                "Passe o link direto do ARQUIVO (termina em .jpg, .png, .webp), não o da página nem o da miniatura do buscador. "
                                "SVG: baixe a versão PNG que a página de origem oferece.")
            total = 0
            with open(destino, "wb") as f:
                while bloco := r.read(1 << 16):
                    total += len(bloco)
                    if total > teto:
                        raise base.Erro(f"a imagem passa do teto de {teto / 1e6:g} MB.", "Escolha uma versão menor na página de origem ou aumente --teto-mb.")
                    f.write(bloco)
            return tipo
    except urllib.error.HTTPError as e:
        dica = "O site recusou o pedido: abra a página de origem no navegador e confira o link direto do arquivo."
        if e.code in (403, 429) and "contato nao configurado" in agente:
            dica += " A Wikimedia exige contato no User-Agent: defina VIDEO_OPS_CONTATO (e-mail ou site do usuário) e repita."
        raise base.Erro(f"o servidor respondeu {e.code} para {urllib.parse.urlsplit(url).hostname}.", dica)
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise base.Erro(f"sem resposta de {urllib.parse.urlsplit(url).hostname}: {getattr(e, 'reason', e)}", "Confira a conexão e o link e repita.", base.SEM_REDE)


def _conferir(arq: Path, min_lado: int) -> dict:
    try:
        from PIL import Image
    except ImportError:
        raise base.Erro(f"este Python ({sys.executable}) não tem o Pillow.", "Rode com /opt/homebrew/bin/python3.")
    Image.MAX_IMAGE_PIXELS = TETO_PIXELS
    try:
        with Image.open(arq) as im:
            im.verify()
        with Image.open(arq) as im:
            formato, largura, altura = str(im.format).upper(), im.width, im.height
    except Exception as e:                                    # o PIL levanta vários tipos para o que não é imagem
        raise base.Erro(f"o arquivo não é uma imagem legível ({type(e).__name__}).", "O site pode ter devolvido uma página no lugar do arquivo: confira o link direto.")
    if formato not in EXTENSOES:
        raise base.Erro(f"formato {formato} não entra no projeto.", "Use JPEG, PNG, WebP ou GIF (a página de origem costuma oferecer outra versão).")
    if max(largura, altura) < min_lado:
        raise base.Erro(f"imagem pequena demais: {largura}x{altura} (mínimo de {min_lado} px no maior lado).",
                        "É a miniatura do buscador? Abra a página de origem e pegue o arquivo original; ou reduza --min-lado se for isso mesmo.")
    return {"largura": largura, "altura": altura, "ext": EXTENSOES[formato]}


def cmd_baixar(a) -> int:
    if bool(a.url) == bool(a.arquivo):
        raise base.Erro("informe --url (link direto da imagem) OU --arquivo (captura já salva).", codigo=base.USO)
    url = _url_ok(a.url, "--url") if a.url else None
    pagina = _url_ok(a.pagina, "--pagina")
    local = Path(a.arquivo).expanduser() if a.arquivo else None
    if local and not local.is_file():
        raise base.Erro(f"arquivo não encontrado: {local}", codigo=base.USO)
    projeto = base.achar_projeto(a.projeto)
    d = base.exigir_da(projeto)
    projeto = Path(d.raiz) if hasattr(d, "raiz") else projeto
    reg = base.registro()
    b = a.base_legal or ("licenca" if (a.licenca or a.licenca_url) else None)
    if b is None:
        raise base.Erro("faltou dizer com que direito a imagem entra.",
                        "Informe a licença lida NA PÁGINA DE ORIGEM (--licenca \"CC BY-SA 4.0\" e, se houver, --licenca-url) ou a base legal "
                        "(--base-legal citacao | autorizacao | proprio) com --nota. Imagem achada no buscador sem licença visível é «todos os direitos reservados».")
    ficha = reg.avaliar_licenca(a.licenca, a.licenca_url, "web")
    if b == "licenca" and not ficha["permitida"]:
        raise base.Erro(f"licença recusada pela política: {a.licenca or a.licenca_url} — {ficha['motivo']}.",
                        "Procure outra imagem, ou registre como exceção: --base-legal citacao (ou autorizacao) com --nota. A decisão é do usuário.")
    if b != "licenca" and not (a.nota or "").strip():
        raise base.Erro(f"--base-legal {b} exige --nota.", "Diga o que é citado e por quê, quem autorizou e onde está a prova, ou por que a imagem é da casa.", base.USO)
    if not a.autor and b != "proprio":
        raise base.Erro("faltou --autor: sem nome de autor (ou do veículo) não há crédito.", "Recolha o crédito na página de origem; se ela não diz, use o nome do site.", base.USO)
    risco = a.risco or {"licenca": ficha["risco"], "citacao": "medio", "autorizacao": "baixo", "proprio": "baixo"}[b]
    repetido = reg.procurar(projeto, arquivo_url=url) if url else []
    pedido = roteiro._achar(roteiro.carregar(projeto), a.pedido) if a.pedido else None
    plano = {"url": url, "arquivo": str(local) if local else None, "pagina": pagina, "autor": a.autor, "titulo": a.titulo,
             "licenca": ficha["nome"] if (a.licenca or a.licenca_url) else None, "base_legal": b, "risco": risco, "pedido": a.pedido,
             "destino": "broll/bruto/W###.<ext>", "ja_baixado": repetido[0]["id"] if repetido else None}
    if not a.json:
        base.diz(f"  imagem:   {url or local}\n  origem:   {pagina}\n  autor:    {a.autor or '—'}" + (f" · título: {a.titulo}" if a.titulo else ""))
        base.diz(f"  licença:  {plano['licenca'] or 'sem licença de reuso (todos os direitos reservados)'}\n  base:     {b} · risco {risco}"
                 + (f" · nota: {a.nota}" if a.nota else "") + (f" · pedido {a.pedido}" if a.pedido else ""))
    if repetido:
        base.diz(json.dumps(plano, ensure_ascii=False, indent=2) if a.json else f"já está no registro como {repetido[0]['id']}: nada a baixar.")
        return base.OK
    if url and not a.confirmar:
        base.diz(json.dumps({**plano, "baixado": False}, ensure_ascii=False, indent=2) if a.json else
                 "PLANO — nada foi baixado. Mostre esta ficha ao usuário e, com o «sim» dele, repita o comando com --confirmar.")
        return base.OK
    if url and pedido is not None and pedido["status"] not in ("aprovado", "baixado", "tratado"):
        raise base.Erro(f"{pedido['id']} está «{pedido['status']}» na pauta: ainda não foi aprovado pelo usuário.",
                        f"Mostre a ficha, espere o «sim» e marque: roteiro.py definir {pedido['id']} --status aprovado. Depois repita com --confirmar.")
    bruto = projeto / reg.PASTA_BRUTO
    bruto.mkdir(parents=True, exist_ok=True)
    tmp = bruto / f"_entrando_{os.getpid()}"
    try:
        if url:
            _baixar(url, tmp, int(a.teto_mb * 1e6))
        else:
            if local.stat().st_size > a.teto_mb * 1e6:
                raise base.Erro(f"o arquivo passa do teto de {a.teto_mb:g} MB.", "Aumente --teto-mb se for isso mesmo.")
            shutil.copyfile(local, tmp)
        medidas = _conferir(tmp, a.min_lado)
        host = urllib.parse.urlsplit(pagina).hostname or ""
        item = {"prefixo": "W", "fonte": "web", "tipo": "imagem", "titulo": a.titulo or (Path(urllib.parse.unquote(urllib.parse.urlsplit(url).path)).stem if url else local.stem),
                "pagina_url": pagina, "arquivo_url": url, "autor": a.autor, "autor_url": a.autor_url, "licenca": a.licenca, "licenca_url": a.licenca_url,
                "base_legal": b, "risco": risco, "pedido_id": a.pedido, "notas": a.nota, "baixado_em": reg.agora_iso(), "sha256": reg.sha256_arquivo(tmp),
                "bytes": tmp.stat().st_size, "largura": medidas["largura"], "altura": medidas["altura"]}
        if b == "citacao":
            autor = " ".join((a.autor or host).split())
            item["credito_tela"] = "Reprodução: " + (autor if len(autor) <= 44 else autor[:43].rstrip() + "…")
        mid = reg.adicionar(projeto, {k: v for k, v in item.items() if v is not None}, mover_de=tmp, extensao=medidas["ext"])
    finally:
        tmp.unlink(missing_ok=True)
    reg.creditos_md(projeto)
    gravado = reg.obter(projeto, mid)
    if a.pedido:
        roteiro.alterar(projeto, a.pedido, midia=mid, status="baixado", url=pagina)
    if a.json:
        base.diz(json.dumps({**plano, "baixado": True, "id": mid, "arquivo": gravado["arquivo"], "largura": medidas["largura"], "altura": medidas["altura"]}, ensure_ascii=False, indent=2))
        return base.OK
    base.diz(f"registrado: {mid} → {gravado['arquivo']} ({medidas['largura']}x{medidas['altura']}, {gravado['bytes'] / 1e6:.2f} MB)")
    base.diz(f"crédito na tela: {gravado.get('credito_tela')}\ncrédito na descrição: {gravado.get('atribuicao')}  (broll/creditos.md atualizado)")
    base.diz(f"próximo passo — moldura e crédito na direção de arte: python3 \"$CRIABR_SKILLS\"/video-broll/scripts/tratar.py {mid} --formato horizontal --moldura --dur 5")
    return base.OK


def main(argv=None) -> int:
    ap = base.Parser(prog="imagens.py", description="Baixa uma imagem por link direto (ou registra uma captura salva) com origem, crédito e licença.")
    sub = ap.add_subparsers(dest="cmd", required=True, parser_class=base.Parser)
    p = sub.add_parser("baixar", help="plano; com --confirmar, baixa, confere e registra")
    p.add_argument("--url", help="link direto do arquivo da imagem (https)")
    p.add_argument("--arquivo", help="captura ou imagem já salva no disco (print de tela): registra sem rede")
    p.add_argument("--pagina", required=True, help="página de origem (onde a imagem está publicada e creditada)")
    p.add_argument("--autor", help="autor ou veículo, como a página de origem credita")
    p.add_argument("--autor-url")
    p.add_argument("--titulo")
    p.add_argument("--licenca", help="licença lida na página de origem (ex.: \"CC BY-SA 4.0\", \"domínio público\")")
    p.add_argument("--licenca-url")
    p.add_argument("--base-legal", choices=("licenca", "citacao", "autorizacao", "proprio"), help="padrão: licenca, quando --licenca é informada")
    p.add_argument("--nota", help="obrigatória em citacao, autorizacao e proprio")
    p.add_argument("--risco", choices=("baixo", "medio", "alto"))
    p.add_argument("--pedido", metavar="P###", help="item da pauta que esta imagem atende (precisa estar «aprovado» para baixar)")
    p.add_argument("--min-lado", type=int, default=640, help="mínimo do maior lado em pixels (padrão 640)")
    p.add_argument("--teto-mb", type=float, default=25.0, help="tamanho máximo do arquivo (padrão 25 MB)")
    p.add_argument("--confirmar", action="store_true", help="baixa de verdade — só depois do «sim» do usuário na conversa")
    p.add_argument("--projeto", metavar="PASTA", help="raiz do projeto (padrão: acha pela pasta atual)")
    p.add_argument("--json", action="store_true", help="saída em JSON")
    p.set_defaults(f=cmd_baixar)
    a = ap.parse_args(argv)
    return a.f(a)


if __name__ == "__main__":
    sys.exit(base.rodar(main))
