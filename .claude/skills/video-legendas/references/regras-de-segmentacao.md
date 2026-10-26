# Regras de segmentação, tempo e legibilidade

O que `scripts/cues.py` e `scripts/legendar.py` aplicam, com o número, o nome da constante e de onde ele vem. **Fontes lidas em 2026-10-07 e conferidas de novo em 2026-10-12** (lista no fim). O que não tem fonte publicada está marcado como **decisão da casa**: são valores calibrados nos dois vídeos de teste desta máquina (20 s de fala contínua; 75 s com dois apresentadores) e podem ser revistos.

Há dois produtos com regras diferentes:

| | legenda **queimada** (o vídeo) | legenda **oculta** (`.srt`/`.vtt`) |
|---|---|---|
| unidade | cue de poucas palavras, acendendo palavra a palavra | frase inteira |
| ritmo | o da fala (sincronia por palavra) | o da leitura |
| tamanho | `legenda.max_palavras` × `legenda.max_linhas` da DA, medido em pixels | 42 caracteres × 2 linhas |
| pontuação | limpa (só `?` e `!`); `manter` no estilo `bloco` | a da transcrição |
| quem lê | todo mundo, com o som ligado ou não | quem liga a legenda; o buscador |

As duas saem das mesmas palavras, depois do glossário — uma correção feita com `cues.py editar` vale para as duas.

## 1. Preparo das palavras (antes de segmentar)

| o que | regra | constante | origem |
|---|---|---|---|
| tokens de controle (`[_BEG_]`, `[Música]`) e vazios | descartados | — | formato do whisper.cpp (skill video-transcricao) |
| pontuação solta (`...`, `—`) | gruda na palavra anterior | — | casa |
| `-me`, `-se` colado | junta à palavra anterior (`disse-me`) | — | casa |
| janela `--inicio/--fim` | entra a palavra cujo **meio** está na janela; tempos rebaseados para 0 | — | casa |
| ordem | início nunca decresce | — | — |
| palavra de duração (quase) zero | puxada para trás: ocupa o silêncio anterior ou até 60 % da palavra anterior, com duração plausível de 0,05 s + 0,05 s por letra (máx. 0,40 s). As seguintes não se movem | `_duracao_plausivel`, `MIN_PALAVRA` | casa (observado: 7 palavras com `a == b` em 75 s) |
| toda palavra fica acesa pelo menos | 0,10 s (ou 2 quadros, o que for maior) | `MIN_PALAVRA` | casa |
| fim estimado da fala de uma palavra | `a + 0,25 s + 0,07 s × letras`, no máximo `b` | `TETO_FALA` | casa (o whisper cola o silêncio seguinte na palavra) |
| palavra que o glossário trocou | o fim da fala é o do trecho **original**, não o do texto novo (`fala_fim` na palavra) | `Pal.fala_fim` | casa. Sem isso, "cento e cinquenta mil" → `150.000` (7 caracteres para 1,9 s de fala) fazia a cue sair no meio da fala e inventava uma pausa de 1,1 s antes de "reais" |
| confiança `p` abaixo de 0,60 | aviso `revisar`, nunca correção automática | `LIMIAR_CONFIANCA` | casa (a video-transcricao usa 0,75 para listar e relata que só valores bem baixos eram erro) |

## 2. Onde a cue fecha (legenda queimada)

Sempre fecha:

- **fim de frase** — a palavra termina em `.`, `!`, `?` ou `…`. BBC §3.2: "Subtitles should contain single sentences".
- **silêncio ≥ 0,70 s** depois da palavra (`PAUSA_DURA`, casa): um bloco parado no meio de uma pausa longa parece travado.

Dentro de cada trecho, programação dinâmica escolhe os cortes de menor custo entre os que **cabem** (item 3) com até `legenda.max_palavras`:

