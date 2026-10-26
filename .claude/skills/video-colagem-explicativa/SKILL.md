---
name: video-colagem-explicativa
description: Cria vídeos curtos (reels/shorts 9:16) no estilo "colagem explicativa" — explainer de colagem sobre papel cinza reciclado, em que cada cena se monta peça a peça em stop-motion de 12 qps: um planeta chapado sobe de baixo e objetos pipocam em anel em volta dele; lixeiras e pinheiros recortados sobem; pessoas em foto P&B com borda branca grossa crescem de um ponto do chão diante de um semicírculo verde-água; fotos dentro de manchas de tinta com grade branca; sol de raios tracejados e faixa de cidade subindo; letreiro Poppins verde em caixa-alta que pousa encolhendo. Troca de cena por corte seco ou pan lateral. Feito com páginas HTML animadas quadro a quadro (GSAP + Playwright + ffmpeg), a biblioteca do estilo (lib/colagem.js), fotos do Wikimedia Commons recortadas, vetores com grão de papel e som sintetizado (trilha corporativa leve + papel, pop e latinha). Use sempre que o usuário pedir "colagem explicativa", "explainer de colagem", "vídeo explicativo com recortes", "colagem sobre papel cinza", "estilo ONG/sustentabilidade/reciclagem", "infográfico animado com recortes de foto", "reels educativo montando a cena peça por peça", "stop-motion de papel", ou mandar uma referência nesse visual pedindo algo "nesse estilo" — mesmo que não diga "colagem explicativa".
---

# Vídeo em colagem explicativa

Três marcas, juntas, fazem o estilo:

