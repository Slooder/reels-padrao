# Plataformas — zonas seguras, specs de envio e limites

**Verificado em: 2026-10-05.** Próxima revalidação: até 2027-01-05 (a cada 3 meses — ver a seção 8).

Este arquivo é a versão legível de `"$CRIABR_SKILLS"/video-direcao-de-arte/kit/plataformas.json`. Os dois dizem a mesma coisa; scripts leem o JSON, pessoas leem este texto. Se um número mudar, mude nos dois.

Cobre YouTube (vídeo longo), YouTube Shorts, Instagram Reels e TikTok.

## Como ler

- **Oficial** = lido em página de ajuda, documentação ou gabarito publicado pela própria plataforma (ou em norma técnica) na data acima.
- **Estimativa** = fonte de mercado ou medição própria. Vem sempre marcada com **(estimativa)** ou com asterisco.
- **Não encontrado** = procurado e não achado em fonte confiável. No JSON aparece como `null`. Não significa zero nem "sem limite".
- Frações: topo e base são frações da **altura** do quadro; direita e esquerda, da **largura**. Os pixels citados valem para 1080×1920 (vertical) e 1920×1080 (horizontal).

> **Aviso sobre estimativas.** Nenhuma das três plataformas publica zona segura para vídeo **orgânico**. O que existe de oficial são os gabaritos de **anúncio**, que reservam espaço a mais (botão de chamada, rótulo de patrocinado). Esta referência adota os números de anúncio como limite de segurança, porque quem cabe neles cabe no orgânico. Também são estimativa, e não regra de plataforma: o alvo de loudness (−14 LUFS), a zona do selo de duração na thumbnail, o recorte das capas na grade do perfil, os trechos visíveis de título e legenda e o limite de 4.000 caracteres da legenda do TikTok no aplicativo. A lista completa está na seção 7.

## Como a DA e o kit usam estes números

Verificado no kit 1.5.0 (os valores abaixo saem de `da.py token`, `d.margens()` e `da.limite()` no preset `dossie`). **Nomes**: em `kit/plataformas.json` todas as seções (`specs`, `limites_texto`, `margens_seguras_vertical`, `capas`, `thumbnail`) usam os nomes canônicos `youtube`, `shorts`, `reels`, `tiktok`; apelidos (`instagram`, `instagram_reels`, `ig`, `youtube_longo`, `yt`, `tt`…) são aceitos por `da.nome_plataforma`. No `da.json` a zona segura do Reels continua na chave `instagram` (esquema v1) e quem consulta pode pedir `reels`.

| número desta referência | onde mora no `da.json` | como as peças leem |
|---|---|---|
| Margens verticais por app (§1) e a união | `formatos.margens_seguras.vertical.{instagram, tiktok, shorts, uniao}` = `[topo, direita, base, esquerda]` em frações — dossiê: `uniao = [0.15, 0.2778, 0.35, 0.1111]` | Python `d.margens("vertical", "tiktok")` → `{x0: 120, y0: 240, x1: 780, y1: 1260, …}` (`"reels"` = `"instagram"`); motor `ctx.area_segura('uniao')`; cenas embutidas aceitam o parâmetro `plataforma` (sem ele usam `uniao`); a prancha vertical desenha as quatro zonas sobrepostas com a legenda na posição real |
| Zona horizontal EBU R 95 para gráficos (§2) | `formatos.margens_seguras.horizontal.padrao = [0.05, 0.05, 0.05, 0.05]` | `d.margens("horizontal")` → 54 px em cima/embaixo, 96 px nos lados em 1080p |
| Legenda vertical: os três retângulos honestos (§1 "Na prática") | `legenda.posicao.vertical.y` (0,56–0,60) e `legenda.largura_max` (fração da largura) | `legenda.posicao.vertical.largura_max` (0,61 nos presets) limita a largura no vertical; `validar` avisa quando o bloco sai da zona `uniao` em altura **ou em largura**; `texto.compor_legenda` e `ctx.kit.legenda` centram no retângulo da zona, quebram em linhas e encolhem por último — a legenda nunca é desenhada fora da zona |
| Resolução, fps e proporção por plataforma (§3) | `formatos.horizontal/vertical/quadrado/thumbnail` (`largura`, `altura`, `fps` racional) | `d.formato("vertical")` → `(1080, 1920, Fraction(30000, 1001))`; motor `--formato vertical`; `video.args_encode(fps)` |
| Loudness −14 LUFS / −1 dBTP (estimativa) | `som.loudness.longo` e `som.loudness.curto` | `video.conferir_loudness(d, arquivo, tipo)` compara com `ebur128`; a conferência final (`da conferencia`) mede `render/final.mp4` contra `longo` e cada `cortes/*.mp4` contra `curto` |
| Selo de duração da thumbnail (§5: reserva de 25 % × 22 % no canto inferior direito) | `thumbnail.zona_proibida = "inferior_direita"` + `thumbnail.zona_proibida_tamanho` (padrão `[0.25, 0.22]`, lido de `thumbnail.youtube.zona_timestamp.reserva_recomendada`) | `d.zona_proibida("thumbnail")` → `{x0: 960, y0: 562, x1: 1280, y1: 720, largura: 320, altura: 158}`; em cena, `ctx.zona_proibida()`; a prancha hachura esse mesmo retângulo |
| Limites de texto, duração e tamanho (§3, §4) | não são tokens da DA: ficam só em `kit/plataformas.json` (`verificado_em`) | `da.limite("reels", "hashtags_max")` → `5`; `da.limite("shorts", "duracao_max_s")` → `180`; `da.plataforma("tiktok")` → ficha com `texto_max`, `duracao_max_s`, `tamanho_max_mb`, `verificado_em` e `vencida` (passou do prazo de revalidação); `None` = número não encontrado em fonte confiável. A conferência final (`da conferencia`, `kit-api.md` §18) lê daqui a duração mínima, máxima e recomendada, o tamanho e a resolução de cada plataforma de destino — vídeo longo contra as de orientação horizontal, peça curta contra as verticais (ou a plataforma declarada no carimbo do corte) — e avisa (`tecnico.plataformas_vencidas`) quando `vencida` é verdadeiro |

Os presets copiam os números de `kit/plataformas.json`; quando esta referência for revalidada (§8), atualize o JSON, este arquivo e os presets — projetos antigos continuam com os números da época em que a DA foi aprovada (é o esperado: mudar margem é nova revisão da DA).

