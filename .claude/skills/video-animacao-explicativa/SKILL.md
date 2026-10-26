---
name: video-animacao-explicativa
description: Biblioteca de 19 cenas animadas que EXPLICAM inteligência artificial — como o modelo funciona (tokenização, embeddings, atenção, próximo token e temperatura, rede neural, treino, janela de contexto, difusão), sistemas em volta dele (RAG, agente com ferramentas, chat, terminal) e estrutura do roteiro (conceito, lista, fluxo, versus, comparativo, linha do tempo, número) — mais o storyboard que liga roteiro → cenas → prévia → renders (roteiro/storyboard.json), tudo no motor determinístico do kit e 100% nos tokens da direção de arte do projeto, em horizontal (YouTube), vertical (Shorts, Reels, TikTok) e quadrado. Use quando o usuário pedir "anima esse conceito", "faz uma animação explicando como o modelo funciona", "mostra o que é RAG", "desenha o laço do agente", "mostra a tokenização/a atenção/a temperatura/a janela de contexto", "põe esse número na tela", "faz um comparativo dos modelos", "monta o storyboard do roteiro", "que cenas dá pra usar nesse trecho?", "sincroniza a animação com a fala", "me mostra uma prévia das animações antes de renderizar" ou "renderiza as animações do vídeo" — mesmo sem dizer "storyboard". Difere das irmãs — video-direcao-de-arte decide cor, fonte e movimento (aqui só se leem tokens; sem DA nada é renderizado); video-pesquisa-ia verifica os fatos e entrega o crédito (aqui se desenha, com fato_ids e fonte); video-broll baixa e trata material de terceiros (aqui tudo é desenhado, sem mídia externa); video-legendas queima a legenda (aqui só se reserva a faixa dela); video-cortes-verticais recorta vídeo gravado; video-pauta-midia escolhe o assunto; video-publicacao empacota e publica. Fora do conjunto: video-motion-graphics faz GC e selo SOBRE vídeo gravado, video-efeitos-sonoros sonoriza as âncoras exportadas daqui e video-montagem encaixa os renders na timeline.
---

# Animações explicativas de IA: biblioteca de cenas e storyboard

Uma cena é uma simplificação **fiel** de um conceito, parametrizável, que se desenha passo a passo no ritmo da narração. O storyboard (`roteiro/storyboard.json`) diz qual cena cobre qual trecho do roteiro, com que dados, por quanto tempo e em que formatos. O script confere tudo antes do render caro, mostra uma folha de contato para aprovação e renderiza sob a trava global.

```bash
sb() { python -B "$CRIABR_SKILLS"/video-animacao-explicativa/scripts/storyboard.py "$@"; }   # redefina em cada bloco: o shell não guarda funções entre chamadas
sb --help          # 13 subcomandos, cada um com --help em PT-BR
sb cenas           # catálogo: biblioteca de IA + cenas do kit + cenas próprias do projeto
```

Rode da raiz do projeto (ou de qualquer pasta dentro dele; `--projeto "<pasta>"` também vale). Códigos de saída: **0** ok · **1** reprovado ou falha de render · **2** projeto sem direção de arte · **64** uso incorreto (parâmetro ruim, cena inexistente). Só biblioteca padrão + o kit em `"$CRIABR_SKILLS"/video-direcao-de-arte/kit` (Pillow, numpy, Node, Chromium e ffmpeg por ele). Caminhos com espaço e acento funcionam (testado em `Vídeo teste ação/`).

Leia quando precisar: `references/catalogo.md` (uma linha por cena, com os parâmetros principais e o selo — leia para escolher), `references/didatica.md` (para cada cena: o que mostra, o que simplifica, **o que a narração não pode afirmar**, erros comuns, fontes abertas em 2026-10-07 — leia antes de escrever o trecho do roteiro e antes de aprovar a prévia) e `references/biblioteca.md` (como as cenas são feitas, a API de `cenas/_ia.js` e o esqueleto de uma cena nova — leia para criar ou corrigir cena).

## Passo 0 — Direção de arte

