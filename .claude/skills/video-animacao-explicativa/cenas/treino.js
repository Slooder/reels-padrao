// treino.js — previsão × resposta, o erro vira um número (a perda), os pesos são ajustados e a curva de perda desce.
// Passos: previsao → alvo → erro → ajuste → repete → fim.
// A perda mostrada é calculada DE VERDADE a partir da probabilidade que o modelo dá à resposta certa em cada passo:
// perda = −ln p(resposta) (entropia cruzada). A curva não é um desenho à parte: sai dos mesmos números das barras.
// Simplificação declarada em references/didatica.md: um exemplo só, meia dúzia de pesos, trajetória inventada.
import { params, guardar, ler, montarQuadro, caixaToken, rotulo, barra, contador, camadaSvg, eixo, clamp, lerp, num, pct, soma, porAtributo } from './_ia.js';

const EXEMPLO = {
  contexto: 'A capital da França é', alvo: ' Paris',
  outros: [{ token: ' Lyon', peso: 0.45 }, { token: ' linda', peso: 0.35 }, { token: ' uma', peso: 0.2 }],
  prob_alvo: [0.04, 0.09, 0.2, 0.38, 0.58, 0.74, 0.85, 0.91],
};

export const meta = {
  nome: 'treino',
  descricao: 'Treino: o modelo chuta o próximo token, compara com a resposta do texto, mede o erro (perda), ajusta os pesos um pouco e repete — a curva de perda desce.',
  dur_padrao: 15,
  formatos: ['horizontal', 'vertical', 'quadrado'],
  alfa_padrao: false,
  grao: true,
  params: params({
    contexto: { tipo: 'texto', padrao: EXEMPLO.contexto, descricao: 'o começo da frase de treino' },
    alvo: { tipo: 'texto', padrao: EXEMPLO.alvo, descricao: 'o token que realmente vem depois, no texto de treino' },
    outros: { tipo: 'lista', min: 1, max: 4, padrao: EXEMPLO.outros, descricao: 'tokens errados que disputam com a resposta; `peso` reparte entre eles a probabilidade que sobra',
      itens: { tipo: 'objeto', campos: { token: { tipo: 'texto', obrigatorio: true }, peso: { tipo: 'numero', obrigatorio: true, min: 0.001 } } } },
    prob_alvo: { tipo: 'lista', min: 3, max: 12, padrao: EXEMPLO.prob_alvo, itens: { tipo: 'numero', min: 0.001, max: 0.999 }, descricao: 'probabilidade dada à resposta certa a cada passo de treino mostrado (a perda de cada passo é −ln dela)' },
    pesos_visiveis: { tipo: 'inteiro', padrao: 8, min: 4, max: 12, descricao: 'quantos pesos aparecem como controles (uma amostra: um modelo real tem milhões de pesos ou mais)' },
    semente: { tipo: 'inteiro', padrao: 11, min: 0, descricao: 'semente do movimento dos controles de peso' },
  }, { titulo: 'Treino' }),
};

const LEGENDAS = ['O modelo *chuta* o próximo token', 'O texto de treino já traz a *resposta*', 'O tamanho do erro vira um número: a *perda*', 'Cada peso é *ajustado* um pouquinho', 'Repetindo com muitos textos, a perda *cai*', 'Treinar é isso: *prever melhor*'];
const passoDeTreino = (d) => Math.max(0.24, d.media * 0.8);

export function roteiro(p, mov) {
  const d = mov.duracoes, e = mov.escalonamento;
  const N = (p.prob_alvo || EXEMPLO.prob_alvo).length, linhas = (p.outros || EXEMPLO.outros).length + 1;
  return [
    { nome: 'previsao', tipo: 'entrada', anim: d.longa + linhas * e * 2 + d.curta },
    { nome: 'alvo', tipo: 'enfase', anim: d.media * 2 },
    { nome: 'erro', tipo: 'enfase', anim: d.longa + d.media },
    { nome: 'ajuste', tipo: 'enfase', anim: d.media + d.longa + d.curta },
    { nome: 'repete', tipo: 'enfase', anim: (N - 2) * passoDeTreino(d) + d.curta },
    { nome: 'fim', tipo: 'texto', anim: d.media * 2 },
  ];
}

const ESTADOS = new WeakMap();

