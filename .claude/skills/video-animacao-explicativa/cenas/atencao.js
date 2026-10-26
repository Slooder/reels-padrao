// atencao.js — um token "olha" para os outros com pesos (arcos) ou a matriz inteira de atenção (calor).
// Passos (arcos): frase → consulta → olhar → pesos → mistura.   Passos (matriz): frase → grade → linhas → consulta.
// Simplificação declarada em references/didatica.md: mostra UMA cabeça de atenção de UMA camada, com pesos
// inventados; modelos reais têm dezenas de camadas e cabeças, e os pesos não são uma explicação do raciocínio.
import { params, guardar, ler, montarQuadro, caixaToken, rotulo, textoDuplo, camadaSvg, arco, matrizDeCalor, barra, conferirDistribuicao, clamp, pct, indiceDoMaior } from './_ia.js';

const EXEMPLO = {
  tokens: ['A', 'capital', 'da', 'França', 'é'],
  matriz: [[1, 0, 0, 0, 0], [0.3, 0.7, 0, 0, 0], [0.1, 0.55, 0.35, 0, 0], [0.06, 0.42, 0.12, 0.4, 0], [0.05, 0.36, 0.06, 0.45, 0.08]],
};

export const meta = {
  nome: 'atencao',
  descricao: 'Atenção: um token consulta os outros e distribui pesos que somam 100% (arcos), ou a matriz inteira de quem olha para quem (calor).',
  dur_padrao: 11,
  formatos: ['horizontal', 'vertical', 'quadrado'],
  alfa_padrao: false,
  grao: true,
  params: params({
    tokens: { tipo: 'lista', min: 2, max: 12, itens: { tipo: 'texto' }, padrao: EXEMPLO.tokens, descricao: 'os tokens da frase, na ordem' },
    consulta: { tipo: 'inteiro', padrao: null, min: 0, descricao: 'índice do token que consulta os outros (padrão: o último — é ele que vai prever o próximo)' },
    pesos: { tipo: 'lista', padrao: null,
      descricao: 'modo arcos: um peso por token (somam 1); modo matriz: uma linha por token, cada linha somando 1. Fora do exemplo padrão é obrigatório: a cena não inventa pesos' },
    modo: { tipo: 'opcao', opcoes: ['arcos', 'matriz'], padrao: 'arcos', descricao: 'arcos = um token e os pesos dele; matriz = todos os tokens (mapa de calor)' },
    causal: { tipo: 'booleano', padrao: true, descricao: 'true = cada token só enxerga os anteriores e a si mesmo (modelos geradores de texto, tipo GPT); false = enxerga a frase toda (codificadores, tipo BERT)' },
  }, { titulo: 'Atenção' }),
};

const LEGENDAS = {
  arcos: ['A frase, token por token', 'Um token *consulta* os anteriores', 'Ele olha mais para uns que para outros', 'Os pesos somam *100%*', 'e o token passa a carregar essa *mistura*'],
  arcosLivre: ['A frase, token por token', 'Um token *consulta* os outros', 'Ele olha mais para uns que para outros', 'Os pesos somam *100%*', 'e o token passa a carregar essa *mistura*'],
  matriz: ['Cada token nas linhas e nas colunas', 'Linha: *quem olha*. Coluna: para quem', 'Cada linha distribui *100%* de atenção', 'A linha do token que vai prever o próximo'],
};

export function roteiro(p, mov) {
  const d = mov.duracoes, e = mov.escalonamento, n = (p.tokens || EXEMPLO.tokens).length;
  if ((p.modo || 'arcos') === 'matriz') {
    return [
      { nome: 'frase', tipo: 'texto', anim: d.media + n * e * 2 },
      { nome: 'grade', tipo: 'entrada', anim: d.longa },
      { nome: 'linhas', tipo: 'enfase', anim: d.media + n * d.curta },
      { nome: 'consulta', tipo: 'enfase', anim: d.media + d.media },
    ];
  }
  return [
    { nome: 'frase', tipo: 'texto', anim: d.media + n * e * 2 },
    { nome: 'consulta', tipo: 'enfase', anim: d.media + d.curta },
    { nome: 'olhar', tipo: 'enfase', anim: d.longa + n * e * 3 },
    { nome: 'pesos', tipo: 'texto', anim: d.media + n * e * 2 + d.media },
    { nome: 'mistura', tipo: 'enfase', anim: d.media + d.longa + n * e },
  ];
}

