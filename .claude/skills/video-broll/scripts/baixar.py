#!/usr/bin/env python3
"""baixar.py — baixa os candidatos escolhidos de uma busca, com registro de licença.

Dois tempos, amarrados por um código: sem --confirmar só monta o PLANO (arquivo, origem, tamanho, licença, crédito), grava-o
em broll/_busca/_plano_<código>.json e não baixa nada — baixar é ação externa e a aprovação é do usuário, na conversa.
O download só acontece com `--plano <código> --confirmar`, e executa EXATAMENTE o plano mostrado: refazer a busca, mudar
um filtro ou o cache vencer não troca o que foi aprovado; se o arquivo mudou no servidor, o item é recusado.

    baixar.py --busca "sala de servidores" --escolher 2,5                  # plano (imprime o código)
    baixar.py --plano 3fa9c1d2 --confirmar                                 # baixa aquele plano (depois do «sim» do usuário)
    baixar.py --busca "terra vista do espaço" --escolher 4 --trecho 30-42  # plano de só 12 s de um vídeo longo

Com --confirmar: teto de tamanho, retomada, sha256, validação por ffprobe e registro em broll/licencas.json (arquivo em
broll/bruto/<id>.<ext>).
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import re
import shutil
import sys
import time
import urllib.parse
from datetime import datetime
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import buscar as B  # noqa: E402
import comum  # noqa: E402
import provedores as P  # noqa: E402
import registro  # noqa: E402

TETO_PADRAO_MB = 80
RESERVA_DISCO = 2 << 30          # nunca deixa o disco com menos de 2 GB livres
VALIDADE_PLANO = 24 * 3600       # um plano aprovado vale um dia: depois disso tamanhos e endereços podem ter mudado
_CONTAINERS_DE_COPIA = ("mp4", "mov", "m4v", "webm", "mkv")
_EXT_PIL = {"JPEG": "jpg", "MPO": "jpg", "PNG": "png", "WEBP": "webp", "TIFF": "tif"}


def _numeros(texto: str, maximo: int) -> list[int]:
    nums = []
    for parte in str(texto).replace(" ", "").split(","):
        if not parte:
            continue
        try:
            if "-" in parte:
                a, b = parte.split("-", 1)
                nums += list(range(int(a), int(b) + 1))
            else:
                nums.append(int(parte))
        except ValueError:
            raise comum.Erro(f"--escolher: {parte!r} não é um número de candidato.", "Use os números da folha de contato: --escolher 2,5 ou --escolher 1-3.", comum.SAIDA_USO)
    fora = [n for n in nums if not 1 <= n <= maximo]
    if fora or not nums:
        raise comum.Erro(f"--escolher: candidato(s) {fora or 'nenhum'} fora da lista (a busca tem {maximo}).", "Confira os números na folha de contato ou no JSON da busca.", comum.SAIDA_USO)
    return list(dict.fromkeys(nums))


def _trecho(texto: str | None) -> tuple[float, float] | None:
    if not texto:
        return None
    try:
        a, b = texto.split("-", 1)
        t0, t1 = comum.segundos(a), comum.segundos(b)
        if t0 is None or t1 is None or t0 < 0 or t1 <= t0:
            raise ValueError
    except ValueError:
        raise comum.Erro(f"--trecho: {texto!r} não é um intervalo válido.", "Use início-fim em segundos ou mm:ss, ex.: --trecho 30-42 ou --trecho 1:05-1:20.", comum.SAIDA_USO)
    return t0, t1


def planejar(d, busca: dict, numeros: list[int], lado_alvo: int | None = None, teto_mb: float = TETO_PADRAO_MB, trecho=None,
             base_legal: str = "licenca", nota: str | None = None, http: comum.Http | None = None) -> list[dict]:
    """Uma entrada por candidato: o que seria baixado, de onde, com que tamanho e licença — e o que impede, se algo impede."""
    raiz = Path(d.raiz)
    http = http or comum.Http()
    lado_alvo = lado_alvo or min(d.dimensoes("horizontal"))
    teto = int(teto_mb * 1e6)
    registrados = registro.carregar(raiz)["itens"]
    plano = []
    for n in numeros:
        c = busca["candidatos"][n - 1]
        prov = P.PROVEDORES[c["fonte"]](http)
        e = {"n": n, "candidato": c, "problema": None, "avisos": list(c.get("avisos") or []), "arquivo": None, "bytes": None, "retoma": False, "ja": None}
        plano.append(e)
        try:
            ok, motivo = prov.disponivel()
            if not ok:
                raise comum.Erro(motivo)
            c = B.sem_segredo(P.sanear(prov.detalhar(c)))      # o detalhe vem do provedor: passa pelos mesmos crivos da busca
            e["candidato"] = c
            e["avisos"] = list(c.get("avisos") or [])
            ordem = P.ordenar_arquivos(c, lado_alvo, None if trecho else teto)
            if not ordem:
                tamanhos = ", ".join(sorted({comum.tamanho_legivel(a.get("bytes")) for a in c.get("arquivos") or []}))
                raise comum.Erro(f"nenhuma versão cabe no teto de {teto_mb:g} MB ({tamanhos or 'o provedor não listou arquivos'})",
                                 "baixe só um trecho (--trecho A-B) ou suba o teto (--teto-mb)")
            grandes = []
            for arq in ordem[:5]:                               # o tamanho real só vem no HEAD: desce de versão até uma caber no teto
                info = http.tamanho(arq["url"], prov.hosts_arquivo)
                tamanho = info["bytes"] or (None if arq.get("bytes_estimado") else arq.get("bytes"))
                e.update(arquivo=arq, bytes=tamanho, retoma=info["retoma"], tipo_http=info["tipo"])
                pesa = tamanho
                if trecho and tamanho and (arq.get("duracao") or c.get("duracao")):          # do trecho só vem uma fatia do arquivo
                    pesa = int(tamanho * min(1.0, (trecho[1] - trecho[0]) / float(arq.get("duracao") or c["duracao"])) * 1.15)
                    e["bytes_trecho"] = pesa
                if not pesa or pesa <= teto or (trecho and not e.get("bytes_trecho")):
                    break
                grandes.append(f"{arq.get('rotulo')}: {comum.tamanho_legivel(pesa)}" + (" no trecho" if trecho else ""))
            else:
                raise comum.Erro(f"nenhuma versão cabe no teto de {teto_mb:g} MB ({'; '.join(grandes)})",
                                 "baixe só um trecho (--trecho A-B) ou suba o teto (--teto-mb)")
            if grandes:
                e["avisos"].append(f"versões maiores ficaram fora do teto ({'; '.join(grandes)}): vai a «{arq.get('rotulo')}»")
            if trecho and c["tipo"] != "video":
                raise comum.Erro("--trecho só vale para vídeo")
            if trecho and arq.get("duracao") and trecho[0] >= arq["duracao"]:
                raise comum.Erro(f"o trecho começa em {trecho[0]:g} s, mas o vídeo tem {arq['duracao']:.0f} s")
        except comum.Erro as erro:
            e["problema"] = comum.mascarar(erro.mensagem) + (f" — {erro.dica}" if erro.dica else "")
            e["sem_rede"] = erro.codigo == comum.SAIDA_SEM_REDE
            continue
        if not c.get("permitida") and base_legal == "licenca":
            e["problema"] = (f"licença recusada pela política ({c.get('licenca')}: {c.get('motivo')}). Só entra como exceção, por decisão do usuário: "
                             "--base-legal citacao|autorizacao --nota \"por quê\"")
        elif base_legal != "licenca" and not (nota or "").strip():
            e["problema"] = f"--base-legal {base_legal} exige --nota explicando a exceção"
        for item in registrados:
            if item.get("pagina_url") == c.get("pagina_url") and item.get("arquivo_url") == arq["url"] and (item.get("trecho") or None) == ({"t0": round(trecho[0], 3), "t1": round(trecho[1], 3)} if trecho else None):
                e["ja"] = item.get("id")
    return plano


_NOME_BASE = {"citacao": "citação", "autorizacao": "autorização"}


def como_entra(c: dict, op: dict | None) -> dict:
    """O que o registro vai gravar para este candidato sob as opções do plano: {excecao, base_legal, risco, uso_comercial,
    exige_atribuicao, nota}. É o que o usuário aprova — por isso o plano mostra isto, e não só a licença de origem."""
    op = op or {}
    base = op.get("base_legal") or "licenca"
    if base == "licenca":
        return {"excecao": False, "base_legal": base, "risco": op.get("risco") or c.get("risco"), "uso_comercial": bool(c.get("uso_comercial")),
                "exige_atribuicao": bool(c.get("exige_atribuicao")), "nota": None}
    risco = op.get("risco") or ("medio" if c.get("risco") == "medio" else {"citacao": "medio", "autorizacao": "baixo"}[base])
    return {"excecao": True, "base_legal": base, "risco": risco, "uso_comercial": False, "exige_atribuicao": True, "nota": (op.get("nota") or "").strip()}


def imprimir_plano(d, plano: list[dict], teto_mb: float, trecho=None, confirmar: bool = False, busca: dict | None = None, codigo: str | None = None,
                   op: dict | None = None) -> None:
    raiz = Path(d.raiz)
    livre = shutil.disk_usage(raiz).free
    limpo = comum.sem_controle              # título, autor e nome de arquivo vêm de terceiros: nunca vão crus para o terminal
    comum.diz((f"DOWNLOAD — plano {codigo}" if codigo else "DOWNLOAD") if confirmar else "PLANO DE DOWNLOAD — nada foi baixado")
    if busca:
        comum.diz(f"  busca: «{limpo(busca.get('consulta'))}» ({limpo(busca.get('slug'))}, feita em {str(busca.get('feito_em'))[:16].replace('T', ' ')})")
        if busca.get("variantes"):
            comum.diz(f"  ! há outra(s) busca(s) com a mesma consulta e outros filtros: {', '.join(busca['variantes'])} — confira se os números são desta")
    total = 0
    for e in plano:
        c, arq = e["candidato"], e["arquivo"]
        comum.diz(f"\n  [{e['n']}] {P.PROVEDORES[c['fonte']].rotulo} · {limpo(c['titulo'])[:80]}")
        comum.diz(f"      página:  {limpo(c['pagina_url'])}")
        if arq:
            nome = limpo(urllib.parse.unquote(urllib.parse.urlsplit(arq["url"]).path.rsplit("/", 1)[-1]))
            dims = f"{arq['largura']}×{arq['altura']}" if arq.get("largura") and arq.get("altura") else "resolução só depois de baixar"
            dur = f" · {comum.duracao_legivel(arq.get('duracao') or c.get('duracao'))}" if c["tipo"] == "video" else ""
            comum.diz(f"      arquivo: {nome if len(nome) <= 70 else nome[:58] + '…' + nome[-11:]}  ({limpo(urllib.parse.urlsplit(arq['url']).hostname)})")
            fatia = (f" · só o trecho {trecho[0]:g}–{trecho[1]:g} s (" + (f"≈ {comum.tamanho_legivel(e['bytes_trecho'])}; " if e.get("bytes_trecho") else "")
                     + "pode vir com alguns segundos a mais no início: o corte cai no quadro-chave anterior)") if trecho else ""
            comum.diz(f"               {comum.tamanho_legivel(e['bytes'])} · {dims}{dur} · versão «{limpo(arq.get('rotulo'))}»{fatia}" + ("" if e["retoma"] or trecho else " · sem retomada"))
            total += 0 if e["problema"] or e["ja"] else ((e.get("bytes_trecho") if trecho else e["bytes"]) or 0)
        entra = como_entra(c, op)
        if entra["excecao"]:
            comum.diz(f"      licença: {limpo(c.get('licenca'))}" + ("" if c.get("permitida") else " — recusada pela política"))
            comum.diz(f"      ⚠ ENTRA COMO EXCEÇÃO: {_NOME_BASE[entra['base_legal']]} — nota: «{limpo(entra['nota']) or 'FALTA A NOTA'}» — risco {entra['risco']} — "
                      "sem uso comercial — crédito obrigatório")
        else:
            comum.diz(f"      licença: {limpo(B.rotulo_licenca(c)[0])} · risco {entra['risco']}" + (" (definido por --risco)" if (op or {}).get("risco") else "")
                      + ("" if c.get("uso_comercial") else " · SEM uso comercial"))
        for av in e["avisos"]:
            comum.diz(f"      ! {limpo(av)}")
        if e["ja"]:
            comum.diz(f"      = já está no registro como {e['ja']}: não será baixado de novo")
        if e["problema"]:
            comum.diz(f"      ✗ NÃO SERÁ BAIXADO: {e['problema']}")
    comum.diz(f"\n  total a baixar: {comum.tamanho_legivel(total)}" + (" (estimativa: do trecho só vem uma fatia)" if trecho else "")
              + f" · teto por arquivo: {teto_mb:g} MB · livre no disco: {livre / 1e9:.1f} GB".replace(".", ",") + f" · destino: {raiz / registro.PASTA_BRUTO}")


def _validar_midia(arq: Path, tipo: str) -> dict:
    """ffprobe (vídeo) ou PIL (imagem): o que foi baixado é mídia de verdade? Devolve largura/altura/fps/duracao e `ext`,
    a extensão que o CONTEÚDO pede (usada quando o provedor não informou uma extensão confiável)."""
    _da, _texto, video, _trava = comum.importar_kit()
    if tipo == "imagem":
        from PIL import Image
        try:
            with Image.open(arq) as im:
                im.verify()
            with Image.open(arq) as im:
                return {"largura": im.width, "altura": im.height, "fps": None, "duracao": None, "ext": _EXT_PIL.get(str(im.format).upper(), "")}
        except Exception as e:                                # PIL levanta vários tipos para arquivo que não é imagem
            raise comum.Erro(f"o arquivo baixado não é uma imagem legível ({type(e).__name__}).", "O provedor pode ter devolvido uma página de erro: refaça a busca com --sem-cache.")
    try:
        s = video.sondar(arq)
    except Exception as e:                                    # a mensagem do kit traz o caminho inteiro: aqui só interessa o que o ffprobe disse
        motivo = " ".join(str(e).replace(str(arq), "o arquivo").split())
        raise comum.Erro(f"o ffprobe não leu o arquivo baixado: {motivo[-220:]}", "O provedor pode ter devolvido uma página de erro: refaça a busca com --sem-cache.")
    if not s.get("largura") or not s.get("duracao"):
        raise comum.Erro("o arquivo baixado não tem trilha de vídeo ou tem duração zero.", "Escolha outra versão (--altura) ou outro candidato.")
    formato, codec = str(s.get("formato") or ""), str(s.get("codec") or "")
    ext = ("mp4" if "mp4" in formato else ("webm" if codec in ("vp8", "vp9", "av1") else "mkv") if "matroska" in formato else "ogv" if formato == "ogg"
           else "avi" if formato == "avi" else "mpg" if formato.startswith("mpeg") else "")
    return {"largura": s["largura"], "altura": s["altura"], "fps": round(float(s["fps"]), 3) if s.get("fps") else None, "duracao": round(float(s["duracao"]), 3), "ext": ext}


def _baixar_trecho(http: comum.Http, url: str, hosts, destino: Path, t0: float, t1: float, teto: int) -> None:
    """Só o intervalo [t0, t1] do vídeo remoto, copiando os fluxos (sem recodificar): o ffmpeg pede ao servidor apenas os
    bytes de que precisa. O corte cai no quadro-chave anterior a t0. Roda sob a trava do kit, com prazo.

    O ffmpeg lê a rede por conta própria, então a lista de hosts é imposta antes e durante: os redirecionamentos são
    resolvidos por este cliente (cada salto conferido), o ffmpeg recebe o endereço FINAL, não pode seguir nenhum outro
    (-max_redirects 0) e só fala https (-protocol_whitelist)."""
    _da, _texto, video, _trava = comum.importar_kit()
    final = http.resolver(url, hosts)
    p = urllib.parse.urlsplit(final)
    protocolos = "http,tcp" if p.scheme == "http" and (p.hostname or "") in ("127.0.0.1", "localhost", "::1") else "https,tls,tcp"   # http só no servidor da suíte
    args = ["-user_agent", comum.agente(), "-rw_timeout", "30000000", "-max_redirects", "0", "-protocol_whitelist", protocolos,
            "-ss", f"{t0:.3f}", "-t", f"{t1 - t0:.3f}", "-i", final,
            "-map", "0:v:0", "-map", "0:a:0?", "-c", "copy", "-avoid_negative_ts", "make_zero", "-fs", str(teto)]
    if destino.suffix in (".mp4", ".mov", ".m4v"):
        args += ["-movflags", "+faststart"]
    try:
        video.executar(args, destino, rotulo="baixar trecho de b-roll", inatividade=60, prazo=900)
    except Exception as e:
        if getattr(e, "codigo", None) is None:
            raise
        motivo = " ".join(comum.mascarar(e).split())
        raise comum.Erro(f"o ffmpeg não conseguiu ler o trecho de {p.hostname}: {motivo[-260:]}",
                         "Se o servidor não aceita leitura por faixas (Range) ou redirecionou no meio, baixe o arquivo inteiro (sem --trecho) "
                         "numa versão menor (--altura) e corte no tratar.py (--t0/--dur).")


def baixar(d, busca: dict, plano: list[dict], teto_mb: float = TETO_PADRAO_MB, trecho=None, base_legal: str = "licenca", nota: str | None = None,
           risco: str | None = None, pedido: str | None = None, http: comum.Http | None = None) -> list[dict]:
    """Executa o plano (só as entradas sem problema). Devolve [{n, id, arquivo, bytes, sha256} | {n, erro}].
    É a função que a linha de comando chama DEPOIS de conferir o código do plano aprovado (ver main)."""
    raiz = Path(d.raiz)
    http = http or comum.Http(prazo=60)
    teto = int(teto_mb * 1e6)
    saida = []
    for e in plano:
        c, arq = e["candidato"], e["arquivo"]
        if e["problema"]:
            saida.append({"n": e["n"], "erro": e["problema"], "sem_rede": bool(e.get("sem_rede"))})
            continue
        if e["ja"]:
            saida.append({"n": e["n"], "id": e["ja"], "repetido": True})
            continue
        prov = P.PROVEDORES[c["fonte"]]
        if shutil.disk_usage(raiz).free - (e["bytes"] or teto) < RESERVA_DISCO:
            saida.append({"n": e["n"], "erro": "pouco espaço em disco: o download deixaria menos de 2 GB livres. Libere espaço (broll/bruto/ antigos, renders de teste) e rode de novo"})
            continue
        ext = P.ext_segura(arq.get("formato"), c["tipo"])     # o que veio da API só vira nome de arquivo depois deste crivo
        marca = hashlib.sha1((arq["url"] + (f"#{trecho}" if trecho else "")).encode()).hexdigest()[:16]
        pasta_tmp = raiz / registro.PASTA_BRUTO / "_baixando"
        tmp = None
        try:
            if not comum.host_permitido(arq["url"], prov.hosts_arquivo):
                raise comum.Erro("endereço do arquivo fora dos hosts do provedor")
            if trecho:
                ext = ext if ext in _CONTAINERS_DE_COPIA else "mkv"
                tmp = pasta_tmp / f"{marca}.{ext}"
                comum.diz(f"  [{e['n']}] baixando o trecho {trecho[0]:g}–{trecho[1]:g} s de {urllib.parse.urlsplit(arq['url']).hostname}…")
                _baixar_trecho(http, arq["url"], prov.hosts_arquivo, tmp, trecho[0], trecho[1], teto)
                tamanho, sha = tmp.stat().st_size, registro.sha256_arquivo(tmp)
                if tamanho >= teto * 0.98:                       # o -fs do ffmpeg para de gravar no teto, sem erro: o trecho sairia cortado
                    raise comum.Erro(f"o trecho passou do teto de {teto_mb:g} MB e sairia cortado.", "Peça uma versão menor (--altura 720), um trecho mais curto ou suba --teto-mb.")
            else:
                tmp = pasta_tmp / f"{marca}.parcial"
                ultimo = [0.0]

                def progresso(feito, total, _u=ultimo, _n=e["n"]):
                    pct = feito / total if total else 0
                    if pct - _u[0] >= 0.25 and pct < 1:
                        _u[0] = pct
                        comum.diz(f"  [{_n}] {pct:.0%} ({comum.tamanho_legivel(feito)})")

                comum.diz(f"  [{e['n']}] baixando {comum.tamanho_legivel(e['bytes'])} de {urllib.parse.urlsplit(arq['url']).hostname}…")
                r = http.baixar(arq["url"], tmp, prov.hosts_arquivo, teto, esperado=e["bytes"], progresso=progresso)
                tamanho, sha = r["bytes"], r["sha256"]
                if r["retomado_de"]:
                    comum.diz(f"  [{e['n']}] retomado a partir de {comum.tamanho_legivel(r['retomado_de'])}")
            midia = _validar_midia(tmp, c["tipo"])
            ext = ext or midia.pop("ext", "")
            midia.pop("ext", None)
            if not ext:
                raise comum.Erro("não reconheci o formato do arquivo baixado (nem pela extensão informada, nem pelo conteúdo).",
                                 "Escolha outra versão (--altura) ou outro candidato.")
            repetido = registro.procurar(raiz, sha256=sha)
            if repetido:
                tmp.unlink()
                saida.append({"n": e["n"], "id": repetido[0]["id"], "repetido": True})
                continue
            item = {"tipo": c["tipo"], "titulo": c["titulo"], "consulta": busca.get("consulta"), "pedido_id": pedido or busca.get("pedido_id"), "fonte": c["fonte"],
                    "id_fonte": c["id_fonte"], "pagina_url": c["pagina_url"], "arquivo_url": arq["url"], "autor": c.get("autor"), "autor_url": c.get("autor_url"),
                    "licenca": c.get("licenca"), "licenca_url": c.get("licenca_url"), "base_legal": base_legal, "baixado_em": datetime.now().astimezone().isoformat(timespec="seconds"),
                    "sha256": sha, "bytes": tamanho, **midia, "trecho": None,
                    "notas": " ".join(x for x in ((nota or "").strip(), *(f"Aviso na busca: {a}." for a in e["avisos"])) if x)}
            if risco or c.get("risco") == "medio":
                item["risco"] = risco or "medio"
            sobra = None
            if trecho:                                         # `trecho` = intervalo da FONTE; `trecho_arquivo` = onde ele está dentro do que chegou
                pedida = trecho[1] - trecho[0]
                item["trecho"] = {"t0": trecho[0], "t1": trecho[1]}
                sobra = round(max(0.0, midia["duracao"] - pedida), 3)
                if sobra > 0.15:
                    item["trecho_arquivo"] = {"t0": sobra, "t1": midia["duracao"]}
            iid = registro.adicionar(raiz, item, mover_de=tmp, extensao="." + ext)
            gravado = registro.obter(raiz, iid)
            saida.append({"n": e["n"], "id": iid, "arquivo": gravado["arquivo"], "bytes": tamanho, "sha256": sha, **midia,
                          "exige_atribuicao": gravado["exige_atribuicao"], "atribuicao": gravado["atribuicao"],
                          "trecho": gravado.get("trecho"), "trecho_arquivo": gravado.get("trecho_arquivo"), "sobra": sobra})
        except (comum.Erro, registro.RegistroErro) as erro:
            sem_rede = getattr(erro, "codigo", None) == comum.SAIDA_SEM_REDE
            if tmp is not None and not sem_rede:
                tmp.unlink(missing_ok=True)                    # só o download interrompido fica no disco, para a retomada
            saida.append({"n": e["n"], "erro": comum.mascarar(erro), "sem_rede": sem_rede})
        except Exception as erro:                              # erro do kit (ffmpeg/ffprobe): vira mensagem, o resto do plano segue
            if tmp is not None:
                tmp.unlink(missing_ok=True)
            if getattr(erro, "codigo", None) is None:
                raise
            saida.append({"n": e["n"], "erro": comum.mascarar(erro)})
    with contextlib.suppress(OSError):
        (raiz / registro.PASTA_BRUTO / "_baixando").rmdir()   # só some se ficou vazia (um .parcial fica para a retomada)
    return saida


# ──────────────────────────────────────────────────── plano aprovado ↔ download ──
def _resumo_do_plano(plano: list[dict], opcoes: dict) -> dict:
    """O que identifica um plano: o que seria baixado, de onde, com que tamanho e licença, e sob que opções."""
    itens = []
    for e in plano:
        c, arq = e["candidato"], e["arquivo"] or {}
        itens.append({"n": e["n"], "fonte": c.get("fonte"), "id_fonte": c.get("id_fonte"), "pagina_url": c.get("pagina_url"), "arquivo_url": arq.get("url"),
                      "bytes": e.get("bytes"), "licenca_id": c.get("licenca_id"), "licenca": c.get("licenca"), "problema": bool(e.get("problema")), "ja": e.get("ja")})
    return {"opcoes": opcoes, "itens": itens}


def _codigo_do_plano(plano: list[dict], opcoes: dict) -> str:
    return hashlib.sha256(json.dumps(_resumo_do_plano(plano, opcoes), ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:8]


def gravar_plano(raiz: Path, busca: dict, plano: list[dict], opcoes: dict) -> str:
    """Guarda o plano mostrado em broll/_busca/_plano_<código>.json e devolve o código. O código sai do conteúdo: o mesmo
    plano dá o mesmo código, e qualquer diferença (outro arquivo, outro tamanho, outra licença) dá outro."""
    plano, opcoes = comum.mascarar_dados(plano), comum.mascarar_dados(opcoes)      # o plano vai para o disco: nenhuma chave nele
    codigo = _codigo_do_plano(plano, opcoes)
    dados = {"versao": 1, "codigo": codigo, "feito_em": datetime.now().astimezone().isoformat(timespec="seconds"), "feito_em_s": time.time(),
             "busca": {k: busca.get(k) for k in ("consulta", "slug", "feito_em", "pedido_id", "assinatura")}, "opcoes": opcoes, "itens": plano}
    arq = raiz / B.PASTA / f"_plano_{codigo}.json"
    arq.parent.mkdir(parents=True, exist_ok=True)
    tmp = arq.with_name(arq.name + ".parcial")
    tmp.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(arq)
    return codigo


def carregar_plano(raiz: Path, codigo: str) -> dict:
    """O plano gravado, conferido: existe, não foi mexido (o código confere com o conteúdo) e não venceu."""
    codigo = str(codigo).strip().lower()
    refazer = "Rode baixar.py --busca … --escolher … (sem --confirmar), mostre o plano ao usuário e confirme com o código novo."
    if not re.fullmatch(r"[0-9a-f]{8}", codigo):
        raise comum.Erro(f"--plano: {codigo[:24]!r} não é um código de plano.", "O código tem 8 caracteres e sai no fim do plano. " + refazer, comum.SAIDA_USO)
    arq = raiz / B.PASTA / f"_plano_{codigo}.json"
    if not arq.is_file():
        raise comum.Erro(f"não há plano {codigo} neste projeto ({arq.parent}).", refazer, comum.SAIDA_USO)
    try:
        dados = json.loads(arq.read_text(encoding="utf-8"))
        confere = _codigo_do_plano(dados["itens"], dados["opcoes"]) == codigo == dados.get("codigo")
    except (json.JSONDecodeError, KeyError, TypeError, AttributeError):
        confere = False
    if not confere:
        raise comum.Erro(f"o plano {codigo} foi alterado depois de gerado (o código não confere com o conteúdo): não vale como aprovação.", refazer)
    idade = time.time() - float(dados.get("feito_em_s") or 0)
    if idade > VALIDADE_PLANO or idade < -300:
        raise comum.Erro(f"o plano {codigo} é de {str(dados.get('feito_em'))[:16].replace('T', ' ')} e venceu (vale {VALIDADE_PLANO // 3600} h).", refazer)
    return dados


def conferir_plano(d, dados: dict, http: comum.Http) -> list[dict]:
    """Antes de baixar, olha de novo cada item do plano aprovado: o provedor continua disponível, o arquivo no servidor ainda
    tem o tamanho que o plano mostrou e o item não entrou no registro nesse meio-tempo. O que divergir ganha `problema`
    e NÃO é baixado — outro arquivo pede outro plano e outro «sim»."""
    raiz = Path(d.raiz)
    registrados = registro.carregar(raiz)["itens"]
    trecho = tuple(dados["opcoes"]["trecho"]) if dados["opcoes"].get("trecho") else None
    for e in dados["itens"]:
        if e.get("problema") or not e.get("arquivo"):
            continue
        c, arq = e["candidato"], e["arquivo"]
        prov = P.PROVEDORES[c["fonte"]](http)
        try:
            ok, motivo = prov.disponivel()
            if not ok:
                raise comum.Erro(motivo)
            info = http.tamanho(arq["url"], prov.hosts_arquivo)
        except comum.Erro as erro:
            e["problema"] = comum.mascarar(erro.mensagem)
            e["sem_rede"] = erro.codigo == comum.SAIDA_SEM_REDE
            continue
        if e.get("bytes") and info["bytes"] and info["bytes"] != e["bytes"]:
            e["problema"] = (f"o arquivo mudou no servidor desde o plano ({comum.tamanho_legivel(e['bytes'])} → {comum.tamanho_legivel(info['bytes'])}): "
                             "não é mais o que foi aprovado. Refaça o plano e mostre de novo ao usuário")
            continue
        for item in registrados:
            if item.get("pagina_url") == c.get("pagina_url") and item.get("arquivo_url") == arq["url"] and (item.get("trecho") or None) == ({"t0": round(trecho[0], 3), "t1": round(trecho[1], 3)} if trecho else None):
                e["ja"] = item.get("id")
    return dados["itens"]


def main(argv=None) -> int:
    ap = comum.Parser(prog="baixar.py", description="Baixa candidatos de uma busca para broll/bruto/ e registra a licença em broll/licencas.json. "
                      "Sem --confirmar monta só o plano (arquivo, origem, tamanho, licença) e imprime o código dele; o download é "
                      "`--plano CÓDIGO --confirmar` e executa exatamente o plano mostrado.",
                      epilog="A aprovação do download é do usuário, na conversa: mostre o plano, espere o «sim» e só então rode --plano CÓDIGO --confirmar. "
                             "Outro candidato, outra versão ou outro trecho = outro plano, outro código, outro «sim».")
    ap.add_argument("--busca", metavar="CONSULTA", help='a consulta feita em buscar.py ("sala de servidores"), o slug ou o caminho do .json')
    ap.add_argument("--escolher", metavar="N,N", help="números dos candidatos na folha de contato (ex.: 2,5 ou 1-3)")
    ap.add_argument("--plano", metavar="CÓDIGO", help="código de um plano já mostrado (sai no fim do plano); sem --confirmar, mostra o plano de novo")
    ap.add_argument("--confirmar", action="store_true", help="baixa o plano indicado em --plano (só depois da aprovação explícita do usuário)")
    ap.add_argument("--altura", type=int, metavar="PX", help="lado menor desejado (padrão: o do formato horizontal da DA, 1080); pega a menor versão que o alcança")
    ap.add_argument("--teto-mb", type=float, metavar="MB", help=f"tamanho máximo por arquivo (padrão {TETO_PADRAO_MB})")
    ap.add_argument("--trecho", metavar="A-B", help="baixa só o intervalo do vídeo (segundos ou mm:ss), sem recodificar — para filme longo")
    ap.add_argument("--base-legal", choices=("licenca", "citacao", "autorizacao"), help="exceção à política de licenças (exige --nota)")
    ap.add_argument("--nota", help="por que a exceção vale (o que é citado, quem autorizou)")
    ap.add_argument("--risco", choices=registro.RISCOS, help="sobrepõe o risco da política")
    ap.add_argument("--pedido", metavar="P003", help="id do pedido em roteiro/pauta.json")
    ap.add_argument("--json", action="store_true", help="saída em JSON")
    ap.add_argument("--projeto", metavar="PASTA", help="raiz do projeto (padrão: acha pela pasta atual)")
    a = ap.parse_args(argv)
    do_plano = ("busca", "escolher", "altura", "teto_mb", "trecho", "base_legal", "nota", "risco", "pedido")
    if a.plano:
        dadas = [f"--{n.replace('_', '-')}" for n in do_plano if getattr(a, n) is not None]
        if dadas:
            ap.error(f"{', '.join(dadas)} não pode(m) vir junto com --plano: essas escolhas já fazem parte do plano. Para mudar qualquer uma, monte outro plano (sem --plano)")
    else:
        if a.confirmar:
            ap.error("--confirmar exige --plano CÓDIGO: primeiro rode sem --confirmar, mostre o plano ao usuário e, depois do «sim», confirme com o código que saiu no fim do plano")
        if not a.busca or not a.escolher:
            ap.error("informe --busca e --escolher (para montar o plano) ou --plano CÓDIGO (para rever ou confirmar um plano)")
        if a.teto_mb is not None and a.teto_mb <= 0:
            ap.error("--teto-mb precisa ser maior que zero")
        if a.altura is not None and a.altura <= 0:
            ap.error("--altura precisa ser maior que zero")
    d, _da = comum.carregar_da(a.projeto)                    # Passo 0: sem DA, código 2
    raiz = Path(d.raiz)
    http = comum.Http(prazo=60)
    if a.plano:
        dados = carregar_plano(raiz, a.plano)
        codigo, op, busca = dados["codigo"], dados["opcoes"], dados["busca"]
        trecho = tuple(op["trecho"]) if op.get("trecho") else None
        plano = conferir_plano(d, dados, http) if a.confirmar else dados["itens"]
    else:
        busca = B.carregar_busca(raiz, a.busca)
        if not busca.get("candidatos"):
            raise comum.Erro(f"a busca {a.busca!r} não tem candidatos.", "Refaça com outros termos em buscar.py.")
        numeros = _numeros(a.escolher, len(busca["candidatos"]))
        trecho = _trecho(a.trecho)
        op = {"altura": a.altura, "teto_mb": a.teto_mb if a.teto_mb is not None else TETO_PADRAO_MB, "trecho": list(trecho) if trecho else None,
              "base_legal": a.base_legal or "licenca", "nota": a.nota, "risco": a.risco, "pedido": a.pedido}
        plano = planejar(d, busca, numeros, op["altura"], op["teto_mb"], trecho, op["base_legal"], op["nota"], http)
        plano = comum.mascarar_dados(plano)
        # plano sem nada a baixar não é gravado nem ganha código: não há o que aprovar
        codigo = gravar_plano(raiz, busca, plano, op) if any(not e["problema"] and not e["ja"] for e in plano) else None
    bloqueados = [e for e in plano if e["problema"]]
    baixaveis = [e for e in plano if not e["problema"] and not e["ja"]]
    so_rede = bool(bloqueados) and all(e.get("sem_rede") for e in bloqueados)        # nada foi recusado: só não houve resposta
    if not a.confirmar:
        if a.json:
            print(json.dumps(comum.mascarar_dados({"plano": codigo, "itens": [{k: v for k, v in e.items() if k != "candidato"} | {
                "titulo": e["candidato"]["titulo"], "fonte": e["candidato"]["fonte"], "licenca": e["candidato"]["licenca"],
                "entra_como": como_entra(e["candidato"], op)} for e in plano]}), ensure_ascii=False, indent=1))
        else:
            imprimir_plano(d, plano, op["teto_mb"], trecho, busca=busca, op=op)
            if baixaveis:
                comum.diz(f"\nCódigo deste plano: {codigo}  (vale {VALIDADE_PLANO // 3600} h)")
                comum.diz(f"Mostre este plano ao usuário. Só depois do «sim» dele: baixar.py --plano {codigo} --confirmar")
            elif so_rede:
                comum.diz("\nSem resposta dos servidores: nada deste plano pôde ser conferido. Confira a conexão e monte o plano de novo — "
                          "não há o que mostrar ao usuário ainda.", erro=True)
            elif bloqueados:
                comum.diz("\nNenhum item deste plano pode ser baixado (veja os ✗ acima): não há o que aprovar. Corrija e monte outro plano.", erro=True)
            else:
                comum.diz("\nTudo o que foi escolhido já está no registro: não há o que baixar.")
        return comum.SAIDA_SEM_REDE if so_rede else 1 if bloqueados else 0
    if not a.json:
        imprimir_plano(d, plano, op["teto_mb"], trecho, confirmar=True, busca=busca, codigo=codigo, op=op)
        comum.diz("")
    res = baixar(d, busca, plano, op["teto_mb"], trecho, op["base_legal"], op["nota"], op["risco"], op["pedido"], http)
    if a.json:
        print(json.dumps(comum.mascarar_dados(res), ensure_ascii=False, indent=1))
    else:
        for r in res:
            if r.get("erro"):
                comum.diz(f"  ✗ [{r['n']}] {r['erro']}")
            elif r.get("repetido"):
                comum.diz(f"  = [{r['n']}] já estava no registro como {r['id']}")
            else:
                dur = f" · {comum.duracao_legivel(r['duracao'])}" if r.get("duracao") else ""
                comum.diz(f"  ✓ [{r['n']}] {r['id']} → {r['arquivo']} · {comum.tamanho_legivel(r['bytes'])} · {r['largura']}×{r['altura']}{dur} · sha256 {r['sha256'][:12]}…")
                if r.get("trecho"):
                    pedida = r["trecho"]["t1"] - r["trecho"]["t0"]
                    if r.get("trecho_arquivo"):
                        ta = r["trecho_arquivo"]
                        comum.diz(f"        pedido: {pedida:g} s ({r['trecho']['t0']:g}–{r['trecho']['t1']:g} s da fonte); o arquivo tem {r['duracao']:.1f} s porque o corte caiu no quadro-chave "
                                  f"anterior. A parte aprovada são os segundos {ta['t0']:.1f}–{ta['t1']:.1f} do arquivo (trecho_arquivo): é o que o tratar.py usa por padrão.")
                    else:
                        comum.diz(f"        pedido: {pedida:g} s ({r['trecho']['t0']:g}–{r['trecho']['t1']:g} s da fonte); o arquivo veio com {r['duracao']:.1f} s.")
                if r.get("exige_atribuicao"):
                    comum.diz(f"        crédito obrigatório: {r['atribuicao']}")
        novos = [r["id"] for r in res if r.get("id") and not r.get("repetido")]
        if novos:
            comum.diz(f"\nRegistro: {raiz / registro.ARQUIVO} · créditos: {raiz / registro.CREDITOS}")
            comum.diz(f"Próximo passo: tratar.py {novos[0]} --formato horizontal vertical --previa")
    falhas = [r for r in res if r.get("erro")]
    return (comum.SAIDA_SEM_REDE if all(r.get("sem_rede") for r in falhas) else 1) if falhas else 0


if __name__ == "__main__":
    sys.exit(comum.rodar(main))
