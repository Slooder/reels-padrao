// proximo_token.js — a distribuição de probabilidade do próximo token, o efeito da temperatura, o sorteio e a
// geração token a token. Passos: contexto → distribuicao → [temperatura] → sorteio → anexa → rodada2 → rodada3 …
// O sorteio é DE VERDADE: um número pseudoaleatório (param `semente`) cai numa régua de 0 a 1 dividida conforme as
// probabilidades; a cena nunca escolhe "à mão" o token que convém. Se as rodadas seguintes foram escritas para outro
// token (campo depois_de), o build recusa e sugere uma semente que produz o caminho esperado.
// Simplificação declarada em references/didatica.md: só 2 a 6 candidatos por rodada (o vocabulário real tem dezenas
// de milhares) e probabilidades inventadas.
import { params, guardar, ler, montarQuadro, caixaToken, rotulo, barra, contador, comTemperatura, sortear, indiceDoMaior, conferirDistribuicao, clamp, lerp, num, pct } from './_ia.js';

const EXEMPLO = {
  contexto: 'A capital da França é',
  rodadas: [
    { depois_de: null, candidatos: [{ token: ' Paris', prob: 0.82 }, { token: ' uma', prob: 0.08 }, { token: ' a', prob: 0.05 }, { token: ' conhecida', prob: 0.03 }, { token: ' Lyon', prob: 0.02 }] },
    { depois_de: ' Paris', candidatos: [{ token: ',', prob: 0.46 }, { token: '.', prob: 0.34 }, { token: ' e', prob: 0.12 }, { token: ' desde', prob: 0.05 }, { token: '!', prob: 0.03 }] },
    { depois_de: ',', candidatos: [{ token: ' a', prob: 0.4 }, { token: ' cidade', prob: 0.28 }, { token: ' uma', prob: 0.18 }, { token: ' e', prob: 0.09 }, { token: ' onde', prob: 0.05 }] },
  ],
};
const PAUSA_T = 0.5;                                        // segundos parado em cada temperatura visitada

export const meta = {
  nome: 'proximo_token',
  descricao: 'Próximo token: as probabilidades em barras, o que a temperatura faz com elas, o sorteio numa régua de 0 a 1 e a geração token a token.',
  dur_padrao: 20,
  formatos: ['horizontal', 'vertical', 'quadrado'],
  alfa_padrao: false,
  grao: true,
  params: params({
    contexto: { tipo: 'texto', padrao: EXEMPLO.contexto, descricao: 'o texto já escrito (o prompt)' },
    rodadas: { tipo: 'lista', min: 1, max: 4, padrao: EXEMPLO.rodadas, descricao: 'uma rodada por token gerado: os candidatos e a probabilidade de cada um (somando 1, na temperatura 1)',
      itens: { tipo: 'objeto', campos: {
        depois_de: { tipo: 'texto', padrao: null, descricao: 'token que precisa ter saído na rodada anterior para esta fazer sentido (a cena confere contra o sorteio)' },
        candidatos: { tipo: 'lista', obrigatorio: true, min: 2, max: 6, itens: { tipo: 'objeto', campos: { token: { tipo: 'texto', obrigatorio: true }, prob: { tipo: 'numero', obrigatorio: true, min: 0, max: 1 } } } },
      } } },
    temperatura: { tipo: 'numero', padrao: 1, min: 0.05, max: 3, descricao: 'temperatura usada nos sorteios (1 = a distribuição como o modelo calculou)' },
    comparar: { tipo: 'lista', padrao: [0.3, 1.6], max: 3, itens: { tipo: 'numero', min: 0.05, max: 3 }, descricao: 'temperaturas mostradas antes do sorteio, para ver as barras mudarem ([] pula o passo)' },
    escolha: { tipo: 'opcao', opcoes: ['sorteio', 'maior'], padrao: 'sorteio', descricao: 'sorteio = amostra conforme as probabilidades; maior = sempre o mais provável (decodificação gulosa)' },
    semente: { tipo: 'inteiro', padrao: 20, min: 0, descricao: 'semente do sorteio: a mesma semente dá sempre o mesmo resultado' },
  }, { titulo: 'O próximo token' }),
};

