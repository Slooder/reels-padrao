// tokenizacao.js — a frase vira pedaços (tokens) e cada pedaço vira o número dele no vocabulário.
// Passos: frase → pedacos → ids → sequencia. A lista de números do último passo é o que o modelo recebe.
// Simplificação declarada em references/didatica.md: os pedaços e os números do exemplo padrão são inventados
// (selo "ilustrativo"); cada modelo tem o próprio tokenizador e o próprio vocabulário.
import { params, guardar, ler, montarQuadro, caixaToken, textoDuplo, rotulo, quebrarEmLinhas, clamp, num } from './_ia.js';

const EXEMPLO = { tokens: ['Token', 'ização', ' não', ' é', ' mág', 'ica', '.'], ids: [30642, 4517, 1235, 380, 9284, 2271, 13] };

export const meta = {
  nome: 'tokenizacao',
  descricao: 'Tokenização: a frase é quebrada em pedaços (tokens) e cada pedaço vira o número dele no vocabulário — a lista de números é o que o modelo recebe.',
  dur_padrao: 9,
  formatos: ['horizontal', 'vertical', 'quadrado'],
  alfa_padrao: false,
  grao: true,
  params: params({
    tokens: { tipo: 'lista', min: 2, max: 14, itens: { tipo: 'texto' }, padrao: EXEMPLO.tokens,
      descricao: 'os pedaços, na ordem, exatamente como o tokenizador os separa; o espaço inicial faz parte do token (" não")' },
    ids: { tipo: 'lista', padrao: null, itens: { tipo: 'inteiro', min: 0 },
      descricao: 'o número de cada token no vocabulário (mesma quantidade de `tokens`). Sem ids, a cena mostra números de exemplo e exige ilustrativo=true' },
    destaque: { tipo: 'inteiro', padrao: null, min: 0, descricao: 'índice do pedaço cujo par pedaço → número ganha o destaque (padrão: o primeiro pedaço que continua uma palavra)' },
  }, { titulo: 'Tokenização' }),
};

const LEGENDAS = ['O texto que você escreve', 'é quebrado em pedaços: os *tokens*', 'Cada token tem um *número* fixo', 'O modelo só recebe *números*'];

export function roteiro(p, mov) {
  const d = mov.duracoes, e = mov.escalonamento, n = (p.tokens || EXEMPLO.tokens).length;
  return [
    { nome: 'frase', tipo: 'texto', anim: d.longa },
    { nome: 'pedacos', tipo: 'enfase', anim: d.media * 1.5 + n * e + d.curta },
    { nome: 'ids', tipo: 'texto', anim: d.media + n * e * 2 + d.media },
    { nome: 'sequencia', tipo: 'enfase', anim: d.media * 2 },
  ];
}

/** Número de exemplo estável para um pedaço sem id (só com ilustrativo=true): nunca passa por dado real. */
function idDeExemplo(texto) {
  let h = 2166136261;
  for (const c of texto) { h ^= c.codePointAt(0); h = Math.imul(h, 16777619) >>> 0; }
  return 100 + (h % 49900);
}

const ESTADOS = new WeakMap();

