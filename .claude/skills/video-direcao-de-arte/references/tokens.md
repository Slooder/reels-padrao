# Dicionário de tokens do `da.json` (esquema v1)

Cada token: o que significa, unidade, faixa que o validador aceita (e a faixa que costuma dar certo), efeito visual e quem consome. Fonte: `kit/da_esquema.json` (kit 1.6.0) e o comportamento observado do compilador, do motor e de `texto.py`/`video.py`.

Convenções que valem para o arquivo inteiro:

- **Frações são do lado menor do quadro**, salvo quando o texto diz "da altura" ou "da largura". É isso que faz a mesma DA servir a 1920×1080, 1080×1920 e 1080×1080: `0,058` vira 63 px nos três.
- **Campo de cor aceita token ou hex**: `"primaria"`, `"dado-3"`, `"neutro-1"` ou `"#FFC700"`. O compilador grava o irmão `<campo>_hex` já resolvido na `da.resolvida.json`. Hex que não está na paleta/dados/neutros entra na lista de permitidas do auditor, então use hex em campo de cor só se for de propósito.
- **Arquivos** (`arquivo`, `lut`, `logo`, `referencias[].arquivo`) são relativos a `da/`, absolutos ou `null`. O compilador grava `<campo>_abs`.
- **Herança**: tudo exceto `projeto` pode vir de `herda` (preset embutido, pessoal ou caminho de outro `da.json`); o filho vence, listas substituem inteiras.
- Chaves iniciadas por `_` ou `x_` são livres (anotações, dados de outra skill): o validador não as conhece, o kit as carrega (`d["x_legendas"]`, com campos `cor*` resolvidos em `<campo>_hex`) e elas **não entram na identidade**. Só guarde nelas o que não muda pixel; o que muda pixel tem de ser token do esquema. Dentro de um mapa de tokens (`cor.paleta`, `cor.gradientes`, `tipografia.papeis`, `tipografia.escala`, `movimento.curvas`, `movimento.duracoes`, margens por plataforma) nome começado por `_` ou `x_` é **erro**: ali toda chave é um token que as peças usam.
- **Identidade (`da_sha256`), regra exata**: todo o conteúdo com a herança aplicada + os arquivos de fonte/LUT/textura/logo referenciados, exceto `herda`, `projeto.*`, `conceito.*` e as chaves `_`/`x_`. Editar qualquer token das seções abaixo (inclusive `som` e `marca`) muda o sha, envelhece os carimbos e — se a DA estava aprovada — pede `revisar`; editar `projeto.nome`, `conceito.frase` ou uma anotação, não.
- **Cor com transparência** não é token: use o token com alfa na peça — `rgba(var(--da-cor-<nome>-rgb), a)` no CSS (única forma; `rgb(var(…-rgb) / a)` computa transparente), `ctx.alfa(token, a)` em cena, `d.rgba(token, a)` em Python.
- Tamanhos de fonte em px: `d.px(fracao, formato)` em Python, `ctx.tam('h1')` / `ctx.px(f)` no motor, `calc(var(--da-lado) * f)` no CSS.
- **Mínimo legível: 0,022 do lado menor para texto de apoio, 0,04 para legenda.** A conta: o lado menor do quadro ocupa a largura da tela do celular (vertical em pé; horizontal com o aparelho deitado, em tela cheia), então num aparelho de 390 pt de largura uma fração `f` rende `f × 390` pt — `da.pt_no_celular(f)`. 0,022 = 24 px em 1080 = 8,6 pt; 0,026 = 28 px = 10,1 pt; 0,04 = 43 px = 15,6 pt. Abaixo de 0,022 o texto só se lê com zoom: os presets traziam cargo de GC e crédito de fonte em 0,016–0,019 (17–20 px, 6,2–7,4 pt) e eles só apareciam ampliando o quadro. O validador **avisa** quando `graficos.gc.tamanho_cargo`, `graficos.citacao_fonte.tamanho` ou `tipografia.escala.nota` ficam abaixo de 0,022, e quando `legenda.tamanho` fica abaixo de 0,04 (`da.MINIMO_LEGIVEL`, `da.MINIMO_LEGENDA`); o recomendado para apoio é ≥ 0,026 e para legenda ≥ 0,052. Os números são convenção do kit, calibrados na faixa "Em escala 1:1" da prancha — é nela que se confere, com a prancha na largura da tela.
- **Legenda e o resto nunca dividem o mesmo lugar.** A legenda fica onde `legenda.posicao` manda; GC, título, gráfico, crédito, assinatura e rótulo de moldura ficam na **área livre** — a zona segura menos a faixa da legenda (`d.area_livre`, `ctx.area_livre`) — nos formatos de `legenda.reservar_em`.

## `versao_esquema`, `herda`

| token | tipo | significado | consumidor |
|---|---|---|---|
| `versao_esquema` | `1` | versão do esquema; o validador recusa outra | kit |
| `herda` | nome de preset, caminho ou `null` | de onde esta DA herda. `"canal-teste"` → `$VIDEO_OPS_HOME/da-presets/canal-teste/da.json` ou `kit/presets/canal-teste.json`; caminho relativo é resolvido a partir da pasta do filho. Cadeia de herança permitida (preset → canal → vídeo) | `compilar` (deep-merge), `salvar-preset` |

## `projeto` — identidade e estado (nunca herdado)