function sequenciaT(p) {
  const seq = [1, ...(p.comparar == null ? [0.3, 1.6] : p.comparar), p.temperatura ?? 1];
  return seq.filter((v, i) => i === 0 || Math.abs(v - seq[i - 1]) > 1e-6);
}

export function roteiro(p, mov) {
  const d = mov.duracoes, e = mov.escalonamento;
  const rodadas = p.rodadas || EXEMPLO.rodadas;
  const tour = sequenciaT(p);
  const r = [
    { nome: 'contexto', tipo: 'texto', anim: d.longa },
    { nome: 'distribuicao', tipo: 'entrada', anim: d.longa + rodadas[0].candidatos.length * e * 2 },
  ];
  if (tour.length > 1) r.push({ nome: 'temperatura', tipo: 'enfase', anim: (tour.length - 1) * (d.longa + PAUSA_T), leitura: 0.4 });
  r.push({ nome: 'sorteio', tipo: 'enfase', anim: d.media * 2 + d.longa * 1.5 });
  r.push({ nome: 'anexa', tipo: 'texto', anim: d.media + d.curta });
  for (let k = 1; k < rodadas.length; k++) r.push({ nome: 'rodada' + (k + 1), tipo: 'enfase', anim: d.media * 4.5 + d.longa * 1.5 });
  return r;
}

const LEGENDA = {
  contexto: 'O texto escrito até aqui', distribuicao: 'O modelo dá uma *probabilidade* a cada continuação',
  temperatura: 'A *temperatura* concentra ou espalha as chances', sorteio: 'Um *sorteio* decide o próximo token',
  maior: 'Aqui vence sempre o *mais provável*', anexa: 'O token entra no texto', rodada: 'e tudo se repete, *um token por vez*',
};

/** Sorteia todas as rodadas com a semente dada. → [{ u, i, pT }] */
function sortearRodadas(rodadas, temperatura, escolha, semente, rngDe) {
  const rng = rngDe(semente);
  return rodadas.map((r) => {
    const pT = comTemperatura(r.candidatos.map((c) => c.prob), temperatura);
    const u = rng();
    return { u, pT, i: escolha === 'maior' ? indiceDoMaior(pT) : sortear(pT, u) };
  });
}
function primeiraDivergencia(rodadas, sorteios) {
  for (let k = 1; k < rodadas.length; k++) {
    const saiu = rodadas[k - 1].candidatos[sorteios[k - 1].i].token;
    if (rodadas[k].depois_de != null && rodadas[k].depois_de !== saiu) return { k, saiu, esperado: rodadas[k].depois_de };
  }
  return null;
}

const ESTADOS = new WeakMap();

