# Gramática visual da colagem + parallax

Conteúdo:

1. Anatomia da prancha
2. Profundidade e câmera
3. Linha do tempo de 5 s
4. Vocabulário de movimento
5. Materiais (CSS e SVG prontos)
6. Composição 9:16
7. Paleta e tipografia
8. Vídeos mais longos (várias pranchas)
9. Checklist antes do render final

O código citado está em `assets/projeto/videos/exemplo-mico/index.html`.

---

## 1. Anatomia da prancha

Cada camada é um `div.ly` que ocupa o palco inteiro (`position:absolute; inset:0; transform-origin:50% 52%`). As peças ficam dentro das camadas com `position:absolute`. A ordem no HTML é a ordem de empilhamento:

| camada | conteúdo | profundidade `DEPTH` |
|---|---|---|
| `L0` | foto do ambiente, escurecida e levemente desfocada | `.06` |
| `Lp` | faixa de papel rasgado no topo, onde fica o título | `.3` |
| `L1` | cartão: mapa ou documento preso com fita | `.35` |
| `L2` | gravura ou ilustração antiga recortada, com legenda | `.6` |
| `L3` | **herói**: foto recortada com contorno de adesivo | `.85` |
| `L4` | folhas ou objetos de primeiro plano, bem desfocados | `1.7` |
| `L5` | textos: número, título, etiqueta, anotação, seta | `.4` |
| — | `#halftone`, `#paperTex`, `#cred` (créditos) e `K.grain`, por cima de tudo, **sem parallax** | — |

Os textos ficam em profundidade média (`.4`) de propósito: andam com o papel e nunca escorregam para fora da área segura. Já os créditos ficam **fora** das camadas, porque o zoom da câmera empurraria a linha do rodapé para fora do quadro no fim do vídeo.

## 2. Profundidade e câmera

```js
const DEPTH = { L0: .06, Lp: .3, L1: .35, L2: .6, L3: .85, L4: 1.7, L5: .4 };
const cam = { z: 0, x: 0, y: 0, r: 0 };
onTick(t => {
  for (const [id, d] of Object.entries(DEPTH)) K.$('#' + id).style.transform =
    `translate(${cam.x * d}px,${cam.y * d}px) scale(${1 + cam.z * d}) rotate(${cam.r * d}deg)`;
});
// no SETUP: um único empurrão lento pela duração inteira
TL.fromTo(cam, { z: -.02, x: 50, y: 40, r: -.8 }, { z: .17, x: -60, y: -40, r: .6, duration: VIDEO.dur, ease: 'sine.inOut', immediateRender: true }, 0);
```

- **Por que funciona:** o olho lê profundidade pela diferença de velocidade. O fundo quase não se move, o herói anda bastante e o primeiro plano passa rápido e desfocado. Sem essa diferença o resultado parece um slide com zoom.
- **Amplitude:** com zoom total de ~0,19 e deslocamento de ~110 px por 5 s, o movimento é perceptível sem ser enjoativo. Até 0,3 de zoom ainda funciona. Acima disso as peças começam a sair do quadro.
- **Folga nas bordas:** a câmera anda, então as peças que encostam na borda precisam passar dela em pelo menos 80 px. É por isso que o fundo do exemplo tem `left:-230px; width:1540px`.
- **Vida própria:** sobre a câmera, o herói e a gravura flutuam com seno lento (`translate` de 5–6 px, períodos diferentes). As folhas balançam ±2,5°. Use `style.translate` e `style.rotate`, que são propriedades separadas e não brigam com o `transform` da câmera nem com o do GSAP.

## 3. Linha do tempo de 5 s (exemplo)

