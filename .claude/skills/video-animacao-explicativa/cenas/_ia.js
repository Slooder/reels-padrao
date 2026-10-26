// _ia.js — ajudantes da biblioteca de cenas explicativas de IA (skill video-animacao-explicativa).
//
// O que mora aqui (e não nas cenas): o QUADRO comum (chapéu em tarja da DA, selo "ilustrativo", crédito de fonte do
// kit, frase do passo, saída), o PLANO DE PASSOS (ritmo didático: um passo por vez, `passos_t` para casar com a
// narração, âncoras para a skill de efeitos sonoros, chave de quadro parado) e as PEÇAS que se repetem (caixa de
// token, nó, linha, seta, arco, matriz de calor, eixo, rótulo, contador, grade responsiva; e, para as cenas de sistema e
// genéricas, cartão, bloco de texto ajustado, digitador, seta curva e o laço de encaixe `caber`), mais a matemática
// pequena que as cenas usam de verdade (softmax com temperatura, sorteio pela distribuição acumulada, formatação pt-BR).
//
// Regras que este arquivo obedece — e que toda cena nova da biblioteca herda ao usá-lo:
//   · módulo ES puro: nada de document/window no nível do módulo (o motor importa a cena no Node para ler `meta`);
//   · nenhuma cor nem fonte literal: só ctx.cor / ctx.alfa / papéis da DA;
//   · troca de cor NUNCA por interpolação de RGB (o meio do caminho sairia da paleta e o auditor reprova): duas
//     camadas sobrepostas, cada uma numa cor da DA, cruzadas por opacidade;
//   · tudo é função pura de t: quem decide o estado é seek(t), nunca o seek anterior;
//   · nenhum texto menor que a escala `nota` da DA (o mínimo legível no celular).
//
// Documentação de uso: ~/.claude/skills/video-animacao-explicativa/references/biblioteca.md

export const VERSAO = '1.2.0';

// ────────────────────────────────────────────────────────────── parâmetros ──
/** Parâmetros que TODA cena da biblioteca aceita (o storyboard.py e a didática contam com eles). */
export const PARAMS_COMUNS = {
  titulo: { tipo: 'texto', padrao: null, descricao: 'chapéu curto no topo, na tarja da DA; "" esconde' },
  legendas: { tipo: 'lista', padrao: null, itens: { tipo: 'texto' },
    descricao: 'frase curta de cada passo, na ordem (padrão: as da cena; [] esconde todas; *asteriscos* destacam um termo)' },
  passos_t: { tipo: 'lista', padrao: null, itens: { tipo: 'numero', min: 0 },
    descricao: 'instante, em segundos a partir do início da cena, em que cada passo dispara (para casar com a narração); os passos que faltarem se distribuem sozinhos' },
  cor: { tipo: 'cor', padrao: 'primaria', descricao: 'token da DA usado no destaque (um por tela)' },
  ilustrativo: { tipo: 'booleano', padrao: true,
    descricao: 'true = exemplo inventado para ilustrar (mostra o selo "ilustrativo"); false = dado real: exige `fonte` aqui e fato_ids no storyboard' },   // padrão por cena: ver params()
  fonte: { tipo: 'texto', padrao: null, descricao: 'crédito da fonte, SEM o prefixo (saída de fatos.py credito F### --sem-prefixo); o kit põe "Fonte: "' },
  plataforma: { tipo: 'plataforma', padrao: null, descricao: 'zona segura a respeitar (vertical: reels, tiktok, shorts, uniao; fora do vertical cai em padrao)' },
  reservar_legenda: { tipo: 'booleano', padrao: null,
    descricao: 'deixa livre a faixa da legenda queimada; padrão: conforme legenda.reservar_em da DA (vertical e quadrado)' },
};

export const SELO_TEXTO = 'null = a tela mostra o texto do próprio roteiro (sem selo e sem crédito obrigatório); true = há exemplo inventado na tela (mostra o selo "ilustrativo"); false = dado real: exige `fonte` aqui e fato_ids no storyboard';
export const SELO_DADO = 'null = o exemplo padrão sai com o selo "ilustrativo", e dados SEUS exigem a escolha; true = exemplo inventado (selo); false = dado real: exige `fonte` aqui e fato_ids no storyboard';

/**
 * meta.params de uma cena: os específicos primeiro, depois os comuns (com o chapéu padrão da cena).
 *   ilustrativo: 'texto' → padrão null: cena que mostra o texto do roteiro (lista, conceito, fluxo, versus) — sem selo;
 *                'dado'  → padrão null: cena de dado (numero, comparativo, linha_do_tempo) — o exemplo padrão leva selo
 *                          e dados do usuário exigem a escolha explícita (decidirIlustrativo);
 *                omitido → padrão true: toda cena cujo exemplo padrão é inventado.
 */
export function params(especificos, { titulo = null, ilustrativo = undefined } = {}) {
  const comuns = JSON.parse(JSON.stringify(PARAMS_COMUNS));
  comuns.titulo.padrao = titulo;
  if (ilustrativo === 'texto' || ilustrativo === 'dado') { comuns.ilustrativo.padrao = null; comuns.ilustrativo.descricao = ilustrativo === 'texto' ? SELO_TEXTO : SELO_DADO; }
  return { ...especificos, ...comuns };
}

/** Erro de dado com mensagem acionável (o storyboard.py mostra a primeira linha já em `validar`, antes do render). */
export function exigir(condicao, mensagem) { if (!condicao) throw new Error(mensagem); }

/**
 * Cena de DADO com ilustrativo padrão null: o exemplo padrão é inventado (selo); com dados do usuário a cena não
 * adivinha — sem a escolha explícita não mostra valor nenhum. Devolve o booleano a passar a montarQuadro.
 */
export function decidirIlustrativo(p, dadosProprios, oQue) {
  if (p.ilustrativo === true || p.ilustrativo === false) return p.ilustrativo;
  exigir(!dadosProprios, `${oQue}: diga se estes dados são reais ou inventados — "ilustrativo": false (+ "fonte" e fato_ids no storyboard) para dado verificado, ou "ilustrativo": true para exemplo inventado (a cena mostra o selo "ilustrativo"). Sem essa escolha a cena não mostra valor nenhum`);
  return true;
}

// ─────────────────────────────────────────────────────── estado por instância ──
// O motor passa o ctx em seek(t, ctx), key(t, ctx) e ancoras(ctx): o estado fica preso ao ctx e a mesma cena pode
// ser montada mais de uma vez na página (por uma cena composta). Sem ctx, vale a última montagem.
export function guardar(mapa, ctx, estado) { mapa.set(ctx, estado); mapa.ultimo = estado; return estado; }
export function ler(mapa, ctx) {
  const s = (ctx && mapa.get(ctx)) || mapa.ultimo;
  if (!s) throw new Error('a cena ainda não foi montada: build() vem antes de seek()');
  return s;
}

// ────────────────────────────────────────────────────────────── matemática ──
export const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
export const lerp = (a, b, p) => a + (b - a) * p;

/** Número em pt-BR: vírgula decimal, ponto de milhar, sinal de menos tipográfico. */
export function num(v, casas = 2, { sinal = false } = {}) {
  if (!Number.isFinite(v)) return '—';
  const neg = v < 0 && Math.abs(v) >= 0.5 * 10 ** -casas;
  const [int, dec] = Math.abs(v).toFixed(casas).split('.');
  const milhar = int.replace(/\B(?=(\d{3})+(?!\d))/g, '.');
  return (neg ? '−' : sinal ? '+' : '') + milhar + (dec ? ',' + dec : '');
}
export const pct = (v, casas = 0) => num(v * 100, casas) + '%';

export function soma(lista) { return lista.reduce((a, b) => a + b, 0); }

/** Confere que `lista` é uma distribuição (números ≥ 0 que somam 1 ± tolerância). Devolve a soma. */
export function conferirDistribuicao(lista, oQue, tolerancia = 0.02) {
  lista.forEach((v, i) => {
    if (typeof v !== 'number' || !Number.isFinite(v) || v < 0) throw new Error(`${oQue}: o item ${i} (${JSON.stringify(v)}) precisa ser um número maior ou igual a zero`);
  });
  const s = soma(lista);
  if (Math.abs(s - 1) > tolerancia) {
    throw new Error(`${oQue}: os valores somam ${num(s, 3)}, e uma distribuição de probabilidade soma 1. Corrija os números (ou divida cada um por ${num(s, 3)})`);
  }
  return s;
}

/**
 * Aplica temperatura T a uma distribuição p (que é a de T = 1): p_T ∝ p^(1/T). É o mesmo que softmax(logits / T),
 * porque p = softmax(logits). T → 0 concentra tudo no mais provável; T grande aproxima da distribuição uniforme.
 */
