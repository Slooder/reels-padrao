# Receitas: como fazer cada peça

## Sumário
1. Fotos: buscar, recortar, tratar
2. Página: esqueleto
3. API de `lib/grifado.js` (`GR`)
4. Trocar o tema do exemplo, passo a passo
5. Variações
6. Problemas comuns

## 1. Fotos: buscar, recortar, tratar

```bash
P=audio/.venv/bin/python; I=videos/02-tema/img; mkdir -p $I
$P -I tools/commons.py buscar "cordel literature" --n 16 --folha previews/c_tema.jpg      # olhe a folha
$P -I tools/commons.py baixar "File:Nome exato.jpg" $I/foto.jpg --largura 2400           # grava $I/creditos.json
$P -I tools/grifado.py recorte $I/foto.jpg $I/foto_gr.png --largura 1340 --sangra lrb \
      [--caixa x0,y0,x1,y1] [--poli "x,y x,y x,y …"] [--px 15] [--nitidez 1.6] [--contraste 1.35]
$P -I tools/grifado.py papel $I/papel.jpg                                               # 2900×2400, cobre o mundo
```

- **Escolha da foto:** um assunto só, de silhueta clara (prédio, objeto, pessoa de meio corpo), fundo que contraste. Prefira domínio público/CC0; CC BY e BY-SA exigem crédito (`GR.credito`). Nada de NC/ND, logos como assunto, nem crianças.
- **`--caixa`** (px da foto original) enquadra antes de escalar; **`--largura`** = largura da peça na página (o contorno `--px` sai certo na tela).
- **`--sangra`**: bordas por onde o assunto vaza da tela (`b` embaixo, `l`/`r` nos lados). Ali não nasce contorno.
- **O Vision perdeu uma parte** (papel branco na mão, cabo, placa): some um polígono com `--poli` em px da foto **original** (pode repetir). No exemplo, o folheto branco foi desenhado assim: `--poli "192,432 962,414 1080,1670 330,1665 275,1230"`. Para achar os cantos, desenhe uma grade sobre a foto (PIL) e leia.
- **Traço fino sumindo no P&B** (desenho, letras impressas): suba `--nitidez` (1,2–2,0).
- O `.json` ao lado do PNG diz a margem do contorno (`margem_topo`) e a escala, caso precise alinhar um ponto.

## 2. Página: esqueleto

```html
<script>VIDEO={w:1080,h:1920,fps:24,dur:8,bpm:104,music:{style:'feira',key:'G',gain:-6}}</script>
<script>LIBS=['grifado.js']</script>
<script src="../../lib/boot.js"></script>
<style>#stage{background:#fcfcfc;overflow:hidden}</style></head><body>
<div id="stage"></div>
<script>
const T = { rotulo:[.25,.60], chicote:[.55,1.30], escreve:.85, verso1:[1.30,2.60], zoom:[1.0,8.0,1,1.07], vermelho:5.30, credito:6.40 };
const X_T = 1900, LINHAS = ['…', '…', '…'];
const stage = K.$('#stage');
GR.mundo(stage, { w: 3000, h: 2400 });
GR.papel('img/papel.jpg', { x: -150, y: -240, w: 2900, h: 2400 });
window.SETUP = () => {
  GR.pontos({ x, y, w, h, seed });  GR.recorte('img/foto_gr.png', { x: -50, y: 925, w: 1340 });
  GR.titulo('Título', { cx: 540, y: 420, fs: 72 });
  const rot = GR.rotulo(['Linha 1', 'linha 2'], { x: 560, y: 617, fs: 66, recuo: 80 });
  const P = GR.paragrafo(LINHAS, { cx: X_T, cy: 970, fs: 66 });
  const fim = GR.escrever(P, T.escreve);
  const seguir = GR.seguir(P, { tau: .34, cursor: .25 });
  const amarelo = GR.marca(rot.faixa(1, { antes: 1.5 }), P.faixa(0), { a0: T.rotulo[0], a1: T.rotulo[1], b0: T.verso1[0], b1: T.verso1[1] });
  const vermelho = GR.destaque(P, P.faixa(LINHAS.length - 1, 1), { t0: T.vermelho });
  const cred = GR.credito(stage, 'Foto: Autor / Wikimedia Commons (licença)');
  const cam = t => ({ x: K.lerp(540, seguir(t), GR.chicote(K.seg(t, ...T.chicote))), y: 960, z: K.lerp(1, 1.07, K.seg(t, 1, 8)) });
  onTick(t0 => { const t = GR.q(t0), c = cam(t); GR.aplicar(c); GR.palavras(P, t); amarelo.tick(t, c); vermelho.tick(t);
    cred.style.opacity = K.seg(t, T.credito, T.credito + .3); });
  // cues de trilha e efeitos: ver audio.md
};
</script>
```

## 3. API de `lib/grifado.js` (`GR`)

