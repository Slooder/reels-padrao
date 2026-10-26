#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""numeros.py — números ditos por extenso → algarismos, para legenda ("vinte e três por cento" → "23%").

Só biblioteca padrão. Não decide tempo: devolve TRECHOS (índice inicial, índice final, texto novo) e quem chama
funde as palavras do trecho guardando o início da primeira e o fim da última — a sincronia não se perde.

Regra de estilo (Netflix, guia de português do Brasil, lido em 2026-10-07): de um a dez por extenso, acima de dez
em algarismos. Por isso "três modelos" fica como está e "doze modelos" vira "12 modelos". Número pequeno só vira
algarismo quando faz parte de uma medida: "cinco por cento" → "5%", "três milhões" → "3 milhões",
"dois vírgula cinco" → "2,5". "um" e "uma" sozinhos nunca viram "1": quase sempre são artigo.

    >>> aplicar("ele disse vinte e três por cento em dois mil e vinte e quatro".split())
    ['ele', 'disse', '23%', 'em', '2024']
"""
from __future__ import annotations

import sys
import unicodedata

sys.dont_write_bytecode = True

UNIDADES = {"zero": 0, "um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "quatro": 4, "cinco": 5, "seis": 6, "sete": 7,
            "oito": 8, "nove": 9}
DEZ_A_DEZENOVE = {"dez": 10, "onze": 11, "doze": 12, "treze": 13, "catorze": 14, "quatorze": 14, "quinze": 15, "dezesseis": 16,
                  "dezessete": 17, "dezoito": 18, "dezenove": 19}
DEZENAS = {"vinte": 20, "trinta": 30, "quarenta": 40, "cinquenta": 50, "sessenta": 60, "setenta": 70, "oitenta": 80, "noventa": 90}
CENTENAS = {"cem": 100, "cento": 100, "duzentos": 200, "duzentas": 200, "trezentos": 300, "trezentas": 300,
            "quatrocentos": 400, "quatrocentas": 400, "quinhentos": 500, "quinhentas": 500, "seiscentos": 600,
            "seiscentas": 600, "setecentos": 700, "setecentas": 700, "oitocentos": 800, "oitocentas": 800,
            "novecentos": 900, "novecentas": 900}
MAGNITUDES = {"milhao", "milhoes", "bilhao", "bilhoes", "trilhao", "trilhoes"}
LIMITE_POR_EXTENSO = 10          # de um a dez por extenso; acima, algarismo


def _chave(s: str) -> str:
    s = "".join(c for c in unicodedata.normalize("NFKD", str(s)) if not unicodedata.combining(c))
    return s.casefold().strip()


def e_numeral(palavra: str) -> bool:
    """A palavra é um numeral por extenso (um, vinte, duzentos, mil…)? Serve à segmentação: numeral não se separa
    do que ele conta."""
    k = _chave(palavra)
    return k in UNIDADES or k in DEZ_A_DEZENOVE or k in DEZENAS or k in CENTENAS or k == "mil"


def _grupo(tok: list[str], i: int, preso: list[bool]) -> tuple[int, int] | None:
    """Número de 0 a 999 a partir de tok[i]: (valor, índice depois do último token) ou None.
    `preso[k]` = o token k está colado ao seguinte (sem pontuação nem pausa entre eles)."""
    n = len(tok)
    if i >= n:
        return None
    j, v = i, 0

    def liga(k: int) -> bool:                       # "… e <resto>" depois do token k−1
        return k + 1 < n and tok[k] == "e" and preso[k - 1] and preso[k]

    if tok[j] in CENTENAS:
        v, exato = CENTENAS[tok[j]], tok[j] == "cem"
        j += 1
        if exato or not liga(j):
            return v, j
        prox = tok[j + 1]
        if prox in DEZ_A_DEZENOVE:
            return v + DEZ_A_DEZENOVE[prox], j + 2
        if prox in DEZENAS:
            v, j = v + DEZENAS[prox], j + 2
            if liga(j) and tok[j + 1] in UNIDADES and UNIDADES[tok[j + 1]] > 0:
                return v + UNIDADES[tok[j + 1]], j + 2
            return v, j
        if prox in UNIDADES and UNIDADES[prox] > 0:
            return v + UNIDADES[prox], j + 2
        return v, j
    if tok[j] in DEZENAS:
        v, j = DEZENAS[tok[j]], j + 1
        if liga(j) and tok[j + 1] in UNIDADES and UNIDADES[tok[j + 1]] > 0:
            return v + UNIDADES[tok[j + 1]], j + 2
        return v, j
    if tok[j] in DEZ_A_DEZENOVE:
        return DEZ_A_DEZENOVE[tok[j]], j + 1
    if tok[j] in UNIDADES:
        return UNIDADES[tok[j]], j + 1
    return None


def _numero(tok: list[str], i: int, preso: list[bool]) -> tuple[int, int, int] | None:
    """Número inteiro a partir de tok[i]: (valor, índice depois do último token, quantos tokens de número) ou None.
    "mil" sozinho não é convertido aqui (fica "mil"); "dois mil e vinte e quatro" → 2024; "cem mil" → 100000."""
    n = len(tok)
    g = _grupo(tok, i, preso)
    j = g[1] if g else i
    if j < n and tok[j] == "mil" and (g is None or preso[j - 1]):
        if g is not None and g[0] == 0:
            return g[0], g[1], g[1] - i
        milhares = g[0] if g else 1
        j += 1
        resto, fim = 0, j
        if preso[j - 1] and j < n:
            if tok[j] == "e" and preso[j]:
                r = _grupo(tok, j + 1, preso)
                if r:
                    resto, fim = r
            elif tok[j] in CENTENAS:
                r = _grupo(tok, j, preso)
                if r:
                    resto, fim = r
        if g is None and resto == 0:
            return None                              # "mil" sozinho continua "mil"
        return milhares * 1000 + resto, fim, fim - i
    if g is None:
        return None
    return g[0], g[1], g[1] - i


def _escrever(valor: int) -> str:
    """1000–9999 sem separador (serve a ano e a quantia); de 10.000 em diante com ponto de milhar."""
    if valor < 10000:
        return str(valor)
    return f"{valor:,}".replace(",", ".")


def trechos(palavras: list[str], preso: list[bool] | None = None) -> list[tuple[int, int, str]]:
    """Trechos a trocar: [(i0, i1, texto)] — as palavras i0…i1−1 viram UMA palavra `texto`. Sem sobreposição, em ordem.
    `preso[k]` False impede que um número atravesse a fronteira entre k e k+1 (vírgula, ponto, pausa)."""
    tok = [_chave(p) for p in palavras]
    n = len(tok)
    preso = list(preso) if preso is not None else [True] * n
    preso += [True] * (n - len(preso))
    saida, i = [], 0
    while i < n:
        num = None if (tok[i] == "cento" and i > 0 and tok[i - 1] == "por") else _numero(tok, i, preso)
        if num is None:                              # ("tantos por cento": o "cento" não é o número 100)
            i += 1
            continue
        valor, j, qtd = num
        # vale trocar quando o número tem mais de uma palavra ("vinte e três") ou passa de dez ("doze")
        texto, fim, forte = _escrever(valor), j, qtd >= 2 or valor > LIMITE_POR_EXTENSO
        # decimal: "três vírgula cinco" → 3,5 ; "zero vírgula vinte e cinco" → 0,25
        if j + 1 < n and tok[j] == "virgula" and preso[j - 1] and preso[j]:
            dec = _grupo(tok, j + 1, preso)
            if dec:
                texto, fim, forte = f"{texto},{dec[0]}", dec[1], True
        if fim + 1 < n and tok[fim] == "por" and tok[fim + 1] == "cento" and preso[fim - 1] and preso[fim]:
            texto, fim, forte = texto + "%", fim + 2, True          # "cinco por cento" → 5%
        elif fim < n and tok[fim] in MAGNITUDES and preso[fim - 1]:
            forte = True                             # "três milhões" → "3 milhões" (a grandeza continua por extenso)
        if forte:
            saida.append((i, fim, texto))
        i = max(fim, i + 1)
    return saida


def aplicar(palavras: list[str], preso: list[bool] | None = None) -> list[str]:
    """As palavras com os números trocados (para teste e uso simples; cues.py usa trechos() para manter os tempos)."""
    saida, i = [], 0
    for i0, i1, texto in trechos(palavras, preso):
        saida += palavras[i:i0] + [texto]
        i = i1
    return saida + palavras[i:]


if __name__ == "__main__":
    print(" ".join(aplicar(sys.argv[1:])) if len(sys.argv) > 1 else __doc__)