export function comTemperatura(probs, T) {
  const t = Math.max(1e-3, T);
  const maior = Math.max(...probs);
  const brutos = probs.map((p) => (p <= 0 ? 0 : Math.exp(Math.log(p / maior) / t)));   // dividido pelo maior: sem estouro numérico
  const s = soma(brutos) || 1;
  return brutos.map((b) => b / s);
}

/** Sorteio pela distribuição acumulada: devolve o índice em que u ∈ [0, 1) cai. */
export function sortear(probs, u) {
  let acum = 0;
  for (let i = 0; i < probs.length; i++) { acum += probs[i]; if (u < acum) return i; }
  return probs.length - 1;
}

export function indiceDoMaior(lista) { let k = 0; lista.forEach((v, i) => { if (v > lista[k]) k = i; }); return k; }

export const ATIVACOES = {
  relu: { nome: 'ReLU', f: (x) => Math.max(0, x) },
  sigmoide: { nome: 'sigmoide', f: (x) => 1 / (1 + Math.exp(-x)) },
  tanh: { nome: 'tanh', f: (x) => Math.tanh(x) },
  linear: { nome: 'linear', f: (x) => x },
};

/** "*termo* em destaque" → HTML seguro com o termo num span na cor do destaque. */
export function marcarTermos(ctx, texto, cor) {
  return String(texto).split('*').map((parte, i) => (i % 2 ? `<span style="color: ${ctx.cor(cor)}">${ctx.esc(parte)}</span>` : ctx.esc(parte))).join('');
}

// ─────────────────────────────────────────────────────────── plano de passos ──
export const LEITURA = 0.9;          // respiro recomendado depois de cada passo (s): o tempo de quem lê
export const LEITURA_MINIMA = 0.35;  // abaixo disso o passo seguinte atropela

/**
 * Duração mínima e recomendada (s) para um roteiro de passos [{nome, anim}] com as durações da DA.
 * É a mesma conta de planejar(); o storyboard.py a usa para avisar ANTES do render.
 */
export function duracoes(roteiro, movimento) {
  const d = movimento.duracoes;
  const anims = roteiro.map((r, i) => Math.max(r.anim, d.curta + d.micro, i === 0 ? d.media + d.curta : 0));
  const base = 0.12 + soma(anims) + d.media;
  return { minima: +(base + roteiro.length * LEITURA_MINIMA).toFixed(2), recomendada: +(base + roteiro.length * LEITURA).toFixed(2) };
}

/**
 * Plano de passos de uma cena: quando cada passo dispara e quanto dura a animação dele.
 *   roteiro  [{ nome, anim (s nominais da animação do passo), tipo: 'entrada'|'enfase'|'texto', leitura? }]
 *   passos_t lista opcional de instantes (s) — um por passo, em ordem; pode ter menos itens que passos
 * Devolve P com: t[k], fim[k], anim[k], e[k] (fator de compressão ≤ 1), inicioSaida, fimEntrada,
 *   P.prog(t, k, atraso, dur, curva)  progresso 0–1 (com a curva da DA) de um trecho do passo k; atraso e dur em
 *                                     segundos NOMINAIS (encolhem junto quando a cena é curta demais)
 *   P.lin(t, k, atraso, dur)          o mesmo, linear
 *   P.passou(t, k)  P.atual(t)  P.chave(t)  P.ancoras()  P.marcar(k, atraso, nome, tipo)
 */
export function planejar(ctx, roteiro, passos_t = null) {
  const D = ctx.duracao, n = roteiro.length;
  if (!n) throw new Error('planejar: o roteiro da cena não tem passos');
  const media = ctx.dur('media'), curta = ctx.dur('curta'), micro = ctx.dur('micro');
  const nomes = roteiro.map((r) => r.nome);
  const inicioSaida = ctx.fim_saida();
  const inicio = Math.min(0.12, D * 0.03);
  const nominal = roteiro.map((r, i) => Math.max(r.anim, curta + micro, i === 0 ? media + curta : 0));
  const precisa = nominal.map((a, i) => a + (roteiro[i].leitura ?? LEITURA));
  const t = new Array(n);
  let dados = 0;
  if (passos_t && passos_t.length) {
    if (passos_t.length > n) {
      throw new Error(`passos_t tem ${passos_t.length} instantes, mas esta cena tem ${n} passo(s) com estes parâmetros (${nomes.join(', ')}): tire os que sobram`);
    }
    passos_t.forEach((v, i) => {
      if (typeof v !== 'number' || !Number.isFinite(v) || v < 0) throw new Error(`passos_t[${i}] = ${JSON.stringify(v)}: use segundos (número ≥ 0) contados do início da cena`);
      if (i && v <= passos_t[i - 1]) throw new Error(`passos_t precisa estar em ordem crescente: o passo "${nomes[i]}" (${num(v, 2)} s) vem antes ou junto do passo "${nomes[i - 1]}" (${num(passos_t[i - 1], 2)} s)`);
      if (v >= inicioSaida - 0.05) throw new Error(`passos_t[${i}] = ${num(v, 2)} s cai na saída da cena, que começa em ${num(inicioSaida, 2)} s (duração ${num(D, 2)} s): aumente "dur" no storyboard ou adiante o passo "${nomes[i]}"`);
      t[i] = v;
    });
    dados = passos_t.length;
  }
  if (dados < n) {                                           // distribui os passos que faltam no tempo que sobra
    const de = dados ? dados - 1 : 0;
    const origem = dados ? t[dados - 1] : inicio;
    const total = soma(precisa.slice(de));
    const s = Math.max(0, inicioSaida - origem) / total;
    let acum = 0;
    for (let k = de; k < n; k++) { if (k >= dados) t[k] = origem + s * acum; acum += precisa[k]; }
  }
  const fim = t.map((_, k) => (k < n - 1 ? t[k + 1] : inicioSaida));
  const anim = nominal.map((a, k) => Math.max(1e-3, Math.min(a, (fim[k] - t[k]) * 0.94)));
  const e = anim.map((a, k) => a / nominal[k]);
  const extras = [];
  const P = {
    n, nomes, t, fim, anim, e, nominal, inicioSaida, fimEntrada: t[0] + anim[0], apertado: e.some((x) => x < 0.999),
    indice(nome) { const i = nomes.indexOf(nome); if (i < 0) throw new Error(`plano: passo "${nome}" não existe (${nomes.join(', ')})`); return i; },
    prog(tt, k, atraso = 0, dur = null, curva = 'entrada') {
      if (typeof k === 'string') k = P.indice(k);
      return ctx.prog(tt, t[k] + atraso * e[k], (dur ?? nominal[k] - atraso) * e[k], curva);
    },
    lin(tt, k, atraso = 0, dur = null) {
      if (typeof k === 'string') k = P.indice(k);
      return ctx.lin(tt, t[k] + atraso * e[k], (dur ?? nominal[k] - atraso) * e[k]);
    },
    passou(tt, k) { if (typeof k === 'string') k = P.indice(k); return tt >= t[k]; },
    /** Índice do passo em curso em tt (−1 antes do primeiro). */
    atual(tt) { let k = -1; for (let i = 0; i < n; i++) if (tt >= t[i]) k = i; return k; },
    /** Chave de quadro parado: entre o fim da animação de um passo e o disparo do seguinte nada muda. */
    chave(tt) {
      if (tt >= inicioSaida) return null;
      const k = P.atual(tt);
      if (k < 0) return null;
      return tt >= t[k] + anim[k] + 0.05 ? 'passo' + k : null;
    },
    /** Âncora extra dentro de um passo (ex.: cada token que entra), em segundos nominais a partir do disparo. */
    marcar(k, atraso, nome, tipo = 'texto') {
      if (typeof k === 'string') k = P.indice(k);
      extras.push({ t: +(t[k] + atraso * e[k]).toFixed(3), nome, tipo });
      return P;
    },
    ancoras() {
      const lista = roteiro.map((r, k) => ({ t: +t[k].toFixed(3), nome: r.nome, tipo: r.tipo || (k ? 'enfase' : 'entrada') }));
      return lista.concat(extras, [{ t: +inicioSaida.toFixed(3), nome: 'saida', tipo: 'saida' }]).sort((a, b) => a.t - b.t);
    },
  };
  return P;
}

// ─────────────────────────────────────────────────────────────── quadro comum ──
/**
 * Quanto uma caixa w × h girada em torno do meio da borda esquerda (é como a tarja do kit aplica
 * graficos.tarja.inclinacao) passa da própria caixa sem giro. `medir()` da tarja devolve a caixa SEM o giro: sem esta
 * conta, no preset neon-shorts (−3°) a ponta direita do chapéu saía de 10 a 24 px acima da zona segura.
 */
