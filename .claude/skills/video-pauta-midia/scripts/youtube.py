#!/usr/bin/env python3
"""youtube.py — busca, ficha (com a licença dos metadados) e download SÓ DO TRECHO de um vídeo do YouTube, pelo yt-dlp.

    youtube.py buscar "entrevista alan turing documentário" [-n 5] [--cc] [--com-licenca] [--pedido P001]
    youtube.py info https://www.youtube.com/watch?v=…
    youtube.py baixar <url> --t0 1:10 --t1 1:25 [--altura 720] [--base-legal citacao --nota "…"] [--pedido P001]   # só o PLANO
    youtube.py baixar <url> --t0 1:10 --t1 1:25 … --confirmar                                                      # baixa e registra

Nunca baixa o vídeo inteiro: --t0 e --t1 são obrigatórios e a duração tem teto (30 s por padrão). O trecho sai em MP4
H.264/AAC, altura ≤ 1080, em broll/bruto/Y###.mp4, registrado em broll/licencas.json pelo módulo da video-broll
(fonte "youtube", autor = canal, licença, base legal, risco, trecho). O download roda sob a trava do kit."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
from datetime import date
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import base  # noqa: E402
import roteiro  # noqa: E402

RE_ID = re.compile(r"(?:youtu\.be/|youtube\.com/(?:watch\?(?:[^#]*&)?v=|shorts/|embed/|live/))([A-Za-z0-9_-]{11})")
CC_BY_URL = "https://creativecommons.org/licenses/by/4.0/"   # para onde a ajuda do YouTube aponta (references/direitos.md)
TERMOS_URL = "https://www.youtube.com/static?template=terms"
FILTRO_CC = "EgIwAQ%3D%3D"                                    # parâmetro `sp` do filtro «Creative Commons» da busca do YouTube
TETO_PADRAO = 30.0
TETO_MAXIMO = {"citacao": 60.0, "licenca": 600.0, "autorizacao": 600.0, "proprio": 600.0}
DIAS_VELHO = 60
_SEM_REDE = r"getaddrinfo|name or service not known|nodename nor servname|network is unreachable|temporary failure in name resolution|timed out|connection refused"
_BLOQUEIO = r"sign in to confirm|not a bot|http error 429|too many requests|http error 403"
_VELHO = r"nsig extraction failed|signature extraction failed|unable to extract|requested format is not available|please report this issue|unsupported url"
_INDISPONIVEL = r"private video|video unavailable|has been removed|not available in your country|members-only|age-restricted|this live event"


def ytdlp() -> str:
    caminho = os.environ.get("VIDEO_PAUTA_YTDLP") or shutil.which("yt-dlp") or "/opt/homebrew/bin/yt-dlp"
    if not Path(caminho).is_file():
        raise base.Erro("o yt-dlp não está instalado.", "Instale com: brew install yt-dlp  (esta skill não instala nem atualiza ferramenta do sistema).")
    return caminho


def versao() -> tuple[str, int | None]:
    """(versão do yt-dlp, idade em dias ou None)."""
    try:
        v = subprocess.run([ytdlp(), "--version"], capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=30).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return "desconhecida", None
    m = re.match(r"(\d{4})\.(\d{1,2})\.(\d{1,2})", v)
    try:
        return v, (date.today() - date(int(m.group(1)), int(m.group(2)), int(m.group(3)))).days if m else None
    except ValueError:
        return v, None


def _falha(stderr: str) -> base.Erro:
    """Traduz o erro do yt-dlp numa mensagem com o que fazer."""
    linhas = [x for x in (stderr or "").splitlines() if x.strip()]
    motivo = next((x for x in reversed(linhas) if "ERROR" in x), linhas[-1] if linhas else "sem mensagem")
    motivo, baixo = " ".join(motivo.split())[:300], (stderr or "").lower()
    v, dias = versao()
    idade = f"yt-dlp {v}" + (f", de {dias} dia(s) atrás" if dias is not None else "")
    atualizar = f"Atualize o yt-dlp você mesmo (brew upgrade yt-dlp, ou pipx upgrade yt-dlp) e repita — instalado: {idade}; esta skill não atualiza ferramenta do sistema."
    if re.search(_SEM_REDE, baixo):
        return base.Erro(f"sem rede para falar com o YouTube: {motivo}", "Confira a conexão e repita.", base.SEM_REDE)
    if re.search(_BLOQUEIO, baixo):
        return base.Erro(f"o YouTube bloqueou o pedido (verificação antirrobô ou limite de pedidos): {motivo}",
                         "Espere alguns minutos e repita. Se persistir: " + atualizar + " A skill não usa os cookies da sua conta; se quiser usá-los, a decisão e o comando são seus.")
    if re.search(_INDISPONIVEL, baixo):
        return base.Erro(f"vídeo indisponível: {motivo}", "Privado, removido, restrito por idade ou por país: escolha outro candidato.")
    if re.search(_VELHO, baixo) or (dias is not None and dias > DIAS_VELHO):
        return base.Erro(f"o yt-dlp não conseguiu ler o YouTube: {motivo}", atualizar)
    return base.Erro(f"o yt-dlp falhou: {motivo}", f"Repita em alguns minutos; instalado: {idade}.")


def _json(args: list[str], prazo: int = 120):
    try:
        r = subprocess.run([ytdlp(), "--no-warnings", "--socket-timeout", "20", *args], capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=prazo)
    except subprocess.TimeoutExpired:
        raise base.Erro(f"o yt-dlp não respondeu em {prazo} s.", "Confira a conexão e repita.", base.SEM_REDE)
    if r.returncode != 0:
        raise _falha(r.stderr)
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        raise _falha(r.stderr or "o yt-dlp não devolveu JSON")


def url_canonica(url: str) -> str:
    m = RE_ID.search(url) or re.fullmatch(r"([A-Za-z0-9_-]{11})", url.strip())
    if not m:
        raise base.Erro(f"não reconheci um vídeo do YouTube em {url[:120]!r}.", "Passe o link do vídeo (youtube.com/watch?v=…, youtu.be/… ou /shorts/…). Só YouTube nesta versão.", base.USO)
    return f"https://www.youtube.com/watch?v={m.group(1)}"


def info(url: str) -> dict:
    b = _json(["--dump-single-json", "--no-playlist", "--skip-download", url_canonica(url)])
    d = str(b.get("upload_date") or "")
    alturas = sorted({int(f["height"]) for f in b.get("formats") or [] if f.get("height") and f.get("vcodec") not in (None, "none")})
    return {"id": b.get("id"), "titulo": b.get("title"), "canal": b.get("channel") or b.get("uploader"), "canal_url": b.get("channel_url") or b.get("uploader_url"),
            "duracao": b.get("duration"), "url": url_canonica(b.get("webpage_url") or url), "licenca_meta": b.get("license"),
            "publicado": f"{d[:4]}-{d[4:6]}-{d[6:]}" if len(d) == 8 else None, "visualizacoes": b.get("view_count"),
            "ao_vivo": bool(b.get("is_live")) or b.get("live_status") in ("is_live", "is_upcoming"), "idade": b.get("age_limit") or 0,
            "musica": bool(b.get("track")) or "Music" in (b.get("categories") or []), "alturas": [h for h in alturas if h <= 1080]}


def avaliar(meta: dict, base_legal: str | None = None, dur: float | None = None) -> dict:
    """O que a licença dos metadados permite pela política do registro, a base legal que cabe e o risco."""
    reg = base.registro()
    lic = meta.get("licenca_meta") or ""
    if re.search(r"creative commons", lic, re.I) and re.search(r"attribution", lic, re.I):
        licenca, lurl = "CC BY", CC_BY_URL
    elif lic and not re.search(r"standard youtube", lic, re.I):
        licenca, lurl = lic, None
    else:
        licenca, lurl = "Licença padrão do YouTube", TERMOS_URL
    ficha = reg.avaliar_licenca(licenca, lurl, "youtube")
    avisos = []
    if ficha["permitida"]:
        avisos.append("a marcação Creative Commons é declaração de quem enviou: confira se o canal é o titular (reenvio de TV ou de outro canal não vale)")
    if meta.get("musica"):
        avisos.append("vídeo de música: o Content ID costuma reivindicar até trecho curto")
    if meta.get("idade"):
        avisos.append("vídeo com restrição de idade")
    b = base_legal or ("licenca" if ficha["permitida"] else None)
    fracao = dur / meta["duracao"] if dur and meta.get("duracao") else None
    if b == "citacao":
        risco = "alto" if meta.get("musica") or (dur or 0) > 30 or (fracao or 0) > 0.2 else "medio"
        if fracao and fracao > 0.2:
            avisos.append(f"o trecho é {fracao:.0%} do vídeo: citação é passagem curta, na medida do comentário")
    else:
        risco = {"licenca": ficha["risco"], "autorizacao": "baixo", "proprio": "baixo"}.get(b, "alto")
    return {"licenca": licenca, "licenca_url": lurl, "nome": ficha["nome"], "permitida": ficha["permitida"], "base_legal": b, "risco": risco, "avisos": avisos}


def _ficha(meta: dict, av: dict) -> list[str]:
    return [f"  título:   {meta['titulo']}", f"  canal:    {meta['canal']}" + (f"  ({meta['canal_url']})" if meta.get("canal_url") else ""),
            f"  duração:  {base.relogio(meta['duracao'])}" + (f" · publicado em {meta['publicado']}" if meta.get("publicado") else ""),
            f"  licença:  {av['nome']}" + (f"  (metadados: «{meta['licenca_meta']}»)" if meta.get("licenca_meta") else "  (os metadados não trazem licença de reuso)"),
            "  uso:      " + ("permitido pela licença, com crédito" if av["permitida"] else "sem licença de reuso — só com autorização, se o canal for seu, ou como citação curta com crédito na tela"),
            f"  link:     {meta['url']}"] + [f"  aviso:    {x}" for x in av["avisos"]]


def cmd_info(a) -> int:
    meta = info(a.url)
    av = avaliar(meta)
    if a.json:
        base.diz(json.dumps({**meta, "avaliacao": av}, ensure_ascii=False, indent=2))
    else:
        base.diz("\n".join(_ficha(meta, av)))
        base.diz(f"  alturas:  {', '.join(map(str, meta['alturas'])) or 'não informadas'}" + ("  · AO VIVO (não dá para baixar trecho)" if meta["ao_vivo"] else ""))
    return base.OK


def cmd_buscar(a) -> int:
    n = max(1, min(a.n, 15))
    if a.cc:
        alvo = f"https://www.youtube.com/results?search_query={urllib.parse.quote_plus(a.consulta)}&sp={FILTRO_CC}"
    else:
        alvo = f"ytsearch{n}:{a.consulta}"
    b = _json(["--flat-playlist", "--dump-single-json", "--playlist-end", str(n), alvo])
    candidatos = []
    for e in (b.get("entries") or [])[:n]:
        if not e or not e.get("id") or (e.get("ie_key") or "Youtube") != "Youtube":
            continue
        c = {"id": e["id"], "titulo": e.get("title"), "canal": e.get("channel") or e.get("uploader"), "duracao": e.get("duration"),
             "url": f"https://www.youtube.com/watch?v={e['id']}", "licenca": None, "permitida": None, "risco": None}
        if a.cc or a.com_licenca:                             # a busca não traz licença: cada candidato é conferido nos metadados
            try:
                av = avaliar(info(c["url"]))
                c.update(licenca=av["nome"], permitida=av["permitida"], risco=av["risco"] if av["permitida"] else "medio a alto (só como citação)")
            except base.Erro as erro:
                c["licenca"] = f"não conferida ({erro.mensagem[:60]})"
        candidatos.append(c)
    if a.pedido:
        projeto = base.achar_projeto(a.projeto)
        it = roteiro.alterar(projeto, a.pedido, consulta=a.consulta)
        if it["status"] == "pendente" and candidatos:
            roteiro.alterar(projeto, a.pedido, status="candidatos")
        roteiro._gravar(projeto / "roteiro" / "_candidatos" / f"{it['id']}.json", json.dumps({"consulta": a.consulta, "cc": a.cc, "candidatos": candidatos}, ensure_ascii=False, indent=2) + "\n")
    if a.json:
        base.diz(json.dumps(candidatos, ensure_ascii=False, indent=2))
        return base.OK
    if not candidatos:
        base.diz("nenhum resultado. Tente outra consulta" + (" ou tire o --cc (pouca coisa no YouTube tem licença Creative Commons)." if a.cc else "."))
        return base.OK
    for i, c in enumerate(candidatos, 1):
        lic = f"\n     licença: {c['licenca']} · risco: {c['risco']}" if c["licenca"] else ""
        base.diz(f"{i:>2}. {c['titulo']}\n     {c['canal']} · {base.relogio(c['duracao'])} · {c['url']}{lic}")
    if not (a.cc or a.com_licenca):
        base.diz("A busca não traz licença: rode «youtube.py info <url>» (ou repita com --com-licenca) antes de mostrar os candidatos ao usuário.")
    return base.OK


def _credito_reproducao(autor: str | None, sufixo: str = " / YouTube") -> str:
    autor = " ".join((autor or "").split()) or "canal não informado"
    return "Reprodução: " + (autor if len(autor) <= 40 else autor[:39].rstrip() + "…") + sufixo


def cmd_baixar(a) -> int:
    t0, t1 = base.segundos(a.t0), base.segundos(a.t1)
    if t0 is None or t1 is None:
        raise base.Erro("faltou o trecho: esta skill nunca baixa o vídeo inteiro.", "Informe --t0 e --t1 (segundos, mm:ss ou hh:mm:ss) do pedaço que o roteiro pede.", base.USO)
    if t0 < 0 or t1 <= t0:
        raise base.Erro(f"trecho inválido: {base.relogio(t0)}–{base.relogio(t1)}.", "t1 precisa ser maior que t0.", base.USO)
    if not 144 <= a.altura <= 1080:
        raise base.Erro(f"altura {a.altura} fora do intervalo.", "Use de 144 a 1080 (a casa não baixa acima de 1080).", base.USO)
    dur = t1 - t0
    projeto = base.achar_projeto(a.projeto)
    d = base.exigir_da(projeto)
    reg = base.registro()
    projeto = Path(d.raiz) if hasattr(d, "raiz") else projeto
    meta = info(a.url)
    av = avaliar(meta, a.base_legal, dur)
    b = av["base_legal"]
    if meta["ao_vivo"]:
        raise base.Erro("o vídeo é uma transmissão ao vivo ou agendada.", "Espere o vídeo virar gravação ou escolha outro.")
    if meta.get("duracao") and t1 > meta["duracao"] + 0.5:
        raise base.Erro(f"o trecho termina em {base.relogio(t1)}, mas o vídeo tem {base.relogio(meta['duracao'])}.", codigo=base.USO)
    if b is None:
        raise base.Erro(f"«{meta['titulo']}» está sob a licença padrão do YouTube (todos os direitos reservados).",
                        "Só entra com base legal declarada: --base-legal citacao (trecho curto, para comentar ou criticar, com crédito na tela), "
                        "autorizacao (o titular autorizou) ou proprio (o canal é seu) — sempre com --nota dizendo por quê. Leia references/direitos.md; a decisão é do usuário.")
    if b == "licenca" and not av["permitida"]:
        raise base.Erro("--base-legal licenca não vale aqui: os metadados não trazem licença de reuso.", "Use citacao, autorizacao ou proprio, com --nota.")
    if b != "licenca" and not (a.nota or "").strip():
        raise base.Erro(f"--base-legal {b} exige --nota.", "Diga o que é citado e por quê, quem autorizou e onde está a prova, ou por que o canal é da casa.", base.USO)
    teto = a.teto if a.teto is not None else TETO_PADRAO
    if teto > TETO_MAXIMO[b]:
        raise base.Erro(f"teto de {teto:g} s acima do máximo para base legal «{b}» ({TETO_MAXIMO[b]:g} s).", "Divida em trechos menores ou reveja a base legal.", base.USO)
    if dur > teto + 1e-6:
        raise base.Erro(f"o trecho tem {dur:g} s e o teto por trecho é {teto:g} s.",
                        f"Encurte o trecho ou, se o uso justificar, repita com --teto (máximo {TETO_MAXIMO[b]:g} s para «{b}»).")
    trecho = {"t0": round(t0, 3), "t1": round(t1, 3)}
    repetido = [it for it in reg.procurar(projeto, fonte="youtube", id_fonte=meta["id"]) if it.get("trecho") == trecho]
    pedido = roteiro.carregar(projeto) and roteiro._achar(roteiro.carregar(projeto), a.pedido) if a.pedido else None
    risco = a.risco or av["risco"]
    plano = {"video": meta, "trecho": trecho, "duracao_trecho": round(dur, 3), "altura_max": a.altura, "base_legal": b, "risco": risco,
             "licenca": av["nome"], "destino": "broll/bruto/Y###.mp4", "pedido": a.pedido, "ja_baixado": repetido[0]["id"] if repetido else None}
    if not a.json:
        base.diz("\n".join(_ficha(meta, av)))
        base.diz(f"  trecho:   {base.relogio(t0)}–{base.relogio(t1)} ({dur:g} s de {base.relogio(meta['duracao'])}) · até {a.altura}p · MP4 H.264/AAC")
        base.diz(f"  base:     {b} · risco {risco}" + (f" · nota: {a.nota}" if a.nota else "") + (f" · pedido {a.pedido}" if a.pedido else ""))
    if repetido:
        base.diz(json.dumps(plano, ensure_ascii=False, indent=2) if a.json else f"já está no registro como {repetido[0]['id']} ({repetido[0].get('arquivo')}): nada a baixar.")
        return base.OK
    if not a.confirmar:
        base.diz(json.dumps({**plano, "baixado": False}, ensure_ascii=False, indent=2) if a.json else
                 "PLANO — nada foi baixado. Mostre esta ficha ao usuário e, com o «sim» dele, repita o comando com --confirmar.")
        return base.OK
    if pedido is not None and pedido["status"] not in ("aprovado", "baixado", "tratado"):
        raise base.Erro(f"{pedido['id']} está «{pedido['status']}» na pauta: ainda não foi aprovado pelo usuário.",
                        f"Mostre a ficha, espere o «sim» e marque: roteiro.py definir {pedido['id']} --status aprovado. Depois repita com --confirmar.")
    _da, video, trava = base.kit()
    bruto = projeto / reg.PASTA_BRUTO
    bruto.mkdir(parents=True, exist_ok=True)
    prefixo = f"_entrando_{os.getpid()}"
    ffmpeg = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"
    cmd = [ytdlp(), "--no-playlist", "--no-progress", "--no-warnings", "--no-mtime", "--socket-timeout", "30", "--retries", "3",
           "--download-sections", f"*{t0:.3f}-{t1:.3f}", "--force-keyframes-at-cuts",
           "-f", f"bv*[height<={a.altura}]+ba/b[height<={a.altura}]", "-S", f"vcodec:h264,res:{a.altura},acodec:aac",
           "--merge-output-format", "mp4", "--ffmpeg-location", str(Path(ffmpeg).parent), "-o", str(bruto / f"{prefixo}.%(ext)s"), meta["url"]]
    try:
        r = trava.rodar(cmd, rotulo="yt-dlp: trecho do YouTube", capturar=True, inatividade=180, prazo=1200)
        if r.codigo != 0:
            if r.motivo:
                raise base.Erro(f"o download parou ({trava.descrever_vigia(r, 'yt-dlp')}).", "Confira a conexão e repita; trecho menor ou --altura menor ajudam.")
            raise _falha(r.stderr)
        achados = [p for p in sorted(bruto.glob(prefixo + ".*")) if p.suffix.lower() in (".mp4", ".mkv", ".webm", ".mov")]
        if not achados:
            raise base.Erro("o yt-dlp terminou sem gravar o trecho.", "Repita; se persistir, atualize o yt-dlp (brew upgrade yt-dlp).")
        arq = achados[0]
        s = video.sondar(arq)
        audio = (s.get("audio") or {}).get("codec")
        if arq.suffix.lower() != ".mp4" or s.get("codec") != "h264" or (audio and audio != "aac") or s.get("pix_fmt") not in ("yuv420p", "yuvj420p"):
            novo = bruto / f"{prefixo}_h264.mp4"                 # o que não veio em H.264/AAC é convertido aqui, sob a mesma trava
            video.executar(["-i", str(arq), "-map", "0:v:0", "-map", "0:a:0?", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
                            "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", "-threads", "2"], novo, rotulo="trecho para H.264/AAC")
            arq, s = novo, video.sondar(novo)
        if not s.get("largura") or not s.get("duracao") or s["altura"] > 1080 and s["largura"] > 1080:
            raise base.Erro("o arquivo baixado não é um vídeo válido de até 1080p.", "Repita com outra --altura.")
        if s["duracao"] > dur + 3:
            raise base.Erro(f"o arquivo veio com {s['duracao']:.1f} s para um trecho de {dur:g} s.", "O yt-dlp não cortou o trecho: atualize-o (brew upgrade yt-dlp) e repita.")
        item = {"prefixo": "Y", "fonte": "youtube", "tipo": "video", "titulo": meta["titulo"], "id_fonte": meta["id"], "pagina_url": meta["url"],
                "autor": meta["canal"], "autor_url": meta.get("canal_url"), "licenca": av["licenca"], "licenca_url": av["licenca_url"],
                "licenca_original": meta.get("licenca_meta"), "base_legal": b, "risco": risco, "trecho": trecho, "pedido_id": a.pedido,
                "notas": a.nota, "baixado_em": reg.agora_iso(), "sha256": reg.sha256_arquivo(arq), "bytes": arq.stat().st_size,
                "largura": s["largura"], "altura": s["altura"], "fps": round(float(s["fps"]), 3) if s.get("fps") else None, "duracao": round(float(s["duracao"]), 3)}
        if b == "citacao":
            item["credito_tela"] = _credito_reproducao(meta["canal"])
        mid = reg.adicionar(projeto, {k: v for k, v in item.items() if v is not None}, mover_de=arq, extensao=".mp4")
    finally:
        for resto in bruto.glob(prefixo + "*"):
            resto.unlink(missing_ok=True)
    reg.creditos_md(projeto)
    gravado = reg.obter(projeto, mid)
    if a.pedido:
        roteiro.alterar(projeto, a.pedido, midia=mid, status="baixado", url=meta["url"], t0=trecho["t0"], t1=trecho["t1"])
    if a.json:
        base.diz(json.dumps({**plano, "baixado": True, "id": mid, "arquivo": gravado["arquivo"]}, ensure_ascii=False, indent=2))
        return base.OK
    base.diz(f"baixado: {mid} → {gravado['arquivo']} ({s['largura']}x{s['altura']}, {s['duracao']:.1f} s, {gravado['bytes'] / 1e6:.1f} MB)")
    base.diz(f"crédito na tela: {gravado.get('credito_tela')}\ncrédito na descrição: {gravado.get('atribuicao')}  (broll/creditos.md atualizado)")
    base.diz(f"próximo passo — moldura e crédito na direção de arte: python3 \"$CRIABR_SKILLS\"/video-broll/scripts/tratar.py {mid} --formato horizontal --moldura")
    return base.OK


def main(argv=None) -> int:
    ap = base.Parser(prog="youtube.py", description="Busca, ficha e download só do trecho de vídeos do YouTube (yt-dlp), com registro de licença.")
    sub = ap.add_subparsers(dest="cmd", required=True, parser_class=base.Parser)
    p = sub.add_parser("buscar", help="procura vídeos (não baixa nada)")
    p.add_argument("consulta")
    p.add_argument("-n", type=int, default=5, help="quantos resultados (padrão 5, máximo 15)")
    p.add_argument("--cc", action="store_true", help="só vídeos com licença Creative Commons (filtro da busca + conferência nos metadados)")
    p.add_argument("--com-licenca", action="store_true", help="confere a licença de cada resultado nos metadados (mais lento)")
    p.add_argument("--pedido", metavar="P###", help="item da pauta: guarda a consulta e os candidatos e marca «candidatos»")
    p.set_defaults(f=cmd_buscar)
    p = sub.add_parser("info", help="ficha do vídeo, com a licença dos metadados")
    p.add_argument("url")
    p.set_defaults(f=cmd_info)
    p = sub.add_parser("baixar", help="plano do trecho; com --confirmar, baixa e registra")
    p.add_argument("url")
    p.add_argument("--t0", help="início do trecho (segundos, mm:ss ou hh:mm:ss)")
    p.add_argument("--t1", help="fim do trecho")
    p.add_argument("--altura", type=int, default=720, help="altura máxima em pixels (padrão 720; máximo 1080)")
    p.add_argument("--teto", type=float, help=f"teto de duração do trecho em segundos (padrão {TETO_PADRAO:g}; máximo 60 em citação, 600 nas outras bases)")
    p.add_argument("--base-legal", choices=("licenca", "citacao", "autorizacao", "proprio"), help="padrão: licenca, quando os metadados trazem Creative Commons")
    p.add_argument("--nota", help="obrigatória em citacao, autorizacao e proprio: o que é citado e por quê, quem autorizou, por que é da casa")
    p.add_argument("--risco", choices=("baixo", "medio", "alto"), help="sobrepõe o risco calculado")
    p.add_argument("--pedido", metavar="P###", help="item da pauta que este trecho atende (precisa estar «aprovado» para baixar)")
    p.add_argument("--confirmar", action="store_true", help="baixa de verdade — só depois do «sim» do usuário na conversa")
    p.set_defaults(f=cmd_baixar)
    for s in sub.choices.values():
        s.add_argument("--projeto", metavar="PASTA", help="raiz do projeto (padrão: acha pela pasta atual)")
        s.add_argument("--json", action="store_true", help="saída em JSON")
    a = ap.parse_args(argv)
    return a.f(a)


if __name__ == "__main__":
    sys.exit(base.rodar(main))
