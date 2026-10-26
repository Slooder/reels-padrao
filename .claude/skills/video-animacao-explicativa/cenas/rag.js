// rag.js — geração aumentada por recuperação (RAG): a pergunta dispara uma busca numa base de documentos, os trechos
// mais parecidos entram no contexto do modelo junto com a pergunta, e a resposta cita de onde veio cada afirmação.
// Passos: pergunta → busca → trechos → contexto → resposta → citacao.
// O que a cena faz de verdade com os dados: ORDENA os documentos pela `pontuacao` que você passou e fica com os `k`
// primeiros (ela não escolhe à mão quem é "relevante"), numera os trechos pela colocação e RECUSA uma resposta que
// cite um trecho que não foi recuperado ([3] com k = 2) — é a regra do RAG: o modelo só pode citar o que recebeu.
// Horizontal: três colunas (pergunta → base → o que o modelo recebe e a resposta). Vertical: uma coluna que se
// reorganiza — no passo `contexto` os trechos não escolhidos saem, os escolhidos sobem e abrem o texto, e um contorno
// abraça "pergunta + trechos": é isso que o modelo recebe.
// Simplificações declaradas em references/didatica.md: a base tem meia dúzia de trechos (as reais têm de milhares a
// milhões), a pontuação é um número dado (na prática sai da comparação de vetores — embeddings — e, muitas vezes,
// também de busca por palavras), e os pesos do modelo NÃO mudam: os documentos só entram no contexto.
import { params, guardar, ler, montarQuadro, escrever, etiqueta, caber, tamanho, exigir, cartao, entrarBloco, barra, contador, rotulo, digitador, camadaSvg, setaCurva, reta, encaixou, respiro, num, clamp, lerp } from './_ia.js';

const EXEMPLO = {
  pergunta: 'Qual o prazo para trocar um produto?',
  documentos: [
    { titulo: 'Trocas e devoluções', trecho: 'A troca pode ser pedida em até 30 dias após a entrega.', pontuacao: 0.91 },
    { titulo: 'Formas de pagamento', trecho: 'Aceitamos cartão, boleto e Pix.', pontuacao: 0.18 },
    { titulo: 'Garantia', trecho: 'Defeitos de fabricação têm garantia de 12 meses.', pontuacao: 0.62 },
    { titulo: 'Entrega', trecho: 'O prazo de entrega varia conforme o CEP.', pontuacao: 0.44 },
  ],
  resposta: 'A troca pode ser pedida em até 30 dias após a entrega [1]. Se for defeito de fabricação, vale a garantia de 12 meses [2].',
};

export const meta = {
  nome: 'rag',
  descricao: 'RAG: a pergunta dispara uma busca numa base de documentos, os trechos mais parecidos entram no contexto do modelo e a resposta cita de onde veio cada afirmação.',
  dur_padrao: 18,
  formatos: ['horizontal', 'vertical', 'quadrado'],
  alfa_padrao: false,
  grao: true,
  params: params({
    pergunta: { tipo: 'texto', padrao: EXEMPLO.pergunta, descricao: 'a pergunta do usuário' },
    documentos: { tipo: 'lista', min: 2, max: 6, padrao: EXEMPLO.documentos, descricao: 'os trechos da base: título, o trecho e a pontuação de semelhança com a pergunta (0 a 1) — a cena ordena por ela',
      itens: { tipo: 'objeto', campos: { titulo: { tipo: 'texto', obrigatorio: true }, trecho: { tipo: 'texto', obrigatorio: true }, pontuacao: { tipo: 'numero', obrigatorio: true, min: 0, max: 1 } } } },
    k: { tipo: 'inteiro', padrao: 2, min: 1, max: 4, descricao: 'quantos trechos são recuperados (os de maior pontuação)' },
    resposta: { tipo: 'texto', padrao: EXEMPLO.resposta, descricao: 'a resposta, citando os trechos por colocação: [1] é o de maior pontuação, [2] o segundo… (só até k)' },
    nome_base: { tipo: 'texto', padrao: 'base de documentos', descricao: 'rótulo da base ("manual da loja", "artigos do site", "PDFs do contrato")' },
    rotulo_pontuacao: { tipo: 'texto', padrao: 'semelhança', descricao: 'cabeçalho da coluna de pontuação (o que o número mede)' },
  }, { titulo: 'RAG' }),
};

