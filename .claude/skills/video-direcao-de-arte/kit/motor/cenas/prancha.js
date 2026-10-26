// prancha.js — PRANCHA DE DIREÇÃO DE ARTE: a página que o cliente aprova. Estática (um quadro), altura pelo conteúdo
// (--formato 1920xauto ou 1080xauto). Monta as outras cenas em quadros reduzidos (ctx.sub) para mostrar GC, moldura,
// legenda, título, barras e thumbnail exatamente como o motor os renderiza. 100% tokens: nenhuma cor própria.
// A amostra de LEGENDA não é desenhada aqui: é o PNG que texto.compor_legenda produz (params.legenda), o mesmo caminho
// das legendas queimadas na produção — o que o cliente aprova é o que sai (D21). A seção "Em escala 1:1" mostra GC e
// legenda sobre o quadro do projeto sem redução: com a prancha na largura da tela do celular, é o tamanho real.
import * as cenaTitulo from './titulo.js';
import * as cenaGc from './gc.js';
import * as cenaMoldura from './moldura.js';
import * as cenaBarras from './barras.js';
import { criarLegenda, fraseDeAmostra, palavraDeConteudo } from './_legenda.js';
import { criarTarja } from './_tarja.js';

export const meta = {
  nome: 'prancha',
  descricao: 'Prancha de direção de arte: conceito, paleta com contraste, tipografia, componentes, tratamento antes/depois, curvas, margens seguras e thumbnail.',
  dur_padrao: 1,
  formatos: [],
  alfa_padrao: false,
  grao: false,
  params: {
    antes: { tipo: 'arquivo', padrao: null, descricao: 'quadro de referência sem tratamento (PNG/JPG)' },
    depois: { tipo: 'arquivo', padrao: null, descricao: 'o mesmo quadro com grade.json aplicado' },
    foto: { tipo: 'arquivo', padrao: null, descricao: 'foto para o GC e a thumbnail (opcional)' },
    legenda: { tipo: 'objeto', padrao: null, descricao: 'amostra de legenda feita por texto.compor_legenda (PNG recortado + posição no quadro deste formato, em px)',
      campos: { arquivo: { tipo: 'arquivo', obrigatorio: true }, x: { tipo: 'numero', obrigatorio: true }, y: { tipo: 'numero', obrigatorio: true }, w: { tipo: 'numero', obrigatorio: true }, h: { tipo: 'numero', obrigatorio: true },
        palavras: { tipo: 'lista', padrao: null }, falada: { tipo: 'inteiro', padrao: null } } },
    referencias: { tipo: 'lista', padrao: null, max: 8, descricao: 'imagens de conceito.referencias (arquivo + nota) para a seção de referências',
      itens: { tipo: 'objeto', campos: { arquivo: { tipo: 'arquivo', obrigatorio: true }, nota: { tipo: 'texto', padrao: '' }, nome: { tipo: 'texto', padrao: '' } } } },
    ref_proporcao: { tipo: 'numero', padrao: null, descricao: 'largura ÷ altura do quadro de referência (antes/depois em 9:16 na prancha vertical quando o footage é vertical)' },
    origem_referencia: { tipo: 'texto', padrao: null, descricao: 'de onde veio o quadro de referência (rótulo do antes/depois)' },
    titulo_exemplo: { tipo: 'texto', padrao: 'A conta que não fecha', descricao: 'título usado nas amostras' },
    nome_exemplo: { tipo: 'texto', padrao: 'Mariana Albuquerque', descricao: 'nome usado no GC de amostra' },
    cargo_exemplo: { tipo: 'texto', padrao: 'Procuradora de Justiça', descricao: 'cargo usado no GC de amostra' },
    data: { tipo: 'texto', padrao: null, descricao: 'data impressa no rodapé' },
    preset: { tipo: 'texto', padrao: null, descricao: 'nome do preset de origem (rodapé)' },
    cadeia: { tipo: 'texto', padrao: null, descricao: 'resumo da cadeia ffmpeg do tratamento (texto livre)' },
  },
};

const S = {};

