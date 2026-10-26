# 04 · Inserts

## Regras gerais

- **Poucos e com função**: um insert só quando ilustra literalmente o que a pessoa diz naquele segundo. Depois do clímax
  (no 104, o versículo) não entra mais nada: a pessoa fala até o fim.
- **Curtos**: o mapa de 8 s "ficou muito tempo"; card de 18 s em cima "ficou muito tempo". Passagem de assunto ≈ 3 s; dado ≈ 4 s;
  vídeo de terceiro ≈ 2–5 s; tela dividida ≈ 6–7 s.
- **Limpos**: sem sombra projetada, sem zoom em foto (a capa/foto aparece parada), 2D (nada de mapa 3D), sem moldura enfeitada.
- **Mesma entrada e saída em todos** (pedido do dono, referência "Dreamy digital product…" aos 0:07): a janela nasce como uma
  faixa arredondada no meio (62 % da largura × 14 % da altura) e cresce até o tamanho final; na saída faz o caminho de volta.
  - entrada 0,55 s, curva `bezier(0.25, 1, 0.5, 1)`; saída 0,4 s, curva `bezier(0.5, 0, 0.75, 0)`; feito com `clip-path: inset(... round r)`.
  - Componente `Janela` em `insertos.tsx` (vale para card, tela cheia e metade da tela dividida).
- Cortes dentro de um insert (trocar de pessoa, trocar de print) são **secos**.
- Material de terceiro (vídeo de outro canal, print, foto): sem som, crédito/licença anotado em `broll/`.

## Tipos (dados em `plano.py → EVENTOS`)

| tipo | como é | exemplo no 104 |
|---|---|---|
| `janela` | card 16:9 de 760×428 no topo (x 160, y 120), cantos 28 px; a pessoa desce enquanto ele está aberto | capa do vídeo do Felca, parada |
| `tela` | tela cheia, sem a pessoa e sem a legenda | prints, mapa, ranking, Nikolas, nordestinos, versículo |
| `dividida` | outra pessoa na metade de cima (1080×960), quem fala na metade de baixo (a base desce 540 px junto com a janela) | a senhora |

## Receitas aprovadas

**Prints de comentários** — fundo escuro liso (`#0E0D0B`), um print por vez, 1020 px de largura, centro em y 860, cantos 18 px,
troca com fade curto (entra 0,18 s, sai 0,12 s), sem desfocar o print e sem animação extra ("o mais simples possível").

**Mapa de região (passagem de assunto, ~3 s)** — vetor 2D da região como **uma forma só** (sem divisa de estados nem capitais),
gerado da malha do IBGE por `mapa_nordeste.py` (as divisas internas se cancelam; ilhas oceânicas fora). Fundo cinza radial
(como a referência `MAPA NORDESTE.jpg`), forma branca `#F4F4F4`. Animação: o contorno se desenha (0,9 s), a forma se preenche,
o nome da região aparece **centralizado dentro da forma** (Helvetica Bold 86 px, `#231F1A`, opacidade + desfoque), aproximação lenta 0,94 → 1,02.

**Dado (ranking, ~4 s)** — mesmo fundo cinza do mapa; título grande (Helvetica Bold 78 px), subtítulo, as linhas entram uma a uma
(0,09 s de intervalo) com selo vermelho da posição (`#C8102E`, como o g1), nome + UF, **barra branca que cresce do zero** e o valor;
no fim um chapéu vermelho em caixa alta com a conclusão ("AS 10 PRIMEIRAS SÃO DO NORDESTE") e a fonte em letra pequena. Texto
entra só por opacidade e desfoque.

**Vídeo de terceiro com a pessoa citada (~4–5 s)** — entra numa janelinha 9:16 à direita (330 px, x 690, y 230), abre para a
tela toda, fica ~3 s e volta para a janelinha antes de sair. Mostrar o **começo** do vídeo dele, sem som.

**Pessoas de um vídeo (depoimentos)** — **tela cheia, enquadramento igual para todas**: rosto a 36 % da altura, zoom 1,2 centrado
no rosto (medido com YuNet), corpo até o joelho. ~2,3 s por pessoa, cortes secos. Card 16:9 em cima cortava as pessoas ("só a
cabeça") e foi reprovado. A legenda queimada do vídeo deles aparece; a nossa some nesse trecho.

**Tela dividida** — a outra pessoa em cima (recorte com cabeça e ombros, sem a legenda queimada dela), quem fala embaixo com o rosto
no meio da metade; a legenda na emenda.

**Versículo / citação** — fundo escuro (radial `#1C1A17` → `#0E0D0B`), referência em caixa alta pequena (Helvetica Bold 34 px,
`#D9D4CA`, espaçada) e o texto serifado (Newsreader 700, 78 px, `#E6DAC0`) **centralizado na tela**; as palavras-chave acendem em
amarelo `#F2D24B` quando são ditas. Palavra com hífen não quebra na linha. Fundo branco/papel foi reprovado ("muito branco").

## O que foi reprovado

Colagem animada de prints; mapa 3D com manchas e câmera; foto com zoom e sombra; insert de foto queimando; recapitulação de
inserts já vistos; card longo em cima com recorte que corta as pessoas; animações das skills da crIAbr em geral.
