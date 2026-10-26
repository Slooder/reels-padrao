// comparativo.js — opções (modelos, planos, abordagens) × critérios. Passos: opcoes → criterio1 → criterio2 → … →
// [destaque]. Horizontal: tabela (uma coluna por opção, uma linha por critério). Vertical: um bloco por critério com
// as opções uma embaixo da outra — nos dois, cada passo mostra UM critério em todas as opções.
// Os valores vão para a tela como texto, do jeito que foram escritos ("200 mil tokens", "US$ 3 por milhão"): a cena
// não converte, não arredonda, não ordena e não elege "o melhor" — `destaque_opcao`/`destaque_criterio` só existem
// se o roteiro mandar. Valor é dado: o exemplo padrão (Modelo A, B, C) é inventado e leva o selo "ilustrativo"; com
// opções suas, a cena exige a escolha — ilustrativo=false + `fonte` (+ fato_ids no storyboard) ou ilustrativo=true.
import { params, guardar, ler, montarQuadro, escrever, caber, tamanho, exigir, igual, decidirIlustrativo, marcador, clamp, encaixou, respiro } from './_ia.js';

const EXEMPLO = {
  criterios: ['Janela de contexto', 'Preço de entrada', 'Velocidade'],
  opcoes: [
    { nome: 'Modelo A', valores: ['32 mil tokens', 'US$ 1 por milhão', 'rápida'] },
    { nome: 'Modelo B', valores: ['128 mil tokens', 'US$ 4 por milhão', 'média'] },
    { nome: 'Modelo C', valores: ['1 milhão de tokens', 'US$ 12 por milhão', 'lenta'] },
  ],
};

export const meta = {
  nome: 'comparativo',
  descricao: 'Comparativo: opções (modelos, planos, abordagens) × critérios, revelado um critério por vez — tabela no horizontal, blocos por critério no vertical. Valores só com fonte ou com o selo "ilustrativo".',
  dur_padrao: 13,
  formatos: ['horizontal', 'vertical', 'quadrado'],
  alfa_padrao: false,
  grao: true,
  params: params({
    criterios: { tipo: 'lista', min: 1, max: 5, itens: { tipo: 'texto' }, padrao: EXEMPLO.criterios, descricao: 'o nome de cada critério (uma linha da tabela), na ordem em que são falados' },
    opcoes: { tipo: 'lista', min: 2, max: 4, padrao: EXEMPLO.opcoes, descricao: 'as opções comparadas: nome e um valor POR CRITÉRIO, como texto pronto para a tela (com a unidade); "—" quando não há dado',
      itens: { tipo: 'objeto', campos: { nome: { tipo: 'texto', obrigatorio: true }, valores: { tipo: 'lista', obrigatorio: true, min: 1, max: 5, itens: { tipo: 'texto' } } } } },
    destaque_opcao: { tipo: 'inteiro', padrao: null, min: 0, descricao: 'índice da opção que termina em destaque (null = nenhuma: a cena não elege vencedor)' },
    destaque_criterio: { tipo: 'inteiro', padrao: null, min: 0, descricao: 'índice do critério em destaque no fim (com destaque_opcao, destaca só a célula)' },
    disposicao: { tipo: 'opcao', opcoes: ['auto', 'tabela', 'blocos'], padrao: 'auto', descricao: 'auto = tabela no horizontal e blocos por critério no vertical' },
  }, { titulo: 'Comparativo', ilustrativo: 'dado' }),
};

const temDestaque = (p) => p.destaque_opcao != null || p.destaque_criterio != null;
const proprio = (p) => !(igual(p.opcoes || EXEMPLO.opcoes, EXEMPLO.opcoes) && igual(p.criterios || EXEMPLO.criterios, EXEMPLO.criterios));

export function roteiro(p, mov) {
  const d = mov.duracoes, e = mov.escalonamento;
  const criterios = p.criterios || EXEMPLO.criterios, opcoes = p.opcoes || EXEMPLO.opcoes, n = opcoes.length, K = criterios.length;
  decidirIlustrativo(p, proprio(p), 'comparativo');
  opcoes.forEach((o, j) => exigir((o.valores || []).length === K, `opcoes[${j}] ("${o.nome}") tem ${(o.valores || []).length} valor(es) e há ${K} critério(s) (${criterios.join(', ')}): é um valor por critério, na mesma ordem — use "—" onde não há dado`));
  exigir(p.destaque_opcao == null || p.destaque_opcao < n, `destaque_opcao = ${p.destaque_opcao}, mas só há ${n} opções (índices de 0 a ${n - 1})`);
  exigir(p.destaque_criterio == null || p.destaque_criterio < K, `destaque_criterio = ${p.destaque_criterio}, mas só há ${K} critérios (índices de 0 a ${K - 1})`);
  const r = [{ nome: 'opcoes', tipo: 'entrada', anim: d.media * 2 + n * e * 3 }];
  for (let k = 0; k < K; k++) r.push({ nome: 'criterio' + (k + 1), tipo: 'texto', anim: d.media * 2 + n * e * 3 });
  if (temDestaque(p)) r.push({ nome: 'destaque', tipo: 'enfase', anim: d.media });
  return r;
}

