# Pipeline da operação de vídeo — quem lê o quê, quem escreve onde

Mapa de todas as skills de vídeo da casa em torno da direção de arte (DA). Pastas são as que `da.py init` cria na raiz do projeto. As skills escritas contra `kit-api.md` (video-pesquisa-ia, video-pauta-midia, video-broll, video-animacao-explicativa, video-legendas, video-cortes-verticais, video-publicacao) importam o kit; as mais antigas (video-transcricao, video-montagem, video-motion-graphics, video-animacao-audio, video-efeitos-sonoros, video-mixagem, gerar-ganchos, gerar-roteiro, melhorar-roteiro) obedecem à DA pelo bloco do `CLAUDE.md` do projeto (camada C6) enquanto não forem adaptadas.

Duas etapas **não têm skill própria** e são feitas direto pelo kit desta skill:

- **Thumbnail**: tokens `thumbnail.*` + `texto.py` (PIL) ou o motor (formato `thumbnail`), pela receita executada de `kit-api.md` §17.1; a peça vai para `thumbs/`, carimbada.
- **Conferência final** (camada C5): o comando `da conferencia` (`kit-api.md` §18) — DA aprovada, lint, carimbos, loudness, limites de plataforma, ficha de fatos e créditos de b-roll — que grava `qa/relatorio.json` e `qa/relatorio.md`. É o portão de publicação.

## Pastas do projeto

| pasta | conteúdo | quem escreve | quem lê |
|---|---|---|---|
| `da/` | `da.json` (fonte de verdade), `DA.md`, `fontes/ luts/ texturas/ logos/ referencias/`, `build/` (gerado), `prancha*.png`, `teste_movimento.mp4`, `rotas/` (candidatas) | video-direcao-de-arte | todas |
| `pesquisa/` | `fatos.json` (ficha de fatos verificada), `fatos.md`, `fontes.md` (fontes para a descrição), `briefing-da.md` | video-pesquisa-ia, gerar-ganchos | gerar-roteiro, video-pauta-midia, video-animacao-explicativa, video-publicacao, `da conferencia` |
| `roteiro/` | ganchos e roteiro comentado; `roteiro.md` (o roteiro limpo), `pauta.json` (pedidos de mídia) e `storyboard.json` (roteiro → cenas) | gerar-ganchos, gerar-roteiro, melhorar-roteiro; video-pauta-midia (`roteiro.md`, `pauta.json`); video-animacao-explicativa (`storyboard.json`) | transcrição (prompt de nomes), pesquisa (`conferir-roteiro`), b-roll, animação, cortes, `da conferencia` |
| `bruto/` | gravações originais (nunca alteradas) | o usuário | transcrição, montagem, cortes, `extrair`, prancha (antes/depois) |
| `transcricao/` | palavras `[{a, b, w, p}]` e segmentos | video-transcricao | legendas, montagem, cortes, motion (citações) |
| `broll/` | `broll/bruto/` = material baixado (nunca conferido) · `broll/tratado/` = material com o tratamento da DA, **carimbado** · `licencas.json` (registro de licenças) e `creditos.md` (créditos prontos) | video-broll (bancos de mídia; dona do registro), video-pauta-midia (imagens e capturas da web, trechos do YouTube) | montagem, animação explicativa, cortes, video-publicacao, `da conferencia` |
| `animacoes/` | cenas (`.js`), params, renders (`.mp4/.mov/.webm/.png` + `.da.json`) | video-animacao-explicativa, video-pauta-midia (cenas de mídia), video-motion-graphics, video-animacao-audio | montagem, efeitos sonoros (âncoras do carimbo), `da conferencia` |
| `legendas/` | cues `[{t0, t1, txt}]`, `.srt`/`.vtt`, overlays e vídeos legendados carimbados | video-legendas | montagem, cortes, video-publicacao, `da conferencia` |
| `cortes/` | `plano.json` e os cortes verticais com legenda (`<id>.mp4` + `<id>.srt`), carimbados | video-cortes-verticais (com video-legendas) | video-publicacao, `da conferencia` |
| `thumbs/` | thumbnails e variações A/B, carimbadas | direto pelo kit (`kit-api.md` §17.1) | video-publicacao, `da conferencia` |
| `render/` | XML/EDL, mixes e renders finais (carimbados); intermediários com nome começado por `_` | video-montagem, video-mixagem, video-efeitos-sonoros | `da conferencia`, video-publicacao |
| `qa/` | `relatorio.json` + `relatorio.md` (a conferência final; `previa.json`/`previa.md` nas prévias), folhas de contato | `da conferencia` | o usuário, video-publicacao (portão) |
| `publicacao/` | títulos, descrições, capítulos, hashtags, arquivos finais por plataforma | video-publicacao | o usuário |