| t (s) | evento | som |
|---|---|---|
| 0.00 | papel rasgado desce do topo (`y:-560→0`, `.45s expo.out`) | `swoosh` |
| 0.20 | slap do número da série | `paper` |
| 0.30 | título se escreve em wipe `steps(7)` | `paper` |
| 0.55 | slap do mapa | `paper` |
| 0.85 | slap da gravura | `paper` |
| 1.00 | créditos aparecem (fade .5s) | — |
| 1.15 | slap do herói | `paper` + `hit_soft` |
| 1.55 | slap da etiqueta vermelha | `paper` |
| 2.00 | círculo vermelho desenhado no mapa (drawSVG .55s) | `marker` |
| 2.50 | "RJ" aparece | — |
| 2.60 | anotação à mão em wipe `steps(10)` (.9s) | `marker` |
| 3.40 | seta desenhada (drawSVG .5s) | `marker` |
| 3.9–5.0 | prancha completa, só a câmera e as flutuações | trilha fecha (`m:stop` 4.7) |

Regras de ritmo:

- **Espaçamento:** as entradas vêm a cada ~0,3 s na montagem (até ~1,6 s). As anotações vêm depois, a cada ~0,6–0,8 s.
- **Segurar o fim:** pelo menos 1 s parado e completo, para quem pausar e para o loop do reels.
- **Leitura:** o herói entra até ~1,2 s, e o fato-gancho (anotação) entra antes da metade do vídeo.

## 4. Vocabulário de movimento

```js
// SLAP: a peça bate na mesa em 4 quadros
const slap = (sel, at) => { TL.fromTo(sel, { scale: 1.3, opacity: 0 }, { scale: 1, opacity: 1, duration: .24, ease: 'steps(4)', immediateRender: true }, at); cue('paper', at + .04, { gain: -1 }); };

// ESCRITA AOS SALTOS: revela da esquerda para a direita em degraus
TL.fromTo('#title', { clipPath: 'inset(0 100% 0 0)' }, { clipPath: 'inset(0 0% 0 0)', duration: .5, ease: 'steps(7)', immediateRender: true }, .3);

// TRAÇO DE MARCADOR: path com stroke-linecap round
TL.fromTo('#circ', { drawSVG: '0%' }, { drawSVG: '100%', duration: .55, ease: 'power1.inOut', immediateRender: true }, 2.0);

// TREMOR STOP-MOTION (12 qps) em peça pequena, dentro do onTick
const q = Math.floor(t * 12) / 12;
K.$('#tg').style.translate = `${Math.round(Math.sin(q * 13) * 2)}px ${Math.round(Math.cos(q * 11) * 2)}px`;
```

- **Rotação inicial:** as peças nascem com rotação fixa (−6° a +5°) no `style` e nunca ficam retas. O slap só mexe em `scale` e `opacity`, então a rotação se mantém.
- **Variações de entrada que combinam:**
  - **Slide de fita:** a peça entra deslizando 60 px com `steps(5)`.
  - **Flip de cartão:** `rotateY` de 90° para 0 com `steps(4)`.
  - **Carimbo:** escala de 1.6 para 1 com `steps(3)`, mais `hit_soft`.

  Evite easing elástico ou bounce liso: quebra a sensação de papel.
- **Círculo, seta e sublinhado:** sempre em `path` aberto. A seta é feita de três subpaths (`M... C...` para o corpo e `M... L...` para cada lado da ponta), com `drop-shadow` para descolar do fundo.

## 5. Materiais (CSS e SVG prontos)

