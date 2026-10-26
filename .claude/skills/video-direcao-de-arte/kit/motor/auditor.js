// auditor.js — camada C3: inspeciona os estilos COMPUTADOS da página inteira em vários instantes e reprova
// cor ou fonte fora da DA, animação/transition CSS, conteúdo externo não declarado e efeitos que alteram cor.
/* da-livre-arquivo: ferramenta de auditoria, não é peça. */
// Roda dentro do Chromium (palco.html). NÃO há escape implícito: elemento invisível agora (opacity 0,
// display none, fora do quadro, caixa zero) é auditado do mesmo jeito, porque vai aparecer em outro instante.
// O único escape é o atributo data-da-livre no elemento (vale para a subárvore) — e ele vai para o carimbo.
//
// O que o estilo computado NÃO mostra também é tratado aqui, um caso por vez:
//   · pixels de fora (img, video, canvas, <image>, iframe…) e CONTROLES NATIVOS (input, progress, meter, select,
//     button, textarea, audio…: o navegador os pinta com as cores do sistema) só passam com data-da-livre;
//   · imagem por CSS no elemento (`content: url()`), no marcador de lista (`list-style-image`) e em pseudo-elemento;
//   · cor do marcador de lista (::marker), texto selecionado (::selection), realce (::highlight) e emoji colorido;
//   · animação que não é CSS: SMIL (<animate>, <set>…), <marquee>, vídeo/áudio tocando e cursor de texto piscando —
//     reprovados mesmo dentro de data-da-livre, porque data-da-livre libera COR, não movimento fora de seek(t).

