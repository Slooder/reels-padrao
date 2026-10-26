// terminal.js — uma janela de terminal: o comando (ou o código) é digitado e a saída aparece. Passos, por bloco:
// comando1 → [saida1] → comando2 → [saida2] → …
// Digitar aqui é CONTEÚDO, não efeito: o comando é revelado caractere a caractere em todas as DAs (peça `digitador`
// de _ia.js), com o cursor na cor do destaque; a saída entra linha a linha (`saida_modo: "linhas"`, como um programa
// imprime) ou caractere a caractere (`"fluxo"`, como a resposta de um modelo chegando).
// O exemplo padrão é inventado (selo "ilustrativo"): os comandos `perguntar` e `contar-tokens` não existem e a saída
// não veio de modelo nenhum. Para mostrar um comando real com a saída real: ilustrativo=false + `fonte` + fato_ids.
import { params, guardar, ler, montarQuadro, escrever, caber, tamanho, exigir, cartao, digitador, entrarBloco, clamp, encaixou, respiro } from './_ia.js';

const EXEMPLO = [
  { comando: 'perguntar "O que é um token?"', saida: ['Um pedaço de texto: uma palavra, parte de uma palavra ou um sinal de pontuação.'] },
  { comando: 'contar-tokens "Tokenização não é mágica."', saida: ['7 tokens'] },
];

export const meta = {
  nome: 'terminal',
  descricao: 'Terminal: o comando ou o código é digitado caractere a caractere, com cursor, e a saída aparece embaixo (linha a linha, ou em fluxo como resposta de modelo) — até 3 blocos de comando e saída.',
  dur_padrao: 11,
  formatos: ['horizontal', 'vertical', 'quadrado'],
  alfa_padrao: false,
  grao: true,
  params: params({
    blocos: { tipo: 'lista', min: 1, max: 3, padrao: EXEMPLO, descricao: 'cada bloco: o comando digitado e as linhas de saída (espaços e recuos são preservados)',
      itens: { tipo: 'objeto', campos: { comando: { tipo: 'texto', obrigatorio: true }, saida: { tipo: 'lista', padrao: [], max: 8, itens: { tipo: 'texto' } } } } },
    prompt: { tipo: 'texto', padrao: '$', descricao: 'o sinal antes do comando ("$", ">>>", ">")' },
    janela: { tipo: 'texto', padrao: 'terminal', descricao: 'texto da barra da janela ("" esconde a barra)' },
    saida_modo: { tipo: 'opcao', opcoes: ['linhas', 'fluxo'], padrao: 'linhas', descricao: 'linhas = a saída entra linha a linha; fluxo = caractere a caractere, como resposta de modelo chegando' },
    destaque: { tipo: 'texto', padrao: null, descricao: 'trecho da saída que ganha a cor do destaque (texto exato)' },
  }, { titulo: null }),
};

const POR_LETRA = 0.5, POR_LETRA_SAIDA = 0.22, POR_LINHA = 1.5;       // em múltiplos de movimento.duracoes.micro
const tDigita = (d, txt) => Math.max(d.longa, Math.min(d.longa * 3, String(txt).length * d.micro * POR_LETRA));
const tSaida = (d, saida, modo) => (modo === 'fluxo'
  ? Math.max(d.media, Math.min(d.longa * 4, saida.join('').length * d.micro * POR_LETRA_SAIDA))
  : d.media + (saida.length - 1) * d.micro * POR_LINHA);

export function roteiro(p, mov) {
  const d = mov.duracoes, blocos = p.blocos || EXEMPLO;
  const r = [];
  blocos.forEach((b, i) => {
    exigir(String(b.comando || '').trim(), `blocos[${i}]: o comando está vazio`);
    r.push({ nome: 'comando' + (i + 1), tipo: i ? 'texto' : 'entrada', anim: (i ? 0 : d.media) + tDigita(d, b.comando) + d.curta });
    const saida = b.saida || [];
    if (saida.length) r.push({ nome: 'saida' + (i + 1), tipo: 'texto', anim: tSaida(d, saida, p.saida_modo) + d.curta });
  });
  return r;
}

const ESTADOS = new WeakMap();