export function folgaDoGiro(w, h, graus) {
  const a = ((graus || 0) * Math.PI) / 180;
  if (!a) return { cima: 0, baixo: 0, esq: 0, dir: 0 };
  const sen = Math.sin(a), cos = Math.cos(a);
  const cantos = [[0, -h / 2], [w, -h / 2], [w, h / 2], [0, h / 2]].map(([x, y]) => [x * cos - y * sen, x * sen + y * cos + h / 2]);
  const xs = cantos.map((q) => q[0]), ys = cantos.map((q) => q[1]);
  return { cima: Math.max(0, -Math.min(...ys)), baixo: Math.max(0, Math.max(...ys) - h), esq: Math.max(0, -Math.min(...xs)), dir: Math.max(0, Math.max(...xs) - w) };
}

/** Zona segura menos a faixa da legenda queimada (ctx.area_livre, kit 1.5); num kit anterior, a zona segura. */
export function areaUtil(ctx, p) {
  const plat = p.plataforma || undefined;
  if (typeof ctx.area_livre === 'function') return ctx.area_livre(plat, { legenda: p.reservar_legenda });
  return ctx.area_segura(plat);
}

/**
 * Monta o quadro comum das cenas da biblioteca e devolve a área que sobra para o conteúdo.
 *   const Q = montarQuadro(palco, p, ctx, { roteiro, legendas: ['frase do passo 1', …] });
 *   Q.raiz      camada da cena (ponha o conteúdo aqui dentro: a saída da DA é aplicada nela)
 *   Q.conteudo  { x, y, w, h, x1, y1 } em px — o retângulo livre entre o chapéu e a frase do passo
 *   Q.P         o plano de passos (planejar)
 *   Q.seek(t)   chapéu, selo, crédito, frases dos passos e a saída — chame DEPOIS de posicionar o conteúdo
 */
export function montarQuadro(palco, p, ctx, { roteiro, legendas = [], selo = 'ilustrativo', larguraLegenda = null } = {}) {
  const real = p.ilustrativo === false;
  if (real && !(p.fonte && String(p.fonte).trim())) {
    throw new Error('ilustrativo=false declara que o dado é real: passe também "fonte" (o crédito de `fatos.py credito F### --sem-prefixo`) e cite o fato em fato_ids no storyboard — ou volte ilustrativo=true para mostrar o selo');
  }
  const P = planejar(ctx, roteiro, p.passos_t);
  const area = areaUtil(ctx, p);
  const horizontal = ctx.orientacao === 'horizontal';
  const raiz = ctx.el('div', 'ia-raiz');
  Object.assign(raiz.style, { position: 'absolute', left: '0', top: '0', width: ctx.L + 'px', height: ctx.A + 'px' });
  palco.appendChild(raiz);
  const vao = ctx.px(horizontal ? 0.034 : 0.026);
  let topo = area.y, base = area.y1;

  // crédito da fonte: peça do kit (papel, tamanho, cor, prefixo e posição de graficos.citacao_fonte)
  let cr = null;
  if (p.fonte && String(p.fonte).trim()) {
    cr = ctx.kit.credito(p.fonte, { area });
    raiz.appendChild(cr.el);
    const r = cr.posicionar();
    const noMeio = !cr.posicao.startsWith('superior') && !cr.posicao.startsWith('inferior');
    if (!noMeio) { if (r.em_cima) topo += r.faixa; else base -= r.faixa; }
  }

  // chapéu (tarja da DA) e selo "ilustrativo"
  let tarja = null, hCab = 0, wTarja = 0;
  if (p.titulo && String(p.titulo).trim()) {
    tarja = ctx.kit.tarja(String(p.titulo).trim(), { tam: Math.min(ctx.px(ctx.DA.graficos.tarja.tamanho), ctx.tam('h3')) });
    raiz.appendChild(tarja.el);
    const giro = ctx.DA.graficos.tarja.inclinacao;
    let m = tarja.medir(), g = folgaDoGiro(m.w, m.h, giro);
    if (m.w + g.esq + g.dir > area.w) { ctx.ajustar_texto(tarja.texto, area.w * 0.9, { min: ctx.tam('nota') }); m = tarja.medir(); g = folgaDoGiro(m.w, m.h, giro); }
    ctx.place(tarja.el, { x: Math.round(area.x + g.esq), y: Math.round(topo + g.cima) });   // a caixa GIRADA é que fica dentro da zona
    hCab = g.cima + m.h + g.baixo; wTarja = g.esq + m.w + g.dir;
  }
  let seloEl = null;
  if (p.ilustrativo === true && selo) {
    const tam = ctx.tam('nota');
    const padX = tam * 0.6, padY = tam * 0.28, borda = Math.max(1, ctx.traco * 0.75);
    seloEl = ctx.texto('dados', selo, { tam, cor: 'texto_suave', classe: 'ia-selo' });
    Object.assign(seloEl.style, { position: 'absolute', padding: `${padY.toFixed(1)}px ${padX.toFixed(1)}px`,
      border: `${borda.toFixed(1)}px solid ${ctx.alfa('texto_suave', 0.6)}`, borderRadius: ctx.raio + 'px' });
    raiz.appendChild(seloEl);
    const m = ctx.medir(seloEl);
    const w = m.w + 2 * padX + 2 * borda, h = m.h + 2 * padY + 2 * borda;
    if (wTarja + vao + w <= area.w) {                        // na linha do chapéu, à direita
      ctx.place(seloEl, { x: area.x1 - w, y: topo + Math.max(0, (hCab - h) / 2) });
      hCab = Math.max(hCab, h);
    } else {                                                // não coube ao lado: embaixo do chapéu
      ctx.place(seloEl, { x: area.x, y: topo + hCab + ctx.px(0.012) });
      hCab += h + ctx.px(0.012);
    }
  }

  // frase de cada passo (uma por vez), na base
  // Peça com legenda queimada (a zona útil já descontou a faixa dela): as frases de passo ficam de fora por padrão,
  // para não empilhar dois textos — quem narra é a legenda. `legendas` explícito continua valendo.
  const textos = p.legendas == null ? (area.reservou ? [] : legendas) : p.legendas;
  if (textos.length > P.n) throw new Error(`legendas tem ${textos.length} frases, mas esta cena tem ${P.n} passo(s) (${P.nomes.join(', ')})`);
  const wLeg = Math.min(area.w, larguraLegenda ?? (horizontal ? ctx.col(Math.ceil(ctx.DA.layout.grade.colunas * 0.75)) : area.w));
  const tamLeg = ctx.tam('h3');
  let hLeg = 0;
  // As frases entram com a entrada padrão da DA; `sobe` parte de baixo e `desliza` de fora — o recorte do tamanho da
  // área útil garante que nenhuma passe da zona segura (nem cubra o crédito) no meio do caminho.
  const recorte = ctx.el('div', 'ia-frases');
  Object.assign(recorte.style, { position: 'absolute', left: Math.round(area.x) + 'px', top: Math.round(area.y) + 'px', width: Math.round(area.w) + 'px', height: Math.max(0, Math.round(base - area.y)) + 'px', overflow: 'hidden' });
  raiz.appendChild(recorte);
  const frases = P.nomes.map((_, k) => {
    const txt = textos[k];
    if (!txt || !String(txt).trim()) return null;
    const e = ctx.texto('corpo', '', { tam: tamLeg, cor: 'texto', wrap: true, maxW: wLeg, classe: 'ia-frase', html: marcarTermos(ctx, txt, p.cor) });
    e.style.position = 'absolute';
    recorte.appendChild(e);
    // uma linha só enquanto a letra não cair abaixo de `corpo`; senão quebra em duas no tamanho cheio
    let m = ctx.medir(e);
    if (m.linhas > 1) {
      e._inner.style.whiteSpace = 'nowrap'; e._inner.style.width = 'auto';
      const corrida = e._inner.offsetWidth * (e._sx || 1);
      const tamUmaLinha = tamLeg * (wLeg / corrida) * 0.995;
      e._inner.style.whiteSpace = 'normal'; e._inner.style.width = (wLeg / (e._sx || 1)).toFixed(2) + 'px';
      if (tamUmaLinha >= ctx.tam('corpo')) { e._inner.style.fontSize = tamUmaLinha.toFixed(2) + 'px'; e._tam = tamUmaLinha; }
      else ctx.ajustar_texto(e, wLeg, { min: Math.max(ctx.tam('nota'), ctx.tam('corpo') * 0.9), maxLinhas: 2 });
      m = ctx.medir(e);
    }
    hLeg = Math.max(hLeg, m.h);
    return { e, n: String(txt).replace(/\*/g, '').length };
  });
  if (hLeg) {
    for (const f of frases) if (f) ctx.place(f.e, { x: 0, y: Math.round(base - hLeg) - Math.round(area.y) });
    base -= hLeg + vao;
  }
  const y0 = topo + (hCab ? hCab + vao : 0);
  const conteudo = { x: area.x, y: y0, w: area.w, h: Math.max(0, base - y0), x1: area.x1, y1: base };
  if (conteudo.h < ctx.px(0.2)) {
    throw new Error(`sobrou pouco espaço para a cena (${Math.round(conteudo.h)} px de altura na zona "${area.plataforma}"): esconda o chapéu (titulo: "") ou as frases (legendas: []), ou passe reservar_legenda=false se esta peça não leva legenda queimada`);
  }

  const media = ctx.dur('media'), curta = ctx.dur('curta');
  const Q = {
    raiz, area, conteudo, P, tarja, selo: seloEl, credito: cr, frases, vao, horizontal, cor: p.cor,
    seek(t) {
      ctx.entrada(raiz, 1, 'fade');
      if (tarja) tarja.seek(ctx.prog(t, 0, media), ctx.prog(t, curta, media));
      if (seloEl) ctx.entrada(seloEl, ctx.prog(t, curta, media), 'fade');
      if (cr) cr.seek(ctx.prog(t, media, media));
      frases.forEach((f, k) => {
        if (!f) return;
        const troca = k < P.n - 1 ? P.t[k + 1] : Infinity;
        if (t >= troca) ctx.saida(f.e, ctx.prog(t, troca, curta * P.e[k + 1], 'saida'), 'fade');
        else ctx.entrada(f.e, ctx.prog(t, P.t[k] + (k ? curta : 0) * P.e[k], media * P.e[k]), undefined, { n: f.n });
      });
      if (t >= P.inicioSaida) ctx.saida(raiz, ctx.prog(t, P.inicioSaida, media, 'saida'));
    },
    /** O que vai para o carimbo (parametros.layout): o auditor e a checagem de pureza amostram em volta destes instantes. */
    layout(extra = {}) {
      return { area: { x: area.x, y: area.y, w: area.w, h: area.h, plataforma: area.plataforma, reservou_legenda: !!area.reservou },
        conteudo: { x: Math.round(conteudo.x), y: Math.round(conteudo.y), w: Math.round(conteudo.w), h: Math.round(conteudo.h) },
        passos: P.nomes.map((nome, k) => ({ nome, t: +P.t[k].toFixed(3), anim: +P.anim[k].toFixed(3) })),
        apertado: P.apertado, ilustrativo: !real, selo: !!seloEl, credito: cr ? cr.rect : null,
        fim_entrada: +P.fimEntrada.toFixed(3), inicio_saida: +P.inicioSaida.toFixed(3), ...extra };
    },
  };
  return Q;
}

