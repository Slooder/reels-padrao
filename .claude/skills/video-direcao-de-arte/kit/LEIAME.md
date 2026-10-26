# Kit de direção de arte (DA) — núcleo + motor de render

Caminho final: `"$CRIABR_SKILLS"/video-direcao-de-arte/kit/`. Tudo aqui localiza os vizinhos pela própria posição
(`Path(__file__)` em Python, `import.meta.url` em Node), então a pasta pode ser copiada inteira para qualquer lugar.

Ideia: cada projeto de vídeo tem UMA fonte de verdade visual, `<projeto>/da/da.json`. Nenhuma skill decide cor,
fonte, curva, grade, legenda ou moldura sozinha — todas leem tokens pela API deste kit. Sem DA não se renderiza nada.

As seis camadas de submissão: **C1** descoberta obrigatória (`da.py achar`, código 2 sem DA) · **C2** só tokens
(`da.py lint`) · **C3** auditor de estilos computados no motor (`motor/auditor.js`) · **C4** carimbo `<saida>.da.json`
(`da.py carimbar` / `conferir-carimbo`) · **C5** conferência final (`da.py conferencia`, um comando deste kit e não uma skill: DA aprovada,
lint, carimbos, loudness e limites de plataforma → `qa/relatorio.json`) · **C6** bloco no `CLAUDE.md` do projeto.

## Arquivos

