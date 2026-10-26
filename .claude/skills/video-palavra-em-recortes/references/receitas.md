# Receitas — API de `lib/recortes.js` (global `RC`)

Na página: `<script>LIBS=['recortes.js']</script>` antes do `boot.js`. Monte tudo no corpo do script e chame `RC.medir()` no `window.SETUP`.

## Esqueleto (frase)

```js
VIDEO = { w:1080, h:1920, fps:30, dur:8.4, bpm:150, music:{ style:'drill', key:'F', gain:1 } }
const stage = K.$('#stage');
const palco = RC.palco(stage);                       // lente velha: varredura, vinheta, estouro
const F = RC.frase(palco, {
  de: 0, q: 3, segura: 9, tam: 165, zoom: [1, 1.5], giro: [0, -7], seed: 21,
  palavras: [
    { palavra: 'Uma', frases: [['', 'ideia na cabeça e'], ['Pense nisso.', 'frase basta'], /* … 10 no total */] },
    { palavra: 'palavra', frases: [/* 10 */], materiais: ['jornal', 'livro', 'maquina'] },   // opcional: restringe
  ],
});
const ult = F.montagens.map(m => m.pags[m.pags.length - 1]);          // a página que segura cada palavra
RC.colagem(stage, ult.map((p, i) => ({ palavra: ['Uma','palavra'][i], pagina: p })), { de: 5.2, passo: .4, tam: 240 });
window.SETUP = async () => { RC.medir(); };
```

## `RC.palco(pai, o)`

Caixa que roda as montagens (uma de cada vez, pelo tempo) com a lente por cima. `o.varredura:false` tira as linhas. Devolve `{el, cam, montagens}`.

## `RC.frase(palco, o)` → `{montagens, fim}`

Uma montagem por palavra, em sequência a partir de `o.de`. Opções comuns a todas: `q` (quadros por recorte, 3), `segura` (quadros do último, 9), `tam` (corpo em px, 165 = macro da referência), `zoom`, `giro` (o sinal alterna por palavra), `vinheta`, `empurra` (.045), `seed`. Cada item de `palavras` aceita as opções de `RC.montagem`.

## `RC.montagem(palco, o)` → `{de, fim, ini, quadros, pags}`

- `palavra` — a palavra grifada (aparece exatamente assim; materiais `up` põem em maiúsculas).
- `frases` — lista de `[antes, depois, topo?]`. `depois` que começa com pontuação não ganha espaço. `topo` = cabeçalho em negrito na linha de cima (`''` = sem; omitido = sorteado de `RC.TOPOS`).
- Fixar uma página: `Object.assign(['antes', 'depois', ''], { material: 'jornal', fonte: 0, grifo: 'circulo:vermelho' })`.
- `quadros` — lista de durações (em quadros) por recorte; sem ela: `q` para todos e `segura` no último.
- `materiais` — nomes permitidos, sorteados sem repetir em sequência (`ordem:'lista'` usa a ordem dada, um por recorte). `grifos` — força uma lista de grifos (ex.: só `['reta:amarelo']` para ficar idêntico à referência).
- `corpo` — frases das linhas de cima/baixo (padrão `RC.CORPO`, genéricas e sem fatos); `de`; `seed`; `estouro:false`; `tom` (semitons da voz de fita).
- Marca os sons: `clique` em cada recorte e `fita` na montagem toda.

## `RC.colagem(pai, itens, o)` → `{el, ts}`

Bilhete de recortes. `itens = [{palavra, pagina}]` (usa papel, fonte e grifo da página) ou `[{palavra, material, fonte, grifo, esc}]`. Opções: `de`, `passo` (0,4 = uma batida), `ate`, `tam` (240), `giros` (lista de graus), `centro` (y do meio da pilha, 950), `gap` (30), `fundo` (material do fundo, `'escuro'`), `seed`. Marca `tapa` em cada entrada.

## Outras peças

- `RC.pagina(pai, palavra, spec)` — uma página avulsa (`spec = {material, fonte, grifo, antes, depois, topo, corpo:[11], tam, seed}`); use dentro de um `palco.cam` se quiser compor algo próprio.
- `RC.palavra(txt, M, F, grifo, rng)` — só o HTML da palavra grifada (para títulos, cartelas).
- `RC.GRIFOS.novo = (r, cor, M) => '<i class="rc-g" style="…">…</i>'` — grifo novo: um elemento absoluto dentro da palavra (`left/right/top/bottom` em `em`). SVG com `viewBox="0 0 100 100" preserveAspectRatio="none"` + `vector-effect="non-scaling-stroke"` para o traço não deformar. `z-index:0` fica atrás do texto, `2` por cima.
- `RC.MATERIAIS.meu = { papel:'meu_papel', tinta:'#222', ent:1.35, fontes:[['Fraunces',400,700,1]], grifos:['marca:amarelo'] }` — fonte: `[família, peso, peso da palavra, escala, 'up'?, espaçamento?]`; `pauta:true` desenha pauta de caderno; `escuro:true` troca a cor do texto grifado; `cab` aumenta o cabeçalho.

## Escrever os trechos (o que mais pesa no resultado)

- **10 por palavra** (9 piscam, o 10º segura). A palavra tem de estar num contexto que um leitor reconheça como texto de verdade: "a última **palavra** é sempre", "o vento **muda** de direção", "antes de **tudo**, respire".
- **2–4 palavras de cada lado.** Varie: palavra no começo (`['', 'ideia na cabeça e']`), no meio, no fim (`['quando a estação', ',']`), depois de ponto (`['Pense nisso.', 'frase basta']`).
- **Mantenha a caixa da palavra igual à da frase** (se a frase começa com "Uma", escreva trechos em que "Uma" abre a frase).
- **O último trecho** pode ser a própria frase com a palavra da vez grifada (`['Uma', 'muda tudo']` para "palavra") — junta as montagens num sentido só.
- Português correto, sem números nem fatos inventados, sem marcas, sem nomes de pessoas reais.

## Prévia e conferência

```bash
$N render.mjs <nn> --at=0.05,0.5,1.15,2.35,3.55,4.75,5.3,6.6      # um instante de cada palavra + colagem
$N render.mjs <nn> && audio/.venv/bin/python tools/analisar.py passo out/<nn-nome>.mp4 previews/x --de 0 --ate 1.3
audio/.venv/bin/python tools/analisar.py comparar <referência.mp4> out/<nn-nome>.mp4 previews/comparar.jpg
```

No `passo`, a palavra tem de estar no mesmo ponto em todos os quadros e o papel tem de mudar a cada 3.

## Texturas

```bash
audio/.venv/bin/python tools/papeis.py --folha previews/papeis.jpg          # refaz todas e mostra
audio/.venv/bin/python tools/papeis.py novo azulado --cor 200,215,230 --fibras 600 --amassado 2
```

Saem com 760×1160 e são usadas em 2× (1520×2320): cobre o quadro com zoom ≥ 1 e giro de até ~10°.
