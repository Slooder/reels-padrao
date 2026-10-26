// difusao.js — do ruído à imagem em passos: a cada passo a rede estima o ruído e tira um pouco, guiada pelo pedido.
// Passos: ruido → pedido → passo1 … passoK → imagem.
// Ruído e imagem são feitos de quadradinhos nas cores da DA (DOM auditável, nada de canvas): a imagem é um mosaico
// de tokens de cor; o ruído é uma camada de quadradinhos de cores sorteadas (semente) por cima, cuja opacidade é o
// nível de ruído. Cada estado do caminho é a mistura imagem + ruído — a mesma forma das fórmulas de difusão.
// Simplificação declarada em references/didatica.md: poucos passos (os geradores reais usam dezenas), direto nos
// pixels (quase todos trabalham num espaço comprimido e decodificam no fim), e a cena já conhece a imagem final —
// o modelo real não: ele só estima, a cada passo, o ruído a retirar.
import { params, guardar, ler, montarQuadro, rotulo, barra, contador, clamp, pct } from './_ia.js';

const GATO = [
  '................',
  '..##........##..',
  '..###......###..',
  '..####....####..',
  '..############..',
  '.##############.',
  '.##############.',
  '.###oo####oo###.',
  '.###oo####oo###.',
  '.##############.',
  '.######oo######.',
  '.##############.',
  '..####o##o####..',
  '..#####oo#####..',
  '...##########...',
  '................',
];
const TINTAS = { '.': 'fundo', '#': null, o: 'texto', '+': 'texto_suave', '=': 'superficie', s: 'secundaria', d: 'destaque' };

export const meta = {
  nome: 'difusao',
  descricao: 'Difusão: a imagem nasce do ruído em passos — a cada passo a rede estima o ruído e remove um pouco, guiada pelo pedido em texto.',
  dur_padrao: 16,
  formatos: ['horizontal', 'vertical', 'quadrado'],
  alfa_padrao: false,
  grao: true,
  params: params({
    imagem: { tipo: 'lista', min: 6, max: 24, padrao: GATO, itens: { tipo: 'texto' },
      descricao: 'a imagem final em mosaico: uma linha de texto por fileira, todas do mesmo tamanho. "." fundo · "#" a cor do destaque · "o" texto · "+" texto_suave · "=" superficie · "s" secundaria · "d" destaque · 1–9 = cor.dados' },
    pedido: { tipo: 'texto', padrao: 'um gato', descricao: 'o pedido em texto que guia a geração ("" esconde)' },
    passos: { tipo: 'inteiro', padrao: 5, min: 2, max: 8, descricao: 'quantos passos de remoção de ruído a cena mostra' },
    semente: { tipo: 'inteiro', padrao: 4, min: 0, descricao: 'semente do ruído inicial: a mesma semente dá sempre o mesmo ruído' },
  }, { titulo: 'Difusão' }),
};

export function roteiro(p, mov) {
  const d = mov.duracoes, K = p.passos || 5;
  return [
    { nome: 'ruido', tipo: 'entrada', anim: d.longa },
    { nome: 'pedido', tipo: 'texto', anim: d.media * 2 },
    ...Array.from({ length: K }, (_, i) => ({ nome: 'passo' + (i + 1), tipo: 'enfase', anim: d.longa + d.media, leitura: i === 0 ? 0.9 : 0.45 })),
    { nome: 'imagem', tipo: 'enfase', anim: d.media * 2 },
  ];
}

function legendasDe(K) {
  const meio = Array.from({ length: K }, (_, i) => (i === 0 ? 'A rede estima o ruído e *tira um pouco*' : i === K - 1 && K >= 3 ? 'Os detalhes aparecem por último' : 'De novo: menos ruído, mais forma'));
  return ['Tudo começa com *ruído* puro', 'O pedido em texto *guia* o processo', ...meio, 'Depois de vários passos, sobra a *imagem*'];
}

const ESTADOS = new WeakMap();