1. **Ache a DA**: `"$CRIABR_SKILLS"/video-direcao-de-arte/kit/bin/da achar --json` a partir da pasta do projeto. Código 2 = não há `da/da.json`: **pare**, diga ao usuário que o projeto não tem direção de arte e chame a skill `video-direcao-de-arte`. O `storyboard.py` faz a mesma checagem e sai com 2; nunca renderize uma cena "só para mostrar" num projeto sem DA.
2. **As cenas só leem tokens**: cor por `ctx.cor`/`ctx.alfa` (o destaque é o parâmetro `cor`, um token, padrão `primaria`), tipografia pelos papéis (`corpo`, `dados`, `titulo`), tamanhos pela escala (`h1`…`nota`), entradas, curvas e durações de `movimento.*`, chapéu pela tarja de `graficos.tarja`, crédito por `ctx.kit.credito` (`graficos.citacao_fonte`), zona segura e faixa da legenda por `ctx.area_livre`. A mesma cena muda de cara quando o `da.json` muda, sem tocar em código (prova: `lab-ia` × `editorial-claro` nas folhas de contato da suíte).
3. **Nenhuma cor ou fonte literal** em cena, parâmetro ou storyboard. O parâmetro `cor` aceita só token da DA (`roxo` → erro 64). Rode `"$CRIABR_SKILLS"/video-direcao-de-arte/kit/bin/da lint --estrito animacoes roteiro/storyboard.json` antes de entregar (`sb conferir` já faz).
4. **O carimbo é do motor**: cada render sai com `<saida>.da.json` (`auditoria: ok`, parâmetros, `ancoras`, `layout`). Nenhuma cena da biblioteca usa `data-da-livre`. Intermediários (`animacoes/_fila_*.json`, `_previa/`, `_feito.json`) começam por `_` e ficam fora do QA.
5. **Pedido que contraria a DA** ("põe a atenção em vermelho"): não vira exceção na cena. Ofereça o token mais próximo (`--param 'cor="destaque"'`, `"negativo"`) ou uma revisão da DA (`da revisar` → editar → `aprovar`).
6. **Uma tarefa pesada por vez**: `sb prever` e `sb render` já entram na trava global do kit. Fila parada com "SEM PROGRESSO há mais de 2 min": `python3 "$CRIABR_SKILLS"/video-direcao-de-arte/kit/trava.py --estado` e, se for o caso, `--liberar`.

## Fluxo

Roteiro e ficha de fatos → catálogo → storyboard → prévia → **aprovação do usuário** → render → entrega para a montagem. Não pule a aprovação: o render é a parte cara, e a prévia custa segundos.

### 1. Parta do roteiro e da ficha de fatos

- **Roteiro**: o texto como será falado (do usuário, de `gerar-roteiro` ou de `melhorar-roteiro`). Marque os trechos que pedem imagem: um conceito, um processo, um número, uma comparação. Sem roteiro, peça o trecho antes de escolher cena — cena sem fala vira enfeite.
- **Ficha de fatos**: `pesquisa/fatos.json`, da skill `video-pesquisa-ia`. Todo número, data, preço ou nome de modelo que vai aparecer **como dado** precisa de um fato (`F###`). Sem fato, o valor só entra como exemplo inventado, com o selo "ilustrativo" na tela — e a narração não pode apresentá-lo como real.
- Leia a seção da cena em `references/didatica.md` antes de fechar o texto do trecho: ela diz o que a narração não pode afirmar sobre o que a imagem mostra.

### 2. Escolha a cena de cada trecho (catálogo)

```bash
sb() { python -B "$CRIABR_SKILLS"/video-animacao-explicativa/scripts/storyboard.py "$@"; }
sb cenas                 # uma linha por cena: duração padrão e o que demonstra
sb cenas rag             # parâmetros, tipos, padrões, formatos e se a cena tem passos sincronizáveis
```

| família | cenas |
|---|---|
| como o modelo funciona | `tokenizacao` · `embeddings` · `atencao` · `proximo_token` · `rede_neural` · `treino` · `janela_contexto` · `difusao` |
| sistemas em volta do modelo | `rag` (busca → trechos no contexto → resposta com citação) · `agente` (modelo pede ferramenta, o aplicativo executa, o resultado volta) · `chat` (resposta token a token) · `terminal` (comando e saída) |
| estrutura do roteiro | `conceito` · `lista` · `fluxo` · `versus` · `comparativo` · `linha_do_tempo` · `numero` |

Parâmetros principais de cada uma: `references/catalogo.md`. Cartela, citação, gráfico de barras e GC são as cenas `titulo`, `citacao`, `barras` e `gc` do kit: entram no mesmo storyboard. Conceito que nenhuma cena cobre: escreva uma cena própria em `<projeto>/animacoes/cenas/` (`references/biblioteca.md` §4) — não force uma metáfora numa cena que mostra outra coisa.

### 3. Monte o storyboard