| token | tipo | significado | consumidor |
|---|---|---|---|
| `nome`, `slug` | texto | nome legível e slug `[a-z0-9-]` (o init gera) | prancha, carimbo, CLAUDE.md |
| `criada_em` | ISO 8601 | data de criação | registro |
| `revisao` | inteiro ≥ 1 | sobe com `da.py revisar`; entra no carimbo (`da_revisao`) | `conferir-carimbo`, conferência final (`da conferencia`) |
| `aprovada`, `aprovada_em`, `aprovada_sha256` | bool, ISO, sha | gravados por `aprovar`. Se o conteúdo mudar depois, `validar`/`compilar` avisam "DA ALTERADA DEPOIS DA APROVAÇÃO" e `aprovar` recusa até `revisar` | prancha ("RASCUNHO"/"aprovada"), conferência final (`da conferencia` reprova DA não aprovada ou alterada depois da aprovação), carimbo (`da_aprovada`) |
| `base` | texto ou `null` | preset de origem usado pelo init (só registro) | prancha, `mostrar` |
| `rota_adotada` | texto ou `null` | nome da rota que `da.py rotas adotar` trouxe para o projeto (só registro) | registro |

## `conceito` — a direção em palavras

| token | tipo | significado e efeito | consumidor |
|---|---|---|---|
| `frase` | texto (1 frase) | resume a DA; é o que `presets` lista e a prancha imprime no topo. Escreva como briefing para um motion designer: material + cor + tipografia + sensação ("preto de arquivo, amarelo de marca-texto e tipografia de carimbo — cada tela parece uma prova sendo apresentada") | prancha, `presets`, `mostrar`, DA.md |
| `palavras_chave` | lista de texto | 4–8 adjetivos/substantivos; viram chips na prancha | prancha, briefing das skills |
| `referencias` | lista de `{arquivo, nota}` | imagens/quadros em `da/referencias/` com o que observar em cada um | prancha (antes/depois usa a primeira), `extrair` |
| `faca` | lista de texto | regras positivas e concretas ("abrir blocos por máscara e só depois revelar o texto") — toda skill visual lê antes de desenhar | video-animacao-explicativa, video-motion-graphics, video-pauta-midia, thumbnail feita pelo kit |
| `nao_faca` | lista de texto | o que o auditor não pega mas quebra o estilo ("gradiente, brilho, sombra", "mais de uma cor de destaque na mesma tela") | idem |

## `formatos` — quadros, fps e margens seguras

| token | tipo/faixa | significado | consumidor |
|---|---|---|---|
| `horizontal`, `vertical`, `quadrado` | `{largura, altura (16–8192, pares), fps}` | os três formatos de vídeo. `fps` é racional em texto: `"30000/1001"` (29,97), `"24000/1001"`, `"25"`, `"60"`. A resolvida acrescenta `fps_num`, `fps_den`, `fps_float`, `lado_menor` | motor (`--formato`), `video.args_encode`, video-cortes-verticais, video-publicacao |
| `thumbnail` | `{largura, altura}` sem fps | 1280×720 por padrão (YouTube aceita até 3840×2160) | thumbnail feita direto pelo kit (`kit-api.md` §17.1), motor |
| `<outro nome>` | idem | formatos extras (ex.: `"capa_reels": {"largura": 1080, "altura": 1350}`) ficam disponíveis em `d.formato(nome)` e `--formato nome` | quem precisar |
| `margens_seguras.horizontal.padrao` | `[topo, direita, base, esquerda]`; topo/base em fração da **altura**, direita/esquerda da **largura** | zona onde texto e GC podem ficar; `[0.05, 0.05, 0.05, 0.05]` = EBU R 95 para gráficos (54 px e 96 px em 1080p) | `d.margens("horizontal")`, `ctx.area_segura()`, todas as cenas |
| `margens_seguras.vertical.instagram / tiktok / shorts` | idem | zona coberta pela interface de cada app (números oficiais de **anúncio**, conservadores para orgânico). Dossiê: instagram `[0.14, 0.21, 0.35, 0.06]`, tiktok `[0.125, 0.2778, 0.3438, 0.1111]`, shorts `[0.15, 0.1778, 0.35, 0.0444]` — ver `plataformas.md` §1 | cenas com `plataforma`, video-legendas, video-cortes-verticais |
| `margens_seguras.vertical.uniao` | idem | pior caso das três: `[0.15, 0.2778, 0.35, 0.1111]` → retângulo livre x 120–780, y 288–1248 em 1080×1920 (660×960 px, só 61 % da largura). É o padrão quando ninguém diz a plataforma | idem; prancha vertical desenha as quatro |
| `margens_seguras.quadrado.padrao` | idem | opcional; sem ela o quadrado usa `horizontal.padrao` | — |

A chave do Reels no `da.json` é `instagram` (contrato do esquema v1). Quem **consulta** pode usar o nome canônico: `d.margens("vertical", "reels")`, `ctx.area_segura('reels')`, `compor_legenda(…, plataforma="reels")` e o parâmetro de cena `tipo: 'plataforma'` aceitam `reels`/`instagram`, `tiktok`, `shorts`, `uniao`, `youtube`/`padrao`; zona pedida num formato que não a tem (`uniao` no horizontal) cai no padrão do formato, e o resultado diz qual foi usada.

Faixa razoável: nunca menos que 0,035 no horizontal; no vertical copie de `plataformas.json` em vez de inventar.

## `cor`

