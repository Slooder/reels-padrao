import React from 'react';
import {AbsoluteFill, Easing, Img, interpolate, interpolateColors, OffthreadVideo, Sequence, staticFile, useCurrentFrame} from 'remotion';
import roteiro from '../../../projetos/104. JP/roteiro/eventos_v2.json';
import nordeste from './nordeste.json';
import {FINAL_INICIO, FPS, FRASES_RESPIRO, FRASES_SEGUNDOS, H, W} from './fala';

// Inserts do JP (pedidos de 23 e 24/10): poucos, sem sombra. Tempos e conteúdo vêm de scripts/plano.py (eventos_v2.json).
//   janela   card 16:9 em cima, cantos arredondados (a capa do Felca); o JP desce na base (montagem.py) enquanto ele está aberto
//   tela     tela cheia: prints, mapa do Nordeste, ranking, Nikolas (abre de uma janelinha), nordestinos, versículo
//   dividida a senhora em cima, o JP embaixo (a base desce junto com a janela: JpTestemunhos.tsx)
// Todo insert entra e sai como a janela da referência do JP ("Dreamy digital product…", 0:07): nasce como uma faixa arredondada
// no meio e cresce até o tamanho final; na saída faz o caminho de volta.

export const PASTA = '104. JP';
const VIDEO_N = `${PASTA}/broll/bruto/nikolas-nordeste/nikolas-nordeste.mp4`;
const NW = 2160; // vídeo do Nikolas: 2160×3840
const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;
const sai = Easing.out(Easing.cubic);
const ENTRA = 0.55;
const SAI = 0.4;

type Clipe = [number, number, number, number]; // [início no vídeo do Nikolas, x, y, largura do recorte no 4K]
export type Evento = {
  tipo: 'janela' | 'tela' | 'dividida';
  id: string;
  de: number;
  ate: number;
  imagem?: string;
  clipes?: Clipe[];
  cartoes?: [string, number][];
};
export const EVENTOS = roteiro.eventos as Evento[];
const [JX0, JY0, JX1, JY1] = roteiro.janela;

const useT = () => useCurrentFrame() / FPS;

// 0 → 1 na entrada, 1 → 0 na saída (curvas rápidas e macias, como na referência)
export const abertura = (t: number, de: number, ate: number, entra = ENTRA, sair = SAI) =>
  Math.min(
    interpolate(t, [de, de + entra], [0, 1], {...clamp, easing: Easing.bezier(0.25, 1, 0.5, 1)}),
    interpolate(t, [ate - sair, ate], [1, 0], {...clamp, easing: Easing.bezier(0.5, 0, 0.75, 0)}),
  );

// a faixa que vira janela: recorte (clip-path) que cresce do meio da caixa até ela inteira
const recorte = (p: number, w: number, h: number, raio: number) => {
  const dx = (w * (1 - interpolate(p, [0, 1], [0.62, 1]))) / 2;
  const dy = (h * (1 - interpolate(p, [0, 1], [0.14, 1]))) / 2;
  const r = interpolate(p, [0, 1], [Math.min(40, h / 2 - dy), raio]);
  return `inset(${dy}px ${dx}px ${dy}px ${dx}px round ${r}px)`;
};

const Janela: React.FC<{de: number; ate: number; x?: number; y?: number; w?: number; h?: number; raio?: number; children: React.ReactNode}> = ({
  de, ate, x = 0, y = 0, w = W, h = H, raio = 0, children,
}) => {
  const p = abertura(useT(), de, ate);
  return (
    <div style={{position: 'absolute', left: x, top: y, width: w, height: h, overflow: 'hidden', clipPath: recorte(p, w, h, raio), opacity: Math.min(1, p * 5)}}>
      {children}
    </div>
  );
};

