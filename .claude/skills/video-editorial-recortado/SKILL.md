---
name: video-editorial-recortado
description: Cria vídeos curtos (reels/shorts 9:16) no estilo "editorial recortado" — fotos reais em preto e branco recortadas como uma silhueta só, com borda azul-ardósia cortada a tesoura, sobre papel quase branco com retícula de bolinhas cinza; título serifado (Lora) com sublinhado de pincel azul, subtítulo que sobe palavra a palavra e etiquetas coral que se montam (um traço vira faixa, palavras pretas soltas pulam uma a uma para dentro e ficam brancas) apontando as partes da imagem. Plano único que vai se preenchendo de anotações. Feito com páginas HTML animadas quadro a quadro (GSAP + Playwright + ffmpeg), a biblioteca do estilo (lib/editorial.js), fotos do Wikimedia Commons recortadas com crédito e som sintetizado. Use sempre que o usuário pedir vídeo "editorial", "estilo revista", "colagem editorial", "recorte P&B com borda colorida", "anotações/etiquetas vermelhas apontando partes", "infográfico anotado", "skyline recortado", reels educativo que explica as partes de um prédio, lugar, objeto ou máquina, ou mandar uma referência nesse visual pedindo algo "nesse estilo" — mesmo que não diga "editorial recortado".
---

# Vídeo em editorial recortado

Três marcas, juntas, fazem o estilo:

1. **Recorte P&B com borda azul cortada a tesoura** sobre papel quase branco, com manchas de retícula cinza atrás. A foto real dá o assunto; a borda de papel (segmentos retos, espessura irregular) diz "colagem feita à mão".
2. **Título serifado com sublinhado de pincel**, e um subtítulo que sobe palavra a palavra. É a voz de revista: calma, legível, impressa.
3. **Etiquetas coral que se montam**: um traço vira faixa que cresce; as palavras aparecem soltas em preto, meia linha acima e abaixo, e pulam uma a uma para dentro da faixa, ficando brancas. É o único movimento "vivo" do vídeo, e por isso prende o olho.

Quase nada mais se mexe: um plano só, câmera quase parada (empurrão de 2–4%), e o quadro vai se enchendo de anotações até respirar no fim.

Veja `assets/exemplo.mp4` (6,8 s, "Brasília de Niemeyer — a cidade desenhada do zero"). O código está em `assets/projeto/videos/exemplo-brasilia/index.html` e é o ponto de partida de todo vídeo novo.

## Preparar o projeto (uma vez por pasta)

```bash
bash <caminho-da-skill>/scripts/setup.sh <pasta-do-projeto>
cd <pasta-do-projeto> && N=$(bash tools/node.sh)
```

Requisitos: Node ≥ 20 (o `node.sh` acha um; o PATH pode ter um velho), ffmpeg e python3. O recorte automático de fotos usa o Vision do macOS 14+ (`tools/recortar.py`); fora do Mac, recorte em outro programa e salve PNG com alfa.

## Fluxo

1. **Tema e texto.** Um título curto (≤ 22 caracteres cabe em 86 px), um subtítulo de 3–6 palavras e 4–6 etiquetas que **nomeiam partes visíveis** da imagem (1 longa, as outras de 1–3 palavras). Não invente números ou fatos; prefira nomes e citações conhecidas.
2. **Fotos** (ver `references/receitas.md`, "Fotos"):
   - `audio/.venv/bin/python tools/commons.py buscar "termo em inglês" --n 16 --folha previews/c.jpg` → olhe a folha e baixe com `baixar <n> videos/<nn>/img/x.jpg`.
   - `tools/recortar.py` (Vision) → `x_cut.png`. Se o Vision perder uma parte, recorte-a à parte com `--caixa`.
   - `tools/editorial.py recorte x_cut.png x_ed.png --largura <px na tela> --px 15` → P&B + borda azul.
   - `tools/editorial.py papel img/papel.jpg` → fundo.
3. **Composição 9:16** (ver `references/estilo.md`): um aglomerado único que vaza pela base, o mais alto no terço central, peças da frente escondendo as bases cortadas das de trás, retícula nos vãos, etiquetas no "céu" ao lado de cada parte.
4. **Montar:** `cp -R videos/exemplo-brasilia videos/<nn-nome>` e troque fotos, posições e textos mantendo a tabela `T` (`references/movimento.md`).
5. **Preview:** `$N render.mjs <nn> --at=0.5,2,3.5,6` (ou `--preview=12`) → `previews/<nn-nome>*` e corrija.
6. **Som e render:** `$N render.mjs <nn> --at=1` (grava `cues.json`), `audio/.venv/bin/python audio/synth.py <nn>`, `$N render.mjs <nn>` → `out/<nn-nome>.mp4` (ver `references/audio.md`).
7. **Conferir:** `ffprobe` (1080×1920, duração, uma faixa de áudio), folha a 8 qps do mp4, texto legível no celular, crédito das fotos no rodapé quando a licença pedir.

## Regras do motor

- Tudo é função do tempo (`onTick(t => …)` ou `TL`); nada de animação CSS, `setTimeout`, `requestAnimationFrame` ou `Math.random()` (use `K.rng`).
- `ED.titulo` e `ED.etiqueta` **medem texto**: chame-os dentro de `window.SETUP` (as fontes já carregaram). Fora dele as larguras saem erradas.
- Fontes: só as de `lib/fonts.css` (Lora para tudo que é editorial; Inter Tight para o crédito). Outra fonte = baixe o woff2 OFL para `lib/fonts/` e declare o `@font-face`.
- Imagens no tamanho de uso: gere o recorte já com `--largura` igual à largura na página.

## Armadilhas do estilo

- **Base reta cortada flutuando.** Toda peça recortada tem um corte reto embaixo. Esconda-o atrás de uma peça da frente ou na borda inferior do quadro; nos vãos que sobrarem, ponha uma retícula.
- **Foto branca sumindo no papel.** O `editorial.py` limita os brancos a `#e1`; a borda azul faz o resto. Não clareie a foto além disso.
- **Etiqueta saindo da tela.** Para encostar na margem direita use `alinhar:'dir'` (o `x` vira a borda direita). Até ~22 caracteres em `fs:47`.
- **Etiquetas demais ao mesmo tempo.** Comece cada uma 0,3–0,6 s depois da anterior: elas se sobrepõem, mas a vista acompanha.
- **Cena vazia.** O plano único só funciona se cada fase trouxer algo novo: título → título sobe → subtítulo → etiquetas → respiro. Respiro final de 25–35% da duração, nunca mais.

## Arquivos

- `assets/projeto/lib/editorial.js` — biblioteca do estilo, global `ED` (API em `references/receitas.md`).
- `scripts/editorial.py` — recorte P&B + borda a tesoura, papel com retícula de pontinhos.
- `references/estilo.md` (paleta, tipografia, materiais, composição) · `movimento.md` (tempos e eases medidos) · `receitas.md` (API e passo a passo) · `audio.md` (trilha e efeitos).
- `scripts/setup.sh` · `node.sh` · `commons.py` · `recortar.py` + `cutout.swift` · `analisar.py` (para ler uma referência nova e comparar lado a lado).
