// citacao.js — frase em destaque + autor + crédito da fonte. Aspas e filete em primaria; o texto entra
// palavra a palavra com o escalonamento da DA; o crédito segue graficos.citacao_fonte.
export const meta = {
  nome: 'citacao',
  descricao: 'Citação em destaque: aspas, frase (entra palavra a palavra), autor e crédito da fonte.',
  dur_padrao: 6,
  formatos: ['horizontal', 'vertical', 'quadrado'],
  alfa_padrao: false,
  grao: true,
  params: {
    texto: { tipo: 'texto', obrigatorio: true, descricao: 'a frase citada (sem aspas; o kit coloca)' },
    autor: { tipo: 'texto', padrao: null, descricao: 'quem disse' },
    cargo: { tipo: 'texto', padrao: null, descricao: 'cargo ou contexto do autor' },
    fonte: { tipo: 'texto', padrao: null, descricao: 'crédito da fonte (veículo, data), SEM o prefixo: o kit põe graficos.citacao_fonte.prefixo ("Fonte: ") e não o duplica' },
    foto: { tipo: 'arquivo', padrao: null, descricao: 'foto do autor (data-da-livre)' },
    papel: { tipo: 'papel', padrao: null, descricao: 'papel tipográfico da frase (padrão: corpo; titulo se for curta)' },
    plataforma: { tipo: 'plataforma', padrao: null, descricao: 'zona segura a respeitar (vertical: reels, tiktok, shorts, uniao; fora do vertical cai em padrao)' },
    reservar_legenda: { tipo: 'booleano', padrao: null, descricao: 'deixa livre a faixa da legenda (bloco e crédito ficam acima ou abaixo dela); padrão: conforme legenda.reservar_em da DA (vertical e quadrado)' },
  },
};

const S = {};

