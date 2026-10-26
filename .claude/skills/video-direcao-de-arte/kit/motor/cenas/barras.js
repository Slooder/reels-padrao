// barras.js — gráfico de barras horizontais animado com a série cor.dados da DA.
// Título, linhas de grade (graficos.dados.grade), eixo (graficos.dados.eixo), rótulos e valores no papel
// graficos.dados.rotulo; as barras crescem escalonadas com a curva de ênfase e os valores contam junto.
export const meta = {
  nome: 'barras',
  descricao: 'Gráfico de barras horizontais: título, até 8 categorias na série cor.dados, valores que contam e crédito da fonte.',
  dur_padrao: 6,
  formatos: ['horizontal', 'vertical', 'quadrado'],
  alfa_padrao: false,
  grao: false,
  params: {
    titulo: { tipo: 'texto', padrao: null, descricao: 'título do gráfico' },
    dados: { tipo: 'lista', obrigatorio: true, min: 1, max: 8, descricao: 'lista de {rotulo, valor} (1 a 8 barras)',
      itens: { tipo: 'objeto', campos: { rotulo: { tipo: 'texto', obrigatorio: true }, valor: { tipo: 'numero', obrigatorio: true } } } },
    unidade: { tipo: 'texto', padrao: '', descricao: 'sufixo dos valores (ex.: "%", " mil", " bi")' },
    prefixo: { tipo: 'texto', padrao: '', descricao: 'prefixo dos valores (ex.: "R$ ")' },
    casas: { tipo: 'inteiro', padrao: 0, min: 0, max: 3, descricao: 'casas decimais dos valores' },
    destaque: { tipo: 'inteiro', padrao: null, min: 0, descricao: 'índice da barra em destaque (as outras ficam em texto_suave)' },
    max: { tipo: 'numero', padrao: null, descricao: 'valor máximo do eixo (padrão: o maior valor)' },
    fonte: { tipo: 'texto', padrao: null, descricao: 'crédito da fonte dos dados, SEM o prefixo: o kit põe graficos.citacao_fonte.prefixo ("Fonte: ") e não o duplica' },
    cores: { tipo: 'opcao', opcoes: ['serie', 'primaria'], padrao: 'serie', descricao: 'serie = uma cor de cor.dados por barra (com mais barras que cores na série, todas saem na primária: cor repetida confunde categorias); primaria = todas na primária' },
    plataforma: { tipo: 'plataforma', padrao: null, descricao: 'zona segura a respeitar (vertical: reels, tiktok, shorts, uniao; fora do vertical cai em padrao)' },
    empilhado: { tipo: 'booleano', padrao: null, descricao: 'rótulo e valor em cima da barra (padrão: sim no vertical, não no horizontal)' },
    reservar_legenda: { tipo: 'booleano', padrao: null, descricao: 'deixa livre a faixa da legenda (bloco e crédito ficam acima ou abaixo dela); padrão: conforme legenda.reservar_em da DA (vertical e quadrado)' },
  },
};

const S = {};

function formatar(v, casas, prefixo, unidade) {
  const s = v.toLocaleString('pt-BR', { minimumFractionDigits: casas, maximumFractionDigits: casas });
  return `${prefixo || ''}${s}${unidade || ''}`;
}