```css
#stage{background:#2b2a20;overflow:hidden}
.ly{position:absolute;inset:0;transform-origin:50% 52%;will-change:transform}
/* contorno branco de adesivo + sombra projetada: aplique no <img> do recorte (PNG com alfa) */
.stk{filter:drop-shadow(6px 0 0 #fbf6ea) drop-shadow(-6px 0 0 #fbf6ea) drop-shadow(0 6px 0 #fbf6ea) drop-shadow(0 -6px 0 #fbf6ea) drop-shadow(14px 22px 16px rgba(20,12,4,.45))}
/* etiqueta vermelha */
.tag{position:absolute;background:#e3321f;color:#fff6ea;font:400 60px/1 'Libre Caslon Text';padding:16px 28px 22px;box-shadow:7px 9px 0 rgba(30,15,5,.3);white-space:nowrap}
/* anotação à mão sobre a foto */
.hand{position:absolute;font:700 66px/1.02 'Caveat';color:#fffaf0;text-shadow:0 3px 14px rgba(0,0,0,.65);white-space:nowrap}
/* legenda de peça */
.cap{position:absolute;font:italic 400 28px 'Libre Caslon Text';color:#3c2c1c;white-space:nowrap}
/* fita crepe */
.tape{position:absolute;width:150px;height:46px;background:rgba(236,226,196,.82);box-shadow:0 2px 6px rgba(0,0,0,.15)}
/* halftone e textura de papel por cima de tudo */
#halftone{position:absolute;inset:0;pointer-events:none;background:radial-gradient(circle,rgba(0,0,0,.28) 1.3px,transparent 1.6px) 0 0/7px 7px;mix-blend-mode:multiply;opacity:.35}
#paperTex{position:absolute;inset:0;pointer-events:none;mix-blend-mode:multiply;opacity:.5}
```

- **Cartão ou polaroide:** um `div` com `background:#fbf6ea; padding:14px 14px 56px; transform:rotate(-6deg); box-shadow:10px 18px 26px rgba(0,0,0,.4)`, com a imagem dentro e duas `.tape` nos cantos (rotações de −32° e +28°).
- **Papel rasgado:** um path com `feTurbulence` + `feDisplacementMap` para a borda irregular e um `feDropShadow` num `<g>` em volta, para a sombra não ser deslocada junto. O código completo está no exemplo, na função que monta `#Lp`. Para rasgar na vertical (lateral), use o mesmo filtro num path vertical. Mude o `seed` para variar a borda.
- **Fundo:** `filter: saturate(.85) sepia(.18) brightness(.78) contrast(1.05) blur(1.2px)`. Escurecer e desfocar um pouco o ambiente é o que faz o papel e os recortes saltarem.
- **Primeiro plano:** folhas em SVG geradas pela função `leaf()` do exemplo, com `blur(6–9px)`, entrando pelos cantos. Para temas sem natureza, troque por um objeto temático desfocado (pena, osso, coleira, folha de papel, lápis).
- **Grão:** `K.grain(K.$('#stage'), { opacity: .2, w: 360 })` vai por último.

## 6. Composição 9:16 (1080×1920)

- **Topo (0–480):** papel claro rasgado. O número da série fica em `y≈150` (mono vermelho, com espaçamento) e o título em `y≈196`, em 2 linhas de Playfair 128 px. Quebre o título à mão (`<br>`) para formar um bloco.
- **Meio (560–1100):** o cartão de um lado, levemente girado. A anotação à mão fica do outro lado, sobre o fundo, com a seta apontando para o detalhe do cartão.
- **Base (1000–1800):** o herói é a maior peça (~60% da largura). Ele sangra a borda direita ou esquerda e fica um pouco sobre a gravura, que é menor e está atrás. A etiqueta fica por cima do canto inferior do herói.
- **Área segura de reels:** deixe o texto essencial fora dos ~260 px de baixo e dos ~140 px da direita na metade inferior, onde ficam os ícones do app. Os créditos podem ficar embaixo porque são pequenos e opcionais de ler.
- **Sobreposição sempre:** cada peça cobre um pedaço de outra. Peças soltas e alinhadas em grade matam o efeito.
- **Diagonal de leitura:** título (topo, à esquerda), anotação (meio, à direita), herói (base, à direita) e etiqueta formam um Z.

## 7. Paleta e tipografia

