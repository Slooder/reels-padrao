# Biblioteca de cenas: como é feita e como escrever uma cena nova

Leia este arquivo quando for **criar ou corrigir uma cena** (da biblioteca, em `"$CRIABR_SKILLS"/video-animacao-explicativa/cenas/`, ou própria de um projeto, em `<projeto>/animacoes/cenas/`). O contrato de cena do motor (`meta`, `build`, `seek`, `key`, `ancoras`, o `ctx`) está em `"$CRIABR_SKILLS"/video-direcao-de-arte/references/kit-api.md` §9–§11; aqui fica só o que a biblioteca acrescenta por cima dele, em `cenas/_ia.js`.

## 1. O que toda cena da biblioteca tem

| export | para quê |
|---|---|
| `meta` | `nome`, `descricao`, `dur_padrao`, `formatos: ['horizontal', 'vertical', 'quadrado']`, `alfa_padrao: false`, `grao: true` e `params: params({…específicos…}, { titulo: 'Chapéu padrão' })` — o `params()` de `_ia.js` acrescenta os parâmetros comuns |
| `roteiro(p, movimento)` | função **pura** (roda no Node, sem DOM): os passos que a cena terá com esses parâmetros — `[{ nome, tipo: 'entrada'\|'enfase'\|'texto', anim }]`, `anim` = segundos nominais da animação do passo, calculados das durações da DA (`movimento.duracoes`, `movimento.escalonamento`). É por ela que o `storyboard.py` confere o ritmo, casa as marcas `\|` do trecho e sabe quantos `passos_t` cabem — antes de qualquer render |
| `build(palco, p, ctx)` | valida o que o validador do motor não alcança (somas, tamanhos casados, dado real sem fonte), chama `montarQuadro`, monta o conteúdo dentro de `Q.conteudo`, guarda o estado com `guardar(ESTADOS, ctx, {…})` e devolve `Q.layout({…})` |
| `seek(t, ctx)` | estado completo de cada elemento em função de `t` (via `P.prog`/`P.lin`), e por último `Q.seek(t)` |
| `key(t, ctx)` / `ancoras(ctx)` | `ler(ESTADOS, ctx).P.chave(t)` e `.P.ancoras()` |

Parâmetros comuns (todos opcionais): `titulo` (chapéu na tarja da DA; `""` esconde), `legendas` (frase de cada passo; `[]` esconde; `*termo*` destaca), `passos_t` (instante de cada passo, em segundos locais), `cor` (token do destaque, padrão `primaria`), `ilustrativo` (padrão `true` = selo), `fonte` (crédito pelo `ctx.kit.credito`), `plataforma`, `reservar_legenda`.

## 2. `_ia.js` em uma olhada