export function build(palco, p, ctx) {
  const dados = (p.dados || []).slice(0, 8).map((d, i) => {
    if (!d || typeof d !== 'object' || typeof d.valor !== 'number') throw new Error(`dados[${i}] precisa ser {rotulo, valor:número}`);
    return { rotulo: String(d.rotulo ?? ''), valor: d.valor };
  });
  if (!dados.length) throw new Error('dados: informe ao menos uma barra');
  const area = ctx.area_livre(p.plataforma || undefined, { legenda: p.reservar_legenda });
  const g = ctx.DA.graficos.dados;
  const serieCabe = dados.length <= ctx.DA.cor.dados.length;       // série menor que o nº de barras: uma cor só, sem repetir
  const horizontal = ctx.orientacao === 'horizontal';
  const empilhado = p.empilhado != null ? p.empilhado : !horizontal;
  const maxV = p.max ?? Math.max(...dados.map((d) => Math.abs(d.valor)), 1e-9);
  const tamRot = ctx.tam(horizontal ? 'corpo' : 'corpo') * (dados.length > 6 ? 0.85 : 1);
  const tamVal = tamRot;
  const largura = Math.min(area.w, horizontal ? ctx.col(10) : area.w);

  const envelope = ctx.el('div', 'barras-envelope');          // posição e ajuste de escala; o bloco dentro fica livre para entrada/saída
  Object.assign(envelope.style, { position: 'absolute', left: area.x + 'px', width: largura + 'px', transformOrigin: 'left top' });
  palco.appendChild(envelope);
  const bloco = ctx.el('div', 'barras-bloco');
  Object.assign(bloco.style, { position: 'relative', width: largura + 'px', display: 'flex', flexDirection: 'column', gap: ctx.px(0.045) + 'px' });
  envelope.appendChild(bloco);

  let titulo = null;
  if (p.titulo) {
    titulo = ctx.texto('subtitulo', p.titulo, { tam: ctx.tam('h3'), cor: 'texto', wrap: true, maxW: largura });
    bloco.appendChild(titulo);
    ctx.ajustar_texto(titulo, largura, { min: ctx.tam('corpo'), maxLinhas: 2 });
    ctx.sem_orfa(titulo);
  }

  // mede a coluna de rótulos para alinhar as barras
  const linhas = [];
  const grafico = ctx.el('div', 'barras-grafico');
  Object.assign(grafico.style, { position: 'relative', display: 'flex', flexDirection: 'column', gap: (tamRot * 0.75) + 'px' });
  bloco.appendChild(grafico);
  const rotulos = dados.map((d) => ctx.texto(g.rotulo, d.rotulo, { tam: tamRot, cor: 'texto' }));
  let colRot = 0;
  for (const r of rotulos) { grafico.appendChild(r); colRot = Math.max(colRot, ctx.medir(r).w); grafico.removeChild(r); }
  const maxRot = largura * (empilhado ? 0.62 : horizontal ? 0.28 : 0.34);
  if (colRot > maxRot) { colRot = maxRot; rotulos.forEach((r) => { grafico.appendChild(r); ctx.ajustar_texto(r, maxRot, { min: tamRot * 0.7 }); grafico.removeChild(r); }); }
  const colVal = ctx.medir((() => { const t = ctx.texto(g.rotulo, formatar(maxV, p.casas, p.prefixo, p.unidade), { tam: tamVal }); grafico.appendChild(t); return t; })()).w * 1.15;
  grafico.removeChild(grafico.lastChild);
  const alturaBarra = empilhado ? Math.max(ctx.px(0.022), Math.min(ctx.px(0.04), (area.h * 0.5) / dados.length - tamRot * 1.9))
    : Math.max(ctx.px(0.028), Math.min(ctx.px(0.06), (area.h * 0.55) / dados.length - tamRot * 0.75));
  const larguraTrilha = empilhado ? largura : largura - colRot - colVal - ctx.px(0.05);

  // linhas de grade (0, 25, 50, 75, 100 %) atrás das barras
  const gradeEl = ctx.el('div', 'barras-grade');
  Object.assign(gradeEl.style, { position: 'absolute', left: (empilhado ? 0 : colRot + ctx.px(0.025)) + 'px', top: '0', bottom: '0', width: larguraTrilha + 'px' });
  for (let i = 0; i <= (empilhado ? 0 : 4); i++) {                 // empilhado: só o eixo; as trilhas fazem o papel da grade
    const l = ctx.el('div');
    Object.assign(l.style, { position: 'absolute', top: '0', bottom: '0', left: (i * 25) + '%', width: Math.max(1, ctx.traco * 0.5).toFixed(1) + 'px',
      background: i === 0 ? ctx.cor(g.eixo) : ctx.alfa(g.grade, 0.9), transformOrigin: 'center top' });
    gradeEl.appendChild(l);
  }
  grafico.appendChild(gradeEl);

  dados.forEach((d, i) => {
    const linha = ctx.el('div', 'barras-linha');
    const r = rotulos[i];
    let cabecalho = null;
    if (empilhado) {
      Object.assign(linha.style, { position: 'relative', display: 'flex', flexDirection: 'column', gap: (tamRot * 0.3) + 'px' });
      cabecalho = ctx.el('div', 'barras-cabecalho');
      Object.assign(cabecalho.style, { display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: ctx.px(0.02) + 'px' });
      cabecalho.appendChild(r);
      linha.appendChild(cabecalho);
    } else {
      Object.assign(linha.style, { position: 'relative', display: 'flex', alignItems: 'center', gap: ctx.px(0.025) + 'px', height: alturaBarra + 'px' });
      Object.assign(r.style, { width: colRot + 'px', flex: 'none', textAlign: 'right' });
      r._inner.style.textAlign = 'right';
      r._inner.style.display = 'block';
      linha.appendChild(r);
    }
    const trilha = ctx.el('div', 'barras-trilha');
    Object.assign(trilha.style, { position: 'relative', width: larguraTrilha + 'px', height: empilhado ? alturaBarra + 'px' : '100%', flex: 'none',
      background: empilhado ? ctx.alfa(g.grade, 0.55) : 'transparent' });
    const barra = ctx.el('div', 'barras-barra');
    const corBarra = p.cores === 'primaria' || !serieCabe ? ctx.cor('primaria') : ctx.dado(i);
    const apagada = p.destaque != null && p.destaque !== i;
    Object.assign(barra.style, { position: 'absolute', left: '0', top: '0', bottom: '0', width: (Math.abs(d.valor) / maxV * 100).toFixed(3) + '%',
      background: apagada ? ctx.alfa('texto_suave', 0.55) : corBarra, transformOrigin: 'left center', borderRadius: ctx.raio ? `0 ${Math.min(ctx.raio, alturaBarra / 2)}px ${Math.min(ctx.raio, alturaBarra / 2)}px 0` : '0' });
    trilha.appendChild(barra);
    linha.appendChild(trilha);
    const valor = ctx.texto(g.rotulo, formatar(d.valor, p.casas, p.prefixo, p.unidade), { tam: tamVal, cor: apagada ? 'texto_suave' : 'texto' });
    valor.style.flex = 'none';
    if (empilhado) { valor._inner.style.textAlign = 'right'; valor.style.minWidth = colVal + 'px'; cabecalho.appendChild(valor); }
    else { valor.style.width = colVal + 'px'; linha.appendChild(valor); }
    grafico.appendChild(linha);
    ctx.medir(r);
    linhas.push({ linha, barra, valor, d });
  });

  // crédito da fonte: peça compartilhada do kit (graficos.citacao_fonte: papel, tamanho, cor, prefixo e as 7 posições)
  let credito = null, cr = null;
  if (p.fonte) {
    cr = ctx.kit.credito(p.fonte, { area });
    credito = cr.el;
    palco.appendChild(credito);
    cr.posicionar();
  }

  // o crédito reserva a faixa dele (em cima ou embaixo, conforme graficos.citacao_fonte.posicao): o bloco é centrado
  // no que sobra e, se ainda assim não couber (8 barras no vertical), encolhe inteiro — nunca fica por baixo do crédito
  const noMeio = cr && !cr.posicao.startsWith('superior') && !cr.posicao.startsWith('inferior');     // posicao 'centro': não reserva faixa
  const faixa = cr && !noMeio ? cr.faixa : 0;
  const creditoEmCima = cr && cr.em_cima;
  const util = { y: area.y + (creditoEmCima ? faixa : 0), h: area.h - faixa };
  let hBloco = bloco.offsetHeight;
  const encolhe = hBloco > util.h ? util.h / hBloco : 1;
  if (encolhe < 1) { envelope.style.transform = `scale(${encolhe.toFixed(4)})`; hBloco *= encolhe; }
  envelope.style.top = Math.round(Math.min(util.y + util.h - hBloco, Math.max(util.y, util.y + (util.h - hBloco) / 2 - ctx.px(0.015)))) + 'px';

  const T = ctx.tl();
  let t0 = 0.05;
  if (titulo) { T.add('titulo', t0, ctx.dur('media')); t0 += ctx.escalonamento * 2; }
  T.add('grade', t0, ctx.dur('media'), { curva: 'suave' });
  T.escalonar(linhas.map((_, i) => 'r' + i), t0 + ctx.escalonamento, ctx.dur('curta'));
  T.escalonar(linhas.map((_, i) => 'b' + i), t0 + ctx.escalonamento * 2, ctx.dur('longa'), { curva: 'enfase', passo: ctx.escalonamento * 1.5 });
  if (credito) T.add('credito', T.fim - ctx.dur('media') * 0.5, ctx.dur('media'));
  const inicioSaida = ctx.fim_saida();
  Object.assign(S, { ctx, p, titulo, gradeEl, linhas, credito, cr, T, bloco, inicioSaida, fimEntrada: T.fim });
  return { bloco: ctx.rectDe(bloco), titulo: titulo ? ctx.rectDe(titulo) : null, credito: credito ? ctx.rectDe(credito) : null, escala_bloco: +encolhe.toFixed(4),
    barras: linhas.length, max: maxV, cores: p.cores === 'primaria' || !serieCabe ? 'primaria' : 'serie', reservou_legenda: area.reservou, fim_entrada: +T.fim.toFixed(3), inicio_saida: +inicioSaida.toFixed(3) };
}