const LEGENDAS = ['Você faz uma *pergunta*', 'O sistema *busca* na base os trechos mais parecidos com ela', 'Só os *mais parecidos* são escolhidos', 'Eles entram no *contexto* do modelo, junto com a pergunta',
  'O modelo responde *com base neles*', 'e cada afirmação aponta para a *fonte*'];
const POR_LETRA = 0.3;
const tResposta = (d, txt) => Math.max(d.longa, Math.min(d.longa * 4, String(txt).length * d.micro * POR_LETRA));

function conferir(p) {
  const docs = p.documentos || EXEMPLO.documentos, k = p.k ?? 2, resposta = String(p.resposta ?? EXEMPLO.resposta);
  exigir(k <= docs.length, `k = ${k}, mas a base só tem ${docs.length} trechos: recupere no máximo ${docs.length}`);
  const citados = [...resposta.matchAll(/\[(\d+)\]/g)].map((m) => +m[1]);
  exigir(citados.length > 0, 'resposta: nenhuma citação — marque de onde veio cada afirmação com [1], [2]… (a colocação do trecho recuperado); sem citação, esta não é a cena certa');
  for (const c of citados) exigir(c >= 1 && c <= k, `a resposta cita [${c}], mas só ${k} trecho(s) foram recuperados ([1] a [${k}]): o modelo não pode citar o que não recebeu — aumente k ou corrija a resposta`);
  const ordem = docs.map((dc, i) => i).sort((a, b) => docs[b].pontuacao - docs[a].pontuacao || a - b);
  return { docs, k, resposta, citados, ordem, colocacao: ordem.reduce((o, i, pos) => { o[i] = pos; return o; }, {}) };
}

export function roteiro(p, mov) {
  const d = mov.duracoes, e = mov.escalonamento, D = conferir(p);
  return [
    { nome: 'pergunta', tipo: 'entrada', anim: d.media + d.longa },
    { nome: 'busca', tipo: 'enfase', anim: d.media * 2 + D.docs.length * e * 3 + d.longa },
    { nome: 'trechos', tipo: 'enfase', anim: d.media * 1.5 },
    { nome: 'contexto', tipo: 'entrada', anim: d.media * 3 + D.k * e * 3 },
    { nome: 'resposta', tipo: 'texto', anim: d.curta + tResposta(d, D.resposta) + d.curta },
    { nome: 'citacao', tipo: 'enfase', anim: d.media * 2 },
  ];
}

const ESTADOS = new WeakMap();