export function build(palco, p, ctx) {
  const area = ctx.area_livre(p.plataforma || undefined, { legenda: p.reservar_legenda });
  const horizontal = ctx.orientacao === 'horizontal';
  const larguraTexto = Math.min(area.w, horizontal ? ctx.col(8) : area.w);
  const curta = p.texto.length <= 70;
  const papel = p.papel || (curta ? 'titulo' : 'corpo');
  const papelCfg = ctx.fonte(papel);
  const tamBase = curta ? ctx.tam('h1') : ctx.tam(horizontal ? 'h2' : 'h2');
  const filete = Math.max(3, ctx.traco * 1.6);

  const bloco = ctx.el('div', 'citacao-bloco');
  Object.assign(bloco.style, { position: 'absolute', left: area.x + 'px', width: larguraTexto + 'px', display: 'flex', flexDirection: 'column', gap: ctx.px(0.03) + 'px' });
  palco.appendChild(bloco);

  // aspas grandes em primaria (papel titulo, sem caixa alta importar)
  const aspas = ctx.texto('titulo', '“', { tam: ctx.tam('display') * 1.1, cor: 'primaria' });
  Object.assign(aspas._inner.style, { lineHeight: '0.75', textTransform: 'none' });
  aspas.style.height = (ctx.tam('display') * 0.62) + 'px';
  bloco.appendChild(aspas);

  // frase: cada palavra num span para entrar escalonada
  const frase = ctx.texto(papel, '', { tam: tamBase, cor: 'texto', wrap: true, maxW: larguraTexto, html: '' });
  if (papelCfg.caixa === 'alta') frase._inner.style.textTransform = 'none';   // citação respeita a grafia original
  const palavras = p.texto.trim().split(/\s+/);
  const spans = palavras.map((w, i) => {
    const s = ctx.el('span', 'citacao-palavra', w + (i < palavras.length - 1 ? ' ' : ''));
    s.style.display = 'inline-block';
    s.style.whiteSpace = 'pre';
    frase._inner.appendChild(s);
    return s;
  });
  bloco.appendChild(frase);
  ctx.ajustar_texto(frase, larguraTexto, { min: ctx.tam('h3') * 0.9, alturaMax: area.h * 0.55, maxLinhas: horizontal ? 4 : 7 });
  ctx.sem_orfa(frase);

  // autor + cargo com filete
  let autor = null, cargo = null, linhaAutor = null, foto = null;
  if (p.autor) {
    linhaAutor = ctx.el('div', 'citacao-autor');
    Object.assign(linhaAutor.style, { display: 'flex', alignItems: 'center', gap: ctx.px(0.02) + 'px' });
    if (p.foto) {
      const lado = Math.round(ctx.tam('h2') * 1.6);
      foto = ctx.el('div', 'citacao-foto');
      foto.setAttribute('data-da-livre', 'foto');
      Object.assign(foto.style, { width: lado + 'px', height: lado + 'px', flex: 'none', overflow: 'hidden', borderRadius: (ctx.raio > 0 ? lado / 2 : 0) + 'px',
        border: `${Math.max(2, ctx.traco).toFixed(1)}px solid ${ctx.cor('primaria')}` });
      const img = document.createElement('img'); img.src = p.foto; img.alt = '';
      Object.assign(img.style, { width: '100%', height: '100%', objectFit: 'cover', display: 'block' });
      foto.appendChild(img);
      linhaAutor.appendChild(foto);
    } else {
      const f = ctx.el('div', 'citacao-filete');
      Object.assign(f.style, { width: Math.round(ctx.col(1) * 0.8) + 'px', height: filete + 'px', background: ctx.cor('primaria'), flex: 'none', transformOrigin: 'left center' });
      linhaAutor.appendChild(f); S.filete = f;
    }
    const col = ctx.el('div');
    Object.assign(col.style, { display: 'flex', flexDirection: 'column', gap: ctx.px(0.004) + 'px' });
    // autor e cargo cabem na mesma largura da frase (menos o filete ou a foto): quebram em até 2 linhas e, se preciso, encolhem
    const wMarca = (p.foto ? Math.round(ctx.tam('h2') * 1.6) : Math.round(ctx.col(1) * 0.8)) + ctx.px(0.02);
    const wAutor = Math.max(ctx.px(0.2), larguraTexto - wMarca);
    autor = ctx.texto('dados', p.autor, { tam: ctx.tam('corpo'), cor: 'texto', wrap: true, maxW: wAutor });
    col.appendChild(autor);
    if (p.cargo) { cargo = ctx.texto('corpo', p.cargo, { tam: ctx.tam('nota'), cor: 'texto_suave', wrap: true, maxW: wAutor }); col.appendChild(cargo); }
    linhaAutor.appendChild(col);
    bloco.appendChild(linhaAutor);
    ctx.ajustar_texto(autor, wAutor, { min: ctx.tam('nota'), maxLinhas: 2 });
    if (cargo) ctx.ajustar_texto(cargo, wAutor, { min: ctx.tam('nota') * 0.85, maxLinhas: 2 });
  }

  // crédito da fonte: peça compartilhada do kit (graficos.citacao_fonte: papel, tamanho, cor, prefixo e as 7 posições)
  let credito = null, cr = null;
  if (p.fonte) {
    cr = ctx.kit.credito(p.fonte, { area });
    credito = cr.el;
    palco.appendChild(credito);
    cr.posicionar();
  }

  // o crédito reserva a faixa dele (em cima ou embaixo, conforme graficos.citacao_fonte.posicao): o bloco é centrado
  // no que sobra e, se ainda assim não couber, encolhe inteiro — nunca fica por baixo do crédito nem sai da zona segura
  const noMeio = cr && !cr.posicao.startsWith('superior') && !cr.posicao.startsWith('inferior');     // posicao 'centro': não reserva faixa
  const faixa = cr && !noMeio ? cr.faixa : 0;
  const emCima = cr && cr.em_cima;
  const util = { y: area.y + (emCima ? faixa : 0), h: area.h - faixa };
  let hBloco = bloco.offsetHeight;
  const encolhe = hBloco > util.h ? util.h / hBloco : 1;
  if (encolhe < 1) { bloco.style.transformOrigin = 'left top'; bloco.style.transform = `scale(${encolhe.toFixed(4)})`; hBloco *= encolhe; }
  bloco.style.top = Math.round(Math.min(util.y + util.h - hBloco, Math.max(util.y, util.y + (util.h - hBloco) / 2 - ctx.px(0.02)))) + 'px';

  const T = ctx.tl();
  T.add('aspas', 0, ctx.dur('media'), { curva: 'enfase' });
  const passo = Math.min(ctx.escalonamento, 1.6 / Math.max(1, spans.length));
  T.escalonar(spans.map((_, i) => 'w' + i), ctx.escalonamento * 2, ctx.dur('media'), { passo });
  const tAutor = T.fim - ctx.dur('media') * 0.5;
  if (linhaAutor) T.add('autor', tAutor, ctx.dur('media'));
  if (credito) T.add('credito', tAutor + ctx.escalonamento * 2, ctx.dur('media'));
  const inicioSaida = ctx.fim_saida();
  Object.assign(S, { ctx, bloco, aspas, frase, spans, linhaAutor, autor, cargo, foto, credito, cr, T, inicioSaida, fimEntrada: T.fim });
  return { bloco: ctx.rectDe(bloco), credito: credito ? ctx.rectDe(credito) : null, palavras: spans.length, linhas: ctx.medir(frase).linhas, papel,
    fim_entrada: +T.fim.toFixed(3), inicio_saida: +inicioSaida.toFixed(3) };
}

