// rede_neural.js — camadas, pesos, a conta de um neurônio e o sinal se propagando até a saída.
// Passos: camadas → pesos → entrada → neuronio → propaga → saida.
// A conta é feita DE VERDADE (soma ponderada + função de ativação) com os pesos mostrados: os números da tabela e
// os brilhos dos neurônios saem do mesmo cálculo. Simplificação declarada em references/didatica.md: rede minúscula,
// sem viés, a mesma ativação em todas as camadas; pesos sorteados para o exemplo (selo "ilustrativo").
import { params, guardar, ler, montarQuadro, no, rotulo, textoDuplo, camadaSvg, linha, ATIVACOES, clamp, num, indiceDoMaior } from './_ia.js';

export const meta = {
  nome: 'rede_neural',
  descricao: 'Rede neural: neurônios em camadas ligados por pesos; um neurônio soma as entradas pesadas e aplica a ativação; o sinal avança camada por camada até a saída.',
  dur_padrao: 14,
  formatos: ['horizontal', 'vertical', 'quadrado'],
  alfa_padrao: false,
  grao: true,
  params: params({
    camadas: { tipo: 'lista', min: 2, max: 5, itens: { tipo: 'inteiro', min: 1, max: 6 }, padrao: [3, 4, 4, 2], descricao: 'neurônios por camada, da entrada à saída (até 5 camadas de até 6 neurônios)' },
    entradas: { tipo: 'lista', padrao: null, itens: { tipo: 'numero' }, descricao: 'valor de cada neurônio de entrada (padrão: valores de exemplo)' },
    pesos: { tipo: 'lista', padrao: null,
      descricao: 'pesos reais: uma matriz por par de camadas, [neurônio de destino][neurônio de origem]. Sem eles a cena sorteia pesos de exemplo com `semente` e exige ilustrativo=true' },
    ativacao: { tipo: 'opcao', opcoes: ['relu', 'sigmoide', 'tanh'], padrao: 'relu', descricao: 'função de ativação aplicada depois da soma' },
    foco: { tipo: 'inteiro', padrao: 0, min: 0, descricao: 'índice do neurônio da 2ª camada cuja conta é aberta na tabela' },
    rotulos_saida: { tipo: 'lista', padrao: null, itens: { tipo: 'texto' }, descricao: 'nome de cada neurônio de saída (opcional)' },
    semente: { tipo: 'inteiro', padrao: 1844, min: 0, descricao: 'semente dos pesos (e das entradas) de exemplo' },
  }, { titulo: 'Rede neural' }),
};

const LEGENDAS = ['Neurônios organizados em *camadas*', 'Cada ligação tem um *peso*', 'Os números de entrada chegam', 'Um neurônio *soma* as entradas pesadas', 'O sinal avança *camada por camada*', 'A saída é o resultado de muitas somas'];

export function roteiro(p, mov) {
  const d = mov.duracoes, e = mov.escalonamento;
  const camadas = p.camadas || [3, 4, 4, 2];
  const L = camadas.length, maior = Math.max(...camadas);
  return [
    { nome: 'camadas', tipo: 'entrada', anim: d.media + (L - 1) * d.media * 0.5 + maior * e },
    { nome: 'pesos', tipo: 'texto', anim: d.media + (L - 1) * d.media * 0.6 + d.curta },
    { nome: 'entrada', tipo: 'texto', anim: d.media + camadas[0] * e * 2 },
    { nome: 'neuronio', tipo: 'enfase', anim: d.media * 3 + camadas[0] * e * 3 },
    { nome: 'propaga', tipo: 'enfase', anim: (L - 1) * d.media * 1.6 + d.media },
    { nome: 'saida', tipo: 'enfase', anim: d.media * 2 },
  ];
}