| token | tipo/faixa | significado e efeito | consumidor |
|---|---|---|---|
| `paleta.fundo` | `#RRGGBB` | plano de fundo de cartelas e caixas; a cor "do canal" quando a tela está vazia | tudo |
| `paleta.superficie` | hex | plano um degrau acima do fundo (caixas, GC, grade de gráfico). Contraste com o fundo costuma ser baixo (1,1–1,5:1) de propósito | GC, barras, prancha |
| `paleta.texto` | hex | texto principal. O validador **reprova** contraste < 3:1 com `fundo` e com `superficie`; mire ≥ 7:1 (16,9:1 no lab-ia, 17:1 no dossiê) porque legenda em celular ao sol precisa | tudo |
| `paleta.texto_suave` | hex | texto secundário (cargo no GC, eixos, créditos). Mire 4,5–7:1 sobre o fundo | GC, barras, citação, legenda de prancha |
| `paleta.primaria` | hex | **a** cor de assinatura: filete, tarja, palavra em destaque na legenda, contorno de pessoa na thumb. Uma só por DA; é o que o espectador lembra | tudo |
| `paleta.secundaria` | hex | apoio: segunda série, fundo de caixa alternativo, gradiente com a primária. Pode ser quase neutra (dossiê usa `#2A2A2A`) | barras, gradientes, tarja alternativa |
| `paleta.destaque` | hex | ênfase pontual diferente da primária (alerta visual, número que salta). Use pouco; se a DA tiver "uma cor de destaque só", faça `destaque` igual ou próxima da `primaria` | citação, dados |
| `paleta.positivo`, `negativo`, `alerta` | hex | semânticas (sobe/desce, certo/errado, atenção) para gráficos e selos; precisam ler sobre `fundo` (≥ 4,5:1) | barras, selos |
| `paleta.<extra>` | hex, nome `[a-z][a-z0-9_]*` (nunca começado por `x_`) | cores a mais entram na paleta, nos tokens (`ctx.cor('<extra>')`, `--da-cor-<extra>`) e nas permitidas | quem as declarar |
| `neutros` | lista de hex (padrão `#000000`, `#FFFFFF`) | extras tolerados pelo auditor (sombra preta, brilho branco). Tokens `neutro-1`, `neutro-2`… | auditor, contornos de legenda |
| `dados` | lista de ≥ 6 itens, ordem fixa; cada item é um `#RRGGBB` **ou o nome de uma cor da paleta** (`"primaria"`, `"texto"`) | série categórica de gráficos; `dado-1` é a primeira barra. Comece pela primária e intercale claro/escuro para barras vizinhas não se confundirem; ≥ 3:1 sobre `fundo` para cada uma. **Escreva o nome quando a cor é da paleta**: a série acompanha a paleta — numa rota que troca só a `primaria`, `dado-1` muda junto (com hex, ficava a primária antiga do preset). Os presets trazem `primaria`, `secundaria`, `texto` e `texto_suave` por nome. Resolvida: `cor.dados` sempre em hex, `cor.dados_tokens` com o nome escrito (ou `null`). O validador reprova nome que não existe na paleta e hex repetido; **avisa** dois nomes que hoje têm a mesma cor e hex que é quase uma cor da paleta (ΔE < 6: "escreva `primaria` no lugar do hex"). Com mais barras que cores na série, a cena `barras` usa só a primária | barras, video-animacao-explicativa, prancha |
| `gradientes.<nome>` | `{tipo: linear\|radial, angulo (−360–360, convenção CSS), paradas: [[token, 0–1], …]}` | gradientes nomeados; a resolvida gera `css` (`linear-gradient(90deg, #5CF0FF 0%, #9D7BFF 100%)`) e o CSS `--da-gradiente-<nome>`. `thumbnail.fundo` aceita `gradiente:<nome>` | thumbnail, cartelas, prancha |

## `tipografia`

| token | tipo/faixa | significado e efeito | consumidor |
|---|---|---|---|
| `papeis.titulo / subtitulo / corpo / dados / legenda` | objeto (os cinco são obrigatórios; outros nomes são permitidos) | os papéis que toda peça usa: `titulo` (cartelas, thumb, GC nome no dossiê), `subtitulo` (sobretítulos, selos, GC), `corpo` (texto corrido, citações), `dados` (números, créditos, eixos), `legenda` (legenda queimada). Limite prático: **duas famílias** por DA (uma de título/legenda, uma de corpo/dados) | tudo |
| `papeis.<p>.familia` | nome CSS (`"IBM Plex Mono"`) | vai para `@font-face` e `--da-fonte-<p>`; o auditor compara a **primeira família** computada com estes nomes | motor, auditor, lint |
| `papeis.<p>.arquivo` | caminho relativo a `da/` ou `null` | arquivo da fonte; o init copia as do preset para `da/fontes/`. `null` = fonte do sistema: o validador avisa que PIL não a carrega (`texto.py` e `fonte_pil` falham) e outra máquina pode não tê-la. Fontes comerciais (Didot, AmsiPro) só por caminho absoluto do sistema, nunca copiadas | `fonte_pil`, `texto.py`, `da.css`, identidade (sha do arquivo) |
| `papeis.<p>.peso` | 1–1000 | `font-weight`; em fonte variável vira o eixo `wght` se `eixos` não disser outra coisa | motor, PIL |
| `papeis.<p>.largura` | 25–200 ou `null` | `font-stretch` em %; só age em fonte variável com eixo `wdth` (Roboto 75–100). Para fonte estática use `escala_x` | motor, PIL |
| `papeis.<p>.estilo` | `normal\|italic` | `font-style` | motor |
| `papeis.<p>.caixa` | `alta\|normal` | `text-transform: uppercase` e `d.texto()`/`Estilo.texto()` em PIL | motor, texto.py |
| `papeis.<p>.tracking` | −0,3–1 em | `letter-spacing`; títulos condensados pedem −0,005 a −0,02, caixa alta pequena pede +0,08 a +0,2 | motor, texto.py (caractere a caractere quando ≠ 0) |
| `papeis.<p>.altura_linha` | 0,6–3 | `line-height`; 1,05–1,1 em títulos, 1,4–1,5 em corpo | motor, texto.py |
| `papeis.<p>.eixos` | `{"wght": 800, "wdth": 88}` | eixos de fonte variável explícitos; a resolvida mostra `eixos_fonte` (faixas reais do arquivo) e `eixos_efetivos` (o que foi aplicado, já recortado às faixas) | `font-variation-settings`, `set_variation_by_axes` |
| `papeis.<p>.escala_x` | 0,3–2 (padrão 1) | condensação geométrica por `scaleX` (motor) ou LANCZOS (PIL) para fontes estáticas sem `wdth`. Dossiê usa 0,66 no título (Archivo SemiExpanded Black fica com cara de condensada) | `ctx.texto`, `texto.py` |
| `escala.display / h1 / h2 / h3 / corpo / nota` | fração do lado menor, > 0 e ≤ 0,6 | os degraus de tamanho. Dossiê: 0,13 / 0,085 / 0,058 / 0,042 / 0,03 / 0,022 → em 1080p: 140 / 92 / 63 / 45 / 32 / 24 px. Em celular, `corpo` abaixo de 0,028 vira ilegível; `nota` abaixo de 0,022 (o mínimo legível — o validador avisa) só se lê com zoom: os presets usam 0,022–0,026. Nomes extras são permitidos | `ctx.tam`, `--da-escala-<n>`, `d.px` |

