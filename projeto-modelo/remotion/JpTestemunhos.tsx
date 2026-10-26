import React, {useEffect, useState} from 'react';
import {AbsoluteFill, cancelRender, continueRender, delayRender, Easing, Freeze, interpolate, OffthreadVideo, staticFile, useCurrentFrame} from 'remotion';
import {ESCURECE, FIM_JP, FINAL_INICIO, FPS, H, LEG, Palavra, PALAVRAS} from './fala';
import {divisao, emTela, Final, Insertos, PASTA} from './insertos';

// "Testemunhos" (JP, Reels 9:16). Base = decupagem aprovada (scripts/montagem.py → render/_base_v2.mp4) + inserts + legenda.
// Legenda pedida pelo JP (23/10): texto simples, sem animação, uma linha só, tudo do mesmo tamanho, sem sombra, baixa
// e centralizada; uma frase emenda na outra (sem buraco entre elas). Some nas telas cheias; na tela dividida vai para a emenda.
// Sombra leve embaixo (24/10). A base desce junto com a abertura da tela dividida.
// Centralização medida no vídeo pronto: projetos/104. JP/scripts/checar_legenda.py (desvio do centro ≤ 8 px, regra do Studio).

// largura média de um caractere da Helvetica Bold com o tracking da DA, em em — estimativa para caber numa linha
const EM_POR_LETRA = 0.54;
const MAX_LETRAS = Math.floor(LEG.largura / (EM_POR_LETRA * LEG.tamanho));
// tela dividida: o JP (metade de baixo) mostra a faixa y 420–1380 da base, com o rosto no meio da metade
const DIVIDIDA_Y0 = 420;

type Bloco = {texto: string; de: number; ate: number};

// frases curtas numa linha: quebra em pontuação, em pausa, no limite de palavras ou quando não cabe mais
const montarBlocos = (palavras: Palavra[]): Bloco[] => {
  const grupos: Palavra[][] = [];
  let atual: Palavra[] = [];
  palavras.forEach((p, i) => {
    const ant = palavras[i - 1];
    const letras = atual.map((a) => a.w).join(' ').length + 1 + p.w.length;
    if (atual.length && (/[.,;:?!]$/.test(ant.w) || p.s - ant.e > 0.45 || atual.length >= LEG.maxPalavras || letras > MAX_LETRAS)) {
      grupos.push(atual);
      atual = [];
    }
    atual.push(p);
  });
  if (atual.length) grupos.push(atual);
  // cada frase fica até a próxima começar: uma emenda na outra
  const de = grupos.map((g) => Math.max(0, g[0].s - 0.05));
  return grupos.map((g, i) => ({
    texto: g.map((p) => p.w).join(' '),
    de: de[i],
    ate: i + 1 < grupos.length ? de[i + 1] : g[g.length - 1].e + 0.6,
  }));
};
const BLOCOS = montarBlocos(PALAVRAS);

const FONTES: [string, string, string][] = [
  ['JP Legenda', `${PASTA}/da/${LEG.fonte}`, '700'],
  ['JP Texto', `${PASTA}/da/fontes/Helvetica.ttf`, '400'],
  ['JP Versiculo', `${PASTA}/da/fontes/Newsreader-Variable.ttf`, '200 800'],
];
const useFontes = () => {
  const [espera] = useState(() => delayRender('fontes'));
  useEffect(() => {
    Promise.all(
      FONTES.map(([nome, arq, peso]) =>
        new FontFace(nome, `url('${staticFile(arq)}') format('truetype')`, {weight: peso}).load().then((f) => {
          (document.fonts as unknown as {add: (f: FontFace) => void}).add(f);
        }),
      ),
    )
      .then(() => continueRender(espera))
      .catch((e) => cancelRender(e));
  }, [espera]);
};

const Legenda: React.FC = () => {
  const t = useCurrentFrame() / FPS;
  const bloco = BLOCOS.find((b) => t >= b.de && t < b.ate);
  if (!bloco || emTela(t) || t >= FINAL_INICIO) return null;
  const centro = divisao(t) > 0.5 ? H / 2 : LEG.centroY;
  return (
    <div
      style={{
        position: 'absolute', left: 0, right: 0, top: centro - (LEG.tamanho * LEG.entrelinha) / 2,
        textAlign: 'center', whiteSpace: 'nowrap',
        fontFamily: 'JP Legenda', fontWeight: 700, fontSize: LEG.tamanho, lineHeight: LEG.entrelinha,
        letterSpacing: `${LEG.tracking}em`, color: LEG.cor,
      }}
    >
      {bloco.texto}
    </div>
  );
};

export const JpTestemunhos: React.FC = () => {
  useFontes();
  const t = useCurrentFrame() / FPS;
  return (
    <AbsoluteFill style={{backgroundColor: 'black'}}>
      {/* depois do último quadro do JP a base é preta: ele fica congelado enquanto a imagem escurece */}
      <Freeze frame={Math.round(FIM_JP * FPS) - 1} active={(f) => f >= Math.round(FIM_JP * FPS) - 1}>
        <OffthreadVideo
          src={staticFile(`${PASTA}/render/_base_v2.mp4`)}
          style={{transform: `translateY(${divisao(t) * (H / 2 - DIVIDIDA_Y0)}px)`}}
        />
      </Freeze>
      {/* sombra bem leve embaixo, atrás da legenda (referência "Dreamy digital product…") */}
      <AbsoluteFill style={{background: 'linear-gradient(to bottom, rgba(0,0,0,0) 58%, rgba(0,0,0,0.38) 100%)'}} />
      <Insertos />
      <Legenda />
      {/* acabada a fala, escurece devagar até o preto; as frases finais surgem depois, no preto */}
      <AbsoluteFill style={{backgroundColor: 'black', opacity: interpolate(t, ESCURECE, [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.inOut(Easing.quad)})}} />
      <Final />
    </AbsoluteFill>
  );
};