```bash
sb() { python -B "$CRIABR_SKILLS"/video-animacao-explicativa/scripts/storyboard.py "$@"; }
sb novo                                                  # cria roteiro/storyboard.json vazio (não sobrescreve sem --forcar)
sb adicionar --cena tokenizacao --trecho "Antes de tudo, o texto é quebrado em pedaços | e cada pedaço vira um número"
sb adicionar --cena atencao --formatos horizontal --params '{"tokens": ["O", "gato", "dorme"], "pesos": [0.2, 0.7, 0.1]}'
sb definir C02 --param 'titulo="Quem olha para quem"' --dur 12       # --param chave=JSON (repetível) · --sem-param chave · --params '{…}' funde
sb mostrar
```

- **`trecho`** é a frase do roteiro que a cena cobre, como será **falada**. A barra `|` marca onde dispara o próximo passo da cena (o primeiro dispara no começo): `n` passos aceitam até `n − 1` marcas.
- **`dur`** nasce da cena e do **ritmo da DA**: a mesma `atencao` pede 11 s no `lab-ia` e 15 s no `editorial-claro`, porque as durações de `movimento` são outras. Não encurte "no olho": `validar` diz o mínimo.
- `adicionar` e `definir` conferem a cena antes de gravar; com erro, **nada é gravado** (código 64) e a mensagem diz o que corrigir (`parâmetro "pontoz" não existe… Quis dizer "pontos"?`). `--mesmo-assim` grava um rascunho.
- Saídas: `animacoes/<id>_<formato>.mp4` (opaco, h264). Cena com fundo transparente (`gc`, ou `--alfa sim`) sai `.webm` (VP9 com alfa, para compor via ffmpeg) ou `.mov` (`--codec-alfa prores4444`, para o Premiere).

**Dado real ou exemplo?** Todo exemplo padrão é inventado e mostra o selo "ilustrativo". Para mostrar dado real de um modelo (tokenização de verdade, tamanho de janela, pesos medidos): `"ilustrativo": false` **+** `"fonte"` (a saída de `fatos.py credito F### --sem-prefixo`; o kit põe "Fonte: ") **+** `fato_ids` (`sb definir C01 --fato F004`). Faltando um dos três, `validar` reprova e o próprio build da cena recusa. A cena nunca inventa número com cara de real: sem `pesos`, a `atencao` de uma frase sua não renderiza.

### 4. Valide (sem renderizar)

```bash
sb() { python -B "$CRIABR_SKILLS"/video-animacao-explicativa/scripts/storyboard.py "$@"; }
sb validar               # contrato + cena existe + parâmetros (validador do motor, sem browser) + formatos + ritmo
sb validar --estrito     # avisos também reprovam: é este que libera o render
```

Reprova: campo do contrato faltando ou de tipo errado, id repetido, formato que a DA não tem, parâmetro desconhecido ou fora da faixa, `dur` menor que o mínimo dos passos (`dur = 2 s é curta demais para os 4 passos… o mínimo com as durações desta DA é 5.6 s`), `passos_t` fora de ordem, a mais ou dentro da saída da cena, dado real sem fonte ou sem fato. Avisa: `dur` abaixo do recomendado (pouco tempo de leitura), cenas que se sobrepõem na linha do tempo, passo comprimido.

### 5. Sincronize com a narração

```bash
sb() { python -B "$CRIABR_SKILLS"/video-animacao-explicativa/scripts/storyboard.py "$@"; }
sb sincronizar --simular                                  # mostra t0, dur e passos_t de cada cena, sem gravar
sb sincronizar --palavras "transcricao/final.palavras.json"   # sem --palavras: a única transcrição da pasta
```

Procura cada `trecho` na transcrição palavra a palavra (skill `video-transcricao`) e preenche `t0` (0,2 s antes da primeira palavra; `--antecipar`), `dur` (até 0,6 s depois da última; `--cauda`; `--manter-dur` não mexe) e, se o trecho tem marcas `|`, `params.passos_t`: cada passo dispara na palavra que vem depois da marca. A busca tolera diferença entre o roteiro e a fala (no teste, "absolvição" no roteiro × "absorvição" na transcrição: casamento de 90%); abaixo de 75% avisa, abaixo de 50% não aplica. Cena sem `trecho` (uma cartela) é pulada: defina `t0` à mão. Use a transcrição **do vídeo montado**: é a linha do tempo dele que `t0` descreve — cortes verticais e publicação leem esse campo.

