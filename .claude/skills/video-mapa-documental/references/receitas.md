# Receitas — dados do mapa e API da biblioteca `MD` (`lib/mapadoc.js`)

## Sumário
1. Dados do mapa (`tools/mapa.py`)
2. Esqueleto da página
3. Mapa: `MD.mapa`, estado e câmera
4. Manchas vermelhas
5. Anotações
6. Tempo: `MD.pisca`, `MD.apaga`, `MD.vai`
7. Problemas comuns

## 1. Dados do mapa (`tools/mapa.py`)

Tudo de domínio público: relevo **NASA GIBS** (Blue Marble Shaded Relief + ASTER GDEM) e vetores **Natural Earth**.

```bash
P=audio/.venv/bin/python
# texturas: caixa = lon0,lat0,lon1,lat1 (oeste,sul,leste,norte); ppd = pixels por grau
$P -I tools/mapa.py baixar fontes --bbox=-130,-60,0,75  --ppd 16  --nome base   # continente (abertura)
$P -I tools/mapa.py baixar fontes --bbox=-76,-36,-32,7  --ppd 64  --nome br     # país inteiro
$P -I tools/mapa.py baixar fontes --bbox=-57,-28,-37,-11 --ppd 160 --nome se    # região do mergulho final
# tinge em 3 materiais com alfa = terra → img/<nome>_cinza.webp, _verde.webp, _vermelho.webp
$P -I tools/mapa.py texturas fontes base videos/02-x/img --borda 0
$P -I tools/mapa.py texturas fontes br   videos/02-x/img --relevo
$P -I tools/mapa.py texturas fontes se   videos/02-x/img --relevo
# estados/províncias, contorno e rios → geo.json
$P -I tools/mapa.py vetores fontes Brazil videos/02-x/geo.json --bbox=-76,-36,-32,7
```

- **ppd**: escolha ≥ o zoom máximo em que a textura aparece (z final 97 → `--ppd 160` dá folga). O GIBS aceita até ~8000 px por lado; divida a caixa se passar.
- **`--relevo`** mistura o sombreado ASTER (só com ppd ≥ 40): deixa o close "enrugado" como na referência.
- **`--borda`** esfuma as bordas da caixa (padrão 4%) para a textura fina se fundir com a grossa. Use `0` na de base.
- **País**: nome em inglês do Natural Earth (`Brazil`, `Portugal`, `Mexico`, `Japan`, `Italy`…). O 50m só tem estados de 9 países; para os outros o script baixa o 10m (~40 MB) sozinho. País sem divisões vira uma região só.
- **Cores**: rampas em `MAT` e `AGUA` no topo do script.
- Créditos obrigatórios por boa prática: "Relevo: NASA Blue Marble / GIBS · Mapa: Natural Earth (domínio público)".

## 2. Esqueleto da página

```html
<script>VIDEO={w:1080,h:1920,fps:30,dur:8,bpm:96,music:{style:'documental',key:'D',gain:-2}}</script>
<script>LIBS=['mapadoc.js']</script>
<script src="../../lib/boot.js"></script>
<style>#stage{background:#111;overflow:hidden;position:relative;width:1080px;height:1920px}</style>
<div id="stage"></div>
<script>
const T = { acende: .85, mergulho: [1.0, 1.75], bordas: 1.2, /* … */ fim: 8 };
const cam = MD.camera([ /* quadros-chave, ver movimento.md */ ]);
window.SETUP = async () => {
  const st = K.$('#stage');
  const M = await MD.mapa(st, { geo: 'geo.json', lat0: -15, cam,
    tex: [{ bbox: [-130,-60,0,75], src: 'img/base' }, { bbox: [-76,-36,-32,7], src: 'img/br' }, { bbox: [-57,-28,-37,-11], src: 'img/se' }] });
  MD.acabamento(st, { grao: .07 });      // vinheta + grão (acima do mapa)
  MD.anotacoes(st, M);                    // camada das anotações (acima da vinheta)
  // … etiquetas, manchas, chamadas, triângulo, retrato, círculo …
  onTick(t => {
    M.ativo = MD.pisca(t, T.acende, .42, 1, .3);
    // … estado do mapa …
    M.desenhar(t); MD.tick(t);
  });
  cue('m:intro', 0); /* … sons … */
};
</script>
```

A ordem das chamadas define as camadas: mapa → vinheta/grão → anotações → créditos.

## 3. Mapa: `MD.mapa`, estado e câmera

`const M = await MD.mapa(parent, { geo, tex, lat0, cam, paleta?, maciez? })`

- `tex`: lista de baixo para cima; cada `src` carrega `src+'_cinza.webp'`, `'_verde.webp'`, `'_vermelho.webp'`.
- `lat0`: latitude de referência da projeção (meio do país).
- `cam`: função `t → {lon, lat, z}` (use `MD.camera([...])`). `z` = px por grau de latitude.
- `maciez`: desfoque das manchas em graus (padrão .13 → 11 px em z 86).
- `paleta`: troca `papel`, `grade`, `borda`, `brilho`, `rio`.

Estado (0..1) que o `onTick` anima antes de `M.desenhar(t)`:

| campo | efeito |
|---|---|
| `M.ativo` | país aceso em verde (clip pelos estados) |
| `M.bordas` | bordas brancas dos estados |
| `M.contorno` | contorno do país |
| `M.rios` | rios acesos (dentro do país) |
| `M.vermelho` | opacidade da camada vermelha (padrão .9) |
| `M.manchas` | lista de manchas (seção 4) |
| `M.grade`, `M.luz` | grade e luz do papel |