| arquivo | o que é |
|---|---|
| `bin/da` | Executável da CLI (`sh`): acha um Python 3.10+ com Pillow (`VIDEO_OPS_PYTHON` → `python` → `/usr/local/bin/python3` → `PATH` → `/usr/bin/python3`) e roda `da.py`. É a chamada que toda a documentação usa (`"$CRIABR_SKILLS"/video-direcao-de-arte/kit/bin/da <subcomando>`): funciona em zsh, bash e sh, com espaço no caminho; 127 se não houver Python utilizável. Precisa do bit de execução (a cópia com `cp -R`/`rsync -a` preserva). |
| `da.py` | CLI (`bin/da --help`, tudo em PT-BR) e módulo importável. Subcomandos do núcleo: `init`, `achar`, `validar`, `compilar`, `mostrar`, `token`, `presets`, `salvar-preset`, `remover-preset`, `extrair`, `rotas` (`criar`, `listar`, `comparar`, `adotar`), `aprovar`, `revisar`, `plataformas`, `lint`, `carimbar`, `conferir-carimbo`, `grade`. Códigos de saída: 0 ok · 1 reprovado/erro · 2 nenhuma DA · 64 uso incorreto. |
| `da_ext_motor.py` | Extensão (ponto `da_ext_*.py`) que acrescenta `prancha`, `teste-movimento` e `render` (repasse ao motor sob a trava). Importável: `achar_node()`, `render([...], da_obj=d, validar_antes=None)`, `imagem_de_teste()`, `gerar_prancha(d, formatos, referencia, foto, escala, reaproveitar)`, `gerar_teste_de_movimento()`, `duracao_do_teste()`, `comparar_rotas()` (o `rotas comparar`), `achar_referencia()`, `referencia_tratada()`, `legenda_de_amostra()`; registra em `da.APOS_APROVAR` o gancho que regenera a prancha com o selo de aprovação. O `render` confere os argumentos fora da fila quando a trava está ocupada (erro de uso volta em < 1 s) e nunca entra na trava com `--validar` ou `--help`. |
| `da_ext_conferencia.py` | Extensão que acrescenta `conferencia`, a **conferência final** do projeto (C5). Só compõe o que o kit já tem — `da.validar` + DA aprovada e não alterada, `da.lint(None, estrito=True)`, `da.conferir_carimbo(…, exigir_aprovada=True)` (pastas de peças, `broll/tratado` e insumos carimbados das composições), `video.conferir_loudness` (`som.loudness.longo` para `render/final.mp4`, `curto` para `cortes/*.mp4`), `video.sondar` contra `da.plataforma(nome)` — e chama por posição as conferências das irmãs que o projeto usa (`<skills>/video-pesquisa-ia/scripts/fatos.py validar --estrito`, `conferir-roteiro --estrito`, `conferir-storyboard`; créditos de `broll/licencas.json` em `broll/creditos.md`); skill ausente = item `info`. Grava `qa/relatorio.json` (contrato: `versao`, `ok`, `verificado_em`, `da_sha256`, `alvos`, `resumo`, `itens`) e `qa/relatorio.md`; `--previa` grava `qa/previa.*`. Não renderiza nada e só escreve em `qa/` (lê a DA em memória: não recompila `da/build/`); não tem número de limite no código. Importável: `conferir(caminho, de, alvos, cortes, plataformas, previa, saida, gravar)` → `Relatorio` (dict + atributos `json`, `md`, `raiz`, `entregaveis`), `listar_entregaveis()`, `caminhos_do_relatorio()`, `texto_resumo()`, `texto_md()`. |
| `trava.py` | Trava global da operação (uma tarefa pesada por vez na máquina de 8 GB) que **nunca fica presa**: `python3 trava.py [--espera-max SEG] [--inatividade SEG] [--prazo SEG] -- <comando…>`, `--estado`, `--liberar [--se-ocioso SEG]`. flock em `/tmp/video-ops-render.lock`, fila com aviso a cada 15 s dizendo há quanto tempo o dono está sem progresso, reentrante por `VIDEO_OPS_TRAVA=<pid>` (ou por linhagem, se a variável se perder). O comando roda em grupo de processos próprio: sinal no dono mata a árvore inteira antes de soltar a trava; dono morto = quem assume encerra os órfãos registrados; vigia de inatividade mata e sai com 124. Importável: `trava.rodar([...], capturar=True, inatividade=120, entrada=…)` → `Resultado`, `trava.executar`, `with trava.Trava(): …`, `trava.estado()`, `trava.liberar_ocioso()`. |
| `texto.py` | Texto em PIL fiel aos papéis da DA e **igual ao do motor** para o mesmo token (vão = espaço real da fonte, contorno para fora da letra, sombra com raio do CSS, caixa de fundo única): fonte variável (eixos), tracking, caixa alta, `escala_x`, quebra sem órfã, encolher até caber, medição e RGBA recortado. `Estilo.do_papel`, `Estilo.legenda`, `Estilo.thumbnail`, `compor_legenda` (várias linhas, dentro da zona segura da plataforma; `apenas=i` para o estilo `palavra`), `estados_da_legenda` (os estados de uma cue conforme `legenda.estilo`), `escalar_estilo`, `compor_bloco` (palavra a palavra, cada uma com seu estilo), `desenhar_linha` (= `compor_legenda` com uma linha), `desenhar`, `credito_fonte`, `quebrar_linhas`, `quebrar_palavras`, `vao_entre_palavras`, `encolher_ate_caber`, `medir`, `colar`. |
| `video.py` | ffmpeg da casa: `sondar` (ffprobe completo; WebM com `-c:v libvpx-vp9` para ver o alfa), `executar` (trava + `.parcial` + rename; `entrada=` para pipe), `args_encode` (H.264 yuv420p bt709 +faststart, AAC 48 kHz; fps do formato da DA), `args_codec`, `filtro_tratamento` (lê `grade.json`), `filtro_recorte` (scale+crop pares, âncora/foco), `filtro_encaixe` (vídeo inteiro sobre fundo desfocado, recorte ou faixas), `filtro_loudnorm` + `medir_para_loudnorm` (alvo de `som.loudness`, uma ou duas passagens), `medir_loudness`/`conferir_loudness` (ebur128), `extrair_quadro`, `folha_de_contato` (PIL, célula na proporção da peça), `entrada_com_alfa`; composições que carimbam com a proveniência dos insumos: `compor_overlay` (alfa de WebM/MOV/PNG, trecho da base), `compor_cues` (N overlays numa passada, faixa RGBA por pipe), `juntar` (transições de `movimento.transicoes` por concat/xfade), `encaixar_em_janela` (insert na janela da moldura, girado junto), `Codificador`/`codificar_quadros` (quadros PIL → h264, vp9alfa ou prores4444). |
| `motor/` | Motor de render HTML → imagem/vídeo (abaixo). |
| `da_esquema.json` | JSON Schema (draft 2020-12) do `da.json` v1 + validador próprio enxuto em `da.py` (não há lib jsonschema). |
| `presets/*.json` | Presets embutidos, completos e válidos: `dossie` (a casa), `lab-ia`, `editorial-claro`, `neon-shorts`, `quadro-negro`. O `init` copia as fontes para `<projeto>/da/fontes/`. |
| `fontes/` | Fontes OFL usadas pelos presets (Archivo SemiExpanded Black, IBM Plex Mono, Montserrat/Roboto/Fira Code variáveis, Urbanist, Bebas Neue). |
| `fontes/LICENCAS/` | `OFL-<Prefixo>.txt` de cada família (aviso de direitos lido da tabela `name` da própria fonte + texto da SIL OFL 1.1) e `LEIAME.md` com a tabela arquivo → licença. `init` e `salvar-preset` copiam a licença junto com cada fonte (`da.licenca_da_fonte`). |
| `plataformas.json` | Zonas seguras, specs e limites por plataforma; origem das `margens_seguras` dos presets. |
| `modelos/CLAUDE.projeto.md` | Bloco `<!-- DA:INICIO --> … <!-- DA:FIM -->` que o `init` escreve/atualiza no `CLAUDE.md` do projeto. |
| `package.json`, `node_modules/playwright-core` | Dependência Node do motor (playwright-core 1.49.1, sem download de browser: usa o Chromium headless shell já instalado). |
| `testes/test_da.py` | 72 testes do núcleo (`python3 -m unittest testes.test_da`, ~8 s). |
| `testes/test_suficiencia.py` | 23 regressões da API de que as skills irmãs dependem (~45 s, trava real, vídeos ≤ 320×180): legenda dentro da zona `uniao` nos 5 presets, vão e contorno com a semântica única, **paridade motor × PIL** (mesma cue pelos dois caminhos: largura ≤ 3 %, palavras e contorno a ≤ 1 px), validador no eixo x, plataformas canônicas e acessores, zona proibida, intermediários com `_`, proveniência dos insumos, `Codificador` nos três codecs e sem segurar a trava (ffmpeg que morre, que não lê, exceção no produtor), `compor_cues` com 64 cues em 10 s numa passada, `juntar` com transições, `compor_overlay` com trecho, encaixe desfocado, loudnorm em duas passagens, `ctx.kit` com várias instâncias, crédito único, `itens`/`plataforma` nos params, moldura na zona e janela girada, transição no teste de movimento. |
| `testes/test_skill.py` | 37 regressões da qualidade da skill (~10 s, sem browser nem ffmpeg): `bin/da` em zsh/bash/sh e os comandos do SKILL.md e do bloco do CLAUDE.md executados como estão escritos; forma única de alfa; regra exata da identidade; lint de Python e "não conferido"; `data-da-livre` por elemento; nenhum `__pycache__`; licença de cada fonte; delimitadores do bloco por linha inteira + backup; `--forcar` sem `--base`; `extrair` ignorando a própria folha; rótulo da trava sem linha de comando; erro de uso do `render` sem esperar a fila da trava; coerência dos números da documentação com o código; exemplos de código do `kit-api.md` (cena de exemplo no lint estrito, blocos Python com nomes que existem); **escopo final** da documentação e dos textos gerados (`CLAUDE.md` e `DA.md` do projeto): nenhuma skill que não existe é citada, a video-pauta-midia está no mapa do pipeline, a C5 aparece como comando com o contrato e todas as opções da CLI, e a thumbnail aponta a receita do kit. |
| `testes/test_produto.py` | 25 regressões do produto visual e do método (~100 s; quadros PNG a 270×480 e um ato do teste de movimento): presets sem aviso e acima do mínimo legível; validador avisando legenda × GC, texto pequeno, GC `linha` sem proteção, rota incoerente (cores quase idênticas, gradiente chapado); `cor.dados` com nomes da paleta; faixa da legenda e área livre iguais em Python e no motor; **vertical sem colisão nos 5 presets** (GC, cartela com assinatura, barras com 8 categorias + crédito, citação com autor longo, moldura — todos na zona `uniao` e fora da faixa da legenda); GC `linha` legível sobre footage claro; prancha com a legenda de `texto.py`, faixa 1:1 e nada além da margem; `digita` linha a linha; teste de movimento que não corta animação (Python × JS na mesma duração); `extrair` com acento de 0,7 % da área, pasta e `--regiao`; `rotas` criar/listar/comparar/adotar; `aprovar` conferindo e regenerando a prancha; `remover-preset` e fontes órfãs; **GC da prancha e do teste de movimento = GC da cena `gc` padrão, por formato**; formato sem reserva (aviso no vertical/quadrado, nota no horizontal, `faixa_reservada` na info da legenda); moldura com rótulo de 40 caracteres + sub de 29 (e sub de 47 sozinho) dentro da zona nos 5 estilos, no vertical e no horizontal, com `rotulo_na_zona` medido. |
| `testes/test_conferencia.py` | 14 regressões da conferência final (~15 s sem fila na trava; três clipes de 2 s, ≤ 320×180, gerados uma vez): caso ok com o relatório conferido campo a campo contra o contrato e sem tocar em nada fora de `qa/`; CLI (resumo, `--json`, `--saida`, erros de uso com código 64, projeto sem DA com código 2); DA não aprovada (erro, e aviso com `--previa`, que grava `qa/previa.json` sem tocar no portão); DA alterada depois da aprovação (sem recompilar `da/build/`); DA inválida e `da.json` ilegível (relatório reprovado, `da_sha256` vazio); peça sem carimbo, peça de outra DA, intermediário com `_`, flag de zona do carimbo; cor literal numa cena e arquivo que o lint não lê; corte com loudness fora do alvo, a conferência de um corte só e a cadeia de insumos dele; entregável acima do limite de duração (com um `plataformas.json` de teste: o limite é lido, não embutido) e abaixo do mínimo; tipo e plataformas de cada entregável; registro de licenças × `creditos.md`; ficha de fatos chamada por posição, com skill presente, ausente (`info`) e quebrada. |
| `testes/test_trava.py` | 19 testes de robustez da trava com arquivo de trava privado (~25 s): entrada por pipe, stderr volumoso, vigia de inatividade e prazo, SIGTERM matando filhos/netos/outra sessão, dono morto por SIGKILL com limpeza dos órfãos, reentrância por linhagem, `--estado`/`--liberar`. |
| `testes/test_motor_robustez.py` | 20 regressões do motor (~180 s, trava real, renders ≤ 480×270): opções estritas e erro de uso antes da fila, ffmpeg que morre ou não lê, laço sem fim em `seek`, SIGTERM/SIGKILL sem órfãos, `--quadro T` idêntico ao quadro T do vídeo nas 5 cenas, cena impura reprovada, 30 caminhos de escape do auditor pelos estilos (`test_12`) e mais 35 pelo que o estilo computado não mostra ou anima fora de `seek` (`test_20`: controles nativos, imagem por CSS, marcador, seleção, emoji, SMIL, mensagens, relógios e sorteios, imagem animada, quietude), DA que muda durante o render, DA alterada após aprovação, barras verticais com 8 categorias, `video.executar` com pipe. |
| `testes/test_motor.py` | 15 testes (o 13º cobre também `da.py render --cena …` sem `--` e `cena` relativa na fila) de ponta a ponta do motor (`python3 -m unittest testes.test_motor -v`, ~25 s): init com 2 presets → prancha (tamanho e diferença entre presets) → h264 a escala 0,5 → alfa em ProRes 4444 e VP9 (decodifica e confere o canal) → auditor reprovando cor literal, fonte fora da DA e transition, aprovando `data-da-livre` → `--sem-auditoria` no carimbo e reprovado pelo `conferir-carimbo` → lock velho recompila → teste-movimento → fila que continua após falha → erros de uso (64) e sem DA (2) → `texto.py`/`video.py`. Pasta temporária com espaço e acento; `VIDEO_OPS_HOME` isolado; trava real. |
| `VERSAO` | Versão do kit (semver). Entra no `da.lock`, nos carimbos e na checagem "kit atualizado ⇒ recompilar". |

