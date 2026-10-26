// Carrega GSAP + plugins + núcleo na ordem certa (caminhos relativos à raiz do projeto)
(function () {
  const root = document.currentScript.src.replace(/lib\/boot\.js.*$/, '');
  const g = root + 'node_modules/gsap/dist/';
  const files = ['gsap.min.js', 'SplitText.min.js', 'CustomEase.min.js', 'CustomWiggle.min.js', 'DrawSVGPlugin.min.js', 'MorphSVGPlugin.min.js', 'ScrambleTextPlugin.min.js', 'MotionPathPlugin.min.js', 'TextPlugin.min.js', 'Physics2DPlugin.min.js'].map(f => g + f)
    .concat([root + 'lib/core.js', root + 'lib/kit.js']);
  document.write(`<link rel="stylesheet" href="${root}lib/kit.css">` + files.map(f => `<script src="${f}"><\/script>`).join(''));
})();
