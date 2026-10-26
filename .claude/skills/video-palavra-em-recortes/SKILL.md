---
name: video-palavra-em-recortes
description: Cria vídeos curtos (reels/shorts 9:16) no estilo "palavra em recortes" — o efeito "paper cut"/"recap" em que a MESMA palavra aparece grifada em vários textos diferentes, trocando a cada 3 quadros (semicolcheia a 150 bpm) sempre parada no centro da tela, enquanto o papel, a fonte e o grifo mudam (jornal, revista, caderno pautado, máquina de escrever, kraft, livro antigo, recibo, post-it, papel escuro…; marca-texto, sublinhado de caneta, círculo à mão, tarja preta, recorte colado, carimbo…), com lente velha (zoom e giro acumulando, vinheta oval, aberração cromática, linhas de varredura, profundidade de campo), voz de fita descendo + clique por recorte, uma batida de preto mudo e o drop em que as palavras viram recortes colados formando a frase. Feito com páginas HTML animadas quadro a quadro (GSAP + Playwright + ffmpeg), a biblioteca do estilo (lib/recortes.js), texturas de papel geradas e som sintetizado. Use sempre que o usuário pedir "paper cut", "recap", "a mesma palavra em vários textos/jornais/livros", "palavra grifada piscando", "palavra destacada em recortes de matéria", "montagem de palavra", "intro de recap", "frase palavra por palavra em recortes", "bilhete de recortes", "texto de jornal com marca-texto rápido", vinheta/abertura tipográfica para reels, ou mandar uma referência nesse visual pedindo algo "nesse estilo" — mesmo que não diga "paper cut".
---

# Vídeo em palavra em recortes

Três marcas, juntas, fazem o estilo:

1. **A mesma palavra, parada no centro, em vários textos diferentes.** A cada 3 quadros (0,1 s = semicolcheia a 150 bpm) troca tudo em volta — o papel, a fonte, o grifo, a frase em que a palavra está —, mas a palavra grifada não sai do lugar. É isso que a deixa legível a 10 trocas por segundo e dá a sensação de "a palavra está em todo lugar".
2. **Lente velha que vai fechando.** Zoom (1,0 → 1,5–1,6×) e giro (0 → ±7°) acumulam ao longo da montagem, cada recorte tem um empurrão próprio que acelera, e por cima há vinheta oval forte no começo, aberração cromática vermelho/ciano, linhas de varredura, profundidade de campo (linhas longe do centro desfocadas) e um 1º quadro estourado.
3. **Som de fita + clique, e depois silêncio.** Uma "voz de fita" harmônica desce de tom picotada a cada recorte, com um clique em cada troca; ao fim, **1 batida de preto mudo** e o drop (trap/drill 150 bpm), em que as palavras viram recortes colados formando a frase.

A variedade é controlada: 11 **materiais** (papel + fontes + tinta que combinam) × 13 **grifos**. Sorteados com semente (sempre o mesmo resultado), sem repetir o material duas vezes seguidas.

Veja `assets/exemplo.mp4` (8,4 s, frase "Uma palavra muda tudo"). O código está em `assets/projeto/videos/exemplo-uma-palavra/index.html` e é o ponto de partida de todo vídeo novo.

## Preparar o projeto (uma vez por pasta)

```bash
bash <caminho-da-skill>/scripts/setup.sh <pasta-do-projeto>
cd <pasta-do-projeto> && N=$(bash tools/node.sh)
```

Requisitos: Node ≥ 20 (o `node.sh` acha um; o PATH pode ter um velho), ffmpeg e python3. Nada é baixado além do npm (gsap, playwright): as texturas de papel são geradas (`tools/papeis.py`) e as fontes vêm em `lib/fonts/` (OFL).

## Fluxo