## O que `compilar` gera em `<projeto>/da/build/`

- `da.resolvida.json` — herança aplicada, padrões do esquema, tokens de cor resolvidos em `<chave>_hex`, arquivos em `<chave>_abs`, fontes inspecionadas (`variavel`, `eixos_fonte`, `eixos_efetivos`), formatos com `fps_num/fps_den`, `_meta`.
- `da.css` — `@font-face` por papel (URL `file://` codificada, fonte variável com faixas) e `:root` com `--da-cor-<chave>`, `--da-cor-<chave>-rgb`, `--da-dado-<n>`, `--da-neutro-<n>`, `--da-gradiente-<nome>`, `--da-fonte/peso/largura/estilo/tracking/caixa/altura-linha/eixos/escala-x-<papel>`, `--da-escala-<nome>`, `--da-margem`, `--da-calha`, `--da-raio`, `--da-traco`, `--da-sombra`, `--da-dur-<nome>`, `--da-escalonamento`, `--da-curva-<nome>`; classes `.da-<papel>`. Tamanhos são `calc(var(--da-lado) * fração)`; o palco fixa `--da-lado` em px.
- `da.js` — `window.DA` (congelado). · `grade.json` — cadeias ffmpeg por formato. · `da.lock` — identidade do build. · `../DA.md` — leitura humana.

## Motor de render (`motor/`)