const PROPS_BORDA = ['top', 'right', 'bottom', 'left'];
const RE_COR = /(?:rgba?|hsla?|color|lab|lch|oklab|oklch|hwb)\([^()]*(?:\([^()]*\)[^()]*)*\)/g;
const RE_FUNCAO_COR = /^(?:rgba?|hsla?|color|lab|lch|oklab|oklch|hwb)\(/;
const SVG_FORMAS = new Set(['path', 'rect', 'circle', 'ellipse', 'line', 'polyline', 'polygon', 'text', 'tspan', 'textPath', 'use']);
const NOMES_GENERICOS = new Set(['serif', 'sans-serif', 'monospace', 'cursive', 'fantasy', 'system-ui', 'ui-serif', 'ui-sans-serif',
  'ui-monospace', 'ui-rounded', 'emoji', 'math', 'fangsong', 'inherit', 'initial', 'unset']);
const NAO_RENDERIZAM = new Set(['script', 'style', 'link', 'meta', 'title', 'head', 'base', 'template', 'noscript']);
// conteúdo cujo pixel o auditor não enxerga: só passa com data-da-livre explícito
const EXTERNOS = new Set(['img', 'video', 'canvas', 'image', 'iframe', 'object', 'embed', 'feimage']);
// controles nativos: quem pinta é o tema do navegador (azul de destaque, verde do <meter>, cinzas do sistema), e essas
// cores não aparecem em getComputedStyle — mesmo tratamento do conteúdo externo: só com data-da-livre explícito
const NATIVOS = new Set(['input', 'progress', 'meter', 'select', 'datalist', 'textarea', 'button', 'audio']);
const FILHOS_DE_NATIVO = new Set(['option', 'optgroup']);       // só existem dentro de select/datalist, que já foi reprovado ou declarado livre
// animação declarativa do SVG (SMIL): roda no relógio do documento, fora de seek(t)
const SMIL = new Set(['animate', 'animatetransform', 'animatemotion', 'animatecolor', 'set', 'discard']);
const SVG_NS = 'http://www.w3.org/2000/svg';
// emoji com apresentação colorida por padrão, sequência com seletor de emoji (U+FE0F), bandeira ou tecla
const RE_EMOJI = /\p{Emoji_Presentation}|\p{Extended_Pictographic}\uFE0F|[\u{1F1E6}-\u{1F1FF}]|\u20E3/u;
// funções de filter/backdrop-filter que mudam a cor do que está embaixo (blur, opacity e drop-shadow com cor da DA passam)
const FILTROS_DE_COR = new Set(['hue-rotate', 'invert', 'sepia', 'saturate', 'grayscale', 'contrast', 'brightness']);
const PSEUDOS = ['::before', '::after'];
// propriedades que carregam cor: nelas, declaração que o navegador descarta vira transparente/herdada em silêncio (D6)
const PROPS_DE_COR = /^(?:color|background(?:-color|-image)?|border(?:-(?:top|right|bottom|left|block|inline)(?:-(?:start|end))?)?(?:-color)?|outline(?:-color)?|fill|stroke|box-shadow|text-shadow|text-decoration(?:-color)?|caret-color|column-rule(?:-color)?|stop-color|flood-color|lighting-color|-webkit-text-stroke(?:-color)?|-webkit-text-fill-color|text-emphasis(?:-color)?|filter|backdrop-filter)$/i;
const FORMA_ALFA = 'cor da DA com alfa tem UMA forma: rgba(var(--da-cor-<nome>-rgb), a) no CSS — ou ctx.alfa(token, a) em cena';

/** 'a: b; c: d(e; f)' → [{prop, valor}], cortando só em ';' fora de parênteses e de aspas. */
function declaracoes(texto) {
  const saida = [];
  let nivel = 0, aspas = null, ini = 0;
  const fechar = (fim) => {
    const d = texto.slice(ini, fim), i = d.indexOf(':');
    if (i > 0) saida.push({ prop: d.slice(0, i).trim().toLowerCase(), valor: d.slice(i + 1).trim() });
  };
  for (let i = 0; i < texto.length; i++) {
    const c = texto[i];
    if (aspas) { if (c === '\\') i++; else if (c === aspas) aspas = null; continue; }
    if (c === '"' || c === "'") aspas = c;
    else if (c === '(') nivel++;
    else if (c === ')') nivel = Math.max(0, nivel - 1);
    else if (c === ';' && nivel === 0) { fechar(i); ini = i + 1; }
  }
  fechar(texto.length);
  return saida;
}

/** Troca cada var(--x[, reserva]) pelo valor computado da variável no elemento. → {texto, faltou: nome da 1ª variável indefinida sem reserva} */
function trocarVars(valor, cs, fundo = 0) {
  let saida = '', i = 0, faltou = null;
  while (i < valor.length) {
    const j = valor.indexOf('var(', i);
    if (j < 0) { saida += valor.slice(i); break; }
    if (j > 0 && /[\w-]/.test(valor[j - 1])) { saida += valor.slice(i, j + 4); i = j + 4; continue; }
    let n = 1, k = j + 4;
    for (; k < valor.length && n > 0; k++) { if (valor[k] === '(') n++; else if (valor[k] === ')') n--; }
    const dentro = valor.slice(j + 4, n === 0 ? k - 1 : k);
    const v = dentro.indexOf(',');
    const nome = (v < 0 ? dentro : dentro.slice(0, v)).trim();
    let real = cs.getPropertyValue(nome).trim();
    if (!real) {
      if (v >= 0 && fundo < 8) { const r = trocarVars(dentro.slice(v + 1), cs, fundo + 1); real = r.texto.trim(); faltou = faltou || r.faltou; }
      else faltou = faltou || nome;
    }
    saida += valor.slice(i, j) + real;
    i = k;
  }
  return { texto: saida, faltou };
}

/** Declarações de cor com var() nas folhas de estilo de um documento ou shadow root: [{seletor, base, prop, valor}]. */
function regrasComVar(raizDeEstilo) {
  const saida = [];
  const ver = (regras) => {
    for (const r of regras || []) {
      if (r.style && r.selectorText) {
        for (const d of declaracoes(r.style.cssText)) {
          if (d.valor.includes('var(') && PROPS_DE_COR.test(d.prop)) {
            saida.push({ seletor: r.selectorText, base: r.selectorText.replace(/::?(?:before|after|marker|first-letter|first-line|placeholder|selection)\b/gi, ''), ...d });
          }
        }
      }
      if (r.cssRules) ver(r.cssRules);
    }
  };
  for (const folha of [...(raizDeEstilo.styleSheets || []), ...(raizDeEstilo.adoptedStyleSheets || [])]) {
    try { ver(folha.cssRules); } catch { /* folha de outra origem */ }
  }
  return saida;
}

function parseRgb(s) {
  s = s.trim();
  let m = /^rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*(?:,\s*([\d.]+%?)\s*)?\)$/.exec(s)
    || /^rgba?\(\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)\s*(?:\/\s*([\d.]+%?)\s*)?\)$/.exec(s);
  const alfa = (v) => (v == null ? 1 : v.endsWith('%') ? parseFloat(v) / 100 : parseFloat(v));
  if (m) return { r: +m[1], g: +m[2], b: +m[3], a: alfa(m[4]) };
  // color-mix(in srgb, <cor da DA> N%, transparent) computa como color(srgb r g b / a), com r, g, b em 0–1
  m = /^color\(\s*srgb\s+([\d.eE+-]+)\s+([\d.eE+-]+)\s+([\d.eE+-]+)\s*(?:\/\s*([\d.]+%?)\s*)?\)$/.exec(s);
  if (m) return { r: +m[1] * 255, g: +m[2] * 255, b: +m[3] * 255, a: alfa(m[4]) };
  return null;
}

