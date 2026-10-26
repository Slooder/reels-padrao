// texto-grifado — biblioteca do estilo (global GR).
// Parágrafo serifado escrito palavra a palavra, marca-texto amarelo que sangra da borda da tela,
// bloco vermelho que vira o texto em branco, e a abertura de colagem editorial (recorte P&B com
// contorno amarelo, retícula de bolinhas, título com sublinhado de pincel) que sai num chicote.
// Tudo é função do tempo: monte as peças dentro de window.SETUP (elas medem texto) e, no onTick, chame
// GR.aplicar(cam), GR.palavras(P, t) e o .tick(t, cam) de cada grifo — com t = GR.q(t) para os 12 qps da referência.
(function () {
  const GR = (window.GR = {});
  const W = () => VIDEO.w, H = () => VIDEO.h;

  GR.cor = { tinta: '#363636', amarelo: '#f9ce80', contorno: '#f3c069', vermelho: '#dd687a', ponto: '#c0c0c0', papel: '#fcfcfc', branco: '#ffffff' };
  // a referência anima a 12 qps (quadros repetidos aos pares). 0 = liso.
  GR.qps = 12;
  GR.q = t => (GR.qps ? Math.floor(t * GR.qps + 1e-6) / GR.qps : t);

  // ───────── mundo + câmera ─────────
  // Um plano só: a abertura e o parágrafo vivem no mesmo "papel" (#mundo); a câmera anda por ele.
  // cam = {x, y, z}: ponto do mundo que fica no centro da tela e o zoom.
  GR.mundo = (stage, o = {}) => {
    const m = K.html(stage, `<div class="gr-mundo abs" style="left:0;top:0;width:${o.w ?? 3000}px;height:${o.h ?? 2400}px;transform-origin:0 0"></div>`);
    GR.el = m; GR.cam = { x: W() / 2, y: H() / 2, z: 1 }; return m;
  };
  GR.aplicar = cam => { GR.cam = cam; GR.el.style.transform = `translate(${W() / 2 - cam.x * cam.z}px,${H() / 2 - cam.y * cam.z}px) scale(${cam.z})`; };
  GR.telaEsq = (cam = GR.cam) => cam.x - W() / 2 / cam.z;          // borda esquerda da tela, em coordenadas do mundo
  GR.telaDir = (cam = GR.cam) => cam.x + W() / 2 / cam.z;

  // papel de fundo (img gerada por tools/grifado.py papel), posicionado no mundo
  GR.papel = (src, o = {}) => K.html(GR.el, `<img class="gr-papel abs" src="${src}" style="left:${o.x ?? -150}px;top:${o.y ?? -240}px;width:${o.w ?? 2900}px;height:${o.h ?? 2400}px">`);

  // ───────── retícula de bolinhas (grade alternada, borda irregular) ─────────
  // passo ≈ 30 px a 1080 de largura; bolinha = 45% do passo; cor #c0c0c0.
  GR.pontos = (o = {}) => {
    const w = o.w ?? 360, h = o.h ?? 320, p = o.passo ?? 30, r = (o.raio ?? .225) * p, seed = o.seed ?? 1, bd = o.borda ?? 1.6;
    const c = K.html(GR.el, `<canvas class="gr-pontos abs" width="${w}" height="${h}" style="left:${o.x}px;top:${o.y}px;width:${w}px;height:${h}px"></canvas>`);
    const x = c.getContext('2d'); x.fillStyle = o.cor ?? GR.cor.ponto;
    for (let j = 0, y = r + 1; y < h - r; j++, y += p * .866) {
      for (let px = r + 1 + (j % 2) * p / 2; px < w - r; px += p) {
        // distância à borda em passos + ruído = borda roída, sem círculos cortados
        const d = Math.min(px, w - px, y, h - y) / p;
        if (d + K.noise(px / p * .55 + seed * 7.1, y / p * .55 - seed * 3.3) * 2.2 < bd) continue;
        x.beginPath(); x.arc(px, y, r, 0, Math.PI * 2); x.fill();
      }
    }
    return c;
  };

  // ───────── recorte (PNG de tools/grifado.py recorte) ─────────
  GR.recorte = (src, o = {}) => K.html(GR.el, `<img class="gr-recorte abs" src="${src}" style="left:${o.x}px;top:${o.y}px;width:${o.w}px">`);

  // ───────── sublinhado de pincel (traço afinado, levemente curvo, com gancho no fim) ─────────
  GR.pincel = (o = {}) => {
    const x0 = o.x0, x1 = o.x1, y = o.y, e = o.esp ?? 10, r = K.rng(o.seed ?? 5), n = 40, L = x1 - x0;
    const cy = u => y + (o.arco ?? 4) * (1 - u) - (o.arco ?? 4) * 1.4 * u * u + (r() - .5) * .6;     // sobe um pouco para a direita
    const th = u => e * Math.max(.18, Math.pow(Math.sin(Math.PI * Math.min(1, u * 1.08)), .45)) * (u < .1 ? .55 + 4.5 * u : 1);
    const top = [], bot = [];
    for (let i = 0; i <= n; i++) { const u = i / n, X = x0 + L * u, Y = cy(u), t = th(u); top.push([X, Y - t * .5]); bot.push([X, Y + t * .5]); }
    const g = o.gancho ?? 1;   // gancho: o pincel desce de volta no fim
    const hk = [[x1 + e * .6 * g, cy(1) - e * .2], [x1 + e * .2 * g, cy(1) + e * .7 * g], [x1 - e * 1.6 * g, cy(1) + e * .55 * g]];
    const pts = top.concat(hk, bot.reverse());
    const d = 'M' + pts.map(p => p[0].toFixed(1) + ',' + p[1].toFixed(1)).join(' L') + ' Z';
    const pad = 40, bx = x0 - pad, by = y - pad;
    return K.html(GR.el, `<svg class="gr-pincel abs" style="left:${bx}px;top:${by}px;overflow:visible" width="${L + 2 * pad}" height="${2 * pad}"><path d="${d}" transform="translate(${-bx},${-by})" fill="${o.cor ?? GR.cor.contorno}"/></svg>`);
  };

  // ───────── texto ─────────
  const fonte = (fs, lh, peso = 700) => `font-family:Lora,serif;font-weight:${peso};font-size:${fs}px;line-height:${lh}px;color:${GR.cor.tinta};white-space:nowrap`;
  // título de uma linha centralizado em cx; y = topo da caixa da linha. Com sublinhado de pincel.
  GR.titulo = (txt, o = {}) => {
    const fs = o.fs ?? 74, lh = Math.round(fs * 1.3);
    const el = K.html(GR.el, `<div class="gr-titulo abs" style="${fonte(fs, lh)};left:0;top:${o.y}px">${txt}</div>`);
    const w = el.offsetWidth; el.style.left = (o.cx - w / 2) + 'px';
    const sub = o.sublinhado === false ? null : GR.pincel(Object.assign({ x0: o.cx - w / 2 - fs * .32, x1: o.cx + w / 2 + fs * .18, y: o.y + lh * .93, esp: fs * .14 }, o.sublinhado || {}));
    if (sub) el.before(sub);
    return { el, sub, w };
  };
  // rótulo de 2+ linhas em escada (cada linha recua `recuo` px). Não desenha grifo: devolve em `faixa(i)` o retângulo
  // (mundo) da linha i para o GR.marca — o mesmo marca-texto que depois atravessa o parágrafo.
  GR.rotulo = (linhas, o = {}) => {
    const fs = o.fs ?? 66, lh = o.lh ?? Math.round(fs * 1.36), sobe = o.passo ?? lh * .92;
    const box = K.html(GR.el, `<div class="gr-rotulo abs" style="left:${o.x}px;top:${o.y}px;z-index:3"></div>`);
    const els = linhas.map((s, i) => K.html(box, `<div class="abs" style="${fonte(fs, lh)};left:${i * (o.recuo ?? fs * 1.1)}px;top:${i * sobe}px">${s}</div>`));
    const faixa = (i, f = {}) => { const e = els[i]; const yc = o.y + e.offsetTop + lh / 2, h = lh * (f.alt ?? .95);
      return { x0: o.x + e.offsetLeft - fs * (f.antes ?? 1.4), x1: o.x + e.offsetLeft + e.offsetWidth + fs * (f.depois ?? .12), y0: yc - h / 2, y1: yc + h / 2 }; };
    return { box, els, faixa, lh, sobe };
  };

  // parágrafo centralizado em (cx, cy), uma linha por item; cada palavra vira um <span> animável.
  GR.paragrafo = (linhas, o = {}) => {
    const fs = o.fs ?? 66, lh = Math.round(fs * (o.entre ?? 1.36)), largura = o.largura ?? 1600;
    const el = K.html(GR.el, `<div class="gr-par abs" style="${fonte(fs, lh)};left:${o.cx - largura / 2}px;top:${o.cy - linhas.length * lh / 2}px;width:${largura}px;text-align:center;z-index:3"></div>`);
    const words = [];
    linhas.forEach((ln, li) => {
      const d = K.html(el, `<div class="gr-ln" style="height:${lh}px"></div>`);
      ln.split(' ').forEach((s, wi) => {
        if (wi) d.appendChild(document.createTextNode(' '));
        const sp = document.createElement('span'); sp.className = 'gr-w'; sp.textContent = s; sp.style.display = 'inline-block'; d.appendChild(sp);
        words.push({ el: sp, txt: s, linha: li, i: wi });
      });
    });
    const P = { el, words, fs, lh, linhas, cx: o.cx, cy: o.cy };
    P.medir = () => { words.forEach(w => Object.assign(w, K.pos(w.el, GR.el))); P.y0 = el.offsetTop; return P; };
    // retângulo (mundo) das palavras [de..ate] de uma linha, com folga; altura = entrelinha × alt
    P.faixa = (linha, de = 0, ate = 1e9, f = {}) => {
      const ws = words.filter(w => w.linha === linha && w.i >= de && w.i <= ate);
      const x0 = Math.min(...ws.map(w => w.x)) - fs * (f.antes ?? .12), x1 = Math.max(...ws.map(w => w.x + w.w)) + fs * (f.depois ?? .14);
      const yc = P.y0 + linha * lh + lh * (f.meio ?? .5), h = lh * (f.alt ?? .95);
      return { x0, x1, y0: yc - h / 2, y1: yc + h / 2, ws };
    };
    return P.medir();
  };

  // escreve palavra a palavra: cada uma surge opaca `sobe`·fs abaixo da linha e sobe em `dur` s.
  // ritmo: `pps` palavras/s em média, palavras longas demoram mais, pausa depois de vírgula/ponto.
  GR.escrever = (P, t0, o = {}) => {
    const pps = o.pps ?? 10.5, sobe = o.sobe ?? .8, dur = o.dur ?? .25, ease = o.ease ?? 'power2.out';
    let t = t0; const base = 1 / pps;
    P.words.forEach((w, k) => {
      w.t = t;
      const L = w.txt.length; let d = base * (.62 + .055 * L);
      if (/[,;:]$/.test(w.txt)) d += base * .7; if (/[.!?]$/.test(w.txt)) d += base * 1.1;
      if (k < P.words.length - 1 && P.words[k + 1].linha !== w.linha) d += base * .25;
      t += d;
      if (o.som !== false) cue(o.somTipo ?? 'lapis', w.t, { gain: (o.somGain ?? 0) + ((k * 7) % 5 - 2) * .8, pan: ((k * 3) % 5 - 2) * .08 });
    });
    P.fim = t; P._sobe = sobe * P.fs; P._dur = dur; P._ease = gsap.parseEase(ease);
    return t;
  };
  GR.palavras = (P, t) => {
    for (const w of P.words) {
      if (t < w.t) { w.el.style.visibility = 'hidden'; continue; }
      w.el.style.visibility = 'visible';
      const u = K.clamp((t - w.t) / P._dur); w.el.style.transform = u >= 1 ? 'none' : `translate3d(0,${(P._sobe * (1 - P._ease(u))).toFixed(2)}px,0)`;
    }
  };

  // câmera que persegue o centro das palavras já escritas, com atraso de 1ª ordem (tau s).
  // Pré-calcula a 120 Hz para ser função pura de t.
  // cursor (0–1): quanto o alvo puxa para a última palavra escrita (a câmera "lê" junto, balançando de leve por linha).
  GR.seguir = (P, o = {}) => {
    const tau = o.tau ?? .32, cur = o.cursor ?? .25, dt = 1 / 120, n = Math.ceil(VIDEO.dur / dt) + 2, xs = new Float32Array(n);
    const alvo = t => {
      let a = 1e9, b = -1e9, u = null;
      for (const w of P.words) if (w.t <= t) { a = Math.min(a, w.x); b = Math.max(b, w.x + w.w); u = w; }
      if (!u) return P.words[0].x + P.words[0].w / 2;
      const c = (a + b) / 2; return c + cur * (u.x + u.w / 2 - c);
    };
    let s = alvo(0); const k = 1 - Math.exp(-dt / tau);
    for (let i = 0; i < n; i++) { s += (alvo(i * dt) - s) * k; xs[i] = s; }
    return t => { const f = K.clamp(t / dt, 0, n - 1.001), i = Math.floor(f); return xs[i] + (xs[i + 1] - xs[i]) * (f - i); };
  };

  // chicote da referência: aceleração longa (u^2,6) e freada curta (power3.out) com a velocidade casada no ponto de corte.
  GR.chicote = (u, o = {}) => {
    u = K.clamp(u); const c = o.corte ?? .82, p = o.p ?? 2.6, k = 3, Y = (k / (1 - c)) / (p / c + k / (1 - c));
    return u < c ? Y * Math.pow(u / c, p) : Y + (1 - Y) * (1 - Math.pow(1 - (u - c) / (1 - c), k));
  };

  // ───────── marca-texto amarelo: do rótulo da abertura até o verso 1 ─────────
  // Uma barra só, na altura comum do rótulo (linha grifada) e do verso 1 do parágrafo:
  //  1. [a0,a1] cresce atrás da palavra do rótulo (a = faixa do rótulo);
  //  2. durante o chicote a ponta esquerda fica presa ao mundo até bater na borda da tela — aí gruda na borda;
  //     a ponta direita desliza do rótulo até o começo do verso, mas nunca fica menor que um toco (`toco` da largura);
  //  3. [b0,b1] a ponta direita percorre o verso (b = faixa do verso).
  GR.marca = (a, b, o = {}) => {
    const el = K.html(GR.el, `<div class="gr-grifo abs" style="top:${b.y0}px;height:${b.y1 - b.y0}px;background:${o.cor ?? GR.cor.amarelo};z-index:2"></div>`);
    const toco = o.toco ?? .2, ease = gsap.parseEase(o.ease ?? 'none'), g = { el };
    g.tick = (t, cam) => {
      if (t < o.a0) { el.style.display = 'none'; return; }
      el.style.display = 'block';
      const esq = GR.telaEsq(cam), L = Math.max(a.x0, esq - 40);
      let R = K.lerp(a.x0, a.x1, K.seg(t, o.a0, o.a1));
      if (t > o.a1) R = Math.max(R, K.lerp(a.x1, b.x0, K.ease('power2.in', K.seg(t, o.a1, o.b0))), esq + toco * W() / cam.z);
      if (t > o.b0) R = Math.max(R, K.lerp(b.x0, b.x1, ease(K.seg(t, o.b0, o.b1))));
      el.style.left = L + 'px'; el.style.width = Math.max(0, R - L) + 'px';
    };
    if (o.som !== false) { cue('grifo', o.a0, { d: o.a1 - o.a0, gain: -2 }); cue('grifo', o.b0, { d: o.b1 - o.b0, gain: o.somGain ?? -4 }); }
    return g;
  };

  // ───────── bloco vermelho que cresce e deixa o texto branco ─────────
  // Bloco atrás das palavras + cópia branca da linha recortada pelo mesmo retângulo.
  GR.destaque = (P, f, o = {}) => {
    const blk = K.html(GR.el, `<div class="gr-destaque abs" style="left:${f.x0}px;top:${f.y0}px;height:${f.y1 - f.y0}px;width:0;background:${o.cor ?? GR.cor.vermelho};z-index:2"></div>`);
    const linha = P.el.children[f.ws[0].linha];
    const cp = K.html(GR.el, `<div class="gr-branco abs" style="${P.el.getAttribute('style')};z-index:4;color:${o.texto ?? GR.cor.branco};pointer-events:none"></div>`);
    cp.style.top = (P.y0 + f.ws[0].linha * P.lh) + 'px'; cp.appendChild(linha.cloneNode(true));
    cp.querySelectorAll('.gr-w').forEach(s => (s.style.visibility = 'visible', s.style.transform = 'none'));
    const ease = gsap.parseEase(o.ease ?? 'power2.inOut'), d = { blk, cp };
    const cpx = cp.offsetLeft, cpw = cp.offsetWidth;
    d.tick = t => {
      const u = ease(K.seg(t, o.t0, o.t0 + (o.dur ?? .95))), R = K.lerp(f.x0, f.x1, u);
      blk.style.width = Math.max(0, R - f.x0) + 'px'; blk.style.display = u > 0 ? 'block' : 'none';
      cp.style.display = u > 0 ? 'block' : 'none';
      cp.style.clipPath = `inset(0 ${Math.max(0, cpx + cpw - R)}px 0 ${f.x0 - cpx}px)`;
    };
    if (o.som !== false) cue('grifo', o.t0 + .04, { d: (o.dur ?? .95) * .85, gain: o.somGain ?? 0 });
    return d;
  };

  // crédito de foto: linha discreta no rodapé, presa à tela (fora do mundo)
  GR.credito = (stage, txt, o = {}) => K.html(stage, `<div class="gr-credito abs" style="left:0;right:0;bottom:${o.base ?? 46}px;text-align:center;font:400 ${o.fs ?? 24}px/1.3 Lora,serif;color:${o.cor ?? '#7d7a76'};opacity:0;z-index:20">${txt}</div>`);
})();