| corte entre a palavra *i* e a *i+1* | custo | de onde vem |
|---|---|---|
| depois de vírgula, ponto e vírgula, dois-pontos, travessão | −7 | Netflix: quebrar "after punctuation marks"; BBC §3.4 |
| silêncio ≥ 0,25 s (≥ 0,125 s) | −3 (−1) | casa (`PAUSA_LEVE`) |
| antes de conjunção ou preposição | −1,5 (−3 em quebra de linha) | Netflix: "before conjunctions", "before prepositions" |
| depois de artigo, preposição, conjunção, possessivo/demonstrativo, `não`, `muito`, `mais`… | +8 | Netflix: não separar "a noun from an article", "a verb from an auxiliary, reflexive pronoun or negation"; BBC §3.4: "article and noun", "preposition and following phrase", "conjunction and following phrase" |
| depois de pronome sujeito (`eu`, `você`, `ele`…) | +3 | Netflix: "a verb from a subject pronoun"; BBC: "pronoun and verb" |
| auxiliar + infinitivo/gerúndio/particípio (`vai | ter`) | +6 | BBC: "parts of a complex verb" |
| depois de verbo de ligação (`é`, `são`, `foi`, `está`, `tem`…) | +3 | casa (`é | só um cidadão comum`) |
| número + unidade (`23 | %`, `3 | milhões`), moeda + número | +12 | casa (o número sem a unidade não diz nada) |
| dentro de um numeral por extenso: `mil | novecentos`, `vinte | e três`, `vinte e | três` | +12, +13,5 e +18 (8 da conjunção + 10) | casa (o numeral é um bloco só; o `e` pendurado é o pior corte e perde com folga até para uma linha de uma palavra só) |
| dentro de `por cento` (`por | cento`) | +14 (8 da preposição + 6) | casa |
| numeral + o que ele conta (`três | modelos`) | +5; nada se o que vem é conjunção (`1999 | e ninguém viu` é bom corte) | casa |
| nome + sobrenome (duas maiúsculas seguidas, fora do início de frase) | +12 | Netflix: "a first name from a last name" |
| dentro de nome com partícula: `Lula | da Silva`, `São José | dos Campos`; `Lula da | Silva` | +13,5; +18 (8 da preposição + 10) | Netflix (mesma regra do nome); casa nos números |
| nome + `e` + nome (`Lula | e Dilma`), ou maiúscula de início de frase + partícula (`Antes | da Copa`) | +5 | casa (podem ser dois nomes; a maiúscula pode ser só ortografia) |
| abrir uma cue | +2,0 | casa |
| cada vaga sobrando na cue | +0,35 | casa (cue cheia muda menos vezes) |
| cue de uma palavra no meio da frase | +6 | casa |
| cue de duas palavras (quando cabem 4 ou mais) | +1 | casa |
| cue que ficaria menos de 0,50 s na tela | +4 | casa (`PESOS_QUEIMADA["relampago"]`): o agrupamento já nasce evitando o flash, porque depois não há como juntar sem passar de `legenda.max_palavras` |

As classes de palavra são listas fechadas em `cues.py` (`ARTIGOS`, `PREPOSICOES`, `CONJUNCOES`, `DETERMINANTES`, `ADVERBIOS_PRESOS`, `PRONOMES_SUJEITO`, `AUXILIARES`, `VERBOS_DE_LIGACAO`, `UNIDADES`), comparadas em minúsculas **com acento** (`e` ≠ `é`, `esta` ≠ `está`). Não há análise sintática: verbo só é reconhecido pela lista de auxiliares e pela terminação da palavra seguinte. Onde a regra errar, `cues.py editar --dividir/--juntar` corrige.

A vírgula vale mais que o custo de abrir uma cue: na queimada, toda vírgula vira corte, desde que não sobre palavra órfã. Na oculta os pesos se invertem (`PESOS_OCULTA`): a frase só se parte quando não cabe.

Os custos são preferências, não proibições: um nome de seis palavras numa DA de `max_palavras: 5` vai ser partido em algum lugar. Medido com a fonte dos presets, no vertical: `Ontem o Luiz Inácio Lula | da Silva falou` (lab-ia, 5 palavras por cue) e `Ontem o Luiz Inácio | Lula da Silva falou` (dossie, 4); `no ano de mil novecentos | e noventa e nove | e ninguém viu`; `Foram vinte e três | por cento` (a alternativa era `Foram` sozinha por 0,3 s). O corte cai antes da partícula ou do `e`, nunca depois; com `numeros_em_algarismo` o mesmo texto sai `Foram 23% em 2017 | 150.000 reais`. O que o custo não resolve é o que não cabe: `em dois mil e dezessete` (5 palavras) numa DA de 4 deixa o `em` na cue de cima. **`legenda.max_palavras` e `legenda.max_linhas` são tetos sem exceção** — nenhuma cue gerada passa deles, nem para salvar uma cue curta.

