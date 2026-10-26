#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""storyboard.py — liga roteiro → cenas animadas → renders, sempre submetido à direção de arte (DA) do projeto.

O storyboard (roteiro/storyboard.json) diz, para cada trecho do roteiro, qual cena da biblioteca o ilustra, com que
parâmetros, por quanto tempo e em que formatos. Este script cria e edita esse arquivo, confere tudo o que dá para
conferir ANTES do render (contrato, cena, parâmetros pelo validador do motor, formatos, ritmo), casa cada cena com a
narração (transcricao/*.palavras.json), mostra uma folha de contato para aprovação, renderiza a fila sob a trava
global e exporta as âncoras para a skill de efeitos sonoros.

Subcomandos: novo · cenas · adicionar · definir · remover · mostrar · validar · sincronizar · fila · prever · render ·
ancoras · conferir. Códigos de saída: 0 ok · 1 reprovado ou falha de render · 2 projeto sem direção de arte ·
64 uso incorreto. Só biblioteca padrão + o kit em ../../video-direcao-de-arte/kit (Pillow e numpy por ele).
"""
from __future__ import annotations

import argparse
import difflib
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
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

sys.dont_write_bytecode = True
AQUI = Path(__file__).resolve().parent
SKILL = AQUI.parent
CENAS_DA_SKILL = SKILL / "cenas"
CENAS_MJS = AQUI / "cenas.mjs"
KIT = SKILL.parent / "video-direcao-de-arte" / "kit"
if not (KIT / "da.py").is_file():
    KIT = Path("~/.claude/skills/video-direcao-de-arte/kit").expanduser()
FATOS_PY = SKILL.parent / "video-pesquisa-ia" / "scripts" / "fatos.py"
SKILL_FINAL = "\"$CRIABR_SKILLS\"/video-animacao-explicativa"

SAIDA_OK, SAIDA_ERRO, SAIDA_SEM_DA, SAIDA_USO = 0, 1, 2, 64
ARQ = Path("roteiro") / "storyboard.json"
MARCA = "|"                              # no `trecho`: "aqui dispara o próximo passo da cena"
CENAS_DO_KIT_FORA = {"prancha", "teste_movimento"}
CODECS_ALFA = {"vp9alfa": ".webm", "prores4444": ".mov"}
CAMPOS = ("id", "trecho", "t0", "dur", "cena", "params", "formatos", "fato_ids", "broll_id", "saida")
LEITURA_MINIMA = 0.35                    # respiro mínimo depois de cada passo (s) — o mesmo valor de cenas/_ia.js


class Uso(Exception):
    """Erro de uso: mensagem acionável, código 64, sem traceback."""

    def __init__(self, mensagem: str, dica: str | None = None, codigo: int = SAIDA_USO):
        super().__init__(mensagem)
        self.dica, self.codigo = dica, codigo


def _kit():
    """Importa o kit só quando o comando precisa dele (o catálogo e a ajuda funcionam sem Pillow)."""
    if str(KIT) not in sys.path:
        sys.path.insert(0, str(KIT))
    try:
        import da, da_ext_motor, video  # noqa: E401
    except ModuleNotFoundError as e:
        raise Uso(f"não consegui importar o kit de direção de arte ({e}).",
                  f"O kit mora em {KIT} e precisa de um Python com Pillow e numpy: rode este script com /opt/homebrew/bin/python3.", SAIDA_ERRO)
    return da, da_ext_motor, video


def diz(*a, erro: bool = False):
    print(*a, file=sys.stderr if erro else sys.stdout)


# ───────────────────────────────────────────────────────────────── projeto e DA ──
def carregar_da(projeto=None):
    """→ (d, raiz). Sem DA: SystemExit(2) com a instrução de chamar a skill video-direcao-de-arte."""
    da, _, _ = _kit()
    try:
        d = da.carregar(de=str(projeto)) if projeto else da.carregar()
    except da.SemDA as e:
        diz(f"erro: {e}", erro=True)
        diz("Este projeto não tem direção de arte (da/da.json): nada é renderizado sem ela. Chame a skill video-direcao-de-arte para criar a DA e volte.", erro=True)
        raise SystemExit(SAIDA_SEM_DA)
    except da.DAErro as e:
        diz(f"erro: {e}" + (f"\n{e.dica}" if getattr(e, 'dica', None) else ""), erro=True)
        raise SystemExit(getattr(e, "codigo", None) or SAIDA_ERRO)
    return d, Path(d.raiz)


# ──────────────────────────────────────────────────────────────── storyboard ──
class Trava:
    """Trava de arquivo para ler-modificar-gravar o storyboard (agentes disparam comandos em paralelo)."""

    def __init__(self, raiz: Path):
        self.arq = raiz / "roteiro" / "_storyboard.lock"

    def __enter__(self):
        self.arq.parent.mkdir(parents=True, exist_ok=True)
        self.f = open(self.arq, "w")
        fcntl.flock(self.f, fcntl.LOCK_EX)
        return self

    def __exit__(self, *a):
        fcntl.flock(self.f, fcntl.LOCK_UN)
        self.f.close()


def ler(raiz: Path) -> dict:
    arq = raiz / ARQ
    if not arq.is_file():
        raise Uso(f"não há storyboard em {arq}.", f"Crie com: python3 {SKILL_FINAL}/scripts/storyboard.py novo")
    try:
        sb = json.loads(arq.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise Uso(f"{arq} não é JSON válido (linha {e.lineno}, coluna {e.colno}: {e.msg}).", "Corrija o arquivo à mão ou recrie com `novo --forcar`.", SAIDA_ERRO)
    if not isinstance(sb, dict) or not isinstance(sb.get("cenas"), list):
        raise Uso(f"{arq} não segue o contrato: esperava {{\"versao\": 1, \"cenas\": [...]}}.", codigo=SAIDA_ERRO)
    return sb


def gravar(raiz: Path, sb: dict) -> Path:
    arq = raiz / ARQ
    arq.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="_storyboard.", suffix=".parcial", dir=str(arq.parent))
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(sb, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, arq)
    return arq


def achar_cena(sb: dict, cid: str) -> dict:
    for c in sb["cenas"]:
        if isinstance(c, dict) and str(c.get("id")) == cid:
            return c
    ids = ", ".join(str(c.get("id")) for c in sb["cenas"] if isinstance(c, dict)) or "(nenhuma)"
    raise Uso(f"a cena {cid!r} não existe no storyboard.", f"Cenas: {ids}.")


def proximo_id(sb: dict) -> str:
    usados = {str(c.get("id")) for c in sb["cenas"] if isinstance(c, dict)}
    n = 1
    while f"C{n:02d}" in usados:
        n += 1
    return f"C{n:02d}"


# ────────────────────────────────────────────────────────────── catálogo de cenas ──
def _node(args: list[str], entrada: str | None = None) -> str:
    _, motor, _ = _kit()
    try:
        r = subprocess.run([motor.achar_node(), str(CENAS_MJS), *args], input=entrada, capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        raise Uso("a leitura das cenas pelo node não terminou em 60 s (laço sem fim no nível do módulo de alguma cena?).", codigo=SAIDA_ERRO)
    if r.returncode != 0:
        raise Uso(f"não consegui ler as cenas com o node: {(r.stderr or r.stdout).strip()[-400:]}", codigo=SAIDA_ERRO)
    return r.stdout


def arquivos_de_cena(raiz: Path | None) -> list[tuple[str, str, Path]]:
    """[(origem, nome, arquivo)] na ordem de precedência: projeto (animacoes/cenas), skill, kit."""
    achados = []
    fontes = []
    if raiz is not None:
        fontes.append(("projeto", raiz / "animacoes" / "cenas"))
    fontes += [("skill", CENAS_DA_SKILL), ("kit", KIT / "motor" / "cenas")]
    for origem, pasta in fontes:
        if not pasta.is_dir():
            continue
        for arq in sorted(pasta.glob("*.js")):
            if arq.name.startswith("_") or (origem == "kit" and arq.stem in CENAS_DO_KIT_FORA):
                continue
            achados.append((origem, arq.stem, arq))
    return achados


def catalogo(raiz: Path | None) -> list[dict]:
    """Lê `meta` de todas as cenas disponíveis. Nome repetido: vale a primeira origem (projeto > skill > kit)."""
    arquivos = arquivos_de_cena(raiz)
    metas = json.loads(_node(["meta", *[str(a) for _, _, a in arquivos]])) if arquivos else []
    vistos, saida = set(), []
    for (origem, nome, arq), m in zip(arquivos, metas):
        item = {"nome": nome, "origem": origem, "arquivo": str(arq), "sombreada": nome in vistos}
        vistos.add(nome)
        if "erro" in m:
            item["erro"] = m["erro"]
        else:
            item.update(meta=m["meta"], tem_roteiro=m["tem_roteiro"])
        saida.append(item)
    return saida


def resolver_cena(raiz: Path, nome: str) -> tuple[Path, str]:
    """Campo `cena` do storyboard → (arquivo, origem). Nome simples: projeto > skill > kit. Caminho .js: relativo à raiz."""
    nome = str(nome or "").strip()
    if not nome:
        raise Uso("faltou o nome da cena.")
    if nome.endswith(".js") or "/" in nome:
        arq = Path(nome).expanduser()
        arq = arq if arq.is_absolute() else raiz / arq
        if not arq.is_file():
            raise Uso(f"a cena {nome!r} não existe ({arq}).", "Caminho de cena própria é relativo à raiz do projeto (ex.: animacoes/cenas/minha.js).")
        return arq, "caminho"
    for origem, n, arq in arquivos_de_cena(raiz):
        if n == nome:
            return arq, origem
    nomes = sorted({n for _, n, _ in arquivos_de_cena(raiz)})
    perto = difflib.get_close_matches(nome, nomes, n=3, cutoff=0.5)
    raise Uso(f"a cena {nome!r} não existe.", (f"Quis dizer {' ou '.join(perto)}? " if perto else "") + f"Cenas disponíveis: {', '.join(nomes)}. Veja os parâmetros com `storyboard.py cenas <nome>`.")


def roteiros(raiz: Path, d, cenas: list[dict]) -> list[dict]:
    """Para cada cena do storyboard: {passos, minima, recomendada} | {passos: None} | {erro}."""
    pedidos = []
    for c in cenas:
        try:
            arq, _ = resolver_cena(raiz, c.get("cena"))
            pedidos.append({"arquivo": str(arq), "params": c.get("params") if isinstance(c.get("params"), dict) else {}})
        except Uso as e:
            pedidos.append({"arquivo": "", "params": {}, "_erro": str(e)})
    validos = [p for p in pedidos if p["arquivo"]]
    mov = {"duracoes": d["movimento"]["duracoes"], "escalonamento": d["movimento"]["escalonamento"]}
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(mov, f)
    try:
        res = json.loads(_node(["roteiro", f.name], json.dumps(validos, ensure_ascii=False))) if validos else []
    finally:
        os.unlink(f.name)
    it = iter(res)
    return [{"erro": p["_erro"]} if not p["arquivo"] else next(it) for p in pedidos]


# ───────────────────────────────────────────────────────────────── contrato ──
def conferir_contrato(sb: dict, d=None) -> list[dict]:
    """Erros de forma do storyboard. → [{cena, nivel, msg}]"""
    achados = []
    indice = [None]

    def erro(cid, msg):
        achados.append({"cena": cid, "nivel": "erro", "msg": msg, "indice": indice[0]})

    if sb.get("versao") != 1:
        erro(None, f'"versao" precisa ser 1 (veio {sb.get("versao")!r})')
    vistos = set()
    for i, c in enumerate(sb.get("cenas", [])):
        indice[0] = i
        if not isinstance(c, dict):
            erro(None, f"cenas[{i}] não é um objeto")
            continue
        cid = c.get("id")
        if not isinstance(cid, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", cid):
            erro(str(cid), f'cenas[{i}].id precisa ser texto sem espaços (ex.: "C01"); veio {cid!r}')
            cid = f"cenas[{i}]"
        elif cid in vistos:
            erro(cid, "id repetido: cada cena tem um id único")
        vistos.add(cid)
        for campo in CAMPOS:
            if campo not in c:
                erro(cid, f'falta o campo "{campo}" do contrato')
        if "trecho" in c and not isinstance(c["trecho"], str):
            erro(cid, '"trecho" precisa ser texto (a frase do roteiro que a cena cobre)')
        t0 = c.get("t0")
        if t0 is not None and (isinstance(t0, bool) or not isinstance(t0, (int, float)) or t0 < 0):
            erro(cid, f'"t0" é null ou segundos ≥ 0 (veio {t0!r})')
        dur = c.get("dur")
        if "dur" in c and (isinstance(dur, bool) or not isinstance(dur, (int, float)) or dur <= 0):
            erro(cid, f'"dur" precisa ser segundos > 0 (veio {dur!r})')
        if "cena" in c and (not isinstance(c["cena"], str) or not c["cena"].strip()):
            erro(cid, '"cena" precisa ser o nome de uma cena ou o caminho de um .js')
        if "params" in c and not isinstance(c["params"], dict):
            erro(cid, '"params" precisa ser um objeto {…}')
        fs = c.get("formatos")
        if "formatos" in c and (not isinstance(fs, list) or not fs or not all(isinstance(x, str) for x in fs)):
            erro(cid, '"formatos" precisa ser uma lista com ao menos um formato da DA (ex.: ["horizontal", "vertical"])')
        elif isinstance(fs, list) and d is not None:
            for fmt in fs:
                if not (isinstance(d["formatos"].get(fmt), dict) and d["formatos"][fmt].get("fps")):
                    validos = [k for k, v in d["formatos"].items() if isinstance(v, dict) and v.get("fps")]
                    erro(cid, f'formato "{fmt}" não é um formato de vídeo desta DA ({", ".join(validos)})')
        fi = c.get("fato_ids")
        if "fato_ids" in c and (not isinstance(fi, list) or not all(isinstance(x, str) for x in fi)):
            erro(cid, '"fato_ids" precisa ser uma lista de ids da ficha de fatos (pode ser vazia)')
        if "broll_id" in c and c["broll_id"] is not None and not isinstance(c["broll_id"], str):
            erro(cid, '"broll_id" é null ou o id de um b-roll (ex.: "B003")')
        sd = c.get("saida")
        if "saida" in c and (not isinstance(sd, str) or not sd.strip() or Path(sd).is_absolute() or ".." in Path(sd).parts):
            erro(cid, '"saida" precisa ser um caminho relativo à raiz do projeto, sem extensão (ex.: "animacoes/C01")')
    return achados


def cena_nova(sb: dict, cena: str, cid: str | None = None, trecho: str = "", dur: float | None = None, t0=None, params=None,
              formatos=None, fato_ids=None, broll_id=None, dur_padrao: float = 6.0) -> dict:
    cid = cid or proximo_id(sb)
    return {"id": cid, "trecho": trecho, "t0": t0, "dur": dur if dur is not None else dur_padrao, "cena": cena, "params": params or {},
            "formatos": formatos or ["horizontal", "vertical"], "fato_ids": fato_ids or [], "broll_id": broll_id, "saida": f"animacoes/{cid}"}


# ─────────────────────────────────────────────────────────────── fila do motor ──
def _alfa_da_cena(c: dict, meta: dict) -> bool:
    return bool(c["alfa"]) if isinstance(c.get("alfa"), bool) else bool((meta or {}).get("alfa_padrao"))


def montar_fila(raiz: Path, sb: dict, formato: str, so=None, escala: float | None = None, codec_alfa: str = "vp9alfa",
                quadros: list[float] | None = None, pasta_previa: Path | None = None) -> tuple[list[dict], list[dict]]:
    """Jobs do motor para um formato. → (jobs, planos); cada plano = {id, saida (Path absoluto), cena, quadro}."""
    metas = {}
    jobs, planos = [], []
    pasta_fila = raiz / "animacoes"
    for c in sb["cenas"]:
        if not isinstance(c, dict) or formato not in (c.get("formatos") or []) or (so and c.get("id") not in so):
            continue
        arq, origem = resolver_cena(raiz, c["cena"])
        if str(arq) not in metas:
            m = json.loads(_node(["meta", str(arq)]))[0]
            if "erro" in m:
                raise Uso(f"cena {c['id']}: não consegui ler {arq.name}: {m['erro']}", codigo=SAIDA_ERRO)
            metas[str(arq)] = m["meta"]
        alfa = _alfa_da_cena(c, metas[str(arq)])
        base = {"cena": arq.stem if origem == "kit" else str(arq), "formato": formato, "dur": c["dur"], "params": c.get("params") or {}, "_id": c["id"]}
        if escala:
            base["escala"] = escala
        if quadros is None:
            ext = CODECS_ALFA[codec_alfa] if alfa else ".mp4"
            saida = raiz / f"{c['saida']}_{formato}{ext}"
            job = {**base, "saida": os.path.relpath(saida, pasta_fila), "alfa": alfa, "codec": codec_alfa if alfa else "h264"}
            jobs.append(job)
            planos.append({"id": c["id"], "saida": saida, "job": job, "arquivo_cena": arq})
        else:
            for k, fr in enumerate(quadros):
                t = round(max(0.0, min(c["dur"], fr * c["dur"])), 3)
                saida = (pasta_previa or pasta_fila / "_previa") / f"{c['id']}_{formato}_q{k + 1}.png"
                job = {**base, "saida": os.path.relpath(saida, pasta_fila), "alfa": False, "quadro": t}
                jobs.append(job)
                planos.append({"id": c["id"], "saida": saida, "job": job, "quadro": t, "arquivo_cena": arq})
    return jobs, planos


def gravar_fila(raiz: Path, nome: str, jobs: list[dict]) -> Path:
    arq = raiz / "animacoes" / nome
    arq.parent.mkdir(parents=True, exist_ok=True)
    arq.write_text(json.dumps(jobs, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return arq


def validar_no_motor(d, fila: Path) -> tuple[bool, str]:
    """Roda o validador do motor (sem browser, fora da trava). → (ok, mensagem)"""
    _, motor, _ = _kit()
    r = motor.render(["--fila", str(fila), "--validar"], da_obj=d, capturar=True)
    return r.returncode == 0, (r.stderr or r.stdout or "").strip()


def formatos_do_storyboard(sb: dict, pedidos=None) -> list[str]:
    todos = []
    for c in sb["cenas"]:
        for f in (c.get("formatos") or []) if isinstance(c, dict) else []:
            if f not in todos:
                todos.append(f)
    if pedidos:
        fora = [f for f in pedidos if f not in todos]
        if fora:
            raise Uso(f"nenhuma cena do storyboard pede o formato {', '.join(fora)}.", f"Formatos em uso: {', '.join(todos) or '(nenhum)'}.")
        return list(pedidos)
    return todos


# ───────────────────────────────────────────────────────────────── validação ──
def validar(raiz: Path, d, sb: dict) -> dict:
    """Contrato + cena existe + params pelo validador do motor + formatos + ritmo. → {ok, erros, avisos, achados}"""
    da, _, _ = _kit()
    achados = conferir_contrato(sb, d)
    com_erro = {a["indice"] for a in achados}                    # cena com erro de forma não segue para as outras conferências

    def nota(cid, nivel, msg):
        achados.append({"cena": cid, "nivel": nivel, "msg": msg})

    cenas = [c for i, c in enumerate(sb["cenas"]) if isinstance(c, dict) and i not in com_erro]
    rots = roteiros(raiz, d, cenas) if cenas else []
    media = d["movimento"]["duracoes"]["media"]
    boas = []
    for c, rot in zip(cenas, rots):
        cid = c["id"]
        if "erro" in rot:
            nota(cid, "erro", rot["erro"])
            continue
        boas.append(c)
        p = c["params"]
        if not str(c["saida"]).startswith("animacoes/"):
            nota(cid, "aviso", f'"saida" é {c["saida"]!r}: fora de animacoes/ a peça escapa do conferir-carimbo padrão e do QA')
        if rot.get("passos"):
            n = len(rot["passos"])
            nomes = ", ".join(x["nome"] for x in rot["passos"])
            if c["dur"] < rot["minima"]:
                nota(cid, "erro", f'dur = {c["dur"]:g} s é curta demais para os {n} passos desta cena ({nomes}): o mínimo com as durações desta DA é {rot["minima"]:g} s (recomendado: {rot["recomendada"]:g} s). Aumente "dur" ou simplifique os parâmetros')
            elif c["dur"] < rot["recomendada"]:
                nota(cid, "aviso", f'dur = {c["dur"]:g} s deixa pouco tempo de leitura por passo ({n} passos); recomendado: {rot["recomendada"]:g} s')
            pt = p.get("passos_t")
            if isinstance(pt, list) and pt:
                if len(pt) > n:
                    nota(cid, "erro", f"passos_t tem {len(pt)} instantes e a cena tem {n} passo(s) ({nomes})")
                elif any(not isinstance(v, (int, float)) or isinstance(v, bool) for v in pt):
                    nota(cid, "erro", "passos_t precisa ser uma lista de números (segundos a partir do início da cena)")
                else:
                    if any(b <= a for a, b in zip(pt, pt[1:])):
                        nota(cid, "erro", f"passos_t precisa estar em ordem crescente (veio {pt})")
                    if pt[-1] >= c["dur"] - media - 0.05:
                        nota(cid, "erro", f'passos_t termina em {pt[-1]:g} s, dentro da saída da cena (que começa em {c["dur"] - media:g} s): aumente "dur" ou adiante o último passo')
                    for k, (a, b) in enumerate(zip(pt, pt[1:] + [c["dur"] - media])):
                        if k == len(pt) - 1 and len(pt) < n:
                            break                                 # o último instante dado divide o resto da cena com os passos sem instante
                        if b - a < rot["passos"][k]["anim"] * 0.6 and b > a:
                            nota(cid, "aviso", f'o passo "{rot["passos"][k]["nome"]}" tem {b - a:.2f} s até o seguinte e a animação dele pede {rot["passos"][k]["anim"]:.2f} s: vai sair comprimida')
                    if len(pt) < n and pt[-1] < c["dur"] - media:
                        resto = rot["passos"][len(pt) - 1:]
                        livre, pede = c["dur"] - media - pt[-1], sum(x["anim"] for x in resto)
                        if livre < pede + LEITURA_MINIMA * len(resto):
                            nota(cid, "aviso", f'depois de {pt[-1]:g} s ainda acontecem {len(resto)} passo(s) ({", ".join(x["nome"] for x in resto)}) e sobram {livre:.2f} s até a saída; as animações deles pedem {pede:.2f} s mais o tempo de leitura: aumente "dur" para pelo menos {pt[-1] + pede + LEITURA_MINIMA * len(resto) + media:.2f} s')
        elif c["dur"] < 1.5:
            nota(cid, "aviso", f'dur = {c["dur"]:g} s: menos de 1,5 s mal dá para ler uma cena')
        if p.get("ilustrativo") is False:
            if not (isinstance(p.get("fonte"), str) and p["fonte"].strip()):
                nota(cid, "erro", 'ilustrativo=false declara dado real: falta params.fonte (use a saída de `fatos.py credito F### --sem-prefixo`)')
            if not c["fato_ids"]:
                nota(cid, "erro", "ilustrativo=false declara dado real: falta citar o fato em fato_ids (ficha de fatos da skill video-pesquisa-ia)")
        elif c["fato_ids"] and "fonte" in p and not p.get("fonte"):
            nota(cid, "aviso", "a cena cita fato_ids e não tem params.fonte: dado de fato vai para a tela com crédito")
    # parâmetros: o validador do motor, uma vez para tudo; se reprovar, cena a cena para listar todos os erros
    if boas:
        formatos = formatos_do_storyboard({"cenas": boas})
        jobs = [j for f in formatos for j in montar_fila(raiz, {"cenas": boas}, f)[0]]
        with tempfile.TemporaryDirectory(prefix="_valida ", dir=str(raiz / "animacoes") if (raiz / "animacoes").is_dir() else None) as tmp:
            fila = Path(tmp) / "_fila.json"
            ajustar = lambda js: [{**j, "saida": str(Path(tmp) / Path(j["saida"]).name)} for j in js]   # noqa: E731
            fila.write_text(json.dumps(ajustar(jobs), ensure_ascii=False), encoding="utf-8")
            ok, msg = validar_no_motor(d, fila)
            for linha in msg.splitlines():
                if linha.startswith("! "):
                    nota(None, "info", linha[2:])
            if not ok:
                for c in boas:
                    js = [j for j in jobs if j["_id"] == c["id"]]
                    fila.write_text(json.dumps(ajustar(js), ensure_ascii=False), encoding="utf-8")
                    ok1, msg1 = validar_no_motor(d, fila)
                    if not ok1:
                        linhas = [x for x in msg1.splitlines() if x.strip() and not x.startswith("[")]
                        texto = " ".join(x.strip() for x in linhas[-3:])
                        texto = re.sub(r"^erro: (job \d+ \([^)]*\): )?", "", texto)
                        nota(c["id"], "erro", texto or "o validador do motor reprovou os parâmetros")
    # sobreposição no tempo
    com_t0 = sorted([c for c in boas if c.get("t0") is not None], key=lambda c: c["t0"])
    for a, b in zip(com_t0, com_t0[1:]):
        if a["t0"] + a["dur"] > b["t0"] + 0.01:
            nota(b["id"], "aviso", f'começa em {b["t0"]:g} s, antes de {a["id"]} terminar ({a["t0"] + a["dur"]:g} s): as duas cenas se sobrepõem na linha do tempo')
    erros = sum(1 for a in achados if a["nivel"] == "erro")
    avisos = sum(1 for a in achados if a["nivel"] == "aviso")
    return {"ok": erros == 0, "erros": erros, "avisos": avisos, "cenas": len(sb["cenas"]), "achados": achados, "da_sha256": d.sha256,
            "roteiros": {c["id"]: r for c, r in zip(cenas, rots) if "erro" not in r}, "verificado_em": da.agora_iso()}


# ───────────────────────────────────────────────────────────────── sincronia ──
def normalizar(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9]+", "", s)


def fatiar_trecho(trecho: str) -> tuple[list[str], list[int]]:
    """Trecho com marcas → (palavras normalizadas, índices das palavras que vêm logo depois de cada marca)."""
    limpo = re.sub(r"\[[^\]]*\]", " ", trecho)                # marcadores de fato [F001] e [sem-fato] não são falados
    tokens, marcas = [], []
    for pedaco in re.split(r"(\|)", limpo):
        if pedaco == MARCA:
            marcas.append(len(tokens))
            continue
        tokens += [n for n in (normalizar(w) for w in pedaco.split()) if n]
    return tokens, marcas


def ancorar(tokens: list[str], palavras: list[str], inicio: int = 0) -> dict | None:
    """Acha `tokens` na transcrição (lista de palavras normalizadas). → {i0, i1, nota, mapa} ou None."""
    n = len(tokens)
    if not n or not palavras:
        return None

    def tentar(de: int):
        sm = difflib.SequenceMatcher(None, palavras[de:], tokens, autojunk=False)
        m = sm.find_longest_match(0, len(palavras) - de, 0, n)
        if m.size == 0:
            return None
        folga = max(3, n // 3)
        a = max(0, de + m.a - m.b - folga)
        b = min(len(palavras), de + m.a - m.b + n + folga)
        sm2 = difflib.SequenceMatcher(None, palavras[a:b], tokens, autojunk=False)
        mapa = {}
        for bl in sm2.get_matching_blocks():
            for k in range(bl.size):
                mapa[bl.b + k] = a + bl.a + k
        if not mapa:
            return None
        return {"i0": min(mapa.values()), "i1": max(mapa.values()), "nota": len(mapa) / n, "mapa": mapa}

    melhor = tentar(inicio)
    if (melhor is None or melhor["nota"] < 0.6) and inicio:
        outro = tentar(0)
        if outro and (melhor is None or outro["nota"] > melhor["nota"]):
            melhor = outro
    return melhor


def sincronizar(raiz: Path, d, sb: dict, palavras: list[dict], antecipar: float = 0.2, cauda: float = 0.6, so=None, manter_dur: bool = False) -> list[dict]:
    """Preenche t0, dur e passos_t (quando o trecho traz marcas) a partir da transcrição. Altera `sb`. → relatório por cena."""
    norm = [normalizar(str(p.get("w", ""))) for p in palavras]
    indices = [i for i, w in enumerate(norm) if w]
    falas = [norm[i] for i in indices]
    cenas = [c for c in sb["cenas"] if isinstance(c, dict) and (not so or c.get("id") in so)]
    rots = roteiros(raiz, d, cenas)
    rel, cursor = [], 0
    for c, rot in zip(cenas, rots):
        item = {"id": c.get("id"), "ok": False}
        rel.append(item)
        tokens, marcas = fatiar_trecho(str(c.get("trecho") or ""))
        if not tokens:
            item.update(ok=None, msg="sem trecho: pulada (cena sem fala, como uma cartela, recebe t0 à mão)")
            continue
        a = ancorar(tokens, falas, cursor)
        if a is None or a["nota"] < 0.5:
            item["msg"] = f"não achei o trecho na transcrição (melhor casamento: {0 if a is None else a['nota']:.0%} das palavras). Confira se o trecho é o que foi FALADO"
            continue
        w0, w1 = palavras[indices[a["i0"]]], palavras[indices[a["i1"]]]
        t0 = round(max(0.0, float(w0["a"]) - antecipar), 2)
        fim = float(w1["b"]) + cauda
        item.update(nota=round(a["nota"], 3), t0=t0, fala=[round(float(w0["a"]), 2), round(float(w1["b"]), 2)])
        passos_t = None
        if marcas:
            n_passos = len(rot["passos"]) if rot.get("passos") else None
            if n_passos is None:
                item["msg"] = "o trecho tem marcas |, mas esta cena não declara passos (cenas do kit não têm passos_t): tire as marcas"
                continue
            if len(marcas) + 1 > n_passos:
                item["msg"] = f"o trecho tem {len(marcas)} marca(s) | e a cena tem {n_passos} passo(s) ({', '.join(x['nome'] for x in rot['passos'])}): cabem no máximo {n_passos - 1} marcas (o 1º passo dispara no começo)"
                continue
            passos_t = [0.0]
            for m in marcas:
                alvo = next((a["mapa"][k] for k in range(m, len(tokens)) if k in a["mapa"]), None)
                if alvo is None:
                    alvo = a["i1"]
                t = round(max(passos_t[-1] + 0.2, float(palavras[indices[alvo]]["a"]) - t0 - 0.08), 2)
                passos_t.append(t)
            # a cena não acaba na última palavra: o último passo marcado e os que vêm depois dele sem marca (a
            # recapitulação de uma lista, o exemplo de um conceito) precisam de tempo para animar e ser lidos
            resto = rot["passos"][len(passos_t) - 1:]
            precisa = t0 + passos_t[-1] + sum(x["anim"] + LEITURA_MINIMA for x in resto) + d["movimento"]["duracoes"]["media"] + 0.05
            if precisa > fim + 0.01:
                item["estendida"] = {"segundos": round(precisa - fim, 2), "passos": [x["nome"] for x in resto]}
                fim = precisa
        dur = round(fim - t0, 2)
        c["t0"] = t0
        if not manter_dur:
            c["dur"] = dur
        if passos_t is not None:
            c.setdefault("params", {})["passos_t"] = passos_t
            item["passos_t"] = passos_t
        item.update(ok=True, dur=c["dur"])
        if a["nota"] < 0.75:
            item["aviso"] = f"só {a['nota']:.0%} das palavras do trecho bateram com a fala: confira o tempo no vídeo"
        if rot.get("passos") and c["dur"] < rot["minima"]:
            item["aviso"] = (item.get("aviso", "") + " " if item.get("aviso") else "") + f"a fala dura menos que o mínimo da cena ({rot['minima']:g} s): alongue o trecho, simplifique os parâmetros ou ajuste dur à mão"
        cursor = a["i0"] + 1
    return rel


# ───────────────────────────────────────────────────────────────── comandos ──
def cmd_novo(args) -> int:
    d, raiz = carregar_da(args.projeto)
    arq = raiz / ARQ
    if arq.is_file() and not args.forcar:
        raise Uso(f"já existe {arq}.", "Use `adicionar`/`definir` para editar, ou `novo --forcar` para recomeçar (o anterior vira storyboard.json.bak).")
    with Trava(raiz):
        if arq.is_file():
            os.replace(arq, arq.with_suffix(".json.bak"))
        gravar(raiz, {"versao": 1, "cenas": []})
    diz(f"Criado {arq} (vazio). Próximo passo: `storyboard.py cenas` para ver o catálogo e `storyboard.py adicionar --cena <nome> --trecho \"…\"`.")
    return SAIDA_OK


def _descrever_param(nome: str, df: dict) -> str:
    tipo = df.get("tipo", "texto")
    extra = []
    if tipo == "opcao":
        extra.append(" | ".join(df.get("opcoes", [])))
    if df.get("min") is not None or df.get("max") is not None:
        extra.append(f"{df.get('min', '…')}–{df.get('max', '…')}")
    if df.get("obrigatorio") and "padrao" not in df:
        extra.append("obrigatório")
    elif df.get("padrao") is not None:
        pad = json.dumps(df["padrao"], ensure_ascii=False)
        extra.append("padrão " + (pad if len(pad) <= 46 else pad[:43] + "…"))
    return f"    {nome:<18} {tipo:<9} {df.get('descricao', '')}" + (f"  [{'; '.join(extra)}]" if extra else "")


def cmd_cenas(args) -> int:
    raiz = None
    try:
        da, _, _ = _kit()
        achado = da.achar(de=args.projeto, obrigatorio=False)
        raiz = Path(achado).parent.parent if achado else None
    except Exception:
        raiz = None
    cat = catalogo(raiz)
    if args.nome:
        itens = [c for c in cat if c["nome"] == args.nome and not c["sombreada"]]
        if not itens:
            nomes = sorted({c["nome"] for c in cat})
            perto = difflib.get_close_matches(args.nome, nomes, n=3, cutoff=0.5)
            raise Uso(f"a cena {args.nome!r} não existe.", (f"Quis dizer {' ou '.join(perto)}? " if perto else "") + f"Cenas: {', '.join(nomes)}.")
        cat = itens
    if args.json:
        print(json.dumps(cat, ensure_ascii=False, indent=1))
        return SAIDA_OK
    for origem, titulo in (("projeto", "Cenas próprias do projeto (animacoes/cenas/)"), ("skill", "Biblioteca de IA (video-animacao-explicativa)"), ("kit", "Cenas do kit de direção de arte")):
        grupo = [c for c in cat if c["origem"] == origem]
        if not grupo:
            continue
        diz(f"\n{titulo}")
        for c in grupo:
            if "erro" in c:
                diz(f"  {c['nome']:<18} ILEGÍVEL: {c['erro']}")
                continue
            m = c["meta"]
            sombra = "  (sombreada por outra de mesmo nome)" if c["sombreada"] else ""
            diz(f"  {c['nome']:<18} {m.get('dur_padrao', '?'):>4} s  {m.get('descricao', '')}{sombra}")
            if args.nome:
                diz(f"    arquivo: {c['arquivo']}")
                diz(f"    formatos: {', '.join(m.get('formatos') or ['qualquer'])} · alfa por padrão: {'sim' if m.get('alfa_padrao') else 'não'} · passos sincronizáveis: {'sim' if c.get('tem_roteiro') else 'não'}")
                diz("    parâmetros:")
                for nome, df in (m.get("params") or {}).items():
                    diz(_descrever_param(nome, df))
    if not args.nome:
        diz("\nDetalhe de uma cena (parâmetros, tipos e padrões): storyboard.py cenas <nome>   ·   --json para máquina")
    return SAIDA_OK


def _ler_params(texto: str | None) -> dict:
    if not texto:
        return {}
    origem = "linha de comando"
    if texto.startswith("@"):
        origem = texto[1:]
        try:
            texto = Path(origem).expanduser().read_text(encoding="utf-8")
        except OSError as e:
            raise Uso(f"--params: não consegui ler {origem} ({e.strerror}).")
    try:
        v = json.loads(texto)
    except json.JSONDecodeError as e:
        raise Uso(f"--params não é JSON válido ({origem}): {e.msg} na coluna {e.colno}.", "Ex.: --params '{\"tokens\": [\"Olá\", \" mundo\"]}' ou --params @params.json")
    if not isinstance(v, dict):
        raise Uso("--params precisa ser um objeto JSON {…}.")
    return v


def _lista(texto: str | None) -> list[str] | None:
    return [x.strip() for x in texto.split(",") if x.strip()] if texto else None


def _conferir_edicao(raiz: Path, d, cena: dict, mesmo_assim: bool) -> None:
    """Confere a cena ANTES de gravar: com erro, nada é gravado (código 64) — a não ser com --mesmo-assim."""
    rel = validar(raiz, d, {"versao": 1, "cenas": [cena]})
    for a in rel["achados"]:
        if a["nivel"] in ("erro", "aviso"):
            diz(f"  {a['nivel'].upper()}: {a['msg']}", erro=True)
    if rel["erros"] and not mesmo_assim:
        raise Uso(f"a cena {cena.get('id')} reprova com esses dados: nada foi gravado.",
                  "Corrija o que está acima e repita o comando (ou use --mesmo-assim para gravar um rascunho que `validar` vai reprovar).")


def cmd_adicionar(args) -> int:
    d, raiz = carregar_da(args.projeto)
    arq, _ = resolver_cena(raiz, args.cena)
    meta = json.loads(_node(["meta", str(arq)]))[0]
    if "erro" in meta:
        raise Uso(f"não consegui ler a cena {args.cena}: {meta['erro']}", codigo=SAIDA_ERRO)
    with Trava(raiz):
        sb = ler(raiz)
        if args.id and any(isinstance(c, dict) and c.get("id") == args.id for c in sb["cenas"]):
            raise Uso(f"já existe uma cena {args.id}.", f"Edite com `storyboard.py definir {args.id} …` ou escolha outro id.")
        params = _ler_params(args.params)
        dur_padrao = meta["meta"].get("dur_padrao", 6)
        if args.dur is None:                                   # o ritmo depende das durações da DA: uma DA calma pede cena mais longa
            rot = roteiros(raiz, d, [{"cena": args.cena, "params": params}])[0]
            if rot.get("recomendada"):
                dur_padrao = max(dur_padrao, -(-rot["recomendada"] // 0.5) * 0.5)
        nova = cena_nova(sb, args.cena, cid=args.id, trecho=args.trecho or "", dur=args.dur, t0=args.t0, params=params,
                         formatos=_lista(args.formatos), fato_ids=args.fato or [], broll_id=args.broll, dur_padrao=dur_padrao)
        if args.alfa is not None:
            nova["alfa"] = args.alfa == "sim"
        _conferir_edicao(raiz, d, nova, args.mesmo_assim)
        if args.depois:
            pos = sb["cenas"].index(achar_cena(sb, args.depois)) + 1
            sb["cenas"].insert(pos, nova)
        else:
            sb["cenas"].append(nova)
        gravar(raiz, sb)
    diz(f"{nova['id']}: cena {args.cena} ({nova['dur']:g} s; {', '.join(nova['formatos'])}) → {nova['saida']}_<formato>")
    return SAIDA_OK


def cmd_definir(args) -> int:
    d, raiz = carregar_da(args.projeto)
    with Trava(raiz):
        sb = ler(raiz)
        original = achar_cena(sb, args.id)
        c = json.loads(json.dumps(original))                    # edita uma cópia: só entra no arquivo se passar na conferência
        if args.cena:
            resolver_cena(raiz, args.cena)
            c["cena"] = args.cena
        if args.trecho is not None:
            c["trecho"] = args.trecho
        if args.dur is not None:
            c["dur"] = args.dur
        if args.t0 is not None:
            c["t0"] = None if args.t0.lower() in ("null", "nulo", "nenhum") else _numero(args.t0, "--t0")
        if args.formatos:
            c["formatos"] = _lista(args.formatos)
        if args.fato is not None:
            c["fato_ids"] = [] if args.fato == ["nenhum"] else args.fato
        if args.broll is not None:
            c["broll_id"] = None if args.broll.lower() in ("null", "nulo", "nenhum") else args.broll
        if args.alfa is not None:
            if args.alfa == "padrao":
                c.pop("alfa", None)
            else:
                c["alfa"] = args.alfa == "sim"
        params = c.setdefault("params", {})
        if args.params_novos:
            params.clear()
        params.update(_ler_params(args.params))
        for par in args.param or []:
            if "=" not in par:
                raise Uso(f"--param {par!r}: use chave=valor (o valor em JSON: --param 'consulta=3', --param 'titulo=\"Atenção\"').")
            k, v = par.split("=", 1)
            try:
                params[k.strip()] = json.loads(v)
            except json.JSONDecodeError:
                params[k.strip()] = v                          # texto simples sem aspas
        for k in args.sem_param or []:
            params.pop(k, None)
        _conferir_edicao(raiz, d, c, args.mesmo_assim)
        sb["cenas"][sb["cenas"].index(original)] = c
        gravar(raiz, sb)
    diz(f"{c['id']}: atualizada (cena {c['cena']}, {c['dur']:g} s, t0 {c['t0']}, {', '.join(c['formatos'])}).")
    return SAIDA_OK


def _numero(texto: str, opcao: str) -> float:
    try:
        return float(texto.replace(",", "."))
    except ValueError:
        raise Uso(f"{opcao} {texto!r}: esperava um número em segundos.")


def cmd_remover(args) -> int:
    _, raiz = carregar_da(args.projeto)
    with Trava(raiz):
        sb = ler(raiz)
        c = achar_cena(sb, args.id)
        sb["cenas"].remove(c)
        gravar(raiz, sb)
    renders = sorted((raiz / Path(c.get("saida", "")).parent).glob(Path(c.get("saida", "x")).name + "_*")) if c.get("saida") else []
    diz(f"{args.id}: removida do storyboard." + (f" Os renders dela continuam em disco ({len(renders)} arquivo(s) em {Path(c['saida']).parent}/): apague à mão se não servem mais." if renders else ""))
    return SAIDA_OK


def cmd_mostrar(args) -> int:
    _, raiz = carregar_da(args.projeto)
    sb = ler(raiz)
    if args.json:
        print(json.dumps(sb, ensure_ascii=False, indent=2))
        return SAIDA_OK
    diz(f"{raiz / ARQ} — {len(sb['cenas'])} cena(s)")
    for c in sb["cenas"]:
        if not isinstance(c, dict):
            continue
        t0 = "  —  " if c.get("t0") is None else f"{c['t0']:6.2f}"
        trecho = str(c.get("trecho") or "")
        diz(f"  {str(c.get('id')):<5} {t0} s +{c.get('dur', 0):5.2f} s  {str(c.get('cena')):<16} {','.join(c.get('formatos') or []):<19} {'fatos ' + ','.join(c['fato_ids']) + '  ' if c.get('fato_ids') else ''}{trecho[:60]}{'…' if len(trecho) > 60 else ''}")
    return SAIDA_OK


def cmd_validar(args) -> int:
    d, raiz = carregar_da(args.projeto)
    sb = ler(raiz)
    rel = validar(raiz, d, sb)
    if args.json:
        print(json.dumps(rel, ensure_ascii=False, indent=1))
    else:
        for a in rel["achados"]:
            onde = f"{a['cena']}: " if a["cena"] else ""
            diz(f"  {a['nivel'].upper():<5} {onde}{a['msg']}")
        veredito = "VÁLIDO" if rel["ok"] and not (args.estrito and rel["avisos"]) else "REPROVADO"
        diz(f"{veredito}: {rel['cenas']} cena(s), {rel['erros']} erro(s), {rel['avisos']} aviso(s). Nada foi renderizado.")
    return SAIDA_OK if rel["ok"] and not (args.estrito and rel["avisos"]) else SAIDA_ERRO


def _achar_palavras(raiz: Path, pedido: str | None) -> Path:
    if pedido:
        arq = Path(pedido).expanduser()
        arq = arq if arq.is_absolute() else (Path.cwd() / arq if (Path.cwd() / arq).is_file() else raiz / arq)
        if not arq.is_file():
            raise Uso(f"transcrição não encontrada: {pedido}.")
        return arq
    achados = sorted((raiz / "transcricao").glob("*.palavras.json"))
    if not achados:
        raise Uso("não há transcrição em transcricao/*.palavras.json.", "Gere com a skill video-transcricao (palavra a palavra) ou passe --palavras ARQUIVO.")
    if len(achados) > 1:
        raise Uso("há mais de uma transcrição em transcricao/.", "Diga qual é a do vídeo montado: --palavras " + " | ".join(f'"{a.relative_to(raiz)}"' for a in achados))
    return achados[0]


def cmd_sincronizar(args) -> int:
    d, raiz = carregar_da(args.projeto)
    arq = _achar_palavras(raiz, args.palavras)
    try:
        palavras = json.loads(arq.read_text(encoding="utf-8"))
        assert isinstance(palavras, list) and all(isinstance(p, dict) and "a" in p and "b" in p and "w" in p for p in palavras)
    except (json.JSONDecodeError, AssertionError):
        raise Uso(f"{arq} não está no formato de palavras da casa.", 'Esperava uma lista [{"a": início_s, "b": fim_s, "w": "palavra", "p": confiança}] (skill video-transcricao).', SAIDA_ERRO)
    with Trava(raiz):
        sb = ler(raiz)
        rel = sincronizar(raiz, d, sb, palavras, antecipar=args.antecipar, cauda=args.cauda, so=_lista(args.so), manter_dur=args.manter_dur)
        if not args.simular:
            sb["sincronia"] = {"origem": str(arq.relative_to(raiz)) if arq.is_relative_to(raiz) else str(arq), "antecipar": args.antecipar, "cauda": args.cauda}
            gravar(raiz, sb)
    falhas = 0
    for r in rel:
        if r["ok"] is None:
            diz(f"  {r['id']:<5} {r['msg']}")
        elif r["ok"]:
            diz(f"  {r['id']:<5} t0 {r['t0']:7.2f} s  dur {r['dur']:5.2f} s  casamento {r['nota']:.0%}" + (f"  passos_t {r['passos_t']}" if r.get("passos_t") else "")
                + (f"\n        + {r['estendida']['segundos']:g} s depois da fala: {' e '.join(r['estendida']['passos'][-2:]) if len(r['estendida']['passos']) < 3 else ', '.join(r['estendida']['passos'])} ainda precisam animar" if r.get("estendida") and not args.manter_dur else "")
                + (f"\n        AVISO: {r['aviso']}" if r.get("aviso") else ""))
        else:
            falhas += 1
            diz(f"  {r['id']:<5} NÃO SINCRONIZADA: {r['msg']}")
    feitas = sum(1 for r in rel if r["ok"])
    diz(f"{'Simulação: nada foi gravado. ' if args.simular else ''}{feitas} cena(s) sincronizada(s) com {arq.name}, {falhas} não encontrada(s), {len(rel) - feitas - falhas} sem trecho.")
    return SAIDA_OK if not falhas else SAIDA_ERRO


def _preparar(args, quadros=None):
    """Comum a fila/prever/render: DA, storyboard válido, formatos."""
    d, raiz = carregar_da(args.projeto)
    sb = ler(raiz)
    so = _lista(getattr(args, "so", None))
    if so:
        for cid in so:
            achar_cena(sb, cid)
    rel = validar(raiz, d, {"versao": sb.get("versao"), "cenas": [c for c in sb["cenas"] if not so or (isinstance(c, dict) and c.get("id") in so)]})
    if not rel["ok"]:
        for a in rel["achados"]:
            if a["nivel"] == "erro":
                diz(f"  ERRO  {a['cena'] + ': ' if a['cena'] else ''}{a['msg']}", erro=True)
        raise Uso("o storyboard reprova em `validar`: nada foi enviado ao motor.", "Corrija os erros acima (storyboard.py definir <id> …) e repita.", SAIDA_ERRO)
    formatos = formatos_do_storyboard({"cenas": [c for c in sb["cenas"] if not so or c.get("id") in so]}, _lista(getattr(args, "formato", None)))
    if not formatos:
        raise Uso("o storyboard não tem cenas para renderizar.", "Acrescente com `storyboard.py adicionar --cena <nome>`.")
    return d, raiz, sb, so, formatos, rel


def cmd_fila(args) -> int:
    d, raiz, sb, so, formatos, _ = _preparar(args)
    for f in formatos:
        jobs, _ = montar_fila(raiz, sb, f, so=so, escala=args.escala, codec_alfa=args.codec_alfa)
        arq = gravar_fila(raiz, f"_fila_{f}.json", jobs)
        diz(f"{arq}: {len(jobs)} job(s) → " + ", ".join(j["saida"] for j in jobs[:4]) + (" …" if len(jobs) > 4 else ""))
    diz("Renderize com `storyboard.py render` (pula o que já está em dia) ou direto no motor: "
        f"\"$CRIABR_SKILLS\"/video-direcao-de-arte/kit/bin/da render --fila \"animacoes/_fila_{formatos[0]}.json\"")
    return SAIDA_OK


# A checagem de "quietude" do motor (dois retratos do mesmo seek(t) têm de ser idênticos) reprova às vezes em render
# REDUZIDO sem que nada tenha mudado na página: a 0,25 da resolução, a borda suavizada de uma barra sai um pixel
# diferente entre dois retratos (medido em 2026-10-12 com a cena proximo_token em t ≈ 15 s: 5 falhas em 12 execuções
# com --escala 0.25, nenhuma em 12 na resolução cheia, e nenhuma mutação de DOM entre os dois seeks). Único ponto do
# contorno: só para essa falha, e só para as peças que falharam, a fila é repetida até duas vezes.
FALHA_INTERMITENTE = "se mexe fora de seek"
REPETICOES = 2


def _rodar_uma_vez(d, fila: Path, inatividade: float | None) -> dict:
    _, motor, _ = _kit()
    args = ["--fila", str(fila), "--json"]
    if inatividade is not None:
        args += ["--inatividade", f"{inatividade:g}"]
    r = motor.render(args, da_obj=d, capturar=True, rotulo="storyboard")
    try:
        res = json.loads(r.stdout[r.stdout.index("{"):])
    except (ValueError, json.JSONDecodeError):
        res = {"ok": False, "renderizados": [], "falhas": [], "erro": (r.stderr or "").strip().splitlines()[-1:] or ["o motor não devolveu resumo"]}
    res["codigo"] = r.returncode
    res["stderr"] = r.stderr or ""
    return res


def _rodar_fila(d, fila: Path, inatividade: float | None) -> dict:
    """Roda a fila no motor. → resumo do motor + codigo + stderr (+ `repetidas`: peças refeitas pela falha intermitente)."""
    res = _rodar_uma_vez(d, fila, inatividade)
    alvo = lambda saida: str((fila.parent / str(saida)).resolve())                       # noqa: E731  (saídas da fila são relativas a ela)
    repetidas = []
    for _ in range(REPETICOES):
        ruins = {alvo(f.get("saida", "")) for f in res.get("falhas", []) if FALHA_INTERMITENTE in str(f.get("erro", ""))}
        if not ruins or res["codigo"] not in (0, 1):
            break
        jobs = [j for j in json.loads(fila.read_text(encoding="utf-8")) if alvo(j["saida"]) in ruins]
        outra = fila.with_name("_repetir" + fila.name)
        outra.write_text(json.dumps(jobs, ensure_ascii=False), encoding="utf-8")
        try:
            r2 = _rodar_uma_vez(d, outra, inatividade)
        finally:
            outra.unlink(missing_ok=True)
        if r2["codigo"] not in (0, 1):
            break
        refeitas = {alvo(o.get("saida", "")) for o in r2.get("renderizados", [])}
        repetidas += sorted(refeitas)
        res["renderizados"] = res.get("renderizados", []) + r2.get("renderizados", [])
        res["falhas"] = [f for f in res.get("falhas", []) if alvo(f.get("saida", "")) not in ruins] + r2.get("falhas", [])
        res["stderr"] += r2["stderr"]
        res["codigo"] = 1 if res["falhas"] else 0
    res["repetidas"] = repetidas
    return res


def cmd_prever(args) -> int:
    d, raiz, sb, so, formatos, rel = _preparar(args)
    _, _, video = _kit()
    if not 1 <= args.quadros <= 3:
        raise Uso("--quadros vai de 1 a 3.")
    media = d["movimento"]["duracoes"]["media"]
    pasta = raiz / "animacoes" / "_previa"
    pasta.mkdir(parents=True, exist_ok=True)
    codigo = SAIDA_OK
    for f in formatos:
        L, A = d.dimensoes(f)
        escala = round(min(1.0, args.largura / L), 4)
        fracoes = {1: [0.82], 2: [0.45, 0.82], 3: [0.25, 0.55, 0.82]}[args.quadros]
        jobs, planos = [], []
        for c in sb["cenas"]:
            if not isinstance(c, dict) or f not in c["formatos"] or (so and c["id"] not in so):
                continue
            teto = max(0.0, (c["dur"] - 2 * media - 0.1) / c["dur"])       # o último quadro fica antes da saída da cena
            j, p = montar_fila(raiz, {"cenas": [c]}, f, escala=escala, quadros=[x * min(1.0, teto / fracoes[-1]) for x in fracoes], pasta_previa=pasta)
            jobs += j
            planos += p
        for p in planos:
            p["saida"].unlink(missing_ok=True)
        fila = gravar_fila(raiz, f"_fila_previa_{f}.json", jobs)
        res = _rodar_fila(d, fila, args.inatividade)
        feitos = [p for p in planos if p["saida"].is_file()]
        if res.get("repetidas"):
            diz(f"  ({len(res['repetidas'])} quadro(s) refeito(s): a checagem de quietude do motor oscila em render reduzido)")
        for fa in res.get("falhas", []):
            diz(f"  FALHA {Path(fa.get('saida', '?')).name}: {fa.get('erro')}", erro=True)
        if res["codigo"] not in (0, 1) or not feitos:
            diz(res["stderr"][-1500:], erro=True)
            raise Uso(f"a prévia do formato {f} não saiu (código {res['codigo']} do motor).", codigo=SAIDA_ERRO)
        folha = pasta / f"storyboard_{f}.png"
        vertical = A > L
        video.folha_de_contato([str(p["saida"]) for p in feitos], [f"{p['id']} · {p['job']['cena'] if '/' not in p['job']['cena'] else Path(p['job']['cena']).stem} · t={p['quadro']:g} s" for p in feitos],
                               str(folha), colunas=args.quadros * (2 if vertical else 1), largura_celula=min(args.largura, 400 if vertical else 640), da_obj=d,
                               titulo=f"Storyboard · {f} · {len({p['id'] for p in feitos})} cena(s)")
        diz(f"{folha}  ({len(feitos)} quadro(s) de {len({p['id'] for p in feitos})} cena(s), escala {escala:g})")
        if len(feitos) < len(planos):
            codigo = SAIDA_ERRO
    diz("Mostre a folha ao usuário. Aprovada, renderize: `storyboard.py render`. (A pasta animacoes/_previa/ é intermediária: fica fora do QA.)")
    return codigo


def _assinatura(plano: dict, d) -> str:
    h = hashlib.sha256()
    h.update(json.dumps(plano["job"], sort_keys=True, ensure_ascii=False).encode())
    h.update(d.sha256.encode())
    arqs = [plano["arquivo_cena"]] + sorted(plano["arquivo_cena"].parent.glob("_*.js"))
    for a in arqs:
        h.update(a.read_bytes())
    return h.hexdigest()


def cmd_render(args) -> int:
    d, raiz, sb, so, formatos, _ = _preparar(args)
    da, _, _ = _kit()
    arq_feito = raiz / "animacoes" / "_feito.json"
    feito = json.loads(arq_feito.read_text(encoding="utf-8")) if arq_feito.is_file() else {}
    total_ok, total_falha, total_pulo = [], [], []
    for f in formatos:
        jobs, planos = montar_fila(raiz, sb, f, so=so, escala=args.escala, codec_alfa=args.codec_alfa)
        fazer = []
        for p in planos:
            chave = str(p["saida"].relative_to(raiz))
            p["chave"], p["assinatura"] = chave, _assinatura(p, d)
            em_dia = (not args.refazer and feito.get(chave) == p["assinatura"] and p["saida"].is_file()
                      and da.conferir_carimbo([str(p["saida"])], da=d)["ok"])
            (total_pulo if em_dia else fazer).append(p)
        if not fazer:
            diz(f"[{f}] nada a fazer: {len(planos)} peça(s) em dia (use --refazer para renderizar de novo).")
            continue
        fila = gravar_fila(raiz, f"_fila_{f}.json", [p["job"] for p in fazer])
        diz(f"[{f}] renderizando {len(fazer)} peça(s) ({len(planos) - len(fazer)} em dia) — fila {fila.relative_to(raiz)}")
        res = _rodar_fila(d, fila, args.inatividade)
        if res.get("repetidas"):
            diz(f"  ({len(res['repetidas'])} peça(s) refeita(s): a checagem de quietude do motor oscila em render reduzido)")
        if res["codigo"] not in (0, 1):
            diz(res["stderr"][-2000:], erro=True)
            diz(f"erro: o motor parou com código {res['codigo']} no formato {f} ({'trava ou inatividade' if res['codigo'] in (75, 124) else 'veja a mensagem acima'}).", erro=True)
        prontos = {str(Path(o["saida"]).resolve()) for o in res.get("renderizados", [])}
        erros = {str(Path(x.get("saida", "")).resolve()): x.get("erro") for x in res.get("falhas", [])}
        for p in fazer:
            alvo = str(p["saida"].resolve())
            if alvo in prontos and p["saida"].is_file():
                feito[p["chave"]] = p["assinatura"]
                total_ok.append(p)
            else:
                feito.pop(p["chave"], None)
                p["erro"] = erros.get(alvo) or (res.get("erro") or ["não foi renderizada"])[0]
                total_falha.append(p)
        arq_feito.write_text(json.dumps(feito, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        if total_falha and res["stderr"]:
            trechos = [ln for ln in res["stderr"].splitlines() if "AUDITORIA" in ln or "IMPURA" in ln or ln.startswith("  t=")]
            for ln in trechos[:12]:
                diz("    " + ln.strip(), erro=True)
    diz(f"\nRESUMO: {len(total_ok)} renderizada(s), {len(total_pulo)} em dia, {len(total_falha)} falha(s)")
    for p in total_ok:
        diz(f"  OK     {p['chave']}  ({p['saida'].stat().st_size / 1048576:.2f} MB)")
    for p in total_falha:
        diz(f"  FALHA  {p['chave']}: {p['erro']}")
    if total_ok or total_pulo:
        diz("Âncoras para a sonorização: `storyboard.py ancoras`. Conferência: \"$CRIABR_SKILLS\"/video-direcao-de-arte/kit/bin/da conferir-carimbo animacoes")
    return SAIDA_ERRO if total_falha else SAIDA_OK


def cmd_ancoras(args) -> int:
    d, raiz = carregar_da(args.projeto)
    da, _, _ = _kit()
    sb = ler(raiz)
    cenas, eventos, faltam = [], [], []
    for c in sb["cenas"]:
        if not isinstance(c, dict):
            continue
        visto = False
        for f in c.get("formatos") or []:
            arq = next((raiz / f"{c['saida']}_{f}{ext}" for ext in (".mp4", ".webm", ".mov") if (raiz / f"{c['saida']}_{f}{ext}").is_file()), None)
            car = da.ler_carimbo(arq) if arq else None
            if not car:
                faltam.append(f"{c['id']}_{f}")
                continue
            anc = (car.get("parametros") or {}).get("ancoras") or []
            t0 = c.get("t0")
            lista = [{"t": a["t"], "t_video": None if t0 is None else round(t0 + a["t"], 3), "nome": a.get("nome"), "tipo": a.get("tipo")} for a in anc]
            cenas.append({"id": c["id"], "cena": c["cena"], "formato": f, "arquivo": str(arq.relative_to(raiz)), "t0": t0, "dur": c["dur"], "da_sha256": car.get("da_sha256"), "ancoras": lista})
            if not visto and t0 is not None:                   # os instantes não mudam de um formato para o outro: conta uma vez
                eventos += [{"t_video": a["t_video"], "cena_id": c["id"], "nome": a["nome"], "tipo": a["tipo"]} for a in lista]
            visto = True
    saida = raiz / "animacoes" / "ancoras.json"
    doc = {"versao": 1, "gerado_em": da.agora_iso(), "origem": str(ARQ), "da_sha256": d.sha256, "cenas": cenas, "eventos": sorted(eventos, key=lambda e: e["t_video"])}
    saida.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    sem_t0 = sorted({c["id"] for c in cenas if c["t0"] is None})
    diz(f"{saida}: {len(cenas)} peça(s), {len(doc['eventos'])} evento(s) na linha do tempo do vídeo.")
    if sem_t0:
        diz(f"  AVISO: {', '.join(sem_t0)} sem t0 — os instantes dessas cenas ficam só em tempo local (rode `sincronizar` ou defina t0).")
    if faltam:
        diz(f"  AVISO: sem render (ou sem carimbo) para {', '.join(faltam)} — rode `storyboard.py render`.")
    return SAIDA_OK if cenas else SAIDA_ERRO


def cmd_conferir(args) -> int:
    d, raiz = carregar_da(args.projeto)
    da, _, _ = _kit()
    sb = ler(raiz)
    codigo = SAIDA_OK
    # 1. fatos: quem confere é a skill video-pesquisa-ia
    cita = sorted({f for c in sb["cenas"] if isinstance(c, dict) for f in (c.get("fato_ids") or [])})
    ficha = raiz / "pesquisa" / "fatos.json"
    if FATOS_PY.is_file() and ficha.is_file():
        cmd = [sys.executable, "-B", str(FATOS_PY), "--projeto", str(raiz), "conferir-storyboard"] + (["--estrito"] if args.estrito else [])
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        diz("— fatos (video-pesquisa-ia) —")
        diz((r.stdout + r.stderr).rstrip())
        if r.returncode != 0:
            codigo = SAIDA_ERRO
    elif cita:
        diz(f"— fatos — ERRO: o storyboard cita {', '.join(cita)}, mas " + ("não há pesquisa/fatos.json neste projeto" if FATOS_PY.is_file() else "a skill video-pesquisa-ia não está instalada ao lado desta") + ": os fatos não foram conferidos.", erro=True)
        codigo = SAIDA_ERRO
    else:
        diz("— fatos — nenhuma cena cita fato_ids e não há ficha: nada a conferir (cenas com dado real precisam de ficha).")
    # 2. regra da casa: dado real leva fonte e fato
    for c in sb["cenas"]:
        p = c.get("params") if isinstance(c, dict) and isinstance(c.get("params"), dict) else {}
        if p.get("ilustrativo") is False and (not c.get("fato_ids") or not p.get("fonte")):
            diz(f"— dado real — ERRO {c.get('id')}: ilustrativo=false sem " + " e sem ".join(x for x, falta in (("fato_ids", not c.get("fato_ids")), ("params.fonte", not p.get("fonte"))) if falta), erro=True)
            codigo = SAIDA_ERRO
    # 3. lint das cenas próprias do projeto e do storyboard
    alvos = [str(raiz / ARQ)] + [str(a) for a in sorted((raiz / "animacoes" / "cenas").glob("*.js"))] if (raiz / "animacoes" / "cenas").is_dir() else [str(raiz / ARQ)]
    for c in sb["cenas"]:
        if isinstance(c, dict) and str(c.get("cena", "")).endswith(".js"):
            arq = raiz / c["cena"]
            if arq.is_file() and str(arq) not in alvos:
                alvos.append(str(arq))
    lint = da.lint(alvos, estrito=True)
    diz(f"— lint (cor e fonte literais) — {lint['arquivos']} arquivo(s): {lint['erros']} erro(s), {lint['avisos']} aviso(s)")
    for a in lint["achados"][:30]:
        diz(f"  {Path(a.get('arquivo', '?')).name}:{a.get('linha', '?')}  {a.get('regra', '')}: {a.get('mensagem') or a.get('trecho', '')}")
    for nc in lint.get("nao_conferidos", []):
        diz(f"  NÃO CONFERIDO {nc.get('arquivo')}: {nc.get('motivo')}")
    if not lint["ok"]:
        codigo = SAIDA_ERRO
    diz("CONFERIDO: nada a corrigir." if codigo == SAIDA_OK else "REPROVADO: corrija o que está acima antes de renderizar.")
    return codigo


# ───────────────────────────────────────────────────────────────────── CLI ──
class _Analisador(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        diz(f"erro: {message}\nVeja as opções com --help.", erro=True)
        raise SystemExit(SAIDA_USO)


def montar_cli() -> argparse.ArgumentParser:
    comum = argparse.ArgumentParser(add_help=False)
    comum.add_argument("--projeto", metavar="PASTA", default=argparse.SUPPRESS, help="pasta do projeto (padrão: a atual ou a mais próxima acima que tenha da/da.json)")
    ap = _Analisador(prog="storyboard.py", parents=[comum], formatter_class=argparse.RawDescriptionHelpFormatter,
                     description="Storyboard de animações explicativas: roteiro → cenas → renders, submetido à direção de arte do projeto.",
                     epilog="Fluxo: novo → cenas → adicionar → validar → sincronizar → prever → (aprovação) → render → ancoras → conferir.\n"
                            "Códigos de saída: 0 ok · 1 reprovado/falha · 2 projeto sem direção de arte · 64 uso incorreto.")
    sub = ap.add_subparsers(dest="comando", metavar="<subcomando>", parser_class=_Analisador)

    def novo(nome, ajuda, func, **k):
        s = sub.add_parser(nome, parents=[comum], help=ajuda, description=k.pop("descricao", ajuda), **k)
        s.set_defaults(func=func)
        return s

    s = novo("novo", "cria roteiro/storyboard.json vazio", cmd_novo)
    s.add_argument("--forcar", action="store_true", help="recomeça do zero (o anterior vira storyboard.json.bak)")
    s = novo("cenas", "catálogo: cenas da biblioteca, do kit e do projeto, com os parâmetros de cada uma", cmd_cenas)
    s.add_argument("nome", nargs="?", help="mostra os parâmetros desta cena")
    s.add_argument("--json", action="store_true", help="saída em JSON (meta completo de cada cena)")
    s = novo("adicionar", "acrescenta uma cena ao storyboard", cmd_adicionar)
    s.add_argument("--cena", required=True, help="nome da cena (veja `cenas`) ou caminho .js relativo ao projeto")
    s.add_argument("--id", help="id da cena (padrão: o próximo C##)")
    s.add_argument("--trecho", help="frase do roteiro que a cena cobre; | marca onde dispara o próximo passo")
    s.add_argument("--dur", type=float, help="duração em segundos (padrão: a da cena)")
    s.add_argument("--t0", type=float, help="início no vídeo, em segundos (padrão: null; `sincronizar` preenche)")
    s.add_argument("--params", help="parâmetros da cena em JSON, ou @arquivo.json")
    s.add_argument("--formatos", help="formatos separados por vírgula (padrão: horizontal,vertical)")
    s.add_argument("--fato", action="append", metavar="F###", help="id de fato da ficha (repetível)")
    s.add_argument("--broll", metavar="B###", help="id do b-roll usado na cena")
    s.add_argument("--alfa", choices=("sim", "nao"), help="fundo transparente (padrão: o que a cena declara)")
    s.add_argument("--depois", metavar="ID", help="insere logo depois desta cena (padrão: no fim)")
    s.add_argument("--mesmo-assim", action="store_true", help="grava mesmo reprovando na conferência (rascunho)")
    s = novo("definir", "edita uma cena do storyboard", cmd_definir)
    s.add_argument("id", help="id da cena")
    s.add_argument("--cena"); s.add_argument("--trecho"); s.add_argument("--dur", type=float)
    s.add_argument("--t0", help="segundos, ou `null` para limpar")
    s.add_argument("--params", help="JSON (ou @arquivo) fundido aos parâmetros atuais")
    s.add_argument("--params-novos", action="store_true", help="com --params: substitui todos os parâmetros em vez de fundir")
    s.add_argument("--param", action="append", metavar="CHAVE=JSON", help="define um parâmetro (repetível): --param 'consulta=3'")
    s.add_argument("--sem-param", action="append", metavar="CHAVE", help="remove um parâmetro (volta ao padrão da cena)")
    s.add_argument("--formatos"); s.add_argument("--fato", action="append", metavar="F###", help="substitui fato_ids (repetível; `nenhum` esvazia)")
    s.add_argument("--broll", help="id do b-roll, ou `null`"); s.add_argument("--alfa", choices=("sim", "nao", "padrao"))
    s.add_argument("--mesmo-assim", action="store_true", help="grava mesmo reprovando na conferência (rascunho)")
    s = novo("remover", "tira uma cena do storyboard (os renders ficam em disco)", cmd_remover)
    s.add_argument("id")
    s = novo("mostrar", "resumo do storyboard", cmd_mostrar)
    s.add_argument("--json", action="store_true")
    s = novo("validar", "confere contrato, cenas, parâmetros (validador do motor), formatos e ritmo — sem renderizar", cmd_validar)
    s.add_argument("--estrito", action="store_true", help="avisos também reprovam")
    s.add_argument("--json", action="store_true")
    s = novo("sincronizar", "ancora cada trecho na transcrição e preenche t0, dur e passos_t", cmd_sincronizar,
             descricao="Procura o `trecho` de cada cena em transcricao/*.palavras.json e preenche t0 e dur. Marcas | no trecho viram passos_t: "
                       "o passo seguinte da cena dispara na palavra que vem depois da marca (o 1º passo dispara no começo).")
    s.add_argument("--palavras", metavar="ARQ", help="transcrição palavra a palavra (padrão: a única em transcricao/)")
    s.add_argument("--antecipar", type=float, default=0.2, help="segundos que a cena entra antes da primeira palavra (padrão: 0,2)")
    s.add_argument("--cauda", type=float, default=0.6, help="segundos que a cena fica depois da última palavra (padrão: 0,6)")
    s.add_argument("--manter-dur", action="store_true", help="preenche só t0 e passos_t; não mexe em dur")
    s.add_argument("--so", metavar="IDS", help="só estas cenas (ids separados por vírgula)")
    s.add_argument("--simular", action="store_true", help="mostra o resultado sem gravar")
    for nome, ajuda, func in (("fila", "gera animacoes/_fila_<formato>.json para o motor", cmd_fila), ("render", "renderiza a fila sob a trava (pula o que está em dia; continua após falha)", cmd_render)):
        s = novo(nome, ajuda, func)
        s.add_argument("--formato", metavar="F[,F]", help="só estes formatos (padrão: todos os do storyboard)")
        s.add_argument("--so", metavar="IDS", help="só estas cenas")
        s.add_argument("--escala", type=float, help="resolução reduzida (ex.: 0.5) — só para teste")
        s.add_argument("--codec-alfa", choices=sorted(CODECS_ALFA), default="vp9alfa", help="codec das cenas com alfa: vp9alfa (.webm, compor via ffmpeg) ou prores4444 (.mov, Premiere)")
        if nome == "render":
            s.add_argument("--refazer", action="store_true", help="renderiza mesmo o que está em dia")
            s.add_argument("--inatividade", type=float, help="segundos sem progresso até abortar (padrão do motor: 120)")
    s = novo("prever", "folha de contato com 1 a 3 quadros de cada cena, em escala reduzida — o que o usuário aprova antes do render", cmd_prever)
    s.add_argument("--formato", metavar="F[,F]"); s.add_argument("--so", metavar="IDS")
    s.add_argument("--quadros", type=int, default=2, help="quadros por cena, de 1 a 3 (padrão: 2)")
    s.add_argument("--largura", type=int, default=640, help="largura de cada quadro em px (padrão: 640)")
    s.add_argument("--inatividade", type=float, help="segundos sem progresso até abortar")
    s = novo("ancoras", "exporta animacoes/ancoras.json (instantes dos passos, lidos dos carimbos) para a skill de efeitos sonoros", cmd_ancoras)
    s = novo("conferir", "fatos (video-pesquisa-ia), dado real com fonte e lint das cenas próprias", cmd_conferir)
    s.add_argument("--estrito", action="store_true", help="repassa --estrito à conferência de fatos")
    return ap


def main(argv=None) -> int:
    ap = montar_cli()
    args = ap.parse_args(argv)
    if not getattr(args, "func", None):
        ap.print_help()
        return SAIDA_USO
    if not hasattr(args, "projeto"):
        args.projeto = None
    try:
        return args.func(args)
    except Uso as e:
        diz(f"erro: {e}" + (f"\n{e.dica}" if e.dica else ""), erro=True)
        return e.codigo
    except KeyboardInterrupt:
        diz("interrompido.", erro=True)
        return 130
    except Exception as e:                                     # defeito interno: uma linha; DA_DEBUG=1 mostra o traceback
        if os.environ.get("DA_DEBUG") == "1":
            raise
        nome = type(e).__name__
        if nome == "DAErro" or type(e).__mro__[1].__name__ == "DAErro":
            diz(f"erro: {e}" + (f"\n{e.dica}" if getattr(e, 'dica', None) else ""), erro=True)
            return getattr(e, "codigo", None) or SAIDA_ERRO
        diz(f"erro interno: {nome}: {e}", erro=True)
        return SAIDA_ERRO


if __name__ == "__main__":
    sys.exit(main())
