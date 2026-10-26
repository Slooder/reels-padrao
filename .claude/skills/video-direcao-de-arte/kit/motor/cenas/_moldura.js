// _moldura.js — peça compartilhada: moldura de insert/b-roll conforme tratamento.moldura da DA (nenhuma | borda |
// cantoneiras | janela | polaroid), com rótulo e sub opcionais. É o corpo da cena `moldura` e o que ctx.kit.moldura
// entrega a cenas de outras skills — cada chamada é uma instância independente (várias molduras na mesma página).
//
//   const m = ctx.kit.moldura({ rotulo: 'arquivo · 2018', sub: 'reprodução', area: [0.1, 0.2, 0.5, 0.4], plataforma: 'uniao' });
//   palco.appendChild(m.el);  …  m.seek(t);     // m.layout.janela / janela_girada: onde o insert entra (px do quadro)
//
// A janela (área do vídeo) fica transparente; nada escurece o vídeo. Rótulo e sub dos estilos borda, cantoneiras e
// nenhuma ficam sempre dentro da zona segura (`plataforma`; padrão do formato) e fora da faixa da legenda quando a peça
// leva legenda queimada (ctx.area_livre). Em janela e polaroid eles moram no cabeçalho/na base da moldura: sem `area`,
// a moldura inteira nasce dentro dessa área livre (no vertical, uma janela de 660 px de largura acima da legenda).
//
// Rótulo e sub CABEM sempre na largura que têm (a da zona, do cabeçalho da janela ou da base da polaroid):
//   1. lado a lado numa linha (rótulo à esquerda, sub à direita), encolhendo os dois até ctx.minimo_legivel;
//   2. se não couberem, o sub desce para baixo do rótulo e cada um quebra em até 2 linhas, encolhendo até o mínimo
//      (o cabeçalho da janela e a base da polaroid crescem para acomodar — layout.janela já vem com a altura nova).
// layout.rotulo_na_zona é medido nos retângulos REAIS de rótulo e sub (layout.rotulo, layout.sub): só é falso quando
// uma `area` pedida põe a moldura fora da zona segura ou quando nem no mínimo legível o texto cabe.

const padH = (e) => { const cs = getComputedStyle(e); return (parseFloat(cs.paddingLeft) || 0) + (parseFloat(cs.paddingRight) || 0); };

/** Tenta deixar `a` e `b` (wrappers de ctx.texto com wrap) lado a lado em `largura` px, encolhendo os dois até `min`. */
function cabemLadoALado(ctx, a, b, largura, vao, min) {
  const lista = [a, b].filter(Boolean);
  for (const e of lista) e._inner.style.whiteSpace = 'nowrap';
  let ok = false;
  for (let k = 0; k < 40; k++) {
    let soma = lista.length > 1 ? vao : 0;
    for (const e of lista) { ctx.medir(e); soma += e.offsetWidth; }
    if (soma <= largura + 0.5) { ok = true; break; }
    let mudou = false;
    for (const e of lista) {
      const tam = e._tam * 0.94;
      if (tam >= Math.min(min, e._tam0) - 1e-6) { e._tam = tam; e._inner.style.fontSize = tam.toFixed(2) + 'px'; mudou = true; }
    }
    if (!mudou) break;
  }
  if (!ok) for (const e of lista) { e._inner.style.whiteSpace = 'normal'; e._tam = e._tam0; e._inner.style.fontSize = e._tam0.toFixed(2) + 'px'; }
  return ok;
}

/** Texto sozinho na linha: quebra em até 2 linhas dentro de `largura` px (com o respiro do chip) e encolhe até `min`. */
function caberEmpilhado(ctx, e, largura, min) {
  const w = Math.max(8, largura - padH(e));
  e._maxW = w;
  e._inner.style.textWrapStyle = 'balance';                   // duas linhas parelhas: nada de "· 2018" sozinho na segunda
  return ctx.ajustar_texto(e, w, { min: Math.min(min, e._tam0), maxLinhas: 2 });
}

