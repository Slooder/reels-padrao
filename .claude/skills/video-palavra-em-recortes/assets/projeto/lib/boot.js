// Carrega GSAP + plugins + núcleo na ordem certa (caminhos relativos à raiz do projeto).
// Bibliotecas de estilo extras: declare antes do boot  <script>LIBS=['estilo.js']</script>  (arquivos em lib/).
(function () {
  const root = document.currentScript.src.replace(/lib\/boot\.js.*$/, '');
  const g = root + 'node_modules/gsap/dist/';
  const files = ['gsap.min.js', 'SplitText.min.js', 'CustomEase.min.js', 'CustomWiggle.min.js', 'DrawSVGPlugin.min.js', 'MorphSVGPlugin.min.js', 'ScrambleTextPlugin.min.js', 'MotionPathPlugin.min.js', 'TextPlugin.min.js', 'Physics2DPlugin.min.js'].map(f => g + f)
    .concat([root + 'lib/core.js', root + 'lib/kit.js']).concat((window.LIBS || []).map(f => root + 'lib/' + f));
  document.write(`<link rel="stylesheet" href="${root}lib/kit.css">` + files.map(f => `<script src="${f}"><\/script>`).join('') +
    `<script type="importmap">{"imports":{"three":"${root}node_modules/three/build/three.module.js","three/addons/":"${root}node_modules/three/examples/jsm/","kit3":"${root}lib/three-kit.js"}}<\/script>`);
})();
