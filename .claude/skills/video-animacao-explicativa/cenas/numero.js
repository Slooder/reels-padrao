// numero.js — um número grande, com contagem, o que ele mede e a fonte. Passos: [rotulo] → numero → [contexto].
// A contagem é só a chegada: os valores intermediários não significam nada e o quadro final mostra EXATAMENTE `valor`
// com as casas pedidas (formatação pt-BR). Para um quadro pausado no meio da contagem não virar "dado": enquanto conta,
// o número fica esmaecido e o crédito da fonte ainda não está na tela — os dois chegam juntos, no valor exato. O número é dado: o exemplo padrão é inventado e leva o selo "ilustrativo";
// com `valor` seu, a cena exige a escolha — ilustrativo=false + `fonte` (+ fato_ids no storyboard) para dado
// verificado, ou ilustrativo=true para exemplo. Os nomes dos parâmetros (`valor`, `prefixo`, `unidade`) são os que
// `fatos.py conferir-storyboard` lê para comparar o que vai para a tela com a ficha de fatos.
import { params, guardar, ler, montarQuadro, escrever, caber, tamanho, exigir, decidirIlustrativo, marcarTermos, porTexto, num, clamp, lerp, encaixou, respiro } from './_ia.js';

const EXEMPLO = { rotulo: 'Janela de contexto · Modelo Exemplo', valor: 128, unidade: ' mil tokens', contexto: 'É quanto texto este modelo de exemplo considera *de uma vez*.' };

export const meta = {
  nome: 'numero',
  descricao: 'Número: um dado grande na tela, com contagem até o valor exato, o rótulo de quem é o número, a frase que diz o que ele mede e o crédito da fonte.',
  dur_padrao: 7,
  formatos: ['horizontal', 'vertical', 'quadrado'],
  alfa_padrao: false,
  grao: true,
  params: params({
    valor: { tipo: 'numero', padrao: null, descricao: 'o número — valor final da contagem (sem `valor`, a cena mostra o exemplo inventado, com selo)' },
    prefixo: { tipo: 'texto', padrao: null, descricao: 'o que vem antes do número ("US$ ", "R$ ", "~")' },
    unidade: { tipo: 'texto', padrao: null, descricao: 'o que vem depois, com o espaço (" mil tokens", "%", " bilhões de parâmetros")' },
    casas: { tipo: 'inteiro', padrao: 0, min: 0, max: 4, descricao: 'casas decimais mostradas (vírgula decimal, ponto de milhar)' },
    rotulo: { tipo: 'texto', padrao: null, descricao: 'linha pequena acima: de quem ou de quando é o número ("Modelo X · out/2026")' },
    contexto: { tipo: 'texto', padrao: null, descricao: 'frase abaixo: o que o número mede (*asteriscos* destacam)' },
    contagem: { tipo: 'booleano', padrao: true, descricao: 'true = conta de `contar_de` até `valor`; false = o número entra pronto' },
    contar_de: { tipo: 'numero', padrao: 0, descricao: 'valor em que a contagem começa' },
  }, { titulo: null, ilustrativo: 'dado' }),
};

function dados(p) {
  const proprio = p.valor != null;
  const e = proprio ? {} : EXEMPLO;
  return { proprio, valor: proprio ? p.valor : EXEMPLO.valor, prefixo: String(p.prefixo ?? ''), unidade: String(p.unidade ?? e.unidade ?? ''),
    rotulo: String(p.rotulo ?? e.rotulo ?? '').trim(), contexto: String(p.contexto ?? e.contexto ?? '').trim(), casas: p.casas ?? 0 };
}

export function roteiro(p, mov) {
  const d = mov.duracoes, D = dados(p);
  decidirIlustrativo(p, D.proprio, 'numero');
  exigir(Number.isFinite(D.valor), `valor = ${JSON.stringify(p.valor)}: precisa ser um número (a unidade vai em "unidade", o símbolo da moeda em "prefixo")`);
  const r = [];
  if (D.rotulo) r.push({ nome: 'rotulo', tipo: 'entrada', anim: d.media });
  r.push({ nome: 'numero', tipo: r.length ? 'enfase' : 'entrada', anim: d.media + (p.contagem === false ? 0 : d.longa * 1.6) + d.curta });
  if (D.contexto) r.push({ nome: 'contexto', tipo: 'texto', anim: d.longa });
  return r;
}

const ESTADOS = new WeakMap();

