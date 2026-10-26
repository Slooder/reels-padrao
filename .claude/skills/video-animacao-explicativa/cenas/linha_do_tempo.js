// linha_do_tempo.js — marcos com data, um por vez, sobre um eixo. Passos: marco1 → marco2 → … → [destaque].
// O eixo se desenha até o marco da vez; a data dele fica na cor do destaque e os anteriores continuam na tela.
// Fidelidade do eixo: em escala `uniforme` os marcos ficam igualmente espaçados e o eixo é TRACEJADO — ele mostra a
// ordem, não a distância no tempo; em escala `tempo` o eixo é contínuo e a posição de cada marco é proporcional ao
// campo `ano` (a cena recusa marcos que se encavalam em vez de empurrá-los para onde não estão).
// Data é dado: o exemplo padrão é inventado (selo "ilustrativo"); com `marcos` seus, a cena exige a escolha —
// ilustrativo=false + `fonte` (+ fato_ids no storyboard) para datas verificadas, ou ilustrativo=true.
import { params, guardar, ler, montarQuadro, escrever, caber, tamanho, exigir, igual, decidirIlustrativo, camadaSvg, linha, marcador, textoDuplo, num, clamp, lerp, encaixou, respiro } from './_ia.js';

const EXEMPLO = [
  { data: 'jan', titulo: 'Ideia', texto: 'o problema é definido' }, { data: 'mar', titulo: 'Dados', texto: 'coleta e limpeza' },
  { data: 'jun', titulo: 'Treino', texto: 'o modelo aprende com os dados' }, { data: 'set', titulo: 'Testes', texto: 'avaliação antes de lançar' },
  { data: 'dez', titulo: 'Lançamento', texto: 'aberto ao público' },
];

export const meta = {
  nome: 'linha_do_tempo',
  descricao: 'Linha do tempo: marcos com data que entram um por vez sobre um eixo (tracejado quando só mostra a ordem; contínuo e proporcional quando cada marco traz o ano).',
  dur_padrao: 13,
  formatos: ['horizontal', 'vertical', 'quadrado'],
  alfa_padrao: false,
  grao: true,
  params: params({
    marcos: { tipo: 'lista', min: 2, max: 7, padrao: EXEMPLO, descricao: 'os marcos, em ordem cronológica: a data como vai aparecer, um título curto e (opcional) uma linha de texto',
      itens: { tipo: 'objeto', campos: { data: { tipo: 'texto', obrigatorio: true }, titulo: { tipo: 'texto', obrigatorio: true }, texto: { tipo: 'texto', padrao: null },
        ano: { tipo: 'numero', padrao: null, descricao: 'posição no tempo para escala=tempo (2017, ou 2017.5 para meados de 2017)' } } } },
    escala: { tipo: 'opcao', opcoes: ['uniforme', 'tempo'], padrao: 'uniforme', descricao: 'uniforme = espaçamento igual, eixo tracejado (ordem, não distância); tempo = posição proporcional a `ano`, eixo contínuo' },
    destaque: { tipo: 'inteiro', padrao: null, min: 0, descricao: 'índice do marco que termina em destaque, num passo final (padrão: fica o último)' },
  }, { titulo: 'Linha do tempo', ilustrativo: 'dado' }),
};

export function roteiro(p, mov) {
  const d = mov.duracoes, marcos = p.marcos || EXEMPLO;
  decidirIlustrativo(p, !igual(marcos, EXEMPLO), 'linha_do_tempo');
  exigir(p.destaque == null || p.destaque < marcos.length, `destaque = ${p.destaque}, mas só há ${marcos.length} marcos (índices de 0 a ${marcos.length - 1})`);
  if (p.escala === 'tempo') {
    marcos.forEach((m, i) => {
      exigir(typeof m.ano === 'number', `escala "tempo": o marco ${i} (${m.data}) não tem "ano" — passe o ano de cada marco como número (2017, 2017.5) ou use escala "uniforme"`);
      if (i) exigir(m.ano > marcos[i - 1].ano, `escala "tempo": os marcos precisam estar em ordem crescente de "ano" (o marco ${i}, ${num(m.ano, 1)}, não vem depois de ${num(marcos[i - 1].ano, 1)})`);
    });
  }
  const r = marcos.map((_, i) => ({ nome: 'marco' + (i + 1), tipo: i ? 'texto' : 'entrada', anim: d.media * 2 + d.curta + (i ? 0 : d.media) }));
  if (p.destaque != null && p.destaque !== marcos.length - 1) r.push({ nome: 'destaque', tipo: 'enfase', anim: d.media });
  return r;
}

