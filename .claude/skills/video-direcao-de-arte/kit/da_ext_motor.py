#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""da_ext_motor.py — extensão do da.py que liga o núcleo ao motor de render HTML (motor/render.mjs).

Subcomandos acrescentados
    prancha          gera da/prancha.png (e prancha_vertical.png): a prancha de direção de arte que o cliente aprova
    teste-movimento  gera da/teste_movimento.mp4 (~4 s, resolução reduzida): título + GC + barras com as curvas da DA
    render           repassa argumentos ao motor (node motor/render.mjs …) já com --da e sob a trava global

Como módulo (import da_ext_motor as motor)
    motor.achar_node()                       caminho do node (VIDEO_OPS_NODE, PATH, ~/.nvm, /opt/homebrew)
    motor.render(["--cena", "titulo", …], da=d)   roda o motor sob a trava; devolve o CompletedProcess
    motor.imagem_de_teste(destino)           quadro sintético 960×540 para provar o tratamento quando não há referência
    motor.gerar_prancha(d, formatos=("horizontal", "vertical"), referencia=None)
"""
from __future__ import annotations

import glob
import json
import math
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True     # D9: nada de __pycache__ dentro da skill (trava.py apaga o que já tiver nascido)
KIT = Path(__file__).resolve().parent
if str(KIT) not in sys.path:
    sys.path.insert(0, str(KIT))
import da  # noqa: E402
import trava  # noqa: E402

MOTOR = KIT / "motor"
RENDER_MJS = MOTOR / "render.mjs"
KIT_FINAL = da.KIT_FINAL


# ────────────────────────────────────────────────────────────────── node ──
def achar_node() -> str:
    """node: VIDEO_OPS_NODE > PATH > ~/.nvm/versions/node/*/bin/node (mais novo) > /opt/homebrew/bin/node."""
    env = os.environ.get("VIDEO_OPS_NODE")
    if env and Path(env).is_file():
        return env
    no_path = shutil.which("node")
    if no_path:
        return no_path
    candidatos = sorted(glob.glob(os.path.expanduser("~/.nvm/versions/node/*/bin/node")),
                        key=lambda p: [int(x) if x.isdigit() else 0 for x in Path(p).parts[-3].lstrip("v").split(".")], reverse=True)
    for c in candidatos + ["/opt/homebrew/bin/node", "/usr/local/bin/node"]:
        if Path(c).is_file():
            return c
    raise da.DAErro("node não encontrado (o motor de render precisa do Node 18+).",
                    dica="Instale com nvm ou `brew install node`, ou aponte VIDEO_OPS_NODE para o executável.")


INATIVIDADE_MOTOR = 180.0       # 2ª linha de defesa (CPU da árvore); a 1ª é o --inatividade do próprio motor (120 s)
PRAZO_VALIDACAO = 60.0          # a conferência (--validar) só lê a DA e importa as cenas no node: sem browser, sem ffmpeg


def _conferir_fora_da_trava(cmd: list[str], cwd, capturar: bool = True) -> trava.Resultado:
    """Roda o motor em modo `--validar` SEM entrar na trava: é leve (um node que confere argumentos, DA, cenas e
    params e sai; não abre Chromium nem ffmpeg). Devolve um trava.Resultado (124 se passar de PRAZO_VALIDACAO)."""
    t0 = time.monotonic()
    try:
        p = subprocess.run(cmd, cwd=cwd, env=os.environ.copy(), stdin=subprocess.DEVNULL, capture_output=capturar,
                           text=True, timeout=PRAZO_VALIDACAO)
        return trava.Resultado(cmd, p.returncode, p.stdout, p.stderr, None, time.monotonic() - t0)
    except subprocess.TimeoutExpired as e:
        def txt(b):
            return b.decode("utf-8", "replace") if isinstance(b, bytes) else (b or "")
        aviso = f"erro: a conferência dos argumentos do motor não terminou em {PRAZO_VALIDACAO:.0f} s (cena com laço sem fim no nível do módulo?)\n"
        return trava.Resultado(cmd, trava.SAIDA_VIGIA, txt(e.stdout), txt(e.stderr) + aviso, "prazo", time.monotonic() - t0)


