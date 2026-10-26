// _legenda.js — peça compartilhada: legenda construída só com os tokens de `legenda` da DA (karaoke | palavra | bloco).
// É a MESMA legenda que texto.compor_legenda desenha em PIL (D10/D11): mesmo vão entre palavras (o espaço real da
// fonte), mesma quebra em linhas (quebrarPalavras = texto.quebrar_palavras), mesmo contorno (espessura × tamanho PARA
// FORA da letra), mesma sombra, mesma caixa de fundo única, mesmo centro e mesmo limite: o retângulo da zona segura.
//
//   const leg = ctx.kit.legenda(['A', 'conta', 'que', 'não', 'fecha'], { falada: 1, plataforma: 'uniao' });
//   palco.appendChild(leg.el); leg.posicionar();          // centro em legenda.posicao.<formato> (x: centro da zona)
//   leg.seek(indice, { pulso });                           // estado puro: palavra falada (−1 = nenhuma ainda)
//   leg.layout → { tamanho, encolheu, linhas, caixa, palavras, zona, dentro_da_zona }   (px do quadro)
//
// O contorno é ctx.contorno (anel de sombras de texto: cantos redondos, como o stroke do PIL) e a sombra é
// filter: drop-shadow por fileira (projetada pelo texto já com o contorno, como em texto.py). No estilo `palavra` a cue
// inteira tem um tamanho só e só a falada aparece — em PIL: texto.estados_da_legenda / compor_legenda(apenas=i).

/** Mesmo algoritmo de texto.quebrar_palavras: enche cada linha e depois equilibra; null = não coube. */
export function quebrarPalavras(larguras, vao, larguraMax, maxLinhas = null) {
  const n = larguras.length;
  if (!n) return [];
  if (larguraMax == null) return [larguras.map((_, i) => i)];
  if (larguras.some((w) => w > larguraMax + 0.5)) return null;
  const linhas = [];
  let atual = [0], wAtual = larguras[0];
  for (let i = 1; i < n; i++) {
    if (wAtual + vao + larguras[i] <= larguraMax + 0.5) { atual.push(i); wAtual += vao + larguras[i]; }
    else { linhas.push(atual); atual = [i]; wAtual = larguras[i]; }
  }
  linhas.push(atual);
  if (maxLinhas != null && linhas.length > maxLinhas) return null;
  const larg = (l) => l.reduce((s, i) => s + larguras[i], 0) + vao * Math.max(0, l.length - 1);
  for (let k = 0; k < 4 * n; k++) {
    let mudou = false;
    for (let j = 0; j < linhas.length - 1; j++) {
      const a = linhas[j], b = linhas[j + 1];
      if (a.length < 2) continue;
      const a2 = a.slice(0, -1), b2 = [a[a.length - 1], ...b];
      if (larg(b2) <= larguraMax + 0.5 && Math.max(larg(a2), larg(b2)) < Math.max(larg(a), larg(b)) - 0.5) { linhas[j] = a2; linhas[j + 1] = b2; mudou = true; }
    }
    if (!mudou) break;
  }
  return linhas;
}

/**
 * Cue de amostra que fecha sentido com n palavras: a prancha, a thumbnail de amostra e o teste de movimento nunca
 * mostram uma frase cortada ("A conta que não"). Com um título próprio, valem as n primeiras palavras dele.
 * Em Python: da_ext_motor.frase_de_amostra(n) (a mesma tabela).
 */
const FRASES_DE_AMOSTRA = { 1: 'Furou', 2: 'Conta furada', 3: 'A conta furou', 4: 'A conta não fecha', 5: 'A conta que não fecha' };
export function fraseDeAmostra(n, titulo = null) {
  const padrao = !titulo || titulo === FRASES_DE_AMOSTRA[5];
  if (!padrao) return String(titulo).trim().split(/\s+/).slice(0, Math.max(1, n));
  return FRASES_DE_AMOSTRA[Math.max(1, Math.min(5, n))].split(' ');
}
/** Índice da palavra "de conteúdo" de uma cue (a mais longa; em empate, a última): é a que a amostra destaca. */
export function palavraDeConteudo(palavras) {
  let i = 0;
  palavras.forEach((w, k) => { if (w.length >= palavras[i].length) i = k; });
  return i;
}