export function build(palco, p, ctx) {
  const rodadas = p.rodadas;
  rodadas.forEach((r, k) => conferirDistribuicao(r.candidatos.map((c) => c.prob), `rodada ${k + 1}: as probabilidades dos candidatos`));
  const sorteios = sortearRodadas(rodadas, p.temperatura, p.escolha, p.semente, ctx.rng);
  const div = primeiraDivergencia(rodadas, sorteios);
  if (div) {
    let dica = 'reescreva os candidatos das rodadas seguintes para esse caminho';
    if (p.escolha === 'sorteio') {
      for (let s = 0; s < 400; s++) if (!primeiraDivergencia(rodadas, sortearRodadas(rodadas, p.temperatura, p.escolha, s, ctx.rng))) { dica = `use semente=${s}, que sorteia o caminho esperado, ou ${dica}`; break; }
    }
    throw new Error(`o sorteio da rodada ${div.k} (semente ${p.semente}, temperatura ${num(p.temperatura, 2)}) deu ${JSON.stringify(div.saiu)}, mas a rodada ${div.k + 1} foi escrita para depois de ${JSON.stringify(div.esperado)}: ${dica}. A cena não força o resultado do sorteio`);
  }
  const tour = sequenciaT(p);
  const rot = roteiro(p, ctx.DA.movimento);
  const legendas = rot.map((r) => (r.nome.startsWith('rodada') ? LEGENDA.rodada : r.nome === 'sorteio' && p.escolha === 'maior' ? LEGENDA.maior : LEGENDA[r.nome]));
  const Q = montarQuadro(palco, p, ctx, { roteiro: rot, legendas });
  const C = Q.conteudo, P = Q.P, cor = p.cor;
  const camada = ctx.el('div', 'pt-camada');
  Object.assign(camada.style, { position: 'absolute', left: '0', top: '0' });
  Q.raiz.appendChild(camada);
  const vao = ctx.px(0.036);

  // regiões: texto à esquerda e painel à direita (horizontal) ou empilhados (vertical)
  const wTexto = Q.horizontal ? C.w * 0.4 : C.w;
  const painel = Q.horizontal ? { x: C.x + wTexto + vao * 1.6, w: C.w - wTexto - vao * 1.6 } : { x: C.x, w: C.w };

  // o texto: contexto + um trecho por rodada (ainda invisível), com a lacuna de onde o próximo token vai entrar
  const texto = ctx.texto('corpo', '', { tam: ctx.tam(Q.horizontal ? 'h2' : 'h3'), cor: 'texto', wrap: true, maxW: wTexto, classe: 'pt-texto', html: '' });
  texto.style.position = 'absolute';
  texto._inner.style.whiteSpace = 'pre-wrap';
  const trechoCtx = ctx.el('span', 'pt-contexto', p.contexto);
  texto._inner.appendChild(trechoCtx);
  const novos = sorteios.map((s, k) => {
    const tok = rodadas[k].candidatos[s.i].token;
    const visivel = tok.replace(/^\s+/, '');
    if (visivel.length < tok.length) texto._inner.appendChild(document.createTextNode(tok.slice(0, tok.length - visivel.length)));
    const span = ctx.el('span', 'pt-novo', visivel);
    span.style.color = ctx.cor(cor);
    texto._inner.appendChild(span);
    return { span, tok };
  });
  camada.appendChild(texto);
  ctx.ajustar_texto(texto, wTexto, { min: ctx.tam('corpo'), maxLinhas: Q.horizontal ? 4 : 2 });
  const mTexto = ctx.medir(texto);

  // painel: cabeçalho (rótulo + temperatura), linhas de candidatos, régua do sorteio
  const rotPainel = rotulo(ctx, 'próximo token', { tam: ctx.tam('nota') });
  camada.appendChild(rotPainel);
  const mRotP = ctx.medir(rotPainel);
  const temp = contador(ctx, { tam: ctx.tam('corpo'), cor: 'texto', formato: (v) => `temperatura ${num(v, 1)}`, modelo: 'temperatura 0,0' });
  camada.appendChild(temp.el);
  const mTemp = temp.medir();
  const hCab = Math.max(mRotP.h, mTemp.h);
  const maxCand = Math.max(...rodadas.map((r) => r.candidatos.length));
  const hRegua = ctx.px(0.03);
  const rot0 = rotulo(ctx, '0', { tam: ctx.tam('nota') }), rot1 = rotulo(ctx, '1', { tam: ctx.tam('nota') });
  const rotRegua = rotulo(ctx, p.escolha === 'maior' ? 'sem sorteio: fica o maior' : 'sorteio: um ponto ao acaso na régua', { tam: ctx.tam('nota') });
  camada.append(rot0, rot1, rotRegua);
  const mR0 = ctx.medir(rot0), mR1 = ctx.medir(rot1), mRR = ctx.medir(rotRegua);
  const hBlocoRegua = ctx.px(0.014) + hRegua + ctx.px(0.008) + mR0.h;
  const hTextoBloco = Q.horizontal ? 0 : mTexto.h + vao;
  const hLinhasMax = C.h - hTextoBloco - hCab - ctx.px(0.018) - vao * 0.8 - hBlocoRegua;
  let tamFicha = ctx.tam(Q.horizontal ? 'h3' : 'corpo');
  let hFicha = tamFicha * 1.65;
  let passo = Math.min(hFicha * 1.22, hLinhasMax / maxCand);
  if (passo < hFicha * 1.06) { tamFicha = Math.max(ctx.tam('nota'), tamFicha * passo / (hFicha * 1.06)); hFicha = tamFicha * 1.65; passo = Math.min(passo, hFicha * 1.22); }
  const hPainel = hCab + ctx.px(0.018) + maxCand * passo + vao * 0.8 + hBlocoRegua;
  const hTudo = Q.horizontal ? Math.max(mTexto.h, hPainel) : hTextoBloco + hPainel;
  const y0 = C.y + Math.max(0, (C.h - hTudo) / 2);
  const yPainel = Q.horizontal ? y0 + (hTudo - hPainel) / 2 : y0 + hTextoBloco;
  ctx.place(texto, { x: Math.round(C.x), y: Math.round(Q.horizontal ? y0 + (hTudo - mTexto.h) / 2 : y0) });
  ctx.place(rotPainel, { x: Math.round(painel.x), y: Math.round(yPainel + hCab - mRotP.h) });
  ctx.place(temp.el, { x: Math.round(painel.x + painel.w - mTemp.w), y: Math.round(yPainel + hCab - mTemp.h) });
  const yLinhas = yPainel + hCab + ctx.px(0.018);
  const yRegua = yLinhas + maxCand * passo + vao * 0.8 + ctx.px(0.014);
  ctx.place(rot0, { x: Math.round(painel.x), y: Math.round(yRegua + hRegua + ctx.px(0.008)) });
  ctx.place(rot1, { x: Math.round(painel.x + painel.w - mR1.w), y: Math.round(yRegua + hRegua + ctx.px(0.008)) });
  ctx.place(rotRegua, { x: Math.round(painel.x + (painel.w - mRR.w) / 2), y: Math.round(yRegua + hRegua + ctx.px(0.008)) });

  // lacuna e realce de cada token novo (medidos depois de o texto estar no lugar)
  for (const nv of novos) {
    const r = ctx.rectDe(nv.span);
    const f = Math.max(3, texto._tam * 0.1);
    const xa = Math.max(C.x, r.x - f), xb = Math.min(C.x1, r.x + r.w + f);      // token no começo ou no fim da linha: a folga não sai da zona
    const lacuna = ctx.el('div', 'pt-lacuna');
    Object.assign(lacuna.style, { position: 'absolute', left: xa.toFixed(1) + 'px', top: (r.y + r.h * 0.08).toFixed(1) + 'px', width: (xb - xa).toFixed(1) + 'px', height: (r.h * 0.84).toFixed(1) + 'px', boxSizing: 'border-box',
      border: `${Math.max(1, ctx.traco * 0.75).toFixed(1)}px dashed ${ctx.cor('texto_suave')}`, borderRadius: ctx.raio + 'px' });
    const brilho = ctx.el('div', 'pt-brilho');
    Object.assign(brilho.style, { position: 'absolute', left: xa.toFixed(1) + 'px', top: (r.y + r.h * 0.08).toFixed(1) + 'px', width: (xb - xa).toFixed(1) + 'px', height: (r.h * 0.84).toFixed(1) + 'px',
      background: ctx.alfa(cor, 0.2), borderRadius: ctx.raio + 'px' });
    camada.insertBefore(brilho, texto);
    camada.insertBefore(lacuna, texto);
    Object.assign(nv, { lacuna, brilho });
  }

  // um grupo por rodada: fichas, barras, percentuais e os trechos da régua
  const wPct = (() => { const t = rotulo(ctx, '100%', { papel: 'dados', tam: tamFicha, cor: 'texto' }); camada.appendChild(t); const w = ctx.medir(t).w; t.remove(); return w; })();
  const grupos = rodadas.map((r, k) => {
    const g = ctx.el('div', 'pt-grupo');
    Object.assign(g.style, { position: 'absolute', left: '0', top: '0' });
    camada.appendChild(g);
    const fichas = r.candidatos.map((c) => { const f = caixaToken(ctx, c.token, { tam: tamFicha, cor, modo: 'contorno' }); g.appendChild(f.el); f.medir(); return f; });
    return { g, fichas, r, k };
  });
  const wFicha = Math.max(...grupos.flatMap((g) => g.fichas.map((f) => f.w)));
  const xBarra = painel.x + wFicha + ctx.px(0.018);
  const wBarra = painel.w - wFicha - ctx.px(0.018) - wPct - ctx.px(0.016);
  const fresta = Math.max(2, ctx.px(0.003));
  for (const gr of grupos) {
    gr.linhas = gr.r.candidatos.map((c, i) => {
      const f = gr.fichas[i];
      const y = yLinhas + i * passo;
      ctx.place(f.el, { x: Math.round(painel.x), y: Math.round(y + (passo - f.h) / 2) });
      const b = barra(ctx, { w: wBarra, h: Math.max(8, Math.min(f.h * 0.5, passo * 0.42)), cor });
      gr.g.appendChild(b.el);
      ctx.place(b.el, { x: Math.round(xBarra), y: Math.round(y + (passo - b.h) / 2) });
      const v = contador(ctx, { tam: tamFicha, cor: 'texto', formato: (x) => (x > 0 && x < 0.005 ? '<1%' : pct(x)), modelo: '100%' });
      gr.g.appendChild(v.el);
      const mv = v.medir();
      ctx.place(v.el, { x: Math.round(painel.x + painel.w - mv.w), y: Math.round(y + (passo - mv.h) / 2) });
      v.el._inner.style.textAlign = 'right'; v.el._inner.style.display = 'block'; v.el._inner.style.width = mv.w + 'px';
      const seg = ctx.el('div', 'pt-trecho');
      Object.assign(seg.style, { position: 'absolute', top: Math.round(yRegua) + 'px', height: hRegua + 'px' });
      const base = ctx.el('div'); Object.assign(base.style, { position: 'absolute', inset: '0', background: ctx.alfa('texto_suave', 0.55), borderRadius: Math.min(ctx.raio, hRegua / 2) + 'px' });
      const viva = ctx.el('div'); Object.assign(viva.style, { position: 'absolute', inset: '0', background: ctx.cor(cor), borderRadius: Math.min(ctx.raio, hRegua / 2) + 'px', opacity: '0' });
      seg.append(base, viva);
      gr.g.appendChild(seg);
      return { f, b, v, seg, viva, prob: c.prob };
    });
  }
  // ponteiro do sorteio
  const agulha = ctx.el('div', 'pt-agulha');
  const hAg = hRegua + ctx.px(0.022);
  Object.assign(agulha.style, { position: 'absolute', left: Math.round(painel.x) + 'px', top: Math.round(yRegua - ctx.px(0.011)) + 'px', width: '0px', height: hAg + 'px' });
  const haste = ctx.el('div'); Object.assign(haste.style, { position: 'absolute', left: (-Math.max(1.5, ctx.traco * 0.75)).toFixed(1) + 'px', top: '0', width: Math.max(3, ctx.traco * 1.5).toFixed(1) + 'px', height: '100%', background: ctx.cor('texto'), borderRadius: '2px' });
  const cabeca = ctx.el('div'); const rc = Math.max(5, ctx.px(0.007));
  Object.assign(cabeca.style, { position: 'absolute', left: -rc + 'px', top: -rc + 'px', width: 2 * rc + 'px', height: 2 * rc + 'px', borderRadius: '50%', background: ctx.cor('texto') });
  agulha.append(haste, cabeca);
  camada.appendChild(agulha);

  guardar(ESTADOS, ctx, { ctx, Q, P, p, rodadas, sorteios, tour, grupos, novos, trechoCtx, texto, rotPainel, temp, rot0, rot1, rotRegua, agulha, painel, fresta, maior: p.escolha === 'maior',
    temTemperatura: tour.length > 1, nCtx: p.contexto.length });
  return Q.layout({ sorteios: sorteios.map((s, k) => ({ u: +s.u.toFixed(4), token: rodadas[k].candidatos[s.i].token, prob: +s.pT[s.i].toFixed(4) })), temperaturas: tour,
    texto: ctx.rectDe(texto), painel: { x: Math.round(painel.x), y: Math.round(yPainel), w: Math.round(painel.w), h: Math.round(hPainel) }, tamanho_ficha: +tamFicha.toFixed(1) });
}

