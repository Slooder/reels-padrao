// agente.js — o laço de um agente: o modelo lê a tarefa, PEDE uma ferramenta, o aplicativo a executa, o resultado
// volta para o contexto, o modelo lê tudo de novo e decide o passo seguinte — até responder.
// Passos: tarefa → pedido → execucao → resultado → volta2 → volta3 → … → resposta. A primeira volta é mostrada em
// três passos (para explicar); as seguintes cabem em um passo cada. Os nomes das ferramentas, os pedidos e os
// resultados vêm de `voltas`.
// O que a cena não deixa confundir: o modelo só ESCREVE o pedido (nome da ferramenta + argumentos); quem executa é o
// aplicativo em volta dele — está escrito junto à caixa das ferramentas e é um passo à parte. E o "contexto" cresce a
// cada volta: é tudo o que o modelo relê antes de decidir (se a lista não couber, ela rola: o que saiu de vista continua lá).
// O exemplo padrão é inventado (selo "ilustrativo"): ferramentas, resultados e resposta não vieram de sistema nenhum.
import { params, guardar, ler, montarQuadro, escrever, etiqueta, caber, tamanho, exigir, cartao, entrarBloco, contador, rotulo, textoDuplo, camadaSvg, setaCurva, reta, clamp, lerp, respiro } from './_ia.js';

const EXEMPLO = {
  tarefa: 'Preciso levar guarda-chuva amanhã?',
  voltas: [
    { ferramenta: 'buscar_previsao', entrada: 'cidade: "Recife", dia: "amanhã"', resultado: '80% de chance de chuva à tarde' },
    { ferramenta: 'ler_agenda', entrada: 'dia: "amanhã"', resultado: '18h — futebol na praia' },
  ],
  resposta: 'Sim. Vai chover à tarde, e você tem futebol às 18h.',
};

export const meta = {
  nome: 'agente',
  descricao: 'Agente: o laço modelo → pedido de ferramenta → execução pelo aplicativo → resultado → modelo, com o contexto crescendo a cada volta, até a resposta final. Ferramentas, pedidos e resultados vêm dos parâmetros.',
  dur_padrao: 20,
  formatos: ['horizontal', 'vertical', 'quadrado'],
  alfa_padrao: false,
  grao: true,
  params: params({
    tarefa: { tipo: 'texto', padrao: EXEMPLO.tarefa, descricao: 'o que o usuário pediu' },
    voltas: { tipo: 'lista', min: 1, max: 4, padrao: EXEMPLO.voltas, descricao: 'cada volta do laço: a ferramenta pedida, os argumentos e o que ela devolveu',
      itens: { tipo: 'objeto', campos: { ferramenta: { tipo: 'texto', obrigatorio: true, descricao: 'nome da ferramenta, como o modelo a chama' }, entrada: { tipo: 'texto', padrao: null, descricao: 'os argumentos do pedido' },
        resultado: { tipo: 'texto', obrigatorio: true, descricao: 'o que a ferramenta devolveu (curto)' } } } },
    resposta: { tipo: 'texto', padrao: EXEMPLO.resposta, descricao: 'a resposta final do modelo' },
    nome_modelo: { tipo: 'texto', padrao: 'modelo', descricao: 'rótulo da caixa do modelo' },
    nome_ferramentas: { tipo: 'texto', padrao: 'ferramentas', descricao: 'rótulo da caixa das ferramentas' },
    quem_executa: { tipo: 'texto', padrao: 'quem executa é o aplicativo', descricao: 'nota junto à caixa das ferramentas ("" esconde)' },
    nome_contexto: { tipo: 'texto', padrao: 'contexto do modelo', descricao: 'cabeçalho da lista do que o modelo relê a cada volta' },
  }, { titulo: 'Agente' }),
};

