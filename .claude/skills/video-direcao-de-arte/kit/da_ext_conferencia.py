#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""da_ext_conferencia.py — extensão do da.py: a CONFERÊNCIA FINAL do projeto (camada C5 da submissão à DA).

Subcomando acrescentado
    conferencia   compõe o que o kit já sabe conferir — validar, lint --estrito, conferir-carimbo com DA aprovada,
                  loudness contra som.loudness e os limites de plataforma — mais as conferências das skills irmãs que
                  existirem (ficha de fatos, licenças de b-roll) e grava qa/relatorio.json + qa/relatorio.md. É o
                  portão de publicação: nada vai para publicacao/ sem esse relatório dizendo ok.

Como módulo (import da_ext_conferencia as conferencia)
    r = conferencia.conferir()                                   # projeto do diretório atual; grava qa/relatorio.{json,md}
    r = conferencia.conferir("/caminho/Projeto", cortes=["K01"]) # só um corte (e o que entrou nele)
    r = conferencia.conferir(alvos=["render/final.mp4"], previa=True, gravar=False)
    r["ok"], r["resumo"], r["itens"], r["alvos"]                 # o relatório, no contrato abaixo
    r.json, r.md, r.raiz, r.entregaveis, r.previa, r.restrito    # arquivos gravados (None com gravar=False) e contexto
    conferencia.texto_resumo(r), conferencia.texto_md(r)         # o que a CLI imprime e o que vai para o .md

Contrato do relatório (qa/relatorio.json) — os nomes de campo não mudam
    {"versao": 1, "ok": bool, "verificado_em": "ISO 8601 com fuso (da.agora_iso(), tirada no INÍCIO da conferência)",
     "da_sha256": "identidade da DA conferida",
     "alvos": [{"arquivo": "caminho relativo à raiz do projeto", "sha256": "…", "bytes": n}],
     "resumo": {"erros": n, "avisos": n},
     "itens": [{"id": "…", "categoria": "da|carimbo|lint|tecnico|loudness|zona_segura|fatos|licencas|texto",
                "alvo": "arquivo ou token", "severidade": "erro|aviso|info", "mensagem": "…", "como_corrigir": "…"}]}