// ───────────────────────────────────────────────────────────────────── peças ──
/**
 * Troca o texto de um elemento SÓ quando ele mudou. seek(t) roda muitas vezes com o mesmo t (auditor, checagem de
 * quietude do motor): reescrever `textContent` com o mesmo valor recria o nó de texto, o navegador repinta o trecho e,
 * em render reduzido (--escala 0.25), a borda suavizada dos vizinhos sai um pixel diferente — o motor acusava PEÇA
 * INQUIETA em `proximo_token` em 8 de 12 execuções. Com esta guarda, repetir o seek não toca no DOM.
 */
export function porTexto(el, txt) { const s = String(txt); if (el.textContent !== s) el.textContent = s; }
/** O mesmo para atributo (pontos de uma curva SVG recalculados a cada seek). */
export function porAtributo(el, nome, valor) { const s = String(valor); if (el.getAttribute(nome) !== s) el.setAttribute(nome, s); }

/** Rótulo curto (papel `dados`, escala `nota`, texto suave por padrão). Meça com ctx.medir depois de pôr no DOM. */
export function rotulo(ctx, texto, { papel = 'dados', tam = null, cor = 'texto_suave', html = null, classe = 'ia-rotulo' } = {}) {
  const e = ctx.texto(papel, texto, { tam: Math.max(ctx.tam('nota'), tam ?? ctx.tam('nota')), cor, classe, html });
  e.style.position = 'absolute';
  return e;
}

/**
 * Texto com duas camadas de cor (A normal, B destaque) cruzadas por opacidade — o jeito de "mudar a cor" sem sair da
 * paleta. → { el, a, b, medir(), misturar(q) }  (q = 0: só A; q = 1: só B)
 */
export function textoDuplo(ctx, papel, texto, { tam, corA = 'texto', corB = 'primaria', classe = 'ia-duplo' } = {}) {
  const el = ctx.el('div', classe);
  Object.assign(el.style, { position: 'absolute' });
  const a = ctx.texto(papel, texto, { tam, cor: corA });
  const b = ctx.texto(papel, texto, { tam, cor: corB });
  Object.assign(b.style, { position: 'absolute', left: '0', top: '0' });
  el.append(a, b);
  const api = {
    el, a, b, w: 0, h: 0,
    medir() { const m = ctx.medir(a); ctx.medir(b); el.style.width = m.w + 'px'; el.style.height = m.h + 'px'; api.w = m.w; api.h = m.h; return m; },
    definir(txt) { porTexto(a._inner, txt); porTexto(b._inner, txt); },
    misturar(q) { const v = clamp(q); a.style.opacity = (1 - v).toFixed(3); b.style.opacity = v.toFixed(3); },
  };
  api.misturar(0);
  return api;
}

/**
 * Caixa de token: fundo `superficie` com filete, texto no papel `dados` e uma camada de destaque por cima.
 * Espaço inicial (" gato") vira uma marca desenhada, porque em tokenizadores reais o espaço faz parte do token.
 *   const c = caixaToken(ctx, ' gato', { tam }); pai.appendChild(c.el); c.medir(); ctx.place(c.el, { x, y });
 *   c.estado({ caixa: 0–1, realce: 0–1, apagado: 0–1 })
 */
export function caixaToken(ctx, texto, { tam = null, papel = 'dados', cor = 'primaria', modo = 'cheio', marcarEspaco = true } = {}) {
  const t = tam ?? ctx.tam('h3');
  const padX = t * 0.36, padY = t * 0.2;
  const borda = Math.max(1, ctx.traco * 0.75);
  const raio = Math.min(ctx.raio, t * 0.4);
  const el = ctx.el('div', 'ia-token');
  el.style.position = 'absolute';
  const miolo = ctx.el('div', 'ia-token-miolo');
  Object.assign(miolo.style, { position: 'absolute', left: '0', top: '0', width: '100%', height: '100%' });
  const fundo = ctx.el('div', 'ia-token-fundo');
  Object.assign(fundo.style, { position: 'absolute', inset: '0', background: ctx.cor('superficie'), border: `${borda.toFixed(1)}px solid ${ctx.alfa('texto_suave', 0.55)}`, borderRadius: raio + 'px' });
  const realce = ctx.el('div', 'ia-token-realce');
  Object.assign(realce.style, { position: 'absolute', inset: '0', borderRadius: raio + 'px', opacity: '0' });
  if (modo === 'cheio') realce.style.background = ctx.cor(cor);
  else realce.style.border = `${Math.max(2, ctx.traco * 1.4).toFixed(1)}px solid ${ctx.cor(cor)}`;
  const bruto = String(texto);
  const temEspaco = marcarEspaco && /^\s/.test(bruto);
  const visivel = bruto.replace(/^\s+/, '') || ' ';
  const wEspaco = temEspaco ? t * 0.5 : 0;
  let marca = null;
  if (temEspaco) {                                           // "⎵" desenhado: não depende de a fonte ter o glifo
    marca = ctx.el('div', 'ia-token-espaco');
    const fio = Math.max(1, t * 0.05).toFixed(1) + 'px solid ' + ctx.alfa('texto_suave', 0.9);
    Object.assign(marca.style, { position: 'absolute', left: (padX * 0.8).toFixed(1) + 'px', width: (wEspaco * 0.72).toFixed(1) + 'px', height: (t * 0.16).toFixed(1) + 'px',
      borderLeft: fio, borderRight: fio, borderBottom: fio });
  }
  const txt = textoDuplo(ctx, papel, visivel, { tam: t, corA: 'texto', corB: modo === 'cheio' ? ctx.legivel(cor, 'texto', 'fundo') : cor, classe: 'ia-token-texto' });
  miolo.append(fundo, realce);
  if (marca) miolo.appendChild(marca);
  miolo.appendChild(txt.el);
  el.appendChild(miolo);
  const api = {
    el, fundo, realce, txt, marca, texto: bruto, temEspaco, w: 0, h: 0, padX, padY, wEspaco, tam: t,
    medir() {
      const m = txt.medir();
      api.w = Math.ceil(m.w + wEspaco + 2 * padX); api.h = Math.ceil(m.h + 2 * padY);
      el.style.width = api.w + 'px'; el.style.height = api.h + 'px';
      Object.assign(txt.el.style, { left: (padX + wEspaco).toFixed(1) + 'px', top: padY.toFixed(1) + 'px' });
      if (marca) marca.style.top = (padY + m.h * 0.62).toFixed(1) + 'px';
      api.wTexto = m.w; api.hTexto = m.h;
      return { w: api.w, h: api.h };
    },
    estado({ caixa = 1, realce: r = 0, apagado = 0, espaco = caixa } = {}) {
      fundo.style.opacity = clamp(caixa).toFixed(3);
      realce.style.opacity = clamp(r).toFixed(3);
      txt.misturar(r);
      if (marca) marca.style.opacity = clamp(espaco).toFixed(3);
      miolo.style.opacity = lerp(1, 0.3, clamp(apagado)).toFixed(3);
    },
  };
  api.estado({});
  return api;
}

