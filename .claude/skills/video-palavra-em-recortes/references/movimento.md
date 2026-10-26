# Movimento — tempos medidos e roteiro-tipo

## Medidas da referência (30 qps)

- Cortes nos quadros 0, 1, 4, 8, 11, 14, 18, 21, 24, 27, 30, 34, 37, 40, 43, 46, 50, 53, 56, 57 → recortes de **3 quadros** (às vezes 4). A 150 bpm a semicolcheia é 0,1 s = 3 quadros: os recortes caem na grade da música.
- O quadro 0 é estourado (claro). O último recorte corta seco para o preto; 1 s de silêncio; drop.
- Dentro de cada recorte a imagem continua se movendo (diferença média entre quadros de 1 no começo a ~10 no fim): o empurrão **acelera** ao longo da montagem.
- Zoom acumulado ~1,0 → 1,6×, giro ~0 → −8°, pequenos saltos de posição (±20 px) a cada troca.

## Como a lib reproduz

Por montagem (uma palavra), com `k` = índice do recorte / (n−1) e `u` = progresso dentro do recorte:

```
zoom = lerp(zoom0, zoom1, k^1.25) × (1 + empurra × (1 + 1.8k) × u)     // empurra = .045
giro = lerp(giro0, giro1, k^1.4) ± 1,2° (sorteado)
posição = ±22 px, ±16 px (sorteado por recorte)
vinheta = lerp(.95, .5, k)
```

Cada palavra recomeça do zoom 1 (a montagem "respira" a cada palavra); `RC.frase` inverte o sinal do giro de uma palavra para a outra.

## Roteiro-tipo de frase (150 bpm, 30 qps)

| trecho | tempo | o quê |
|---|---|---|
| palavra 1 | 0,0–1,2 | 9 recortes de 3 quadros + 1 que segura 9 quadros (36 quadros = 3 batidas) |
| palavra 2…n | +1,2 s cada | idem; troca de palavra = pancada grave |
| silêncio | 1 batida (0,4 s) | preto mudo, como na referência |
| drop | início do compasso seguinte | colagem: um recorte por batida (0,4 s) |
| fecho | ~1,4 s parado + fade 0,6 s | a frase inteira na tela |

Fórmula da duração: `n × 1,2 + 0,4 + n × 0,4 + 1,4 + 0,6`. Com 4 palavras = 8,4 s; com 3 = 6,8 s; com 6 = 11,6 s (para 6+ palavras, use `segura: 6` e passo de colagem 0,2 s).

**Uma palavra só** (como a referência): `RC.montagem` com 18 trechos e `quadros` medidos `[1,3,4,3,3,4,3,3,3,3,4,3,3,3,3,4,3,3]`, depois preto e o que vier (título, footage…).

## Tabela T do exemplo

```js
const T = { frase: 0, silencio: 4.8, drop: 5.2, fade: [7.8, 8.38] };
// colagem: de T.drop, passo .4 → 5,2 · 5,6 · 6,0 · 6,4
```

## Entradas e saídas

- Recorte: corte seco (não há transição entre recortes — o corte É o efeito).
- Peça da colagem: "tapa" de stop-motion — escala 1,32 → 1 em 4 degraus em 0,13 s e giro que assenta (1,6× → 1×). Som `tapa` no quadro.
- Fim: fade para o preto de 0,6 s sobre tudo.
- Câmera da colagem: empurrão lento 1 → 1,05 (`sine.inOut`) do drop ao fim.