**Intermediário começa por `_`.** Em qualquer pasta de peças (`animacoes legendas cortes thumbs render broll/tratado`), arquivo ou subpasta cujo nome começa por sublinhado (`legendas/_png/`, `render/_base recortada.mp4`, `qa/_q 0.6.png`) é material de trabalho: `conferir-carimbo`, o lint e a conferência final passam por cima. Todo o resto nessas pastas é peça e precisa de carimbo.

## Ordem e pontos de aprovação humana

```
pesquisa (ficha de fatos) → roteiro comentado → [APROVAÇÃO 1: roteiro] → DIREÇÃO DE ARTE → [APROVAÇÃO 2: prancha + teste de movimento → da.py aprovar]
→ pauta de mídia (roteiro.md + pauta.json, downloads, cenas de mídia) → gravação → transcrição → b-roll tratado + animações + motion
→ montagem → som (SFX, mix) → [APROVAÇÃO 3: corte final] → cortes verticais + legendas → thumbnail (direto pelo kit)
→ CONFERÊNCIA FINAL (da conferencia → qa/relatorio.json) → [APROVAÇÃO 4: título/thumb/descrição] → publicação
```

Nada depois de "direção de arte" começa sem `da/da.json` válido (toda skill visual faz `da.py achar`; código 2 = parar e chamar video-direcao-de-arte). Nada vai para `publicacao/` sem `qa/relatorio.json` dizendo `"ok": true`, feito com a DA atual, mais novo que o arquivo a publicar e com esse arquivo na lista `alvos`. Mudança de DA depois da aprovação 2 = `revisar` → editar → `aprovar` de novo → **re-renderizar** tudo o que a conferência (ou `conferir-carimbo`) marcar como `DA DIFERENTE`.

## O que cada skill lê da DA e escreve com carimbo

