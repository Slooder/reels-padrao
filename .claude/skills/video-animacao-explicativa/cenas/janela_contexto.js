// janela_contexto.js — a faixa de tokens enche; entrada e saída ocupam a MESMA janela; o que não cabe fica de fora.
// Passos: janela → bloco1 → bloco2 → … → resumo.
// Simplificação declarada em references/didatica.md: a janela do exemplo tem poucas dezenas de casas (as reais têm de
// milhares a milhões de tokens) e o descarte do mais antigo é UMA das políticas possíveis — quem decide o que sai é o
// aplicativo; chamada direta à API que estoura o limite costuma ser recusada, não truncada.
import { params, guardar, ler, montarQuadro, rotulo, textoDuplo, contador, clamp, lerp, num } from './_ia.js';

const EXEMPLO = [
  { rotulo: 'pergunta', tokens: 5, tipo: 'entrada' }, { rotulo: 'resposta', tokens: 9, tipo: 'saida' },
  { rotulo: 'nova pergunta', tokens: 6, tipo: 'entrada' }, { rotulo: 'nova resposta', tokens: 10, tipo: 'saida' },
];

export const meta = {
  nome: 'janela_contexto',
  descricao: 'Janela de contexto: a conversa enche uma faixa de tamanho fixo; o que você escreve e o que o modelo responde ocupam a mesma janela; o que não cabe fica de fora e o modelo não vê.',
  dur_padrao: 14,
  formatos: ['horizontal', 'vertical', 'quadrado'],
  alfa_padrao: false,
  grao: true,
  params: params({
    capacidade: { tipo: 'inteiro', padrao: 24, min: 8, max: 48, descricao: 'quantas casas a janela desenhada tem' },
    blocos: { tipo: 'lista', min: 1, max: 8, padrao: EXEMPLO, descricao: 'as mensagens, na ordem: quantas casas cada uma ocupa e se é entrada (você) ou saída (modelo)',
      itens: { tipo: 'objeto', campos: { rotulo: { tipo: 'texto', padrao: null }, tokens: { tipo: 'inteiro', obrigatorio: true, min: 1, max: 60 }, tipo: { tipo: 'opcao', opcoes: ['entrada', 'saida'], obrigatorio: true } } } },
    tokens_por_celula: { tipo: 'inteiro', padrao: 1, min: 1, descricao: 'quantos tokens cada casa representa nos rótulos (ex.: 1000 → "24.000 tokens"); número real de modelo exige fonte e fato_ids' },
  }, { titulo: 'Janela de contexto' }),
};

const ritmo = (d, qtd) => Math.max(d.micro, Math.min(d.curta * 0.7, 1.5 / qtd));

export function roteiro(p, mov) {
  const d = mov.duracoes;
  const blocos = p.blocos || EXEMPLO;
  return [
    { nome: 'janela', tipo: 'entrada', anim: d.longa + d.media },
    ...blocos.map((b, i) => ({ nome: 'bloco' + (i + 1), tipo: 'texto', anim: b.tokens * ritmo(d, b.tokens) + d.media })),
    { nome: 'resumo', tipo: 'enfase', anim: d.media * 2 },
  ];
}

function legendasDe(blocos, N) {
  const frases = ['A *janela de contexto* é o texto que o modelo enxerga de uma vez'];
  let acum = 0, viuEntrada = false, viuSaida = false;
  for (const b of blocos) {
    const antes = acum; acum += b.tokens;
    if (acum > N && antes <= N) frases.push('Quando não cabe, o mais antigo *fica de fora*');
    else if (acum > N) frases.push('A conversa segue; mais texto antigo sai');
    else if (b.tipo === 'entrada') frases.push(viuEntrada ? 'A conversa inteira é reenviada a cada turno' : 'O que você escreve ocupa a janela');
    else frases.push(viuSaida ? 'A janela vai enchendo' : 'A resposta *também* ocupa a janela');
    if (b.tipo === 'entrada') viuEntrada = true; else viuSaida = true;
  }
  frases.push(acum > N ? 'O que saiu, o modelo *não vê mais*' : 'Tudo o que está na janela é relido a cada resposta');
  return frases;
}

const ESTADOS = new WeakMap();