Utilitários: `M.xy(lon, lat)` → `[x, y]` na tela; `M.cam` (câmera atual); `M.zf(zRef, p)` fator de espessura.

## 4. Manchas vermelhas

```js
const m = MD.mancha(lon, lat, rx, ry, { rot: 0, seed, rug: .22 }); // rx, ry em graus; contorno pincelado irregular
M.manchas.push(m);
// no onTick:
m.a = MD.pisca(t, t0, .32, seed, .35);                    // acende piscando
m.s = K.lerp(.75, 1, MD.vai(t, t0, .3, 'power2.out'));    // cresce ao acender
```

- **Espalhar**: várias manchas com atraso de ~0,08 s, na ordem do caminho (origem → destino).
- **Fundir num núcleo** (fase 7): as periféricas `m.a *= MD.apaga(t, tF, .3, seed)`; as do núcleo `m.s *= K.lerp(1, 1.45, MD.vai(t, tF, .5, 'power2.inOut'))`; e 3–5 **manchas-ponte** entre elas com `a` de 0 → 1 em .4 s. A máscara é desfocada, então elas viram uma região só, como metaballs.
- O vermelho só pinta onde há terra (alfa da textura): mancha sobre o mar some sozinha.

## 5. Anotações (DOM presas a lon/lat)

Todas aparecem piscando e são atualizadas por `MD.tick(t)`.

```js
MD.etiqueta(lon, lat, 'Minas Gerais', t0, { dim: [3.5, .5], ate: 5.9 });   // pílula com ponteiro ▼ apontando para lon/lat
MD.cidade(lon, lat, 'Belém', t0, { lado: 'e' });                          // ponto + nome verde ('e' = texto à esquerda)
MD.chamada(lon, lat, ['Vale do Paraíba', 'século XIX'], t0, {
  cot: [56, 112], ponta: [440, 112],   // cotovelo e fim do trecho horizontal, em px a partir do alvo
  tam: 41, lado: 'acima', seed: 7 });  // rótulo sobre (ou 'abaixo' do) trecho horizontal; decodifica sozinho
MD.triangulo(lon, lat, ['Café'], t0, { lado: 264, tam: 62, escala: () => M.cam.z / 86,
  miolo: { src: 'img/foto_pb.jpg', diam: 112, t: 5.95 } });               // foto redonda atrás do texto a partir de t
MD.retrato(lon, lat, 'img/foto_pb.jpg', ['FRUTO DO', 'CAFEEIRO'], t0, { diam: 220, dx: 222, dy: -168,
  escala: () => M.cam.z / 86, para: { t: 5.45, d: .5, dx: 0, dy: -10, s: .51, esconde: true } }); // voa para o miolo
MD.circulo(lon, lat, 360, t0, { escala: () => M.cam.z / 86, tracos: 26, giro: 2.5 });
K.html(st, `<div class="md-cred" id="cred">Relevo: NASA Blue Marble / GIBS · Mapa: Natural Earth (domínio público)<br>Foto: Autor, CC BY-SA 4.0, via Wikimedia Commons</div>`);
```

- **Troca retrato → miolo**: `para.s = miolo.diam / retrato.diam` e `miolo.t = para.t + para.d`; com `esconde: true` o retrato some no mesmo quadro em que o miolo aparece.
- **Texto decodificado avulso**: `MD.decodifica(el, t0)` devolve `t => …` para chamar no tick; `el` precisa de filhos `.md-l`.
- Os rótulos usam CSS `text-transform: uppercase`; escreva normal com acentos.
- Classes para ajustar no CSS da página: `.md-tag`, `.md-cidade`, `.md-rotulo`, `.md-l2`, `.md-tri-txt`, `.md-ret-leg`, `.md-linha`, `.md-circ`, `.md-vinheta`, `.md-cred`.

## 6. Tempo

- `MD.pisca(t, t0, d=.4, seed=1, dim=.35)` → 0 antes, 1 depois, padrão liga/desliga no meio. Use `seed` diferente em cada peça para não piscarem iguais.
- `MD.apaga(t, t0, d=.3, seed)` → 1 antes, 0 depois, decaindo com tremidas.
- `MD.vai(t, t0, d, ease)` → 0..1 com ease do GSAP (para crescer, escurecer, mover).
- `MD.camera(keys)` → função de câmera; cada chave pode ter `ease` (vale para o trecho que termina nela).

## 7. Problemas comuns

- **País não acende / sem bordas:** `geo.json` com anéis vazios (simplificação de anel fechado) — use o `mapa.py` desta skill, que corta o anel antes de simplificar.
- **Vermelho só aparece numa caixa:** composição com `source-in`; a lib usa `destination-in` com a máscara desfocada — não troque.
- **Emenda visível entre texturas:** gere a fina com `--borda` (> 0) e com o mesmo `--relevo` da de baixo, ou aceite (a emenda some quando a fina cobre a tela inteira).
- **Rótulo cortando o círculo tracejado:** suba o cotovelo (`cot[1]` mais negativo) até o rótulo ficar fora do círculo.
- **Rótulo saindo da tela no empurrão final:** tire `escala` da chamada; diminua `ponta[0]` ou `tam`.
- **Lento para renderizar:** texturas grandes demais; mantenha cada `.webp` ≤ ~3500 px de lado.