export function build(palco, p, ctx) {
  const tokens = p.tokens.map(String);
  if (tokens.some((x) => !x.length)) throw new Error('tokens: há um pedaço vazio na lista');
  let ids = p.ids;
  if (ids && ids.length !== tokens.length) throw new Error(`ids tem ${ids.length} número(s) e tokens tem ${tokens.length} pedaço(s): é um número por pedaço`);
  if (!ids) {
    const padrao = tokens.length === EXEMPLO.tokens.length && tokens.every((x, i) => x === EXEMPLO.tokens[i]);
    if (!padrao && p.ilustrativo === false) throw new Error('faltou "ids": com ilustrativo=false a cena não inventa os números — passe o id real de cada token (e a fonte)');
    ids = padrao ? EXEMPLO.ids : tokens.map(idDeExemplo);
  }
  const n = tokens.length;
  const destaque = p.destaque != null ? p.destaque : Math.max(0, tokens.findIndex((x, i) => i > 0 && !/^\s/.test(x) && /\p{L}/u.test(x)));
  if (destaque >= n) throw new Error(`destaque = ${p.destaque}, mas só há ${n} pedaços (índices de 0 a ${n - 1})`);

  const Q = montarQuadro(palco, p, ctx, { roteiro: roteiro(p, ctx.DA.movimento), legendas: LEGENDAS });
  const C = Q.conteudo, P = Q.P;
  const cor = p.cor;
  const camada = ctx.el('div', 'tok-camada');
  Object.assign(camada.style, { position: 'absolute', left: '0', top: '0' });
  Q.raiz.appendChild(camada);

  // contador ("7 tokens") e a linha final com a lista de números
  const conta = rotulo(ctx, `${n} tokens`, { tam: ctx.tam('corpo') });
  camada.appendChild(conta);
  const mConta = ctx.medir(conta);
  const rotSeq = rotulo(ctx, 'entrada do modelo', { tam: ctx.tam('nota') });
  camada.appendChild(rotSeq);
  const mRot = ctx.medir(rotSeq);
  const seq = ctx.texto('dados', `[${ids.join(', ')}]`, { tam: ctx.tam('h3'), cor, wrap: true, maxW: C.w, classe: 'tok-seq' });
  seq.style.position = 'absolute';
  camada.appendChild(seq);
  ctx.ajustar_texto(seq, C.w, { min: ctx.tam('nota'), maxLinhas: Q.horizontal ? 1 : 3 });
  let mSeq = ctx.medir(seq);

  // tenta do maior tamanho para o menor até as fileiras caberem
  const vaoBloco = ctx.px(0.03);
  let fixo = mConta.h + vaoBloco * 0.6 + vaoBloco * 1.4 + mRot.h + ctx.px(0.008) + mSeq.h;
  let U = null;
  for (let tam = ctx.tam('h1'); ; tam *= 0.93) {
    const minimo = tam <= ctx.tam('corpo');
    // horizontal: uma fileira só enquanto a letra não ficar pequena; vertical: a maior letra que couber em até 4 fileiras
    const maxFileiras = Q.horizontal ? (tam >= ctx.tam('h3') ? 1 : 2) : 4;
    const tamId = Math.max(ctx.tam('nota'), tam * 0.52);
    const caixas = tokens.map((x) => { const c = caixaToken(ctx, x, { tam, cor }); camada.appendChild(c.el); c.medir(); return c; });
    const numeros = ids.map((v) => { const d = textoDuplo(ctx, 'dados', String(v), { tam: tamId, corA: 'texto_suave', corB: cor, classe: 'tok-id' }); camada.appendChild(d.el); d.medir(); return d; });
    const vao = tam * 0.3, fio = tam * 0.34;
    const larguras = caixas.map((c, i) => Math.max(c.w, numeros[i].w));
    const fileiras = quebrarEmLinhas(larguras, C.w, vao);
    const hFileira = caixas[0].h + fio + numeros[0].h;
    const vaoFileira = tam * 0.5;
    const hTotal = fileiras.length * hFileira + (fileiras.length - 1) * vaoFileira + fixo;
    const coube = fileiras.length <= maxFileiras && hTotal <= C.h && Math.max(...larguras) <= C.w;
    // fichas no mínimo e ainda sobra altura por fazer: quem encolhe agora é a lista de números do fim (até `nota`),
    // que no vertical ocupa até 3 linhas na escala h3 — numa DA de letra grande ela sozinha estourava a área útil
    if (!coube && minimo && hTotal > C.h && seq._tam * 0.93 >= ctx.tam('nota')) {
      for (const c of caixas) c.el.remove();
      for (const d of numeros) d.el.remove();
      seq._tam *= 0.93; seq._inner.style.fontSize = seq._tam.toFixed(2) + 'px';
      mSeq = ctx.medir(seq);
      fixo = mConta.h + vaoBloco * 0.6 + vaoBloco * 1.4 + mRot.h + ctx.px(0.008) + mSeq.h;
      tam /= 0.93;                                          // repete este tamanho de ficha com a lista menor
      continue;
    }
    if (coube || minimo) {
      U = { tam, tamId, caixas, numeros, vao, fio, larguras, fileiras, hFileira, vaoFileira, hTotal };
      break;
    }
    for (const c of caixas) c.el.remove();
    for (const d of numeros) d.el.remove();
  }
  if (U.hTotal > C.h + 1) throw new Error(`tokenizacao: ${n} pedaços não couberam na área útil deste formato (${Math.round(C.w)} × ${Math.round(C.h)} px) nem com a menor letra legível da DA — use uma frase mais curta. Para ganhar altura: titulo: "", ou reservar_legenda=false se a peça não leva legenda queimada`);

  // posições: bloco centrado na altura do conteúdo, alinhado à esquerda (grade da DA)
  const y0 = C.y + Math.max(0, (C.h - U.hTotal) / 2);
  ctx.place(conta, { x: C.x, y: Math.round(y0) });
  const yFileiras = y0 + mConta.h + vaoBloco * 0.6;
  const fios = [];
  const unidades = new Array(n);
  U.fileiras.forEach((f, r) => {
    let x = C.x, xFrase = C.x;
    const y = yFileiras + r * (U.hFileira + U.vaoFileira);
    for (const i of f.itens) {
      const c = U.caixas[i], d = U.numeros[i], w = U.larguras[i];
      const xc = x + (w - c.w) / 2;
      const casca = ctx.el('div', 'tok-casca');              // a casca leva o deslocamento da frase; a caixa dentro fica livre para a entrada da DA
      ctx.place(casca, { x: Math.round(xc), y: Math.round(y), w: c.w, h: c.h });
      camada.appendChild(casca);
      casca.appendChild(c.el);
      ctx.place(c.el, { x: 0, y: 0 });
      ctx.place(d.el, { x: Math.round(x + (w - d.w) / 2), y: Math.round(y + c.h + U.fio) });
      const fioEl = ctx.el('div', 'tok-fio');
      Object.assign(fioEl.style, { position: 'absolute', left: Math.round(x + w / 2) + 'px', top: Math.round(y + c.h + U.fio * 0.18) + 'px', width: Math.max(1, ctx.traco * 0.75).toFixed(1) + 'px',
        height: Math.round(U.fio * 0.64) + 'px', background: ctx.alfa('texto_suave', 0.8), transformOrigin: 'center top' });
      camada.appendChild(fioEl);
      fios.push(fioEl);
      // na frase corrida (passo 1) os pedaços ficam colados: deslocamento do texto de cada caixa até a posição dele na frase
      const xTexto = Math.round(xc) + c.padX + c.wEspaco;
      unidades[i] = { c, d, casca, fio: fioEl, dx: (xFrase + c.wEspaco) - xTexto, letras: c.texto.length };
      xFrase += c.wEspaco + c.wTexto;
      x += w + U.vao;
    }
  });
  const ySeq = yFileiras + U.fileiras.length * U.hFileira + (U.fileiras.length - 1) * U.vaoFileira + vaoBloco * 1.4;
  ctx.place(rotSeq, { x: C.x, y: Math.round(ySeq) });
  ctx.place(seq, { x: C.x, y: Math.round(ySeq + mRot.h + ctx.px(0.008)) });

  const totalLetras = unidades.reduce((a, u) => a + u.letras, 0);
  let antes = 0;
  for (const u of unidades) { u.de = antes / totalLetras; u.ate = (antes + u.letras) / totalLetras; antes += u.letras; }
  guardar(ESTADOS, ctx, { ctx, Q, P, unidades, conta, rotSeq, seq, destaque, n, nSeq: seq._inner.textContent.length });
  return Q.layout({ tokens: n, fileiras: U.fileiras.length, tamanho_token: +U.tam.toFixed(1), tamanho_id: +U.tamId.toFixed(1), tamanho_sequencia: +seq._tam.toFixed(1), destaque,
    bloco: { x: Math.round(C.x), y: Math.round(y0), w: Math.round(Math.max(...U.fileiras.map((f) => f.largura), mSeq.w)), h: Math.round(U.hTotal) } });
}

