---
name: video-mapa-documental
description: Cria vídeos curtos (reels/shorts 9:16) no estilo "mapa documental" de canal de história — mapa de satélite escuro sobre papel cinza quadriculado com vinheta pesada, país que acende em verde-esmeralda PISCANDO com bordas brancas brilhantes e rios acesos, região vermelha translúcida de borda macia que se espalha e se fecha numa área marcada por um triângulo vermelho com texto branco black, e anotações de documentário (linhas de chamada com cotovelo cujo rótulo se "decodifica", retrato P&B em círculo, círculo tracejado que encolhe girando), tudo num mergulho contínuo de câmera sem cortes. Feito com páginas HTML animadas quadro a quadro (canvas + GSAP + Playwright + ffmpeg), relevo real da NASA e vetores Natural Earth (domínio público) e som sintetizado (tambores de guerra, zumbido elétrico, chiado de dados). Use sempre que o usuário pedir mapa animado, "mapa estilo documentário", "mapa histórico", "mapa de guerra", "como X se espalhou pelo mapa", expansão/rota/território/ocupação/migração/difusão no mapa, explainer de história ou geografia, reels educativo com mapa, "igual àqueles mapas de canal de história", ou mandar uma referência nesse visual pedindo algo "nesse estilo", mesmo sem dizer "mapa documental".
---

# Vídeo em mapa documental

As 3 marcas do estilo:

1. **Mapa escuro de satélite sobre papel cinza quadriculado com vinheta** — o país em foco acende verde-esmeralda com bordas brancas brilhantes e rios/lagos verde-água acesos; o resto da terra fica cinza-escuro.
2. **Região vermelha translúcida de borda macia** que acende piscando, se espalha em manchas e se fecha numa área só, marcada por um **triângulo vermelho com texto branco black**.
3. **Anotações de documentário** sobre um **mergulho contínuo de câmera sem cortes**: chamadas com cotovelo cujo rótulo se decodifica (barras borradas → letras), retrato P&B em círculo que voa para dentro do triângulo, círculo tracejado que encolhe girando.

Funciona porque o espectador lê o mapa como "documento": a textura de satélite dá verdade, o piscar elétrico dá a sensação de sistema/arquivo, e o vermelho sobre verde dirige o olho para um só lugar enquanto a câmera mergulha.

Veja `assets/exemplo.mp4` (8 s, "o café no Brasil — como ele se espalhou pelo mapa"). O código está em `assets/projeto/videos/exemplo-cafe/index.html` e é o ponto de partida de todo vídeo novo.

## Preparar o projeto (uma vez por pasta)

```bash
bash <caminho-da-skill>/scripts/setup.sh <pasta-do-projeto>
cd <pasta-do-projeto> && N=$(bash tools/node.sh)
$N render.mjs exemplo --preview=12        # confere que o motor roda → previews/exemplo-cafe.jpg
```

Requisitos: Node ≥ 20 (o `tools/node.sh` acha um; o PATH pode ter um velho), ffmpeg, python3 e internet na primeira vez para baixar os dados do mapa. macOS 14+ só se for recortar fotos com Vision.

## Fluxo

1. **Roteiro** — escolha o país e a região-alvo, e escreva a tabela `T` com o roteiro-tipo de `references/movimento.md` (mundo → país acende → mergulho com bordas → etiquetas → manchas se espalham → núcleo + mergulho → triângulo → chamada 1 → retrato → círculo → chamada 2 → respiro). Em 5–8 s mantenha essa ordem e proporção.
   **Fatos:** não invente números nem datas; use só o que você sabe com certeza (ano marcante, século, "maior produtor hoje"…).
2. **Dados do mapa** (`tools/mapa.py`, domínio público — ver `references/receitas.md` §1):
   ```bash
   P=audio/.venv/bin/python
   $P -I tools/mapa.py baixar fontes --bbox=<l0,b0,l1,b1 do continente> --ppd 16 --nome base
   $P -I tools/mapa.py baixar fontes --bbox=<caixa do país>  --ppd 64  --nome pais
   $P -I tools/mapa.py baixar fontes --bbox=<caixa da região final> --ppd 160 --nome reg
   $P -I tools/mapa.py texturas fontes base videos/<nn-nome>/img --borda 0
   $P -I tools/mapa.py texturas fontes pais videos/<nn-nome>/img --relevo
   $P -I tools/mapa.py texturas fontes reg  videos/<nn-nome>/img --relevo
   $P -I tools/mapa.py vetores  fontes <País em inglês> videos/<nn-nome>/geo.json --bbox=<caixa do país>
   ```