1. **Texto.** Uma frase curta e forte de 2–6 palavras (ou uma palavra só, como a referência). Para **cada** palavra escreva **10 trechos** `[antes, depois, topo?]` em português em que ela aparece naturalmente — é o texto da "matéria" em volta dela. O 10º (o que segura na tela) pode ser a própria frase com a palavra da vez grifada. Regras em `references/receitas.md` ("Escrever os trechos"). Não invente números nem fatos.
2. **Montar:** `cp -R videos/exemplo-uma-palavra videos/<nn-nome>` e troque `palavras`/`frases`, a colagem e a tabela `T` (`references/movimento.md`). Mantenha `bpm: 150`, `q: 3` e `segura: 9`: é o ritmo medido.
3. **Variar:** deixe o sorteio escolher papel/fonte/grifo, ou fixe nas páginas que importam (`Object.assign([antes, depois, ''], {material, fonte, grifo})`), principalmente na última de cada palavra, que vira o recorte da colagem. Catálogo em `references/estilo.md`.
4. **Preview:** `$N render.mjs <nn> --at=0.05,0.5,1.15,2.35,3.55,4.75,5.3,6.6` → `previews/<nn-nome>.jpg`; para o ritmo, `$N render.mjs <nn>` e `audio/.venv/bin/python tools/analisar.py passo out/<nn-nome>.mp4 previews/x --de 0 --ate 1.4`.
5. **Som e render:** `$N render.mjs <nn> --at=1` (grava `cues.json`), `audio/.venv/bin/python audio/synth.py <nn>`, `$N render.mjs <nn>` → `out/<nn-nome>.mp4` (ver `references/audio.md`).
6. **Conferir:** `ffprobe` (1080×1920, duração, uma faixa de áudio), loudness −14 LUFS, a palavra no mesmo ponto em todos os recortes, legível no celular.

## Regras do motor

- Tudo é função do tempo (`onTick`/`TL`): nada de animação CSS, `setTimeout`, `requestAnimationFrame` ou `Math.random()` — a lib usa `K.rng(semente)`, então o sorteio é igual em todo render.
- **Chame `RC.medir()` no `window.SETUP`.** Ele mede cada página (com as fontes já carregadas) e alinha a coluna para a palavra grifada cair exatamente no centro. Sem isso a palavra pula de lugar a cada recorte — e o estilo morre.
- Crie as montagens antes do SETUP (no corpo do script): `RC.palco`, `RC.frase`/`RC.montagem`, `RC.colagem`.
- Fontes: só as de `lib/fonts.css` (40 famílias). Fonte nova = woff2 OFL em `lib/fonts/` + `@font-face`, e uma entrada no material.

## Armadilhas do estilo

- **Palavra que pula.** Medição feita com a página escondida (largura 0) ou sem `RC.medir()`. A lib mostra cada página só durante a medição; não mexa no `display` das páginas por fora.
- **Trecho curto demais.** Se `antes` e `depois` forem curtos, as linhas de cima/baixo dominam e a palavra some na massa de texto. Dê 2–4 palavras de cada lado.
- **Cabeçalho que some.** O `topo` fica alinhado à mesma margem da coluna; com `antes` comprido a margem sai da tela e o cabeçalho curto desaparece. Use `topo` com 15+ caracteres ou deixe vazio.
- **Palavra em caixa diferente.** Materiais `up` (kraft, recibo) põem tudo em maiúsculas; a frase da colagem acompanha. Para manter a caixa, restrinja `materiais` na montagem.
- **Grifo que vira mancha.** `marca` multiplica com o papel: em papel escuro só funciona com cores claras (`lima`, `amarelo`); a lib já troca a cor do texto nesses casos.
- **Montagem lenta demais.** Recortes de 4+ quadros viram slideshow. A referência é 3 quadros (às vezes 4); só o último de cada palavra segura (9 quadros).
- **Colagem estourando a largura.** Palavra comprida em fonte larga (Unbounded, Dela Gothic) passa de 1080 px com `tam` 240: baixe `tam` ou use `esc` no item.

## Arquivos

- `assets/projeto/lib/recortes.js` — a biblioteca, global `RC` (API em `references/receitas.md`).
- `assets/projeto/lib/papeis/*.jpg` — texturas dos materiais (`scripts/papeis.py` refaz e cria novas).
- `references/estilo.md` (as 3 marcas, materiais, grifos, cores, lente) · `movimento.md` (tempos medidos, tabela T, colagem) · `receitas.md` (API e como escrever os trechos) · `audio.md` (fita, cliques, drill).
- `scripts/setup.sh` · `node.sh` · `papeis.py` · `analisar.py` (ler uma referência nova e comparar lado a lado).