### 6. Prévia e aprovação do usuário

```bash
sb() { python -B "$CRIABR_SKILLS"/video-animacao-explicativa/scripts/storyboard.py "$@"; }
sb prever                          # animacoes/_previa/storyboard_<formato>.png: 2 quadros de cada cena
sb prever --quadros 3 --so C02     # 1 a 3 quadros; só algumas cenas; --formato vertical
```

**Abra a folha (Read) e mostre ao usuário antes do render.** Confira com `references/didatica.md` ao lado: o que está na tela é o que a narração diz? Algum número parece real sem ser? O destaque está no elemento certo? No vertical, nada encosta na borda da zona segura? Medido (M1, 8 GB): 9 quadros de 2 cenas (6 horizontais e 3 verticais) a 640 px em 7,4 s. **Só renderize depois de um sim explícito do usuário** ("pode renderizar"); pedido de ajuste volta para `sb definir` e nova prévia. Na folha, o último quadro de cada cena (82% da duração) é o estado final; texto pela metade no primeiro é digitação em andamento, não corte.

### 7. Renderize

```bash
sb() { python -B "$CRIABR_SKILLS"/video-animacao-explicativa/scripts/storyboard.py "$@"; }
sb render                          # todos os formatos do storyboard, sob a trava; pula o que está em dia
sb render --formato vertical --so C01,C02
sb render --escala 0.25            # teste rápido em resolução reduzida (renderize de novo sem --escala para entregar)
```

Valida de novo, gera `animacoes/_fila_<formato>.json`, renderiza num navegador só, **continua depois de uma falha** e fecha com `RESUMO: n renderizada(s), n em dia, n falha(s)` (código 1 se houve falha). "Em dia" = mesma cena, mesmos parâmetros, mesma DA e arquivo intacto (`animacoes/_feito.json`); mudou qualquer um, renderiza de novo; `--refazer` força. Medido (M1, 8 GB, preset `quadro-negro`): `tokenizacao` de 11 s em 1920 × 1080 (330 quadros) em 46 s, arquivo de 1,7 MB; a 0,25 da resolução, três peças custaram 23 s de processamento (94 s de relógio naquele momento, porque a fila da trava estava ocupada por outros processos). `sb fila` só gera as filas (para rodar no motor por fora: `"$CRIABR_SKILLS"/video-direcao-de-arte/kit/bin/da render --fila "animacoes/_fila_horizontal.json"`).

### 8. Âncoras, conferência e entrega para a montagem

```bash
sb() { python -B "$CRIABR_SKILLS"/video-animacao-explicativa/scripts/storyboard.py "$@"; }
sb ancoras       # animacoes/ancoras.json: o instante de cada passo de cada cena, lido dos carimbos
sb conferir      # fatos (video-pesquisa-ia), dado real com fonte, lint do storyboard e das cenas próprias
"$CRIABR_SKILLS"/video-direcao-de-arte/kit/bin/da conferir-carimbo animacoes
```

- `ancoras.json` traz, por peça, `ancoras: [{t, t_video, nome, tipo}]` (`t` local; `t_video` = `t0 + t`) e a lista `eventos` na linha do tempo do vídeo, para a skill `video-efeitos-sonoros` (`tipo`: `entrada`, `enfase`, `texto`, `saida` — as famílias de `som.sfx` da DA). Cena sem `t0` fica só em tempo local.
- `conferir` chama `fatos.py conferir-storyboard` quando a skill `video-pesquisa-ia` está instalada e o projeto tem `pesquisa/fatos.json`; storyboard que cita `fato_ids` sem ficha reprova.
- **Entrega à montagem**: os `.mp4` de `animacoes/` (um por cena e formato, com o carimbo `.da.json` ao lado), o `roteiro/storyboard.json` (`t0` e `dur` de cada cena na linha do tempo) e `animacoes/ancoras.json`. Diga ao usuário onde cada peça entra. Juntar cenas em sequência com a transição da DA: `video.juntar` do kit (`kit-api.md` §5.3). A conferência final do vídeo montado é o comando `"$CRIABR_SKILLS"/video-direcao-de-arte/kit/bin/da conferencia`.

## O que vale para todas as cenas