const ESTADOS = new WeakMap();

export function build(palco, p, ctx) {
  const criterios = p.criterios.map(String), opcoes = p.opcoes, n = opcoes.length, K = criterios.length, cor = p.cor;
  const rot = roteiro(p, ctx.DA.movimento);
  const ilustrativo = decidirIlustrativo(p, proprio(p), 'comparativo');
  const Q = montarQuadro(palco, { ...p, ilustrativo }, ctx, { roteiro: rot });
  const C = Q.conteudo, P = Q.P;
  const tabela = p.disposicao === 'tabela' || (p.disposicao === 'auto' && Q.horizontal);
  const fundoCam = ctx.el('div', 'comp-fundo'), camada = ctx.el('div', 'comp-camada');
  for (const c of [fundoCam, camada]) { Object.assign(c.style, { position: 'absolute', left: '0', top: '0' }); Q.raiz.appendChild(c); }
  const fio = Math.max(1, ctx.traco * 0.75);
  const g = ctx.DA.graficos.dados;

  const U = caber((s) => {
    const tamV = tamanho(ctx, 'h3', s * 0.95), tamC = tamanho(ctx, 'corpo', s * 1.05), pad = tamV * 0.55;
    const lado = tamC * 0.3;
    if (tabela) {
      const wCritMax = C.w * 0.26;
      const rots = criterios.map((c) => escrever(ctx, camada, 'corpo', c, { tam: tamC, cor: 'texto_suave', maxW: wCritMax - lado * 2.2, maxLinhas: 2, classe: 'comp-criterio' }));
      const wCrit = Math.max(...rots.map((r) => r.w)) + lado * 2.2 + pad;
      const wCol = (C.w - wCrit) / n;
      const nomes = opcoes.map((o) => escrever(ctx, camada, 'titulo', String(o.nome), { tam: tamanho(ctx, 'h3', s), maxW: wCol - 2 * pad, maxLinhas: 2, classe: 'comp-nome' }));
      const cel = opcoes.map((o) => o.valores.map((v) => escrever(ctx, camada, 'dados', String(v), { tam: tamV, maxW: wCol - 2 * pad, maxLinhas: 2, classe: 'comp-valor' })));
      const hCab = Math.max(...nomes.map((x) => x.h)) + 2 * pad * 0.8;
      // linhas arejadas: se sobra altura, cada linha ganha corpo (até 3× a letra) em vez de a tabela virar uma tira no meio do quadro
      const arejada = Math.min(tamV * 3, (C.h * 0.72 - hCab) / K);
      const hLin = criterios.map((_, k) => Math.max(Math.max(rots[k].h, ...cel.map((col) => col[k].h)) + 2 * pad * 0.8, arejada));
      const h = hCab + hLin.reduce((a, b) => a + b, 0);
      // valor numa linha só enquanto a letra não ficar pequena; abaixo disso, aceita duas linhas
      const umaLinha = s > 1 ? 1 : 2;
      const cabe = h <= C.h * respiro(s) && cel.every((col) => col.every((c) => c.w <= wCol - 2 * pad + 1 && c.linhas <= umaLinha)) && nomes.every((x) => x.w <= wCol - 2 * pad + 1);
      return { cabe, tabela, rots, nomes, cel, wCrit, wCol, hCab, hLin, h, pad, lado, tamV };
    }
    // blocos por critério: em cada bloco, o nome de cada opção à esquerda e o valor à direita
    const rots = criterios.map((c) => escrever(ctx, camada, 'subtitulo', c, { tam: tamC, cor: 'texto', maxW: C.w - lado * 2.2, maxLinhas: 2, classe: 'comp-criterio' }));
    const nomes = criterios.map(() => opcoes.map((o) => escrever(ctx, camada, 'corpo', String(o.nome), { tam: tamC, cor: 'texto_suave', maxW: C.w * 0.4, maxLinhas: 1, classe: 'comp-nome' })));
    const cel = opcoes.map((o) => o.valores.map((v) => escrever(ctx, camada, 'dados', String(v), { tam: tamV * 0.92, maxW: C.w * 0.58, maxLinhas: 2, alinhar: 'direita', classe: 'comp-valor' })));
    const hLin = criterios.map((_, k) => opcoes.map((__, j) => Math.max(nomes[k][j].h, cel[j][k].h) + pad * 0.55));
    const hBloco = criterios.map((_, k) => rots[k].h + pad * 0.5 + hLin[k].reduce((a, b) => a + b, 0));
    const vBloco = pad * 1.3;
    const h = hBloco.reduce((a, b) => a + b, 0) + (K - 1) * vBloco;
    return { cabe: h <= C.h * respiro(s), tabela, rots, nomes, cel, hLin, hBloco, vBloco, h, pad, lado, tamV };
  }, () => camada.replaceChildren(), { inicio: Q.horizontal ? 1.25 : 1.05 });
  encaixou(U, C, 'comparativo');

  const y0 = Math.round(C.y + Math.max(0, (C.h - U.h) / 2));
  const linhas = [], marcas = [];
  const novaLinha = (x, y, w, alfa) => {
    const l = ctx.el('div', 'comp-fio');
    Object.assign(l.style, { position: 'absolute', left: Math.round(x) + 'px', top: Math.round(y) + 'px', width: Math.round(w) + 'px', height: fio.toFixed(1) + 'px', background: ctx.alfa(alfa >= 0.99 ? 'texto_suave' : g.eixo, alfa >= 0.99 ? 0.7 : alfa), transformOrigin: 'left center' });
    camada.appendChild(l);
    return l;
  };
  const novaMarca = (x, yCentro) => {
    const m = marcador(ctx, { tipo: 'quadrado', lado: U.lado, cor });
    camada.appendChild(m.el);
    Object.assign(m.el.style, { left: Math.round(x) + 'px', top: Math.round(yCentro - U.lado / 2) + 'px' });
    return m;
  };
  const ret = { col: [], lin: [], cel: opcoes.map(() => []) };            // retângulos para o destaque final
  let cab = null;
  if (U.tabela) {
    const xCol = (j) => C.x + U.wCrit + j * U.wCol;
    U.nomes.forEach((nm, j) => nm.em(xCol(j) + U.pad, y0 + (U.hCab - nm.h) / 2));
    cab = novaLinha(C.x, y0 + U.hCab - fio, C.w, 1);
    let y = y0 + U.hCab;
    criterios.forEach((_, k) => {
      const hl = U.hLin[k];
      marcas.push(novaMarca(C.x, y + hl / 2));
      U.rots[k].em(C.x + U.lado * 2.2, y + (hl - U.rots[k].h) / 2);
      opcoes.forEach((__, j) => { U.cel[j][k].em(xCol(j) + U.pad, y + (hl - U.cel[j][k].h) / 2); ret.cel[j][k] = { x: xCol(j), y, w: U.wCol, h: hl }; });
      ret.lin[k] = { x: C.x, y, w: C.w, h: hl };
      linhas.push(k < K - 1 ? novaLinha(C.x, y + hl - fio, C.w, 0.35) : null);
      y += hl;
    });
    opcoes.forEach((_, j) => { ret.col[j] = { x: xCol(j), y: y0, w: U.wCol, h: U.h }; });
  } else {
    let y = y0;
    criterios.forEach((_, k) => {
      const yB = y;
      marcas.push(novaMarca(C.x, y + (U.rots[k].h / U.rots[k].linhas) / 2));
      U.rots[k].em(C.x + U.lado * 2.2, y);
      y += U.rots[k].h + U.pad * 0.5;
      opcoes.forEach((__, j) => {
        const hl = U.hLin[k][j];
        U.nomes[k][j].em(C.x + U.lado * 2.2, y + (hl - U.nomes[k][j].h) / 2);
        const c = U.cel[j][k];
        c.em(C.x1 - c.w, y + (hl - c.h) / 2);
        ret.cel[j][k] = { x: C.x, y, w: C.w, h: hl };
        y += hl;
      });
      ret.lin[k] = { x: C.x, y: yB, w: C.w, h: y - yB };
      linhas.push(null);
      y += U.vBloco;
    });
    opcoes.forEach((_, j) => { ret.col[j] = null; });
  }
  // destaque final: um ou mais retângulos tingidos, atrás do texto
  let alvos = [];
  const jo = p.destaque_opcao, ko = p.destaque_criterio;
  if (jo != null && ko != null) alvos = [ret.cel[jo][ko]];
  else if (jo != null) alvos = ret.col[jo] ? [ret.col[jo]] : criterios.map((_, k) => ret.cel[jo][k]);
  else if (ko != null) alvos = [ret.lin[ko]];
  const aneis = alvos.map((r) => {
    const a = ctx.el('div', 'comp-destaque');
    const folga = U.tabela && jo != null && ko == null ? 0 : U.pad * 0.3;
    Object.assign(a.style, { position: 'absolute', left: Math.round(r.x - folga) + 'px', top: Math.round(r.y) + 'px', width: Math.round(r.w + 2 * folga) + 'px', height: Math.round(r.h) + 'px', boxSizing: 'border-box',
      background: ctx.alfa(cor, 0.14), border: `${Math.max(2, ctx.traco * 1.4).toFixed(1)}px solid ${ctx.cor(cor)}`, borderRadius: ctx.raio + 'px' });
    fundoCam.appendChild(a);
    return a;
  });
  guardar(ESTADOS, ctx, { ctx, Q, P, p, U, cab, linhas, marcas, aneis, n, K });
  return Q.layout({ disposicao: U.tabela ? 'tabela' : 'blocos', opcoes: n, criterios: K, escala: +U.escala.toFixed(3), tamanho_valor: +U.tamV.toFixed(1),
    bloco: { x: Math.round(C.x), y: y0, w: Math.round(C.w), h: Math.round(U.h) } });
}

