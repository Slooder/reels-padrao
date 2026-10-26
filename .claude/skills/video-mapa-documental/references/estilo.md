# Estilo — mapa documental

Leitura de uma referência de documentário histórico (16:9, 23 s, um plano contínuo) e como ela vira 9:16.

## As 3 marcas (o que qualquer pessoa reconhece)

1. **Mapa escuro de satélite sobre papel cinza quadriculado com vinheta.** O país em foco acende verde-esmeralda, com bordas brancas brilhantes e rios/lagos acesos; o resto da terra é cinza-escuro.
2. **Região vermelha translúcida de borda macia** que acende piscando, se espalha e se fecha numa área, marcada por um **triângulo vermelho sólido com texto branco black**.
3. **Anotações de documentário** sobre um **mergulho de câmera sem cortes**: chamadas com cotovelo e rótulo que se decodifica, retrato P&B em círculo, círculo tracejado que encolhe girando.

Se uma decisão não serve a essas 3 coisas, corte.

## Paleta (medida na referência)

| papel | hex / valor | onde |
|---|---|---|
| papel (oceano) | `#5d5e5a` + luz difusa branca 20% no centro-direita | fundo de tudo fora da terra |
| grade | `rgba(214,214,206,.16)`, 1,4 px | quadradinhos no papel |
| terra apagada | rampa `#0e0f0e → #2e2f2d → #62645f` | textura de satélite cinza |
| país aceso | rampa `#000a05 → #032c1c → #18704c` (média medida ≈ `#073624`) | textura verde |
| rios e lagos | `rgba(78,228,176,.95)` com brilho | só dentro do país aceso |
| bordas | `rgba(232,238,232,.82)` + brilho branco 9 px | estados/províncias e contorno |
| vermelho | rampa `#5c0c04 → #c02410 → #f4623a`, opacidade .9 | região (média medida ≈ `#a02e15`) |
| triângulo | gradiente `#ff3a22 → #e01e12` + halo vermelho | marcador |
| texto | `#ffffff` com brilho branco (6 px + 18 px) | rótulos e triângulo |
| etiqueta | pílula `rgba(104,178,148,.34)`, texto `#d4ece1` | nomes de estados |
| cidade | `#38e3a6` negrito com brilho verde | nomes de cidades |

As rampas estão em `tools/mapa.py` (`MAT`). Para outra "cor de país" (ex.: azul-petróleo), mude a rampa `verde` e a cor `AGUA`, não o CSS.

## Tipografia

- **Destaques** (triângulo, chamadas, legenda do retrato): **Montserrat** 800–900, caixa-alta, espaçamento .03–.06 em, branco com brilho. A referência usa uma geométrica tipo Gotham; Montserrat é a mais próxima livre.
  - triângulo: 62–70 px, 1 palavra curta (ou 2 linhas curtas);
  - chamada: 1ª linha 40–54 px, 2ª linha 72% dela;
  - legenda do retrato: 25 px, 2 linhas.
- **Mapa** (etiquetas e cidades): **Noto Sans** 500/700 (humanista larga, como a Verdana dos mapas). Etiqueta 29 px; cidade 25 px.
- Fontes em `lib/fonts.css` (só o subconjunto latino, cobre acentos do pt-BR).

## Materiais e acabamento

- Textura real de relevo (NASA Blue Marble + ASTER) tingida em 3 materiais: cinza, verde, vermelho. O relevo aparece por baixo do vermelho — é isso que faz parecer "mapa de satélite pintado", não forma chapada.
- Bordas e rios com `shadowBlur` (bloom). Contorno do país um pouco mais grosso.
- Vinheta elíptica pesada (cantos ~86% preto) acima do mapa e abaixo das anotações.
- Grão leve (7%, overlay).
- Sombra difusa preta sob a terra (18 px) para descolar do papel.

## Composição 9:16

- **Recomponha**: o "caminho" da história vai na vertical (origem em cima, destino embaixo, ou o contrário). Ex.: o café desce de Belém ao Sudeste quase na mesma longitude.
- Abertura: continente inteiro, país ~45% da largura.
- Mapa do país: país ocupando a largura toda (z ≈ 50–55 px/grau para um país do tamanho do Brasil).
- Final: região vermelha com ~45% da largura, centro em ~55% da altura; triângulo de 260–300 px; círculo tracejado com diâmetro ≈ 70–75% da largura; chamada 1 abaixo/ao lado da região, chamada 2 acima e **fora** do círculo; créditos no rodapé.
- Margem lateral mínima de 40 px para textos. Etiquetas podem sair cortadas na borda (como na referência); rótulos não.

## O que evitar

- Cortes secos: o estilo é um plano só; a "edição" é a câmera.
- Fade comum para acender: tudo acende **piscando** (`MD.pisca`).
- Vermelho opaco chapado (perde o relevo) ou bordas duras nas manchas.
- Texto em cima do triângulo/círculo de outra anotação.
- Logos, pessoas reais da referência, fotos sem licença livre. Créditos de CC BY/BY-SA no rodapé.