export function build(palco, p, ctx) {
  const D = conferir(p), cor = p.cor, N = D.docs.length, k = D.k;
  const Q = montarQuadro(palco, p, ctx, { roteiro: roteiro(p, ctx.DA.movimento), legendas: LEGENDAS });
  const C = Q.conteudo, P = Q.P, H = Q.horizontal;
  const svg = camadaSvg(ctx, Q.raiz);
  const camada = ctx.el('div', 'rag-camada');
  Object.assign(camada.style, { position: 'absolute', left: '0', top: '0' });
  Q.raiz.appendChild(camada);
  const recuperados = D.ordem.slice(0, k);                        // índices dos documentos, do mais parecido para o menos
  const htmlResposta = ctx.esc(D.resposta).replace(/\[(\d+)\]/g, (m) => `<span class="rag-cita" style="color: ${ctx.cor(cor)}">${m}</span>`);
  const rot = (txt) => { const r = rotulo(ctx, txt, { tam: ctx.tam('nota') }); camada.appendChild(r); const m = ctx.medir(r); return { el: r, w: m.w, h: m.h }; };
  const esp = Math.max(1.5, ctx.traco);

  let abrir = !H;                                                 // vertical: a linha escolhida abre e mostra o trecho (se couber)
  const tentar = (s) => {
    const tam = tamanho(ctx, 'h3', s * (H ? 0.92 : 0.86)), tamTit = tamanho(ctx, 'corpo', s * 1.02), tamTre = tamanho(ctx, 'nota', s * 1.08), pad = tamTit * 0.55;
    const vaoRot = ctx.tam('nota') * 0.4, vao = tamTit * 0.42;
    const seta = H ? C.w * 0.055 : tam * 1.05;                      // espaço das setas entre as etapas
    const borda = H ? 0 : pad * 0.55;                              // vertical: folga do contorno "o modelo recebe" em volta da pergunta e dos trechos
    const wA = H ? C.w * 0.25 : C.w - 2 * borda, wB = H ? C.w * 0.31 : C.w - 2 * borda, wC = H ? C.w - wA - wB - 2 * seta : C.w;
    const R = { p: H ? rot('pergunta') : null, d: rot(String(p.nome_base)), s: rot(String(p.rotulo_pontuacao)), c: H ? rot('o modelo recebe') : null, r: rot('resposta') };
    const perg = escrever(ctx, camada, 'corpo', String(p.pergunta), { tam, maxW: wA - 2 * pad, maxLinhas: H ? 4 : 2, classe: 'rag-pergunta' });
    const hPerg = perg.h + 2 * pad * (H ? 1 : 0.7);
    const crachas = D.docs.map((_, i) => (D.colocacao[i] < k ? etiqueta(ctx, camada, `[${D.colocacao[i] + 1}]`, { tam: tamTre, cor, fundo: 'fundo', contorno: cor }) : null));
    const lugar = Math.max(...crachas.map((c) => (c ? c.w : 0))) + pad * 0.5;               // o crachá da colocação tem lugar marcado no cartão:
    const vaga = H ? 0 : lugar, vagaBarra = H ? lugar : 0;                                    // antes do título (vertical) ou no fim da linha da barra (horizontal)
    const wBarra = H ? 0 : Math.min(wB * 0.16, tamTit * 2.6);
    const docs = D.docs.map((dc) => {
      const val = contador(ctx, { tam: ctx.tam('nota'), cor: 'texto', formato: (v) => num(v, 2), modelo: '0,00' });
      camada.appendChild(val.el);
      const mv = val.medir();
      const tit = escrever(ctx, camada, 'titulo', String(dc.titulo), { tam: tamTit, maxW: wB - 2 * pad - mv.w - pad - wBarra - vaga - (H ? 0 : pad * 0.6), maxLinhas: H ? 2 : 1, classe: 'rag-doc-titulo' });
      const tre = escrever(ctx, camada, 'corpo', String(dc.trecho), { tam: tamTre, cor: 'texto_suave', maxW: wB - 2 * pad - vaga - vagaBarra, maxLinhas: H ? 2 : 3, classe: 'rag-doc-trecho' });
      const hBarra = Math.max(4, tamTit * 0.16);
      const h = H ? pad * 0.8 + tit.h + tamTit * 0.15 + tre.h + tamTit * 0.3 + hBarra + pad * 0.8 : pad * 0.55 + Math.max(tit.h, mv.h) + pad * 0.55;
      const hAberto = abrir ? h + tre.h + pad * 0.6 : h;
      return { val, mv, tit, tre, h, hAberto, hBarra, cheia: tit.linhas > (H ? 2 : 1) || tre.linhas > (H ? 2 : 3) };
    });
    const hCab = Math.max(R.d.h, R.s.h) + vaoRot;
    const hDocs = docs.reduce((a, x) => a + x.h, 0) + (N - 1) * vao;
    const resp = escrever(ctx, camada, 'corpo', '', { tam: tamanho(ctx, 'h3', s * (H ? 0.8 : 0.82)), maxW: wC, maxLinhas: H ? 7 : 6, html: htmlResposta, classe: 'rag-resposta' });
    if (H) {
      // o que o modelo recebe: a pergunta (resumida) e os k trechos, numerados pela colocação
      const mini = escrever(ctx, camada, 'corpo', String(p.pergunta), { tam: tamTre, cor: 'texto_suave', maxW: wC - 2 * pad, maxLinhas: 2, classe: 'rag-mini' });
      const fichas = recuperados.map((di, j) => {
        const nro = etiqueta(ctx, camada, `[${j + 1}]`, { tam: tamTre, cor, fundo: 'superficie', contorno: cor });
        const txt = escrever(ctx, camada, 'corpo', String(D.docs[di].titulo), { tam: tamTre, cor: 'texto', maxW: wC - 2 * pad - nro.w - pad * 0.6, maxLinhas: 2, classe: 'rag-ficha' });
        return { nro, txt, h: Math.max(nro.h, txt.h) };
      });
      const hPainel = pad * 0.8 + mini.h + fichas.reduce((a, f) => a + vao * 0.8 + f.h, 0) + pad * 0.8;
      const colA = R.p.h + vaoRot + hPerg, colB = hCab + hDocs, colC = R.c.h + vaoRot + hPainel + vao * 2 + R.r.h + vaoRot + resp.h;
      const alt = Math.max(colA, colB, colC);
      return { cabe: alt <= C.h * respiro(s) && docs.every((x) => !x.cheia), tam, tamTit, tamTre, pad, vaoRot, vao, seta, wA, wB, wC, R, perg, hPerg, crachas, vaga, wBarra, docs, hCab, hDocs, mini, fichas, hPainel, resp, alt, vagaBarra };
    }
    // vertical — dois arranjos na mesma coluna: A (a base inteira) e B (só os escolhidos, abertos, dentro do contorno)
    const marca = etiqueta(ctx, camada, 'o modelo recebe', { tam: ctx.tam('nota'), cor });
    const topo = marca.h * 0.5 + borda;                            // a etiqueta monta na linha de cima do contorno
    const hA = topo + hPerg + seta + hCab + hDocs;
    const hSel = D.docs.reduce((a, _, i) => a + (D.colocacao[i] < k ? docs[i].hAberto : 0), 0) + (k - 1) * vao;
    const hB = topo + hPerg + seta + hCab + hSel + borda + seta + R.r.h + vaoRot + resp.h;
    const alt = Math.max(hA, hB);
    return { cabe: alt <= C.h && docs.every((x) => !x.cheia), tam, tamTit, tamTre, pad, vaoRot, vao, seta, wA, wB, wC, R, perg, hPerg, crachas, vaga, wBarra, docs, hCab, hDocs, resp, marca, borda, topo, hA, hB, hSel, alt };
  };
  const limpar = () => camada.replaceChildren();
  let U = caber(tentar, limpar, { inicio: H ? 1.1 : 1.05, min: 0.5 });
  if (!U.cabe && abrir) { limpar(); abrir = false; U = caber(tentar, limpar, { inicio: 1.05, min: 0.5 }); }      // sem lugar para abrir os trechos: ficam só os títulos
  encaixou(U, C, 'rag', 'encurte a pergunta, os títulos ou a resposta, ou use menos documentos');

  const y0 = Math.round(C.y + Math.max(0, (C.h - U.alt) / 2));
  const xA = H ? C.x : C.x + U.borda, xB = H ? C.x + U.wA + U.seta : C.x + U.borda, xC = H ? xB + U.wB + U.seta : C.x;
  const yA = H ? y0 : y0 + U.topo, yB = H ? y0 : yA + U.hPerg + U.seta;
  // A. a pergunta
  if (H) ctx.place(U.R.p.el, { x: Math.round(xA), y: Math.round(yA) });
  const cPerg = cartao(ctx, { w: U.wA, h: U.hPerg, cor });
  camada.appendChild(cPerg.el);
  cPerg.em(xA, yA + (H ? U.R.p.h + U.vaoRot : 0));
  cPerg.miolo.appendChild(U.perg.el);
  U.perg.em(U.pad, U.pad * (H ? 1 : 0.7));
  // B. a base de documentos, na ordem em que foi dada (a busca é que descobre quem vem primeiro)
  const xRotB = H ? xB : xB + U.tam * 1.9;
  ctx.place(U.R.d.el, { x: Math.round(xRotB), y: Math.round(yB) });
  ctx.place(U.R.s.el, { x: Math.round(xB + U.wB - U.R.s.w - (H ? 0 : U.pad * 0.7)), y: Math.round(yB) });   // vertical: não encosta no contorno "o modelo recebe"
  let y = yB + U.hCab, yb = yB + U.hCab;
  const docs = U.docs.map((x, i) => {
    const escolhido = D.colocacao[i] < k;
    const casca = ctx.el('div', 'rag-casca');                     // leva o deslocamento do arranjo B: a entrada da DA fica com o cartão
    Object.assign(casca.style, { position: 'absolute', left: Math.round(xB) + 'px', top: Math.round(y) + 'px', width: Math.round(U.wB) + 'px', height: '1px' });
    camada.appendChild(casca);
    const c = cartao(ctx, { w: U.wB, h: x.h, cor });
    casca.appendChild(c.el);
    c.em(0, 0);
    c.miolo.append(x.tit.el, x.val.el, x.tre.el);
    let b;
    const cr = U.crachas[i];
    if (H) {
      x.tit.em(U.pad, U.pad * 0.8);
      ctx.place(x.val.el, { x: Math.round(U.wB - U.pad - x.mv.w), y: Math.round(U.pad * 0.8 + (x.tit.h / x.tit.linhas - x.mv.h) / 2) });
      x.tre.em(U.pad, U.pad * 0.8 + x.tit.h + U.tamTit * 0.15);
      b = barra(ctx, { w: U.wB - 2 * U.pad - U.vagaBarra, h: x.hBarra, cor });
      c.miolo.appendChild(b.el);
      ctx.place(b.el, { x: Math.round(U.pad), y: Math.round(x.h - U.pad * 0.8 - x.hBarra) });
      if (cr) { c.miolo.appendChild(cr.el); cr.em(U.wB - U.pad - cr.w, x.h - U.pad * 0.65 - cr.h); }
    } else {
      x.tit.em(U.pad + U.vaga, (x.h - x.tit.h) / 2);
      ctx.place(x.val.el, { x: Math.round(U.wB - U.pad - x.mv.w), y: Math.round((x.h - x.mv.h) / 2) });
      x.tre.em(U.pad + U.vaga, x.h - U.pad * 0.15);
      b = barra(ctx, { w: U.wBarra, h: x.hBarra, cor });
      c.miolo.appendChild(b.el);
      ctx.place(b.el, { x: Math.round(U.wB - U.pad - x.mv.w - U.pad * 0.6 - U.wBarra), y: Math.round((x.h - x.hBarra) / 2) });
      if (cr) { c.miolo.appendChild(cr.el); cr.em(U.pad * 0.7, (x.h - cr.h) / 2); }
      c.miolo.style.overflow = 'hidden';                           // o trecho só aparece quando a linha abre
    }
    const item = { c, casca, ...x, b, cracha: cr, pontuacao: D.docs[i].pontuacao, colocacao: D.colocacao[i], escolhido, y, sobe: escolhido ? yb - y : 0 };
    y += x.h + U.vao;
    if (escolhido) yb += x.hAberto + U.vao;
    return item;
  });
  // C. o que o modelo recebe, e a resposta
  let painel = null, fichas = [], contorno = null, s1, s2, yResp;
  if (H) {
    ctx.place(U.R.c.el, { x: Math.round(xC), y: Math.round(y0) });
    const yPainel = y0 + U.R.c.h + U.vaoRot;
    painel = cartao(ctx, { w: U.wC, h: U.hPainel, cor });
    camada.appendChild(painel.el);
    painel.em(xC, yPainel);
    painel.miolo.appendChild(U.mini.el);
    U.mini.em(U.pad, U.pad * 0.8);
    let yf = U.pad * 0.8 + U.mini.h;
    fichas = U.fichas.map((f) => {
      yf += U.vao * 0.8;
      painel.miolo.append(f.nro.el, f.txt.el);
      f.nro.em(U.pad, yf + (f.h - f.nro.h) / 2);
      f.txt.em(U.pad + f.nro.w + U.pad * 0.6, yf + (f.h - f.txt.h) / 2);
      yf += f.h;
      return f;
    });
    yResp = yPainel + U.hPainel + U.vao * 2;
    const f = U.seta * 0.14, ya = cPerg.y + cPerg.h / 2, yc = yPainel + U.hPainel / 2;
    s1 = setaCurva(ctx, svg, reta(xA + U.wA + f, ya, xB - f, ya), { cor, esp });
    s2 = setaCurva(ctx, svg, reta(xB + U.wB + f, yc, xC - f, yc), { cor, esp });
  } else {
    // contorno "o modelo recebe": abraça a pergunta e os trechos escolhidos (no arranjo B)
    const yFim = yB + U.hCab + U.hSel + U.borda;
    contorno = ctx.el('div', 'rag-contorno');
    Object.assign(contorno.style, { position: 'absolute', left: Math.round(C.x - 0) + 'px', top: Math.round(yA - U.borda) + 'px', width: Math.round(C.w) + 'px', height: Math.round(yFim - (yA - U.borda)) + 'px', boxSizing: 'border-box',
      border: `${Math.max(2, ctx.traco * 1.2).toFixed(1)}px solid ${ctx.cor(cor)}`, borderRadius: (ctx.raio + U.borda * 0.5) + 'px' });
    camada.insertBefore(contorno, camada.firstChild);
    camada.appendChild(U.marca.el);
    U.marca.em(C.x1 - U.marca.w - U.pad, yA - U.borda - U.marca.h / 2);
    // dentro do contorno tudo recua a borda dele para os lados
    const xm = xB + U.tam * 0.85, f = U.seta * 0.16;
    s1 = setaCurva(ctx, svg, reta(xm, cPerg.y + cPerg.h + f, xm, yB + U.hCab - f * 2), { cor, esp });
    s2 = setaCurva(ctx, svg, reta(xm, yFim + f, xm, yFim + U.seta - f), { cor, esp });
    yResp = yFim + U.seta;
  }
  ctx.place(U.R.r.el, { x: Math.round(H ? xC : xB + U.tam * 1.9), y: Math.round(H ? yResp : yResp - U.seta * 0.5 - U.R.r.h / 2) });
  U.resp.em(xC, H ? yResp + U.R.r.h + U.vaoRot : yResp + U.vaoRot);
  const dig = digitador(ctx, U.resp.el);
  const d = ctx.DA.movimento.duracoes;
  P.marcar('resposta', d.curta + tResposta(d, D.resposta), 'fim_da_resposta', 'texto');
  guardar(ESTADOS, ctx, { ctx, Q, P, D, U, H, abre: abrir, cPerg, docs, painel, fichas, contorno, dig, s1, s2, k, tResp: tResposta(d, D.resposta), nPerg: String(p.pergunta).length });
  return Q.layout({ recuperados: recuperados.map((i, j) => ({ citacao: j + 1, titulo: D.docs[i].titulo, pontuacao: D.docs[i].pontuacao })), citados: [...new Set(D.citados)], k,
    arranjo: H ? 'colunas' : abrir ? 'coluna_com_trechos_abertos' : 'coluna_so_titulos', escala: +U.escala.toFixed(3), tamanho_titulo: +U.tamTit.toFixed(1), tamanho_resposta: +U.resp.tam.toFixed(1),
    bloco: { x: Math.round(C.x), y: y0, w: Math.round(C.w), h: Math.round(U.alt) } });
}