1. **Papel cinza reciclado vazio** (#dbdbdb, fibras e pintinhas) como mesa única. Nada de moldura, vinheta ou câmera: o papel só "ferve" de leve (a textura troca de posição a cada 2–12 quadros, com brilho ±1,5%). O vazio é parte do visual; a cena tem respiro.
2. **Três materiais na mesma colagem**: pessoas e veículos em **foto P&B com borda branca grossa**; coisas e lugares em **foto colorida recortada sem borda**; e **ícones vetoriais chapados com grão de papel** (planeta, lixeiras, pinheiros com riscos brancos, sol de raios tracejados, latas com contorno branco), mais **manchas de tinta** (retângulo verde, semicírculo verde-água, quadradinhos amarelo e azul), **grade branca fina** e **círculo tracejado**.
3. **A cena se monta peça a peça em stop-motion de 12 qps**: sobe de baixo passando um pouco do ponto, cresce de um ponto do chão, pipoca em anel um a um, cai e quica. Entre cenas, corte seco ou pan lateral liso.

O texto é pouco: um letreiro Poppins SemiBold verde em caixa-alta + uma linha Poppins Regular escura, no topo, que entra grande e encolhe até o lugar em 3 degraus (como o logo da referência).

Veja `assets/exemplo.mp4` (7,6 s, "A latinha de alumínio — a campeã da reciclagem no Brasil"). O código está em `assets/projeto/videos/exemplo-latinha/index.html` e é o ponto de partida de todo vídeo novo.

## Preparar o projeto (uma vez por pasta)

```bash
bash <caminho-da-skill>/scripts/setup.sh <pasta-do-projeto>
cd <pasta-do-projeto> && N=$(bash tools/node.sh)
```

Requisitos: Node ≥ 20 (o `node.sh` acha um; o PATH pode ter um velho), ffmpeg e python3. O recorte automático de fotos usa o Vision do macOS 14+ (`tools/recortar.py`); fora do Mac, recorte em outro programa e salve PNG com alfa.

Confira que funciona: `$N render.mjs exemplo --preview=6` → `previews/exemplo-latinha.jpg`.

## Fluxo

1. **Roteiro.** 4–6 cenas de 1,3–1,8 s cada, contando um processo (problema → onde vai → quem faz → transformação → resultado). Uma frase curta por cena: letreiro de 2–5 palavras (≤ 22 caracteres cabe em 70 px) + linha de 3–7 palavras. Não invente números; use fatos seguros. Escreva a tabela `T` de tempos antes de desenhar (`references/movimento.md`).
2. **Para cada cena, escolha o tipo** (`references/estilo.md`, "Cenas-tipo"): planeta + anel, cenário de ícones (lixeiras/pinheiros), pessoa P&B diante de semicírculo, foto em mancha com grade, sol + faixa de cidade. Misture os três materiais em cada cena.
3. **Recursos** (`references/receitas.md`):
   - fotos do Commons: `audio/.venv/bin/python tools/commons.py buscar "termo em inglês" --n 12 --folha previews/c.jpg`, olhe a folha, `baixar "File:…" videos/<nn>/img/x.jpg`;
   - recorte: `tools/recortar.py x.jpg x_cut.png` (Vision). Céu de horizonte se tira por cor (receita em `receitas.md`);
   - pessoa: `tools/colagem.py adesivo x_cut.png x_pb.png --largura <px na tela>` (P&B + borda branca);
   - foto em mancha: `tools/colagem.py pb x_cut.png x_pb.png --largura 820` (P&B sem borda, base desbotando);
   - lugar/coisa colorida: `tools/colagem.py tamanho x_cut.png x_s.png --largura <px>`;
   - papel: `tools/colagem.py papel videos/<nn>/img/papel.jpg`;
   - planeta: `tools/globo.py videos/<nn>/img/globo.json --lon -50 --lat -8 --destaque brasil`.
4. **Montar:** `cp -R videos/exemplo-latinha videos/<nn-nome>` e troque fotos, textos e peças mantendo a gramática.
5. **Preview:** `$N render.mjs <nn> --at=0.5,1.4,2.2,3.5,5,7` (ou `--preview=12`) → `previews/<nn-nome>*` e corrija.
6. **Som e render:** `$N render.mjs <nn> --at=1` (grava `cues.json`), `audio/.venv/bin/python audio/synth.py <nn>`, `$N render.mjs <nn>` → `out/<nn-nome>.mp4` (ver `references/audio.md`).
7. **Conferir:** `ffprobe` (1080×1920, duração, uma faixa de áudio), folha a 8 qps do mp4 (`ffmpeg -i out/x.mp4 -vf "fps=8,scale=216:384,tile=10x7" -frames:v 1 previews/f8.jpg`), letreiro legível no celular, crédito das fotos no rodapé quando a licença pedir.

## Regras do motor

- Tudo é função do tempo (`onTick(t => …)` ou `TL`); nada de animação CSS, `setTimeout` ou `Math.random()` (use `K.rng`).
- Use os movimentos de `CE` (`sobe`, `cresce`, `pipoca`, `pousa`, `cai`, `pan`, `traca`): eles já quantizam o tempo em 12 qps e marcam o som. Movimento liso só no pan e nas rotações lentas (anel, raios do sol).
- `.ce-peca` nasce escondida (`visibility:hidden`). Peça que não tem entrada animada precisa de `gsap.set(el, {autoAlpha: 1})`. Grupo que contém peças precisa de `visibility:visible` no `css`, senão os filhos herdam o escondido (o `autoAlpha` do GSAP põe `visibility: inherit`).
- `mix-blend-mode` vai na `.ce-peca` (que cria o contexto de empilhamento), não no filho, senão não mistura com a foto de baixo.
- Peça que cai deve **surgir abaixo do letreiro** (`dist` de −600 a −800), não do topo da tela: em degraus de 12 qps ela fica parada atrás das letras.
- Cada cena é um `.cena` com `display` controlado por `CE.cenas({...})`; no pan, as duas cenas ficam visíveis juntas.

## Arquivos

- `assets/projeto/lib/colagem.js` — a biblioteca do estilo (API em `references/receitas.md`).
- `assets/projeto/audio/synth.py` — trilha `explainer` e efeitos `lata` e `fogo`, além dos padrões.
- `scripts/colagem.py` (papel, adesivo, pb, tamanho) · `scripts/globo.py` + `scripts/ne/` (Natural Earth) · `commons.py` · `recortar.py` + `cutout.swift` · `analisar.py` (ler e comparar com uma referência).
- `references/estilo.md` · `movimento.md` · `receitas.md` · `audio.md`.