const LEGENDA = {
  tarefa: 'O modelo recebe uma *tarefa*', pedido: 'Ele não age sozinho: *pede* uma ferramenta', execucao: 'Quem *executa* o pedido é o aplicativo',
  resultado: 'O *resultado* volta e entra no contexto', volta: 'O modelo relê tudo e *decide o próximo passo*', resposta: 'Com o que precisa em mãos, *responde*',
};

function conferir(p) {
  const voltas = p.voltas || EXEMPLO.voltas;
  voltas.forEach((v, i) => exigir(String(v.ferramenta || '').trim() && String(v.resultado || '').trim(), `voltas[${i}]: faltou a ferramenta ou o resultado — cada volta do laço tem o pedido E o que voltou`));
  return { voltas, tarefa: String(p.tarefa ?? EXEMPLO.tarefa).trim(), resposta: String(p.resposta ?? EXEMPLO.resposta).trim() };
}

export function roteiro(p, mov) {
  const d = mov.duracoes, D = conferir(p);
  const r = [
    { nome: 'tarefa', tipo: 'entrada', anim: d.media * 2 + d.curta },
    { nome: 'pedido', tipo: 'enfase', anim: d.media * 3 },
    { nome: 'execucao', tipo: 'enfase', anim: d.media * 2 },
    { nome: 'resultado', tipo: 'texto', anim: d.media * 3 },
  ];
  for (let k = 1; k < D.voltas.length; k++) r.push({ nome: 'volta' + (k + 1), tipo: 'enfase', anim: d.media * 6.5 });
  r.push({ nome: 'resposta', tipo: 'texto', anim: d.media * 2 + d.longa });
  return r;
}

const ESTADOS = new WeakMap();