export function build(palco, p, ctx) {
  const N = p.prob_alvo.length, cor = p.cor;
  const perdas = p.prob_alvo.map((q) => -Math.log(q));
  const partes = p.outros.map((o) => o.peso / soma(p.outros.map((x) => x.peso)));
  const Q = montarQuadro(palco, p, ctx, { roteiro: roteiro(p, ctx.DA.movimento), legendas: LEGENDAS });
  const C = Q.conteudo, P = Q.P;
  const camada = ctx.el('div', 'tr-camada');
  Object.assign(camada.style, { position: 'absolute', left: '0', top: '0' });
  Q.raiz.appendChild(camada);
  const vao = ctx.px(Q.horizontal ? 0.05 : 0.03);

  // regiões: previsão à esquerda, pesos e curva à direita (horizontal) ou tudo empilhado (vertical)
  const linhas = [{ token: p.alvo, alvo: true }, ...p.outros.map((o) => ({ token: o.token, alvo: false }))];
  const esq = Q.horizontal ? { x: C.x, w: C.w * 0.44 } : { x: C.x, w: C.w };
  const dir = Q.horizontal ? { x: C.x + C.w * 0.44 + vao * 1.4, w: C.w * 0.56 - vao * 1.4 } : { x: C.x, w: C.w };

  // frase de treino com a lacuna da resposta
  const frase = ctx.texto('corpo', '', { tam: Q.horizontal ? ctx.tam('h2') : Math.min(ctx.tam('h3'), ctx.tam('corpo') * 1.15), cor: 'texto', wrap: true, maxW: esq.w, classe: 'tr-frase', html: '' });
  frase.style.position = 'absolute';
  frase._inner.style.whiteSpace = 'pre-wrap';
  frase._inner.appendChild(ctx.el('span', 'tr-contexto', p.contexto));
  const visivel = p.alvo.replace(/^\s+/, '');
  if (visivel.length < p.alvo.length) frase._inner.appendChild(document.createTextNode(p.alvo.slice(0, p.alvo.length - visivel.length)));
  const resposta = ctx.el('span', 'tr-resposta', visivel);
  resposta.style.color = ctx.cor(cor);
  frase._inner.appendChild(resposta);
  camada.appendChild(frase);
  ctx.ajustar_texto(frase, esq.w, { min: ctx.tam('corpo'), maxLinhas: Q.horizontal ? 3 : 2 });
  const mFrase = ctx.medir(frase);
  const mFraseH = mFrase.h;

  // medidas dos blocos
  // empilhado (vertical): a letra das fichas encolhe até as fileiras caberem sem se encostar — nunca abaixo de `nota`
  let tamFicha = ctx.tam(Q.horizontal ? 'h3' : 'corpo');
  if (!Q.horizontal) {
    const reservado = mFraseH + 3 * vao + 2 * ctx.tam('nota') * 1.4 + ctx.px(0.03) + ctx.px(0.06) + ctx.px(0.14);     // frase, vãos, 2 rótulos, pesos e curva mínimos
    tamFicha = Math.max(ctx.tam('nota'), Math.min(tamFicha, (C.h - reservado) / (linhas.length * 1.65 * 1.08)));
  }
  const fichas = linhas.map((l) => { const f = caixaToken(ctx, l.token, { tam: tamFicha, cor, modo: 'contorno' }); camada.appendChild(f.el); f.medir(); return f; });
  const hFicha = fichas[0].h;
  const rotPesos = rotulo(ctx, 'pesos do modelo (uma amostra)', { tam: ctx.tam('nota') });
  const rotPerda = rotulo(ctx, 'perda', { tam: ctx.tam('nota') });
  const rotPassos = rotulo(ctx, 'passos de treino', { tam: ctx.tam('nota') });
  camada.append(rotPesos, rotPerda, rotPassos);
  const mRPe = ctx.medir(rotPesos), mRPd = ctx.medir(rotPerda), mRPa = ctx.medir(rotPassos);
  const valor = contador(ctx, { tam: ctx.tam(Q.horizontal ? 'h2' : 'h3'), cor: 'texto', formato: (v) => num(v, 2), modelo: '0,00' });
  camada.appendChild(valor.el);
  const mVal = valor.medir();
  let passo, hBarras, hPesos, hGraf, yFrase, yBarras, yPesos, yGraf;
  if (Q.horizontal) {
    passo = Math.min(hFicha * 1.3, (C.h - mFrase.h - vao) / linhas.length);
    hBarras = linhas.length * passo;
    const hEsq = mFrase.h + vao + hBarras;
    yFrase = C.y + (C.h - hEsq) / 2; yBarras = yFrase + mFrase.h + vao;
    hPesos = Math.min(ctx.px(0.16), C.h * 0.26);
    hGraf = Math.min(C.h - hPesos - mRPe.h - vao * 1.2 - mRPa.h - ctx.px(0.02), ctx.px(0.36));
    const hDir = mRPe.h + ctx.px(0.012) + hPesos + vao + hGraf + ctx.px(0.012) + mRPa.h;
    yPesos = C.y + (C.h - hDir) / 2; yGraf = yPesos + mRPe.h + ctx.px(0.012) + hPesos + vao;
  } else {
    const sobra = C.h - mFrase.h - 3 * vao - mRPe.h - mRPa.h - ctx.px(0.03);
    passo = Math.max(hFicha * 1.06, Math.min(hFicha * 1.2, (sobra * 0.42) / linhas.length));
    hBarras = linhas.length * passo;
    hPesos = Math.max(ctx.px(0.05), Math.min(ctx.px(0.1), (sobra - hBarras) * 0.3));
    hGraf = Math.max(ctx.px(0.1), Math.min(ctx.px(0.3), sobra - hBarras - hPesos));
    const medir = () => mFrase.h + vao + hBarras + vao + mRPe.h + ctx.px(0.01) + hPesos + vao + hGraf + ctx.px(0.01) + mRPa.h;
    // os mínimos acima somam mais que a área útil numa DA de letra grande: a curva e os controles cedem altura antes de sair da zona
    for (const [ler, gravar, piso] of [[() => hGraf, (v) => { hGraf = v; }, ctx.px(0.07)], [() => hPesos, (v) => { hPesos = v; }, ctx.px(0.035)]]) {
      const excesso = medir() - C.h;
      if (excesso > 0) gravar(Math.max(piso, ler() - excesso));
    }
    const hTudo = medir();
    if (hTudo > C.h + 1) throw new Error(`treino: a frase, as ${linhas.length} barras, os controles e a curva não couberam na área útil deste formato (${Math.round(C.w)} × ${Math.round(C.h)} px) nem com a menor letra legível da DA — use menos alternativas em "outros" ou uma frase mais curta. Para ganhar altura: titulo: "", ou reservar_legenda=false se a peça não leva legenda queimada`);
    yFrase = C.y + Math.max(0, (C.h - hTudo) / 2); yBarras = yFrase + mFrase.h + vao;
    yPesos = yBarras + hBarras + vao; yGraf = yPesos + mRPe.h + ctx.px(0.01) + hPesos + vao;
  }
  ctx.place(frase, { x: Math.round(esq.x), y: Math.round(yFrase) });
  const rr = ctx.rectDe(resposta), folga = Math.max(3, frase._tam * 0.1);
  const lacuna = ctx.el('div', 'tr-lacuna');
  Object.assign(lacuna.style, { position: 'absolute', left: (rr.x - folga).toFixed(1) + 'px', top: (rr.y + rr.h * 0.08).toFixed(1) + 'px', width: (rr.w + 2 * folga).toFixed(1) + 'px', height: (rr.h * 0.84).toFixed(1) + 'px',
    border: `${Math.max(1, ctx.traco * 0.75).toFixed(1)}px dashed ${ctx.cor('texto_suave')}`, borderRadius: ctx.raio + 'px' });
  camada.insertBefore(lacuna, frase);

  // barras da previsão
  const wFicha = Math.max(...fichas.map((f) => f.w));
  const wPct = (() => { const t = rotulo(ctx, '100%', { tam: tamFicha, cor: 'texto' }); camada.appendChild(t); const w = ctx.medir(t).w; t.remove(); return w; })();
  const xBarra = esq.x + wFicha + ctx.px(0.018), wBarra = esq.w - wFicha - ctx.px(0.018) - wPct - ctx.px(0.016);
  const fileiras = linhas.map((l, i) => {
    const f = fichas[i], y = yBarras + i * passo;
    ctx.place(f.el, { x: Math.round(esq.x), y: Math.round(y + (passo - f.h) / 2) });
    const b = barra(ctx, { w: wBarra, h: Math.max(8, Math.min(f.h * 0.5, passo * 0.42)), cor });
    camada.appendChild(b.el);
    ctx.place(b.el, { x: Math.round(xBarra), y: Math.round(y + (passo - b.h) / 2) });
    const v = contador(ctx, { tam: tamFicha, cor: 'texto', formato: (x) => (x > 0 && x < 0.005 ? '<1%' : pct(x)), modelo: '100%' });
    camada.appendChild(v.el);
    const mv = v.medir();
    ctx.place(v.el, { x: Math.round(esq.x + esq.w - mv.w), y: Math.round(y + (passo - mv.h) / 2) });
    Object.assign(v.el._inner.style, { textAlign: 'right', display: 'block', width: mv.w + 'px' });
    return { f, b, v, alvo: l.alvo, parte: l.alvo ? 0 : partes[i - 1] };
  });

  // controles de peso: cada um faz um passeio pequeno e cada vez menor (semente)
  ctx.place(rotPesos, { x: Math.round(dir.x), y: Math.round(yPesos) });
  const yTrilho = yPesos + mRPe.h + ctx.px(Q.horizontal ? 0.012 : 0.01);
  const K = p.pesos_visiveis;
  const rng = ctx.rng(p.semente);
  const wCtl = Math.min(dir.w / K, ctx.px(0.12));
  const lBotao = Math.max(10, Math.min(wCtl * 0.42, ctx.px(0.03))), aBotao = Math.max(6, hPesos * 0.14);
  const controles = Array.from({ length: K }, (_, k) => {
    const valores = [0.2 + 0.6 * rng()];
    for (let i = 1; i < N; i++) valores.push(clamp(valores[i - 1] + (rng() - 0.5) * 0.55 * 0.82 ** i, 0.06, 0.94));
    const cx = dir.x + wCtl * (k + 0.5);
    const trilho = ctx.el('div', 'tr-trilho');
    Object.assign(trilho.style, { position: 'absolute', left: (cx - Math.max(1, ctx.traco * 0.5)).toFixed(1) + 'px', top: Math.round(yTrilho) + 'px', width: Math.max(2, ctx.traco).toFixed(1) + 'px', height: Math.round(hPesos) + 'px',
      background: ctx.alfa(ctx.DA.graficos.dados.grade, 0.9), borderRadius: '2px' });
    const botao = ctx.el('div', 'tr-botao');
    Object.assign(botao.style, { position: 'absolute', left: (cx - lBotao / 2).toFixed(1) + 'px', top: Math.round(yTrilho - aBotao / 2) + 'px', width: lBotao.toFixed(1) + 'px', height: aBotao.toFixed(1) + 'px' });
    const neutro = ctx.el('div'); Object.assign(neutro.style, { position: 'absolute', inset: '0', background: ctx.cor('texto'), borderRadius: Math.min(ctx.raio, aBotao / 2) + 'px' });
    const vivo = ctx.el('div'); Object.assign(vivo.style, { position: 'absolute', inset: '0', background: ctx.cor(cor), borderRadius: Math.min(ctx.raio, aBotao / 2) + 'px', opacity: '0' });
    botao.append(neutro, vivo);
    camada.append(trilho, botao);
    return { trilho, botao, vivo, valores };
  });

  // curva de perda
  const svg = camadaSvg(ctx, camada);
  const wValor = Math.max(mVal.w, ctx.tam('nota') * 7);        // coluna do número: cabe também o rótulo "perda agora"
  const gx = dir.x + ctx.px(0.004), gy = yGraf, gw = dir.w - wValor - ctx.px(0.03), gh = hGraf;
  const eixoY = eixo(ctx, svg, gx, gy + gh, gx, gy), eixoX = eixo(ctx, svg, gx, gy + gh, gx + gw, gy + gh, { marcas: Math.min(N - 2, 10) });
  const maxPerda = Math.max(...perdas);
  const ponto = (s) => {
    const i = Math.min(N - 2, Math.floor(s)), f = s - i;
    const q = lerp(p.prob_alvo[i], p.prob_alvo[i + 1], f);
    return { x: gx + (s / (N - 1)) * gw, y: gy + gh - (-Math.log(q) / maxPerda) * gh * 0.9, q, perda: -Math.log(q) };
  };
  const curva = ctx.svg('path', { d: '', stroke: ctx.cor(cor), 'stroke-width': Math.max(2, ctx.traco * 1.6).toFixed(2), 'stroke-linecap': 'round', 'stroke-linejoin': 'round', fill: 'none' });
  svg.appendChild(curva);
  const rp = Math.max(5, ctx.px(0.008));
  const bolinha = ctx.el('div', 'tr-ponto');
  Object.assign(bolinha.style, { position: 'absolute', left: -rp + 'px', top: -rp + 'px', width: 2 * rp + 'px', height: 2 * rp + 'px', borderRadius: '50%', background: ctx.cor(cor) });
  const aro = ctx.el('div', 'tr-aro');
  Object.assign(aro.style, { position: 'absolute', left: -rp * 2.4 + 'px', top: -rp * 2.4 + 'px', width: rp * 4.8 + 'px', height: rp * 4.8 + 'px', borderRadius: '50%', border: `${Math.max(2, ctx.traco * 1.2).toFixed(1)}px solid ${ctx.cor(cor)}` });
  camada.append(aro, bolinha);
  ctx.place(rotPerda, { x: Math.round(gx + ctx.px(0.012)), y: Math.round(gy - mRPd.h * 0.2) });
  ctx.place(rotPassos, { x: Math.round(gx + gw - mRPa.w), y: Math.round(gy + gh + ctx.px(Q.horizontal ? 0.012 : 0.01)) });
  ctx.place(valor.el, { x: Math.round(dir.x + dir.w - mVal.w), y: Math.round(gy + gh * 0.5 - mVal.h / 2) });
  const rotAgora = rotulo(ctx, 'perda agora', { tam: ctx.tam('nota') });
  camada.appendChild(rotAgora);
  const mRA = ctx.medir(rotAgora);
  ctx.place(rotAgora, { x: Math.round(dir.x + dir.w - Math.max(mRA.w, mVal.w)), y: Math.round(gy + gh * 0.5 - mVal.h / 2 - mRA.h - ctx.px(0.004)) });

  guardar(ESTADOS, ctx, { ctx, Q, P, p, N, frase, resposta, lacuna, fileiras, controles, hPesos, eixoX, eixoY, curva, bolinha, aro, ponto, rotPesos, rotPerda, rotPassos, rotAgora, valor, nCtx: p.contexto.length });
  return Q.layout({ passos_de_treino: N, perda_inicial: +perdas[0].toFixed(4), perda_final: +perdas[N - 1].toFixed(4), frase: ctx.rectDe(frase),
    grafico: { x: Math.round(gx), y: Math.round(gy), w: Math.round(gw), h: Math.round(gh) }, tamanho_ficha: +tamFicha.toFixed(1), fileira: { passo: +passo.toFixed(1), ficha: hFicha },
    bloco: { x: Math.round(C.x), y: Math.round(yFrase), w: Math.round(C.w), h: Math.round(gy + gh + ctx.px(Q.horizontal ? 0.012 : 0.01) + mRPa.h - yFrase) } });
}

