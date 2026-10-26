// versus.js — dois lados na mesma tela: A × B, antes → depois. Passos (revelar=pares): lados → par1 → par2 → … →
// [destaque]; (revelar=lados): lado1 → lado2 → [destaque].
// Em `pares`, cada linha de A aparece junto da linha correspondente de B, na mesma altura: a comparação é sempre do
// mesmo critério. A cena NÃO elege vencedor: `destaque` (0 ou 1) só existe se o roteiro disser qual lado destacar.
// É cena de TEXTO; número ou nome de modelo num dos lados é afirmação: fato_ids no storyboard e `fonte`.
import { params, guardar, ler, montarQuadro, escrever, caber, tamanho, exigir, marcarTermos, cartao, marcador, entrarBloco, clamp, encaixou, respiro } from './_ia.js';

const EXEMPLO = [
  { titulo: 'Programa tradicional', itens: ['Segue regras escritas por pessoas', 'Mesma entrada, mesma saída', 'Falha quando falta uma regra'] },
  { titulo: 'Modelo de linguagem', itens: ['Segue padrões aprendidos de textos', 'A resposta pode variar a cada pedido', 'Pode errar com texto convincente'] },
];

export const meta = {
  nome: 'versus',
  descricao: 'Versus: dois lados na mesma tela (A × B, antes → depois), com as linhas reveladas aos pares, critério a critério; a cena só destaca um lado se o roteiro mandar.',
  dur_padrao: 12,
  formatos: ['horizontal', 'vertical', 'quadrado'],
  alfa_padrao: false,
  grao: true,
  params: params({
    lados: { tipo: 'lista', min: 2, max: 2, padrao: EXEMPLO, descricao: 'os dois lados, cada um com título e de 1 a 5 linhas curtas (a linha i de um lado é comparada com a linha i do outro)',
      itens: { tipo: 'objeto', campos: { titulo: { tipo: 'texto', obrigatorio: true }, itens: { tipo: 'lista', obrigatorio: true, min: 1, max: 5, itens: { tipo: 'texto' } } } } },
    divisor: { tipo: 'texto', padrao: '×', descricao: 'o sinal entre os lados: "×", "→" (antes → depois), "ou"' },
    revelar: { tipo: 'opcao', opcoes: ['pares', 'lados'], padrao: 'pares', descricao: 'pares = linha a linha nos dois lados; lados = o lado A inteiro, depois o B' },
    destaque: { tipo: 'inteiro', padrao: null, min: 0, max: 1, descricao: 'lado que termina em destaque (0 = primeiro, 1 = segundo); null = nenhum' },
  }, { titulo: null, ilustrativo: 'texto' }),
};

export function roteiro(p, mov) {
  const d = mov.duracoes, e = mov.escalonamento, lados = p.lados || EXEMPLO;
  const nMax = Math.max(...lados.map((l) => (l.itens || []).length));
  const r = [];
  if (p.revelar === 'lados') lados.forEach((l, i) => r.push({ nome: 'lado' + (i + 1), tipo: i ? 'enfase' : 'entrada', anim: d.media * 2 + (l.itens || []).length * e * 3 }));
  else {
    r.push({ nome: 'lados', tipo: 'entrada', anim: d.media * 2 + d.curta });
    for (let k = 0; k < nMax; k++) r.push({ nome: 'par' + (k + 1), tipo: 'texto', anim: d.media * 1.5 + d.curta });
  }
  if (p.destaque != null) r.push({ nome: 'destaque', tipo: 'enfase', anim: d.media });
  return r;
}

const ESTADOS = new WeakMap();

