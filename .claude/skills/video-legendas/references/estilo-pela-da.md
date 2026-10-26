# A aparência da legenda é da direção de arte

`legendar.py` não tem opção de cor, fonte, tamanho, posição nem animação. Tudo o que se vê vem de tokens do `da/da.json` do projeto, lidos pelo kit. Mudar a aparência é mudar a DA — e isso muda **todas** as legendas do projeto de uma vez, que é o objetivo.

## Caminho de qualquer mudança

```bash
"$CRIABR_SKILLS"/video-direcao-de-arte/kit/bin/da token legenda          # o bloco como está
"$CRIABR_SKILLS"/video-direcao-de-arte/kit/bin/da revisar                # só se a DA já foi aprovada: abre a revisão N+1
# edite da/da.json (bloco "legenda"; dicionário dos tokens: "$CRIABR_SKILLS"/video-direcao-de-arte/references/tokens.md)
"$CRIABR_SKILLS"/video-direcao-de-arte/kit/bin/da validar                # avisa se a legenda sai da zona segura ou perde contraste
"$CRIABR_SKILLS"/video-direcao-de-arte/kit/bin/da prancha --formato vertical    # a prancha mostra a legenda sobre as quatro zonas
python3 "$CRIABR_SKILLS"/video-legendas/scripts/legendar.py --video … --palavras … --previa      # a legenda nova sobre o vídeo real
"$CRIABR_SKILLS"/video-direcao-de-arte/kit/bin/da aprovar                # com o "sim" do usuário
```

Depois de mudar a DA: gere as cues de novo (elas são medidas com a fonte e o tamanho) e renderize outra vez o que `da conferir-carimbo` marcar como `DA DIFERENTE`. Quem conduz a revisão é a skill `video-direcao-de-arte`; esta skill só mostra o efeito.

## "Quero a legenda assim" → token

| pedido do usuário | token (em `da/da.json`) | observação |
|---|---|---|
| "palavra por palavra, tipo TikTok" (bloco visível, palavra acesa) | `legenda.estilo: "karaoke"` | as já ditas ficam em `legenda.cor_falada` (ou `null` = igual a `cor`) |
| "uma palavra de cada vez, grandona" | `legenda.estilo: "palavra"` + `legenda.tamanho` 0,08–0,1 | todas as palavras de uma cue têm o mesmo tamanho |
| "legenda normal, de frase" | `legenda.estilo: "bloco"` | a pontuação é mantida; `max_palavras` 6–8 |
| "maior" / "menor" | `legenda.tamanho` (fração do lado menor) | 0,052 = 56 px em 1080. Abaixo de 0,04 o kit avisa; quanto maior, menos palavras cabem por linha |
| "mais (menos) palavras por tela" | `legenda.max_palavras`, `legenda.max_linhas` | são tetos sem exceção: o que não couber vira mais cues, nunca texto menor; `cues.py editar --linhas` recusa passar de `max_linhas` (a legenda sairia da faixa reservada a ela) |
| "outra cor na palavra falada" | `legenda.cor_destaque` = nome de um token da paleta | a cor nova nasce em `cor.paleta` (e passa pela prancha); a conferência de contraste lista os tokens que leem melhor |
| "caixa preta atrás" | `legenda.fundo: {"cor": "fundo", "alfa": 0.85, "raio": 0.2, "respiro": [0.4, 0.2]}` | alfa < 0,8 deixa o vídeo vazar por trás da letra |
| "contorno" / "sombra" | `legenda.contorno: {"cor": "fundo", "espessura": 0.1}`, `legenda.sombra` | 0,08–0,12 segura a legenda sobre qualquer vídeo |
| "tudo maiúsculo" | `legenda.caixa: "alta"` | |
| "outra fonte" | `tipografia.papeis.legenda` | arquivo da fonte em `da/fontes/`, com a licença |
| "mais para baixo / para cima" | `legenda.posicao.vertical.y` (ou `.horizontal.y`), fração da altura | no vertical a zona `uniao` vai de 0,15 a 0,65: abaixo de 0,65 ficam nome da conta, legenda do post e botões. O kit empurra o bloco para dentro da zona se o token pedir fora |
| "centralizada no quadro" (vertical) | `legenda.posicao.vertical.x: 0.5` | o padrão é o centro da zona segura (x = 450 de 1080), porque a coluna de botões come a direita |
| "mais larga" | `legenda.largura_max` / `legenda.posicao.vertical.largura_max` | nunca passa da zona; no vertical a `uniao` deixa 0,61 da largura. **`--plataforma shorts` ou `reels` não alarga a legenda**: a zona cresce (840 e 788 px em 1080), mas o bloco continua limitado por este token (0,61 nos cinco presets = 658,8 px nas quatro zonas, medido); só o centro muda. Legenda mais larga só para Shorts é token, e aí ela deixa de caber na `uniao` |
| "o GC está em cima da legenda" (horizontal) | `legenda.reservar_em`: inclua `"horizontal"` | por padrão a faixa da legenda só é reservada no vertical e no quadrado; no horizontal GC, crédito e gráficos do kit ficam no mesmo lugar. `legendar.py` avisa toda vez que queima num formato sem reserva; depois de mudar o token, as peças com GC precisam ser refeitas |
| "com um pulinho" / "aparecendo suave" / "sem animação" | `legenda.animacao: "pop" \| "fade" \| "nenhuma"` | ver abaixo |
| "pulo mais forte / mais lento" | `movimento.duracoes.micro` (pop), `movimento.duracoes.curta` (fade), `movimento.curvas.entrada` | valem para toda a animação do projeto, não só para a legenda |
| "sem ponto e vírgula" / "com pontuação" | **não é token**: `--pontuacao limpa\|manter\|nenhuma` | é conteúdo, não aparência |
| "esconder esse nome" / "escreve 23% em número" | **não é token**: `legendas/glossario.json` | idem |