## 3. "Cabe" = cabe na tela sem encolher

Cada cue candidata é medida com a fonte, o tamanho, o tracking, o contorno e a caixa do bloco `legenda` da DA, dentro da largura que a zona segura deixa (`MedidorDaDA`: `texto.largura_texto`, `texto.vao_entre_palavras` e `texto.caixa_da_legenda` do kit — a mesma conta de `texto.compor_legenda` antes de encolher). Cue que não cabe em `legenda.max_linhas` linhas não é candidata. Só sobra encolher quando **uma palavra sozinha** é mais larga que a zona; aí sai o aviso de largura e, na hora de desenhar, o kit encolhe o bloco inteiro.

No estilo `palavra`, "cabe" é cada palavra caber sozinha — e uma palavra longa demais fica numa cue só dela, para não reduzir o tamanho das vizinhas (o kit usa um tamanho por cue).

Referência externa de tamanho, para conversar com a DA: a BBC pede altura de linha de 7 % a 8 % da altura do vídeo em 16:9 e de 3,9 % a 4,5 % em 9:16, e largura de até 68 % (16:9) ou 90 % (9:16) do quadro para legenda online. Os presets da DA usam `legenda.tamanho` de 0,046 a 0,092 do lado menor e `largura_max` 0,76–0,80 (horizontal) e 0,61 (vertical, por causa da zona `uniao`). O kit considera 0,040 do lado menor o mínimo sem aviso (`da.MINIMO_LEGENDA`: 43 px em 1080).

## 4. Quebra de linha dentro da cue

1. O **menor número de linhas** que cabe (Netflix: "Text should usually be kept to one line, unless it exceeds the character limitation"). O teto é `legenda.max_linhas`; a BBC recomenda 2 linhas em paisagem e até 3 no vertical.
2. Entre as partições possíveis, a de menor custo: os mesmos custos de sentido do item 2 (sem as pausas) + 4 × (diferença de largura entre a linha mais larga e a mais estreita ÷ largura útil) + 4 por linha de uma palavra só (em cue de 3 ou mais). BBC §3.4: prioridade ao critério linguístico sobre o geométrico — por isso `cento / e cinquenta mil` (linha de uma palavra) ganha de `cento e / cinquenta mil` (conjunção pendurada dentro do numeral).

Exemplo medido (bloco, zona de 330 px): `que ele falou ali / que é real,` e não `que ele falou / ali que é real,`.

## 5. Tempos da cue queimada

| regra | valor | constante | origem |
|---|---|---|---|
| entrada | no início da primeira palavra | — | Netflix: in-time no primeiro quadro de áudio (tolerância de 1–2 quadros); BBC §5.1: "subtitle appearance should coincide with speech onset" |
| saída sem cue logo depois | 0,30 s depois do fim estimado da fala | `SEGURA` | casa. A Netflix recomenda ao menos 0,5 s para legenda de frase inteira; na queimada a leitura acompanha a palavra acesa |
| vão menor que 0,5 s até a próxima cue | fechado: a cue fica até a próxima entrar | `FECHA_VAO` | Netflix: vãos de 3 a 11 quadros (24 fps) são fechados para 2 quadros; BBC §4.5: vão curto "produces a very jerky effect" |
| respiro entre cues coladas | 2 quadros do vídeo | `RESPIRO_QUADROS` | Netflix: "Subtitles must have a minimum of 2 frames between them" |
| o respiro nunca come a última palavra | ela fica acesa ao menos 0,10 s | `MIN_PALAVRA` | casa |
| estilo `palavra` | sem respiro (não há bloco trocando) | — | casa |
| duração mínima | 0,50 s; a segmentação já evita (custo `relampago`); o que sobrar abaixo disso funde com a vizinha da mesma frase **se o conjunto couber em `legenda.max_palavras`** e na largura; senão fica o aviso `duracao` | `DUR_MIN` | casa (a referência de frase inteira é 5/6 s). Medido no preset de 4 palavras por cue, fala rápida: 3 avisos em 20 s e 7 em 75 s, todos entre 0,30 e 0,49 s |
| fala muito rápida | aviso acima de 25 caracteres por segundo, medidos pela duração **real** da cue em todos os estilos | `CPS_QUEIMADA` | casa. Nos vídeos de teste a fala normal ficou entre 15 e 22; acima de 25 era tempo ruim da transcrição |
| estilo `palavra` | quem pisca é a palavra, não a cue: aviso `relampago` para palavra com menos de 0,10 s de tela; não há aviso `duracao` | `MIN_PALAVRA` | casa |
| nunca | sobrepor a cue seguinte; passar do fim do vídeo | — | — |

