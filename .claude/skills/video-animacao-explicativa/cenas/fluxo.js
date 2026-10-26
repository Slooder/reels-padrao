// fluxo.js — diagrama genérico de caixas e setas montado dos parâmetros: nós, ligações e a ordem de revelação.
// Passos: passo1 → passo2 → … → [destaque]; cada passo revela os nós de um item de `ordem` (padrão: uma camada do
// diagrama por passo) e as ligações cujas duas pontas já estão na tela. O que entra fica em destaque até o próximo.
// A disposição sai das ligações: cada nó fica uma camada depois do último que aponta para ele; no quadro horizontal o
// fluxo corre da esquerda para a direita, no vertical de cima para baixo. Ligação que volta (um ciclo) é desenhada
// como arco por fora — é assim que se mostra um laço. `coluna` e `linha` em cada nó fixam a posição à mão.
// É cena de TEXTO: o diagrama afirma o que o roteiro afirma. Confira-o com references/didatica.md — uma seta é uma
// afirmação ("isto vai para aquilo") tanto quanto uma frase.
import { params, guardar, ler, montarQuadro, escrever, etiqueta, caber, tamanho, exigir, cartao, entrarBloco, camadaSvg, setaCurva, pontoNaCurva, clamp, encaixou, respiro } from './_ia.js';

const EXEMPLO = {
  nos: [{ id: 'texto', rotulo: 'Texto', sub: 'o que você escreve' }, { id: 'tokens', rotulo: 'Tokens', sub: 'pedaços numerados' }, { id: 'modelo', rotulo: 'Modelo', sub: 'faz as contas' },
    { id: 'probs', rotulo: 'Chances', sub: 'de cada continuação' }, { id: 'proximo', rotulo: 'Próximo token', sub: 'sorteado' }],
  ligacoes: [{ de: 'texto', para: 'tokens' }, { de: 'tokens', para: 'modelo' }, { de: 'modelo', para: 'probs' }, { de: 'probs', para: 'proximo' }, { de: 'proximo', para: 'tokens', rotulo: 'volta para a fila' }],
};

export const meta = {
  nome: 'fluxo',
  descricao: 'Fluxo: diagrama de caixas e setas a partir de nós e ligações, revelado passo a passo na ordem pedida; a disposição sai das ligações (esquerda → direita no horizontal, cima → baixo no vertical) e ciclos viram arcos.',
  dur_padrao: 13,
  formatos: ['horizontal', 'vertical', 'quadrado'],
  alfa_padrao: false,
  grao: true,
  params: params({
    nos: { tipo: 'lista', min: 2, max: 9, padrao: EXEMPLO.nos, descricao: 'as caixas: id (curto, sem espaço), rótulo e, se quiser, uma linha de apoio; coluna/linha (a partir de 0) fixam a posição',
      itens: { tipo: 'objeto', campos: { id: { tipo: 'texto', obrigatorio: true }, rotulo: { tipo: 'texto', obrigatorio: true }, sub: { tipo: 'texto', padrao: null },
        coluna: { tipo: 'inteiro', padrao: null, min: 0, max: 5 }, linha: { tipo: 'inteiro', padrao: null, min: 0, max: 3 } } } },
    ligacoes: { tipo: 'lista', max: 14, padrao: EXEMPLO.ligacoes, descricao: 'as setas: de → para (ids dos nós), com rótulo opcional; tracejada = ligação opcional ou indireta',
      itens: { tipo: 'objeto', campos: { de: { tipo: 'texto', obrigatorio: true }, para: { tipo: 'texto', obrigatorio: true }, rotulo: { tipo: 'texto', padrao: null }, tracejada: { tipo: 'booleano', padrao: false } } } },
    ordem: { tipo: 'lista', padrao: null, max: 9, itens: { tipo: 'lista', min: 1, itens: { tipo: 'texto' } }, descricao: 'ordem de revelação: uma lista de ids por passo (padrão: uma camada por passo); cada nó aparece exatamente uma vez' },
    destaque: { tipo: 'texto', padrao: null, descricao: 'id do nó que termina em destaque, num passo final (null = nenhum)' },
    direcao: { tipo: 'opcao', opcoes: ['auto', 'horizontal', 'vertical'], padrao: 'auto', descricao: 'sentido do fluxo: auto = horizontal no quadro deitado, vertical no quadro em pé' },
  }, { titulo: null, ilustrativo: 'texto' }),
};

