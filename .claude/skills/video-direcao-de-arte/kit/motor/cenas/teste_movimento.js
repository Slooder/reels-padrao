// teste_movimento.js — o teste de movimento da DA em três atos, cada peça sozinha na tela (como na produção):
//   1. titulo  cartela de título entra, respira e sai;
//   2. gc      GC sobre um quadro do projeto (params.fundo), na posição da PRODUÇÃO (reservar_legenda null = o que
//              legenda.reservar_em da DA mandar). Onde a DA reserva a faixa da legenda (vertical e quadrado, por
//              padrão), a legenda corre palavra a palavra junto com o GC, que desvia dela. Onde não reserva e os dois
//              ocupam a mesma faixa (horizontal, por padrão), o ato mostra só o GC — é o que a produção entrega;
//   3. barras  gráfico de barras entra, conta até o valor final e fica.
// Entre os atos, a transição padrão da DA (movimento.transicoes.padrao, via ctx.transicao).
// Os TEMPOS saem das durações da DA (plano()): nenhuma animação é cortada em preset lento. `--dur` só estica ou encolhe
// os respiros (nunca abaixo de 0,2 s); a duração efetiva é a que duracao() devolve ao motor.
import * as cenaTitulo from './titulo.js';
import * as cenaGc from './gc.js';
import * as cenaBarras from './barras.js';
import { fraseDeAmostra } from './_legenda.js';

const ATOS = ['titulo', 'gc', 'barras'];
const RESPIRO = 0.7, RESPIRO_MIN = 0.2;
const BARRAS = [{ rotulo: 'Santa Catarina', valor: 0.31 }, { rotulo: 'São Paulo', valor: 0.28 }, { rotulo: 'Paraná', valor: 0.42 }, { rotulo: 'Bahia', valor: 1.65 }, { rotulo: 'Maranhão', valor: 2.4 }];

export const meta = {
  nome: 'teste_movimento',
  descricao: 'Teste de movimento em três atos (título → GC sobre footage, com a legenda onde a DA reserva a faixa dela → barras) com as curvas, durações e a transição da DA.',
  dur_padrao: 6,
  formatos: ['horizontal', 'vertical', 'quadrado'],
  alfa_padrao: false,
  grao: true,
  params: {
    titulo: { tipo: 'texto', padrao: 'A conta que não fecha', descricao: 'título da cartela (com um título próprio, as primeiras palavras viram a legenda do 2º ato)' },
    nome: { tipo: 'texto', padrao: 'Mariana Albuquerque', descricao: 'nome do GC' },
    cargo: { tipo: 'texto', padrao: 'Procuradora de Justiça', descricao: 'cargo do GC' },
    fundo: { tipo: 'arquivo', padrao: null, descricao: 'quadro do projeto para o 2º ato (footage já tratado); sem ele, um plano em superficie' },
    atos: { tipo: 'lista', padrao: null, min: 1, max: 3, descricao: 'quais atos renderizar, na ordem fixa titulo → gc → barras (padrão: os três)', itens: { tipo: 'opcao', opcoes: ATOS } },
  },
};

/**
 * Plano de tempos a partir da DA — função pura, usada pelo motor (no Node, para decidir a duração) e pelo build.
 * Cada ato = [transição de chegada] + entrada completa + respiro + saída. `pedida` (s) só mexe no respiro.
 */
