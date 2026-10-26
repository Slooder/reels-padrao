// embeddings.js — palavras como pontos num plano; vizinhança semântica; o vetor de uma palavra.
// Passos: plano → pontos → vizinhanca → vetor.
// Simplificação declarada em references/didatica.md: o plano é uma PROJEÇÃO em 2 dimensões de um espaço que, nos
// modelos reais, tem centenas ou milhares; os eixos não têm significado legível; posições do exemplo são inventadas.
import { params, guardar, ler, montarQuadro, rotulo, textoDuplo, camadaSvg, linha, seta, eixo, clamp, num } from './_ia.js';

const EXEMPLO = {
  pontos: [
    { rotulo: 'gato', x: -0.58, y: 0.5 }, { rotulo: 'cachorro', x: -0.32, y: 0.72 }, { rotulo: 'leão', x: -0.74, y: 0.2 },
    { rotulo: 'maçã', x: 0.5, y: 0.56 }, { rotulo: 'banana', x: 0.7, y: 0.3 }, { rotulo: 'uva', x: 0.34, y: 0.82 },
    { rotulo: 'carro', x: 0.12, y: -0.5 }, { rotulo: 'ônibus', x: 0.42, y: -0.72 }, { rotulo: 'bicicleta', x: -0.2, y: -0.76 },
  ],
  vetor: [0.21, -0.53, 0.8, 0.07, -0.31],
};

export const meta = {
  nome: 'embeddings',
  descricao: 'Embeddings: cada palavra vira um ponto num plano, significados parecidos ficam perto e, para o modelo, a palavra é uma lista de números (o vetor).',
  dur_padrao: 10,
  formatos: ['horizontal', 'vertical', 'quadrado'],
  alfa_padrao: false,
  grao: true,
  params: params({
    pontos: { tipo: 'lista', min: 3, max: 16, padrao: EXEMPLO.pontos, descricao: 'palavras e a posição de cada uma no plano (x e y entre −1 e 1; y cresce para cima)',
      itens: { tipo: 'objeto', campos: { rotulo: { tipo: 'texto', obrigatorio: true }, x: { tipo: 'numero', obrigatorio: true, min: -1, max: 1 }, y: { tipo: 'numero', obrigatorio: true, min: -1, max: 1 } } } },
    destaque: { tipo: 'texto', padrao: null, descricao: 'rótulo da palavra explicada (padrão: a primeira da lista)' },
    vizinhos: { tipo: 'inteiro', padrao: 2, min: 1, max: 5, descricao: 'quantas palavras mais próximas entram na vizinhança' },
    vetor: { tipo: 'lista', padrao: null, min: 2, max: 6, itens: { tipo: 'numero' }, descricao: 'primeiros números do vetor da palavra em destaque (padrão: as duas coordenadas do plano)' },
    dimensoes: { tipo: 'inteiro', padrao: null, min: 2, descricao: 'tamanho real do vetor no modelo citado (é dado de modelo: exige fonte e fato_ids); sem ele o texto diz "centenas ou milhares"' },
  }, { titulo: 'Embeddings' }),
};

const LEGENDAS = ['Um mapa de palavras', 'Cada palavra vira um *ponto*', 'Significados parecidos ficam *perto*', 'A palavra vira uma *lista de números*'];

export function roteiro(p, mov) {
  const d = mov.duracoes, e = mov.escalonamento, n = (p.pontos || EXEMPLO.pontos).length;
  return [
    { nome: 'plano', tipo: 'entrada', anim: d.longa },
    { nome: 'pontos', tipo: 'texto', anim: d.media + d.curta + n * e * 2 },
    { nome: 'vizinhanca', tipo: 'enfase', anim: d.longa + d.media },
    { nome: 'vetor', tipo: 'enfase', anim: d.longa + d.media },
  ];
}

const ESTADOS = new WeakMap();
const cruza = (a, b) => a.x < b.x1 && b.x < a.x1 && a.y < b.y1 && b.y < a.y1;