export function build(palco, p, ctx) {
  const lados = p.lados;
  lados.forEach((l, i) => exigir(String(l.titulo).trim() && l.itens.every((x) => String(x).trim()), `lados[${i}]: título e linhas não podem ser vazios`));
  const Q = montarQuadro(palco, p, ctx, { roteiro: roteiro(p, ctx.DA.movimento) });
  const C = Q.conteudo, P = Q.P, cor = p.cor;
  const camada = ctx.el('div', 'versus-camada');
  Object.assign(camada.style, { position: 'absolute', left: '0', top: '0' });
  Q.raiz.appendChild(camada);
  const lado_a_lado = Q.horizontal;
  const pares = p.revelar !== 'lados';
  const nMax = Math.max(...lados.map((l) => l.itens.length));

  const U = caber((s) => {
    const tam = tamanho(ctx, 'h3', s), pad = tam * 0.8;
    const selo = escrever(ctx, camada, 'dados', String(p.divisor || '×'), { tam: tamanho(ctx, 'h3', s), cor: 'texto', classe: 'versus-divisor' });
    const dSelo = Math.max(selo.w, selo.h) + tam * 0.5;
    const meio = lado_a_lado ? dSelo + tam * 0.7 : dSelo * 0.5;       // vão entre os cartões (o selo mora nele)
    const w = lado_a_lado ? (C.w - meio) / 2 : C.w;
    const wTxt = w - 2 * pad - tam * 0.75;
    const cols = lados.map((l) => ({
      titulo: escrever(ctx, camada, 'titulo', String(l.titulo), { tam: tamanho(ctx, 'h2', s * 0.9), maxW: w - 2 * pad, maxLinhas: 2, classe: 'versus-titulo' }),
      linhas: l.itens.map((txt) => escrever(ctx, camada, 'corpo', '', { tam, maxW: wTxt, maxLinhas: 3, html: marcarTermos(ctx, String(txt), cor), classe: 'versus-linha' })),
    }));
    const hTit = lado_a_lado ? Math.max(...cols.map((c) => c.titulo.h)) : null;
    const vao = tam * 0.55, vTit = tam * 0.7;
    // altura de cada linha: em colunas lado a lado, o par divide a mesma altura
    const hLinha = (ci, k) => (lado_a_lado ? Math.max(...cols.map((c) => (c.linhas[k] ? c.linhas[k].h : 0))) : cols[ci].linhas[k].h);
    const hCartao = (ci) => pad + (hTit ?? cols[ci].titulo.h) + vTit + Array.from({ length: lado_a_lado ? nMax : cols[ci].linhas.length }, (_, k) => hLinha(ci, k)).reduce((a, b) => a + b, 0)
      + ((lado_a_lado ? nMax : cols[ci].linhas.length) - 1) * vao + pad;
    const hs = [hCartao(0), hCartao(1)];
    const h = lado_a_lado ? Math.max(...hs) : hs[0] + meio + hs[1];
    return { cabe: h <= C.h * respiro(s), tam, pad, selo, dSelo, meio, w, cols, hTit, vao, vTit, hLinha, hs, h };
  }, () => camada.replaceChildren(), { inicio: Q.horizontal ? 1.15 : 1 });
  encaixou(U, C, 'versus');

  const y0 = Math.round(C.y + Math.max(0, (C.h - U.h) / 2));
  const cartoes = lados.map((l, ci) => {
    const x = lado_a_lado ? C.x + ci * (U.w + U.meio) : C.x;
    const y = lado_a_lado ? y0 : y0 + ci * (U.hs[0] + U.meio);
    const hc = lado_a_lado ? U.h : U.hs[ci];
    const c = cartao(ctx, { w: U.w, h: hc, cor });
    camada.appendChild(c.el);
    c.em(x, y);
    const col = U.cols[ci];
    c.miolo.appendChild(col.titulo.el);
    col.titulo.em(U.pad, U.pad);
    const fio = ctx.el('div', 'versus-fio');
    const yFio = U.pad + (U.hTit ?? col.titulo.h) + U.vTit * 0.5;
    Object.assign(fio.style, { position: 'absolute', left: Math.round(U.pad) + 'px', top: Math.round(yFio) + 'px', width: Math.round(U.w - 2 * U.pad) + 'px', height: Math.max(1, ctx.traco * 0.75).toFixed(1) + 'px',
      background: ctx.alfa('texto_suave', 0.6), transformOrigin: 'left center' });
    c.miolo.appendChild(fio);
    let yl = U.pad + (U.hTit ?? col.titulo.h) + U.vTit;
    const linhas = col.linhas.map((ln, k) => {
      const m = marcador(ctx, { tipo: 'quadrado', lado: U.tam * 0.26, cor });
      c.miolo.append(m.el, ln.el);
      const hPrimeira = ln.h / ln.linhas;
      Object.assign(m.el.style, { left: Math.round(U.pad) + 'px', top: Math.round(yl + (hPrimeira - m.h) / 2) + 'px' });
      ln.em(U.pad + U.tam * 0.75, yl);
      yl += U.hLinha(ci, k) + U.vao;
      return { ln, m, letras: String(l.itens[k]).replace(/\*/g, '').length };
    });
    return { c, titulo: col.titulo, fio, linhas, letras: String(l.titulo).length };
  });
  // selo do meio (o sinal): um disco com filete, entre os dois cartões
  const disco = ctx.el('div', 'versus-disco');
  const dx = lado_a_lado ? C.x + U.w + (U.meio - U.dSelo) / 2 : C.x + (C.w - U.dSelo) / 2;
  const dy = lado_a_lado ? y0 + (U.h - U.dSelo) / 2 : y0 + U.hs[0] + (U.meio - U.dSelo) / 2;
  Object.assign(disco.style, { position: 'absolute', left: Math.round(dx) + 'px', top: Math.round(dy) + 'px', width: Math.round(U.dSelo) + 'px', height: Math.round(U.dSelo) + 'px', borderRadius: '50%', boxSizing: 'border-box',
    background: ctx.cor('fundo'), border: `${Math.max(1.5, ctx.traco).toFixed(1)}px solid ${ctx.cor('texto_suave')}` });
  camada.appendChild(disco);
  disco.appendChild(U.selo.el);
  U.selo.em((U.dSelo - U.selo.w) / 2 - Math.max(1.5, ctx.traco), (U.dSelo - U.selo.h) / 2 - Math.max(1.5, ctx.traco));

  guardar(ESTADOS, ctx, { ctx, Q, P, p, cartoes, disco, pares, nMax });
  return Q.layout({ revelar: pares ? 'pares' : 'lados', disposicao: lado_a_lado ? 'lado_a_lado' : 'empilhado', escala: +U.escala.toFixed(3), tamanho_linha: +U.tam.toFixed(1),
    bloco: { x: Math.round(C.x), y: y0, w: Math.round(C.w), h: Math.round(U.h) } });
}