## `layout`

| token | faixa | efeito | consumidor |
|---|---|---|---|
| `grade.colunas` | 1–24 | colunas da grade de composição (12 é o padrão) | `ctx.grade()`, `ctx.col(n)` |
| `grade.margem` | 0–0,25 do lado menor | margem de **composição** (onde os blocos se alinham), diferente das margens seguras de plataforma; 0,06–0,07 | `ctx.margem`, `--da-margem` |
| `grade.calha` | 0–0,1 | espaço entre colunas; 0,012–0,016 | `ctx.calha` |
| `raio` | 0–0,5 | raio de canto padrão: 0 = tudo reto (dossiê), 0,01–0,02 = suave | `ctx.raio`, GC, tarja, selo, legenda com fundo |
| `traco` | 0–0,05 | espessura padrão de filetes e barras (mín. 1 px); 0,004–0,006 | `ctx.traco`, filete do título, cantoneiras |
| `sombra` | `null` ou `{dx, dy, desfoque (−0,2–0,2), cor, alfa}` | sombra padrão de blocos; `null` = sem sombra (dossiê) | `--da-sombra`, GC estilo caixa |
| `densidade` | `arejada\|media\|densa` | quanto a tela aguenta de informação; orienta as skills (quantas linhas de legenda, quantas barras, respiros) — não tem efeito automático | video-animacao-explicativa, video-legendas |

## `movimento`

| token | faixa | efeito | consumidor |
|---|---|---|---|
| `curvas.entrada / saida / enfase / suave / linear` | `[x1, y1, x2, y2]`, x em 0–1 | cubic-bezier. `entrada` = chegar (ease-out, ex.: `[0.215, 0.61, 0.355, 1]`), `saida` = ir embora (ease-in), `enfase` = movimento forte (`[0.2, 0, 0, 1]`), `suave` = ajustes, `linear` = contadores. y fora de 0–1 dá overshoot ("quica") — proibido no dossiê, aceitável em neon-shorts | `ctx.ease/prog`, `d.facilitar`, `--da-curva-<n>`, prancha (desenha as curvas) |
| `duracoes.micro / curta / media / longa` | 0–10 s | tempos-padrão: micro 0,08–0,12 (tick), curta 0,2–0,3 (saída, palavra), media 0,36–0,5 (entrada de bloco), longa 0,7–0,9 (título) | `ctx.dur`, `d.dur`, `--da-dur-<n>`, `vida()`, `fim_saida()` |
| `escalonamento` | 0–2 s | atraso entre itens de uma sequência (stagger); 0,04–0,08 | `Timeline.escalonar`, título (tarja → título → filete → subtítulo) |
| `entrada_padrao` | `sobe\|desliza\|mascara\|escala\|fade\|digita` | como as coisas aparecem quando a cena não diz: `mascara` (dossiê, revela por clip), `digita` (lab-ia), `sobe` (editorial) | `ctx.entrada` sem tipo, `vida()`, legenda `pop` |
| `saida_padrao` | `fade\|desce\|mascara\|corte` | como somem; `fade` quase sempre | `ctx.saida` sem tipo |
| `transicoes.padrao`, `transicoes.permitidas` | `corte\|fade\|empurra\|mascara\|desliza\|zoom` | transições entre planos/cenas; `padrao` tem de estar em `permitidas`. **Executadas pelo kit** (tabela abaixo): tipo fora de `permitidas` é erro nos dois executores — a DA decide quais existem | `video.juntar`, `ctx.transicao`, `d.transicao()`, video-montagem, video-cortes-verticais, teste de movimento |
| `principios` | lista de texto | regras de animação em prosa ("o bloco abre primeiro, o texto aparece depois"; "nada quica") — a prancha imprime, as skills leem | video-animacao-explicativa, video-motion-graphics |

Como cada transição é executada (duração = `duracoes.media`; `corte` = 0):