- **Parâmetros comuns**: `titulo` (chapéu na tarja da DA; `""` esconde), `legendas` (a frase de cada passo; `[]` esconde; `*termo*` ganha a cor do destaque), `passos_t`, `cor`, `ilustrativo`, `fonte`, `plataforma` (`reels`, `tiktok`, `shorts`, `uniao`; no horizontal cai em `padrao`), `reservar_legenda`.
- **Ritmo**: uma ideia por passo — o elemento entra, ganha o destaque e só então vem o próximo. Sem `passos_t`, os passos se repartem na duração; com cena curta demais, as animações encolhem juntas (`layout.apertado: true` no carimbo) em vez de se atropelar.
- **Vertical**: tudo fica na zona segura da plataforma **menos a faixa da legenda queimada** (`legenda.reservar_em` da DA: vertical e quadrado por padrão). Nesse caso as frases de passo ficam escondidas — quem narra é a legenda, e dois textos empilhados brigam. `"reservar_legenda": false` devolve a altura e as frases; passar `legendas` explícitas mostra as frases mesmo com a faixa reservada.
- **Texto**: nada abaixo da escala `nota` da DA; rótulos em `corpo` ou maior; números em pt-BR (vírgula decimal).
- **Determinismo**: `seek(t)` puro; o que é sorteado usa `semente` e fica registrado no carimbo (`layout.sorteios` em `proximo_token`).

## Contrato

`roteiro/storyboard.json`: `{"versao": 1, "cenas": [{"id": "C01", "trecho", "t0": null|s, "dur": s, "cena": "nome ou caminho .js", "params": {…}, "formatos": ["horizontal", "vertical"], "fato_ids": [], "broll_id": null, "saida": "animacoes/C01"}]}`. Campos acrescentados por esta skill, todos opcionais: na cena, `alfa` (bool: força fundo transparente ou opaco); na raiz, `sincronia` (`{origem, antecipar, cauda}` da última sincronização). Nome de cena resolve nesta ordem: `<projeto>/animacoes/cenas/` → biblioteca → kit. Só o `storyboard.py` grava o arquivo, com trava (`roteiro/_storyboard.lock`) e troca atômica; `novo --forcar` guarda o anterior em `storyboard.json.bak`.

Outras skills importam o módulo por posição: `sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "video-animacao-explicativa" / "scripts")); import storyboard` → `storyboard.ler(raiz)`, `storyboard.validar(raiz, d, sb)`, `storyboard.catalogo(raiz)`, `storyboard.roteiros(raiz, d, cenas)`, `storyboard.sincronizar(raiz, d, sb, palavras)`, `storyboard.montar_fila(raiz, sb, formato)`.

## Testes

```bash
cd "$CRIABR_SKILLS"/video-animacao-explicativa/scripts && python -B -m testes.lote --folhas "<pasta>"       # 19 cenas × 2 formatos × lab-ia e dossie pelo auditor (~1 min) + 4 folhas de contato
cd "$CRIABR_SKILLS"/video-animacao-explicativa/scripts && python -B -m unittest testes.test_storyboard   # 16 testes, sem navegador
cd "$CRIABR_SKILLS"/video-animacao-explicativa/scripts && python -B -m unittest testes.test_cenas        # 8 testes no motor; as duas suítes juntas: 24 testes em 6 min 35 s (M1, 8 GB, 2026-10-12)
```

`testes.lote` renderiza um quadro do meio de cada cena da pasta e sai com 1 se alguma falhar no build, reprovar no auditor, usar `data-da-livre`, declarar conteúdo fora da zona segura ou sair sem o selo devido; `--fracao 0.88` mostra o estado final e `--so rag,agente` restringe. `test_cenas` acrescenta pureza (quadro avulso = quadro do vídeo), lint estrito, erros de dado, o caso apertado do `neon-shorts` e a caixa real dos pixels contra a área livre. Tudo em pasta temporária, com `VIDEO_OPS_HOME` dentro dela. Detalhes: `references/biblioteca.md` §5.

## Armadilhas (observadas ao construir e testar em 2026-10-07 e 2026-10-12)