Cada palavra fica acesa do seu início até o início da seguinte (a última, até a saída da cue). Os tempos são arredondados para o quadro da base na hora de renderizar.

## 6. Legenda oculta (`.srt` e `.vtt`)

| regra | valor | constante | origem |
|---|---|---|---|
| caracteres por linha | 42 | `OCULTA_CARACTERES` | Netflix, guia de português do Brasil |
| linhas | 2 | `OCULTA_LINHAS` | Netflix: "Maximum two lines" |
| duração mínima | 5/6 s | `OCULTA_DUR_MIN` | Netflix, requisitos gerais |
| duração máxima | 7 s | `OCULTA_DUR_MAX` | Netflix, requisitos gerais |
| saída | 0,5 s depois do fim da fala, sem invadir a próxima (respiro de 2 quadros) | `OCULTA_SEGURA` | Netflix, guia de tempo |
| velocidade de leitura | 17 caracteres/s de referência; aviso acima de 20 | `OCULTA_CPS` | Netflix pt-BR: 17 (adulto), 13 (infantil); 20 e 17 em legenda para surdos e ensurdecidos. A BBC trabalha com 160–180 palavras por minuto |
| números | de um a dez por extenso; acima, algarismo (só com `numeros_em_algarismo: true` no glossário) | `numeros.LIMITE_POR_EXTENSO` | Netflix pt-BR |

A legenda oculta é **literal** (não resume a fala). Quando a fala passa da velocidade de leitura e não há silêncio para estender, o script só avisa — resumir é trabalho editorial.

Formato dos arquivos:

- `.srt` (SubRip): número, `HH:MM:SS,mmm --> HH:MM:SS,mmm`, texto, linha em branco; UTF-8 sem marcação. O YouTube pede "plain UTF-8" e não reconhece marcação em `.srt`.
- `.vtt` (WebVTT): primeira linha `WEBVTT`, tempos com ponto (`HH:MM:SS.mmm`), `&` e `<` escapados; o texto não pode conter `-->`. O YouTube aceita `.vtt` ("in initial implementation").
- Os dois saem sem sobreposição, em ordem, com fim depois do início, e terminam dentro do vídeo. O teste `test_28` passa o `.srt` pelo conferidor da `video-publicacao` quando ela está instalada ao lado.

## 7. Contraste contra o vídeo

`legendar.py` amostra 16 quadros (no meio da palavra do meio de cues espalhadas pelo trecho), já no enquadramento de saída, e mede na caixa da legenda:

1. a luminância relativa do fundo (fórmula da WCAG 2.2, limiar 0,04045), nos percentis 10 e 90 — o texto passa por cima do claro e do escuro;
2. se a DA tem `legenda.fundo`, o fundo efetivo é a caixa misturada ao vídeo pelo `alfa`;
3. a razão de contraste de cada cor em uso (`cor`, `cor_destaque`, `cor_falada`) contra o p10 e o p90: vale a pior;
4. se a DA tem `legenda.contorno` com espessura ≥ 0,05 do tamanho, a letra está isolada do fundo: vale o maior entre letra × fundo e letra × contorno (**decisão da casa**; a WCAG não trata de contorno).