`ok` = nenhum item com severidade "erro". `alvos` = os entregáveis conferidos (render/final.mp4 e cortes/*.mp4, ou os
pedidos): quem publica confere que o arquivo dele está na lista com o mesmo sha256.

Nada aqui valida por conta própria: cada item vem de uma função do kit (da.validar, da.lint, da.conferir_carimbo,
video.sondar, video.conferir_loudness, da.plataforma) ou da conferência de uma skill irmã, chamada por posição. Não
renderiza nada; as medições de loudness entram na trava global uma a uma.
"""
from __future__ import annotations

import inspect
import json
import os
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True     # D9: nada de __pycache__ dentro da skill (trava.py apaga o que já tiver nascido)
KIT = Path(__file__).resolve().parent
if str(KIT) not in sys.path:
    sys.path.insert(0, str(KIT))
import da  # noqa: E402

VERSAO_RELATORIO = 1
CATEGORIAS = ("da", "carimbo", "lint", "tecnico", "loudness", "zona_segura", "fatos", "licencas", "texto")
SEVERIDADES = ("erro", "aviso", "info")
PASTA_RELATORIO = "qa"
NOME_RELATORIO = "relatorio"            # qa/relatorio.json + qa/relatorio.md: o portão de publicação
NOME_PREVIA = "previa"                  # qa/previa.json + qa/previa.md: conferência com --previa nunca vira portão
ENTREGAVEL_LONGO = "render/final.mp4"
PASTA_CORTES = "cortes"
EXT_ENTREGAVEL = ".mp4"
# tipo do entregável → alvo de som.loudness e orientação das plataformas de destino (lidas de plataformas.json)
TIPOS = {"longo": "horizontal", "curto": "vertical"}
ROTULO_TIPO = {"longo": "vídeo longo", "curto": "peça curta"}
FICHA_DE_FATOS = "pesquisa/fatos.json"
ROTEIRO = "roteiro/roteiro.md"
STORYBOARD = "roteiro/storyboard.json"
SKILL_FATOS = ("video-pesquisa-ia", "scripts/fatos.py")
SKILL_LICENCAS = ("video-broll", "scripts/registro.py")
REGISTRO_DE_LICENCAS = "broll/licencas.json"
CREDITOS = "broll/creditos.md"
PRAZO_IRMA = 120.0                      # segundos para cada conferência de skill irmã (texto puro, sem ffmpeg)
SKILLS_FINAL = "\"$CRIABR_SKILLS\""

COMO_CORRIGIR_CARIMBO = {
    "sem_carimbo": "Gere a peça pelo kit (o motor, `da grade` e as composições de video.py carimbam sozinhos) ou carimbe o que você "
                   "fez por PIL/ffmpeg com d.carimbar(saida, ferramenta, formato, parametros, insumos=[…]). Arquivo de trabalho "
                   "leva _ no começo do nome e fica fora da conferência.",
    "carimbo_invalido": "Apague o sidecar .da.json ilegível e gere a peça de novo pelo kit.",
    "sha_diferente": "Renderize a peça de novo com a DA atual.",
    "auditoria_pulada": "Renderize de novo com o auditor ligado (sem --sem-auditoria) e refaça as composições que usam a peça; "
                        "carimbar de novo não limpa auditoria pulada.",
    "arquivo_alterado": "O arquivo foi regravado por fora do kit depois do carimbo: gere a peça de novo pelo kit.",
    "da_alterada": "Rode `da revisar` e, com o \"aprovo\" do usuário, `da aprovar`.",
    "da_nao_aprovada": "Rode `da aprovar` depois do \"aprovo\" do usuário.",
    "insumo_de_outra_da": "Renderize o insumo de novo com a DA atual e refaça a composição.",
}


# ──────────────────────────────────────────────────────────────── utilidades ──
class Relatorio(dict):
    """O relatório no contrato (um dict serializável como está) + contexto que NÃO vai para o JSON, em atributos:
    `json`/`md` (arquivos gravados ou None), `raiz`, `entregaveis` ([{arquivo, rel, tipo, plataformas}]), `previa`,
    `restrito` (só os alvos pedidos), `projeto` (nome), `da_revisao`, `da_situacao`."""
    json = None
    md = None
    raiz = None
    entregaveis: list = []
    previa = False
    restrito = False
    projeto = ""
    da_revisao = None
    da_situacao = ""


class _Itens(list):
    """Lista de itens do relatório com ids estáveis e únicos: <categoria>.<regra>[.<n>]."""

    def __init__(self):
        super().__init__()
        self._contagem: dict[str, int] = {}

    def mais(self, categoria: str, regra: str, severidade: str, alvo, mensagem, como_corrigir: str = "", unico: bool = False) -> dict:
        chave = f"{categoria}.{regra}"
        self._contagem[chave] = self._contagem.get(chave, 0) + 1
        ident = chave if unico and self._contagem[chave] == 1 else f"{chave}.{self._contagem[chave]}"
        item = {"id": ident, "categoria": categoria, "alvo": str(alvo), "severidade": severidade,
                "mensagem": " ".join(str(mensagem).split()), "como_corrigir": " ".join(str(como_corrigir or "").split())}
        self.append(item)
        return item


def _rel(caminho, raiz: Path) -> str:
    """Caminho relativo à raiz do projeto, com barras; fora dela, o absoluto."""
    p = Path(str(caminho))
    try:
        return p.resolve().relative_to(raiz.resolve()).as_posix()
    except (ValueError, OSError):
        return str(p)


def _dentro(caminho: Path, pasta: Path) -> bool:
    try:
        caminho.resolve().relative_to(pasta.resolve())
        return True
    except (ValueError, OSError):
        return False


def _e_intermediario(caminho: Path, raiz: Path) -> bool:
    """D15: nome (do arquivo ou de uma pasta acima dele, dentro do projeto) começado por `_`; broll/bruto também não é peça."""
    rel = _rel(caminho, raiz)
    if any(da._e_intermediario(parte) for parte in Path(rel).parts):
        return True
    return any(_dentro(caminho, raiz / p) for p in da.PASTAS_SEM_PECAS)


def _numero(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _seg(s: float) -> str:
    """Duração legível: 185.2 → '3 min 05 s'; 42.25 → '42,3 s'."""
    s = float(s)
    if s < 60:
        return f"{da._ptbr(s, 1)} s"
    m, resto = divmod(int(round(s)), 60)
    h, m = divmod(m, 60)
    return (f"{h} h {m:02d} min" if h else f"{m} min {resto:02d} s")


def _fps(f) -> str:
    return da._ptbr(float(f), 2) if f else "?"


def _mb(n_bytes: int) -> str:
    return f"{da._ptbr(n_bytes / (1024 * 1024), 1)} MB"


def _skill_irma(nome: str, relativo: str) -> Path:
    """Arquivo de uma skill irmã, POR POSIÇÃO (<skills>/<nome>/…), sem depender de ela existir."""
    return KIT.parent.parent / nome / relativo


def _chamada_irma(nome: str, relativo: str) -> str:
    return f"python3 {SKILLS_FINAL}/{nome}/{relativo}"


# ─────────────────────────────────────────────────────────────── entregáveis ──
def _plataformas_do_tipo(tipo: str) -> list[str]:
    """Plataformas de destino de um tipo de entregável: as de plataformas.json cuja resolução recomendada tem a
    orientação do tipo (longo → horizontal; curto → vertical). Nenhum nome de plataforma é fixado aqui."""
    alvo = TIPOS[tipo]
    nomes = []
    for nome in da.PLATAFORMAS:
        res = da.plataforma(nome).get("resolucao_px")
        if isinstance(res, list) and len(res) == 2 and all(_numero(x) for x in res) and da.orientacao_de(*res) == alvo:
            nomes.append(nome)
    return nomes


def _plataformas_do_carimbo(arquivo: Path) -> list[str]:
    """Plataforma(s) que a skill que fez o corte declarou no carimbo (parametros.plataforma / .plataformas). Zona que
    não é plataforma ('uniao', 'padrao') não restringe nada."""
    c = da.ler_carimbo(arquivo) or {}
    p = c.get("parametros") if isinstance(c.get("parametros"), dict) else {}
    brutos = p.get("plataformas") if isinstance(p.get("plataformas"), list) else [p.get("plataforma")]
    nomes = []
    for b in brutos:
        if not isinstance(b, str) or not b.strip():
            continue
        try:
            n = da.nome_plataforma(b)
        except da.DAErro:
            continue
        if n not in nomes:
            nomes.append(n)
    return nomes


def _resolver_alvo(arg, raiz: Path, pasta_padrao: str | None = None) -> Path:
    """Arquivo pedido na linha de comando: como veio (a partir do diretório atual), relativo à raiz do projeto ou —
    para --corte — dentro de cortes/, com ou sem extensão. Fora do projeto ou inexistente: erro de uso (64)."""
    bruto = Path(str(arg)).expanduser()
    candidatos = [bruto] if bruto.is_absolute() else [Path.cwd() / bruto, raiz / bruto]
    if pasta_padrao and not bruto.is_absolute():
        candidatos += [raiz / pasta_padrao / bruto, raiz / pasta_padrao / (bruto.name + EXT_ENTREGAVEL)]
        candidatos += [raiz / pasta_padrao / (bruto.name + ext) for ext in sorted(da.EXT_VIDEO) if ext != EXT_ENTREGAVEL]
    existentes = [c for c in candidatos if c.is_file()]
    achado = next((c for c in existentes if _dentro(c, raiz)), existentes[0] if existentes else None)    # dentro do projeto primeiro
    if achado is None:
        if any(c.is_dir() for c in candidatos):
            raise da.DAErro(f"conferencia: {arg} é uma pasta; o alvo é um arquivo de vídeo (ex.: {ENTREGAVEL_LONGO})", codigo=da.SAIDA_USO)
        dica = None
        if pasta_padrao:
            cortes = [p.name for p in _cortes_do_projeto(raiz)]
            dica = ("Cortes do projeto: " + ", ".join(cortes)) if cortes else f"Não há nenhum {EXT_ENTREGAVEL} em {pasta_padrao}/."
        raise da.DAErro(f"conferencia: não encontrei o alvo {arg} (procurei a partir daqui e da raiz do projeto {raiz})", dica=dica,
                        codigo=da.SAIDA_USO)
    achado = achado.resolve()
    if not _dentro(achado, raiz):
        raise da.DAErro(f"conferencia: {achado} está fora do projeto ({raiz}); o relatório só aponta para arquivos do projeto",
                        dica="Copie ou exporte o arquivo para render/ ou cortes/ e confira de novo.", codigo=da.SAIDA_USO)
    return achado


def _cortes_do_projeto(raiz: Path) -> list[Path]:
    pasta = raiz / PASTA_CORTES
    if not pasta.is_dir():
        return []
    return sorted(p for p in pasta.iterdir()
                  if p.is_file() and p.suffix.lower() == EXT_ENTREGAVEL and not p.name.startswith(".")
                  and not da._e_intermediario(p.name) and ".parcial." not in p.name)


def listar_entregaveis(raiz, alvos=None, cortes=None, plataformas=None) -> list[dict]:
    """Os entregáveis de uma conferência: [{'arquivo': Path, 'rel', 'tipo': 'longo'|'curto', 'plataformas': [...]}].

    Sem `alvos` nem `cortes`: render/final.mp4 (longo), se existir, e cortes/*.mp4 (curtos; só o primeiro nível, sem
    intermediários de nome começado por _). `alvos`: arquivos pedidos — curto se está em cortes/, longo se não.
    `cortes`: arquivos ou nomes de corte, sempre conferidos como peça curta (é também como se confere uma peça
    vertical nativa que mora em render/). `plataformas`: destino dos curtos; sem isso vale a plataforma declarada no
    carimbo do corte e, na falta dela, todas as de orientação vertical em plataformas.json."""
    raiz = Path(raiz).resolve()
    pedidas = []
    for p in plataformas or []:
        try:
            n = da.nome_plataforma(p)
        except da.DAErro as e:
            raise da.DAErro(f"conferencia: {e.mensagem}", codigo=da.SAIDA_USO)
        if n not in pedidas:
            pedidas.append(n)
    lista: list[tuple[Path, str]] = []
    if alvos or cortes:
        for a in alvos or []:
            arq = _resolver_alvo(a, raiz)
            lista.append((arq, "curto" if _dentro(arq, raiz / PASTA_CORTES) else "longo"))
        for c in cortes or []:
            lista.append((_resolver_alvo(c, raiz, PASTA_CORTES), "curto"))
    else:
        if (raiz / ENTREGAVEL_LONGO).is_file():
            lista.append(((raiz / ENTREGAVEL_LONGO).resolve(), "longo"))
        lista += [(p.resolve(), "curto") for p in _cortes_do_projeto(raiz)]
    saida, vistos = [], {}
    for arq, tipo in lista:
        if arq in vistos:
            if tipo == "curto":                       # pedido como alvo e como --corte: vale a peça curta
                vistos[arq]["tipo"] = "curto"
            continue
        ent = {"arquivo": arq, "rel": _rel(arq, raiz), "tipo": tipo, "plataformas": []}
        vistos[arq] = ent
        saida.append(ent)
    for ent in saida:
        do_tipo = _plataformas_do_tipo(ent["tipo"])
        ent["plataformas"] = ((pedidas or _plataformas_do_carimbo(ent["arquivo"]) or do_tipo) if ent["tipo"] == "curto" else do_tipo)
    return saida


# ───────────────────────────────────────────────────────────────────── (a) DA ──
def _conferir_da(da_json: Path, itens: _Itens, previa: bool):
    """validar sem erros + DA aprovada e não alterada depois da aprovação. Devolve (DA carregada ou None, validação)."""
    alvo = "da/da.json"
    try:
        v = da.validar(da_json)
    except da.SemDA:
        raise
    except da.DAErro as e:                             # da.json que nem dá para ler (JSON quebrado, `herda` que não existe)
        v = {"erros": [e.mensagem + (f" — {e.dica}" if getattr(e, "dica", None) else "")], "avisos": [], "notas": [],
             "sha256": "", "revisao": None}
    for e in v["erros"]:
        itens.mais("da", "erro", "erro", alvo, e, "Corrija o da.json e rode `da validar` até sair sem erros.")
    if v["erros"]:
        itens.mais("da", "invalida", "erro", alvo,
                   "a DA não passa na validação: lint, carimbos, loudness e limites de plataforma NÃO foram conferidos",
                   "Corrija os erros acima (`da validar`), compile (`da compilar`) e rode `da conferencia` de novo.", unico=True)
        return None, v
    d = da.carregar(da_json, compilar=False)           # só em memória: a conferência não regrava da/build/ nem o DA.md
    for a in v["avisos"]:
        if "DEPOIS DA APROVAÇÃO" in a:
            continue                                   # vira o item da.alterada_apos_aprovacao, abaixo
        itens.mais("da", "aviso", "aviso", alvo, a,
                   "Aviso do `da validar`: ajuste o token (nova revisão, se a DA já foi aprovada) ou siga ciente dele.")
    for n in v["notas"]:
        itens.mais("da", "nota", "info", alvo, n)
    if d.meta.get("alterada_apos_aprovacao"):
        itens.mais("da", "alterada_apos_aprovacao", "erro", alvo,
                   f"DA ALTERADA DEPOIS DA APROVAÇÃO: o da.json foi editado depois do `aprovar` da revisão {d.revisao} — o visual em "
                   "vigor não é o que o usuário aprovou",
                   "Rode `da revisar`, gere a prancha e o teste de movimento de novo, mostre ao usuário e rode `da aprovar`; depois "
                   "renderize outra vez as peças que `da conferir-carimbo` marcar como DA DIFERENTE.", unico=True)
    elif not d.aprovada:
        itens.mais("da", "nao_aprovada", "aviso" if previa else "erro", alvo,
                   f"a DA (revisão {d.revisao}) ainda não foi aprovada"
                   + (" — rebaixado a aviso porque esta conferência é uma prévia (--previa)" if previa else ""),
                   "Rode `da aprovar` depois do \"aprovo\" do usuário sobre a prancha e o teste de movimento "
                   "(`da aprovar --estrito` recusa se os dois não estiverem em dia).", unico=True)
    return d, v


# ─────────────────────────────────────────────────────────────────── (b) lint ──
def _conferir_lint(d, itens: _Itens) -> dict:
    r = da.lint(None, da=d, estrito=True)
    raiz = d.raiz
    for a in r["achados"]:
        itens.mais("lint", str(a.get("regra") or "achado"), "erro", _rel(a["arquivo"], raiz),
                   f"linha {a.get('linha')}, coluna {a.get('coluna')}: [{a.get('regra')}] {a.get('trecho')}"
                   + ("" if a.get("severidade") == "erro" else " (aviso do lint: reprova no modo estrito)"),
                   str(a.get("sugestao") or "Troque o literal pelo token da DA."))
    for f in r["nao_conferidos"]:
        itens.mais("lint", "nao_conferido", "erro", _rel(f["arquivo"], raiz), f"NÃO CONFERIDO pelo lint — {f['motivo']}",
                   "O lint só dá sinal verde para o que leu: escreva a fonte da peça numa linguagem que ele lê, ou dê ao arquivo um "
                   "nome começado por _ se ele é intermediário e não peça.")
    for n in r["notas"]:
        itens.mais("lint", "nota", "info", "pastas de peças", n)
    if r["arquivos"] == 0:
        itens.mais("lint", "nada_lido", "info", "pastas de peças",
                   "o lint não leu nenhum arquivo: não há fonte de peça (HTML, CSS, JS, JSON, SVG, Python) em "
                   + ", ".join(da.PASTAS_COM_PECAS) + " — nada a reprovar, e nada conferido", unico=True)
    else:
        itens.mais("lint", "resumo", "info", "pastas de peças",
                   f"lint --estrito: {r['arquivos']} arquivo(s) lido(s), {r['erros']} violação(ões), {r['avisos']} aviso(s), "
                   f"{len(r['nao_conferidos'])} não conferido(s)", unico=True)
    return r


# ──────────────────────────────────────────────────────────────── (c) carimbo ──
def _flags_de_zona(no, caminho: str = "layout", fundo: int = 0) -> list[str]:
    """Chaves `…_na_zona` / `dentro_da_zona` que o próprio kit gravou como False no layout do carimbo."""
    achadas = []
    if isinstance(no, dict) and fundo < 4:
        for k, v in no.items():
            if v is False and (str(k).endswith("na_zona") or str(k) == "dentro_da_zona"):
                achadas.append(f"{caminho}.{k}")
            elif isinstance(v, dict):
                achadas += _flags_de_zona(v, f"{caminho}.{k}", fundo + 1)
    return achadas


def _conferir_carimbos(d, entregaveis: list[dict], restrito: bool, previa: bool, itens: _Itens) -> list[dict]:
    """conferir-carimbo com exigência de DA aprovada (menos em prévia): as pastas de peças do projeto (broll/tratado
    incluída) — ou, numa conferência restrita, só os alvos — e os insumos carimbados das composições."""
    raiz = d.raiz
    exigir = not previa
    if restrito:
        caminhos = [e["arquivo"] for e in entregaveis]
    else:
        caminhos = [raiz / p for p in da.PASTAS_COM_PECAS if (raiz / p).is_dir()]
    pecas = list(da.conferir_carimbo(caminhos, da=d, exigir_aprovada=exigir)["pecas"]) if caminhos else []
    vistos = {str(Path(p["arquivo"]).resolve()) for p in pecas}
    extras, fila = [], list(pecas)
    while fila:                                        # insumos das composições que são peças e ficaram fora da varredura
        novos = []                                     # (e os insumos deles: a cadeia inteira, uma leva por vez)
        for p in fila:
            for ins in p.get("insumos") or []:
                cam = ins.get("caminho")
                if not ins.get("carimbado") or not cam:
                    continue
                arq = Path(str(cam))
                if not arq.exists() or str(arq.resolve()) in vistos or _e_intermediario(arq, raiz):
                    continue
                vistos.add(str(arq.resolve()))
                novos.append(arq)
        fila = da.conferir_carimbo(novos, da=d, exigir_aprovada=exigir)["pecas"] if novos else []
        extras += novos
        pecas += fila
    agrupar = {"da_nao_aprovada": [], "da_alterada": []}          # um item só: o motivo é da DA, não de cada peça
    for p in pecas:
        rel = _rel(p["arquivo"], raiz)
        estado = p["estado"]
        if estado in agrupar:
            agrupar[estado].append(rel)
        elif estado != "ok":
            itens.mais("carimbo", estado, "erro", rel, f"{da.ESTADOS_CARIMBO[estado]} — {p.get('detalhe') or 'sem detalhe'}",
                       COMO_CORRIGIR_CARIMBO.get(estado, "Gere a peça de novo pelo kit."))
        else:
            if p.get("livres"):
                itens.mais("carimbo", "livres", "info", rel,
                           f"{len(p['livres'])} elemento(s) data-da-livre (fora da auditoria de cor): "
                           + ", ".join(str(x.get("seletor", "?")) + (f" ({x['motivo']})" if x.get("motivo") else "")
                                       for x in p["livres"][:6] if isinstance(x, dict)),
                           "Confira se cada um é mesmo foto, logo de terceiros ou captura de tela.")
            sem = [str(i.get("arquivo")) for i in (p.get("insumos") or []) if not i.get("carimbado")]
            if sem:
                itens.mais("carimbo", "insumo_sem_carimbo", "info", rel, f"insumo(s) sem carimbo (material bruto?): {', '.join(sem[:6])}")
        params = (p.get("carimbo") or {}).get("parametros")
        for flag in _flags_de_zona(params.get("layout")) if isinstance(params, dict) else []:
            itens.mais("zona_segura", "fora_da_zona", "aviso", rel,
                       f"o carimbo da peça registra {flag} = false: o kit mediu um elemento fora da zona segura",
                       "Encurte o texto ou tire a área pedida à mão, renderize de novo e confira `layout` no carimbo.")
    for estado, lista in agrupar.items():
        if lista:
            itens.mais("carimbo", estado, "erro", "da/da.json",
                       f"{da.ESTADOS_CARIMBO[estado]}: {len(lista)} peça(s) com carimbo em dia reprovam por causa da DA — "
                       + ", ".join(lista[:8]) + ("…" if len(lista) > 8 else ""), COMO_CORRIGIR_CARIMBO[estado], unico=True)
    em_dia = sum(1 for p in pecas if p["estado"] == "ok")
    itens.mais("carimbo", "resumo", "info", "alvos pedidos e insumos" if restrito else "pastas de peças",
               f"conferir-carimbo{' --exigir-aprovada' if exigir else ''}: {len(pecas)} peça(s), {em_dia} em dia"
               + (f" ({len(extras)} insumo(s) de composição conferido(s) fora da varredura)" if extras else ""), unico=True)
    return pecas


# ────────────────────────────────────────────────────────────── (e) técnica ──
def _conferir_tecnica(d, ent: dict, itens: _Itens, video) -> dict | None:
    """Duração, orientação/resolução, tamanho, fps e formato de entrega de um entregável, contra os limites de
    plataforma (da.plataforma) e os formatos da DA. Devolve a sondagem (ou None se o arquivo não pôde ser lido)."""
    arq, rel = ent["arquivo"], ent["rel"]
    try:
        s = video.sondar(arq)
    except da.DAErro as e:
        itens.mais("tecnico", "ilegivel", "erro", rel, e.mensagem, "Exporte o arquivo de novo: o ffprobe não conseguiu lê-lo.")
        return None
    L, A = int(s.get("largura") or 0), int(s.get("altura") or 0)
    if not L or not A:
        itens.mais("tecnico", "sem_video", "erro", rel, "o arquivo não tem trilha de vídeo", "Exporte o entregável de novo.")
        return None
    dur, tam = float(s.get("duracao") or 0.0), arq.stat().st_size
    orient = da.orientacao_de(L, A)
    fps = s.get("fps")
    itens.mais("tecnico", "medidas", "info", rel,
               f"{ROTULO_TIPO[ent['tipo']]} {L}×{A} ({orient}), {_fps(fps)} fps, {_seg(dur)}, "
               f"{s.get('codec')} {s.get('pix_fmt')}, {_mb(tam)}, {'com' if s.get('tem_audio') else 'SEM'} áudio — conferido contra "
               + (", ".join(ent["plataformas"]) or "nenhuma plataforma"))
    # limites de cada plataforma de destino (plataformas.json, por da.plataforma)
    abaixo: dict[str, list[str]] = {}                  # resolução recomendada que a peça não alcança → plataformas
    for nome in ent["plataformas"]:
        f = da.plataforma(nome)
        maximo, minimo, recomendada = f.get("duracao_max_s"), f.get("duracao_min_s"), f.get("duracao_max_recomendada_s")
        if _numero(maximo) and dur > maximo:
            itens.mais("tecnico", "duracao_max", "erro", rel,
                       f"duração de {_seg(dur)} passa do máximo de {nome} ({_seg(maximo)})",
                       f"Encurte a peça para caber em {nome}, ou tire {nome} do destino deste corte (--plataforma) se ele não vai para lá.")
        elif _numero(recomendada) and dur > recomendada:
            itens.mais("tecnico", "duracao_recomendada", "aviso", rel,
                       f"duração de {_seg(dur)} passa da recomendada por {nome} ({_seg(recomendada)}); o máximo é {_seg(maximo) if _numero(maximo) else 'não publicado'}",
                       "Aceitável; a plataforma entrega melhor peças dentro da duração recomendada.")
        if _numero(minimo) and dur < minimo:
            itens.mais("tecnico", "duracao_min", "erro", rel, f"duração de {_seg(dur)} fica abaixo do mínimo de {nome} ({_seg(minimo)})",
                       f"Alongue a peça ou tire {nome} do destino deste corte (--plataforma).")
        teto = f.get("tamanho_max_mb")
        if _numero(teto) and tam > teto * 1024 * 1024:
            itens.mais("tecnico", "tamanho", "erro", rel, f"arquivo de {_mb(tam)} passa do teto de {nome} ({da._num(teto)} MB)",
                       "Exporte de novo com mais compressão (crf maior em video.args_encode).")
        res = f.get("resolucao_px")
        if isinstance(res, list) and len(res) == 2 and all(_numero(x) for x in res):
            pedida = da.orientacao_de(*res)
            if orient != pedida:
                opostas = {orient, pedida} == {"horizontal", "vertical"}
                itens.mais("tecnico", "orientacao", "erro" if opostas else "aviso", rel,
                           f"a peça é {orient} ({L}×{A}) e {nome} pede {pedida} ({res[0]}×{res[1]})",
                           ("Se esta é uma peça curta vertical, confira-a com --corte; se é o vídeo longo, exporte no formato horizontal da DA."
                            if ent["tipo"] == "longo" else
                            "Recorte com video.filtro_recorte ou encaixe com video.filtro_encaixe para o formato vertical da DA."))
            elif min(L, A) < min(res):
                abaixo.setdefault(f"{res[0]}×{res[1]}", []).append(nome)
    # formato da DA para a orientação da peça (um aviso só de resolução por entregável)
    try:
        dl, dal = d.dimensoes(orient)
    except da.DAErro:
        dl = dal = None
    fora_da_da = bool(dl) and (L, A) != (dl, dal)
    if fora_da_da or abaixo:
        partes = ([f"diferente do formato {orient} da DA ({dl}×{dal})"] if fora_da_da else []) \
            + ([f"abaixo da recomendada por {'; '.join(', '.join(n) + ' (' + r + ')' for r, n in abaixo.items())}"] if abaixo else [])
        itens.mais("tecnico", "resolucao", "aviso", rel, f"resolução {L}×{A} " + " e ".join(partes),
                   "Entregável sai na resolução do formato da DA; prévia reduzida (--escala) não é entregável: renderize a versão final.")
    try:
        fps_da = video.fps_do_formato(d, orient if dl else f"{L}x{A}")
    except da.DAErro:
        fps_da = None
    if fps and fps_da and round(float(fps), 2) != round(float(fps_da), 2):
        itens.mais("tecnico", "fps", "aviso", rel, f"{_fps(fps)} fps; o formato {orient} da DA é {_fps(fps_da)} fps",
                   "Exporte com video.args_encode(d, formato=…), que usa o fps do formato na DA.")
    # formato de entrega da casa: o que video.args_encode produz
    enc = video.args_encode(d, formato=orient if dl else "horizontal")
    pix = enc[enc.index("-pix_fmt") + 1] if "-pix_fmt" in enc else None
    codec = next((nome for nome, spec in video.CODECS.items() if not spec[1]), None)
    if (codec and s.get("codec") != codec) or (pix and s.get("pix_fmt") != pix) or s.get("tem_alfa"):
        itens.mais("tecnico", "formato_de_entrega", "aviso", rel,
                   f"codec {s.get('codec')} / {s.get('pix_fmt')}; o formato de entrega do kit é {codec} {pix} (video.args_encode)",
                   "Exporte o entregável com video.args_encode: H.264 opaco com +faststart é o que as plataformas pedem.")
    return s


# ──────────────────────────────────────────────────────────────── (d) loudness ──
def _conferir_loudness(d, ent: dict, itens: _Itens, video) -> None:
    arq, rel, tipo = ent["arquivo"], ent["rel"], ent["tipo"]
    token = f"som.loudness.{tipo}"
    try:
        r = video.conferir_loudness(d, arq, tipo)
    except da.DAErro as e:
        itens.mais("loudness", "sem_medida", "erro", rel, f"não foi possível medir o loudness: {e.mensagem}",
                   "O entregável precisa de trilha de áudio com som; refaça o mix (video-mixagem) e exporte de novo.")
        return
    m, alvo, desvio = r["medido"], r["alvo"], r["desvio_lufs"]
    pico = m.get("pico_real")
    medido = (f"{da._ptbr(m['lufs'], 1)} LUFS" + (f", pico {da._ptbr(pico, 1)} dBTP" if pico is not None else "")
              + f"; alvo {token} = {da._ptbr(alvo['lufs'], 1)} LUFS / {da._ptbr(alvo['pico_real'], 1)} dBTP")
    if r["ok"]:
        itens.mais("loudness", "medido", "info", rel, f"dentro do alvo — {medido} (desvio {da._ptbr(desvio, 1)})")
        return
    tolerancia = inspect.signature(video.conferir_loudness).parameters["tolerancia"].default
    conserto = ("Refaça o mix na video-mixagem para o alvo da DA." if tipo == "longo" else
                "Normalize em duas passagens: video.medir_para_loudnorm(arq, d, \"curto\", folga_pico=0.5) + "
                "video.filtro_loudnorm(d, \"curto\", medida=…, folga_pico=0.5), como a video-cortes-verticais faz.")
    if abs(desvio) > tolerancia:
        itens.mais("loudness", "fora_do_alvo", "erro", rel,
                   f"loudness fora do alvo — {medido}: desvio de {da._ptbr(desvio, 1)} LU (tolerância ±{da._ptbr(tolerancia, 1)})", conserto)
    if r["estoura_pico"]:
        itens.mais("loudness", "pico", "erro", rel, f"pico real acima do teto — {medido}",
                   conserto + " O AAC devolve o pico ~0,2 dB acima do limitador: é para isso a folga_pico.")


# ─────────────────────────────────────────────────── (f) skills irmãs: fatos ──
def _rodar_irma(script: Path, args: list[str], raiz: Path):
    """Roda a conferência de uma skill irmã e devolve (código, json ou None, stderr)."""
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    try:
        r = subprocess.run([sys.executable, str(script), *args], capture_output=True, text=True, stdin=subprocess.DEVNULL,
                           timeout=PRAZO_IRMA, cwd=str(raiz), env=env)
    except subprocess.TimeoutExpired:
        return None, None, f"não respondeu em {int(PRAZO_IRMA)} s"
    except OSError as e:
        return None, None, str(e)
    try:
        dados = json.loads(r.stdout) if r.stdout.strip() else None
    except json.JSONDecodeError:
        dados = None
    return r.returncode, (dados if isinstance(dados, dict) else None), (r.stderr or "").strip()


def _conferir_fatos(raiz: Path, itens: _Itens) -> None:
    """Se o projeto tem ficha de fatos, chama (por posição) fatos.py validar --estrito, conferir-roteiro --estrito e
    conferir-storyboard da video-pesquisa-ia. Skill ausente = item "info", nunca erro."""
    ficha = raiz / FICHA_DE_FATOS
    if not ficha.is_file():
        itens.mais("fatos", "sem_ficha", "info", FICHA_DE_FATOS,
                   "o projeto não tem ficha de fatos: a conferência de fatos não se aplica (ela é da skill video-pesquisa-ia)", unico=True)
        return
    script = _skill_irma(*SKILL_FATOS)
    chamada = _chamada_irma(*SKILL_FATOS)
    if not script.is_file():
        itens.mais("fatos", "skill_ausente", "info", FICHA_DE_FATOS,
                   f"o projeto tem {FICHA_DE_FATOS}, mas a skill {SKILL_FATOS[0]} não está instalada ao lado desta: ficha, roteiro e "
                   "storyboard NÃO foram conferidos contra os fatos",
                   f"Instale a skill {SKILL_FATOS[0]} em {SKILLS_FINAL}/ e rode `da conferencia` de novo.", unico=True)
        return
    conserto = f"Resolva pela skill {SKILL_FATOS[0]} e confira com `{chamada} "
    # (regra, alvo, subcomando como se digita, argumentos, avisos reprovam?)
    chamadas = [("ficha", FICHA_DE_FATOS, "validar --estrito", ["validar", "--estrito"], True)]
    if (raiz / ROTEIRO).is_file():
        chamadas.append(("roteiro", ROTEIRO, f"conferir-roteiro {ROTEIRO} --estrito", ["conferir-roteiro", str(raiz / ROTEIRO), "--estrito"], True))
    else:
        itens.mais("fatos", "sem_roteiro", "info", ROTEIRO, f"não há {ROTEIRO}: o roteiro não foi cruzado com a ficha de fatos", unico=True)
    if (raiz / STORYBOARD).is_file():
        chamadas.append(("storyboard", STORYBOARD, "conferir-storyboard", ["conferir-storyboard", str(raiz / STORYBOARD)], False))
    for regra, alvo, sub, args, estrito in chamadas:
        codigo, rel, stderr = _rodar_irma(script, [*args, "--json", "--projeto", str(raiz)], raiz)
        if rel is None or codigo not in (0, 1):
            itens.mais("fatos", f"{regra}_nao_conferido", "erro", alvo,
                       f"`fatos.py {sub}` não devolveu resultado (código {codigo}): {stderr[-300:] or 'sem mensagem'}",
                       f"Rode `{chamada} {sub}` na raiz do projeto e resolva o que ele disser.")
            continue
        graves = rel.get("erros") if regra == "ficha" else rel.get("pendencias")
        leves = rel.get("avisos")
        for nivel, lista in (("grave", graves), ("leve", leves)):
            for a in lista if isinstance(lista, list) else []:
                if not isinstance(a, dict):
                    continue
                reprova = nivel == "grave" or estrito
                if regra == "ficha":
                    onde = f"{alvo}#{a.get('id')}" if a.get("id") else alvo
                    texto = f"{a.get('campo')}: {a.get('mensagem')}" if a.get("campo") else str(a.get("mensagem"))
                else:
                    onde = f"{alvo}:{a['linha']}" if a.get("linha") else (f"{alvo}#{a['cena']}" if a.get("cena") else alvo)
                    texto = f"[{a.get('tipo')}] {a.get('detalhe')}" + (f" — “{str(a['frase'])[:160]}”" if a.get("frase") else "")
                if nivel == "leve" and estrito:
                    texto += " (aviso: reprova no modo estrito)"
                itens.mais("fatos", regra, "erro" if reprova else "aviso", onde, texto, conserto + sub + "`.")
        if not (graves or leves):
            itens.mais("fatos", f"{regra}_ok", "info", alvo, f"`fatos.py {sub}`: sem pendências nem avisos")


# ──────────────────────────────────────────────── (f) skills irmãs: licenças ──
def _conferir_licencas(raiz: Path, itens: _Itens) -> None:
    """Registro de licenças do b-roll (broll/licencas.json, da video-broll): todo item que exige atribuição precisa
    estar em broll/creditos.md. Lê os dois arquivos; não depende da skill."""
    registro = raiz / REGISTRO_DE_LICENCAS
    if not registro.is_file():
        itens.mais("licencas", "sem_registro", "info", REGISTRO_DE_LICENCAS,
                   "o projeto não tem registro de licenças de b-roll: nada a conferir (ele é gravado pela skill video-broll)", unico=True)
        return
    regravar = f"Regrave os créditos com `{_chamada_irma(*SKILL_LICENCAS)} creditos` e leve a seção \"Para a descrição\" à descrição do vídeo."
    try:
        dados = da.ler_json(registro)
        lista = dados.get("itens") if isinstance(dados, dict) else None
        if not isinstance(lista, list):
            raise da.DAErro("não tem o formato do contrato ({\"versao\": 1, \"itens\": [...]})")
    except da.DAErro as e:
        itens.mais("licencas", "registro_ilegivel", "erro", REGISTRO_DE_LICENCAS, f"registro de licenças ilegível: {e.mensagem}",
                   "Conserte o arquivo ou restaure a cópia licencas.json.bak ao lado (skill video-broll).", unico=True)
        return
    lista = [i for i in lista if isinstance(i, dict)]
    usados = [i for i in lista if i.get("usado_em")]
    exigem = [i for i in (usados or lista) if i.get("exige_atribuicao")]       # a mesma regra do creditos.md da video-broll
    creditos = raiz / CREDITOS
    try:
        texto = " ".join(creditos.read_text(encoding="utf-8").split()) if creditos.is_file() else None
    except (OSError, UnicodeDecodeError):
        texto = None
    faltam = 0
    for i in exigem:
        onde = f"{REGISTRO_DE_LICENCAS}#{i.get('id')}"
        atribuicao = " ".join(str(i.get("atribuicao") or "").split())
        if not atribuicao:
            faltam += 1
            itens.mais("licencas", "sem_atribuicao", "erro", onde,
                       f"o item {i.get('id')} ({i.get('licenca')}) exige atribuição e não tem o texto de atribuição no registro",
                       "Complete autor, título e página do item pela skill video-broll (registro.py atualizar) e regrave os créditos.")
        elif texto is None or atribuicao not in texto:
            faltam += 1
            itens.mais("licencas", "sem_credito", "erro", onde,
                       f"o item {i.get('id')} ({i.get('licenca')}) exige atribuição e ela não aparece em {CREDITOS}"
                       + (" (o arquivo não existe)" if texto is None else "") + f": {atribuicao[:200]}", regravar)
    itens.mais("licencas", "resumo", "info", REGISTRO_DE_LICENCAS,
               f"{len(lista)} item(ns) no registro" + (f", {len(usados)} marcado(s) como usado(s)" if usados else ", nenhum com usado_em (vale o registro inteiro)")
               + f"; {len(exigem)} exige(m) atribuição, {len(exigem) - faltam} com o crédito em {CREDITOS}", unico=True)


# ─────────────────────────────────────────────────────────────── a conferência ──
def caminhos_do_relatorio(raiz, saida=None, previa: bool = False) -> tuple[Path, Path]:
    """(arquivo .json, arquivo .md). Padrão: <raiz>/qa/relatorio.json e .md — em prévia, qa/previa.json e .md, para
    uma prévia nunca servir de portão de publicação. `saida`: pasta, ou o caminho do .json (o .md vai ao lado)."""
    nome = NOME_PREVIA if previa else NOME_RELATORIO
    if saida:
        s = Path(str(saida)).expanduser()
        if s.suffix.lower() == ".json":
            return s, s.with_suffix(".md")
        return s / f"{nome}.json", s / f"{nome}.md"
    pasta = Path(raiz) / PASTA_RELATORIO
    return pasta / f"{nome}.json", pasta / f"{nome}.md"


def conferir(caminho=None, de=None, alvos=None, cortes=None, plataformas=None, previa: bool = False, saida=None,
             gravar: bool = True) -> Relatorio:
    """A conferência final do projeto. Devolve o relatório (um dict no contrato de qa/relatorio.json, com o contexto
    em atributos) e, com gravar=True, grava o .json e o .md.

    caminho/de:  como em da.carregar (da.json ou pasta do projeto / pasta de onde procurar). Sem DA: SemDA (código 2).
    alvos:       entregáveis a conferir no lugar do padrão (render/final.mp4 + cortes/*.mp4). Arquivo em cortes/ é
                 peça curta; fora dela, vídeo longo.
    cortes:      arquivos ou nomes de corte ("K01", "cortes/K01.mp4"), sempre conferidos como peça curta. Com `alvos`
                 ou `cortes` a conferência é RESTRITA: carimbo, loudness e técnica valem só para eles (e para os insumos
                 carimbados deles); DA, lint, fatos e licenças continuam sendo do projeto inteiro.
    plataformas: destino dos curtos (nomes ou apelidos); padrão: o que o carimbo do corte declara, senão todas as
                 verticais de plataformas.json.
    previa:      DA ainda não aprovada vira aviso em vez de erro, e o relatório vai para qa/previa.json.
    saida:       pasta ou arquivo .json do relatório (padrão: <projeto>/qa/)."""
    verificado_em = da.agora_iso()                     # no início: o que mudar durante a conferência fica mais novo que ela
    da_json = da.achar(de=de, da=caminho).resolve()
    raiz = da.raiz_do_projeto(da_json).resolve()
    itens = _Itens()
    restrito = bool(alvos or cortes)
    entregaveis = listar_entregaveis(raiz, alvos, cortes, plataformas)      # erro de uso sai antes de qualquer conferência
    arq_json, arq_md = caminhos_do_relatorio(raiz, saida, previa)
    portao = raiz / PASTA_RELATORIO / f"{NOME_RELATORIO}.json"
    if gravar and previa and arq_json.resolve() == portao.resolve():
        raise da.DAErro(f"conferencia: uma prévia não pode ser gravada em {_rel(portao, raiz)}, que é o portão de publicação",
                        dica=f"Tire o --saida (a prévia vai para {PASTA_RELATORIO}/{NOME_PREVIA}.json) ou escolha outro arquivo.",
                        codigo=da.SAIDA_USO)
    d, validacao = _conferir_da(da_json, itens, previa)
    lista_alvos = []
    if d is not None:
        import video  # noqa: E402  (só aqui: `da --help` não precisa do ffmpeg)
        _conferir_lint(d, itens)
        _conferir_carimbos(d, entregaveis, restrito, previa, itens)
        if not entregaveis:
            itens.mais("tecnico", "sem_entregavel", "aviso", f"{ENTREGAVEL_LONGO}, {PASTA_CORTES}/*{EXT_ENTREGAVEL}",
                       "nenhum entregável encontrado: loudness e limites de plataforma não foram conferidos, e o relatório não "
                       "libera a publicação de nenhum arquivo",
                       f"Finalize {ENTREGAVEL_LONGO} (video-montagem + video-mixagem) ou os cortes em {PASTA_CORTES}/ e rode de novo.",
                       unico=True)
        vencidas = False
        for ent in entregaveis:
            arq = ent["arquivo"]
            lista_alvos.append({"arquivo": ent["rel"], "sha256": da.sha256_arquivo(arq), "bytes": arq.stat().st_size})
            sonda = _conferir_tecnica(d, ent, itens, video)
            if sonda is not None:
                _conferir_loudness(d, ent, itens, video)
            vencidas = vencidas or any(da.plataforma(n).get("vencida") for n in ent["plataformas"])
        if vencidas:
            ficha = da.plataforma(da.PLATAFORMAS[0])
            itens.mais("tecnico", "plataformas_vencidas", "aviso", "plataformas.json",
                       f"os limites de plataforma foram verificados em {ficha.get('verificado_em')} (há {ficha.get('idade_dias')} dia(s)) "
                       "e passaram do prazo de revalidação", "Revalide os limites (references/plataformas.md §8) antes de publicar.", unico=True)
    _conferir_fatos(raiz, itens)
    _conferir_licencas(raiz, itens)
    erros = sum(1 for i in itens if i["severidade"] == "erro")
    avisos = sum(1 for i in itens if i["severidade"] == "aviso")
    rel = Relatorio({"versao": VERSAO_RELATORIO, "ok": erros == 0, "verificado_em": verificado_em,
                     "da_sha256": d.sha256 if d is not None else validacao["sha256"], "alvos": lista_alvos,
                     "resumo": {"erros": erros, "avisos": avisos}, "itens": list(itens)})
    rel.raiz, rel.entregaveis, rel.previa, rel.restrito = raiz, entregaveis, bool(previa), restrito
    rel.projeto = (d.meta.get("nome") if d is not None else None) or raiz.name
    rel.da_revisao = d.revisao if d is not None else validacao.get("revisao")
    rel.da_situacao = ("inválida" if d is None else "ALTERADA DEPOIS DA APROVAÇÃO" if d.meta.get("alterada_apos_aprovacao")
                       else "aprovada" if d.aprovada else "não aprovada")
    if gravar:
        rel.json, rel.md = da.gravar_json(arq_json, dict(rel)), da.gravar_texto(arq_md, texto_md(rel))
    return rel


# ───────────────────────────────────────────────────────────────── os textos ──
def _contagem_por_categoria(rel: dict) -> list[tuple[str, int, int, int]]:
    linhas = []
    for cat in CATEGORIAS:
        do = [i for i in rel["itens"] if i["categoria"] == cat]
        if do:
            linhas.append((cat, *(sum(1 for i in do if i["severidade"] == s) for s in SEVERIDADES)))
    return linhas


def _veredito(rel: Relatorio) -> str:
    r = rel["resumo"]
    return f"{'APROVADO' if rel['ok'] else 'REPROVADO'}: {r['erros']} erro(s), {r['avisos']} aviso(s)"


def _da_em_palavras(rel: Relatorio, completo: bool = False) -> str:
    """'revisão 2, aprovada, sha256 c913a9b9db63…' — ou o que der para dizer de uma DA que nem pôde ser lida."""
    sha = str(rel["da_sha256"] or "")
    revisao = f"revisão {rel.da_revisao}" if rel.da_revisao is not None else "revisão desconhecida"
    if not sha:
        return f"{revisao}, {rel.da_situacao}, sem identidade (o da.json não pôde ser lido)"
    return f"{revisao}, {rel.da_situacao}, sha256 " + (f"`{sha}`" if completo else f"{sha[:12]}…")


def _modo(rel: Relatorio) -> str:
    partes = ["só os alvos pedidos (carimbo, loudness e técnica restritos a eles)" if rel.restrito else "projeto inteiro"]
    if rel.previa:
        partes.append("PRÉVIA: DA não aprovada não reprova e este relatório não é o portão de publicação")
    return "; ".join(partes)


def texto_resumo(rel: Relatorio) -> str:
    """O que a CLI imprime: cabeçalho, entregáveis, contagem por categoria, erros e avisos, veredito."""
    L = [f"CONFERÊNCIA FINAL — {rel.projeto} · DA {_da_em_palavras(rel)}",
         f"Modo: {_modo(rel)}"]
    if rel.entregaveis:
        L.append(f"Entregáveis ({len(rel.entregaveis)}):")
        L += [f"  {e['rel']}  ({ROTULO_TIPO[e['tipo']]} → {', '.join(e['plataformas']) or 'sem plataforma'})" for e in rel.entregaveis]
    else:
        L.append("Entregáveis: nenhum")
    for cat, e, a, i in _contagem_por_categoria(rel):
        estado = "ok" if not e and not a else ", ".join(p for p in (f"{e} erro(s)" if e else "", f"{a} aviso(s)" if a else "") if p)
        L.append(f"  {cat:<12} {estado}" + (f"  ({i} informação(ões))" if i else ""))
    for titulo, sev, marca in (("ERROS", "erro", "✗"), ("AVISOS", "aviso", "!")):
        do = [i for i in rel["itens"] if i["severidade"] == sev]
        if do:
            L.append(f"{titulo} ({len(do)})")
            for i in do:
                L.append(f"  {marca} [{i['id']}] {i['alvo']} — {i['mensagem']}")
                if i["como_corrigir"]:
                    L.append(f"      → {i['como_corrigir']}")
    L.append(_veredito(rel) + ".")
    if rel.json:
        L.append(f"Relatório: {rel.json} · {Path(str(rel.md)).name}")
    return "\n".join(L)


def texto_md(rel: Relatorio) -> str:
    """qa/relatorio.md: o mesmo relatório para gente ler."""
    r = rel["resumo"]
    L = [f"# Conferência final — {rel.projeto}", "",
         f"**{'APROVADO' if rel['ok'] else 'REPROVADO'}** — {r['erros']} erro(s), {r['avisos']} aviso(s) · verificado em {rel['verificado_em']}",
         "",
         f"- Direção de arte: {_da_em_palavras(rel, completo=True)}",
         f"- Modo: {_modo(rel)}",
         f"- Gerado por `da conferencia` (kit {da.KIT_VERSAO}). Não edite: rode o comando de novo.",
         "", "## Entregáveis conferidos", ""]
    if rel["alvos"]:
        por_rel = {e["rel"]: e for e in rel.entregaveis}
        L += ["| arquivo | tipo | plataformas | tamanho | sha256 |", "|---|---|---|---|---|"]
        for a in rel["alvos"]:
            e = por_rel.get(a["arquivo"], {})
            L.append(f"| `{a['arquivo']}` | {ROTULO_TIPO.get(e.get('tipo'), '—')} | {', '.join(e.get('plataformas') or []) or '—'} | "
                     f"{_mb(a['bytes'])} | `{a['sha256'][:16]}…` |")
    else:
        L.append("Nenhum. Sem entregável na lista, este relatório não libera a publicação de nenhum arquivo.")
    L += ["", "## Por categoria", "", "| categoria | erros | avisos | informações |", "|---|---|---|---|"]
    L += [f"| {cat} | {e} | {a} | {i} |" for cat, e, a, i in _contagem_por_categoria(rel)]
    for titulo, sev in (("Erros", "erro"), ("Avisos", "aviso"), ("Informações", "info")):
        do = [i for i in rel["itens"] if i["severidade"] == sev]
        L += ["", f"## {titulo} ({len(do)})", ""]
        if not do:
            L.append("Nenhum." if sev != "info" else "Nenhuma.")
        for i in do:
            L.append(f"- **{i['id']}** · `{i['alvo']}` — {i['mensagem']}")
            if i["como_corrigir"]:
                L.append(f"  - Como corrigir: {i['como_corrigir']}")
    return "\n".join(L) + "\n"


# ────────────────────────────────────────────────────────────────────── CLI ──
def _cfg_conferencia(p) -> None:
    p.add_argument("alvos", nargs="*", metavar="ALVO",
                   help=f"entregáveis a conferir no lugar do padrão ({ENTREGAVEL_LONGO} e {PASTA_CORTES}/*{EXT_ENTREGAVEL}); arquivo em "
                        f"{PASTA_CORTES}/ é peça curta, fora dela é vídeo longo")
    p.add_argument("--corte", metavar="ARQ|NOME", action="append", default=[],
                   help=f"confere só este corte, como peça curta (repita a opção): caminho ou nome em {PASTA_CORTES}/, com ou sem "
                        f"{EXT_ENTREGAVEL} (ex.: --corte K01)")
    p.add_argument("--plataforma", metavar="NOME", action="append", default=[],
                   help="destino das peças curtas (repita a opção): shorts, reels, tiktok… Padrão: a plataforma que o carimbo do "
                        "corte declara; sem ela, todas as verticais de plataformas.json")
    p.add_argument("--previa", action="store_true",
                   help=f"prévia: DA ainda não aprovada vira aviso em vez de erro, e o relatório vai para {PASTA_RELATORIO}/{NOME_PREVIA}.json "
                        f"(nunca para o {NOME_RELATORIO}.json, que é o portão de publicação)")
    p.add_argument("--saida", metavar="PASTA|ARQ.json",
                   help=f"onde gravar o relatório: pasta, ou o caminho do .json (o .md vai ao lado). Padrão: {PASTA_RELATORIO}/ do projeto")
    p.add_argument("--json", action="store_true", help="imprime o relatório em JSON (o mesmo conteúdo do arquivo) em vez do resumo")


def _cmd_conferencia(args) -> int:
    rel = conferir(getattr(args, "da", None), de=getattr(args, "de", None), alvos=args.alvos, cortes=args.corte,
                   plataformas=args.plataforma, previa=args.previa, saida=args.saida)
    print(json.dumps(dict(rel), ensure_ascii=False, indent=2) if args.json else texto_resumo(rel))
    return da.SAIDA_OK if rel["ok"] else da.SAIDA_ERRO


def registrar(mod) -> None:
    mod.registrar_subcomando(
        "conferencia", "conferência final do projeto (C5): DA, lint, carimbos, loudness e limites de plataforma → qa/relatorio.json",
        _cfg_conferencia, _cmd_conferencia,
        "A conferência final, compondo o que o kit já confere: (a) `validar` sem erros e DA aprovada e não alterada depois da "
        "aprovação; (b) `lint --estrito` nas pastas de peças; (c) `conferir-carimbo --exigir-aprovada`, com broll/tratado e os "
        f"insumos das composições; (d) loudness de {ENTREGAVEL_LONGO} (som.loudness.longo) e de {PASTA_CORTES}/*{EXT_ENTREGAVEL} "
        "(som.loudness.curto); (e) duração, orientação, resolução, tamanho, fps e formato de cada entregável contra os limites "
        "de plataforma; (f) se o projeto tiver, a ficha de fatos (video-pesquisa-ia) e os créditos do registro de licenças "
        f"(video-broll). Grava {PASTA_RELATORIO}/{NOME_RELATORIO}.json (contrato: versao, ok, verificado_em, da_sha256, alvos, resumo, "
        f"itens) e {PASTA_RELATORIO}/{NOME_RELATORIO}.md. Não renderiza nada. Código 0 se ok, 1 se houver erro, 2 sem DA, 64 uso incorreto.")
