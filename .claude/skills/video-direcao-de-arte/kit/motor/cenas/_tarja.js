// _tarja.js — peça compartilhada: etiqueta/tarja conforme graficos.tarja da DA (chapada | contorno | sublinhado).
// Abre o bloco primeiro (máscara) e só depois revela o texto — "forma antes de conteúdo".
// Uso: const T = criarTarja(ctx, 'Capítulo 2', {tam}); palco.appendChild(T.el); … T.seek(pBloco, pTexto)

export function criarTarja(ctx, texto, { tam = null, papel = null, inverter = false } = {}) {
  const cfg = ctx.DA.graficos.tarja;
  const estilo = cfg.estilo;
  const papelUsado = papel || cfg.papel;
  const tamanho = tam ?? ctx.px(cfg.tamanho);
  const corFundo = ctx.cor(inverter ? cfg.cor_texto : cfg.cor_fundo);
  const corTexto = ctx.cor(inverter ? cfg.cor_fundo : cfg.cor_texto);
  const raiz = ctx.el('div', 'tarja tarja-' + estilo);
  Object.assign(raiz.style, { position: 'relative', display: 'inline-block', transformOrigin: 'left center' });
  const fundo = ctx.el('div', 'tarja-fundo');
  Object.assign(fundo.style, { position: 'absolute', inset: '0', transformOrigin: 'left center', borderRadius: ctx.raio + 'px' });
  const padX = tamanho * 0.45, padY = tamanho * 0.18;
  const txt = ctx.texto(papelUsado, texto, { tam: tamanho, cor: estilo === 'chapada' ? corTexto : (inverter ? cfg.cor_fundo : cfg.cor_fundo) });
  Object.assign(txt.style, { position: 'relative', padding: `${padY.toFixed(1)}px ${padX.toFixed(1)}px`, whiteSpace: 'nowrap' });
  if (estilo === 'chapada') {
    fundo.style.background = corFundo;
    txt._inner.style.color = corTexto;
  } else if (estilo === 'contorno') {
    fundo.style.border = `${Math.max(1, ctx.traco).toFixed(1)}px solid ${corFundo}`;
    txt._inner.style.color = ctx.cor(cfg.cor_texto);
  } else {                                                  // sublinhado: texto + linha grossa embaixo
    Object.assign(fundo.style, { inset: 'auto 0 0 0', height: Math.max(2, ctx.traco * 1.6).toFixed(1) + 'px', background: corFundo, borderRadius: '0' });
    txt.style.padding = `0 0 ${(tamanho * 0.22).toFixed(1)}px 0`;
    txt._inner.style.color = ctx.cor(cfg.cor_texto);
  }
  if (cfg.inclinacao) raiz.style.transform = `rotate(${cfg.inclinacao}deg)`;
  raiz.append(fundo, txt);
  const api = {
    el: raiz, fundo, texto: txt, papel: papelUsado, tamanho,
    medir() {
      const m = ctx.medir(txt);
      const pad = estilo === 'sublinhado' ? { x: 0, y: tamanho * 0.22 } : { x: padX * 2, y: padY * 2 };
      raiz.style.width = Math.ceil(m.w + pad.x) + 'px';
      raiz.style.height = Math.ceil(m.h + pad.y) + 'px';
      return { w: Math.ceil(m.w + pad.x), h: Math.ceil(m.h + pad.y) };
    },
    /** pBloco: abertura do bloco (0–1), pTexto: opacidade do texto (0–1). */
    seek(pBloco, pTexto) {
      fundo.style.transform = `scaleX(${ctx.clamp(pBloco).toFixed(4)})`;
      fundo.style.opacity = pBloco > 0 ? '1' : '0';
      txt.style.opacity = ctx.clamp(pTexto).toFixed(3);
    },
  };
  return api;
}