// trechos do vídeo do Nikolas em sequência (sem som, cortes secos), dividindo [de, ate) por igual, cada um com o seu recorte;
// o recorte cobre a caixa w×h e fica centrado nela (a caixa pode mudar de tamanho na animação do Nikolas)
const Clipes: React.FC<{clipes: Clipe[]; de: number; ate: number; w: number; h: number; aspecto: number}> = ({clipes, de, ate, w, h, aspecto}) => {
  const cada = (ate - de) / clipes.length;
  return (
    <>
      {clipes.map(([ini, rx, ry, rw], i) => {
        const rh = rw * aspecto;
        const s = Math.max(w / rw, h / rh);
        return (
          <Sequence key={ini} from={Math.round((de + i * cada) * FPS)} durationInFrames={Math.round(cada * FPS) + 1} layout="none">
            <div style={{position: 'absolute', left: 0, top: 0, width: w, height: h, overflow: 'hidden'}}>
              <OffthreadVideo
                src={staticFile(VIDEO_N)} muted startFrom={Math.round(ini * FPS)}
                style={{position: 'absolute', left: (w - rw * s) / 2 - rx * s, top: (h - rh * s) / 2 - ry * s, width: NW * s, height: NW * s * (16 / 9)}}
              />
            </div>
          </Sequence>
        );
      })}
    </>
  );
};

// capa do Felca: parada, sem zoom e sem sombra
const Felca: React.FC<{e: Evento}> = ({e}) => (
  <Janela de={e.de} ate={e.ate} x={JX0} y={JY0} w={JX1 - JX0} h={JY1 - JY0} raio={28}>
    <Img src={staticFile(`${PASTA}/${e.imagem}`)} style={{width: '100%', height: '100%', objectFit: 'cover'}} />
  </Janela>
);

// Nikolas: entra numa janelinha à direita do JP, abre para a tela toda, e no fim volta para a janelinha e sai
const PIP = {left: 690, top: 230, width: 330, height: (330 * 16) / 9};
const Nikolas: React.FC<{e: Evento}> = ({e}) => {
  const t = useT();
  const cheio = interpolate(t, [e.de + 0.5, e.de + 0.95, e.ate - 0.95, e.ate - 0.5], [0, 1, 1, 0], {...clamp, easing: Easing.inOut(Easing.cubic)});
  const caixa = {
    left: interpolate(cheio, [0, 1], [PIP.left, 0]), top: interpolate(cheio, [0, 1], [PIP.top, 0]),
    width: interpolate(cheio, [0, 1], [PIP.width, W]), height: interpolate(cheio, [0, 1], [PIP.height, H]),
  };
  return (
    <Janela de={e.de} ate={e.ate} x={caixa.left} y={caixa.top} w={caixa.width} h={caixa.height} raio={interpolate(cheio, [0, 1], [26, 0])}>
      <Clipes clipes={e.clipes ?? []} de={e.de} ate={e.ate} w={caixa.width} h={caixa.height} aspecto={16 / 9} />
    </Janela>
  );
};

// nordestinos: tela toda, cortes secos, mesmo enquadramento para todos (o recorte de cada um vem do plano)
const Nordestinos: React.FC<{e: Evento}> = ({e}) => (
  <Janela de={e.de} ate={e.ate}>
    <AbsoluteFill style={{backgroundColor: '#0E0D0B'}}>
      <Clipes clipes={e.clipes ?? []} de={e.de} ate={e.ate} w={W} h={H} aspecto={H / W} />
    </AbsoluteFill>
  </Janela>
);

// prints: fundo escuro liso, um por vez, grande e centralizado, troca com fade curto (versão simples aprovada)
const Prints: React.FC<{e: Evento}> = ({e}) => {
  const t = useT();
  const cartoes = e.cartoes ?? [];
  return (
    <Janela de={e.de} ate={e.ate}>
      <AbsoluteFill style={{backgroundColor: '#0E0D0B'}}>
        {cartoes.map(([nome, ti], i) => {
          const prox = i + 1 < cartoes.length ? cartoes[i + 1][1] : e.ate + 1;
          const op = Math.min(i === 0 ? 1 : interpolate(t, [ti, ti + 0.18], [0, 1], clamp), interpolate(t, [prox - 0.12, prox], [1, 0], clamp));
          return (
            <div key={nome} style={{position: 'absolute', left: 30, width: W - 60, top: 0, height: 1720, display: 'flex', alignItems: 'center', opacity: op}}>
              <Img src={staticFile(`${PASTA}/broll/tratado/prints/${nome}.png`)} style={{width: '100%', borderRadius: 18}} />
            </div>
          );
        })}
      </AbsoluteFill>
    </Janela>
  );
};