export function criarLegenda(ctx, palavras, { falada = 0, formato = null, largura = null, plataforma = undefined, x = null, y = null,
  maxLinhas = null, linhas = null, minimo = 10 } = {}) {
  const cfg = ctx.DA.legenda;
  const fmt = formato || ctx.orientacao;
  const pos = cfg.posicao[fmt] || cfg.posicao.horizontal;
  const zona = plataforma === 'quadro' ? { x: 0, y: 0, w: ctx.L, h: ctx.A, x1: ctx.L, y1: ctx.A, plataforma: 'quadro' } : ctx.area_segura(plataforma || undefined);
  const papel = ctx.fonte(cfg.papel);
  const sx = papel.escala_x || 1;
  const tamPedido = ctx.px(cfg.tamanho);
  const maxW = Math.min(largura ?? ctx.L * (pos.largura_max ?? cfg.largura_max), zona.w);
  const nl = maxLinhas ?? cfg.max_linhas;
  const umaPorVez = cfg.estilo === 'palavra';
  const altLinha = papel.altura_linha || 1.1;

  const raiz = ctx.el('div', 'legenda legenda-' + cfg.estilo);
  Object.assign(raiz.style, { position: 'absolute', transform: 'translate(-50%, -50%)', pointerEvents: 'none', whiteSpace: 'nowrap' });
  const bloco = ctx.el('div', 'legenda-linha');                   // o bloco inteiro (uma ou mais fileiras): caixa de fundo única
  ctx.estilo(bloco, cfg.papel, { tam: tamPedido, cor: cfg.cor });
  Object.assign(bloco.style, { textAlign: 'center', textTransform: cfg.caixa === 'alta' ? 'uppercase' : 'none', display: 'inline-block',
    lineHeight: String(altLinha), boxSizing: 'content-box', verticalAlign: 'top' });
  if (sx !== 1) { bloco.style.transform = `scaleX(${sx})`; bloco.style.transformOrigin = 'center center'; }
  raiz.appendChild(bloco);
  const spans = palavras.map((w) => {
    const s = ctx.el('span', 'legenda-palavra', w);
    s.style.display = 'inline-block';
    s.style.whiteSpace = 'pre';
    return s;
  });

  // estilo que depende do tamanho: contorno (para fora), sombra e caixa de fundo — as mesmas contas de texto.py
  const medidas = (tam) => {
    const esp = cfg.contorno && cfg.contorno.espessura > 0 ? Math.max(1, Math.round(cfg.contorno.espessura * tam)) : 0;
    const resp = cfg.fundo ? (cfg.fundo.respiro || [0.4, 0.2]) : [0, 0];
    const rx = resp[0] * tam, ry = resp[1] * tam;
    return { esp, rx, ry, bordaX: Math.max(esp, rx) * sx, bordaY: Math.max(esp, ry) };
  };
  let filtroSombra = '';
  const vestir = (tam) => {
    const m = medidas(tam);
    bloco.style.fontSize = tam.toFixed(2) + 'px';
    if (m.esp) ctx.contorno(bloco, cfg.contorno.cor, m.esp);
    if (cfg.sombra) {
      // a sombra é a do texto JÁ com o contorno, como em texto.py: `filter: drop-shadow` enxerga glifo + traço (o
      // text-shadow do Chromium projeta só o preenchimento, que fica escondido atrás de um contorno mais grosso que o
      // deslocamento). O 3º valor do drop-shadow é o desvio-padrão: metade do raio CSS que `sombra.desfoque` declara.
      const s = cfg.sombra;
      filtroSombra = `drop-shadow(${((s.dx || 0) * tam).toFixed(2)}px ${((s.dy || 0) * tam).toFixed(2)}px ${((s.desfoque || 0) * tam / 2).toFixed(2)}px ${ctx.alfa(s.cor || 'neutro-1', s.alfa ?? 0.6)})`;
    }
    if (cfg.fundo) {
      const f = cfg.fundo;
      Object.assign(bloco.style, { background: ctx.alfa(f.cor, f.alfa ?? 0.85), padding: `${m.ry.toFixed(2)}px ${m.rx.toFixed(2)}px`, borderRadius: ((f.raio || 0) * tam).toFixed(2) + 'px' });
    }
    return m;
  };

  // mede com o bloco provisoriamente no palco (as fontes já estão carregadas); offsetWidth ignora transform de ancestrais,
  // e a régua de 1000 px dá a escala real para usar larguras fracionárias
  const montarFileiras = (quebra) => {
    bloco.textContent = '';
    for (const l of quebra) {
      const f = ctx.el('div', 'legenda-fileira');
      f.style.whiteSpace = 'nowrap';
      if (filtroSombra) f.style.filter = filtroSombra;          // por fileira: a caixa de fundo do bloco não projeta sombra
      l.forEach((i, k) => { f.appendChild(spans[i]); if (k < l.length - 1) f.appendChild(document.createTextNode(' ')); });
      bloco.appendChild(f);
    }
  };
  const hospedeiro = ctx.palco || document.body;
  raiz.style.visibility = 'hidden';
  hospedeiro.appendChild(raiz);
  const regua = ctx.el('div');
  Object.assign(regua.style, { position: 'absolute', width: '1000px', height: '1px', visibility: 'hidden' });
  hospedeiro.appendChild(regua);
  const escalaTela = (regua.getBoundingClientRect().width || 1000) / 1000;
  const espaco = ctx.el('span', null, ' ');
  espaco.style.display = 'inline-block'; espaco.style.whiteSpace = 'pre';
  const largDe = (e) => e.getBoundingClientRect().width / escalaTela / (sx !== 1 ? sx : 1) * 1;     // largura de layout (antes do scaleX do bloco)
  let tam = tamPedido, quebra = null, larguras = [], vao = 0, m = null, coube = true;
  for (;;) {
    m = vestir(tam);
    montarFileiras([palavras.map((_, i) => i)]);
    bloco.firstChild.appendChild(espaco);
    const tr = parseFloat(getComputedStyle(bloco).letterSpacing) || 0;
    larguras = spans.map((s) => (largDe(s) - tr) * sx);            // avanço sem o tracking do fim, já condensado (como texto.largura_texto)
    vao = (largDe(espaco) + tr) * sx;                               // espaço real da fonte + tracking dos dois lados
    espaco.remove();
    const util = maxW - 2 * m.bordaX;
    if (umaPorVez) quebra = larguras.every((w) => w <= util + 0.5) ? [palavras.map((_, i) => i)] : null;
    else if (linhas) quebra = linhas.every((l) => l.reduce((s, i) => s + larguras[i], 0) + vao * (l.length - 1) <= util + 0.5) ? linhas : null;
    else quebra = quebrarPalavras(larguras, vao, util, nl);
    const cabeH = quebra && (umaPorVez ? 1 : quebra.length) * tam * altLinha + 2 * m.bordaY <= zona.h + 0.5;
    if (quebra && cabeH) break;
    if (tam * 0.94 < minimo) {
      coube = false;
      quebra = linhas || [palavras.map((_, i) => i)];
      if (!linhas && !umaPorVez && nl > 1 && palavras.length > 1) {
        const por = Math.ceil(palavras.length / nl);
        quebra = [];
        for (let i = 0; i < palavras.length; i += por) quebra.push(palavras.map((_, k) => k).slice(i, i + por));
      }
      break;
    }
    tam *= 0.94;
  }
  montarFileiras(quebra);
  regua.remove();
  raiz.remove();
  raiz.style.visibility = '';

  // geometria final (px do quadro), calculada como em texto.compor_legenda
  const largLinhas = quebra.map((l) => l.reduce((s, i) => s + larguras[i], 0) + vao * (l.length - 1));
  const largTxt = umaPorVez ? Math.max(...larguras) : Math.max(...largLinhas);
  const altTxt = (umaPorVez ? 1 : quebra.length) * tam * altLinha;
  const w = largTxt + 2 * m.bordaX, h = altTxt + 2 * m.bordaY;
  const centro = () => {
    let cx = x ?? (pos.x != null ? pos.x * ctx.L : (zona.x + zona.x1) / 2);
    let cy = y ?? pos.y * ctx.A;
    cx = w > zona.w ? (zona.x + zona.x1) / 2 : Math.min(Math.max(cx, zona.x + w / 2), zona.x1 - w / 2);
    cy = h > zona.h ? (zona.y + zona.y1) / 2 : Math.min(Math.max(cy, zona.y + h / 2), zona.y1 - h / 2);
    return { cx, cy };
  };
  const geometria = () => {
    const { cx, cy } = centro();
    const caixa = { x0: cx - w / 2, y0: cy - h / 2, x1: cx + w / 2, y1: cy + h / 2 };
    const pal = [];
    quebra.forEach((l, li) => {
      let px = cx - largLinhas[li] / 2;
      for (const i of l) { pal[i] = { texto: palavras[i], linha: li, x0: +px.toFixed(2), x1: +(px + larguras[i]).toFixed(2) }; px += larguras[i] + vao; }
    });
    const r2 = (v) => +v.toFixed(2);
    return { tamanho: r2(tam), tamanho_pedido: r2(tamPedido), encolheu: tam < tamPedido - 1e-6, coube, linhas: quebra.map((l) => l.map((i) => palavras[i])),
      caixa: { x0: r2(caixa.x0), y0: r2(caixa.y0), x1: r2(caixa.x1), y1: r2(caixa.y1) }, palavras: pal, vao: r2(vao), contorno_px: m.esp,
      zona: { x0: zona.x, y0: zona.y, x1: zona.x1, y1: zona.y1, plataforma: zona.plataforma },
      dentro_da_zona: caixa.x0 >= zona.x - 0.5 && caixa.x1 <= zona.x1 + 0.5 && caixa.y0 >= zona.y - 0.5 && caixa.y1 <= zona.y1 + 0.5 };
  };

  const api = {
    el: raiz, linha: bloco, spans, tam, layout: null,
    /** Estado puro: índice da palavra falada (ou -1 = nenhuma ainda). */
    seek(indice, { pulso = 0 } = {}) {
      spans.forEach((s, i) => {
        let cor = cfg.cor_hex || ctx.cor(cfg.cor);
        if (cfg.estilo === 'karaoke') {
          if (i === indice) cor = ctx.cor(cfg.cor_destaque);
          else if (i < indice && cfg.cor_falada) cor = ctx.cor(cfg.cor_falada);
        } else if (umaPorVez) {
          s.style.visibility = i === indice ? 'visible' : 'hidden';
          s.style.position = i === indice ? 'relative' : 'absolute';
          cor = ctx.cor(cfg.cor_destaque);
        }
        s.style.color = cor;
        const escala = cfg.animacao === 'pop' && i === indice ? 1 + 0.08 * (1 - ctx.clamp(pulso)) : 1;
        s.style.transform = escala !== 1 ? `scale(${escala.toFixed(3)})` : 'none';
      });
      return indice;
    },
    /** Põe o bloco no lugar (centro da DA, empurrado para dentro da zona segura). Devolve o y (fração da altura). */
    posicionar() {
      const { cx, cy } = centro();
      raiz.style.left = cx.toFixed(2) + 'px';
      raiz.style.top = cy.toFixed(2) + 'px';
      api.layout = geometria();
      return cy / ctx.A;
    },
  };
  api.layout = geometria();
  api.seek(falada);
  return api;
}