| função | o que faz | quando |
|---|---|---|
| `GR.cor` | paleta (`tinta`, `amarelo`, `contorno`, `vermelho`, `ponto`, `papel`) | — |
| `GR.qps` / `GR.q(t)` | quantiza o tempo em 12 qps (0 = liso) | onTick |
| `GR.mundo(stage, {w,h})` | cria o "papel" onde tudo mora; a câmera anda por ele | antes de tudo |
| `GR.aplicar({x,y,z})` | posiciona a câmera (ponto do mundo no centro da tela + zoom) | onTick |
| `GR.telaEsq(cam)` / `telaDir` | borda da tela em coordenadas do mundo | onTick |
| `GR.papel(src, {x,y,w,h})` | fundo de papel no mundo | qualquer hora |
| `GR.pontos({x,y,w,h, passo:30, raio:.225, borda:1.6, seed})` | mancha de retícula (canvas) com borda roída | qualquer hora |
| `GR.recorte(src, {x,y,w})` | PNG do `grifado.py recorte` | qualquer hora |
| `GR.titulo(txt, {cx,y,fs:74, sublinhado:{…}\|false})` | título centralizado + `GR.pincel` embaixo; devolve `{el, sub, w}` | **SETUP** |
| `GR.pincel({x0,x1,y,esp,arco:4,gancho:1,seed,cor})` | sublinhado de pincel avulso (SVG) | qualquer hora |
| `GR.rotulo(linhas, {x,y,fs:66,recuo,passo})` | rótulo em escada; `.faixa(i, {antes,depois,alt})` dá o retângulo da linha i | **SETUP** |
| `GR.paragrafo(linhas, {cx,cy,fs:66,entre:1.36})` | parágrafo centralizado, uma `<span>` por palavra; `P.faixa(linha, de, ate, {antes,depois,alt})` | **SETUP** |
| `GR.escrever(P, t0, {pps:10.5, sobe:.8, dur:.25, ease, som, somTipo:'lapis', somGain})` | agenda as palavras (+ cue de lápis em cada); devolve o fim | **SETUP** |
| `GR.palavras(P, t)` | mostra/sobe as palavras no instante t | onTick |
| `GR.seguir(P, {tau:.32, cursor:.25})` | devolve `x(t)` da câmera que persegue o texto (pré-calculada a 120 Hz) | **SETUP** |
| `GR.chicote(u, {corte:.82, p:2.6})` | ease do chicote (aceleração longa, freada curta) | onTick |
| `GR.marca(a, b, {a0,a1,b0,b1, toco:.2, ease:'none', cor, som})` | o marca-texto rótulo → borda → verso; `.tick(t, cam)` | **SETUP** + onTick |
| `GR.destaque(P, f, {t0, dur:.95, ease:'power2.inOut', cor, texto})` | bloco vermelho + texto branco; `.tick(t)` | **SETUP** + onTick |
| `GR.credito(stage, txt, {fs:24, base:46, cor})` | linha de crédito presa à tela (opacidade 0 até você subir) | qualquer hora |

## 4. Trocar o tema do exemplo, passo a passo

1. `cp -R videos/exemplo-cordel videos/02-tema` e apague `cues.json`.
2. Escreva o parágrafo em linhas de 18–27 caracteres. Meça a mais longa: com Lora Bold 66 px, ~26 caracteres ≈ 860 px. Se passar de ~900 px, baixe `fs` do parágrafo **e** do rótulo juntos (eles têm de casar).
3. Gere a foto (seção 1), troque `GR.recorte`, mova as duas manchas de `GR.pontos` para os vãos do novo assunto.
4. Troque título e rótulo. A 2ª linha do rótulo precisa ficar com a faixa (`rot.faixa(1)`) na mesma altura que `P.faixa(0)`: com `fs 66`, `y` do rótulo 617 ↔ `cy` do parágrafo 970 para 6 linhas. Para N linhas: `cy = 745 + (N−1)/2 × 90`.
5. Escolha o trecho vermelho: `P.faixa(últimaLinha, palavraInicial)`.
6. `$N render.mjs 02 --at=0.1,0.6,1.1,1.3,1.9,3.6,5.7,7.5` e confira: o grifo atravessa sem pular? a 1ª palavra começa logo depois do toco? o vermelho cobre só a frase-chave?
7. Crédito: `GR.credito` com autor e licença do `creditos.json`.

## 5. Variações

- **Sem foto** (citação pura): pule a abertura e comece com a câmera já no parágrafo (`x: seguir(t)`). Para o grifo nascer como toco na borda, passe um rótulo fictício fora do mundo: `GR.marca({x0:-1e4, x1:-1e4}, P.faixa(0), {a0:.2, a1:.2, b0:.6, b1:1.8})`.
- **Mais de um grifo amarelo:** chame `GR.marca` de novo para outra linha. Com `a = {x0:-1e4, x1:-1e4}` a barra sangra da borda; com `a = b = P.faixa(i)` e `a0=a1=b0` ela começa na 1ª palavra (sem toco, use `toco:0`).
- **Grifo vermelho no meio do texto:** `GR.destaque(P, P.faixa(2, 1, 3), …)` — a cópia branca é sempre da linha inteira, recortada pelo bloco.
- **Paleta:** mude `GR.cor.amarelo`/`vermelho` antes de criar as peças (ex.: verde-limão e azul); mantenha o papel claro e a tinta escura.

## 6. Problemas comuns

- **Palavras na posição errada / grifo deslocado:** alguma medição rodou fora do `SETUP` (fonte ainda não carregada).
- **Barra amarela some no meio do chicote:** `toco` 0 ou `b0` cedo demais; use `toco .2` e `b0` ≥ fim do chicote.
- **Primeiro quadro com texto já escrito:** `T.escreve` antes do chicote começar; a 1ª palavra deve nascer com a câmera já em movimento (0,3 s depois do início do chicote).
- **Recorte com halo escuro no contorno:** foto de fundo escuro; aumente `--px` ou ajuste `--poli` para não incluir fundo.
