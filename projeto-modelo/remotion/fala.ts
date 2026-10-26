import palavrasBrutas from '../../../projetos/104. JP/transcricao/final_v2.palavras.json';
import da from '../../../projetos/104. JP/da/da.json';
import roteiro from '../../../projetos/104. JP/roteiro/eventos_v2.json';

// Vídeo gravado do JP (projetos/104. JP). As palavras já estão no tempo do vídeo final (scripts/finalizar.py → palavras_finais).
// Visual da legenda vem da direção de arte do projeto (da/da.json): tamanho, tracking, entrelinha, posição.

export type Palavra = {w: string; chave: string; s: number; e: number};

export const chave = (w: string) =>
  w
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]/g, '');

export const PALAVRAS: Palavra[] = (palavrasBrutas as {w: string; a: number; b: number}[]).map((p) => ({
  w: p.w,
  chave: chave(p.w),
  s: p.a,
  e: Math.max(p.b, p.a + 0.05),
}));

export const FPS = 30;
export const W = 1080;
export const H = 1920;
// fim (pedido do JP, 24/10): acabada a fala, a imagem escurece devagar até o preto e as frases finais surgem uma por vez
// no centro, no estilo da legenda (referência: o fim do vídeo do Nikolas) — insertos.tsx → Final
export const FIM_JP = roteiro.fim_jp; // último quadro do JP na base
// escurece enquanto ele ainda fala ("…mudança desse país.") e chega ao preto no último quadro dele: nada de imagem parada
export const ESCURECE: [number, number] = [roteiro.fim_fala - 1.2, FIM_JP];
export const FINAL_INICIO = FIM_JP + 0.4;
export const FRASES_SEGUNDOS = [2.0, 3.0, 2.2, 4.5]; // quanto cada frase fica na tela (a última, com a bandeira, fecha o vídeo)
export const FRASES_RESPIRO = 0.2; // preto entre uma frase e a outra
export const FINAL_SEGUNDOS = FRASES_SEGUNDOS.reduce((a, b) => a + b, 0) + FRASES_RESPIRO * (FRASES_SEGUNDOS.length - 1);
export const DURACAO_QUADROS = Math.round((FINAL_INICIO + FINAL_SEGUNDOS) * FPS);

const tipo = da.tipografia.papeis.legenda;
export const LEG = {
  fonte: tipo.arquivo,
  tamanho: Math.round(da.legenda.tamanho * W),
  tracking: tipo.tracking,
  entrelinha: tipo.altura_linha,
  largura: Math.round(da.legenda.posicao.vertical.largura_max * W),
  centroY: da.legenda.posicao.vertical.y * H,
  maxPalavras: da.legenda.max_palavras,
  cor: da.cor.paleta.texto,
};