| grupo | funções |
|---|---|
| quadro e ritmo | `montarQuadro(palco, p, ctx, { roteiro, legendas, selo })` → `Q` com `raiz`, `conteudo {x, y, w, h, x1, y1}`, `P`, `horizontal`, `seek(t)`, `layout(extra)`; `planejar(ctx, roteiro, passos_t)` (usado pelo quadro); `duracoes(roteiro, movimento)` → `{ minima, recomendada }`; `areaUtil(ctx, p)` |
| plano de passos `P` | `P.t[k]`, `P.fim[k]`, `P.anim[k]`, `P.e[k]` (compressão ≤ 1), `P.prog(t, passo, atraso, dur, curva)`, `P.lin(…)`, `P.passou(t, passo)`, `P.atual(t)`, `P.indice(nome)`, `P.chave(t)`, `P.marcar(passo, atraso, nome, tipo)`, `P.ancoras()` — `atraso` e `dur` em segundos **nominais**: encolhem juntos quando a cena é mais curta que o recomendado |
| peças | `caixaToken(ctx, texto, { tam, cor, modo: 'cheio'\|'contorno' })` → `{ el, medir(), estado({ caixa, realce, apagado }) }`; `no(ctx, { r })` → `{ el, em(cx, cy), estado({ ativacao, realce }) }`; `barra(ctx, { w, h })` → `estado({ fracao, realce, trilha })`; `matrizDeCalor(ctx, { linhas, colunas, lado })` → `grade(p)`, `celula(i, j, valor, p)`, `vazia`, `contornar`; `contador(ctx, { formato, modelo })` → `definir(v)`; `rotulo(ctx, texto, { tam, cor })`; `textoDuplo(ctx, papel, texto, { corA, corB })` → `misturar(q)` |
| traços (SVG) | `camadaSvg(ctx, pai)`; `linha(ctx, svg, x1, y1, x2, y2, { cor, esp, alfa, tracejado })` → `.tracar(p)`; `caminho(ctx, svg, d, …)`; `arco(ctx, svg, x1, y1, x2, y2, altura, …)`; `seta(…)` → `.tracar(p)`; `eixo(ctx, svg, x1, y1, x2, y2, { marcas })` |
| layout | `gradeResponsiva(n, area, { razao, vao, maxColunas })` → `pos(i)`; `quebrarEmLinhas(larguras, larguraMax, vao)` |
| contas | `comTemperatura(probs, T)`, `sortear(probs, u)`, `indiceDoMaior`, `conferirDistribuicao(lista, oQue)`, `ATIVACOES`, `num(v, casas)`, `pct(v)` (pt-BR), `marcarTermos` |
| estado | `guardar(mapa, ctx, estado)`, `ler(mapa, ctx)` — o estado fica preso ao `ctx`, então a mesma cena pode ser montada mais de uma vez na página |

## 3. Regras que as cenas seguem (cada uma veio de um erro)

1. **Cor muda por camadas, nunca por conta.** Interpolar RGB entre dois tokens produz, no meio do caminho, uma cor fora da paleta — o auditor amostra dezenas de instantes e reprova. Para "acender" algo: duas camadas sobrepostas, cada uma numa cor da DA, cruzadas por opacidade (`textoDuplo`, `caixaToken.estado({ realce })`, `barra.estado({ realce })`).
2. **Quem recebe `ctx.entrada` não recebe `transform` seu.** `ctx.entrada`/`ctx.saida` escrevem `opacity`, `transform` e `clip-path` do elemento. Deslocamento próprio vai numa casca em volta (é o que `tokenizacao` faz para a frase se abrir em pedaços).
3. **Uma cor de destaque por tela**: o token de `p.cor`. O resto é `texto`, `texto_suave`, `superficie` e as cores de `graficos.dados`. Série categórica (`ctx.dado(i)`) só onde a cor **é** o dado (o ruído de `difusao`).
4. **Nenhum texto abaixo de `ctx.tam('nota')`**; rótulo principal em `corpo` ou maior. `ctx.ajustar_texto(…, { min: ctx.tam('nota') })`.
5. **Glifo incerto se desenha.** A marca de espaço do token é feita com bordas, não com "␣": a fonte do papel pode não ter o caractere e o navegador cairia numa fonte de fora da DA.
6. **A cena não fabrica dado real.** Exemplo padrão → selo. Dado do usuário sem os números (pesos de atenção, ids com `ilustrativo: false`) → erro de `build` dizendo o que passar. Sorteio → gerador com `semente` (`ctx.rng`), nunca resultado escolhido.
7. **Tudo dentro de `Q.conteudo`** (a zona segura menos chapéu, frase do passo, crédito e, no vertical, a faixa da legenda queimada). Devolva em `Q.layout({ bloco: … })` o retângulo que ocupou: a suíte e o QA leem do carimbo.
8. **`roteiro()` e `seek()` contam a mesma história.** A soma de atrasos e durações usada em `seek` para o passo `k` não passa do `anim` declarado em `roteiro` — senão `P.chave(t)` devolve "quadro parado" com a animação ainda em curso e o vídeo sai travado nesse trecho (a suíte compara o quadro do vídeo com o PNG avulso e pega).

## 4. Esqueleto de uma cena nova

