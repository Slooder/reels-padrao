# Direção de arte — Testemunhos

> Desabafo sóbrio e cinematográfico: o JP falando é o centro; pouco motion, texto limpo, papel e máquina de escrever nos momentos de peso.

Revisão 1 · NÃO APROVADA (rascunho) · sha256 `9ad198ef744bb3a6…` · base: editorial-claro

_Gerado por `da.py compilar`. Não edite este arquivo: mude `da/da.json` e recompile._

## Conceito

Palavras-chave: editorial, sóbrio, papel, tipográfico, arejado, revista.

**Faça**

- Compor como página: título forte, chapéu em caixa alta espaçada, texto em coluna estreita
- Vermelho só para o que é notícia: o número principal, a palavra-chave, o fio que guia o olho
- Fios finos e legenda de foto como em revista; crédito sempre visível
- Entradas por fade e cortes secos: o ritmo vem da edição, não do efeito
- Fotos com cor natural, levemente aquecidas, em moldura fina

**Não faça**

- Fundo escuro, neon ou qualquer brilho
- Texto sobre foto sem caixa de papel por trás
- Animação chamativa: nada gira, quica ou pisca
- Mais de uma família de título por tela
- Encher a página: se não cabe com folga, vira duas telas

## Cor

| token | hex | CSS | contraste c/ fundo |
|---|---|---|---|
| fundo | `#0E0D0B` | `var(--da-cor-fundo)` | — |
| superficie | `#1C1A17` | `var(--da-cor-superficie)` | 1,1:1 |
| texto | `#FFFFFF` | `var(--da-cor-texto)` | 19,4:1 |
| texto_suave | `#D9D4CA` | `var(--da-cor-texto-suave)` | 13,2:1 |
| primaria | `#F2D24B` | `var(--da-cor-primaria)` | 13:1 |
| secundaria | `#231F1A` | `var(--da-cor-secundaria)` | 1,2:1 |
| destaque | `#F2D24B` | `var(--da-cor-destaque)` | 13:1 |
| positivo | `#2D6A4F` | `var(--da-cor-positivo)` | 3:1 |
| negativo | `#7F1D1D` | `var(--da-cor-negativo)` | 1,9:1 |
| alerta | `#B45309` | `var(--da-cor-alerta)` | 3,9:1 |
| papel | `#E6DAC0` | `var(--da-cor-papel)` | 14:1 |
| tinta | `#231F1A` | `var(--da-cor-tinta)` | 1,2:1 |
| bandeira_sombra | `#000000` | `var(--da-cor-bandeira-sombra)` | 1,1:1 |
| mesa | `#3B2A1D` | `var(--da-cor-mesa)` | 1,4:1 |
| marcador | `#C8102E` | `var(--da-cor-marcador)` | 3,3:1 |

