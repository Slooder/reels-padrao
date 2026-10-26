---
name: video-texto-grifado
description: Cria vídeos curtos (reels/shorts 9:16) no estilo "texto grifado" — tipografia editorial em que um parágrafo serifado (Lora Bold, cinza-escuro sobre papel quase branco) é escrito palavra a palavra, cada palavra brotando um pouco abaixo da linha e subindo, enquanto a câmera persegue o texto e depois empurra devagar; um marca-texto amarelo que sangra da borda esquerda da tela grifa a primeira frase e, no fim, um bloco vermelho cresce sobre a frase-chave e deixa o texto branco. Abre com uma colagem editorial (recorte de foto P&B com contorno amarelo grosso, retícula de bolinhas cinza, título com sublinhado de pincel) cujo grifo vira, num chicote horizontal, o grifo do parágrafo. Feito com páginas HTML animadas quadro a quadro (GSAP + Playwright + ffmpeg), a biblioteca do estilo (lib/grifado.js), fotos do Wikimedia Commons recortadas e som sintetizado. Use sempre que o usuário pedir vídeo de "texto grifado", "marca-texto", "texto com highlight", "grifo amarelo", "frase destacada em vermelho", "tipografia editorial", "texto de revista animado", "citação/parágrafo aparecendo palavra por palavra", "poema/verso/cordel animado", reels de frase, de citação ou de explicação curta em texto, ou mandar uma referência nesse visual pedindo algo "nesse estilo" — mesmo que não diga "texto grifado".
---

# Vídeo em texto grifado

Três marcas, juntas, fazem o estilo:

1. **Parágrafo serifado escrito palavra a palavra.** Lora Bold #363636 sobre papel #fcfcfc, centralizado. Cada palavra surge já opaca ~0,8 em abaixo da linha e sobe em 0,25 s; a câmera persegue o centro do que já foi escrito, com atraso, e depois empurra devagar (≈1 %/s). É a voz de quem lê junto.
2. **Marca-texto que sangra da borda da tela.** A barra amarela #f9ce80 não começa na palavra: começa *fora da tela, à esquerda*, e cresce devagar por trás da primeira frase. No fim, um **bloco vermelho #dd687a** cresce sobre a frase-chave e o texto coberto fica branco — o único "golpe" do vídeo.
3. **Abertura de colagem editorial que vira o texto.** Recorte de foto P&B com contorno amarelo liso, retícula de bolinhas cinza, título com sublinhado de pincel e um rótulo em escada com grifo. O grifo do rótulo está na *mesma altura* do 1º verso: no chicote horizontal ele é arrastado, gruda na borda e se estica sobre o parágrafo.

Quase nada mais se mexe. Tudo anima a **12 qps** (quadros repetidos aos pares), como na referência.

Veja `assets/exemplo.mp4` (8 s, "Literatura de cordel — o folheto que conta histórias na feira"). O código está em `assets/projeto/videos/exemplo-cordel/index.html` e é o ponto de partida de todo vídeo novo.

## Preparar o projeto (uma vez por pasta)

```bash
bash <caminho-da-skill>/scripts/setup.sh <pasta-do-projeto>
cd <pasta-do-projeto> && N=$(bash tools/node.sh)
```

Requisitos: Node ≥ 20 (o `node.sh` acha um; o PATH pode ter um velho), ffmpeg e python3. O recorte automático de fotos usa o Vision do macOS 14+ (`tools/grifado.py recorte` chama `tools/cutout`); fora do Mac, desenhe a máscara com `--poli` ou recorte em outro programa.

## Fluxo

