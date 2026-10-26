#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cues.py — palavras cronometradas [{a, b, w, p}] → cues de legenda (contrato da casa) + .srt e .vtt.

    python3 cues.py gerar --palavras transcricao/fala.palavras.json --video bruto/fala.mp4 --formato vertical
    python3 cues.py mostrar legendas/fala.cues.json
    python3 cues.py editar legendas/fala.cues.json --cue 3 --texto "a Ana Nakamura"
    python3 cues.py exportar legendas/fala.cues.json

O que decide o agrupamento vem da direção de arte do projeto (bloco `legenda` do da/da.json): `max_palavras`,
`max_linhas`, `estilo`, tamanho e largura — as cues são medidas com a fonte real da DA e só existem se couberem
sem encolher. O que é regra de leitura (pausa, pontuação, sentido, duração, respiro) está nas constantes abaixo,
cada uma com o motivo; as fontes estão em references/regras-de-segmentacao.md.
"""
from __future__ import annotations

import argparse
import difflib
import itertools
import math
import os
import re
import sys
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum  # noqa: E402
import numeros  # noqa: E402
from comum import Erro, br, relogio  # noqa: E402

# ───────────────────────────────────────────────────────────────── regras ──
# Legenda QUEIMADA (palavra a palavra): o ritmo é o da fala; as regras só evitam cue que pisca ou que fica órfã.
PAUSA_DURA = 0.70          # s de silêncio que sempre fecha a cue: bloco parado no meio de uma pausa parece travado
PAUSA_LEVE = 0.25          # s de silêncio que já é um bom lugar para quebrar
SEGURA = 0.30              # s que a cue fica depois da última palavra (sem invadir a próxima)
FECHA_VAO = 0.50           # vão menor que isto entre duas cues é fechado: a cue fica até a seguinte entrar
RESPIRO_QUADROS = 2        # quadros vazios entre duas cues coladas (a troca de bloco precisa ser percebida)
DUR_MIN = 0.50             # s: abaixo disso a cue é um flash; tenta fundir com a vizinha, senão avisa
MIN_PALAVRA = 0.10         # s: toda palavra fica acesa pelo menos isto (o whisper devolve palavras de duração zero)
CPS_QUEIMADA = 25          # caracteres por segundo a partir dos quais a cue queimada ganha aviso (ninguém lê; quase sempre é tempo ruim)
LIMIAR_CONFIANCA = 0.60    # p do whisper abaixo disto vira aviso para revisão humana
TETO_FALA = (0.25, 0.07)   # duração plausível de uma palavra: 0,25 s + 0,07 s por letra (o resto do intervalo é pausa)
# Legenda OCULTA (.srt/.vtt, frases inteiras): regras de legendagem profissional
OCULTA_CARACTERES = 42     # por linha
OCULTA_LINHAS = 2
OCULTA_DUR_MIN = 5 / 6     # s
OCULTA_DUR_MAX = 7.0       # s
OCULTA_CPS = 17            # caracteres por segundo (adulto)
OCULTA_SEGURA = 0.50       # s depois do fim da fala

# Pesos da segmentação (custo menor = corte melhor). Na queimada a vírgula vale mais que o custo de abrir uma cue: toda
# vírgula vira corte, desde que não sobre palavra órfã. Na oculta é o contrário: a frase só se parte quando não cabe.
# `relampago` = custo de uma cue que ficaria menos de DUR_MIN na tela: o agrupamento já nasce evitando o flash, porque
# depois não há como consertar sem passar de `legenda.max_palavras`.
PESOS_QUEIMADA = {"cue": 2.0, "virgula": 7.0, "vazio": 0.35, "curta": 1.0, "relampago": 4.0}
PESOS_OCULTA = {"cue": 6.0, "virgula": 3.0, "vazio": 0.0, "curta": 2.0}

ESTILOS = ("karaoke", "palavra", "bloco")
PONTUACOES = ("limpa", "manter", "nenhuma")
MASCARA = "***"

# Classes de palavra para o sentido da quebra. Comparação em minúsculas COM acento: "e" (conjunção) não é "é" (verbo),
# "esta" (demonstrativo) não é "está" (verbo), "nos" não é "nós".
ARTIGOS = {"o", "a", "os", "as", "um", "uma", "uns", "umas"}
PREPOSICOES = {"de", "do", "da", "dos", "das", "em", "no", "na", "nos", "nas", "por", "pelo", "pela", "pelos", "pelas", "para",
               "pra", "pro", "pros", "pras", "com", "sem", "sob", "sobre", "até", "entre", "desde", "ao", "aos", "à", "às", "num",
               "numa", "nuns", "numas", "dum", "duma", "neste", "nesta", "nesse", "nessa", "naquele", "naquela", "deste", "desta",
               "desse", "dessa", "daquele", "daquela", "nisso", "disso", "contra", "após", "perante", "durante"}
CONJUNCOES = {"e", "ou", "mas", "que", "se", "porque", "pois", "como", "quando", "nem", "porém", "enquanto", "embora", "onde"}
DETERMINANTES = {"meu", "minha", "meus", "minhas", "seu", "sua", "seus", "suas", "nosso", "nossa", "nossos", "nossas", "teu",
                 "tua", "este", "esta", "estes", "estas", "esse", "essa", "esses", "essas", "aquele", "aquela", "aqueles",
                 "aquelas", "cada", "todo", "toda", "todos", "todas", "qual", "quais", "algum", "alguma", "alguns", "algumas",
                 "nenhum", "nenhuma", "outro", "outra", "outros", "outras"}
ADVERBIOS_PRESOS = {"não", "muito", "muita", "muitos", "muitas", "mais", "menos", "tão", "bem", "já", "só", "também"}
PRONOMES_SUJEITO = {"eu", "tu", "você", "ele", "ela", "nós", "vocês", "eles", "elas", "gente"}
PARTICULAS_DE_NOME = {"de", "da", "do", "dos", "das", "e"}
UNIDADES = {"%", "por", "anos", "ano", "meses", "mês", "dias", "dia", "horas", "hora", "minutos", "minuto", "segundos",
            "segundo", "reais", "real", "dólares", "dólar", "euros", "euro", "mil", "milhão", "milhões", "bilhão", "bilhões",
            "trilhão", "trilhões", "vezes", "vez", "graus", "quilos", "kg", "km", "metros", "tokens", "parâmetros",
            "pontos", "pessoas", "centavos", "gb", "mb", "tb", "gigas", "watts", "bits"}
MOEDAS = {"r$", "us$", "$", "€", "£"}
AUXILIARES = {"vai", "vou", "vamos", "vão", "ia", "iam", "pode", "podem", "posso", "podia", "deve", "devem", "devia", "quer",
              "querem", "quero", "tem", "têm", "tinha", "ter", "está", "estão", "estava", "estou", "foi", "são", "ser", "sido",
              "havia", "vem", "precisa", "consegue", "costuma"}
VERBOS_DE_LIGACAO = {"é", "são", "era", "eram", "foi", "foram", "está", "estão", "estava", "ser", "estar", "tem", "têm", "há", "fica", "parece"}
LIGA_A_DIREITA = ARTIGOS | PREPOSICOES | CONJUNCOES | DETERMINANTES | ADVERBIOS_PRESOS
_RE_FORMA_NOMINAL = re.compile(r"(?:[aeio]r|[aei]ndo|[ai]d[oa]s?|sto|ito)$")     # infinitivo, gerúndio, particípio

_ABRE = "\"'“‘«([{¿¡-–—"
_FECHA = ".,;:!?…\"'”’»)]}-–—"
_RE_NUMERO = re.compile(r"^[+-]?\d[\d.,]*(?:[%ºª°]|[kKmM])?$")


# ─────────────────────────────────────────────────────────────── palavras ──
@dataclass
class Pal:
    """Uma palavra cronometrada: `nucleo` é o texto sem a pontuação das pontas; `pre`/`pos` guardam a pontuação."""
    a: float
    b: float
    nucleo: str
    pre: str = ""
    pos: str = ""
    p: float = 1.0
    orig: str | None = None
    destaque: bool = False
    censurada: bool = False
    linha: int = 0
    fala_fim: float | None = None      # fim da fala herdado do trecho ORIGINAL quando o glossário trocou o texto (ver _fundir)
    lote: int = 0                      # de qual troca do glossário a palavra veio (0 = nenhuma); não vai para o arquivo

    @property
    def chave(self) -> str:
        """Minúsculas, com acento: é assim que as classes de palavra são comparadas."""
        return self.nucleo.casefold()

    @property
    def txt(self) -> str:
        """Texto da legenda oculta: com a pontuação original."""
        return f"{self.pre}{self.nucleo}{self.pos}"

    def w(self, pontuacao: str = "limpa") -> str:
        """Texto queimado. 'limpa' tira ponto e vírgula e deixa só ? e ! (o que muda a entonação); 'manter' deixa
        tudo; 'nenhuma' tira tudo."""
        if pontuacao == "manter":
            return self.txt
        if pontuacao == "limpa":
            for sinal in "?!":
                if sinal in self.pos:
                    return self.nucleo + sinal
        return self.nucleo

    @property
    def fim_de_frase(self) -> bool:
        return any(c in self.pos for c in ".!?…")

    @property
    def pontuacao_fraca(self) -> bool:
        return any(c in self.pos for c in ",;:)]»”–—") and not self.fim_de_frase

    @property
    def maiuscula(self) -> bool:
        return self.nucleo[:1].isupper()

    @property
    def numero(self) -> bool:
        return bool(_RE_NUMERO.match(self.nucleo)) or numeros.e_numeral(self.nucleo)

    @property
    def fim_da_fala(self) -> float:
        """Fim estimado da fala: o whisper cola o silêncio seguinte na duração da palavra. O teto (0,25 s + 0,07 s por
        letra) vale para o texto que foi FALADO: palavra que o glossário trocou ("cento e cinquenta mil" → "150.000",
        um nome → "***") guarda em `fala_fim` o fim de fala do trecho original — senão o texto curto na tela faria a
        cue sair no meio da fala e inventaria uma pausa que não existe."""
        if self.fala_fim is not None:
            return min(self.b, max(self.a, self.fala_fim))
        return min(self.b, self.a + TETO_FALA[0] + TETO_FALA[1] * max(1, len(self.nucleo)))


def partir_token(s: str) -> tuple[str, str, str]:
    """'“Brasília,”' → ('“', 'Brasília', ',”'). Token só de pontuação devolve núcleo vazio."""
    s = re.sub(r"\s+", " ", str(s)).strip()
    i, j = 0, len(s)
    while i < j and s[i] in _ABRE:
        i += 1
    while j > i and s[j - 1] in _FECHA:
        j -= 1
    if i < j and s[i:j] in ("%",):
        return "", s[i:j], s[j:]
    nucleo = s[i:j]
    # ponto final de sigla continua na sigla: "S.A." / "B.O."
    if "." in nucleo and j < len(s) and s[j] == "." and re.fullmatch(r"(?:[A-Za-zÀ-ÿ]\.)+[A-Za-zÀ-ÿ]", nucleo):
        nucleo, j = nucleo + ".", j + 1
    return s[:i], nucleo, s[j:]


def ler_palavras(fonte) -> list[dict]:
    """Lê e confere o JSON da transcrição: lista de {a, b, w, p}. Erros dizem qual item e o que falta."""
    dados = fonte if isinstance(fonte, list) else comum.ler_json(fonte, "arquivo de palavras")
    if isinstance(dados, dict) and isinstance(dados.get("palavras"), list):
        dados = dados["palavras"]
    if not isinstance(dados, list) or not dados:
        raise Erro("o arquivo de palavras precisa ser uma lista não vazia de {\"a\", \"b\", \"w\", \"p\"}.",
                   "Gere com a skill video-transcricao (passada palavra a palavra: -ml 1 -sow -ojf).")
    saida = []
    for n, item in enumerate(dados):
        if not isinstance(item, dict) or "w" not in item or "a" not in item:
            raise Erro(f"palavra {n} fora do formato: esperava {{\"a\": início_s, \"b\": fim_s, \"w\": \"texto\", \"p\": confiança}}, veio {str(item)[:80]}.",
                       "Tempos em segundos; `w` é o texto da palavra.")
        try:
            a = float(item["a"])
            b = float(item.get("b", a))
            p = float(item.get("p", 1.0))
        except (TypeError, ValueError):
            raise Erro(f"palavra {n} ({item.get('w')!r}): `a`, `b` e `p` precisam ser números (segundos e confiança de 0 a 1).")
        if not (math.isfinite(a) and math.isfinite(b)) or a < 0:
            raise Erro(f"palavra {n} ({item.get('w')!r}): tempo inválido (a={item['a']!r}, b={item.get('b')!r}).")
        saida.append({"a": a, "b": max(a, b), "w": str(item["w"]), "p": p})
    return saida


def preparar(dados: list[dict], inicio: float | None = None, fim: float | None = None,
             min_palavra: float = MIN_PALAVRA) -> tuple[list[Pal], dict]:
    """Recorta a janela (rebaseando os tempos para 0 = início), separa pontuação, junta tokens soltos e conserta
    tempos impossíveis (duração zero, ordem trocada). Devolve (palavras, notas)."""
    t0 = float(inicio or 0.0)
    t1 = float(fim) if fim is not None else math.inf
    if t1 <= t0:
        raise Erro(f"janela vazia: --fim ({br(t1)} s) precisa ser maior que --inicio ({br(t0)} s).")
    notas = {"lidas": len(dados), "fora_da_janela": 0, "tempos_reparados": 0, "tokens_fundidos": 0}
    pal: list[Pal] = []
    for item in sorted(dados, key=lambda x: (x["a"], x["b"])):
        w = item["w"].strip()
        if not w or w.startswith("["):                 # segmentos de controle do whisper ([_BEG_], [Música])
            continue
        meio = (item["a"] + item["b"]) / 2
        if not (t0 <= meio < t1):                      # a palavra pertence à janela onde está o seu meio
            notas["fora_da_janela"] += 1
            continue
        pre, nucleo, pos = partir_token(w)
        a, b = max(0.0, item["a"] - t0), min(item["b"], t1) - t0
        if not nucleo:                                 # token só de pontuação: gruda na palavra anterior
            if pal:
                pal[-1].pos += pre + pos
                pal[-1].b = max(pal[-1].b, b)
                notas["tokens_fundidos"] += 1
            continue
        if pre.startswith("-") and pal and not pal[-1].pos and len(pre) == 1 and a - pal[-1].b < 0.15:
            pal[-1].nucleo += "-" + nucleo             # "disse" + "-me" → "disse-me"
            pal[-1].pos, pal[-1].b = pos, max(pal[-1].b, b)
            pal[-1].p = min(pal[-1].p, item["p"])
            notas["tokens_fundidos"] += 1
            continue
        pal.append(Pal(a=a, b=max(a, b), nucleo=nucleo, pre=pre, pos=pos, p=item["p"]))
    if not pal:
        raise Erro("nenhuma palavra da transcrição cai no trecho pedido.",
                   "Confira --inicio/--fim (são tempos do vídeo de origem, em segundos) e se o arquivo de palavras é deste vídeo.")
    notas["tempos_reparados"] = normalizar_tempos(pal, min_palavra)
    return pal, notas


def _duracao_plausivel(p: Pal) -> float:
    """Quanto uma palavra leva para ser dita, por alto: 0,05 s + 0,05 s por letra, entre MIN_PALAVRA e 0,40 s."""
    return min(0.40, max(MIN_PALAVRA, 0.05 + 0.05 * len(p.nucleo)))


def normalizar_tempos(pal: list[Pal], min_palavra: float = MIN_PALAVRA, piso: float = 0.0) -> int:
    """Garante início crescente, pelo menos `min_palavra` de tela para cada palavra e b dentro do próprio intervalo.

    O whisper devolve palavras de duração zero coladas no início da seguinte ("E", "eu", "Você"). Cada sequência
    dessas palavras APERTADAS é puxada para trás — elas foram ditas antes de a seguinte começar —, ocupando o silêncio
    anterior ou, se não houver, até 60 % da palavra anterior, com duração proporcional ao tamanho. As seguintes não
    são empurradas (a sincronia do resto não muda). `piso` = tempo antes do qual nenhuma palavra pode começar (o início
    da cue, quando se normaliza uma cue editada). Devolve quantas palavras andaram mais de 20 ms."""
    n = len(pal)
    antes = [p.a for p in pal]
    for i in range(1, n):
        pal[i].a = max(pal[i].a, pal[i - 1].a)
    fim = [pal[i + 1].a if i + 1 < n else max(pal[i].b, pal[i].a + min_palavra) for i in range(n)]
    apertada = [fim[i] - pal[i].a < min_palavra - 1e-9 for i in range(n)]
    i = 0
    while i < n:
        if not apertada[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and apertada[j + 1]:
            j += 1
        quer = [_duracao_plausivel(p) for p in pal[i:j + 1]]
        if i == 0:
            t_ini = max(piso, pal[0].a - sum(quer))
        elif pal[i - 1].b < pal[i].a - 1e-3:               # há silêncio antes: é dele que sai o tempo
            t_ini = max(pal[i - 1].b, pal[i - 1].a + min_palavra)
        else:                                              # coladas: no máximo 60 % da palavra anterior
            t_ini = pal[i - 1].a + max(min_palavra, 0.4 * (pal[i].a - pal[i - 1].a))
        t_ini = min(t_ini, pal[i].a)
        k = min(1.0, max(0.0, fim[j] - t_ini) / sum(quer))
        t = fim[j]
        for m in range(j, i - 1, -1):
            t -= quer[m - i] * k
            pal[m].a = min(pal[m].a, t)
        i = j + 1
    pal[0].a = max(piso, pal[0].a)
    for i in range(1, n):
        pal[i].a = max(pal[i].a, pal[i - 1].a + min_palavra)
    for i in range(n):
        teto = pal[i + 1].a if i + 1 < n else math.inf
        pal[i].b = min(max(pal[i].b, pal[i].a + min(min_palavra, teto - pal[i].a)), teto)
        pal[i].a, pal[i].b = round(pal[i].a, 3), round(pal[i].b, 3)
    return sum(1 for a, p in zip(antes, pal) if abs(a - p.a) > 0.02)


# ────────────────────────────────────────────────────────────── glossário ──
CHAVES_GLOSSARIO = {"trocas", "censura", "numeros_em_algarismo", "destaques", "mascara"}


def ler_glossario(caminho) -> dict:
    """legendas/glossario.json → {"trocas": {errado: certo}, "censura": [...], "numeros_em_algarismo": bool,
    "destaques": [...], "mascara": "***"}. Chave desconhecida é erro (um "troca" digitado errado passaria em branco)."""
    g = comum.ler_json(caminho, "glossário")
    if not isinstance(g, dict):
        raise Erro(f"o glossário {Path(str(caminho)).name} precisa ser um objeto JSON com trocas, censura, numeros_em_algarismo e destaques.")
    for k in g:
        if k not in CHAVES_GLOSSARIO and not str(k).startswith("_"):
            perto = difflib.get_close_matches(str(k), sorted(CHAVES_GLOSSARIO), n=1)
            raise Erro(f"glossário: chave desconhecida {k!r}." + (f" Quis dizer {perto[0]!r}?" if perto else ""),
                       f"Chaves aceitas: {', '.join(sorted(CHAVES_GLOSSARIO))} (anotações livres começam por _).")
    trocas = g.get("trocas") or {}
    if not isinstance(trocas, dict) or any(not isinstance(k, str) or not isinstance(v, str) or not k.strip() for k, v in trocas.items()):
        raise Erro("glossário: `trocas` precisa ser um objeto {\"como saiu\": \"como deve ficar\"} com textos.")
    for campo in ("censura", "destaques"):
        v = g.get(campo) or []
        if not isinstance(v, list) or any(not isinstance(x, str) or not x.strip() for x in v):
            raise Erro(f"glossário: `{campo}` precisa ser uma lista de textos.")
    if not isinstance(g.get("numeros_em_algarismo", False), bool):
        raise Erro("glossário: `numeros_em_algarismo` precisa ser true ou false.")
    mascara = g.get("mascara", MASCARA)
    if not isinstance(mascara, str) or not mascara.strip() or " " in mascara.strip() or partir_token(mascara.strip()) != ("", mascara.strip(), ""):
        raise Erro("glossário: `mascara` precisa ser um texto sem espaços que não comece nem termine em pontuação (ex.: \"***\" ou \"###\").",
                   "Colchetes, aspas, reticências e hífen nas pontas seriam lidos como pontuação da frase.")
    return {"trocas": dict(trocas), "censura": list(g.get("censura") or []), "destaques": list(g.get("destaques") or []),
            "numeros_em_algarismo": bool(g.get("numeros_em_algarismo", False)), "mascara": mascara.strip()}


def _achar(pal: list[Pal], termo: list[str], forma) -> list[int]:
    """Índices onde a sequência `termo` (já normalizada por `forma`) começa em `pal`, sem atravessar fim de frase."""
    n, k, achados, i = len(pal), len(termo), [], 0
    while i + k <= n:
        if all(forma(pal[i + j].nucleo) == termo[j] for j in range(k)) and not any(pal[i + j].fim_de_frase for j in range(k - 1)):
            achados.append(i)
            i += k
        else:
            i += 1
    return achados


def _fundir(pal: list[Pal], i0: int, i1: int, novas: list[str], literal: bool = False, conferido: bool = False, **campos) -> list[Pal]:
    """Troca pal[i0:i1] por `novas` palavras repartindo o intervalo de tempo pelo tamanho de cada uma: a sincronia do
    trecho se mantém nas pontas (início da primeira antiga, fim da última) e o FIM DA FALA continua sendo o do trecho
    original (`fala_fim`), não o do texto novo. `literal` = o texto novo entra como está (máscara de censura), sem
    separar pontuação. `conferido` = o texto novo foi escrito por gente (troca do glossário, edição): confiança 1,0."""
    velhas = pal[i0:i1]
    a, b = velhas[0].a, velhas[-1].b
    if len(novas) == len(velhas):
        tempos = [(v.a, v.b) for v in velhas]
        falas = [v.fim_da_fala for v in velhas]
    else:
        pesos = [max(1, len(x)) for x in novas]
        total, acum, tempos = sum(pesos), 0, []
        for w in pesos:
            tempos.append((a + (b - a) * acum / total, a + (b - a) * (acum + w) / total))
            acum += w
        # dentro do trecho a fala é contínua (cada palavra nova vai até a seguinte); a última acaba onde a fala acabava
        falas = [tb for _, tb in tempos[:-1]] + [velhas[-1].fim_da_fala]
    orig = " ".join(v.orig or v.txt for v in velhas)
    saida = []
    for k, (texto, (ta, tb)) in enumerate(zip(novas, tempos)):
        pre, nucleo, pos = ("", texto, "") if literal else partir_token(texto)
        saida.append(Pal(a=round(ta, 3), b=round(tb, 3), nucleo=nucleo or texto,
                         pre=(velhas[0].pre if k == 0 else "") + pre,
                         pos=pos + (velhas[-1].pos if k == len(novas) - 1 else ""),
                         p=1.0 if conferido else min(v.p for v in velhas), orig=orig if k == 0 else None,
                         destaque=any(v.destaque for v in velhas),
                         fala_fim=round(min(tb, max(ta, falas[k])), 3), **campos))
    return saida


def aplicar_glossario(pal: list[Pal], g: dict | None) -> tuple[list[Pal], dict]:
    """Aplica trocas → números → censura → destaques. Devolve (palavras, relatório com contagens e o que não ocorreu)."""
    rel = {"trocas": 0, "numeros": 0, "censuradas": 0, "destaques": 0, "sem_ocorrencia": []}
    if not g:
        return pal, rel
    pal = list(pal)
    lote = 0
    # 1. trocas: caixa não importa, acento importa ("da" não é "dá"); as chaves mais longas primeiro
    for errado, certo in sorted(g["trocas"].items(), key=lambda kv: -len(kv[0].split())):
        termo = [partir_token(x)[1].casefold() for x in errado.split()]
        termo = [t for t in termo if t]
        novas = certo.split()
        if not termo:
            continue
        achados = _achar(pal, termo, lambda s: s.casefold())
        if not achados:
            rel["sem_ocorrencia"].append(f"troca «{errado}»")
        for i in reversed(achados):
            if not novas:                              # troca por vazio = tirar a palavra (o tempo vai para a anterior)
                if i > 0:                              # … que fica na tela enquanto a palavra tirada é dita
                    pal[i - 1].fala_fim = pal[i + len(termo) - 1].fim_da_fala
                    pal[i - 1].b = pal[i + len(termo) - 1].b
                    pal[i - 1].pos += pal[i + len(termo) - 1].pos
                del pal[i:i + len(termo)]
            else:
                lote += 1                              # texto escrito por gente: sem aviso de confiança palavra a palavra
                bloco = _fundir(pal, i, i + len(termo), novas, conferido=True, lote=lote)
                if pal[i].maiuscula and bloco[0].nucleo[:1].islower() and (i == 0 or pal[i - 1].fim_de_frase):
                    bloco[0].nucleo = bloco[0].nucleo[:1].upper() + bloco[0].nucleo[1:]
                if [x.nucleo for x in bloco] == [x.nucleo for x in pal[i:i + len(termo)]]:
                    continue
                pal[i:i + len(termo)] = bloco
            rel["trocas"] += 1
    # 2. números por extenso → algarismos (numeros.py decide o que vale trocar)
    if g["numeros_em_algarismo"] and pal:
        preso = [not (p.pos or (q.a - p.fim_da_fala) >= PAUSA_LEVE) for p, q in zip(pal, pal[1:])] + [False]
        for i0, i1, texto in reversed(numeros.trechos([p.nucleo for p in pal], preso)):
            pal[i0:i1] = _fundir(pal, i0, i1, [texto])
            rel["numeros"] += 1
    # 3. censura: o termo some do arquivo (não fica nem em `orig`)
    for termo_txt in sorted(g["censura"], key=lambda s: -len(s.split())):
        termo = [comum.chave(partir_token(x)[1]) for x in termo_txt.split()]
        termo = [t for t in termo if t]
        if not termo:
            continue
        achados = _achar(pal, termo, comum.chave)
        if not achados:
            rel["sem_ocorrencia"].append("um termo de censura")      # sem repetir o termo no relatório
        for i in reversed(achados):
            lotes = {v.lote for v in pal[i:i + len(termo)] if v.lote}
            bloco = _fundir(pal, i, i + len(termo), [g["mascara"]], literal=True, censurada=True)
            bloco[0].orig, bloco[0].pre = None, ""
            pal[i:i + len(termo)] = bloco
            for p in pal:                              # a troca que trouxe o termo guardava a transcrição original na
                if p.lote in lotes:                    # palavra vizinha ("Ana" ← "Anna Nakamora"): some junto
                    p.orig = None
            rel["censuradas"] += 1
    # 4. destaques
    for termo_txt in g["destaques"]:
        termo = [comum.chave(partir_token(x)[1]) for x in termo_txt.split()]
        termo = [t for t in termo if t]
        achados = _achar(pal, termo, comum.chave) if termo else []
        if termo and not achados:
            rel["sem_ocorrencia"].append(f"destaque «{termo_txt}»")
        for i in achados:
            for p in pal[i:i + len(termo)]:
                p.destaque = True
            rel["destaques"] += 1
    return pal, rel


# ─────────────────────────────────────────────────────────────── medidores ──
class MedidorDeCaracteres:
    """Largura em caracteres (legenda oculta): `util` caracteres por linha, vão de um espaço."""

    def __init__(self, caracteres: int = OCULTA_CARACTERES, max_linhas: int = OCULTA_LINHAS):
        self.util, self.vao, self.max_linhas, self.uma_por_vez = float(caracteres), 1.0, int(max_linhas), False

    def largura(self, texto_da_palavra: str) -> float:
        return float(len(texto_da_palavra))


class MedidorDaDA:
    """Largura em px com a fonte, o tamanho, o contorno e a caixa do bloco `legenda` da DA, dentro da zona segura da
    plataforma — a mesma conta que texto.compor_legenda faz antes de encolher. Cue que não cabe aqui encolheria na tela."""

    def __init__(self, d, largura: int, altura: int, plataforma: str | None = None):
        _, texto, _, _ = comum.kit()
        self._texto = texto
        leg = d["legenda"]
        self.est = texto.Estilo.legenda(d, largura, altura)
        ref = texto.caixa_da_legenda(d, largura, altura, plataforma)
        esp = int(round(self.est.contorno[1])) if self.est.contorno else 0
        rx = self.est.fundo["respiro"][0] if self.est.fundo else 0.0
        self.util = float(ref["largura_max"]) - 2 * max(esp, rx) * (float(self.est.escala_x) or 1.0)
        self.vao = texto.vao_entre_palavras(self.est)
        self.max_linhas = int(leg["max_linhas"])
        self.uma_por_vez = leg["estilo"] == "palavra"
        self.zona = ref["zona"]
        self._cache: dict = {}

    def largura(self, texto_da_palavra: str) -> float:
        if texto_da_palavra not in self._cache:
            self._cache[texto_da_palavra] = self._texto.largura_texto(texto_da_palavra, self.est)
        return self._cache[texto_da_palavra]


def _largura_linha(larguras: list[float], vao: float) -> float:
    return sum(larguras) + vao * max(0, len(larguras) - 1)


def cabe(larguras: list[float], med) -> bool:
    """As palavras cabem em até med.max_linhas linhas de med.util? (estilo `palavra`: cada uma cabe sozinha)."""
    if any(w > med.util + 0.5 for w in larguras):
        return False
    if med.uma_por_vez:
        return True
    linhas, atual = 1, larguras[0]
    for w in larguras[1:]:
        if atual + med.vao + w <= med.util + 0.5:
            atual += med.vao + w
        else:
            linhas, atual = linhas + 1, w
    return linhas <= med.max_linhas


# ──────────────────────────────────────────────────────────── segmentação ──
def pausa_depois(pal: list[Pal], i: int) -> float:
    return max(0.0, pal[i + 1].a - pal[i].fim_da_fala) if i + 1 < len(pal) else math.inf


def custo_quebra(pal: list[Pal], i: int, linha: bool = False, virgula: float = 5.0) -> float:
    """Quanto custa quebrar ENTRE a palavra i e a i+1 (negativo = bom lugar). Vale para fim de cue e, com
    `linha=True`, para fim de linha dentro da cue (onde não há pausa para ajudar)."""
    p, q = pal[i], pal[i + 1]
    c = 0.0
    if p.fim_de_frase:
        return -12.0
    if p.pontuacao_fraca:
        c -= virgula
    if not linha:
        pausa = pausa_depois(pal, i)
        c -= 3.0 if pausa >= PAUSA_LEVE else 1.0 if pausa >= PAUSA_LEVE / 2 else 0.0
    kp, kq = p.chave, q.chave
    if kq in CONJUNCOES or kq in PREPOSICOES:
        c -= 3.0 if linha else 1.5                     # quebra-se ANTES de conjunção e preposição
    if not p.pontuacao_fraca:
        if kp in LIGA_A_DIREITA:
            c += 8.0                                   # artigo, preposição, conjunção, possessivo, "não": presos ao que vem
        elif kp in PRONOMES_SUJEITO:
            c += 3.0                                   # sujeito + verbo
        elif kp in AUXILIARES and _RE_FORMA_NOMINAL.search(kq):
            c += 6.0                                   # locução verbal: "vai | ter", "está | fazendo"
        elif kp in VERBOS_DE_LIGACAO:
            c += 3.0                                   # verbo de ligação + o que ele liga: "é | só um cidadão"
        depois = pal[i + 2] if i + 2 < len(pal) else None
        if p.numero and (kq in UNIDADES or q.nucleo.startswith("%")):
            c += 12.0                                  # número + unidade
        elif p.numero and q.numero:
            c += 12.0                                  # numeral composto: "mil | novecentos", "dois | mil"
        elif p.numero and kq == "e" and depois is not None and depois.numero:
            c += 13.5                                  # "vinte | e três" (cobre o desconto de quebrar antes de conjunção)
        elif p.numero and kq not in CONJUNCOES and not (kp == "cento" and i > 0 and pal[i - 1].chave == "por"):
            c += 5.0                                   # numeral + o que ele conta ("três | modelos"; "1999 | e ninguém viu" é bom corte)
        if kp == "e" and q.numero and i > 0 and pal[i - 1].numero:
            c += 10.0                                  # "vinte e | três": além dos 8 de toda conjunção pendurada. É o PIOR corte do numeral e
                                                       # tem de perder com folga — com 6, a linha de uma palavra só (+4) fazia "cento e / cinquenta mil"
        if kp in MOEDAS and q.numero:
            c += 12.0
        if kp == "por" and kq == "cento":
            c += 6.0                                   # "por | cento": a unidade inteira fica junta (além dos 8 da preposição)
        inicio_de_frase = i == 0 or pal[i - 1].fim_de_frase
        if p.maiuscula and q.maiuscula and not p.numero:
            c += 3.0 if inicio_de_frase else 12.0      # nome + sobrenome ("O Pedro": a inicial é só ortografia)
        elif p.maiuscula and kq in PARTICULAS_DE_NOME and depois is not None and depois.maiuscula:
            # nome com partícula é um bloco só: "Lula | da Silva", "São José | dos Campos". Com "e" podem ser dois nomes
            # ("Lula | e Dilma") e, no começo da frase, a maiúscula pode ser só ortografia ("Antes | da Copa").
            c += 5.0 if (kq == "e" or inicio_de_frase) else 13.5
        if kp in PARTICULAS_DE_NOME and kp != "e" and q.maiuscula and i > 0 and pal[i - 1].maiuscula:
            c += 10.0                                  # "Lula da | Silva": além dos 8 de toda preposição pendurada (o pior corte do nome, com a mesma folga)
        elif kp in LIGA_A_DIREITA and q.maiuscula and not q.numero:
            c += 5.0                                   # "a | Maria", "em | São José": pendurar a palavra de ligação não é saída para
                                                       # poupar o nome — se ele não cabe inteiro, o corte é dentro dele, antes da partícula
    return c


def segmentar(pal: list[Pal], med, max_palavras: int, texto_de=lambda p: p.w(), pesos: dict | None = None,
              dur_max: float | None = None, dur_min: float = DUR_MIN) -> list[tuple[int, int]]:
    """Agrupa as palavras em cues [(i0, i1), …]. Fim de frase e pausa longa sempre fecham; dentro de cada trecho,
    programação dinâmica escolhe os cortes de menor custo entre os que CABEM (med) com até `max_palavras`."""
    n = len(pal)
    pesos = pesos or PESOS_QUEIMADA
    larg = [med.largura(texto_de(p)) for p in pal]
    cues, i0 = [], 0
    for i in range(n):
        duro = i == n - 1 or pal[i].fim_de_frase or pausa_depois(pal, i) >= PAUSA_DURA
        if not duro:
            continue
        s, e = i0, i + 1
        N = e - s
        melhor = {s: (0.0, None)}
        for j in range(s + 1, e + 1):
            for k in range(1, min(max_palavras, j - s) + 1):
                a = j - k
                if a not in melhor:
                    continue
                if k > 1 and not cabe(larg[a:j], med):
                    continue
                if dur_max is not None and k > 1 and pal[j - 1].fim_da_fala - pal[a].a > dur_max:
                    continue
                custo = melhor[a][0] + pesos["cue"] + pesos["vazio"] * (max_palavras - k)
                if pesos.get("relampago"):             # cue que ficaria menos de `dur_min` na tela (fala rápida, grupo pequeno)
                    sai = min(pal[j].a if j < n else math.inf, pal[j - 1].fim_da_fala + SEGURA)
                    if sai - pal[a].a < dur_min - 1e-6:
                        custo += pesos["relampago"]
                if k == 1 and N > 1:
                    custo += 6.0                       # palavra órfã no meio da frase
                elif k == 2 and N > 2 and max_palavras >= 4:
                    custo += pesos["curta"]
                if j < e:
                    custo += custo_quebra(pal, j - 1, virgula=pesos["virgula"])
                if j not in melhor or custo < melhor[j][0]:
                    melhor[j] = (custo, a)
        j, trecho = e, []
        while j != s:
            a = melhor[j][1]
            trecho.append((a, j))
            j = a
        cues += reversed(trecho)
        i0 = e
    return cues


def melhor_quebra(pal: list[Pal], larguras: list[float], med) -> list[int] | None:
    """Reparte UMA cue em linhas: o menor número de linhas que cabe e, entre as partições possíveis, a de menor custo
    (sentido primeiro, equilíbrio depois). Devolve as contagens por linha ([2, 3]) ou None se não cabe em med.max_linhas."""
    n = len(larguras)
    if med.uma_por_vez or n == 1:
        return [n] if all(w <= med.util + 0.5 for w in larguras) else None
    for nl in range(1, min(med.max_linhas, n) + 1):
        melhor, escolhida = math.inf, None
        for cortes in itertools.combinations(range(1, n), nl - 1):
            limites = [0, *cortes, n]
            ws = [_largura_linha(larguras[a:b], med.vao) for a, b in zip(limites, limites[1:])]
            if max(ws) > med.util + 0.5:
                continue
            custo = sum(custo_quebra(pal, c - 1, linha=True) for c in cortes)
            custo += 4.0 * (max(ws) - min(ws)) / med.util                                                  # linhas de largura parecida
            custo += sum(4.0 for a, b in zip(limites, limites[1:]) if b - a == 1 and n > 2)                # linha de uma palavra só
            if custo < melhor:
                melhor, escolhida = custo, [b - a for a, b in zip(limites, limites[1:])]
        if escolhida:
            return escolhida
    return None


# ───────────────────────────────────────────────────────────────── tempos ──
def temporizar(pal: list[Pal], grupos: list[tuple[int, int]], duracao: float, respiro: float, segura: float = SEGURA,
               dur_min: float = DUR_MIN, fecha_vao: float = FECHA_VAO) -> list[dict]:
    """t0/t1 de cada cue: entra na primeira palavra; sai `segura` depois do fim da fala ou, se a próxima cue vem em
    menos de `fecha_vao`, fica até `respiro` antes dela. Nunca sobrepõe, nunca passa do fim do vídeo."""
    saida = []
    for k, (i0, i1) in enumerate(grupos):
        t0 = pal[i0].a
        prox = pal[grupos[k + 1][0]].a if k + 1 < len(grupos) else math.inf
        # o respiro nunca come a última palavra: ela fica acesa pelo menos MIN_PALAVRA
        teto = min(max(prox - respiro, min(prox, pal[i1 - 1].a + MIN_PALAVRA)) if prox < math.inf else math.inf, duracao)
        fim_fala = pal[i1 - 1].fim_da_fala
        t1 = teto if (prox - fim_fala) < fecha_vao else fim_fala + segura
        t1 = min(max(t1, t0 + dur_min), teto)
        if t1 <= t0:                                   # sem espaço nenhum (palavras coladas no fim do vídeo)
            t1 = min(max(t0 + MIN_PALAVRA, t1), max(duracao, t0 + MIN_PALAVRA))
        saida.append({"t0": round(t0, 3), "t1": round(t1, 3), "i0": i0, "i1": i1})
    return saida


def fundir_curtas(pal: list[Pal], cues: list[dict], med, max_palavras: int, dur_min: float, texto_de) -> int:
    """Cue que dura menos que `dur_min` é fundida com a vizinha da MESMA frase quando o conjunto cabe na largura e em
    `legenda.max_palavras` (o teto é o da DA; o que não puder fundir fica com o aviso `duracao`). Devolve quantas fusões fez."""
    fusoes, k = 0, 0
    while k < len(cues):
        c = cues[k]
        if c["t1"] - c["t0"] >= dur_min - 1e-6 or len(cues) == 1:
            k += 1
            continue
        candidatas = []
        if k > 0 and not pal[cues[k - 1]["i1"] - 1].fim_de_frase and pausa_depois(pal, cues[k - 1]["i1"] - 1) < PAUSA_DURA:
            candidatas.append(k - 1)
        if k + 1 < len(cues) and not pal[c["i1"] - 1].fim_de_frase and pausa_depois(pal, c["i1"] - 1) < PAUSA_DURA:
            candidatas.append(k)
        feita = False
        for j in candidatas:                           # j = índice da cue da esquerda no par (j, j+1)
            e, d = cues[j], cues[j + 1]
            if d["i1"] - e["i0"] > max_palavras:           # o teto é o da DA: sem exceção para "caber só mais uma"
                continue
            if not cabe([med.largura(texto_de(p)) for p in pal[e["i0"]:d["i1"]]], med):
                continue
            cues[j:j + 2] = [{"t0": e["t0"], "t1": d["t1"], "i0": e["i0"], "i1": d["i1"]}]
            fusoes, feita, k = fusoes + 1, True, max(0, j)
            break
        if not feita:
            k += 1
    return fusoes


# ───────────────────────────────────────────────────────── legenda oculta ──
def frases(pal: list[Pal], duracao: float, respiro: float) -> list[dict]:
    """Legenda oculta: frases inteiras, até 2 linhas de 42 caracteres, de 5/6 s a 7 s, com a pontuação original."""
    med = MedidorDeCaracteres()
    grupos = segmentar(pal, med, max_palavras=24, texto_de=lambda p: p.txt, pesos=PESOS_OCULTA,
                       dur_max=OCULTA_DUR_MAX - OCULTA_SEGURA)
    saida = []
    for k, (i0, i1) in enumerate(grupos):
        trecho = pal[i0:i1]
        larguras = [med.largura(p.txt) for p in trecho]
        partes = melhor_quebra(trecho, larguras, med) or [len(trecho)]
        linhas, i = [], 0
        for q in partes:
            linhas.append(" ".join(p.txt for p in trecho[i:i + q]))
            i += q
        t0 = trecho[0].a
        prox = pal[grupos[k + 1][0]].a if k + 1 < len(grupos) else math.inf
        teto = min(prox - respiro if prox < math.inf else math.inf, duracao)
        t1 = min(max(trecho[-1].fim_da_fala + OCULTA_SEGURA, t0 + OCULTA_DUR_MIN), teto, t0 + OCULTA_DUR_MAX)
        if t1 <= t0:
            t1 = t0 + MIN_PALAVRA
        saida.append({"t0": round(t0, 3), "t1": round(t1, 3), "texto": "\n".join(linhas)})
    return saida


def _ms(t: float) -> int:
    return int(round(max(0.0, t) * 1000))


def _sem_sobreposicao(itens: list[dict]) -> list[tuple[int, int, str]]:
    """(t0_ms, t1_ms, texto) com fim > início e sem sobrepor o seguinte, já no arredondamento de milissegundo."""
    saida = []
    for it in itens:
        a, b = _ms(it["t0"]), _ms(it["t1"])
        if saida and a < saida[-1][1]:
            saida[-1] = (saida[-1][0], max(saida[-1][0] + 1, a), saida[-1][2])
            a = max(a, saida[-1][1])
        saida.append((a, max(a + 1, b), it["texto"]))
    return saida


def texto_srt(itens: list[dict]) -> str:
    """SubRip: número, HH:MM:SS,mmm --> HH:MM:SS,mmm, texto, linha em branco. UTF-8 sem marcação."""
    blocos = []
    for n, (a, b, texto) in enumerate(_sem_sobreposicao(itens), 1):
        blocos.append(f"{n}\n{comum.hms(a / 1000)} --> {comum.hms(b / 1000)}\n{texto.strip().replace('-->', '→')}\n")
    return "\n".join(blocos)


def texto_vtt(itens: list[dict]) -> str:
    """WebVTT: cabeçalho WEBVTT, tempos com ponto, & < > escapados, sem "-->" no texto."""
    partes = ["WEBVTT\n"]
    for n, (a, b, texto) in enumerate(_sem_sobreposicao(itens), 1):
        limpo = texto.strip().replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("--&gt;", "→")
        partes.append(f"{n}\n{comum.hms(a / 1000, '.')} --> {comum.hms(b / 1000, '.')}\n{limpo}\n")
    return "\n".join(partes)


# ─────────────────────────────────────────────────────────────── documento ──
def _pal_para_json(p: Pal, pontuacao: str) -> dict:
    item = {"a": p.a, "b": p.b, "w": p.w(pontuacao), "linha": p.linha, "destaque": bool(p.destaque), "p": round(p.p, 3), "txt": p.txt}
    if p.orig and not p.censurada and p.orig != p.txt:
        item["orig"] = p.orig
    if p.censurada:
        item["censurada"] = True
    if p.fala_fim is not None:
        item["fala_fim"] = round(min(p.b, max(p.a, p.fala_fim)), 3)
    return item


def _pal_de_json(item: dict) -> Pal:
    pre, nucleo, pos = partir_token(item.get("txt") or item["w"])
    return Pal(a=float(item["a"]), b=float(item["b"]), nucleo=nucleo or str(item["w"]), pre=pre, pos=pos, p=float(item.get("p", 1.0)),
               orig=item.get("orig"), destaque=bool(item.get("destaque")), censurada=bool(item.get("censurada")),
               linha=int(item.get("linha", 0)), fala_fim=None if item.get("fala_fim") is None else float(item["fala_fim"]))


def palavras_do_documento(doc: dict) -> list[Pal]:
    return [_pal_de_json(w) for c in doc["cues"] for w in c["palavras"]]


def max_linhas_de(med) -> int:
    """Quantas linhas uma cue pode ter: `legenda.max_linhas` da DA; no estilo `palavra`, uma (só uma palavra aparece)."""
    return 1 if med.uma_por_vez else int(med.max_linhas)


def _montar_cue(n: int, t0: float, t1: float, trecho: list[Pal], med, pontuacao: str, partes: list[int] | None = None) -> tuple[dict, bool]:
    """Uma cue do contrato a partir das palavras; devolve (cue, coube_sem_encolher)."""
    larguras = [med.largura(p.w(pontuacao)) for p in trecho]
    coube = True
    if partes is None:
        partes = melhor_quebra(trecho, larguras, med)
        if partes is None:                             # não cabe: reparte por igual; na tela o kit encolhe (e legendar avisa)
            coube = False
            nl = 1 if med.uma_por_vez else min(med.max_linhas, len(trecho))
            por = math.ceil(len(trecho) / nl)
            partes = [len(trecho[i:i + por]) for i in range(0, len(trecho), por)]
    elif sum(partes) != len(trecho) or any(q < 1 for q in partes):
        raise Erro(f"cue {n}: as linhas {partes} não somam as {len(trecho)} palavras da cue.",
                   "Em --linhas passe a quantidade de palavras de cada linha, ex.: 2,3.")
    else:
        limites = [0, *itertools.accumulate(partes)]
        coube = all(_largura_linha(larguras[a:b], med.vao) <= med.util + 0.5 for a, b in zip(limites, limites[1:]))
    linhas, i = [], 0
    for li, q in enumerate(partes):
        for p in trecho[i:i + q]:
            p.linha = li
        linhas.append([p.w(pontuacao) for p in trecho[i:i + q]])
        i += q
    for p in trecho:                                   # palavras dentro da cue
        p.a, p.b = max(p.a, 0.0), min(p.b, t1)
    cue = {"id": n, "t0": t0, "t1": t1, "linhas": linhas, "palavras": [_pal_para_json(p, pontuacao) for p in trecho]}
    if len(linhas) > max_linhas_de(med):
        cue["_linhas_demais"] = max_linhas_de(med)
    return cue, coube


def _avisos(doc: dict, limiar: float, dur_min: float) -> list[dict]:
    avisos = []
    uma_por_vez = doc.get("estilo") == "palavra"
    for c in doc["cues"]:
        texto_cue = " ".join(w["w"] for w in c["palavras"])
        dur = c["t1"] - c["t0"]
        if uma_por_vez:                                # o que se vê é cada palavra: avisa a que passa como um flash
            fins = [w["a"] for w in c["palavras"][1:]] + [c["t1"]]
            for w, f in zip(c["palavras"], fins):
                if f - w["a"] < MIN_PALAVRA - 0.005:
                    avisos.append({"tipo": "relampago", "cue": c["id"], "t": w["a"],
                                   "mensagem": f"cue {c['id']} ({relogio(w['a'])}): «{w['w']}» fica só {br(f - w['a'])} s na tela (fala muito rápida ou tempo ruim da transcrição)"})
        for w in c["palavras"]:
            if w.get("p", 1.0) < limiar and not w.get("censurada"):
                avisos.append({"tipo": "confianca", "cue": c["id"], "t": w["a"], "palavra": w["w"], "p": w["p"],
                               "mensagem": f"cue {c['id']} ({relogio(w['a'])}): «{w['w']}» saiu com confiança {br(w['p'])} — ouça o trecho e corrija se preciso"})
        if dur < dur_min - 1e-6 and not uma_por_vez:       # no estilo `palavra` quem pisca é a palavra (aviso `relampago`), não a cue
            avisos.append({"tipo": "duracao", "cue": c["id"], "t": c["t0"],
                           "mensagem": f"cue {c['id']} ({relogio(c['t0'])}): fica só {br(dur)} s na tela (mínimo {br(dur_min)} s) — «{texto_cue}»"})
        cps = len(texto_cue) / max(dur, 1e-6)              # sempre pela duração REAL da cue, em qualquer estilo
        if cps > CPS_QUEIMADA and len(c["palavras"]) > 1:
            avisos.append({"tipo": "leitura", "cue": c["id"], "t": c["t0"],
                           "mensagem": f"cue {c['id']} ({relogio(c['t0'])}): {br(cps, 1)} caracteres por segundo (fala rápida; o aviso começa em {CPS_QUEIMADA}) — «{texto_cue}»"})
        if c.get("_linhas_demais"):
            avisos.append({"tipo": "linhas", "cue": c["id"], "t": c["t0"],
                           "mensagem": f"cue {c['id']} ({relogio(c['t0'])}): {len(c['linhas'])} linhas, acima de legenda.max_linhas ({c['_linhas_demais']}) — sairia da faixa "
                                       f"que a DA reserva para a legenda; na tela a quebra é refeita em até {c['_linhas_demais']} — «{texto_cue}»"})
        elif c.get("_nao_coube"):
            avisos.append({"tipo": "largura", "cue": c["id"], "t": c["t0"],
                           "mensagem": f"cue {c['id']} ({relogio(c['t0'])}): não cabe no tamanho da DA e vai encolher na tela — «{texto_cue}»"})
    return avisos


def _fechar_documento(doc: dict, pal_por_cue: list[list[Pal]], limiar: float, dur_min: float) -> dict:
    """Recalcula o que deriva das cues: frases da legenda oculta, avisos e contagens."""
    todas = [p for trecho in pal_por_cue for p in trecho]
    respiro_oculta = float((doc.get("regras") or {}).get("respiro_oculta", RESPIRO_QUADROS / 30))
    doc["frases"] = frases(todas, doc["duracao"], respiro_oculta) if todas else []
    doc["avisos"] = _avisos(doc, limiar, dur_min)
    for it in doc["frases"]:
        cps = len(it["texto"].replace("\n", " ")) / max(it["t1"] - it["t0"], 1e-6)
        if cps > OCULTA_CPS + 3:
            doc["avisos"].append({"tipo": "leitura_oculta", "t": it["t0"],
                                  "mensagem": f"legenda oculta em {relogio(it['t0'])}: {br(cps, 0)} caracteres por segundo (referência {OCULTA_CPS}) — fala rápida, sem silêncio para estender"})
    for c in doc["cues"]:
        c.pop("_nao_coube", None)
        c.pop("_linhas_demais", None)
    return doc


def construir(palavras, d, largura: int, altura: int, formato: str, plataforma: str | None = None, inicio: float | None = None,
              fim: float | None = None, duracao: float | None = None, fps=None, glossario: dict | None = None,
              pontuacao: str | None = None, limiar: float = LIMIAR_CONFIANCA, origem: str | None = None,
              palavras_origem: str | None = None, segura: float = SEGURA, dur_min: float = DUR_MIN,
              respiro_quadros: int = RESPIRO_QUADROS) -> dict:
    """O documento de cues (contrato legendas/<nome>.cues.json) em memória. `d` é a DA carregada pelo kit."""
    da, _, _, _ = comum.kit()
    leg = d["legenda"]
    estilo = leg["estilo"]
    pontuacao = pontuacao or ("manter" if estilo == "bloco" else "limpa")
    if pontuacao not in PONTUACOES:
        raise Erro(f"pontuação {pontuacao!r} inválida; use {', '.join(PONTUACOES)}.", codigo=64)
    fps_f = da.fps_racional(fps) if fps is not None and not isinstance(fps, Fraction) else fps
    if not fps_f:
        fps_f = Fraction(30000, 1001)
    # no estilo `palavra` não há bloco trocando: o respiro só roubaria tempo da última palavra de cada cue
    respiro = 0.0 if estilo == "palavra" else respiro_quadros / float(fps_f)
    dados = ler_palavras(palavras)
    if duracao is not None:                            # palavra que começa depois do fim do vídeo não tem onde aparecer
        limite = float(inicio or 0.0) + float(duracao)
        antes = len(dados)
        dados = [w for w in dados if w["a"] < limite - 0.02] or dados[:0]
        depois_do_fim = antes - len(dados)
        if not dados:
            raise Erro(f"todas as {antes} palavras da transcrição começam depois do fim do vídeo ({br(limite)} s).",
                       "O arquivo de palavras é de outro vídeo, ou os tempos não estão no relógio deste (use --inicio/--fim em vez de cortar a transcrição).")
    else:
        depois_do_fim = 0
    pal, notas = preparar(dados, inicio, fim, max(MIN_PALAVRA, 2 / float(fps_f)))
    notas["depois_do_fim"] = depois_do_fim
    pal, rel = aplicar_glossario(pal, glossario)
    if not pal:
        raise Erro("depois do glossário não sobrou palavra nenhuma no trecho.")
    normalizar_tempos(pal, max(MIN_PALAVRA, 2 / float(fps_f)))
    janela_dur = (float(fim) - float(inicio or 0)) if fim is not None else None
    if duracao is None:
        duracao = janela_dur if janela_dur is not None else pal[-1].b + segura
    elif janela_dur is not None:
        duracao = min(float(duracao), janela_dur)
    med = MedidorDaDA(d, largura, altura, plataforma)
    texto_de = lambda p: p.w(pontuacao)  # noqa: E731
    grupos = segmentar(pal, med, int(leg["max_palavras"]), texto_de=texto_de, dur_min=dur_min)
    tempos = temporizar(pal, grupos, float(duracao), respiro, segura, dur_min)
    # no estilo `palavra` só uma palavra aparece por vez: a duração da cue não se vê, e fundir só amarraria tamanhos
    fusoes = 0 if estilo == "palavra" else fundir_curtas(pal, tempos, med, int(leg["max_palavras"]), dur_min, texto_de)
    if fusoes:
        tempos = temporizar(pal, [(c["i0"], c["i1"]) for c in tempos], float(duracao), respiro, segura, dur_min)
    cues, por_cue = [], []
    for n, c in enumerate(tempos, 1):
        trecho = pal[c["i0"]:c["i1"]]
        cue, coube = _montar_cue(n, c["t0"], c["t1"], trecho, med, pontuacao)
        if not coube:
            cue["_nao_coube"] = True
        cues.append(cue)
        por_cue.append(trecho)
    doc = {
        "versao": 1, "origem": origem, "formato": formato, "plataforma": med.zona["plataforma"], "estilo": estilo,
        "largura": int(largura), "altura": int(altura), "fps": f"{fps_f.numerator}/{fps_f.denominator}",
        "janela": {"inicio": round(float(inicio or 0.0), 3), "fim": None if fim is None else round(float(fim), 3)},
        "duracao": round(float(duracao), 3), "palavras_origem": palavras_origem, "pontuacao": pontuacao,
        "da_sha256": d.sha256, "gerado_em": da.agora_iso(), "editado": False,
        "regras": {"max_palavras": int(leg["max_palavras"]), "max_linhas": int(leg["max_linhas"]), "segura": segura, "dur_min": dur_min,
                   "respiro": round(respiro, 4), "respiro_oculta": round(respiro_quadros / float(fps_f), 4), "pausa_dura": PAUSA_DURA,
                   "limiar_confianca": limiar},
        "glossario": {**{k: v for k, v in rel.items() if k != "sem_ocorrencia"}, "sem_ocorrencia": rel["sem_ocorrencia"]},
        "notas": {**notas, "fusoes_de_cue_curta": fusoes},
        "cues": cues,
    }
    return _fechar_documento(doc, por_cue, limiar, dur_min)


def validar(doc: dict) -> list[str]:
    """Problemas de estrutura de um documento de cues (lista vazia = ok). É o que `editar` confere antes de gravar."""
    prob = []
    if not isinstance(doc, dict) or doc.get("versao") != 1 or not isinstance(doc.get("cues"), list):
        return ["não é um documento de cues versão 1 (faltam `versao` e `cues`)"]
    if doc.get("estilo") not in ESTILOS:
        prob.append(f"estilo {doc.get('estilo')!r} desconhecido")
    fim_anterior = -1.0
    for c in doc["cues"]:
        rot = f"cue {c.get('id')}"
        if not all(k in c for k in ("t0", "t1", "linhas", "palavras")):
            prob.append(f"{rot}: faltam campos (t0, t1, linhas, palavras)")
            continue
        if c["t1"] <= c["t0"]:
            prob.append(f"{rot}: t1 ({c['t1']}) não é depois de t0 ({c['t0']})")
        if c["t0"] < fim_anterior - 1e-6:
            prob.append(f"{rot}: começa em {c['t0']} antes do fim da anterior ({fim_anterior})")
        fim_anterior = c["t1"]
        if not c["palavras"]:
            prob.append(f"{rot}: sem palavras")
            continue
        if [w["w"] for w in c["palavras"]] != [w for linha in c["linhas"] for w in linha]:
            prob.append(f"{rot}: `linhas` e `palavras` não têm o mesmo texto")
        a_ant = c["t0"] - 1e-6
        for w in c["palavras"]:
            if w["a"] < a_ant - 1e-6 or w["a"] >= c["t1"] + 1e-6:
                prob.append(f"{rot}: palavra «{w['w']}» começa em {w['a']}, fora de ordem ou fora da cue")
            a_ant = w["a"]
            if not 0 <= int(w.get("linha", 0)) < len(c["linhas"]):
                prob.append(f"{rot}: palavra «{w['w']}» aponta para a linha {w.get('linha')}, que não existe")
    return prob


def caminhos(pasta, nome: str) -> dict:
    pasta = Path(str(pasta))
    return {"cues": pasta / f"{nome}.cues.json", "srt": pasta / f"{nome}.srt", "vtt": pasta / f"{nome}.vtt"}


def gravar(doc: dict, pasta, nome: str) -> dict:
    """Grava <nome>.cues.json + .srt + .vtt (irmãos) e devolve os caminhos."""
    prob = validar(doc)
    if prob:
        raise Erro("as cues ficaram inconsistentes e não foram gravadas:\n  - " + "\n  - ".join(prob[:8]),
                   "Isto é defeito do gerador ou de uma edição: rode `cues.py gerar` de novo ou desfaça a última edição.")
    arq = caminhos(pasta, nome)
    comum.gravar_json(arq["cues"], doc)
    comum.gravar_texto(arq["srt"], texto_srt(doc["frases"]))
    comum.gravar_texto(arq["vtt"], texto_vtt(doc["frases"]))
    return arq


def nome_do_formato(d, largura: int, altura: int) -> str:
    """Nome do formato de VÍDEO da DA com essas dimensões ('vertical', 'horizontal'…) ou 'LxA'. `thumbnail` tem o mesmo
    tamanho de um vídeo 720p mas não é formato de vídeo (não tem fps): não serve de nome."""
    for nome, f in d["formatos"].items():
        if isinstance(f, dict) and f.get("largura") == largura and f.get("altura") == altura and f.get("fps"):
            return nome
    return f"{largura}x{altura}"


def _segundos(t: float) -> str:
    return f"{float(t):.3f}".rstrip("0").rstrip(".")


def marca_do_trecho(inicio, fim, info: dict | None = None) -> str:
    """'62.4-91s': o intervalo do trecho, em segundos do vídeo de origem, para compor nome de arquivo e mensagem."""
    ate = float(fim) if fim is not None else (float(info["duracao"]) if info and info.get("duracao") else None)
    if ate is not None and info and info.get("duracao"):
        ate = min(ate, float(info["duracao"]))
    return f"{_segundos(inicio or 0)}-{_segundos(ate) + 's' if ate is not None else 'fim'}"


def e_do_video_inteiro(doc: dict) -> bool:
    """As cues deste documento são a legenda de um vídeo inteiro (relógio = o do próprio vídeo), e não de um trecho?"""
    jan, origem, fonte = doc.get("janela") or {}, doc.get("origem"), doc.get("fonte") or {}
    if float(jan.get("inicio") or 0) > 0.0005 or "#t=" in str(origem or ""):
        return False
    if origem is None:
        return jan.get("fim") is None
    return not fonte.get("video") or fonte.get("video") == origem


def resolver_formato(d, formato: str | None, video_info: dict | None, escala: float | None = None) -> tuple[str, int, int]:
    """(nome do formato, largura, altura) do quadro de SAÍDA: o formato pedido (nome da DA ou LxA) ou, sem ele, o
    tamanho do próprio vídeo. `escala` reduz para prévias (lados pares)."""
    if formato:
        L, A = d.dimensoes(formato)
    elif video_info and video_info.get("largura"):
        L, A = video_info["largura"], video_info["altura"]
    else:
        raise Erro("não sei o tamanho do quadro: informe --formato (vertical, horizontal ou LxA) ou --video.", codigo=64)
    if escala is not None and abs(float(escala) - 1) > 1e-9:
        if not 0.05 <= float(escala) <= 1:
            raise Erro(f"--escala {escala} fora de 0.05–1 (é só para prévias e testes).", "Use, por exemplo, --escala 0.5 (metade do tamanho).", 64)
        L, A = max(2, int(round(L * float(escala) / 2)) * 2), max(2, int(round(A * float(escala) / 2)) * 2)
    if L % 2 or A % 2:
        raise Erro(f"quadro {L}×{A}: largura e altura precisam ser pares (H.264 4:2:0).", "Use um formato da DA ou LxA com números pares.", 64)
    return nome_do_formato(d, L, A), int(L), int(A)


def gerar(palavras, projeto=None, video=None, formato: str | None = None, plataforma: str | None = None, inicio=None, fim=None,
          nome: str | None = None, glossario=None, escala: float | None = None, fps=None, forcar: bool = False, d=None,
          gravar_arquivos: bool = True, **regras) -> dict:
    """Do arquivo de palavras aos três arquivos em legendas/. Devolve {'doc', 'arquivos', 'nome', 'largura', 'altura'}.
    É a função que legendar.py chama; `d` permite reaproveitar a DA já carregada."""
    da, _, vid, _ = comum.kit()
    d = d or comum.carregar_da(projeto, pistas=[palavras if not isinstance(palavras, list) else None, video])
    info = vid.sondar(video) if video else None
    if info is not None and not info.get("largura"):
        raise Erro(f"{Path(str(video)).name} não tem trilha de vídeo.", "Passe o vídeo que vai receber a legenda.")
    nome_fmt, L, A = resolver_formato(d, formato, info, escala)
    if plataforma:
        d.margens("vertical" if A > L else "horizontal", plataforma, largura=L, altura=A)      # nome inexistente → erro do kit, com sugestão
    if inicio is not None and info is not None and float(inicio) >= float(info["duracao"]):
        raise Erro(f"--inicio ({br(float(inicio))} s) fica depois do fim do vídeo ({br(info['duracao'])} s).", codigo=64)
    # Trecho ou vídeo inteiro? Decide o NOME: legendas/<nome do vídeo>.srt é onde a video-publicacao procura a legenda
    # oculta do vídeo inteiro — a de um trecho nunca pode ser gravada com esse nome.
    trecho = float(inicio or 0) > 0.0005 or (fim is not None and (info is None or float(fim) < float(info["duracao"]) - 0.02))
    do_inteiro = {re.sub(r"\.palavras(\.json)?$|\.json$", "", Path(str(x)).name if x is palavras else Path(str(x)).stem)
                  for x in (video, None if isinstance(palavras, list) else palavras) if x}
    if nome is None:
        nome = (Path(str(video)).stem if video else next(iter(do_inteiro), "legenda"))
        if trecho:
            nome = f"{nome} {marca_do_trecho(inicio, fim, info)}"
    elif trecho and comum.nome_de_arquivo(nome) in do_inteiro:
        sugestao = f"{comum.nome_de_arquivo(nome)} {marca_do_trecho(inicio, fim, info)}"
        raise Erro(f"o trecho ({marca_do_trecho(inicio, fim, info)}) seria gravado como legendas/{comum.nome_de_arquivo(nome)}.srt, o nome da legenda do vídeo INTEIRO "
                   "(é esse arquivo que a video-publicacao envia junto com o vídeo longo).",
                   f"Dê outro nome ao trecho: --nome \"{sugestao}\" (ou o nome do corte, ex.: --nome K01).", 64)
    nome = comum.nome_de_arquivo(nome)
    pasta = d.raiz / "legendas"
    arq = caminhos(pasta, nome)
    if arq["cues"].is_file() and not forcar:
        try:
            antigo = comum.ler_json(arq["cues"])
        except Erro:
            antigo = {}
        if isinstance(antigo, dict) and antigo.get("editado"):
            raise Erro(f"{comum.relativo(arq['cues'], d.raiz)} foi corrigido à mão ({len(antigo.get('edicoes') or [])} edição(ões)) e seria sobrescrito.",
                       "Para queimar a versão corrigida use `legendar.py --cues <esse arquivo>`; para jogar as correções fora e "
                       "gerar de novo, acrescente --refazer-cues (em cues.py gerar: --forcar).")
        if trecho and isinstance(antigo, dict) and e_do_video_inteiro(antigo):
            raise Erro(f"{comum.relativo(arq['cues'], d.raiz)} é a legenda de um vídeo INTEIRO ({antigo.get('origem') or 'sem vídeo'}) e seria trocada pela de um trecho "
                       f"({marca_do_trecho(inicio, fim, info)}), junto com o .srt e o .vtt.",
                       f"Dê outro nome ao trecho (--nome \"{nome} {marca_do_trecho(inicio, fim, info)}\"); para substituir de propósito, "
                       "--refazer-cues (em cues.py gerar: --forcar).")
    g = None
    caminho_g = Path(str(glossario)) if glossario else pasta / "glossario.json"
    if glossario and not caminho_g.is_file():
        raise Erro(f"glossário não encontrado: {caminho_g}")
    if caminho_g.is_file():
        g = ler_glossario(caminho_g)
    if fps is None:
        fps = info["fps"] if info and info.get("fps") else vid.fps_do_formato(d, f"{L}x{A}")
    duracao, fim_pedido = None, None
    if info:
        duracao = max(0.0, float(info["duracao"]) - float(inicio or 0.0))
        if fim is not None and float(fim) > float(info["duracao"]) + 0.02:      # trecho que passa do fim: vale até o fim do vídeo
            fim_pedido, fim = float(fim), round(float(info["duracao"]), 3)
    # `origem` = o vídeo cujo relógio as cues seguem. Com trecho, os tempos são do trecho: o endereço leva o intervalo
    # (#t=início,fim), para ninguém tomar a legenda de um pedaço pela legenda do vídeo inteiro.
    origem = comum.relativo(video, d.raiz) if video else None
    if origem and (float(inicio or 0) > 0.0005 or (fim is not None and info and float(fim) < float(info["duracao"]) - 0.02)):
        origem = f"{origem}#t={float(inicio or 0):.3f},{float(fim) if fim is not None else float(info['duracao']):.3f}"
    doc = construir(palavras, d, L, A, nome_fmt, plataforma, inicio, fim, duracao, fps, g,
                    origem=origem,
                    palavras_origem=None if isinstance(palavras, list) else comum.relativo(palavras, d.raiz), **regras)
    if g is not None:
        doc["glossario"]["arquivo"] = comum.relativo(caminho_g, d.raiz)
    if video:
        doc["fonte"] = {"video": comum.relativo(video, d.raiz), "inicio": round(float(inicio or 0.0), 3),
                        "fim": None if fim is None else round(float(fim), 3)}
    if fim_pedido is not None:
        doc["notas"]["fim_pedido"] = fim_pedido
    if gravar_arquivos:
        gravar(doc, pasta, nome)
    return {"doc": doc, "arquivos": arq, "nome": nome, "largura": L, "altura": A, "da": d}


# ────────────────────────────────────────────────────────────────── editar ──
def _realinhar(velhas: list[Pal], novas: list[str]) -> list[Pal]:
    """Texto novo sobre palavras cronometradas: o que não mudou guarda o tempo; o que mudou reparte o intervalo do
    trecho trocado pelo tamanho das palavras novas (difflib decide o que é "o mesmo")."""
    antes = [v.txt for v in velhas]
    sm = difflib.SequenceMatcher(a=[comum.chave(partir_token(x)[1]) for x in antes],
                                 b=[comum.chave(partir_token(x)[1]) for x in novas], autojunk=False)
    saida: list[Pal] = []
    for op, i0, i1, j0, j1 in sm.get_opcodes():
        if op == "equal":
            for v, texto in zip(velhas[i0:i1], novas[j0:j1]):
                pre, nucleo, pos = partir_token(texto)
                saida.append(Pal(a=v.a, b=v.b, nucleo=nucleo or texto, pre=pre, pos=pos, p=v.p, orig=v.orig,
                                 destaque=v.destaque, censurada=v.censurada, fala_fim=v.fala_fim))
        elif op == "delete":
            if saida:                                  # a palavra tirada continua sendo dita: a anterior fica até o fim dela
                saida[-1].fala_fim = velhas[i1 - 1].fim_da_fala
                saida[-1].b = velhas[i1 - 1].b
        elif op == "replace":
            bloco = _fundir(velhas, i0, i1, novas[j0:j1])
            for b in bloco:
                b.p, b.orig = 1.0, None                # texto conferido por gente: sem aviso de confiança
            # _fundir herda a pontuação das pontas antigas; o texto novo manda
            for b, texto in zip(bloco, novas[j0:j1]):
                b.pre, nucleo, b.pos = partir_token(texto)
                b.nucleo = nucleo or texto
            saida += bloco
        else:                                          # insert: abre espaço dividindo o tempo da palavra anterior (ou da seguinte)
            if saida:
                dono = saida[-1]
                a, b = dono.a, dono.b
                pesos = [max(1, len(dono.nucleo))] + [max(1, len(x)) for x in novas[j0:j1]]
            elif i0 < len(velhas):
                dono = velhas[i0]
                a, b = dono.a, dono.b
                pesos = [max(1, len(x)) for x in novas[j0:j1]] + [max(1, len(dono.nucleo))]
            else:
                raise Erro("não há palavra com tempo para apoiar o texto novo.")
            total, acum, cortes = sum(pesos), 0, []
            for w in pesos:
                cortes.append((a + (b - a) * acum / total, a + (b - a) * (acum + w) / total))
                acum += w
            if saida:
                dono.b = round(cortes[0][1], 3)
                faixa = cortes[1:]
            else:
                velhas[i0] = Pal(**{**dono.__dict__, "a": round(cortes[-1][0], 3)})
                faixa = cortes[:-1]
            for texto, (ta, tb) in zip(novas[j0:j1], faixa):
                pre, nucleo, pos = partir_token(texto)
                saida.append(Pal(a=round(ta, 3), b=round(tb, 3), nucleo=nucleo or texto, pre=pre, pos=pos, p=1.0))
    return saida


def editar(doc: dict, d, cue: int, texto: str | None = None, palavra: int | None = None, para: str | None = None,
           t0: float | None = None, t1: float | None = None, juntar: bool = False, dividir: int | None = None,
           linhas: list[int] | None = None, destacar: list[int] | None = None, sem_destaque: list[int] | None = None,
           remover: bool = False) -> tuple[dict, str]:
    """Aplica UMA correção a uma cue e devolve (documento, descrição do que mudou). Recalcula linhas, legenda oculta e
    avisos; marca `editado` para que um `gerar` não apague a correção sem querer."""
    da, _, _, _ = comum.kit()
    ids = [c["id"] for c in doc["cues"]]
    if cue not in ids:
        raise Erro(f"não existe cue {cue} (o arquivo tem as cues {ids[0]} a {ids[-1]}).", "Veja os números com `cues.py mostrar <arquivo>`.", 64)
    k = ids.index(cue)
    por_cue = [[_pal_de_json(w) for w in c["palavras"]] for c in doc["cues"]]
    tempos = [[c["t0"], c["t1"]] for c in doc["cues"]]
    partes: dict[int, list[int]] = {i: [len(l) for l in c["linhas"]] for i, c in enumerate(doc["cues"])}
    pont = doc.get("pontuacao") or "limpa"
    respiro = float((doc.get("regras") or {}).get("respiro", RESPIRO_QUADROS / 30))
    feito = []
    n_pal = len(por_cue[k])

    def indice(v: int, o_que: str) -> int:
        if not 1 <= v <= len(por_cue[k]):
            raise Erro(f"{o_que} {v} não existe: a cue {cue} tem {len(por_cue[k])} palavra(s).", "As palavras são contadas a partir de 1.", 64)
        return v - 1

    if remover:
        del por_cue[k], tempos[k]
        partes = {}
        feito.append(f"cue {cue} removida")
    else:
        if texto is not None:
            novas = texto.split()
            if not novas:
                raise Erro("--texto vazio: para tirar a cue use --remover.", codigo=64)
            por_cue[k] = _realinhar(por_cue[k], novas)
            partes.pop(k, None)
            feito.append(f"cue {cue}: texto → «{texto}»")
        if para is not None:
            if palavra is None:
                raise Erro("--para precisa de --palavra N (qual palavra da cue trocar).", codigo=64)
            i = indice(palavra, "palavra")
            novas = para.split()
            if len(novas) == 1:
                velha = por_cue[k][i]
                pre, nucleo, pos = partir_token(novas[0])
                por_cue[k][i] = Pal(a=velha.a, b=velha.b, nucleo=nucleo or novas[0], pre=pre or velha.pre, pos=pos or velha.pos,
                                    p=1.0, destaque=velha.destaque, fala_fim=velha.fala_fim)
            else:
                bloco = _fundir(por_cue[k], i, i + 1, novas)
                for b in bloco:
                    b.p, b.orig = 1.0, None
                por_cue[k][i:i + 1] = bloco
                partes.pop(k, None)
            feito.append(f"cue {cue}: palavra {palavra} → «{para}»")
        for lista, valor in ((destacar, True), (sem_destaque, False)):
            for v in lista or []:
                por_cue[k][indice(v, "palavra")].destaque = valor
                feito.append(f"cue {cue}: palavra {v} {'com' if valor else 'sem'} destaque")
        if dividir is not None:
            if not 1 <= dividir < len(por_cue[k]):
                raise Erro(f"--dividir {dividir}: a cue {cue} tem {len(por_cue[k])} palavra(s); o corte vai depois da palavra 1 a {len(por_cue[k]) - 1}.", codigo=64)
            esq, dir_ = por_cue[k][:dividir], por_cue[k][dividir:]
            meio = dir_[0].a
            por_cue[k:k + 1] = [esq, dir_]
            tempos[k:k + 1] = [[tempos[k][0], round(max(tempos[k][0] + MIN_PALAVRA, meio - respiro), 3)], [meio, tempos[k][1]]]
            partes = {}
            feito.append(f"cue {cue} dividida depois da palavra {dividir}")
        if juntar:
            if k + 1 >= len(por_cue):
                raise Erro(f"--juntar: a cue {cue} é a última; não há seguinte para juntar.", codigo=64)
            por_cue[k:k + 2] = [por_cue[k] + por_cue[k + 1]]
            tempos[k:k + 2] = [[tempos[k][0], tempos[k + 1][1]]]
            partes = {}
            feito.append(f"cues {cue} e {cue + 1} juntadas")
        if t0 is not None or t1 is not None:
            novo0 = tempos[k][0] if t0 is None else float(t0)
            novo1 = tempos[k][1] if t1 is None else float(t1)
            if novo1 <= novo0:
                raise Erro(f"tempos inválidos: a cue terminaria ({br(novo1)} s) antes de começar ({br(novo0)} s).", codigo=64)
            if k > 0 and novo0 < tempos[k - 1][1]:
                raise Erro(f"--t0 {br(novo0)} invade a cue anterior, que vai até {br(tempos[k - 1][1])} s.", "Encurte a anterior primeiro (--cue N --t1 …).", 64)
            if k + 1 < len(tempos) and novo1 > tempos[k + 1][0]:
                raise Erro(f"--t1 {br(novo1)} invade a cue seguinte, que começa em {br(tempos[k + 1][0])} s.", codigo=64)
            if novo1 > float(doc.get("duracao") or novo1) + 1e-6:
                raise Erro(f"--t1 {br(novo1)} passa do fim do vídeo ({br(doc['duracao'])} s).", codigo=64)
            desloc = novo0 - tempos[k][0]
            if abs(desloc) > 1e-9 and por_cue[k][0].a < novo0:      # a cue começou mais tarde: a 1ª palavra acompanha
                por_cue[k][0].a = round(novo0, 3)
            if novo0 < por_cue[k][0].a and t0 is not None:
                por_cue[k][0].a = round(novo0, 3)
            tempos[k] = [round(novo0, 3), round(novo1, 3)]
            feito.append(f"cue {cue}: tempos → {br(novo0)}–{br(novo1)} s")
        if linhas is not None:
            if sum(linhas) != len(por_cue[k]) or any(q < 1 for q in linhas):
                raise Erro(f"--linhas {','.join(map(str, linhas))}: a cue {cue} tem {len(por_cue[k])} palavra(s); as linhas precisam somar isso.",
                           "Passe a quantidade de palavras de cada linha, ex.: 2,3.", 64)
            if doc.get("estilo") == "palavra" and len(linhas) > 1:
                raise Erro(f"--linhas {','.join(map(str, linhas))}: no estilo `palavra` só uma palavra aparece por vez; não há linhas para repartir.",
                           "Para mudar o agrupamento use --dividir K ou --juntar.", 64)
            teto = int(d["legenda"]["max_linhas"])
            if len(linhas) > teto:
                raise Erro(f"--linhas {','.join(map(str, linhas))}: são {len(linhas)} linhas e a direção de arte permite {teto} (legenda.max_linhas).",
                           "Com mais linhas a legenda sai da faixa que a DA reserva para ela e passa por cima de GC e título. Divida a cue "
                           "(--dividir K); se a legenda do projeto deve ter mais linhas, isso é token: legenda.max_linhas na DA.", 64)
            partes[k] = list(linhas)
            feito.append(f"cue {cue}: linhas → {linhas}")
    if not feito:
        raise Erro("nenhuma mudança pedida.", "Use --texto, --palavra N --para, --t0/--t1, --juntar, --dividir N, --linhas, --destacar ou --remover.", 64)
    if not por_cue:
        raise Erro("isso tiraria a última cue do arquivo.", "Para não legendar, simplesmente não rode o legendar.", 64)
    med = MedidorDaDA(d, int(doc["largura"]), int(doc["altura"]), doc.get("plataforma"))
    novas_cues = []
    for i, (trecho, (c0, c1)) in enumerate(zip(por_cue, tempos)):
        normalizar_tempos(trecho, MIN_PALAVRA, piso=c0)       # nenhuma palavra antes do início da própria cue
        if i + 1 < len(tempos) and trecho[-1].a + MIN_PALAVRA > tempos[i + 1][0]:
            raise Erro(f"a cue {i + 1} ficou com palavras demais para o tempo que tem ({len(trecho)} palavra(s) em {br(tempos[i + 1][0] - c0)} s).",
                       "Encurte o texto, ou junte a cue com a seguinte (--juntar) antes de trocar o texto.", 64)
        cue_json, coube = _montar_cue(i + 1, round(c0, 3), round(max(c1, trecho[-1].a + MIN_PALAVRA), 3), trecho, med, pont,
                                      partes.get(i) if len(partes.get(i) or []) and sum(partes.get(i) or []) == len(trecho) else None)
        if not coube:
            cue_json["_nao_coube"] = True
        novas_cues.append(cue_json)
    doc = {**doc, "cues": novas_cues, "editado": True}
    doc["edicoes"] = list(doc.get("edicoes") or []) + [{"em": da.agora_iso(), "o_que": "; ".join(feito)}]
    regras = doc.get("regras") or {}
    doc = _fechar_documento(doc, por_cue, float(regras.get("limiar_confianca", LIMIAR_CONFIANCA)), float(regras.get("dur_min", DUR_MIN)))
    return doc, "; ".join(feito)


# ───────────────────────────────────────────────────────────────────── CLI ──
def _tabela(doc: dict) -> str:
    linhas = [f"{doc.get('origem') or '(sem vídeo)'} · {doc['formato']} {doc['largura']}×{doc['altura']} · zona {doc['plataforma']} · "
              f"estilo {doc['estilo']} · {len(doc['cues'])} cue(s) em {br(doc['duracao'])} s" + (" · EDITADO" if doc.get("editado") else "")]
    for c in doc["cues"]:
        texto_cue = " / ".join(" ".join(("*" + w if p.get("destaque") else w) for w, p in zip(l, [p for p in c["palavras"] if p["linha"] == li]))
                               for li, l in enumerate(c["linhas"]))
        baixa = min(w.get("p", 1.0) for w in c["palavras"])
        marca = f"  (p {br(baixa)})" if baixa < float((doc.get("regras") or {}).get("limiar_confianca", LIMIAR_CONFIANCA)) else ""
        linhas.append(f"{c['id']:>4}  {relogio(c['t0']):>7} → {relogio(c['t1']):>7}  {br(c['t1'] - c['t0']):>5} s  {texto_cue}{marca}")
    return "\n".join(linhas)


def _resumo(doc: dict, arq: dict, raiz) -> str:
    por_tipo: dict = {}
    for a in doc["avisos"]:
        por_tipo[a["tipo"]] = por_tipo.get(a["tipo"], 0) + 1
    g, notas = doc.get("glossario") or {}, doc.get("notas") or {}
    out = [f"{comum.relativo(arq['cues'], raiz)}: {len(doc['cues'])} cue(s), {sum(len(c['palavras']) for c in doc['cues'])} palavra(s), "
           f"{len(doc['frases'])} frase(s) em .srt/.vtt · {doc['formato']} {doc['largura']}×{doc['altura']} · zona {doc['plataforma']} · estilo {doc['estilo']}"]
    if any(g.get(k) for k in ("trocas", "numeros", "censuradas", "destaques")):
        out.append(f"  glossário: {g.get('trocas', 0)} troca(s), {g.get('numeros', 0)} número(s), {g.get('censuradas', 0)} censura(s), {g.get('destaques', 0)} destaque(s)")
    for s in g.get("sem_ocorrencia") or []:
        out.append(f"  glossário: {s} não ocorreu neste trecho")
    if notas.get("fim_pedido") is not None:
        out.append(f"  --fim {br(notas['fim_pedido'])} passa do fim do vídeo: o trecho vai até {br((doc.get('janela') or {}).get('fim') or 0)} s")
    if notas.get("depois_do_fim"):
        out.append(f"  aviso: {notas['depois_do_fim']} palavra(s) da transcrição começam depois do fim do vídeo e ficaram de fora — a transcrição é mesmo deste vídeo?")
    if notas.get("tempos_reparados"):
        out.append(f"  {notas['tempos_reparados']} palavra(s) vieram com duração quase nula ou fora de ordem e foram reposicionadas (cada uma fica acesa ao menos {br(MIN_PALAVRA)} s)")
    if notas.get("fusoes_de_cue_curta"):
        out.append(f"  {notas['fusoes_de_cue_curta']} cue(s) curta(s) demais foram fundidas com a vizinha")
    nomes = {"confianca": "palavra(s) com confiança baixa", "duracao": "cue(s) curta(s) demais", "leitura": "cue(s) de fala rápida",
             "relampago": f"palavra(s) que passam em menos de {br(MIN_PALAVRA)} s",
             "largura": "cue(s) que não cabem sem encolher", "leitura_oculta": "frase(s) da legenda oculta acima da velocidade de leitura"}
    for tipo, qtd in por_tipo.items():
        out.append(f"  aviso: {qtd} {nomes.get(tipo, tipo)}")
    for a in [a for a in doc["avisos"] if a["tipo"] in ("confianca", "largura", "duracao")][:12]:
        out.append(f"    · {a['mensagem']}")
    return "\n".join(out)


def _abrir_doc(caminho) -> tuple[dict, Path]:
    caminho = Path(str(caminho)).expanduser()
    doc = comum.ler_json(caminho, "arquivo de cues")
    prob = validar(doc)
    if prob:
        raise Erro(f"{caminho.name} não é um arquivo de cues válido:\n  - " + "\n  - ".join(prob[:8]),
                   "Gere de novo com `cues.py gerar` (ou confira a edição feita à mão).")
    return doc, caminho


def _nome_do_arquivo(caminho: Path) -> str:
    return caminho.name[:-len(".cues.json")] if caminho.name.endswith(".cues.json") else caminho.stem


def _lista_de_inteiros(s: str) -> list[int]:
    try:
        return [int(x) for x in re.split(r"[,\s]+", s.strip()) if x]
    except ValueError:
        raise argparse.ArgumentTypeError(f"esperava números separados por vírgula (ex.: 2,3), veio {s!r}")


def _tempo(s: str) -> float:
    try:
        return comum.tempo_cli(s)
    except ValueError as e:
        raise argparse.ArgumentTypeError(str(e))


def montar_cli() -> argparse.ArgumentParser:
    ap = comum.Analisador(
        prog="cues.py",
        description="Palavras cronometradas → cues de legenda (legendas/<nome>.cues.json) + .srt e .vtt de frases inteiras.\n"
                    "Agrupamento conforme o bloco `legenda` da direção de arte do projeto (max_palavras, max_linhas, estilo).",
        epilog="Códigos de saída: 0 ok · 1 erro · 2 projeto sem direção de arte · 64 uso incorreto.")
    ap.add_argument("--projeto", metavar="PASTA", help="pasta do projeto (onde está da/da.json); padrão: a pasta atual ou a do arquivo")
    sub = ap.add_subparsers(dest="comando", metavar="{gerar,mostrar,editar,exportar}")

    g = sub.add_parser("gerar", help="cria legendas/<nome>.cues.json + .srt + .vtt a partir da transcrição",
                       description="Segmenta as palavras em cues, aplica o glossário do projeto (legendas/glossario.json), "
                                   "calcula tempos e grava os três arquivos. Não renderiza nada.")
    g.add_argument("--palavras", required=True, metavar="ARQ", help='JSON da transcrição: [{"a": início_s, "b": fim_s, "w": "palavra", "p": confiança}]')
    g.add_argument("--video", metavar="ARQ", help="vídeo de origem (dá tamanho, fps, duração e o campo `origem`)")
    g.add_argument("--formato", metavar="F", help="quadro da legenda: formato da DA (vertical, horizontal…) ou LxA; padrão: o do vídeo")
    g.add_argument("--plataforma", metavar="P", help="zona segura: uniao (padrão do vertical), reels, tiktok, shorts")
    g.add_argument("--inicio", type=_tempo, metavar="S", help="início do trecho no vídeo de origem (segundos ou m:ss); os tempos saem rebaseados")
    g.add_argument("--fim", type=_tempo, metavar="S", help="fim do trecho no vídeo de origem")
    g.add_argument("--nome", metavar="NOME", help="nome dos arquivos em legendas/ (padrão: o do vídeo ou o do arquivo de palavras)")
    g.add_argument("--glossario", metavar="ARQ", help="glossário a usar (padrão: legendas/glossario.json, se existir)")
    g.add_argument("--pontuacao", choices=PONTUACOES, help="pontuação na legenda queimada (padrão: limpa; no estilo bloco, manter)")
    g.add_argument("--limiar-confianca", type=float, default=LIMIAR_CONFIANCA, metavar="P", help=f"confiança abaixo da qual a palavra vira aviso (padrão {LIMIAR_CONFIANCA})")
    g.add_argument("--escala", type=float, metavar="F", help="reduz o quadro (0.5 = metade) para prévias e testes")
    g.add_argument("--forcar", action="store_true", help="sobrescreve um arquivo de cues que foi corrigido à mão")

    m = sub.add_parser("mostrar", help="lista as cues com tempo, duração e quebra de linha", description="Lista as cues de um arquivo. `/` marca a quebra de linha; `*` a palavra com destaque.")
    m.add_argument("arquivo", help="legendas/<nome>.cues.json")
    m.add_argument("--avisos", action="store_true", help="mostra também todos os avisos")

    e = sub.add_parser("editar", help="corrige UMA cue sem refazer as outras (e regrava .srt e .vtt)",
                       description="Corrige uma cue e regrava os três arquivos. O arquivo fica marcado como editado: para queimar "
                                   "use `legendar.py --cues <arquivo>`.")
    e.add_argument("arquivo", help="legendas/<nome>.cues.json")
    e.add_argument("--cue", type=int, required=True, metavar="N", help="número da cue (veja com `mostrar`)")
    e.add_argument("--texto", metavar="TXT", help="texto novo da cue inteira; os tempos das palavras que não mudaram ficam")
    e.add_argument("--palavra", type=int, metavar="K", help="qual palavra da cue (a partir de 1), para usar com --para")
    e.add_argument("--para", metavar="TXT", help="texto novo da palavra K")
    e.add_argument("--t0", type=_tempo, metavar="S", help="novo início da cue (segundos)")
    e.add_argument("--t1", type=_tempo, metavar="S", help="novo fim da cue (segundos)")
    e.add_argument("--juntar", action="store_true", help="junta esta cue com a seguinte")
    e.add_argument("--dividir", type=int, metavar="K", help="divide a cue depois da palavra K")
    e.add_argument("--linhas", type=_lista_de_inteiros, metavar="A,B", help="palavras por linha, ex.: 2,3")
    e.add_argument("--destacar", type=_lista_de_inteiros, metavar="K[,K]", help="põe destaque nas palavras K")
    e.add_argument("--sem-destaque", type=_lista_de_inteiros, metavar="K[,K]", help="tira o destaque das palavras K")
    e.add_argument("--remover", action="store_true", help="apaga a cue (palavra alucinada pelo whisper, trecho que não deve ter legenda)")

    x = sub.add_parser("exportar", help="regrava .srt e .vtt a partir do arquivo de cues", description="Regrava os irmãos .srt e .vtt de um arquivo de cues.")
    x.add_argument("arquivo", help="legendas/<nome>.cues.json")
    return ap


def main(argv=None) -> int:
    ap = montar_cli()
    args = ap.parse_args(argv)
    if not args.comando:
        ap.print_help()
        return 64
    da, _, _, _ = comum.kit()
    if args.comando == "gerar":
        r = gerar(args.palavras, projeto=args.projeto, video=args.video, formato=args.formato, plataforma=args.plataforma,
                  inicio=args.inicio, fim=args.fim, nome=args.nome, glossario=args.glossario, escala=args.escala,
                  forcar=args.forcar, pontuacao=args.pontuacao, limiar=args.limiar_confianca)
        print(_resumo(r["doc"], r["arquivos"], r["da"].raiz))
        return 0
    doc, caminho = _abrir_doc(args.arquivo)
    if args.comando == "mostrar":
        print(_tabela(doc))
        if args.avisos:
            for a in doc.get("avisos") or []:
                print("  aviso:", a["mensagem"])
        elif doc.get("avisos"):
            print(f"({len(doc['avisos'])} aviso(s); veja com --avisos)")
        return 0
    if args.comando == "exportar":
        arq = gravar(doc, caminho.parent, _nome_do_arquivo(caminho))
        print(f"{arq['srt'].name} e {arq['vtt'].name} regravados ({len(doc['frases'])} frase(s)).")
        return 0
    d = comum.carregar_da(args.projeto, pistas=[caminho])
    doc, feito = editar(doc, d, args.cue, texto=args.texto, palavra=args.palavra, para=args.para, t0=args.t0, t1=args.t1,
                        juntar=args.juntar, dividir=args.dividir, linhas=args.linhas, destacar=args.destacar,
                        sem_destaque=args.sem_destaque, remover=args.remover)
    gravar(doc, caminho.parent, _nome_do_arquivo(caminho))
    print(f"{feito}. {caminho.name}, .srt e .vtt regravados; para queimar: legendar.py --cues \"{caminho}\" …")
    if doc.get("da_sha256") and doc["da_sha256"] != d.sha256:
        print("aviso: a direção de arte mudou desde que estas cues foram medidas; se o tamanho ou a largura da legenda mudou, gere de novo.", file=sys.stderr)
    return 0


def executar_cli(main_fn, argv=None) -> int:
    """Roda uma CLI traduzindo erros em UMA linha acionável (sem traceback) e no código de saída certo."""
    try:
        da, _, _, _ = comum.kit()
    except Erro as e:
        print(f"erro: {e.mensagem}" + (f"\n  → {e.dica}" if e.dica else ""), file=sys.stderr)
        return e.codigo
    try:
        return int(main_fn(argv) or 0)
    except Erro as e:
        print(f"erro: {e.mensagem}" + (f"\n  → {e.dica}" if e.dica else ""), file=sys.stderr)
        return e.codigo
    except da.SemDA as e:
        print(f"erro: {e.mensagem}\n  → Este projeto não tem direção de arte (da/da.json). Pare e chame a skill video-direcao-de-arte "
              f"({comum.DA_CLI} init …); legenda sem DA não se renderiza.", file=sys.stderr)
        return 2
    except da.DAErro as e:
        dica = getattr(e, "dica", None)
        print(f"erro: {getattr(e, 'mensagem', None) or e}" + (f"\n  → {dica}" if dica else ""), file=sys.stderr)
        return int(getattr(e, "codigo", None) or 1)
    except TimeoutError as e:                              # trava.TempoEsgotado: a fila de render não andou
        print(f"erro: {e}\n  → A máquina está ocupada com outro render. Veja quem segura a fila: "
              f"python3 {comum.KIT / 'trava.py'} --estado", file=sys.stderr)
        return 75
    except KeyboardInterrupt:
        print("interrompido.", file=sys.stderr)
        return 130
    except BrokenPipeError:
        return 0
    except Exception as e:  # noqa: BLE001 — defeito interno sai em uma linha; o traceback, só a pedido
        if os.environ.get("LEGENDAS_DEBUG") or os.environ.get("DA_DEBUG"):
            raise
        print(f"erro interno: {type(e).__name__}: {e}\n  → Isto é defeito do script, não do seu comando. Rode de novo com LEGENDAS_DEBUG=1 "
              f"para ver onde foi e relate.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(executar_cli(main))