/**
 * Nó (neurônio, ponto de um grafo): círculo com contorno, carga de ativação (0–1) e anel de destaque.
 *   const n = no(ctx, { r }); pai.appendChild(n.el); n.em(cx, cy); n.estado({ ativacao, realce, visivel })
 */
export function no(ctx, { r, cor = 'primaria' } = {}) {
  const borda = Math.max(1.5, ctx.traco);
  const el = ctx.el('div', 'ia-no');
  Object.assign(el.style, { position: 'absolute', width: 2 * r + 'px', height: 2 * r + 'px' });
  const base = ctx.el('div', 'ia-no-base');
  Object.assign(base.style, { position: 'absolute', inset: '0', borderRadius: '50%', background: ctx.cor('superficie'), border: `${borda.toFixed(1)}px solid ${ctx.cor('texto_suave')}` });
  const carga = ctx.el('div', 'ia-no-carga');
  Object.assign(carga.style, { position: 'absolute', inset: borda.toFixed(1) + 'px', borderRadius: '50%', background: ctx.cor(cor), opacity: '0' });
  const anel = ctx.el('div', 'ia-no-anel');
  const folga = Math.max(3, r * 0.22);
  Object.assign(anel.style, { position: 'absolute', inset: (-folga).toFixed(1) + 'px', borderRadius: '50%', border: `${Math.max(2, ctx.traco * 1.3).toFixed(1)}px solid ${ctx.cor(cor)}`, opacity: '0' });
  el.append(base, carga, anel);
  const api = {
    el, r, cx: 0, cy: 0,
    em(cx, cy) { api.cx = cx; api.cy = cy; el.style.left = (cx - r).toFixed(1) + 'px'; el.style.top = (cy - r).toFixed(1) + 'px'; return api; },
    estado({ ativacao = 0, realce = 0 } = {}) {
      carga.style.opacity = clamp(ativacao).toFixed(3);
      anel.style.opacity = clamp(realce).toFixed(3);
      anel.style.transform = `scale(${lerp(1.25, 1, clamp(realce)).toFixed(4)})`;
    },
  };
  return api;
}

/** Camada SVG do tamanho do quadro (linhas, setas, arcos). Coordenadas em px do quadro. */
export function camadaSvg(ctx, pai) {
  const s = ctx.svg('svg', { width: ctx.L, height: ctx.A, viewBox: `0 0 ${ctx.L} ${ctx.A}` });
  Object.assign(s.style, { position: 'absolute', left: '0', top: '0', overflow: 'visible', pointerEvents: 'none' });
  pai.appendChild(s);
  return s;
}

/**
 * Linha reta (conexão). → elemento com .tracar(p): desenha do início ao fim em função pura de p; aceita tracejado.
 */
export function linha(ctx, svg, x1, y1, x2, y2, { cor = 'texto_suave', esp = null, alfa = 1, tracejado = null } = {}) {
  const e = ctx.svg('line', { x1, y1, x2: x1, y2: y1, stroke: ctx.cor(cor), 'stroke-width': (esp ?? ctx.traco).toFixed(2), 'stroke-opacity': alfa.toFixed(3),
    'stroke-linecap': 'round', fill: 'none', 'stroke-dasharray': tracejado || null });
  svg.appendChild(e);
  e.tracar = (p) => {
    const q = clamp(p);
    porAtributo(e, 'x2', lerp(x1, x2, q).toFixed(2)); porAtributo(e, 'y2', lerp(y1, y2, q).toFixed(2));
    e.style.opacity = q > 0 ? '1' : '0';
    return e;
  };
  e.ponto = (q) => ({ x: lerp(x1, x2, q), y: lerp(y1, y2, q) });
  e.tracar(0);
  return e;
}

/** Caminho curvo (arco de atenção, curva de perda). → elemento com .tracar(p). Não combine com tracejado. */
export function caminho(ctx, svg, d, { cor = 'texto_suave', esp = null, alfa = 1 } = {}) {
  const e = ctx.svg('path', { d, pathLength: 1, stroke: ctx.cor(cor), 'stroke-width': (esp ?? ctx.traco).toFixed(2), 'stroke-opacity': alfa.toFixed(3),
    'stroke-linecap': 'round', 'stroke-linejoin': 'round', fill: 'none' });
  svg.appendChild(e);
  e.style.strokeDasharray = '1 1';
  e.tracar = (p) => { const q = clamp(p); e.style.strokeDashoffset = (1 - q).toFixed(4); e.style.opacity = q > 0 ? '1' : '0'; return e; };
  e.tracar(0);
  return e;
}

/** Arco entre dois pontos (curva quadrática); `altura` > 0 curva para cima/esquerda do segmento. */
export function arco(ctx, svg, x1, y1, x2, y2, altura, op = {}) {
  const mx = (x1 + x2) / 2, my = (y1 + y2) / 2;
  const dx = x2 - x1, dy = y2 - y1, comp = Math.hypot(dx, dy) || 1;
  const cx = mx + (dy / comp) * altura * 2, cy = my - (dx / comp) * altura * 2;      // ponto de controle: o arco passa a `altura` do segmento
  return caminho(ctx, svg, `M ${x1.toFixed(1)} ${y1.toFixed(1)} Q ${cx.toFixed(1)} ${cy.toFixed(1)} ${x2.toFixed(1)} ${y2.toFixed(1)}`, op);
}

/** Seta reta com ponta. → { haste, ponta, tracar(p) } */
export function seta(ctx, svg, x1, y1, x2, y2, { cor = 'texto_suave', esp = null, alfa = 1, ponta = null } = {}) {
  const tam = ponta ?? Math.max(8, (esp ?? ctx.traco) * 4.5);
  const ang = Math.atan2(y2 - y1, x2 - x1);
  const bx = x2 - Math.cos(ang) * tam * 0.9, by = y2 - Math.sin(ang) * tam * 0.9;
  const haste = linha(ctx, svg, x1, y1, bx, by, { cor, esp, alfa });
  const a1 = ang + Math.PI * 0.84, a2 = ang - Math.PI * 0.84;
  const pts = [[x2, y2], [x2 + Math.cos(a1) * tam, y2 + Math.sin(a1) * tam], [x2 + Math.cos(a2) * tam, y2 + Math.sin(a2) * tam]];
  const cabeca = ctx.svg('polygon', { points: pts.map((q) => q.map((v) => v.toFixed(1)).join(',')).join(' '), fill: ctx.cor(cor), 'fill-opacity': alfa.toFixed(3), stroke: 'none' });
  svg.appendChild(cabeca);
  const api = { haste, ponta: cabeca, tracar(p) { haste.tracar(clamp(p / 0.85)); cabeca.style.opacity = clamp((p - 0.8) / 0.2).toFixed(3); return api; } };
  api.tracar(0);
  return api;
}

/**
 * Eixo (linha na cor graficos.dados.eixo) com marcas opcionais. → { linha, marcas[], tracar(p) }
 */
export function eixo(ctx, svg, x1, y1, x2, y2, { marcas = 0, tamMarca = null } = {}) {
  const g = ctx.DA.graficos.dados;
  const esp = Math.max(1, ctx.traco * 0.75);
  const l = linha(ctx, svg, x1, y1, x2, y2, { cor: g.eixo, esp });
  const tm = tamMarca ?? ctx.px(0.008);
  const comp = Math.hypot(x2 - x1, y2 - y1) || 1;
  const nx = -(y2 - y1) / comp, ny = (x2 - x1) / comp;
  const ms = [];
  for (let i = 1; i <= marcas; i++) {
    const q = i / (marcas + 1), px = lerp(x1, x2, q), py = lerp(y1, y2, q);
    const m = linha(ctx, svg, px - nx * tm, py - ny * tm, px + nx * tm, py + ny * tm, { cor: g.eixo, esp });
    m.q = q; ms.push(m);
  }
  return { linha: l, marcas: ms, tracar(p) { l.tracar(p); for (const m of ms) m.tracar(clamp((p - m.q) * 6)); } };
}

/**
 * Matriz de calor: células com a cor do destaque e opacidade proporcional ao valor (0–max).
 *   const M = matrizDeCalor(ctx, { linhas, colunas, lado, vao }); pai.appendChild(M.el); ctx.place(M.el, { x, y });
 *   M.celula(i, j, valor 0–1, p 0–1)   M.contornar(i, p)  (destaca a linha i)   M.vazia(i, j, p) (célula mascarada)
 */