const ESTADOS = new WeakMap();

function resolverPesos(p, tokens, consulta) {
  const n = tokens.length;
  const padrao = n === EXEMPLO.tokens.length && tokens.every((x, i) => x === EXEMPLO.tokens[i]);
  let bruto = p.pesos;
  if (bruto == null) {
    if (!padrao) throw new Error(`faltou "pesos": a cena não inventa pesos de atenção para os seus tokens. Passe ${p.modo === 'matriz' ? `${n} linhas com ${n} pesos cada (cada linha somando 1)` : `${n} pesos, um por token, somando 1`}`);
    bruto = EXEMPLO.matriz;
  }
  const eMatriz = Array.isArray(bruto[0]);
  if (p.modo === 'matriz' && !eMatriz) throw new Error(`modo "matriz" pede pesos como matriz: ${n} linhas (quem olha) com ${n} números cada (para quem)`);
  const conferirLinha = (linha, i) => {
    if (!Array.isArray(linha) || linha.length !== n) throw new Error(`pesos de "${tokens[i]}": esperava ${n} números (um por token), veio ${Array.isArray(linha) ? linha.length : typeof linha}`);
    conferirDistribuicao(linha, `pesos de "${tokens[i]}"`);
    if (p.causal) {
      const futuro = linha.findIndex((v, j) => j > i && v > 0.001);
      if (futuro >= 0) throw new Error(`causal=true: "${tokens[i]}" não enxerga "${tokens[futuro]}", que vem depois dele — zere esse peso, ou passe causal=false se o modelo explicado lê a frase inteira`);
    }
  };
  if (eMatriz) {
    if (bruto.length !== n) throw new Error(`pesos: a matriz tem ${bruto.length} linha(s) e a frase tem ${n} tokens`);
    bruto.forEach(conferirLinha);
    return { matriz: bruto, linha: bruto[consulta] };
  }
  conferirLinha(bruto, consulta);
  return { matriz: null, linha: bruto };
}

export function build(palco, p, ctx) {
  const tokens = p.tokens.map(String);
  const n = tokens.length;
  const consulta = p.consulta == null ? n - 1 : p.consulta;
  if (consulta >= n) throw new Error(`consulta = ${p.consulta}, mas a frase tem ${n} tokens (índices de 0 a ${n - 1})`);
  const { matriz, linha } = resolverPesos(p, tokens, consulta);
  const legendas = p.modo === 'matriz' ? LEGENDAS.matriz : (p.causal ? LEGENDAS.arcos : LEGENDAS.arcosLivre);
  const Q = montarQuadro(palco, p, ctx, { roteiro: roteiro(p, ctx.DA.movimento), legendas });
  const camada = ctx.el('div', 'at-camada');
  Object.assign(camada.style, { position: 'absolute', left: '0', top: '0' });
  Q.raiz.appendChild(camada);
  const S = p.modo === 'matriz' ? montarMatriz(ctx, p, Q, camada, tokens, consulta, matriz) : montarArcos(ctx, p, Q, camada, tokens, consulta, linha);
  guardar(ESTADOS, ctx, { ctx, Q, P: Q.P, modo: p.modo, n, consulta, causal: p.causal, ...S });
  return Q.layout({ modo: p.modo, disposicao: S.disposicao, consulta: tokens[consulta], mais_olhado: tokens[S.forte], ...S.info });
}