| arquivo | papel |
|---|---|
| `render.mjs` | CLI. `node render.mjs --cena <modulo.js> --saida <arq> [--formato horizontal\|vertical\|quadrado\|thumbnail\|LxA\|Lxauto] [--dur S] [--fps N/D] [--params '<json>'\|@arq.json] [--alfa] [--quadro T\|fim] [--codec h264\|prores4444\|vp9alfa] [--escala 0.5] [--sem-auditoria] [--da <da.json>] [--de <pasta>] [--fila fila.json] [--json] [--validar] [--inatividade SEG]`. Opção desconhecida = erro 64. Erros de uso saem antes da fila; depois reexecuta-se sob `trava.py` se não estiver na trava (`--sem-trava` desliga), repassando sinais. Aborta (matando ffmpeg e Chromium e apagando o `.parcial`) em SIGINT/SIGTERM/SIGHUP, quando o dono da trava ou o processo pai morre, e depois de `--inatividade` segundos sem progresso (padrão 120). |
| `comum.mjs` | Descobertas: Chromium (`VIDEO_OPS_CHROME`, senão o `chromium_headless_shell-*` mais novo em `~/Library/Caches/ms-playwright`; erro acionável com o comando de instalação), python, ffmpeg/ffprobe; ponte com `da.py` (`achar --json` + `compilar --se-preciso`, `carimbar` com `--sha-esperado`/`--origem`, todos com prazo de 120 s); `reexecutarSobTrava` assíncrono que repassa sinais; `ffprobe` que lê alfa de WebM. |
| `palco.html` | Página do render: fixa `--da-lado`, injeta `da.css` + `da.js`, espera `document.fonts.load` de cada papel (falha se uma fonte da DA não carregar), importa `runtime.js`, `auditor.js` e a cena, espera `<img>`/`<image>`, liga o grão (opcional), expõe `window.seek(t)`, `frameKey(t)`, `DUR`, `READY`/`ERR`, `__palco.auditar()` e `__palco.pureza()`. Antes de importar a cena, intercepta relógios (`requestAnimationFrame`, `setTimeout`, `setInterval`, `requestIdleCallback`, `Date.now`, `new Date()`, `performance.now`/`timeOrigin`, `document.timeline.currentTime`, `event.timeStamp`, `Intl.DateTimeFormat` sem data, `Temporal.Now`), sorteios (`Math.random`, `crypto.getRandomValues`/`randomUUID`) e agendadores (`MessagePort`/`window`/`BroadcastChannel.postMessage`, `scheduler.postTask`, `Worker`, `queueMicrotask` encadeado) — o uso vira violação — e registra os shadow roots. `__palco.imagens()` lista toda imagem que a página usa, para o `render.mjs` conferir no disco se alguma é animada. |
| `runtime.js` | Helpers do `ctx` (abaixo), solver de cubic-bezier, `Timeline`, entradas/saídas da DA, grão determinístico por seed (6 ladrilhos, `data-da-livre`), texto com `escala_x`, medição independente de transform, `contraste()`. |
| `auditor.js` | C3, sem escapes implícitos: em dezenas de instantes (grade temporal + âncoras da cena + bordas de entrada/saída, teto 64; só T com `--quadro`) percorre a **página inteira** — html, body, fora do `#palco`, shadow roots, `::before`/`::after` — inclusive o que está invisível agora (opacity 0, display none, fora do quadro), e confere `color`, `background-color`, cores de `background-image`/`border-image` (gradientes), `border-*-color` (largura > 0), `outline-color`, `box-shadow`, `text-shadow`, `drop-shadow()`, `text-decoration-color`, `-webkit-text-stroke/fill-color`, `fill`/`stroke`/`stop-color`/`flood-color` (SVG, inclusive em `<defs>`), `font-family` efetiva e `transition`/`animation` + `document.getAnimations()`. Reprova também: `img/video/canvas/<image>/iframe` e `url()` sem `data-da-livre`, `filter`/`backdrop-filter` que alteram cor, `mix-blend-mode`, `data-da-livre` no palco, os usos de API de tempo/acaso/agendamento registrados pelo palco, controles nativos (`input`, `progress`, `meter`, `select`, `textarea`, `button`, `audio`), `content: url()` no elemento, `list-style-image`, `paint()`, cor do `::marker`, texto selecionado, `CSS.highlights`, emoji colorido e — mesmo dentro de `data-da-livre` — SMIL, `<marquee>`, mídia tocando e `contenteditable` com foco. Permitidos: paleta + dados + neutros, qualquer alfa dessas cores (inclusive `color(srgb …)` de `color-mix`), `transparent`, tolerância de 3 por canal. Único escape: subárvores `data-da-livre`, devolvidas em `livres` para o carimbo (a camada de grão do kit é reconhecida à parte). Relatório: seletor curto, propriedade, valor, token mais próximo. |
| `cenas/` | Cenas-base canônicas (100 % tokens; horizontal e vertical): `titulo` (cartela com tarja + título + filete + subtítulo), `gc` (lower third nos 4 estilos de `graficos.gc`: barra, caixa, linha, etiqueta; proteção sobre vídeo por `graficos.gc.protecao`), `moldura` (nenhuma/borda/cantoneiras/janela/polaroid; devolve a `janela` transparente em px), `citacao` (aspas, frase palavra a palavra, autor, crédito), `barras` (horizontal; empilhado no vertical), `prancha` (a prancha de DA), `teste_movimento` (três atos; exporta `duracao()`). Todas trabalham em `ctx.area_livre` (zona segura menos a faixa da legenda; parâmetro `reservar_legenda`). Compartilhados: `_tarja.js`, `_legenda.js` (a legenda do motor + `fraseDeAmostra`), `_credito.js`, `_moldura.js`. |

### Contrato de cena (módulo ES puro — nada de `document` no nível do módulo)

```js
export const meta = { nome, descricao, dur_padrao, formatos: ['horizontal', …], alfa_padrao: false, grao: false,
  params: { titulo: { tipo: 'texto', obrigatorio: true, descricao }, foto: { tipo: 'arquivo', padrao: null }, … } };
export async function build(palco, params, ctx) { /* monta o DOM dentro de `palco`, mede, devolve info (vai para o carimbo) */ }
export function seek(t) { /* estado visual PURO em t — chamado fora de ordem */ }
export function key(t) { /* opcional: chave de quadro estático (cache) ou null */ }
export function ancoras() { /* opcional: [{t, nome, tipo}] para a skill de SFX */ }
export function duracao({ DA, params, formato, pedida }) { /* opcional: a cena calcula a própria duração (roda no Node, antes do browser) */ }
```

Tipos de `params`: `texto`, `numero`, `inteiro`, `booleano`, `lista`, `objeto`, `arquivo` (vira URL `file://`, existência conferida),
`cor` (token da DA), `papel`, `opcao` (`opcoes: [...]`); `min`/`max`; validação em Node antes de abrir o browser (código 64).

### `ctx` (criado por `runtime.criarCtx`)

`DA`, `L`, `A`, `u` (lado menor), `fps`, `duracao` (= `DUR`, total da peça), `formato`, `orientacao`, `transparente`, `params` ·
`px(fracao)`, `tam(nomeDaEscala)`, `cor(token)` (só tokens ou hex da DA; senão erro), `rgb`, `alfa(token, a)` → `rgba()`, `dado(i)`,
`contraste(a, b)`, `legivel(fundo, a, b)` · `fonte(papel)`, `estilo(el, papel, {tam, cor})`, `texto(papel, str, {tam, cor, maxW, wrap, alinhar})`
(wrapper com `escala_x` por `scaleX`, como o motor da casa), `medir(w)`, `ajustar_texto(w, larguraMax, {min, alturaMax, maxLinhas})`, `sem_orfa(w)` ·
`ease(curva)`, `prog(t, t0, dur, curva)`, `lin`, `dur(nome)`, `escalonamento`, `tl()` (Timeline: `add`, `escalonar`, `p`, `lin`, `t0`, `t1`, `fim`, `ancoras`),
`entrada(el, p, tipo, op)`, `saida(el, p, tipo, op)`, `vida(el, t, {de, ate, entrada, saida})`, `fim_saida()` ·
`margens(plataforma)`, `plataformas()`, `area_segura(plataforma)`, `area_livre(plataforma, {legenda})`, `faixa_legenda(plataforma)`, `grade()`, `col(n)`, `margem`, `calha`, `raio`, `traco` ·
`rng(seed)`, `el`, `svg`, `place`, `rectDe`, `esc`, `clamp`, `lerp`, `mapa`, `grao()`, `sub({L, A, palco, dur, alfa})` (ctx aninhado: a prancha monta cenas em quadros reduzidos).