export function plano(DA, { atos = null, pedida = null } = {}) {
  const m = DA.movimento, d = m.duracoes, e = m.escalonamento;
  const trans = m.transicoes.padrao === 'corte' ? 0 : d.media;
  const entrada = {
    titulo: 0.05 + Math.max(2 * e + d.longa, 8 * e + d.media),                     // tarja → título (longa) → filete → subtítulo → assinatura
    gc: 4 * e + d.media,                                                           // raiz → acento → nome → cargo
    barras: 0.05 + (4 + 1.5 * (BARRAS.length - 1)) * e + d.longa + 0.5 * d.media,   // título → grade → barras escalonadas (longa) → crédito
  };
  const saida = { titulo: d.media, gc: d.media, barras: 0 };                       // o gráfico fica: o último quadro mostra os valores finais
  const lista = ATOS.filter((a) => !atos || atos.includes(a));
  const fixo = lista.reduce((s, a, i) => s + (i > 0 ? trans : 0) + entrada[a] + saida[a], 0);
  let respiro = RESPIRO;
  if (pedida != null && Number.isFinite(+pedida)) respiro = Math.max(RESPIRO_MIN, (+pedida - fixo) / lista.length);
  const janelas = {};
  let t = 0;
  lista.forEach((a, i) => {
    const pre = i > 0 ? trans : 0;
    const cena = entrada[a] + respiro + saida[a];
    janelas[a] = { t0: +t.toFixed(4), pre, inicio: +(t + pre).toFixed(4), cena: +cena.toFixed(4), entrada: +entrada[a].toFixed(4), saida: saida[a] };
    t += pre + cena;
  });
  const r3 = (v) => +v.toFixed(3);
  return { atos: lista, janelas, total: r3(t), respiro: r3(respiro), transicao: m.transicoes.padrao, dur_transicao: trans,
    minima: r3(fixo + RESPIRO_MIN * lista.length), natural: r3(fixo + RESPIRO * lista.length) };
}

/** Contrato opcional do motor: a cena calcula a própria duração (o --dur pedido chega em `pedida`). */
export function duracao({ DA, params, pedida }) {
  return plano(DA, { atos: params && params.atos, pedida }).total;
}

const S = {};

function camada(ctx, palco, nome) {
  const c = ctx.el('div', 'camada camada-' + nome);
  Object.assign(c.style, { position: 'absolute', inset: '0', background: ctx.cor('fundo'), overflow: 'hidden' });
  palco.appendChild(c);
  return c;
}

export async function build(palco, p, ctx) {
  const P = plano(ctx.DA, { atos: p.atos, pedida: ctx.duracao });
  const J = P.janelas, cams = {}, sub = {};
  const info = { ...P };
  if (J.titulo) {
    cams.titulo = camada(ctx, palco, 'titulo');
    sub.titulo = ctx.sub({ L: ctx.L, A: ctx.A, palco: cams.titulo, dur: J.titulo.cena });
    info.titulo = await cenaTitulo.build(cams.titulo, { titulo: p.titulo, sobretitulo: 'Capítulo 2', subtitulo: 'Teste de movimento da direção de arte', alinhar: 'esquerda', posicao: 'centro',
      escala_titulo: 'display', assinatura: true, plataforma: null, reservar_legenda: null }, sub.titulo);
  }
  if (J.gc) {
    cams.gc = camada(ctx, palco, 'gc');
    cams.gc.style.background = ctx.cor('superficie');
    if (p.fundo) {
      const im = document.createElement('img');
      im.src = p.fundo; im.alt = ''; im.setAttribute('data-da-livre', 'footage de referência do projeto');
      Object.assign(im.style, { position: 'absolute', inset: '0', width: '100%', height: '100%', objectFit: 'cover' });
      cams.gc.appendChild(im);
    }
    sub.gc = ctx.sub({ L: ctx.L, A: ctx.A, palco: cams.gc, dur: J.gc.cena, alfa: true });
    // o GC do teste é o da produção (reservar_legenda null): a legenda só entra junto se a DA reserva a faixa dela neste
    // formato — ou se, sem reserva, os dois não se tocam. Senão o ato mostra só o GC, como a produção vai entregar.
    info.gc = await cenaGc.build(cams.gc, { nome: p.nome, cargo: p.cargo, foto: null, selo: null, plataforma: null, entrada_em: 0, saida_em: null, reservar_legenda: null }, sub.gc);
    const f = sub.gc.faixa_legenda(), g = info.gc.caixa;
    const juntos = !!info.gc.reservou_legenda || !(g.x < f.x1 && f.x0 < g.x1 && g.y < f.y1 && f.y0 < g.y1);
    S.leg = null; S.palavras = 0;
    info.legenda = null;
    info.gc_e_legenda_juntos = juntos;
    if (juntos) {
      const palavras = fraseDeAmostra(ctx.DA.legenda.max_palavras, p.titulo);
      S.leg = sub.gc.kit.legenda(palavras, { falada: -1 });
      cams.gc.appendChild(S.leg.el);
      S.leg.posicionar();
      S.palavras = palavras.length;
      info.legenda = S.leg.layout.caixa;
    } else {
      info.legenda_omitida = `"${sub.gc.orientacao}" não está em legenda.reservar_em e o GC ocupa a faixa da legenda (y ${Math.round(f.y0)} a ${Math.round(f.y1)} px): os dois não entram juntos`;
    }
  }
  if (J.barras) {
    cams.barras = camada(ctx, palco, 'barras');
    sub.barras = ctx.sub({ L: ctx.L, A: ctx.A, palco: cams.barras, dur: J.barras.cena + ctx.dur('longa') + 5 });   // a saída da cena nunca começa dentro do teste
    info.barras = await cenaBarras.build(cams.barras, { titulo: 'Quanto cada estado recebe de volta por real enviado', dados: BARRAS, unidade: '', prefixo: 'R$ ', casas: 2, destaque: 0, max: null,
      fonte: 'Tesouro Nacional, 2024', cores: 'serie', plataforma: null, empilhado: null, reservar_legenda: null }, sub.barras);
  }
  Object.assign(S, { ctx, P, J, cams });
  return info;
}