// ───────────────────────────────────────────────────────────────── arcos ──
function montarArcos(ctx, p, Q, camada, tokens, consulta, pesos) {
  const C = Q.conteudo, cor = p.cor, n = tokens.length;
  const maxPeso = Math.max(...pesos);
  const outros = pesos.map((w, j) => (j === consulta ? -1 : w));
  const forte = indiceDoMaior(outros);
  const tamPct = ctx.tam('corpo');
  // a "mistura": faixa com um trecho por token, largura proporcional ao peso
  const rotMix = rotulo(ctx, `o que “${tokens[consulta].trim()}” passa a carregar`, { tam: ctx.tam('nota') });
  camada.appendChild(rotMix);
  const mRot = ctx.medir(rotMix);
  const hMix = ctx.px(0.036);
  const hBlocoMix = mRot.h + ctx.px(0.01) + hMix;

  // tenta a fileira (tokens lado a lado, arcos por cima); se não couber com letra legível, vira coluna
  let caixas = null, tam, fileira = false, vao;
  for (tam = ctx.tam('h1'); tam >= ctx.tam('corpo') * 0.999; tam *= 0.93) {
    caixas = tokens.map((x) => { const c = caixaToken(ctx, x, { tam, cor, marcarEspaco: false }); camada.appendChild(c.el); c.medir(); return c; });
    vao = tam * 0.34;
    const total = caixas.reduce((a, c) => a + c.w, 0) + (n - 1) * vao;
    if (total <= C.w * (tam > ctx.tam('h2') ? 0.8 : 1)) { fileira = true; break; }
    for (const c of caixas) c.el.remove();
    caixas = null;
  }
  const svg = camadaSvg(ctx, camada);
  const pcts = pesos.map((w, j) => { const t = textoDuplo(ctx, 'dados', pct(w), { tam: tamPct, corA: 'texto', corB: cor, classe: 'at-pct' }); camada.appendChild(t.el); t.medir(); return t; });
  const arcos = [], barras = [];
  let xMix, wMix, yMix, info;
  if (fileira) {
    const total = caixas.reduce((a, c) => a + c.w, 0) + (n - 1) * vao;
    const hCaixa = caixas[0].h;
    const hArcoMax = Math.max(ctx.px(0.06), Math.min(C.h * 0.36, total * 0.3));
    const vaoMix = ctx.px(0.05);
    const hBloco = hArcoMax + hCaixa + ctx.px(0.012) + pcts[0].h + vaoMix + hBlocoMix;
    const y0 = C.y + Math.max(0, (C.h - hBloco) / 2);
    const yCaixa = y0 + hArcoMax;
    let x = C.x + (C.w - total) / 2;
    const cxs = [];
    caixas.forEach((c, j) => {
      ctx.place(c.el, { x: Math.round(x), y: Math.round(yCaixa) });
      cxs.push(x + c.w / 2);
      ctx.place(pcts[j].el, { x: Math.round(x + (c.w - pcts[j].w) / 2), y: Math.round(yCaixa + hCaixa + ctx.px(0.012)) });
      x += c.w + vao;
    });
    const maxDist = Math.max(...cxs.map((v) => Math.abs(v - cxs[consulta])));
    pesos.forEach((w, j) => {
      if (j === consulta || w <= 0.001) { arcos.push(null); return; }
      const dist = Math.abs(cxs[j] - cxs[consulta]);
      const h = hArcoMax * 0.92 * (dist / maxDist) ** 0.75;
      const a = arco(ctx, svg, cxs[consulta], yCaixa - 3, cxs[j], yCaixa - 3, cxs[j] < cxs[consulta] ? -h : h, { cor, esp: ctx.traco * (1.2 + 5 * w / maxPeso), alfa: 0.35 + 0.65 * w / maxPeso });
      arcos.push(a);
    });
    xMix = C.x + (C.w - total) / 2; wMix = total; yMix = yCaixa + hCaixa + ctx.px(0.012) + pcts[0].h + vaoMix;
    info = { tamanho_token: +tam.toFixed(1), bloco: { x: Math.round(xMix), y: Math.round(y0), w: Math.round(total), h: Math.round(hBloco) } };
  } else {
    // coluna: arcos na calha da esquerda, barra e percentual à direita de cada token
    const vaoMix = ctx.px(0.04);
    const hDisp = C.h - hBlocoMix - vaoMix;
    tam = Math.max(ctx.tam('nota'), Math.min(ctx.tam('h3'), (hDisp / n) / 1.75));
    caixas = tokens.map((x) => { const c = caixaToken(ctx, x, { tam, cor, marcarEspaco: false }); camada.appendChild(c.el); c.medir(); return c; });
    const hCaixa = caixas[0].h;
    const passo = Math.min(hCaixa * 1.3, hDisp / n);
    const calha = Math.min(C.w * 0.2, n * passo * 0.3);
    const wCaixa = Math.max(...caixas.map((c) => c.w));
    const wPct = Math.max(...pcts.map((t) => t.w));
    const xCaixa = C.x + calha;
    const xBarra = xCaixa + wCaixa + ctx.px(0.02);
    const wBarra = Math.max(ctx.px(0.05), C.x1 - wPct - ctx.px(0.016) - xBarra);
    const hBloco = n * passo + vaoMix + hBlocoMix;
    const y0 = C.y + Math.max(0, (C.h - hBloco) / 2);
    const cys = [];
    caixas.forEach((c, j) => {
      const y = y0 + j * passo + (passo - hCaixa) / 2;
      ctx.place(c.el, { x: Math.round(xCaixa), y: Math.round(y) });
      cys.push(y + hCaixa / 2);
      const b = barra(ctx, { w: wBarra, h: Math.max(6, hCaixa * 0.36), cor });
      camada.appendChild(b.el);
      ctx.place(b.el, { x: Math.round(xBarra), y: Math.round(y + hCaixa / 2 - b.h / 2) });
      barras.push(b);
      ctx.place(pcts[j].el, { x: Math.round(C.x1 - pcts[j].w), y: Math.round(y + (hCaixa - pcts[j].h) / 2) });
    });
    const maxDist = Math.max(...cys.map((v) => Math.abs(v - cys[consulta])));
    pesos.forEach((w, j) => {
      if (j === consulta || w <= 0.001) { arcos.push(null); return; }
      const dist = Math.abs(cys[j] - cys[consulta]);
      const h = (calha - ctx.px(0.012)) * 0.92 * (dist / maxDist) ** 0.75;
      arcos.push(arco(ctx, svg, xCaixa - 3, cys[consulta], xCaixa - 3, cys[j], cys[j] < cys[consulta] ? h : -h, { cor, esp: ctx.traco * (1 + 2.6 * w / maxPeso), alfa: 0.35 + 0.65 * w / maxPeso }));
    });
    xMix = C.x; wMix = C.w; yMix = y0 + n * passo + vaoMix;
    info = { tamanho_token: +tam.toFixed(1), bloco: { x: Math.round(C.x), y: Math.round(y0), w: Math.round(C.w), h: Math.round(hBloco) } };
  }
  // faixa da mistura
  ctx.place(rotMix, { x: Math.round(xMix), y: Math.round(yMix) });
  const yFaixa = yMix + mRot.h + ctx.px(0.01);
  const fresta = Math.max(2, ctx.px(0.003));
  const util = wMix - fresta * (pesos.filter((w) => w > 0.001).length - 1);
  let xs = xMix;
  const trechos = pesos.map((w) => {
    if (w <= 0.001) return null;
    const e = ctx.el('div', 'at-trecho');
    const larg = util * w;
    Object.assign(e.style, { position: 'absolute', left: xs.toFixed(1) + 'px', top: Math.round(yFaixa) + 'px', width: larg.toFixed(1) + 'px', height: hMix + 'px', background: ctx.cor(cor),
      borderRadius: Math.min(ctx.raio, hMix / 2) + 'px', transformOrigin: 'left center' });
    camada.appendChild(e);
    xs += larg + fresta;
    return { e, alfa: 0.3 + 0.7 * w / maxPeso };
  });
  const ordem = pesos.map((w, j) => j).filter((j) => arcos[j]).sort((a, b) => pesos[b] - pesos[a]);
  return { disposicao: fileira ? 'fileira' : 'coluna', caixas, pcts, arcos, barras, trechos, rotMix, pesos, maxPeso, forte, ordem, info };
}