export function build(palco, p, ctx) {
  const pontos = p.pontos.map((q) => ({ rotulo: String(q.rotulo), x: q.x, y: q.y }));
  const nomes = pontos.map((q) => q.rotulo);
  if (new Set(nomes).size !== nomes.length) throw new Error('pontos: há rótulos repetidos — cada palavra aparece uma vez');
  const padrao = p.pontos.length === EXEMPLO.pontos.length && p.pontos.every((q, i) => q.rotulo === EXEMPLO.pontos[i].rotulo);
  const iDest = p.destaque == null ? 0 : nomes.indexOf(p.destaque);
  if (iDest < 0) throw new Error(`destaque "${p.destaque}" não está em pontos (${nomes.join(', ')})`);
  const k = Math.min(p.vizinhos, pontos.length - 1);
  const dist = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);
  const ordem = pontos.map((q, i) => i).filter((i) => i !== iDest).sort((a, b) => dist(pontos[a], pontos[iDest]) - dist(pontos[b], pontos[iDest]));
  const viz = ordem.slice(0, k);
  let vetor = p.vetor || (padrao && iDest === 0 ? EXEMPLO.vetor : null);
  const soCoordenadas = !vetor;
  if (!vetor) vetor = [pontos[iDest].x, pontos[iDest].y];

  const Q = montarQuadro(palco, p, ctx, { roteiro: roteiro(p, ctx.DA.movimento), legendas: LEGENDAS });
  const C = Q.conteudo, P = Q.P, cor = p.cor;
  const camada = ctx.el('div', 'emb-camada');
  Object.assign(camada.style, { position: 'absolute', left: '0', top: '0' });
  Q.raiz.appendChild(camada);

  // geometria: plano quadrado; painel ao lado (horizontal) ou embaixo (vertical)
  const vao = ctx.px(0.04);
  let lado = Q.horizontal ? Math.min(C.h, C.w * 0.52) : 0;
  const wPainel = Q.horizontal ? C.w - lado - vao : C.w;

  // painel do vetor: a palavra, a lista de números e a nota de quantos números são.
  // Horizontal: empilhado ao lado do plano. Vertical: palavra e lista na mesma linha, embaixo do plano (a altura é curta).
  const mostrados = Q.horizontal ? vetor : vetor.slice(0, 3);
  const palavra = ctx.texto('titulo', pontos[iDest].rotulo, { tam: ctx.tam(Q.horizontal ? 'h1' : 'h3'), cor, classe: 'emb-palavra' });
  const lista = ctx.texto('dados', `[ ${mostrados.map((v) => num(v, 2)).join('  ')}  … ]`, { tam: ctx.tam(Q.horizontal ? 'h2' : 'corpo'), cor: 'texto', wrap: Q.horizontal, maxW: wPainel, classe: 'emb-vetor' });
  const textoNota = p.dimensoes ? `${num(p.dimensoes, 0)} números no total` : (soCoordenadas ? 'aqui, só as 2 coordenadas do mapa; no modelo, centenas ou milhares' : 'no modelo, centenas ou milhares de números');
  const nota = ctx.texto('dados', textoNota, { tam: ctx.tam(Q.horizontal ? 'corpo' : 'nota'), cor: 'texto_suave', wrap: true, maxW: wPainel, classe: 'emb-nota' });
  for (const e of [palavra, lista, nota]) { e.style.position = 'absolute'; camada.appendChild(e); }
  ctx.ajustar_texto(palavra, Q.horizontal ? wPainel : wPainel * 0.42, { min: ctx.tam('corpo') });
  const mP = ctx.medir(palavra);
  const vaoLinha = ctx.px(0.018);
  const wLista = Q.horizontal ? wPainel : wPainel - mP.w - vaoLinha;
  ctx.ajustar_texto(lista, wLista, { min: ctx.tam('nota'), maxLinhas: Q.horizontal ? 2 : 1 });
  ctx.ajustar_texto(nota, wPainel, { min: ctx.tam('nota'), maxLinhas: 2 });
  const mL = ctx.medir(lista), mN = ctx.medir(nota);
  const hLinha = Q.horizontal ? mP.h + ctx.px(0.016) + mL.h : Math.max(mP.h, mL.h);
  const hPainel = hLinha + ctx.px(0.014) + mN.h;
  if (!Q.horizontal) lado = Math.min(C.w, C.h - hPainel - vao * 0.6);
  const plano = Q.horizontal ? { x: C.x, y: C.y + (C.h - lado) / 2 } : { x: C.x + (C.w - lado) / 2, y: C.y };
  const painel = Q.horizontal ? { x: plano.x + lado + vao, y: C.y + (C.h - hPainel) / 2 } : { x: C.x, y: plano.y + lado + vao * 0.6 };
  ctx.place(palavra, { x: Math.round(painel.x), y: Math.round(painel.y + (Q.horizontal ? 0 : (hLinha - mP.h) / 2)) });
  if (Q.horizontal) ctx.place(lista, { x: Math.round(painel.x), y: Math.round(painel.y + mP.h + ctx.px(0.016)) });
  else ctx.place(lista, { x: Math.round(painel.x + mP.w + vaoLinha), y: Math.round(painel.y + (hLinha - mL.h) / 2) });
  ctx.place(nota, { x: Math.round(painel.x), y: Math.round(painel.y + hLinha + ctx.px(0.014)) });

  // plano: fundo, grade, eixos e a nota "projeção em 2 dimensões"
  const g = ctx.DA.graficos.dados;
  const fundo = ctx.el('div', 'emb-plano');
  Object.assign(fundo.style, { position: 'absolute', left: plano.x + 'px', top: plano.y + 'px', width: lado + 'px', height: lado + 'px', background: ctx.alfa('superficie', 0.55), borderRadius: ctx.raio + 'px' });
  camada.appendChild(fundo);
  const svg = camadaSvg(ctx, camada);
  const grade = [];
  for (let i = 1; i < 6; i++) {
    if (i === 3) continue;
    const q = (i / 6) * lado;
    grade.push(linha(ctx, svg, plano.x + q, plano.y, plano.x + q, plano.y + lado, { cor: g.grade, esp: Math.max(1, ctx.traco * 0.5) }));
    grade.push(linha(ctx, svg, plano.x, plano.y + q, plano.x + lado, plano.y + q, { cor: g.grade, esp: Math.max(1, ctx.traco * 0.5) }));
  }
  const cx = plano.x + lado / 2, cy = plano.y + lado / 2;
  const eixoX = eixo(ctx, svg, plano.x, cy, plano.x + lado, cy);
  const eixoY = eixo(ctx, svg, cx, plano.y + lado, cx, plano.y);
  const notaPlano = rotulo(ctx, 'projeção em 2 dimensões', { tam: ctx.tam('nota') });
  camada.appendChild(notaPlano);
  const mNP = ctx.medir(notaPlano);
  ctx.place(notaPlano, { x: Math.round(plano.x + lado - mNP.w - ctx.px(0.012)), y: Math.round(plano.y + lado - mNP.h - ctx.px(0.008)) });

  // pontos e rótulos (o rótulo procura um lado livre: direita, esquerda, cima, baixo)
  const r = Math.max(5, ctx.px(0.0095));
  const folga = lado * 0.07;
  const pos = (q) => ({ x: plano.x + folga + ((q.x + 1) / 2) * (lado - 2 * folga), y: plano.y + folga + ((1 - q.y) / 2) * (lado - 2 * folga) });
  const tamRot = Math.max(ctx.tam('nota'), Math.min(ctx.tam('corpo'), lado * 0.052));
  const ocupados = [{ x: plano.x + lado - mNP.w - ctx.px(0.02), y: plano.y + lado - mNP.h - ctx.px(0.012), x1: plano.x + lado, y1: plano.y + lado }];
  const itens = pontos.map((q, i) => {
    const c = pos(q);
    ocupados.push({ x: c.x - r * 1.6, y: c.y - r * 1.6, x1: c.x + r * 1.6, y1: c.y + r * 1.6 });
    const base = ctx.el('div', 'emb-ponto');
    Object.assign(base.style, { position: 'absolute', left: (c.x - r).toFixed(1) + 'px', top: (c.y - r).toFixed(1) + 'px', width: 2 * r + 'px', height: 2 * r + 'px' });
    const neutro = ctx.el('div'); Object.assign(neutro.style, { position: 'absolute', inset: '0', borderRadius: '50%', background: ctx.cor('texto') });
    const vivo = ctx.el('div'); Object.assign(vivo.style, { position: 'absolute', inset: '0', borderRadius: '50%', background: ctx.cor(cor), opacity: '0' });
    base.append(neutro, vivo);
    camada.appendChild(base);
    const t = textoDuplo(ctx, 'dados', q.rotulo, { tam: tamRot, corA: 'texto', corB: cor, classe: 'emb-rotulo' });
    camada.appendChild(t.el);
    return { q, i, c, base, vivo, t };
  });
  for (const it of itens) {
    const m = it.t.medir();
    const d = r * 1.9;
    const opcoes = [{ x: it.c.x + d, y: it.c.y - m.h / 2 }, { x: it.c.x - d - m.w, y: it.c.y - m.h / 2 }, { x: it.c.x - m.w / 2, y: it.c.y - d - m.h }, { x: it.c.x - m.w / 2, y: it.c.y + d }];
    let escolhida = null;
    for (const o of opcoes) {
      const caixa = { x: o.x, y: o.y, x1: o.x + m.w, y1: o.y + m.h };
      const dentro = caixa.x >= plano.x + 2 && caixa.x1 <= plano.x + lado - 2 && caixa.y >= plano.y + 2 && caixa.y1 <= plano.y + lado - 2;
      if (dentro && !ocupados.some((b) => cruza(caixa, b))) { escolhida = caixa; break; }
    }
    if (!escolhida) { const o = opcoes[it.c.x > cx ? 1 : 0]; escolhida = { x: o.x, y: o.y, x1: o.x + m.w, y1: o.y + m.h }; }
    ocupados.push(escolhida);
    ctx.place(it.t.el, { x: Math.round(escolhida.x), y: Math.round(escolhida.y) });
  }

  // vizinhança: mancha suave em volta da palavra e dos vizinhos + fios até cada vizinho; depois a seta do vetor
  const cd = itens[iDest].c;
  const raioViz = Math.max(...viz.map((i) => Math.hypot(itens[i].c.x - cd.x, itens[i].c.y - cd.y))) + r * 3.2;
  const mancha = ctx.el('div', 'emb-vizinhanca');
  Object.assign(mancha.style, { position: 'absolute', left: (cd.x - raioViz).toFixed(1) + 'px', top: (cd.y - raioViz).toFixed(1) + 'px', width: (2 * raioViz).toFixed(1) + 'px', height: (2 * raioViz).toFixed(1) + 'px',
    borderRadius: '50%', background: ctx.alfa(cor, 0.12), border: `${Math.max(1, ctx.traco * 0.75).toFixed(1)}px solid ${ctx.alfa(cor, 0.7)}` });
  camada.insertBefore(mancha, svg);
  const fios = viz.map((i) => linha(ctx, svg, cd.x, cd.y, itens[i].c.x, itens[i].c.y, { cor, esp: Math.max(1.5, ctx.traco) }));
  const flecha = seta(ctx, svg, cx, cy, cd.x, cd.y, { cor, esp: Math.max(2, ctx.traco * 1.5) });

  guardar(ESTADOS, ctx, { ctx, Q, P, itens, iDest, viz: new Set(viz), grade, eixoX, eixoY, notaPlano, fundo, mancha, fios, flecha, palavra, lista, nota, nLista: lista._inner.textContent.length });
  return Q.layout({ plano: { x: Math.round(plano.x), y: Math.round(plano.y), lado: Math.round(lado) }, painel: { x: Math.round(painel.x), y: Math.round(painel.y), w: Math.round(wPainel), h: Math.round(hPainel) },
    destaque: nomes[iDest], vizinhos: viz.map((i) => nomes[i]), tamanho_rotulo: +tamRot.toFixed(1) });
}

