---
name: video-colagem-parallax
description: Cria vídeos curtos de colagem animada com parallax 2.5D (estilo Vox / documentário / scrapbook). O vídeo tem fotos reais recortadas com borda de adesivo, gravuras antigas, mapa preso com fita, papel rasgado, etiqueta vermelha e anotação à mão com seta e círculo desenhados, além de halftone e grão. Uma câmera lenta empurra cada camada numa profundidade diferente. Busca imagens de licença livre no Wikimedia Commons e anota os créditos, recorta os bichos e objetos com o Vision do macOS e sintetiza o som (passarinho, papel, marcador). Renderiza um mp4 9:16 (ou 16:9, 1:1) quadro a quadro com GSAP, Playwright e ffmpeg. Use sempre que o usuário pedir vídeo de colagem, colagem animada, parallax, efeito 2.5D, "estilo Vox", fotos recortadas animadas, scrapbook, motion de documentário ou reels/shorts educativos com fotos ("raças de cachorro", "animais do Brasil", "5 fatos sobre..."). Use também quando ele mandar uma referência nesse visual pedindo algo parecido, mesmo sem falar "colagem" nem "parallax".
---

# Vídeo de colagem + parallax

O visual vem de dois movimentos que contrastam:

- **O que chega é stop-motion.** As peças batem na mesa em 4 quadros (`steps(4)`), o título e a letra à mão se escrevem aos saltos, e a etiqueta treme a 12 quadros por segundo.
- **O que flutua é liso.** A câmera faz um empurrão lento e contínuo, e cada camada anda numa velocidade proporcional à profundidade dela. O fundo quase não se mexe e as folhas da frente passam rápido e desfocadas.

Os materiais são de papel de verdade: foto com contorno branco de adesivo, papel rasgado, fita crepe, gravura do séc. XIX, halftone e grão. A tinta é vermelha e branca, feita à mão.

Veja `assets/exemplo.mp4` para calibrar o olhar. O código dele está em `assets/projeto/videos/exemplo-mico/index.html` e é o ponto de partida de todo vídeo novo.

## Preparar o projeto (uma vez por pasta)

```bash
bash <caminho-da-skill>/scripts/setup.sh <pasta-do-projeto>
```

O script copia o motor de render, instala gsap e playwright, cria o venv Python com numpy, scipy e pillow, compila o recorte do Vision (`tools/cutout`) e copia `tools/commons.py` e `tools/recortar.py`.

- **Requisitos:** macOS 14+ (Vision e VideoToolbox), Node 18+, ffmpeg, python3 e swiftc (`xcode-select --install`). Fora do Mac o render funciona com libx264, mas o recorte tem que ser feito de outro jeito (rembg ou à mão).
- **Onde rodar:** todos os comandos abaixo rodam **da raiz do projeto**.

## Fluxo

### 1. Pauta

Um vídeo de 5 s é **uma prancha** com 1 assunto, 1 título, 1 fato-gancho (a anotação à mão) e 1 etiqueta curta (o "selo"). Liste as peças antes de buscar imagens:

| Peça | O que é | Exemplo do mico |
|---|---|---|
| fundo | foto ampla do ambiente | Mata Atlântica |
| cartão | mapa, documento ou foto antiga presa com fita | mapa da área original |
| ilustração | gravura ou desenho antigo, recortado | gravura séc. XIX |
| herói | a foto principal, recortada, maior peça da tela | o mico |
| textos | número da série, título, etiqueta, anotação com seta ou círculo | "só no Brasil" |

Para temas com vários itens ("5 raças de cachorro"), faça uma prancha por item. Veja "Vídeos mais longos" em `references/estilo.md`.

### 2. Imagens com crédito

```bash
audio/.venv/bin/python tools/commons.py buscar "Golden retriever" --n 16
```

Isso lista os resultados e gera `previews/commons.jpg`. **Abra a folha de contato e escolha olhando.** Depois baixe:

```bash
audio/.venv/bin/python tools/commons.py baixar 3 videos/<nome>/img/heroi.jpg
```

O download grava a peça em `img/creditos.json`.

O que dá certo:

- **Herói:** o bicho inteiro no quadro, fundo simples e contrastado, de corpo inteiro ou 3/4, sem nada na frente. Uma foto boa vale mais que um recorte consertado.
- **Gravuras de domínio público:** busque em inglês ou latim, por exemplo `"<nome científico> engraving"`, `"<raça> illustration 19th century"`, `Brehms Tierleben`, `Meyers Konversations-Lexikon`, `Iconographia Zoologica`.
- **Mapas:** NASA e mapas antigos costumam ser de domínio público.
- **Licenças:** CC BY e CC BY-SA **exigem crédito no vídeo**. O script recusa NC e ND. Monte o rodapé com `tools/commons.py creditos videos/<nome>/img`.