const ESTADOS = new WeakMap();

export function build(palco, p, ctx) {
  const marcos = p.marcos, N = marcos.length, cor = p.cor;
  const rot = roteiro(p, ctx.DA.movimento);
  const ilustrativo = decidirIlustrativo(p, !igual(marcos, EXEMPLO), 'linha_do_tempo');
  const Q = montarQuadro(palco, { ...p, ilustrativo }, ctx, { roteiro: rot });
  const C = Q.conteudo, P = Q.P, H = Q.horizontal;
  const svg = camadaSvg(ctx, Q.raiz);
  const camada = ctx.el('div', 'tempo-camada');
  Object.assign(camada.style, { position: 'absolute', left: '0', top: '0' });
  Q.raiz.appendChild(camada);
  const fracao = p.escala === 'tempo' ? marcos.map((m) => (m.ano - marcos[0].ano) / (marcos[N - 1].ano - marcos[0].ano)) : marcos.map((_, i) => i / (N - 1));

  const U = caber((s) => {
    const r = Math.max(5, tamanho(ctx, 'corpo', s) * 0.22);                // raio do ponto
    const vao = tamanho(ctx, 'corpo', s) * 0.9;
    // largura de cada rótulo: no horizontal os marcos alternam acima/abaixo do eixo, então cada um pode ter dois passos de largura
    const wRot = H ? Math.min((2 * (C.w + vao)) / (N + 1) - vao, ctx.col(5)) : C.w - 2 * r - vao;
    const blocos = marcos.map((m) => {
      const data = textoDuplo(ctx, 'dados', String(m.data), { tam: tamanho(ctx, 'h3', s), corA: 'texto', corB: cor, classe: 'tempo-data' });
      camada.appendChild(data.el); data.medir();
      const titulo = escrever(ctx, camada, 'titulo', String(m.titulo), { tam: tamanho(ctx, 'h3', s * 0.9), maxW: H ? wRot : wRot - data.w - vao * 0.6, maxLinhas: 2, classe: 'tempo-titulo' });
      const texto = m.texto && String(m.texto).trim() ? escrever(ctx, camada, 'corpo', String(m.texto), { tam: tamanho(ctx, 'corpo', s * 0.85), cor: 'texto_suave', maxW: wRot, maxLinhas: 3, classe: 'tempo-texto' }) : null;
      const v = titulo.tam * 0.18;
      // horizontal: data / título / texto empilhados; vertical: data e título na mesma linha, texto embaixo
      const h = H ? data.h + v + titulo.h + (texto ? v + texto.h : 0) : Math.max(data.h, titulo.h) + (texto ? v + texto.h : 0);
      const w = H ? Math.max(data.w, titulo.w, texto ? texto.w : 0) : Math.max(data.w + vao * 0.6 + titulo.w, texto ? texto.w : 0);
      return { data, titulo, texto, v, h, w };
    });
    const haste = vao * 0.9;
    let cabe, geo;
    if (H) {
      const cima = blocos.filter((_, i) => i % 2 === 0), baixo = blocos.filter((_, i) => i % 2 === 1);
      const hCima = Math.max(...cima.map((b) => b.h)), hBaixo = baixo.length ? Math.max(...baixo.map((b) => b.h)) : 0;
      const span = C.w - Math.max(blocos[N - 1].w, r * 2) - r;
      const xs = fracao.map((f) => C.x + r + f * span);
      const h = hCima + haste + 2 * r + (baixo.length ? haste + hBaixo : 0);
      cabe = h <= C.h * respiro(s);
      for (let i = 0; i < N; i++) {
        if (i + 2 < N && xs[i + 2] - xs[i] < blocos[i].w + vao * 0.5) cabe = false;      // vizinhos do mesmo lado do eixo
        if (i + 1 < N && xs[i + 1] - xs[i] < 3 * r) cabe = false;
      }
      geo = { xs, h, hCima, hBaixo, span };
    } else {
      const span = Math.max(1, C.h - blocos[N - 1].h);
      let ys, passo = null;
      if (p.escala === 'tempo') {
        ys = fracao.map((f) => f * span);
        cabe = blocos.slice(0, -1).every((bl, i) => ys[i + 1] - ys[i] >= bl.h + vao * 0.5);
      } else {                                                    // uniforme: o passo é o necessário (bloco centrado), não a altura toda
        passo = Math.min(span / (N - 1), Math.max(...blocos.map((bl) => bl.h)) + vao * 1.5);
        ys = blocos.map((_, i) => i * passo);
        cabe = blocos.slice(0, -1).every((bl) => passo >= bl.h + vao * 0.5) && (N - 1) * passo + blocos[N - 1].h <= C.h * respiro(s);
      }
      geo = { ys, h: ys[N - 1] + blocos[N - 1].h, passo };
    }
    return { cabe, r, vao, haste, wRot, blocos, ...geo, s };
  }, () => camada.replaceChildren(), { inicio: H ? 1.5 : 1.25 });
  exigir(U.cabe || p.escala !== 'tempo', 'escala "tempo": há marcos próximos demais no tempo para caberem no eixo sem encavalar (nem na menor letra legível). Use escala "uniforme" (eixo tracejado: mostra a ordem), tire marcos ou encurte os textos');
  encaixou(U, C, 'linha_do_tempo', 'encurte os textos ou tire marcos');

  const y0 = Math.round(C.y + Math.max(0, (C.h - U.h) / 2));
  const fio = Math.max(1, ctx.traco * 0.75);
  const tracejado = p.escala === 'tempo' ? null : `${(fio * 4).toFixed(1)} ${(fio * 4).toFixed(1)}`;
  let eixo, pontos;
  const itens = U.blocos.map((b, i) => {
    const m = marcador(ctx, { tipo: 'ponto', lado: 2 * U.r, cor, corBase: 'texto' });
    const h = ctx.el('div', 'tempo-haste');
    camada.append(h, m.el);
    let px, py;
    if (H) {
      const yE = y0 + U.hCima + U.haste + U.r;
      px = U.xs[i]; py = yE;
      const cima = i % 2 === 0;
      const yB = cima ? yE - U.r - U.haste - b.h : yE + U.r + U.haste;
      b.data.el.style.left = Math.round(px - U.r) + 'px'; b.data.el.style.top = Math.round(yB) + 'px';
      b.titulo.em(px - U.r, yB + b.data.h + b.v);
      if (b.texto) b.texto.em(px - U.r, yB + b.data.h + b.v + b.titulo.h + b.v);
      Object.assign(h.style, { position: 'absolute', left: (px - fio / 2).toFixed(1) + 'px', top: Math.round(cima ? yE - U.r - U.haste * 0.8 : yE + U.r) + 'px', width: fio.toFixed(1) + 'px', height: Math.round(U.haste * 0.8) + 'px',
        background: ctx.alfa('texto_suave', 0.8), transformOrigin: cima ? 'center bottom' : 'center top' });
    } else {
      const xE = C.x + U.r;
      const yB = y0 + U.ys[i];
      const hTopo = Math.max(b.data.h, b.titulo.h);
      px = xE; py = yB + hTopo / 2;
      const xB = xE + U.r + U.vao;
      b.data.el.style.left = Math.round(xB) + 'px'; b.data.el.style.top = Math.round(yB + (hTopo - b.data.h) / 2) + 'px';
      b.titulo.em(xB + b.data.w + U.vao * 0.6, yB + (hTopo - b.titulo.h) / 2);
      if (b.texto) b.texto.em(xB, yB + hTopo + b.v);
      Object.assign(h.style, { position: 'absolute', left: Math.round(xE + U.r) + 'px', top: (py - fio / 2).toFixed(1) + 'px', width: Math.round(U.vao * 0.7) + 'px', height: fio.toFixed(1) + 'px',
        background: ctx.alfa('texto_suave', 0.8), transformOrigin: 'left center' });
    }
    Object.assign(m.el.style, { left: (px - U.r).toFixed(1) + 'px', top: (py - U.r).toFixed(1) + 'px' });
    return { ...b, ponto: m, haste: h, px, py, letras: String(marcos[i].titulo).length, letrasTexto: String(marcos[i].texto || '').length };
  });
  if (H) {
    const yE = itens[0].py;
    eixo = linha(ctx, svg, C.x, yE, C.x1, yE, { cor: ctx.DA.graficos.dados.eixo, esp: fio * 1.5, tracejado });
    pontos = itens.map((it, i) => (i === N - 1 ? 1 : (it.px - C.x) / C.w));
  } else {
    const xE = itens[0].px, ya = itens[0].py, yb = itens[N - 1].py + U.r * 3;
    eixo = linha(ctx, svg, xE, ya, xE, yb, { cor: ctx.DA.graficos.dados.eixo, esp: fio * 1.5, tracejado });
    pontos = itens.map((it, i) => (i === N - 1 ? 1 : (it.py - ya) / (yb - ya)));
  }
  guardar(ESTADOS, ctx, { ctx, Q, P, p, itens, eixo, pontos, N, H, fim: p.destaque != null && p.destaque !== N - 1 });
  return Q.layout({ marcos: N, escala_do_eixo: p.escala, eixo: tracejado ? 'tracejado' : 'continuo', escala: +U.escala.toFixed(3), tamanho_data: +itens[0].data.a._tam.toFixed(1),
    bloco: { x: Math.round(C.x), y: y0, w: Math.round(C.w), h: Math.round(U.h) } });
}