export function seek(t) {
  const { ctx, aspas, spans, linhaAutor, cr, T, inicioSaida } = S;
  const ent = ctx.DA.movimento.entrada_padrao;
  const tipoPalavra = ent === 'mascara' || ent === 'digita' ? 'fade' : ent === 'escala' ? 'escala' : 'sobe';
  // Função pura de t: estado de entrada completo primeiro; a saída dos blocos vem por cima no fim.
  for (const e of [S.frase, linhaAutor]) if (e) ctx.entrada(e, 1, 'fade');
  const pa = T.p(t, 'aspas');
  aspas.style.opacity = ctx.clamp(pa).toFixed(3);
  aspas.style.transform = `scale(${(0.8 + 0.2 * pa).toFixed(4)})`;
  aspas.style.transformOrigin = 'left bottom';
  aspas.style.clipPath = 'none';
  spans.forEach((s, i) => ctx.entrada(s, T.p(t, 'w' + i), tipoPalavra, { dist: ctx.px(0.015) }));
  if (linhaAutor) {
    const p = T.p(t, 'autor');
    if (S.filete) { S.filete.style.transform = `scaleX(${p.toFixed(4)})`; S.filete.style.opacity = p > 0 ? '1' : '0'; }
    if (S.foto) ctx.entrada(S.foto, p, 'fade');
    ctx.entrada(S.autor, p, 'fade');
    if (S.cargo) ctx.entrada(S.cargo, ctx.prog(t, T.t0('autor') + ctx.escalonamento, ctx.dur('media')), 'fade');
  }
  if (cr) cr.seek(T.p(t, 'credito'));
  if (t >= inicioSaida) {
    const ps = ctx.prog(t, inicioSaida, ctx.dur('media'), 'saida');
    for (const e of [aspas, S.frase, linhaAutor]) if (e) ctx.saida(e, ps);
    if (cr) cr.sair(ps);
  }
}

export function key(t) {
  return t >= S.fimEntrada + 0.05 && t < S.inicioSaida ? 'estavel' : null;
}

export function ancoras() {
  const a = S.T.ancoras().filter((x) => x.nome === 'aspas' || x.nome === 'w0' || x.nome === 'autor');
  return a.concat([{ t: +S.inicioSaida.toFixed(3), nome: 'saida', tipo: 'saida' }]);
}
