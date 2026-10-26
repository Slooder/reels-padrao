# Receitas: como fazer cada peça

## Sumário
1. Fotos: buscar, recortar, tratar
2. Página: esqueleto
3. API de `lib/editorial.js` (`ED`)
4. Trocar o tema do exemplo, passo a passo
5. Problemas comuns

## 1. Fotos: buscar, recortar, tratar

```bash
P=audio/.venv/bin/python; I=videos/02-tema/img; mkdir -p $I
$P tools/commons.py buscar "Sydney Opera House" --n 16 --folha previews/c_opera.jpg   # olhe a folha
$P tools/commons.py baixar 4 $I/opera.jpg --largura 2400                            # grava $I/creditos.json
$P tools/recortar.py $I/opera.jpg $I/opera_cut.png --max 2400 [--caixa x0,y0,x1,y1]  # Vision → PNG com alfa
$P tools/editorial.py recorte $I/opera_cut.png $I/opera_ed.png --largura 1300 --px 15 --seed 4
$P tools/editorial.py papel $I/papel.jpg
```

- **Escolha da foto:** céu limpo (azul liso ou escuro) recorta melhor. Prefira domínio público/CC0; CC BY e BY-SA exigem crédito no vídeo (`ED.credito`). Nada de NC/ND, logos como assunto ou pessoas identificáveis em primeiro plano.
- **Vision perdeu uma parte** (aconteceu com a cúpula do Senado): recorte só aquela região com `--caixa` e monte as duas peças lado a lado na página.
- **`--largura`** = largura da peça na página. A ferramenta redimensiona para cima ou para baixo antes de fazer a borda, então a espessura (`--px`) sai certa na tela.
- **Tratamento P&B por foto:** `--contraste` (1,3–1,8) e `--gama` (0,8 clareia sombras, 1,25 escurece meios-tons). Fachada de vidro cinza → `--contraste 1.75 --gama 1.18`; foto escura com estrutura branca → `--contraste 1.3 --gama .82`.
- **Borda:** `--px 15` (espessura média), `--var .5` (variação), `--eps .45` (quanto a tesoura corta caminho), `--seed` muda o desenho. `--cor 5b7ba3` é o azul do estilo.
- O `.json` ao lado do PNG diz onde a foto ficou dentro dele (margem da borda), caso precise alinhar um ponto da foto.

## 2. Página: esqueleto

```html
<script>VIDEO={w:1080,h:1920,fps:30,dur:6.8,bpm:92,music:{style:'ambient_major',key:'F',gain:0}}</script>
<script>LIBS=['editorial.js']</script>
<script src="../../lib/boot.js"></script>
<style>#stage{background:#f5f5f3;overflow:hidden} #cidade{position:absolute;inset:0}</style>
<div id="stage">
 <div id="fundo" class="fill"></div>                       <!-- papel + retículas -->
 <div id="cidade"></div>                                   <!-- recortes (trás → frente) -->
 <div id="textos" class="fill" style="z-index:5"></div>    <!-- título e subtítulo -->
 <div id="rotulos" class="fill" style="z-index:6"></div>   <!-- etiquetas e crédito -->
</div>
<script>
const T = { tit: 0, traco: .26, sobe: .95, sub: 1.30, L: [2.62, 3.24, 3.58, 3.90, 4.22], cred: 4.75 };
// … peças fora do SETUP; textos que medem largura dentro dele
window.SETUP = () => { /* ED.titulo, ED.sublinhado, ED.sobe, ED.etiqueta */ };
</script>
```

## 3. API de `lib/editorial.js` (`ED`)

