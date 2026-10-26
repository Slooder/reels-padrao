// colagem.js — biblioteca do estilo "colagem explicativa" (explainer de colagem sobre papel cinza).
// Global: window.CE. Precisa do motor (core.js + kit.js + GSAP). Carregue com <script>LIBS=['colagem.js']</script>.
//
// As 3 marcas: (1) papel cinza reciclado vazio que "ferve" de leve; (2) três materiais na mesma colagem —
// pessoas em foto P&B com borda branca grossa, coisas/lugares em foto colorida recortada, ícones vetoriais
// chapados com grão + manchas de tinta, grade branca e círculo tracejado; (3) a cena se monta peça a peça em
// stop-motion de 12 qps (sobe de baixo, cresce do chão, pipoca em anel, cai) e troca por corte seco ou pan lateral.
(function () {
  const CE = (window.CE = {});
  const NS = 'http://www.w3.org/2000/svg';

  // ───────────── paleta medida na referência ─────────────
  CE.COR = {
    papel: '#dbdbdb', tinta: '#1d1d1d', verde: '#3aa845',          // papel, texto escuro, letreiro Poppins verde
    oceano: '#2a99da', terra: '#a4f269', destaque: '#7fd23f',     // planeta
    limao: '#9be22f', amarelo: '#f6c431', sol: '#f7c531',          // lixeira da ref (limão), metal no Brasil (amarelo), sol
    agua: '#94b3af', aguaEsc: '#5a887d', pinho: '#2f5e50',          // semicírculo, mancha retangular, pinheiros verdes
    grafite: '#2b2b2b', grafite2: '#454545',                        // pinheiros escuros
    ocre: '#f4c55c', azul: '#3a9ad9', tracejado: '#6aa88a',         // manchinhas e círculo tracejado
  };
  const LATAS = [['#d8343a', '#f3f3f3'], ['#2f6fd0', '#f6c431'], ['#3cae5c', '#f3f3f3'], ['#c9ced4', '#2f6fd0'], ['#f6c431', '#d8343a'],
    ['#8b5cc7', '#f3f3f3'], ['#f08a2c', '#1d1d1d'], ['#1d1d1d', '#9be22f'], ['#e85d9a', '#f3f3f3'], ['#22a7a0', '#f6c431']];
  CE.LATAS = LATAS;

  // ───────────── stop-motion: tempo em degraus de 12 qps ─────────────
  // ease que segura cada pose 1/12 s (2–3 quadros a 30 qps), como a referência
  CE.passos = (ease, d, fps = 12) => { const f = gsap.parseEase(ease); const n = Math.max(1, Math.round(d * fps)); return p => (p >= 1 ? 1 : p <= 0 ? 0 : f(Math.ceil(p * n - 1e-6) / n)); };
  CE.q = (t, fps = 12) => Math.floor(t * fps + 1e-6) / fps;

  // ───────────── filtros (grão de papel nos vetores, sombra curta) ─────────────
  CE.defs = () => {
    if (document.getElementById('ce-defs')) return;
    K.html(document.body, `<svg id="ce-defs" width="0" height="0" style="position:absolute">
      <filter id="ce-grao" x="-5%" y="-5%" width="110%" height="110%" color-interpolation-filters="sRGB">
        <feTurbulence type="fractalNoise" baseFrequency=".9" numOctaves="2" seed="4" result="n"/>
        <feColorMatrix in="n" type="saturate" values="0" result="g"/>
        <feComponentTransfer in="g" result="g2"><feFuncR type="linear" slope=".55" intercept=".7"/><feFuncG type="linear" slope=".55" intercept=".7"/><feFuncB type="linear" slope=".55" intercept=".7"/><feFuncA type="linear" slope="0" intercept="1"/></feComponentTransfer>
        <feBlend in="SourceGraphic" in2="g2" mode="multiply" result="b"/>
        <feComposite in="b" in2="SourceGraphic" operator="in"/>
      </filter>
      <filter id="ce-borda" x="-20%" y="-20%" width="140%" height="140%">
        <feTurbulence type="fractalNoise" baseFrequency=".035" numOctaves="3" seed="9" result="t"/>
        <feDisplacementMap in="SourceGraphic" in2="t" scale="14" xChannelSelector="R" yChannelSelector="G"/>
      </filter>
    </svg>`);
  };
  CE.SOMBRA = 'drop-shadow(0 5px 6px rgba(0,0,0,.16))';

  // ───────────── papel cinza reciclado que ferve ─────────────
  // img: papel.jpg maior que a tela (tools/colagem.py papel). A textura troca de posição em intervalos
  // irregulares de 2–12 quadros, com brilho ±1,5% — medido na referência (≈4 trocas por segundo).
  CE.papel = (stage, src, o = {}) => {
    const el = K.html(stage, `<div class="ce-papel" style="position:absolute;inset:0;background:${CE.COR.papel} url(${src}) 0 0/auto;z-index:0"></div>`);
    const r = K.rng(o.seed ?? 11), fps = VIDEO.fps, trocas = [];
    let f = 0;
    while (f < VIDEO.dur * fps + 30) { trocas.push({ f, x: -Math.round(r() * 300), y: -Math.round(r() * 460), b: .985 + r() * .03, fx: r() < .5 }); f += 2 + Math.floor(r() * 11); }
    onTick(t => {
      const qf = Math.floor(t * fps + 1e-6); let s = trocas[0];
      for (const tr of trocas) { if (tr.f <= qf) s = tr; else break; }
      el.style.backgroundPosition = `${s.x}px ${s.y}px`; el.style.filter = `brightness(${s.b.toFixed(3)})`; el.style.transform = s.fx ? 'scaleX(-1)' : '';
    });
    return el;
  };

  // ───────────── cenas: só uma (ou duas, no pan) visível por vez ─────────────
  CE.cenas = mapa => onTick(t => { for (const [sel, [a, b]] of Object.entries(mapa)) K.$(sel).style.display = t >= a && t < b ? 'block' : 'none'; });

  // ───────────── peças posicionadas ─────────────
  // CE.peca(pai, html, {x,y,w,h,z,origem}) → div absoluto com o conteúdo; origem = transform-origin
  CE.peca = (pai, html, o = {}) => K.html(pai, `<div class="ce-peca" style="position:absolute;left:${o.x ?? 0}px;top:${o.y ?? 0}px;${o.w ? `width:${o.w}px;` : ''}${o.h ? `height:${o.h}px;` : ''}z-index:${o.z ?? 1};transform-origin:${o.origem ?? '50% 100%'};${o.css ?? ''}">${html}</div>`);
  // foto recortada: P&B com borda já assada (tools/colagem.py adesivo) ou colorida sem borda
  CE.foto = (pai, src, o = {}) => CE.peca(pai, `<img src="${src}" style="display:block;width:100%;${o.sombra === false ? '' : `filter:${CE.SOMBRA}`}">`, o);

  // ───────────── vetores chapados com grão ─────────────
  const svg = (w, h, vb, corpo, o = {}) => `<svg width="${w}" height="${h}" viewBox="${vb}" style="display:block;overflow:visible${o.sombra ? `;filter:${CE.SOMBRA}` : ''}">${corpo}</svg>`;
  const G = (s, f = 'ce-grao') => `<g filter="url(#${f})">${s}</g>`;

  // planeta: dados = JSON de tools/globo.py ({terra, destaque}); raio r px
  CE.planeta = (dados, o = {}) => {
    const r = o.r ?? 300, id = 'pl' + Math.round(r) + (o.id ?? ''), aro = o.aro ?? r * .035;
    return svg(2 * (r + aro), 2 * (r + aro), `${-1 - aro / r} ${-1 - aro / r} ${2 + 2 * aro / r} ${2 + 2 * aro / r}`,
      `<defs><clipPath id="${id}"><circle r="1"/></clipPath></defs>
       <circle r="${1 + aro / r}" fill="#fff"/>
       ${G(`<circle r="1" fill="${o.oceano ?? CE.COR.oceano}"/>
       <g clip-path="url(#${id})"><path d="${dados.terra}" fill="${o.terra ?? CE.COR.terra}" fill-rule="nonzero"/>
       ${dados.destaque && o.destaque !== false ? `<path d="${dados.destaque}" fill="${o.destaque ?? CE.COR.destaque}" stroke="${o.terra ?? CE.COR.terra}" stroke-width=".006"/>` : ''}</g>`)}`, o);
  };

  // lata de alumínio (ícone): w px de largura; cor = [corpo, faixa]; amassada = true dá o corpo sanfonado
  CE.lata = (o = {}) => {
    const w = o.w ?? 80, [c1, c2] = o.cor ?? LATAS[0], am = o.amassada, h = am ? 120 : 180;
    const corpo = am
      ? 'M10 34 L4 52 L14 68 L6 86 L12 104 Q50 118 88 104 L95 86 L86 70 L96 52 L90 34 Q50 46 10 34 Z'
      : 'M8 30 Q8 22 16 18 L22 12 Q50 6 78 12 L84 18 Q92 22 92 30 L92 160 Q92 176 50 176 Q8 176 8 160 Z';
    const faixa = am ? 'M5 62 Q30 74 50 62 T95 62 L92 80 Q70 92 50 80 T8 80 Z' : 'M8 92 Q30 76 50 92 T92 92 L92 124 Q70 108 50 124 T8 124 Z';
    const topo = am ? `<ellipse cx="50" cy="34" rx="40" ry="9" fill="#d9dde2"/><ellipse cx="50" cy="34" rx="31" ry="6" fill="#b9bfc6"/><rect x="40" y="29" width="20" height="7" rx="3.5" fill="#e9ecef"/>`
      : `<ellipse cx="50" cy="13" rx="29" ry="6.5" fill="#d9dde2"/><ellipse cx="50" cy="13" rx="23" ry="4.6" fill="#b4bac2"/><rect x="40" y="9" width="20" height="7" rx="3.5" fill="#eef0f2"/><circle cx="46" cy="12.5" r="1.8" fill="#9aa1a9"/>`;
    return svg(w, w * h / 100, `0 0 100 ${h}`,
      `<path d="${corpo}" fill="none" stroke="#fff" stroke-width="${o.contorno ?? 7}" stroke-linejoin="round"/>
       ${G(`<path d="${corpo}" fill="${c1}"/>
       <clipPath id="lc${o.id ?? ''}${am ? 'a' : 'b'}${c1.slice(1)}"><path d="${corpo}"/></clipPath>
       <g clip-path="url(#lc${o.id ?? ''}${am ? 'a' : 'b'}${c1.slice(1)})"><path d="${faixa}" fill="${c2}"/>
         <rect x="${am ? 18 : 18}" y="0" width="11" height="${h}" fill="#fff" opacity=".32"/><rect x="72" y="0" width="22" height="${h}" fill="#000" opacity=".14"/>
         ${am ? '<path d="M4 52 L96 52 M14 68 L86 70 M6 86 L95 86" stroke="#000" stroke-opacity=".18" stroke-width="2.5"/>' : '<rect x="0" y="16" width="100" height="10" fill="#c9ced4"/><rect x="0" y="162" width="100" height="16" fill="#b9bfc6"/>'}</g>
       ${topo}`)}`, o);
  };

  // lacre (anel de abrir a lata): peça pequena prateada com contorno branco
  CE.lacre = (o = {}) => {
    const w = o.w ?? 46, c = o.cor ?? '#c3c9d0';
    const d = 'M30 2 Q54 2 57 26 Q60 50 50 70 Q46 98 30 98 Q14 98 10 70 Q0 50 3 26 Q6 2 30 2 Z';
    return svg(w, w * 100 / 60, '0 0 60 100', `<path d="${d}" fill="none" stroke="#fff" stroke-width="8" stroke-linejoin="round"/>
      ${G(`<path d="${d}" fill="${c}"/><ellipse cx="30" cy="30" rx="17" ry="18" fill="${CE.COR.papel}"/>
      <ellipse cx="30" cy="78" rx="7" ry="6" fill="#8f97a0"/><path d="M12 54 Q30 62 48 54" stroke="#fff" stroke-opacity=".5" stroke-width="3" fill="none"/>
      <path d="M8 22 Q10 8 24 5" stroke="#fff" stroke-opacity=".6" stroke-width="3" fill="none" stroke-linecap="round"/>`)}`, o);
  };

  // símbolo de reciclagem (3 setas em triângulo) em caixa 100×100
  CE.reciclagem = (cor = '#fff') => {
    const v = [0, 1, 2].map(k => { const a = (-90 + k * 120) * Math.PI / 180; return [50 + 34 * Math.cos(a), 56 + 34 * Math.sin(a)]; });
    let s = '';
    for (let k = 0; k < 3; k++) {
      const [ax, ay] = v[k], [bx, by] = v[(k + 1) % 3], dx = bx - ax, dy = by - ay, L = Math.hypot(dx, dy), ux = dx / L, uy = dy / L;
      const p0 = [ax + ux * 9, ay + uy * 9], p1 = [bx - ux * 21, by - uy * 21], nx = -uy, ny = ux;
      const tip = [bx - ux * 6, by - uy * 6];
      s += `<path d="M${p0[0].toFixed(1)} ${p0[1].toFixed(1)} L${p1[0].toFixed(1)} ${p1[1].toFixed(1)}" stroke="${cor}" stroke-width="10" stroke-linecap="butt"/>`;
      s += `<path d="M${(p1[0] + nx * 11).toFixed(1)} ${(p1[1] + ny * 11).toFixed(1)} L${tip[0].toFixed(1)} ${tip[1].toFixed(1)} L${(p1[0] - nx * 11).toFixed(1)} ${(p1[1] - ny * 11).toFixed(1)} Z" fill="${cor}"/>`;
    }
    return s;
  };

  // lixeira de reciclagem (frente), w px; cor do corpo; símbolo branco; rodinhas
  CE.lixeira = (o = {}) => {
    const w = o.w ?? 240, c = o.cor ?? CE.COR.amarelo, esc = o.escura ?? 'rgba(0,0,0,.16)';
    return svg(w, w * 1.32, '0 0 100 132',
      `<rect x="16" y="118" width="9" height="14" rx="3" fill="#3a3a3a"/><rect x="75" y="118" width="9" height="14" rx="3" fill="#3a3a3a"/>
       ${G(`<path d="M10 16 L90 16 L84 122 L16 122 Z" fill="${c}"/>
       <path d="M10 16 L90 16 L89 26 L11 26 Z" fill="${esc}"/>
       <rect x="3" y="6" width="94" height="12" rx="4" fill="${c}"/><rect x="3" y="14" width="94" height="4" fill="${esc}"/>
       <g transform="translate(25 44) scale(.5)">${CE.reciclagem(o.simbolo ?? '#fff')}</g>`)}`, o);
  };

  // pinheiro recortado: triângulo alto com dentes nos lados e riscos brancos (ou sem riscos)
  CE.pinheiro = (o = {}) => {
    const w = o.w ?? 200, h = o.h ?? 520, n = o.niveis ?? 5, r = K.rng(o.seed ?? 3), c = o.cor ?? CE.COR.grafite;
    const L = [], R = [];
    for (let i = 0; i < n; i++) {
      const u0 = i / n, u1 = (i + 1) / n, y0 = u0 * h, y1 = u1 * h;
      const hw0 = (u0 * .78 + .02) * w / 2, hw1 = (u1 * .98 + .02) * w / 2, j = r() * .06 * w;
      L.push([w / 2 - hw0 * .7, y0], [w / 2 - hw1 - j, y1 - (i < n - 1 ? h * .02 : 0)]); R.push([w / 2 + hw0 * .7, y0], [w / 2 + hw1 + j, y1 - (i < n - 1 ? h * .03 : 0)]);
    }
    const pts = [[w / 2, 0], ...L, ...R.reverse()];
    let riscos = '';
    if (o.riscos !== false) for (let i = 0; i < (o.nr ?? 7); i++) {
      const u = .25 + r() * .7, y = u * h, x = w / 2 + (r() - .3) * u * w * .45, l = (14 + r() * 26) * w / 200;
      riscos += `<path d="M${x.toFixed(1)} ${y.toFixed(1)} l${l.toFixed(1)} ${(-l * .45).toFixed(1)}" stroke="#fff" stroke-opacity="${o.riscoAlfa ?? .5}" stroke-width="${(2.2 * w / 200).toFixed(1)}" stroke-linecap="round"/>`;
    }
    return svg(w, h, `0 0 ${w} ${h}`, G(`<path d="M${pts.map(p => p.map(v => v.toFixed(1)).join(' ')).join(' L')} Z" fill="${c}"/>
      <path d="M${w / 2} 0 L${w / 2} ${h} L${pts[pts.length - 1][0]} ${pts[pts.length - 1][1]} Z" fill="#fff" opacity=".07"/>${riscos}`), o);
  };

  // sol amarelo com raios tracejados
  CE.sol = (o = {}) => {
    const r = o.r ?? 120, n = o.raios ?? 28, c = o.cor ?? CE.COR.sol, R = r * 1.42;
    let ra = '';
    for (let i = 0; i < n; i++) { const a = i / n * Math.PI * 2, r0 = r * 1.2, r1 = r * 1.36; ra += `<line x1="${(Math.cos(a) * r0).toFixed(1)}" y1="${(Math.sin(a) * r0).toFixed(1)}" x2="${(Math.cos(a) * r1).toFixed(1)}" y2="${(Math.sin(a) * r1).toFixed(1)}" stroke="${c}" stroke-width="${(r * .065).toFixed(1)}" stroke-linecap="round"/>`; }
    return svg(2 * R, 2 * R, `${-R} ${-R} ${2 * R} ${2 * R}`, `<g class="ce-raios">${ra}</g>${G(`<circle r="${r}" fill="${c}"/>`)}`, o);
  };

  // mancha de tinta de borda irregular: forma 'ret' (retângulo pincelado) ou 'semi' (semicírculo)
  CE.mancha = (o = {}) => {
    const w = o.w ?? 300, h = o.h ?? 200, r = K.rng(o.seed ?? 5), c = o.cor ?? CE.COR.aguaEsc, j = o.tremor ?? 6;
    let d;
    if (o.forma === 'semi') {
      const pts = []; const N = 48;
      for (let i = 0; i <= N; i++) { const a = Math.PI + i / N * Math.PI, rr = 1 + (r() - .5) * .025; pts.push([w / 2 + Math.cos(a) * w / 2 * rr, h + Math.sin(a) * h * rr]); }
      d = 'M' + pts.map(p => p.map(v => v.toFixed(1)).join(' ')).join(' L') + ` L${w} ${h} L0 ${h} Z`;
    } else {
      const lado = (x0, y0, x1, y1, n) => { const p = []; for (let i = 0; i < n; i++) { const u = i / n; p.push([x0 + (x1 - x0) * u + (r() - .5) * j * (y0 === y1 ? .3 : 1), y0 + (y1 - y0) * u + (r() - .5) * j * (x0 === x1 ? .3 : 1)]); } return p; };
      const pts = [...lado(0, 0, w, 0, 14), ...lado(w, 0, w, h, 10), ...lado(w, h, 0, h, 14), ...lado(0, h, 0, 0, 10)];
      d = 'M' + pts.map(p => p.map(v => v.toFixed(1)).join(' ')).join(' L') + ' Z';
    }
    return svg(w, h, `0 0 ${w} ${h}`, G(`<path d="${d}" fill="${c}"/>`), o);
  };

  // grade de linhas finas (brancas na referência); cada linha tem classe ce-gl para animar o traçado
  CE.grade = (o = {}) => {
    const w = o.w ?? 600, h = o.h ?? 600, p = o.passo ?? 60, c = o.cor ?? 'rgba(255,255,255,.9)', e = o.esp ?? 1.6;
    let s = '';
    for (let x = 0; x <= w + .1; x += p) s += `<line class="ce-gl" x1="${x}" y1="0" x2="${x}" y2="${h}" stroke="${c}" stroke-width="${e}"/>`;
    for (let y = 0; y <= h + .1; y += p) s += `<line class="ce-gl" x1="0" y1="${y}" x2="${w}" y2="${y}" stroke="${c}" stroke-width="${e}"/>`;
    return svg(w, h, `0 0 ${w} ${h}`, s, o);
  };

  // círculo tracejado (anel de traços curtos)
  CE.anel = (o = {}) => {
    const r = o.r ?? 120, n = o.tracos ?? 26, c = o.cor ?? CE.COR.tracejado, e = o.esp ?? r * .07, R = r + e;
    let s = '';
    for (let i = 0; i < n; i++) { const a = i / n * Math.PI * 2, da = Math.PI / n * .55; s += `<path d="M${(Math.cos(a - da) * r).toFixed(1)} ${(Math.sin(a - da) * r).toFixed(1)} A${r} ${r} 0 0 1 ${(Math.cos(a + da) * r).toFixed(1)} ${(Math.sin(a + da) * r).toFixed(1)}" stroke="${c}" stroke-width="${e.toFixed(1)}" fill="none" stroke-linecap="round"/>`; }
    return svg(2 * R, 2 * R, `${-R} ${-R} ${2 * R} ${2 * R}`, s, o);
  };

  // ───────────── texto: letreiro Poppins verde + linha escura ─────────────
  CE.legenda = (pai, o = {}) => {
    const el = K.html(pai, `<div class="ce-leg" style="position:absolute;left:0;right:0;top:${o.y ?? 230}px;text-align:center;z-index:${o.z ?? 20}">
      <div class="ce-t1" style="display:inline-block;font:600 ${o.tam ?? 70}px/1.05 Poppins;color:${o.cor ?? CE.COR.verde};letter-spacing:.005em;text-transform:uppercase;transform-origin:50% 60%">${o.t1 ?? ''}</div><br>
      <div class="ce-t2" style="display:inline-block;margin-top:${o.gap ?? 14}px;font:400 ${o.tam2 ?? 40}px/1.2 Poppins;color:${o.cor2 ?? CE.COR.tinta};transform-origin:50% 50%">${o.t2 ?? ''}</div></div>`);
    return { el, t1: el.querySelector('.ce-t1'), t2: el.querySelector('.ce-t2') };
  };

  // ───────────── movimentos (todos em degraus de 12 qps, menos o pan) ─────────────
  const som = (o, tipo, at, extra = {}) => { if (o.som !== false) cue(o.som ?? tipo, at, Object.assign({}, extra, o.somOpc || {})); };
  // sobe de baixo e passa um pouco do ponto (planeta, lixeiras, faixa de cidade)
  CE.sobe = (el, at, o = {}) => { const d = o.d ?? .4; TL.fromTo(el, { y: o.dist ?? 1200, autoAlpha: 1 }, { y: 0, duration: d, ease: CE.passos(o.ease ?? 'back.out(1.25)', d), immediateRender: true }, at); TL.set(el, { autoAlpha: 1 }, at); som(o, 'paper', at + d * .7); return at + d; };
  // cresce de um ponto no chão (pessoas, veículos): escala ancorada na base
  CE.cresce = (el, at, o = {}) => { const d = o.d ?? .7; if (o.origem) gsap.set(el, { transformOrigin: o.origem }); TL.fromTo(el, { scale: o.s0 ?? .03 }, { scale: 1, duration: d, ease: CE.passos(o.ease ?? 'power2.out', d), immediateRender: true }, at); TL.fromTo(el, { autoAlpha: 0 }, { autoAlpha: 1, duration: .001, immediateRender: true }, at); som(o, 'swoosh', at, { gain: -8 }); return at + d; };
  // pipoca: 0 → passa → 1 (aparelhos em anel, manchinhas, sol)
  CE.pipoca = (el, at, o = {}) => { const d = o.d ?? .25; TL.fromTo(el, { scale: o.s0 ?? 0, rotate: o.r0 ?? 0, autoAlpha: 0 }, { scale: 1, rotate: o.r ?? 0, autoAlpha: 1, duration: d, ease: CE.passos(o.ease ?? 'back.out(2.2)', d), immediateRender: true }, at); som(o, 'pop', at, { f: o.f ?? 560, gain: o.gain ?? -4 }); return at + d; };
  // pousa: o letreiro entra grande e encolhe até o tamanho (3 degraus, como o logo da referência)
  CE.pousa = (el, at, o = {}) => { const d = o.d ?? .2; TL.fromTo(el, { scale: o.s0 ?? 2.2, autoAlpha: 0 }, { scale: 1, autoAlpha: 1, duration: d, ease: CE.passos(o.ease ?? 'power2.out', d), immediateRender: true }, at); som(o, 'paper', at, { gain: -6 }); return at + d; };
  // cai de cima com gravidade e quica pouco (latinha caindo na lixeira); devolve o instante do impacto
  CE.cai = (el, at, o = {}) => {
    const d = o.d ?? .38, imp = at + d;
    TL.fromTo(el, { y: o.dist ?? -1300, rotate: o.r0 ?? 0 }, { y: o.y1 ?? 0, rotate: o.r ?? 0, duration: d, ease: CE.passos('power2.in', d), immediateRender: true }, at);
    TL.fromTo(el, { autoAlpha: 0 }, { autoAlpha: 1, duration: .001, immediateRender: true }, at);   // surge no 1º degrau (stop-motion)
    if (o.quica !== false) TL.to(el, { keyframes: [{ y: (o.y1 ?? 0) - (o.quique ?? 26), duration: .08 }, { y: o.y1 ?? 0, duration: .08 }], ease: 'none' }, imp);
    som(o, 'lata', imp); return imp;
  };
  // amassa ao receber algo (lixeira): escala vertical .92 → 1 em degraus
  CE.amassa = (el, at, o = {}) => { TL.fromTo(el, { scaleY: o.s ?? .9, scaleX: 1.04 }, { scaleY: 1, scaleX: 1, duration: .25, ease: CE.passos('back.out(3)', .25), immediateRender: false }, at); };
  // pan lateral liso entre duas cenas (a câmera "anda" para o lado): sai vai para -dist, entra vem de +dist
  CE.pan = (sai, entra, at, o = {}) => { const d = o.d ?? .5, dist = o.dist ?? VIDEO.w; TL.fromTo(sai, { x: 0 }, { x: -dist, duration: d, ease: o.ease ?? 'power2.inOut', immediateRender: false }, at); TL.fromTo(entra, { x: dist }, { x: 0, duration: d, ease: o.ease ?? 'power2.inOut', immediateRender: true }, at); som(o, 'whoosh_in', at, { gain: -5 }); return at + d; };
  // grade se desenhando: cada linha cresce do começo ao fim, em ordem, em degraus
  CE.traca = (svgEl, at, o = {}) => { const ls = [...svgEl.querySelectorAll('.ce-gl')], d = o.d ?? .35; ls.forEach((l, i) => TL.fromTo(l, { drawSVG: '0%' }, { drawSVG: '100%', duration: d, ease: CE.passos('power2.out', d), immediateRender: true }, at + i * (o.s ?? .012))); som(o, 'marker', at, { gain: -8 }); };
})();