export function build(palco, p, ctx) {
  const N = p.capacidade, k = p.tokens_por_celula, cor = p.cor;
  const blocos = p.blocos;
  const M = blocos.reduce((a, b) => a + b.tokens, 0);
  if (M > 140) throw new Error(`blocos somam ${M} casas; o desenho comporta até 140 — aumente tokens_por_celula e diminua os números`);
  const rot = roteiro(p, ctx.DA.movimento);
  const Q = montarQuadro(palco, p, ctx, { roteiro: rot, legendas: legendasDe(blocos, N) });
  const C = Q.conteudo, P = Q.P, d = ctx.DA.movimento.duracoes;
  const camada = ctx.el('div', 'jc-camada');
  Object.assign(camada.style, { position: 'absolute', left: '0', top: '0' });
  Q.raiz.appendChild(camada);

  // rótulos e contadores
  const unidade = (v) => num(v * k, 0);
  const rotJanela = rotulo(ctx, 'janela de contexto', { tam: ctx.tam('nota') });
  const conta = contador(ctx, { tam: ctx.tam('corpo'), cor: 'texto', formato: (v) => `${unidade(v)} / ${unidade(N)} tokens`, modelo: `${unidade(N)} / ${unidade(N)} tokens` });
  const rotFora = textoDuplo(ctx, 'dados', 'fora da janela', { tam: ctx.tam('nota'), corA: 'texto_suave', corB: 'texto', classe: 'jc-fora' });
  const contaFora = contador(ctx, { tam: ctx.tam('corpo'), cor: 'texto', formato: (v) => unidade(v), modelo: unidade(Math.max(0, M - N)) });
  camada.append(rotJanela, conta.el, rotFora.el, contaFora.el);
  const mRJ = ctx.medir(rotJanela), mConta = conta.medir(), mCF = contaFora.medir();
  rotFora.medir();
  const itensLegenda = [['entrada (você)', 'texto_suave'], ['saída (modelo)', cor]].map(([txt, token]) => {
    const q = ctx.el('div', 'jc-amostra'); const lado = ctx.tam('nota') * 0.8;
    Object.assign(q.style, { position: 'absolute', width: lado + 'px', height: lado + 'px', background: ctx.cor(token), borderRadius: Math.min(ctx.raio, lado / 4) + 'px' });
    const r = rotulo(ctx, txt, { tam: ctx.tam('nota') });
    camada.append(q, r);
    return { q, r, m: ctx.medir(r), lado };
  });
  const hLinha = Math.max(mRJ.h, mConta.h), hLeg = itensLegenda[0].m.h;
  const vaoV = ctx.px(0.018);

  // grade de casas: uma fileira (horizontal, até 32 casas) ou várias (vertical e janelas grandes)
  const umaFileira = Q.horizontal && N <= 32;
  const colunas = umaFileira ? N : Q.horizontal ? Math.ceil(N / 2) : N <= 12 ? N : N <= 24 ? 6 : 8;
  const fileiras = Math.ceil(N / colunas);
  const foraVisiveis = umaFileira ? Math.min(5, Math.max(2, Math.round(N / 5))) : colunas;
  // várias fileiras: a moldura (borda + folga de 0,9 fresta de cada lado) tem de caber na largura útil junto com as casas
  const borda = Math.max(2, ctx.traco);
  const passoX = umaFileira ? C.w / (colunas + foraVisiveis + 0.6) : Math.min((C.w - 2 * borda) / (colunas + 0.096), (C.w - 2 * borda - 2.4) / colunas);
  const fresta = Math.max(3, passoX * 0.12);
  const w = passoX - fresta;
  const hMaxCasa = umaFileira ? ctx.px(0.17) : ctx.px(0.075);
  const hDisp = C.h - hLinha - vaoV * 3 - hLeg - (umaFileira ? 0 : rotFora.h + vaoV);
  const h = Math.max(8, Math.min(umaFileira ? w * 2.6 : w * 0.62, hMaxCasa, hDisp / (fileiras + (umaFileira ? 0 : 1)) - fresta));
  const passoY = h + fresta;
  const hGrade = fileiras * passoY - fresta;
  const hTudo = (umaFileira ? hLinha + vaoV : rotFora.h + vaoV * 0.6 + passoY + vaoV * 0.4) + hGrade + vaoV * (umaFileira ? 1.6 : 1) + (umaFileira ? 0 : hLinha + vaoV) + hLeg;
  const y0 = C.y + Math.max(0, (C.h - hTudo) / 2);
  const fx = umaFileira ? C.x + foraVisiveis * passoX + fresta * 0.5 + passoX * 0.3 : C.x + borda + fresta * 0.9;
  const fy = umaFileira ? y0 + hLinha + vaoV : y0 + rotFora.h + vaoV * 0.6 + passoY + vaoV * 0.4;
  const casa = (i) => { const linha = Math.floor(i / colunas); return { linha, x: fx + (i - linha * colunas) * passoX, y: fy + linha * passoY }; };
  const lugar = (s) => {                                     // posição de um token na casa s (fracionária); k = encolhe ao trocar de fileira
    if (umaFileira) return { x: fx + s * passoX, y: fy, k: 1 };
    const a = Math.floor(s), f = s - a, A = casa(a), B = casa(a + 1);
    if (A.linha === B.linha) return { x: lerp(A.x, B.x, f), y: A.y, k: 1 };
    return f < 0.5 ? { x: A.x, y: A.y, k: 1 - 2 * f } : { x: B.x, y: B.y, k: 2 * f - 1 };
  };
  // moldura da janela e casas vazias
  const moldura = ctx.el('div', 'jc-moldura');
  const pad = fresta * 0.9;
  Object.assign(moldura.style, { position: 'absolute', left: (fx - pad - borda).toFixed(1) + 'px', top: (fy - pad - borda).toFixed(1) + 'px', width: (colunas * passoX - fresta + 2 * pad + 2 * borda).toFixed(1) + 'px',
    height: (hGrade + 2 * pad + 2 * borda).toFixed(1) + 'px', border: `${borda.toFixed(1)}px solid ${ctx.cor('texto')}`, borderRadius: (Math.min(ctx.raio, h / 4) + pad) + 'px' });
  camada.appendChild(moldura);
  const raio = Math.min(ctx.raio, Math.min(w, h) / 4);
  const vazias = Array.from({ length: N }, (_, i) => {
    const c = casa(i), e = ctx.el('div', 'jc-vazia');
    Object.assign(e.style, { position: 'absolute', left: c.x.toFixed(1) + 'px', top: c.y.toFixed(1) + 'px', width: w.toFixed(1) + 'px', height: h.toFixed(1) + 'px', background: ctx.alfa(ctx.DA.graficos.dados.grade, 0.7), borderRadius: raio + 'px' });
    camada.appendChild(e);
    return e;
  });
  // tokens: um elemento por casa ocupada, com o instante em que entra
  const fichas = [];
  blocos.forEach((b, bi) => {
    const passo = P.indice('bloco' + (bi + 1));
    const r = ritmo(d, b.tokens);
    for (let i = 0; i < b.tokens; i++) {
      const e = ctx.el('div', 'jc-token');
      Object.assign(e.style, { position: 'absolute', left: '0', top: '0', width: w.toFixed(1) + 'px', height: h.toFixed(1) + 'px', background: ctx.cor(b.tipo === 'saida' ? cor : 'texto_suave'), borderRadius: raio + 'px', transformOrigin: 'center center' });
      camada.appendChild(e);
      fichas.push({ e, j: fichas.length, t0: P.t[passo] + i * r * P.e[passo], dur: r * P.e[passo] });
    }
  });
  // posições dos rótulos
  if (umaFileira) {
    ctx.place(rotFora.el, { x: Math.round(C.x), y: Math.round(y0 + hLinha - rotFora.h) });
    ctx.place(contaFora.el, { x: Math.round(C.x + rotFora.w + ctx.px(0.012)), y: Math.round(y0 + hLinha - mCF.h) });
    ctx.place(rotJanela, { x: Math.round(fx - pad), y: Math.round(y0 + hLinha - mRJ.h) });
    ctx.place(conta.el, { x: Math.round(fx + colunas * passoX - fresta + pad - mConta.w), y: Math.round(y0 + hLinha - mConta.h) });
  } else {
    ctx.place(rotFora.el, { x: Math.round(C.x), y: Math.round(y0) });
    ctx.place(contaFora.el, { x: Math.round(C.x + rotFora.w + ctx.px(0.012)), y: Math.round(y0 + rotFora.h - mCF.h) });
    const yL = fy + hGrade + pad + borda + vaoV * 0.7;
    ctx.place(rotJanela, { x: Math.round(C.x), y: Math.round(yL + hLinha - mRJ.h) });
    ctx.place(conta.el, { x: Math.round(C.x1 - mConta.w), y: Math.round(yL + hLinha - mConta.h) });
  }
  const yLeg = umaFileira ? fy + hGrade + pad + borda + vaoV * 1.2 : fy + hGrade + pad + borda + vaoV * 0.7 + hLinha + vaoV;
  let xLeg = umaFileira ? fx - pad : C.x;
  for (const it of itensLegenda) {
    ctx.place(it.q, { x: Math.round(xLeg), y: Math.round(yLeg + (it.m.h - it.lado) / 2) });
    ctx.place(it.r, { x: Math.round(xLeg + it.lado + ctx.px(0.008)), y: Math.round(yLeg) });
    xLeg += it.lado + ctx.px(0.008) + it.m.w + ctx.px(0.03);
  }
  guardar(ESTADOS, ctx, { ctx, Q, P, N, M, fichas, vazias, moldura, lugar, umaFileira, foraVisiveis, colunas, rotJanela, conta, rotFora, contaFora, itensLegenda, transborda: M > N });
  return Q.layout({ capacidade: N, casas_ocupadas: M, de_fora: Math.max(0, M - N), fileiras, colunas, casa: { w: Math.round(w), h: Math.round(h) },
    bloco: { x: Math.round(C.x), y: Math.round(y0), w: Math.round(C.w), h: Math.round(hTudo) } });
}