Entradas: `sobe`, `desce`, `desliza`, `mascara` (clip-path), `escala`, `fade`, `digita` (caractere a caractere e linha a linha, com o corte na fronteira de cada glifo medida no texto). Saídas: `fade`, `desce`, `sobe`, `mascara`, `corte`.

### Saídas e verificação

- `--quadro T` → PNG (alfa se `--alfa`); `Lxauto` fixa a altura pelo conteúdo (só PNG). Dimensão conferida no cabeçalho IHDR.
- Vídeo: PNG por pipe (`image2pipe`), cache por `key(t)`, `ffmpeg -threads 2`; cada escrita corre contra a saída do ffmpeg (ffmpeg morto = job falha em segundos, com o quadro e o sinal na mensagem). O ffprobe confere resolução, fps, nº de quadros e `pix_fmt` no `<saida>.parcial`, o carimbo é calculado sobre ele com a identidade da DA do início, e só então o `.parcial` vira a saída.
  `h264` = libx264 crf 17 yuv420p **bt709 marcado** (via `scale=…out_color_matrix/primaries/transfer` + `-x264-params colorprim…`, porque o ffmpeg 8 ignora `-color_primaries/-color_trc` com libx264) +faststart, `.mp4`.
  `prores4444` = `prores_ks -profile 4444 yuva444p10le` (o decoder reporta `yuva444p12le`), `.mov`, para o Premiere.
  `vp9alfa` = `libvpx-vp9 yuva420p -auto-alt-ref 0`, `.webm`, para compor via ffmpeg — para LER o alfa é obrigatório `-c:v libvpx-vp9` antes do `-i` (`video.entrada_com_alfa`).
- Carimbo (C4) gravado pelo próprio `da.py carimbar` com `ferramenta: motor`, formato, `parametros` (cena, params, fps, codec, escala, quadros, reaproveitados, âncoras, `layout` devolvido pelo `build`, `livres` = elementos `data-da-livre` vistos pelo auditor, Chromium, tempo) e `auditoria: ok|pulada`.
- `--fila fila.json`: lista de jobs `{cena, saida, formato, dur, fps, params, alfa, quadro, codec, escala, sem_auditoria}` num único browser; continua após falha; resumo; código 1 se algum falhou.

### `da.py prancha [--formato horizontal|vertical|ambos] [--referencia <imagem|vídeo>] [--foto <img>] [--saida PASTA] [--escala F]`

Gera `da/prancha.png` (1920 × altura automática, ~7 000 px) e `da/prancha_vertical.png` (1080 × ~7 800 px) com a cena `motor/cenas/prancha.js`:
cabeçalho com revisão e estado (`RASCUNHO — AGUARDANDO APROVAÇÃO` / `APROVADA EM dd/mm/aaaa`); referências do conceito com a nota de cada uma
(quando `conceito.referencias` tem imagens); paleta com nome, hex e contraste WCAG (5 colunas iguais; série de dados mostrando o token quando
o item é um nome da paleta); papéis tipográficos e escala; componentes montados pelo próprio motor (cartela de título, GC + legenda, moldura);
**Em escala 1:1** — uma faixa do quadro sem redução, sangrada de borda a borda, com GC e legenda sobre o quadro do projeto (juntos onde a DA reserva a faixa da legenda; em duas tiras — GC na posição da produção, legenda sozinha — onde não reserva e os dois se tocam); tratamento
ANTES/DEPOIS (`grade.json` aplicado via `da.py grade`; 9:16 na prancha vertical quando o footage é vertical); barras, curvas cubic-bezier com
durações e as transições permitidas a meio caminho; no vertical, a zona `uniao` com GC e legenda na posição real e uma miniatura por plataforma
(hachurado = coberto pela interface); thumbnail (silhueta ou `--foto`) com zona proibida; faça/não faça; som e marca.
A amostra de legenda é o PNG de `texto.estados_da_legenda` (`da/build/prancha/legenda_<formato>.png`): o mesmo caminho da produção. Os rótulos
da própria prancha só usam a `primaria` quando ela tem ≥ 3:1 sobre o fundo (DA clara com amarelo cai para `texto`).
Quadro de referência: `bruto/`, `broll/bruto/`, `broll/tratado/`, `broll/`, depois `da/referencias` (numa rota, também no projeto-pai), ou
`--referencia`; sem nada, um quadro sintético gerado em PIL. Intermediários em `da/build/prancha/` (`antes.png`, `depois.png`,
`legenda_<formato>.png`, `params_<formato>.json`). O carimbo traz `layout.mapa` (seções em px) — é por ele que `rotas comparar` alinha as colunas.

`da.py teste-movimento [--formato F] [--escala 0.5] [--dur S] [--atos titulo,gc,barras] [--referencia ARQ]` → `da/teste_movimento.mp4`
(960×540 por padrão): cartela de título entra, respira e sai · GC + legenda sobre um quadro do projeto · barras entram, contam e ficam, com
a transição padrão da DA entre os atos. A duração é calculada pelas durações da DA (`duracao()` da cena = `da_ext_motor.duracao_do_teste`);
`--dur` só mexe nos respiros.

### Tempos medidos (M1, 8 GB, Chromium headless shell 1243)

- Abrir o browser + palco + fontes: ~0,6 s. Quadro PNG 960×540: ~1,4 s de parede no total (com as duas chamadas ao `da.py`).
- Vídeo 960×540 a 29,97 fps: ~30 quadros/s de captura (1 s de título = 2,5–3,4 s de parede; 2 s de GC em VP9 = 2,5 s; 2 s de moldura em ProRes = 2,1 s com 19/60 quadros reaproveitados pelo cache).
- Prancha: 0,8–2 s por formato (+ ~0,5 s do antes/depois); teste de movimento do dossie (6,7 s de peça) a 480×270: 12 s; `rotas comparar` com 3 pranchas geradas na hora: 10 s.
- A suíte `test_motor` inteira: ~25 s. Em 1920×1080 estime 3–4× o tempo de captura do 960×540.

## Identidade e aprovação

`da_sha256` = sha256 de TODO o conteúdo com a herança aplicada + sha256 dos arquivos de estilo referenciados (fontes,
LUT, textura, logo), exceto `herda`, `projeto.*`, `conceito.*` e qualquer chave iniciada por `_` ou `x_` (em qualquer
profundidade). É `da.identidade()`; as exceções são as constantes `FORA_DA_IDENTIDADE` e `PREFIXOS_LIVRES`. Padrões do
esquema não entram no hash. Trocar uma cor, uma fonte ou o loudness muda a identidade; renomear o projeto, reescrever o
conceito, anotar em `x_*`, aprovar ou revisar não muda.
`aprovar` grava `aprovada=true`, `aprovada_em` e `aprovada_sha256`; qualquer edição posterior faz `validar`/`compilar`
avisarem "DA ALTERADA DEPOIS DA APROVAÇÃO" até `revisar` e novo `aprovar`.