export function seek(t, ctxArg) {
  const { ctx, Q, P, p, N, frase, resposta, lacuna, fileiras, controles, hPesos, eixoX, eixoY, curva, bolinha, aro, ponto, rotPesos, rotPerda, rotPassos, rotAgora, valor, nCtx } = ler(ESTADOS, ctxArg);
  const d = ctx.DA.movimento.duracoes, e = ctx.escalonamento;
  // s = quantos passos de treino já aconteceram (contínuo): 0 até o ajuste, 0→1 no ajuste, 1→N−1 na repetição
  const pAj = P.prog(t, 'ajuste', d.media, d.longa, 'suave');
  const pRep = P.prog(t, 'repete', 0, (N - 2) * Math.max(0.24, d.media * 0.8), 'suave');
  const s = clamp(pAj) + (N - 2) * clamp(pRep);
  const agora = ponto(s);
  const pAlvo = P.prog(t, 'alvo', 0, d.media, 'enfase');
  // 1. frase e previsão
  ctx.entrada(frase, P.lin(t, 'previsao', 0, d.longa), undefined, { n: nCtx });
  resposta.style.opacity = clamp(pAlvo).toFixed(3);
  lacuna.style.opacity = (clamp(P.prog(t, 'previsao', d.media, d.media)) * (1 - clamp(pAlvo))).toFixed(3);
  fileiras.forEach((l, i) => {
    const pe = P.prog(t, 'previsao', d.curta + i * e * 2, d.longa, 'enfase'), q = clamp(pe);
    const prob = l.alvo ? agora.q : (1 - agora.q) * l.parte;
    ctx.entrada(l.f.el, q, 'fade');
    l.f.estado({ caixa: 1, realce: l.alvo ? clamp(pAlvo) : 0 });
    l.b.estado({ fracao: prob * clamp(pe, 0, 1.04), realce: l.alvo ? clamp(pAlvo) : 0, trilha: q });
    l.v.definir(prob * q);
    l.v.el.style.opacity = q.toFixed(3);
  });
  // 3. o erro vira um número e o primeiro ponto da curva
  const pEixos = P.prog(t, 'erro', 0, d.longa, 'suave');
  eixoX.tracar(pEixos); eixoY.tracar(pEixos);
  ctx.entrada(rotPerda, P.prog(t, 'erro', d.curta, d.media), 'fade');
  ctx.entrada(rotPassos, P.prog(t, 'erro', d.curta, d.media), 'fade');
  const pPonto = P.prog(t, 'erro', d.media, d.media, 'enfase');
  ctx.entrada(valor.el, P.prog(t, 'erro', d.media, d.media));
  ctx.entrada(rotAgora, P.prog(t, 'erro', d.media, d.media), 'fade');
  valor.definir(agora.perda);
  bolinha.style.transform = `translate(${agora.x.toFixed(2)}px, ${agora.y.toFixed(2)}px) scale(${clamp(pPonto, 0, 1.2).toFixed(4)})`;
  bolinha.style.opacity = pPonto > 0 ? '1' : '0';
  const pFim = P.prog(t, 'fim', 0, d.media, 'enfase');
  aro.style.transform = `translate(${agora.x.toFixed(2)}px, ${agora.y.toFixed(2)}px) scale(${lerp(1.6, 1, clamp(pFim)).toFixed(4)})`;
  aro.style.opacity = clamp(pFim).toFixed(3);
  // curva: do passo 0 até s, com o último trecho interpolado
  let caminho = '';
  if (s > 1e-4) {
    const a0 = ponto(0);
    caminho = `M ${a0.x.toFixed(2)} ${a0.y.toFixed(2)}`;
    for (let i = 1; i <= Math.floor(s + 1e-9); i++) { const a = ponto(Math.min(i, N - 1)); caminho += ` L ${a.x.toFixed(2)} ${a.y.toFixed(2)}`; }
    caminho += ` L ${agora.x.toFixed(2)} ${agora.y.toFixed(2)}`;
  }
  porAtributo(curva, 'd', caminho);
  curva.style.opacity = caminho ? '1' : '0';
  // 4–5. os controles de peso aparecem e se mexem junto com s
  ctx.entrada(rotPesos, P.prog(t, 'ajuste', 0, d.media), 'fade');
  const mexendo = Math.max(Math.sin(Math.PI * clamp(pAj)), clamp(pRep) > 0 && clamp(pRep) < 1 ? Math.min(1, 6 * clamp(pRep) * (1 - clamp(pRep)) + 0.4) : 0);
  controles.forEach((c, k) => {
    const pe = P.prog(t, 'ajuste', k * e, d.media);
    const i = Math.min(N - 2, Math.floor(s)), v = lerp(c.valores[i], c.valores[i + 1], s - i);
    c.trilho.style.opacity = clamp(pe).toFixed(3);
    c.trilho.style.transform = `scaleY(${clamp(pe).toFixed(4)})`;
    c.botao.style.opacity = clamp(pe).toFixed(3);
    c.botao.style.transform = `translateY(${((1 - v) * hPesos).toFixed(2)}px)`;
    c.vivo.style.opacity = clamp(mexendo).toFixed(3);
  });
  Q.seek(t);
}

export function key(t, ctx) { return ler(ESTADOS, ctx).P.chave(t); }

export function ancoras(ctx) { return ler(ESTADOS, ctx).P.ancoras(); }