export function seek(t, ctxArg) {
  const { ctx, Q, P, N, fichas, vazias, moldura, lugar, umaFileira, foraVisiveis, colunas, rotJanela, conta, rotFora, contaFora, itensLegenda, transborda } = ler(ESTADOS, ctxArg);
  const d = ctx.DA.movimento.duracoes;
  // 1. a janela vazia
  ctx.entrada(moldura, P.prog(t, 'janela', 0, d.longa), 'fade');
  vazias.forEach((e, i) => { e.style.opacity = clamp(P.prog(t, 'janela', d.curta * 0.5 + (i / N) * d.media, d.media)).toFixed(3); });
  ctx.entrada(rotJanela, P.prog(t, 'janela', d.media, d.media), 'fade');
  ctx.entrada(conta.el, P.prog(t, 'janela', d.media, d.media), 'fade');
  itensLegenda.forEach((it, i) => { const pe = P.prog(t, 'janela', d.longa + i * d.curta * 0.5, d.media - i * d.curta * 0.5); ctx.entrada(it.r, pe, 'fade'); it.q.style.opacity = clamp(pe).toFixed(3); });
  // 2. os tokens entram um a um; passou da capacidade, tudo anda uma casa e o mais antigo sai pela borda
  let cheios = 0;
  for (const f of fichas) { f.q = clamp((t - f.t0) / f.dur); cheios += f.q; }
  const inicio = Math.max(0, cheios - N);
  const pResumo = P.prog(t, 'resumo', 0, d.media, 'enfase');
  for (const f of fichas) {
    const s = f.j - inicio;
    const L = lugar(s);
    let opacidade = f.q, escala = L.k * (0.6 + 0.4 * f.q);
    if (s < -0.02) {                                          // fora da janela: apaga com a distância e encolhe
      const dist = umaFileira ? -s : Math.ceil(-s / colunas);
      const some = umaFileira ? clamp(1 - (dist - 0.5) / foraVisiveis) : (dist <= 1 ? 1 : 0);
      opacidade = f.q * some * lerp(0.42, 0.75, clamp(pResumo));
      escala *= 0.82;
    }
    f.e.style.opacity = opacidade.toFixed(3);
    f.e.style.transform = `translate(${L.x.toFixed(2)}px, ${L.y.toFixed(2)}px) scale(${Math.max(0, escala).toFixed(4)})`;
  }
  conta.definir(Math.round(Math.min(N, cheios)));
  const fora = Math.max(0, Math.round(cheios) - N);
  const pFora = transborda ? clamp(inicio * 2) : 0;
  ctx.entrada(rotFora.el, pFora, 'fade');
  rotFora.misturar(pResumo);
  ctx.entrada(contaFora.el, pFora, 'fade');
  contaFora.definir(fora);
  Q.seek(t);
}

export function key(t, ctx) { return ler(ESTADOS, ctx).P.chave(t); }

export function ancoras(ctx) { return ler(ESTADOS, ctx).P.ancoras(); }
