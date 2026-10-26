# Estilo: editorial recortado

Leitura da referência (editorial em fundo branco, 16:9, 9,6 s, plano único) e como ela vira 9:16.

## As 3 marcas

1. **Recorte P&B com borda azul-ardósia cortada a tesoura** sobre papel quase branco, com retícula de bolinhas cinza atrás.
2. **Título serifado com sublinhado de pincel azul** no topo; subtítulo que sobe palavra a palavra.
3. **Etiquetas coral que se montam**: traço → faixa que cresce; palavras pretas soltas ao redor pulam uma a uma para dentro e ficam brancas.

Tudo o que você fizer tem de servir a essas três. Se uma cena nova não tem nenhuma delas, ela não é deste estilo.

## Paleta

| papel | hex | variável CSS (`lib/editorial.js`) |
|---|---|---|
| fundo (papel/reboco claro) | `#f5f5f3`, pontinhos cinza `#e0e0dd` | — (textura `editorial.py papel`) |
| texto (título, subtítulo, palavras soltas) | `#2a2a2a` | `--ed-tinta` |
| borda dos recortes | `#5b7ba3` | `--ed-azul` (e `--cor` no `editorial.py`) |
| miolo do sublinhado | `#2f4560` | `--ed-azul-escuro` |
| faixa das etiquetas | `#e0646b` · texto `#ffffff` | `--ed-coral` |
| retícula | `#c9c9c9` | `--ed-pontos` |
| foto | P&B, pretos `#0b`, brancos no máximo `#e1` | — |

Só essas cores. Nada de gradiente colorido, sombra projetada ou brilho.

## Tipografia

- **Lora Bold (700)** para tudo: título, subtítulo, etiquetas. É uma serifa de texto de contraste médio, com "g" de dois andares; a referência usa exatamente essa família.
- Tamanhos em 9:16 (1080×1920):

| peça | tamanho | onde |
|---|---|---|
| título | 86 px (≈4,5% da altura), encolhe para caber em 960 px | centralizado, topo final em y≈168 |
| subtítulo | 60 px (≈¾ do título) | centralizado, logo abaixo (y≈312) |
| etiqueta | 47 px, faixa com 1,42× de altura e ⅓ em de respiro nas pontas | perto da parte que nomeia |
| crédito | Inter Tight 500, 15 px, branco com sombra | rodapé |

- Caixa alta e baixa, sem caixa-alta inteira. Citações entre aspas curvas “ ”.
- O sublinhado fica **atrás** das letras, na linha de base (as descendentes passam por cima), começa um pouco antes da primeira letra e passa ~½ em da última, terminando redondo.

## Materiais

- **Papel:** quase branco com nuvens de pontinhos cinza de 1–3 px (fotocópia de parede) e manchas muito suaves. Gere com `tools/editorial.py papel`.
- **Retícula:** bolinhas cinza de raio 7 px em grade alternada a cada 26 px, em manchas retangulares de ~270×210 px, parcialmente escondidas atrás do recorte. 2–3 manchas por vídeo.
- **Recorte:** foto real convertida em P&B de alto contraste com grão fino; por trás, a borda de papel azul de ~15 px com espessura que varia ±25% e contorno em segmentos retos (cantos vivos, "corta caminho" nas reentrâncias). Gere com `tools/editorial.py recorte`.
- Sem vinheta, sem grão animado, sem tremor: o acabamento é de impressão limpa.

## Composição 9:16

A referência é horizontal: um skyline largo ocupando os 70% de baixo e o título no topo. Em 9:16 **recomponha**, não estique:

- **Faixas verticais:** título + subtítulo nos 20% de cima; um respiro de ~80 px; o aglomerado de recortes dos ~32% até a base, vazando pela borda inferior.
- **Aglomerado único:** empilhe 2–4 recortes em profundidade (trás → frente) para fazer um "skyline" alto. O mais alto no terço central-esquerdo ou central; uma peça larga na frente, embaixo, escondendo as bases retas das peças de trás. Peças podem vazar pelas laterais.
- **Retícula nos vãos:** onde sobrar papel entre peças (cantos embaixo, ao lado das torres), ponha uma mancha de retícula — é o que a referência faz atrás do skyline.
- **Etiquetas no céu:** alterne esquerda/direita descendo pela tela, cada uma encostada na parte que nomeia (acima, ao lado ou por cima da foto). A longa vai no alto, perto do subtítulo; as curtas descem pelo aglomerado. Margem mínima de 40 px das bordas.
- Exemplo (Brasília): Congresso (torres + prato da Câmara) atrás, `w:1150` em `(70,590)`; cúpula do Senado `w:470` em `(-78,1352)`; Catedral na frente `w:1370` em `(-130,1212)`, vazando pela base; retículas em `(-10,540)`, `(822,930)` e `(-10,1480)`.