/** Entradas, pesos e a passagem para a frente. Pura: recebe o gerador (ctx.rng no motor). */
export function calcular(p, rngDe) {
  const camadas = p.camadas, L = camadas.length;
  const rng = rngDe(p.semente);
  const umaCasa = () => { const v = Math.round((rng() * 1.8 - 0.9) * 10) / 10; return v === 0 ? 0.1 : v; };
  let entradas = p.entradas;
  if (entradas && entradas.length !== camadas[0]) throw new Error(`entradas tem ${entradas.length} valor(es) e a 1ª camada tem ${camadas[0]} neurônio(s)`);
  const exemplo = [0.9, 0.2, 0.6, 0.4, 0.8, 0.1];
  if (!entradas) entradas = exemplo.slice(0, camadas[0]);
  let W = p.pesos;
  const sorteados = !W;
  if (W) {
    if (W.length !== L - 1) throw new Error(`pesos tem ${W.length} matriz(es); com ${L} camadas são ${L - 1} (uma por par de camadas vizinhas)`);
    W.forEach((m, l) => {
      if (!Array.isArray(m) || m.length !== camadas[l + 1] || m.some((linhaW) => !Array.isArray(linhaW) || linhaW.length !== camadas[l] || linhaW.some((v) => typeof v !== 'number' || !Number.isFinite(v)))) {
        throw new Error(`pesos[${l}]: esperava ${camadas[l + 1]} linha(s) (neurônios da camada ${l + 2}) com ${camadas[l]} número(s) cada (neurônios da camada ${l + 1})`);
      }
    });
  } else {
    W = [];
    for (let l = 0; l < L - 1; l++) W.push(Array.from({ length: camadas[l + 1] }, () => Array.from({ length: camadas[l] }, umaCasa)));
  }
  const f = ATIVACOES[p.ativacao || 'relu'].f;
  const A = [entradas.slice()], Z = [null];
  for (let l = 0; l < L - 1; l++) {
    const z = W[l].map((linhaW) => linhaW.reduce((s, w, i) => s + w * A[l][i], 0));
    Z.push(z); A.push(z.map(f));
  }
  return { camadas, entradas, W, A, Z, sorteados };
}

const ESTADOS = new WeakMap();