export function matrizDeCalor(ctx, { linhas, colunas, lado, vao = null, cor = 'primaria' }) {
  const g = ctx.DA.graficos.dados;
  const v = vao ?? Math.max(2, lado * 0.08);
  const raio = Math.min(ctx.raio, lado * 0.2);
  const el = ctx.el('div', 'ia-matriz');
  const w = colunas * lado + (colunas - 1) * v, h = linhas * lado + (linhas - 1) * v;
  Object.assign(el.style, { position: 'absolute', width: w + 'px', height: h + 'px' });
  const cel = [], aneis = [];
  for (let i = 0; i < linhas; i++) {
    cel.push([]);
    for (let j = 0; j < colunas; j++) {
      const c = ctx.el('div', 'ia-matriz-celula');
      Object.assign(c.style, { position: 'absolute', left: j * (lado + v) + 'px', top: i * (lado + v) + 'px', width: lado + 'px', height: lado + 'px' });
      const fundo = ctx.el('div');
      Object.assign(fundo.style, { position: 'absolute', inset: '0', background: ctx.alfa(g.grade, 0.9), borderRadius: raio + 'px' });
      const calor = ctx.el('div');
      Object.assign(calor.style, { position: 'absolute', inset: '0', background: ctx.cor(cor), borderRadius: raio + 'px', opacity: '0' });
      const risco = ctx.el('div');                                // célula mascarada: um traço diagonal
      Object.assign(risco.style, { position: 'absolute', left: '22%', right: '22%', top: '50%', height: Math.max(1, ctx.traco * 0.75).toFixed(1) + 'px',
        background: ctx.cor('texto_suave'), transform: 'rotate(-45deg)', opacity: '0' });
      c.append(fundo, calor, risco);
      el.appendChild(c);
      cel[i].push({ c, fundo, calor, risco });
    }
    const anel = ctx.el('div', 'ia-matriz-anel');
    const f = Math.max(2, v * 0.5);
    Object.assign(anel.style, { position: 'absolute', left: -f + 'px', top: (i * (lado + v) - f) + 'px', width: (w + 2 * f) + 'px', height: (lado + 2 * f) + 'px',
      border: `${Math.max(2, ctx.traco * 1.2).toFixed(1)}px solid ${ctx.cor(cor)}`, borderRadius: (raio + f) + 'px', opacity: '0' });
    el.appendChild(anel);
    aneis.push(anel);
  }
  return {
    el, w, h, lado, vao: v, passo: lado + v,
    grade(p) { for (let i = 0; i < linhas; i++) for (let j = 0; j < colunas; j++) cel[i][j].fundo.style.opacity = clamp(p * 1.6 - (i + j) / (linhas + colunas) * 0.6).toFixed(3); },
    celula(i, j, valor, p = 1) { cel[i][j].calor.style.opacity = (clamp(valor) * clamp(p)).toFixed(3); },
    vazia(i, j, p) { cel[i][j].risco.style.opacity = (0.7 * clamp(p)).toFixed(3); },
    contornar(i, p) { aneis.forEach((a, k) => { a.style.opacity = (k === i ? clamp(p) : 0).toFixed(3); }); },
    centro(i, j) { return { x: j * (lado + v) + lado / 2, y: i * (lado + v) + lado / 2 }; },
  };
}

/**
 * Contador: texto que mostra um número em função pura de p. → { el, definir(valor), medir() }
 * Reserve a largura com o MAIOR texto que ele vai mostrar (`modelo`) para o layout não dançar.
 */
export function contador(ctx, { papel = 'dados', tam = null, cor = 'texto', formato = (v) => num(v, 0), modelo = null } = {}) {
  const e = ctx.texto(papel, modelo ?? formato(0), { tam: tam ?? ctx.tam('corpo'), cor, classe: 'ia-contador' });
  e.style.position = 'absolute';
  return { el: e, medir() { return ctx.medir(e); }, definir(v) { porTexto(e._inner, formato(v)); } };
}

/**
 * Grade responsiva: distribui n itens de proporção `razao` (largura/altura) numa área, escolhendo o número de
 * colunas que dá a maior célula. → { colunas, linhas, w, h, largura, altura, pos(i) → { x, y, linha, coluna } }
 */
export function gradeResponsiva(n, area, { razao = 1, vao = 0, maxColunas = n, minColunas = 1, maxLado = Infinity, centrar = true } = {}) {
  let melhor = null;
  for (let c = Math.max(1, minColunas); c <= Math.max(1, Math.min(n, maxColunas)); c++) {
    const l = Math.ceil(n / c);
    const w = Math.min((area.w - (c - 1) * vao) / c, ((area.h - (l - 1) * vao) / l) * razao, maxLado);
    if (w > 0 && (!melhor || w > melhor.w + 0.01)) melhor = { colunas: c, linhas: l, w, h: w / razao };
  }
  if (!melhor) melhor = { colunas: 1, linhas: n, w: Math.max(1, area.w), h: Math.max(1, area.w) / razao };
  const largura = melhor.colunas * melhor.w + (melhor.colunas - 1) * vao;
  const altura = melhor.linhas * melhor.h + (melhor.linhas - 1) * vao;
  const ox = area.x + (centrar ? (area.w - largura) / 2 : 0), oy = area.y + (centrar ? (area.h - altura) / 2 : 0);
  return { ...melhor, largura, altura, x: ox, y: oy,
    pos(i) { const linha = Math.floor(i / melhor.colunas), coluna = i % melhor.colunas; return { x: ox + coluna * (melhor.w + vao), y: oy + linha * (melhor.h + vao), linha, coluna }; } };
}

/**
 * Quebra uma fila de caixas (larguras em px) em linhas que cabem em `larguraMax`.
 * → [{ itens: [índices], largura }]
 */
export function quebrarEmLinhas(larguras, larguraMax, vao = 0) {
  const linhas = [];
  let atual = { itens: [], largura: 0 };
  larguras.forEach((w, i) => {
    const nova = atual.itens.length ? atual.largura + vao + w : w;
    if (atual.itens.length && nova > larguraMax + 0.5) { linhas.push(atual); atual = { itens: [i], largura: w }; }
    else { atual.itens.push(i); atual.largura = nova; }
  });
  if (atual.itens.length) linhas.push(atual);
  return linhas;
}

/** Barra horizontal com trilha (graficos.dados.grade) e preenchimento em duas camadas (normal / destaque). */
export function barra(ctx, { w, h, cor = 'primaria', corBase = 'texto_suave' }) {
  const g = ctx.DA.graficos.dados;
  const raio = Math.min(ctx.raio, h / 2);
  const el = ctx.el('div', 'ia-barra');
  Object.assign(el.style, { position: 'absolute', width: w + 'px', height: h + 'px' });
  const trilha = ctx.el('div');
  Object.assign(trilha.style, { position: 'absolute', inset: '0', background: ctx.alfa(g.grade, 0.75), borderRadius: raio + 'px' });
  const base = ctx.el('div');
  Object.assign(base.style, { position: 'absolute', left: '0', top: '0', height: '100%', background: ctx.cor(corBase), borderRadius: raio + 'px', width: '0px' });
  const viva = ctx.el('div');
  Object.assign(viva.style, { position: 'absolute', left: '0', top: '0', height: '100%', background: ctx.cor(cor), borderRadius: raio + 'px', width: '0px', opacity: '0' });
  el.append(trilha, base, viva);
  return {
    el, w, h,
    /** fracao 0–1 da largura; realce 0–1 cruza a cor base com a do destaque; trilha 0–1 revela a trilha. */
    estado({ fracao = 0, realce = 0, trilha: tr = 1 } = {}) {
      const px = (clamp(fracao, 0, 1.05) * w).toFixed(2) + 'px';
      base.style.width = px; viva.style.width = px;
      viva.style.opacity = clamp(realce).toFixed(3);
      trilha.style.opacity = clamp(tr).toFixed(3);
    },
  };
}

// ─────────────────────────────────────────── peças das cenas de sistema e genéricas ──
/**
 * Mesmos dados? (para saber se o parâmetro é o exemplo padrão da cena ou dado do usuário). Campo null conta como
 * ausente: o validador do motor preenche com null os campos opcionais de cada objeto antes de a cena receber.
 */
const semNulos = (k, v) => (v === null ? undefined : v);
export const igual = (a, b) => JSON.stringify(a, semNulos) === JSON.stringify(b, semNulos);

/** Degrau da escala da DA multiplicado por s — nunca abaixo de `nota` (o mínimo legível no celular). */
export function tamanho(ctx, nome, s = 1) { return Math.max(ctx.tam('nota'), ctx.tam(nome) * s); }

/**
 * Laço de encaixe: chama tentar(s) com s = `inicio` (1), × 0,92, × 0,92… até o conteúdo caber. `tentar` monta tudo NA ESCALA s
 * dentro de um recipiente e devolve { cabe, … }; quando não cabe, `limpar()` esvazia o recipiente antes da próxima.
 * → o resultado da tentativa aceita + { escala } (a última, mesmo sem caber, quando s chega ao mínimo).
 */