| `transicoes.*` | em vídeo — `video.juntar(clipes, saida, transicao=…)` | em cena — `ctx.transicao(A, B, p, tipo)` |
|---|---|---|
| `corte` | `concat` (sem sobreposição) | troca seca em p = 0,5 |
| `fade` | `xfade=transition=fade` | B aparece por opacidade sobre A |
| `empurra` | `xfade=transition=slideleft` | A sai para a esquerda enquanto B entra da direita |
| `mascara` | `xfade=transition=wipeleft` | B é revelado por recorte, da direita para a esquerda |
| `desliza` | `xfade=transition=coverleft` | B desliza por cima de A, que fica parado |
| `zoom` | `xfade=transition=zoomin` | A amplia 25 % e some sobre B |

No ffmpeg o progresso é linear e cada transição come `duracoes.media` do total (os clipes se sobrepõem; o áudio cruza junto); no motor a cena escolhe a curva (`ctx.prog(t, t0, ctx.dur_transicao(), 'suave')`) e a `origem` (`direita`, `esquerda`, `cima`, `baixo`).

## `tratamento` — footage e b-roll (vira `grade.json`)

| token | faixa | filtro ffmpeg gerado | efeito | consumidor |
|---|---|---|---|---|
| `grade.lut` + `intensidade_lut` | `.cube` relativo a `da/` ou `null`; 0–1 | `lut3d` (+ `split/blend` com `all_opacity` quando parcial) | look de filme; intensidade 0,5–0,8 costuma bastar | video-broll, `da.py grade` |
| `grade.exposicao` | −3–3 EV | `lutyuv` com ganho 2^(EV/2,2) | clarear/escurecer (aproximação em YUV, não linear) | idem |
| `grade.contraste`, `saturacao`, `gama` | 0–3, 0–3, 0,1–10 (1 = neutro) | `eq=contrast=…:saturation=…:gamma=…` (só os ≠ 1) | contraste 1,05–1,15 e saturação 0,75–0,9 unificam b-roll de origens diferentes; saturação 0 = P&B | idem |
| `grade.temperatura` | −100 (fria) – 100 (quente) | `colortemperature` com 3500 K (> 0) ou 12000 K (< 0) e `mix = |t|/100`, `pl=1` | ±15–25 já é visível; aproximação grossa (dois pontos de Kelvin) | idem |
| `grade.matiz` | −180–180° | `hue=h=` | rotação de matiz; raramente ≠ 0 | idem |
| `grade.curva` | `null`, preset do `curves` (`vintage`, `strong_contrast`…), `[[x, y], …]` ou `{mestre, r, g, b}` | `curves` | curva tonal | idem |
| `duotone.ativo / sombra / luz / mistura` | bool; tokens; 0–1 | `colorchannelmixer` (luma BT.709) + `lutrgb` rampa sombra→luz (+ blend se parcial) | duotone (fotos de pessoas no dossiê: `fundo` → `texto`) | video-broll, thumbnail feita pelo kit |
| `grao.ativo / intensidade / temporal` | bool; 0–100; bool | `noise=c0s=<int>:c0f=t+u` (só luma; `u` sem temporal) | grão: 3–6 une footage limpo com arquivo; `extrair` sugere a intensidade a partir das referências. No motor vira overlay de 6 ladrilhos com opacidade ≈ intensidade/40 (aproximação visual) | video-broll, motor (`meta.grao`) |
| `vinheta.ativo / angulo` | bool; 0–π/2 rad | `vignette=angle=` | escurece os cantos; 0,3–0,45 | video-broll |
| `nitidez` | 0–2 | `unsharp` 5×5 só na luma | 0,15–0,3 para b-roll comprimido | video-broll |
| `desfoque` | 0–0,1 do lado menor | `gblur` sigma na cadeia de acabamento | desfoca o **quadro inteiro** do footage tratado (plano de fundo de cartela, b-roll que não deve competir com o texto); 0 = neutro, e é o valor de quem só quer tratar cor. **Não** é o fundo desfocado do corte vertical: isso é `encaixe` | video-broll (`filtro_tratamento`, `da.py grade`) |
| `encaixe.modo` | `desfocado\|recorte\|faixas` (padrão `desfocado`) | `video.filtro_encaixe(origem, formato, d=d)` | como um vídeo de **outra proporção** entra no quadro (16:9 → 9:16): `desfocado` = o vídeo inteiro por cima de uma cópia dele ampliada e desfocada; `recorte` = amplia e corta em `recorte.ancora`; `faixas` = vídeo inteiro com faixas chapadas. Fora da cadeia de tratamento e do `grade.json` | video-cortes-verticais, video-broll |
| `encaixe.desfoque / escurecer / cor` | 0–0,2 do lado menor da saída (padrão 0,035); 0–1 (padrão 0,25); token (padrão `fundo`) | `gblur` + `lutyuv` só no fundo; `pad` com a cor | sigma do fundo desfocado, quanto ele escurece para o vídeo se destacar, e a cor das faixas no modo `faixas` | `video.filtro_encaixe` |
| `velocidade` | > 0–10 | `setpts` / `atempo` (fora da cadeia de cor; `grade.json → velocidade`) | b-roll em câmera lenta sutil (0,8–0,9) | video-broll |
| `moldura.estilo` | `nenhuma\|borda\|cantoneiras\|janela\|polaroid` | — (cena `moldura` do motor) | como um insert é emoldurado | cena `moldura`, video-broll, video-animacao-explicativa |
| `moldura.espessura / cor / raio / margem / rotulo` | 0–0,1; token; 0–0,5; 0–0,3; bool | — | espessura 0,004–0,006; cor `primaria`; margem = quanto o insert fica menor que o quadro; `rotulo` = mostra "arquivo · 2018" junto | cena `moldura` |
| `recorte.ancora` | `centro\|rosto\|terco_esq\|terco_dir` | `video.filtro_recorte` (scale+crop) | onde ancorar o corte 16:9 → 9:16 quando não há detecção de rosto | video-cortes-verticais, thumbnail |