export function build(palco, p, ctx) {
  const blocos = p.blocos, cor = p.cor;
  const Q = montarQuadro(palco, p, ctx, { roteiro: roteiro(p, ctx.DA.movimento) });
  const C = Q.conteudo, P = Q.P;
  const camada = ctx.el('div', 'term-camada');
  Object.assign(camada.style, { position: 'absolute', left: '0', top: '0' });
  Q.raiz.appendChild(camada);
  const wJanela = Q.horizontal ? Math.min(C.w, ctx.col(Math.ceil(ctx.DA.layout.grade.colunas * 0.84))) : C.w;
  const temBarra = !!String(p.janela ?? '').trim();
  const marcar = (txt) => {
    const seguro = ctx.esc(txt), alvo = p.destaque ? ctx.esc(String(p.destaque)) : '';
    return alvo && seguro.includes(alvo) ? seguro.split(alvo).join(`<span style="color: ${ctx.cor(cor)}">${alvo}</span>`) : seguro;
  };

  const U = caber((s) => {
    const tam = tamanho(ctx, 'h3', s), pad = tam * 0.85;
    const hBarra = temBarra ? ctx.tam('nota') * 2.1 : 0;
    const wCorpo = wJanela - 2 * pad;
    const sinal = escrever(ctx, camada, 'dados', String(p.prompt), { tam, cor, classe: 'term-prompt' });
    const recuo = sinal.w + tam * 0.55;
    const vao = tam * 0.34, vaoBloco = tam * 0.75;
    let y = hBarra + pad, largo = false;
    const partes = blocos.map((b, i) => {
      const cmd = escrever(ctx, camada, 'dados', String(b.comando), { tam, maxW: wCorpo - recuo, pre: true, classe: 'term-comando' });
      if (cmd.linhas > 2) largo = true;
      const yCmd = y;
      y += cmd.h;
      const saidas = (b.saida || []).map((ln) => {
        const e = escrever(ctx, camada, 'dados', '', { tam, maxW: wCorpo, pre: true, html: marcar(String(ln) || ' '), classe: 'term-saida' });
        if (e.linhas > 3) largo = true;
        y += vao;
        const yo = y;
        y += e.h;
        return { e, y: yo };
      });
      y += i < blocos.length - 1 ? vaoBloco : 0;
      return { cmd, yCmd, saidas };
    });
    const h = y + pad;
    return { cabe: h <= C.h * respiro(s) && !largo, tam, pad, hBarra, sinal, recuo, partes, h };
  }, () => camada.replaceChildren(), { inicio: Q.horizontal ? 1.2 : 1, min: 0.45 });
  encaixou(U, C, 'terminal');

  const y0 = Math.round(C.y + Math.max(0, (C.h - U.h) / 2));
  const janela = cartao(ctx, { w: wJanela, h: U.h, cor });
  camada.appendChild(janela.el);
  janela.em(C.x, y0);
  if (temBarra) {                                                  // barra: três discos vazados e o nome da janela
    const barra = ctx.el('div', 'term-barra');
    Object.assign(barra.style, { position: 'absolute', left: '0', top: '0', width: '100%', height: Math.round(U.hBarra) + 'px', boxSizing: 'border-box', borderBottom: `${Math.max(1, ctx.traco * 0.75).toFixed(1)}px solid ${ctx.alfa('texto_suave', 0.55)}` });
    janela.miolo.appendChild(barra);
    const dco = ctx.tam('nota') * 0.5;
    for (let i = 0; i < 3; i++) {
      const o = ctx.el('div', 'term-disco');
      Object.assign(o.style, { position: 'absolute', left: Math.round(U.pad + i * dco * 1.7) + 'px', top: Math.round((U.hBarra - dco) / 2) + 'px', width: dco.toFixed(1) + 'px', height: dco.toFixed(1) + 'px', borderRadius: '50%', boxSizing: 'border-box',
        border: `${Math.max(1, ctx.traco * 0.75).toFixed(1)}px solid ${ctx.cor('texto_suave')}` });
      barra.appendChild(o);
    }
    const nome = escrever(ctx, barra, 'dados', String(p.janela), { tam: ctx.tam('nota'), cor: 'texto_suave', classe: 'term-nome' });
    nome.em(U.pad + 3 * dco * 1.7 + dco, (U.hBarra - nome.h) / 2);
  }
  const d = ctx.DA.movimento.duracoes;
  const sinais = [], linhas = [];
  U.partes.forEach((pt, i) => {
    const sinal = i === 0 ? U.sinal : escrever(ctx, camada, 'dados', String(p.prompt), { tam: U.tam, cor, classe: 'term-prompt' });
    janela.miolo.append(sinal.el, pt.cmd.el);
    sinal.em(U.pad, pt.yCmd);
    pt.cmd.em(U.pad + U.recuo, pt.yCmd);
    sinais.push(sinal);
    pt.dig = digitador(ctx, pt.cmd.el);
    pt.tCmd = tDigita(d, blocos[i].comando);
    pt.saidas.forEach((sd) => { janela.miolo.appendChild(sd.e.el); sd.e.em(U.pad, sd.y); if (p.saida_modo === 'fluxo') sd.dig = digitador(ctx, sd.e.el); });
    pt.letras = pt.saidas.map((sd) => (sd.dig ? sd.dig.total : 0));
    pt.tSaida = pt.saidas.length ? tSaida(d, blocos[i].saida, p.saida_modo) : 0;
    P.marcar('comando' + (i + 1), (i ? 0 : d.media) + pt.tCmd, 'fim_da_digitacao', 'texto');
  });
  const cursor = ctx.el('div', 'term-cursor');
  Object.assign(cursor.style, { position: 'absolute', left: '0', top: '0', width: (U.tam * 0.52).toFixed(1) + 'px', height: '10px', background: ctx.cor(cor), transformOrigin: 'left top' });
  janela.miolo.appendChild(cursor);
  guardar(ESTADOS, ctx, { ctx, Q, P, p, U, janela, sinais, cursor, fluxo: p.saida_modo === 'fluxo' });
  return Q.layout({ blocos: blocos.length, escala: +U.escala.toFixed(3), tamanho_letra: +U.tam.toFixed(1), saida_modo: p.saida_modo,
    bloco: { x: Math.round(C.x), y: y0, w: Math.round(wJanela), h: Math.round(U.h) } });
}