const FUNDO_CINZA = 'radial-gradient(ellipse at 50% 45%, #BDBDBD 0%, #9C9C9C 70%, #8A8A8A 100%)';

// mapa 2D (só a passagem de assunto): o contorno do Nordeste se desenha, a forma se preenche de branco (uma forma só,
// sem estados nem capitais) e "Nordeste" aparece no meio da forma
const Mapa: React.FC<{e: Evento}> = ({e}) => {
  const t = useT();
  const traco = interpolate(t, [e.de + 0.1, e.de + 1.0], [1, 0], {...clamp, easing: Easing.inOut(Easing.cubic)});
  const enche = interpolate(t, [e.de + 0.75, e.de + 1.2], [0, 1], clamp);
  const zoom = interpolate(t, [e.de, e.de + 1.2, e.ate], [0.94, 1, 1.02], {...clamp, easing: sai});
  const rotulo = interpolate(t, [e.de + 1.05, e.de + 1.4], [0, 1], clamp);
  return (
    <Janela de={e.de} ate={e.ate}>
      <AbsoluteFill style={{background: FUNDO_CINZA}}>
        <div style={{position: 'absolute', left: (W - nordeste.w) / 2, top: 860 - nordeste.h / 2, width: nordeste.w, height: nordeste.h, transform: `scale(${zoom})`}}>
          <svg width={nordeste.w} height={nordeste.h} viewBox={`0 0 ${nordeste.w} ${nordeste.h}`}>
            {/* traço da mesma cor fecha a costura entre os estados vizinhos: na tela vira uma forma só */}
            <path d={nordeste.d} fill="#F4F4F4" stroke="#F4F4F4" strokeWidth={1.6} strokeLinejoin="round" opacity={enche} />
            <path d={nordeste.contorno} fill="none" stroke="#F4F4F4" strokeWidth={5} strokeLinejoin="round" pathLength={1}
              strokeDasharray={1} strokeDashoffset={traco} />
          </svg>
          <div
            style={{
              position: 'absolute', left: 0, width: nordeste.w, top: nordeste.cy - 45, textAlign: 'center',
              fontFamily: 'JP Legenda', fontWeight: 700, fontSize: 86, lineHeight: 1, letterSpacing: '-0.035em', color: '#231F1A',
              opacity: rotulo, filter: `blur(${(1 - rotulo) * 8}px)`,
            }}
          >
            Nordeste
          </div>
        </div>
      </AbsoluteFill>
    </Janela>
  );
};