3. **Retrato** — foto livre (CC0/PD/CC BY/BY-SA) do Commons: `tools/commons.py buscar/baixar`, depois P&B quadrada (~560 px). Nada de pessoas da referência; se for pessoa, só figura histórica com foto em domínio público.
4. **Montar** — `cp -R videos/exemplo-cafe videos/<nn-nome>`; troque câmera, manchas, etiquetas e anotações mantendo a gramática (`references/estilo.md`, API em `references/receitas.md`).
5. **Preview** — `$N render.mjs <nn> --at=0.4,1.3,2.2,2.9,3.4,4.3,5.2,7.8` → `previews/<nn-nome>.jpg`. Confira: nada cortado na borda, rótulo fora do círculo tracejado, triângulo sem cobrir o alvo da chamada.
6. **Som e render** — `$N render.mjs <nn> --at=1` (grava cues) → `audio/.venv/bin/python audio/synth.py <nn>` → `$N render.mjs <nn>` → `out/<nn-nome>.mp4` (ver `references/audio.md`).
7. **Conferir** — `ffprobe` (1080×1920, duração, áudio) e uma folha de 8 qps; créditos no rodapé (`.md-cred`).

## Regras do motor

- Tudo é função do tempo: estado do mapa e peças são calculados no `onTick` (o render pula para qualquer `t`). Nada de animação CSS, `setTimeout`, `requestAnimationFrame` ou `Math.random()` — use `K.rng` / `MD.pisca`.
- O mapa é **um canvas redesenhado a cada quadro** (`M.desenhar(t)`); as anotações são DOM presas a lon/lat (`MD.tick(t)`). Chame os dois no mesmo `onTick`, nessa ordem.
- `MD.mapa` é assíncrono (carrega `geo.json` e texturas): crie tudo dentro de `window.SETUP = async () => {…}`.
- Projeção equirretangular com `lat0` no meio do país (`x = lon·cos(lat0)`). Para países longe do equador (> 45°) a deformação aparece; aceite ou escolha `lat0` no centro da região final.
- Texturas: a fina (`--ppd 160`) só na região do mergulho final; a grossa embaixo cobre o resto. A ordem em `tex:[…]` é de baixo para cima.
- Camada vermelha: as texturas são desenhadas primeiro e recortadas pela máscara desfocada (`destination-in`). Nunca troque por `source-in` — ele apaga tudo fora de cada textura.
- Chamadas e rótulos: largura máxima ≈ 440 px; deixe ≥ 40 px de margem lateral. Não ponha `escala` nas chamadas (o empurrão as joga para fora da tela); triângulo, retrato e círculo podem crescer com `escala: () => M.cam.z / zFinal`.
- O 9:16 é recomposição, não corte: a coluna vertical acompanha o "caminho" (norte → sul, origem → destino), os rótulos usam a altura extra acima e abaixo da região.

## Arquivos

- `assets/projeto/lib/mapadoc.js` — a biblioteca do estilo (global `MD`; API em `references/receitas.md`).
- `assets/projeto/videos/exemplo-cafe/` — o demo completo (página, `geo.json`, texturas, créditos).
- `assets/projeto/audio/synth.py` — trilha `documental` + efeitos `flicker` e `decode`.
- `scripts/mapa.py` — baixa relevo (NASA GIBS) e vetores (Natural Earth), tinge as texturas e extrai estados/rios.
- `references/estilo.md` · `movimento.md` · `receitas.md` · `audio.md`.
- `scripts/setup.sh`, `scripts/node.sh`, ferramentas de foto (`commons.py`, `recortar.py`, `cutout.swift`, `texturas.py`) e `analisar.py` (ler referências).