export function criarMoldura(ctx, op = {}) {
  const p = { rotulo: null, sub: null, area: null, inclinacao: null, estilo: null, plataforma: null, reservar_legenda: null, ...op };
  const zona = ctx.area_segura(p.plataforma || undefined);
  const livre = ctx.area_livre(p.plataforma || undefined, { legenda: p.reservar_legenda });
  const cfg = ctx.DA.tratamento.moldura;
  const estilo = p.estilo || cfg.estilo;
  const cor = ctx.cor(cfg.cor);
  const esp = Math.max(1, ctx.px(cfg.espessura));
  const margem = ctx.px(cfg.margem);
  const raio = ctx.px(cfg.raio);
  const L = ctx.L, A = ctx.A;
  let jan = p.area ? { x: p.area[0] * L, y: p.area[1] * A, w: p.area[2] * L, h: p.area[3] * A }
    : { x: margem, y: margem, w: L - 2 * margem, h: A - 2 * margem };
  if (!p.area && (estilo === 'janela' || estilo === 'polaroid')) {
    // moldura com cabeçalho/base próprios: o padrão é caber inteira na área livre, para o rótulo nunca nascer sob a
    // interface do app nem sobre a legenda (no horizontal a área livre é praticamente o quadro menos a margem)
    const x0 = Math.max(jan.x, livre.x), y0 = Math.max(jan.y, livre.y), x1 = Math.min(jan.x + jan.w, livre.x1), y1 = Math.min(jan.y + jan.h, livre.y1);
    jan = { x: x0, y: y0, w: x1 - x0, h: y1 - y0 };
  }
  const inclin = p.inclinacao != null ? p.inclinacao : (estilo === 'polaroid' ? -1.5 : 0);
  const raiz = ctx.el('div', 'moldura moldura-' + estilo);
  Object.assign(raiz.style, { position: 'absolute', left: '0', top: '0', width: L + 'px', height: A + 'px', transformOrigin: 'center center' });
  const partes = {};                                        // nome → elemento (para a entrada)
  const tamRot = ctx.tam('nota');
  const padChip = tamRot * 0.5;
  const minLeg = ctx.minimo_legivel;
  let empilhado = false;
  // as medidas pedem o elemento no DOM: a raiz fica provisoriamente no palco e sai no fim (quem chama decide onde pôr)
  const hospedeiro = ctx.palco || document.body;
  hospedeiro.appendChild(raiz);

  /** Texto de apoio que sabe quebrar: `larguraMax` é a largura do TEXTO (sem o respiro do chip). */
  function apoio(papel, texto, tam, corTexto, larguraMax) {
    const t = ctx.texto(papel, texto, { tam, cor: corTexto, wrap: true, maxW: Math.max(8, larguraMax) });
    t._inner.style.overflowWrap = 'anywhere';                 // palavra maior que a linha quebra em vez de vazar
    t._tam0 = t._tam;
    t.style.flex = 'none';
    return t;
  }

  function chip(texto, corTexto, corBg, larguraMax) {
    const t = apoio('dados', texto, tamRot, corTexto, larguraMax);
    t._inner.style.letterSpacing = '0.14em';
    t._inner.style.textTransform = 'uppercase';
    if (corBg) Object.assign(t.style, { background: corBg, padding: `${(padChip * 0.55).toFixed(1)}px ${padChip.toFixed(1)}px`, borderRadius: ctx.raio + 'px' });
    return t;
  }

  if (estilo === 'borda') {
    const b = ctx.el('div', 'moldura-borda');
    Object.assign(b.style, { position: 'absolute', left: jan.x + 'px', top: jan.y + 'px', width: jan.w + 'px', height: jan.h + 'px', boxSizing: 'border-box' });
    // quatro arestas separadas: a moldura se desenha em sequência (topo → direita → base → esquerda)
    const arestas = [
      ['topo', { left: 0, top: 0, width: jan.w, height: esp }, 'left center', 'scaleX'],
      ['direita', { right: 0, top: 0, width: esp, height: jan.h }, 'center top', 'scaleY'],
      ['base', { left: 0, bottom: 0, width: jan.w, height: esp }, 'right center', 'scaleX'],
      ['esquerda', { left: 0, top: 0, width: esp, height: jan.h }, 'center bottom', 'scaleY'],
    ];
    for (const [nome, css, origem, eixo] of arestas) {
      const a = ctx.el('div', 'moldura-aresta');
      Object.assign(a.style, { position: 'absolute', background: cor, transformOrigin: origem });
      for (const [k, v] of Object.entries(css)) a.style[k] = v + 'px';
      b.appendChild(a); partes[nome] = a; a._eixo = eixo;
    }
    if (raio > 0) { b.style.borderRadius = raio + 'px'; b.style.overflow = 'hidden'; }
    raiz.appendChild(b);
  } else if (estilo === 'cantoneiras') {
    const braco = Math.max(esp * 6, ctx.px(0.055));
    const cantos = [['tl', 'top', 'left'], ['tr', 'top', 'right'], ['bl', 'bottom', 'left'], ['br', 'bottom', 'right']];
    for (const [k, v, h] of cantos) {
      const c = ctx.el('div', 'moldura-canto ' + k);
      Object.assign(c.style, { position: 'absolute', width: braco + 'px', height: braco + 'px', boxSizing: 'border-box', border: '0 solid ' + cor });
      c.style[v] = (v === 'top' ? jan.y : A - jan.y - jan.h) + 'px';
      c.style[h] = (h === 'left' ? jan.x : L - jan.x - jan.w) + 'px';
      c.style[`border${v[0].toUpperCase() + v.slice(1)}Width`] = esp + 'px';
      c.style[`border${h[0].toUpperCase() + h.slice(1)}Width`] = esp + 'px';
      c._dx = (h === 'left' ? 1 : -1) * ctx.px(0.02); c._dy = (v === 'top' ? 1 : -1) * ctx.px(0.02);
      raiz.appendChild(c); partes[k] = c;
    }
    // linha interna fina que "fecha" o quadro
    const linha = ctx.el('div', 'moldura-linha');
    const rec = braco * 0.45;
    Object.assign(linha.style, { position: 'absolute', left: (jan.x + rec) + 'px', top: (jan.y + rec) + 'px', width: (jan.w - 2 * rec) + 'px', height: (jan.h - 2 * rec) + 'px',
      boxSizing: 'border-box', border: `${Math.max(1, ctx.traco * 0.5).toFixed(1)}px solid ${ctx.alfa('texto_suave', 0.55)}`, transformOrigin: 'left center' });
    raiz.appendChild(linha); partes.linha = linha;
  } else if (estilo === 'janela') {
    const barra = Math.max(tamRot * 2.1, ctx.px(0.04));
    const j = ctx.el('div', 'moldura-janela');
    Object.assign(j.style, { position: 'absolute', left: jan.x + 'px', top: jan.y + 'px', width: jan.w + 'px', height: jan.h + 'px', boxSizing: 'border-box',
      border: `${esp.toFixed(1)}px solid ${cor}`, borderRadius: raio + 'px', overflow: 'hidden', transformOrigin: 'center center' });
    const cab = ctx.el('div', 'moldura-cabecalho');
    Object.assign(cab.style, { position: 'absolute', left: '0', top: '0', right: '0', height: barra + 'px', background: ctx.alfa('superficie', 0.94),
      borderBottom: `${Math.max(1, esp * 0.6).toFixed(1)}px solid ${cor}`, display: 'flex', alignItems: 'center', gap: (barra * 0.28) + 'px', padding: `0 ${(barra * 0.4).toFixed(1)}px` });
    const pontos = ctx.el('div', 'moldura-pontos');
    Object.assign(pontos.style, { display: 'flex', gap: (barra * 0.16) + 'px', marginRight: (barra * 0.2) + 'px' });
    for (const tk of ['negativo', 'alerta', 'positivo']) {
      const d = ctx.el('span');
      Object.assign(d.style, { width: (barra * 0.26) + 'px', height: (barra * 0.26) + 'px', borderRadius: '50%', background: ctx.cor(tk), display: 'block' });
      pontos.appendChild(d);
    }
    cab.appendChild(pontos);
    // largura que sobra para os textos: a do cabeçalho menos o respiro lateral, os três pontos e o vão até eles
    const dentro = Math.max(8, jan.w - 2 * esp - 2 * barra * 0.4 - barra * 1.3 - barra * 0.28);
    const textos = ctx.el('div', 'moldura-rotulos');
    Object.assign(textos.style, { display: 'flex', flex: '1 1 auto', minWidth: '0', alignItems: 'center', justifyContent: 'space-between', gap: (barra * 0.28) + 'px' });
    const r = p.rotulo ? chip(p.rotulo, 'texto', null, dentro) : null, s = p.sub ? chip(p.sub, 'texto_suave', null, dentro) : null;
    if (r) { textos.appendChild(r); partes.rotulo = r; }
    if (s) { s.style.marginLeft = 'auto'; textos.appendChild(s); partes.sub = s; }
    cab.appendChild(textos);
    j.appendChild(cab);
    raiz.appendChild(j); partes.janela = j;
    let alturaCab = barra;
    if (!cabemLadoALado(ctx, r, s, dentro, barra * 0.28, minLeg)) {
      // não cabem lado a lado nem no mínimo legível: o sub desce, cada um quebra em até 2 linhas e o cabeçalho cresce
      const vaoY = tamRot * 0.25;
      Object.assign(textos.style, { flexDirection: 'column', alignItems: 'flex-start', justifyContent: 'center', gap: vaoY + 'px' });
      if (s) s.style.marginLeft = '0';
      for (const e of [r, s]) if (e) caberEmpilhado(ctx, e, dentro, minLeg);
      alturaCab = Math.max(barra, Math.ceil((r ? r.offsetHeight : 0) + (s ? s.offsetHeight : 0) + (r && s ? vaoY : 0) + tamRot * 0.9));
      empilhado = !!(r && s);
      cab.style.height = alturaCab + 'px';
    }
    jan = { x: jan.x + esp, y: jan.y + alturaCab, w: jan.w - 2 * esp, h: jan.h - alturaCab - esp };
  } else if (estilo === 'polaroid') {
    const lado = Math.max(esp * 2.2, ctx.px(0.028));
    let base = Math.max(esp * 7, ctx.px(0.1));
    const quadro = ctx.el('div', 'moldura-polaroid');
    const w = jan.w, h = jan.h;
    // o retângulo pedido é o papel inteiro; a janela fica dentro
    Object.assign(quadro.style, { position: 'absolute', left: jan.x + 'px', top: jan.y + 'px', width: w + 'px', height: h + 'px', boxSizing: 'border-box',
      borderStyle: 'solid', borderColor: cor, borderWidth: `${lado}px ${lado}px ${base}px ${lado}px`, borderRadius: raio + 'px',
      boxShadow: `0 ${ctx.px(0.008).toFixed(1)}px ${ctx.px(0.03).toFixed(1)}px ${ctx.alfa('fundo', 0.45)}`, transformOrigin: 'center center' });
    const legenda = ctx.el('div', 'moldura-legenda');
    Object.assign(legenda.style, { position: 'absolute', left: '0', right: '0', bottom: -base + 'px', height: base + 'px', display: 'flex', alignItems: 'center',
      justifyContent: 'space-between', padding: `0 ${(lado * 0.4).toFixed(1)}px` });
    const dentro = Math.max(8, w - 2 * lado - 2 * lado * 0.4);   // largura da base do papel, menos o respiro lateral
    const r = p.rotulo ? apoio('subtitulo', p.rotulo, Math.min(base * 0.42, ctx.tam('h3')), 'fundo', dentro) : null;
    const s = p.sub ? apoio('dados', p.sub, Math.min(base * 0.26, tamRot), 'fundo', dentro) : null;
    if (r) { legenda.appendChild(r); partes.rotulo = r; }
    if (s) { s._inner.style.opacity = '0.75'; legenda.appendChild(s); partes.sub = s; }
    quadro.appendChild(legenda);
    raiz.appendChild(quadro); partes.polaroid = quadro;
    if (!cabemLadoALado(ctx, r, s, dentro, lado * 0.8, minLeg)) {
      // não cabem lado a lado: sub sob o rótulo, cada um em até 2 linhas; a base do papel cresce se precisar
      const vaoY = base * 0.06;
      Object.assign(legenda.style, { flexDirection: 'column', alignItems: 'flex-start', justifyContent: 'center', gap: vaoY + 'px' });
      for (const e of [r, s]) if (e) caberEmpilhado(ctx, e, dentro, minLeg);
      base = Math.max(base, Math.ceil((r ? r.offsetHeight : 0) + (s ? s.offsetHeight : 0) + (r && s ? vaoY : 0) + lado * 0.6));
      empilhado = !!(r && s);
      quadro.style.borderWidth = `${lado}px ${lado}px ${base}px ${lado}px`;
      Object.assign(legenda.style, { bottom: -base + 'px', height: base + 'px' });
    }
    jan = { x: jan.x + lado, y: jan.y + lado, w: w - 2 * lado, h: h - lado - base };
  }

  // rótulo e sub para os estilos sem cabeçalho próprio: presos à moldura, mas nunca fora da zona segura da plataforma
  // (no vertical, o topo e a lateral direita do quadro ficam sob a interface dos apps)
  if (estilo === 'borda' || estilo === 'cantoneiras' || estilo === 'nenhuma') {
    const gc = ctx.DA.graficos.gc;
    const recuo = estilo === 'cantoneiras' ? Math.max(esp * 6, ctx.px(0.055)) * 0.45 + padChip * 1.8 : esp + padChip * 1.4;
    const topo = Math.max(jan.y + recuo, livre.y);
    const xa = Math.max(jan.x + recuo, zona.x), xb = Math.min(jan.x + jan.w - recuo, zona.x1);
    const larg = Math.max(8, xb - xa);                         // o que sobra entre a moldura e a zona segura
    const corRot = ctx.contraste(cfg.cor, gc.cor_fundo) >= 3 ? cfg.cor : ctx.legivel(gc.cor_fundo, gc.cor_nome, 'texto');
    const fundoChip = ctx.alfa(gc.cor_fundo, gc.alfa_fundo);
    const r = p.rotulo ? chip(p.rotulo, corRot, fundoChip, larg - 2 * padChip) : null;
    const s = p.sub ? chip(p.sub, ctx.contraste('texto_suave', gc.cor_fundo) >= 3 ? 'texto_suave' : corRot, fundoChip, larg - 2 * padChip) : null;
    for (const [k, e] of [['rotulo', r], ['sub', s]]) if (e) { e.style.position = 'absolute'; raiz.appendChild(e); partes[k] = e; }
    const lado = cabemLadoALado(ctx, r, s, larg, padChip * 2, minLeg);
    if (!lado) for (const e of [r, s]) if (e) caberEmpilhado(ctx, e, larg, minLeg);
    if (r) Object.assign(r.style, { left: xa + 'px', top: topo + 'px' });
    if (s && (lado || !r)) Object.assign(s.style, { left: (xb - s.offsetWidth) + 'px', top: topo + 'px' });       // lado a lado (ou sozinho): à direita
    else if (s) Object.assign(s.style, { left: xa + 'px', top: (topo + r.offsetHeight + padChip * 0.6) + 'px' });  // empilhado: sob o rótulo
    empilhado = !lado && !!(r && s);
  }
  for (const k of ['rotulo', 'sub']) if (partes[k]) ctx.medir(partes[k]);
  if (estilo === 'polaroid' && inclin) raiz.style.transform = `rotate(${inclin}deg)`;     // só depois de medir: o giro não entra na conta
  const retRotulo = partes.rotulo ? ctx.rectDe(partes.rotulo) : null, retSub = partes.sub ? ctx.rectDe(partes.sub) : null;
  // na zona de verdade: os retângulos REAIS de rótulo e sub (já girados, na polaroid) dentro da zona segura
  const dentroDaZona = (q) => !q || (q.x >= zona.x - 0.5 && q.y >= zona.y - 0.5 && q.x1 <= zona.x1 + 0.5 && q.y1 <= zona.y1 + 0.5);
  const naZona = dentroDaZona(retRotulo) && dentroDaZona(retSub);
  const tamanhos = { rotulo: partes.rotulo ? +partes.rotulo._tam.toFixed(2) : null, sub: partes.sub ? +partes.sub._tam.toFixed(2) : null };
  raiz.remove();

  const T = ctx.tl();
  const d = ctx.dur('media');
  if (estilo === 'borda') T.escalonar(['topo', 'direita', 'base', 'esquerda'], 0, d * 0.7, { passo: d * 0.18, curva: 'suave' });
  else if (estilo === 'cantoneiras') { T.escalonar(['tl', 'tr', 'bl', 'br'], 0, d, { passo: ctx.escalonamento * 0.6 }); T.add('linha', ctx.escalonamento, d, { curva: 'suave' }); }
  else if (estilo === 'janela') T.add('janela', 0, d);
  else if (estilo === 'polaroid') T.add('polaroid', 0, ctx.dur('longa'));
  const tRot = Math.max(T.fim * 0.45, ctx.escalonamento * 3);
  if (partes.rotulo) T.add('rotulo', tRot, d);
  if (partes.sub) T.add('sub', tRot + ctx.escalonamento, d);
  const inicioSaida = ctx.fim_saida();
  // janela já girada (polaroid inclinada): a raiz gira em torno do centro do QUADRO; devolve o centro e os 4 cantos
  // da janela depois do giro, para quem encaixa o insert (video.encaixar_em_janela) não deixar cunhas nos cantos
  const rad = inclin * Math.PI / 180, cx0 = L / 2, cy0 = A / 2;
  const gira = (x, y) => [cx0 + (x - cx0) * Math.cos(rad) - (y - cy0) * Math.sin(rad), cy0 + (x - cx0) * Math.sin(rad) + (y - cy0) * Math.cos(rad)];
  const cantos = [[jan.x, jan.y], [jan.x + jan.w, jan.y], [jan.x + jan.w, jan.y + jan.h], [jan.x, jan.y + jan.h]].map(([x, y]) => gira(x, y).map((v) => +v.toFixed(2)));
  const centro = gira(jan.x + jan.w / 2, jan.y + jan.h / 2).map((v) => +v.toFixed(2));
  const layout = { estilo, janela: { x: Math.round(jan.x), y: Math.round(jan.y), w: Math.round(jan.w), h: Math.round(jan.h) }, inclinacao: inclin,
    janela_girada: { cx: centro[0], cy: centro[1], w: Math.round(jan.w), h: Math.round(jan.h), angulo: inclin, cantos },
    zona: { x: zona.x, y: zona.y, x1: zona.x1, y1: zona.y1, plataforma: zona.plataforma }, rotulo_na_zona: naZona, rotulo: retRotulo, sub: retSub,
    rotulo_empilhado: empilhado, tamanho_rotulo: tamanhos.rotulo, tamanho_sub: tamanhos.sub, minimo_legivel: +minLeg.toFixed(2),
    fim_entrada: +T.fim.toFixed(3), inicio_saida: +inicioSaida.toFixed(3) };
  const S = { ctx, estilo, raiz, partes, T, inicioSaida, fimEntrada: T.fim };
  return { el: raiz, layout, partes, seek: (t) => seekMoldura(S, t), key: (t) => (t >= S.fimEntrada + 0.05 && t < S.inicioSaida ? 'estatico' : null),
    ancoras: () => [{ t: 0, nome: 'entrada', tipo: 'entrada' }, { t: +S.inicioSaida.toFixed(3), nome: 'saida', tipo: 'saida' }] };
}

