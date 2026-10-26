// chat.js — uma conversa em bolhas: a pergunta entra inteira; a resposta do modelo chega TOKEN A TOKEN (streaming),
// com um contador de tokens. Passos: pergunta1 → resposta1 → pergunta2 → resposta2 → …
// O que a cena mostra de verdade: a resposta não aparece pronta — o modelo gera um pedaço por vez e a interface vai
// mostrando. A bolha cresce linha a linha; cada token nasce na cor do destaque e assenta na cor do texto.
// Fidelidade: sem `tokens`, o recorte da resposta em pedaços é DE EXEMPLO (palavras, pontuação e palavras longas
// partidas em duas) — não é a tokenização de modelo nenhum; com `tokens` (a lista real, que remonta o texto exato)
// o contador passa a contar tokens de verdade. A conversa padrão é inventada (selo "ilustrativo"): resposta real de
// um modelo exige ilustrativo=false + `fonte` + fato_ids. O `ritmo` (tokens por segundo) é escolha de animação.
import { params, guardar, ler, montarQuadro, escrever, caber, tamanho, exigir, cartao, entrarBloco, contador, num, clamp, lerp, encaixou } from './_ia.js';

const EXEMPLO = [
  { de: 'usuario', texto: 'O que é uma janela de contexto?' },
  { de: 'modelo', texto: 'É todo o texto que o modelo consegue considerar de uma vez: a sua pergunta, a conversa anterior e a própria resposta.' },
];

export const meta = {
  nome: 'chat',
  descricao: 'Chat: bolhas de pergunta e resposta; a resposta do modelo chega token a token (streaming), com a bolha crescendo e um contador de tokens — até 6 mensagens, com rolagem.',
  dur_padrao: 12,
  formatos: ['horizontal', 'vertical', 'quadrado'],
  alfa_padrao: false,
  grao: true,
  params: params({
    mensagens: { tipo: 'lista', min: 1, max: 6, padrao: EXEMPLO, descricao: 'as mensagens, na ordem: quem fala e o texto; em mensagens do modelo, `tokens` (opcional) é a divisão real em tokens',
      itens: { tipo: 'objeto', campos: { de: { tipo: 'opcao', opcoes: ['usuario', 'modelo'], obrigatorio: true }, texto: { tipo: 'texto', obrigatorio: true },
        tokens: { tipo: 'lista', padrao: null, itens: { tipo: 'texto' }, descricao: 'os tokens da resposta, com o espaço dentro (" janela"); juntos têm de remontar o texto exato' } } } },
    nome_usuario: { tipo: 'texto', padrao: 'Você', descricao: 'rótulo das bolhas de quem pergunta' },
    nome_modelo: { tipo: 'texto', padrao: 'Modelo', descricao: 'rótulo das bolhas do modelo (nome de modelo real é afirmação: fato e fonte)' },
    ritmo: { tipo: 'numero', padrao: 14, min: 2, max: 60, descricao: 'tokens por segundo na tela (escolha de animação, não a velocidade de um modelo)' },
    contador: { tipo: 'booleano', padrao: true, descricao: 'mostra "n tokens" ao lado do nome enquanto a resposta chega' },
  }, { titulo: null }),
};

/** Recorte DE EXEMPLO de um texto em pedaços: palavra com o espaço na frente, pontuação à parte, palavra longa em duas. */
export function pedacosDeExemplo(texto) {
  const saida = [];
  for (const bruto of String(texto).match(/\s*\S+/g) || []) {
    const [, espaco, miolo, pontuacao] = /^(\s*)(.*?)([.,;:!?…]*)$/u.exec(bruto);
    if (miolo.length >= 9 && /^\p{L}+$/u.test(miolo)) { const c = Math.ceil(miolo.length * 0.55); saida.push(espaco + miolo.slice(0, c), miolo.slice(c)); }
    else if (miolo) saida.push(espaco + miolo);
    if (pontuacao) saida.push((miolo ? '' : espaco) + pontuacao);
  }
  return saida;
}