export function seek(t, ctxArg) {
  const { ctx, Q, P, p, itens, eixo, pontos, N, H, fim } = ler(ESTADOS, ctxArg);
  const d = ctx.DA.movimento.duracoes;
  const pFim = fim ? P.prog(t, 'destaque', 0, d.media, 'enfase') : 0;
  let ate = 0;
  itens.forEach((it, i) => {
    const passo = 'marco' + (i + 1), at = i === 0 ? d.media : 0;
    // 1. o eixo chega ao marco; 2. o ponto e a haste; 3. data, título e texto
    const pEixo = P.prog(t, passo, 0, d.media + at, 'suave');
    ate = i === 0 ? pontos[0] * clamp(pEixo) : lerp(ate, pontos[i], clamp(pEixo));
    const pPonto = P.prog(t, passo, at + d.media * 0.5, d.media, 'enfase');
    it.ponto.el.style.opacity = clamp(pPonto * 1.5).toFixed(3);
    it.ponto.el.style.transform = `scale(${(0.5 + 0.5 * Math.min(pPonto, 1.25)).toFixed(4)})`;
    const ph = P.prog(t, passo, at + d.media * 0.5, d.media);
    it.haste.style.transform = H ? `scaleY(${clamp(ph).toFixed(4)})` : `scaleX(${clamp(ph).toFixed(4)})`;
    it.haste.style.opacity = ph > 0 ? '1' : '0';
    const pData = P.prog(t, passo, at + d.media, d.media);
    ctx.entrada(it.data.el, pData, 'fade');
    ctx.entrada(it.titulo.el, pData, undefined, { n: it.letras });
    if (it.texto) ctx.entrada(it.texto.el, P.prog(t, passo, at + d.media + d.curta, d.media), 'fade');
    const proximo = i < N - 1 ? P.prog(t, 'marco' + (i + 2), 0, d.media, 'suave') : 0;
    let daVez = clamp(pPonto) * (1 - clamp(proximo));
    if (fim) daVez = i === p.destaque ? Math.max(daVez, pFim) : daVez * (1 - pFim);
    it.ponto.misturar(daVez);
    it.data.misturar(daVez);
  });
  eixo.tracar(ate);
  Q.seek(t);
}

export function key(t, ctx) { return ler(ESTADOS, ctx).P.chave(t); }

export function ancoras(ctx) { return ler(ESTADOS, ctx).P.ancoras(); }