export function seek(t, ctxArg) {
  const { ctx, Q, P, U, janela, sinais, cursor, fluxo } = ler(ESTADOS, ctxArg);
  const d = ctx.DA.movimento.duracoes;
  entrarBloco(ctx, janela.el, P.prog(t, 'comando1', 0, d.media));
  let cur = null;
  U.partes.forEach((pt, i) => {
    const passo = 'comando' + (i + 1), at = i ? 0 : d.media;
    const comecou = P.passou(t, passo);
    sinais[i].el.style.opacity = (i === 0 ? clamp(P.prog(t, passo, d.media * 0.5, d.media * 0.5)) : comecou ? 1 : 0).toFixed(3);
    const pos = pt.dig.seek(P.lin(t, passo, at, pt.tCmd));
    const temSaida = pt.saidas.length > 0;
    const saiu = temSaida && P.passou(t, 'saida' + (i + 1));
    if (comecou && !saiu) cur = { x: pt.cmd.x + pos.x, y: pt.cmd.y + pos.y0, h: pos.y1 - pos.y0, digitando: !pos.fim && pos.vistos > 0 };
    if (!temSaida) return;
    const ps = 'saida' + (i + 1);
    if (fluxo) {                                                   // caractere a caractere, uma linha depois da outra
      const total = pt.letras.reduce((a, b) => a + b, 0) || 1;
      const q = P.lin(t, ps, 0, pt.tSaida) * total;
      let antes = 0;
      pt.saidas.forEach((sd, k) => { sd.dig.seek(clamp((q - antes) / Math.max(1, pt.letras[k]))); antes += pt.letras[k]; });
    } else pt.saidas.forEach((sd, k) => ctx.entrada(sd.e.el, P.prog(t, ps, k * d.micro * POR_LINHA, d.media), 'fade'));
  });
  if (cur) {
    cursor.style.opacity = '1';
    cursor.style.transform = `translate(${(cur.x + U.tam * 0.08).toFixed(2)}px, ${(cur.y + cur.h * 0.1).toFixed(2)}px) scaleY(${(cur.h * 0.8 / 10).toFixed(4)})`;
  } else cursor.style.opacity = '0';
  Q.seek(t);
}

export function key(t, ctx) { return ler(ESTADOS, ctx).P.chave(t); }

export function ancoras(ctx) { return ler(ESTADOS, ctx).P.ancoras(); }