| função | o que faz | quando chamar |
|---|---|---|
| `ED.papel(pai, 'img/papel.jpg')` | fundo de papel (114,8% do quadro, folga p/ câmera) | qualquer hora |
| `ED.reticula(pai, {x,y,w,h, t0, d:.32, degraus:7, dir:'l'\|'r', passo:26, raio:7})` | mancha de bolinhas cinza que aparece em degraus | qualquer hora |
| `ED.peca(pai, src, {x,y,w,z})` | recorte posicionado pela largura (`transform-origin` embaixo) | qualquer hora |
| `ED.empurra(el, {para:1.03, dy:0, ease:'sine.inOut', t0, t1})` | empurrão lento de câmera numa camada | qualquer hora |
| `ED.titulo(pai, txt, {y, fs:86, maxw, peso})` | linha serifada centralizada que cabe em `maxw`; devolve `{el, palavras, larg, x0, fs}` | **SETUP** |
| `ED.sublinhado(tit.el, {x, y, w, h, t0, d:.55})` | pincel azul atrás das letras, desenhado da esquerda p/ a direita | **SETUP** (depois do título) |
| `ED.sobe(palavras, t0, {passo, d:.38, dy:.6, som, gain})` | palavras aparecem ½ linha abaixo e sobem; devolve o fim | **SETUP** |
| `ED.etiqueta(pai, {texto, x, y, t0, fs:47, seed, alinhar:'esq'\|'dir', passoA:.066, passoS:.1, som:true})` | a etiqueta coral que se monta; devolve `{el, w, h, fim}` | **SETUP** |
| `ED.credito(pai, texto, {t0})` | linha de crédito no rodapé (15 px, sombra) | qualquer hora |
| `ED.som(tipo, t, opções)` | `cue` que desloca uns quadros um efeito igual a outro a < 60 ms | qualquer hora |

Exemplos curtos:

```js
// título que entra, sublinha e sobe para abrir espaço
const tit = ED.titulo($('#textos'), 'Ópera de Sydney', { y: 168, fs: 86 });
ED.sublinhado(tit.el, { x: tit.x0 - tit.fs * .2, y: tit.fs * .95, w: tit.larg + tit.fs * .55, h: tit.fs * .29, t0: T.traco });
ED.sobe(tit.palavras, T.tit, { passo: .12, d: .4, som: 'paper', gain: -1 });
const ez = gsap.parseEase('power3.inOut');
onTick(t => (tit.el.style.transform = `translateY(${96 * (1 - ez(K.seg(t, T.sobe, T.sobe + .62)))}px)`));

// subtítulo palavra a palavra
const sub = ED.titulo($('#textos'), 'Conchas sobre o porto', { y: 312, fs: 60 });
ED.sobe(sub.palavras, T.sub, { passo: .21, som: 'pop', gain: -2 });

// etiqueta encostada na margem direita
ED.etiqueta($('#rotulos'), { texto: 'Concha maior', x: 1036, y: 1170, t0: 3.5, seed: 2, alinhar: 'dir' });
```

- `seed` muda a ordem em que as palavras aparecem e para que lado se espalham. Se uma palavra solta cair em cima de outra etiqueta, troque o `seed`.
- As cores vêm das variáveis CSS (`--ed-coral`, `--ed-azul`…). Para outra paleta, redefina em `:root` na página — mas a do estilo é a da tabela em `estilo.md`.

## 4. Trocar o tema do exemplo, passo a passo

1. `cp -R videos/exemplo-brasilia videos/02-tema` e apague as imagens.
2. Faça os recortes (seção 1) já com a largura de uso.
3. Componha as peças olhando `--at=6` (estado final) até o aglomerado ficar único e vazar pela base. Retículas nos vãos.
4. Escreva título, subtítulo e etiquetas; posicione cada etiqueta perto da sua parte (`--at=6` de novo).
5. Ajuste `T` se o texto for maior: cada palavra extra do subtítulo soma 0,21 s; cada etiqueta, ~0,3 s.
6. Atualize o crédito (`ED.credito`) com o `creditos.json` (`tools/commons.py creditos videos/02-tema/img`).
7. Som e render (`audio.md`).

## 5. Problemas comuns

- **Etiqueta com largura errada / palavras amontoadas:** chamou `ED.etiqueta` fora do `SETUP` (fonte ainda não carregada).
- **Base reta de uma peça aparecendo no meio da tela:** mova a peça para trás de outra ou para a borda de baixo; se não der, retícula embaixo dela.
- **Recorte com "dentes" ou buracos na borda:** o alfa do Vision tinha falhas; rode `recortar.py` com `--caixa` mais justa ou aumente `--px`.
- **Prédio branco sumindo:** confira se usou o `.png` tratado (`*_ed.png`) e não o `*_cut.png`.
- **Duas teclas soando como uma:** use `ED.som` em vez de `cue` para efeitos repetidos (as etiquetas já usam).