/** Lê nós e ligações e devolve a estrutura do diagrama (função pura: roda no Node, antes do render). */
function analisar(p) {
  const nos = p.nos || EXEMPLO.nos, ligsBrutas = p.ligacoes || EXEMPLO.ligacoes;
  const ids = nos.map((n) => String(n.id));
  ids.forEach((id, i) => exigir(ids.indexOf(id) === i, `nos: o id "${id}" aparece duas vezes — cada nó tem um id único`));
  const ligs = ligsBrutas.map((l, i) => {
    for (const ponta of ['de', 'para']) exigir(ids.includes(String(l[ponta])), `ligacoes[${i}].${ponta} = "${l[ponta]}" não é id de nenhum nó (${ids.join(', ')})`);
    exigir(String(l.de) !== String(l.para), `ligacoes[${i}]: o nó "${l.de}" aponta para ele mesmo — um laço passa por outro nó`);
    return { de: String(l.de), para: String(l.para), rotulo: l.rotulo ? String(l.rotulo).trim() : '', tracejada: !!l.tracejada };
  });
  // 1. ligações de retorno: as que fecham um ciclo na ordem em que os nós foram declarados (busca em profundidade)
  const estado = Object.fromEntries(ids.map((id) => [id, 0]));
  const visita = (u) => {
    estado[u] = 1;
    for (const l of ligs) if (l.de === u) { if (estado[l.para] === 1) l.retorno = true; else if (estado[l.para] === 0) visita(l.para); }
    estado[u] = 2;
  };
  for (const id of ids) if (estado[id] === 0) visita(id);
  // 2. camada de cada nó: uma depois da mais funda das que apontam para ele (ou a `coluna` dada)
  const fixa = Object.fromEntries(nos.map((n) => [String(n.id), n.coluna]));
  const memo = {};
  const camadaDe = (v) => {
    if (v in memo) return memo[v];
    if (fixa[v] != null) return (memo[v] = fixa[v]);
    memo[v] = 0;
    for (const l of ligs) if (l.para === v && !l.retorno) memo[v] = Math.max(memo[v], camadaDe(l.de) + 1);
    return memo[v];
  };
  ids.forEach(camadaDe);
  const usadas = [...new Set(ids.map((id) => memo[id]))].sort((a, b) => a - b);
  const camada = Object.fromEntries(ids.map((id) => [id, usadas.indexOf(memo[id])]));
  const porCamada = usadas.map((_, c) => nos.filter((n) => camada[String(n.id)] === c)
    .sort((a, b) => (a.linha ?? 99) - (b.linha ?? 99)).map((n) => String(n.id)));
  exigir(porCamada.length <= 6, `o diagrama ficou com ${porCamada.length} camadas em sequência; cabem até 6 — junte etapas ou divida em duas cenas`);
  porCamada.forEach((c, i) => exigir(c.length <= 4, `a camada ${i + 1} do diagrama tem ${c.length} nós lado a lado (${c.join(', ')}); cabem até 4 — use "coluna" para redistribuir ou divida em duas cenas`));
  for (const l of ligs) { const dl = camada[l.para] - camada[l.de]; l.tipo = dl === 1 ? 'vizinha' : dl > 1 ? 'salto' : dl === 0 ? 'mesma' : 'retorno'; }
  // 3. ordem de revelação
  let ordem = porCamada.map((c) => c.slice());
  if (p.ordem && p.ordem.length) {
    ordem = p.ordem.map((passo) => passo.map(String));
    const vistos = ordem.flat();
    for (const id of vistos) exigir(ids.includes(id), `ordem: "${id}" não é id de nenhum nó (${ids.join(', ')})`);
    for (const id of ids) {
      const vezes = vistos.filter((x) => x === id).length;
      exigir(vezes === 1, vezes ? `ordem: o nó "${id}" aparece ${vezes} vezes — cada nó entra uma vez só` : `ordem: faltou o nó "${id}" — todo nó precisa entrar em algum passo`);
    }
  }
  exigir(!p.destaque || ids.includes(String(p.destaque)), `destaque = "${p.destaque}" não é id de nenhum nó (${ids.join(', ')})`);
  const passoDe = {};
  ordem.forEach((passo, s) => passo.forEach((id) => { passoDe[id] = s; }));
  for (const l of ligs) l.passo = Math.max(passoDe[l.de], passoDe[l.para]);
  return { nos, ids, ligs, camada, porCamada, ordem, passoDe };
}

const tNos = (d, e, n) => d.media * 1.4 + (n - 1) * e * 3;