1. **Texto primeiro.** Um título curto (≤ 22 caracteres), um rótulo de 2 linhas curtas (a 2ª é a grifada) e um parágrafo de **4–7 linhas de 18–27 caracteres** (uma linha por item; em 9:16 cada linha é um verso ou um pedaço de frase). Marque qual linha leva o amarelo (a 1ª) e qual trecho leva o vermelho (o fim, a frase-chave). Não invente números nem fatos.
2. **Foto da abertura** (ver `references/receitas.md`, "Fotos"): `tools/commons.py buscar` → `baixar` → `tools/grifado.py recorte` (P&B + contorno amarelo, `--sangra` nas bordas que vazam da tela) → `tools/grifado.py papel`.
3. **Montar:** `cp -R videos/exemplo-cordel videos/<nn-nome>` e troque textos, foto e posições mantendo a tabela `T` (`references/movimento.md`). Regra de ouro: **a linha grifada do rótulo e a 1ª linha do parágrafo têm a mesma faixa vertical** (mesmo `fs`, mesma entrelinha, mesmo `y`).
4. **Preview:** `$N render.mjs <nn> --at=0.1,0.6,1.1,1.3,1.9,3.6,5.7,7.5` → `previews/<nn-nome>/` e corrija.
5. **Som e render:** `$N render.mjs <nn> --at=1` (grava `cues.json`), `audio/.venv/bin/python audio/synth.py <nn>`, `$N render.mjs <nn>` → `out/<nn-nome>.mp4` (ver `references/audio.md`).
6. **Conferir:** `ffprobe` (1080×1920, duração, uma faixa de áudio), folha a 8 qps (`ffmpeg -i out/x.mp4 -vf "fps=8,scale=216:384,tile=8x8" -frames:v 1 folha.jpg`), texto legível no celular, crédito da foto no rodapé quando a licença pedir.

## Regras do motor

- Tudo é função do tempo: o vídeo inteiro roda num `onTick(t => …)` com `t = GR.q(t)`; nada de animação CSS, `setTimeout`, `requestAnimationFrame` ou `Math.random()` (use `K.rng`/`K.noise`).
- `GR.titulo`, `GR.rotulo`, `GR.paragrafo`, `GR.marca` e `GR.destaque` **medem texto**: chame-os dentro de `window.SETUP` (as fontes já carregaram).
- Um plano só: abertura e parágrafo moram no mesmo `GR.mundo` (a abertura em x 0–1080, o parágrafo à direita, `X_T ≈ 1900`); quem anda é a câmera (`GR.aplicar`).
- Fonte: só Lora (já em `lib/fonts.css`). Outra fonte = baixe o woff2 OFL para `lib/fonts/` e declare o `@font-face`.

## Armadilhas do estilo

- **Grifo que não "passa" do rótulo para o texto.** Se o rótulo e a 1ª linha estiverem em alturas diferentes, a barra pula. Calcule: `cy` do parágrafo = centro da linha grifada do rótulo + (nLinhas−1)/2 × entrelinha.
- **Barra atravessando a abertura inteira.** Acontece quando o chicote atrasa e o verso começa a ser grifado com a câmera ainda na abertura. O grifo do verso (`b0`) começa depois que o chicote acaba.
- **Câmera que não "lê".** Com linhas curtas a câmera centraliza cada linha e fica parada; `GR.seguir(P, {cursor:.25})` puxa um pouco para a última palavra.
- **Bloco vermelho com texto desalinhado.** A cópia branca clona a linha do parágrafo; não mude `fs`/entrelinha da linha depois do SETUP.
- **Recorte com borda reta flutuando.** A foto tem um corte reto embaixo (e às vezes nos lados): use `--sangra lrb` e posicione a peça vazando 10–15 px da tela.
- **Trilha engolindo o lápis.** O tique por palavra é baixo de propósito; mantenha a trilha `feira` em `gain` −6 e a zabumba leve (ver `references/audio.md`).

## Arquivos

- `assets/projeto/lib/grifado.js` — biblioteca do estilo, global `GR` (API em `references/receitas.md`).
- `scripts/grifado.py` — recorte P&B com contorno de cor liso (Vision + polígonos) e papel-reboco.
- `references/estilo.md` (paleta, tipografia, materiais, composição 9:16) · `movimento.md` (tempos e eases medidos) · `receitas.md` (API e passo a passo) · `audio.md` (trilha e efeitos).
- `scripts/setup.sh` · `node.sh` · `commons.py` · `recortar.py` + `cutout.swift` · `analisar.py` (para ler uma referência nova e comparar lado a lado).