export function seek(t, ctxArg) {
  const { ctx, Q, P, p, U, cab, linhas, marcas, aneis, n, K } = ler(ESTADOS, ctxArg);
  const d = ctx.DA.movimento.duracoes, e = ctx.escalonamento;
  const pDest = aneis.length ? P.prog(t, 'destaque', 0, d.media, 'enfase') : 0;
  // 1. quem está sendo comparado
  // (na tabela: os cabeçalhos das colunas; nos blocos: os nomes das opções do primeiro bloco, ainda sem valor)
  (U.tabela ? U.nomes : U.nomes[0]).forEach((nm, j) => ctx.entrada(nm.el, P.prog(t, 'opcoes', j * e * 3, d.media)));
  if (cab) {
    const pc = P.prog(t, 'opcoes', d.media, d.media + n * e * 3);
    cab.style.transform = `scaleX(${clamp(pc).toFixed(4)})`;
    cab.style.opacity = pc > 0 ? '1' : '0';
  }
  // 2. um critério por vez, em todas as opções
  for (let k = 0; k < K; k++) {
    const passo = 'criterio' + (k + 1);
    const pr = P.prog(t, passo, 0, d.media);
    ctx.entrada(U.rots[k].el, pr);
    const proximo = k < K - 1 ? P.prog(t, 'criterio' + (k + 2), 0, d.curta) : (aneis.length ? pDest : P.prog(t, passo, d.media * 2 + n * e * 3 - d.curta, d.curta));
    marcas[k].el.style.opacity = clamp(pr * 2).toFixed(3);
    marcas[k].misturar(clamp(P.prog(t, passo, 0, d.media, 'enfase')) * (1 - clamp(proximo)));
    for (let j = 0; j < n; j++) {
      const pv = P.prog(t, passo, d.media * 0.6 + j * e * 3, d.media);
      ctx.entrada(U.cel[j][k].el, pv);
      if (!U.tabela && k > 0) ctx.entrada(U.nomes[k][j].el, P.prog(t, passo, d.media * 0.3 + j * e * 3, d.media), 'fade');
    }
    if (linhas[k]) { const pl = P.prog(t, passo, d.media, d.media); linhas[k].style.transform = `scaleX(${clamp(pl).toFixed(4)})`; linhas[k].style.opacity = pl > 0 ? '1' : '0'; }
  }
  for (const a of aneis) { a.style.opacity = clamp(pDest).toFixed(3); a.style.transform = `scale(${(0.97 + 0.03 * Math.min(pDest, 1.3)).toFixed(4)})`; }
  Q.seek(t);
}

export function key(t, ctx) { return ler(ESTADOS, ctx).P.chave(t); }

export function ancoras(ctx) { return ler(ESTADOS, ctx).P.ancoras(); }