## Mapeamento token → filtro ffmpeg (`tratamento`)

Só filtros que existem neste ffmpeg (sem drawtext/subtitles/ass). Com tudo neutro a cadeia é `null`.

| token | filtro | regra |
|---|---|---|
| `grade.exposicao` (EV) | `lutyuv` | ganho 2^(EV/2,2) em Y, U e V; 0 = omitido |
| `grade.contraste`, `saturacao`, `gama` | `eq` | só os parâmetros ≠ 1 |
| `grade.matiz` (graus) | `hue=h=` | 0 = omitido |
| `grade.temperatura` (−100…100) | `colortemperature` | > 0 → 3500 K, < 0 → 12000 K, `mix` = \|t\|/100, `pl=1` |
| `grade.curva` | `curves` | preset, pontos (`all=`) ou `{mestre, r, g, b}` |
| `grade.lut` + `intensidade_lut` | `lut3d` (+ `split`/`blend`) | parcial = blend normal com `all_opacity` |
| `duotone` | `colorchannelmixer` + `lutrgb` (+ `split`/`blend`) | luma BT.709 e rampa sombra→luz |
| `desfoque` | `gblur` | sigma = fração × lado menor |
| `nitidez` | `unsharp` | 5×5 só na luma |
| `vinheta.angulo` | `vignette` | ângulo em radianos |
| `grao.intensidade`, `temporal` | `noise` | só luma: `c0f=t+u` ou `c0f=u` |
| `velocidade` | `setpts` / `atempo` | fora da cadeia de cor |

## Campos acrescentados ao contrato do esquema (todos opcionais, com `default`)

- `projeto.base`; `tipografia.papeis.<p>.eixos` e `escala_x`; `legenda.sombra.dx/cor`; `legenda.fundo.raio/respiro`;
  `graficos.gc.papel_nome/papel_cargo/tamanho_nome/tamanho_cargo/cor_nome/cor_cargo/cor_fundo/alfa_fundo/cor_acento`;
  `graficos.tarja.estilo/papel/tamanho/cor_fundo/cor_texto/inclinacao`; `graficos.citacao_fonte.cor`; `thumbnail.cor/cor_destaque`.
- 1.5.0: `legenda.reservar_em`, `graficos.gc.protecao`, `projeto.rota_adotada`; itens de `cor.dados` podem ser nomes da paleta.
- 1.5.1: nenhum campo novo.
- 1.6.0: nenhum campo novo (o esquema não mudou; nenhum token, subcomando existente ou assinatura foi alterado).
- Tokens de cor aceitam também `dado-N` e `neutro-N`. Chaves iniciadas por `_` ou `x_` são livres (fora do esquema e da identidade); em mapas de tokens (`cor.paleta`, `tipografia.escala`…) esses prefixos são erro de validação.

## Escopo final (1.6.0)

- **A conferência final é do kit.** A operação fechou sem skill de QA e sem skill de thumbnail. A camada C5 virou o subcomando `conferencia` (`da_ext_conferencia.py`, pelo ponto de extensão `da_ext_*.py`): compõe `validar`, `lint --estrito`, `conferir-carimbo --exigir-aprovada`, `video.conferir_loudness` e os limites de `da.plataforma`, e grava `qa/relatorio.json` + `qa/relatorio.md` — o portão que a video-publicacao lê. Nenhuma regra de validação nova: cada item do relatório vem de uma função que já existia. Itens têm id estável (`<categoria>.<regra>[.<n>]`), severidade `erro`/`aviso`/`info` e `como_corrigir`; `ok` = nenhum erro; `verificado_em` é tirada no início (o que mudar durante a conferência fica mais novo que ela).
- **Entregáveis e plataformas sem número no código.** `render/final.mp4` é o vídeo longo (`som.loudness.longo`; plataformas de orientação horizontal em `plataformas.json`), `cortes/*.mp4` são peças curtas (`som.loudness.curto`; a plataforma declarada no carimbo do corte, senão todas as verticais). Duração mínima, máxima e recomendada, tamanho e resolução saem de `da.plataforma(nome)`; a tolerância de loudness é a de `video.conferir_loudness`; o formato de entrega esperado é o que `video.args_encode` produz.
- **Decisões**: `--previa` grava `qa/previa.json` (nunca o portão: `--saida` apontando para `qa/relatorio.json` é erro de uso) e só rebaixa "DA não aprovada" — DA alterada depois da aprovação continua erro; conferência restrita (`ALVO…`, `--corte`) limita carimbo, loudness e técnica aos alvos e aos insumos carimbados deles, mas DA, lint, fatos e licenças continuam do projeto; "DA NÃO APROVADA" e "DA ALTERADA" de `conferir-carimbo` viram um item só (o motivo é da DA, não de cada peça); avisos do lint e das conferências `--estrito` das irmãs entram como erro; skill irmã ausente é `info`, skill presente que não devolve resultado é erro; alvo inexistente ou fora do projeto é erro de uso (64) e não grava relatório; projeto sem entregável sai `ok` com aviso e `alvos: []`; DA inválida ou `da.json` ilegível grava relatório reprovado (`da.invalida`) em vez de só sair com erro, para um relatório antigo `ok` não continuar valendo; a DA é lida com `carregar(compilar=False)`, para a conferência não escrever fora de `qa/`.
- **Thumbnail**: continua possível direto pelo kit (tokens `thumbnail.*`, `texto.Estilo.thumbnail`, `texto.compor_bloco`, formato `thumbnail` do motor, `d.zona_proibida`); a receita executada está em `references/kit-api.md` §17.1.
- **Textos**: `DA.md` e o bloco do `CLAUDE.md` dos projetos passaram a citar `da conferencia`; a mensagem do auditor para `<img>` sem `data-da-livre` diz "a conferência final lista". Projetos antigos recebem o bloco novo rodando `init` de novo (o anterior fica em `CLAUDE.md.bak-<data>`).

## Fecho (1.5.1)