function tokensDe(m, i) {
  const texto = String(m.texto ?? '').trim();
  if (!Array.isArray(m.tokens) || !m.tokens.length) return pedacosDeExemplo(texto);
  exigir(m.tokens.join('') === texto, `mensagens[${i}].tokens não remonta o texto da mensagem: juntos, os tokens dão ${JSON.stringify(m.tokens.join('').slice(0, 60))} e o texto é ${JSON.stringify(texto.slice(0, 60))} — cada token leva o próprio espaço (" janela") e nada pode faltar`);
  return m.tokens.map(String);
}

export function roteiro(p, mov) {
  const d = mov.duracoes, msgs = p.mensagens || EXEMPLO, ritmo = p.ritmo || 14;
  let nq = 0, nr = 0;
  return msgs.map((m, i) => {
    exigir(String(m.texto ?? '').trim(), `mensagens[${i}]: o texto está vazio`);
    if (m.de === 'modelo') return { nome: 'resposta' + (++nr), tipo: 'texto', anim: d.media + tokensDe(m, i).length / ritmo + d.micro + d.curta * 2 };
    return { nome: 'pergunta' + (++nq), tipo: i ? 'texto' : 'entrada', anim: d.media * 2 };
  });
}

const ESTADOS = new WeakMap();

export function build(palco, p, ctx) {
  const msgs = p.mensagens, cor = p.cor;
  const rot = roteiro(p, ctx.DA.movimento);
  const Q = montarQuadro(palco, p, ctx, { roteiro: rot });
  const C = Q.conteudo, P = Q.P, d = ctx.DA.movimento.duracoes;
  const coluna = Q.horizontal ? Math.min(C.w, ctx.col(Math.ceil(ctx.DA.layout.grade.colunas * 0.72))) : C.w;
  const xCol = Q.horizontal ? (C.w - coluna) / 2 : 0;
  const janela = ctx.el('div', 'chat-janela');
  Object.assign(janela.style, { position: 'absolute', left: Math.round(C.x) + 'px', top: Math.round(C.y) + 'px', width: Math.round(C.w) + 'px', height: Math.round(C.h) + 'px' });
  const rolo = ctx.el('div', 'chat-rolo');
  Object.assign(rolo.style, { position: 'absolute', left: '0', top: '0', width: Math.round(C.w) + 'px' });
  janela.appendChild(rolo);
  Q.raiz.appendChild(janela);
  const esp = Math.max(3, ctx.traco * 1.6);
  const toks = msgs.map((m, i) => (m.de === 'modelo' ? tokensDe(m, i) : null));

  const U = caber((s) => {
    const tam = tamanho(ctx, 'h3', s * (Q.horizontal ? 1 : 0.92)), pad = tam * 0.62;
    const wMax = coluna * (Q.horizontal ? 0.8 : 0.9);
    const bolhas = msgs.map((m, i) => {
      const modelo = m.de === 'modelo';
      const nome = escrever(ctx, rolo, 'dados', String(modelo ? p.nome_modelo : p.nome_usuario), { tam: ctx.tam('nota'), cor: 'texto_suave', classe: 'chat-nome' });
      const html = modelo ? toks[i].map((tk) => `<span class="chat-tok">${ctx.esc(tk)}</span>`).join('') : null;
      const wTxt = wMax - 2 * pad - (modelo ? esp : 0);
      const txt = escrever(ctx, rolo, 'corpo', modelo ? '' : String(m.texto).trim(), { tam, maxW: wTxt, html, classe: 'chat-texto' });
      const viva = modelo ? escrever(ctx, rolo, 'corpo', '', { tam: txt.tam, cor, maxW: wTxt, html, classe: 'chat-viva' }) : null;
      return { modelo, nome, txt, viva, w: Math.ceil(txt.w + 2 * pad + (modelo ? esp : 0)), h: Math.ceil(txt.h + 2 * pad) };
    });
    const vNome = ctx.tam('nota') * 0.35, vMsg = tam * 0.8;
    const maior = Math.max(...bolhas.map((b) => b.nome.h + vNome + b.h));
    const total = bolhas.reduce((a, b) => a + b.nome.h + vNome + b.h, 0) + (bolhas.length - 1) * vMsg;
    // ampliar (s > 1) só se a conversa inteira couber sem rolar; no tamanho normal basta a maior bolha caber (o resto rola)
    return { cabe: s > 1 ? total <= C.h * 0.88 : maior <= C.h * 0.82, tam, pad, bolhas, vNome, vMsg };
  }, () => rolo.replaceChildren(), { inicio: Q.horizontal ? 1.35 : 1.1, min: 0.45 });
  encaixou(U, C, 'chat', 'há uma mensagem longa demais para uma bolha: divida-a em duas ou encurte');

  // posições (com as alturas FINAIS): quem pergunta à direita da coluna, o modelo à esquerda
  let y = 0, nq = 0, nr = 0;
  const bolhas = U.bolhas.map((b, i) => {
    const passo = b.modelo ? 'resposta' + (++nr) : 'pergunta' + (++nq);
    const x = b.modelo ? xCol : xCol + coluna - b.w;
    b.nome.em(b.modelo ? x : x + b.w - b.nome.w, y);
    const yB = y + b.nome.h + U.vNome;
    const c = cartao(ctx, { w: b.w, h: b.h, cor });
    rolo.appendChild(c.el);
    c.em(x, yB);
    const xTxt = U.pad + (b.modelo ? esp : 0);
    c.miolo.appendChild(b.txt.el);
    b.txt.em(xTxt, U.pad);
    const item = { ...b, passo, c, y, yB, k: P.indice(passo) };
    if (b.modelo) {
      const barra = ctx.el('div', 'chat-barra');                  // filete: esta bolha é do modelo
      Object.assign(barra.style, { position: 'absolute', left: '0', top: '0', width: esp.toFixed(1) + 'px', height: '100%', background: ctx.cor(cor) });
      c.miolo.append(barra, b.viva.el);
      c.miolo.style.overflow = 'hidden';                           // enquanto a bolha cresce, a linha nova não vaza para fora dela
      b.viva.em(xTxt, U.pad);
      const base = [...b.txt.el.querySelectorAll('.chat-tok')], vivos = [...b.viva.el.querySelectorAll('.chat-tok')];
      const fundos = base.map((sp) => sp.offsetTop + sp.offsetHeight);
      const hLinha = fundos.length ? Math.min(...fundos) : b.txt.h;
      // para cada token: a base da linha em que ele está e o primeiro token dessa linha
      let primeiro = 0;
      const linhaDe = fundos.map((f, j) => { if (j && f > fundos[j - 1] + 1) primeiro = j; return { fundo: f, primeiro, anterior: primeiro ? fundos[primeiro - 1] : hLinha }; });
      Object.assign(item, { base, vivos, linhaDe, hLinha, n: base.length });
      if (p.contador) {
        const conta = contador(ctx, { tam: ctx.tam('nota'), cor: 'texto_suave', formato: (v) => `${num(v, 0)} ${v === 1 ? 'token' : 'tokens'}`, modelo: `${base.length} tokens` });
        rolo.appendChild(conta.el);
        conta.medir();
        ctx.place(conta.el, { x: Math.round(x + b.nome.w + ctx.tam('nota') * 0.9), y: Math.round(y) });
        item.conta = conta;
      }
      P.marcar(passo, d.media + base.length / p.ritmo, 'fim_da_resposta', 'texto');
    } else item.letras = String(msgs[i].texto).trim().length;
    y = yB + b.h + (i < msgs.length - 1 ? U.vMsg : 0);
    return item;
  });
  const total = y;
  const rola = total > C.h;
  const y0 = rola ? 0 : Math.round((C.h - total) / 2);
  if (rola) janela.style.overflow = 'hidden';
  guardar(ESTADOS, ctx, { ctx, Q, P, p, U, bolhas, rolo, total, rola, y0, hC: C.h });
  return Q.layout({ mensagens: msgs.length, tokens: bolhas.filter((b) => b.modelo).map((b) => b.n), recorte: msgs.some((m) => m.de === 'modelo' && !(m.tokens && m.tokens.length)) ? 'de_exemplo' : 'informado',
    rola, escala: +U.escala.toFixed(3), tamanho_texto: +U.tam.toFixed(1),
    bloco: { x: Math.round(C.x + xCol), y: Math.round(C.y + y0), w: Math.round(coluna), h: Math.round(Math.min(total, C.h)) } });
}