---

## 1. Zona segura do vídeo vertical (1080×1920)

### Margens por aplicativo

| Aplicativo | Topo | Base | Esquerda | Direita acima dos botões | Direita ao lado dos botões | Coluna de botões começa em | Origem |
|---|---|---|---|---|---|---|---|
| **Instagram Reels** | 14% · 269 px | 35% · 672 px | 6% · 65 px | 6% · 65 px | 21% · 227 px (estimativa) | 60% da altura · y = 1152 | Oficial — Meta, anúncios em Reels |
| **TikTok** | 12,5% · 240 px | 34,4% · 660 px | 11,1% · 120 px | 11,1% · 120 px | 27,8% · 300 px | 43,75% da altura · y = 840 | Oficial — gabarito In-Feed de anúncios |
| **YouTube Shorts** | 15% · 288 px | 35% · 672 px | 4,4% · 48 px | 17,8% · 192 px | 17,8% · 192 px | não se aplica | Oficial — gabarito vertical do Google Ads |
| **União (pior caso)** | **15% · 288 px** | **35% · 672 px** | **11,1% · 120 px** | **17,8% · 192 px** | **27,8% · 300 px** | **43,75% · y = 840** | Calculado a partir dos três |

Quem define cada lado da união: topo — Shorts; base — Instagram e Shorts; esquerda — TikTok; direita ao lado dos botões — TikTok; direita acima dos botões — Shorts.

### Os dois retângulos da união

| Retângulo | x | y | Tamanho | Quando usar |
|---|---|---|---|---|
| **Estrito** | 120 a 780 | 288 a 1248 | 660 × 960 px | Qualquer texto, em qualquer altura. Livre nos três apps. |
| **Acima da coluna** | 120 a 888 | 288 a 840 | 768 × 552 px | Texto que fica inteiro na metade de cima (títulos, ganchos). |

No JSON, `direita` é sempre a margem **estrita** (vale ao lado dos botões). `direita_acima_da_coluna` é a margem menor, válida só acima de `coluna_botoes_a_partir_de_y`.

### Na prática

- **Nada importante abaixo de y = 1248** (os 35% de baixo): ali ficam nome da conta, legenda do post, áudio e, em anúncio, o botão de chamada.
- **Nada importante acima de y = 288** (os 15% de cima): abas, busca e rótulos.
- O retângulo estrito não é centrado no quadro: o centro dele é x = 450, e o do quadro é x = 540. Para legenda queimada há três saídas honestas:
  1. bloco centrado no quadro (x = 540) e abaixo de y = 840: largura máxima de **480 px**;
  2. bloco centrado no retângulo estrito (x = 450): largura máxima de **660 px**, levemente deslocado para a esquerda;
  3. bloco inteiro acima de y = 840 e centrado no quadro: largura máxima de **696 px**.
- Instagram com aviso legal no anúncio: a Meta pede **40% da base inteira** livre.
- Telas mais altas que 9:16 podem dar zoom no vídeo e cortar as bordas; o que está dentro da zona segura não é cortado.
- TikTok com âncora (link ou produto) aumenta a área coberta na base — existe um gabarito oficial separado ("In-Feed with Anchor"). Versão árabe espelha os botões para a esquerda.

### Detalhe de cada fonte