Com tudo neutro, a cadeia é `null`. `da.py grade --verificar` confirma que este ffmpeg tem os filtros.

## `legenda` — legenda queimada

| token | faixa | efeito | consumidor |
|---|---|---|---|
| `estilo` | `karaoke\|palavra\|bloco` | karaokê (bloco visível, palavra falada em `cor_destaque`, já ditas em `cor_falada`), uma palavra por vez (só a falada, em `cor_destaque`, todas do mesmo tamanho dentro da cue), ou bloco estático em `cor` | `texto.estados_da_legenda` (PIL) e `ctx.kit.legenda(...).seek(i)` (motor) produzem os mesmos estados; video-legendas, video-animacao-audio, video-cortes-verticais, prancha (amostra) |
| `papel` | nome de papel | papel tipográfico da legenda (normalmente `legenda`) | `Estilo.legenda` |
| `tamanho` | 0,01–0,3 do lado menor | 0,052–0,065 → 56–70 px em 1080 de lado. Abaixo de 0,045 não lê no celular; abaixo de 0,04 o validador avisa | `Estilo.legenda` (`d.px`) |
| `caixa` | `alta\|normal` | caixa alta ajuda a legibilidade de palavras curtas | texto.py |
| `cor`, `cor_destaque`, `cor_falada` | tokens; `cor_falada` pode ser `null` (= `cor`) | texto, palavra sendo dita, palavras já ditas. Validador exige `cor`×`fundo` ≥ 3:1 | texto.py |
| `contorno` | `null` ou `{cor, espessura 0–0,5 em}` | `espessura` = fração do **tamanho da fonte**, espessura **externa visível** (para fora da letra), arredondada para px inteiro e com cantos redondos: 0,11 × 67 px = 7 px em volta de cada glifo (× `escala_x` na horizontal). 0,08–0,12 segura a legenda sobre qualquer footage. A mesma conta no motor e em PIL (medido: 7 px no topo e na base nos dois) | `texto.compor_legenda`, `ctx.kit.legenda`, `ctx.contorno` |
| `sombra` | `null` ou `{dx, dy (−1–1 em), desfoque (0–1 em), alfa, cor}` | frações do tamanho da fonte; `desfoque` é o **raio** de desfoque no sentido do CSS (`text-shadow`: o desvio-padrão do gaussiano é a metade). A sombra é projetada pelo texto **já com o contorno** (com contorno 0,14 e `dy` 0,07, a sombra aparece 0,07 abaixo do contorno; não fica escondida atrás dele). `dy 0,04, desfoque 0,08, alfa 0,6` é o padrão da casa | idem |
| `fundo` | `null` ou `{cor, alfa, raio (em), respiro [x, y] em}` | **uma** caixa atrás do bloco inteiro (lab-ia e neon-shorts): a caixa das linhas (`nº de linhas × altura_linha × tamanho`) mais o `respiro` de cada lado; `raio` em fração do tamanho. Igual no motor e em PIL (até 1.3.0 o PIL desenhava uma caixa por palavra) | idem |
| `posicao.<formato>.y` (`vertical`, `horizontal` e outros) | 0–1 da **altura** | centro vertical do bloco. 0,60 no vertical cai dentro da zona `uniao` (0,15–0,65); 0,84–0,86 no horizontal. O validador avisa quando o bloco com `max_linhas` sai da zona segura | `compor_legenda`, `ctx.kit.legenda`, prancha vertical (mostra sobre as margens) |
| `posicao.<formato>.x` (opcional) | 0–1 da **largura** | centro horizontal do bloco. Sem ele, o centro do **retângulo da zona segura** — no vertical `uniao`, x = 450 de 1080, não 540: a coluna de botões fica à direita. O validador avisa se o `x` declarado põe o bloco para fora da zona | idem |
| `posicao.<formato>.largura_max` (opcional) | 0,1–1 da **largura** | teto de largura só para aquele formato. Os presets declaram `vertical.largura_max: 0.61` (a zona `uniao` deixa 0,611); sem ele vale `legenda.largura_max` | idem |
| `largura_max` | 0,1–1 da **largura** | largura máxima do bloco em todo formato que não declare `posicao.<formato>.largura_max`; 0,76–0,84 no horizontal. O kit **nunca** deixa a legenda passar da zona segura: se o token pede mais do que a zona tem, a cue quebra em linhas e, por último, encolhe — e o validador avisa (`legenda.largura_max = 0,8: no vertical a zona segura 'uniao' só deixa 0,611 da largura…`) | `compor_legenda` (quebra em `max_linhas`, depois encolhe tudo junto), `desenhar_linha` (uma linha: só encolhe) |
| `max_linhas`, `max_palavras` | 1–6; 1–20 | linhas por bloco e palavras por cue (2 e 4 no dossiê; 2 e 5 no lab-ia) | video-legendas (segmentação das cues) |
| `animacao` | `pop\|fade\|nenhuma` | entrada de cada cue/palavra | video-legendas |
| `reservar_em` (opcional) | lista de `vertical`, `quadrado`, `horizontal` (padrão `["vertical", "quadrado"]`) | os formatos em que a peça leva **legenda queimada**. Neles as cenas do kit deixam livre a **faixa da legenda** — o retângulo que ela pode ocupar no pior caso: `max_linhas` linhas (1 no estilo `palavra`) × `tamanho` × entrelinha, na largura máxima, com contorno ou caixa e a sombra — e trabalham na área livre (o lado maior: acima ou abaixo da faixa, com 0,012 de respiro). No dossie vertical a faixa vai de y 1071 a 1238 e a área livre de 288 a 1058: o GC `inferior_esquerda` fica em y 931–1058, logo acima da legenda. Sem a reserva (o padrão do horizontal: longo de YouTube raramente leva legenda queimada), o GC fica na base da zona e **ocupa a faixa da legenda** — no neon-shorts, GC em y 872–1026 e faixa em y 798–937 de 1080: os dois não entram juntos, e é exatamente isso que a prancha horizontal e o teste de movimento mostram (GC na base; a legenda numa tira à parte). Horizontal com legenda queimada → acrescente `"horizontal"` aqui (GC, título, gráfico, crédito e os documentos de aprovação passam a desviar), ou passe `reservar_legenda: true` numa cena só. O validador **avisa** quando a faixa não deixa espaço para o GC num formato reservado (`legenda × GC no vertical: …`), quando deixa menos de 20 % da altura, e quando o vertical ou o quadrado saem da lista com GC e legenda no mesmo lugar; para o horizontal fora da lista ele deixa uma **nota** (`horizontal sem reserva de legenda: …`), que não reprova nem com `--estrito`. Em código: `d.legenda_reservada(formato)` | `d.faixa_legenda`, `d.area_livre`, `ctx.faixa_legenda`, `ctx.area_livre`; cenas `gc`, `titulo`, `barras`, `citacao`, `moldura`; `ctx.kit.credito`, `texto.credito_fonte` |