def render(args: list[str], da_obj: da.DA | None = None, da_json=None, cwd=None, rotulo: str | None = None,
           capturar: bool = False, espera_max: float | None = None, inatividade: float | None = INATIVIDADE_MOTOR,
           validar_antes: bool | None = None):
    """Roda `node motor/render.mjs --da <da.json> <args>` sob a trava global (reentrante). Não levanta em rc ≠ 0.

    Devolve um trava.Resultado (mesma leitura de um CompletedProcess: .returncode, .stdout, .stderr — os dois
    últimos só com capturar=True). O node roda em grupo de processos próprio: SIGINT/SIGTERM/SIGHUP neste processo
    matam node, Chromium e ffmpeg antes de a trava ser solta; `inatividade` segundos sem CPU na árvore também
    (returncode 124, .motivo == 'inatividade').

    Erro de uso não espera na fila: com `--validar` nos argumentos o motor só confere e sai, SEM entrar na trava;
    e, quando a trava está ocupada por outro processo, a conferência roda antes de entrar na fila — parâmetro
    errado volta em menos de 1 s com código 64, em vez de depois de minutos de espera. `validar_antes` força
    (True) ou dispensa (False) essa conferência; o padrão (None) confere só quando haveria espera."""
    if not RENDER_MJS.is_file():
        raise da.DAErro(f"motor não encontrado em {RENDER_MJS}")
    if not (MOTOR.parent / "node_modules" / "playwright-core").is_dir():
        raise da.DAErro("falta node_modules/playwright-core no kit.",
                        dica=f"Rode: cd {KIT_FINAL} && npm install (ou copie node_modules/playwright-core de outro motor da casa).")
    alvo = str(da_obj.caminho) if da_obj is not None else (str(da_json) if da_json else None)
    args = [str(a) for a in args]
    cmd = [achar_node(), str(RENDER_MJS)]
    if alvo and "--da" not in args and not any(a.startswith("--da=") for a in args):
        cmd += ["--da", alvo]                    # na frente: um `--quadro` sem valor no fim não engole o --da
    cmd += args
    if "--validar" in args or "--help" in args:  # nada pesado vai rodar: não há por que esperar a fila
        return _conferir_fora_da_trava(cmd, cwd, capturar=capturar)
    if validar_antes is None:
        validar_antes = trava.sob_trava() is None and not trava.estado()["livre"]
    if validar_antes:
        v = _conferir_fora_da_trava([*cmd, "--validar"], cwd)
        if v.returncode != 0:                    # erro de uso (64), DA ausente (2) ou inválida: volta já, sem fila
            if not capturar:
                sys.stdout.write(v.stdout or "")
                sys.stderr.write(v.stderr or "")
                sys.stdout.flush()
                sys.stderr.flush()
            return v
    if inatividade is INATIVIDADE_MOTOR:
        inatividade = trava.inatividade_padrao(INATIVIDADE_MOTOR)
    r = trava.rodar(cmd, rotulo=rotulo or "motor de render", espera_max=espera_max, capturar=capturar,
                    cwd=cwd, env=os.environ.copy(), inatividade=inatividade)
    if r.motivo:
        print(f"erro: {trava.descrever_vigia(r, rotulo or 'motor de render')}", file=sys.stderr)
    return r