let _tela = null;
/** Último recurso para espaços de cor que não são sRGB (lab, oklch, display-p3…): pinta 1 px e lê o resultado. */
function parsePorCanvas(s) {
  try {
    if (!_tela) { _tela = document.createElement('canvas'); _tela.width = 1; _tela.height = 1; }
    const cx = _tela.getContext('2d', { willReadFrequently: true });
    cx.fillStyle = 'rgba(1, 2, 3, 0.5)';
    const sentinela = cx.fillStyle;
    cx.fillStyle = s;
    if (cx.fillStyle === sentinela) return null;               // o canvas recusou o valor
    cx.clearRect(0, 0, 1, 1);
    cx.fillRect(0, 0, 1, 1);
    const d = cx.getImageData(0, 0, 1, 1).data;
    return { r: d[0], g: d[1], b: d[2], a: d[3] / 255, aproximada: true };
  } catch { return null; }
}

function hexParaRgb(h) {
  h = h.replace('#', '');
  const n = parseInt(h.slice(0, 6), 16);
  return { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255 };
}

function paiDe(e) {
  if (e.parentElement) return e.parentElement;
  const raiz = e.getRootNode && e.getRootNode();
  return raiz && raiz.host ? raiz.host : null;                  // sai de um shadow root para o hospedeiro
}

function seletorCurto(e) {
  const partes = [];
  let atual = e;
  for (let n = 0; atual && atual.nodeType === 1 && n < 3 && atual.id !== 'palco' && atual !== document.body && atual !== document.documentElement; n++) {
    let s = atual.tagName.toLowerCase();
    if (atual.id) { s += '#' + atual.id; partes.unshift(s); break; }
    const classes = [...(atual.classList || [])].filter((c) => !c.startsWith('da-texto')).slice(0, 2);
    if (classes.length) s += '.' + classes.join('.');
    const pai = atual.parentElement;
    if (pai) {
      const irmaos = [...pai.children].filter((x) => x.tagName === atual.tagName);
      if (irmaos.length > 1) s += `:nth-of-type(${irmaos.indexOf(atual) + 1})`;
    } else if (atual.getRootNode && atual.getRootNode().host) s = '(shadow) ' + s;
    partes.unshift(s);
    atual = paiDe(atual);
  }
  if (!partes.length) return e === document.body ? 'body' : e === document.documentElement ? 'html' : e.id === 'palco' ? '#palco' : e.tagName.toLowerCase();
  return partes.join(' > ');
}

function temTextoDireto(e) {
  for (const n of e.childNodes) if (n.nodeType === 3 && n.nodeValue.trim()) return true;
  return false;
}

/** Texto de um `content` computado: '"oi"' → 'oi'; none/normal/url() → ''. */
function textoDoContent(c) {
  if (!c || c === 'none' || c === 'normal') return '';
  const m = c.match(/"((?:[^"\\]|\\.)*)"|'((?:[^'\\]|\\.)*)'/g);
  return m ? m.map((x) => x.slice(1, -1)).join('') : (/counter|attr\(/.test(c) ? '?' : '');
}

/** Regras de folha de estilo que citam pseudo-elementos raros (só então vale o custo de auditá-los). */
function pseudosRaros() {
  const achados = new Set();
  const ver = (regras) => {
    for (const r of regras || []) {
      if (r.selectorText) {
        if (/::?first-letter/i.test(r.selectorText)) achados.add('::first-letter');
        if (/::?first-line/i.test(r.selectorText)) achados.add('::first-line');
        if (/::marker/i.test(r.selectorText)) achados.add('::marker');
      }
      if (r.cssRules) ver(r.cssRules);
    }
  };
  for (const folha of document.styleSheets) { try { ver(folha.cssRules); } catch { /* folha de outra origem */ } }
  return achados;
}

/**
 * auditar({permitidas: ['#RRGGBB', …], familias: ['Nome CSS', …], tolerancia: 3, amostras: [t…], seek(t), raiz, sombras, apis})
 * → {ok, violacoes: [{t, seletor, propriedade, valor, motivo, proximo}], animacoes: [...], livres: [{seletor, motivo, tag, elementos, area}], amostras}
 * `sombras`: shadow roots registrados pelo palco (inclusive os fechados). `apis`: usos de APIs de tempo/aleatoriedade
 * que o palco interceptou — cada um vira uma violação. `doKit(el)`: true para elementos criados pelo próprio kit (grão).
 */
