// titulo.js — cartela de título/capítulo (fundo opaco, com grão se a DA pedir).
// Sobretítulo em tarja (graficos.tarja), título no papel "titulo" (escala display, encolhe até caber),
// filete em primaria e subtítulo em "corpo". Entradas/saídas e curvas vêm da DA; alinhamento à grade.
import { criarTarja } from './_tarja.js';

export const meta = {
  nome: 'titulo',
  descricao: 'Cartela de título ou abertura de capítulo: sobretítulo em tarja, título grande, filete e subtítulo.',
  dur_padrao: 4,
  formatos: ['horizontal', 'vertical', 'quadrado', 'thumbnail'],
  alfa_padrao: false,
  grao: true,
  params: {
    titulo: { tipo: 'texto', obrigatorio: true, descricao: 'o título (até ~8 palavras; encolhe para caber em 3 linhas)' },
    sobretitulo: { tipo: 'texto', padrao: null, descricao: 'texto curto acima do título (ex.: "Capítulo 2"), em tarja' },
    subtitulo: { tipo: 'texto', padrao: null, descricao: 'linha de apoio abaixo do título' },
    alinhar: { tipo: 'opcao', opcoes: ['esquerda', 'centro'], padrao: 'esquerda', descricao: 'alinhamento do bloco' },
    posicao: { tipo: 'opcao', opcoes: ['centro', 'base'], padrao: 'centro', descricao: 'bloco centrado na vertical ou apoiado na base da zona segura' },
    escala_titulo: { tipo: 'opcao', opcoes: ['display', 'h1', 'h2'], padrao: 'display', descricao: 'degrau da escala tipográfica do título' },
    assinatura: { tipo: 'booleano', padrao: true, descricao: 'mostra marca.assinatura no rodapé, se houver' },
    plataforma: { tipo: 'plataforma', padrao: null, descricao: 'zona segura a respeitar (vertical: reels, tiktok, shorts, uniao; fora do vertical cai em padrao)' },
    reservar_legenda: { tipo: 'booleano', padrao: null, descricao: 'deixa livre a faixa da legenda (o bloco é centrado no que sobra); padrão: conforme legenda.reservar_em da DA (vertical e quadrado)' },
  },
};

const S = {};