export function seek(t, ctxArg) {
  const S = ler(ESTADOS, ctxArg);
  const { ctx, Q, P, p, sorteios, tour, grupos, novos, trechoCtx, rotPainel, temp, rot0, rot1, rotRegua, agulha, painel, fresta, maior } = S;
  const d = ctx.DA.movimento.duracoes, e = ctx.escalonamento;
  const R = grupos.length;
  // temperatura em t: visita cada valor do passeio com a curva suave da DA e para um pouco em cada um
  let T = S.temTemperatura ? tour[0] : p.temperatura;
  if (S.temTemperatura && P.passou(t, 'temperatura')) {
    const k = P.indice('temperatura');
    const tau = (t - P.t[k]) / P.e[k];
    const j = Math.min(tour.length - 2, Math.floor(tau / (d.longa + PAUSA_T)));
    T = lerp(tour[j], tour[j + 1], ctx.ease('suave')(clamp((tau - j * (d.longa + PAUSA_T)) / d.longa)));
  }
  // linha do tempo de cada rodada (a 1ª espalha em passos próprios; as seguintes cabem num passo só)
  const tempo = (k) => {
    if (k === 0) {
      return { entra: (i) => P.prog(t, 'distribuicao', i * e * 2, d.longa, 'enfase'), grupo: P.prog(t, 'distribuicao', 0, d.media), regua: P.prog(t, 'sorteio', 0, d.media),
        ponteiro: P.prog(t, 'sorteio', d.media, d.longa * 1.5, 'suave'), acerto: P.prog(t, 'sorteio', d.media + d.longa * 1.5, d.media, 'enfase'), anexa: P.prog(t, 'anexa', 0, d.media, 'enfase'),
        lacuna: P.prog(t, 'distribuicao', 0, d.media), comecouSorteio: P.passou(t, 'sorteio') };
    }
    const nome = 'rodada' + (k + 1);
    return { entra: (i) => P.prog(t, nome, d.media * 0.5 + i * e, d.media, 'enfase'), grupo: P.prog(t, nome, d.media * 0.5, d.media), regua: P.prog(t, nome, d.media * 0.5, d.media),
      ponteiro: P.prog(t, nome, d.media * 2, d.longa * 1.5, 'suave'), acerto: P.prog(t, nome, d.media * 2 + d.longa * 1.5, d.media, 'enfase'), anexa: P.prog(t, nome, d.media * 3.5 + d.longa * 1.5, d.media, 'enfase'),
      lacuna: P.prog(t, nome, d.media * 0.5, d.media), comecouSorteio: t >= P.t[P.indice(nome)] + d.media * 2 * P.e[P.indice(nome)] };
  };
  const some = (k) => (k < R - 1 ? P.prog(t, 'rodada' + (k + 2), 0, d.media * 0.5) : 0);
  ctx.entrada(S.texto, P.lin(t, 'contexto', 0, d.longa), undefined, { n: S.nCtx });
  ctx.entrada(rotPainel, P.prog(t, 'distribuicao', 0, d.media), 'fade');
  ctx.entrada(temp.el, S.temTemperatura ? P.prog(t, 'temperatura', 0, d.curta) : (Math.abs(p.temperatura - 1) > 1e-6 ? P.prog(t, 'distribuicao', 0, d.media) : 0), 'fade');
  temp.definir(T);
  let rodadaDoPonteiro = -1, reguaVisivel = 0;
  grupos.forEach((gr, k) => {
    const tk = tempo(k), sai = some(k), s = sorteios[k];
    gr.g.style.opacity = (clamp(tk.grupo) * (1 - sai)).toFixed(3);
    const probs = k === 0 ? comTemperatura(gr.linhas.map((l) => l.prob), T) : s.pT;
    const maiorP = Math.max(...probs, 1e-9);
    const util = painel.w - fresta * (probs.length - 1);
    let x = painel.x;
    gr.linhas.forEach((l, i) => {
      const pe = tk.entra(i), q = clamp(pe), escolhido = i === s.i;
      ctx.entrada(l.f.el, q, 'fade');
      l.f.estado({ caixa: 1, realce: escolhido ? clamp(tk.acerto) : 0 });
      l.b.estado({ fracao: (probs[i] / Math.max(maiorP, 0.5)) * clamp(pe, 0, 1.04), realce: escolhido ? clamp(tk.acerto) : 0, trilha: q });
      l.v.definir(probs[i] * q);
      l.v.el.style.opacity = q.toFixed(3);
      const larg = Math.max(0, util * probs[i]);
      l.seg.style.left = x.toFixed(2) + 'px'; l.seg.style.width = larg.toFixed(2) + 'px';
      l.seg.style.opacity = clamp(tk.regua).toFixed(3);
      l.viva.style.opacity = (escolhido ? clamp(tk.acerto) : 0).toFixed(3);
      x += larg + fresta;
    });
    if (tk.comecouSorteio) rodadaDoPonteiro = k;
    reguaVisivel = Math.max(reguaVisivel, clamp(tk.regua) * (1 - sai));
    // o token sorteado entra no texto: a lacuna some, o trecho aparece com o realce da rodada
    const nv = novos[k];
    nv.span.style.opacity = clamp(tk.anexa).toFixed(3);
    nv.lacuna.style.opacity = (clamp(tk.lacuna) * (1 - clamp(tk.anexa))).toFixed(3);
    nv.brilho.style.opacity = (clamp(tk.anexa) * (1 - sai)).toFixed(3);
    nv.brilho.style.transform = `scale(${lerp(1.18, 1, clamp(tk.anexa)).toFixed(4)})`;
  });
  for (const r of [rot0, rot1, rotRegua]) ctx.entrada(r, reguaVisivel, 'fade');
  if (rodadaDoPonteiro < 0 || maior) agulha.style.opacity = '0';
  else {
    const tk = tempo(rodadaDoPonteiro), s = sorteios[rodadaDoPonteiro];
    agulha.style.opacity = (clamp(tk.regua) * (1 - some(rodadaDoPonteiro))).toFixed(3);
    // posição do ponto sorteado na régua: u na escala útil + uma fresta por trecho que ficou para trás
    const alvo = (painel.w - fresta * (s.pT.length - 1)) * s.u + fresta * s.i;
    agulha.style.transform = `translateX(${(alvo * clamp(tk.ponteiro)).toFixed(2)}px)`;
  }
  if (rodadaDoPonteiro < 0 || maior) agulha.style.transform = 'none';
  Q.seek(t);
}

export function key(t, ctx) { return ler(ESTADOS, ctx).P.chave(t); }

export function ancoras(ctx) { return ler(ESTADOS, ctx).P.ancoras(); }