export function auditar({ permitidas, familias, tolerancia = 3, amostras = [0], seek = null, raiz = null, nomes = {}, sombras = [], apis = [], doKit = null }) {
  raiz = raiz || document.documentElement;
  const lista = permitidas.map((h) => ({ hex: h.toUpperCase(), ...hexParaRgb(h) }));
  const famOk = new Set(familias.map((f) => f.toLowerCase().replace(/^["']|["']$/g, '')));
  const violacoes = [];
  const animacoes = [];
  const vistos = new Set();
  const livres = new Map();                                     // elemento com data-da-livre → {seletor, motivo, tag, elementos, area}
  const L = window.innerWidth, A = window.innerHeight;
  const palco = document.getElementById('palco');
  const intocaveis = new Set([document.documentElement, document.body, palco].filter(Boolean));
  const sombraDe = new Map(sombras.filter((s) => s && s.host).map((s) => [s.host, s]));
  const raros = pseudosRaros();
  const regrasDe = new Map();                                   // documento ou shadow root → declarações de cor com var()
  const suporta = new Map();                                    // 'prop|valor' → CSS.supports (cache)
  const regrasPara = (e) => {
    const r = e.getRootNode ? e.getRootNode() : document;
    if (!regrasDe.has(r)) regrasDe.set(r, regrasComVar(r));
    return regrasDe.get(r);
  };

  function proxima(c) {
    let melhor = null, dist = Infinity;
    for (const p of lista) {
      const d = Math.max(Math.abs(p.r - c.r), Math.abs(p.g - c.g), Math.abs(p.b - c.b));
      if (d < dist) { dist = d; melhor = p; }
    }
    return melhor ? { hex: melhor.hex, token: nomes[melhor.hex] || null, distancia: Math.round(dist) } : null;
  }

  function corOk(c) {
    if (!c) return true;
    if (c.a <= 0.004) return true;                              // transparent
    const tol = c.aproximada ? tolerancia + 2 : tolerancia;
    return lista.some((p) => Math.abs(p.r - c.r) <= tol && Math.abs(p.g - c.g) <= tol && Math.abs(p.b - c.b) <= tol);
  }

  function registrar(t, seletor, propriedade, valor, motivo, proximo = null) {
    const chave = seletor + '|' + propriedade + '|' + valor;
    if (vistos.has(chave)) return;
    vistos.add(chave);
    violacoes.push({ t: +Number(t).toFixed(3), seletor, propriedade, valor: String(valor).slice(0, 200), motivo, proximo });
  }

  function conferirCor(t, sel, propriedade, valor) {
    if (!valor || valor === 'none' || valor === 'transparent' || valor === 'currentcolor') return;
    let c = parseRgb(valor);
    if (!c) {
      if (!RE_FUNCAO_COR.test(valor)) return;                   // url(#gradiente), context-fill…: as paradas são auditadas à parte
      c = parsePorCanvas(valor);
      if (!c) { registrar(t, sel, propriedade, valor, 'cor em formato não reconhecido'); return; }
    }
    if (corOk(c)) return;
    const px = proxima(c);
    registrar(t, sel, propriedade, valor, 'cor fora da DA' + (c.a < 1 ? ' (o alfa não é o problema: o RGB não bate)' : ''),
      px ? `${px.token ? px.token + ' ' : ''}${px.hex} (Δ ${px.distancia})` : null);
  }

  /** Cores dentro de uma lista (gradiente, sombra, filtro). `aceitaUrl` = false reprova url() fora de data-da-livre. */
  function conferirLista(t, sel, propriedade, valor, aceitaUrl = true) {
    if (!valor || valor === 'none' || valor === 'normal') return;
    if (/url\(/.test(valor)) {
      if (!aceitaUrl) registrar(t, sel, propriedade, valor.replace(/url\((?:"[^"]{40}[^"]*"|'[^']{40}[^']*'|[^)]{40}[^)]*)\)/g, 'url(…)'),
        'imagem por url() fora de data-da-livre — o auditor não enxerga os pixels; marque o elemento com data-da-livre (foto, logo de terceiros, captura, textura)');
      valor = valor.replace(/url\((?:"[^"]*"|'[^']*'|[^)]*)\)/g, 'url()');
    }
    if (!aceitaUrl && /(?:^|[\s,(])(?:paint|element|-webkit-canvas)\(/.test(valor)) {
      registrar(t, sel, propriedade, valor.slice(0, 80), 'imagem desenhada por código (paint() do CSS Houdini) — o auditor não enxerga os pixels; desenhe com elementos e tokens, ou use um elemento com data-da-livre');
    }
    for (const c of valor.match(RE_COR) || []) conferirCor(t, sel, propriedade, c);
  }

  function conferirFiltro(t, sel, propriedade, valor) {
    if (!valor || valor === 'none') return;
    if (/url\(/.test(valor)) registrar(t, sel, propriedade, valor, 'filtro SVG por url() pode alterar a cor — use cor da DA direto, ou data-da-livre se for foto/logo');
    for (const m of valor.matchAll(/([a-z-]+)\(/g)) {
      if (FILTROS_DE_COR.has(m[1])) {
        registrar(t, sel, propriedade, valor, `${m[1]}() altera a cor do que está embaixo: o resultado sai da paleta — troque pela cor da DA (ou data-da-livre em foto/logo)`);
        break;
      }
    }
    conferirLista(t, sel, propriedade, valor);                  // cor do drop-shadow()
  }

  /**
   * D6 — declaração de cor que o navegador joga fora sem avisar. `rgb(var(--da-cor-fundo-rgb) / 0.86)` passa no parser
   * (tem var()), mas depois da troca vira `rgb(10, 10, 10 / 0.86)`, que é inválido: o fundo computa transparente (e um
   * `color` assim herda a cor do pai). O estilo computado sozinho não denuncia — transparente é cor permitida —, então
   * a declaração é refeita aqui: troca as variáveis pelos valores do elemento e pergunta ao navegador se o resultado vale.
   */
  function conferirDeclaracao(t, sel, prop, bruto, cs) {
    const valor = bruto.replace(/\s*!important\s*$/i, '').trim();
    if (!valor || !PROPS_DE_COR.test(prop)) return;
    const comVar = valor.includes('var(');
    let final = valor;
    if (comVar) {
      const r = trocarVars(valor, cs);
      if (r.faltou) {
        registrar(t, sel, prop, bruto, `a variável ${r.faltou} não existe aqui (e não há valor de reserva): o navegador descarta a declaração e a cor computa transparente/herdada — confira o nome do token no da.css (--da-cor-<nome>, --da-cor-<nome>-rgb, --da-dado-<n>, --da-neutro-<n>)`);
        return;
      }
      final = r.texto;
    }
    const chave = prop + '|' + final;
    if (!suporta.has(chave)) {
      let ok = true;
      try { ok = !CSS.supports(prop, 'initial') || CSS.supports(prop, final); } catch { ok = true; }
      suporta.set(chave, ok);
    }
    if (suporta.get(chave)) return;
    registrar(t, sel, prop, bruto, `declaração inválida${comVar ? ` depois de trocar as variáveis (vira "${final.slice(0, 70)}")` : ''}: o navegador descarta e a cor computa transparente/herdada — ${FORMA_ALFA}`);
  }

  function conferirDeclaradas(t, sel, e, cs) {
    const estilo = e.getAttribute && e.getAttribute('style');
    if (estilo) for (const d of declaracoes(estilo)) conferirDeclaracao(t, sel, d.prop, d.valor, cs);
    for (const r of regrasPara(e)) {
      let casa = false;
      try { casa = !!r.base.trim() && e.matches(r.base); } catch { casa = false; }
      if (casa) conferirDeclaracao(t, r.seletor === r.base ? sel : `${sel} (regra ${r.seletor})`, r.prop, r.valor, cs);
    }
  }

  function conferirFonte(t, sel, cs) {
    const primeira = cs.fontFamily.split(',')[0].trim().replace(/^["']|["']$/g, '').toLowerCase();
    if (famOk.has(primeira)) return;
    registrar(t, sel, 'font-family', cs.fontFamily, NOMES_GENERICOS.has(primeira) ? 'fonte genérica (nenhum papel da DA aplicado)' : 'fonte fora da DA',
      'use var(--da-fonte-<papel>), a classe .da-<papel> ou ctx.estilo(el, papel)');
  }

  /** Propriedades que valem tanto para o elemento quanto para um pseudo-elemento. */
  function conferirCaixa(t, sel, cs, comTexto) {
    conferirCor(t, sel, 'background-color', cs.backgroundColor);
    conferirLista(t, sel, 'background-image', cs.backgroundImage, false);
    conferirLista(t, sel, 'border-image-source', cs.borderImageSource, false);
    conferirLista(t, sel, 'box-shadow', cs.boxShadow);
    for (const lado of PROPS_BORDA) {
      if (parseFloat(cs.getPropertyValue(`border-${lado}-width`)) > 0 && cs.getPropertyValue(`border-${lado}-style`) !== 'none') {
        conferirCor(t, sel, `border-${lado}-color`, cs.getPropertyValue(`border-${lado}-color`));
      }
    }
    if (cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) > 0) conferirCor(t, sel, 'outline-color', cs.outlineColor);
    if (cs.columnRuleStyle && cs.columnRuleStyle !== 'none' && parseFloat(cs.columnRuleWidth) > 0) conferirCor(t, sel, 'column-rule-color', cs.columnRuleColor);
    conferirFiltro(t, sel, 'filter', cs.filter);
    conferirFiltro(t, sel, 'backdrop-filter', cs.backdropFilter || cs.webkitBackdropFilter);
    if (cs.mixBlendMode && cs.mixBlendMode !== 'normal') {
      registrar(t, sel, 'mix-blend-mode', cs.mixBlendMode, 'mistura altera a cor do que está embaixo: o resultado sai da paleta (só a camada de grão do kit usa, com data-da-livre)');
    }
    if (cs.backgroundBlendMode && cs.backgroundBlendMode.split(',').some((m) => m.trim() !== 'normal')) {
      registrar(t, sel, 'background-blend-mode', cs.backgroundBlendMode, 'mistura de fundos altera a cor: o resultado sai da paleta');
    }
    if (comTexto) {
      conferirCor(t, sel, 'color', cs.color);
      conferirLista(t, sel, 'text-shadow', cs.textShadow);
      if (cs.textDecorationLine && cs.textDecorationLine !== 'none') conferirCor(t, sel, 'text-decoration-color', cs.textDecorationColor);
      if (parseFloat(cs.webkitTextStrokeWidth) > 0) conferirCor(t, sel, '-webkit-text-stroke-color', cs.webkitTextStrokeColor);
      if (cs.webkitTextFillColor && cs.webkitTextFillColor !== cs.color) conferirCor(t, sel, '-webkit-text-fill-color', cs.webkitTextFillColor);
      if (cs.textEmphasisStyle && cs.textEmphasisStyle !== 'none') conferirCor(t, sel, 'text-emphasis-color', cs.textEmphasisColor);
    }
  }

  /** O elemento (ou um ancestral, atravessando shadow roots) com data-da-livre; no html/body/#palco o atributo não vale. */
  function livreDe(e) {
    for (let n = e; n; n = paiDe(n)) {
      if (n.hasAttribute && n.hasAttribute('data-da-livre') && !intocaveis.has(n)) return n;
    }
    return null;
  }

  function anotarLivre(e) {
    let reg = livres.get(e);
    if (!reg) {
      reg = { seletor: seletorCurto(e), motivo: e.getAttribute('data-da-livre') || '', tag: e.tagName.toLowerCase(), elementos: 0, area: 0 };
      livres.set(e, reg);
    }
    reg.elementos = Math.max(reg.elementos, e.querySelectorAll('*').length + 1);
    const b = e.getBoundingClientRect();
    const w = Math.max(0, Math.min(L, b.right) - Math.max(0, b.left)), h = Math.max(0, Math.min(A, b.bottom) - Math.max(0, b.top));
    reg.area = Math.max(reg.area, +((w * h) / Math.max(1, L * A)).toFixed(3));
  }

  function* todos(no) {
    yield no;
    const sombra = no.shadowRoot || sombraDe.get(no);
    if (sombra) for (const f of sombra.children) yield* todos(f);
    for (const f of no.children) yield* todos(f);
  }

  for (const e of intocaveis) {
    if (e.hasAttribute('data-da-livre')) {
      registrar(amostras[0] ?? 0, seletorCurto(e), 'data-da-livre', e.getAttribute('data-da-livre') || '(vazio)',
        'data-da-livre no palco, no body ou no html liberaria a peça inteira — marque só o elemento da foto, do logo ou da captura');
    }
  }

  for (const t of amostras) {
    if (seek) seek(t);
    for (const e of todos(raiz)) {
      const tag = e.tagName.toLowerCase();
      if (NAO_RENDERIZAM.has(tag) || FILHOS_DE_NATIVO.has(tag)) continue;
      if (doKit && doKit(e)) continue;                          // camada de grão do kit: ruído neutro com mix-blend, a única exceção embutida
      // movimento fora de seek(t): vale para a página inteira, inclusive dentro de data-da-livre (que libera cor, não relógio)
      if (SMIL.has(tag) && e.namespaceURI === SVG_NS) {
        registrar(t, seletorCurto(e), `<${e.tagName}> (SMIL)`, ['attributeName', 'dur', 'repeatCount'].map((k) => (e.getAttribute(k) ? `${k}=${e.getAttribute(k)}` : '')).filter(Boolean).join(' ') || '(sem atributos)',
          'animação SMIL roda no relógio do navegador, fora de seek(t): cada render sai diferente — tire o elemento e anime o atributo dentro de seek(t) (data-da-livre não libera animação)');
        continue;
      }
      if (tag === 'marquee') {
        registrar(t, seletorCurto(e), '<marquee>', (e.textContent || '').trim().slice(0, 40), '<marquee> anima sozinho, fora de seek(t) — mova o texto com transform dentro de seek(t)');
        continue;
      }
      if ((tag === 'video' || tag === 'audio') && e.paused === false) {
        registrar(t, seletorCurto(e), `<${tag}> tocando`, (e.currentSrc || e.getAttribute('src') || '').slice(-80) || '(sem src)',
          'mídia tocando em tempo real: o quadro não depende só de t — a peça não leva vídeo/áudio vivo (componha o footage no ffmpeg: video.compor_overlay / video.encaixar_em_janela)');
      }
      const dono = livreDe(e);
      if (dono) { if (dono === e) anotarLivre(e); continue; }
      const sel = seletorCurto(e);
      if (EXTERNOS.has(tag)) {
        registrar(t, sel, tag === 'image' ? '<image> (SVG)' : `<${tag}>`, (e.getAttribute('src') || e.getAttribute('href') || '').slice(0, 80) || '(sem src)',
          'conteúdo que o auditor não enxerga (pixels de fora da DA) sem data-da-livre — declare data-da-livre="foto|logo|captura…" no elemento; o seletor vai para o carimbo e a conferência final lista');
        continue;
      }
      if (NATIVOS.has(tag)) {
        registrar(t, sel, `<${tag}>${e.getAttribute('type') ? ` type=${e.getAttribute('type')}` : ''} (controle nativo)`, (e.getAttribute('value') || e.textContent || '').trim().slice(0, 40) || '(vazio)',
          'controle nativo: quem pinta é o tema do navegador (azul de destaque, cinzas e verdes do sistema), fora da DA e invisível para o auditor — desenhe com div/svg e tokens, ou declare data-da-livre="captura de interface" no elemento');
        continue;
      }
      const cs = getComputedStyle(e);
      const svgForma = e instanceof SVGElement && SVG_FORMAS.has(tag);
      const comTexto = temTextoDireto(e) || (svgForma && (tag === 'text' || tag === 'tspan'));

      // transições e animações CSS (mesmo paradas): peças são função pura de seek(t)
      if (cs.transitionProperty !== 'none' && cs.transitionDuration.split(',').some((d) => parseFloat(d) > 0)) {
        registrar(t, sel, 'transition', `${cs.transitionProperty} ${cs.transitionDuration}`, 'transition CSS declarada (proibida: o motor chama seek(t) fora de ordem)');
      }
      if (cs.animationName && cs.animationName !== 'none') {
        registrar(t, sel, 'animation', cs.animationName, 'animation CSS declarada (proibida: o motor chama seek(t) fora de ordem)');
      }

      conferirCaixa(t, sel, cs, comTexto);
      conferirDeclaradas(t, sel, e, cs);
      if (comTexto && (!svgForma || tag === 'text' || tag === 'tspan')) conferirFonte(t, sel, cs);
      // `content: url()` no próprio elemento troca o conteúdo por uma imagem (gradiente idem): mesmo rigor do <img>
      if (cs.content && cs.content !== 'normal' && cs.content !== 'none' && /url\(|gradient\(|image-set\(|cross-fade\(/.test(cs.content)) {
        conferirLista(t, sel, 'content', cs.content, false);
      }
      if (cs.display === 'list-item') {
        // o marcador é pintado com a cor do item (mesmo sem texto direto) ou com uma imagem: nenhum dos dois passa em branco
        if (cs.listStyleImage && cs.listStyleImage !== 'none') conferirLista(t, sel + '::marker', 'list-style-image', cs.listStyleImage, false);
        else if (cs.listStyleType !== 'none') conferirCor(t, sel + '::marker', 'color', getComputedStyle(e, '::marker').color);
      }
      if (comTexto) {
        for (const n of e.childNodes) {
          if (n.nodeType !== 3) continue;
          const m = RE_EMOJI.exec(n.nodeValue);
          if (m) { registrar(t, sel, 'emoji', m[0], 'emoji é desenhado pela fonte de emoji do sistema, com cores que não são da DA — use um ícone SVG com tokens, ou envolva o emoji em <span data-da-livre="emoji">'); break; }
        }
      }
      if (svgForma && !e.closest('clipPath, mask')) {
        // <use> herda o preenchimento do símbolo: o fill computado dele só conta se foi declarado no próprio <use>
        const fillVale = tag !== 'line' && (tag !== 'use' || e.hasAttribute('fill') || e.style.fill);
        if (fillVale) conferirCor(t, sel, 'fill', cs.fill);
        if (cs.stroke !== 'none' && parseFloat(cs.strokeWidth) > 0 && (tag !== 'use' || e.hasAttribute('stroke') || e.style.stroke)) conferirCor(t, sel, 'stroke', cs.stroke);
      }
      if (tag === 'stop') conferirCor(t, sel, 'stop-color', cs.stopColor);
      if (tag === 'feflood' || tag === 'fedropshadow') conferirCor(t, sel, 'flood-color', cs.floodColor);
      if (tag === 'fediffuselighting' || tag === 'fespecularlighting') conferirCor(t, sel, 'lighting-color', cs.lightingColor);

      // pseudo-elementos: ::before/::after sempre; ::marker/::first-letter/::first-line só se alguma folha os cita
      for (const ps of PSEUDOS) {
        const pcs = getComputedStyle(e, ps);
        const conteudo = pcs.content;
        if (!conteudo || conteudo === 'none' || conteudo === 'normal') continue;
        const selPs = sel + ps;
        if (/url\(/.test(conteudo)) registrar(t, selPs, 'content', 'url(…)', 'imagem por url() em pseudo-elemento não pode ser declarada livre — use um elemento de verdade com data-da-livre');
        else if (/gradient\(/.test(conteudo)) conferirLista(t, selPs, 'content', conteudo);
        const texto = textoDoContent(conteudo).trim() !== '';
        conferirCaixa(t, selPs, pcs, texto);
        if (texto) conferirFonte(t, selPs, pcs);
        if (texto && RE_EMOJI.test(textoDoContent(conteudo))) registrar(t, selPs, 'emoji', conteudo.slice(0, 20), 'emoji em pseudo-elemento é pintado com as cores da fonte de emoji do sistema — use um elemento de verdade com data-da-livre="emoji" ou um ícone SVG com tokens');
      }
      if (comTexto) {
        for (const ps of ['::first-letter', '::first-line']) {
          if (!raros.has(ps)) continue;
          const pcs = getComputedStyle(e, ps);
          conferirCor(t, sel + ps, 'color', pcs.color);
          conferirCor(t, sel + ps, 'background-color', pcs.backgroundColor);
          conferirFonte(t, sel + ps, pcs);
        }
      }
    }
    // o que é pintado por cima do estilo: seleção de texto, realce (CSS Custom Highlight) e cursor de edição
    const selecao = window.getSelection ? window.getSelection() : null;
    if (selecao && selecao.rangeCount && !selecao.isCollapsed) {
      const no = selecao.anchorNode && (selecao.anchorNode.nodeType === 1 ? selecao.anchorNode : selecao.anchorNode.parentElement);
      if (!no || !livreDe(no)) {
        registrar(t, no ? seletorCurto(no) : '(documento)', '::selection', String(selecao).slice(0, 40),
          'texto selecionado é pintado com as cores de seleção (do sistema ou de uma regra ::selection), fora da DA — para marca-texto use um <span> com fundo em token; chame getSelection().removeAllRanges()');
      }
    }
    if (window.CSS && CSS.highlights && CSS.highlights.size) {
      registrar(t, '(documento)', '::highlight', [...CSS.highlights.keys()].join(', ').slice(0, 60),
        'realce por CSS.highlights é pintado por uma regra ::highlight() que o auditor não lê — use um <span> com cor e fundo em tokens');
    }
    const foco = document.activeElement;
    if (foco && foco !== document.body && foco.isContentEditable && !livreDe(foco)) {
      registrar(t, seletorCurto(foco), 'foco em contenteditable', '(cursor de texto)', 'elemento editável com foco mostra o cursor piscando em tempo real, fora de seek(t) — tire o foco (el.blur()) ou o contenteditable');
    }
    const anims = document.getAnimations ? document.getAnimations() : [];
    for (const a of anims) {
      const alvo = a.effect && a.effect.target ? seletorCurto(a.effect.target) : '?';
      const chave = 'anim|' + alvo + '|' + (a.animationName || a.transitionProperty || a.constructor.name);
      if (vistos.has(chave)) continue;
      vistos.add(chave);
      animacoes.push({ t: +t.toFixed(3), seletor: alvo, tipo: a.constructor.name, nome: a.animationName || a.transitionProperty || null });
    }
  }

  for (const u of apis) {
    registrar(amostras[0] ?? 0, u.onde || '(cena)', 'API proibida', u.api + (u.vezes > 1 ? ` ×${u.vezes}` : ''),
      `${u.api} chamada pela cena (${u.fase}): a peça tem de ser função pura de t — tempo só pelo t de seek(t), aleatoriedade só por ctx.rng(semente)`);
  }

  if (seek) seek(amostras[0] ?? 0);
  return { ok: violacoes.length === 0 && animacoes.length === 0, violacoes, animacoes, amostras, livres: [...livres.values()], apis_vistas: apis.length };
}