export function seek(t, ctxArg) {
  const { ctx, Q, P, p, cartoes, disco, pares, nMax } = ler(ESTADOS, ctxArg);
  const d = ctx.DA.movimento.duracoes, e = ctx.escalonamento;
  const pDest = p.destaque != null ? P.prog(t, 'destaque', 0, d.media, 'enfase') : 0;
  cartoes.forEach((cz, ci) => {
    const passoLado = pares ? 'lados' : 'lado' + (ci + 1);
    const at = pares ? ci * d.curta : 0;
    entrarBloco(ctx, cz.c.el, P.prog(t, passoLado, at, d.media));
    ctx.entrada(cz.titulo.el, P.prog(t, passoLado, at + d.media * 0.5, d.media), undefined, { n: cz.letras });
    const pf = P.prog(t, passoLado, at + d.media, d.media);
    cz.fio.style.transform = `scaleX(${clamp(pf).toFixed(4)})`;
    cz.fio.style.opacity = pf > 0 ? '1' : '0';
    cz.linhas.forEach((li, k) => {
      let pe, daVez;
      if (pares) {
        pe = P.prog(t, 'par' + (k + 1), ci * d.media * 0.5, d.media);
        const proximo = k < nMax - 1 ? P.prog(t, 'par' + (k + 2), 0, d.curta) : pDest;
        daVez = clamp(P.prog(t, 'par' + (k + 1), ci * d.media * 0.5, d.media, 'enfase')) * (1 - clamp(proximo));
        if (k === nMax - 1 && p.destaque == null) daVez *= 1 - P.prog(t, 'par' + (k + 1), d.media * 1.5, d.curta);
      } else {
        pe = P.prog(t, passoLado, d.media + k * e * 3, d.media);
        daVez = 0;
      }
      ctx.entrada(li.ln.el, pe, undefined, { n: li.letras });
      li.m.el.style.opacity = clamp(pe * 2).toFixed(3);
      li.m.misturar(daVez);
    });
    const escolhido = p.destaque === ci;
    cz.c.estado({ realce: escolhido ? pDest : 0, cheio: escolhido ? pDest : 0, apagado: p.destaque != null && !escolhido ? pDest : 0 });
  });
  const pDisco = pares ? P.prog(t, 'lados', d.media, d.media, 'enfase') : P.prog(t, 'lado2', 0, d.media, 'enfase');
  disco.style.opacity = clamp(pDisco * 1.5).toFixed(3);
  disco.style.transform = `scale(${(0.7 + 0.3 * Math.min(pDisco, 1.2)).toFixed(4)})`;
  Q.seek(t);
}

export function key(t, ctx) { return ler(ESTADOS, ctx).P.chave(t); }

export function ancoras(ctx) { return ler(ESTADOS, ctx).P.ancoras(); }