### 3. Recortes

```bash
audio/.venv/bin/python tools/recortar.py videos/<nome>/img/heroi.jpg videos/<nome>/img/heroi_cut.png
```

O script corta pelo objeto, endurece a borda (para o contorno de adesivo não fazer halo) e salva uma prova sobre fundo verde em `previews/recorte-*.jpg`. **Abra a prova.**

- O Vision perde partes finas (rabo, bigode, antena, pata fina).
- Com dois bichos na foto ele recorta os dois. Use `--caixa x0,y0,x1,y1` (frações de 0 a 1) para recortar a foto antes.

Mapas e cartões não se recortam: corte o retângulo que interessa com PIL e emoldure com papel no HTML.

### 4. Montar a prancha

```bash
cp -R videos/exemplo-mico videos/<nn-nome>
```

Troque as imagens, os textos, as posições e as rotações. Antes de posicionar, leia `references/estilo.md`: ele traz a tabela de profundidade das camadas, a câmera, os tempos, os materiais em CSS e a composição 9:16. Mantenha a estrutura `.ly` + `DEPTH` + `cam`, porque é ela que faz o parallax.

### 5. Preview e iteração

```bash
node render.mjs <nome> --preview=12          # folha com 12 quadros → previews/<nome>.jpg
node render.mjs <nome> --at=0.4,1.2,2.6,4.8  # instantes específicos → previews/<nome>/NN.jpg
```

Abra a folha e corrija até cada quadro ser uma composição boa:

- nada importante cortado pela borda;
- as peças se sobrepõem um pouco (é colagem, não grade);
- o título fica legível sobre o papel;
- o herói é a maior peça;
- o último segundo fica parado e completo, para quem pausar.

Para inspecionar o estado da página num instante: `node dbg.mjs <nome> 2.5 "getComputedStyle(K.$('#tg')).opacity"`.

### 6. Som e render final

```bash
audio/.venv/bin/python audio/synth.py <nome>   # trilha + efeitos a partir de videos/<nome>/cues.json
node render.mjs <nome>                          # out/<nome>.mp4 (junta audio/<nome>.wav sozinho)
```

O `cues.json` é escrito a cada preview ou render, então rode um preview **antes** do synth. Os tipos de cue, os estilos de trilha e a narração opcional estão em `references/audio.md`.

Para conferir o mp4 pronto, extraia 2 ou 3 quadros com ffmpeg e olhe antes de entregar.

## Regras do motor (o render pula para qualquer instante t)

- **Tudo é função do tempo.** Animação vai na timeline `TL` (GSAP pausada) ou em `onTick(t => ...)`. Não use transição ou animação CSS, `setTimeout`, `requestAnimationFrame` nem `Math.random()`; use `K.rng(seed)`. Se não for assim, o quadro renderizado não bate com o instante.
- **Elemento que começa escondido** entra com `TL.fromTo(..., {opacity:0}, {opacity:1, immediateRender:true})`. Um `from()` depois de `gsap.set(autoAlpha:0)` anima de 0 para 0 e o elemento nunca aparece. O `slap()` do exemplo já faz certo.
- **DrawSVG** só funciona em `path`, `line`, `circle` e similares. Não funciona em `<text>` nem em traço tracejado. Texto se revela com `clipPath` (o wipe em `steps()` do exemplo, ou `K.wipe`).
- **Fontes locais** estão em `lib/fonts.css`: Playfair Display, Libre Caslon Text, Caveat, JetBrains Mono, Inter Tight, Archivo e Special Elite. Para outra fonte, baixe o woff2 em `lib/fonts/` e declare o `@font-face`. O render espera `document.fonts`.
- **Imagem pesada deixa o render lento.** Recortes podem ter até ~2× a largura em que aparecem e o fundo até ~1700 px.
- **Cue de som** vai junto da animação: `cue('paper', t)`. O tempo do som é o tempo do movimento.

## Formatos

O padrão é `VIDEO={w:1080,h:1920,fps:60,dur:5,...}`. Para 16:9 ou 1:1, mude `w` e `h` e **recomponha**: reposicione as peças em vez de escalar. A colagem depende de onde cada peça sangra a borda.

## Arquivos

- `scripts/setup.sh`: cria ou completa um projeto.
- `scripts/commons.py`: busca, baixa e anota os créditos do Wikimedia Commons.
- `scripts/recortar.py` e `scripts/cutout.swift`: recorte com Vision, corte pela caixa e prova.
- `assets/projeto/`: o motor (`render.mjs`, `dbg.mjs`, `lib/`, `audio/synth.py`, `audio/narrate.py`) e o exemplo `videos/exemplo-mico/`.
- `assets/exemplo.mp4`: o resultado de referência.
- `references/estilo.md`: a gramática visual. **Leia antes de montar.**
- `references/audio.md`: cues, trilha e narração.