export function build(palco, p, ctx) {
  const D = dados(p);
  const ilustrativo = decidirIlustrativo(p, D.proprio, 'numero');
  const Q = montarQuadro(palco, { ...p, ilustrativo }, ctx, { roteiro: roteiro(p, ctx.DA.movimento) });
  const C = Q.conteudo, P = Q.P, cor = p.cor;
  const camada = ctx.el('div', 'numero-camada');
  Object.assign(camada.style, { position: 'absolute', left: '0', top: '0' });
  Q.raiz.appendChild(camada);
  const final = num(D.valor, D.casas);
  const empilhar = !Q.horizontal && !!D.unidade.trim();          // no vertical a unidade desce para a linha de baixo
  const largura = Q.horizontal ? Math.min(C.w, ctx.col(Math.ceil(ctx.DA.layout.grade.colunas * 0.8))) : C.w;

  const U = caber((s) => {
    const rot = D.rotulo ? escrever(ctx, camada, 'subtitulo', D.rotulo, { tam: tamanho(ctx, 'corpo', s), cor: 'texto_suave', maxW: largura, maxLinhas: 2, classe: 'numero-rotulo' }) : null;
    const tam = tamanho(ctx, 'display', s);
    const lado = (txt) => (txt ? `<span style="font-size: 0.4em">${ctx.esc(txt)}</span>` : '');
    const html = `${lado(D.prefixo)}<span class="numero-valor" style="color: ${ctx.cor(cor)}; font-variant-numeric: tabular-nums">${ctx.esc(final)}</span>${empilhar ? '' : lado(D.unidade)}`;
    const linha = escrever(ctx, camada, 'titulo', '', { tam, html, classe: 'numero-linha' });
    const uni = empilhar ? escrever(ctx, camada, 'titulo', D.unidade.trim(), { tam: tam * 0.36, maxW: largura, maxLinhas: 2, classe: 'numero-unidade' }) : null;
    const ctxo = D.contexto ? escrever(ctx, camada, 'corpo', '', { tam: tamanho(ctx, Q.horizontal ? 'h2' : 'h3', Math.min(1, s)), maxW: largura, maxLinhas: 3, html: marcarTermos(ctx, D.contexto, cor), classe: 'numero-contexto' }) : null;
    const vRot = rot ? tam * 0.1 : 0, vUni = uni ? tam * 0.02 : 0, vCtx = ctxo ? tam * 0.2 : 0;
    const h = (rot ? rot.h + vRot : 0) + linha.h + (uni ? vUni + uni.h : 0) + (ctxo ? vCtx + ctxo.h : 0);
    return { cabe: h <= C.h * respiro(s) && linha.w <= largura + 1, rot, linha, uni, ctxo, vRot, vUni, vCtx, h, tam };
  }, () => camada.replaceChildren(), { inicio: 1.7, min: 0.3 });
  encaixou(U, C, 'numero');

  const y0 = Math.round(C.y + Math.max(0, (C.h - U.h) / 2));
  let y = y0;
  if (U.rot) { U.rot.em(C.x, y); y += U.rot.h + U.vRot; }
  const casca = ctx.el('div', 'numero-casca');                    // leva o pulso de chegada: a entrada da DA fica com o texto
  Object.assign(casca.style, { position: 'absolute', left: Math.round(C.x) + 'px', top: Math.round(y) + 'px', width: Math.round(U.linha.w) + 'px', height: Math.round(U.linha.h) + 'px', transformOrigin: 'left 70%' });
  camada.appendChild(casca);
  casca.appendChild(U.linha.el);
  U.linha.em(0, 0);
  y += U.linha.h;
  if (U.uni) { U.uni.em(C.x, y + U.vUni); y += U.vUni + U.uni.h; }
  if (U.ctxo) U.ctxo.em(C.x, y + U.vCtx);
  const valorEl = U.linha.el.querySelector('.numero-valor');
  const tContagem = p.contagem === false ? 0 : ctx.dur('longa') * 1.6;
  if (tContagem) P.marcar('numero', ctx.dur('media') + tContagem, 'valor_final', 'enfase');
  guardar(ESTADOS, ctx, { ctx, Q, P, D, U, casca, valorEl, final, de: p.contar_de ?? 0, tContagem });
  return Q.layout({ texto_final: `${D.prefixo}${final}${D.unidade}`, valor: D.valor, escala: +U.escala.toFixed(3), tamanho_numero: +U.linha.tam.toFixed(1),
    bloco: { x: Math.round(C.x), y: y0, w: Math.round(Math.max(U.linha.w, U.rot ? U.rot.w : 0, U.ctxo ? U.ctxo.w : 0, U.uni ? U.uni.w : 0)), h: Math.round(U.h) } });
}

export function seek(t, ctxArg) {
  const { ctx, Q, P, D, U, casca, valorEl, final, de, tContagem } = ler(ESTADOS, ctxArg);
  const d = ctx.DA.movimento.duracoes;
  if (U.rot) ctx.entrada(U.rot.el, P.prog(t, 'rotulo', 0, d.media), undefined, { n: D.rotulo.length });
  ctx.entrada(U.linha.el, P.prog(t, 'numero', 0, d.media), 'fade');
  // contagem: linear no começo, freando no fim (curva `suave` da DA); o último valor é sempre o exato
  const pc = tContagem ? P.prog(t, 'numero', d.media * 0.5, tContagem + d.media * 0.5, 'suave') : 1;
  porTexto(valorEl, pc >= 1 ? final : num(lerp(de, D.valor, clamp(pc)), D.casas));
  const chegou = P.prog(t, 'numero', d.media + tContagem, d.curta, 'enfase');
  casca.style.transform = tContagem ? `scale(${lerp(0.96, 1, clamp(chegou)).toFixed(4)})` : 'none';
  valorEl.style.opacity = tContagem ? lerp(0.45, 1, clamp(chegou)).toFixed(3) : '1';       // valor provisório: esmaecido até ser o exato
  if (U.uni) ctx.entrada(U.uni.el, P.prog(t, 'numero', d.media * 0.5, d.media), 'fade');
  if (U.ctxo) ctx.entrada(U.ctxo.el, P.prog(t, 'contexto', 0, d.longa), undefined, { n: D.contexto.replace(/\*/g, '').length });
  Q.seek(t);
  // depois de Q.seek (que mostra o crédito logo no começo): com contagem, a fonte só aparece ao lado do valor exato
  if (Q.credito && tContagem) Q.credito.seek(P.prog(t, 'numero', d.media + tContagem, d.curta));      // dentro do `anim` do passo (roteiro)
}

export function key(t, ctx) { return ler(ESTADOS, ctx).P.chave(t); }

export function ancoras(ctx) { return ler(ESTADOS, ctx).P.ancoras(); }