# ─────────────────────────────────────────────────────── referência de imagem ──
def imagem_de_teste(destino, largura: int = 960, altura: int = 540) -> Path:
    """Quadro sintético para provar o tratamento: céu em degradê, horizonte quente, tom de pele, rampa de cinza
    e manchas de cor — tudo suave o bastante para mostrar contraste, saturação, temperatura, vinheta e grão."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFilter
    L, A = largura, altura
    y = np.linspace(0, 1, A)[:, None]
    x = np.linspace(0, 1, L)[None, :]
    um = np.ones((A, L))
    ceu = np.stack([(70 + 90 * y) * um, (110 + 80 * y) * um, (170 + 50 * y) * um], -1)   # azul → claro
    chao = np.stack([(120 + 40 * x) * um, (90 + 30 * x) * um, (60 + 20 * x) * um], -1)  # terra quente
    hor = 0.58
    mascara = np.clip((y - hor) / 0.015, 0, 1) * um
    img = ceu * (1 - mascara[..., None]) + chao * mascara[..., None]
    sol = np.exp(-(((x - 0.72) ** 2) / 0.012 + ((y - 0.42) ** 2) / 0.02))
    img += np.stack([80 * sol, 55 * sol, 20 * sol], -1)
    im = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGB").filter(ImageFilter.GaussianBlur(1.2))
    d = ImageDraw.Draw(im)
    # da-livre:inicio — quadro SINTÉTICO que imita footage (pele, roupa, patches de cor) para provar o tratamento: não é peça
    # "pessoa": rosto e ombros em tom de pele, com sombra
    cx, cy, r = int(L * 0.34), int(A * 0.5), int(A * 0.13)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(224, 172, 132))
    d.ellipse([cx - r * 0.55, cy - r * 0.2, cx - r * 0.15, cy + r * 0.25], fill=(190, 135, 100))
    d.rounded_rectangle([cx - r * 1.9, cy + r * 1.1, cx + r * 1.9, A], radius=int(r * 0.8), fill=(48, 62, 110))
    d.rectangle([cx - r * 1.9, cy + r * 2.4, cx + r * 1.9, A], fill=(48, 62, 110))
    # rampa de cinza e manchas de cor (patches de referência)
    passos = 12
    pw = int(L * 0.5 / passos)
    for i in range(passos):
        v = int(255 * i / (passos - 1))
        d.rectangle([int(L * 0.47) + i * pw, int(A * 0.86), int(L * 0.47) + (i + 1) * pw, int(A * 0.94)], fill=(v, v, v))
    cores = [(200, 40, 40), (40, 160, 70), (40, 80, 200), (230, 200, 40), (40, 190, 200), (200, 60, 170)]
    for i, c in enumerate(cores):
        d.rectangle([int(L * 0.47) + i * pw * 2, int(A * 0.78), int(L * 0.47) + (i + 1) * pw * 2 - 4, int(A * 0.85)], fill=c)
    # da-livre:fim
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_name(destino.stem + ".parcial.png")
    im.save(tmp, "PNG")
    os.replace(tmp, destino)
    return destino


def achar_referencia(d: da.DA) -> Path | None:
    """O quadro do PROJETO que serve de fundo às amostras (antes/depois, GC, legenda): primeiro footage — bruto/,
    broll/bruto/, broll/tratado/, broll/ —, só depois as imagens de da/referencias (que costumam ser prints de design).
    Numa rota (<projeto>/da/rotas/<nome>/da/da.json), procura também no projeto-pai. None se não houver nada."""
    raizes = [d.raiz]
    pai = da.projeto_pai(d.caminho)
    if pai is not None:
        raizes.append(pai)
    pastas = []
    for r in raizes:
        pastas += [r / "bruto", r / "broll" / "bruto", r / "broll" / "tratado", r / "broll"]
    pastas += [d.pasta / "referencias"] + ([pai / "da" / "referencias"] if pai is not None else [])
    for pasta in pastas:
        if not pasta.is_dir():
            continue
        for arq in sorted(pasta.iterdir()):
            if arq.is_file() and not arq.name.startswith((".", da.PREFIXO_INTERMEDIARIO)) and not da.e_saida_do_extrair(arq) \
                    and arq.suffix.lower() in da.EXT_IMAGEM | da.EXT_VIDEO:
                return arq
    return None


def referencia_tratada(d: da.DA, referencia=None, largura: int = 960) -> dict:
    """Quadro de referência do projeto antes e depois do grade.json: {'antes', 'depois', 'origem'} em da/build/prancha/.
    É o fundo das amostras da prancha e do 2º ato do teste de movimento. Roda sob a trava (ffmpeg)."""
    build = d.build / "prancha"
    build.mkdir(parents=True, exist_ok=True)
    with trava.Trava(rotulo="referência da DA"):
        antes, origem = _quadro_de_referencia(d, referencia, build / "antes.png", largura)
        depois = build / "depois.png"
        da.aplicar_grade(antes, depois, da=d, parte="completa")
    return {"antes": antes, "depois": depois, "origem": origem}


def _quadro_de_referencia(d: da.DA, referencia, destino: Path, largura: int = 960) -> tuple[Path, str]:
    """Produz destino (PNG, `largura` px de largura) a partir de imagem, vídeo ou quadro sintético. Devolve (png, origem)."""
    from PIL import Image, ImageOps
    destino.parent.mkdir(parents=True, exist_ok=True)
    if referencia is None:
        referencia = achar_referencia(d)
    if referencia is None:
        imagem_de_teste(destino, largura, round(largura * 9 / 16))
        return destino, "quadro sintético (nenhuma gravação em bruto/ ou broll/, nenhuma imagem em da/referencias)"
    referencia = Path(referencia)
    if not referencia.is_file():
        raise da.DAErro(f"referência não encontrada: {referencia}")
    if referencia.suffix.lower() in da.EXT_VIDEO:
        info = da.sondar(referencia)
        t = max(0.0, min(info["duracao"] * 0.4, info["duracao"] - 0.1)) if info["duracao"] else 0.0
        tmp = destino.with_name(destino.stem + ".parcial.png")
        da._rodar_ffmpeg(["-y", "-ss", f"{t:.3f}", "-i", str(referencia), "-frames:v", "1", "-update", "1",
                          "-vf", f"scale={largura}:-2:flags=lanczos", "-threads", "2", str(tmp)], f"quadro de {referencia.name}")
        os.replace(tmp, destino)
        return destino, f"quadro de {referencia.name} em {t:.2f} s"
    try:
        im = ImageOps.exif_transpose(Image.open(referencia)).convert("RGB")
    except OSError as e:
        raise da.DAErro(f"não consegui abrir a referência {referencia}: {e}")
    if im.width != largura:
        im = im.resize((largura, max(2, round(im.height * largura / im.width / 2) * 2)), Image.LANCZOS)
    tmp = destino.with_name(destino.stem + ".parcial.png")
    im.save(tmp, "PNG")
    os.replace(tmp, destino)
    return destino, f"imagem {referencia.name}"


# ────────────────────────────────────────────────────────────── prancha ──
FORMATOS_PRANCHA = {"horizontal": ("1920xauto", "prancha.png"), "vertical": ("1080xauto", "prancha_vertical.png")}
QUADRO_DA_PRANCHA = {"horizontal": (1920, 1080), "vertical": (1080, 1920)}
FRASES_DE_AMOSTRA = {1: "Furou", 2: "Conta furada", 3: "A conta furou", 4: "A conta não fecha", 5: "A conta que não fecha"}


def frase_de_amostra(n: int) -> list[str]:
    """Cue de amostra que fecha sentido com n palavras (a mesma tabela de motor/cenas/prancha.js)."""
    return FRASES_DE_AMOSTRA[max(1, min(5, int(n)))].split(" ")


def legenda_de_amostra(d: da.DA, formato: str, destino: Path) -> dict:
    """A amostra de legenda da prancha, feita pelo MESMO caminho da produção (texto.estados_da_legenda → PNG recortado):
    grava `destino` e devolve os params da cena prancha {'arquivo','x','y','w','h','palavras','falada'} (px do quadro)."""
    import texto
    L, A = QUADRO_DA_PRANCHA[formato]
    palavras = frase_de_amostra(d["legenda"]["max_palavras"])
    falada = max(range(len(palavras)), key=lambda i: (len(palavras[i]), i))       # a palavra de conteúdo (a mais longa)
    estados = texto.estados_da_legenda(palavras, d, L, A, formato=formato, recortar=True)
    img, info = estados[min(falada, len(estados) - 1)]
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_name(destino.stem + ".parcial.png")
    img.save(tmp, "PNG")
    os.replace(tmp, destino)
    return {"arquivo": str(destino), "x": int(info["x"]), "y": int(info["y"]), "w": img.width, "h": img.height,
            "palavras": palavras, "falada": falada}


def referencias_do_conceito(d: da.DA, limite: int = 8) -> list[dict]:
    """conceito.referencias que são IMAGENS existentes: [{'arquivo' (absoluto), 'nota', 'nome'}] para a seção de referências."""
    saida = []
    for r in (d["conceito"].get("referencias") or [])[:limite * 2]:
        arq = r.get("arquivo_abs") or r.get("arquivo")
        if not arq:
            continue
        arq = Path(arq)
        if arq.is_file() and arq.suffix.lower() in da.EXT_IMAGEM and not da.e_saida_do_extrair(arq):
            saida.append({"arquivo": str(arq), "nota": str(r.get("nota") or ""), "nome": arq.name})
        if len(saida) >= limite:
            break
    return saida


def gerar_prancha(d: da.DA, formatos=("horizontal", "vertical"), referencia=None, foto=None, saida_pasta=None,
                  sem_auditoria: bool = False, escala: float = 1.0, reaproveitar: bool = False) -> dict:
    """Gera a(s) prancha(s). Devolve {'arquivos': [Path], 'antes', 'depois', 'origem_referencia', 'tempos': {fmt: s}}.

    A amostra de legenda é o PNG de texto.estados_da_legenda (o caminho da produção) e o fundo das amostras é um quadro
    do projeto (achar_referencia: bruto/, broll/, da/referencias; numa rota, também os do projeto-pai). `reaproveitar`
    refaz a prancha com o MESMO quadro de referência e a mesma foto da geração anterior (é o que `aprovar` usa para o
    cabeçalho passar a dizer APROVADA sem trocar a imagem que o cliente viu)."""
    pasta = Path(saida_pasta) if saida_pasta else d.pasta
    pasta.mkdir(parents=True, exist_ok=True)
    build = d.build / "prancha"
    build.mkdir(parents=True, exist_ok=True)
    resultado = {"arquivos": [], "tempos": {}, "falhas": []}
    anterior = {}
    if reaproveitar and (build / "antes.png").is_file() and (build / "depois.png").is_file():
        for fmt in ("horizontal", "vertical"):
            try:
                anterior = anterior or da.ler_json(build / f"params_{fmt}.json")
            except da.DAErro:
                continue
    with trava.Trava(rotulo="prancha da DA"):
        if anterior:
            antes, depois, origem = build / "antes.png", build / "depois.png", anterior.get("origem_referencia") or "quadro da geração anterior"
            da.aplicar_grade(antes, depois, da=d, parte="completa")
            if foto is None and anterior.get("foto") and Path(anterior["foto"]).is_file():
                foto = anterior["foto"]
        else:
            ref = referencia_tratada(d, referencia)
            antes, depois, origem = ref["antes"], ref["depois"], ref["origem"]
        resultado.update(antes=antes, depois=depois, origem_referencia=origem)
        cadeia = d.grade("horizontal")
        try:
            from PIL import Image
            with Image.open(antes) as im_ref:
                proporcao = round(im_ref.width / im_ref.height, 4)
        except Exception:
            proporcao = None
        comuns = {"antes": str(antes), "depois": str(depois), "foto": str(foto) if foto else None,
                  "data": time.strftime("%Y-%m-%d %H:%M"), "preset": d["projeto"].get("base"),
                  "cadeia": None if cadeia == "null" else cadeia, "ref_proporcao": proporcao, "origem_referencia": origem,
                  "referencias": referencias_do_conceito(d) or None}
        for fmt in formatos:
            if fmt not in FORMATOS_PRANCHA:
                raise da.DAErro(f"formato de prancha {fmt!r} inválido; use horizontal, vertical ou ambos")
            tamanho, nome = FORMATOS_PRANCHA[fmt]
            destino = pasta / nome
            # a legenda da prancha é a da produção: PNG de texto.py, posição incluída (D21)
            params = {**comuns, "legenda": legenda_de_amostra(d, fmt, build / f"legenda_{fmt}.png")}
            params = {k: v for k, v in params.items() if v is not None}
            arq_params = build / f"params_{fmt}.json"
            da.gravar_json(arq_params, params)
            t0 = time.monotonic()
            args = ["--cena", "prancha", "--formato", tamanho, "--quadro", "0", "--saida", str(destino),
                    "--params", "@" + str(arq_params), "--sem-trava"]
            if escala != 1.0:
                args += ["--escala", da._num(escala, 3)]
            if sem_auditoria:
                args.append("--sem-auditoria")
            r = render(args, da_obj=d, rotulo=f"prancha {fmt}")
            resultado["tempos"][fmt] = round(time.monotonic() - t0, 1)
            if r.returncode != 0 or not destino.is_file():
                resultado["falhas"].append(fmt)
            else:
                resultado["arquivos"].append(destino)
    return resultado


def _cfg_prancha(p):
    p.add_argument("--formato", choices=("horizontal", "vertical", "ambos"), default="ambos",
                   help="qual prancha gerar (padrão: ambos → da/prancha.png e da/prancha_vertical.png)")
    p.add_argument("--referencia", metavar="ARQ", help="imagem ou vídeo de referência para o antes/depois (padrão: da/referencias, bruto ou broll; senão um quadro sintético)")
    p.add_argument("--foto", metavar="ARQ", help="foto para o GC de amostra")
    p.add_argument("--saida", metavar="PASTA", help="pasta de saída (padrão: da/ do projeto)")
    p.add_argument("--escala", type=float, default=1.0, help="prévia reduzida (ex.: 0.5)")
    p.add_argument("--sem-auditoria", action="store_true", help="pula o auditor C3 (fica registrado no carimbo)")


def _cmd_prancha(args) -> int:
    d = da.carregar(getattr(args, "da", None), de=getattr(args, "de", None))
    formatos = ("horizontal", "vertical") if args.formato == "ambos" else (args.formato,)
    r = gerar_prancha(d, formatos, referencia=args.referencia, foto=args.foto, saida_pasta=args.saida,
                      sem_auditoria=args.sem_auditoria, escala=args.escala)
    da._diz(f"Referência: {r['origem_referencia']}")
    for a in r["arquivos"]:
        try:
            from PIL import Image
            with Image.open(a) as im:
                dims = f"{im.width}×{im.height}"
        except Exception:
            dims = "?"
        fmt = next(k for k, v in FORMATOS_PRANCHA.items() if v[1] == a.name)
        da._diz(f"Prancha {fmt}: {a}  ({dims}, {a.stat().st_size / 1048576:.2f} MB, {r['tempos'].get(fmt, '?')} s)")
    if r["falhas"]:
        da._diz(f"erro: a prancha falhou em: {', '.join(r['falhas'])} (veja as mensagens do motor acima)", erro=True)
        return da.SAIDA_ERRO
    da._diz("Abra a prancha com o cliente; quando aprovar: `da.py aprovar`.")
    return da.SAIDA_OK


# ─────────────────────────────────────────────── aprovação: prancha com o selo ──
def _regerar_pranchas_aprovadas(da_json, documentos: dict, args) -> list[str]:
    """Gancho de `da.py aprovar`: refaz as pranchas que estavam em dia (mesmo quadro de referência, mesma escala) para
    o cabeçalho do documento de registro dizer "APROVADA em <data>" em vez de "RASCUNHO"."""
    if getattr(args, "sem_prancha", False):
        return []
    formatos = [fmt for fmt, (_, nome) in FORMATOS_PRANCHA.items() if documentos.get(nome, {}).get("estado") == "em dia"]
    if not formatos:
        return []
    d = da.carregar(da_json)
    linhas = []
    for fmt in formatos:
        escala = documentos[FORMATOS_PRANCHA[fmt][1]].get("escala") or 1.0
        r = gerar_prancha(d, (fmt,), escala=float(escala), reaproveitar=True)
        if r["falhas"]:
            linhas.append(f"! não consegui regenerar a prancha {fmt} com o selo de aprovação — rode `{da.DA_CLI} prancha --formato {fmt}`")
        else:
            linhas.append(f"prancha {fmt} regenerada com o cabeçalho APROVADA: {r['arquivos'][0]}")
    return linhas


# ───────────────────────────────────────────────────── rotas: lado a lado ──
def comparar_rotas(nomes=None, formato: str = "vertical", com_atual: bool = False, largura: int | None = None, saida=None,
                   regerar: bool = False, caminho=None, de=None, movimento: bool = False) -> dict:
    """Pranchas das rotas LADO A LADO, na mesma escala e alinhadas por seção (o mapa de seções vem do carimbo de cada
    prancha). Gera as pranchas que faltam ou estão desatualizadas. Devolve {'saida', 'colunas': [nomes], 'geradas': [nomes],
    'tamanho': (L, A), 'movimento': Path | None}. A folha fica em da/rotas/comparacao_<formato>.png (não é peça: sem carimbo)."""
    from PIL import Image, ImageDraw, ImageFont
    if formato not in FORMATOS_PRANCHA:
        raise da.DAErro(f"formato {formato!r} inválido; use vertical ou horizontal", codigo=da.SAIDA_USO)
    proj = da._da_do_projeto(caminho, de)
    rotas = da.listar_rotas(caminho, de)
    pedidos = [str(n) for n in (nomes or [])]
    faltam = [n for n in pedidos if n not in {r["nome"] for r in rotas}]
    if faltam:
        raise da.DAErro(f"rota(s) inexistente(s): {', '.join(faltam)}.", dica="Rotas do projeto: " + (", ".join(r["nome"] for r in rotas) or "(nenhuma)"))
    alvos = ([("atual", proj)] if com_atual else []) + [(r["nome"], r["da_json"]) for r in rotas if not pedidos or r["nome"] in pedidos]
    if len(alvos) < 2:
        raise da.DAErro("comparar precisa de pelo menos duas DAs (duas rotas, ou uma rota e --com-atual).",
                        dica=f"Crie outra rota: {da.DA_CLI} rotas criar <nome> --base <preset>")
    nome_arq = FORMATOS_PRANCHA[formato][1]
    col_w = int(largura or (720 if formato == "vertical" else 960))
    colunas, geradas = [], []
    for nome, da_json in alvos:
        d = da.carregar(da_json)                         # DA inválida: DAInvalida com os erros da rota
        png = d.pasta / nome_arq
        carimbo = da.ler_carimbo(png) if png.is_file() else None
        lay = ((carimbo or {}).get("parametros") or {}).get("layout") or {}
        if regerar or not png.is_file() or (carimbo or {}).get("da_sha256") != d.sha256 or not lay.get("mapa"):
            r = gerar_prancha(d, (formato,))
            if r["falhas"]:
                raise da.DAErro(f"a prancha da rota {nome!r} falhou (veja as mensagens do motor acima).")
            geradas.append(nome)
            lay = (da.ler_carimbo(png)["parametros"]).get("layout") or {}
        colunas.append({"nome": nome, "d": d, "png": png, "mapa": lay["mapa"], "largura": lay.get("largura") or QUADRO_DA_PRANCHA[formato][0]})
    # linhas: cabeçalho + união das seções (pela ordem em que aparecem)
    titulos = []
    for c in colunas:
        for i, m in enumerate(c["mapa"]):
            if m["titulo"] not in titulos:
                titulos.insert(min(len(titulos), i), m["titulo"])
    for c in colunas:
        im = Image.open(c["png"]).convert("RGB")
        k = im.width / c["largura"]                       # prancha feita com --escala: o mapa está em px de layout
        esc = col_w / im.width
        c["fundo"] = im.getpixel((2, 2))
        partes = {"": (0, c["mapa"][0]["y"] * k)}
        for m in c["mapa"]:
            partes[m["titulo"]] = (m["y"] * k, (m["y"] + m["h"]) * k)
        c["recortes"] = {}
        for t, (y0, y1) in partes.items():
            rec = im.crop((0, int(y0), im.width, int(min(im.height, y1 + (24 * k if t else 0)))))
            c["recortes"][t] = rec.resize((col_w, max(1, round(rec.height * esc))), Image.LANCZOS)
        im.close()
    # da-livre:inicio — folha de comparação entre DAs DIFERENTES: é ferramenta de escolha, não peça; tem fonte e cores próprias
    FUNDO, TEXTO, SUAVE, LINHA = (24, 24, 24), (238, 238, 234), (150, 150, 146), (70, 70, 70)

    def fonte(tam: int, negrito: bool = False):
        for nome_f in (("IBMPlexMono-Bold.ttf",) if negrito else ()) + ("IBMPlexMono-Medium.ttf", "IBMPlexMono-Regular.ttf"):
            try:
                return ImageFont.truetype(str(KIT / "fontes" / nome_f), tam)
            except OSError:
                continue
        return ImageFont.load_default()
    # da-livre:fim
    vao, topo = 16, 96
    linhas = [""] + titulos
    alturas = [max((c["recortes"][t].height if t in c["recortes"] else 0) for c in colunas) for t in linhas]
    W = len(colunas) * col_w + (len(colunas) + 1) * vao
    H = topo + sum(alturas) + (len(linhas) + 1) * vao
    folha = Image.new("RGB", (W, H), FUNDO)
    des = ImageDraw.Draw(folha)
    f_nome, f_frase = fonte(26, True), fonte(15)
    for i, c in enumerate(colunas):
        x = vao + i * (col_w + vao)
        des.text((x, 18), c["nome"], font=f_nome, fill=TEXTO)
        frase = (c["d"]["conceito"].get("frase") or "").strip()
        limite = max(10, int(col_w / 9.2))
        des.text((x, 56), frase if len(frase) <= limite else frase[:limite - 1] + "…", font=f_frase, fill=SUAVE)
    y = topo
    for t, h in zip(linhas, alturas):
        des.line([(0, y - vao // 2), (W, y - vao // 2)], fill=LINHA, width=1)
        for i, c in enumerate(colunas):
            x = vao + i * (col_w + vao)
            des.rectangle([x, y, x + col_w - 1, y + h - 1], fill=c["fundo"])
            if t in c["recortes"]:
                folha.paste(c["recortes"][t], (x, y))
        y += h + vao
    destino = Path(saida) if saida else proj.parent / da.PASTA_ROTAS / f"comparacao_{formato}.png"
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_name(destino.stem + ".parcial" + destino.suffix)
    folha.save(tmp, "PNG", optimize=True)
    os.replace(tmp, destino)
    resultado = {"saida": destino, "colunas": [c["nome"] for c in colunas], "geradas": geradas, "tamanho": folha.size, "movimento": None}
    if movimento:
        resultado["movimento"] = _comparar_movimento(alvos, formato, destino.with_name("comparacao_movimento.mp4"))
    return resultado


def _comparar_movimento(alvos, formato: str, destino: Path) -> Path:
    """Testes de movimento das rotas lado a lado num vídeo só (cada um congelado no último quadro até o mais longo acabar)."""
    import video
    arquivos, duracoes = [], []
    for nome, da_json in alvos:
        d = da.carregar(da_json)
        arq = d.pasta / "teste_movimento.mp4"
        c = da.ler_carimbo(arq) if arq.is_file() else None
        if not c or c.get("da_sha256") != d.sha256 or c.get("formato") != formato:
            r, arq, _ = gerar_teste_de_movimento(d, formato, escala=0.25)
            if r.returncode != 0:
                raise da.DAErro(f"o teste de movimento da rota {nome!r} falhou (veja as mensagens do motor acima).")
        arquivos.append(arq)
        duracoes.append(float(video.sondar(arq)["duracao"]))
    total = max(duracoes)
    alt = 480 if formato == "vertical" else 270
    args = ["-y"]
    for a in arquivos:
        args += ["-i", str(a)]
    partes = [f"[{i}:v]scale=-2:{alt}:flags=lanczos,tpad=stop_mode=clone:stop_duration={max(0.0, total - dur):.3f},setsar=1[v{i}]" for i, dur in enumerate(duracoes)]
    partes.append("".join(f"[v{i}]" for i in range(len(arquivos))) + f"hstack=inputs={len(arquivos)}[v]")
    args += ["-filter_complex", ";".join(partes), "-map", "[v]", "-t", f"{total:.3f}", "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
             "-pix_fmt", "yuv420p", "-threads", "2", "-movflags", "+faststart"]
    return video.executar(args, destino, rotulo="comparação de movimento")


def cmd_comparar_rotas(args) -> int:
    t0 = time.monotonic()
    r = comparar_rotas(args.nomes, formato=args.formato, com_atual=args.com_atual, largura=args.largura, saida=args.saida,
                       regerar=args.regerar, caminho=getattr(args, "da", None), de=getattr(args, "de", None), movimento=args.movimento)
    if r["geradas"]:
        da._diz(f"Pranchas geradas agora: {', '.join(r['geradas'])}")
    da._diz(f"Lado a lado ({' | '.join(r['colunas'])}): {r['saida']}  ({r['tamanho'][0]}×{r['tamanho'][1]}, {da._ptbr(time.monotonic() - t0, 1)} s)")
    if r["movimento"]:
        da._diz(f"Movimento lado a lado: {r['movimento']}")
    da._diz(f"Mostre ao usuário; depois: {da.DA_CLI} rotas adotar <nome>")
    return da.SAIDA_OK


# ──────────────────────────────────────────────────────── teste de movimento ──
ATOS_DO_TESTE = ("titulo", "gc", "barras")


def duracao_do_teste(d: da.DA, atos=None, pedida: float | None = None) -> dict:
    """Plano de tempos do teste de movimento para esta DA — a mesma conta de motor/cenas/teste_movimento.js (plano()):
    {'total', 'natural', 'minima', 'respiro', 'atos'}. Cada ato = entrada completa + respiro + saída, com as durações da DA."""
    m = d["movimento"]
    du, e = m["duracoes"], float(m["escalonamento"])
    trans = 0.0 if m["transicoes"]["padrao"] == "corte" else float(du["media"])
    entrada = {"titulo": 0.05 + max(2 * e + du["longa"], 8 * e + du["media"]), "gc": 4 * e + du["media"],
               "barras": 0.05 + (4 + 1.5 * 4) * e + du["longa"] + 0.5 * du["media"]}
    saida = {"titulo": du["media"], "gc": du["media"], "barras": 0.0}
    lista = [a for a in ATOS_DO_TESTE if not atos or a in atos]
    fixo = sum((trans if i else 0.0) + entrada[a] + saida[a] for i, a in enumerate(lista))
    respiro = 0.7 if pedida is None else max(0.2, (float(pedida) - fixo) / len(lista))
    return {"total": round(fixo + respiro * len(lista), 3), "natural": round(fixo + 0.7 * len(lista), 3),
            "minima": round(fixo + 0.2 * len(lista), 3), "respiro": round(respiro, 3), "atos": lista}


def gerar_teste_de_movimento(d: da.DA, formato: str = "horizontal", escala: float = 0.5, dur: float | None = None, saida=None,
                             atos=None, referencia=None, sem_auditoria: bool = False):
    """Renderiza o teste de movimento (cena teste_movimento): título → GC + legenda sobre um quadro do projeto → barras.
    A duração sai das durações da DA (duracao_do_teste); `dur` só mexe nos respiros. Devolve (trava.Resultado, saida, plano)."""
    saida = Path(saida) if saida else d.pasta / "teste_movimento.mp4"
    if atos:
        ruins = [a for a in atos if a not in ATOS_DO_TESTE]
        if ruins:
            raise da.DAErro(f"--atos: {', '.join(ruins)} não existe(m); use {', '.join(ATOS_DO_TESTE)}", codigo=da.SAIDA_USO)
    plano = duracao_do_teste(d, atos, dur)
    params = {}
    if atos:
        params["atos"] = [a for a in ATOS_DO_TESTE if a in atos]
    if not atos or "gc" in atos:
        params["fundo"] = str(referencia_tratada(d, referencia)["depois"])
    args = ["--cena", "teste_movimento", "--formato", formato, "--escala", da._num(escala, 3), "--saida", str(saida)]
    if dur is not None:
        args += ["--dur", da._num(dur, 3)]
    if params:
        arq = d.build / "prancha" / "params_teste.json"
        arq.parent.mkdir(parents=True, exist_ok=True)
        da.gravar_json(arq, params)
        args += ["--params", "@" + str(arq)]
    if sem_auditoria:
        args.append("--sem-auditoria")
    return render(args, da_obj=d, rotulo="teste de movimento"), saida, plano


def _cfg_teste(p):
    p.add_argument("--formato", default="horizontal", help="formato da DA: horizontal (padrão), vertical ou quadrado — renderizado em escala reduzida")
    p.add_argument("--escala", type=float, default=0.5, help="fator de redução (padrão: 0.5 → 960×540 no horizontal, 540×960 no vertical)")
    p.add_argument("--dur", type=float, default=None,
                   help="duração desejada em segundos. Padrão: calculada pelas durações da DA (entrada completa + respiro de 0,7 s + saída "
                        "em cada ato). Só estica ou encolhe os respiros: nenhuma animação é cortada, e abaixo do mínimo vale o mínimo")
    p.add_argument("--atos", metavar="LISTA", help="atos a renderizar, separados por vírgula: titulo, gc, barras (padrão: os três)")
    p.add_argument("--referencia", metavar="ARQ", help="imagem ou vídeo do projeto para o fundo do ato do GC (padrão: bruto/, broll/, da/referencias)")
    p.add_argument("--saida", metavar="ARQ", help="arquivo .mp4 (padrão: da/teste_movimento.mp4)")
    p.add_argument("--sem-auditoria", action="store_true", help="pula o auditor C3")


def _cmd_teste(args) -> int:
    d = da.carregar(getattr(args, "da", None), de=getattr(args, "de", None))
    atos = [a.strip() for a in args.atos.split(",") if a.strip()] if args.atos else None
    t0 = time.monotonic()
    r, saida, plano = gerar_teste_de_movimento(d, args.formato, args.escala, args.dur, args.saida, atos, args.referencia, args.sem_auditoria)
    if r.returncode != 0:
        return r.returncode
    da._diz(f"Teste de movimento: {saida}  ({da._ptbr(plano['total'], 2)} s de peça: {' → '.join(plano['atos'])}, respiro de "
            f"{da._ptbr(plano['respiro'], 2)} s por ato; render em {da._ptbr(time.monotonic() - t0, 1)} s)")
    if args.dur is not None and abs(plano["total"] - args.dur) > 0.01:
        da._diz(f"  ! --dur {da._ptbr(args.dur, 2)} não corta animação: o mínimo desta DA é {da._ptbr(plano['minima'], 2)} s (pelas durações de movimento)")
    return da.SAIDA_OK


# ───────────────────────────────────────────────────────────── repasse ──
def _cfg_render(p):
    p.add_argument("argumentos", nargs="...", help="argumentos do motor: --cena, --saida, --formato, --dur, --params… (node motor/render.mjs --help)")


def _cmd_render(args) -> int:
    repasse = list(args.argumentos)
    if repasse[:1] == ["--"]:                    # `da.py render -- --help`: o separador é do da.py, não do motor
        repasse = repasse[1:]
    if "--help" in repasse:                      # a ajuda do motor não depende de haver DA nem de esperar a fila
        return _conferir_fora_da_trava([achar_node(), str(RENDER_MJS), "--help"], None, capturar=False).returncode
    d = da.carregar(getattr(args, "da", None), de=getattr(args, "de", None))
    r = render(repasse, da_obj=d, rotulo="render")
    return r.returncode


def registrar(mod) -> None:
    if _regerar_pranchas_aprovadas not in mod.APOS_APROVAR:
        mod.APOS_APROVAR.append(_regerar_pranchas_aprovadas)
    mod.registrar_subcomando("prancha", "gera a prancha de direção de arte (da/prancha.png e prancha_vertical.png)", _cfg_prancha, _cmd_prancha,
                             "Monta, com o próprio motor, a prancha que o cliente aprova: conceito, paleta com contraste, tipografia, componentes "
                             "(título, GC + legenda, moldura), tratamento antes/depois, barras, curvas de movimento, margens seguras (vertical) e thumbnail.")
    mod.registrar_subcomando("teste-movimento", "gera da/teste_movimento.mp4 (~4 s) com título + GC + barras", _cfg_teste, _cmd_teste)
    mod.registrar_subcomando("render", "repassa ao motor: da.py render --cena titulo --saida x.mp4 …", _cfg_render, _cmd_render,
                             f"Equivale a `node {KIT_FINAL}/motor/render.mjs … --da <da.json>` sob a trava global. "
                             "Ajuda do motor: da.py render -- --help", repasse=True)