export function build(palco, p, ctx) {
  const D = conferir(p), cor = p.cor, V = D.voltas.length;
  const rot = roteiro(p, ctx.DA.movimento);
  const legendas = rot.map((r) => (r.nome.startsWith('volta') ? LEGENDA.volta : LEGENDA[r.nome]));
  const Q = montarQuadro(palco, p, ctx, { roteiro: rot, legendas });
  const C = Q.conteudo, P = Q.P, H = Q.horizontal;
  const svg = camadaSvg(ctx, Q.raiz);
  const camada = ctx.el('div', 'agente-camada');
  Object.assign(camada.style, { position: 'absolute', left: '0', top: '0' });
  Q.raiz.appendChild(camada);
  // o contexto, linha a linha: tarefa, (pedido, resultado) de cada volta, resposta
  const linhas = [{ tipo: 'tarefa', marca: 'tarefa', txt: D.tarefa, papel: 'corpo', passo: 'tarefa' }];
  D.voltas.forEach((v, i) => {
    const passo = i === 0 ? null : 'volta' + (i + 1);
    linhas.push({ tipo: 'pedido', marca: 'pedido', txt: `${v.ferramenta}(${v.entrada ? String(v.entrada) : ''})`, papel: 'dados', passo: passo || 'pedido', volta: i });
    linhas.push({ tipo: 'resultado', marca: 'resultado', txt: String(v.resultado), papel: 'dados', passo: passo || 'resultado', volta: i });
  });
  linhas.push({ tipo: 'resposta', marca: 'resposta', txt: D.resposta, papel: 'corpo', passo: 'resposta' });

  const U = caber((s) => {
    const tam = tamanho(ctx, 'corpo', s * (H ? 1.12 : 1)), tamNo = tamanho(ctx, 'h3', s * (H ? 1 : 0.86)), pad = tam * 0.6;
    const vaoCol = H ? C.w * 0.05 : 0;
    const wL = H ? C.w * 0.43 : C.w, wR = H ? C.w - wL - vaoCol : C.w;
    const cab = rotulo(ctx, String(p.nome_contexto), { tam: ctx.tam('nota') });
    camada.appendChild(cab);
    const mCab = ctx.medir(cab);
    const conta = contador(ctx, { tam: ctx.tam('nota'), cor: 'texto_suave', formato: (v) => `volta ${Math.round(v)} de ${V}`, modelo: `volta ${V} de ${V}` });
    camada.appendChild(conta.el);
    const mConta = conta.medir();
    // marcas (tarefa, pedido…) numa coluna de largura fixa; o texto de cada linha ao lado
    const marcas = linhas.map((ln) => { const m = textoDuplo(ctx, 'dados', ln.marca, { tam: ctx.tam('nota'), corA: 'texto_suave', corB: cor, classe: 'agente-marca' }); camada.appendChild(m.el); m.medir(); return m; });
    const wMarca = Math.max(...marcas.map((m) => m.w)) + pad * 1.25;      // 0,8 deixava a marca mais longa ("resultado") colada no trilho (folha de contato de 2026-10-12)
    const textos = linhas.map((ln) => escrever(ctx, camada, ln.papel, ln.txt, { tam: ln.papel === 'dados' ? tam * 0.94 : tam, maxW: wL - wMarca - pad * 0.4, maxLinhas: 4, classe: 'agente-linha' }));
    const vao = tam * 0.42;
    const hCab = mCab.h + vao * 1.2;
    const hLinhas = textos.reduce((a, x) => a + x.h, 0) + (linhas.length - 1) * vao;
    // o laço: duas caixas e dois arcos
    const k = tamNo * (H ? 2.3 : 1.7);
    const nomeM = escrever(ctx, camada, 'titulo', String(p.nome_modelo), { tam: tamNo, maxW: wR * 0.34, maxLinhas: 2, alinhar: 'centro', classe: 'agente-no' });
    const nomeF = escrever(ctx, camada, 'titulo', String(p.nome_ferramentas), { tam: tamNo, maxW: wR * 0.34, maxLinhas: 2, alinhar: 'centro', classe: 'agente-no' });
    // nome de ferramenta é identificador (buscar_previsao): quebra depois de _ . - / : e, se ainda assim não couber, em qualquer letra — nunca sai da caixa
    const nomes = D.voltas.map((v) => escrever(ctx, camada, 'dados', '', { tam: ctx.tam('nota'), cor, maxW: wR * 0.34, maxLinhas: 2, alinhar: 'centro', classe: 'agente-ferramenta', quebraLivre: true,
      html: ctx.esc(String(v.ferramenta)).replace(/([_.\-/:])/g, '$1<wbr>') }));
    const hNomes = Math.max(...nomes.map((n) => n.h));
    const wNo = wR * 0.34 + 2 * pad, hNo = Math.max(nomeM.h, nomeF.h) + hNomes + tamNo * 0.2 + 2 * pad;
    const rPed = etiqueta(ctx, camada, 'pedido', { tam: ctx.tam('nota') }), rRes = etiqueta(ctx, camada, 'resultado', { tam: ctx.tam('nota') });
    // a nota "quem executa": sob a caixa das ferramentas (horizontal) ou numa linha inteira abaixo do arco de volta (vertical)
    const nota = String(p.quem_executa || '').trim() ? escrever(ctx, camada, 'dados', String(p.quem_executa).trim(), { tam: ctx.tam('nota'), cor: 'texto_suave', maxW: H ? wNo * 0.66 : wR, maxLinhas: 3, alinhar: H ? 'esquerda' : 'direita', classe: 'agente-nota' }) : null;
    const contaNoMeio = H && wR - 2 * wNo >= mConta.w + tam * 0.8;           // "volta 1 de 2" entre as caixas; sem lugar, vai para a linha do cabeçalho do contexto
    const hArco = k * 0.75 + rPed.h * 0.5;
    const hLaco = hArco + hNo + (H ? Math.max(hArco, nota ? tam * 0.4 + nota.h : 0) : hArco + (nota ? tam * 0.3 + nota.h : 0));
    // o contexto inteiro cabe? se não couber nem na menor letra, a lista rola (as linhas antigas sobem e saem de vista)
    const hJanela = H ? C.h * respiro(s) - hCab : C.h - hLaco - tam * 0.9 - hCab;
    const maior = Math.max(...textos.map((x) => x.h));
    const cabe = hLinhas <= hJanela && hLaco <= C.h * respiro(s) && textos.every((x) => x.linhas <= 3) && nomes.every((n) => n.linhas <= 2);
    return { cabe, tam, tamNo, pad, vaoCol, wL, wR, cab, mCab, hCab, marcas, wMarca, textos, vao, hLinhas, hJanela, maior, k, nomeM, nomeF, nomes, hNomes, wNo, hNo, rPed, rRes, nota, conta, mConta, contaNoMeio, hArco, hLaco };
  }, () => camada.replaceChildren(), { inicio: H ? 1.1 : 1, min: 0.6 });
  const rola = !U.cabe;
  exigir(U.cabe || (U.hJanela >= U.maior * 2.2 && U.hLaco <= C.h), `agente: o laço e o contexto não couberam na área útil deste formato (${Math.round(C.w)} × ${Math.round(C.h)} px) nem com a menor letra legível da DA — encurte a tarefa, os pedidos e os resultados, ou use menos voltas. Para ganhar altura: titulo: "" ou legendas: []`);
  const hVista = Math.min(U.hLinhas, U.hJanela);
  const hLista = U.hCab + hVista;
  const alt = H ? Math.max(hLista, U.hLaco) : U.hLaco + U.tam * 0.9 + hLista;

  const y0 = Math.round(C.y + Math.max(0, (C.h - alt) / 2));
  // lista do contexto (esquerda no horizontal; embaixo no vertical), dentro de uma janela que rola se for preciso
  const xL = C.x, yL = H ? y0 + (alt - hLista) / 2 : y0 + U.hLaco + U.tam * 0.9;
  ctx.place(U.cab, { x: Math.round(xL), y: Math.round(yL) });
  const janela = ctx.el('div', 'agente-janela');
  Object.assign(janela.style, { position: 'absolute', left: Math.round(xL) + 'px', top: Math.round(yL + U.hCab) + 'px', width: Math.round(U.wL) + 'px', height: Math.round(hVista) + 'px' });
  if (rola) janela.style.overflow = 'hidden';
  const rolo = ctx.el('div', 'agente-rolo');
  Object.assign(rolo.style, { position: 'absolute', left: '0', top: '0', width: '100%' });
  janela.appendChild(rolo);
  camada.appendChild(janela);
  let y = 0;
  const itens = linhas.map((ln, i) => {
    const tx = U.textos[i], m = U.marcas[i];
    rolo.append(m.el, tx.el);
    Object.assign(m.el.style, { left: '0px', top: Math.round(y + (tx.h / tx.linhas - m.h) / 2) + 'px' });
    tx.em(U.wMarca, y);
    const item = { ...ln, tx, m, y, letras: ln.txt.length };
    y += tx.h + U.vao;
    return item;
  });
  const trilho = ctx.el('div', 'agente-trilho');                 // fio à esquerda do texto: a lista é uma coisa só, que cresce
  Object.assign(trilho.style, { position: 'absolute', left: Math.round(U.wMarca - U.pad * 0.45) + 'px', top: '0', width: Math.max(1, ctx.traco * 0.75).toFixed(1) + 'px',
    height: Math.round(U.hLinhas) + 'px', background: ctx.alfa('texto_suave', 0.6), transformOrigin: 'center top' });
  rolo.appendChild(trilho);
  // o laço
  const xR = H ? C.x + U.wL + U.vaoCol : C.x, yR = H ? y0 + (alt - U.hLaco) / 2 : y0;
  const yNo = yR + U.hArco;
  const cM = cartao(ctx, { w: U.wNo, h: U.hNo, cor }), cF = cartao(ctx, { w: U.wNo, h: U.hNo, cor });
  camada.append(cM.el, cF.el);
  cM.em(xR, yNo);
  cF.em(xR + U.wR - U.wNo, yNo);
  const hTxt = (nome) => nome.h + U.tamNo * 0.2 + U.hNomes;
  cM.miolo.appendChild(U.nomeM.el);
  U.nomeM.em(U.pad, (U.hNo - U.nomeM.h) / 2);
  cF.miolo.appendChild(U.nomeF.el);
  U.nomeF.em(U.pad, (U.hNo - hTxt(U.nomeF)) / 2);
  U.nomes.forEach((n) => { cF.miolo.appendChild(n.el); n.em(U.pad, (U.hNo - hTxt(U.nomeF)) / 2 + U.nomeF.h + U.tamNo * 0.2); });
  const esp = Math.max(1.5, ctx.traco), f = 0.22, k = U.k;        // os arcos saem do lado de dentro das caixas: sobra lugar para a nota
  const ax = cM.x + U.wNo * (0.5 + f), bx = cF.x + U.wNo * (0.5 - f);
  const curvaIda = [ax, yNo, ax, yNo - k, bx, yNo - k, bx, yNo], curvaVolta = [bx, yNo + U.hNo, bx, yNo + U.hNo + k, ax, yNo + U.hNo + k, ax, yNo + U.hNo];
  const arcos = [curvaIda, curvaVolta].map((c) => {
    const base = setaCurva(ctx, svg, c, { cor: 'texto_suave', esp });
    const g = ctx.svg('g');
    svg.appendChild(g);
    const viva = setaCurva(ctx, g, c, { cor, esp: esp * 1.3 });
    return { base, viva, g };
  });
  const xMeio = (ax + bx) / 2;
  U.rPed.em(xMeio - U.rPed.w / 2, yNo - k * 0.75 - U.rPed.h / 2);
  U.rRes.em(xMeio - U.rRes.w / 2, yNo + U.hNo + k * 0.75 - U.rRes.h / 2);
  if (U.contaNoMeio) ctx.place(U.conta.el, { x: Math.round(xMeio - U.mConta.w / 2), y: Math.round(yNo + (U.hNo - U.mConta.h) / 2) });
  else ctx.place(U.conta.el, { x: Math.round(xL + U.wL - U.mConta.w), y: Math.round(yL) });
  if (U.nota) {
    if (H) U.nota.em(bx + U.tam * 0.7, yNo + U.hNo + U.tam * 0.4);
    else U.nota.em(C.x1 - U.nota.w, yNo + U.hNo + U.hArco + U.tam * 0.3);
  }
  const bolinha = ctx.el('div', 'agente-pulso');
  const rb = Math.max(5, U.tamNo * 0.2);
  Object.assign(bolinha.style, { position: 'absolute', left: (-rb).toFixed(1) + 'px', top: (-rb).toFixed(1) + 'px', width: (2 * rb).toFixed(1) + 'px', height: (2 * rb).toFixed(1) + 'px', borderRadius: '50%', background: ctx.cor(cor) });
  camada.appendChild(bolinha);
  // tarefa entra / resposta sai: setas curtas entre a lista e o modelo (só no horizontal, onde há o vão entre as colunas)
  let sEntra = null, sSai = null;
  if (H) {
    const x1 = C.x + U.wL + U.vaoCol * 0.12, x2 = cM.x - U.vaoCol * 0.12;
    sEntra = setaCurva(ctx, svg, reta(x1, yNo + U.hNo * 0.32, x2, yNo + U.hNo * 0.32), { cor: 'texto_suave', esp });
    sSai = setaCurva(ctx, svg, reta(x2, yNo + U.hNo * 0.68, x1, yNo + U.hNo * 0.68), { cor, esp });
  }
  // rolagem: quando a linha i chega, a lista sobe até o topo da primeira linha que ainda cabe inteira acima dela
  const paradas = itens.map((it) => {
    const sobra = it.y + it.tx.h - hVista;
    if (!rola || sobra <= 0) return 0;
    const primeira = itens.find((x) => x.y >= sobra - 0.5);
    return primeira ? primeira.y : sobra;
  });
  guardar(ESTADOS, ctx, { ctx, Q, P, D, U, itens, trilho, rolo, rola, hVista, paradas, cM, cF, arcos, bolinha, sEntra, sSai, V });
  return Q.layout({ voltas: V, ferramentas: D.voltas.map((v) => v.ferramenta), linhas_de_contexto: linhas.length, contexto_rola: rola, escala: +U.escala.toFixed(3), tamanho_linha: +U.tam.toFixed(1),
    laco: { x: Math.round(xR), y: Math.round(yR), w: Math.round(U.wR), h: Math.round(U.hLaco) }, bloco: { x: Math.round(C.x), y: y0, w: Math.round(C.w), h: Math.round(alt) } });
}