export function build(palco, p, ctx) {
  const linhas = p.imagem.map(String), cols = linhas[0].length, rows = linhas.length, K = p.passos, cor = p.cor;
  if (cols < 6 || cols > 24) throw new Error(`imagem: cada fileira precisa ter de 6 a 24 quadradinhos (a primeira tem ${cols})`);
  linhas.forEach((l, i) => {
    if (l.length !== cols) throw new Error(`imagem: a fileira ${i + 1} tem ${l.length} quadradinhos e a primeira tem ${cols} — todas precisam do mesmo tamanho`);
    for (const c of l) if (!(c in TINTAS) && !/[1-9]/.test(c)) throw new Error(`imagem: símbolo "${c}" na fileira ${i + 1} não existe (use . # o + = s d ou 1–9)`);
  });
  const tinta = (c) => (/[1-9]/.test(c) ? ctx.dado(+c - 1) : ctx.cor(TINTAS[c] || cor));
  const Q = montarQuadro(palco, p, ctx, { roteiro: roteiro(p, ctx.DA.movimento), legendas: legendasDe(K) });
  const C = Q.conteudo, P = Q.P;
  const camada = ctx.el('div', 'df-camada');
  Object.assign(camada.style, { position: 'absolute', left: '0', top: '0' });
  Q.raiz.appendChild(camada);
  const vao = ctx.px(0.04);

  // painel: pedido, passo k de K e o medidor de ruído
  const temPedido = !!(p.pedido && p.pedido.trim());
  const rotPedido = rotulo(ctx, 'pedido', { tam: ctx.tam('nota') });
  const pedido = ctx.texto('corpo', temPedido ? `“${p.pedido.trim()}”` : '', { tam: ctx.tam(Q.horizontal ? 'h2' : 'h3'), cor: 'texto', classe: 'df-pedido' });
  pedido.style.position = 'absolute';
  const conta = contador(ctx, { tam: ctx.tam(Q.horizontal ? 'h3' : 'corpo'), cor: 'texto', formato: (v) => `passo ${Math.round(v)} de ${K}`, modelo: `passo ${K} de ${K}` });
  const rotRuido = rotulo(ctx, 'ruído', { tam: ctx.tam('nota') });
  const valRuido = contador(ctx, { tam: ctx.tam('corpo'), cor: 'texto', formato: (v) => pct(v), modelo: '100%' });
  camada.append(rotPedido, pedido, conta.el, rotRuido, valRuido.el);
  const mRP = ctx.medir(rotPedido), mC = conta.medir(), mRR = ctx.medir(rotRuido), mVR = valRuido.medir();
  const lado0 = Q.horizontal ? Math.min(C.h, C.w * 0.5) : 0;
  const wPainel = Q.horizontal ? C.w - lado0 - vao * 1.4 : C.w;
  ctx.ajustar_texto(pedido, Q.horizontal ? wPainel : wPainel - mC.w - vao, { min: ctx.tam('corpo') });
  const mP = ctx.medir(pedido);
  const hMed = ctx.px(0.022);
  const hPainel = Q.horizontal
    ? (temPedido ? mRP.h + ctx.px(0.006) + mP.h + vao : 0) + mC.h + vao * 0.7 + mRR.h + ctx.px(0.01) + hMed
    : Math.max(temPedido ? mRP.h + ctx.px(0.004) + mP.h : 0, mC.h) + ctx.px(0.02) + Math.max(mRR.h, hMed);
  const lado = Q.horizontal ? lado0 : Math.min(C.w, C.h - hPainel - vao * 0.7);
  const cel = Math.floor(Math.min(lado / cols, lado / rows));
  const wG = cel * cols, hG = cel * rows;
  const gx = Q.horizontal ? C.x : C.x + (C.w - wG) / 2;
  const gy = Q.horizontal ? C.y + (C.h - hG) / 2 : C.y;
  const px = Q.horizontal ? gx + wG + vao * 1.4 : C.x;
  let py = Q.horizontal ? C.y + (C.h - hPainel) / 2 : gy + hG + vao * 0.7;
  if (Q.horizontal) {
    if (temPedido) { ctx.place(rotPedido, { x: Math.round(px), y: Math.round(py) }); py += mRP.h + ctx.px(0.006); ctx.place(pedido, { x: Math.round(px), y: Math.round(py) }); py += mP.h + vao; }
    ctx.place(conta.el, { x: Math.round(px), y: Math.round(py) }); py += mC.h + vao * 0.7;
  } else {
    const hTopo = Math.max(temPedido ? mRP.h + ctx.px(0.004) + mP.h : 0, mC.h);
    if (temPedido) { ctx.place(rotPedido, { x: Math.round(px), y: Math.round(py) }); ctx.place(pedido, { x: Math.round(px), y: Math.round(py + mRP.h + ctx.px(0.004)) }); }
    ctx.place(conta.el, { x: Math.round(C.x1 - mC.w), y: Math.round(py + hTopo - mC.h) });
    py += hTopo + ctx.px(0.02);
  }
  const wMed = Q.horizontal ? Math.min(wPainel, ctx.col(4)) - mVR.w - ctx.px(0.016) : wPainel - mRR.w - mVR.w - ctx.px(0.032);
  const medidor = barra(ctx, { w: wMed, h: hMed, cor, corBase: 'texto_suave' });
  camada.appendChild(medidor.el);
  if (Q.horizontal) {
    ctx.place(rotRuido, { x: Math.round(px), y: Math.round(py) }); py += mRR.h + ctx.px(0.01);
    ctx.place(medidor.el, { x: Math.round(px), y: Math.round(py) });
    ctx.place(valRuido.el, { x: Math.round(px + wMed + ctx.px(0.016)), y: Math.round(py + (hMed - mVR.h) / 2) });
  } else {
    const hL = Math.max(mRR.h, hMed);
    ctx.place(rotRuido, { x: Math.round(px), y: Math.round(py + (hL - mRR.h) / 2) });
    ctx.place(medidor.el, { x: Math.round(px + mRR.w + ctx.px(0.016)), y: Math.round(py + (hL - hMed) / 2) });
    ctx.place(valRuido.el, { x: Math.round(C.x1 - mVR.w), y: Math.round(py + (hL - mVR.h) / 2) });
  }

  // mosaico: a imagem embaixo, o ruído por cima
  const fresta = Math.max(1, Math.round(cel * 0.06));
  const mosaico = (classe, corDe) => {
    const g = ctx.el('div', classe);
    Object.assign(g.style, { position: 'absolute', left: '0', top: '0', width: wG + 'px', height: hG + 'px' });
    for (let i = 0; i < rows; i++) for (let j = 0; j < cols; j++) {
      const q = ctx.el('div');
      Object.assign(q.style, { position: 'absolute', left: j * cel + 'px', top: i * cel + 'px', width: (cel - fresta) + 'px', height: (cel - fresta) + 'px', background: corDe(i, j) });
      g.appendChild(q);
    }
    return g;
  };
  const quadro = ctx.el('div', 'df-quadro');
  Object.assign(quadro.style, { position: 'absolute', left: Math.round(gx) + 'px', top: Math.round(gy) + 'px', width: wG + 'px', height: hG + 'px' });
  const rng = ctx.rng(p.semente);
  const paleta = [...ctx.DA.cor.dados.map((_, i) => ctx.dado(i)), ctx.cor('texto'), ctx.cor('superficie'), ctx.cor('fundo')];
  const imagem = mosaico('df-imagem', (i, j) => tinta(linhas[i][j]));
  const ruido = mosaico('df-ruido', () => paleta[Math.floor(rng() * paleta.length)]);
  const varredura = ctx.el('div', 'df-varredura');
  Object.assign(varredura.style, { position: 'absolute', left: '0', top: '0', width: wG + 'px', height: Math.max(3, Math.round(cel * 0.18)) + 'px', background: ctx.cor(cor) });
  const aro = ctx.el('div', 'df-aro');
  const f = Math.max(4, ctx.px(0.008));
  Object.assign(aro.style, { position: 'absolute', left: -f + 'px', top: -f + 'px', width: (wG + 2 * f - fresta) + 'px', height: (hG + 2 * f - fresta) + 'px', border: `${Math.max(2, ctx.traco * 1.2).toFixed(1)}px solid ${ctx.cor(cor)}`, borderRadius: ctx.raio + 'px' });
  quadro.append(imagem, ruido, varredura, aro);
  camada.appendChild(quadro);

  guardar(ESTADOS, ctx, { ctx, Q, P, K, quadro, imagem, ruido, varredura, aro, hG, rotPedido, pedido, conta, rotRuido, valRuido, medidor, temPedido, nPedido: (p.pedido || '').length + 2 });
  return Q.layout({ passos_de_difusao: K, mosaico: { x: Math.round(gx), y: Math.round(gy), w: wG, h: hG, colunas: cols, fileiras: rows, quadradinho: cel },
    painel: { x: Math.round(px), w: Math.round(wPainel), h: Math.round(hPainel) } });
}