## O que cada estilo desenha

| `legenda.estilo` | na tela | estados por cue | cores |
|---|---|---|---|
| `karaoke` | o bloco inteiro da cue, parado; a palavra falada muda de cor | um por palavra | falada: `cor_destaque`; já ditas: `cor_falada` (ou `cor`); por dizer: `cor` |
| `palavra` | só a palavra falada, centrada | um por palavra | `cor_destaque` |
| `bloco` | o bloco inteiro, estático | um | `cor` (palavras de `destaques` do glossário em `cor_destaque`) |

Os estados são desenhados por `texto.estados_da_legenda` (kit), em paridade com a peça `ctx.kit.legenda` do motor: a mesma DA rende a mesma legenda numa animação e num corte legendado.

## O que cada animação faz

| `legenda.animacao` | karaokê | palavra | bloco | duração |
|---|---|---|---|---|
| `fade` | a cue entra por opacidade | cada palavra entra por opacidade | a cue entra por opacidade | `movimento.duracoes.curta`, no máximo metade da duração da cue (no estilo `palavra`, metade do tempo da palavra); curva `movimento.curvas.entrada` |
| `pop` | a palavra falada nasce 8 % maior e assenta, **no lugar** (as vizinhas não se mexem) | a palavra nasce 8 % maior e assenta | o bloco nasce 8 % maior na entrada da cue | `movimento.duracoes.micro`, no máximo metade do tempo em que a palavra (ou o bloco) fica acesa; curva `entrada` |
| `nenhuma` | troca seca | troca seca | troca seca | — |

- Os 8 % são o número do motor (`motor/cenas/_legenda.js`), repetido em `legendar.AMPLITUDE_DO_POP` para as duas peças baterem.
- A saída da cue é sempre um corte seco.
- O pop nunca tira a palavra da zona segura: encostada na borda, ela cresce menos (o resultado conta em `conferencia.zona.pop_reduzido`).
- No karaokê a palavra cresce no máximo **meio vão** para cada lado — palavra longa cresce menos de 8 %, para não colar na vizinha — e as letras das outras palavras ficam por cima do contorno dela, como no desenho assentado (o acento da linha de baixo não some).
- Com `micro` de 0,06–0,14 s (os presets), o pop dura de 1 a 4 quadros a 30 fps (em 60 fps, o dobro de quadros).

## O mesmo corte em três DAs (medido)

O mesmo trecho de 3 s, o mesmo comando, só o projeto muda (para ver as folhas de contato nesta máquina: `scripts/testes/ponta_a_ponta.py`, que as grava em `<saida>/prova/`):

| preset | estilo + animação | o que se vê em 540×960 |
|---|---|---|
| `lab-ia` | karaokê + fade | texto de 28 px em caixa escura arredondada; palavra falada em ciano, já ditas em cinza |
| `neon-shorts` | palavra + pop | uma palavra de 50 px em caixa alta, verde, contorno preto grosso e sombra dura |
| `editorial-claro` | bloco + fade | frase de 25 px com pontuação, texto escuro sobre caixa clara |

## O que a skill lê da DA (lista completa)

`legenda.*` (todos os tokens) · `tipografia.papeis.<legenda.papel>` · `cor.paleta` (por nome de token) · `formatos.margens_seguras` (zona `uniao`, `instagram`, `tiktok`, `shorts`, `padrao`) · `formatos.<nome>` (tamanho e fps quando `--formato` é um nome) · `movimento.duracoes.micro`, `.curta` · `movimento.curvas.entrada` · `tratamento.recorte.ancora` (recorte) · `tratamento.encaixe.*` (`--enquadramento encaixe`) · `tratamento.grade` e acabamento (só com `--tratamento`).

`layout.densidade` e `legenda.reservar_em` não mudam o desenho da legenda: o segundo diz às **outras** cenas do kit (GC, título, gráficos) para deixarem livre a faixa da legenda. A skill lê `reservar_em` só para avisar (`d.legenda_reservada`): queimar legenda num formato fora dessa lista — o horizontal, por padrão — põe a legenda no lugar do GC.
