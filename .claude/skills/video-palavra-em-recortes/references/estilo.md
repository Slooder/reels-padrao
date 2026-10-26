# Estilo — palavra em recortes

## As 3 marcas (o que qualquer pessoa reconhece)

1. **A mesma palavra parada no centro, em vários textos diferentes**, trocando a cada 3 quadros.
2. **Lente velha que vai fechando**: zoom e giro acumulando, empurrão que acelera, vinheta oval, aberração cromática, varredura, profundidade de campo.
3. **Voz de fita descendo + clique por recorte, depois 1 batida de preto mudo** antes do drop.

Tudo o mais serve a essas três. Se um recorte "bonito" tira a palavra do centro ou desacelera o ritmo, ele está errado.

## Como a referência é (medida)

- 702×396, 30 qps. Abertura de 1,9 s com 18 recortes: troca a cada 3 quadros (às vezes 4), 1º quadro estourado, corte seco para o preto, 1 s de silêncio.
- Papel creme #DBCFB6 com vincos; texto em geométrica de 'a' de um andar (≈ Outfit), palavra "Recap" semibold preta sobre marca-texto reto #EBC63F.
- Zoom acumulado ~1,6×, giro ~−8°, vinheta oval quase preta que diminui com o zoom, aberração vermelho/ciano, linhas de varredura finas, leve sépia.

## Composição 9:16

- A palavra no **centro exato** (540, 960). A coluna de texto é alinhada à esquerda numa margem comum a todas as linhas da página (como uma matéria de verdade); a margem é calculada para a palavra cair no centro.
- **11 linhas** por página (5 acima, 5 abaixo); com `tam` 165 aparecem ~7, cortadas pelas bordas — é o "macro" da referência. As de fora ficam desfocadas (1,8 px por linha de distância) e mais transparentes.
- Texto corrido: as linhas saem pela direita da tela. Não centralize as linhas, não justifique: tem de parecer uma matéria fotografada de perto.

## Materiais (papel + fontes + tinta)

| material | papel | fontes (corpo/palavra) | tinta | grifos que combinam |
|---|---|---|---|---|
| `creme` (o da referência) | creme envelhecido, vincos | Outfit 400/600 | #1b1c1f | reta, marca amarela, sublinhado e círculo vermelhos |
| `jornal` | cinza-bege com pontinhos | Libre Caslon 400/700 · Playfair 400/800 (cabeçalho maior) | #1e1e1e | marca amarela, círculo/caixa vermelhos, reta |
| `revista` | branco couché com brilho | Archivo 500/800 · Inter Tight · Familjen | #111 | tarja preta, marca rosa, recorte amarelo, reta azul |
| `caderno` | branco com pauta azul e margem vermelha | Caveat · Kalam (caneta azul) | #1F3B8F | círculo e onda vermelhos, marca verde, sublinhado |
| `maquina` | papel de máquina com respingos | Special Elite · Courier Prime | #262626 | sublinhado duplo, caixa, marca, tracejado |
| `kraft` | pardo fibroso | Bebas Neue · Big Shoulders · Anton (CAIXA ALTA) | #1d1309 | recorte branco, carimbo vermelho, tarja |
| `livro` | amarelado, manchas, bordas escuras | Fraunces · Young Serif · DM Serif | #2b2118 | sublinhado e colchetes a lápis, marca laranja, círculo |
| `escuro` | papel preto | Syne · Space Grotesk · Unbounded (texto claro) | #ECE8DF | marca lima, caixa branca, sublinhado/reta amarelos |
| `recibo` | térmico com faixas | VT323 · Space Mono (CAIXA ALTA) | #383838 | tracejado, marca rosa, tarja |
| `postit` | amarelo | Permanent Marker · Reenie Beanie | #1d1d1d | sublinhado e círculo vermelhos, onda azul |
| `rosa` | rosa reciclado com pintas | Dela Gothic · Rubik Mono · Bricolage | #26276a | marca azul, sublinhado azul, reta amarela |

Material novo: `audio/.venv/bin/python tools/papeis.py novo meu_papel --cor 210,190,150` e uma entrada em `RC.MATERIAIS` (veja `receitas.md`).

## Grifos

| grifo | como é | quando usar |
|---|---|---|
| `reta` | bloco chapado atrás (o da referência) | papel claro, "marca-texto limpo" |
| `marca` | marca-texto com bordas irregulares e pontas inclinadas, multiplica com o papel | o mais orgânico |
| `sublinhado` | traço de caneta levemente curvo | caderno, livro, post-it |
| `duplo` | dois traços retos | máquina de escrever, recibo |
| `onda` | sublinhado ondulado | caderno, post-it |
| `circulo` | elipse à mão que passa do ponto de partida (1,1 volta) | o mais "humano"; fica por cima do texto |
| `caixa` | retângulo à mão com cantos que passam | jornal, máquina |
| `tracejado` | caixa tracejada | recibo, máquina |
| `colchete` | [ ] a lápis | livro |
| `tarja` | barra escura e a palavra na cor do papel | revista, kraft, recibo (impacto) |
| `recorte` | pedaço de papel recortado com a palavra, girado, com sombra | kraft, revista (o "paper cut" literal) |
| `carimbo` | caixa vermelha gasta (filtro de ruído), palavra vermelha | kraft |

Cores (`RC.CORES`): amarelo #F2CD3B · rosa #FF86B8 · verde #A6E86A · laranja #FFAE45 · azul #8FD0FF · lima #D9F24A · vermelho #D7262E · caneta #1F3B8F · lápis #5a5650 · preto #121212 · branco #F4F1EA. Escreva `tipo:cor` (`'marca:rosa'`, `'circulo:vermelho'`) ou um hex (`'reta:#ffd400'`).

## Lente (acabamento do palco)

- Vinheta oval `ellipse 78% 60%`: opacidade nas bordas de .95 (1º recorte) a .5 (último) — `vinheta: [.95, .5]`.
- Aberração cromática em todo texto: sombra vermelha à esquerda e ciano à direita, 4 px no centro, +1,5 px por linha de distância.
- Linhas de varredura: listras de 2 px a cada 6 px, 10% de escuro (`RC.palco(pai, {varredura:false})` desliga).
- Sépia .16 + contraste 1,06 nos papéis claros; papel escuro só contraste.
- 1º quadro de cada palavra estourado (flash branco a 55%) — `estouro: false` desliga.

## Colagem final (bilhete de recortes)

Fundo de papel escuro com varredura e vinheta; cada palavra num pedaço do mesmo papel/fonte/grifo da página que segurou, com borda recortada à tesoura (polígono com dentes), giro de ±2–5°, sombra projetada, empilhados no centro com deslocamentos laterais. Entram com "tapa" de stop-motion (escala 1,32 → 1 em 4 degraus em 0,13 s).