| papel | cor |
|---|---|
| papel claro (rasgado, cartão) | `#ece3cf` / `#fbf6ea` |
| tinta escura (título, legenda) | `#24170e` / `#3c2c1c` |
| vermelho (número, etiqueta, círculo) | `#e3321f` |
| branco quente (anotação, seta, contorno) | `#fffaf0` / `#fbf6ea` |
| fundo do palco | `#2b2a20` |

| uso | fonte |
|---|---|
| título | Playfair Display 700, `letter-spacing:-.035em`, `line-height:.9` |
| série | JetBrains Mono 700 26 px, `letter-spacing:.2em`, vermelho |
| etiqueta | Libre Caslon Text 60 px |
| legenda | Libre Caslon Text itálico 28 px |
| anotação | Caveat 700 66 px |
| créditos | Inter Tight 500 15 px |

Para variar entre vídeos de uma série, troque **uma** cor de destaque (o vermelho vira azul-tinta, verde-musgo ou mostarda) e mantenha todo o resto. A série fica reconhecível.

## 8. Vídeos mais longos (várias pranchas)

Para listas ("5 raças de cachorro"), use 1 prancha por item, com 3,5 a 5 s cada, 1 abertura e 1 fechamento. Esqueleto que funciona com o mesmo motor (adapte):

```html
<div class="board" id="b0"><div class="ly" data-d=".06">…</div><div class="ly" data-d=".85">…</div>…</div>
<div class="board" id="b1">…</div>
```

```js
const BOARDS = [{ id: 'b0', t0: 0, t1: 4.5 }, { id: 'b1', t0: 4.5, t1: 9 } /* … */];
onTick(t => BOARDS.forEach(b => {
  const el = K.$('#' + b.id), on = t >= b.t0 - .4 && t < b.t1 + .4;
  el.style.visibility = on ? 'visible' : 'hidden'; if (!on) return;
  const u = K.ease('sine.inOut', (t - b.t0) / (b.t1 - b.t0));          // câmera própria por prancha
  const c = { z: K.lerp(-.02, .17, u), x: K.lerp(50, -60, u), y: K.lerp(40, -40, u), r: K.lerp(-.8, .6, u) };
  el.querySelectorAll('.ly').forEach(l => { const d = +l.dataset.d;
    l.style.transform = `translate(${c.x * d}px,${c.y * d}px) scale(${1 + c.z * d}) rotate(${c.r * d}deg)`; });
}));
```

Transições entre pranchas (escolha uma e mantenha na série):

- **Chicote lateral:**
  - a prancha que sai faz `x:0→-1080` e a que entra faz `x:1080→0`, em `.35s`, ease `whip`;
  - `filter: blur(0→14px→0)` no meio do caminho;
  - cue `whoosh_in`.
- **Papel rasgado cobre:**
  - uma folha de papel rasgado (o mesmo filtro do topo) atravessa a tela inteira em `steps(5)`;
  - a próxima prancha já está montada atrás dela;
  - cue `paper` + `swoosh`.
- **Mergulho no herói:**
  - nos últimos 0,4 s o `cam.z` da prancha vai a ~1,5, com o herói como centro (ajuste o `transform-origin`);
  - a próxima prancha entra com o slap do fundo.

Em cada prancha, comprima as entradas (tudo montado em ~1,6 s) e segure ≥1,2 s para a leitura. Se houver narração, a linha do tempo segue a fala (veja `audio.md`).

## 9. Checklist antes do render final

- [ ] A folha de preview (12 quadros) não mostra nenhum quadro "vazio" ou desequilibrado depois de 1,2 s.
- [ ] Nenhuma borda de imagem aparece quando a câmera está nos extremos (`--at=0,<dur − 0.02>`).
- [ ] Os recortes não têm halo nem pedaço do fundo original (confira a prova verde).
- [ ] O texto é legível em tela de celular: título ≥ 100 px e anotação ≥ 56 px.
- [ ] Os créditos de todas as imagens CC BY e CC BY-SA estão na tela.
- [ ] Cada slap, traço e escrita tem o cue de som correspondente.
