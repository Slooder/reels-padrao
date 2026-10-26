// conceito.js — um termo, a definição curta e um exemplo. Passos: termo → definicao → [exemplo].
// O termo entra grande, com um filete na cor do destaque; a definição vem depois (uma frase); o exemplo fica num
// cartão à parte, rotulado — exemplo não é definição, e a tela mantém os dois separados.
// É cena de TEXTO: a definição é afirmação do roteiro (confira em references/didatica.md ou na ficha de fatos). Se o
// exemplo for inventado e puder passar por dado real, use ilustrativo=true (selo); número de modelo exige fato e fonte.
import { params, guardar, ler, montarQuadro, escrever, caber, tamanho, exigir, marcarTermos, cartao, entrarBloco, clamp, encaixou, respiro } from './_ia.js';

const EXEMPLO = {
  termo: 'Token',
  definicao: 'O menor pedaço de texto que o modelo lê e escreve: uma *palavra*, *parte de uma palavra* ou um *sinal*.',
  exemplo: '“Tokenização” pode virar dois pedaços: “Token” + “ização”.',
};

export const meta = {
  nome: 'conceito',
  descricao: 'Conceito: um termo em destaque, a definição curta e um exemplo num cartão à parte — para apresentar vocabulário (token, embedding, janela de contexto, RAG…).',
  dur_padrao: 9,
  formatos: ['horizontal', 'vertical', 'quadrado'],
  alfa_padrao: false,
  grao: true,
  params: params({
    termo: { tipo: 'texto', padrao: EXEMPLO.termo, descricao: 'o termo (1 a 3 palavras)' },
    sub: { tipo: 'texto', padrao: null, descricao: 'linha pequena sob o termo: a sigla por extenso, a tradução ou a pronúncia (ex.: "geração aumentada por recuperação")' },
    definicao: { tipo: 'texto', padrao: null, descricao: 'a definição em UMA frase (até umas 25 palavras; *asteriscos* destacam)' },
    exemplo: { tipo: 'texto', padrao: null, descricao: 'um exemplo curto ("" ou ausente: a cena fica sem o passo do exemplo)' },
    rotulo_exemplo: { tipo: 'texto', padrao: 'exemplo', descricao: 'rótulo do cartão do exemplo ("exemplo", "na prática", "não confunda")' },
  }, { titulo: 'Conceito', ilustrativo: 'texto' }),
};

function dados(p) {
  const padrao = (p.termo ?? EXEMPLO.termo) === EXEMPLO.termo && p.definicao == null;
  const definicao = String(p.definicao ?? (padrao ? EXEMPLO.definicao : '')).trim();
  const exemplo = String(p.exemplo ?? (padrao ? EXEMPLO.exemplo : '')).trim();
  return { termo: String(p.termo ?? EXEMPLO.termo).trim(), definicao, exemplo, sub: String(p.sub ?? '').trim() };
}

export function roteiro(p, mov) {
  const d = mov.duracoes, D = dados(p);
  exigir(D.termo, 'termo: faltou o termo');
  exigir(D.definicao, `faltou "definicao": a cena conceito mostra o termo "${D.termo}" e a definição dele em uma frase`);
  const r = [{ nome: 'termo', tipo: 'entrada', anim: d.longa + d.media }, { nome: 'definicao', tipo: 'texto', anim: d.longa }];
  if (D.exemplo) r.push({ nome: 'exemplo', tipo: 'enfase', anim: d.media * 2 });
  return r;
}

const ESTADOS = new WeakMap();