export function build(palco, p, ctx) {
  const R = calcular(p, ctx.rng);
  if (R.sorteados && p.ilustrativo === false) throw new Error('faltou "pesos": com ilustrativo=false a cena não sorteia pesos — passe as matrizes reais (e a fonte)');
  const { camadas, W, A, Z } = R;
  const L = camadas.length;
  if (p.foco >= camadas[1]) throw new Error(`foco = ${p.foco}, mas a 2ª camada tem ${camadas[1]} neurônio(s) (índices de 0 a ${camadas[1] - 1})`);
  if (p.rotulos_saida && p.rotulos_saida.length !== camadas[L - 1]) throw new Error(`rotulos_saida tem ${p.rotulos_saida.length} nome(s) e a saída tem ${camadas[L - 1]} neurônio(s)`);
  const Q = montarQuadro(palco, p, ctx, { roteiro: roteiro(p, ctx.DA.movimento), legendas: LEGENDAS });
  const C = Q.conteudo, P = Q.P, cor = p.cor;
  const camada = ctx.el('div', 'rn-camada');
  Object.assign(camada.style, { position: 'absolute', left: '0', top: '0' });
  Q.raiz.appendChild(camada);
  const vao = ctx.px(0.04);
  const casas = R.sorteados ? 1 : 2;

  // tabela: a conta do neurônio em foco (entrada × peso, soma, ativação)
  const nIn = camadas[0];
  let tamT = ctx.tam(Q.horizontal ? 'h3' : 'corpo');
  if (!Q.horizontal) {                                       // empilhado: a tabela não pode tomar mais que ~45% da altura — a rede é a protagonista
    const estimada = (nIn + 2) * tamT * 1.4 + 2 * ctx.tam('nota') * 1.5 + ctx.px(0.03);
    if (estimada > C.h * 0.45) tamT = Math.max(ctx.tam('nota'), tamT * (C.h * 0.45) / estimada);
  }
  const larg = 13;
  const linhasT = [];
  for (let i = 0; i < nIn; i++) linhasT.push({ txt: `${num(A[0][i], 2).padStart(5)} × ${num(W[0][p.foco][i], casas).padStart(5)}`, cor: 'texto' });
  linhasT.push({ txt: 'soma'.padEnd(larg - 6) + num(Z[1][p.foco], 2).padStart(6), cor: 'texto', regua: true });
  linhasT.push({ txt: ATIVACOES[p.ativacao].nome.padEnd(larg - 6) + num(A[1][p.foco], 2).padStart(6), cor });
  const tituloT = rotulo(ctx, 'a conta de um neurônio', { tam: ctx.tam('nota') });
  const cabT = rotulo(ctx, 'entrada × peso', { tam: ctx.tam('nota') });
  camada.append(tituloT, cabT);
  const mTit = ctx.medir(tituloT), mCab = ctx.medir(cabT);
  const tabela = linhasT.map((l) => { const e = ctx.texto('dados', l.txt, { tam: tamT, cor: l.cor, classe: 'rn-linha' }); e._inner.style.whiteSpace = 'pre'; e.style.position = 'absolute'; camada.appendChild(e); return { e, m: ctx.medir(e), regua: l.regua }; });
  const hLinha = tabela[0].m.h * 1.08;
  const wTab = Math.max(...tabela.map((x) => x.m.w), mTit.w, mCab.w);
  const hTab = mTit.h + ctx.px(0.01) + mCab.h + ctx.px(0.006) + linhasT.length * hLinha + ctx.px(0.012);

  // regiões
  const rede = Q.horizontal ? { x: C.x, y: C.y, w: C.w - wTab - vao * 1.5, h: C.h } : { x: C.x, y: C.y, w: C.w, h: C.h - hTab - vao * 0.8 };
  const xTab = Q.horizontal ? C.x1 - wTab : C.x, yTab = Q.horizontal ? C.y + (C.h - hTab) / 2 : rede.y + rede.h + vao * 0.8;
  let y = yTab;
  ctx.place(tituloT, { x: Math.round(xTab), y: Math.round(y) }); y += mTit.h + ctx.px(0.01);
  ctx.place(cabT, { x: Math.round(xTab), y: Math.round(y) }); y += mCab.h + ctx.px(0.006);
  const fio = ctx.el('div', 'rn-regua');
  tabela.forEach((x) => {
    if (x.regua) {
      Object.assign(fio.style, { position: 'absolute', left: Math.round(xTab) + 'px', top: Math.round(y + ctx.px(0.004)) + 'px', width: Math.round(tabela[0].m.w) + 'px', height: Math.max(1, ctx.traco * 0.75).toFixed(1) + 'px',
        background: ctx.cor('texto_suave'), transformOrigin: 'left center' });
      camada.appendChild(fio);
      y += ctx.px(0.012);
    }
    ctx.place(x.e, { x: Math.round(xTab), y: Math.round(y) });
    y += hLinha;
  });

  // rede: colunas de neurônios, rótulos das camadas, valores de entrada e de saída
  const nomesCamada = camadas.map((_, l) => (l === 0 ? 'entrada' : l === L - 1 ? 'saída' : L === 3 ? 'oculta' : `oculta ${l}`));
  let cabs = nomesCamada.map((nome) => { const e = rotulo(ctx, nome, { tam: ctx.tam('nota') }); camada.appendChild(e); return { e, m: ctx.medir(e) }; });
  const hCab = cabs[0].m.h + ctx.px(0.016);
  const tamVal = Math.max(ctx.tam('nota'), ctx.tam('corpo') * (Q.horizontal ? 1 : 0.85));
  const valIn = A[0].map((v) => { const e = rotulo(ctx, num(v, 2), { tam: tamVal, cor: 'texto' }); camada.appendChild(e); return { e, m: ctx.medir(e) }; });
  const iMaior = indiceDoMaior(A[L - 1]);
  const valOut = A[L - 1].map((v, j) => { const t = textoDuplo(ctx, 'dados', (p.rotulos_saida ? p.rotulos_saida[j] + ' ' : '') + num(v, 2), { tam: tamVal, corA: 'texto', corB: cor, classe: 'rn-saida' }); camada.appendChild(t.el); t.medir(); return t; });
  const maiorN = Math.max(...camadas);
  const folgaE = Math.max(...valIn.map((v) => v.m.w)) + ctx.px(0.016), folgaD = Math.max(...valOut.map((v) => v.w)) + ctx.px(0.016);
  const hRede = rede.h - hCab;
  const r = Math.max(8, Math.min(ctx.px(0.036), hRede / (maiorN * 2.9), (rede.w - folgaE - folgaD) / ((L - 1) * 5.2)));
  const passoY = Math.min(r * 3.3, hRede / maiorN);
  // valores ao lado dos neurônios: se a fileira ficou baixa, a letra acompanha (nunca abaixo de `nota`)
  const tamCabe = Math.max(ctx.tam('nota'), Math.min(tamVal, passoY / 1.35));
  if (tamCabe < tamVal - 0.5) {
    for (const v of valIn) { v.e._inner.style.fontSize = tamCabe.toFixed(2) + 'px'; v.m = ctx.medir(v.e); }
    for (const v of valOut) { v.a._inner.style.fontSize = tamCabe.toFixed(2) + 'px'; v.b._inner.style.fontSize = tamCabe.toFixed(2) + 'px'; v.medir(); }
  }
  const hUsada = hCab + maiorN * passoY;
  const yBase = rede.y + Math.max(0, (rede.h - hUsada) / 2);
  const xCol = (l) => rede.x + folgaE + r + (l * (rede.w - folgaE - folgaD - 2 * r)) / (L - 1);
  const yNo = (l, i) => yBase + hCab + (maiorN * passoY) / 2 + (i - (camadas[l] - 1) / 2) * passoY;
  const svg = camadaSvg(ctx, camada);
  const maxW = Math.max(...W.flat(2).map(Math.abs), 1e-9);
  const maxA = Math.max(...A.flat().map(Math.abs), 1e-9);
  const fios = [];
  for (let l = 0; l < L - 1; l++) {
    const maxSinal = Math.max(...W[l].flatMap((linhaW) => linhaW.map((w, i) => Math.abs(w * A[l][i]))), 1e-9);
    for (let j = 0; j < camadas[l + 1]; j++) for (let i = 0; i < camadas[l]; i++) {
      const w = W[l][j][i], forca = Math.abs(w) / maxW;
      const x1 = xCol(l) + r, y1 = yNo(l, i), x2 = xCol(l + 1) - r, y2 = yNo(l + 1, j);
      const esp = ctx.traco * (0.6 + 1.8 * forca);
      const tracejado = w < 0 ? `${(esp * 2.2).toFixed(1)} ${(esp * 2.6).toFixed(1)}` : null;
      const base = linha(ctx, svg, x1, y1, x2, y2, { cor: 'texto_suave', esp, alfa: 0.22 + 0.6 * forca, tracejado });
      const pulso = linha(ctx, svg, x1, y1, x2, y2, { cor, esp: esp * 1.25, alfa: 0.25 + 0.75 * Math.abs(w * A[l][i]) / maxSinal, tracejado });
      fios.push({ l, i, j, base, pulso, ordem: fios.length });
    }
  }
  const nos = camadas.map((qtd, l) => Array.from({ length: qtd }, (_, i) => { const n = no(ctx, { r, cor }); camada.appendChild(n.el); n.em(xCol(l), yNo(l, i)); return n; }));
  // rótulos das camadas: se não cabem lado a lado (rede estreita, letra grande), ficam só "entrada" e "saída"
  const vaoCol = xCol(1) - xCol(0);
  const apertados = Math.max(...cabs.map((c) => c.m.w)) > vaoCol * 0.92;
  cabs.forEach((c, l) => { c.l = l; if (apertados && l > 0 && l < L - 1) { c.e.remove(); c.fora = true; } });
  cabs = cabs.filter((c) => !c.fora);
  cabs.forEach((c) => {
    const x = c.l === 0 ? Math.max(rede.x, xCol(0) - c.m.w / 2) : c.l === L - 1 ? Math.min(rede.x + rede.w - c.m.w, xCol(L - 1) - c.m.w / 2) : xCol(c.l) - c.m.w / 2;
    ctx.place(c.e, { x: Math.round(x), y: Math.round(yBase) });
  });
  valIn.forEach((v, i) => ctx.place(v.e, { x: Math.round(xCol(0) - r - ctx.px(0.016) - v.m.w), y: Math.round(yNo(0, i) - v.m.h / 2) }));
  valOut.forEach((v, j) => ctx.place(v.el, { x: Math.round(xCol(L - 1) + r + ctx.px(0.016)), y: Math.round(yNo(L - 1, j) - v.h / 2) }));

  guardar(ESTADOS, ctx, { ctx, Q, P, p, L, camadas, A, maxA, nos, fios, cabs, valIn, valOut, iMaior, tabela, fio, tituloT, cabT, nIn });
  return Q.layout({ camadas, foco: p.foco, soma_foco: +Z[1][p.foco].toFixed(4), ativacao_foco: +A[1][p.foco].toFixed(4), saida: A[L - 1].map((v) => +v.toFixed(4)), pesos_sorteados: R.sorteados,
    raio_no: +r.toFixed(1), passo_no: +passoY.toFixed(1), rotulos_de_camada: cabs.length, rede: { x: Math.round(rede.x), y: Math.round(rede.y), w: Math.round(rede.w), h: Math.round(rede.h) }, tabela: { x: Math.round(xTab), y: Math.round(yTab), w: Math.round(wTab), h: Math.round(hTab) } });
}