export function build(palco, p, ctx) {
  const area = ctx.area_livre(p.plataforma || undefined, { legenda: p.reservar_legenda });
  const g = ctx.grade();
  const centro = p.alinhar === 'centro';
  const larguraTexto = Math.min(area.w, ctx.orientacao === 'horizontal' ? ctx.col(9) : area.w);

  const bloco = ctx.el('div', 'titulo-bloco');
  Object.assign(bloco.style, { position: 'absolute', left: area.x + 'px', width: area.w + 'px', display: 'flex', flexDirection: 'column',
    alignItems: centro ? 'center' : 'flex-start', gap: ctx.px(0.022) + 'px' });
  palco.appendChild(bloco);

  let tarja = null;
  if (p.sobretitulo) {
    tarja = criarTarja(ctx, p.sobretitulo, { tam: Math.min(ctx.px(ctx.DA.graficos.tarja.tamanho), ctx.tam('h3')) });
    bloco.appendChild(tarja.el);
    tarja.medir();
  }

  const titulo = ctx.texto('titulo', p.titulo, { tam: ctx.tam(p.escala_titulo), wrap: true, maxW: larguraTexto, alinhar: centro ? 'centro' : 'esquerda' });
  bloco.appendChild(titulo);
  const alturaMax = area.h * (p.subtitulo ? 0.55 : 0.68);
  ctx.ajustar_texto(titulo, larguraTexto, { min: ctx.tam('h3'), alturaMax, maxLinhas: ctx.orientacao === 'vertical' ? 5 : 3 });
  ctx.sem_orfa(titulo);

  const filete = ctx.el('div', 'titulo-filete');
  Object.assign(filete.style, { height: Math.max(2, ctx.traco * 1.4).toFixed(1) + 'px', width: Math.round(ctx.col(2)) + 'px',
    background: ctx.cor('primaria'), transformOrigin: centro ? 'center center' : 'left center' });
  bloco.appendChild(filete);

  let sub = null;
  if (p.subtitulo) {
    sub = ctx.texto('corpo', p.subtitulo, { tam: ctx.tam('corpo'), cor: 'texto_suave', wrap: true, maxW: Math.min(larguraTexto, ctx.col(ctx.orientacao === 'horizontal' ? 6 : g.colunas)), alinhar: centro ? 'centro' : 'esquerda' });
    bloco.appendChild(sub);
    ctx.ajustar_texto(sub, larguraTexto, { min: ctx.tam('nota'), maxLinhas: 3 });
    ctx.sem_orfa(sub);
  }

  // assinatura (marca.assinatura): na borda da área OPOSTA à do GC da DA — GC embaixo → assinatura em cima —, para que
  // um GC composto sobre a cartela nunca caia em cima dela; reserva a própria faixa e o bloco usa o que sobra
  let assinatura = null, faixaAss = 0;
  const assEmCima = !ctx.DA.graficos.gc.posicao.startsWith('superior');
  if (p.assinatura && ctx.DA.marca.assinatura) {
    assinatura = ctx.texto('dados', ctx.DA.marca.assinatura, { tam: ctx.tam('nota'), cor: 'texto_suave' });
    assinatura.style.position = 'absolute';
    palco.appendChild(assinatura);
    const ma = ctx.medir(assinatura);
    Object.assign(assinatura.style, { left: Math.round(centro ? area.x + (area.w - ma.w) / 2 : area.x) + 'px', top: Math.round(assEmCima ? area.y : area.y1 - ma.h) + 'px' });
    faixaAss = ma.h + ctx.px(0.02);
  }

  // posição vertical do bloco, dentro do que sobra da área (sem a faixa da assinatura)
  const util = { y: area.y + (assinatura && assEmCima ? faixaAss : 0), y1: area.y1 - (assinatura && !assEmCima ? faixaAss : 0) };
  let hBloco = bloco.offsetHeight;
  const encolhe = hBloco > util.y1 - util.y ? (util.y1 - util.y) / hBloco : 1;
  if (encolhe < 1) { bloco.style.transformOrigin = centro ? 'center top' : 'left top'; bloco.style.transform = `scale(${encolhe.toFixed(4)})`; hBloco *= encolhe; }
  const topo = p.posicao === 'base' ? util.y1 - hBloco : util.y + (util.y1 - util.y - hBloco) / 2;
  bloco.style.top = Math.round(Math.max(util.y, topo)) + 'px';

  // timeline: tarja → título → filete → subtítulo (escalonados); saída em bloco no fim
  const T = ctx.tl();
  const e = ctx.escalonamento;
  let t = 0.05;
  if (tarja) { T.add('tarja', t, ctx.dur('media')); t += e * 2; }
  T.add('titulo', t, ctx.dur('longa')); t += e * 3;
  T.add('filete', t, ctx.dur('media'), { curva: 'enfase' }); t += e * 2;
  if (sub) T.add('sub', t, ctx.dur('media'));
  if (assinatura) T.add('assinatura', t + e, ctx.dur('media'));
  const fimEntrada = T.fim;
  const inicioSaida = ctx.fim_saida();
  Object.assign(S, { ctx, p, bloco, tarja, titulo, filete, sub, assinatura, T, fimEntrada, inicioSaida });
  return { bloco: ctx.rectDe(bloco), titulo: ctx.rectDe(titulo), tarja: tarja ? ctx.rectDe(tarja.el) : null, linhas: ctx.medir(titulo).linhas, fim_entrada: +fimEntrada.toFixed(3), inicio_saida: +inicioSaida.toFixed(3) };
}

export function seek(t) {
  const { ctx, T, tarja, titulo, filete, sub, assinatura, inicioSaida } = S;
  const saindo = t >= inicioSaida;
  const ps = saindo ? ctx.prog(t, inicioSaida, ctx.dur('media'), 'saida') : 0;
  const tipoEnt = ctx.DA.movimento.entrada_padrao;
  if (tarja) {
    if (saindo) ctx.saida(tarja.el, ps);
    else ctx.entrada(tarja.el, 1, 'fade');                  // o wrapper fica parado; bloco e texto têm fases próprias
    tarja.seek(T.p(t, 'tarja'), T.lin(t, 'tarja') > 0.45 ? ctx.prog(t, T.t0('tarja') + ctx.dur('micro') * 1.5, ctx.dur('curta'), 'suave') : 0);
  }
  if (saindo) ctx.saida(titulo, ps); else ctx.entrada(titulo, T.p(t, 'titulo'), tipoEnt, { origem: 'esquerda', n: (S.p.titulo || '').length });
  if (saindo) ctx.saida(filete, ps);
  else {
    const pf = T.p(t, 'filete');
    filete.style.opacity = pf > 0 ? '1' : '0';
    filete.style.transform = `scaleX(${ctx.clamp(pf, 0, 1.2).toFixed(4)})`;
    filete.style.clipPath = 'none';
  }
  if (sub) { if (saindo) ctx.saida(sub, ps); else ctx.entrada(sub, T.p(t, 'sub'), tipoEnt === 'digita' ? 'fade' : tipoEnt); }
  if (assinatura) { if (saindo) ctx.saida(assinatura, ps); else ctx.entrada(assinatura, T.p(t, 'assinatura'), 'fade'); }
}

export function key(t) {
  const { fimEntrada, inicioSaida } = S;
  return t >= fimEntrada + 0.05 && t < inicioSaida ? 'estavel' : null;
}

export function ancoras() {
  return S.T.ancoras();
}