## `graficos` — GC, tarja, ícones, dados, crédito

| token | faixa | efeito | consumidor |
|---|---|---|---|
| `gc.estilo` | `barra\|caixa\|linha\|etiqueta` | lower third: barra lateral em `cor_acento`, caixa chapada, linha fina, etiqueta compacta | cena `gc`, video-motion-graphics |
| `gc.posicao` | `superior_esquerda`, `superior_centro`, `superior_direita`, `centro`, `inferior_esquerda`, `inferior_centro`, `inferior_direita` (7 posições; não há `centro_esquerda`/`centro_direita`) | canto do GC dentro da zona segura | cena `gc` |
| `gc.papel_nome / papel_cargo` | papéis (padrão `subtitulo` / `dados`) | tipografia do nome e do cargo | cena `gc` |
| `gc.tamanho_nome / tamanho_cargo` | 0,005–0,3 (padrão 0,042 / 0,022) | tamanhos. `tamanho_cargo` abaixo de 0,022 (o mínimo legível) gera aviso; os presets usam 0,024–0,030 | cena `gc` |
| `gc.cor_nome / cor_cargo / cor_fundo / cor_acento` | tokens (padrão `texto` / `texto_suave` / `fundo` / `primaria`) | cores | cena `gc` |
| `gc.alfa_fundo` | 0–1 (padrão 0,86) | opacidade do fundo do GC (da caixa nos estilos `barra` e `caixa`; do painel de proteção no `degrade`). Abaixo de 0,6 sem `protecao`, o validador avisa | cena `gc` |
| `gc.protecao` (opcional) | `auto\|nenhuma\|sombra\|contorno\|degrade` (padrão `auto`) | como o GC se protege do vídeo que passa atrás, sempre na cor de apoio `cor_fundo`: `sombra` = halo desfocado em volta das letras; `contorno` = anel de 0,09 em; `degrade` = painel `cor_fundo × alfa_fundo` de bordas esfumadas atrás do bloco. `auto` = `degrade` no estilo `linha` (o único sem caixa: sem apoio, texto escuro sobre footage ficava a 1,2:1) e `nenhuma` nos demais. O validador avisa `linha` com `nenhuma` e nome/cargo com menos de 3:1 contra `cor_fundo` (no `etiqueta`, cargo contra `superficie`) | cena `gc` (devolve a efetiva em `layout.protecao`) |
| `tarja.estilo / papel / tamanho / cor_fundo / cor_texto / inclinacao` | `chapada\|contorno\|sublinhado`; papel; 0,005–0,3; tokens; −45–45° | faixa de destaque (sobretítulo, "AO VIVO", palavra-chave) | `_tarja.js` (título), video-animacao-explicativa |
| `icones.estilo / espessura` | `traco\|cheio`; 0–0,05 | estilo de ícones e espessura do traço | video-animacao-explicativa |
| `dados.eixo / grade / rotulo` | tokens | cores de eixo, linhas de grade e rótulos dos gráficos (séries vêm de `cor.dados`) | cena `barras`, video-animacao-explicativa |
| `citacao_fonte.papel / tamanho / posicao / cor` | papel; 0,005–0,2; uma das 7 posições; token (padrão `texto_suave`) | crédito "Fonte: IBGE, 2024", sempre dentro da zona segura e fora da faixa da legenda (a posição vale dentro da área livre: `inferior_*` no vertical fica logo acima da legenda); `_centro` centraliza na zona. `tamanho` abaixo de 0,022 gera aviso; os presets usam 0,022–0,024 | peça única: `ctx.kit.credito` (cenas `barras`, `citacao` e as de outras skills) e `texto.credito_fonte` (PIL) |
| `citacao_fonte.prefixo` | texto (padrão `"Fonte: "`; `""` = sem prefixo) | o que vem antes do crédito. Nunca é duplicado: `"Fonte: IBGE"` passado com o prefixo `"Fonte: "` continua `Fonte: IBGE` | idem |

## `thumbnail`