| skill | lê da DA | produz (carimba) |
|---|---|---|
| **video-direcao-de-arte** | briefing, referências (`extrair`) | `da/da.json`, `build/`, `DA.md`, `prancha*.png`, `teste_movimento.mp4`; bloco do `CLAUDE.md`; presets pessoais; o kit; a conferência final (`qa/relatorio.json`) |
| **video-pesquisa-ia** | nada visual; só o crédito de fonte (`graficos.citacao_fonte`, por `texto.credito_fonte` / `ctx.kit.credito`) | `pesquisa/fatos.json`, `fatos.md`, `fontes.md` (sem carimbo: não é peça visual); confere roteiro e storyboard contra a ficha |
| **video-pauta-midia** | `tratamento.moldura` e `graficos.citacao_fonte` (o material citado aparece com moldura e crédito), `movimento.*`, `layout.*`, `conceito.nao_faca` — pelas cenas do motor e por `ctx.kit` | `roteiro/roteiro.md` e `roteiro/pauta.json` a partir do roteiro comentado; imagens e capturas da web e trechos do YouTube em `broll/bruto/`, registrados em `broll/licencas.json`; cenas de mídia renderizadas em `animacoes/` + `.da.json` |
| **video-broll** | `tratamento.*` (`video.filtro_tratamento`, `da.py grade`), `moldura` (cena `moldura` + `video.encaixar_em_janela`), `encaixe` (`video.filtro_encaixe`), `recorte.ancora`, `graficos.citacao_fonte` (`texto.credito_fonte` / `ctx.kit.credito`), `conceito.nao_faca` (o que não baixar) | `broll/tratado/<nome>.mp4` + `.da.json` (com origem, licença e cadeia nos `parametros`; o baixado fica em `broll/bruto/`); `broll/licencas.json` e `broll/creditos.md` |
| **video-animacao-explicativa** | tudo: cenas do motor (`titulo`, `citacao`, `barras`, `moldura` + cenas próprias com as peças de `ctx.kit`), `cor.dados`, `graficos.*`, `movimento.*` (inclusive `transicoes`: `ctx.transicao`, `video.juntar`), `layout.*`, `conceito.faca/nao_faca/principios` | `roteiro/storyboard.json`; `animacoes/*.mp4/.mov/.webm` (+ `.da.json` com `ancoras` e `layout`) |
| video-transcricao | nada visual (usa `roteiro/` para o `--prompt` de nomes) | `transcricao/*.json` (sem carimbo: não é peça visual) |
| video-motion-graphics (antiga; adaptar) | `graficos.gc`, `tarja`, `marca`, `movimento`, margens — via cena `gc` do motor | `animacoes/gc_*.webm` com alfa + carimbo |
| video-animacao-audio (antiga; adaptar) | `legenda.*` (`texto.py`), `paleta`, `papeis` | `animacoes/audio_*.mp4` + carimbo |
| **video-legendas** | `legenda.*` (`Estilo.legenda`, `texto.compor_legenda`), `formatos.margens_seguras.vertical` (a legenda nunca sai da zona), `movimento.duracoes.micro/curta` (pop/fade) | `legendas/<nome>.cues.json`, `.srt`/`.vtt`, `legendas/*.mp4|.mov|.webm` + carimbo (`video.compor_cues`: todas as cues numa passada; receita em `kit-api.md` §16); PNGs de cue em `legendas/_png/` |
| video-montagem (antiga) | `movimento.transicoes`, `formatos.*.fps`, `marca.marca_dagua` | `render/*.xml`, EDL, capítulos |
| video-efeitos-sonoros (antiga) | `som.sfx`, `som.identidade`; âncoras `{t, nome, tipo}` dos carimbos de `animacoes/` | `render/trilha_sfx.wav` |
| video-mixagem (antiga) | `som.loudness.longo/curto`, `som.musica` (`video.conferir_loudness`) | `render/mix_final.wav`, `render/final.mp4` |
| **video-cortes-verticais** | `formatos.vertical`, `margens_seguras.vertical.*` (`plataforma`), `tratamento.recorte.ancora` (`video.filtro_recorte`) ou `tratamento.encaixe` (`video.filtro_encaixe`), `legenda.*`, `movimento.transicoes` (`video.juntar`), `marca.assinatura`, `som.loudness.curto` (`video.filtro_loudnorm` em duas passagens) | `cortes/plano.json`, `cortes/*.mp4` + carimbo (com `t0/t1` de origem e `plataforma` nos `parametros` — a conferência final usa essa plataforma para escolher os limites) |
| thumbnail — **direto pelo kit**, sem skill (`kit-api.md` §17.1) | `thumbnail.*`, `formatos.thumbnail`, `paleta`, `papeis.titulo`, `gradientes`, `conceito.nao_faca`; `d.zona_proibida("thumbnail")` | `thumbs/*.png` + carimbo (variações A/B) |
| conferência final — **comando do kit** `da conferencia` (`kit-api.md` §18) | tudo: `validar` + DA aprovada, `lint --estrito` (peças **e** scripts que as geram; reprova o que o lint não conseguiu ler), `conferir-carimbo --exigir-aprovada` (inclui `broll/tratado`; reprova composição com insumo sem auditoria ou de outra DA), `video.conferir_loudness` contra `som.loudness`, limites de `plataformas.json`; por posição, a ficha de fatos (video-pesquisa-ia) e os créditos do registro de licenças (video-broll) | `qa/relatorio.json` + `qa/relatorio.md` (não renderiza nada) |
| **video-publicacao** | `marca.assinatura`, `formatos`, limites de `plataformas.json` por `da.plataforma(nome)` / `da.limite(plataforma, chave)` (título, descrição, hashtags, duração, tamanho; nomes `youtube`, `shorts`, `reels`, `tiktok`); o portão `qa/relatorio.json` | `publicacao/<plataforma>/…` |

## Fluxo A — vídeo longo de YouTube (horizontal, 10–40 min)