export function seek(t) {
  const { ctx, p, titulo, gradeEl, linhas, cr, T, bloco, inicioSaida } = S;
  const ent = ctx.DA.movimento.entrada_padrao;
  // Função pura de t: estado de entrada completo de cada parte; a saída do bloco e do crédito vem por cima no fim.
  ctx.entrada(bloco, 1, 'fade');
  if (titulo) ctx.entrada(titulo, T.p(t, 'titulo'), ent === 'escala' ? 'sobe' : ent, { n: (p.titulo || '').length });
  const pg = T.p(t, 'grade');
  [...gradeEl.children].forEach((l, i) => { const q = ctx.clamp(pg * 1.4 - i * 0.1); l.style.transform = `scaleY(${q.toFixed(4)})`; l.style.opacity = q > 0 ? '1' : '0'; });
  linhas.forEach((ln, i) => {
    const pr = T.p(t, 'r' + i);
    ctx.entrada(ln.linha.firstChild, pr, 'fade');                 // rótulo (ou cabeçalho rótulo+valor)
    const pb = ctx.clamp(T.p(t, 'b' + i), 0, 1.12);
    ln.barra.style.transform = `scaleX(${pb.toFixed(4)})`;
    ln.barra.style.opacity = pb > 0 ? '1' : '0';
    const q = ctx.clamp(pb);
    ln.valor._inner.textContent = formatar(ln.d.valor * q, p.casas, p.prefixo, p.unidade);
    ln.valor.style.opacity = (q > 0 ? 0.4 + 0.6 * q : 0).toFixed(3);
  });
  if (cr) cr.seek(T.p(t, 'credito'));
  if (t >= inicioSaida) {
    const ps = ctx.prog(t, inicioSaida, ctx.dur('media'), 'saida');
    ctx.saida(bloco, ps);
    if (cr) cr.sair(ps);
  }
}

export function key(t) {
  return t >= S.fimEntrada + 0.05 && t < S.inicioSaida ? 'estavel' : null;
}

export function ancoras() {
  return S.T.ancoras().filter((a) => a.nome === 'titulo' || a.nome.startsWith('b')).concat([{ t: +S.inicioSaida.toFixed(3), nome: 'saida', tipo: 'saida' }]);
}