export function caber(tentar, limpar, { min = 0.5, passo = 0.92, inicio = 1 } = {}) {
  for (let s = inicio; ; s *= passo) {
    const r = tentar(s);
    if (r.cabe || s * passo < min) return { ...r, escala: s };
    limpar();
  }
}

/**
 * Depois de `caber`: se nem a menor letra legível fez o conteúdo caber, a cena PARA com uma mensagem acionável —
 * melhor falhar no render (e já no `validar` do storyboard não, porque isso depende do quadro) do que sair da zona segura.
 */
export function encaixou(U, C, cena, dica = 'encurte os textos ou tire itens') {
  exigir(U.cabe, `${cena}: o conteúdo não coube na área útil deste formato (${Math.round(C.w)} × ${Math.round(C.h)} px) nem com a menor letra legível da DA — ${dica}. Para ganhar altura: esconda o chapéu (titulo: "") ou as frases de passo (legendas: []); se a peça não leva legenda queimada, reservar_legenda=false`);
}

/** Respiro: quando a cena AMPLIA o conteúdo (s > 1) para ocupar o quadro, ela para antes de encostar nas bordas. */
export const respiro = (s) => (s > 1 ? 0.88 : 1);

/**
 * Bloco de texto de um papel da DA, já no DOM, medido e ajustado: com `maxW` quebra em linhas e, se passar de
 * `maxLinhas` (ou uma palavra não couber), encolhe até o piso (`min`, nunca abaixo de `nota`).
 * → { el, w, h, linhas, tam, x, y, em(x, y) }   (`pre` preserva espaços e quebras: código e saída de terminal;
 *   `quebraLivre` deixa uma palavra maior que a caixa quebrar em qualquer letra — identificadores e endereços)
 */
export function escrever(ctx, pai, papel, str, { tam = null, cor = 'texto', maxW = 0, maxLinhas = Infinity, min = null, html = null, alinhar = 'esquerda', classe = '', pre = false, quebraLivre = false } = {}) {
  const piso = Math.max(ctx.tam('nota'), min ?? 0);
  const e = ctx.texto(papel, str, { tam: Math.max(piso, tam ?? ctx.tam('corpo')), cor, wrap: maxW > 0, maxW, alinhar, classe, html });
  e.style.position = 'absolute';
  if (pre) e._inner.style.whiteSpace = maxW > 0 ? 'pre-wrap' : 'pre';
  if (quebraLivre) e._inner.style.overflowWrap = 'anywhere';      // palavra mais larga que a caixa quebra em qualquer letra (nome de função, URL)
  pai.appendChild(e);
  let m = ctx.medir(e);
  if (maxW > 0) {
    // "não coube" = linhas demais, ou uma palavra mais larga que a caixa. (A largura medida não serve de critério: em
    // texto centrado ou à direita ela é sempre a da caixa, e comparar com maxW encolhia tudo até o piso.)
    const estoura = () => m.linhas > maxLinhas || e._inner.scrollWidth > e._inner.clientWidth + 1;
    for (let t = e._tam; estoura() && t * 0.94 >= piso; ) { t *= 0.94; e._inner.style.fontSize = t.toFixed(2) + 'px'; e._tam = t; m = ctx.medir(e); }
  }
  const api = { el: e, w: m.w, h: m.h, linhas: m.linhas, tam: e._tam, x: 0, y: 0,
    em(x, y) { api.x = Math.round(x); api.y = Math.round(y); ctx.place(e, { x: api.x, y: api.y }); return api; } };
  return api;
}

/** Etiqueta pequena com placa de fundo (rótulo de ligação por cima de uma linha, número de citação); `maxW` quebra em linhas. */
export function etiqueta(ctx, pai, texto, { tam = null, cor = 'texto_suave', fundo = 'fundo', papel = 'dados', contorno = null, maxW = 0 } = {}) {
  const t = Math.max(ctx.tam('nota'), tam ?? ctx.tam('nota'));
  const padX = t * 0.42, padY = t * 0.16, esp = contorno ? Math.max(1, ctx.traco * 0.75) : 0;
  const e = ctx.texto(papel, texto, { tam: t, cor, classe: 'ia-etiqueta', wrap: maxW > 0, maxW: Math.max(0, maxW - 2 * padX) });
  Object.assign(e.style, { position: 'absolute', padding: `${padY.toFixed(1)}px ${padX.toFixed(1)}px`, background: ctx.cor(fundo), borderRadius: Math.min(ctx.raio, t * 0.4) + 'px' });
  if (contorno) e.style.border = `${esp.toFixed(1)}px solid ${ctx.cor(contorno)}`;
  pai.appendChild(e);
  const m = ctx.medir(e);
  const api = { el: e, w: Math.ceil(m.w + 2 * padX + 2 * esp), h: Math.ceil(m.h + 2 * padY + 2 * esp), x: 0, y: 0,
    em(x, y) { api.x = Math.round(x); api.y = Math.round(y); ctx.place(e, { x: api.x, y: api.y }); return api; } };
  return api;
}

/**
 * Cartão: plano `superficie` com filete, um anel de destaque por cima e o miolo para o conteúdo.
 *   const c = cartao(ctx, { w, h }); pai.appendChild(c.el); c.em(x, y); c.miolo.appendChild(…)
 *   ctx.entrada(c.el, p)                 a entrada da DA vai no elemento de fora
 *   c.estado({ realce, apagado, cheio }) realce = anel na cor do destaque; apagado = recua (0,38); cheio = fundo tingido
 */
export function cartao(ctx, { w, h, cor = 'primaria', fundo = 'superficie', borda = 'texto_suave', alfaBorda = 0.55, raio = null, tinta = 0.16 } = {}) {
  const r = raio ?? Math.min(ctx.raio, Math.min(w, h) / 2);
  const esp = Math.max(1, ctx.traco * 0.75);
  const el = ctx.el('div', 'ia-cartao');
  Object.assign(el.style, { position: 'absolute', width: Math.round(w) + 'px', height: Math.round(h) + 'px' });
  const corpo = ctx.el('div', 'ia-cartao-corpo');             // leva o "apagado": ctx.entrada mexe na opacidade de `el`
  Object.assign(corpo.style, { position: 'absolute', inset: '0' });
  const base = ctx.el('div', 'ia-cartao-fundo');
  Object.assign(base.style, { position: 'absolute', inset: '0', boxSizing: 'border-box', background: ctx.cor(fundo), border: `${esp.toFixed(1)}px solid ${ctx.alfa(borda, alfaBorda)}`, borderRadius: r + 'px' });
  const cheia = ctx.el('div', 'ia-cartao-tinta');
  Object.assign(cheia.style, { position: 'absolute', inset: '0', background: ctx.alfa(cor, tinta), borderRadius: r + 'px', opacity: '0' });
  const anel = ctx.el('div', 'ia-cartao-anel');
  Object.assign(anel.style, { position: 'absolute', inset: '0', boxSizing: 'border-box', border: `${Math.max(2, ctx.traco * 1.4).toFixed(1)}px solid ${ctx.cor(cor)}`, borderRadius: r + 'px', opacity: '0' });
  const miolo = ctx.el('div', 'ia-cartao-miolo');
  Object.assign(miolo.style, { position: 'absolute', inset: '0' });
  corpo.append(base, cheia, anel, miolo);
  el.appendChild(corpo);
  const api = { el, miolo, corpo, w: Math.round(w), h: Math.round(h), x: 0, y: 0, raio: r,
    em(x, y) { api.x = Math.round(x); api.y = Math.round(y); el.style.left = api.x + 'px'; el.style.top = api.y + 'px'; return api; },
    altura(h2) { el.style.height = h2.toFixed(1) + 'px'; return api; },
    estado({ realce = 0, apagado = 0, cheio = 0 } = {}) {
      anel.style.opacity = clamp(realce).toFixed(3);
      cheia.style.opacity = clamp(cheio).toFixed(3);
      corpo.style.opacity = lerp(1, 0.38, clamp(apagado)).toFixed(3);
    } };
  api.estado({});
  return api;
}

/**
 * Digitador: revela o texto de um elemento caractere a caractere, linha a linha, em função pura de p — e diz onde
 * fica o cursor. É a mesma técnica da entrada `digita` do motor (corte na fronteira de cada glifo; o texto não é
 * reescrito), usada aqui quando DIGITAR É O CONTEÚDO (terminal, resposta chegando), não a entrada decorativa da DA.
 * O elemento precisa estar no DOM e no tamanho final. → { total, linhas, seek(p) → { x, y0, y1, vistos, fim } }
 */