function mostrar(c, visivel) {
  Object.assign(c.style, { opacity: '1.000', transform: 'none', clipPath: 'none', zIndex: visivel ? '1' : '0', visibility: visivel ? 'visible' : 'hidden' });
}

export function seek(t) {
  const { ctx, P, J, cams } = S;
  // função pura de t: toda cena recebe o estado dela para o tempo LOCAL deste instante; quem aparece é decidido depois
  if (J.titulo) cenaTitulo.seek(ctx.clamp(t - J.titulo.inicio, 0, J.titulo.cena));
  if (J.gc) {
    const tl = ctx.clamp(t - J.gc.inicio, 0, J.gc.cena);
    cenaGc.seek(tl);
    if (S.leg) {
      // a legenda corre durante o ato: uma palavra por vez, do fim da entrada do GC até a saída
      const ini = J.gc.entrada * 0.4, fim = J.gc.cena - J.gc.saida * 0.5;
      const passo = (fim - ini) / Math.max(1, S.palavras);
      const i = tl < ini ? -1 : Math.min(S.palavras - 1, Math.floor((tl - ini) / passo));
      S.leg.seek(i, { pulso: i < 0 ? 1 : ctx.clamp((tl - ini - i * passo) / Math.max(1e-6, ctx.dur('curta'))) });
    }
  }
  if (J.barras) cenaBarras.seek(ctx.clamp(t - J.barras.inicio, 0, J.barras.cena));
  const atual = [...P.atos].reverse().find((a) => t >= J[a].t0) || P.atos[0];
  const i = P.atos.indexOf(atual);
  for (const a of P.atos) mostrar(cams[a], a === atual);
  if (i > 0 && J[atual].pre > 0 && t < J[atual].inicio) {
    const anterior = P.atos[i - 1];
    mostrar(cams[anterior], true);
    ctx.transicao(cams[anterior], cams[atual], ctx.prog(t, J[atual].t0, J[atual].pre, 'suave'));
  }
}

export function ancoras() {
  const { P, J } = S;
  const a = [];
  P.atos.forEach((nome, i) => {
    if (i > 0) a.push({ t: J[nome].t0, nome: 'transicao_' + nome, tipo: 'transicao' });
    a.push({ t: J[nome].inicio, nome, tipo: 'entrada' });
    if (J[nome].saida > 0) a.push({ t: +(J[nome].inicio + J[nome].cena - J[nome].saida).toFixed(3), nome: nome + '_saida', tipo: 'saida' });
  });
  return a;
}
