// gc.js — lower third (GC) com nome, cargo e foto opcional, fundo transparente.
// Estilo, posição, papéis, tamanhos e cores vêm de graficos.gc da DA:
//   barra    caixa com barra de acento na lateral      caixa    caixa com raio da DA e cargo em caixa separada
//   linha    sem caixa: filete de acento + texto        etiqueta chip chapado na cor de fundo do GC (ex.: neon)
// Proteção sobre vídeo (graficos.gc.protecao): auto | nenhuma | sombra | contorno | degrade — sempre em cor_fundo. No
// `auto`, o estilo `linha` (o único sem caixa) ganha o painel esfumado (`degrade`); os demais já têm apoio próprio.
// O GC fica na zona segura MENOS a faixa da legenda quando a peça leva legenda queimada (ctx.area_livre): nunca os dois
// no mesmo lugar. `reservar_legenda` força (true) ou dispensa (false); null segue legenda.reservar_em da DA — por
// padrão vertical e quadrado; no horizontal o GC fica na base e OCUPA a faixa da legenda (`da validar` anota; a prancha
// e o teste de movimento mostram exatamente isto). Vídeo horizontal com legenda queimada: ponha "horizontal" na lista.
export const meta = {
  nome: 'gc',
  descricao: 'Lower third com nome, cargo e foto opcional; estilo e posição definidos por graficos.gc da DA.',
  dur_padrao: 5,
  formatos: ['horizontal', 'vertical', 'quadrado'],
  alfa_padrao: true,
  grao: false,
  params: {
    nome: { tipo: 'texto', obrigatorio: true, descricao: 'nome da pessoa' },
    cargo: { tipo: 'texto', padrao: null, descricao: 'cargo, papel ou descrição curta' },
    foto: { tipo: 'arquivo', padrao: null, descricao: 'foto (jpg/png); entra em data-da-livre' },
    selo: { tipo: 'texto', padrao: null, descricao: 'etiqueta curta acima do nome (ex.: "ao vivo", "arquivo 2018")' },
    plataforma: { tipo: 'plataforma', padrao: null, descricao: 'zona segura a respeitar (vertical: reels, tiktok, shorts, uniao; fora do vertical cai em padrao)' },
    entrada_em: { tipo: 'numero', padrao: 0, min: 0, descricao: 'instante em que o GC começa a entrar (s)' },
    saida_em: { tipo: 'numero', padrao: null, min: 0, descricao: 'instante em que começa a sair (padrão: fim − duração média)' },
    reservar_legenda: { tipo: 'booleano', padrao: null, descricao: 'deixa livre a faixa da legenda (o GC fica acima ou abaixo dela); padrão: conforme legenda.reservar_em da DA (vertical e quadrado)' },
  },
};

const S = {};

