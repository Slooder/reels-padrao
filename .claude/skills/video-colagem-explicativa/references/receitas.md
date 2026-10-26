# Receitas — a biblioteca `CE` (lib/colagem.js) e as ferramentas

Carregue na página: `<script>LIBS=['colagem.js']</script>` antes do `boot.js`. Tudo acontece dentro de `window.SETUP = async () => { … }` (pode usar `await fetch` para ler `globo.json`).

## Esqueleto

```html
<script>VIDEO={w:1080,h:1920,fps:30,dur:7.6,bpm:104,music:{style:'explainer',key:'D',gain:-5}}</script>
<script>LIBS=['colagem.js']</script>
<script src="../../lib/boot.js"></script>
<style>#stage{background:#dbdbdb;overflow:hidden} .cena{position:absolute;inset:0;z-index:2;display:none} .ce-peca{visibility:hidden}</style>
<div id="stage"><div class="cena" id="s1"></div><div class="cena" id="s2"></div></div>
<script>
window.SETUP = async () => {
  CE.defs();                                   // filtros (grão de papel)
  CE.papel(K.$('#stage'), 'img/papel.jpg');    // papel que ferve
  CE.cenas({ '#s1': [0, 1.5], '#s2': [1.5, 99] });
  cue('m:main', 0); cue('m:stop', VIDEO.dur - .22);
  // … peças e movimentos …
};
</script>
```

## Peças

| função | o que é | opções principais |
|---|---|---|
| `CE.peca(pai, html, {x,y,w,h,z,origem,css})` | div absoluto (nasce escondido) com o conteúdo | `origem` = transform-origin (padrão base-centro) |
| `CE.foto(pai, src, {x,y,w,z,origem,sombra})` | foto recortada (PNG com alfa) com sombra curta | `sombra:false` para faixas e fotos em mancha |
| `CE.planeta(dados, {r, oceano, terra, destaque})` | planeta chapado com aro branco | `dados` = JSON de `tools/globo.py` |
| `CE.lata({w, cor:[corpo,faixa], amassada, contorno, id})` | latinha com contorno branco | cores prontas em `CE.LATAS` |
| `CE.lacre({w})` | lacre de lata (peça miúda para o anel) | |
| `CE.lixeira({w, cor, simbolo})` | lixeira com símbolo de reciclagem | `cor: CE.COR.amarelo` (metal) |
| `CE.pinheiro({w,h,cor,seed,niveis,riscos})` | pinheiro dentado, com riscos brancos | `riscos:false` nos verdes |
| `CE.sol({r, raios})` | sol com raios tracejados (`.ce-raios` gira) | |
| `CE.mancha({w,h,cor,seed,tremor,forma})` | mancha de tinta de borda irregular | `forma:'semi'` = semicírculo |
| `CE.grade({w,h,passo,cor,esp})` | grade de linhas (`.ce-gl`) | anime com `CE.traca` |
| `CE.anel({r, tracos, esp, cor})` | círculo tracejado | |
| `CE.legenda(pai, {t1, t2, y})` | letreiro Poppins verde + linha escura | devolve `{el, t1, t2}` |
| `CE.reciclagem(cor)` | símbolo (3 setas) em caixa 100×100, para pôr em SVG | |

Toda função vetorial devolve uma string `<svg>`; ponha dentro de `CE.peca`.

## Movimentos (todos marcam o som)

```js
CE.sobe(el, t, {d, dist, ease, som})        // sobe de baixo em degraus, passa do ponto
CE.cresce(el, t, {d, s0, origem, som})      // cresce de um ponto (ancorado), opaco desde o 1º degrau
CE.pipoca(el, t, {d, r0, r, f, gain, som})  // 0 → passa → 1, girando de r0 para r; f = tom do pop
CE.pousa(el, t, {d, s0, som})               // letreiro: grande → tamanho, 3 degraus
const imp = CE.cai(el, t, {d, dist, r0, r, quique, som})   // surge e cai; devolve o instante do impacto
CE.amassa(el, imp, {s})                      // squash ao receber algo
CE.pan(cenaSai, cenaEntra, t, {d, dist})     // pan lateral liso + whoosh
CE.traca(svgDaGrade, t, {d, s})              // linhas da grade surgem em sequência
```

`som: false` silencia; `som: 'paper'` troca o tipo; `somOpc: {gain:-6}` ajusta.

## Exemplos curtos

Planeta + anel de objetos em elipse:

```js
const globo = await (await fetch('img/globo.json')).json();
const pl = CE.peca(s1, CE.planeta(globo, { r: 310 }), { x: 540 - 321, y: 1090 - 321, origem: '50% 50%', z: 2 });
CE.sobe(pl, .06, { d: .42, dist: 1150, ease: 'back.out(1.15)' });
for (let i = 0; i < 12; i++) {
  const a = (-90 + i * 30) * Math.PI / 180, w = 84, h = w * 1.8;
  const el = CE.peca(anel, CE.lata({ w, cor: CE.LATAS[i % 10], id: 'a' + i }), { x: 540 + Math.cos(a) * 452 - w / 2, y: 1090 + Math.sin(a) * 560 - h / 2, origem: '50% 50%', z: 3 });
  CE.pipoca(el, .56 + i * .055, { d: .22, r0: -25, r: 0, f: 480 + i * 40 });
}
onTick(t => anel.style.transform = `rotate(${(CE.q(t) * 4).toFixed(2)}deg)`);   // anel com transform-origin no centro do planeta
```

Pessoa P&B que cresce diante do semicírculo:

```js
const semi = CE.peca(s3, CE.mancha({ forma: 'semi', w: 1000, h: 520, cor: CE.COR.agua }), { x: 40, y: 950, z: 1 });
gsap.set(semi, { autoAlpha: 1 });
const p = CE.foto(s3, 'img/pessoa_pb.png', { x: 150, y: 1640 - 566, w: 900, z: 4, origem: '13% 97%' });  // origem nos pés
CE.cresce(p, 3.28, { d: .62 });
```

Foto em mancha com grade e acento colorido:

```js
const sw = CE.peca(s4, CE.mancha({ w: 770, h: 560, cor: CE.COR.aguaEsc, seed: 8, tremor: 10 }), { x: 34, y: 830, z: 1 });
const gr = CE.peca(s4, CE.grade({ w: 680, h: 748, passo: 68 }), { x: 352, y: 726, z: 2 });
gsap.set([sw, gr], { autoAlpha: 1 }); CE.traca(gr.querySelector('svg'), 4.47);
CE.sobe(CE.foto(s4, 'img/foto_pb.png', { x: 30, y: 647, w: 820, z: 3, sombra: false }), 4.51, { d: .36, dist: 900 });
// acento: mix-blend na .ce-peca, não no filho
const brasa = CE.peca(s4, `<div style="width:340px;height:380px;border-radius:50%;background:radial-gradient(closest-side,rgba(255,190,60,.95),rgba(255,128,24,.8) 38%,rgba(255,92,10,0))"></div>`, { x: 240, y: 880, z: 4, origem: '50% 50%', css: 'mix-blend-mode:multiply' });
```

## Ferramentas de imagem

```bash
P=audio/.venv/bin/python
$P tools/colagem.py papel   videos/<nn>/img/papel.jpg                         # papel cinza 1400×2400
$P tools/colagem.py adesivo videos/<nn>/img/x_cut.png videos/<nn>/img/x_pb.png --largura 900 --borda 10   # pessoa: P&B + borda branca
$P tools/colagem.py pb      videos/<nn>/img/x_cut.png videos/<nn>/img/x_pb.png --largura 820 --desbota .16 # foto em mancha
$P tools/colagem.py tamanho videos/<nn>/img/x_cut.png videos/<nn>/img/x_s.png  --largura 1200            # colorida sem borda
$P tools/globo.py videos/<nn>/img/globo.json --lon -50 --lat -8 --destaque brasil                        # planeta
```

- `--largura` = largura na tela (ou até 2× ela). A borda fica proporcional ao que se vê.
- Planeta: `--lon/--lat` escolhem o centro (África `20,5`; Europa `15,45`; Ásia `90,30`). `--destaque` usa `tools/ne/<nome>.geojson` (vem `brasil`; outros países: extraia do Natural Earth `ne_110m_admin_0_countries`).

### Fotos

- Busca: `$P tools/commons.py buscar "waste picker" --n 16 --folha previews/c.jpg` → olhe a folha → `$P tools/commons.py baixar "File:Nome exato.jpg" videos/<nn>/img/x.jpg --largura 2400` (grava `img/creditos.json`). Só CC0, domínio público, CC BY e CC BY-SA; BY e BY-SA pedem crédito no vídeo.
- Recorte: `$P tools/recortar.py x.jpg x_cut.png --max 1800` (Vision). Confira a prova em `previews/recorte-*.jpg`.
- **Horizonte de cidade** (o Vision não acha "objeto"): tire o céu por cor. Marque como céu os pixels azulados (`b > r+18`) ou brancos pouco saturados, desça cada coluna do topo até 6 pixels seguidos de não-céu, suavize a altura com mediana de 5 colunas e **abertura morfológica** (`scipy.ndimage.grey_opening`, largura ~31) para tirar os riscos de nuvem, e limite a altura a `mediana(181) + 150`. Sobrou pico? Zere o alfa acima da altura dos vizinhos.
- Evite fotos em que marcas apareçam grandes (latas de refrigerante de perto, por exemplo). Fardos vistos de longe funcionam: as marcas somem no tamanho de uso.

## Créditos

Faixa escura 55% na base da última cena, Poppins 500 16 px: `Fotos: autor (licença) · … · via Wikimedia Commons`. Entra 1,2 s depois do início da cena.