- **Instagram.** O guia de anúncios da Meta diz, literalmente, para deixar livres "at least 14% of the top, 35% of the bottom, and 6% on each side". O diagrama oficial da Central de Ajuda para Empresas mostra, além disso, um recorte no canto inferior direito que sobe até 40% da altura. A largura desse recorte **não vem rotulada**: os 21% foram medidos no diagrama e coincidem com a medição publicada pelo AdKit (226,8 px). Fontes: [Meta Ads Guide — Reels](https://www.facebook.com/business/ads-guide/update/video/instagram-reels), [Meta — safe zone](https://www.facebook.com/business/help/980593475366490), [AdKit](https://adkit.so/tools/safe-zones/instagram) (mercado).
- **TikTok.** Medido pixel a pixel no gabarito oficial `Feed.png` (versão padrão, sem âncora). O desenho usa base 720×1280 com cotas 160 (topo), 440 (base), 80 (cada lado) e coluna direita de 120 × 720; convertido para 1080×1920 multiplicando por 1,5. A página oficial avisa que a zona varia com o tamanho da legenda do anúncio e que a prévia pode diferir um pouco do aparelho. Fontes: [TikTok Auction In-Feed Ads](https://ads.tiktok.com/help/article/tiktok-auction-in-feed-ads?lang=en), [gabarito .zip](https://lf-tt4b.tiktokcdn.com/obj/i18nblog/tt4b_cms/en-US/5jqet0ab9qci-10e7f5Vig4uhAscNP8XPB0.zip).
- **YouTube Shorts.** Medido pixel a pixel no gabarito oficial "YouTube | Vertical Video Ads — Safe Zone Overlay": área livre de x = 48 a 888 e y = 288 a 1248. É um gabarito **universal** de anúncio vertical, não a foto de uma tela do Shorts. Fontes: [Google Ads — About video ad specs](https://support.google.com/google-ads/answer/13547298?hl=en), [gabarito PNG](https://services.google.com/fh/files/misc/youtubesafezoneoverlay_vertical_final.png).

### Quanto de folga isso carrega no orgânico (estimativa)

Faixas relatadas por fontes de mercado para a interface orgânica em 2026. As fontes divergem bastante entre si. **Não use como limite**; serve só para saber que os números de cima são conservadores.

| Aplicativo | Topo | Base | Direita | Esquerda |
|---|---|---|---|---|
| Instagram Reels | 10,9% a 14% | 16,1% a 35% | 6% a 7,8% | 0 a 6% |
| TikTok | 5,6% a 10,4% | 13% a 16,9% | 11,1% a 15,2% | 0 a 5,6% |
| YouTube Shorts | 6,3% a 19,8% | 15% a 19,8% | 8,9% a 13% | 0 a 5,6% |

Fontes (mercado): [AdaptlyPost](https://adaptlypost.com/blog/social-media-safe-zones-2026-complete-guide), [PostEverywhere](https://posteverywhere.ai/blog/tiktok-aspect-ratio), [ClipSpeed](https://www.clipspeed.ai/blog/youtube-shorts-size.html), [Poster.ly](https://www.poster.ly/tools/youtube-shorts-safe-zone-checker), [Hopper HQ](https://www.hopperhq.com/blog/instagram-reel-size/), [Reap](https://reap.video/blog/short-form-video-safe-zones).

---

## 2. Zona segura do vídeo horizontal (1920×1080)

Nenhuma plataforma publica zona segura para vídeo horizontal orgânico. O padrão adotado é a norma de radiodifusão.

| Perfil | Topo | Base | Esquerda | Direita | Origem |
|---|---|---|---|---|---|
| **Padrão — gráficos** (texto, logotipo, GC) | 5% · 54 px | 5% · 54 px | 5% · 96 px | 5% · 96 px | Oficial — norma EBU R 95 |
| Padrão — ação | 3,5% · 38 px | 3,5% · 38 px | 3,5% · 67 px | 3,5% · 67 px | Oficial — norma EBU R 95 |
| YouTube como anúncio | 3,5% · 38 px | 35,8% · 387 px | 2% · 38 px | 8,4% · 162 px | Oficial — gabarito horizontal do Google Ads |

O gabarito de anúncio ainda tem dois recortes no topo: canto superior esquerdo (496 × 183 px, ou 25,8% × 16,9%) e canto superior direito (476 × 133 px, ou 24,8% × 12,3%). Só interessa se a peça também rodar como anúncio; para vídeo orgânico a base de 35,8% é exagerada.

Sobreposições do player do YouTube que cobrem o quadro:

| Elemento | Quando aparece | Regra | Origem |
|---|---|---|---|
| Tela final | Últimos 5 a 20 s | O vídeo precisa ter 25 s ou mais; até 4 elementos em 16:9 | Oficial |
| Marca d'água do canal | Últimos 15 s, a partir de um instante escolhido ou o vídeo inteiro | Imagem quadrada, mínimo de 150×150 px, menos de 1 MB; só no modo paisagem | Oficial (a posição exata não está documentada) |
| Controles, barra de progresso e título | Ao pausar, tocar ou passar o mouse | Base e topo do player | Observação, não oficial |
| Legendas automáticas (CC) | Quando o espectador liga | Centro da base, por padrão | Observação, não oficial |

Fontes: [EBU R 95](https://tech.ebu.ch/publications/r095), [Google Ads — About video ad specs](https://support.google.com/google-ads/answer/13547298?hl=en), [gabarito horizontal PNG](https://services.google.com/fh/files/blogs/ytsafezoneoverlay-horizontal.png), [YouTube — end screens](https://support.google.com/youtube/answer/6388789?hl=en), [YouTube — channel branding](https://support.google.com/youtube/answer/10456525?hl=en).

---

## 3. Specs de envio

### Quadro comparativo

| Item | YouTube longo | YouTube Shorts | Instagram Reels | TikTok |
|---|---|---|---|---|
| Resolução | 1920×1080 (ou 3840×2160) | 1080×1920; máximo de 1080p | 1080×1920 (estimativa); mínimo de 720 px; pela API, largura máxima de 1920 px | 1080×1920 (estimativa); pela API, de 360 a 4096 px por lado |
| Proporção | 16:9 | 9:16 (qualquer quadrado ou vertical vira Short) | 9:16 (aceita de 1.91:1 a 9:16) | 9:16 (aceita 1:1 e 16:9) |
| fps | O mesmo da captação; comuns: 24, 25, 30, 48, 50, 60 | Igual ao YouTube | Mínimo de 30 (Central de Ajuda); 23 a 60 (API) | 23 a 60 (API) |
| Container | MP4 com fast start, sem edit lists | Igual ao YouTube | MP4 ou MOV, fast start, sem edit lists | MP4 (recomendado), WebM ou MOV |
| Codec de vídeo | H.264 High Profile, progressivo, 2 B-frames, GOP fechado de metade do fps, CABAC, 4:2:0 | Igual ao YouTube | H.264 ou HEVC, mesmos parâmetros | H.264 (recomendado), H.265, VP8 ou VP9 |
| Bitrate de vídeo | 1080p: 8 Mbps (24–30 fps) ou 12 Mbps (48–60 fps) | Igual à linha de 1080p | Máximo de 25 Mbps VBR (API); recomendado: não encontrado | Mínimo de 516 kbps (anúncio); recomendado: não encontrado (mercado: 8 a 12 Mbps) |
| Áudio | AAC-LC, 48 kHz, estéreo, 384 kbps | Igual ao YouTube | AAC, 48 kHz, 128 kbps | Não encontrado (mercado: AAC) |
| Loudness | −14 LUFS, pico real −1 dBTP (estimativa) | −14 LUFS (estimativa) | −14 LUFS (estimativa) | −14 LUFS (estimativa) |
| Cor | BT.709 SDR; HDR em Rec. 2020 com PQ ou HLG | BT.709 SDR; HDR: não encontrado | Não encontrado para vídeo (capa: sRGB) | Não encontrado |
| Duração mínima | Não encontrado | Não encontrado | 3 s (API) | Não encontrado |
| **Duração máxima** | **12 h** (15 min sem verificar a conta) | **3 min (180 s)** | **20 min**; só até **3 min** é recomendado a novos públicos; pela API, 15 min | **60 min** enviado; **10 min** gravado no app; pela API, 10 min |
| Tamanho máximo | 256 GB | 256 GB (limite geral do YouTube) | 300 MB (API); 4 GB (anúncio); pelo app: não encontrado | 4 GB (API); 500 MB (anúncio); pelo app: não encontrado |

### YouTube (vídeo longo)

Tudo oficial, salvo o loudness.

- **Limite de envio:** "256 GB or 12 hours, whichever is less". Sem verificar a conta, 15 minutos.
- **Container e codec:** MP4 com o moov atom no início (fast start) e sem edit lists; H.264 High Profile, progressivo, 2 B-frames consecutivos, GOP fechado de metade do fps, CABAC, bitrate variável, croma 4:2:0. Aceita também MOV, ProRes, DNxHR, HEVC, WebM e outros.
- **Áudio:** AAC-LC (ou Opus), 48 kHz, estéreo. Bitrates recomendados: mono 128 kbps, estéreo 384 kbps, 5.1 512 kbps.
- **Cor em SDR:** BT.709 em primárias, transferência e matriz. O YouTube converte faixa completa (full range) para faixa limitada.
- **HDR:** Rec. 2020 com PQ ou HLG, 10 ou 12 bits, com metadados; codecs VP9 Profile 2, AV1 ou HEVC. DCI-P3 não é suportado. O YouTube gera a versão SDR sozinho.
- **Barras pretas:** não embutir; o player se adapta à proporção.
- **Loudness (estimativa):** o YouTube não documenta o alvo. O valor de −14 LUFS integrado é consenso de mercado, medido em "Estatísticas para nerds"; o YouTube só atenua o que passa do alvo. Pico real de −1 dBTP é recomendação de mercado.

Bitrates de vídeo recomendados (Mbps):

| Resolução | SDR 24–30 fps | SDR 48–60 fps | HDR 24–30 fps | HDR 48–60 fps |
|---|---|---|---|---|
| 720p | 5 | 7,5 | 6,5 | 9,5 |
| 1080p | 8 | 12 | 10 | 15 |
| 1440p | 16 | 24 | 20 | 30 |
| 2160p (4K) | 35 a 45 | 53 a 68 | 44 a 56 | 66 a 85 |

Fontes: [encoding settings](https://support.google.com/youtube/answer/1722171?hl=en), [resolução e proporção](https://support.google.com/youtube/answer/6375112?hl=en), [limite de envio](https://support.google.com/youtube/answer/71673?hl=en), [formatos aceitos](https://support.google.com/youtube/troubleshooter/2888402?hl=en), [HDR](https://support.google.com/youtube/answer/7126552?hl=en); loudness (mercado): [Production Advice](https://productionadvice.co.uk/stats-for-nerds/), [Fora Soft](https://www.forasoft.com/learn/audio-for-video/articles-audio/lufs-targets-per-platform-2026).

### YouTube Shorts

- **Duração máxima: 3 minutos.** Desde 15/10/2024, todo envio quadrado ou vertical de até 3 minutos vira Short (canais oficiais de artista: desde 08/12/2025). Envios anteriores continuam como vídeo comum. Oficial.
- **Atenção:** Short com mais de 1 minuto e reivindicação ativa de Content ID é **bloqueado no mundo todo**. Cuidado com música de terceiros em peças de 61 a 180 s. Oficial.
- **Duração mínima:** não encontrado.
- **Resolução:** a ajuda diz "You can upload Short videos with a maximum resolution of 1080p". Oficial.
- **Codec, bitrate, áudio e cor:** o YouTube não publica tabela própria para Shorts; valem as recomendações gerais (linha de 1080p). HDR em Shorts: não encontrado.
- **Teste A/B:** não existe para Shorts. Oficial.

Fontes: [three-minute Shorts](https://support.google.com/youtube/answer/15424877?hl=en), [criar Shorts](https://support.google.com/youtube/answer/10059070?hl=en), [teste A/B](https://support.google.com/youtube/answer/13861714?hl=en).

### Instagram Reels

- **Duração:** a Central de Ajuda diz "You can record and edit videos up to 20 minutes with Instagram Reels" e, em nota, "Reels over 3 minutes won't be recommended to new audiences". Para alcance, **180 s é o teto prático**. O recurso é liberado aos poucos; nem toda conta vê os 20 minutos. Oficial.
- **Central de Ajuda (app):** proporção de 1.91:1 a 9:16, mínimo de 30 fps e de 720 px. Detalhes técnicos: progressivo, High profile, 2 B-frames, GOP fechado de metade do fps, CABAC, 4:2:0; áudio estéreo (ou estéreo + 5.1) a 48 kHz ou 96 kHz; capa em png ou jpg. Oficial.
- **Graph API v26.0 (agendadores):** MP4 ou MOV, H.264 ou HEVC, 23 a 60 fps, largura máxima de 1920 px, bitrate VBR de até 25 Mbps, áudio AAC de até 48 kHz a 128 kbps, **de 3 s a 15 min, até 300 MB**. Oficial.
- **Anúncio em Reels:** MP4 ou MOV, 9:16, resolução recomendada de 1440×2560, de 0 s a 15 min, até 4 GB. Oficial.
- **1080×1920** é o padrão de mercado (estimativa); a Central de Ajuda só exige proporção, 720 px e 30 fps.
- **Não encontrado:** tamanho máximo pelo aplicativo, bitrate recomendado, espaço de cor do vídeo, HDR e loudness. Mercado: BT.709 SDR e −14 LUFS (há fontes que citam de −10 a −16).
- Para preservar qualidade, ligar no app "Enviar na qualidade mais alta" (Configurações › Qualidade da mídia). Oficial.

Fontes: [Reel size & aspect ratios](https://help.instagram.com/1038071743007909), [Record a reel](https://help.instagram.com/2720958398006062), [Graph API — IG User Media](https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/media), [Meta Ads Guide — Reels](https://www.facebook.com/business/ads-guide/update/video/instagram-reels).

### TikTok

- **Duração:** o suporte oficial diz "Videos you record in TikTok can be up to 10 minutes long. Videos you upload in TikTok can be up to 60 minutes long." Limites maiores são liberados aos poucos por conta e região. Oficial.
- **API de publicação (agendadores):** MP4 (recomendado), WebM ou MOV; H.264 (recomendado), H.265, VP8 ou VP9; 23 a 60 fps; de 360 a 4096 px por lado; até 4 GB. Toda conta posta 3 minutos; algumas têm 5 ou 10; o máximo por API é 10 minutos. Oficial.
- **Anúncio In-Feed (não Spark):** 9:16 a partir de 540×960, até 10 minutos, até 500 MB, bitrate mínimo de 516 kbps. Oficial.
- **1080×1920** é o padrão de mercado (estimativa); o TikTok não publica resolução recomendada para vídeo orgânico.
- **Não encontrado:** duração mínima, codec e bitrate de áudio, espaço de cor, HDR, loudness e tamanho máximo pelo aplicativo. Mercado: AAC, BT.709 SDR, −14 LUFS, vídeo de 8 a 12 Mbps. Os relatos de tamanho máximo divergem muito (72 MB no Android e 287,6 MB no iOS segundo uma fonte; de 500 MB a 10 GB no envio pela web segundo outras).

Fontes: [suporte — Camera tools](https://www.tiktok.com/support/faq_detail?id=7581821547946580492), [API — Media Transfer Guide](https://developers.tiktok.com/doc/content-posting-api-media-transfer-guide), [TikTok Auction In-Feed Ads](https://ads.tiktok.com/help/article/tiktok-auction-in-feed-ads?lang=en); mercado: [PostEverywhere](https://posteverywhere.ai/blog/tiktok-aspect-ratio).

---

## 4. Limites de texto

| Campo | Limite | Origem |
|---|---|---|
| **YouTube — título** | 100 caracteres; `<` e `>` são proibidos | Oficial |
| YouTube — título visível antes de cortar | 60 a 70 caracteres | Estimativa |
| **YouTube — descrição** | 5.000 caracteres (a API fala em 5.000 **bytes**: acento e emoji pesam mais) | Oficial |
| YouTube — descrição visível antes do "mais" | 120 a 150 caracteres | Estimativa |
| **YouTube — tags** | 500 caracteres na soma; as vírgulas contam, e tag com espaço conta como se tivesse aspas | Oficial (API) |
| **YouTube — hashtags** | Até 3 aparecem junto ao título; com mais de 60, o YouTube ignora **todas** | Oficial |
| **Shorts — título e descrição** | Os mesmos 100 e 5.000 do vídeo comum | Oficial |
| **Reels — legenda** | 2.200 caracteres | Oficial (Graph API) |
| **Instagram — hashtags** | **5 por publicação** (legenda e comentários somados) | Oficial (Central de Ajuda) |
| Reels — menções com @ | 20 | Oficial (Graph API) |
| Reels — legenda visível antes do "mais" | Cerca de 55 caracteres no player de Reels; cerca de 125 no feed | Estimativa |
| **TikTok — legenda de vídeo pela API** | 2.200 (unidades UTF-16); hashtags e menções contam dentro | Oficial (API) |
| TikTok — legenda de vídeo no aplicativo | 4.000 caracteres | Estimativa |
| TikTok — post de fotos pela API | Título de 90; descrição de 4.000 | Oficial (API) |
| TikTok — quantidade de hashtags | Não encontrado | — |
| TikTok — legenda visível antes do "mais" | 55 a 100 caracteres | Estimativa |

### Capítulos do YouTube — regras para valerem

Todas oficiais:

1. A lista de tempos e títulos vai na **descrição**.
2. O primeiro tempo é **00:00**.
3. Pelo menos **três** tempos, em ordem **crescente**.
4. Cada capítulo dura no mínimo **10 segundos**.
5. Capítulos manuais substituem os automáticos.
6. O recurso fica indisponível se o canal tiver strike ativo ou se o conteúdo puder ser inadequado para alguns espectadores.

### Observações

- **Hashtags do Instagram.** A Central de Ajuda diz: "You can use up to 5 tags on a post. If you include more than 5 tags on a single photo/video, your comment won't post." O limite foi anunciado pela conta @creators em 18/12/2025. A documentação da Graph API ainda diz "30 hashtags" — está defasada; use 5.
- **Tags do YouTube.** A própria ajuda diz que elas têm papel mínimo na descoberta e servem para grafias erradas comuns. Tags em excesso na descrição violam a política de spam.
- **Legenda do TikTok.** Se a publicação passar por agendador, o teto real é 2.200, não 4.000.

Fontes: [YouTube — Edit video settings](https://support.google.com/youtube/answer/57404?hl=en), [YouTube Data API — Videos](https://developers.google.com/youtube/v3/docs/videos), [YouTube — tags](https://support.google.com/youtube/answer/146402?hl=en), [YouTube — hashtags](https://support.google.com/youtube/answer/6390658?hl=en), [YouTube — capítulos](https://support.google.com/youtube/answer/9884579?hl=en), [Instagram — hashtags](https://help.instagram.com/351460621611097), [Graph API — IG User Media](https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/media), [TikTok API — Direct Post](https://developers.tiktok.com/doc/content-posting-api-reference-direct-post), [TikTok API — Photo Post](https://developers.tiktok.com/doc/content-posting-api-reference-photo-post); mercado: [BetaNews](https://betanews.com/2025/12/19/instagram-puts-a-limit-on-hashtag-usage/), [HowManyWords](https://howmanywords.app/blog/youtube-character-limits), [ClipSpeed](https://www.clipspeed.ai/blog/instagram-reels-captions.html), [RecurPost](https://recurpost.com/tiktok-scheduler/tiktok-character-limits-and-hashtags/).

---

## 5. Thumbnail do YouTube

Não há skill de thumbnail: ela é feita direto pelo kit, com os tokens `thumbnail.*` da DA, pela receita de `kit-api.md` §17.1. Esta seção é a regra de plataforma que a receita segue.

| Item | Valor | Origem |
|---|---|---|
| Resolução recomendada | **3840×2160** ("tão grande quanto possível") | Oficial |
| Resolução mínima para não ser rebaixada no teste A/B | 1280×720 | Oficial |
| Largura mínima | 640 px | Oficial |
| Proporção | 16:9 | Oficial |
| Formatos | JPG ou PNG (a página do Google Ads cita também GIF) | Oficial |
| Peso máximo | **2 MB pelo celular; 50 MB pelo computador**; podcast pelo celular: 10 MB | Oficial |
| Peso que sobe por qualquer caminho | Até 2 MB | Derivado |
| Requisito | Conta verificada | Oficial |

Em vídeo **vertical**, a thumbnail 16:9 personalizada é trocada por uma 4:5 gerada automaticamente na página inicial, no Explorar e nas inscrições; a personalizada continua no feed de exibição, no histórico e fora do celular. Oficial.

### Teste A/B de título e thumbnail

Nome atual na ajuda: "A/B test titles & thumbnails" (antes, "Test & compare"). Tudo oficial.

- Até **3 variações**, em três modos: só título, só thumbnail, ou título e thumbnail.
- Vence a variação com maior **participação no tempo de exibição** (watch time share) — não a de maior taxa de cliques.
- O teste termina em até **duas semanas**. Sem vencedor claro, fica a primeira variação enviada.
- Só no **YouTube Studio pelo computador**, com recursos avançados ativados.
- Não vale para Shorts, lives agendadas, estreias, vídeos feitos para crianças, vídeos para público adulto e vídeos privados.
- Se **alguma** thumbnail do teste tiver menos de 1280×720, **todas** são rebaixadas para 854×480.
- Trocar título ou thumbnail no meio do teste interrompe o teste.

### Zona do selo de duração (estimativa — medição própria)

O YouTube não documenta o selo. Ele fica no **canto inferior direito**, tem altura fixa de 20 px de tela e largura conforme o texto, então ocupa fração **maior** quanto menor a miniatura.

| Onde foi medido | Miniatura (px de tela) | Selo + folga | Fração da largura | Fração da altura |
|---|---|---|---|---|
| Busca no desktop, "1:31:02" | 500 × 281 | 60 × 28 | 12,1% | 10,0% |
| Busca no desktop, "50:32" | 500 × 281 | 51 × 28 | 10,1% | 10,0% |
| Busca no site móvel (tela de 375 px), "1:31:02" | 375 × 210 | 56 × 28 | 15,1% | 13,3% |
| Lista lateral da página do vídeo, "44:18" | 234 × 132 | 43 × 24 | 18,2% | 18,3% |
| Lista lateral da página do vídeo, "0:16" | 234 × 132 | 40 × 28 | 17,0% | 21,3% |

**Reserva recomendada: 25% da largura × 22% da altura no canto inferior direito** — 320 × 158 px em 1280×720, 480 × 238 px em 1920×1080, 960 × 475 px em 3840×2160. É o pior caso medido arredondado para cima; em miniaturas ainda menores (TV, telas finais) pode ser mais.

### Outras sobreposições na thumbnail

| Elemento | Onde | Medida | Origem |
|---|---|---|---|
| Cantos arredondados | Os quatro cantos | Raio de 12 px numa miniatura de 436 px (cerca de 2,8% da largura) | Estimativa — medição própria |
| Selo de playlist ("N vídeos") ou de ao vivo | Canto inferior direito | 76 × 20 px numa miniatura de 500 px | Estimativa — medição própria |
| "Assistir mais tarde" e "Adicionar à fila" | Canto superior direito, ao passar o mouse no desktop | Não medido | Observação |
| Barra vermelha de progresso | Borda inferior, em vídeo já iniciado | Não medido | Observação |
| Prévia em movimento | Substitui a thumbnail ao passar o mouse ou parar a rolagem | — | Observação |

Fontes: [YouTube — custom thumbnails](https://support.google.com/youtube/answer/72431?hl=en), [YouTube — A/B test](https://support.google.com/youtube/answer/13861714?hl=en), [Google Ads — About video ad specs](https://support.google.com/google-ads/answer/13547298?hl=en); medição própria no DOM de [youtube.com](https://www.youtube.com/results?search_query=documentary+history) em 2026-10-05.

---

## 6. Capas de Reels, TikTok e Shorts

| Item | Reels | TikTok | Shorts |
|---|---|---|---|
| Tamanho de envio | 1080×1920 (9:16) | 1080×1920 (estimativa) | 2160×3840 recomendado; altura mínima de 640 px |
| Formato e peso | JPG ou PNG; pela API, JPEG de até 8 MB em sRGB | Não encontrado | JPG ou PNG; até 50 MB pelo computador |
| Como se escolhe | Quadro do vídeo ou imagem enviada | Quadro do vídeo; pela API, `video_cover_timestamp_ms` (sem valor, usa o **primeiro quadro**) | Imagem enviada **só** no YouTube Studio pelo computador, com conta verificada |
| Grade do perfil | Recorte central **3:4** — 1080×1440; perde 240 px em cima e 240 px embaixo (estimativa) | Recorte central de cerca de 3:4; há fontes que falam em 1:1 (estimativa) | Não encontrado |
| Outras superfícies | Feed: 4:5 central, 1080×1350 (estimativa). Aba Reels: 9:16 inteiro | Não encontrado | Não encontrado |
| **Zona conservadora para rosto e texto** | Quadrado central de 1080×1080 (y de 420 a 1500) | Quadrado central de 1080×1080 (y de 420 a 1500) | Terço central, até medir no canal |

Observações:

- **Reels.** A grade 3:4 foi anunciada por Adam Mosseri em janeiro de 2025; a Central de Ajuda não traz o número e ainda recomenda "420px by 654px (or 1:1.55 ratio)", texto antigo. A documentação da API diz que, ao compartilhar no feed, usa o quadrado central 1:1. Por isso a zona conservadora é o quadrado central, que sobrevive aos recortes 3:4, 4:5 e 1:1. A Central de Ajuda também diz "Right now, you can't edit your cover photo after you've uploaded it" — confira a capa antes de publicar.
- **TikTok.** Não há número oficial de capa nem de recorte. O único dado oficial é que, sem instrução, a API usa o primeiro quadro: ele nunca deve ser preto ou vazio.
- **Shorts.** A ajuda diz "Custom thumbnails for Shorts are currently only available to add in YouTube Studio on a computer" e recomenda 9:16. Segundo o mercado, a liberação começou em 25/07/2026 e pode não estar em todas as contas. Não há teste A/B.

Fontes: [Instagram — Reel size](https://help.instagram.com/1038071743007909), [Graph API — IG User Media](https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/media), [TikTok API — Direct Post](https://developers.tiktok.com/doc/content-posting-api-reference-direct-post), [YouTube — custom thumbnails](https://support.google.com/youtube/answer/72431?hl=en); mercado: [Hopper HQ](https://www.hopperhq.com/blog/instagram-reel-size/), [Kapwing](https://www.kapwing.com/resources/instagrams-new-grid-layout-size-and-dimensions-2025/), [Business Today](https://www.businesstoday.in/technology/news/story/instagram-head-announces-big-changes-3-minute-reels-and-new-look-for-profile-grid-461527-2025-01-21), [PostEverywhere](https://posteverywhere.ai/blog/tiktok-aspect-ratio), [Relevant Audience](https://www.relevantaudience.com/social-media-marketing/youtube-shorts-custom-thumbnails-no-ab-testing/).

---

## 7. O que nesta referência é estimativa

Nada desta lista é regra publicada por plataforma. Trate como ponto de partida e meça no canal do projeto quando a decisão depender do número.

1. **Zona segura no orgânico.** Os números adotados são oficiais, mas de **anúncio**. A interface orgânica real cobre menos, e não há número oficial para ela.
2. **Largura da coluna de botões do Instagram (21%).** Medida no diagrama oficial, que não traz a cota.
3. **União das zonas.** É uma conta sobre os três gabaritos; nenhuma plataforma a publica. No `plataformas.json` ela vem com `"oficial": false` e `"derivado_de": ["reels", "tiktok", "shorts"]`, para que a conferência final (`da conferencia`) e a video-publicacao não a apresentem como número de plataforma.
4. **Loudness de −14 LUFS e pico real de −1 dBTP**, nas quatro saídas. Nenhuma plataforma documenta o alvo.
5. **1080×1920 como resolução "recomendada"** de Reels e TikTok, e bitrate de 8 a 12 Mbps no TikTok.
6. **Zona do selo de duração** na thumbnail (25% × 22%) e demais sobreposições da miniatura: medição própria numa data, num navegador.
7. **Recorte das capas** na grade do perfil (3:4 no Instagram e no TikTok) e no feed (4:5).
8. **Trechos visíveis** de título, descrição e legenda antes do "mais".
9. **Legenda de 4.000 caracteres** no aplicativo do TikTok.
10. **Tamanho máximo de arquivo pelo aplicativo** em Reels e TikTok: não encontrado; os relatos divergem.
11. **Data de liberação da capa personalizada de Shorts** (25/07/2026).

Limites da própria pesquisa: as páginas oficiais foram lidas na versão em inglês, e a busca de fontes de mercado cobre só resultados dos Estados Unidos. Recursos liberados aos poucos (Reels de 20 minutos, TikTok de 60 minutos, capa de Shorts) podem não estar na conta do projeto. As medidas de interface não foram tiradas dentro dos aplicativos de celular.

---

## 8. O que revalidar a cada 3 meses

Para cada item: abrir a fonte, conferir o número, corrigir o JSON e este arquivo, e trocar a data de verificação nos dois.

| O que conferir | Valor de hoje | Onde |
|---|---|---|
| Duração máxima de Shorts | 180 s | [three-minute Shorts](https://support.google.com/youtube/answer/15424877?hl=en) |
| Duração de Reels e teto de recomendação | 20 min; recomendado até 3 min | [Record a reel](https://help.instagram.com/2720958398006062) |
| Duração no TikTok | 10 min gravado; 60 min enviado | [Camera tools](https://www.tiktok.com/support/faq_detail?id=7581821547946580492) |
| Zona segura da Meta | 14% / 35% / 6%; recorte de 40% | [Ads Guide — Reels](https://www.facebook.com/business/ads-guide/update/video/instagram-reels) e [safe zone](https://www.facebook.com/business/help/980593475366490) |
| Gabarito do TikTok | 240 / 660 / 120 / coluna de 300 a partir de y = 840 | [In-Feed Ads](https://ads.tiktok.com/help/article/tiktok-auction-in-feed-ads?lang=en) — baixar o .zip e medir de novo |
| Gabarito vertical do Google | livre de x = 48 a 888, y = 288 a 1248 | [About video ad specs](https://support.google.com/google-ads/answer/13547298?hl=en) — baixar o PNG e medir de novo |
| Hashtags do Instagram | 5 | [Use hashtags](https://help.instagram.com/351460621611097) |
| Thumbnail do YouTube | 3840×2160; 2 MB no celular, 50 MB no computador | [custom thumbnails](https://support.google.com/youtube/answer/72431?hl=en) |
| Teste A/B do YouTube | 3 variações; 14 dias; fora de Shorts | [A/B test](https://support.google.com/youtube/answer/13861714?hl=en) |
| Capa personalizada de Shorts | Só no Studio pelo computador | [custom thumbnails](https://support.google.com/youtube/answer/72431?hl=en) — e conferir na conta |
| Grade do perfil no Instagram | 3:4 | Olhar o perfil do projeto no aplicativo |
| Grade do perfil no TikTok | Cerca de 3:4, não documentado | Olhar o perfil do projeto no aplicativo |
| Selo de duração na thumbnail | Reserva de 25% × 22% | Medir de novo na busca do desktop, no celular e na lista lateral |
| Legenda do TikTok | 2.200 pela API; 4.000 no app (estimativa) | [Direct Post](https://developers.tiktok.com/doc/content-posting-api-reference-direct-post) e o próprio aplicativo |
| Tabela de bitrate, áudio e cor do YouTube | 8 / 12 Mbps em 1080p; AAC 48 kHz 384 kbps; BT.709 | [encoding settings](https://support.google.com/youtube/answer/1722171?hl=en) |
| Limites das APIs (se usar agendador) | Reels: 15 min, 300 MB. TikTok: 10 min, 4 GB | [Graph API](https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/media) e [Media Transfer Guide](https://developers.tiktok.com/doc/content-posting-api-media-transfer-guide) |
| Capítulos do YouTube | 00:00; 3 tempos; 10 s | [Video Chapters](https://support.google.com/youtube/answer/9884579?hl=en) |
| Loudness | −14 LUFS (estimativa) | Procurar documentação oficial; se aparecer, trocar a marcação |

Fora do ciclo, revalide na hora quando: um aplicativo redesenhar o player; a plataforma anunciar mudança de duração ou de limite; um vídeo publicado aparecer com texto coberto.

---

## 9. Como os números foram obtidos

- **Texto oficial:** páginas de ajuda e documentação abertas em 2026-10-05, com os trechos numéricos conferidos no texto da página (não em resumo de terceiros).
- **Gabaritos oficiais:** os PNGs do Google Ads e o `Feed.png` do TikTok foram lidos e medidos pixel a pixel (limites da área transparente). O diagrama da Meta foi conferido contra as cotas rotuladas (6%, 14%, 35%, 40%).
- **Medição própria:** selo de duração e cantos da miniatura medidos no DOM do YouTube (busca no desktop, site móvel com tela de 375 px e lista lateral da página do vídeo).
- **Mercado:** usado só onde não há número oficial, sempre marcado, e com faixas quando as fontes divergem.
- **Páginas que exigem navegador com JavaScript:** o suporte do TikTok (Camera tools — o endereço antigo `support.tiktok.com/en/using-tiktok/creating-videos/camera-tools` redireciona, com 302, para `www.tiktok.com/support/faq_detail?id=7581821547946580492`, conferido em 2026-10-06) e a Central de Ajuda do Instagram (`help.instagram.com/…`) devolvem só o cabeçalho a `curl`/leitores sem JS. Na revalidação de 2026-10-06, por esse motivo, os 10/60 min do TikTok **não** foram reconferidos na fonte oficial, e as 5 hashtags do Instagram e os 14 %/35 %/6 % da Meta foram confirmados só por fontes secundárias; os números de thumbnail do YouTube e dos Shorts de 3 min foram relidos nas páginas oficiais. Revalide os três primeiros abrindo a página num navegador.

---

## Fontes

### Oficiais

**YouTube e Google**
- [Recommended upload encoding settings](https://support.google.com/youtube/answer/1722171?hl=en)
- [Video resolution & aspect ratios](https://support.google.com/youtube/answer/6375112?hl=en)
- [Upload videos longer than 15 minutes](https://support.google.com/youtube/answer/71673?hl=en)
- [Supported YouTube file formats](https://support.google.com/youtube/troubleshooter/2888402?hl=en)
- [Upload High Dynamic Range (HDR) videos](https://support.google.com/youtube/answer/7126552?hl=en)
- [Understand three-minute YouTube Shorts](https://support.google.com/youtube/answer/15424877?hl=en)
- [Get started creating YouTube Shorts](https://support.google.com/youtube/answer/10059070?hl=en)
- [Add custom thumbnails on YouTube](https://support.google.com/youtube/answer/72431?hl=en)
- [A/B test titles & thumbnails](https://support.google.com/youtube/answer/13861714?hl=en)
- [Video Chapters](https://support.google.com/youtube/answer/9884579?hl=en)
- [Edit video settings](https://support.google.com/youtube/answer/57404?hl=en)
- [YouTube Data API — Videos](https://developers.google.com/youtube/v3/docs/videos)
- [Add tags to your YouTube videos](https://support.google.com/youtube/answer/146402?hl=en)
- [Find playlists & videos using hashtags](https://support.google.com/youtube/answer/6390658?hl=en)
- [Add end screens to videos](https://support.google.com/youtube/answer/6388789?hl=en)
- [Manage your channel branding](https://support.google.com/youtube/answer/10456525?hl=en)
- [Google Ads — About video ad specs](https://support.google.com/google-ads/answer/13547298?hl=en)
- [Gabarito vertical (PNG)](https://services.google.com/fh/files/misc/youtubesafezoneoverlay_vertical_final.png)
- [Gabarito horizontal (PNG)](https://services.google.com/fh/files/blogs/ytsafezoneoverlay-horizontal.png)

**Instagram e Meta**
- [Meta Ads Guide — Video ad specs on Instagram Reels](https://www.facebook.com/business/ads-guide/update/video/instagram-reels)
- [About text overlays and the safe zone for ads on Facebook and Instagram](https://www.facebook.com/business/help/980593475366490)
- [Reel size & aspect ratios on Instagram](https://help.instagram.com/1038071743007909)
- [Record a reel on Instagram](https://help.instagram.com/2720958398006062)
- [Use hashtags on Instagram](https://help.instagram.com/351460621611097)
- [Meta for Developers — IG User Media](https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/media)

**TikTok**
- [Suporte — Camera tools](https://www.tiktok.com/support/faq_detail?id=7581821547946580492)
- [TikTok Auction In-Feed Ads](https://ads.tiktok.com/help/article/tiktok-auction-in-feed-ads?lang=en)
- [Gabarito In-Feed, versão padrão (.zip)](https://lf-tt4b.tiktokcdn.com/obj/i18nblog/tt4b_cms/en-US/5jqet0ab9qci-10e7f5Vig4uhAscNP8XPB0.zip)
- [Content Posting API — Media Transfer Guide](https://developers.tiktok.com/doc/content-posting-api-media-transfer-guide)
- [Content Posting API — Direct Post](https://developers.tiktok.com/doc/content-posting-api-reference-direct-post)
- [Content Posting API — Photo Post](https://developers.tiktok.com/doc/content-posting-api-reference-photo-post)

**Norma técnica**
- [EBU R 95 — Safe areas for 16:9 television production](https://tech.ebu.ch/publications/r095)

### De mercado (estimativas)

- [AdKit — safe zones](https://adkit.so/tools/safe-zones/instagram) — medições dos gabaritos oficiais, atualizado em 2026-09-10
- [AdaptlyPost — social media safe zones 2026](https://adaptlypost.com/blog/social-media-safe-zones-2026-complete-guide)
- [PostEverywhere — TikTok aspect ratio](https://posteverywhere.ai/blog/tiktok-aspect-ratio) — 2026-05-15
- [ClipSpeed — YouTube Shorts size](https://www.clipspeed.ai/blog/youtube-shorts-size.html) — 2026-09-11
- [Poster.ly — YouTube Shorts safe zone checker](https://www.poster.ly/tools/youtube-shorts-safe-zone-checker)
- [Hopper HQ — Instagram Reel size](https://www.hopperhq.com/blog/instagram-reel-size/) — 2026-09-18
- [Reap — short-form video safe zones](https://reap.video/blog/short-form-video-safe-zones) — 2026-09-07
- [Kapwing — Instagram's new grid layout](https://www.kapwing.com/resources/instagrams-new-grid-layout-size-and-dimensions-2025/)
- [Business Today — nova grade do perfil](https://www.businesstoday.in/technology/news/story/instagram-head-announces-big-changes-3-minute-reels-and-new-look-for-profile-grid-461527-2025-01-21) — 2025-01-21
- [BetaNews — limite de hashtags do Instagram](https://betanews.com/2025/12/19/instagram-puts-a-limit-on-hashtag-usage/) — 2025-12-19
- [Fora Soft — LUFS targets per platform 2026](https://www.forasoft.com/learn/audio-for-video/articles-audio/lufs-targets-per-platform-2026) — 2026-06-05
- [Production Advice — Stats for nerds](https://productionadvice.co.uk/stats-for-nerds/)
- [HowManyWords — YouTube character limits](https://howmanywords.app/blog/youtube-character-limits) — 2026-04-29
- [ClipSpeed — Instagram Reels captions](https://www.clipspeed.ai/blog/instagram-reels-captions.html)
- [RecurPost — TikTok character limits and hashtags](https://recurpost.com/tiktok-scheduler/tiktok-character-limits-and-hashtags/)
- [Relevant Audience — YouTube Shorts custom thumbnails](https://www.relevantaudience.com/social-media-marketing/youtube-shorts-custom-thumbnails-no-ab-testing/)
- Medição própria no DOM do YouTube em 2026-10-05