export function build(palco, p, ctx) {
  const cfg = ctx.DA.graficos.gc;
  const estilo = cfg.estilo;
  const area = ctx.area_livre(p.plataforma || undefined, { legenda: p.reservar_legenda });
  const protecao = (cfg.protecao || 'auto') === 'auto' ? (estilo === 'linha' ? 'degrade' : 'nenhuma') : cfg.protecao;
  const tamNome = ctx.px(cfg.tamanho_nome), tamCargo = ctx.px(cfg.tamanho_cargo);
  const respiro = tamNome * 0.5;
  const raio = ctx.raio;
  const corFundo = ctx.alfa(cfg.cor_fundo, cfg.alfa_fundo);
  const corAcento = ctx.cor(cfg.cor_acento);
  const pos = cfg.posicao;                                   // inferior_esquerda | inferior_centro | inferior_direita | …
  const aDireita = pos.endsWith('direita'), aoCentro = pos.endsWith('centro'), emCima = pos.startsWith('superior');
  const maxW = Math.min(area.w, ctx.orientacao === 'horizontal' ? ctx.col(7) : area.w);

  const raiz = ctx.el('div', 'gc gc-' + estilo);
  Object.assign(raiz.style, { position: 'absolute', display: 'flex', alignItems: 'flex-end', gap: respiro + 'px' });

  // foto opcional (quadrada ou redonda conforme o raio da DA)
  let foto = null;
  if (p.foto) {
    const lado = Math.round(tamNome * 2.9);
    foto = ctx.el('div', 'gc-foto');
    foto.setAttribute('data-da-livre', 'foto');
    Object.assign(foto.style, { width: lado + 'px', height: lado + 'px', flex: 'none', overflow: 'hidden', position: 'relative',
      borderRadius: (raio > 0 ? Math.min(lado / 2, raio * 3) : 0) + 'px', border: `${Math.max(2, ctx.traco).toFixed(1)}px solid ${corAcento}`,
      background: ctx.cor('superficie') });
    const img = document.createElement('img');
    img.src = p.foto; img.alt = '';
    Object.assign(img.style, { width: '100%', height: '100%', objectFit: 'cover', display: 'block' });
    foto.appendChild(img);
    raiz.appendChild(foto);
  }

  // caixa de texto
  const caixa = ctx.el('div', 'gc-caixa');
  Object.assign(caixa.style, { position: 'relative', display: 'flex', flexDirection: 'column', alignItems: aoCentro ? 'center' : 'flex-start',
    gap: (tamCargo * 0.35) + 'px', maxWidth: maxW + 'px' });
  let acento = null;
  if (estilo === 'barra') {
    Object.assign(caixa.style, { background: corFundo, padding: `${(respiro * 0.9).toFixed(1)}px ${(respiro * 1.3).toFixed(1)}px ${(respiro * 0.9).toFixed(1)}px ${(respiro * 1.3 + ctx.traco * 2.2).toFixed(1)}px`, borderRadius: raio + 'px' });
    acento = ctx.el('div', 'gc-acento');
    Object.assign(acento.style, { position: 'absolute', left: '0', top: '0', bottom: '0', width: Math.max(3, ctx.traco * 2.2).toFixed(1) + 'px', background: corAcento, transformOrigin: 'center bottom',
      borderRadius: raio ? `${raio}px 0 0 ${raio}px` : '0' });
    caixa.appendChild(acento);
  } else if (estilo === 'caixa') {
    Object.assign(caixa.style, { background: corFundo, padding: `${(respiro * 0.9).toFixed(1)}px ${(respiro * 1.3).toFixed(1)}px`, borderRadius: raio + 'px',
      borderLeft: `${Math.max(2, ctx.traco).toFixed(1)}px solid ${corAcento}` });
  } else if (estilo === 'linha') {
    acento = ctx.el('div', 'gc-acento');
    Object.assign(acento.style, { position: 'relative', height: Math.max(2, ctx.traco * 1.4).toFixed(1) + 'px', width: Math.round(ctx.col(1)) + 'px', background: corAcento,
      transformOrigin: aDireita ? 'right center' : 'left center', marginBottom: (tamCargo * 0.3) + 'px' });
    caixa.appendChild(acento);
    caixa.style.padding = `0 0 ${(respiro * 0.3).toFixed(1)}px 0`;
  } else {                                                  // etiqueta
    Object.assign(caixa.style, { gap: (tamCargo * 0.5) + 'px' });
  }

  let selo = null;
  if (p.selo) {
    selo = ctx.texto('dados', p.selo, { tam: tamCargo * 0.85, cor: cfg.cor_acento });
    selo._inner.style.letterSpacing = '0.14em';
    selo._inner.style.textTransform = 'uppercase';
    caixa.appendChild(selo);
  }
  const nome = ctx.texto(cfg.papel_nome, p.nome, { tam: tamNome, cor: cfg.cor_nome, wrap: true, maxW: maxW - respiro * 2.6, alinhar: aoCentro ? 'centro' : 'esquerda' });
  caixa.appendChild(nome);
  let cargo = null;
  if (p.cargo) {
    cargo = ctx.texto(cfg.papel_cargo, p.cargo, { tam: tamCargo, cor: cfg.cor_cargo, wrap: true, maxW: maxW - respiro * 2.6, alinhar: aoCentro ? 'centro' : 'esquerda' });
    caixa.appendChild(cargo);
  }
  if (estilo === 'etiqueta') {
    // nome e cargo em chips independentes (chapados)
    Object.assign(nome.style, { background: corFundo, padding: `${(tamNome * 0.18).toFixed(1)}px ${(tamNome * 0.45).toFixed(1)}px`, borderRadius: raio + 'px' });
    if (cargo) Object.assign(cargo.style, { background: ctx.alfa('superficie', Math.max(0.85, cfg.alfa_fundo)), padding: `${(tamCargo * 0.22).toFixed(1)}px ${(tamCargo * 0.6).toFixed(1)}px`, borderRadius: raio + 'px' });
    if (selo) Object.assign(selo.style, { background: ctx.alfa(cfg.cor_acento, 1), padding: `${(tamCargo * 0.2).toFixed(1)}px ${(tamCargo * 0.5).toFixed(1)}px`, borderRadius: raio + 'px' });
    if (selo) selo._inner.style.color = ctx.cor('fundo');
  }
  // proteção sobre vídeo (D19): sempre na cor de apoio do GC (cor_fundo), para o texto ter contraste garantido por token
  let painel = null;
  if (protecao === 'sombra' || protecao === 'degrade') {
    const halo = `0 0 ${ctx.px(0.006).toFixed(1)}px ${ctx.alfa(cfg.cor_fundo, 0.95)}, 0 ${ctx.px(0.002).toFixed(1)}px ${ctx.px(0.016).toFixed(1)}px ${ctx.alfa(cfg.cor_fundo, 0.85)}`;
    for (const e of [nome, cargo, selo]) if (e && !(estilo === 'etiqueta')) e._inner.style.textShadow = halo;
  } else if (protecao === 'contorno') {
    for (const [e, tam] of [[nome, tamNome], [cargo, tamCargo], [selo, tamCargo * 0.85]]) if (e && estilo !== 'etiqueta') ctx.contorno(e._inner, cfg.cor_fundo, Math.max(1, Math.round(tam * 0.09)));
  }
  if (protecao === 'degrade') {
    // painel esfumado atrás do bloco: cor_fundo × alfa_fundo, com as bordas desfeitas por uma sombra de caixa da mesma cor
    painel = ctx.el('div', 'gc-protecao');
    const fx = respiro * 1.1, fy = respiro * 0.75, esfuma = respiro * 1.1;
    Object.assign(painel.style, { position: 'absolute', left: (-fx).toFixed(1) + 'px', right: (-fx).toFixed(1) + 'px', top: (-fy).toFixed(1) + 'px', bottom: (-fy).toFixed(1) + 'px',
      background: corFundo, boxShadow: `0 0 ${esfuma.toFixed(1)}px ${(esfuma * 0.35).toFixed(1)}px ${corFundo}`, borderRadius: (raio || respiro * 0.5).toFixed(1) + 'px' });
    caixa.insertBefore(painel, caixa.firstChild);
  }
  raiz.appendChild(caixa);
  palco.appendChild(raiz);

  // medidas (fontes já carregadas)
  ctx.ajustar_texto(nome, maxW - respiro * 2.6, { min: tamNome * 0.6, maxLinhas: 2 });
  ctx.sem_orfa(nome);
  if (cargo) { ctx.ajustar_texto(cargo, maxW - respiro * 2.6, { min: tamCargo * 0.75, maxLinhas: 2 }); ctx.sem_orfa(cargo); }
  if (selo) ctx.medir(selo);
  const r = { width: raiz.offsetWidth, height: raiz.offsetHeight };
  const x = aDireita ? area.x1 - r.width : aoCentro ? area.x + (area.w - r.width) / 2 : area.x;
  const y = emCima ? area.y : area.y1 - r.height;
  Object.assign(raiz.style, { left: Math.round(x) + 'px', top: Math.round(y) + 'px' });

  const T = ctx.tl();
  const t0 = p.entrada_em || 0;
  T.add('raiz', t0, ctx.dur('media'));
  if (acento) T.add('acento', t0 + ctx.escalonamento, ctx.dur('media'), { curva: 'enfase' });
  if (foto) T.add('foto', t0, ctx.dur('media'));
  if (selo) T.add('selo', t0 + ctx.escalonamento * 2, ctx.dur('curta'));
  T.add('nome', t0 + ctx.escalonamento * 2, ctx.dur('media'));
  if (cargo) T.add('cargo', t0 + ctx.escalonamento * 4, ctx.dur('media'));
  const inicioSaida = p.saida_em != null ? p.saida_em : ctx.fim_saida();
  Object.assign(S, { ctx, p, estilo, raiz, caixa, acento, foto, selo, nome, cargo, T, aDireita, inicioSaida, fimEntrada: T.fim });
  return { caixa: { x: Math.round(x), y: Math.round(y), w: r.width, h: r.height, x1: Math.round(x) + r.width, y1: Math.round(y) + r.height }, estilo, protecao,
    area: { x: area.x, y: area.y, x1: area.x1, y1: area.y1, plataforma: area.plataforma }, reservou_legenda: area.reservou, faixa_legenda: area.faixa_legenda,
    fim_entrada: +T.fim.toFixed(3), inicio_saida: +inicioSaida.toFixed(3) };
}