- **GC × legenda no horizontal**: `prancha.js` e `teste_movimento.js` montam o GC com `reservar_legenda: null` (o padrão da produção); onde a DA não reserva a faixa e os dois se tocam, a prancha mostra duas tiras 1:1 e o teste omite a legenda (`legenda_omitida`). `validar_dados(…, notas)` avisa formato sem reserva no vertical/quadrado e **anota** no horizontal (`validar()["notas"]`, impressas por `validar` e `aprovar`; não reprovam em `--estrito`). `da.caixa_gc_estimada` faz em Python a conta de posição do `gc.js`; `d.legenda_reservada(formato)` e `info["faixa_reservada"]` (`texto.compor_legenda`) respondem a quem queima legenda, e o `DA.md` ganhou a linha `Faixa da legenda reservada … em: …` (`_md_reserva_da_legenda`).
- **Auditor**: o que o estilo computado não mostra (lista na linha do `auditor.js`, acima) e o que anima fora de `seek(t)`. No `render.mjs`, depois dos estilos e da pureza: `imagensAnimadas` (lê GIF/APNG/WebP/AVIF/SVG no disco) e a **quietude** (dois retratos do mesmo `seek(t)` a 120 ms + `seek(t)` repetido; os PNG da divergência ficam em `da/build/depurar/`); usos de API proibida que só aparecem depois da auditoria de estilos (`tardios`) também reprovam. A linha de sucesso passou a ser `auditoria ok (N instantes, pureza em P, quietude em 1)` — quem fazia `grep` da linha antiga precisa ajustar.
- **Moldura**: `_moldura.js` mede rótulo e sub (`cabemLadoALado` → `caberEmpilhado` com `ctx.ajustar_texto`, 2 linhas parelhas, piso `ctx.minimo_legivel`); cabeçalho da janela e base da polaroid crescem; `rotulo_na_zona` sai dos retângulos reais; `layout` ganhou `rotulo_empilhado`, `tamanho_rotulo`, `tamanho_sub`, `minimo_legivel`.
- **`da-livre-arquivo`** do `auditor.js` voltou para as 10 primeiras linhas (o cabeçalho tinha crescido e o lint do próprio kit reprovava).

## Produto visual e método (1.5.0)

- **Faixa da legenda reservada (D18)**: `da.faixa_da_legenda` / `da.area_livre_de` (e os métodos `d.faixa_legenda`, `d.area_livre`) fazem em Python a mesma conta de `ctx.faixa_legenda` / `ctx.area_livre` no `runtime.js`. As cenas `gc`, `titulo`, `barras`, `citacao` e `moldura`, o `ctx.kit.credito` e o `texto.credito_fonte` trabalham nessa área; o token `legenda.reservar_em` (padrão vertical e quadrado) diz onde a reserva vem ligada e o parâmetro `reservar_legenda` força por cena. Mexeu na conta de um lado, mexa no outro (`test_produto.test_30` compara).
- **Mínimo legível**: `da.MINIMO_LEGIVEL` (0,022) e `da.MINIMO_LEGENDA` (0,04) — o validador avisa; os presets subiram cargo, crédito e `nota`.
- **GC protegido (D19)**: `graficos.gc.protecao` (`auto` = painel `degrade` no estilo `linha`); validador avisa `linha` sem proteção e texto do GC sem contraste com o apoio.
- **Rotas (D20)**: `da.criar_rota`, `da.listar_rotas`, `da.adotar_rota`, `da.projeto_pai`, `da.bases_da_cadeia` (a rota resolve arquivos também contra o `da/` do projeto-pai) e `da_ext_motor.comparar_rotas`. `aprovar` confere `da.documentos_de_aprovacao` e chama os ganchos de `da.APOS_APROVAR`.
- **Prancha e teste de movimento (D21)**: legenda de `texto.py`, faixa 1:1, mapa de seções no carimbo; contrato opcional `duracao()` de cena no `render.mjs`.
- **Coerência de cor**: `cor.dados` aceita nomes da paleta (`da.hex_do_item`; resolvida guarda `cor.dados_tokens`); avisos para cores quase idênticas, hex quase igual a uma cor da paleta e gradiente chapado.
- **`extrair`**: `_acentos` (cores vivas a partir de 0,3 % da área), pasta como argumento, `--regiao`; a folha cabe na largura com vídeo de 6 quadros.
- **Presets**: `neon-shorts` com contraste 1,12, gama 1,1 e vinheta 0,4 (footage escuro deixava de afundar: L* médio 23,8 → 21,2 em vez de 15,7).

## API para as skills irmãs (1.4.0)

- **Uma semântica de texto nos dois lados**: `texto.py` e `motor/cenas/_legenda.js` fazem as mesmas contas (vão, quebra `quebrar_palavras`/`quebrarPalavras`, contorno externo de cantos redondos — no motor, `ctx.contorno` = anel de sombras de texto —, sombra projetada pelo texto com contorno — no motor, `filter: drop-shadow` por fileira —, caixa única, tamanho comum no estilo `palavra`, kerning com tracking, centro no retângulo da zona segura). Mexeu num, mexa no outro e rode `test_30`.
- **Peças compartilhadas**: `_legenda.js`, `_tarja.js`, `_credito.js` e `_moldura.js` são instanciáveis várias vezes por página e chegam às cenas de fora por `ctx.kit` (runtime.js); as cenas embutidas `barras`, `citacao` e `moldura` usam as mesmas peças. `ctx.kit.cena(nome, …)` importa uma cópia do módulo por instância (`?instancia=N`).
- **Transições**: nomes em `da.TRANSICOES`; `video.XFADE` (ffmpeg) e `ctx.transicao` (motor) executam os mesmos seis; `d.transicao()` recusa o que não está em `permitidas`.
- **Proveniência**: `da.carimbar(…, insumos=[…])` lê os carimbos dos insumos (`da.proveniencia`), grava `insumos` e `midia`, e rebaixa a auditoria para `pulada` quando um insumo pulou o auditor; `conferir_carimbo` tem os estados `auditoria_pulada` (com o insumo no detalhe) e `insumo_de_outra_da`.
- **Intermediários**: `da.PREFIXO_INTERMEDIARIO = "_"` (pastas e arquivos fora de `conferir-carimbo` e do lint por varredura), `da.PASTAS_SEM_PECAS = ("broll/bruto",)`, `da.PASTAS_COM_PECAS` inclui `broll/tratado`; o `init` cria `broll/bruto/` e `broll/tratado/` (`da.SUBPASTAS_TRABALHO`).
- **Plataformas**: `plataformas.json` usa `youtube`, `shorts`, `reels`, `tiktok` em todas as seções, com `apelidos`; `da.plataformas()`, `da.plataforma(nome)`, `da.limite(plataforma, chave, grupo=None)`, `da.nome_plataforma(apelido)`; no `da.json` a zona do Reels continua na chave `instagram` (`da.ZONA_DA_PLATAFORMA`).
- **Tokens novos, todos com padrão** (não mudam a identidade de quem não os escreve): `tratamento.encaixe.{modo, desfoque, escurecer, cor}`, `legenda.posicao.<formato>.{x, largura_max}`, `graficos.citacao_fonte.prefixo`, `thumbnail.zona_proibida_tamanho`.