- **Auditor aprovado não é layout aprovado.** Em 2026-10-12 o lote deu 76 de 76 e a folha mostrava, no vertical do `dossie`, o cabeçalho "semelhança" de `rag` encostado no contorno e a marca "resultado" de `agente` colada no trilho do contexto. O auditor lê cor, fonte e movimento; texto cortado e elemento em cima de outro só aparecem para quem **olha a folha**.
- **Quadro do meio engana.** Em `comparativo`, `chat`, `terminal` e `versus` o texto entra digitado ou por revelação: a 50% da cena a folha mostra "Preço de entra" e parece corte. Antes de consertar, veja o estado final (o último quadro de `sb prever`, ou `testes.lote --fracao 0.88`).
- **No vertical a cena ocupa a metade de cima do quadro, e isso é a DA.** A base é da legenda queimada e da interface da plataforma. Não "centralize" a cena no quadro: `"reservar_legenda": false` devolve a altura quando o corte não leva legenda.
- **Fonte monoespaçada pede mais largura.** As mesmas 19 cenas cabem com folga no `lab-ia` e ficam justas no `dossie` (corpo monoespaçado): rótulo que sobra num preset encosta no outro. Texto próprio longo: confira a prévia no preset do projeto, não no exemplo.
- **A mesma cena precisa de tempos diferentes em DAs diferentes.** Com a duração padrão de 11 s, a `atencao` passava no `lab-ia` (mínimo 7,2 s) e era curta para o `editorial-claro` (mínimo 11,9 s; `proximo_token` vai de 16 s a 24 s). Por isso `adicionar` calcula a duração com as durações da DA do projeto, e trocar a DA de um projeto pede `sb validar` de novo.
- **No vertical sobra pouca altura.** A zona `uniao` deixa 660 × 960 px em 1080 × 1920, e com a faixa da legenda reservada a cena fica com ~780 px de altura: na primeira versão o plano de `embeddings` saiu pequeno demais e os rótulos `carro`, `ônibus` e `bicicleta` se encavalaram. A correção foi esconder as frases de passo quando há legenda queimada e compactar os painéis; se uma cena sua ficar miúda, veja `layout.conteudo` no carimbo antes de mexer em fonte. No `neon-shorts` (a maior letra e a maior faixa de legenda) as fileiras de `treino` chegaram a se encostar e a rede de `rede_neural` ficou espremida pela tabela: hoje as fichas e a tabela encolhem até caber (nunca abaixo de `nota`) e os rótulos das camadas ocultas somem quando não cabem lado a lado.
- **A fala costuma ser mais curta que a cena.** Na fixture, um trecho de 3,65 s de fala caiu numa `tokenizacao` cujo mínimo é 5,6 s: `sincronizar` avisa e `validar` reprova. Alongue o trecho (a cena pode começar antes e terminar depois da frase), tire passos (`comparar: []` e menos `rodadas` em `proximo_token`) ou segure a duração com `--manter-dur`.
- **Marcas demais no trecho não são ignoradas**: 4 barras numa cena de 4 passos devolvem `cabem no máximo 3 marcas` e a cena não é sincronizada. O primeiro passo dispara sempre no começo.
- **O sorteio de `proximo_token` é de verdade.** Com `semente: 4`, a primeira rodada do exemplo sorteia " a" (5%), e a segunda rodada foi escrita para depois de " Paris": o build recusa e sugere uma semente que dá o caminho esperado. Não existe parâmetro para "forçar" o token; para um resultado fixo use `escolha: "maior"` e diga na narração que é o mais provável.
- **`ctx.entrada` apaga o `transform` do elemento.** Na primeira versão da `tokenizacao`, o deslocamento que abria a frase em pedaços anulava a entrada da DA (`sobe`, `escala`). Movimento próprio vai numa casca em volta do elemento (`references/biblioteca.md` §3).
- **O kit mudou durante a construção** (1.4.0 → 1.5.0): `ctx.area_livre` (zona segura menos a faixa da legenda) apareceu no motor antes de entrar no `kit-api.md`. As cenas chegam a ela por um ponto só (`areaUtil` em `cenas/_ia.js`), que cai em `ctx.area_segura` num kit sem a função.
- **A fila da trava é compartilhada.** Durante os testes, renders ficaram alguns segundos em `[trava] aguardando trava… em uso por pid …` por causa de outros processos da máquina. É esperado; só intervenha com `trava.py --estado` se aparecer `SEM PROGRESSO`.
- **`prever` não substitui olhar em tamanho real.** A folha reduz o quadro a 640 px: serve para aprovar composição e conteúdo. Para conferir legibilidade no celular, renderize um quadro cheio da cena (`"$CRIABR_SKILLS"/video-direcao-de-arte/kit/bin/da render --cena <arquivo da cena mostrado em sb cenas NOME> --saida "animacoes/_t/q.png" --quadro 6 --formato vertical`) e abra.
- **Guardar o comando numa variável não funciona** (`SB="python3 ~/…/storyboard.py"; $SB validar`): o zsh não divide a variável em palavras e o til entre aspas não expande. Por isso os exemplos usam a função `sb`.