function seekMoldura(S, t) {
  const { ctx, estilo, raiz, partes, T, inicioSaida } = S;
  // Função pura de t: as partes recebem sempre o estado de entrada para este t; a saída é só a opacidade da raiz.
  raiz.style.opacity = t >= inicioSaida ? (1 - ctx.prog(t, inicioSaida, ctx.dur('curta'), 'saida')).toFixed(3) : '1';
  if (estilo === 'borda') {
    for (const n of ['topo', 'direita', 'base', 'esquerda']) {
      const p = T.p(t, n);
      partes[n].style.transform = `${partes[n]._eixo}(${p.toFixed(4)})`;
      partes[n].style.opacity = p > 0 ? '1' : '0';
    }
  } else if (estilo === 'cantoneiras') {
    for (const n of ['tl', 'tr', 'bl', 'br']) {
      const c = partes[n], p = T.p(t, n);
      c.style.opacity = p.toFixed(3);
      c.style.transform = `translate(${(c._dx * (1 - p)).toFixed(2)}px, ${(c._dy * (1 - p)).toFixed(2)}px)`;
    }
    const pl = T.p(t, 'linha');
    partes.linha.style.transform = `scaleX(${pl.toFixed(4)})`;
    partes.linha.style.opacity = pl > 0 ? '1' : '0';
  } else if (estilo === 'janela') {
    const p = T.p(t, 'janela');
    partes.janela.style.opacity = p.toFixed(3);
    partes.janela.style.transform = `scale(${(0.985 + 0.015 * p).toFixed(4)})`;
  } else if (estilo === 'polaroid') {
    const p = T.p(t, 'polaroid');
    partes.polaroid.style.opacity = p.toFixed(3);
    partes.polaroid.style.transform = `translateY(${(ctx.px(0.03) * (1 - p)).toFixed(2)}px) scale(${(0.97 + 0.03 * p).toFixed(4)})`;
  }
  if (partes.rotulo) ctx.entrada(partes.rotulo, T.p(t, 'rotulo'), 'desce', { dist: ctx.px(0.012) });
  if (partes.sub) ctx.entrada(partes.sub, T.p(t, 'sub'), 'fade');
}
