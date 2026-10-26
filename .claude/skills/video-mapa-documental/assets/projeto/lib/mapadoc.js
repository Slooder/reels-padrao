// mapa-documental — biblioteca do estilo (global MD)
// Mapa de satélite escuro sobre papel cinza quadriculado, país que acende verde PISCANDO, bordas brancas
// com brilho, rios acesos, região vermelha translúcida de borda macia que se espalha, e anotações de
// documentário: etiquetas-pílula, cidades em verde, triângulo vermelho com texto black, chamadas com
// cotovelo cujo texto se "decodifica", retrato P&B em círculo e círculo tracejado que encolhe girando.
// Tudo é função de t: cada peça guarda seus tempos e é desenhada no onTick do mapa.
(function () {
  const MD = (window.MD = {});
  const D2R = Math.PI / 180;

  // ───────── tempo ─────────
  // acender piscando (medido na referência: liga/desliga irregular a 30 qps por ~0,4 s, sempre acende no 1º quadro)
  MD.pisca = (t, t0, d = 0.4, seed = 1, dim = 0.35) => {
    if (t < t0) return 0;
    if (t >= t0 + d) return 1;
    const f = Math.floor((t - t0) * 30);
    if (f === 0) return 1;
    const u = (t - t0) / d, r = K.rng(seed * 7919 + f * 131)(), lim = 0.3 + 0.6 * u;
    return r < lim ? 1 : r < lim + 0.22 ? dim : 0;
  };
  // apagar piscando (o inverso: some com 2–3 tremidas)
  MD.apaga = (t, t0, d = 0.3, seed = 2) => {
    if (t < t0) return 1;
    if (t >= t0 + d) return 0;
    const r = K.rng(seed * 7919 + Math.floor((t - t0) * 30) * 131)();
    return (1 - K.seg(t, t0, t0 + d)) * (r < 0.6 ? 1 : 0.3);
  };
  // valor suave entre dois tempos com ease do GSAP
  MD.vai = (t, t0, d, ease = 'power2.out') => K.ease(ease, K.seg(t, t0, t0 + d));

  // câmera por quadros-chave: [{t, lon, lat, z(px por grau), ease}] — zoom interpolado em log (mergulho uniforme)
  MD.camera = keys => t => {
    if (t <= keys[0].t) return { lon: keys[0].lon, lat: keys[0].lat, z: keys[0].z };
    for (let i = 1; i < keys.length; i++) {
      const a = keys[i - 1], b = keys[i];
      if (t <= b.t) {
        const u = K.ease(b.ease || 'sine.inOut', K.seg(t, a.t, b.t));
        return { lon: K.lerp(a.lon, b.lon, u), lat: K.lerp(a.lat, b.lat, u), z: Math.exp(K.lerp(Math.log(a.z), Math.log(b.z), u)) };
      }
    }
    const l = keys[keys.length - 1]; return { lon: l.lon, lat: l.lat, z: l.z };
  };

  // ───────── mapa (canvas) ─────────
  // MD.mapa(stage, {geo, tex:[{bbox:[lon0,lat0,lon1,lat1], src:'img/br'}], lat0, cam: fn(t)})
  // src → carrega src+'_cinza.webp', '_verde.webp', '_vermelho.webp' (gerados por tools/mapa.py texturas)
  MD.mapa = async (parent, o) => {
    const W = VIDEO.w, H = VIDEO.h;
    const mk = () => { const c = document.createElement('canvas'); c.width = W; c.height = H; return c; };
    const c = mk(); c.className = 'md-mapa'; parent.appendChild(c);
    const x = c.getContext('2d'), mC = mk(), mX = mC.getContext('2d'), rC = mk(), rX = rC.getContext('2d');
    const geo = await (await fetch(o.geo)).json();
    const load = s => new Promise((res, rej) => { const i = new Image(); i.onload = () => i.decode().then(() => res(i), () => res(i)); i.onerror = () => rej(new Error('falta ' + s)); i.src = s; });
    const tex = await Promise.all((o.tex || []).map(async T => ({ bbox: T.bbox, cinza: await load(T.src + '_cinza.webp'), verde: await load(T.src + '_verde.webp'), vermelho: await load(T.src + '_vermelho.webp') })));
    const kx = Math.cos((o.lat0 ?? 0) * D2R);
    const M = {
      canvas: c, geo, tex, kx, cam: { lon: 0, lat: 0, z: 10 },
      // estado (0..1) que as cenas animam
      ativo: 0,      // país aceso em verde
      bordas: 0,     // bordas brancas dos estados/províncias
      contorno: 0,   // contorno do país
      rios: 0,       // rios acesos
      vermelho: 0.9, // opacidade geral da camada vermelha
      manchas: [],   // MD.mancha(...)
      grade: 1, luz: 1,
      paleta: Object.assign({ papel: '#5d5e5a', grade: 'rgba(214,214,206,.16)', borda: 'rgba(232,238,232,.82)', brilho: 'rgba(255,255,255,.55)', rio: 'rgba(78,228,176,.95)' }, o.paleta || {}),
    };
    M.xy = (lon, lat) => [W / 2 + (lon - M.cam.lon) * kx * M.cam.z, H / 2 - (lat - M.cam.lat) * M.cam.z];
    M.zf = (zRef = 60, p = 0.5) => Math.pow(M.cam.z / zRef, p); // fator para espessuras que crescem pouco com o zoom
    const ring = (p, r) => { for (let i = 0; i < r.length; i++) { const [X, Y] = M.xy(r[i][0], r[i][1]); i ? p.lineTo(X, Y) : p.moveTo(X, Y); } p.closePath(); };
    const pathOf = rings => { const p = new Path2D(); rings.forEach(r => ring(p, r)); return p; };
    const paisPath = () => pathOf(geo.estados.flatMap(e => e.aneis));
    const drawTex = (ctx, kind) => {
      for (const T of tex) {
        const [l0, b0, l1, b1] = T.bbox, [X0, Y0] = M.xy(l0, b1), [X1, Y1] = M.xy(l1, b0);
        if (X1 < 0 || X0 > W || Y1 < 0 || Y0 > H) continue;
        ctx.drawImage(T[kind], X0, Y0, X1 - X0, Y1 - Y0);
      }
    };

    M.desenhar = t => {
      if (o.cam) M.cam = o.cam(t);
      const P = M.paleta, z = M.cam.z;
      x.save(); x.setTransform(1, 0, 0, 1, 0, 0); x.globalAlpha = 1; x.globalCompositeOperation = 'source-over';
      x.imageSmoothingEnabled = true; x.imageSmoothingQuality = 'high';
      // 1. papel cinza com luz difusa e grade (num plano "mais fundo": cresce menos que o mapa)
      x.fillStyle = P.papel; x.fillRect(0, 0, W, H);
      const g = x.createRadialGradient(W * 0.58, H * 0.42, 0, W * 0.58, H * 0.42, H * 0.75);
      g.addColorStop(0, `rgba(255,255,250,${0.2 * M.luz})`); g.addColorStop(0.55, `rgba(255,255,250,${0.06 * M.luz})`); g.addColorStop(1, 'rgba(0,0,0,0)');
      x.fillStyle = g; x.fillRect(0, 0, W, H);
      if (M.grade > 0) {
        const zp = 3.2 * Math.pow(z, 0.45), G = 9, sp = G * zp, X0 = M.cam.lon * kx * zp, Y0 = -M.cam.lat * zp;
        x.strokeStyle = P.grade; x.globalAlpha = M.grade; x.lineWidth = 1.4; x.beginPath();
        for (let gx = W / 2 - (((X0 % sp) + sp) % sp) - sp * Math.ceil(W / sp); gx < W + sp; gx += sp) { x.moveTo(Math.round(gx) + 0.5, 0); x.lineTo(Math.round(gx) + 0.5, H); }
        for (let gy = H / 2 - (((Y0 % sp) + sp) % sp) - sp * Math.ceil(H / sp); gy < H + sp; gy += sp) { x.moveTo(0, Math.round(gy) + 0.5); x.lineTo(W, Math.round(gy) + 0.5); }
        x.stroke(); x.globalAlpha = 1;
      }
      // 2. terra apagada (cinza-escuro de satélite)
      x.shadowColor = 'rgba(0,0,0,.45)'; x.shadowBlur = 18; drawTex(x, 'cinza'); x.shadowBlur = 0;
      const pais = paisPath();
      // 3. país aceso (verde)
      if (M.ativo > 0) { x.save(); x.clip(pais); x.globalAlpha = M.ativo; drawTex(x, 'verde'); x.restore(); }
      // 4. rios acesos
      if (M.rios > 0 && geo.rios) {
        x.save(); x.clip(pais); x.strokeStyle = P.rio; x.shadowColor = P.rio; x.lineJoin = x.lineCap = 'round';
        for (const r of geo.rios) {
          const w = (r.rank <= 4 ? 2.0 : r.rank <= 6 ? 1.4 : 1.0) * M.zf(60, 0.55);
          x.globalAlpha = M.rios * (r.rank <= 4 ? 0.7 : r.rank <= 6 ? 0.5 : 0.32); x.lineWidth = w; x.shadowBlur = 6 * M.zf(60, 0.4);
          const p = new Path2D(); r.pts.forEach((q, i) => { const [X, Y] = M.xy(q[0], q[1]); i ? p.lineTo(X, Y) : p.moveTo(X, Y); }); x.stroke(p);
        }
        x.restore();
      }
      // 5. bordas brancas com brilho
      if (M.bordas > 0) {
        x.save(); x.lineJoin = 'round'; x.strokeStyle = P.borda; x.shadowColor = P.brilho;
        x.globalAlpha = M.bordas; x.lineWidth = 2.2 * M.zf(60, 0.3); x.shadowBlur = 9;
        for (const e of geo.estados) x.stroke(pathOf(e.aneis));
        x.restore();
      }
      if (M.contorno > 0) { x.save(); x.strokeStyle = P.borda; x.shadowColor = P.brilho; x.shadowBlur = 10; x.globalAlpha = M.contorno; x.lineWidth = 2.6 * M.zf(60, 0.3); x.stroke(pais); x.restore(); }
      // 6. região vermelha: máscara (manchas) → desfoque → textura vermelha só onde há máscara e terra
      const vis = M.manchas.filter(m => m.a > 0.002 && m.s > 0.002);
      if (vis.length && M.vermelho > 0) {
        mX.setTransform(1, 0, 0, 1, 0, 0); mX.clearRect(0, 0, W, H); mX.fillStyle = '#fff';
        for (const m of vis) { mX.globalAlpha = m.a; mX.fill(manchaPath(M, m)); }
        mX.globalAlpha = 1;
        // (texturas primeiro, máscara desfocada depois com destination-in: source-in apagaria o que fica fora de cada textura)
        rX.setTransform(1, 0, 0, 1, 0, 0); rX.globalCompositeOperation = 'source-over'; rX.clearRect(0, 0, W, H);
        rX.imageSmoothingQuality = 'high'; drawTex(rX, 'vermelho');
        rX.globalCompositeOperation = 'destination-in'; rX.filter = `blur(${(o.maciez ?? 0.13) * z}px)`; rX.drawImage(mC, 0, 0);
        rX.filter = 'none'; rX.globalCompositeOperation = 'source-over';
        x.globalAlpha = M.vermelho; x.drawImage(rC, 0, 0); x.globalAlpha = 1;
      }
      x.restore();
    };
    return M;
  };

  // mancha: elipse irregular em graus (rx, ry em graus de latitude), girada (rot em graus); a = opacidade, s = escala
  MD.mancha = (lon, lat, rx, ry, o = {}) => ({ lon, lat, rx, ry, rot: o.rot || 0, seed: o.seed ?? Math.round(lon * 13 + lat * 7), a: 0, s: 1, rug: o.rug ?? 0.22 });
  function manchaPath(M, m) {
    const p = new Path2D(), n = 56, cr = Math.cos(m.rot * D2R), sr = Math.sin(m.rot * D2R), [cx, cy] = M.xy(m.lon, m.lat), z = M.cam.z;
    for (let i = 0; i <= n; i++) {
      const a = (i / n) * Math.PI * 2, ca = Math.cos(a), sa = Math.sin(a);
      // contorno "pincelado": ruído de baixa frequência + cantos levemente quadrados (como os da referência)
      const r = m.s * (1 + m.rug * K.noise(ca * 1.4 + m.seed * 0.37, sa * 1.4 - m.seed * 0.21)) * (1 + 0.12 * Math.pow(Math.abs(Math.sin(2 * a)), 3));
      const ex = m.rx * ca * r, ey = m.ry * sa * r, X = cx + (ex * cr - ey * sr) * z, Y = cy - (ex * sr + ey * cr) * z;
      i ? p.lineTo(X, Y) : p.moveTo(X, Y);
    }
    p.closePath(); return p;
  }

  // ───────── anotações (DOM por cima do canvas, presas ao mapa) ─────────
  const pecas = [];
  MD.anotacoes = (parent, M) => {
    const lay = K.html(parent, '<div class="md-anot"><svg class="md-linhas" width="' + VIDEO.w + '" height="' + VIDEO.h + '"></svg></div>');
    MD._lay = lay; MD._svg = lay.querySelector('svg'); MD._M = M; return lay;
  };
  MD.tick = t => { for (const p of pecas) p(t); };
  const at = (el, X, Y) => { el.style.transform = `translate(${X.toFixed(1)}px,${Y.toFixed(1)}px)`; };

  // etiqueta-pílula com ponteiro ▼ (nome de estado/província). o.ate: some piscando; o.dim: [t, opacidade]
  MD.etiqueta = (lon, lat, txt, t0, o = {}) => {
    const el = K.html(MD._lay, `<div class="md-tag"><span>${txt}</span></div>`), seed = (o.seed ?? pecas.length) + 3;
    pecas.push(t => {
      let a = MD.pisca(t, t0, o.d ?? 0.3, seed, 0.4);
      if (o.dim) a *= K.lerp(1, o.dim[1], MD.vai(t, o.dim[0], 0.5, 'sine.inOut'));
      if (o.ate !== undefined) a *= 1 - MD.pisca(t, o.ate, 0.25, seed + 5, 0.5);
      el.style.opacity = a; el.style.display = a > 0.01 ? '' : 'none';
      if (a > 0.01) { const [X, Y] = MD._M.xy(lon, lat); at(el, X, Y); }
    });
    return el;
  };
  // cidade: texto verde vivo em negrito, sem caixa, com ponto
  MD.cidade = (lon, lat, txt, t0, o = {}) => {
    const el = K.html(MD._lay, `<div class="md-cidade ${o.lado === 'e' ? 'md-e' : ''}"><i></i><span>${txt}</span></div>`), seed = (o.seed ?? pecas.length) + 11;
    pecas.push(t => {
      let a = MD.pisca(t, t0, 0.25, seed, 0.3);
      if (o.dim) a *= K.lerp(1, o.dim[1], MD.vai(t, o.dim[0], 0.5, 'sine.inOut'));
      if (o.ate !== undefined) a *= 1 - MD.pisca(t, o.ate, 0.25, seed + 5, 0.5);
      el.style.opacity = a; el.style.display = a > 0.01 ? '' : 'none';
      if (a > 0.01) { const [X, Y] = MD._M.xy(lon, lat); at(el, X, Y); }
    });
    return el;
  };

  // texto que se "decodifica": cada linha nasce como barra branca borrada, as letras chegam borradas e firmam
  MD.decodifica = (el, t0, o = {}) => {
    const linhas = [...el.querySelectorAll('.md-l')], chars = [], barras = [], r = K.rng(o.seed ?? 5);
    linhas.forEach((ln, li) => {
      const txt = ln.textContent; ln.textContent = '';
      const bar = document.createElement('b'); bar.className = 'md-barra'; ln.appendChild(bar); barras.push({ el: bar, t: t0 + li * 0.05 });
      [...txt].forEach(ch => { const s = document.createElement('span'); s.textContent = ch; s.className = 'md-ch'; ln.appendChild(s); chars.push({ el: s, t: t0 + 0.08 + li * 0.05 + r() * (o.espalha ?? 0.24) }); });
    });
    return t => {
      for (const b of barras) {
        const u = MD.vai(t, b.t, 0.16, 'power2.out'), f = 1 - MD.vai(t, b.t + 0.16, 0.22, 'power1.in');
        b.el.style.width = (u * 92).toFixed(1) + '%'; b.el.style.opacity = t < b.t ? 0 : f * 0.8;
      }
      for (const c of chars) {
        const u = K.seg(t, c.t, c.t + 0.22), on = t >= c.t ? 1 : 0;
        c.el.style.opacity = on * (u < 0.15 ? 0.6 + 0.4 * (Math.floor(t * 30) % 2) : 1);
        c.el.style.filter = u < 1 ? `blur(${((1 - K.ease('power2.out', u)) * 9).toFixed(2)}px)` : 'none';
      }
    };
  };

  // chamada: linha branca do alvo (lon,lat) até um cotovelo e uma ponta (em px relativos ao alvo), rótulo de 2 linhas
  // sobre o trecho horizontal. o.cot=[dx,dy], o.ponta=[dx,dy] (fim do trecho horizontal), o.lado: 'acima'|'abaixo'
  MD.chamada = (lon, lat, linhas, t0, o = {}) => {
    const ns = 'http://www.w3.org/2000/svg', pl = document.createElementNS(ns, 'polyline'); pl.setAttribute('class', 'md-linha'); MD._svg.appendChild(pl);
    const el = K.html(MD._lay, `<div class="md-rotulo">${linhas.map((l, i) => `<div class="md-l ${i ? 'md-l2' : ''}">${l}</div>`).join('')}</div>`);
    if (o.tam) el.style.fontSize = o.tam + 'px';
    const dec = MD.decodifica(el, t0 + (o.dLinha ?? 0.3) * 0.7, { seed: o.seed ?? linhas[0].length });
    const cot = o.cot || [-60, -60], ponta = o.ponta || [-360, -60];
    pecas.push(t => {
      const vis = t >= t0;
      pl.style.display = el.style.display = vis ? '' : 'none';
      if (!vis) return;
      const [X, Y] = MD._M.xy(lon, lat), sc = o.escala ? o.escala(t) : 1;
      const A = [X, Y], B = [X + cot[0] * sc, Y + cot[1] * sc], C = [X + ponta[0] * sc, Y + ponta[1] * sc];
      // desenha do alvo para fora (power2.out)
      const L1 = Math.hypot(B[0] - A[0], B[1] - A[1]), L2 = Math.hypot(C[0] - B[0], C[1] - B[1]), u = MD.vai(t, t0, o.dLinha ?? 0.3, 'power2.out') * (L1 + L2);
      const pts = [A];
      if (u <= L1) pts.push([K.lerp(A[0], B[0], u / L1), K.lerp(A[1], B[1], u / L1)]);
      else pts.push(B, [K.lerp(B[0], C[0], (u - L1) / L2), K.lerp(B[1], C[1], (u - L1) / L2)]);
      pl.setAttribute('points', pts.map(p => p.map(v => v.toFixed(1)).join(',')).join(' '));
      pl.style.opacity = MD.pisca(t, t0, 0.15, 3);
      const mx = (B[0] + C[0]) / 2;
      el.style.transform = `translate(${mx.toFixed(1)}px,${(C[1] + (o.lado === 'abaixo' ? 14 : -14)).toFixed(1)}px) translate(-50%,${o.lado === 'abaixo' ? '0' : '-100%'}) scale(${sc})`;
      dec(t);
    });
    return { el, linha: pl };
  };

  // triângulo vermelho com texto branco black (o "marcador" do assunto). o.lado = largura em px
  MD.triangulo = (lon, lat, linhas, t0, o = {}) => {
    const w = o.lado ?? 300, h = w * 0.866;
    const el = K.html(MD._lay, `<div class="md-tri" style="width:${w}px;height:${h}px">
      <svg viewBox="0 0 100 86.6" width="${w}" height="${h}" preserveAspectRatio="none"><defs><linearGradient id="mdtg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ff3a22"/><stop offset="1" stop-color="#e01e12"/></linearGradient></defs>
      <polygon points="50,0 100,86.6 0,86.6" fill="url(#mdtg)"/></svg>
      <div class="md-tri-slot">${o.miolo ? `<div class="md-ret-foto" style="width:${o.miolo.diam}px;height:${o.miolo.diam}px"><img src="${o.miolo.src}"></div>` : ''}</div><div class="md-tri-txt">${linhas.map(l => `<div>${l}</div>`).join('')}</div></div>`);
    if (o.tam) el.querySelector('.md-tri-txt').style.fontSize = o.tam + 'px';
    const slot = el.querySelector('.md-tri-slot');
    pecas.push(t => {
      if (o.miolo) slot.style.opacity = t >= o.miolo.t ? 1 : 0;
      const a = MD.pisca(t, t0, o.d ?? 0.35, 21, 0.3); el.style.display = a > 0 ? '' : 'none'; if (!a) return;
      const [X, Y] = MD._M.xy(lon, lat), sc = (o.escala ? o.escala(t) : 1) * K.lerp(1.12, 1, MD.vai(t, t0, 0.35, 'power3.out'));
      el.style.opacity = a; el.style.transform = `translate(${X.toFixed(1)}px,${Y.toFixed(1)}px) translate(-50%,-62%) scale(${sc.toFixed(4)})`;
    });
    return el;
  };

  // retrato P&B em círculo com legenda em caixa-alta. o.para: {t, d, dx, dy, s} → desliza/encolhe para outro ponto (ex.: dentro do triângulo)
  MD.retrato = (lon, lat, src, linhas, t0, o = {}) => {
    const d = o.diam ?? 230;
    const el = K.html(MD._lay, `<div class="md-ret" style="width:${d}px"><div class="md-ret-foto" style="width:${d}px;height:${d}px"><img src="${src}"></div>
      <div class="md-ret-leg">${linhas.map(l => `<div>${l}</div>`).join('')}</div></div>`);
    pecas.push(t => {
      const a = MD.pisca(t, t0, 0.25, 31, 0.4); el.style.display = a > 0 ? '' : 'none'; if (!a) return;
      const [X, Y] = MD._M.xy(lon, lat), pop = K.ease('back.out(2.2)', K.seg(t, t0, t0 + 0.32));
      let dx = o.dx ?? 0, dy = o.dy ?? 0, s = pop * (o.escala ? o.escala(t) : 1);
      if (o.para) { const u = MD.vai(t, o.para.t, o.para.d ?? 0.5, 'power3.inOut'); dx = K.lerp(dx, o.para.dx, u); dy = K.lerp(dy, o.para.dy, u); s *= K.lerp(1, o.para.s, u);
        if (o.para.esconde && t >= o.para.t + (o.para.d ?? 0.5)) { el.style.display = 'none'; return; } }
      el.style.opacity = a; el.style.transform = `translate(${(X + dx).toFixed(1)}px,${(Y + dy).toFixed(1)}px) translate(-50%,-50%) scale(${s.toFixed(4)})`;
    });
    return el;
  };

  // círculo tracejado grosso: entra grande (×1,35) e encolhe girando. r em px no zoom zRef (cresce com o mapa)
  MD.circulo = (lon, lat, r, t0, o = {}) => {
    const ns = 'http://www.w3.org/2000/svg', g = document.createElementNS(ns, 'g'), ci = document.createElementNS(ns, 'circle');
    ci.setAttribute('class', 'md-circ'); ci.setAttribute('r', r); g.appendChild(ci); MD._svg.insertBefore(g, MD._svg.firstChild);
    const per = 2 * Math.PI * r, n = o.tracos ?? 26; ci.setAttribute('stroke-dasharray', `${(per / n) * 0.62} ${(per / n) * 0.38}`);
    pecas.push(t => {
      const a = MD.pisca(t, t0, 0.3, 41, 0.5); g.style.display = a > 0 ? '' : 'none'; if (!a) return;
      const [X, Y] = MD._M.xy(lon, lat), u = MD.vai(t, t0, o.d ?? 0.6, 'power3.out');
      const s = K.lerp(1.35, 1, u) * (o.escala ? o.escala(t) : 1), rot = K.lerp(-28, 0, u) + (t - t0) * (o.giro ?? 2.5);
      g.setAttribute('transform', `translate(${X.toFixed(1)},${Y.toFixed(1)}) rotate(${rot.toFixed(2)}) scale(${s.toFixed(4)})`); g.style.opacity = a;
    });
    return ci;
  };

  // acabamento: vinheta pesada + grão leve (acima do mapa e abaixo das anotações, como na referência)
  MD.acabamento = (parent, o = {}) => {
    K.html(parent, `<div class="md-vinheta" style="opacity:${o.vinheta ?? 1}"></div>`);
    if (o.grao !== 0) K.grain(parent, { opacity: o.grao ?? 0.07, blend: 'overlay', w: 540 });
  };

  // estilos (injetados uma vez)
  const css = `
  .md-mapa,.md-anot,.md-vinheta{position:absolute;inset:0}
  .md-anot{pointer-events:none}
  .md-anot>div{position:absolute;left:0;top:0;will-change:transform}
  .md-linhas{position:absolute;left:0;top:0;overflow:visible}
  .md-linha{fill:none;stroke:#f4f6f2;stroke-width:5;stroke-linejoin:miter;filter:drop-shadow(0 0 5px rgba(255,255,255,.7))}
  .md-circ{fill:none;stroke:#d9dbd6;stroke-width:10;opacity:.92;filter:drop-shadow(0 0 6px rgba(255,255,255,.35))}
  .md-tag{font:500 29px/1 'Noto Sans',sans-serif;color:#d4ece1;white-space:nowrap}
  .md-tag span{display:block;transform:translate(-50%,calc(-100% - 12px));background:rgba(104,178,148,.34);padding:6px 13px 8px;border-radius:5px;box-shadow:inset 0 0 0 1.5px rgba(170,230,200,.16);text-shadow:0 0 6px rgba(160,255,210,.35)}
  .md-tag span::after{content:'';position:absolute;left:50%;bottom:-11px;margin-left:-9px;border:9px solid transparent;border-bottom:0;border-top:11px solid rgba(104,178,148,.34)}
  .md-cidade{font:700 25px/1 'Noto Sans',sans-serif;color:#38e3a6;white-space:nowrap;text-shadow:0 0 8px rgba(40,230,160,.55)}
  .md-cidade i{position:absolute;left:-5px;top:-5px;width:10px;height:10px;border-radius:50%;background:#7dffd0;box-shadow:0 0 8px #3be3a6}
  .md-cidade span{position:absolute;left:12px;top:-12px}
  .md-cidade.md-e span{left:auto;right:12px}
  .md-rotulo{font:800 46px/1.02 'Montserrat',sans-serif;color:#fff;text-transform:uppercase;letter-spacing:.035em;text-align:center;white-space:nowrap;
    text-shadow:0 0 6px rgba(255,255,255,.85),0 0 18px rgba(255,255,255,.45),0 0 2px #fff}
  .md-l{position:relative}
  .md-l2{font-size:.72em;letter-spacing:.06em;margin-top:.1em}
  .md-ch{display:inline-block;white-space:pre}
  .md-barra{position:absolute;left:4%;top:32%;height:36%;width:0;max-width:92%;background:#fff;border-radius:3px;filter:blur(4px);box-shadow:0 0 12px rgba(255,255,255,.8)}
  .md-tri{transform-origin:50% 62%}
  .md-tri svg{position:absolute;left:0;top:0;filter:drop-shadow(0 0 22px rgba(255,40,20,.55)) drop-shadow(0 6px 16px rgba(0,0,0,.35))}
  .md-tri-slot{position:absolute;left:50%;top:44%;transform:translate(-50%,-50%)}
  .md-tri-txt{position:absolute;left:0;right:0;top:51%;font:900 68px/.98 'Montserrat',sans-serif;color:#fff;text-align:center;text-transform:uppercase;letter-spacing:.03em;
    text-shadow:0 0 8px rgba(255,255,255,.75),0 0 22px rgba(255,255,255,.3)}
  .md-ret-foto{border-radius:50%;overflow:hidden;background:#8a8a86;box-shadow:0 0 0 3px rgba(255,255,255,.12),0 10px 30px rgba(0,0,0,.45)}
  .md-ret-foto img{width:100%;height:100%;object-fit:cover;filter:grayscale(1) contrast(1.18) brightness(.92)}
  .md-ret-leg{position:absolute;left:50%;bottom:-18px;transform:translateX(-50%);font:800 25px/1.02 'Montserrat',sans-serif;color:#fff;text-align:center;letter-spacing:.05em;white-space:nowrap;
    text-shadow:0 0 6px rgba(0,0,0,.9),0 0 3px rgba(0,0,0,.9),0 0 12px rgba(255,255,255,.35)}
  .md-vinheta{background:radial-gradient(ellipse 78% 62% at 54% 46%,rgba(0,0,0,0) 38%,rgba(0,0,0,.42) 72%,rgba(0,0,0,.86) 100%);pointer-events:none}
  .md-cred{position:absolute;left:0;right:0;bottom:46px;text-align:center;font:500 15px/1.35 'Noto Sans',sans-serif;color:rgba(235,240,236,.72);letter-spacing:.02em}`;
  const st = document.createElement('style'); st.textContent = css; document.head.appendChild(st);
})();
