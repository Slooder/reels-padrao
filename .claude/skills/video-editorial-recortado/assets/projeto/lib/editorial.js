// editorial.js — estilo "editorial recortado": papel quase branco, recortes P&B com borda azul cortada a tesoura,
// título serifado com sublinhado de pincel, palavras que sobem e etiquetas coral que se montam palavra a palavra.
// Tudo é função de t (onTick). Funções que medem texto (ED.etiqueta, ED.titulo) vão no SETUP, depois das fontes.
(function () {
  const ED = (window.ED = {});
  let uid = 0;
  const css = document.createElement('style');
  css.textContent = `
:root{--ed-tinta:#2a2a2a;--ed-azul:#5b7ba3;--ed-azul-escuro:#2f4560;--ed-coral:#e0646b;--ed-pontos:#c9c9c9;--ed-serif:'Lora',Georgia,serif}
.ed-papel{position:absolute;left:-80px;top:-142px;width:1240px;height:2204px;max-width:none}
.ed-txt{position:absolute;font-family:var(--ed-serif);font-weight:700;color:var(--ed-tinta);white-space:nowrap;line-height:1.18}
.ed-w{display:inline-block;opacity:0;will-change:transform}
.ed-ret{position:absolute;pointer-events:none}
.ed-peca{position:absolute;display:block;max-width:none;transform-origin:50% 100%}
.ed-rot{position:absolute;font-family:var(--ed-serif);font-weight:700;white-space:pre}
.ed-rot .bar{position:absolute;left:0;top:0;background:var(--ed-coral)}
.ed-rot .w{position:absolute;top:0;opacity:0;color:var(--ed-tinta)}
.ed-cred{position:absolute;left:30px;right:30px;bottom:18px;text-align:center;font:500 15px/1.35 'Inter Tight',sans-serif;opacity:0;text-shadow:0 1px 2px rgba(0,0,0,.9),0 0 6px rgba(0,0,0,.7)}`;
  document.head.appendChild(css);

  const el = (tag, cls, parent, style = '') => { const e = document.createElement(tag); if (cls) e.className = cls; if (style) e.style.cssText = style; if (parent) parent.appendChild(e); return e; };
  // som sem "flam": dois efeitos IGUAIS a menos de 60 ms viram um só estalo estranho → empurra o segundo uns quadros
  const usados = {};
  ED.som = (tipo, t, o = {}) => {
    const u = (usados[tipo] = usados[tipo] || []); let tt = t;
    while (u.some(x => Math.abs(x - tt) < 0.06)) tt += 0.034;
    u.push(tt); return cue(tipo, tt, o);
  };
  const vx = (x) => K.clamp((x / VIDEO.w) * 2 - 1, -1, 1) * 0.5;   // pan do som pela posição na tela

  // ── fundo de papel (textura de tools/editorial.py papel; 114,8% do quadro com folga p/ câmera)
  ED.papel = (parent, src) => { const i = el('img', 'ed-papel', parent); i.src = src; return i; };

  // ── recorte (PNG de tools/editorial.py recorte) posicionado por largura
  ED.peca = (parent, src, { x = 0, y = 0, w = 600, z = 1, id } = {}) => {
    const i = el('img', 'ed-peca', parent, `left:${x}px;top:${y}px;width:${w}px;z-index:${z}`); i.src = src; if (id) i.id = id; return i;
  };

  // ── retícula de bolinhas cinza que aparece em degraus da esquerda p/ a direita
  ED.reticula = (parent, { x, y, w, h, passo = 26, raio = 7, cor, t0 = 0, d = 0.35, degraus = 7, dir = 'l' } = {}) => {
    const c = cor || 'var(--ed-pontos)', g = `radial-gradient(circle,${c} ${raio}px,transparent ${raio + 1}px)`;
    const e = el('div', 'ed-ret', parent, `left:${x}px;top:${y}px;width:${w}px;height:${h}px;` +
      `background:${g} ${passo / 2}px ${passo / 2}px/${passo * 2}px ${passo * 2}px,${g} ${passo * 1.5}px ${passo * 1.5}px/${passo * 2}px ${passo * 2}px`);
    onTick(t => {
      const k = Math.floor(K.seg(t, t0, t0 + d) * degraus) / degraus;
      e.style.clipPath = dir === 'l' ? `inset(0 ${(1 - k) * 100}% 0 0)` : `inset(0 0 0 ${(1 - k) * 100}%)`;
      e.style.visibility = k > 0 ? 'visible' : 'hidden';
    });
    return e;
  };

  // ── separa um texto em palavras (inline-block) para animar
  ED.palavras = (alvo, txt) => { alvo.innerHTML = txt.split(' ').map(w => `<span class="ed-w">${w}</span>`).join(' '); return [...alvo.querySelectorAll('.ed-w')]; };

  // ── palavras que aparecem ½ linha abaixo e sobem até a linha (subtítulo da referência)
  ED.sobe = (spans, t0, { passo = 0.22, d = 0.38, dy = 0.6, ease = 'power3.out', som = 'tick', gain = -2 } = {}) => {
    const fs = parseFloat(getComputedStyle(spans[0]).fontSize);
    const ez = gsap.parseEase(ease);
    spans.forEach((s, i) => { if (som) ED.som(som, t0 + i * passo, { gain, pan: (i % 2 ? 0.25 : -0.25) }); });
    onTick(t => spans.forEach((s, i) => {
      const ti = t0 + i * passo;
      s.style.opacity = t >= ti ? 1 : 0;
      s.style.transform = `translateY(${(dy * fs * (1 - ez(K.seg(t, ti, ti + d)))).toFixed(2)}px)`;
    }));
    return t0 + (spans.length - 1) * passo + d;
  };

  // ── sublinhado de pincel azul (fino à esquerda, termina redondo à direita), desenhado da esquerda p/ a direita
  ED.sublinhado = (parent, { x, y, w, h = 16, t0 = 0, d = 0.5, ease = 'power2.out', cor, escuro, seed = 3, som = 'marker' } = {}) => {
    const id = 'edsl' + uid++, H = h * 2.2, a = cor || 'var(--ed-azul)', b = escuro || 'var(--ed-azul-escuro)';
    const r = h * 0.48, cy = H / 2;
    const body = `M0 ${cy + h * .12} C${w * .25} ${cy - h * .05},${w * .6} ${cy - h * .42},${w - r} ${cy - h * .46}` +
      ` A${r} ${r * 1.02} 0 0 1 ${w - r} ${cy + h * .5} C${w * .62} ${cy + h * .42},${w * .3} ${cy + h * .25},0 ${cy + h * .22}Z`;
    const core = `M${w * .03} ${cy + h * .1} C${w * .3} ${cy - h * .02},${w * .65} ${cy - h * .14},${w - r * 1.4} ${cy - h * .12}`;
    const s = el('div', '', parent, `position:absolute;left:${x}px;top:${y - H / 2}px;width:${w}px;height:${H}px;overflow:visible`);
    s.innerHTML = `<svg width="${w}" height="${H}" viewBox="0 0 ${w} ${H}" style="overflow:visible">
      <defs><filter id="${id}f" filterUnits="userSpaceOnUse" x="-40" y="-40" width="${w + 80}" height="${H + 80}">
        <feTurbulence type="fractalNoise" baseFrequency=".035 .22" numOctaves="2" seed="${seed}"/><feDisplacementMap in="SourceGraphic" scale="${Math.max(2, h * .16)}"/></filter>
        <clipPath id="${id}c"><rect id="${id}r" x="-20" y="-40" width="0" height="${H + 80}"/></clipPath></defs>
      <g clip-path="url(#${id}c)"><g filter="url(#${id}f)"><path d="${body}" fill="${a}"/>
      <path d="${core}" fill="none" stroke="${b}" stroke-width="${h * .2}" stroke-linecap="round" opacity=".75"/></g></g></svg>`;
    const rect = s.querySelector('#' + id + 'r'), ez = gsap.parseEase(ease);
    if (som) ED.som(som, t0, { gain: -3 });
    onTick(t => rect.setAttribute('width', ((w + 40) * ez(K.seg(t, t0, t0 + d))).toFixed(1)));
    return s;
  };

  // ── título serifado centralizado (cabe em maxw); devolve {el, palavras, larg, x0, fs}. Chame no SETUP.
  //    O sublinhado vai DENTRO de el (fica atrás das letras): ED.sublinhado(tit.el, {x: tit.x0 - fs*.15, y: fs, w: tit.larg + fs*.6, …})
  ED.titulo = (parent, txt, { y, fs = 86, maxw = VIDEO.w - 120, peso = 700 } = {}) => {
    const box = el('div', 'ed-txt', parent, `left:0;width:${VIDEO.w}px;top:${y}px;text-align:center;font-size:${fs}px;font-weight:${peso};z-index:5`);
    const linha = el('span', '', box, 'display:inline-block;position:relative;z-index:1');
    const ws = ED.palavras(linha, txt);
    let w = linha.offsetWidth;
    if (w > maxw) { box.style.fontSize = (fs * maxw / w).toFixed(1) + 'px'; w = linha.offsetWidth; }
    return { el: box, palavras: ws, larg: w, x0: (VIDEO.w - w) / 2, fs: parseFloat(box.style.fontSize) };
  };

  // ── etiqueta coral que se monta: traço → faixa que cresce; palavras pretas espalhadas meia linha acima/abaixo
  //    aparecem secas em ordem aleatória e pulam, em ordem de leitura, para dentro da faixa (ficam brancas). Chame no SETUP.
  ED.etiqueta = (parent, { texto, x, y, t0, fs = 42, pad = 0.34, seed = 1, passoA = 0.066, passoS = 0.1, cresce, som = true, alinhar = 'esq' } = {}) => {
    const H = Math.round(fs * 1.42), P = Math.round(fs * pad);
    const box = el('div', 'ed-rot', parent, `left:${x}px;top:${y}px;font-size:${fs}px;line-height:${H}px;height:${H}px`);
    const bar = el('div', 'bar', box, `height:${H}px;width:0`);
    // mede a posição de cada palavra na linha final
    const med = el('div', '', box, `position:absolute;left:${P}px;top:0;visibility:hidden;white-space:pre`);
    const pal = texto.split(' ');
    med.innerHTML = pal.map(p => `<span>${p}</span>`).join(' ');
    const sp = [...med.children], pos = sp.map(s => ({ x: s.offsetLeft + P, w: s.offsetWidth }));
    const W = Math.ceil(med.offsetWidth + 2 * P); med.remove();
    if (alinhar === 'dir') box.style.left = (x - W) + 'px';
    const r = K.rng(seed * 977 + 13), n = pal.length;
    const ws = pal.map((p, i) => {
      const s = el('span', 'w', box, `left:${pos[i].x}px`); s.textContent = p;
      const lado = ((i + (seed % 2)) % 2 ? -1 : 1) * (r() < .15 ? -1 : 1);
      return { s, dx: (r() - .5) * fs * 0.9, dy: lado * H * (0.9 + r() * 0.3), ta: 0, ts: 0, fim: pos[i].x + pos[i].w + P };
    });
    // ordem aleatória de aparecer; ordem de leitura para pular
    const ordem = [...ws.keys()].sort(() => r() - .5);
    ordem.forEach((i, k) => (ws[i].ta = t0 + 0.07 + k * passoA));
    let tp = t0 + 0.07 + n * passoA * 0.55 + 0.1;
    ws.forEach(w => { tp = Math.max(tp, w.ta + 0.12); w.ts = tp; tp += passoS; });
    const dCresce = cresce ?? Math.min(0.75, 0.22 + texto.length * 0.016), ez = gsap.parseEase('power2.out');
    if (som) {
      const pan = vx(x + W / 2);
      ED.som('swoosh', t0 + 0.02, { gain: -11, pan });
      ws.forEach(w => { ED.som('focus_tick', w.ta, { gain: 2, pan }); ED.som('key', w.ts, { gain: -5, pan }); });
    }
    onTick(t => {
      if (t < t0) { bar.style.width = '0px'; ws.forEach(w => (w.s.style.opacity = 0)); return; }
      let ext = 0;
      ws.forEach(w => {
        const dentro = t >= w.ts;
        if (dentro) ext = Math.max(ext, w.fim);
        w.s.style.opacity = t >= w.ta ? 1 : 0;
        w.s.style.color = dentro ? '#fff' : 'var(--ed-tinta)';
        w.s.style.transform = dentro ? 'none' : `translate(${w.dx.toFixed(1)}px,${w.dy.toFixed(1)}px)`;
      });
      const g = t < t0 + 0.05 ? 3 : 3 + (W - 3) * ez(K.seg(t, t0 + 0.05, t0 + 0.05 + dCresce));
      bar.style.width = Math.max(g, ext).toFixed(1) + 'px';
    });
    return { el: box, w: W, h: H, fim: ws[n - 1].ts + 0.05 };
  };

  // ── empurrão lento (câmera quase parada da referência)
  ED.empurra = (alvo, { t0 = 0, t1 = VIDEO.dur, de = 1, para = 1.03, dy = 0, ease = 'sine.inOut', origem = '50% 100%' } = {}) => {
    alvo.style.transformOrigin = origem; const ez = gsap.parseEase(ease);
    onTick(t => { const k = ez(K.seg(t, t0, t1)); alvo.style.transform = `translateY(${(dy * k).toFixed(2)}px) scale(${K.lerp(de, para, k).toFixed(5)})`; });
  };

  // ── crédito das fotos no rodapé
  ED.credito = (parent, texto, { t0 = 0, d = 0.4, cor = 'rgba(255,255,255,.78)' } = {}) => {
    const c = el('div', 'ed-cred', parent, `color:${cor}`); c.textContent = texto;
    onTick(t => (c.style.opacity = K.seg(t, t0, t0 + d)));
    return c;
  };
})();