export function seek(t, ctxArg) {
  const { ctx, Q, P, p, U, bolhas, rolo, rola, y0, hC } = ler(ESTADOS, ctxArg);
  const d = ctx.DA.movimento.duracoes;
  let fundo = 0;
  for (const b of bolhas) {
    const pe = P.prog(t, b.passo, 0, d.media);
    entrarBloco(ctx, b.c.el, pe);
    ctx.entrada(b.nome.el, pe, 'fade');
    let h = b.h;
    if (!b.modelo) ctx.entrada(b.txt.el, P.prog(t, b.passo, d.media * 0.4, d.media * 1.6), undefined, { n: b.letras });
    else {
      const e = P.e[b.k], t0 = P.t[b.k] + d.media * e, passo = e / p.ritmo;       // o token j nasce em t0 + j·passo
      const vistos = Math.max(0, Math.min(b.n, Math.floor((t - t0) / passo + 1 + 1e-6)));
      for (let j = 0; j < b.n; j++) {
        const idade = t - (t0 + j * passo);
        const a = idade < 0 ? 0 : clamp(idade / (d.micro * e));
        b.base[j].style.opacity = a.toFixed(3);
        b.vivos[j].style.opacity = (a * (1 - clamp((idade - d.micro * e) / (d.curta * 2 * e)))).toFixed(3);
      }
      // a bolha cresce linha a linha: da base da linha anterior para a da linha do último token visível
      const pad2 = 2 * U.pad;
      if (vistos <= 0) h = pad2 + b.hLinha;
      else {
        const ln = b.linhaDe[vistos - 1];
        h = pad2 + lerp(ln.anterior, ln.fundo, ln.primeiro === 0 ? 1 : clamp((t - (t0 + ln.primeiro * passo)) / (d.curta * e)));
      }
      b.c.altura(h);
      if (b.conta) { b.conta.definir(vistos); b.conta.el.style.opacity = (vistos > 0 ? clamp(pe) : 0).toFixed(3); }
    }
    b.hAgora = h; b.pe = clamp(pe);
    if (P.passou(t, b.passo)) fundo = lerp(fundo, b.yB + h, clamp(P.prog(t, b.passo, 0, d.media, 'suave')));
  }
  const desloca = rola ? Math.max(0, fundo + U.pad * 0.5 - hC) : -y0;
  for (const b of bolhas) {                                       // rolando: quem já passou da borda de cima some antes de ser cortado
    const total = b.yB - b.y + b.hAgora, passouDaBorda = rola ? desloca - b.y : 0;
    const vis = passouDaBorda <= 0 ? 1 : clamp(1 - (passouDaBorda / total) * 1.8);
    b.c.corpo.style.opacity = vis.toFixed(3);
    b.nome.el.style.opacity = (b.pe * vis).toFixed(3);
    if (b.conta && vis < 1) b.conta.el.style.opacity = (parseFloat(b.conta.el.style.opacity) * vis).toFixed(3);
  }
  rolo.style.transform = `translateY(${(-desloca).toFixed(2)}px)`;
  Q.seek(t);
}

export function key(t, ctx) { return ler(ESTADOS, ctx).P.chave(t); }

export function ancoras(ctx) { return ler(ESTADOS, ctx).P.ancoras(); }