export function seek(t, ctxArg) {
  const { ctx, Q, P, U, itens, trilho, rolo, rola, hVista, paradas, cM, cF, arcos, bolinha, sEntra, sSai, V } = ler(ESTADOS, ctxArg);
  const d = ctx.DA.movimento.duracoes;
  const nome = (v) => (v === 0 ? null : 'volta' + (v + 1));
  // janelas de cada volta: quando o pedido viaja, quando o aplicativo executa, quando o resultado volta
  const volta = (v) => (v === 0
    ? { ida: P.prog(t, 'pedido', d.media * 0.5, d.media * 1.5, 'suave'), idaLin: P.lin(t, 'pedido', d.media * 0.5, d.media * 1.5), exec: P.prog(t, 'execucao', 0, d.media, 'enfase'),
        vinda: P.prog(t, 'resultado', 0, d.media * 1.5, 'suave'), vindaLin: P.lin(t, 'resultado', 0, d.media * 1.5), linhaPedido: P.prog(t, 'pedido', d.media * 1.5, d.media), linhaResultado: P.prog(t, 'resultado', d.media * 1.5, d.media),
        comecou: P.passou(t, 'pedido'), leu: P.prog(t, 'resultado', d.media * 1.5, d.media, 'enfase') }
    : { ida: P.prog(t, nome(v), d.media * 0.5, d.media * 1.5, 'suave'), idaLin: P.lin(t, nome(v), d.media * 0.5, d.media * 1.5), exec: P.prog(t, nome(v), d.media * 2, d.media, 'enfase'),
        vinda: P.prog(t, nome(v), d.media * 3.5, d.media * 1.5, 'suave'), vindaLin: P.lin(t, nome(v), d.media * 3.5, d.media * 1.5), linhaPedido: P.prog(t, nome(v), d.media * 1.5, d.media), linhaResultado: P.prog(t, nome(v), d.media * 5, d.media),
        comecou: P.passou(t, nome(v)), leu: P.prog(t, nome(v), d.media * 5, d.media, 'enfase') });
  const W = Array.from({ length: V }, (_, v) => volta(v));
  const pResp = P.prog(t, 'resposta', 0, d.media, 'enfase');
  // contexto: cada linha entra na sua hora; a marca da linha mais recente fica na cor do destaque
  ctx.entrada(U.cab, P.prog(t, 'tarefa', 0, d.media), 'fade');
  const chegada = itens.map((it) => (it.tipo === 'tarefa' ? P.prog(t, 'tarefa', d.media * 0.5, d.media) : it.tipo === 'resposta' ? P.prog(t, 'resposta', d.media, d.longa)
    : it.tipo === 'pedido' ? W[it.volta].linhaPedido : W[it.volta].linhaResultado));
  let fundo = 0, rolagem = 0;
  itens.forEach((it, i) => {
    if (chegada[i] > 0) rolagem = lerp(rolagem, paradas[i], clamp(chegada[i]));
    ctx.entrada(it.tx.el, chegada[i], undefined, { n: it.letras });
    it.m.el.style.opacity = clamp(chegada[i] * 2).toFixed(3);
    const proxima = i < itens.length - 1 ? clamp(chegada[i + 1] * 2) : 0;
    it.m.misturar(clamp(chegada[i] * 2) * (1 - proxima));
    if (chegada[i] > 0) fundo = lerp(fundo, it.y + it.tx.h, clamp(chegada[i]));
  });
  trilho.style.transform = `scaleY(${(fundo / Math.max(1, U.hLinhas)).toFixed(4)})`;
  trilho.style.opacity = fundo > 0 ? '1' : '0';
  rolo.style.transform = rola ? `translateY(${(-rolagem).toFixed(2)}px)` : 'none';                          // o que não cabe mais rola para cima
  // o laço: caixas, arcos, o pulso que viaja e a volta em que estamos
  entrarBloco(ctx, cM.el, P.prog(t, 'tarefa', 0, d.media));
  ctx.entrada(U.nomeM.el, P.prog(t, 'tarefa', d.media * 0.5, d.media), 'fade');
  if (sEntra) sEntra.tracar(P.prog(t, 'tarefa', d.media, d.media, 'suave'));
  entrarBloco(ctx, cF.el, P.prog(t, 'pedido', 0, d.media));
  ctx.entrada(U.nomeF.el, P.prog(t, 'pedido', d.media * 0.5, d.media), 'fade');
  arcos[0].base.tracar(W[0].ida); arcos[1].base.tracar(W[0].vinda);
  ctx.entrada(U.rPed.el, P.prog(t, 'pedido', d.media * 1.5, d.media * 0.5), 'fade');
  ctx.entrada(U.rRes.el, P.prog(t, 'resultado', d.media, d.media * 0.5), 'fade');
  if (U.nota) ctx.entrada(U.nota.el, P.prog(t, 'execucao', 0, d.media), 'fade');
  let atual = -1, pos = null, idaViva = 0, vindaViva = 0, executando = 0, lendo = 0;
  W.forEach((w, v) => {
    if (w.comecou) atual = v;
    if (w.idaLin > 0 && w.idaLin < 1) pos = arcos[0].base.ponto(w.ida);
    if (w.vindaLin > 0 && w.vindaLin < 1) pos = arcos[1].base.ponto(w.vinda);
    const depois = v < V - 1 ? clamp(P.prog(t, nome(v + 1), 0, d.curta)) : clamp(pResp);
    idaViva = Math.max(idaViva, (w.idaLin > 0 ? 1 : 0) * (1 - clamp(w.exec)));
    vindaViva = Math.max(vindaViva, (w.vindaLin > 0 ? 1 : 0) * (1 - depois));
    executando = Math.max(executando, clamp(w.exec) * (1 - clamp(w.vinda)));
    lendo = Math.max(lendo, clamp(w.leu) * (1 - depois));
  });
  arcos[0].viva.tracar(1); arcos[1].viva.tracar(1);
  arcos[0].g.style.opacity = idaViva.toFixed(3);
  arcos[1].g.style.opacity = vindaViva.toFixed(3);
  U.nomes.forEach((n, v) => { n.el.style.opacity = (v === atual ? clamp(W[v].ida * 2) : 0).toFixed(3); });
  if (pos) { bolinha.style.opacity = '1'; bolinha.style.transform = `translate(${pos.x.toFixed(2)}px, ${pos.y.toFixed(2)}px)`; }
  else { bolinha.style.opacity = '0'; bolinha.style.transform = 'none'; }
  U.conta.definir(Math.max(1, atual + 1));
  U.conta.el.style.opacity = (atual >= 0 ? clamp(W[0].ida * 2) : 0).toFixed(3);
  cF.estado({ realce: executando });
  cM.estado({ realce: Math.max(lendo, pResp) });
  if (sSai) sSai.tracar(P.prog(t, 'resposta', d.media * 0.5, d.media, 'suave'));
  Q.seek(t);
}

export function key(t, ctx) { return ler(ESTADOS, ctx).P.chave(t); }

export function ancoras(ctx) { return ler(ESTADOS, ctx).P.ancoras(); }
