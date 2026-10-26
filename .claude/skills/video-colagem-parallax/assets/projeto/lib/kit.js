// Ferramentas de motion compartilhadas. Tudo entra na linha do tempo TL (nada toca sozinho).
const K = (window.K = {});
K.rng = seed => () => { seed |= 0; seed = (seed + 0x6d2b79f5) | 0; let t = Math.imul(seed ^ (seed >>> 15), 1 | seed); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
K.$ = (s, r = document) => r.querySelector(s);
K.$$ = (s, r = document) => [...r.querySelectorAll(s)];
K.clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
K.seg = (t, a, b) => K.clamp((t - a) / (b - a));
K.lerp = (a, b, k) => a + (b - a) * k;
K.ease = (name, v) => gsap.parseEase(name)(K.clamp(v));
K.smooth = v => { v = K.clamp(v); return v * v * v * (v * (v * 6 - 15) + 10); };
K.noise = (() => { // ruído de valor 1D/2D suave e determinístico
  const p = new Uint8Array(512), r = K.rng(1337); const a = [...Array(256).keys()].sort(() => r() - 0.5); for (let i = 0; i < 512; i++) p[i] = a[i & 255];
  const g = (h, x, y) => ((h & 1 ? x : -x) + (h & 2 ? y : -y));
  return (x, y = 0) => { const X = Math.floor(x) & 255, Y = Math.floor(y) & 255; x -= Math.floor(x); y -= Math.floor(y); const u = K.smooth(x), v = K.smooth(y);
    const A = p[X] + Y, Bb = p[X + 1] + Y; return K.lerp(K.lerp(g(p[A], x, y), g(p[Bb], x - 1, y), u), K.lerp(g(p[A + 1], x, y - 1), g(p[Bb + 1], x - 1, y - 1), u), v) * 0.7; };
})();

CustomEase.create('out', 'M0,0 C0.16,1 0.3,1 1,1');          // saída rápida e assentada
CustomEase.create('io', 'M0,0 C0.7,0 0.1,1 1,1');            // in-out dramático
CustomEase.create('snap', 'M0,0 C0.5,0 0.05,1 1,1');
CustomEase.create('whip', 'M0,0 C0.9,0 0.1,1 1,1');          // chicote de câmera
CustomEase.create('soft', 'M0,0 C0.45,0 0.2,1 1,1');

K.split = (el, type = 'chars,words,lines', o = {}) => SplitText.create(el, Object.assign({ type, mask: o.mask === undefined ? 'lines' : o.mask, linesClass: 'sx-ln', wordsClass: 'sx-wd', charsClass: 'sx-ch', aria: 'none' }, o));

// revelações mascaradas
K.rise = (tg, at, o = {}) => TL.from(tg, { yPercent: o.y ?? 115, rotate: o.r ?? 0, duration: o.d ?? 0.9, ease: o.ease ?? 'out', stagger: o.s ?? 0.035 }, at);
K.sink = (tg, at, o = {}) => TL.to(tg, { yPercent: o.y ?? -115, duration: o.d ?? 0.55, ease: o.ease ?? 'power3.in', stagger: o.s ?? 0.02 }, at);
K.blurIn = (tg, at, o = {}) => TL.fromTo(tg, { opacity: 0, filter: `blur(${o.b ?? 24}px)`, scale: o.sc ?? 1.08 }, { opacity: 1, filter: 'blur(0px)', scale: 1, duration: o.d ?? 1.1, ease: o.ease ?? 'out', stagger: o.s ?? 0.04 }, at);
K.blurOut = (tg, at, o = {}) => TL.to(tg, { opacity: 0, filter: `blur(${o.b ?? 20}px)`, scale: o.sc ?? 0.96, duration: o.d ?? 0.5, ease: 'power2.in', stagger: o.s ?? 0.02 }, at);
K.show = (tg, at) => TL.set(tg, { autoAlpha: 1 }, at);
K.hide = (tg, at) => TL.set(tg, { autoAlpha: 0 }, at);
K.wipe = (tg, at, o = {}) => { const from = { l: 'inset(0 100% 0 0)', r: 'inset(0 0 0 100%)', u: 'inset(100% 0 0 0)', d: 'inset(0 0 100% 0)' }[o.dir || 'l']; return TL.fromTo(tg, { clipPath: from }, { clipPath: 'inset(0 0% 0 0)', duration: o.d ?? 0.8, ease: o.ease ?? 'io' }, at); };
K.count = (el, from, to, at, d, fmt = v => Math.round(v).toLocaleString('pt-BR')) => { const o = { v: from }; el.textContent = fmt(from); return TL.to(o, { v: to, duration: d, ease: 'power3.out', onUpdate: () => (el.textContent = fmt(o.v)) }, at); };
K.type = (el, str, at, cps = 28, o = {}) => { const s = { n: 0 }; const caret = o.caret ? '<span class="caret"></span>' : '';
  TL.to(s, { n: str.length, duration: str.length / cps, ease: 'none', onUpdate: () => (el.innerHTML = esc(str.slice(0, Math.round(s.n))) + caret) }, at); return at + str.length / cps; };
const esc = s => s.replace(/&/g, '&amp;').replace(/</g, '&lt;');

// grão de filme animado (canvas em baixa resolução, determinístico por quadro)
K.grain = (parent, o = {}) => {
  const c = document.createElement('canvas'), w = o.w ?? 480, h = Math.round(w * VIDEO.h / VIDEO.w);
  c.width = w; c.height = h; c.className = 'grain'; c.style.opacity = o.opacity ?? 0.35; if (o.blend) c.style.mixBlendMode = o.blend; parent.appendChild(c);
  const x = c.getContext('2d'), img = x.createImageData(w, h);
  onTick(t => { const r = K.rng(Math.floor(t * VIDEO.fps) * 7919 + 1); const d = img.data; for (let i = 0; i < d.length; i += 4) { const v = 128 + (r() + r() + r() - 1.5) * 120; d[i] = d[i + 1] = d[i + 2] = v; d[i + 3] = 255; } x.putImageData(img, 0, 0); });
  return c;
};

K.html = (parent, s) => { const t = document.createElement('template'); t.innerHTML = s.trim(); const n = [...t.content.childNodes]; n.forEach(c => parent.appendChild(c)); return n.length === 1 ? n[0] : n; };

// textura procedural → dataURL (fn recebe ctx, w, h, rng)
K.texture = (w, h, fn, seed = 1) => { const c = document.createElement('canvas'); c.width = w; c.height = h; const x = c.getContext('2d'); fn(x, w, h, K.rng(seed)); return c.toDataURL('image/png'); };
K.paperTex = (base = '#efe8da', seed = 3) => K.texture(512, 512, (x, w, h, r) => {
  x.fillStyle = base; x.fillRect(0, 0, w, h);
  for (let i = 0; i < 9000; i++) { const v = r(); x.fillStyle = `rgba(${v < .5 ? '60,45,20' : '255,255,255'},${r() * .05})`; x.fillRect(r() * w, r() * h, 1 + r() * 2, 1 + r() * 2); }
  x.strokeStyle = 'rgba(90,70,40,.05)'; for (let i = 0; i < 160; i++) { x.beginPath(); const a = r() * w, b = r() * h; x.moveTo(a, b); x.lineTo(a + (r() - .5) * 40, b + (r() - .5) * 40); x.stroke(); }
}, seed);

// cursor com clique
K.cursor = (parent, o = {}) => {
  const c = K.html(parent, `<svg class="cursor" viewBox="0 0 32 32"><path d="M6 3 L6 25 L11.5 19.8 L15.4 28.6 L19.2 27 L15.4 18.3 L22.8 18.3 Z" fill="${o.fill ?? '#111'}" stroke="${o.stroke ?? '#fff'}" stroke-width="1.8" stroke-linejoin="round"/></svg>`);
  const rp = K.html(parent, `<div class="ripple"></div>`);
  gsap.set(c, { x: o.x ?? 2000, y: o.y ?? 1200 }); gsap.set(rp, { x: o.x ?? 2000, y: o.y ?? 1200 });
  return {
    el: c,
    to: (x, y, at, d = .8, ease = 'io') => { TL.to(c, { x: x - 6, y: y - 3, duration: d, ease }, at); TL.set(rp, { x, y }, at + d); return at + d; },
    click: (at, snd = true) => { TL.to(c, { scale: .82, duration: .08, ease: 'power2.out', transformOrigin: '6px 3px' }, at); TL.to(c, { scale: 1, duration: .25, ease: 'back.out(3)' }, at + .08);
      TL.fromTo(rp, { scale: .3, opacity: .7 }, { scale: 2.6, opacity: 0, duration: .55, ease: 'out' }, at); if (snd) cue('click', at); return at; },
  };
};
// palavra que troca girando no lugar (efeito caça-níquel)
K.slot = (el, words, at, step, o = {}) => {
  el.innerHTML = `<span style="display:inline-grid;overflow:hidden;vertical-align:bottom;height:${o.h ?? '1.15em'}"><span class="slot-in" style="display:flex;flex-direction:column">${words.map(w => `<span style="height:${o.h ?? '1.15em'};white-space:nowrap">${w}</span>`).join('')}</span></span>`;
  const inn = el.querySelector('.slot-in');
  words.forEach((w, i) => { if (i) { TL.to(inn, { yPercent: -100 * i / words.length, duration: o.d ?? .45, ease: o.ease ?? 'expo.inOut' }, at + (i - 1) * step); if (o.snd !== false) cue('tick', at + (i - 1) * step + .2); } });
};
// posição de layout (ignora transforms) de el relativa a root
K.pos = (el, root) => { let x = 0, y = 0, n = el; while (n && n !== root) { x += n.offsetLeft; y += n.offsetTop; n = n.offsetParent; } return { x, y, w: el.offsetWidth, h: el.offsetHeight, cx: x + el.offsetWidth / 2, cy: y + el.offsetHeight / 2 }; };

// entrada segura de algo escondido: autoAlpha 0→1 + propriedades extras
K.enter = (tg, at, from = {}, o = {}) => TL.fromTo(tg, Object.assign({ autoAlpha: 0 }, from), Object.assign({ autoAlpha: 1, x: 0, y: 0, scale: 1, rotate: 0, filter: 'blur(0px)', duration: o.d ?? .7, ease: o.ease ?? 'out', immediateRender: false }, o.to || {}), at);

// shader de tela cheia (WebGL2). frag recebe uT (tempo), uR (resolução), uP (vec4 de parâmetros animáveis via S.p)
K.GLSL = `
float h21(vec2 p){p=fract(p*vec2(123.34,456.21));p+=dot(p,p+45.32);return fract(p.x*p.y);}
float vnoise(vec2 p){vec2 i=floor(p),f=fract(p);vec2 u=f*f*(3.-2.*f);return mix(mix(h21(i),h21(i+vec2(1,0)),u.x),mix(h21(i+vec2(0,1)),h21(i+vec2(1,1)),u.x),u.y);}
float fbm(vec2 p){float v=0.,a=.5;mat2 m=mat2(1.6,1.2,-1.2,1.6);for(int i=0;i<6;i++){v+=a*vnoise(p);p=m*p;a*=.5;}return v;}
vec3 pal(float t,vec3 a,vec3 b,vec3 c,vec3 d){return a+b*cos(6.28318*(c*t+d));}
`;
K.shader = (parent, frag, o = {}) => {
  const c = document.createElement('canvas'); c.width = VIDEO.w; c.height = VIDEO.h; c.className = 'layer'; if (o.style) c.style.cssText += o.style;
  o.append ? parent.appendChild(c) : parent.prepend(c);
  const gl = c.getContext('webgl2', { preserveDrawingBuffer: true, antialias: false });
  const sh = (type, src) => { const s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s); if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s)); return s; };
  const pr = gl.createProgram();
  gl.attachShader(pr, sh(gl.VERTEX_SHADER, '#version 300 es\nin vec2 p;void main(){gl_Position=vec4(p,0,1);}'));
  gl.attachShader(pr, sh(gl.FRAGMENT_SHADER, '#version 300 es\nprecision highp float;uniform float uT;uniform vec2 uR;uniform vec4 uP;uniform vec4 uQ;out vec4 o;' + K.GLSL + frag));
  gl.linkProgram(pr); gl.useProgram(pr);
  const b = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, b); gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
  const loc = gl.getAttribLocation(pr, 'p'); gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
  const U = n => gl.getUniformLocation(pr, n), S = { c, p: { x: 0, y: 0, z: 0, w: 0 }, q: { x: 0, y: 0, z: 0, w: 0 } };
  onTick(t => { gl.viewport(0, 0, c.width, c.height); gl.uniform1f(U('uT'), t); gl.uniform2f(U('uR'), c.width, c.height);
    gl.uniform4f(U('uP'), S.p.x, S.p.y, S.p.z, S.p.w); gl.uniform4f(U('uQ'), S.q.x, S.q.y, S.q.z, S.q.w); gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4); });
  return S;
};