// ──────────────────────────────────────────────────────────────── matriz ──
function montarMatriz(ctx, p, Q, camada, tokens, consulta, matriz) {
  const C = Q.conteudo, cor = p.cor, n = tokens.length;
  const tamRot = Math.max(ctx.tam('nota'), Math.min(ctx.tam('corpo'), C.w / (n * 5.2)));
  const linhasRot = tokens.map((x) => { const t = textoDuplo(ctx, 'dados', x.trim(), { tam: tamRot, corA: 'texto', corB: cor, classe: 'at-linha' }); camada.appendChild(t.el); t.medir(); return t; });
  const colsRot = tokens.map((x) => { const t = rotulo(ctx, x.trim(), { tam: tamRot, cor: 'texto' }); camada.appendChild(t); return { el: t, m: ctx.medir(t) }; });
  const wRot = Math.max(...linhasRot.map((t) => t.w));
  const maiorCol = Math.max(...colsRot.map((c) => c.m.w));
  const hRotulo = colsRot[0].m.h;
  const pcts = matriz[consulta].map((w) => { const t = rotulo(ctx, pct(w), { tam: ctx.tam('nota'), cor: 'texto' }); camada.appendChild(t); return { el: t, m: ctx.medir(t) }; });
  const vaoRot = ctx.px(0.014);
  const hBase = pcts[0].m.h + vaoRot;
  let lado = Math.min((C.w - wRot - vaoRot) / n, ctx.px(0.13));
  const girar = maiorCol > lado * 0.96;
  const hTopo = (girar ? maiorCol * 0.72 + hRotulo * 0.72 : hRotulo) + vaoRot;
  lado = Math.min(lado, (C.h - hTopo - hBase) / n);
  const vaoCel = Math.max(2, lado * 0.07);
  lado -= vaoCel * (n - 1) / n;
  const M = matrizDeCalor(ctx, { linhas: n, colunas: n, lado, vao: vaoCel, cor });
  camada.appendChild(M.el);
  const wTotal = wRot + vaoRot + M.w, hTotal = hTopo + M.h + hBase;
  const x0 = C.x + (C.w - wTotal) / 2, y0 = C.y + Math.max(0, (C.h - hTotal) / 2);
  const xM = x0 + wRot + vaoRot, yM = y0 + hTopo;
  ctx.place(M.el, { x: Math.round(xM), y: Math.round(yM) });
  linhasRot.forEach((t, i) => ctx.place(t.el, { x: Math.round(x0 + wRot - t.w), y: Math.round(yM + i * M.passo + (lado - t.h) / 2) }));
  colsRot.forEach((c, j) => {
    const cx = xM + j * M.passo + lado / 2;
    if (girar) { ctx.place(c.el, { x: Math.round(cx - hRotulo * 0.3), y: Math.round(yM - vaoRot - hRotulo) }); c.giro = 'rotate(-46deg)'; c.el.style.transformOrigin = 'left bottom'; }
    else { ctx.place(c.el, { x: Math.round(cx - c.m.w / 2), y: Math.round(yM - vaoRot - hRotulo) }); c.giro = ''; }
  });
  pcts.forEach((t, j) => ctx.place(t.el, { x: Math.round(xM + j * M.passo + lado / 2 - t.m.w / 2), y: Math.round(yM + M.h + vaoRot) }));
  const maxPeso = Math.max(...matriz.flat());
  const outros = matriz[consulta].map((w, j) => (j === consulta ? -1 : w));
  return { disposicao: 'matriz', M, matriz, linhasRot, colsRot, pcts, maxPeso, forte: indiceDoMaior(outros),
    info: { lado: Math.round(lado), rotulos_girados: girar, tamanho_rotulo: +tamRot.toFixed(1), bloco: { x: Math.round(x0), y: Math.round(y0), w: Math.round(wTotal), h: Math.round(hTotal) } } };
}