| token | faixa | efeito | consumidor |
|---|---|---|---|
| `max_palavras` | 1–12 | palavras no título da thumb (3–4) | quem monta a thumbnail (direto pelo kit: `kit-api.md` §17.1) |
| `papel`, `tamanho` | papel; 0,02–0,6 do lado menor | fonte e tamanho do título (0,17–0,2 → 122–144 px em 720 de altura) | `texto.Estilo.thumbnail`, `ctx.texto` |
| `cor`, `cor_destaque` | tokens (padrão `texto`, `primaria`) | texto e a palavra que salta | `texto.Estilo.thumbnail(d, destaque=True)`, `ctx.cor` |
| `contorno` | `null` ou `{cor, espessura em}` | contorno do texto (0,05), com a mesma semântica de `legenda.contorno`: fração do tamanho da fonte, para fora da letra (0,05 × 144 px = 7 px) | `texto.Estilo.thumbnail`, `ctx.contorno`, prancha |
| `tratamento_foto.saturacao / contraste` | 0–3 | tratamento da foto da thumb (dossiê: saturação 0 = P&B; neon: 1,15) | quem monta a thumbnail (o kit não aplica sozinho: é a cadeia que você passa à foto) |
| `tratamento_foto.recorte_pessoa`, `contorno_pessoa` | bool; `null` ou `{cor, espessura 0–0,1 do lado menor}` | recortar a pessoa do fundo e contorná-la (`primaria`, 0,012) | quem monta a thumbnail (o recorte real da pessoa é trabalho de quem a monta; a prancha usa silhueta) |
| `fundo` | token, `gradiente:<nome>` ou `foto` | o que fica atrás | quem monta a thumbnail, pelos derivados `thumbnail.fundo_css` (motor) e `thumbnail.fundo_hex` (PIL) |
| `zona_proibida` | `nenhuma` ou um canto | canto que o texto não ocupa; `inferior_direita` porque o YouTube cobre com a duração (ver `plataformas.md` §5) | `d.zona_proibida()`, `ctx.zona_proibida()`, prancha (hachura) |
| `zona_proibida_tamanho` | `[largura, altura]` em fração da largura e da altura do quadro (padrão `[0.25, 0.22]`) | tamanho do retângulo proibido. O padrão é a reserva do selo de duração em `plataformas.json` (`thumbnail.youtube.zona_timestamp.reserva_recomendada`): 320 × 158 px em 1280 × 720. A prancha hachura exatamente este retângulo | idem |

## `som`

| token | faixa | efeito | consumidor |
|---|---|---|---|
| `identidade` | texto | a sonoridade em uma frase | video-mixagem, video-efeitos-sonoros |
| `loudness.longo / curto` | `{lufs −40–−5, pico_real −12–0 dBTP}` | alvos para vídeo longo e peça curta (−14 LUFS / −1 dBTP nos presets; é estimativa de mercado, nenhuma plataforma publica) | video-mixagem, video-cortes-verticais, `video.conferir_loudness`, conferência final (`da conferencia`: `longo` para `render/final.mp4`, `curto` para `cortes/*.mp4`) |
| `sfx.entrada / enfase / texto` (+ extras) | texto | família de efeito por gatilho (`whoosh`, `impacto`, `tick`, `blip`) casada com as `ancoras` que as cenas devolvem no carimbo | video-efeitos-sonoros |
| `musica.clima`, `musica.bpm` | texto; `[min, max]` 20–300 | clima e faixa de andamento da trilha | video-mixagem, video-montagem |

## `marca`

| token | faixa | efeito | consumidor |
|---|---|---|---|
| `logo` | arquivo relativo a `da/logos/` ou `null` | logo do canal (entra em `data-da-livre`; o sha do arquivo entra na identidade da DA) | cena `titulo` (assinatura), video-publicacao, thumbnail |
| `assinatura` | `"@canal"` ou `null` | assinatura em texto; a cena `titulo` mostra no rodapé quando `assinatura: true` | cena `titulo`, cortes verticais |
| `posicao_logo` | as mesmas 7 posições de `gc.posicao` | canto do logo/marca d'água | video-motion-graphics, cortes |
| `marca_dagua` | bool | manter logo discreto durante o vídeo | video-montagem, cortes verticais |

## Tokens derivados (só na resolvida e no CSS, não se escrevem no `da.json`)

`cor.permitidas` (lista do auditor), `cor.dados_tokens` (para cada item de `cor.dados`, o nome da paleta que foi escrito no `da.json`, ou `null` se era hex — `cor.dados` em si fica sempre em hex), `<cor>_hex`, `<arquivo>_abs`, `thumbnail.zona_proibida_ret` (`{x, y, w, h}` em frações do quadro, ou `null`; é o que `d.zona_proibida()` e `ctx.zona_proibida()` devolvem em px), `thumbnail.fundo_tipo` (`cor`, `gradiente` ou `foto`) com `thumbnail.fundo_hex` (cor chapada resolvida; `null` nos outros tipos) e `thumbnail.fundo_css` (valor pronto para `background`: o hex ou o `linear-gradient(…)` do gradiente nomeado), `papeis.<p>.{arquivo_abs, css_familia, variavel, eixos_fonte, eixos_efetivos, eixos_ordem, css_variacao}`, `formatos.<f>.{fps_num, fps_den, fps_float, lado_menor}`, `gradientes.<g>.{paradas_hex, css}`, `_meta.{sha256, revisao, aprovada, aprovada_em, alterada_apos_aprovacao, nome, slug, raiz, da_json, pasta_da, build, kit_versao, compilado_em, ancestrais}`.