export function seek(t) {
  const { ctx, estilo, raiz, acento, foto, selo, nome, cargo, T, aDireita, inicioSaida } = S;
  const ent = ctx.DA.movimento.entrada_padrao;
  const tipoRaiz = estilo === 'etiqueta' ? (ent === 'digita' ? 'fade' : ent) : (ent === 'digita' || ent === 'mascara' ? 'desliza' : ent);
  // Função pura de t: primeiro o estado de entrada COMPLETO de cada parte para este t; a saída (que só mexe na raiz)
  // vem por cima no fim. Um `return` aqui antes de posicionar os filhos faria --quadro T ≠ quadro T do vídeo.
  ctx.entrada(raiz, T.p(t, 'raiz'), tipoRaiz, { origem: aDireita ? 'direita' : 'esquerda' });
  if (acento) {
    const pa = ctx.clamp(T.p(t, 'acento'), 0, 1.15);
    acento.style.transform = estilo === 'linha' ? `scaleX(${pa.toFixed(4)})` : `scaleY(${pa.toFixed(4)})`;
    acento.style.opacity = pa > 0 ? '1' : '0';
  }
  if (foto) ctx.entrada(foto, T.p(t, 'foto'), 'fade');
  if (selo) ctx.entrada(selo, T.p(t, 'selo'), 'fade');
  ctx.entrada(nome, T.p(t, 'nome'), ent === 'escala' ? 'sobe' : ent, { n: (S.p.nome || '').length, dist: ctx.px(0.02) });
  if (cargo) ctx.entrada(cargo, T.p(t, 'cargo'), ent === 'digita' || ent === 'escala' ? 'fade' : ent, { dist: ctx.px(0.015) });
  if (t >= inicioSaida) ctx.saida(raiz, ctx.prog(t, inicioSaida, ctx.dur('curta'), 'saida'), undefined, { origem: aDireita ? 'direita' : 'esquerda' });
}

export function key(t) {
  return t >= S.fimEntrada + 0.05 && t < S.inicioSaida ? 'estavel' : null;
}

export function ancoras() {
  return S.T.ancoras().filter((a) => a.nome === 'raiz' || a.nome === 'nome').concat([{ t: +S.inicioSaida.toFixed(3), nome: 'saida', tipo: 'saida' }]);
}