export function seek(t, ctxArg) {
  const { ctx, Q, P, itens, iDest, viz, grade, eixoX, eixoY, notaPlano, fundo, mancha, fios, flecha, palavra, lista, nota, nLista } = ler(ESTADOS, ctxArg);
  const d = ctx.DA.movimento.duracoes, e = ctx.escalonamento;
  // 1. o plano se desenha
  ctx.entrada(fundo, P.prog(t, 'plano', 0, d.media), 'fade');
  const pEixos = P.prog(t, 'plano', d.curta * 0.5, d.longa - d.curta * 0.5, 'suave');
  eixoX.tracar(pEixos); eixoY.tracar(pEixos);
  grade.forEach((l, i) => l.tracar(clamp(pEixos * 1.5 - (i / grade.length) * 0.5)));
  ctx.entrada(notaPlano, P.prog(t, 'plano', d.media, d.curta), 'fade');
  // 2. os pontos entram; 3. a vizinhança acende e o resto recua; 4. a seta e a lista de números
  const pViz = P.prog(t, 'vizinhanca', 0, d.media);
  const pVet = P.prog(t, 'vetor', 0, d.longa, 'enfase');
  itens.forEach((it, i) => {
    const pe = P.prog(t, 'pontos', i * e * 2, d.media);
    const meu = i === iDest, perto = viz.has(i);
    const apaga = meu || perto ? 0 : pViz * 0.68;
    ctx.entrada(it.base, pe, 'escala');
    it.base.style.opacity = (clamp(pe) * (1 - apaga)).toFixed(3);
    ctx.entrada(it.t.el, P.prog(t, 'pontos', i * e * 2 + d.curta * 0.5, d.media), 'fade');
    it.t.el.style.opacity = (clamp(P.prog(t, 'pontos', i * e * 2 + d.curta * 0.5, d.media)) * (1 - apaga)).toFixed(3);
    const aceso = meu ? pViz : perto ? pViz * (1 - 0.999 * clamp(pVet)) : 0;
    it.vivo.style.opacity = clamp(aceso).toFixed(3);
    it.t.misturar(meu ? pViz : 0);
  });
  mancha.style.opacity = (clamp(pViz) * (1 - 0.65 * clamp(pVet))).toFixed(3);
  mancha.style.transform = `scale(${(0.7 + 0.3 * P.prog(t, 'vizinhanca', 0, d.longa, 'enfase')).toFixed(4)})`;
  fios.forEach((f, i) => { f.tracar(P.prog(t, 'vizinhanca', d.curta + i * e * 2, d.media, 'suave')); f.style.opacity = (f.style.opacity === '0' ? 0 : 1 - 0.75 * clamp(pVet)).toFixed(3); });
  flecha.tracar(pVet);
  ctx.entrada(palavra, P.prog(t, 'vetor', d.curta, d.media));
  ctx.entrada(lista, P.prog(t, 'vetor', d.media, d.longa), undefined, { n: nLista });
  ctx.entrada(nota, P.prog(t, 'vetor', d.longa, d.media), 'fade');
  Q.seek(t);
}

export function key(t, ctx) { return ler(ESTADOS, ctx).P.chave(t); }

export function ancoras(ctx) { return ler(ESTADOS, ctx).P.ancoras(); }