export function digitador(ctx, el) {
  const caixa = el.getBoundingClientRect();
  const kx = (caixa.width / (el.offsetWidth || 1)) || 1, ky = (caixa.height / (el.offsetHeight || 1)) || 1;
  const rg = document.createRange();
  const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
  const chars = [], linhas = [];
  let no;
  while ((no = walker.nextNode())) {
    const s = no.nodeValue;
    for (let i = 0; i < s.length; i++) {
      rg.setStart(no, i); rg.setEnd(no, i + 1);
      const r = rg.getBoundingClientRect();
      if (!(r.height > 0)) continue;                           // espaço colapsado numa quebra de linha
      const y0 = (r.top - caixa.top) / ky, y1 = (r.bottom - caixa.top) / ky, x0 = (r.left - caixa.left) / kx, x1 = (r.right - caixa.left) / kx;
      let li = linhas.findIndex((l) => Math.abs((l.y0 + l.y1) / 2 - (y0 + y1) / 2) < (y1 - y0) * 0.5);
      if (li < 0) { linhas.push({ y0, y1, x0 }); li = linhas.length - 1; }
      else { linhas[li].y0 = Math.min(linhas[li].y0, y0); linhas[li].y1 = Math.max(linhas[li].y1, y1); linhas[li].x0 = Math.min(linhas[li].x0, x0); }
      chars.push({ linha: li, x1 });
    }
  }
  const real = linhas.map((l) => ({ y0: l.y0, y1: l.y1, x0: l.x0 }));
  const corte = linhas.map((l) => ({ y0: l.y0, y1: l.y1 }));
  for (let i = 0; i < corte.length - 1; i++) { const m = (corte[i].y1 + corte[i + 1].y0) / 2; corte[i].y1 = m; corte[i + 1].y0 = m; }
  if (corte.length) { corte[0].y0 = -4; corte[corte.length - 1].y1 = el.offsetHeight + 4; }
  for (let i = 1; i < chars.length; i++) if (chars[i].linha === chars[i - 1].linha) chars[i].x1 = Math.max(chars[i].x1, chars[i - 1].x1);
  const total = chars.length, W = (el.offsetWidth + 4).toFixed(2);
  const vazio = { x: 0, y0: 0, y1: el.offsetHeight || ctx.tam('corpo') };
  return { total, linhas: linhas.length,
    seek(p) {
      const vistos = Math.floor(clamp(p) * total + 1e-6);
      if (!total || vistos <= 0) {
        el.style.opacity = '0'; el.style.clipPath = 'inset(0 100% 0 0)';
        return { x: real.length ? real[0].x0 : vazio.x, y0: real.length ? real[0].y0 : vazio.y0, y1: real.length ? real[0].y1 : vazio.y1, vistos: 0, fim: !total };
      }
      const c = chars[vistos - 1], ln = corte[c.linha];
      el.style.opacity = '1';
      if (vistos >= total) el.style.clipPath = 'none';
      else {
        const x = c.x1.toFixed(2), y0 = ln.y0.toFixed(2), y1 = ln.y1.toFixed(2);
        el.style.clipPath = c.linha === 0 ? `polygon(-4px -4px, ${x}px -4px, ${x}px ${y1}px, -4px ${y1}px)`
          : `polygon(-4px -4px, ${W}px -4px, ${W}px ${y0}px, ${x}px ${y0}px, ${x}px ${y1}px, -4px ${y1}px)`;
      }
      return { x: c.x1, y0: real[c.linha].y0, y1: real[c.linha].y1, vistos, fim: vistos >= total };
    } };
}

/**
 * Entrada da DA para BLOCOS (cartão, painel, janela): a entrada padrão do projeto, exceto quando ela é `digita` —
 * que revela texto letra a letra e não faz sentido numa caixa; aí o bloco abre por máscara ("a forma se desenha").
 */
export function entrarBloco(ctx, el, p, op) {
  const tipo = ctx.DA.movimento.entrada_padrao;
  ctx.entrada(el, p, tipo === 'digita' ? 'mascara' : tipo, op);
}

/** Cúbica de Bézier reta entre dois pontos (para usar setaCurva e pontoNaCurva num segmento). */
export function reta(x1, y1, x2, y2) { return [x1, y1, lerp(x1, x2, 1 / 3), lerp(y1, y2, 1 / 3), lerp(x1, x2, 2 / 3), lerp(y1, y2, 2 / 3), x2, y2]; }

/** Ponto e direção de uma cúbica [x1, y1, c1x, c1y, c2x, c2y, x2, y2] em q ∈ [0, 1]. → { x, y, ang } */
export function pontoNaCurva(c, q) {
  const u = 1 - q;
  const f = (i) => u * u * u * c[i] + 3 * u * u * q * c[i + 2] + 3 * u * q * q * c[i + 4] + q * q * q * c[i + 6];
  const g = (i) => 3 * u * u * (c[i + 2] - c[i]) + 6 * u * q * (c[i + 4] - c[i + 2]) + 3 * q * q * (c[i + 6] - c[i + 4]);
  return { x: f(0), y: f(1), ang: Math.atan2(g(1), g(0)) };
}

/**
 * Seta curva (cúbica de Bézier) com ponta. → { haste, ponta, curva, tracar(p), ponto(q) }
 * `tracejado` (ex.: '6 6') troca o desenho progressivo por opacidade (um traço tracejado não se "desenha").
 */
export function setaCurva(ctx, svg, c, { cor = 'texto_suave', esp = null, alfa = 1, ponta = null, tracejado = null } = {}) {
  const e = esp ?? ctx.traco;
  const tam = ponta ?? Math.max(8, e * 4.5);
  let ang = Math.atan2(c[7] - c[5], c[6] - c[4]);
  if (Math.hypot(c[7] - c[5], c[6] - c[4]) < 0.5) ang = Math.atan2(c[7] - c[1], c[6] - c[0]);
  const rx = Math.cos(ang) * tam * 0.9, ry = Math.sin(ang) * tam * 0.9;      // a haste para antes: a ponta cobre o fim
  const d = `M ${c[0].toFixed(1)} ${c[1].toFixed(1)} C ${c[2].toFixed(1)} ${c[3].toFixed(1)}, ${(c[4] - rx).toFixed(1)} ${(c[5] - ry).toFixed(1)}, ${(c[6] - rx).toFixed(1)} ${(c[7] - ry).toFixed(1)}`;
  let haste;
  if (tracejado) {
    haste = ctx.svg('path', { d, stroke: ctx.cor(cor), 'stroke-width': e.toFixed(2), 'stroke-opacity': alfa.toFixed(3), 'stroke-linecap': 'butt', fill: 'none', 'stroke-dasharray': tracejado });
    svg.appendChild(haste);
    haste.tracar = (p) => { haste.style.opacity = clamp(p).toFixed(3); return haste; };
  } else haste = caminho(ctx, svg, d, { cor, esp: e, alfa });
  const a1 = ang + Math.PI * 0.84, a2 = ang - Math.PI * 0.84;
  const pts = [[c[6], c[7]], [c[6] + Math.cos(a1) * tam, c[7] + Math.sin(a1) * tam], [c[6] + Math.cos(a2) * tam, c[7] + Math.sin(a2) * tam]];
  const cabeca = ctx.svg('polygon', { points: pts.map((q) => q.map((v) => v.toFixed(1)).join(',')).join(' '), fill: ctx.cor(cor), 'fill-opacity': alfa.toFixed(3), stroke: 'none' });
  svg.appendChild(cabeca);
  const api = { haste, ponta: cabeca, curva: c,
    tracar(p) { haste.tracar(tracejado ? p : clamp(p / 0.85)); cabeca.style.opacity = clamp((p - 0.8) / 0.2).toFixed(3); return api; },
    ponto(q) { return pontoNaCurva(c, clamp(q)); } };
  api.tracar(0);
  return api;
}

/**
 * Marcador pequeno em duas cores (normal ↔ destaque): 'ponto' (círculo), 'traco' (travessão) ou 'quadrado'.
 * → { el, w, h, misturar(q) }
 */
export function marcador(ctx, { tipo = 'ponto', lado, cor = 'primaria', corBase = 'texto_suave' } = {}) {
  const el = ctx.el('div', 'ia-marcador');
  const w = tipo === 'traco' ? lado * 1.5 : lado, h = tipo === 'traco' ? Math.max(2, lado * 0.22) : lado;
  Object.assign(el.style, { position: 'absolute', width: w.toFixed(1) + 'px', height: h.toFixed(1) + 'px' });
  const raio = tipo === 'ponto' ? '50%' : Math.min(ctx.raio, lado * 0.2) + 'px';
  const a = ctx.el('div'), b = ctx.el('div');
  Object.assign(a.style, { position: 'absolute', inset: '0', background: ctx.cor(corBase), borderRadius: raio });
  Object.assign(b.style, { position: 'absolute', inset: '0', background: ctx.cor(cor), borderRadius: raio, opacity: '0' });
  el.append(a, b);
  return { el, w, h, misturar(q) { const v = clamp(q); a.style.opacity = (1 - v).toFixed(3); b.style.opacity = v.toFixed(3); } };
}