export function seek(t, ctxArg) {
  const { ctx, Q, P, p, L, camadas, A, maxA, nos, fios, cabs, valIn, valOut, iMaior, tabela, fio, tituloT, cabT, nIn } = ler(ESTADOS, ctxArg);
  const d = ctx.DA.movimento.duracoes, e = ctx.escalonamento;
  const pSaida = P.prog(t, 'saida', 0, d.media, 'enfase');
  // quando o neurônio (l, i) recebe o valor dele
  const carga = (l, i) => {
    if (l === 0) return P.prog(t, 'entrada', i * e * 2, d.media);
    if (l === 1 && i === p.foco) return P.prog(t, 'neuronio', d.media, d.media);
    return P.prog(t, 'propaga', (l - 1) * d.media * 1.6 + d.media * 0.8, d.media);
  };
  nos.forEach((col, l) => col.forEach((n, i) => {
    ctx.entrada(n.el, P.prog(t, 'camadas', l * d.media * 0.5 + i * e, d.media), 'escala');
    const foco = l === 1 && i === p.foco, maior = l === L - 1 && i === iMaior;
    n.estado({ ativacao: (Math.abs(A[l][i]) / maxA) * clamp(carga(l, i)),
      realce: foco ? clamp(P.prog(t, 'neuronio', 0, d.media, 'enfase')) * (1 - clamp(pSaida)) : maior ? clamp(pSaida) : 0 });
  }));
  cabs.forEach((c) => ctx.entrada(c.e, P.prog(t, 'camadas', c.l * d.media * 0.5, d.media), 'fade'));
  for (const f of fios) {
    f.base.tracar(P.prog(t, 'pesos', f.l * d.media * 0.6 + (f.ordem % 12) * e * 0.25, d.media, 'suave'));
    const pp = f.l === 0 && f.j === p.foco ? P.prog(t, 'neuronio', 0, d.media, 'suave') : P.prog(t, 'propaga', f.l * d.media * 1.6, d.media, 'suave');
    f.pulso.tracar(pp);
  }
  valIn.forEach((v, i) => ctx.entrada(v.e, P.prog(t, 'entrada', i * e * 2, d.media), 'fade'));
  valOut.forEach((v, j) => { ctx.entrada(v.el, P.prog(t, 'saida', j * e * 2, d.media), 'fade'); v.misturar(j === iMaior ? pSaida : 0); });
  // tabela do neurônio em foco
  ctx.entrada(tituloT, P.prog(t, 'neuronio', 0, d.curta), 'fade');
  ctx.entrada(cabT, P.prog(t, 'neuronio', d.curta * 0.5, d.curta), 'fade');
  tabela.forEach((x, i) => {
    const atraso = i < nIn ? d.curta + i * e * 3 : d.media + nIn * e * 3 + (i - nIn) * d.media * 0.8;
    ctx.entrada(x.e, P.prog(t, 'neuronio', atraso, d.media), undefined, { n: 13 });
  });
  const pf = P.prog(t, 'neuronio', d.media + nIn * e * 3 - d.curta * 0.5, d.media, 'suave');
  fio.style.transform = `scaleX(${clamp(pf).toFixed(4)})`;
  fio.style.opacity = pf > 0 ? '1' : '0';
  Q.seek(t);
}

export function key(t, ctx) { return ler(ESTADOS, ctx).P.chave(t); }

export function ancoras(ctx) { return ler(ESTADOS, ctx).P.ancoras(); }
