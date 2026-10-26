#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Números por extenso → algarismos (numeros.py). Só biblioteca padrão; roda em milissegundos."""
import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numeros  # noqa: E402


def frase(s: str) -> str:
    return " ".join(numeros.aplicar(s.split()))


class TestNumeros(unittest.TestCase):
    def test_01_de_um_a_dez_fica_por_extenso(self):
        self.assertEqual(frase("um modelo de três camadas e dez cabeças"), "um modelo de três camadas e dez cabeças")
        self.assertEqual(frase("dois e três são cinco"), "dois e três são cinco")

    def test_02_acima_de_dez_vira_algarismo(self):
        self.assertEqual(frase("doze cabeças e vinte camadas"), "12 cabeças e 20 camadas")
        self.assertEqual(frase("cento e vinte e três trezentos e dois novecentos e noventa e nove"), "123 302 999")

    def test_03_anos_e_milhares(self):
        self.assertEqual(frase("em dois mil e dezessete e em mil novecentos e noventa e oito"), "em 2017 e em 1998")
        self.assertEqual(frase("dois mil e vinte e quatro"), "2024")
        self.assertEqual(frase("cem mil pessoas e duzentos e cinquenta mil reais"), "100.000 pessoas e 250.000 reais")
        self.assertEqual(frase("mil e quinhentos"), "1500")
        self.assertEqual(frase("mil pessoas"), "mil pessoas")              # "mil" sozinho continua por extenso

    def test_04_porcentagem_decimal_e_grandeza(self):
        self.assertEqual(frase("vinte e três por cento"), "23%")
        self.assertEqual(frase("cinco por cento e cem por cento"), "5% e 100%")       # medida: vale mesmo abaixo de dez
        self.assertEqual(frase("três vírgula cinco e zero vírgula vinte e cinco"), "3,5 e 0,25")
        self.assertEqual(frase("três milhões de tokens ou um milhão e meio"), "3 milhões de tokens ou 1 milhão e meio")
        self.assertEqual(frase("tantos por cento"), "tantos por cento")               # "cento" sem número antes não é 100

    def test_05_artigo_nao_vira_um(self):
        self.assertEqual(frase("uma ideia e um artigo"), "uma ideia e um artigo")

    def test_06_pontuacao_ou_pausa_corta_o_numero(self):
        # preso[k] = a palavra k está colada à seguinte; False em "vinte" impede "vinte | e três" de virar 23
        self.assertEqual(numeros.aplicar("vinte e três".split(), [False, True, True]), ["20", "e", "três"])
        self.assertEqual(numeros.aplicar("vinte e três".split(), [True, True, True]), ["23"])

    def test_07_trechos_devolvem_indices_para_manter_a_sincronia(self):
        t = numeros.trechos("ele disse vinte e três por cento hoje".split())
        self.assertEqual(t, [(2, 7, "23%")])

    def test_08_e_numeral(self):
        for w in ("um", "Vinte", "duzentas", "mil", "três"):
            self.assertTrue(numeros.e_numeral(w), w)
        for w in ("milhão", "e", "cento.", "modelo"):
            self.assertFalse(numeros.e_numeral(w), w)


if __name__ == "__main__":
    unittest.main()