export function build(palco, p, ctx) {
  const D = dados(p);
  const Q = montarQuadro(palco, p, ctx, { roteiro: roteiro(p, ctx.DA.movimento) });
  const C = Q.conteudo, P = Q.P, cor = p.cor;
  const camada = ctx.el('div', 'conceito-camada');
  Object.assign(camada.style, { position: 'absolute', left: '0', top: '0' });
  Q.raiz.appendChild(camada);
  const duasColunas = Q.horizontal && !!D.exemplo;
  const vaoCol = ctx.px(0.07);
  const wEsq = duasColunas ? (C.w - vaoCol) * 0.58 : Q.horizontal ? Math.min(C.w, ctx.col(Math.ceil(ctx.DA.layout.grade.colunas * 0.75))) : C.w;
  const wDir = duasColunas ? C.w - vaoCol - wEsq : wEsq;
  const esp = Math.max(3, ctx.traco * 1.6);

  const U = caber((s) => {
    const termo = escrever(ctx, camada, 'titulo', D.termo, { tam: tamanho(ctx, Q.horizontal ? 'display' : 'h1', s), maxW: wEsq, maxLinhas: 2, classe: 'conceito-termo' });
    const sub = D.sub ? escrever(ctx, camada, 'dados', D.sub, { tam: tamanho(ctx, 'corpo', s), cor: 'texto_suave', maxW: wEsq, maxLinhas: 2, classe: 'conceito-sub' }) : null;
    const def = escrever(ctx, camada, 'corpo', '', { tam: tamanho(ctx, Q.horizontal ? 'h2' : 'h3', s), maxW: wEsq, maxLinhas: Q.horizontal ? 4 : 6, html: marcarTermos(ctx, D.definicao, cor), classe: 'conceito-definicao' });
    const vTermo = termo.tam * 0.16, vFilete = termo.tam * 0.3, vSub = sub ? sub.tam * 0.5 : 0;
    const hEsq = termo.h + vTermo + esp + (sub ? vSub + sub.h : 0) + vFilete + def.h;
    let ex = null, hEx = 0;
    if (D.exemplo) {
      const pad = tamanho(ctx, 'corpo', s) * 0.9;
      const rot = escrever(ctx, camada, 'dados', p.rotulo_exemplo, { tam: tamanho(ctx, 'nota', s), cor: 'texto_suave', classe: 'conceito-rotulo' });
      const txt = escrever(ctx, camada, 'corpo', '', { tam: tamanho(ctx, 'h3', s), maxW: wDir - 2 * pad - esp, maxLinhas: 5, html: marcarTermos(ctx, D.exemplo, cor), classe: 'conceito-exemplo' });
      hEx = pad + rot.h + pad * 0.45 + txt.h + pad;
      ex = { rot, txt, pad, h: hEx };
    }
    const vaoEx = D.exemplo && !duasColunas ? tamanho(ctx, 'h3', s) * 1.1 : 0;
    const h = duasColunas ? Math.max(hEsq, hEx) : hEsq + vaoEx + hEx;
    return { cabe: h <= C.h * respiro(s) && termo.w <= wEsq + 1 && def.linhas <= (Q.horizontal ? 4 : 6), termo, sub, def, ex, vTermo, vFilete, vSub, hEsq, hEx, vaoEx, h };
  }, () => camada.replaceChildren(), { inicio: Q.horizontal ? 1.1 : 1 });
  encaixou(U, C, 'conceito');

  const y0 = Math.round(C.y + Math.max(0, (C.h - U.h) / 2));
  const yEsq = duasColunas ? y0 + (U.h - U.hEsq) / 2 : y0;
  U.termo.em(C.x, yEsq);
  const filete = ctx.el('div', 'conceito-filete');
  const wFilete = Math.max(U.termo.w, ctx.px(0.08));
  Object.assign(filete.style, { position: 'absolute', left: Math.round(C.x) + 'px', top: Math.round(yEsq + U.termo.h + U.vTermo) + 'px', width: Math.round(wFilete) + 'px', height: esp.toFixed(1) + 'px', background: ctx.cor(cor), transformOrigin: 'left center' });
  camada.appendChild(filete);
  let y = yEsq + U.termo.h + U.vTermo + esp;
  if (U.sub) { U.sub.em(C.x, y + U.vSub); y += U.vSub + U.sub.h; }
  U.def.em(C.x, y + U.vFilete);
  let caixa = null;
  if (U.ex) {
    // em duas colunas o cartão do exemplo nasce na altura da definição (os dois se leem juntos), sem passar da base do bloco
    const xEx = duasColunas ? C.x + wEsq + vaoCol : C.x;
    const yEx = duasColunas ? Math.max(y0, Math.min(U.def.y, y0 + U.h - U.hEx)) : yEsq + U.hEsq + U.vaoEx;
    caixa = cartao(ctx, { w: wDir, h: U.hEx, cor });
    camada.appendChild(caixa.el);
    caixa.em(xEx, yEx);
    const barra = ctx.el('div', 'conceito-barra');                // filete lateral: o cartão é do exemplo, não da definição
    Object.assign(barra.style, { position: 'absolute', left: '0', top: '0', width: esp.toFixed(1) + 'px', height: '100%', background: ctx.cor(cor) });
    caixa.miolo.append(barra, U.ex.rot.el, U.ex.txt.el);
    U.ex.rot.em(esp + U.ex.pad, U.ex.pad);
    U.ex.txt.em(esp + U.ex.pad, U.ex.pad + U.ex.rot.h + U.ex.pad * 0.45);
  }
  guardar(ESTADOS, ctx, { ctx, Q, P, U, filete, caixa, n: { termo: D.termo.length, def: D.definicao.replace(/\*/g, '').length, ex: D.exemplo.replace(/\*/g, '').length } });
  return Q.layout({ colunas: duasColunas ? 2 : 1, escala: +U.escala.toFixed(3), tamanho_termo: +U.termo.tam.toFixed(1), tamanho_definicao: +U.def.tam.toFixed(1),
    bloco: { x: Math.round(C.x), y: y0, w: Math.round(duasColunas ? C.w : Math.max(U.termo.w, U.def.w, U.ex ? wDir : 0)), h: Math.round(U.h) } });
}

export function seek(t, ctxArg) {
  const { ctx, Q, P, U, filete, caixa, n } = ler(ESTADOS, ctxArg);
  const d = ctx.DA.movimento.duracoes;
  ctx.entrada(U.termo.el, P.prog(t, 'termo', 0, d.longa), undefined, { n: n.termo });
  const pf = P.prog(t, 'termo', d.media, d.longa, 'enfase');
  filete.style.transform = `scaleX(${clamp(pf).toFixed(4)})`;
  filete.style.opacity = pf > 0 ? '1' : '0';
  if (U.sub) ctx.entrada(U.sub.el, P.prog(t, 'termo', d.longa, d.media), 'fade');
  ctx.entrada(U.def.el, P.prog(t, 'definicao', 0, d.longa), undefined, { n: n.def });
  if (caixa) {
    entrarBloco(ctx, caixa.el, P.prog(t, 'exemplo', 0, d.media));
    ctx.entrada(U.ex.rot.el, P.prog(t, 'exemplo', d.media * 0.5, d.media), 'fade');
    ctx.entrada(U.ex.txt.el, P.prog(t, 'exemplo', d.media * 0.5, d.media * 1.5), undefined, { n: n.ex });
  }
  Q.seek(t);
}

export function key(t, ctx) { return ler(ESTADOS, ctx).P.chave(t); }

export function ancoras(ctx) { return ler(ESTADOS, ctx).P.ancoras(); }
