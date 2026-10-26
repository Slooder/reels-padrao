# Estilo: texto grifado

Leitura da referência (Klickpin, "19 Trending Side Hustle Ideas for 2026": 16:9, 11,9 s, plano único, áudio mudo, animação a 12 qps) e como ela vira 9:16.

## Sumário
1. As 3 marcas
2. Paleta
3. Tipografia
4. Materiais
5. Composição 9:16
6. O que não fazer

## 1. As 3 marcas

1. **Parágrafo serifado escrito palavra a palavra** — cada palavra brota abaixo da linha e sobe; a câmera persegue o texto com atraso e depois empurra devagar.
2. **Marca-texto amarelo que sangra da borda esquerda da tela** e cresce por trás da primeira frase; no fim, **bloco vermelho** sobre a frase-chave com o texto em branco.
3. **Abertura de colagem editorial** (recorte P&B com contorno amarelo, retícula, título com pincel, rótulo grifado) que sai num chicote horizontal — e o grifo do rótulo é o mesmo que grifa o parágrafo.

## 2. Paleta (medida nos quadros)

| papel | hex | onde |
|---|---|---|
| papel | `#fcfcfc` (p1 243 · p5 247 · p50 252) | fundo inteiro, com manchas fracas e pontinhos |
| tinta | `#363636` | todo texto (o antisserrilhado dá ~#3c3429 na mediana) |
| marca-texto | `#f9ce80` | barra do rótulo e da 1ª frase |
| contorno / pincel | `#f3c069` | contorno do recorte e sublinhado do título |
| destaque | `#dd687a` | bloco da frase-chave, texto branco `#fff` por cima |
| retícula | `#c0c0c0` | bolinhas atrás do recorte |
| crédito | `#7d7a76` | rodapé |

Nada de sombra, vinheta ou grão de filme além do papel: o acabamento é limpo e plano.

## 3. Tipografia

- **Lora Bold (700)** para tudo: título, rótulo, parágrafo e (regular 400) crédito. Serifa de texto com "a" e "g" de dois andares; é o que dá o ar de revista.
- **Mesmo tamanho em tudo** (na referência título, rótulo e parágrafo têm ~22 px em 480): em 9:16 use parágrafo e rótulo `fs 66` e título `fs 72`.
- **Entrelinha 1,36** (`lh = 90` para `fs 66`). Caixa normal, sem tracking.
- **Parágrafo centralizado**, linhas de 18–27 caracteres; a mais longa ocupa ~75–85 % da largura (a ref.: 82 %).
- Crédito: Lora 400, 24 px, centralizado, 46 px acima da borda de baixo.

## 4. Materiais

- **Papel-reboco quase branco** (`tools/grifado.py papel`): manchas cinza muito fracas, nuvens de pontinhos, 4–6 rachaduras de 1 px. Tem de quase sumir: se você "vê" a textura no celular, está forte demais.
- **Marca-texto:** retângulo chapado, cantos retos, sem textura nem transparência, **atrás** do texto; altura = 0,95 × entrelinha (cobre das ascendentes até um pouco abaixo da linha de base). Começa fora da tela, à esquerda.
- **Bloco vermelho:** mesmo retângulo, mesma altura; o texto coberto vira branco (cópia branca da linha recortada pelo bloco).
- **Recorte P&B** (`tools/grifado.py recorte`): preto #09, branco #ef, contraste alto, nitidez local para traço fino não sumir; **contorno amarelo liso de ~15 px** (≈1,4 % da largura) que segue a silhueta com cantos arredondados — não é "tesoura". Vaza pela borda de baixo (e pelos lados, se precisar).
- **Retícula:** grade alternada (hexagonal), passo 30 px, bolinha 45 % do passo, borda roída por ruído (bolinhas inteiras somem; nenhuma cortada ao meio). Fica atrás do recorte e aparece só nos vãos.
- **Sublinhado de pincel:** traço afinado nas pontas, levemente curvo, com um gancho que desce no fim; começa ~0,3 em antes da 1ª letra e passa ~0,2 em da última.

## 5. Composição 9:16

Abertura (mundo x 0–1080, câmera parada em x 540):

| peça | y (px) | observação |
|---|---|---|
| título + pincel | 420–520 | centralizado |
| rótulo, 2 linhas em escada | 617–790 | à direita (x ≈ 560), 2ª linha recuada 80 px e grifada |
| recorte | 925 → vaza embaixo | ~1340 px de largura, assunto principal no terço central |
| retícula | 990–1530 | 2 manchas, nos vãos ao lado do assunto |

Parágrafo (mundo x ≈ 1900): bloco centralizado no meio da tela (`cy ≈ 970`), 1ª linha na **mesma faixa** da linha grifada do rótulo (≈ 700–790, 37–41 % da altura — como na referência).

A referência é horizontal; em 9:16 o parágrafo vira 4–7 linhas curtas (uma ideia por linha) e o rótulo fica acima do assunto, não ao lado.

## 6. O que não fazer

- Fonte sem serifa, itálico ou caixa-alta: some a voz editorial.
- Marca-texto arredondado, "pincelado" ou transparente: na referência ele é um retângulo chapado.
- Palavras entrando com fade, escala ou desfoque: elas aparecem inteiras e só **sobem**.
- Mais de um bloco vermelho, ou vermelho antes do respiro: o vermelho é o fecho.
- Câmera parada no parágrafo: sem o empurrão lento e o atraso da perseguição o vídeo vira slide.
