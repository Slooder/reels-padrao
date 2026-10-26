# 01 · Processo

## Como trabalhar com o dono

- Ele manda o bruto (um ou mais takes) e as referências numa pasta `projetos/<NNN. nome>/` (ou no chat). Referências ficam soltas na raiz da pasta.
- **Uma etapa por vez, cada uma aprovada antes da próxima**, nesta ordem (a mesma do 104):
  1. decupagem (só o corte, sem legenda nem insert) → prévia em vídeo leve;
  2. legenda → **prévia em JPG** das primeiras frases (tela cheia + folha de 6 frases) antes de renderizar;
  3. inserts → **prévia em JPG** (folha com todos em ordem + 4 em tamanho real) → prévia rápida do vídeo inteiro;
  4. final (fechamento) → prévia só do trecho final;
  5. render final em qualidade máxima.
- Pedido de ajuste: aplicar só o que foi pedido, mandar prévia de novo. Ele aprova por amostra; o que dá para medir (centro da legenda,
  loudness, duração) eu meço e informo, não peço para ele conferir.
- Mensagens em português simples. Ao entregar: link do arquivo, duração, o que foi medido e o que ficou de fora.
- Vídeo com propaganda eleitoral: lembrar uma vez, na entrega, de confirmar o prazo com advogado eleitoral.

## Passo a passo técnico (copiar o 104 e trocar os dados)

Projeto-modelo: `projetos/104. JP/` (scripts) + `src/videos/jp-testemunhos/` (Remotion). Para um Reels novo `NNN. nome`:

1. **Pasta:** `projetos/NNN. nome/` com `bruto/` (takes originais, nunca alterados), `roteiro/`, `transcricao/`, `render/`, `publicacao/`,
   `broll/bruto/` (material de terceiros) e `broll/tratado/`. Copiar `scripts/` e `da/` do 104.
2. **Transcrever** cada take (palavra por palavra): skill `video-transcricao` → `roteiro/<take>.palavras.json`.
3. **Decupar** em `scripts/plano.py`: `FONTES`, `TRECHOS`, `RESPIROS`, `ZOOM`, `EVENTOS` (inserts), `CARTELA` (final). Ver [02-decupagem.md](02-decupagem.md).
   `python plano.py` grava `roteiro/eventos_v2.json` (lido pelo Remotion).
4. **Base:** `python montagem.py v2` → `render/_base_v2.mp4` (recorte do 4K com o zoom do rosto; ~10 min para 3 min de vídeo).
5. **Palavras da legenda:** `python finalizar.py palavras` → `transcricao/final_v2.palavras.json` (corrige grafias em `CORRECOES`).
6. **Remotion:** copiar `src/videos/jp-testemunhos/` para `src/videos/<slug>/`, trocar `PASTA` e os imports do JSON, registrar a
   composição em `src/Root.tsx` (um `<Folder>` com uma `<Composition>`). `npx tsc --noEmit` tem que passar.
7. **Prévias:**
   - imagens: `npx remotion still <bundle> <Id> saida.png --frame=N` (o bundle sai de `render_remotion.py ... --frames=0-0`);
   - vídeo inteiro rápido: `python render_remotion.py <Id> <saida.mp4> --scale=0.5 --crf=30 --x264-preset=veryfast` (~5 min, ~15 MB);
   - só um trecho: `--frames=A-B`.
8. **Final:** `python render_remotion.py <Id> render/_remotion_v2.mp4` → `python finalizar.py ../render/_remotion_v2.mp4`
   (só voz, −14 LUFS) → `python checar_legenda.py ../render/final_v2.mp4` (centro ≤ 8 px) → cópia para `publicacao/` + versão leve.

## Ferramentas (onde está cada coisa)

| o quê | onde |
|---|---|
| decupagem, inserts, cartela (dados) | `scripts/plano.py` → `roteiro/eventos_v2.json` |
| base com zoom do rosto | `scripts/montagem.py` |
| palavras da legenda, loudness final | `scripts/finalizar.py` |
| render no Remotion (bundle + junção temporária) | `scripts/render_remotion.py` |
| centro e altura da legenda medidos | `scripts/checar_legenda.py` |
| mapa de região do IBGE como forma única | `scripts/mapa_nordeste.py` |
| composição (base + inserts + legenda + final) | `src/videos/<slug>/JpTestemunhos.tsx`, `insertos.tsx`, `fala.ts` |
| direção de arte (tokens da legenda) | `da/da.json` |