export function roteiro(p, mov) {
  const d = mov.duracoes, e = mov.escalonamento, A = analisar(p);
  const r = A.ordem.map((ids, s) => ({ nome: 'passo' + (s + 1), tipo: s ? 'enfase' : 'entrada', anim: tNos(d, e, ids.length) + (A.ligs.some((l) => l.passo === s) ? d.media * 2 : 0) + d.curta }));
  if (p.destaque) r.push({ nome: 'destaque', tipo: 'enfase', anim: d.media });
  return r;
}

const ESTADOS = new WeakMap();

export function build(palco, p, ctx) {
  const A = analisar(p), cor = p.cor;
  const Q = montarQuadro(palco, p, ctx, { roteiro: roteiro(p, ctx.DA.movimento) });
  const C = Q.conteudo, P = Q.P;
  const svg = camadaSvg(ctx, Q.raiz);
  const camada = ctx.el('div', 'fluxo-camada');
  Object.assign(camada.style, { position: 'absolute', left: '0', top: '0' });
  Q.raiz.appendChild(camada);
  const deitado = p.direcao === 'horizontal' || (p.direcao === 'auto' && Q.horizontal);
  const nL = A.porCamada.length, m = Math.max(...A.porCamada.map((c) => c.length));
  const tem = (tipo) => A.ligs.some((l) => l.tipo === tipo);
  const info = Object.fromEntries(A.nos.map((n) => [String(n.id), n]));

  const U = caber((s) => {
    const tam = tamanho(ctx, 'h3', s), tamSub = tamanho(ctx, 'nota', s * 1.12), pad = tam * 0.5;
    const k = tam * 1.9;                                         // quanto um arco se afasta das caixas
    const rots = A.ligs.map((l) => (l.rotulo ? etiqueta(ctx, camada, l.rotulo, { tam: tamanho(ctx, 'nota', s), maxW: deitado ? 0 : ctx.px(0.17) }) : null));
    const wRot = (tipos) => Math.max(0, ...A.ligs.map((l, i) => (rots[i] && tipos.includes(l.tipo) ? rots[i].w : 0)));
    const hRot = (tipos) => Math.max(0, ...A.ligs.map((l, i) => (rots[i] && tipos.includes(l.tipo) ? rots[i].h : 0)));
    let wBox, vaoX, vaoY, antes, depois;
    if (deitado) {
      vaoX = Math.max(tam * 1.7, wRot(['vizinha']) + tam * 0.9);
      wBox = Math.min((C.w - (nL - 1) * vaoX) / nL, ctx.col(4));
      vaoY = Math.max(tam * 0.9, hRot(['mesma']) + tam * 0.9);
      antes = tem('salto') ? k * 0.75 + hRot(['salto']) * 0.5 + tam * 0.2 : 0;      // espaço em cima (saltos) e embaixo (retornos)
      depois = tem('retorno') ? k * 0.75 + hRot(['retorno']) * 0.5 + tam * 0.2 : 0;
    } else {
      vaoX = tam * 0.6;
      antes = tem('salto') ? k * 0.75 + (wRot(['salto']) ? wRot(['salto']) + tam * 0.3 : tam * 0.2) : 0;        // espaço à esquerda (saltos) e à direita (retornos),
      depois = tem('retorno') ? k * 0.75 + (wRot(['retorno']) ? wRot(['retorno']) + tam * 0.3 : tam * 0.2) : 0;   // com o rótulo AO LADO do arco
      wBox = Math.min((C.w - antes - depois - (m - 1) * vaoX) / m, ctx.col(8));
      vaoY = Math.max(tam * 1.15, hRot(['vizinha']) + tam * 0.9);
    }
    const textos = A.ids.map((id) => {
      const rot = escrever(ctx, camada, 'titulo', String(info[id].rotulo), { tam, maxW: wBox - 2 * pad, maxLinhas: 2, alinhar: 'centro', classe: 'fluxo-rotulo' });
      const sub = info[id].sub && String(info[id].sub).trim() ? escrever(ctx, camada, 'corpo', String(info[id].sub), { tam: tamSub, cor: 'texto_suave', maxW: wBox - 2 * pad, maxLinhas: 2, alinhar: 'centro', classe: 'fluxo-sub' }) : null;
      return { rot, sub, h: pad + rot.h + (sub ? tam * 0.12 + sub.h : 0) + pad, largo: rot.linhas > 2 || rot.el._inner.scrollWidth > rot.el._inner.clientWidth + 1 };
    });
    const hBox = Math.max(...textos.map((x) => x.h), deitado ? Math.min(wBox * 0.5, tam * 3.6) : 0);       // caixa com corpo, não uma tira
    const larg = deitado ? nL * wBox + (nL - 1) * vaoX : antes + m * wBox + (m - 1) * vaoX + depois;
    const alt = deitado ? antes + m * hBox + (m - 1) * vaoY + depois : nL * hBox + (nL - 1) * vaoY;
    return { cabe: alt <= C.h * respiro(s) && larg <= C.w + 1 && wBox > tam * 3 && textos.every((x) => !x.largo), tam, pad, k, rots, wBox, hBox, vaoX, vaoY, antes, depois, textos, larg, alt };
  }, () => camada.replaceChildren(), { inicio: deitado ? 1.15 : 1.05, min: 0.45 });
  encaixou(U, C, 'fluxo');

  // posição de cada caixa: camadas ao longo do fluxo, nós da mesma camada centrados no outro eixo
  const x0 = C.x + (C.w - U.larg) / 2, y0 = C.y + Math.max(0, (C.h - U.alt) / 2);
  const caixas = {};
  A.porCamada.forEach((lista, c) => {
    lista.forEach((id, i) => {
      const fila = info[id].linha != null ? Math.min(info[id].linha, m - 1) : i + (m - lista.length) / 2;
      const x = deitado ? x0 + c * (U.wBox + U.vaoX) : x0 + U.antes + fila * (U.wBox + U.vaoX);
      const y = deitado ? y0 + U.antes + fila * (U.hBox + U.vaoY) : y0 + c * (U.hBox + U.vaoY);
      const cx = cartao(ctx, { w: U.wBox, h: U.hBox, cor });
      camada.appendChild(cx.el);
      cx.em(x, y);
      const tx = U.textos[A.ids.indexOf(id)];
      const hTxt = tx.rot.h + (tx.sub ? U.tam * 0.12 + tx.sub.h : 0);
      cx.miolo.appendChild(tx.rot.el);
      tx.rot.em(U.pad, (U.hBox - hTxt) / 2);
      if (tx.sub) { cx.miolo.appendChild(tx.sub.el); tx.sub.em(U.pad, (U.hBox - hTxt) / 2 + tx.rot.h + U.tam * 0.12); }
      caixas[id] = { c: cx, rot: tx.rot, sub: tx.sub, x: cx.x, y: cx.y, x1: cx.x + cx.w, y1: cx.y + cx.h, cx: cx.x + cx.w / 2, cy: cx.y + cx.h / 2, letras: String(info[id].rotulo).length };
    });
  });
  // setas: reta/curva suave entre camadas vizinhas; arco por fora para salto (pula camadas) e retorno (volta)
  const f = 0.22, k = U.k;
  const curvaDe = (l) => {
    const a = caixas[l.de], b = caixas[l.para];
    if (deitado) {
      if (l.tipo === 'vizinha') { const dx = b.x - a.x1; return [a.x1, a.cy, a.x1 + dx * 0.5, a.cy, b.x - dx * 0.5, b.cy, b.x, b.cy]; }
      if (l.tipo === 'salto') { const ax = a.cx + U.wBox * f, bx = b.cx - U.wBox * f; return [ax, a.y, ax, a.y - k, bx, b.y - k, bx, b.y]; }
      if (l.tipo === 'retorno') { const ax = a.cx - U.wBox * f, bx = b.cx + U.wBox * f; return [ax, a.y1, ax, a.y1 + k, bx, b.y1 + k, bx, b.y1]; }
      return b.y > a.y ? [a.cx, a.y1, a.cx, a.y1 + 1, b.cx, b.y - 1, b.cx, b.y] : [a.cx, a.y, a.cx, a.y - 1, b.cx, b.y1 + 1, b.cx, b.y1];
    }
    if (l.tipo === 'vizinha') { const dy = b.y - a.y1; return [a.cx, a.y1, a.cx, a.y1 + dy * 0.5, b.cx, b.y - dy * 0.5, b.cx, b.y]; }
    if (l.tipo === 'salto') { const ay = a.cy + U.hBox * f, by = b.cy - U.hBox * f; return [a.x, ay, a.x - k, ay, b.x - k, by, b.x, by]; }
    if (l.tipo === 'retorno') { const ay = a.cy - U.hBox * f, by = b.cy + U.hBox * f; return [a.x1, ay, a.x1 + k, ay, b.x1 + k, by, b.x1, by]; }
    return b.x > a.x ? [a.x1, a.cy, a.x1 + 1, a.cy, b.x - 1, b.cy, b.x, b.cy] : [a.x, a.cy, a.x - 1, a.cy, b.x1 + 1, b.cy, b.x1, b.cy];
  };
  const esp = Math.max(1.5, ctx.traco);
  const setas = A.ligs.map((l, i) => {
    const c = curvaDe(l);
    const traco = l.tracejada ? `${(esp * 3).toFixed(1)} ${(esp * 3).toFixed(1)}` : null;
    const base = setaCurva(ctx, svg, c, { cor: 'texto_suave', esp, tracejado: traco });
    const g = ctx.svg('g');
    svg.appendChild(g);
    const viva = setaCurva(ctx, g, c, { cor, esp: esp * 1.2, tracejado: traco });
    const rot = U.rots[i];
    if (rot) {                                                   // rótulo no meio da curva; em arco lateral (fluxo vertical), ao lado dele
      const meio = pontoNaCurva(c, 0.5), folga = U.tam * 0.3;
      const x = deitado || l.tipo === 'vizinha' || l.tipo === 'mesma' ? meio.x - rot.w / 2 : l.tipo === 'retorno' ? meio.x + folga : meio.x - folga - rot.w;
      rot.em(clamp(x, C.x, C.x1 - rot.w), clamp(meio.y - rot.h / 2, C.y, C.y1 - rot.h));
    }
    return { ...l, base, viva, g, rot };
  });
  guardar(ESTADOS, ctx, { ctx, Q, P, p, A, caixas, setas, S: A.ordem.length });
  return Q.layout({ sentido: deitado ? 'horizontal' : 'vertical', camadas: A.porCamada, passos_do_diagrama: A.ordem, retornos: A.ligs.filter((l) => l.tipo === 'retorno').map((l) => `${l.de}>${l.para}`),
    escala: +U.escala.toFixed(3), tamanho_rotulo: +Math.min(...U.textos.map((x) => x.rot.tam)).toFixed(1), caixa: { w: Math.round(U.wBox), h: Math.round(U.hBox) },
    bloco: { x: Math.round(x0), y: Math.round(y0), w: Math.round(U.larg), h: Math.round(U.alt) } });
}