1. `video-pesquisa-ia` monta a ficha de fatos em `pesquisa/`; gerar-ganchos → gerar-roteiro → melhorar-roteiro escrevem o roteiro, com os comentários de mídia ("aqui entra o print do anúncio", "trecho do vídeo tal"). Aprovação 1.
2. **DA**: briefing → `da/referencias/` + `extrair` → 2–3 rotas (`da.py rotas criar`) → `rotas comparar` (pranchas lado a lado) → `rotas adotar` → refinar → `prancha` + `teste-movimento` → aprovação 2 → `da.py aprovar --estrito` (regenera a prancha com o selo de aprovação). Se é canal novo: `salvar-preset <canal>`.
3. `video-pauta-midia` lê o roteiro comentado e escreve `roteiro/roteiro.md` (limpo, é o que vai para a gravação e para `fatos.py conferir-roteiro`) e `roteiro/pauta.json` (os pedidos de mídia); baixa imagens, capturas e trechos do YouTube para `broll/bruto/` com registro em `broll/licencas.json`, e entrega as cenas de mídia em `animacoes/`. Os pedidos de banco de mídia da pauta seguem para a `video-broll`.
4. Gravação em `bruto/`. `video-transcricao` → `transcricao/` (palavra a palavra e segmentos).
5. Em paralelo e sempre sob a trava: `video-broll` baixa e trata (`da.py grade`), `video-animacao-explicativa` monta o storyboard e renderiza as cenas do roteiro (`da.py render --fila …`), `video-motion-graphics` gera os GCs (`--cena gc`, vp9alfa).
6. `video-montagem` monta o XML (transições de `movimento.transicoes`), `video-efeitos-sonoros` sonoriza as âncoras, `video-mixagem` fecha em `som.loudness.longo` (−14 LUFS / −1 dBTP). Aprovação 3 sobre `render/final.mp4`. Para ver o estado antes de cortar: `da conferencia render/final.mp4` (só o vídeo longo) ou `da conferencia --previa`.
7. `video-cortes-verticais` tira 3–6 cortes (`plataforma: uniao` ou por app) com `video-legendas`; a thumbnail sai direto pelo kit, em 3 variações (`kit-api.md` §17.1; zona proibida inferior direita).
8. **Conferência final**: `da conferencia` — DA aprovada, `lint --estrito`, carimbos (com `broll/tratado` e insumos), loudness e limites de plataforma de `render/final.mp4` e de cada corte, fatos e créditos. Relatório em `qa/`; cada erro diz como corrigir. Aprovação 4.
9. `video-publicacao` escreve título/descrição/capítulos dentro dos limites de `plataformas.json`, confere o portão (`qa/relatorio.json`) e organiza `publicacao/youtube/`, `shorts/`, `reels/`, `tiktok/`.

## Fluxo B — peça curta nativa vertical (20–90 s, Reels/TikTok/Shorts)

1. Fatos (se a peça cita modelo, preço ou data: `video-pesquisa-ia`), gancho e roteiro curtos (gerar-ganchos → gerar-roteiro). Aprovação 1.
2. **DA**: se o canal já tem preset pessoal, `init --base <canal> --herdar` e só ajuste `conceito.frase`, talvez `primaria`; prancha **vertical** é a que importa (`prancha --formato vertical`, `teste-movimento --formato vertical`) — confira legenda e GC dentro da zona `uniao`, o GC fora da faixa da legenda, e a legibilidade na seção "Em escala 1:1" com a prancha na largura da tela do celular. Aprovação 2 → `aprovar`.
3. `video-pauta-midia`, se o roteiro pede print ou trecho de vídeo; gravação vertical (ou horizontal + `filtro_recorte` com `recorte.ancora`); transcrição.
4. `video-legendas` queima legenda palavra a palavra (`legenda.estilo`, `tamanho` ≥ 0,052, `posicao.vertical.y` 0,56–0,60, `largura_max` respeitando os 61 % úteis); `video-animacao-explicativa`/`motion` só com `plataforma` definida; b-roll tratado com a mesma cadeia.
5. Mix em `som.loudness.curto`. Capa/thumb vertical direto pelo kit (`formatos` extra `capa_reels` 1080×1350 se o canal usar).
6. **Conferência final** da peça como peça curta: `da conferencia --corte render/final.mp4` (ou `da conferencia --corte K01` para um corte em `cortes/`), com `--plataforma` se ela vai para um app só — carimbos, loudness `curto` e a duração de **cada** app de destino (Shorts 180 s; Reels de 3 s a 20 min, recomendando até 3 min; TikTok 60 min — `plataformas.md` §3).
7. Publicação por app com os limites de legenda/hashtag de `plataformas.md` §4.

## Regras transversais

- **Uma tarefa pesada por vez** na máquina de 8 GB: todo ffmpeg/Chromium/whisper passa por `trava.py` (as skills escritas contra o kit já entram sozinhas; as antigas devem envolver seus comandos). Dois agentes em paralelo esperam na fila, não competem por memória.
- **Prévias baratas antes do render caro**: `--quadro T` e `--escala 0.5` no motor; `--inicio/--duracao` no `grade`; 3 s de teste de movimento; `da conferencia --previa` para ver o que falta antes de a DA estar aprovada.
- **Carimbo em tudo que é peça**; composição carimba com `insumos=[…]` (as funções de `video.py` fazem sozinhas) e herda o pior dos insumos. `broll/bruto/` não é conferido, `broll/tratado/` é; intermediário leva `_` no nome.
- **Mudança de visual é mudança de DA**: nunca na peça. O custo é re-renderizar o que `conferir-carimbo` apontar — e é por isso que a aprovação 2 vem antes de qualquer render.
- **Datas**: os limites de plataforma valem até a revalidação trimestral (`plataformas.md` §8, próxima em 2027-01-05); a conferência final avisa quando o prazo venceu e a skill de publicação confere a data antes de usar.
