// recortes.js — "PALAVRA EM RECORTES" (paper cut / recap): a MESMA palavra aparece grifada em vários textos
// diferentes, trocando a cada 3 quadros (semicolcheia a 150 bpm), sempre no mesmo ponto da tela, com zoom e giro
// acumulando, lente velha (vinheta, aberração cromática, linhas de varredura, profundidade de campo).
// A variedade vem de MATERIAIS (papel + fontes + tinta) × GRIFOS (marca-texto, sublinhado, círculo, tarja, recorte…).
// Uso: <script>LIBS=['recortes.js']</script> antes do boot.js. Tudo é função de t; medidas no SETUP (RC.medir()).
(function () {
  const RC = (window.RC = {});
  const V = window.VIDEO;
  const RAIZ = document.currentScript.src.replace(/lib\/recortes\.js.*$/, '');
  RC.papel = nome => `${RAIZ}lib/papeis/${nome}.jpg`;

  // ───────────── cores dos grifos ─────────────
  RC.CORES = { amarelo: '#F2CD3B', rosa: '#FF86B8', verde: '#A6E86A', laranja: '#FFAE45', azul: '#8FD0FF', lima: '#D9F24A',
    vermelho: '#D7262E', caneta: '#1F3B8F', lapis: '#5a5650', preto: '#121212', branco: '#F4F1EA' };

  // ───────────── materiais: papel + fontes + tinta + grifos que combinam ─────────────
  // fonte: [família, peso do texto, peso da palavra, escala do corpo, caixa ('' | 'up'), espaçamento]
  RC.MATERIAIS = {
    creme:   { papel: 'creme', tinta: '#1b1c1f', ent: 1.42, fontes: [['Outfit', 400, 600, 1]], grifos: ['reta:amarelo', 'marca:amarelo', 'sublinhado:vermelho', 'circulo:vermelho'] },
    jornal:  { papel: 'jornal', tinta: '#1e1e1e', ent: 1.32, cab: 1.18, fontes: [['Libre Caslon Text', 400, 700, .95], ['Playfair Display', 400, 800, 1]], grifos: ['marca:amarelo', 'circulo:vermelho', 'caixa:vermelho', 'reta:amarelo'] },
    revista: { papel: 'revista', tinta: '#111', ent: 1.25, fontes: [['Archivo', 500, 800, .96, '', '-.01em'], ['Inter Tight', 500, 800, 1, '', '-.02em'], ['Familjen Grotesk', 500, 700, 1]], grifos: ['tarja:preto', 'marca:rosa', 'recorte:amarelo', 'reta:azul'] },
    caderno: { papel: 'caderno', tinta: '#1F3B8F', ent: 1.38, pauta: true, fontes: [['Caveat', 500, 700, 1.32], ['Kalam', 400, 700, 1.04]], grifos: ['circulo:vermelho', 'onda:vermelho', 'marca:verde', 'sublinhado:vermelho'] },
    maquina: { papel: 'maquina', tinta: '#262626', ent: 1.45, fontes: [['Special Elite', 400, 400, .9], ['Courier Prime', 400, 700, .94]], grifos: ['duplo:preto', 'caixa:preto', 'marca:amarelo', 'tracejado:vermelho'] },
    kraft:   { papel: 'kraft', tinta: '#1d1309', ent: 1.12, fontes: [['Bebas Neue', 400, 400, 1.22, 'up', '.01em'], ['Big Shoulders Display', 600, 900, 1.12, 'up'], ['Anton', 400, 400, 1.0, 'up']], grifos: ['recorte:branco', 'carimbo:vermelho', 'tarja:preto'] },
    livro:   { papel: 'livro', tinta: '#2b2118', ent: 1.4, fontes: [['Fraunces', 400, 700, 1], ['Young Serif', 400, 400, .98], ['DM Serif Display', 400, 400, 1.04]], grifos: ['sublinhado:lapis', 'colchete:lapis', 'marca:laranja', 'circulo:lapis'] },
    escuro:  { papel: 'escuro', tinta: '#ECE8DF', ent: 1.3, escuro: true, fontes: [['Syne', 500, 800, 1], ['Space Grotesk', 400, 700, 1], ['Unbounded', 400, 700, .84]], grifos: ['marca:lima', 'caixa:branco', 'sublinhado:amarelo', 'reta:amarelo'] },
    recibo:  { papel: 'recibo', tinta: '#383838', ent: 1.2, fontes: [['VT323', 400, 400, 1.34, 'up'], ['Space Mono', 400, 700, .86, 'up']], grifos: ['tracejado:preto', 'marca:rosa', 'tarja:preto'] },
    postit:  { papel: 'postit', tinta: '#1d1d1d', ent: 1.3, fontes: [['Permanent Marker', 400, 400, .98], ['Reenie Beanie', 400, 400, 1.5]], grifos: ['sublinhado:vermelho', 'circulo:vermelho', 'onda:azul'] },
    rosa:    { papel: 'rosa', tinta: '#26276a', ent: 1.26, fontes: [['Dela Gothic One', 400, 400, .82], ['Rubik Mono One', 400, 400, .78, 'up'], ['Bricolage Grotesque', 500, 800, 1]], grifos: ['marca:azul', 'sublinhado:azul', 'reta:amarelo'] },
  };

  const st = document.createElement('style');
  st.textContent = `
  .rc-box{position:absolute;inset:0;overflow:hidden;background:#000;display:none}
  .rc-cam{position:absolute;inset:0;transform-origin:50% 50%}
  .rc-pg{position:absolute;left:50%;top:50%;width:0;height:0;display:none}
  .rc-paper{position:absolute;left:-760px;top:-1160px;width:1520px;height:2320px;background-size:1520px 2320px}
  .rc-rl{position:absolute;white-space:nowrap;line-height:1}
  .rc-kw{position:relative;display:inline-block;isolation:isolate;padding:0 .1em}
  .rc-kt{position:relative;z-index:1}
  .rc-g{position:absolute;pointer-events:none}
  .rc-g svg{position:absolute;inset:0;width:100%;height:100%;overflow:visible}
  .rc-scan{position:absolute;inset:0;pointer-events:none;background:repeating-linear-gradient(0deg,rgba(20,15,5,.10) 0 2px,rgba(0,0,0,0) 2px 6px)}
  .rc-vig{position:absolute;inset:0;pointer-events:none}
  .rc-flash{position:absolute;inset:0;background:#fff;pointer-events:none;display:none}
  .rc-peca{position:absolute;left:0;top:0;transform-origin:50% 50%;filter:drop-shadow(10px 16px 14px rgba(0,0,0,.55))}
  .rc-peca .rc-pp{position:relative;padding:.2em .38em .26em;white-space:nowrap;line-height:1}
  .rc-peca .rc-pf{position:absolute;inset:0;background-size:1520px 2320px}
  `;
  document.head.appendChild(st);

  // ───────────── grifos (HTML dentro da palavra; r = rng, cor = nome de RC.CORES) ─────────────
  const J = (r, a) => (r() - .5) * 2 * a;                      // jitter ±a
  const pts = (l, n = 1) => l.map(p => p.map(v => v.toFixed(n)).join(',')).join(' ');
  const svg = (box, inner, extra = '') => `<i class="rc-g" style="${box}${extra}"><svg viewBox="0 0 100 100" preserveAspectRatio="none">${inner}</svg></i>`;
  const traco = (d, cor, w, o = '') => `<path d="${d}" fill="none" stroke="${cor}" stroke-width="${w}" stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke" ${o}/>`;
  RC.GRIFOS = {
    // marca-texto reto (o da referência): bloco chapado atrás da palavra
    reta: (r, c) => `<i class="rc-g" style="left:0;right:0;top:.08em;bottom:-.04em;background:${c};z-index:0"></i>`,
    // marca-texto de verdade: bordas irregulares, pontas inclinadas, multiplica com o papel
    marca: (r, c) => {
      const top = [], bot = []; for (let i = 0; i <= 6; i++) { const x = i / 6 * 100; top.push([x, 10 + J(r, 5)]); bot.push([x, 92 + J(r, 5)]); }
      top[0][0] = -2 + J(r, 2); bot[0][0] = 2 + J(r, 2); top[6][0] = 102 + J(r, 2); bot[6][0] = 98 + J(r, 2);
      return svg('left:-.08em;right:-.08em;top:.02em;bottom:-.06em;z-index:0;mix-blend-mode:multiply;', `<polygon points="${pts(top.concat(bot.reverse()))}" fill="${c}" opacity=".88"/>`);
    },
    sublinhado: (r, c) => svg('left:-.04em;right:-.04em;bottom:-.16em;height:.22em;', traco(`M${J(r, 2)},${50 + J(r, 20)} Q50,${50 + J(r, 40)} ${100 + J(r, 3)},${45 + J(r, 20)}`, c, c === RC.CORES.lapis ? 5 : 8, 'opacity=".92"')),
    duplo: (r, c) => svg('left:-.02em;right:-.02em;bottom:-.2em;height:.24em;', traco(`M0,${20 + J(r, 8)} L100,${18 + J(r, 8)}`, c, 5) + traco(`M2,${82 + J(r, 8)} L98,${80 + J(r, 8)}`, c, 5)),
    onda: (r, c) => { let d = `M0,50`; const n = 5 + Math.floor(r() * 3); for (let i = 0; i < n; i++) { const x0 = i / n * 100, x1 = (i + .5) / n * 100, x2 = (i + 1) / n * 100; d += ` Q${x0 + (x1 - x0) / 2},${5 + J(r, 6)} ${x1},50 Q${x1 + (x2 - x1) / 2},${95 + J(r, 6)} ${x2},50`; }
      return svg('left:0;right:0;bottom:-.24em;height:.2em;', traco(d, c, 6)); },
    circulo: (r, c) => { let d = ''; const a0 = -2.4 + J(r, .3), turns = 1.12 + r() * .12, n = 40;
      for (let i = 0; i <= n; i++) { const a = a0 + i / n * Math.PI * 2 * turns, rr = 1 + J(r, .05) + i / n * .06; d += (i ? ' L' : 'M') + (50 + Math.cos(a) * 50 * rr).toFixed(1) + ',' + (50 + Math.sin(a) * 50 * rr).toFixed(1); }
      return svg('left:-.22em;right:-.22em;top:-.16em;bottom:-.14em;z-index:2;', traco(d, c, c === RC.CORES.lapis ? 4.5 : 7, 'opacity=".9"')); },
    caixa: (r, c) => svg('left:-.12em;right:-.12em;top:-.02em;bottom:-.1em;z-index:2;', traco(`M${-3 + J(r, 2)},${J(r, 4)} L${103 + J(r, 2)},${J(r, 4)} L${100 + J(r, 2)},${100 + J(r, 4)} L${J(r, 2)},${100 + J(r, 4)} Z M${-2},${4 + J(r, 3)} L${6},${J(r, 3)}`, c, 5)),
    tracejado: (r, c) => `<i class="rc-g" style="left:-.1em;right:-.1em;top:0;bottom:-.08em;border:5px dashed ${c};z-index:2"></i>`,
    colchete: (r, c) => svg('left:-.22em;right:-.22em;top:-.06em;bottom:-.12em;z-index:2;', traco('M10,2 L2,2 L2,98 L10,98', c, 5) + traco('M90,2 L98,2 L98,98 L90,98', c, 5)),
    // tarja invertida: barra escura, a palavra na cor do papel
    tarja: (r, c, m) => `<i class="rc-g" style="left:-.04em;right:-.04em;top:.04em;bottom:-.06em;background:${c};transform:rotate(${J(r, 1.2).toFixed(2)}deg);z-index:0"></i>`,
    // recorte colado por cima: pedaço de papel recortado com a palavra, sombra e giro
    recorte: (r, c) => { const p = []; for (let i = 0; i <= 8; i++) p.push([i / 8 * 100, J(r, 6)]); for (let i = 0; i <= 2; i++) p.push([100 + J(r, 3), i / 2 * 100]); for (let i = 8; i >= 0; i--) p.push([i / 8 * 100, 100 + J(r, 6)]); for (let i = 2; i >= 0; i--) p.push([J(r, 3), i / 2 * 100]);
      return svg(`left:-.16em;right:-.16em;top:-.06em;bottom:-.12em;z-index:0;transform:rotate(${J(r, 3).toFixed(2)}deg);filter:drop-shadow(4px 7px 4px rgba(0,0,0,.35));`, `<polygon points="${pts(p)}" fill="${c}"/>`); },
    carimbo: (r, c) => svg(`left:-.16em;right:-.16em;top:-.08em;bottom:-.14em;z-index:2;transform:rotate(${(-3 + J(r, 2)).toFixed(2)}deg);`, `<rect x="0" y="0" width="100" height="100" rx="4" fill="none" stroke="${c}" stroke-width="7" vector-effect="non-scaling-stroke" opacity=".85" filter="url(#rc-gasto)"/>`),
  };
  // grifos que mudam a cor do texto da palavra
  const corTexto = (tipo, c, M) => tipo === 'tarja' ? (M.escuro ? '#111' : '#F4F1EA') : tipo === 'carimbo' ? c : (M.escuro && /reta|marca/.test(tipo)) ? '#111' : null;

  // filtros SVG globais (carimbo gasto)
  const DEFS = `<svg width="0" height="0" style="position:absolute"><defs>
    <filter id="rc-gasto" x="-10%" y="-10%" width="120%" height="120%"><feTurbulence type="fractalNoise" baseFrequency=".9" numOctaves="2" seed="4"/><feColorMatrix values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 -2.2 1.6"/><feComposite in="SourceGraphic" operator="in"/></filter>
  </defs></svg>`;
  let defsOk = false; const defs = () => { if (!defsOk) { K.html(document.body, DEFS); defsOk = true; } };

  // palavra grifada (HTML): usado nas páginas e nas peças da colagem
  RC.palavra = (palavra, M, fonte, grifo, r) => {
    const [tipo, cn = 'amarelo'] = grifo.split(':'), c = RC.CORES[cn] || cn;
    const ct = corTexto(tipo, c, M);
    return `<span class="rc-kw" style="font-weight:${fonte[2]}">${RC.GRIFOS[tipo](r, c, M)}<span class="rc-kt"${ct ? ` style="color:${ct}"` : ''}>${palavra}</span></span>`;
  };

  // ───────────── página: papel + coluna de texto com a palavra grifada no centro da tela ─────────────
  // spec = {material, fonte (índice), grifo, antes, depois, topo, corpo:[11 linhas], tam, seed}
  RC.pagina = (pai, palavra, spec) => {
    const M = RC.MATERIAIS[spec.material], F = M.fontes[spec.fonte % M.fontes.length], r = K.rng(spec.seed || 1);
    const tam = (spec.tam || 118) * F[3], L = tam * M.ent;
    const el = K.html(pai, `<div class="rc-pg"><div class="rc-paper" style="background-image:url(${RC.papel(M.papel)});background-position:${Math.round(r() * 1500)}px ${Math.round(r() * 2300)}px"></div></div>`);
    if (M.pauta) el.insertAdjacentHTML('beforeend', `<div style="position:absolute;left:-760px;top:${-6 * L}px;width:1520px;height:${12 * L}px;background:repeating-linear-gradient(180deg,rgba(0,0,0,0) 0 ${L - 3}px,rgba(70,120,200,.38) ${L - 3}px ${L}px);background-position:0 ${(tam * .48).toFixed(1)}px"></div>`);
    const ln = [], txt = s => F[4] === 'up' ? s.toUpperCase() : s;
    const base = `font-family:'${F[0]}';font-size:${tam.toFixed(1)}px;color:${M.tinta};letter-spacing:${F[5] || 'normal'};`;
    for (let k = -5; k <= 5; k++) {
      const d = Math.abs(k), cab = k === -1 && spec.topo;
      const e = K.html(el, `<div class="rc-rl" style="${base}font-weight:${cab ? F[2] : F[1]};top:${(k * L - tam * .55).toFixed(1)}px;${cab && M.cab ? `font-size:${(tam * M.cab).toFixed(1)}px;` : ''}"></div>`);
      if (k === 0) {
        const kwTxt = txt(palavra), dep = spec.depois ? (/^[,.;:!?]/.test(spec.depois) ? '' : ' ') + txt(spec.depois) : '';
        e.innerHTML = `${spec.antes ? txt(spec.antes) + ' ' : ''}${RC.palavra(kwTxt, M, F, spec.grifo, r)}${dep}`;
      } else e.textContent = txt(cab ? spec.topo : spec.corpo[(k + 5) % spec.corpo.length]);
      e.style.filter = d ? `blur(${(d * 1.8).toFixed(1)}px)` : '';                                   // profundidade de campo
      e.style.opacity = 1 - Math.min(.4, d * .07);
      e.style.textShadow = `-${4 + d * 1.5}px 0 rgba(255,30,30,.42), ${4 + d * 1.5}px 0 rgba(0,200,255,.42)`;  // aberração cromática
      ln.push(e);
    }
    if (M.pauta) el.insertAdjacentHTML('beforeend', `<div class="rc-margem" style="position:absolute;top:-1160px;height:2320px;width:4px;background:rgba(215,50,50,.45)"></div>`);
    return { el, ln, kw: ln[5].querySelector('.rc-kw'), M, F, spec };
  };

  // ───────────── montagem de UMA palavra ─────────────
  // o = {palavra, frases:[[antes, depois, topo?], …], de, quadros:[…] (ou n + q + segura), materiais:[…] (sorteio sem repetir; ordem:'lista' segue a ordem),
  //      grifos:[…] (força uma lista), zoom:[1,1.55], giro:[0,-7], vinheta:[.95,.5], tam:118, seed, corpo:[frases…]}
  RC.CORPO = ['Quem anda pela cidade sabe que', 'o começo de tudo é pequeno,', 'uma linha escrita à mão num', 'caderno esquecido no fundo da gaveta.',
    'Cada página guarda um jeito', 'próprio de contar a mesma coisa', 'e quem lê de novo sempre encontra', 'um detalhe que tinha passado.',
    'O texto certo é o que cabe', 'no tempo de quem está lendo.', 'Entre uma frase e outra existe', 'um silêncio que também conta.'];
  RC.TOPOS = ['Início / Ideias / Texto', 'Edição de hoje', 'Capítulo um', 'Nota do editor', 'Caderno de cultura', 'Rascunho', 'Página 12',
    'Diário de bordo', 'Especial', 'Crônica', 'Arquivo', 'Lista de hoje'];
  RC.montagem = (box, o) => {
    const fps = V.fps, de = o.de ?? 0, r = K.rng(o.seed ?? 7);
    const n = o.frases.length;
    const quadros = o.quadros || o.frases.map((_, i) => (i === n - 1 ? (o.segura ?? 9) : (o.q ?? 3)));
    const nomes = o.materiais || Object.keys(RC.MATERIAIS);
    let ult = null;
    const pags = o.frases.map((f, i) => {
      let mat = o.ordem === 'lista' ? nomes[i % nomes.length] : nomes[Math.floor(r() * nomes.length)];
      if (mat === ult && nomes.length > 1) mat = nomes[(nomes.indexOf(mat) + 1) % nomes.length];
      if (f.material) mat = f.material;
      ult = mat;
      const M = RC.MATERIAIS[mat], gl = o.grifos || M.grifos;
      const corpo = []; for (let k = 0; k < 11; k++) corpo.push((o.corpo || RC.CORPO)[Math.floor(r() * (o.corpo || RC.CORPO).length)]);
      const fr = Math.floor(r() * 9);
      return RC.pagina(box.cam, o.palavra, { material: mat, fonte: f.fonte ?? fr, grifo: f.grifo || gl[Math.floor(r() * gl.length)],
        antes: f[0], depois: f[1], topo: f[2] ?? (r() < .55 ? RC.TOPOS[Math.floor(r() * RC.TOPOS.length)] : ''), corpo, tam: (o.tam ?? 118) * (.92 + r() * .16), seed: (o.seed ?? 7) * 100 + i });
    });
    const ini = []; let acc = 0; quadros.forEach(q => { ini.push(de + acc / fps); acc += q; });
    const M = { de, fim: de + acc / fps, ini, quadros, pags, o, giroSinal: o.giro ? 1 : (r() < .5 ? -1 : 1) };
    box.montagens.push(M);
    ini.forEach((ti, i) => cue('clique', ti, { gain: i === n - 1 ? 0 : -3 - (i % 2) * 2, var: i % 4 }));
    cue('fita', de, { d: M.fim - de, cortes: ini.map(x => +(x - de).toFixed(3)), tom: o.tom ?? 0 });
    return M;
  };

  // ───────────── caixa (palco) que roda as montagens: lente velha por cima ─────────────
  // RC.palco(pai) → {el, cam, montagens}; chame RC.montagem(palco, …) quantas vezes quiser (em sequência)
  RC.palcos = [];
  RC.palco = (pai, o = {}) => {
    defs();
    const el = K.html(pai, `<div class="rc-box"><div class="rc-cam"></div><div class="rc-scan"></div><div class="rc-vig"></div><div class="rc-flash"></div></div>`);
    const P = { el, cam: el.children[0], scan: el.children[1], vig: el.children[2], flash: el.children[3], montagens: [], o };
    if (o.varredura === false) P.scan.style.display = 'none';
    RC.palcos.push(P);
    onTick(t => {
      const M = P.montagens.find(m => t >= m.de && t < m.fim);
      el.style.display = M ? 'block' : 'none';
      P.montagens.forEach(m => m.pags.forEach(p => (p.el.style.display = 'none')));
      if (!M) return;
      const f = Math.floor((t - M.de) * V.fps + 1e-6); let i = 0, a = 0;
      for (; i < M.quadros.length - 1; i++) { if (f < a + M.quadros[i]) break; a += M.quadros[i]; }
      const pg = M.pags[i]; pg.el.style.display = 'block';
      const n = M.quadros.length, u = (f - a + .5) / M.quadros[i], k = n > 1 ? i / (n - 1) : 0, r = K.rng(i * 977 + 3 + Math.round(M.de * 100));
      const zz = M.o.zoom || [1, 1.55], gg = M.o.giro || [0, -7 * M.giroSinal], vv = M.o.vinheta || [.95, .5];
      const empurra = (M.o.empurra ?? .045) * (1 + 1.8 * k);                 // empurrão dentro do recorte, cada vez mais rápido
      const z = K.lerp(zz[0], zz[1], Math.pow(k, 1.25)) * (1 + empurra * u);
      const g = K.lerp(gg[0], gg[1], Math.pow(k, 1.4)) + J(r, 1.2);
      P.cam.style.transform = `translate(${J(r, 22).toFixed(1)}px,${J(r, 16).toFixed(1)}px) scale(${z.toFixed(4)}) rotate(${g.toFixed(2)}deg)`;
      const vg = K.lerp(vv[0], vv[1], k);
      P.vig.style.background = `radial-gradient(ellipse 78% 60% at 50% 50%,rgba(0,0,0,0) 52%,rgba(10,6,0,${(vg * .55).toFixed(3)}) 80%,rgba(6,4,0,${vg.toFixed(3)}) 100%)`;
      P.cam.style.filter = pg.M.escuro ? 'contrast(1.05)' : 'sepia(.16) contrast(1.06)';
      const primeiro = i === 0 && f === a && (M.o.estouro ?? true);            // 1º quadro estourado (claro), como na referência
      P.flash.style.display = primeiro ? 'block' : 'none'; P.flash.style.opacity = .55;
    });
    return P;
  };

  // ───────────── frase: uma montagem por palavra, em sequência ─────────────
  // o = {palavras:[{palavra, frases:[[antes,depois,topo?]…], materiais?, grifos?}], de, q:3, segura:9, tam, zoom, seed}
  RC.frase = (palco, o) => {
    let t = o.de ?? 0; const out = [];
    o.palavras.forEach((w, i) => {
      const M = RC.montagem(palco, Object.assign({ q: o.q ?? 3, segura: o.segura ?? 9, tam: o.tam, zoom: o.zoom, vinheta: o.vinheta, empurra: o.empurra,
        seed: (o.seed ?? 11) + i * 31, tom: i, giro: o.giro ? o.giro.map(g => g * (i % 2 ? -1 : 1)) : undefined }, w, { de: t }));
      out.push(M); t = M.fim;
    });
    return { montagens: out, fim: t };
  };

  // ───────────── medidas (SETUP): alinha a coluna para a palavra grifada ficar no centro ─────────────
  RC.medir = () => {
    RC.palcos.forEach(P => {
      P.el.style.display = 'block';
      P.montagens.forEach(M => M.pags.forEach(p => {
        p.el.style.display = 'block';
        const x0 = -(p.kw.offsetLeft + p.kw.offsetWidth / 2);
        p.ln.forEach(e => (e.style.left = x0 + 'px'));
        const mg = p.el.querySelector('.rc-margem'); if (mg) mg.style.left = (x0 - 40) + 'px';
        p.el.style.display = 'none';
      }));
      P.el.style.display = 'none';
    });
    RC.pecas.forEach(f => f());
  };

  // ───────────── colagem final: as palavras viram recortes colados (bilhete de recortes) ─────────────
  // itens = [{palavra, pagina (de uma montagem: usa o mesmo papel/fonte/grifo) | material/fonte/grifo}], o = {de, passo, fundo:'escuro', tam, giros}
  RC.pecas = [];
  RC.colagem = (pai, itens, o = {}) => {
    defs();
    const el = K.html(pai, `<div class="rc-box"><div class="rc-cam" style="background:url(${RC.papel(o.fundo || 'escuro')}) center/1520px 2320px"></div><div class="rc-scan"></div><div class="rc-vig" style="background:radial-gradient(ellipse 80% 62% at 50% 50%,rgba(0,0,0,0) 50%,rgba(0,0,0,.75) 100%)"></div></div>`);
    const cam = el.children[0], tam = o.tam ?? 150, r = K.rng(o.seed ?? 5);
    const pecas = itens.map((it, i) => {
      const pg = it.pagina, M = pg ? pg.M : RC.MATERIAIS[it.material], F = pg ? pg.F : M.fontes[(it.fonte || 0) % M.fontes.length];
      const grifo = pg ? pg.spec.grifo : it.grifo;
      const txt = F[4] === 'up' ? it.palavra.toUpperCase() : it.palavra;
      const p = K.html(cam, `<div class="rc-peca"><div class="rc-pf" style="background-image:url(${RC.papel(M.papel)});background-position:${Math.round(r() * 1400)}px ${Math.round(r() * 2200)}px"></div><div class="rc-pp" style="font-family:'${F[0]}';font-size:${(tam * F[3] * (it.esc ?? 1)).toFixed(1)}px;color:${M.tinta};letter-spacing:${F[5] || 'normal'}">${RC.palavra(txt, M, F, grifo, K.rng(i * 13 + 2))}</div></div>`);
      // borda recortada à tesoura (polígono com pequenos dentes)
      const pts = []; const nx = 9, ny = 4;
      for (let k = 0; k <= nx; k++) pts.push(`${(k / nx * 100).toFixed(1)}% ${(J(r, 2.5) + 2).toFixed(1)}%`);
      for (let k = 1; k <= ny; k++) pts.push(`${(98 + J(r, 1.5)).toFixed(1)}% ${(k / ny * 100).toFixed(1)}%`);
      for (let k = nx; k >= 0; k--) pts.push(`${(k / nx * 100).toFixed(1)}% ${(98 + J(r, 2.5)).toFixed(1)}%`);
      for (let k = ny; k >= 1; k--) pts.push(`${(2 + J(r, 1.5)).toFixed(1)}% ${(k / ny * 100).toFixed(1)}%`);
      p.querySelector('.rc-pf').style.clipPath = `polygon(${pts.join(',')})`;
      return { p, giro: (o.giros && o.giros[i]) ?? J(r, 5), dx: J(r, 60) };
    });
    // layout (SETUP): pilha centralizada, com deslocamentos e giros de bilhete
    RC.pecas.push(() => {
      el.style.display = 'block';
      const hs = pecas.map(q => q.p.offsetHeight), ws = pecas.map(q => q.p.offsetWidth), gap = o.gap ?? 18;
      const H = hs.reduce((a, b) => a + b, 0) + gap * (pecas.length - 1); let y = (o.centro ?? V.h / 2) - H / 2;
      pecas.forEach((q, i) => { q.x = V.w / 2 - ws[i] / 2 + q.dx; q.y = y; y += hs[i] + gap; });
      el.style.display = 'none';
    });
    const ts = itens.map((_, i) => (o.de ?? 0) + i * (o.passo ?? .4));
    onTick(t => {
      const on = t >= (o.de ?? 0) && t < (o.ate ?? V.dur); el.style.display = on ? 'block' : 'none'; if (!on) return;
      cam.style.transform = `scale(${(1 + .05 * K.ease('sine.inOut', K.seg(t, o.de ?? 0, o.ate ?? V.dur))).toFixed(4)})`;
      pecas.forEach((q, i) => {
        const t0 = ts[i]; if (t < t0) { q.p.style.display = 'none'; return; }
        q.p.style.display = 'block';
        const u = K.seg(t, t0, t0 + .13), st = Math.min(1, Math.floor(u * 4) / 3);        // "tapa" de stop-motion em 4 degraus
        const s = 1.32 - .32 * st;
        q.p.style.transform = `translate(${q.x.toFixed(1)}px,${q.y.toFixed(1)}px) rotate(${(q.giro * (1 + .6 * (1 - st))).toFixed(2)}deg) scale(${s.toFixed(3)})`;
      });
    });
    ts.forEach((t, i) => cue('tapa', t, { var: i }));
    return { el, ts };
  };
})();
