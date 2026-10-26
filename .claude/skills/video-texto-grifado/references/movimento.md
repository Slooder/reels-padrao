# Movimento: tempos, eases e ritmo

Tudo medido quadro a quadro na referência (24 qps com animação a 12 qps) e comprimido para 8 s mantendo a proporção.

## Sumário
1. Roteiro-tipo (tabela T)
2. Escrita palavra a palavra
3. Câmera: chicote, perseguição e empurrão
4. Marca-texto: rótulo → borda → verso
5. Bloco vermelho
6. 12 qps
7. Durações diferentes

## 1. Roteiro-tipo (tabela T)

| fase | ref (12 s) | demo (8 s) | o que acontece |
|---|---|---|---|
| abertura parada | 0–0,50 | 0–0,55 | tudo já está na tela no quadro 0 (nada entra) |
| grifo do rótulo | 0,45–0,80 | 0,25–0,60 | barra cresce atrás da 2ª linha do rótulo |
| chicote | 0,50–1,30 | 0,55–1,30 | câmera acelera para a direita e freia no parágrafo |
| escrita | 0,75–3,30 | 0,85–3,50 | ~10 palavras/s; começa *antes* do chicote acabar |
| grifo do verso 1 | 1,25–3,00 | 1,30–2,60 | a ponta da barra percorre a 1ª linha, devagar e constante |
| respiro | 3,30–9,70 | 3,50–5,30 | só o empurrão lento |
| bloco vermelho | 9,75–10,80 | 5,30–6,25 | cresce sobre a frase-chave, texto vira branco |
| segura + crédito | 10,8–11,9 | 6,25–8,00 | crédito entra em 0,3 s em 6,40 |

```js
const T = { rotulo:[.25,.60], chicote:[.55,1.30], escreve:.85, verso1:[1.30,2.60], zoom:[1.0,8.0,1,1.07], vermelho:5.30, credito:6.40 };
```

Regra de proporção: abertura ≈ 7 %, chicote ≈ 9 %, escrita ≈ 30 %, respiro ≈ 25 %, vermelho ≈ 12 %, segura ≈ 20 %.

## 2. Escrita palavra a palavra (`GR.escrever` + `GR.palavras`)

- Cada palavra aparece **opaca e inteira** 0,8 em abaixo da linha e sobe até ela em **0,25 s, `power2.out`** (na ref.: 18 px de 22 px de corpo no 1º quadro visível, assentada em 3 quadros de 12 qps).
- Ritmo: `pps` 10,5 palavras/s em média; cada palavra dura `(0,62 + 0,055·letras)/pps`; +0,7/pps depois de vírgula/ponto-e-vírgula, +1,1/pps depois de ponto, +0,25/pps na troca de linha.
- As palavras novas ficam visivelmente mais baixas que as anteriores por 2–3 palavras: é esse "degrau" que dá a sensação de escrita.

## 3. Câmera (`GR.chicote`, `GR.seguir`, empurrão)

```js
const cam = t => ({
  x: K.lerp(540, seguir(t), GR.chicote(K.seg(t, ...T.chicote))),   // abertura → perseguição
  y: 960,                                                         // sem movimento vertical
  z: K.lerp(1, 1.07, K.seg(t, 1.0, 8.0)),                         // empurrão lento, linear
});
```

- **Chicote:** aceleração longa `u^2,6` até 82 % do tempo e freada curta `power3.out`, com a velocidade casada no corte. Medido na ref.: 3 → 11 → 25 → 48 → 83 → 136 → 218 px a cada 1/12 s, ~2 500 px/s no pico (em 852 px de largura).
- **Perseguição:** o alvo é o centro horizontal das palavras já escritas, puxado 25 % para a última palavra (`cursor`), filtrado com atraso de 1ª ordem `tau .34 s`. Na ref. a 1ª linha anda de x=324 → 75 ao longo de 2 s.
- **Empurrão:** 1 → 1,07 entre 1,0 s e o fim (≈1 %/s; ref.: 1 → 1,085 em 9,4 s), em torno do centro da tela.
- **Sem câmera vertical** e sem empurrão durante a abertura.

## 4. Marca-texto: rótulo → borda → verso (`GR.marca`)

Uma barra só, três fases:

1. `[a0, a1]` cresce linear atrás da linha do rótulo (começa 1,5 em antes da palavra).
2. Depois de `a1`: a ponta esquerda fica presa ao mundo até a borda da tela passar por ela — aí gruda na borda (`telaEsq − 40`). A ponta direita desliza do rótulo até o início do verso (`power2.in`), mas nunca fica menor que um **toco de 20 % da largura da tela** (na ref.: 173–187 px de 852).
3. `[b0, b1]` a ponta direita percorre o verso, `ease 'none'` (ref.: ~220 px/s em 852).

O toco termina mais ou menos onde começa a 1ª palavra (porque a câmera centraliza a linha): a barra parece "esperar" o texto chegar.

## 5. Bloco vermelho (`GR.destaque`)

- Cresce da esquerda para a direita em **0,95 s, `power2.inOut`** (ref.: 1,05 s; 346 → 365 px nos primeiros 0,2 s, ~1 000 px/s no meio, assenta devagar).
- Cobre só a frase-chave (na ref. a 2ª metade da última linha; no demo "reúne a feira inteira.", deixando o "e" de fora).
- O texto coberto vira branco exatamente na borda do bloco (mesma `clip-path`).

## 6. 12 qps

A referência só muda de imagem a cada 2 quadros. `GR.q(t)` quantiza o tempo de tudo (câmera, palavras, grifos) em degraus de 1/12 s; o render continua a 24 qps. No chicote os saltos de 100–200 px por degrau são parte do visual. `GR.qps = 0` deixa liso.

## 7. Durações diferentes

- 6 s: abertura 0–0,4, chicote 0,4–1,0, escrita até ~2,7 (≤ 18 palavras), respiro até 3,9, vermelho 3,9–4,7, segura até 6.
- 10–12 s: mantenha abertura e chicote (≈ 1,3 s), aumente o respiro (é ele que dá tempo de leitura) e o parágrafo até ~30 palavras.
- Nunca encurte o respiro abaixo de ~1,5 s: o espectador lê ali.
