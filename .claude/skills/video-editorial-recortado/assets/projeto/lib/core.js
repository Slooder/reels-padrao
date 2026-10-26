// Núcleo de tempo: tudo é função de t. Cada vídeo define window.VIDEO = {w,h,fps,dur,bpm}
// e monta a linha do tempo em TL (GSAP, pausada). Camadas canvas/WebGL usam onTick(fn(t)).
(function () {
  const V = (window.VIDEO = Object.assign({ w: 1920, h: 1080, fps: 60, dur: 15, bpm: 120 }, window.VIDEO || {}));
  gsap.registerPlugin(...['SplitText', 'CustomEase', 'DrawSVGPlugin', 'MorphSVGPlugin', 'ScrambleTextPlugin', 'MotionPathPlugin', 'TextPlugin', 'Physics2DPlugin', 'CustomWiggle'].map(n => window[n]).filter(Boolean));
  gsap.ticker.lagSmoothing(0);
  const TL = (window.TL = gsap.timeline({ paused: true }));
  const ticks = [];
  const cues = (window.__cues = []);
  window.onTick = fn => ticks.push(fn);
  // marcação de som: cue('whoosh', t, {gain, pan, pitch})
  window.cue = (type, t, o = {}) => (cues.push(Object.assign({ type, t }, o)), t);
  window.B = n => (n * 60) / V.bpm; // batidas → segundos
  window.CTA = ['ASSINE A CRIA BR', 'APENAS R$ 1 PARA TESTAR', 'SIGA @LEOLAMERABR'];

  document.documentElement.style.setProperty('--w', V.w + 'px');
  document.documentElement.style.setProperty('--h', V.h + 'px');

  let cur = 0;
  window.__seek = async t => {
    cur = t;
    TL.totalTime(Math.min(t, Math.max(TL.duration(), 0.0001)));
    for (const fn of ticks) await fn(t);
  };

  window.__boot = async () => {
    await document.fonts.ready;
    // força o carregamento de todas as fontes usadas na página
    await Promise.all([...document.fonts].map(f => f.load().catch(() => 0)));
    if (window.SETUP) await window.SETUP();
    await window.__seek(0);
    window.__ready = true;
  };

  // Pré-visualização no navegador (fora da renderização): toca em tempo real, espaço pausa, ←/→ navega
  window.addEventListener('load', async () => {
    await window.__boot();
    if (window.__render) return;
    const st = document.getElementById('stage');
    const fit = () => { const k = Math.min(innerWidth / V.w, innerHeight / V.h); st.style.transform = `translate(${(innerWidth - V.w * k) / 2}px,${(innerHeight - V.h * k) / 2}px) scale(${k})`; };
    fit(); addEventListener('resize', fit);
    let playing = true, t0 = performance.now() - cur * 1000;
    addEventListener('keydown', e => {
      if (e.code === 'Space') { playing = !playing; t0 = performance.now() - cur * 1000; }
      if (e.code === 'ArrowRight') { cur = Math.min(V.dur, cur + 0.5); t0 = performance.now() - cur * 1000; __seek(cur); }
      if (e.code === 'ArrowLeft') { cur = Math.max(0, cur - 0.5); t0 = performance.now() - cur * 1000; __seek(cur); }
    });
    const loop = async () => { if (playing) await __seek(((performance.now() - t0) / 1000) % V.dur); requestAnimationFrame(loop); };
    loop();
  });
})();