// ranking (print do g1, Anuário 2025): título, as 10 cidades entrando uma a uma com a barra crescendo do zero, e o fecho
// "as 10 primeiras são do Nordeste". Mesmo fundo cinza do mapa, barras brancas, selos vermelhos como no g1.
const RANKING = roteiro.ranking as [string, string, string][];
const Ranking: React.FC<{e: Evento}> = ({e}) => {
  const t = useT();
  const surge = (a: number, d = 0.3) => interpolate(t, [e.de + a, e.de + a + d], [0, 1], clamp);
  const texto = (a: number) => ({opacity: surge(a), filter: `blur(${(1 - surge(a)) * 6}px)`});
  const fecho = surge(2.0, 0.35);
  return (
    <Janela de={e.de} ate={e.ate}>
      <AbsoluteFill style={{background: FUNDO_CINZA, fontFamily: 'JP Legenda', color: '#141414'}}>
        <div style={{position: 'absolute', left: 70, top: 236, fontWeight: 700, fontSize: 32, letterSpacing: '0.1em', color: '#C8102E', ...texto(2.0)}}>
          AS 10 PRIMEIRAS SÃO DO NORDESTE
        </div>
        <div style={{position: 'absolute', left: 70, width: 940, top: 292, fontWeight: 700, fontSize: 78, lineHeight: 1.0, letterSpacing: '-0.03em', ...texto(0.2)}}>
          Cidades mais violentas do Brasil
        </div>
        <div style={{position: 'absolute', left: 70, top: 468, fontFamily: 'JP Texto', fontSize: 33, color: '#333333', ...texto(0.3)}}>
          Mortes violentas por 100 mil habitantes
        </div>
        {RANKING.map(([cidade, uf, taxa], i) => {
          const a = 0.45 + i * 0.09;
          const barra = interpolate(t, [e.de + a + 0.1, e.de + a + 0.7], [0, 1], {...clamp, easing: sai});
          const valor = parseFloat(taxa.replace(',', '.'));
          return (
            <div key={cidade} style={{position: 'absolute', left: 70, width: 940, top: 556 + i * 86, height: 70, display: 'flex', alignItems: 'center', ...texto(a)}}>
              <div style={{width: 78, height: 54, borderRadius: 12, background: '#C8102E', color: '#FFFFFF', fontWeight: 700, fontSize: 30,
                display: 'flex', alignItems: 'center', justifyContent: 'center', marginRight: 20}}>
                {i + 1}º
              </div>
              <div style={{flex: 1, fontWeight: 700, fontSize: 36, letterSpacing: '-0.02em', whiteSpace: 'nowrap'}}>
                {cidade} <span style={{fontFamily: 'JP Texto', fontWeight: 400, fontSize: 27, color: '#3D3D3D'}}>{uf}</span>
              </div>
              <div style={{width: 220, height: 18}}>
                <div style={{width: (220 * valor * barra) / 80, height: 18, borderRadius: 9, background: '#FFFFFF'}} />
              </div>
              <div style={{width: 100, textAlign: 'right', fontWeight: 700, fontSize: 36}}>{taxa}</div>
            </div>
          );
        })}
        <div style={{position: 'absolute', left: 70, width: 940, top: 1440, fontFamily: 'JP Texto', fontSize: 22, color: '#333333', opacity: fecho}}>
          {roteiro.fonte_ranking} (via g1)
        </div>
      </AbsoluteFill>
    </Janela>
  );
};