| nível | razão | origem |
|---|---|---|
| ruim | < 3:1 | WCAG 2.2, critério 1.4.3: mínimo para texto grande (18 pt, ou 14 pt em negrito) — a legenda queimada é texto grande |
| no limite | 3:1 a 4,5:1 | 4,5:1 é o mínimo geral do mesmo critério |
| ok | ≥ 4,5:1 | — |

A resposta a um trecho ruim é sempre um **token** (ligar `legenda.contorno` ou `legenda.fundo`, subir `legenda.fundo.alfa`, trocar o token de `legenda.cor_destaque` por outro da paleta que o script lista com a razão medida). Nunca uma cor escrita na peça.

`fundo carregado` (`FUNDO_CARREGADO`, casa): p90 − p10 da luminância **bruta** ≥ 0,45 atrás da legenda. Costuma ser texto ou GC do próprio vídeo; também dispara em camisa listrada. É um convite a olhar a prévia, não um veredito.

Limites da medida: amostra por tempo (um flash de 0,2 s entre duas amostras passa), mede a caixa do bloco (não letra por letra) e não enxerga movimento. Sombra sem contorno não entra na conta.

## Fontes (lidas em 2026-10-07; conferidas de novo em 2026-10-12, na revisão e no fecho da skill)

- Netflix Partner Help Center — *Brazilian Portuguese Timed Text Style Guide* (última atualização da página: 2025-07-07): 42 caracteres por linha; até 17 caracteres por segundo (adulto) e 13 (infantil); máximo de duas linhas; números de 1 a 10 por extenso. https://partnerhelp.netflixstudios.com/hc/en-us/articles/215600497-Brazilian-Portuguese-Timed-Text-Style-Guide
- Netflix Partner Help Center — *Timed Text Style Guide: General Requirements* (2022-10-07): duração mínima de 5/6 s e máxima de 7 s; uma linha sempre que couber; onde quebrar e o que não separar. https://partnerhelp.netflixstudios.com/hc/en-us/articles/215758617-Timed-Text-Style-Guide-General-Requirements
- Netflix Partner Help Center — *Timed Text Style Guide: Subtitle Timing Guidelines* (2025-07-04): entrada a 1–2 quadros do áudio; saída idealmente 0,5 s depois; mínimo de 2 quadros entre legendas; vãos de 3–11 quadros fechados. https://partnerhelp.netflixstudios.com/hc/en-us/articles/360051554394-Timed-Text-Style-Guide-Subtitle-Timing-Guidelines
- BBC — *Subtitle Guidelines*, versão 1.2.5 (março de 2026): 160–180 palavras por minuto; cerca de 0,3 s por palavra; 2 linhas (3 no vertical 9:16); largura de 68 % (16:9) e 90 % (9:16); quebra em pontos naturais (§3.4); vãos (§4.5); sincronia com o início da fala (§5.1); altura de linha por proporção. https://www.bbc.co.uk/accessibility/forproducts/guides/subtitles/
- W3C — *Web Content Accessibility Guidelines (WCAG) 2.2*, Recomendação de 12 de dezembro de 2024: critério 1.4.3 (4,5:1; 3:1 para texto grande), definições de "large scale", "contrast ratio" e "relative luminance". https://www.w3.org/TR/WCAG22/
- W3C — *WebVTT: The Web Video Text Tracks Format*, Candidate Recommendation Draft de 20 de maio de 2026: corpo do arquivo, carimbo de tempo, texto da cue. https://www.w3.org/TR/webvtt1/
- YouTube Help — *Supported subtitle and closed caption files*: `.srt` em UTF-8 sem marcação; `.vtt` aceito. https://support.google.com/youtube/answer/2734698?hl=en

O que **não** foi encontrado em fonte confiável e por isso não é citado como regra: preferência por "pirâmide invertida" nas duas linhas (a página de requisitos gerais da Netflix não traz), tamanho mínimo de legenda queimada publicado por Instagram, TikTok ou YouTube, e qualquer norma para legenda palavra a palavra — o karaokê de redes sociais não tem padrão publicado; as regras dele aqui são adaptação das de legendagem e decisão da casa.
