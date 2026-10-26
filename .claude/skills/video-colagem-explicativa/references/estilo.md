# Estilo — colagem explicativa

Leitura de uma referência de 78 s (explainer de reciclagem em 16:9, narração + trilha corporativa): o mesmo papel cinza do começo ao fim, cenas que se montam peça a peça e quase nenhum texto. Aqui está o que copiar e por quê.

## As 3 marcas

1. **Papel cinza reciclado vazio.** Fundo único `#dbdbdb` com fibras curtas e pintinhas, sem vinheta nem moldura. A textura do papel troca de posição em intervalos irregulares de 2–12 quadros (≈ 4 vezes por segundo), com brilho entre 0,985 e 1,015: é o que dá vida a uma cena parada. `CE.papel` faz isso.
2. **Três materiais na mesma colagem.** É a mistura que diz "colagem explicativa", não um material só:
   - **pessoas e veículos**: foto P&B contrastada, recortada, com **borda branca grossa** (≈ 10 px em 1080 de largura) e sombra curta e suave;
   - **lugares e coisas**: foto **colorida** recortada **sem borda** (prédio, galpão, cidade, monte, fardo, fogo);
   - **ícones vetoriais chapados com grão de papel**: planeta, lixeiras, pinheiros com riscos brancos, sol de raios tracejados, objetos com contorno branco (latas, aparelhos); e **manchas de tinta** de borda irregular (retângulo, semicírculo, quadradinhos), **grade branca fina** e **círculo tracejado**.
3. **A cena se monta peça a peça em stop-motion de 12 qps.** Cada pose dura 2–3 quadros (a 30 qps). As peças sobem de baixo, crescem de um ponto do chão, pipocam em anel, caem. Depois de montada, a cena quase não se mexe.

## Paleta (medida na referência)

| uso | hex |
|---|---|
| papel | `#dbdbdb` (varia 217–222 de luminância) |
| letreiro | `#3aa845` (verde) · linha de baixo `#1d1d1d` |
| planeta | oceano `#2a99da` · terra `#a4f269` (verde-limão) · aro branco |
| lixeira da referência | `#9be22f` (verde-limão). No Brasil, metal = **amarelo** `#f6c431` |
| verde-água | semicírculo `#94b3af` · mancha retangular `#5a887d` · pinheiro verde `#2f5e50` |
| pinheiros escuros | `#2b2b2b` e `#454545` com riscos brancos a 50% |
| sol | `#f7c531` |
| manchinhas | ocre `#f4c55c` · azul `#3a9ad9` · círculo tracejado `#6aa88a` |

Tudo em `CE.COR`.

## Tipografia

- **Poppins** (OFL, vem na skill). Letreiro: SemiBold 600, caixa-alta, verde, ~70 px (3,6% da altura). Linha de baixo: Regular 400, caixa-baixa, quase preto, ~40 px.
- Centralizado no topo (y ≈ 236). Uma frase por cena. Sem caixas, sem fundo, sem sombra.
- Entra **grande e encolhe** até o tamanho (escala 2,2 → 1 em 3 degraus, 0,2 s); a linha de baixo vem 0,12 s depois.

## Composição 9:16

A referência é horizontal; em 9:16 recomponha, não corte:

- letreiro no terço de cima, assunto centrado em y ≈ 1000–1500;
- o anel em volta do planeta vira **elipse alta** (RX ≈ 450, RY ≈ 560) para ocupar a altura;
- cenário de ícones (lixeiras entre pinheiros): pinheiros saindo pelas bordas, lixeiras ao centro com a do meio na frente e maior;
- pessoa P&B: pés no chão em y ≈ 1600, semicírculo atrás com a base na altura do joelho, pinheiros verdes saindo de trás;
- faixa de cidade/monte encostada na base (≈ 27% da altura) e o resto em cima, no "céu" de papel;
- deixe respiro: um terço do quadro vazio é normal neste estilo.

## Cenas-tipo (escolha 4–6)

| cena | peças | entradas |
|---|---|---|
| **planeta + anel** | planeta chapado (`CE.planeta`), 12 objetos + 6 miúdos em elipse | planeta sobe; objetos pipocam a cada 0,055 s alternando lados; anel gira 4°/s |
| **cenário de ícones** | 3 lixeiras (`CE.lixeira`), 4 pinheiros (`CE.pinheiro`), objetos espiando pela boca | tudo sobe junto; objetos caem dentro e a lixeira amassa |
| **pessoa diante do semicírculo** | `CE.mancha({forma:'semi'})`, pinheiros verdes, foto P&B com borda | pessoa cresce dos pés; objetos pipocam em cima do que ela carrega |
| **foto em mancha com grade** | `CE.mancha` retangular, `CE.grade`, foto P&B sem borda com base desbotada, acento colorido (fogo, brilho) | grade se traça; foto sobe; acento acende e tremula; objeto colorido cresce ao lado |
| **sol + faixa** | `CE.sol`, faixa de cidade (foto colorida), objeto-herói, `CE.anel`, manchinhas | faixa sobe; sol pipoca e os raios giram; herói cai e quica; anel e manchinhas pipocam |

Outras da referência que cabem: balança com dois pesos, gráfico de linha branca em zigue-zague sobre grade, mãos (foto) segurando um objeto, galpão + sacos, notas de dinheiro.

## O que NÃO fazer

- Câmera que empurra, parallax, vinheta, grão de filme, aberração: a referência não tem.
- Fotos coloridas de pessoas, ou borda branca em lugares: quebra a regra dos materiais.
- Movimento liso nas entradas: tem de ser em degraus (12 qps). Só o pan e as rotações lentas são lisas.
- Muito texto: uma frase curta por cena.
- Logos e marcas (a referência termina num logo; aqui termina no objeto-herói + crédito).