## Higiene e segurança (1.3.0)

- **Sem `__pycache__`**: `trava.py` (base de todos os módulos) liga `sys.dont_write_bytecode` e apaga `kit/__pycache__/` ao ser importado; `testes/__init__.py` faz o mesmo para as suítes. O custo é recompilar `da.py` a cada processo (~0,1 s).
- **Cor com alfa — uma forma**: `rgba(var(--da-cor-<nome>-rgb), a)`. Está no cabeçalho do `da.css`, no bloco do CLAUDE.md, na sugestão do lint (`alfa-invalido` acusa a forma com barra) e no auditor (`conferirDeclaracao`: refaz a declaração com as variáveis trocadas e pergunta ao `CSS.supports`).
- **Lint**: `.py` é lido pela árvore sintática (`_Lint.py`); o que o lint não lê vai para `nao_conferidos` e reprova com `--estrito`; `data-da-livre` vira faixa de caracteres (o elemento), não linha.
- **Carimbo**: `carimbar` levanta `DAErro` em vez de trocar `pulada` por `ok`/`n/a` no mesmo arquivo; o motor passa `--reauditada` (opção interna) quando o render acabou de passar pelo auditor.
- **Trava**: rótulo padrão = nome do executável (+ script), nunca os argumentos; arquivo da trava em modo 600.
- **Render**: `da_ext_motor.render` roda `node render.mjs … --validar` (sem browser, sem trava) antes de entrar na fila quando a trava está ocupada por outro processo; `da.py render -- --help` tira o `--` antes de repassar (o motor passou a recusar opção desconhecida).
- **init**: delimitadores do bloco só em linha própria, exatamente um par, `CLAUDE.md.bak-<data>` antes de regravar; `--forcar` sem `--base` reaproveita a base. **extrair** ignora `referencias_folha.png`/`referencias_analise.json`.

## Decisões e desvios documentados (motor)

- **`ctx.dur` é a função das durações da DA** (`ctx.dur('media')`); a duração total da peça está em `ctx.duracao` (e `ctx.DUR`). O contrato listava os dois com o mesmo nome; o uso em cena favorece a função. `ctx.alfa(token, a)` devolve `rgba()`; se a peça é transparente está em `ctx.transparente`.
- O auditor confere a **primeira família** do `font-family` computado e só em elementos com texto direto; fontes genéricas (`sans-serif`, `system-ui`) reprovam. `background-image: url(…)`, `<img>`, `<canvas>`, `<video>` e `<image>` reprovam fora de `data-da-livre` (o auditor não enxerga os pixels) — fotos vão em `<img data-da-livre="foto">`. `mask-image: url()` passa de propósito (máscara só mexe em alfa), mas a imagem entra na conferência de animação. O auditor não lê pixels: uma rede por amostragem do screenshot foi descartada porque qualquer alfa de cor da DA sobre footage produz cores fora da paleta.
- Nos nós de texto o runtime nunca usa o atalho CSS `text-wrap`: em Chromium ≥ 130 ele redefine `text-wrap-mode` e anula um `white-space: nowrap` anterior (um "2" de "Capítulo 2" caía numa segunda linha invisível). Use `text-wrap-style`.
- Medidas de layout dentro das cenas usam `offsetWidth/offsetHeight` (independentes de transform) para que a prancha possa montar cenas em quadros reduzidos por `scale()`. Elementos precisam estar no DOM antes de medir.
- O `--escala` usa `deviceScaleFactor` (mesmo layout CSS, menos pixels); dimensões ímpares são cortadas em 1 px para o yuv420p.
- `--quadro fim` é o último instante (geralmente já depois da saída); para o estado "em repouso" use um T entre `fim_entrada` e `inicio_saida` (ambos no `layout` do carimbo).
- `prancha` também carimba a saída, e os intermediários em `da/build/prancha/` levam o carimbo do `da.py grade`.
- `render.mjs` grava o PNG/vídeo antes de conferir com ffprobe; se a conferência falha, o arquivo fica **sem carimbo** (a conferência final reprova) e o job conta como falha.
- `da.py render` repassa argumentos ao motor já com `--da` e sob a trava; ajuda do motor: `da.py render -- --help` (`--help` sozinho é capturado pelo argparse do `da.py`). O subcomando é registrado com `repasse=True`: o `main()` usa `parse_known_args` e devolve as opções desconhecidas (`--cena …`) para `args.argumentos` na ordem original — sem isso o argparse mandava `--cena` para "extras" e `da.py render --cena titulo …` dava erro 64 (corrigido em 1.1.0, com teste de regressão em `test_13_erros_de_uso`). Subcomandos comuns continuam estritos.
- Na `--fila`, `cena` com caminho é resolvida primeiro em relação à pasta do `fila.json` (como `saida`) e depois ao cwd.
- As cenas embutidas guardam estado no próprio módulo (padrão do motor da casa): importadas diretamente, cada uma pode ser montada **uma vez** por página (a prancha e o teste de movimento respeitam isso). Para várias instâncias, `ctx.kit.cena(nome, params, {palco})` importa uma cópia do módulo por chamada; as peças de `ctx.kit` (legenda, tarja, crédito, moldura) guardam o estado na instância.
- O ffprobe nativo reporta `yuv420p` para WebM com alfa; `comum.ffprobe` e `video.sondar` passam `-c:v libvpx-vp9` para `.webm`.

## Ponto de extensão

`da.registrar_subcomando(nome, ajuda, configurar, executar, descricao=None, repasse=False)` ou um arquivo `da_ext_<nome>.py` ao lado de `da.py`
com `def registrar(da): …` (é assim que `da_ext_motor.py` e `da_ext_conferencia.py` entram). Toda extensão ganha `--da`/`--de`, as mensagens de erro
e o "sem DA = código 2" de graça. `repasse=True` é para subcomandos que repassam a linha de comando a outro programa
(positional `argumentos` com `nargs="..."`): opções desconhecidas vão para `args.argumentos` em vez de erro de uso.

## Documentação da skill

`"$CRIABR_SKILLS"/video-direcao-de-arte/SKILL.md` (método e armadilhas), `references/kit-api.md` (API para skills irmãs, contrato de cena,
auditor, carimbo, thumbnail direto pelo kit, conferência final e contrato de `qa/relatorio.json`), `references/tokens.md` (dicionário de tokens), `references/metodo-da.md`, `references/pipeline.md`, `references/plataformas.md`.