// ───────────────────────────────────────────────────────────────── utilidades ──
function lum(hex) {
  const c = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map((v) => (v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
}
function contraste(a, b) { const la = lum(a), lb = lum(b); return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05); }
const ptbr = (x, casas = 1) => x.toLocaleString('pt-BR', { minimumFractionDigits: casas, maximumFractionDigits: casas });
function css(e, obj) { Object.assign(e.style, obj); return e; }

export async function build(palco, p, ctx) {
  const DA = ctx.DA;
  const vertical = ctx.L < 1400;
  const PAD = vertical ? 56 : 80;
  const W = ctx.L - 2 * PAD;
  const GAP = vertical ? 24 : 32;
  const u = ctx.L;                                            // unidade de layout da prancha: a própria largura
  const t = (f) => Math.round(u * f);                          // tamanhos relativos à largura da prancha
  const corTexto = ctx.cor('texto'), corSuave = ctx.cor('texto_suave'), corFundo = ctx.cor('fundo');
  const hair = `${Math.max(1, ctx.traco * 0.6).toFixed(1)}px solid ${ctx.alfa('texto', 0.14)}`;
  // a primária só vira TEXTO ou traço da própria prancha quando tem contraste para isso (DA clara com amarelo: 1,7:1)
  const corMarca = ctx.contraste('primaria', 'fundo') >= 3 ? 'primaria' : 'texto';
  const corMarcaSup = ctx.contraste('primaria', 'superficie') >= 3 ? 'primaria' : 'texto';
  const nomeExemplo = p.nome_exemplo, cargoExemplo = p.cargo_exemplo, tituloExemplo = p.titulo_exemplo;

  const pagina = css(ctx.el('div', 'prancha'), { position: 'relative', width: ctx.L + 'px', padding: `${PAD}px ${PAD}px ${PAD * 0.8}px`, display: 'flex',
    flexDirection: 'column', gap: (GAP * 2.2) + 'px', background: corFundo, color: corTexto });
  palco.appendChild(pagina);

  const rotulo = (txt, { cor = 'texto_suave', tam = t(0.0105) } = {}) => {
    const r = ctx.texto('dados', txt, { tam, cor });
    r._inner.style.letterSpacing = '0.16em'; r._inner.style.textTransform = 'uppercase';
    return r;
  };
  const corpo = (txt, { cor = 'texto', tam = t(0.0125), maxW = W, papel = 'corpo' } = {}) => ctx.texto(papel, txt, { tam, cor, wrap: true, maxW });

  function secao(titulo, nota) {
    const s = css(ctx.el('section', 'prancha-secao'), { display: 'flex', flexDirection: 'column', gap: GAP + 'px' });
    const cab = css(ctx.el('div'), { display: 'flex', alignItems: 'baseline', gap: GAP + 'px', paddingBottom: (GAP * 0.5) + 'px', borderBottom: hair });
    const num = rotulo(String(++S.n).padStart(2, '0'), { cor: corMarca });
    const tit = ctx.texto('subtitulo', titulo, { tam: t(0.0135), cor: 'texto' });
    S.mapa.push({ n: S.n, titulo, el: s });
    cab.append(num, tit);
    if (nota) { const n = corpo(nota, { cor: 'texto_suave', tam: t(0.0105), maxW: W * 0.6 }); n.style.marginLeft = 'auto'; n._inner.style.textAlign = 'right'; cab.appendChild(n); }
    s.appendChild(cab);
    pagina.appendChild(s);
    return s;
  }

  /** Quadro reduzido L×A em escala s (cenas montam dentro com ctx.sub). */
  function quadro(L, A, s, { fundoImg = null, legenda = null, pai = null } = {}) {
    const slot = css(ctx.el('div', 'prancha-slot'), { position: 'relative', width: Math.round(L * s) + 'px', display: 'flex', flexDirection: 'column', gap: (GAP * 0.4) + 'px' });
    if (pai) pai.appendChild(slot);                           // precisa estar no DOM antes de as cenas medirem texto
    const caixa = css(ctx.el('div'), { position: 'relative', width: Math.round(L * s) + 'px', height: Math.round(A * s) + 'px', overflow: 'hidden', borderRadius: ctx.raio + 'px', border: hair, background: corFundo });
    const frame = css(ctx.el('div', 'prancha-quadro'), { position: 'absolute', left: '0', top: '0', width: L + 'px', height: A + 'px', transform: `scale(${s})`, transformOrigin: 'left top', overflow: 'hidden', background: corFundo });
    if (fundoImg) {
      const im = document.createElement('img'); im.src = fundoImg; im.alt = ''; im.setAttribute('data-da-livre', 'referência');
      css(im, { position: 'absolute', inset: '0', width: '100%', height: '100%', objectFit: 'cover' });
      frame.appendChild(im);
    }
    caixa.appendChild(frame); slot.appendChild(caixa);
    // rotulo(txt): a legenda do quadro pode ser escrita depois de a cena montar (quando depende do que ela devolveu)
    const api = { slot, frame, caixa, rotulo(txt) { const n = nota(txt, Math.round(L * s)); slot.appendChild(n); S.medir.push(n); return n; } };
    if (legenda) api.rotulo(legenda);
    return api;
  }
  /** Legenda curta que quebra dentro de uma largura (papel dados, caixa alta). */
  function nota(txt, maxW) {
    const n = ctx.texto('dados', txt, { tam: t(0.0095), cor: 'texto_suave', wrap: true, maxW });
    n._inner.style.letterSpacing = '0.1em'; n._inner.style.textTransform = 'uppercase';
    return n;
  }

  S.n = 0; S.medir = []; S.ajustar = []; S.mapa = [];
  // ═══════════════════════════════════════════════════════════ 0. cabeçalho ══
  {
    const cab = css(ctx.el('header'), { display: 'flex', flexDirection: 'column', gap: (GAP * 0.9) + 'px' });
    const topo = css(ctx.el('div'), { display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: GAP + 'px' });
    const tarja = criarTarja(ctx, 'Direção de arte', { tam: t(0.012) });
    tarja.seek(1, 1);
    topo.appendChild(tarja.el);
    const m = DA._meta;
    const aprovadaOk = m.aprovada && !m.alterada_apos_aprovacao;
    const dataAprov = aprovadaOk && m.aprovada_em ? ' em ' + String(m.aprovada_em).slice(0, 10).split('-').reverse().join('/') : '';
    const estado = aprovadaOk ? `aprovada${dataAprov}` : m.aprovada ? 'alterada após aprovação — pede nova revisão' : 'rascunho — aguardando aprovação';
    const corEstado = aprovadaOk ? (ctx.contraste('positivo', 'fundo') >= 3 ? 'positivo' : 'texto') : m.aprovada ? (ctx.contraste('negativo', 'fundo') >= 3 ? 'negativo' : 'texto') : 'texto_suave';
    const metaTxt = css(ctx.el('div'), { display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: (GAP * 0.2) + 'px' });
    const l1 = rotulo(`revisão ${m.revisao} · ${estado}`, { cor: corEstado, tam: t(0.0115) });
    const l2 = rotulo(`${m.sha256.slice(0, 12)}…` + (p.preset ? ` · base ${p.preset}` : ''));
    metaTxt.append(l1, l2); S.medir.push(l1, l2);
    topo.appendChild(metaTxt);
    cab.appendChild(topo);
    const nome = ctx.texto('titulo', m.nome, { tam: t(vertical ? 0.085 : 0.062), cor: 'texto', wrap: true, maxW: W });
    cab.appendChild(nome);
    const frase = corpo(DA.conceito.frase, { tam: t(vertical ? 0.021 : 0.0165), maxW: vertical ? W : W * 0.78 });
    cab.appendChild(frase);
    if (DA.conceito.palavras_chave.length) {
      const chips = css(ctx.el('div'), { display: 'flex', flexWrap: 'wrap', gap: (GAP * 0.4) + 'px' });
      for (const k of DA.conceito.palavras_chave) {
        const c = ctx.texto('dados', k, { tam: t(0.0105), cor: 'texto' });
        css(c, { padding: `${t(0.004)}px ${t(0.01)}px`, border: `${Math.max(1, ctx.traco * 0.6).toFixed(1)}px solid ${ctx.alfa('texto', 0.35)}`, borderRadius: (ctx.raio || 2) + 'px' });
        chips.appendChild(c);
      }
      cab.appendChild(chips);
    }
    pagina.appendChild(cab);
    tarja.medir(); ctx.ajustar_texto(nome, W, { maxLinhas: 2, min: t(0.03) }); ctx.sem_orfa(nome); ctx.medir(frase); ctx.sem_orfa(frase);
  }

  // ═══════════════════════════════════════════════ referências do conceito (se houver) ══
  if (p.referencias && p.referencias.length) {
    const sec = secao('Referências', 'as imagens de conceito.referencias e o que se tirou de cada uma — a DA abaixo é a resposta a elas');
    const colunas = vertical ? 2 : Math.min(4, Math.max(2, p.referencias.length));
    const grade = css(ctx.el('div'), { display: 'grid', gridTemplateColumns: `repeat(${colunas}, minmax(0, 1fr))`, gap: GAP + 'px' });
    const larg = (W - (colunas - 1) * GAP) / colunas;
    for (const r of p.referencias.slice(0, 8)) {
      const card = css(ctx.el('div'), { display: 'flex', flexDirection: 'column', gap: (GAP * 0.35) + 'px' });
      const cx = css(ctx.el('div'), { width: larg + 'px', height: Math.round(larg * 9 / 16) + 'px', overflow: 'hidden', borderRadius: ctx.raio + 'px', border: hair, background: ctx.cor('superficie') });
      const im = document.createElement('img'); im.src = r.arquivo; im.alt = ''; im.setAttribute('data-da-livre', 'referência do conceito');
      css(im, { width: '100%', height: '100%', objectFit: 'contain', display: 'block' });
      cx.appendChild(im);
      card.appendChild(cx);
      if (r.nome) { const n = nota(r.nome, larg); card.appendChild(n); S.medir.push(n); }
      if (r.nota) { const e = corpo(r.nota, { tam: t(0.0105), maxW: larg }); card.appendChild(e); S.medir.push(e); }
      grade.appendChild(card);
    }
    sec.appendChild(grade);
  }

  // ═══════════════════════════════════════════════════════════ 1. paleta ══
  {
    const sec = secao('Paleta', 'razão de contraste WCAG de cada cor sobre o fundo; AA = 4,5:1 para texto, 3:1 para traço e ícone');
    const nCol = vertical ? 3 : 5;
    const larguraCol = Math.floor((W - (nCol - 1) * GAP) / nCol);
    const grade = css(ctx.el('div'), { display: 'grid', gridTemplateColumns: `repeat(${nCol}, minmax(0, 1fr))`, gap: GAP + 'px' });
    for (const [k, hex] of Object.entries(DA.cor.paleta)) {
      const card = css(ctx.el('div'), { display: 'flex', flexDirection: 'column', gap: (GAP * 0.35) + 'px' });
      const sw = css(ctx.el('div'), { height: t(vertical ? 0.075 : 0.07) + 'px', background: hex, borderRadius: ctx.raio + 'px', border: hair, position: 'relative', padding: t(0.008) + 'px', display: 'flex', alignItems: 'flex-end' });
      const sobre = contraste(hex, corTexto) >= contraste(hex, corFundo) ? 'texto' : 'fundo';
      const hexTxt = ctx.texto('dados', hex, { tam: t(0.011), cor: sobre });
      sw.appendChild(hexTxt);
      const nomeTok = ctx.texto('subtitulo', k.replace(/_/g, ' '), { tam: t(0.0125), cor: 'texto', wrap: true, maxW: larguraCol });
      const c = k === 'fundo' ? null : contraste(hex, corFundo);
      const info = corpo(c == null ? 'fundo do quadro' : `${ptbr(c, 1)}:1 sobre o fundo · ${c >= 7 ? 'AAA' : c >= 4.5 ? 'AA' : c >= 3 ? 'AA grande / traço' : 'só superfície'}`,
        { cor: 'texto_suave', tam: t(0.0098), maxW: larguraCol });
      card.append(sw, nomeTok, info);
      grade.appendChild(card);
      S.medir.push(hexTxt, nomeTok, info);
    }
    sec.appendChild(grade);
    // dados, neutros e gradientes
    const linha = css(ctx.el('div'), { display: 'grid', gridTemplateColumns: vertical ? '1fr' : '2fr 1fr 1fr', gap: GAP + 'px' });
    const bloco = (titulo, filhos) => {
      const b = css(ctx.el('div'), { display: 'flex', flexDirection: 'column', gap: (GAP * 0.4) + 'px' });
      b.appendChild(rotulo(titulo));
      const faixa = css(ctx.el('div'), { display: 'flex', gap: (GAP * 0.3) + 'px', flexWrap: 'wrap' });
      for (const f of filhos) faixa.appendChild(f);
      b.appendChild(faixa);
      return b;
    };
    const amostra = (hex, etiqueta, largura) => {
      const a = css(ctx.el('div'), { display: 'flex', flexDirection: 'column', gap: (GAP * 0.25) + 'px', width: largura + 'px' });
      a.appendChild(css(ctx.el('div'), { height: t(0.028) + 'px', background: hex, borderRadius: ctx.raio + 'px', border: hair }));
      const e = ctx.texto('dados', etiqueta, { tam: t(0.0092), cor: 'texto_suave', wrap: true, maxW: largura, html: etiqueta.replace(' ', '<br>') }); a.appendChild(e); S.medir.push(e);
      return a;
    };
    const lw = vertical ? Math.floor((W - GAP * 0.3 * 7) / 7) : Math.min(t(0.062), Math.floor((W * 0.5 - GAP * 0.3 * (DA.cor.dados.length - 1)) / DA.cor.dados.length));
    const tokDado = DA.cor.dados_tokens || [];
    linha.appendChild(bloco('Série de dados (ordem fixa)', DA.cor.dados.map((h, i) => amostra(h, `dado-${i + 1} ${tokDado[i] ? '= ' + tokDado[i].replace(/_/g, ' ') : h}`, lw))));
    linha.appendChild(bloco('Neutros tolerados', DA.cor.neutros.map((h, i) => amostra(h, `neutro-${i + 1} ${h}`, lw))));
    const grads = Object.entries(DA.cor.gradientes);
    linha.appendChild(bloco('Gradientes', grads.length ? grads.map(([n, g]) => { const a = amostra('transparent', n, lw * 2); a.firstChild.style.background = g.css; return a; })
      : [corpo('nenhum', { cor: 'texto_suave', tam: t(0.0098) })]));
    sec.appendChild(linha);
  }

  // ═══════════════════════════════════════════════════════════ 2. tipografia ══
  {
    const sec = secao('Tipografia', 'papéis tipográficos e a escala (frações do lado menor do quadro; px em 1080)');
    const lista = css(ctx.el('div'), { display: 'flex', flexDirection: 'column', gap: (GAP * 0.9) + 'px' });
    const amostras = { titulo: 'Ação, coração, avô', subtitulo: 'Ação, coração, avô — ç ã õ é', corpo: 'Ação, coração, avô — ç ã õ é à ü. Números 0123456789 e sinais R$ % ±',
      dados: '0123456789 R$ 1.234,56 · 23h59 · ç ã õ é', legenda: 'Ação, coração, avô' };
    const tamanhos = { titulo: ctx.tam('h1') * (vertical ? 0.75 : 0.7), subtitulo: ctx.tam('h3'), corpo: ctx.tam('corpo'), dados: ctx.tam('corpo'), legenda: ctx.px(DA.legenda.tamanho) * 0.8 };
    for (const [nome, pp] of Object.entries(DA.tipografia.papeis)) {
      const linha = css(ctx.el('div'), { display: 'grid', gridTemplateColumns: vertical ? '1fr' : `${t(0.16)}px 1fr`, gap: GAP + 'px', alignItems: 'center', paddingBottom: (GAP * 0.6) + 'px', borderBottom: hair });
      const esq = css(ctx.el('div'), { display: 'flex', flexDirection: 'column', gap: (GAP * 0.2) + 'px' });
      esq.appendChild(ctx.texto('subtitulo', nome, { tam: t(0.0125), cor: corMarca }));
      const det = [`${pp.familia} ${pp.peso}${pp.estilo === 'italic' ? ' itálico' : ''}`, `caixa ${pp.caixa} · tracking ${ptbr(pp.tracking, 3)} em · entrelinha ${ptbr(pp.altura_linha, 2)}`];
      if (pp.largura != null) det.push(`largura ${pp.largura}%`);
      if (pp.escala_x && pp.escala_x !== 1) det.push(`escala_x ${ptbr(pp.escala_x, 2)} (condensação)`);
      if (pp.eixos && Object.keys(pp.eixos).length) det.push('eixos ' + Object.entries(pp.eixos).map(([k, v]) => `${k} ${v}`).join(' · '));
      det.push(pp.arquivo ? pp.arquivo.replace(/^fontes\//, '') : 'fonte do sistema');
      for (const d of det) { const e = corpo(d, { cor: 'texto_suave', tam: t(0.0095), maxW: vertical ? W : t(0.16) }); esq.appendChild(e); S.medir.push(e); }
      const dir = ctx.texto(nome, amostras[nome] || 'Ação, coração, avô — ç ã õ é', { tam: tamanhos[nome] || ctx.tam('corpo'), cor: 'texto', wrap: true, maxW: vertical ? W : W - t(0.16) - GAP });
      linha.append(esq, dir);
      lista.appendChild(linha);
      S.medir.push(dir);
      S.ajustar.push([dir, vertical ? W : W - t(0.16) - GAP]);
    }
    sec.appendChild(lista);
    const esc = css(ctx.el('div'), { display: 'flex', alignItems: 'baseline', gap: GAP + 'px', flexWrap: 'wrap' });
    for (const [n, f] of Object.entries(DA.tipografia.escala)) {
      const b = css(ctx.el('div'), { display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: '2px' });
      const aa = ctx.texto('titulo', 'Aa', { tam: f * 1080 * (vertical ? 0.55 : 0.62), cor: 'texto' });
      aa._inner.style.textTransform = 'none';
      aa._inner.style.lineHeight = '1';
      const r = rotulo(`${n} ${ptbr(f, 3)} · ${Math.round(f * 1080)} px`, { tam: t(0.0092) });
      b.append(aa, r); esc.appendChild(b); S.medir.push(aa, r);
    }
    sec.appendChild(esc);
  }

  // ═══════════════════════════════════════════════ 3. componentes (quadros reduzidos) ══
  const fundoRef = p.depois || p.antes || null;
  const L2 = vertical ? 1080 : 1920, A2 = vertical ? 1920 : 1080;
  // amostra de legenda: as palavras vêm de quem gerou o PNG (texto.compor_legenda); sem PNG, a peça do motor (mesma conta)
  const cue = (p.legenda && p.legenda.palavras) || fraseDeAmostra(DA.legenda.max_palavras, tituloExemplo);
  const falada = p.legenda && p.legenda.falada != null ? p.legenda.falada : palavraDeConteudo(cue);
  function porLegenda(frame, cx) {
    if (p.legenda) {
      const im = document.createElement('img'); im.src = p.legenda.arquivo; im.alt = '';
      im.setAttribute('data-da-livre', 'legenda desenhada por texto.compor_legenda (o caminho da produção)');
      css(im, { position: 'absolute', left: p.legenda.x + 'px', top: p.legenda.y + 'px', width: p.legenda.w + 'px', height: p.legenda.h + 'px' });
      frame.appendChild(im);
      return { x0: p.legenda.x, y0: p.legenda.y, x1: p.legenda.x + p.legenda.w, y1: p.legenda.y + p.legenda.h };
    }
    const leg = criarLegenda(cx, cue, { falada, formato: vertical ? 'vertical' : 'horizontal' });
    frame.appendChild(leg.el); leg.posicionar();
    return leg.layout.caixa;
  }
  // O GC da prancha é o da PRODUÇÃO: reservar_legenda null = o que legenda.reservar_em da DA mandar neste formato.
  // Onde a DA reserva a faixa da legenda, GC e legenda aparecem juntos (o GC desvia). Onde não reserva e os dois ocupam
  // a mesma faixa, a prancha NÃO os mostra juntos: o GC fica onde a produção o põe e a legenda ganha uma tira própria.
  const paramsGc = { nome: nomeExemplo, cargo: cargoExemplo, foto: p.foto, selo: null, plataforma: null, entrada_em: 0, saida_em: null, reservar_legenda: null };
  const fmtNome = vertical ? 'vertical' : 'horizontal';
  const sonda = ctx.sub({ L: L2, A: A2, palco: ctx.palco, dur: 5, alfa: true });
  const reservaAqui = sonda.area_livre().reservou;
  const faixaLeg = sonda.faixa_legenda();
  const cruza = (g, f) => g.x < f.x1 && f.x0 < g.x1 && g.y < f.y1 && f.y0 < g.y1;
  let caixaGc = null, caixaLeg = null, juntos = true;
  {
    const sec = secao('Componentes', 'montados pelo motor com estes mesmos tokens: cartela de título, GC e moldura de b-roll' +
      (reservaAqui ? ' — a legenda entra junto e o GC desvia da faixa dela' : ` — "${fmtNome}" não está em legenda.reservar_em: aqui as peças não desviam da legenda`));
    const fila = css(ctx.el('div'), { display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: GAP + 'px' });
    sec.appendChild(fila);
    const s = (W - 2 * GAP) / 3 / L2;
    // título
    const q1 = quadro(L2, A2, s, { pai: fila, legenda: `cartela de título · entrada "${DA.movimento.entrada_padrao}" · saída "${DA.movimento.saida_padrao}"` });
    const c1 = ctx.sub({ L: L2, A: A2, palco: q1.frame, dur: 4 });
    await cenaTitulo.build(q1.frame, { titulo: tituloExemplo, sobretitulo: 'Capítulo 2', subtitulo: 'Como o dinheiro some no caminho até Brasília', alinhar: 'esquerda', posicao: 'centro', escala_titulo: 'display', assinatura: true, plataforma: null, reservar_legenda: null }, c1);
    cenaTitulo.seek(2.4);
    // GC + legenda sobre o quadro tratado
    const q2 = quadro(L2, A2, s, { pai: fila, fundoImg: fundoRef, legenda: '' });
    const c2 = ctx.sub({ L: L2, A: A2, palco: q2.frame, dur: 5, alfa: true });
    const lg = await cenaGc.build(q2.frame, paramsGc, c2);
    cenaGc.seek(2.5);
    caixaGc = lg.caixa;
    juntos = !!lg.reservou_legenda || !cruza(caixaGc, faixaLeg);
    if (juntos) caixaLeg = porLegenda(q2.frame, c2);
    q2.rotulo(juntos ? `GC "${DA.graficos.gc.estilo}" + legenda "${DA.legenda.estilo}" ${p.legenda ? 'desenhada por texto.py, como na produção' : '(peça do motor)'}`
      : `GC "${DA.graficos.gc.estilo}" na posição da produção · sem legenda: neste formato os dois ocupam a mesma faixa (veja "Em escala 1:1")`);
    // moldura
    const q3 = quadro(L2, A2, s, { pai: fila, fundoImg: fundoRef, legenda: `moldura "${DA.tratamento.moldura.estilo}" (janela transparente) com rótulo` });
    const c3 = ctx.sub({ L: L2, A: A2, palco: q3.frame, dur: 6, alfa: true });
    await cenaMoldura.build(q3.frame, { rotulo: 'Arquivo · 2018', sub: 'Reprodução', area: null, inclinacao: null, estilo: null, plataforma: null, reservar_legenda: null }, c3);
    cenaMoldura.seek(3);
  }

  // ═══════════════════════════════════════════════ 4. em escala 1:1 (faixa do quadro sem redução) ══
  {
    const lg = DA.legenda, gc = DA.graficos.gc;
    const sec = secao('Em escala 1:1', `legenda ${Math.round(lg.tamanho * 1080)} px · nome do GC ${Math.round(gc.tamanho_nome * 1080)} px · cargo ${Math.round(gc.tamanho_cargo * 1080)} px — com a prancha na largura da tela, é o tamanho real no vídeo`);
    const folga = 110;
    /** Tira do quadro L2×A2 de y0 a y1, sem redução: o GC e/ou a legenda na posição real. Devolve a caixa da legenda. */
    async function tira(y0, y1, comGc, comLegenda, texto) {
      const faixa = css(ctx.el('div', 'prancha-1x1'), { position: 'relative', width: L2 + 'px', height: (y1 - y0) + 'px', marginLeft: -PAD + 'px', overflow: 'hidden', background: corFundo });
      sec.appendChild(faixa);
      const frame = css(ctx.el('div', 'prancha-quadro'), { position: 'absolute', left: '0', top: -y0 + 'px', width: L2 + 'px', height: A2 + 'px', overflow: 'hidden', background: ctx.cor('superficie') });
      faixa.appendChild(frame);
      if (fundoRef) {
        const im = document.createElement('img'); im.src = fundoRef; im.alt = ''; im.setAttribute('data-da-livre', 'referência');
        css(im, { position: 'absolute', inset: '0', width: '100%', height: '100%', objectFit: 'cover' });
        frame.appendChild(im);
      }
      let cxLeg = null, caixa = null;
      if (comGc) {
        const gc1 = await ctx.kit.cena('gc', paramsGc, { palco: frame, L: L2, A: A2, dur: 5, alfa: true });
        gc1.seek(2.5);
        cxLeg = gc1.ctx;
      }
      if (comLegenda) caixa = porLegenda(frame, cxLeg || ctx.sub({ L: L2, A: A2, palco: frame, dur: 5, alfa: true }));
      const n = nota(`faixa de ${L2} × ${y1 - y0} px do quadro ${L2}×${A2} (de y ${y0} a ${y1}), sem redução · ${texto}` + (fundoRef ? ' · sobre o quadro do projeto já tratado' : ''), W);
      sec.appendChild(n); S.medir.push(n);
      return caixa;
    }
    const corta = (a, b) => [Math.max(0, Math.round(a - folga)), Math.min(A2, Math.round(b + folga))];
    if (juntos) {
      const [y0, y1] = corta(Math.min(caixaGc.y, caixaLeg.y0), Math.max(caixaGc.y1, caixaLeg.y1));
      await tira(y0, y1, true, true, 'GC e legenda ao mesmo tempo, na posição real' + (reservaAqui ? ' (o GC desvia da faixa da legenda)' : ''));
      S.faixa1x1 = { y0, y1, gc: caixaGc, legenda: caixaLeg, juntos: true, reservou_legenda: !!reservaAqui, faixa_legenda: faixaLeg, tiras: [{ y0, y1, conteudo: 'gc+legenda' }] };
    } else {
      // a DA não reserva a faixa da legenda neste formato: é isto que a produção entrega — cada peça no seu lugar, uma por vez
      const [g0, g1] = corta(caixaGc.y, caixaGc.y1);
      await tira(g0, g1, true, false, `GC na posição da produção — "${fmtNome}" não está em legenda.reservar_em, então ele não desvia da legenda`);
      const [l0, l1] = corta(faixaLeg.y0, faixaLeg.y1);
      caixaLeg = await tira(l0, l1, false, true, `legenda na posição real, sozinha: ocupa a mesma faixa do GC (y ${Math.round(faixaLeg.y0)} a ${Math.round(faixaLeg.y1)}) — se este formato levar legenda queimada, inclua "${fmtNome}" em legenda.reservar_em e o GC passa a desviar`);
      S.faixa1x1 = { y0: g0, y1: g1, gc: caixaGc, legenda: caixaLeg, juntos: false, reservou_legenda: false, faixa_legenda: faixaLeg, tiras: [{ y0: g0, y1: g1, conteudo: 'gc' }, { y0: l0, y1: l1, conteudo: 'legenda' }] };
    }
  }

  // ═══════════════════════════════════════════════════ 5. tratamento antes/depois ══
  {
    const g = DA.tratamento.grade;
    const partes = [`contraste ${ptbr(g.contraste, 2)}`, `saturação ${ptbr(g.saturacao, 2)}`, `gama ${ptbr(g.gama, 2)}`, `exposição ${ptbr(g.exposicao, 1)} EV`,
      `temperatura ${g.temperatura}`, `matiz ${g.matiz}°`, g.lut ? `LUT ${g.lut} ${Math.round(g.intensidade_lut * 100)}%` : 'sem LUT',
      DA.tratamento.duotone.ativo ? `duotone ${DA.tratamento.duotone.sombra}→${DA.tratamento.duotone.luz}` : 'sem duotone',
      DA.tratamento.grao.ativo ? `grão ${DA.tratamento.grao.intensidade}${DA.tratamento.grao.temporal ? ' temporal' : ''}` : 'sem grão',
      DA.tratamento.vinheta.ativo ? `vinheta ${ptbr(DA.tratamento.vinheta.angulo, 2)}` : 'sem vinheta',
      DA.tratamento.nitidez ? `nitidez ${ptbr(DA.tratamento.nitidez, 2)}` : null, DA.tratamento.desfoque ? `desfoque ${ptbr(DA.tratamento.desfoque, 3)}` : null].filter(Boolean);
    const sec = secao('Tratamento de imagem', partes.join(' · '));
    const fila = css(ctx.el('div'), { display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: GAP + 'px' });
    const imgW = (W - GAP) / 2;
    // footage vertical na prancha vertical aparece inteiro (9:16); nos outros casos, no enquadramento 16:9 do quadro
    const emPe = vertical && p.ref_proporcao != null && p.ref_proporcao < 0.9;
    const imgH = Math.round(emPe ? Math.min(imgW / Math.max(p.ref_proporcao, 0.5), imgW * 16 / 9) : imgW * 9 / 16);
    for (const [rot, src] of [['antes · ' + (p.origem_referencia || 'bruto'), p.antes], ['depois · grade.json aplicado (' + (p.cadeia ? 'cadeia completa' : 'cor + acabamento') + ')', p.depois]]) {
      const b = css(ctx.el('div'), { display: 'flex', flexDirection: 'column', gap: (GAP * 0.4) + 'px' });
      const cx = css(ctx.el('div'), { width: imgW + 'px', height: imgH + 'px', overflow: 'hidden', borderRadius: ctx.raio + 'px', border: hair, background: ctx.cor('superficie'), display: 'flex', alignItems: 'center', justifyContent: 'center' });
      if (src) { const im = document.createElement('img'); im.src = src; im.alt = ''; im.setAttribute('data-da-livre', 'referência'); css(im, { width: '100%', height: '100%', objectFit: 'cover' }); cx.appendChild(im); }
      else { const e = corpo('sem quadro de referência — passe --referencia <imagem> ao gerar a prancha', { cor: 'texto_suave', tam: t(0.011), maxW: imgW * 0.7 }); e._inner.style.textAlign = 'center'; cx.appendChild(e); S.medir.push(e); }
      const r = nota(rot, imgW); b.append(cx, r); S.medir.push(r);
      fila.appendChild(b);
    }
    sec.appendChild(fila);
    if (p.cadeia) { const c = corpo(p.cadeia, { cor: 'texto_suave', tam: t(0.0088), papel: 'dados', maxW: W }); c._inner.style.wordBreak = 'break-all'; sec.appendChild(c); S.medir.push(c); }
  }

  // ═══════════════════════════════════════ 6. gráfico de dados + curvas de movimento ══
  {
    const sec = secao('Dados e movimento', 'gráfico de barras com a série cor.dados · curvas cubic-bezier com as durações da DA · transições permitidas a meio caminho');
    const fila = css(ctx.el('div'), { display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: GAP + 'px', alignItems: 'start' });
    sec.appendChild(fila);
    const s = ((W - GAP) / 2) / L2;
    const q = quadro(L2, A2, s, { pai: fila, legenda: `barras · grade ${DA.graficos.dados.grade} · eixo ${DA.graficos.dados.eixo} · rótulos em "${DA.graficos.dados.rotulo}"` });
    const cb = ctx.sub({ L: L2, A: A2, palco: q.frame, dur: 60 });
    await cenaBarras.build(q.frame, { titulo: 'Quanto cada estado recebe de volta por real enviado', dados: [{ rotulo: 'Santa Catarina', valor: 0.31 }, { rotulo: 'São Paulo', valor: 0.28 }, { rotulo: 'Paraná', valor: 0.42 }, { rotulo: 'Bahia', valor: 1.65 }, { rotulo: 'Maranhão', valor: 2.4 }, { rotulo: 'Piauí', valor: 2.9 }],
      unidade: '', prefixo: 'R$ ', casas: 2, destaque: null, max: null, fonte: 'Tesouro Nacional, 2024', cores: 'serie', plataforma: null, empilhado: null, reservar_legenda: null }, cb);
    cenaBarras.seek(30);                                       // bem depois do fim da entrada, em qualquer DA: valores finais
    const mov = css(ctx.el('div'), { display: 'flex', flexDirection: 'column', gap: GAP + 'px' });
    fila.appendChild(mov);
    const metade = (W - GAP) / 2;
    const curvas = css(ctx.el('div'), { display: 'grid', gridTemplateColumns: `repeat(${vertical ? 2 : 5}, minmax(0, 1fr))`, gap: GAP + 'px' });
    const lado = vertical ? Math.floor((metade - GAP) / 2) : Math.floor((metade - 4 * GAP) / 5);
    for (const [nome, c] of Object.entries(DA.movimento.curvas)) {
      const b = css(ctx.el('div'), { display: 'flex', flexDirection: 'column', gap: (GAP * 0.3) + 'px' });
      const pad = 10, g = lado - 2 * pad, yMin = Math.min(0, c[1], c[3]) - 0.05, yMax = Math.max(1, c[1], c[3]) + 0.05;
      const X = (x) => pad + x * g, Y = (y) => pad + (1 - (y - yMin) / (yMax - yMin)) * g;
      const sv = ctx.svg('svg', { width: lado, height: lado, viewBox: `0 0 ${lado} ${lado}` });
      sv.appendChild(ctx.svg('rect', { x: 0.5, y: 0.5, width: lado - 1, height: lado - 1, fill: ctx.cor('superficie'), stroke: ctx.alfa('texto', 0.12), rx: ctx.raio }));
      sv.appendChild(ctx.svg('line', { x1: X(0), y1: Y(0), x2: X(1), y2: Y(0), stroke: ctx.alfa('texto', 0.18), 'stroke-width': 1 }));
      sv.appendChild(ctx.svg('line', { x1: X(0), y1: Y(1), x2: X(1), y2: Y(1), stroke: ctx.alfa('texto', 0.18), 'stroke-width': 1, 'stroke-dasharray': '3 3' }));
      sv.appendChild(ctx.svg('line', { x1: X(0), y1: Y(0), x2: X(c[0]), y2: Y(c[1]), stroke: ctx.alfa('texto_suave', 0.6), 'stroke-width': 1 }));
      sv.appendChild(ctx.svg('line', { x1: X(1), y1: Y(1), x2: X(c[2]), y2: Y(c[3]), stroke: ctx.alfa('texto_suave', 0.6), 'stroke-width': 1 }));
      sv.appendChild(ctx.svg('path', { d: `M ${X(0)} ${Y(0)} C ${X(c[0])} ${Y(c[1])}, ${X(c[2])} ${Y(c[3])}, ${X(1)} ${Y(1)}`, fill: 'none', stroke: ctx.cor(corMarcaSup), 'stroke-width': Math.max(2, ctx.traco * 0.8) }));
      for (const [px, py] of [[c[0], c[1]], [c[2], c[3]]]) sv.appendChild(ctx.svg('circle', { cx: X(px), cy: Y(py), r: 3.5, fill: ctx.cor('texto_suave') }));
      b.appendChild(sv);
      const n = ctx.texto('subtitulo', nome, { tam: t(0.011), cor: 'texto' });
      const v = corpo(`[${c.map((x) => ptbr(x, 2)).join(', ')}]` + (nome === 'entrada' ? ` · ${DA.movimento.entrada_padrao}` : nome === 'saida' ? ` · ${DA.movimento.saida_padrao}` : ''), { cor: 'texto_suave', tam: t(0.0088), maxW: lado });
      b.append(n, v); curvas.appendChild(b); S.medir.push(n, v);
    }
    mov.appendChild(curvas);
    const durs = css(ctx.el('div'), { display: 'flex', gap: GAP + 'px', flexWrap: 'wrap', alignItems: 'flex-end' });
    for (const [n, d] of Object.entries(DA.movimento.duracoes)) {
      const b = css(ctx.el('div'), { display: 'flex', flexDirection: 'column', gap: '4px', alignItems: 'flex-start' });
      b.appendChild(css(ctx.el('div'), { width: Math.round(d * t(0.14)) + 'px', height: Math.max(3, ctx.traco) + 'px', background: ctx.cor(corMarca) }));
      const r = rotulo(`${n} ${ptbr(d, 2)} s`, { tam: t(0.0092) }); b.appendChild(r); S.medir.push(r);
      durs.appendChild(b);
    }
    const r2 = rotulo(`escalonamento ${ptbr(DA.movimento.escalonamento, 2)} s`, { tam: t(0.0092) });
    durs.appendChild(r2); S.medir.push(r2);
    mov.appendChild(durs);
    // transições permitidas, cada uma a meio caminho (p = 0,5) entre um plano A e um plano B — a padrão vem marcada
    {
      const tr = DA.movimento.transicoes;
      const cab = nota(`transições permitidas (padrão: ${tr.padrao}) · a meio caminho de A para B`, metade);
      mov.appendChild(cab); S.medir.push(cab);
      const tira = css(ctx.el('div'), { display: 'flex', gap: (GAP * 0.6) + 'px', flexWrap: 'wrap' });
      const tw = Math.min(t(0.085), Math.floor((metade - 3 * GAP * 0.6) / 4)), th = Math.round(tw * (vertical ? 16 / 9 : 9 / 16));
      for (const nome of tr.permitidas) {
        const b = css(ctx.el('div'), { display: 'flex', flexDirection: 'column', gap: '4px' });
        const cx = css(ctx.el('div'), { position: 'relative', width: tw + 'px', height: th + 'px', overflow: 'hidden', border: nome === tr.padrao ? `2px solid ${ctx.cor(corMarca)}` : hair, borderRadius: ctx.raio + 'px', background: corFundo });
        const mk = (letra, bg, cor) => { const c = css(ctx.el('div'), { position: 'absolute', inset: '0', background: ctx.cor(bg), display: 'flex', alignItems: 'center', justifyContent: 'center' });
          const e = ctx.texto('titulo', letra, { tam: th * 0.5, cor }); c.appendChild(e); cx.appendChild(c); S.medir.push(e); return c; };
        const a = mk('A', 'superficie', 'texto_suave'), bb = mk('B', 'fundo', 'texto');
        const sub2 = ctx.sub({ L: tw, A: th, palco: cx, dur: 1 });
        sub2.transicao(a, bb, 0.5, nome);
        b.appendChild(cx);
        const r = rotulo(nome, { tam: t(0.0088), cor: nome === tr.padrao ? 'texto' : 'texto_suave' }); b.appendChild(r); S.medir.push(r);
        tira.appendChild(b);
      }
      mov.appendChild(tira);
    }
    if (DA.movimento.principios.length) {
      const ul = css(ctx.el('div'), { display: 'flex', flexDirection: 'column', gap: '6px' });
      for (const x of DA.movimento.principios) { const e = corpo('— ' + x, { cor: 'texto_suave', tam: t(0.0098), maxW: metade }); ul.appendChild(e); S.medir.push(e); }
      mov.appendChild(ul);
    }
  }

  // ═══════════════════════════════════════════ 7. vertical: margens seguras (só na prancha vertical) ══
  if (vertical) {
    const sec = secao('Margens seguras no vertical', 'hachurado = coberto pela interface do app; a "união" (pior caso dos três) é a zona padrão das peças');
    const fila = css(ctx.el('div'), { display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: GAP + 'px', alignItems: 'start' });
    sec.appendChild(fila);
    const metade = (W - GAP) / 2;
    const tabela = DA.formatos.margens_seguras.vertical;
    const hachura = (cor, passo) => `repeating-linear-gradient(135deg, ${ctx.alfa(cor, 0.5)} 0 ${passo}px, ${ctx.alfa('fundo', 0.35)} ${passo}px ${passo * 2.4}px)`;
    /** Pinta num quadro 1080×1920 o que a interface cobre (hachura) e contorna a área livre. */
    function zonas(frame, m4, passo, traco) {
      const [tp, dr, bs, es] = m4;
      for (const [x, y, w, h] of [[0, 0, 1, tp], [0, 1 - bs, 1, bs], [0, tp, es, 1 - tp - bs], [1 - dr, tp, dr, 1 - tp - bs]]) {
        frame.appendChild(css(ctx.el('div'), { position: 'absolute', left: (x * 1080) + 'px', top: (y * 1920) + 'px', width: (w * 1080) + 'px', height: (h * 1920) + 'px', backgroundImage: hachura(corMarca, passo) }));
      }
      frame.appendChild(css(ctx.el('div'), { position: 'absolute', left: (es * 1080) + 'px', top: (tp * 1920) + 'px', width: ((1 - es - dr) * 1080) + 'px', height: ((1 - tp - bs) * 1920) + 'px', border: `${traco}px dashed ${ctx.cor(corMarca)}`, boxSizing: 'border-box' }));
    }
    const s = metade / 1080;
    const q = quadro(1080, 1920, s, { pai: fila, fundoImg: fundoRef, legenda: juntos ? 'união: área livre tracejada, com o GC e a legenda na posição real (o GC fora da faixa da legenda)'
      : 'união: área livre tracejada, com o GC na posição da produção — "vertical" não está em legenda.reservar_em: GC e legenda ocupam a mesma faixa' });
    zonas(q.frame, tabela.uniao || Object.values(tabela)[0], 14, 4);
    const gz = await ctx.kit.cena('gc', paramsGc, { palco: q.frame, L: 1080, A: 1920, dur: 5, alfa: true });
    gz.seek(2.5);
    if (juntos) porLegenda(q.frame, gz.ctx);
    const dir = css(ctx.el('div'), { display: 'flex', flexDirection: 'column', gap: GAP + 'px' });
    fila.appendChild(dir);
    const nomes = Object.keys(tabela).filter((k) => k !== 'uniao');
    const gapMini = GAP * 0.6;
    const sm = (metade - gapMini * (nomes.length - 1)) / Math.max(1, nomes.length) / 1080;
    const minis = css(ctx.el('div'), { display: 'flex', gap: gapMini + 'px' });
    dir.appendChild(minis);
    for (const plat of nomes) {
      const qm = quadro(1080, 1920, sm, { pai: minis, fundoImg: fundoRef, legenda: plat });
      zonas(qm.frame, tabela[plat], 40, 12);
    }
    const lista = css(ctx.el('div'), { display: 'flex', flexDirection: 'column', gap: (GAP * 0.4) + 'px' });
    const linhaDe = (nome, m4, forte) => {
      const [tp, dr, bs, es] = m4;
      const e = corpo(`${nome}: topo ${ptbr(tp * 100, 1)}% · direita ${ptbr(dr * 100, 1)}% · base ${ptbr(bs * 100, 1)}% · esquerda ${ptbr(es * 100, 1)}% — livre ${Math.round((1 - es - dr) * 1080)} × ${Math.round((1 - tp - bs) * 1920)} px`,
        { cor: forte ? 'texto' : 'texto_suave', tam: t(0.0105), maxW: metade });
      lista.appendChild(e); S.medir.push(e);
    };
    if (tabela.uniao) linhaDe('união (zona padrão)', tabela.uniao, true);
    for (const plat of nomes) linhaDe(plat, tabela[plat], false);
    const lg = DA.legenda;
    const e2 = corpo(`legenda: ${lg.estilo} · papel ${lg.papel} · ${ptbr(lg.tamanho, 3)} do lado menor (${Math.round(lg.tamanho * 1080)} px) · y ${ptbr(lg.posicao.vertical.y, 2)} no vertical, ${ptbr(lg.posicao.horizontal.y, 2)} no horizontal · até ${lg.max_linhas} linha(s) × ${lg.max_palavras} palavras · ${lg.contorno ? 'contorno ' + ptbr(lg.contorno.espessura, 2) + ' em' : 'sem contorno'} · ${lg.fundo ? 'caixa de fundo' : 'sem caixa'} · animação ${lg.animacao} · faixa reservada em: ${(lg.reservar_em || []).join(', ') || 'nenhum formato'}`,
      { cor: 'texto_suave', tam: t(0.0098), maxW: metade });
    lista.appendChild(e2); S.medir.push(e2);
    dir.appendChild(lista);
  }

  // ═══════════════════════════════════════════════ 8. thumbnail + faça / não faça ══
  {
    const th = DA.thumbnail;
    const sec = secao('Thumbnail e regras', `até ${th.max_palavras} palavras em "${th.papel}" a ${ptbr(th.tamanho, 2)} do lado menor · zona proibida: ${th.zona_proibida.replace(/_/g, ' ')}`);
    const fila = css(ctx.el('div'), { display: 'grid', gridTemplateColumns: vertical ? 'minmax(0, 1fr)' : `${Math.round(W * 0.42)}px minmax(0, 1fr)`, gap: GAP + 'px', alignItems: 'start' });
    sec.appendChild(fila);
    const sT = (vertical ? W : W * 0.42) / 1280;
    const q = quadro(1280, 720, sT, { pai: fila, legenda: `thumbnail 1280×720 · ${p.foto ? 'foto do projeto' : 'silhueta no lugar da pessoa recortada'} com contorno · zona proibida hachurada` });
    const f = q.frame;
    f.style.background = th.fundo_css || corFundo;
    if (th.fundo === 'foto' && fundoRef) { const im = document.createElement('img'); im.src = fundoRef; im.alt = ''; im.setAttribute('data-da-livre', 'foto'); css(im, { position: 'absolute', inset: '0', width: '100%', height: '100%', objectFit: 'cover' }); f.appendChild(im); }
    const cp = th.tratamento_foto.contorno_pessoa;
    if (p.foto) {
      // foto do projeto no lugar da pessoa: moldura na cor e espessura de tratamento_foto.contorno_pessoa (o recorte de verdade é de quem monta a thumbnail, direto pelo kit)
      const cx = css(ctx.el('div'), { position: 'absolute', right: '40px', bottom: '0', width: '470px', height: '640px', overflow: 'hidden', boxSizing: 'border-box',
        border: th.tratamento_foto.recorte_pessoa ? `${Math.round(cp.espessura * 720)}px solid ${ctx.cor(cp.cor)}` : 'none', borderBottom: 'none', borderRadius: `${Math.round(ctx.raio * 2)}px ${Math.round(ctx.raio * 2)}px 0 0` });
      const im = document.createElement('img'); im.src = p.foto; im.alt = ''; im.setAttribute('data-da-livre', 'foto');
      css(im, { width: '100%', height: '100%', objectFit: 'cover', display: 'block' });
      cx.appendChild(im); f.appendChild(cx);
    } else {
      // silhueta de pessoa (marcador) com contorno conforme tratamento_foto.contorno_pessoa
      const sv = ctx.svg('svg', { width: 520, height: 620, viewBox: '0 0 520 620', style: 'position:absolute;right:40px;bottom:-20px' });
      sv.appendChild(ctx.svg('path', { d: 'M260 40c-70 0-120 55-120 130s50 140 120 140 120-65 120-140S330 40 260 40zm-110 300C70 350 20 440 20 620h480c0-180-50-270-130-280-30 20-70 30-110 30s-80-10-110-30z',
        fill: ctx.cor('superficie'), stroke: th.tratamento_foto.recorte_pessoa ? ctx.cor(cp.cor) : 'none', 'stroke-width': Math.round(cp.espessura * 720), 'stroke-linejoin': 'round' }));
      f.appendChild(sv);
    }
    // título da thumbnail: frase que fecha sentido em max_palavras, com a última palavra em cor_destaque
    const palavras = fraseDeAmostra(th.max_palavras, tituloExemplo);
    const tt = ctx.el('div');
    ctx.estilo(tt, th.papel, { tam: th.tamanho * 720 });
    css(tt, { position: 'absolute', left: '56px', top: '48px', width: '720px', lineHeight: '0.95', color: ctx.cor(th.cor) });   // caixa: a do papel
    const sx = ctx.fonte(th.papel).escala_x || 1;
    if (sx !== 1) { tt.style.transform = `scaleX(${sx})`; tt.style.transformOrigin = 'left top'; tt.style.width = (720 / sx) + 'px'; }
    // contorno com a semântica única da DA: espessura × tamanho = px PARA FORA da letra (igual à legenda e a texto.py)
    if (th.contorno && th.contorno.espessura > 0) ctx.contorno(tt, th.contorno.cor, Math.max(1, Math.round(th.contorno.espessura * th.tamanho * 720)));
    palavras.forEach((w, i) => { const sp = ctx.el('span', null, w + ' '); if (i === palavras.length - 1) sp.style.color = ctx.cor(th.cor_destaque); tt.appendChild(sp); });
    f.appendChild(tt);
    if (th.zona_proibida_ret) {
      // o mesmo retângulo que as cenas recebem por ctx.zona_proibida() e o Python por d.zona_proibida(): frações do quadro
      const zr = th.zona_proibida_ret;
      const zona = css(ctx.el('div'), { position: 'absolute', left: (zr.x * 1280) + 'px', top: (zr.y * 720) + 'px', width: (zr.w * 1280) + 'px', height: (zr.h * 720) + 'px',
        border: `3px dashed ${ctx.cor('negativo')}`, boxSizing: 'border-box',
        backgroundImage: `repeating-linear-gradient(135deg, ${ctx.alfa('negativo', 0.25)} 0 8px, transparent 8px 20px)` });
      f.appendChild(zona);
    }
    const regras = css(ctx.el('div'), { display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: GAP + 'px' });
    for (const [titulo, lista, cor] of [['Faça', DA.conceito.faca, 'positivo'], ['Não faça', DA.conceito.nao_faca, 'negativo']]) {
      const col = css(ctx.el('div'), { display: 'flex', flexDirection: 'column', gap: (GAP * 0.45) + 'px' });
      col.appendChild(ctx.texto('subtitulo', titulo, { tam: t(0.0125), cor: ctx.contraste(cor, 'fundo') >= 3 ? cor : 'texto' }));
      for (const x of lista) { const e = corpo((cor === 'positivo' ? '✓ ' : '✕ ') + x, { tam: t(0.0105), maxW: vertical ? (W - GAP) / 2 : (W * 0.58 - 2 * GAP) / 2 }); col.appendChild(e); S.medir.push(e); }
      regras.appendChild(col);
    }
    fila.appendChild(regras);
    // som e marca
    const som = DA.som, marca = DA.marca;
    const extra = corpo(`Som: ${som.identidade} Loudness ${ptbr(som.loudness.longo.lufs, 0)} LUFS / ${ptbr(som.loudness.longo.pico_real, 1)} dBTP (longo) · SFX entrada ${som.sfx.entrada}, ênfase ${som.sfx.enfase}, texto ${som.sfx.texto} · música ${som.musica.clima} (${som.musica.bpm[0]}–${som.musica.bpm[1]} bpm). Marca: ${marca.logo ? 'logo ' + marca.logo : 'sem logo'}${marca.assinatura ? ' · assinatura ' + marca.assinatura : ''} · ${marca.posicao_logo.replace(/_/g, ' ')}${marca.marca_dagua ? " · marca d'água" : ''}.`,
      { cor: 'texto_suave', tam: t(0.0098), maxW: W });
    sec.appendChild(extra); S.medir.push(extra);
  }

  // ═══════════════════════════════════════════════════════════════ rodapé ══
  {
    const rod = css(ctx.el('footer'), { display: 'flex', justifyContent: 'space-between', gap: GAP + 'px', paddingTop: GAP + 'px', borderTop: hair });
    const a = nota(`gerada pelo kit de direção de arte ${DA._meta.kit_versao} · da.py prancha${p.data ? ' · ' + p.data : ''}`, W * 0.55);
    const b = nota(`${DA._meta.slug} · sha256 ${DA._meta.sha256.slice(0, 12)}…`, W * 0.4);
    b._inner.style.textAlign = 'right';
    rod.append(a, b); pagina.appendChild(rod); S.medir.push(a, b);
  }

  for (const e of S.medir) ctx.medir(e);
  for (const [e, w] of S.ajustar || []) { ctx.ajustar_texto(e, w, { maxLinhas: 3, min: t(0.012) }); ctx.sem_orfa(e); }
  S.pagina = pagina;
  // mapa das seções (px da própria prancha): `da.py rotas comparar` alinha as pranchas por ele, e quem recorta também
  const mapa = S.mapa.map((m, i) => ({ n: m.n, titulo: m.titulo, y: m.el.offsetTop, h: m.el.offsetHeight }));
  return { altura: pagina.offsetHeight, largura: ctx.L, secoes: S.n, mapa, faixa_1x1: S.faixa1x1 ? { y: S.mapa.find((m) => m.titulo === 'Em escala 1:1').el.offsetTop, ...S.faixa1x1 } : null,
    legenda: p.legenda ? 'texto.py' : 'motor' };
}

export function seek() { /* página estática */ }
export function key() { return 'estatico'; }
