// runtime.js — helpers do palco. Roda DENTRO do Chromium (módulo ES carregado pelo palco.html).
// As cenas recebem tudo pelo `ctx` (criarCtx) e não precisam importar nada: ficam portáteis.
// Regra de ouro: todo estado visual é função PURA de t (nada de requestAnimationFrame, transition ou animation).
/* da-livre-arquivo: este arquivo não é peça; as únicas cores aqui são as da DA, lidas em tempo de execução. */

// Peças compartilhadas do kit (D17): as cenas — embutidas e externas — as recebem por ctx.kit, sem importar nada.
import { criarLegenda } from './cenas/_legenda.js';
import { criarTarja } from './cenas/_tarja.js';
import { criarCredito } from './cenas/_credito.js';
import { criarMoldura } from './cenas/_moldura.js';

/** Nomes canônicos de plataforma (youtube, shorts, reels, tiktok) e apelidos → chave usada em formatos.margens_seguras. */
export const ZONA_DA_PLATAFORMA = { reels: 'instagram', instagram_reels: 'instagram', reel: 'instagram', ig: 'instagram', insta: 'instagram',
  youtube_shorts: 'shorts', short: 'shorts', tt: 'tiktok', 'tik-tok': 'tiktok', youtube: 'padrao', youtube_longo: 'padrao', yt: 'padrao' };
export const TRANSICOES = ['corte', 'fade', 'empurra', 'mascara', 'desliza', 'zoom'];
/** Menor texto de apoio legível, em fração do lado menor (24 px em 1080; 8,6 pt num celular) — o mesmo da.MINIMO_LEGIVEL do validador. */
export const MINIMO_LEGIVEL = 0.022;

export const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
export const lerp = (a, b, p) => a + (b - a) * p;
export const mapa = (x, a, b, c, d) => c + (d - c) * clamp((x - a) / (b - a || 1e-9));

/** cubic-bezier(x1, y1, x2, y2) como função pura p(x) → progresso. y pode passar de 0–1 (overshoot). */
export function bezier(x1, y1, x2, y2) {
  const eixo = (t, a, b) => 3 * a * t * (1 - t) ** 2 + 3 * b * t * t * (1 - t) + t ** 3;
  const amostras = new Float64Array(33);
  for (let i = 0; i <= 32; i++) amostras[i] = eixo(i / 32, x1, x2);
  return function (x) {
    if (x <= 0) return 0;
    if (x >= 1) return 1;
    let i = 1;
    while (i < 32 && amostras[i] < x) i++;
    let lo = (i - 1) / 32, hi = i / 32;
    for (let k = 0; k < 24; k++) {                       // bisseção: x(t) é monótona com x1, x2 em [0, 1]
      const meio = (lo + hi) / 2;
      if (eixo(meio, x1, x2) < x) lo = meio; else hi = meio;
    }
    return eixo((lo + hi) / 2, y1, y2);
  };
}

/** Gerador determinístico (mulberry32): rng(seed)() → [0, 1). */
export function mulberry32(a) {
  a |= 0;
  return function () {
    a = a + 0x6D2B79F5 | 0;
    let t = Math.imul(a ^ a >>> 15, 1 | a);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  };
}

export const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const SVG_NS = 'http://www.w3.org/2000/svg';

export function el(tag, classe, texto) {
  const e = document.createElement(tag);
  if (classe) e.className = classe;
  if (texto != null) e.textContent = texto;
  return e;
}

export function svg(tag, atributos = {}, filhos = []) {
  const e = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(atributos)) if (v != null) e.setAttribute(k, String(v));
  for (const f of filhos) if (f) e.appendChild(f);
  return e;
}