// versículo: fundo escuro, texto serifado centralizado na tela; "morno" e "vomitar-te-ei da minha boca" acendem em amarelo
const VERSO: [string, number][] = [
  ['Assim, porque és', 0], ['morno,', 1], ['e não és frio nem quente,', 0], ['vomitar-te-ei', 2], ['da minha boca.', 2],
];
const Versiculo: React.FC<{e: Evento}> = ({e}) => {
  const t = useT();
  const acende = (n: number) => (n === 0 ? 0 : interpolate(t, [e.de + (n === 1 ? 1.6 : 3.2), e.de + (n === 1 ? 1.9 : 3.5)], [0, 1], clamp));
  return (
    <Janela de={e.de} ate={e.ate}>
      <AbsoluteFill style={{background: 'radial-gradient(ellipse at 50% 46%, #1C1A17 0%, #0E0D0B 75%)'}}>
        <div style={{position: 'absolute', left: 90, right: 90, top: 0, height: 1840, display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center'}}>
          <div style={{fontFamily: 'JP Legenda', fontWeight: 700, fontSize: 34, letterSpacing: '0.14em', color: '#D9D4CA', marginBottom: 46}}>
            APOCALIPSE 3:16
          </div>
          <div style={{fontFamily: 'JP Versiculo', fontWeight: 700, fontSize: 78, lineHeight: 1.18, letterSpacing: '-0.01em', textAlign: 'center', color: '#E6DAC0'}}>
            {VERSO.map(([trecho, n]) => (
              // "vomitar-te-ei" não quebra no hífen
              <span key={trecho} style={{color: n ? interpolateColors(acende(n), [0, 1], ['#E6DAC0', '#F2D24B']) : undefined, whiteSpace: trecho.includes('-') ? 'nowrap' : undefined}}>
                {trecho}{' '}
              </span>
            ))}
          </div>
        </div>
      </AbsoluteFill>
    </Janela>
  );
};

// a senhora (vídeo do Nikolas, sem som) na metade de cima; o JP desce para a metade de baixo junto com a janela
const Senhora: React.FC<{e: Evento}> = ({e}) => (
  <Janela de={e.de} ate={e.ate} h={H / 2}>
    <AbsoluteFill style={{backgroundColor: '#0E0D0B'}}>
      <Clipes clipes={e.clipes ?? []} de={e.de} ate={e.ate} w={W} h={H / 2} aspecto={H / 2 / W} />
    </AbsoluteFill>
  </Janela>
);

// frases finais sobre o preto (referência do JP: o fim do vídeo do Nikolas, "Na hora de votar, não se esqueça…"): uma por vez,
// grandes e no centro, na tipografia da legenda; cada uma surge com opacidade e desfoque e some antes da próxima.
// A última (diagramação do JP, 24/10) entra em três tempos: o nome, o número grande em amarelo (primária da DA) e por último a
// bandeira do Brasil menor (broll/bruto/bandeira/flag-of-brazil.svg, Wikimedia, domínio público).
const FRASES = roteiro.cartela as string[];
const TEXTO_FINAL = {fontFamily: 'JP Legenda', fontWeight: 700, lineHeight: 1.0, letterSpacing: '-0.045em', textAlign: 'center'} as const;
const TEMPO_FRASES = (() => {
  let t = FINAL_INICIO;
  return FRASES_SEGUNDOS.map((d) => {
    const de = t;
    t += d + FRASES_RESPIRO;
    return [de, de + d] as const;
  });
})();
export const Final: React.FC = () => {
  const t = useT();
  if (t < FINAL_INICIO) return null;
  return (
    <AbsoluteFill style={{backgroundColor: '#000000'}}>
      {FRASES.map((frase, i) => {
        const [de, ate] = TEMPO_FRASES[i];
        if (t < de || t > ate) return null;
        const ultima = i === FRASES.length - 1;
        const entra = (atraso = 0) => interpolate(t, [de + atraso, de + atraso + 0.45], [0, 1], {...clamp, easing: sai});
        const surge = (atraso = 0) => ({opacity: entra(atraso), filter: `blur(${(1 - entra(atraso)) * 8}px)`});
        const some = interpolate(t, [ate - (ultima ? 0.6 : 0.28), ate], [1, 0], clamp);
        return (
          <div key={frase} style={{position: 'absolute', left: 90, right: 90, top: 0, height: 1800, display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center', gap: ultima ? 34 : 0, opacity: some}}>
            {ultima ? (
              <>
                <div style={{...TEXTO_FINAL, ...surge(0), fontSize: 92, color: '#FFFFFF'}}>{frase}</div>
                <div style={{...TEXTO_FINAL, ...surge(0.5), fontSize: 320, lineHeight: 0.9, letterSpacing: '-0.03em', color: '#F2D24B'}}>{roteiro.numero}</div>
                <Img src={staticFile(`${PASTA}/broll/bruto/bandeira/flag-of-brazil.svg`)} style={{width: 150, height: 105, borderRadius: 8, ...surge(1.0)}} />
              </>
            ) : (
              <div style={{...TEXTO_FINAL, ...surge(0), fontSize: 86, color: '#FFFFFF', whiteSpace: 'pre-line'}}>{frase}</div>
            )}
          </div>
        );
      })}
    </AbsoluteFill>
  );
};

const PECAS: Record<string, React.FC<{e: Evento}>> = {
  felca: Felca, prints: Prints, mapa: Mapa, ranking: Ranking, nikolas: Nikolas, nordestinos: Nordestinos, senhora: Senhora, versiculo: Versiculo,
};

export const Insertos: React.FC = () => {
  const t = useT();
  return (
    <>
      {EVENTOS.filter((e) => t >= e.de && t <= e.ate).map((e) => {
        const Peca = PECAS[e.id];
        return <Peca key={e.id} e={e} />;
      })}
    </>
  );
};

export const emTela = (t: number) => EVENTOS.some((e) => e.tipo === 'tela' && t >= e.de && t < e.ate);
// tela dividida: quanto ela está aberta (0–1), para a base descer junto
export const divisao = (t: number) => {
  const e = EVENTOS.find((d) => d.tipo === 'dividida' && t >= d.de && t < d.ate);
  return e ? abertura(t, e.de, e.ate) : 0;
};
