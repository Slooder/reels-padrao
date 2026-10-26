// moldura.js — OVERLAY transparente que marca um insert/b-roll conforme tratamento.moldura da DA.
// Estilos: nenhuma | borda | cantoneiras | janela | polaroid. A janela (área do vídeo) fica transparente;
// build() devolve `janela` = {x, y, w, h} em px e `janela_girada` = {cx, cy, w, h, angulo, cantos} (a mesma janela
// depois da inclinação da polaroid) para a montagem encaixar o insert — video.encaixar_em_janela faz isso.
// O desenho mora em _moldura.js (peça compartilhada: ctx.kit.moldura); aqui fica só o contrato de cena.
import { criarMoldura } from './_moldura.js';

export const meta = {
  nome: 'moldura',
  descricao: 'Moldura de b-roll/insert (borda, cantoneiras, janela ou polaroid) com rótulo opcional; fundo transparente.',
  dur_padrao: 6,
  formatos: ['horizontal', 'vertical', 'quadrado'],
  alfa_padrao: true,
  grao: false,
  params: {
    rotulo: { tipo: 'texto', padrao: null, descricao: 'rótulo curto (ex.: "arquivo · 2018", "reprodução")' },
    sub: { tipo: 'texto', padrao: null, descricao: 'texto secundário (fonte do material, data)' },
    area: { tipo: 'lista', padrao: null, descricao: 'janela do insert [x, y, w, h] em frações de L e A (padrão: quadro menos a margem; nos estilos janela e polaroid, limitado à área livre da zona segura)' },
    inclinacao: { tipo: 'numero', padrao: null, min: -10, max: 10, descricao: 'rotação em graus (padrão: −1,5 na polaroid, 0 nas demais)' },
    estilo: { tipo: 'opcao', opcoes: ['nenhuma', 'borda', 'cantoneiras', 'janela', 'polaroid'], padrao: null, descricao: 'força um estilo (padrão: o da DA)' },
    plataforma: { tipo: 'plataforma', padrao: null, descricao: 'zona segura que o rótulo e o sub respeitam (vertical: reels, tiktok, shorts, uniao)' },
    reservar_legenda: { tipo: 'booleano', padrao: null, descricao: 'mantém rótulo, sub e (em janela/polaroid, sem `area`) a moldura fora da faixa da legenda; padrão: conforme legenda.reservar_em da DA' },
  },
};

const S = {};

export function build(palco, p, ctx) {
  S.m = criarMoldura(ctx, p);
  palco.appendChild(S.m.el);
  return S.m.layout;
}

export function seek(t) { S.m.seek(t); }

export function key(t) { return S.m.key(t); }

export function ancoras() { return S.m.ancoras(); }