function _lum(hex) {
  const c = hexParaRgb(hex).map((v) => v / 255).map((v) => (v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
}
/** Razão de contraste WCAG (1–21) entre dois hex. */
export function contraste(a, b) {
  const la = _lum(a), lb = _lum(b);
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
}

export function hexParaRgb(h) {
  h = String(h).trim().replace('#', '');
  if (h.length === 3) h = h.split('').map((c) => c + c).join('');
  const n = parseInt(h.slice(0, 6), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

export function place(e, { x, y, w, h, direita, base } = {}) {
  e.style.position = 'absolute';
  if (x != null) e.style.left = x + 'px';
  if (y != null) e.style.top = y + 'px';
  if (direita != null) e.style.right = direita + 'px';
  if (base != null) e.style.bottom = base + 'px';
  if (w != null) e.style.width = w + 'px';
  if (h != null) e.style.height = h + 'px';
  return e;
}

export function rectDe(e) {
  const r = e.getBoundingClientRect();
  return { x: r.left, y: r.top, w: r.width, h: r.height, x1: r.right, y1: r.bottom };
}

// ──────────────────────────────────────────────────────────────── timeline ──
/** Sequenciador simples: nomes → janelas [t0, t0+dur]; progresso por curva da DA; âncoras para SFX. */
export class Timeline {
  constructor(ctx) { this.ctx = ctx; this.itens = new Map(); this.fim = 0; }
  add(nome, t0, dur, { curva = 'entrada', tipo = 'entrada' } = {}) {
    this.itens.set(nome, { t0, dur, curva, tipo });
    this.fim = Math.max(this.fim, t0 + dur);
    return this;
  }
  /** Vários nomes, escalonados pelo movimento.escalonamento da DA (ou `passo`). */
  escalonar(nomes, t0, dur, { passo = this.ctx.DA.movimento.escalonamento, curva = 'entrada', tipo = 'entrada' } = {}) {
    nomes.forEach((n, i) => this.add(n, t0 + i * passo, dur, { curva, tipo }));
    return this;
  }
  t0(nome) { return this.itens.get(nome)?.t0 ?? 0; }
  t1(nome) { const i = this.itens.get(nome); return i ? i.t0 + i.dur : 0; }
  /** Progresso 0–1 (já com a curva) do item em t. */
  p(t, nome, curva) {
    const i = this.itens.get(nome);
    if (!i) throw new Error(`timeline: item ${JSON.stringify(nome)} não existe`);
    return this.ctx.prog(t, i.t0, i.dur, curva || i.curva);
  }
  lin(t, nome) { const i = this.itens.get(nome); return clamp((t - i.t0) / i.dur); }
  ancoras() {
    return [...this.itens.entries()].map(([nome, i]) => ({ t: +i.t0.toFixed(3), nome, tipo: i.tipo })).sort((a, b) => a.t - b.t);
  }
}

// ───────────────────────────────────────────────────────── entradas e saídas ──
const DIST = 0.045;                                      // deslocamento padrão das entradas (fração do lado menor)

function aplicarEstado(e, { opacidade = 1, transform = '', clip = null, extra = null }) {
  e.style.opacity = opacidade.toFixed(3);
  e.style.transform = transform || 'none';
  e.style.clipPath = clip || 'none';
  if (extra) for (const [k, v] of Object.entries(extra)) e.style[k] = v;
}

/**
 * Estado de ENTRADA de um elemento para o progresso p (0 = invisível, 1 = em repouso).
 * tipos: sobe | desliza | mascara | escala | fade | digita (por caracteres, com clip quantizado).
 */
export function estadoEntrada(ctx, e, p, tipo, { dist = ctx.px(DIST), origem = 'esquerda', n = null } = {}) {
  p = clamp(p, 0, 2);                                    // curvas de ênfase podem passar de 1 (overshoot)
  const q = clamp(p);
  switch (tipo) {
    case 'sobe': return aplicarEstado(e, { opacidade: q, transform: `translateY(${(dist * (1 - p)).toFixed(2)}px)` });
    case 'desce': return aplicarEstado(e, { opacidade: q, transform: `translateY(${(-dist * (1 - p)).toFixed(2)}px)` });
    case 'desliza': {
      const s = origem === 'direita' ? 1 : -1;
      return aplicarEstado(e, { opacidade: q, transform: `translateX(${(s * dist * (1 - p)).toFixed(2)}px)` });
    }
    case 'mascara': {
      const resto = ((1 - q) * 100).toFixed(2) + '%';
      const clip = origem === 'cima' ? `inset(0 0 ${resto} 0)` : origem === 'direita' ? `inset(0 0 0 ${resto})` : `inset(0 ${resto} 0 0)`;
      return aplicarEstado(e, { opacidade: q > 0 ? 1 : 0, transform: '', clip });
    }
    case 'escala': return aplicarEstado(e, { opacidade: q, transform: `scale(${(0.9 + 0.1 * p).toFixed(4)})` });
    case 'digita': {
      // Caractere a caractere, LINHA A LINHA, com o corte na fronteira de cada glifo (medida no próprio texto): em fonte
      // proporcional nenhuma letra aparece pela metade e a 2ª linha só começa quando a 1ª terminou. O texto não é
      // reescrito (nada de um span por letra, que mudaria kerning e quebra de linha): só o clip-path muda com p.
      const mapa = mapaDeCaracteres(e);
      if (!mapa) {                                         // sem medida (elemento fora do fluxo agora): corte proporcional
        const total = n ?? (e.textContent || '').length ?? 1;
        const frac = total ? Math.floor(q * total + 1e-6) / total : q;
        return aplicarEstado(e, { opacidade: q > 0 ? 1 : 0, transform: '', clip: `inset(0 ${((1 - frac) * 100).toFixed(3)}% 0 0)` });
      }
      const vistos = Math.floor(q * mapa.total + 1e-6);
      if (vistos <= 0) return aplicarEstado(e, { opacidade: 0, transform: '', clip: 'inset(0 100% 0 0)' });
      if (vistos >= mapa.total) return aplicarEstado(e, { opacidade: 1, transform: '' });
      const c = mapa.chars[vistos - 1], ln = mapa.linhas[c.linha];
      const W = (mapa.w + 4).toFixed(2), x = c.x1.toFixed(2), y0 = ln.y0.toFixed(2), y1 = ln.y1.toFixed(2);
      const clip = c.linha === 0
        ? `polygon(-4px -4px, ${x}px -4px, ${x}px ${y1}px, -4px ${y1}px)`
        : `polygon(-4px -4px, ${W}px -4px, ${W}px ${y0}px, ${x}px ${y0}px, ${x}px ${y1}px, -4px ${y1}px)`;
      return aplicarEstado(e, { opacidade: 1, transform: '', clip });
    }
    case 'fade':
    default: return aplicarEstado(e, { opacidade: q, transform: '' });
  }
}

/**
 * Mapa dos caracteres de um elemento de texto para a entrada 'digita': posição de cada caractere (borda direita, em px
 * LOCAIS do elemento) e as linhas (topo e base). Medido uma vez e guardado; refeito se o texto ou a caixa mudarem.
 * Devolve null quando o elemento não tem caixa agora (display: none num ancestral) — quem chama usa o corte proporcional.
 */
const MAPAS_DIGITA = new WeakMap();
function mapaDeCaracteres(e) {
  const txt = e.textContent || '';
  const assinatura = `${txt}|${e.offsetWidth}|${e.offsetHeight}`;
  const guardado = MAPAS_DIGITA.get(e);
  if (guardado && guardado.assinatura === assinatura) return guardado;
  const caixa = e.getBoundingClientRect();
  if (!(caixa.width > 0 && caixa.height > 0) || !e.offsetWidth || !e.offsetHeight) return null;
  const kx = caixa.width / e.offsetWidth, ky = caixa.height / e.offsetHeight;      // transform de ancestrais (prancha, transição)
  const rg = document.createRange();
  const walker = document.createTreeWalker(e, NodeFilter.SHOW_TEXT);
  const chars = [], linhas = [];
  let no;
  while ((no = walker.nextNode())) {
    const s = no.nodeValue;
    for (let i = 0; i < s.length; i++) {
      rg.setStart(no, i); rg.setEnd(no, i + 1);
      const r = rg.getBoundingClientRect();
      if (!(r.height > 0)) continue;                         // espaço colapsado na quebra de linha: não ocupa lugar
      const y0 = (r.top - caixa.top) / ky, y1 = (r.bottom - caixa.top) / ky, x1 = (r.right - caixa.left) / kx;
      let li = linhas.findIndex((l) => Math.abs((l.y0 + l.y1) / 2 - (y0 + y1) / 2) < (y1 - y0) * 0.5);
      if (li < 0) { linhas.push({ y0, y1 }); li = linhas.length - 1; } else { linhas[li].y0 = Math.min(linhas[li].y0, y0); linhas[li].y1 = Math.max(linhas[li].y1, y1); }
      chars.push({ linha: li, x1 });
    }
  }
  if (!chars.length) return null;
  // fronteira entre linhas no meio do vão (ou da sobreposição): o corte de uma linha nunca mostra a de baixo
  for (let i = 0; i < linhas.length - 1; i++) { const m = (linhas[i].y1 + linhas[i + 1].y0) / 2; linhas[i].y1 = m; linhas[i + 1].y0 = m; }
  linhas[0].y0 = -4; linhas[linhas.length - 1].y1 = e.offsetHeight + 4;
  for (let i = 1; i < chars.length; i++) if (chars[i].linha === chars[i - 1].linha) chars[i].x1 = Math.max(chars[i].x1, chars[i - 1].x1);
  const mapa = { assinatura, total: chars.length, chars, linhas, w: e.offsetWidth };
  MAPAS_DIGITA.set(e, mapa);
  return mapa;
}

/** Estado de SAÍDA para o progresso p (0 = em repouso, 1 = sumiu). tipos: fade | desce | sobe | mascara | corte. */
export function estadoSaida(ctx, e, p, tipo, { dist = ctx.px(DIST), origem = 'esquerda' } = {}) {
  const q = clamp(p);
  switch (tipo) {
    case 'desce': return aplicarEstado(e, { opacidade: 1 - q, transform: `translateY(${(dist * q).toFixed(2)}px)` });
    case 'sobe': return aplicarEstado(e, { opacidade: 1 - q, transform: `translateY(${(-dist * q).toFixed(2)}px)` });
    case 'mascara': {
      const resto = (q * 100).toFixed(2) + '%';
      const clip = origem === 'direita' ? `inset(0 ${resto} 0 0)` : `inset(0 0 0 ${resto})`;
      return aplicarEstado(e, { opacidade: q < 1 ? 1 : 0, transform: '', clip });
    }
    case 'corte': return aplicarEstado(e, { opacidade: q >= 1 ? 0 : 1, transform: '' });
    case 'fade':
    default: return aplicarEstado(e, { opacidade: 1 - q, transform: '' });
  }
}

// ─────────────────────────────────────────────────────────────────── grão ──
/** Camada de grão determinística: poucos ladrilhos de ruído (seed fixa) reutilizados; data-da-livre. */
export const GRAOS = new WeakSet();                      // camadas de grão criadas AQUI: o auditor as reconhece sem listá-las como livres

export function criarGrao(ctx, { quadros = 6, lado = 320, intensidade = null, fps = 24 } = {}) {
  const g = ctx.DA.tratamento.grao;
  const forca = intensidade ?? g.intensidade;
  const camada = el('div', 'da-grao');
  GRAOS.add(camada);
  camada.setAttribute('data-da-livre', 'grão gerado pelo kit');
  camada.setAttribute('aria-hidden', 'true');
  Object.assign(camada.style, { position: 'absolute', inset: '0', pointerEvents: 'none', mixBlendMode: 'overlay',
    opacity: clamp(forca / 40, 0, 0.6).toFixed(3), backgroundRepeat: 'repeat', backgroundSize: `${lado}px ${lado}px`, zIndex: 9000 });
  const ladrilhos = [];
  for (let k = 0; k < quadros; k++) {
    const c = document.createElement('canvas');
    c.width = lado; c.height = lado;
    const cx = c.getContext('2d');
    const id = cx.createImageData(lado, lado);
    const d = id.data;
    const rnd = mulberry32(7919 + k * 104729);
    for (let i = 0; i < d.length; i += 4) {
      const v = 96 + ((rnd() + rnd()) * 64) | 0;         // ruído centrado em cinza médio (overlay neutro)
      d[i] = v; d[i + 1] = v; d[i + 2] = v; d[i + 3] = 255;
    }
    cx.putImageData(id, 0, 0);
    ladrilhos.push(`url(${c.toDataURL('image/png')})`);
  }
  camada.style.backgroundImage = ladrilhos[0];
  return {
    elemento: camada,
    quadros,
    indice: (t) => Math.floor(t * fps) % quadros,
    seek(t) {
      const i = Math.floor(t * fps) % quadros;
      camada.style.backgroundImage = ladrilhos[i];
      camada.style.backgroundPosition = `${(i * 37) % lado}px ${(i * 53) % lado}px`;
      return i;
    },
  };
}

// ────────────────────────────────────────────────────────────────── texto ──
function medirLinhas(inner) {
  const rg = document.createRange();
  rg.selectNodeContents(inner);
  const rects = [...rg.getClientRects()].filter((r) => r.width > 0 && r.height > 0);
  if (!rects.length) return { linhas: 0, direita: 0, esquerda: 0 };
  const tops = [];
  for (const r of rects) if (!tops.some((y) => Math.abs(y - r.top) < r.height * 0.5)) tops.push(r.top);
  return { linhas: tops.length, direita: Math.max(...rects.map((r) => r.right)), esquerda: Math.min(...rects.map((r) => r.left)) };
}

function palavrasUltimaLinha(inner) {
  const rg = document.createRange();
  const walker = document.createTreeWalker(inner, NodeFilter.SHOW_TEXT);
  const tops = [];
  let n;
  while ((n = walker.nextNode())) {
    const re = /\S+/g;
    let m;
    while ((m = re.exec(n.nodeValue))) {
      rg.setStart(n, m.index); rg.setEnd(n, m.index + m[0].length);
      const r = rg.getBoundingClientRect();
      if (r.width > 0) tops.push(r.top);
    }
  }
  if (tops.length < 2) return { total: tops.length, ultima: tops.length };
  const ultimo = tops[tops.length - 1];
  const alturaRef = Math.max(1, (Math.max(...tops) - Math.min(...tops)) / Math.max(1, new Set(tops.map((y) => Math.round(y))).size - 1));
  return { total: tops.length, ultima: tops.filter((y) => Math.abs(y - ultimo) < alturaRef * 0.5).length };
}

// ─────────────────────────────────────────────────────────────────── ctx ──
/**
 * criarCtx({DA, palco, formato: {nome, L, A, fps}, dur}) → o `ctx` que as cenas recebem.
 * Tudo em px já é absoluto para o quadro L×A; frações são do lado menor (u).
 */
export function criarCtx({ DA, palco, formato, dur, alfa = false }) {
  const L = formato.L, A = formato.A, u = Math.min(L, A);
  const cor = DA.cor;
  const permitidas = new Set((cor.permitidas || []).map((h) => h.toUpperCase()));
  const curvasCache = new Map();
  const nomeFormato = formato.nome;
  const orientacao = L > A ? 'horizontal' : L < A ? 'vertical' : 'quadrado';

  function corToken(nome) {
    if (nome == null) throw new Error('ctx.cor: faltou o nome do token');
    const s = String(nome).trim();
    if (s.startsWith('#')) {
      const h = s.length === 4 ? '#' + s.slice(1).split('').map((c) => c + c).join('') : s;
      if (!permitidas.has(h.toUpperCase())) throw new Error(`ctx.cor: ${s} não é uma cor da DA (use um token: ${Object.keys(cor.paleta).join(', ')}, dado-N, neutro-N)`);
      return h.toUpperCase();
    }
    if (s in cor.paleta) return cor.paleta[s];
    const m = /^(dado|neutro)-(\d+)$/.exec(s);
    if (m) {
      const lista = m[1] === 'dado' ? cor.dados : cor.neutros;
      const i = parseInt(m[2], 10);
      if (i >= 1 && i <= lista.length) return lista[i - 1];
      throw new Error(`ctx.cor: ${s} não existe (há ${lista.length} em cor.${m[1] === 'dado' ? 'dados' : 'neutros'})`);
    }
    throw new Error(`ctx.cor: token ${JSON.stringify(nome)} não existe na DA (${Object.keys(cor.paleta).join(', ')}, dado-N, neutro-N)`);
  }

  const ctx = {
    // `dur(nome)` é a função das durações da DA; a duração total da peça fica em `duracao` (e `DUR`)
    DA, palco, L, A, u, fps: formato.fps, duracao: dur, DUR: dur, formato: nomeFormato, orientacao, transparente: alfa,
    clamp, lerp, mapa, el, svg, place, rectDe, esc, bezier, mulberry32,
    px: (f) => f * u,
    /** Menor tamanho (px deste quadro) a que um texto de apoio pode encolher para caber: MINIMO_LEGIVEL × lado menor. */
    minimo_legivel: MINIMO_LEGIVEL * u,
    cor: corToken,
    rgb: (nome) => hexParaRgb(corToken(nome)),
    alfa: (nome, a) => { const [r, g, b] = hexParaRgb(corToken(nome)); return `rgba(${r}, ${g}, ${b}, ${clamp(a).toFixed(3)})`; },
    dado: (i) => corToken(`dado-${((i % cor.dados.length) + cor.dados.length) % cor.dados.length + 1}`),
    contraste: (a, b) => contraste(corToken(a), corToken(b)),
    /** Entre dois tokens de texto, o que lê melhor sobre `fundo`. */
    legivel: (fundo, a = 'texto', b = 'fundo') => (contraste(corToken(a), corToken(fundo)) >= contraste(corToken(b), corToken(fundo)) ? a : b),
    fonte(papel) {
      const p = DA.tipografia.papeis[papel];
      if (!p) throw new Error(`ctx.fonte: papel ${JSON.stringify(papel)} não existe (${Object.keys(DA.tipografia.papeis).join(', ')})`);
      return p;
    },
    tam(nome) {
      const f = DA.tipografia.escala[nome];
      if (f == null) throw new Error(`ctx.tam: escala ${JSON.stringify(nome)} não existe (${Object.keys(DA.tipografia.escala).join(', ')})`);
      return f * u;
    },
    ease(nome) {
      if (!curvasCache.has(nome)) {
        const c = DA.movimento.curvas[nome];
        if (!c) throw new Error(`ctx.ease: curva ${JSON.stringify(nome)} não existe (${Object.keys(DA.movimento.curvas).join(', ')})`);
        curvasCache.set(nome, bezier(...c));
      }
      return curvasCache.get(nome);
    },
    prog(t, t0, d, curva = 'entrada') { return ctx.ease(curva)(clamp((t - t0) / (d || 1e-9))); },
    lin: (t, t0, d) => clamp((t - t0) / (d || 1e-9)),
    dur(nome) {
      const d = DA.movimento.duracoes[nome];
      if (d == null) throw new Error(`ctx.dur: duração ${JSON.stringify(nome)} não existe (${Object.keys(DA.movimento.duracoes).join(', ')})`);
      return d;
    },
    escalonamento: DA.movimento.escalonamento,
    /**
     * Margens seguras em px. `plataforma`: chave de formatos.margens_seguras deste formato (vertical: instagram, tiktok,
     * shorts, uniao; horizontal: padrao) ou nome canônico/apelido (reels = instagram; youtube = padrao). Zona que existe
     * em OUTRO formato (ex.: 'uniao' pedida num quadro horizontal) cai no padrão deste formato — o mesmo storyboard
     * serve aos dois; nome que não existe em lugar nenhum é erro. O resultado diz a zona usada em `.plataforma`.
     */
    margens(plataforma) {
      const tabela = DA.formatos.margens_seguras;
      const bloco = tabela[nomeFormato] || tabela[orientacao] || tabela.horizontal;
      const padrao = 'uniao' in bloco ? 'uniao' : 'padrao' in bloco ? 'padrao' : Object.keys(bloco)[0];
      const pedida = plataforma || null;
      if (!plataforma) plataforma = padrao;
      else if (!(plataforma in bloco)) {
        const chave = ZONA_DA_PLATAFORMA[String(plataforma).toLowerCase()] || String(plataforma).toLowerCase();
        const conhecida = String(plataforma).toLowerCase() in ZONA_DA_PLATAFORMA || Object.values(tabela).some((b) => b && typeof b === 'object' && (plataforma in b || chave in b));
        if (chave in bloco) plataforma = chave;
        else if (conhecida) plataforma = padrao;
        else throw new Error(`ctx.margens: plataforma ${JSON.stringify(plataforma)} não existe (zonas deste formato: ${Object.keys(bloco).join(', ')}; também valem reels, youtube e as zonas dos outros formatos)`);
      }
      const m = bloco[plataforma];
      // teto com folga de 0,1 px, igual a d.margens() em Python (0,2778 × 1080 = 300,02 → 300)
      const teto = (v) => Math.ceil(v - 0.1);
      return { topo: teto(m[0] * A), direita: teto(m[1] * L), base: teto(m[2] * A), esquerda: teto(m[3] * L), plataforma, pedida };
    },
    plataformas() {
      const tabela = DA.formatos.margens_seguras;
      return Object.keys(tabela[nomeFormato] || tabela[orientacao] || tabela.horizontal);
    },
    area_segura(plataforma) {
      const m = ctx.margens(plataforma);
      return { x: m.esquerda, y: m.topo, w: L - m.esquerda - m.direita, h: A - m.topo - m.base, x1: L - m.direita, y1: A - m.base, plataforma: m.plataforma };
    },
    /**
     * Faixa (px) que a legenda da DA pode ocupar neste quadro no PIOR caso — legenda.max_linhas linhas (1 no estilo
     * `palavra`) no tamanho pedido, na largura máxima, com contorno ou caixa e a sombra para baixo — dentro da zona
     * segura da plataforma: { x0, y0, x1, y1, linhas, tamanho, formato }. Mesma conta de d.faixa_legenda() em Python.
     */
    faixa_legenda(plataforma) {
      const leg = DA.legenda, zona = ctx.area_segura(plataforma);
      const pos = leg.posicao[orientacao] || leg.posicao.horizontal;
      const papel = DA.tipografia.papeis[leg.papel] || {};
      const tam = leg.tamanho * u;
      const linhas = leg.estilo === 'palavra' ? 1 : leg.max_linhas;
      const esp = leg.contorno && leg.contorno.espessura > 0 ? Math.max(1, Math.round(leg.contorno.espessura * tam)) : 0;
      const resp = leg.fundo ? (leg.fundo.respiro || [0.35, 0.18]) : [0, 0];
      const bordaY = Math.max(esp, resp[1] * tam);
      const larg = Math.min((pos.largura_max ?? leg.largura_max) * L, zona.w);
      const h = linhas * tam * (papel.altura_linha || 1.1) + 2 * bordaY;
      let cx = pos.x != null ? pos.x * L : (zona.x + zona.x1) / 2, cy = pos.y * A;
      cx = Math.min(Math.max(cx, zona.x + larg / 2), zona.x1 - larg / 2);
      cy = h > zona.h ? (zona.y + zona.y1) / 2 : Math.min(Math.max(cy, zona.y + h / 2), zona.y1 - h / 2);
      const s = leg.sombra;
      const sombra = s ? Math.max(0, ((s.dy || 0) + (s.desfoque || 0) / 2) * tam) : 0;
      const r2 = (v) => +v.toFixed(2);
      return { x0: r2(cx - larg / 2), y0: r2(cy - h / 2), x1: r2(cx + larg / 2), y1: r2(cy + h / 2 + sombra), linhas, tamanho: r2(tam), formato: orientacao };
    },
    /**
     * Zona segura MENOS a faixa da legenda (D18): a área onde GC, título, gráfico, crédito e assinatura ficam sem
     * encostar na legenda queimada. `legenda`: true = reserva sempre; false = nunca; null (padrão) = conforme
     * legenda.reservar_em da DA (padrão: vertical e quadrado; thumbnail nunca). Fica com o lado maior (acima ou abaixo
     * da faixa). Devolve o mesmo formato de area_segura() + { reservou, faixa_legenda, lado }. Em Python: d.area_livre().
     */
    area_livre(plataforma, { legenda = null } = {}) {
      const z = ctx.area_segura(plataforma);
      const base = { ...z, reservou: false, faixa_legenda: null, lado: null };
      const reservar = legenda != null ? !!legenda : (nomeFormato !== 'thumbnail' && (DA.legenda.reservar_em || ['vertical', 'quadrado']).includes(orientacao));
      if (!reservar) return base;
      const f = ctx.faixa_legenda(plataforma);
      const folga = 0.012 * u;
      const acima = f.y0 - folga - z.y, abaixo = z.y1 - (f.y1 + folga);
      if (Math.max(acima, abaixo) <= 0) return { ...base, faixa_legenda: f, sem_espaco: true };
      let y0 = z.y, y1 = z.y1;
      if (acima >= abaixo) y1 = Math.floor(f.y0 - folga + 1e-6); else y0 = Math.ceil(f.y1 + folga - 1e-6);
      return { ...z, y: y0, y1, h: y1 - y0, reservou: true, faixa_legenda: f, lado: acima >= abaixo ? 'acima' : 'abaixo' };
    },
    grade() {
      const g = DA.layout.grade;
      const margem = g.margem * u, calha = g.calha * u;
      const larguraCol = (L - 2 * margem - (g.colunas - 1) * calha) / g.colunas;
      return { colunas: g.colunas, margem, calha, larguraCol, x: (i) => margem + i * (larguraCol + calha) };
    },
    col(n) { const g = ctx.grade(); return n * g.larguraCol + (n - 1) * g.calha; },
    margem: DA.layout.grade.margem * u,
    calha: DA.layout.grade.calha * u,
    raio: DA.layout.raio * u,
    traco: Math.max(1, DA.layout.traco * u),
    rng: mulberry32,
    tl: () => new Timeline(ctx),

    /** Aplica o papel tipográfico (classe .da-<papel>) + tamanho + cor a um elemento. */
    estilo(e, papel, { tam = null, cor: c = null } = {}) {
      ctx.fonte(papel);
      e.classList.add('da-' + papel.replace(/_/g, '-'));
      if (tam != null) e.style.fontSize = tam.toFixed(2) + 'px';
      if (c) e.style.color = corToken(c);
      return e;
    },

    /**
     * Bloco de texto fiel ao papel (inclui escala_x por transform, como no motor da casa).
     * Devolve um wrapper dimensionado pela medida VISUAL; use ctx.medir(w) depois de mexer no DOM.
     */
    texto(papel, str, { tam = null, cor: c = null, maxW = 0, wrap = false, alinhar = 'esquerda', classe = '', html = null } = {}) {
      const p = ctx.fonte(papel);
      const sx = p.escala_x || 1;
      const w = el('div', 'da-texto' + (classe ? ' ' + classe : ''));
      w.style.position = 'relative';
      w.style.boxSizing = 'content-box';                      // medir() fixa a largura do CONTEÚDO; padding soma por fora
      const inner = el('div', 'da-texto-inner');
      ctx.estilo(inner, papel, { tam: tam ?? ctx.tam('corpo'), cor: c || 'texto' });
      if (html != null) inner.innerHTML = html; else inner.textContent = str;
      inner.style.display = wrap ? 'block' : 'inline-block';
      inner.style.whiteSpace = wrap ? 'normal' : 'nowrap';
      inner.style.textAlign = alinhar === 'centro' ? 'center' : alinhar === 'direita' ? 'right' : 'left';
      if (wrap) inner.style.textWrapStyle = 'pretty';           // nunca `text-wrap` (atalho que anula o nowrap)
      inner.style.transformOrigin = 'left top';
      if (sx !== 1) inner.style.transform = `scaleX(${sx})`;
      if (wrap && maxW) inner.style.width = (maxW / sx).toFixed(2) + 'px';
      w.appendChild(inner);
      w._inner = inner; w._sx = sx; w._papel = papel; w._maxW = maxW; w._wrap = wrap; w._alinhar = alinhar;
      w._tam = parseFloat(inner.style.fontSize);
      return w;
    },

    /** Mede um wrapper de ctx.texto (ou um elemento comum) e fixa a caixa visual. */
    medir(w) {
      if (!w._inner) { const r = w.getBoundingClientRect(); return { w: r.width, h: r.height, linhas: 1 }; }
      const inner = w._inner;
      const sx = w._sx;
      const r = inner.getBoundingClientRect();
      const larguraLayout = inner.offsetWidth, alturaLayout = inner.offsetHeight;
      let vw = larguraLayout * sx;
      let linhas = 1;
      if (w._wrap) {
        const m = medirLinhas(inner);
        linhas = m.linhas || 1;
        if (r.width > 0 && w._alinhar === 'esquerda') {
          const escalaReal = (larguraLayout * sx) / r.width;         // compensa transform de ancestrais
          vw = (m.direita - r.left) * escalaReal;                     // linha mais larga, não a caixa toda
        }
      }
      const vh = alturaLayout;
      w.style.width = Math.ceil(vw) + 'px';
      w.style.height = Math.ceil(vh) + 'px';
      return { w: Math.ceil(vw), h: Math.ceil(vh), linhas };
    },

    /** Encolhe a fonte até caber em larguraMax (e alturaMax); devolve a medida final. */
    ajustar_texto(w, larguraMax, { min = 12, alturaMax = Infinity, passo = 0.94, maxLinhas = Infinity } = {}) {
      const inner = w._inner || w;
      let tam = parseFloat(getComputedStyle(inner).fontSize);
      let m;
      for (let k = 0; k < 40; k++) {
        if (w._inner && w._wrap && w._maxW) inner.style.width = (Math.min(w._maxW, larguraMax) / w._sx).toFixed(2) + 'px';
        m = ctx.medir(w);
        const cabe = m.w <= larguraMax + 0.5 && m.h <= alturaMax + 0.5 && m.linhas <= maxLinhas;
        if (cabe || tam * passo < min) break;
        tam = Math.max(min, tam * passo);
        inner.style.fontSize = tam.toFixed(2) + 'px';
        if (w._inner) w._tam = tam;
      }
      return m;
    },

    /** Evita palavra órfã na última linha: junta as duas últimas palavras com espaço inquebrável, senão encolhe um pouco. */
    sem_orfa(w, { min = 12 } = {}) {
      const inner = w._inner || w;
      if (!(w._wrap ?? true)) return ctx.medir(w);
      for (let k = 0; k < 6; k++) {
        const m = ctx.medir(w);
        const pal = palavrasUltimaLinha(inner);
        if (m.linhas < 2 || pal.ultima !== 1 || pal.total < 3) return m;
        const txt = inner.textContent;
        const NBSP = String.fromCharCode(160);
        const i = txt.lastIndexOf(' ');
        if (k === 0 && i > 0 && inner.children.length === 0 && !txt.includes(NBSP, i)) {
          inner.textContent = txt.slice(0, i) + NBSP + txt.slice(i + 1);   // junta as duas últimas palavras
          continue;
        }
        const tam = parseFloat(getComputedStyle(inner).fontSize) * 0.96;
        if (tam < min) return m;
        inner.style.fontSize = tam.toFixed(2) + 'px';
        if (w._inner) w._tam = tam;
      }
      return ctx.medir(w);
    },

    /** Entrada/saída da DA aplicadas a um elemento em função de t. Devolve {p_entrada, p_saida, visivel}. */
    vida(e, t, { de = 0, ate = dur, entrada = {}, saida = {} } = {}) {
      const ent = { tipo: DA.movimento.entrada_padrao, dur: ctx.dur('media'), curva: 'entrada', ...entrada };
      const sai = { tipo: DA.movimento.saida_padrao, dur: ctx.dur('curta'), curva: 'saida', ...saida };
      const tSaida = ate - sai.dur;
      if (t < de) { estadoEntrada(ctx, e, 0, ent.tipo, ent); return { p_entrada: 0, p_saida: 0, visivel: false }; }
      if (ate != null && t >= tSaida && sai.tipo !== 'nenhuma') {
        const ps = ctx.prog(t, tSaida, sai.dur, sai.curva);
        estadoSaida(ctx, e, ps, sai.tipo, sai);
        return { p_entrada: 1, p_saida: ps, visivel: ps < 1 };
      }
      const pe = ctx.prog(t, de, ent.dur, ent.curva);
      estadoEntrada(ctx, e, pe, ent.tipo, ent);
      return { p_entrada: pe, p_saida: 0, visivel: pe > 0 };
    },
    entrada: (e, p, tipo, op) => estadoEntrada(ctx, e, p, tipo || DA.movimento.entrada_padrao, op),
    saida: (e, p, tipo, op) => estadoSaida(ctx, e, p, tipo || DA.movimento.saida_padrao, op),
    grao: (op) => criarGrao(ctx, op),

    /** Janela de saída padrão da peça: começa em dur − duracoes.media. */
    fim_saida() { return dur - ctx.dur('media'); },

    /**
     * Contorno de texto com a semântica da DA (a mesma de texto.py): `px` = espessura EXTERNA visível, para fora da
     * letra, com cantos redondos. Tokens `contorno.espessura` são frações do tamanho da fonte:
     * ctx.contorno(el, c.cor, c.espessura * tamanhoPx).
     * É desenhado como um anel de sombras de texto sem desfoque (o glifo dilatado por um círculo de raio px) e não com
     * -webkit-text-stroke: o traço do Chromium junta em esquadria e, em fonte variável (contornos sobrepostos), solta
     * farpas nos vértices agudos — visto no P e no acento de "PÚBLICO" em Montserrat 900 com contorno de 0,14 em.
     * Ocupa a propriedade text-shadow do elemento; sombra projetada vai em `filter: drop-shadow()` (como ctx.kit.legenda).
     */
    contorno(e, token, px) {
      const r = Math.max(0, +px || 0);
      e.style.webkitTextStroke = '';
      if (r <= 0) { e.style.textShadow = 'none'; return e; }
      const corHex = corToken(token);
      const partes = [];
      for (const raio of r > 3 ? [r, r * 0.5] : [r]) {            // anel externo + um interno: cobre traços mais finos que o raio
        const n = Math.max(12, Math.ceil((2 * Math.PI * raio) / 0.6));
        for (let k = 0; k < n; k++) {
          const a = (2 * Math.PI * k) / n;
          partes.push(`${(raio * Math.cos(a)).toFixed(2)}px ${(raio * Math.sin(a)).toFixed(2)}px 0 ${corHex}`);
        }
      }
      e.style.textShadow = partes.join(', ');
      return e;
    },

    /**
     * thumbnail.zona_proibida em px DESTE quadro: {x, y, w, h, x1, y1, canto} ou null ('nenhuma'). O tamanho vem de
     * thumbnail.zona_proibida_tamanho ([largura, altura] em fração do quadro; padrão 0,25 × 0,22, a reserva do selo de
     * duração do YouTube em plataformas.json). Em Python: d.zona_proibida(largura, altura).
     */
    zona_proibida() {
      const r = DA.thumbnail.zona_proibida_ret;
      if (!r) return null;
      const x = Math.round(r.x * L), y = Math.round(r.y * A), w = Math.round(r.w * L), h = Math.round(r.h * A);
      return { x, y, w, h, x1: x + w, y1: y + h, canto: DA.thumbnail.zona_proibida };
    },

    /** Duração (s) de uma transição da DA: 0 para 'corte', movimento.duracoes.media para as demais. */
    dur_transicao(tipo) { return (tipo || DA.movimento.transicoes.padrao) === 'corte' ? 0 : ctx.dur('media'); },

    /**
     * Transição entre duas camadas irmãs (position: absolute, do tamanho do quadro) em função PURA de p (0 = só A,
     * 1 = só B; passe p já com a curva: ctx.prog(t, t0, ctx.dur_transicao(), 'suave')). tipo: corte | fade | empurra |
     * mascara | desliza | zoom — padrão movimento.transicoes.padrao; fora de movimento.transicoes.permitidas é erro
     * (a DA decide quais existem). origem: 'direita' (padrão) | 'esquerda' | 'cima' | 'baixo'.
     * O mesmo mapa vale no ffmpeg: video.juntar(clipes, saida, transicao=…) — tabela em references/tokens.md.
     */
    transicao(a, b, p, tipo, { origem = 'direita' } = {}) {
      const t = tipo || DA.movimento.transicoes.padrao;
      const permitidas = DA.movimento.transicoes.permitidas;
      if (!TRANSICOES.includes(t)) throw new Error(`ctx.transicao: tipo ${JSON.stringify(t)} não existe (${TRANSICOES.join(', ')})`);
      if (!permitidas.includes(t)) throw new Error(`ctx.transicao: ${JSON.stringify(t)} não está em movimento.transicoes.permitidas da DA (${permitidas.join(', ')})`);
      const q = clamp(p);
      const estado = (e, { op = 1, tf = 'none', clip = 'none', z = 0, vis = true }) => {
        e.style.opacity = op.toFixed(3); e.style.transform = tf; e.style.clipPath = clip; e.style.zIndex = String(z);
        e.style.visibility = vis ? 'visible' : 'hidden';
      };
      if (q <= 0) { estado(a, { z: 1 }); estado(b, { vis: false }); return t; }
      if (q >= 1) { estado(a, { vis: false }); estado(b, { z: 1 }); return t; }
      const horizontal = origem === 'direita' || origem === 'esquerda';
      const sinal = origem === 'direita' || origem === 'baixo' ? 1 : -1;
      const desloca = (f) => (horizontal ? `translateX(${(sinal * f * L).toFixed(2)}px)` : `translateY(${(sinal * f * A).toFixed(2)}px)`);
      switch (t) {
        case 'corte': estado(a, { vis: q < 0.5, z: 1 }); estado(b, { vis: q >= 0.5, z: 1 }); break;
        case 'fade': estado(a, { z: 0 }); estado(b, { op: q, z: 1 }); break;
        case 'empurra': estado(a, { tf: desloca(-q), z: 0 }); estado(b, { tf: desloca(1 - q), z: 1 }); break;
        case 'desliza': estado(a, { z: 0 }); estado(b, { tf: desloca(1 - q), z: 1 }); break;
        case 'mascara': {
          const resto = ((1 - q) * 100).toFixed(3) + '%';
          const clip = origem === 'direita' ? `inset(0 0 0 ${resto})` : origem === 'esquerda' ? `inset(0 ${resto} 0 0)` : origem === 'baixo' ? `inset(${resto} 0 0 0)` : `inset(0 0 ${resto} 0)`;
          estado(a, { z: 0 }); estado(b, { clip, z: 1 });
          break;
        }
        case 'zoom': estado(b, { z: 0 }); estado(a, { op: 1 - q, tf: `scale(${(1 + 0.25 * q).toFixed(4)})`, z: 1 }); break;
      }
      return t;
    },

    /** ctx derivado para um quadro aninhado (ex.: a prancha monta um GC num quadro 1920×1080 reduzido). */
    sub({ L: L2, A: A2, palco: palco2, nome = null, dur: dur2 = null, alfa: alfa2 = false }) {
      const nome2 = nome || (L2 > A2 ? 'horizontal' : L2 < A2 ? 'vertical' : 'quadrado');
      const c2 = criarCtx({ DA, palco: palco2, formato: { nome: nome2, L: L2, A: A2, fps: formato.fps }, dur: dur2 ?? dur, alfa: alfa2 });
      c2.params = {};
      return c2;
    },
  };
    /**
   * ctx.kit — peças do kit prontas para QUALQUER cena (embutida ou de outra skill), várias instâncias por página.
   * Cada chamada devolve uma instância nova ({ el, … }): ponha `el` no DOM e chame os métodos dela em seek(t).
   *   ctx.kit.legenda(palavras, {falada, plataforma, x, y, maxLinhas})  → { el, posicionar(), seek(indice, {pulso}), layout }
   *   ctx.kit.tarja(texto, {tam, papel, inverter})                      → { el, medir(), seek(pBloco, pTexto) }
   *   ctx.kit.credito(texto, {plataforma, area, prefixo, posicao})      → { el, posicionar(), seek(p), sair(p), faixa, em_cima }
   *   ctx.kit.moldura({rotulo, sub, area, estilo, plataforma, …})       → { el, layout, seek(t), key(t), ancoras() }
   *   await ctx.kit.cena('barras', params, {palco, dur, L, A, alfa})    → cena embutida inteira numa camada sua
   */
  ctx.kit = {
    legenda: (palavras, op) => criarLegenda(ctx, palavras, op),
    tarja: (texto, op) => criarTarja(ctx, texto, op),
    credito: (texto, op) => criarCredito(ctx, texto, op),
    moldura: (op) => criarMoldura(ctx, op),
    /**
     * Monta uma cena embutida (titulo, gc, moldura, citacao, barras) numa camada da SUA cena. Cada chamada importa uma
     * cópia própria do módulo (o estado das cenas embutidas é por módulo), então duas instâncias convivem.
     * Devolve { meta, layout, ctx, seek(t), key(t), ancoras() } — seek(t) em tempo LOCAL da instância (0 … dur).
     */
    async cena(nome, params = {}, { palco: camada = palco, dur: d2 = null, L: L2 = L, A: A2 = A, alfa: alfa2 = true, nome: nomeFmt = null } = {}) {
      if (!/^[a-z][a-z0-9_]*$/.test(String(nome))) throw new Error(`ctx.kit.cena: nome ${JSON.stringify(nome)} inválido (titulo, gc, moldura, citacao, barras)`);
      ctx.kit._n = (ctx.kit._n || 0) + 1;
      let mod;
      try { mod = await import(new URL(`./cenas/${nome}.js?instancia=${ctx.kit._n}`, import.meta.url).href); } catch (e) {
        throw new Error(`ctx.kit.cena: não consegui carregar a cena embutida ${JSON.stringify(nome)} (${e && e.message ? e.message : e})`);
      }
      const esquema = (mod.meta && mod.meta.params) || {};
      const p = {};
      for (const [k, def] of Object.entries(esquema)) p[k] = k in params ? params[k] : (def.padrao === undefined ? null : JSON.parse(JSON.stringify(def.padrao)));
      for (const k of Object.keys(params)) if (!(k in esquema)) throw new Error(`ctx.kit.cena(${nome}): parâmetro ${JSON.stringify(k)} não existe (${Object.keys(esquema).join(', ')})`);
      for (const [k, def] of Object.entries(esquema)) if (def.obrigatorio && p[k] == null) throw new Error(`ctx.kit.cena(${nome}): faltou o parâmetro obrigatório ${JSON.stringify(k)}`);
      const c2 = ctx.sub({ L: L2, A: A2, palco: camada, nome: nomeFmt, dur: d2 ?? (mod.meta && mod.meta.dur_padrao) ?? dur, alfa: alfa2 });
      c2.params = p;
      const layout = await mod.build(camada, p, c2);
      return { meta: mod.meta || {}, layout: layout || null, ctx: c2, seek: (t) => mod.seek(t, c2), key: (t) => (typeof mod.key === 'function' ? mod.key(t, c2) : null),
        ancoras: () => (typeof mod.ancoras === 'function' ? mod.ancoras(c2) || [] : []) };
    },
  };
  return ctx;
}