export function seek(t, ctxArg) {
  const { ctx, Q, P, D, U, H, abre, cPerg, docs, painel, fichas, contorno, dig, s1, s2, k, tResp, nPerg } = ler(ESTADOS, ctxArg);
  const d = ctx.DA.movimento.duracoes, e = ctx.escalonamento;
  // 1. a pergunta
  if (H) ctx.entrada(U.R.p.el, P.prog(t, 'pergunta', 0, d.media), 'fade');
  entrarBloco(ctx, cPerg.el, P.prog(t, 'pergunta', 0, d.media));
  ctx.entrada(U.perg.el, P.prog(t, 'pergunta', d.media * 0.5, d.longa), undefined, { n: nPerg });
  // 2. a busca: a seta, a base e a pontuação de cada trecho
  s1.tracar(P.prog(t, 'busca', 0, d.media, 'suave'));
  ctx.entrada(U.R.d.el, P.prog(t, 'busca', d.media * 0.5, d.media), 'fade');
  ctx.entrada(U.R.s.el, P.prog(t, 'busca', d.media * 2, d.media), 'fade');
  const pEscolha = P.prog(t, 'trechos', 0, d.media, 'enfase');
  const pCita = P.prog(t, 'citacao', 0, d.media, 'enfase');
  const citado1 = D.citados[0] - 1;
  // 4 (vertical). os não escolhidos saem; os escolhidos sobem e abrem o trecho
  const pSome = H ? 0 : P.prog(t, 'contexto', 0, d.media);
  const pSobe = H ? 0 : P.prog(t, 'contexto', d.media * 0.5, d.media * 1.5, 'suave');
  docs.forEach((dc, i) => {
    entrarBloco(ctx, dc.c.el, P.prog(t, 'busca', d.media + i * e * 3, d.media));
    const pm = P.prog(t, 'busca', d.media * 2 + i * e * 3, d.longa, 'suave');
    dc.b.estado({ fracao: dc.pontuacao * clamp(pm), realce: dc.escolhido ? pEscolha : 0, trilha: clamp(pm * 3) });
    dc.val.definir(dc.pontuacao * clamp(pm));
    dc.val.el.style.opacity = clamp(pm * 3).toFixed(3);
    // 3. ficam os k mais parecidos; 6. o trecho citado primeiro acende junto com a citação
    dc.c.estado({ realce: dc.escolhido ? clamp(pEscolha) : 0, apagado: dc.escolhido ? 0 : pEscolha, cheio: dc.colocacao === citado1 ? pCita : 0 });
    if (dc.cracha) dc.cracha.el.style.opacity = clamp(P.prog(t, 'trechos', d.media * 0.5, d.media)).toFixed(3);
    if (H) return;
    dc.casca.style.opacity = dc.escolhido ? '1' : (1 - clamp(pSome)).toFixed(3);
    dc.casca.style.transform = `translateY(${(dc.sobe * clamp(pSobe)).toFixed(2)}px)`;
    dc.c.altura(lerp(dc.h, dc.hAberto, dc.escolhido ? clamp(pSobe) : 0));
    dc.tre.el.style.opacity = (dc.escolhido && abre ? clamp(P.prog(t, 'contexto', d.media * 1.5, d.media)) : 0).toFixed(3);
  });
  // 4. o contexto: pergunta + trechos
  if (H) {
    s2.tracar(P.prog(t, 'contexto', 0, d.media, 'suave'));
    ctx.entrada(U.R.c.el, P.prog(t, 'contexto', d.media * 0.5, d.media), 'fade');
    entrarBloco(ctx, painel.el, P.prog(t, 'contexto', d.media * 0.5, d.media));
    ctx.entrada(U.mini.el, P.prog(t, 'contexto', d.media, d.media), 'fade');
    fichas.forEach((f, j) => {
      const pf = P.prog(t, 'contexto', d.media * 2 + j * e * 3, d.media);
      f.nro.el.style.opacity = clamp(pf * 2).toFixed(3);
      ctx.entrada(f.txt.el, pf, 'fade');
    });
  } else {
    const pc = P.prog(t, 'contexto', d.media * 2, d.media);
    ctx.entrada(contorno, pc, 'fade');
    ctx.entrada(U.marca.el, pc, 'fade');
    s2.tracar(P.prog(t, 'resposta', 0, d.curta, 'suave'));
  }
  // 5. a resposta chega escrita, com as citações
  ctx.entrada(U.R.r.el, P.prog(t, 'resposta', 0, d.curta), 'fade');
  dig.seek(P.lin(t, 'resposta', d.curta, tResp));
  Q.seek(t);
}

export function key(t, ctx) { return ler(ESTADOS, ctx).P.chave(t); }

export function ancoras(ctx) { return ler(ESTADOS, ctx).P.ancoras(); }