export function seek(t, ctxArg) {
  const { ctx, Q, P, p, A, caixas, setas, S } = ler(ESTADOS, ctxArg);
  const d = ctx.DA.movimento.duracoes, e = ctx.escalonamento;
  const pDest = p.destaque ? P.prog(t, 'destaque', 0, d.media, 'enfase') : 0;
  // quanto o destaque do passo s já passou adiante (o seguinte começou; no último, some sozinho no fim — ou vai para `destaque`)
  const passou = A.ordem.map((ids, s) => clamp(s < S - 1 ? P.prog(t, 'passo' + (s + 2), 0, d.curta) : (p.destaque ? pDest : P.prog(t, 'passo' + (s + 1), P.nominal[s] - d.curta, d.curta))));
  A.ordem.forEach((ids, s) => {
    const passo = 'passo' + (s + 1);
    ids.forEach((id, i) => {
      const n = caixas[id], at = i * e * 3;
      entrarBloco(ctx, n.c.el, P.prog(t, passo, at, d.media));
      ctx.entrada(n.rot.el, P.prog(t, passo, at + d.media * 0.4, d.media), undefined, { n: n.letras });
      if (n.sub) ctx.entrada(n.sub.el, P.prog(t, passo, at + d.media * 0.4, d.media), 'fade');
      const daVez = clamp(P.prog(t, passo, at, d.media, 'enfase')) * (1 - passou[s]);
      n.c.estado({ realce: String(p.destaque) === id ? Math.max(daVez, pDest) : daVez });
    });
  });
  for (const st of setas) {
    const passo = 'passo' + (st.passo + 1), at = tNos(d, e, A.ordem[st.passo].length);
    const pt = P.prog(t, passo, at, d.media * 1.5, 'suave');
    st.base.tracar(pt);
    st.viva.tracar(pt);
    st.g.style.opacity = (1 - passou[st.passo]).toFixed(3);
    if (st.rot) ctx.entrada(st.rot.el, P.prog(t, passo, at + d.media * 1.5, d.media * 0.5), 'fade');
  }
  Q.seek(t);
}

export function key(t, ctx) { return ler(ESTADOS, ctx).P.chave(t); }

export function ancoras(ctx) { return ler(ESTADOS, ctx).P.ancoras(); }