export function seek(t, ctxArg) {
  const { ctx, Q, P, unidades, conta, rotSeq, seq, destaque, n, nSeq } = ler(ESTADOS, ctxArg);
  const d = ctx.DA.movimento.duracoes, e = ctx.escalonamento;
  const pFrase = P.lin(t, 'frase', 0, d.longa);
  const pAbre = P.prog(t, 'pedacos', 0, d.media, 'enfase');
  const pSeq = P.prog(t, 'sequencia', 0, d.media);
  unidades.forEach((u, i) => {
    // 1. a frase entra corrida, um pedaço depois do outro (com a entrada da DA)
    ctx.entrada(u.c.el, clamp((pFrase - u.de) / (u.ate - u.de)), undefined, { n: u.letras });
    // 2. os pedaços se afastam e a caixa de cada um aparece
    u.casca.style.transform = `translateX(${(u.dx * (1 - pAbre)).toFixed(2)}px)`;
    const pCaixa = P.prog(t, 'pedacos', d.media * 0.5 + i * e, d.media);
    // 3. o número de cada pedaço; depois o destaque em um par
    const pId = P.prog(t, 'ids', i * e * 2, d.media);
    const pPar = i === destaque ? P.prog(t, 'ids', d.media + n * e * 2, d.media, 'enfase') * (1 - pSeq) : 0;
    u.c.estado({ caixa: pCaixa, realce: clamp(pPar), apagado: pSeq });
    u.fio.style.transform = `scaleY(${clamp(pId).toFixed(4)})`;
    u.fio.style.opacity = (pId > 0 ? 1 - 0.7 * pSeq : 0).toFixed(3);
    ctx.entrada(u.d.el, pId, undefined, { n: 6 });
    u.d.misturar(clamp(pPar));
  });
  ctx.entrada(conta, P.prog(t, 'pedacos', d.media * 1.5 + n * e, d.curta), 'fade');
  // 4. a lista de números: é isto que o modelo recebe
  ctx.entrada(rotSeq, pSeq, 'fade');
  ctx.entrada(seq, P.prog(t, 'sequencia', d.curta, d.media * 2 - d.curta), undefined, { n: nSeq });
  Q.seek(t);
}

export function key(t, ctx) { return ler(ESTADOS, ctx).P.chave(t); }

export function ancoras(ctx) { return ler(ESTADOS, ctx).P.ancoras(); }
