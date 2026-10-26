// lista.js — tópicos que entram um a um, no ritmo da fala. Passos: item1 → item2 → … → [recapitulacao].
// O tópico da vez fica com o marcador na cor do destaque e uma régua ao lado; os já falados continuam na tela, mais
// apagados (a lousa acumula); no fim, todos acendem juntos. Com `passos_t` (ou marcas | no trecho do storyboard) cada
// tópico dispara na palavra em que é dito.
// É cena de TEXTO: mostra o que a narração diz, sem selo "ilustrativo". Número ou nome de modelo dentro de um tópico
// é afirmação como qualquer outra: fato_ids no storyboard e `fonte`.
import { params, guardar, ler, montarQuadro, escrever, caber, tamanho, exigir, igual, marcarTermos, marcador, textoDuplo, clamp, lerp, encaixou, respiro } from './_ia.js';

const EXEMPLO = {
  chamada: 'Como um modelo de linguagem escreve',
  itens: ['Quebra o texto em *tokens*', 'Calcula a *probabilidade* de cada continuação', '*Sorteia* o próximo token', 'Repete, *um token por vez*'],
};

export const meta = {
  nome: 'lista',
  descricao: 'Lista: tópicos que entram um a um no ritmo da fala; o da vez fica em destaque, os anteriores continuam visíveis (mais apagados) e, no fim, todos acendem juntos.',
  dur_padrao: 11,
  formatos: ['horizontal', 'vertical', 'quadrado'],
  alfa_padrao: false,
  grao: true,
  params: params({
    itens: { tipo: 'lista', min: 2, max: 6, itens: { tipo: 'texto' }, padrao: EXEMPLO.itens,
      descricao: 'os tópicos, na ordem em que são falados (curtos: até umas 8 palavras; *asteriscos* destacam um termo)' },
    chamada: { tipo: 'texto', padrao: null, descricao: 'frase-título acima da lista ("" esconde; sem `itens` seus, vale a do exemplo)' },
    marcador: { tipo: 'opcao', opcoes: ['numero', 'ponto', 'traco', 'nenhum'], padrao: 'numero', descricao: 'o que vem antes de cada tópico' },
    anteriores: { tipo: 'opcao', opcoes: ['apagar', 'manter'], padrao: 'apagar', descricao: 'apagar = os tópicos já falados recuam quando o seguinte entra; manter = ficam acesos' },
    recapitular: { tipo: 'booleano', padrao: true, descricao: 'passo final em que todos os tópicos voltam a acender juntos (só com anteriores=apagar)' },
  }, { titulo: null, ilustrativo: 'texto' }),
};

const temRecap = (p, n) => p.recapitular !== false && (p.anteriores || 'apagar') === 'apagar' && n > 1;

export function roteiro(p, mov) {
  const d = mov.duracoes, itens = p.itens || EXEMPLO.itens;
  const r = itens.map((_, i) => ({ nome: 'item' + (i + 1), tipo: i ? 'texto' : 'entrada', anim: d.media + d.curta + (i ? 0 : d.media) }));
  if (temRecap(p, itens.length)) r.push({ nome: 'recapitulacao', tipo: 'enfase', anim: d.media });
  return r;
}

const ESTADOS = new WeakMap();