export function seek(t, ctxArg) {
  const S = ler(ESTADOS, ctxArg);
  const { ctx, Q, P, n, consulta, causal } = S;
  const d = ctx.DA.movimento.duracoes, e = ctx.escalonamento;
  if (S.modo === 'matriz') {
    const { M, matriz, linhasRot, colsRot, pcts, maxPeso } = S;
    const pCons = P.prog(t, 'consulta', 0, d.media, 'enfase');
    linhasRot.forEach((r, i) => { ctx.entrada(r.el, P.prog(t, 'frase', i * e * 2, d.media), 'fade'); r.misturar(i === consulta ? pCons : 0); });
    colsRot.forEach((c, j) => { ctx.entrada(c.el, P.prog(t, 'frase', j * e * 2, d.media), 'fade'); c.el.style.transform = c.giro || 'none'; });
    M.grade(P.prog(t, 'grade', 0, d.longa, 'suave'));
    for (let i = 0; i < n; i++) {
      const pl = P.prog(t, 'linhas', i * d.curta, d.media);
      for (let j = 0; j < n; j++) {
        M.celula(i, j, 0.12 + 0.88 * matriz[i][j] / maxPeso, matriz[i][j] > 0.001 ? clamp(pl * 1.3 - (j / n) * 0.3) : 0);
        M.vazia(i, j, causal && j > i ? P.prog(t, 'grade', d.media, d.longa - d.media) : 0);
      }
    }
    M.contornar(consulta, pCons);
    pcts.forEach((x, j) => ctx.entrada(x.el, P.prog(t, 'consulta', d.curta + j * e, d.media), 'fade'));
    Q.seek(t);
    return;
  }
  const { caixas, pcts, arcos, barras, trechos, rotMix, pesos, maxPeso, forte, ordem } = S;
  const pCons = P.prog(t, 'consulta', 0, d.media, 'enfase');
  const pFuturo = P.prog(t, 'consulta', d.curta * 0.5, d.media);
  caixas.forEach((c, j) => {
    ctx.entrada(c.el, P.prog(t, 'frase', j * e * 2, d.media));
    c.estado({ caixa: 1, realce: j === consulta ? clamp(pCons) : 0, apagado: causal && j > consulta ? pFuturo : 0 });
  });
  ordem.forEach((j, k) => arcos[j].tracar(P.prog(t, 'olhar', k * e * 3, d.longa, 'suave')));
  pcts.forEach((x, j) => {
    const visivel = !(causal && j > consulta);
    const pp = visivel ? P.prog(t, 'pesos', j * e * 2, d.media) : 0;
    ctx.entrada(x.el, pp, 'fade');
    const q = visivel ? P.lin(t, 'pesos', j * e * 2, d.media) : 0;
    x.definir(pct(pesos[j] * q));
    x.misturar(j === forte ? P.prog(t, 'pesos', d.media + n * e * 2, d.media, 'enfase') : 0);
    if (barras[j]) barras[j].estado({ fracao: (pesos[j] / maxPeso) * clamp(P.prog(t, 'pesos', j * e * 2, d.media, 'enfase'), 0, 1.04), realce: j === forte ? clamp(pp) : 0.45 * clamp(pp), trilha: visivel ? P.prog(t, 'frase', j * e * 2, d.media) : 0 });
  });
  ctx.entrada(rotMix, P.prog(t, 'mistura', 0, d.media), 'fade');
  let k = 0;
  trechos.forEach((tr) => {
    if (!tr) return;
    const pm = P.prog(t, 'mistura', d.curta + k * e, d.longa, 'enfase');
    tr.e.style.transform = `scaleX(${clamp(pm, 0, 1.04).toFixed(4)})`;
    tr.e.style.opacity = (pm > 0 ? tr.alfa : 0).toFixed(3);
    k++;
  });
  Q.seek(t);
}

export function key(t, ctx) { return ler(ESTADOS, ctx).P.chave(t); }

export function ancoras(ctx) { return ler(ESTADOS, ctx).P.ancoras(); }