export function seek(t, ctxArg) {
  const { ctx, Q, P, K, quadro, imagem, ruido, varredura, aro, hG, rotPedido, pedido, conta, rotRuido, valRuido, medidor, temPedido, nPedido } = ler(ESTADOS, ctxArg);
  const d = ctx.DA.movimento.duracoes;
  const anim = d.longa + d.media;
  // nível de ruído: cai um degrau por passo, depois da "leitura" da rede (a varredura)
  let feitos = 0, varre = -1;
  for (let i = 1; i <= K; i++) {
    feitos += clamp(P.prog(t, 'passo' + i, anim * 0.45, anim * 0.55, 'suave'));
    const pv = P.lin(t, 'passo' + i, 0, anim * 0.5);
    if (pv > 0 && pv < 1) varre = pv;
  }
  const sigma = 1 - feitos / K;
  ctx.entrada(quadro, P.prog(t, 'ruido', 0, d.longa, 'suave'), 'mascara', { origem: 'cima' });
  imagem.style.opacity = P.passou(t, 'passo1') ? '1' : '0';
  ruido.style.opacity = clamp(sigma).toFixed(3);
  varredura.style.opacity = varre < 0 ? '0' : Math.min(1, 4 * varre * (1 - varre) + 0.25).toFixed(3);
  varredura.style.transform = `translateY(${(Math.max(0, varre) * (hG - 4)).toFixed(2)}px)`;
  const pFim = P.prog(t, 'imagem', 0, d.media, 'enfase');
  aro.style.opacity = clamp(pFim).toFixed(3);
  aro.style.transform = `scale(${(1.04 - 0.04 * clamp(pFim, 0, 1.2)).toFixed(4)})`;
  // painel
  if (temPedido) { ctx.entrada(rotPedido, P.prog(t, 'pedido', 0, d.curta), 'fade'); ctx.entrada(pedido, P.prog(t, 'pedido', 0, d.media * 1.5), undefined, { n: nPedido }); }
  else { ctx.entrada(rotPedido, 0, 'fade'); ctx.entrada(pedido, 0, 'fade'); }
  const pPainel = P.prog(t, 'pedido', d.media, d.media);
  ctx.entrada(conta.el, pPainel, 'fade');
  conta.definir(Math.floor(feitos + 0.02));
  ctx.entrada(rotRuido, pPainel, 'fade');
  ctx.entrada(valRuido.el, pPainel, 'fade');
  valRuido.definir(sigma);
  medidor.el.style.opacity = clamp(pPainel).toFixed(3);
  medidor.estado({ fracao: clamp(sigma), realce: 0, trilha: 1 });
  Q.seek(t);
}

export function key(t, ctx) { return ler(ESTADOS, ctx).P.chave(t); }

export function ancoras(ctx) { return ler(ESTADOS, ctx).P.ancoras(); }