export function build(palco, p, ctx) {
  const textos = p.itens.map((x) => String(x).trim());
  exigir(textos.every(Boolean), 'itens: há um tópico vazio na lista');
  const chamada = p.chamada != null ? String(p.chamada).trim() : (igual(p.itens, EXEMPLO.itens) ? EXEMPLO.chamada : '');
  const Q = montarQuadro(palco, p, ctx, { roteiro: roteiro(p, ctx.DA.movimento) });
  const C = Q.conteudo, P = Q.P, cor = p.cor, n = textos.length;
  const camada = ctx.el('div', 'lista-camada');
  Object.assign(camada.style, { position: 'absolute', left: '0', top: '0' });
  Q.raiz.appendChild(camada);
  const largura = Q.horizontal ? Math.min(C.w, ctx.col(Math.ceil(ctx.DA.layout.grade.colunas * 0.8))) : C.w;
  const wRegua = Math.max(3, ctx.traco * 1.6);

  const U = caber((s) => {
    const tam = tamanho(ctx, Q.horizontal ? 'h2' : 'h3', s);
    const cab = chamada ? escrever(ctx, camada, 'titulo', chamada, { tam: tamanho(ctx, Q.horizontal ? 'h1' : 'h2', s * 0.86), maxW: largura, maxLinhas: 2, classe: 'lista-chamada' }) : null;
    // marcadores: número (papel dados, duas cores) ou forma desenhada
    const marcas = textos.map((_, i) => {
      if (p.marcador === 'nenhum') return null;
      if (p.marcador === 'numero') { const m = textoDuplo(ctx, 'dados', String(i + 1), { tam: tam * 0.82, corA: 'texto_suave', corB: cor, classe: 'lista-numero' }); camada.appendChild(m.el); m.medir(); return m; }
      const m = marcador(ctx, { tipo: p.marcador, lado: tam * 0.3, cor }); camada.appendChild(m.el); return m;
    });
    const wMarca = marcas[0] ? Math.max(...marcas.map((m) => m.w)) + tam * 0.55 : 0;
    const xMarca = wRegua + tam * 0.55, xTexto = xMarca + wMarca;
    const linhas = textos.map((txt) => escrever(ctx, camada, 'corpo', '', { tam, maxW: largura - xTexto, maxLinhas: 3, html: marcarTermos(ctx, txt, cor), classe: 'lista-item' }));
    const vao = tam * 0.5, vaoCab = cab ? tam * 0.95 : 0;
    const hItens = linhas.reduce((a, l) => a + l.h, 0) + (n - 1) * vao;
    const h = (cab ? cab.h + vaoCab : 0) + hItens;
    const w = Math.max(cab ? cab.w : 0, xTexto + Math.max(...linhas.map((l) => l.w)));
    return { cabe: h <= C.h * respiro(s) && w <= C.w + 1 && linhas.every((l) => l.linhas <= 3), tam, cab, marcas, linhas, vao, vaoCab, hItens, h, w, xMarca, xTexto, wMarca };
  }, () => camada.replaceChildren(), { inicio: Q.horizontal ? 1.3 : 1.1 });
  encaixou(U, C, 'lista');

  // posições: bloco centrado na altura do conteúdo, alinhado à esquerda (a grade da DA)
  const y0 = Math.round(C.y + Math.max(0, (C.h - U.h) / 2));
  if (U.cab) U.cab.em(C.x, y0);
  let y = y0 + (U.cab ? U.cab.h + U.vaoCab : 0);
  const yItens = y;
  const itens = U.linhas.map((l, i) => {
    const casca = ctx.el('div', 'lista-casca');                  // leva o "apagado": a entrada da DA mexe na opacidade do texto
    Object.assign(casca.style, { position: 'absolute', left: '0', top: '0' });
    camada.appendChild(casca);
    casca.appendChild(l.el);
    l.em(C.x + U.xTexto, y);
    const m = U.marcas[i];
    if (m) {
      casca.appendChild(m.el);
      const hLinha = l.h / l.linhas;                              // o marcador acompanha a PRIMEIRA linha do tópico
      const wM = m.w, hM = m.h;
      Object.assign(m.el.style, { left: Math.round(C.x + U.xMarca + (p.marcador === 'numero' ? U.wMarca - U.tam * 0.55 - wM : 0)) + 'px', top: Math.round(y + (hLinha - hM) / 2) + 'px' });
    }
    const item = { casca, texto: l, marca: m, y, h: l.h, letras: textos[i].replace(/\*/g, '').length };
    y += l.h + U.vao;
    return item;
  });
  const regua = ctx.el('div', 'lista-regua');
  Object.assign(regua.style, { position: 'absolute', left: Math.round(C.x) + 'px', top: '0', width: wRegua.toFixed(1) + 'px', height: '1px', background: ctx.cor(cor), transformOrigin: 'left top' });
  camada.appendChild(regua);

  guardar(ESTADOS, ctx, { ctx, Q, P, p, itens, cab: U.cab, regua, yItens, hItens: U.hItens, n, recap: temRecap(p, n), nCab: chamada.length });
  return Q.layout({ itens: n, tamanho_item: +U.tam.toFixed(1), escala: +U.escala.toFixed(3), marcador: p.marcador,
    bloco: { x: Math.round(C.x), y: y0, w: Math.round(U.w), h: Math.round(U.h) } });
}

export function seek(t, ctxArg) {
  const { ctx, Q, P, p, itens, cab, regua, yItens, hItens, n, recap, nCab } = ler(ESTADOS, ctxArg);
  const d = ctx.DA.movimento.duracoes;
  const pRecap = recap ? P.prog(t, 'recapitulacao', 0, d.media, 'suave') : 0;
  if (cab) ctx.entrada(cab.el, P.prog(t, 'item1', 0, d.media), undefined, { n: nCab });
  const atraso = (i) => (i === 0 ? (cab ? d.media : 0) : 0);
  // régua: nasce no 1º tópico, desliza para o da vez e, na recapitulação, abraça a lista inteira
  let ry = itens[0].y, rh = itens[0].h;
  itens.forEach((it, i) => {
    const pe = P.prog(t, 'item' + (i + 1), atraso(i), d.media);
    ctx.entrada(it.texto.el, pe, undefined, { n: it.letras });
    const chegou = P.prog(t, 'item' + (i + 1), atraso(i), d.media, 'enfase');
    const proximo = i < n - 1 ? P.prog(t, 'item' + (i + 2), 0, d.curta, 'suave') : 0;
    const daVez = clamp(chegou) * (1 - proximo);
    if (it.marca) { it.marca.el.style.opacity = clamp(pe * 2).toFixed(3); it.marca.misturar(daVez * (1 - pRecap)); }
    const apagado = p.anteriores === 'apagar' ? proximo * (1 - pRecap) : 0;
    it.casca.style.opacity = lerp(1, 0.4, clamp(apagado)).toFixed(3);
    if (i > 0) { const q = clamp(chegou); ry = lerp(ry, it.y, q); rh = lerp(rh, it.h, q); }
  });
  ry = lerp(ry, yItens, pRecap); rh = lerp(rh, hItens, pRecap);
  const nasce = P.prog(t, 'item1', atraso(0), d.media, 'enfase');
  regua.style.transform = `translateY(${ry.toFixed(2)}px) scaleY(${(rh * clamp(nasce)).toFixed(3)})`;
  regua.style.opacity = nasce > 0 ? '1' : '0';
  Q.seek(t);
}

export function key(t, ctx) { return ler(ESTADOS, ctx).P.chave(t); }

export function ancoras(ctx) { return ler(ESTADOS, ctx).P.ancoras(); }