Dados (ordem fixa, `dado-1`…): `#F2D24B` `#FFFFFF` `#E07A5F` `#81B29A` `#F2CC8F` `#A8DADC`.
Neutros (`neutro-1`…): `#000000` `#FFFFFF`.
Gradientes: `papel` = linear-gradient(180deg, #0E0D0B 0%, #1C1A17 100%).

## Tipografia

| papel | família | peso | largura | caixa | tracking | entrelinha | arquivo |
|---|---|---|---|---|---|---|---|
| titulo | Helvetica | 700 | normal | normal | -0,022 em | 1,02 | `fontes/Helvetica-Bold.ttf` |
| subtitulo | Helvetica | 700 | normal | alta | 0,14 em | 1,3 | `fontes/Helvetica-Bold.ttf` |
| corpo | Helvetica | 400 | normal | normal | 0,002 em | 1,5 | `fontes/Helvetica.ttf` |
| dados | Helvetica | 400 | normal | normal | 0 em | 1,3 | `fontes/Helvetica.ttf` |
| legenda | Helvetica | 700 | normal | normal | -0,045 em | 1 | `fontes/Helvetica-Bold.ttf` |
| versiculo | Newsreader | 700 | normal | normal | -0,01 em | 1,18 | `fontes/Newsreader-Variable.ttf` |

Escala (fração do lado menor): display 0,115 (124 px em 1080); h1 0,076 (82 px em 1080); h2 0,05 (54 px em 1080); h3 0,036 (39 px em 1080); corpo 0,029 (31 px em 1080); nota 0,022 (24 px em 1080).

## Layout

Grade de 12 colunas, margem 0,08 (86 px em 1080), calha 0,016 (17 px em 1080); raio 0 (0 px em 1080); traço 0,0019 (2 px em 1080); sombra nenhuma; densidade arejada.

## Movimento

Curvas (cubic-bezier): entrada [0,25, 0,1, 0,25, 1]; saida [0,4, 0, 1, 1]; enfase [0,3, 0, 0,1, 1]; suave [0,45, 0, 0,55, 1]; linear [0, 0, 1, 1].
Durações: micro 0,14 s; curta 0,36 s; media 0,64 s; longa 1,1 s; escalonamento 0,09 s.
Entrada padrão: fade · saída padrão: fade · transição padrão: corte (permitidas: corte, fade).

- Calma: o texto surge, fica o tempo de ser lido e sai sem chamar atenção
- Deslocamentos curtos; a página nunca treme
- O corte seco é a transição; o fade é exceção para mudança de assunto
- Hierarquia entra de cima para baixo: chapéu, título, texto

## Tratamento de imagem (footage e b-roll)

Grade: exposição 0 EV · contraste 1,04 · saturação 0,92 · gama 1 · temperatura 8 · matiz 0° · LUT nenhuma · curva nenhuma.
Duotone: não · grão: intensidade 3 temporal · vinheta: não · nitidez 0,1 · desfoque 0 · velocidade 1×.
Moldura: borda (cor texto, espessura 0,0019 (2 px em 1080), margem 0,07 (76 px em 1080), rótulo sim) · recorte ancorado em: rosto.
Cadeia ffmpeg (horizontal): `eq=contrast=1.04:saturation=0.92,format=gbrp,colortemperature=temperature=3500:mix=0.08:pl=1,format=yuv420p,unsharp=lx=5:ly=5:la=0.1:cx=5:cy=5:ca=0,noise=c0s=3:c0f=t+u`

## Legenda

Estilo bloco, papel `legenda`, tamanho 0,06 (65 px em 1080), caixa normal; cor texto (`#FFFFFF`), destaque texto (`#FFFFFF`); contorno não; sombra não; caixa de fundo não.
Posição (y do centro): vertical 0,7; horizontal 0,86 · largura máx. 0,76 · até 2 linha(s) e 6 palavra(s) por cue · animação fade.
Faixa da legenda reservada (GC, crédito, título e gráficos desviam dela) em: vertical, quadrado. Em horizontal as peças **não** desviam (GC, crédito e gráficos usam a zona segura inteira e podem ocupar a faixa da legenda): se esse formato levar legenda queimada, inclua-o em `legenda.reservar_em` antes de produzir.

## Gráficos, thumbnail, som e marca

- GC: estilo linha, inferior esquerda; nome em `titulo`, cargo em `subtitulo`.
- Tarja: sublinhado, texto texto sobre primaria, papel `titulo`.
- Ícones: traco (0,0024 (3 px em 1080)). Gráficos de dados: eixo texto, grade superficie, rótulos em `dados`.
- Crédito de fonte: papel `dados`, 0,023 (25 px em 1080), inferior esquerda.
- Thumbnail: até 5 palavras em `titulo` (0,16 do lado menor); fundo fundo; foto com saturação 1 e contraste 1,06, pessoa recortada; zona proibida: inferior direita.
- Som: Acústico e contido: piano, cordas discretas e som de papel; nada compete com a voz. Loudness: longo -14 LUFS / -1 dBTP; curto -14 LUFS / -1 dBTP. SFX: entrada = papel, enfase = tick, texto = tick. Música: piano e cordas leves, contemplativo (70–95 bpm).
- Marca: logo nenhum; assinatura nenhuma; posição superior direita; marca d'água não.

## Formatos e margens seguras

- horizontal: 1920×1080 a 30000/1001 fps
- vertical: 1080×1920 a 30000/1001 fps
- quadrado: 1080×1080 a 30000/1001 fps
- thumbnail: 1280×720
- margens seguras horizontal [topo, direita, base, esquerda]: padrao [0,05, 0,05, 0,05, 0,05]
- margens seguras vertical [topo, direita, base, esquerda]: instagram [0,14, 0,21, 0,35, 0,06]; tiktok [0,125, 0,2778, 0,3438, 0,1111]; shorts [0,15, 0,1778, 0,35, 0,0444]; uniao [0,15, 0,2778, 0,35, 0,1111]
- margens seguras quadrado [topo, direita, base, esquerda]: padrao [0,05, 0,05, 0,05, 0,05]

## Como as peças usam a DA

- HTML/CSS: `<link rel="stylesheet" href="da/build/da.css">` e `var(--da-cor-primaria)`, `var(--da-fonte-titulo)`, `var(--da-escala-h1)`, classes `.da-titulo`, `.da-corpo`… Cor com transparência tem uma forma só: `rgba(var(--da-cor-fundo-rgb), 0.86)`. Em cena do motor: `ctx.cor(…)`, `ctx.alfa(…, a)`; fora dele, `window.DA` (de `da/build/da.js`).
- Python: `sys.path.insert(0, os.path.expanduser(""$CRIABR_SKILLS"/video-direcao-de-arte/kit")); import da; d = da.carregar()` → `d.cor("primaria")`, `d.fonte("titulo")`, `d.px(...)`, `d.grade("horizontal")`.
- Proibido cor ou fonte literal em peças (HTML, CSS, JS, JSON, SVG e Python): `"$CRIABR_SKILLS"/video-direcao-de-arte/kit/bin/da lint <pasta>` reprova. Toda saída leva carimbo: `"$CRIABR_SKILLS"/video-direcao-de-arte/kit/bin/da conferir-carimbo`.
- Antes de publicar: `"$CRIABR_SKILLS"/video-direcao-de-arte/kit/bin/da conferencia` — a conferência final (DA aprovada, lint, carimbos, loudness e limites de plataforma) grava `qa/relatorio.json` e `qa/relatorio.md`; nada vai para `publicacao/` com esse relatório reprovado.
