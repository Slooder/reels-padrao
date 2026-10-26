// _credito.js — peça compartilhada: crédito de fonte ("Fonte: IBGE, 2024") conforme graficos.citacao_fonte da DA.
// Uma implementação só para as cenas `barras` e `citacao`, para cenas de outras skills (ctx.kit.credito) e, em PIL,
// texto.credito_fonte: mesmo papel, tamanho, cor, prefixo e as 7 posições do esquema, sempre dentro da zona segura.
//
//   const cr = ctx.kit.credito('IBGE, 2024', { plataforma: p.plataforma });
//   palco.appendChild(cr.el); const { faixa, em_cima } = cr.posicionar();   // reserve `faixa` px em cima ou embaixo
//   cr.seek(pEntrada);  …  cr.sair(pSaida);                                  // puros: opacidade em função de p

export function criarCredito(ctx, texto, { plataforma = undefined, area = null, prefixo = undefined, posicao = null, maxLinhas = 2, larguraMax = null, reservar_legenda = null } = {}) {
  const cf = ctx.DA.graficos.citacao_fonte;
  // sem `area`, o crédito mora na zona segura menos a faixa da legenda (ctx.area_livre): nunca nasce em cima dela
  const zona = area || ctx.area_livre(plataforma || undefined, { legenda: reservar_legenda });
  const pos = posicao || cf.posicao;
  const pre = prefixo === undefined ? (cf.prefixo ?? 'Fonte: ') : (prefixo || '');
  const bruto = String(texto ?? '').trim();
  // nunca duplica: "Fonte: IBGE" passado com o prefixo "Fonte: " continua "Fonte: IBGE"
  const completo = pre && !bruto.toLowerCase().startsWith(pre.trim().toLowerCase()) ? pre + bruto : bruto;
  const alinhar = pos.endsWith('direita') ? 'direita' : (pos.endsWith('centro') || pos === 'centro') ? 'centro' : 'esquerda';
  const maxW = Math.min(larguraMax ?? zona.w, zona.w);
  const tam = ctx.px(cf.tamanho);
  const el = ctx.texto(cf.papel, completo, { tam, cor: cf.cor || 'texto_suave', wrap: true, maxW, alinhar, classe: 'credito-fonte' });
  el.style.position = 'absolute';
  const api = {
    el, texto: completo, posicao: pos, faixa: 0, em_cima: pos.startsWith('superior'), rect: null,
    /** Mede e posiciona (o elemento precisa estar no DOM). Devolve { faixa, em_cima, rect }: `faixa` = altura a reservar. */
    posicionar() {
      ctx.ajustar_texto(el, maxW, { min: tam * 0.8, maxLinhas });
      const m = ctx.medir(el);                                   // esquerda: caixa justa na linha mais larga; centro/direita: caixa de maxW com o texto alinhado dentro
      const x = alinhar === 'esquerda' ? zona.x : alinhar === 'direita' ? zona.x1 - m.w : zona.x + (zona.w - m.w) / 2;
      const y = pos.startsWith('superior') ? zona.y : pos.startsWith('inferior') ? zona.y1 - m.h : zona.y + (zona.h - m.h) / 2;
      el.style.left = Math.round(x) + 'px';
      el.style.top = Math.round(y) + 'px';
      api.faixa = m.h + ctx.px(0.02);
      api.rect = { x: Math.round(x), y: Math.round(y), w: m.w, h: m.h, x1: Math.round(x) + m.w, y1: Math.round(y) + m.h, linhas: m.linhas, alinhar };
      return { faixa: api.faixa, em_cima: api.em_cima, rect: api.rect };
    },
    /** Entrada pura: p 0–1 (já com a curva). Nunca mexe em left/top nem em transform de posição. */
    seek(p) { ctx.entrada(el, p, 'fade'); },
    /** Saída pura por cima da entrada: p 0–1. */
    sair(p) { ctx.saida(el, p, 'fade'); },
  };
  return api;
}