```js
import { params, guardar, ler, montarQuadro, rotulo } from './_ia.js';   // cena de projeto: copie _ia.js para animacoes/cenas/

export const meta = { nome: 'minha_cena', descricao: 'Uma frase: o que a cena demonstra.', dur_padrao: 8,
  formatos: ['horizontal', 'vertical', 'quadrado'], alfa_padrao: false, grao: true,
  params: params({ itens: { tipo: 'lista', min: 2, max: 6, itens: { tipo: 'texto' }, padrao: ['um', 'dois', 'três'], descricao: 'os itens' } }, { titulo: 'Minha cena' }) };

export function roteiro(p, mov) {
  const d = mov.duracoes, n = (p.itens || []).length;
  return [{ nome: 'itens', tipo: 'entrada', anim: d.media + n * mov.escalonamento * 2 }, { nome: 'destaque', tipo: 'enfase', anim: d.media }];
}
const ESTADOS = new WeakMap();

export function build(palco, p, ctx) {
  const Q = montarQuadro(palco, p, ctx, { roteiro: roteiro(p, ctx.DA.movimento), legendas: ['Os itens entram', 'e o primeiro ganha o *destaque*'] });
  const C = Q.conteudo;
  const els = p.itens.map((txt, i) => { const e = rotulo(ctx, txt, { tam: ctx.tam('h3'), cor: 'texto' }); Q.raiz.appendChild(e); ctx.medir(e); ctx.place(e, { x: C.x, y: C.y + i * ctx.tam('h3') * 1.6 }); return e; });
  guardar(ESTADOS, ctx, { ctx, Q, P: Q.P, els });
  return Q.layout({ bloco: { x: C.x, y: C.y, w: C.w, h: p.itens.length * ctx.tam('h3') * 1.6 } });
}
export function seek(t, ctxArg) {
  const { ctx, Q, P, els } = ler(ESTADOS, ctxArg);
  const d = ctx.DA.movimento.duracoes;
  els.forEach((e, i) => ctx.entrada(e, P.prog(t, 'itens', i * ctx.escalonamento * 2, d.media)));
  Q.seek(t);
}
export function key(t, ctx) { return ler(ESTADOS, ctx).P.chave(t); }
export function ancoras(ctx) { return ler(ESTADOS, ctx).P.ancoras(); }
```

Prove antes de registrar no storyboard: `"$CRIABR_SKILLS"/video-direcao-de-arte/kit/bin/da render --cena animacoes/cenas/minha_cena.js --saida "animacoes/_t/minha.png" --quadro 5 --escala 0.5` em horizontal e `--formato vertical`, em dois projetos de presets diferentes, e **abra os PNGs**. Depois `"$CRIABR_SKILLS"/video-direcao-de-arte/kit/bin/da lint --estrito animacoes/cenas`.

## 5. Suítes

Da pasta `"$CRIABR_SKILLS"/video-animacao-explicativa/scripts`, com `python -B -m`:

- `testes.lote` — o teste em lote: um quadro do meio de **cada** cena da pasta, em horizontal e vertical, nos presets `lab-ia` e `dossie`, pelo auditor (76 quadros, ~1 min). `--folhas "<pasta>"` grava uma folha de contato por preset e formato; `--fracao 0.88` mostra o estado final; `--so a,b`, `--presets`, `--formatos`, `--colunas`.
- `unittest testes.test_storyboard` — 16 testes do CLI, do contrato e da sincronia, sem navegador.
- `unittest testes.test_cenas` — 8 testes no motor: lint estrito, auditor em `lab-ia` e `editorial-claro`, pureza (quadro avulso = quadro do vídeo), erros de dado, caso apertado no `neon-shorts`, três formatos num terceiro preset e a caixa real dos pixels contra a área livre.

Cena nova em `cenas/` entra sozinha em todos (a lista é a pasta). O auditor confere cor, fonte e movimento, não posição: depois de mexer no layout de uma cena, gere as folhas do lote e **olhe**.
