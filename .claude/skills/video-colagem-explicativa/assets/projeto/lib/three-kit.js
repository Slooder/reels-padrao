// Palco 3D padrão: renderer determinístico + pós-processamento (bloom, grão, vinheta, aberração cromática).
import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
export { THREE };

const FinishShader = {
  uniforms: { tDiffuse: { value: null }, uTime: { value: 0 }, uGrain: { value: 0.06 }, uVig: { value: 0.35 }, uCA: { value: 0.0015 }, uRes: { value: new THREE.Vector2(1920, 1080) } },
  vertexShader: `varying vec2 vUv; void main(){ vUv=uv; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.); }`,
  fragmentShader: `uniform sampler2D tDiffuse; uniform float uTime,uGrain,uVig,uCA; varying vec2 vUv;
    float h(vec2 p){ return fract(sin(dot(p,vec2(12.9898,78.233)))*43758.5453); }
    void main(){ vec2 c=vUv-.5; float d=length(c);
      vec2 off=c*uCA*(1.+d*4.);
      vec3 col=vec3(texture2D(tDiffuse,vUv+off).r,texture2D(tDiffuse,vUv).g,texture2D(tDiffuse,vUv-off).b);
      col*=1.-uVig*smoothstep(.25,.85,d);
      col+=(h(vUv*vec2(1920.,1080.)+fract(uTime*7.13)*100.)-.5)*uGrain;
      gl_FragColor=vec4(col,1.); }`,
};

export function stage3D(o = {}) {
  const V = window.VIDEO;
  const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true, powerPreference: 'high-performance', alpha: !!o.alpha });
  renderer.setPixelRatio(1);
  renderer.setSize(V.w, V.h, false);
  renderer.toneMapping = o.toneMapping ?? THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = o.exposure ?? 1;
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  if (o.shadows) { renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap; }
  renderer.domElement.className = 'layer';
  (o.parent || document.getElementById('stage')).prepend(renderer.domElement);
  const scene = new THREE.Scene();
  if (o.bg !== undefined && o.bg !== null) scene.background = new THREE.Color(o.bg);
  const camera = new THREE.PerspectiveCamera(o.fov ?? 35, V.w / V.h, 0.1, o.far ?? 500);
  const composer = new EffectComposer(renderer);
  composer.setPixelRatio(1); composer.setSize(V.w, V.h);
  composer.addPass(new RenderPass(scene, camera));
  // saneamento: NaN/infinito vira 0 e brilho extremo é limitado (o bloom espalharia um único pixel inválido pela tela toda)
  composer.addPass(new ShaderPass({ uniforms: { tDiffuse: { value: null } }, vertexShader: `varying vec2 vUv; void main(){ vUv=uv; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.); }`,
    fragmentShader: `uniform sampler2D tDiffuse; varying vec2 vUv; void main(){ vec4 c=texture2D(tDiffuse,vUv); if(any(isnan(c))||any(isinf(c))) c=vec4(0.,0.,0.,1.); gl_FragColor=min(c,vec4(48.)); }` }));
  let bloom = null;
  if (o.bloom !== false) { const b = o.bloom || {}; bloom = new UnrealBloomPass(new THREE.Vector2(V.w, V.h), b.strength ?? 0.8, b.radius ?? 0.5, b.threshold ?? 0.75); composer.addPass(bloom); }
  composer.addPass(new OutputPass());
  const finish = new ShaderPass(FinishShader);
  Object.assign(finish.uniforms.uGrain, { value: o.grain ?? 0.05 }); finish.uniforms.uVig.value = o.vignette ?? 0.35; finish.uniforms.uCA.value = o.ca ?? 0.0012;
  composer.addPass(finish);
  const S = { THREE, renderer, scene, camera, composer, bloom, finish, update: null };
  onTick(t => { finish.uniforms.uTime.value = t; if (S.update) S.update(t); composer.render(); });
  return S;
}
